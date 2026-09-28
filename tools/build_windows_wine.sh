#!/usr/bin/env bash
# Build the Windows release on Linux, through Wine and a Windows Python.
#
#   tools/build_windows_wine.sh 4.1.0
#
# PyInstaller cannot cross-compile, so build_release.py has to run under a
# Windows interpreter. The first run sets up a dedicated Wine prefix (the
# default ~/.wine is left alone); later runs reuse it.
set -euo pipefail

cd "$(dirname "$0")/.."

PY_VERSION=3.12.10
ICU_URL=https://github.com/unicode-org/icu/releases/download/release-77-1/icu4c-77_1-Win64-MSVC2022.zip

export WINEPREFIX="${ANIME_UPDATER_WINEPREFIX:-$HOME/.local/share/wineprefixes/anime-updater-build}"
export WINEARCH=win64
export WINEDEBUG=-all

CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/anime-updater-build"
SYS32="$WINEPREFIX/drive_c/windows/system32"
PY='C:\Python312\python.exe'

command -v wine >/dev/null || { echo "[ERROR] wine is not installed"; exit 1; }
mkdir -p "$CACHE"

if [ ! -f "$WINEPREFIX/drive_c/Python312/python.exe" ]; then
    echo "[INFO] Creating the Wine prefix at $WINEPREFIX"
    mkdir -p "$WINEPREFIX"
    wineboot -i
    curl -fL -o "$CACHE/python-$PY_VERSION-amd64.exe" \
        "https://www.python.org/ftp/python/$PY_VERSION/python-$PY_VERSION-amd64.exe"
    wine "$CACHE/python-$PY_VERSION-amd64.exe" /quiet InstallAllUsers=0 PrependPath=1 \
        Include_test=0 Include_tcltk=0 Include_doc=0 Include_launcher=0 \
        'TargetDir=C:\Python312'
fi

# Windows 10+ ships icuuc.dll in System32 and Qt6Core links against it; Wine
# does not, so a forwarder to an official ICU build stands in for it.
if [ ! -f "$SYS32/icuuc.dll" ]; then
    echo "[INFO] Installing ICU into the Wine prefix"
    curl -fL -o "$CACHE/icu.zip" "$ICU_URL"
    rm -rf "$CACHE/icu"
    unzip -q "$CACHE/icu.zip" -d "$CACHE/icu"
    cp "$CACHE"/icu/bin64/icuuc[0-9]*.dll "$CACHE"/icu/bin64/icudt[0-9]*.dll "$SYS32/"
    python3 tools/make_icu_forwarder.py "$SYS32/icuuc.dll" "$(ls "$SYS32"/icuuc[0-9]*.dll | head -n 1)"
fi

wine "$PY" -m pip install --disable-pip-version-check -q -U -r requirements.txt pyinstaller
wine "$PY" build_release.py "$@"
