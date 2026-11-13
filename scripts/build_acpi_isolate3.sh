#!/bin/sh
# Bisect step 3: remove ONLY the AcpiTables.inf table package from the FDF and
# DSC, keep both ACPI DXE drivers enabled.
#
# Results so far:
#   baseline (no ACPI at all)                     -> boot menu OK
#   full ACPI (2 drivers + table package)         -> black screen
#   minus AcpiPlatformDxe                         -> black screen
#   minus BOTH drivers, table package still in    -> black screen
#
# Inner FV grew only ~24 KB, so the 4 MB FD size is NOT the cause.  Removing
# the table package is the clean way to prove whether the package itself is the
# regression trigger.
set -eu
UEFI=/root/data/caihong-work/uefi
WORK=/root/data/caihong-work
cd "$UEFI"
F=Platforms/OnePlus/caihongPkg/caihong.fdf
D=Platforms/OnePlus/caihongPkg/caihong.dsc

# Re-enable both drivers, drop the table package line from FDF and DSC.
sed -i 's|^  #INF MdeModulePkg/Universal/Acpi/AcpiTableDxe/AcpiTableDxe.inf.*|  INF MdeModulePkg/Universal/Acpi/AcpiTableDxe/AcpiTableDxe.inf|' "$F"
sed -i 's|^  #INF MdeModulePkg/Universal/Acpi/AcpiPlatformDxe/AcpiPlatformDxe.inf.*|  INF MdeModulePkg/Universal/Acpi/AcpiPlatformDxe/AcpiPlatformDxe.inf|' "$F"
sed -i 's|^  INF RuleOverride = ACPITABLE caihong/AcpiTables.inf.*|  #INF RuleOverride = ACPITABLE caihong/AcpiTables.inf  # bisect step 3: removed|' "$F"
sed -i 's|^  caihong/AcpiTables.inf.*|  #caihong/AcpiTables.inf  # bisect step 3: removed|' "$D"

echo "=== FDF ACPI lines ==="
grep -n "Acpi\|ACPITABLE" "$F" | head -8
echo "=== DSC ACPI line ==="
grep -n "AcpiTables" "$D" | head -4

export CLANGPDB_AARCH64_PREFIX=aarch64-linux-gnu-
echo "=== building DEBUG (drivers only, no tables) ==="
"$WORK/.venv/bin/python" build_uefi.py -d caihong -r DEBUG > /root/data/build-acpi-iso3.log 2>&1
tail -5 /root/data/build-acpi-iso3.log
ls -l Mu-caihong*.img
