#!/bin/sh
# Normalise line endings in the Mu-Qcom checkout.
#
# SPDX-License-Identifier: GPL-2.0-only
#
# Why this exists: cloning the Mu-Qcom repositories on Windows with the default
# core.autocrlf=true rewrites every text file to CRLF.  The shell build entry
# point then fails with the extremely unhelpful
#
#     ./build_uefi.sh: cannot execute: required file not found
#
# because the kernel looks for an interpreter literally named "/bin/bash\r".
# Makefiles and .patch files break in similarly confusing ways.
#
# This script converts only the files whose line endings actually matter to the
# build, which is fast even on a checkout with large submodules (a full-tree
# scan of Edk2 on a 9p/DrvFs mount takes many minutes).
#
# Usage (inside WSL/Linux):
#   sh scripts/fix_line_endings.sh [<muqcom-dir>]
set -eu
CDPATH=

root=$(cd -- "$(dirname -- "$0")/.." && pwd)
dir="${1:-$root/source/Mu-Qcom-musabcel}"
[ -d "$dir" ] || { echo "error: not a directory: $dir" >&2; exit 2; }
cd "$dir"

echo "== normalising line endings under $dir"

converted=0
# Convert one file in place; report if it actually changed.
conv() {
	f=$1
	[ -f "$f" ] || return 0
	if grep -q "$(printf '\r')" "$f" 2>/dev/null; then
		sed -i 's/\r$//' "$f"
		converted=$((converted + 1))
		echo "   fixed: $f"
	fi
}

# 1) Shell entry points and helper scripts at the top level.
for f in *.sh docker-build.sh; do conv "$f"; done

# 2) Every *.sh reachable in the repo (excluding submodule internals, which
#    gcc/EDK2 tolerate either way, and .git).
find . -maxdepth 4 -name '*.sh' -not -path './.git/*' -print 2>/dev/null | while read -r f; do
	conv "$f"
done

# 3) Makefiles that the build actually runs (BootShim is compiled directly).
conv BootShim/Makefile
find . -maxdepth 3 -name 'Makefile' -not -path './.git/*' -print 2>/dev/null | while read -r f; do
	conv "$f"
done

# 4) The Mu patch series: `git apply` rejects CRLF-corrupted diffs.
for f in Resources/MuPatches/*.patch; do conv "$f"; done

# 5) The board package we added, and the build config.
for f in Resources/Configs/caihong.conf \
         Platforms/OnePlus/caihongPkg/*.dsc \
         Platforms/OnePlus/caihongPkg/*.dec \
         Platforms/OnePlus/caihongPkg/*.fdf \
         Platforms/OnePlus/caihongPkg/DeviceBuild.py \
         Silicon/Qualcomm/CliffsPkg/*.inc; do
	conv "$f"
done

echo "== files changed: see lines above"
echo "== verify:"
head -1 build_uefi.sh | od -c | head -1
if head -1 build_uefi.sh | grep -q "$(printf '\r')"; then
	echo "!! build_uefi.sh still has CRLF" >&2
	exit 1
fi
echo "== build_uefi.sh shebang is LF-terminated"
exit 0
