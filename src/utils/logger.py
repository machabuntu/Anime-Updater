"""
Logging utility for Anime Updater
Provides both console and file logging with date-based rotation
"""

import logging
import os
import sys
from pathlib import Path
from datetime import datetime
import threading

class DateBasedFileHandler(logging.FileHandler):
    def __init__(self, log_dir, filename_prefix):
        self.log_dir = log_dir
        self.filename_prefix = filename_prefix
        self.current_date = datetime.now().date()
        self.baseFilename = self._get_log_filename()
        super().__init__(self.baseFilename, encoding='utf-8')

    def _get_log_filename(self):
        return os.path.join(self.log_dir, f"{self.filename_prefix}_{self.current_date}.log")

    def emit(self, record):
        try:
            self.acquire()
            if datetime.now().date() != self.current_date:
                self.current_date = datetime.now().date()
                self.baseFilename = self._get_log_filename()
                if self.stream:
                    self.stream.close()
                    self.stream = None
                # Ensure encoding is set when reopening
                self.encoding = 'utf-8'
                self.stream = self._open()
            super().emit(record)
        finally:
            self.release()

class Logger:
    """Centralized logging for the application"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if Logger._initialized:
            return
        Logger._initialized = True
        
        # Create logs directory
        if getattr(sys, 'frozen', False):
            # Running as PyInstaller executable
            app_dir = Path.home() / ".shikimori_updater"
        else:
            # Running as script
            app_dir = Path.home() / ".shikimori_updater"
        
        self.log_dir = app_dir / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup logger
        self.logger = logging.getLogger('AnimeUpdater')
        self.logger.setLevel(logging.DEBUG)
        
        # Clear any existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        simple_formatter = logging.Formatter(
            '%(levelname)s: %(message)s'
        )
        
        # File handler - always log to file with date-based rotation
        self.file_handler = DateBasedFileHandler(str(self.log_dir), "shikimori_updater")
        self.file_handler.setLevel(logging.DEBUG)
        self.file_handler.setFormatter(detailed_formatter)
        self.logger.addHandler(self.file_handler)
        
        # Console handler - only if console is available
        try:
            # Check if we have a console available
            if sys.stdout and sys.stdout.isatty():
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setLevel(logging.INFO)
                console_handler.setFormatter(simple_formatter)
                self.logger.addHandler(console_handler)
        except:
            # No console available (running as Windows app without console)
            pass
        
        # Log startup
        self.logger.info("=" * 50)
        self.logger.info("Anime Updater started")
        self.logger.info(f"Log file: {self.file_handler.baseFilename}")
        self.logger.info("=" * 50)
    
    def get_logger(self, name=None):
        """Get a logger instance"""
        if name:
            return logging.getLogger(f'AnimeUpdater.{name}')
        return self.logger
    
    def get_log_file_path(self):
        """Get the current log file path"""
        # Return the current log file path from the DateBasedFileHandler
        # This will ensure it returns the correct file even if the date has changed
        return self.file_handler._get_log_filename()

# Global logger instance
_global_logger = Logger()

def get_logger(name=None):
    """Get a logger instance"""
    return _global_logger.get_logger(name)

def get_log_file_path():
    """Get the current log file path"""
    return _global_logger.get_log_file_path()
