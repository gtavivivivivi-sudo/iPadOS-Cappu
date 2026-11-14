#!/usr/bin/env python3
"""dtfetch.py - read a device tree out of a remote IPSW without downloading it.

Only the Python standard library is needed (Termux: pkg install python).

  python dtfetch.py <ipsw-url>                 list boards inside the IPSW
  python dtfetch.py <ipsw-url> j171ap          print /product and /buttons
  python dtfetch.py <ipsw-url> j171ap --full   print the whole tree
  python dtfetch.py <ipsw-url> j171ap --out ipad7_dt.txt   write to file
"""
import struct
import sys
import zlib
import plistlib
import urllib.request


# ---------- HTTP range reads ----------
def rng(url, start=None, end=None, suffix=None):
    rg = "bytes=-%d" % suffix if suffix is not None else "bytes=%d-%d" % (start, end)
    req = urllib.request.Request(url, headers={"Range": rg})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
        status = r.status
        cr = r.headers.get("Content-Range")
    if status != 206:
        raise SystemExit("server ignored the Range request (status %s)" % status)
    total = int(cr.split("/")[-1]) if cr else None
    return data, total


# ---------- ZIP index (zip64 aware) ----------
def read_index(url):
    tail, total = rng(url, suffix=1 << 20)
    base = total - len(tail)
    i = tail.rfind(b"PK\x05\x06")
    if i < 0:
        raise SystemExit("not a zip: no end-of-central-directory record")
    _, _, _, nent, _, cdsize, cdoff, _ = struct.unpack("<IHHHHIIH", tail[i:i + 22])
    if 0xFFFFFFFF in (cdsize, cdoff) or nent == 0xFFFF:
        j = tail.rfind(b"PK\x06\x07", 0, i)
        if j < 0:
            raise SystemExit("zip64 locator not found")
        _, _, off64, _ = struct.unpack("<IIQI", tail[j:j + 20])
        if off64 >= base:
            rec = tail[off64 - base:off64 - base + 56]
        else:
            rec, _ = rng(url, off64, off64 + 55)
        _, _, _, _, _, _, nent, _, cdsize, cdoff = struct.unpack("<IQHHIIQQQQ", rec)
    cd, _ = rng(url, cdoff, cdoff + cdsize - 1)
    entries = {}
    p = 0
    while p + 46 <= len(cd) and cd[p:p + 4] == b"PK\x01\x02":
        (_, _, _, _, method, _, _, _, csize, usize, nlen, elen, clen,
         _, _, _, lho) = struct.unpack("<I6H3I5H2I", cd[p:p + 46])
        name = cd[p + 46:p + 46 + nlen].decode("utf-8", "replace")
        extra = cd[p + 46 + nlen:p + 46 + nlen + elen]
        q = 0
        while q + 4 <= len(extra):
            eid, esz = struct.unpack("<HH", extra[q:q + 4])
            if eid == 1:
                z = extra[q + 4:q + 4 + esz]
                k = 0
                if usize == 0xFFFFFFFF:
                    usize = struct.unpack("<Q", z[k:k + 8])[0]; k += 8
                if csize == 0xFFFFFFFF:
                    csize = struct.unpack("<Q", z[k:k + 8])[0]; k += 8
                if lho == 0xFFFFFFFF:
                    lho = struct.unpack("<Q", z[k:k + 8])[0]; k += 8
            q += 4 + esz
        entries[name] = (method, csize, lho)
        p += 46 + nlen + elen + clen
    return entries


def read_entry(url, ent):
    method, csize, lho = ent
    hdr, _ = rng(url, lho, lho + 29)
    nlen, elen = struct.unpack("<HH", hdr[26:30])
    data, _ = rng(url, lho + 30 + nlen + elen, lho + 30 + nlen + elen + csize - 1)
    if method == 0:
        return data
    if method == 8:
        return zlib.decompressobj(-15).decompress(data)
    raise SystemExit("unsupported zip method %d" % method)


# ---------- IM4P ----------
def der(b, i):
    tag = b[i]
    ln = b[i + 1]
    i += 2
    if ln & 0x80:
        n = ln & 0x7F
        ln = int.from_bytes(b[i:i + n], "big")
        i += n
    return tag, i, ln


def seq_items(b, start, length):
    items, p, end = [], start, start + length
    while p < end:
        t, cs, cl = der(b, p)
        items.append((t, b[cs:cs + cl], b[p:cs + cl]))
        p = cs + cl
    return items


def im4p_payload(b):
    _, s, l = der(b, 0)
    items = seq_items(b, s, l)
    if items[0][1] == b"IMG4":            # IMG4 wrapper -> take the IM4P inside
        _, s, l = der(items[1][2], 0)
        items = seq_items(items[1][2], s, l)
    if items[0][1] != b"IM4P":
        raise SystemExit("not an IM4P file")
    payload = items[3][1]
    encrypted = len(items) > 4 and items[4][0] == 0x04
    return payload, encrypted


def unpack(payload):
    if payload[:3] == b"bvx":              # LZFSE
        for mod in ("lzfse", "liblzfse"):
            try:
                m = __import__(mod)
                return m.decompress(payload)
            except ImportError:
                continue
        raise SystemExit("payload is LZFSE-compressed: pip install lzfse (or pyliblzfse)")
    return payload


# ---------- device tree ----------
def parse_dt(b, off=0):
    np_, nc = struct.unpack_from("<II", b, off)
    off += 8
    props = []
    for _ in range(np_):
        name = b[off:off + 32].split(b"\0", 1)[0].decode("latin1")
        ln = struct.unpack_from("<I", b, off + 32)[0] & 0x7FFFFFFF
        props.append((name, b[off + 36:off + 36 + ln]))
        off += 36 + ((ln + 3) & ~3)
    kids = []
    for _ in range(nc):
        node, off = parse_dt(b, off)
        kids.append(node)
    return {"props": props, "kids": kids}, off


def node_name(n):
    for k, v in n["props"]:
        if k == "name":
            return v.split(b"\0", 1)[0].decode("latin1")
    return "?"


def fmt(v):
    if v and v[-1] == 0 and all(32 <= c < 127 for c in v[:-1]) and len(v) > 1:
        return '"%s"' % v[:-1].decode()
    if len(v) == 4:
        return "%d (0x%x)" % (struct.unpack("<I", v)[0], struct.unpack("<I", v)[0])
    if len(v) == 8:
        a, c = struct.unpack("<II", v)
        return "%d, %d (0x%x, 0x%x)" % (a, c, a, c)
    return "0x" + v[:24].hex() + ("..." if len(v) > 24 else "")


def dump(n, out, depth=0):
    pad = "  " * depth
    out.append("%s[%s]" % (pad, node_name(n)))
    for k, v in sorted(n["props"]):
        if k != "name":
            out.append("%s  %s = %s" % (pad, k, fmt(v)))
    for c in n["kids"]:
        dump(c, out, depth + 1)


def find(n, name):
    if node_name(n) == name:
        return n
    for c in n["kids"]:
        r = find(c, name)
        if r:
            return r
    return None


# ---------- main ----------
def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    full = "--full" in sys.argv
    outfile = None
    if "--out" in sys.argv:
        outfile = sys.argv[sys.argv.index("--out") + 1]
        a = [x for x in a if x != outfile]
    if not a:
        print(__doc__)
        return
    url = a[0]
    board = a[1].lower() if len(a) > 1 else None

    ents = read_index(url)
    bm = plistlib.loads(read_entry(url, ents["BuildManifest.plist"]))
    boards = {}
    for ident in bm.get("BuildIdentities", []):
        dc = ident.get("Info", {}).get("DeviceClass", "").lower()
        path = ident.get("Manifest", {}).get("DeviceTree", {}).get("Info", {}).get("Path")
        if dc and path:
            boards[dc] = path
    if not board:
        print("Supported products:", ", ".join(bm.get("SupportedProductTypes", [])))
        print("Boards in this IPSW:")
        for dc in sorted(boards):
            print("  ", dc)
        print("\nRun again with a board name, e.g.: python dtfetch.py <url> %s" % next(iter(boards), "j171ap"))
        return
    if board not in boards:
        raise SystemExit("board %r not found. Available: %s" % (board, ", ".join(sorted(boards))))

    blob = read_entry(url, ents[boards[board]])
    payload, encrypted = im4p_payload(blob)
    if encrypted:
        raise SystemExit("this device tree is encrypted (needs a key), cannot read it")
    dt, _ = parse_dt(unpack(payload))

    out = ["# board %s, file %s" % (board, boards[board])]
    root = [(k, v) for k, v in dt["props"] if k in ("model", "target-type", "compatible")]
    for k, v in root:
        out.append("# %s = %s" % (k, fmt(v)))
    if full:
        dump(dt, out)
    else:
        for nm in ("buttons", "product"):
            n = find(dt, nm)
            if n:
                dump(n, out)
            else:
                out.append("[%s] not found" % nm)
    text = "\n".join(out)
    if outfile:
        with open(outfile, "w") as f:
            f.write(text + "\n")
        print("written:", outfile, "(%d lines)" % len(out))
    else:
        print(text)


if __name__ == "__main__":
    main()
