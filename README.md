# Anime Updater

Desktop application that keeps your **Shikimori** or **MyAnimeList** anime and
manga lists up to date. It watches your media player, matches the file that is
playing against your list, and bumps the episode count on its own.

![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-green)
![Qt](https://img.shields.io/badge/GUI-PySide6-41cd52)
![License](https://img.shields.io/badge/license-MIT-blue)

## Features

### List management

- Anime and manga in separate tabs, each split by status with live counters
- Filters for name, year, type and score; click any column header to sort
- Quick controls in the toolbar edit the selected title without opening a dialog
- Double-click a row for the full edit dialog (episodes, status, score, rewatches)
- Search and add new titles, with entries already on your list dimmed out
- Seasonal browser for finding what is airing this season

### Automatic scrobbling

- Detects PotPlayer on Windows and mpv or Celluloid on Linux
- Parses the anime name and episode number out of the file name, then matches it
  against your list using synonyms and fuzzy comparison
- Updates only when the detected episode is exactly one past your current
  progress, so a random file cannot corrupt your list
- Moves a title from *Plan to Watch* to *Watching* on the first episode, and
  marks it *Completed* on the last one
- A companion browser extension can report progress from streaming sites through
  the local API

### Notifications

- Desktop notifications for new episodes and for series that finish airing
- Optional Telegram messages, with separate switches for progress, completions,
  drops and rewatches

### Interface

- Light and dark themes, plus a *system* mode that follows the desktop
- System tray icon with minimise-to-tray and close-to-tray
- Local cache means the window opens with your list already populated

## Requirements

- Windows 10/11 or Linux
- Python 3.10 or newer, only when running from source
- A Shikimori or MyAnimeList account

On Linux the tray icon needs a desktop that implements the StatusNotifierItem
specification. KDE and most others do; GNOME needs the AppIndicator extension.

## Installing

### Pre-built binary

Download the latest release, then:

**Windows** — run `Anime Updater.exe`.

**Linux** — make the file executable and run it. To get a menu entry and a
proper task bar icon, install the desktop file that ships next to it:

```bash
chmod +x anime-updater
mkdir -p ~/.local/bin ~/.local/share/applications ~/.local/share/icons
cp anime-updater ~/.local/bin/
cp icon.png ~/.local/share/icons/anime-updater.png
cp anime-updater.desktop ~/.local/share/applications/
```

### From source

```bash
git clone https://github.com/machabuntu/Shikimori-Updater.git
cd Shikimori-Updater

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

python main.py
```

### Building a binary yourself

```bash
pip install pyinstaller

python build.py          # Windows -> dist/Anime Updater.exe
python build_linux.py    # Linux   -> dist/anime-updater
```

Both scripts read the spec files tracked in the repository. The result is a
single file of roughly 75 MB; most of that is Qt.

A GitHub release that the in-app updater can install is a zip named
`Anime_Updater_{version}_Windows.zip` or `Anime_Updater_{version}_Linux.zip`,
with the binary above sitting at the root of the archive. The release scripts
build that zip (and bump `src/utils/version.py`):

```bash
python build_release.py 4.1.0         # Windows
python build_release_linux.py 4.1.0   # Linux
```

PyInstaller cannot cross-compile: the Windows exe has to come from a Windows
Python. Without a Windows machine, build it under Wine:

```bash
tools/build_windows_wine.sh 4.1.0
```

The first run creates a separate Wine prefix in
`~/.local/share/wineprefixes/anime-updater-build` with Python and the
requirements; later runs reuse it. Wine lacks the `icuuc.dll` that Windows 10+
ships and Qt links against, so the script installs a stand-in that forwards to
an official ICU build. It only lives in that prefix and is not bundled.

The self-updater is a second, separate binary, built so that replacing the main
executable does not fight with PyInstaller's temporary extraction directory.
The release scripts build it too; to build it alone:

```bash
python build_updater.py        # Windows
python build_updater_linux.py  # Linux
```

## Setup

### Shikimori

Shikimori credentials are built in, so signing in is just **Menu → Sign in**,
which opens your browser and captures the redirect automatically.

To use your own API application instead, register one at
[Shikimori OAuth Applications](https://shikimori.one/oauth/applications) with
the redirect URI `http://localhost:8080/callback` and the `user_rates` scope,
then enter the client ID and secret in **Menu → Options → Main**.

### MyAnimeList

MyAnimeList has no shared credentials, so you need your own:

1. Open [MyAnimeList API settings](https://myanimelist.net/apiconfig) and create
   a client
2. Set the redirect URI to `http://localhost:8080/callback`
3. Copy the client ID into **Menu → Options → Main**, switch *Active service* to
   MyAnimeList, and leave the secret empty for a public client
4. Sign in from the menu

### Telegram (optional)

Create a bot with [@BotFather](https://t.me/botfather), then put the bot token
and your chat ID into **Menu → Options → Notifications** and pick the events you
want to hear about.

## Usage

**Scrobbling.** Turn it on with **Menu → Start Scrobbling**, then play an
episode. After a minute of playback the episode is committed. Only an episode
exactly one ahead of your current progress counts, so skipping around in a
series does not touch your list.

**Adding titles.** The *Search & Add* tab searches the service directly; pick a
status and add. The *Seasonal Anime* tab lists a whole season at once and adds
straight to *Plan to Watch*.

**Editing.** Select a row and use the toolbar controls, or double-click it for
the full dialog. Right-click gives status changes, comments, opening the page in
a browser, and removal.

## Configuration

| What | Where |
| --- | --- |
| Settings | `~/.shikimori_updater/config.json` |
| Cache and logs | `%LOCALAPPDATA%\ShikimoriUpdater` (Windows), `~/.local/share/ShikimoriUpdater` (Linux) |

Most settings have a control in the options dialog. The two that do not are the
player list and the scrobble delay:

```json
{
  "monitoring": {
    "min_watch_time": 60,
    "supported_players": [
      "PotPlayerMini64.exe", "PotPlayer64.exe", "mpv", "celluloid"
    ]
  },
  "ui": {
    "theme": "system",
    "minimize_to_tray": false,
    "close_to_tray": false
  }
}
```

Adding a player is a matter of appending its process name to
`supported_players`; anything that puts the file name in its window title works.

## Project layout

```
main.py                      entry point and argument parsing
build.py, build_linux.py     PyInstaller drivers
*.spec                       build configuration, tracked on purpose

src/api/                     Shikimori and MyAnimeList clients
src/core/                    config, cache, and the framework-agnostic services
    clients.py                 picks the client for the active service
    library.py                 loading, caching and matching list entries
    scrobble.py                deciding whether an episode counts
    updates.py                 release checks
    autostart.py               launch on login
src/ui/                      the Qt interface
    theme/                     colour tokens, the QSS template, ThemeManager
    views/                     the four list tabs
    dialogs/                   options, sign-in, edit, comment, update, logs
    controller.py              bridges the interface to the services
    workers.py                 background work on a QThreadPool
src/utils/                   player monitoring, matching, Telegram, logging
tests/                       unit tests for the core services
tools/check_imports.py       imports every module to catch broken imports
```

## Development

```bash
pip install -r requirements.txt

python -m unittest discover -s tests    # unit tests
python tools/check_imports.py           # every module imports cleanly
python main.py --self-test              # build the whole interface, then exit
python main.py --gallery                # every styled widget on one screen
```

`--gallery` is the fastest way to check a stylesheet change: it renders every
widget the application uses, and `SHIKI_THEME=dark` switches which palette it
starts in.

Colours live in `src/ui/theme/tokens.py` and are substituted into
`src/ui/theme/app.qss` wherever a `@token` appears, so a palette change is one
edit in one file.

## Troubleshooting

**Sign-in fails.** Check that the redirect URI on the service side is exactly
`http://localhost:8080/callback`, and that nothing else is holding port 8080.

**Scrobbling does nothing.** Confirm the player's process name is in
`supported_players`, that the file name follows a recognisable pattern such as
`[Group] Anime Name - 05 [1080p]`, and that the title is already on your list at
episode 4. **Menu → View Logs** shows what was parsed and what it matched.

**No tray icon on Linux.** On GNOME, install the AppIndicator extension. The
application still runs without a tray; it just cannot minimise into one.

**The list looks stale.** **Menu → Refresh List** forces a reload from the API
instead of the cache.

## Licence

MIT, see [LICENSE](LICENSE). The published binaries link Qt dynamically through
PySide6 under the LGPL.

## Acknowledgements

- [Shikimori](https://shikimori.one) and [MyAnimeList](https://myanimelist.net)
  for their APIs
- [Qt](https://www.qt.io) and PySide6 for the interface toolkit
