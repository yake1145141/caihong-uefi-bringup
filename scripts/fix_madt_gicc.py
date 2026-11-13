#!/usr/bin/env python3
"""
Rebuild APIC.aml with spec-compliant 80-byte GICC structures.

Measured facts:
  * the device's own DTB says MPIDR = 0x000,0x100,...,0x700 and
    GICD 0x17100000 / GICR 0x17180000 size 0x200000, which matches our entries
  * but our eight GICC structures declare Length=82 while ACPI 6.x (and the
    upstream Kailua table this was derived from) use 80
  * the two surplus bytes sit after the last defined field, so trimming them
    does not move any real value

Output table: 44 + 8*80 + 24 (GICD) + 20 (GIC-ITS) = 728 bytes.
"""
import pathlib
import struct
import sys

SRC = pathlib.Path("/root/data/caihong-acpi/APIC.aml")
DST = pathlib.Path("/root/data/caihong-acpi/APIC.aml")


def fix(data: bytes) -> bytes:
    hdr = bytearray(data[:44])
    body = bytearray()
    off = 44
    trimmed = 0
    while off + 2 <= len(data):
        t, ln = data[off], data[off + 1]
        if ln < 2:
            break
        chunk = bytearray(data[off:off + ln])
        if t == 0x0B and ln != 80:
            # keep the 80 meaningful bytes, drop the tail padding
            keep = min(80, ln)
            chunk = bytearray(data[off:off + keep])
            chunk[1] = 80
            trimmed += 1
        body += chunk
        off += ln

    total = 44 + len(body)
    hdr[4:8] = struct.pack("<I", total)
    out = hdr + body
    out[9] = 0
    out[9] = (-sum(out)) & 0xFF        # header checksum over whole table
    print("trimmed %d GICC structure(s), new length %d (was %d)"
          % (trimmed, total, len(data)))
    print("checksum = 0x%02X (sum mod 256 = %d)"
          % (out[9], sum(out) & 0xFF))
    return bytes(out)


def walk(d):
    off, n = 44, 0
    print("  #  type  len")
    while off + 2 <= len(d):
        t, ln = d[off], d[off + 1]
        if ln < 2:
            break
        print("  %-2d 0x%02X  %d" % (n, t, ln))
        off += ln
        n += 1
    print("  end=0x%X total=%d" % (off, len(d)))


def main():
    data = SRC.read_bytes()
    print("=== before (%d bytes) ===" % len(data))
    walk(data)
    fixed = fix(data)
    DST.write_bytes(fixed)
    print("=== after (%d bytes) ===" % len(fixed))
    walk(fixed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
