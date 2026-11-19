m1-boot.img      M1 diagnostic shim, gzip kernel + appended DTB (same layout as the reference TWRP images)
m1-boot-raw.img  same, kernel not gzipped (fallback if LK rejects gzip)
ONLY for: fastboot boot <image>. NEVER fastboot flash these. Built from shim/mt8176 by tools/mkboot_mt8176.py.
