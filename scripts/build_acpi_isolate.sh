#!/bin/sh
# Isolation build for the ACPI regression:
#
#   * disable ONLY AcpiPlatformDxe (keep AcpiTableDxe + the six AML tables)
#   * DEBUG build, console filtered to ERROR|WARN so errors stay on the panel
#
# The clean ACPI RELEASE build black-screens while the original firmware shows
# the boot menu, so bisect the three ACPI components.  AcpiPlatformDxe is the
# first suspect: it walks/installs the tables very early in DXE.
set -eu
UEFI=/root/data/caihong-work/uefi
WORK=/root/data/caihong-work
cd "$UEFI"

F=Platforms/OnePlus/caihongPkg/caihong.fdf
D=Platforms/OnePlus/caihongPkg/caihong.dsc

# 1. Disable AcpiPlatformDxe only (idempotent).
sed -i 's|^  INF MdeModulePkg/Universal/Acpi/AcpiPlatformDxe/AcpiPlatformDxe.inf|  #INF MdeModulePkg/Universal/Acpi/AcpiPlatformDxe/AcpiPlatformDxe.inf  # isolation: disabled|' "$F"
grep -n "Acpi" "$F"

# 2. Quiet console: only ERROR|WARN, inserted into an existing
#    [PcdsFixedAtBuild] section if present, otherwise appended.
python3 - "$D" <<'PY'
import re
import sys
import pathlib
p = pathlib.Path(sys.argv[1])
t = p.read_text(encoding="utf-8", errors="surrogateescape")
line = "  gEfiMdePkgTokenSpaceGuid.PcdDebugPrintErrorLevel|0x80000040"
if "PcdDebugPrintErrorLevel" in t:
    import re
    t = re.sub(r"(?m)^\s*gEfiMdePkgTokenSpaceGuid\.PcdDebugPrintErrorLevel.*$", line, t)
elif "[PcdsFixedAtBuild" in t:
    # insert right after the first [PcdsFixedAtBuild*] header
    t = re.sub(r"(?m)^(\[PcdsFixedAtBuild[^\]]*\]\s*)$", r"\1\n" + line, t, count=1)
else:
    t += "\n[PcdsFixedAtBuild]\n" + line + "\n"
p.write_text(t, encoding="utf-8", errors="surrogateescape")
print("debug level:", [l.strip() for l in t.splitlines() if "PcdDebugPrintErrorLevel" in l])
PY

# 3. Make sure no colour markers remain enabled.
if grep -q "CAIHONG_BRINGUP_MARKERS" "$D"; then
  sed -i 's/-DCAIHONG_BRINGUP_MARKERS=1//g' "$D"
fi

export CLANGPDB_AARCH64_PREFIX=aarch64-linux-gnu-

echo "=== building DEBUG (isolation + quiet) ==="
"$WORK/.venv/bin/python" build_uefi.py -d caihong -r DEBUG > /root/data/build-acpi-iso.log 2>&1
tail -5 /root/data/build-acpi-iso.log
ls -l Mu-caihong*.img
