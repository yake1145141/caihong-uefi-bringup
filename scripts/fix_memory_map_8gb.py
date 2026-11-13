#!/usr/bin/env python3
"""
Complete the caihong memory map for an 8 GB device.

Evidence (device's own DTB, Resources/DTBs/caihong.dtb):
  * DRAM base is 0x80000000, device has 8 GB  -> top is 0x2_8000_0000
  * highest reserved-memory region ends at 0xFFE00000 (the 4 GB boundary);
    nothing is reserved above 4 GB
  * the low 4 GB carries, among others:
        trust-ui-vm @0xF3800000 +0x0440_0000
        oem-vm      @0xF7C00000 +0x04C0_0000
        ramoops     @0xFE5C0000 +0x0024_0000
        llcc-lpi    @0xFF800000 +0x0060_0000

The existing MemoryMapLib.c describes only up to 0xF3800000 and marks a single
442 MB region as Conv, so Windows sees ~442 MB of usable RAM and cannot build a
ramdisk for the 896 MB boot.wim.

This patch therefore:
  1. adds the four missing reservations in 0xF3800000..0x1_0000_0000
  2. adds the free gaps in that window as Conv
  3. adds the entire 6 GB above 4 GB as Conv
Every address comes from the DTB; nothing is invented.
"""
import pathlib
import sys

P = pathlib.Path(
    "/root/data/caihong-work/uefi/Platforms/OnePlus/caihongPkg/Library/"
    "MemoryMapLib/MemoryMapLib.c"
)

MARK = "CAIHONG_8GB_MAP"

ANCHOR = ('  {"TZApps_Reserved",     0xD8800000, 0x1B000000, AddMem, MEM_RES, '
          'UNCACHEABLE, Reserv, UNCACHED_UNBUFFERED_XN},')

INSERT = """  // CAIHONG_8GB_MAP: reservations and free DRAM above 0xF3800000, all taken
  // from the device's own DTB (highest reserved region ends at 0xFFE00000).
  {"TrustUiVm_Reserved",  0xF3800000, 0x00440000, AddMem, MEM_RES, SYS_MEM_CAP, Reserv, WRITE_BACK_XN},
  {"OemVm_Reserved",      0xF7C00000, 0x004C0000, AddMem, MEM_RES, SYS_MEM_CAP, Reserv, WRITE_BACK_XN},
  {"RamOops_Reserved",    0xFE5C0000, 0x00024000, AddMem, MEM_RES, SYS_MEM_CAP, Reserv, WRITE_BACK_XN},
  {"LlccLpi_Reserved",    0xFF800000, 0x00060000, AddMem, MEM_RES, SYS_MEM_CAP, Reserv, WRITE_BACK_XN},
  {"FreeHigh1",           0xFC800000, 0x01DC0000, AddMem, SYS_MEM, SYS_MEM_CAP, Conv,   WRITE_BACK_XN},
  {"FreeHigh2",           0xFE800000, 0x01000000, AddMem, SYS_MEM, SYS_MEM_CAP, Conv,   WRITE_BACK_XN},
  {"FreeHigh3",           0xFFE00000, 0x00200000, AddMem, SYS_MEM, SYS_MEM_CAP, Conv,   WRITE_BACK_XN},
  // 6 GB of plain DRAM above the 4 GB boundary: 0x1_0000_0000 .. 0x2_8000_0000
  {"SystemRamAbove4G",    0x100000000, 0x180000000, AddMem, SYS_MEM, SYS_MEM_CAP, Conv,  WRITE_BACK_XN},"""

def main():
    t = P.read_text(encoding="utf-8", errors="surrogateescape")
    if MARK in t:
        print("already patched")
        return 0
    if ANCHOR not in t:
        print("ERROR: anchor line not found in", P)
        return 1
    t = t.replace(ANCHOR, ANCHOR + "\n" + INSERT, 1)
    P.write_text(t, encoding="utf-8", errors="surrogateescape")
    print("inserted 8 GB DRAM description")

    # Report the resulting conventional total.
    conv = 0
    for line in t.splitlines():
        if ", Conv," in line and line.strip().startswith("{"):
            try:
                parts = line.split(",")
                base = int(parts[1].strip(), 16)
                size = int(parts[2].strip(), 16)
                conv += size
                print("  Conv 0x%010X + 0x%X" % (base, size))
            except Exception:
                pass
    print("total Conv = 0x%X (%d MB)" % (conv, conv // (1024 * 1024)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
