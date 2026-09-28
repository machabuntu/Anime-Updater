#!/usr/bin/env python3
"""
Shikimori Updater - Main Application Entry Point
Tracks anime episodes from media players and updates Shikimori list
"""

import argparse
import os
import sys

# Handle both development and PyInstaller environments
def setup_path():
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller executable
        application_path = sys._MEIPASS
        src_path = os.path.join(application_path, 'src')
        # Also add the main application path
        if application_path not in sys.path:
            sys.path.insert(0, application_path)
    else:
        # Running as script
        application_path = os.path.dirname(os.path.abspath(__file__))
        src_path = os.path.join(application_path, 'src')
        # Add both the main directory and src directory
        if application_path not in sys.path:
            sys.path.insert(0, application_path)

    if src_path not in sys.path:
        sys.path.insert(0, src_path)

setup_path()

# Initialize logging first
try:
    from utils.logger import get_logger
    logger = get_logger('main')
except ImportError as e:
    print(f"Failed to import logger: {e}")
    import logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger('main')


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog='anime-updater',
        description='Track anime and manga progress on Shikimori or MyAnimeList.',
        add_help=True,
    )
    parser.add_argument(
        '--gallery',
        action='store_true',
        help='Open the Qt style gallery (development aid).',
    )
    parser.add_argument(
        '--self-test',
        action='store_true',
        help='Build the interface, then exit. Used to smoke test a build.',
    )
    args, _unknown = parser.parse_known_args(argv)
    return args


def report_fatal_error(message):
    """Show a startup failure to the user with whatever toolkit is available."""
    logger.error(message)
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(None, 'Anime Updater', message)
    except Exception:
        print(message, file=sys.stderr)


def main():
    """Main application entry point"""
    args = parse_args()

    try:
        logger.info("Starting Shikimori Updater application")

        from core.config import Config
        config = Config()

        from ui import app as qt_app

        if args.gallery:
            return qt_app.run_gallery()

        if args.self_test:
            return qt_app.run_self_test(config)

        return qt_app.run(config)

    except Exception as e:
        logger.exception("Failed to start application")
        report_fatal_error(f"Failed to start application: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
