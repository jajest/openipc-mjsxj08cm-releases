"""Прервать автозагрузку U-Boot Xiaomi MJSXJ08CM: шлёт Ctrl+C, Enter и пробел, пока не появится «SigmaStar #».

    python uart_break.py [порт=COM11] [секунд=60]

Запустить, затем включить камеру. Всё принятое пишется в uart-break-<время>.log в текущей папке.
Нужен pyserial: pip install pyserial. Порт: Windows — COMn (Диспетчер устройств), Linux — /dev/ttyUSB0.
"""
import re
import sys
import time
from pathlib import Path

import serial

port = sys.argv[1] if len(sys.argv) > 1 else "COM11"
secs = float(sys.argv[2]) if len(sys.argv) > 2 else 60
# приглашения U-Boot SigmaStar бывают «SigmaStar #», «=>», «#»
PROMPT = re.compile(rb"(SigmaStar\s*#|=>\s*$|^\S*#\s*$)", re.M)

log = Path(time.strftime("uart-break-%Y%m%d-%H%M%S.log"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
print(f"{port}: жду загрузку {secs:.0f} с, шлю прерывание -> {log}", flush=True)

buf = b""
with serial.Serial(port, 115200, timeout=0.02) as s, open(log, "wb") as f:
    end = time.time() + secs
    seen_boot = False
    while time.time() < end:
        data = s.read(4096)
        if data:
            buf += data
            f.write(data)
            f.flush()
            sys.stdout.write(data.decode("utf-8", "replace"))
            sys.stdout.flush()
        if not seen_boot and (b"IPL" in buf or b"U-Boot" in buf):
            seen_boot = True
        if seen_boot:
            s.write(b"\x03\r ")  # Ctrl+C, Enter, пробел — что-то из этого обычно ловится
            if PROMPT.search(buf[-200:]):
                s.write(b"\r")
                time.sleep(0.5)
                tail = s.read(4096)
                f.write(tail)
                print(tail.decode("utf-8", "replace"), "\n-- приглашение получено", flush=True)
                break
        if b"Starting kernel" in buf:
            print("\n-- U-Boot не прервался, ядро стартует", flush=True)
            break
