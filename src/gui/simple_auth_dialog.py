"""
Simplified Authentication Dialog for OAuth
Supports Shikimori and MyAnimeList with automatic callback capture.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
import threading
import http.server
import socketserver
import socket
import urllib.parse
import time
from gui.modern_style import ModernStyle
from utils.logger import get_logger


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback"""
    
    def __init__(self, *args, auth_dialog=None, **kwargs):
        self.auth_dialog = auth_dialog
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET request for OAuth callback"""
        try:
            parsed_url = urllib.parse.urlparse(self.path)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            
            if 'code' in query_params:
                auth_code = query_params['code'][0]
                
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                
                success_html = """
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>Authorization Successful</title>
                    <style>
                        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f0f2f5; }
                        .container { max-width: 600px; margin: 0 auto; background: white; padding: 40px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                        .success { color: #28a745; font-size: 24px; margin-bottom: 20px; }
                        .message { color: #333; font-size: 16px; line-height: 1.5; }
                        .checkmark { font-size: 48px; color: #28a745; margin-bottom: 20px; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="checkmark">&#10003;</div>
                        <div class="success">Authorization Successful!</div>
                        <div class="message">
                            You have successfully authorized Anime Updater.<br>
                            You can now close this browser tab and return to the application.
                        </div>
                    </div>
                </body>
                </html>
                """
                
                self.wfile.write(success_html.encode())
                
                if self.auth_dialog:
                    self.auth_dialog.handle_callback_success(auth_code)
                    
            elif 'error' in query_params:
                error = query_params.get('error', ['unknown'])[0]
                error_description = query_params.get('error_description', ['Unknown error'])[0]
                
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                
                error_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>Authorization Failed</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f0f2f5; }}
                        .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 40px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                        .error {{ color: #dc3545; font-size: 24px; margin-bottom: 20px; }}
                        .message {{ color: #333; font-size: 16px; line-height: 1.5; }}
                        .x-mark {{ font-size: 48px; color: #dc3545; margin-bottom: 20px; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="x-mark">&#10007;</div>
                        <div class="error">Authorization Failed</div>
                        <div class="message">
                            Error: {error}<br>
                            {error_description}<br><br>
                            Please close this tab and try again in the application.
                        </div>
                    </div>
                </body>
                </html>
                """
                
                self.wfile.write(error_html.encode())
                
                if self.auth_dialog:
                    self.auth_dialog.handle_callback_error(error, error_description)
            else:
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"Invalid callback")
                
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Internal server error")
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        pass


class SimpleAuthDialog:
    """Service-aware OAuth dialog supporting Shikimori and MyAnimeList."""
    
    def __init__(self, parent, config, api_client):
        self.parent = parent
        self.config = config
        self.api_client = api_client
        self.service_key = getattr(api_client, 'SERVICE_KEY', 'shikimori')
        self.service_name = getattr(api_client, 'SERVICE_NAME', 'Shikimori')
        self.logger = get_logger('auth')
        self.callback_server = None
        self.callback_thread = None
        self.callback_port = 8080
        self.auth_success = False
        self._dialog_width = 600
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"{self.service_name} Authentication")
        self.dialog.geometry(f"{self._dialog_width}x100")
        self.dialog.resizable(True, True)
        self.dialog.minsize(500, 300)
        
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        dark_theme = config.get('ui.dark_theme', False)
        self.modern_style = ModernStyle(self.dialog, dark_theme=dark_theme)
        self.dialog.after(100, self.modern_style._apply_title_bar_theme)
        
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        self._create_widgets()
    
    def _get_instructions(self) -> str:
        if self.service_key == 'mal':
            return (
                "This app will handle the MyAnimeList OAuth authentication process.\n\n"
                "1. Click 'Start Authentication' below\n"
                "2. Your browser will open to MyAnimeList's authorization page\n"
                "3. Log in to MyAnimeList and click 'Allow'\n"
                "4. The app will automatically capture the authorization and complete setup\n\n"
                "Note: You must first configure your MAL Client ID in Options."
            )
        return (
            "This app will automatically handle the OAuth authentication process.\n\n"
            "1. Click 'Start Authentication' below\n"
            "2. Your browser will open to Shikimori's authorization page\n"
            "3. Log in to Shikimori and click 'Authorize'\n"
            "4. The app will automatically capture the authorization and complete setup\n\n"
            "Note: The app uses pre-configured client credentials for simplicity."
        )

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title_label = ttk.Label(main_frame, text=f"{self.service_name} Authentication",
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        instructions_frame = ttk.LabelFrame(main_frame, text="How it works", padding="15")
        instructions_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.instructions_label = ttk.Label(instructions_frame, text=self._get_instructions(),
                                            wraplength=450, justify=tk.LEFT)
        self.instructions_label.pack()
        
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="15")
        status_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.status_var = tk.StringVar(value="Ready to start authentication")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var,
                                     wraplength=450, justify=tk.LEFT)

        self.status_label.pack()
        
        self.progress = ttk.Progressbar(status_frame, mode='indeterminate')
        self.progress.pack(fill=tk.X, pady=(10, 0))
        
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(20, 0))
        
        self.cancel_button = ttk.Button(buttons_frame, text="Cancel",
                                       command=self._on_closing)
        self.cancel_button.pack(side=tk.RIGHT, padx=(10, 0))
        
        self.auth_button = ttk.Button(buttons_frame, text="Start Authentication",
                                     command=self._start_authentication)
        self.auth_button.pack(side=tk.RIGHT)
        
        self.dialog.after(1, self._set_dynamic_size)
    
    def _find_available_port(self, start_port=8080, max_attempts=10):
        for port in range(start_port, start_port + max_attempts):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('localhost', port))
                    return port
            except OSError:
                continue
        raise RuntimeError("Could not find an available port for callback server")
    
    def _start_callback_server(self):
        try:
            self.callback_port = self._find_available_port()
            
            def handler_factory(*args, **kwargs):
                return CallbackHandler(*args, auth_dialog=self, **kwargs)
            
            self.callback_server = socketserver.TCPServer(
                ('localhost', self.callback_port),
                handler_factory
            )
            
            self.logger.info(f"Callback server started on port {self.callback_port}")
            
            self.callback_thread = threading.Thread(
                target=self.callback_server.serve_forever,
                daemon=True
            )
            self.callback_thread.start()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start callback server: {e}")
            self.dialog.after(0, lambda: self._update_status(
                f"Error: Could not start callback server: {str(e)}", error=True
            ))
            return False
    
    def _stop_callback_server(self):
        if self.callback_server:
            try:
                self.callback_server.shutdown()
                self.callback_server.server_close()
                self.logger.info("Callback server stopped")
            except Exception as e:
                self.logger.error(f"Error stopping callback server: {e}")
            finally:
                self.callback_server = None
                self.callback_thread = None
    
    def _start_authentication(self):
        """Start the OAuth authentication process"""
        if self.service_key == 'mal':
            client_id = self.config.get('mal.client_id', '')
            if not client_id:
                self._update_status(
                    "MAL Client ID is not configured. Please set it in Options first.", error=True)
                return

        self.auth_button.config(state=tk.DISABLED)
        self.progress.start()
        self._update_status("Starting callback server...")
        
        def start_auth_process():
            try:
                if not self._start_callback_server():
                    return
                
                self.dialog.after(0, lambda: self._update_status(
                    "Callback server started. Opening browser..."
                ))
                
                client_id = self.config.get(f'{self.service_key}.client_id')
                redirect_uri = f"http://localhost:{self.callback_port}/callback"
                
                auth_url = self.api_client.get_auth_url(client_id, redirect_uri)
                
                self.dialog.after(0, lambda: self._update_status(
                    f"Opening browser for authorization. Please log in to {self.service_name} and authorize the app."
                ))
                
                webbrowser.open(auth_url)
                
                def timeout_check():
                    time.sleep(120)
                    if not self.auth_success and self.callback_server:
                        self.dialog.after(0, lambda: self._handle_timeout())
                
                threading.Thread(target=timeout_check, daemon=True).start()
                
            except Exception as e:
                self.dialog.after(0, lambda: self._update_status(
                    f"Error starting authentication: {str(e)}", error=True
                ))
                self.dialog.after(0, self._reset_ui)
        
        threading.Thread(target=start_auth_process, daemon=True).start()
    
    def handle_callback_success(self, auth_code):
        self.logger.info(f"Received authorization code: {auth_code[:10]}...")
        
        self.dialog.after(0, lambda: self._update_status(
            "Authorization code received. Exchanging for access token..."
        ))
        
        def exchange_token():
            try:
                client_id = self.config.get(f'{self.service_key}.client_id')
                client_secret = self.config.get(f'{self.service_key}.client_secret', '')
                redirect_uri = f"http://localhost:{self.callback_port}/callback"
                
                token_data = self.api_client.exchange_code_for_token(
                    client_id, client_secret, auth_code, redirect_uri
                )
                
                self.auth_success = True
                
                self.dialog.after(0, lambda: self._update_status(
                    "Authentication successful! Closing..."
                ))
                
                self.dialog.after(1000, self._close_success)
                
            except Exception as e:
                error_msg = str(e)
                self.logger.error(f"Token exchange failed: {error_msg}")
                
                self.dialog.after(0, lambda: self._update_status(
                    f"Authentication failed: {error_msg}", error=True
                ))
                self.dialog.after(0, self._reset_ui)
        
        threading.Thread(target=exchange_token, daemon=True).start()
    
    def handle_callback_error(self, error, error_description):
        self.logger.error(f"OAuth error: {error} - {error_description}")
        
        self.dialog.after(0, lambda: self._update_status(
            f"Authorization failed: {error} - {error_description}", error=True
        ))
        self.dialog.after(0, self._reset_ui)
    
    def _handle_timeout(self):
        if not self.auth_success:
            self._update_status(
                "Authentication timed out. Please try again.", error=True
            )
            self._reset_ui()
    
    def _update_status(self, message, error=False):
        self.status_var.set(message)
        if error:
            try:
                self.status_label.config(foreground='red')
            except:
                pass
        else:
            try:
                self.status_label.config(foreground='')
            except:
                pass
    
    def _reset_ui(self):
        self.progress.stop()
        self.auth_button.config(state=tk.NORMAL)
        self._stop_callback_server()
    
    def _close_success(self):
        self._stop_callback_server()
        self.dialog.destroy()
    
    def _on_closing(self):
        self._stop_callback_server()
        self.dialog.destroy()
    
    def _set_dynamic_size(self):
        try:
            self.dialog.update_idletasks()
            main_frame = self.dialog.winfo_children()[0]
            required_width = main_frame.winfo_reqwidth() + 40
            required_height = main_frame.winfo_reqheight() + 40
            
            self._dialog_width = max(600, required_width)
            final_height = max(350, required_height)
            
            wrap = self._dialog_width - 150
            self.instructions_label.configure(wraplength=wrap)
            self.status_label.configure(wraplength=wrap)
            
            self.dialog.geometry(f"{self._dialog_width}x{final_height}")
            self._center_dialog_sized(self._dialog_width, final_height)
            
        except Exception as e:
            print(f"Error calculating dynamic size: {e}")
            self.dialog.geometry("600x500")
    
    def _center_dialog_sized(self, width, height):
        try:
            self.dialog.update_idletasks()
            screen_width = self.dialog.winfo_screenwidth()
            screen_height = self.dialog.winfo_screenheight()
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            self.dialog.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            pass
