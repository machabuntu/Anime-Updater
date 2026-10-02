"""
Rules for manual list edits.

Changing one field of an entry often implies another: rating a title whose
last episode is already watched completes it, watching the first episode of a
planned title starts it. The tkinter version spread these rules over three
handlers (progress, score, status); here they are one pure function, so every
place that edits an entry (the toolbar panel, the context menu, the edit
dialog) behaves the same.

Nothing in this module talks to the API or the interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

NOTIFY_COMPLETED = 'completed'
NOTIFY_STATUS_CHANGE = 'status_change'

# Manual changes into these statuses are announced in Telegram. Which of them
# are actually sent is decided by the notifier's own settings.
_ANNOUNCED_STATUSES = ('dropped', 'rewatching')


@dataclass
class AnimeEdit:
    """What to send to the API for one manual anime edit, and what it means."""

    episodes: Optional[int] = None
    status: Optional[str] = None
    score: Optional[int] = None
    rewatches: Optional[int] = None

    previous_status: str = ''
    auto_status: bool = False
    notification: Optional[str] = None
    is_rewatch: bool = False

    @property
    def is_empty(self) -> bool:
        return (self.episodes is None and self.status is None
                and self.score is None and self.rewatches is None)

    def updates(self) -> Dict[str, Any]:
        """The fields that change, keyed as they are stored in the list."""
        values = {
            'episodes': self.episodes,
            'status': self.status,
            'score': self.score,
            'rewatches': self.rewatches,
        }
        return {key: value for key, value in values.items() if value is not None}


def plan_anime_edit(entry: Dict[str, Any], episodes: Optional[int] = None,
                    status: Optional[str] = None, score: Optional[int] = None,
                    rewatches: Optional[int] = None) -> AnimeEdit:
    """Turn a requested change into the full set of changes it implies.

    ``None`` means "leave as is". Values equal to the stored ones are dropped,
    so a dialog may pass every field it shows.

    Explicit status changes:
      * Rewatching restarts progress at episode 0.
      * Completed fills progress up to the episode count when it is known.
      * Completing a rewatch counts it, unless the caller set the count.

    Without an explicit status, the episode count or score can change it:
      * Finishing a rewatch completes it and counts it, score or not.
      * Reaching the last episode with a score, or scoring a title whose last
        episode is watched, completes it. A finished but unrated title is left
        alone so the user can still rate it.
      * Watching an episode of a planned title moves it to Watching.
    """
    anime = entry.get('anime') or {}
    current_status = entry.get('status', '') or ''
    current_episodes = entry.get('episodes', 0) or 0
    current_score = entry.get('score', 0) or 0
    current_rewatches = entry.get('rewatches', 0) or 0
    total_episodes = anime.get('episodes', 0) or 0

    if episodes == current_episodes:
        episodes = None
    if score == current_score:
        score = None
    if rewatches == current_rewatches:
        rewatches = None
    if status == current_status or status == '':
        status = None

    edit = AnimeEdit(episodes=episodes, status=status, score=score,
                     rewatches=rewatches, previous_status=current_status)

    if status is not None:
        if status == 'rewatching' and episodes is None and current_episodes:
            edit.episodes = 0
        elif (status == 'completed' and episodes is None
              and total_episodes and current_episodes < total_episodes):
            edit.episodes = total_episodes
    elif episodes is not None or score is not None:
        new_episodes = current_episodes if episodes is None else episodes
        new_score = current_score if score is None else score
        finished = total_episodes > 0 and new_episodes >= total_episodes

        if current_status == 'rewatching' and finished and episodes is not None:
            edit.status = 'completed'
        elif current_status != 'completed' and finished and new_score > 0:
            edit.status = 'completed'
        elif current_status == 'planned' and episodes is not None and new_episodes > 0:
            edit.status = 'watching'
        edit.auto_status = edit.status is not None

    if edit.status == 'completed' and current_status == 'rewatching':
        edit.is_rewatch = True
        if edit.rewatches is None:
            edit.rewatches = current_rewatches + 1

    if edit.status == 'completed':
        edit.notification = NOTIFY_COMPLETED
    elif edit.status in _ANNOUNCED_STATUSES:
        edit.notification = NOTIFY_STATUS_CHANGE

    return edit
