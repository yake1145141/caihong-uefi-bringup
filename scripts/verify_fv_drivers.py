#!/usr/bin/env python3
"""
Verify that the drivers extracted from the device's uefi.img actually ended up
in the firmware volume that EDK2 just produced.

Checks, for every module recorded in BINARIES_INDEX.json, whether a FFS file
directory with that module GUID exists under the build's
`<Build>/<pkg>/<target>/FV/Ffs` tree.  This is the concrete evidence that the
SM8650 drivers (not the SM8550 placeholders) are inside the image.

Usage:
    python3 verify_fv_drivers.py <BINARIES_INDEX.json> <FV/Ffs dir> [<DXE.inc>]

The third argument is the platform's Include/DXE.inc.  It is used to tell a
module that is absent *by design* (commented out upstream, e.g. GLinkDxe and
Phoenix2_0Dxe) from one that was genuinely lost during the FV build.  The path
recorded inside the index is a build-host path and may not exist where the
check runs, so it is accepted explicitly.
"""

import json
import os
import sys


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 64
    index_path, ffs_dir = sys.argv[1], sys.argv[2]
    dxe_inc = sys.argv[3] if len(sys.argv) > 3 else None

    with open(index_path, encoding="utf-8") as f:
        index = json.load(f)

    if not os.path.isdir(ffs_dir):
        print("error: FFS directory not found: %s" % ffs_dir, file=sys.stderr)
        return 2

    entries = os.listdir(ffs_dir)
    # Normalise once; FFS directory names are "<GUID><Name>".
    upper = [e.upper() for e in entries]

    # Some modules are referenced by APRIORI.inc but deliberately commented out
    # in DXE.inc (inherited from the upstream SM8550 port).  Those are absent
    # from the FV *by design* and must not be reported as failures.
    disabled = set()
    if not dxe_inc:
        cand = index.get("platform_include")
        if cand and os.path.isdir(cand) and os.path.isfile(os.path.join(cand, "DXE.inc")):
            dxe_inc = os.path.join(cand, "DXE.inc")
    if dxe_inc and os.path.isfile(dxe_inc):
        import re
        with open(dxe_inc, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = re.search(r"#\s*INF\s+\S+/(\w+)\.inf", line)
                if m:
                    disabled.add(m.group(1))
        print("classifying against: %s (%d disabled entries)"
              % (dxe_inc, len(disabled)))
    else:
        print("note: no DXE.inc supplied; every absence will be reported as "
              "unexpected")

    present, missing, by_design = [], [], []
    for mod in index["modules"]:
        g = mod["guid"].upper()
        if any(e.startswith(g) for e in upper):
            present.append(mod)
        elif mod["base_name"] in disabled:
            by_design.append(mod)
        else:
            missing.append(mod)

    print("modules generated      : %d" % len(index["modules"]))
    print("FFS entries in FV      : %d" % len(entries))
    print("present in the FV      : %d" % len(present))
    print("absent by design       : %d  (commented out in DXE.inc)" % len(by_design))
    if by_design:
        for m in by_design:
            print("     %-22s %s" % (m["base_name"], m["guid"]))
    print("unexpectedly missing   : %d" % len(missing))
    if missing:
        for m in missing:
            print("   %-24s %s" % (m["base_name"], m["guid"]))

    key = {"UFSDxe", "DALSYSDxe", "TLMMDxe", "PmicDxeLa", "RpmhDxe", "EnvDxe"}
    print("\n-- spot check of SoC-critical drivers --")
    for mod in index["modules"]:
        if mod["base_name"] in key:
            g = mod["guid"].upper()
            ok = any(e.startswith(g) for e in upper)
            print("   %-14s %s  %s" % (mod["base_name"], "PRESENT" if ok else "MISSING",
                                       mod["guid"]))
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
