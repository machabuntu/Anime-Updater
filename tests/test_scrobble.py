"""
Tests for the extracted scrobble pipeline.

These pin down the rules that used to be duplicated in two places in the
tkinter main window, so the Qt rewrite cannot quietly change them.

Run with:  python -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from core.library import LibraryService  # noqa: E402
from core.scrobble import ScrobbleOutcome, ScrobbleService  # noqa: E402


class FakeConfig:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


class FakeClient:
    STATUSES = {
        'watching': 'Watching',
        'planned': 'Plan to Watch',
        'completed': 'Completed',
        'on_hold': 'On Hold',
        'dropped': 'Dropped',
        'rewatching': 'Rewatching',
    }
    MANGA_STATUSES = {
        'watching': 'Reading',
        'planned': 'Plan to Read',
        'completed': 'Completed',
        'on_hold': 'On Hold',
        'dropped': 'Dropped',
    }
    SERVICE_NAME = 'Fake'

    def __init__(self, succeed=True):
        self.succeed = succeed
        self.calls = []

    def update_anime_progress(self, rate_id, episodes, status=None):
        self.calls.append((rate_id, episodes, status))
        return self.succeed


class FakeCacheManager:
    def __init__(self):
        self.saved = []

    def save_anime_list(self, user_id, data):
        self.saved.append((user_id, data))

    def load_anime_list(self, user_id):
        return None

    def save_manga_list(self, user_id, data):
        pass

    def load_manga_list(self, user_id):
        return None


class FakeMatcher:
    """Matches on an exact, case-insensitive title comparison."""

    def __init__(self):
        self.on_cache_updated_callback = None

    def find_best_match(self, detected_name, anime_list, episode_number=None):
        for entry in anime_list:
            name = entry.get('anime', {}).get('name', '')
            if name.lower() == detected_name.lower():
                return entry, 1.0
        return None

    def initialize_detailed_cache(self, user_id, data):
        pass

    def start_periodic_updater(self, user_id):
        pass

    def stop_periodic_updater(self):
        pass

    def set_cache_updated_callback(self, callback):
        self.on_cache_updated_callback = callback


class FakeTelegram:
    def __init__(self):
        self.progress = []
        self.completion = []

    def send_progress_update(self, *args):
        self.progress.append(args)

    def send_completion_update(self, *args):
        self.completion.append(args)


def make_entry(rate_id, name, status, episodes, total, score=0):
    return {
        'id': rate_id,
        'status': status,
        'episodes': episodes,
        'score': score,
        'anime': {'name': name, 'episodes': total, 'url': f'/animes/{rate_id}'},
    }


class ScrobbleServiceTest(unittest.TestCase):
    def setUp(self):
        self.config = FakeConfig({'monitoring.min_watch_time': 60})
        self.client = FakeClient()
        self.library = LibraryService(
            self.config, self.client, FakeCacheManager(), FakeMatcher()
        )
        self.library.current_user = {'id': 7, 'nickname': 'tester'}
        self.telegram = FakeTelegram()
        self.service = ScrobbleService(self.config, self.library, self.telegram)

    def _load(self, data):
        self.library.anime_list_data = data

    def test_next_episode_is_committed(self):
        entry = make_entry(1, 'Frieren', 'watching', 4, 28)
        self._load({'watching': [entry]})

        result = self.service.process_episode('Frieren', 5)

        self.assertIs(result.outcome, ScrobbleOutcome.UPDATED)
        self.assertEqual(self.client.calls, [(1, 5, None)])
        self.assertEqual(entry['episodes'], 5)
        self.assertIn('episode 5', result.message)

    def test_skipping_ahead_is_rejected(self):
        entry = make_entry(1, 'Frieren', 'watching', 4, 28)
        self._load({'watching': [entry]})

        result = self.service.process_episode('Frieren', 9)

        self.assertIs(result.outcome, ScrobbleOutcome.NOT_NEXT_EPISODE)
        self.assertEqual(self.client.calls, [])
        self.assertEqual(entry['episodes'], 4)

    def test_rewatching_the_same_episode_is_ignored(self):
        entry = make_entry(1, 'Frieren', 'watching', 4, 28)
        self._load({'watching': [entry]})

        first = self.service.process_episode('Frieren', 5)
        second = self.service.process_episode('Frieren', 5)

        self.assertIs(first.outcome, ScrobbleOutcome.UPDATED)
        # The second attempt is now "not next" because progress already moved,
        # which is the same protection the original code relied on.
        self.assertIsNot(second.outcome, ScrobbleOutcome.UPDATED)
        self.assertEqual(len(self.client.calls), 1)

    def test_committed_episode_is_not_repeated_after_manual_rollback(self):
        entry = make_entry(1, 'Frieren', 'watching', 4, 28)
        self._load({'watching': [entry]})

        self.service.process_episode('Frieren', 5)
        entry['episodes'] = 4  # user rolled progress back by hand

        result = self.service.process_episode('Frieren', 5)

        self.assertIs(result.outcome, ScrobbleOutcome.ALREADY_UPDATED)
        self.assertEqual(len(self.client.calls), 1)

    def test_session_reset_allows_recommit(self):
        entry = make_entry(1, 'Frieren', 'watching', 4, 28)
        self._load({'watching': [entry]})

        self.service.process_episode('Frieren', 5)
        entry['episodes'] = 4
        self.service.reset_session()

        result = self.service.process_episode('Frieren', 5)

        self.assertIs(result.outcome, ScrobbleOutcome.UPDATED)
        self.assertEqual(len(self.client.calls), 2)

    def test_planned_title_moves_to_watching(self):
        entry = make_entry(1, 'Mushishi', 'planned', 0, 26)
        self._load({'planned': [entry]})

        result = self.service.process_episode('Mushishi', 1)

        self.assertIs(result.outcome, ScrobbleOutcome.UPDATED)
        self.assertEqual(self.client.calls, [(1, 1, 'watching')])
        self.assertIn('Moved to Watching', result.message)
        # The entry must also change bucket, not just its status field.
        self.assertEqual(self.library.anime_list_data['planned'], [])
        self.assertEqual(self.library.anime_list_data['watching'], [entry])

    def test_final_episode_completes_when_scored(self):
        entry = make_entry(1, 'Look Back', 'watching', 0, 1, score=8)
        self._load({'watching': [entry]})

        result = self.service.process_episode('Look Back', 1)

        self.assertEqual(self.client.calls, [(1, 1, 'completed')])
        self.assertIn('Completed', result.message)
        self.assertEqual(self.library.anime_list_data['completed'], [entry])
        self.assertEqual(len(self.telegram.completion), 1)
        self.assertEqual(len(self.telegram.progress), 0)

    def test_final_episode_keeps_status_when_unscored(self):
        entry = make_entry(1, 'Look Back', 'watching', 0, 1, score=0)
        self._load({'watching': [entry]})

        self.service.process_episode('Look Back', 1)

        self.assertEqual(self.client.calls, [(1, 1, None)])
        self.assertEqual(entry['status'], 'watching')
        self.assertEqual(len(self.telegram.progress), 1)

    def test_unknown_title_reports_no_match(self):
        self._load({'watching': [make_entry(1, 'Frieren', 'watching', 4, 28)]})

        result = self.service.process_episode('Some Other Show', 1)

        self.assertIs(result.outcome, ScrobbleOutcome.NO_MATCH)
        self.assertEqual(self.client.calls, [])

    def test_completed_titles_are_not_matched(self):
        # A finished season 1 must not absorb episodes of an ongoing season 2.
        self._load({'completed': [make_entry(1, 'Frieren', 'completed', 28, 28)]})

        result = self.service.process_episode('Frieren', 1)

        self.assertIs(result.outcome, ScrobbleOutcome.NO_MATCH)

    def test_api_failure_is_reported_and_not_cached(self):
        self.client.succeed = False
        entry = make_entry(1, 'Frieren', 'watching', 4, 28)
        self._load({'watching': [entry]})

        result = self.service.process_episode('Frieren', 5)

        self.assertIs(result.outcome, ScrobbleOutcome.UPDATE_FAILED)
        self.assertEqual(entry['episodes'], 4)
        self.assertEqual(len(self.telegram.progress), 0)

    def test_telegram_failure_does_not_fail_the_scrobble(self):
        def boom(*_args):
            raise RuntimeError('telegram is down')

        self.telegram.send_progress_update = boom
        entry = make_entry(1, 'Frieren', 'watching', 4, 28)
        self._load({'watching': [entry]})

        result = self.service.process_episode('Frieren', 5)

        self.assertIs(result.outcome, ScrobbleOutcome.UPDATED)
        self.assertEqual(entry['episodes'], 5)

    def test_now_watching_text_reflects_list_membership(self):
        self._load({'watching': [make_entry(1, 'Frieren', 'watching', 4, 28)]})

        self.assertEqual(
            self.service.describe_now_watching('Frieren', 5),
            'Now Watching: Frieren - Episode 5',
        )
        self.assertEqual(
            self.service.describe_now_watching('Unknown Show', 1),
            'Anime not in active list: Unknown Show - Episode 1',
        )


class LibraryServiceTest(unittest.TestCase):
    def setUp(self):
        self.config = FakeConfig()
        self.client = FakeClient()
        self.library = LibraryService(
            self.config, self.client, FakeCacheManager(), FakeMatcher()
        )
        self.library.current_user = {'id': 7, 'nickname': 'tester'}

    def test_active_entries_exclude_completed_and_dropped(self):
        self.library.anime_list_data = {
            'watching': [make_entry(1, 'A', 'watching', 1, 12)],
            'planned': [make_entry(2, 'B', 'planned', 0, 12)],
            'on_hold': [make_entry(3, 'C', 'on_hold', 3, 12)],
            'rewatching': [make_entry(4, 'D', 'rewatching', 2, 12)],
            'completed': [make_entry(5, 'E', 'completed', 12, 12)],
            'dropped': [make_entry(6, 'F', 'dropped', 4, 12)],
        }

        names = {e['anime']['name'] for e in self.library.active_anime_entries()}

        self.assertEqual(names, {'A', 'B', 'C', 'D'})

    def test_load_anime_list_from_api_reports_progress(self):
        self.client.get_user_anime_list = lambda uid, status: (
            [make_entry(1, 'A', status, 1, 12)] if status == 'watching' else []
        )
        messages = []

        result = self.library.load_anime_list(force_refresh=True, progress=messages.append)

        self.assertTrue(result.loaded)
        self.assertFalse(result.from_cache)
        self.assertEqual(result.total, 1)
        self.assertIn('Refreshing anime list...', messages)

    def test_load_without_user_returns_not_loaded(self):
        self.library.current_user = None

        result = self.library.load_anime_list(force_refresh=True)

        self.assertFalse(result.loaded)
        self.assertEqual(result.total, 0)

    def test_find_anime_entry_by_rate_id(self):
        entry = make_entry(42, 'A', 'watching', 1, 12)
        self.library.anime_list_data = {'watching': [entry]}

        self.assertIs(self.library.find_anime_entry(42), entry)
        self.assertIsNone(self.library.find_anime_entry(99))


if __name__ == '__main__':
    unittest.main()
