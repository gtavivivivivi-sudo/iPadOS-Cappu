#!/usr/bin/env python3
"""Fetch the iPad7,11 (J171AP) device tree and the rootfs image list from the remote IPSW.

Works on a PC and in Termux (stdlib only). Writes to research/ipsw-ipad7/:
    j171ap.adt                    raw device tree (input for tools/mkadt_ipad7.py)
    DeviceTree.j171ap.im4p        the original file (kept for `ipsw img4 im4p extract` on a PC)
    BuildManifest.plist

    python3 mipad3/tools/fetch_j171ap.py [ipsw-url] [out-dir]
The URL defaults to mipad3/config/ipsw_url.txt.
"""
import os
import plistlib
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dtfetch as d  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
BOARD = "j171ap"


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else open(os.path.join(HERE, "..", "config", "ipsw_url.txt")).read().strip()
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "research", "ipsw-ipad7")
    os.makedirs(out, exist_ok=True)

    ents = d.read_index(url)
    bm_raw = d.read_entry(url, ents["BuildManifest.plist"])
    open(os.path.join(out, "BuildManifest.plist"), "wb").write(bm_raw)
    bm = plistlib.loads(bm_raw)

    ident = None
    for i in bm.get("BuildIdentities", []):
        if i.get("Info", {}).get("DeviceClass", "").lower() == BOARD:
            ident = i
            if i["Info"].get("RestoreBehavior") == "Erase":
                break
    if not ident:
        boards = sorted({i.get("Info", {}).get("DeviceClass", "") for i in bm.get("BuildIdentities", [])})
        raise SystemExit("board %s not in this IPSW. Boards: %s" % (BOARD, ", ".join(boards)))

    print("IPSW products:", ", ".join(bm.get("SupportedProductTypes", [])))
    print("Disk images for %s (for tools/mkiosroot.sh):" % BOARD)
    for key, val in sorted(ident.get("Manifest", {}).items()):
        path = val.get("Info", {}).get("Path", "")
        if path.endswith((".dmg", ".aea")):
            ent = ents.get(path)
            size = "%.2f GiB" % (ent[1] / 2**30) if ent else "?"
            print("  %-22s %s  (%s)" % (key, path, size))

    dt_path = ident["Manifest"]["DeviceTree"]["Info"]["Path"]
    blob = d.read_entry(url, ents[dt_path])
    im4p = os.path.join(out, os.path.basename(dt_path))
    open(im4p, "wb").write(blob)

    payload, encrypted = d.im4p_payload(blob)
    if encrypted:
        raise SystemExit("device tree is encrypted, cannot read it here. Raw file saved: %s" % im4p)
    try:
        raw = d.unpack(payload)
    except SystemExit as e:
        print(e)
        print("Raw IM4P saved: %s" % im4p)
        print("Finish on a PC:  ipsw img4 im4p extract %s -o %s" % (im4p, os.path.join(out, BOARD + ".adt")))
        raise SystemExit(2)
    adt_path = os.path.join(out, BOARD + ".adt")
    open(adt_path, "wb").write(raw)
    print("device tree:", adt_path, "(%d bytes)" % len(raw))


if __name__ == "__main__":
    main()
