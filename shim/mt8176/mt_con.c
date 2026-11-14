/* Output: UART always, framebuffer text console when /chosen gave us an address. */
#include "plat.h"
#include "../font.h"

#define SCALE 2
static volatile uint32_t *fb;
static uint32_t fbw, fbh, col, row;

static void uart_put(char c)
{
#if UART_PL011
	while (*(volatile uint32_t *)(UART_BASE + 0x18) & (1 << 5))	/* TXFF */
		;
	*(volatile uint32_t *)(UART_BASE + 0x00) = c;
#else
	for (int i = 0; i < 100000 && !(*(volatile uint32_t *)(UART_BASE + 0x14) & (1 << 5)); i++)	/* LSR.THRE */
		;
	*(volatile uint32_t *)(UART_BASE + 0x00) = c;
#endif
}

void out_init(uintptr_t fb_base, uint32_t w, uint32_t h)
{
	if (!fb_base)
		return;
	fb = (volatile uint32_t *)fb_base;
	fbw = w;
	fbh = h;
	for (uint32_t i = 0; i < w * h; i++)
		fb[i] = 0xff000040;
}

static void fb_put(char c)
{
	uint32_t cw = 8 * SCALE, ch = 16 * SCALE;
	if (c == '\n' || (col + 2) * cw > fbw) {
		col = 0;
		row++;
		if (c == '\n')
			return;
	}
	if ((row + 1) * ch > fbh)
		return;
	if (c < 0x20 || c > 0x7e)
		c = '?';
	const unsigned char *g = font8x16[c - 0x20];
	for (int gy = 0; gy < 16; gy++)
		for (int gx = 0; gx < 8; gx++)
			for (int sy = 0; sy < SCALE; sy++)
				for (int sx = 0; sx < SCALE; sx++)
					fb[(row * ch + gy * SCALE + sy) * fbw + col * cw + gx * SCALE + sx] =
						(g[gy] & (0x80 >> gx)) ? 0xffffffff : 0xff000040;
	col++;
}

void out_char(char c)
{
	if (c == '\n')
		uart_put('\r');
	uart_put(c);
	if (fb)
		fb_put(c);
}

void out_str(const char *s)
{
	while (*s)
		out_char(*s++);
}

void out_hex(uint64_t v, int digits)
{
	static const char h[] = "0123456789abcdef";
	for (int i = digits - 1; i >= 0; i--)
		out_char(h[(v >> (4 * i)) & 0xf]);
}

void out_kv(const char *k, uint64_t v)
{
	out_str(k);
	out_str(" = 0x");
	out_hex(v, 16);
	out_char('\n');
}
