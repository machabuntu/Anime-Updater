"""
Shared widgets used across the interface.

These wrap the small amount of boilerplate that would otherwise repeat in every
view: cards with a heading, controls whose icons follow the theme, and compact
label/field rows.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ui.theme import theme


class ThemedIcon:
    """Keeps a widget's icon in sync with the active theme.

    Icons are raster images baked in a single colour, so they have to be
    re-rendered whenever the palette changes.
    """

    def _init_themed_icon(self, icon_name: Optional[str], size: int = 16,
                          token: str = 'icon') -> None:
        self._icon_name = icon_name
        self._icon_size = size
        self._icon_token = token
        theme().theme_changed.connect(self._refresh_themed_icon)
        self._refresh_themed_icon()

    def set_icon_name(self, icon_name: Optional[str]) -> None:
        self._icon_name = icon_name
        self._refresh_themed_icon()

    def _refresh_themed_icon(self, *_args) -> None:
        if not self._icon_name:
            return
        self.setIcon(theme().icon(self._icon_name, self._icon_size, self._icon_token))
        self.setIconSize(QSize(self._icon_size, self._icon_size))


class IconButton(QPushButton, ThemedIcon):
    """A push button with a themed icon, optionally icon-only."""

    def __init__(self, icon_name: str, text: str = '', parent: Optional[QWidget] = None,
                 accent: bool = False, flat: bool = False, tooltip: str = '',
                 icon_size: int = 16) -> None:
        super().__init__(text, parent)
        if accent:
            self.setProperty('accent', True)
        if flat:
            self.setProperty('flat', True)
        if tooltip:
            self.setToolTip(tooltip)
        if not text:
            self.setFixedWidth(32)
        self.setCursor(Qt.PointingHandCursor)
        self._init_themed_icon(
            icon_name, icon_size, 'icon_on_accent' if accent else 'icon'
        )


class IconToolButton(QToolButton, ThemedIcon):
    """A tool button with a themed icon, used for dropdown menus."""

    def __init__(self, icon_name: str, text: str = '', parent: Optional[QWidget] = None,
                 tooltip: str = '', icon_size: int = 16) -> None:
        super().__init__(parent)
        if text:
            self.setText(text)
            self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        if tooltip:
            self.setToolTip(tooltip)
        self.setCursor(Qt.PointingHandCursor)
        self._init_themed_icon(icon_name, icon_size)


class StepperButton(QPushButton):
    """Small square +/- button for the progress controls."""

    def __init__(self, symbol: str, tooltip: str = '',
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(symbol, parent)
        self.setProperty('stepper', True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        if tooltip:
            self.setToolTip(tooltip)


class Card(QFrame):
    """A surface panel with a border and rounded corners."""

    def __init__(self, parent: Optional[QWidget] = None, margins: int = 12,
                 spacing: int = 8) -> None:
        super().__init__(parent)
        self.setObjectName('Card')
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(margins, margins, margins, margins)
        self._layout.setSpacing(spacing)

    def body(self) -> QVBoxLayout:
        return self._layout

    def add_widget(self, widget: QWidget) -> QWidget:
        self._layout.addWidget(widget)
        return widget

    def add_layout(self, layout: QLayout) -> QLayout:
        self._layout.addLayout(layout)
        return layout


class SectionCard(Card):
    """A card with a heading, replacing the tkinter ``LabelFrame``."""

    def __init__(self, title: str, parent: Optional[QWidget] = None,
                 margins: int = 12, spacing: int = 8) -> None:
        super().__init__(parent, margins, spacing)
        heading = QLabel(title)
        heading.setObjectName('HeadingLabel')
        self._layout.addWidget(heading)
        self._heading = heading

    def set_title(self, title: str) -> None:
        self._heading.setText(title)


class FieldRow(QWidget):
    """A ``label: control`` row with a fixed width label column."""

    def __init__(self, label: str, field: QWidget, label_width: int = 0,
                 parent: Optional[QWidget] = None, stretch_field: bool = True) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.label = QLabel(label)
        if label_width:
            self.label.setMinimumWidth(label_width)
        layout.addWidget(self.label)
        layout.addWidget(field, 1 if stretch_field else 0)
        if not stretch_field:
            layout.addStretch(1)

        self.field = field


def hline(parent: Optional[QWidget] = None) -> QFrame:
    """A one pixel horizontal divider."""
    line = QFrame(parent)
    line.setFrameShape(QFrame.HLine)
    line.setFrameShadow(QFrame.Plain)
    line.setFixedHeight(1)
    return line


def vline(parent: Optional[QWidget] = None) -> QFrame:
    """A one pixel vertical divider, used between toolbar groups."""
    line = QFrame(parent)
    line.setFrameShape(QFrame.VLine)
    line.setFrameShadow(QFrame.Plain)
    line.setFixedWidth(1)
    line.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
    return line


def secondary_label(text: str = '', parent: Optional[QWidget] = None) -> QLabel:
    label = QLabel(text, parent)
    label.setObjectName('SecondaryLabel')
    return label


def hint_label(text: str = '', parent: Optional[QWidget] = None) -> QLabel:
    label = QLabel(text, parent)
    label.setObjectName('HintLabel')
    label.setWordWrap(True)
    return label


def title_label(text: str = '', parent: Optional[QWidget] = None) -> QLabel:
    label = QLabel(text, parent)
    label.setObjectName('TitleLabel')
    return label


def row(*widgets, spacing: int = 8, stretch_last: bool = False) -> QHBoxLayout:
    """Build a horizontal layout from widgets, layouts or ``None`` for a spacer."""
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    for item in widgets:
        if item is None:
            layout.addStretch(1)
        elif isinstance(item, QLayout):
            layout.addLayout(item)
        else:
            layout.addWidget(item)
    if stretch_last:
        layout.setStretch(layout.count() - 1, 1)
    return layout
