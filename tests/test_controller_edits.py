"""
Manual list edits through the controller: API call, local list, notifications.

The controller is built without its constructor, which would start the player
monitor and the local API server; only what the edit path touches is set up.
"""

import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from PySide6.QtCore import QCoreApplication, QEventLoop, QObject, QTimer  # noqa: E402

from core.library import LibraryService  # noqa: E402
from ui.controller import AppController  # noqa: E402
from test_scrobble import FakeCacheManager, FakeConfig, FakeMatcher  # noqa: E402


class FakeClient:
    SERVICE_NAME = 'Fake'
    STATUSES = {
        'planned': 'Plan to Watch', 'watching': 'Watching', 'completed': 'Completed',
        'dropped': 'Dropped', 'rewatching': 'Rewatching', 'on_hold': 'On Hold',
    }
    MANGA_STATUSES = {
        'planned': 'Plan to Read', 'watching': 'Reading', 'completed': 'Completed',
        'dropped': 'Dropped', 'on_hold': 'On Hold',
    }

    def __init__(self, succeed=True):
        self.succeed = succeed
        self.anime_calls = []
        self.manga_calls = []

    def update_anime_progress(self, rate_id, episodes=None, **fields):
        self.anime_calls.append((rate_id, episodes, fields))
        return self.succeed

    def update_manga_progress(self, rate_id, chapters=None, **fields):
        self.manga_calls.append((rate_id, chapters, fields))
        return self.succeed


class FakeTelegram:
    def __init__(self):
        self.completion = []
        self.status_change = []

    def send_completion_update(self, *args):
        self.completion.append(args)

    def send_status_change_update(self, *args):
        self.status_change.append(args)


def anime(rate_id, status, episodes, total=12, score=0, rewatches=0):
    return {
        'id': rate_id, 'status': status, 'episodes': episodes, 'score': score,
        'rewatches': rewatches, 'text': '',
        'anime': {'name': f'Show {rate_id}', 'episodes': total, 'url': f'/animes/{rate_id}'},
    }


def manga(rate_id, status, chapters=0):
    return {'id': rate_id, 'status': status, 'chapters': chapters, 'volumes': 0, 'score': 0,
            'manga': {'name': f'Book {rate_id}', 'chapters': 50, 'volumes': 5}}


def make_controller(client):
    controller = AppController.__new__(AppController)
    QObject.__init__(controller)
    controller.config = FakeConfig()
    controller.logger = __import__('logging').getLogger('test')
    controller.client = client
    controller.library = LibraryService(controller.config, client, FakeCacheManager(), FakeMatcher())
    controller.library.current_user = {'id': 7, 'nickname': 'tester'}
    controller.telegram_notifier = FakeTelegram()
    return controller


def wait_for(predicate, timeout_ms=3000):
    loop = QEventLoop()
    poll = QTimer()
    poll.timeout.connect(lambda: predicate() and loop.quit())
    poll.start(5)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    poll.stop()


class ControllerEditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.client = FakeClient()
        self.controller = make_controller(self.client)
        self.events = []
        self.controller.anime_list_changed.connect(lambda: self.events.append('list'))
        self.controller.anime_entry_changed.connect(lambda e: self.events.append(('entry', e)))
        self.controller.manga_list_changed.connect(lambda: self.events.append('manga'))
        self.controller.status_message.connect(lambda m, _a: self.events.append(('msg', m)))

    def _run(self, call):
        call()
        wait_for(lambda: any(e == 'list' or e == 'manga' or (isinstance(e, tuple) and e[0] == 'entry')
                             for e in self.events))

    def _buckets(self):
        return {status: [e['id'] for e in entries]
                for status, entries in self.controller.library.anime_list_data.items()}

    def test_score_on_finished_title_completes_and_notifies(self):
        self.controller.library.anime_list_data = {'watching': [anime(1, 'watching', 12)]}
        live = self.controller.library.find_anime_entry(1)

        self._run(lambda: self.controller.update_anime(live, score=8))

        _rate, episodes, fields = self.client.anime_calls[0]
        self.assertEqual(fields['status'], 'completed')
        self.assertEqual(fields['score'], 8)
        self.assertEqual(self._buckets(), {'watching': [], 'completed': [1]})
        self.assertEqual(len(self.controller.telegram_notifier.completion), 1)
        name, score = self.controller.telegram_notifier.completion[0][:2]
        self.assertEqual((name, score), ('Show 1', 8))

    def test_manual_completed_moves_live_entry_even_from_stale_copy(self):
        self.controller.library.anime_list_data = {'watching': [anime(1, 'watching', 12, score=7)]}
        stale = copy.deepcopy(self.controller.library.find_anime_entry(1))
        stale['score'] = 3  # the copy has drifted from the list since a reload

        self._run(lambda: self.controller.update_anime(stale, status='completed'))

        self.assertEqual(self._buckets(), {'watching': [], 'completed': [1]})
        live = self.controller.library.find_anime_entry(1)
        self.assertEqual(live['status'], 'completed')
        self.assertEqual(live['score'], 7)
        self.assertEqual(len(self.controller.telegram_notifier.completion), 1)

    def test_dropping_sends_status_change(self):
        self.controller.library.anime_list_data = {'watching': [anime(1, 'watching', 3)]}

        self._run(lambda: self.controller.update_anime(
            self.controller.library.find_anime_entry(1), status='dropped'))

        self.assertEqual(self._buckets(), {'watching': [], 'dropped': [1]})
        args = self.controller.telegram_notifier.status_change[0]
        self.assertEqual(args[1:3], ('Watching', 'dropped'))

    def test_finishing_a_rewatch_counts_it(self):
        self.controller.library.anime_list_data = {
            'rewatching': [anime(1, 'rewatching', 11, score=9, rewatches=1)]
        }

        self._run(lambda: self.controller.update_anime(
            self.controller.library.find_anime_entry(1), episodes=12))

        self.assertEqual(self.client.anime_calls[0][2]['rewatches'], 2)
        live = self.controller.library.find_anime_entry(1)
        self.assertEqual((live['status'], live['rewatches']), ('completed', 2))
        _name, _score, _user, is_rewatch, count = self.controller.telegram_notifier.completion[0][:5]
        self.assertEqual((is_rewatch, count), (True, 2))

    def test_failed_update_changes_nothing_and_resets_the_panel(self):
        self.client.succeed = False
        self.controller.library.anime_list_data = {'watching': [anime(1, 'watching', 12)]}
        live = self.controller.library.find_anime_entry(1)

        self._run(lambda: self.controller.update_anime(live, score=8))

        self.assertEqual(live['score'], 0)
        self.assertEqual(live['status'], 'watching')
        self.assertIn(('entry', live), self.events)
        self.assertEqual(self.controller.telegram_notifier.completion, [])

    def test_manga_status_change_moves_between_tabs(self):
        self.controller.library.manga_list_data = {'watching': [manga(5, 'watching', 10)]}
        stale = copy.deepcopy(self.controller.library.manga_list_data['watching'][0])

        self._run(lambda: self.controller.update_manga(stale, status='completed'))

        data = self.controller.library.manga_list_data
        self.assertEqual([e['id'] for e in data['watching']], [])
        self.assertEqual([e['id'] for e in data['completed']], [5])


if __name__ == '__main__':
    unittest.main()
