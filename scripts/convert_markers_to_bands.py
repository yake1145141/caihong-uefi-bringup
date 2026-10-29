#!/usr/bin/env python3
"""
Convert the caihong bring-up markers from "paint the screen a colour" to
"draw an N-band progress bar".

Why
---
Colour-based markers proved ambiguous on real hardware: two adjacent greens
(0xFF00FF00 and 0xFF00FF80) are indistinguishable when reported by eye, and
fast transitions are easy to miss, so the same observation was reported as
"green" for different milestones.  Counting horizontal white bands removes the
guesswork: the number of bands IS the milestone number.

Protocol
--------
The screen is repainted on every milestone:
  * whole framebuffer cleared to black
  * the first N twentieths filled white
so a stopped device shows exactly N bands.

This script rewrites the macro definition and every call site in PrePi.c and
PeiHobLib.c to the numbered form, using an explicit line->step map so nothing
is inferred from ordering.

Usage:
    python scripts/convert_markers_to_bands.py <repo-root>
"""

import os
import re
import sys

BANDS = 20

MACRO = """#define BRINGUP_STEP(n)                                                  \\
  do {                                                                   \\
    volatile UINT32 *BringupFb_ = (volatile UINT32 *)0xD5100000ULL;       \\
    UINTN            BringupX_, BringupY_, BringupBand_;                  \\
    for (BringupY_ = 0; BringupY_ < 2120U; BringupY_++) {                 \\
      BringupBand_ = BringupY_ / (2120U / %dU);                          \\
      for (BringupX_ = 0; BringupX_ < 3000U; BringupX_++) {               \\
        BringupFb_[BringupY_ * 3000U + BringupX_] =                       \\
          (BringupBand_ < (UINTN)(n)) ? 0xFFFFFFFFU : 0xFF000000U;        \\
      }                                                                   \\
    }                                                                     \\
  } while (0)
""" % BANDS

NUMLINE = "#define BRINGUP_STEP(n)  do { } while (0)\n"

# Execution order (NOT file order -- CEntryPoint sits after PrePiMain in the
# file but runs first).  step number -> meaning
STEPS = {
    1:  "CEntryPoint entered (SEC/entry asm and FV handoff OK)",
    2:  "PlatformInitialize (GICR wake) done",
    3:  "Display Reserved zeroed, SerialPortInitialize done",
    4:  "UEFI FD region located, D-cache invalidated",
    5:  "PrePiMain entered",
    6:  "DXE Heap and UEFI Stack regions located",
    7:  "ArchInitialize done",
    8:  "Debug agent + debug timer interrupt done",
    9:  "HobConstructor + PrePeiSetHobList done",
    10: "MemoryPeim (MMU + memory HOBs) done",
    11: "BuildStackHob + BuildCpuHob done",
    12: "MP core PPI block done",
    13: "SEC performance HOB built",
    14: "SetBootMode done; PlatformPeim next",
    15: "PlatformPeim: PcdFvBaseAddress is CORRECT",
    16: "PlatformPeim: BuildFvHob done",
    17: "PlatformPeim: BuildMemHobForFv done",
    18: "PlatformPeim: BuildPlatformHobs done",
    19: "DecompressFirstFv done",
    20: "pre-DxeCore: all PrePi work complete",
}

# line number -> step number, per file (1-based, as of this conversion).
PREPI_MAP = {
    109: 5, 139: 6, 160: 7, 171: 8, 180: 9, 194: 10, 205: 11,
    245: 12, 253: 13, 263: 14, 272: 19, 295: 20,
    314: 1, 321: 2, 354: 3, 397: 4,
}
PEIHOB_MAP = {}


def rewrite(path, linemap, is_prepi):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    out = []
    for n, line in enumerate(lines, 1):
        s = line

        # Replace the macro definition block.
        if s.startswith("#define BRINGUP_PAINT(") or s.startswith("#define BRINGUP_PAINT ("):
            continue
        if s.strip().startswith("#define BRINGUP_PAINT(c)  do { } while (0)"):
            continue
        # drop the no-op fallback line too
        if s.strip() == "#define BRINGUP_PAINT(c)  do { } while (0)":
            continue

        if "BRINGUP_PAINT" in s:
            step = linemap.get(n)
            if step is None:
                print("  !! unmapped marker at line %d: %s" % (n, s.strip()))
                out.append(s)
                continue
            indent = s[:len(s) - len(s.lstrip())]
            out.append("%sBRINGUP_STEP (%d);   /* %s */\n"
                       % (indent, step, STEPS.get(step, "")))
            continue
        out.append(s)

    text = "".join(out)
    # Insert the new macro right after the include block.
    anchor = "#include <Library/DebugLib.h>\n"
    if anchor in text:
        text = text.replace(anchor, anchor + "\n//\n// caihong bring-up progress bar: N white bands = milestone N.\n//\n"
                            + "#if defined (CAIHONG_BRINGUP_MARKERS) && CAIHONG_BRINGUP_MARKERS\n"
                            + MACRO + "#else\n" + NUMLINE + "#endif\n", 1)
    else:
        print("  !! anchor not found in", path)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("  rewrote", path)


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    base = os.path.join(root, "source/Mu-Qcom-musabcel/Silicon/Silicium/SiliciumPkg")
    rewrite(os.path.join(base, "PrePi/PrePi.c"), PREPI_MAP, True)
    print("NOTE: PeiHobLib.c needs its own pass; see the manual step map there.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
