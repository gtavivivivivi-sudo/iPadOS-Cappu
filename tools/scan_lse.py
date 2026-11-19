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


def load_symbols(buf):
    """Defined symbols of a thin 64-bit Mach-O as a sorted list of (vmaddr, name), else []."""
    if len(buf) < 32 or struct.unpack_from("<I", buf, 0)[0] != 0xFEEDFACF:
        return []
    ncmds = struct.unpack_from("<I", buf, 16)[0]
    p = 32
    syms = []
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", buf, p)
        if cmd == 0x2:   # LC_SYMTAB
            symoff, nsyms, stroff, strsize = struct.unpack_from("<IIII", buf, p + 8)
            for i in range(nsyms):
                n_strx, n_type, n_sect, _d, n_value = struct.unpack_from("<IBBHQ", buf, symoff + i * 16)
                if (n_type & 0xE0) or (n_type & 0x0E) != 0x0E or n_value == 0:
                    continue      # debug (stab), undefined or absolute: not a code symbol
                end = buf.find(b"\0", stroff + n_strx, stroff + strsize)
                syms.append((n_value, buf[stroff + n_strx:end].decode("ascii", "replace")))
        p += size
    syms.sort()
    return syms


def symbolize(syms, addr):
    """'name+0xoff' for the closest symbol at or below addr, or '?' without symbols."""
    if not syms:
        return "?"
    import bisect
    i = bisect.bisect_right(syms, (addr, "\U0010ffff")) - 1
    if i < 0:
        return "?"
    return "%s+%#x" % (syms[i][1], addr - syms[i][0])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--raw", action="store_true")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--syms", action="store_true", help="resolve each hit to the nearest symbol (thin Mach-O kernel)")
    ap.add_argument("--allow", action="append", default=[], metavar="SYMBOL",
                     help="a function/symbol name whose hits are KNOWN, checked false positives (literal data that "
                          "happens to match an LSE opcode, not an instruction that ever executes) and should not "
                          "fail the gate. Requires --syms, since this matches on the resolved symbol name, not the "
                          "address. Repeatable. Every use must be justified in a comment next to the call site: this "
                          "flag exists to document one specific, already-investigated false positive (see "
                          "patches/ - K256 in corecrypto's SHA-256 round-constant table), not to silence the gate.")
    a = ap.parse_args()
    if a.allow and not a.syms:
        sys.exit("--allow requires --syms (it matches on resolved symbol names)")
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
        syms = load_symbols(buf) if a.syms else []
        if a.syms and not syms:
            print("   (no symbol table found: use a thin Mach-O kernel, not stripped)")
        for addr, off, w, n in hits[:a.top]:
            where = ("  in " + symbolize(syms, addr)) if a.syms else ""
            print("   vm %#x  file %#x  %08x  %s%s" % (addr, off, w, n, where))
        if a.syms and syms:
            fn = {}
            for addr, _o, _w, _n in hits:
                k = symbolize(syms, addr).split("+")[0]
                fn[k] = fn.get(k, 0) + 1
            print("   hits per function: " + ", ".join("%s=%d" % kv for kv in sorted(fn.items(), key=lambda kv: -kv[1])))
        if a.allow and syms:
            # Only drop a hit from the gate count when it resolves to a symbol on the --allow
            # list - never by address/offset alone, and never when symbols failed to load.
            kept = []
            allowed_n = 0
            for addr, off, w, n in hits:
                fn = symbolize(syms, addr).split("+")[0]
                if fn in a.allow:
                    allowed_n += 1
                else:
                    kept.append((addr, off, w, n))
            if allowed_n:
                print("   (%d hit(s) in --allow'd symbol(s) %s excluded from the gate count - "
                      "still printed above, not hidden)" % (allowed_n, sorted(set(a.allow) & {symbolize(syms, h[0]).split("+")[0] for h in hits})))
            hits = kept
            counts = {}
            for _addr, _off, _w, nm in hits:
                counts[nm] = counts.get(nm, 0) + 1
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
