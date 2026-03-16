"""
Enhanced Anime Name Matcher with Synonym Support
Intelligently fetches and caches detailed anime info including synonyms for better matching
"""

import re
import time
import threading
from typing import List, Dict, Any, Optional, Tuple, Set
from difflib import SequenceMatcher
from .anime_matcher import AnimeMatcher

class EnhancedAnimeMatcher(AnimeMatcher):
    """Enhanced matcher with synonym support and intelligent caching"""
    
    def __init__(self, shikimori_client, cache_manager):
        super().__init__()
        self.shikimori_client = shikimori_client
        self.cache_manager = cache_manager
        self.detailed_anime_cache = {}  # In-memory cache
        self.cache_loaded = False
        self.api_request_delay = 1.0  # 1000ms delay between API requests (1 request per second to avoid limits)
        self.last_api_request = 0
        
        # Setup logging
        from utils.logger import get_logger
        self.logger = get_logger('enhanced_matcher')
        
        # Periodic updater for non-released anime
        self.periodic_updater_running = False
        self.periodic_updater_thread = None
        # Get update interval from config (default 1 hour)
        from core.config import Config
        config = Config()
        self.update_interval = config.get('detailed_cache.update_interval_hours', 1) * 3600  # Convert hours to seconds
        self.on_cache_updated_callback = None  # Callback for when cache is updated
        
    def initialize_detailed_cache(self, user_id: int, anime_list_data: Dict[str, List[Dict[str, Any]]]):
        """Initialize detailed anime cache with synonyms for user's anime list"""
        self.logger.info("Initializing enhanced anime matching with synonyms...")
        
        # Try to load from disk cache first
        cached_details = self.cache_manager.load_detailed_anime_info(user_id)
        if cached_details:
            self.detailed_anime_cache = cached_details
            self.cache_loaded = True
            self.logger.info(f"Loaded detailed anime info from cache: {len(cached_details)} entries")
        
        # Always check if we need to update cache (missing anime or old cache)
        anime_ids = self._get_all_anime_ids_from_list(anime_list_data)
        
        if cached_details:
            missing_ids = anime_ids - set(cached_details.keys())
            
            if missing_ids:
                self.logger.info(f"Found {len(missing_ids)} anime missing detailed info, fetching in background...")
                threading.Thread(target=self._fetch_missing_details, 
                               args=(user_id, missing_ids), daemon=True).start()
            else:
                self.logger.info("All anime details already cached!")
            return
        
        # No cache found, need to fetch all details
        self.logger.info(f"No detailed cache found, fetching info for {len(anime_ids)} anime in background...")
        
        # Fetch in background to avoid blocking startup
        threading.Thread(target=self._fetch_all_details, 
                        args=(user_id, anime_ids), daemon=True).start()
    
    def _get_all_anime_ids_from_list(self, anime_list_data: Dict[str, List[Dict[str, Any]]]) -> Set[int]:
        """Extract all anime IDs from user's list"""
        anime_ids = set()
        for status_list in anime_list_data.values():
            for anime_entry in status_list:
                anime = anime_entry.get('anime', {})
                if anime and 'id' in anime:
                    anime_ids.add(anime['id'])
        return anime_ids
    
    def _fetch_all_details(self, user_id: int, anime_ids: Set[int]):
        """Fetch detailed info for all anime IDs"""
        detailed_info = {}
        total = len(anime_ids)
        
        for i, anime_id in enumerate(anime_ids):
            try:
                # Rate limiting
                self._wait_for_api_rate_limit()
                
                print(f"Fetching detailed info: {i+1}/{total} ({anime_id})")
                details = self.shikimori_client.get_anime_details(anime_id)
                
                if details:
                    detailed_info[anime_id] = details
                    # Save progress periodically
                    if len(detailed_info) % 20 == 0:
                        self._save_progress(user_id, detailed_info)
                
            except Exception as e:
                print(f"Error fetching details for anime {anime_id}: {e}")
                continue
        
        # Final save
        self.detailed_anime_cache.update(detailed_info)
        self.cache_manager.save_detailed_anime_info(user_id, self.detailed_anime_cache)
        self.cache_loaded = True
        
        print(f"Enhanced anime matching ready! Cached {len(detailed_info)} detailed entries")
    
    def _fetch_missing_details(self, user_id: int, missing_ids: Set[int]):
        """Fetch detailed info for missing anime IDs"""
        total = len(missing_ids)
        fetched_count = 0
        
        for i, anime_id in enumerate(missing_ids):
            try:
                # Rate limiting
                self._wait_for_api_rate_limit()
                
                print(f"Fetching missing detailed info: {i+1}/{total} ({anime_id})")
                details = self.shikimori_client.get_anime_details(anime_id)
                
                if details:
                    self.detailed_anime_cache[anime_id] = details
                    fetched_count += 1
                    
                    # Save progress periodically
                    if fetched_count % 20 == 0:
                        self.cache_manager.save_detailed_anime_info(user_id, self.detailed_anime_cache)
                        print(f"Progress saved: {fetched_count}/{total} entries cached")
                    
            except Exception as e:
                print(f"Error fetching details for anime {anime_id}: {e}")
                continue
        
        # Final save
        self.cache_manager.save_detailed_anime_info(user_id, self.detailed_anime_cache)
        print(f"Updated detailed cache with {fetched_count} new entries (total: {len(self.detailed_anime_cache)})")
    
    def _save_progress(self, user_id: int, detailed_info: Dict[int, Dict[str, Any]]):
        """Save progress to cache"""
        self.detailed_anime_cache.update(detailed_info)
        self.cache_manager.save_detailed_anime_info(user_id, self.detailed_anime_cache)
    
    def _wait_for_api_rate_limit(self):
        """Ensure we don't exceed API rate limits"""
        current_time = time.time()
        time_since_last = current_time - self.last_api_request
        
        if time_since_last < self.api_request_delay:
            time.sleep(self.api_request_delay - time_since_last)
        
        self.last_api_request = time.time()
    
    def find_best_match(self, detected_name: str, anime_list: List[Dict[str, Any]], 
                       episode_number: int = None) -> Optional[Tuple[Dict[str, Any], float]]:
        """
        Enhanced find_best_match with synonym support
        
        Args:
            detected_name: Name detected from video file
            anime_list: List of anime from user's list
            episode_number: Episode number (used for additional validation)
            
        Returns:
            Tuple of (best_match, similarity_score) or None
        """
        if not detected_name or not anime_list:
            return None
        
        cleaned_detected = self._clean_name(detected_name)
        best_match = None
        best_score = 0.0
        
        for anime_entry in anime_list:
            anime = anime_entry.get('anime', {})
            if not anime:
                continue
            
            # Get enhanced names including synonyms from detailed cache
            names = self._get_enhanced_anime_names(anime)
            
            best_anime_score = 0.0
            # Calculate similarity with each name
            for name in names:
                score = self._calculate_similarity(cleaned_detected, name)
                best_anime_score = max(best_anime_score, score)
                
                if score > best_score:
                    # Additional validation for episode number
                    if episode_number is not None:
                        total_episodes = anime.get('episodes', 0)
                        if total_episodes > 0 and episode_number > total_episodes:
                            # Skip if episode number exceeds total episodes
                            continue
                    
                    best_score = score
                    best_match = anime_entry
        
        # Only return matches above threshold
        if best_score >= self.similarity_threshold:
            return (best_match, best_score)
        
        return None
    
    def _get_enhanced_anime_names(self, anime: Dict[str, Any]) -> List[str]:
        """Get all possible names including synonyms from detailed cache"""
        names = []
        anime_id = anime.get('id')
        
        # Start with basic names from the anime list entry
        names.extend(self._get_all_anime_names(anime))
        
        # Add synonyms from detailed cache if available
        if anime_id and anime_id in self.detailed_anime_cache:
            detailed_info = self.detailed_anime_cache[anime_id]
            
            # Add synonyms
            synonyms = detailed_info.get('synonyms', [])
            if isinstance(synonyms, list):
                names.extend([self._clean_name(synonym) for synonym in synonyms])
            
            # Add English names if not already included
            english = detailed_info.get('english', [])
            if isinstance(english, list):
                names.extend([self._clean_name(name) for name in english])
            elif isinstance(english, str):
                names.append(self._clean_name(english))
            
            # Add Japanese names if not already included
            japanese = detailed_info.get('japanese', [])
            if isinstance(japanese, list):
                names.extend([self._clean_name(name) for name in japanese])
            elif isinstance(japanese, str):
                names.append(self._clean_name(japanese))
        
        # Remove empty names and duplicates
        names = list(set([name for name in names if name]))
        
        return names
    
    def get_matching_status(self) -> str:
        """Get status of synonym matching capability"""
        if not self.cache_loaded:
            return "Loading synonyms..."
        
        total_cached = len(self.detailed_anime_cache)
        return f"Enhanced matching ready ({total_cached} anime with synonyms)"
    
    def force_refresh_synonyms(self, user_id: int, anime_list_data: Dict[str, List[Dict[str, Any]]]):
        """Force refresh of synonym cache"""
        self.detailed_anime_cache.clear()
        self.cache_loaded = False
        
        # Clear disk cache
        import os
        cache_file = os.path.join(self.cache_manager.cache_dir, f"anime_details_{user_id}.json")
        if os.path.exists(cache_file):
            os.remove(cache_file)
        
        # Reinitialize
        self.initialize_detailed_cache(user_id, anime_list_data)
    
    def start_periodic_updater(self, user_id: int):
        """Start periodic updating of non-released anime details"""
        if self.periodic_updater_running:
            self.logger.debug("Periodic updater already running, skipping start")
            return
            
        self.periodic_updater_running = True
        self.periodic_updater_thread = threading.Thread(
            target=self._periodic_update_loop, 
            args=(user_id,), 
            daemon=True
        )
        self.periodic_updater_thread.start()
        self.logger.info(f"Started periodic updater for non-released anime details (interval: {self.update_interval//3600}h)")
    
    def stop_periodic_updater(self):
        """Stop periodic updating"""
        if not self.periodic_updater_running:
            self.logger.debug("Periodic updater not running, skipping stop")
            return
            
        self.logger.info("Stopping periodic updater for anime details")
        self.periodic_updater_running = False
        if self.periodic_updater_thread:
            self.periodic_updater_thread.join(timeout=2)
        self.logger.info("Periodic updater stopped successfully")
    
    def _periodic_update_loop(self, user_id: int):
        """Main loop for periodic updates"""
        self.logger.info("Periodic update loop started")
        
        while self.periodic_updater_running:
            try:
                # Wait for the update interval
                self.logger.debug(f"Waiting {self.update_interval//3600}h for next periodic update")
                for _ in range(self.update_interval):
                    if not self.periodic_updater_running:
                        break
                    time.sleep(1)
                
                if not self.periodic_updater_running:
                    break
                    
                # Update non-released anime
                self.logger.info("Starting periodic update of non-released anime")
                self._update_non_released_anime(user_id)
                
            except Exception as e:
                self.logger.error(f"Error in periodic update loop: {e}", exc_info=True)
                # Wait a bit before retrying
                time.sleep(60)
        
        self.logger.info("Periodic update loop ended")
    
    def _update_non_released_anime(self, user_id: int):
        """Update detailed info for anime that are not released"""
        if not self.detailed_anime_cache:
            self.logger.warning("No detailed cache available for periodic update")
            return
            
        # Find anime that are not released
        non_released_ids = []
        status_counts = {}
        
        for anime_id, details in self.detailed_anime_cache.items():
            status = details.get('status', '').lower()
            if status:
                status_counts[status] = status_counts.get(status, 0) + 1
                if status != 'released':
                    non_released_ids.append(anime_id)
        
        self.logger.info(f"Cache status distribution: {status_counts}")
        
        if not non_released_ids:
            self.logger.info("No non-released anime found for periodic update")
            return
            
        self.logger.info(f"Updating {len(non_released_ids)} non-released anime details...")
        
        updated_count = 0
        status_changes = []
        
        for anime_id in non_released_ids:
            if not self.periodic_updater_running:
                self.logger.info("Periodic update interrupted, stopping")
                break
                
            try:
                # Rate limiting
                self._wait_for_api_rate_limit()
                
                # Get current status for comparison
                old_status = self.detailed_anime_cache.get(anime_id, {}).get('status', 'unknown')
                
                # Fetch updated details
                self.logger.debug(f"Fetching updated details for anime {anime_id}")
                details = self.shikimori_client.get_anime_details(anime_id)
                
                if details:
                    new_status = details.get('status', 'unknown')
                    
                    # Update cache - ensure we actually update the existing entry
                    if anime_id in self.detailed_anime_cache:
                        self.detailed_anime_cache[anime_id].update(details)
                    else:
                        self.detailed_anime_cache[anime_id] = details
                    updated_count += 1
                    
                    # Track status changes
                    if old_status != new_status:
                        anime_name = details.get('name', f'ID:{anime_id}')
                        status_changes.append(f"{anime_name}: {old_status} -> {new_status}")
                        self.logger.info(f"Status change detected: {anime_name} ({anime_id}): {old_status} -> {new_status}")
                    
                    # Save progress periodically
                    if updated_count % 10 == 0:
                        self.cache_manager.save_detailed_anime_info(user_id, self.detailed_anime_cache)
                        self.logger.info(f"Periodic update progress: {updated_count}/{len(non_released_ids)} updated")
                else:
                    self.logger.warning(f"Failed to fetch details for anime {anime_id}")
                        
            except Exception as e:
                self.logger.error(f"Error updating anime {anime_id} during periodic update: {e}")
                continue
        
        # Final save
        if updated_count > 0:
            self.cache_manager.save_detailed_anime_info(user_id, self.detailed_anime_cache)
            
            if status_changes:
                self.logger.info(f"Periodic update completed: {updated_count}/{len(non_released_ids)} anime updated, {len(status_changes)} status changes:")
                for change in status_changes:
                    self.logger.info(f"  - {change}")
            else:
                self.logger.info(f"Periodic update completed: {updated_count}/{len(non_released_ids)} anime updated, no status changes")
            
            # Trigger UI refresh callback if available
            if hasattr(self, 'on_cache_updated_callback') and self.on_cache_updated_callback:
                self.logger.debug("Triggering UI refresh callback")
                self.on_cache_updated_callback()
        else:
            self.logger.info("Periodic update completed: no anime were updated")
    
    def set_cache_updated_callback(self, callback):
        """Set callback to be called when cache is updated"""
        self.on_cache_updated_callback = callback
    
    def search_anime(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search for anime by name using the active service API"""
        return self.shikimori_client.search_anime(query, limit)
