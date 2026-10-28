"""Programmatically drawn icons and application icons (no external assets)."""

from __future__ import annotations

import math

from PySide6.QtCore import QFileInfo, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

try:
    from PySide6.QtGui import QFileIconProvider
except ImportError:  # pragma: no cover - Qt5 compat
    from PySide6.QtWidgets import QFileIconProvider

_provider = QFileIconProvider()
_cache: dict[str, QIcon] = {}


def app_icon(path: str) -> QIcon:
    key = path.lower()
    icon = _cache.get(key)
    if icon is None:
        icon = _provider.icon(QFileInfo(path))
        _cache[key] = icon
    return icon


def _arc_points(cx: float, cy: float, r: float, a0: float, a1: float, steps: int = 40) -> list[QPointF]:
    """Sample an arc; angles in degrees, 0 = right, positive = clockwise (screen coords)."""
    pts = []
    for i in range(steps + 1):
        a = math.radians(a0 + (a1 - a0) * i / steps)
        pts.append(QPointF(cx + math.cos(a) * r, cy + math.sin(a) * r))
    return pts


def draw_moon(p: QPainter, rect: QRectF, color: QColor) -> None:
    outer = QPainterPath()
    outer.addEllipse(rect)
    inner = QPainterPath()
    w = rect.width()
    ir = w * 0.44
    cx = rect.center().x() + w * 0.20
    cy = rect.center().y() - w * 0.18
    inner.addEllipse(QRectF(cx - ir, cy - ir, ir * 2, ir * 2))
    p.fillPath(outer.subtracted(inner), color)


def draw_sun(p: QPainter, rect: QRectF, color: QColor) -> None:
    c = rect.center()
    r = rect.width() / 2.0
    pen_w = max(1.4, rect.width() * 0.085)
    p.save()
    p.setPen(QPen(color, pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.setBrush(color)
    body = r * 0.42
    p.drawEllipse(c, body, body)
    for i in range(8):
        a = math.radians(i * 45)
        r1, r2 = r * 0.66, r * 0.95
        p.drawLine(
            QPointF(c.x() + math.cos(a) * r1, c.y() + math.sin(a) * r1),
            QPointF(c.x() + math.cos(a) * r2, c.y() + math.sin(a) * r2),
        )
    p.restore()


def draw_pause(p: QPainter, rect: QRectF, color: QColor) -> None:
    w, h = rect.width(), rect.height()
    bar_w = w * 0.20
    gap = w * 0.16
    left = rect.left() + (w - bar_w * 2 - gap) / 2
    top = rect.top() + h * 0.22
    bar_h = h * 0.56
    first = QPainterPath()
    first.addRoundedRect(left, top, bar_w, bar_h, bar_w / 2, bar_w / 2)
    second = QPainterPath()
    second.addRoundedRect(
        left + bar_w + gap, top, bar_w, bar_h, bar_w / 2, bar_w / 2
    )
    p.fillPath(first, color)
    p.fillPath(second, color)


def draw_play(p: QPainter, rect: QRectF, color: QColor) -> None:
    h, w = rect.height(), rect.width()
    cx, cy = rect.center().x(), rect.center().y()
    path = QPainterPath()
    x0 = rect.left() + w * 0.32
    path.moveTo(x0, cy - h * 0.40)
    path.lineTo(rect.left() + w * 0.76, cy)
    path.lineTo(x0, cy + h * 0.40)
    path.closeSubpath()
    p.fillPath(path, color)


def draw_search(p: QPainter, rect: QRectF, color: QColor) -> None:
    pen_w = max(1.5, rect.width() * 0.11)
    p.save()
    p.setPen(QPen(color, pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    r = rect.width() * 0.30
    c = QPointF(rect.center().x() - rect.width() * 0.06, rect.center().y() - rect.height() * 0.06)
    p.drawEllipse(c, r, r)
    p.drawLine(
        QPointF(c.x() + r * 0.72, c.y() + r * 0.72),
        QPointF(rect.right() - pen_w * 0.7, rect.bottom() - pen_w * 0.7),
    )
    p.restore()


def draw_refresh(p: QPainter, rect: QRectF, color: QColor) -> None:
    pen_w = max(1.5, rect.width() * 0.10)
    cx, cy = rect.center().x(), rect.center().y()
    r = rect.width() / 2.0 - pen_w
    p.save()
    p.setPen(QPen(color, pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    a0, a1 = -75.0, 195.0
    pts = _arc_points(cx, cy, r, a0, a1)
    path = QPainterPath()
    path.moveTo(pts[0])
    for pt in pts[1:]:
        path.lineTo(pt)
    p.drawPath(path)
    # arrow head at the start of the arc, pointing along travel direction
    rad = math.radians(a0)
    tx, ty = -math.sin(rad), math.cos(rad)
    nx, ny = -ty, tx
    start = pts[0]
    size = pen_w * 1.9
    tip = QPointF(start.x() + tx * size, start.y() + ty * size)
    b1 = QPointF(start.x() + nx * size * 0.8, start.y() + ny * size * 0.8)
    b2 = QPointF(start.x() - nx * size * 0.8, start.y() - ny * size * 0.8)
    tri = QPainterPath()
    tri.moveTo(tip)
    tri.lineTo(b1)
    tri.lineTo(b2)
    tri.closeSubpath()
    p.setPen(Qt.PenStyle.NoPen)
    p.fillPath(tri, color)
    p.restore()


def draw_folder(p: QPainter, rect: QRectF, color: QColor) -> None:
    pen_w = max(1.4, rect.width() * 0.08)
    m = pen_w
    x0, y0 = rect.left() + m, rect.top() + m
    x1, y1 = rect.right() - m, rect.bottom() - m
    tab_h = (y1 - y0) * 0.24
    tab_w = x0 + (x1 - x0) * 0.44
    p.save()
    p.setPen(QPen(color, pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath()
    path.moveTo(x0, y0)
    path.lineTo(tab_w, y0)
    path.lineTo(tab_w, y0 + tab_h)
    path.lineTo(x1, y0 + tab_h)
    path.lineTo(x1, y1)
    path.lineTo(x0, y1)
    path.closeSubpath()
    p.drawPath(path)
    # plus sign
    s = (x1 - x0) * 0.15
    pcx = x0 + (x1 - x0) * 0.68
    pcy = y0 + tab_h + ((y1) - (y0 + tab_h)) / 2
    p.drawLine(QPointF(pcx - s, pcy), QPointF(pcx + s, pcy))
    p.drawLine(QPointF(pcx, pcy - s), QPointF(pcx, pcy + s))
    p.restore()


def render_logo(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0.0, QColor("#4C8DFF"))
    grad.setColorAt(1.0, QColor("#1B49C4"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(grad)
    p.drawRoundedRect(QRectF(0, 0, size, size), size * 0.24, size * 0.24)
    font = p.font()
    font.setBold(True)
    font.setPixelSize(int(size * 0.56))
    p.setFont(font)
    p.setPen(QColor("#FFFFFF"))
    p.drawText(QRectF(0, size * 0.01, size, size), int(Qt.AlignmentFlag.AlignCenter), "V")
    p.setBrush(QColor("#4FDCB0"))
    p.drawEllipse(QPointF(size * 0.76, size * 0.76), size * 0.10, size * 0.10)
    p.end()
    return pm
