# Чеклист за компом

## 1. Планшет (Android, USB-отладка)
    adb shell getprop ro.board.platform
    adb shell getprop ro.product.board
    adb shell cat /proc/cpuinfo        # флаги: есть ли "atomics"
    adb reboot bootloader              # единственный способ в fastboot без кнопок
    fastboot oem device-info           # статус загрузчика

## 2. Дерево iPad7,11 (теперь: python3 mipad3/tools/fetch_j171ap.py, затем python3 tools/mkadt_mt8176.py out.adt --dump)
    python3 tools/dtfetch.py "<ссылка на IPSW>"            # список плат
    python3 tools/dtfetch.py "<ссылка на IPSW>" j171ap --out ipad7_dt.txt       # buttons + product
Ссылка: https://ipsw.me/install/iPad7,11/20G81/ (прямая ссылка на updates.cdn-apple.com на этой странице).
Берём именно Wi-Fi плату (j171ap), без модема.

## 3. Сверить config/identity.json
Все значения с confidence != verified заменить настоящими из ipad7_dt.txt.

## 4. Образы для корня
Из BuildManifest.plist узнать имена OS.dmg / SystemOS.dmg / AppOS.dmg (у iPad могут отличаться от iPhone).
Собирать по tools/mkiosroot.sh из ios-sweet (Linux, apfs-fuse, hfsprogs; в Docker нужен --privileged).

## 5. Проверки без планшета (добавлено 2026-11-13)
- LSE: найти casal/ldadd/swp в dyld shared cache userland 16.6.1 (arm64e-and-lse.md)
- Компиляция патча 0082 в Actions (смотреть строки с error:)
- GPU: после M1 узнать BVNC GX6250 и сверить со списком Mesa (gpu.md)
