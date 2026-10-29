#!/bin/sh
# Reduce the DEBUG console noise so a single error/warning stays visible on the
# panel instead of scrolling away.
#
# The reference firmware prints everything (DEBUG_INFO and below), which fills
# the screen within a second or two.  Restricting PcdDebugPrintErrorLevel to
# ERROR|WARN keeps only the lines that matter for bring-up.
set -eu
D=/root/data/caihong-work/uefi/Platforms/OnePlus/caihongPkg/caihong.dsc

echo "=== current PcdDebugPrintErrorLevel ==="
grep -n "PcdDebugPrintErrorLevel" "$D" || echo "(not set)"

# Append to the fixed-at-build PCD section if it exists, otherwise create it.
if grep -q "PcdDebugPrintErrorLevel" "$D"; then
  sed -i 's|^\(  *\)gEfiMdePkgTokenSpaceGuid.PcdDebugPrintErrorLevel.*|\1gEfiMdePkgTokenSpaceGuid.PcdDebugPrintErrorLevel\|0x80000040|' "$D"
else
  printf '\n[PcdsFixedAtBuild]\n  gEfiMdePkgTokenSpaceGuid.PcdDebugPrintErrorLevel|0x80000040\n' >> "$D"
fi

echo "=== after ==="
grep -n "PcdDebugPrintErrorLevel" "$D"

echo
echo "=== rebuilding DEBUG (errors/warnings only) ==="
cd /root/data/uefi-caihong
./scripts/build.sh /root/data/caihong-work DEBUG > /root/data/caihong-build-quiet.log 2>&1
tail -6 /root/data/caihong-build-quiet.log
ls -l /root/data/caihong-work/uefi/Mu-caihong*.img
