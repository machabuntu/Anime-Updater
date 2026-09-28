"""Dialogs used by the main window."""

from ui.dialogs.auth import AuthDialog
from ui.dialogs.comment import CommentDialog
from ui.dialogs.edit import AnimeEditDialog, MangaEditDialog
from ui.dialogs.logs import LogViewerDialog
from ui.dialogs.options import OptionsDialog
from ui.dialogs.update import UpdateDialog

__all__ = [
    'AnimeEditDialog',
    'AuthDialog',
    'CommentDialog',
    'LogViewerDialog',
    'MangaEditDialog',
    'OptionsDialog',
    'UpdateDialog',
]
