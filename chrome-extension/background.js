const API_BASE = 'http://localhost:5000/api';

chrome.runtime.onInstalled.addListener(() => {
  console.log('Anime Scrobbler extension installed.');
});

// Listener to receive messages from content script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === 'SCROBBLE_ANIME') {
    post('scrobble', request.animeData).then(sendResponse);
    return true; // the response is sent once the app has answered
  }
  if (request.type === 'CANCEL_SCROBBLE') {
    post('cancel_scrobble', request.animeData).then(sendResponse);
    return true;
  }
  return false;
});

// Sends one request to the desktop app and remembers the outcome, so the
// popup can show whether the last episode actually reached it.
async function post(endpoint, animeData) {
  const record = {
    action: endpoint,
    title: animeData && animeData.title,
    episode: animeData && animeData.episode,
    time: Date.now(),
  };

  try {
    const response = await fetch(`${API_BASE}/${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(animeData),
    });
    const data = await response.json().catch(() => ({}));
    record.ok = response.ok;
    record.message = data.message || `HTTP ${response.status}`;
  } catch (error) {
    record.ok = false;
    record.message = `Shikimori Updater is not reachable: ${error.message}`;
  }

  if (record.ok) {
    console.log(`Anime Scrobbler: ${endpoint} ok`, record);
  } else {
    console.error(`Anime Scrobbler: ${endpoint} failed`, record);
  }
  await chrome.storage.local.set({ lastRequest: record });
  return { status: record.ok ? 'success' : 'error', message: record.message };
}
