"""
Notification Service - Handle system notifications for episode updates
"""

import tkinter as tk
from tkinter import messagebox
import threading
import time
from typing import Optional, Callable

try:
    # For Windows 10+ toast notifications
    from win10toast import ToastNotifier
    TOAST_AVAILABLE = True
except ImportError:
    TOAST_AVAILABLE = False

try:
    # Alternative notification library
    import plyer
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False

class NotificationService:
    """Service for displaying system notifications"""
    
    def __init__(self):
        self.toast_notifier = None
        if TOAST_AVAILABLE:
            try:
                self.toast_notifier = ToastNotifier()
            except:
                pass
    
    def show_episode_notification(self, anime_name: str, episode_number: int, 
                                callback: Optional[Callable] = None):
        """Show notification for new episode availability"""
        title = "New Episode Available!"
        message = f"{anime_name}\nEpisode {episode_number} is now available"
        
        self._show_notification(title, message, callback)
    
    def show_release_notification(self, anime_name: str, 
                                callback: Optional[Callable] = None):
        """Show notification for anime release completion"""
        title = "Anime Fully Released!"
        message = f"{anime_name}\nAll episodes are now available"
        
        self._show_notification(title, message, callback)
    
    def _show_notification(self, title: str, message: str, 
                          callback: Optional[Callable] = None):
        """Show system notification using available method"""
        def show_notification():
            success = False
            
            # Try Windows 10 toast notification first
            if self.toast_notifier:
                try:
                    self.toast_notifier.show_toast(
                        title=title,
                        msg=message,
                        icon_path=None,
                        duration=10,
                        threaded=True
                    )
                    success = True
                except Exception as e:
                    print(f"Toast notification failed: {e}")
            
            # Try plyer notification as fallback
            if not success and PLYER_AVAILABLE:
                try:
                    plyer.notification.notify(
                        title=title,
                        message=message,
                        timeout=10
                    )
                    success = True
                except Exception as e:
                    print(f"Plyer notification failed: {e}")
            
            # Fallback to popup notification
            if not success:
                self._show_popup_notification(title, message, callback)
        
        # Run notification in separate thread to avoid blocking UI
        threading.Thread(target=show_notification, daemon=True).start()
    
    def _show_popup_notification(self, title: str, message: str, 
                               callback: Optional[Callable] = None):
        """Fallback popup notification using tkinter"""
        def show_popup():
            # Create a simple notification popup window
            popup = tk.Toplevel()
            popup.title(title)
            popup.geometry("300x150")
            popup.resizable(False, False)
            
            # Position in bottom right corner
            popup.update_idletasks()
            x = popup.winfo_screenwidth() - 320
            y = popup.winfo_screenheight() - 200
            popup.geometry(f"300x150+{x}+{y}")
            
            # Make it stay on top
            popup.attributes('-topmost', True)
            
            # Style the popup
            popup.configure(bg='#2d2d2d')
            
            # Title
            title_label = tk.Label(popup, text=title, font=('Arial', 12, 'bold'),
                                 bg='#2d2d2d', fg='white')
            title_label.pack(pady=(10, 5))
            
            # Message
            message_label = tk.Label(popup, text=message, font=('Arial', 10),
                                   bg='#2d2d2d', fg='white', wraplength=280)
            message_label.pack(pady=5)
            
            # Close button
            def close_popup():
                popup.destroy()
                if callback:
                    callback()
            
            close_btn = tk.Button(popup, text="OK", command=close_popup,
                                bg='#0078d4', fg='white', relief='flat',
                                font=('Arial', 9))
            close_btn.pack(pady=(10, 5))
            
            # Auto-close after 10 seconds
            popup.after(10000, close_popup)
            
            # Focus and bring to front
            popup.focus_force()
            popup.lift()
        
        # Schedule popup on main thread
        if hasattr(tk, '_default_root') and tk._default_root:
            tk._default_root.after(0, show_popup)
    
    @staticmethod
    def is_available() -> bool:
        """Check if notification service is available"""
        return TOAST_AVAILABLE or PLYER_AVAILABLE
