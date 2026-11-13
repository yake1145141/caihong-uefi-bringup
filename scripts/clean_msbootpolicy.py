#!/usr/bin/env python3
"""
Remove the stale CaihongDumpAcpi block that an earlier (aborted) experiment
injected into MsBootPolicy.c.

Common/Mu is not tracked by git in this tree, so `git checkout` cannot restore
it; cut the injected region out by locating its own markers.
"""
import pathlib
import sys

P = pathlib.Path(
    "/root/data/caihong-work/uefi/Common/Mu/PcBdsPkg/MsBootPolicy/MsBootPolicy.c"
)

MARK = "// CAIHONG_ACPI_DUMP"


def main():
    t = P.read_text(encoding="utf-8", errors="surrogateescape")
    if MARK not in t:
        print("clean already")
        return 0

    start = t.index(MARK)
    halt = t.find("CpuDeadLoop ();", start)
    if halt < 0:
        print("ERROR: cannot find end of injected block")
        return 1
    end = t.find("}", halt)
    if end < 0:
        print("ERROR: cannot find closing brace")
        return 1
    end += 1
    while end < len(t) and t[end] in "\r\n":
        end += 1

    t = t[:start] + t[end:]

    # Drop a leftover commented-out call if present.
    t = t.replace("  // CaihongDumpAcpi ();\r\n\r\n", "")
    t = t.replace("  // CaihongDumpAcpi ();\n\n", "")

    P.write_text(t, encoding="utf-8", errors="surrogateescape")
    print("removed injected block; MARK still present:", MARK in t)
    return 0


if __name__ == "__main__":
    sys.exit(main())
