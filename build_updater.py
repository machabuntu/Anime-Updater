#!/usr/bin/env python3
"""
Build script for the standalone updater executable
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def build_standalone_updater():
    """Build the standalone updater executable using PyInstaller"""
    
    # Get the current directory
    current_dir = Path(__file__).parent
    updater_script = current_dir / "updater_standalone.py"
    
    if not updater_script.exists():
        print(f"Error: Updater script not found at {updater_script}")
        return False
    
    # Output directory
    dist_dir = current_dir / "dist"
    
    # PyInstaller command
    pyinstaller_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--console",
        "--name", "updater",
        "--distpath", str(dist_dir),
        "--workpath", str(current_dir / "build_updater"),
        "--specpath", str(current_dir),
        "--clean",
        str(updater_script)
    ]
    
    print("Building standalone updater...")
    print(f"Command: {' '.join(pyinstaller_cmd)}")
    
    try:
        result = subprocess.run(pyinstaller_cmd, check=True, capture_output=True, text=True)
        print("Build completed successfully!")
        
        # Check if the executable was created
        updater_exe = dist_dir / "updater.exe"
        if updater_exe.exists():
            print(f"Standalone updater created at: {updater_exe}")
            print(f"File size: {updater_exe.stat().st_size} bytes")
            return True
        else:
            print("Error: Executable not found after build")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return False
    except Exception as e:
        print(f"Build failed with exception: {e}")
        return False

def main():
    """Main entry point"""
    if not build_standalone_updater():
        sys.exit(1)
    
    print("\nStandalone updater built successfully!")
    print("You can now use the standalone updater to avoid MEI folder conflicts.")

if __name__ == "__main__":
    main()
