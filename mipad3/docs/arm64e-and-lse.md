# arm64e (PAC) и LSE: что мешает userland на Cortex-A72

## Наш выбор
iPad 7 (A10, iPadOS 16.6.1) это обычный arm64 без PAC, поэтому PAC для нас не проблема. LSE-атомики (ARMv8.1) есть
у A10, но их нет у A72 (ARMv8.0). Проверено в QEMU shim M1: `ISAR0.atomics = 0` на модели A72.
Проверка реального userland на LSE-инструкции ещё не сделана (UNVERIFIED).

## Как Bergamota запускает iOS 18 (arm64e) на Snapdragon 845
По README Bergamota: на iOS 18 все системные бинарники arm64e, а Snapdragon 845 (ARMv8.2) pointer authentication не имеет.
Решение проекта: инструмент **Renegade** переписывает каждый arm64e Mach-O и весь dyld shared cache так,
чтобы они работали на CPU без PAC (в репозитории `tools/renegade/`: pacstrip*, fips_rehmac, сборка root, HFS+).
Ядро там xnu-11215 (поколение iOS 18) с патчами, загрузчик свой (Enxerto, bare-metal).

Следствие для нас:
- Прежний вывод "arm64e-userland на A72 невозможен без эмуляции" был неверным. Статическая переписка работает (по заявлению проекта).
- Если когда-нибудь понадобится iPadOS 17/18 (устройства A12+, например iPad mini 5), этот путь существует.
- Snapdragon 845 имеет ARMv8.2, то есть LSE там есть. Bergamota LSE-проблему не решала. У нас A72 без LSE:
  если в userland есть LSE-инструкции, потребуется переписчик в духе Renegade (LSE -> LL/SC). Это моя гипотеза, не проверена.

## Ближайшая проверка (без планшета)
Скачать IPSW, извлечь dyld shared cache arm64, найти LSE-инструкции (casal, ldadd, swp и т.п.). Если их нет в
горячих путях, проблемы нет. Если есть, оценить объём переписывания, взяв за образец Renegade.

## Результат проверки ядра (2026-11-14)
`tools/scan_lse.py` (проверен на коде clang с `armv8.1-a`: находит те же 5 LSE-инструкций, что и objdump; на `armv8-a` 0) на собранном в Actions `kernel.development.cappu`: **865 LSE-слов** (744 LD<op>/SWP, 117 CAS, 4 CASP; objdump насчитал 877).
Причины: `-march=armv8.2-a+crypto` в `MACHINE_FLAGS_ARM64_CAPPU` (унаследован от Snapdragon-порта, у него ARMv8.2) и два `casa` без защиты в `osfmk/arm/commpage/commpage_asm.s`. `machine_routines_asm.s` уже под `#if __ARM_ARCH_8_2__`.
Исправление: патч `0083` (флаг `-march=armv8-a+crypto` и запасной вариант на `ldaxr/stxr`). Проверено только: запасной вариант ассемблируется под `armv8-a`, а обычный `casa` там отвергается. Полную сборку с новым флагом ещё не гоняли. В CI добавлен шаг "LSE gate": он краснит сборку, если в ядре снова найдутся LSE-инструкции.
Не проверено: есть ли LSE в userland iPadOS 16.6.1 (для этого нужны dylib из IPSW, см. `scan_lse.py` в режиме папки).
