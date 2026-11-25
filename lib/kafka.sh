#!/usr/bin/env bash
# ==============================================================================
# THEME GRUB "KAFKA.SYS // DEPARTURES" (lib/kafka.sh)
# Theme pixel cùng bộ với dotfiles Hyprland Kafka (trình đăng nhập KAFKA.SYS):
# bảng giờ tàu LED ở nhà ga, đoàn tàu pixel, ảnh nền pixel hoá, font pixel có dấu tiếng Việt, icon pixel.
# Ảnh Kafka (có bản quyền) KHÔNG nằm trong repo: sinh lúc cài từ thư mục dotfiles ($KAFKA_DESKTOP_DIR);
# không có thì tự vẽ nền tím + chú nhện.
# ==============================================================================

KAFKA_SRC="$ROOT_DIR/kafka-src"
KAFKA_OUT="$ROOT_DIR/kafka"

# Tìm file đầu tiên tồn tại trong danh sách
_kafka_first() { local f; for f in "$@"; do [ -f "$f" ] && { echo "$f"; return 0; }; done; return 1; }

# Dựng font pf2 (Kafka Pixel VN 7/28/35/42): ưu tiên font pixel có dấu dựng từ dotfiles, không có thì $KAFKA_FALLBACK_FONT
_kafka_fonts() {
    local ttf="" builder="$KAFKA_DESKTOP_DIR/fonts/build-kafka-pixel-font.py" tmp
    if [ -f "$builder" ] && grep -q -- "--vietnamese" "$builder"; then
        tmp=$(mktemp -d)
        python3 "$builder" --vietnamese --out "$tmp/KafkaPixelVN.ttf" >/dev/null && ttf="$tmp/KafkaPixelVN.ttf"
    fi
    [ -n "$ttf" ] && [ -f "$ttf" ] || { ttf="$KAFKA_FALLBACK_FONT"; log_warn "Không có font Kafka Pixel VN, dùng $(basename "$ttf")"; }
    rm -f "$KAFKA_OUT"/*.pf2
    local s
    for s in 7 28 35 42; do   # bội số của 7 → mỗi điểm pixel đúng 1/4/5/6 px, chữ sắc (7 chỉ để thanh đếm ngược mảnh)
        grub-mkfont -n "Kafka Pixel VN" -s "$s" -o "$KAFKA_OUT/kafka-pixel-$s.pf2" "$ttf"
    done
    # dòng lệnh / sửa lệnh GRUB: font mono thật (font pixel chỉ có chữ HOA, gõ đường dẫn dễ nhầm)
    grub-mkfont -n "Kafka Mono" -s 20 -o "$KAFKA_OUT/kafka-mono-20.pf2" "$KAFKA_MONO_FONT"
    [ -n "${tmp:-}" ] && rm -rf "$tmp"
}

# Sinh toàn bộ ảnh + font + khung intro vào kafka/ (không cần root)
kafka_build_assets() {
    log_info "Tạo theme GRUB KAFKA.SYS (bảng giờ tàu)..."
    local bg
    # ảnh gốc trước (pixel hoá mịn 480x270); không có thì bg-pixel.png 240x135 của trình đăng nhập
    bg=$(_kafka_first "$KAFKA_DESKTOP_DIR/wallpapers/kafka_landscape_3.jpg" \
                      "$KAFKA_DESKTOP_DIR/greetd/kafka-greeter/bg-pixel.png") || bg=""
    [ -n "$bg" ] || log_warn "Không thấy ảnh nền Kafka trong $KAFKA_DESKTOP_DIR, dùng nền tự vẽ"
    rm -f "$KAFKA_OUT"/*.png "$KAFKA_OUT/intro.txt"
    python3 "$KAFKA_SRC/make-kafka-theme.py" "$KAFKA_OUT" ${bg:+--bg "$bg"}
    python3 "$KAFKA_SRC/make-icons.py" "$KAFKA_OUT/icons" --scale 4
    install -m755 "$KAFKA_SRC/intro-cfg.sh" "$KAFKA_OUT/intro-cfg.sh"     # /etc/grub.d/05_kafka_intro gọi bản trong /boot
    _kafka_fonts
    log_ok "Đã tạo theme KAFKA.SYS trong $KAFKA_OUT"
}

# /etc/grub.d/05_kafka_intro: hiệu ứng xuất hiện (chuỗi intro-NN.png) trước menu, chỉ khi theme đang là kafka,
# GRUB ở gfxterm và không ẩn menu (fast-boot / TIMEOUT_STYLE=hidden thì tự bỏ qua). Gọi từ grub_install_base.
KAFKA_INTRO_SCRIPT="/etc/grub.d/05_kafka_intro"
kafka_grub_hook() {
    if [ "$GRUB_THEME_NAME" != "kafka" ]; then
        rm -f "$KAFKA_INTRO_SCRIPT"
        return 0
    fi
    cat > "$KAFKA_INTRO_SCRIPT" <<'EOF5'
#!/bin/sh
# Hiệu ứng xuất hiện của theme GRUB KAFKA.SYS — tự sinh bởi grub-theme-3os (lib/kafka.sh). Gỡ: sudo ./install.sh --kafka --undo
set -e
. /usr/share/grub/grub-mkconfig_lib
THEME_DIR=/boot/grub/themes/kafka
[ -f "$THEME_DIR/intro.txt" ] && [ -f "$THEME_DIR/intro-cfg.sh" ] || exit 0
case "${GRUB_THEME:-}" in */themes/kafka/*) ;; *) exit 0 ;; esac
case "${GRUB_TERMINAL_OUTPUT:-gfxterm}" in *gfxterm*) ;; *) exit 0 ;; esac
[ "${GRUB_TIMEOUT_STYLE:-menu}" = "hidden" ] && exit 0
prepare_grub_to_access_device $(${grub_probe} --target=device "$THEME_DIR")
sh "$THEME_DIR/intro-cfg.sh" "$THEME_DIR" "$(make_system_path_relative_to_its_root "$THEME_DIR")"
EOF5
    chmod 755 "$KAFKA_INTRO_SCRIPT"
}

# Chạy GRUB thật trong QEMU để xem trước (không đụng ổ đĩa/ESP): ảnh menu + GIF hiệu ứng xuất hiện
kafka_preview() {
    local out="${1:-$ROOT_DIR/preview-kafka.png}"
    GIF="${out%.png}-intro.gif" GIF_START=0.3 GIF_SECONDS=4.5 GIF_INTERVAL=0.05 \
        "$KAFKA_SRC/preview-qemu.sh" "$KAFKA_OUT" "$out" 2>&1 | grep -v 'terminating on signal' || true
    log_ok "Ảnh menu: $out — hiệu ứng: ${out%.png}-intro.gif"
}
