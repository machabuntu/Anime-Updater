#!/usr/bin/env python3
"""
Linux build script for Anime Updater.

Builds a standalone binary with PyInstaller so the app can be installed to
autostart on Linux without running main.py directly.
"""

import os
import subprocess
import sys
from pathlib import Path


def check_pyinstaller() -> bool:
    """Ensure PyInstaller is available."""
    try:
        import PyInstaller  # noqa: F401
        print("[OK] PyInstaller is available")
        return True
    except ImportError:
        print("[INFO] PyInstaller not found, installing...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "pyinstaller"]
            )
            print("[OK] PyInstaller installed successfully")
            return True
        except subprocess.CalledProcessError as exc:
            print(f"[ERROR] Failed to install PyInstaller: {exc}")
            return False


def build_executable() -> bool:
    """Build the Linux binary with PyInstaller CLI."""
    print("Building Linux binary...")

    # Use os.pathsep so add-data format is correct on both Linux (:) and Windows (;)
    add_data_sep = os.pathsep

    cmd = [
        "pyinstaller",
        "--name",
        "anime-updater",
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
        "--add-data",
        f"src{add_data_sep}src",
        "main.py",
    ]

    # Prefer PNG icon on Linux; fall back to ICO if only that exists.
    if Path("icon.png").exists():
        cmd.extend(["--icon", "icon.png"])
    elif Path("icon.ico").exists():
        cmd.extend(["--icon", "icon.ico"])

    try:
        subprocess.check_call(cmd)
        print("[OK] Linux binary built successfully")
        return True
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] Build failed: {exc}")
        return False


def copy_files():
    """Copy auxiliary files into dist for convenience."""
    dist_dir = Path("dist")
    if not dist_dir.exists():
        print("[ERROR] dist directory not found after build")
        return

    for filename in ("README.md", "requirements.txt"):
        src = Path(filename)
        if src.exists():
            try:
                dst = dist_dir / src.name
                dst.write_bytes(src.read_bytes())
                print(f"[OK] Copied {src.name}")
            except Exception as exc:  # pylint: disable=broad-except
                print(f"[WARN] Could not copy {src.name}: {exc}")


def main():
    if os.name != "posix":
        print("[WARN] This script is intended to run on Linux (posix).")

    if not check_pyinstaller():
        sys.exit(1)

    if not build_executable():
        sys.exit(1)

    copy_files()

    binary_path = Path("dist") / "anime-updater"
    if binary_path.exists():
        size_mb = binary_path.stat().st_size / (1024 * 1024)
        print(f"\nBinary created: {binary_path} ({size_mb:.1f} MB)")
        print("You can place it in ~/.local/bin and add to autostart (e.g. systemd user service).")
    else:
        print("\n[WARN] Binary not found in dist/. Check PyInstaller output.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBuild cancelled by user.")

