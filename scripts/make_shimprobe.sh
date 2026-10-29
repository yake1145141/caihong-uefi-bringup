#!/bin/sh
# Build the BootShim progress probe (scripts/shimprobe.S) and package it with
# the current firmware volume as a v4 boot image.
#
# SPDX-License-Identifier: GPL-2.0-only
#
# Usage (in the Mu-Qcom checkout, after a successful build):
#   sh make_shimprobe.sh
#
# Output: ./Mu-shimprobe.img
#   = shimprobe.bin ++ CAIHONG_UEFI.fd, gzipped, in a header-v4 boot image.
set -eu
CDPATH=

TARGET_BUILD_MODE="${TARGET_BUILD_MODE:-RELEASE}"
FD="./Build/caihongPkg/${TARGET_BUILD_MODE}_CLANGPDB/FV/CAIHONG_UEFI.fd"
SRC="${SHIM_SRC:-./shimprobe.S}"
BIN="./shimprobe.bin"
PAYLOAD="./shimprobe_payload.bin"
OUT="./Mu-shimprobe.img"

UEFI_BASE="${UEFI_BASE:-0xA7000000}"
UEFI_SIZE="${UEFI_SIZE:-0x00400000}"

[ -f "$FD" ]  || { echo "missing $FD" >&2; exit 2; }
[ -f "$SRC" ] || { echo "missing $SRC" >&2; exit 2; }

echo "== assembling $SRC  (UEFI_BASE=$UEFI_BASE UEFI_SIZE=$UEFI_SIZE)"
clang --target=aarch64-none-elf -c "$SRC" \
	-DUEFI_BASE="$UEFI_BASE" -DUEFI_SIZE="$UEFI_SIZE" -o shimprobe.o
llvm-objcopy -O binary shimprobe.o "$BIN"

magic=$(dd if="$BIN" bs=1 skip=56 count=4 2>/dev/null)
echo "== shim: $(wc -c < "$BIN") bytes, magic at 0x38 = '$magic'"
[ "$magic" = "ARMd" ] || { echo "ERROR: bad Image magic" >&2; exit 1; }

echo "== payload: shim + FD"
cat "$BIN" "$FD" > "$PAYLOAD"
echo "   $(wc -c < "$PAYLOAD") bytes"

echo "== packaging (header v4, gzip)"
gzip -c < "$PAYLOAD" > "$PAYLOAD.gz"
python3 ./Resources/Scripts/mkbootimg.py \
	--kernel "$PAYLOAD.gz" \
	--ramdisk ./Resources/ramdisk \
	--kernel_offset 0x00000000 \
	--ramdisk_offset 0x00000000 \
	--tags_offset 0x00000000 \
	--os_version 13.0.0 \
	--os_patch_level "$(date '+%Y-%m')" \
	--header_version 4 \
	-o "$OUT" || { echo "mkbootimg failed" >&2; exit 1; }

echo "== wrote $OUT ($(wc -c < "$OUT") bytes)"
