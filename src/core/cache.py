"""
Cache Manager for Anime Updater
Handles caching anime list data to disk for faster startup
"""

import json
import os
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

class CacheManager:
    """Manages caching of anime list data"""
    
    def __init__(self, config):
        self.config = config
        self.cache_dir = self._get_cache_dir()
        self._ensure_cache_dir()
    
    def _get_cache_dir(self) -> str:
        """Get cache directory path"""
        # Use user's AppData/Local directory on Windows
        if os.name == 'nt':
            cache_dir = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'ShikimoriUpdater', 'cache')
        else:
            # For other platforms, use ~/.cache
            cache_dir = os.path.join(os.path.expanduser('~'), '.cache', 'shikimori_updater')
        
        return cache_dir
    
    def _ensure_cache_dir(self):
        """Ensure cache directory exists"""
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def _get_cache_file_path(self, user_id: int) -> str:
        """Get cache file path for specific user"""
        return os.path.join(self.cache_dir, f"anime_list_{user_id}.json")
    
    def save_anime_list(self, user_id: int, anime_list_data: Dict[str, List[Dict[str, Any]]]):
        """Save anime list data to cache"""
        try:
            cache_file = self._get_cache_file_path(user_id)
            
            cache_data = {
                'user_id': user_id,
                'timestamp': time.time(),
                'datetime': datetime.now().isoformat(),
                'data': anime_list_data
            }
            
            # Write to temporary file first, then rename for atomic operation
            temp_file = cache_file + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            # Atomic rename
            if os.path.exists(cache_file):
                os.remove(cache_file)
            os.rename(temp_file, cache_file)
            
            print(f"Cache saved: {cache_file}")
            return True
            
        except Exception as e:
            print(f"Error saving cache: {e}")
            return False
    
    def load_anime_list(self, user_id: int) -> Optional[Dict[str, List[Dict[str, Any]]]]:
        """Load anime list data from cache"""
        try:
            cache_file = self._get_cache_file_path(user_id)
            
            if not os.path.exists(cache_file):
                print("No cache file found")
                return None
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Verify cache is for correct user
            if cache_data.get('user_id') != user_id:
                print("Cache user ID mismatch")
                return None
            
            print(f"Cache loaded from: {cache_data.get('datetime', 'unknown time')}")
            return cache_data.get('data')
        
        except Exception as e:
            print(f"Error loading cache: {e}")
            return None
    
    def add_anime_to_cache(self, user_id: int, anime_entry: Dict[str, Any]) -> bool:
        """Add a new anime entry to the cache"""
        try:
            cache_file = self._get_cache_file_path(user_id)
            
            if not os.path.exists(cache_file):
                print("No cache file found to add anime to")
                return False
            
            # Load current cache
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Verify cache is for correct user
            if cache_data.get('user_id') != user_id:
                print("Cache user ID mismatch")
                return False
            
            # Get the status to add the anime to
            status = anime_entry.get('status', 'planned')
            anime_list_data = cache_data.get('data', {})
            
            # Make sure the status list exists
            if status not in anime_list_data:
                anime_list_data[status] = []
            
            # Add the new anime entry
            anime_list_data[status].append(anime_entry)
            
            # Update timestamp to mark cache as recently modified
            cache_data['timestamp'] = time.time()
            cache_data['datetime'] = datetime.now().isoformat()
            
            # Write back to cache file
            temp_file = cache_file + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            # Atomic rename
            if os.path.exists(cache_file):
                os.remove(cache_file)
            os.rename(temp_file, cache_file)
            
            anime_id = anime_entry.get('id')
            print(f"Added anime ID {anime_id} to cache in status '{status}'")
            return True
                
        except Exception as e:
            print(f"Error adding anime to cache: {e}")
            return False
    
    def update_anime_in_cache(self, user_id: int, anime_id: int, updates: Dict[str, Any]) -> bool:
        """Update a specific anime entry in the cache"""
        try:
            cache_file = self._get_cache_file_path(user_id)
            
            if not os.path.exists(cache_file):
                print("No cache file found to update")
                return False
            
            # Load current cache
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Verify cache is for correct user
            if cache_data.get('user_id') != user_id:
                print("Cache user ID mismatch")
                return False
            
            # Find and update the anime entry
            anime_list_data = cache_data.get('data', {})
            updated = False
            
            for status_key, anime_list in anime_list_data.items():
                for i, entry in enumerate(anime_list):
                    if entry.get('id') == anime_id:
                        # Check if status is changing (need to move between lists)
                        old_status = entry.get('status', '')
                        new_status = updates.get('status', old_status)
                        
                        if new_status != old_status and new_status in anime_list_data:
                            # Remove from old status list
                            anime_list_data[status_key].pop(i)
                            # Update the entry with new data
                            entry.update(updates)
                            # Add to new status list
                            anime_list_data[new_status].append(entry)
                        else:
                            # Just update in place
                            entry.update(updates)
                        
                        updated = True
                        break
                
                if updated:
                    break
            
            if updated:
                # Update timestamp to mark cache as recently modified
                cache_data['timestamp'] = time.time()
                cache_data['datetime'] = datetime.now().isoformat()
                
                # Write back to cache file
                temp_file = cache_file + '.tmp'
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, ensure_ascii=False, indent=2)
                
                # Atomic rename
                if os.path.exists(cache_file):
                    os.remove(cache_file)
                os.rename(temp_file, cache_file)
                
                print(f"Cache updated for anime ID {anime_id}")
                return True
            else:
                print(f"Anime ID {anime_id} not found in cache")
                return False
                
        except Exception as e:
            print(f"Error updating cache: {e}")
            return False
    
    def is_cache_valid(self, user_id: int, max_age_hours: float = 24) -> bool:
        """Check if cache is valid (exists and not too old)"""
        try:
            cache_file = self._get_cache_file_path(user_id)
            
            if not os.path.exists(cache_file):
                return False
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Check user ID
            if cache_data.get('user_id') != user_id:
                return False
            
            # Check age
            cache_timestamp = cache_data.get('timestamp', 0)
            current_timestamp = time.time()
            age_hours = (current_timestamp - cache_timestamp) / 3600
            
            is_valid = age_hours < max_age_hours
            print(f"Cache age: {age_hours:.1f} hours, valid: {is_valid}")
            return is_valid
            
        except Exception as e:
            print(f"Error checking cache validity: {e}")
            return False
    
    def clear_cache(self, user_id: Optional[int] = None):
        """Clear cache for specific user or all users"""
        try:
            if user_id:
                # Clear specific user cache
                cache_file = self._get_cache_file_path(user_id)
                if os.path.exists(cache_file):
                    os.remove(cache_file)
                    print(f"Cache cleared for user {user_id}")
            else:
                # Clear all cache files
                for file in os.listdir(self.cache_dir):
                    if file.startswith('anime_list_') and file.endswith('.json'):
                        os.remove(os.path.join(self.cache_dir, file))
                print("All cache files cleared")
                
        except Exception as e:
            print(f"Error clearing cache: {e}")
    
    def get_cache_info(self, user_id: int) -> Dict[str, Any]:
        """Get information about cached data"""
        try:
            cache_file = self._get_cache_file_path(user_id)
            
            if not os.path.exists(cache_file):
                return {'exists': False}
            
            file_stat = os.stat(cache_file)
            file_size = file_stat.st_size
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            cache_timestamp = cache_data.get('timestamp', 0)
            cache_datetime = datetime.fromtimestamp(cache_timestamp)
            age_hours = (time.time() - cache_timestamp) / 3600
            
            # Count anime entries
            total_anime = 0
            status_counts = {}
            for status, anime_list in cache_data.get('data', {}).items():
                count = len(anime_list)
                status_counts[status] = count
                total_anime += count
            
            return {
                'exists': True,
                'user_id': cache_data.get('user_id'),
                'timestamp': cache_timestamp,
                'datetime': cache_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                'age_hours': age_hours,
                'file_size': file_size,
                'total_anime': total_anime,
                'status_counts': status_counts
            }
            
        except Exception as e:
            return {'exists': False, 'error': str(e)}
    
    def save_detailed_anime_info(self, user_id: int, anime_details: Dict[int, Dict[str, Any]]):
        """Save detailed anime info (including synonyms) to cache"""
        try:
            cache_file = os.path.join(self.cache_dir, f"anime_details_{user_id}.json")
            
            cache_data = {
                'user_id': user_id,
                'timestamp': time.time(),
                'datetime': datetime.now().isoformat(),
                'data': anime_details
            }
            
            # Write to temporary file first, then rename for atomic operation
            temp_file = cache_file + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            # Atomic rename
            if os.path.exists(cache_file):
                os.remove(cache_file)
            os.rename(temp_file, cache_file)
            
            print(f"Detailed anime info cached: {len(anime_details)} entries")
            return True
            
        except Exception as e:
            print(f"Error saving detailed anime info: {e}")
            return False
    
    def load_detailed_anime_info(self, user_id: int) -> Optional[Dict[int, Dict[str, Any]]]:
        """Load detailed anime info from cache"""
        try:
            cache_file = os.path.join(self.cache_dir, f"anime_details_{user_id}.json")
            
            if not os.path.exists(cache_file):
                return None
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Verify cache is for correct user
            if cache_data.get('user_id') != user_id:
                return None
            
            # Convert string keys back to integers (JSON converts int keys to strings)
            data = cache_data.get('data', {})
            if data:
                # Convert string keys to integers
                converted_data = {}
                for key, value in data.items():
                    try:
                        int_key = int(key)
                        converted_data[int_key] = value
                    except (ValueError, TypeError):
                        # Skip invalid keys
                        continue
                return converted_data
            return {}
            
        except Exception as e:
            print(f"Error loading detailed anime info: {e}")
            return None
    
    # Manga cache methods
    def _get_manga_cache_file_path(self, user_id: int) -> str:
        """Get manga cache file path for specific user"""
        return os.path.join(self.cache_dir, f"manga_list_{user_id}.json")
    
    def save_manga_list(self, user_id: int, manga_list_data: Dict[str, List[Dict[str, Any]]]):
        """Save manga list data to cache"""
        try:
            cache_file = self._get_manga_cache_file_path(user_id)
            
            cache_data = {
                'user_id': user_id,
                'timestamp': time.time(),
                'datetime': datetime.now().isoformat(),
                'data': manga_list_data
            }
            
            # Write to temporary file first, then rename for atomic operation
            temp_file = cache_file + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            # Atomic rename
            if os.path.exists(cache_file):
                os.remove(cache_file)
            os.rename(temp_file, cache_file)
            
            print(f"Manga cache saved: {cache_file}")
            return True
            
        except Exception as e:
            print(f"Error saving manga cache: {e}")
            return False
    
    def load_manga_list(self, user_id: int) -> Optional[Dict[str, List[Dict[str, Any]]]]:
        """Load manga list data from cache"""
        try:
            cache_file = self._get_manga_cache_file_path(user_id)
            
            if not os.path.exists(cache_file):
                print("No manga cache file found")
                return None
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Verify cache is for correct user
            if cache_data.get('user_id') != user_id:
                print("Manga cache user ID mismatch")
                return None
            
            print(f"Manga cache loaded from: {cache_data.get('datetime', 'unknown time')}")
            return cache_data.get('data')
        
        except Exception as e:
            print(f"Error loading manga cache: {e}")
            return None
    
    def add_manga_to_cache(self, user_id: int, manga_entry: Dict[str, Any]) -> bool:
        """Add a new manga entry to the cache"""
        try:
            cache_file = self._get_manga_cache_file_path(user_id)
            
            if not os.path.exists(cache_file):
                print("No manga cache file found to add manga to")
                return False
            
            # Load current cache
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Verify cache is for correct user
            if cache_data.get('user_id') != user_id:
                print("Manga cache user ID mismatch")
                return False
            
            # Get the status to add the manga to
            status = manga_entry.get('status', 'planned')
            manga_list_data = cache_data.get('data', {})
            
            # Make sure the status list exists
            if status not in manga_list_data:
                manga_list_data[status] = []
            
            # Add the new manga entry
            manga_list_data[status].append(manga_entry)
            
            # Update timestamp to mark cache as recently modified
            cache_data['timestamp'] = time.time()
            cache_data['datetime'] = datetime.now().isoformat()
            
            # Write back to cache file
            temp_file = cache_file + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            # Atomic rename
            if os.path.exists(cache_file):
                os.remove(cache_file)
            os.rename(temp_file, cache_file)
            
            manga_id = manga_entry.get('id')
            print(f"Added manga ID {manga_id} to cache in status '{status}'")
            return True
                
        except Exception as e:
            print(f"Error adding manga to cache: {e}")
            return False
    
    def update_manga_in_cache(self, user_id: int, manga_id: int, updates: Dict[str, Any]) -> bool:
        """Update a specific manga entry in the cache"""
        try:
            cache_file = self._get_manga_cache_file_path(user_id)
            
            if not os.path.exists(cache_file):
                print("No manga cache file found to update")
                return False
            
            # Load current cache
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Verify cache is for correct user
            if cache_data.get('user_id') != user_id:
                print("Manga cache user ID mismatch")
                return False
            
            # Find and update the manga entry
            manga_list_data = cache_data.get('data', {})
            updated = False
            
            for status_key, manga_list in manga_list_data.items():
                for i, entry in enumerate(manga_list):
                    if entry.get('id') == manga_id:
                        # Check if status is changing (need to move between lists)
                        old_status = entry.get('status', '')
                        new_status = updates.get('status', old_status)
                        
                        if new_status != old_status and new_status in manga_list_data:
                            # Remove from old status list
                            manga_list_data[status_key].pop(i)
                            # Update the entry with new data
                            entry.update(updates)
                            # Add to new status list
                            manga_list_data[new_status].append(entry)
                        else:
                            # Just update in place
                            entry.update(updates)
                        
                        updated = True
                        break
                
                if updated:
                    break
            
            if updated:
                # Update timestamp to mark cache as recently modified
                cache_data['timestamp'] = time.time()
                cache_data['datetime'] = datetime.now().isoformat()
                
                # Write back to cache file
                temp_file = cache_file + '.tmp'
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, ensure_ascii=False, indent=2)
                
                # Atomic rename
                if os.path.exists(cache_file):
                    os.remove(cache_file)
                os.rename(temp_file, cache_file)
                
                print(f"Manga cache updated for manga ID {manga_id}")
                return True
            else:
                print(f"Manga ID {manga_id} not found in cache")
                return False
                
        except Exception as e:
            print(f"Error updating manga cache: {e}")
            return False
    
    def is_manga_cache_valid(self, user_id: int, max_age_hours: float = 24) -> bool:
        """Check if manga cache is valid (exists and not too old)"""
        try:
            cache_file = self._get_manga_cache_file_path(user_id)
            
            if not os.path.exists(cache_file):
                return False
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Check user ID
            if cache_data.get('user_id') != user_id:
                return False
            
            # Check age
            cache_timestamp = cache_data.get('timestamp', 0)
            current_timestamp = time.time()
            age_hours = (current_timestamp - cache_timestamp) / 3600
            
            is_valid = age_hours < max_age_hours
            print(f"Manga cache age: {age_hours:.1f} hours, valid: {is_valid}")
            return is_valid
            
        except Exception as e:
            print(f"Error checking manga cache validity: {e}")
            return False
