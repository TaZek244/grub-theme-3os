#!/usr/bin/env python3
"""sprites.py — sprite pixel-art gốc cho theme GRUB kiểu "bảng giờ tàu" hoài cổ (kafka).

Định nghĩa bản đồ ký tự (character maps) của đầu tàu, toa tàu và đường ray,
cùng bảng màu và hàm vẽ bằng pycairo. '.' = trong suốt (không có trong PALETTE).
"""

import sys

import cairo

# Bảng màu: ký tự đơn -> "#rrggbb" ('.' = trong suốt, không nằm trong PALETTE)
PALETTE = {
    "o": "#140e1a",  # viền tối (dark outline)
    "b": "#4a3f58",  # thân tàu mận (plum body) — sáng hơn để nổi trên nền tối
    "l": "#56466a",  # mận nhạt (light plum)
    "p": "#c94785",  # sọc hồng (pink stripe)
    "P": "#f08cbb",  # hồng nhạt (light pink)
    "w": "#ffd6ea",  # ánh sáng cửa sổ (window glow)
    "v": "#a37de0",  # lavender
    "W": "#fbf7fd",  # trắng (white)
    "d": "#7a6b8c",  # bánh xe (đủ sáng để thấy trên ray tối)
    "y": "#ffe08a",  # đèn pha vàng (headlight yellow)
}

# Đầu tàu tốc hành hoài cổ hướng TRÁI, 64 cột x 20 hàng.
# Mũi tàu tròn/ nghiêng bên trái, đèn pha trên mũi, sọc hồng ngang thân,
# 4 cửa sổ vuông phát sáng, bánh xe ở hàng 17..19, ăng-ten nhỏ trên nóc.
# Viền tối 1 pixel bao quanh toàn bộ hình dạng.
TRAIN_HEAD = [
    # 0 ăng-ten / pantograph trên nóc
    "." * 45 + "ovvo" + "." * 15,
    # 1
    "." * 45 + "v..v" + "." * 15,
    # 2
    "." * 46 + "vv" + "." * 16,
    # 3 nóc thân tàu
    "." * 14 + "o" * 48 + "." * 2,
    # 4 thân trên, mũi bắt đầu nghiêng
    "." * 11 + "oo" + "l" * 47 + "oo" + "." * 2,
    # 5
    "." * 8 + "oo" + "b" * 50 + "oo" + "." * 2,
    # 6
    "." * 5 + "oo" + "b" * 53 + "oo" + "." * 2,
    # 7
    "." * 3 + "o" + "b" * 56 + "o" + "." * 3,
    # 8 4 cửa sổ vuông phát sáng
    "." * 2 + "o" + "b" * 3 + "wwww" + "b" * 5 + "wwww" + "b" * 5 + "wwww" + "b" * 5 + "wwww" + "b" * 23 + "o" + "." * 3,
    # 9
    "." * 2 + "o" + "b" * 3 + "wwww" + "b" * 5 + "wwww" + "b" * 5 + "wwww" + "b" * 5 + "wwww" + "b" * 23 + "o" + "." * 3,
    # 10
    "." * 2 + "o" + "b" * 3 + "wwww" + "b" * 5 + "wwww" + "b" * 5 + "wwww" + "b" * 5 + "wwww" + "b" * 23 + "o" + "." * 3,
    # 11
    "." * 2 + "o" + "b" * 3 + "wwww" + "b" * 5 + "wwww" + "b" * 5 + "wwww" + "b" * 5 + "wwww" + "b" * 23 + "o" + "." * 3,
    # 12 đèn pha trên mũi (bên trái)
    "." * 1 + "o" + "yy" + "o" + "b" * 55 + "o" + "." * 3,
    # 13
    "." * 1 + "o" + "yy" + "o" + "b" * 55 + "o" + "." * 3,
    # 14 sọc hồng
    "." * 2 + "o" + "p" * 57 + "o" + "." * 3,
    # 15 sọc hồng nhạt
    "." * 3 + "o" + "P" * 56 + "o" + "." * 3,
    # 16 đáy thân tàu
    "." * 4 + "o" * 56 + "." * 4,
    # 17 bánh xe (hàng trên)
    "." * 8 + "oddo" + "." * 6 + "oddo" + "." * 10 + "oddo" + "." * 6 + "oddo" + "." * 18,
    # 18 bánh xe (giữa)
    "." * 8 + "oddo" + "." * 6 + "oddo" + "." * 10 + "oddo" + "." * 6 + "oddo" + "." * 18,
    # 19 bánh xe (hàng dưới)
    "." * 9 + "oo" + "." * 8 + "oo" + "." * 12 + "oo" + "." * 8 + "oo" + "." * 19,
]

# Toa hành khách, 56 cột x 20 hàng (cùng phong cách: đầu phẳng, 5 cửa sổ, sọc, bánh xe).
# Có móc nối (coupler) 2 cột ở mép trái.
TRAIN_CAR = [
    # 0
    "." * 56,
    # 1
    "." * 56,
    # 2
    "." * 56,
    # 3 nóc
    ".." + "o" * 52 + "..",
    # 4 vệt sáng mép nóc
    ".." + "o" + "l" * 50 + "o" + "..",
    # 5
    ".." + "o" + "b" * 50 + "o" + "..",
    # 6
    ".." + "o" + "b" * 50 + "o" + "..",
    # 7
    ".." + "o" + "b" * 50 + "o" + "..",
    # 8 5 cửa sổ
    ".." + "o" + "b" * 3 + "wwww" + "b" * 6 + "wwww" + "b" * 6 + "wwww" + "b" * 6 + "wwww" + "b" * 6 + "wwww" + "b" * 3 + "o" + "..",
    # 9
    ".." + "o" + "b" * 3 + "wwww" + "b" * 6 + "wwww" + "b" * 6 + "wwww" + "b" * 6 + "wwww" + "b" * 6 + "wwww" + "b" * 3 + "o" + "..",
    # 10
    ".." + "o" + "b" * 3 + "wwww" + "b" * 6 + "wwww" + "b" * 6 + "wwww" + "b" * 6 + "wwww" + "b" * 6 + "wwww" + "b" * 3 + "o" + "..",
    # 11
    ".." + "o" + "b" * 3 + "wwww" + "b" * 6 + "wwww" + "b" * 6 + "wwww" + "b" * 6 + "wwww" + "b" * 6 + "wwww" + "b" * 3 + "o" + "..",
    # 12
    ".." + "o" + "b" * 50 + "o" + "..",
    # 13 móc nối 2 cột bên trái
    "oo" + "o" + "b" * 50 + "o" + "..",
    # 14 sọc hồng
    "oo" + "p" * 51 + "o" + "..",
    # 15 sọc hồng nhạt
    ".o" + "P" * 51 + "o" + "..",
    # 16 đáy
    ".." + "o" * 52 + "..",
    # 17 bánh xe
    "." * 6 + "oddo" + "." * 6 + "oddo" + "." * 10 + "oddo" + "." * 6 + "oddo" + "." * 12,
    # 18
    "." * 6 + "oddo" + "." * 6 + "oddo" + "." * 10 + "oddo" + "." * 6 + "oddo" + "." * 12,
    # 19
    "." * 7 + "oo" + "." * 8 + "oo" + "." * 12 + "oo" + "." * 8 + "oo" + "." * 13,
]

# Ô đường ray lặp ngang, 16 cột x 4 hàng: thanh ray mận nhạt + tà vẹt mận sẫm bên dưới.
RAIL = [
    "llllllllllllllll",
    "bb..bbbb..bbbb..",
    "bb..bbbb..bbbb..",
    "................",
]


def _hex_to_rgb(h):
    """Đổi "#rrggbb" -> (r, g, b) trong [0, 1]."""
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255.0,
            int(h[2:4], 16) / 255.0,
            int(h[4:6], 16) / 255.0)


def sprite_size(sprite):
    """Trả về (cols, rows) của sprite."""
    if not sprite:
        return (0, 0)
    return (len(sprite[0]), len(sprite))


def draw_sprite(ctx, sprite, x, y, cell, alpha=1.0):
    """Vẽ sprite tại (x, y), mỗi ô kích thước cell x cell.

    Mỗi ký tự khác '.' được vẽ bằng màu trong PALETTE; các ô cùng ký tự
    liền nhau theo chiều ngang được gộp thành một hình chữ nhật.
    """
    for row_idx, row in enumerate(sprite):
        col_idx = 0
        width = len(row)
        while col_idx < width:
            ch = row[col_idx]
            if ch == ".":
                col_idx += 1
                continue
            run_start = col_idx
            while col_idx < width and row[col_idx] == ch:
                col_idx += 1
            r, g, b = _hex_to_rgb(PALETTE[ch])
            ctx.set_source_rgba(r, g, b, alpha)
            ctx.rectangle(x + run_start * cell, y + row_idx * cell,
                          (col_idx - run_start) * cell, cell)
            ctx.fill()


def draw_rail(ctx, x0, x1, y, cell):
    """Lát ô RAIL lặp ngang từ x0 đến x1 tại tung độ y."""
    cols, _rows = sprite_size(RAIL)
    tile_w = cols * cell
    if tile_w <= 0:
        return
    x = x0
    while x < x1:
        draw_sprite(ctx, RAIL, x, y, cell)
        x += tile_w


def selftest():
    """Kiểm tra sprite và vẽ ảnh xem trước. Trả về 0 nếu OK, ngược lại 1."""
    problems = []

    def check(name, sprite, expected_cols, expected_rows):
        if len(sprite) != expected_rows:
            problems.append(f"{name}: {len(sprite)} hàng (cần {expected_rows})")
        if not sprite:
            problems.append(f"{name}: sprite rỗng")
            return
        cols = len(sprite[0])
        for i, row in enumerate(sprite):
            if len(row) != cols:
                problems.append(f"{name} hàng {i}: {len(row)} cột (cần {cols})")
            for ch in row:
                if ch != "." and ch not in PALETTE:
                    problems.append(f"{name} hàng {i}: ký tự lạ {ch!r}")
        if cols != expected_cols:
            problems.append(f"{name}: {cols} cột (cần {expected_cols})")

    check("TRAIN_HEAD", TRAIN_HEAD, 64, 20)
    check("TRAIN_CAR", TRAIN_CAR, 56, 20)
    check("RAIL", RAIL, 16, 4)

    # Vẽ đầu tàu + 2 toa + đường ray ở kích thước cell 3
    try:
        cell = 3
        head_w, head_h = sprite_size(TRAIN_HEAD)
        car_w, car_h = sprite_size(TRAIN_CAR)
        rail_w, rail_h = sprite_size(RAIL)
        margin = 10
        total_w = (head_w + car_w * 2) * cell + margin * 2
        train_y = margin
        rail_y = train_y + head_h * cell
        total_h = rail_y + rail_h * cell + margin
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, total_w, total_h)
        ctx = cairo.Context(surf)
        # nền tối
        ctx.set_source_rgb(0.08, 0.05, 0.10)
        ctx.paint()
        x = margin
        draw_sprite(ctx, TRAIN_HEAD, x, train_y, cell)
        x += head_w * cell
        draw_sprite(ctx, TRAIN_CAR, x, train_y, cell)
        x += car_w * cell
        draw_sprite(ctx, TRAIN_CAR, x, train_y, cell)
        draw_rail(ctx, 0, total_w, rail_y, cell)
        out = "/tmp/kafka-train-preview.png"
        try:
            surf.write_to_png(out)
        except Exception:
            out = "kafka-train-preview.png"
            surf.write_to_png(out)
    except Exception as e:
        problems.append(f"vẽ preview: {e}")

    if problems:
        for p in problems:
            print(p)
        return 1
    print("selftest: OK")
    return 0


if __name__ == "__main__":
    sys.exit(selftest())
