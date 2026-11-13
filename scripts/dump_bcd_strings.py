#!/usr/bin/env python3
"""Dump boot-relevant UTF-16 strings from a Windows BCD hive."""
import re
import sys

p = sys.argv[1] if len(sys.argv) > 1 else \
    "/root/data/pe-fat/src/efi/microsoft/boot/bcd"
d = open(p, "rb").read()
print("BCD size:", len(d))

s = d.decode("utf-16-le", errors="ignore")
for kw in ["boot.wim", "boot.sdi", "ramdisk", "device", "osdevice",
           "winload", "bootmgfw", "EFI", "system32"]:
    print("%-10s %d" % (kw, len(re.findall(kw, s, re.I))))

print()
print("--- boot-relevant strings ---")
seen = set()
for m in re.finditer(r"[ -~]{5,}", s):
    t = m.group()
    if any(k in t.lower() for k in
           ["wim", "sdi", "efi", "boot", "ramdisk", "winload",
            "system32", "locate", "partition"]):
        if t not in seen:
            seen.add(t)
            print("  ", t[:140])
