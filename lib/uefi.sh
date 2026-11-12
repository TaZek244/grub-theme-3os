#!/usr/bin/env bash
# ==============================================================================
# THƯ VIỆN MENU NGANG UEFI TỰ VIẾT (lib/uefi.sh)
# Gồm: tạo bộ ảnh định dạng .tbi (TBI1), biên dịch triboot.efi và cài vào ESP
# ==============================================================================

uefi_build_assets() {
    local name="${1-$USER_NAME}"
    local suffix="${name:+, $name}"
    local udir="$ROOT_DIR/uefi-menu"
    local build_dir="$udir/build"
    local png_dir="$build_dir/png"
    local tbi_dir="$build_dir/assets"
    local bg="$ROOT_DIR/triboot/background.png"

    log_info "Tạo bộ ảnh .tbi cho ứng dụng UEFI menu${name:+ ($name)}..."
    rm -rf -- "$build_dir"
    mkdir -p -- "$png_dir" "$tbi_dir"

    _write_tbi() {
        local aname=$1 src=$2 w h expected actual
        read -r w h < <(magick identify -format '%w %h\n' "$src")
        printf 'TBI1' > "$tbi_dir/$aname.tbi"
        printf '%b' "\\$(printf '%03o' $((w & 255)))\\$(printf '%03o' $(((w >> 8) & 255)))\\$(printf '%03o' $(((w >> 16) & 255)))\\$(printf '%03o' $(((w >> 24) & 255)))" >> "$tbi_dir/$aname.tbi"
        printf '%b' "\\$(printf '%03o' $((h & 255)))\\$(printf '%03o' $(((h >> 8) & 255)))\\$(printf '%03o' $(((h >> 16) & 255)))\\$(printf '%03o' $(((h >> 24) & 255)))" >> "$tbi_dir/$aname.tbi"
        printf '\0\0\0\0' >> "$tbi_dir/$aname.tbi"
        magick "$src" -alpha on -depth 8 BGRA:- >> "$tbi_dir/$aname.tbi"
        expected=$((16 + w * h * 4))
        actual=$(stat -c '%s' "$tbi_dir/$aname.tbi")
        [ "$actual" = "$expected" ] || die "Lỗi tạo $aname.tbi: cần $expected bytes, nhận được $actual"
    }

    _finish_asset() {
        cp -- "$2" "$png_dir/$1.png"
        _write_tbi "$1" "$png_dir/$1.png"
    }

    _text_asset() {
        local aname=$1 text=$2 size=$3 color=$4 glow_color=${5:-} glow_alpha=${6:-0.35}
        local base glow out font="$FONT_REG"
        [[ "$aname" == greet_* ]] && font="$FONT_BOLD"
        base=$(mktemp --tmpdir="$udir" .asset-base.XXXXXX.png)
        out=$(mktemp --tmpdir="$udir" .asset-out.XXXXXX.png)
        magick -size 1400x180 xc:none -font "$font" -pointsize "$size" -fill "$color" \
            -gravity center -annotate +0+0 "$text" "$base"
        if [ -n "$glow_color" ]; then
            glow=$(mktemp --tmpdir="$udir" .asset-glow.XXXXXX.png)
            magick -size 1400x180 xc:none -font "$font" -pointsize "$size" -fill "$glow_color" \
                -gravity center -annotate +0+0 "$text" -channel A -evaluate multiply "$glow_alpha" +channel \
                -blur 0x12 "$glow"
            magick "$glow" "$base" -compose over -composite -trim -bordercolor none -border 18 "$out"
            rm -f -- "$glow"
        else
            magick "$base" -trim -bordercolor none -border 8 "$out"
        fi
        _finish_asset "$aname" "$out"
        rm -f -- "$base" "$out"
    }

    _label_asset() {
        local os=$1 text=$2 color=$3
        local on off mask grad glow
        on=$(mktemp --tmpdir="$udir" .asset-on.XXXXXX.png)
        off=$(mktemp --tmpdir="$udir" .asset-off.XXXXXX.png)
        mask=$(mktemp --tmpdir="$udir" .asset-mask.XXXXXX.png)
        grad=$(mktemp --tmpdir="$udir" .asset-grad.XXXXXX.png)
        glow=$(mktemp --tmpdir="$udir" .asset-label-glow.XXXXXX.png)
        magick -size 500x80 xc:none -font "$FONT_BOLD" -pointsize 32 -fill white -gravity center \
            -annotate +0+0 "$text" "$mask"
        magick -size 500x80 "gradient:#ffffff-${color}" "$grad"
        magick "$grad" "$mask" -alpha off -compose CopyOpacity -composite "$on"
        magick -size 500x80 xc:none -font "$FONT_BOLD" -pointsize 32 -fill "$color" -gravity center \
            -annotate +0+0 "$text" -channel A -evaluate multiply 0.25 +channel -blur 0x8 "$glow"
        magick "$glow" "$on" -compose over -composite "$on"
        magick -size 500x80 xc:none -font "$FONT_REG" -pointsize 30 -fill '#8a93a6' -gravity center \
            -annotate +0+0 "$text" "$off"
        _finish_asset "label_${os}_on" "$on"
        _finish_asset "label_${os}_off" "$off"
        rm -f -- "$on" "$off" "$mask" "$grad" "$glow"
    }

    _finish_asset bg "$bg"
    _text_asset greet_sang  "Chào buổi sáng${suffix}"  56 '#f2f4f8' "$COLOR_MORNING"
    _text_asset greet_chieu "Chào buổi chiều${suffix}" 56 '#f2f4f8' "$COLOR_AFTERNOON"
    _text_asset greet_toi   "Chào buổi tối${suffix}"   56 '#f2f4f8' "$COLOR_EVENING"
    _text_asset title 'Chọn hệ điều hành' 24 '#8a93a6'

    for spec in 'arch archlinux' 'windows windows' 'ubuntu ubuntu'; do
        read -r os logo <<<"$spec"
        rsvg-convert -w 192 -h 192 "$PAPIRUS_LOGO_DIR/distributor-logo-$logo.svg" -o "$png_dir/icon_$os.png"
        _write_tbi "icon_$os" "$png_dir/icon_$os.png"
    done

    for spec in "arch $COLOR_ARCH" "windows $COLOR_WINDOWS" "ubuntu $COLOR_UBUNTU"; do
        read -r os color <<< "$spec"
        magick -size 440x440 "radial-gradient:${color}8c-${color}00" "$png_dir/glow_$os.png"
        _write_tbi "glow_$os" "$png_dir/glow_$os.png"
    done

    _label_asset arch    'Arch Linux' "$COLOR_ARCH"
    _label_asset windows 'Windows 11' "$COLOR_WINDOWS"
    _label_asset ubuntu  'Ubuntu'     "$COLOR_UBUNTU"

    for n in $(seq 0 30); do _text_asset "count_$n" "Tự khởi động sau $n giây" 20 '#9aa3b2'; done
    _text_asset paused  'Đã dừng đếm giờ · Enter để khởi động' 20 '#9aa3b2'
    _text_asset booting 'Đang khởi động…' 20 '#f2f4f8'
    _text_asset hint    '←  →  chọn        Enter  khởi động        Esc  menu GRUB' 18 '#5d6577'
    log_ok "Đã tạo xong bộ asset .tbi cho UEFI menu."
}

uefi_build_binary() {
    log_info "Biên dịch ứng dụng UEFI (triboot.efi)..."
    make -C "$ROOT_DIR/uefi-menu"
    log_ok "Đã biên dịch uefi-menu/out/triboot.efi."
}

uefi_install() {
    local udir="$ROOT_DIR/uefi-menu"
    [ -f "$udir/out/triboot.efi" ] || run_as_user uefi_build_binary
    [ "$(ls "$udir/build/assets"/*.tbi 2>/dev/null | wc -l)" -ge 51 ] || run_as_user uefi_build_assets "$USER_NAME"
    [ "$(findmnt -no UUID "$ARCH_ESP_MNT")" = "$ARCH_ESP_UUID" ] || die "$ARCH_ESP_MNT không phải ESP $ARCH_ESP_UUID"

    log_info "Cài đặt UEFI menu vào $UEFI_MENU_DEST..."
    rm -rf "$UEFI_MENU_DEST.new"
    mkdir -p "$UEFI_MENU_DEST.new/assets"
    cp "$udir/out/triboot.efi" "$UEFI_MENU_DEST.new/"
    cp "$udir/build/assets"/*.tbi "$UEFI_MENU_DEST.new/assets/"
    sync
    rm -rf "$UEFI_MENU_DEST"
    mv "$UEFI_MENU_DEST.new" "$UEFI_MENU_DEST"
    sync

    grub_hide_extra_entries uefi
    log_ok "Đã cài đặt UEFI menu và cấu hình GRUB."
}

uefi_undo() {
    rm -f /etc/grub.d/09_triboot
    rm -rf "$UEFI_MENU_DEST"
    if [ -f "$REFIND_DIR/refind_x64.efi" ]; then
        grub_set_chainloader refind
    fi
    update_grub_cfg
    log_ok "Đã gỡ UEFI menu ($UEFI_MENU_DEST)."
}
