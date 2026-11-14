/*
 * GICv2 (ARM GIC-400) support for the MT8176 (Mi Pad 3) shim.
 * Replaces the GICv3 sysreg/redistributor path of shim.c (Qualcomm).
 * Bases from arch/arm64/boot/dts/mt8173.dtsi (cappu-n-oss).
 * STATUS: untested, written from the GICv2 spec (Arm IHI 0048B), syntax-checked only.
 * UNKNOWN until first boot: which security state the shim runs in. With the Security
 * Extensions, a non-secure caller sees only the NS view (GICD_IGROUPR may be RAZ/WI).
 */
#ifndef GICV2_H
#define GICV2_H
#include <stdint.h>

#ifndef GICD_BASE_MT8176
#define GICD_BASE_MT8176   0x10221000UL   /* distributor      */
#define GICC_BASE_MT8176   0x10222000UL   /* CPU interface    */
#endif   /* plat.h may override both for the QEMU virt board */

/* Distributor */
#define GICD_CTLR          0x000
#define GICD_TYPER         0x004
#define GICD_IGROUPR       0x080
#define GICD_ISENABLER     0x100
#define GICD_ICENABLER     0x180
#define GICD_ICPENDR       0x280
#define GICD_IPRIORITYR    0x400
#define GICD_ITARGETSR     0x800
#define GICD_ICFGR         0xC00
#define GICD_SGIR          0xF00
/* CPU interface */
#define GICC_CTLR          0x000
#define GICC_PMR           0x004
#define GICC_BPR           0x008
#define GICC_IAR           0x00C
#define GICC_EOIR          0x010

/* INTIDs of the architected timer PPIs: PPI n -> INTID 16 + n (dts: PPI 13,14,11,10) */
#define INTID_PPI(n)       (16 + (n))
#define INTID_TIMER_SEC    INTID_PPI(13)  /* 29 */
#define INTID_TIMER_PHYS   INTID_PPI(14)  /* 30, non-secure physical */
#define INTID_TIMER_VIRT   INTID_PPI(11)  /* 27 */
#define INTID_TIMER_HYP    INTID_PPI(10)  /* 26 */
#define GIC_SPURIOUS       1023

static inline uint32_t g_rd(uintptr_t a) { return *(volatile uint32_t *)a; }
static inline void g_wr(uintptr_t a, uint32_t v) { *(volatile uint32_t *)a = v; }
static inline void g_wr8(uintptr_t a, uint8_t v) { *(volatile uint8_t *)a = v; }
static inline void g_dsb(void)
{
#if defined(__aarch64__)
	__asm__ volatile("dsb sy" ::: "memory");
#endif
}

/* Number of interrupt lines (GICD_TYPER.ITLinesNumber: lines = 32 * (N + 1)) */
static inline uint32_t gicv2_nr_irqs(void)
{
	return 32 * ((g_rd(GICD_BASE_MT8176 + GICD_TYPER) & 0x1f) + 1);
}

/* Boot CPU: distributor + own CPU interface. Interrupts stay masked at the core. */
static inline void gicv2_dist_init(void)
{
	uintptr_t d = GICD_BASE_MT8176;
	uint32_t n = gicv2_nr_irqs();

	g_wr(d + GICD_CTLR, 0);
	for (uint32_t i = 32; i < n; i += 32) {
		g_wr(d + GICD_ICENABLER + i / 8, 0xffffffff);
		g_wr(d + GICD_ICPENDR + i / 8, 0xffffffff);
	}
	for (uint32_t i = 32; i < n; i += 4)
		g_wr(d + GICD_IPRIORITYR + i, 0xa0a0a0a0);
	for (uint32_t i = 32; i < n; i += 4)
		g_wr(d + GICD_ITARGETSR + i, 0x01010101);   /* all SPIs to CPU0 for now */
	for (uint32_t i = 32; i < n; i += 16)
		g_wr(d + GICD_ICFGR + i / 4, 0);            /* level-triggered */
	g_wr(d + GICD_CTLR, 1);
	g_dsb();
}

/* Every CPU: banked PPI/SGI setup and CPU interface. */
static inline void gicv2_cpu_init(void)
{
	uintptr_t d = GICD_BASE_MT8176, c = GICC_BASE_MT8176;

	g_wr(d + GICD_ICENABLER, 0xffff0000);          /* PPIs off, SGIs untouched */
	g_wr(d + GICD_ISENABLER, 0x0000ffff);          /* SGIs 0..15 on (IPIs)     */
	for (uint32_t i = 0; i < 32; i += 4)
		g_wr(d + GICD_IPRIORITYR + i, 0xa0a0a0a0);
	g_wr(c + GICC_PMR, 0xf0);
	g_wr(c + GICC_BPR, 0);
	g_wr(c + GICC_CTLR, 1);
	g_dsb();
}

static inline void gicv2_enable_irq(uint32_t intid, uint8_t prio)
{
	g_wr8(GICD_BASE_MT8176 + GICD_IPRIORITYR + intid, prio);
	g_wr(GICD_BASE_MT8176 + GICD_ISENABLER + (intid / 32) * 4, 1U << (intid % 32));
}

/* IRQ entry: returns INTID (and CPU id in bits 12:10 for SGIs); 1023 = spurious. */
static inline uint32_t gicv2_ack(void) { return g_rd(GICC_BASE_MT8176 + GICC_IAR); }
static inline void gicv2_eoi(uint32_t iar) { g_wr(GICC_BASE_MT8176 + GICC_EOIR, iar); }

/* IPI to a CPU mask (0..7), SGI id 0..15; TargetListFilter = 0 */
static inline void gicv2_send_sgi(uint32_t cpu_mask, uint32_t sgi)
{
	g_dsb();
	g_wr(GICD_BASE_MT8176 + GICD_SGIR, ((cpu_mask & 0xff) << 16) | (sgi & 0xf));
}
#endif
