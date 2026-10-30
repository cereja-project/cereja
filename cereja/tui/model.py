"""UI-owned ephemeral result retention; logical bytes are not a heap/RSS limit."""
from dataclasses import dataclass

from cereja.ui.editing import TextContent, TextSelection
from cereja.ui.text import normalize_text, grapheme_spans


def bounded_text(text, limit):
    # Callers supply redacted text. No arbitrary object conversion or graph retention.
    if type(text) is not str:
        raise TypeError('result text must be a string')
    raw_cut = len(text) > limit
    safe = normalize_text(text[:limit])
    encoded = safe.encode('utf-8')
    if not raw_cut and len(encoded) <= limit:
        return safe, False
    marker = '\n[Content truncated]'
    prefix = encoded[:max(0, limit - len(marker))].decode('utf-8', 'ignore')
    # Drop the final cluster, which may have been cut inside a combining sequence.
    end = 0
    for start, _ in grapheme_spans(prefix):
        end = start
    return prefix[:end] + marker, True


@dataclass(slots=True)
class ResultBlock:
    identity: str
    command: str
    content: TextContent
    state: str = 'Succeeded'
    active: bool = False
    truncated: bool = False
    anchor: int = 0
    selection: TextSelection | None = None
    attachment: str = ''

    @property
    def payload_bytes(self):
        size = len((self.identity + self.command + self.state + self.content.text + self.attachment).encode('utf-8'))
        if self.selection is not None and self.selection.content is not self.content:
            size += len(self.selection.content.text.encode('utf-8'))
        return size


class Results:
    """Keep 20 completed blocks, one active block and at most 256 KiB of safe payload.

    Per-block content is 16 KiB. Selection can pin one previous canonical revision.
    Active admission reserves two revisions plus metadata before accepting a job.
    """

    def __init__(self, *, max_completed=20, max_bytes=256 * 1024, block_bytes=16384):
        if any(type(x) is not int for x in (max_completed, max_bytes, block_bytes)):
            raise TypeError('retention bounds must be integers')
        if max_completed < 1 or block_bytes < 64 or max_bytes < block_bytes + 128:
            raise ValueError('retention bounds too small')
        self.max_completed, self.max_bytes, self.block_bytes = max_completed, max_bytes, block_bytes
        self.blocks = []
        self.selected = None
        self.follow_latest = True
        self.omitted = 0
        self._sequence = 0

    @property
    def retained_bytes(self):
        return sum(block.payload_bytes for block in self.blocks)

    @property
    def current(self):
        return next((block for block in self.blocks if block.identity == self.selected), None)

    def _trim(self):
        while (sum(not b.active for b in self.blocks) > self.max_completed or
               self.retained_bytes > self.max_bytes):
            index = next((i for i, b in enumerate(self.blocks) if not b.active), None)
            if index is None:
                raise ValueError('active result exceeds retention capacity')
            removed = self.blocks.pop(index)
            self.omitted += 1
            if self.selected == removed.identity:
                survivors = self.blocks[index:] or self.blocks[max(0, index - 1):index]
                self.selected = survivors[0].identity if survivors else None

    def append(self, command, text, *, active=False):
        if command not in ('/' + name for name in (
                'home', 'system', 'tree', 'large-files', 'context', 'compress', 'download',
                'examples', 'tools', 'diagnostics', 'help')):
            raise ValueError('results retain registered command identity only')
        if active and any(b.active for b in self.blocks):
            raise ValueError('one active result only')
        self._sequence += 1
        identity = 'result-' + str(self._sequence)
        safe, truncated = bounded_text(text, self.block_bytes)
        block = ResultBlock(identity, command, TextContent(identity, 0, safe),
                            'Validating' if active else 'Succeeded', active, truncated)
        if active and self.max_bytes < 2 * self.block_bytes + 128:
            raise ValueError('active result needs capacity for a pinned revision')
        self.blocks.append(block)
        if self.follow_latest or self.selected is None:
            self.selected = identity
        self._trim()
        return block

    def finish(self, block, state, text, *, attachment=''):
        if block not in self.blocks or not block.active:
            raise ValueError('result is not the active block')
        safe, truncated = bounded_text(text, self.block_bytes)
        if type(attachment) is not str or len(attachment.encode('utf-8')) > 48000:
            raise ValueError('attachment must be bounded serialized data')
        block.attachment = attachment
        block.content = TextContent(block.identity, block.content.revision + 1, safe)
        block.state, block.active, block.truncated = state, False, truncated
        self._trim()

    def select(self, identity, *, latest=False):
        if not any(block.identity == identity for block in self.blocks):
            raise ValueError('unknown result')
        self.selected, self.follow_latest = identity, latest

    def latest(self):
        if self.blocks:
            self.select(self.blocks[-1].identity, latest=True)

    def select_text(self):
        block = self.current
        if block is not None:
            block.selection = TextSelection(block.content, 0, len(block.content.text))
            self.follow_latest = False

    def clear_selection(self):
        for block in self.blocks:
            block.selection = None
