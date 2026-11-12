#!/bin/sh
# Build a *clean* caihong firmware with ACPI enabled: no debug colour markers,
# no forced boot menu, no quiet-console override.
#
# The previous ACPI build inherited -DCAIHONG_BRINGUP_MARKERS=1 from an earlier
# experiment, so the red flash on the panel was the DxeMain marker, not a
# crash.  This script makes the DSC pristine before building.
set -eu
WORK=/root/data/caihong-work
REPO=/root/data/uefi-caihong
UEFI=$WORK/uefi
TARGET=${1:-RELEASE}

cd "$UEFI"

# 1. Restore the pristine platform package from the reference repo, then
#    re-enable only ACPI (the marker/debug PCD lines are dropped).
cp -r "$REPO/Platforms/OnePlus/caihongPkg" Platforms/OnePlus/
python3 /root/data/enable_caihong_acpi.py

# 2. Undo the parent-tree leftovers from earlier experiments: the forced-menu
#    edit in KeyCallback.c and the injected colour markers in DxeMain.c /
#    BootManager.c.  Restore those three files from git.
git -C "$UEFI" checkout -- \
    Silicon/Silicium/SiliciumPkg/Library/BootManagerLib/KeyCallback.c \
    Silicon/Silicium/SiliciumPkg/Library/BootManagerLib/BootManager.c \
    Mu_Basecore/MdeModulePkg/Core/Dxe/DxeMain/DxeMain.c 2>/dev/null || true

echo "=== DSC flags (should show no markers / no debug PCD) ==="
grep -n "CAIHONG_\|PcdDebugPrintErrorLevel\|acpi\|Acpi" \
    Platforms/OnePlus/caihongPkg/caihong.dsc || true

export CLANGPDB_AARCH64_PREFIX=aarch64-linux-gnu-

echo "=== building $TARGET ==="
"$WORK/.venv/bin/python" build_uefi.py -d caihong -r "$TARGET" > /root/data/build-acpi-clean.log 2>&1
tail -5 /root/data/build-acpi-clean.log
ls -l Mu-caihong*.img
