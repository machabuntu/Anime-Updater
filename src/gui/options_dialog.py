"""
Options Dialog - Configure application settings
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
if 'nt' in sys.builtin_module_names:
    import winreg
from pathlib import Path
from gui.modern_style import ModernStyle

class OptionsDialog:
    """Dialog for configuring application settings"""
    
    def __init__(self, parent, config, main_window=None):
        self.parent = parent
        self.config = config
        self.main_window = main_window
        self.changes_made = False
        self._service_changed = False
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Options")
        # Don't set height initially - will be calculated after content is added
        self.dialog.geometry("450x100")  # Temporary small height
        self.dialog.resizable(False, False)
        
        # Make dialog modal
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center dialog
        self._center_dialog()
        
        # Apply modern styling
        dark_theme = config.get('ui.dark_theme', False)
        self.modern_style = ModernStyle(self.dialog, dark_theme=dark_theme)
        
        # Apply title bar theme after dialog is fully set up
        self.dialog.after(100, self.modern_style._apply_title_bar_theme)
        
        self._create_widgets()
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = self.parent.winfo_rootx() + (self.parent.winfo_width() - 450) // 2
        y = self.parent.winfo_rooty() + (self.parent.winfo_height() - 400) // 2
        self.dialog.geometry(f"450x400+{x}+{y}")
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        # Main settings tab
        self.main_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.main_tab, text="Main")
        self._create_main_tab()
        
        # Notifications tab
        self.notifications_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.notifications_tab, text="Notifications")
        self._create_notifications_tab()
        
        # Load current values
        self._load_current_values()
        
        # Buttons
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(buttons_frame, text="Save", command=self._save_changes).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(buttons_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT)
        
        # Calculate and set dynamic height after all content is added
        self.dialog.after(1, self._set_dynamic_height)
    
    def _on_service_selection_changed(self, event=None):
        """Show/hide MAL credential fields based on selected service."""
        selected = self.service_var.get()
        if selected == "MyAnimeList":
            self.mal_creds_frame.pack(fill=tk.X, pady=(5, 0))
        else:
            self.mal_creds_frame.pack_forget()
        self.dialog.after(10, self._set_dynamic_height)

    def _load_current_values(self):
        """Load current configuration values"""
        # Service selection
        active_service = self.config.get('service.active', 'shikimori')
        self.service_var.set("MyAnimeList" if active_service == 'mal' else "Shikimori")
        self.mal_client_id_var.set(self.config.get('mal.client_id', ''))
        self.mal_client_secret_var.set(self.config.get('mal.client_secret', ''))
        self._on_service_selection_changed()

        # Check if app is in startup
        self.startup_var.set(self._is_in_startup())
        
        # Auto-monitor setting
        self.auto_monitor_var.set(self.config.get('monitoring.auto_start', False))
        
        # Auto-update check setting
        self.auto_update_check_var.set(self.config.get('updates.auto_check', True))
        
        # Watch time setting (convert from seconds to minutes)
        watch_time_seconds = self.config.get('monitoring.min_watch_time', 60)
        self.watch_time_var.set(watch_time_seconds // 60)
        
        # System tray settings
        self.minimize_to_tray_var.set(self.config.get('ui.minimize_to_tray', False))
        self.close_to_tray_var.set(self.config.get('ui.close_to_tray', False))
        
        # Notification settings
        self.episode_notifications_var.set(self.config.get('notifications.episode_notifications', False))
        self.release_notifications_var.set(self.config.get('notifications.release_notifications', False))
        
        # Telegram settings
        self.telegram_enabled_var.set(self.config.get('telegram.enabled', False))
        self.telegram_token_var.set(self.config.get('telegram.bot_token', ''))
        self.telegram_chat_id_var.set(self.config.get('telegram.chat_id', ''))
        self.telegram_send_progress_var.set(self.config.get('telegram.send_progress', False))
        self.telegram_send_completed_var.set(self.config.get('telegram.send_completed', True))
        self.telegram_send_dropped_var.set(self.config.get('telegram.send_dropped', False))
        self.telegram_send_rewatching_var.set(self.config.get('telegram.send_rewatching', False))
        
        # Update telegram controls state
        self._toggle_telegram_controls(self.telegram_enabled_var.get())
    
    def _is_in_startup(self):
        """Check if application is in Windows startup"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                r"Software\Microsoft\Windows\CurrentVersion\Run")
            try:
                winreg.QueryValueEx(key, "AnimeUpdater")
                winreg.CloseKey(key)
                return True
            except FileNotFoundError:
                winreg.CloseKey(key)
                return False
        except Exception:
            return False
    
    def _add_to_startup(self):
        """Add application to Windows startup"""
        try:
            # Get path to executable
            if getattr(sys, 'frozen', False):
                # Running as exe
                app_path = sys.executable
            else:
                # Running as script
                app_path = f'"{sys.executable}" "{os.path.abspath("main.py")}"'
            
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                r"Software\Microsoft\Windows\CurrentVersion\Run", 
                                0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "AnimeUpdater", 0, winreg.REG_SZ, app_path)
            winreg.CloseKey(key)
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add to startup: {str(e)}")
            return False
    
    def _remove_from_startup(self):
        """Remove application from Windows startup"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                r"Software\Microsoft\Windows\CurrentVersion\Run", 
                                0, winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, "AnimeUpdater")
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            # Already not in startup
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to remove from startup: {str(e)}")
            return False
    
    def _save_changes(self):
        """Save configuration changes"""
        try:
            # Save service selection and MAL credentials
            old_service = self.config.get('service.active', 'shikimori')
            new_service = 'mal' if self.service_var.get() == "MyAnimeList" else 'shikimori'
            self.config.set('service.active', new_service)
            self.config.set('mal.client_id', self.mal_client_id_var.get().strip())
            self.config.set('mal.client_secret', self.mal_client_secret_var.get().strip())
            if new_service != old_service:
                self._service_changed = True

            # Handle startup setting
            if self.startup_var.get():
                if not self._is_in_startup():
                    if not self._add_to_startup():
                        return
            else:
                if self._is_in_startup():
                    if not self._remove_from_startup():
                        return
            
            # Save auto-monitor setting
            self.config.set('monitoring.auto_start', self.auto_monitor_var.get())
            
            # Save auto-update check setting
            self.config.set('updates.auto_check', self.auto_update_check_var.get())
            
            # Save watch time setting (convert minutes to seconds)
            watch_time_minutes = self.watch_time_var.get()
            self.config.set('monitoring.min_watch_time', watch_time_minutes * 60)
            
            # Save system tray settings
            self.config.set('ui.minimize_to_tray', self.minimize_to_tray_var.get())
            self.config.set('ui.close_to_tray', self.close_to_tray_var.get())
            
            # Save notification settings
            self.config.set('notifications.episode_notifications', self.episode_notifications_var.get())
            self.config.set('notifications.release_notifications', self.release_notifications_var.get())
            
            # Save Telegram settings
            self.config.set('telegram.enabled', self.telegram_enabled_var.get())
            self.config.set('telegram.bot_token', self.telegram_token_var.get())
            self.config.set('telegram.chat_id', self.telegram_chat_id_var.get())
            self.config.set('telegram.send_progress', self.telegram_send_progress_var.get())
            self.config.set('telegram.send_completed', self.telegram_send_completed_var.get())
            self.config.set('telegram.send_dropped', self.telegram_send_dropped_var.get())
            self.config.set('telegram.send_rewatching', self.telegram_send_rewatching_var.get())
            
            self.changes_made = True
            messagebox.showinfo("Success", "Settings saved successfully!")
            self.dialog.destroy()

            if self._service_changed and self.main_window:
                self.main_window.on_service_changed()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {str(e)}")
    
    def _set_dynamic_height(self):
        """Calculate and set dynamic height based on content"""
        try:
            # Update all widgets to get accurate measurements
            self.dialog.update_idletasks()
            
            # Get the required height of the main frame
            main_frame = self.dialog.winfo_children()[0]  # First child is main_frame
            required_height = main_frame.winfo_reqheight() + 40  # Add padding
            
            # Set minimum height to prevent too small dialogs
            min_height = 300
            final_height = max(min_height, required_height)
            
            # Get current position
            current_geometry = self.dialog.geometry()
            width_pos = current_geometry.split('x')[0]
            pos_part = current_geometry.split('+')[1:] if '+' in current_geometry else []
            
            # Update geometry with new height
            if pos_part:
                new_geometry = f"{width_pos}x{final_height}+{'+'.join(pos_part)}"
            else:
                new_geometry = f"{width_pos}x{final_height}"
            
            self.dialog.geometry(new_geometry)
            
            # Re-center the dialog with new height
            self._center_dialog_with_height(final_height)
            
        except Exception as e:
            # Fallback to fixed height if calculation fails
            print(f"Error calculating dynamic height: {e}")
            self.dialog.geometry("450x500")
    
    def _center_dialog_with_height(self, height):
        """Center dialog on parent with specific height"""
        try:
            self.dialog.update_idletasks()
            x = self.parent.winfo_rootx() + (self.parent.winfo_width() - 450) // 2
            y = self.parent.winfo_rooty() + (self.parent.winfo_height() - height) // 2
            self.dialog.geometry(f"450x{height}+{x}+{y}")
        except Exception:
            # Fallback positioning
            pass
    
    def _create_main_tab(self):
        """Create main settings tab"""
        # Anime service selection
        service_frame = ttk.LabelFrame(self.main_tab, text="Anime Service", padding="10")
        service_frame.pack(fill=tk.X, pady=(0, 15))

        self.service_var = tk.StringVar()
        service_row = ttk.Frame(service_frame)
        service_row.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(service_row, text="Active service:").pack(side=tk.LEFT, padx=(0, 10))
        self.service_combo = ttk.Combobox(service_row, textvariable=self.service_var,
                                          values=["Shikimori", "MyAnimeList"],
                                          state="readonly", width=18)
        self.service_combo.pack(side=tk.LEFT)
        self.service_combo.bind("<<ComboboxSelected>>", self._on_service_selection_changed)

        # MAL credentials (shown only when MAL is selected)
        self.mal_creds_frame = ttk.LabelFrame(service_frame, text="MyAnimeList API Credentials", padding="8")

        mal_id_row = ttk.Frame(self.mal_creds_frame)
        mal_id_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(mal_id_row, text="Client ID:").pack(anchor=tk.W)
        self.mal_client_id_var = tk.StringVar()
        self.mal_client_id_entry = ttk.Entry(mal_id_row, textvariable=self.mal_client_id_var, width=45)
        self.mal_client_id_entry.pack(fill=tk.X, pady=(2, 0))

        mal_secret_row = ttk.Frame(self.mal_creds_frame)
        mal_secret_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(mal_secret_row, text="Client Secret:").pack(anchor=tk.W)
        self.mal_client_secret_var = tk.StringVar()
        self.mal_client_secret_entry = ttk.Entry(mal_secret_row, textvariable=self.mal_client_secret_var,
                                                  show="*", width=45)
        self.mal_client_secret_entry.pack(fill=tk.X, pady=(2, 0))

        mal_note = ttk.Label(self.mal_creds_frame,
                             text="Register an API client at myanimelist.net/apiconfig\n"
                                  "Set redirect URL to http://localhost:8080/callback",
                             foreground="gray", font=("Arial", 8), justify=tk.LEFT)
        mal_note.pack(anchor=tk.W, pady=(4, 0))

        # Startup options
        startup_frame = ttk.LabelFrame(self.main_tab, text="Startup Options", padding="10")
        startup_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Add to Windows startup
        self.startup_var = tk.BooleanVar()
        startup_check = ttk.Checkbutton(startup_frame, text="Add application to Windows startup",
                                       variable=self.startup_var)
        startup_check.pack(anchor=tk.W, pady=(0, 5))
        
        # Enable scrobbling by default
        self.auto_monitor_var = tk.BooleanVar()
        auto_monitor_check = ttk.Checkbutton(startup_frame, text="Enable scrobbling by default on start",
                                            variable=self.auto_monitor_var)
        auto_monitor_check.pack(anchor=tk.W)
        
        # Auto-check for updates
        self.auto_update_check_var = tk.BooleanVar()
        auto_update_check = ttk.Checkbutton(startup_frame, text="Automatically check for updates (hourly)",
                                           variable=self.auto_update_check_var)
        auto_update_check.pack(anchor=tk.W, pady=(0, 5))
        
        # Scrobbling options
        monitor_frame = ttk.LabelFrame(self.main_tab, text="Scrobbling Options", padding="10")
        monitor_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Watch time setting
        watch_time_frame = ttk.Frame(monitor_frame)
        watch_time_frame.pack(fill=tk.X)
        
        ttk.Label(watch_time_frame, text="Update anime progress after:").pack(side=tk.LEFT)
        
        self.watch_time_var = tk.IntVar()
        watch_time_spin = ttk.Spinbox(watch_time_frame, textvariable=self.watch_time_var,
                                     from_=1, to=60, width=5)
        watch_time_spin.pack(side=tk.LEFT, padx=(10, 5))
        
        ttk.Label(watch_time_frame, text="minutes").pack(side=tk.LEFT)
        
        # System Tray options
        tray_frame = ttk.LabelFrame(self.main_tab, text="System Tray Options", padding="10")
        tray_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Minimize to tray
        self.minimize_to_tray_var = tk.BooleanVar()
        minimize_tray_check = ttk.Checkbutton(tray_frame, text="Minimize to system tray instead of taskbar",
                                            variable=self.minimize_to_tray_var)
        minimize_tray_check.pack(anchor=tk.W, pady=(0, 5))
        
        # Close to tray
        self.close_to_tray_var = tk.BooleanVar()
        close_tray_check = ttk.Checkbutton(tray_frame, text="Close to system tray instead of exiting",
                                         variable=self.close_to_tray_var)
        close_tray_check.pack(anchor=tk.W)
        
        # Add note about dependencies
        try:
            import pystray
            from PIL import Image
        except ImportError:
            note_label = ttk.Label(tray_frame, text="Note: Install 'pystray' and 'pillow' packages for tray functionality", 
                                 foreground="orange", font=("Arial", 8))
            note_label.pack(anchor=tk.W, pady=(5, 0))
    
    def _create_notifications_tab(self):
        """Create notifications settings tab"""
        # Desktop notification options
        desktop_frame = ttk.LabelFrame(self.notifications_tab, text="Desktop Notifications", padding="10")
        desktop_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Episode notifications
        self.episode_notifications_var = tk.BooleanVar()
        episode_check = ttk.Checkbutton(desktop_frame, 
                                       text="Notify when new episodes are available for watching anime",
                                       variable=self.episode_notifications_var)
        episode_check.pack(anchor=tk.W, pady=(0, 5))
        
        # Release notifications
        self.release_notifications_var = tk.BooleanVar()
        release_check = ttk.Checkbutton(desktop_frame, 
                                      text="Notify when planned anime are fully released",
                                      variable=self.release_notifications_var)
        release_check.pack(anchor=tk.W)
        
        # Add note about notification dependencies
        try:
            from utils.notification_service import NotificationService
            if not NotificationService.is_available():
                note_label = ttk.Label(desktop_frame, 
                                     text="Note: Install 'win10toast' or 'plyer' for better notifications", 
                                     foreground="orange", font=("Arial", 8))
                note_label.pack(anchor=tk.W, pady=(5, 0))
        except ImportError:
            pass
        
        # Telegram notifications
        telegram_frame = ttk.LabelFrame(self.notifications_tab, text="Telegram Notifications", padding="10")
        telegram_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Enable telegram notifications
        self.telegram_enabled_var = tk.BooleanVar()
        telegram_check = ttk.Checkbutton(telegram_frame, text="Enable Telegram notifications",
                                        variable=self.telegram_enabled_var,
                                        command=self._on_telegram_enabled_changed)
        telegram_check.pack(anchor=tk.W, pady=(0, 10))
        
        # Bot token
        token_frame = ttk.Frame(telegram_frame)
        token_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(token_frame, text="Bot Token:").pack(anchor=tk.W)
        self.telegram_token_var = tk.StringVar()
        self.telegram_token_entry = ttk.Entry(token_frame, textvariable=self.telegram_token_var, 
                                             show="*", width=50)
        self.telegram_token_entry.pack(fill=tk.X, pady=(2, 0))
        
        # Chat ID
        chat_frame = ttk.Frame(telegram_frame)
        chat_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(chat_frame, text="Channel/Chat ID:").pack(anchor=tk.W)
        self.telegram_chat_id_var = tk.StringVar()
        self.telegram_chat_id_entry = ttk.Entry(chat_frame, textvariable=self.telegram_chat_id_var, width=50)
        self.telegram_chat_id_entry.pack(fill=tk.X, pady=(2, 0))
        
        # Test connection button
        test_frame = ttk.Frame(telegram_frame)
        test_frame.pack(fill=tk.X, pady=(5, 10))
        
        self.test_button = ttk.Button(test_frame, text="Test Connection", command=self._test_telegram_connection)
        self.test_button.pack(side=tk.LEFT)
        
        # Filter options
        filter_frame = ttk.LabelFrame(telegram_frame, text="Send Notifications For:", padding="5")
        filter_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.telegram_send_progress_var = tk.BooleanVar()
        progress_check = ttk.Checkbutton(filter_frame, text="Any positive progress change",
                                       variable=self.telegram_send_progress_var)
        progress_check.pack(anchor=tk.W)
        
        self.telegram_send_completed_var = tk.BooleanVar()
        completed_check = ttk.Checkbutton(filter_frame, text="Only completed anime",
                                        variable=self.telegram_send_completed_var)
        completed_check.pack(anchor=tk.W)
        
        self.telegram_send_dropped_var = tk.BooleanVar()
        dropped_check = ttk.Checkbutton(filter_frame, text="Dropped anime",
                                       variable=self.telegram_send_dropped_var)
        dropped_check.pack(anchor=tk.W)
        
        self.telegram_send_rewatching_var = tk.BooleanVar()
        rewatching_check = ttk.Checkbutton(filter_frame, text="Started rewatching anime",
                                          variable=self.telegram_send_rewatching_var)
        rewatching_check.pack(anchor=tk.W)
        
        # Info label
        info_label = ttk.Label(telegram_frame, 
                             text="Note: Only scrobbling updates will be sent, not manual updates.",
                             foreground="gray", font=("Arial", 8))
        info_label.pack(anchor=tk.W, pady=(5, 0))
        
        # Initially disable telegram controls
        self._toggle_telegram_controls(False)
    
    def _on_telegram_enabled_changed(self):
        """Handle telegram enabled checkbox change"""
        enabled = self.telegram_enabled_var.get()
        self._toggle_telegram_controls(enabled)
    
    def _toggle_telegram_controls(self, enabled: bool):
        """Enable or disable telegram controls"""
        state = tk.NORMAL if enabled else tk.DISABLED
        
        self.telegram_token_entry.config(state=state)
        self.telegram_chat_id_entry.config(state=state)
        self.test_button.config(state=state)
    
    def _test_telegram_connection(self):
        """Test Telegram bot connection"""
        # Temporarily save telegram settings to config for testing
        old_enabled = self.config.get('telegram.enabled', False)
        old_token = self.config.get('telegram.bot_token', '')
        
        self.config.set('telegram.enabled', True)
        self.config.set('telegram.bot_token', self.telegram_token_var.get())
        
        try:
            from utils.telegram_notifier import TelegramNotifier
            notifier = TelegramNotifier(self.config)
            success, message = notifier.test_connection()
            
            if success:
                messagebox.showinfo("Connection Test", f"✅ {message}")
            else:
                messagebox.showerror("Connection Test", f"❌ {message}")
                
        except Exception as e:
            messagebox.showerror("Connection Test", f"❌ Error: {str(e)}")
        finally:
            # Restore old settings
            self.config.set('telegram.enabled', old_enabled)
            self.config.set('telegram.bot_token', old_token)
