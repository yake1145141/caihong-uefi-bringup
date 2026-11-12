#!/bin/sh
# Build a FAT32 disk image containing the BYDJ ARM PE, ready to be written to
# a USB mass-storage device or a device partition.
#
# The PE is an ISO9660 image; UEFI cannot boot ISO directly.  It needs a FAT
# filesystem with \EFI\BOOT\BOOTAA64.EFI.  boot.wim is 896 MB so a 1.2 GB
# FAT32 volume is enough (single-file limit 4 GB is not hit).
#
# Runs on the Linux build host (mkfs.vfat + 7z, no admin privileges needed).
set -eu

ISO=/root/data/BYDJ-PE-v4.0.2.iso
WORK=/root/data/pe-fat
IMG=/root/data/BYDJ-PE-arm-fat32.img
SIZE_MB=1200

rm -rf "$WORK"
mkdir -p "$WORK/src" "$WORK/mnt"

echo "=== extracting ISO ==="
7z x -y -o"$WORK/src" "$ISO" > /root/data/pe-extract.log 2>&1
ls -l "$WORK/src/efi/boot/bootaa64.efi"
echo "boot.wim: $(stat -c %s "$WORK/src/sources/boot.wim") bytes"

echo "=== creating sparse ${SIZE_MB} MB image ==="
truncate -s "${SIZE_MB}M" "$IMG"

echo "=== mkfs.vfat ==="
mkfs.vfat -F 32 -n CAIHONGPE -s 4 "$IMG" > /root/data/pe-mkfs.log 2>&1
cat /root/data/pe-mkfs.log

echo "=== copying files ==="
mount -o loop "$IMG" "$WORK/mnt"
cp -r "$WORK/src/." "$WORK/mnt/"
sync
echo "=== layout ==="
ls -la "$WORK/mnt" | head -12
echo "--- EFI ---"
find "$WORK/mnt/efi" -type f | head -10
echo "--- sources ---"
ls -l "$WORK/mnt/sources"
df -h "$WORK/mnt" | tail -1
umount "$WORK/mnt"

echo "=== result ==="
ls -l "$IMG"
sha256sum "$IMG"
