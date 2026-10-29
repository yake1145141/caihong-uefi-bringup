#!/bin/sh
# Restore the real VcsDxe / RscDxe (un-stubbed, built from this device's own
# uefi.img).
#
# The reference project replaces both drivers' entry points with `mov x0,#0;ret`
# to stop VcsDxe from powering the panel down.  That also means the voltage
# domain subsystem is never brought up, and a later register access to the AOSS
# block faults:
#
#   ESR 0x96000010  -> Data abort, EA=1 (synchronous external abort)
#   FAR 0x0C792008  -> inside AOSS (0x0B000000 + 0x04000000)
#
# i.e. something touched an unpowered peripheral.  Try the real drivers.
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

swap VcsDxe VcsDxe
swap RscDxe RscDxe
