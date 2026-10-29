#!/bin/sh
# Diagnose why GenFds cannot produce a DEPEX section (.dpx) for a prebuilt
# driver: run GenSec by hand with exactly the arguments BaseTools used.
#
# SPDX-License-Identifier: GPL-2.0-only
#
# Usage (inside WSL):
#   sh scripts/diag_gensec.sh <repo-root> <driver-name>
# e.g.
#   sh scripts/diag_gensec.sh /root/muqcom EnvDxe
set -u
CDPATH=

root="${1:-/root/muqcom}"
drv="${2:-EnvDxe}"
tools="$root/Mu_Basecore/BaseTools/Bin/Mu-Basetools_extdep/Linux-x86"
depex="$root/Binaries/caihong/QcomPkg/Drivers/$drv/$drv.depex"
out="/tmp/gensec-$drv.dpx"

echo "tools dir : $tools"
echo "depex     : $depex"
[ -d "$tools" ] || { echo "MISSING tools dir" >&2; exit 2; }
[ -f "$depex" ] || { echo "MISSING depex" >&2; exit 2; }
printf 'depex hex : '
od -An -tx1 "$depex" | tr -s ' \n' ' '
echo

echo "--- GenSec directly ---"
"$tools/GenSec" -s EFI_SECTION_DXE_DEPEX -o "$out" "$depex"
rc=$?
echo "rc=$rc"
if [ -f "$out" ]; then
	echo "output    : $(wc -c < "$out") bytes"
	od -An -tx1 "$out" | head -3
else
	echo "output    : NOT CREATED"
fi

echo "--- is GenSec on PATH during a build? ---"
echo "PATH=$PATH" | tr ':' '\n' | grep -c 'Basetools_extdep' || true
