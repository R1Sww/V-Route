"""Custom Material-style widgets for V-Route."""

from __future__ import annotations

import math

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSlider,
    QWidget,
)

from . import icons
from . import theme as T


def qc(color: str, alpha: int = 255) -> QColor:
    c = QColor(color)
    c.setAlpha(alpha)
    return c


def lerp_color(a, b, t: float) -> QColor:
    ca, cb = QColor(a), QColor(b)
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    return QColor.fromRgbF(
        ca.redF() + (cb.redF() - ca.redF()) * t,
        ca.greenF() + (cb.greenF() - ca.greenF()) * t,
        ca.blueF() + (cb.blueF() - ca.blueF()) * t,
    )


class MCheckBox(QWidget):
    """Animated Material-style checkbox (drawn, not styled)."""

    toggled = Signal(bool)

    def __init__(self, checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._checked = bool(checked)
        self._progress = 1.0 if self._checked else 0.0
        self._hovered = False
        self._anim = QPropertyAnimation(self, b"progress", self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setFixedSize(24, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def sizeHint(self) -> QSize:
        return QSize(24, 24)

    def _get_progress(self) -> float:
        return self._progress

    def _set_progress(self, value: float) -> None:
        self._progress = float(value)
        self.update()

    progress = Property(float, _get_progress, _set_progress)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool, emit: bool = True, animate: bool = True) -> None:
        checked = bool(checked)
        end = 1.0 if checked else 0.0
        changed = checked != self._checked
        self._checked = checked
        self._anim.stop()
        if abs(self._progress - end) > 1e-6:
            if animate:
                self._anim.setStartValue(self._progress)
                self._anim.setEndValue(end)
                self._anim.start()
            else:
                self._set_progress(end)
        if changed and emit:
            self.toggled.emit(checked)
        self.update()

    def enterEvent(self, e) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
        else:
            super().mousePressEvent(e)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        th = T.CURRENT
        t = self._progress
        box = QRectF(3, 3, 18, 18)
        border = lerp_color(th.outline, th.primary, min(1.0, t * 1.7))
        if self._hovered and t < 0.05:
            border = lerp_color(border, th.text_dim, 0.55)
        fill = QColor(th.primary)
        fill.setAlphaF(min(1.0, t * 1.35))
        p.setPen(QPen(border, 2.0, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(fill if t > 0.01 else Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(box, 5.0, 5.0)
        if self.hasFocus():
            p.setPen(QPen(qc(th.primary, 120), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(0.75, 0.75, 22.5, 22.5), 7.0, 7.0)
        if t > 0.15:
            k = min(1.0, (t - 0.15) / 0.85)
            p0 = QPointF(box.left() + 4.4, box.top() + 9.6)
            p1 = QPointF(box.left() + 9.0, box.top() + 14.0)
            p2 = QPointF(box.right() - 4.0, box.top() + 6.2)
            p.setPen(QPen(qc(th.on_primary), 2.1, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(Qt.BrushStyle.NoBrush)
            if k < 0.45:
                u = k / 0.45
                p.drawLine(p0, QPointF(p0.x() + (p1.x() - p0.x()) * u,
                                       p0.y() + (p1.y() - p0.y()) * u))
            else:
                p.drawLine(p0, p1)
                u = (k - 0.45) / 0.55
                p.drawLine(p1, QPointF(p1.x() + (p2.x() - p1.x()) * u,
                                       p1.y() + (p2.y() - p1.y()) * u))


class SegmentedControl(QWidget):
    """Material segmented button group (connection type selector)."""

    currentChanged = Signal(int)

    def __init__(self, options, current: int = 0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._options = [str(o) for o in options]
        self._index = max(0, min(int(current), len(self._options) - 1))
        self._slide = float(self._index)
        self._hover = -1
        self._anim = QPropertyAnimation(self, b"slide", self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def _get_slide(self) -> float:
        return self._slide

    def _set_slide(self, value: float) -> None:
        self._slide = float(value)
        self.update()

    slide = Property(float, _get_slide, _set_slide)

    def currentIndex(self) -> int:
        return self._index

    def currentOption(self) -> str:
        if 0 <= self._index < len(self._options):
            return self._options[self._index]
        return ""

    def sizeHint(self) -> QSize:
        fm = self.fontMetrics()
        widest = max((fm.horizontalAdvance(o) for o in self._options), default=52)
        return QSize((widest + 26) * len(self._options) + 8, 44)

    def setIndex(self, index: int, emit: bool = True) -> None:
        index = max(0, min(int(index), len(self._options) - 1))
        if index == self._index:
            return
        self._index = index
        self._anim.stop()
        self._anim.setStartValue(self._slide)
        self._anim.setEndValue(float(index))
        self._anim.start()
        self.update()
        if emit:
            self.currentChanged.emit(index)

    def _seg_at(self, x: float) -> int:
        if not self._options:
            return -1
        w = self.width() / len(self._options)
        i = int(x // w) if x >= 0 else -1
        return i if 0 <= i < len(self._options) else -1

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            i = self._seg_at(e.position().x())
            if i >= 0:
                self.setIndex(i)
        else:
            super().mousePressEvent(e)

    def mouseMoveEvent(self, e) -> None:
        i = self._seg_at(e.position().x())
        if i != self._hover:
            self._hover = i
            self.update()
        super().mouseMoveEvent(e)

    def leaveEvent(self, e) -> None:
        self._hover = -1
        self.update()
        super().leaveEvent(e)

    def keyPressEvent(self, e) -> None:
        if e.key() == Qt.Key.Key_Left:
            self.setIndex(self._index - 1)
        elif e.key() == Qt.Key.Key_Right:
            self.setIndex(self._index + 1)
        else:
            super().keyPressEvent(e)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        th = T.CURRENT
        outer = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        n = max(1, len(self._options))
        h = outer.height()
        rad = h / 2
        p.setPen(QPen(qc(th.outline), 1.0))
        p.setBrush(qc(th.surface_alt))
        p.drawRoundedRect(outer, rad, rad)
        seg_w = outer.width() / n
        if 0 <= self._hover < n:
            hv = QRectF(outer.left() + self._hover * seg_w + 2, outer.top() + 2,
                        seg_w - 4, h - 4)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(qc(th.hover, 170))
            p.drawRoundedRect(hv, (h - 4) / 2, (h - 4) / 2)
        pill = QRectF(outer.left() + self._slide * seg_w + 3, outer.top() + 3,
                      seg_w - 6, h - 6)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(qc(th.primary))
        p.drawRoundedRect(pill, pill.height() / 2, pill.height() / 2)
        font = QFont(self.font())
        font.setBold(True)
        p.setFont(font)
        for i, opt in enumerate(self._options):
            blend = max(0.0, 1.0 - abs(i - self._slide))
            p.setPen(lerp_color(th.text_dim, th.on_primary, blend))
            cell = QRectF(outer.left() + i * seg_w, outer.top(), seg_w, h)
            p.drawText(cell, int(Qt.AlignmentFlag.AlignCenter), opt)
        if self.hasFocus():
            p.setPen(QPen(qc(th.primary, 160), 2.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), rad, rad)


class IconButton(QPushButton):
    """Round icon button with a hover circle."""

    def __init__(self, size: int = 40, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._hovered = False
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def enterEvent(self, e) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._hovered:
            s = min(self.width(), self.height())
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(qc(T.CURRENT.text, 26))
            p.drawRoundedRect(QRectF(0, 0, s, s), s / 2, s / 2)
        self.draw_icon(p)

    def draw_icon(self, p: QPainter) -> None:
        pass


class ThemeToggleButton(IconButton):
    """Moon/sun toggle with rotation + cross-fade animation."""

    def __init__(self, dark: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(40, parent)
        self._progress = 0.0 if dark else 1.0
        self._anim = QPropertyAnimation(self, b"progress", self)
        self._anim.setDuration(340)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.setToolTip("Сменить тему (луна / солнце)")

    def _get_progress(self) -> float:
        return self._progress

    def _set_progress(self, value: float) -> None:
        self._progress = float(value)
        self.update()

    progress = Property(float, _get_progress, _set_progress)

    def set_dark(self, dark: bool, animate: bool = True) -> None:
        end = 0.0 if dark else 1.0
        if abs(self._progress - end) < 1e-6:
            return
        self._anim.stop()
        self._anim.setStartValue(self._progress)
        self._anim.setEndValue(end)
        if animate:
            self._anim.start()
        else:
            self._set_progress(end)

    def draw_icon(self, p: QPainter) -> None:
        rect = QRectF(10, 10, 20, 20)
        prog = self._progress
        a_moon = max(0.0, min(1.0, (0.72 - prog) / 0.45))
        a_sun = max(0.0, min(1.0, (prog - 0.28) / 0.45))
        th = T.CURRENT
        p.save()
        p.translate(rect.center())
        p.rotate(170.0 * prog)
        p.translate(-rect.center())
        if a_moon > 0.02:
            col = QColor(th.text)
            col.setAlphaF(a_moon)
            icons.draw_moon(p, rect, col)
        if a_sun > 0.02:
            col = QColor("#FFB74D")
            col.setAlphaF(a_sun)
            icons.draw_sun(p, rect, col)
        p.restore()


class RefreshButton(IconButton):
    def draw_icon(self, p: QPainter) -> None:
        icons.draw_refresh(p, QRectF(11, 11, 18, 18), qc(T.CURRENT.primary))


class SearchField(QLineEdit):
    """Outlined search field with a drawn magnifier icon."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("search")
        self.setFixedHeight(44)

    def paintEvent(self, e) -> None:
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        icons.draw_search(p, QRectF(14, (self.height() - 18) / 2, 18, 18),
                          qc(T.CURRENT.text_dim))


class ElidedLabel(QLabel):
    """Label that elides its text instead of clipping."""

    def __init__(self, mode: Qt.TextElideMode = Qt.TextElideMode.ElideRight,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full = ""
        self._mode = mode

    def setText(self, text: str) -> None:
        self._full = str(text)
        self._relayout_text()

    def fullText(self) -> str:
        return self._full

    def _relayout_text(self) -> None:
        w = self.width()
        if w <= 4:
            super().setText("")
            return
        super().setText(self.fontMetrics().elidedText(self._full, self._mode, w))

    def sizeHint(self) -> QSize:
        fm = self.fontMetrics()
        return QSize(fm.horizontalAdvance(self._full), fm.height() + 4)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, self.fontMetrics().height() + 4)

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._relayout_text()


class DotLabel(QWidget):
    """Small status dot with an optional pulse ring."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = "#8DA2C0"
        self._phase = 0.0
        self._pulse = False
        self._timer = QTimer(self)
        self._timer.setInterval(60)
        self._timer.timeout.connect(self._tick)
        self.setFixedSize(12, 12)

    def set_color(self, color: str) -> None:
        self._color = color
        self.update()

    def set_pulsing(self, on: bool) -> None:
        self._pulse = bool(on)
        if on:
            self._phase = 0.0
            self._timer.start()
        else:
            self._timer.stop()
            self.update()

    def _tick(self) -> None:
        self._phase += 0.5
        if self._phase > 6.28318:
            self._phase -= 6.28318
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        if self._pulse:
            alpha = int(35 + 80 * (math.sin(self._phase) * 0.5 + 0.5))
            p.setPen(QPen(qc(self._color, alpha), 2.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(rect.adjusted(0.5, 0.5, -0.5, -0.5))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(qc(self._color))
        p.drawEllipse(rect.adjusted(3, 3, -3, -3))


class StatusChip(QFrame):
    """Proxy status chip: idle / checking / ok / fail."""

    _LABELS = {
        "idle": "не проверено",
        "checking": "проверка…",
        "ok": "прокси отвечает",
        "fail": "прокси не отвечает",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("chip")
        self.setFixedHeight(36)
        self._state = "idle"
        self._custom: str | None = None
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 0, 14, 0)
        h.setSpacing(8)
        self._dot = DotLabel()
        self._text = QLabel("не проверено")
        self._text.setObjectName("chipText")
        h.addWidget(self._dot, 0, Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(self._text, 0, Qt.AlignmentFlag.AlignVCenter)
        self.setState("idle")

    def setState(self, state: str, text: str | None = None) -> None:
        self._state = state
        self._custom = text
        th = T.CURRENT
        color = {
            "idle": th.text_dim,
            "checking": th.warning,
            "ok": th.success,
            "fail": th.error,
        }.get(state, th.text_dim)
        self._dot.set_color(color)
        self._dot.set_pulsing(state == "checking")
        self._text.setText(text or self._LABELS.get(state, ""))
        self._text.setStyleSheet(f"color: {color}; font-weight: bold;")

    def refresh(self) -> None:
        self.setState(self._state, self._custom)


class Snackbar(QFrame):
    """Slide-up notification bar (Material snackbar)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("snackbar")
        self._home = QPointF(0, 0)
        self._tone = "info"
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 9, 18, 9)
        self._label = QLabel("")
        self._label.setObjectName("snackBarText")
        lay.addWidget(self._label)
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)
        self._pos_anim = QPropertyAnimation(self, b"pos", self)
        self._pos_anim.setDuration(240)
        self._pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._op_anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._op_anim.setDuration(240)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(3400)
        self._timer.timeout.connect(self._hide)
        self.hide()

    def set_home(self, pos: QPointF) -> None:
        self._home = QPointF(pos)

    def show_message(self, text: str, tone: str = "info") -> None:
        self._tone = tone
        self._label.setText(text)
        self.adjustSize()
        parent = self.parentWidget()
        if parent is not None and hasattr(parent, "recalc_overlays"):
            parent.recalc_overlays()
        self._pos_anim.stop()
        self._op_anim.stop()
        start = (self._home + QPointF(0, 26)).toPoint()
        self.move(start)
        self.show()
        self.raise_()
        self._pos_anim.setStartValue(start)
        self._pos_anim.setEndValue(self._home.toPoint())
        self._op_anim.setStartValue(0.0)
        self._op_anim.setEndValue(1.0)
        self._pos_anim.start()
        self._op_anim.start()
        self._timer.start()

    def _hide(self) -> None:
        self._pos_anim.stop()
        self._op_anim.stop()
        self._pos_anim.setStartValue(self.pos())
        self._pos_anim.setEndValue((QPointF(self.pos()) + QPointF(0, 18)).toPoint())
        self._op_anim.setStartValue(1.0)
        self._op_anim.setEndValue(0.0)
        self._op_anim.finished.connect(self.hide, Qt.ConnectionType.SingleShotConnection)
        self._pos_anim.start()
        self._op_anim.start()

    def paintEvent(self, e) -> None:
        super().paintEvent(e)
        th = T.CURRENT
        tone = {
            "ok": th.success, "warn": th.warning, "error": th.error,
        }.get(self._tone, th.primary)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bar = QRectF(9, 11, 4, max(6, self.height() - 22))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(qc(tone))
        p.drawRoundedRect(bar, 2, 2)


class ProxyToggle(QPushButton):
    """Play/pause pill toggle for the interception engine (top bar)."""

    toggled_state = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._on = False
        self._t = 0.0
        self._hovered = False
        self._anim = QPropertyAnimation(self, b"t", self)
        self._anim.setDuration(260)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.setFixedHeight(48)
        self.setFixedWidth(198)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setToolTip("Включить / выключить перехват соединений")
        self.clicked.connect(self._clicked)

    def _get_t(self) -> float:
        return self._t

    def _set_t(self, value: float) -> None:
        self._t = float(value)
        self.update()

    t = Property(float, _get_t, _set_t)

    def _clicked(self) -> None:
        self.setState(not self._on)

    def isOn(self) -> bool:
        return self._on

    def setState(self, on: bool, emit: bool = True) -> None:
        on = bool(on)
        if on == self._on:
            return
        self._on = on
        self._anim.stop()
        self._anim.setStartValue(self._t)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()
        if emit:
            self.toggled_state.emit(on)
        self.update()

    def enterEvent(self, e) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        th = T.CURRENT
        t = self._t
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        rad = rect.height() / 2
        on_state = t >= 0.5
        if on_state:
            bg = qc(th.primary)
            border = qc(th.primary)
            if self._hovered:
                bg = qc(lerp_color(th.primary, "#FFFFFF", 0.12))
            text_col = qc(th.on_primary)
        else:
            bg = qc(th.surface_alt)
            border = qc(th.outline)
            if self._hovered:
                bg = qc(lerp_color(th.surface_alt, th.hover, 0.7))
            text_col = qc(th.primary)
        p.setPen(QPen(border, 1.5))
        p.setBrush(bg)
        p.drawRoundedRect(rect, rad, rad)

        icon_rect = QRectF(rect.left() + 16, rect.center().y() - 9, 18, 18)
        a_play = max(0.0, 1.0 - t / 0.45)
        a_pause = max(0.0, (t - 0.55) / 0.45)
        if a_play > 0.02:
            col = QColor(th.primary)
            col.setAlphaF(a_play)
            icons.draw_play(p, icon_rect, col)
        if a_pause > 0.02:
            col = QColor(th.on_primary)
            col.setAlphaF(a_pause)
            icons.draw_pause(p, icon_rect, col)

        label = "ВЫКЛЮЧИТЬ" if on_state else "ВКЛЮЧИТЬ"
        font = QFont(self.font())
        font.setBold(True)
        font.setPointSize(10)
        p.setFont(font)
        p.setPen(text_col)
        p.drawText(
            QRectF(rect.left() + 42, rect.top(), rect.width() - 50, rect.height()),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter),
            label,
        )


class AppRow(QFrame):
    """One application row: checkbox + icon + name + path."""

    toggled = Signal(object, bool)

    def __init__(self, entry, checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.entry = entry
        self.setObjectName("appRow")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 6, 16, 6)
        lay.setSpacing(12)
        self._box = MCheckBox(checked)
        self._box.toggled.connect(self._box_toggled)
        lay.addWidget(self._box, 0, Qt.AlignmentFlag.AlignVCenter)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(icons.app_icon(entry.path).pixmap(26, 26))
        icon_lbl.setFixedSize(28, 28)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        self._name = ElidedLabel(Qt.TextElideMode.ElideRight)
        self._name.setObjectName("appName")
        self._name.setText(entry.name)
        self._name.setMinimumWidth(0)
        self._path = ElidedLabel(Qt.TextElideMode.ElideMiddle)
        self._path.setObjectName("appPath")
        self._path.setText(entry.path)
        self._path.setMinimumWidth(0)
        lay.addWidget(self._name, 2, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self._path, 3, Qt.AlignmentFlag.AlignVCenter)
        self.setFixedHeight(50)

    def checked(self) -> bool:
        return self._box.isChecked()

    def set_checked(self, value: bool, emit: bool = True, animate: bool = True) -> None:
        self._box.setChecked(value, emit=emit, animate=animate)

    def _box_toggled(self, value: bool) -> None:
        self.toggled.emit(self, value)

    def matches(self, query: str) -> bool:
        if not query:
            return True
        return query in self.entry.name.lower() or query in self.entry.path.lower()

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._box.setChecked(not self._box.isChecked())
        else:
            super().mousePressEvent(e)


class AccentPicker(QWidget):
    """Preset accent swatches + a custom-RGB dialog button."""

    accent_changed = Signal(str)

    def __init__(self, accent: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._accent = T.normalize_accent(accent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(7)
        self._dots: list[tuple[str, str, QPushButton]] = []
        for pid, label, hex_ in T.PRESETS:
            dot = QPushButton()
            dot.setFixedSize(20, 20)
            dot.setToolTip(label)
            dot.setCursor(Qt.CursorShape.PointingHandCursor)
            dot.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            dot.clicked.connect(
                lambda _checked=False, h=hex_: self._pick(h)
            )
            lay.addWidget(dot)
            self._dots.append((pid, hex_, dot))
        more = QPushButton("+")
        more.setFixedSize(22, 22)
        more.setCursor(Qt.CursorShape.PointingHandCursor)
        more.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        more.setToolTip("Свой акцентный цвет (RGB)")
        more.clicked.connect(self._custom)
        lay.addWidget(more)
        self._more = more
        self.refresh()

    def _pick(self, hex_: str) -> None:
        self._accent = T.normalize_accent(hex_)
        self.refresh()
        self.accent_changed.emit(self._accent)

    def _custom(self) -> None:
        dlg = ColorPickerDialog(self._accent, self)
        if dlg.exec():
            self._accent = dlg.color_hex()
            self.refresh()
            self.accent_changed.emit(self._accent)

    def current(self) -> str:
        return self._accent

    def refresh(self) -> None:
        th = T.CURRENT
        for _pid, hex_, dot in self._dots:
            selected = QColor(hex_) == QColor(self._accent)
            dot.setStyleSheet(
                f"QPushButton {{ background-color: {hex_}; border-radius: 10px; "
                f"border: 2px solid {th.text if selected else th.surface}; }}"
                f"QPushButton:hover {{ border: 2px solid {th.text_dim}; }}"
            )
        self._more.setStyleSheet(
            f"QPushButton {{ background-color: {th.surface_alt}; color: {th.text_dim}; "
            f"border-radius: 11px; border: 1px dashed {th.outline}; font-weight: bold; }}"
            f"QPushButton:hover {{ color: {th.text}; border-color: {th.text_dim}; }}"
        )


class ColorPickerDialog(QDialog):
    """Compact RGB colour dialog with hex input and live preview."""

    def __init__(self, initial: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Свой акцентный цвет")
        self.setFixedWidth(360)
        self._color = QColor(initial)
        self._updating = False

        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        self._preview = QLabel()
        self._preview.setFixedHeight(60)
        lay.addWidget(self._preview)

        self._sliders = []
        for name in ("R", "G", "B"):
            row = QHBoxLayout()
            lab = QLabel(name)
            lab.setFixedWidth(16)
            sl = QSlider(Qt.Orientation.Horizontal)
            sl.setRange(0, 255)
            val = QLabel("0")
            val.setFixedWidth(36)
            sl.valueChanged.connect(self._on_slider)
            row.addWidget(lab)
            row.addWidget(sl, 1)
            row.addWidget(val)
            lay.addLayout(row)
            self._sliders.append((name, sl, val))

        hexrow = QHBoxLayout()
        hexrow.addWidget(QLabel("HEX"))
        self._hex = QLineEdit(initial)
        self._hex.setMaxLength(7)
        self._hex.setFixedWidth(120)
        self._hex.textChanged.connect(self._on_hex)
        hexrow.addWidget(self._hex)
        hexrow.addStretch(1)
        lay.addLayout(hexrow)

        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("Отмена")
        cancel.setObjectName("textButton")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Применить")
        ok.setObjectName("tonalButton")
        ok.clicked.connect(self.accept)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        lay.addLayout(btns)

        self._sync()

    def color_hex(self) -> str:
        return self._color.name()

    def _on_slider(self, _value: int) -> None:
        if self._updating:
            return
        r, g, b = (sl.value() for _n, sl, _v in self._sliders)
        self._color = QColor(r, g, b)
        self._sync()

    def _on_hex(self, text: str) -> None:
        if self._updating:
            return
        c = QColor(text)
        if c.isValid():
            self._color = c
            self._sync(write_hex=False)

    def _sync(self, write_hex: bool = True) -> None:
        self._updating = True
        for name, sl, val in self._sliders:
            v = {"R": self._color.red(), "G": self._color.green(),
                 "B": self._color.blue()}[name]
            sl.setValue(v)
            val.setText(str(v))
        if write_hex:
            self._hex.setText(self._color.name())
        th = T.CURRENT
        on_col = "#FFFFFF" if T.luminance(self._color.name()) < 0.5 else "#101820"
        self._preview.setStyleSheet(
            f"background-color: {self._color.name()}; border-radius: 12px; "
            f"border: 1px solid {th.outline};"
        )
        self._preview.setText(self._color.name().upper())
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet(
            self._preview.styleSheet() + f" color: {on_col}; font-weight: bold;"
        )
        self._updating = False
