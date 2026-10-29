#!/bin/sh
# Verify the build artifacts of the caihong WoA port and (re)generate
# artifacts/SHA256SUMS.
#
# SPDX-License-Identifier: GPL-2.0-only
#
# This script is deliberately paranoid: it checks that each artifact is what it
# claims to be (size, ACPI checksum, PE/COFF machine type, ELF machine) rather
# than just listing files.  A file that merely exists is not evidence.
#
# Usage:
#   sh scripts/check_artifacts.sh            # verify + write SHA256SUMS
#   sh scripts/check_artifacts.sh --check    # verify against existing SHA256SUMS
set -u
CDPATH=

root=$(cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root" || exit 1
MODE="${1:-write}"
fail=0
checked=0

say_ok()  { printf '  [ OK ] %s\n' "$*"; checked=$((checked+1)); }
say_bad() { printf '  [FAIL] %s\n' "$*"; fail=1; }

echo "=============================================================="
echo " caihong artifact verification"
echo "=============================================================="

# ---------------------------------------------------------------- ACPI tables
echo
echo "-- ACPI tables (build/acpi) --"
ACPI_DIR=build/acpi
if [ ! -d "$ACPI_DIR" ]; then
	echo "  [SKIP] $ACPI_DIR absent - run scripts/build_acpi.ps1 first"
else
	for t in DSDT FACP APIC GTDT DBG2 PPTT; do
		f="$ACPI_DIR/$t.aml"
		if [ ! -f "$f" ]; then say_bad "$t.aml missing"; continue; fi
		# ACPI: every byte of the table must sum to 0 modulo 256.
		sum=$(od -An -tu1 -v "$f" | tr -s ' ' '\n' | awk 'NF{s+=$1} END{print s%256}')
		size=$(wc -c < "$f" | tr -d ' ')
		# table length field (offset 4, little endian) must equal file size
		len=$(od -An -tu4 -j4 -N4 "$f" | tr -d ' ')
		sig=$(dd if="$f" bs=1 count=4 2>/dev/null)
		if [ "$sum" != "0" ]; then
			say_bad "$t.aml checksum invalid (sum=$sum)"
		elif [ "$len" != "$size" ]; then
			say_bad "$t.aml length field $len != file size $size"
		elif [ "$sig" != "$t" ]; then
			say_bad "$t.aml signature '$sig' != '$t'"
		else
			say_ok "$t.aml  $size bytes  sig=$sig  checksum+length ok"
		fi
	done
fi

# ------------------------------------------------------------ UEFI firmware
echo
echo "-- UEFI firmware (Mu-Qcom build output) --"
found_fd=0
# The build runs either in the WSL-native tree (/root/muqcom) or on the remote
# Ubuntu host; finished images are copied here.  Three artifact sets are kept:
#   uefi/         SM8550 placeholder drivers (pipeline validation only)
#   uefi-ubuntu/  same, built on glibc     (reproducibility evidence, B13)
#   uefi-real/    built with the SM8650 drivers recovered from the device's own
#                 uefi.img (B14) -- the only set that reflects this hardware
for f in artifacts/uefi/CAIHONG_UEFI.fd \
         artifacts/uefi/Mu-caihong-0-Model.img \
         artifacts/uefi-ubuntu/CAIHONG_UEFI.fd \
         artifacts/uefi-ubuntu/Mu-caihong-0-Model.img \
         artifacts/uefi-real/CAIHONG_UEFI.fd \
         artifacts/uefi-real/Mu-caihong-0-Model.img \
         source/Mu-Qcom-musabcel/Build/*/RELEASE_CLANGPDB/FV/*.fd \
         source/Mu-Qcom-musabcel/Build/*/DEBUG_CLANGPDB/FV/*.fd \
         source/Mu-Qcom-musabcel/Build/*/RELEASE_GCC5/FV/*.fd \
         source/Mu-Qcom-musabcel/Build/*/DEBUG_GCC5/FV/*.fd \
         source/Mu-Qcom-musabcel/Mu-*.img; do
	[ -f "$f" ] || continue
	found_fd=1
	size=$(wc -c < "$f" | tr -d ' ')
	case "$f" in
		*.fd)
			# EFI_FIRMWARE_VOLUME_HEADER: '_FVH' signature lives at 0x28
			# and FvLength (u64 LE) at 0x20 must equal the file size.
			sig=$(dd if="$f" bs=1 skip=40 count=4 2>/dev/null)
			flen=$(od -An -tu8 -j32 -N8 "$f" | tr -d ' ')
			if [ "$sig" != "_FVH" ]; then
				say_bad "$(basename "$f"): missing _FVH signature"
			elif [ "$flen" != "$size" ]; then
				say_bad "$(basename "$f"): FvLength $flen != file size $size"
			else
				say_ok "$(basename "$f")  $size bytes  _FVH ok, FvLength matches"
			fi
			;;
		*.img)
			magic=$(dd if="$f" bs=1 count=8 2>/dev/null)
			if [ "$magic" = "ANDROID!" ]; then
				say_ok "$(basename "$f")  $size bytes  Android boot image"
			else
				say_bad "$(basename "$f"): not an Android boot image"
			fi
			;;
		*)
			say_ok "$(basename "$f")  $size bytes"
			;;
	esac
done
if [ "$found_fd" -eq 0 ]; then
	echo "  [SKIP] no firmware image found."
	echo "         Recorded reasons for this checkout (docs/bringup-log.md):"
	echo "           - the build stops in edk2-pytool-extensions' dependency"
	echo "             update because two NuGet packages cannot be fetched:"
	echo "             mu_nasm@20016.1.1 and edk2-basecrypto-driver-bin@1.0.1"
	echo "           - and caihong.dsc additionally refuses to link while"
	echo "             CAIHONG_ABL_ADDRESSES_VERIFIED = 0."
	echo "         A missing .fd here is therefore expected, not a regression."
fi

# --------------------------------------------------------------- PE/COFF ARM64
echo
echo "-- architecture sanity (any *.efi that does exist) --"
for f in $(find build source/Mu-Qcom-musabcel/Build -name '*.efi' -type f 2>/dev/null | head -20); do
	magic=$(dd if="$f" bs=1 count=2 2>/dev/null)
	if [ "$magic" != "MZ" ]; then
		say_bad "$(basename "$f"): not a PE image"
		continue
	fi
	# e_lfanew lives at offset 0x3C (u32 LE); the COFF machine field follows
	# the 4-byte "PE\0\0" signature.  AArch64 is 0xAA64, which reads back as
	# "aa64" when dumped little-endian.
	e_lfanew=$(od -An -tu4 -j60 -N4 "$f" | tr -d ' ')
	if [ -z "$e_lfanew" ]; then say_bad "$(basename "$f"): truncated header"; continue; fi
	machine=$(od -An -tx2 -j$((e_lfanew + 4)) -N2 "$f" | tr -d ' ')
	if [ "$machine" = "aa64" ]; then
		say_ok "$(basename "$f")  PE32+ AArch64"
	else
		say_bad "$(basename "$f"): COFF machine 0x$machine is not AArch64 (0xaa64)"
	fi
done

# ------------------------------------------------------------------- sha256
echo
echo "-- checksums --"
mkdir -p artifacts
if [ "$MODE" = "--check" ]; then
	if [ ! -f artifacts/SHA256SUMS ]; then
		say_bad "artifacts/SHA256SUMS missing"
	else
		if (cd . && sha256sum -c artifacts/SHA256SUMS >/dev/null 2>&1); then
			say_ok "all artifacts match artifacts/SHA256SUMS"
		else
			say_bad "artifacts do not match artifacts/SHA256SUMS"
			sha256sum -c artifacts/SHA256SUMS 2>&1 | grep -v ': OK$' | head -10
		fi
	fi
else
	: > artifacts/SHA256SUMS
	for f in build/acpi/DSDT.aml build/acpi/FACP.aml build/acpi/APIC.aml \
	         build/acpi/GTDT.aml build/acpi/DBG2.aml build/acpi/PPTT.aml \
	         artifacts/uefi/CAIHONG_UEFI.fd \
	         artifacts/uefi/Mu-caihong-0-Model.img \
	         artifacts/uefi/BootShim.bin \
	         artifacts/uefi-ubuntu/CAIHONG_UEFI.fd \
	         artifacts/uefi-ubuntu/Mu-caihong-0-Model.img \
	         artifacts/uefi-real/CAIHONG_UEFI.fd \
	         artifacts/uefi-real/Mu-caihong-0-Model.img \
	         artifacts/uefi-real/BINARIES_INDEX.json; do
		[ -f "$f" ] && sha256sum "$f" >> artifacts/SHA256SUMS
	done
	if [ -s artifacts/SHA256SUMS ]; then
		say_ok "wrote artifacts/SHA256SUMS ($(wc -l < artifacts/SHA256SUMS | tr -d ' ') entries)"
		cat artifacts/SHA256SUMS
	else
		say_bad "nothing to checksum"
	fi
fi

echo
echo "=============================================================="
printf ' %d checks ok\n' "$checked"
if [ "$fail" -ne 0 ]; then
	echo " ARTIFACT VERIFICATION FAILED" >&2
	exit 1
fi
echo " ARTIFACT VERIFICATION PASSED"
exit 0
