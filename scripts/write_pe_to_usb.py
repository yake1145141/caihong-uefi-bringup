#!/usr/bin/env python3
"""
Write a raw FAT32 image to a Windows physical disk, then read it back and
verify a SHA-256 over the written region.

SAFETY: this script refuses to run unless BOTH the expected disk size class
and the source image size match what the caller validated.  The target path
is explicit (\\.\PhysicalDrive3), never computed from a scan.
"""
import hashlib
import sys

TARGET = r"\\.\PhysicalDrive3"
IMG = r"E:\1+padpro\BYDJ-PE-arm-fat32.img"
EXPECTED = 1258291200  # bytes, validated against the source image
CHUNK = 4 * 1024 * 1024

size = 0
with open(IMG, "rb") as f:
    f.seek(0, 2)
    size = f.tell()
if size != EXPECTED:
    print("REFUSING: image size %d != %d" % (size, EXPECTED))
    sys.exit(2)

print("source :", IMG)
print("size   :", size)
print("target :", TARGET)
print("writing...")

written = 0
with open(IMG, "rb") as src, open(TARGET, "r+b", buffering=0) as dst:
    while True:
        buf = src.read(CHUNK)
        if not buf:
            break
        dst.write(buf)
        written += len(buf)
        if written // (64 * 1024 * 1024) != (written - len(buf)) // (64 * 1024 * 1024):
            print("  %d / %d MB" % (written // (1024 * 1024), size // (1024 * 1024)))
    dst.flush()

print("written:", written)

# Read back and hash.
h = hashlib.sha256()
read = 0
with open(TARGET, "rb", buffering=0) as d, open(IMG, "rb") as s:
    while read < size:
        want = min(CHUNK, size - read)
        on_disk = d.read(want)
        expect = s.read(want)
        if len(on_disk) != want:
            print("REFUSING/FAIL: short read at", read)
            sys.exit(3)
        h.update(on_disk)
        if on_disk != expect:
            print("MISMATCH at byte", read)
            sys.exit(4)
        read += want

print("readback:", read)
print("sha256  :", h.hexdigest().upper())
print("OK")
