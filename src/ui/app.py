"""
Qt application bootstrap.

Owns the QApplication, installs the theme and hands control to the main window.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from ui import theme as theme_pkg
from ui import workers

logger = logging.getLogger('ui.app')

APP_NAME = 'Anime Updater'
ORG_NAME = 'ShikimoriUpdater'


def resource_path(name: str) -> Optional[Path]:
    """Locate a file bundled next to the application.

    Works both from a source checkout and from a PyInstaller one-file build,
    where data files are unpacked into ``sys._MEIPASS``.
    """
    roots = []
    if getattr(sys, 'frozen', False):
        roots.append(Path(getattr(sys, '_MEIPASS', '.')))
    roots.append(Path(__file__).resolve().parents[2])

    for root in roots:
        candidate = root / name
        if candidate.exists():
            return candidate
    return None


def app_icon() -> QIcon:
    """Load the window/taskbar icon, preferring the PNG over the ICO."""
    icon = QIcon()
    for name in ('icon.png', 'icon.ico'):
        path = resource_path(name)
        if path is not None:
            icon.addFile(str(path))
    return icon


def create_application(argv: Optional[list] = None) -> QApplication:
    """Create and configure the QApplication instance."""
    existing = QApplication.instance()
    if existing is not None:
        return existing

    # Fractional scaling looks better rounded up than snapped to integers.
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setDesktopFileName('anime-updater')

    # Fusion reacts predictably to stylesheets on every platform, unlike the
    # native Windows style which ignores several QSS properties.
    app.setStyle('Fusion')

    # With close-to-tray enabled the main window is only hidden, and Qt would
    # otherwise treat that as the last window going away and exit.
    app.setQuitOnLastWindowClosed(False)

    icon = app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    return app


def run(config) -> int:
    """Start the Qt interface and block until the user closes it."""
    app = create_application()

    theme_pkg.install(app, config.theme_mode)

    # Imported late so that a failure here can still be reported through a Qt
    # message box rather than crashing before the application exists.
    try:
        from ui.main_window import MainWindow
    except Exception as exc:
        logger.exception('Failed to import the main window')
        QMessageBox.critical(None, 'Startup Error', f'Failed to build the interface:\n\n{exc}')
        return 1

    window = MainWindow(config)
    window.show()

    try:
        return app.exec()
    finally:
        workers.shutdown()


def run_self_test(config) -> int:
    """Build the whole interface in both themes, then exit.

    A packaged binary can fail in ways a source checkout never does: a missing
    Qt platform plugin, a stylesheet that was not bundled, an import pruned by
    PyInstaller. Running this after a build catches all three.
    """
    from PySide6.QtCore import QTimer

    app = create_application()
    theme_pkg.install(app, config.theme_mode)

    from ui.main_window import MainWindow

    window = MainWindow(config)
    window.show()

    manager = theme_pkg.theme()
    for mode in (theme_pkg.THEME_LIGHT, theme_pkg.THEME_DARK):
        manager.set_mode(mode)
        app.processEvents()

    QTimer.singleShot(0, app.quit)
    try:
        app.exec()
    finally:
        window.quit_application()
        workers.shutdown()

    print('Self test passed: the interface builds and both themes apply.')
    return 0


def run_gallery() -> int:
    """Developer entry point that renders every styled widget.

    Useful for checking the stylesheet in both themes without authenticating.
    Invoked with ``python main.py --gallery``.
    """
    app = create_application()
    mode = os.environ.get('SHIKI_THEME', theme_pkg.THEME_LIGHT)
    theme_pkg.install(app, mode)

    from ui.gallery import GalleryWindow

    window = GalleryWindow()
    window.show()
    return app.exec()
