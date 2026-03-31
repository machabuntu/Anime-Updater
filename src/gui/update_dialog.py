"""
Update Dialog - Shows available updates and handles installation
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from typing import Dict, Any, Optional
import webbrowser
from utils.updater import UpdateChecker
from utils.version import get_version_info

class UpdateDialog:
    """Dialog for showing update information and handling updates"""
    
    def __init__(self, parent, update_info: Dict[str, Any]):
        self.parent = parent
        self.update_info = update_info
        self.dialog = None
        self.progress_var = None
        self.status_var = None
        self.update_button = None
        self.progress_bar = None
        
        self._create_dialog()
    
    def _create_dialog(self):
        """Create the update dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Update Available")
        self.dialog.geometry("500x400")
        self.dialog.resizable(False, False)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (400 // 2)
        self.dialog.geometry(f"500x400+{x}+{y}")
        
        # Main frame
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(main_frame, text="🔄 Update Available", 
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Version info frame
        version_frame = ttk.LabelFrame(main_frame, text="Version Information")
        version_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Current version
        current_frame = ttk.Frame(version_frame)
        current_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(current_frame, text="Current Version:").pack(side=tk.LEFT)
        ttk.Label(current_frame, text=self.update_info['current_version'], 
                 font=("Arial", 10, "bold")).pack(side=tk.RIGHT)
        
        # New version
        new_frame = ttk.Frame(version_frame)
        new_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(new_frame, text="Latest Version:").pack(side=tk.LEFT)
        ttk.Label(new_frame, text=self.update_info['latest_version'], 
                 font=("Arial", 10, "bold"), foreground="green").pack(side=tk.RIGHT)
        
        # Release notes
        if self.update_info.get('release_notes'):
            notes_frame = ttk.LabelFrame(main_frame, text="What's New")
            notes_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            
            notes_text = scrolledtext.ScrolledText(notes_frame, height=8, wrap=tk.WORD)
            notes_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            notes_text.insert(tk.END, self.update_info['release_notes'])
            notes_text.config(state=tk.DISABLED)
        
        # Progress frame
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, 
                                          maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))
        
        self.status_var = tk.StringVar(value="Ready to update")
        status_label = ttk.Label(progress_frame, textvariable=self.status_var)
        status_label.pack()
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        # Cancel button
        cancel_button = ttk.Button(button_frame, text="Later", 
                                 command=self._cancel_update)
        cancel_button.pack(side=tk.RIGHT, padx=(5, 0))
        
        # Update button
        self.update_button = ttk.Button(button_frame, text="Update Now", 
                                      command=self._start_update)
        self.update_button.pack(side=tk.RIGHT)
        
        # View on GitHub button
        github_button = ttk.Button(button_frame, text="View on GitHub", 
                                 command=self._open_github)
        github_button.pack(side=tk.LEFT)
        
        # Handle window close
        self.dialog.protocol("WM_DELETE_WINDOW", self._cancel_update)
    
    def _start_update(self):
        """Start the update process"""
        self.update_button.config(state=tk.DISABLED)
        self.status_var.set("Downloading update archive...")
        self.progress_var.set(0)
        
        # Get version info and create updater
        version_info = get_version_info()
        updater = UpdateChecker(version_info['github_repo'], version_info['version'])
        
        # Set the download URL from the update info if available
        if 'download_url' in self.update_info and self.update_info['download_url']:
            updater.updater.download_url = self.update_info['download_url']
            updater.updater.latest_version = self.update_info['latest_version']
            updater.updater.release_notes = self.update_info.get('release_notes', '')
        
        # Start download and installation
        updater.download_and_install(self._update_progress)
    
    def _update_progress(self, progress: float):
        """Update progress bar"""
        self.progress_var.set(progress)
        if progress >= 85 and progress < 100:
            self.status_var.set("Extracting update...")
        elif progress >= 100:
            self.status_var.set("Installing update...")
            self.dialog.after(2000, self._update_complete)
    
    def _update_complete(self):
        """Handle update completion"""
        self.status_var.set("Update complete! Restarting...")
        self.dialog.after(1000, self._close_dialog)
    
    def _cancel_update(self):
        """Cancel the update"""
        self._close_dialog()
    
    def _open_github(self):
        """Open GitHub release page"""
        version_info = get_version_info()
        url = f"https://github.com/{version_info['github_repo']}/releases/latest"
        webbrowser.open(url)
    
    def _close_dialog(self):
        """Close the dialog"""
        if self.dialog:
            self.dialog.destroy()
    
    def show(self):
        """Show the dialog"""
        self.dialog.wait_window()


class UpdateNotification:
    """Simple notification for available updates"""
    
    def __init__(self, parent, update_info: Dict[str, Any]):
        self.parent = parent
        self.update_info = update_info
    
    def show(self):
        """Show update notification"""
        result = messagebox.askyesno(
            "Update Available",
            f"A new version ({self.update_info['latest_version']}) is available!\n\n"
            f"Current version: {self.update_info['current_version']}\n"
            f"Would you like to update now?",
            icon="question"
        )
        
        if result:
            dialog = UpdateDialog(self.parent, self.update_info)
            dialog.show()
        
        return result
