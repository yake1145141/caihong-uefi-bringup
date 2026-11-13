#!/usr/bin/env python3
"""
Validate the six caihong ACPI tables byte by byte.

Windows on ARM is far stricter than Linux/XNU about ACPI:
  * every table header must have a correct checksum
  * FACP must set the ARM "hardware reduced" flags
  * MADT must carry GICC/GICD/GICR structures for a GICv3 machine
  * GTDT must describe the EL1 timer GSIVs

A 900E crash dump right after the boot manager starts reading ACPI usually
means one of the above is wrong, so check them before touching anything else.
"""
import struct
import sys

NAMES = ["FACP", "APIC", "GTDT", "DBG2", "PPTT", "DSDT"]
BASE = r"E:\caihong-windows\build\acpi"


def csum(data):
    return sum(data) & 0xFF


def parse(path):
    d = open(path, "rb").read()
    sig = d[0:4].decode("ascii", "replace")
    length = struct.unpack_from("<I", d, 4)[0]
    rev = d[8]
    oemid = d[10:16].decode("ascii", "replace").rstrip("\x00")
    oemtbl = d[16:24].decode("ascii", "replace").rstrip("\x00")
    oemrev = struct.unpack_from("<I", d, 24)[0]
    creator = d[28:32].decode("ascii", "replace")
    crest = struct.unpack_from("<I", d, 32)[0]
    ok = (csum(d[:length]) == 0) if length == len(d) else None
    print("=== %s ===" % sig)
    print("  file bytes : %d" % len(d))
    print("  header len : %d  %s" % (length, "OK" if length == len(d) else "MISMATCH!"))
    print("  revision   : %d" % rev)
    print("  OEM        : %-6s / %-8s rev %d" % (oemid, oemtbl, oemrev))
    print("  creator    : %-4s rev %d" % (creator, crest))
    print("  checksum   : %s (0x%02X)" % (
        "OK" if ok else ("BAD" if ok is False else "N/A"), csum(d[:length])))
    return d, sig


def dump_facp(d):
    # ARM flags live in the FADT; dump the fields Windows cares about
    print("  [FACP detail]")
    print("    Flags(0x70)          = 0x%08X" % struct.unpack_from("<I", d, 0x70)[0])
    hw_reduced = (struct.unpack_from("<I", d, 0x70)[0] >> 20) & 1
    print("    HW_REDUCED_ACPI      = %d (ARM requires 1)" % hw_reduced)
    if len(d) >= 0x94:
        print("    FADT minor version   = %d" % d[0x83])
        print("    X_DSDT (0x88)        = 0x%016X" % struct.unpack_from("<Q", d, 0x88)[0])
        print("    X_FIRMWARE_CTRL(0x84)= 0x%016X" % struct.unpack_from("<Q", d, 0x84)[0])


def dump_madt(d):
    print("  [MADT/APIC detail]")
    off = 44
    n = 0
    while off + 2 <= len(d):
        t = d[off]
        ln = d[off + 1]
        if ln < 2:
            break
        names = {0x0B: "GICC", 0x0C: "GICD", 0x0E: "GICR", 0x0F: "GIC ITS",
                 0x0A: "GIC CPU IF", 0x0D: "GIC MSI"}
        print("    type=0x%02X %-10s len=%d" % (t, names.get(t, "?"), ln))
        if t == 0x0B and ln >= 76:      # GICC
            print("      CPU InterfaceNumber=0x%08X UID=%d" %
                  (struct.unpack_from("<I", d, off + 4)[0], struct.unpack_from("<I", d, off + 8)[0]))
        if t == 0x0C and ln >= 24:      # GICD
            print("      GICD base=0x%08X" % struct.unpack_from("<Q", d, off + 8)[0])
        if t == 0x0E and ln >= 16:      # GICR
            print("      GICR base=0x%08X" % struct.unpack_from("<Q", d, off + 4)[0])
        off += ln
        n += 1
    print("    total structures: %d" % n)


def dump_gtdt(d):
    print("  [GTDT detail]")
    print("    CntControlBase=0x%08X" % struct.unpack_from("<Q", d, 40)[0])
    print("    CntReadBase   =0x%08X" % struct.unpack_from("<Q", d, 48)[0])
    print("    EL1 timer GSIV=0x%08X  flags=0x%08X" %
          (struct.unpack_from("<I", d, 56)[0], struct.unpack_from("<I", d, 60)[0]))


for n in NAMES:
    d, sig = parse(r"%s\%s.aml" % (BASE, n))
    if sig == "FACP":
        dump_facp(d)
    elif sig == "APIC":
        dump_madt(d)
    elif sig == "GTDT":
        dump_gtdt(d)
    print()
