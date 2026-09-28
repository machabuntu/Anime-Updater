"""
OAuth sign-in.

Spins up a throwaway HTTP server on localhost, sends the user to the service's
authorisation page and captures the redirect. The server thread reports back
through a signal, so the dialog never touches widgets off the GUI thread.
"""

from __future__ import annotations

import http.server
import socketserver
import threading
import urllib.parse
from typing import Optional

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui import workers
from ui.widgets import hint_label, secondary_label, title_label
from utils.logger import get_logger

CALLBACK_TIMEOUT_MS = 120_000
CLOSE_DELAY_MS = 800

# Both services validate the redirect URI against the one registered for the
# application, so this port cannot be negotiated at runtime.
CALLBACK_PORT = 8080

_RESULT_PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>
 body {{ font-family: system-ui, sans-serif; background: #f0f2f5; margin: 0;
        display: flex; align-items: center; justify-content: center; height: 100vh; }}
 .card {{ background: #fff; padding: 40px 56px; border-radius: 12px; text-align: center;
        box-shadow: 0 2px 16px rgba(0,0,0,.08); max-width: 480px; }}
 .mark {{ font-size: 48px; color: {colour}; }}
 h1 {{ font-size: 20px; color: {colour}; margin: 16px 0 8px; }}
 p {{ color: #444; line-height: 1.5; margin: 0; }}
</style></head>
<body><div class="card"><div class="mark">{mark}</div><h1>{title}</h1><p>{message}</p></div></body>
</html>"""


def _page(success: bool, message: str) -> bytes:
    return _RESULT_PAGE.format(
        title='Authorisation successful' if success else 'Authorisation failed',
        colour='#28a745' if success else '#dc3545',
        mark='&#10003;' if success else '&#10007;',
        message=message,
    ).encode('utf-8')


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """Handles the single redirect the service sends us."""

    dialog = None

    def do_GET(self) -> None:  # noqa: N802 - name fixed by BaseHTTPRequestHandler
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

        if 'code' in params:
            self._respond(200, _page(
                True, 'You can close this tab and return to the application.'
            ))
            if self.dialog:
                self.dialog.callback_received.emit(params['code'][0], '')
            return

        if 'error' in params:
            error = params.get('error', ['unknown'])[0]
            description = params.get('error_description', [''])[0]
            self._respond(400, _page(False, f'{error}. {description}'))
            if self.dialog:
                self.dialog.callback_received.emit('', f'{error}: {description}'.strip(': '))
            return

        self._respond(400, b'Invalid callback')

    def _respond(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args) -> None:
        """Silence the default stderr access log."""


class AuthDialog(QDialog):
    """Guides the user through the OAuth handshake."""

    callback_received = Signal(str, str)

    def __init__(self, controller, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.config = controller.config
        self.client = controller.client
        self.logger = get_logger('auth')

        self.service_key = getattr(self.client, 'SERVICE_KEY', 'shikimori')
        self.service_name = getattr(self.client, 'SERVICE_NAME', 'Shikimori')

        self._server: Optional[socketserver.TCPServer] = None
        self._port = 0
        self._succeeded = False

        self.setWindowTitle(f'{self.service_name} sign-in')
        self.setMinimumWidth(560)
        self._build()

        self.callback_received.connect(self._on_callback)
        self._timeout = QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.setInterval(CALLBACK_TIMEOUT_MS)
        self._timeout.timeout.connect(self._on_timeout)

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(title_label(f'Sign in to {self.service_name}'))
        layout.addWidget(hint_label(self._instructions()))

        self.status = secondary_label('Ready to start.')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # The link stays visible so sign-in still works when no browser can be
        # launched from here: the user pastes it into one themselves.
        self.link_row = QWidget()
        link_layout = QHBoxLayout(self.link_row)
        link_layout.setContentsMargins(0, 0, 0, 0)
        link_layout.setSpacing(8)
        self.link_field = QLineEdit()
        self.link_field.setReadOnly(True)
        link_layout.addWidget(self.link_field, 1)
        self.copy_button = QPushButton('Copy link')
        self.copy_button.clicked.connect(self._copy_link)
        link_layout.addWidget(self.copy_button)
        self.link_row.setVisible(False)
        layout.addWidget(self.link_row)

        buttons = QHBoxLayout()
        buttons.addStretch(1)

        self.cancel_button = QPushButton('Cancel')
        self.cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.cancel_button)

        self.start_button = QPushButton('Start sign-in')
        self.start_button.setProperty('accent', True)
        self.start_button.clicked.connect(self.start)
        buttons.addWidget(self.start_button)
        layout.addLayout(buttons)

    def _instructions(self) -> str:
        if self.service_key == 'mal':
            return (
                'Your browser opens the MyAnimeList authorisation page. Log in and '
                'choose Allow, and the app captures the result automatically. '
                'The MAL Client ID has to be set in Options first.'
            )
        return (
            'Your browser opens the Shikimori authorisation page. Log in and choose '
            'Authorize, and the app captures the result automatically.'
        )

    # ----------------------------------------------------------------- handshake --

    def start(self) -> None:
        if self.service_key == 'mal' and not self.config.get('mal.client_id', ''):
            self._fail('Set the MAL Client ID in Options before signing in.')
            return

        self.start_button.setEnabled(False)
        self.progress.setVisible(True)
        self.status.setText('Starting the local callback server...')

        try:
            self._start_server()
        except Exception as exc:
            self.logger.exception('Could not start the callback server')
            self._fail(f'Could not start the callback server: {exc}')
            return

        client_id = self.config.get(f'{self.service_key}.client_id')
        redirect_uri = f'http://localhost:{self._port}/callback'

        try:
            auth_url = self.client.get_auth_url(client_id, redirect_uri)
        except Exception as exc:
            self.logger.exception('Could not build the authorisation URL')
            self._fail(f'Could not build the authorisation URL: {exc}')
            return

        self.link_field.setText(auth_url)
        self.link_field.setCursorPosition(0)
        self.link_row.setVisible(True)
        self.status.setText(
            f'Opening {self.service_name} in your browser. Waiting for you to '
            f'authorise the app...'
        )
        self._timeout.start()
        workers.open_url(auth_url, on_failure=self._on_browser_failed)

    def _on_browser_failed(self) -> None:
        if self._server is None:
            return
        self.status.setText(
            'Could not open a browser automatically. Copy the link below, open it '
            'in your browser and authorise the app; this window picks up the '
            'result on its own.'
        )

    def _copy_link(self) -> None:
        QGuiApplication.clipboard().setText(self.link_field.text())
        self.copy_button.setText('Copied')
        QTimer.singleShot(1500, lambda: self.copy_button.setText('Copy link'))

    def _start_server(self) -> None:
        handler = type('BoundCallbackHandler', (_CallbackHandler,), {'dialog': self})
        try:
            self._server = socketserver.TCPServer(('localhost', CALLBACK_PORT), handler)
        except OSError as exc:
            raise RuntimeError(
                f'Port {CALLBACK_PORT} is already in use. The sign-in redirect has to '
                f'arrive on that exact port, so close whatever is holding it and try '
                f'again. ({exc})'
            ) from exc

        self._port = CALLBACK_PORT
        self._server.daemon_threads = True
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        self.logger.info('Callback server listening on port %s', self._port)

    def _stop_server(self) -> None:
        if self._server is None:
            return
        server, self._server = self._server, None
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            self.logger.exception('Error stopping the callback server')

    # ------------------------------------------------------------------ results --

    def _on_callback(self, code: str, error: str) -> None:
        self._timeout.stop()
        if error:
            self._fail(f'Authorisation failed: {error}')
            return

        self.status.setText('Exchanging the code for an access token...')
        client_id = self.config.get(f'{self.service_key}.client_id')
        client_secret = self.config.get(f'{self.service_key}.client_secret', '')
        redirect_uri = f'http://localhost:{self._port}/callback'
        client = self.client

        def work():
            return client.exchange_code_for_token(
                client_id, client_secret, code, redirect_uri
            )

        workers.run_async(work, on_success=self._on_token, on_error=self._fail)

    def _on_token(self, _token) -> None:
        self._succeeded = True
        self._stop_server()
        self.progress.setVisible(False)
        self.link_row.setVisible(False)
        self.status.setText('Signed in. Closing...')
        QTimer.singleShot(CLOSE_DELAY_MS, self.accept)

    def _on_timeout(self) -> None:
        if not self._succeeded:
            self._fail('Timed out waiting for authorisation. Please try again.')

    def _fail(self, message: str) -> None:
        self.logger.error(message)
        self._stop_server()
        self._timeout.stop()
        self.progress.setVisible(False)
        self.link_row.setVisible(False)
        self.start_button.setEnabled(True)
        self.status.setText(message)
        self.status.setObjectName('ErrorLabel')
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def done(self, result: int) -> None:
        self._timeout.stop()
        self._stop_server()
        super().done(result)


