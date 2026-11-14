/*
 * Platform selection for the MT8176 (Mi Pad 3) shim.
 *   -DPLAT_QEMU    QEMU "virt" board, -cpu cortex-a72, gic-version=2 (stand-in for testing)
 *   (default)      real MT8176. Addresses from cappu-n-oss dts, see mipad3/config/hardware-mt8176.md
 */
#ifndef PLAT_H
#define PLAT_H
#include <stdint.h>

#ifdef PLAT_QEMU
#define PLAT_NAME		"qemu-virt"
#define GICD_BASE_MT8176	0x08000000UL
#define GICC_BASE_MT8176	0x08010000UL
#define UART_BASE		0x09000000UL	/* PL011 */
#define UART_PL011		1
#define PSCI_CALL		"hvc #0"	/* virt without EL2/EL3 emulates PSCI behind hvc */
#else
#define PLAT_NAME		"mt8176"
/* GICD/GICC defaults live in gicv2.h */
#define UART_BASE		0x11002000UL	/* MTK 16550-like UART0, 26 MHz, 921600n1 (U: LK may leave it configured) */
#define UART_PL011		0
#define PSCI_CALL		"smc #0"
#endif

/* Architected timer PPIs, same on both: virt = PPI 11 -> INTID 27 */
#define TEST_INTID		27

#define rsr(r) ({ uint64_t _v; __asm__ volatile("mrs %0, " r : "=r"(_v)); _v; })
#define wsr(r, v) __asm__ volatile("msr " r ", %0" : : "r"((uint64_t)(v)))
#define isb() __asm__ volatile("isb" ::: "memory")

/* mt_fdt.c */
int mt_fdt_prop(uintptr_t fdt, const char *node, const char *prop, uintptr_t *val, uint32_t *len);
int mt_fdt_nth(uintptr_t fdt, const char *node, int idx, const char **name, uintptr_t *val, uint32_t *len);
/* mt_con.c */
void out_init(uintptr_t fb_base, uint32_t w, uint32_t h);
void out_char(char c);
void out_str(const char *s);
void out_hex(uint64_t v, int digits);
void out_kv(const char *k, uint64_t v);
#endif
