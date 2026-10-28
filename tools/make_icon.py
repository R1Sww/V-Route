"""Generate assets/vroute.ico from a programmatically drawn logo."""

from __future__ import annotations

import struct
import sys
import tempfile
from pathlib import Path

SIZES = (16, 24, 32, 48, 64, 128, 256)


def main() -> int:
    from PySide6.QtGui import QGuiApplication

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from vroute import icons  # noqa: E402

    app = QGuiApplication([])  # noqa: F841  (QPixmap requires an app instance)
    tmp = Path(tempfile.gettempdir())

    png_blobs: list[bytes] = []
    for size in SIZES:
        pm = icons.render_logo(size)
        png = tmp / f"vroute_{size}.png"
        if not pm.save(str(png), "PNG"):
            print("failed to render", png)
            return 1
        png_blobs.append(png.read_bytes())
        png.unlink(missing_ok=True)

    out = bytearray()
    out += struct.pack("<HHH", 0, 1, len(SIZES))
    offset = 6 + 16 * len(SIZES)
    entries = b""
    for size, blob in zip(SIZES, png_blobs):
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    out += entries
    for blob in png_blobs:
        out += blob

    dest = Path(__file__).resolve().parents[1] / "assets" / "vroute.ico"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(bytes(out))
    print("icon written:", dest, f"({dest.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())