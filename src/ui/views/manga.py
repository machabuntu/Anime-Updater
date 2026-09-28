"""
Manga list tab.

Same shape as the anime tab with five statuses, a chapters and volumes pair of
columns and no type filter.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QLineEdit, QMenu, QPushButton, QTabBar, QWidget

from ui.models import Column, year_of
from ui.views.anime import SCORE_FILTERS
from ui.views.base import ListView
from ui.workers import Debouncer

STATUS_ORDER = ('watching', 'planned', 'completed', 'on_hold', 'dropped')

MANGA_COLUMNS = (
    Column('name', 'Manga Name', 300,
           lambda e: e.get('manga', {}).get('name', 'Unknown'), stretch=True),
    Column('status', 'Status', 120, lambda e: _status_label(e)),
    Column('chapters', 'Chapters', 100,
           lambda e: f"{e.get('chapters', 0)}/{e.get('manga', {}).get('chapters') or '?'}",
           align=Qt.AlignCenter, sort=lambda e: e.get('chapters', 0) or 0),
    Column('volumes', 'Volumes', 100,
           lambda e: f"{e.get('volumes', 0)}/{e.get('manga', {}).get('volumes') or '?'}",
           align=Qt.AlignCenter, sort=lambda e: e.get('volumes', 0) or 0),
    Column('score', 'Score', 80,
           lambda e: str(e.get('score') or '-'),
           align=Qt.AlignCenter, sort=lambda e: e.get('score', 0) or 0),
    Column('year', 'Year', 80,
           lambda e: year_of(e.get('manga', {})),
           align=Qt.AlignCenter,
           sort=lambda e: _year_number(e.get('manga', {}))),
)

_STATUS_LABELS: Dict[str, str] = {}


class MangaListView(ListView):
    """The user's manga list, one status at a time."""

    def __init__(self, controller, parent: Optional[QWidget] = None) -> None:
        super().__init__(controller, MANGA_COLUMNS, None, parent)
        self._data: Dict[str, List[Dict[str, Any]]] = {}
        self._current_status = STATUS_ORDER[0]
        self._debounce = Debouncer(self._refresh_rows, 150, self)

        self._build_filters()
        self._build_status_tabs()
        self.layout.addWidget(self.table, 1)

        self.entry_activated.connect(self._edit_entry)
        self.refresh_status_labels()

    def _build_filters(self) -> None:
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('Filter by name')
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMaximumWidth(220)
        self.search_input.textChanged.connect(lambda _t: self._debounce.trigger())

        self.year_combo = QComboBox()
        self.year_combo.addItem('All')
        self.year_combo.currentIndexChanged.connect(self._refresh_rows)

        self.score_combo = QComboBox()
        for label, threshold in SCORE_FILTERS:
            self.score_combo.addItem(label, threshold)
        self.score_combo.currentIndexChanged.connect(self._refresh_rows)

        clear = QPushButton('Clear All')
        clear.clicked.connect(self._clear_filters)

        self.add_filter_bar(
            'Search:', self.search_input,
            'Year:', self.year_combo,
            'Score:', self.score_combo,
            clear, None,
        )

    def _build_status_tabs(self) -> None:
        self.status_bar = QTabBar()
        self.status_bar.setExpanding(False)
        self.status_bar.setDrawBase(False)
        for status in STATUS_ORDER:
            self.status_bar.addTab(_status_name(self.controller, status))
        self.status_bar.currentChanged.connect(self._on_status_tab_changed)
        self.layout.addWidget(self.status_bar)

    # -------------------------------------------------------------------- data --

    def set_data(self, data: Dict[str, List[Dict[str, Any]]]) -> None:
        self._data = data or {}
        _refresh_status_label_cache(self.controller)
        self._refresh_years()
        self._refresh_rows()

    def clear(self) -> None:
        self.set_data({})

    def refresh_status_labels(self) -> None:
        _refresh_status_label_cache(self.controller)
        for index, status in enumerate(STATUS_ORDER):
            self.status_bar.setTabText(index, _status_name(self.controller, status))
        self._update_counters()

    def _refresh_years(self) -> None:
        years = set()
        for entries in self._data.values():
            for entry in entries:
                year = year_of(entry.get('manga', {}))
                if year != '-':
                    years.add(year)

        current = self.year_combo.currentText()
        self.year_combo.blockSignals(True)
        self.year_combo.clear()
        self.year_combo.addItem('All')
        self.year_combo.addItems(sorted(years, reverse=True))
        index = self.year_combo.findText(current)
        self.year_combo.setCurrentIndex(max(index, 0))
        self.year_combo.blockSignals(False)

    def _on_status_tab_changed(self, index: int) -> None:
        if 0 <= index < len(STATUS_ORDER):
            self._current_status = STATUS_ORDER[index]
            self._refresh_rows()

    def _refresh_rows(self) -> None:
        self.set_entries(self._data.get(self._current_status, []))
        self.apply_filters([self._matches])
        self._update_counters()

    def _update_counters(self) -> None:
        for index, status in enumerate(STATUS_ORDER):
            entries = self._data.get(status, [])
            count = sum(1 for entry in entries if self._matches(entry))
            self.status_bar.setTabText(
                index, f'{_status_name(self.controller, status)} [{count}]'
            )

    def _matches(self, entry: Dict[str, Any]) -> bool:
        manga = entry.get('manga', {})
        if not manga:
            return False

        needle = self.search_input.text().strip().lower()
        if needle and needle not in manga.get('name', '').lower():
            return False

        year = self.year_combo.currentText()
        if year != 'All' and year_of(manga) != year:
            return False

        threshold = self.score_combo.currentData()
        if threshold is not None:
            score = entry.get('score', 0) or 0
            if threshold == 0:
                if score > 0:
                    return False
            elif score < threshold:
                return False

        return True

    def _clear_filters(self) -> None:
        for widget in (self.year_combo, self.score_combo):
            widget.blockSignals(True)
            widget.setCurrentIndex(0)
            widget.blockSignals(False)
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)
        self._refresh_rows()

    # ----------------------------------------------------------------- actions --

    def build_context_menu(self, menu: QMenu, entry: Dict[str, Any]) -> None:
        from ui.theme import theme

        icon = theme().icon
        service = getattr(self.controller.client, 'SERVICE_NAME', 'the service')
        menu.addAction(icon('external-link'), f'Open on {service}').triggered.connect(
            lambda: self.open_on_service(entry.get('manga', {}).get('url', ''))
        )
        menu.addSeparator()
        menu.addAction(icon('pencil'), 'Edit...').triggered.connect(
            lambda: self._edit_entry(entry)
        )
        menu.addSeparator()

        for status in STATUS_ORDER:
            if status == entry.get('status'):
                continue
            label = _status_name(self.controller, status)
            menu.addAction(icon('list'), f'Mark as {label}').triggered.connect(
                lambda _checked=False, s=status: self.controller.update_manga(entry, status=s)
            )
        menu.addSeparator()
        menu.addAction(icon('message-square'), 'Add Comment...').triggered.connect(
            lambda: self._edit_comment(entry)
        )
        menu.addSeparator()
        menu.addAction(icon('trash'), 'Remove from List').triggered.connect(
            lambda: self._remove(entry)
        )

    def _edit_entry(self, entry: Dict[str, Any]) -> None:
        from ui.dialogs.edit import MangaEditDialog

        MangaEditDialog(self.controller, entry, self).exec()

    def _edit_comment(self, entry: Dict[str, Any]) -> None:
        from ui.dialogs.comment import CommentDialog

        name = entry.get('manga', {}).get('name', 'this title')
        current = entry.get('text', '') or entry.get('text_html', '')
        dialog = CommentDialog(name, current, self)
        if dialog.exec():
            self.controller.set_manga_comment(entry, dialog.text())

    def _remove(self, entry: Dict[str, Any]) -> None:
        from PySide6.QtWidgets import QMessageBox

        name = entry.get('manga', {}).get('name', 'this title')
        confirmed = QMessageBox.question(
            self, 'Remove from list', f'Remove "{name}" from your list?'
        ) == QMessageBox.Yes
        if confirmed:
            self.controller.remove_manga(entry)


def _refresh_status_label_cache(controller) -> None:
    _STATUS_LABELS.clear()
    _STATUS_LABELS.update(getattr(controller.client, 'MANGA_STATUSES', {}))


def _status_name(controller, status: str) -> str:
    if not _STATUS_LABELS:
        _refresh_status_label_cache(controller)
    return _STATUS_LABELS.get(status, status.replace('_', ' ').title())


def _status_label(entry: Dict[str, Any]) -> str:
    status = entry.get('status', '')
    return _STATUS_LABELS.get(status, status.replace('_', ' ').title())


def _year_number(media: Dict[str, Any]) -> int:
    year = year_of(media)
    return int(year) if year.isdigit() else 0
