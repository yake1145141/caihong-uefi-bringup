#!/bin/sh
# Build a DEBUG image that dumps the installed ACPI tables (RSDP/XSDT) and halts.
#
# No source patching of MsBootPolicy: the dump is a standalone DXE driver whose
# DEPEX (SimpleFileSystem) guarantees ACPI is fully installed by then.
set -eu
REPO=/root/data/uefi-caihong
UEFI=/root/data/caihong-work/uefi
WORK=/root/data/caihong-work
INF=$UEFI/Silicium-ACPI/Platforms/OnePlus/caihong/AcpiTables.inf
PKG=$UEFI/Platforms/OnePlus/caihongPkg
DSC=$PKG/caihong.dsc
FDF=$PKG/caihong.fdf
cd "$UEFI"

sh /root/data/restore_reference_drivers.sh > /root/data/restore-drivers.log 2>&1
cp -r "$REPO/Platforms/OnePlus/caihongPkg" Platforms/OnePlus/

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

python3 /root/data/fix_memory_map_8gb.py > /root/data/memmap.log 2>&1 || true

# --- inject AcpiDumpDxe ---
mkdir -p "$PKG/Drivers/AcpiDumpDxe"
cp /root/data/acidump/AcpiDumpDxe.c "$PKG/Drivers/AcpiDumpDxe/"
cp /root/data/acidump/AcpiDumpDxe.inf "$PKG/Drivers/AcpiDumpDxe/"

python3 - "$DSC" "$FDF" <<'PY'
import re, sys, pathlib
dsc, fdf = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
line = "  caihongPkg/Drivers/AcpiDumpDxe/AcpiDumpDxe.inf"

t = dsc.read_text(encoding="utf-8", errors="surrogateescape")
anchor = "  caihong/AcpiTables.inf"
if line not in t and anchor in t:
    t = t.replace(anchor, anchor + "\n" + line, 1)
t = dsc.read_text(encoding="utf-8", errors="surrogateescape") if False else t

vers = "  gEfiMdeModulePkgTokenSpaceGuid.PcdAcpiExposedTableVersions|0x3F"
dbg  = "  gEfiMdePkgTokenSpaceGuid.PcdDebugPrintErrorLevel|0x80000040"
if "PcdAcpiExposedTableVersions" in t:
    t = re.sub(r"(?m)^.*PcdAcpiExposedTableVersions.*$", vers, t, count=1)
if "PcdDebugPrintErrorLevel" in t:
    t = re.sub(r"(?m)^\s*gEfiMdePkgTokenSpaceGuid\.PcdDebugPrintErrorLevel.*$", dbg, t)
elif "[PcdsFixedAtBuild" in t:
    t = re.sub(r"(?m)^(\[PcdsFixedAtBuild[^\]]*\]\s*)$", r"\1\n" + dbg, t, count=1)
dsc.write_text(t, encoding="utf-8", errors="surrogateescape")

f = fdf.read_text(encoding="utf-8", errors="surrogateescape")
anchor = "  INF RuleOverride = ACPITABLE caihong/AcpiTables.inf"
if "AcpiDumpDxe" not in f:
    if anchor not in f:
        raise SystemExit("ERROR: FDF anchor missing")
    f = f.replace(anchor, anchor + "\n\n  INF caihongPkg/Drivers/AcpiDumpDxe/AcpiDumpDxe.inf", 1)
    fdf.write_text(f, encoding="utf-8", errors="surrogateescape")
print("dsc:", line in dsc.read_text(encoding="utf-8", errors="surrogateescape"),
      "fdf:", "AcpiDumpDxe" in fdf.read_text(encoding="utf-8", errors="surrogateescape"))
PY

export CLANGPDB_AARCH64_PREFIX=aarch64-linux-gnu-
echo "=== building DEBUG (ACPI dump driver) ==="
"$WORK/.venv/bin/python" build_uefi.py -d caihong -r DEBUG > /root/data/build-acpidump2.log 2>&1
tail -4 /root/data/build-acpidump2.log
grep -n 'error:' /root/data/build-acpidump2.log | head -4 || true
ls -l Mu-caihong*.img
