"""
Background work helpers.

The tkinter code ran API calls in raw daemon threads and hopped back to the GUI
thread with ``root.after(0, ...)``. Qt does that marshalling itself: a signal
emitted from a worker thread is delivered in the receiver's thread, so callbacks
here are always safe to touch widgets.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional, Set

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal, Slot

logger = logging.getLogger('ui.workers')

# QThreadPool does not keep Python references to a running QRunnable, so a
# worker collected mid-flight would take its signal object with it.
_active: Set['Worker'] = set()


class WorkerSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    done = Signal()


class Worker(QRunnable):
    """Runs a callable on the shared thread pool and reports back via signals."""

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.signals = WorkerSignals()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._cancelled = False

    def cancel(self) -> None:
        """Ask the worker to drop its result once it finishes.

        The callable itself is not interrupted; this only suppresses the
        callbacks, which is what callers need when a view is torn down.
        """
        self._cancelled = True

    @Slot()
    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:
            logger.exception('Background task %s failed', getattr(self._fn, '__name__', self._fn))
            if not self._cancelled:
                self.signals.failed.emit(str(exc))
        else:
            if not self._cancelled:
                self.signals.succeeded.emit(result)
        finally:
            if not self._cancelled:
                self.signals.done.emit()
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
    worker = Worker(fn, *args, **kwargs)
    if on_success is not None:
        worker.signals.succeeded.connect(on_success)
    if on_error is not None:
        worker.signals.failed.connect(on_error)
    if on_done is not None:
        worker.signals.done.connect(on_done)

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
    for worker in list(_active):
        worker.cancel()
    QThreadPool.globalInstance().waitForDone(timeout_ms)
