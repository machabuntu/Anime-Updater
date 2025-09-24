chrome.runtime.onInstalled.addListener(() => {
  console.log('Anime Scrobbler extension installed.');
});

// Listener to receive messages from content script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === 'SCROBBLE_ANIME') {
    scrobbleAnime(request.animeData);
    sendResponse({ status: 'success' });
  } else if (request.type === 'CANCEL_SCROBBLE') {
    cancelScrobble(request.animeData);
    sendResponse({ status: 'cancelled' });
  }
});

function scrobbleAnime(animeData) {
  fetch('http://localhost:5000/api/scrobble', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(animeData),
  })
    .then((response) => response.json())
    .then((data) => {
      console.log('Scrobbled successfully:', data);
    })
    .catch((error) => {
      console.error('Error scrobbling anime:', error);
    });
}

function cancelScrobble(animeData) {
  fetch('http://localhost:5000/api/cancel_scrobble', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(animeData),
  })
    .then((response) => response.json())
    .then((data) => {
      console.log('Scrobble cancelled successfully:', data);
    })
    .catch((error) => {
      console.error('Error cancelling scrobble:', error);
    });
}

