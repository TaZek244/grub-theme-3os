#!/usr/bin/env python3
"""make-icons.py — sinh icon pixel-art 16x16 cho theme GRUB "KAFKA.SYS" (thư mục kafka/).

Mỗi icon là một bản đồ ký tự trong ICONS: 16 dòng x 16 cột, '.' = trong suốt,
mỗi ký tự còn lại là một khoá của PALETTE. Viền tối 1 ô (#140e1a) và điểm sáng
góc trên-trái được nắn thẳng vào bản đồ để icon đọc được trên mọi nền.

Vẽ bằng tay, không PIL / không công cụ ngoài: xuất PNG RGBA qua zlib + struct.
GRUB chọn icon theo class của menuentry nên tên file đúng là <class>.png.

Dùng:
  make-icons.py OUTDIR [--scale N]     # ghi 9 file icon (mặc định N=4 -> 64x64)
  make-icons.py --preview FILE.png     # một dải xem trước tất cả icon
  make-icons.py --selftest             # kiểm tra bản đồ + giải mã PNG
"""

import argparse
import os
import shutil
import struct
import sys
import tempfile
import zlib

GRID = 16
ICON_ORDER = ["arch", "windows", "ubuntu", "gnu-linux", "efi", "restart",
              "shutdown", "triboot", "kafka"]

# Chars -> RGBA (0..255). '.' không nằm ở đây: nó là ô trong suốt.
PALETTE = {
    "o": (0x14, 0x0e, 0x1a, 255),   # viền tối
    "w": (0xfb, 0xf7, 0xfd, 255),   # trắng
    "p": (0xc9, 0x47, 0x85, 255),   # hồng KAFKA
    "P": (0xf0, 0x8c, 0xbb, 255),   # hồng nhạt
    "l": (0xa3, 0x7d, 0xe0, 255),   # lavender
    "L": (0xd2, 0xb8, 0xf2, 255),   # lavender nhạt (highlight)
    "s": (0xe0, 0x50, 0x6e, 255),   # đỏ/hồng nút nguồn
    "a": (0x17, 0x93, 0xd1, 255),   # xanh Arch
    "A": (0x7f, 0xd0, 0xf5, 255),   # xanh Arch nhạt
    "b": (0x00, 0xa4, 0xef, 255),   # xanh Windows
    "B": (0x6f, 0xc9, 0xf5, 255),   # xanh Windows nhạt
    "u": (0xe9, 0x54, 0x20, 255),   # cam Ubuntu
    "U": (0xff, 0x8c, 0x42, 255),   # cam Ubuntu nhạt
    "g": (0x8b, 0x7f, 0xa8, 255),   # xám lavender (chip EFI)
    "G": (0xc4, 0xb9, 0xdd, 255),   # xám lavender nhạt
    "d": (0x30, 0x26, 0x3c, 255),   # thân nhện màu tím mận
    "m": (0x4a, 0x3a, 0x5a, 255),   # tím mận nhạt (bụng nhện)
}

ICONS = {
    # A mountain / Arch blue triangle, notch ở đáy, mép trái trên sáng.
    "arch": [
        "................",
        ".......oo.......",
        "......oAAo......",
        "......oaao......",
        ".....oAaaao.....",
        ".....oaaaao.....",
        "....oAaaaaao....",
        "....oaaaaaao....",
        "...oAaaaaaaao...",
        "...oaaaaaaaao...",
        "..oAaaaaaaaaao..",
        "..oaaaaaaaaaao..",
        ".oaaaaa..aaaaao.",
        "................",
        "................",
        "................",
    ],
    # Bốn ô vuông 2x2, mỗi ô có viền tối + một điểm sáng trên-trái.
    "windows": [
        "................",
        "................",
        "................",
        "..ooooo..ooooo..",
        "..oBbbo..oBbbo..",
        "..obbbo..obbbo..",
        "..obbbo..obbbo..",
        "..ooooo..ooooo..",
        "................",
        "..ooooo..ooooo..",
        "..oBbbo..oBbbo..",
        "..obbbo..obbbo..",
        "..obbbo..obbbo..",
        "..ooooo..ooooo..",
        "................",
        "................",
    ],
    # Vòng tròn cam + 3 chấm (circle of friends), chấm có viền tối.
    "ubuntu": [
        "......ouuo......",
        ".....ouuuuo.....",
        ".....ouuuuo.....",
        "....oUouuouo....",
        "...oUUuoouuuo...",
        "..oUUoo..oouuo..",
        "..oUuo....ouuo..",
        "..oUo......ouo..",
        "..oUo......ouo..",
        ".ouo........ouo.",
        "ouuuooo..ooouuuo",
        "ouuuouuoouuouuuo",
        ".ouoouuuuuuoouo.",
        "..o..oooooo..o..",
        "................",
        "................",
    ],
    # Hộp terminal: thanh tiêu đề có 3 nút, màn hình tối, dấu ">_" lavender.
    "gnu-linux": [
        "................",
        "................",
        ".oooooooooooooo.",
        ".oLolollllllllo.",
        ".oooooooooooooo.",
        ".oLdddddddddddo.",
        ".odLddddddddddo.",
        ".oddLdddddddddo.",
        ".odddLddddddddo.",
        ".oddLdddddddddo.",
        ".odLdddLLLLdddo.",
        ".oddddddddddddo.",
        ".oddddddddddddo.",
        ".oooooooooooooo.",
        "................",
        "................",
    ],
    # Chip EFI: thân xám lavender, 3 chân mỗi cạnh, điểm sáng góc trên-trái.
    "efi": [
        "................",
        "................",
        "................",
        "......o.o.o.....",
        "......g.g.g.....",
        ".....oooooo.....",
        "...ogoGgggogo...",
        ".....oggggo.....",
        "...ogoggggogo...",
        ".....oggggo.....",
        "...ogoggggogo...",
        ".....oooooo.....",
        "......g.g.g.....",
        "......o.o.o.....",
        "................",
        "................",
    ],
    # Mũi tên vòng tròn hồng, có khe hở ở trên và đầu mũi tên.
    "restart": [
        "..........oooo..",
        "......ooooppppo.",
        "....ooPppoopppo.",
        "...oPPPppo.oppo.",
        "..oPPppoo...opo.",
        "..oPpoo......o..",
        ".oPpo.......opo.",
        ".oPpo......oppo.",
        ".oPpo......oppo.",
        ".oPpo......oppo.",
        ".oPpo......oppo.",
        "..oppoo..ooppo..",
        "..oppppooppppo..",
        "...oppppppppo...",
        "....ooppppoo....",
        "......oooo......",
    ],
    # Biểu tượng nguồn: vòng hồng/đỏ hở đỉnh + thanh dọc ở giữa.
    "shutdown": [
        "................",
        ".......oo.......",
        "....o.oPso.o....",
        "...oPoossooso...",
        "..oPPsossossso..",
        "..oPsoossoosso..",
        ".oPso.osso.osso.",
        ".oPso.osso.osso.",
        ".oPso.osso.osso.",
        ".oPso..oo..osso.",
        ".oPso......osso.",
        "..ossoo..oosso..",
        "..ossssoosssso..",
        "...osssssssso...",
        "....oossssoo....",
        "......oooo......",
    ],
    # Nhện nhỏ: thân tím mận tròn, 8 chân, kính mát hồng.
    "triboot": [
        "................",
        ".o............o.",
        "olo..........olo",
        ".olo..oooo..olo.",
        "o.olooddddoolo.o",
        "looooddddddooool",
        "olloddmdddddollo",
        ".oolddddddddloo.",
        "..odPppooPppdo..",
        "..oddppddppddo..",
        ".ollddddddddllo.",
        "oloodddmmdddoolo",
        "lo..oddmmddo..ol",
        "o..oloddddolo..o",
        "..olo.oooo.olo..",
        ".olo........olo.",
    ],
}
# kafka.png cùng thiết kế với triboot.png (chia sẻ danh sách).
ICONS["kafka"] = ICONS["triboot"]


def write_png(path, w, h, rgba_bytes):
    """Ghi ảnh PNG RGBA 8-bit bằng zlib + struct (không cần thư viện ngoài)."""
    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff))

    raw = bytearray()
    stride = w * 4
    for y in range(h):
        raw.append(0)                       # filter type 0 (None)
        raw += rgba_bytes[y * stride:(y + 1) * stride]
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


def read_png_info(path):
    """Bộ đọc PNG tối giản cho --selftest: trả (w, h, raw) hoặc raise ValueError."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("signature PNG sai")
    pos, w, h, idat = 8, None, None, bytearray()
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        tag = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        crc = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])[0]
        if len(payload) != length or (zlib.crc32(tag + payload) & 0xffffffff) != crc:
            raise ValueError("chunk PNG hỏng")
        if tag == b"IHDR":
            w, h = struct.unpack(">II", payload[:8])
        elif tag == b"IDAT":
            idat += payload
        elif tag == b"IEND":
            break
        pos += 12 + length
    if w is None or h is None:
        raise ValueError("thiếu IHDR")
    raw = zlib.decompress(bytes(idat))
    if len(raw) != h * (1 + w * 4):
        raise ValueError("kích thước dữ liệu ảnh sai")
    return w, h, raw


def icon_canvas(name, scale):
    """Phóng bản đồ 16x16 lên (16*scale)^2 px, nearest-neighbour, RGBA bytes."""
    rows = ICONS[name]
    size = GRID * scale
    out = bytearray(size * size * 4)
    for gy, row in enumerate(rows):
        for gx, ch in enumerate(row):
            if ch == ".":
                continue
            px = bytes(PALETTE[ch])
            for sy in range(scale):
                base = ((gy * scale + sy) * size + gx * scale) * 4
                for sx in range(scale):
                    off = base + sx * 4
                    out[off:off + 4] = px
    return bytes(out)


def build(outdir, scale):
    os.makedirs(outdir, exist_ok=True)
    for name in ICON_ORDER:
        write_png(os.path.join(outdir, name + ".png"),
                  GRID * scale, GRID * scale, icon_canvas(name, scale))


def make_preview(path, scale):
    """Một dải ảnh: các icon xếp hàng ngang trên nền #261e30 để dễ review."""
    cell = GRID * scale
    gap, pad = scale, scale * 2
    width = pad * 2 + len(ICON_ORDER) * cell + (len(ICON_ORDER) - 1) * gap
    height = pad * 2 + cell
    bg = (0x26, 0x1e, 0x30, 255)
    out = bytearray(bg * (width * height))
    for i, name in enumerate(ICON_ORDER):
        img = icon_canvas(name, scale)
        ox = pad + i * (cell + gap)
        for y in range(cell):
            src = y * cell * 4
            dst = ((pad + y) * width + ox) * 4
            out[dst:dst + cell * 4] = img[src:src + cell * 4]
    write_png(path, width, height, bytes(out))


def selftest():
    ok = True

    def fail(msg):
        nonlocal ok
        print("LỖI:", msg)
        ok = False

    if set(ICONS) != set(ICON_ORDER):
        fail("tập ICONS không khớp ICON_ORDER")
    for name, rows in ICONS.items():
        if len(rows) != GRID:
            fail(f"{name}: {len(rows)} dòng (cần 16)")
            continue
        for y, row in enumerate(rows):
            if len(row) != GRID:
                fail(f"{name} dòng {y}: {len(row)} cột (cần 16)")
            for ch in row:
                if ch != "." and ch not in PALETTE:
                    fail(f"{name} dòng {y}: ký tự lạ {ch!r}")
        opaque = sum(1 for row in rows for ch in row if ch != ".")
        if opaque < 20:
            fail(f"{name}: chỉ {opaque} ô không trong suốt (cần >= 20)")

    tmp = tempfile.mkdtemp(prefix="kafka-icons-")
    try:
        build(tmp, 4)
        for name in ICON_ORDER:
            p = os.path.join(tmp, name + ".png")
            try:
                w, h, _ = read_png_info(p)
                if (w, h) != (64, 64):
                    fail(f"{name}.png: kích thước {w}x{h} (cần 64x64)")
            except (OSError, ValueError, zlib.error) as e:
                fail(f"{name}.png: không giải mã được ({e})")
        prev = os.path.join(tmp, "preview.png")
        make_preview(prev, 4)
        try:
            read_png_info(prev)
        except (OSError, ValueError, zlib.error) as e:
            fail(f"preview.png: không giải mã được ({e})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("selftest:", "OK" if ok else "LỖI")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("outdir", nargs="?")
    ap.add_argument("--scale", type=int, default=4, help="px mỗi ô (mặc định 4)")
    ap.add_argument("--preview", metavar="FILE.png", help="ghi dải xem trước")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.scale < 1:
        ap.error("--scale phải >= 1")
    if a.preview:
        make_preview(a.preview, a.scale)
        return 0
    if not a.outdir:
        ap.error("thiếu OUTDIR (hoặc dùng --preview / --selftest)")
    build(a.outdir, a.scale)
    return 0


if __name__ == "__main__":
    sys.exit(main())
