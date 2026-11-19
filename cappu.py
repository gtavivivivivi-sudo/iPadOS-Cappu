#!/usr/bin/env python3
"""iPadOS-Cappu launcher: build and run the M1 diagnostic shim. Works on Windows, macOS, Linux.

  python cappu.py doctor              which tools are installed
  python cappu.py fetch [--run ID|--zip FILE]  download the latest kernel built by GitHub Actions into dist/kernel/ and run the LSE gate on it
  python cappu.py check               repo validation + device tree generator self-test
  python cappu.py qemu                build the shim for QEMU and run it (needs clang, ld.lld, llvm-objcopy, qemu)
  python cappu.py image [--ref FILE] [--fb 0xADDR]
                                      build the shim for the tablet and pack boot images into dist/
                                      (FILE = any Mi Pad 3 TWRP/boot image used as a format template; default: dist/m1-boot.img)
                                      (--fb = framebuffer address from `report`, used if LK's DTB does not give one)
  python cappu.py report              collect read-only facts about the tablet into report-*.txt (send it to Claude)
  python cappu.py tablet              guided `fastboot boot` of dist/m1-boot.img (never flashes anything)

M1 is a diagnostic shim, NOT iPadOS. Nothing here has run on the tablet yet.
"""
import argparse, os, pathlib, shutil, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent
SHIM = ROOT / "shim" / "mt8176"
DIST = ROOT / "dist"


def have(tool):
    p = shutil.which(tool)
    if p:
        return p
    for d in (ROOT / "platform-tools", ROOT.parent / "platform-tools"):
        for ext in ("", ".exe"):
            c = d / (tool + ext)
            if c.is_file():
                return str(c)
    return None


def need(*tools):
    miss = [t for t in tools if not have(t)]
    if miss:
        sys.exit("missing tools: %s\nrun `python cappu.py doctor`" % ", ".join(miss))


def run(cmd, **kw):
    cmd = [str(c) for c in cmd]
    cmd[0] = have(cmd[0]) or cmd[0]
    return subprocess.run(cmd, **kw)


def cmd_version(_):
    f = ROOT / "VERSION"
    print(f.read_text(encoding="utf-8").strip() if f.is_file() else "unknown (VERSION file missing)")


def cmd_doctor(_):
    rows = [("python", sys.executable), ("clang", have("clang")), ("ld.lld", have("ld.lld")),
            ("llvm-objcopy", have("llvm-objcopy")), ("llvm-readelf", have("llvm-readelf")),
            ("qemu-system-aarch64", have("qemu-system-aarch64")), ("adb", have("adb")),
            ("fastboot", have("fastboot")), ("git", have("git"))]
    for n, p in rows:
        print("%-22s %s" % (n, p or "NOT FOUND"))
    print("\nqemu command needs: clang, ld.lld, llvm-objcopy, qemu-system-aarch64")
    print("image command needs: clang, ld.lld, llvm-objcopy")
    print("tablet command needs: adb, fastboot (platform-tools)")


def build_shim(qemu, fb=None):
    need("clang", "ld.lld", "llvm-objcopy")
    out = SHIM / "out"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    cf = ["--target=aarch64-none-elf", "-O2", "-ffreestanding", "-nostdlib", "-fno-pic",
          "-mgeneral-regs-only", "-mstrict-align", "-fno-stack-protector", "-Wall", "-Wextra"]
    if qemu:
        cf.append("-DPLAT_QEMU")
    if fb:
        cf.append("-DFB_FIXED=%#xUL" % fb)
    objs = []
    for src, name in [(ROOT / "shim" / "start.S", "start")] + [(SHIM / (n + ".c"), n) for n in ("mt_main", "mt_fdt", "mt_con")]:
        o = out / (name + ".o")
        if run(["clang"] + cf + ["-c", src, "-o", o]).returncode:
            sys.exit("compile failed: %s" % src.name)
        objs.append(o)
    if have("llvm-readelf"):
        r = run(["llvm-readelf", "-r"] + objs[1:], capture_output=True, text=True)
        if "ABS64" in r.stdout:
            sys.exit("error: absolute relocations in C objects (shim must be position independent)")
    elf, img = out / "shim.elf", out / "Image"
    if run(["ld.lld", "-T", ROOT / "shim" / "shim.ld", "--build-id=none", "-static", "-N"] + objs + ["-o", elf]).returncode:
        sys.exit("link failed")
    if run(["llvm-objcopy", "-O", "binary", elf, img]).returncode:
        sys.exit("objcopy failed")
    print("built %s (%d bytes, plat=%s%s)" % (img, img.stat().st_size, "qemu-virt" if qemu else "mt8176", ", fb=%#x" % fb if fb else ""))
    return img


def cmd_qemu(_):
    need("qemu-system-aarch64")
    img = build_shim(True)
    cmd = ["qemu-system-aarch64", "-M", "virt,gic-version=2", "-cpu", "cortex-a72", "-m", "1G",
           "-nographic", "-monitor", "none", "-kernel", img, "-serial", "stdio"]
    print("running QEMU (cortex-a72, GICv2), exits by itself...\n")
    try:
        r = run(cmd, capture_output=True, text=True, timeout=30)
        text = r.stdout
    except subprocess.TimeoutExpired as e:
        text = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
    print(text.replace("\r", ""))
    ok = "RESULT: PASS" in text
    print("QEMU result:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


def cmd_check(_):
    ok = True
    # tools/validate-repo.py is intentionally gutted and is not run (it used to be called here, which made `check` always fail)
    with tempfile.TemporaryDirectory() as d:
        r = run([sys.executable, ROOT / "tools" / "mkadt_mt8176.py", os.path.join(d, "out.adt"), "--dump"],
                capture_output=True, text=True)
        good = r.returncode == 0 and "iPad7,11" in r.stdout
        print("mkadt_mt8176 self-test:", "OK" if good else "FAILED\n" + r.stdout[-500:] + r.stderr[-500:])
        ok &= good
    sys.exit(0 if ok else 1)


def cmd_image(a):
    ref = pathlib.Path(a.ref) if getattr(a, "ref", None) else None
    if not ref:
        # No TWRP/boot image at hand: our own previous image is a valid template (same Android header, kernel+appended DTB).
        # Copy it first if you rebuild into the same folder: the output files are overwritten.
        own = DIST / "m1-boot.img"
        if own.is_file():
            ref = DIST / ".template.img"
            shutil.copyfile(own, ref)
            print("no --ref: using dist/m1-boot.img as the format template")
    if not ref or not ref.is_file():
        sys.exit("need --ref FILE: any Mi Pad 3 recovery/boot image (e.g. twrp.img), used only as a format template")
    fb = None
    if getattr(a, "fb", None):
        try:
            fb = int(a.fb, 0)
        except ValueError:
            sys.exit("--fb must be a number like 0xbf000000")
        if fb & 0xfff or not 0x40000000 <= fb < 0x140000000:
            sys.exit("--fb %#x is not a 4K-aligned address inside DRAM 0x40000000..0x140000000" % fb)
    img = build_shim(False, fb)
    DIST.mkdir(exist_ok=True)
    try:
        for name, extra in (("m1-boot.img", []), ("m1-boot-raw.img", ["--raw"])):
            r = run([sys.executable, ROOT / "tools" / "mkboot_mt8176.py", "--ref", ref, "--shim", img,
                     "-o", DIST / name] + extra)
            if r.returncode:
                sys.exit("packing failed")
    finally:
        if ref.name == ".template.img":
            ref.unlink()
    print("\nimages in %s. Use only with `fastboot boot`, never flash them." % DIST)


def battery_level():
    try:
        r = run(["adb", "shell", "dumpsys", "battery"], capture_output=True, text=True, timeout=20, errors="replace")
        for line in r.stdout.splitlines():
            if line.strip().startswith("level:"):
                return int(line.split(":")[1])
    except Exception:
        pass
    return None


def cmd_report(_):
    """Collect read-only facts about the tablet into report-*.txt (nothing is changed on the device)."""
    import time
    need("adb", "fastboot")
    lines = []

    def sec(title, cmd, timeout=40):
        lines.append("=== %s   $ %s" % (title, " ".join(str(c) for c in cmd)))
        try:
            r = run(cmd, capture_output=True, text=True, timeout=timeout, errors="replace")
            out = (r.stdout + r.stderr).strip()
        except Exception as e:
            out = "ERROR: %s" % e
        lines.append(out)
        lines.append("")
        return out

    adb_list = sec("adb devices", ["adb", "devices", "-l"])
    in_adb = any(l.split()[1:2] == ["device"] for l in adb_list.splitlines()[1:] if l.strip())
    if in_adb:
        for t, c in [("getprop", ["adb", "shell", "getprop"]), ("uname", ["adb", "shell", "uname", "-a"]),
                     ("cpuinfo", ["adb", "shell", "cat", "/proc/cpuinfo"]),
                     ("meminfo", ["adb", "shell", "cat", "/proc/meminfo"]),
                     ("cmdline", ["adb", "shell", "cat", "/proc/cmdline"]),
                     ("partitions", ["adb", "shell", "cat", "/proc/partitions"]),
                     ("partition names", ["adb", "shell", "ls -l /dev/block/platform/*/by-name"]),
                     ("mounts", ["adb", "shell", "cat", "/proc/mounts"]),
                     # read-only facts that answer the M1 unknowns (framebuffer address/format, real RAM map)
                     ("iomem", ["adb", "shell", "cat", "/proc/iomem"]),
                     ("dt chosen", ["adb", "shell", "ls -l /proc/device-tree/chosen/"]),
                     ("dt videolfb", ["adb", "shell", "for f in /proc/device-tree/chosen/atag*; do echo == $f; od -A x -t x1 $f 2>&1 || hexdump -C $f 2>&1; done"]),
                     ("dt memory", ["adb", "shell", "for f in /proc/device-tree/memory*/reg; do echo == $f; od -A x -t x1 $f 2>&1; done"]),
                     ("fb0", ["adb", "shell", "for f in name bits_per_pixel stride virtual_size modes; do echo $f: $(cat /sys/class/graphics/fb0/$f 2>&1); done"]),
                     ("dmesg fb/lcm", ["adb", "shell", "dmesg | grep -i -E 'fb|lcm|framebuffer|ram_console|videolfb' | head -60"]),
                     ("battery", ["adb", "shell", "dumpsys", "battery"])]:
            sec(t, c)
    else:
        lines.append("(no device in Android/adb mode: adb part skipped)\n")
    fb_list = sec("fastboot devices", ["fastboot", "devices"], 20)
    if fb_list.strip() and "waiting" not in fb_list:
        sec("fastboot getvar all", ["fastboot", "getvar", "all"], 30)
        sec("fastboot oem device-info", ["fastboot", "oem", "device-info"], 30)
    else:
        lines.append("(no device in fastboot mode: fastboot part skipped)\n")
    text = "\n".join(lines)
    name = ROOT / ("report-%s.txt" % time.strftime("%Y%m%d-%H%M%S"))
    name.write_text(text, encoding="utf-8")
    print("\nsaved: %s  (%d bytes)\nSend me this file." % (name, len(text.encode())))
    for key in ("ro.product.model", "ro.build.version.release", "ro.boot.flash.locked", "ro.boot.verifiedbootstate", "unlocked:"):
        for l in text.splitlines():
            if key in l:
                print("  " + l.strip())
                break


def _repo_slug():
    try:
        u = subprocess.run(["git", "remote", "get-url", "origin"], cwd=str(ROOT), capture_output=True, text=True).stdout.strip()
        import re
        m = re.search(r"github\.com[:/]([^/]+/[^/.]+)", u)
        if m:
            return m.group(1)
    except Exception:
        pass
    return "gtavivivivivi-sudo/iPadOS-Cappu"


def _gh_json(url, token):
    import json, urllib.request
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "cappu"})
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def cmd_fetch(args):
    """Download the kernel artifact of the latest successful xnu workflow run (or --run ID, or a local --zip),
    unpack it into dist/kernel/<run>/, print its sha256 and run the same LSE gate as CI. Writes nothing to the tablet."""
    import hashlib, urllib.request, zipfile
    out = ROOT / "dist" / "kernel"
    out.mkdir(parents=True, exist_ok=True)
    tag = "local"
    if getattr(args, "zip", None):
        z = pathlib.Path(args.zip)
        if not z.is_file():
            sys.exit("no such file: %s" % z)
        tag = "zip-" + hashlib.sha256(z.read_bytes()).hexdigest()[:8]
    else:
        slug = _repo_slug()
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token and have("gh"):
            r = subprocess.run([have("gh"), "auth", "token"], capture_output=True, text=True)
            token = r.stdout.strip() or None
        run_id = getattr(args, "run", None)
        if not run_id:
            runs = _gh_json("https://api.github.com/repos/%s/actions/workflows/xnu.yml/runs?status=success&per_page=1" % slug, token)
            if not runs.get("workflow_runs"):
                sys.exit("no successful xnu run found in %s" % slug)
            run = runs["workflow_runs"][0]
            run_id = run["id"]
            print("latest successful run: #%s %s (%s)" % (run.get("run_number"), run_id, run.get("head_sha", "")[:7]))
        if not token:
            sys.exit("downloading artifacts needs a GitHub token (even for public repos).\n"
                     "Make one: GitHub -> Settings -> Developer settings -> Fine-grained tokens, read-only 'Actions' for this repo,\n"
                     "then in PowerShell: $env:GITHUB_TOKEN='...'   (or install gh and run `gh auth login`).\n"
                     "Or download the xnu-kernel zip from the run page by hand and use: python cappu.py fetch --zip FILE")
        arts = _gh_json("https://api.github.com/repos/%s/actions/runs/%s/artifacts" % (slug, run_id), token).get("artifacts", [])
        art = next((a for a in arts if a["name"] == "xnu-kernel" and not a.get("expired")), None)
        if not art:
            sys.exit("run %s has no live 'xnu-kernel' artifact (artifacts expire after a few days; re-run the workflow)" % run_id)
        z = out / ("xnu-kernel-%s.zip" % run_id)
        req = urllib.request.Request(art["archive_download_url"], headers={"Authorization": "Bearer " + token, "User-Agent": "cappu"})
        print("downloading %s (%.1f MB) ..." % (art["name"], art["size_in_bytes"] / 1e6))
        with urllib.request.urlopen(req, timeout=300) as r, open(z, "wb") as f:
            shutil.copyfileobj(r, f)
        tag = str(run_id)
    dest = out / tag
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(z) as zf:
        zf.extractall(dest)
    kern = sorted(dest.rglob("kernel.*.cappu"))
    if not kern:
        sys.exit("no kernel.*.cappu inside the artifact: %s" % dest)
    k = kern[0]
    print("kernel: %s\nsha256: %s" % (k, hashlib.sha256(k.read_bytes()).hexdigest()))
    (out / "LATEST.txt").write_text("%s\n" % k.relative_to(ROOT), encoding="utf-8")
    print("LSE gate (same as CI):")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "scan_lse.py"), str(k), "--top", "10", "--syms", "--allow", "K256"])
    print("LSE gate: %s" % ("PASS" if r.returncode == 0 else "FAIL (exit %d)" % r.returncode))
    sys.exit(r.returncode)


def ask(prompt, word):
    return input("%s\nType '%s' to continue, anything else aborts: " % (prompt, word)).strip().lower() == word


def cmd_tablet(_):
    need("adb", "fastboot")
    image = DIST / "m1-boot.img"
    if not image.is_file():
        sys.exit("dist/m1-boot.img missing: run `python cappu.py image --ref <twrp.img>` first")
    print("This boots a DIAGNOSTIC image from RAM. It writes nothing to flash.")
    print("If the tablet hangs: hold Power for 10-15 s. It also resets itself ~60 s after the result.\n")
    print("Looking for the tablet in Android (adb):")
    run(["adb", "devices"])
    lvl = battery_level()
    if lvl is not None:
        print("battery: %d%%" % lvl)
        if lvl < 50:
            sys.exit("charge the tablet above 50%% first (now %d%%)" % lvl)
    if ask("\nReboot the tablet into the bootloader now (adb reboot bootloader)?", "yes"):
        run(["adb", "reboot", "bootloader"])
        input("Wait until the tablet shows fastboot, then press Enter...")
    print("\nfastboot devices:")
    r = run(["fastboot", "devices"], capture_output=True, text=True)
    print(r.stdout or "(nothing: check cable/driver, or hold Vol- + Power while powering on)")
    if not r.stdout.strip():
        sys.exit(1)
    print("fastboot oem device-info (lock state), send me this output:")
    r = run(["fastboot", "oem", "device-info"], capture_output=True, text=True)
    print((r.stdout + r.stderr).strip())
    if not ask("\nRun `fastboot boot %s` (photograph the screen right after)?" % image.name, "boot"):
        sys.exit(0)
    r = run(["fastboot", "boot", image])
    if r.returncode:
        print("\nfastboot boot failed. Try the fallback: fastboot boot %s" % (DIST / "m1-boot-raw.img"))
        print("A refusal here is a SAFE outcome (nothing was changed).")
    else:
        print("\nBooted. Read the screen for 60 s, photograph it, and send the photo.")


# --- interactive menu (double-click on Windows opens this, no args needed) ---

_GREEN, _GREY, _RESET = "\033[32m", "\033[90m", "\033[0m"

MENU_ITEMS = [
    ("doctor  -  какие инструменты найдены", "doctor"),
    ("fetch   -  скачать последнее ядро из Actions и проверить LSE", "fetch"),
    ("check   -  проверка репозитория + самотест mkadt", "check"),
    ("qemu    -  собрать шим и прогнать в QEMU", "qemu"),
    ("image   -  собрать образы M1 для планшета (нужен --ref файл)", "image"),
    ("report  -  собрать данные с планшета, только чтение", "report"),
    ("tablet  -  fastboot boot на планшете, с подтверждениями", "tablet"),
    ("Выход", "exit"),
]


def _console_setup():
    if os.name == "nt":
        os.system("chcp 65001 >NUL 2>&1")  # UTF-8 codepage, so Cyrillic shows correctly
        os.system("")  # turns on ANSI/VT100 escapes in cmd.exe (Windows 10+)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def _clear():
    print("\033[2J\033[H", end="")


def _read_key():
    """Blocks for one keypress, returns 'up' / 'down' / 'enter' / None."""
    if os.name == "nt":
        import msvcrt
        ch = msvcrt.getch()
        if ch in (b"\x00", b"\xe0"):
            ch2 = msvcrt.getch()
            return {b"H": "up", b"P": "down"}.get(ch2)
        if ch in (b"\r", b"\n"):
            return "enter"
        if ch == b"\x03":
            raise KeyboardInterrupt
        return None
    import termios, tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch2 = sys.stdin.read(2)
            return {"[A": "up", "[B": "down"}.get(ch2)
        if ch in ("\r", "\n"):
            return "enter"
        if ch == "\x03":
            raise KeyboardInterrupt
        return None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _menu(title, items):
    idx = 0
    while True:
        _clear()
        print(title)
        print("#" * 60)
        for i, (label, _) in enumerate(items):
            if i == idx:
                print("%s-> %s%s" % (_GREEN, label, _RESET))
            else:
                print("%s   %s%s" % (_GREY, label, _RESET))
        print("#" * 60)
        print("стрелки вверх/вниз, Enter - выбрать")
        key = _read_key()
        if key == "up":
            idx = (idx - 1) % len(items)
        elif key == "down":
            idx = (idx + 1) % len(items)
        elif key == "enter":
            return items[idx][1]


def interactive_main():
    _console_setup()
    while True:
        choice = _menu("iPadOS-Cappu", MENU_ITEMS)
        if choice == "exit":
            break
        _clear()
        try:
            if choice == "image":
                ref = input("Путь к файлу-шаблону (например twrp.img): ").strip()
                cmd_image(argparse.Namespace(ref=ref))
            else:
                {"doctor": cmd_doctor, "fetch": lambda _: cmd_fetch(argparse.Namespace(zip=None, run=None)), "check": cmd_check, "qemu": cmd_qemu,
                 "report": cmd_report, "tablet": cmd_tablet}[choice](None)
        except SystemExit as e:
            if e.code not in (0, None):
                print("\n[команда завершилась с кодом %s]" % e.code)
        except KeyboardInterrupt:
            print("\n[прервано]")
        input("\nНажми Enter, чтобы вернуться в меню...")
    print("\nЗакрыть можно Enter'ом.")
    try:
        input()
    except Exception:
        pass


def main():
    if len(sys.argv) == 1:
        interactive_main()
        return
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n, f in (("version", cmd_version), ("doctor", cmd_doctor), ("check", cmd_check), ("qemu", cmd_qemu), ("report", cmd_report), ("tablet", cmd_tablet)):
        sub.add_parser(n).set_defaults(fn=f)
    p = sub.add_parser("fetch")
    p.add_argument("--run", help="workflow run id (default: latest successful)")
    p.add_argument("--zip", help="use a downloaded xnu-kernel artifact zip instead of downloading")
    p.set_defaults(fn=cmd_fetch)
    p = sub.add_parser("image")
    p.add_argument("--ref", help="Mi Pad 3 boot/recovery image used as a format template (default: dist/m1-boot.img)")
    p.add_argument("--fb", help="fixed framebuffer address from the Android report, e.g. 0xbf000000 (overrides LK's DTB value)")
    p.set_defaults(fn=cmd_image)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
