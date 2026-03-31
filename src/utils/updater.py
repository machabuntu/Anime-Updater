"""
Auto-updater utility for Anime Updater
Checks for updates from GitHub releases and handles downloading/installing
"""

import os
import sys
import json
import subprocess
import tempfile
import shutil
import zipfile
from pathlib import Path
from typing import Optional, Dict, Any
import urllib.request
import urllib.error
from packaging import version
from .logger import get_logger

logger = get_logger('updater')

class Updater:
    """Handles application updates from GitHub releases"""
    
    def __init__(self, github_repo: str, current_version: str):
        """
        Initialize updater
        
        Args:
            github_repo: GitHub repository in format 'owner/repo'
            current_version: Current application version (e.g., '1.0.0')
        """
        self.github_repo = github_repo
        self.current_version = current_version
        self.api_url = f"https://api.github.com/repos/{github_repo}/releases/latest"
        self.download_url = None
        self.latest_version = None
        self.release_notes = None
        
    def check_for_updates(self) -> bool:
        """
        Check if updates are available
        
        Returns:
            True if update is available, False otherwise
        """
        try:
            if not getattr(sys, 'frozen', False):
                return False
            logger.info(f"Checking for updates from {self.api_url}")
            
            # Create request with user agent
            request = urllib.request.Request(self.api_url)
            request.add_header('User-Agent', 'AnimeUpdater/1.0')
            request.add_header('Accept', 'application/vnd.github.v3+json')
            
            # Get latest release info
            with urllib.request.urlopen(request, timeout=30) as response:
                response_text = response.read().decode('utf-8')
                data = json.loads(response_text)
                
                # Log response for debugging
                logger.debug(f"GitHub API response status: {response.status}")
                logger.debug(f"Response headers: {dict(response.headers)}")
                logger.debug(f"Response data keys: {list(data.keys())}")
            
            # Extract version info
            self.latest_version = data.get('tag_name', '').lstrip('v')
            self.release_notes = data.get('body', '')
            
            # Find ZIP archive download URL
            # Look for pattern: Anime_Updater_X.X.X_Windows.zip
            assets = data.get('assets', [])
            logger.info(f"Found {len(assets)} assets in release")
            
            for asset in assets:
                asset_name = asset.get('name', '')
                download_url = asset.get('browser_download_url', '')
                logger.info(f"Asset: {asset_name}, Download URL: {download_url}")
                
                if ((asset_name.startswith('Anime_Updater_') or
                     asset_name.startswith('Shikimori_Updater_')) and
                    asset_name.endswith('_Windows.zip')):
                    if download_url:
                        self.download_url = download_url
                        logger.info(f"Found ZIP archive: {asset_name}")
                        logger.info(f"Download URL: {self.download_url}")
                        break
                    else:
                        logger.warning(f"ZIP archive found but no download URL: {asset_name}")
                        
                # Also try more flexible matching
                elif (asset_name.endswith('.zip') and 
                      ('Anime_Updater' in asset_name or 'AnimeUpdater' in asset_name or
                       'Anime Updater' in asset_name or
                       'Shikimori' in asset_name or 'ShikimoriUpdater' in asset_name)):
                    if download_url:
                        self.download_url = download_url
                        logger.info(f"Found ZIP archive (flexible match): {asset_name}")
                        logger.info(f"Download URL: {self.download_url}")
                        break
                    else:
                        logger.warning(f"ZIP archive found but no download URL: {asset_name}")
            
            if not self.download_url:
                logger.warning("No Windows ZIP archive found in latest release")
                logger.warning(f"Available assets: {[asset.get('name', '') for asset in assets]}")
                return False
            
            # Compare versions
            if self.latest_version and self.current_version:
                is_newer = version.parse(self.latest_version) > version.parse(self.current_version)
                logger.info(f"Current: {self.current_version}, Latest: {self.latest_version}, Update available: {is_newer}")
                return is_newer
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to check for updates: {e}")
            return False
    
    def get_update_info(self) -> Dict[str, Any]:
        """Get information about available update"""
        return {
            'current_version': self.current_version,
            'latest_version': self.latest_version,
            'download_url': self.download_url,
            'release_notes': self.release_notes
        }
    
    def download_update(self, progress_callback=None) -> Optional[str]:
        """
        Download the update
        
        Args:
            progress_callback: Optional callback for progress updates
            
        Returns:
            Path to downloaded file or None if failed
        """
        if not self.download_url:
            logger.error("No download URL available")
            return None
        
        try:
            # Create temporary file for ZIP download
            temp_dir = tempfile.gettempdir()
            zip_filename = f"Anime_Updater_{self.latest_version}_Windows.zip"
            zip_path = os.path.join(temp_dir, zip_filename)
            
            logger.info(f"Downloading update ZIP from {self.download_url}")
            
            def report_progress(block_num, block_size, total_size):
                if progress_callback and total_size > 0:
                    progress = (block_num * block_size) / total_size * 85  # Reserve 15% for extraction
                    progress_callback(min(progress, 85))
            
            # Download ZIP file
            urllib.request.urlretrieve(self.download_url, zip_path, report_progress)
            logger.info(f"ZIP downloaded to {zip_path}")
            
            # Extract the EXE file from ZIP
            if progress_callback:
                progress_callback(90)  # Update progress to 90%
            
            exe_path = self._extract_exe_from_zip(zip_path)
            if not exe_path:
                return None
            
            # Clean up ZIP file but NOT the extracted EXE (update script will clean it up)
            try:
                os.remove(zip_path)
            except Exception:
                pass  # Ignore cleanup errors
            
            if progress_callback:
                progress_callback(100)  # Complete
            
            logger.info(f"Update extracted to {exe_path}")
            logger.info(f"NOTE: Extracted file will be cleaned up by update script")
            return exe_path
            
        except Exception as e:
            logger.error(f"Failed to download update: {e}")
            return None
    
    def install_update(self, downloaded_path: str) -> bool:
        """
        Install the update by replacing current executable
        
        Args:
            downloaded_path: Path to the downloaded update
            
        Returns:
            True if installation was successful
        """
        try:
            # Get current executable path
            if getattr(sys, 'frozen', False):
                current_exe = sys.executable
            else:
                # For development/testing - look for existing compiled version
                logger.warning("Running from source - looking for existing compiled version")
                
                # Try to find an existing compiled version in common locations
                possible_locations = [
                    os.path.join(os.getcwd(), "Anime Updater.exe"),
                    os.path.join(os.getcwd(), "dist", "Anime Updater.exe"),
                    os.path.join(os.getcwd(), "build", "Anime Updater.exe"),
                    os.path.join(os.path.dirname(os.getcwd()), "Anime Updater.exe"),
                    os.path.join(os.getcwd(), "Shikimori Updater.exe"),
                    os.path.join(os.getcwd(), "dist", "Shikimori Updater.exe"),
                ]
                
                current_exe = None
                for location in possible_locations:
                    if os.path.exists(location):
                        current_exe = location
                        logger.info(f"Found existing compiled version at: {location}")
                        break
                
                if not current_exe:
                    logger.error("Cannot update: No compiled version found and not running from frozen application")
                    logger.error("To test updates, either:")
                    logger.error("  1. Run from a compiled/frozen version of the application")
                    logger.error("  2. Place a compiled 'Anime Updater.exe' in one of these locations:")
                    for location in possible_locations:
                        logger.error(f"     - {location}")
                    return False
            
            # Validate files exist
            if not os.path.exists(downloaded_path):
                logger.error(f"Downloaded update file not found: {downloaded_path}")
                return False
            
            if not os.path.exists(current_exe):
                logger.error(f"Current executable not found: {current_exe}")
                return False
            
            # Log file information
            logger.info(f"Installing update:")
            logger.info(f"  Current EXE: {current_exe}")
            logger.info(f"  New EXE: {downloaded_path}")
            logger.info(f"  Current EXE size: {os.path.getsize(current_exe)} bytes")
            logger.info(f"  New EXE size: {os.path.getsize(downloaded_path)} bytes")
            
            # Try to use standalone updater first
            if self._use_standalone_updater(downloaded_path, current_exe):
                return True
            
            # Fallback to batch script method
            logger.info("Falling back to batch script method")
            update_script = self._create_update_script(downloaded_path, current_exe)
            
            # Validate script was created
            if not os.path.exists(update_script):
                logger.error(f"Failed to create update script: {update_script}")
                return False
            
            # Execute update script and exit
            logger.info(f"Executing update script: {update_script}")
            subprocess.Popen([update_script], shell=True)
            logger.info("Update script launched, exiting application")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to install update: {e}")
            return False
    
    def _extract_exe_from_zip(self, zip_path: str) -> Optional[str]:
        """
        Extract only the main application EXE file from the ZIP archive
        Ignores updater.exe and other files
        
        Args:
            zip_path: Path to the ZIP file
            
        Returns:
            Path to extracted EXE file or None if failed
        """
        try:
            temp_dir = tempfile.gettempdir()
            
            logger.info(f"Extracting main application EXE from ZIP archive")
            
            # Target executable names to look for (main application)
            target_exe_names = ["Anime Updater.exe", "AnimeUpdater.exe", "Shikimori Updater.exe", "ShikimoriUpdater.exe"]
            
            # Files to ignore during extraction
            ignore_files = ["updater.exe", "standalone_updater.exe", "ShikimoriUpdater_Updater.exe", "AnimeUpdater_Updater.exe"]
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # List all files in the ZIP
                file_list = zip_ref.namelist()
                logger.info(f"Files in ZIP: {file_list}")
                
                # Find the main application executable
                main_exe_entry = None
                for entry in file_list:
                    filename = os.path.basename(entry)
                    
                    # Skip directories
                    if entry.endswith('/'):
                        continue
                    
                    # Skip ignored files
                    if filename.lower() in [f.lower() for f in ignore_files]:
                        logger.info(f"Ignoring file during extraction: {filename}")
                        continue
                    
                    # Check if this is the main application executable
                    if filename in target_exe_names:
                        main_exe_entry = entry
                        logger.info(f"Found main application executable: {filename}")
                        break
                
                if not main_exe_entry:
                    logger.error(f"Could not find main application executable in ZIP")
                    logger.error(f"Looking for: {target_exe_names}")
                    logger.error(f"Available files: {[os.path.basename(f) for f in file_list if not f.endswith('/')]}")
                    return None
                
                # Extract only the main application executable directly to temp
                final_exe_path = os.path.join(temp_dir, f"AnimeUpdater_{self.latest_version}.exe")
                
                logger.info(f"Extracting {main_exe_entry} to {final_exe_path}")
                
                # Extract the specific file
                with zip_ref.open(main_exe_entry) as source, open(final_exe_path, 'wb') as target:
                    shutil.copyfileobj(source, target)
                
                logger.info(f"Main application EXE extracted to {final_exe_path}")
                logger.info(f"Extracted file size: {os.path.getsize(final_exe_path)} bytes")
                
                return final_exe_path
            
        except Exception as e:
            logger.error(f"Failed to extract EXE from ZIP: {e}")
            return None
    
    def _create_update_script(self, new_exe_path: str, current_exe_path: str) -> str:
        """Create a batch script to handle the update process"""
        # Extract just the filename from the current exe path for taskkill
        current_exe_name = os.path.basename(current_exe_path)
        
        script_content = f'''@echo off
setlocal enabledelayedexpansion
set LOG_FILE="%TEMP%\anime_update.log"
echo %DATE% %TIME% - Starting update script > %LOG_FILE%
echo %DATE% %TIME% - Current EXE: {current_exe_path} >> %LOG_FILE%
echo %DATE% %TIME% - New EXE: {new_exe_path} >> %LOG_FILE%
echo %DATE% %TIME% - EXE Name: {current_exe_name} >> %LOG_FILE%

echo Updating Anime Updater...
echo Current EXE: {current_exe_path}
echo New EXE: {new_exe_path}
echo EXE Name: {current_exe_name}

:: Wait for parent process to exit
echo %DATE% %TIME% - Waiting for parent process to exit >> %LOG_FILE%
timeout /t 1 /nobreak > nul

:: Try to gracefully shutdown the application via API
echo %DATE% %TIME% - Attempting graceful shutdown via API >> %LOG_FILE%
echo Attempting graceful shutdown...
curl -X POST "http://localhost:5000/api/shutdown" -H "Content-Type: application/json" -d "{{}}" -s --max-time 5 >> %LOG_FILE% 2>&1

:: Wait for graceful shutdown to complete
echo %DATE% %TIME% - Waiting for graceful shutdown to complete >> %LOG_FILE%
timeout /t 5 /nobreak > nul

:: Check if new executable exists
echo Checking if new executable exists...
echo %DATE% %TIME% - Checking if new executable exists at: {new_exe_path} >> %LOG_FILE%
if not exist "{new_exe_path}" (
    echo ERROR: New executable not found at: {new_exe_path}
    echo %DATE% %TIME% - ERROR: New executable not found >> %LOG_FILE%
    echo Available files in temp directory:
    dir "{os.path.dirname(new_exe_path)}" | find "AnimeUpdater"
    pause
    exit /b 1
)
echo %DATE% %TIME% - New executable found successfully >> %LOG_FILE%

:: Backup current version
echo Backing up current version...
echo %DATE% %TIME% - Backing up current version >> %LOG_FILE%
copy "{current_exe_path}" "{current_exe_path}.backup" >nul 2>&1

:: Replace with new version
echo Replacing executable...
echo Source: {new_exe_path}
echo Target: {current_exe_path}
echo %DATE% %TIME% - Replacing executable from {new_exe_path} to {current_exe_path} >> %LOG_FILE%
copy "{new_exe_path}" "{current_exe_path}"

if errorlevel 1 (
    echo Update failed, restoring backup...
    copy "{current_exe_path}.backup" "{current_exe_path}" >nul 2>&1
    if errorlevel 1 (
        echo Failed to restore backup!
        echo Manual intervention required.
        pause
        exit /b 1
    )
    echo Backup restored successfully.
    pause
    exit /b 1
) else (
    echo Update successful!
)

:: Verify the file was actually updated
echo Verifying update...
if exist "{current_exe_path}" (
    echo New executable size: 
    dir "{current_exe_path}" | find "bytes"
) else (
    echo ERROR: Executable not found after update!
    pause
    exit /b 1
)

:: Clean up
del "{current_exe_path}.backup" 2>nul
del "{new_exe_path}" 2>nul

:: Clean up old PyInstaller temp directories BEFORE restart
:: This forces the new application to extract fresh files
echo Cleaning up old PyInstaller temp directories...
for /d %%d in ("%TEMP%\_MEI*") do (
    echo Removing temp directory: %%d
    rmdir /s /q "%%d" 2>nul
)

:: Additional cleanup for other temp patterns
for /d %%d in ("%TEMP%\*Anime*Updater*") do (
    echo Removing Anime Updater temp directory: %%d
    rmdir /s /q "%%d" 2>nul
)
for /d %%d in ("%TEMP%\*Shikimori*") do (
    echo Removing legacy temp directory: %%d
    rmdir /s /q "%%d" 2>nul
)

:: Wait a moment for cleanup to complete
timeout /t 2 /nobreak > nul

:: Display success message
echo.
echo ========================================
echo   UPDATE COMPLETED SUCCESSFULLY!
echo ========================================
echo.
echo The application has been updated successfully.
echo Your application is now running version {self.latest_version}.
echo.
echo Attempting to restart the application...
echo.

:: Clear PyInstaller environment variables to prevent inheritance issues
echo Clearing PyInstaller environment variables...
echo %DATE% %TIME% - Clearing PyInstaller environment variables >> %LOG_FILE%
set _MEIPASS=
set _MEIPASS2=
set _MEI=
set PYINSTALLER_CRYPTO_KEY=
set PYINSTALLER_DISTPATH=
set PYINSTALLER_WORKPATH=
set PYINSTALLER_SPEC_PATH=
set PYINSTALLER_TEMP_PATH=
set PYINSTALLER_BUILDDIR=
set PYINSTALLER_CONFIG_DIR=
set PYINSTALLER_ONEFILE_TEMP_PATH=

:: Create a completely isolated launcher script to break inheritance chain
echo Creating isolated launcher script...
echo %DATE% %TIME% - Creating isolated launcher script >> %LOG_FILE%
set LAUNCHER_SCRIPT="%TEMP%\anime_launcher.bat"

:: Create the launcher script with maximum isolation
echo @echo off > %LAUNCHER_SCRIPT%
echo setlocal >> %LAUNCHER_SCRIPT%
echo echo Preparing to launch updated Anime Updater... >> %LAUNCHER_SCRIPT%
echo. >> %LAUNCHER_SCRIPT%
echo :: Clear all PyInstaller related environment variables >> %LAUNCHER_SCRIPT%
echo set _MEIPASS= >> %LAUNCHER_SCRIPT%
echo set _MEIPASS2= >> %LAUNCHER_SCRIPT%
echo set _MEI= >> %LAUNCHER_SCRIPT%
echo set PYINSTALLER_CRYPTO_KEY= >> %LAUNCHER_SCRIPT%
echo set PYINSTALLER_DISTPATH= >> %LAUNCHER_SCRIPT%
echo set PYINSTALLER_WORKPATH= >> %LAUNCHER_SCRIPT%
echo set PYINSTALLER_SPEC_PATH= >> %LAUNCHER_SCRIPT%
echo set PYINSTALLER_TEMP_PATH= >> %LAUNCHER_SCRIPT%
echo set PYINSTALLER_BUILDDIR= >> %LAUNCHER_SCRIPT%
echo set PYINSTALLER_CONFIG_DIR= >> %LAUNCHER_SCRIPT%
echo set PYINSTALLER_ONEFILE_TEMP_PATH= >> %LAUNCHER_SCRIPT%
echo. >> %LAUNCHER_SCRIPT%
echo :: Wait longer to ensure all processes are fully terminated >> %LAUNCHER_SCRIPT%
echo echo Waiting for system to stabilize... >> %LAUNCHER_SCRIPT%
echo timeout /t 3 /nobreak ^^> nul >> %LAUNCHER_SCRIPT%
echo. >> %LAUNCHER_SCRIPT%
echo :: Final cleanup of any remaining MEI directories >> %LAUNCHER_SCRIPT%
echo echo Performing final cleanup... >> %LAUNCHER_SCRIPT%
echo for /d %%%%d in ("%%TEMP%%\_MEI*"^) do rmdir /s /q "%%%%d" 2^^>nul >> %LAUNCHER_SCRIPT%
echo. >> %LAUNCHER_SCRIPT%
echo :: Launch with process isolation using schtasks for complete separation >> %LAUNCHER_SCRIPT%
echo echo Starting Anime Updater with process isolation... >> %LAUNCHER_SCRIPT%
echo schtasks /create /tn "AnimeUpdaterRestart" /tr "\"{current_exe_path}\"" /sc once /st 00:00 /f ^^>nul 2^^>^^&1 >> %LAUNCHER_SCRIPT%
echo schtasks /run /tn "AnimeUpdaterRestart" ^^>nul 2^^>^^&1 >> %LAUNCHER_SCRIPT%
echo timeout /t 2 /nobreak ^^> nul >> %LAUNCHER_SCRIPT%
echo schtasks /delete /tn "AnimeUpdaterRestart" /f ^^>nul 2^^>^^&1 >> %LAUNCHER_SCRIPT%
echo. >> %LAUNCHER_SCRIPT%
echo :: If schtasks failed, try direct launch as fallback >> %LAUNCHER_SCRIPT%
echo echo Fallback: Direct launch... >> %LAUNCHER_SCRIPT%
echo start "" "{current_exe_path}" >> %LAUNCHER_SCRIPT%
echo. >> %LAUNCHER_SCRIPT%
echo :: Self-destruct >> %LAUNCHER_SCRIPT%
echo timeout /t 2 /nobreak ^^> nul >> %LAUNCHER_SCRIPT%
echo del "%%~f0" >> %LAUNCHER_SCRIPT%

:: Launch the isolated launcher script with complete process separation
echo Starting isolated launcher with process separation...
echo %DATE% %TIME% - Starting isolated launcher script with schtasks >> %LOG_FILE%
start "" /min cmd /c %LAUNCHER_SCRIPT%

:: Wait a moment then clean up script
timeout /t 2 /nobreak > nul
del "%~f0"
'''
        
        script_path = os.path.join(tempfile.gettempdir(), "update_anime.bat")
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        logger.info(f"Update script created at: {script_path}")
        return script_path
    
    def _use_standalone_updater(self, new_exe_path: str, current_exe_path: str) -> bool:
        """Try to use standalone updater executable for the update process"""
        try:
            # Look for standalone updater executable
            if getattr(sys, 'frozen', False):
                # Running as frozen executable
                app_dir = os.path.dirname(sys.executable)
            else:
                # Running from source
                app_dir = os.path.dirname(os.path.abspath(__file__))
                app_dir = os.path.dirname(os.path.dirname(app_dir))  # Go up to project root
            
            # Try different possible locations for standalone updater
            possible_updater_locations = [
                os.path.join(app_dir, "updater.exe"),
                os.path.join(app_dir, "standalone_updater.exe"),
                os.path.join(app_dir, "AnimeUpdater_Updater.exe"),
                os.path.join(app_dir, "ShikimoriUpdater_Updater.exe"),
                os.path.join(app_dir, "dist", "updater.exe"),
                os.path.join(app_dir, "dist", "standalone_updater.exe"),
                os.path.join(app_dir, "build", "updater.exe")
            ]
            
            updater_exe = None
            for location in possible_updater_locations:
                if os.path.exists(location):
                    updater_exe = location
                    logger.info(f"Found standalone updater at: {location}")
                    break
            
            if not updater_exe:
                logger.info("No standalone updater found, will use batch script fallback")
                return False
            
            # Launch standalone updater
            logger.info(f"Launching standalone updater: {updater_exe}")
            logger.info(f"  New EXE: {new_exe_path}")
            logger.info(f"  Target EXE: {current_exe_path}")
            
            # Launch the standalone updater with arguments
            subprocess.Popen([
                updater_exe,
                "--new-exe", new_exe_path,
                "--target-exe", current_exe_path,
                "--wait-timeout", "30"
            ])
            
            logger.info("Standalone updater launched successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to launch standalone updater: {e}")
            return False


class UpdateChecker:
    """Simplified update checker for UI integration"""
    
    def __init__(self, github_repo: str, current_version: str):
        self.updater = Updater(github_repo, current_version)
        self.update_available = False
        self.update_info = None
    
    def check_updates_async(self, callback):
        """Check for updates asynchronously"""
        def check_thread():
            try:
                self.update_available = self.updater.check_for_updates()
                if self.update_available:
                    self.update_info = self.updater.get_update_info()
                callback(self.update_available, self.update_info)
            except Exception as e:
                logger.error(f"Update check failed: {e}")
                callback(False, None)
        
        import threading
        threading.Thread(target=check_thread, daemon=True).start()
    
    def download_and_install(self, progress_callback=None):
        """Download and install update"""
        def update_thread():
            try:
                # Download
                downloaded_path = self.updater.download_update(progress_callback)
                if not downloaded_path:
                    return False
                
                # Install (this will exit the application)
                return self.updater.install_update(downloaded_path)
                
            except Exception as e:
                logger.error(f"Update installation failed: {e}")
                return False
        
        import threading
        threading.Thread(target=update_thread, daemon=True).start()
