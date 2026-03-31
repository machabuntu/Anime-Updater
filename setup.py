#!/usr/bin/env python3
"""
Setup script for Shikimori Updater
"""

import sys
import subprocess
import os

def install_requirements():
    """Install required packages"""
    print("Installing required packages...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✓ Requirements installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install requirements: {e}")
        return False

def check_python_version():
    """Check if Python version is compatible"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"✗ Python 3.8+ is required, but you have {version.major}.{version.minor}")
        return False
    
    print(f"✓ Python {version.major}.{version.minor}.{version.micro} is compatible")
    return True

def create_desktop_shortcut():
    """Create desktop shortcut (Windows only)"""
    if sys.platform != "win32":
        return
    
    try:
        import winshell
        from win32com.client import Dispatch
        
        desktop = winshell.desktop()
        shortcut_path = os.path.join(desktop, "Shikimori Updater.lnk")
        target = os.path.join(os.path.dirname(__file__), "main.py")
        working_dir = os.path.dirname(__file__)
        
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.Targetpath = sys.executable
        shortcut.Arguments = f'"{target}"'
        shortcut.WorkingDirectory = working_dir
        shortcut.IconLocation = sys.executable
        shortcut.save()
        
        print(f"✓ Desktop shortcut created: {shortcut_path}")
        
    except ImportError:
        print("! Desktop shortcut creation requires 'winshell' package")
        print("  You can install it with: pip install winshell pywin32")
    except Exception as e:
        print(f"! Could not create desktop shortcut: {e}")

def main():
    """Main setup function"""
    print("Shikimori Updater Setup")
    print("=" * 40)
    
    # Check Python version
    if not check_python_version():
        print("\nPlease upgrade Python and try again.")
        return False
    
    # Install requirements
    if not install_requirements():
        print("\nSetup failed. Please check your internet connection and try again.")
        return False
    
    # Optional: Create desktop shortcut
    if sys.platform == "win32":
        response = input("\nWould you like to create a desktop shortcut? (y/n): ").lower()
        if response in ['y', 'yes']:
            create_desktop_shortcut()
    
    print("\n" + "=" * 40)
    print("✓ Setup completed successfully!")
    print("\nTo run the application:")
    print(f"  python {os.path.join(os.path.dirname(__file__), 'main.py')}")
    print("\nFor first-time setup:")
    print("1. Create a Shikimori API application at:")
    print("   https://shikimori.io/oauth/applications")
    print("2. Use redirect URI: http://localhost:8080/callback")
    print("3. Grant 'user_rates' scope")
    print("4. Run the application and follow the authentication steps")
    
    return True

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
    except Exception as e:
        print(f"\nUnexpected error during setup: {e}")
        print("Please check the README.md for manual installation instructions.")
