"""Persistent application settings for V-Route."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .theme import DEFAULT_ACCENT, normalize_accent

APP_DIR_NAME = "V-Route"
VALID_PROTOS = ("HTTP", "HTTPS", "SOCKS4", "SOCKS5")


def config_file() -> Path:
    base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    directory = base / APP_DIR_NAME
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        directory = Path.cwd() / ".vroute-data"
        directory.mkdir(parents=True, exist_ok=True)
    return directory / "config.json"


@dataclass
class Config:
    host: str = "127.0.0.1"
    port: int = 2080
    proto: str = "HTTP"
    theme: str = "dark"
    accent: str = DEFAULT_ACCENT
    selected: list = field(default_factory=list)
    folders: list = field(default_factory=list)
    manual_apps: list = field(default_factory=list)

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or config_file()
        cfg = cls()
        if not path.exists():
            return cfg
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return cfg
        if not isinstance(data, dict):
            return cfg
        host = data.get("host")
        if isinstance(host, str) and host.strip():
            cfg.host = host.strip()
        try:
            port = int(data.get("port", cfg.port))
            if 0 < port < 65536:
                cfg.port = port
        except (TypeError, ValueError):
            pass
        proto = str(data.get("proto", cfg.proto)).upper()
        if proto in VALID_PROTOS:
            cfg.proto = proto
        # V-Route deliberately uses one dark graphite theme.  Old config files
        # may still contain "light", but it is ignored and normalized here.
        cfg.theme = "dark"
        cfg.accent = normalize_accent(str(data.get("accent", DEFAULT_ACCENT)))
        sel = data.get("selected")
        if isinstance(sel, list):
            cfg.selected = [x.strip() for x in sel if isinstance(x, str) and x.strip()]
        folders = data.get("folders")
        if isinstance(folders, list):
            cfg.folders = [x.strip() for x in folders if isinstance(x, str) and x.strip()]
        manual = data.get("manual_apps")
        if isinstance(manual, list):
            cfg.manual_apps = [
                {"name": str(m.get("name", "")).strip(),
                 "path": str(m.get("path", "")).strip()}
                for m in manual if isinstance(m, dict)
                and isinstance(m.get("path"), str) and m.get("path", "").strip()
            ]
        return cfg

    def save(self, path: Path | None = None) -> None:
        path = path or config_file()
        payload = {
            "host": self.host,
            "port": self.port,
            "proto": self.proto,
            "theme": "dark",
            "accent": self.accent,
            "selected": list(self.selected),
            "folders": list(self.folders),
            "manual_apps": list(self.manual_apps),
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, path)
        except Exception:
            try:
                tmp.unlink(missing_ok=True)
            except (NameError, OSError):
                pass
