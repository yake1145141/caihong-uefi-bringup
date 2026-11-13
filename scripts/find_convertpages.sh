#!/bin/sh
# Locate the source of the "ConvertPages: failed to find range" message seen
# when bootmgfw.efi loads, and show its context to judge whether it is fatal.
set -eu
TREE=/root/data/caihong-work/uefi

echo "=== files containing the message ==="
grep -rln 'ConvertPages: failed to find range' "$TREE" 2>/dev/null | head -10 || true

f=$(grep -rl 'ConvertPages: failed to find range' "$TREE" 2>/dev/null | head -1 || true)
if [ -n "$f" ]; then
    echo
    echo "=== context in $f ==="
    grep -n -B18 -A10 'ConvertPages: failed to find range' "$f" | head -40
else
    echo "(string not found in tree; likely emitted by the closed-source Windows loader)"
fi
