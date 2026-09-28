"""
API client factory.

Which service is active is a configuration detail, so the rest of the
application asks for a client instead of importing a concrete one.
"""

from __future__ import annotations

SERVICE_SHIKIMORI = 'shikimori'
SERVICE_MAL = 'mal'

SERVICE_LABELS = {
    SERVICE_SHIKIMORI: 'Shikimori',
    SERVICE_MAL: 'MyAnimeList',
}


def create_client(config):
    """Build the API client for the service selected in config."""
    if config.get('service.active', SERVICE_SHIKIMORI) == SERVICE_MAL:
        from api.mal_client import MALClient
        return MALClient(config)

    from api.shikimori_client import ShikimoriClient
    return ShikimoriClient(config)


def service_label(service_key: str) -> str:
    """Human readable name for a service key."""
    return SERVICE_LABELS.get(service_key, service_key)
