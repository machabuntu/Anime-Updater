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

def build_executable():
    """Build the executable using PyInstaller"""
    print("Building executable...")
    
    # Use spec file if it exists, otherwise use command line
    spec_files = ["Anime Updater.spec", "anime_updater.spec", "Shikimori Updater.spec", "shikimori_updater.spec"]
    spec_file = None
    for spec in spec_files:
        if os.path.exists(spec):
            spec_file = spec
            break
    
    if spec_file:
        print(f"Using spec file for build: {spec_file}")
        cmd = [
            "pyinstaller",
            "--clean",     # Clean PyInstaller cache
            "--noconfirm", # Overwrite output directory
            spec_file
        ]
    else:
        print("Using command line build...")
        # PyInstaller command
        cmd = [
            "pyinstaller",
            "--name", "Anime Updater",
            "--windowed",  # No console window
            "--onefile",   # Single executable file
            "--clean",     # Clean PyInstaller cache
            "--noconfirm", # Overwrite output directory
            "--add-data", "src;src",  # Include src directory
            "main.py"
        ]
        
        # Add icon files as data if they exist
        if os.path.exists("icon.png"):
            cmd.extend(["--add-data", "icon.png;."])
        if os.path.exists("icon.ico"):
            cmd.extend(["--add-data", "icon.ico;."])
        
        # Add icon if it exists
        if os.path.exists("icon.ico"):
            cmd.extend(["--icon", "icon.ico"])
        elif os.path.exists("icon.png"):
            # Convert PNG to ICO if needed
            try:
                from PIL import Image
                img = Image.open("icon.png")
                img.save("icon.ico")
                cmd.extend(["--icon", "icon.ico"])
                print("[OK] Converted icon.png to icon.ico")
            except ImportError:
                print("! PIL not available for icon conversion, using default icon")
            except Exception as e:
                print(f"! Failed to convert icon: {e}")
    
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
