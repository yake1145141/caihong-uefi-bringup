#!/bin/sh
# Build the caihong (OnePlus Pad Pro, SM8650) UEFI firmware, or a reference
# device used to prove the toolchain.
#
# SPDX-License-Identifier: GPL-2.0-only
#
# Intended to run INSIDE the WSL Alpine environment (or any Linux with the
# same packages).  Run from the Mu-Qcom checkout root.
#
#   scripts/build_uefi.sh -d caihong          # the actual target
#   scripts/build_uefi.sh -d aston            # reference build (SM8550)
#
# Environment:
#   MUQCOM_DIR   path to the Mu-Qcom checkout (default: ./source/Mu-Qcom-musabcel
#                when invoked from the project root, else the current dir)
#   BUILD_DEVICE fallback device if -d is not given
#
# Exit codes:
#   0  build succeeded
#   2  missing dependency
#   3  device config not found
#   4  compile failed
set -eu
CDPATH=

DEVICE=""
while [ $# -gt 0 ]; do
	case "$1" in
		-d|--device) DEVICE="$2"; shift 2 ;;
		-h|--help) sed -n '2,20p' "$0"; exit 0 ;;
		*) echo "unknown argument: $1" >&2; exit 64 ;;
	esac
done
DEVICE="${DEVICE:-${BUILD_DEVICE:-}}"
[ -n "$DEVICE" ] || { echo "error: no device given (-d <codename>)" >&2; exit 64; }

MUQCOM_DIR="${MUQCOM_DIR:-}"
if [ -z "$MUQCOM_DIR" ]; then
	if [ -d source/Mu-Qcom-musabcel ]; then MUQCOM_DIR=source/Mu-Qcom-musabcel
	elif [ -d Platforms ] && [ -d Silicon ]; then MUQCOM_DIR=.
	else echo "error: cannot locate the Mu-Qcom checkout (set MUQCOM_DIR)" >&2; exit 2
	fi
fi
cd "$MUQCOM_DIR"

# ---------------------------------------------------------------- dependencies
need=""
command -v python3  >/dev/null 2>&1 || need="$need python3"
command -v make     >/dev/null 2>&1 || need="$need make"
command -v git      >/dev/null 2>&1 || need="$need git"
CROSS=""
for p in aarch64-none-elf-gcc aarch64-linux-gnu-gcc aarch64-elf-gcc; do
	if command -v "$p" >/dev/null 2>&1; then CROSS="$p"; break; fi
done
[ -n "$CROSS" ] || need="$need aarch64-cross-gcc(gcc-aarch64-none-elf)"
if [ -n "$need" ]; then
	echo "error: missing dependencies:$need" >&2
	echo "  Alpine: apk add python3 make git gcc-aarch64-none-elf binutils-aarch64-none-elf" >&2
	exit 2
fi
echo "== cross compiler: $CROSS ($($CROSS --version | head -1))"

if [ ! -f "Resources/Configs/${DEVICE}.conf" ]; then
	echo "error: no device config Resources/Configs/${DEVICE}.conf" >&2
	exit 3
fi

# Python build tooling (edk2-pytool-extensions) -- idempotent.
if ! python3 -c "import edk2toolext" >/dev/null 2>&1; then
	echo "== installing python build requirements"
	python3 -m pip install --quiet --break-system-packages -r pip-requirements.txt \
		|| { echo "error: pip install failed" >&2; exit 2; }
fi

# ------------------------------------------------------------------ build
echo "== building device: $DEVICE"
set +e
./build_uefi.sh -d "$DEVICE" -r "${BUILD_MODE:-RELEASE}" > "build-${DEVICE}.log" 2>&1
rc=$?
set -e
echo "---- last 40 lines of build-${DEVICE}.log ----"
tail -40 "build-${DEVICE}.log" 2>/dev/null || true
echo "------------------------------------------------"
if [ "$rc" -ne 0 ]; then
	echo "== BUILD FAILED for $DEVICE (exit $rc); full log: build-${DEVICE}.log" >&2
	exit 4
fi

echo "== build succeeded; artifacts:"
ls -l "Mu-${DEVICE}".* 2>/dev/null || true
find Build -maxdepth 3 -name '*.fd' -o -maxdepth 3 -name '*.efi' 2>/dev/null | head -20
