"""
Library service.

Owns the user's anime and manga lists: fetching them from the API, caching them
on disk, applying local edits and answering "is this title in my list?".

Deliberately free of any GUI toolkit. Long running methods take an optional
``progress`` callback and are meant to be called from a worker thread; the
caller decides how to get back to its own event loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.cache import CacheManager
from utils.enhanced_anime_matcher import EnhancedAnimeMatcher
from utils.logger import get_logger

# Statuses a title can be in while the user is still watching it. Completed and
# dropped entries are excluded so that a detected episode of season 2 does not
# match the finished season 1.
ACTIVE_ANIME_STATUSES = ('watching', 'planned', 'rewatching', 'on_hold')

ProgressCallback = Optional[Callable[[str], None]]

ListData = Dict[str, List[Dict[str, Any]]]


@dataclass
class ListLoadResult:
    """Outcome of loading a list, used to build the status bar message."""

    data: ListData = field(default_factory=dict)
    total: int = 0
    from_cache: bool = False
    loaded: bool = False


class LibraryService:
    """The user's lists plus everything that reads or writes them."""

    def __init__(self, config, client, cache_manager: Optional[CacheManager] = None,
                 matcher: Optional[EnhancedAnimeMatcher] = None) -> None:
        self.config = config
        self.logger = get_logger('library')
        self.client = client
        self.cache_manager = cache_manager or CacheManager(config)
        self.matcher = matcher or EnhancedAnimeMatcher(client, self.cache_manager)

        self.current_user: Optional[Dict[str, Any]] = None
        self.anime_list_data: ListData = {}
        self.manga_list_data: ListData = {}

    # ------------------------------------------------------------- lifecycle --

    def set_client(self, client) -> None:
        """Swap the API client after the user changed service.

        The matcher caches per-service titles and synonyms, so it is rebuilt
        rather than reused.
        """
        self.matcher.stop_periodic_updater()
        self.client = client
        self.matcher = EnhancedAnimeMatcher(client, self.cache_manager)
        self.clear()

    def clear(self) -> None:
        """Drop all loaded data, e.g. on logout or service switch."""
        self.current_user = None
        self.anime_list_data = {}
        self.manga_list_data = {}

    def shutdown(self) -> None:
        self.matcher.stop_periodic_updater()

    @property
    def user_id(self) -> Optional[int]:
        return self.current_user['id'] if self.current_user else None

    @property
    def username(self) -> str:
        if not self.current_user:
            return 'Unknown'
        return self.current_user.get('nickname', 'Unknown')

    # ------------------------------------------------------------------ user --

    def load_user(self) -> Optional[Dict[str, Any]]:
        """Fetch and remember the authenticated user."""
        self.current_user = self.client.get_current_user()
        return self.current_user

    # ----------------------------------------------------------------- anime --

    def load_anime_list(self, force_refresh: bool = False,
                        progress: ProgressCallback = None) -> ListLoadResult:
        """Load the anime list from cache, or from the API when forced.

        Returns an empty, not-loaded result when there is no authenticated user.
        """
        if not self.current_user:
            return ListLoadResult()

        user_id = self.current_user['id']

        if not force_refresh:
            _report(progress, 'Loading anime list from cache...')
            cached = self.cache_manager.load_anime_list(user_id)
            if cached:
                self.anime_list_data = cached
                self._start_matching(user_id)
                return ListLoadResult(cached, _count(cached), True, True)

        _report(progress, 'Refreshing anime list...')
        data: ListData = {}
        total = 0
        for status_key, status_display in self.client.STATUSES.items():
            _report(progress, f'Loading {status_display} anime...')
            entries = self.client.get_user_anime_list(user_id, status_key)
            data[status_key] = entries
            total += len(entries)
            _report(progress, f'Loaded {total} anime so far...')

        self.anime_list_data = data
        self.cache_manager.save_anime_list(user_id, data)
        self._start_matching(user_id)
        return ListLoadResult(data, total, False, True)

    def reload_anime_from_cache(self) -> ListLoadResult:
        """Re-read the anime list from disk after a local edit."""
        if not self.current_user:
            return ListLoadResult()

        cached = self.cache_manager.load_anime_list(self.current_user['id'])
        if not cached:
            return ListLoadResult()

        self.anime_list_data = cached
        return ListLoadResult(cached, _count(cached), True, True)

    def save_anime_cache(self) -> None:
        """Persist the in-memory anime list, e.g. after a scrobble."""
        if self.current_user:
            self.cache_manager.save_anime_list(self.current_user['id'], self.anime_list_data)

    def add_anime_to_cache(self, anime_entry: Dict[str, Any]) -> bool:
        if not self.current_user:
            return False
        return self.cache_manager.add_anime_to_cache(self.current_user['id'], anime_entry)

    def update_anime_in_cache(self, anime_id: int, updates: Dict[str, Any]) -> bool:
        if not self.current_user:
            return False
        return self.cache_manager.update_anime_in_cache(
            self.current_user['id'], anime_id, updates
        )

    # ----------------------------------------------------------------- manga --

    def load_manga_list(self, force_refresh: bool = False,
                        progress: ProgressCallback = None) -> ListLoadResult:
        """Load the manga list from cache, or from the API when forced."""
        if not self.current_user:
            return ListLoadResult()

        user_id = self.current_user['id']

        if not force_refresh:
            _report(progress, 'Loading manga list from cache...')
            cached = self.cache_manager.load_manga_list(user_id)
            if cached:
                self.manga_list_data = cached
                return ListLoadResult(cached, _count(cached), True, True)

        _report(progress, 'Refreshing manga list...')
        data: ListData = {}
        total = 0
        for status_key, status_display in self.client.MANGA_STATUSES.items():
            _report(progress, f'Loading {status_display} manga...')
            entries = self.client.get_user_manga_list(user_id, status_key)
            data[status_key] = entries
            total += len(entries)
            _report(progress, f'Loaded {total} manga so far...')

        self.manga_list_data = data
        self.cache_manager.save_manga_list(user_id, data)
        return ListLoadResult(data, total, False, True)

    def reload_manga_from_cache(self) -> ListLoadResult:
        if not self.current_user:
            return ListLoadResult()

        cached = self.cache_manager.load_manga_list(self.current_user['id'])
        if not cached:
            return ListLoadResult()

        self.manga_list_data = cached
        return ListLoadResult(cached, _count(cached), True, True)

    def save_manga_cache(self) -> None:
        if self.current_user:
            self.cache_manager.save_manga_list(self.current_user['id'], self.manga_list_data)

    def add_manga_to_cache(self, manga_entry: Dict[str, Any]) -> bool:
        if not self.current_user:
            return False
        return self.cache_manager.add_manga_to_cache(self.current_user['id'], manga_entry)

    def update_manga_in_cache(self, manga_id: int, updates: Dict[str, Any]) -> bool:
        if not self.current_user:
            return False
        return self.cache_manager.update_manga_in_cache(
            self.current_user['id'], manga_id, updates
        )

    # --------------------------------------------------------------- lookups --

    def active_anime_entries(self) -> List[Dict[str, Any]]:
        """Every anime entry the user has not finished or abandoned."""
        entries: List[Dict[str, Any]] = []
        for status_key in ACTIVE_ANIME_STATUSES:
            entries.extend(self.anime_list_data.get(status_key, []))
        return entries

    def all_anime_entries(self) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        for status_entries in self.anime_list_data.values():
            entries.extend(status_entries)
        return entries

    def match_active_anime(self, title: str, episode: Optional[int] = None
                           ) -> Optional[Tuple[Dict[str, Any], float]]:
        """Fuzzy match a detected title against the active entries."""
        entries = self.active_anime_entries()
        if not entries:
            return None
        return self.matcher.find_best_match(title, entries, episode)

    def is_anime_in_active_list(self, title: str) -> bool:
        return self.match_active_anime(title) is not None

    def is_anime_in_list(self, title: str) -> bool:
        entries = self.all_anime_entries()
        if not entries:
            return False
        return self.matcher.find_best_match(title, entries) is not None

    def find_anime_entry(self, anime_id: int) -> Optional[Dict[str, Any]]:
        """Locate a list entry by its rate id."""
        return _find_entry(self.anime_list_data, anime_id)

    def find_manga_entry(self, manga_id: int) -> Optional[Dict[str, Any]]:
        return _find_entry(self.manga_list_data, manga_id)

    def move_anime_entry(self, entry: Dict[str, Any], new_status: str) -> Dict[str, Any]:
        """Move an entry between status buckets, keeping the data consistent.

        The tkinter code mutated ``entry['status']`` without moving the entry
        between buckets, so a scrobble that completed a series left it filed
        under Watching until the next full refresh. Returns the entry that is
        now in the list, which differs from ``entry`` when that was a stale
        copy from before a reload.
        """
        return _move_entry(self.anime_list_data, entry, new_status)

    def move_manga_entry(self, entry: Dict[str, Any], new_status: str) -> Dict[str, Any]:
        return _move_entry(self.manga_list_data, entry, new_status)

    # ------------------------------------------------------------- internals --

    def _start_matching(self, user_id: int) -> None:
        """Prime synonym based matching and keep airing titles up to date."""
        try:
            self.matcher.initialize_detailed_cache(user_id, self.anime_list_data)
            self.matcher.start_periodic_updater(user_id)
        except Exception:
            self.logger.exception('Failed to initialise enhanced anime matching')

    def set_cache_updated_callback(self, callback: Callable[[], None]) -> None:
        """Called by the matcher when it refreshes airing status in background."""
        self.matcher.set_cache_updated_callback(callback)


def _find_entry(data: ListData, entry_id: Any) -> Optional[Dict[str, Any]]:
    for entries in data.values():
        for entry in entries:
            if entry.get('id') == entry_id:
                return entry
    return None


def _move_entry(data: ListData, entry: Dict[str, Any], new_status: str) -> Dict[str, Any]:
    """Refile an entry under ``new_status``, matching it by id.

    Matching by id rather than identity matters: after a list reload the
    caller may still hold the old dict, and moving that one would leave the
    real entry behind in its old bucket and add a duplicate to the new one.
    """
    entry_id = entry.get('id')
    for status_key, entries in data.items():
        for index, candidate in enumerate(entries):
            if candidate is entry or candidate.get('id') == entry_id:
                candidate['status'] = new_status
                if status_key != new_status:
                    del entries[index]
                    data.setdefault(new_status, []).append(candidate)
                return candidate

    entry['status'] = new_status
    data.setdefault(new_status, []).append(entry)
    return entry


def _count(data: ListData) -> int:
    return sum(len(entries) for entries in data.values())


def _report(progress: ProgressCallback, message: str) -> None:
    if progress is not None:
        progress(message)
