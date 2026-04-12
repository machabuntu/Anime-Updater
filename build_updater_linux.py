#!/usr/bin/env python3
"""
Build script for the standalone Linux updater binary.
Produces dist/updater_linux via PyInstaller.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


def build_standalone_updater() -> bool:
    """Build the standalone updater binary using PyInstaller."""
    current_dir = Path(__file__).parent
    updater_script = current_dir / "updater_standalone_linux.py"

    if not updater_script.exists():
        print(f"Error: updater script not found at {updater_script}")
        return False

    dist_dir = current_dir / "dist"

    pyinstaller_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--console",
        "--name", "updater_linux",
        "--distpath", str(dist_dir),
        "--workpath", str(current_dir / "build_updater_linux"),
        "--specpath", str(current_dir),
        "--clean",
        str(updater_script),
    ]

    print("Building standalone Linux updater…")
    print(f"Command: {' '.join(pyinstaller_cmd)}")

    try:
        result = subprocess.run(pyinstaller_cmd, check=True, capture_output=True, text=True)
        print("Build completed successfully!")
        print(result.stdout)

        updater_bin = dist_dir / "updater_linux"
        if updater_bin.exists():
            size_mb = updater_bin.stat().st_size / (1024 * 1024)
            print(f"Standalone updater created at: {updater_bin}")
            print(f"File size: {size_mb:.1f} MB")
            return True
        else:
            print("Error: binary not found after build")
            return False

    except subprocess.CalledProcessError as exc:
        print(f"Build failed: {exc}")
        print(f"stdout: {exc.stdout}")
        print(f"stderr: {exc.stderr}")
        return False
    except Exception as exc:
        print(f"Build failed with exception: {exc}")
        return False


def main():
    print("Anime Updater — Linux Standalone Updater Build Script")
    print("=" * 55)

    if os.name != "posix":
        print("[WARN] This script is intended to run on Linux.")

    if not build_standalone_updater():
        sys.exit(1)

    print("\nStandalone Linux updater built successfully!")
    print("Place dist/updater_linux next to the anime-updater binary.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBuild cancelled by user.")
