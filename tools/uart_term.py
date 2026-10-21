"""Простой построчный терминал UART, 115200 (вместо PuTTY/miniterm; miniterm на CP2102 под Windows падает с ошибкой 121).

    python uart_term.py [порт=COM11]

Строка уходит в камеру по Enter. Выход — Ctrl+C. Ввод (в том числе пароль) виден на экране.
"""
import sys
import threading

import serial

port = sys.argv[1] if len(sys.argv) > 1 else "COM11"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
s = serial.Serial(port, 115200, timeout=0.1)


def reader():
    while True:
        data = s.read(4096)
        if data:
            sys.stdout.write(data.decode("utf-8", "replace"))
            sys.stdout.flush()


threading.Thread(target=reader, daemon=True).start()
print(f"{port} открыт. Enter — отправить строку, Ctrl+C — выход.", flush=True)
s.write(b"\r")
try:
    while True:
        s.write(input().encode() + b"\r")
except (KeyboardInterrupt, EOFError):
    pass
finally:
    s.close()
    print("\nпорт закрыт")
