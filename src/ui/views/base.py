"""
Shared plumbing for the list views.

Sets up the table, its sort and filter proxy, the header sizing and the context
menu, so each view only has to declare its columns, filters and actions.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence

from PySide6.QtCore import QModelIndex, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QMenu,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ui import workers
from ui.models import Column, EntryFilterProxy, EntryTableModel, RowStyle
from ui.widgets import secondary_label


class ListView(QWidget):
    """A filtered, sortable table of API entries."""

    selection_changed = Signal(object)
    entry_activated = Signal(dict)

    def __init__(self, controller, columns: Sequence[Column],
                 style: Optional[RowStyle] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.controller = controller

        self.model = EntryTableModel(columns, style, self)
        self.proxy = EntryFilterProxy(self)
        self.proxy.setSourceModel(self.model)

        self.table = _build_table(self.proxy, columns)
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(self._on_double_clicked)
        self.table.customContextMenuRequested.connect(self._on_context_menu)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12, 12, 12, 12)
        self.layout.setSpacing(8)

    # -------------------------------------------------------------- selection --

    def selected_entry(self) -> Optional[Dict[str, Any]]:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return None
        return self.proxy.entry(indexes[0])

    def select_first(self) -> None:
        if self.proxy.rowCount():
            self.table.selectRow(0)

    def _on_selection_changed(self, *_args) -> None:
        self.selection_changed.emit(self.selected_entry())

    def _on_double_clicked(self, index: QModelIndex) -> None:
        entry = self.proxy.entry(index)
        if entry is not None:
            self.entry_activated.emit(entry)

    # ----------------------------------------------------------- context menu --

    def _on_context_menu(self, position) -> None:
        index = self.table.indexAt(position)
        if not index.isValid():
            return

        self.table.selectRow(index.row())
        entry = self.proxy.entry(index)
        if entry is None:
            return

        menu = QMenu(self)
        self.build_context_menu(menu, entry)
        if not menu.isEmpty():
            menu.exec(self.table.viewport().mapToGlobal(position))

    def build_context_menu(self, menu: QMenu, entry: Dict[str, Any]) -> None:
        """Populate the right-click menu. Overridden by each view."""

    # ---------------------------------------------------------------- helpers --

    def refresh_entry(self, entry: Dict[str, Any]) -> None:
        self.model.refresh_entry(entry)

    def set_entries(self, entries: Sequence[Dict[str, Any]]) -> None:
        """Replace the rows while keeping the selected entry selected."""
        previous = self.selected_entry()
        self.model.set_entries(entries)
        if previous is not None:
            self.select_entry(previous)

    def select_entry(self, entry: Dict[str, Any]) -> bool:
        row = self.model.row_of(entry)
        if row < 0:
            return False
        proxy_index = self.proxy.mapFromSource(self.model.index(row, 0))
        if not proxy_index.isValid():
            return False
        self.table.selectRow(proxy_index.row())
        return True

    def open_on_service(self, url: str) -> None:
        """Open a title's page, expanding the relative URL the API returns."""
        if not url:
            self.controller.status_message.emit('No page for this title', True)
            return
        if url.startswith('/'):
            url = getattr(self.controller.client, 'SERVICE_URL', '').rstrip('/') + url
        workers.open_url(
            url,
            on_failure=lambda: self.controller.status_message.emit(
                f'Could not open the browser. Link: {url}', True
            ),
        )

    def add_filter_bar(self, *widgets) -> QWidget:
        """Append a row of filter controls above the table."""
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for widget in widgets:
            if widget is None:
                layout.addStretch(1)
            elif isinstance(widget, str):
                layout.addWidget(secondary_label(widget))
            else:
                layout.addWidget(widget)
        self.layout.addWidget(bar)
        return bar

    def apply_filters(self, predicates: Sequence[Callable[[Dict[str, Any]], bool]]) -> None:
        self.proxy.set_predicates(predicates)

    def visible_entries(self) -> List[Dict[str, Any]]:
        return [
            self.proxy.entry(self.proxy.index(row, 0))
            for row in range(self.proxy.rowCount())
        ]


def _build_table(model, columns: Sequence[Column]) -> QTableView:
    table = QTableView()
    # The model has to be attached before the header is configured, otherwise
    # the resize modes are dropped and every column keeps its default width.
    table.setModel(model)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.setSortingEnabled(True)
    table.setWordWrap(False)
    table.setContextMenuPolicy(Qt.CustomContextMenu)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(28)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

    header = table.horizontalHeader()
    header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    header.setHighlightSections(False)
    header.setSortIndicatorShown(True)
    header.setStretchLastSection(False)
    for index, column in enumerate(columns):
        header.setSectionResizeMode(
            index, QHeaderView.Stretch if column.stretch else QHeaderView.Interactive
        )
        if not column.stretch:
            header.resizeSection(index, column.width)

    table.sortByColumn(0, Qt.AscendingOrder)
    return table
