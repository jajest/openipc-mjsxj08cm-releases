#!/bin/sh
# Запись OpenIPC во флеш Xiaomi MJSXJ08CM из OpenIPC, запущенного в ОЗУ с microSD (uart_ramboot.py).
# Положить в корень карты вместе с uImage и rootfs.squashfs.ssc325 (из архива релиза), запустить в консоли UART:
#   sh /mnt/mmcblk0p1/flash-openipc.sh          — проверки, копия флеша (если её нет), запись
#   sh /mnt/mmcblk0p1/flash-openipc.sh --check  — только проверки, ничего не пишет
# Пишет только kernel (mtd1) и rootfs (mtd2), стирает rootfs_data (mtd3) под настройки OpenIPC. boot, config и
# factory не трогает: ядро держит их только для чтения, скрипт это проверяет и без этого не пишет.

D=/mnt/mmcblk0p1
K=$D/uImage
R=$D/rootfs.squashfs.ssc325
COPY=$D/flash-stock.bin

stop() {
	echo
	echo "СТОП: $*"
	echo "Во флеш ничего не записано дальше этого места."
	exit 1
}

echo "1. Проверки"
grep -q 'root=/dev/ram0' /proc/cmdline || stop "система запущена не из ОЗУ (нужна загрузка с карты, root=/dev/ram0)"
[ -f "$K" ] || stop "нет $K (uImage.ssc325 из архива, переименованный)"
[ -f "$R" ] || stop "нет $R (из архива релиза)"
# mtd: имя, размер, можно ли писать
for p in "0 boot 327680 ro" "1 kernel 2097152 rw" "2 rootfs 7733248 rw" "3 rootfs_data 6488064 rw" \
	"4 config 65536 ro" "5 factory 65536 ro"; do
	set -- $p
	name=$(cat /sys/class/mtd/mtd$1/name)
	size=$(cat /sys/class/mtd/mtd$1/size)
	flags=$(cat /sys/class/mtd/mtd$1/flags)
	[ "$name" = "$2" ] && [ "$size" = "$3" ] || stop "mtd$1: $name $size, ожидалось $2 $3 — разметка не та"
	if [ "$4" = ro ] && [ $((flags & 0x400)) -ne 0 ]; then
		stop "mtd$1 ($2) доступен на запись — должен быть только на чтение"
	fi
	echo "   mtd$1 $2 $3 $4"
done
ks=$(stat -c %s "$K")
rs=$(stat -c %s "$R")
[ "$ks" -le 2097152 ] || stop "uImage ($ks байт) больше раздела kernel"
[ "$rs" -le 7733248 ] || stop "rootfs ($rs байт) больше раздела rootfs"
echo "   uImage $ks байт, rootfs $rs байт — помещаются"

if [ ! -f "$COPY" ]; then
	echo "2. Копия флеша -> $COPY (16 МиБ, около минуты)"
	cat /dev/mtd0 /dev/mtd1 /dev/mtd2 /dev/mtd3 /dev/mtd4 /dev/mtd5 > "$COPY" && sync || stop "не удалось записать копию на карту"
	[ "$(stat -c %s "$COPY")" = 16777216 ] || stop "копия не 16777216 байт"
	a=$(sha256sum "$COPY" | cut -d' ' -f1)
	b=$(cat /dev/mtd0 /dev/mtd1 /dev/mtd2 /dev/mtd3 /dev/mtd4 /dev/mtd5 | sha256sum | cut -d' ' -f1)
	[ "$a" = "$b" ] || stop "два чтения флеша не совпали — флеш читается нестабильно"
	echo "   готово, sha256 $a (два чтения совпали). Перенесите копию с карты на компьютер и храните."
else
	echo "2. Копия флеша уже есть: $COPY"
	# boot/config/factory не пишутся никогда — на флеше они обязаны совпадать с копией (значит, смещения верны)
	for p in "0 0 5" "4 254 1" "5 255 1"; do
		set -- $p
		a=$(dd if="$COPY" bs=65536 skip=$2 count=$3 2>/dev/null | md5sum | cut -d' ' -f1)
		b=$(md5sum < /dev/mtd$1 | cut -d' ' -f1)
		[ "$a" = "$b" ] || stop "mtd$1 не совпадает с копией — копия от другой камеры или разметка не та"
	done
	echo "   boot, config, factory совпадают с копией"
fi

[ "$1" = --check ] && { echo; echo "--check: всё готово к записи, ничего не записано."; exit 0; }

n=3
for p in "1 $K" "2 $R"; do
	set -- $p
	size=$(stat -c %s "$2")
	want=$(md5sum < "$2" | cut -d' ' -f1)
	echo "$n. $(basename "$2") -> /dev/mtd$1"
	# head -c, а не dd bs=<мегабайты>: при 40 МБ свободной памяти dd с большим буфером убивает OOM-killer
	if [ "$(head -c "$size" /dev/mtd$1 | md5sum | cut -d' ' -f1)" = "$want" ]; then
		echo "   уже записано — пропуск"
	else
		flash_eraseall /dev/mtd$1 > /dev/null && flashcp "$2" /dev/mtd$1 || stop "ошибка записи mtd$1"
		[ "$(head -c "$size" /dev/mtd$1 | md5sum | cut -d' ' -f1)" = "$want" ] || stop "mtd$1: прочитанное не совпадает с файлом — запустите скрипт ещё раз"
		echo "   записано и проверено чтением"
	fi
	n=$((n + 1))
done

echo "$n. rootfs_data -> чистый jffs2 под настройки OpenIPC (данные Mi Home остаются только в копии)"
flash_eraseall -j /dev/mtd3 > /dev/null || stop "ошибка стирания mtd3"
echo "   стёрт"
sync
echo
echo "Готово. Удалите с карты uImage и uInitrd (или выньте карту), выключите и включите камеру:"
echo "она загрузится в OpenIPC с флеша через заводской U-Boot."
