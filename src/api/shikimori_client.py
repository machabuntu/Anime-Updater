"""
Shikimori API Client
Handles authentication and API operations with Shikimori
"""

import requests
import time
from urllib.parse import urlencode
from typing import Optional, Dict, Any, List

class ShikimoriClient:
    """Client for Shikimori API operations"""
    
    BASE_URL = "https://shikimori.io/api"
    AUTH_URL = "https://shikimori.io/oauth"
    SERVICE_NAME = "Shikimori"
    SERVICE_URL = "https://shikimori.io"
    SERVICE_KEY = "shikimori"
    
    # Anime list statuses
    STATUSES = {
        'planned': 'Plan to Watch',
        'watching': 'Watching', 
        'completed': 'Completed',
        'dropped': 'Dropped',
        'rewatching': 'Rewatching',
        'on_hold': 'On Hold'
    }
    
    # Manga list statuses (no rewatching status for manga)
    # Note: Shikimori API uses 'watching' for currently reading manga
    MANGA_STATUSES = {
        'planned': 'Plan to Read',
        'watching': 'Reading', 
        'completed': 'Completed',
        'dropped': 'Dropped',
        'on_hold': 'On Hold'
    }
    
    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ShikimoriUpdater/1.0'
        })
        
        # Setup logging
        from utils.logger import get_logger
        self.logger = get_logger('shikimori_api')
        
        # Rate limiting for API requests
        self.api_request_delay = 0.5  # 500ms delay between requests to respect API limits
        self.last_api_request = 0
        
        # Set access token if available
        access_token = config.get('shikimori.access_token')
        if access_token:
            self.session.headers.update({
                'Authorization': f'Bearer {access_token}'
            })
    
    def get_auth_url(self, client_id: str, redirect_uri: str) -> str:
        """Get OAuth authorization URL"""
        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'user_rates'
        }
        return f"{self.AUTH_URL}/authorize?{urlencode(params)}"
    
    def exchange_code_for_token(self, client_id: str, client_secret: str, 
                               code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        data = {
            'grant_type': 'authorization_code',
            'client_id': client_id,
            'client_secret': client_secret,
            'code': code,
            'redirect_uri': redirect_uri
        }
        
        headers = {
            'User-Agent': 'ShikimoriUpdater/1.0'
        }
        
        response = requests.post(f"{self.AUTH_URL}/token", data=data, headers=headers)
        
        if response.status_code == 200:
            token_data = response.json()
            
            # Save tokens to config
            self.config.set('shikimori.access_token', token_data['access_token'])
            self.config.set('shikimori.refresh_token', token_data['refresh_token'])
            
            # Update session headers
            self.session.headers.update({
                'Authorization': f'Bearer {token_data["access_token"]}'
            })
            
            return token_data
        else:
            raise Exception(f"Failed to get access token: {response.status_code} - {response.text}")
    
    def refresh_access_token(self) -> bool:
        """Refresh access token using refresh token"""
        refresh_token = self.config.get('shikimori.refresh_token')
        client_id = self.config.get('shikimori.client_id')
        client_secret = self.config.get('shikimori.client_secret')
        
        if not all([refresh_token, client_id, client_secret]):
            return False
        
        data = {
            'grant_type': 'refresh_token',
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token
        }
        
        headers = {
            'User-Agent': 'ShikimoriUpdater/1.0'
        }
        
        try:
            response = requests.post(f"{self.AUTH_URL}/token", data=data, headers=headers)
            
            if response.status_code == 200:
                token_data = response.json()
                
                # Update tokens
                self.config.set('shikimori.access_token', token_data['access_token'])
                self.config.set('shikimori.refresh_token', token_data['refresh_token'])
                
                # Update session headers
                self.session.headers.update({
                    'Authorization': f'Bearer {token_data["access_token"]}'
                })
                
                return True
            else:
                return False
        except Exception:
            return False
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make authenticated request with automatic token refresh"""
        url = f"{self.BASE_URL}{endpoint}"
        
        response = self.session.request(method, url, **kwargs)
        
        # If unauthorized, try to refresh token
        if response.status_code == 401:
            if self.refresh_access_token():
                response = self.session.request(method, url, **kwargs)
        
        return response
    
    def _wait_for_api_rate_limit(self):
        """Ensure we don't exceed API rate limits"""
        current_time = time.time()
        time_since_last = current_time - self.last_api_request
        
        if time_since_last < self.api_request_delay:
            time.sleep(self.api_request_delay - time_since_last)
        
        self.last_api_request = time.time()
    
    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """Get current authenticated user info"""
        try:
            self.logger.debug("Fetching current user info")
            response = self._make_request('GET', '/users/whoami')
            if response.status_code == 200:
                user_data = response.json()
                username = user_data.get('nickname', 'Unknown')
                user_id = user_data.get('id', 'Unknown')
                self.logger.info(f"Successfully fetched user info: {username} (ID: {user_id})")
                self.config.set('shikimori.user_id', user_data['id'])
                return user_data
            else:
                self.logger.error(f"Failed to get user info: HTTP {response.status_code}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting current user: {e}")
            return None
    
    def get_user_anime_list(self, user_id: int, status: str = None) -> List[Dict[str, Any]]:
        """Get user's anime list with pagination support"""
        status_filter = f" with status '{status}'" if status else ""
        self.logger.info(f"Fetching anime list for user {user_id}{status_filter}")
        
        all_anime = []
        page = 1
        limit = 100  # Maximum items per page
        
        try:
            while True:
                # Rate limiting - wait before making request
                self._wait_for_api_rate_limit()
                
                params = {
                    'page': page,
                    'limit': limit
                }
                if status:
                    params['status'] = status

                self.logger.debug(f"Fetching page {page} of anime list")
                response = self._make_request('GET', f'/users/{user_id}/anime_rates', params=params)

                if response.status_code == 200:
                    page_data = response.json()

                    # If no data returned, we've reached the end
                    if not page_data:
                        break

                    all_anime.extend(page_data)
                    self.logger.debug(f"Fetched {len(page_data)} anime from page {page}, total: {len(all_anime)}")

                    # If we got less than the limit, this was the last page
                    if len(page_data) < limit:
                        break

                    page += 1
                else:
                    self.logger.error(f"Failed to fetch anime list page {page}: HTTP {response.status_code}")
                    break

            self.logger.info(f"Successfully fetched {len(all_anime)} anime{status_filter}")
            return all_anime
        except Exception as e:
            self.logger.error(f"Error fetching anime list: {e}")
            return []
    
    def get_anime_details(self, anime_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed anime information"""
        try:
            response = self._make_request('GET', f'/animes/{anime_id}')
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None
    
    def search_anime(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search for anime by name"""
        try:
            params = {
                'q': query,
                'limit': limit,
                'order': 'popularity'
            }
            response = self._make_request('GET', '/animes', params=params)
            
            if response.status_code == 200:
                results = response.json()
                # Filter out None values from the API response
                if isinstance(results, list):
                    return [item for item in results if item is not None]
                return []
            return []
        except Exception:
            return []
    
    def update_anime_progress(self, rate_id: int, episodes: int = None, 
                            score: int = None, status: str = None, 
                            rewatches: int = None, **kwargs) -> bool:
        """Update anime progress"""
        try:
            data = {}
            if episodes is not None:
                data['episodes'] = episodes
            if score is not None:
                data['score'] = score
            if status is not None:
                data['status'] = status
            if rewatches is not None:
                data['rewatches'] = rewatches
            
            # Add any additional fields from kwargs
            data.update(kwargs)
            
            update_info = ', '.join([f"{k}={v}" for k, v in data.items()])
            self.logger.info(f"Updating anime progress (rate_id: {rate_id}): {update_info}")
            
            response = self._make_request('PATCH', f'/user_rates/{rate_id}', 
                                        json={'user_rate': data})
            
            success = response.status_code == 200
            if success:
                self.logger.info(f"Successfully updated anime progress for rate_id {rate_id}")
            else:
                self.logger.error(f"Failed to update anime progress for rate_id {rate_id}: HTTP {response.status_code}")
            
            return success
        except Exception as e:
            self.logger.error(f"Error updating anime progress for rate_id {rate_id}: {e}")
            return False
    
    def add_anime_to_list(self, anime_id: int, status: str = 'planned') -> Optional[Dict[str, Any]]:
        """Add anime to user's list"""
        try:
            # Get current user ID
            user_id = self.config.get('shikimori.user_id')
            if not user_id:
                return None
            
            data = {
                'user_rate': {
                    'user_id': user_id,
                    'target_id': anime_id,
                    'target_type': 'Anime',
                    'status': status
                }
            }
            
            response = self._make_request('POST', '/user_rates', json=data)
            
            if response.status_code == 201:
                return response.json()
            return None
        except Exception:
            return None
    
    def delete_anime_from_list(self, rate_id: int) -> bool:
        """Remove anime from user's list"""
        try:
            response = self._make_request('DELETE', f'/user_rates/{rate_id}')
            return response.status_code == 204
        except Exception:
            return False
    
    # Manga methods
    def get_user_manga_list(self, user_id: int, status: str = None) -> List[Dict[str, Any]]:
        """Get user's manga list with pagination support"""
        all_manga = []
        page = 1
        limit = 100  # Maximum items per page
        
        try:
            while True:
                # Rate limiting - wait before making request
                self._wait_for_api_rate_limit()
                
                params = {
                    'page': page,
                    'limit': limit
                }
                if status:
                    params['status'] = status

                response = self._make_request('GET', f'/users/{user_id}/manga_rates', params=params)

                if response.status_code == 200:
                    page_data = response.json()

                    # If no data returned, we've reached the end
                    if not page_data:
                        break

                    all_manga.extend(page_data)

                    # If we got less than the limit, this was the last page
                    if len(page_data) < limit:
                        break

                    page += 1
                else:
                    break

            return all_manga
        except Exception as e:
            return []
    
    def get_manga_details(self, manga_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed manga information"""
        try:
            response = self._make_request('GET', f'/mangas/{manga_id}')
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None
    
    def search_manga(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search for manga by name"""
        try:
            params = {
                'q': query,
                'limit': limit,
                'order': 'popularity'
            }
            response = self._make_request('GET', '/mangas', params=params)
            
            if response.status_code == 200:
                return response.json()
            return []
        except Exception:
            return []
    
    def update_manga_progress(self, rate_id: int, chapters: int = None, volumes: int = None,
                            score: int = None, status: str = None, **kwargs) -> bool:
        """Update manga progress"""
        try:
            data = {}
            if chapters is not None:
                data['chapters'] = chapters
            if volumes is not None:
                data['volumes'] = volumes
            if score is not None:
                data['score'] = score
            if status is not None:
                data['status'] = status
            
            # Add any additional fields from kwargs
            data.update(kwargs)
            
            response = self._make_request('PATCH', f'/user_rates/{rate_id}', 
                                        json={'user_rate': data})
            
            return response.status_code == 200
        except Exception:
            return False
    
    def add_manga_to_list(self, manga_id: int, status: str = 'planned') -> Optional[Dict[str, Any]]:
        """Add manga to user's list"""
        try:
            # Get current user ID
            user_id = self.config.get('shikimori.user_id')
            if not user_id:
                return None
            
            data = {
                'user_rate': {
                    'user_id': user_id,
                    'target_id': manga_id,
                    'target_type': 'Manga',
                    'status': status
                }
            }
            
            response = self._make_request('POST', '/user_rates', json=data)
            
            if response.status_code == 201:
                return response.json()
            return None
        except Exception:
            return None
    
    def delete_manga_from_list(self, rate_id: int) -> bool:
        """Remove manga from user's list"""
        try:
            response = self._make_request('DELETE', f'/user_rates/{rate_id}')
            return response.status_code == 204
        except Exception:
            return False
