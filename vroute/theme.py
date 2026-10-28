"""Single dark graphite theme with selectable accent colour presets."""

from __future__ import annotations

from dataclasses import dataclass
from string import Template

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

DEFAULT_ACCENT = "#4C7DFF"


@dataclass(frozen=True)
class Theme:
    key: str
    bg: str
    surface: str
    surface_alt: str
    hover: str
    text: str
    text_dim: str
    outline: str
    primary: str
    on_primary: str
    primary_dim: str
    error: str
    success: str
    warning: str
    shadow_alpha: int


@dataclass(frozen=True)
class Base:
    bg: str
    surface: str
    surface_alt: str
    hover: str
    text: str
    text_dim: str
    outline: str
    error: str
    success: str
    warning: str
    shadow_alpha: int


DARK_BASE = Base(
    bg="#101216", surface="#17191E", surface_alt="#1E2128", hover="#292D36",
    text="#F0F2F5", text_dim="#9AA2B1", outline="#343944",
    error="#FF7085", success="#4FDCB0", warning="#FFC46B", shadow_alpha=140,
)

# (id, label, hex) — accent presets
PRESETS = [
    ("dark_blue", "Тёмно-синий", "#4C7DFF"),
    ("violet", "Фиолетовый", "#8B5CF6"),
    ("green", "Зелёный", "#22C55E"),
    ("mint", "Мятный", "#2DD4BF"),
    ("yellow", "Жёлтый", "#EAB308"),
    ("red", "Красный", "#EF4444"),
    ("crimson", "Малиновый", "#EC4899"),
    ("orange", "Оранжевый", "#F97316"),
    ("black", "Чёрный", "#18181B"),
    ("white", "Белый", "#F8FAFC"),
]


def mix(hex1: str, hex2: str, t: float) -> str:
    a, b = QColor(hex1), QColor(hex2)
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    return QColor.fromRgbF(
        a.redF() + (b.redF() - a.redF()) * t,
        a.greenF() + (b.greenF() - a.greenF()) * t,
        a.blueF() + (b.blueF() - a.blueF()) * t,
    ).name()


def luminance(hex_color: str) -> float:
    c = QColor(hex_color)
    return 0.2126 * c.redF() + 0.7152 * c.greenF() + 0.0722 * c.blueF()


def normalize_accent(hex_color: str) -> str:
    """Validate a hex colour, fall back to the default accent."""
    c = QColor(hex_color)
    if c.isValid():
        return c.name()
    return DEFAULT_ACCENT


def adjust_accent(hex_color: str, dark: bool) -> str:
    """Clamp accent luminance so it stays visible on the current base theme."""
    c = QColor(hex_color)
    for _ in range(24):
        lum = luminance(c.name())
        if dark and lum < 0.24:
            c = c.lighter(112)
        elif not dark and lum > 0.78:
            c = c.darker(112)
        else:
            break
    return c.name()


def build_theme(_dark: bool = True, accent_hex: str = DEFAULT_ACCENT) -> Theme:
    """Build the only supported theme: dark graphite."""
    base = DARK_BASE
    accent = adjust_accent(normalize_accent(accent_hex), True)
    # The chosen colour is a system colour, not just a button colour.  A very
    # restrained tint keeps the surfaces elegant while making every preset
    # perceptibly change the whole interface.
    bg = mix(base.bg, accent, 0.07)
    surface = mix(base.surface, accent, 0.10)
    surface_alt = mix(base.surface_alt, accent, 0.14)
    hover = mix(base.hover, accent, 0.20)
    outline = mix(base.outline, accent, 0.18)
    on_primary = "#0B1220" if luminance(accent) > 0.45 else "#FFFFFF"
    primary_dim = mix(accent, surface, 0.24)
    return Theme(
        key="dark",
        bg=bg, surface=surface, surface_alt=surface_alt,
        hover=hover, text=base.text, text_dim=base.text_dim,
        outline=outline, error=base.error, success=base.success,
        warning=base.warning, shadow_alpha=base.shadow_alpha,
        primary=accent, on_primary=on_primary, primary_dim=primary_dim,
    )


CURRENT: Theme = build_theme(True, DEFAULT_ACCENT)


_QSS = Template("""
QWidget#root { background-color: $bg; }

QLabel { background: transparent; }
QLabel#appTitle { color: $text; font-size: 21px; font-weight: bold; }
QLabel#appSubtitle { color: $text_dim; font-size: 12px; }
QLabel#fieldLabel { color: $text_dim; font-size: 11px; font-weight: bold; }
QLabel#sectionHeader { color: $text_dim; font-size: 11px; font-weight: bold; }
QLabel#countLabel { color: $text_dim; font-size: 12px; }
QLabel#secondary { color: $text_dim; font-size: 13px; }
QLabel#appName { color: $text; font-size: 14px; font-weight: bold; }
QLabel#appPath { color: $text_dim; font-size: 11px; }
QLabel#chipText { color: $text_dim; font-size: 12px; }
QLabel#snackBarText { color: $text; font-size: 13px; }

QFrame#card {
    background-color: $surface;
    border: 1px solid $outline;
    border-radius: 18px;
}
QFrame#appRow {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 12px;
}
QFrame#appRow:hover {
    background-color: $surface_alt;
    border: 1px solid $outline;
}
QFrame#chip {
    background-color: $surface_alt;
    border: 1px solid $outline;
    border-radius: 12px;
}
QFrame#snackbar {
    background-color: $surface_alt;
    border: 1px solid $outline;
    border-radius: 12px;
}

QLineEdit {
    background-color: $surface_alt;
    border: 1px solid $outline;
    border-radius: 12px;
    padding: 10px 14px;
    font-size: 14px;
    color: $text;
    selection-background-color: $primary;
    selection-color: $on_primary;
}
QLineEdit:focus {
    border: 2px solid $primary;
    padding: 9px 13px;
}
QLineEdit[error="true"], QLineEdit[error="true"]:focus {
    border: 2px solid $error;
    padding: 9px 13px;
}
QLineEdit#search {
    border-radius: 22px;
    padding: 10px 14px 10px 40px;
    font-size: 14px;
}
QLineEdit#search:focus {
    border: 2px solid $primary;
    padding: 9px 13px 9px 39px;
}

QPushButton {
    background-color: transparent;
    border: none;
    color: $text;
    font-size: 13px;
    font-weight: bold;
    padding: 0px;
}
QPushButton:disabled { color: $text_dim; }
QPushButton#tonalButton {
    background-color: $primary_dim;
    color: $primary;
    border-radius: 13px;
    padding: 10px 16px;
    font-size: 13px;
}
QPushButton#tonalButton:hover { background-color: $hover; }
QPushButton#tonalButton:disabled { background-color: $surface_alt; color: $text_dim; }
QPushButton#textButton {
    color: $primary;
    border-radius: 9px;
    padding: 8px 10px;
    font-size: 13px;
}
QPushButton#textButton:hover { background-color: $primary_dim; }
QPushButton#textButton:disabled { color: $text_dim; background-color: transparent; }

QScrollArea { background: transparent; border: none; }
QScrollArea::corner { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 0px; }
QScrollBar::handle:vertical {
    background: $outline;
    border-radius: 5px;
    min-height: 32px;
}
QScrollBar::handle:vertical:hover { background: $text_dim; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; width: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }

QToolTip {
    color: $text;
    background-color: $surface_alt;
    border: 1px solid $outline;
    padding: 5px 8px;
    font-size: 12px;
}
""")


def build_qss(theme: Theme) -> str:
    from dataclasses import asdict
    return _QSS.substitute(asdict(theme))


def apply(app: QApplication, key: str, accent_hex: str | None = None) -> Theme:
    global CURRENT
    CURRENT = build_theme(True, accent_hex or DEFAULT_ACCENT)
    app.setStyleSheet(build_qss(CURRENT))
    pal = app.palette()
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(CURRENT.text_dim))
    pal.setColor(QPalette.ColorRole.Text, QColor(CURRENT.text))
    pal.setColor(QPalette.ColorRole.Base, QColor(CURRENT.surface_alt))
    app.setPalette(pal)
    return CURRENT
