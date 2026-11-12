#!/usr/bin/env bash
# ==============================================================================
# THƯ VIỆN HÀM TIỆN ÍCH DÙNG CHUNG (COMMON HELPERS)
# ==============================================================================

log_info()  { printf '\033[1;34m==>\033[0m \033[1m%s\033[0m\n' "$*"; }
log_ok()    { printf '\033[1;32m  ✓\033[0m %s\n' "$*"; }
log_warn()  { printf '\033[1;33m  !\033[0m %s\n' "$*" >&2; }
die()       { printf '\033[1;31m  ✗ Lỗi:\033[0m %s\n' "$*" >&2; exit 1; }

require_root() {
    [ "$(id -u)" -eq 0 ] || die "Cần chạy bằng quyền root: sudo ./install.sh $*"
}

# Chạy lệnh với quyền user thường (tránh tạo file build thuộc sở hữu root trong repo)
run_as_user() {
    if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
        sudo -u "$SUDO_USER" "$@"
    else
        "$@"
    fi
}

# Đặt hoặc thay thế dòng KEY=VALUE trong /etc/default/grub
set_grub_opt() {
    local k=$1 v=$2 file=${3:-/etc/default/grub}
    if grep -qE "^#?\s*${k}=" "$file"; then
        sed -i -E "s|^#?\s*${k}=.*|${k}=${v}|" "$file"
    else
        echo "${k}=${v}" >> "$file"
    fi
}

# Sinh lại grub.cfg và kiểm tra cú pháp an toàn
update_grub_cfg() {
    grub-mkconfig -o /boot/grub/grub.cfg
    grub-script-check /boot/grub/grub.cfg
}

# Liệt kê các mục menu hiện có trong grub.cfg
print_grub_entries() {
    echo "Các mục hiện có trong GRUB:"
    grep -E "^\s*menuentry '" /boot/grub/grub.cfg | sed -E "s/^\s*menuentry '([^']*)'.*/  - \1/" || true
}
