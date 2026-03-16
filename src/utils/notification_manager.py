"""
Notification Manager - Track anime episodes and release dates for notifications
"""

import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Callable
from utils.notification_service import NotificationService

class NotificationManager:
    """Manages anime episode and release notifications"""
    
    def __init__(self, config, shikimori_client, cache_manager):
        self.config = config
        self.shikimori_client = shikimori_client
        self.cache_manager = cache_manager
        self.notification_service = NotificationService()
        
        self.current_user_id = None
        self.anime_list_data = {}
        self.detailed_cache = {}
        
        # Tracking state
        self.running = False
        self.check_thread = None
        self.check_interval = 300  # Check every 5 minutes
        
        # Callbacks
        self.on_episode_notification = None
        self.on_release_notification = None
        
    def start_monitoring(self, user_id: int, anime_list_data: Dict[str, List[Dict[str, Any]]]):
        """Start monitoring anime for notifications"""
        if self.running:
            return
        
        self.current_user_id = user_id
        self.anime_list_data = anime_list_data
        
        # Load detailed cache
        self._load_detailed_cache()
        
        self.running = True
        self.check_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.check_thread.start()
        
        print("Notification monitoring started")
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.running = False
        if self.check_thread:
            self.check_thread.join(timeout=1)
        
        print("Notification monitoring stopped")
    
    def update_anime_list(self, anime_list_data: Dict[str, List[Dict[str, Any]]]):
        """Update the anime list data"""
        self.anime_list_data = anime_list_data
    
    def _load_detailed_cache(self):
        """Load detailed anime information from cache"""
        if not self.current_user_id:
            return
        
        self.detailed_cache = self.cache_manager.load_detailed_anime_info(self.current_user_id) or {}
        print(f"Loaded detailed cache with {len(self.detailed_cache)} entries")
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                if (self.config.get('notifications.episode_notifications', False) or 
                    self.config.get('notifications.release_notifications', False)):
                    
                    self._check_notifications()
                
                # Sleep for check interval
                for _ in range(self.check_interval):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                print(f"Error in notification monitoring loop: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    def _check_notifications(self):
        """Check for anime notifications"""
        current_time = datetime.now(timezone.utc)
        
        # Check episode notifications
        if self.config.get('notifications.episode_notifications', False):
            self._check_episode_notifications(current_time)
        
        # Check release notifications  
        if self.config.get('notifications.release_notifications', False):
            self._check_release_notifications(current_time)
    
    def _check_episode_notifications(self, current_time: datetime):
        """Check for new episode notifications"""
        watching_anime = self.anime_list_data.get('watching', [])
        
        for anime_entry in watching_anime:
            try:
                anime_id = anime_entry['anime']['id']
                user_progress = anime_entry.get('episodes', 0)
                
                # Get detailed info from cache
                detailed_info = self.detailed_cache.get(anime_id)
                if not detailed_info:
                    continue
                
                # Check if anime is ongoing
                status = detailed_info.get('status', '')
                if status != 'ongoing':
                    continue
                
                episodes_aired = detailed_info.get('episodes_aired', 0)
                next_episode_at = detailed_info.get('next_episode_at')
                
                # Check if user's progress matches aired episodes and next episode time has passed
                if (episodes_aired > 0 and 
                    user_progress == episodes_aired and 
                    next_episode_at):
                    
                    try:
                        # Parse next episode time
                        next_episode_time = datetime.fromisoformat(next_episode_at.replace('Z', '+00:00'))
                        
                        # Check if it's time for the next episode
                        if current_time >= next_episode_time:
                            anime_name = anime_entry['anime'].get('name', 'Unknown')
                            next_episode = episodes_aired + 1
                            
                            self._show_episode_notification(anime_entry, next_episode)
                            
                    except (ValueError, TypeError) as e:
                        print(f"Error parsing next_episode_at for anime {anime_id}: {e}")
                        
            except Exception as e:
                print(f"Error checking episode notification for anime: {e}")
    
    def _check_release_notifications(self, current_time: datetime):
        """Check for anime release completion notifications"""
        planned_anime = self.anime_list_data.get('planned', [])
        
        for anime_entry in planned_anime:
            try:
                anime_id = anime_entry['anime']['id']
                
                # Get detailed info from cache
                detailed_info = self.detailed_cache.get(anime_id)
                if not detailed_info:
                    continue
                
                released_on = detailed_info.get('released_on')
                next_episode_at = detailed_info.get('next_episode_at')
                
                # For completed anime, check released_on date
                if released_on:
                    try:
                        # Parse release date (assuming it's the final release date)
                        release_date = datetime.fromisoformat(released_on.replace('Z', '+00:00'))
                        
                        if current_time >= release_date:
                            anime_name = anime_entry['anime'].get('name', 'Unknown')
                            self._show_release_notification(anime_entry)
                            
                    except (ValueError, TypeError) as e:
                        print(f"Error parsing released_on for anime {anime_id}: {e}")
                
                # For ongoing anime, check if next_episode_at indicates completion
                elif next_episode_at:
                    try:
                        next_episode_time = datetime.fromisoformat(next_episode_at.replace('Z', '+00:00'))
                        
                        # If the "next episode" time has passed and anime is marked as completed,
                        # it means the series has finished airing
                        status = detailed_info.get('status', '')
                        if status == 'released' and current_time >= next_episode_time:
                            anime_name = anime_entry['anime'].get('name', 'Unknown')
                            self._show_release_notification(anime_entry)
                            
                    except (ValueError, TypeError) as e:
                        print(f"Error parsing next_episode_at for anime {anime_id}: {e}")
                        
            except Exception as e:
                print(f"Error checking release notification for anime: {e}")
    
    def _show_episode_notification(self, anime_entry: Dict[str, Any], episode_number: int):
        """Show episode notification and update anime info"""
        anime_name = anime_entry['anime'].get('name', 'Unknown')
        anime_id = anime_entry['anime']['id']
        
        def on_notification_shown():
            # Update anime information from the active service
            self._update_anime_detailed_info(anime_id)
            
            if self.on_episode_notification:
                self.on_episode_notification(anime_entry, episode_number)
        
        self.notification_service.show_episode_notification(
            anime_name, episode_number, on_notification_shown)
        
        print(f"Episode notification shown for {anime_name} episode {episode_number}")
    
    def _show_release_notification(self, anime_entry: Dict[str, Any]):
        """Show release notification"""
        anime_name = anime_entry['anime'].get('name', 'Unknown')
        
        def on_notification_shown():
            if self.on_release_notification:
                self.on_release_notification(anime_entry)
        
        self.notification_service.show_release_notification(
            anime_name, on_notification_shown)
        
        print(f"Release notification shown for {anime_name}")
    
    def _update_anime_detailed_info(self, anime_id: int):
        """Update detailed anime information from the active service API"""
        def update_info():
            try:
                detailed_info = self.shikimori_client.get_anime_details(anime_id)
                if detailed_info and self.current_user_id:
                    # Update the detailed cache
                    if anime_id not in self.detailed_cache:
                        self.detailed_cache[anime_id] = {}
                    
                    self.detailed_cache[anime_id].update(detailed_info)
                    
                    # Save updated cache
                    self.cache_manager.save_detailed_anime_info(
                        self.current_user_id, self.detailed_cache)
                    
                    print(f"Updated detailed info for anime {anime_id}")
                    
            except Exception as e:
                print(f"Error updating detailed info for anime {anime_id}: {e}")
        
        threading.Thread(target=update_info, daemon=True).start()
    
    def set_episode_notification_callback(self, callback: Callable):
        """Set callback for episode notifications"""
        self.on_episode_notification = callback
    
    def set_release_notification_callback(self, callback: Callable):
        """Set callback for release notifications"""
        self.on_release_notification = callback
    
    def is_episode_notifications_enabled(self) -> bool:
        """Check if episode notifications are enabled"""
        return self.config.get('notifications.episode_notifications', False)
    
    def is_release_notifications_enabled(self) -> bool:
        """Check if release notifications are enabled"""
        return self.config.get('notifications.release_notifications', False)
