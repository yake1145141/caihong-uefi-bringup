#!/bin/sh
# Swap UFSDxe for the build extracted from THIS device's own uefi.img.
#
# Background: the reference project ships vendor drivers taken from the author's
# Android 16 firmware, while this device runs Android 15.  UFSDxe is where the
# reference firmware dies (UFS.c +2172, EFI_DEVICE_ERROR, ufs_error_log 11/3b/55),
# so try the driver that matches our own firmware instead.
#
# The reference's binary patch for UFSDxe targets an offset valid only for ITS
# build, so the INF is pointed back at the unpatched file.
set -eu
U=/root/data/caihong-work/uefi/Binaries/caihong/QcomPkg/Drivers/UFSDxe

echo "=== before ==="
ls -l "$U"
grep -i 'PE32' "$U/UFSDxe.inf" || true

cp /root/data/ours-UFSDxe.efi "$U/UFSDxe.efi"
rm -f "$U/UFSDxe.patched.efi"
sed -i 's|PE32|UFSDxe.patched.efi|*|PE32|UFSDxe.efi|*|' "$U/UFSDxe.inf" 2>/dev/null || true
# sed with pipes is awkward; rewrite explicitly:
python3 - <<'PY'
import re, pathlib
p = pathlib.Path("/root/data/caihong-work/uefi/Binaries/caihong/QcomPkg/Drivers/UFSDxe/UFSDxe.inf")
t = p.read_text()
t = t.replace("PE32|UFSDxe.patched.efi|*", "PE32|UFSDxe.efi|*")
p.write_text(t)
print("inf now:", [l for l in t.splitlines() if "PE32" in l])
PY

echo "=== after ==="
ls -l "$U"
sha256sum "$U/UFSDxe.efi"
