"""
Theme aware icon set.

Icon geometry is stored inline as SVG markup rather than as data files so that
frozen PyInstaller builds need no extra bundled resources and no runtime path
resolution. Every icon is stroked in a single colour supplied by the caller,
which lets the same source recolour itself when the theme changes.

Paths follow the Lucide icon geometry (MIT licensed): 24x24 viewBox, 2px
stroke, round caps and joins.
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_STROKE_ICONS: Dict[str, str] = {
    'chevron-down': '<path d="m6 9 6 6 6-6"/>',
    'chevron-up': '<path d="m18 15-6-6-6 6"/>',
    'chevron-right': '<path d="m9 18 6-6-6-6"/>',
    'chevron-left': '<path d="m15 18-6-6 6-6"/>',
    'check': '<path d="M20 6 9 17l-5-5"/>',
    'x': '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    'menu': '<path d="M4 6h16"/><path d="M4 12h16"/><path d="M4 18h16"/>',
    'plus': '<path d="M5 12h14"/><path d="M12 5v14"/>',
    'minus': '<path d="M5 12h14"/>',
    'search': '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    'refresh': (
        '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/>'
        '<path d="M21 3v5h-5"/>'
        '<path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/>'
        '<path d="M8 16H3v5"/>'
    ),
    'play': '<path d="M6 4.5v15l13-7.5z"/>',
    'stop': '<rect x="5" y="5" width="14" height="14" rx="2"/>',
    'settings': (
        '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0'
        'l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51'
        'a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08'
        'a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18'
        'a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39'
        'a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09'
        'a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25'
        'a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>'
    ),
    'key': (
        '<path d="m15.5 7.5 2.3 2.3a1 1 0 0 0 1.4 0l2.1-2.1a1 1 0 0 0 0-1.4L19 4"/>'
        '<path d="m21 2-9.6 9.6"/><circle cx="7.5" cy="15.5" r="5.5"/>'
    ),
    'log-out': (
        '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>'
        '<path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>'
    ),
    'moon': '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z"/>',
    'sun': (
        '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/>'
        '<path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/>'
        '<path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/>'
        '<path d="m19.07 4.93-1.41 1.41"/>'
    ),
    'monitor': (
        '<rect width="20" height="14" x="2" y="3" rx="2"/>'
        '<path d="M8 21h8"/><path d="M12 17v4"/>'
    ),
    'file-text': (
        '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z"/>'
        '<path d="M14 2v5h6"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/>'
    ),
    'download': (
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
        '<path d="M7 10l5 5 5-5"/><path d="M12 15V3"/>'
    ),
    'trash': (
        '<path d="M3 6h18"/>'
        '<path d="M19 6l-.8 14a2 2 0 0 1-2 1.9H7.8a2 2 0 0 1-2-1.9L5 6"/>'
        '<path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'
    ),
    'external-link': (
        '<path d="M15 3h6v6"/><path d="M10 14 21 3"/>'
        '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>'
    ),
    'message-square': '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    'pencil': (
        '<path d="M21.2 2.8a2.7 2.7 0 0 0-3.8 0l-11 11L5 19l5.2-1.4 11-11a2.7 2.7 0 0 0 0-3.8z"/>'
        '<path d="m15 5 4 4"/>'
    ),
    'list': (
        '<path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/>'
        '<path d="M3 6h.01"/><path d="M3 12h.01"/><path d="M3 18h.01"/>'
    ),
    'book-open': (
        '<path d="M12 7v14"/>'
        '<path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5'
        'a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>'
    ),
    'calendar': (
        '<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/>'
        '<path d="M8 2v4"/><path d="M16 2v4"/>'
    ),
    'database': (
        '<ellipse cx="12" cy="5" rx="9" ry="3"/>'
        '<path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/>'
    ),
    'filter-x': (
        '<path d="M13.013 3H2l8 9.46V19l4 2v-8.54l.9-1.055"/>'
        '<path d="m22 3-5 5"/><path d="m17 3 5 5"/>'
    ),
    'info': (
        '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>'
    ),
    'power': '<path d="M12 2v10"/><path d="M18.4 6.6a9 9 0 1 1-12.77.04"/>',
    'eye': (
        '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7z"/>'
        '<circle cx="12" cy="12" r="3"/>'
    ),
    'folder-open': (
        '<path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.55 6'
        'a2 2 0 0 1-1.94 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2'
        'a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"/>'
    ),
}

_FILLED_ICONS: Dict[str, str] = {
    'dot': '<circle cx="12" cy="12" r="5"/>',
}


def available_icons() -> tuple:
    """Return every icon name this provider can render."""
    return tuple(sorted({*_STROKE_ICONS, *_FILLED_ICONS}))


def _svg_source(name: str, color: str, stroke_width: float) -> str:
    if name in _FILLED_ICONS:
        body = _FILLED_ICONS[name]
        style = f'fill="{color}" stroke="none"'
    else:
        try:
            body = _STROKE_ICONS[name]
        except KeyError:
            raise KeyError(f"Unknown icon: {name!r}") from None
        style = (
            f'fill="none" stroke="{color}" stroke-width="{stroke_width}" '
            'stroke-linecap="round" stroke-linejoin="round"'
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'width="24" height="24" {style}>{body}</svg>'
    )


class IconProvider:
    """Renders the inline SVG set into pixmaps and on-disk stylesheet assets."""

    def __init__(self) -> None:
        self._pixmaps: Dict[tuple, QPixmap] = {}
        self._assets: Dict[tuple, str] = {}
        self._asset_dir: Optional[Path] = None

    def pixmap(self, name: str, color: str, size: int = 16,
               stroke_width: float = 2.0, ratio: float = 1.0) -> QPixmap:
        """Render an icon, caching by every parameter that affects the result."""
        key = (name, color, size, stroke_width, round(ratio, 2))
        cached = self._pixmaps.get(key)
        if cached is not None:
            return cached

        source = _svg_source(name, color, stroke_width)
        renderer = QSvgRenderer(QByteArray(source.encode('utf-8')))

        physical = max(1, int(round(size * ratio)))
        pixmap = QPixmap(physical, physical)
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        renderer.render(painter, QRectF(0, 0, physical, physical))
        painter.end()

        self._pixmaps[key] = pixmap
        return pixmap

    def icon(self, name: str, color: str, size: int = 16,
             disabled_color: Optional[str] = None,
             stroke_width: float = 2.0) -> QIcon:
        """Build a QIcon with normal and, optionally, disabled variants."""
        result = QIcon()
        for scale in (1.0, 2.0):
            result.addPixmap(
                self.pixmap(name, color, size, stroke_width, scale),
                QIcon.Normal,
            )
            if disabled_color:
                result.addPixmap(
                    self.pixmap(name, disabled_color, size, stroke_width, scale),
                    QIcon.Disabled,
                )
        return result

    def stylesheet_asset(self, name: str, color: str, size: int = 16,
                         stroke_width: float = 2.0) -> str:
        """Write an icon to disk and return a path usable in a QSS ``url()``.

        Qt stylesheets can only reference images by path, so theme aware icons
        used inside QSS (combo box arrows, check marks, sort indicators) are
        materialised as PNG files once per theme and colour.
        """
        key = (name, color, size, stroke_width)
        cached = self._assets.get(key)
        if cached is not None:
            return cached

        if self._asset_dir is None:
            self._asset_dir = Path(tempfile.mkdtemp(prefix='shikimori-icons-'))

        digest = hashlib.sha1(
            f'{name}:{color}:{size}:{stroke_width}'.encode('utf-8')
        ).hexdigest()[:12]
        path = self._asset_dir / f'{name}-{digest}.png'

        if not path.exists():
            # Render at 2x so the image stays crisp on HiDPI screens; QSS scales
            # it down to the width/height declared in the rule.
            pixmap = self.pixmap(name, color, size * 2, stroke_width)
            pixmap.save(str(path), 'PNG')

        # QSS url() needs forward slashes even on Windows.
        asset_path = path.as_posix()
        self._assets[key] = asset_path
        return asset_path


_provider: Optional[IconProvider] = None


def provider() -> IconProvider:
    """Return the process wide icon provider."""
    global _provider
    if _provider is None:
        _provider = IconProvider()
    return _provider
