# Chrome Extension Debugging Instructions

## To test the qanime.ru and qfilms.ru extraction:

### Method 1: Test with local files
1. Open Chrome and go to `chrome://extensions/`
2. Make sure "Developer mode" is enabled
3. Click "Load unpacked" and select the `chrome-extension` folder
4. Open the `test-qanime.html` or `test-qfilms.html` file in Chrome
5. Open Developer Tools (F12) and go to the Console tab
6. You should see debugging output showing what the extension found

### Method 2: Test on actual sites
1. Make sure the extension is loaded (see Method 1)
2. Go to any qanime.ru or qfilms.ru anime episode page
3. Open Developer Tools (F12) and go to the Console tab
4. Look for console messages starting with "Anime Scrobbler:"
5. The extension will log:
   - What selectors it's using
   - What elements it found on the page
   - URL pattern matching attempts
   - Final extraction results

### What to look for in console:
- `Anime Scrobbler: Debugging qanime.ru/qfilms.ru page` - Shows the extension is running
- `Found potential title elements: X` - Shows how many title elements were found
- `Found potential episode elements: X` - Shows how many episode elements were found
- `URL pattern "pattern-name" matched:` - Shows if URL extraction worked
- `Final extraction results:` - Shows the final title and episode found (or null)

### If extraction fails:
1. Copy the console output
2. Look at what elements were found
3. We can add specific selectors based on the actual page structure

### To manually test extraction:
In the browser console on a qanime.ru or qfilms.ru page, you can run:
```javascript
// Test title extraction
document.querySelectorAll('h1, h2, h3, .title, [class*="title"], meta[property="og:title"]')

// Test episode extraction  
document.querySelectorAll('[class*="episode"], [class*="seriya"], .breadcrumb, nav')

// Test URL extraction
console.log(window.location.href);

// Test the main extraction function
extractAnimeInfo();
```
