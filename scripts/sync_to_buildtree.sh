#!/bin/sh
# Sync the editable board sources from the Windows workspace into the WSL
# native-filesystem build tree.
#
# SPDX-License-Identifier: GPL-2.0-only
#
# WHY A SEPARATE BUILD TREE
# -------------------------
# Building Mu-Qcom directly on /mnt/e (the Windows drive through 9p/DrvFs) is
# unusable: NuGet's mono process managed ~8 seconds of CPU time in 30 minutes
# and never finished extracting a package, because every small-file write goes
# through the 9p protocol.  The tree is therefore copied once to /root/muqcom
# (ext4) and builds run there.  Measured: the same tree builds normally.
#
# This script only refreshes the handful of files that this project actually
# edits, so the expensive 2.1 GB copy does not have to be repeated.
#
# Usage (inside WSL):
#   sh scripts/sync_to_buildtree.sh [<build-tree>]
set -eu
CDPATH=

# Resolve the source tree relative to this script's own location.
here=$(cd -- "$(dirname -- "$0")/.." && pwd)
src="$here/source/Mu-Qcom-musabcel"
dst="${1:-/root/muqcom}"

[ -d "$src" ] || { echo "error: source tree not found: $src" >&2; exit 2; }
[ -d "$dst" ] || { echo "error: build tree not found: $dst" >&2
	echo "       create it first:  cp -a \"$src\" \"$dst\"" >&2
	exit 2; }

echo "== syncing $src -> $dst"

# Files/directories this port owns.
for rel in \
	"Platforms/OnePlus/caihongPkg" \
	"Silicon/Qualcomm/CliffsPkg" \
	"Silicium-ACPI/SoCs/Qualcomm/Cliffs" \
	"Silicium-ACPI/Platforms/OnePlus/caihong" ; do
	if [ -d "$src/$rel" ]; then
		mkdir -p "$dst/$rel"
		cp -a "$src/$rel/." "$dst/$rel/"
		echo "   dir  $rel"
	fi
done

for rel in \
	"Resources/Configs/caihong.conf" \
	"Resources/Scripts/caihong.sh" ; do
	if [ -f "$src/$rel" ]; then
		mkdir -p "$(dirname "$dst/$rel")"
		cp -a "$src/$rel" "$dst/$rel"
		echo "   file $rel"
	fi
done

# Files that came from a Windows checkout may carry CRLF, which the EDK2 DSC
# parser and the shell both dislike.  Normalise only what we just copied.
find "$dst/Platforms/OnePlus/caihongPkg" \
     "$dst/Silicon/Qualcomm/CliffsPkg" \
     "$dst/Silicium-ACPI/SoCs/Qualcomm/Cliffs" \
     "$dst/Silicium-ACPI/Platforms/OnePlus/caihong" \
     -type f 2>/dev/null | while read -r f; do
	case "$f" in
		*.dsc|*.dec|*.fdf|*.inc|*.inf|*.c|*.h|*.asl|*.dsl|*.sh|*.conf)
			sed -i 's/\r$//' "$f" ;;
	esac
done
sed -i 's/\r$//' "$dst/Resources/Configs/caihong.conf" 2>/dev/null || true
sed -i 's/\r$//' "$dst/Resources/Scripts/caihong.sh" 2>/dev/null || true

echo "== sync complete"
