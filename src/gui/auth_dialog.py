"""
Authentication Dialog for Shikimori OAuth
"""

import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
import urllib.parse
import threading
import http.server
import socketserver
import socket
from gui.modern_style import ModernStyle
from utils.logger import get_logger

class AuthDialog:
    """Dialog for Shikimori authentication setup"""
    
    def __init__(self, parent, config, shikimori):
        self.parent = parent
        self.config = config
        self.shikimori = shikimori
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Shikimori Authentication")
        self.dialog.geometry("600x790")
        self.dialog.resizable(True, True)
        
        # Make dialog modal
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - 600) // 2
        y = (self.dialog.winfo_screenheight() - 790) // 2
        self.dialog.geometry(f"600x790+{x}+{y}")
        
        # Apply modern styling
        dark_theme = config.get('ui.dark_theme', False)
        self.modern_style = ModernStyle(self.dialog, dark_theme=dark_theme)
        
        # Apply title bar theme after dialog is fully set up
        self.dialog.after(100, self.modern_style._apply_title_bar_theme)
        
        self._create_widgets()
        
        # Load existing credentials if available
        self._load_existing_credentials()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Shikimori Authentication Setup", 
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Instructions frame with fixed height
        instructions_frame = ttk.LabelFrame(main_frame, text="Setup Instructions", padding="10")
        instructions_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Create a text widget for better formatting
        try:
            bg_color = instructions_frame.cget('background')
        except:
            bg_color = self.dialog.cget('bg')
        
        # Apply theming to text widget
        text_bg = self.modern_style.get_color('bg_card')
        text_fg = self.modern_style.get_color('text_primary')
        
        instructions_text = tk.Text(instructions_frame, height=12, wrap=tk.WORD, 
                                  font=("Segoe UI", 9), relief=tk.FLAT, 
                                  background=text_bg,
                                  foreground=text_fg,
                                  selectbackground=self.modern_style.get_color('accent'),
                                  selectforeground=self.modern_style.get_color('text_white'),
                                  insertbackground=text_fg,
                                  state=tk.DISABLED, cursor="arrow")
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(instructions_frame, orient=tk.VERTICAL, command=instructions_text.yview)
        instructions_text.configure(yscrollcommand=scrollbar.set)
        
        # Pack text widget and scrollbar
        instructions_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Insert instructions text
        instructions_content = """To use this application, you need to create a Shikimori API application.

Follow these steps:

1. Go to https://shikimori.io/oauth/applications

2. Click 'New Application'

3. Fill in the form with these EXACT details:
   • Name: Anime Updater (or any name you prefer)
   • Redirect URI: http://localhost:8080/callback
     ⚠️  CRITICAL: Must be exactly this URL, no variations!
   • Scopes: user_rates
     ⚠️  CRITICAL: Must include this scope for the app to work!

4. Save the application and copy the Client ID and Client Secret below
   • Client ID: Long string of letters/numbers
   • Client Secret: Long string of letters/numbers
   ⚠️  Copy these EXACTLY as shown, no extra spaces!

5. Click 'Start Authorization' to begin the OAuth process"""
        
        instructions_text.config(state=tk.NORMAL)
        instructions_text.insert(tk.END, instructions_content)
        instructions_text.config(state=tk.DISABLED)
        
        # Open browser button
        browser_button = ttk.Button(main_frame, text="Open Shikimori OAuth Applications",
                                   command=self._open_oauth_page)
        browser_button.pack(pady=(0, 20))
        
        # Credentials frame
        creds_frame = ttk.LabelFrame(main_frame, text="API Credentials", padding="10")
        creds_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Client ID
        ttk.Label(creds_frame, text="Client ID:").pack(anchor=tk.W)
        self.client_id_var = tk.StringVar()
        client_id_entry = ttk.Entry(creds_frame, textvariable=self.client_id_var, width=50)
        client_id_entry.pack(fill=tk.X, pady=(2, 10))
        
        # Client Secret
        ttk.Label(creds_frame, text="Client Secret:").pack(anchor=tk.W)
        self.client_secret_var = tk.StringVar()
        client_secret_entry = ttk.Entry(creds_frame, textvariable=self.client_secret_var, 
                                       width=50, show="*")
        client_secret_entry.pack(fill=tk.X, pady=(2, 10))
        
        # Show/Hide secret button
        self.show_secret_var = tk.BooleanVar()
        show_secret_cb = ttk.Checkbutton(creds_frame, text="Show Client Secret",
                                        variable=self.show_secret_var,
                                        command=lambda: client_secret_entry.config(
                                            show="" if self.show_secret_var.get() else "*"))
        show_secret_cb.pack(anchor=tk.W)
        
        # Authorization frame
        auth_frame = ttk.LabelFrame(main_frame, text="Authorization", padding="10")
        auth_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Authorize button
        self.auth_button = ttk.Button(auth_frame, text="Start Authorization",
                                     command=self._start_authorization)
        self.auth_button.pack(pady=(0, 10))
        
        # Authorization code
        ttk.Label(auth_frame, text="Authorization Code (paste from browser):").pack(anchor=tk.W)
        self.auth_code_var = tk.StringVar()
        self.auth_code_entry = ttk.Entry(auth_frame, textvariable=self.auth_code_var, width=50)
        self.auth_code_entry.pack(fill=tk.X, pady=(2, 10))
        self.auth_code_entry.config(state=tk.DISABLED)
        
        # Complete authorization button
        self.complete_button = ttk.Button(auth_frame, text="Complete Authorization",
                                         command=self._complete_authorization,
                                         state=tk.DISABLED)
        self.complete_button.pack()
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(buttons_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        self.save_button = ttk.Button(buttons_frame, text="Save & Close", 
                                     command=self._save_and_close, state=tk.DISABLED)
        self.save_button.pack(side=tk.RIGHT)
    
    def _load_existing_credentials(self):
        """Load existing credentials if available"""
        client_id = self.config.get('shikimori.client_id', '')
        client_secret = self.config.get('shikimori.client_secret', '')
        
        if client_id:
            self.client_id_var.set(client_id)
        if client_secret:
            self.client_secret_var.set(client_secret)
    
    def _open_oauth_page(self):
        """Open Shikimori OAuth applications page"""
        webbrowser.open("https://shikimori.io/oauth/applications")
    
    def _start_authorization(self):
        """Start OAuth authorization process"""
        client_id = self.client_id_var.get().strip()
        client_secret = self.client_secret_var.get().strip()
        
        if not client_id or not client_secret:
            messagebox.showerror("Error", "Please enter both Client ID and Client Secret")
            return
        
        # Save credentials
        self.config.set('shikimori.client_id', client_id)
        self.config.set('shikimori.client_secret', client_secret)
        
        # Generate authorization URL
        redirect_uri = "http://localhost:8080/callback"
        auth_url = self.shikimori.get_auth_url(client_id, redirect_uri)
        
        # Open authorization URL in browser
        webbrowser.open(auth_url)
        
        # Enable code entry
        self.auth_code_entry.config(state=tk.NORMAL)
        self.complete_button.config(state=tk.NORMAL)
        
        messagebox.showinfo("Authorization", 
            "Your browser should now open to Shikimori's authorization page.\n\n"
            "After you authorize the application, you'll be redirected to a page that may show an error. "
            "That's normal!\n\n"
            "IMPORTANT: Copy the authorization code from the URL:\n"
            "• The URL will look like: http://localhost:8080/callback?code=XXXXXXXX\n"
            "• You can copy either just the code part (XXXXXXXX) OR the entire URL\n"
            "• The application will automatically extract the code from either format")
    
    def _complete_authorization(self):
        """Complete OAuth authorization with the provided code"""
        client_id = self.client_id_var.get().strip()
        client_secret = self.client_secret_var.get().strip()
        auth_code = self.auth_code_var.get().strip()
        
        if not auth_code:
            messagebox.showerror("Error", "Please enter the authorization code")
            return
        
        # Disable button during processing
        self.complete_button.config(state=tk.DISABLED, text="Processing...")
        
        def exchange_code():
            try:
                # Clean the auth code - remove any whitespace or URL encoding
                clean_code = auth_code.strip()
                
                # If user pasted the full URL, extract just the code
                if "code=" in clean_code:
                    # Extract code from URL
                    parsed = urllib.parse.urlparse(clean_code)
                    query_params = urllib.parse.parse_qs(parsed.query)
                    if 'code' in query_params:
                        clean_code = query_params['code'][0]
                    else:
                        # Try to find code in the URL string
                        import re
                        code_match = re.search(r'code=([^&]+)', clean_code)
                        if code_match:
                            clean_code = code_match.group(1)
                
                # URL decode the code in case it's encoded
                clean_code = urllib.parse.unquote(clean_code)
                
                redirect_uri = "http://localhost:8080/callback"
                token_data = self.shikimori.exchange_code_for_token(
                    client_id, client_secret, clean_code, redirect_uri)
                
                # Success - enable save button
                self.dialog.after(0, lambda: self.complete_button.config(
                    state=tk.NORMAL, text="✓ Authorized"))
                self.dialog.after(0, lambda: self.save_button.config(state=tk.NORMAL))
                self.dialog.after(0, lambda: messagebox.showinfo("Success", 
                    "Authorization successful! You can now save and close this dialog."))
                
            except Exception as e:
                error_msg = str(e)
                debug_info = f"\nDebug info:\n- Original input: '{auth_code[:50]}...' (truncated)\n- Cleaned code: '{clean_code[:50]}...' (truncated)"
                
                # Specific error handling for common issues
                if "403" in error_msg:
                    error_title = "403 Forbidden - OAuth Configuration Issue"
                    troubleshooting = (
                        "This error indicates a problem with your OAuth application setup:\n\n"
                        "REQUIRED FIXES:\n"
                        "1. Double-check your Shikimori OAuth application settings:\n"
                        "   • Go to https://shikimori.io/oauth/applications\n"
                        "   • Edit your application\n"
                        "   • Redirect URI must be EXACTLY: http://localhost:8080/callback\n"
                        "   • Scopes must include: user_rates\n\n"
                        "2. Verify your credentials:\n"
                        "   • Client ID should be a long string of letters/numbers\n"
                        "   • Client Secret should be a long string of letters/numbers\n"
                        "   • Copy them exactly from the Shikimori OAuth page\n\n"
                        "3. Try creating a new OAuth application if the issue persists\n\n"
                        "4. Make sure the authorization code is fresh (not expired)\n"
                        f"{debug_info}"
                    )
                elif "401" in error_msg:
                    error_title = "401 Unauthorized - Invalid Credentials"
                    troubleshooting = (
                        "Your Client ID or Client Secret is incorrect:\n\n"
                        "• Copy the Client ID and Secret exactly from Shikimori\n"
                        "• Make sure there are no extra spaces or characters\n"
                        "• Try regenerating the Client Secret on Shikimori\n"
                        f"{debug_info}"
                    )
                else:
                    error_title = "Authorization Failed"
                    troubleshooting = (
                        "Common issues:\n"
                        "• Make sure you copied the entire code from the URL\n"
                        "• Check that your Client ID and Secret are correct\n"
                        "• Ensure the redirect URI is exactly: http://localhost:8080/callback\n"
                        "• Try generating a new authorization code\n"
                        f"{debug_info}"
                    )
                
                self.dialog.after(0, lambda: self.complete_button.config(
                    state=tk.NORMAL, text="Complete Authorization"))
                self.dialog.after(0, lambda: messagebox.showerror(error_title, 
                    f"Error: {error_msg}\n\n{troubleshooting}"))
        
        threading.Thread(target=exchange_code, daemon=True).start()
    
    def _save_and_close(self):
        """Save settings and close dialog"""
        self.dialog.destroy()
