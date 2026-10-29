#!/usr/bin/env python3
"""
Run the edk2toollib DSC parser against a DSC and report exactly which line it
rejects.

Why: `stuart_build` reports only "We have a stray operand ==" with a traceback
inside edk2toollib, which does not say which file or line.  This script turns
that into an actionable line number, and lets us compare our own platform DSC
against an untouched upstream one to prove whether the fault is in our file or
in the parser.

Usage (inside WSL):
    python3 scan_dsc.py <dsc> [<dsc> ...]
"""

import os
import sys
import traceback

from edk2toollib.uefi.edk2.parsers.dsc_parser import DscParser


def parse_one(path):
    print("=" * 70)
    print("DSC:", path)
    if not os.path.isfile(path):
        print("  MISSING")
        return False
    p = DscParser()
    # The parser needs the workspace layout to resolve !include and packages.
    root = path
    for _ in range(6):
        root = os.path.dirname(root)
    p.SetBaseAbsPath(root)
    p.SetPackagePaths([root])
    try:
        p.ParseFile(path)
        print("  OK  (%d sections parsed)" % len(p.Lines))
        return True
    except Exception as exc:  # noqa: BLE001 - we want everything
        print("  FAILED: %s: %s" % (type(exc).__name__, exc))
        tb = traceback.extract_tb(sys.exc_info()[2])
        for frame in tb[-3:]:
            print("    at %s:%s  %s" % (os.path.basename(frame.filename),
                                        frame.lineno, frame.line))
        return False


def find_offenders(path):
    """Print every line that contains a conditional operator, with context."""
    print("-" * 70)
    print("Conditional/operator lines in", path)
    section = "<none>"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for n, line in enumerate(f, 1):
                s = line.strip()
                if s.startswith("[") and s.endswith("]"):
                    section = s
                if s.startswith("!if") or s.startswith("!elseif") or "==" in s:
                    print("  %-5d %-22s %s" % (n, section, s[:100]))
    except OSError as exc:
        print("  cannot read:", exc)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    ok = True
    for path in sys.argv[1:]:
        ok &= parse_one(path)
        find_offenders(path)
    print("=" * 70)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
