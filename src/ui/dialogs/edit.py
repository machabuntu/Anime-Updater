"""
Edit dialogs for a single list entry.

The tkinter build had these classes but never bound them to anything, so the
dialogs were unreachable. Here they open on double click and from the context
menu of both list views.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.widgets import secondary_label, title_label

UNKNOWN_TOTAL = 9999


class _EntryEditDialog(QDialog):
    """Shared scaffolding for the anime and manga editors."""

    def __init__(self, controller, entry: Dict[str, Any], media_key: str,
                 statuses: Dict[str, str], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.entry = entry
        self.media = entry.get(media_key, {})

        self.setWindowTitle('Edit entry')
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        name = self.media.get('name', 'Unknown')
        heading = title_label(name)
        heading.setWordWrap(True)
        layout.addWidget(heading)

        subtitle = ', '.join(part for part in (
            (self.media.get('kind') or '').upper(),
            (self.media.get('aired_on') or '')[:4],
        ) if part)
        if subtitle:
            layout.addWidget(secondary_label(subtitle))

        self.form = QFormLayout()
        self.form.setSpacing(10)
        layout.addLayout(self.form)

        self.status_combo = QComboBox()
        for key, label in statuses.items():
            self.status_combo.addItem(label, key)
        index = self.status_combo.findData(entry.get('status', ''))
        self.status_combo.setCurrentIndex(max(index, 0))
        self.form.addRow('Status:', self.status_combo)

        self.build_fields()

        self.score_combo = QComboBox()
        self.score_combo.addItem('Not scored', 0)
        for value in range(1, 11):
            self.score_combo.addItem(str(value), value)
        index = self.score_combo.findData(entry.get('score', 0) or 0)
        self.score_combo.setCurrentIndex(max(index, 0))
        self.form.addRow('Score:', self.score_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setProperty('accent', True)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def build_fields(self) -> None:
        """Add the media specific progress fields."""

    def _save(self) -> None:
        self.apply_changes()
        self.accept()

    def apply_changes(self) -> None:
        raise NotImplementedError


class AnimeEditDialog(_EntryEditDialog):
    """Episodes, status and score for one anime."""

    def __init__(self, controller, entry: Dict[str, Any],
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(
            controller, entry, 'anime',
            getattr(controller.client, 'STATUSES', {}), parent,
        )

    def build_fields(self) -> None:
        total = self.media.get('episodes', 0) or 0
        self.episodes_spin = QSpinBox()
        self.episodes_spin.setRange(0, total or UNKNOWN_TOTAL)
        self.episodes_spin.setValue(self.entry.get('episodes', 0) or 0)
        self.episodes_spin.setSuffix(f' / {total}' if total else '')
        self.form.addRow('Episodes:', self.episodes_spin)

        self.rewatches_spin = QSpinBox()
        self.rewatches_spin.setRange(0, 999)
        self.rewatches_spin.setValue(self.entry.get('rewatches', 0) or 0)
        self.form.addRow('Rewatches:', self.rewatches_spin)

    def apply_changes(self) -> None:
        status = self.status_combo.currentData()
        self.controller.update_anime(
            self.entry,
            episodes=self.episodes_spin.value(),
            status=status if status != self.entry.get('status') else None,
            score=self.score_combo.currentData(),
            rewatches=self.rewatches_spin.value(),
        )


class MangaEditDialog(_EntryEditDialog):
    """Chapters, volumes, status and score for one manga."""

    def __init__(self, controller, entry: Dict[str, Any],
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(
            controller, entry, 'manga',
            getattr(controller.client, 'MANGA_STATUSES', {}), parent,
        )

    def build_fields(self) -> None:
        total_chapters = self.media.get('chapters', 0) or 0
        self.chapters_spin = QSpinBox()
        self.chapters_spin.setRange(0, total_chapters or UNKNOWN_TOTAL)
        self.chapters_spin.setValue(self.entry.get('chapters', 0) or 0)
        self.chapters_spin.setSuffix(f' / {total_chapters}' if total_chapters else '')
        self.form.addRow('Chapters:', self.chapters_spin)

        total_volumes = self.media.get('volumes', 0) or 0
        self.volumes_spin = QSpinBox()
        self.volumes_spin.setRange(0, total_volumes or UNKNOWN_TOTAL)
        self.volumes_spin.setValue(self.entry.get('volumes', 0) or 0)
        self.volumes_spin.setSuffix(f' / {total_volumes}' if total_volumes else '')
        self.form.addRow('Volumes:', self.volumes_spin)

    def apply_changes(self) -> None:
        status = self.status_combo.currentData()
        self.controller.update_manga(
            self.entry,
            chapters=self.chapters_spin.value(),
            volumes=self.volumes_spin.value(),
            status=status if status != self.entry.get('status') else None,
            score=self.score_combo.currentData(),
        )
