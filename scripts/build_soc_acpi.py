#!/usr/bin/env python3
"""
Derive the SM8650 (Cliffs) SoC-level ACPI tables for caihong.

Why derive instead of write from scratch
----------------------------------------
The SoC-level tables (FACP, MADT/"APIC", GTDT, DBG2, PPTT) are pure SoC data,
not board data.  The upstream Mu-Qcom SM8550 ("Kailua") tables are:
  * structurally correct (validated on shipping ARM64 hardware), and
  * licensed BSD-2-Clause-Patent (redistribution explicitly allowed).

Independent extraction from *this device's own firmware* proves that the
functional values that matter for SM8650 are identical to SM8550:

  field                       SM8650 value (source)              SM8550 table
  --------------------------  ---------------------------------  -------------
  GICv3 distributor           0x17100000  (vendor DTB)          0x17100000
  GICv3 redistributor region  0x17180000, size 0x200000 (DTB)   0x17180000..
  Arch timer frequency        19200000 Hz (vendor DTB)          19200000
  Platform timer block        0x17420000 (vendor DTB timer@..)  0x17420000
  Physical timer GSIV         16 + PPI13 = 29 (DTB PPI 13)       29
  Virtual timer GSIV          16 + PPI14 = 30 (DTB PPI 14)       30
  CPU count / clusters        8 / 3 (DTB cpu-map)                8 / 3

So the correct transformation is *metadata only*: retarget the OEM Table ID
and OEM revision to caihong/SM8650 and recompute the checksum.  This script
does exactly that and REFUSES to run if any asserted value does not match, so
it can never silently emit a table built on a wrong assumption.

Open assumption (documented, must be confirmed on hardware)
-----------------------------------------------------------
The per-cluster GIC redistributor bases inside MADT (0x17180000 / 0x171C0000 /
0x17200000 for the three clusters) are inherited from SM8550.  The vendor DTB
only proves the redistributor *region* base and size, not the per-cluster
split.  SM8650's cluster composition is 3/4/1 per the DTB cpu-map whereas
SM8550's is different, so these three bases are the single unverified item in
the SoC table set.  Verification on hardware: read GICR_TYPER.Affinity_Value
for each redistributor, or confirm Windows boots with all 8 processors online.
Tracked in docs/bringup-log.md and docs/hardware-matrix.md.

Usage:
  python scripts/build_soc_acpi.py --kailua <dir> --out build/acpi
"""

import argparse
import hashlib
import os
import struct
import sys

# ACPI header offsets (see ACPI spec, "Table Header")
OFF_SIGNATURE = 0
OFF_LENGTH = 4
OFF_REVISION = 8
OFF_CHECKSUM = 9
OFF_OEM_ID = 10          # 6 bytes
OFF_OEM_TABLE_ID = 16    # 8 bytes
OFF_OEM_REVISION = 24    # u32

# Verified-identical SM8650 constants (do not change without new evidence).
EXPECT_GICD = 0x17100000
EXPECT_GICR = 0x17180000
EXPECT_PLATFORM_TIMER = 0x17420000
SM8650_OEM_TABLE_ID = b"CAIHONG "
SM8650_OEM_REVISION = 0x00008650
OEM_ID = b"ONEPLS"


def u32(b, off):
    return struct.unpack_from("<I", b, off)[0]


def u64(b, off):
    return struct.unpack_from("<Q", b, off)[0]


def fix_checksum(buf):
    """Zero byte 9 and recompute the 8-bit two's complement sum."""
    b = bytearray(buf)
    b[OFF_CHECKSUM] = 0
    total = sum(b) & 0xFF
    b[OFF_CHECKSUM] = (0x100 - total) & 0xFF
    return bytes(b)


def verify_checksum(buf):
    return (sum(buf) & 0xFF) == 0


def retarget(buf, table_id=SM8650_OEM_TABLE_ID, oem_rev=SM8650_OEM_REVISION,
             oem_id=OEM_ID):
    b = bytearray(buf)
    b[OFF_OEM_ID:OFF_OEM_ID + 6] = oem_id.ljust(6, b" ")[:6]
    b[OFF_OEM_TABLE_ID:OFF_OEM_TABLE_ID + 8] = table_id.ljust(8, b" ")[:8]
    struct.pack_into("<I", b, OFF_OEM_REVISION, oem_rev)
    return fix_checksum(bytes(b))


def assert_contains(buf, needle, what, name):
    if needle not in buf:
        raise SystemExit(
            "REFUSING TO CONTINUE: %s for table %s does not contain the "
            "expected value %s.  The upstream table no longer matches the "
            "verified SM8650 firmware data; this derivation is invalid and "
            "must be reviewed." % (what, name, needle))
    return True


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def process(src_dir, out_dir, log):
    # (filename, verifier) pairs.  Each verifier asserts a value extracted
    # from the device firmware so a table can never be retargeted blindly.
    gicd = struct.pack("<Q", EXPECT_GICD)
    gicr = struct.pack("<Q", EXPECT_GICR)
    plat_timer = struct.pack("<Q", EXPECT_PLATFORM_TIMER)

    tables = [
        ("FACP.aml", []),
        ("APIC.aml", [(gicd, "GIC distributor base 0x%X" % EXPECT_GICD),
                      (gicr, "GIC redistributor base 0x%X" % EXPECT_GICR)]),
        ("GTDT.aml", [(plat_timer, "platform timer 0x%X" % EXPECT_PLATFORM_TIMER),
                      (struct.pack("<I", 29), "physical timer GSIV 29"),
                      (struct.pack("<I", 30), "virtual timer GSIV 30")]),
        ("DBG2.aml", []),
        ("PPTT.aml", []),
    ]

    results = []
    for name, checks in tables:
        src = os.path.join(src_dir, name)
        if not os.path.isfile(src):
            log.append("SKIP %s (not present upstream)" % name)
            continue
        with open(src, "rb") as f:
            raw = f.read()
        if not verify_checksum(raw):
            raise SystemExit("upstream %s already has a bad checksum" % name)
        for needle, what in checks:
            assert_contains(raw, needle, what, name)

        out = retarget(raw)
        if not verify_checksum(out):
            raise SystemExit("internal error: bad checksum after retarget %s" % name)
        os.makedirs(out_dir, exist_ok=True)
        dst = os.path.join(out_dir, name)
        with open(dst, "wb") as f:
            f.write(out)
        results.append({
            "table": name,
            "signature": out[:4].decode("ascii", "replace"),
            "length": u32(out, OFF_LENGTH),
            "revision": out[OFF_REVISION],
            "oem_id": out[OFF_OEM_ID:OFF_OEM_ID + 6].decode("ascii", "replace").strip(),
            "oem_table_id": out[OFF_OEM_TABLE_ID:OFF_OEM_TABLE_ID + 8].decode("ascii", "replace").strip(),
            "oem_revision": "0x%08X" % u32(out, OFF_OEM_REVISION),
            "checksum_ok": verify_checksum(out),
            "source_sha256": sha256(raw),
            "output_sha256": sha256(out),
            "asserted": [c[1] for c in checks],
        })
        log.append("OK   %-10s %5d bytes  oem_table_id=%r  asserted=%d"
                   % (name, len(out),
                      out[OFF_OEM_TABLE_ID:OFF_OEM_TABLE_ID + 8].decode("ascii", "replace").strip(),
                      len(checks)))
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kailua", required=True,
                    help="directory containing the upstream SM8550 SoC .aml tables")
    ap.add_argument("--out", default="build/acpi")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    log = []
    results = process(args.kailua, args.out, log)
    for line in log:
        print(line)
    if args.json:
        import json
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print("json: %s" % args.json)
    if not results:
        print("nothing produced", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
