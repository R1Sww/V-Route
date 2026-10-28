"""Driverless per-application proxy launcher.

The old implementation tried to rewrite WinDivert socket events.  That
requires a system driver and cannot reinject socket-layer events safely.  This
engine intentionally has no native hooks, services, elevation or global proxy
changes: it launches selected applications with a private proxy environment
and Chromium-compatible command-line options.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .launcher import build_proxy_environment, command_for_entry


class Engine(QObject):
    """Owns only child processes started by this application."""

    state_changed = Signal(bool)
    stats = Signal(int, int)  # launched processes, reserved for UI compatibility
    error = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._lock = threading.RLock()
        self._targets: list = []
        self._params = ("SOCKS5", "127.0.0.1", 2080)
        self._processes: list[subprocess.Popen] = []
        self.running = False

    def is_running(self) -> bool:
        with self._lock:
            self._reap_finished_locked()
            return self.running

    def set_targets(self, paths) -> None:
        with self._lock:
            self._targets = list(paths or [])

    def set_params(self, proto: str, host: str, port: int) -> None:
        with self._lock:
            self._params = (str(proto), str(host), int(port))

    def start(self) -> None:
        with self._lock:
            self._reap_finished_locked()
            if self.running:
                return
            targets = list(self._targets)
            params = self._params
        if not targets:
            self.error.emit("Не выбраны приложения для запуска")
            return

        env = build_proxy_environment(*params)
        launched: list[subprocess.Popen] = []
        try:
            for target in targets:
                command, cwd = command_for_entry(str(target), params)
                if not command:
                    continue
                child_env = os.environ.copy()
                child_env.update(env)
                creationflags = 0
                if sys.platform == "win32":
                    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
                launched.append(subprocess.Popen(
                    command,
                    cwd=cwd,
                    env=child_env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=creationflags,
                    shell=False,
                ))
        except (OSError, ValueError) as exc:
            for process in launched:
                self._terminate_process(process)
            self.error.emit(f"Не удалось запустить приложение: {exc}")
            return

        if not launched:
            self.error.emit("Не найдено ни одного запускаемого приложения")
            return
        with self._lock:
            self._processes = launched
            self.running = True
        self.state_changed.emit(True)
        self.stats.emit(len(launched), 0)

    def stop(self) -> None:
        with self._lock:
            processes = list(self._processes)
            self._processes.clear()
            was_running = self.running
            self.running = False
        for process in processes:
            self._terminate_process(process)
        if was_running:
            self.state_changed.emit(False)
        self.stats.emit(0, 0)

    def refresh(self) -> None:
        with self._lock:
            was_running = self.running
            self._reap_finished_locked()
            count = len(self._processes)
            running = was_running and count > 0
            if was_running and count == 0:
                self.running = False
        if was_running and count == 0:
            self.state_changed.emit(False)
        elif running:
            self.stats.emit(count, 0)

    def _reap_finished_locked(self) -> None:
        self._processes = [p for p in self._processes if p.poll() is None]

    @staticmethod
    def _terminate_process(process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return
        try:
            if sys.platform == "win32":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                process.terminate()
            process.wait(timeout=1.5)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            try:
                process.kill()
                process.wait(timeout=1.0)
            except (OSError, ValueError, subprocess.TimeoutExpired):
                pass


def test_proxy(host: str, port: int, timeout: float = 1.2) -> bool:
    """Check that the configured proxy accepts a TCP connection."""
    import socket

    if not host:
        return False
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False
