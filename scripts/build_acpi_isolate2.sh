#!/bin/sh
# Second isolation step: keep ONLY the AcpiTables.inf table package; disable
# both AcpiTableDxe and AcpiPlatformDxe.
#
# Step 1 (AcpiPlatformDxe disabled) still black-screened with no error text,
# so this distinguishes "AcpiTableDxe itself" from "the AML table package".
set -eu
UEFI=/root/data/caihong-work/uefi
WORK=/root/data/caihong-work
cd "$UEFI"
F=Platforms/OnePlus/caihongPkg/caihong.fdf

sed -i 's|^  INF MdeModulePkg/Universal/Acpi/AcpiTableDxe/AcpiTableDxe.inf|  #INF MdeModulePkg/Universal/Acpi/AcpiTableDxe/AcpiTableDxe.inf  # isolation step 2|' "$F"
sed -i 's|^  INF MdeModulePkg/Universal/Acpi/AcpiPlatformDxe/AcpiPlatformDxe.inf|  #INF MdeModulePkg/Universal/Acpi/AcpiPlatformDxe/AcpiPlatformDxe.inf  # isolation step 2|' "$F"
echo "=== FDF ACPI lines ==="
grep -n "Acpi\|ACPITABLE" "$F" | head -8

export CLANGPDB_AARCH64_PREFIX=aarch64-linux-gnu-
echo "=== building DEBUG (table package only) ==="
"$WORK/.venv/bin/python" build_uefi.py -d caihong -r DEBUG > /root/data/build-acpi-iso2.log 2>&1
tail -5 /root/data/build-acpi-iso2.log
ls -l Mu-caihong*.img
