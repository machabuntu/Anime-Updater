// Popup script for Anime Scrobbler extension

// Check API server status
async function checkAPIStatus() {
  const statusElement = document.getElementById('status');
  const statusText = document.getElementById('status-text');
  
  try {
    const response = await fetch('http://localhost:5000/api/status');
    if (response.ok) {
      const data = await response.json();
      statusElement.className = 'status connected';
      statusText.textContent = 'Connected to Shikimori Updater';
    } else {
      throw new Error('API not responding');
    }
  } catch (error) {
    statusElement.className = 'status error';
    statusText.textContent = 'Shikimori Updater not running';
  }
}

// Get current tab's anime info
async function getCurrentAnimeInfo() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    // Request anime info from content script
    const response = await chrome.tabs.sendMessage(tab.id, { type: 'GET_ANIME_INFO' });
    
    if (response && response.animeInfo) {
      const animeInfo = response.animeInfo;
      displayCurrentAnime(animeInfo);
      
      // Pre-fill manual form with detected info
      document.getElementById('manual-title').value = animeInfo.title || '';
      document.getElementById('manual-episode').value = animeInfo.episode || '';
    }
  } catch (error) {
    console.log('Could not get anime info from content script:', error);
    // Fallback to injection method
    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId: (await chrome.tabs.query({ active: true, currentWindow: true }))[0].id },
        function: extractAnimeInfoFromPage
      });
      
      if (results && results[0] && results[0].result) {
        const animeInfo = results[0].result;
        displayCurrentAnime(animeInfo);
        
        // Pre-fill manual form with detected info
        document.getElementById('manual-title').value = animeInfo.title || '';
        document.getElementById('manual-episode').value = animeInfo.episode || '';
      }
    } catch (fallbackError) {
      console.log('Fallback extraction also failed:', fallbackError);
    }
  }
}

// Function to inject into page for anime extraction
function extractAnimeInfoFromPage() {
  // This will use the same logic as content.js but executed on demand
  const hostname = window.location.hostname;
  
  // Site-specific selectors (simplified version)
  const selectors = {
    title: 'h1, .title, .anime-title, .video-title, .show-title, [class*="title"]',
    episode: '.episode, .ep, .episode-number, .ep-number, [class*="episode"]'
  };
  
  // Try to extract title
  let title = null;
  const titleSelectors = selectors.title.split(', ');
  for (const selector of titleSelectors) {
    const element = document.querySelector(selector);
    if (element && element.textContent.trim()) {
      title = element.textContent.trim();
      break;
    }
  }
  
  // Try to extract episode number
  let episode = null;
  const episodeSelectors = selectors.episode.split(', ');
  for (const selector of episodeSelectors) {
    const element = document.querySelector(selector);
    if (element && element.textContent.trim()) {
      const text = element.textContent.trim();
      const match = text.match(/\d+/);
      if (match) {
        episode = parseInt(match[0]);
        break;
      }
    }
  }
  
  // Try to extract from URL or page title if direct selectors failed
  if (!title || !episode) {
    const url = window.location.href;
    const pageTitle = document.title;
    
    // URL patterns
    const urlMatch = url.match(/\/anime\/([^/]+)\/(?:episode-)?(\d+)/i) ||
                    url.match(/\/watch\/(.+?)[-_](?:episode[-_])?(\d+)/i);
    
    if (urlMatch) {
      title = title || urlMatch[1].replace(/[-_]/g, ' ');
      episode = episode || parseInt(urlMatch[2]);
    }
    
    // Page title patterns
    const titleMatch = pageTitle.match(/^(.+?)\s*[-–]\s*Episode\s*(\d+)/i) ||
                      pageTitle.match(/^(.+?)\s+Episode\s*(\d+)/i);
    
    if (titleMatch) {
      title = title || titleMatch[1].trim();
      episode = episode || parseInt(titleMatch[2]);
    }
  }
  
  if (title && episode) {
    // Clean title
    title = title
      .replace(/\s*-\s*(Crunchyroll|Funimation|AnimeLab|9anime|Gogoanime).*$/i, '')
      .replace(/\s*\(\d{4}\)\s*$/, '')
      .replace(/\s*-\s*Episode\s*\d+.*$/i, '')
      .replace(/\s*(Sub|Dub|Subbed|Dubbed)\s*$/i, '')
      .trim();
    
    return {
      title: title,
      episode: episode,
      url: window.location.href,
      site: hostname
    };
  }
  
  return null;
}

// Display current anime info in popup
function displayCurrentAnime(animeInfo) {
  const currentAnimeDiv = document.getElementById('current-anime');
  const titleSpan = document.getElementById('anime-title');
  const episodeSpan = document.getElementById('anime-episode');
  
  if (animeInfo) {
    titleSpan.textContent = animeInfo.title;
    episodeSpan.textContent = animeInfo.episode;
    currentAnimeDiv.style.display = 'block';
  } else {
    currentAnimeDiv.style.display = 'none';
  }
}

// Manual scrobble function
async function manualScrobble() {
  const title = document.getElementById('manual-title').value.trim();
  const episode = parseInt(document.getElementById('manual-episode').value);
  const button = document.getElementById('scrobble-btn');
  
  if (!title || !episode) {
    alert('Please enter both anime title and episode number');
    return;
  }
  
  button.disabled = true;
  button.textContent = 'Scrobbling...';
  
  try {
    const response = await fetch('http://localhost:5000/api/scrobble', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        title: title,
        episode: episode,
        manual: true
      })
    });
    
    const result = await response.json();
    
    if (response.ok) {
      button.textContent = 'Scrobbled!';
      setTimeout(() => {
        button.textContent = 'Scrobble Episode';
        button.disabled = false;
      }, 2000);
    } else {
      throw new Error(result.message || 'Scrobbling failed');
    }
  } catch (error) {
    button.textContent = 'Error';
    alert('Scrobbling failed: ' + error.message);
    setTimeout(() => {
      button.textContent = 'Scrobble Episode';
      button.disabled = false;
    }, 2000);
  }
}

// Initialize popup
document.addEventListener('DOMContentLoaded', async () => {
  await checkAPIStatus();
  await getCurrentAnimeInfo();
});

// Make manualScrobble available globally
window.manualScrobble = manualScrobble;
