import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from core.list_edits import NOTIFY_COMPLETED, NOTIFY_STATUS_CHANGE, plan_anime_edit  # noqa: E402


def entry(status='watching', episodes=0, total=12, score=0, rewatches=0):
    return {
        'id': 1, 'status': status, 'episodes': episodes, 'score': score,
        'rewatches': rewatches, 'anime': {'name': 'Show', 'episodes': total},
    }


class ScoreTest(unittest.TestCase):
    def test_scoring_a_finished_title_completes_it(self):
        edit = plan_anime_edit(entry(episodes=12), score=8)
        self.assertEqual(edit.score, 8)
        self.assertEqual(edit.status, 'completed')
        self.assertTrue(edit.auto_status)
        self.assertEqual(edit.notification, NOTIFY_COMPLETED)

    def test_scoring_an_unfinished_title_only_scores(self):
        edit = plan_anime_edit(entry(episodes=5), score=8)
        self.assertIsNone(edit.status)
        self.assertIsNone(edit.notification)

    def test_rescoring_a_completed_title_is_not_a_new_completion(self):
        edit = plan_anime_edit(entry('completed', episodes=12, score=7), score=9)
        self.assertIsNone(edit.status)
        self.assertIsNone(edit.notification)

    def test_removing_a_score_does_not_complete(self):
        edit = plan_anime_edit(entry(episodes=12, score=7), score=0)
        self.assertEqual(edit.score, 0)
        self.assertIsNone(edit.status)

    def test_unknown_episode_count_never_auto_completes(self):
        edit = plan_anime_edit(entry(episodes=30, total=0), score=8)
        self.assertIsNone(edit.status)

    def test_scoring_a_finished_dropped_title_completes_it(self):
        edit = plan_anime_edit(entry('on_hold', episodes=12), score=6)
        self.assertEqual(edit.status, 'completed')

    def test_scoring_a_finished_rewatch_counts_it(self):
        edit = plan_anime_edit(entry('rewatching', episodes=12, rewatches=1), score=9)
        self.assertEqual(edit.status, 'completed')
        self.assertTrue(edit.is_rewatch)
        self.assertEqual(edit.rewatches, 2)


class EpisodesTest(unittest.TestCase):
    def test_last_episode_completes_a_scored_title(self):
        edit = plan_anime_edit(entry(episodes=11, score=8), episodes=12)
        self.assertEqual(edit.status, 'completed')
        self.assertEqual(edit.notification, NOTIFY_COMPLETED)

    def test_last_episode_keeps_an_unscored_title_open(self):
        edit = plan_anime_edit(entry(episodes=11), episodes=12)
        self.assertIsNone(edit.status)

    def test_first_episode_starts_a_planned_title(self):
        edit = plan_anime_edit(entry('planned'), episodes=1)
        self.assertEqual(edit.status, 'watching')
        self.assertIsNone(edit.notification)

    def test_planned_title_watched_in_one_go_with_score_completes(self):
        edit = plan_anime_edit(entry('planned', score=8), episodes=12)
        self.assertEqual(edit.status, 'completed')

    def test_finishing_a_rewatch_completes_and_counts_it_without_score(self):
        edit = plan_anime_edit(entry('rewatching', episodes=11, rewatches=2), episodes=12)
        self.assertEqual(edit.status, 'completed')
        self.assertTrue(edit.is_rewatch)
        self.assertEqual(edit.rewatches, 3)

    def test_lowering_progress_of_a_completed_title_keeps_status(self):
        edit = plan_anime_edit(entry('completed', episodes=12, score=8), episodes=10)
        self.assertEqual(edit.episodes, 10)
        self.assertIsNone(edit.status)

    def test_unchanged_values_make_an_empty_edit(self):
        edit = plan_anime_edit(entry(episodes=3, score=5), episodes=3, score=5)
        self.assertTrue(edit.is_empty)


class ExplicitStatusTest(unittest.TestCase):
    def test_completing_fills_progress(self):
        edit = plan_anime_edit(entry(episodes=5, score=7), status='completed')
        self.assertEqual(edit.status, 'completed')
        self.assertEqual(edit.episodes, 12)
        self.assertFalse(edit.auto_status)
        self.assertEqual(edit.notification, NOTIFY_COMPLETED)

    def test_completing_keeps_progress_the_user_typed(self):
        edit = plan_anime_edit(entry(episodes=5), status='completed', episodes=8)
        self.assertEqual(edit.episodes, 8)

    def test_completing_with_unknown_total_leaves_progress(self):
        edit = plan_anime_edit(entry(episodes=5, total=0), status='completed')
        self.assertIsNone(edit.episodes)

    def test_completing_a_rewatch_counts_it(self):
        edit = plan_anime_edit(entry('rewatching', episodes=12, rewatches=0), status='completed')
        self.assertTrue(edit.is_rewatch)
        self.assertEqual(edit.rewatches, 1)

    def test_completing_a_rewatch_respects_a_typed_count(self):
        edit = plan_anime_edit(entry('rewatching', episodes=12, rewatches=1),
                               status='completed', rewatches=5)
        self.assertEqual(edit.rewatches, 5)

    def test_rewatching_restarts_progress(self):
        edit = plan_anime_edit(entry('completed', episodes=12, score=8), status='rewatching')
        self.assertEqual(edit.episodes, 0)
        self.assertEqual(edit.notification, NOTIFY_STATUS_CHANGE)

    def test_dropping_is_announced(self):
        edit = plan_anime_edit(entry(episodes=3), status='dropped')
        self.assertEqual(edit.notification, NOTIFY_STATUS_CHANGE)
        self.assertIsNone(edit.episodes)

    def test_on_hold_is_not_announced(self):
        edit = plan_anime_edit(entry(episodes=3), status='on_hold')
        self.assertIsNone(edit.notification)

    def test_explicit_status_wins_over_auto_completion(self):
        edit = plan_anime_edit(entry(episodes=12), status='on_hold', score=8)
        self.assertEqual(edit.status, 'on_hold')

    def test_same_status_is_dropped(self):
        edit = plan_anime_edit(entry('watching', episodes=3), status='watching')
        self.assertTrue(edit.is_empty)


if __name__ == '__main__':
    unittest.main()
