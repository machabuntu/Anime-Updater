"""
Configuration management for Anime Updater
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

class Config:
    """Application configuration manager"""
    
    def __init__(self):
        self.app_dir = Path.home() / ".shikimori_updater"
        self.config_file = self.app_dir / "config.json"
        self.app_dir.mkdir(exist_ok=True)
        
        # Load environment variables
        load_dotenv()
        
        # Default configuration
        self.default_config = {
            "service": {
                "active": "shikimori"
            },
            "shikimori": {
                "client_id": "Mf86jr7hvlSRXHy0yNTqUi8kxQgYiB-7whXD1JVYI60",
                "client_secret": "hcTpGGUHEpW7-aIU4L6y8sqwsoLXcPY58ttHwWAGzb8",
                "access_token": None,
                "refresh_token": None,
                "user_id": None
            },
            "mal": {
                "client_id": "",
                "client_secret": "",
                "access_token": None,
                "refresh_token": None,
                "user_id": None
            },
            "monitoring": {
                "check_interval": 5,  # seconds
                "min_watch_time": 60,  # seconds
                "supported_players": ["PotPlayerMini64.exe", "PotPlayerMini.exe", "PotPlayer64.exe", "PotPlayer.exe"]
            },
            "window": {
                "width": 1000,
                "height": 700,
                "x": None,
                "y": None
            },
            "telegram": {
                "enabled": False,
                "bot_token": "",
                "chat_id": "",
                "send_progress": False,
                "send_completed": True,
                "send_dropped": False,
                "send_rewatching": False
            },
            "updates": {
                "auto_check": True,
                "check_interval": 3600  # 1 hour in seconds
            }
        }
        
        self.config = self.load_config()
    
    def load_config(self):
        """Load configuration from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # Merge with defaults
                return self._merge_config(self.default_config, config)
            except Exception as e:
                print(f"Error loading config: {e}")
        
        return self.default_config.copy()
    
    def save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def _merge_config(self, default, loaded):
        """Recursively merge loaded config with defaults"""
        result = default.copy()
        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        return result
    
    def get(self, key_path, default=None):
        """Get config value by dot-separated key path"""
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key_path, value):
        """Set config value by dot-separated key path"""
        keys = key_path.split('.')
        config = self.config
        
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        config[keys[-1]] = value
        self.save_config()
    
    @property
    def active_service(self):
        """Get the currently active anime service ('shikimori' or 'mal')"""
        return self.get('service.active', 'shikimori')

    @property
    def is_authenticated(self):
        """Check if user is authenticated with the active service"""
        service = self.active_service
        return bool(self.get(f'{service}.access_token'))
