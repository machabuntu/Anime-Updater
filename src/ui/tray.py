"""
System tray icon.

Replaces pystray, which needed its own thread and a separate Pillow rendered
image. QSystemTrayIcon lives on the GUI thread and reuses the window icon.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from utils import notification_service
from utils.logger import get_logger

TOOLTIP = 'Anime Updater'


class TrayIcon(QObject):
    """Tray icon with the same menu the pystray version offered."""

    show_requested = Signal()
    toggle_monitoring_requested = Signal()
    refresh_requested = Signal()
    quit_requested = Signal()

    def __init__(self, icon: QIcon, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.logger = get_logger('tray')
        self._icon = QSystemTrayIcon(icon, self)
        self._icon.setToolTip(TOOLTIP)

        menu = QMenu()
        self._show_action = menu.addAction('Show Window')
        self._show_action.triggered.connect(self.show_requested)
        menu.setDefaultAction(self._show_action)
        menu.addSeparator()

        self._monitor_action = menu.addAction('Start Scrobbling')
        self._monitor_action.triggered.connect(self.toggle_monitoring_requested)

        menu.addAction('Refresh List').triggered.connect(self.refresh_requested)
        menu.addSeparator()
        menu.addAction('Exit').triggered.connect(self.quit_requested)

        # Kept alive explicitly: QSystemTrayIcon does not take ownership.
        self._menu = menu
        self._icon.setContextMenu(menu)
        self._icon.activated.connect(self._on_activated)

    @staticmethod
    def is_available() -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()

    def show(self) -> None:
        if self.is_available():
            self._icon.show()
        else:
            self.logger.info('No system tray on this desktop; icon not shown')

    def hide(self) -> None:
        self._icon.hide()

    def set_monitoring(self, active: bool) -> None:
        self._monitor_action.setText('Stop Scrobbling' if active else 'Start Scrobbling')

    def set_tooltip(self, text: str) -> None:
        self._icon.setToolTip(text or TOOLTIP)

    def notify(self, title: str, message: str, seconds: int = 5) -> bool:
        """Show a desktop notification through the tray, if supported."""
        if not self.is_available() or not QSystemTrayIcon.supportsMessages():
            return False
        self._icon.showMessage(title, message, self._icon.icon(), seconds * 1000)
        return True

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_requested.emit()


def install(window: QWidget, controller) -> Optional[TrayIcon]:
    """Attach a tray icon to the main window, or return None if unsupported."""
    if not TrayIcon.is_available():
        get_logger('tray').info('System tray unavailable; running without it')
        return None

    tray = TrayIcon(window.windowIcon(), window)
    tray.show_requested.connect(lambda: _restore(window))
    tray.toggle_monitoring_requested.connect(controller.toggle_monitoring)
    tray.refresh_requested.connect(lambda: controller.refresh_anime_list(True))
    tray.quit_requested.connect(window.quit_application)
    controller.monitoring_changed.connect(tray.set_monitoring)
    tray.set_monitoring(controller.monitoring_active)
    tray.show()

    notification_service.set_tray(tray)
    return tray


def _restore(window: QWidget) -> None:
    window.showNormal()
    window.raise_()
    window.activateWindow()
