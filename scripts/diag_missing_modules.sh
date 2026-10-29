#!/bin/sh
# Diagnose why specific modules are missing from the produced firmware volume.
#
# SPDX-License-Identifier: GPL-2.0-only
#
# Usage (inside the build tree):
#   sh diag_missing_modules.sh <repo-root> <module> [<module> ...]
#
# Reports, per module:
#   1. whether the platform's Include/*.inc still references it (and how)
#   2. the INF that was generated for it, its FILE_GUID and depex state
#   3. whether that GUID appears anywhere under Build/.../FV/Ffs
#   4. whether the GUID or the base name collides with another generated module
#
# A GUID collision is the usual explanation: EDK2 keys FFS files by GUID, so
# two INFs sharing one FILE_GUID silently produce a single FFS entry.
set -u
CDPATH=

root="${1:?usage: $0 <repo-root> <module> [<module>...]}"
shift
[ $# -ge 1 ] || { echo "no modules given" >&2; exit 64; }

pkg="$root/Platforms/OnePlus/caihongPkg"
build_dir="$root/Build/caihongPkg/RELEASE_CLANGPDB/FV/Ffs"
bin_dir="$root/Binaries/caihong/QcomPkg/Drivers"

echo "=============================================================="
echo " repo    : $root"
echo " pkg     : $pkg"
echo " FV/Ffs  : $build_dir"
echo "=============================================================="

for mod in "$@"; do
	echo
	echo "########## $mod ##########"

	echo "-- 1. references in Include/*.inc --"
	grep -rn "$mod" "$pkg/Include/" 2>/dev/null | sed 's/^/   /' || echo "   (none)"

	echo "-- 2. generated INF --"
	inf=$(find "$bin_dir" -iname "$mod.inf" 2>/dev/null | head -1)
	if [ -z "$inf" ]; then
		echo "   INF NOT FOUND under $bin_dir"
		continue
	fi
	echo "   path: ${inf#$root/}"
	grep -E 'BASE_NAME|FILE_GUID|MODULE_TYPE' "$inf" | sed 's/^/   /'
	dep=$(dirname "$inf")/$(basename "$inf" .inf).depex
	if [ -f "$dep" ]; then
		printf '   depex: %s bytes: ' "$(wc -c < "$dep" | tr -d ' ')"
		od -An -tx1 "$dep" | tr -d '\n' | cut -c1-40
		echo
	else
		echo "   depex: absent"
	fi

	guid=$(grep -i 'FILE_GUID' "$inf" | head -1 | sed 's/.*= *//' | tr -d ' \r')
	base=$(grep -i 'BASE_NAME' "$inf" | head -1 | sed 's/.*= *//' | tr -d ' \r')
	echo "   guid=$guid  base=$base"

	echo "-- 3. GUID present in FV/Ffs? --"
	if [ -d "$build_dir" ]; then
		n=$(ls "$build_dir" | grep -i -c "^$guid" || true)
		echo "   matches: $n"
		ls "$build_dir" | grep -i "^$guid" | sed 's/^/   /' || true
	else
		echo "   FV/Ffs directory missing"
	fi

	echo "-- 4. collisions --"
	echo "   same GUID in other generated INFs:"
	grep -ril "FILE_GUID *= *$guid" "$bin_dir" 2>/dev/null \
		| grep -vi "/$(basename "$(dirname "$inf")")/" | sed 's/^/     /' || true
	echo "   same BASE_NAME elsewhere:"
	find "$bin_dir" -iname "$base.inf" 2>/dev/null | sed 's/^/     /' || true
done
