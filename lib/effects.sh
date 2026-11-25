#!/usr/bin/env bash
# ==============================================================================
# THƯ VIỆN HIỆU ỨNG LỜI CHÀO & MÀN HÌNH PLYMOUTH (lib/effects.sh)
# Gồm:
#   - Tạo ảnh lời chào theo buổi (sáng / chiều / tối) cho rEFInd
#   - Tạo ảnh Plymouth: lời chào khi bật máy + lời tạm biệt khi tắt/khởi động lại
#   - Cài đặt systemd service đổi lời chào theo giờ và Plymouth cho Arch & Ubuntu
# ==============================================================================

# Chọn thư mục nguồn theme Plymouth để cài: bản KAFKA.SYS pixel (nếu đã sinh) hoặc bản cũ
_ply_src() {
    local os=$1 d name
    if [ "$os" = arch ]; then
        d="$ROOT_DIR/effects/plymouth-theme"
        name=$(basename "$PLYMOUTH_ARCH_DIR")
    else
        d="$ROOT_DIR/effects/plymouth-ubuntu"
        name="$PLYMOUTH_UBUNTU_NAME"
    fi
    if [ "$PLYMOUTH_STYLE" = kafka ] && [ -f "$ROOT_DIR/effects/build-kafka/$os/$name.script" ]; then
        d="$ROOT_DIR/effects/build-kafka/$os"
    fi
    echo "$d"
}

# Sinh toàn bộ ảnh lời chào rEFInd + tài nguyên Plymouth cho Arch và Ubuntu
effects_build_assets() {
    local name="${1-$USER_NAME}"
    local suffix="${name:+, $name}"
    local ed="$ROOT_DIR/effects"
    local bg="$ROOT_DIR/triboot/background.png"

    log_info "Tạo bộ ảnh lời chào & tạm biệt${name:+ cho \"$name\"}..."
    mkdir -p "$ed/banners" "$ed/plymouth-theme" "$ed/plymouth-ubuntu"

    # 1. Banner menu rEFInd theo 3 buổi
    _make_banner() {
        local file=$1 text=$2 glow=$3
        magick "$bg" \
            \( -size 1400x900 -define gradient:extent=minimum "radial-gradient:${glow}-none" -channel A -evaluate multiply 0.30 +channel \) \
            -geometry +260+-420 -compose screen -composite -compose over \
            -gravity north -font "$FONT_BOLD" -pointsize 50 -fill '#f2f4f8' -annotate +0+232 "${text}${suffix}" \
            -gravity north -font "$FONT_REG"  -pointsize 22 -fill '#8a93a6' -annotate +0+312 'Chọn hệ điều hành' \
            -gravity south -font "$FONT_REG"  -pointsize 20 -fill '#4d5566' -annotate +0+56 '←  →   chọn            Enter   khởi động' \
            -strip "PNG24:$ed/banners/${file}.png"
    }
    _make_banner sang  'Chào buổi sáng'  "$COLOR_MORNING"
    _make_banner chieu 'Chào buổi chiều' "$COLOR_AFTERNOON"
    _make_banner toi   'Chào buổi tối'   "$COLOR_EVENING"

    # 2. Tài nguyên Plymouth cho Arch Linux
    local pa="$ed/plymouth-theme"
    cp "$bg" "$pa/background.png"
    rsvg-convert -w 168 -h 168 "$PAPIRUS_LOGO_DIR/distributor-logo-archlinux.svg" -o "$pa/logo.png"
    magick "$pa/logo.png" -alpha extract -blur 0x18 -level 0,60% \
        \( +clone -fill "$COLOR_ARCH" -colorize 100 \) +swap -alpha off -compose copy_opacity -composite \
        -background none -gravity center -extent 260x260 -strip "PNG32:$pa/glow.png"
    magick -background none -font "$FONT_BOLD" -pointsize 44 -fill '#f2f4f8' label:"Chào mừng trở lại${suffix}" -strip "PNG32:$pa/greet.png"
    magick -background none -font "$FONT_BOLD" -pointsize 44 -fill '#f2f4f8' label:"Hẹn gặp lại${suffix}"       -strip "PNG32:$pa/bye.png"
    magick -background none -font "$FONT_REG"  -pointsize 22 -fill '#8a93a6' label:'Arch Linux đang khởi động'     -strip "PNG32:$pa/sub.png"
    magick -background none -font "$FONT_REG"  -pointsize 22 -fill '#8a93a6' label:'Arch Linux đang tắt máy'       -strip "PNG32:$pa/sub_shutdown.png"
    magick -background none -font "$FONT_REG"  -pointsize 22 -fill '#8a93a6' label:'Arch Linux đang khởi động lại' -strip "PNG32:$pa/sub_reboot.png"
    magick -size 14x14 xc:none -fill '#e6e9f0' -draw 'circle 7,7 7,1' -strip "PNG32:$pa/dot.png"

    # 3. Tài nguyên Plymouth cho Ubuntu
    local pu="$ed/plymouth-ubuntu"
    cp "$bg" "$pu/background.png"
    cp "$pa/dot.png" "$pu/dot.png"
    cp "$pa/greet.png" "$pu/greet.png"
    cp "$pa/bye.png" "$pu/bye.png"
    sed -e 's/khởi động Arch/khởi động Ubuntu/' "$pa/triboot.script" > "$pu/triboot-ubuntu.script"
    rsvg-convert -w 168 -h 168 "$PAPIRUS_LOGO_DIR/distributor-logo-ubuntu.svg" -o "$pu/logo.png"
    magick "$pu/logo.png" -alpha extract -blur 0x18 -level 0,60% \
        \( +clone -fill "$COLOR_UBUNTU" -colorize 100 \) +swap -alpha off -compose copy_opacity -composite \
        -background none -gravity center -extent 260x260 -strip "PNG32:$pu/glow.png"
    magick -background none -font "$FONT_REG"  -pointsize 22 -fill '#8a93a6' label:'Ubuntu đang khởi động'     -strip "PNG32:$pu/sub.png"
    magick -background none -font "$FONT_REG"  -pointsize 22 -fill '#8a93a6' label:'Ubuntu đang tắt máy'       -strip "PNG32:$pu/sub_shutdown.png"
    magick -background none -font "$FONT_REG"  -pointsize 22 -fill '#8a93a6' label:'Ubuntu đang khởi động lại' -strip "PNG32:$pu/sub_reboot.png"

    cat > "$pu/triboot-ubuntu.plymouth" <<'PT'
[Plymouth Theme]
Name=Triboot Ubuntu
Description=Màn hình chào khi khởi động Ubuntu (theme Triboot)
ModuleName=script

[script]
ImageDir=/usr/share/plymouth/themes/triboot-ubuntu
ScriptFile=/usr/share/plymouth/themes/triboot-ubuntu/triboot-ubuntu.script
PT

    # 4. Bản Plymouth KAFKA.SYS pixel (ảnh nền có bản quyền → chỉ sinh trong effects/build-kafka/, đã gitignore)
    if [ "$PLYMOUTH_STYLE" = kafka ]; then
        local pbg="" candidate
        for candidate in \
            "$KAFKA_DESKTOP_DIR/wallpapers/kafka_landscape_3.jpg" \
            "$KAFKA_DESKTOP_DIR/greetd/kafka-greeter/bg-pixel.png"; do
            if [ -f "$candidate" ]; then
                pbg="$candidate"
                break
            fi
        done
        [ -n "$pbg" ] || log_warn "Không thấy ảnh nền KAFKA.SYS, dùng nền tự vẽ cho Plymouth."
        log_info "Tạo màn hình chào Plymouth KAFKA.SYS..."
        python3 "$ROOT_DIR/kafka-src/make-kafka-plymouth.py" "$ed/build-kafka/arch" \
            --os arch --theme triboot --dir "$PLYMOUTH_ARCH_DIR" --name "$name" ${pbg:+--bg "$pbg"}
        python3 "$ROOT_DIR/kafka-src/make-kafka-plymouth.py" "$ed/build-kafka/ubuntu" \
            --os ubuntu --theme "$PLYMOUTH_UBUNTU_NAME" --dir "$PLYMOUTH_UBUNTU_DIR" --name "$name" ${pbg:+--bg "$pbg"}
    fi
    log_ok "Đã tạo xong bộ ảnh lời chào & tạm biệt."
}

effects_rebuild_initramfs() {
    if ! mkinitcpio -P; then
        log_warn "mkinitcpio lỗi — khôi phục $MKINITCPIO_CONF cũ và tạo lại initramfs để máy vẫn boot được"
        cp -a "$BK_EFFECTS/mkinitcpio.conf" "$MKINITCPIO_CONF"
        mkinitcpio -P || die "Tạo lại initramfs vẫn lỗi — ĐỪNG khởi động lại máy!"
        exit 1
    fi
}

# Cài đặt dịch vụ lời chào theo buổi + Plymouth cho Arch Linux
effects_install_arch() {
    local ed="$ROOT_DIR/effects"
    log_info "Cài đặt hiệu ứng lời chào theo buổi & màn hình Plymouth cho Arch..."

    for f in "$ed"/banners/{sang,chieu,toi}.png; do
        [ -f "$f" ] || die "Thiếu $f"
    done
    local pa
    pa=$(_ply_src arch)
    for f in "$pa"/{triboot.plymouth,triboot.script,background.png}; do
        [ -f "$f" ] || die "Thiếu $f"
    done
    [ "$(df --output=avail -m "$ARCH_ESP_MNT" | tail -1)" -ge 200 ] || die "$ARCH_ESP_MNT còn dưới 200MB, không đủ để tạo lại initramfs"

    if [ ! -f "$BK_EFFECTS/.done" ]; then
        rm -rf "$BK_EFFECTS"; mkdir -p "$BK_EFFECTS"
        cp -a "$MKINITCPIO_CONF" "$BK_EFFECTS/mkinitcpio.conf"
        [ -f "$REFIND_THEME_DIR/banner.png" ] && cp -a "$REFIND_THEME_DIR/banner.png" "$BK_EFFECTS/banner.png"
        touch "$BK_EFFECTS/.done"
    fi

    # 1. Nếu có rEFInd, cài dịch vụ đổi banner theo buổi
    if [ -d "$REFIND_THEME_DIR" ]; then
        mkdir -p "$REFIND_THEME_DIR/banners"
        cp "$ed"/banners/{sang,chieu,toi}.png "$REFIND_THEME_DIR/banners/"
        local ext=png
        if [ "${FAST_BOOT:-1}" -eq 1 ] || [ -f "$REFIND_THEME_DIR/banner.bmp" ]; then
            if command -v magick >/dev/null; then
                ext=bmp
                for f in "$REFIND_THEME_DIR"/banners/*.png; do
                    magick "$f" -alpha off -type TrueColor "BMP3:${f%.png}.bmp.tmp" && mv -f "${f%.png}.bmp.tmp" "${f%.png}.bmp"
                done
            fi
        fi
        cat > "$GREET_BIN" <<EOF
#!/bin/sh
# Chọn ảnh lời chào cho lần mở máy tới. Gọi lúc bật máy (start) và lúc tắt máy (stop).
D=${REFIND_THEME_DIR}
h=\$(date +%H); h=\${h#0}
p=
if [ "\$1" = stop ] && { [ "\$h" -ge 22 ] || [ "\$h" -lt 5 ]; }; then p=sang; fi
if [ -z "\$p" ]; then
    if   [ "\$h" -ge 5 ]  && [ "\$h" -lt 11 ]; then p=sang
    elif [ "\$h" -ge 11 ] && [ "\$h" -lt 18 ]; then p=chieu
    else p=toi; fi
fi
src=\$D/banners/\$p.${ext}
[ -f "\$src" ] || exit 0
cmp -s "\$src" "\$D/banner.${ext}" && exit 0
cp "\$src" "\$D/banner.${ext}.tmp" && mv -f "\$D/banner.${ext}.tmp" "\$D/banner.${ext}"
EOF
        chmod 755 "$GREET_BIN"
        cat > "$GREET_SERVICE" <<EOF
[Unit]
Description=Triboot: đổi lời chào trên menu rEFInd theo buổi
RequiresMountsFor=${ARCH_ESP_MNT}

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=${GREET_BIN} start
ExecStop=${GREET_BIN} stop

[Install]
WantedBy=multi-user.target
EOF
        systemctl daemon-reload
        systemctl enable --now triboot-greeting.service
        log_ok "Đã kích hoạt dịch vụ triboot-greeting.service (định dạng .$ext)."
    fi

    # 2. Cài đặt Plymouth theme cho Arch
    pacman -S --needed --noconfirm plymouth
    [ -f "$BK_EFFECTS/plymouth-theme" ] || plymouth-set-default-theme 2>/dev/null > "$BK_EFFECTS/plymouth-theme" || true
    rm -rf "$PLYMOUTH_ARCH_DIR"; mkdir -p "$PLYMOUTH_ARCH_DIR"
    cp "$pa"/* "$PLYMOUTH_ARCH_DIR/"

    if ! grep -qE '^HOOKS=.*\bplymouth\b' "$MKINITCPIO_CONF"; then
        sed -i -E '/^HOOKS=/ s/\bsystemd\b/systemd plymouth/' "$MKINITCPIO_CONF"
    fi
    plymouth-set-default-theme triboot
    effects_rebuild_initramfs

    # 3. Thêm tham số "splash" vào kernel Arch
    refind_set_splash add
    if [ -f /etc/default/grub ] && ! grep -qE '^GRUB_CMDLINE_LINUX_DEFAULT=.*\bsplash\b' /etc/default/grub; then
        [ -f "$BK_EFFECTS/grub" ] || cp -a /etc/default/grub "$BK_EFFECTS/grub"
        sed -i -E 's/^(GRUB_CMDLINE_LINUX_DEFAULT="[^"]*)"/\1 splash"/' /etc/default/grub
        update_grub_cfg >/dev/null
    fi
    log_ok "Đã cập nhật Plymouth cho Arch Linux (hỗ trợ cả lời chào bật máy & lời tạm biệt tắt máy)."
}

# Đồng bộ trực tiếp file Plymouth sang phân vùng Ubuntu từ Arch (nếu Ubuntu đã cài theme).
# Màn hình BẬT máy nằm trong initramfs của Ubuntu, Arch không tự dựng lại được → đặt cờ để
# triboot-plymouth-refresh.service (cài bởi --ubuntu) chạy update-initramfs ở lần bật Ubuntu kế tiếp.
effects_sync_ubuntu_from_arch() {
    local ub tmp pu
    ub=$(blkid -U "$UBUNTU_ROOT_UUID" 2>/dev/null || true)
    [ -n "$ub" ] || return 0
    tmp=$(mktemp -d)
    if mount "$ub" "$tmp" 2>/dev/null; then
        if [ -d "$tmp$PLYMOUTH_UBUNTU_DIR" ]; then
            log_info "Đồng bộ màn hình chào/tạm biệt sang phân vùng Ubuntu..."
            pu=$(_ply_src ubuntu)
            rm -f "$tmp$PLYMOUTH_UBUNTU_DIR"/*
            cp "$pu"/* "$tmp$PLYMOUTH_UBUNTU_DIR/"
            mkdir -p "$tmp$UBUNTU_FLAG_DIR"
            touch "$tmp$UBUNTU_FLAG_DIR/plymouth-changed"
            sync
            log_ok "Đã đồng bộ theme Plymouth sang Ubuntu."
            if [ -f "$tmp$UBUNTU_REFRESH_SERVICE" ]; then
                log_info "Lần bật Ubuntu kế tiếp sẽ tự update-initramfs; màn hình chào mới hiện từ lần bật sau đó (màn hình tắt máy đổi ngay)."
            else
                log_warn "Ubuntu chưa có triboot-plymouth-refresh.service: vào Ubuntu chạy 'sudo ./install.sh --ubuntu' một lần để màn hình chào mới hiện."
            fi
        fi
        umount "$tmp" || true
    fi
    rmdir "$tmp" 2>/dev/null || true
}

# Tìm ảnh nền Kafka cho Plymouth (bản quyền, không có trong repo). In ra đường dẫn một bản sao
# đọc được bởi user thường (file tạm, nơi gọi tự xoá), hoặc chuỗi rỗng.
# Thứ tự: repo dotfiles trên máy này → (đang ở Ubuntu) repo dotfiles trên phân vùng Arch, gắn chỉ đọc.
_kafka_bg_rel=("wallpapers/kafka_landscape_3.jpg" "greetd/kafka-greeter/bg-pixel.png")
effects_find_kafka_bg() {
    local rel found="" dev mnt d out
    for rel in "${_kafka_bg_rel[@]}"; do
        [ -f "$KAFKA_DESKTOP_DIR/$rel" ] && { found="$KAFKA_DESKTOP_DIR/$rel"; break; }
    done
    if [ -z "$found" ] && is_ubuntu && dev=$(blkid -U "$ARCH_ROOT_UUID" 2>/dev/null); then
        mnt=$(mktemp -d)
        if mount -o ro "$dev" "$mnt" 2>/dev/null; then
            # Arch trên ext4 (home trong /) hoặc btrfs (subvolume @, @home)
            for d in "$mnt"/home/*/Desktop/repo_4Fun/custom_desktop "$mnt"/@home/*/Desktop/repo_4Fun/custom_desktop \
                "$mnt"/@/home/*/Desktop/repo_4Fun/custom_desktop; do
                for rel in "${_kafka_bg_rel[@]}"; do
                    if [ -f "$d/$rel" ]; then
                        out=$(mktemp --suffix=".${rel##*.}")
                        cp "$d/$rel" "$out"
                        chmod 644 "$out"
                        found="$out"
                        break 2
                    fi
                done
            done
            umount "$mnt" || true
        fi
        rmdir "$mnt" 2>/dev/null || true
        [ -n "$found" ] && log_info "Lấy ảnh nền Kafka từ phân vùng Arch." >&2
    elif [ -n "$found" ]; then
        out=$(mktemp --suffix=".${found##*.}")
        cp "$found" "$out"
        chmod 644 "$out"
        found="$out"
    fi
    echo "$found"
}

# Sinh theme Plymouth KAFKA.SYS bản Ubuntu ngay trong Ubuntu (effects/build-kafka/ubuntu)
effects_build_ubuntu_kafka() {
    local bg
    bg=$(effects_find_kafka_bg)
    [ -n "$bg" ] || log_warn "Không thấy ảnh nền Kafka (repo dotfiles), dùng nền tự vẽ."
    log_info "Tạo màn hình chào Plymouth KAFKA.SYS cho Ubuntu..."
    run_as_user python3 "$ROOT_DIR/kafka-src/make-kafka-plymouth.py" "$ROOT_DIR/effects/build-kafka/ubuntu" \
        --os ubuntu --theme "$PLYMOUTH_UBUNTU_NAME" --dir "$PLYMOUTH_UBUNTU_DIR" --name "$USER_NAME" ${bg:+--bg "$bg"}
    local rc=$?
    [ -n "$bg" ] && rm -f "$bg"
    return $rc
}

# Ẩn menu GRUB riêng của Ubuntu: chọn Ubuntu ở menu chính (rEFInd / KAFKA / Windows Boot Manager)
# là vào thẳng. Ubuntu 20.04 hiện lại menu trong 2 trường hợp, phải tắt cả hai:
#   - recordfail (lần trước tắt máy không sạch) → GRUB_RECORDFAIL_TIMEOUT=0
#   - 30_os-prober thấy HĐH khác thì ép timeout 10s → GRUB_DISABLE_OS_PROBER=true
#     (menu chính đã liệt kê Windows/Arch). Vẫn giữ Shift/Esc lúc bật để mở menu khi cần cứu hộ.
_ubuntu_hide_grub_menu() {
    set_grub_opt GRUB_TIMEOUT_STYLE hidden
    set_grub_opt GRUB_TIMEOUT 0
    set_grub_opt GRUB_RECORDFAIL_TIMEOUT 0
    set_grub_opt GRUB_DISABLE_OS_PROBER true
    log_ok "Ẩn menu GRUB của Ubuntu (giữ Shift/Esc lúc bật để mở khi cần)."
}

_ubuntu_install_refresh_service() {
    mkdir -p "$UBUNTU_FLAG_DIR"
    cat >"$UBUNTU_REFRESH_SERVICE" <<UNIT
[Unit]
Description=Triboot: dựng lại initramfs khi theme Plymouth được đồng bộ từ Arch
ConditionPathExists=$UBUNTU_FLAG_DIR/plymouth-changed
After=local-fs.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'update-initramfs -u && rm -f $UBUNTU_FLAG_DIR/plymouth-changed'

[Install]
WantedBy=multi-user.target
UNIT
    systemctl daemon-reload
    systemctl enable triboot-plymouth-refresh.service >/dev/null 2>&1 || true
}

# Cài đặt Plymouth cho Ubuntu (chạy trực tiếp từ trong Ubuntu; thử cho 20.04 trở lên)
effects_install_ubuntu() {
    is_ubuntu || die "Chế độ --ubuntu chỉ chạy khi đang ở trong Ubuntu."
    local ver pu link="/usr/share/plymouth/themes/default.plymouth"
    ver=$(. /etc/os-release && echo "${VERSION_ID:-0}")
    log_info "Cài màn hình chào/tạm biệt cho Ubuntu $ver"
    dpkg --compare-versions "$ver" lt 20.04 && log_warn "Mới thử cho Ubuntu 20.04 trở lên."

    if [ -s /etc/crypttab ] && grep -qvE '^\s*(#|$)' /etc/crypttab; then
        die "Ubuntu đang dùng ổ mã hóa (/etc/crypttab), theme này không có ô nhập mật khẩu."
    fi

    local pkgs=(plymouth plymouth-themes)
    [ "$PLYMOUTH_STYLE" = kafka ] && pkgs+=(python3-cairo)
    apt-get install -y "${pkgs[@]}"
    ls /usr/lib/*/plymouth/script.so >/dev/null 2>&1 || die "Không thấy module script.so của Plymouth"

    # Bản KAFKA.SYS: sinh ngay trong Ubuntu (effects/build-kafka/ không nằm trong git). Lỗi thì dùng bản phẳng.
    if [ "$PLYMOUTH_STYLE" = kafka ]; then
        effects_build_ubuntu_kafka || log_warn "Không sinh được bản KAFKA.SYS, dùng bản phẳng."
    fi
    pu=$(_ply_src ubuntu)
    for f in "$PLYMOUTH_UBUNTU_NAME.plymouth" "$PLYMOUTH_UBUNTU_NAME.script" background.png; do
        [ -f "$pu/$f" ] || die "Thiếu $pu/$f"
    done

    mkdir -p "$BK_UBUNTU"
    [ -f "$BK_UBUNTU/grub" ] || cp -a /etc/default/grub "$BK_UBUNTU/grub"

    rm -rf "$PLYMOUTH_UBUNTU_DIR"
    mkdir -p "$PLYMOUTH_UBUNTU_DIR"
    cp "$pu"/* "$PLYMOUTH_UBUNTU_DIR/"
    update-alternatives --install "$link" default.plymouth "$PLYMOUTH_UBUNTU_DIR/$PLYMOUTH_UBUNTU_NAME.plymouth" 150
    update-alternatives --set default.plymouth "$PLYMOUTH_UBUNTU_DIR/$PLYMOUTH_UBUNTU_NAME.plymouth"

    # Plymouth hiện sớm bằng framebuffer (máy không có KMS sớm thì vẫn thấy màn hình chào)
    if [ ! -f /etc/initramfs-tools/conf.d/splash ]; then
        echo FRAMEBUFFER=y >/etc/initramfs-tools/conf.d/splash
        touch "$BK_UBUNTU/created-splash-conf"
    fi

    # "quiet splash" là điều kiện để Plymouth hiện cả lúc bật lẫn lúc tắt máy
    local opt
    for opt in quiet splash; do
        if ! grep -qE "^GRUB_CMDLINE_LINUX_DEFAULT=.*\\b$opt\\b" /etc/default/grub; then
            sed -i -E "s/^(GRUB_CMDLINE_LINUX_DEFAULT=\"[^\"]*)\"/\\1 $opt\"/" /etc/default/grub
        fi
    done
    [ "$UBUNTU_HIDE_GRUB" = 1 ] && _ubuntu_hide_grub_menu
    update-grub

    _ubuntu_install_refresh_service
    update-initramfs -u
    log_ok "Đã cài màn hình chào/tạm biệt Plymouth cho Ubuntu (thấy từ lần khởi động tới)."
}

effects_undo_ubuntu() {
    is_ubuntu || die "Chế độ --ubuntu --undo chỉ chạy trong Ubuntu."
    update-alternatives --remove default.plymouth "$PLYMOUTH_UBUNTU_DIR/$PLYMOUTH_UBUNTU_NAME.plymouth" 2>/dev/null || true
    update-alternatives --auto default.plymouth || true
    rm -rf "$PLYMOUTH_UBUNTU_DIR"
    systemctl disable triboot-plymouth-refresh.service 2>/dev/null || true
    rm -f "$UBUNTU_REFRESH_SERVICE"
    rm -rf "$UBUNTU_FLAG_DIR"
    systemctl daemon-reload
    if [ -f "$BK_UBUNTU/created-splash-conf" ]; then
        rm -f /etc/initramfs-tools/conf.d/splash "$BK_UBUNTU/created-splash-conf"
    fi
    if [ -f "$BK_UBUNTU/grub" ]; then
        cp -a "$BK_UBUNTU/grub" /etc/default/grub   # trả lại cả menu GRUB, os-prober, splash như cũ
        update-grub
    fi
    update-initramfs -u
    log_ok "Đã gỡ màn hình Plymouth của Ubuntu và trả lại menu GRUB như cũ."
}

effects_undo_arch() {
    if [ -f "$BK_EFFECTS/.done" ]; then
        systemctl disable --now triboot-greeting.service 2>/dev/null || true
        rm -f "$GREET_SERVICE" "$GREET_BIN"
        systemctl daemon-reload
        [ -f "$BK_EFFECTS/banner.png" ] && [ -d "$REFIND_THEME_DIR" ] && cp -a "$BK_EFFECTS/banner.png" "$REFIND_THEME_DIR/banner.png"
        rm -rf "$REFIND_THEME_DIR/banners"
        refind_set_splash remove
        if [ -f "$BK_EFFECTS/grub" ]; then
            cp -a "$BK_EFFECTS/grub" /etc/default/grub
            update_grub_cfg >/dev/null
        fi
        cp -a "$BK_EFFECTS/mkinitcpio.conf" "$MKINITCPIO_CONF"
        if [ -s "$BK_EFFECTS/plymouth-theme" ]; then
            plymouth-set-default-theme "$(cat "$BK_EFFECTS/plymouth-theme")" || true
        fi
        rm -rf "$PLYMOUTH_ARCH_DIR"
        mkinitcpio -P
        log_ok "Đã gỡ hiệu ứng lời chào & Plymouth trên Arch."
    fi
}
