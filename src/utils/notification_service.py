"""
Desktop notifications for new episodes and finished airings.

Delivery goes through the tray icon first, which gives a native toast on
Windows and a desktop notification on Linux without any extra dependency. When
there is no tray (a bare X session, GNOME without the AppIndicator extension)
a small themed window is shown in the corner instead.

Callers may be on a worker thread, so everything is marshalled onto the GUI
thread through a signal.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QObject, QPoint, QTimer, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from utils.logger import get_logger

POPUP_TIMEOUT_MS = 10_000
POPUP_WIDTH = 320
POPUP_MARGIN = 16

# The tray icon, once the UI installs one. Kept at module level so the service
# does not need a reference to the main window.
_tray = None


def set_tray(tray) -> None:
    """Register the tray icon used to deliver notifications."""
    global _tray
    _tray = tray


class NotificationService(QObject):
    """Shows a desktop notification, falling back to an in-app popup."""

    _requested = Signal(str, str, object)

    def __init__(self) -> None:
        super().__init__()
        self.logger = get_logger('notifications')
        self._popups: list = []
        self._requested.connect(self._deliver, Qt.QueuedConnection)

    def show_episode_notification(self, anime_name: str, episode_number: int,
                                  callback: Optional[Callable] = None) -> None:
        self._requested.emit(
            'New episode available',
            f'{anime_name}\nEpisode {episode_number} is out',
            callback,
        )

    def show_release_notification(self, anime_name: str,
                                  callback: Optional[Callable] = None) -> None:
        self._requested.emit(
            'Fully released',
            f'{anime_name}\nEvery episode is available now',
            callback,
        )

    def _deliver(self, title: str, message: str, callback: Optional[Callable]) -> None:
        if _tray is not None and _tray.notify(title, message):
            if callback:
                callback()
            return

        if QApplication.instance() is None:
            self.logger.info('No GUI available for notification: %s', title)
            return

        popup = _Popup(title, message, callback)
        popup.closed.connect(lambda: self._popups.remove(popup))
        self._popups.append(popup)
        popup.show_in_corner(len(self._popups) - 1)

    @staticmethod
    def is_available() -> bool:
        """Notifications always work: there is a popup fallback."""
        return True


class _Popup(QWidget):
    """A small always-on-top card in the corner of the primary screen."""

    closed = Signal()

    def __init__(self, title: str, message: str,
                 callback: Optional[Callable] = None) -> None:
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setObjectName('NotificationPopup')
        self.setFixedWidth(POPUP_WIDTH)
        self._callback = callback

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        heading = QLabel(title)
        heading.setObjectName('HeadingLabel')
        layout.addWidget(heading)

        body = QLabel(message)
        body.setWordWrap(True)
        body.setObjectName('SecondaryLabel')
        layout.addWidget(body)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        dismiss = QPushButton('OK')
        dismiss.setProperty('accent', True)
        dismiss.clicked.connect(self.close)
        buttons.addWidget(dismiss)
        layout.addLayout(buttons)

        QTimer.singleShot(POPUP_TIMEOUT_MS, self.close)

    def show_in_corner(self, index: int) -> None:
        """Stack popups upward from the bottom-right of the primary screen."""
        self.adjustSize()
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.show()
            return

        area = screen.availableGeometry()
        offset = (self.height() + 8) * index
        self.move(QPoint(
            area.right() - self.width() - POPUP_MARGIN,
            area.bottom() - self.height() - POPUP_MARGIN - offset,
        ))
        self.show()

    def closeEvent(self, event) -> None:
        self.closed.emit()
        if self._callback:
            try:
                self._callback()
            except Exception:
                get_logger('notifications').exception('Notification callback failed')
            self._callback = None
        super().closeEvent(event)
