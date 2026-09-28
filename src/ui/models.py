"""
Table models for the four list views.

The tkinter code rebuilt an entire ``Treeview`` on every keystroke in a filter
box and re-implemented column sorting three times over. A model with a sort and
filter proxy in front of it gets both for free and only repaints the rows that
are actually on screen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt

from ui.theme import theme

ENTRY_ROLE = Qt.UserRole + 1
SORT_ROLE = Qt.UserRole + 2

# Titles that have not finished airing get a tinted row; entries already on the
# user's list are dimmed in the seasonal and search views.
TINT_UNRELEASED = 'unreleased'
TINT_NONE = ''

RELEASED_STATUSES = ('released', 'finished_airing')


@dataclass(frozen=True)
class Column:
    """One table column: how to label it, size it and read it from an entry."""

    key: str
    title: str
    width: int
    display: Callable[[Dict[str, Any]], str]
    align: Qt.AlignmentFlag = Qt.AlignLeft | Qt.AlignVCenter
    sort: Optional[Callable[[Dict[str, Any]], Any]] = None
    stretch: bool = False

    def sort_key(self, entry: Dict[str, Any]) -> Any:
        if self.sort is not None:
            return self.sort(entry)
        return self.display(entry).lower()


@dataclass
class RowStyle:
    """Optional per-row decoration supplied by the view."""

    tint: Callable[[Dict[str, Any]], str] = field(default=lambda _entry: TINT_NONE)
    dimmed: Callable[[Dict[str, Any]], bool] = field(default=lambda _entry: False)


class EntryTableModel(QAbstractTableModel):
    """Exposes a flat list of API entries through a column specification."""

    def __init__(self, columns: Sequence[Column], style: Optional[RowStyle] = None,
                 parent=None) -> None:
        super().__init__(parent)
        self._columns = list(columns)
        self._entries: List[Dict[str, Any]] = []
        self._style = style or RowStyle()
        theme().theme_changed.connect(self._repaint)

    # ------------------------------------------------------------------- data --

    def set_entries(self, entries: Sequence[Dict[str, Any]]) -> None:
        self.beginResetModel()
        self._entries = list(entries)
        self.endResetModel()

    def entries(self) -> List[Dict[str, Any]]:
        return self._entries

    def entry(self, row: int) -> Optional[Dict[str, Any]]:
        if 0 <= row < len(self._entries):
            return self._entries[row]
        return None

    def row_of(self, entry: Dict[str, Any]) -> int:
        for row, candidate in enumerate(self._entries):
            if candidate is entry or candidate.get('id') == entry.get('id'):
                return row
        return -1

    def refresh_entry(self, entry: Dict[str, Any]) -> None:
        """Repaint a single row after an in-place edit."""
        row = self.row_of(entry)
        if row < 0:
            return
        self._entries[row] = entry
        self.dataChanged.emit(
            self.index(row, 0), self.index(row, len(self._columns) - 1)
        )

    def columns(self) -> List[Column]:
        return self._columns

    # ------------------------------------------------------- QAbstractTableModel --

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._entries)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None

        entry = self._entries[index.row()]
        column = self._columns[index.column()]

        if role == Qt.DisplayRole:
            return column.display(entry)
        if role == Qt.TextAlignmentRole:
            return int(column.align)
        if role == SORT_ROLE:
            return column.sort_key(entry)
        if role == ENTRY_ROLE:
            return entry
        if role == Qt.BackgroundRole:
            tint = self._style.tint(entry)
            if tint == TINT_UNRELEASED:
                return theme().qcolor('row_highlight')
            return None
        if role == Qt.ForegroundRole:
            if self._style.dimmed(entry):
                return theme().qcolor('text_disabled')
            return None
        if role == Qt.ToolTipRole and column.stretch:
            return column.display(entry)
        return None

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.DisplayRole) -> Any:
        if orientation != Qt.Horizontal:
            return None
        if role == Qt.DisplayRole:
            return self._columns[section].title
        if role == Qt.TextAlignmentRole:
            return int(self._columns[section].align)
        return None

    def _repaint(self) -> None:
        """Row tints come from the palette, so they follow theme changes."""
        if not self._entries:
            return
        self.dataChanged.emit(
            self.index(0, 0),
            self.index(len(self._entries) - 1, len(self._columns) - 1),
            [Qt.BackgroundRole, Qt.ForegroundRole],
        )


Predicate = Callable[[Dict[str, Any]], bool]


class EntryFilterProxy(QSortFilterProxyModel):
    """Filters rows through a list of predicates and sorts on the model's keys."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSortRole(SORT_ROLE)
        self.setDynamicSortFilter(True)
        self._predicates: List[Predicate] = []

    def set_predicates(self, predicates: Sequence[Predicate]) -> None:
        self._predicates = list(predicates)
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, parent: QModelIndex) -> bool:
        model = self.sourceModel()
        entry = model.entry(source_row) if isinstance(model, EntryTableModel) else None
        if entry is None:
            return True
        return all(predicate(entry) for predicate in self._predicates)

    def entry(self, proxy_index: QModelIndex) -> Optional[Dict[str, Any]]:
        if not proxy_index.isValid():
            return None
        source = self.mapToSource(proxy_index)
        model = self.sourceModel()
        if isinstance(model, EntryTableModel):
            return model.entry(source.row())
        return None


# ------------------------------------------------------------------ formatters --

def title_of(entry: Dict[str, Any], key: str) -> str:
    return entry.get(key, {}).get('name', 'Unknown')


def year_of(media: Dict[str, Any]) -> str:
    aired = media.get('aired_on') or media.get('released_on') or ''
    return aired[:4] if len(aired) >= 4 else '-'


def score_text(entry: Dict[str, Any]) -> str:
    score = entry.get('score', 0) or 0
    return str(score) if score else '-'


def is_unreleased(status: str) -> bool:
    status = (status or '').lower()
    return bool(status) and status not in RELEASED_STATUSES


def format_status(raw: str) -> str:
    """Normalise the differing status vocabularies of the two services."""
    mapping = {
        'released': 'Finished',
        'finished_airing': 'Finished',
        'ongoing': 'Ongoing',
        'currently_airing': 'Ongoing',
        'anons': 'Announced',
        'not_yet_aired': 'Announced',
    }
    raw = (raw or '').lower()
    return mapping.get(raw, raw.replace('_', ' ').title() if raw else '-')
