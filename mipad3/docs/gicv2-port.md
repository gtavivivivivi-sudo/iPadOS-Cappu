# GICv2 вместо GICv3: что менять

Причина: у MT8176 GIC-400 (GICv2, регистры по MMIO), а ios-sweet написан под GICv3 Qualcomm (sysreg ICC_*, redistributor).

## Shim (shim/)
- Готово: `shim/gicv2.h` (init distributor и CPU interface, enable, ack/EOI, SGI). Не тестировалось, только проверка синтаксиса.
- Заменить в shim.c: `find_gicr`, `GICR_*`, `icc_sre/ctlr/pmr/bpr/hppir/sgi1r` на вызовы из gicv2.h. `test_gic` и `irq_window` переписать под GICC_IAR/EOIR.
- Адреса: GICD 0x10221000, GICC 0x10222000 (из dts). INTID таймера: virt 27 (PPI 11), phys NS 30 (PPI 14).

## XNU (xnu/patches, патч 0004 и 0017)
- Убрать `HAS_GIC_V3` ветку и константы GICR_*/GICD_CTLR_ARE_NS: их нет в GICv2.
- В `sleh_irq`: чтение IAR через MMIO (GICC_IAR) вместо `ICC_IAR1_EL1`; EOI через GICC_EOIR.
- IPI: запись в GICD_SGIR вместо `ICC_SGI1R_EL1`; маска целевых CPU 8 бит.
- Включение PPI/SGI: банковые GICD_ISENABLER0/IPRIORITYR0 на каждом ядре (не redistributor).
- Device tree (mkadt): узел GIC и interrupt-parent переписать, виртуальный таймер INTID 27 вместо 19 (патч 0017 ставил 19 для Qualcomm).
- Данные GIC-400 брать из dts, адреса не из памяти.

## Неизвестное до первой загрузки
- В каком security state стартует ядро (NS EL1/EL2). От этого зависит, видны ли GICD_IGROUPR и группы прерываний.
- Нужна ли смена endianness/barriers: проверить в логе первого запуска.
