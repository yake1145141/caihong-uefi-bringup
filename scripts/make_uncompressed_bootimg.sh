#!/bin/sh
# Build an UNCOMPRESSED caihong boot image variant.
#
# SPDX-License-Identifier: GPL-2.0-only
#
# Why: the standard Mu-Silicium packaging gzips (BootShim + FD) into the boot
# image "kernel".  If this device's ABL does not decompress the kernel, it
# would jump straight into gzip data and fault immediately -- which matches the
# observed behaviour (fastboot reports "Booting OKAY", then the device drops
# back to fastboot a few seconds later).
#
# BootShim deliberately embeds the "ARM\x64" magic of an AArch64 Image header,
# which suggests the loader validates that header.  A gzip stream hides it.
#
# This script emits an uncompressed variant for comparison:
#   kernel = BootShim.bin ++ CAIHONG_UEFI.fd      (4 MB + 144 bytes)
#
# Usage (in the Mu-Qcom checkout, after a successful build):
#   sh make_uncompressed_bootimg.sh
set -eu
CDPATH=

# Default it explicitly: with `set -u` the case label below only *tests* the
# variable, it does not assign it, so FD would reference an unset name.
TARGET_BUILD_MODE="${TARGET_BUILD_MODE:-RELEASE}"
FD="./Build/caihongPkg/${TARGET_BUILD_MODE}_CLANGPDB/FV/CAIHONG_UEFI.fd"
SHIM="./BootShim/BootShim.bin"
OUT="./Mu-caihong-uncompressed.img"
PAYLOAD="./Resources/bootpayload_uncompressed.bin"

[ -f "$FD" ]   || { echo "missing $FD" >&2; exit 2; }
[ -f "$SHIM" ] || { echo "missing $SHIM" >&2; exit 2; }

echo "shim  : $(wc -c < "$SHIM") bytes"
echo "fd    : $(wc -c < "$FD") bytes"

cat "$SHIM" "$FD" > "$PAYLOAD"
echo "payload: $(wc -c < "$PAYLOAD") bytes (uncompressed)"

python3 ./Resources/Scripts/mkbootimg.py \
	--kernel "$PAYLOAD" \
	--ramdisk ./Resources/ramdisk \
	--kernel_offset 0x00000000 \
	--ramdisk_offset 0x00000000 \
	--tags_offset 0x00000000 \
	--os_version 13.0.0 \
	--os_patch_level "$(date '+%Y-%m')" \
	--header_version 1 \
	-o "$OUT" || { echo "mkbootimg failed" >&2; exit 1; }

echo "wrote $OUT ($(wc -c < "$OUT") bytes)"
