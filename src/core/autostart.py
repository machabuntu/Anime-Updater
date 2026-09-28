"""
Launch on login.

A registry value under ``Run`` on Windows, an XDG desktop entry on Linux.
Raises ``AutostartError`` so the caller decides how to tell the user.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from utils.logger import get_logger

APP_NAME = 'AnimeUpdater'
DISPLAY_NAME = 'Anime Updater'

_RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
_AUTOSTART_DIR = Path.home() / '.config' / 'autostart'
_DESKTOP_FILE = _AUTOSTART_DIR / 'anime-updater.desktop'

logger = get_logger('autostart')


class AutostartError(RuntimeError):
    """Raised when the autostart entry could not be written or removed."""


def _is_windows() -> bool:
    return sys.platform == 'win32'


def _command() -> str:
    """The command line that starts this application."""
    if getattr(sys, 'frozen', False):
        return f'"{sys.executable}"' if _is_windows() else sys.executable

    script = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'main.py'))
    if _is_windows():
        return f'"{sys.executable}" "{script}"'
    return f'{sys.executable} {script}'


def is_enabled() -> bool:
    if _is_windows():
        return _windows_is_enabled()
    return _DESKTOP_FILE.exists()


def set_enabled(enabled: bool) -> None:
    """Add or remove the autostart entry, doing nothing if already correct."""
    if enabled == is_enabled():
        return
    if enabled:
        _enable()
    else:
        _disable()


def _enable() -> None:
    if _is_windows():
        _windows_enable()
        return

    try:
        _AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
        _DESKTOP_FILE.write_text(
            '[Desktop Entry]\n'
            'Type=Application\n'
            f'Name={DISPLAY_NAME}\n'
            f'Exec={_command()}\n'
            'Terminal=false\n'
            'X-GNOME-Autostart-enabled=true\n',
            encoding='utf-8',
        )
    except OSError as exc:
        raise AutostartError(f'Could not write {_DESKTOP_FILE}: {exc}') from exc


def _disable() -> None:
    if _is_windows():
        _windows_disable()
        return

    try:
        _DESKTOP_FILE.unlink(missing_ok=True)
    except OSError as exc:
        raise AutostartError(f'Could not remove {_DESKTOP_FILE}: {exc}') from exc


def _windows_is_enabled() -> bool:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        return False
    except OSError:
        logger.exception('Could not read the autostart registry key')
        return False


def _windows_enable() -> None:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _command())
    except OSError as exc:
        raise AutostartError(f'Could not write the autostart registry value: {exc}') from exc


def _windows_disable() -> None:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise AutostartError(f'Could not remove the autostart registry value: {exc}') from exc
