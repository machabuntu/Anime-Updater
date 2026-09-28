"""
Settings dialog.

Three tabs matching the tkinter original: Main, Notifications and Network.
Nothing is written to the config until Save is pressed.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ui import workers
from ui.widgets import Card, SectionCard, hint_label
from utils.logger import get_logger

PROXY_TYPES = (('None', 'none'), ('HTTP', 'http'), ('SOCKS5', 'socks5'))
SERVICES = (('Shikimori', 'shikimori'), ('MyAnimeList', 'mal'))


class OptionsDialog(QDialog):
    """Edits application settings."""

    def __init__(self, controller, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.config = controller.config
        self.logger = get_logger('options')

        self.setWindowTitle('Options')
        self.setMinimumSize(560, 620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._main_tab(), 'Main')
        self.tabs.addTab(self._notifications_tab(), 'Notifications')
        self.tabs.addTab(self._network_tab(), 'Network')
        layout.addWidget(self.tabs, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setProperty('accent', True)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._load()

    # -------------------------------------------------------------------- tabs --

    def _main_tab(self) -> QWidget:
        page = ScrollPage()
        body = page.body

        service_card = SectionCard('Anime service')
        self.service_combo = QComboBox()
        for label, key in SERVICES:
            self.service_combo.addItem(label, key)
        self.service_combo.currentIndexChanged.connect(self._on_service_selection)
        service_form = QFormLayout()
        service_form.addRow('Active service:', self.service_combo)
        service_card.add_layout(service_form)

        self.mal_card = Card()
        mal_form = QFormLayout()
        self.mal_client_id = QLineEdit()
        self.mal_client_secret = QLineEdit()
        self.mal_client_secret.setEchoMode(QLineEdit.Password)
        mal_form.addRow('MAL Client ID:', self.mal_client_id)
        mal_form.addRow('MAL Client Secret:', self.mal_client_secret)
        self.mal_card.add_layout(mal_form)
        self.mal_card.add_widget(hint_label(
            'Create an API application in your MyAnimeList profile settings. '
            'The secret can be left empty for public clients.'
        ))
        service_card.add_widget(self.mal_card)
        body.addWidget(service_card)

        startup_card = SectionCard('Startup')
        self.startup_check = QCheckBox('Launch on login')
        self.auto_monitor_check = QCheckBox('Start scrobbling automatically')
        self.auto_update_check = QCheckBox('Check for updates hourly')
        for box in (self.startup_check, self.auto_monitor_check, self.auto_update_check):
            startup_card.add_widget(box)
        body.addWidget(startup_card)

        scrobble_card = SectionCard('Scrobbling')
        self.watch_time_spin = QSpinBox()
        self.watch_time_spin.setRange(1, 120)
        self.watch_time_spin.setSuffix(' min')
        scrobble_form = QFormLayout()
        scrobble_form.addRow('Update progress after:', self.watch_time_spin)
        scrobble_card.add_layout(scrobble_form)
        body.addWidget(scrobble_card)

        tray_card = SectionCard('System tray')
        self.minimize_tray_check = QCheckBox('Minimise to tray instead of the taskbar')
        self.close_tray_check = QCheckBox('Close to tray instead of exiting')
        tray_card.add_widget(self.minimize_tray_check)
        tray_card.add_widget(self.close_tray_check)
        body.addWidget(tray_card)

        body.addStretch(1)
        return page

    def _notifications_tab(self) -> QWidget:
        page = ScrollPage()
        body = page.body

        desktop_card = SectionCard('Desktop notifications')
        self.episode_notify_check = QCheckBox('New episode of a title I am watching')
        self.release_notify_check = QCheckBox('A title from Plan to Watch starts airing')
        desktop_card.add_widget(self.episode_notify_check)
        desktop_card.add_widget(self.release_notify_check)
        body.addWidget(desktop_card)

        telegram_card = SectionCard('Telegram')
        self.telegram_check = QCheckBox('Send updates to Telegram')
        self.telegram_check.toggled.connect(self._on_telegram_toggled)
        telegram_card.add_widget(self.telegram_check)

        telegram_form = QFormLayout()
        self.telegram_token = QLineEdit()
        self.telegram_token.setEchoMode(QLineEdit.Password)
        self.telegram_chat_id = QLineEdit()
        telegram_form.addRow('Bot token:', self.telegram_token)
        telegram_form.addRow('Chat or channel ID:', self.telegram_chat_id)
        telegram_card.add_layout(telegram_form)

        self.telegram_test_button = QPushButton('Send test message')
        self.telegram_test_button.clicked.connect(self._test_telegram)
        telegram_card.add_widget(self.telegram_test_button)

        self.telegram_progress = QCheckBox('Any progress change')
        self.telegram_completed = QCheckBox('Completed titles')
        self.telegram_dropped = QCheckBox('Dropped titles')
        self.telegram_rewatching = QCheckBox('Started rewatching')
        for box in (self.telegram_progress, self.telegram_completed,
                    self.telegram_dropped, self.telegram_rewatching):
            telegram_card.add_widget(box)

        self._telegram_fields = [
            self.telegram_token, self.telegram_chat_id, self.telegram_test_button,
            self.telegram_progress, self.telegram_completed,
            self.telegram_dropped, self.telegram_rewatching,
        ]
        body.addWidget(telegram_card)

        body.addStretch(1)
        return page

    def _network_tab(self) -> QWidget:
        page = ScrollPage()
        body = page.body

        proxy_card = SectionCard('Proxy')
        self.proxy_type = QComboBox()
        for label, key in PROXY_TYPES:
            self.proxy_type.addItem(label, key)
        self.proxy_type.currentIndexChanged.connect(self._on_proxy_type_changed)

        self.proxy_host = QLineEdit()
        self.proxy_port = QLineEdit()
        self.proxy_user = QLineEdit()
        self.proxy_password = QLineEdit()
        self.proxy_password.setEchoMode(QLineEdit.Password)

        proxy_form = QFormLayout()
        proxy_form.addRow('Type:', self.proxy_type)
        proxy_form.addRow('Host:', self.proxy_host)
        proxy_form.addRow('Port:', self.proxy_port)
        proxy_form.addRow('Username:', self.proxy_user)
        proxy_form.addRow('Password:', self.proxy_password)
        proxy_card.add_layout(proxy_form)
        proxy_card.add_widget(hint_label(
            'Username and password are optional. Changes take effect on the next request.'
        ))
        body.addWidget(proxy_card)

        self._proxy_fields = [
            self.proxy_host, self.proxy_port, self.proxy_user, self.proxy_password
        ]
        body.addStretch(1)
        return page

    # -------------------------------------------------------------------- state --

    def _load(self) -> None:
        get = self.config.get

        index = self.service_combo.findData(get('service.active', 'shikimori'))
        self.service_combo.setCurrentIndex(max(index, 0))
        self.mal_client_id.setText(get('mal.client_id', '') or '')
        self.mal_client_secret.setText(get('mal.client_secret', '') or '')

        from core import autostart
        self.startup_check.setChecked(autostart.is_enabled())
        self.auto_monitor_check.setChecked(bool(get('monitoring.auto_start', False)))
        self.auto_update_check.setChecked(bool(get('updates.auto_check', True)))
        self.watch_time_spin.setValue(max(1, int(get('monitoring.min_watch_time', 60)) // 60))

        self.minimize_tray_check.setChecked(bool(get('ui.minimize_to_tray', False)))
        self.close_tray_check.setChecked(bool(get('ui.close_to_tray', False)))

        self.episode_notify_check.setChecked(
            bool(get('notifications.episode_notifications', False)))
        self.release_notify_check.setChecked(
            bool(get('notifications.release_notifications', False)))

        self.telegram_check.setChecked(bool(get('telegram.enabled', False)))
        self.telegram_token.setText(get('telegram.bot_token', '') or '')
        self.telegram_chat_id.setText(get('telegram.chat_id', '') or '')
        self.telegram_progress.setChecked(bool(get('telegram.send_progress', False)))
        self.telegram_completed.setChecked(bool(get('telegram.send_completed', True)))
        self.telegram_dropped.setChecked(bool(get('telegram.send_dropped', False)))
        self.telegram_rewatching.setChecked(bool(get('telegram.send_rewatching', False)))

        index = self.proxy_type.findData(get('proxy.type', 'none'))
        self.proxy_type.setCurrentIndex(max(index, 0))
        self.proxy_host.setText(get('proxy.host', '') or '')
        self.proxy_port.setText(str(get('proxy.port', '') or ''))
        self.proxy_user.setText(get('proxy.username', '') or '')
        self.proxy_password.setText(get('proxy.password', '') or '')

        self._on_service_selection()
        self._on_telegram_toggled(self.telegram_check.isChecked())
        self._on_proxy_type_changed()

    def _save(self) -> None:
        set_value = self.config.set

        previous_service = self.config.get('service.active', 'shikimori')
        new_service = self.service_combo.currentData()

        if not self._apply_autostart():
            return

        set_value('service.active', new_service)
        set_value('mal.client_id', self.mal_client_id.text().strip())
        set_value('mal.client_secret', self.mal_client_secret.text().strip())

        set_value('monitoring.auto_start', self.auto_monitor_check.isChecked())
        set_value('updates.auto_check', self.auto_update_check.isChecked())
        set_value('monitoring.min_watch_time', self.watch_time_spin.value() * 60)

        set_value('ui.minimize_to_tray', self.minimize_tray_check.isChecked())
        set_value('ui.close_to_tray', self.close_tray_check.isChecked())

        set_value('notifications.episode_notifications', self.episode_notify_check.isChecked())
        set_value('notifications.release_notifications', self.release_notify_check.isChecked())

        set_value('telegram.enabled', self.telegram_check.isChecked())
        set_value('telegram.bot_token', self.telegram_token.text().strip())
        set_value('telegram.chat_id', self.telegram_chat_id.text().strip())
        set_value('telegram.send_progress', self.telegram_progress.isChecked())
        set_value('telegram.send_completed', self.telegram_completed.isChecked())
        set_value('telegram.send_dropped', self.telegram_dropped.isChecked())
        set_value('telegram.send_rewatching', self.telegram_rewatching.isChecked())

        set_value('proxy.type', self.proxy_type.currentData())
        set_value('proxy.host', self.proxy_host.text().strip())
        set_value('proxy.port', self.proxy_port.text().strip())
        set_value('proxy.username', self.proxy_user.text().strip())
        set_value('proxy.password', self.proxy_password.text().strip())

        self.controller.schedule_update_check()
        self.accept()

        if new_service != previous_service:
            self.controller.on_service_changed()
        else:
            self.controller.status_message.emit('Settings saved', True)

    def _apply_autostart(self) -> bool:
        from core.autostart import AutostartError, set_enabled

        try:
            set_enabled(self.startup_check.isChecked())
            return True
        except AutostartError as exc:
            QMessageBox.warning(self, 'Startup', str(exc))
            return False

    # ------------------------------------------------------------------ reactions --

    def _on_service_selection(self) -> None:
        self.mal_card.setVisible(self.service_combo.currentData() == 'mal')

    def _on_telegram_toggled(self, enabled: bool) -> None:
        for widget in self._telegram_fields:
            widget.setEnabled(enabled)

    def _on_proxy_type_changed(self) -> None:
        enabled = self.proxy_type.currentData() != 'none'
        for widget in self._proxy_fields:
            widget.setEnabled(enabled)

    def _test_telegram(self) -> None:
        token = self.telegram_token.text().strip()
        chat_id = self.telegram_chat_id.text().strip()
        if not token or not chat_id:
            QMessageBox.information(
                self, 'Telegram', 'Enter both the bot token and the chat ID first.'
            )
            return

        self.telegram_test_button.setEnabled(False)
        self.telegram_test_button.setText('Sending...')

        def work() -> bool:
            import requests

            response = requests.post(
                f'https://api.telegram.org/bot{token}/sendMessage',
                json={'chat_id': chat_id, 'text': 'Anime Updater test message.'},
                timeout=15,
            )
            return response.ok

        def done(ok: bool) -> None:
            self._reset_test_button()
            if ok:
                QMessageBox.information(self, 'Telegram', 'Test message sent.')
            else:
                QMessageBox.warning(
                    self, 'Telegram',
                    'Telegram rejected the message. Check the token and chat ID.',
                )

        def failed(message: str) -> None:
            self._reset_test_button()
            QMessageBox.warning(self, 'Telegram', f'Could not reach Telegram: {message}')

        workers.run_async(work, on_success=done, on_error=failed)

    def _reset_test_button(self) -> None:
        self.telegram_test_button.setEnabled(True)
        self.telegram_test_button.setText('Send test message')


class ScrollPage(QWidget):
    """A tab body that scrolls when the settings do not fit.

    Cards are added to ``body`` rather than to the page's own layout, which
    belongs to the scroll area.
    """

    def __init__(self) -> None:
        super().__init__()
        content = QWidget()
        self.body = QVBoxLayout(content)
        self.body.setContentsMargins(12, 12, 12, 12)
        self.body.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
