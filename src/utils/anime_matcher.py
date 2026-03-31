"""
Anime Name Matcher
Matches detected anime names with anime list data using fuzzy matching
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from difflib import SequenceMatcher

class AnimeMatcher:
    """Match anime names from various sources"""
    
    def __init__(self):
        self.similarity_threshold = 0.8  # Raised to require better matches
        self.exact_match_threshold = 0.95
    
    def find_best_match(self, detected_name: str, anime_list: List[Dict[str, Any]], 
                       episode_number: int = None) -> Optional[Tuple[Dict[str, Any], float]]:
        """
        Find the best matching anime from the user's list
        
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
            
            anime_name = anime.get('name', 'Unknown')
            # Get all possible names for this anime
            names = self._get_all_anime_names(anime)
            
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
    
    def search_and_match(self, detected_name: str, search_results: List[Dict[str, Any]], 
                        episode_number: int = None) -> Optional[Tuple[Dict[str, Any], float]]:
        """
        Find the best match from search results
        
        Args:
            detected_name: Name detected from video file
            search_results: Search results from the API
            episode_number: Episode number for validation
            
        Returns:
            Tuple of (best_match, similarity_score) or None
        """
        if not detected_name or not search_results:
            return None
        
        cleaned_detected = self._clean_name(detected_name)
        best_match = None
        best_score = 0.0
        
        for anime in search_results:
            # Get all possible names for this anime
            names = self._get_all_anime_names(anime)
            
            # Calculate similarity with each name
            for name in names:
                score = self._calculate_similarity(cleaned_detected, name)
                
                if score > best_score:
                    # Additional validation for episode number
                    if episode_number is not None:
                        total_episodes = anime.get('episodes', 0)
                        if total_episodes > 0 and episode_number > total_episodes:
                            # Skip if episode number exceeds total episodes
                            continue
                    
                    best_score = score
                    best_match = anime
        
        # Only return matches above threshold
        if best_score >= self.similarity_threshold:
            return (best_match, best_score)
        
        return None
    
    def _get_all_anime_names(self, anime: Dict[str, Any]) -> List[str]:
        """Get all possible names for an anime (English, Japanese, synonyms)"""
        names = []
        
        # Main name
        if anime.get('name'):
            names.append(self._clean_name(anime['name']))
        
        # Russian name
        if anime.get('russian'):
            names.append(self._clean_name(anime['russian']))
        
        # English names
        english = anime.get('english', [])
        if isinstance(english, list):
            names.extend([self._clean_name(name) for name in english])
        elif isinstance(english, str):
            names.append(self._clean_name(english))
        
        # Japanese names
        japanese = anime.get('japanese', [])
        if isinstance(japanese, list):
            names.extend([self._clean_name(name) for name in japanese])
        elif isinstance(japanese, str):
            names.append(self._clean_name(japanese))
        
        # Synonyms
        synonyms = anime.get('synonyms', [])
        if isinstance(synonyms, list):
            names.extend([self._clean_name(name) for name in synonyms])
        
        # Remove empty names and duplicates
        names = list(set([name for name in names if name]))
        
        return names
    
    def _clean_name(self, name: str) -> str:
        """Clean and normalize anime name for comparison"""
        if not name:
            return ""
        
        # Convert to lowercase
        name = name.lower()
        
        # Remove common prefixes/suffixes
        name = re.sub(r'^(the|a|an)\s+', '', name)
        name = re.sub(r'\s+(tv|ova|ona|movie|special)$', '', name)
        
        # Remove season indicators
        name = re.sub(r'\s+(season|s)\s*\d+', '', name)
        name = re.sub(r'\s+\d+(st|nd|rd|th)\s+season', '', name)
        
        # Remove year indicators
        name = re.sub(r'\s*\(\d{4}\)', '', name)
        name = re.sub(r'\s*\d{4}$', '', name)
        
        # Replace punctuation and special characters with spaces
        name = re.sub(r'[^\w\s]', ' ', name)
        
        # Replace multiple spaces with single space
        name = re.sub(r'\s+', ' ', name)
        
        return name.strip()
    
    def _calculate_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two anime names"""
        if not name1 or not name2:
            return 0.0
        
        # Exact match gets highest score
        if name1 == name2:
            return 1.0
        
        # Use SequenceMatcher for fuzzy matching
        similarity = SequenceMatcher(None, name1, name2).ratio()
        
        # Bonus for word order independence
        words1 = set(name1.split())
        words2 = set(name2.split())
        
        if words1 and words2:
            word_overlap = len(words1.intersection(words2)) / max(len(words1), len(words2))
            similarity = max(similarity, word_overlap * 0.8)  # Weight word overlap slightly less
        
        # Bonus for substring matches
        if name1 in name2 or name2 in name1:
            similarity = max(similarity, 0.8)
        
        return min(similarity, 1.0)  # Cap at 1.0
    
    def suggest_corrections(self, detected_name: str, anime_list: List[Dict[str, Any]], 
                          max_suggestions: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        """
        Suggest possible corrections for unmatched anime names
        
        Args:
            detected_name: Name that couldn't be matched
            anime_list: User's anime list
            max_suggestions: Maximum number of suggestions to return
            
        Returns:
            List of (anime, similarity_score) tuples sorted by score
        """
        if not detected_name or not anime_list:
            return []
        
        cleaned_detected = self._clean_name(detected_name)
        suggestions = []
        
        for anime_entry in anime_list:
            anime = anime_entry.get('anime', {})
            if not anime:
                continue
            
            names = self._get_all_anime_names(anime)
            best_score = 0.0
            
            for name in names:
                score = self._calculate_similarity(cleaned_detected, name)
                best_score = max(best_score, score)
            
            if best_score > 0.3:  # Lower threshold for suggestions
                suggestions.append((anime_entry, best_score))
        
        # Sort by score and return top suggestions
        suggestions.sort(key=lambda x: x[1], reverse=True)
        return suggestions[:max_suggestions]
