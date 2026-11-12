#!/usr/bin/env python3
"""Inspect the *working* Mu-caihong-0.img: decompress the kernel payload and
look for ACPI tables / Windows boot support inside the firmware volume.

Android boot image header v4 layout:
  0x00 magic[8], 0x08 kernel_size, 0x0C ramdisk_size, 0x10 os_version,
  0x14 header_size, 0x18..0x27 reserved, 0x28 header_version, ...
kernel data starts at header_size (usually 4096) and is gzip-compressed.
"""
import gzip
import io
import struct
import sys
import zlib

path = sys.argv[1] if len(sys.argv) > 1 else r"E:\1+padpro\Mu-caihong-0.img"
d = open(path, "rb").read()

print("file size      :", len(d))
print("magic          :", d[:8])
kernel_size = struct.unpack_from("<I", d, 0x08)[0]
ramdisk_size = struct.unpack_from("<I", d, 0x0C)[0]
header_size = struct.unpack_from("<I", d, 0x14)[0]
header_version = struct.unpack_from("<I", d, 0x28)[0]
print("kernel_size    : 0x%X" % kernel_size)
print("ramdisk_size   : 0x%X" % ramdisk_size)
print("header_size    :", header_size)
print("header_version :", header_version)

# v4 header_size is 1584, but the payload is aligned to a 4096-byte page.
# Try several plausible offsets; accept the first that yields a gzip stream.
raw = None
for base in (header_size, ((header_size + 4095) // 4096) * 4096, 4096, 0x1000):
    k = d[base:base + kernel_size]
    i = k.find(b"\x1f\x8b\x08")
    if i < 0:
        continue
    try:
        # The Android boot image appends a DTB after the gzip member.  GzipFile
        # would try to parse that as a second member and fail, so decompress
        # exactly one DEFLATE stream with zlib and discard the trailing bytes.
        dec = zlib.decompressobj(16 + zlib.MAX_WBITS)
        raw = dec.decompress(k[i:])
        raw += dec.flush()
        if len(raw) < 0x10000:
            raise ValueError("decompressed only %d bytes" % len(raw))
        print("payload base   : 0x%X (gzip at +0x%X)" % (base, i))
        print("decompressed   :", len(raw), "bytes")
        print("gzip trailer   : %d unused bytes (DTB etc.)" % len(dec.unused_data))
        break
    except Exception as e:
        print("  base 0x%X: gzip at +0x%X failed: %s" % (base, i, e))

if raw is None:
    print("ERROR: no decompressible gzip payload found")
    sys.exit(1)

out = r"E:\caihong-windows\work\working-uefi-payload.bin"
open(out, "wb").write(raw)
print("saved          :", out)

print()
print("=== ACPI / FDT / Windows-related signatures in the decompressed FV ===")
sigs = [
    b"RSD PTR ", b"FACP", b"APIC", b"GTDT", b"DBG2", b"PPTT",
    b"DSDT", b"SSDT", b"BGRT", b"SPCR", b"MCFG", b"RSDT", b"XSDT",
    b"ACPI", b"AcpiTableDxe", b"AcpiPlatformDxe",
    b"Please select boot device", b"USB Storage", b"Internal Storage",
    b"Ram Storage", b"BOOTAA64", b"bootaa64", b"Windows Boot Manager",
    b"RamDisk", b"Ram Disk",
]
for s in sigs:
    i = raw.find(s)
    label = s.decode("ascii", "replace")
    found = ("at 0x%X" % i) if i >= 0 else "NOT FOUND"
    print("  %-28s %s" % (label, found))

print()
print("=== FV header ===")
i = raw.find(b"_FVH")
print("  _FVH at", hex(i) if i >= 0 else "NOT FOUND")
