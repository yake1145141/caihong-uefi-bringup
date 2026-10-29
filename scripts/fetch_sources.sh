#!/bin/sh
# Fetch the upstream sources the caihong port depends on.
#
# SPDX-License-Identifier: GPL-2.0-only
#
# Idempotent and non-destructive: existing checkouts are left alone unless
# --force is given, and nothing is ever deleted without an explicit request.
#
# Usage:
#   sh scripts/fetch_sources.sh            # fetch what is missing
#   sh scripts/fetch_sources.sh --force    # re-clone everything
#
# Notes
#   * All repositories are shallow (--depth 1) because this project only needs
#     a working tree plus the resolved commit id, which fetch_sources records
#     into source/<name>.commit.
#   * The kernel is cloned with a blob filter and a sparse checkout limited to
#     arch/arm64/boot/dts/qcom, which is the only part this port consumes.
#   * Set GIT_TERMINAL_PROMPT=0 so a missing credential fails instead of
#     hanging.
set -u
CDPATH=
GIT_TERMINAL_PROMPT=0
export GIT_TERMINAL_PROMPT

FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

root=$(cd -- "$(dirname -- "$0")/.." && pwd)
mkdir -p "$root/source" || exit 1
cd "$root/source" || exit 1

fail=0

clone() {
	name=$1; url=$2; shift 2
	if [ -d "$name/.git" ]; then
		if [ "$FORCE" -eq 1 ]; then
			echo "== $name: --force, removing and re-cloning"
			rm -rf -- "$name" || { fail=1; return; }
		else
			echo "== $name: already present, left untouched"
			git -C "$name" rev-parse HEAD 2>/dev/null > "$name.commit" || true
			return
		fi
	fi
	echo "== cloning $name from $url"
	if git clone "$@" "$url" "$name"; then
		git -C "$name" rev-parse HEAD > "$name.commit" 2>/dev/null || true
		echo "   recorded commit: $(cat "$name.commit" 2>/dev/null)"
	else
		echo "!! clone failed: $name" >&2
		fail=1
	fi
}

# 1) Mu-Qcom fork that actually has the newest SoC packages (SM8750/SM8550).
#    This is the base the caihong board package is written against.
clone Mu-Qcom-musabcel \
	https://github.com/musabcel/Mu-Qcom.git \
	--depth 1 --recurse-submodules --shallow-submodules

# 2) The other widely referenced fork.  Kept for source comparison only; it
#    tops out at SM8450 and is NOT used as a build base.
clone Mu-Qcom-liliumbeta \
	https://github.com/liliumbeta/Mu-Qcom.git \
	--depth 1 --recurse-submodules --shallow-submodules

# 3) The device's Linux project: build scripts + pinned dependency manifest.
#    Contains no kernel source itself (see config/dependencies.env).
clone caihong-linux-rootfs \
	https://github.com/Osilvfe/caihong-linux-rootfs.git \
	--depth 1

# 4) The actual kernel fork used by that project (Linux 6.x + caihong DTS).
#    Sparse: only the Qualcomm device trees.
if [ ! -d linux-caihong/.git ]; then
	echo "== cloning linux-caihong (sparse: arch/arm64/boot/dts/qcom)"
	if git clone --filter=blob:none --sparse --depth 1 \
		-b caihong-v7.3 https://github.com/Osilvfe/linux.git linux-caihong; then
		(cd linux-caihong && git sparse-checkout set arch/arm64/boot/dts/qcom) \
			|| echo "   warning: sparse-checkout failed; run it manually" >&2
		git -C linux-caihong rev-parse HEAD > linux-caihong.commit 2>/dev/null || true
	else
		echo "!! clone failed: linux-caihong" >&2
		fail=1
	fi
elif [ "$FORCE" -eq 1 ]; then
	rm -rf -- linux-caihong
	exec sh "$0" "$@"
else
	echo "== linux-caihong: already present, left untouched"
fi

# 5) The Windows BSP repository named in the project brief.  It is kept ONLY so
#    the absence of SM8650 support can be audited reproducibly -- it contains
#    documentation and no driver code at all.
clone windows_silicon_qcom_lanai \
	https://github.com/WOA-Project/windows_silicon_qcom_lanai.git \
	--depth 1

echo
echo "-- resolved commits --"
for f in *.commit; do
	[ -f "$f" ] || continue
	printf '  %-34s %s\n' "${f%.commit}" "$(cat "$f")"
done

echo
if [ "$fail" -ne 0 ]; then
	echo "Some sources failed to fetch; see the messages above." >&2
	exit 1
fi
echo "All sources present."
exit 0
