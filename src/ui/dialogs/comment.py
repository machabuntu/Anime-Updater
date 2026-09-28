"""Editor for the review text attached to a list entry."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.widgets import hint_label, title_label


class CommentDialog(QDialog):
    """Multi-line editor for an entry's comment."""

    def __init__(self, title: str, text: str = '',
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle('Comment')
        self.setMinimumSize(520, 380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        layout.addWidget(title_label(f'Comment for {title}'))
        layout.addWidget(hint_label(
            'Shown on your profile next to this title.'
        ))

        self.editor = QPlainTextEdit(text)
        self.editor.setPlaceholderText('Write your thoughts...')
        layout.addWidget(self.editor, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Save).setProperty('accent', True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def text(self) -> str:
        return self.editor.toPlainText().strip()
