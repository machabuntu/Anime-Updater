"""
Background work helpers.

The tkinter code ran API calls in raw daemon threads and hopped back to the GUI
thread with ``root.after(0, ...)``. Qt does that marshalling itself: a signal
emitted from a worker thread is delivered in the receiver's thread, so callbacks
here are always safe to touch widgets.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Optional, Set

from PySide6.QtCore import QCoreApplication, QObject, QRunnable, QThreadPool, QTimer, Signal, Slot

logger = logging.getLogger('ui.workers')

# QThreadPool does not keep Python references to a running QRunnable, so a
# worker collected mid-flight would vanish before reporting back.
_active: Set['Worker'] = set()
_active_lock = threading.Lock()


class _Dispatcher(QObject):
    """Runs callables on the GUI thread on behalf of pool threads.

    Results travel through one long-lived object. A signal object per task
    would be released by the pool thread while the GUI thread still has its
    queued signals pending, and delivering to it then crashes the process.
    """

    call = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.call.connect(self._run)

    @Slot(object)
    def _run(self, fn: Callable[[], None]) -> None:
        try:
            fn()
        except Exception:
            logger.exception('Background task callback failed')


_dispatcher: Optional[_Dispatcher] = None


def _get_dispatcher() -> _Dispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = _Dispatcher()
        app = QCoreApplication.instance()
        if app is not None:
            _dispatcher.moveToThread(app.thread())
    return _dispatcher


class _Callbacks:
    """Outcome handlers of one task; outlives the QRunnable that ran it."""

    def __init__(self, on_success, on_error, on_done) -> None:
        self.on_success = on_success
        self.on_error = on_error
        self.on_done = on_done
        self.cancelled = False

    def deliver(self, ok: bool, payload: Any) -> None:
        # Runs on the GUI thread, so a cancel() issued after the task
        # finished but before delivery is still honoured.
        if self.cancelled:
            return
        try:
            if ok and self.on_success is not None:
                self.on_success(payload)
            elif not ok and self.on_error is not None:
                self.on_error(payload)
        finally:
            if self.on_done is not None and not self.cancelled:
                self.on_done()


class Worker(QRunnable):
    """Runs a callable on the shared thread pool and reports back on the GUI thread."""

    def __init__(self, fn: Callable[..., Any], *args: Any,
                 on_success: Optional[Callable[[Any], None]] = None,
                 on_error: Optional[Callable[[str], None]] = None,
                 on_done: Optional[Callable[[], None]] = None,
                 **kwargs: Any) -> None:
        super().__init__()
        self._dispatcher = _get_dispatcher()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._callbacks = _Callbacks(on_success, on_error, on_done)

    def cancel(self) -> None:
        """Ask the worker to drop its result once it finishes.

        The callable itself is not interrupted; this only suppresses the
        callbacks, which is what callers need when a view is torn down.
        """
        self._callbacks.cancelled = True

    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:
            logger.exception('Background task %s failed', getattr(self._fn, '__name__', self._fn))
            outcome = (False, str(exc))
        else:
            outcome = (True, result)

        callbacks = self._callbacks
        self._dispatcher.call.emit(lambda: callbacks.deliver(*outcome))
        with _active_lock:
            _active.discard(self)


def run_async(
    fn: Callable[..., Any],
    *args: Any,
    on_success: Optional[Callable[[Any], None]] = None,
    on_error: Optional[Callable[[str], None]] = None,
    on_done: Optional[Callable[[], None]] = None,
    **kwargs: Any,
) -> Worker:
    """Execute ``fn`` off the GUI thread and route the outcome to callbacks."""
    worker = Worker(fn, *args, on_success=on_success, on_error=on_error,
                    on_done=on_done, **kwargs)
    with _active_lock:
        _active.add(worker)
    QThreadPool.globalInstance().start(worker)
    return worker


def open_url(url: str, on_failure: Optional[Callable[[], None]] = None) -> None:
    """Open ``url`` in the browser without freezing the window.

    ``on_failure`` runs on the GUI thread if no program managed to open it.
    """
    from utils.external import open_url as _open

    def report(opened: bool) -> None:
        if not opened and on_failure is not None:
            on_failure()

    run_async(
        _open, url,
        on_success=report,
        on_error=lambda _msg: on_failure() if on_failure is not None else None,
    )


class Debouncer(QObject):
    """Collapses a burst of calls into a single delayed invocation.

    Used for filter text fields, where the tkinter version rebuilt the whole
    tree on every key release.
    """

    def __init__(self, callback: Callable[[], None], delay_ms: int = 200,
                 parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(delay_ms)
        self._timer.timeout.connect(callback)

    def trigger(self) -> None:
        self._timer.start()

    def cancel(self) -> None:
        self._timer.stop()

    def flush(self) -> None:
        """Fire immediately if a call is pending."""
        if self._timer.isActive():
            self._timer.stop()
            self._timer.timeout.emit()


def shutdown(timeout_ms: int = 3000) -> None:
    """Wait for in-flight workers so the process can exit cleanly."""
    with _active_lock:
        pending = list(_active)
    for worker in pending:
        worker.cancel()
    QThreadPool.globalInstance().waitForDone(timeout_ms)
