#!/bin/sh
# Build a DEBUG image that runs the UFS large-read test at boot.
#
# Configuration: completed 8 GB memory map + minimal ACPI set + UfsReadTestDxe.
# DEBUG is required because DEBUG() macros compile out in RELEASE.
set -eu
REPO=/root/data/uefi-caihong
UEFI=/root/data/caihong-work/uefi
WORK=/root/data/caihong-work
INF=$UEFI/Silicium-ACPI/Platforms/OnePlus/caihong/AcpiTables.inf
PKG=$UEFI/Platforms/OnePlus/caihongPkg
DSC=$PKG/caihong.dsc
FDF=$PKG/caihong.fdf
cd "$UEFI"

git checkout -- \
    Silicon/Silicium/SiliciumPkg/Library/BootManagerLib/KeyCallback.c \
    Silicon/Silicium/SiliciumPkg/Library/BootManagerLib/BootManager.c \
    Mu_Basecore/MdeModulePkg/Core/Dxe/DxeMain/DxeMain.c \
    Mu_Basecore/MdeModulePkg/Universal/Acpi/AcpiPlatformDxe/AcpiPlatform.c 2>/dev/null || true

sh /root/data/restore_reference_drivers.sh > /root/data/restore-drivers.log 2>&1
cp -r "$REPO/Platforms/OnePlus/caihongPkg" Platforms/OnePlus/

# --- ACPI first: this un-comments the FDF/DSC anchors the driver patch needs ---
python3 /root/data/enable_caihong_acpi.py
python3 /root/data/fix_acpi_guid.py
python3 - "$INF" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="surrogateescape")
head = t.split("[Binaries]")[0].rstrip() + "\n\n[Binaries]\n"
p.write_text(head + "  ASL|DSDT.aml\n  ASL|FACP.aml\n  ASL|APIC.aml\n  ASL|GTDT.aml\n",
             encoding="utf-8", errors="surrogateescape")
PY

# --- inject the UFS read test driver (after the package copy and ACPI enable) ---
mkdir -p "$PKG/Drivers/UfsReadTestDxe"
cp /root/data/ufs-test/UfsReadTestDxe.c "$PKG/Drivers/UfsReadTestDxe/"
cp /root/data/ufs-test/UfsReadTestDxe.inf "$PKG/Drivers/UfsReadTestDxe/"

python3 - "$DSC" "$FDF" <<'PY'
import sys, pathlib
dsc, fdf = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
line = "  caihongPkg/Drivers/UfsReadTestDxe/UfsReadTestDxe.inf"

t = dsc.read_text(encoding="utf-8", errors="surrogateescape")
if line not in t:
    anchor = "  caihong/AcpiTables.inf"
    if anchor in t:
        t = t.replace(anchor, anchor + "\n" + line, 1)
    else:
        t = t.replace("[Components]", "[Components]\n" + line, 1)
    dsc.write_text(t, encoding="utf-8", errors="surrogateescape")

f = fdf.read_text(encoding="utf-8", errors="surrogateescape")
if "UfsReadTestDxe" not in f:
    anchor = "  INF RuleOverride = ACPITABLE caihong/AcpiTables.inf"
    if anchor not in f:
        raise SystemExit("ERROR: FDF anchor missing after ACPI enable")
    f = f.replace(anchor, anchor + "\n\n  # caihong bring-up: UFS large-read test\n  INF caihongPkg/Drivers/UfsReadTestDxe/UfsReadTestDxe.inf", 1)
    fdf.write_text(f, encoding="utf-8", errors="surrogateescape")
print("dsc:", line in dsc.read_text(encoding="utf-8", errors="surrogateescape"))
print("fdf:", "UfsReadTestDxe" in fdf.read_text(encoding="utf-8", errors="surrogateescape"))
PY

# Memory map: full 8 GB
python3 /root/data/fix_memory_map_8gb.py > /root/data/memmap.log 2>&1 || true
tail -2 /root/data/memmap.log

# Console: ERROR|WARN only
python3 - "$DSC" <<'PY'
import re, sys, pathlib
p = pathlib.Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="surrogateescape")
line = "  gEfiMdePkgTokenSpaceGuid.PcdDebugPrintErrorLevel|0x80000040"
if "PcdDebugPrintErrorLevel" in t:
    t = re.sub(r"(?m)^\s*gEfiMdePkgTokenSpaceGuid\.PcdDebugPrintErrorLevel.*$", line, t)
elif "[PcdsFixedAtBuild" in t:
    t = re.sub(r"(?m)^(\[PcdsFixedAtBuild[^\]]*\]\s*)$", r"\1\n" + line, t, count=1)
else:
    t += "\n[PcdsFixedAtBuild]\n" + line + "\n"
p.write_text(t, encoding="utf-8", errors="surrogateescape")
print("console filter set")
PY

export CLANGPDB_AARCH64_PREFIX=aarch64-linux-gnu-
echo "=== building DEBUG (UFS read test) ==="
"$WORK/.venv/bin/python" build_uefi.py -d caihong -r DEBUG > /root/data/build-ufstest.log 2>&1
tail -6 /root/data/build-ufstest.log
ls -l Mu-caihong*.img
