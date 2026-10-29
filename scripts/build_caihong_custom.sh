#!/bin/sh
# Rebuild the reference caihong firmware while keeping the bring-up changes:
#
#   1. KeyCallback.c:  always enter the BDS boot-manager menu (no key press).
#   2. caihong.dsc:    print only ERROR|WARN to the panel console.
#   3. caihong.dsc:    define CAIHONG_BRINGUP_MARKERS so the DxeCore colour
#                      milestones compiled into Mu_Basecore/DxeMain are active.
#
# The repo's own scripts/build.sh starts with `git checkout -f` on the parent
# tree and re-copies the platform package, which would undo all of this, so the
# steps are performed here and build_uefi.py is driven directly.
set -eu
WORK=/root/data/caihong-work
REPO=/root/data/uefi-caihong
UEFI=$WORK/uefi
TARGET=${1:-DEBUG}

cd "$UEFI"

# 1. Always show the boot menu.
KC=Silicon/Silicium/SiliciumPkg/Library/BootManagerLib/KeyCallback.c
sed -i '20s/= FALSE/= TRUE/' "$KC"
echo "menu gate:"; sed -n '20p' "$KC"

# 2. Refresh the platform package the same way build.sh does, then patch it.
cp -r "$REPO/Platforms/OnePlus/caihongPkg" Platforms/OnePlus/
D=Platforms/OnePlus/caihongPkg/caihong.dsc

# 2a. quiet console: only ERROR|WARN
if grep -q "PcdDebugPrintErrorLevel" "$D"; then
  sed -i 's|^\(  *\)gEfiMdePkgTokenSpaceGuid.PcdDebugPrintErrorLevel.*|\1gEfiMdePkgTokenSpaceGuid.PcdDebugPrintErrorLevel\|0x80000040|' "$D"
else
  printf '\n[PcdsFixedAtBuild]\n  gEfiMdePkgTokenSpaceGuid.PcdDebugPrintErrorLevel|0x80000040\n' >> "$D"
fi

# 2b. enable the bring-up markers compiled into DxeMain
if ! grep -q "CAIHONG_BRINGUP_MARKERS" "$D"; then
  printf '\n[BuildOptions]\n  *_*_*_CC_FLAGS = -DCAIHONG_BRINGUP_MARKERS=1\n' >> "$D"
fi

echo "debug level:"; grep -n "PcdDebugPrintErrorLevel" "$D"
echo "markers:";     grep -n "CAIHONG_BRINGUP_MARKERS" "$D"

export CLANGPDB_AARCH64_PREFIX=aarch64-linux-gnu-

echo "=== building $TARGET ==="
"$WORK/.venv/bin/python" build_uefi.py -d caihong -r "$TARGET" > /root/data/caihong-custom-build.log 2>&1
tail -5 /root/data/caihong-custom-build.log
ls -l Mu-caihong*.img
