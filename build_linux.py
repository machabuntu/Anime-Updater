#!/usr/bin/env python3
"""
Linux build script for Anime Updater.

Builds a standalone binary with PyInstaller so any Linux user can download
a single file and run the application directly.
"""

import os
import subprocess
import sys
from pathlib import Path

SPEC_FILE = "anime-updater-linux.spec"
BINARY_NAME = "anime-updater"


def check_tkinter() -> bool:
    """Verify that tkinter is available (requires python3-tk on most distros)."""
    try:
        import tkinter  # noqa: F401
        print("[OK] tkinter is available")
        return True
    except ImportError:
        print("[ERROR] tkinter is not installed.")
        print("       Install it with your package manager, e.g.:")
        print("         Ubuntu/Debian:  sudo apt install python3-tk")
        print("         Fedora:         sudo dnf install python3-tkinter")
        print("         Arch:           sudo pacman -S tk")
        return False


def check_pyinstaller() -> bool:
    """Ensure PyInstaller is available, installing it if needed."""
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
    """Build the Linux binary using the spec file or CLI fallback."""
    print("\nBuilding Linux binary...")

    if Path(SPEC_FILE).exists():
        print(f"Using spec file: {SPEC_FILE}")
        cmd = [
            "pyinstaller",
            "--clean",
            "--noconfirm",
            SPEC_FILE,
        ]
    else:
        print(f"[WARN] {SPEC_FILE} not found, falling back to CLI build")
        cmd = [
            "pyinstaller",
            "--name", BINARY_NAME,
            "--onefile",
            "--windowed",
            "--clean",
            "--noconfirm",
            "--strip",
            "--add-data", f"src{os.pathsep}src",
        ]

        if Path("icon.png").exists():
            cmd.extend(["--add-data", f"icon.png{os.pathsep}."])
            cmd.extend(["--icon", "icon.png"])
        elif Path("icon.ico").exists():
            cmd.extend(["--add-data", f"icon.ico{os.pathsep}."])
            cmd.extend(["--icon", "icon.ico"])

        cmd.append("main.py")

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
    print("Anime Updater — Linux Build Script")
    print("=" * 40)

    if os.name != "posix":
        print("[WARN] This script is intended to run on Linux (posix).")

    if not check_tkinter():
        sys.exit(1)

    if not check_pyinstaller():
        sys.exit(1)

    if not build_executable():
        sys.exit(1)

    copy_files()

    binary_path = Path("dist") / BINARY_NAME
    if binary_path.exists():
        size_mb = binary_path.stat().st_size / (1024 * 1024)
        print(f"\n{'=' * 40}")
        print(f"[SUCCESS] Build completed!")
        print(f"  Binary:  {binary_path.resolve()}")
        print(f"  Size:    {size_mb:.1f} MB")
        print(f"\nRun it directly:  ./{binary_path}")
        print("Or copy to PATH:  cp dist/anime-updater ~/.local/bin/")
    else:
        print("\n[WARN] Binary not found in dist/. Check PyInstaller output.")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBuild cancelled by user.")
