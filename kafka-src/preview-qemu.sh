#!/usr/bin/env bash
# preview-qemu.sh — chạy GRUB THẬT với một theme trong QEMU (OVMF, không đụng ổ đĩa/ESP của máy) rồi chụp màn hình.
#   kafka-src/preview-qemu.sh <thư mục theme> <ảnh ra.png> [số giây chờ=7] [phím gửi trước khi chụp, vd "down down"]
#   Chế độ GIF (đặt biến môi trường GIF = đường dẫn file GIF ra):
#       GIF=intro.gif kafka-src/preview-qemu.sh <theme> <ảnh ra.png>
#       Tuỳ chọn: GIF_START=1.0 (giây chờ trước khi chụp), GIF_SECONDS=6 (thời lượng chụp),
#       GIF_INTERVAL=0.1 (giây giữa hai frame). Giữ một kết nối monitor duy nhất trong suốt
#       lần chụp, tạo GIF resize 50% với delay tính theo timestamp thực của từng frame,
#       rồi vẫn ghi frame cuối (nguyên kích thước) ra <ảnh ra.png>. Ở chế độ này không dùng WAIT/KEYS.
# Cần: grub (grub-mkstandalone), qemu-system-x86_64, edk2-ovmf, imagemagick. Không cần sudo.
set -euo pipefail

THEME=$(cd -- "${1:?thiếu thư mục theme}" && pwd)
OUT=$(realpath -m -- "${2:?thiếu ảnh ra}")
WAIT=${3:-7}
KEYS=${4:-}
OVMF_DIR=""
for d in /usr/share/edk2/x64 /usr/share/ovmf/x64 /usr/share/OVMF; do
    [ -f "$d/OVMF_CODE.4m.fd" ] && OVMF_DIR=$d && break
done
[ -n "$OVMF_DIR" ] || { echo "Không thấy OVMF (pacman -S edk2-ovmf)" >&2; exit 1; }

WORK=$(mktemp -d "${TMPDIR:-/tmp}/kafka-grub-preview.XXXXXX")
trap 'kill "${QPID:-0}" 2>/dev/null || true; rm -rf "$WORK"' EXIT
mkdir -p "$WORK/esp/EFI/BOOT"
NAME=$(basename "$THEME")

cat > "$WORK/grub.cfg" <<EOF
insmod all_video
insmod gfxterm
insmod png
insmod font
insmod regexp
set gfxmode=1920x1080,auto
set gfxpayload=keep
terminal_output gfxterm
for f in (memdisk)/themes/$NAME/*.pf2; do loadfont "\$f"; done
set theme=(memdisk)/themes/$NAME/theme.txt
EOF

# hiệu ứng xuất hiện (dùng chung với /etc/grub.d/05_kafka_intro)
sh "$(dirname -- "$0")/intro-cfg.sh" "$THEME" "(memdisk)/themes/$NAME" >> "$WORK/grub.cfg"

cat >> "$WORK/grub.cfg" <<EOF
set timeout=30
set default=0
menuentry 'Triboot' --class triboot { true }
menuentry 'Arch Linux' --class arch --class gnu-linux --class os { true }
menuentry 'Windows 11' --class windows --class os { true }
menuentry 'Ubuntu' --class ubuntu --class gnu-linux --class os { true }
menuentry 'Khởi động lại' --class restart { reboot }
menuentry 'Tắt máy' --class shutdown { halt }
EOF

grub-mkstandalone -O x86_64-efi -o "$WORK/esp/EFI/BOOT/BOOTX64.EFI" \
    --modules="part_gpt fat all_video gfxterm png font regexp gfxterm_background play" \
    "boot/grub/grub.cfg=$WORK/grub.cfg" "themes/$NAME=$THEME"

cp "$OVMF_DIR/OVMF_VARS.4m.fd" "$WORK/vars.fd"

KVM_ARGS=()
if [ -r /dev/kvm ] && [ -w /dev/kvm ]; then
    KVM_ARGS=(-enable-kvm -cpu host)
    echo "QEMU: dùng KVM (/dev/kvm)" >&2
else
    echo "QEMU: dùng TCG (/dev/kvm không dùng được)" >&2
fi

qemu-system-x86_64 -machine q35 -m 512 -nodefaults -no-user-config \
    -drive if=pflash,format=raw,readonly=on,file="$OVMF_DIR/OVMF_CODE.4m.fd" \
    -drive if=pflash,format=raw,file="$WORK/vars.fd" \
    -drive file=fat:rw:"$WORK/esp",format=raw,if=virtio \
    -device VGA,xres=1920,yres=1080 -display none \
    "${KVM_ARGS[@]}" \
    -monitor unix:"$WORK/mon",server,nowait &
QPID=$!

mon() { python3 -c 'import socket,sys,time
s=socket.socket(socket.AF_UNIX); s.connect(sys.argv[1]); time.sleep(0.2); s.recv(4096)
for c in sys.argv[2:]:
    s.sendall((c+"\n").encode()); time.sleep(0.4)
time.sleep(0.5); s.close()' "$WORK/mon" "$@"; }

if [ -n "${GIF:-}" ]; then
    GIF_START=${GIF_START:-1.0}
    GIF_SECONDS=${GIF_SECONDS:-6}
    GIF_INTERVAL=${GIF_INTERVAL:-0.1}
    sleep "$GIF_START"

    # Một kết nối monitor duy nhất cho toàn bộ lần chụp; mỗi dòng in ra là
    # "<đường dẫn frame> <timestamp>" (để bash tính delay thật giữa các frame).
    captured=$(python3 -c 'import socket,sys,time
s=socket.socket(socket.AF_UNIX); s.connect(sys.argv[1]); time.sleep(0.2); s.recv(4096)
interval=float(sys.argv[2]); duration=float(sys.argv[3]); prefix=sys.argv[4]
t0=time.monotonic(); n=0
while time.monotonic()-t0 < duration:
    t=time.monotonic()
    path="%s/f-%04d.ppm" % (prefix, n)
    s.sendall(("screendump "+path+"\n").encode())
    print(path+" "+repr(t), flush=True)
    n+=1
    time.sleep(interval)
time.sleep(0.5)
print("END "+repr(time.monotonic()))
s.close()' "$WORK/mon" "$GIF_INTERVAL" "$GIF_SECONDS" "$WORK")

    frame_lines=()
    if [ -n "$captured" ]; then
        mapfile -t frame_lines <<< "$captured"
    fi

    paths=()
    times=()
    end_ts=""
    for line in "${frame_lines[@]}"; do
        case "$line" in
            END\ *) end_ts=${line#END } ;;
            *\ *) paths+=("${line%% *}"); times+=("${line##* }") ;;
        esac
    done
    if [ -z "$end_ts" ] && [ ${#times[@]} -gt 0 ]; then
        end_ts=${times[$(( ${#times[@]} - 1 ))]}
    fi

    # Chờ các file PPM do QEMU ghi xong (screendump là bất đồng bộ).
    for f in "${paths[@]}"; do
        for _ in 1 2 3 4 5 6 7 8 9 10; do
            if [ -s "$f" ]; then break; fi
            sleep 0.1
        done
    done

    # Delay thực (centisecond, tối thiểu 2) giữa hai timestamp liên tiếp.
    delays=()
    for i in "${!paths[@]}"; do
        if [ $((i + 1)) -lt ${#times[@]} ]; then
            t_next=${times[$((i + 1))]}
        else
            t_next=$end_ts
        fi
        d=$(awk -v a="${times[$i]}" -v b="$t_next" 'BEGIN { d=int((b-a)*100+0.5); if (d<2) d=2; print d }')
        delays+=("$d")
    done

    # Bỏ các frame trùng liên tiếp (vd intro đen ở đầu): cộng delay của chúng
    # vào frame trước đó đã giữ lại.
    keep_paths=()
    keep_delays=()
    prev_md5=""
    for i in "${!paths[@]}"; do
        f=${paths[$i]}
        if [ ! -s "$f" ]; then continue; fi
        h=$(md5sum -- "$f" | awk '{print $1}')
        if [ -n "$prev_md5" ] && [ "$h" = "$prev_md5" ]; then
            j=$((${#keep_delays[@]} - 1))
            keep_delays[$j]=$(( ${keep_delays[$j]} + ${delays[$i]} ))
            continue
        fi
        keep_paths+=("$f")
        keep_delays+=("${delays[$i]}")
        prev_md5=$h
    done
    if [ ${#keep_paths[@]} -eq 0 ] && [ ${#paths[@]} -gt 0 ]; then
        keep_paths=("${paths[0]}")
        keep_delays=("${delays[0]}")
    fi

    if [ ${#keep_paths[@]} -gt 0 ]; then
        gif_args=()
        for i in "${!keep_paths[@]}"; do
            gif_args+=(-delay "${keep_delays[$i]}" "${keep_paths[$i]}")
        done
        magick "${gif_args[@]}" -resize 50% -loop 0 -layers Optimize "$GIF"
        echo "GIF: $GIF" >&2
    else
        echo "Không chụp được frame nào cho GIF" >&2
    fi

    last_frame=""
    if [ ${#paths[@]} -gt 0 ]; then
        last_frame=${paths[$(( ${#paths[@]} - 1 ))]}
    fi
    if [ -z "$last_frame" ] || [ ! -s "$last_frame" ]; then
        mon "screendump $WORK/shot.ppm"
        sleep 1
        last_frame="$WORK/shot.ppm"
    fi
    magick "$last_frame" "$OUT"
else
    sleep "$WAIT"
    if [ -n "$KEYS" ]; then
        cmds=()
        for k in $KEYS; do cmds+=("sendkey $k"); done
        mon "${cmds[@]}"
        sleep 1
    fi
    mon "screendump $WORK/shot.ppm"
    sleep 1
    magick "$WORK/shot.ppm" "$OUT"
fi
echo "$OUT"
