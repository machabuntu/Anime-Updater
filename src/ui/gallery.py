"""
Style gallery.

A developer-only window that renders one of every themed widget so the
stylesheet can be reviewed in both themes without signing in. Not reachable
from the normal UI; launch with ``python main.py --gallery``.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableView,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ui.theme import theme
from ui.widgets import IconButton, SectionCard


class GalleryWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle('Style Gallery')
        self.resize(980, 720)

        tabs = QTabWidget()
        tabs.addTab(self._controls_tab(), 'Controls')
        tabs.addTab(self._table_tab(), 'Table')
        self.setCentralWidget(tabs)

        toolbar = self.addToolBar('Main')
        toolbar.setMovable(False)
        toggle = QPushButton('Toggle theme')
        toggle.clicked.connect(self._toggle_theme)
        toolbar.addWidget(toggle)

        self.statusBar().addWidget(QLabel('Ready'))

    def _toggle_theme(self) -> None:
        theme().toggle()

    def _controls_tab(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        title = QLabel('Typography and buttons')
        title.setObjectName('TitleLabel')
        outer.addWidget(title)

        for name, text in (
            ('HeadingLabel', 'Heading label'),
            ('SecondaryLabel', 'Secondary label'),
            ('HintLabel', 'Hint label, used for notes under a field'),
            ('SuccessLabel', 'Success label'),
            ('WarningLabel', 'Warning label'),
            ('ErrorLabel', 'Error label'),
        ):
            label = QLabel(text)
            label.setObjectName(name)
            outer.addWidget(label)

        buttons = SectionCard('Buttons')
        row = QHBoxLayout()
        row.setSpacing(8)
        default = QPushButton('Default')
        accent = QPushButton('Accent')
        accent.setProperty('accent', True)
        disabled = QPushButton('Disabled')
        disabled.setEnabled(False)
        flat = QPushButton('Flat')
        flat.setProperty('flat', True)
        minus = QPushButton('\u2212')
        minus.setProperty('stepper', True)
        plus = QPushButton('+')
        plus.setProperty('stepper', True)
        icon_button = IconButton('refresh', 'Refresh')
        tool = QToolButton()
        tool.setText('Menu')
        tool.setIcon(theme().icon('menu'))
        tool.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        tool.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(tool)
        menu.addAction(theme().icon('key'), 'Authentication...')
        menu.addSeparator()
        menu.addAction(theme().icon('settings'), 'Options...')
        action = menu.addAction('Checkable item')
        action.setCheckable(True)
        action.setChecked(True)
        menu.addAction(theme().icon('log-out'), 'Exit')
        tool.setMenu(menu)

        for widget in (default, accent, disabled, flat, minus, plus, icon_button, tool):
            row.addWidget(widget)
        row.addStretch(1)
        buttons.add_layout(row)
        outer.addWidget(buttons)

        inputs = SectionCard('Inputs')
        grid = QHBoxLayout()
        grid.setSpacing(8)
        line = QLineEdit()
        line.setPlaceholderText('Search by name')
        combo = QComboBox()
        combo.addItems(['All', 'TV', 'Movie', 'OVA', 'ONA', 'Special'])
        spin = QSpinBox()
        spin.setRange(0, 9999)
        spin.setValue(12)
        disabled_combo = QComboBox()
        disabled_combo.addItems(['Disabled'])
        disabled_combo.setEnabled(False)
        for widget in (line, combo, spin, disabled_combo):
            grid.addWidget(widget)
        inputs.add_layout(grid)
        outer.addWidget(inputs)

        toggles = SectionCard('Toggles and progress')
        checks = QVBoxLayout()
        checked = QCheckBox('Enabled checkbox')
        checked.setChecked(True)
        checks.addWidget(checked)
        checks.addWidget(QCheckBox('Unchecked checkbox'))
        off = QCheckBox('Disabled checkbox')
        off.setEnabled(False)
        checks.addWidget(off)
        radio = QRadioButton('Radio button')
        radio.setChecked(True)
        checks.addWidget(radio)
        checks.addWidget(QRadioButton('Another radio'))
        bar = QProgressBar()
        bar.setValue(62)
        bar.setTextVisible(False)
        checks.addWidget(bar)
        text_bar = QProgressBar()
        text_bar.setValue(38)
        text_bar.setTextVisible(True)
        checks.addWidget(text_bar)
        toggles.add_layout(checks)
        outer.addWidget(toggles)

        group = QGroupBox('Plain group box')
        group_layout = QVBoxLayout(group)
        editor = QTextEdit()
        editor.setPlainText('Multi-line text area used by the comment dialog.')
        editor.setMaximumHeight(80)
        group_layout.addWidget(editor)
        outer.addWidget(group)

        outer.addStretch(1)
        return page

    def _table_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)

        model = QStandardItemModel()
        headers = ['Anime Name', 'Status', 'Progress', 'Score', 'Type', 'Year']
        model.setHorizontalHeaderLabels(headers)

        rows = [
            ('Frieren: Beyond Journey\u2019s End', 'Watching', '17/28', '10', 'TV', '2023'),
            ('Mushishi', 'Completed', '26/26', '9', 'TV', '2005'),
            ('Ping Pong the Animation', 'Completed', '11/11', '9', 'TV', '2014'),
            ('Monogatari Series: Off & Monster', 'Plan to Watch', '0/?', '-', 'TV', '2024'),
            ('Look Back', 'Completed', '1/1', '8', 'Movie', '2024'),
        ]
        highlight = theme().qcolor('row_highlight')
        for index, row in enumerate(rows):
            items = [QStandardItem(value) for value in row]
            for column, item in enumerate(items):
                item.setEditable(False)
                if column in (2, 3, 5):
                    item.setTextAlignment(Qt.AlignCenter)
                if index == 3:
                    item.setBackground(highlight)
            model.appendRow(items)

        table = QTableView()
        table.setModel(model)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableView.SelectRows)
        table.setSelectionMode(QTableView.SingleSelection)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setSortingEnabled(True)
        header = table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        table.selectRow(0)
        layout.addWidget(table)
        return page
