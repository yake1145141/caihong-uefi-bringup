#!/usr/bin/env python3
"""
Extract every device tree blob we can obtain from the provided caihong firmware
images, and dump each one to .dts text for auditing.

Sources (all read-only; nothing on the device is touched):
  images/dtbo.img        -> overlay DTBs (dtbo_idx 7 is the active one per getprop)
  images/vendor_boot.img -> vendor DTB (base SoC + board description)
  images/boot.img        -> kernel + generic ramdisk (for version identification)

Outputs under work/dt/<image>/ .

Usage:
  python scripts/extract_dtb.py [--src E:\\1+padpro\\oxygenos] [--out work\\dt]
"""

import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fdtlib import (Fdt, FdtError, parse_dtbo_partition, parse_vendor_boot,
                    parse_boot_v4)


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def dump(buf, path):
    try:
        fdt = Fdt(buf)
    except FdtError as e:
        with open(path + ".error.txt", "w", encoding="utf-8") as f:
            f.write("FDT parse failed: %s\n" % e)
        return None, str(e)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(fdt.to_dts())
    return fdt, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=r"E:\1+padpro\oxygenos")
    ap.add_argument("--out", default=r"work\dt")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    report = {"src": args.src, "images": {}, "dtbs": []}

    def load(name):
        p = os.path.join(args.src, name)
        if not os.path.isfile(p):
            return None, p
        with open(p, "rb") as f:
            return f.read(), p

    # ---------------------------------------------------------------- dtbo
    dtbo, dtbo_path = load("dtbo.img")
    if dtbo:
        outdir = os.path.join(args.out, "dtbo")
        os.makedirs(outdir, exist_ok=True)
        report["images"]["dtbo.img"] = {
            "path": dtbo_path, "size": len(dtbo), "sha256": sha256(dtbo)}
        try:
            entries = parse_dtbo_partition(dtbo)
        except FdtError as e:
            entries = []
            report["images"]["dtbo.img"]["error"] = str(e)
        report["images"]["dtbo.img"]["entry_count"] = len(entries)
        for idx, e in enumerate(entries):
            # NOTE: OPPO/QCOM build all entries with dt_id=0/dt_rev=0; the
            # selector used by ABL is the table *index* (ro.boot.dtbo_idx).
            base = os.path.join(outdir, "dtbo_idx%02d_id%d_rev%d" % (idx, e.id, e.rev))
            fdt, err = dump(e.data, base + ".dts")
            rec = {"source": "dtbo.img", "index": idx, "id": e.id, "rev": e.rev,
                   "size": len(e.data), "sha256": sha256(e.data),
                   "dts": os.path.relpath(base + ".dts", args.out) if fdt else None,
                   "error": err}
            if fdt is not None:
                rec["model"] = fdt.root.get_string("model")
                rec["compatible"] = fdt.root.get_stringlist("compatible")
                # overlays: list fragment target paths
                frags = []
                for n in fdt.root.children:
                    if n.name.startswith("fragment"):
                        tp = n.get_string("target-path")
                        if tp is None:
                            tgt = n.get_cells("target")
                            tp = "phandle:0x%x" % tgt[0] if tgt else "<unknown>"
                        frags.append(tp)
                rec["fragments"] = frags
            report["dtbs"].append(rec)

    # --------------------------------------------------------- vendor_boot
    vb, vb_path = load("vendor_boot.img")
    if vb:
        outdir = os.path.join(args.out, "vendor_boot")
        os.makedirs(outdir, exist_ok=True)
        report["images"]["vendor_boot.img"] = {
            "path": vb_path, "size": len(vb), "sha256": sha256(vb)}
        try:
            info = parse_vendor_boot(vb)
            meta = {k: v for k, v in info.items() if k not in ("dtb", "ramdisks", "bootconfig")}
            report["images"]["vendor_boot.img"]["header"] = meta
            report["images"]["vendor_boot.img"]["ramdisk_count"] = len(info["ramdisks"])
            if info.get("bootconfig"):
                with open(os.path.join(outdir, "bootconfig.txt"), "wb") as f:
                    f.write(info["bootconfig"])
            for i, rd in enumerate(info["ramdisks"]):
                with open(os.path.join(outdir, "ramdisk_%02d.img" % i), "wb") as f:
                    f.write(rd["data"])
            if info.get("dtb"):
                dtb = info["dtb"]
                report["images"]["vendor_boot.img"]["dtb_size"] = len(dtb)
                fdt, err = dump(dtb, os.path.join(outdir, "vendor.dts"))
                rec = {"source": "vendor_boot.img", "size": len(dtb),
                       "sha256": sha256(dtb), "dts": "vendor_boot/vendor.dts" if fdt else None,
                       "error": err}
                if fdt is not None:
                    rec["model"] = fdt.root.get_string("model")
                    rec["compatible"] = fdt.root.get_stringlist("compatible")
                report["dtbs"].append(rec)
                with open(os.path.join(outdir, "vendor.dtb"), "wb") as f:
                    f.write(dtb)
        except FdtError as e:
            report["images"]["vendor_boot.img"]["error"] = str(e)

    # ---------------------------------------------------------------- boot
    boot, boot_path = load("boot.img")
    if boot:
        report["images"]["boot.img"] = {"path": boot_path, "size": len(boot),
                                        "sha256": sha256(boot)}
        try:
            bi = parse_boot_v4(boot)
            report["images"]["boot.img"]["header"] = {
                k: v for k, v in bi.items() if k not in ("kernel", "ramdisk")}
            outdir = os.path.join(args.out, "boot")
            os.makedirs(outdir, exist_ok=True)
            if bi.get("kernel"):
                with open(os.path.join(outdir, "kernel"), "wb") as f:
                    f.write(bi["kernel"])
        except FdtError as e:
            report["images"]["boot.img"]["error"] = str(e)

    with open(os.path.join(args.out, "extract-report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # human summary
    print("== extracted DTB inventory ==")
    for r in report["dtbs"]:
        print("  %-28s id=%-3s size=%-7d model=%s" %
              (r["source"], r.get("id", "-"), r["size"], r.get("model")))
    print("report: %s" % os.path.join(args.out, "extract-report.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
