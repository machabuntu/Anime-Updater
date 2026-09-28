"""
Main application window.

Keeps the layout of the tkinter original: a toolbar holding the menu button and
the compact panel for the selected title, four tabs below it, and a status bar
with the "Now Watching" read-out on the right.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QActionGroup, QCloseEvent, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QWidget,
)

from ui.controller import NOW_WATCHING_IDLE, AppController
from ui.selection_panel import SelectionPanel
from ui.theme import THEME_DARK, THEME_LIGHT, THEME_SYSTEM, theme
from ui.widgets import IconToolButton, secondary_label, vline
from utils.logger import get_logger

STATUS_CLEAR_MS = 10000

# Messages describing work in flight should stay until replaced, matching the
# tkinter behaviour.
STICKY_PREFIXES = ('Loading', 'Loaded', 'Refreshing')

DEFAULT_WIDTH = 1000
DEFAULT_HEIGHT = 700


class MainWindow(QMainWindow):
    """Shell that hosts the four views and wires them to the controller."""

    def __init__(self, config, controller: Optional[AppController] = None) -> None:
        super().__init__()
        self.config = config
        self.logger = get_logger('main_window')
        self.controller = controller or AppController(config)

        self._closing = False
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(lambda: self.status_label.setText(''))

        self.setWindowIcon(_app_icon())
        self._build_toolbar()
        self._build_tabs()
        self._build_status_bar()
        self._restore_geometry()
        self._connect_controller()

        from ui import tray as tray_module
        self.tray = tray_module.install(self, self.controller)

        self.setWindowTitle(self.controller.window_title())

    # ------------------------------------------------------------ construction --

    def _build_toolbar(self) -> None:
        toolbar = QToolBar('Main', self)
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        self.addToolBar(Qt.TopToolBarArea, toolbar)

        self.menu_button = IconToolButton('menu', 'Menu', tooltip='Application menu')
        self.menu_button.setPopupMode(IconToolButton.InstantPopup)
        self.menu_button.setMenu(self._build_menu())
        toolbar.addWidget(self.menu_button)
        toolbar.addWidget(vline())

        client = self.controller.client
        self.selection_panel = SelectionPanel(client.STATUSES, client.MANGA_STATUSES)
        self.selection_panel.episodes_changed.connect(self._on_progress_changed)
        self.selection_panel.volumes_changed.connect(self._on_volumes_changed)
        self.selection_panel.status_changed.connect(self._on_status_changed)
        self.selection_panel.score_changed.connect(self._on_score_changed)
        toolbar.addWidget(self.selection_panel)

    def _build_menu(self) -> QMenu:
        menu = QMenu(self)
        icon = theme().icon

        self.auth_action = menu.addAction(icon('key'), 'Authentication...')
        self.auth_action.triggered.connect(self._handle_auth)
        menu.addSeparator()

        self.scrobble_action = menu.addAction(icon('play'), 'Start Scrobbling')
        self.scrobble_action.setShortcut(QKeySequence('Ctrl+M'))
        self.scrobble_action.triggered.connect(self.controller.toggle_monitoring)
        menu.addSeparator()

        self.refresh_anime_action = menu.addAction(icon('refresh'), 'Refresh Anime List')
        self.refresh_anime_action.setShortcut(QKeySequence.Refresh)
        self.refresh_anime_action.triggered.connect(
            lambda: self.controller.refresh_anime_list(True)
        )
        self.refresh_manga_action = menu.addAction(icon('book-open'), 'Refresh Manga List')
        self.refresh_manga_action.triggered.connect(
            lambda: self.controller.refresh_manga_list(True)
        )
        menu.addSeparator()

        self.options_action = menu.addAction(icon('settings'), 'Options...')
        self.options_action.triggered.connect(self._show_options)

        appearance = menu.addMenu(icon('monitor'), 'Appearance')
        self._appearance_menu = appearance
        self._theme_group = QActionGroup(self)
        self._theme_group.setExclusive(True)
        self._theme_actions = {}
        for mode, label, name in (
            (THEME_SYSTEM, 'Follow system', 'monitor'),
            (THEME_LIGHT, 'Light', 'sun'),
            (THEME_DARK, 'Dark', 'moon'),
        ):
            entry = appearance.addAction(icon(name), label)
            entry.setCheckable(True)
            entry.setChecked(theme().mode == mode)
            entry.triggered.connect(lambda _checked, m=mode: self._set_theme(m))
            self._theme_group.addAction(entry)
            self._theme_actions[mode] = (entry, name)
        menu.addSeparator()

        self.clear_cache_action = menu.addAction(icon('trash'), 'Clear Cache')
        self.clear_cache_action.triggered.connect(self._clear_cache)
        self.synonyms_action = menu.addAction(icon('database'), 'Refresh Synonyms')
        self.synonyms_action.triggered.connect(self.controller.refresh_synonyms)
        menu.addSeparator()

        self.logs_action = menu.addAction(icon('file-text'), 'View Logs')
        self.logs_action.triggered.connect(self._show_logs)
        menu.addSeparator()

        self.update_action = menu.addAction(icon('download'), 'Check for Updates')
        self.update_action.triggered.connect(
            lambda: self.controller.check_for_updates(manual=True)
        )
        menu.addSeparator()

        self.quit_action = menu.addAction(icon('log-out'), 'Exit')
        self.quit_action.setShortcut(QKeySequence.Quit)
        self.quit_action.triggered.connect(self.close)

        theme().theme_changed.connect(self._refresh_menu_icons)
        return menu

    def _refresh_menu_icons(self, *_args) -> None:
        icon = theme().icon
        self.auth_action.setIcon(icon('key'))
        self.scrobble_action.setIcon(
            icon('stop' if self.controller.is_monitoring() else 'play')
        )
        self.refresh_anime_action.setIcon(icon('refresh'))
        self.refresh_manga_action.setIcon(icon('book-open'))
        self.options_action.setIcon(icon('settings'))
        self._appearance_menu.setIcon(icon('monitor'))
        for action, name in self._theme_actions.values():
            action.setIcon(icon(name))
        self.clear_cache_action.setIcon(icon('trash'))
        self.synonyms_action.setIcon(icon('database'))
        self.logs_action.setIcon(icon('file-text'))
        self.update_action.setIcon(icon('download'))
        self.quit_action.setIcon(icon('log-out'))

    def _build_tabs(self) -> None:
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        from ui.views import MangaListView, SearchView, SeasonalView, AnimeListView

        self.anime_view = AnimeListView(self.controller)
        self.manga_view = MangaListView(self.controller)
        self.search_view = SearchView(self.controller)
        self.seasonal_view = SeasonalView(self.controller)

        self.tabs.addTab(self.anime_view, 'Anime List')
        self.tabs.addTab(self.manga_view, 'Manga List')
        self.tabs.addTab(self.search_view, 'Search && Add')
        self.tabs.addTab(self.seasonal_view, 'Seasonal Anime')

        self.anime_view.selection_changed.connect(self.selection_panel.show_anime)
        self.manga_view.selection_changed.connect(self.selection_panel.show_manga)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.setCentralWidget(self.tabs)

    def _build_status_bar(self) -> None:
        bar = QStatusBar()
        bar.setSizeGripEnabled(True)

        self.status_label = QLabel('Ready')
        bar.addWidget(self.status_label, 1)

        self.now_watching_label = secondary_label(NOW_WATCHING_IDLE)
        bar.addPermanentWidget(self.now_watching_label)

        self.setStatusBar(bar)

    def _connect_controller(self) -> None:
        controller = self.controller
        controller.status_message.connect(self.set_status)
        controller.now_watching_changed.connect(self.now_watching_label.setText)
        controller.user_changed.connect(self._refresh_title)
        controller.monitoring_changed.connect(self._on_monitoring_changed)
        controller.service_changed.connect(self._on_service_changed)
        controller.anime_list_changed.connect(self._on_anime_list_changed)
        controller.manga_list_changed.connect(self._on_manga_list_changed)
        controller.anime_entry_changed.connect(self._on_anime_entry_changed)
        controller.update_available.connect(self._show_update_dialog)
        controller.no_update_available.connect(self._show_no_update_message)
        controller.shutdown_requested.connect(self.close)

    # ---------------------------------------------------------------- geometry --

    def _restore_geometry(self) -> None:
        width = self.config.get('window.width', DEFAULT_WIDTH) or DEFAULT_WIDTH
        height = self.config.get('window.height', DEFAULT_HEIGHT) or DEFAULT_HEIGHT
        self.resize(int(width), int(height))

        x = self.config.get('window.x')
        y = self.config.get('window.y')
        if x is not None and y is not None and self._is_on_screen(int(x), int(y)):
            self.move(int(x), int(y))
        else:
            self._center()

    def _is_on_screen(self, x: int, y: int) -> bool:
        """Guard against a saved position on a monitor that is now gone."""
        from PySide6.QtGui import QGuiApplication

        for screen in QGuiApplication.screens():
            if screen.availableGeometry().contains(x, y):
                return True
        return False

    def _center(self) -> None:
        from PySide6.QtGui import QGuiApplication

        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        self.move(
            available.center().x() - self.width() // 2,
            available.center().y() - self.height() // 2,
        )

    def _save_geometry(self) -> None:
        if self.isMaximized() or self.isFullScreen():
            return
        self.config.set('window.width', self.width())
        self.config.set('window.height', self.height())
        self.config.set('window.x', self.x())
        self.config.set('window.y', self.y())

    # ------------------------------------------------------------------ status --

    def set_status(self, message: str, auto_clear: bool = True) -> None:
        self.status_label.setText(message)
        self._status_timer.stop()
        if auto_clear and not message.startswith(STICKY_PREFIXES):
            self._status_timer.start(STATUS_CLEAR_MS)

    def _refresh_title(self) -> None:
        title = self.controller.window_title()
        self.setWindowTitle(title)
        if self.tray is not None:
            self.tray.set_tooltip(title)

    def _on_monitoring_changed(self, active: bool) -> None:
        self.scrobble_action.setText('Stop Scrobbling' if active else 'Start Scrobbling')
        self.scrobble_action.setIcon(theme().icon('stop' if active else 'play'))

    def _on_service_changed(self) -> None:
        client = self.controller.client
        self.selection_panel.set_statuses(client.STATUSES, client.MANGA_STATUSES)
        self.selection_panel.clear()

    # ------------------------------------------------------------------- views --

    def _on_anime_list_changed(self) -> None:
        self.anime_view.set_data(self.controller.get_anime_list_data())
        self._resync_selection()

    def _on_manga_list_changed(self) -> None:
        self.manga_view.set_data(self.controller.get_manga_list_data())

    def _on_anime_entry_changed(self, entry: Dict[str, Any]) -> None:
        self.anime_view.refresh_entry(entry)
        if self.selection_panel.entry is entry:
            self.selection_panel.show_anime(entry)

    def _resync_selection(self) -> None:
        """Re-read the panel after the underlying list was rebuilt."""
        entry = self.selection_panel.entry
        if entry is None:
            return
        if self.selection_panel.mode == 'anime':
            self.selection_panel.show_anime(entry)
        else:
            self.selection_panel.show_manga(entry)

    def _on_tab_changed(self, index: int) -> None:
        """Show the panel for whichever list the user is looking at."""
        widget = self.tabs.widget(index)
        if widget is self.anime_view:
            self.selection_panel.show_anime(self.anime_view.selected_entry())
        elif widget is self.manga_view:
            self.selection_panel.show_manga(self.manga_view.selected_entry())

    # ------------------------------------------------------- panel interaction --

    def _on_progress_changed(self, value: int) -> None:
        entry = self.selection_panel.entry
        if entry is None:
            return
        if self.selection_panel.mode == 'anime':
            self.controller.update_anime(entry, episodes=value)
        else:
            self.controller.update_manga(entry, chapters=value)

    def _on_volumes_changed(self, value: int) -> None:
        entry = self.selection_panel.entry
        if entry is not None:
            self.controller.update_manga(entry, volumes=value)

    def _on_status_changed(self, status: str) -> None:
        entry = self.selection_panel.entry
        if entry is None:
            return
        if self.selection_panel.mode == 'anime':
            # Rewatching restarts progress, as in the tkinter version.
            episodes = 0 if status == 'rewatching' else None
            self.controller.update_anime(entry, status=status, episodes=episodes)
        else:
            self.controller.update_manga(entry, status=status)

    def _on_score_changed(self, score: int) -> None:
        entry = self.selection_panel.entry
        if entry is None:
            return
        if self.selection_panel.mode == 'anime':
            self.controller.update_anime(entry, score=score)
        else:
            self.controller.update_manga(entry, score=score)

    # ----------------------------------------------------------------- actions --

    def _set_theme(self, mode: str) -> None:
        theme().set_mode(mode)
        self.config.theme_mode = mode

    def _handle_auth(self) -> None:
        from ui.dialogs.auth import AuthDialog

        if self.controller.is_authenticated:
            service = self.controller.client.SERVICE_NAME
            confirmed = QMessageBox.question(
                self, 'Log out', f'Do you want to log out from {service}?'
            ) == QMessageBox.Yes
            if confirmed:
                self.controller.log_out()
            return

        dialog = AuthDialog(self.controller, self)
        if dialog.exec() and self.controller.is_authenticated:
            self.controller.load_user_data()

    def _show_options(self) -> None:
        from ui.dialogs.options import OptionsDialog

        dialog = OptionsDialog(self.controller, self)
        dialog.exec()

    def _show_logs(self) -> None:
        from ui.dialogs.logs import LogViewerDialog

        LogViewerDialog(self).show()

    def _clear_cache(self) -> None:
        confirmed = QMessageBox.question(
            self, 'Clear cache',
            'Delete the cached lists and download them again?',
        ) == QMessageBox.Yes
        if confirmed:
            self.controller.clear_cache()

    def _show_update_dialog(self, info: Dict[str, Any]) -> None:
        from ui.dialogs.update import UpdateDialog

        UpdateDialog(info, self).exec()

    def _show_no_update_message(self) -> None:
        QMessageBox.information(
            self, 'No updates', 'You are running the latest version.'
        )

    # ---------------------------------------------------------------- shutdown --

    def changeEvent(self, event) -> None:
        """Send the window to the tray when minimised, if the user asked for it."""
        from PySide6.QtCore import QEvent

        super().changeEvent(event)
        if (event.type() == QEvent.WindowStateChange
                and self.isMinimized()
                and self.tray is not None
                and self.config.get('ui.minimize_to_tray', False)):
            # Hiding during the event itself confuses some window managers.
            QTimer.singleShot(0, self.hide)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._closing:
            event.accept()
            return

        if self.config.get('ui.close_to_tray', False) and self.tray is not None:
            self.hide()
            event.ignore()
            return

        self._shut_down()
        event.accept()

    def quit_application(self) -> None:
        """Close for real, bypassing the close-to-tray preference."""
        self._shut_down()
        self.close()

    def _shut_down(self) -> None:
        if self._closing:
            return
        self._closing = True
        self._save_geometry()
        if self.tray is not None:
            self.tray.hide()
        self.controller.shutdown()
        # The application does not exit on its own, since closing the last
        # window is not a quit signal while the tray icon may still be around.
        QApplication.quit()


def _app_icon() -> QIcon:
    """Load the bundled application icon, wherever PyInstaller put it."""
    if getattr(sys, 'frozen', False):
        roots = [sys._MEIPASS]
    else:
        roots = [os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))]

    for root in roots:
        for name in ('icon.png', 'icon.ico'):
            path = os.path.join(root, name)
            if os.path.exists(path):
                return QIcon(path)
    return QIcon()
