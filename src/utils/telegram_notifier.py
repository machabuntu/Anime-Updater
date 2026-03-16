"""
Telegram Notifier for Anime Progress Updates
"""

import requests
import threading
import time
from typing import Optional, Dict, Any
from utils.logger import get_logger

class TelegramNotifier:
    """Send anime progress updates to Telegram channel"""
    
    def __init__(self, config):
        self.config = config
        self.logger = get_logger('telegram_notifier')
        self.base_url = "https://api.telegram.org/bot{token}/{method}"
        
    def _get_service_base_url(self) -> str:
        service = self.config.get('service.active', 'shikimori')
        if service == 'mal':
            return "https://myanimelist.net"
        return "https://shikimori.io"

    def is_enabled(self) -> bool:
        """Check if Telegram notifications are enabled"""
        return self.config.get('telegram.enabled', False)
    
    def send_progress_update(self, anime_name: str, episode: int, total_episodes: int, username: str, anime_url: str = ''):
        """Send progress update for watching anime"""
        if not self.is_enabled():
            return
        
        # Check filter - only send if "any progress" is enabled
        if not self.config.get('telegram.send_progress', False):
            return
        
        # Format anime name as hyperlink if URL is available
        if anime_url:
            # Ensure URL is absolute
            if anime_url.startswith('/'):
                full_url = f"{self._get_service_base_url()}{anime_url}"
            else:
                full_url = anime_url
            anime_display = f"<a href='{full_url}'>{anime_name}</a>"
        else:
            anime_display = anime_name
        
        # Multi-line formatted message
        message = f"📺 <b>Episode Watched</b>\n"
        message += f"👤 <b>User:</b> {username}\n"
        message += f"🎬 <b>Anime:</b> {anime_display}\n"
        message += f"📋 <b>Progress:</b> Episode {episode}"
        if total_episodes > 0:
            message += f" of {total_episodes}"
        
        self._send_message_async(message)
    
    def send_completion_update(self, anime_name: str, score: int, username: str, is_rewatch: bool = False, rewatch_count: int = 0, anime_url: str = '', comment: str = ''):
        """Send completion update for completed anime"""
        if not self.is_enabled():
            return
        
        # Both filters allow completion messages
        if not (self.config.get('telegram.send_progress', False) or 
                self.config.get('telegram.send_completed', False)):
            return
        
        # Format anime name as hyperlink if URL is available
        if anime_url:
            # Ensure URL is absolute
            if anime_url.startswith('/'):
                full_url = f"{self._get_service_base_url()}{anime_url}"
            else:
                full_url = anime_url
            anime_display = f"<a href='{full_url}'>{anime_name}</a>"
        else:
            anime_display = anime_name
        
        # Multi-line formatted message
        if is_rewatch and rewatch_count > 0:
            message = f"🔄 <b>Anime Rewatched</b>\n"
            message += f"👤 <b>User:</b> {username}\n"
            message += f"🎬 <b>Anime:</b> {anime_display}\n"
            message += f"🔢 <b>Rewatch Count:</b> {rewatch_count}"
            if score > 0:
                message += f"\n⭐ <b>Score:</b> {score}/10"
        else:
            message = f"🎉 <b>Anime Completed</b>\n"
            message += f"👤 <b>User:</b> {username}\n"
            message += f"🎬 <b>Anime:</b> {anime_display}"
            if score > 0:
                message += f"\n⭐ <b>Score:</b> {score}/10"
        
        # Add comment if exists
        if comment:
            message += f"\n💭 <b>Comment:</b> {comment}"
        
        self._send_message_async(message)
    
    def send_status_change_update(self, anime_name: str, old_status: str, new_status: str, score: int, username: str, anime_url: str = '', comment: str = ''):
        """Send status change update for manually changed anime status"""
        if not self.is_enabled():
            return
        
        # Check specific status change settings
        if new_status == 'dropped':
            if not self.config.get('telegram.send_dropped', False):
                return
        elif new_status == 'rewatching':
            if not self.config.get('telegram.send_rewatching', False):
                return
        else:
            # For other status changes, don't send notifications
            return
        
        # Format anime name as hyperlink if URL is available
        if anime_url:
            # Ensure URL is absolute
            if anime_url.startswith('/'):
                full_url = f"{self._get_service_base_url()}{anime_url}"
            else:
                full_url = anime_url
            anime_display = f"<a href='{full_url}'>{anime_name}</a>"
        else:
            anime_display = anime_name
        
        # Multi-line formatted message
        if new_status == 'dropped':
            message = f"❌ <b>Anime Dropped</b>\n"
        elif new_status == 'rewatching':
            message = f"🔄 <b>Started Rewatching</b>\n"
        
        message += f"👤 <b>User:</b> {username}\n"
        message += f"🎬 <b>Anime:</b> {anime_display}\n"
        message += f"📊 <b>Status:</b> {old_status} → {new_status}"
        
        if score > 0:
            message += f"\n⭐ <b>Score:</b> {score}/10"
        
        # Add comment if exists
        if comment:
            message += f"\n💭 <b>Comment:</b> {comment}"
        
        self._send_message_async(message)
    
    def send_comment_update(self, anime_name: str, comment: str, username: str, anime_url: str = ''):
        """Send notification when a comment is added to anime"""
        if not self.is_enabled():
            return
        
        # For now, always send comment notifications if telegram is enabled
        # Future: could add a specific setting for comment notifications
        
        # Format anime name as hyperlink if URL is available
        if anime_url:
            # Ensure URL is absolute
            if anime_url.startswith('/'):
                full_url = f"{self._get_service_base_url()}{anime_url}"
            else:
                full_url = anime_url
            anime_display = f"<a href='{full_url}'>{anime_name}</a>"
        else:
            anime_display = anime_name
        
        # Multi-line formatted message
        message = f"💭 <b>Comment Added</b>\n"
        message += f"👤 <b>User:</b> {username}\n"
        message += f"🎬 <b>Anime:</b> {anime_display}\n"
        message += f"💬 <b>Comment:</b> {comment}"
        
        self._send_message_async(message)
    
    def _send_message_async(self, message: str):
        """Send message asynchronously to avoid blocking UI"""
        def send():
            try:
                self._send_message(message)
            except Exception as e:
                self.logger.error(f"Failed to send Telegram message: {e}")
        
        threading.Thread(target=send, daemon=True).start()
    
    def _send_message(self, message: str):
        """Send message to Telegram channel/chat"""
        bot_token = self.config.get('telegram.bot_token', '')
        chat_id = self.config.get('telegram.chat_id', '')
        
        if not bot_token or not chat_id:
            self.logger.warning("Telegram bot token or chat ID not configured")
            return
        
        url = self.base_url.format(token=bot_token, method='sendMessage')
        
        data = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        
        try:
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if not result.get('ok', False):
                error_description = result.get('description', 'Unknown error')
                self.logger.error(f"Telegram API error: {error_description}")
            else:
                self.logger.debug(f"Successfully sent message to Telegram: {message}")
                
        except requests.RequestException as e:
            self.logger.error(f"Network error sending Telegram message: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error sending Telegram message: {e}")
    
    def test_connection(self) -> tuple[bool, str]:
        """Test Telegram bot connection and return (success, message)"""
        bot_token = self.config.get('telegram.bot_token', '')
        
        if not bot_token:
            return False, "Bot token not configured"
        
        url = self.base_url.format(token=bot_token, method='getMe')
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result.get('ok', False):
                bot_info = result.get('result', {})
                bot_name = bot_info.get('username', 'Unknown')
                return True, f"Connected to bot: @{bot_name}"
            else:
                error_description = result.get('description', 'Unknown error')
                return False, f"Telegram API error: {error_description}"
                
        except requests.RequestException as e:
            return False, f"Network error: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"
