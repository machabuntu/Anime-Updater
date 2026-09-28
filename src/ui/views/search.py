"""
Search tab.

Looks a title up on the active service and adds it to the list with the chosen
status. Titles already on the list are dimmed so the user can tell at a glance.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QLineEdit, QMenu, QPushButton, QWidget

from ui import workers
from ui.models import Column, RowStyle, year_of
from ui.views.base import ListView

SEARCH_COLUMNS = (
    Column('name', 'Anime Name', 300, lambda e: e.get('name', 'Unknown'), stretch=True),
    Column('type', 'Type', 90, lambda e: (e.get('kind') or '').upper()),
    Column('episodes', 'Episodes', 90,
           lambda e: str(e.get('episodes') or '-'),
           align=Qt.AlignCenter, sort=lambda e: e.get('episodes', 0) or 0),
    Column('year', 'Year', 80, lambda e: year_of(e),
           align=Qt.AlignCenter, sort=lambda e: _year_number(e)),
)


class SearchView(ListView):
    """Find anime on the service and add them to the list."""

    def __init__(self, controller, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            controller, SEARCH_COLUMNS,
            RowStyle(dimmed=self._already_in_list), parent,
        )
        self._searching = False

        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText('Search anime by name')
        self.query_input.setClearButtonEnabled(True)
        self.query_input.returnPressed.connect(self.search)

        self.search_button = QPushButton('Search')
        self.search_button.setProperty('accent', True)
        self.search_button.clicked.connect(self.search)

        self.status_combo = QComboBox()
        self._fill_statuses()

        self.add_button = QPushButton('Add Selected')
        self.add_button.setEnabled(False)
        self.add_button.clicked.connect(self._add_selected)

        self.add_filter_bar(
            self.query_input, self.search_button, None,
            'Add as:', self.status_combo, self.add_button,
        )
        self.layout.addWidget(self.table, 1)

        self.selection_changed.connect(
            lambda entry: self.add_button.setEnabled(entry is not None)
        )
        self.entry_activated.connect(lambda entry: self._add(entry))
        controller.service_changed.connect(self._fill_statuses)

    # ---------------------------------------------------------------- searching --

    def _fill_statuses(self) -> None:
        statuses = getattr(self.controller.client, 'STATUSES', {})
        self.status_combo.clear()
        for key, label in statuses.items():
            self.status_combo.addItem(label, key)
        index = self.status_combo.findData('planned')
        self.status_combo.setCurrentIndex(max(index, 0))

    def search(self) -> None:
        query = self.query_input.text().strip()
        if not query or self._searching:
            return

        self._searching = True
        self.search_button.setEnabled(False)
        self.search_button.setText('Searching...')
        self.controller.status_message.emit(f'Searching for "{query}"...', False)

        def work():
            return self.controller.client.search_anime(query)

        def done(results) -> None:
            self._finish_search()
            self.set_entries(results or [])
            count = len(results or [])
            self.controller.status_message.emit(
                f'{count} result(s) for "{query}"' if count else f'Nothing found for "{query}"',
                True,
            )

        def failed(message: str) -> None:
            self._finish_search()
            self.controller.status_message.emit(f'Search failed: {message}', True)

        workers.run_async(work, on_success=done, on_error=failed)

    def _finish_search(self) -> None:
        self._searching = False
        self.search_button.setEnabled(True)
        self.search_button.setText('Search')

    # ------------------------------------------------------------------ adding --

    def _add_selected(self) -> None:
        entry = self.selected_entry()
        if entry is not None:
            self._add(entry)

    def _add(self, anime: Dict[str, Any], status: Optional[str] = None) -> None:
        anime_id = anime.get('id')
        if anime_id is None:
            return

        status = status or self.status_combo.currentData() or 'planned'
        name = anime.get('name', 'title')
        self.controller.status_message.emit(f'Adding {name}...', False)
        self.controller.add_anime(
            anime_id, status,
            on_done=lambda _ok: self.model.refresh_entry(anime),
        )

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
        menu.addSeparator()
        for key, label in getattr(self.controller.client, 'STATUSES', {}).items():
            menu.addAction(icon('plus'), f'Add as {label}').triggered.connect(
                lambda _checked=False, s=key: self._add(entry, s)
            )


def _year_number(media: Dict[str, Any]) -> int:
    year = year_of(media)
    return int(year) if year.isdigit() else 0
