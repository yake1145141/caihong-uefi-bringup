#!/usr/bin/env python3
"""
Build a FAT32 disk image containing a Windows ARM PE, ready to be written to a
USB drive (or later flashed to a partition) for booting from the caihong UEFI
boot menu.

Why this exists
---------------
The BYDJ-PE ISO is an ISO9660 image.  UEFI firmware cannot boot an ISO directly;
it needs a FAT filesystem with \\EFI\\BOOT\\BOOTAA64.EFI.  This script creates a
raw FAT32 volume containing exactly those files.

The volume is intentionally sized generously above the ISO's ~910 MB so that
boot.wim (896 MB) fits with room for the FAT metadata.  The result is a flat
image suitable for `dd`/fastboot flash to a partition, or for writing to a USB
mass-storage device.

Usage:
    python make_arm_pe_fat.py <source-drive-or-dir> <output.img> [size_mb]
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def copy_tree(src, dst_root):
    """Copy src (a directory) recursively into dst_root, preserving case."""
    for name in os.listdir(src):
        s = os.path.join(src, name)
        d = os.path.join(dst_root, name)
        if os.path.isdir(s):
            os.makedirs(d, exist_ok=True)
            copy_tree(s, d)
        else:
            shutil.copy2(s, d)
            print("   ", os.path.relpath(d, dst_root))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    src = sys.argv[1]
    out = sys.argv[2]
    size_mb = int(sys.argv[3]) if len(sys.argv) > 3 else 1200

    if not os.path.isdir(src):
        print("source is not a directory:", src)
        return 2

    # Verify the required ARM64 loader is present before doing any work.
    loader = os.path.join(src, "efi", "boot", "bootaa64.efi")
    if not os.path.isfile(loader):
        print("ERROR: missing", loader)
        return 2
    data = open(loader, "rb").read()
    pe = int.from_bytes(data[0x3C:0x40], "little")
    machine = int.from_bytes(data[pe + 4:pe + 6], "little")
    if machine != 0xAA64:
        print("ERROR: bootaa64.efi is not ARM64 (machine=0x%X)" % machine)
        return 2
    print("ARM64 loader verified: 0xAA64")

    # 1. Create a sparse raw image.
    with open(out, "wb") as f:
        f.truncate(size_mb * 1024 * 1024)
    print("created sparse image:", out, size_mb, "MB")

    # 2. Build a VHD holding that image, attach it, format FAT32, copy files,
    #    then detach.  On Windows this uses the built-in diskpart/Hyper-V
    #    tooling via PowerShell; ImageMagick-style mtools is not required.
    ps = os.path.join(HERE, "make_arm_pe_fat.ps1")
    cmd = [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", ps, "-ImagePath", os.path.abspath(out),
        "-Source", os.path.abspath(src), "-SizeMB", str(size_mb),
    ]
    print("running:", " ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
