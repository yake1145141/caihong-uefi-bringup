#!/usr/bin/env python3
"""
Isolate the edk2toollib "stray operand" failure to a file.

DscParser.ParseFile() runs three phases; the one that raises here is
`__ProcessDefines(file_lines)`, which is fed the *top-level* DSC's raw lines.
Rather than fight include resolution, this script calls that phase directly on
a single file, so we can compare our own platform DSC against an untouched
upstream one (aston, SM8550) and tell whether the fault is ours or the
toolchain's.

Usage (inside WSL):
    python3 diag_dsc_defines.py <file.dsc> [<file.dsc> ...]
"""

import os
import sys

from edk2toollib.uefi.edk2.parsers.dsc_parser import DscParser

# The mangled name of the private phase inside DscParser.
PROCESS_DEFINES = "_DscParser__ProcessDefines"

# Package roots used by DeviceBuild.py for this tree.  !include resolution in
# the Defines phase needs these, otherwise every file "fails" spuriously.
PACKAGE_DIRS = [
    "Platforms/OnePlus",
    "Common/Mu",
    "Common/Mu_OEM_Sample",
    "Common/Mu_Tiano_Plus",
    "Features/DFCI",
    "Mu_Basecore",
    "Silicon/Arm/Mu_Tiano",
    "Silicon/Qualcomm",
    "Silicon/Silicium",
    "Silicium-ACPI/Platforms/OnePlus",
    "Silicium-ACPI/SoCs/Qualcomm",
]


def make_parser(root):
    p = DscParser()
    p.SetBaseAbsPath(root)
    p.SetPackagePaths([os.path.join(root, d) for d in PACKAGE_DIRS]
                      + [root])
    return p


def probe(path):
    print("=" * 70)
    print("file:", path)
    root = os.getcwd()
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError as exc:
        print("  cannot read:", exc)
        return None

    # Show what the parser believes the [Defines] section is.
    section = None
    in_def = False
    count = 0
    for n, raw in enumerate(lines, 1):
        s = raw.strip()
        if s.startswith("[") and s.endswith("]"):
            section = s
            in_def = (s == "[Defines]")
            continue
        if in_def:
            count += 1
            if "==" in s or s.startswith("!if") or s.startswith("!elseif"):
                print("  [Defines] line %d would hit EvaluateConditional: %s"
                      % (n, s[:90]))
    print("  lines inside [Defines]:", count)

    parser = make_parser(root)
    fn = getattr(parser, PROCESS_DEFINES, None)
    if fn is None:
        print("  SKIP: private phase not found (library layout changed)")
        return None
    try:
        fn(lines)
        print("  RESULT: __ProcessDefines OK")
        return True
    except Exception as exc:  # noqa: BLE001
        print("  RESULT: __ProcessDefines FAILED: %s: %s"
              % (type(exc).__name__, exc))
        return False


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    results = [(p, probe(p)) for p in sys.argv[1:]]
    print("=" * 70)
    for p, r in results:
        print("  %-55s %s" % (p.split("/")[-1], {True: "OK",
                                                  False: "FAIL", None: "?"}[r]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
