"""Discovering installed applications (Start Menu shortcuts, desktop, custom folders)."""

from __future__ import annotations

import locale
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

_SKIP_STEMS = re.compile(
    r"^(unins\d*|uninstall.*|setup.*|install.*|update|downloader|crashpad)$", re.I
)

_SKIP_DIRS = {
    "$recycle.bin", "system volume information", "recovery",
    "windowsapps", "$winreagent", ".git", "node_modules",
}


@dataclass
class AppEntry:
    name: str
    path: str
    args: str = ""
    source: str = "start_menu"
    is_lnk: bool = False

    @property
    def key(self) -> str:
        return self.path.lower()


def shortcut_roots() -> list[str]:
    env = os.environ
    candidates = []
    if env.get("APPDATA"):
        candidates.append(Path(env["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs")
    if env.get("ProgramData"):
        candidates.append(Path(env["ProgramData"]) / "Microsoft/Windows/Start Menu/Programs")
    if env.get("USERPROFILE"):
        candidates.append(Path(env["USERPROFILE"]) / "Desktop")
    if env.get("PUBLIC"):
        candidates.append(Path(env["PUBLIC"]) / "Public Desktop")
    return [str(p) for p in candidates if p.exists()]


def _decode(data: bytes) -> str:
    if not data:
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return data.decode(locale.getpreferredencoding(False))
        except Exception:
            return data.decode("utf-8", errors="replace")


def _resolve_shortcuts(roots: list[str], timeout: float = 25.0) -> dict[str, tuple[str, str, str]]:
    """lnk path (lower) -> (lnk path, target path, arguments); {} on failure."""
    if not roots:
        return {}
    root_list = ", ".join("'" + r.replace("'", "''") + "'" for r in roots)
    script = (
        "$ErrorActionPreference = 'SilentlyContinue'\n"
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n"
        "$ws = New-Object -ComObject WScript.Shell\n"
        f"$roots = @({root_list})\n"
        "foreach ($root in $roots) {\n"
        "  if (-not (Test-Path -LiteralPath $root)) { continue }\n"
        "  Get-ChildItem -LiteralPath $root -Recurse -Filter '*.lnk' -File "
        "-ErrorAction SilentlyContinue | ForEach-Object {\n"
        "    try {\n"
        "      $s = $ws.CreateShortcut($_.FullName)\n"
        "      $t = [string]$s.TargetPath\n"
        "      if ($t -ne '') { "
        "Write-Output ($_.FullName + [char]9 + $t + [char]9 + [string]$s.Arguments) }\n"
        "    } catch { }\n"
        "  }\n"
        "}\n"
    )
    tmp = Path(tempfile.gettempdir()) / f"vroute_scan_{os.getpid()}.ps1"
    result: dict[str, tuple[str, str, str]] = {}
    try:
        tmp.write_text(script, encoding="utf-8-sig")
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-File", str(tmp)],
            capture_output=True, timeout=timeout, creationflags=_NO_WINDOW,
        )
        for line in _decode(proc.stdout).splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                lnk, target = parts[0].strip(), parts[1].strip()
                args = parts[2].strip() if len(parts) > 2 else ""
                if lnk and target:
                    result[lnk.lower()] = (lnk, target, args)
    except Exception:
        return {}
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
    return result


def _iter_lnks(roots: list[str]):
    for root in roots:
        try:
            yield from Path(root).rglob("*.lnk")
        except OSError:
            continue


def scan_folders(folders: list[str], per_limit: int = 500) -> list[AppEntry]:
    entries: list[AppEntry] = []
    for folder in folders:
        base = Path(folder)
        if not base.is_dir():
            continue
        count = 0
        for root, dirs, files in os.walk(base, onerror=lambda _e: None):
            rel = Path(root).relative_to(base)
            if len(rel.parts) >= 6:
                dirs[:] = []
                continue
            dirs[:] = [d for d in dirs if d.lower() not in _SKIP_DIRS and not d.startswith("$")]
            for fname in files:
                if not fname.lower().endswith(".exe"):
                    continue
                stem = Path(fname).stem
                if _SKIP_STEMS.match(stem):
                    continue
                entries.append(AppEntry(name=stem, path=str(Path(root) / fname), source="folder"))
                count += 1
                if count >= per_limit:
                    break
            if count >= per_limit:
                break
    return entries


def scan_all(folders: list[str] | None = None, shortcut_timeout: float = 25.0) -> list[AppEntry]:
    folders = list(folders or [])
    roots = shortcut_roots()
    resolved = _resolve_shortcuts(roots, timeout=max(0.1, shortcut_timeout))
    entries: dict[str, AppEntry] = {}

    for _key, (_lnk, target, args) in resolved.items():
        name = Path(_lnk).stem
        if _SKIP_STEMS.match(name):
            continue
        tgt = Path(target)
        if tgt.suffix.lower() != ".exe" or not tgt.is_file():
            continue
        entry = AppEntry(name=name, path=str(tgt), args=args, source="start_menu")
        entries.setdefault(entry.key, entry)

    if not resolved:
        # Shortcut resolution failed — expose .lnk files as-is (launched through the shell).
        for lnk in _iter_lnks(roots):
            if _SKIP_STEMS.match(lnk.stem):
                continue
            entry = AppEntry(name=lnk.stem, path=str(lnk), source="start_menu", is_lnk=True)
            entries.setdefault(entry.key, entry)

    for entry in scan_folders(folders):
        entries.setdefault(entry.key, entry)

    result = sorted(entries.values(), key=lambda e: e.name.lower())
    return result[:1200]


def find_exe(name: str, time_budget: float = 10.0) -> str | None:
    """Resolve 'app.exe' (or a bare program name) to a full path.

    Order: literal path -> PATH -> Start Menu shortcuts -> common install roots.
    """
    if not name:
        return None
    name = name.strip().strip('"')
    if not name:
        return None
    if (os.sep in name or "/" in name) and Path(name).is_file():
        return str(Path(name).resolve())
    low = name.lower()
    if not low.endswith(".exe"):
        low += ".exe"
    import shutil

    hit = shutil.which(name)
    if not hit and not name.lower().endswith(".exe"):
        hit = shutil.which(name + ".exe")
    if hit:
        return hit
    deadline = time.monotonic() + time_budget
    try:
        remaining = max(0.1, deadline - time.monotonic())
        for entry in scan_all([], shortcut_timeout=remaining):
            if time.monotonic() > deadline:
                break
            if Path(entry.path).name.lower() == low:
                return entry.path
    except Exception:
        pass
    env = os.environ
    roots = []
    for var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramData",
                "ProgramW6432"):
        value = env.get(var)
        if value:
            roots.append(Path(value))
    for var in ("LOCALAPPDATA", "APPDATA"):
        value = env.get(var)
        if value:
            roots.append(Path(value) / "Programs")
            roots.append(Path(value))
    roots.extend([Path("C:/Windows"), Path("C:/Windows/System32")])
    best = None
    for root in roots:
        if not root.is_dir() or time.monotonic() > deadline:
            continue
        try:
            for dirpath, dirnames, files in os.walk(root, onerror=lambda _e: None):
                if time.monotonic() > deadline:
                    break
                rel = Path(dirpath).relative_to(root)
                if len(rel.parts) >= 4:
                    dirnames[:] = []
                    continue
                dirnames[:] = [
                    d for d in dirnames
                    if d.lower() not in _SKIP_DIRS and not d.startswith("$")
                ]
                for f in files:
                    if f.lower() == low:
                        candidate = str(Path(dirpath) / f)
                        if best is None or len(candidate) < len(best):
                            best = candidate
                if best:
                    break
        except OSError:
            continue
        if best:
            break
    return best
