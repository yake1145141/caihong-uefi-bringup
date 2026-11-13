#!/bin/sh
# Fix the ACPI table version filter, which was silently discarding every table
# except the revision-6 FACP.
#
# Root cause:
#   MdeModulePkg.dec has TWO defaults for PcdAcpiExposedTableVersions:
#       [PcdsFixedAtBuild]              ... 0x3E   (ACPI 2.0 .. 6.0)
#       [PcdsFixedAtBuild.AARCH64]      ... 0x20   (ACPI 6.0 ONLY)
#   On AArch64 the 0x20 wins, and the resolve build shows
#       _PCD_VALUE_PcdAcpiExposedTableVersions = 0x20U
#   AcpiTableDxe's InstallAcpiTableFv then only keeps tables whose ACPI version
#   matches 0x20, i.e. revision-6 tables.  Our APIC (rev 5), GTDT (rev 2) and
#   DSDT (rev 2) were dropped, leaving Windows an ACPI namespace with a single
#   FACP whose DSDT pointer is 0.
#
# Fix: override to 0x3F (all versions incl. 1.0B) in the platform DSC.
set -eu
REPO=/root/data/uefi-caihong
UEFI=/root/data/caihong-work/uefi
WORK=/root/data/caihong-work
INF=$UEFI/Silicium-ACPI/Platforms/OnePlus/caihong/AcpiTables.inf
DSC=$UEFI/Platforms/OnePlus/caihongPkg/caihong.dsc
cd "$UEFI"

git checkout -- \
    Silicon/Silicium/SiliciumPkg/Library/BootManagerLib/KeyCallback.c \
    Silicon/Silicium/SiliciumPkg/Library/BootManagerLib/BootManager.c \
    Mu_Basecore/MdeModulePkg/Core/Dxe/DxeMain/DxeMain.c \
    Mu_Basecore/MdeModulePkg/Universal/Acpi/AcpiPlatformDxe/AcpiPlatform.c 2>/dev/null || true

sh /root/data/restore_reference_drivers.sh > /root/data/restore-drivers.log 2>&1
cp -r "$REPO/Platforms/OnePlus/caihongPkg" Platforms/OnePlus/

python3 /root/data/enable_caihong_acpi.py
python3 /root/data/fix_acpi_guid.py

# Four consistent tables (PPTT stays out: it claims 12 CPUs vs MADT's 8).
python3 - "$INF" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="surrogateescape")
head = t.split("[Binaries]")[0].rstrip() + "\n\n[Binaries]\n"
p.write_text(head + "  ASL|DSDT.aml\n  ASL|FACP.aml\n  ASL|APIC.aml\n  ASL|GTDT.aml\n",
             encoding="utf-8", errors="surrogateescape")
PY

python3 /root/data/fix_memory_map_8gb.py > /root/data/memmap.log 2>&1 || true

# --- the actual fix: expose every ACPI table version ---
python3 - "$DSC" <<'PY'
import re, sys, pathlib
p = pathlib.Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="surrogateescape")

line = ("  # caihong: AArch64 defaults to ACPI 6.0 only, which drops our rev-5\n"
        "  # APIC / rev-2 DSDT and GTDT from the XSDT.  Expose all versions.\n"
        "  gEfiMdeModulePkgTokenSpaceGuid.PcdAcpiExposedTableVersions|0x3F")

if "PcdAcpiExposedTableVersions" in t:
    t = re.sub(r"(?m)^.*PcdAcpiExposedTableVersions.*$", line, t, count=1)
elif "[PcdsFixedAtBuild" in t:
    t = re.sub(r"(?m)^(\[PcdsFixedAtBuild[^\]]*\]\s*)$", r"\1\n" + line, t, count=1)
else:
    t += "\n[PcdsFixedAtBuild]\n" + line + "\n"
p.write_text(t, encoding="utf-8", errors="surrogateescape")
print("ACPI version override:", [l.strip() for l in t.splitlines() if "ExposedTableVersions" in l])
PY

export CLANGPDB_AARCH64_PREFIX=aarch64-linux-gnu-
echo "=== building RELEASE (ACPI version fix) ==="
"$WORK/.venv/bin/python" build_uefi.py -d caihong -r RELEASE > /root/data/build-acpiver.log 2>&1
tail -4 /root/data/build-acpiver.log
ls -l Mu-caihong*.img

echo "=== verify the PCD resolved to 0x3F ==="
grep -h "_PCD_VALUE_PcdAcpiExposedTableVersions" \
  Build/caihongPkg/RELEASE_CLANGPDB/AARCH64/MdeModulePkg/Universal/Acpi/AcpiTableDxe/AcpiTableDxe/DEBUG/AutoGen.h 2>/dev/null | head -2
