"""
Launching programs outside the application.

A PyInstaller one-file build unpacks itself into a temporary directory and
points ``LD_LIBRARY_PATH`` at it, so the bundled Qt is found. Every child
process inherits that. On KDE ``xdg-open`` hands the URL to ``kde-open``, which
is itself a Qt program: it then loads our Qt instead of the system one and
dies on a symbol version mismatch before the browser ever starts. Children
therefore get the environment the user's session had, not ours.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from typing import Dict, List, Optional

from utils.logger import get_logger

logger = get_logger('external')

# How long to wait for the opener before assuming it handed off successfully.
# xdg-open returns as soon as the browser has accepted the URL, so a failure
# shows up well inside this window.
_OPENER_GRACE_SECONDS = 5


def _bundle_dir() -> Optional[str]:
    if not getattr(sys, 'frozen', False):
        return None
    return getattr(sys, '_MEIPASS', None)


def external_env() -> Dict[str, str]:
    """The environment to hand to programs that are not part of this bundle."""
    env = dict(os.environ)
    bundle = _bundle_dir()
    if bundle is None:
        return env

    # PyInstaller keeps the value it replaced under a *_ORIG name.
    for var in ('LD_LIBRARY_PATH',):
        original = env.pop(f'{var}_ORIG', None)
        if original is not None:
            env[var] = original
        else:
            env.pop(var, None)

    for key in list(env):
        # Bootloader bookkeeping. A frozen child, such as the standalone
        # updater, would otherwise take these as describing itself.
        if key.startswith('_PYI_') or key.startswith('_MEI'):
            env.pop(key)
            continue

        value = env[key]
        if bundle not in value:
            continue
        kept = [part for part in value.split(os.pathsep) if bundle not in part]
        if kept:
            env[key] = os.pathsep.join(kept)
        else:
            env.pop(key)

    return env


def _linux_openers(url: str) -> List[List[str]]:
    candidates = [
        ['xdg-open', url],
        ['gio', 'open', url],
        ['kde-open', url],
        ['gnome-open', url],
    ]
    return [cmd for cmd in candidates if shutil.which(cmd[0])]


def _watch(proc: subprocess.Popen, command: str) -> None:
    """Drain and log an opener that outlived the grace period."""
    try:
        _out, err = proc.communicate()
    except (OSError, ValueError):
        return
    if proc.returncode:
        logger.warning('%s exited with %s: %s', command, proc.returncode,
                       (err or b'').decode('utf-8', 'replace').strip())


def open_url(url: str) -> bool:
    """Open a URL in the user's browser. Returns False if nothing could open it.

    May block for a few seconds while the opener starts, so GUI code should call
    it off the main thread.
    """
    if not url:
        return False

    if sys.platform == 'win32':
        try:
            os.startfile(url)  # noqa: S606 - the documented way to open a URL on Windows
            return True
        except OSError:
            logger.exception('os.startfile failed for %s', url)
            return webbrowser.open(url)

    if sys.platform == 'darwin':
        return webbrowser.open(url)

    env = external_env()
    for cmd in _linux_openers(url):
        try:
            proc = subprocess.Popen(
                cmd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
        except OSError:
            logger.exception('Could not start %s', cmd[0])
            continue

        try:
            _out, err = proc.communicate(timeout=_OPENER_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            # Still running: generic xdg-open runs the browser in the foreground.
            threading.Thread(target=_watch, args=(proc, cmd[0]), daemon=True).start()
            logger.info('Opened %s with %s', url, cmd[0])
            return True

        if proc.returncode == 0:
            logger.info('Opened %s with %s', url, cmd[0])
            return True

        logger.warning('%s failed with exit code %s: %s', cmd[0], proc.returncode,
                       (err or b'').decode('utf-8', 'replace').strip())

    logger.error('No program could open %s', url)
    return False


def popen(args, **kwargs) -> subprocess.Popen:
    """``subprocess.Popen`` with the bundle stripped from the environment."""
    kwargs.setdefault('env', external_env())
    return subprocess.Popen(args, **kwargs)
