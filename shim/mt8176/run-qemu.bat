@echo off
rem Windows: build + run in QEMU. Needs clang, ld.lld, llvm-objcopy (LLVM) and qemu-system-aarch64 in PATH.
cd /d "%~dp0"
if not exist out mkdir out
set CF=--target=aarch64-none-elf -O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align -fno-stack-protector -Wall -Wextra -DPLAT_QEMU
for %%f in (mt_main mt_fdt mt_con) do (clang %CF% -c %%f.c -o out\%%f.o || exit /b 1)
clang %CF% -c ..\start.S -o out\start.o || exit /b 1
ld.lld -T ..\shim.ld --build-id=none -static -N out\start.o out\mt_main.o out\mt_fdt.o out\mt_con.o -o out\shim.elf || exit /b 1
llvm-objcopy -O binary out\shim.elf out\Image || exit /b 1
echo Built. Starting QEMU, it exits by itself after RESULT line (Ctrl+C if it hangs).
qemu-system-aarch64 -M virt,gic-version=2 -cpu cortex-a72 -m 1G -nographic -monitor none -device loader,file=out\Image,addr=0x40200000,cpu-num=0 -serial stdio
pause
