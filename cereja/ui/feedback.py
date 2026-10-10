"""Opt-in inline feedback. No domain work, clipboard, focus or redraw loop."""
from itertools import count
import threading

from .buffer import CellBuffer, Rect
from .editing import TextContent
from .events import TimerEvent
from .text import text_metrics

__all__ = ['InlineStatus', 'ProgressBar', 'ActivityIndicator']

_LABELS = {'loading': 'Loading', 'empty': 'Empty', 'error': 'Error',
           'success': 'Done', 'warning': 'Warning', 'idle': 'Idle', 'canceled': 'Canceled'}
_OWNERS = count(1)
_MAX_TEXT = 65536
_MAX_COUNT = 2**63 - 1


def _bool(value, name):
    if type(value) is not bool:
        raise TypeError(f'{name} must be bool')


def _count(value):
    # Counts deliberately exclude bool, floats, NaN and unbounded integer text.
    return type(value) is int and 0 <= value <= _MAX_COUNT


class _Feedback:
    def __init__(self, identity):
        if not isinstance(identity, str) or not identity or len(identity.encode('utf-8')) > 4096:
            raise ValueError('identity must be nonempty text of at most 4096 UTF-8 bytes')
        self._identity = identity
        self._thread = threading.get_ident()
        self._content = None

    def _owned(self):
        if threading.get_ident() != self._thread:
            raise RuntimeError('feedback belongs to the UI thread')

    @property
    def content(self):
        """Safe canonical text; visual frames never replace its revision."""
        return self._content

    def _replace(self, text):
        if not isinstance(text, str):
            raise TypeError('message must be text')
        if len(text) > _MAX_TEXT:
            raise ValueError('feedback exceeds canonical byte limit')
        revision = 0 if self._content is None else self._content.revision + 1
        content = TextContent(self._identity, revision, text)
        if len(content.text.encode('utf-8')) > _MAX_TEXT:
            raise ValueError('feedback exceeds canonical byte limit')
        if self._content is None or content.text != self._content.text:
            self._content = content

    def _area(self, frame, rect, clip):
        if not isinstance(frame, CellBuffer) or not isinstance(rect, Rect):
            raise TypeError('paint requires CellBuffer and Rect')
        if clip is not None and not isinstance(clip, Rect):
            raise TypeError('clip must be Rect or None')
        line = Rect(rect.x, rect.y, rect.width, min(rect.height, 1))
        area = line.intersection(Rect(0, 0, frame.width, frame.height))
        return area if clip is None else area.intersection(clip)

    def _display(self, frame, rect):
        return self.content.text.split('\n', 1)[0]

    def paint(self, frame, rect, *, clip=None):
        """Clear and paint one clipped row; return its bounded damage rectangle."""
        self._owned()
        area = self._area(frame, rect, clip)
        if area.width and area.height:
            frame.clear(clip=area)
            frame.draw_text(rect.x, rect.y, self._display(frame, rect), clip=area)
        return area


class InlineStatus(_Feedback):
    """Persistent labelled loading/empty/error/success/warning/idle/canceled."""
    def __init__(self, identity, state, message):
        super().__init__(identity)
        self._set(state, message)

    @property
    def state(self):
        return self._state

    def _set(self, state, message):
        if not isinstance(state, str) or state not in _LABELS:
            raise ValueError('unsupported inline state')
        if not isinstance(message, str):
            raise TypeError('message must be text')
        self._replace(_LABELS[state] + (': ' + message if message else ''))
        self._state = state

    def update(self, state, message):
        self._owned()
        self._set(state, message)


class ProgressBar(_Feedback):
    """Only caller-observed integer counts and an explicitly trusted denominator.

    Invalid/untrusted progress renders a textual unavailable/unknown-total state,
    without a bar or percentage. Counts alone never establish operation success.
    """
    def __init__(self, identity, message, *, completed=None, total=None, reliable_total=False):
        super().__init__(identity)
        self.update(message, completed=completed, total=total, reliable_total=reliable_total)

    @property
    def determinate(self):
        return self._determinate

    @property
    def percent(self):
        return self._percent

    def update(self, message, *, completed=None, total=None, reliable_total=False):
        self._owned()
        _bool(reliable_total, 'reliable_total')
        if not isinstance(message, str):
            raise TypeError('message must be text')
        valid = (_count(completed) and _count(total) and total > 0
                 and completed <= total and reliable_total)
        percent = completed * 100 // total if valid else None
        if valid:
            numbers = f'{completed}/{total} ({percent}%)'
        elif _count(completed):
            numbers = f'{completed} completed; total unavailable'
        else:
            numbers = 'Progress unavailable'
        self._replace('Progress: ' + numbers + (': ' + message if message else ''))
        self._determinate, self._percent = valid, percent
        self._completed, self._total = completed if valid else None, total if valid else None

    def _display(self, frame, rect):
        text = super()._display(frame, rect)
        # Keep the useful state/counts first. A bar only uses remaining cells.
        remaining = min(22, rect.width - text_metrics(text, frame.policy).line_widths()[0] - 1)
        if self.determinate and remaining >= 5:
            cells = remaining - 2
            filled = self._completed * cells // self._total
            text += ' [' + '#' * filled + '.' * (cells - filled) + ']'
        return text


class ActivityIndicator(InlineStatus):
    """Spinner OR three-cell dots for caller-confirmed active loading.

    Paint after real updates/resize to synchronize visibility and motion policy.
    Route TimerEvent by owner; handle() reports damage without submitting frames.
    Hiding/closing cancels its timer. No application operation is canceled here.
    """
    def __init__(self, loop, identity, message, *, active=False, kind='spinner', motion=True):
        from .scheduling import EventLoop
        if not isinstance(loop, EventLoop):
            raise TypeError('indicator needs EventLoop')
        _bool(active, 'active')
        _bool(motion, 'motion')
        if kind not in ('spinner', 'dots'):
            raise ValueError('kind must be spinner or dots')
        super().__init__(identity, 'loading', message)
        loop._check_active()
        self._loop, self._kind = loop, kind
        self._active, self._motion = active, motion
        self._visible, self._closed = True, False
        self._timer = None
        self._phase = 0
        self._owner = f'ui.feedback:{next(_OWNERS)}'
        self._motion_notice = ''

    @property
    def owner(self):
        return self._owner

    @property
    def timer_id(self):
        return self._timer if self._loop.has_timer(self._timer) else None

    @property
    def motion_notice(self):
        return self._motion_notice

    def _live(self):
        self._owned()
        if self._closed:
            raise RuntimeError('indicator is closed')

    def _cancel(self):
        if not self._loop.stopped and not self._loop.session.closed:
            self._loop.cancel_owner(self.owner)
        self._timer = None
        self._phase = 0
        self._motion_notice = ''

    def update(self, state, message, *, active=False):
        self._live()
        _bool(active, 'active')
        if active and state != 'loading':
            raise ValueError('only loading can assert active work')
        self._set(state, message)
        self._active = active
        if not active:
            self._cancel()

    def set_visible(self, visible):
        self._live()
        _bool(visible, 'visible')
        self._visible = visible
        if not visible:
            self._cancel()

    def set_motion(self, enabled):
        self._live()
        _bool(enabled, 'enabled')
        self._motion = enabled
        if not enabled:
            self._cancel()

    def close(self):
        self._owned()
        if not self._closed:
            self._cancel()
            self._closed = True

    def handle(self, event):
        self._owned()
        if (self._closed or type(event) is not TimerEvent or event.owner != self.owner
                or event.timer_id != self.timer_id or not self._active):
            return False
        self._phase = (self._phase + 1) % 4
        return True

    def paint(self, frame, rect, *, clip=None):
        self._live()
        area = self._area(frame, rect, clip)
        # A clipped-away marker has no visible animation to schedule.
        marker_width = 1 if self._kind == 'spinner' else 3
        marker = Rect(rect.x, rect.y, min(marker_width, rect.width), min(1, rect.height)).intersection(area)
        eligible = (self._visible and self._active and self._motion and marker.width
                    and marker.height and not self._loop.stopped and not self._loop.session.closed)
        if not eligible:
            self._cancel()
        elif self.timer_id is None:
            try:
                self._timer = self._loop.call_later(self._loop.indicator_interval,
                    owner=self.owner, interval=self._loop.indicator_interval,
                    decorative=True, spinner=True)
                self._motion_notice = ''
            except OverflowError:
                # Real state remains readable; retry only at an explicit paint.
                self._timer = None
                self._motion_notice = 'Animation timer capacity unavailable'
        if not self._visible:
            if area.width and area.height:
                frame.clear(clip=area)
            return area
        return super().paint(frame, rect, clip=clip)

    def _display(self, frame, rect):
        marker = '   '
        if self.timer_id is not None:
            marker = ('|/-\\'[self._phase] + '  ' if self._kind == 'spinner'
                      else ('.' * (self._phase + 1 if self._phase < 3 else 0)).ljust(3))
        return marker + ' ' + super()._display(frame, rect)
