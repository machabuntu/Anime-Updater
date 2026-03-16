"""
Main GUI Window for Anime Updater
"""

import tkinter as tk
from tkinter import ttk, messagebox
try:
    from tkinter import simpledialog
except ImportError:
    import tkinter.simpledialog as simpledialog
import threading
import webbrowser
import os
import sys
from typing import Dict, List, Any, Optional
try:
    import pystray
    from PIL import Image, ImageDraw
    # Test that pystray can be initialized
    test_image = Image.new('RGB', (16, 16), 'black')
    test_icon = pystray.Icon('test', test_image)
    TRAY_AVAILABLE = True
    # Will log when logger is available
except ImportError as e:
    # Will log when logger is available
    TRAY_AVAILABLE = False
except Exception as e:
    # Will log when logger is available
    TRAY_AVAILABLE = False

from api.shikimori_client import ShikimoriClient
from api.mal_client import MALClient
from api.api_server import APIServer
from utils.player_monitor import PlayerMonitor, EpisodeInfo
from utils.anime_matcher import AnimeMatcher
from utils.enhanced_anime_matcher import EnhancedAnimeMatcher
from gui.simple_auth_dialog import SimpleAuthDialog
from gui.anime_list_frame import AnimeListFrame
from gui.manga_list_frame import MangaListFrame
from gui.search_frame import SearchFrame
from gui.options_dialog import OptionsDialog
from gui.modern_style import ModernStyle
from core.cache import CacheManager
from utils.logger import get_logger
from utils.updater import UpdateChecker
from utils.version import get_version_info
from gui.update_dialog import UpdateNotification

class MainWindow:
    """Main application window"""
    
    def __init__(self, root: tk.Tk, config):
        self.root = root
        self.config = config
        self.logger = get_logger('main_window')
        self.api_client = self._create_active_client(config)
        self.player_monitor = PlayerMonitor(config)
        self.cache_manager = CacheManager(config)
        # Use enhanced matcher with synonym support
        self.anime_matcher = EnhancedAnimeMatcher(self.api_client, self.cache_manager)
        
        # Initialize notification manager
        from utils.notification_manager import NotificationManager
        self.notification_manager = NotificationManager(config, self.api_client, self.cache_manager)
        
        # Initialize Telegram notifier
        from utils.telegram_notifier import TelegramNotifier
        self.telegram_notifier = TelegramNotifier(config)
        
        # Data
        self.current_user = None
        self.anime_list_data: Dict[str, List[Dict[str, Any]]] = {}
        self.manga_list_data: Dict[str, List[Dict[str, Any]]] = {}
        self.monitoring_active = False
        self.tray_icon = None
        self.window_minimized = False
        self.updated_anime_episodes = set()  # Track which anime episodes have been updated
        self.browser_watched_episodes = {}  # Track browser episodes with start times: {unique_key: start_time}
        self.browser_pending_timers = {}  # Track pending timer callbacks: {unique_key: timer_id}
        
        # Update check timer
        self.update_check_timer = None
        
        # Setup window
        self._setup_window()
        self._create_widgets()
        self._setup_monitoring()
        
        # Initialize API server
        self.api_server = APIServer(scrobble_callback=self._handle_scrobble, shutdown_callback=self._handle_shutdown)
        self.api_server.start()

        # Load initial data if authenticated
        if config.is_authenticated:
            self._load_user_data()
            
            # Auto-start monitoring if enabled
            if self.config.get('monitoring.auto_start', False):
                self.root.after(2000, self._toggle_monitoring)  # Start after 2 seconds delay
        else:
            # Update window title for not logged in state
            self._update_window_title()
        
        # Check for updates on startup (after a delay)
        self.root.after(5000, self._check_for_updates)
        
        # Start auto-update checks if enabled
        if self.config.get('updates.auto_check', True):
            self._schedule_update_check()
    
    def _handle_scrobble(self, anime_data):
        """Handle scrobble data received from API server or extension"""
        try:
            # Handle cancel action
            if anime_data.get('action') == 'cancel':
                return self._handle_cancel_scrobble(anime_data)
            
            title = anime_data['title']
            episode = anime_data['episode']
            self.logger.info(f"Scrobbling anime: {title}, Episode: {episode}")
            
            # Create unique key for this episode
            episode_key = f"{title}_{episode}"
            
            # Update the "Now Watching" panel immediately
            # Check if anime is in user's list first (only active statuses)
            if self._is_anime_in_active_list(title):
                anime_display = f"Now Watching: {title} - Episode {episode}"
                self.logger.info(f"Anime found in user's active list: {title}")
            else:
                anime_display = f"Anime not in active list: {title} - Episode {episode}"
                self.logger.info(f"Anime not found in user's active list: {title}")
            
            # Update the panel on main thread
            self.root.after(0, lambda: self.current_anime_var.set(anime_display))
            
            # Start tracking watch time for browser episodes
            import time
            self.browser_watched_episodes[episode_key] = time.time()
            
            def process_episode():
                try:
                    # Clean up timer tracking since we're now processing
                    current_episode_key = f"{title}_{episode}"
                    if current_episode_key in self.browser_pending_timers:
                        del self.browser_pending_timers[current_episode_key]
                    if current_episode_key in self.browser_watched_episodes:
                        del self.browser_watched_episodes[current_episode_key]
                    
                    # Find matching anime in user's list - only consider active statuses
                    # Filter out Completed and Dropped anime to avoid conflicts with multiple seasons
                    active_statuses = ['watching', 'planned', 'rewatching', 'on_hold']
                    all_anime = []
                    for status_key in active_statuses:
                        if status_key in self.anime_list_data:
                            all_anime.extend(self.anime_list_data[status_key])
                    
                    self.logger.debug(f"Searching for anime match: {title}")
                    match_result = self.anime_matcher.find_best_match(title, all_anime, episode)
                    
                    if match_result:
                        anime_entry, similarity = match_result
                        anime_data = anime_entry['anime']
                        anime_name = anime_data.get('name', title)
                        anime_id = anime_entry['id']
                        
                        self.logger.info(f"Anime match found: {anime_name} (ID: {anime_id}, Similarity: {similarity:.2f})")
                        
                        # Check if episode number is +1 from current progress
                        current_episodes = anime_entry.get('episodes', 0)
                        target_episode = episode
                        
                        self.logger.info(f"Episode progress check: Current={current_episodes}, Target={target_episode}")
                        
                        # Check if this episode has already been updated for this anime
                        anime_episode_key = f"{anime_id}_{target_episode}"
                        
                        # Allow update if episode is next (+1) or if current episode but not yet updated
                        # Defensive check - ensure updated_anime_episodes exists
                        if not hasattr(self, 'updated_anime_episodes'):
                            self.updated_anime_episodes = set()
                        already_updated = anime_episode_key in self.updated_anime_episodes
                        
                        if already_updated:
                            self.logger.info(f"Episode {target_episode} already updated for {anime_name}, skipping")
                        
                        if (target_episode == current_episodes + 1):
                            # Update progress
                            rate_id = anime_entry['id']
                            anime_data = anime_entry['anime']
                            total_episodes = anime_data.get('episodes', 0)
                            
                            # Determine new status
                            current_status = anime_entry.get('status', '')
                            new_status = None
                            
                            self.logger.info(f"Status determination: Current status={current_status}, Total episodes={total_episodes}")
                            
                            # Check if anime is in Plan to Watch and should be moved to Watching
                            if current_status == 'planned' and target_episode > 0:
                                new_status = 'watching'
                                self.logger.info(f"Status change: {current_status} -> {new_status} (started watching)")
                            elif total_episodes > 0 and target_episode >= total_episodes:
                                # Check if anime is scored
                                current_score = anime_entry.get('score', 0)
                                if current_score > 0:
                                    new_status = 'completed'
                                    self.logger.info(f"Status change: {current_status} -> {new_status} (completed, has score)")
                                else:
                                    self.logger.info(f"Anime finished but no score set, keeping status as {current_status}")
                            
                            # Update on the active service
                            self.logger.info(f"Updating anime progress: {anime_name} -> Episode {target_episode}" + 
                                            (f", Status: {new_status}" if new_status else ""))
                            success = self.api_client.update_anime_progress(
                                rate_id, target_episode, status=new_status)
                            
                            if success:
                                anime_name = anime_data.get('name', title)
                                message = f"Updated {anime_name} to episode {target_episode}"
                                if new_status == 'completed':
                                    message += " (Completed)"
                                elif current_status == 'planned' and new_status == 'watching':
                                    message += " (Moved to Watching)"
                                
                                self.logger.info(f"Anime progress update successful: {message}")
                                self.root.after(0, lambda: self._set_status(message))
                                # Mark this episode as updated
                                self.updated_anime_episodes.add(anime_episode_key)
                                
                                # Update only this specific anime in the list instead of full refresh
                                # Update the local data first
                                anime_entry['episodes'] = target_episode
                                if new_status:
                                    anime_entry['status'] = new_status
                                
                                # Update cache with the modified data
                                if self.current_user:
                                    self.cache_manager.save_anime_list(self.current_user['id'], self.anime_list_data)
                                    self.logger.debug("Anime list cache updated after scrobbling")
                                
                                # Send Telegram notification for scrobbling update
                                if self.current_user:
                                    username = self.current_user.get('nickname', 'Unknown')
                                    anime_url = anime_data.get('url', '')
                                    
                                    if new_status == 'completed':
                                        # Check if this is a rewatch completion
                                        old_status = anime_entry.get('status', '')
                                        is_rewatch = old_status == 'rewatching'
                                        rewatch_count = 0
                                        
                                        if is_rewatch:
                                            # Get current rewatch count (this would be updated by the API call)
                                            rewatch_count = anime_entry.get('rewatches', 0) + 1
                                        
                                        self.logger.info(f"Sending completion Telegram notification for {anime_name}" + 
                                                        (f" (rewatch #{rewatch_count})" if is_rewatch else ""))
                                        
                                        # Send completion notification
                                        score = anime_entry.get('score', 0)
                                        comment = anime_entry.get('text', '') or anime_entry.get('text_html', '')
                                        self.telegram_notifier.send_completion_update(anime_name, score, username, is_rewatch, rewatch_count, anime_url, comment)
                                    else:
                                        # Send progress notification
                                        total_episodes = anime_data.get('episodes', 0)
                                        self.logger.info(f"Sending progress Telegram notification for {anime_name} episode {target_episode}")
                                        self.telegram_notifier.send_progress_update(anime_name, target_episode, total_episodes, username, anime_url)
                                
                                self.root.after(0, lambda: self._update_single_anime(anime_entry))
                            else:
                                error_msg = f"Failed to update {title}"
                                self.logger.error(f"Anime progress update failed: {error_msg}")
                                self.root.after(0, lambda: self._set_status(error_msg))
                        else:
                            warn_msg = f"Episode {target_episode} is not next for {title} (current: {current_episodes})"
                            self.logger.warning(f"Episode validation failed: {warn_msg}")
                            self.root.after(0, lambda: self._set_status(warn_msg))
                    else:
                        warn_msg = f"No match found for {title}"
                        self.logger.warning(f"Anime matching failed: {warn_msg}")
                        self.root.after(0, lambda: self._set_status(warn_msg))
                        
                except Exception as e:
                    error_msg = f"Error processing episode: {str(e)}"
                    self.logger.error(f"Episode processing error: {error_msg}", exc_info=True)
                    self.root.after(0, lambda: self._set_status(error_msg))
            
            # Set a timer for browser scrobbling just like local scrobbling
            timer_duration = self.config.get('monitoring.min_watch_time', 60)
            timer_id = self.root.after(timer_duration * 1000, process_episode)
            self.browser_pending_timers[episode_key] = timer_id
            
            self.logger.info(f"Browser scrobble timer set for {timer_duration} seconds: {title} Episode {episode}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to handle scrobble: {e}")
            # Update status bar with error message
            self.root.after(0, lambda: self._set_status(f"Error scrobbling: {str(e)}"))
            return False
    
    def _handle_cancel_scrobble(self, cancel_data):
        """Handle cancellation of browser scrobble"""
        try:
            title = cancel_data.get('title', '')
            episode = cancel_data.get('episode', '')
            
            if not title:
                self.logger.warning("Cancel scrobble request missing title")
                return False
            
            # Create episode key to find pending timer
            episode_key = f"{title}_{episode}" if episode else None
            
            # If specific episode provided, cancel that specific timer
            if episode_key and episode_key in self.browser_pending_timers:
                timer_id = self.browser_pending_timers[episode_key]
                self.root.after_cancel(timer_id)
                del self.browser_pending_timers[episode_key]
                del self.browser_watched_episodes[episode_key]
                self.logger.info(f"Cancelled browser scrobble timer for: {title} Episode {episode}")
            else:
                # Cancel all timers for this title
                cancelled_count = 0
                keys_to_remove = []
                for key in list(self.browser_pending_timers.keys()):
                    if key.startswith(f"{title}_"):
                        timer_id = self.browser_pending_timers[key]
                        self.root.after_cancel(timer_id)
                        keys_to_remove.append(key)
                        cancelled_count += 1
                
                for key in keys_to_remove:
                    del self.browser_pending_timers[key]
                    if key in self.browser_watched_episodes:
                        del self.browser_watched_episodes[key]
                
                self.logger.info(f"Cancelled {cancelled_count} browser scrobble timers for: {title}")
            
            # Clear "Now Watching" panel if this was the current anime
            current_display = self.current_anime_var.get()
            if title in current_display:
                self.root.after(0, lambda: self.current_anime_var.set("Now Watching: None"))
                self.logger.info(f"Cleared Now Watching panel for cancelled scrobble: {title}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error handling cancel scrobble: {e}")
            return False
    
    def _handle_shutdown(self):
        """Handle shutdown request from API"""
        try:
            self.logger.info("Shutdown request received via API")
            # Schedule the actual shutdown to happen on the main thread
            self.root.after(0, self._actually_close)
        except Exception as e:
            self.logger.error(f"Error handling shutdown request: {e}")
    
    def _setup_window(self):
        """Setup main window properties"""
        self.root.title("Anime Updater - Not logged in")
        
        # Set window icon
        self._set_window_icon()
        
        # Set window size and position
        width = self.config.get('window.width', 1000)
        height = self.config.get('window.height', 700)
        x = self.config.get('window.x')
        y = self.config.get('window.y')
        
        if x is not None and y is not None:
            self.root.geometry(f"{width}x{height}+{x}+{y}")
        else:
            self.root.geometry(f"{width}x{height}")
            # Center window
            self.root.update_idletasks()
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            self.root.geometry(f"{width}x{height}+{x}+{y}")
        
        # Save window position on close
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Handle window state changes for tray functionality
        self.root.bind('<Unmap>', self._on_minimize)
        self.root.bind('<Map>', self._on_restore)
        
        # Apply modern styling
        dark_theme = self.config.get('ui.dark_theme', False)
        self.modern_style = ModernStyle(self.root, dark_theme=dark_theme)
        
        # Apply title bar theme after window is fully set up
        self.root.after(100, self.modern_style._apply_title_bar_theme)
        
        # Initialize system tray if available
        if TRAY_AVAILABLE:
            self._setup_system_tray()
    
    def _set_window_icon(self):
        """Set the window icon"""
        try:
            # Try to find icon file in different locations
            icon_paths = [
                'icon.ico',
                '../icon.ico',
                'icon.png',
                '../icon.png'
            ]
            
            # Check for frozen (PyInstaller) environment
            if getattr(sys, 'frozen', False):
                # Running as PyInstaller executable
                base_path = sys._MEIPASS
                icon_paths = [
                    os.path.join(base_path, 'icon.ico'),
                    os.path.join(base_path, 'icon.png'),
                    'icon.ico',
                    'icon.png'
                ]
            
            for icon_path in icon_paths:
                if os.path.exists(icon_path):
                    if icon_path.endswith('.ico'):
                        # Use ICO file directly
                        self.root.iconbitmap(icon_path)
                        self.logger.info(f"Window icon set from: {icon_path}")
                        return
                    elif icon_path.endswith('.png'):
                        # Convert PNG to PhotoImage for tkinter
                        try:
                            from PIL import Image, ImageTk
                            img = Image.open(icon_path)
                            # Resize to standard icon size if needed
                            img = img.resize((32, 32), Image.Resampling.LANCZOS)
                            photo = ImageTk.PhotoImage(img)
                            self.root.iconphoto(True, photo)
                            # Keep a reference to prevent garbage collection
                            self.root._icon_photo = photo
                            self.logger.info(f"Window icon set from: {icon_path}")
                            return
                        except ImportError:
                            self.logger.warning("PIL not available for PNG icon conversion")
                        except Exception as e:
                            self.logger.warning(f"Failed to load PNG icon {icon_path}: {e}")
            
            self.logger.info("Using default window icon (no custom icon found)")
            
        except Exception as e:
            self.logger.error(f"Error setting window icon: {e}")
    
    def _load_tray_icon(self):
        """Load custom icon for system tray"""
        try:
            # Try to find icon file in different locations
            icon_paths = [
                'icon.png',
                '../icon.png',
                'icon.ico',
                '../icon.ico'
            ]
            
            # Check for frozen (PyInstaller) environment
            if getattr(sys, 'frozen', False):
                # Running as PyInstaller executable
                base_path = sys._MEIPASS
                icon_paths = [
                    os.path.join(base_path, 'icon.png'),
                    os.path.join(base_path, 'icon.ico'),
                    'icon.png',
                    'icon.ico'
                ]
            
            for icon_path in icon_paths:
                if os.path.exists(icon_path):
                    try:
                        img = Image.open(icon_path)
                        # Resize to tray icon size
                        img = img.resize((32, 32), Image.Resampling.LANCZOS)
                        # Convert to RGBA for better compatibility
                        if img.mode != 'RGBA':
                            img = img.convert('RGBA')
                        self.logger.info(f"Tray icon loaded from: {icon_path}")
                        return img
                    except Exception as e:
                        self.logger.warning(f"Failed to load tray icon {icon_path}: {e}")
                        continue
            
            self.logger.info("Using fallback tray icon (no custom icon found)")
            return None
            
        except Exception as e:
            self.logger.error(f"Error loading tray icon: {e}")
            return None
    
    def _create_widgets(self):
        """Create main window widgets"""
        # Main container
        main_frame = ttk.Frame(self.root, style='Modern.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Toolbar
        self._create_toolbar(main_frame)
        
        # Status bar
        self._create_status_bar(main_frame)
        
        # Main content area
        self._create_content_area(main_frame)
    
    def _create_toolbar(self, parent):
        """Create toolbar with main controls"""
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=(0, 5))
        
        # Left side - Menu dropdown
        menu_frame = ttk.Frame(toolbar, style='Modern.TFrame')
        menu_frame.pack(side=tk.LEFT, padx=(0, 10), pady=2)
        
        self.menu_button = ttk.Menubutton(menu_frame, text="Menu", style='Modern.TButton')
        self.menu_button.pack(side=tk.LEFT)
        
        # Create dropdown menu
        self.menu = tk.Menu(self.menu_button, tearoff=0)
        self.menu_button.config(menu=self.menu)
        
        # Apply modern styling to menu
        self.modern_style.configure_menu(self.menu)
        
        self.menu.add_command(label="Authentication...", command=self._handle_auth)
        self.menu.add_separator()
        self.menu.add_command(label="Start/Stop Scrobbling", command=self._toggle_monitoring)
        self.menu.add_separator()
        self.menu.add_command(label="Refresh Anime List", command=lambda: self._refresh_list(force_refresh=True))
        self.menu.add_command(label="Refresh Manga List", command=lambda: self._refresh_manga_list(force_refresh=True))
        self.menu.add_separator()
        self.menu.add_command(label="Options...", command=self._show_options)
        # Add dark theme toggle
        self.menu.add_separator()
        self.menu.add_command(label="Toggle Dark Theme", command=self._toggle_dark_theme)
        # Add cache management to menu
        self.menu.add_separator()
        self.menu.add_command(label="Clear Cache", command=self._clear_cache)
        self.menu.add_command(label="Refresh Synonyms", command=self._refresh_synonyms)
        self.menu.add_separator()
        self.menu.add_command(label="View Logs", command=self._show_log_viewer)
        self.menu.add_separator()
        self.menu.add_command(label="Check for Updates", command=self._check_for_updates)
        self.menu.add_separator()
        self.menu.add_command(label="Exit", command=self._exit_application)
        
        # Compact anime info panel  
        self._create_compact_anime_info(toolbar)
    
    def _create_compact_anime_info(self, parent):
        """Create a compact anime info panel in the toolbar"""
        info_frame = ttk.Frame(parent)
        info_frame.pack(side=tk.LEFT, padx=(0, 10), pady=2, ipadx=5, ipady=2)
        
        # First row - Anime name only
        name_row = ttk.Frame(info_frame)
        name_row.pack(fill=tk.X, pady=(0, 2))
        
        self.compact_anime_name_var = tk.StringVar(value="None")
        name_label = ttk.Label(name_row, textvariable=self.compact_anime_name_var, font=("Segoe UI", 9, "bold"))
        name_label.pack(side=tk.LEFT)
        
        # Second row - Progress Controls
        progress_row = ttk.Frame(info_frame)
        progress_row.pack(fill=tk.X, pady=(0, 2))

        # Progress control
        progress_frame = ttk.Frame(progress_row)
        progress_frame.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(progress_frame, text="Ep:").pack(side=tk.LEFT, padx=(0, 2))

        # Decrease button for episodes/chapters (20% smaller)
        self.compact_decrease_btn = ttk.Button(progress_frame, text="-", width=2,
                                             command=self._compact_decrease_progress)
        self.compact_decrease_btn.pack(side=tk.LEFT, padx=(0, 2))
        
        # Episode entry (compact) - this will change to chapters in manga mode
        self.compact_episode_var = tk.StringVar(value="0")
        self.compact_episode_entry = ttk.Entry(progress_frame, textvariable=self.compact_episode_var, width=4, justify=tk.CENTER)
        self.compact_episode_entry.pack(side=tk.LEFT, padx=2)
        self.compact_episode_entry.bind('<Return>', self._on_compact_episode_entry)
        self.compact_episode_entry.bind('<FocusOut>', self._on_compact_episode_entry)
        self.compact_episode_entry.bind('<FocusIn>', self._on_compact_episode_focus_in)
        self.compact_episode_entry.bind('<KeyPress>', self._on_compact_episode_key_press)

        self.compact_total_episodes_var = tk.StringVar(value="/?")
        ttk.Label(progress_frame, textvariable=self.compact_total_episodes_var).pack(side=tk.LEFT, padx=(2, 2))
        
        # Increase button for episodes/chapters (20% smaller)
        self.compact_increase_btn = ttk.Button(progress_frame, text="+", width=2,
                                             command=self._compact_increase_progress)
        self.compact_increase_btn.pack(side=tk.LEFT, padx=(2, 10))
        
        # Volume controls (hidden by default for anime mode)
        self.volume_frame = ttk.Frame(progress_row)
        self.volume_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(self.volume_frame, text="Vol:").pack(side=tk.LEFT, padx=(0, 2))
        
        # Decrease button for volumes (20% smaller)
        self.compact_volume_decrease_btn = ttk.Button(self.volume_frame, text="-", width=2,
                                                    command=self._compact_decrease_volumes)
        self.compact_volume_decrease_btn.pack(side=tk.LEFT, padx=(0, 2))
        
        # Volume entry
        self.compact_volume_var = tk.StringVar(value="0")
        self.compact_volume_entry = ttk.Entry(self.volume_frame, textvariable=self.compact_volume_var, width=4, justify=tk.CENTER)
        self.compact_volume_entry.pack(side=tk.LEFT, padx=2)
        self.compact_volume_entry.bind('<Return>', self._on_compact_volume_entry)
        self.compact_volume_entry.bind('<FocusOut>', self._on_compact_volume_entry)
        
        self.compact_total_volumes_var = tk.StringVar(value="/?")
        ttk.Label(self.volume_frame, textvariable=self.compact_total_volumes_var).pack(side=tk.LEFT, padx=(2, 2))
        
        # Increase button for volumes (20% smaller)
        self.compact_volume_increase_btn = ttk.Button(self.volume_frame, text="+", width=2,
                                                    command=self._compact_increase_volumes)
        self.compact_volume_increase_btn.pack(side=tk.LEFT, padx=(2, 0))
        
        # Initially hide volume controls (anime mode)
        self.volume_frame.pack_forget()

        # Third row - Status and Score Controls
        status_score_row = ttk.Frame(info_frame)
        status_score_row.pack(fill=tk.X)

        # Status control (compact)
        status_frame = ttk.Frame(status_score_row)
        status_frame.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT, padx=(0, 2))

        self.compact_status_var = tk.StringVar(value="-")
        self.compact_status_combo = ttk.Combobox(status_frame, textvariable=self.compact_status_var,
                                                values=["-"] + list(self.api_client.STATUSES.values()),
                                                width=12, state="readonly")
        self.compact_status_combo.pack(side=tk.LEFT)
        self.compact_status_combo.bind('<<ComboboxSelected>>', self._on_compact_status_changed)

        # Score control (compact)
        score_frame = ttk.Frame(status_score_row)
        score_frame.pack(side=tk.LEFT, padx=(10, 0))

        ttk.Label(score_frame, text="Score:").pack(side=tk.LEFT, padx=(0, 2))

        self.compact_score_var = tk.StringVar(value="-")
        self.compact_score_combo = ttk.Combobox(score_frame, textvariable=self.compact_score_var,
                                               values=["-"] + [str(i) for i in range(1, 11)],
                                               width=3, state="readonly")
        self.compact_score_combo.pack(side=tk.LEFT)
        self.compact_score_combo.bind('<<ComboboxSelected>>', self._on_compact_score_changed)
        
        # Store current mode (anime or manga)
        self.current_mode = 'anime'  # Default to anime mode
        
        # Initially disable controls
        self._set_compact_controls_enabled(False)
    
    def _create_monitoring_info_panel(self, parent):
        """Create a panel to show current monitoring status"""
        monitor_frame = ttk.Frame(parent, padding="5")
        monitor_frame.pack(side=tk.RIGHT, padx=(10, 0), pady=5)

        self.current_anime_var = tk.StringVar(value="Now Watching: None")
        ttk.Label(monitor_frame, textvariable=self.current_anime_var, font=("Arial", 10)).pack(anchor=tk.W)

    def _create_status_bar(self, parent):
        """Create status bar"""
        self.status_var = tk.StringVar(value="Ready")
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(5, 0))
        
        # Status message on the left
        ttk.Label(status_frame, textvariable=self.status_var, relief=tk.SUNKEN).pack(
            fill=tk.X, side=tk.LEFT)
        
        # Add monitoring info panel on the right
        self._create_monitoring_info_panel(status_frame)
    
    def _create_anime_info_panel(self, parent):
        """Create anime info panel with controls"""
        self.selected_anime = None
        
        info_frame = ttk.LabelFrame(parent, text="Selected Anime", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Main info area
        main_info = ttk.Frame(info_frame)
        main_info.pack(fill=tk.X)
        
        # Left side - Anime info
        left_frame = ttk.Frame(main_info)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Anime name
        self.anime_name_var = tk.StringVar(value="No anime selected")
        anime_name_label = ttk.Label(left_frame, textvariable=self.anime_name_var, 
                                    font=("Arial", 11, "bold"))
        anime_name_label.pack(anchor=tk.W)
        
        # Anime details - First row (Type and Year)
        self.anime_details_var = tk.StringVar(value="")
        anime_details_label = ttk.Label(left_frame, textvariable=self.anime_details_var, 
                                       foreground="gray")
        anime_details_label.pack(anchor=tk.W)
        
        # Anime details - Second row (Status and Score)
        self.anime_status_score_var = tk.StringVar(value="")
        anime_status_score_label = ttk.Label(left_frame, textvariable=self.anime_status_score_var, 
                                            foreground="gray")
        anime_status_score_label.pack(anchor=tk.W)
        
        # Right side - Controls
        controls_frame = ttk.Frame(main_info)
        controls_frame.pack(side=tk.RIGHT, padx=(20, 0))
        
        # Progress control
        progress_frame = ttk.Frame(controls_frame)
        progress_frame.pack(pady=(0, 10))
        
        ttk.Label(progress_frame, text="Episodes:").pack(side=tk.LEFT)
        
        # Decrease button
        self.decrease_btn = ttk.Button(progress_frame, text="-", width=3,
                                      command=self._decrease_progress)
        self.decrease_btn.pack(side=tk.LEFT, padx=(5, 2))
        
        # Episode entry
        self.episode_var = tk.StringVar(value="0")
        self.episode_entry = ttk.Entry(progress_frame, textvariable=self.episode_var, 
                                      width=8, justify=tk.CENTER)
        self.episode_entry.pack(side=tk.LEFT, padx=2)
        self.episode_entry.bind('<Return>', self._on_episode_entry)
        self.episode_entry.bind('<FocusOut>', self._on_episode_entry)
        self.episode_entry.bind('<FocusIn>', self._on_episode_focus_in)
        self.episode_entry.bind('<KeyPress>', self._on_episode_key_press)
        
        # Total episodes label
        self.total_episodes_var = tk.StringVar(value="/ ?")
        ttk.Label(progress_frame, textvariable=self.total_episodes_var).pack(side=tk.LEFT, padx=(2, 5))
        
        # Increase button
        self.increase_btn = ttk.Button(progress_frame, text="+", width=3,
                                      command=self._increase_progress)
        self.increase_btn.pack(side=tk.LEFT, padx=(2, 5))
        
        # Score control
        score_frame = ttk.Frame(controls_frame)
        score_frame.pack()
        
        ttk.Label(score_frame, text="Score:").pack(side=tk.LEFT)
        
        self.score_var = tk.StringVar(value="Not scored")
        self.score_combo = ttk.Combobox(score_frame, textvariable=self.score_var,
                                       values=["Not scored"] + [str(i) for i in range(1, 11)],
                                       width=12, state="readonly")
        self.score_combo.pack(side=tk.LEFT, padx=(5, 0))
        self.score_combo.bind('<<ComboboxSelected>>', self._on_score_changed)
        
        # Initially disable controls
        self._set_compact_controls_enabled(False)
    
    def _create_content_area(self, parent):
        """Create main content area with notebook"""
        # Initialize variables needed for set_selected_anime method
        self.anime_name_var = tk.StringVar(value="No anime selected")
        self.anime_details_var = tk.StringVar(value="")
        self.anime_status_score_var = tk.StringVar(value="")
        self.selected_anime = None
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        # Anime List tab
        self.anime_list_frame = AnimeListFrame(self.notebook, self)
        self.notebook.add(self.anime_list_frame, text="Anime List")
        
        # Manga List tab
        self.manga_list_frame = MangaListFrame(self.notebook, self)
        self.notebook.add(self.manga_list_frame, text="Manga List")
        
        # Search tab
        self.search_frame = SearchFrame(self.notebook, self)
        self.notebook.add(self.search_frame, text="Search & Add")
    
    def _setup_monitoring(self):
        """Setup player monitoring callbacks"""
        self.player_monitor.on_episode_detected = self._on_episode_detected
        self.player_monitor.on_episode_watched = self._on_episode_watched
        self.player_monitor.on_player_closed = self._on_player_closed
    
    def _handle_auth(self):
        """Handle authentication"""
        if self.config.is_authenticated:
            # Already authenticated, offer to logout
            self.logger.info("User requested logout (already authenticated)")
            service_name = self.api_client.SERVICE_NAME
            if messagebox.askyesno("Logout", f"Do you want to logout from {service_name}?"):
                self._logout()
        else:
            # Show authentication dialog
            self.logger.info("User requested authentication")
            auth_dialog = SimpleAuthDialog(self.root, self.config, self.api_client)
            self.root.wait_window(auth_dialog.dialog)
            
            if self.config.is_authenticated:
                self.logger.info("Authentication successful, loading user data")
                self._load_user_data()
            else:
                self.logger.info("Authentication cancelled or failed")
    
    def _logout(self):
        """Logout from the active service"""
        username = self.current_user.get('nickname', 'Unknown') if self.current_user else 'Unknown'
        self.logger.info(f"Logging out user: {username}")
        
        service = self.config.active_service
        self.config.set(f'{service}.access_token', None)
        self.config.set(f'{service}.refresh_token', None)
        self.config.set(f'{service}.user_id', None)
        
        # Stop periodic updater
        self.anime_matcher.stop_periodic_updater()
        self.logger.info("Stopped periodic anime status updater")
        
        self.current_user = None
        self.anime_list_data.clear()
        
        self._update_auth_ui()
        self.anime_list_frame.clear_list()
        self._set_status("Logged out")
        self.logger.info("Logout completed successfully")
    
    def _load_user_data(self):
        """Load user data from the active service"""
        self.logger.info("Starting user data loading process")
        
        def load_data():
            try:
                self._set_status("Loading user data...")
                
                # Get current user
                self.logger.info(f"Fetching current user information from {self.api_client.SERVICE_NAME}")
                self.current_user = self.api_client.get_current_user()
                if not self.current_user:
                    self.logger.error(f"Failed to get user information from {self.api_client.SERVICE_NAME} API")
                    messagebox.showerror("Error", "Failed to get user information")
                    return
                
                username = self.current_user.get('nickname', 'Unknown')
                user_id = self.current_user.get('id', 'Unknown')
                self.logger.info(f"Successfully loaded user: {username} (ID: {user_id})")
                
                # Update UI on main thread
                self.root.after(0, self._update_auth_ui)
                
                # Load anime list
                self.logger.info("Loading anime list data")
                self._refresh_list_data()
                
                # Load manga list
                self.logger.info("Loading manga list data")
                self._refresh_manga_list_data()
                
                self.logger.info("User data loading completed successfully")
                
            except Exception as e:
                self.logger.error(f"Error loading user data: {str(e)}", exc_info=True)
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to load user data: {str(e)}"))
                self.root.after(0, lambda: self._set_status("Error loading data"))
        
        threading.Thread(target=load_data, daemon=True).start()
    
    def _refresh_list(self, force_refresh: bool = False):
        """Refresh anime list from the active service"""
        if not self.config.is_authenticated:
            self.logger.warning("Attempted to refresh anime list without authentication")
            messagebox.showwarning("Warning", "Please login first")
            return
        
        refresh_type = "forced" if force_refresh else "normal"
        self.logger.info(f"Starting anime list refresh ({refresh_type})")
        
        def refresh_data():
            try:
                self._refresh_list_data(force_refresh=force_refresh)
            except Exception as e:
                self.logger.error(f"Failed to refresh anime list: {str(e)}", exc_info=True)
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to refresh list: {str(e)}"))
                self.root.after(0, lambda: self._set_status("Error refreshing list"))
        
        threading.Thread(target=refresh_data, daemon=True).start()
    
    def _reload_from_cache(self):
        """Reload anime list from cache (for reflecting manual updates)"""
        if not self.current_user:
            return
        
        def reload_data():
            try:
                user_id = self.current_user['id']
                cached_data = self.cache_manager.load_anime_list(user_id)
                
                if cached_data:
                    self.anime_list_data = cached_data
                    total_anime = sum(len(anime_list) for anime_list in cached_data.values())
                    
                    # Update UI on main thread
                    self.root.after(0, lambda: self.anime_list_frame.update_list(self.anime_list_data))
                    self.root.after(0, lambda: self._set_status(f"Updated from cache - {total_anime} anime"))
                else:
                    # Fallback to full refresh if cache not available
                    self.root.after(0, lambda: self._refresh_list(force_refresh=True))
                    
            except Exception as e:
                self.logger.error(f"Error reloading from cache: {e}")
                # Fallback to full refresh on error
                self.root.after(0, lambda: self._refresh_list(force_refresh=True))
        
        threading.Thread(target=reload_data, daemon=True).start()
    
    def _refresh_list_data(self, force_refresh: bool = False):
        """Refresh anime list data (called from background thread)"""
        if not self.current_user:
            return
        
        user_id = self.current_user['id']
        
        # Try to load from cache first (unless forced refresh)
        if not force_refresh:
            self.root.after(0, lambda: self._set_status("Loading anime list from cache..."))
            cached_data = self.cache_manager.load_anime_list(user_id)
            
            if cached_data:
                self.anime_list_data = cached_data
                total_anime = sum(len(anime_list) for anime_list in cached_data.values())
                
                # Update UI on main thread
                self.root.after(0, lambda: self.anime_list_frame.update_list(self.anime_list_data))
                self.root.after(0, lambda: self._set_status(f"Anime list loaded from cache - {total_anime} anime"))
                
                # Initialize enhanced matching with synonyms
                if self.current_user:
                    self.anime_matcher.initialize_detailed_cache(self.current_user['id'], self.anime_list_data)
                    # Set callback for cache updates to refresh UI
                    self.anime_matcher.set_cache_updated_callback(self._on_detailed_cache_updated)
                    # Start periodic updater for non-released anime
                    self.anime_matcher.start_periodic_updater(self.current_user['id'])
                return
        
        # Load from API if no cache or forced refresh
        self.root.after(0, lambda: self._set_status("Refreshing anime list..."))
        
        total_anime = 0
        
        # Load all statuses
        for i, status_key in enumerate(self.api_client.STATUSES.keys()):
            status_display = self.api_client.STATUSES[status_key]
            self.root.after(0, lambda s=status_display: self._set_status(f"Loading {s} anime..."))
            
            anime_list = self.api_client.get_user_anime_list(user_id, status_key)
            self.anime_list_data[status_key] = anime_list
            total_anime += len(anime_list)
            
            # Update progress
            progress = f"Loaded {total_anime} anime so far..."
            self.root.after(0, lambda p=progress: self._set_status(p))
        
        # Save to cache
        self.cache_manager.save_anime_list(user_id, self.anime_list_data)
        
        # Clear episode tracking since anime progress might have changed
        if hasattr(self, 'updated_anime_episodes'):
            self.updated_anime_episodes.clear()
        else:
            self.updated_anime_episodes = set()
        
        # Update UI on main thread
        self.root.after(0, lambda: self.anime_list_frame.update_list(self.anime_list_data))
        self.root.after(0, lambda: self._set_status(f"Anime list updated - {total_anime} anime loaded"))
        
        # Initialize enhanced matching with synonyms
        if self.current_user:
            self.anime_matcher.initialize_detailed_cache(self.current_user['id'], self.anime_list_data)
            # Set callback for cache updates to refresh UI
            self.anime_matcher.set_cache_updated_callback(self._on_detailed_cache_updated)
            # Start periodic updater for non-released anime
            self.anime_matcher.start_periodic_updater(self.current_user['id'])
    
    def _update_auth_ui(self):
        """Update authentication UI elements"""
        self._update_window_title()
    
    def _update_window_title(self):
        """Update window title with user and monitoring status"""
        base_title = "Anime Updater"
        service_name = self.api_client.SERVICE_NAME
        
        if self.current_user:
            username = self.current_user.get('nickname', 'Unknown')
            scrobbling_status = "Active" if self.monitoring_active else "Passive"
            version = get_version_info()['version']
            title = f"{base_title} ({service_name}) - Logged as {username} - Scrobbling {scrobbling_status} - v{version}"
        else:
            version = get_version_info()['version']
            title = f"{base_title} ({service_name}) - Not logged in - v{version}"
        
        self.root.title(title)
    
    def _toggle_monitoring(self):
        """Toggle player monitoring"""
        if not self.config.is_authenticated:
            self.logger.warning("Attempted to toggle monitoring without authentication")
            messagebox.showwarning("Warning", "Please login first")
            return
        
        if self.monitoring_active:
            self.logger.info("Stopping player monitoring")
            self.player_monitor.stop_monitoring()
            self.monitoring_active = False
            self.current_anime_var.set("Now Watching: None")  # Clear current episode display
            self.logger.info("Player monitoring stopped successfully")
        else:
            self.logger.info("Starting player monitoring")
            self.player_monitor.start_monitoring()
            self.monitoring_active = True
            # Clear episode tracking when starting monitoring
            if hasattr(self, 'updated_anime_episodes'):
                self.updated_anime_episodes.clear()
            else:
                self.updated_anime_episodes = set()
            self.logger.info("Player monitoring started successfully")
        
        # Update window title with new monitoring status
        self._update_window_title()
    
    def _on_detailed_cache_updated(self):
        """Called when the detailed anime cache is updated by the periodic updater"""
        # Schedule UI refresh on the main thread
        self.root.after(0, lambda: self.anime_list_frame.update_list(self.anime_list_data))
        self.root.after(0, lambda: self._set_status("Anime status highlighting updated"))
    
    def _on_episode_detected(self, episode_info: EpisodeInfo):
        """Handle detected episode"""
        self.logger.info(f"Episode detected: {episode_info.anime_name} - Episode {episode_info.episode_number}")
        
        # Check if anime is in user's list (only active statuses)
        if self._is_anime_in_active_list(episode_info.anime_name):
            anime_display = f"Now Watching: {episode_info.anime_name} - Episode {episode_info.episode_number}"
            self.logger.info(f"Anime found in user's active list: {episode_info.anime_name}")
        else:
            anime_display = f"Anime not in active list: {episode_info.anime_name} - Episode {episode_info.episode_number}"
            self.logger.info(f"Anime not found in user's active list: {episode_info.anime_name}")
        
        self.root.after(0, lambda: self.current_anime_var.set(anime_display))
    
    def _on_episode_watched(self, episode_info: EpisodeInfo, watch_time: float):
        """Handle watched episode"""
        self.logger.info(f"Episode watched: {episode_info.anime_name} - Episode {episode_info.episode_number} (Watch time: {watch_time:.1f}s)")
        
        def process_episode():
            try:
                # Find matching anime in user's list - only consider active statuses
                # Filter out Completed and Dropped anime to avoid conflicts with multiple seasons
                active_statuses = ['watching', 'planned', 'rewatching', 'on_hold']
                all_anime = []
                for status_key in active_statuses:
                    if status_key in self.anime_list_data:
                        all_anime.extend(self.anime_list_data[status_key])
                
                self.logger.debug(f"Searching for anime match: {episode_info.anime_name}")
                match_result = self.anime_matcher.find_best_match(
                    episode_info.anime_name, all_anime, episode_info.episode_number)
                
                if match_result:
                    anime_entry, similarity = match_result
                    anime_data = anime_entry['anime']
                    anime_name = anime_data.get('name', episode_info.anime_name)
                    anime_id = anime_entry['id']
                    
                    self.logger.info(f"Anime match found: {anime_name} (ID: {anime_id}, Similarity: {similarity:.2f})")
                    
                    # Check if episode number is +1 from current progress
                    current_episodes = anime_entry.get('episodes', 0)
                    target_episode = episode_info.episode_number
                    
                    self.logger.info(f"Episode progress check: Current={current_episodes}, Target={target_episode}")
                    
                    # Check if this episode has already been updated for this anime
                    episode_key = f"{anime_id}_{target_episode}"
                    
                    # Allow update if episode is next (+1) or if current episode but not yet updated
                    # Defensive check - ensure updated_anime_episodes exists
                    if not hasattr(self, 'updated_anime_episodes'):
                        self.updated_anime_episodes = set()
                    already_updated = episode_key in self.updated_anime_episodes
                    
                    if already_updated:
                        self.logger.info(f"Episode {target_episode} already updated for {anime_name}, skipping")
                    
                    if (target_episode == current_episodes + 1):
                        # Update progress
                        rate_id = anime_entry['id']
                        anime_data = anime_entry['anime']
                        total_episodes = anime_data.get('episodes', 0)
                        
                        # Determine new status
                        current_status = anime_entry.get('status', '')
                        new_status = None
                        
                        self.logger.info(f"Status determination: Current status={current_status}, Total episodes={total_episodes}")
                        
                        # Check if anime is in Plan to Watch and should be moved to Watching
                        if current_status == 'planned' and target_episode > 0:
                            new_status = 'watching'
                            self.logger.info(f"Status change: {current_status} -> {new_status} (started watching)")
                        elif total_episodes > 0 and target_episode >= total_episodes:
                            # Check if anime is scored
                            current_score = anime_entry.get('score', 0)
                            if current_score > 0:
                                new_status = 'completed'
                                self.logger.info(f"Status change: {current_status} -> {new_status} (completed, has score)")
                            else:
                                self.logger.info(f"Anime finished but no score set, keeping status as {current_status}")
                        
                        # Update on the active service
                        self.logger.info(f"Updating anime progress: {anime_name} -> Episode {target_episode}" + 
                                       (f", Status: {new_status}" if new_status else ""))
                        success = self.api_client.update_anime_progress(
                            rate_id, target_episode, status=new_status)
                        
                        if success:
                            anime_name = anime_data.get('name', episode_info.anime_name)
                            message = f"Updated {anime_name} to episode {target_episode}"
                            if new_status == 'completed':
                                message += " (Completed)"
                            elif current_status == 'planned' and new_status == 'watching':
                                message += " (Moved to Watching)"
                            
                            self.logger.info(f"Anime progress update successful: {message}")
                            self.root.after(0, lambda: self._set_status(message))
                            # Mark this episode as updated
                            self.updated_anime_episodes.add(episode_key)
                            
                            # Update only this specific anime in the list instead of full refresh
                            # Update the local data first
                            anime_entry['episodes'] = target_episode
                            if new_status:
                                anime_entry['status'] = new_status
                            
                            # Update cache with the modified data
                            if self.current_user:
                                self.cache_manager.save_anime_list(self.current_user['id'], self.anime_list_data)
                                self.logger.debug("Anime list cache updated after scrobbling")
                            
                            # Send Telegram notification for scrobbling update
                            if self.current_user:
                                username = self.current_user.get('nickname', 'Unknown')
                                anime_url = anime_data.get('url', '')
                                
                                if new_status == 'completed':
                                    # Check if this is a rewatch completion
                                    old_status = anime_entry.get('status', '')
                                    is_rewatch = old_status == 'rewatching'
                                    rewatch_count = 0
                                    
                                    if is_rewatch:
                                        # Get current rewatch count (this would be updated by the API call)
                                        rewatch_count = anime_entry.get('rewatches', 0) + 1
                                    
                                    self.logger.info(f"Sending completion Telegram notification for {anime_name}" + 
                                                   (f" (rewatch #{rewatch_count})" if is_rewatch else ""))
                                    
                                    # Send completion notification
                                    score = anime_entry.get('score', 0)
                                    comment = anime_entry.get('text', '') or anime_entry.get('text_html', '')
                                    self.telegram_notifier.send_completion_update(anime_name, score, username, is_rewatch, rewatch_count, anime_url, comment)
                                else:
                                    # Send progress notification
                                    total_episodes = anime_data.get('episodes', 0)
                                    self.logger.info(f"Sending progress Telegram notification for {anime_name} episode {target_episode}")
                                    self.telegram_notifier.send_progress_update(anime_name, target_episode, total_episodes, username, anime_url)
                            
                            self.root.after(0, lambda: self._update_single_anime(anime_entry))
                        else:
                            error_msg = f"Failed to update {episode_info.anime_name}"
                            self.logger.error(f"Anime progress update failed: {error_msg}")
                            self.root.after(0, lambda: self._set_status(error_msg))
                    else:
                        warn_msg = f"Episode {target_episode} is not next for {episode_info.anime_name} (current: {current_episodes})"
                        self.logger.warning(f"Episode validation failed: {warn_msg}")
                        self.root.after(0, lambda: self._set_status(warn_msg))
                else:
                    warn_msg = f"No match found for {episode_info.anime_name}"
                    self.logger.warning(f"Anime matching failed: {warn_msg}")
                    self.root.after(0, lambda: self._set_status(warn_msg))
                    
            except Exception as e:
                error_msg = f"Error processing episode: {str(e)}"
                self.logger.error(f"Episode processing error: {error_msg}", exc_info=True)
                self.root.after(0, lambda: self._set_status(error_msg))
        
        threading.Thread(target=process_episode, daemon=True).start()
    
    def _is_anime_in_list(self, anime_name: str) -> bool:
        """Check if anime is in user's list using fuzzy matching"""
        if not self.anime_list_data:
            return False
        
        # Get all anime from user's list
        all_anime = []
        for anime_list in self.anime_list_data.values():
            all_anime.extend(anime_list)
        
        # Use anime matcher to find if there's a match
        match_result = self.anime_matcher.find_best_match(anime_name, all_anime)
        return match_result is not None
    
    def _on_player_closed(self):
        """Handle when player is closed - clear the monitoring panel"""
        # Always clear the panel when any player closes for now
        self.current_anime_var.set("Now Watching: None")
    
    def _set_status(self, message: str, auto_clear: bool = True):
        """Set status bar message"""
        self.status_var.set(message)
        # Auto-clear status after 10 seconds if requested
        if auto_clear and not message.startswith(("Loading", "Loaded", "Refreshing")):
            self.root.after(10000, lambda: self.status_var.set("") 
                           if self.status_var.get() == message else None)
    
    def _on_closing(self):
        """Handle window closing"""
        # Check if should close to tray
        if self.config.get('ui.close_to_tray', False) and TRAY_AVAILABLE:
            self._hide_to_tray()
            return
        
        self._actually_close()
    
    def _actually_close(self):
        """Actually close the application"""
        # Save window position
        geometry = self.root.geometry()
        parts = geometry.split('+')
        if len(parts) >= 3:
            size = parts[0]
            x = parts[1]
            y = parts[2]
            
            width, height = size.split('x')
            self.config.set('window.width', int(width))
            self.config.set('window.height', int(height))
            self.config.set('window.x', int(x))
            self.config.set('window.y', int(y))
        
        # Stop monitoring
        if self.monitoring_active:
            self.player_monitor.stop_monitoring()
        
        # Stop notification monitoring
        if hasattr(self, 'notification_manager'):
            self.notification_manager.stop_monitoring()
        
        # Stop periodic updater
        if hasattr(self, 'anime_matcher'):
            self.anime_matcher.stop_periodic_updater()
        
        # Stop API server
        if hasattr(self, 'api_server') and self.api_server:
            self.api_server.stop()
        
        # Stop system tray
        if self.tray_icon and hasattr(self.tray_icon, 'stop'):
            try:
                self.tray_icon.stop()
            except:
                pass
        
        # Stop update check timer
        self._stop_update_check_timer()
        
        self.root.destroy()
    
    @staticmethod
    def _create_active_client(config):
        """Factory: return the appropriate API client based on config."""
        service = config.get('service.active', 'shikimori')
        if service == 'mal':
            return MALClient(config)
        return ShikimoriClient(config)

    # Public methods for other components
    def get_active_client(self):
        """Get the currently active API client instance"""
        return self.api_client

    def get_shikimori_client(self):
        """Legacy alias -- returns the active client regardless of service."""
        return self.api_client

    def on_service_changed(self):
        """Called after the active service has been switched in config.
        Re-creates the API client and reloads data if authenticated."""
        self.api_client = self._create_active_client(self.config)
        self.anime_matcher = EnhancedAnimeMatcher(self.api_client, self.cache_manager)
        from utils.notification_manager import NotificationManager
        self.notification_manager = NotificationManager(self.config, self.api_client, self.cache_manager)

        self.current_user = None
        self.anime_list_data.clear()
        self.manga_list_data.clear()
        self.anime_list_frame.clear_list()
        self.manga_list_frame.clear_list()

        if self.config.is_authenticated:
            self._load_user_data()

        self._update_window_title()
        self._set_status(f"Switched to {self.api_client.SERVICE_NAME}")

    def get_anime_list_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get current anime list data"""
        return self.anime_list_data
    
    def refresh_anime_list(self):
        """Public method to refresh anime list (forces full refresh and cache rebuild)"""
        self._refresh_list(force_refresh=True)
    
    # Anime info panel methods
    def set_selected_anime(self, anime_entry: Optional[Dict[str, Any]]):
        """Set the currently selected anime in the info panel"""
        # If we're changing selection and there are pending changes, apply them to the current anime first
        if hasattr(self, 'selected_anime') and hasattr(self, 'episode_editing_anime') and self.selected_anime and anime_entry != self.selected_anime:
            self._commit_pending_episode_changes()
        
        self.selected_anime = anime_entry
        
        if anime_entry:
            anime = anime_entry.get('anime', {})
            
            # Update compact panel
            name = anime.get('name', 'Unknown')
            # Truncate long names for compact display
            if len(name) > 50:
                display_name = name[:47] + "..."
            else:
                display_name = name
            self.compact_anime_name_var.set(display_name)
            
            # Update detailed info panel
            self.anime_name_var.set(name)
            
            # First row: Type and Year
            anime_type = anime.get('kind', 'Unknown').upper()
            aired_on = anime.get('aired_on', '')
            year = aired_on[:4] if aired_on else 'Unknown'
            type_year_info = f"Type: {anime_type} | Year: {year}"
            self.anime_details_var.set(type_year_info)
            
            # Second row: Status and Score
            status = anime_entry.get('status', '')
            status_display = self.api_client.STATUSES.get(status, 'Unknown') if status in self.api_client.STATUSES else 'Unknown'
            score = anime_entry.get('score', 0)
            score_display = str(score) if score > 0 else 'Not scored'
            status_score_info = f"Status: {status_display} | Score: {score_display}"
            self.anime_status_score_var.set(status_score_info)
            
            # Update progress in compact panel
            current_episodes = anime_entry.get('episodes', 0)
            total_episodes = anime.get('episodes', 0)
            self.compact_episode_var.set(str(current_episodes))
            self.compact_total_episodes_var.set(f"/{total_episodes if total_episodes else '?'}")
            
            # Note: Main episode entry removed - only using compact panel
            
            # Update status in compact panel
            status = anime_entry.get('status', '')
            if status in self.api_client.STATUSES:
                status_display = self.api_client.STATUSES[status]
                self.compact_status_var.set(status_display)
            else:
                self.compact_status_var.set("-")
            
            # Update score in compact panel
            score = anime_entry.get('score', 0)
            if score > 0:
                self.compact_score_var.set(str(score))
            else:
                self.compact_score_var.set("-")
            
            # Enable compact controls
            self._set_compact_controls_enabled(True)
        else:
            # Clear compact selection
            self.compact_anime_name_var.set("None")
            self.compact_episode_var.set("0")
            self.compact_total_episodes_var.set("/?")
            self.compact_status_var.set("-")
            self.compact_score_var.set("-")
            
            # Clear detailed info panel
            self.anime_name_var.set("No anime selected")
            self.anime_details_var.set("")
            self.anime_status_score_var.set("")
            
            # Disable compact controls
            self._set_compact_controls_enabled(False)
    
    def _set_controls_enabled(self, enabled: bool):
        """Enable or disable the anime controls (placeholder - only compact controls used)"""
        pass
    
    def _decrease_progress(self):
        """Decrease episode progress by 1"""
        if not self.selected_anime:
            return
        
        try:
            current = int(self.compact_episode_var.get())
            new_value = max(0, current - 1)
            self.compact_episode_var.set(str(new_value))
            self._update_progress(new_value)
        except ValueError:
            pass
    
    def _increase_progress(self):
        """Increase episode progress by 1"""
        if not self.selected_anime:
            return
        
        try:
            current = int(self.compact_episode_var.get())
            total = self.selected_anime['anime'].get('episodes', 9999)
            new_value = min(total if total else 9999, current + 1)
            self.compact_episode_var.set(str(new_value))
            self._update_progress(new_value)
        except ValueError:
            pass
    
    # Main episode entry methods removed - only using compact panel now
    
    # Main score change method removed - only using compact panel now
    
    def _commit_pending_episode_changes(self):
        """Commit any pending episode changes before changing selection"""
        if hasattr(self, 'episode_editing_anime') and self.episode_editing_anime and hasattr(self, 'episode_editing_original_value') and self.episode_editing_original_value is not None:
            try:
                current_value = self.compact_episode_var.get()
                if current_value != self.episode_editing_original_value:
                    new_value = int(current_value)
                    total = self.episode_editing_anime['anime'].get('episodes', 9999)
                    new_value = max(0, min(total if total else 9999, new_value))
                    
                    current_episodes = self.episode_editing_anime.get('episodes', 0)
                    if new_value != current_episodes:
                        self._update_progress_for_anime(self.episode_editing_anime, new_value)
            except ValueError:
                pass
            
            # Clear editing state
            self.episode_editing_anime = None
            self.episode_editing_original_value = None
    
    def _update_progress(self, episodes: int):
        """Update anime progress on the active service"""
        if not self.selected_anime:
            return
        
        self._update_progress_for_anime(self.selected_anime, episodes)
    
    def _update_progress_for_anime(self, anime_entry: Dict[str, Any], episodes: int):
        """Update anime progress on the active service for specific anime"""
        if not anime_entry:
            return
        
        def update_data():
            try:
                rate_id = anime_entry['id']
                anime_name = anime_entry['anime'].get('name', 'Unknown')
                
                # Check if should auto-complete or change status
                total_episodes = anime_entry['anime'].get('episodes', 0)
                current_score = anime_entry.get('score', 0)
                current_status = anime_entry.get('status', '')
                new_status = None
                rewatches_increment = 0
                
                # Check if anime is in Plan to Watch and should be moved to Watching
                if current_status == 'planned' and episodes > 0:
                    new_status = 'watching'
                # Special logic for Rewatching status
                elif current_status == 'rewatching' and total_episodes > 0 and episodes >= total_episodes:
                    # Auto-complete from Rewatching and increment rewatches
                    new_status = 'completed'
                    rewatches_increment = 1
                elif total_episodes > 0 and episodes >= total_episodes and current_score > 0:
                    new_status = 'completed'
                
                # Prepare rewatches field for API call
                additional_fields = {}
                if rewatches_increment > 0:
                    current_rewatches = anime_entry.get('rewatches', 0) or 0
                    additional_fields['rewatches'] = current_rewatches + rewatches_increment
                
                success = self.api_client.update_anime_progress(
                    rate_id, episodes=episodes, status=new_status, **additional_fields)
                
                if success:
                    message = f"Updated {anime_name} to episode {episodes}"
                    if new_status == 'completed':
                        message += " (Completed)"
                    elif current_status == 'planned' and new_status == 'watching':
                        message += " (Moved to Watching)"
                    
                    self.root.after(0, lambda: self._set_status(message))
                    
                    # Send Telegram notification for rewatch completion
                    if self.current_user and new_status == 'completed' and rewatches_increment > 0:
                        username = self.current_user.get('nickname', 'Unknown')
                        anime_url = anime_entry['anime'].get('url', '')
                        score = anime_entry.get('score', 0)
                        
                        # Send immediate rewatch notification with incremented count
                        # The cache will be updated by the _update_cache_and_reload call below
                        current_rewatches = anime_entry.get('rewatches', 0) or 0
                        new_rewatch_count = current_rewatches + rewatches_increment
                        
                        self.telegram_notifier.send_completion_update(
                            anime_name, score, username, True, new_rewatch_count, anime_url
                        )
                    
                    # Update cache directly and reload from cache
                    if self.current_user:
                        anime_id = anime_entry['id']
                        update_data = {'episodes': episodes}
                        if new_status:
                            update_data['status'] = new_status
                        if rewatches_increment > 0:
                            # Also update rewatch count in cache
                            current_rewatches = anime_entry.get('rewatches', 0) or 0
                            update_data['rewatches'] = current_rewatches + rewatches_increment
                        
                        # Update cache and reload
                        self._update_cache_and_reload(anime_id, update_data)
                else:
                    self.root.after(0, lambda: self._set_status(f"Failed to update {anime_name}"))
                    # Reset to previous value
                    prev_episodes = anime_entry.get('episodes', 0)
                    self.root.after(0, lambda: self.compact_episode_var.set(str(prev_episodes)))
                    
            except Exception as e:
                self.root.after(0, lambda: self._set_status(f"Error updating progress: {str(e)}"))
        
        threading.Thread(target=update_data, daemon=True).start()
    
    def _update_score(self, score: int):
        """Update anime score on the active service"""
        if not self.selected_anime:
            return
        
        def update_data():
            try:
                rate_id = self.selected_anime['id']
                anime_name = self.selected_anime['anime'].get('name', 'Unknown')
                
                # Check if should auto-complete when score is set
                current_episodes = self.selected_anime.get('episodes', 0)
                total_episodes = self.selected_anime['anime'].get('episodes', 0)
                current_status = self.selected_anime.get('status', '')
                new_status = None
                
                # Auto-complete if score is being set and episodes are at max
                if score > 0 and total_episodes > 0 and current_episodes >= total_episodes and current_status != 'completed':
                    new_status = 'completed'
                
                success = self.api_client.update_anime_progress(
                    rate_id, episodes=current_episodes, score=score, status=new_status)
                
                if success:
                    if score > 0:
                        message = f"Set {anime_name} score to {score}"
                        if new_status == 'completed':
                            message += " (Auto-completed)"
                        self.root.after(0, lambda: self._set_status(message))
                    else:
                        self.root.after(0, lambda: self._set_status(f"Removed score for {anime_name}"))
                    
                    # Send Telegram notification for auto-completion
                    if self.current_user and new_status == 'completed':
                        username = self.current_user.get('nickname', 'Unknown')
                        anime_url = self.selected_anime['anime'].get('url', '')
                        self.telegram_notifier.send_completion_update(
                            anime_name, score, username, False, 0, anime_url
                        )
                    
                    # Update cache directly and reload from cache
                    if self.current_user:
                        anime_id = self.selected_anime['id']
                        update_data = {'score': score}
                        if new_status:
                            update_data['status'] = new_status
                        self._update_cache_and_reload(anime_id, update_data)
                else:
                    self.root.after(0, lambda: self._set_status(f"Failed to update {anime_name} score"))
                    # Reset to previous value
                    prev_score = self.selected_anime.get('score', 0)
                    if prev_score > 0:
                        self.root.after(0, lambda: self.compact_score_var.set(str(prev_score)))
                    else:
                        self.root.after(0, lambda: self.compact_score_var.set("-"))
                    
            except Exception as e:
                self.root.after(0, lambda: self._set_status(f"Error updating score: {str(e)}"))
        
        threading.Thread(target=update_data, daemon=True).start()
    
    def _set_compact_controls_enabled(self, enabled: bool):
        """Enable or disable the compact anime/manga controls"""
        state = tk.NORMAL if enabled else tk.DISABLED
        readonly_state = "readonly" if enabled else tk.DISABLED
        
        # Episode/Chapter controls
        self.compact_episode_entry.config(state=state)
        self.compact_decrease_btn.config(state=state)
        self.compact_increase_btn.config(state=state)
        
        # Volume controls (only visible in manga mode)
        if hasattr(self, 'compact_volume_entry'):
            self.compact_volume_entry.config(state=state)
            self.compact_volume_decrease_btn.config(state=state)
            self.compact_volume_increase_btn.config(state=state)
        
        # Status and score controls
        self.compact_status_combo.config(state=readonly_state)
        self.compact_score_combo.config(state=readonly_state)
    
    def _on_compact_episode_focus_in(self, event=None):
        """Handle when compact episode entry gets focus - record which anime we're editing"""
        if self.selected_anime:
            # Initialize editing attributes if they don't exist
            if not hasattr(self, 'episode_editing_anime'):
                self.episode_editing_anime = None
            if not hasattr(self, 'episode_editing_original_value'):
                self.episode_editing_original_value = None
            
            self.episode_editing_anime = self.selected_anime
            self.episode_editing_original_value = self.compact_episode_var.get()
    
    def _on_compact_episode_key_press(self, event=None):
        """Handle key press in compact episode entry - mark that we're editing"""
        if self.selected_anime:
            # Initialize editing attributes if they don't exist
            if not hasattr(self, 'episode_editing_anime'):
                self.episode_editing_anime = None
            
            self.episode_editing_anime = self.selected_anime
    
    def _on_compact_episode_entry(self, event=None):
        """Handle manual episode entry in compact panel"""
        # Use the anime we started editing, not the currently selected one
        target_anime = self.episode_editing_anime if self.episode_editing_anime else self.selected_anime
        
        if not target_anime:
            return
        
        try:
            new_value = int(self.compact_episode_var.get())
            total = target_anime['anime'].get('episodes', 9999)
            new_value = max(0, min(total if total else 9999, new_value))
            
            # Only update if the value actually changed
            current = target_anime.get('episodes', 0)
            if new_value != current:
                self.compact_episode_var.set(str(new_value))
                self._update_progress_for_anime(target_anime, new_value)
            
            # Clear editing state
            if hasattr(self, 'episode_editing_anime'):
                self.episode_editing_anime = None
            if hasattr(self, 'episode_editing_original_value'):
                self.episode_editing_original_value = None
            
        except ValueError:
            # Reset to original value if invalid
            if self.episode_editing_original_value is not None:
                self.compact_episode_var.set(self.episode_editing_original_value)
            else:
                current = target_anime.get('episodes', 0)
                self.compact_episode_var.set(str(current))
            
            # Clear editing state
            if hasattr(self, 'episode_editing_anime'):
                self.episode_editing_anime = None
            if hasattr(self, 'episode_editing_original_value'):
                self.episode_editing_original_value = None
    
    def _on_compact_score_changed(self, event=None):
        """Handle score change in compact panel"""
        if not self.selected_anime:
            return
        
        score_text = self.compact_score_var.get()
        if score_text == "-":
            score = 0
        else:
            try:
                score = int(score_text)
            except ValueError:
                return
        
        self._update_score(score)
    
    def _on_compact_status_changed(self, event=None):
        """Handle status change in compact panel"""
        if not self.selected_anime:
            return
        
        status_text = self.compact_status_var.get()
        if status_text == "-":
            return
        
        # Convert status display back to API key
        status_map = {v: k for k, v in self.api_client.STATUSES.items()}
        new_status_key = status_map.get(status_text)
        
        if new_status_key:
            self._update_status(new_status_key)
    
    def _update_status(self, status: str):
        """Update anime status on the active service"""
        if not self.selected_anime:
            return
        
        def update_data():
            try:
                rate_id = self.selected_anime['id']
                anime_name = self.selected_anime['anime'].get('name', 'Unknown')
                
                # Special handling for Rewatching status
                episodes_to_update = self.selected_anime.get('episodes', 0)
                if status == 'rewatching':
                    episodes_to_update = 0  # Set episodes to 0 when changing to Rewatching
                
                success = self.api_client.update_anime_progress(
                    rate_id, episodes=episodes_to_update, status=status)
                
                if success:
                    status_display = self.api_client.STATUSES.get(status, status)
                    message = f"Changed {anime_name} status to {status_display}"
                    if status == 'rewatching':
                        message += " (episodes reset to 0)"
                    self.root.after(0, lambda: self._set_status(message))
                    
                    # Send Telegram notification for manual status changes
                    if self.current_user:
                        username = self.current_user.get('nickname', 'Unknown')
                        old_status = self.selected_anime.get('status', '')
                        old_status_display = self.api_client.STATUSES.get(old_status, old_status)
                        score = self.selected_anime.get('score', 0)
                        anime_url = self.selected_anime['anime'].get('url', '')
                        
                        if status in ['dropped', 'rewatching']:
                            # Get comment from the selected anime
                            comment = self.selected_anime.get('text', '') or self.selected_anime.get('text_html', '')
                            self.telegram_notifier.send_status_change_update(
                                anime_name, old_status_display, status, score, username, anime_url, comment
                            )
                        elif status == 'completed':
                            # Check if this is completing from rewatching
                            is_rewatch = old_status == 'rewatching'
                            rewatch_count = 0
                            if is_rewatch:
                                rewatch_count = self.selected_anime.get('rewatches', 0) + 1
                            
                            self.telegram_notifier.send_completion_update(
                                anime_name, score, username, is_rewatch, rewatch_count, anime_url
                            )
                    
                    # Update cache directly and reload from cache
                    if self.current_user:
                        anime_id = self.selected_anime['id']
                        update_data = {'status': status}
                        if status == 'rewatching':
                            update_data['episodes'] = 0
                        self._update_cache_and_reload(anime_id, update_data)
                else:
                    self.root.after(0, lambda: self._set_status(f"Failed to update {anime_name} status"))
                    # Reset to previous value
                    prev_status = self.selected_anime.get('status', '')
                    if prev_status in self.api_client.STATUSES:
                        prev_status_display = self.api_client.STATUSES[prev_status]
                        self.root.after(0, lambda: self.compact_status_var.set(prev_status_display))
                    else:
                        self.root.after(0, lambda: self.compact_status_var.set("-"))
                    
            except Exception as e:
                self.root.after(0, lambda: self._set_status(f"Error updating status: {str(e)}"))
        
        threading.Thread(target=update_data, daemon=True).start()
    
    def _add_anime_cache_and_reload(self, anime_entry: Dict[str, Any]):
        """Add anime to cache and reload from cache to reflect changes"""
        def add_and_reload():
            if self.current_user:
                user_id = self.current_user['id']
                # Add the anime to cache
                cache_updated = self.cache_manager.add_anime_to_cache(user_id, anime_entry)
                
                if cache_updated:
                    # Reload from updated cache
                    self.root.after(0, self._reload_from_cache)
                else:
                    # Fallback to full refresh if cache update failed
                    self.root.after(0, lambda: self._refresh_list(force_refresh=True))
        
        threading.Thread(target=add_and_reload, daemon=True).start()
    
    def _update_cache_and_reload(self, anime_id: int, updates: Dict[str, Any]):
        """Update cache directly and reload from cache to reflect changes"""
        def update_and_reload():
            if self.current_user:
                user_id = self.current_user['id']
                # Update the cache file directly
                cache_updated = self.cache_manager.update_anime_in_cache(user_id, anime_id, updates)
                
                if cache_updated:
                    # Reload from updated cache
                    self.root.after(0, self._reload_from_cache)
                else:
                    # Fallback to full refresh if cache update failed
                    self.root.after(0, lambda: self._refresh_list(force_refresh=True))
        
        threading.Thread(target=update_and_reload, daemon=True).start()
    
    
    def _setup_system_tray(self):
        """Setup system tray icon and menu"""
        if not TRAY_AVAILABLE:
            print("System tray not available - skipping setup")
            return
        
        try:
            # Try to load custom icon first
            image = self._load_tray_icon()
            
            if not image:
                # Fallback: Create a more visible icon with better contrast
                image = Image.new('RGBA', (32, 32), (0, 0, 0, 0))  # Transparent background
                draw = ImageDraw.Draw(image)
                
                # Draw a blue circle background
                draw.ellipse([2, 2, 30, 30], fill='#0078D4', outline='#005A9E', width=2)
                
                # Draw the letter 'S' in white
                try:
                    # Try to use a built-in font
                    from PIL import ImageFont
                    font = ImageFont.load_default()
                    # Calculate text position to center it
                    bbox = draw.textbbox((0, 0), 'S', font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    x = (32 - text_width) // 2
                    y = (32 - text_height) // 2 - 2
                    draw.text((x, y), 'A', fill='white', font=font)
                except:
                    # Fallback to simple text without font
                    draw.text((10, 8), 'A', fill='white')
            
            # Create tray menu
            menu = pystray.Menu(
                pystray.MenuItem("Show Window", self._show_from_tray, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Start/Stop Scrobbling", self._toggle_monitoring_from_tray),
                pystray.MenuItem("Refresh List", self._refresh_from_tray),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Exit", self._exit_from_tray)
            )
            
            # Create tray icon with double-click handler
            self.tray_icon = pystray.Icon(
                "Anime Updater",
                image,
                "Anime Updater - Double-click to show",
                menu
            )
            
            # Set double-click action to show window
            self.tray_icon.default_action = self._show_from_tray
            
            print("System tray icon created successfully")
            
        except Exception as e:
            print(f"Failed to setup system tray: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_minimize(self, event):
        """Handle window minimize event"""
        if (event.widget == self.root and 
            self.config.get('ui.minimize_to_tray', False) and 
            TRAY_AVAILABLE):
            
            # Use a delay to ensure the window state has changed
            self.root.after(100, self._check_and_hide_to_tray)
    
    def _on_restore(self, event):
        """Handle window restore event"""
        if event.widget == self.root:
            self.window_minimized = False
    
    def _check_and_hide_to_tray(self):
        """Check if window is iconified and hide to tray if needed"""
        if self.root.state() == 'iconic' and TRAY_AVAILABLE:
            self._hide_to_tray()
    
    def _hide_to_tray(self):
        """Hide window to system tray"""
        if not TRAY_AVAILABLE:
            print("Cannot hide to tray - functionality not available")
            return
        
        if not self.tray_icon:
            print("Cannot hide to tray - tray icon not initialized")
            return
        
        try:
            self.root.withdraw()
            self.window_minimized = True
            
            if not hasattr(self.tray_icon, '_running') or not self.tray_icon._running:
                # Start tray icon in a separate thread
                self.tray_icon._running = True
                print("Starting system tray icon...")
                
                def run_tray():
                    try:
                        self.tray_icon.run()
                    except Exception as e:
                        print(f"Error running tray icon: {e}")
                
                threading.Thread(target=run_tray, daemon=True).start()
            else:
                print("Tray icon already running")
            
        except Exception as e:
            print(f"Error hiding to tray: {e}")
            import traceback
            traceback.print_exc()
    
    def _show_from_tray(self, icon=None, item=None):
        """Show window from system tray"""
        print("Show from tray called")
        self.root.after(0, self._restore_window)
    
    def _restore_window(self):
        """Restore window from tray"""
        print("Restoring window from tray")
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            self.root.attributes('-topmost', True)
            self.root.after(100, lambda: self.root.attributes('-topmost', False))
            self.window_minimized = False
            print("Window restored successfully")
        except Exception as e:
            print(f"Error restoring window: {e}")
    
    def _toggle_monitoring_from_tray(self, icon=None, item=None):
        """Toggle monitoring from tray menu"""
        self.root.after(0, self._toggle_monitoring)
    
    def _refresh_from_tray(self, icon=None, item=None):
        """Refresh anime list from tray menu"""
        self.root.after(0, lambda: self._refresh_list(force_refresh=True))
    
    def _exit_from_tray(self, icon=None, item=None):
        """Exit application from tray menu"""
        print("Exit from tray called")
        # Stop the tray icon first
        if self.tray_icon and hasattr(self.tray_icon, 'stop'):
            try:
                self.tray_icon.stop()
            except:
                pass
        self.root.after(0, self._actually_close)
    
    def _clear_cache(self):
        """Clear anime list cache"""
        if not self.current_user:
            messagebox.showwarning("Warning", "Please login first")
            return
        
        if messagebox.askyesno("Clear Cache", "Are you sure you want to clear the anime list cache?"):
            self.cache_manager.clear_cache(self.current_user['id'])
            self._set_status("Cache cleared")
    
    def _refresh_synonyms(self):
        """Force refresh synonym cache for better anime matching"""
        if not self.current_user or not self.anime_list_data:
            messagebox.showwarning("Warning", "Please login and load anime list first")
            return
        
        if messagebox.askyesno("Refresh Synonyms", 
                              "This will re-download detailed anime info including synonyms for better matching.\n\n"
                              "This may take a few minutes. Continue?"):
            self.anime_matcher.force_refresh_synonyms(self.current_user['id'], self.anime_list_data)
            self._set_status("Refreshing synonyms in background...")
    
    def _show_options(self):
        """Show options dialog"""
        options_dialog = OptionsDialog(self.root, self.config, main_window=self)
        self.root.wait_window(options_dialog.dialog)
        
        if options_dialog.changes_made:
            # Update player monitor with new settings
            self.player_monitor.min_watch_time = self.config.get('monitoring.min_watch_time', 60)
            
            # Check if auto-start monitoring is enabled and we're logged in
            if self.config.get('monitoring.auto_start', False) and self.config.is_authenticated and not self.monitoring_active:
                self._toggle_monitoring()
    
    def _toggle_dark_theme(self):
        """Toggle between light and dark themes"""
        # Get current theme state and toggle it
        current_dark_theme = self.config.get('ui.dark_theme', False)
        new_dark_theme = not current_dark_theme
        
        # Save the new preference
        self.config.set('ui.dark_theme', new_dark_theme)
        
        # Apply the new theme
        self.modern_style.switch_theme(new_dark_theme)
        
        # Update anime list highlighting for the new theme
        if hasattr(self, 'anime_list_frame'):
            self.anime_list_frame._configure_anime_status_tags()
        
        # Apply title bar theme with delay
        self.root.after(100, self.modern_style._apply_title_bar_theme)
        
        # Update status
        theme_name = "dark" if new_dark_theme else "light"
        self._set_status(f"Switched to {theme_name} theme")
    
    def _show_log_viewer(self):
        """Show log viewer window"""
        try:
            from utils.logger import get_log_file_path
            log_file = get_log_file_path()
            
            # Create log viewer window
            log_window = tk.Toplevel(self.root)
            log_window.title("Application Logs")
            log_window.geometry("800x600")
            
            # Apply modern styling
            dark_theme = self.config.get('ui.dark_theme', False)
            modern_style = ModernStyle(log_window, dark_theme=dark_theme)
            
            # Create main frame
            main_frame = ttk.Frame(log_window, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Log file path info
            info_frame = ttk.Frame(main_frame)
            info_frame.pack(fill=tk.X, pady=(0, 10))
            
            ttk.Label(info_frame, text=f"Log file: {log_file}", font=("Arial", 9)).pack(anchor=tk.W)
            
            # Text widget with scrollbar
            text_frame = ttk.Frame(main_frame)
            text_frame.pack(fill=tk.BOTH, expand=True)
            
            text_widget = tk.Text(text_frame, wrap=tk.NONE, font=("Consolas", 9))
            
            # Scrollbars
            v_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
            h_scrollbar = ttk.Scrollbar(text_frame, orient=tk.HORIZONTAL, command=text_widget.xview)
            text_widget.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
            
            # Pack widgets
            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
            
            # Load log content with robust encoding handling
            def load_log_content():
                try:
                    # Try UTF-8 first
                    with open(log_file, 'r', encoding='utf-8') as f:
                        return f.read()
                except UnicodeDecodeError:
                    try:
                        # Try with UTF-8 and error handling
                        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                            content = f.read()
                            # Add warning about encoding issues
                            warning = "⚠️  WARNING: Log file contains encoding issues. Some characters may be displayed incorrectly.\n\n"
                            return warning + content
                    except Exception:
                        try:
                            # Fallback to system default encoding
                            with open(log_file, 'r', encoding='cp1252', errors='replace') as f:
                                content = f.read()
                                warning = "⚠️  WARNING: Log file read with Windows-1252 encoding. Some characters may be displayed incorrectly.\n\n"
                                return warning + content
                        except Exception:
                            # Last resort: read as binary and decode with errors
                            with open(log_file, 'rb') as f:
                                raw_content = f.read()
                                content = raw_content.decode('utf-8', errors='replace')
                                warning = "⚠️  WARNING: Log file read in binary mode. Some characters may be displayed incorrectly.\n\n"
                                return warning + content
            
            try:
                content = load_log_content()
                if content:
                    text_widget.insert(tk.END, content)
                    # Scroll to bottom
                    text_widget.see(tk.END)
                else:
                    text_widget.insert(tk.END, "Log file is empty.")
            except FileNotFoundError:
                text_widget.insert(tk.END, "Log file not found. No logs have been generated yet.")
            except Exception as e:
                text_widget.insert(tk.END, f"Error reading log file: {e}")
            
            text_widget.config(state=tk.DISABLED)
            
            # Buttons frame
            buttons_frame = ttk.Frame(main_frame)
            buttons_frame.pack(fill=tk.X, pady=(10, 0))
            
            # Refresh button
            def refresh_logs():
                text_widget.config(state=tk.NORMAL)
                text_widget.delete(1.0, tk.END)
                try:
                    content = load_log_content()
                    if content:
                        text_widget.insert(tk.END, content)
                        text_widget.see(tk.END)
                    else:
                        text_widget.insert(tk.END, "Log file is empty.")
                except Exception as e:
                    text_widget.insert(tk.END, f"Error reading log file: {e}")
                text_widget.config(state=tk.DISABLED)
            
            ttk.Button(buttons_frame, text="Refresh", command=refresh_logs).pack(side=tk.LEFT)
            
            # Open log folder button
            def open_log_folder():
                import os
                import subprocess
                log_dir = os.path.dirname(log_file)
                try:
                    subprocess.Popen(f'explorer "{log_dir}"')
                except Exception as e:
                    messagebox.showerror("Error", f"Could not open log folder: {e}")
            
            ttk.Button(buttons_frame, text="Open Log Folder", command=open_log_folder).pack(side=tk.LEFT, padx=(10, 0))
            
            # Clean logs button (to fix encoding issues)
            def clean_logs():
                if messagebox.askyesno("Clean Logs", "This will create a new clean log file. Current logs will be backed up. Continue?"):
                    try:
                        import shutil
                        import os
                        from datetime import datetime
                        
                        # Create backup
                        backup_file = log_file + ".backup"
                        shutil.copy2(log_file, backup_file)
                        
                        # Create new clean log file
                        with open(log_file, 'w', encoding='utf-8') as f:
                            f.write("# Log file cleaned due to encoding issues\n")
                            f.write(f"# Original log backed up to: {backup_file}\n")
                            f.write(f"# Clean log started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                        
                        messagebox.showinfo("Success", f"Logs cleaned successfully. Backup saved to: {backup_file}")
                        refresh_logs()  # Refresh the display
                        
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to clean logs: {e}")
            
            ttk.Button(buttons_frame, text="Clean Logs", command=clean_logs).pack(side=tk.LEFT, padx=(10, 0))
            
            # Close button
            ttk.Button(buttons_frame, text="Close", command=log_window.destroy).pack(side=tk.RIGHT)
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not open log viewer: {e}")
    
    def _exit_application(self):
        """Exit the application completely"""
        self._actually_close()
    
    def _update_single_anime(self, anime_entry: Dict[str, Any]):
        """Update a single anime entry in the local data and refresh only that item"""
        if not anime_entry:
            return
        
        # Find and update the anime in local data
        found = False
        old_status_key = None
        
        for status_key, anime_list in self.anime_list_data.items():
            for i, entry in enumerate(anime_list):
                if entry.get('id') == anime_entry.get('id'):
                    old_status_key = status_key
                    new_status = anime_entry.get('status', '')
                    
                    # If status changed, we need to move the anime
                    if new_status != status_key and new_status in self.anime_list_data:
                        # Remove from old list
                        self.anime_list_data[status_key].pop(i)
                        # Add to new list  
                        self.anime_list_data[new_status].append(anime_entry)
                    else:
                        # Just update in place
                        self.anime_list_data[status_key][i] = anime_entry
                    
                    found = True
                    break
            
            if found:
                break
        
        if found:
            # Update the UI display efficiently - only refresh the tree view
            self.anime_list_frame.update_list(self.anime_list_data)
            # Update the selected anime in the info panel if it's the same one
            if self.selected_anime and self.selected_anime.get('id') == anime_entry.get('id'):
                self.set_selected_anime(anime_entry)
            # Update the item_data in anime_list_frame to maintain consistency
            self.anime_list_frame._sync_item_data_with_updated_entry(anime_entry)
        else:
            # If not found, do a full refresh as fallback
            self._refresh_list()
    
    # Manga-specific methods
    def get_manga_list_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get current manga list data"""
        return self.manga_list_data
    
    def refresh_manga_list(self):
        """Public method to refresh manga list (forces full refresh and cache rebuild)"""
        self._refresh_manga_list(force_refresh=True)
    
    def set_selected_manga(self, manga_entry: Optional[Dict[str, Any]]):
        """Set the currently selected manga in the info panel"""
        # Store selected manga (different from anime)
        self.selected_manga = manga_entry
        self.selected_anime = None  # Clear anime selection
        
        if manga_entry:
            manga = manga_entry.get('manga', {})
            
            # Update compact panel for manga
            name = manga.get('name', 'Unknown')
            # Truncate long names for compact display
            if len(name) > 50:
                display_name = name[:47] + "..."
            else:
                display_name = name
            self.compact_anime_name_var.set(display_name + " (Manga)")
            
            # Switch to manga mode - show chapters and volumes separately
            self._switch_to_manga_mode(manga_entry)
            
            # Update status in compact panel
            status = manga_entry.get('status', '')
            if status in self.api_client.MANGA_STATUSES:
                status_display = self.api_client.MANGA_STATUSES[status]
                self.compact_status_var.set(status_display)
            else:
                self.compact_status_var.set("-")
            
            # Update score in compact panel
            score = manga_entry.get('score', 0)
            if score > 0:
                self.compact_score_var.set(str(score))
            else:
                self.compact_score_var.set("-")
                
            # Enable controls
            self._set_compact_controls_enabled(True)
        else:
            # Clear manga selection
            self.selected_manga = None
            self._switch_to_anime_mode()
            self.compact_anime_name_var.set("None")
            self.compact_status_var.set("-")
            self.compact_score_var.set("-")
            self._set_compact_controls_enabled(False)
    
    def _refresh_manga_list(self, force_refresh: bool = False):
        """Refresh manga list from the active service"""
        if not self.config.is_authenticated:
            messagebox.showwarning("Warning", "Please login first")
            return
        
        def refresh_data():
            try:
                self._refresh_manga_list_data(force_refresh=force_refresh)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to refresh manga list: {str(e)}"))
                self.root.after(0, lambda: self._set_status("Error refreshing manga list"))
        
        threading.Thread(target=refresh_data, daemon=True).start()
    
    def _refresh_manga_list_data(self, force_refresh: bool = False):
        """Refresh manga list data (called from background thread)"""
        if not self.current_user:
            return
        
        user_id = self.current_user['id']
        
        # Try to load from cache first (unless forced refresh)
        if not force_refresh:
            self.root.after(0, lambda: self._set_status("Loading manga list from cache..."))
            cached_data = self.cache_manager.load_manga_list(user_id)
            
            if cached_data:
                self.manga_list_data = cached_data
                total_manga = sum(len(manga_list) for manga_list in cached_data.values())
                
                # Update UI on main thread
                self.root.after(0, lambda: self.manga_list_frame.update_list(self.manga_list_data))
                self.root.after(0, lambda: self._set_status(f"Manga list loaded from cache - {total_manga} manga"))
                return
        
        # Load from API if no cache or forced refresh
        self.root.after(0, lambda: self._set_status("Refreshing manga list..."))
        
        total_manga = 0
        
        # Load all statuses (no rewatching status for manga)
        for i, status_key in enumerate(self.api_client.MANGA_STATUSES.keys()):
            status_display = self.api_client.MANGA_STATUSES[status_key]
            self.root.after(0, lambda s=status_display: self._set_status(f"Loading {s} manga..."))
            
            manga_list = self.api_client.get_user_manga_list(user_id, status_key)
            self.manga_list_data[status_key] = manga_list
            total_manga += len(manga_list)
            
            # Update progress
            progress = f"Loaded {total_manga} manga so far..."
            self.root.after(0, lambda p=progress: self._set_status(p))
        
        # Save to cache
        self.cache_manager.save_manga_list(user_id, self.manga_list_data)
        
        # Update UI on main thread
        self.root.after(0, lambda: self.manga_list_frame.update_list(self.manga_list_data))
        self.root.after(0, lambda: self._set_status(f"Manga list updated - {total_manga} manga loaded"))
    
    def _update_manga_cache_and_reload(self, manga_id: int, updates: Dict[str, Any]):
        """Update manga cache directly and reload from cache to reflect changes"""
        def update_and_reload():
            if self.current_user:
                user_id = self.current_user['id']
                # Update the cache file directly
                cache_updated = self.cache_manager.update_manga_in_cache(user_id, manga_id, updates)
                
                if cache_updated:
                    # Reload from updated cache
                    self.root.after(0, self._reload_manga_from_cache)
                else:
                    # Fallback to full refresh if cache update failed
                    self.root.after(0, lambda: self._refresh_manga_list(force_refresh=True))
        
        threading.Thread(target=update_and_reload, daemon=True).start()
    
    def _reload_manga_from_cache(self):
        """Reload manga list from cache (for reflecting manual updates)"""
        if not self.current_user:
            return
        
        def reload_data():
            try:
                user_id = self.current_user['id']
                cached_data = self.cache_manager.load_manga_list(user_id)
                
                if cached_data:
                    self.manga_list_data = cached_data
                    total_manga = sum(len(manga_list) for manga_list in cached_data.values())
                    
                    # Update UI on main thread
                    self.root.after(0, lambda: self.manga_list_frame.update_list(self.manga_list_data))
                    self.root.after(0, lambda: self._set_status(f"Updated from manga cache - {total_manga} manga"))
                else:
                    # Fallback to full refresh if cache not available
                    self.root.after(0, lambda: self._refresh_manga_list(force_refresh=True))
                    
            except Exception as e:
                self.logger.error(f"Error reloading manga from cache: {e}")
                # Fallback to full refresh on error
                self.root.after(0, lambda: self._refresh_manga_list(force_refresh=True))
        
        threading.Thread(target=reload_data, daemon=True).start()
    
    def _switch_to_manga_mode(self, manga_entry):
        """Switch UI to manga mode - show chapters and volumes"""
        self.current_mode = 'manga'
        
        # Update episode label to chapters
        progress_frame = self.compact_episode_entry.master
        for widget in progress_frame.winfo_children():
            if isinstance(widget, ttk.Label) and widget.cget('text') == 'Ep:':
                widget.config(text='Ch:')
                break
        
        # Show volume controls
        self.volume_frame.pack(side=tk.LEFT, padx=(0, 10), after=progress_frame)
        
        # Update values
        manga = manga_entry.get('manga', {})
        current_chapters = manga_entry.get('chapters', 0)
        total_chapters = manga.get('chapters', 0)
        current_volumes = manga_entry.get('volumes', 0)
        total_volumes = manga.get('volumes', 0)
        
        self.compact_episode_var.set(str(current_chapters))
        self.compact_total_episodes_var.set(f"/{total_chapters if total_chapters else '?'}")
        self.compact_volume_var.set(str(current_volumes))
        self.compact_total_volumes_var.set(f"/{total_volumes if total_volumes else '?'}")
        
        # Update status combo values for manga
        self.compact_status_combo.config(values=["-"] + list(self.api_client.MANGA_STATUSES.values()))
    
    def _switch_to_anime_mode(self):
        """Switch UI to anime mode - hide volumes, show episodes"""
        self.current_mode = 'anime'
        
        # Update chapters label back to episodes
        progress_frame = self.compact_episode_entry.master
        for widget in progress_frame.winfo_children():
            if isinstance(widget, ttk.Label) and widget.cget('text') == 'Ch:':
                widget.config(text='Ep:')
                break
        
        # Hide volume controls
        self.volume_frame.pack_forget()
        
        # Reset values
        self.compact_episode_var.set("0")
        self.compact_total_episodes_var.set("/?")
        self.compact_volume_var.set("0")
        self.compact_total_volumes_var.set("/?")
        
        # Update status combo values for anime
        self.compact_status_combo.config(values=["-"] + list(self.api_client.STATUSES.values()))
    
    def _compact_decrease_progress(self):
        """Decrease progress by 1 (episodes for anime, chapters for manga)"""
        if self.current_mode == 'manga' and self.selected_manga:
            self._decrease_manga_chapters()
        elif self.current_mode == 'anime' and self.selected_anime:
            self._decrease_progress()
    
    def _compact_increase_progress(self):
        """Increase progress by 1 (episodes for anime, chapters for manga)"""
        if self.current_mode == 'manga' and self.selected_manga:
            self._increase_manga_chapters()
        elif self.current_mode == 'anime' and self.selected_anime:
            self._increase_progress()
    
    def _compact_decrease_volumes(self):
        """Decrease manga volumes by 1"""
        if not self.selected_manga:
            return
        
        try:
            current = int(self.compact_volume_var.get())
            new_value = max(0, current - 1)
            self.compact_volume_var.set(str(new_value))
            self._update_manga_volumes(new_value)
        except ValueError:
            pass
    
    def _compact_increase_volumes(self):
        """Increase manga volumes by 1"""
        if not self.selected_manga:
            return
        
        try:
            current = int(self.compact_volume_var.get())
            total = self.selected_manga['manga'].get('volumes', 9999)
            new_value = min(total if total else 9999, current + 1)
            self.compact_volume_var.set(str(new_value))
            self._update_manga_volumes(new_value)
        except ValueError:
            pass
    
    def _decrease_manga_chapters(self):
        """Decrease manga chapters by 1"""
        if not self.selected_manga:
            return
        
        try:
            current = int(self.compact_episode_var.get())
            new_value = max(0, current - 1)
            self.compact_episode_var.set(str(new_value))
            self._update_manga_chapters(new_value)
        except ValueError:
            pass
    
    def _increase_manga_chapters(self):
        """Increase manga chapters by 1"""
        if not self.selected_manga:
            return
        
        try:
            current = int(self.compact_episode_var.get())
            total = self.selected_manga['manga'].get('chapters', 9999)
            new_value = min(total if total else 9999, current + 1)
            self.compact_episode_var.set(str(new_value))
            self._update_manga_chapters(new_value)
        except ValueError:
            pass
    
    def _on_compact_volume_entry(self, event=None):
        """Handle manual volume entry in compact panel"""
        if not self.selected_manga:
            return
        
        try:
            new_value = int(self.compact_volume_var.get())
            total = self.selected_manga['manga'].get('volumes', 9999)
            new_value = max(0, min(total if total else 9999, new_value))
            
            # Only update if the value actually changed
            current = self.selected_manga.get('volumes', 0)
            if new_value != current:
                self.compact_volume_var.set(str(new_value))
                self._update_manga_volumes(new_value)
            
        except ValueError:
            # Reset to current value if invalid
            current = self.selected_manga.get('volumes', 0)
            self.compact_volume_var.set(str(current))
    
    def _update_manga_chapters(self, chapters: int):
        """Update manga chapter progress on the active service"""
        if not self.selected_manga:
            return
        
        def update_data():
            try:
                rate_id = self.selected_manga['id']
                manga_name = self.selected_manga['manga'].get('name', 'Unknown')
                
                success = self.api_client.update_manga_progress(
                    rate_id, chapters=chapters)
                
                if success:
                    self.root.after(0, lambda: self._set_status(
                        f"Updated {manga_name} to chapter {chapters}"))
                    
                    # Update cache directly and reload from cache
                    manga_id = self.selected_manga['id']
                    self._update_manga_cache_and_reload(manga_id, {'chapters': chapters})
                else:
                    self.root.after(0, lambda: self._set_status(
                        f"Failed to update {manga_name} chapters"))
                    # Reset to previous value
                    prev_chapters = self.selected_manga.get('chapters', 0)
                    self.root.after(0, lambda: self.compact_episode_var.set(str(prev_chapters)))
                    
            except Exception as e:
                self.root.after(0, lambda: self._set_status(
                    f"Error updating chapters: {str(e)}"))
        
        threading.Thread(target=update_data, daemon=True).start()
    
    def _update_manga_volumes(self, volumes: int):
        """Update manga volume progress on the active service"""
        if not self.selected_manga:
            return
        
        def update_data():
            try:
                rate_id = self.selected_manga['id']
                manga_name = self.selected_manga['manga'].get('name', 'Unknown')
                
                success = self.api_client.update_manga_progress(
                    rate_id, volumes=volumes)
                
                if success:
                    self.root.after(0, lambda: self._set_status(
                        f"Updated {manga_name} to volume {volumes}"))
                    
                    # Update cache directly and reload from cache
                    manga_id = self.selected_manga['id']
                    self._update_manga_cache_and_reload(manga_id, {'volumes': volumes})
                else:
                    self.root.after(0, lambda: self._set_status(
                        f"Failed to update {manga_name} volumes"))
                    # Reset to previous value
                    prev_volumes = self.selected_manga.get('volumes', 0)
                    self.root.after(0, lambda: self.compact_volume_var.set(str(prev_volumes)))
                    
            except Exception as e:
                self.root.after(0, lambda: self._set_status(
                    f"Error updating volumes: {str(e)}"))
        
        threading.Thread(target=update_data, daemon=True).start()
    
    def _check_for_updates(self):
        """Check for application updates"""
        try:
            version_info = get_version_info()
            update_checker = UpdateChecker(version_info['github_repo'], version_info['version'])
            
            def update_callback(update_available, update_info):
                if update_available and update_info:
                    # Show update notification
                    notification = UpdateNotification(self.root, update_info)
                    notification.show()
                else:
                    # Only show "no updates" message if manually triggered
                    if hasattr(self, '_manual_update_check') and self._manual_update_check:
                        self._manual_update_check = False
                        messagebox.showinfo("No Updates", "You are running the latest version!")
            
            # Mark as manual check if called from menu
            import inspect
            frame = inspect.currentframe()
            if frame and frame.f_back:
                caller_locals = frame.f_back.f_locals
                if 'self' in caller_locals and hasattr(caller_locals['self'], 'menu'):
                    self._manual_update_check = True
            
            update_checker.check_updates_async(update_callback)
            
        except Exception as e:
            self.logger.error(f"Error checking for updates: {e}")
            if hasattr(self, '_manual_update_check') and self._manual_update_check:
                self._manual_update_check = False
                messagebox.showerror("Update Error", f"Failed to check for updates: {str(e)}")
    
    def _schedule_update_check(self):
        """Schedule the next automatic update check"""
        if not self.config.get('updates.auto_check', True):
            # Auto-check is disabled, cancel any existing timer
            if self.update_check_timer:
                self.root.after_cancel(self.update_check_timer)
                self.update_check_timer = None
            return
        
        # Get the check interval from config (in seconds)
        check_interval = self.config.get('updates.check_interval', 3600)  # Default 1 hour
        
        # Schedule the next check
        self.update_check_timer = self.root.after(check_interval * 1000, self._auto_check_for_updates)
        
        self.logger.info(f"Next automatic update check scheduled in {check_interval} seconds")
    
    def _auto_check_for_updates(self):
        """Automatically check for updates (called by timer)"""
        try:
            # Only check if auto-check is still enabled
            if not self.config.get('updates.auto_check', True):
                return
                
            self.logger.info("Performing automatic update check")
            
            version_info = get_version_info()
            update_checker = UpdateChecker(version_info['github_repo'], version_info['version'])
            
            def update_callback(update_available, update_info):
                if update_available and update_info:
                    # Show update notification (silently, not as manual check)
                    notification = UpdateNotification(self.root, update_info)
                    notification.show()
                    self.logger.info(f"Automatic update check found new version: {update_info.get('latest_version', 'Unknown')}")
                else:
                    self.logger.info("Automatic update check: No updates available")
                
                # Schedule the next check regardless of result
                self._schedule_update_check()
            
            update_checker.check_updates_async(update_callback)
            
        except Exception as e:
            self.logger.error(f"Error during automatic update check: {e}")
            # Schedule the next check even if this one failed
            self._schedule_update_check()
    
    def _is_anime_in_active_list(self, anime_name: str) -> bool:
        """Check if anime is in user's active list (Watching, Plan to Watch, Rewatching, On Hold)"""
        if not self.anime_list_data:
            return False
        
        # Only consider active statuses to avoid conflicts with multiple seasons
        active_statuses = ['watching', 'planned', 'rewatching', 'on_hold']
        
        # Collect all anime from active statuses
        all_anime = []
        for status_key in active_statuses:
            if status_key in self.anime_list_data:
                all_anime.extend(self.anime_list_data[status_key])
        
        # Use the anime matcher to find a match
        match_result = self.anime_matcher.find_best_match(anime_name, all_anime)
        return match_result is not None
    
    def _stop_update_check_timer(self):
        """Stop the automatic update check timer"""
        if self.update_check_timer:
            self.root.after_cancel(self.update_check_timer)
            self.update_check_timer = None
            self.logger.info("Automatic update check timer stopped")
