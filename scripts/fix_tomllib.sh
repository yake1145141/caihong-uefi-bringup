#!/bin/sh
# Make the reference build run on Python 3.10: its build_uefi.py imports
# tomllib (3.11+), so provide a shim backed by the tomli backport.
set -eu

V=/root/data/caihong-work/.venv
"$V/bin/pip" install --quiet tomli

SP=$("$V/bin/python" -c 'import site; print(site.getsitepackages()[0])')
printf 'from tomli import load, loads, TOMLDecodeError\n' > "$SP/tomllib.py"

"$V/bin/python" - <<'EOF'
import tomllib
print("tomllib shim ok:", tomllib.__file__)
EOF
