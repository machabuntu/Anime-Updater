"""
Compact panel for the currently selected title.

Sits in the toolbar and mirrors the three row layout of the tkinter version:
the title name, a progress stepper, and the status and score pickers. It
switches between anime and manga, where the progress row becomes chapters and a
volumes stepper appears next to it.

The panel only reports intent through signals; the controller performs the
update and calls back into ``show_anime`` / ``show_manga`` with fresh data.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.widgets import StepperButton, secondary_label

NO_SELECTION = 'No title selected'
NO_VALUE = '-'

# The tkinter panel fell back to this when a title had no episode count, so
# ongoing series stayed editable.
UNKNOWN_TOTAL = 9999

MODE_ANIME = 'anime'
MODE_MANGA = 'manga'


class SelectionPanel(QWidget):
    """Read-out and quick editor for the selected list entry."""

    episodes_changed = Signal(int)
    volumes_changed = Signal(int)
    status_changed = Signal(str)
    score_changed = Signal(int)

    def __init__(self, anime_statuses: Dict[str, str], manga_statuses: Dict[str, str],
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._anime_statuses = dict(anime_statuses)
        self._manga_statuses = dict(manga_statuses)
        self._entry: Optional[Dict[str, Any]] = None
        self._mode = MODE_ANIME
        # Suppresses signals while the widgets are being filled in.
        self._loading = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._build_name_row())
        layout.addWidget(self._build_progress_row())
        layout.addWidget(self._build_status_row())

        self.set_statuses(self._anime_statuses, self._manga_statuses)
        # Volumes only apply to manga, so they start hidden.
        for widget in self.volume_widgets:
            widget.setVisible(False)
        self.clear()

    # ------------------------------------------------------------ construction --

    def _build_name_row(self) -> QWidget:
        self.name_label = QLabel(NO_SELECTION)
        self.name_label.setObjectName('HeadingLabel')
        self.name_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        return self.name_label

    def _build_progress_row(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.progress_label = secondary_label('Ep:')
        self.progress_down = StepperButton('\u2212', 'One less episode')
        self.progress_spin = _progress_spin()
        self.progress_total = secondary_label('/?')
        self.progress_up = StepperButton('+', 'One more episode')

        self.progress_down.clicked.connect(lambda: self._step(self.progress_spin, -1))
        self.progress_up.clicked.connect(lambda: self._step(self.progress_spin, 1))
        self.progress_spin.editingFinished.connect(self._emit_progress)

        for widget in (self.progress_label, self.progress_down, self.progress_spin,
                       self.progress_total, self.progress_up):
            layout.addWidget(widget)

        self.volume_widgets = []
        self.volume_label = secondary_label('Vol:')
        self.volume_down = StepperButton('\u2212', 'One less volume')
        self.volume_spin = _progress_spin()
        self.volume_total = secondary_label('/?')
        self.volume_up = StepperButton('+', 'One more volume')

        self.volume_down.clicked.connect(lambda: self._step(self.volume_spin, -1))
        self.volume_up.clicked.connect(lambda: self._step(self.volume_spin, 1))
        self.volume_spin.editingFinished.connect(self._emit_volumes)

        layout.addSpacing(8)
        for widget in (self.volume_label, self.volume_down, self.volume_spin,
                       self.volume_total, self.volume_up):
            layout.addWidget(widget)
            self.volume_widgets.append(widget)

        layout.addStretch(1)
        return container

    def _build_status_row(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.status_combo = QComboBox()
        self.status_combo.setMinimumWidth(130)
        self.status_combo.currentIndexChanged.connect(self._emit_status)

        self.score_combo = QComboBox()
        self.score_combo.setMinimumWidth(64)
        self.score_combo.addItem(NO_VALUE, 0)
        for value in range(1, 11):
            self.score_combo.addItem(str(value), value)
        self.score_combo.currentIndexChanged.connect(self._emit_score)

        layout.addWidget(secondary_label('Status:'))
        layout.addWidget(self.status_combo)
        layout.addSpacing(8)
        layout.addWidget(secondary_label('Score:'))
        layout.addWidget(self.score_combo)
        layout.addStretch(1)
        return container

    # ------------------------------------------------------------------- state --

    def set_statuses(self, anime_statuses: Dict[str, str],
                     manga_statuses: Dict[str, str]) -> None:
        """Refresh the status choices, e.g. after switching service."""
        self._anime_statuses = dict(anime_statuses)
        self._manga_statuses = dict(manga_statuses)
        self._fill_statuses()

    def _fill_statuses(self) -> None:
        statuses = self._anime_statuses if self._mode == MODE_ANIME else self._manga_statuses
        self._loading = True
        self.status_combo.clear()
        self.status_combo.addItem(NO_VALUE, '')
        for key, label in statuses.items():
            self.status_combo.addItem(label, key)
        self._loading = False

    def clear(self) -> None:
        """Return to the empty state and disable the controls."""
        self._entry = None
        self._loading = True

        self.name_label.setText(NO_SELECTION)
        self.progress_spin.setRange(0, UNKNOWN_TOTAL)
        self.progress_spin.setValue(0)
        self.progress_total.setText('/?')
        self.volume_spin.setRange(0, UNKNOWN_TOTAL)
        self.volume_spin.setValue(0)
        self.volume_total.setText('/?')
        self.status_combo.setCurrentIndex(0)
        self.score_combo.setCurrentIndex(0)

        self._loading = False
        self._set_enabled(False)

    def show_anime(self, entry: Optional[Dict[str, Any]]) -> None:
        if entry is None:
            self.clear()
            return

        self._set_mode(MODE_ANIME)
        anime = entry.get('anime', {})
        self._populate(
            entry,
            name=anime.get('name', 'Unknown'),
            progress=entry.get('episodes', 0),
            total=anime.get('episodes', 0),
            status=entry.get('status', ''),
            score=entry.get('score', 0),
        )

    def show_manga(self, entry: Optional[Dict[str, Any]]) -> None:
        if entry is None:
            self.clear()
            return

        self._set_mode(MODE_MANGA)
        manga = entry.get('manga', {})
        self._populate(
            entry,
            name=manga.get('name', 'Unknown'),
            progress=entry.get('chapters', 0),
            total=manga.get('chapters', 0),
            status=entry.get('status', ''),
            score=entry.get('score', 0),
        )

        total_volumes = manga.get('volumes', 0) or 0
        self._loading = True
        self.volume_spin.setRange(0, total_volumes or UNKNOWN_TOTAL)
        self.volume_spin.setValue(entry.get('volumes', 0) or 0)
        self.volume_total.setText(f'/{total_volumes or "?"}')
        self._loading = False

    @property
    def entry(self) -> Optional[Dict[str, Any]]:
        return self._entry

    @property
    def mode(self) -> str:
        return self._mode

    # -------------------------------------------------------------- internals --

    def _populate(self, entry: Dict[str, Any], name: str, progress: int, total: int,
                  status: str, score: int) -> None:
        self._entry = entry
        self._loading = True

        self.name_label.setText(name)
        self.name_label.setToolTip(name)

        total = total or 0
        self.progress_spin.setRange(0, total or UNKNOWN_TOTAL)
        self.progress_spin.setValue(progress or 0)
        self.progress_total.setText(f'/{total or "?"}')

        index = self.status_combo.findData(status)
        self.status_combo.setCurrentIndex(index if index >= 0 else 0)

        index = self.score_combo.findData(score or 0)
        self.score_combo.setCurrentIndex(index if index >= 0 else 0)

        self._loading = False
        self._set_enabled(True)

    def _set_mode(self, mode: str) -> None:
        if mode == self._mode:
            return

        self._mode = mode
        is_manga = mode == MODE_MANGA
        self.progress_label.setText('Ch:' if is_manga else 'Ep:')
        for widget in self.volume_widgets:
            widget.setVisible(is_manga)
        self._fill_statuses()

    def _set_enabled(self, enabled: bool) -> None:
        for widget in (self.progress_label, self.progress_down, self.progress_spin,
                       self.progress_total, self.progress_up,
                       self.status_combo, self.score_combo, *self.volume_widgets):
            widget.setEnabled(enabled)

    def _step(self, spin: QSpinBox, delta: int) -> None:
        """Nudge a stepper and commit straight away, as the buttons imply intent."""
        new_value = max(spin.minimum(), min(spin.maximum(), spin.value() + delta))
        if new_value == spin.value():
            return
        spin.setValue(new_value)
        if spin is self.progress_spin:
            self._emit_progress()
        else:
            self._emit_volumes()

    def _emit_progress(self) -> None:
        if self._loading or self._entry is None:
            return
        current = (self._entry.get('episodes', 0) if self._mode == MODE_ANIME
                   else self._entry.get('chapters', 0))
        if self.progress_spin.value() != (current or 0):
            self.episodes_changed.emit(self.progress_spin.value())

    def _emit_volumes(self) -> None:
        if self._loading or self._entry is None:
            return
        if self.volume_spin.value() != (self._entry.get('volumes', 0) or 0):
            self.volumes_changed.emit(self.volume_spin.value())

    def _emit_status(self) -> None:
        if self._loading or self._entry is None:
            return
        status = self.status_combo.currentData()
        if status and status != self._entry.get('status', ''):
            self.status_changed.emit(status)

    def _emit_score(self) -> None:
        if self._loading or self._entry is None:
            return
        score = self.score_combo.currentData() or 0
        if score != (self._entry.get('score', 0) or 0):
            self.score_changed.emit(score)


def _progress_spin() -> QSpinBox:
    """A narrow spin box; stepping is done by the adjacent buttons."""
    spin = QSpinBox()
    spin.setButtonSymbols(QSpinBox.NoButtons)
    spin.setAlignment(Qt.AlignCenter)
    spin.setFixedWidth(56)
    spin.setKeyboardTracking(False)
    spin.setRange(0, UNKNOWN_TOTAL)
    return spin
