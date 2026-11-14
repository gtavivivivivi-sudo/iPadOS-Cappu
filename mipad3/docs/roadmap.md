# Roadmap iPadOS-Cappu
Ветки: main = alpha/beta (нестабильная), release = только проверенное. Отметки: [x] сделано и проверено, [~] написано, но не запускалось, [ ] не начато.

## Alpha (сейчас): подготовка без железа
- [x] Реальный device tree iPad7,11 (J171AP) из IPSW 20G81
- [x] Данные MT8176 из исходников cappu (config/hardware-mt8176.md)
- [x] Генератор device tree MT8176 (tools/mkadt_mt8176.py), параметры памяти и FB отмечены U
- [x] M1 shim проходит в QEMU (Cortex-A72, GICv2, старт с EL1 и EL2)
- [x] Формат boot-образа по трём TWRP, образы M1 в dist/ (только `fastboot boot`)
- [x] Сборка XNU в GitHub Actions на macos-15 (запуск #4 зелёный)
- [x] Патч 0082: GICv2 для MT8176 применяется и собирается в GitHub Actions, подтверждено артефактом xnu-kernel (в бинарнике есть CAPPU GIC: _cappu_gic_ack/eoi/send_sgi); на железе не запускался
- [~] Патч 0083: ядро под ARMv8.0 без LSE. Причина: в собранном ядре 865 LSE-инструкций (A72 бы упал на первой атомарной операции). Патч написан, полную сборку с новым флагом не проверяли, в CI добавлен шаг-проверка
- [ ] Проверка LSE в userland iPadOS 16.6.1 (`tools/scan_lse.py` по dylib из IPSW)
- [ ] Проверка LSE в userland 16.6.1 (arm64e-and-lse.md)
- [ ] M2: чтение eMMC (MSDC), в QEMU не проверить
- [ ] Корневая ФС из трёх DMG (tools/mkiosroot.sh)
- [ ] Бэкап разделов и план восстановления (brick-safety.md)

## Beta: первый запуск на планшете
- [ ] M1 на планшете: принимает ли LK `fastboot boot`, реальная RAM, FB, CNTFRQ, MIDR
- [ ] Подставить реальные значения в device tree (убрать U)
- [ ] Вывод XNU в framebuffer (UART без проводов недоступен)
- [ ] 81 апстримный патч под MT8176 (таймер, UART, eMMC, framebuffer, тач)
- [ ] launchd, SpringBoard на CPU-рендере, тач, жесты

## Release (stable)
- [ ] Возможное решение для GPU: PowerVR Vulkan + zink, драйвер ядра под XNU (gpu.md). Достаточно любого ускорения
- [ ] Все 6 ядер (PSCI smc, два кластера: нужен MAX_CPU_CLUSTERS=2)
- [ ] Вся RAM (4 ГБ; в dts 2 ГБ)
- [ ] OTA через своё приложение (A/B)
- [ ] Стабильность >= 50% (метрику договорить)
- [ ] Полноценный Setup Assistant с принудительной/обойдённой активацией Apple (реальная проверка iCloud, скорее всего, не пройдёт — устройство не привязано к настоящему iPhone)
- [ ] Все базовые функции, которые должны быть у любого планшета (общая юзабельность)

## Идеи на потом
- Отладка через USB virtual COM (SSUSB mtu3 на 0x11270000), после результатов M1
- iPadOS 17/18 через переписку arm64e в стиле Renegade (arm64e-and-lse.md)
