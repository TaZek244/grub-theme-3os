#!/usr/bin/env bash
# ==============================================================================
# CẤU HÌNH TRUNG TÂM (SETTINGS) CHO TRIBOOT
# Chỉnh sửa file này để thay đổi tên hiển thị, chế độ khởi động, thời gian chờ
# hoặc UUID phân vùng.
# ==============================================================================

# --- 1. Tùy chỉnh giao diện & hành vi ---
USER_NAME="${TRIBOOT_NAME:-TaZek}"        # Tên hiển thị trên lời chào / tạm biệt (để "" nếu không muốn hiện tên)
BOOT_MODE="${TRIBOOT_MODE:-refind}"       # Chế độ menu chính: "refind" | "uefi" | "grub"
FAST_BOOT=1                               # 1 = Tắt GRUB đồ họa trung gian + dùng ảnh BMP không nén cho rEFInd
MENU_TIMEOUT=8                            # Thời gian đếm ngược tự khởi động (giây)
RESOLUTION="1920x1080"                    # Độ phân giải màn hình menu

# --- 2. Thông tin phân vùng phần cứng (UUID / PARTUUID) ---
ARCH_ESP_MNT="/boot"
ARCH_ESP_UUID="15AA-0CE1"                                    # sda1 (vfat - ESP của Arch)
ARCH_ESP_PARTUUID="124a725e-8a92-4d60-accd-91697f6e1b76"     # PARTUUID của sda1
ARCH_ROOT_UUID="8006d6ff-4672-4328-a7b4-86ce5b21ba88"        # Root (/) của Arch Linux

NVME_ESP_UUID="4C7D-3ECC"                                    # nvme0n1p1 (ESP của Windows 11 + Ubuntu)
NVME_ESP_PARTUUID="2ecc4d3c-983c-4039-8914-553998470895"     # PARTUUID của nvme0n1p1
UBUNTU_ROOT_UUID="5fa9547f-3752-4735-a2e3-155df7bbaad3"      # nvme0n1p5 (Root / và /boot của Ubuntu)

# --- 3. Đường dẫn hệ thống ---
GRUB_THEME_DIR="/boot/grub/themes/triboot"
GRUB_HOOK_FILE="/etc/pacman.d/hooks/triboot-grubd.hook"
GRUB_HIDE_SCRIPTS="10_linux 30_uefi-firmware 31_efi_bootnext"

REFIND_DIR="$ARCH_ESP_MNT/EFI/refind"
REFIND_CONF="$REFIND_DIR/refind.conf"
REFIND_THEME_DIR="$REFIND_DIR/themes/triboot"
EFI_LABEL="Triboot"

UEFI_MENU_DEST="$ARCH_ESP_MNT/EFI/triboot"

PLYMOUTH_ARCH_DIR="/usr/share/plymouth/themes/triboot"
PLYMOUTH_UBUNTU_NAME="triboot-ubuntu"
PLYMOUTH_UBUNTU_DIR="/usr/share/plymouth/themes/$PLYMOUTH_UBUNTU_NAME"
MKINITCPIO_CONF="/etc/mkinitcpio.conf"

GREET_BIN="/usr/local/bin/triboot-greeting"
GREET_SERVICE="/etc/systemd/system/triboot-greeting.service"

# --- 4. Thư mục sao lưu (tương thích với các bản sao lưu cũ) ---
BK_GRUB="/root/grub-backup-triboot"
BK_FIXMENU="/root/triboot-fixmenu-backup"
BK_FASTBOOT="/root/triboot-fastboot-backup"
BK_EFFECTS="/root/triboot-effects-backup"
BK_UBUNTU="/root/triboot-ubuntu-backup"

# --- 5. Phông chữ & Màu sắc tạo tài nguyên (Assets) ---
FONT_BOLD="/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"
FONT_REG="/usr/share/fonts/TTF/DejaVuSans.ttf"
PAPIRUS_LOGO_DIR="/usr/share/icons/Papirus/64x64/apps"

COLOR_ARCH="#1793d1"
COLOR_WINDOWS="#00a4ef"
COLOR_UBUNTU="#e95420"
COLOR_MORNING="#ffb347"
COLOR_AFTERNOON="#7cc8ff"
COLOR_EVENING="#8c6cff"
