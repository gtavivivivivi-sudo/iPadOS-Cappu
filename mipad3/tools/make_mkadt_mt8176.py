#!/usr/bin/env python3
"""Derive tools/mkadt_mt8176.py from tools/mkadt.py: iPad 7 Wi-Fi identity + MT8176 SoC layer.

Replaces mipad3/tools/make_mkadt_ipad7.py, which broke when mkadt.py was renamed sweet->cappu
(its 'xiaomi,sweet' match no longer exists and tools/mkadt_ipad7.py still emits sweet-* node names
that the cappu-* kernel patches do not look for). Every replacement is asserted.

    python3 mipad3/tools/make_mkadt_mt8176.py
    python3 tools/mkadt_mt8176.py out.adt --dump [--qemu] [--phys-base=0x.. --mem-size=0x.. --fb=0x..]

Values marked U are NOT verified on a Mi Pad 3; replace them with what shim M1 prints from the real DTB.
"""
import os

root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
src = os.path.join(root, "tools", "mkadt.py")
dst = os.path.join(root, "tools", "mkadt_mt8176.py")
text = open(src).read()

REPL = [
    # --- identity: iPad 7 Wi-Fi (J171AP) instead of iPhone X (D22AP)
    ("../research/ipsw-x/d22ap.adt", "../research/ipsw-ipad7/j171ap.adt"),
    ("('display-scale', u32(3)),", "('display-scale', u32(2)),"),
    ("('chip-id', u32(0x8015)),", "('chip-id', u32(0x8010)),  # T8010 (A10 Fusion), same SoC family as iPad 7"),
    ("cstr('D22AP') + cstr('iPhone10,3') + cstr('xiaomi,cappu') + cstr('qcom,sm7150') + cstr('AppleARM')",
     "cstr('J171AP') + cstr('iPad7,11') + cstr('xiaomi,cappu') + cstr('mediatek,mt8176') + cstr('AppleARM')"),
    ("('model', cstr('iPhone10,3')),", "('model', cstr('iPad7,11')),"),
    ("('target-type', cstr('D22')),", "('target-type', cstr('J171')),"),
    ("('target-sub-type', cstr('D22AP')),", "('target-sub-type', cstr('J171AP')),"),
    # --- memory (U): conservative window inside the dts RAM, clear of the reserved ranges
    # 0x44400000/0x444f0000 (ram_console) and 0x5ffff000; real map comes from shim M1 (/memory in LK's DTB)
    ("PHYS_BASE = 0xb0000000", "PHYS_BASE = 0x48000000  # U"),
    ("MEM_SIZE = 0x4d000000", "MEM_SIZE = 0x17000000  # U: 368 MB, ends below 0x5ffff000"),
    # --- SoC bases (V: cappu-n-oss dts, see mipad3/config/hardware-mt8176.md); sizes are U
    ("SOC_BASE = 0x01000000", "SOC_BASE = 0x10000000"),
    ("GICD, GICD_SIZE = 0x17a00000, 0x10000", "GICD, GICD_SIZE = 0x10221000, 0x1000"),
    ("GICR, GICR_SIZE = 0x17a60000, 0x100000", "GICR, GICR_SIZE = 0x10222000, 0x2000  # GIC-400: this is the CPU interface (GICC)"),
    # --- framebuffer (U): LK passes the real address in /chosen/atag,videolfb; 0 = not set, use --fb
    ("FB, FB_SIZE = 0x9c000000, 0x1700000", "FB, FB_SIZE = 0x0, 0xc00000  # U: base from /chosen/atag,videolfb"),
    ("FB_W, FB_H, FB_STRIDE = 1080, 2400, 1080 * 4", "FB_W, FB_H, FB_STRIDE = 1536, 2048, 1536 * 4  # stride U"),
    # --- storage (U): eMMC MSDC instead of UFS; node only records the address for the future driver
    ("UFS, UFS_SIZE = 0x01d84000, 0x3000", "UFS, UFS_SIZE = 0x11230000, 0x1000"),
    # QEMU virt's GIC sits below the phone's SOC_BASE: use a lower /arm-io base there
    ("gicd, gicr, timebase = (QEMU_GICD, QEMU_GICR, QEMU_TIMEBASE) if qemu else (GICD, GICR, TIMEBASE)",
     "gicd, gicr, timebase = (QEMU_GICD, QEMU_GICR, QEMU_TIMEBASE) if qemu else (GICD, GICR, TIMEBASE)\n"
     "    soc_base = 0x08000000 if qemu else SOC_BASE"),
    ("('reg', u64(gicd - SOC_BASE, GICD_SIZE, gicr - SOC_BASE, GICR_SIZE)),",
     "('reg', u64(gicd - soc_base, GICD_SIZE, gicr - soc_base, GICR_SIZE)),"),
    ("('ranges', u64(0, SOC_BASE, 0x100000000 - SOC_BASE)),",
     "('ranges', u64(0, soc_base, 0x100000000 - soc_base)),"),
    # eMMC node renamed so the UFS driver (patch 0028) does not bind to an MSDC address
    ("ufs = node('cappu-ufs', [", "ufs = node('cappu-msdc0', ["),
    ("('compatible', cstr('qcom,ufshc')),", "('compatible', cstr('mediatek,mt8173-mmc')),"),
    # --- timer (U for TIMEBASE: dts value not checked; read CNTFRQ in shim M1 on the tablet)
    ("TIMEBASE = 19200000", "TIMEBASE = 13000000  # U"),
    ("VTIMER_INTID = 19", "VTIMER_INTID = 27  # PPI 11 + 16 (V: dts)"),
    ("QEMU_GICD, QEMU_GICR, QEMU_TIMEBASE = 0x08000000, 0x080a0000, 62500000",
     "QEMU_GICD, QEMU_GICR, QEMU_TIMEBASE = 0x08000000, 0x08010000, 62500000  # virt gic-version=2: GICD, GICC"),
    # --- CPUs: 4x Cortex-A53 (MPIDR 0x000-0x003) + 2x Cortex-A72 (0x100, 0x101; dts says a57, specs say A72)
    ("for core in range(1 if qemu else 8):", "for core in range(1 if qemu else 6):"),
    ("('compatible', cstr('qcom,kryo470') + cstr('ARM,v8')),",
     "('compatible', cstr('arm,cortex-a53' if core < 4 else 'arm,cortex-a72') + cstr('ARM,v8')),"),
    ("('reg', u32(core << 8)),  # actual MPIDR Aff1:Aff0, NOT logical ID",
     "('reg', u32(core if core < 4 else 0x100 + core - 4)),  # actual MPIDR Aff1:Aff0 (U for A72 pair)"),
    ("('clock-frequency', u32(2304000000 if core >= 6 else 1804800000)),",
     "('clock-frequency', u32(2100000000 if core >= 4 else 1700000000)),  # informational, U"),
    # --- GIC node
    ("cstr('arm,gic-v3')", "cstr('arm,gic-400')"),
    # --- display canvas (portrait panel 1536x2048)
    ("('canvas-width', u32(1125)),", "('canvas-width', u32(1536)),"),
    ("('canvas-height', u32(2436)),", "('canvas-height', u32(2048)),"),
    # --- command line overrides for the unknown memory/framebuffer values
    ("if __name__ == '__main__':\n    root = build(",
     "def _args():\n"
     "    for a in sys.argv[2:]:\n"
     "        for opt, name in (('--phys-base=', 'PHYS_BASE'), ('--mem-size=', 'MEM_SIZE'), ('--fb=', 'FB'), ('--fb-size=', 'FB_SIZE')):\n"
     "            if a.startswith(opt):\n"
     "                globals()[name] = int(a[len(opt):], 0)\n"
     "\n\n"
     "if __name__ == '__main__':\n    _args()\n    root = build("),
]
for old, new in REPL:
    n = text.count(old)
    assert n == 1, "expected exactly one match for %r, found %d" % (old, n)
    text = text.replace(old, new)

header = '''# GENERATED by mipad3/tools/make_mkadt_mt8176.py from tools/mkadt.py - do not edit, regenerate.
# iPad 7 Wi-Fi identity (J171AP) + MT8176 SoC layer. Values marked U are unverified on the tablet.
'''
first, _, rest = text.partition("\n")
text = (first + "\n" + header + rest) if first.startswith("#!") else header + text
open(dst, "w").write(text)
os.chmod(dst, 0o755)
print("wrote", dst)
