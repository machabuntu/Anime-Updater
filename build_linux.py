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


def check_pyside() -> bool:
    """Verify PySide6 is installed and ships the platform plugins Qt needs."""
    try:
        import PySide6
    except ImportError:
        print("[ERROR] PySide6 is not installed.")
        print("        Install it with:  pip install -r requirements.txt")
        return False

    print(f"[OK] PySide6 {PySide6.__version__} is available")

    plugins = Path(PySide6.__file__).parent / "Qt" / "plugins" / "platforms"
    if not plugins.is_dir():
        print(f"[ERROR] Qt platform plugins are missing at {plugins}")
        return False

    available = sorted(p.stem.removeprefix("libq") for p in plugins.glob("libq*.so"))
    print(f"[OK] Qt platform plugins: {', '.join(available)}")

    # Without xcb the binary cannot start on X11 or under XWayland, which is
    # still how most desktops run it.
    if "xcb" not in available:
        print("[ERROR] The xcb platform plugin is missing; the binary would not")
        print("        start on X11. Reinstall PySide6-Essentials.")
        return False

    if "wayland" not in available:
        print("[WARN] No wayland plugin; the binary will fall back to XWayland.")

    return True


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
    """Build the Linux binary from the spec file."""
    print("\nBuilding Linux binary...")

    if not Path(SPEC_FILE).exists():
        print(f"[ERROR] {SPEC_FILE} not found. It is tracked in git; run the")
        print("        script from the repository root.")
        return False

    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", SPEC_FILE]

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

    extras = [
        Path("README.md"),
        Path("requirements.txt"),
        # Installing this entry into ~/.local/share/applications is what gives
        # the binary an icon in the task bar and an identity to the portal.
        Path("packaging/anime-updater.desktop"),
        Path("icon.png"),
    ]

    for src in extras:
        if not src.exists():
            continue
        try:
            (dist_dir / src.name).write_bytes(src.read_bytes())
            print(f"[OK] Copied {src.name}")
        except OSError as exc:
            print(f"[WARN] Could not copy {src.name}: {exc}")


def main():
    print("Anime Updater — Linux Build Script")
    print("=" * 40)

    if os.name != "posix":
        print("[WARN] This script is intended to run on Linux (posix).")

    if not check_pyside():
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
