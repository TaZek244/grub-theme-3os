// KAFKA.SYS // LINE 01 — menu UEFI dạng TUYẾN TÀU NGANG (cùng hạ tầng với triboot.c).
// Các trạm = hệ điều hành đã cài (trạm nào không tìm thấy loader thì tự ẩn) + ga cuối "TỪ BỎ"
// (Enter → hộp Tắt máy / Khởi động lại). Đoàn tàu pixel chạy mượt tới trạm đang chọn; Enter = tàu rời ga rồi khởi động.
// Ảnh do kafka-src/make-kafka-line.py sinh (định dạng .tbi), đặt ở \EFI\kafka\assets\.
// GRUB chainload file này; Esc quay lại GRUB, lỗi khởi tạo thì GRUB tự rơi xuống mục dự phòng.
#include "efi.h"

// ===================== Cấu hình máy =====================
#define TIMEOUT_MS     10000          // tự khởi động trạm đầu tiên sau 10 giây
#define ASSET_DIR      u"\\EFI\\kafka\\assets\\"

// Bố cục — phải khớp kafka-src/make-kafka-line.py (selftest của nó kiểm tra các dòng #define này)
#define TRACK_Y 800
#define SIGN_FOOT 14
#define TRAIN_HEAD_W 256
#define TRAIN_FOOT 2
#define STATION_MARGIN 260

typedef struct {
    const char *key;                  // tên ảnh: sign_<key>_on/off
    EFI_GUID    part;                 // GUID phân vùng (GPT) chứa loader
    CHAR16     *path;                 // đường dẫn loader trên phân vùng đó
    CHAR16     *options;              // tham số truyền cho loader (NULL = không có)
} Entry;

static Entry ENTRIES[] = {
    { "arch",
      {0x124a725e, 0x8a92, 0x4d60, {0xac, 0xcd, 0x91, 0x69, 0x7f, 0x6e, 0x1b, 0x76}},
      u"\\vmlinuz-linux",
      u"initrd=\\initramfs-linux.img root=UUID=8006d6ff-4672-4328-a7b4-86ce5b21ba88 rw loglevel=3 quiet splash" },
    { "windows",
      {0x2ecc4d3c, 0x983c, 0x4039, {0x89, 0x14, 0x55, 0x39, 0x98, 0x47, 0x08, 0x95}},
      u"\\EFI\\Microsoft\\Boot\\bootmgfw.efi", 0 },
    { "ubuntu",
      {0x2ecc4d3c, 0x983c, 0x4039, {0x89, 0x14, 0x55, 0x39, 0x98, 0x47, 0x08, 0x95}},
      u"\\EFI\\ubuntu\\shimx64.efi", 0 },
};
#define N_ENTRIES 3
#define MAX_ST (N_ENTRIES + 1)

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
static FILE *ROOT;

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
    for (u64 i = 0; i < (u64)w * h; i++) {
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
static u32 *fb, *bgbuf;
typedef struct { i32 x0, y0, x1, y1; } Rect;
static Rect clip;

static inline u32 blend(u32 d, u32 s, u32 op) {   // s premultiplied, op 0..256
    u32 sa = ((s >> 24) * op) >> 8;
    if (!sa) return d;
    if (sa == 255 && op >= 256) return s;
    u32 inv = 255 - sa, out = 0;
    for (int sh = 0; sh < 24; sh += 8) {
        u32 sc = (((s >> sh) & 0xff) * op) >> 8;
        u32 v = sc + (((d >> sh) & 0xff) * inv + 127) / 255;
        out |= (v > 255 ? 255 : v) << sh;
    }
    return out;
}

// Vẽ ảnh 1:1, góc trên trái (x, y), độ đậm op (0..256). Ảnh pixel art nên không co giãn.
static void blit(const Img *img, i32 x0, i32 y0, u32 op) {
    if (!img->px || op == 0) return;
    if (op > 256) op = 256;
    i32 ax = x0 < clip.x0 ? clip.x0 : x0, ay = y0 < clip.y0 ? clip.y0 : y0;
    i32 bx = x0 + (i32)img->w > clip.x1 ? clip.x1 : x0 + (i32)img->w;
    i32 by = y0 + (i32)img->h > clip.y1 ? clip.y1 : y0 + (i32)img->h;
    for (i32 y = ay; y < by; y++) {
        u32 *src = img->px + (u64)(y - y0) * img->w + (ax - x0);
        u32 *dst = fb + (u64)y * W + ax;
        for (i32 x = ax; x < bx; x++, src++, dst++) *dst = blend(*dst, *src, op);
    }
}
static void blit_c(const Img *img, i32 cx, i32 y, u32 op) { blit(img, cx - (i32)img->w / 2, y, op); }

// Hình chữ nhật đặc (màu 0xRRGGBB), độ đậm op
static void box(i32 x, i32 y, i32 w, i32 h, u32 rgb, u32 op) {
    i32 ax = x < clip.x0 ? clip.x0 : x, ay = y < clip.y0 ? clip.y0 : y;
    i32 bx = x + w > clip.x1 ? clip.x1 : x + w, by = y + h > clip.y1 ? clip.y1 : y + h;
    u32 s = 0xff000000u | rgb;
    for (i32 yy = ay; yy < by; yy++)
        for (i32 xx = ax; xx < bx; xx++) fb[(u64)yy * W + xx] = blend(fb[(u64)yy * W + xx], s, op);
}

// Làm tối cả vùng clip (k: 0..256 = mức giữ lại)
static void dim(u32 k) {
    for (i32 y = clip.y0; y < clip.y1; y++) {
        u32 *p = fb + (u64)y * W + clip.x0;
        for (i32 x = clip.x0; x < clip.x1; x++, p++) {
            u32 c = *p;
            *p = (((c & 0xff00ff) * k >> 8) & 0xff00ff) | (((c & 0x00ff00) * k >> 8) & 0x00ff00);
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
static u32 ease(i64 t, i64 dur) {            // ease-out bậc 3: 0..256
    if (t <= 0) return 0;
    if (t >= dur) return 256;
    i64 x = 256 - t * 256 / dur;
    return (u32)(256 - x * x * x / 65536);
}
static u32 breath(i64 t, i64 period) {       // 0..256, mượt
    i64 p = t % period, half = period / 2;
    i64 v = p < half ? p : period - p;
    i64 x = v * 256 / half;
    return (u32)(x * x * (768 - 2 * x) / 65536);
}

// ===================== Khởi động hệ điều hành =====================
static DP *dp_next(DP *d) { return (DP *)((u8 *)d + (d->Length[0] | (d->Length[1] << 8))); }
static UINTN dp_size(DP *d) {
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
    return EFI_IS_ERR(s) ? s : EFI_ABORTED;
}

// ===================== Trạm + ảnh =====================
typedef struct { i32 entry; Img on, off; i32 x; } Station;   // entry = -1: ga cuối "TỪ BỎ"
static Station stn[MAX_ST];
static i32 n_st = 0, n_os = 0;
static Img bg, train_l, train_r, paused, booting, panel, btn_on[2], btn_off[2];
static Img count[31];

static void name_of(char *nb, const char *a, const char *b, const char *c) {
    int n = 0;
    for (const char *p = a; *p; p++) nb[n++] = *p;
    for (const char *p = b; *p; p++) nb[n++] = *p;
    for (const char *p = c; *p; p++) nb[n++] = *p;
    nb[n] = 0;
}

static int load_assets(void) {
    char nb[40];
    int ok = load_img(&bg, "bg") && load_img(&train_l, "train_l") && load_img(&train_r, "train_r") &&
             load_img(&paused, "paused") && load_img(&booting, "booting") && load_img(&panel, "quit_panel") &&
             load_img(&btn_on[0], "btn_off_on") && load_img(&btn_off[0], "btn_off_off") &&
             load_img(&btn_on[1], "btn_rst_on") && load_img(&btn_off[1], "btn_rst_off");
    // Trạm: chỉ hệ điều hành tìm thấy loader. Không thấy cái nào thì vẫn hiện hết (để còn thử / báo lỗi khi chọn).
    for (int pass = 0; pass < 2 && n_os == 0; pass++)
        for (int i = 0; i < N_ENTRIES; i++)
            if (pass == 1 || find_volume(&ENTRIES[i])) { stn[n_st].entry = i; n_st++; n_os++; }
    stn[n_st++].entry = -1;
    for (int i = 0; i < n_st; i++) {
        const char *k = stn[i].entry < 0 ? "quit" : ENTRIES[stn[i].entry].key;
        name_of(nb, "sign_", k, "_on");  ok = ok && load_img(&stn[i].on, nb);
        name_of(nb, "sign_", k, "_off"); ok = ok && load_img(&stn[i].off, nb);
    }
    for (int i = 0; i <= 30; i++) {
        char num[3] = { 0, 0, 0 };
        if (i >= 10) { num[0] = '0' + i / 10; num[1] = '0' + i % 10; } else num[0] = '0' + i;
        name_of(nb, "count_", num, "");
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

#define YS(v) ((i32)((i64)(v) * H / 1080))

// ===================== Trạng thái =====================
static i32 cur = 0, sel[MAX_ST];
static i32 train_x = -100000;                  // vị trí tâm đầu tàu (px * 256)
static int facing_r = 1;                       // đầu tàu quay phải?
static int is_paused = 0, departing = 0, popup = 0, pchoice = 0, quitting = 0;
static i64 paused_at = 0, dep_at = 0, popup_at = 0, last_ms = 0;
static Rect R_MID, R_BOT, R_ALL;
static i32 track_y, sign_top;

static void draw_train(i32 hx) {               // hx = tâm đầu tàu (px)
    const Img *t = facing_r ? &train_r : &train_l;
    i32 x = facing_r ? hx + TRAIN_HEAD_W / 2 - (i32)t->w : hx - TRAIN_HEAD_W / 2;
    blit(t, x, track_y + TRAIN_FOOT - (i32)t->h, 256);
}

static i32 depart_offset(i64 t) {              // tàu rời ga: nhanh dần
    i64 e = t - dep_at; if (e < 0) e = 0;
    return (i32)(e * e / 420);
}

static void render_scene(Rect r, i64 t) {
    clip = r;
    fill_bg(r);
    // biển trạm: hiện dần từng biển, biển đang chọn nhô lên
    for (int i = 0; i < n_st; i++) {
        u32 in = ease(t - 250 - i * 110, 520);
        i32 s = sel[i];
        i32 y = track_y + SIGN_FOOT - (i32)stn[i].on.h + (i32)(30 * (256 - in) / 256) - 8 * s / 1024;
        i32 x = stn[i].x - ((i32)stn[i].on.w - 4) / 2;
        blit(&stn[i].off, x, y, (u32)((1024 - s) * 256 / 1024) * in / 256);
        blit(&stn[i].on, x, y, (u32)(s * 256 / 1024) * in / 256);
    }
    // đoàn tàu
    i32 hx = train_x >> 8;
    if (departing) hx += facing_r ? depart_offset(t) : -depart_offset(t);
    draw_train(hx);
    // đèn nhấp nháy trên ray dưới trạm đang chọn (tàu đã tới gần)
    if (!departing) {
        i32 d = hx - stn[cur].x; if (d < 0) d = -d;
        if (d < 4) box(stn[cur].x - 6, track_y + 22, 12, 6, 0xf08cbb, 80 + 176 * breath(t, 1400) / 256);
    }
    // đếm giờ / trạng thái
    u32 bot = ease(t - 900, 500);
    i32 by = YS(912);
    i32 cx = W / 2;
    if (departing) {
        blit_c(&booting, cx, by + 14, ease(t - dep_at, 250));
    } else if (n_os) {
        u32 fade = is_paused ? 256 - ease(t - paused_at, 300) : 256;
        i64 left = TIMEOUT_MS - t; if (left < 0) left = 0;
        i32 bw = 480;
        box(cx - bw / 2, by, bw, 8, 0x3a2a3f, bot * fade / 256);
        box(cx - bw / 2, by, (i32)(bw * left / TIMEOUT_MS) & ~3, 8, 0xf08cbb, bot * fade / 256);
        i32 n = clampi((i32)((left + 999) / 1000), 0, 30);
        blit_c(&count[n], cx, by + 14, bot * fade / 256);
        if (is_paused) blit_c(&paused, cx, by + 14, ease(t - paused_at - 150, 350) * bot / 256);
    }
}

static void render_popup(i64 t) {
    Rect all = R_ALL;
    render_scene(all, t);
    clip = all;
    u32 a = ease(t - popup_at, 220);
    dim(256 - 150 * a / 256);
    i32 px = (W - (i32)panel.w) / 2, py = (H - (i32)panel.h) / 2 - 40 + (i32)(20 * (256 - a) / 256);
    blit(&panel, px, py, a);
    for (int i = 0; i < 2; i++) {
        const Img *b = i == pchoice ? &btn_on[i] : &btn_off[i];
        i32 bx = W / 2 + (i == 0 ? -24 - (i32)b->w : 24);
        blit(b, bx, py + 236, a);
    }
    present(all);
}

static void fade_out(i64 t0) {
    for (;;) {
        i64 t = now_ms(), k = (t - t0) * 256 / 350;
        if (k >= 256) break;
        if (popup) render_popup(t); else render_scene(R_ALL, t);
        clip = R_ALL;
        dim((u32)(256 - k));
        present(R_ALL);
    }
    memset(fb, 0, (UINTN)W * H * 4);
    present(R_ALL);
}

static void set_cur(i32 c) { cur = clampi(c, 0, n_st - 1); }

EFI_STATUS API efi_main(EFI_HANDLE image, EFI_SYSTEM_TABLE *st) {
    ST = st; BS = st->BootServices; SELF = image;
    BS->SetWatchdogTimer(0, 0, 0, 0);

    EFI_LOADED_IMAGE *li; SFS *fs;
    if (EFI_IS_ERR(BS->HandleProtocol(image, &LIP_GUID, (void **)&li)) ||
        EFI_IS_ERR(BS->HandleProtocol(li->DeviceHandle, &SFS_GUID, (void **)&fs)) ||
        EFI_IS_ERR(fs->OpenVolume(fs, &ROOT))) { say(u"Kafka: khong mo duoc o chua file\r\n"); return EFI_LOAD_ERROR; }
    if (!load_assets()) { say(u"Kafka: thieu file anh trong \\EFI\\kafka\\assets\r\n"); return EFI_LOAD_ERROR; }
    if (!screen_init()) { say(u"Kafka: khong co che do do hoa\r\n"); return EFI_LOAD_ERROR; }
    st->ConOut->EnableCursor(st->ConOut, 0);
    scale_bg();
    clock_init();

    track_y = YS(TRACK_Y);
    for (int i = 0; i < n_st; i++)
        stn[i].x = n_st == 1 ? W / 2 : STATION_MARGIN + (W - 2 * STATION_MARGIN) * i / (n_st - 1);
    sign_top = track_y + SIGN_FOOT - (i32)stn[0].on.h - 16;
    R_ALL = rect_clamp(0, 0, W, H);
    R_MID = rect_clamp(0, sign_top, W, track_y + 40);
    R_BOT = rect_clamp(W / 2 - 520, YS(900), W / 2 + 520, YS(980));
    train_x = (-(i32)train_r.w) << 8;          // tàu từ ngoài mép trái chạy vào ga
    render_scene(R_ALL, 0);
    present(R_ALL);

    int popup_drawn = 0;
    for (;;) {
        i64 t = now_ms();
        i64 dt = t - last_ms; last_ms = t;

        EFI_INPUT_KEY k;
        while (!EFI_IS_ERR(st->ConIn->ReadKeyStroke(st->ConIn, &k))) {
            if (departing || quitting) continue;
            if (popup) {
                if (k.ScanCode == SCAN_LEFT || k.ScanCode == SCAN_UP) pchoice = 0;
                if (k.ScanCode == SCAN_RIGHT || k.ScanCode == SCAN_DOWN) pchoice = 1;
                if (k.ScanCode == SCAN_ESC) { popup = 0; render_scene(R_ALL, t); present(R_ALL); continue; }
                if (k.UnicodeChar == '\r' || k.UnicodeChar == ' ') quitting = 1;
                popup_drawn = 0;
                continue;
            }
            int go = 0;
            if (k.ScanCode == SCAN_LEFT || k.ScanCode == SCAN_UP)    set_cur(cur - 1);
            if (k.ScanCode == SCAN_RIGHT || k.ScanCode == SCAN_DOWN) set_cur(cur + 1);
            if (k.UnicodeChar >= '1' && k.UnicodeChar < '1' + n_st) { set_cur(k.UnicodeChar - '1'); }
            if (k.UnicodeChar == '\r' || k.UnicodeChar == ' ') go = 1;
            if (k.ScanCode == SCAN_ESC) {           // về GRUB
                memset(fb, 0, (UINTN)W * H * 4); present(R_ALL);
                st->ConOut->ClearScreen(st->ConOut);
                return EFI_SUCCESS;
            }
            if (!is_paused) { is_paused = 1; paused_at = t; }
            if (go) {
                if (stn[cur].entry < 0) { popup = 1; popup_at = t; pchoice = 0; popup_drawn = 0; }
                else { departing = 1; dep_at = t; facing_r = 1; train_x = stn[cur].x << 8; }
            }
        }
        if (!is_paused && !departing && n_os && t >= TIMEOUT_MS) {
            cur = 0; departing = 1; dep_at = t; facing_r = 1; train_x = stn[0].x << 8;
        }

        // tàu chạy về trạm đang chọn (chậm dần khi vào ga), biển trạm sáng/tắt mượt
        if (dt > 100) dt = 100;
        if (t > 150 && !departing) {
            i32 target = stn[cur].x << 8, d = target - train_x;
            if (d > 2 * 256) facing_r = 1; else if (d < -2 * 256) facing_r = 0;
            train_x += (i32)((i64)d * dt / (dt + 150));
            if (d < 256 && d > -256) train_x = target;
        }
        for (int i = 0; i < n_st; i++) {
            i32 target = i == cur ? 1024 : 0;
            sel[i] += (i32)((target - sel[i]) * dt / (dt + 70));
            if (target - sel[i] < 4 && sel[i] - target < 4) sel[i] = target;
        }

        if (popup) {
            if (!popup_drawn || t - popup_at < 260) { render_popup(t); popup_drawn = 1; }
        } else {
            render_scene(R_MID, t); present(R_MID);
            render_scene(R_BOT, t); present(R_BOT);
        }

        if (quitting) {
            fade_out(now_ms());
            st->RuntimeServices->ResetSystem(pchoice == 0 ? 2 /* EfiResetShutdown */ : 0 /* EfiResetCold */, 0, 0, 0);
            return EFI_ABORTED;
        }
        if (departing && depart_offset(t) > W) {
            fade_out(now_ms());
            EFI_STATUS s = boot_entry(&ENTRIES[stn[cur].entry]);
            st->ConOut->ClearScreen(st->ConOut);
            say(u"Khong khoi dong duoc tram nay (loi ");
            CHAR16 num[20]; int n = 0; u64 v = s & 0xffff; do { num[n++] = '0' + v % 10; v /= 10; } while (v);
            CHAR16 out[22]; int m = 0; while (n) out[m++] = num[--n]; out[m++] = ')'; out[m] = 0;
            say(out); say(u". Quay lai menu sau 4 giay...\r\n");
            BS->Stall(4000000);
            departing = 0; is_paused = 1; paused_at = now_ms() - 1000;
            render_scene(R_ALL, now_ms()); present(R_ALL);
        }
        while (now_ms() - t < 16) BS->Stall(500);
    }
}
