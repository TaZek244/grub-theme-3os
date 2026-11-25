#!/usr/bin/env bash
# ==============================================================================
# TRIBOOT — TRÌNH CÀI ĐẶT & QUẢN LÝ DUY NHẤT (install.sh)
# Toàn bộ cấu hình nằm ở: lib/config.sh
# Các hàm chức năng nằm ở: lib/{common,grub,refind,effects,uefi}.sh
# ==============================================================================
set -euo pipefail

ROOT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT_DIR"

# Nạp cấu hình và các thư viện hàm
source "$ROOT_DIR/lib/config.sh"
source "$ROOT_DIR/lib/common.sh"
source "$ROOT_DIR/lib/grub.sh"
source "$ROOT_DIR/lib/refind.sh"
source "$ROOT_DIR/lib/effects.sh"
source "$ROOT_DIR/lib/uefi.sh"
source "$ROOT_DIR/lib/kafka.sh"

usage() {
    cat <<EOF
Cách dùng: sudo ./install.sh [TÙY CHỌN]

Chế độ chạy (mặc định không tham số = cập nhật lời chào/tạm biệt + Plymouth + fast-boot):
  (trống)              Tạo ảnh lời chào/tạm biệt ($USER_NAME) -> cập nhật Plymouth -> tối ưu fast-boot -> đồng bộ Ubuntu
  --all                Cài đặt toàn bộ từ đầu (GRUB + ${BOOT_MODE} + Plymouth + fast-boot)
  --effects            Chỉ tạo lại bộ ảnh lời chào/tạm biệt và cập nhật Plymouth + đồng bộ Ubuntu
  --refind             Cài đặt menu ngang rEFInd + tối ưu fast-boot BMP
  --uefi               Biên dịch & cài đặt menu ngang UEFI tự viết (triboot.efi) + ẩn mục thừa GRUB
  --grub               Cài đặt theme GRUB dọc truyền thống + mục boot 3 OS (theme chọn bằng --theme)
  --kafka              Tạo + cài theme GRUB pixel KAFKA.SYS (BOOT_MODE="grub": = --theme kafka --grub; chế độ khác: chỉ chép theme, không đổi luồng khởi động)
  --kafka-assets       Chỉ sinh ảnh/font/icon theme KAFKA.SYS vào kafka/ (không cần sudo)
  --kafka-preview      Chạy GRUB thật với theme KAFKA.SYS trong QEMU, chụp preview-kafka.png + GIF hiệu ứng (không cần sudo)
  --kafka-line         Biên dịch & cài đặt menu tuyến tàu ngang KAFKA.SYS (kafka.efi) + ẩn mục thừa GRUB
  --kafka-line-build   Chỉ dựng ảnh .tbi + kafka.efi cho menu KAFKA.SYS (không cần sudo)
  --fast-boot          Bật tối ưu khởi động nhanh (ảnh BMP không nén + tắt GRUB đồ họa trung gian)
  --ubuntu             Chạy TRONG Ubuntu (20.04+): cài màn hình chào/tạm biệt Plymouth, ẩn menu GRUB của Ubuntu
                       (chọn Ubuntu ở menu chính là vào thẳng). Trong Ubuntu, chạy không tham số = --ubuntu
  --assets             Chỉ tạo lại toàn bộ file ảnh (không cần sudo)

Tùy chọn kèm theo:
  --theme triboot|kafka  Theme GRUB dọc dùng cho --grub / --all (mặc định: "$GRUB_THEME_NAME")
  --name "Tên"         Đặt tên hiển thị trên lời chào & tạm biệt (mặc định trong lib/config.sh: "$USER_NAME")
  --undo               Hoàn tác về cấu hình trước đó (có thể kết hợp: --undo, --refind --undo, --uefi --undo, --kafka-line --undo, --ubuntu --undo)
  -h, --help           Hiện hướng dẫn này
EOF
}

ACTION="default"
UNDO=0

while [ $# -gt 0 ]; do
    case "$1" in
        --all|--effects|--refind|--uefi|--grub|--fast-boot|--ubuntu|--assets|--kafka|--kafka-assets|--kafka-preview|--kafka-line|--kafka-line-build)
            ACTION="${1#--}"
            shift
            ;;
        --name)
            [ $# -ge 2 ] || die "Thiếu giá trị cho --name"
            USER_NAME="$2"
            shift 2
            ;;
        --theme)
            [ $# -ge 2 ] || die "Thiếu giá trị cho --theme"
            case "$2" in triboot|kafka) GRUB_THEME_NAME="$2" ;; *) die "Theme không hợp lệ: $2 (triboot | kafka)" ;; esac
            shift 2
            ;;
        --undo)
            UNDO=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "Tham số không hợp lệ: $1 (xem ./install.sh --help)"
            ;;
    esac
done

[ "$ACTION" = "kafka" ] && GRUB_THEME_NAME="kafka"
# Trong Ubuntu: chế độ mặc định / --effects (vốn cho Arch: mkinitcpio, rEFInd) chuyển thành --ubuntu
if is_ubuntu && { [ "$ACTION" = default ] || [ "$ACTION" = effects ]; }; then
    ACTION=ubuntu
fi
GRUB_THEME_DIR="/boot/grub/themes/$GRUB_THEME_NAME"

# Theme KAFKA.SYS: sinh ảnh / xem trước không cần sudo
if [ "$ACTION" = "kafka-assets" ]; then
    kafka_build_assets "$USER_NAME"
    exit 0
fi
if [ "$ACTION" = "kafka-preview" ]; then
    [ -f "$KAFKA_OUT/background.png" ] || kafka_build_assets "$USER_NAME"
    kafka_preview
    exit 0
fi

# Menu tuyến tàu ngang KAFKA.SYS: chỉ dựng ảnh + kafka.efi, không cần sudo
if [ "$ACTION" = "kafka-line-build" ]; then
    kafka_line_build
    exit 0
fi

# Chế độ chỉ tạo ảnh không cần sudo
if [ "$ACTION" = "assets" ]; then
    effects_build_assets "$USER_NAME"
    uefi_build_assets "$USER_NAME"
    exit 0
fi

require_root "$@"

# Xử lý hoàn tác (--undo)
if [ "$UNDO" -eq 1 ]; then
    case "$ACTION" in
        ubuntu)    effects_undo_ubuntu ;;
        fast-boot) refind_undo_fastboot ;;
        effects)   effects_undo_arch ;;
        uefi)      uefi_undo; grub_undo_fixmenu ;;
        kafka-line) kafka_line_undo; grub_undo_fixmenu ;;
        refind)    refind_undo; grub_undo_fixmenu ;;
        grub)      grub_undo_base ;;
        kafka)     rm -rf /boot/grub/themes/kafka; GRUB_THEME_DIR="/boot/grub/themes/triboot"; grub_undo_base ;;
        *)
            log_info "Hoàn tác cấu hình Triboot..."
            refind_undo_fastboot
            effects_undo_arch
            grub_undo_fixmenu
            grub_undo_base
            ;;
    esac
    exit 0
fi

# Xử lý cài đặt / cập nhật theo chế độ
case "$ACTION" in
    default|effects)
        run_as_user bash -c "ROOT_DIR='$ROOT_DIR'; KAFKA_DESKTOP_DIR='$KAFKA_DESKTOP_DIR'; source '$ROOT_DIR/lib/config.sh'; source '$ROOT_DIR/lib/common.sh'; source '$ROOT_DIR/lib/effects.sh'; effects_build_assets '$USER_NAME'"
        effects_install_arch
        if [ "$ACTION" = "default" ] && [ "${FAST_BOOT:-1}" -eq 1 ] && [ -f "$REFIND_CONF" ]; then
            refind_enable_fastboot
        fi
        effects_sync_ubuntu_from_arch
        log_info "Hoàn tất cập nhật!"
        ;;

    all)
        [ "$GRUB_THEME_NAME" = "kafka" ] && run_as_user bash -c "ROOT_DIR='$ROOT_DIR'; KAFKA_DESKTOP_DIR='$KAFKA_DESKTOP_DIR'; source '$ROOT_DIR/lib/config.sh'; source '$ROOT_DIR/lib/common.sh'; source '$ROOT_DIR/lib/kafka.sh'; kafka_build_assets '$USER_NAME'"
        grub_install_base
        run_as_user bash -c "ROOT_DIR='$ROOT_DIR'; KAFKA_DESKTOP_DIR='$KAFKA_DESKTOP_DIR'; source '$ROOT_DIR/lib/config.sh'; source '$ROOT_DIR/lib/common.sh'; source '$ROOT_DIR/lib/effects.sh'; effects_build_assets '$USER_NAME'"
        if [ "$BOOT_MODE" = "uefi" ]; then
            run_as_user bash -c "ROOT_DIR='$ROOT_DIR'; source '$ROOT_DIR/lib/config.sh'; source '$ROOT_DIR/lib/common.sh'; source '$ROOT_DIR/lib/uefi.sh'; uefi_build_assets '$USER_NAME'; uefi_build_binary"
            uefi_install
        elif [ "$BOOT_MODE" = "refind" ]; then
            refind_install
        fi
        effects_install_arch
        if [ "$BOOT_MODE" = "refind" ] && [ "${FAST_BOOT:-1}" -eq 1 ]; then
            refind_enable_fastboot
        fi
        effects_sync_ubuntu_from_arch
        print_grub_entries
        log_info "Đã cài đặt toàn bộ Triboot hoàn tất!"
        ;;

    refind)
        refind_install
        if [ "${FAST_BOOT:-1}" -eq 1 ]; then
            refind_enable_fastboot
        fi
        ;;

    uefi)
        run_as_user bash -c "ROOT_DIR='$ROOT_DIR'; source '$ROOT_DIR/lib/config.sh'; source '$ROOT_DIR/lib/common.sh'; source '$ROOT_DIR/lib/uefi.sh'; uefi_build_assets '$USER_NAME'; uefi_build_binary"
        uefi_install
        print_grub_entries
        ;;

    kafka-line)
        run_as_user bash -c "ROOT_DIR='$ROOT_DIR'; KAFKA_DESKTOP_DIR='$KAFKA_DESKTOP_DIR'; source '$ROOT_DIR/lib/config.sh'; source '$ROOT_DIR/lib/common.sh'; source '$ROOT_DIR/lib/grub.sh'; source '$ROOT_DIR/lib/uefi.sh'; kafka_line_build"
        kafka_line_install
        print_grub_entries
        ;;

    grub)
        grub_install_base
        print_grub_entries
        ;;

    kafka)
        run_as_user bash -c "ROOT_DIR='$ROOT_DIR'; KAFKA_DESKTOP_DIR='$KAFKA_DESKTOP_DIR'; source '$ROOT_DIR/lib/config.sh'; source '$ROOT_DIR/lib/common.sh'; source '$ROOT_DIR/lib/kafka.sh'; kafka_build_assets '$USER_NAME'"
        if [ "$BOOT_MODE" = "grub" ]; then
            grub_install_base
            print_grub_entries
        else
            # Menu chính là rEFInd/UEFI (GRUB ẩn, fast-boot): chỉ chép theme, KHÔNG đổi /etc/default/grub
            # để không làm thay đổi luồng khởi động hiện tại.
            rm -rf "$GRUB_THEME_DIR"; mkdir -p "$GRUB_THEME_DIR"
            cp -r "$KAFKA_OUT/." "$GRUB_THEME_DIR/"; rm -f "$GRUB_THEME_DIR"/.asset-*
            log_ok "Đã chép theme vào $GRUB_THEME_DIR (chưa bật)."
            log_warn "Menu chính đang là '$BOOT_MODE' nên GRUB bị ẩn. Muốn dùng theme: đặt BOOT_MODE=\"grub\" trong lib/config.sh rồi chạy lại sudo ./install.sh --kafka"
        fi
        ;;

    fast-boot)
        refind_enable_fastboot
        ;;

    ubuntu)
        effects_install_ubuntu
        ;;
esac
