#!/usr/bin/env python3
"""Pack the MT8176 shim into an Android boot.img that matches a known-good Mi Pad 3 image.

Takes header parameters, cmdline and the appended DTB from a reference image (the TWRP/boot
image of the tablet, `--ref`), replaces the kernel with our shim and the ramdisk with a tiny
cpio. Kernel blob = gzip(Image) + DTB, same layout as the reference (Image.gz-dtb).
FOR `fastboot boot` ONLY. Never flash the result to boot/recovery.

  python3 tools/mkboot_mt8176.py --ref twrp.img --shim shim/mt8176/out/Image -o m1-boot.img [--raw]
"""
import argparse, gzip, struct, sys

def pad(b, ps):
    return b + b"\0" * (-len(b) % ps)

def cpio_empty():
    # newc archive holding only the TRAILER!!! entry
    name = b"TRAILER!!!\0"
    hdr = b"070701" + b"".join(b"%08X" % v for v in (0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, len(name), 0))
    d = hdr + name
    d += b"\0" * (-len(d) % 4)
    return d + b"\0" * (-len(d) % 512 or 0)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--shim", required=True)
    ap.add_argument("-o", required=True)
    ap.add_argument("--raw", action="store_true", help="do not gzip the kernel")
    a = ap.parse_args()

    r = open(a.ref, "rb").read()
    if r[:8] != b"ANDROID!":
        sys.exit("ref is not an Android boot image")
    ks, ka, rs, ra, ss, sa, ta, ps, dts, osv = struct.unpack("<10I", r[8:48])
    name, cmd = r[48:64], r[64:576]
    if ss or dts:
        sys.exit("ref has second stage / dt image, not supported")
    kern = r[ps:ps + ks]
    i = kern.rfind(b"\xd0\x0d\xfe\xed")
    if i < 0 or i + struct.unpack(">I", kern[i + 4:i + 8])[0] != len(kern):
        sys.exit("no appended DTB at the end of the reference kernel")
    dtb = kern[i:]

    shim = open(a.shim, "rb").read()
    if shim[0x38:0x3c] != b"ARM\x64":
        sys.exit("shim has no arm64 Image header")
    blob = (shim if a.raw else gzip.compress(shim, 9, mtime=0)) + dtb
    ramdisk = cpio_empty()

    hdr = b"ANDROID!" + struct.pack("<10I", len(blob), ka, len(ramdisk), ra, 0, sa, ta, ps, 0, osv)
    hdr += name + cmd
    hdr += b"\0" * 32          # id (sha) left zero; LK does not check it on the reference image (U)
    hdr = pad(hdr, ps)
    out = hdr + pad(blob, ps) + pad(ramdisk, ps)
    open(a.o, "wb").write(out)
    print("kernel %d (%s) + dtb %d, ramdisk %d, page %d, kaddr %#x, cmdline %r -> %s (%d bytes)"
          % (len(blob), "raw" if a.raw else "gzip", len(dtb), len(ramdisk), ps, ka,
             cmd.rstrip(b"\0").decode(), a.o, len(out)))

main()
