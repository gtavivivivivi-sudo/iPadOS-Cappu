#!/usr/bin/env python3
"""Read-only backup of the Mi Pad 3 partitions that must be saved before anything else touches the tablet.

Nothing is ever written to the tablet: the only remote commands are `ls`, `cat /proc/partitions`, `id`, `getprop`
and `dd if=<partition>` (checked by _ro() before every call). Needs the tablet booted in Android with USB debugging
and ROOT (uid 0 via `adb root` style shell, or `su`). Without root nothing is read and the script says so.

  python tools/cappu-backup.py --report report-XXXX.txt   which wanted partitions exist (offline, no tablet needed)
  python tools/cappu-backup.py --list                     same, but from the tablet, plus root check
  python tools/cappu-backup.py --out backups              read everything wanted, verify, write SHA256SUMS.txt
  python tools/cappu-backup.py --out backups --only boot,recovery --extra para,expdb

Each partition is read twice and the two SHA-256 sums must match, and the size must equal /proc/partitions.
STATUS: tested only against a fake adb (tools/ selftest in the update notes); NOT run on the real tablet yet (U).
nvram/nvdata/proinfo hold IMEI and MAC: keep the backups private and in two places.
"""
import argparse, hashlib, os, pathlib, re, shutil, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
WANTED = [  # (our name, possible by-name names)
    ("preloader", ["preloader"]), ("lk", ["lk", "uboot"]), ("boot", ["boot", "bootimg"]),
    ("recovery", ["recovery"]), ("nvram", ["nvram"]), ("nvdata", ["nvdata"]), ("proinfo", ["proinfo"]),
    ("seccfg", ["seccfg"]), ("protect1", ["protect1"]), ("protect2", ["protect2"]),
]
_OK_PREFIX = ("ls ", "cat /proc/partitions", "id", "getprop ro.", "dd if=/dev/block/", "su -c ")


def _ro(cmd):
    """Refuse anything that is not one of our read-only commands."""
    inner = cmd[len("su -c "):].strip().strip('"') if cmd.startswith("su -c ") else cmd
    bad = (" of=", ">", "|", ";", "&", "`", "$(", "rm ", "mkfs", "wipe", "format", "erase", "flash")
    if not inner.startswith(_OK_PREFIX[:-1]) or any(b in inner for b in bad):
        sys.exit("internal error: refusing non read-only command: %r" % cmd)


def find_adb():
    p = shutil.which("adb")
    if p:
        return p
    for d in (ROOT / "platform-tools", ROOT.parent / "platform-tools"):
        for ext in ("", ".exe"):
            c = d / ("adb" + ext)
            if c.is_file():
                return str(c)
    sys.exit("adb not found (put platform-tools next to the repo or in PATH)")


class Adb:
    def __init__(self):
        self.adb = find_adb()
        self.su = False

    def sh(self, cmd, timeout=60):
        _ro(cmd)
        r = subprocess.run([self.adb, "shell", cmd], capture_output=True, text=True, errors="replace", timeout=timeout)
        return (r.stdout or "").replace("\r", ""), r.returncode

    def state(self):
        r = subprocess.run([self.adb, "get-state"], capture_output=True, text=True, errors="replace", timeout=20)
        return (r.stdout + r.stderr).strip()

    def detect_root(self):
        out, _ = self.sh("id")
        if "uid=0" in out:
            self.su = False
            return True
        out, _ = self.sh('su -c "id"')
        if "uid=0" in out:
            self.su = True
            return True
        return False

    def stream(self, dev):
        """Yield the raw bytes of a block device."""
        cmd = 'su -c "dd if=%s bs=1048576"' % dev if self.su else "dd if=%s bs=1048576" % dev
        _ro(cmd)
        p = subprocess.Popen([self.adb, "exec-out", cmd], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            while True:
                b = p.stdout.read(1 << 20)
                if not b:
                    break
                yield b
        finally:
            p.stdout.close()
            p.wait()


def parse_byname(text):
    m = {}
    for line in text.splitlines():
        r = re.search(r"\s(\S+)\s+->\s+(/dev/block/\S+)\s*$", line.strip())
        if r:
            m[r.group(1)] = r.group(2)
    return m


def parse_partitions(text):
    sizes = {}
    for line in text.splitlines():
        f = line.split()
        if len(f) == 4 and f[0].isdigit() and f[2].isdigit():
            sizes[f[3]] = int(f[2]) * 1024
    return sizes


def plan(byname, only, extra):
    rows, missing = [], []
    wanted = [(n, a) for n, a in WANTED if not only or n in only] + [(e, [e]) for e in extra]
    for name, aliases in wanted:
        hit = next((a for a in aliases if a in byname), None)
        if hit:
            rows.append((name, hit, byname[hit]))
        else:
            missing.append(name)
    return rows, missing


def show_plan(rows, missing, sizes=None):
    for name, hit, dev in rows:
        sz = (sizes or {}).get(dev.rsplit("/", 1)[-1])
        print("  %-10s %-14s %s%s" % (name, hit, dev, "  %d bytes" % sz if sz else ""))
    if missing:
        print("  not found: " + ", ".join(missing))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", help="read partition names from a cappu.py report file (no tablet needed)")
    ap.add_argument("--list", action="store_true", help="show partitions and root status, read nothing")
    ap.add_argument("--out", help="folder for the backup")
    ap.add_argument("--only", default="", help="comma list of our names (default: all wanted)")
    ap.add_argument("--extra", default="", help="comma list of extra by-name partitions")
    ap.add_argument("--no-verify", action="store_true", help="read each partition once")
    a = ap.parse_args()
    only = [x for x in a.only.split(",") if x]
    extra = [x for x in a.extra.split(",") if x]

    if a.report:
        text = pathlib.Path(a.report).read_text(encoding="utf-8", errors="replace")
        rows, missing = plan(parse_byname(text), only, extra)
        print("partitions found in the report:")
        show_plan(rows, missing, parse_partitions(text))
        return
    if not a.list and not a.out:
        ap.error("give --report FILE, --list or --out DIR")

    adb = Adb()
    st = adb.state()
    if st != "device":
        sys.exit("adb state is %r, need 'device' (USB debugging on, confirm the prompt on the tablet)" % st)
    names, _ = adb.sh("ls -l /dev/block/platform/*/by-name")
    byname = parse_byname(names) or parse_byname(adb.sh("ls -l /dev/block/platform/*/*/by-name")[0])
    sizes = parse_partitions(adb.sh("cat /proc/partitions")[0])
    rows, missing = plan(byname, only, extra)
    root = adb.detect_root()
    print("root: %s" % ("yes (%s)" % ("su" if adb.su else "adb shell is uid 0") if root else "NO"))
    show_plan(rows, missing, sizes)
    if a.list:
        return
    if not byname:
        sys.exit("no /dev/block/platform/*/by-name on the tablet: nothing to read")
    if not root:
        sys.exit("no root: raw partitions cannot be read over adb. NOTHING was read or written.\n"
                 "Options: get root, or take the images from the stock Fastboot ROM; tell Claude which.")

    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sums, bad = [], []
    for name, hit, dev in rows:
        want = sizes.get(dev.rsplit("/", 1)[-1])
        path = out / (name + ".img")
        h, n = hashlib.sha256(), 0
        with open(path, "wb") as f:
            for chunk in adb.stream(dev):
                f.write(chunk)
                h.update(chunk)
                n += len(chunk)
        ok = want is None or n == want
        why = "" if ok else "size %d != expected %d" % (n, want)
        if ok and not a.no_verify:
            h2 = hashlib.sha256()
            for chunk in adb.stream(dev):
                h2.update(chunk)
            if h2.hexdigest() != h.hexdigest():
                ok, why = False, "second read differs"
        print("%-10s %9d bytes  %s  %s" % (name, n, h.hexdigest()[:16], "OK" if ok else "FAIL: " + why))
        if ok:
            sums.append("%s  %s" % (h.hexdigest(), path.name))
        else:
            bad.append(name)
            os.replace(path, str(path) + ".BAD")	# never leave a suspect file under a good name
    (out / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    model = adb.sh("getprop ro.product.model")[0].strip()
    fp = adb.sh("getprop ro.build.fingerprint")[0].strip()
    (out / "manifest.txt").write_text("date %s\nmodel %s\nfingerprint %s\nroot via %s\nverified %s\nfailed %s\nnot found %s\n" % (
        time.strftime("%Y-%m-%d %H:%M:%S"), model, fp, "su" if adb.su else "uid0", "no" if a.no_verify else "double read",
        ",".join(bad) or "-", ",".join(missing) or "-"), encoding="utf-8")
    print("\nwrote %s (%d ok, %d failed, %d not found). Copy the folder to a second place." % (out, len(sums), len(bad), len(missing)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
