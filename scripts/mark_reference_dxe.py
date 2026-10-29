#!/usr/bin/env python3
"""
Add flat-colour milestone markers to the reference build's DxeCore so the panel
tells us how far BDS gets.

Context: with the real VcsDxe/RscDxe restored the external abort is gone, but
the device now ends on a black screen with the backlight still on, no USB
enumeration and no response to keys.  The framebuffer console stops producing
output, so the console path itself may have been switched to graphics.

The markers paint the whole framebuffer:
    RED     DxeMain entered
    ORANGE  CoreDispatcher() returned
    YELLOW  about to hand over to gBds->Entry (BDS reached)
The last colour on screen wins, so the panel reports the furthest milestone.
"""
import pathlib
import sys

PATH = pathlib.Path(
    "/root/data/caihong-work/uefi/Mu_Basecore/MdeModulePkg/Core/Dxe/DxeMain/DxeMain.c"
)

MACRO = r"""
#if defined (CAIHONG_BRINGUP_MARKERS) && CAIHONG_BRINGUP_MARKERS
//
// caihong bring-up: paint the panel a flat colour at each DxeCore milestone.
// The framebuffer address is the ABL "Display_Reserved" region proven earlier
// in this project.
//
#define BRINGUP_FILL(c)                                                    \
  do {                                                                     \
    volatile UINT32 *Fb_ = (volatile UINT32 *)0xD5100000ULL;                \
    UINTN            I_;                                                    \
    for (I_ = 0; I_ < (3000U * 2120U); I_++) {                              \
      Fb_[I_] = (UINT32)(c);                                               \
    }                                                                      \
  } while (0)
#else
#define BRINGUP_FILL(c)  do { } while (0)
#endif
"""


def main():
    text = PATH.read_text(encoding="utf-8", errors="surrogateescape")

    if "BRINGUP_FILL" in text:
        print("already patched")
        return 0

    # Insert the macro right after the includes block: find the last #include.
    lines = text.splitlines(keepends=True)
    last_inc = max(i for i, l in enumerate(lines) if l.startswith("#include"))
    lines.insert(last_inc + 1, MACRO)
    text = "".join(lines)

    # M1: entry of DxeMain
    entry = "DxeMain (\n  IN  VOID  *HobStart\n  )\n{\n"
    if entry not in text:
        print("ERROR: DxeMain signature not found")
        return 1
    text = text.replace(
        entry, entry + "  BRINGUP_FILL (0xFFFF0000);   // RED: DxeMain entered\n", 1
    )

    # M2: after the dispatcher
    disp = "  CoreDispatcher ();\n"
    if disp not in text:
        print("ERROR: CoreDispatcher call not found")
        return 1
    text = text.replace(
        disp,
        disp + "  BRINGUP_FILL (0xFFFF8000);   // ORANGE: dispatcher returned\n",
        1,
    )

    # M3: just before BDS
    bds = "  gBds->Entry (gBds);\n"
    if bds not in text:
        print("ERROR: gBds->Entry call not found")
        return 1
    text = text.replace(
        bds,
        "  BRINGUP_FILL (0xFFFFFF00);   // YELLOW: handing over to BDS\n" + bds,
        1,
    )

    PATH.write_text(text, encoding="utf-8", errors="surrogateescape")
    print("patched", PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
