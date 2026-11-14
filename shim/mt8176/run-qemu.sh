#!/bin/bash
# Needs qemu-system-aarch64 (brew install qemu). Loads the Image at 0x40200000, CPU0 starts there at EL1.
set -euo pipefail
cd "$(dirname "$0")"
./build.sh qemu
timeout 20 qemu-system-aarch64 -M virt,gic-version=2 -cpu cortex-a72 -m 1G -nographic -monitor none \
	-device loader,file=out/Image,addr=0x40200000,cpu-num=0 -serial stdio | tee out/qemu.log
grep -q "RESULT: PASS" out/qemu.log && echo "OK" || { echo "FAILED"; exit 1; }
