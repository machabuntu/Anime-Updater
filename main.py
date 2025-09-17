#!/usr/bin/env python3
"""
Shikimori Updater - Main Application Entry Point
Tracks anime episodes from media players and updates Shikimori list
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import sys
import os

# Handle both development and PyInstaller environments
def setup_path():
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller executable
        application_path = sys._MEIPASS
        src_path = os.path.join(application_path, 'src')
        # Also add the main application path
        if application_path not in sys.path:
            sys.path.insert(0, application_path)
    else:
        # Running as script
        application_path = os.path.dirname(os.path.abspath(__file__))
        src_path = os.path.join(application_path, 'src')
        # Add both the main directory and src directory
        if application_path not in sys.path:
            sys.path.insert(0, application_path)
    
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    
    # Debug path information (for development only)
    # Uncomment for debugging path issues:
    # print(f"Application path: {application_path}")
    # print(f"Source path: {src_path}")
    # print(f"Frozen: {getattr(sys, 'frozen', False)}")

setup_path()

# Initialize logging first
try:
    from utils.logger import get_logger
    logger = get_logger('main')
except ImportError as e:
    print(f"Failed to import logger: {e}")
    import logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger('main')

try:
    from core.config import Config
    from gui.main_window import MainWindow
except ImportError as e:
    logger.error(f"Failed to import main modules: {e}")
    messagebox.showerror("Import Error", f"Failed to import required modules: {e}\n\nPlease check the installation.")
    sys.exit(1)

def main():
    """Main application entry point"""
    try:
        # Test logging
        logger.info("Starting Shikimori Updater application")
        
        # Initialize configuration
        config = Config()
        
        # Create main window
        root = tk.Tk()
        photo = tk.PhotoImage(file = 'icon.png')
        root.wm_iconphoto(False, photo)

        app = MainWindow(root, config)
        
        # Start the application
        root.mainloop()
        
    except Exception as e:
        messagebox.showerror("Error", f"Failed to start application: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
