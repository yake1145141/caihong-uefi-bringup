#!/bin/sh
# Build DEBUG firmware from the CORRECT tree (restored reference drivers +
# ACPI tables) with MsBootPolicy enumeration logging promoted to ERROR, and
# console filtered to ERROR|WARN so those lines stay visible on the panel.
set -eu
REPO=/root/data/uefi-caihong
UEFI=/root/data/caihong-work/uefi
WORK=/root/data/caihong-work
cd "$UEFI"

# 1. Restore platform package, re-enable ACPI, restore reference drivers.
cp -r "$REPO/Platforms/OnePlus/caihongPkg" Platforms/OnePlus/
python3 /root/data/enable_caihong_acpi.py
sh /root/data/restore_reference_drivers.sh > /root/data/restore-drivers.log 2>&1

# 2. Reset the three files touched by earlier experiments, then apply the
#    MsBootPolicy logging patch.
git checkout -- \
    Silicon/Silicium/SiliciumPkg/Library/BootManagerLib/KeyCallback.c \
    Silicon/Silicium/SiliciumPkg/Library/BootManagerLib/BootManager.c \
    Mu_Basecore/MdeModulePkg/Core/Dxe/DxeMain/DxeMain.c 2>/dev/null || true
python3 /root/data/mark_msboot_enum.py

# 3. Console filter: ERROR|WARN only.
python3 - Platforms/OnePlus/caihongPkg/caihong.dsc <<'PY'
import re, pathlib
p = pathlib.Path("Platforms/OnePlus/caihongPkg/caihong.dsc")
t = p.read_text(encoding="utf-8", errors="surrogateescape")
line = "  gEfiMdePkgTokenSpaceGuid.PcdDebugPrintErrorLevel|0x80000040"
if "PcdDebugPrintErrorLevel" in t:
    t = re.sub(r"(?m)^\s*gEfiMdePkgTokenSpaceGuid\.PcdDebugPrintErrorLevel.*$", line, t)
elif "[PcdsFixedAtBuild" in t:
    t = re.sub(r"(?m)^(\[PcdsFixedAtBuild[^\]]*\]\s*)$", r"\1\n" + line, t, count=1)
else:
    t += "\n[PcdsFixedAtBuild]\n" + line + "\n"
p.write_text(t, encoding="utf-8", errors="surrogateescape")
print("console filter set")
PY

export CLANGPDB_AARCH64_PREFIX=aarch64-linux-gnu-
echo "=== building DEBUG (MSBOOT enum logging) ==="
"$WORK/.venv/bin/python" build_uefi.py -d caihong -r DEBUG > /root/data/build-msboot-debug.log 2>&1
tail -5 /root/data/build-msboot-debug.log
ls -l Mu-caihong*.img
