"""
HTTP API Server for Chrome Extension Integration
Allows the Chrome extension to send anime scrobble data to the application
"""

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import logging
from typing import Callable, Optional, Dict, Any

from utils.logger import get_logger

class AnimeScrobbleHandler(BaseHTTPRequestHandler):
    """HTTP request handler for anime scrobble requests"""
    
    def __init__(self, *args, scrobble_callback: Optional[Callable] = None, shutdown_callback: Optional[Callable] = None, **kwargs):
        self.scrobble_callback = scrobble_callback
        self.shutdown_callback = shutdown_callback
        self.logger = get_logger('api_server')
        super().__init__(*args, **kwargs)
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_POST(self):
        """Handle POST requests for scrobbling and cancelling"""
        if self.path == '/api/scrobble':
            try:
                # Read the request body
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                
                # Parse JSON data
                anime_data = json.loads(post_data.decode('utf-8'))
                
                self.logger.info(f"Received scrobble request: {anime_data}")
                
                # Validate required fields
                if not anime_data.get('title') or not anime_data.get('episode'):
                    self.send_error_response(400, "Missing required fields: title, episode")
                    return
                
                # Call the scrobble callback if provided
                if self.scrobble_callback:
                    try:
                        result = self.scrobble_callback(anime_data)
                        if result:
                            self.send_success_response({"status": "success", "message": "Anime scrobbled successfully"})
                        else:
                            self.send_error_response(500, "Failed to scrobble anime")
                    except Exception as e:
                        self.logger.error(f"Error in scrobble callback: {e}")
                        self.send_error_response(500, f"Internal error: {str(e)}")
                else:
                    self.send_success_response({"status": "received", "message": "Data received but no handler configured"})
                    
            except json.JSONDecodeError:
                self.send_error_response(400, "Invalid JSON data")
            except Exception as e:
                self.logger.error(f"Error handling scrobble request: {e}")
                self.send_error_response(500, f"Internal server error: {str(e)}")
        elif self.path == '/api/cancel_scrobble':
            try:
                # Read the request body
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                
                # Parse JSON data
                cancel_data = json.loads(post_data.decode('utf-8'))
                
                self.logger.info(f"Received cancel scrobble request: {cancel_data}")
                
                # Call the scrobble callback with cancel action
                if self.scrobble_callback:
                    try:
                        result = self.scrobble_callback({"action": "cancel", **cancel_data})
                        if result:
                            self.send_success_response({"status": "success", "message": "Scrobble cancelled successfully"})
                        else:
                            self.send_error_response(500, "Failed to cancel scrobble")
                    except Exception as e:
                        self.logger.error(f"Error in cancel scrobble callback: {e}")
                        self.send_error_response(500, f"Internal error: {str(e)}")
                else:
                    self.send_success_response({"status": "received", "message": "Cancel request received but no handler configured"})
                    
            except json.JSONDecodeError:
                self.send_error_response(400, "Invalid JSON data")
            except Exception as e:
                self.logger.error(f"Error handling cancel scrobble request: {e}")
                self.send_error_response(500, f"Internal server error: {str(e)}")
        elif self.path == '/api/shutdown':
            try:
                self.logger.info("Received shutdown request")
                
                # Call the shutdown callback if provided
                if self.shutdown_callback:
                    try:
                        self.send_success_response({"status": "success", "message": "Shutdown initiated successfully"})
                        # Call shutdown callback after sending response
                        threading.Thread(target=self.shutdown_callback, daemon=True).start()
                    except Exception as e:
                        self.logger.error(f"Error in shutdown callback: {e}")
                        self.send_error_response(500, f"Internal shutdown error: {str(e)}")
                else:
                    self.send_error_response(500, "Shutdown handler not configured")
                    
            except Exception as e:
                self.logger.error(f"Error handling shutdown request: {e}")
                self.send_error_response(500, f"Internal server error: {str(e)}")
        else:
            self.send_error_response(404, "Not found")
    
    def do_GET(self):
        """Handle GET requests for status check"""
        if self.path == '/api/status':
            self.send_success_response({"status": "running", "message": "Anime Updater API is running"})
        else:
            self.send_error_response(404, "Not found")
    
    def send_success_response(self, data: Dict[str, Any]):
        """Send a successful JSON response"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def send_error_response(self, status_code: int, message: str):
        """Send an error JSON response"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        error_data = {"status": "error", "message": message}
        self.wfile.write(json.dumps(error_data).encode('utf-8'))
    
    def log_message(self, format, *args):
        """Override to use our logger instead of stderr"""
        self.logger.debug(f"{self.address_string()} - {format % args}")

class APIServer:
    """HTTP API Server for Chrome extension integration"""
    
    def __init__(self, port: int = 5000, scrobble_callback: Optional[Callable] = None, shutdown_callback: Optional[Callable] = None):
        self.port = port
        self.scrobble_callback = scrobble_callback
        self.shutdown_callback = shutdown_callback
        self.server = None
        self.server_thread = None
        self.logger = get_logger('api_server')
        self.running = False
    
    def start(self):
        """Start the API server in a separate thread"""
        if self.running:
            self.logger.warning("API server is already running")
            return
        
        try:
            # Create a custom handler class with the scrobble callback
            def handler_factory(*args, **kwargs):
                return AnimeScrobbleHandler(*args, scrobble_callback=self.scrobble_callback, shutdown_callback=self.shutdown_callback, **kwargs)
            
            self.server = HTTPServer(('localhost', self.port), handler_factory)
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
            self.running = True
            self.logger.info(f"API server started on http://localhost:{self.port}")
            
        except Exception as e:
            self.logger.error(f"Failed to start API server: {e}")
            raise
    
    def stop(self):
        """Stop the API server"""
        if not self.running:
            return
        
        try:
            if self.server:
                self.server.shutdown()
                self.server.server_close()
            
            if self.server_thread and self.server_thread.is_alive():
                self.server_thread.join(timeout=2)
            
            self.running = False
            self.logger.info("API server stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping API server: {e}")
    
    def _run_server(self):
        """Run the server - called in separate thread"""
        try:
            self.server.serve_forever()
        except Exception as e:
            if self.running:  # Only log if we weren't intentionally stopped
                self.logger.error(f"API server error: {e}")
            self.running = False
    
    def is_running(self) -> bool:
        """Check if the server is running"""
        return self.running and self.server_thread and self.server_thread.is_alive()
