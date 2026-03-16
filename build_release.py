#!/usr/bin/env python3
"""
Enhanced build script with version management and release automation
"""

import os
import sys
import subprocess
import shutil
import json
import datetime
from pathlib import Path

def update_version(version_file, new_version):
    """Update version in version.py file"""
    try:
        with open(version_file, 'r') as f:
            content = f.read()
        
        # Update version
        import re
        content = re.sub(r'__version__ = "[^"]*"', f'__version__ = "{new_version}"', content)
        
        # Update build date
        today = datetime.date.today().strftime('%Y-%m-%d')
        content = re.sub(r'BUILD_DATE = "[^"]*"', f'BUILD_DATE = "{today}"', content)
        
        with open(version_file, 'w') as f:
            f.write(content)
        
        print(f"Updated version to {new_version} and build date to {today}")
        return True
    except Exception as e:
        print(f"Error updating version: {e}")
        return False

def build_executable():
    """Build the executable"""
    try:
        # Run the existing build script
        result = subprocess.run([sys.executable, 'build.py'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("Build successful!")
            print(result.stdout)
            return True
        else:
            print("Build failed!")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"Error building executable: {e}")
        return False

def create_release_package(version, output_dir="releases"):
    """Create a release package"""
    try:
        # Create releases directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Create version-specific directory
        version_dir = os.path.join(output_dir, f"v{version}")
        if os.path.exists(version_dir):
            shutil.rmtree(version_dir)
        os.makedirs(version_dir)
        
        # Copy executable
        exe_path = os.path.join("dist", "Anime Updater.exe")
        if os.path.exists(exe_path):
            shutil.copy2(exe_path, version_dir)
            print(f"Copied executable to {version_dir}")
        else:
            print(f"Executable not found at {exe_path}")
            return False
        
        # Copy important files
        files_to_copy = [
            "README.md",
            "requirements.txt",
            "CHANGELOG.md"  # If you have one
        ]
        
        for file in files_to_copy:
            if os.path.exists(file):
                shutil.copy2(file, version_dir)
                print(f"Copied {file}")
        
        # Create release info
        release_info = {
            "version": version,
            "build_date": datetime.date.today().isoformat(),
            "executable": "Anime Updater.exe",
            "files": os.listdir(version_dir)
        }
        
        with open(os.path.join(version_dir, "release_info.json"), 'w') as f:
            json.dump(release_info, f, indent=2)
        
        # Create zip file
        zip_path = os.path.join(output_dir, f"AnimeUpdater-v{version}.zip")
        shutil.make_archive(zip_path.replace('.zip', ''), 'zip', version_dir)
        
        print(f"Created release package: {zip_path}")
        return True
        
    except Exception as e:
        print(f"Error creating release package: {e}")
        return False

def main():
    """Main build and release function"""
    print("Anime Updater Release Builder")
    print("=" * 40)
    
    # Get version from command line or prompt
    if len(sys.argv) > 1:
        new_version = sys.argv[1]
    else:
        # Try to read current version
        try:
            with open('src/utils/version.py', 'r') as f:
                content = f.read()
                import re
                version_match = re.search(r'__version__ = "([^"]*)', content)
                if version_match:
                    current_version = version_match.group(1)
                else:
                    current_version = "1.0.0"
                print(f"Current version: {current_version}")
        except:
            current_version = "1.0.0"
        
        new_version = input(f"Enter new version (current: {current_version}): ").strip()
        if not new_version:
            new_version = current_version
    
    print(f"Building version: {new_version}")
    
    # Update version file
    version_file = "src/utils/version.py"
    if not update_version(version_file, new_version):
        print("Failed to update version file")
        return False
    
    # Build executable
    if not build_executable():
        print("Failed to build executable")
        return False
    
    # Create release package
    if not create_release_package(new_version):
        print("Failed to create release package")
        return False
    
    print(f"\nBuild completed successfully!")
    print(f"Version: {new_version}")
    print(f"Release package created in: releases/")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nBuild cancelled by user.")
    except Exception as e:
        print(f"\nUnexpected error during build: {e}")
        print("Please check the requirements and try again.")
