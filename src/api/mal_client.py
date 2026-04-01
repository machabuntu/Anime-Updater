"""
MyAnimeList API Client
Handles authentication and API operations with MyAnimeList.
Normalizes responses to match the Shikimori data format used by the UI.
"""

import requests
import time
import secrets
import string
from urllib.parse import urlencode
from typing import Optional, Dict, Any, List
from utils.proxy import get_proxies


class MALClient:
    """Client for MyAnimeList API v2 operations"""

    BASE_URL = "https://api.myanimelist.net/v2"
    AUTH_URL = "https://myanimelist.net/v1/oauth2"
    SERVICE_NAME = "MyAnimeList"
    SERVICE_URL = "https://myanimelist.net"
    SERVICE_KEY = "mal"

    STATUSES = {
        'planned': 'Plan to Watch',
        'watching': 'Watching',
        'completed': 'Completed',
        'dropped': 'Dropped',
        'rewatching': 'Rewatching',
        'on_hold': 'On Hold'
    }

    MANGA_STATUSES = {
        'planned': 'Plan to Read',
        'watching': 'Reading',
        'completed': 'Completed',
        'dropped': 'Dropped',
        'on_hold': 'On Hold'
    }

    # Internal status -> MAL anime API status
    _STATUS_TO_MAL_ANIME = {
        'planned': 'plan_to_watch',
        'watching': 'watching',
        'completed': 'completed',
        'dropped': 'dropped',
        'rewatching': 'watching',
        'on_hold': 'on_hold',
    }

    _MAL_ANIME_TO_STATUS = {
        'plan_to_watch': 'planned',
        'watching': 'watching',
        'completed': 'completed',
        'dropped': 'dropped',
        'on_hold': 'on_hold',
    }

    _STATUS_TO_MAL_MANGA = {
        'planned': 'plan_to_read',
        'watching': 'reading',
        'completed': 'completed',
        'dropped': 'dropped',
        'on_hold': 'on_hold',
    }

    _MAL_MANGA_TO_STATUS = {
        'plan_to_read': 'planned',
        'reading': 'watching',
        'completed': 'completed',
        'dropped': 'dropped',
        'on_hold': 'on_hold',
    }

    ANIME_LIST_FIELDS = (
        "list_status{status,score,num_episodes_watched,is_rewatching,num_times_rewatched,updated_at,comments},"
        "num_episodes,media_type,alternative_titles,start_date,status"
    )

    MANGA_LIST_FIELDS = (
        "list_status{status,score,num_volumes_read,num_chapters_read,is_rereading,num_times_reread,updated_at,comments},"
        "num_volumes,num_chapters,media_type,alternative_titles,start_date,status"
    )

    ANIME_DETAIL_FIELDS = (
        "id,title,main_picture,alternative_titles,start_date,end_date,synopsis,mean,rank,"
        "popularity,num_list_users,num_scoring_users,media_type,status,genres,num_episodes,"
        "start_season,source,average_episode_duration,rating"
    )

    MANGA_DETAIL_FIELDS = (
        "id,title,main_picture,alternative_titles,start_date,end_date,synopsis,mean,rank,"
        "popularity,num_list_users,num_scoring_users,media_type,status,genres,num_volumes,"
        "num_chapters,authors{first_name,last_name}"
    )

    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'AnimeUpdater/1.0'
        })
        self._proxies = get_proxies(self.config)
        self.session.proxies.update(self._proxies)

        from utils.logger import get_logger
        self.logger = get_logger('mal_api')

        self.api_request_delay = 0.5
        self.last_api_request = 0

        # PKCE code_verifier stored during the auth flow
        self._code_verifier: Optional[str] = None

        access_token = config.get('mal.access_token')
        if access_token:
            self.session.headers.update({
                'Authorization': f'Bearer {access_token}'
            })

    # ------------------------------------------------------------------
    # PKCE helpers
    # ------------------------------------------------------------------

    def generate_code_verifier(self) -> str:
        """Generate a PKCE code verifier (43-128 chars, URL-safe)."""
        alphabet = string.ascii_letters + string.digits + '-._~'
        self._code_verifier = ''.join(secrets.choice(alphabet) for _ in range(128))
        return self._code_verifier

    # ------------------------------------------------------------------
    # OAuth
    # ------------------------------------------------------------------

    def get_auth_url(self, client_id: str, redirect_uri: str) -> str:
        if not self._code_verifier:
            self.generate_code_verifier()
        params = {
            'response_type': 'code',
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'code_challenge': self._code_verifier,
            'code_challenge_method': 'plain',
            'state': secrets.token_urlsafe(16),
        }
        return f"{self.AUTH_URL}/authorize?{urlencode(params)}"

    def exchange_code_for_token(self, client_id: str, client_secret: str,
                                code: str, redirect_uri: str) -> Dict[str, Any]:
        if not self._code_verifier:
            raise Exception("PKCE code_verifier was not generated before token exchange")

        data = {
            'client_id': client_id,
            'client_secret': client_secret,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri,
            'code_verifier': self._code_verifier,
        }

        response = requests.post(f"{self.AUTH_URL}/token", data=data,
                                 headers={'User-Agent': 'AnimeUpdater/1.0'},
                                 proxies=self._proxies)

        if response.status_code == 200:
            token_data = response.json()
            self.config.set('mal.access_token', token_data['access_token'])
            self.config.set('mal.refresh_token', token_data['refresh_token'])
            self.session.headers.update({
                'Authorization': f'Bearer {token_data["access_token"]}'
            })
            self._code_verifier = None
            return token_data
        else:
            raise Exception(f"Failed to get access token: {response.status_code} - {response.text}")

    def refresh_access_token(self) -> bool:
        refresh_token = self.config.get('mal.refresh_token')
        client_id = self.config.get('mal.client_id')
        client_secret = self.config.get('mal.client_secret')

        if not all([refresh_token, client_id]):
            return False

        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': client_id,
        }
        if client_secret:
            data['client_secret'] = client_secret

        try:
            response = requests.post(f"{self.AUTH_URL}/token", data=data,
                                     headers={'User-Agent': 'AnimeUpdater/1.0'},
                                     proxies=self._proxies)
            if response.status_code == 200:
                token_data = response.json()
                self.config.set('mal.access_token', token_data['access_token'])
                self.config.set('mal.refresh_token', token_data['refresh_token'])
                self.session.headers.update({
                    'Authorization': f'Bearer {token_data["access_token"]}'
                })
                return True
            else:
                self.logger.error(f"MAL token refresh failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            self.logger.error(f"MAL token refresh error: {e}")
            return False

    # ------------------------------------------------------------------
    # Internal request helpers
    # ------------------------------------------------------------------

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        url = f"{self.BASE_URL}{endpoint}"
        response = self.session.request(method, url, **kwargs)
        if response.status_code == 401:
            if self.refresh_access_token():
                response = self.session.request(method, url, **kwargs)
        return response

    def _wait_for_api_rate_limit(self):
        current_time = time.time()
        time_since_last = current_time - self.last_api_request
        if time_since_last < self.api_request_delay:
            time.sleep(self.api_request_delay - time_since_last)
        self.last_api_request = time.time()

    # ------------------------------------------------------------------
    # Normalization helpers
    # ------------------------------------------------------------------

    def _normalize_anime_status(self, mal_status: str, is_rewatching: bool = False) -> str:
        if is_rewatching:
            return 'rewatching'
        return self._MAL_ANIME_TO_STATUS.get(mal_status, 'planned')

    def _normalize_manga_status(self, mal_status: str, is_rereading: bool = False) -> str:
        if is_rereading:
            return 'rewatching'
        return self._MAL_MANGA_TO_STATUS.get(mal_status, 'planned')

    def _normalize_anime_entry(self, mal_entry: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a MAL anime list entry to Shikimori-compatible format."""
        node = mal_entry.get('node', {})
        list_status = mal_entry.get('list_status', {})

        anime_id = node.get('id', 0)
        mal_status = list_status.get('status', 'plan_to_watch')
        is_rewatching = list_status.get('is_rewatching', False)
        internal_status = self._normalize_anime_status(mal_status, is_rewatching)

        aired_on = node.get('start_date', '') or ''

        return {
            'id': anime_id,
            'episodes': list_status.get('num_episodes_watched', 0),
            'score': list_status.get('score', 0),
            'status': internal_status,
            'rewatches': list_status.get('num_times_rewatched', 0),
            'text': list_status.get('comments', ''),
            'anime': {
                'id': anime_id,
                'name': node.get('title', 'Unknown'),
                'russian': '',
                'url': f"/anime/{anime_id}",
                'episodes': node.get('num_episodes', 0),
                'kind': node.get('media_type', ''),
                'aired_on': aired_on,
                'status': node.get('status', ''),
                'english': (node.get('alternative_titles') or {}).get('en', ''),
                'japanese': ((node.get('alternative_titles') or {}).get('ja') or [''])[0]
                            if isinstance((node.get('alternative_titles') or {}).get('ja'), list)
                            else (node.get('alternative_titles') or {}).get('ja', ''),
                'synonyms': (node.get('alternative_titles') or {}).get('synonyms', []),
            }
        }

    def _normalize_manga_entry(self, mal_entry: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a MAL manga list entry to Shikimori-compatible format."""
        node = mal_entry.get('node', {})
        list_status = mal_entry.get('list_status', {})

        manga_id = node.get('id', 0)
        mal_status = list_status.get('status', 'plan_to_read')
        is_rereading = list_status.get('is_rereading', False)
        internal_status = self._normalize_manga_status(mal_status, is_rereading)

        aired_on = node.get('start_date', '') or ''

        return {
            'id': manga_id,
            'chapters': list_status.get('num_chapters_read', 0),
            'volumes': list_status.get('num_volumes_read', 0),
            'score': list_status.get('score', 0),
            'status': internal_status,
            'text': list_status.get('comments', ''),
            'manga': {
                'id': manga_id,
                'name': node.get('title', 'Unknown'),
                'russian': '',
                'url': f"/manga/{manga_id}",
                'chapters': node.get('num_chapters', 0),
                'volumes': node.get('num_volumes', 0),
                'kind': node.get('media_type', ''),
                'aired_on': aired_on,
                'status': node.get('status', ''),
            }
        }

    def _normalize_search_anime(self, mal_node: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a MAL anime search result node to Shikimori-compatible format."""
        node = mal_node.get('node', mal_node)
        anime_id = node.get('id', 0)
        aired_on = node.get('start_date', '') or ''
        return {
            'id': anime_id,
            'name': node.get('title', 'Unknown'),
            'russian': '',
            'url': f"/anime/{anime_id}",
            'episodes': node.get('num_episodes', 0),
            'kind': node.get('media_type', ''),
            'aired_on': aired_on,
            'status': node.get('status', ''),
        }

    def _normalize_search_manga(self, mal_node: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a MAL manga search result node to Shikimori-compatible format."""
        node = mal_node.get('node', mal_node)
        manga_id = node.get('id', 0)
        aired_on = node.get('start_date', '') or ''
        return {
            'id': manga_id,
            'name': node.get('title', 'Unknown'),
            'russian': '',
            'url': f"/manga/{manga_id}",
            'chapters': node.get('num_chapters', 0),
            'volumes': node.get('num_volumes', 0),
            'kind': node.get('media_type', ''),
            'aired_on': aired_on,
            'status': node.get('status', ''),
        }

    # ------------------------------------------------------------------
    # User
    # ------------------------------------------------------------------

    def get_current_user(self) -> Optional[Dict[str, Any]]:
        try:
            self.logger.debug("Fetching current MAL user info")
            response = self._make_request('GET', '/users/@me',
                                          params={'fields': 'anime_statistics'})
            if response.status_code == 200:
                data = response.json()
                user_id = data.get('id', 0)
                username = data.get('name', 'Unknown')
                self.logger.info(f"MAL user: {username} (ID: {user_id})")
                self.config.set('mal.user_id', user_id)
                return {
                    'id': user_id,
                    'nickname': username,
                    'name': username,
                    'avatar': data.get('picture', ''),
                }
            else:
                self.logger.error(f"MAL user info failed: HTTP {response.status_code}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting MAL user: {e}")
            return None

    # ------------------------------------------------------------------
    # Anime list
    # ------------------------------------------------------------------

    def get_user_anime_list(self, user_id: int, status: str = None) -> List[Dict[str, Any]]:
        status_filter = f" with status '{status}'" if status else ""
        self.logger.info(f"Fetching MAL anime list{status_filter}")

        all_anime: List[Dict[str, Any]] = []
        offset = 0
        limit = 1000

        mal_status = self._STATUS_TO_MAL_ANIME.get(status) if status else None
        is_rewatching_filter = (status == 'rewatching')

        try:
            while True:
                self._wait_for_api_rate_limit()
                params: Dict[str, Any] = {
                    'fields': self.ANIME_LIST_FIELDS,
                    'limit': limit,
                    'offset': offset,
                    'nsfw': 'true',
                }
                if mal_status and not is_rewatching_filter:
                    params['status'] = mal_status

                response = self._make_request('GET', '/users/@me/animelist', params=params)

                if response.status_code != 200:
                    self.logger.error(f"MAL anime list fetch failed: HTTP {response.status_code}")
                    break

                data = response.json()
                page_data = data.get('data', [])
                if not page_data:
                    break

                for entry in page_data:
                    normalized = self._normalize_anime_entry(entry)
                    if is_rewatching_filter:
                        if normalized['status'] == 'rewatching':
                            all_anime.append(normalized)
                    elif status and normalized['status'] != status:
                        continue
                    else:
                        all_anime.append(normalized)

                next_url = (data.get('paging') or {}).get('next')
                if not next_url or len(page_data) < limit:
                    break
                offset += limit

            self.logger.info(f"Fetched {len(all_anime)} anime from MAL{status_filter}")
            return all_anime
        except Exception as e:
            self.logger.error(f"Error fetching MAL anime list: {e}")
            return []

    def get_anime_details(self, anime_id: int) -> Optional[Dict[str, Any]]:
        try:
            self._wait_for_api_rate_limit()
            response = self._make_request('GET', f'/anime/{anime_id}',
                                          params={'fields': self.ANIME_DETAIL_FIELDS})
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None

    SEASONAL_FIELDS = (
        "id,title,main_picture,alternative_titles,start_date,end_date,"
        "mean,rank,popularity,num_list_users,media_type,status,"
        "num_episodes,start_season,genres,rating"
    )

    def get_seasonal_anime(self, year: int, season: str, sort: str = 'anime_num_list_users',
                           limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get anime for a specific season from MAL.

        ``season`` should be one of: winter, spring, summer, fall.
        Returns normalized Shikimori-compatible dicts.
        """
        try:
            all_anime: List[Dict[str, Any]] = []
            while True:
                self._wait_for_api_rate_limit()
                params: Dict[str, Any] = {
                    'sort': sort,
                    'limit': min(limit, 500),
                    'offset': offset,
                    'fields': self.SEASONAL_FIELDS,
                    'nsfw': 'true',
                }
                response = self._make_request(
                    'GET', f'/anime/season/{year}/{season}', params=params)

                if response.status_code != 200:
                    self.logger.error(
                        f"MAL seasonal anime fetch failed: HTTP {response.status_code}")
                    break

                data = response.json()
                page_data = data.get('data', [])
                if not page_data:
                    break

                for entry in page_data:
                    normalized = self._normalize_seasonal_anime(entry)
                    if normalized:
                        all_anime.append(normalized)

                next_url = (data.get('paging') or {}).get('next')
                if not next_url or len(page_data) < limit:
                    break
                offset += len(page_data)

            self.logger.info(f"Fetched {len(all_anime)} seasonal anime from MAL for {season} {year}")
            return all_anime
        except Exception as e:
            self.logger.error(f"Error fetching MAL seasonal anime: {e}")
            return []

    def _normalize_seasonal_anime(self, mal_entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize a MAL seasonal anime entry to Shikimori-like format."""
        node = mal_entry.get('node', mal_entry)
        if not node:
            return None
        anime_id = node.get('id', 0)
        aired_on = node.get('start_date', '') or ''
        mean = node.get('mean', 0) or 0
        return {
            'id': anime_id,
            'name': node.get('title', 'Unknown'),
            'russian': '',
            'url': f"/anime/{anime_id}",
            'episodes': node.get('num_episodes', 0),
            'episodes_aired': 0,
            'kind': node.get('media_type', ''),
            'aired_on': aired_on,
            'status': node.get('status', ''),
            'score': str(mean) if mean else '0',
            'image': node.get('main_picture', {}),
            'popularity': node.get('popularity', 0),
            'num_list_users': node.get('num_list_users', 0),
            'rating': node.get('rating', ''),
            'genres': [g.get('name', '') for g in (node.get('genres') or [])],
        }

    def search_anime(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            self._wait_for_api_rate_limit()
            params = {
                'q': query,
                'limit': min(limit, 100),
                'fields': 'num_episodes,media_type,start_date,alternative_titles,status',
                'nsfw': 'true',
            }
            response = self._make_request('GET', '/anime', params=params)
            if response.status_code == 200:
                data = response.json()
                results = data.get('data', [])
                return [self._normalize_search_anime(r) for r in results if r is not None]
            return []
        except Exception:
            return []

    def update_anime_progress(self, rate_id: int, episodes: int = None,
                              score: int = None, status: str = None,
                              rewatches: int = None, **kwargs) -> bool:
        """rate_id is actually anime_id for MAL."""
        try:
            data = {}
            if episodes is not None:
                data['num_watched_episodes'] = episodes
            if score is not None:
                data['score'] = score
            if status is not None:
                if status == 'rewatching':
                    data['status'] = 'watching'
                    data['is_rewatching'] = 'true'
                else:
                    mal_status = self._STATUS_TO_MAL_ANIME.get(status, status)
                    data['status'] = mal_status
                    data['is_rewatching'] = 'false'
            if rewatches is not None:
                data['num_times_rewatched'] = rewatches

            update_info = ', '.join([f"{k}={v}" for k, v in data.items()])
            self.logger.info(f"Updating MAL anime progress (anime_id: {rate_id}): {update_info}")

            self._wait_for_api_rate_limit()
            response = self._make_request('PATCH', f'/anime/{rate_id}/my_list_status', data=data)
            success = response.status_code == 200
            if success:
                self.logger.info(f"MAL anime update success for anime_id {rate_id}")
            else:
                self.logger.error(f"MAL anime update failed for anime_id {rate_id}: HTTP {response.status_code} - {response.text}")
            return success
        except Exception as e:
            self.logger.error(f"Error updating MAL anime progress: {e}")
            return False

    def add_anime_to_list(self, anime_id: int, status: str = 'planned') -> Optional[Dict[str, Any]]:
        try:
            mal_status = self._STATUS_TO_MAL_ANIME.get(status, 'plan_to_watch')
            data = {'status': mal_status}

            self._wait_for_api_rate_limit()
            response = self._make_request('PATCH', f'/anime/{anime_id}/my_list_status', data=data)

            if response.status_code == 200:
                result = response.json()
                return {
                    'id': anime_id,
                    'status': status,
                    'episodes': result.get('num_episodes_watched', 0),
                    'score': result.get('score', 0),
                }
            return None
        except Exception:
            return None

    def delete_anime_from_list(self, rate_id: int) -> bool:
        """rate_id is actually anime_id for MAL."""
        try:
            self._wait_for_api_rate_limit()
            response = self._make_request('DELETE', f'/anime/{rate_id}/my_list_status')
            return response.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Manga list
    # ------------------------------------------------------------------

    def get_user_manga_list(self, user_id: int, status: str = None) -> List[Dict[str, Any]]:
        self.logger.info(f"Fetching MAL manga list" + (f" with status '{status}'" if status else ""))

        all_manga: List[Dict[str, Any]] = []
        offset = 0
        limit = 1000

        mal_status = self._STATUS_TO_MAL_MANGA.get(status) if status else None

        try:
            while True:
                self._wait_for_api_rate_limit()
                params: Dict[str, Any] = {
                    'fields': self.MANGA_LIST_FIELDS,
                    'limit': limit,
                    'offset': offset,
                    'nsfw': 'true',
                }
                if mal_status:
                    params['status'] = mal_status

                response = self._make_request('GET', '/users/@me/mangalist', params=params)

                if response.status_code != 200:
                    self.logger.error(f"MAL manga list fetch failed: HTTP {response.status_code}")
                    break

                data = response.json()
                page_data = data.get('data', [])
                if not page_data:
                    break

                for entry in page_data:
                    normalized = self._normalize_manga_entry(entry)
                    if status and normalized['status'] != status:
                        continue
                    all_manga.append(normalized)

                next_url = (data.get('paging') or {}).get('next')
                if not next_url or len(page_data) < limit:
                    break
                offset += limit

            self.logger.info(f"Fetched {len(all_manga)} manga from MAL")
            return all_manga
        except Exception as e:
            self.logger.error(f"Error fetching MAL manga list: {e}")
            return []

    def get_manga_details(self, manga_id: int) -> Optional[Dict[str, Any]]:
        try:
            self._wait_for_api_rate_limit()
            response = self._make_request('GET', f'/manga/{manga_id}',
                                          params={'fields': self.MANGA_DETAIL_FIELDS})
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None

    def search_manga(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            self._wait_for_api_rate_limit()
            params = {
                'q': query,
                'limit': min(limit, 100),
                'fields': 'num_volumes,num_chapters,media_type,start_date,alternative_titles,status',
                'nsfw': 'true',
            }
            response = self._make_request('GET', '/manga', params=params)
            if response.status_code == 200:
                data = response.json()
                results = data.get('data', [])
                return [self._normalize_search_manga(r) for r in results if r is not None]
            return []
        except Exception:
            return []

    def update_manga_progress(self, rate_id: int, chapters: int = None, volumes: int = None,
                              score: int = None, status: str = None, **kwargs) -> bool:
        """rate_id is actually manga_id for MAL."""
        try:
            data = {}
            if chapters is not None:
                data['num_chapters_read'] = chapters
            if volumes is not None:
                data['num_volumes_read'] = volumes
            if score is not None:
                data['score'] = score
            if status is not None:
                mal_status = self._STATUS_TO_MAL_MANGA.get(status, status)
                data['status'] = mal_status

            self._wait_for_api_rate_limit()
            response = self._make_request('PATCH', f'/manga/{rate_id}/my_list_status', data=data)
            return response.status_code == 200
        except Exception:
            return False

    def add_manga_to_list(self, manga_id: int, status: str = 'planned') -> Optional[Dict[str, Any]]:
        try:
            mal_status = self._STATUS_TO_MAL_MANGA.get(status, 'plan_to_read')
            data = {'status': mal_status}

            self._wait_for_api_rate_limit()
            response = self._make_request('PATCH', f'/manga/{manga_id}/my_list_status', data=data)

            if response.status_code == 200:
                result = response.json()
                return {
                    'id': manga_id,
                    'status': status,
                    'chapters': result.get('num_chapters_read', 0),
                    'volumes': result.get('num_volumes_read', 0),
                    'score': result.get('score', 0),
                }
            return None
        except Exception:
            return None

    def delete_manga_from_list(self, rate_id: int) -> bool:
        """rate_id is actually manga_id for MAL."""
        try:
            self._wait_for_api_rate_limit()
            response = self._make_request('DELETE', f'/manga/{rate_id}/my_list_status')
            return response.status_code == 200
        except Exception:
            return False
