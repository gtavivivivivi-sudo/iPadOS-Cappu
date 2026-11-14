# GPU-ускорение для Mi Pad 3 (PowerVR GX6250): ВОЗМОЖНОЕ РЕШЕНИЕ

Статус: идея, ничего не запускалось и не писалось. Цель Release: любое ускорение (Metal не обязателен).
Исходные заметки автора лежат в `ref/gpu-notes-user.txt` (не удалять).

## Откуда идея
Bergamota (iOS 18 на Poco F1) и ios-sweet-ветки с Adreno показывают схему: открытый драйвер Mesa в userland +
собственный драйвер GPU в ядре XNU. Для Adreno это Mesa freedreno, который отдаёт OpenGL ES рендереру
CoreAnimation (так описано в README связанных проектов; механизм сам я не разбирал). Прошивка GPU кладётся в ADT
(в Bergamota для этого есть `tools/adt-gpufw.py`). Дальше поверх GL заходит Metal (путь Asahi, "Tales of the M1 GPU").

## Что известно про GX6250 (проверено по Mesa docs, Phoronix, mesa-dev, LKML, ноябрь 2026)
- У Imagination есть открытый стек для Rogue: Vulkan-драйвер `powervr` в Mesa (`-Dvulkan-drivers=imagination`)
  и ядерный драйвер `drm/imagination`. GX6250 был одной из трёх первых целей, разработку вели на Chromebook Acer R13
  с MT8173, то есть на родственном SoC.
- Mesa: GX6250 с BVNC `4.40.2.51` значится "partially supported, not under active development" (Vulkan 1.2).
  GX6250 с BVNC `4.45.2.58` в списке неподдерживаемых. BVNC GPU в нашем MT8176 неизвестен: читается из регистров GPU.
- Нужна бинарная прошивка Rogue (репозиторий linux-firmware Imagination). Её надо достать и положить в образ.
- Для OpenGL ES через zink на GX6250 в обсуждениях приходилось ставить `PVR_I_WANT_A_BROKEN_VULKAN_DRIVER`:
  Vulkan неполный, результат не гарантирован.

## Возможный путь
1. Узнать BVNC: прочитать регистры GPU (shim/XNU), сравнить со списком Mesa.
2. Достать прошивку под этот BVNC.
3. Драйвер ядра под XNU: порт логики `drm/imagination` (Linux DRM-слой там не нужен, но надо MMU/VA, подачу команд,
   управление питанием и тактированием из dts cappu). Это основная работа.
4. Mesa (`powervr` + zink или прямой GLES) в userland iOS и подмена GL-рендерера CoreAnimation. Как именно сделано в Bergamota, надо читать их `docs/` (GPU research).
5. Metal поверх: очень далеко, для Release не нужен.

## Риски
- Неполная поддержка именно нашего BVNC, "не развивается активно".
- Объём драйвера ядра (Linux-версия была ~33,6k строк на момент v3, актуальный размер не проверен).
- Сначала должен работать CPU-рендер (Beta), иначе отлаживать GPU не на чем.

## Ссылки
- https://docs.mesa3d.org/drivers/powervr.html
- https://www.phoronix.com/news/PowerVR-DRM-Driver-v3
- https://lists.freedesktop.org/archives/mesa-dev/2022-March/225699.html
- https://github.com/ry-diffusion/Bergamota (папка docs/, GPU research)
- https://github.com/dipa-studio/ios-sweet, https://github.com/joranv1/ios-sailfish
- https://asahilinux.org/2022/11/tales-of-the-m1-gpu/
- OrangeFox Recovery: для нас пока не нужен, у cappu есть TWRP
