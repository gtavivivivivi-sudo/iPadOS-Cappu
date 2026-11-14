# iPadOS-Cappu

Порт iPadOS 16.6.1 на Xiaomi Mi Pad 3 (`cappu`, MediaTek MT8176). Форк [dipa-studio/ios-sweet](https://github.com/dipa-studio/ios-sweet) (MIT): тот же подход (свой загрузочный shim + пропатченное открытое ядро XNU 8796 + немодифицированный userland Apple из IPSW), но под другой планшет.

**Стадия: Alpha.** На самом планшете пока ничего не запускалось. Ниже только то, что реально проверено, а непроверенное и гипотезы помечены прямо.

## Что сейчас можно запустить

Это диагностический shim M1, а не iPadOS. Он печатает на экран/UART сведения о процессоре (MIDR, поддержка LSE-атомиков, EL), содержимое `/chosen` и `/memory` из DTB, поднимает GICv2 и проверяет прерывание таймера.

```
python cappu.py doctor                # какие инструменты есть
python cappu.py check                 # проверка репозитория и генератора device tree
python cappu.py qemu                  # собрать и запустить M1 в QEMU (Cortex-A72, GICv2)
python cappu.py image --ref twrp.img  # собрать M1 для планшета, образы в dist/
python cappu.py report                # собрать данные о планшете в report-*.txt (только чтение)
python cappu.py tablet                # пошаговый `fastboot boot` на планшет (ничего не прошивает)
```

Нужны: Python 3, LLVM (`clang`, `ld.lld`, `llvm-objcopy`), для `qemu` ещё `qemu-system-aarch64`, для `tablet` ещё `adb` и `fastboot` (platform-tools). `--ref` это любой образ recovery/boot для Mi Pad 3 (например TWRP), нужен только как шаблон формата.

Готовые образы в `dist/`: `m1-boot.img` (ядро gzip, как у рабочих TWRP) и `m1-boot-raw.img` (запасной). **Их можно только грузить через `fastboot boot`, прошивать нельзя.**

## Статус

| Область | Состояние |
| --- | --- |
| M1 shim в QEMU (A72, GICv2, старт с EL1 и с EL2) | Работает: `RESULT: PASS`, таймер INTID 27 даёт прерывания |
| M1 shim на планшете | Образы собраны, **не запускались** |
| Device tree iPad7,11 (J171AP) | Реальное дерево из IPSW 20G81, `home-button-type = 2` (жесты) добавляет генератор |
| Генератор device tree MT8176 (`tools/mkadt_mt8176.py`) | Выдаёт дерево: 4x A53 + 2x A72, GIC-400, msdc0, 1536x2048. Карта памяти и framebuffer **не проверены** |
| Формат boot-образа | Разобран по трём TWRP для cappu, совпадает во всех (`mipad3/docs/bootimg-format.md`) |
| Сборка XNU в GitHub Actions (macos-15) | Проходит, ядро xnu-8796.141.3 собирается. Это ядро ещё со Snapdragon-кодом и на планшете не заработает |
| GICv2 в XNU (патч `0082`) | Применяется к дереву после 0081 и собирается в GitHub Actions (в собранном ядре есть код CAPPU GIC), на железе не запускался |
| Ядро без LSE (патч `0083`, `tools/scan_lse.py`) | Нашли: собранное ядро содержало 865 LSE-инструкций, а у A72 их нет. Патч написан, полную сборку ещё не проверяли (CI проверит сам) |
| Остальные 81 патч | Апстримные, под Snapdragon SM7150, под MT8176 не адаптированы |
| Корневая ФС из IPSW | Не собрана (`tools/mkiosroot.sh`) |
| LSE-атомики в userland 16.6.1 на A72 | **Не проверено**, возможный блокер (`mipad3/docs/arm64e-and-lse.md`) |
| XNU на планшете, userland, тач, экран, драйверы UART/eMMC | Не сделаны |
| GPU, Wi-Fi, звук | Не начаты |

## Что неизвестно (проверится первым запуском)

Заблокирован ли загрузчик, принимает ли LK `fastboot boot`, добавляет ли LK в наш DTB `/chosen/atag,videolfb` и реальный объём RAM (в dts 2 ГБ, в железе 4 ГБ), формат пикселя и stride framebuffer, реальный MIDR ядер (в dts A57, по спецификации A72), тактируется ли UART0 `0x11002000`, BVNC GPU.

## Возможные решения (гипотезы, не проверены)

**GPU-ускорение (цель Release).** Возможное решение: открытый стек Imagination для Rogue. GX6250 был одной из первых целей драйвера `powervr` в Mesa (Vulkan) и ядерного `drm/imagination`, разработку вели на MT8173, родственном нашему SoC. Идея: Mesa PowerVR Vulkan + zink для OpenGL ES, затем собственный драйвер ядра под XNU и подмена GL-рендерера CoreAnimation, по схеме Bergamota для Adreno. Оговорки: в Mesa GX6250 (BVNC 4.40.2.51) "partially supported, not under active development", вариант 4.45.2.58 не поддерживается, наш BVNC неизвестен; нужна бинарная прошивка; драйвер ядра это основная работа. Подробности и ссылки: `mipad3/docs/gpu.md`.

**arm64e и LSE.** Bergamota запускает iOS 18 (arm64e) на Snapdragon 845 без PAC, переписывая все arm64e Mach-O и dyld shared cache инструментом Renegade. Для нас это открывает путь к iPadOS 17/18 (A12+) и даёт образец, как переписать LSE-атомики под A72 (если они окажутся в userland 16.6.1). Подробности: `mipad3/docs/arm64e-and-lse.md`.

## Цели

- **Alpha (сейчас):** подготовка без железа: M1 в QEMU, формат образа, device tree, патч GICv2, сборка в Actions.
- **Beta:** первый запуск на планшете: shim, затем XNU, первая строка на экране, затем launchd и SpringBoard на CPU-рендеринге.
- **Release (стабильная ветка):** любое GPU-ускорение (Metal не обязателен), все 6 ядер, вся RAM (4 ГБ), OTA через собственное приложение (схема A/B), стабильность от 50%.

Подробный чек-лист: `mipad3/docs/roadmap.md`.

## Безопасность

Не прошивай образы из `dist/`. Перед любой записью на планшет нужен бэкап нужных разделов (`preloader`, `lk`, `boot`, `recovery`, `nvram`, `nvdata`, `proinfo`, `seccfg`, `protect1/2`). Правила и неизвестные места: `mipad3/docs/brick-safety.md`. Порт ставится в `userdata` и **стирает данные Android**.

## Карта репозитория

- `cappu.py` запускатор (см. выше); план первого дня с планшетом: `mipad3/docs/TOMORROW.md`
- `shim/mt8176/` M1 shim, `shim/gicv2.h` слой GICv2, `shim/start.S` вход (спуск с EL2 на EL1)
- `xnu/patches/` патчи XNU 8796 (0082 GICv2 для MT8176)
- `tools/mkadt_mt8176.py` device tree MT8176, `tools/mkboot_mt8176.py` упаковка boot-образа
- `mipad3/` документы и данные платы: `config/hardware-mt8176.md`, `docs/` (roadmap, безопасность, формат образа, GICv2, framebuffer, GPU, arm64e и LSE)
- `research/ipsw-ipad7/j171ap.adt` реальное дерево iPad7,11
- `NOTES.md` текущее состояние для передачи работы (в начале), ниже дневник автора апстрима
- `docs/UPSTREAM-ios-sweet-README.md` исходный README апстрима (про Redmi Note 10 Pro, не про Mi Pad 3)

## Происхождение

Форк ios-sweet, MIT, (c) 2026 dipa-studio, см. `LICENSE`. Апстрим запускает свой код на Redmi Note 10 Pro; всё, что в апстримном README написано про загрузку до домашнего экрана, относится к нему, а не к Mi Pad 3. Идеи про GPU и arm64e опираются на Bergamota (ry-diffusion).
