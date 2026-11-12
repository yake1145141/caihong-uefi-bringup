#!/usr/bin/env python3
"""
Definitively determine whether the *working* caihong UEFI carries ACPI tables.

Windows on ARM requires ACPI (RSDP/XSDT, MADT/GICC, GTDT, ...).  A plain
string scan of the 4 MB outer FD is misleading because the inner firmware
volume (all DXE drivers + ACPI tables + BDS strings) is LZMA-compressed inside
an EFI_SECTION_GUID_DEFINED FFS file.  This script walks the FV/FFS/section
structure, decompresses that section, and scans the result.

The LZMA GUID used by GenFds is ee4e5898-3914-4259-9d6e-dc7bd79403cf.
"""
import lzma
import struct
import sys
import uuid

PATH = sys.argv[1] if len(sys.argv) > 1 else \
    r"E:\caihong-windows\work\working-uefi-payload.bin"

LZMA_GUID = uuid.UUID("ee4e5898-3914-4259-9d6e-dc7bd79403cf")

d = open(PATH, "rb").read()
print("payload:", len(d), "bytes")

# ---- locate the outer FV by its _FVH signature ----
fv = d.find(b"_FVH")
if fv < 0:
    print("ERROR: no _FVH found")
    sys.exit(1)
fv -= 0x28
hdr_len = struct.unpack_from("<H", d, fv + 0x30)[0]
fv_len = struct.unpack_from("<Q", d, fv + 0x20)[0]
print("outer FV base: 0x%X  header_len=0x%X  length=0x%X" % (fv, hdr_len, fv_len))

# ---- walk FFS files ----
pos = fv + hdr_len
inner = None
files = []
while pos + 24 <= len(d) and pos < fv + fv_len:
    name = d[pos:pos + 16]
    ftype = d[pos + 18]
    size = d[pos + 20] | (d[pos + 21] << 8) | (d[pos + 22] << 16)
    if size < 24 or pos + size > len(d):
        break
    try:
        g = uuid.UUID(bytes_le=name)
    except Exception:
        g = None
    files.append((pos, ftype, size, g))
    print("  FFS @0x%06X type=0x%02X size=0x%-8X %s" % (pos, ftype, size, g))

    # FV_IMAGE file -> find its GUIDed section
    if ftype == 0x0B:
        s = pos + 24
        end = pos + size
        while s + 4 <= end:
            ssz = d[s] | (d[s + 1] << 8) | (d[s + 2] << 16)
            st = d[s + 3]
            if ssz < 4:
                break
            if st == 0x02 and s + 24 <= end:                 # GUID_DEFINED
                sg = uuid.UUID(bytes_le=d[s + 4:s + 20])
                doff = struct.unpack_from("<H", d, s + 20)[0]
                attrs = struct.unpack_from("<H", d, s + 22)[0]
                print("    GUIDed section: %s data_offset=%d attrs=0x%X" %
                      (sg, doff, attrs))
                if sg == LZMA_GUID:
                    payload = d[s + doff:s + ssz]
                    print("    LZMA payload: %d bytes, head %s" %
                          (len(payload), payload[:8].hex(" ")))
                    for fmt in (lzma.FORMAT_ALONE, lzma.FORMAT_AUTO):
                        try:
                            inner = lzma.decompress(payload, format=fmt)
                            print("    decompressed: %d bytes" % len(inner))
                            break
                        except Exception as e:
                            print("    %s failed: %s" % (fmt, e))
            s += (ssz + 3) & ~3
    pos += (size + 7) & ~7

if inner is None:
    print("ERROR: could not decompress inner FV")
    sys.exit(1)

open(r"E:\caihong-windows\work\working-uefi-inner.bin", "wb").write(inner)

print()
print("=== ACPI table signatures inside the INNER firmware volume ===")
sigs = [b"RSD PTR ", b"FACP", b"APIC", b"GTDT", b"DBG2", b"PPTT",
        b"DSDT", b"SSDT", b"MCFG", b"RSDT", b"XSDT", b"BGRT", b"SPCR",
        b"IORT", b"CSRT", b"FPDT"]
for s in sigs:
    i = inner.find(s)
    print("  %-10s %s" % (s.decode(), ("at 0x%X" % i) if i >= 0 else "NOT FOUND"))

print()
print("=== DXE / BDS / Windows related strings inside the INNER volume ===")
for s in [b"AcpiTableDxe", b"AcpiPlatformDxe", b"AcpiTables",
          b"Please select boot device", b"USB Storage", b"Internal Storage",
          b"FFU Mode", b"Mass Storage", b"Power Off", b"BOOTAA64",
          b"bootaa64", b"Fat", b"PartitionDxe", b"DiskIoDxe",
          b"AcpiTableProtocol", b"gEfiAcpiTableProtocolGuid"]:
    i = inner.find(s)
    print("  %-28s %s" %
          (s.decode("ascii", "replace"), ("at 0x%X" % i) if i >= 0 else "NOT FOUND"))
