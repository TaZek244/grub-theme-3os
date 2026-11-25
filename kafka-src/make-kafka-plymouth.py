#!/usr/bin/env python3
"""make-kafka-plymouth.py — màn hình chào/tạm biệt Plymouth kiểu pixel KAFKA.SYS (cùng bộ với menu tuyến tàu LINE 01).

Bật máy: đoàn tàu chạy vào GA <HỆ ĐIỀU HÀNH> và dừng dưới biển trạm, hộp kiểu cửa sổ game hiện lên
"CHÀO MỪNG TRỞ LẠI, <TÊN>" + "<HĐH> ĐANG KHỞI ĐỘNG", thanh tải là dãy ô pixel sáng lần lượt.
Tắt máy / khởi động lại: tàu đang đỗ rồi RỜI GA nhanh dần, hộp "HẸN GẶP LẠI, <TÊN>".

Ghi ra OUTDIR đủ file cho theme script của Plymouth:
  <theme>.plymouth, <theme>.script, background.png, train.png, sign.png,
  panel_boot.png, panel_shutdown.png, panel_reboot.png, block_on.png, block_off.png
Ảnh nền lấy từ --bg (ảnh Kafka của dotfiles, KHÔNG đưa lên repo); không có thì nền tự vẽ.

Dùng:
  make-kafka-plymouth.py OUTDIR --os arch|ubuntu --theme TÊN_THEME --dir /usr/share/plymouth/themes/TÊN [--name TaZek] [--bg ẢNH]
  make-kafka-plymouth.py --selftest
  make-kafka-plymouth.py --preview ẢNH.png [--mode boot|shutdown|reboot] [--os arch] [--bg ẢNH]
"""

import argparse
import importlib.util
import os
import shutil
import sys
import tempfile

import cairo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pixelfont as pf  # noqa: E402


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


line = _load("mk_line", "make-kafka-line.py")    # dùng chung chữ có dấu, khung lưới ô, biển trạm, tàu, nền
mk = line.mk
C = line.C
W, H = line.W, line.H
TRACK_Y = line.TRACK_Y
OS_NAME = {"arch": "ARCH LINUX", "ubuntu": "UBUNTU"}

# Bố cục (px ở 1920x1080) — script Plymouth dùng cùng số (tính theo tỉ lệ màn hình)
PANEL_X = 80             # mép trái hộp chào (để lộ mặt Kafka ở giữa)
PANEL_CY = 296           # tâm dọc hộp chào
BLOCKS = 12              # số ô thanh tải
BLOCK = 28               # cạnh ô
BLOCK_GAP = 8
BLOCKS_Y = 432           # mép trên dãy ô


def make_bg(bg_path):
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
    ctx = cairo.Context(surf)
    mk.BG_SHIFT = 0
    mk.draw_background(ctx, mk.pixelize(bg_path))
    mk.rect(ctx, 0, 0, W, H, (0.05, 0.03, 0.07, 0.38))
    pf.draw_icon(ctx, "spider", 80, 58, 4, C["pink_hi"])
    pf.draw_text(ctx, "KAFKA.SYS // LINE 01", 80 + 36 + 16, 62, 4, C["text"], C["shadow"])
    q = "LISTEN TO THE SOUND OF THE RAIN..."
    pf.draw_text(ctx, q, W - 80 - pf.text_width(q, 3), 66, 3, C["dim"], C["shadow"])
    mk.rect(ctx, 0, TRACK_Y + 16, W, H - TRACK_Y - 16, mk.hexc("#0e0a12", 0.94))
    for x in range(0, W, 24):
        mk.rect(ctx, x, TRACK_Y + 40, 12, 4, mk.hexc("#f08cbb", 0.30))
    line.sprites.draw_rail(ctx, 0, W, TRACK_Y, 4)
    return surf


def make_panel(title, big, sub):
    u = 4
    tw = max(line.vn_width(big, 5), line.vn_width(sub, 3)) + 2 * 64
    w = max(760, (tw + 7) // 8 * 8)
    h = 236
    surf, ctx = line.new(w + u, h + u)
    line.pframe(ctx, 0, 0, w, h, u, C["panel"], C["panel_hi"], C["panel_sh"], C["edge"])
    mk.rect(ctx, 2 * u, 2 * u, w - 4 * u, 48, C["pink"])                   # dải tiêu đề hồng
    mk.rect(ctx, 2 * u, 2 * u, w - 4 * u, u, C["pink_hi"])
    pf.draw_text(ctx, title, 28, 22, 3, C["text"])
    for i in range(3):
        mk.rect(ctx, w - 40 - i * 24, 24, 14, 14, C["edge"])
        mk.rect(ctx, w - 38 - i * 24, 26, 10, 10, mk.hexc("#ffd6ea") if i == 0 else C["panel_hi"])
    line.vn_center(ctx, big, w // 2, 84, 5, C["text"], C["shadow"])
    line.vn_center(ctx, sub, w // 2, 166, 3, C["pink_hi"])
    return surf


def make_block(on):
    s, ctx = line.new(BLOCK, BLOCK)
    mk.rect(ctx, 0, 0, BLOCK, BLOCK, C["edge"])
    if on:
        mk.rect(ctx, 4, 4, BLOCK - 8, BLOCK - 8, C["pink_hi"])
        mk.rect(ctx, 4, 4, BLOCK - 8, 4, mk.hexc("#ffd6ea"))
        mk.rect(ctx, 4, BLOCK - 8, BLOCK - 8, 4, C["pink"])
    else:
        mk.rect(ctx, 4, 4, BLOCK - 8, BLOCK - 8, mk.hexc("#2a2033"))
    return s


SCRIPT = r'''// KAFKA.SYS // LINE 01 — màn hình chào / tạm biệt Plymouth kiểu pixel (tự sinh bởi kafka-src/make-kafka-plymouth.py)
// Bật máy: tàu chạy vào ga __OS__ rồi dừng, hộp chào hiện lên, dãy ô tải chạy.
// Tắt máy / khởi động lại: tàu rời ga nhanh dần, hộp "HẸN GẶP LẠI".
// Ảnh vẽ cho 1920x1080; màn khác thì co theo chiều cao (s).

Window.SetBackgroundTopColor(0.07, 0.05, 0.09);
Window.SetBackgroundBottomColor(0.07, 0.05, 0.09);

sw = Window.GetWidth();
sh = Window.GetHeight();
ox = Window.GetX();
oy = Window.GetY();
s = sh / 1080;
cx = ox + sw / 2;

fun px(img) {                       // co ảnh theo tỉ lệ màn hình (1080p: giữ nguyên, không nhoè)
    if (s == 1) return img;
    return img.Scale(Math.Int(img.GetWidth() * s), Math.Int(img.GetHeight() * s));
}

bg = Sprite(Image("background.png").Scale(sw, sh));
bg.SetPosition(ox, oy, -100);

track_y = oy + __TRACK_Y__ * s;
mode = Plymouth.GetMode();
if (mode == "shutdown") panel_img = px(Image("panel_shutdown.png"));
else if (mode == "reboot") panel_img = px(Image("panel_reboot.png"));
else panel_img = px(Image("panel_boot.png"));
leaving = (mode == "shutdown" || mode == "reboot");

sign = Sprite(px(Image("sign.png")));
sign_x = cx - (sign.GetImage().GetWidth() - 4 * s) / 2;
sign_y = track_y + __SIGN_FOOT__ * s - sign.GetImage().GetHeight();
sign.SetOpacity(0);

train = Sprite(px(Image("train.png")));
tw = train.GetImage().GetWidth();
train_y = track_y + __TRAIN_FOOT__ * s - train.GetImage().GetHeight();
park_x = cx + __HEAD_W__ * s / 2 - tw;           // đầu tàu (bên phải) dừng ngay dưới biển trạm

panel = Sprite(panel_img);
panel_y = oy + __PANEL_CY__ * s - panel_img.GetHeight() / 2;
panel.SetOpacity(0);

on_img = px(Image("block_on.png"));
off_img = px(Image("block_off.png"));
bstep = (__BLOCK__ + __BLOCK_GAP__) * s;
bx0 = ox + __PANEL_X__ * s + (panel_img.GetWidth() - __BLOCKS__ * bstep + __BLOCK_GAP__ * s) / 2;
for (i = 0; i < __BLOCKS__; i++) {
    blk[i] = Sprite(off_img);
    blk[i].SetPosition(bx0 + i * bstep, oy + __BLOCKS_Y__ * s, 5);
    blk[i].SetOpacity(0);
    lit[i] = 0;
}

t = 0;                              // số khung (~50/giây)
fun ease(x) { x = Math.Clamp(x, 0, 1); return 1 - (1 - x) * (1 - x) * (1 - x); }

fun refresh_callback() {
    t++;
    // biển trạm hiện + trượt lên
    a = ease(t / 30);
    sign.SetPosition(sign_x, sign_y + 24 * s * (1 - a), 2);
    sign.SetOpacity(a);

    // đoàn tàu
    if (leaving) {
        e = Math.Max(0, t - 40);                 // đỗ chừng 0.8 giây rồi rời ga, nhanh dần
        x = park_x + e * e * 0.9 * s;
    } else {
        x = -tw + (park_x + tw) * ease((t - 10) / 100);
    }
    train.SetPosition(Math.Int(x / (2 * s)) * 2 * s, train_y, 3);   // bước 2px: giữ chất pixel

    // hộp chào
    p = ease((t - 30) / 35);
    panel.SetPosition(ox + __PANEL_X__ * s - 40 * s * (1 - p), panel_y + 20 * s * (1 - p), 4);
    panel.SetOpacity(p);

    // dãy ô tải: một đoạn 4 ô sáng chạy vòng; tắt máy thì chạy ngược
    if (t > 60) {
        head = Math.Int((t - 60) / 5) % (__BLOCKS__ + 4);
        if (leaving) head = __BLOCKS__ + 3 - head;
        for (i = 0; i < __BLOCKS__; i++) {
            want = (i <= head && i > head - 4);
            if (want != lit[i]) {
                if (want) blk[i].SetImage(on_img); else blk[i].SetImage(off_img);
                lit[i] = want;
            }
            blk[i].SetOpacity(1);
        }
    }
}
Plymouth.SetRefreshFunction(refresh_callback);

// Thông báo dạng chữ của hệ thống (vd. fsck) dưới dãy ô
msg = Sprite();
fun message_callback(text) {
    if (text == "") {
        msg.SetOpacity(0);
    } else {
        msg.SetImage(Image.Text(text, 0.83, 0.79, 0.87));
        msg.SetPosition(ox + __PANEL_X__ * s + 8 * s, oy + (__BLOCKS_Y__ + 44) * s, 6);
        msg.SetOpacity(1);
    }
}
Plymouth.SetMessageFunction(message_callback);
'''


def script_text(os_key):
    rep = {"__OS__": OS_NAME[os_key], "__TRACK_Y__": TRACK_Y, "__SIGN_FOOT__": line.SIGN_FOOT,
           "__TRAIN_FOOT__": line.TRAIN_FOOT, "__HEAD_W__": line.TRAIN_HEAD_W, "__PANEL_CY__": PANEL_CY, "__PANEL_X__": PANEL_X,
           "__BLOCKS__": BLOCKS, "__BLOCK__": BLOCK, "__BLOCK_GAP__": BLOCK_GAP, "__BLOCKS_Y__": BLOCKS_Y}
    s = SCRIPT
    for k, v in rep.items():
        s = s.replace(k, str(v))
    return s


def build(outdir, os_key, theme, theme_dir, name="", bg_path=None):
    os.makedirs(outdir, exist_ok=True)
    for f in os.listdir(outdir):
        os.unlink(os.path.join(outdir, f))
    nm = f", {name.upper()}" if name else ""
    osn = OS_NAME[os_key]
    make_bg(bg_path).write_to_png(os.path.join(outdir, "background.png"))
    line.make_train("r").write_to_png(os.path.join(outdir, "train.png"))
    line.make_sign(os_key, True).write_to_png(os.path.join(outdir, "sign.png"))
    make_panel("KAFKA.SYS // ARRIVAL", f"CHÀO MỪNG TRỞ LẠI{nm}", f"{osn} ĐANG KHỞI ĐỘNG").write_to_png(
        os.path.join(outdir, "panel_boot.png"))
    make_panel("KAFKA.SYS // DEPARTURE", f"HẸN GẶP LẠI{nm}", f"{osn} ĐANG TẮT MÁY").write_to_png(
        os.path.join(outdir, "panel_shutdown.png"))
    make_panel("KAFKA.SYS // DEPARTURE", f"HẸN GẶP LẠI{nm}", f"{osn} ĐANG KHỞI ĐỘNG LẠI").write_to_png(
        os.path.join(outdir, "panel_reboot.png"))
    make_block(True).write_to_png(os.path.join(outdir, "block_on.png"))
    make_block(False).write_to_png(os.path.join(outdir, "block_off.png"))
    with open(os.path.join(outdir, theme + ".script"), "w", encoding="utf-8") as f:
        f.write(script_text(os_key))
    with open(os.path.join(outdir, theme + ".plymouth"), "w", encoding="utf-8") as f:
        f.write(f"""[Plymouth Theme]
Name=KAFKA.SYS {osn.title()}
Description=Màn hình chào/tạm biệt pixel KAFKA.SYS khi khởi động {osn.title()} (grub-theme-3os)
ModuleName=script

[script]
ImageDir={theme_dir}
ScriptFile={theme_dir}/{theme}.script
""")


def preview(out, mode="boot", os_key="arch", name="TAZEK", bg_path=None, t=200):
    """Ghép một khung như script vẽ ở khung t (1920x1080)."""
    d = tempfile.mkdtemp()
    build(d, os_key, "x", d, name, bg_path)
    surf = cairo.ImageSurface.create_from_png(os.path.join(d, "background.png"))
    ctx = cairo.Context(surf)

    def img(n):
        return cairo.ImageSurface.create_from_png(os.path.join(d, n))

    def e(x):
        x = min(1, max(0, x))
        return 1 - (1 - x) ** 3
    sign = img("sign.png")
    line.paste(ctx, sign, W / 2 - (sign.get_width() - 4) / 2, TRACK_Y + line.SIGN_FOOT - sign.get_height())
    tr = img("train.png")
    park = W / 2 + line.TRAIN_HEAD_W / 2 - tr.get_width()
    x = park + max(0, t - 40) ** 2 * 0.9 if mode != "boot" else -tr.get_width() + (park + tr.get_width()) * e((t - 10) / 100)
    line.paste(ctx, tr, int(x) // 2 * 2, TRACK_Y + line.TRAIN_FOOT - tr.get_height())
    p = img(f"panel_{mode}.png")
    line.paste(ctx, p, PANEL_X, PANEL_CY - p.get_height() / 2)
    on, off = img("block_on.png"), img("block_off.png")
    step = BLOCK + BLOCK_GAP
    x0 = PANEL_X + (p.get_width() - BLOCKS * step + BLOCK_GAP) / 2
    head = ((t - 60) // 5) % (BLOCKS + 4)
    for i in range(BLOCKS):
        line.paste(ctx, on if head - 4 < i <= head else off, x0 + i * step, BLOCKS_Y)
    surf.write_to_png(out)
    shutil.rmtree(d)


def selftest():
    ok = True
    d = tempfile.mkdtemp(prefix="kafka-ply-")
    build(d, "arch", "triboot", "/usr/share/plymouth/themes/triboot", "TaZek")
    need = ["triboot.plymouth", "triboot.script", "background.png", "train.png", "sign.png", "panel_boot.png",
            "panel_shutdown.png", "panel_reboot.png", "block_on.png", "block_off.png"]
    for f in need:
        if not os.path.isfile(os.path.join(d, f)):
            print("thiếu", f)
            ok = False
    sc = open(os.path.join(d, "triboot.script"), encoding="utf-8").read()
    if "__" in sc.replace("__OS__", ""):
        left = [w for w in sc.split() if w.startswith("__") or "__" in w]
        if left:
            print("script còn biến chưa thay:", left[:5])
            ok = False
    if sc.count("{") != sc.count("}") or sc.count("(") != sc.count(")"):
        print("script lệch ngoặc")
        ok = False
    p = cairo.ImageSurface.create_from_png(os.path.join(d, "panel_boot.png"))
    if p.get_width() > W - 160 or PANEL_CY + p.get_height() // 2 > BLOCKS_Y - 16:
        print("hộp chào quá to / đè dãy ô tải")
        ok = False
    s = cairo.ImageSurface.create_from_png(os.path.join(d, "sign.png"))
    if BLOCKS_Y + BLOCK + 60 > TRACK_Y + line.SIGN_FOOT - s.get_height():
        print("dãy ô tải (và dòng thông báo) đè biển trạm")
        ok = False
    shutil.rmtree(d)
    print("selftest:", "OK" if ok else "LỖI")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("outdir", nargs="?")
    ap.add_argument("--os", choices=sorted(OS_NAME), default="arch")
    ap.add_argument("--theme", default="triboot")
    ap.add_argument("--dir", help="thư mục theme khi cài (ImageDir), mặc định /usr/share/plymouth/themes/<theme>")
    ap.add_argument("--name", default="")
    ap.add_argument("--bg")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--preview")
    ap.add_argument("--mode", choices=("boot", "shutdown", "reboot"), default="boot")
    ap.add_argument("--frame", type=int, default=200)
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.preview:
        preview(a.preview, a.mode, a.os, a.name or "TAZEK", a.bg, a.frame)
        return 0
    if not a.outdir:
        ap.error("thiếu OUTDIR")
    build(a.outdir, a.os, a.theme, a.dir or f"/usr/share/plymouth/themes/{a.theme}", a.name, a.bg)
    print(f"Plymouth KAFKA.SYS ({a.os}) → {a.outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
