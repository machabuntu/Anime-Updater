"""Update notification with in-place download and install."""

from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QProgressBar,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui import workers
from ui.widgets import secondary_label, title_label
from utils.logger import get_logger
from utils.version import get_version_info

INSTALL_SETTLE_MS = 2000


class _ProgressBridge(QObject):
    """Carries progress from the updater's thread into the GUI thread."""

    progressed = Signal(float)


class UpdateDialog(QDialog):
    """Shows what changed and can install the new build."""

    def __init__(self, info: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.info = info
        self.logger = get_logger('update_dialog')
        self._installing = False

        self.setWindowTitle('Update available')
        self.setMinimumSize(520, 440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        layout.addWidget(title_label('A new version is available'))

        versions = QFormLayout()
        versions.setSpacing(6)
        versions.addRow('Installed:', QLabel(str(info.get('current_version', '?'))))
        latest = QLabel(str(info.get('latest_version', '?')))
        latest.setObjectName('SuccessLabel')
        versions.addRow('Latest:', latest)
        layout.addLayout(versions)

        notes = info.get('release_notes')
        if notes:
            layout.addWidget(secondary_label("What's new"))
            viewer = QPlainTextEdit(notes)
            viewer.setReadOnly(True)
            layout.addWidget(viewer, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status = secondary_label('')
        layout.addWidget(self.status)

        buttons = QDialogButtonBox()
        self.github_button = QPushButton('View on GitHub')
        self.github_button.clicked.connect(self._open_github)
        buttons.addButton(self.github_button, QDialogButtonBox.HelpRole)

        self.install_button = QPushButton('Update Now')
        self.install_button.setProperty('accent', True)
        self.install_button.clicked.connect(self._install)
        buttons.addButton(self.install_button, QDialogButtonBox.AcceptRole)

        later = QPushButton('Later')
        later.clicked.connect(self.reject)
        buttons.addButton(later, QDialogButtonBox.RejectRole)
        layout.addWidget(buttons)

        self._bridge = _ProgressBridge(self)
        self._bridge.progressed.connect(self._on_progress, Qt.QueuedConnection)

    # ---------------------------------------------------------------- installing --

    def _install(self) -> None:
        if self._installing:
            return

        self._installing = True
        self.install_button.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.status.setText('Downloading update...')

        info = self.info
        emit = self._bridge.progressed.emit

        def work() -> None:
            from utils.updater import UpdateChecker

            version = get_version_info()
            checker = UpdateChecker(version['github_repo'], version['version'])
            if info.get('download_url'):
                checker.updater.download_url = info['download_url']
                checker.updater.latest_version = info.get('latest_version')
                checker.updater.release_notes = info.get('release_notes', '')
            checker.download_and_install(emit)

        workers.run_async(work, on_error=self._on_failed)

    def _on_progress(self, value: float) -> None:
        self.progress.setValue(int(value))
        if value >= 100:
            self.status.setText('Installing, the app will restart...')
        elif value >= 85:
            self.status.setText('Extracting update...')

    def _on_failed(self, message: str) -> None:
        self.logger.error('Update failed: %s', message)
        self._installing = False
        self.install_button.setEnabled(True)
        self.progress.setVisible(False)
        self.status.setText(f'Update failed: {message}')

    def _open_github(self) -> None:
        repo = get_version_info()['github_repo']
        url = f'https://github.com/{repo}/releases/latest'
        workers.open_url(
            url, on_failure=lambda: self.status.setText(f'Could not open the browser: {url}')
        )
