"""
Application controller.

Everything the old ``MainWindow`` did that was not building widgets: owning the
services, driving the scrobble timers, retrying a failed connection and
scheduling update checks. Views talk to this object and listen to its signals,
which keeps them free of business logic.

Callbacks arriving from non-Qt threads (the HTTP API server and the player
monitor) only ever emit signals. Qt queues those into the GUI thread, so timers
and widgets are always touched from the right thread.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, QTimer, Signal

from core.clients import create_client
from core.library import LibraryService, ListLoadResult
from core.scrobble import ScrobbleOutcome, ScrobbleResult, ScrobbleService
from core.updates import UpdateService
from ui import workers
from utils.logger import get_logger
from utils.version import get_version_info

NOW_WATCHING_IDLE = 'Now Watching: None'

CONNECTION_RETRY_MS = 5000
STARTUP_UPDATE_CHECK_MS = 5000
AUTO_START_MONITORING_MS = 2000


class AppController(QObject):
    """Owns application state and services for the Qt interface."""

    # Status bar text. The flag says whether it should clear itself.
    status_message = Signal(str, bool)
    now_watching_changed = Signal(str)

    anime_list_changed = Signal()
    manga_list_changed = Signal()
    anime_entry_changed = Signal(dict)

    user_changed = Signal()
    monitoring_changed = Signal(bool)
    service_changed = Signal()

    update_available = Signal(dict)
    no_update_available = Signal()
    shutdown_requested = Signal()

    # Internal hops from worker threads into the GUI thread.
    _scrobble_requested = Signal(str, int, str)
    _scrobble_cancelled = Signal(str, str)

    def __init__(self, config, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.config = config
        self.logger = get_logger('controller')

        self.client = create_client(config)
        self.library = LibraryService(config, self.client)

        from utils.telegram_notifier import TelegramNotifier
        self.telegram_notifier = TelegramNotifier(config)
        self.scrobbler = ScrobbleService(config, self.library, self.telegram_notifier)
        self.updates = UpdateService(config)

        from utils.player_monitor import PlayerMonitor
        self.player_monitor = PlayerMonitor(config)
        self.monitoring_active = False

        self.notification_manager = self._create_notification_manager()

        self._pending_scrobbles: Dict[str, QTimer] = {}
        self._connection_retry = QTimer(self)
        self._connection_retry.setSingleShot(True)
        self._connection_retry.setInterval(CONNECTION_RETRY_MS)
        self._connection_retry.timeout.connect(lambda: self.load_user_data(is_retry=True))

        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._auto_check_updates)

        self._manual_update_check = False

        self._scrobble_requested.connect(self._begin_pending_scrobble)
        self._scrobble_cancelled.connect(self._cancel_pending_scrobble)

        self._wire_player_monitor()
        self.api_server = self._start_api_server()

    # ------------------------------------------------------------- lifecycle --

    def start(self) -> None:
        """Kick off everything that should happen shortly after launch."""
        if self.config.is_authenticated:
            self.load_user_data()
            if self.config.get('monitoring.auto_start', False):
                QTimer.singleShot(AUTO_START_MONITORING_MS, self.start_monitoring)
        else:
            self.user_changed.emit()

        QTimer.singleShot(STARTUP_UPDATE_CHECK_MS, self.check_for_updates)
        self.schedule_update_check()

    def shutdown(self) -> None:
        """Stop every background facility. Safe to call more than once."""
        self._connection_retry.stop()
        self._update_timer.stop()

        for timer in self._pending_scrobbles.values():
            timer.stop()
        self._pending_scrobbles.clear()

        if self.monitoring_active:
            try:
                self.player_monitor.stop_monitoring()
            except Exception:
                self.logger.exception('Failed to stop the player monitor')
            self.monitoring_active = False

        for facility, stop in (
            ('notification manager', getattr(self.notification_manager, 'stop_monitoring', None)),
            ('API server', getattr(self.api_server, 'stop', None)),
        ):
            if stop is None:
                continue
            try:
                stop()
            except Exception:
                self.logger.exception('Failed to stop the %s', facility)

        self.library.shutdown()

    # ------------------------------------------------------------------ title --

    def window_title(self) -> str:
        """Title text mirroring the tkinter format, including the version."""
        version = get_version_info()['version']
        service = self.client.SERVICE_NAME

        if self.library.current_user:
            state = 'Active' if self.monitoring_active else 'Passive'
            return (
                f'Anime Updater ({service}) - Logged as {self.library.username}'
                f' - Scrobbling {state} - v{version}'
            )
        return f'Anime Updater ({service}) - Not logged in - v{version}'

    # ------------------------------------------------------------------- auth --

    @property
    def is_authenticated(self) -> bool:
        return bool(self.config.is_authenticated)

    def log_out(self) -> None:
        """Drop the stored tokens for the active service."""
        self.logger.info('Logging out user: %s', self.library.username)
        service = self.config.active_service
        for key in ('access_token', 'refresh_token', 'user_id'):
            self.config.set(f'{service}.{key}', None)

        self.library.matcher.stop_periodic_updater()
        self.library.clear()

        self.anime_list_changed.emit()
        self.manga_list_changed.emit()
        self.user_changed.emit()
        self.status_message.emit('Logged out', True)

    def on_service_changed(self) -> None:
        """Rebuild the client stack after the user switched service."""
        self._connection_retry.stop()

        self.client = create_client(self.config)
        self.library.set_client(self.client)
        self.notification_manager = self._create_notification_manager()

        self.anime_list_changed.emit()
        self.manga_list_changed.emit()
        self.user_changed.emit()
        self.service_changed.emit()
        self.status_message.emit(f'Switched to {self.client.SERVICE_NAME}', True)

        if self.config.is_authenticated:
            self.load_user_data()

    # -------------------------------------------------------------- list data --

    def load_user_data(self, is_retry: bool = False) -> None:
        """Fetch the user, then both lists, retrying on connection failure."""
        if is_retry:
            self._connection_retry.stop()

        self.logger.info('Starting user data loading process')
        self.status_message.emit('Loading user data...', False)

        def load() -> bool:
            user = self.library.load_user()
            if not user:
                return False

            self.library.load_anime_list(progress=self._emit_progress)
            self.library.load_manga_list(progress=self._emit_progress)
            self.library.set_cache_updated_callback(self._on_detailed_cache_updated)
            return True

        def done(ok: bool) -> None:
            if not ok:
                self.logger.error('Failed to get user information from the API')
                self._retry_connection('Connection failed')
                return

            self.logger.info('User data loaded for %s', self.library.username)
            self.user_changed.emit()
            self.anime_list_changed.emit()
            self.manga_list_changed.emit()
            self.status_message.emit(
                f'Loaded {_total(self.library.anime_list_data)} anime and '
                f'{_total(self.library.manga_list_data)} manga',
                True,
            )

        workers.run_async(
            load,
            on_success=done,
            on_error=lambda message: self._retry_connection(f'Connection error: {message}'),
        )

    def refresh_anime_list(self, force_refresh: bool = False) -> None:
        if not self._require_auth():
            return

        def load() -> ListLoadResult:
            return self.library.load_anime_list(force_refresh, self._emit_progress)

        def done(result: ListLoadResult) -> None:
            if not result.loaded:
                return
            if not result.from_cache:
                self.scrobbler.reset_session()
            self.anime_list_changed.emit()
            source = 'from cache' if result.from_cache else 'updated'
            self.status_message.emit(f'Anime list {source} - {result.total} anime', True)

        workers.run_async(load, on_success=done, on_error=self._emit_error)

    def refresh_manga_list(self, force_refresh: bool = False) -> None:
        if not self._require_auth():
            return

        def load() -> ListLoadResult:
            return self.library.load_manga_list(force_refresh, self._emit_progress)

        def done(result: ListLoadResult) -> None:
            if not result.loaded:
                return
            self.manga_list_changed.emit()
            source = 'from cache' if result.from_cache else 'updated'
            self.status_message.emit(f'Manga list {source} - {result.total} manga', True)

        workers.run_async(load, on_success=done, on_error=self._emit_error)

    def reload_anime_from_cache(self) -> None:
        """Re-read the anime list from disk, falling back to a full refresh."""
        def load() -> ListLoadResult:
            return self.library.reload_anime_from_cache()

        def done(result: ListLoadResult) -> None:
            if not result.loaded:
                self.refresh_anime_list(force_refresh=True)
                return
            self.anime_list_changed.emit()
            self.status_message.emit(f'Updated from cache - {result.total} anime', True)

        workers.run_async(load, on_success=done,
                          on_error=lambda _m: self.refresh_anime_list(force_refresh=True))

    def reload_manga_from_cache(self) -> None:
        def load() -> ListLoadResult:
            return self.library.reload_manga_from_cache()

        def done(result: ListLoadResult) -> None:
            if not result.loaded:
                self.refresh_manga_list(force_refresh=True)
                return
            self.manga_list_changed.emit()
            self.status_message.emit(f'Updated from manga cache - {result.total} manga', True)

        workers.run_async(load, on_success=done,
                          on_error=lambda _m: self.refresh_manga_list(force_refresh=True))

    def add_anime_to_cache_and_reload(self, anime_entry: Dict[str, Any]) -> None:
        """Insert a freshly added title into the cache and reload."""
        def work() -> bool:
            return self.library.add_anime_to_cache(anime_entry)

        workers.run_async(
            work,
            on_success=lambda ok: (
                self.reload_anime_from_cache() if ok
                else self.refresh_anime_list(force_refresh=True)
            ),
            on_error=lambda _m: self.refresh_anime_list(force_refresh=True),
        )

    def update_anime_cache_and_reload(self, anime_id: int, updates: Dict[str, Any]) -> None:
        def work() -> bool:
            return self.library.update_anime_in_cache(anime_id, updates)

        workers.run_async(
            work,
            on_success=lambda ok: (
                self.reload_anime_from_cache() if ok
                else self.refresh_anime_list(force_refresh=True)
            ),
            on_error=lambda _m: self.refresh_anime_list(force_refresh=True),
        )

    def update_manga_cache_and_reload(self, manga_id: int, updates: Dict[str, Any]) -> None:
        def work() -> bool:
            return self.library.update_manga_in_cache(manga_id, updates)

        workers.run_async(
            work,
            on_success=lambda ok: (
                self.reload_manga_from_cache() if ok
                else self.refresh_manga_list(force_refresh=True)
            ),
            on_error=lambda _m: self.refresh_manga_list(force_refresh=True),
        )

    def clear_cache(self) -> None:
        """Drop the on-disk cache and pull everything again."""
        try:
            self.library.cache_manager.clear_cache(self.library.user_id)
        except Exception as exc:
            self._emit_error(str(exc))
            return
        self.status_message.emit('Cache cleared, refreshing...', True)
        self.refresh_anime_list(force_refresh=True)
        self.refresh_manga_list(force_refresh=True)

    def refresh_synonyms(self) -> None:
        """Re-download alternative titles used for fuzzy matching."""
        user_id = self.library.user_id
        if user_id is None:
            self.status_message.emit('Log in first', True)
            return

        self.status_message.emit('Refreshing synonyms...', False)

        def work() -> None:
            self.library.matcher.initialize_detailed_cache(
                user_id, self.library.anime_list_data
            )

        workers.run_async(
            work,
            on_success=lambda _r: self.status_message.emit('Synonyms refreshed', True),
            on_error=self._emit_error,
        )

    # ------------------------------------------------------- anime list edits --

    def get_anime_list_data(self) -> Dict[str, List[Dict[str, Any]]]:
        return self.library.anime_list_data

    def get_manga_list_data(self) -> Dict[str, List[Dict[str, Any]]]:
        return self.library.manga_list_data

    def update_anime(self, entry: Dict[str, Any], episodes: Optional[int] = None,
                     status: Optional[str] = None, score: Optional[int] = None,
                     rewatches: Optional[int] = None) -> None:
        """Push a manual anime edit, then reflect it locally."""
        rate_id = entry['id']
        name = entry.get('anime', {}).get('name', 'anime')

        def work() -> bool:
            return self.client.update_anime_progress(
                rate_id,
                episodes if episodes is not None else entry.get('episodes', 0),
                status=status,
                score=score,
                rewatches=rewatches,
            )

        def done(ok: bool) -> None:
            if not ok:
                self.status_message.emit(f'Failed to update {name}', True)
                return

            updates: Dict[str, Any] = {}
            if episodes is not None:
                entry['episodes'] = episodes
                updates['episodes'] = episodes
            if score is not None:
                entry['score'] = score
                updates['score'] = score
            if rewatches is not None:
                entry['rewatches'] = rewatches
                updates['rewatches'] = rewatches
            if status is not None:
                self.library.move_anime_entry(entry, status)
                updates['status'] = status

            self.library.save_anime_cache()
            self.status_message.emit(f'Updated {name}', True)
            if status is not None:
                self.anime_list_changed.emit()
            else:
                self.anime_entry_changed.emit(entry)

        workers.run_async(work, on_success=done, on_error=self._emit_error)

    def update_manga(self, entry: Dict[str, Any], chapters: Optional[int] = None,
                     volumes: Optional[int] = None, status: Optional[str] = None,
                     score: Optional[int] = None) -> None:
        """Push a manual manga edit, then reflect it locally."""
        rate_id = entry['id']
        name = entry.get('manga', {}).get('name', 'manga')

        def work() -> bool:
            return self.client.update_manga_progress(
                rate_id,
                chapters if chapters is not None else entry.get('chapters', 0),
                volumes=volumes,
                status=status,
                score=score,
            )

        def done(ok: bool) -> None:
            if not ok:
                self.status_message.emit(f'Failed to update {name}', True)
                return

            if chapters is not None:
                entry['chapters'] = chapters
            if volumes is not None:
                entry['volumes'] = volumes
            if score is not None:
                entry['score'] = score
            if status is not None:
                entry['status'] = status

            self.library.save_manga_cache()
            self.status_message.emit(f'Updated {name}', True)
            self.manga_list_changed.emit()

        workers.run_async(work, on_success=done, on_error=self._emit_error)

    def remove_anime(self, entry: Dict[str, Any]) -> None:
        rate_id = entry['id']
        name = entry.get('anime', {}).get('name', 'anime')

        def work() -> bool:
            return self.client.delete_anime_from_list(rate_id)

        def done(ok: bool) -> None:
            if ok:
                self.status_message.emit(f'Removed {name}', True)
                self.refresh_anime_list(force_refresh=True)
            else:
                self.status_message.emit(f'Failed to remove {name}', True)

        workers.run_async(work, on_success=done, on_error=self._emit_error)

    def remove_manga(self, entry: Dict[str, Any]) -> None:
        rate_id = entry['id']
        name = entry.get('manga', {}).get('name', 'manga')

        def work() -> bool:
            return self.client.delete_manga_from_list(rate_id)

        def done(ok: bool) -> None:
            if ok:
                self.status_message.emit(f'Removed {name}', True)
                self.refresh_manga_list(force_refresh=True)
            else:
                self.status_message.emit(f'Failed to remove {name}', True)

        workers.run_async(work, on_success=done, on_error=self._emit_error)

    def set_anime_comment(self, entry: Dict[str, Any], text: str) -> None:
        """Save a review. Both text fields are written, as the API returns
        either depending on the service."""
        rate_id = entry['id']
        anime = entry.get('anime', {})

        def work() -> bool:
            return self.client.update_anime_progress(rate_id, text=text, text_html=text)

        def done(ok: bool) -> None:
            if not ok:
                self.status_message.emit('Failed to save comment', True)
                return

            entry['text'] = text
            entry['text_html'] = text
            self.library.save_anime_cache()
            self.status_message.emit('Comment saved', True)
            self.anime_entry_changed.emit(entry)

            if text and self.telegram_notifier:
                try:
                    self.telegram_notifier.send_comment_update(
                        anime.get('name', 'Unknown'), text,
                        self.library.username, anime.get('url', ''),
                    )
                except Exception:
                    self.logger.exception('Failed to send comment notification')

        workers.run_async(work, on_success=done, on_error=self._emit_error)

    def set_manga_comment(self, entry: Dict[str, Any], text: str) -> None:
        rate_id = entry['id']

        def work() -> bool:
            return self.client.update_manga_progress(rate_id, text=text, text_html=text)

        def done(ok: bool) -> None:
            if not ok:
                self.status_message.emit('Failed to save comment', True)
                return
            entry['text'] = text
            entry['text_html'] = text
            self.library.save_manga_cache()
            self.status_message.emit('Comment saved', True)

        workers.run_async(work, on_success=done, on_error=self._emit_error)

    def add_anime(self, anime_id: int, status: str, on_done=None) -> None:
        """Add a title to the list from search or the seasonal browser."""
        def work():
            return self.client.add_anime_to_list(anime_id, status)

        def done(entry) -> None:
            if entry:
                self.status_message.emit('Added to list', True)
                if isinstance(entry, dict):
                    self.add_anime_to_cache_and_reload(entry)
                else:
                    self.refresh_anime_list(force_refresh=True)
            else:
                self.status_message.emit('Failed to add to list', True)
            if on_done is not None:
                on_done(bool(entry))

        workers.run_async(work, on_success=done, on_error=self._emit_error)

    # ------------------------------------------------------------- monitoring --

    def is_monitoring(self) -> bool:
        return self.monitoring_active

    def toggle_monitoring(self) -> None:
        if self.monitoring_active:
            self.stop_monitoring()
        else:
            self.start_monitoring()

    def start_monitoring(self) -> None:
        if self.monitoring_active:
            return
        if not self._require_auth():
            return

        self.logger.info('Starting player monitoring')
        self.player_monitor.start_monitoring()
        self.monitoring_active = True
        self.scrobbler.reset_session()
        self.monitoring_changed.emit(True)
        self.user_changed.emit()

    def stop_monitoring(self) -> None:
        if not self.monitoring_active:
            return

        self.logger.info('Stopping player monitoring')
        self.player_monitor.stop_monitoring()
        self.monitoring_active = False
        self.now_watching_changed.emit(NOW_WATCHING_IDLE)
        self.monitoring_changed.emit(False)
        self.user_changed.emit()

    # ---------------------------------------------------------------- updates --

    def check_for_updates(self, manual: bool = False) -> None:
        self._manual_update_check = manual

        def report(available: bool, info: Optional[Dict[str, Any]]) -> None:
            # Runs on the checker's thread; hop back via a queued signal.
            if available and info:
                self.update_available.emit(info)
            elif self._manual_update_check:
                self._manual_update_check = False
                self.no_update_available.emit()

        self.updates.check_async(report)

    def schedule_update_check(self) -> None:
        """Arm the periodic update check, or disarm it when switched off."""
        if not self.updates.auto_check_enabled:
            self._update_timer.stop()
            return

        interval = self.updates.check_interval_seconds
        self._update_timer.start(interval * 1000)
        self.logger.info('Next automatic update check in %s seconds', interval)

    def _auto_check_updates(self) -> None:
        if not self.updates.auto_check_enabled:
            return

        self.logger.info('Performing automatic update check')

        def report(available: bool, info: Optional[Dict[str, Any]]) -> None:
            if available and info:
                self.update_available.emit(info)
            self.schedule_update_check()

        self.updates.check_async(report)

    # ---------------------------------------------------------- scrobble flow --

    def _wire_player_monitor(self) -> None:
        self.player_monitor.on_episode_detected = self._on_episode_detected
        self.player_monitor.on_episode_watched = self._on_episode_watched
        self.player_monitor.on_player_closed = self._on_player_closed

    def _start_api_server(self):
        """Expose the local HTTP endpoint used by the browser extension."""
        try:
            from api.api_server import APIServer
            server = APIServer(
                scrobble_callback=self._handle_remote_scrobble,
                shutdown_callback=lambda: self.shutdown_requested.emit(),
            )
            server.start()
            return server
        except Exception:
            self.logger.exception('Failed to start the local API server')
            return None

    def _handle_remote_scrobble(self, payload: Dict[str, Any]) -> bool:
        """Called on the HTTP server thread by the browser extension."""
        try:
            title = payload.get('title', '')
            episode = payload.get('episode')

            if payload.get('action') == 'cancel':
                self._scrobble_cancelled.emit(title, str(episode or ''))
                return True

            if not title or episode is None:
                self.logger.warning('Scrobble request missing title or episode')
                return False

            episode = int(episode)
            # Matching can be slow, so it stays on this thread rather than
            # blocking the GUI; only the resulting text is handed over.
            description = self.scrobbler.describe_now_watching(title, episode)
            self._scrobble_requested.emit(title, episode, description)
            return True
        except Exception:
            self.logger.exception('Failed to handle scrobble payload')
            return False

    def _begin_pending_scrobble(self, title: str, episode: int, description: str) -> None:
        """Arm the delayed commit for a browser reported episode."""
        self.now_watching_changed.emit(description)

        key = f'{title}_{episode}'
        existing = self._pending_scrobbles.pop(key, None)
        if existing is not None:
            existing.stop()

        delay = self.scrobbler.min_watch_time
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(delay * 1000)
        timer.timeout.connect(lambda: self._commit_pending_scrobble(key, title, episode))
        self._pending_scrobbles[key] = timer
        timer.start()

        self.logger.info(
            'Browser scrobble timer set for %s seconds: %s episode %s', delay, title, episode
        )

    def _commit_pending_scrobble(self, key: str, title: str, episode: int) -> None:
        self._pending_scrobbles.pop(key, None)
        self._process_episode(title, episode)

    def _cancel_pending_scrobble(self, title: str, episode: str) -> None:
        """Drop pending timers for a title the user stopped watching."""
        prefix = f'{title}_'
        keys = [f'{title}_{episode}'] if episode else []
        keys += [key for key in self._pending_scrobbles if key.startswith(prefix)]

        cancelled = 0
        for key in dict.fromkeys(keys):
            timer = self._pending_scrobbles.pop(key, None)
            if timer is not None:
                timer.stop()
                cancelled += 1

        if cancelled:
            self.logger.info('Cancelled %s browser scrobble timer(s) for %s', cancelled, title)
        self.now_watching_changed.emit(NOW_WATCHING_IDLE)

    def _on_episode_detected(self, episode_info) -> None:
        """Player monitor found a title on screen. Runs on its thread."""
        description = self.scrobbler.describe_now_watching(
            episode_info.anime_name, episode_info.episode_number
        )
        self.now_watching_changed.emit(description)

    def _on_episode_watched(self, episode_info, watch_time: float) -> None:
        """Player monitor confirmed enough watch time. Runs on its thread."""
        self.logger.info(
            'Episode watched: %s - episode %s (%.1fs)',
            episode_info.anime_name, episode_info.episode_number, watch_time,
        )
        self._scrobble_requested.emit(
            episode_info.anime_name, episode_info.episode_number, ''
        )

    def _on_player_closed(self) -> None:
        self.now_watching_changed.emit(NOW_WATCHING_IDLE)

    def _process_episode(self, title: str, episode: int) -> None:
        """Run the scrobble pipeline off the GUI thread and report the result."""
        def work() -> ScrobbleResult:
            return self.scrobbler.process_episode(title, episode)

        def done(result: ScrobbleResult) -> None:
            self.status_message.emit(result.message, True)
            if result.outcome is ScrobbleOutcome.UPDATED and result.entry:
                self.anime_list_changed.emit()

        workers.run_async(work, on_success=done, on_error=self._emit_error)

    # ------------------------------------------------------------- internals --

    def _create_notification_manager(self):
        try:
            from utils.notification_manager import NotificationManager
            return NotificationManager(self.config, self.client, self.library.cache_manager)
        except Exception:
            self.logger.exception('Failed to create the notification manager')
            return None

    def _on_detailed_cache_updated(self) -> None:
        """The matcher refreshed airing status for unreleased titles."""
        self.anime_list_changed.emit()

    def _require_auth(self) -> bool:
        if self.config.is_authenticated:
            return True
        self.status_message.emit('Please log in first', True)
        return False

    def _retry_connection(self, reason: str) -> None:
        self.status_message.emit(f'{reason} - retrying in 5 s...', False)
        if not self._connection_retry.isActive():
            self._connection_retry.start()

    def _emit_progress(self, message: str) -> None:
        """Progress callback handed to the library; fires on a worker thread."""
        self.status_message.emit(message, False)

    def _emit_error(self, message: str) -> None:
        self.logger.error('Background operation failed: %s', message)
        self.status_message.emit(f'Error: {message}', True)


def _total(data: Dict[str, List[Dict[str, Any]]]) -> int:
    return sum(len(entries) for entries in data.values())
