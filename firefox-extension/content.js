// Content script to scrape anime data from streaming websites

// Site-specific selectors for popular anime streaming sites
const SITE_SELECTORS = {
  // qanime.ru
  'qanime.ru': {
    title: 'meta[property="og:title"], title, h1, .video-title, .anime-title',
    episode: 'meta[property="ya:ovs:episod"], .episode-number, [class*="episode"]'
  },
  // qfilms.ru
  'qfilms.ru': {
    title: 'meta[property="og:title"], title, h1, .video-title, .anime-title',
    episode: 'meta[property="ya:ovs:episod"], .episode-number, [class*="episode"]'
  },
  // Generic selectors for other sites
  'generic': {
    title: 'h1, .title, .anime-title, .video-title, .show-title, [class*="title"]',
    episode: '.episode, .ep, .episode-number, .ep-number, [class*="episode"]'
  }
};

// Extract English title from qanime.ru/qfilms.ru title format
function extractEnglishTitleFromQanime(fullTitle) {
  console.log('Anime Scrobbler: Processing qanime.ru/qfilms.ru title:', fullTitle);
  
  // Pattern: "Русское название / English Title - season episode"
  // Example: "Апокалипсис: Отель / Apocalypse Hotel - 1 сезон, 4 серия"
  
  const patterns = [
    // Pattern with Russian / English format
    /^[^/]+\/\s*([^-]+?)\s*-\s*\d+\s*сезон/i,
    // Pattern with just English title before season info
    /^([^-]+?)\s*-\s*\d+\s*сезон/i,
    // Fallback: everything before the first dash
    /^([^-]+)/
  ];
  
  for (const pattern of patterns) {
    const match = fullTitle.match(pattern);
    if (match) {
      let englishTitle = match[1].trim();
      
      // Clean up common prefixes/suffixes
      englishTitle = englishTitle.replace(/^[^/]+\/\s*/, ''); // Remove Russian part
      englishTitle = englishTitle.replace(/\s*субтитры.*$/i, ''); // Remove subtitle info
      englishTitle = englishTitle.replace(/\s*смотреть.*$/i, ''); // Remove watch info
      
      if (englishTitle && englishTitle.length > 2) {
        console.log('Anime Scrobbler: Extracted English title:', englishTitle);
        return englishTitle.trim();
      }
    }
  }
  
  // If no pattern matched, return the original title
  console.log('Anime Scrobbler: No English title pattern matched, using original');
  return fullTitle;
}

// animego.me keeps every episode on one page. The English title is the
// schema.org alternateName, and the episode being played is the player bar
// item carrying the "active" class: its data-episode-number is the number
// the site's own player syncs when the user picks a series or the embedded
// player advances. The bar itself arrives later, from /player/<id>.
function extractAnimego() {
  const title = animegoTitle();
  const episode = animegoEpisode();
  if (!title || !episode) {
    return null;
  }
  return {
    title: title,
    episode: episode,
    url: window.location.href,
    site: window.location.hostname,
  };
}

// Shikimori and MAL search by the romaji or English name, so the Russian
// name is only the last resort.
function animegoTitle() {
  const series = animegoSeriesNode();
  const alternate = series && animegoText(series.alternateName);
  if (alternate) {
    return alternate;
  }

  const synonyms = document.querySelectorAll('.entity__title-synonyms li');
  for (const item of synonyms) {
    const text = item.textContent.trim();
    if (/[a-z]/i.test(text) && !/[а-яё]/i.test(text)) {
      return text;
    }
  }

  const name = series && animegoText(series.name);
  if (name) {
    return name;
  }
  const heading = document.querySelector('.entity__title h1, h1');
  return heading ? heading.textContent.trim() : null;
}

function animegoSeriesNode() {
  const scripts = document.querySelectorAll('script[type="application/ld+json"]');
  for (const script of scripts) {
    let data;
    try {
      data = JSON.parse(script.textContent);
    } catch (e) {
      continue;
    }
    const node = animegoFindSeries(data);
    if (node) {
      return node;
    }
  }
  return null;
}

function animegoFindSeries(node) {
  if (!node || typeof node !== 'object') {
    return null;
  }
  if (Array.isArray(node)) {
    for (const item of node) {
      const found = animegoFindSeries(item);
      if (found) {
        return found;
      }
    }
    return null;
  }
  if (Array.isArray(node['@graph'])) {
    const found = animegoFindSeries(node['@graph']);
    if (found) {
      return found;
    }
  }

  const type = node['@type'];
  const types = Array.isArray(type) ? type : [type];
  if (types.includes('TVSeries') || types.includes('Movie') || types.includes('TVEpisode')) {
    return node;
  }
  return null;
}

function animegoText(value) {
  if (Array.isArray(value)) {
    value = value.find(item => typeof item === 'string');
  }
  return typeof value === 'string' ? value.trim() : '';
}

function animegoEpisode() {
  // The site's episode controller marks the playing item with "active" and
  // stores the visible number in data-episode-number. data-episode itself is
  // an internal id, not the series number.
  const active = document.querySelector('[data-anime-player-episodes-target~="episode"].active')
    || document.querySelector('.player-video-bar__item.active');
  const episode = parseInt(active && active.dataset.episodeNumber, 10);
  if (!Number.isInteger(episode) || episode < 1) {
    return null;
  }
  return episode;
}

function isAnimego() {
  return /(^|\.)animego\.[a-z]+$/i.test(window.location.hostname);
}

// The episode list is injected after load and the active item changes without
// a navigation, so the bar has to be watched rather than read once.
function watchAnimegoPlayer() {
  const observer = new MutationObserver(() => {
    const animeInfo = extractAnimego();
    if (animeInfo) {
      sendAnimeInfoUpdated(animeInfo);
    }
  });
  observer.observe(document.documentElement, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ['class'],
  });
}

// Extract anime information based on current site
function extractAnimeInfo() {
  const hostname = window.location.hostname;

  if (isAnimego()) {
    return extractAnimego();
  }

  let selectors = null;
  
  // Add debugging for qanime.ru and qfilms.ru
  if (hostname.includes('qanime.ru') || hostname.includes('qfilms.ru')) {
    console.log('Anime Scrobbler: Debugging qanime.ru/qfilms.ru page');
    console.log('URL:', window.location.href);
    console.log('Page title:', document.title);
    
    // Log all potential title elements
    const potentialTitles = document.querySelectorAll('h1, h2, h3, .title, [class*="title"], meta[property="og:title"]');
    console.log('Found potential title elements:', potentialTitles.length);
    potentialTitles.forEach((el, i) => {
      const text = el.tagName === 'META' ? el.getAttribute('content') : el.textContent;
      console.log(`Title element ${i}:`, el.tagName, el.className, text?.trim());
    });
    
    // Log all potential episode elements
    const potentialEpisodes = document.querySelectorAll('[class*="episode"], [class*="seriya"], .breadcrumb, nav');
    console.log('Found potential episode elements:', potentialEpisodes.length);
    potentialEpisodes.forEach((el, i) => {
      console.log(`Episode element ${i}:`, el.tagName, el.className, el.textContent?.trim());
    });
    
    // Log page structure for debugging
    console.log('Body classes:', document.body.className);
    console.log('Main content areas:');
    const mainAreas = document.querySelectorAll('main, .main, .content, .container, #content, #main');
    mainAreas.forEach((area, i) => {
      console.log(`Main area ${i}:`, area.tagName, area.className, area.id);
    });
  }
  
  // Find matching site selectors
  for (const [site, siteSelectors] of Object.entries(SITE_SELECTORS)) {
    if (hostname.includes(site)) {
      selectors = siteSelectors;
      console.log(`Anime Scrobbler: Using selectors for ${site}:`, selectors);
      break;
    }
  }
  
  // Fall back to generic selectors
  if (!selectors) {
    selectors = SITE_SELECTORS.generic;
    console.log('Anime Scrobbler: Using generic selectors:', selectors);
  }
  
  // Try to extract title
  let title = null;
  let episodeFromTitle = null;
  const titleSelectors = selectors.title.split(', ');
  for (const selector of titleSelectors) {
    const element = document.querySelector(selector);
    if (element) {
      let text = '';
      // Handle meta tags differently
      if (selector.includes('meta')) {
        text = element.getAttribute('content') || '';
      } else {
        text = element.textContent || element.innerText || '';
      }
      text = text.trim();
      if (text) {
        let fromTitle = text.match(/(\d+)\sсерия/);
        if(fromTitle) {
          let epNum = fromTitle[1];
          if(epNum) {
            episodeFromTitle = parseInt(epNum);
          }
        }
        // Special handling for qanime.ru and qfilms.ru titles
        if (hostname.includes('qanime.ru') || hostname.includes('qfilms.ru')) {
          title = extractEnglishTitleFromQanime(text);
        } else {
          title = text;
        }
        console.log(`Anime Scrobbler: Found title using selector "${selector}": ${text}`);
        if (hostname.includes('qanime.ru') || hostname.includes('qfilms.ru')) {
          console.log(`Anime Scrobbler: Extracted English title: ${title}`);
        }
        break;
      }
    }
  }
  
  // Try to extract episode number
  console.log(`Anime Scrobbler: check1 "${episodeFromTitle}" in "${title}"`);
  let episode = null;
  const episodeSelectors = selectors.episode.split(', ');
  for (const selector of episodeSelectors) {
    console.log(`Anime Scrobbler: check "${selector}"`);
    const element = document.querySelector(selector);
    if (element) {
      let text = '';
      // Handle meta tags differently
      if (selector.includes('meta')) {
        text = element.getAttribute('content') || '';
      } else {
        text = element.textContent || element.innerText || '';
      }
      text = text.trim();
      if (text) {
        // For meta tags, the content is already the episode number
        if (selector.includes('meta')) {
          episode = parseInt(text);
        } else {
          // Extract number from text (e.g., "Episode 5" -> 5)
          const match = text.match(/\d+/);
          if (match) {
            episode = parseInt(match[0]);
          }
        }
        if (episode) {
          if(episodeFromTitle && episode != episodeFromTitle) {
            episode = episodeFromTitle;
          }
          console.log(`Anime Scrobbler: Found111 episode using selector "${selector}": ${episode}`);
          break;
        }
      }
    }
  }
  
  // Try alternative methods if direct selectors failed
  // Debug what we found so far
  console.log('Anime Scrobbler: Initial extraction results:', { title, episode });
  
  if (!title || !episode) {
    console.log('Anime Scrobbler: Trying alternative extraction methods...');
    const alternativeData = extractFromURL() || extractFromPageTitle();
    if (alternativeData) {
      console.log('Anime Scrobbler: Alternative extraction found:', alternativeData);
      title = title || alternativeData.title;
      episode = episode || alternativeData.episode;
    } else {
      console.log('Anime Scrobbler: No alternative extraction data found');
    }
  }
  
  console.log('Anime Scrobbler: Final extraction results:', { title, episode });
  
  if (!title || !episode) {
    console.log('Anime Scrobbler: Could not extract anime info from this page');
    return null;
  }
  
  return {
    title: cleanTitle(title),
    episode: episode,
    url: window.location.href,
    site: hostname
  };
}

// Extract anime info from URL patterns
function extractFromURL() {
  const url = window.location.href;
  const pathname = window.location.pathname;
  
  console.log('Anime Scrobbler: Trying URL extraction from:', url);
  
  // Common URL patterns for episode pages
  const urlPatterns = [
    // Pattern: /anime/title-name/episode-number
    { pattern: /\/anime\/([^/]+)\/(?:episode-)?(\d+)/i, name: 'anime-episode' },
    // Pattern: /watch/title-name-episode-number
    { pattern: /\/watch\/(.+?)[-_](?:episode[-_])?(\d+)/i, name: 'watch-episode' },
    // Pattern: /series/title/episode/number
    { pattern: /\/series\/([^/]+)\/episode\/(\d+)/i, name: 'series-episode' },
    // Pattern: /video/id-title.season.episode (for qanime.ru and qfilms.ru)
    { pattern: /\/video\/\d+-([^.]+)\.\d+\.sezon\.(\d+)\.seriya/i, name: 'qanime-sezon-seriya' },
    // Pattern: /video/id-title-episode
    { pattern: /\/video\/\d+-(.+?)[-.](?:seriya|episode)[-.]?(\d+)/i, name: 'video-episode' },
    // More flexible qanime.ru/qfilms.ru patterns
    { pattern: /\/video\/\d+-(.+?)\.(\d+)\./i, name: 'qanime-flexible' },
    // Extract from pathname segments
    { pattern: /\/video\/\d+-(.+?)[-.](.+?)[-.](.+)/i, name: 'qfilms-segments' }
  ];
  
  for (const { pattern, name } of urlPatterns) {
    const match = url.match(pattern);
    if (match) {
      console.log(`Anime Scrobbler: URL pattern "${name}" matched:`, match);
      
      let title = match[1];
      let episode = null;
      
      // Handle different match patterns
      if (name === 'qfilms-segments') {
        // For /video/id-title-season-episode format
        title = match[1];
        // Look for episode number in any of the segments
        for (let i = 2; i < match.length; i++) {
          const num = parseInt(match[i]);
          if (!isNaN(num) && num > 0 && num < 1000) {
            episode = num;
            break;
          }
        }
      } else {
        episode = parseInt(match[2]);
      }
      
      if (title && episode) {
        const result = {
          title: title.replace(/[-_.]/g, ' ').trim(),
          episode: episode
        };
        console.log('Anime Scrobbler: URL extraction result:', result);
        return result;
      }
    }
  }
  
  console.log('Anime Scrobbler: No URL pattern matched');
  return null;
}

// Extract anime info from page title
function extractFromPageTitle() {
  const title = document.title;
  
  // Common title patterns
  const titlePatterns = [
    // "Anime Name - Episode 5"
    /^(.+?)\s*[-–]\s*Episode\s*(\d+)/i,
    // "Anime Name Episode 5"
    /^(.+?)\s+Episode\s*(\d+)/i,
    // "Anime Name Ep 5"
    /^(.+?)\s+Ep\.?\s*(\d+)/i
  ];
  
  for (const pattern of titlePatterns) {
    const match = title.match(pattern);
    if (match) {
      return {
        title: match[1].trim(),
        episode: parseInt(match[2])
      };
    }
  }
  
  return null;
}

// Clean anime title (remove common streaming site suffixes)
function cleanTitle(title) {
  return title
    .replace(/\s*-\s*(Crunchyroll|Funimation|AnimeLab|9anime|Gogoanime|qanime|qfilms).*$/i, '')
    .replace(/\s*\(\d{4}\)\s*$/, '') // Remove year
    .replace(/\s*-\s*Episode\s*\d+.*$/i, '') // Remove episode info
    .replace(/\s*-\s*\d+\s*seriya.*$/i, '') // Remove Russian episode info
    .replace(/\s*(Sub|Dub|Subbed|Dubbed|Rus|Russian)\s*$/i, '') // Remove sub/dub info
    .replace(/\s*\d+\s*sezon.*$/i, '') // Remove season info
    .trim();
}

// Communicate with background script
function sendAnimeInfo(animeInfo) {
  if (!animeInfo) return;
  
  console.log('Anime Scrobbler: Sending anime info:', animeInfo);
  
  chrome.runtime.sendMessage({
    type: 'SCROBBLE_ANIME',
    animeData: animeInfo,
  }, (response) => {
    console.log('Anime Scrobbler: Response from background:', response);
  });
}

// Check if the page looks like an anime episode page
function isAnimeEpisodePage() {
  const url = window.location.href.toLowerCase();
  const keywords = ['anime', 'episode', 'watch', 'series', 'ep', 'video', 'seriya', 'sezon'];
  return keywords.some(keyword => url.includes(keyword));
}

// Main execution
(function() {
  // Only run on pages that might be anime episodes
  if (!isAnimeEpisodePage()) {
    return;
  }
  console.log('Anime Scrobbler: content script active on', window.location.href);

  // Wait for page to load completely
  function tryExtraction() {
    const animeInfo = extractAnimeInfo();
    if (animeInfo) {
        sendAnimeInfoUpdated(animeInfo);
    } else {
      console.log('Anime Scrobbler: No anime info found on this page');
    }
  }
  
  // Try extraction after page load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', tryExtraction);
  } else {
    // Page already loaded
    setTimeout(tryExtraction, 1000); // Give it a second for dynamic content
  }

  if (isAnimego()) {
    watchAnimegoPlayer();
  }

  // Also try when URL changes (for single-page applications). The hash is
  // ignored: animego uses #player as an anchor, and that is not a new episode.
  let currentPage = pageKey();
  setInterval(() => {
    if (pageKey() === currentPage) {
      return;
    }
    currentPage = pageKey();
    cancelCurrentScrobble();
    if (isAnimeEpisodePage()) {
      setTimeout(tryExtraction, 2000); // Wait longer for SPA route changes
    }
  }, 1000);
})();

function pageKey() {
  return window.location.origin + window.location.pathname + window.location.search;
}

// Listen for messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === 'GET_ANIME_INFO') {
    const animeInfo = extractAnimeInfo();
    sendResponse({ animeInfo: animeInfo });
  }
  return true; // Keep the message channel open for async response
});

// Send cancel request when page is about to be unloaded
let currentAnimeInfo = null;

function cancelCurrentScrobble() {
  if (!currentAnimeInfo) {
    return;
  }
  console.log('Anime Scrobbler: Cancelling scrobble for:', currentAnimeInfo.title);
  const animeData = {
    title: currentAnimeInfo.title,
    episode: currentAnimeInfo.episode,
  };
  currentAnimeInfo = null;
  chrome.runtime.sendMessage({
    type: 'CANCEL_SCROBBLE',
    animeData: animeData,
  });
}

window.addEventListener('beforeunload', cancelCurrentScrobble);

// Update the sendAnimeInfo function to track current anime
function sendAnimeInfoUpdated(animeInfo) {
  if (!animeInfo) return;

  // The player bar is re-rendered often. Sending the same episode again would
  // restart the watch timer, and leaving the previous one running would
  // scrobble an episode the user has already switched away from.
  if (currentAnimeInfo
      && currentAnimeInfo.title === animeInfo.title
      && currentAnimeInfo.episode === animeInfo.episode) {
    return;
  }
  cancelCurrentScrobble();
  currentAnimeInfo = animeInfo;
  console.log('Anime Scrobbler: Sending anime info:', animeInfo);
  
  chrome.runtime.sendMessage({
    type: 'SCROBBLE_ANIME',
    animeData: animeInfo,
  }, (response) => {
    console.log('Anime Scrobbler: Response from background:', response);
  });
}

