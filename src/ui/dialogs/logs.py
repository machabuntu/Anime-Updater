"""Read-only viewer for the application log file."""

from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFontDatabase, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.widgets import secondary_label

REFRESH_MS = 2000

# Reading only the tail keeps a long-running session's log from freezing the
# dialog; the interesting lines are always at the end anyway.
TAIL_BYTES = 512 * 1024


class LogViewerDialog(QDialog):
    """Shows the log file, optionally following it as it grows."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle('Application logs')
        self.resize(900, 620)

        from utils.logger import get_log_file_path
        self.log_path = get_log_file_path()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(secondary_label(f'Log file: {self.log_path}'))

        self.viewer = QPlainTextEdit()
        self.viewer.setReadOnly(True)
        self.viewer.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.viewer.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        layout.addWidget(self.viewer, 1)

        controls = QHBoxLayout()
        controls.setSpacing(8)

        self.follow_box = QCheckBox('Follow')
        self.follow_box.setChecked(True)
        self.follow_box.toggled.connect(self._on_follow_toggled)
        controls.addWidget(self.follow_box)

        refresh = QPushButton('Refresh')
        refresh.clicked.connect(self.reload)
        controls.addWidget(refresh)

        controls.addStretch(1)

        close = QPushButton('Close')
        close.clicked.connect(self.accept)
        controls.addWidget(close)
        layout.addLayout(controls)

        self._timer = QTimer(self)
        self._timer.setInterval(REFRESH_MS)
        self._timer.timeout.connect(self.reload)
        self._timer.start()

        self.reload()

    def reload(self) -> None:
        text = self._read_tail()
        if text == self.viewer.toPlainText():
            return

        at_bottom = self.follow_box.isChecked()
        self.viewer.setPlainText(text)
        if at_bottom:
            self.viewer.moveCursor(QTextCursor.End)

    def _read_tail(self) -> str:
        if not self.log_path or not os.path.exists(self.log_path):
            return 'No log file yet.'

        try:
            size = os.path.getsize(self.log_path)
            with open(self.log_path, 'rb') as handle:
                if size > TAIL_BYTES:
                    handle.seek(size - TAIL_BYTES)
                    handle.readline()  # drop the partial first line
                raw = handle.read()
            return raw.decode('utf-8', errors='replace')
        except OSError as exc:
            return f'Could not read the log file: {exc}'

    def _on_follow_toggled(self, enabled: bool) -> None:
        if enabled:
            self._timer.start()
            self.reload()
        else:
            self._timer.stop()

    def closeEvent(self, event) -> None:
        self._timer.stop()
        super().closeEvent(event)
