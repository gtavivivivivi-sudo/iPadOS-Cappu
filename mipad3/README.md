# mipad3: iPadOS (iPad 7 Wi-Fi, 16.6.1) на Xiaomi Mi Pad 3

Надстройка над ios-sweet (клон этого репо лежит рядом, upstream-файлы не тронуты).
Цель: идентичность iPad7,11 / J171AP + жесты (home-button-type 2) на MT8176.
Статус: проверена только цепочка "достать дерево из IPSW -> собрать device tree с идентичностью iPad"
(на синтетическом IPSW, не на настоящем файле Apple). На железе ничего не запускалось.

## Что есть
- tools/mkadt_ipad7.py        СГЕНЕРИРОВАН из tools/mkadt.py: идентичность J171AP / iPad7,11, display-scale 2
- mipad3/tools/make_mkadt_ipad7.py   генератор (с проверкой замен; запускать после обновления upstream)
- mipad3/tools/fetch_j171ap.py       достаёт j171ap.adt и список DMG из удалённого IPSW (только stdlib)
- mipad3/tools/dtfetch.py            печатает /product и /buttons любой платы из удалённого IPSW
- mipad3/config/identity.json        черновые параметры с уровнем уверенности
- mipad3/config/ipsw_url.txt         ссылка на iPad_10.2_16.6.1_20G81_Restore.ipsw (со страницы ipsw.me)
- mipad3/termux/*.sh                 то же самое для Termux на телефоне + упаковка для переноса на ПК
- mipad3/docs/ref/MobileGestalt.h    справочный заголовок

## Порядок (ПК)
    python3 mipad3/tools/make_mkadt_ipad7.py          # уже сделано, но можно повторить
    python3 mipad3/tools/fetch_j171ap.py              # -> research/ipsw-ipad7/j171ap.adt + список DMG
    python3 tools/mkadt_ipad7.py out.adt --dump       # проверить, что /product с idiom=pad на месте
Если дерево сжато LZFSE и без `pip install lzfse` не читается, скрипт сохранит DeviceTree.j171ap.im4p
и напишет команду для ПК: ipsw img4 im4p extract ... -o research/ipsw-ipad7/j171ap.adt

## Порядок (Termux на телефоне)
    bash mipad3/termux/setup.sh
    bash mipad3/termux/fetch.sh
    termux-setup-storage        # один раз
    bash mipad3/termux/export.sh   # -> Downloads/ipad7_parts.zip, потом по USB на ПК
На ПК распаковать zip в корень репо, он создаст research/ipsw-ipad7/.

## Чего здесь НЕТ (главная работа)
- SoC-слой device tree всё ещё от Snapdragon 732G (cpus, arm-io, GIC, ufs, 'xiaomi,sweet'): нужен порт на MT8176
  (прерывания, таймер, UART, eMMC вместо UFS).
- Корневая ФС: tools/mkiosroot.sh на Linux (apfs-fuse, hfsprogs, в Docker нужен --privileged); имена DMG выведет fetch_j171ap.py.
- Загрузчик MediaTek (preloader/LK) вместо Qualcomm fastboot-пути шима.
- Совместимость юзерленда 16.6.1 с ядром xnu-8796.141.3 и набором команд A72 (ARMv8.0) не проверена.
