"""Запуск OpenIPC в ОЗУ с microSD: прервать U-Boot, выполнить команды из boot.txt релиза, писать лог загрузки.

    python uart_ramboot.py [--cmds boot.txt] [--port COM11] [--wait 120] [--log 180]

Запустить, затем включить камеру. Во флеш ничего не пишется: saveenv, sf write и sf erase скрипт отвергает.
Лог — uart-ramboot-<время>.log в текущей папке. Нужен pyserial.
"""
import argparse
import re
import sys
import time
from pathlib import Path

import serial

PROMPT = b"SigmaStar # "
FORBIDDEN = re.compile(r"^\s*(saveenv|sf\s+(write|erase|update)|env\s+save)", re.I)

ap = argparse.ArgumentParser()
ap.add_argument("--cmds", default="boot.txt")
ap.add_argument("--port", default="COM11")
ap.add_argument("--wait", type=float, default=120, help="сколько ждать включения камеры, с")
ap.add_argument("--log", type=float, default=180, help="сколько писать лог после bootm, с")
a = ap.parse_args()

cmds = [l.strip() for l in Path(a.cmds).read_text(encoding="utf-8-sig").splitlines()
        if l.strip() and not l.lstrip().startswith("#")]
bad = [c for c in cmds if FORBIDDEN.match(c)]
if bad:
    raise SystemExit(f"запись во флеш запрещена: {bad}")

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # консоль Windows — cp1251, мусор с UART её роняет
log = Path(time.strftime("uart-ramboot-%Y%m%d-%H%M%S.log"))
s = serial.Serial(a.port, 115200, timeout=0.02)
f = open(log, "wb")


def rx():
    data = s.read(4096)
    if data:
        f.write(data)
        f.flush()
        sys.stdout.write(data.decode("utf-8", "replace"))
        sys.stdout.flush()
    return data


print(f"{a.port}: включайте камеру (жду {a.wait:.0f} с) -> {log}", flush=True)
buf, end, seen = b"", time.time() + a.wait, False
while time.time() < end:
    buf += rx()
    seen = seen or b"IPL" in buf or b"U-Boot" in buf
    if seen:
        s.write(b"\x03\r ")  # как в uart_break.py: один Ctrl+C не ловится
        if PROMPT.rstrip() in buf[-200:]:
            s.write(b"\r")
            time.sleep(0.5)
            rx()
            break
    if b"Starting kernel" in buf:
        raise SystemExit("\n-- U-Boot не прервался")
else:
    raise SystemExit("\n-- камера не загрузилась / нет приглашения")

time.sleep(0.3)
s.reset_input_buffer()
for cmd in cmds:
    s.write(cmd.encode() + b"\r")
    buf, end = b"", time.time() + (a.log if cmd.startswith("bootm") else 60)
    while time.time() < end:
        buf += rx()
        if not cmd.startswith("bootm") and buf.endswith(PROMPT):
            break
    else:
        if not cmd.startswith("bootm"):
            raise SystemExit(f"\n-- нет приглашения после: {cmd}")
    if re.search(rb"(\*\* Unable|Error|error|not found|No card|Bad )", buf) and not cmd.startswith("bootm"):
        raise SystemExit(f"\n-- ошибка на команде: {cmd}")
print("\n-- лог записан:", log)
