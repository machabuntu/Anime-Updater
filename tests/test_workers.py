import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

from ui import workers


def _app():
    return QCoreApplication.instance() or QCoreApplication([])


def _wait(predicate, timeout_ms=5000):
    loop = QEventLoop()
    poll = QTimer()
    poll.timeout.connect(lambda: predicate() and loop.quit())
    poll.start(5)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    poll.stop()


class RunAsyncTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = _app()

    def test_callbacks_run_on_the_gui_thread(self):
        main = threading.get_ident()
        seen = []

        for i in range(200):
            workers.run_async(
                lambda n=i: n * 2,
                on_success=lambda value: seen.append((value, threading.get_ident())),
            )

        _wait(lambda: len(seen) == 200)
        self.assertEqual(sorted(v for v, _ in seen), [n * 2 for n in range(200)])
        self.assertTrue(all(tid == main for _, tid in seen))

    def test_error_then_done(self):
        events = []

        def boom():
            raise ValueError('nope')

        workers.run_async(
            boom,
            on_success=lambda _v: events.append('success'),
            on_error=lambda msg: events.append(f'error:{msg}'),
            on_done=lambda: events.append('done'),
        )

        _wait(lambda: 'done' in events)
        self.assertEqual(events, ['error:nope', 'done'])

    def test_cancel_suppresses_callbacks(self):
        gate = threading.Event()
        events = []

        worker = workers.run_async(
            gate.wait,
            on_success=lambda _v: events.append('success'),
            on_done=lambda: events.append('done'),
        )
        worker.cancel()
        gate.set()

        workers.run_async(lambda: None, on_done=lambda: events.append('marker'))
        _wait(lambda: 'marker' in events)
        self.assertEqual(events, ['marker'])


if __name__ == '__main__':
    unittest.main()
