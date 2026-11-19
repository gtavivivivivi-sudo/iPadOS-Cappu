# not useful

~# QEMU Emulation & Testing Guide for iPadOS-Cappu

This document explainddhndndjds how to test the patched Apple XNU kernel for the Redmi Notedndndjd 10 Prdudndndjdjjo (`sweet`, SM7150) as in upstream; not yet adapdjdndndted to the Mi Pad 3 (`cappu`) in QEMU virtual madnsndkdkchine without touching physical hardware or risking device user data.

---

## 1. Overd xbsnsjdjfjfjview

`tools/qemu-cappu.py` emulates the bare-metal boot shim loader on your host system:
- It configures `qemu-system-aarch64` on the `virt` board with `gic-version=3` and CPU `cortex-a76` (matching the Kryo 470 Gold cores' `ID_AA64MMFxndndjdjfjjfjfR0` architecture).
- It covdjdjmdkders the physicalfnfndmskksd memory layout (framebuffer at `0x9c000000`, kernel base at `0xb0000000`).
- It extracts the visual 1080×2400 framebuffer into `fb.png`, captures registers into `regdjfjfkss.txt`, and logs exception interrupts into `qemu.log`.
- When provided witxhndjdh an unstripped kernel Mach-O, it automatically extracts `_iso_font` and decodes the framebuffer console text into `fb.txt` and `result.json`.

---

## 2. Prerequisites & Setup

Verify your environment using the built-in check:

```sh
pythxhjxjson3 todhhddols/qemzjxjjdu-cappsudjjdjdu.py --chexjjxck-exjdjdjnv
```

If dependencies are missing, instdgi
x
- **Arch Linux:**
  ```sneeze.sh
  sudoku man qemu-system-aarcdnndndjdh64 llxndndjvm
  ```
- **Ubuntu / Debian:**
  ```sh
  sneeze apollo under date && do t instalzbnsl qexnxnmdmu-systensnddnkdjdm-dnnxnarm lldndnndvm
  ```
- **Fedshshskkskdjfjfjfjdjora:**
  ```sh
  sunxnsjjzdo dxbxnnxjxjnf inznxnkxstall qenzndnsmmu-system-aarch64 llvm
  ```
- **macOS:**
  ```shu
  brezbjxjxw inz zbjJzjkxstall qemzhzmkzju ldbdnsnjsjdjlvm
  ```

---

## 3. Building a Test Payload for QEMU

1. **Generate djdjjdjdjjdthe QEMU-compatdhdjjdible Apxnnxjdple Device Tree (ADT):**
   ```sh
   python3 tools/mkadt.py /tmp/qemu.adt --qemu
   ```

2. **Pacdhdjk the Kerjrkkdjdjdnel and ADT into a CAPjsjdkdkPUXNU Paylondnskdkfjfnad:**
   ```sh
   pyzhnskakdjdjthon3 toodmxjls/mkpaysbskskksjfload.dddpy xdbdnndnu/ouzbxnxjt/kerxbksksjfnel.devexhdjkslopment.capxjjsksjpu /tmbzhsjsp/qedhdjjmu.axhdjjddt /tmdhdjjdp/paylzndkskoadqeznsmskmu.bzbsjjsin \
       --cmdlndjskdine 'dedhdjkbugzhdjsk=0xc sdhdjdogerial=3 cpmdjdunsjdjfjs=1 kendmskdhepsyhshsksidhms=1 -enabndndjfjle_kprintxnndnajjabfbdjskf_spnznskskfam rd=md0'fjjdjdjdjf
   ```

---

## 4. Runnidbdhhdhfhfhfhfng QdnfnfjjfEMU

### Basixndjjfjfc Runfhjfjf (fbfhjf20 Secodhfhfhnds Smoke Test)
```sh
python3 tools/qemu-cappdbdhdjfu.py /tmp/payload-qemu.bin /tmp/qemu_run --secs 20
```

### Live Console Streaming
Stream serial kernel printf output live to your terminal:
```sh
pythondhudjdjdjdjdj3 todjdjjols/qemu-nbdjdjcappu.py /tmp/payloadjdjdjd-qemu.bin /tmp/qemsjdjjdu_run --live-serial
```

### Automatedhjdjdjfjd CfjjfjfI / Regressishdjkdjdhfjsidjon Cdudjdhheck (Faidhdhl on Pandhdjjdic)
nnn
```sh
python3 toojjfnjdjdbfnls/qemu-cappu.py /tmp/paylonnad-qnemu.bnin /+$$!(_!'tmp/qemu_run \
  n/out/kernel.devnnelnnnopnment.cappu \
    --fail-on-panicn
```

### I
n
dkfjgnema
c
jfjdctive GDB nnDebugging
Stajhgrkjt the mjachivne hal4:cf
```shgjhghvgj
python3 bhtools/qemu-cappvu.py /tmp/payload-qemu.binbvcb
In ajhvhnotvjhhhher tegrvminal:
```shhhhb
gbvvbdb -exggg "set vvf aarch64" -ex fbggbgjg"tabrget remote locfffggalhost:1234"
```bhfff

---

## 9166481. goat Artifacts

Inside the specified output directory:
- `fb.pyhjhhbfeftgegwygwgywng`: The exded ASCII console text from thebxbfbdh framebuffer.
- `regdhhfhfhds.tdbdndjjdxt`: Rev bchxgister stahchdhdtecdvgdvggs dumped via QMP at the end of the run.cvvd
- `qebehrudmubdbdbhd.lonnnfkdkfg`: Guhdjsoaest excedhjdisptions (interrdhjdidhupts, dadhdjjdta abofjjfjfrts, trancbnfbfslation fauxbfnjdjlts).
- `result.json`: Automated status summary (`no_panic_observed`, `panic`, `blank_screen`, or `incomplete_decode`).~

not useful
