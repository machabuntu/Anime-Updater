"""
Application update checking.

Thin wrapper over ``utils.updater.UpdateChecker`` that centralises the version
lookup and the auto-check settings. Scheduling is left to the caller because it
belongs to the UI event loop.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple

from utils.logger import get_logger
from utils.version import get_version_info

UpdateCallback = Callable[[bool, Optional[Dict[str, Any]]], None]


class UpdateService:
    """Checks GitHub releases for a newer version."""

    def __init__(self, config) -> None:
        self.config = config
        self.logger = get_logger('updates')

    @property
    def auto_check_enabled(self) -> bool:
        return bool(self.config.get('updates.auto_check', True))

    @property
    def check_interval_seconds(self) -> int:
        return int(self.config.get('updates.check_interval', 3600))

    @property
    def version(self) -> str:
        return get_version_info()['version']

    def check_async(self, callback: UpdateCallback) -> None:
        """Query GitHub on a background thread and report back.

        The callback runs on that background thread, so callers on a GUI must
        marshal it to their own thread.
        """
        try:
            from utils.updater import UpdateChecker

            info = get_version_info()
            checker = UpdateChecker(info['github_repo'], info['version'])
            checker.check_updates_async(callback)
        except Exception as exc:
            self.logger.error('Error checking for updates: %s', exc)
            callback(False, None)

    def check(self) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Synchronous check, for callers that already run off the GUI thread."""
        try:
            from utils.updater import Updater

            info = get_version_info()
            updater = Updater(info['github_repo'], info['version'])
            if updater.check_for_updates():
                return True, updater.get_update_info()
            return False, None
        except Exception as exc:
            self.logger.error('Error checking for updates: %s', exc)
            return False, None
