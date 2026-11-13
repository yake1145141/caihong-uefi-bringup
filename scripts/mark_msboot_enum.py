#!/usr/bin/env python3
"""
Promote the MsBootPolicy device-enumeration messages to DEBUG_ERROR so they
survive the console filter (PcdDebugPrintErrorLevel = 0x80000040, ERROR|WARN).

We need to know, on the real device, whether the FAT32 PE volume written to
userdata is enumerated as a SimpleFileSystem handle at all:

    Found %d handles
    %d handles survived filtering
    No handles survived filtering!
    Selecting device <path>
    ... was blocked from booting
"""
import pathlib
import sys

P = pathlib.Path(
    "/root/data/caihong-work/uefi/Common/Mu/PcBdsPkg/MsBootPolicy/MsBootPolicy.c"
)


def main():
    t = P.read_text(encoding="utf-8", errors="surrogateescape")
    if "CAIHONG_MSBOOT_DEBUG" in t:
        print("already patched")
        return 0

    replacements = [
        ('DEBUG ((DEBUG_INFO, "Found %d handles\\n", HandleCount));',
         'DEBUG ((DEBUG_ERROR, "[MSBOOT] Found %d handles\\n", HandleCount));'),
        ('DEBUG ((DEBUG_INFO, "%d handles survived filtering\\n", HandleCount));',
         'DEBUG ((DEBUG_ERROR, "[MSBOOT] %d handles survived filtering\\n", HandleCount));'),
        ('DEBUG ((DEBUG_WARN, "No handles survived filtering!\\n"));',
         'DEBUG ((DEBUG_ERROR, "[MSBOOT] No handles survived filtering!\\n"));'),
        ('DEBUG ((DEBUG_INFO, "Selecting device %s", TmpStr));',
         'DEBUG ((DEBUG_ERROR, "[MSBOOT] Selecting device %s", TmpStr));'),
        ('DEBUG ((DEBUG_WARN, "Device %s\\n", TmpStr));',
         'DEBUG ((DEBUG_ERROR, "[MSBOOT] Device %s\\n", TmpStr));'),
        ('DEBUG ((DEBUG_WARN, " was blocked from booting\\n"));',
         'DEBUG ((DEBUG_ERROR, "[MSBOOT] was blocked from booting\\n"));'),
        ('DEBUG ((DEBUG_ERROR, "Unable to locate any %g handles - code=%r\\n", ByGuid, Status));',
         'DEBUG ((DEBUG_ERROR, "[MSBOOT] Unable to locate any %g handles - code=%r\\n", ByGuid, Status));'),
    ]
    n = 0
    for old, new in replacements:
        if old in t:
            t = t.replace(old, new, 1)
            n += 1
        else:
            print("WARN: pattern not found:", old[:60])

    t = t.replace("/**@file This module implements the Microsoft Boot Policy.",
                  "// CAIHONG_MSBOOT_DEBUG: enumeration messages promoted to ERROR\n"
                  "/**@file This module implements the Microsoft Boot Policy.", 1)
    P.write_text(t, encoding="utf-8", errors="surrogateescape")
    print("patched %d sites in %s" % (n, P))
    return 0


if __name__ == "__main__":
    sys.exit(main())
