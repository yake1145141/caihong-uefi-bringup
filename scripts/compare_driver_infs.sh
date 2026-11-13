#!/bin/sh
# Compare the vendor driver INFs in the pristine reference repo against the
# build tree, which was modified during B25 (drivers swapped to the Android 15
# set).  This checks whether the ACPI black-screen experiments were actually
# run against the same known-good baseline as the user's menu-working image.
set -eu
REF=/root/data/uefi-caihong/Binaries/caihong/QcomPkg/Drivers
TREE=/root/data/caihong-work/uefi/Binaries/caihong/QcomPkg/Drivers

echo "driver          reference-repo                 build-tree"
for d in VcsDxe RscDxe UFSDxe ClockDxe SPMIDxe PmicDxe ButtonsDxe UsbConfigDxe UsbMsdDxe; do
    r=$(grep -h 'PE32' "$REF/$d/"*.inf 2>/dev/null | head -1 | tr -d ' ' || true)
    t=$(grep -h 'PE32' "$TREE/$d/"*.inf 2>/dev/null | head -1 | tr -d ' ' || true)
    printf '%-15s %-34s %s\n' "$d" "${r:-MISSING}" "${t:-MISSING}"
done

echo
echo "=== sha256 of the ORIGINAL reference image vs the user's working image ==="
sha256sum /root/data/caihong-work/uefi/Resources/Configs/caihong.toml 2>/dev/null || true
