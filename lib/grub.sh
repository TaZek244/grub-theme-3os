#!/usr/bin/env bash
# ==============================================================================
# THƯ VIỆN QUẢN LÝ GRUB (lib/grub.sh)
# Gồm: cài đặt theme GRUB, tạo các mục boot 3 OS, ẩn mục thừa, tối ưu fast-boot
# ==============================================================================

# Sinh file /etc/grub.d/11_triboot từ cấu hình UUID trong lib/config.sh
grub_write_11_triboot() {
    cat > /etc/grub.d/11_triboot <<EOF
#!/bin/sh
exec tail -n +3 \$0
# Mục boot cho Arch Linux, Windows 11 và Ubuntu (tự sinh từ lib/config.sh)

menuentry 'Arch Linux' --class arch --class gnu-linux --class os {
    load_video
    set gfxpayload=keep
    insmod gzio
    insmod part_gpt
    insmod fat
    search --no-floppy --fs-uuid --set=root ${ARCH_ESP_UUID}
    linux  /vmlinuz-linux root=UUID=${ARCH_ROOT_UUID} rw loglevel=3 quiet splash
    initrd /initramfs-linux.img
}

menuentry 'Windows 11' --class windows --class os {
    insmod part_gpt
    insmod fat
    insmod chain
    search --no-floppy --fs-uuid --set=root ${NVME_ESP_UUID}
    chainloader /EFI/Microsoft/Boot/bootmgfw.efi
}

menuentry 'Ubuntu' --class ubuntu --class gnu-linux --class os {
    insmod part_gpt
    insmod ext2
    search --no-floppy --fs-uuid --set=root ${UBUNTU_ROOT_UUID}
    if [ -f /boot/vmlinuz -a -f /boot/initrd.img ]; then
        linux /boot/vmlinuz root=UUID=${UBUNTU_ROOT_UUID} ro quiet splash
        initrd /boot/initrd.img
    else
        insmod fat
        insmod chain
        search --no-floppy --fs-uuid --set=root ${NVME_ESP_UUID}
        chainloader /EFI/ubuntu/shimx64.efi
    fi
}
EOF
    chmod 755 /etc/grub.d/11_triboot
}

# Sinh file /etc/grub.d/40_custom (Khởi động lại / Tắt máy)
grub_write_40_custom() {
    cat > /etc/grub.d/40_custom <<'EOF'
#!/bin/sh
exec tail -n +3 $0
# Mục nguồn của theme Triboot

menuentry 'Khởi động lại' --class restart {
    insmod reboot
    reboot
}

menuentry 'Tắt máy' --class shutdown {
    insmod halt
    halt
}
EOF
    chmod 755 /etc/grub.d/40_custom
}

# Sinh mục đầu tiên (09_refind hoặc 09_triboot) để GRUB chainload sang menu ngang
grub_set_chainloader() {
    local target=${1:-refind}
    rm -f /etc/grub.d/09_refind /etc/grub.d/09_triboot
    if [ "$target" = "uefi" ]; then
        cat > /etc/grub.d/09_triboot <<EOF
#!/bin/sh
exec tail -n +3 \$0
# Mục đầu tiên: menu ngang Triboot (ứng dụng UEFI tự viết).
# Lỗi thì GRUB tự rơi xuống mục 1 (Arch Linux).
set fallback=1

menuentry 'Triboot' --class triboot {
    insmod part_gpt
    insmod fat
    insmod chain
    search --no-floppy --fs-uuid --set=root ${ARCH_ESP_UUID}
    chainloader /EFI/triboot/triboot.efi
}
EOF
        chmod 755 /etc/grub.d/09_triboot
    elif [ "$target" = "refind" ]; then
        cat > /etc/grub.d/09_refind <<EOF
#!/bin/sh
exec tail -n +3 \$0
# Mục đầu tiên: mở menu ngang rEFInd. Lỗi thì GRUB tự rơi xuống mục 1 (Arch Linux).
set fallback=1

menuentry 'Triboot' --class triboot {
    insmod part_gpt
    insmod fat
    insmod chain
    search --no-floppy --fs-uuid --set=root ${ARCH_ESP_UUID}
    chainloader /EFI/refind/refind_x64.efi
}
EOF
        chmod 755 /etc/grub.d/09_refind
    fi
}

# Sao lưu cấu hình GRUB gốc (chỉ lần đầu)
grub_backup_init() {
    if [ ! -f "$BK_GRUB/.done" ]; then
        rm -rf "$BK_GRUB"; mkdir -p "$BK_GRUB"
        [ -f /etc/grub.d/11_triboot ] && cp -a /etc/grub.d/11_triboot "$BK_GRUB/11_triboot"
        [ -d "$GRUB_THEME_DIR" ] && cp -a "$GRUB_THEME_DIR" "$BK_GRUB/theme"
        cp -a /etc/default/grub     "$BK_GRUB/grub"
        cp -a /etc/grub.d/40_custom "$BK_GRUB/40_custom"
        cp -a /boot/grub/grub.cfg   "$BK_GRUB/grub.cfg"
        touch "$BK_GRUB/.done"
    fi
}

# Cài đặt theme GRUB dọc truyền thống + các mục 3 OS
grub_install_base() {
    log_info "Cài đặt theme GRUB & các mục khởi động 3 hệ điều hành..."
    grub_backup_init

    rm -rf "$GRUB_THEME_DIR"
    mkdir -p "$GRUB_THEME_DIR"
    cp -r "$ROOT_DIR/triboot/." "$GRUB_THEME_DIR/"

    grub_write_11_triboot
    grub_write_40_custom

    set_grub_opt GRUB_THEME         "\"$GRUB_THEME_DIR/theme.txt\""
    set_grub_opt GRUB_GFXMODE       "${RESOLUTION},auto"
    set_grub_opt GRUB_TIMEOUT       "$MENU_TIMEOUT"
    set_grub_opt GRUB_TIMEOUT_STYLE "menu"
    sed -i -E 's|^\s*GRUB_TERMINAL_OUTPUT=.*|#&|' /etc/default/grub

    update_grub_cfg
    log_ok "Đã cài đặt GRUB theme và mục boot."
}

# Ẩn các mục thừa trong GRUB (10_linux, 30_uefi-firmware, 31_efi_bootnext) và tạo pacman hook
grub_hide_extra_entries() {
    local target=${1:-uefi}
    log_info "Ẩn các mục thừa trong GRUB và cài đặt chuyển tiếp ($target)..."
    [ -f "$ARCH_ESP_MNT/vmlinuz-linux" ] && [ -f "$ARCH_ESP_MNT/initramfs-linux.img" ] || die "Không thấy kernel Arch trong $ARCH_ESP_MNT"

    if [ ! -f "$BK_FIXMENU/.done" ]; then
        rm -rf "$BK_FIXMENU"; mkdir -p "$BK_FIXMENU"
        cp -a /etc/default/grub "$BK_FIXMENU/grub"
        [ -f /etc/grub.d/11_triboot ] && cp -a /etc/grub.d/11_triboot "$BK_FIXMENU/11_triboot"
        touch "$BK_FIXMENU/.done"
    fi

    grub_set_chainloader "$target"
    grub_write_11_triboot
    for f in $GRUB_HIDE_SCRIPTS; do
        [ -f "/etc/grub.d/$f" ] && chmod -x "/etc/grub.d/$f"
    done

    mkdir -p "$(dirname "$GRUB_HOOK_FILE")"
    cat > "$GRUB_HOOK_FILE" <<EOF
[Trigger]
Type = Package
Operation = Install
Operation = Upgrade
Target = grub

[Action]
Description = Triboot: ẩn mục thừa trong GRUB
When = PostTransaction
Exec = /bin/sh -c 'cd /etc/grub.d && chmod -x $GRUB_HIDE_SCRIPTS && grub-mkconfig -o /boot/grub/grub.cfg'
EOF

    set_grub_opt GRUB_DEFAULT       "0"
    set_grub_opt GRUB_TIMEOUT       "1"
    set_grub_opt GRUB_TIMEOUT_STYLE "hidden"

    update_grub_cfg
    log_ok "Đã ẩn mục thừa GRUB và trỏ mặc định vào menu $target."
}

# Tối ưu GRUB trung gian: tắt theme/font/gfxterm, không chờ (GRUB_TIMEOUT=0)
grub_enable_fastboot() {
    log_info "Tối ưu GRUB trung gian (chế độ chữ, không chờ, không nạp theme)..."
    set_grub_opt GRUB_TIMEOUT         "0"
    set_grub_opt GRUB_TIMEOUT_STYLE   "hidden"
    set_grub_opt GRUB_TERMINAL_OUTPUT "console"
    sed -i -E 's|^\s*(GRUB_THEME=.*)|#\1|; s|^\s*(GRUB_GFXMODE=.*)|#\1|' /etc/default/grub

    update_grub_cfg
    if grep -qE '^\s*(set theme=|loadfont|terminal_output gfxterm)' /boot/grub/grub.cfg; then
        log_warn "grub.cfg vẫn còn theme/gfxterm, hãy kiểm tra lại /etc/default/grub"
    else
        log_ok "GRUB trung gian đã chuyển sang chế độ khởi động tức thì."
    fi
}

# Hoàn tác cấu hình GRUB
grub_undo_fixmenu() {
    if [ -f "$BK_FIXMENU/.done" ]; then
        cp -a "$BK_FIXMENU/grub" /etc/default/grub
        [ -f "$BK_FIXMENU/11_triboot" ] && cp -a "$BK_FIXMENU/11_triboot" /etc/grub.d/11_triboot
        rm -f /etc/grub.d/09_refind /etc/grub.d/09_triboot "$GRUB_HOOK_FILE"
        for f in $GRUB_HIDE_SCRIPTS; do [ -f "/etc/grub.d/$f" ] && chmod +x "/etc/grub.d/$f"; done
        update_grub_cfg
        log_ok "Đã khôi phục menu GRUB từ $BK_FIXMENU."
    fi
}

grub_undo_base() {
    if [ -f "$BK_GRUB/.done" ]; then
        cp -a "$BK_GRUB/grub"      /etc/default/grub
        cp -a "$BK_GRUB/40_custom" /etc/grub.d/40_custom
        if [ -f "$BK_GRUB/11_triboot" ]; then cp -a "$BK_GRUB/11_triboot" /etc/grub.d/11_triboot; else rm -f /etc/grub.d/11_triboot; fi
        rm -rf "$GRUB_THEME_DIR"
        [ -d "$BK_GRUB/theme" ] && cp -a "$BK_GRUB/theme" "$GRUB_THEME_DIR"
        cp -a "$BK_GRUB/grub.cfg"  /boot/grub/grub.cfg
        log_ok "Đã khôi phục cấu hình GRUB gốc từ $BK_GRUB."
    fi
}
