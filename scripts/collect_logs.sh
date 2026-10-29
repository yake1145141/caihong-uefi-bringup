#!/bin/sh
# Collect build/test logs into a single timestamped bundle for the caihong port.
#
# SPDX-License-Identifier: GPL-2.0-only
#
# Read-only with respect to sources: it copies logs into
# artifacts/logs-<UTC timestamp>/ and writes an index with commit ids, host
# information and the checksums of the collected files.
#
# Usage:  sh scripts/collect_logs.sh [extra-file ...]
set -u
CDPATH=

root=$(cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root" || exit 1

ts=$(date -u +%Y%m%dT%H%M%SZ 2>/dev/null || echo unknown)
dest="artifacts/logs-$ts"
mkdir -p "$dest" || exit 1

n=0
copy() {
	src=$1
	[ -f "$src" ] || return 0
	# flatten the path but keep it recognisable: a_b_c.log
	name=$(printf '%s' "$src" | sed 's|^\./||; s|[/\\]|_|g')
	cp -- "$src" "$dest/$name" 2>/dev/null && n=$((n+1))
}

echo "== collecting logs into $dest"

# Build logs from the Mu-Qcom tree and from the wrapper script
copy source/Mu-Qcom-musabcel/build-aston.log
copy source/Mu-Qcom-musabcel/build-caihong.log
copy work/build-aston.log
copy work/build-caihong.log
copy work/pip.log
copy work/qcom-Makefile.txt

# Anything else the caller points at
for f in "$@"; do copy "$f"; done

# ACPI generation record
copy build/acpi/soc-tables.json

# ---------------------------------------------------------------- index
{
	echo "caihong WoA port - log bundle"
	echo "generated: $(date -u 2>/dev/null || echo unknown) UTC"
	echo
	echo "== host =="
	uname -srm 2>/dev/null || echo unknown
	[ -r /etc/os-release ] && (. /etc/os-release; echo "$NAME $VERSION_ID")
	echo
	echo "== source commits =="
	for f in source/*.commit; do
		[ -f "$f" ] || continue
		printf '  %-34s %s\n' "$(basename "$f" .commit)" "$(cat "$f")"
	done
	for d in source/Mu-Qcom-musabcel source/caihong-linux-rootfs source/linux-caihong; do
		if [ -d "$d/.git" ]; then
			printf '  %-34s %s\n' "$d" "$(git -C "$d" rev-parse HEAD 2>/dev/null)"
		fi
	done
	echo
	echo "== collected files =="
	(cd "$dest" && ls -l 2>/dev/null)
	echo
	echo "== checksums =="
	(cd "$dest" && sha256sum ./* 2>/dev/null)
} > "$dest/INDEX.txt" 2>/dev/null

echo "== collected $n file(s)"
[ -f "$dest/INDEX.txt" ] && echo "== index: $dest/INDEX.txt"
echo "== note: logs under $dest are NOT part of artifacts/SHA256SUMS"
echo "   (they change on every run); the index records their own digests."
exit 0
