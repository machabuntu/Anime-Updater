"""
Scrobble service.

The tkinter version carried two near-identical copies of this pipeline: one for
episodes reported by the browser extension (``_handle_scrobble``) and one for
episodes detected in a local player (``_on_episode_watched``). Both did the same
thing: match the title against the active list, require the episode to be
exactly one ahead of the stored progress, push the update, then refresh the
cache and send notifications. That logic lives here once.

Timing is intentionally left out. The browser path has to wait for the minimum
watch time before committing, and how you wait belongs to the event loop of
whichever toolkit is on top.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from core.library import LibraryService
from utils.logger import get_logger


class ScrobbleOutcome(Enum):
    """Why a scrobble attempt ended the way it did."""

    UPDATED = 'updated'
    NO_MATCH = 'no_match'
    NOT_NEXT_EPISODE = 'not_next_episode'
    ALREADY_UPDATED = 'already_updated'
    UPDATE_FAILED = 'update_failed'
    ERROR = 'error'


@dataclass
class ScrobbleResult:
    outcome: ScrobbleOutcome
    message: str
    entry: Optional[Dict[str, Any]] = None

    @property
    def succeeded(self) -> bool:
        return self.outcome is ScrobbleOutcome.UPDATED


class ScrobbleService:
    """Turns "title X, episode N was watched" into a list update."""

    def __init__(self, config, library: LibraryService, telegram_notifier) -> None:
        self.config = config
        self.library = library
        self.telegram_notifier = telegram_notifier
        self.logger = get_logger('scrobble')

        # Guards against the same episode being committed twice within one
        # session, e.g. when a player is restarted on the same file.
        self._committed: set = set()

    # ------------------------------------------------------------- lifecycle --

    def reset_session(self) -> None:
        """Forget which episodes were already committed.

        Called when monitoring starts and after a full list refresh, since
        stored progress may have changed elsewhere.
        """
        self._committed.clear()

    @property
    def min_watch_time(self) -> int:
        """Seconds a title must be watched before the update is committed."""
        return self.config.get('monitoring.min_watch_time', 60)

    # ---------------------------------------------------------------- display --

    def describe_now_watching(self, title: str, episode: int) -> str:
        """Build the "Now Watching" line shown in the status bar."""
        if self.library.is_anime_in_active_list(title):
            return f'Now Watching: {title} - Episode {episode}'
        return f'Anime not in active list: {title} - Episode {episode}'

    # --------------------------------------------------------------- pipeline --

    def process_episode(self, title: str, episode: int) -> ScrobbleResult:
        """Commit one watched episode. Safe to call from a worker thread."""
        try:
            return self._process(title, episode)
        except Exception as exc:
            self.logger.exception('Episode processing error for %s ep %s', title, episode)
            return ScrobbleResult(ScrobbleOutcome.ERROR, f'Error processing episode: {exc}')

    def _process(self, title: str, episode: int) -> ScrobbleResult:
        match = self.library.match_active_anime(title, episode)
        if not match:
            self.logger.warning('Anime matching failed for %s', title)
            return ScrobbleResult(ScrobbleOutcome.NO_MATCH, f'No match found for {title}')

        entry, similarity = match
        anime = entry.get('anime', {})
        anime_name = anime.get('name', title)
        rate_id = entry['id']
        self.logger.info(
            'Anime match found: %s (ID: %s, similarity: %.2f)', anime_name, rate_id, similarity
        )

        current_episodes = entry.get('episodes', 0)
        self.logger.info(
            'Episode progress check: current=%s target=%s', current_episodes, episode
        )

        commit_key = f'{rate_id}_{episode}'
        if commit_key in self._committed:
            self.logger.info('Episode %s already updated for %s, skipping', episode, anime_name)
            return ScrobbleResult(
                ScrobbleOutcome.ALREADY_UPDATED,
                f'Episode {episode} already updated for {anime_name}',
                entry,
            )

        if episode != current_episodes + 1:
            message = (
                f'Episode {episode} is not next for {title} (current: {current_episodes})'
            )
            self.logger.warning('Episode validation failed: %s', message)
            return ScrobbleResult(ScrobbleOutcome.NOT_NEXT_EPISODE, message, entry)

        previous_status = entry.get('status', '')
        new_status = self._next_status(entry, anime, episode)

        self.logger.info(
            'Updating anime progress: %s -> episode %s%s',
            anime_name, episode, f', status: {new_status}' if new_status else '',
        )
        if not self.library.client.update_anime_progress(rate_id, episode, status=new_status):
            message = f'Failed to update {anime_name}'
            self.logger.error('Anime progress update failed: %s', message)
            return ScrobbleResult(ScrobbleOutcome.UPDATE_FAILED, message, entry)

        self._committed.add(commit_key)
        entry['episodes'] = episode
        if new_status:
            self.library.move_anime_entry(entry, new_status)
        self.library.save_anime_cache()

        self._notify(entry, anime, anime_name, episode, previous_status, new_status)

        message = f'Updated {anime_name} to episode {episode}'
        if new_status == 'completed':
            message += ' (Completed)'
        elif previous_status == 'planned' and new_status == 'watching':
            message += ' (Moved to Watching)'
        self.logger.info('Anime progress update successful: %s', message)

        return ScrobbleResult(ScrobbleOutcome.UPDATED, message, entry)

    # ------------------------------------------------------------- internals --

    def _next_status(self, entry: Dict[str, Any], anime: Dict[str, Any],
                     episode: int) -> Optional[str]:
        """Decide whether this episode also changes the entry's status.

        Starting a planned title moves it to watching. Reaching the final
        episode completes it, but only when a score is already set, so the user
        is not left with a completed entry they never rated.
        """
        current_status = entry.get('status', '')
        total_episodes = anime.get('episodes', 0)

        if current_status == 'planned' and episode > 0:
            self.logger.info('Status change: %s -> watching (started watching)', current_status)
            return 'watching'

        if total_episodes > 0 and episode >= total_episodes:
            if entry.get('score', 0) > 0:
                self.logger.info(
                    'Status change: %s -> completed (finished, has score)', current_status
                )
                return 'completed'
            self.logger.info(
                'Anime finished but no score set, keeping status as %s', current_status
            )

        return None

    def _notify(self, entry: Dict[str, Any], anime: Dict[str, Any], anime_name: str,
                episode: int, previous_status: str, new_status: Optional[str]) -> None:
        """Send the Telegram notification for a committed scrobble."""
        if not self.library.current_user or not self.telegram_notifier:
            return

        username = self.library.username
        anime_url = anime.get('url', '')

        try:
            if new_status == 'completed':
                is_rewatch = previous_status == 'rewatching'
                rewatch_count = entry.get('rewatches', 0) + 1 if is_rewatch else 0
                self.logger.info(
                    'Sending completion Telegram notification for %s%s',
                    anime_name, f' (rewatch #{rewatch_count})' if is_rewatch else '',
                )
                comment = entry.get('text', '') or entry.get('text_html', '')
                self.telegram_notifier.send_completion_update(
                    anime_name, entry.get('score', 0), username,
                    is_rewatch, rewatch_count, anime_url, comment,
                )
            else:
                self.logger.info(
                    'Sending progress Telegram notification for %s episode %s',
                    anime_name, episode,
                )
                self.telegram_notifier.send_progress_update(
                    anime_name, episode, anime.get('episodes', 0), username, anime_url,
                )
        except Exception:
            # A failed notification must never undo a successful list update.
            self.logger.exception('Failed to send Telegram notification for %s', anime_name)
