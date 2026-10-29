#!/bin/sh
# Show the mEnterBootManager plumbing in the reference BootManagerLib so the
# "must press a key to enter the menu" gate can be removed for bring-up.
set -eu
B=/root/data/caihong-work/uefi/Silicon/Silicium/SiliciumPkg/Library/BootManagerLib

echo "=== BootManager.c: mEnterBootManager ==="
grep -n "mEnterBootManager" "$B/BootManager.c" || true

echo
echo "=== KeyCallback.c: mEnterBootManager ==="
grep -n "mEnterBootManager" "$B/KeyCallback.c" || true

echo
echo "=== context around the PriorityBoot gate ==="
sed -n '145,175p' "$B/BootManager.c"
