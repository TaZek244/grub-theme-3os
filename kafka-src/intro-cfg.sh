#!/bin/sh
# intro-cfg.sh — in lệnh GRUB cho hiệu ứng xuất hiện của theme KAFKA.SYS, đọc từ intro.txt.
#   intro-cfg.sh <thư mục theme trên máy> <đường dẫn thư mục theme NHƯ GRUB THẤY>
# Mỗi khung: background_image <khung> rồi `play 6000 0 N` = nghỉ im lặng N x 10ms (tempo 6000 nhịp/phút,
# cao độ 0 = không kêu; GRUB không có lệnh chờ dưới 1 giây). Chỉ chạy ở gfxterm, một lần mỗi lần khởi động.
set -eu
src=${1:?thiếu thư mục theme}
dst=${2:?thiếu đường dẫn GRUB}
[ -f "$src/intro.txt" ] || exit 0
cat <<GRUB
if [ "\${kafka_intro_done}" != "1" ]; then
  set kafka_intro_done=1
  export kafka_intro_done
  insmod gfxterm_background
  insmod play
GRUB
grep -v '^#' "$src/intro.txt" | while read -r f hold; do
    [ -n "$f" ] && [ -f "$src/$f" ] || continue
    echo "  background_image \"$dst/$f\""
    echo "  clear"           # gfxterm vẽ vào bộ đệm ẩn; clear ép đẩy khung ra màn hình
    if [ "${hold:-0}" -gt 0 ]; then echo "  play 6000 0 $hold"; fi
done
echo "fi"
