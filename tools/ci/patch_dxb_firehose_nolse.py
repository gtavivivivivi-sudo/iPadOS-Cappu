#!/usr/bin/env python3
"""Append an arm64-only -march override to libfirehose_kernel's xcconfig, via dxb/build.sh.

Why: libfirehose_kernel.a (part of libdispatch, built by darwin-xnu-build's build_libdispatch()
from a SEPARATE apple-oss-distributions/libdispatch clone - not patches/) is compiled with
plain "-target arm64-apple-macos15.0" and no -march/-mcpu, which silently defaults to a baseline
that still has LSE on this SDK - the same root cause patches/0083 already fixes on the xnu
side. Confirmed via tools/scan_lse.py --syms (run 43705548522): all 11 real LSE hits left after
0083 (the 12th, in K256, is a SHA-256-constants false positive) are in _firehose_buffer_* /
_firehose_merge_updates, i.e. exactly this library.

First attempt (run 43763875572) passed "OTHER_CFLAGS[arch=arm64]=..." straight on the xcodebuild
command line in the workflow. FAILED - xcodebuild's own command-line arg parser splits a
KEY[cond=x]=value argument on the FIRST "=" only, reads the key as "OTHER_CFLAGS[arch" and hands
clang the broken leftover "arm64]=-march=..." as a literal filename.

Fix here: append the override straight into libfirehose_kernel.xcconfig instead, via a line
inserted into dxb/build.sh right after the two existing sed calls that already edit that same
file for path substitutions. xcconfig's own KEY[arch=value] qualifier syntax handles a
conditional override correctly (unlike the xcodebuild command line), and $(OTHER_CFLAGS) makes
the arm64-only line inherit the project's base flags (-mkernel -nostdinc -Wno-packed) instead of
replacing them.
"""
import sys

if len(sys.argv) != 2:
    sys.exit("usage: patch_dxb_firehose_nolse.py <path to dxb/build.sh>")

path = sys.argv[1]
src = open(path).read()

anchor = (
    'sed -i \'\' \'s|$(SDKROOT)/usr/local/include|$(FAKEROOT_DIR)/usr/local/include|g\' '
    '"${SRCROOT}/xcodeconfig/libfirehose_kernel.xcconfig"'
)
if anchor not in src:
    sys.exit("anchor line not found in build.sh - did DXB's build_libdispatch() change?")

addition_line = (
    "echo 'OTHER_CFLAGS[arch=arm64] = $(OTHER_CFLAGS) -march=armv8.1-a+crypto+nolse' "
    '>> "${SRCROOT}/xcodeconfig/libfirehose_kernel.xcconfig"'
)

# Match the anchor line's own leading whitespace so the inserted line sits at the same
# indentation inside build_libdispatch().
line_start = src.rfind("\n", 0, src.index(anchor)) + 1
indent = src[line_start:src.index(anchor)]

new_src = src.replace(anchor, anchor + "\n" + indent + addition_line, 1)
if new_src.count(addition_line) != 1:
    sys.exit("insertion did not happen exactly once - aborting")

open(path, "w").write(new_src)
print("patched:", path)
