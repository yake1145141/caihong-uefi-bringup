#!/bin/sh
# Swap the remaining patched power/clock drivers for the builds extracted from
# THIS device's own uefi.img.
#
# The reference project patches ClockDxe, SPMIDxe and PmicDxeLa.  All three sit
# under the UFS power/clock path, and UFS initialization still fails with
# EFI_DEVICE_ERROR after swapping UFSDxe alone, so align these too.  Their
# binary patches are offset-specific, so the INFs are pointed back at the
# unpatched files.
set -eu
B=/root/data/caihong-work/uefi/Binaries/caihong/QcomPkg/Drivers

swap() {
  dir=$1
  base=$2
  echo "--- $dir / $base"
  cp "/root/data/ours-$base.efi" "$B/$dir/$base.efi"
  rm -f "$B/$dir/$base.patched.efi"
  python3 - "$B/$dir/$base.inf" "$base" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); base = sys.argv[2]
t = p.read_text().replace(f"PE32|{base}.patched.efi|*", f"PE32|{base}.efi|*")
p.write_text(t)
print("   ", [l.strip() for l in t.splitlines() if "PE32" in l])
PY
  sha256sum "$B/$dir/$base.efi"
}

swap ClockDxe ClockDxe
swap SPMIDxe  SPMIDxe
swap PmicDxe  PmicDxeLa
