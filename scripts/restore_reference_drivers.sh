#!/bin/sh
# Restore the ORIGINAL vendor driver set from the reference repo into the build
# tree, undoing the B25 experiment (which swapped six drivers for the Android 15
# versions and removed their binary patches).
#
# This is required before any ACPI experiment: the user's menu-working image is
# built from the reference repo's patched drivers, while every B27/B28 build was
# made from the swapped tree -- so those results were not comparable.
set -eu
REF=/root/data/uefi-caihong/Binaries/caihong/QcomPkg/Drivers
TREE=/root/data/caihong-work/uefi/Binaries/caihong/QcomPkg/Drivers

for d in VcsDxe RscDxe UFSDxe ClockDxe SPMIDxe PmicDxe ButtonsDxe UsbConfigDxe UsbMsdDxe; do
    rm -rf "$TREE/$d"
    cp -r "$REF/$d" "$TREE/$d"
    printf 'restored %-14s -> %s\n' "$d" \
        "$(grep -h 'PE32' "$TREE/$d/"*.inf | head -1 | tr -d ' ')"
done

echo
echo "=== verify all nine INFs now point to patched ==="
for d in VcsDxe RscDxe UFSDxe ClockDxe SPMIDxe PmicDxe ButtonsDxe UsbConfigDxe UsbMsdDxe; do
    grep -h 'PE32' "$TREE/$d/"*.inf | head -1 | tr -d ' '
done
