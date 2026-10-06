"""
How long the controller waits before committing a watched episode.

The player monitor measures watch time itself; the browser extension reports
an episode the moment it starts. Only the second needs a timer.
"""

import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from PySide6.QtCore import QCoreApplication  # noqa: E402

from core.scrobble import ScrobbleOutcome, ScrobbleResult  # noqa: E402
from test_controller_edits import FakeClient, make_controller, wait_for  # noqa: E402


class FakeScrobbler:
    min_watch_time = 60

    def __init__(self):
        self.processed = []

    def process_episode(self, title, episode):
        self.processed.append((title, episode))
        return ScrobbleResult(ScrobbleOutcome.UPDATED, f'Updated {title}')

    def describe_now_watching(self, title, episode):
        return f'Now Watching: {title} - Episode {episode}'


class ScrobbleTimingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.controller = make_controller(FakeClient())
        self.controller.scrobbler = FakeScrobbler()
        self.controller._pending_scrobbles = {}
        self.controller._scrobble_requested.connect(self.controller._begin_pending_scrobble)
        self.controller._episode_watched.connect(self.controller._process_episode)

    def test_player_episode_is_committed_without_a_second_wait(self):
        info = SimpleNamespace(anime_name='Show', episode_number=6)

        self.controller._on_episode_watched(info, 60.5)
        wait_for(lambda: self.controller.scrobbler.processed, timeout_ms=1000)

        self.assertEqual(self.controller.scrobbler.processed, [('Show', 6)])
        self.assertEqual(self.controller._pending_scrobbles, {})

    def test_browser_episode_waits_for_the_minimum_watch_time(self):
        self.controller._handle_remote_scrobble({'title': 'Show', 'episode': 6})
        self.app.processEvents()

        self.assertEqual(self.controller.scrobbler.processed, [])
        timer = self.controller._pending_scrobbles['Show_6']
        self.assertEqual(timer.interval(), 60 * 1000)
        self.assertTrue(timer.isActive())
        timer.stop()


if __name__ == '__main__':
    unittest.main()
