"""Main application window for V-Route."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    Qt,
    QThread,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QIcon, QIntValidator
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from . import engine as engine_mod
from . import icons, scanner, theme as T
from .config import Config
from .widgets import (
    AccentPicker,
    AppRow,
    ProxyToggle,
    RefreshButton,
    SearchField,
    SegmentedControl,
    Snackbar,
    StatusChip,
)


class ScanWorker(QThread):
    done = Signal(object)

    def __init__(self, folders: list, parent=None) -> None:
        super().__init__(parent)
        self.folders = list(folders)

    def run(self) -> None:
        try:
            entries = scanner.scan_all(self.folders)
        except Exception:
            entries = []
        self.done.emit(entries)


class TestWorker(QThread):
    done = Signal(bool)

    def __init__(self, host: str, port: int, parent=None) -> None:
        super().__init__(parent)
        self.host = host
        self.port = port

    def run(self) -> None:
        try:
            result = engine_mod.test_proxy(self.host, self.port, 1.2)
        except Exception:
            result = False
        self.done.emit(result)


class Root(QWidget):
    """Central widget that keeps floating overlays anchored to corners."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("root")
        self._right: list[QWidget] = []
        self._left: list[QWidget] = []

    def add_overlay(self, widget: QWidget, side: str) -> None:
        (self._right if side == "right" else self._left).append(widget)

    def recalc_overlays(self) -> None:
        m = 26
        for w in self._right:
            pos = self.width() - m - w.width(), self.height() - m - w.height()
            if hasattr(w, "set_home"):
                w.set_home(QPointF(*pos))
            w.move(*pos)
        for w in self._left:
            pos = m, self.height() - m - w.height()
            if hasattr(w, "set_home"):
                w.set_home(QPointF(*pos))
            w.move(*pos)

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self.recalc_overlays()


class MainWindow(QMainWindow):
    """Main window: connection settings on top, application picker below."""

    scanned = Signal()

    def __init__(self, config: Config, persist: bool = True, animate: bool = True,
                 demo_select: int = 0, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.persist = persist
        self.animate = animate
        self.demo_select = demo_select
        self.rows: dict[str, AppRow] = {}
        self.entries: list = []
        self._scan_worker = None
        self._test_worker = None
        self._shadows: list = []
        self._theme_anims: list = []
        self._pending_folder_msg = False

        self.engine = engine_mod.Engine(self)
        self.engine.state_changed.connect(self._on_engine_state)
        self.engine.stats.connect(self._on_engine_stats)
        self.engine.error.connect(self._on_engine_error)
        self._engine_timer = QTimer(self)
        self._engine_timer.setInterval(1000)
        self._engine_timer.timeout.connect(self.engine.refresh)
        self._engine_timer.start()

        self.setWindowTitle("V-Route")
        self.setMinimumSize(1020, 620)
        self.resize(1180, 780)
        self.setWindowIcon(QIcon(icons.render_logo(64)))

        self.root = Root()
        self.setCentralWidget(self.root)
        self._main_lay = QVBoxLayout(self.root)
        self._main_lay.setContentsMargins(26, 16, 26, 18)
        self._main_lay.setSpacing(14)

        self._build_header()
        self._build_connection_card()
        self._build_apps_card()
        self._build_overlays()

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(600)
        self._save_timer.timeout.connect(self._save)

        self._update_subtitle()
        self._update_count()
        self.start_scan()
        QTimer.singleShot(700, self.start_proxy_test)

    # ------------------------------------------------------------------ layout
    def _add_shadow(self, widget: QWidget, blur: int = 26, dy: int = 8) -> None:
        eff = QGraphicsDropShadowEffect(widget)
        eff.setBlurRadius(blur)
        eff.setOffset(0, dy)
        eff.setColor(QColor(0, 0, 0, T.CURRENT.shadow_alpha))
        widget.setGraphicsEffect(eff)
        self._shadows.append(eff)

    def _build_header(self) -> None:
        head = QHBoxLayout()
        head.setSpacing(14)
        left = QVBoxLayout()
        left.setSpacing(1)
        title = QLabel("V-ROUTE")
        title.setObjectName("appTitle")
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("appSubtitle")
        left.addWidget(title)
        left.addWidget(self.subtitle)
        head.addLayout(left)
        head.addStretch(1)
        self.accent_picker = AccentPicker(self.config.accent)
        self.accent_picker.accent_changed.connect(self._on_accent_changed)
        head.addWidget(self.accent_picker, 0, Qt.AlignmentFlag.AlignVCenter)
        self._main_lay.addLayout(head)

    def _build_connection_card(self) -> None:
        card = QFrame()
        card.setObjectName("card")
        self._add_shadow(card)
        self._main_lay.addWidget(card)
        outer = QHBoxLayout(card)
        outer.setContentsMargins(20, 14, 20, 16)
        outer.setSpacing(14)

        form = QHBoxLayout()
        form.setSpacing(14)

        def field(label_text: str, widget: QWidget) -> QVBoxLayout:
            box = QVBoxLayout()
            box.setSpacing(6)
            lab = QLabel(label_text)
            lab.setObjectName("fieldLabel")
            box.addWidget(lab)
            box.addWidget(widget)
            return box

        self.host_edit = QLineEdit(self.config.host)
        self.host_edit.setPlaceholderText("127.0.0.1")
        self.host_edit.setFixedHeight(44)
        self.host_edit.setMinimumWidth(160)
        self.port_edit = QLineEdit(str(self.config.port))
        self.port_edit.setValidator(QIntValidator(1, 65535, self))
        self.port_edit.setPlaceholderText("2080")
        self.port_edit.setFixedHeight(44)
        self.port_edit.setFixedWidth(120)
        proto_names = ["HTTP", "HTTPS", "SOCKS4", "SOCKS5"]
        idx = proto_names.index(self.config.proto) if self.config.proto in proto_names else 0
        self.type_seg = SegmentedControl(proto_names, current=idx)
        self.type_seg.setFixedHeight(44)

        form.addLayout(field("ХОСТ", self.host_edit), 3)
        form.addLayout(field("ПОРТ", self.port_edit), 1)
        form.addLayout(field("ТИП СОЕДЕНЕНИЯ", self.type_seg), 0)
        form.addStretch(1)

        right = QHBoxLayout()
        right.setSpacing(10)
        self.chip = StatusChip()
        self.test_btn = QPushButton("Проверить")
        self.test_btn.setObjectName("textButton")
        self.test_btn.clicked.connect(self.start_proxy_test)
        self.toggle_btn = ProxyToggle()
        self.toggle_btn.toggled_state.connect(self._on_toggle)
        right.addWidget(self.chip, 0, Qt.AlignmentFlag.AlignVCenter)
        right.addWidget(self.test_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        right.addWidget(self.toggle_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        outer.addLayout(form, 1)
        outer.addLayout(right, 0)

        self.host_edit.textChanged.connect(self._on_conn_changed)
        self.port_edit.textChanged.connect(self._on_conn_changed)
        self.type_seg.currentChanged.connect(self._on_type_changed)


    def _build_apps_card(self) -> None:
        card = QFrame()
        card.setObjectName("card")
        self._add_shadow(card, blur=30, dy=10)
        self._main_lay.addWidget(card, 1)
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 14, 16, 8)
        v.setSpacing(10)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self.search = SearchField()
        self.search.setPlaceholderText("Поиск приложения…")
        self.search.textChanged.connect(self.apply_filter)
        self.count_lbl = QLabel("Выбрано: 0")
        self.count_lbl.setObjectName("countLabel")
        self.clear_btn = QPushButton("Снять все")
        self.clear_btn.setObjectName("textButton")
        self.clear_btn.clicked.connect(self.clear_selection)
        self.add_folder_btn = QPushButton("+ Папка")
        self.add_folder_btn.setObjectName("tonalButton")
        self.add_folder_btn.setToolTip("Добавить папку с приложениями")
        self.add_folder_btn.clicked.connect(self.add_folder)
        self.refresh_btn = RefreshButton()
        self.refresh_btn.setToolTip("Обновить список приложений")
        self.refresh_btn.clicked.connect(self.start_scan)
        toolbar.addWidget(self.search, 1)
        toolbar.addWidget(self.count_lbl)
        toolbar.addWidget(self.clear_btn)
        toolbar.addWidget(self.add_folder_btn)
        toolbar.addWidget(self.refresh_btn)
        v.addLayout(toolbar)

        manual = QHBoxLayout()
        manual.setSpacing(10)
        self.manual_edit = QLineEdit()
        self.manual_edit.setPlaceholderText("название приложения — например, chrome.exe")
        self.manual_edit.setFixedHeight(40)
        self.manual_edit.returnPressed.connect(self.add_manual)
        manual_add = QPushButton("Добавить")
        manual_add.setObjectName("tonalButton")
        manual_add.clicked.connect(self.add_manual)
        manual.addWidget(self.manual_edit, 1)
        manual.addWidget(manual_add)
        v.addLayout(manual)

        self.engine_status = QLabel("Прокси-запуск: выключен")
        self.engine_status.setObjectName("secondary")
        v.addWidget(self.engine_status)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_host = QWidget()
        self.list_lay = QVBoxLayout(self.list_host)
        self.list_lay.setContentsMargins(2, 2, 4, 6)
        self.list_lay.setSpacing(6)
        self.empty_lbl = QLabel("Сканирование установленных приложений…")
        self.empty_lbl.setObjectName("secondary")
        self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_lbl.setFixedHeight(56)
        self.hdr_sel = QLabel("")
        self.hdr_sel.setObjectName("sectionHeader")
        self.hdr_sel.setFixedHeight(28)
        self.hdr_sel.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.hdr_other = QLabel("")
        self.hdr_other.setObjectName("sectionHeader")
        self.hdr_other.setFixedHeight(28)
        self.hdr_other.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.list_lay.addWidget(self.empty_lbl)
        self.list_lay.addWidget(self.hdr_sel)
        self.list_lay.addWidget(self.hdr_other)
        self.list_lay.addStretch(1)
        scroll.setWidget(self.list_host)
        v.addWidget(scroll, 1)
        self.hdr_sel.hide()
        self.hdr_other.hide()

    def _build_overlays(self) -> None:
        self.snack = Snackbar(self.root)
        self.root.add_overlay(self.snack, "left")
        self.root.recalc_overlays()


    # ---------------------------------------------------------------- scanning
    def start_scan(self) -> None:
        if self._scan_worker is not None and self._scan_worker.isRunning():
            return
        self.empty_lbl.setText("Сканирование установленных приложений…")
        self.empty_lbl.show()
        self.search.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self._scan_worker = ScanWorker(list(self.config.folders), self)
        self._scan_worker.done.connect(self.on_scan_done)
        self._scan_worker.start()

    def on_scan_done(self, entries) -> None:
        merged = list(entries)
        have = {e.key for e in merged}
        for m in self.config.manual_apps:
            path = m.get("path", "")
            if path and path.lower() not in have:
                merged.append(scanner.AppEntry(
                    name=m.get("name") or Path(path).stem,
                    path=path, source="manual"))
                have.add(path.lower())
        merged.sort(key=lambda e: e.name.lower())
        self.entries = merged

        self.search.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        for row in list(self.rows.values()):
            self.list_lay.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
        self.rows = {}
        selected = {p.lower() for p in self.config.selected}
        for entry in self.entries:
            row = AppRow(entry, checked=(entry.path.lower() in selected))
            row.toggled.connect(self.on_row_toggled)
            self.rows[entry.path.lower()] = row
            self.list_lay.addWidget(row)
        if self.demo_select:
            for row in list(self.rows.values())[: self.demo_select]:
                row.set_checked(True, emit=False, animate=False)
        self.rebuild_order()
        self.apply_filter(self.search.text())
        self._update_count()
        self._update_subtitle()
        if not self.entries:
            self.empty_lbl.setText(
                "Приложения не найдены — нажмите «+ Папка» или добавьте вручную"
            )
            self.empty_lbl.show()
        if self._pending_folder_msg:
            self._pending_folder_msg = False
            self.snack.show_message(
                f"Список обновлён · всего приложений: {len(self.entries)}", "ok"
            )
        self._sync_engine_targets()
        self.scanned.emit()

    def rebuild_order(self) -> None:
        rows = list(self.rows.values())
        selected = sorted(
            [r for r in rows if r.checked()], key=lambda r: r.entry.name.lower()
        )
        other = sorted(
            [r for r in rows if not r.checked()], key=lambda r: r.entry.name.lower()
        )
        for r in rows:
            self.list_lay.removeWidget(r)
        i = self.list_lay.indexOf(self.hdr_sel)
        for r in selected:
            i += 1
            self.list_lay.insertWidget(i, r)
        j = self.list_lay.indexOf(self.hdr_other)
        for r in other:
            j += 1
            self.list_lay.insertWidget(j, r)

    def on_row_toggled(self, row, checked: bool) -> None:
        self.list_lay.removeWidget(row)
        anchor = self.hdr_sel if checked else self.hdr_other
        idx = self.list_lay.indexOf(anchor)
        self.list_lay.insertWidget(idx + 1, row)
        self._update_headers()
        self._update_count()
        self._save_selected()
        self._update_subtitle()
        self._sync_engine_targets()

    def _update_headers(self) -> None:
        rows = list(self.rows.values())
        sel = [r for r in rows if r.checked() and not r.isHidden()]
        oth = [r for r in rows if not r.checked() and not r.isHidden()]
        total_sel = sum(1 for r in rows if r.checked())
        suffix = "" if len(sel) == total_sel else f" из {total_sel}"
        self.hdr_sel.setText(f"ВЫБРАННЫЕ — {len(sel)}{suffix}")
        self.hdr_other.setText(f"ОСТАЛЬНЫЕ ПРИЛОЖЕНИЯ — {len(oth)}")
        self.hdr_sel.setVisible(bool(sel))
        self.hdr_other.setVisible(bool(oth))

    def _update_count(self) -> int:
        n = sum(1 for r in self.rows.values() if r.checked())
        self.count_lbl.setText(f"Выбрано: {n}")
        self.clear_btn.setEnabled(n > 0)
        return n

    def apply_filter(self, text: str = "") -> None:
        q = (text or "").strip().lower()
        for r in self.rows.values():
            r.setVisible(r.matches(q))
        visible = sum(1 for r in self.rows.values() if not r.isHidden())
        if self.rows:
            if visible == 0:
                self.empty_lbl.setText(
                    f"Ничего не найдено по запросу «{text.strip()}»"
                )
                self.empty_lbl.show()
            else:
                self.empty_lbl.hide()
        self._update_headers()

    def clear_selection(self) -> None:
        for r in self.rows.values():
            if r.checked():
                r.set_checked(False, emit=False, animate=False)
        self.rebuild_order()
        self._update_headers()
        self._update_count()
        self._save_selected()
        self._update_subtitle()
        self._sync_engine_targets()


    def add_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Выберите папку с приложениями"
        )
        if not path:
            return
        if path not in self.config.folders:
            self.config.folders.append(path)
            self._save()
        self._pending_folder_msg = True
        self.start_scan()

    def add_manual(self) -> None:
        text = self.manual_edit.text().strip()
        if not text:
            return
        found = scanner.find_exe(text)
        if not found:
            self.snack.show_message(f"«{text}» не найдено в системе", "error")
            return
        key = found.lower()
        if any(m.get("path", "").lower() == key for m in self.config.manual_apps):
            self.snack.show_message("Уже в списке", "warn")
            self.manual_edit.clear()
            return
        self.config.manual_apps.append({"name": Path(found).stem, "path": found})
        self._save()
        self.manual_edit.clear()
        if key not in self.rows:
            entry = scanner.AppEntry(
                name=Path(found).stem, path=found, source="manual"
            )
            row = AppRow(entry, checked=True)
            row.toggled.connect(self.on_row_toggled)
            self.rows[key] = row
            self.list_lay.addWidget(row)
            self.rebuild_order()
            self.apply_filter(self.search.text())
            self._update_count()
            self._update_headers()
            self._update_subtitle()
            self._save_selected()
            self._sync_engine_targets()
        self.snack.show_message(f"Добавлено: {Path(found).name}", "ok")

    def _selected_paths(self) -> list:
        return [r.entry.path for r in self.rows.values() if r.checked()]

    def _save_selected(self) -> None:
        if not self.persist:
            return
        current = self._selected_paths()
        known = set(self.rows.keys())
        missing = [p for p in self.config.selected if p.lower() not in known]
        self.config.selected = missing + current
        self._save()

    def _sync_engine_targets(self) -> None:
        if self.engine.is_running():
            self.engine.set_targets(self._selected_paths())

    # ------------------------------------------------------------- connection
    def _on_conn_changed(self, *_args) -> None:
        self._update_subtitle()
        self.chip.setState("idle")
        self._save_timer.start()
        self._push_params()

    def _on_type_changed(self, *_args) -> None:
        self._update_subtitle()
        self.chip.setState("idle")
        self._save_timer.start()
        self._push_params()

    def _push_params(self) -> None:
        if not self.engine.is_running():
            return
        host = self.host_edit.text().strip()
        try:
            port = int(self.port_edit.text())
        except ValueError:
            return
        if host and 0 < port < 65536:
            self.engine.set_params(self.type_seg.currentOption(), host, port)

    def _update_subtitle(self) -> None:
        host = self.host_edit.text().strip() or "—"
        port = self.port_edit.text().strip() or "—"
        proto = self.type_seg.currentOption()
        n = sum(1 for r in self.rows.values() if r.checked())
        self.subtitle.setText(
            f"{proto} · {host}:{port} · выбрано приложений: {n}"
        )

    def start_proxy_test(self) -> None:
        if self._test_worker is not None and self._test_worker.isRunning():
            return
        host = self.host_edit.text().strip()
        try:
            port = int(self.port_edit.text())
        except ValueError:
            port = -1
        if not host or not 0 < port < 65536:
            self.chip.setState("fail", "укажите хост и порт")
            return
        self.test_btn.setEnabled(False)
        self.chip.setState("checking")
        self._test_worker = TestWorker(host, port, self)
        self._test_worker.done.connect(self._on_test_done)
        self._test_worker.start()

    def _on_test_done(self, ok: bool) -> None:
        self.test_btn.setEnabled(True)
        host = self.host_edit.text().strip()
        port = self.port_edit.text().strip()
        if ok:
            self.chip.setState("ok", f"{host}:{port} · онлайн")
        else:
            self.chip.setState("fail", f"{host}:{port} · не отвечает")


    # ----------------------------------------------------------------- engine
    def _on_toggle(self, on: bool) -> None:
        if not on:
            self.engine.stop()
            return
        if not self._selected_paths():
            self.toggle_btn.setState(False, emit=False)
            self.snack.show_message("Отметьте приложения галочками", "warn")
            return
        host = self.host_edit.text().strip()
        try:
            port = int(self.port_edit.text())
            ok_port = 1 <= port <= 65535
        except ValueError:
            port = -1
            ok_port = False
        self._field_error(self.host_edit, not host)
        self._field_error(self.port_edit, not ok_port)
        if not host or not ok_port:
            self.toggle_btn.setState(False, emit=False)
            self.snack.show_message("Проверьте хост и порт", "error")
            return
        self._sync_fields()
        if self.persist:
            self.config.save()
        self.engine.set_params(self.type_seg.currentOption(), host, port)
        self.engine.set_targets(self._selected_paths())
        self.engine.start()

    def _on_engine_state(self, running: bool) -> None:
        self.toggle_btn.setState(running, emit=False)
        if running:
            self.engine_status.setText("Прокси-запуск: ВКЛЮЧЁН")
            self.snack.show_message("Выбранные приложения запущены через прокси", "ok")
        else:
            self.engine_status.setText("Прокси-запуск: выключен")

    def _on_engine_stats(self, procs: int, conns: int) -> None:
        if self.engine.is_running():
            self.engine_status.setText(
                f"Прокси-запуск: ВКЛЮЧЁН · процессов: {procs}"
            )

    def _on_engine_error(self, message: str) -> None:
        self.toggle_btn.setState(False, emit=False)
        self.engine_status.setText("Прокси-запуск: выключен")
        self.snack.show_message(message, "error")
        if self.engine.is_running():
            self.engine.stop()

    def _field_error(self, edit: QLineEdit, on: bool) -> None:
        if bool(edit.property("error")) == on:
            return
        edit.setProperty("error", on)
        style = edit.style()
        style.unpolish(edit)
        style.polish(edit)
        edit.update()

    # ----------------------------------------------------------------- theme
    def _on_accent_changed(self, hex_: str) -> None:
        self.config.accent = hex_
        if self.persist:
            self._save()
        T.apply(QApplication.instance(), self.config.theme, self.config.accent)
        self.accent_picker.refresh()
        for w in self.findChildren(QWidget):
            w.update()

    def _apply_theme_now(self) -> None:
        T.apply(QApplication.instance(), self.config.theme, self.config.accent)
        for eff in self._shadows:
            eff.setColor(QColor(0, 0, 0, T.CURRENT.shadow_alpha))
        self.chip.refresh()
        self.accent_picker.refresh()
        for w in self.findChildren(QWidget):
            w.update()

    # ------------------------------------------------------------------ save
    def _sync_fields(self) -> None:
        self.config.host = self.host_edit.text().strip()
        try:
            self.config.port = int(self.port_edit.text())
        except ValueError:
            pass
        self.config.proto = self.type_seg.currentOption()

    def _save(self) -> None:
        if not self.persist:
            return
        self._sync_fields()
        self.config.save()

    def closeEvent(self, e) -> None:
        try:
            self.engine.stop()
        except Exception:
            pass
        # Never destroy a QThread wrapper while its Python worker is still
        # running.  This avoids Qt's "Destroyed while thread is still
        # running" shutdown crash when the window is closed during a scan or
        # proxy check.
        for worker in (self._scan_worker, self._test_worker):
            if worker is not None and worker.isRunning():
                if not worker.wait(800):
                    worker.terminate()
                    worker.wait(800)
        if self.persist:
            self._sync_fields()
            self.config.save()
        super().closeEvent(e)
