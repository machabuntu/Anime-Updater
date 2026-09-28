"""
Theme manager.

Applies the token substituted stylesheet to the whole ``QApplication``, which
means switching themes is a single call and reaches every widget, including
dialogs that are already open. The tkinter implementation had to walk the widget
tree by hand and missed several places; nothing here needs that.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from ui.icons import provider as icon_provider
from ui.theme import tokens

_TOKEN_RE = re.compile(r'@([a-z][a-z0-9_]*)')
_COMMENT_RE = re.compile(r'/\*.*?\*/', re.DOTALL)
_COMMENT_RE = re.compile(r'/\*.*?\*/', re.DOTALL)

# Icons referenced from inside the stylesheet. Each entry maps the QSS token
# name to the icon name and the colour token used to paint it.
_QSS_ICONS = {
    'icon_chevron_down': ('chevron-down', 'text_secondary'),
    'icon_chevron_down_muted': ('chevron-down', 'text_disabled'),
    'icon_chevron_up': ('chevron-up', 'text_secondary'),
    'icon_chevron_right': ('chevron-right', 'text_secondary'),
    'icon_check': ('check', 'text_on_accent'),
    'icon_dot': ('dot', 'text_on_accent'),
    'icon_sort_up': ('chevron-up', 'accent'),
    'icon_sort_down': ('chevron-down', 'accent'),
}

THEME_SYSTEM = 'system'
THEME_LIGHT = 'light'
THEME_DARK = 'dark'
THEMES = (THEME_SYSTEM, THEME_LIGHT, THEME_DARK)


class ThemeManager(QObject):
    """Owns the active theme and keeps the application stylesheet in sync."""

    #: Emitted after a new theme has been applied. Widgets that paint themselves
    #: outside of QSS (table row tags, custom delegates) listen to this.
    theme_changed = Signal(bool)

    def __init__(self, app: QApplication, mode: str = THEME_SYSTEM) -> None:
        super().__init__(app)
        self._app = app
        self._mode = mode if mode in THEMES else THEME_SYSTEM
        self._dark = self._resolve_dark(self._mode)
        self._tokens: Dict[str, str] = {}
        self._qss_template = self._load_template()

        QGuiApplication.styleHints().colorSchemeChanged.connect(
            self._on_system_scheme_changed
        )

    # ------------------------------------------------------------- queries --

    @property
    def mode(self) -> str:
        """The configured mode: ``system``, ``light`` or ``dark``."""
        return self._mode

    @property
    def is_dark(self) -> bool:
        """Whether the currently rendered theme is the dark one."""
        return self._dark

    def color(self, token: str) -> str:
        """Look up a colour token, e.g. ``accent`` or ``row_highlight``."""
        return self._tokens.get(token, '#000000')

    def qcolor(self, token: str) -> QColor:
        return QColor(self.color(token))

    def icon(self, name: str, size: int = 16, token: str = 'icon'):
        """Build a themed QIcon that also carries a disabled variant."""
        return icon_provider().icon(
            name,
            self.color(token),
            size,
            disabled_color=self.color('text_disabled'),
        )

    def accent_icon(self, name: str, size: int = 16):
        return icon_provider().icon(name, self.color('accent'), size)

    # ------------------------------------------------------------- mutation --

    def set_mode(self, mode: str) -> None:
        """Switch to a new mode and repaint if the effective theme changed."""
        if mode not in THEMES:
            return
        self._mode = mode
        self.apply()

    def toggle(self) -> str:
        """Flip between light and dark, returning the new mode.

        Toggling from ``system`` picks whichever explicit theme is the opposite
        of what is currently on screen, so the visible result always changes.
        """
        self.set_mode(THEME_LIGHT if self._dark else THEME_DARK)
        return self._mode

    def apply(self) -> None:
        """Rebuild and install the stylesheet for the current mode."""
        dark = self._resolve_dark(self._mode)
        self._dark = dark
        self._tokens = tokens.palette(dark)

        self._app.setStyleSheet(self._render(self._tokens))
        self._apply_palette(self._tokens)
        self.theme_changed.emit(dark)

    def apply_window_frame(self, widget) -> None:
        """Match the Windows title bar to the theme.

        Qt does not follow an application stylesheet for native window
        decorations, so the immersive dark mode flag has to be set directly.
        No-op everywhere except Windows.
        """
        if sys.platform != 'win32':
            return
        try:
            import ctypes

            hwnd = int(widget.winId())
            value = ctypes.c_int(1 if self._dark else 0)
            dwmapi = ctypes.windll.dwmapi
            # DWMWA_USE_IMMERSIVE_DARK_MODE, with the pre-20H1 attribute id as
            # a fallback for older Windows 10 builds.
            for attribute in (20, 19):
                if dwmapi.DwmSetWindowAttribute(
                    hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
                ) == 0:
                    break
        except Exception:
            pass

    # -------------------------------------------------------------- private --

    @staticmethod
    def _load_template() -> str:
        qss_path = Path(__file__).with_name('app.qss')
        source = qss_path.read_text(encoding='utf-8')
        # Comments are dropped up front so that prose mentioning @tokens is not
        # mistaken for a substitution site.
        return _COMMENT_RE.sub('', source)

    def _render(self, palette: Dict[str, str]) -> str:
        values = dict(palette)
        icons = icon_provider()
        for qss_token, (icon_name, color_token) in _QSS_ICONS.items():
            values[qss_token] = icons.stylesheet_asset(
                icon_name, palette.get(color_token, '#000000')
            )

        def substitute(match: re.Match) -> str:
            name = match.group(1)
            if name not in values:
                raise KeyError(f'Unknown style token: @{name}')
            return values[name]

        return _TOKEN_RE.sub(substitute, self._qss_template)

    def _apply_palette(self, palette: Dict[str, str]) -> None:
        """Keep QPalette in sync for widgets Qt paints without the stylesheet.

        Native file dialogs, text cursors and selection colours read QPalette
        rather than QSS, so both have to agree.
        """
        qp = QPalette()

        window = QColor(palette['bg_base'])
        base = QColor(palette['bg_surface'])
        text = QColor(palette['text_primary'])
        disabled = QColor(palette['text_disabled'])
        accent = QColor(palette['accent'])
        on_accent = QColor(palette['text_on_accent'])

        qp.setColor(QPalette.Window, window)
        qp.setColor(QPalette.WindowText, text)
        qp.setColor(QPalette.Base, base)
        qp.setColor(QPalette.AlternateBase, QColor(palette['bg_surface_alt']))
        qp.setColor(QPalette.Text, text)
        qp.setColor(QPalette.Button, base)
        qp.setColor(QPalette.ButtonText, text)
        qp.setColor(QPalette.BrightText, QColor(palette['error']))
        qp.setColor(QPalette.ToolTipBase, QColor(palette['bg_overlay']))
        qp.setColor(QPalette.ToolTipText, text)
        qp.setColor(QPalette.Highlight, accent)
        qp.setColor(QPalette.HighlightedText, on_accent)
        qp.setColor(QPalette.Link, QColor(palette['text_link']))
        qp.setColor(QPalette.LinkVisited, QColor(palette['text_link']))
        qp.setColor(QPalette.PlaceholderText, QColor(palette['text_tertiary']))

        for role in (
            QPalette.WindowText, QPalette.Text, QPalette.ButtonText,
            QPalette.HighlightedText,
        ):
            qp.setColor(QPalette.Disabled, role, disabled)

        self._app.setPalette(qp)

    @staticmethod
    def _resolve_dark(mode: str) -> bool:
        if mode == THEME_DARK:
            return True
        if mode == THEME_LIGHT:
            return False
        scheme = QGuiApplication.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
        # Qt could not determine the desktop preference; light reads better as
        # a neutral default and matches the previous tkinter behaviour.
        return False

    def _on_system_scheme_changed(self, _scheme) -> None:
        if self._mode == THEME_SYSTEM:
            self.apply()


_manager: Optional[ThemeManager] = None


def install(app: QApplication, mode: str = THEME_SYSTEM) -> ThemeManager:
    """Create the process wide theme manager and apply the initial theme."""
    global _manager
    _manager = ThemeManager(app, mode)
    _manager.apply()
    return _manager


def theme() -> ThemeManager:
    """Return the installed theme manager."""
    if _manager is None:
        raise RuntimeError('ThemeManager has not been installed yet')
    return _manager
