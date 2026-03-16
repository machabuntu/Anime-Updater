"""
Version management for Anime Updater
"""

# Application version
__version__ = "3.2.8"

# GitHub repository for updates
GITHUB_REPO = "machabuntu/Anime-Updater"

# Build information
BUILD_DATE = "2025-09-26"
BUILD_NUMBER = "1"

def get_version() -> str:
    """Get the current version string"""
    return __version__

def get_version_info() -> dict:
    """Get detailed version information"""
    return {
        'version': __version__,
        'github_repo': GITHUB_REPO,
        'build_date': BUILD_DATE,
        'build_number': BUILD_NUMBER
    }
