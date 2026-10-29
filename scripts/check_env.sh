#!/bin/sh
# Audit the build environment for the caihong (SM8650) Windows-on-ARM port.
#
# SPDX-License-Identifier: GPL-2.0-only
#
# Read-only: inspects the host, reports what is present and what is missing,
# and exits non-zero only when a HARD requirement is missing.  Soft
# requirements are reported but do not fail the run.
#
# Usage:  sh scripts/check_env.sh
# Runs on Linux (including WSL).  On Windows, use PowerShell for the host half
# (see the "Windows host" section below) and run this inside WSL.
set -u
CDPATH=

ok=0
fail=0
have() { printf '  [ OK ] %s\n' "$*"; ok=$((ok+1)); }
miss() { printf '  [MISS] %s\n' "$*"; fail=$((fail+1)); }
soft() { printf '  [ -- ] %s\n' "$*"; }

echo "=============================================================="
echo " caihong WoA port - environment audit"
echo "=============================================================="

echo
echo "-- host --"
printf '  kernel : %s\n' "$(uname -srm 2>/dev/null || echo unknown)"
if [ -r /etc/os-release ]; then
	. /etc/os-release
	printf '  distro : %s %s\n' "${NAME:-?}" "${VERSION_ID:-?}"
fi
printf '  cwd    : %s\n' "$(pwd)"
if command -v df >/dev/null 2>&1; then
	printf '  disk   : %s free on this filesystem\n' "$(df -h . | awk 'NR==2{print $4}')"
fi
printf '  ram    : %s\n' "$(awk '/MemTotal/{printf "%.1f GiB", $2/1048576}' /proc/meminfo 2>/dev/null || echo unknown)"

echo
echo "-- hard requirements --"
for t in python3 make git; do
	if command -v "$t" >/dev/null 2>&1; then have "$t ($("$t" --version 2>&1 | head -1))"; else miss "$t"; fi
done

CROSS=""
for p in aarch64-none-elf-gcc aarch64-linux-gnu-gcc aarch64-elf-gcc; do
	if command -v "$p" >/dev/null 2>&1; then CROSS="$p"; break; fi
done
if [ -n "$CROSS" ]; then have "aarch64 cross gcc: $CROSS ($("$CROSS" --version | head -1))"
else miss "aarch64 cross gcc (Alpine: apk add gcc-aarch64-none-elf binutils-aarch64-none-elf)"; fi

if [ -n "$CROSS" ]; then
	for b in objcopy; do
		if command -v "aarch64-none-elf-$b" >/dev/null 2>&1 || command -v "aarch64-linux-gnu-$b" >/dev/null 2>&1; then
			have "aarch64 $b"
		else miss "aarch64 $b"; fi
	done
fi

echo
echo "-- soft requirements (needed for parts of the pipeline) --"
for t in iasl dtc zstd clang lld; do
	if command -v "$t" >/dev/null 2>&1; then soft "$t present: $(command -v "$t")"
	else soft "$t absent (optional; iasl also ships in Mu-Qcom as Compiler/iasl.exe)"; fi
done

# Python modules used by the ACPI/build tooling
if command -v python3 >/dev/null 2>&1; then
	if python3 -c 'import edk2toolext' >/dev/null 2>&1; then
		have "edk2-pytool-extensions (python)"
	else
		soft "edk2-pytool-extensions missing: python3 -m pip install --break-system-packages -r pip-requirements.txt"
	fi
fi

echo
echo "-- project tree --"
for d in source/Mu-Qcom-musabcel source/caihong-linux-rootfs source/linux-caihong acpi/caihong scripts; do
	if [ -d "$d" ]; then soft "present: $d"; else soft "MISSING: $d (run scripts/fetch_sources.sh)"; fi
done

echo
echo "-- device images (read-only inputs) --"
# The stock firmware is what every address in this port is derived from.
for f in dtbo.img vendor_boot.img boot.img uefi.img xbl.img abl.img; do
	found=""
	for base in /mnt/e/1+padpro/oxygenos /e/1+padpro/oxygenos "E:/1+padpro/oxygenos"; do
		if [ -f "$base/$f" ]; then found="$base/$f"; break; fi
	done
	if [ -n "$found" ]; then soft "found $f"; else soft "absent $f"; fi
done

echo
echo "=============================================================="
printf ' hard checks: %d ok, %d missing\n' "$ok" "$fail"
echo "=============================================================="
if [ "$fail" -ne 0 ]; then
	echo "Environment is NOT ready. Install the missing hard requirements above." >&2
	exit 1
fi
echo "Hard requirements satisfied."
exit 0
