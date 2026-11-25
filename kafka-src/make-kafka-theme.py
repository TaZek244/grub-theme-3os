#!/usr/bin/env python3
"""make-kafka-theme.py — sinh theme GRUB "KAFKA.SYS // DEPARTURES" (thư mục kafka/): ảnh + theme.txt + khung intro.

Ý tưởng: bootloader là một NHÀ GA. Mỗi hệ điều hành là một "điểm đến" trên BẢNG GIỜ TÀU LED
(khung kim loại có đinh tán, nền đen chấm LED, cột NO. / DESTINATION, chữ hồng phát sáng),
thanh đếm ngược là "chuyến kế tiếp khởi hành sau %d giây", đáy màn là đường ray với đoàn tàu pixel đang đỗ.
Kafka đứng ở phần ba bên phải (ảnh nền được dời sang phải); không có thẻ ảnh/cửa sổ như màn đăng nhập.

GRUB không vẽ được những thứ này và không có animation, nên:
  * mọi thứ tĩnh được VẼ SẴN vào background.png ở toạ độ cố định 1920x1080;
  * theme.txt do script này sinh (cùng bảng LAYOUT, không lệch toạ độ);
  * hiệu ứng xuất hiện = chuỗi intro-NN.png + intro.txt (thời gian giữ, 1/100 s): tàu chạy vào ga và dừng,
    bảng bật nguồn, các hàng chữ LẬT loạn xạ rồi dừng lại → menu. /etc/grub.d/05_kafka_intro (lib/kafka.sh)
    vẽ từng khung bằng `background_image` + `clear`, chờ bằng `play 6000 0 N` (kafka-src/intro-cfg.sh).

Dùng:
  make-kafka-theme.py OUTDIR [--bg ẢNH] [--no-intro]
  make-kafka-theme.py --selftest | --print-layout
--bg: ảnh nền (pixel hoá về 480x270). Không có thì tự vẽ chạng vạng tím + chú nhện (không cần ảnh bản quyền).
"""

import argparse
import os
import random
import shutil
import subprocess
import sys
import tempfile

import cairo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pixelfont as pf  # noqa: E402

try:
    import sprites  # noqa: E402  (đoàn tàu + đường ray pixel)
except Exception:  # pragma: no cover
    sprites = None

W, H = 1920, 1080
P0 = 4                    # lưới nền
BG_SHIFT = 424            # dời ảnh nền sang phải để Kafka đứng ở phần ba bên phải (bội số của ô ảnh)


def hexc(h, a=1.0):
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)


C = {
    "edge": hexc("#140e1a"), "text": hexc("#fbf7fd"), "dim": hexc("#d4cade"), "faint": hexc("#9a8bab"),
    "pink": hexc("#c94785"), "pink_hi": hexc("#f08cbb"), "pink_edge": hexc("#3d1028"),
    "shadow": hexc("#0b0710", 0.85),
    # khung kim loại của bảng
    "metal": hexc("#2c2436"), "metal_hi": hexc("#4a3f58"), "metal_sh": hexc("#17111d"), "rivet": hexc("#6b5d7c"),
    # mặt LED
    "led_bg": hexc("#0c0910"), "led_dot": hexc("#1d1526"), "led_off": hexc("#3a2a3f"), "led": hexc("#f08cbb"),
    "led_glow": hexc("#f08cbb", 0.22), "led_green": hexc("#7fd6a8"),
}

# ---- Bố cục (px, màn 1920x1080). theme.txt sinh từ đây.
BOARD = (80, 150, 1080, 790)          # khung bảng (gồm viền kim loại)
BEZEL = 24
INNER = (BOARD[0] + BEZEL, BOARD[1] + BEZEL, BOARD[2] - 2 * BEZEL, BOARD[3] - 2 * BEZEL)
COL_NO = INNER[0] + 32                # cột số thứ tự
ITEM_H, ITEM_SP, ICON = 68, 8, 48
LAYOUT = {
    "board": BOARD,
    "subtitle": (INNER[0] + 32, 250),                         # "CHỌN ĐIỂM ĐẾN" dưới chữ DEPARTURES (label GRUB, font 28)
    "colhead_y": 312,
    "menu": (INNER[0] + 112, 352, INNER[2] - 112 - 32, 6 * (ITEM_H + ITEM_SP) + 30),   # +30: viền khung chọn
    "count": (INNER[0] + 32, 858, 520),                        # label "khởi hành sau %d giây" (font 28)
    "bar": (INNER[0] + 600, 870, INNER[2] - 600 - 32, 12),     # GRUB vẽ cao ~20 (font cỡ 7)
    "hint_y": BOARD[1] + BOARD[3] - BEZEL + 6,                 # chữ gợi ý phím trên viền đáy
    "rail_y": 1036,
    "train_x": 1300,
}


# ---------------------------------------------------------------- vẽ cơ bản
def rect(ctx, x, y, w, h, col):
    ctx.set_source_rgba(*col)
    ctx.rectangle(x, y, w, h)
    ctx.fill()


def text(ctx, s, x, y, cell, col, shadow=True):
    pf.draw_text(ctx, s, x, y, cell, col, C["shadow"] if shadow else None)


def led_text(ctx, s, x, y, cell, col=None):
    """Chữ LED: quầng mờ quanh nét + nét sáng."""
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
        pf.draw_text(ctx, s, x + dx, y + dy, cell, C["led_glow"])
    pf.draw_text(ctx, s, x, y, cell, col or C["led"])


def _imagemagick():
    """Trả về list lệnh ImageMagick (magick hoặc convert), None nếu không có."""
    if shutil.which("magick"):
        return ["magick"]
    if shutil.which("convert"):
        return ["convert"]
    return None


def load_surface(path):
    if not path or not os.path.isfile(path):
        return None
    tmp = None
    if not path.lower().endswith(".png"):
        cmd = _imagemagick()
        if cmd is None:
            return None
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        try:
            subprocess.run(cmd + [path, tmp.name], check=True)
        except Exception:
            os.unlink(tmp.name)
            raise
        path = tmp.name
    try:
        return cairo.ImageSurface.create_from_png(path)
    except Exception:
        return None
    finally:
        if tmp:
            os.unlink(tmp.name)


def pixelize(path):
    """Ảnh nền → 480x270 bảng 48 màu (ô 4px ở 1080p). bg-pixel.png (240x135) của greeter thì giữ nguyên."""
    if not path or not os.path.isfile(path):
        return None
    if os.path.basename(path) == "bg-pixel.png" or _imagemagick() is None:
        return load_surface(path)
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    subprocess.run(_imagemagick() + [path, "-resize", "480x270^", "-gravity", "center", "-extent", "480x270",
                    "-modulate", "92,112", "-dither", "FloydSteinberg", "-colors", "48",
                    "-fill", "#140e1c", "-colorize", "30%", tmp.name], check=True)
    s = load_surface(tmp.name)
    os.unlink(tmp.name)
    return s


# ---------------------------------------------------------------- các lớp
def draw_background(ctx, bg):
    rect(ctx, 0, 0, W, H, hexc("#120c17"))
    if bg:
        bw, bh = bg.get_width(), bg.get_height()
        s = max(W / bw, H / bh)
        ctx.save()
        ctx.translate((W - bw * s) / 2 + BG_SHIFT, (H - bh * s) / 2)
        ctx.scale(s, s)
        ctx.set_source_surface(bg, 0, 0)
        ctx.get_source().set_filter(cairo.FILTER_NEAREST)
        ctx.paint()
        ctx.restore()
        for i in range(12):                       # mép trái ảnh sau khi dời: tối dần thành nền (bậc thang)
            rect(ctx, BG_SHIFT + i * 2 * P0, 0, 2 * P0, H, (0.07, 0.05, 0.09, 1 - (i + 1) / 13))
    else:
        steps = 18
        for i in range(steps):
            k = i / (steps - 1)
            ctx.set_source_rgb(0.08 + 0.18 * k, 0.05 + 0.04 * k, 0.11 + 0.10 * k)
            ctx.rectangle(0, H * i / steps, W, H / steps + 1)
            ctx.fill()
        pf.draw_icon(ctx, "spider", 1300, 260, 40, hexc("#c94785", 0.16))      # nhện lớn mờ chỗ Kafka đứng
    rings = 10                                    # vignette bậc thang
    for i in range(rings):
        ctx.set_source_rgba(0.04, 0.02, 0.06, 0.05 * (rings - i) / rings)
        ins = i * 6 * P0
        ctx.rectangle(0, 0, W, H)
        ctx.rectangle(ins, ins, W - 2 * ins, H - 2 * ins)
        ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        ctx.fill()
    ctx.set_fill_rule(cairo.FILL_RULE_WINDING)
    ctx.set_source_rgba(0.06, 0.03, 0.08, 0.30)
    ctx.paint()
    ctx.set_source_rgba(0, 0, 0, 0.10)            # scanline
    for y in range(0, H, 2 * P0):
        ctx.rectangle(0, y, W, 2)
    ctx.fill()
    rnd = random.Random(1924)                     # mưa pixel
    for _ in range(W // (P0 * 5)):
        x = rnd.randrange(0, W // P0) * P0
        y = rnd.randrange(0, H // P0) * P0
        ln = rnd.choice((3, 4, 5, 6))
        a = 0.16 + 0.22 * rnd.random()
        rect(ctx, x, y, P0, ln * P0, (0.94, 0.55, 0.73, a))
        rect(ctx, x, y + ln * P0, P0, P0, (1, 0.85, 0.93, a + 0.15))


def draw_train(ctx, x, rail_y):
    cell = 3
    if sprites:
        hw, hh = sprites.sprite_size(sprites.TRAIN_HEAD)
        cw, _ = sprites.sprite_size(sprites.TRAIN_CAR)
        y = rail_y - hh * cell + 2 * cell
        sprites.draw_sprite(ctx, sprites.TRAIN_HEAD, x, y, cell)
        cx = x + hw * cell
        while cx < W:
            sprites.draw_sprite(ctx, sprites.TRAIN_CAR, cx, y, cell)
            cx += cw * cell
    else:
        rect(ctx, x, rail_y - 60, W - x, 56, C["metal"])
        rect(ctx, x, rail_y - 36, W - x, 8, C["pink"])


def draw_scene(ctx, train_x):
    """Đường ray + mép sân ga + đoàn tàu + chữ góc trên."""
    ry = LAYOUT["rail_y"]
    rect(ctx, 0, ry + 12, W, H - ry - 12, hexc("#0e0a12", 0.92))
    if sprites:
        sprites.draw_rail(ctx, 0, W, ry, 4)
    else:
        rect(ctx, 0, ry, W, 4, C["metal_hi"])
        for x in range(0, W, 32):
            rect(ctx, x, ry + 4, 16, 8, C["metal"])
    if train_x is not None and train_x < W:
        draw_train(ctx, train_x, ry)
    for x in range(0, W, 24):                     # vạch cảnh báo mép sân ga
        rect(ctx, x, ry - 76, 12, 4, hexc("#f08cbb", 0.35))
    pf.draw_icon(ctx, "spider", 80, 58, 4, C["pink_hi"])
    text(ctx, "KAFKA.SYS // BOOT TERMINAL", 80 + 36 + 16, 62, 4, C["text"])
    q = "LISTEN TO THE SOUND OF THE RAIN..."
    text(ctx, q, W - 80 - pf.text_width(q, 3), 66, 3, C["dim"])


def draw_board(ctx, state="on", scramble=0):
    """state: 'off' (chỉ khung, LED tắt) | 'on'. scramble > 0: các hàng hiện ký tự lật loạn (hạt giống = scramble)."""
    bx, by, bw, bh = BOARD
    rect(ctx, bx + 12, by + 12, bw, bh, (0.03, 0.02, 0.05, 0.6))               # bóng cứng
    rect(ctx, bx, by, bw, bh, C["edge"])
    rect(ctx, bx + 4, by + 4, bw - 8, bh - 8, C["metal"])
    rect(ctx, bx + 4, by + 4, bw - 8, 4, C["metal_hi"])
    rect(ctx, bx + 4, by + 4, 4, bh - 8, C["metal_hi"])
    rect(ctx, bx + 4, by + bh - 8, bw - 8, 4, C["metal_sh"])
    rect(ctx, bx + bw - 8, by + 4, 4, bh - 8, C["metal_sh"])
    for (x, y) in ((bx + 10, by + 10), (bx + bw - 18, by + 10), (bx + 10, by + bh - 18), (bx + bw - 18, by + bh - 18),
                   (bx + bw // 2 - 4, by + 10), (bx + bw // 2 - 4, by + bh - 18)):
        rect(ctx, x, y, 8, 8, C["edge"])                                        # đinh tán
        rect(ctx, x, y, 4, 4, C["rivet"])
    ix, iy, iw, ih = INNER
    rect(ctx, ix - 4, iy - 4, iw + 8, ih + 8, C["edge"])
    rect(ctx, ix, iy, iw, ih, C["led_bg"])
    ctx.set_source_rgba(*C["led_dot"])                                          # lưới chấm LED
    for y in range(iy + 3, iy + ih, 6):
        for x in range(ix + 3, ix + iw, 6):
            ctx.rectangle(x, y, 2, 2)
    ctx.fill()
    hint = "UP/DN: SELECT    ENTER: BOARD    E: EDIT    C: CMD"
    text(ctx, hint, bx + (bw - pf.text_width(hint, 2)) // 2, LAYOUT["hint_y"], 2, C["dim"], shadow=False)
    if state == "off":
        return
    rnd = random.Random(scramble or 1)
    glyphs = [g for g in pf.GLYPHS if g.strip() and g not in "<>"]

    def maybe(s):
        if not scramble:
            return s
        return "".join(rnd.choice(glyphs) if ch != " " and rnd.random() < 0.7 else ch for ch in s)

    led_text(ctx, maybe("DEPARTURES"), ix + 32, iy + 22, 7)
    tag = "TERMINAL 01"
    tw = pf.text_width(tag, 3)
    pf.draw_text(ctx, tag, ix + iw - 32 - tw, iy + 30, 3, C["faint"])
    rect(ctx, ix + iw - 32 - tw - 22, iy + 32, 12, 12, C["led_green"])         # đèn "đang chạy"
    tag2 = "PLATFORM // UEFI"
    pf.draw_text(ctx, tag2, ix + iw - 32 - pf.text_width(tag2, 2), iy + 60, 2, C["led_off"])
    cy = LAYOUT["colhead_y"]
    pf.draw_text(ctx, "NO.", COL_NO, cy, 3, C["faint"])
    pf.draw_text(ctx, "DESTINATION", LAYOUT["menu"][0] + ICON + 24, cy, 3, C["faint"])
    st = "STATUS: ON TIME"
    pf.draw_text(ctx, st, ix + iw - 32 - pf.text_width(st, 3), cy, 3, C["led_green"])
    for x in range(ix + 24, ix + iw - 24, 8):
        rect(ctx, x, cy + 30, 4, 2, C["led_off"])
    mx, my, mw, mh = LAYOUT["menu"]
    for i in range(6):
        ry = my + 8 + i * (ITEM_H + ITEM_SP)
        # số thứ tự = LED tối (hàng trống trông như đèn chưa bật)
        pf.draw_text(ctx, f"{i + 1:02d}", COL_NO, ry + (ITEM_H - 28) // 2, 4, C["led_off"])
        if i:
            for x in range(ix + 24, ix + iw - 24, 12):
                rect(ctx, x, ry - ITEM_SP // 2 - 1, 4, 2, C["led_dot"])
        if scramble:                              # chữ lật loạn đúng chỗ GRUB sẽ in tên điểm đến
            n = rnd.randrange(6, 14)
            led_text(ctx, "".join(rnd.choice(glyphs) for _ in range(n)), mx + ICON + 24, ry + (ITEM_H - 35) // 2, 5)
    rect(ctx, ix + 16, LAYOUT["count"][1] - 16, iw - 32, 2, C["led_off"])      # vạch trên dải đếm ngược


def nine(path_prefix, w, h, border, draw):
    """Vẽ hộp w×h rồi cắt 9 mảnh GRUB: prefix_{nw,n,ne,w,c,e,sw,s,se}.png, viền `border` px."""
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(surf)
    draw(ctx)
    b = border
    parts = {
        "nw": (0, 0, b, b), "n": (b, 0, w - 2 * b, b), "ne": (w - b, 0, b, b),
        "w": (0, b, b, h - 2 * b), "c": (b, b, w - 2 * b, h - 2 * b), "e": (w - b, b, b, h - 2 * b),
        "sw": (0, h - b, b, b), "s": (b, h - b, w - 2 * b, b), "se": (w - b, h - b, b, b),
    }
    for k, (x, y, pw, ph) in parts.items():
        out = cairo.ImageSurface(cairo.FORMAT_ARGB32, pw, ph)
        c2 = cairo.Context(out)
        c2.set_source_surface(surf, -x, -y)
        c2.paint()
        out.write_to_png(f"{path_prefix}_{k}.png")


def make_styles(outdir):
    def sel(ctx):          # mục đang chọn: vạch LED đảo màu (nền hồng sáng, chữ tối), khấc tối ở mép trái
        rect(ctx, 0, 0, 18, 18, C["led"])
        rect(ctx, 0, 0, 18, 2, hexc("#ffd6ea"))
        rect(ctx, 0, 16, 18, 2, C["pink"])
        rect(ctx, 0, 0, 4, 18, C["pink_edge"])
        rect(ctx, 4, 0, 2, 18, hexc("#ffd6ea"))
    nine(os.path.join(outdir, "select"), 18, 18, 6, sel)

    def bar(ctx):          # rãnh thanh đếm ngược
        rect(ctx, 0, 0, 12, 12, C["led_off"])
        rect(ctx, 3, 3, 6, 6, C["led_bg"])
    nine(os.path.join(outdir, "bar"), 12, 12, 3, bar)

    def hl(ctx):           # phần đã chạy
        rect(ctx, 0, 0, 12, 12, C["led"])
        rect(ctx, 0, 9, 12, 3, C["pink"])
    nine(os.path.join(outdir, "bar_hl"), 12, 12, 3, hl)


def theme_txt():
    mx, my, mw, mh = LAYOUT["menu"]
    bx, by, bw, bh = LAYOUT["bar"]
    cx, cy, cw = LAYOUT["count"]
    sx, sy = LAYOUT["subtitle"]
    return f'''# KAFKA.SYS // DEPARTURES — theme GRUB pixel kiểu bảng giờ tàu LED ở nhà ga (dotfiles Hyprland Kafka)
# FILE TỰ SINH bởi kafka-src/make-kafka-theme.py (bảng LAYOUT) — sửa ở đó rồi chạy ./install.sh --kafka-assets.
# Toạ độ cố định cho 1920x1080; bảng, đoàn tàu, chữ tĩnh đã vẽ sẵn vào background.png.
# Thanh đếm ngược: GRUB ép cao tối thiểu = chiều cao font của nó và nới ngang theo chữ bên trong,
# nên thanh không có chữ + font cỡ 7 tí hon; dòng đếm ngược là label riêng.
title-text: ""
desktop-image: "background.png"
desktop-color: "#120c17"
terminal-font: "Kafka Mono Bold 20"
terminal-box: "bar_*.png"
terminal-left: "10%"
terminal-top: "10%"
terminal-width: "80%"
terminal-height: "80%"

+ label {{
    left = {sx}
    top = {sy}
    width = 700
    align = "left"
    text = "Chọn điểm đến"
    font = "Kafka Pixel VN Regular 28"
    color = "#d4cade"
}}

+ boot_menu {{
    left = {mx}
    top = {my}
    width = {mw}
    height = {mh}
    item_font = "Kafka Pixel VN Regular 35"
    item_color = "#f08cbb"
    selected_item_font = "Kafka Pixel VN Regular 42"
    selected_item_color = "#1a0d16"
    icon_width = {ICON}
    icon_height = {ICON}
    item_icon_space = 24
    item_height = {ITEM_H}
    item_padding = 0
    item_spacing = {ITEM_SP}
    selected_item_pixmap_style = "select_*.png"
    scrollbar = false
}}

+ label {{
    id = "__timeout__"
    left = {cx}
    top = {cy}
    width = {cw}
    align = "left"
    text = "Khởi hành sau %d giây"
    font = "Kafka Pixel VN Regular 28"
    color = "#f08cbb"
}}

+ progress_bar {{
    id = "__timeout__"
    left = {bx}
    top = {by}
    width = {bw}
    height = {bh}
    bar_style = "bar_*.png"
    highlight_style = "bar_hl_*.png"
    font = "Kafka Pixel VN Regular 7"
    text = ""
}}
'''


# ---------------------------------------------------------------- ghép khung
def compose(base, board=None, scramble=0, train_x=None, dark=0.0, flash=0.0):
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
    ctx = cairo.Context(surf)
    ctx.set_source_surface(base, 0, 0)
    ctx.paint()
    if dark:
        rect(ctx, 0, 0, W, H, (0.02, 0.01, 0.03, dark))
    draw_scene(ctx, LAYOUT["train_x"] if train_x is None else train_x)
    if board:
        draw_board(ctx, board, scramble)
    if flash:
        rect(ctx, 0, 0, W, H, (1, 0.85, 0.93, flash))
    return surf


def build(outdir, bg_path=None, intro=True):
    os.makedirs(outdir, exist_ok=True)
    base = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
    draw_background(cairo.Context(base), pixelize(bg_path))

    final = compose(base, "on")
    final.write_to_png(os.path.join(outdir, "background.png"))
    make_styles(outdir)
    with open(os.path.join(outdir, "theme.txt"), "w") as f:
        f.write(theme_txt())

    for old in os.listdir(outdir):
        if (old.startswith("intro-") and old.endswith(".png")) or old == "intro.txt":
            os.unlink(os.path.join(outdir, old))
    if not intro:
        return
    tx = LAYOUT["train_x"]
    # (khung, giữ 1/100 s): tàu chạy vào ga (chậm dần) → bảng bật nguồn → các hàng lật → menu
    frames = [
        (compose(base, None, train_x=W + 40, dark=0.75), 20),
        (compose(base, None, train_x=tx + 520, dark=0.70), 5),
        (compose(base, None, train_x=tx + 240, dark=0.62), 5),
        (compose(base, None, train_x=tx + 90, dark=0.55), 5),
        (compose(base, None, train_x=tx + 24, dark=0.50), 6),
        (compose(base, None, train_x=tx, dark=0.45), 12),
        (compose(base, "off", dark=0.30), 10),
        (compose(base, "off", flash=0.12), 4),
        (compose(base, "on", scramble=11), 6),
        (compose(base, "on", scramble=23), 6),
        (compose(base, "on", scramble=37), 6),
        (final, 0),
    ]
    with open(os.path.join(outdir, "intro.txt"), "w") as f:
        f.write("# khung  giữ(1/100 s) — tự sinh bởi make-kafka-theme.py; GRUB: background_image + play 6000 0 N\n")
        for i, (fr, hold) in enumerate(frames):
            nm = f"intro-{i:02d}.png"
            fr.write_to_png(os.path.join(outdir, nm))
            f.write(f"{nm} {hold}\n")


def selftest():
    ok = True
    d = tempfile.mkdtemp(prefix="kafka-grub-")
    build(d)
    need = ["background.png", "theme.txt", "intro.txt"] + [
        f"{p}_{k}.png" for p in ("select", "bar", "bar_hl") for k in ("nw", "n", "ne", "w", "c", "e", "sw", "s", "se")]
    for f in need:
        if not os.path.isfile(os.path.join(d, f)):
            print("thiếu", f)
            ok = False
    intro = sorted(f for f in os.listdir(d) if f.startswith("intro-") and f.endswith(".png"))
    if len(intro) < 8:
        print("thiếu khung intro:", intro)
        ok = False
    elif open(os.path.join(d, intro[-1]), "rb").read() != open(os.path.join(d, "background.png"), "rb").read():
        print("khung intro cuối khác background.png (sẽ bị giật khi chuyển sang menu)")
        ok = False
    ix, iy, iw, ih = INNER
    mx, my, mw, mh = LAYOUT["menu"]
    if not (ix < mx and mx + mw <= ix + iw and LAYOUT["colhead_y"] + 32 < my):
        print("menu tràn khỏi mặt LED")
        ok = False
    if 6 * (ITEM_H + ITEM_SP) > mh or my + mh > LAYOUT["count"][1] - 16:
        print("menu không đủ chỗ cho 6 mục / đè dòng đếm ngược")
        ok = False
    if LAYOUT["count"][1] + 56 > LAYOUT["hint_y"]:
        print("dòng đếm ngược tràn khỏi mặt LED")
        ok = False
    if LAYOUT["count"][0] + LAYOUT["count"][2] > LAYOUT["bar"][0]:
        print("dòng đếm ngược đè thanh")
        ok = False
    if BOARD[1] + BOARD[3] + 12 > LAYOUT["rail_y"] - 76:
        print("bảng đè sân ga/đoàn tàu")
        ok = False
    if sprites is None:
        print("(cảnh báo) không nạp được sprites.py — tàu vẽ đơn giản")
    t = open(os.path.join(d, "theme.txt")).read()
    if f"top = {my}" not in t or "Kafka Pixel VN Regular 42" not in t:
        print("theme.txt không khớp LAYOUT")
        ok = False
    shutil.rmtree(d)
    print("selftest:", "OK" if ok else "LỖI")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("outdir", nargs="?")
    ap.add_argument("--bg")
    ap.add_argument("--avatar", help="(bỏ qua — bố cục nhà ga không dùng ảnh mặt; giữ để tương thích)")
    ap.add_argument("--name", help="(bỏ qua, giữ để tương thích)")
    ap.add_argument("--sub", help="(bỏ qua, giữ để tương thích)")
    ap.add_argument("--no-intro", action="store_true", help="không sinh khung hình hiệu ứng xuất hiện")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--print-layout", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.print_layout:
        for k, v in LAYOUT.items():
            print(k, v)
        return 0
    if not a.outdir:
        ap.error("thiếu OUTDIR")
    build(a.outdir, a.bg, intro=not a.no_intro)
    return 0


if __name__ == "__main__":
    sys.exit(main())
