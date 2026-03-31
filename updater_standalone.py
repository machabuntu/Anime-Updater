#!/usr/bin/env python3
"""
Standalone updater for Anime Updater
This is compiled as a separate executable to avoid MEI folder conflicts
"""

import os
import sys
import time
import shutil
import subprocess
import tempfile
import argparse
import urllib.request
import urllib.error
import json
from pathlib import Path

def shutdown_app_via_api(timeout=30):
    """Shutdown the application via API endpoint"""
    api_url = "http://localhost:5000/api/shutdown"
    
    print(f"Sending shutdown request to API: {api_url}")
    
    try:
        # Create shutdown request
        request = urllib.request.Request(
            api_url,
            data=json.dumps({}).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'AnimeUpdater-StandaloneUpdater/1.0'
            },
            method='POST'
        )
        
        # Send shutdown request
        with urllib.request.urlopen(request, timeout=10) as response:
            response_data = response.read().decode('utf-8')
            print(f"API response: {response_data}")
            print("Shutdown request sent successfully")
            
    except urllib.error.URLError as e:
        print(f"Failed to connect to API (application may already be closed): {e}")
        return True  # Assume app is already closed
    except Exception as e:
        print(f"Error sending shutdown request: {e}")
        return False
    
    return True

def wait_for_process_exit(exe_path, timeout=30):
    """Wait for the main application to exit"""
    exe_name = os.path.basename(exe_path)
    
    print(f"Waiting for {exe_name} to exit...")
    
    for _ in range(timeout):
        try:
            # Check if process is still running
            result = subprocess.run(
                ['tasklist', '/fi', f'imagename eq {exe_name}'],
                capture_output=True,
                text=True
            )
            
            if exe_name not in result.stdout:
                print(f"{exe_name} has exited")
                return True
                
        except Exception as e:
            print(f"Error checking process: {e}")
            
        time.sleep(1)
    
    print(f"Timeout waiting for {exe_name} to exit")
    return False

def update_executable(new_exe_path, target_exe_path):
    """Replace the target executable with the new one"""
    print(f"Updating executable:")
    print(f"  Source: {new_exe_path}")
    print(f"  Target: {target_exe_path}")
    
    # Create backup
    backup_path = f"{target_exe_path}.backup"
    try:
        shutil.copy2(target_exe_path, backup_path)
        print(f"Backup created: {backup_path}")
    except Exception as e:
        print(f"Warning: Could not create backup: {e}")
    
    # Replace executable
    try:
        shutil.copy2(new_exe_path, target_exe_path)
        print("Executable updated successfully")
        
        # Clean up backup
        if os.path.exists(backup_path):
            os.remove(backup_path)
            
        return True
        
    except Exception as e:
        print(f"Failed to update executable: {e}")
        
        # Try to restore backup
        if os.path.exists(backup_path):
            try:
                shutil.copy2(backup_path, target_exe_path)
                print("Backup restored")
                os.remove(backup_path)
            except Exception as restore_e:
                print(f"Failed to restore backup: {restore_e}")
        
        return False

def restart_application(exe_path):
    """Restart the application with complete process isolation"""
    print(f"Restarting application: {exe_path}")
    
    # Wait a moment for system to stabilize
    time.sleep(2)
    
    try:
        # Use subprocess.Popen with complete isolation
        subprocess.Popen(
            [exe_path],
            cwd=os.path.dirname(exe_path),
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
        print("Application restarted successfully")
        return True
        
    except Exception as e:
        print(f"Failed to restart application: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Standalone updater for Anime Updater')
    parser.add_argument('--new-exe', required=True, help='Path to the new executable')
    parser.add_argument('--target-exe', required=True, help='Path to the target executable to replace')
    parser.add_argument('--wait-timeout', type=int, default=30, help='Timeout in seconds to wait for process exit')
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("Anime Updater - Standalone Updater")
    print("=" * 50)
    
    # Validate paths
    if not os.path.exists(args.new_exe):
        print(f"Error: New executable not found: {args.new_exe}")
        return 1
    
    if not os.path.exists(args.target_exe):
        print(f"Error: Target executable not found: {args.target_exe}")
        return 1
    
    # Shutdown the application via API
    print("Step 1: Shutting down application via API...")
    if not shutdown_app_via_api():
        print("Failed to shutdown via API, application may already be closed")
    
    # Wait for main application to exit
    print("Step 2: Waiting for application to exit...")
    if not wait_for_process_exit(args.target_exe, args.wait_timeout):
        print("Warning: Main application may still be running")
    
    # Additional wait to ensure process is fully terminated
    print("Step 3: Waiting for system to stabilize...")
    time.sleep(3)
    
    # Update the executable
    if not update_executable(args.new_exe, args.target_exe):
        print("Update failed!")
        input("Press Enter to exit...")
        return 1
    
    # Clean up the new executable
    try:
        os.remove(args.new_exe)
        print(f"Cleaned up temporary file: {args.new_exe}")
    except Exception as e:
        print(f"Warning: Could not clean up temporary file: {e}")
    
    # Restart the application
    if not restart_application(args.target_exe):
        print("Failed to restart application")
        print("Please start the application manually")
        input("Press Enter to exit...")
        return 1
    
    print("Update completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
