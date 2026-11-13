#!/usr/bin/env python3
"""
Fix the caihong AcpiTables.inf FILE_GUID.

AcpiPlatformDxe reads the ACPI table storage FFS file using
PcdGetPtr (PcdAcpiTableStorageFile), whose default is
  7E374E25-8E01-4FEE-87F2-390C23C606CD
The original enable_caihong_acpi.py wrote ...CE (last byte changed to avoid a
collision with the pong platform).  That one-byte mismatch means ReadSection()
never finds our FFS file, so none of the six AML tables are installed and the
RSDP handed to the Windows boot manager is empty.

There is no collision to avoid: pong's AcpiTables.inf is in a different build
entirely.  Use the PCD default GUID.
"""
import pathlib
import sys

INF = pathlib.Path(
    "/root/data/caihong-work/uefi/Silicium-ACPI/Platforms/OnePlus/caihong/AcpiTables.inf"
)
GOOD = "7E374E25-8E01-4FEE-87F2-390C23C606CD"
BAD = "7E374E25-8E01-4FEE-87F2-390C23C606CE"


def main():
    t = INF.read_text(encoding="utf-8", errors="surrogateescape")
    if BAD in t:
        t = t.replace(BAD, GOOD)
        INF.write_text(t, encoding="utf-8", errors="surrogateescape")
        print("fixed:", BAD, "->", GOOD)
    elif GOOD in t:
        print("already correct:", GOOD)
    else:
        print("ERROR: unexpected FILE_GUID in", INF)
        return 1
    print([l.strip() for l in t.splitlines() if "FILE_GUID" in l])
    return 0


if __name__ == "__main__":
    sys.exit(main())
