"""
User-configured proxy for all outgoing HTTP requests.

Reads proxy settings from the application config (type / host / port /
optional credentials) and returns a dict suitable for ``requests``.

Usage::

    from utils.proxy import get_proxies

    proxies = get_proxies(config)
    session = requests.Session()
    session.proxies.update(proxies)
"""

from typing import Dict


def get_proxies(config) -> Dict[str, str]:
    """Build a ``{scheme: url}`` proxy dict from application config."""
    proxy_type = config.get('proxy.type', 'none')
    if proxy_type == 'none':
        return {}

    host = config.get('proxy.host', '').strip()
    port = config.get('proxy.port', '').strip()
    if not host or not port:
        return {}

    scheme = "socks5h" if proxy_type == "socks5" else "http"

    auth = ""
    user = config.get('proxy.username', '').strip()
    pwd = config.get('proxy.password', '').strip()
    if user:
        auth = f"{user}:{pwd}@" if pwd else f"{user}@"

    url = f"{scheme}://{auth}{host}:{port}"
    return {"http": url, "https": url}
