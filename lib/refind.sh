#!/usr/bin/env bash
# ==============================================================================
# THƯ VIỆN QUẢN LÝ rEFInd & TỐI ƯU BMP (lib/refind.sh)
# ==============================================================================

refind_entry_nums() {
    efibootmgr | awk -v l="$EFI_LABEL" '
        match($0, /^Boot[0-9A-Fa-f]{4}\*?[[:space:]]+/) {
            name = substr($0, RLENGTH + 1); sub(/[[:space:]].*$/, "", name)
            if (name == l) print substr($0, 5, 4)
        }'
}

# Thêm hoặc gỡ từ khóa "splash" trong mục Arch Linux của refind.conf
refind_set_splash() {
    local mode=$1
    [ -f "$REFIND_CONF" ] || return 0
    awk -v mode="$mode" '
        /menuentry "Arch Linux"/ { inarch = 1 }
        inarch && /^[[:space:]]*}/ { inarch = 0 }
        inarch && /^[[:space:]]*options / {
            if (mode == "add" && $0 !~ / splash/) sub(/"[[:space:]]*$/, " splash\"")
            if (mode == "remove") gsub(/ splash/, "")
        }
        { print }' "$REFIND_CONF" > "$REFIND_CONF.tmp" && mv "$REFIND_CONF.tmp" "$REFIND_CONF"
}

# Cài đặt rEFInd lên ESP của Arch (/boot)
refind_install() {
    log_info "Cài đặt rEFInd lên $ARCH_ESP_MNT..."
    local src disk part tmp nvme_esp stage="$REFIND_DIR.new" old="$REFIND_DIR.old"

    src=$(findmnt -no SOURCE "$ARCH_ESP_MNT")
    [ "$(lsblk -no PARTUUID "$src")" = "$ARCH_ESP_PARTUUID" ] || die "$ARCH_ESP_MNT không phải phân vùng $ARCH_ESP_PARTUUID ($src)"
    disk=/dev/$(lsblk -no PKNAME "$src")
    part=$(cat "/sys/class/block/$(basename "$src")/partition")
    [ -f "$ARCH_ESP_MNT/vmlinuz-linux" ] && [ -f "$ARCH_ESP_MNT/initramfs-linux.img" ] || die "Không thấy kernel Arch trong $ARCH_ESP_MNT"

    tmp=$(mktemp -d)
    nvme_esp=$(blkid -U "$NVME_ESP_UUID") || { rmdir "$tmp"; die "Không thấy ESP NVMe ($NVME_ESP_UUID)"; }
    mount -o ro "$nvme_esp" "$tmp"
    for f in EFI/Microsoft/Boot/bootmgfw.efi EFI/ubuntu/shimx64.efi; do
        if [ -f "$tmp/$f" ]; then log_ok "Tìm thấy $f"; else umount "$tmp"; rmdir "$tmp"; die "Thiếu $f trên $nvme_esp"; fi
    done
    umount "$tmp"; rmdir "$tmp"

    pacman -S --needed --noconfirm refind
    local rshare=/usr/share/refind

    rm -rf "$stage"; mkdir -p "$stage"
    cp "$rshare/refind_x64.efi" "$stage/"
    cp -r "$rshare/icons" "$stage/icons"
    cp "$ROOT_DIR/refind/refind.conf" "$stage/refind.conf"
    cp -r "$ROOT_DIR/refind/themes" "$stage/themes"
    touch "$stage/.triboot"

    for f in refind_x64.efi refind.conf icons themes/triboot/banner.png themes/triboot/icons/arch.png themes/triboot/icons/windows.png themes/triboot/icons/ubuntu.png; do
        [ -e "$stage/$f" ] || die "Chép thiếu $f"
    done
    sync

    if [ -d "$REFIND_DIR" ]; then
        if [ -f "$REFIND_DIR/.triboot" ]; then rm -rf "$REFIND_DIR"
        elif [ ! -d "$old" ]; then mv "$REFIND_DIR" "$old"
        else rm -rf "$REFIND_DIR"; fi
    fi
    mv "$stage" "$REFIND_DIR"; sync

    if [ -z "$(refind_entry_nums)" ]; then
        efibootmgr -q --create --disk "$disk" --part "$part" --loader '\EFI\refind\refind_x64.efi' --label "$EFI_LABEL" || true
    fi
    local n order
    n=$(refind_entry_nums | head -1 || true)
    if [ -n "$n" ]; then
        order=$(efibootmgr | awk -v n="$n" '/^BootOrder:/ { k = split($2, a, ","); s = n; for (i = 1; i <= k; i++) if (a[i] != n) s = s "," a[i]; print s }')
        efibootmgr -q -o "${order:-$n}" || true
        log_ok "BootOrder: $(efibootmgr | awk '/^BootOrder:/ {print $2}') (Boot$n = $EFI_LABEL)"
    fi

    # Đảm bảo GRUB cũng có mục 09_refind cho các máy firmware luôn vào GRUB trước
    grub_hide_extra_entries refind
}

# Tối ưu tốc độ khởi động rEFInd bằng banner BMP không nén + tắt GRUB đồ họa trung gian
refind_enable_fastboot() {
    log_info "Tối ưu tốc độ khởi động (Fast-Boot: BMP không nén + ẩn GRUB trung gian)..."
    [ -f "$REFIND_CONF" ] || die "Không thấy $REFIND_CONF"
    command -v magick >/dev/null || die "Cần ImageMagick (pacman -S imagemagick)"
    [ "$(df --output=avail -m "$ARCH_ESP_MNT" | tail -1)" -ge 60 ] || die "$ARCH_ESP_MNT còn dưới 60MB, không đủ chỗ cho banner BMP"

    if [ ! -f "$BK_FASTBOOT/.done" ]; then
        rm -rf "$BK_FASTBOOT"; mkdir -p "$BK_FASTBOOT"
        cp -a /etc/default/grub "$BK_FASTBOOT/grub"
        cp -a "$REFIND_CONF" "$BK_FASTBOOT/refind.conf"
        [ -f "$GREET_BIN" ] && cp -a "$GREET_BIN" "$BK_FASTBOOT/triboot-greeting"
        touch "$BK_FASTBOOT/.done"
    fi

    grub_enable_fastboot

    to_bmp() { magick "$1" -alpha off -type TrueColor "BMP3:$2.tmp" && mv -f "$2.tmp" "$2"; }
    [ -f "$REFIND_THEME_DIR/banner.png" ] && to_bmp "$REFIND_THEME_DIR/banner.png" "$REFIND_THEME_DIR/banner.bmp"
    for f in "$REFIND_THEME_DIR"/banners/*.png; do
        [ -f "$f" ] && to_bmp "$f" "${f%.png}.bmp"
    done
    sync

    sed -i -E 's#^\s*banner\s+themes/triboot/banner\.(png|bmp)#banner themes/triboot/banner.bmp#; s#^\s*banner_scale\s+.*#banner_scale noscale#' "$REFIND_CONF"
    grep -q '^banner themes/triboot/banner.bmp' "$REFIND_CONF" || die "Không sửa được dòng banner trong $REFIND_CONF"

    if [ -f "$GREET_BIN" ]; then
        sed -i -E 's|banners/\$p\.png|banners/$p.bmp|; s|\$D/banner\.png|$D/banner.bmp|g' "$GREET_BIN"
        "$GREET_BIN" start || true
    fi
    log_ok "Đã chuyển banner rEFInd sang BMP không nén và tối ưu GRUB."
}

refind_undo_fastboot() {
    if [ -f "$BK_FASTBOOT/.done" ]; then
        cp -a "$BK_FASTBOOT/grub" /etc/default/grub
        [ -f "$BK_FASTBOOT/refind.conf" ] && cp -a "$BK_FASTBOOT/refind.conf" "$REFIND_CONF"
        [ -f "$BK_FASTBOOT/triboot-greeting" ] && cp -a "$BK_FASTBOOT/triboot-greeting" "$GREET_BIN"
        rm -f "$REFIND_THEME_DIR/banner.bmp" "$REFIND_THEME_DIR"/banners/*.bmp
        update_grub_cfg
        rm -rf "$BK_FASTBOOT"
        log_ok "Đã hoàn tác cấu hình fast-boot."
    fi
}

refind_undo() {
    refind_undo_fastboot
    for n in $(refind_entry_nums); do
        efibootmgr -q -b "$n" -B && log_ok "Đã xóa mục boot $EFI_LABEL (Boot$n)"
    done
    rm -rf "$REFIND_DIR" "$REFIND_DIR.new"
    if [ -d "$REFIND_DIR.old" ]; then
        mv "$REFIND_DIR.old" "$REFIND_DIR"
        log_ok "Đã khôi phục rEFInd có sẵn từ trước."
    fi
}
