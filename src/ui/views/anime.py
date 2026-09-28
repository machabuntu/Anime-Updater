"""
Anime list tab.

Status tabs with live counters, four filters, and the same six columns as the
tkinter version.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QLineEdit, QMenu, QPushButton, QTabBar, QWidget

from ui.models import Column, RowStyle, TINT_NONE, TINT_UNRELEASED, is_unreleased, year_of
from ui.views.base import ListView
from ui.workers import Debouncer

STATUS_ORDER = ('watching', 'planned', 'completed', 'on_hold', 'dropped', 'rewatching')

TYPES = ('All', 'TV', 'Movie', 'OVA', 'ONA', 'Special', 'Music')

# Label together with the minimum score it admits; "10" means exactly ten,
# which the tkinter version got wrong by parsing the first character.
SCORE_FILTERS = (
    ('All', None),
    ('Not Scored', 0),
    ('1+', 1), ('2+', 2), ('3+', 3), ('4+', 4), ('5+', 5),
    ('6+', 6), ('7+', 7), ('8+', 8), ('9+', 9), ('10', 10),
)

ANIME_COLUMNS = (
    Column('name', 'Anime Name', 300,
           lambda e: e.get('anime', {}).get('name', 'Unknown'), stretch=True),
    Column('status', 'Status', 100, lambda e: _status_label(e)),
    Column('progress', 'Progress', 90,
           lambda e: f"{e.get('episodes', 0)}/{e.get('anime', {}).get('episodes') or '?'}",
           align=Qt.AlignCenter, sort=lambda e: e.get('episodes', 0) or 0),
    Column('score', 'Score', 70,
           lambda e: str(e.get('score') or '-'),
           align=Qt.AlignCenter, sort=lambda e: e.get('score', 0) or 0),
    Column('type', 'Type', 80, lambda e: (e.get('anime', {}).get('kind') or '').upper()),
    Column('year', 'Year', 70,
           lambda e: year_of(e.get('anime', {})),
           align=Qt.AlignCenter,
           sort=lambda e: _year_number(e.get('anime', {}))),
)

_STATUS_LABELS: Dict[str, str] = {}


class AnimeListView(ListView):
    """The user's anime list, one status at a time."""

    def __init__(self, controller, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            controller, ANIME_COLUMNS,
            RowStyle(tint=self._tint_for), parent,
        )
        self._data: Dict[str, List[Dict[str, Any]]] = {}
        self._current_status = STATUS_ORDER[0]
        self._debounce = Debouncer(self._refresh_rows, 150, self)

        self._build_filters()
        self._build_status_tabs()
        self.layout.addWidget(self.table, 1)

        self.entry_activated.connect(self._edit_entry)
        self.refresh_status_labels()

    # ------------------------------------------------------------ construction --

    def _build_filters(self) -> None:
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('Filter by name')
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(lambda _t: self._debounce.trigger())

        self.year_combo = QComboBox()
        self.year_combo.addItem('All')
        self.year_combo.currentIndexChanged.connect(self._refresh_rows)

        self.type_combo = QComboBox()
        self.type_combo.addItems(TYPES)
        self.type_combo.currentIndexChanged.connect(self._refresh_rows)

        self.score_combo = QComboBox()
        for label, threshold in SCORE_FILTERS:
            self.score_combo.addItem(label, threshold)
        self.score_combo.currentIndexChanged.connect(self._refresh_rows)

        clear = QPushButton('Clear All')
        clear.clicked.connect(self._clear_filters)

        self.add_filter_bar(
            'Name:', self.search_input,
            'Year:', self.year_combo,
            'Type:', self.type_combo,
            'Score:', self.score_combo,
            clear, None,
        )
        self.search_input.setMaximumWidth(220)

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
        """Re-read status names, which differ between services."""
        _refresh_status_label_cache(self.controller)
        for index, status in enumerate(STATUS_ORDER):
            self.status_bar.setTabText(index, _status_name(self.controller, status))
        self._update_counters()

    def _refresh_years(self) -> None:
        years = set()
        for entries in self._data.values():
            for entry in entries:
                year = year_of(entry.get('anime', {}))
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

    # ----------------------------------------------------------------- filters --

    def _matches(self, entry: Dict[str, Any]) -> bool:
        anime = entry.get('anime', {})
        if not anime:
            return False

        needle = self.search_input.text().strip().lower()
        if needle and needle not in anime.get('name', '').lower():
            return False

        year = self.year_combo.currentText()
        if year != 'All' and year_of(anime) != year:
            return False

        kind = self.type_combo.currentText()
        if kind != 'All' and (anime.get('kind') or '').upper() != kind.upper():
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
        for widget in (self.year_combo, self.type_combo, self.score_combo):
            widget.blockSignals(True)
            widget.setCurrentIndex(0)
            widget.blockSignals(False)
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)
        self._refresh_rows()

    # ------------------------------------------------------------------ styling --

    def _tint_for(self, entry: Dict[str, Any]) -> str:
        """Highlight titles that are still airing or not out yet."""
        anime_id = entry.get('anime', {}).get('id')
        if anime_id is None:
            return TINT_NONE

        cache = getattr(self.controller.library.matcher, 'detailed_anime_cache', {})
        details = cache.get(anime_id)
        if details and is_unreleased(details.get('status', '')):
            return TINT_UNRELEASED
        return TINT_NONE

    # ----------------------------------------------------------------- actions --

    def build_context_menu(self, menu: QMenu, entry: Dict[str, Any]) -> None:
        from ui.theme import theme

        icon = theme().icon
        service = getattr(self.controller.client, 'SERVICE_NAME', 'the service')
        menu.addAction(icon('external-link'), f'Open on {service}').triggered.connect(
            lambda: self.open_on_service(entry.get('anime', {}).get('url', ''))
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
                lambda _checked=False, s=status: self._set_status(entry, s)
            )
        menu.addSeparator()
        menu.addAction(icon('message-square'), 'Add Comment...').triggered.connect(
            lambda: self._edit_comment(entry)
        )
        menu.addSeparator()
        menu.addAction(icon('trash'), 'Remove from List').triggered.connect(
            lambda: self._remove(entry)
        )

    def _set_status(self, entry: Dict[str, Any], status: str) -> None:
        episodes = 0 if status == 'rewatching' else None
        self.controller.update_anime(entry, status=status, episodes=episodes)

    def _edit_entry(self, entry: Dict[str, Any]) -> None:
        from ui.dialogs.edit import AnimeEditDialog

        dialog = AnimeEditDialog(self.controller, entry, self)
        dialog.exec()

    def _edit_comment(self, entry: Dict[str, Any]) -> None:
        from ui.dialogs.comment import CommentDialog

        name = entry.get('anime', {}).get('name', 'this title')
        current = entry.get('text', '') or entry.get('text_html', '')
        dialog = CommentDialog(name, current, self)
        if dialog.exec():
            self.controller.set_anime_comment(entry, dialog.text())

    def _remove(self, entry: Dict[str, Any]) -> None:
        from PySide6.QtWidgets import QMessageBox

        name = entry.get('anime', {}).get('name', 'this title')
        confirmed = QMessageBox.question(
            self, 'Remove from list', f'Remove "{name}" from your list?'
        ) == QMessageBox.Yes
        if confirmed:
            self.controller.remove_anime(entry)


def _refresh_status_label_cache(controller) -> None:
    _STATUS_LABELS.clear()
    _STATUS_LABELS.update(getattr(controller.client, 'STATUSES', {}))


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
