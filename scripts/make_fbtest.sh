#!/bin/sh
# Build and package the framebuffer probe (scripts/fbtest.S) as a v4 boot image.
#
# SPDX-License-Identifier: GPL-2.0-only
#
# Usage (in the Mu-Qcom checkout, clang + lld + mkbootimg available):
#   sh make_fbtest.sh
#
# Output: ./Mu-fbtest.img
set -eu
CDPATH=

SRC="${FB_SRC:-./fbtest.S}"
OBJ="./fbtest.o"
BIN="./fbtest.bin"
OUT="./Mu-fbtest.img"

[ -f "$SRC" ] || { echo "missing $SRC" >&2; exit 2; }

echo "== assembling $SRC"
clang --target=aarch64-none-elf -c "$SRC" -o "$OBJ"
llvm-objcopy -O binary "$OBJ" "$BIN"

size=$(wc -c < "$BIN" | tr -d ' ')
echo "== raw binary: $size bytes"

# Sanity: the Image magic must sit at offset 0x38, otherwise the loader will
# reject the image the same way it rejected our v1 boot image.
magic=$(dd if="$BIN" bs=1 skip=56 count=4 2>/dev/null)
echo "== magic at 0x38: $magic"
[ "$magic" = "ARMd" ] || { echo "ERROR: ARM64 Image magic missing at 0x38" >&2; exit 1; }

echo "== packaging as Android boot image header v4"
python3 ./Resources/Scripts/mkbootimg.py \
	--kernel "$BIN" \
	--ramdisk ./Resources/ramdisk \
	--kernel_offset 0x00000000 \
	--ramdisk_offset 0x00000000 \
	--tags_offset 0x00000000 \
	--os_version 13.0.0 \
	--os_patch_level "$(date '+%Y-%m')" \
	--header_version 4 \
	-o "$OUT" || { echo "mkbootimg failed" >&2; exit 1; }

echo "== wrote $OUT ($(wc -c < "$OUT") bytes)"
