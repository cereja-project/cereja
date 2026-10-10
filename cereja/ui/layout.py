"""Composable cell geometry and lazy scroll windows, without application state.

Import explicitly. Rectangles, text occupancy and painting remain owned by
ui.buffer; dirty comparison remains owned by ui.rendering. No terminal I/O,
content enumeration, widget tree, timer, cache or domain integration is implied.
"""

from dataclasses import dataclass, replace
from itertools import zip_longest
from typing import Iterable

from .buffer import Rect, _integer


__all__ = ['Constraint', 'split_rows', 'split_columns', 'inset', 'Viewport', 'layout_damage']


def _rect(value, name):
    if not isinstance(value, Rect):
        raise TypeError(f'{name} must be Rect')


@dataclass(frozen=True, slots=True)
class Constraint:
    """Track minimum/maximum cells and integer weight for remaining space.

    Zero weight keeps the minimum. Maximum None is unbounded. If minima cannot
    fit, they are clipped in iterable order; application recovery policy is
    separate. Equal fractional remainders favor the earlier track.
    """

    minimum: int = 0
    maximum: int | None = None
    weight: int = 1

    def __post_init__(self):
        _integer(self.minimum, 'minimum', nonnegative=True)
        _integer(self.weight, 'weight', nonnegative=True)
        if self.maximum is not None:
            _integer(self.maximum, 'maximum', nonnegative=True)
            if self.maximum < self.minimum:
                raise ValueError('maximum must be at least minimum')

    @classmethod
    def fixed(cls, size: int) -> 'Constraint':
        return cls(size, size, 0)


def _allocate(span, constraints):
    sizes, remaining = [], span
    for item in constraints:
        size = min(item.minimum, remaining)
        sizes.append(size)
        remaining -= size
    eligible = [i for i, item in enumerate(constraints)
                if item.weight and (item.maximum is None or sizes[i] < item.maximum)]
    while remaining and eligible:
        total = sum(constraints[i].weight for i in eligible)
        # Fix capped tracks first, then redistribute their unused weighted
        # share. At most one round per capped track plus the final division;
        # never loop once per cell or per content item.
        capped = [i for i in eligible if constraints[i].maximum is not None and
                  remaining * constraints[i].weight >= (constraints[i].maximum - sizes[i]) * total]
        if capped:
            for i in capped:
                growth = constraints[i].maximum - sizes[i]
                sizes[i] += growth
                remaining -= growth
            cap_set = set(capped)
            eligible = [i for i in eligible if i not in cap_set]
            continue
        remainders = []
        allocated = 0
        for i in eligible:
            growth, remainder = divmod(remaining * constraints[i].weight, total)
            sizes[i] += growth
            allocated += growth
            remainders.append((-remainder, i))
        for _, i in sorted(remainders)[:remaining - allocated]:
            sizes[i] += 1
        remaining = 0
    return sizes


def _split(bounds, constraints, gap, *, vertical):
    _rect(bounds, 'bounds')
    _integer(gap, 'gap', nonnegative=True)
    constraints = tuple(constraints)
    if any(not isinstance(item, Constraint) for item in constraints):
        raise TypeError('constraints must contain Constraint values')
    span = bounds.height if vertical else bounds.width
    gaps = min(span, gap * max(0, len(constraints) - 1))
    sizes = _allocate(span - gaps, constraints)
    offset, result = 0, []
    for size in sizes:
        if vertical:
            result.append(Rect(bounds.x, bounds.y + offset, bounds.width, size))
        else:
            result.append(Rect(bounds.x + offset, bounds.y, size, bounds.height))
        offset = min(span, offset + size + gap)
    return tuple(result)


def split_rows(bounds: Rect, constraints: Iterable[Constraint], *, gap: int = 0) -> tuple[Rect, ...]:
    """Partition vertically in cell rows; nest using any returned rectangle."""
    return _split(bounds, constraints, gap, vertical=True)


def split_columns(bounds: Rect, constraints: Iterable[Constraint], *, gap: int = 0) -> tuple[Rect, ...]:
    """Partition horizontally in cell columns; surplus may remain at the end."""
    return _split(bounds, constraints, gap, vertical=False)


def inset(bounds: Rect, *, left: int = 0, top: int = 0, right: int = 0,
          bottom: int = 0) -> Rect:
    """Apply nonnegative padding, saturating empty geometry inside bounds."""
    _rect(bounds, 'bounds')
    for name, value in (('left', left), ('top', top), ('right', right), ('bottom', bottom)):
        _integer(value, name, nonnegative=True)
    return Rect(bounds.x + min(left, bounds.width), bounds.y + min(top, bounds.height),
                max(0, bounds.width - left - right), max(0, bounds.height - top - bottom))


@dataclass(frozen=True, slots=True)
class Viewport:
    """A cell window over caller-owned content, with optional ancestor clipping.

    Requested scroll anchors survive zero/undersized viewports. Effective offsets
    clamp to current content and window dimensions. Visible is a content-space
    rectangle, origin translates content to destination cells, and clip_rect is
    the destination-space intersection for buffer painting. Neither text nor
    items, selection identity, editing state or follow-latest are owned here.
    """

    rect: Rect
    content_width: int
    content_height: int
    scroll_x: int = 0
    scroll_y: int = 0
    clip: Rect | None = None

    def __post_init__(self):
        _rect(self.rect, 'rect')
        for name in ('content_width', 'content_height', 'scroll_x', 'scroll_y'):
            _integer(getattr(self, name), name, nonnegative=True)
        if self.clip is not None:
            _rect(self.clip, 'clip')

    @property
    def offset(self) -> tuple[int, int]:
        return (min(self.scroll_x, max(0, self.content_width - self.rect.width)),
                min(self.scroll_y, max(0, self.content_height - self.rect.height)))

    @property
    def origin(self) -> tuple[int, int]:
        x, y = self.offset
        return self.rect.x - x, self.rect.y - y

    @property
    def clip_rect(self) -> Rect:
        return self.rect if self.clip is None else self.rect.intersection(self.clip)

    @property
    def visible(self) -> Rect:
        clip, (ox, oy) = self.clip_rect, self.origin
        x = min(self.content_width, max(0, clip.x - ox))
        y = min(self.content_height, max(0, clip.y - oy))
        return Rect(x, y, min(clip.width, self.content_width - x),
                    min(clip.height, self.content_height - y))

    def resized(self, rect: Rect, *, clip: Rect | None = None) -> 'Viewport':
        """Preserve requested anchors; supply the newly arranged ancestor clip."""
        return replace(self, rect=rect, clip=clip)

    def scrolled(self, *, dx: int = 0, dy: int = 0) -> 'Viewport':
        """Move from effective offsets, clamping to content; hidden is a no-op."""
        _integer(dx, 'dx')
        _integer(dy, 'dy')
        if not self.clip_rect.width or not self.clip_rect.height:
            return self
        x, y = self.offset
        return replace(self, scroll_x=min(max(0, x + dx), max(0, self.content_width - self.rect.width)),
                       scroll_y=min(max(0, y + dy), max(0, self.content_height - self.rect.height)))

    def ensure_visible(self, target: Rect) -> 'Viewport':
        """Reveal a retained content target without owning/changing selection.

        Oversized targets align their start; ancestor clipping or content bounds
        can prevent full exposure. Empty windows/targets preserve anchors.
        """
        _rect(target, 'target')
        if (target.x < 0 or target.y < 0 or target.x + target.width > self.content_width or
                target.y + target.height > self.content_height):
            raise ValueError('target must be contained in content')
        visible = self.visible
        if not visible.width or not visible.height or not target.width or not target.height:
            return self

        def reveal(start, size, visible_start, visible_size, offset, content_size, window_size):
            if start < visible_start or size > visible_size:
                offset += start - visible_start
            elif start + size > visible_start + visible_size:
                offset += start + size - visible_start - visible_size
            return min(max(0, offset), max(0, content_size - window_size))

        x, y = self.offset
        return replace(self,
                       scroll_x=reveal(target.x, target.width, visible.x, visible.width,
                                       x, self.content_width, self.rect.width),
                       scroll_y=reveal(target.y, target.height, visible.y, visible.height,
                                       y, self.content_height, self.rect.height))


def layout_damage(before: Iterable[Rect], after: Iterable[Rect], bounds: Rect, *,
                  max_regions: int = 64) -> tuple[Rect, ...]:
    """Old/new geometry damage by stable slot order, clipped to frame bounds.

    Identical geometry has no layout damage; content/style/scroll changes must
    be marked by the caller separately. Removed and moved old bounds are kept.
    Overflow falls back to one full bounds rectangle, without a persistent queue.
    The renderer still owns resize/policy invalidation and whole-glyph diffing.
    """
    _rect(bounds, 'bounds')
    _integer(max_regions, 'max_regions', nonnegative=True)
    if not max_regions:
        raise ValueError('max_regions must be positive')
    before, after = tuple(before), tuple(after)
    if any(not isinstance(rect, Rect) for rect in before + after):
        raise TypeError('geometry must contain Rect values')
    result, seen = [], set()
    for old, new in zip_longest(before, after):
        if old == new:
            continue
        for rect in (old, new):
            if rect is None:
                continue
            clipped = bounds.intersection(rect)
            if clipped.width and clipped.height and clipped not in seen:
                result.append(clipped)
                seen.add(clipped)
                if len(result) > max_regions:
                    return (bounds,)
    return tuple(result)
