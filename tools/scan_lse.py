#!/usr/bin/env python3
"""Scan arm64 code for ARMv8.1 LSE atomics (LDADD/LDCLR/LDEOR/LDSET/LDSMAX/... , SWP, CAS, CASP).

Cortex-A72 (Mi Pad 3) is ARMv8.0 and has no LSE; an LSE instruction executed there is an illegal instruction.
Input can be: a thin or fat Mach-O (scans the instruction sections of the arm64 slice), a dyld shared cache file
(scans its executable mappings; pass every sub-cache file), or any raw arm64 binary (--raw: every aligned word).

  python tools/scan_lse.py dyld_shared_cache_arm64 dyld_shared_cache_arm64.01 ...
  python tools/scan_lse.py libsystem_c.dylib
  python tools/scan_lse.py --raw out/Image

A folder is scanned recursively (use it for dylibs extracted with `ipsw dyld extract`: exact instruction sections, no
string false positives). A whole dyld cache works too but its executable mappings also hold strings and constants:
four-printable-ASCII-byte words are filtered, the rest can still produce a few false hits, so check suspicious
addresses with a disassembler.

Limits: data embedded in code can look like an instruction (rare); finding LSE code does not mean it runs on an
unsupported CPU, because Apple code may pick it at runtime from hw.optional.armv8_1_atomics (U: not verified for 16.6.1).
"""
import argparse, struct, sys

LSE = [  # (name, mask, value)
    ("LD<op>/ST<op>/SWP", 0x3F200C00, 0x38200000),   # atomic memory operations
    ("CAS/CASA/CASL/CASAL", 0x3FA07C00, 0x08A07C00),
    ("CASP", 0xBFA07C00, 0x08207C00),
]


def is_ldapr(w):  # LDAPR* share the atomic-op encoding class (o3=1, opc=100): ARMv8.3, not LSE
    return (w & 0x3F20FC00) == 0x3820C000


def classify(w):
    for name, m, v in LSE:
        if (w & m) == v and not (name.startswith("LD<") and is_ldapr(w)):
            return name
    return None


def scan_words(buf, start, end, base_addr, hits, counts):
    start += (-start) % 4
    end -= (end - start) % 4
    for off in range(start, end, 4):
        w = struct.unpack_from("<I", buf, off)[0]
        if (w & 0x08000000) == 0:   # cheap reject: all LSE encodings have bit 27 set
            continue
        n = classify(w)
        if n and all(0x20 <= b < 0x7F for b in struct.pack("<I", w)):
            n = None   # four printable ASCII bytes: a string, not an instruction
        if n:
            counts[n] = counts.get(n, 0) + 1
            hits.append((base_addr + (off - start), off, w, n))


def ranges_for(buf, raw):
    """Return list of (file_start, file_end, vmaddr_of_start, label)."""
    if raw:
        return [(0, len(buf), 0, "raw")]
    if buf[:7] == b"dyld_v1":
        mo, mc = struct.unpack_from("<II", buf, 0x10)
        out = []
        for i in range(mc):
            addr, size, foff, maxp, initp = struct.unpack_from("<QQQII", buf, mo + i * 32)
            if initp & 4:
                out.append((foff, foff + size, addr, "dyld exec mapping %d" % i))
        if not out:
            sys.exit("dyld cache without executable mappings (sub-cache with data only?)")
        return out
    magic = struct.unpack_from("<I", buf, 0)[0]
    base = 0
    if struct.unpack_from(">I", buf, 0)[0] == 0xCAFEBABE:       # fat
        n = struct.unpack_from(">I", buf, 4)[0]
        pick = None
        for i in range(n):
            ct, cs, off, size, al = struct.unpack_from(">iiIII", buf, 8 + 20 * i)
            if ct == 0x0100000C:
                pick = (off, size)
                if (cs & 0xFFFFFF) == 2:      # arm64e preferred if present
                    break
        if not pick:
            sys.exit("no arm64 slice in fat binary")
        base = pick[0]
        magic = struct.unpack_from("<I", buf, base)[0]
    if magic != 0xFEEDFACF:
        sys.exit("not a 64-bit Mach-O / dyld cache (use --raw for flat binaries)")
    ncmds = struct.unpack_from("<I", buf, base + 16)[0]
    p = base + 32
    out = []
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", buf, p)
        if cmd == 0x19:
            nsects = struct.unpack_from("<I", buf, p + 64)[0]
            q = p + 72
            for _ in range(nsects):
                sect = buf[q:q + 16].split(b"\0")[0].decode()
                addr, ssize, off, _a, _r, _n, flags = struct.unpack_from("<QQIIIII", buf, q + 32)
                if flags & 0x80000400:        # pure/some instructions
                    out.append((base + off, base + off + ssize, addr, sect))
                q += 80
        p += size
    if not out:
        sys.exit("no instruction sections found")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--raw", action="store_true")
    ap.add_argument("--top", type=int, default=10)
    a = ap.parse_args()
    import os
    paths = []
    for f in a.files:
        if os.path.isdir(f):
            for d, _, names in os.walk(f):
                paths += [os.path.join(d, n) for n in sorted(names)]
        else:
            paths.append(f)
    total = {}
    skipped = 0
    scanned_files = 0
    for f in paths:
        buf = open(f, "rb").read()
        if os.path.isdir(f) or (not a.raw and len(buf) < 32):
            continue
        if not a.raw and not (buf[:7] == b"dyld_v1" or struct.unpack_from("<I", buf, 0)[0] == 0xFEEDFACF
                              or struct.unpack_from(">I", buf, 0)[0] == 0xCAFEBABE):
            skipped += 1      # not a Mach-O / dyld cache (e.g. a text file in the folder)
            continue
        scanned_files += 1
        hits, counts = [], {}
        scanned = 0
        for s, e, addr, label in ranges_for(buf, a.raw):
            scan_words(buf, s, e, addr, hits, counts)
            scanned += e - s
        print("%s: scanned %.1f MB of code, LSE words: %d %s" % (f, scanned / 1e6, len(hits), counts or ""))
        for addr, off, w, n in hits[:a.top]:
            print("   vm %#x  file %#x  %08x  %s" % (addr, off, w, n))
        for k, v in counts.items():
            total[k] = total.get(k, 0) + v
    n = sum(total.values())
    if scanned_files == 0:
        print("\nNOTHING WAS SCANNED (%d files skipped: not Mach-O / dyld cache). Use --raw for flat binaries." % skipped)
        sys.exit(3)
    if skipped:
        print("\n(%d non-Mach-O files skipped)" % skipped)
    print("\nTOTAL LSE instruction words: %d %s" % (n, total or ""))
    if n == 0:
        print("VERDICT: none found in the scanned code (ARMv8.0 safe for these files).")
    else:
        print("VERDICT: LSE present. On A72 this is only OK if it never executes (runtime-selected) or gets patched. Needs a closer look.")
    sys.exit(0 if n == 0 else 2)


if __name__ == "__main__":
    main()
