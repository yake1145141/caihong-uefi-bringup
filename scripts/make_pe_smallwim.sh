#!/bin/sh
# Build a small FAT32 PE image whose boot.wim is TRUNCATED to the first 4 MB.
#
# Purpose: determine whether the 900E happens before or after the Windows loader
# creates the ramdisk and parses the WIM.
#   * the WIM header stays intact, so bootmgr opens it and starts the ramdisk
#   * the resource table is cut, so it must fail later and (hopefully) show an
#     error on the panel instead of dying silently
#
# Resulting image is ~128 MB, so flashing userdata is quick.
set -eu

ISO=/root/data/BYDJ-PE-v4.0.2.iso
WORK=/root/data/pe-small
IMG=/root/data/BYDJ-PE-smallwim.img
SIZE_MB=128
WIM_KEEP_MB=4

rm -rf "$WORK"
mkdir -p "$WORK/src" "$WORK/mnt"

echo "=== extracting ISO ==="
7z x -y -o"$WORK/src" "$ISO" > /root/data/pe-small-extract.log 2>&1

WIM="$WORK/src/sources/boot.wim"
echo "original boot.wim: $(stat -c %s "$WIM") bytes"

echo "=== truncating boot.wim to first ${WIM_KEEP_MB} MB ==="
dd if="$WIM" of="$WORK/boot-head.wim" bs=1M count="$WIM_KEEP_MB" status=none
mv "$WORK/boot-head.wim" "$WIM"
echo "new boot.wim: $(stat -c %s "$WIM") bytes"

echo "=== creating ${SIZE_MB} MB FAT32 image ==="
truncate -s "${SIZE_MB}M" "$IMG"
mkfs.vfat -F 32 -n CAIHONGPE -s 4 "$IMG" > /root/data/pe-small-mkfs.log 2>&1
cat /root/data/pe-small-mkfs.log

echo "=== copying files ==="
mount -o loop "$IMG" "$WORK/mnt"
cp -r "$WORK/src/." "$WORK/mnt/"
sync
echo "--- layout ---"
ls -l "$WORK/mnt/sources" | head -5
ls -l "$WORK/mnt/efi/boot/bootaa64.efi"
df -h "$WORK/mnt" | tail -1
umount "$WORK/mnt"

echo "=== result ==="
ls -l "$IMG"
sha256sum "$IMG"
