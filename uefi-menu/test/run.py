# Chạy menu trong QEMU, gửi phím theo kịch bản, chụp màn hình, in log serial.
# Dùng: python3 -I run.py OUTDIR "phím@giây,..."   (phím theo tên QEMU sendkey, vd right@3,ret@5)
import os, socket, subprocess, sys, time
here = os.path.dirname(os.path.abspath(__file__)); out = sys.argv[1]; script = sys.argv[2] if len(sys.argv) > 2 else ""
shots = [float(x) for x in (sys.argv[3] if len(sys.argv) > 3 else "1,2,4").split(",")]
os.makedirs(out, exist_ok=True)
mon = os.path.join(out, "mon.sock"); vars_ = os.path.join(out, "vars.fd")
subprocess.run(["cp", "/usr/share/edk2/x64/OVMF_VARS.4m.fd", vars_], check=True)
q = subprocess.Popen(["qemu-system-x86_64", "-machine", "q35", "-m", "1024", "-display", "none",
    "-device", "VGA,xres=1920,yres=1080", "-serial", "file:" + os.path.join(out, "serial.log"),
    "-monitor", "unix:%s,server,nowait" % mon,
    "-drive", "if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd",
    "-drive", "if=pflash,format=raw,file=" + vars_,
    "-drive", "format=raw,file=fat:rw:" + os.path.join(here, "esp"),
    "-drive", "format=raw,file=fat:rw:" + os.path.join(here, "nvme"), "-net", "none"])
for _ in range(50):
    if os.path.exists(mon): break
    time.sleep(0.1)
s = socket.socket(socket.AF_UNIX); s.connect(mon)
def cmd(c): s.sendall((c + "\n").encode()); time.sleep(0.05)
# chờ tới khi menu bắt đầu (log có dòng nạp BOOTX64)
log = os.path.join(out, "serial.log"); t0 = None
for _ in range(400):
    if os.path.exists(log) and b"starting Boot" in open(log, "rb").read(): t0 = time.time(); break
    time.sleep(0.05)
if t0 is None: print("menu không chạy"); q.kill(); sys.exit(1)
events = [(float(t), "key", k) for k, t in (e.split("@") for e in script.split(",") if e)] + [(t, "shot", None) for t in shots]
for t, kind, k in sorted(events):
    time.sleep(max(0, t0 + t - time.time()))
    if kind == "key": cmd("sendkey " + k)
    else: cmd("screendump %s/shot_%05.2f.ppm" % (out, t))
time.sleep(1.0); q.kill()
print(open(log, "rb").read().decode("utf-8", "replace").replace("\x1b", "")[-600:])
