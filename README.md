# OpenIPC для Xiaomi MJSXJ08CM — релизы

Сборки [OpenIPC](https://github.com/OpenIPC/firmware) для камеры Xiaomi Mi Home Security Camera 360° 1080p
**MJSXJ08CM** (SigmaStar SSC323, датчик JX-F37, Wi-Fi SSW101B). Здесь только готовые архивы для обновления.

## Для чего

`openipc-mjsxj08cm.tgz` — архив для `sysupgrade` (ядро + rootfs) для камер, **на которые OpenIPC уже установлен**
этой сборкой (заводской U-Boot, `init=/linuxrc`, разметка флеша Xiaomi). На камеру с заводской прошивкой Xiaomi
его так не поставить, и типовая сборка OpenIPC с GitHub этой камере не подходит.

Камера берёт последний релиз по адресу из env `upgrade`:

    fw_setenv upgrade https://github.com/jajest/openipc-mjsxj08cm-releases/releases/latest/download/openipc-mjsxj08cm.tgz

## Установка

- Веб-интерфейс: Firmware → «Install» (берёт адрес из `upgrade`) или «Install this file» с этим архивом.
  В «What gets written» → «Advanced options» включить **«Reflash even if the same version»**, иначе сборка той же
  даты не запишется. «Reset config (wipe overlay)» **не включать**.
- Или по SSH: `sysupgrade -k -r -z --force_ver --archive=/tmp/openipc-mjsxj08cm.tgz`.
- **«Automatic updates» не включать** — они ставят типовые сборки OpenIPC.

В образе нет настроек Wi-Fi и паролей: `/etc/wpa_supplicant.conf` и пароль root камера хранит в overlay
(раздел `rootfs_data`), они переживают обновление.
