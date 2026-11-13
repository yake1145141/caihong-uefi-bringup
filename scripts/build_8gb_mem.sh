#!/bin/sh
# Build: minimal ACPI set + completed 8 GB memory map.
#
# The memory-map patch MUST run after the platform package is copied from the
# reference repo, otherwise the copy overwrites it.
set -eu
REPO=/root/data/uefi-caihong
UEFI=/root/data/caihong-work/uefi
WORK=/root/data/caihong-work
INF=$UEFI/Silicium-ACPI/Platforms/OnePlus/caihong/AcpiTables.inf
cd "$UEFI"

git checkout -- \
    Silicon/Silicium/SiliciumPkg/Library/BootManagerLib/KeyCallback.c \
    Silicon/Silicium/SiliciumPkg/Library/BootManagerLib/BootManager.c \
    Mu_Basecore/MdeModulePkg/Core/Dxe/DxeMain/DxeMain.c \
    Mu_Basecore/MdeModulePkg/Universal/Acpi/AcpiPlatformDxe/AcpiPlatform.c 2>/dev/null || true

sh /root/data/restore_reference_drivers.sh > /root/data/restore-drivers.log 2>&1
cp -r "$REPO/Platforms/OnePlus/caihongPkg" Platforms/OnePlus/

# ACPI: the four tables Windows needs, and none of the malformed extras.
python3 /root/data/enable_caihong_acpi.py
python3 /root/data/fix_acpi_guid.py
python3 - "$INF" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="surrogateescape")
head = t.split("[Binaries]")[0].rstrip() + "\n\n[Binaries]\n"
t = head + "  ASL|DSDT.aml\n  ASL|FACP.aml\n  ASL|APIC.aml\n  ASL|GTDT.aml\n"
p.write_text(t, encoding="utf-8", errors="surrogateescape")
PY

# Memory map: describe the full 8 GB (after the package copy!).
python3 /root/data/fix_memory_map_8gb.py

echo "=== memory map Conv entries ==="
grep -n 'Conv,' Platforms/OnePlus/caihongPkg/Library/MemoryMapLib/MemoryMapLib.c | head -12
echo "=== installed ACPI tables ==="
sed -n '/\[Binaries\]/,$p' "$INF"

export CLANGPDB_AARCH64_PREFIX=aarch64-linux-gnu-
echo "=== building RELEASE ==="
"$WORK/.venv/bin/python" build_uefi.py -d caihong -r RELEASE > /root/data/build-8gb.log 2>&1
tail -4 /root/data/build-8gb.log
ls -l Mu-caihong*.img
