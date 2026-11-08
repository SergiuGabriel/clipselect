"""Builds icon.icns (macOS), icon.ico (Windows) and icon.png (window icon) from icon_source.png. Run before PyInstaller."""
import io
import struct
import sys
from pathlib import Path

from PIL import Image

src_path = Path("icon_source.png")
if not src_path.exists():
    sys.exit("icon_source.png is missing from the repository root - upload it (1024x1024 PNG).")
src = Image.open(src_path).convert("RGBA")
if src.size[0] != src.size[1]:
    side = min(src.size)
    src = src.crop(((src.size[0] - side) // 2, (src.size[1] - side) // 2, (src.size[0] + side) // 2, (src.size[1] + side) // 2))

# --- macOS .icns written by hand: PNG payloads in the standard 'ic0x/icp' chunks
chunks = [(b"icp4", 16), (b"icp5", 32), (b"icp6", 64), (b"ic07", 128), (b"ic08", 256), (b"ic09", 512), (b"ic10", 1024),
          (b"ic11", 32), (b"ic12", 64), (b"ic13", 256), (b"ic14", 512)]
body = b""
for tag, size in chunks:
    buf = io.BytesIO()
    src.resize((size, size), Image.LANCZOS).save(buf, "PNG")
    data = buf.getvalue()
    body += tag + struct.pack(">I", len(data) + 8) + data
Path("icon.icns").write_bytes(b"icns" + struct.pack(">I", len(body) + 8) + body)

# --- Windows .ico and runtime window icon
src.save("icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
src.resize((256, 256), Image.LANCZOS).save("icon.png", optimize=True)
print("icons built:", [p for p in ("icon.icns", "icon.ico", "icon.png") if Path(p).exists()])
