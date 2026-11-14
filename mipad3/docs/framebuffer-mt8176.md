# Framebuffer на MT8176: откуда брать адрес

Источник: drivers/misc/mediatek/video/mtdummy/mtkfb.c (cappu-n-oss), функции __parse_tag_videolfb*.

(V) LK кладёт данные экрана в device tree, который передаёт ядру, в узел /chosen (глубина 1, имя "chosen" или "chosen@0"):
- свойство "atag,videolfb": структура
  struct { u64 fb_base; u32 islcmfound; u32 fps; u32 vram; char lcmname[]; }
- а также отдельные свойства: atag,videolfb-fb_base_h / -fb_base_l, -islcmfound, -islcm_inited, -fps, -vramSize, -lcmname.
Если fps == 0, ядро Android подставляет 6000 (60.00 Гц).

Вывод: адрес framebuffer НЕ нужно хардкодить. Shim читает /chosen/atag,videolfb из DTB, который отдал LK, и рисует в fb_base. Размер: vram.

(V) Разрешение панели 1536x2048 (CONFIG_LCM_WIDTH/HEIGHT в defconfig).

(U) Не подтверждено, проверить на первой загрузке:
- что LK добавляет /chosen/atag,videolfb в DTB нашего образа (в стоковом Android так, для своего boot-образа нужно проверить);
- формат пикселя и stride (вероятно 32 bit, строка = ширина*4, но в этих файлах не найдено);
- что LK не гасит дисплей перед передачей управления.

Как это помогает без UART: первая отладка идёт текстом прямо в framebuffer (аналог патча 0003 в ios-sweet).
