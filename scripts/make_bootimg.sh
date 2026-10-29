#!/bin/sh
# Repack the caihong firmware as an Android boot image, parameterised by header
# version.
#
# SPDX-License-Identifier: GPL-2.0-only
#
# WHY THIS EXISTS
# ---------------
# The stock boot.img on this device is header_version 4 (GKI: kernel only,
# ramdisk lives in vendor_boot, ramdisk_size = 0).  Mu-Silicium's stock script
# emits header_version 1, and the device's ABL never boots it -- it lands back
# in fastboot within a few seconds without ever lighting the panel, which looks
# like the loader rejects the image outright rather than executing it.
#
# This script lets the same payload be emitted as v1 or v4 so the two can be
# compared on hardware.
#
# Usage (in the Mu-Qcom checkout, after a successful build):
#   sh make_bootimg.sh <header_version> [gzip|plain]
# e.g.
#   sh make_bootimg.sh 4 plain
#   sh make_bootimg.sh 4 gzip
#
# Notes:
#   * GKI v4 kernels must NOT be compressed by us -- ABL decompresses when the
#     image asks for it; 'gzip' here means we gzip the payload ourselves, which
#     is what Mu-Silicium does.  Both are offered because they behave
#     differently across Qualcomm generations.
#   * The kernel payload is always  BootShim.bin ++ CAIHONG_UEFI.fd.
set -eu
CDPATH=

HV="${1:?usage: $0 <header_version 1|4> [gzip|plain]}"
MODE="${2:-plain}"
case "$HV" in 1|4) ;; *) echo "header_version must be 1 or 4" >&2; exit 64 ;; esac
case "$MODE" in gzip|plain) ;; *) echo "mode must be gzip or plain" >&2; exit 64 ;; esac

TARGET_BUILD_MODE="${TARGET_BUILD_MODE:-RELEASE}"
FD="./Build/caihongPkg/${TARGET_BUILD_MODE}_CLANGPDB/FV/CAIHONG_UEFI.fd"
SHIM="./BootShim/BootShim.bin"
RAW="./Resources/bootpayload_v${HV}_${MODE}.bin"
OUT="./Mu-caihong-v${HV}-${MODE}.img"

[ -f "$FD" ]   || { echo "missing $FD" >&2; exit 2; }
[ -f "$SHIM" ] || { echo "missing $SHIM" >&2; exit 2; }

cat "$SHIM" "$FD" > "$RAW.plain"
if [ "$MODE" = "gzip" ]; then
	gzip -c < "$RAW.plain" > "$RAW"
else
	cp "$RAW.plain" "$RAW"
fi
rm -f "$RAW.plain"

echo "shim     : $(wc -c < "$SHIM") bytes"
echo "fd       : $(wc -c < "$FD") bytes"
echo "payload  : $(wc -c < "$RAW") bytes ($MODE)"

python3 ./Resources/Scripts/mkbootimg.py \
	--kernel "$RAW" \
	--ramdisk ./Resources/ramdisk \
	--kernel_offset 0x00000000 \
	--ramdisk_offset 0x00000000 \
	--tags_offset 0x00000000 \
	--os_version 13.0.0 \
	--os_patch_level "$(date '+%Y-%m')" \
	--header_version "$HV" \
	-o "$OUT" || { echo "mkbootimg failed for header_version $HV" >&2; exit 1; }

echo "wrote $OUT ($(wc -c < "$OUT") bytes)"
