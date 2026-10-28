"""V-Route entry point: `python main.py` (or the built V-Route.exe).

Flags:
    --selftest              run headless self-checks and exit
    --screenshot <path>     render the UI (after startup scan) and save a PNG
    --theme dark             kept for compatibility; the app is always dark
"""

from __future__ import annotations

import ctypes
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from vroute import theme as T
from vroute.config import Config


def _set_app_id() -> None:
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("VRoute.launcher")
    except Exception:
        pass


def selftest() -> int:
    from vroute import engine, launcher, scanner

    failures: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
        if not cond:
            failures.append(name)

    try:
        dark_theme = T.build_theme(True, "#4C7DFF")
        q1 = T.build_qss(dark_theme)
        check("dark theme build", dark_theme.key == "dark" and dark_theme.bg in q1 and len(q1) > 1000)
    except Exception as exc:
        check("themes build", False, str(exc))

    check("accent presets", len(T.PRESETS) == 10)
    t = T.build_theme(True, "#18181B")
    check("black accent clamped on dark", T.luminance(t.primary) > 0.2,
          f"-> {t.primary}")
    t = T.build_theme(True, "#F8FAFC")
    check("white accent valid on dark", T.luminance(t.primary) > 0.85,
          f"-> {t.primary}")

    env = launcher.build_proxy_environment("SOCKS5", "127.0.0.1", 2080)
    check("private proxy environment", env["all_proxy"] == "socks5://127.0.0.1:2080"
          and "NO_PROXY" in env)
    check("chromium proxy url", launcher.proxy_url("HTTP", "127.0.0.1", 2080)
          == "http://127.0.0.1:2080")

    import tempfile
    tmp = Path(tempfile.gettempdir()) / "vroute_selftest.json"
    cfg = Config(host="10.0.0.1", port=9050, proto="SOCKS4", theme="dark",
                 accent="#22C55E", selected=["C:/a.exe"], folders=["C:/b"],
                 manual_apps=[{"name": "a", "path": "C:/a.exe"}])
    cfg.save(tmp)
    cfg2 = Config.load(tmp)
    check("config roundtrip",
          (cfg2.host, cfg2.port, cfg2.proto, cfg2.theme, cfg2.accent)
           == ("10.0.0.1", 9050, "SOCKS4", "dark", "#22c55e")
          and cfg2.selected == ["C:/a.exe"]
          and cfg2.manual_apps == [{"name": "a", "path": "C:/a.exe"}])
    tmp.unlink(missing_ok=True)

    roots = scanner.shortcut_roots()
    check("shortcut roots", len(roots) >= 1, f"{len(roots)} каталогов")
    try:
        entries = scanner.scan_all([])
        check("scan start menu", len(entries) > 0, f"найдено {len(entries)}")
        print("      примеры:", ", ".join(e.name for e in entries[:5]))
    except Exception as exc:
        check("scan start menu", False, str(exc))

    hit = scanner.find_exe("python.exe")
    check("find_exe python.exe", bool(hit), hit or "не найдено")

    print()
    if failures:
        print("SELFTEST FAILED:", ", ".join(failures))
        return 1
    print("SELFTEST OK")
    return 0


def _parse(argv: list[str]) -> dict:
    opts = {"selftest": False, "screenshot": None, "theme": None}
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--selftest":
            opts["selftest"] = True
        elif arg == "--screenshot" and i + 1 < len(argv):
            i += 1
            opts["screenshot"] = argv[i]
        elif arg == "--theme" and i + 1 < len(argv):
            i += 1
            opts["theme"] = argv[i]
        i += 1
    return opts


def main(argv: list[str]) -> int:
    opts = _parse(argv)

    config = Config.load()
    if opts["theme"] == "dark":
        config.theme = opts["theme"]

    app = QApplication(sys.argv)
    app.setApplicationName("V-Route")
    app.setApplicationDisplayName("V-Route")
    font = QFont()
    font.setFamilies(["Roboto", "Segoe UI Variable Text", "Segoe UI", "Arial"])
    font.setPointSize(10)
    app.setFont(font)
    _set_app_id()
    T.apply(app, config.theme, config.accent)

    if opts["selftest"]:
        return selftest()

    from vroute.mainwindow import MainWindow

    screenshot = opts["screenshot"]
    win = MainWindow(
        config,
        persist=screenshot is None,
        animate=screenshot is None,
        demo_select=3 if screenshot else 0,
    )
    win.show()

    if screenshot:
        state = {"done": False}

        def capture() -> None:
            if state["done"]:
                return
            state["done"] = True
            path = Path(screenshot)
            path.parent.mkdir(parents=True, exist_ok=True)
            ok = win.grab().save(str(path), "PNG")
            print(f"screenshot {'saved' if ok else 'FAILED'}: {path}")
            app.quit()

        win.scanned.connect(lambda: QTimer.singleShot(800, capture))
        QTimer.singleShot(4500, capture)
        QTimer.singleShot(10000, capture)
        return app.exec()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
