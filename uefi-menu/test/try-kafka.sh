#!/usr/bin/env bash
# Mở menu tuyến tàu KAFKA.SYS trong cửa sổ QEMU để tự bấm thử (không đụng ổ đĩa/ESP thật, không cần sudo).
#   uefi-menu/test/try-kafka.sh            # dùng ảnh đã dựng (./install.sh --kafka-line-build)
# Loader Arch/Windows/Ubuntu là bản giả (test/echo.c): chọn trạm sẽ hiện dòng FAKE-LOADER-STARTED.
# "Tắt máy" đóng cửa sổ QEMU, "Khởi động lại" khởi động lại máy ảo. Đóng cửa sổ để thoát.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(cd -- "$HERE/../.." && pwd)
[ -f "$ROOT/uefi-menu/out/kafka.efi" ] && [ -d "$ROOT/uefi-menu/build-kafka/assets" ] || "$ROOT/install.sh" --kafka-line-build
OVMF=/usr/share/edk2/x64
WORK=$(mktemp -d "${TMPDIR:-/tmp}/kafka-try.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/esp/EFI/BOOT" "$WORK/esp/EFI/kafka"
cp "$ROOT/uefi-menu/out/kafka.efi" "$WORK/esp/EFI/BOOT/BOOTX64.EFI"
cp -r "$ROOT/uefi-menu/build-kafka/assets" "$WORK/esp/EFI/kafka/"
cp "$HERE/esp/vmlinuz-linux" "$WORK/esp/"          # Arch giả
cp -r "$HERE/nvme" "$WORK/nvme"                    # Windows + Ubuntu giả
cp "$OVMF/OVMF_VARS.4m.fd" "$WORK/vars.fd"
KVM=(); [ -r /dev/kvm ] && [ -w /dev/kvm ] && KVM=(-enable-kvm -cpu host)
qemu-system-x86_64 -machine q35 -m 1024 "${KVM[@]}" -name "KAFKA.SYS // LINE 01" \
    -device VGA,xres=1920,yres=1080 -display gtk,zoom-to-fit=on -net none \
    -drive if=pflash,format=raw,readonly=on,file="$OVMF/OVMF_CODE.4m.fd" \
    -drive if=pflash,format=raw,file="$WORK/vars.fd" \
    -drive format=raw,file=fat:rw:"$WORK/esp" \
    -drive format=raw,file=fat:rw:"$WORK/nvme"
