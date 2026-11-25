#!/usr/bin/env python3
"""make-kafka-line.py — sinh bộ ảnh cho menu UEFI "KAFKA.SYS // LINE 01" (uefi-menu/src/kafka.c).

Tuyến tàu NGANG: các trạm là các hệ điều hành đã cài (app tự ẩn trạm không tìm thấy loader) + trạm cuối "TỪ BỎ"
(chọn → hộp Tắt máy / Khởi động lại). Đoàn tàu pixel chạy mượt giữa các trạm; chọn trạm khác thì tàu chạy tới đó.

Mọi chữ vẽ sẵn bằng font pixel có dấu (kafka-src/vnglyphs.json, xuất từ font Kafka Pixel VN của dotfiles),
vị trí trạm do app tính lúc chạy (tuỳ số trạm), nên chỉ biển trạm/tàu là ảnh rời; nền vẽ sẵn tiêu đề, đường ray, gợi ý phím.

Định dạng .tbi (đọc bởi kafka.c/triboot.c): "TBI1", u32 rộng, u32 cao, 4 byte 0, rồi BGRA 8 bit KHÔNG nhân alpha.

Dùng:
  make-kafka-line.py OUTDIR [--bg ẢNH] [--png]      (--png: ghi thêm bản .png để xem)
  make-kafka-line.py --selftest
  make-kafka-line.py --preview ẢNH.png [--bg ẢNH]   (ghép thử một khung như app vẽ)
"""

import argparse
import importlib.util
import json
import os
import shutil
import struct
import sys
import tempfile

import cairo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pixelfont as pf  # noqa: E402
import sprites  # noqa: E402


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mk = _load("mk_theme", "make-kafka-theme.py")     # dùng lại nền pixel hoá + vignette + mưa
icons = _load("mk_icons", "make-icons.py")

W, H = 1920, 1080
# ---- phải khớp với uefi-menu/src/kafka.c (selftest kiểm tra)
TRACK_Y = 800            # mép trên thanh ray
SIGN_FOOT = 14           # đáy ảnh biển trạm thấp hơn mép ray bấy nhiêu px (cột + nút trạm cắm xuống ray)
TRAIN_CELL = 4
TRAIN_HEAD_W = 64 * TRAIN_CELL
TRAIN_FOOT = 2           # đáy ảnh tàu thấp hơn mép ray

GLYPHS = json.load(open(os.path.join(HERE, "vnglyphs.json"), encoding="utf-8"))
KEYS = {"arch": "ARCH LINUX", "windows": "WINDOWS 11", "ubuntu": "UBUNTU", "quit": "TỪ BỎ"}
ICON_OF = {"arch": "arch", "windows": "windows", "ubuntu": "ubuntu", "quit": "shutdown"}

hexc = mk.hexc
C = dict(mk.C)
C.update({
    "panel": hexc("#261e30"), "panel_hi": hexc("#4a3f58"), "panel_sh": hexc("#1d1626"),
    "pink_sh": hexc("#962f62"), "red": hexc("#b8324f"), "red_hi": hexc("#e0506e"), "red_sh": hexc("#7a1f35"),
    "red_edge": hexc("#3a0d18"),
})


# ---------------------------------------------------------------- chữ pixel có dấu
def vn_width(s, cell):
    return max(0, len(s) * 6 * cell - cell)


def vn_text(ctx, s, x, y, cell, col, shadow=None):
    """y = đỉnh vùng dấu (lưới 12 hàng: 3 hàng dấu + 7 thân + 2 dưới chân)."""
    s = s.upper()
    for pass_, c in ((1, shadow), (0, col)):
        if c is None:
            continue
        off = cell if pass_ else 0
        ctx.set_source_rgba(*c)
        for i, ch in enumerate(s):
            rows = GLYPHS.get(ch) or GLYPHS.get(" ")
            if not rows:
                continue
            gx = x + i * 6 * cell + off
            for r, line in enumerate(rows):
                for k, bit in enumerate(line):
                    if bit == "1":
                        ctx.rectangle(gx + k * cell, y + r * cell + off, cell, cell)
        ctx.fill()


def vn_center(ctx, s, cx, y, cell, col, shadow=None):
    vn_text(ctx, s, cx - vn_width(s, cell) // 2, y, cell, col, shadow)


# ---------------------------------------------------------------- khung lưới ô (góc bậc thang, bóng cứng)
def pframe(ctx, x, y, w, h, u, fill, hi, sh, edge, drop=True):
    rect = mk.rect

    def shape(ox, oy, ins, col):
        X, Y, Ww, Hh = x + ox + ins, y + oy + ins, w - 2 * ins, h - 2 * ins
        rect(ctx, X + 2 * u, Y, Ww - 4 * u, Hh, col)
        rect(ctx, X + u, Y + u, Ww - 2 * u, Hh - 2 * u, col)
        rect(ctx, X, Y + 2 * u, Ww, Hh - 4 * u, col)
    if drop:
        shape(u, u, 0, (0.03, 0.02, 0.05, 0.75))
    shape(0, 0, 0, edge)
    shape(0, 0, u, fill)
    rect(ctx, x + 2 * u, y + u, w - 4 * u, u, hi)
    rect(ctx, x + u, y + 2 * u, u, h - 4 * u, hi)
    rect(ctx, x + 2 * u, y + h - 2 * u, w - 4 * u, u, sh)
    rect(ctx, x + w - 2 * u, y + 2 * u, u, h - 4 * u, sh)


def icon_surface(name, scale):
    size = icons.GRID * scale
    raw = icons.icon_canvas(name, scale)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    stride = surf.get_stride()
    buf = surf.get_data()
    for yy in range(size):
        for xx in range(size):
            r, g, b, a = raw[(yy * size + xx) * 4:(yy * size + xx) * 4 + 4]
            o = yy * stride + xx * 4
            buf[o:o + 4] = bytes((b * a // 255, g * a // 255, r * a // 255, a))
    surf.mark_dirty()
    return surf


def paste(ctx, surf, x, y, alpha=1.0):
    ctx.set_source_surface(surf, x, y)
    ctx.get_source().set_filter(cairo.FILTER_NEAREST)
    ctx.paint_with_alpha(alpha)


# ---------------------------------------------------------------- xuất .tbi
def write_tbi(surf, path):
    surf.flush()
    w, h, stride = surf.get_width(), surf.get_height(), surf.get_stride()
    data = bytes(surf.get_data())
    opaque = surf.get_format() == cairo.FORMAT_RGB24
    out = bytearray(b"TBI1" + struct.pack("<III", w, h, 0))
    for yy in range(h):
        row = data[yy * stride: yy * stride + w * 4]
        if opaque:
            for xx in range(0, w * 4, 4):
                out += row[xx:xx + 3] + b"\xff"
        else:
            for xx in range(0, w * 4, 4):
                b, g, r, a = row[xx:xx + 4]
                if a and a < 255:                      # bỏ nhân alpha
                    b, g, r = min(255, b * 255 // a), min(255, g * 255 // a), min(255, r * 255 // a)
                out += bytes((b, g, r, a))
    with open(path, "wb") as f:
        f.write(out)


def new(w, h):
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    return s, cairo.Context(s)


# ---------------------------------------------------------------- từng ảnh
def make_bg(bg_path):
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
    ctx = cairo.Context(surf)
    mk.BG_SHIFT = 0
    mk.draw_background(ctx, mk.pixelize(bg_path))
    mk.rect(ctx, 0, 0, W, H, (0.05, 0.03, 0.07, 0.30))
    # tiêu đề
    pf.draw_icon(ctx, "spider", 80, 58, 4, C["pink_hi"])
    pf.draw_text(ctx, "KAFKA.SYS // LINE 01", 80 + 36 + 16, 62, 4, C["text"], C["shadow"])
    q = "LISTEN TO THE SOUND OF THE RAIN..."
    pf.draw_text(ctx, q, W - 80 - pf.text_width(q, 3), 66, 3, C["dim"], C["shadow"])
    vn_text(ctx, "CHỌN TRẠM ĐẾN", 80, 136, 6, C["pink_hi"], C["shadow"])
    vn_text(ctx, "MỖI TRẠM LÀ MỘT HỆ ĐIỀU HÀNH - GA CUỐI LÀ TỪ BỎ", 84, 226, 3, C["dim"], C["shadow"])
    # đường ray + nền đá dưới ray
    mk.rect(ctx, 0, TRACK_Y + 16, W, H - TRACK_Y - 16, hexc("#0e0a12", 0.94))
    for x in range(0, W, 24):
        mk.rect(ctx, x, TRACK_Y + 40, 12, 4, hexc("#f08cbb", 0.30))       # vạch cảnh báo
    sprites.draw_rail(ctx, 0, W, TRACK_Y, 4)
    # trụ chắn cuối tuyến (sau ga cuối)
    mk.rect(ctx, W - 56, TRACK_Y - 36, 24, 36, C["edge"])
    mk.rect(ctx, W - 52, TRACK_Y - 32, 16, 12, C["red_hi"])
    mk.rect(ctx, W - 52, TRACK_Y - 20, 16, 16, C["metal"])
    hint = "< >  CHỌN TRẠM      ENTER  KHỞI HÀNH      1-4  CHỌN NHANH      ESC  MENU GRUB"
    vn_center(ctx, hint, W // 2, 1012, 2, C["faint"])
    return surf


def make_sign(key, on):
    pw, ph, u = 300, 176, 4
    post_h = 70
    node = 28
    w, h = pw + u, ph + post_h + node // 2 + SIGN_FOOT
    surf, ctx = new(w, h)
    quit_ = key == "quit"
    if on:
        fill, hi, sh, edge = ((C["red"], C["red_hi"], C["red_sh"], C["red_edge"]) if quit_ else
                              (C["pink"], C["pink_hi"], C["pink_sh"], C["pink_edge"]))
        name_c, small_c = C["text"], hexc("#ffd6ea")
    else:
        fill, hi, sh, edge = C["panel"], C["panel_hi"], C["panel_sh"], C["edge"]
        name_c, small_c = (C["red_hi"] if quit_ else C["faint"]), C["led_off"]
    cx = pw // 2
    # cột + nút trạm cắm xuống ray
    mk.rect(ctx, cx - 8, ph - 8, 16, post_h + 8, C["edge"])
    mk.rect(ctx, cx - 4, ph - 8, 8, post_h + 8, C["metal_hi"] if on else C["metal"])
    ny = h - SIGN_FOOT - node
    mk.rect(ctx, cx - node // 2, ny, node, node, C["edge"])
    mk.rect(ctx, cx - node // 2 + 4, ny + 4, node - 8, node - 8, hi if on else C["panel_hi"])
    # biển
    pframe(ctx, 0, 0, pw, ph, u, fill, hi, sh, edge)
    ic = icon_surface(ICON_OF[key], 4)
    paste(ctx, ic, cx - 32, 20, 1.0 if on else 0.55)
    small = "GA CUỐI" if quit_ else "SÂN GA"
    vn_center(ctx, small, cx, 92, 2, small_c)
    vn_center(ctx, KEYS[key], cx, 116, 4, name_c, C["shadow"] if on else None)
    return surf


def make_train(direction):
    hw, hh = sprites.sprite_size(sprites.TRAIN_HEAD)
    cw, _ = sprites.sprite_size(sprites.TRAIN_CAR)
    c = TRAIN_CELL
    w, h = (hw + cw) * c, hh * c
    surf, ctx = new(w, h)
    sprites.draw_sprite(ctx, sprites.TRAIN_HEAD, 0, 0, c)
    sprites.draw_sprite(ctx, sprites.TRAIN_CAR, hw * c, 0, c)
    if direction == "r":                               # đầu tàu quay sang phải
        out, o = new(w, h)
        o.translate(w, 0)
        o.scale(-1, 1)
        o.set_source_surface(surf, 0, 0)
        o.get_source().set_filter(cairo.FILTER_NEAREST)
        o.paint()
        return out
    return surf


def make_label(s, cell, col, pad=8):
    w = vn_width(s, cell) + 2 * pad + cell
    h = 12 * cell + 2 * pad + cell
    surf, ctx = new(w, h)
    vn_text(ctx, s, pad, pad, cell, col, C["shadow"])
    return surf


def make_quit_panel():
    w, h, u = 820, 420, 4
    surf, ctx = new(w + u, h + u)
    pframe(ctx, 0, 0, w, h, u, C["panel"], C["panel_hi"], C["panel_sh"], C["edge"])
    mk.rect(ctx, 2 * u, 2 * u, w - 4 * u, 48, C["red"])                     # dải tiêu đề
    mk.rect(ctx, 2 * u, 2 * u, w - 4 * u, u, C["red_hi"])
    pf.draw_text(ctx, "GA CUOI // TERMINUS", 28, 22, 3, C["text"])
    for i in range(3):
        mk.rect(ctx, w - 40 - i * 24, 24, 14, 14, C["edge"])
        mk.rect(ctx, w - 38 - i * 24, 26, 10, 10, C["red_hi"] if i == 0 else C["panel_hi"])
    vn_center(ctx, "TỪ BỎ HÀNH TRÌNH?", w // 2, 88, 6, C["text"], C["shadow"])
    vn_center(ctx, "TÀU SẼ KHÔNG CHẠY NỮA. CHỌN CÁCH DỪNG LẠI:", w // 2, 178, 3, C["dim"])
    vn_center(ctx, "< >  CHỌN      ENTER  XÁC NHẬN      ESC  Ở LẠI", w // 2, h - 46, 2, C["faint"])
    return surf


def make_button(key, on):
    w, h, u = 340, 96, 4
    surf, ctx = new(w + u, h + u)
    if on:
        pframe(ctx, 0, 0, w, h, u, C["pink"], C["pink_hi"], C["pink_sh"], C["pink_edge"])
    else:
        pframe(ctx, 0, 0, w, h, u, hexc("#1a1322"), C["panel_hi"], C["panel_sh"], C["edge"])
    name = "TẮT MÁY" if key == "off" else "KHỞI ĐỘNG LẠI"
    ic = icon_surface("shutdown" if key == "off" else "restart", 3)
    tw = 48 + 16 + vn_width(name, 3)
    x0 = (w - tw) // 2
    paste(ctx, ic, x0, (h - 48) // 2, 1.0 if on else 0.6)
    vn_text(ctx, name, x0 + 64, (h - 36) // 2, 3, C["text"] if on else C["dim"], C["shadow"] if on else None)
    return surf


# ---------------------------------------------------------------- build
def assets(bg_path):
    yield "bg", make_bg(bg_path)
    for k in KEYS:
        yield f"sign_{k}_on", make_sign(k, True)
        yield f"sign_{k}_off", make_sign(k, False)
    yield "train_l", make_train("l")
    yield "train_r", make_train("r")
    for n in range(31):
        yield f"count_{n}", make_label(f"KHỞI HÀNH SAU {n} GIÂY", 3, C["pink_hi"])
    yield "paused", make_label("ĐÃ DỪNG ĐẾM GIỜ - ENTER ĐỂ KHỞI HÀNH", 3, C["dim"])
    yield "booting", make_label("TÀU ĐANG RỜI GA...", 3, C["text"])
    yield "quit_panel", make_quit_panel()
    for k in ("off", "rst"):
        yield f"btn_{k}_on", make_button(k, True)
        yield f"btn_{k}_off", make_button(k, False)


def build(outdir, bg_path=None, png=False):
    os.makedirs(outdir, exist_ok=True)
    for old in os.listdir(outdir):
        if old.endswith((".tbi", ".png")):
            os.unlink(os.path.join(outdir, old))
    names = []
    for name, surf in assets(bg_path):
        write_tbi(surf, os.path.join(outdir, name + ".tbi"))
        if png:
            surf.write_to_png(os.path.join(outdir, name + ".png"))
        names.append(name)
    return names


def read_tbi(path):
    d = open(path, "rb").read()
    assert d[:4] == b"TBI1", path
    w, h = struct.unpack("<II", d[4:12])
    assert len(d) == 16 + w * h * 4, path
    return w, h


def preview(out, bg_path=None, cur=1, keys=("arch", "windows", "ubuntu", "quit")):
    """Ghép thử khung như kafka.c vẽ (cùng công thức vị trí) để xem nhanh không cần QEMU."""
    surf = make_bg(bg_path)
    ctx = cairo.Context(surf)
    xs = station_xs(len(keys))
    for i, k in enumerate(keys):
        s = make_sign(k, i == cur)
        paste(ctx, s, xs[i] - (s.get_width() - 4) // 2, TRACK_Y + SIGN_FOOT - s.get_height())
    t = make_train("r")
    paste(ctx, t, xs[cur] + TRAIN_HEAD_W // 2 - t.get_width(), TRACK_Y + TRAIN_FOOT - t.get_height())
    lab = make_label("KHỞI HÀNH SAU 9 GIÂY", 3, C["pink_hi"])
    paste(ctx, lab, W // 2 - lab.get_width() // 2, 930)
    surf.write_to_png(out)


def station_xs(n):
    """Giống kafka.c: trạm cách đều trong [MARGIN, W-MARGIN]."""
    margin = 260
    if n == 1:
        return [W // 2]
    return [margin + (W - 2 * margin) * i // (n - 1) for i in range(n)]


def selftest():
    ok = True
    d = tempfile.mkdtemp(prefix="kafka-line-")
    names = build(d)
    for n in names:
        try:
            read_tbi(os.path.join(d, n + ".tbi"))
        except AssertionError as e:
            print("tbi hỏng:", e)
            ok = False
    if len(names) != 1 + 8 + 2 + 31 + 2 + 1 + 4:
        print("số ảnh sai:", len(names))
        ok = False
    for ch in "TỪ BỎ KHỞI HÀNH SAU GIÂY ĐÃ DỪNG ĐẾM TẮT MÁY ĐỘNG LẠI CHỌN TRẠM ĐẾN MỖI LÀ HỆ ĐIỀU GA CUỐI TÀU SẼ NỮA":
        if ch not in GLYPHS:
            print("thiếu glyph", ch)
            ok = False
    w, _ = read_tbi(os.path.join(d, "sign_arch_on.tbi"))
    xs = station_xs(4)
    if xs[1] - xs[0] < w + 40:
        print("biển trạm sát nhau quá")
        ok = False
    csrc = os.path.join(HERE, "..", "uefi-menu", "src", "kafka.c")
    if os.path.isfile(csrc):
        src = open(csrc, encoding="utf-8").read()
        for k, v in (("TRACK_Y", TRACK_Y), ("SIGN_FOOT", SIGN_FOOT), ("TRAIN_HEAD_W", TRAIN_HEAD_W),
                     ("TRAIN_FOOT", TRAIN_FOOT), ("STATION_MARGIN", 260)):
            if f"#define {k} {v}" not in src:
                print(f"kafka.c lệch hằng số: cần '#define {k} {v}'")
                ok = False
    shutil.rmtree(d)
    print("selftest:", "OK" if ok else "LỖI")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("outdir", nargs="?")
    ap.add_argument("--bg")
    ap.add_argument("--png", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--preview")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.preview:
        preview(a.preview, a.bg)
        return 0
    if not a.outdir:
        ap.error("thiếu OUTDIR")
    names = build(a.outdir, a.bg, a.png)
    print(f"{len(names)} ảnh .tbi → {a.outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
