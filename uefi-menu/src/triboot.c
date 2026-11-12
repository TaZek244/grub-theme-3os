// Triboot — menu chọn hệ điều hành dạng ngang, có hiệu ứng, cho UEFI.
// GRUB chainload file này; Esc quay lại GRUB, lỗi khởi tạo thì GRUB tự rơi xuống mục dự phòng.
#include "efi.h"

// ===================== Cấu hình máy =====================
#define TIMEOUT_MS     10000          // tự khởi động sau 10 giây
#define TZ_OFFSET_H    7              // đồng hồ phần cứng chạy UTC, Việt Nam = UTC+7
#define ASSET_DIR      u"\\EFI\\triboot\\assets\\"

typedef struct {
    const char *key;                  // tên asset: icon_<key>, glow_<key>, label_<key>_on/off
    EFI_GUID    part;                 // GUID phân vùng (GPT) chứa loader
    CHAR16     *path;                 // đường dẫn loader trên phân vùng đó
    CHAR16     *options;              // tham số truyền cho loader (NULL = không có)
    u32         color;                // màu thanh đếm giờ khi đang chọn mục này (0xRRGGBB)
} Entry;

static Entry ENTRIES[] = {
    { "arch",
      {0x124a725e, 0x8a92, 0x4d60, {0xac, 0xcd, 0x91, 0x69, 0x7f, 0x6e, 0x1b, 0x76}},
      u"\\vmlinuz-linux",
      u"initrd=\\initramfs-linux.img root=UUID=8006d6ff-4672-4328-a7b4-86ce5b21ba88 rw loglevel=3 quiet splash",
      0x1793d1 },
    { "windows",
      {0x2ecc4d3c, 0x983c, 0x4039, {0x89, 0x14, 0x55, 0x39, 0x98, 0x47, 0x08, 0x95}},
      u"\\EFI\\Microsoft\\Boot\\bootmgfw.efi", 0, 0x00a4ef },
    { "ubuntu",
      {0x2ecc4d3c, 0x983c, 0x4039, {0x89, 0x14, 0x55, 0x39, 0x98, 0x47, 0x08, 0x95}},
      u"\\EFI\\ubuntu\\shimx64.efi", 0, 0xe95420 },
};
#define N_ENTRIES 3

// ===================== Hạ tầng =====================
static EFI_SYSTEM_TABLE  *ST;
static EFI_BOOT_SERVICES *BS;
static EFI_HANDLE         SELF;
static EFI_GUID GOP_GUID   = {0x9042a9de, 0x23dc, 0x4a38, {0x96, 0xfb, 0x7a, 0xde, 0xd0, 0x80, 0x51, 0x6a}};
static EFI_GUID LIP_GUID   = {0x5b1b31a1, 0x9562, 0x11d2, {0x8e, 0x3f, 0x00, 0xa0, 0xc9, 0x69, 0x72, 0x3b}};
static EFI_GUID SFS_GUID   = {0x964e5b22, 0x6459, 0x11d2, {0x8e, 0x39, 0x00, 0xa0, 0xc9, 0x69, 0x72, 0x3b}};
static EFI_GUID DP_GUID    = {0x09576e91, 0x6d3f, 0x11d2, {0x8e, 0x39, 0x00, 0xa0, 0xc9, 0x69, 0x72, 0x3b}};

void *memset(void *d, int c, UINTN n) { u8 *p = d; while (n--) *p++ = (u8)c; return d; }
void *memcpy(void *d, const void *s, UINTN n) { u8 *p = d; const u8 *q = s; while (n--) *p++ = *q++; return d; }
static int guid_eq(const void *a, const void *b) { const u8 *x = a, *y = b; for (int i = 0; i < 16; i++) if (x[i] != y[i]) return 0; return 1; }
static UINTN wlen(const CHAR16 *s) { UINTN n = 0; while (s[n]) n++; return n; }

static void *alloc(UINTN n) { void *p = 0; if (EFI_IS_ERR(BS->AllocatePool(EfiLoaderData, n, &p))) return 0; return p; }

static void say(CHAR16 *s) { ST->ConOut->OutputString(ST->ConOut, s); }

// --- Thời gian: đếm bằng TSC, hiệu chỉnh với Stall lúc khởi động
static u64 tsc_per_ms = 1, tsc0;
static inline u64 rdtsc(void) { u32 lo, hi; __asm__ volatile("rdtsc" : "=a"(lo), "=d"(hi)); return ((u64)hi << 32) | lo; }
static void clock_init(void) { u64 a = rdtsc(); BS->Stall(20000); u64 b = rdtsc(); tsc_per_ms = (b - a) / 20; if (!tsc_per_ms) tsc_per_ms = 1; tsc0 = rdtsc(); }
static i64 now_ms(void) { return (i64)((rdtsc() - tsc0) / tsc_per_ms); }

// ===================== Ảnh =====================
typedef struct { u32 w, h; u32 *px; } Img;   // px: BGRA đã nhân sẵn alpha (premultiplied)

static FILE *ROOT;     // ổ chứa chính file này (ESP của Arch)

static void *read_file(FILE *root, CHAR16 *path, UINTN *size) {
    FILE *f;
    if (EFI_IS_ERR(root->Open(root, &f, path, FILE_MODE_READ, 0))) return 0;
    u64 sz = 0;
    f->SetPosition(f, ~0ULL); f->GetPosition(f, &sz); f->SetPosition(f, 0);
    void *buf = alloc(sz ? sz : 1);
    UINTN n = sz;
    if (!buf || EFI_IS_ERR(f->Read(f, &n, buf)) || n != sz) { f->Close(f); return 0; }
    f->Close(f);
    if (size) *size = sz;
    return buf;
}

static int load_img(Img *img, const char *name) {
    CHAR16 path[128]; UINTN k = 0;
    for (const CHAR16 *p = ASSET_DIR; *p; p++) path[k++] = *p;
    for (const char *p = name; *p; p++) path[k++] = (CHAR16)*p;
    path[k++] = '.'; path[k++] = 't'; path[k++] = 'b'; path[k++] = 'i'; path[k] = 0;
    UINTN sz; u8 *d = read_file(ROOT, path, &sz);
    if (!d || sz < 16 || d[0] != 'T' || d[1] != 'B' || d[2] != 'I' || d[3] != '1') return 0;
    u32 w = *(u32 *)(d + 4), h = *(u32 *)(d + 8);
    if ((u64)w * h * 4 + 16 != sz) return 0;
    u32 *px = (u32 *)(d + 16);
    for (u64 i = 0; i < (u64)w * h; i++) {       // đổi sang premultiplied
        u32 c = px[i], a = c >> 24;
        u32 b = (c & 0xff) * a / 255, g = ((c >> 8) & 0xff) * a / 255, r = ((c >> 16) & 0xff) * a / 255;
        px[i] = (a << 24) | (r << 16) | (g << 8) | b;
    }
    img->w = w; img->h = h; img->px = px;
    return 1;
}

// ===================== Màn hình + vẽ =====================
static GOP *gop;
static i32 W, H;
static u32 *fb;        // bộ đệm sau
static u32 *bgbuf;     // nền đã co giãn đúng màn hình

typedef struct { i32 x0, y0, x1, y1; } Rect;
static Rect clip;

static inline u32 blend(u32 d, u32 s, u32 op) {   // s premultiplied, op 0..256
    u32 sa = ((s >> 24) * op) >> 8;
    if (!sa) return d;
    u32 inv = 255 - sa, out = 0;
    for (int sh = 0; sh < 24; sh += 8) {
        u32 sc = (((s >> sh) & 0xff) * op) >> 8;
        u32 dc = (d >> sh) & 0xff;
        u32 v = sc + (dc * inv + 127) / 255;
        if (v > 255) v = 255;
        out |= v << sh;
    }
    return out;
}

// Vẽ ảnh với tâm (cx, cy), cỡ rộng tw (giữ tỉ lệ), độ đậm op (0..256). tw == img->w thì vẽ 1:1.
static void draw(const Img *img, i32 cx, i32 cy, i32 tw, u32 op) {
    if (!img->px || op == 0) return;
    if (op > 256) op = 256;
    i32 th = (i32)((i64)img->h * tw / img->w);
    i32 x0 = cx - tw / 2, y0 = cy - th / 2;
    i32 ax = x0 < clip.x0 ? clip.x0 : x0, ay = y0 < clip.y0 ? clip.y0 : y0;
    i32 bx = x0 + tw > clip.x1 ? clip.x1 : x0 + tw, by = y0 + th > clip.y1 ? clip.y1 : y0 + th;
    if (ax >= bx || ay >= by) return;
    if (tw == (i32)img->w) {
        for (i32 y = ay; y < by; y++) {
            u32 *src = img->px + (u64)(y - y0) * img->w + (ax - x0);
            u32 *dst = fb + (u64)y * W + ax;
            for (i32 x = ax; x < bx; x++, src++, dst++) *dst = blend(*dst, *src, op);
        }
        return;
    }
    // Co giãn song tuyến (bilinear), toạ độ 16.16
    i64 step = ((i64)img->w << 16) / tw;
    for (i32 y = ay; y < by; y++) {
        i64 sy = ((i64)(y - y0) * step + step / 2) - 32768;
        if (sy < 0) sy = 0;
        i32 iy = (i32)(sy >> 16), fy = (i32)((sy >> 8) & 0xff);
        if (iy >= (i32)img->h - 1) { iy = img->h - 1; fy = 0; }
        u32 *r0 = img->px + (u64)iy * img->w, *r1 = r0 + (iy + 1 < (i32)img->h ? img->w : 0);
        u32 *dst = fb + (u64)y * W + ax;
        for (i32 x = ax; x < bx; x++, dst++) {
            i64 sx = ((i64)(x - x0) * step + step / 2) - 32768;
            if (sx < 0) sx = 0;
            i32 ix = (i32)(sx >> 16), fx = (i32)((sx >> 8) & 0xff);
            i32 ix1 = ix + 1;
            if (ix1 >= (i32)img->w) { ix1 = ix = img->w - 1; fx = 0; }
            u32 a = r0[ix], b = r0[ix1], c = r1[ix], d = r1[ix1], s = 0;
            for (int sh = 0; sh < 32; sh += 8) {
                u32 top = (((a >> sh) & 0xff) * (256 - fx) + ((b >> sh) & 0xff) * fx) >> 8;
                u32 bot = (((c >> sh) & 0xff) * (256 - fx) + ((d >> sh) & 0xff) * fx) >> 8;
                s |= ((top * (256 - fy) + bot * fy) >> 8) << sh;
            }
            *dst = blend(*dst, s, op);
        }
    }
}

// Thanh bo tròn hai đầu (cao h), màu rgb, độ đậm op
static void pill(i32 x, i32 y, i32 w, i32 h, u32 rgb, u32 op) {
    if (w <= 0 || op == 0) return;
    i32 r = h / 2;
    for (i32 j = 0; j < h; j++) {
        i32 yy = y + j; if (yy < clip.y0 || yy >= clip.y1) continue;
        for (i32 i = 0; i < w; i++) {
            i32 xx = x + i; if (xx < clip.x0 || xx >= clip.x1) continue;
            // độ phủ ở hai đầu: khoảng cách tới tâm nửa vòng tròn (x2 để có nửa pixel)
            i32 cxp = i < r ? r : (i >= w - r ? w - r - 1 : i);
            i32 dx = 2 * (i - cxp), dy = 2 * j + 1 - h;
            i32 d2 = dx * dx + dy * dy, R2 = h * h;
            u32 cov = 256;
            if (d2 > R2) { i32 over = d2 - R2; cov = over >= 4 * h ? 0 : 256 - over * 256 / (4 * h); }
            if (!cov) continue;
            u32 s = 0xff000000u | rgb;
            fb[(u64)yy * W + xx] = blend(fb[(u64)yy * W + xx], s, (op * cov) >> 8);
        }
    }
}

static void fill_bg(Rect r) {
    for (i32 y = r.y0; y < r.y1; y++) memcpy(fb + (u64)y * W + r.x0, bgbuf + (u64)y * W + r.x0, (UINTN)(r.x1 - r.x0) * 4);
}
static void present(Rect r) {
    gop->Blt(gop, fb, BltBufferToVideo, r.x0, r.y0, r.x0, r.y0, r.x1 - r.x0, r.y1 - r.y0, (UINTN)W * 4);
}
static Rect rect_clamp(i32 x0, i32 y0, i32 x1, i32 y1) {
    Rect r = { x0 < 0 ? 0 : x0, y0 < 0 ? 0 : y0, x1 > W ? W : x1, y1 > H ? H : y1 };
    return r;
}

static int screen_init(void) {
    if (EFI_IS_ERR(BS->LocateProtocol(&GOP_GUID, 0, (void **)&gop)) || !gop) return 0;
    // Ưu tiên 1920x1080 nếu có, không thì giữ chế độ hiện tại
    for (u32 m = 0; m < gop->Mode->MaxMode; m++) {
        UINTN sz; EFI_GOP_MODE_INFO *info;
        if (EFI_IS_ERR(gop->QueryMode(gop, m, &sz, &info))) continue;
        if (info->HorizontalResolution == 1920 && info->VerticalResolution == 1080) {
            if (m != gop->Mode->Mode) gop->SetMode(gop, m);
            break;
        }
    }
    W = gop->Mode->Info->HorizontalResolution;
    H = gop->Mode->Info->VerticalResolution;
    fb = alloc((UINTN)W * H * 4);
    bgbuf = alloc((UINTN)W * H * 4);
    return fb && bgbuf;
}

// ===================== Hoạt ảnh =====================
static i32 clampi(i32 v, i32 a, i32 b) { return v < a ? a : v > b ? b : v; }
// ease-out bậc 3: t trong [0, dur] -> 0..256
static u32 ease(i64 t, i64 dur) {
    if (t <= 0) return 0;
    if (t >= dur) return 256;
    i64 x = 256 - t * 256 / dur;           // 256..0
    return (u32)(256 - x * x * x / 65536);
}
// sóng "thở" mượt, chu kỳ ms -> 0..256
static u32 breath(i64 t, i64 period) {
    i64 p = t % period, half = period / 2;
    i64 v = p < half ? p : period - p;     // 0..half
    i64 x = v * 256 / half;                // 0..256
    return (u32)(x * x * (768 - 2 * x) / 65536);   // smoothstep
}

// ===================== Khởi động hệ điều hành =====================
static DP *dp_next(DP *d) { return (DP *)((u8 *)d + (d->Length[0] | (d->Length[1] << 8))); }

static UINTN dp_size(DP *d) {   // không gồm nút kết thúc
    UINTN n = 0;
    while (d->Type != DP_END) { n += d->Length[0] | (d->Length[1] << 8); d = dp_next(d); }
    return n;
}

static int file_exists(EFI_HANDLE h, CHAR16 *path) {
    SFS *fs; FILE *root, *f;
    if (EFI_IS_ERR(BS->HandleProtocol(h, &SFS_GUID, (void **)&fs))) return 0;
    if (EFI_IS_ERR(fs->OpenVolume(fs, &root))) return 0;
    int ok = !EFI_IS_ERR(root->Open(root, &f, path, FILE_MODE_READ, 0));
    if (ok) f->Close(f);
    root->Close(root);
    return ok;
}

// Tìm phân vùng theo GUID; không thấy thì tìm phân vùng nào có file loader
static EFI_HANDLE find_volume(Entry *e) {
    UINTN n = 0; EFI_HANDLE *hs = 0, found = 0;
    BS->LocateHandleBuffer(ByProtocol, &SFS_GUID, 0, &n, &hs);
    for (UINTN i = 0; i < n && !found; i++) {
        DP *d;
        if (EFI_IS_ERR(BS->HandleProtocol(hs[i], &DP_GUID, (void **)&d))) continue;
        for (; d->Type != DP_END; d = dp_next(d)) {
            if (d->Type == DP_MEDIA && d->SubType == DP_HD) {
                u8 *b = (u8 *)d;
                if (b[41] == 2 && guid_eq(b + 24, &e->part) && file_exists(hs[i], e->path)) found = hs[i];
            }
        }
    }
    for (UINTN i = 0; i < n && !found; i++) if (file_exists(hs[i], e->path)) found = hs[i];
    if (hs) BS->FreePool(hs);
    return found;
}

static EFI_STATUS boot_entry(Entry *e) {
    EFI_HANDLE vol = find_volume(e);
    if (!vol) return EFI_NOT_FOUND;
    DP *base;
    if (EFI_IS_ERR(BS->HandleProtocol(vol, &DP_GUID, (void **)&base))) return EFI_NOT_FOUND;
    UINTN bsz = dp_size(base), plen = wlen(e->path), fsz = 4 + (plen + 1) * 2;
    u8 *dp = alloc(bsz + fsz + 4);
    if (!dp) return EFI_LOAD_ERROR;
    memcpy(dp, base, bsz);
    u8 *f = dp + bsz;
    f[0] = DP_MEDIA; f[1] = DP_FILE; f[2] = (u8)fsz; f[3] = (u8)(fsz >> 8);
    memcpy(f + 4, e->path, (plen + 1) * 2);
    u8 *end = f + fsz; end[0] = DP_END; end[1] = 0xFF; end[2] = 4; end[3] = 0;

    EFI_HANDLE img;
    EFI_STATUS s = BS->LoadImage(0, SELF, dp, 0, 0, &img);
    if (EFI_IS_ERR(s)) return s;
    if (e->options) {
        EFI_LOADED_IMAGE *li;
        if (!EFI_IS_ERR(BS->HandleProtocol(img, &LIP_GUID, (void **)&li))) {
            li->LoadOptions = e->options;
            li->LoadOptionsSize = (u32)((wlen(e->options) + 1) * 2);
        }
    }
    s = BS->StartImage(img, 0, 0);
    return EFI_IS_ERR(s) ? s : EFI_ABORTED;   // quay lại được đây nghĩa là không boot được
}

// ===================== Menu =====================
static Img bg, title, hint, paused, booting, greet;
static Img icon[N_ENTRIES], glow[N_ENTRIES], lon[N_ENTRIES], loff[N_ENTRIES];
static Img count[31];

static int load_assets(void) {
    static char nb[32];
    int ok = load_img(&bg, "bg") && load_img(&title, "title") && load_img(&hint, "hint") &&
             load_img(&paused, "paused") && load_img(&booting, "booting");
    // Lời chào theo buổi (giờ Việt Nam)
    EFI_TIME t; int hour = 12;
    if (!EFI_IS_ERR(ST->RuntimeServices->GetTime(&t, 0))) hour = (t.Hour + TZ_OFFSET_H) % 24;
    const char *g = hour >= 4 && hour < 11 ? "greet_sang" : hour >= 11 && hour < 18 ? "greet_chieu" : "greet_toi";
    ok = ok && load_img(&greet, g);
    for (int i = 0; i < N_ENTRIES; i++) {
        const char *pre[4] = { "icon_", "glow_", "label_", "label_" };
        Img *dst[4] = { &icon[i], &glow[i], &lon[i], &loff[i] };
        for (int k = 0; k < 4; k++) {
            int n = 0;
            for (const char *p = pre[k]; *p; p++) nb[n++] = *p;
            for (const char *p = ENTRIES[i].key; *p; p++) nb[n++] = *p;
            if (k == 2) { nb[n++] = '_'; nb[n++] = 'o'; nb[n++] = 'n'; }
            if (k == 3) { nb[n++] = '_'; nb[n++] = 'o'; nb[n++] = 'f'; nb[n++] = 'f'; }
            nb[n] = 0;
            ok = ok && load_img(dst[k], nb);
        }
    }
    for (int i = 0; i <= 30; i++) {
        int n = 0; nb[n++] = 'c'; nb[n++] = 'o'; nb[n++] = 'u'; nb[n++] = 'n'; nb[n++] = 't'; nb[n++] = '_';
        if (i >= 10) nb[n++] = '0' + i / 10;
        nb[n++] = '0' + i % 10; nb[n] = 0;
        ok = ok && load_img(&count[i], nb);
    }
    return ok;
}

static void scale_bg(void) {
    for (i32 y = 0; y < H; y++) {
        u32 sy = (u32)((u64)y * bg.h / H);
        for (i32 x = 0; x < W; x++) bgbuf[(u64)y * W + x] = bg.px[(u64)sy * bg.w + (u64)x * bg.w / W] | 0xff000000u;
    }
}

// Toạ độ thiết kế cho 1080p, co theo chiều cao màn hình
#define YS(v) ((i32)((i64)(v) * H / 1080))

static i32 cur = 0;
static i32 sel[N_ENTRIES];          // 0..1024: mức "được chọn" của từng mục (chạy mượt)
static int is_paused = 0, is_booting = 0;
static i64 paused_at = 0, boot_at = 0, last_ms = 0;

static Rect R_TOP, R_MID, R_BOT;

static void render(Rect r, i64 t) {
    clip = r;
    fill_bg(r);
    i32 cx = W / 2;
    // Lời chào + tiêu đề: hiện dần, trượt lên
    u32 a = ease(t, 700);
    draw(&greet, cx, YS(230) + (i32)(24 * (256 - a) / 256), greet.w, a);
    a = ease(t - 250, 600);
    draw(&title, cx, YS(318) + (i32)(14 * (256 - a) / 256), title.w, a * 230 / 256);

    // Hàng icon
    for (int i = 0; i < N_ENTRIES; i++) {
        i32 x = cx + (i - 1) * 380;
        u32 in = ease(t - 350 - i * 120, 650);
        i32 slide = (i32)(40 * (256 - in) / 256);
        i32 s = sel[i];
        i32 iy = YS(560) + slide - 12 * s / 1024;
        u32 br = breath(t, 2600);
        u32 gop_ = (u32)((i64)s * (170 + 86 * br / 256) / 1024);           // quầng sáng "thở"
        draw(&glow[i], x, iy, glow[i].w, gop_ * in / 256);
        i32 size = 150 + 42 * s / 1024;
        u32 op = (u32)(150 + 106 * s / 1024);
        draw(&icon[i], x, iy, size, op * in / 256);
        i32 ly = YS(560) + 128 + slide;
        draw(&loff[i], x, ly, loff[i].w, (u32)((1024 - s) * 256 / 1024) * in / 256);
        draw(&lon[i],  x, ly, lon[i].w,  (u32)(s * 256 / 1024) * in / 256);
    }

    // Đếm giờ / trạng thái
    u32 bot = ease(t - 800, 500);
    i32 by = YS(905);
    if (is_booting) {
        draw(&booting, cx, by + 24, booting.w, ease(t - boot_at, 250));
    } else {
        u32 fade = is_paused ? 256 - ease(t - paused_at, 300) : 256;
        i64 left = TIMEOUT_MS - t; if (left < 0) left = 0;
        i32 bw = 420;
        pill(cx - bw / 2, by, bw, 6, 0x1a1f2a, bot * fade / 256);
        pill(cx - bw / 2, by, (i32)(bw * left / TIMEOUT_MS), 6, ENTRIES[cur].color, bot * fade / 256);
        i32 n = clampi((i32)((left + 999) / 1000), 0, 30);
        draw(&count[n], cx, by + 34, count[n].w, bot * fade / 256);
        if (is_paused) draw(&paused, cx, by + 20, paused.w, ease(t - paused_at - 150, 350) * bot / 256);
    }
    draw(&hint, cx, H - YS(56), hint.w, ease(t - 1000, 600));
    present(r);
}

static void full_redraw(i64 t) { Rect all = { 0, 0, W, H }; render(all, t); }

static void fade_out(i64 t0) {
    for (;;) {
        i64 t = now_ms(), k = (t - t0) * 256 / 350;
        if (k >= 256) break;
        Rect all = { 0, 0, W, H };
        clip = all;
        render(all, t);   // vẽ đầy đủ rồi làm tối dần
        for (u64 i = 0; i < (u64)W * H; i++) {
            u32 c = fb[i];
            fb[i] = (((c & 0xff00ff) * (u32)(256 - k) >> 8) & 0xff00ff) | (((c & 0x00ff00) * (u32)(256 - k) >> 8) & 0x00ff00);
        }
        present(all);
    }
    memset(fb, 0, (UINTN)W * H * 4);
    Rect all = { 0, 0, W, H }; present(all);
}

static void set_cur(i32 c) {
    cur = clampi(c, 0, N_ENTRIES - 1);
}

EFI_STATUS API efi_main(EFI_HANDLE image, EFI_SYSTEM_TABLE *st) {
    ST = st; BS = st->BootServices; SELF = image;
    BS->SetWatchdogTimer(0, 0, 0, 0);       // không để firmware tự khởi động lại khi ngồi ở menu lâu

    EFI_LOADED_IMAGE *li; SFS *fs;
    if (EFI_IS_ERR(BS->HandleProtocol(image, &LIP_GUID, (void **)&li)) ||
        EFI_IS_ERR(BS->HandleProtocol(li->DeviceHandle, &SFS_GUID, (void **)&fs)) ||
        EFI_IS_ERR(fs->OpenVolume(fs, &ROOT))) { say(u"Triboot: khong mo duoc o chua file\r\n"); return EFI_LOAD_ERROR; }
    if (!load_assets()) { say(u"Triboot: thieu file anh trong \\EFI\\triboot\\assets\r\n"); return EFI_LOAD_ERROR; }
    if (!screen_init()) { say(u"Triboot: khong co che do do hoa\r\n"); return EFI_LOAD_ERROR; }
    st->ConOut->EnableCursor(st->ConOut, 0);
    scale_bg();
    clock_init();

    i32 cx = W / 2;
    R_TOP = rect_clamp(cx - 640, YS(150), cx + 640, YS(360));
    R_MID = rect_clamp(cx - 380 - 240, YS(560) - 250, cx + 380 + 240, YS(560) + 175);
    R_BOT = rect_clamp(cx - 520, YS(880), cx + 520, H);
    sel[cur] = 0;
    full_redraw(0);

    for (;;) {
        i64 t = now_ms();
        i64 dt = t - last_ms; last_ms = t;

        // Phím
        EFI_INPUT_KEY k;
        while (!EFI_IS_ERR(st->ConIn->ReadKeyStroke(st->ConIn, &k))) {
            if (is_booting) continue;
            int moved = 0, go = 0;
            if (k.ScanCode == SCAN_LEFT || k.ScanCode == SCAN_UP)    { set_cur(cur - 1); moved = 1; }
            if (k.ScanCode == SCAN_RIGHT || k.ScanCode == SCAN_DOWN) { set_cur(cur + 1); moved = 1; }
            if (k.UnicodeChar >= '1' && k.UnicodeChar <= '0' + N_ENTRIES) { set_cur(k.UnicodeChar - '1'); go = 1; }
            if (k.UnicodeChar == '\r' || k.UnicodeChar == ' ') go = 1;
            if (k.ScanCode == SCAN_ESC) {           // về GRUB
                memset(fb, 0, (UINTN)W * H * 4); Rect all = { 0, 0, W, H }; present(all);
                st->ConOut->ClearScreen(st->ConOut);
                return EFI_SUCCESS;
            }
            if ((moved || k.UnicodeChar) && !is_paused && !go) { is_paused = 1; paused_at = t; }
            if (go) { is_booting = 1; boot_at = t; }
        }
        if (!is_paused && !is_booting && t >= TIMEOUT_MS) { is_booting = 1; boot_at = t; }

        // Mức chọn chạy mượt về đích
        if (dt > 100) dt = 100;
        for (int i = 0; i < N_ENTRIES; i++) {
            i32 target = i == cur ? 1024 : 0;
            sel[i] += (i32)((target - sel[i]) * dt / (dt + 70));
            if (sel[i] < 0) sel[i] = 0;
            if (sel[i] > 1024) sel[i] = 1024;
            if (sel[i] != target && (target - sel[i] < 4 && sel[i] - target < 4)) sel[i] = target;
        }

        if (t < 1700) render(R_TOP, t);
        render(R_MID, t);
        render(R_BOT, t);

        if (is_booting && t - boot_at > 300) {
            fade_out(now_ms());
            EFI_STATUS s = boot_entry(&ENTRIES[cur]);
            // Không boot được: báo lỗi rồi quay lại menu
            st->ConOut->ClearScreen(st->ConOut);
            say(u"Khong khoi dong duoc muc nay (loi ");
            CHAR16 num[20]; int n = 0; u64 v = s & 0xffff; do { num[n++] = '0' + v % 10; v /= 10; } while (v);
            CHAR16 out[22]; int m = 0; while (n) out[m++] = num[--n]; out[m++] = ')'; out[m] = 0;
            say(out); say(u". Quay lai menu sau 4 giay...\r\n");
            BS->Stall(4000000);
            is_booting = 0; is_paused = 1; paused_at = now_ms() - 1000;
            full_redraw(now_ms());
        }

        // Giữ ~60 khung hình/giây
        while (now_ms() - t < 16) BS->Stall(500);
    }
}
