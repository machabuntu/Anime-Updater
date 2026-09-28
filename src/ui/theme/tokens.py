"""
Design tokens for the Qt interface.

Every colour, radius and spacing value used by ``app.qss`` lives here. The
stylesheet references tokens as ``@token_name`` and the theme manager performs
the substitution, so a theme switch is a single stylesheet reload.
"""

from __future__ import annotations

import sys
from typing import Dict

LIGHT: Dict[str, str] = {
    # Surfaces, from furthest back to closest to the user
    'bg_base': '#F5F5F7',
    'bg_sunken': '#ECECEF',
    'bg_surface': '#FFFFFF',
    'bg_surface_alt': '#FAFAFB',
    'bg_raised': '#FFFFFF',
    'bg_overlay': '#FFFFFF',

    # Interaction states applied on top of a surface
    'hover': '#F0F0F3',
    'pressed': '#E6E6EA',
    'selected': '#E4EFF9',
    'selected_hover': '#D6E7F6',

    # Accent ramp
    'accent': '#0078D4',
    'accent_hover': '#1A86DE',
    'accent_pressed': '#005FA8',
    'accent_subtle': '#EAF4FD',
    'accent_border': '#0067B8',

    # Text
    'text_primary': '#1A1A1A',
    'text_secondary': '#5C5C5C',
    'text_tertiary': '#8A8A8F',
    'text_disabled': '#ABABB0',
    'text_on_accent': '#FFFFFF',
    'text_link': '#0067B8',

    # Lines
    'border': '#E1E1E4',
    'border_strong': '#C8C8CC',
    'border_focus': '#0078D4',
    'divider': '#E8E8EB',

    # Semantic
    'success': '#0F7B0F',
    'warning': '#C77700',
    'error': '#C42B1C',
    'info': '#0078D4',

    # Scrollbars
    'scrollbar_track': '#00000000',
    'scrollbar_handle': '#C4C4C8',
    'scrollbar_handle_hover': '#A4A4AA',

    # Table row decorations (ported from the tkinter treeview tags)
    'row_highlight': '#DCEBFA',
    'row_muted_text': '#9A9AA0',

    # Icons
    'icon': '#3C3C41',
    'icon_muted': '#75757C',
    'icon_on_accent': '#FFFFFF',
}

DARK: Dict[str, str] = {
    'bg_base': '#1B1B1F',
    'bg_sunken': '#16161A',
    'bg_surface': '#242429',
    'bg_surface_alt': '#202024',
    'bg_raised': '#2A2A31',
    'bg_overlay': '#2A2A31',

    'hover': '#2E2E35',
    'pressed': '#38383F',
    'selected': '#23394C',
    'selected_hover': '#2B455C',

    'accent': '#4CA3E8',
    'accent_hover': '#63B1EE',
    'accent_pressed': '#3B8ACB',
    'accent_subtle': '#1E3550',
    'accent_border': '#5AAEF0',

    'text_primary': '#F2F2F3',
    'text_secondary': '#B4B4BB',
    'text_tertiary': '#8A8A92',
    'text_disabled': '#66666E',
    'text_on_accent': '#0A1A26',
    'text_link': '#6DB6EE',

    'border': '#35353C',
    'border_strong': '#46464F',
    'border_focus': '#4CA3E8',
    'divider': '#303038',

    'success': '#6CCB6C',
    'warning': '#E8B339',
    'error': '#F16C60',
    'info': '#4CA3E8',

    'scrollbar_track': '#00000000',
    'scrollbar_handle': '#4A4A52',
    'scrollbar_handle_hover': '#5E5E68',

    'row_highlight': '#1F3854',
    'row_muted_text': '#7A7A82',

    'icon': '#D8D8DC',
    'icon_muted': '#95959D',
    'icon_on_accent': '#0A1A26',
}

# Shape and spacing are theme independent.
GEOMETRY: Dict[str, str] = {
    'radius_sm': '4px',
    'radius_md': '6px',
    'radius_lg': '8px',
    'radius_pill': '14px',

    'space_xs': '2px',
    'space_sm': '4px',
    'space_md': '8px',
    'space_lg': '12px',
    'space_xl': '16px',

    'control_height': '28px',
    'control_height_lg': '32px',
    'row_height': '28px',
    'header_height': '30px',

    'font_size': '13px',
    'font_size_sm': '12px',
    'font_size_lg': '15px',
    'font_size_title': '19px',
}


def font_family() -> str:
    """Return a platform appropriate UI font stack.

    The tkinter version hardcoded ``Segoe UI``, which does not exist on Linux
    and silently fell back to a bitmap font. Each platform gets its native UI
    face here, with progressively more generic fallbacks.
    """
    if sys.platform == 'win32':
        return '"Segoe UI Variable Text", "Segoe UI", "Noto Sans", sans-serif'
    if sys.platform == 'darwin':
        return '"SF Pro Text", "Helvetica Neue", "Noto Sans", sans-serif'
    return '"Inter", "Noto Sans", "Cantarell", "Ubuntu", "DejaVu Sans", sans-serif'


def palette(dark: bool) -> Dict[str, str]:
    """Return the full token map for one theme, colours plus geometry."""
    tokens = dict(DARK if dark else LIGHT)
    tokens.update(GEOMETRY)
    tokens['font_family'] = font_family()
    return tokens
