"""
Seasonal tab.

Browse a season's line-up, filter it, and add titles straight to Plan to Watch.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QMenu, QPushButton, QSpinBox, QWidget

from ui import workers
from ui.models import (
    Column,
    RowStyle,
    TINT_NONE,
    TINT_UNRELEASED,
    format_status,
    is_unreleased,
)
from ui.views.base import ListView
from ui.widgets import secondary_label

SEASONS = ('Winter', 'Spring', 'Summer', 'Fall')

SORT_OPTIONS_SHIKIMORI = {'Score': 'ranked', 'Popularity': 'popularity', 'Name': 'name'}
SORT_OPTIONS_MAL = {
    'Score': 'anime_score',
    'Popularity': 'anime_num_list_users',
    'Name': '_client_side',
}

KIND_FILTER = {
    'All': None, 'TV': 'tv', 'Movie': 'movie', 'OVA': 'ova',
    'ONA': 'ona', 'Special': 'special', 'Music': 'music',
}

STATUS_FILTER = {
    'All': None,
    'Ongoing': ('ongoing', 'currently_airing'),
    'Finished': ('released', 'finished_airing'),
    'Announced': ('anons', 'not_yet_aired'),
}

LIST_FILTER = {'All': None, 'Not in list': False, 'In list': True}

SEASONAL_COLUMNS = (
    Column('name', 'Name', 350, lambda e: e.get('name', 'Unknown'), stretch=True),
    Column('score', 'Score', 80, lambda e: _score_text(e),
           align=Qt.AlignCenter, sort=lambda e: _score_value(e)),
    Column('type', 'Type', 90, lambda e: (e.get('kind') or '').upper()),
    Column('episodes', 'Ep.', 70, lambda e: str(e.get('episodes') or '-'),
           align=Qt.AlignCenter, sort=lambda e: e.get('episodes', 0) or 0),
    Column('status', 'Status', 110, lambda e: format_status(e.get('status', ''))),
)


class SeasonalView(ListView):
    """Season browser with a one-click Plan to Watch button."""

    def __init__(self, controller, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            controller, SEASONAL_COLUMNS,
            RowStyle(tint=self._tint_for, dimmed=self._already_in_list), parent,
        )
        self._loading = False
        self._build_controls()
        self.layout.addWidget(self.table, 1)
        self._build_footer()

        self.entry_activated.connect(self._add_to_plan)
        self.selection_changed.connect(
            lambda entry: self.add_button.setEnabled(entry is not None)
        )

    # ------------------------------------------------------------ construction --

    def _build_controls(self) -> None:
        now = datetime.datetime.now()

        self.year_spin = QSpinBox()
        self.year_spin.setRange(1970, now.year + 1)
        self.year_spin.setValue(now.year)

        self.season_combo = QComboBox()
        self.season_combo.addItems(SEASONS)
        self.season_combo.setCurrentText(SEASONS[(now.month - 1) // 3])

        self.load_button = QPushButton('Load')
        self.load_button.setProperty('accent', True)
        self.load_button.clicked.connect(self.load_season)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(list(SORT_OPTIONS_SHIKIMORI.keys()))
        self.sort_combo.setCurrentText('Popularity')
        self.sort_combo.currentIndexChanged.connect(self._apply_sort)

        self.add_filter_bar(
            'Year:', self.year_spin,
            'Season:', self.season_combo,
            self.load_button,
            'Sort:', self.sort_combo, None,
        )

        self.kind_combo = _filter_combo(KIND_FILTER)
        self.status_combo = _filter_combo(STATUS_FILTER)
        self.list_combo = _filter_combo(LIST_FILTER)
        for combo in (self.kind_combo, self.status_combo, self.list_combo):
            combo.currentIndexChanged.connect(self._refresh_filters)

        self.add_filter_bar(
            'Type:', self.kind_combo,
            'Status:', self.status_combo,
            'In my list:', self.list_combo, None,
        )

    def _build_footer(self) -> None:
        self.add_button = QPushButton('Add to Plan to Watch')
        self.add_button.setEnabled(False)
        self.add_button.clicked.connect(
            lambda: self._add_to_plan(self.selected_entry())
        )
        self.count_label = secondary_label('Select a season and click Load')
        self.add_filter_bar(self.add_button, self.count_label, None)

    # ------------------------------------------------------------------ loading --

    def load_season(self) -> None:
        if self._loading:
            return

        year = self.year_spin.value()
        season = self.season_combo.currentText()
        sort_label = self.sort_combo.currentText()
        sort_key = self._sort_options().get(sort_label, 'popularity')

        self._loading = True
        self.load_button.setEnabled(False)
        self.load_button.setText('Loading...')
        self.controller.status_message.emit(f'Loading {season} {year}...', False)

        def work():
            return self.controller.client.get_seasonal_anime(
                year, season.lower(), sort=sort_key
            )

        def done(results) -> None:
            self._finish_load()
            self.set_entries(results or [])
            self._apply_sort()
            self.controller.status_message.emit(
                f'{len(results or [])} titles for {season} {year}', True
            )

        def failed(message: str) -> None:
            self._finish_load()
            self.count_label.setText(f'Error: {message}')
            self.controller.status_message.emit(f'Failed to load season: {message}', True)

        workers.run_async(work, on_success=done, on_error=failed)

    def _finish_load(self) -> None:
        self._loading = False
        self.load_button.setEnabled(True)
        self.load_button.setText('Load')

    def _sort_options(self) -> Dict[str, str]:
        service = getattr(self.controller.client, 'SERVICE_NAME', '')
        return SORT_OPTIONS_MAL if service == 'MyAnimeList' else SORT_OPTIONS_SHIKIMORI

    # ----------------------------------------------------------------- filtering --

    def _apply_sort(self) -> None:
        """Map the sort picker onto a column, since the table sorts locally."""
        label = self.sort_combo.currentText()
        if label == 'Name':
            self.table.sortByColumn(0, Qt.AscendingOrder)
        elif label == 'Score':
            self.table.sortByColumn(1, Qt.DescendingOrder)
        self._refresh_filters()

    def _refresh_filters(self) -> None:
        self.apply_filters([self._matches])
        self._update_count()

    def _matches(self, anime: Dict[str, Any]) -> bool:
        kind = self.kind_combo.currentData()
        if kind and (anime.get('kind') or '').lower() != kind:
            return False

        statuses = self.status_combo.currentData()
        if statuses is not None and (anime.get('status') or '').lower() not in statuses:
            return False

        wanted = self.list_combo.currentData()
        if wanted is not None and self._already_in_list(anime) != wanted:
            return False

        return True

    def _update_count(self) -> None:
        shown = self.proxy.rowCount()
        total = self.model.rowCount()
        if shown == total:
            self.count_label.setText(f'{shown} anime')
        else:
            self.count_label.setText(f'{shown} anime shown (of {total} total)')

    # ------------------------------------------------------------------ styling --

    def _tint_for(self, anime: Dict[str, Any]) -> str:
        return TINT_UNRELEASED if is_unreleased(anime.get('status', '')) else TINT_NONE

    def _already_in_list(self, anime: Dict[str, Any]) -> bool:
        anime_id = anime.get('id')
        if anime_id is None:
            return False
        for entry in self.controller.library.all_anime_entries():
            if entry.get('anime', {}).get('id') == anime_id:
                return True
        return False

    # ----------------------------------------------------------------- actions --

    def build_context_menu(self, menu: QMenu, entry: Dict[str, Any]) -> None:
        from ui.theme import theme

        icon = theme().icon
        service = getattr(self.controller.client, 'SERVICE_NAME', 'the service')
        menu.addAction(icon('external-link'), f'Open on {service}').triggered.connect(
            lambda: self.open_on_service(entry.get('url', ''))
        )
        menu.addAction(icon('plus'), 'Add to Plan to Watch').triggered.connect(
            lambda: self._add_to_plan(entry)
        )

    def _add_to_plan(self, anime: Optional[Dict[str, Any]]) -> None:
        if not anime or anime.get('id') is None:
            return
        if self._already_in_list(anime):
            self.controller.status_message.emit('Already on your list', True)
            return

        self.controller.status_message.emit(
            f"Adding {anime.get('name', 'title')}...", False
        )
        self.controller.add_anime(
            anime['id'], 'planned',
            on_done=lambda _ok: self._refresh_filters(),
        )


def _filter_combo(options: Dict[str, Any]) -> QComboBox:
    combo = QComboBox()
    for label, value in options.items():
        combo.addItem(label, value)
    return combo


def _score_text(anime: Dict[str, Any]) -> str:
    value = _score_value(anime)
    return f'{value:.2f}' if value else '-'


def _score_value(anime: Dict[str, Any]) -> float:
    try:
        return float(anime.get('score') or 0)
    except (TypeError, ValueError):
        return 0.0
