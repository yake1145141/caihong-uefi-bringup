#!/bin/sh
# Force the reference firmware to always show the BDS boot-manager menu.
#
# HANDOFF.md documents that PlatformBootManagerPriorityBoot() only starts
# BootManagerMenu when EnterBootManager() returns TRUE, which KeyCallback sets
# when any key arrives during boot.  On this device we could not reliably hit
# that window, so bring-up uses the unconditional variant instead.
set -eu
B=/root/data/caihong-work/uefi/Silicon/Silicium/SiliciumPkg/Library/BootManagerLib/KeyCallback.c

echo "before:"
sed -n '20p' "$B"

sed -i '20s/= FALSE/= TRUE/' "$B"

echo "after:"
sed -n '20p' "$B"

echo
echo "=== rebuilding DEBUG ==="
cd /root/data/uefi-caihong
./scripts/build.sh /root/data/caihong-work DEBUG > /root/data/caihong-build-menu.log 2>&1
tail -6 /root/data/caihong-build-menu.log
ls -l /root/data/caihong-work/uefi/Mu-caihong*.img
