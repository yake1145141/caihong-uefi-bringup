#!/usr/bin/env python3
"""
Build a real `Binaries/<device>/QcomPkg/Drivers` tree from the drivers extracted
out of the device's own uefi.img.

Context
-------
Mu-Silicium links prebuilt per-device UEFI drivers.  For SM8650 they are not
published, so the port was using the SM8550 set as a placeholder, which made the
firmware unusable on hardware (docs/bringup-log.md B12.2).

`scripts/extract_uefi_drivers.py` recovers 106 PE32 modules from the device's
own uefi.img.  This script turns them into the directory layout and .inf
metadata that the EDK2 build expects:

    Binaries/caihong/QcomPkg/Drivers/<Dir>/<File>.inf
    Binaries/caihong/QcomPkg/Drivers/<Dir>/<File>.efi
    Binaries/caihong/QcomPkg/Drivers/<Dir>/<File>.depex    (when present)

The .inf is synthesised with the module's ORIGINAL FFS GUID, because that GUID
is what the FV build and any GUID-based cross references rely on.

Name mapping
------------
The platform's Include/*.inc files were inherited from the SM8550 port, so some
INF names there differ from the SM8650 firmware's own module UI names (for
example the .inc asks for `DALSYSDxe` while the firmware calls it `DALSys`).
Those differences are listed explicitly in NAME_MAP rather than guessed, and
anything still unresolved is reported instead of silently skipped.

Usage:
    python scripts/make_binaries_from_uefi.py --extract work/uefi-extract \
        --platform source/Mu-Qcom-musabcel/Platforms/OnePlus/caihongPkg \
        --out build/binaries-caihong [--dry-run]
"""

import argparse
import glob
import json
import os
import re
import shutil
import sys

# .inc INF base name  ->  module UI name inside uefi.img
# Only entries where the two genuinely differ are listed; identical names are
# matched automatically.
NAME_MAP = {
    "EnvDxe":            "EnvDxeEnhanced",
    "DALSYSDxe":         "DALSys",
    "HWIODxe":           "HWIODxeDriver",
    "ChipInfoDxe":       "ChipInfo",
    "PlatformInfoDxe":   "PlatformInfoDxeDriver",
    "HALIOMMUDxe":       "HALIOMMU",
    "GLinkDxe":          "GlinkDxe",
    "TLMMDxe":           "DALTLMM",
    "I2CDxe":            "I2C",
    "SPMIDxe":           "SPMI",
    "SPIDxe":            "SPI",
    "PmicDxeLa":         "PmicDxe",
    "Phoenix2_0Dxe":     "Phoenix2_0Dex",
    "XhciPciEmulationDxe": "XhciPciEmulation",
    "OGaugeAuth":        "OGaugeAuthDxe",
}

# Modules whose EDK2 MODULE_TYPE must not be a plain DXE_DRIVER.
RUNTIME_MODULES = {
    "RuntimeDxe":               "DXE_RUNTIME_DRIVER",
    "ResetRuntimeDxe":          "DXE_RUNTIME_DRIVER",
    "CapsuleRuntimeDxe":        "DXE_RUNTIME_DRIVER",
    "VariableDxe":              "DXE_RUNTIME_DRIVER",
    "EmbeddedMonotonicCounter": "DXE_RUNTIME_DRIVER",
    "RealTimeClock":            "DXE_RUNTIME_DRIVER",
}

INF_TEMPLATE = """\
# Synthesised by scripts/make_binaries_from_uefi.py from the module extracted
# out of this device's own uefi.img (see docs/bringup-log.md B14).
[Defines]
  INF_VERSION                    = 0x0001001B
  BASE_NAME                      = {base_name}
  FILE_GUID                      = {guid}
  MODULE_TYPE                    = {module_type}
  VERSION_STRING                 = 1.0
  ENTRY_POINT                    = {entry}

[Binaries.AARCH64]
{depex_line}  PE32|{base_name}.efi|*

[Depex]
  TRUE
"""


def collect_refs(platform_dir):
    """Every `Binaries/<device>/.../*.inf` path referenced by the platform."""
    refs = []
    pats = [os.path.join(platform_dir, "Include", "*.inc"),
            os.path.join(platform_dir, "*.fdf"),
            os.path.join(platform_dir, "*.dsc")]
    seen = set()
    for f in sorted(sum((glob.glob(p) for p in pats), [])):
        for line in open(f, encoding="utf-8", errors="replace"):
            m = re.search(r"Binaries/[^/\s]+/(\S+\.inf)", line)
            if not m:
                continue
            rel = m.group(1)                 # e.g. QcomPkg/Drivers/EnvDxe/EnvDxe.inf
            if rel in seen:
                continue
            seen.add(rel)
            refs.append(rel)
    return refs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extract", required=True)
    ap.add_argument("--platform", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--entry", default="EfiEntry")
    args = ap.parse_args()

    rep = json.load(open(os.path.join(args.extract, "extract-report.json"),
                         encoding="utf-8"))
    modules = {}
    for d in rep["drivers"]:
        modules.setdefault(d["name"], d)

    refs = collect_refs(args.platform)
    print("INF references in platform: %d" % len(refs))
    print("modules extracted from uefi.img: %d" % len(modules))

    made, unresolved = [], []
    for rel in refs:
        base = os.path.splitext(os.path.basename(rel))[0]
        ui = NAME_MAP.get(base, base)
        mod = modules.get(ui)
        if mod is None:
            unresolved.append((rel, base, ui))
            continue
        made.append((rel, base, mod))

    print("\nresolvable: %d   unresolved: %d" % (len(made), len(unresolved)))
    if unresolved:
        print("\n-- unresolved (platform references a module not in uefi.img) --")
        for rel, base, ui in unresolved:
            print("   %-22s -> %-24s (%s)" % (base, ui, rel))

    if args.dry_run:
        print("\n-- would generate --")
        for rel, base, mod in made[:15]:
            print("   %-22s guid=%s  %d bytes efi, %d bytes depex"
                  % (base, mod["guid"], mod["pe32_bytes"], mod["depex_bytes"]))
        if len(made) > 15:
            print("   ... and %d more" % (len(made) - 15))
        return 0

    # ---- write the tree ---------------------------------------------------
    drv_root = os.path.join(args.out, "QcomPkg", "Drivers")
    os.makedirs(drv_root, exist_ok=True)
    index = []
    for rel, base, mod in made:
        # rel is already "QcomPkg/Drivers/<Dir>/<File>.inf" (the platform's
        # Include/*.inc paths are relative to Binaries/<device>/), so it maps
        # directly onto the output root.
        out_rel = rel
        dst_inf = os.path.join(args.out, out_rel)
        dst_dir = os.path.dirname(dst_inf)
        os.makedirs(dst_dir, exist_ok=True)

        src_efi = os.path.join(args.extract, mod["efi"])
        dst_efi = os.path.join(dst_dir, base + ".efi")
        shutil.copyfile(src_efi, dst_efi)

        depex_line = ""
        src_depex = os.path.join(args.extract, os.path.dirname(mod["efi"]),
                                 os.path.basename(mod["efi"])[:-4] + ".depex")
        if mod["depex_bytes"] and os.path.isfile(src_depex):
            raw = open(src_depex, "rb").read()
            # Qualcomm ships some modules with a 2-byte depex "06 08":
            #   0x06 EFI_DEP_PUSH consumes 0x08 as its operand, leaving no
            #   0x08 EFI_DEP_END opcode.  BaseTools then fails to build the
            #   .dpx section and aborts with a misleading error C0DE.
            # Normalise to the minimal valid expression (END = always load),
            # which is what an empty depex is meant to express.
            if raw == b"\x06\x08":
                raw = b"\x08"
            with open(os.path.join(dst_dir, base + ".depex"), "wb") as f:
                f.write(raw)
            depex_line = "  DXE_DEPEX|%s.depex|*\n" % base

        with open(dst_inf, "w", encoding="utf-8", newline="\n") as f:
            f.write(INF_TEMPLATE.format(
                base_name=base, guid=mod["guid"],
                module_type=RUNTIME_MODULES.get(base, "DXE_DRIVER"),
                entry=args.entry, depex_line=depex_line))

        index.append({"inf": out_rel, "base_name": base,
                      "source_module": mod["name"], "guid": mod["guid"],
                      "efi_bytes": mod["pe32_bytes"],
                      "depex": bool(depex_line)})

    with open(os.path.join(args.out, "BINARIES_INDEX.json"), "w",
              encoding="utf-8") as f:
        json.dump({"generated_from": "uefi.img", "count": len(index),
                   # Recorded so scripts/verify_fv_drivers.py can tell a module
                   # that is absent *by design* (commented out in DXE.inc, as
                   # GLinkDxe / Phoenix2_0Dxe are upstream) from one that was
                   # genuinely lost during the FV build.
                   "platform_include": os.path.abspath(
                       os.path.join(args.platform, "Include")),
                   "unresolved": [r[0] for r in unresolved],
                   "modules": index}, f, indent=2)

    print("\nwrote %d modules under %s" % (len(index), drv_root))
    print("index: %s" % os.path.join(args.out, "BINARIES_INDEX.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
