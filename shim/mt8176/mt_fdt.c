/* Find a property of a depth-1 node (e.g. /chosen) in the DTB LK hands over. Byte-wise reads only. */
#include "plat.h"

static uint32_t be32(uintptr_t a)
{
	volatile uint8_t *b = (volatile uint8_t *)a;
	return (uint32_t)b[0] << 24 | b[1] << 16 | b[2] << 8 | b[3];
}

static int streq(const char *a, const char *b)
{
	while (*a && *a == *b)
		a++, b++;
	return *a == *b;
}

/* node name matches "chosen" or "chosen@0" */
static int nodeeq(const char *name, const char *want)
{
	while (*want && *name == *want)
		name++, want++;
	return !*want && (*name == 0 || *name == '@');
}

int mt_fdt_prop(uintptr_t fdt, const char *node, const char *prop, uintptr_t *val, uint32_t *len)
{
	if (!fdt || be32(fdt) != 0xd00dfeed)
		return 0;
	uintptr_t p = fdt + be32(fdt + 8), strings = fdt + be32(fdt + 12);
	int depth = 0, in = 0;

	for (;;) {
		uint32_t tok = be32(p);
		p += 4;
		if (tok == 1) {
			const char *n = (const char *)p;
			depth++;
			if (depth == 2)
				in = nodeeq(n, node);
			while (*(volatile const char *)p)
				p++;
			p = (p + 4) & ~3UL;
		} else if (tok == 2) {
			if (depth == 2 && in)
				return 0;
			depth--;
		} else if (tok == 3) {
			uint32_t l = be32(p), off = be32(p + 4);
			if (in && depth == 2 && streq((const char *)(strings + off), prop)) {
				*val = p + 8;
				*len = l;
				return 1;
			}
			p = (p + 8 + l + 3) & ~3UL;
		} else if (tok != 4) {
			return 0;
		}
	}
}

/* idx-th property of a depth-1 node (name matched like mt_fdt_prop). Returns 1 and fills name/val/len, 0 at the end. */
int mt_fdt_nth(uintptr_t fdt, const char *node, int idx, const char **name, uintptr_t *val, uint32_t *len)
{
	if (!fdt || be32(fdt) != 0xd00dfeed)
		return 0;
	uintptr_t p = fdt + be32(fdt + 8), strings = fdt + be32(fdt + 12);
	int depth = 0, in = 0, n = 0;

	for (;;) {
		uint32_t tok = be32(p);
		p += 4;
		if (tok == 1) {
			const char *nm = (const char *)p;
			depth++;
			if (depth == 2)
				in = nodeeq(nm, node);
			while (*(volatile const char *)p)
				p++;
			p = (p + 4) & ~3UL;
		} else if (tok == 2) {
			if (depth == 2 && in)
				return 0;
			depth--;
		} else if (tok == 3) {
			uint32_t l = be32(p), off = be32(p + 4);
			if (in && depth == 2 && n++ == idx) {
				*name = (const char *)(strings + off);
				*val = p + 8;
				*len = l;
				return 1;
			}
			p = (p + 8 + l + 3) & ~3UL;
		} else if (tok != 4) {
			return 0;
		}
	}
}
