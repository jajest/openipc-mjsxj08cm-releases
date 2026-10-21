"""Полная копия SPI-флеша через консоль U-Boot: sf read в ОЗУ, затем md.b по кускам с проверкой crc32 каждого.

    python uart_dump.py flash-stock.bin [--port COM11] [--size 0x1000000] [--chunk 0x10000]

Запускать, когда камера уже стоит в приглашении «SigmaStar #» (uart_break.py). Флеш только читается.
Можно прервать и запустить снова: проверенные куски (файл <имя>.done) пропускаются. Нужен pyserial.
"""
import argparse
import re
import sys
import time
import zlib
from pathlib import Path

import serial

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RAM = 0x22000000
PROMPT = b"SigmaStar # "
LINE = re.compile(rb"^([0-9a-f]{8}):((?: [0-9a-f]{2}){1,16})", re.M)
CRC = re.compile(rb"==> ([0-9a-f]{8})")

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--port", default="COM11")
ap.add_argument("--baud", type=int, default=115200)
ap.add_argument("--size", type=lambda x: int(x, 0), default=0x1000000)
ap.add_argument("--chunk", type=lambda x: int(x, 0), default=0x10000)
ap.add_argument("--no-read", action="store_true", help="флеш уже в ОЗУ (sf read сделан)")
a = ap.parse_args()

out = Path(a.out)
done_file = out.with_suffix(out.suffix + ".done")
done = set(int(x, 16) for x in done_file.read_text().split()) if done_file.exists() else set()
if not out.exists():
    out.write_bytes(b"\xff" * a.size)

s = serial.Serial(a.port, a.baud, timeout=0.05)


def run(cmd, timeout=60):
    s.reset_input_buffer()
    s.write(cmd.encode() + b"\r")
    buf, end = b"", time.time() + timeout
    while time.time() < end:
        buf += s.read(1 << 16)
        if buf.endswith(PROMPT):
            return buf
    raise TimeoutError(f"{cmd}: нет приглашения; хвост: {buf[-200:]!r}")


if not a.no_read:
    print(run("sf probe 0").decode(errors="replace"))
    print(run(f"sf read {RAM:#x} 0 {a.size:#x}", timeout=120).decode(errors="replace"))
total = CRC.search(run(f"crc32 {RAM:#x} {a.size:#x}", timeout=120)).group(1).decode()
print(f"crc32 всего флеша (U-Boot): {total}")

t0 = time.time()
with open(out, "r+b") as f:
    for off in range(0, a.size, a.chunk):
        if off in done:
            continue
        addr = RAM + off
        for attempt in range(5):
            want = CRC.search(run(f"crc32 {addr:#x} {a.chunk:#x}")).group(1).decode()
            # пустые куски (всё 0xFF или 0x00) узнаём по crc и не гоняем через md — консоль всего 115200
            fill = next((bytes([b]) * a.chunk for b in (0xFF, 0x00)
                         if f"{zlib.crc32(bytes([b]) * a.chunk):08x}" == want), None)
            if fill:
                data = bytearray(fill)
                break
            data = bytearray()
            text = run(f"md.b {addr:#x} {a.chunk:#x}", timeout=a.chunk * 6 * 10 / a.baud + 30)
            exp = addr
            for m in LINE.finditer(text):
                if int(m.group(1), 16) != exp:
                    break
                row = bytes.fromhex(m.group(2).decode())
                data += row
                exp += len(row)
            got = f"{zlib.crc32(data):08x}"
            if len(data) == a.chunk and got == want:
                break
            print(f"  {off:#08x}: повтор ({len(data)} байт, crc {got} != {want})")
        else:
            raise SystemExit(f"кусок {off:#x} не читается — остановка")
        f.seek(off)
        f.write(data)
        f.flush()
        done.add(off)
        with open(done_file, "a") as d:
            d.write(f"{off:x}\n")
        n = len(done) * a.chunk
        rate = (n - 0) / max(time.time() - t0, 1)
        print(f"{off:#08x} ok  {n * 100 // a.size}%  ~{(a.size - n) / max(rate, 1) / 60:.0f} мин", flush=True)

final = f"{zlib.crc32(out.read_bytes()):08x}"
print(f"файл crc32 {final}, U-Boot {total}: {'СОВПАДАЕТ' if final == total else 'НЕ СОВПАДАЕТ'}")
