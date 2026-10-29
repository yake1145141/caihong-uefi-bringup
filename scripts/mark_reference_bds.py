#!/usr/bin/env python3
"""
Paint flat colours inside BDS, after the console has been reset.

The DxeMain markers are drawn before `gBds->Entry()`, and BDS resets the console
when it starts, which wipes them -- so a black screen after the log cannot be
told apart from "never reached BDS".  These markers are drawn from inside
PlatformBootManagerPriorityBoot(), i.e. after that reset:

    MAGENTA  PriorityBoot entered
    BLUE     the "do not show the menu" early-return was taken

Whitespace- and line-ending-agnostic: the file is located by name and the marker
is inserted just after the opening brace / before the early return.
"""
import pathlib
import sys

PATH = pathlib.Path(
    "/root/data/caihong-work/uefi/Silicon/Silicium/SiliciumPkg/Library/BootManagerLib/BootManager.c"
)

MACRO = r"""
#if defined (CAIHONG_BRINGUP_MARKERS) && CAIHONG_BRINGUP_MARKERS
#define BRINGUP_FILL_BDS(c)                                                \
  do {                                                                     \
    volatile UINT32 *Fb_ = (volatile UINT32 *)0xD5100000ULL;                \
    UINTN            I_;                                                    \
    for (I_ = 0; I_ < (3000U * 2120U); I_++) {                              \
      Fb_[I_] = (UINT32)(c);                                               \
    }                                                                      \
  } while (0)
#else
#define BRINGUP_FILL_BDS(c)  do { } while (0)
#endif
"""


def main():
    raw = PATH.read_bytes()
    nl = b"\r\n" if b"\r\n" in raw else b"\n"
    text = raw.decode("utf-8", "surrogateescape")

    if "BRINGUP_FILL_BDS" in text:
        print("already patched")
        return 0

    # 1. macro after the last #include
    lines = text.splitlines(keepends=True)
    last_inc = max(i for i, l in enumerate(lines) if l.lstrip().startswith("#include"))
    macro = MACRO.replace("\n", nl.decode())
    lines.insert(last_inc + 1, macro)
    text = "".join(lines)

    # 2. marker right after the opening brace of the function
    key = "PlatformBootManagerPriorityBoot"
    i = text.find(key)
    if i < 0:
        print("ERROR: function not found")
        return 1
    brace = text.find("{", i)
    if brace < 0:
        print("ERROR: opening brace not found")
        return 1
    ins = nl.decode() + "  BRINGUP_FILL_BDS (0xFFFF00FF);   // MAGENTA: PriorityBoot entered" + nl.decode()
    text = text[: brace + 1] + ins + text[brace + 1 :]

    # 3. marker before the early return
    j = text.find("BootManagerFlag == FALSE")
    if j >= 0:
        ret = text.find("return;", j)
        if ret >= 0:
            ins2 = "BRINGUP_FILL_BDS (0xFF0000FF);   // BLUE: menu suppressed" + nl.decode() + "    "
            text = text[:ret] + ins2 + text[ret:]
            print("early-return branch marked")
        else:
            print("WARNING: no return after the flag check")
    else:
        print("WARNING: flag check not found")

    PATH.write_text(text, encoding="utf-8", errors="surrogateescape", newline="")
    print("patched", PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
