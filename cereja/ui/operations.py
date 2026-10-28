"""One explicit operation, bounded typed publication, no presentation ownership."""
from dataclasses import dataclass
import threading

from ._posting import Cancellation, _text, payload_bytes
from .events import (ProgressEvent, WakeEvent, OperationStartedEvent, OperationPhaseEvent,
                     OperationResultEvent, OperationErrorEvent)

__all__ = ['OperationBridge', 'OperationBusy', 'CooperativeCancellation',
           'OperationContext', 'OperationSnapshot']


class OperationBusy(RuntimeError):
    """A previous operation or its final publication still owns the slot."""


@dataclass(frozen=True)
class CooperativeCancellation:
    """Adapter assertion backed by named domain tests, not automatic certification."""
    evidence: str

    def __post_init__(self):
        if not self.evidence:
            raise ValueError('name the validated cooperative contract')
        _text(self.evidence, limit=4096)


@dataclass(frozen=True)
class OperationSnapshot:
    source: str
    generation: int
    name: str
    state: str
    active: bool
    cancellable: bool
    worker_exited: bool
    delivery: str
    outcome: OperationResultEvent | OperationErrorEvent | None


class _CooperativeStop(BaseException):
    pass


class _PublicationLost(RuntimeError):
    pass


class _Execution:
    def __init__(self, request, name, capability):
        self.request, self.name, self.capability = request, name, capability
        self.lock = threading.Lock()
        # Domain stop and presentation suppression are deliberately separate.
        self.stop = Cancellation()
        self.state = 'Validating'
        self.started_running = False
        self.outcome = None
        self.worker_exited = False
        self.delivery = 'pending'
        self.worker = None
        self.worker_id = None
        self.settling = False


def _error_text(error):
    # Do not retain exception/traceback graphs or invoke arbitrary __str__ code.
    # Only an exact short string first argument is included.
    name = type(error).__name__[:128]
    message = error.args[0] if error.args and type(error.args[0]) is str else ''
    return (name + ': ' + message[:768]).encode('utf-8', 'backslashreplace')[:4096].decode(
        'utf-8', 'ignore')


class OperationContext:
    """Worker-only observed phases, real counts and cooperative checkpoints."""
    def __init__(self, loop, execution):
        self._loop, self._execution = loop, execution

    def _owned(self):
        if threading.get_ident() != self._execution.worker_id:
            raise RuntimeError('operation context belongs to its domain worker')

    def _send(self, event):
        if not self._loop.wait_post(event, cancellation=self._execution.request.cancellation):
            raise _PublicationLost('operation consumer is unavailable')

    def checkpoint(self):
        """A validated adapter calls this only where interruption is safe."""
        self._owned()
        ex = self._execution
        with ex.lock:
            if ex.capability is not None and ex.state != 'Committing' and ex.stop.cancelled:
                raise _CooperativeStop()

    def _phase(self, phase):
        self._owned()
        ex = self._execution
        with ex.lock:
            if ex.capability is not None and ex.stop.cancelled:
                raise _CooperativeStop()
            required = 'Validating' if phase == 'Running' else 'Running'
            if ex.state != required:
                raise RuntimeError('invalid observed operation phase')
            ex.state = phase
            if phase == 'Running':
                ex.started_running = True
        self._send(OperationPhaseEvent(ex.request.source, ex.request.generation, phase))

    def running(self):
        """Report that adapter validation finished and actual work is beginning."""
        self._phase('Running')

    def committing(self):
        """Atomically exclude cancellation before an adapter's observed commit."""
        self._phase('Committing')

    def progress(self, completed, *, total=None, reliable_total=False, message=''):
        """Nonblocking coalescible observation; False means no capacity/consumer."""
        self._owned()
        ex = self._execution
        if type(reliable_total) is not bool:
            raise TypeError('reliable_total must be bool')
        _text(message, limit=4096)
        with ex.lock:
            if not ex.started_running or ex.state not in ('Running', 'Committing', 'CancelRequested'):
                raise RuntimeError('progress requires confirmed activity')
        event = ProgressEvent(ex.request.source, completed,
                              total if reliable_total else None, message,
                              ex.request.generation)
        return self._loop.post(event)


class OperationBridge:
    """UI-owned controller, with one domain worker and one completion observer.

    The one observer joins off the UI thread, then publishes one terminal event.
    It sleeps on a condition between operations and exits on close().
    No operation queue, polling timer, renderer, disk history or domain service
    hooks. Call handle() from the UI handler and close() on consumer disposal.
    A source belongs exclusively to this bridge for its lifetime.
    """
    def __init__(self, loop, source):
        loop._check_active()
        _text(source, limit=4096)
        if not source:
            raise ValueError('source must be nonempty')
        self._loop, self._source = loop, source
        self._execution = None
        self._closed = False
        self._exit_wait = False
        self._condition = threading.Condition()
        self._pending = None
        self._observer = None

    def _owned(self):
        self._loop._check_thread()

    def _delivery(self, ex):
        if ex.delivery in ('pending', 'queued') and ex.worker_exited:
            if self._closed or self._loop.stopped:
                return 'unavailable'
            if not self._loop.request_active(ex.request):
                return 'suppressed'
        return ex.delivery

    @property
    def snapshot(self):
        self._owned()
        ex = self._execution
        if ex is None:
            return OperationSnapshot(self._source, 0, '', 'Idle', False, False,
                                     True, 'none', None)
        with ex.lock:
            delivery = self._delivery(ex)
            active = not ex.worker_exited or delivery in ('pending', 'queued')
            cancellable = (not self._closed and not self._loop.stopped
                           and ex.capability is not None and not ex.settling and ex.outcome is None
                           and ex.state in ('Validating', 'Running'))
            return OperationSnapshot(self._source, ex.request.generation, ex.name,
                ex.state, active, cancellable, ex.worker_exited, delivery,
                ex.outcome if ex.worker_exited else None)

    @property
    def active(self):
        return self.snapshot.active

    @property
    def exit_choices(self):
        snapshot = self.snapshot
        if not snapshot.active:
            return ('exit',)
        return ('return', 'wait', 'cancel') if snapshot.cancellable else ('return', 'wait')

    def start(self, name, operation, *, cleanup=None, cancellation=None):
        self._owned()
        self._loop._check_active()
        if self._closed:
            raise RuntimeError('operation bridge is closed')
        if self.active:
            raise OperationBusy('current operation or final publication is still active')
        _text(name, limit=4096)
        if not name or not callable(operation) or (cleanup is not None and not callable(cleanup)):
            raise TypeError('name and callable operation/cleanup required')
        if cancellation is not None and type(cancellation) is not CooperativeCancellation:
            raise TypeError('cancellation requires a validated CooperativeCancellation contract')
        if self._execution is not None:
            self._loop.forget_request(self._source, request=self._execution.request)
        request = self._loop.begin_request(self._source)
        ex = _Execution(request, name, cancellation)
        with self._condition:
            if self._observer is None:
                try:
                    observer = threading.Thread(target=self._observe,
                        name='cereja-operation-observer', daemon=False)
                    self._observer = observer
                    observer.start()
                except BaseException:
                    self._observer = None
                    self._loop.forget_request(self._source, request=request)
                    raise
            self._execution = ex
            try:
                worker = threading.Thread(target=self._work, args=(ex, operation, cleanup),
                                          name='cereja-operation-worker', daemon=False)
                worker.start()
                ex.worker = worker
            except BaseException as error:
                ex.outcome = OperationErrorEvent(self._source, request.generation,
                                                 'Failed', _error_text(error))
            # An already explicitly started worker, never a queued invocation.
            self._pending = ex
            self._condition.notify()
        return request.generation

    def _work(self, ex, operation, cleanup):
        ex.worker_id = threading.get_ident()
        ctx = OperationContext(self._loop, ex)
        value, available, primary = None, False, ''
        state = 'Failed'
        try:
            ctx._send(OperationStartedEvent(self._source, ex.request.generation,
                                           ex.name, ex.capability is not None))
            value = operation(ctx)
            with ex.lock:
                phase = ex.state
            if not ex.started_running or phase not in ('Running', 'Committing', 'CancelRequested'):
                raise RuntimeError('adapter returned without observing Running')
            # Validate before retaining a result. No arbitrary object graph is kept.
            payload_bytes(OperationResultEvent(self._source, ex.request.generation,
                                                'Succeeded', value))
            available = True
            state = 'Succeeded'
        except _CooperativeStop:
            state = 'Cancelled'
            value = None
        except BaseException as error:
            primary = _error_text(error)
            value = None
        with ex.lock:
            ex.settling = True
            phase = ex.state
        cleanup_error = ''
        try:
            if cleanup is not None:
                cleanup()
        except BaseException as error:
            cleanup_error = _error_text(error)
        if cleanup_error:
            # A retained result and two diagnostics must share the SAME 64 KiB
            # event limit. Oversized combined payload reports result omission.
            event = OperationErrorEvent(self._source, ex.request.generation,
                'CleanupFailed', cleanup_error, primary, phase, value, available)
            try:
                payload_bytes(event)
            except ValueError:
                event = OperationErrorEvent(self._source, ex.request.generation,
                    'CleanupFailed', cleanup_error, primary or 'Result omitted: event byte limit',
                    phase)
        elif state == 'Failed':
            event = OperationErrorEvent(self._source, ex.request.generation,
                                        'Failed', primary, phase=phase)
        else:
            event = OperationResultEvent(self._source, ex.request.generation, state, value)
        with ex.lock:
            ex.outcome = event
            # Terminal state becomes observable only after join in the observer.

    def _observe(self):
        token = Cancellation()
        while True:
            with token._watch(self._condition):
                with self._condition:
                    while self._pending is None and not self._closed and not token.cancelled:
                        self._condition.wait()
                    if self._pending is None:
                        self._observer = None
                        return
                    ex = self._pending
                    self._pending = None
            token = ex.request.cancellation
            if ex.worker is not None:
                # NEVER on the UI thread; may wait indefinitely for domain I/O.
                ex.worker.join()
            with ex.lock:
                ex.worker_exited = True
                if ex.outcome is None:
                    ex.outcome = OperationErrorEvent(self._source, ex.request.generation,
                        'Failed', 'Worker exited without a valid outcome')
                event = ex.outcome
                ex.state = event.state
            try:
                accepted = self._loop.wait_post(event, cancellation=ex.request.cancellation)
                with ex.lock:
                    if ex.delivery != 'delivered':
                        ex.delivery = 'queued' if accepted else 'unavailable'
            except BaseException:
                # Never retry uncertain admission: the envelope may already exist.
                with ex.lock:
                    if ex.delivery != 'delivered':
                        ex.delivery = 'publication_failed'
            with ex.lock:
                notify_failure = ex.delivery in ('unavailable', 'publication_failed')
            if notify_failure:
                try:
                    # A zero-payload inbox event retains wake even if a plain
                    # consumer has not entered its condition wait yet. If full,
                    # ready work already wakes it; if closed there is no consumer.
                    self._loop.post(WakeEvent())
                except BaseException:
                    pass  # Receipt still records unavailable/uncertain publication.
            # Release old per-operation references even during an idle wait.
            ex = event = None

    def cancel(self):
        """Request safe cooperation only. Success does not mean Cancelled."""
        self._owned()
        if not self.snapshot.cancellable:
            return False
        ex = self._execution
        with ex.lock:
            if ex.settling or ex.outcome is not None or ex.state not in ('Validating', 'Running'):
                return False
            ex.stop.cancel()
            ex.state = 'CancelRequested'
        return True

    def request_exit(self, choice='return'):
        """Explicit UI choice; return cancels a previous wait-to-exit decision."""
        self._owned()
        if choice not in ('return', 'wait', 'cancel', 'exit'):
            raise ValueError('unsupported exit choice')
        if choice == 'return':
            self._exit_wait = False
            return False
        if not self.active:
            return self._loop.request_shutdown('operation exit')
        if choice == 'exit':
            raise RuntimeError('active operation requires return/wait decision')
        if choice == 'cancel' and not self.cancel():
            return False
        self._exit_wait = True
        return False

    def handle(self, event):
        """Consume own current lifecycle events once; never handles keyboard input."""
        self._owned()
        ex = self._execution
        if (ex is None or type(event) not in (OperationStartedEvent, OperationPhaseEvent,
                ProgressEvent, OperationResultEvent, OperationErrorEvent)
                or event.source != self._source or event.generation != ex.request.generation
                or not self._loop.request_active(ex.request)):
            return False
        if type(event) in (OperationResultEvent, OperationErrorEvent):
            with ex.lock:
                if event is not ex.outcome or ex.delivery == 'delivered':
                    return False
                ex.delivery = 'delivered'
            if self._exit_wait:
                self._loop.request_shutdown('operation completed before exit')
        return True

    def close(self):
        """Detach consumer and wake publication waits; never stop or join domain I/O."""
        self._owned()
        if self._closed:
            return
        with self._condition:
            self._closed = True
            self._condition.notify_all()
        ex = self._execution
        if ex is not None:
            ex.request.cancellation.cancel()
            if not self._loop.stopped:
                self._loop.forget_request(self._source, request=ex.request)

