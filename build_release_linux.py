#!/usr/bin/env python3
"""
Linux release builder for Anime Updater.

Usage:
    python build_release_linux.py          # prompts for version
    python build_release_linux.py 4.1.0   # non-interactive

Steps:
  1. Bump __version__ and BUILD_DATE in src/utils/version.py
  2. Build the Linux binary via build_linux.py
  3. Package dist/anime-updater + docs into
     releases/v{version}/  and zip as
     releases/Anime_Updater_{version}_Linux.zip
"""

import os
import sys
import re
import subprocess
import shutil
import json
import datetime
from pathlib import Path


VERSION_FILE = "src/utils/version.py"
BINARY_NAME = "anime-updater"          # output of build_linux.py
RELEASES_DIR = "releases"


def update_version(version_file: str, new_version: str) -> bool:
    """Patch __version__ and BUILD_DATE inside version.py."""
    try:
        with open(version_file, "r") as fh:
            content = fh.read()

        content = re.sub(r'__version__ = "[^"]*"',
                         f'__version__ = "{new_version}"', content)
        today = datetime.date.today().strftime("%Y-%m-%d")
        content = re.sub(r'BUILD_DATE = "[^"]*"',
                         f'BUILD_DATE = "{today}"', content)

        with open(version_file, "w") as fh:
            fh.write(content)

        print(f"[OK] Version set to {new_version}, build date to {today}")
        return True
    except Exception as exc:
        print(f"[ERROR] Could not update version file: {exc}")
        return False


def build_executable() -> bool:
    """Invoke build_linux.py to produce dist/anime-updater."""
    try:
        result = subprocess.run(
            [sys.executable, "build_linux.py"],
            capture_output=False,          # let output stream to terminal
        )
        if result.returncode == 0:
            print("[OK] Linux binary built successfully")
            return True
        else:
            print("[ERROR] Linux build failed")
            return False
    except Exception as exc:
        print(f"[ERROR] Build raised an exception: {exc}")
        return False


def create_release_package(version: str, output_dir: str = RELEASES_DIR) -> bool:
    """
    Assemble the release directory and zip it as
    Anime_Updater_{version}_Linux.zip.
    """
    try:
        os.makedirs(output_dir, exist_ok=True)

        version_dir = os.path.join(output_dir, f"v{version}")
        if os.path.exists(version_dir):
            shutil.rmtree(version_dir)
        os.makedirs(version_dir)

        # Copy main binary
        bin_src = os.path.join("dist", BINARY_NAME)
        if not os.path.exists(bin_src):
            print(f"[ERROR] Binary not found at {bin_src}")
            return False
        shutil.copy2(bin_src, version_dir)
        print(f"[OK] Copied {BINARY_NAME} to {version_dir}")

        # Copy optional docs
        for filename in ("README.md", "requirements.txt", "CHANGELOG.md"):
            if os.path.exists(filename):
                shutil.copy2(filename, version_dir)
                print(f"[OK] Copied {filename}")

        # Write release metadata
        release_info = {
            "version": version,
            "build_date": datetime.date.today().isoformat(),
            "platform": "linux",
            "executable": BINARY_NAME,
            "files": os.listdir(version_dir),
        }
        with open(os.path.join(version_dir, "release_info.json"), "w") as fh:
            json.dump(release_info, fh, indent=2)

        # Create ZIP:  Anime_Updater_{version}_Linux.zip
        zip_name = f"Anime_Updater_{version}_Linux"
        zip_path = os.path.join(output_dir, zip_name)
        shutil.make_archive(zip_path, "zip", version_dir)
        print(f"[OK] Release archive: {zip_path}.zip")

        return True

    except Exception as exc:
        print(f"[ERROR] Could not create release package: {exc}")
        return False


def _read_current_version() -> str:
    try:
        with open(VERSION_FILE, "r") as fh:
            content = fh.read()
        m = re.search(r'__version__ = "([^"]*)"', content)
        return m.group(1) if m else "1.0.0"
    except Exception:
        return "1.0.0"


def main():
    print("Anime Updater — Linux Release Builder")
    print("=" * 40)

    if os.name != "posix":
        print("[WARN] This script is intended to run on Linux.")

    # Determine new version
    if len(sys.argv) > 1:
        new_version = sys.argv[1]
    else:
        current_version = _read_current_version()
        print(f"Current version: {current_version}")
        new_version = input(f"Enter new version (current: {current_version}): ").strip()
        if not new_version:
            new_version = current_version

    print(f"Building version: {new_version}")

    if not update_version(VERSION_FILE, new_version):
        sys.exit(1)

    if not build_executable():
        sys.exit(1)

    if not create_release_package(new_version):
        sys.exit(1)

    print(f"\n[SUCCESS] Build completed!")
    print(f"  Version : {new_version}")
    print(f"  Archive : {RELEASES_DIR}/Anime_Updater_{new_version}_Linux.zip")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBuild cancelled by user.")
    except Exception as exc:
        print(f"\nUnexpected error: {exc}")
        sys.exit(1)
