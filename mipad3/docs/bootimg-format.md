# Формат boot-образа Mi Pad 3 (по twrp.img с 4PDA, sha256 6d4eaa92...b171)

Разобрано 2026-11-13. (V) = видно в файле, (U) = не проверено на планшете.

- (V) Стандартный Android boot header v0, `ANDROID!`, page size 2048.
- (V) kernel_addr 0x40080000 (DRAM base 0x40000000 + 0x80000), ramdisk_addr 0x49000000, second 0x40f78000, tags 0x4e000000.
- (V) cmdline: `bootopt=64S3,32N2,64N2 androidboot.selinux=permissive buildvariant=eng`.
  (U) `bootopt` читается так: 64-bit ATF на EL3 (64S3), ядро 64N2 = 64-bit, non-secure, EL2. Если так, ядро стартует на EL2, и `shim/start.S` уже умеет спускаться на EL1.
- (V) Ядро = gzip(Image) + приклеенный DTB (Image.gz-dtb). Без 512-байтных MTK-заголовков ни на ядре, ни на ramdisk. Ramdisk = gzip cpio.
- (V) Ядро внутри: Linux 3.18.35 (aarch64, сборка 2017-04-06), text_offset 0x80000, image_size 0x121a000.
- (V) DTB: `compatible = "mediatek,xiaomi8176_tb_c9_n", "mediatek,mt8173"`. Это скомпилированный `xiaomi8176_tb_c9_n.dts` из исходников cappu: GIC-400 по 0x10221000 и 0x10222000, memory@40000000 размером 0x80000000 (2 ГБ), узел /chosen пустой (его заполняет LK во время загрузки), reserved-memory pstore 0x44000000, ram_console 0x44400000.
- (U) Что LK заменит размер памяти на реальные 4 ГБ и добавит /chosen/atag,videolfb в DTB нашего образа. Узнаем из первого запуска.

## Сборка нашего образа
`python3 tools/mkboot_mt8176.py --ref twrp.img --shim shim/mt8176/out/Image -o m1-boot.img [--raw]`
Параметры и DTB берутся из `--ref`, ядро заменяется нашим шимом, ramdisk пустой. Только для `fastboot boot`, НИКОГДА не прошивать в boot/recovery.
Основной вариант gzip (как у рабочего образа), `--raw` запасной, если LK не примет gzip (U).

## Сверка по трём образам (2026-11-13)
Сравнены три TWRP для cappu: `twrp.img`, `twrp-3_1_0-cappu_b4.img`, `twrp-3_2_3-0-cappu-20180906-Kirhe.img`.
- (V) У всех троих одинаковый контейнер: page 2048, kernel 0x40080000, ramdisk 0x49000000, tags 0x4e000000, cmdline с `bootopt=64S3,32N2,64N2`, gzip-ядро + приклеенный DTB, без MTK-заголовков. Формат подтверждён тремя независимыми сборками.
- (V) `twrp.img` и `b4` содержат одно и то же ядро 3.18.35 (сборка Xiaomi 2017-04-06) и побайтово одинаковый DTB.
- (V) `Kirhe 3.2.3`: другое ядро, Linux 3.18.121-YAEL-kernel (сборщик goayandi@universal, GCC 7.3, ник совпадает с владельцем зеркала исходников из NOTES). DTB почти тот же: убран узел pstore-reserved-memory@44000000, один флаг tpd-filter-enable. GIC, memory (2 ГБ в DTB) и compatible те же.
- Для `--ref` подходит любой из трёх. По умолчанию берём `twrp.img` (ядро ближе всего к стоковому).
