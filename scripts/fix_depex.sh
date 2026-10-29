#!/bin/sh
# Repair a malformed EDK2 DEPEX file.
#
# SPDX-License-Identifier: GPL-2.0-only
#
# WHY
# ---
# Some prebuilt QcomPkg driver packages ship a DEPEX that is not a valid
# dependency expression.  The OnePlus Ace 3 (SM8550) set in Binaries/ contains
# EnvDxe/EnvDxe.depex as exactly two bytes:  06 08
#   0x06 = EFI_DEP_PUSH  -> consumes the next byte (0x08) as its operand
#   0x08 = EFI_DEP_END   -> ...which means the required END opcode is missing
#
# BaseTools' GenFds then cannot produce the .dpx section for that module and
# aborts the whole build with the misleading
#   "error C0DE: Unknown fatal error" / FileNotFoundError: ...SEC1.1.dpx
#
# The minimal *valid* dependency expression is a single END opcode (0x08),
# which means "no dependencies - always dispatch".  For a prebuilt driver that
# is what an empty depex is meant to say.
#
# Usage:
#   sh scripts/fix_depex.sh <file.depex> [...]
set -eu
CDPATH=

[ $# -ge 1 ] || { echo "usage: $0 <file.depex> [...]" >&2; exit 64; }

for f in "$@"; do
	if [ ! -f "$f" ]; then
		echo "skip (missing): $f" >&2
		continue
	fi
	size=$(wc -c < "$f" | tr -d ' ')
	hex=$(od -An -tx1 "$f" | tr -d ' \n')
	# A valid depex must end with the END opcode 0x08 and, for anything
	# longer than one byte, must be a well-formed expression we cannot
	# verify here.  Only the 2-byte "06 08" case is repaired.
	if [ "$size" = "2" ] && [ "$hex" = "0608" ]; then
		printf '\010' > "$f"
		echo "repaired: $f  (0608 -> 08)"
	else
		echo "left as-is: $f  (size=$size hex=$hex)"
	fi
done
