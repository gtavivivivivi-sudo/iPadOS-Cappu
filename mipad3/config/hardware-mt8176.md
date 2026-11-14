# Mi Pad 3 (чип и экран проверены по спецификациям, остальное из памяти)

- SoC: MediaTek MT8176 (2x Cortex-A72 + 4x Cortex-A53, PowerVR GX6250), 4 ГБ ОЗУ, 64 ГБ eMMC, 7,9" 2048x1536, без сотовой связи (проверено по спецификациям).
- Родственный MT8173 есть в mainline Linux (arch/arm64/boot/dts/mediatek/mt8173.dtsi): оттуда брать
  адреса UART, контроллера прерываний (GIC), таймера и eMMC (MSDC). Конкретные адреса не выписываю: из памяти можно ошибиться.
- Хранилище eMMC (в ios-sweet UFS): нужен драйвер MSDC.
- Загрузка: preloader + LK, не Qualcomm ABL. fastboot есть, если загрузчик разблокирован.
- ISA: ARMv8.0 (нет LSE, нет PAC). Брать только arm64, не arm64e.
- UART для отладки: искать на плате, без него первая загрузка вслепую.

## Из исходников ядра (MiCode/Xiaomi_Kernel_OpenSource, ветка cappu-n-oss), сверено 2026-11-12
Плата: arch/arm64/boot/dts/xiaomi8176_tb_c9_n.dts (+ mt8173_plus.dtsi, mt8173.dtsi). Defconfig: arch/arm64/configs/xiaomi8176_tb_c9_n_defconfig.
- Прерывания: ARM GIC-400 (это GICv2, не GICv3). Distributor 0x10221000, CPU if 0x10222000, hyp 0x10224000, vcpu 0x10226000. В ios-sweet (Snapdragon) стоит GICv3, нужен драйвер GICv2.
- Таймер: arm,armv8-timer, PPI 13, 14, 11, 10.
- UART0: 0x11002000 (MTK UART), IRQ SPI 83, clock 26 MHz, GPIO rx 113 / tx 114. Консоль ядра Android: ttyMT0 921600n1.
- eMMC: mmc0 0x11230000, IRQ SPI 71, HS200/HS400 (MSDC, не UFS).
- RAM: memory@40000000 размер 0x80000000 (2 GB) в dts. В железе 4 GB, как расширяется (LK?) НЕ проверено.
- Резервы: 0x44400000 (0x80000 ram_console), 0x444f0000 (0x10000), 0x5ffff000 (0x2000).
- Экран: 1536x2048 (CONFIG_LCM_WIDTH/HEIGHT), драйвер MTK_FB; адрес framebuffer LK передаёт в DTB: /chosen/atag,videolfb (см. framebuffer-mt8176.md).
- Загрузка: PSCI через smc; ядро Android с appended DTB; бутлоадер MediaTek LK.
- Ядра в dts: 4x cortex-a53 (0x000-0x003) + 2x cortex-a57 (0x100, 0x101). По спекам A72. Реальный MIDR не снимали, проверить.
