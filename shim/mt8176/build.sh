#!/bin/bash
# Build the MT8176 M1 shim. Usage: build.sh [qemu]   (needs clang + ld.lld, no cross gcc)
set -euo pipefail
cd "$(dirname "$0")"
DEF=""; [ "${1:-}" = qemu ] && DEF="-DPLAT_QEMU"
CF="--target=aarch64-none-elf -O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align -fno-stack-protector -Wall -Wextra $DEF"
mkdir -p out
clang $CF -c ../start.S -o out/start.o
for f in mt_main mt_fdt mt_con; do clang $CF -c $f.c -o out/$f.o; done
abs=$(llvm-readelf -r out/mt_*.o | grep -c ABS64 || true)
[ "$abs" = 0 ] || { echo "error: $abs absolute relocs in C objects" >&2; exit 1; }
ld.lld -T ../shim.ld --build-id=none -static -N out/start.o out/mt_main.o out/mt_fdt.o out/mt_con.o -o out/shim.elf
llvm-objcopy -O binary out/shim.elf out/Image
ls -l out/Image
