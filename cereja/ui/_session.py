"""Single-owner acquisition journal and acknowledged terminal output."""

from contextlib import contextmanager
import threading


_owners = {}
_owner_lock = threading.RLock()


class TerminalCleanupError(RuntimeError):
    """All restorations were attempted; these resources may remain unrestored."""

    def __init__(self, failures):
        self.failures = tuple(failures)
        super().__init__(f'{len(self.failures)} terminal restoration(s) failed')


def _safe_text(text):
    if not isinstance(text, str):
        raise TypeError('terminal text must be str')
    result = []
    for char in text:
        code = ord(char)
        if char == '\n':
            result.append(char)
        elif char == '\t':
            result.append('    ')
        elif code < 32 or 127 <= code <= 159:
            result.append(f'\\x{code:02x}')
        elif 0xD800 <= code <= 0xDFFF:
            result.append('\ufffd')
        else:
            result.append(char)
    return ''.join(result)


class TerminalSession:
    """Context-managed transaction over a backend's captured terminal resources.

    Native adapters implement capture/acquire/restore. A restoration must be safe
    even when an acquisition mutated its resource and then raised. One UI thread
    owns both the session and its output. Suspension reserves that ownership while
    restoring modes for external output, then captures and reacquires afresh.
    """

    def __init__(self, backend):
        self.backend = backend
        self.capabilities = backend.capabilities
        self.closed = False
        self.broken_pipe = False
        self.needs_redraw = True
        self.cleanup_failures = ()
        self._active = False
        self._thread = None
        self._owned = False
        self._journal = []
        self._snapshot = None
        self._output_generation = 0

    @property
    def animations_enabled(self):
        return not self.capabilities.plain and not self.capabilities.reduced_motion

    def _check_thread(self):
        if self._thread is not None and self._thread != threading.get_ident():
            raise RuntimeError('terminal session belongs to another thread')

    def _check_active(self):
        self._check_thread()
        if self.closed or not self._active:
            raise RuntimeError('terminal session is not active')

    def __enter__(self):
        self._check_thread()
        if self.closed or self._owned:
            raise RuntimeError('terminal session cannot be entered again')
        identity = self.backend.identity
        with _owner_lock:
            if identity in _owners:
                raise RuntimeError('terminal already has an owner')
            _owners[identity] = self
            self._owned = True
        self._thread = threading.get_ident()
        try:
            self._acquire()
        except BaseException as error:
            self.close(error)
            raise
        return self

    def _acquire(self):
        self.capabilities = self.backend.capabilities
        self._snapshot = self.backend.capture()
        output_probed = bool(getattr(self.backend, 'needs_output_probe', False))
        if output_probed:
            # Native VT support may require a reversible mode change. It is
            # performed only after ownership/capture, under the same journal.
            self._journal.append('output_mode')
            self.backend.acquire('output_mode', self._snapshot)
            self.capabilities = self.backend.capabilities
        if not self.capabilities.plain:
            resources = ['input_mode'] if output_probed else ['output_mode', 'input_mode']
            if self.capabilities.alternate_screen:
                resources.append('alternate_screen')
            if self.capabilities.cursor:
                resources.append('cursor')
            if self.capabilities.paste:
                resources.append('paste')
            resources.append('signal_handlers')
            for resource in resources:
                # Register restoration before a backend can partially mutate it.
                self._journal.append(resource)
                self.backend.acquire(resource, self._snapshot)
        self._active = True

    def _unwind(self):
        self._active = False
        failures = []
        while self._journal:
            resource = self._journal.pop()
            try:
                self.backend.restore(resource, self._snapshot)
            except BaseException as error:
                failures.append((resource, error))
        self.cleanup_failures += tuple(failures)
        return failures

    def close(self, initiating_error=None):
        self._check_thread()
        if self.closed:
            return
        failures = self._unwind()
        self.closed = True
        if self._owned:
            with _owner_lock:
                if _owners.get(self.backend.identity) is self:
                    del _owners[self.backend.identity]
            self._owned = False
        if failures:
            if initiating_error is not None:
                for resource, error in failures:
                    try:
                        # Neither exception repr nor an overridden add_note may
                        # replace the initiating failure. Raw failures remain owned.
                        BaseException.add_note(initiating_error,
                            f'Terminal restoration failed ({resource}); '
                            'see session.cleanup_failures')
                    except BaseException:
                        pass
            else:
                raise TerminalCleanupError(failures)

    def __exit__(self, error_type, error, traceback):
        self.close(error)
        return False

    @contextmanager
    def suspend(self):
        self._check_active()
        failures = self._unwind()
        if failures:
            self.close()
            raise TerminalCleanupError(failures)
        try:
            yield
        except BaseException as error:
            self.close(error)
            raise
        else:
            if not self.closed:
                try:
                    self._acquire()
                    self.needs_redraw = True
                    self.backend.invalidate()
                except BaseException as error:
                    self.close(error)
                    raise

    def write_text(self, text):
        """Write ordinary text with visible control escapes, including in plain mode."""
        safe = _safe_text(text)
        result = self._write_frame(safe)
        if safe:
            self.needs_redraw = True
        return result

    def _write_frame(self, text, *, cells=None):
        """Internal encoder transport, not an arbitrary ANSI drawing API.

        Commit virtual cells only after all characters and flush succeed. Actual
        composition/encoding and unchanged-frame detection belong to the renderer.
        """
        self._check_active()
        if not isinstance(text, str):
            raise TypeError('encoded frame must be str')
        if self.capabilities.plain:
            text = _safe_text(text)
        if not text:
            return True
        self._output_generation += 1
        self.needs_redraw = True
        try:
            offset = 0
            while offset < len(text):
                count = self.backend.write(text[offset:])
                if type(count) is not int or not 0 < count <= len(text) - offset:
                    raise OSError('terminal write did not acknowledge valid progress')
                offset += count
            self.backend.flush()
            if cells is not None:
                commit = getattr(self.backend, 'commit_cells', None)
                if commit is not None:
                    commit(cells)
            self.needs_redraw = False
            return True
        except BrokenPipeError:
            self.needs_redraw = True
            self.broken_pipe = True
            # A broken pipe can stop cleanly only if terminal restoration succeeds.
            self.close()
            return False
        except BaseException as error:
            self.needs_redraw = True
            self.close(error)
            raise
