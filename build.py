#!/usr/bin/env python3
"""
Build script for creating Anime Updater executable
"""

import os
import sys
import subprocess
import shutil

def check_pyinstaller():
    """Check if PyInstaller is installed"""
    try:
        import PyInstaller
        print("[OK] PyInstaller is available")
        return True
    except ImportError:
        print("[ERROR] PyInstaller not found")
        print("Installing PyInstaller...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
            print("[OK] PyInstaller installed successfully")
            return True
        except subprocess.CalledProcessError:
            print("[ERROR] Failed to install PyInstaller")
            return False

SPEC_FILE = "Shikimori Updater.spec"


def check_pyside():
    """Verify PySide6 is installed before handing over to PyInstaller."""
    try:
        import PySide6
    except ImportError:
        print("[ERROR] PySide6 is not installed")
        print("Install it with: pip install -r requirements.txt")
        return False

    print(f"[OK] PySide6 {PySide6.__version__} is available")
    return True


def build_executable():
    """Build the executable from the spec file"""
    print("Building executable...")

    if not os.path.exists(SPEC_FILE):
        print(f"[ERROR] {SPEC_FILE} not found. It is tracked in git; run this")
        print("        script from the repository root.")
        return False

    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", SPEC_FILE]

    try:
        subprocess.check_call(cmd)
        print("[OK] Executable built successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Build failed: {e}")
        return False

def copy_files():
    """Copy additional files to dist folder"""
    dist_dir = "dist"
    if not os.path.exists(dist_dir):
        print("[ERROR] Dist directory not found")
        return False
    
    files_to_copy = [
        "README.md",
        "requirements.txt"
    ]
    
    for file in files_to_copy:
        if os.path.exists(file):
            try:
                shutil.copy2(file, dist_dir)
                print(f"[OK] Copied {file}")
            except Exception as e:
                print(f"[WARNING] Could not copy {file}: {e}")
    
    return True

def main():
    """Main build function"""
    print("Anime Updater Build Script")
    print("=" * 40)
    
    if not check_pyside():
        return False

    # Check PyInstaller
    if not check_pyinstaller():
        print("\nBuild failed. Please install PyInstaller manually:")
        print("pip install pyinstaller")
        return False
    
    # Build executable
    if not build_executable():
        print("\nBuild failed. Check the output above for errors.")
        return False
    
    # Copy additional files
    copy_files()
    
    print("\n" + "=" * 40)
    print("[SUCCESS] Build completed successfully!")
    
    exe_path = os.path.join("dist", "Anime Updater.exe")
    if os.path.exists(exe_path):
        size = os.path.getsize(exe_path) / (1024 * 1024)  # Size in MB
        print(f"\nExecutable created: {exe_path}")
        print(f"Size: {size:.1f} MB")
        print("\nYou can now distribute the 'dist' folder")
        print("or just the executable file.")
    
    return True

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nBuild cancelled by user.")
    except Exception as e:
        print(f"\nUnexpected error during build: {e}")
        print("Please check the requirements and try again.")
