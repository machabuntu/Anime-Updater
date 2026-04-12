#!/usr/bin/env python3
"""
Standalone updater for Anime Updater — Linux
Compiled as a separate binary to avoid PyInstaller _MEI temp-folder conflicts.

Usage:
  updater_linux --new-exe /tmp/anime-updater_4.1.0 --target-exe /opt/anime-updater/anime-updater
"""

import os
import sys
import time
import shutil
import subprocess
import argparse
import urllib.request
import urllib.error
import json
from pathlib import Path

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def shutdown_app_via_api(timeout: int = 30) -> bool:
    """Ask the running application to shut down via its local HTTP API."""
    api_url = "http://localhost:5000/api/shutdown"
    print(f"Sending shutdown request to {api_url}")
    try:
        request = urllib.request.Request(
            api_url,
            data=json.dumps({}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "AnimeUpdater-StandaloneUpdater/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            print(f"API response: {response.read().decode('utf-8')}")
            print("Shutdown request sent successfully")
    except urllib.error.URLError as exc:
        print(f"Could not reach API (app may already be closed): {exc}")
        return True  # treat as already closed
    except Exception as exc:
        print(f"Error sending shutdown request: {exc}")
        return False
    return True


def wait_for_process_exit(exe_path: str, timeout: int = 30) -> bool:
    """Wait until no process running *exe_path* is alive."""
    exe_name = os.path.basename(exe_path)
    print(f"Waiting for {exe_name} to exit…")

    for _ in range(timeout):
        running = False
        if HAS_PSUTIL:
            for proc in psutil.process_iter(["exe", "name"]):
                try:
                    proc_exe = proc.info.get("exe") or ""
                    if proc_exe == exe_path or proc.info.get("name") == exe_name:
                        running = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        else:
            # Fallback: parse `ps aux` output
            try:
                result = subprocess.run(
                    ["ps", "aux"],
                    capture_output=True,
                    text=True,
                )
                running = exe_name in result.stdout
            except Exception:
                pass

        if not running:
            print(f"{exe_name} has exited")
            return True
        time.sleep(1)

    print(f"Timeout waiting for {exe_name} to exit")
    return False


def update_executable(new_bin_path: str, target_bin_path: str) -> bool:
    """Replace *target_bin_path* with *new_bin_path*, creating a backup first."""
    print(f"Updating binary:")
    print(f"  Source : {new_bin_path}")
    print(f"  Target : {target_bin_path}")

    backup_path = f"{target_bin_path}.backup"
    try:
        shutil.copy2(target_bin_path, backup_path)
        print(f"Backup created: {backup_path}")
    except Exception as exc:
        print(f"Warning: could not create backup: {exc}")

    try:
        shutil.copy2(new_bin_path, target_bin_path)
        os.chmod(target_bin_path, 0o755)
        print("Binary updated and marked executable")

        if os.path.exists(backup_path):
            os.remove(backup_path)
        return True

    except Exception as exc:
        print(f"Failed to update binary: {exc}")
        if os.path.exists(backup_path):
            try:
                shutil.copy2(backup_path, target_bin_path)
                os.chmod(target_bin_path, 0o755)
                print("Backup restored")
                os.remove(backup_path)
            except Exception as restore_exc:
                print(f"Failed to restore backup: {restore_exc}")
        return False


def restart_application(exe_path: str) -> bool:
    """Restart the application in a fully detached process."""
    print(f"Restarting application: {exe_path}")
    time.sleep(2)
    try:
        subprocess.Popen(
            [exe_path],
            cwd=os.path.dirname(exe_path) or "/",
            start_new_session=True,
        )
        print("Application restarted successfully")
        return True
    except Exception as exc:
        print(f"Failed to restart application: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Standalone updater for Anime Updater (Linux)"
    )
    parser.add_argument("--new-exe", required=True, help="Path to the new binary")
    parser.add_argument("--target-exe", required=True, help="Path to the binary to replace")
    parser.add_argument(
        "--wait-timeout", type=int, default=30,
        help="Seconds to wait for the application to exit",
    )
    args = parser.parse_args()

    print("=" * 50)
    print("Anime Updater — Standalone Updater (Linux)")
    print("=" * 50)

    if not os.path.exists(args.new_exe):
        print(f"Error: new binary not found: {args.new_exe}")
        return 1
    if not os.path.exists(args.target_exe):
        print(f"Error: target binary not found: {args.target_exe}")
        return 1

    print("Step 1: Shutting down application via API…")
    shutdown_app_via_api()

    print("Step 2: Waiting for application to exit…")
    if not wait_for_process_exit(args.target_exe, args.wait_timeout):
        print("Warning: application may still be running, proceeding anyway")

    print("Step 3: Waiting for system to stabilise…")
    time.sleep(2)

    print("Step 4: Installing update…")
    if not update_executable(args.new_exe, args.target_exe):
        print("Update failed!")
        return 1

    print("Step 5: Cleaning up temporary file…")
    try:
        os.remove(args.new_exe)
        print(f"Removed: {args.new_exe}")
    except Exception as exc:
        print(f"Warning: could not remove temporary file: {exc}")

    print("Step 6: Restarting application…")
    if not restart_application(args.target_exe):
        print("Failed to restart application — please start it manually")
        return 1

    print("Update completed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
