#!/usr/bin/env python3
"""
Linux release builder for Anime Updater.

Usage:
    python build_release_linux.py          # prompts for version
    python build_release_linux.py 4.1.0    # non-interactive

The zip name is the contract with src/utils/updater.py: it looks at the latest
GitHub release for ``Anime_Updater_{version}_Linux.zip`` and extracts
``anime-updater`` from it. A differently named archive is invisible to
installed copies.
"""

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


VERSION_FILE = "src/utils/version.py"
BINARY_NAME = "anime-updater"
RELEASES_DIR = "releases"
ZIP_SUFFIX = "Linux"

# Files shipped next to the binary for a first-time install. The auto-updater
# later pulls only BINARY_NAME out of the zip and ignores the rest.
EXTRA_FILES = (
    Path("README.md"),
    Path("LICENSE"),
    Path("packaging/anime-updater.desktop"),
    Path("icon.png"),
)


def update_version(version_file: str, new_version: str) -> bool:
    """Patch __version__ and BUILD_DATE inside version.py."""
    try:
        content = Path(version_file).read_text(encoding="utf-8")
        content = re.sub(r'__version__ = "[^"]*"', f'__version__ = "{new_version}"', content)
        today = datetime.date.today().strftime("%Y-%m-%d")
        content = re.sub(r'BUILD_DATE = "[^"]*"', f'BUILD_DATE = "{today}"', content)
        Path(version_file).write_text(content, encoding="utf-8")
        print(f"[OK] Version set to {new_version}, build date to {today}")
        return True
    except OSError as exc:
        print(f"[ERROR] Could not update version file: {exc}")
        return False


def run_script(script: str) -> bool:
    result = subprocess.run([sys.executable, script])
    if result.returncode != 0:
        print(f"[ERROR] {script} failed")
        return False
    print(f"[OK] {script} finished")
    return True


def create_release_package(version: str, output_dir: str = RELEASES_DIR) -> bool:
    """Assemble releases/v{version}/ and zip it for the updater."""
    try:
        os.makedirs(output_dir, exist_ok=True)

        version_dir = Path(output_dir) / f"v{version}"
        if version_dir.exists():
            shutil.rmtree(version_dir)
        version_dir.mkdir(parents=True)

        bin_src = Path("dist") / BINARY_NAME
        if not bin_src.exists():
            print(f"[ERROR] Binary not found at {bin_src}")
            return False
        dest_bin = version_dir / BINARY_NAME
        shutil.copy2(bin_src, dest_bin)
        dest_bin.chmod(0o755)
        print(f"[OK] Copied {BINARY_NAME}")

        updater_src = Path("dist") / "updater_linux"
        if updater_src.exists():
            dest_updater = version_dir / "updater_linux"
            shutil.copy2(updater_src, dest_updater)
            dest_updater.chmod(0o755)
            print("[OK] Copied updater_linux")
        else:
            print("[WARN] dist/updater_linux missing; new installs will have no self-updater")

        for src in EXTRA_FILES:
            if src.exists():
                shutil.copy2(src, version_dir / src.name)
                print(f"[OK] Copied {src.name}")

        release_info = {
            "version": version,
            "build_date": datetime.date.today().isoformat(),
            "platform": "linux",
            "executable": BINARY_NAME,
            "files": sorted(os.listdir(version_dir)),
        }
        (version_dir / "release_info.json").write_text(
            json.dumps(release_info, indent=2), encoding="utf-8"
        )

        zip_stem = Path(output_dir) / f"Anime_Updater_{version}_{ZIP_SUFFIX}"
        shutil.make_archive(str(zip_stem), "zip", version_dir)
        print(f"[OK] Release archive: {zip_stem}.zip")
        return True

    except OSError as exc:
        print(f"[ERROR] Could not create release package: {exc}")
        return False


def _read_current_version() -> str:
    try:
        content = Path(VERSION_FILE).read_text(encoding="utf-8")
        match = re.search(r'__version__ = "([^"]*)"', content)
        return match.group(1) if match else "1.0.0"
    except OSError:
        return "1.0.0"


def main() -> int:
    print("Anime Updater — Linux Release Builder")
    print("=" * 40)

    if os.name != "posix":
        print("[WARN] This script is intended to run on Linux.")

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
        return 1
    if not run_script("build_linux.py"):
        return 1
    # Best-effort: a missing updater binary still produces a usable zip.
    run_script("build_updater_linux.py")
    if not create_release_package(new_version):
        return 1

    print("\n[SUCCESS] Build completed!")
    print(f"  Version : {new_version}")
    print(f"  Archive : {RELEASES_DIR}/Anime_Updater_{new_version}_{ZIP_SUFFIX}.zip")
    print("  Upload that zip as a GitHub release asset so the in-app updater can see it.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nBuild cancelled by user.")
        sys.exit(130)
