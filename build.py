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
BINARY_PATH = os.path.join("dist", "Anime Updater.exe")

# Import name -> pip package. PyInstaller silently leaves out whatever is not
# installed, producing an exe that dies at start, so all of them are checked.
REQUIRED_MODULES = {
    "PySide6": "PySide6-Essentials",
    "requests": "requests",
    "socks": "pysocks",
    "psutil": "psutil",
    "dotenv": "python-dotenv",
    "win32gui": "pywin32",
}


def check_requirements():
    """Verify every runtime dependency is importable before building."""
    missing = []
    for module, package in REQUIRED_MODULES.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)

    if missing:
        print(f"[ERROR] Missing packages: {', '.join(missing)}")
        print("        Install them with:  pip install -r requirements.txt")
        return False

    import PySide6
    print(f"[OK] PySide6 {PySide6.__version__} and the other requirements are installed")
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

    if sys.platform != "win32":
        print("[ERROR] build.py builds the Windows exe and needs a Windows Python;")
        print("        on Linux use build_linux.py.")
        return False

    if not check_requirements():
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

    if not os.path.exists(BINARY_PATH):
        print(f"[ERROR] {BINARY_PATH} was not produced. Check the PyInstaller output.")
        return False

    print("\n" + "=" * 40)
    print("[SUCCESS] Build completed successfully!")

    size = os.path.getsize(BINARY_PATH) / (1024 * 1024)  # Size in MB
    print(f"\nExecutable created: {BINARY_PATH}")
    print(f"Size: {size:.1f} MB")
    print("\nYou can now distribute the 'dist' folder")
    print("or just the executable file.")

    return True

if __name__ == "__main__":
    try:
        sys.exit(0 if main() else 1)
    except KeyboardInterrupt:
        print("\n\nBuild cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error during build: {e}")
        print("Please check the requirements and try again.")
        sys.exit(1)
