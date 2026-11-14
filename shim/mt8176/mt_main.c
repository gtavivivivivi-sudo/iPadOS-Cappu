/*
 * MT8176 milestone M1: prove the boot path and the GICv2 + timer IRQ path.
 *   1. text on UART (and framebuffer if LK's DTB has /chosen/atag,videolfb)
 *   2. CPU id registers (EL, MIDR, MPIDR, ISAR0 atomics field = the LSE question)
 *   3. GIC-400 init, virtual timer PPI 27 delivered as IRQ, count 10 ms ticks for 300 ms
 * Result line: "RESULT: PASS" or "RESULT: FAIL". On QEMU the shim then powers off via PSCI.
 * Builds for QEMU virt with -DPLAT_QEMU. UNTESTED ON REAL HARDWARE.
 */
#include "plat.h"
#include "../gicv2.h"

static volatile uint32_t irq_count, irq_other, irq_last;

/* No buttons on this tablet: never end in a dead loop. Wait, then PSCI SYSTEM_RESET (smc via ATF). */
static void reboot_later(uint32_t secs)
{
#ifndef PLAT_QEMU
	out_str("rebooting in ");
	out_hex(secs, 2);
	out_str(" s\n");
	uint64_t end = rsr("cntpct_el0") + rsr("cntfrq_el0") * secs;
	while (rsr("cntpct_el0") < end)
		;
	register uint64_t x0 __asm__("x0") = 0x84000009UL;	/* PSCI SYSTEM_RESET */
	__asm__ volatile(PSCI_CALL : "+r"(x0) : : "memory");
#else
	(void)secs;
#endif
}
static const char *stage;	/* set at runtime: no absolute pointers in data */

void exc_handler(uint64_t slot, uint64_t *regs)
{
	(void)regs;
	if (slot == 5) {		/* IRQ from current EL, SPx */
		uint32_t iar = gicv2_ack(), id = iar & 0x3ff;
		if (id == GIC_SPURIOUS)
			return;
		irq_last = id;
		if (id == TEST_INTID) {
			irq_count++;
			wsr("cntv_tval_el0", rsr("cntfrq_el0") / 100);
		} else {
			irq_other++;
		}
		gicv2_eoi(iar);
		return;
	}
	out_str("\nPANIC stage=");
	out_str(stage);
	out_kv("\nslot", slot);
	out_kv("esr ", rsr("esr_el1"));
	out_kv("elr ", rsr("elr_el1"));
	out_kv("far ", rsr("far_el1"));
	reboot_later(30);
	for (;;)
		__asm__ volatile("wfe");
}

void secondary_main(uint64_t idx)
{
	(void)idx;
	for (;;)
		__asm__ volatile("wfe");
}

static void off(int ok)
{
	out_str(ok ? "RESULT: PASS\n" : "RESULT: FAIL\n");
#ifdef PLAT_QEMU
	register uint64_t x0 __asm__("x0") = 0x84000008UL;	/* PSCI SYSTEM_OFF */
	__asm__ volatile(PSCI_CALL : "+r"(x0) : : "memory");
#endif
	reboot_later(60);
	for (;;)
		__asm__ volatile("wfe");
}

/* Print every property of a depth-1 node: strings as text, everything else as hex (max 32 bytes). */
static void dump_node(uintptr_t dtb, const char *node)
{
	const char *nm;
	uintptr_t v;
	uint32_t l;
	out_str("-- /");
	out_str(node);
	out_char('\n');
	for (int i = 0; mt_fdt_nth(dtb, node, i, &nm, &v, &l); i++) {
		volatile uint8_t *b = (volatile uint8_t *)v;
		int text = l > 1 && l <= 96 && b[l - 1] == 0;
		for (uint32_t k = 0; text && k + 1 < l; k++)
			if (b[k] < 0x20 || b[k] > 0x7e)
				text = 0;
		out_str(nm);
		out_str(" [");
		out_hex(l, 4);
		out_str("] ");
		if (text) {
			out_str((const char *)v);
		} else {
			for (uint32_t k = 0; k < l && k < 32; k++)
				out_hex(b[k], 2);
		}
		out_char('\n');
	}
}

void shim_main(uint64_t dtb)
{
	uintptr_t v;
	uint32_t l;

	stage = "start";

	/* Framebuffer address from LK's DTB: prefer split BE cells, fall back to the LE blob (U). */
	uintptr_t fbaddr = 0;
	uint32_t blob0 = 0, blob1 = 0;
	uintptr_t vh, vl;
	uint32_t lh, ll;
	if (mt_fdt_prop(dtb, "chosen", "atag,videolfb-fb_base_h", &vh, &lh) &&
	    mt_fdt_prop(dtb, "chosen", "atag,videolfb-fb_base_l", &vl, &ll)) {
		uint8_t *h = (uint8_t *)vh, *lo = (uint8_t *)vl;
		fbaddr = (uintptr_t)((uint64_t)(h[0] << 24 | h[1] << 16 | h[2] << 8 | h[3]) << 32 |
				     (uint32_t)(lo[0] << 24 | lo[1] << 16 | lo[2] << 8 | lo[3]));
	} else if (mt_fdt_prop(dtb, "chosen", "atag,videolfb", &v, &l) && l >= 8) {
		volatile uint8_t *b = (volatile uint8_t *)v;
		for (int i = 0; i < 8; i++)
			fbaddr |= (uintptr_t)b[i] << (8 * i);
		blob0 = b[0] | b[1] << 8 | b[2] << 16 | b[3] << 24;
		blob1 = l;
	}
	/* DRAM is 0x40000000..0x140000000 (4 GB, U); anything else is a parse error: do not write there */
	if (fbaddr < 0x40000000UL || fbaddr + 1536UL * 2048 * 4 > 0x140000000UL || (fbaddr & 0xfff))
		fbaddr = 0;
	out_init(fbaddr, 1536, 2048);	/* panel 1536x2048, stride = w*4 (U) */

	out_str("\niPadOS-Cappu shim M1, plat=" PLAT_NAME "\n");
	out_kv("dtb", dtb);
	out_kv("fb", fbaddr);
	out_kv("blob0", blob0);
	out_kv("bloblen", blob1);
	out_kv("CurrentEL", rsr("CurrentEL"));
	out_kv("MIDR", rsr("midr_el1"));
	out_kv("MPIDR", rsr("mpidr_el1"));
	out_kv("ISAR0", rsr("id_aa64isar0_el1"));
	out_kv("ISAR0.atomics", (rsr("id_aa64isar0_el1") >> 20) & 0xf);	/* 2 = LSE present, 0 = none */
	out_kv("PFR0", rsr("id_aa64pfr0_el1"));
	out_kv("MMFR0", rsr("id_aa64mmfr0_el1"));
	out_kv("MMFR1", rsr("id_aa64mmfr1_el1"));
	out_kv("MMFR1.pan", (rsr("id_aa64mmfr1_el1") >> 20) & 0xf);	/* 0 = no PAN, 1/2 = PAN present (xnu patch 0083 v3 needs this) */
	out_kv("CNTFRQ", rsr("cntfrq_el0"));

	dump_node(dtb, "chosen");
	dump_node(dtb, "memory");

	stage = "gic";
	gicv2_dist_init();
	gicv2_cpu_init();
	out_kv("GICD_TYPER", g_rd(GICD_BASE_MT8176 + GICD_TYPER));

	stage = "timer";
	gicv2_enable_irq(TEST_INTID, 0xa0);
	wsr("cntv_tval_el0", rsr("cntfrq_el0") / 100);
	wsr("cntv_ctl_el0", 1);
	isb();
	__asm__ volatile("msr daifclr, #2" ::: "memory");
	uint64_t end = rsr("cntpct_el0") + rsr("cntfrq_el0") * 3 / 10;
	while (rsr("cntpct_el0") < end)
		;
	__asm__ volatile("msr daifset, #2" ::: "memory");
	wsr("cntv_ctl_el0", 0);

	out_kv("irqs", irq_count);
	out_kv("other", irq_other);
	out_kv("last", irq_last);
	off(irq_count >= 20 && irq_count <= 35 && !irq_other);	/* ~30 expected */
}
