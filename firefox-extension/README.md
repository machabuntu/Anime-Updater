# Anime Scrobbler Chrome Extension

This Chrome extension automatically scrobbles anime episodes from streaming websites and updates your progress in the Shikimori Updater application.

## Features

- **Automatic Detection**: Automatically detects anime titles and episode numbers from popular streaming sites
- **Manual Scrobbling**: Manual scrobble option for cases where automatic detection fails
- **Real-time Status**: Shows connection status to your Shikimori Updater app
- **Wide Compatibility**: Works with Crunchyroll, Funimation, 9anime, Gogoanime, and many other sites

## Installation

1. Make sure your Shikimori Updater application is running on your computer
2. Open Chrome and go to `chrome://extensions/`
3. Enable "Developer mode" in the top right corner
4. Click "Load unpacked" and select the `chrome-extension` folder
5. The extension should appear in your extensions list

## Usage

### Automatic Scrobbling
1. Navigate to any anime episode page on a supported streaming site
2. The extension will automatically detect the anime title and episode number
3. It will send this information to your running Shikimori Updater app
4. Your progress will be updated on Shikimori automatically

### Manual Scrobbling
1. Click on the extension icon in your browser toolbar
2. Enter the anime title and episode number manually
3. Click "Scrobble Episode"
4. Your progress will be updated

### Status Checking
- Click the extension icon to see if it's connected to your Shikimori Updater app
- Green status = Connected and ready
- Red status = Shikimori Updater not running or not reachable

## Supported Sites

The extension works best with these popular anime streaming sites:

- **Crunchyroll** (crunchyroll.com)
- **Funimation** (funimation.com) 
- **9anime** (9anime.*)
- **Gogoanime** (gogoanime.*)
- **AnimeLab** (animelab.com)
- **Generic sites** with standard anime page structures

## How It Works

1. **Content Script**: Runs on anime episode pages to extract title and episode information
2. **Background Script**: Handles communication between the web page and your local app
3. **API Integration**: Sends scrobble data to your Shikimori Updater app via HTTP API (localhost:5000)
4. **Shikimori Update**: Your app processes the data and updates your anime list on Shikimori

## Troubleshooting

### Extension not working?
- Make sure Shikimori Updater is running on your computer
- Check that the app is listening on port 5000 (default)
- Try refreshing the anime episode page
- Check browser console for error messages

### Anime not detected?
- Use the manual scrobble option in the extension popup
- The extension works best on dedicated episode pages
- Some sites with heavy JavaScript may need page refresh

### Connection issues?
- Ensure Windows Firewall isn't blocking the connection
- Make sure you're logged into Shikimori in your Updater app
- Try restarting both the browser and the Updater app

## Development

To modify or enhance the extension:

1. Edit the relevant files:
   - `manifest.json` - Extension configuration
   - `content.js` - Page scraping logic
   - `background.js` - Extension background processes
   - `popup.html/js` - Extension popup interface

2. Reload the extension in `chrome://extensions/`

3. Test on various anime streaming sites

## API Endpoints

The extension communicates with these local API endpoints:

- `GET http://localhost:5000/api/status` - Check if app is running
- `POST http://localhost:5000/api/scrobble` - Send anime scrobble data

## Privacy

This extension:
- Only runs on anime streaming sites
- Sends data to your local Shikimori Updater app only
- Does not collect or send data to external servers
- Does not track your browsing habits

## License

This extension is part of the Shikimori Updater project and follows the same license terms.
