"""Private per-process proxy configuration for Windows applications."""

from __future__ import annotations

import os
import shlex
from pathlib import Path


def proxy_url(proto: str, host: str, port: int) -> str:
    scheme = str(proto).upper()
    if scheme == "SOCKS4":
        scheme = "socks4"
    elif scheme == "SOCKS5":
        scheme = "socks5"
    else:
        scheme = "http"
    return f"{scheme}://{host}:{int(port)}"


def build_proxy_environment(proto: str, host: str, port: int) -> dict[str, str]:
    """Return variables applied only to children launched by V-Route."""
    url = proxy_url(proto, host, port)
    bypass = "localhost,127.0.0.1,::1"
    values = {
        "http_proxy": url,
        "https_proxy": url,
        "all_proxy": url,
        "no_proxy": bypass,
        "HTTP_PROXY": url,
        "HTTPS_PROXY": url,
        "ALL_PROXY": url,
        "NO_PROXY": bypass,
        # Common aliases used by native and Java-based clients.
        "http_proxy_host": str(host),
        "http_proxy_port": str(int(port)),
    }
    # curl intentionally only trusts lowercase http_proxy; remove the unsafe
    # CGI-sensitive uppercase variant from the inherited environment.
    values["HTTP_PROXY"] = url
    return values


def _is_chromium(path: Path) -> bool:
    name = path.stem.lower()
    return any(token in name for token in (
        "chrome", "msedge", "brave", "opera", "vivaldi", "yandex",
    ))


def command_for_entry(raw_path: str, params: tuple[str, str, int]):
    """Create a safe argv list and working directory for one selected target."""
    path = Path(raw_path.strip().strip('"')).expanduser()
    if not path.is_file():
        return None, None
    if path.suffix.lower() != ".exe":
        return None, None
    command = [str(path)]
    if _is_chromium(path):
        _proto, host, port = params
        command.extend([
            f"--proxy-server={proxy_url(_proto, host, port)}",
            "--proxy-bypass-list=<-loopback>;localhost;127.0.0.1;::1",
        ])
    return command, str(path.parent)
