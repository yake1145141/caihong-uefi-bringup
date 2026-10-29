#!/usr/bin/env python3
"""
Extract a machine-readable hardware description of the SM8650 (caihong) from
the device's own firmware device trees.

This is the evidence generator for the whole port: every address that ends up
in uefi/Silicon/Qualcomm/CliffsPkg or in acpi/caihong/*.dsl is supposed to be
traceable to this output.

Input : work/dt/vendor_boot/vendor.dtb      (SoC description, "qcom,cliffs")
        work/dt/dtbo/dtbo_idx07_*.dts       (active board overlay, board-id 8,0)
Output: docs/hw-<soc>-<device>.json + a human summary on stdout

Both inputs are produced by scripts/extract_dtb.py from the stock images in
E:\\1+padpro\\oxygenos.  Nothing here touches the device.

Usage:
  python scripts/extract_hw.py [--dtb work/dt/vendor_boot/vendor.dtb] [--out docs]
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fdtlib import Fdt

# GIC SPI -> ACPI GSIV conversion for a GICv3 with 32 SGIs + 16 PPIs.
GSIV_BASE = 32


def gsiv(interrupts):
    """Decode a <GIC_SPI n flags> triple to (type, spi, gsiv)."""
    if not interrupts or len(interrupts) < 3:
        return None
    itype, num, flags = interrupts[0], interrupts[1], interrupts[2]
    kind = {0: "SPI", 1: "PPI"}.get(itype, "type%d" % itype)
    base = GSIV_BASE if itype == 0 else 16
    return {"kind": kind, "spi": num, "flags": flags, "gsiv": base + num}


def cells_counts(node):
    """Resolve (#address-cells, #size-cells) as seen by `node`.

    Device tree binds these to the *parent* of the node that has `reg`, and
    the SM8650 vendor DTB mixes 2/2 at the root with 1/1 under /soc, so they
    must be resolved per node rather than assumed.
    """
    ac = sc = None
    n = node.parent
    while n is not None:
        if ac is None:
            ac = n.get_u32("#address-cells")
        if sc is None:
            sc = n.get_u32("#size-cells")
        if ac is not None and sc is not None:
            break
        n = n.parent
    return (ac if ac is not None else 2), (sc if sc is not None else 2)


def regs(node):
    r = node.get_cells("reg")
    if not r:
        return []
    ac, sc = cells_counts(node)
    if ac not in (1, 2) or sc not in (1, 2):
        return []
    stride = ac + sc
    if stride == 0 or len(r) % stride:
        return []
    out = []
    for i in range(0, len(r), stride):
        base = 0
        for c in r[i:i + ac]:
            base = (base << 32) | c
        size = 0
        for c in r[i + ac:i + stride]:
            size = (size << 32) | c
        out.append({"base": base, "size": size})
    return out


def find(root, *needles):
    """Find nodes whose name or compatible contains any needle."""
    out = []
    for n in root.walk():
        hay = n.name.lower() + " " + " ".join(n.get_stringlist("compatible") or []).lower()
        if any(x in hay for x in needles):
            out.append(n)
    return out


def describe(n):
    return {
        "node": n.name,
        "path": n.path(),
        "compatible": n.get_stringlist("compatible"),
        "regions": regs(n),
        "interrupt": gsiv(n.get_cells("interrupts")),
        "status": n.get_string("status"),
    }


WANTED = [
    ("gic", ("arm,gic-v3",)),
    ("generic_timer", ("arm,armv8-timer",)),
    ("timer_frame", ("arm,armv7-timer-mem",)),
    ("ufs", ("ufshc", "qcom,ufshc")),
    ("usb_dwc3", ("dwc3", "dwc-usb3-msm")),
    ("pinctrl", ("pinctrl", "tlmm")),
    ("spmi", ("spmi-pmic-arb",)),
    ("debug_uart", ("geni-debug-uart", "qup_uart")),
    ("geni_se", ("geni-se-qup",)),
    ("display_mdp", ("mdss_mdp",)),
    ("dsi", ("mdss_dsi_ctrl", "mdss_dsi_phy")),
    ("gpu", ("kgsl", "adreno")),
    ("i2c", ("geni_i2c",)),
    ("spi", ("geni-spi", "spi_geni")),
    ("qspi", ("qcom,qspi",)),
    ("pcie", ("pcie",)),
    ("rpmh", ("rpmh", "rsc")),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dtb", default=os.path.join("work", "dt", "vendor_boot", "vendor.dtb"))
    ap.add_argument("--out", default="docs")
    ap.add_argument("--soc", default="sm8650")
    ap.add_argument("--device", default="caihong")
    args = ap.parse_args()

    with open(args.dtb, "rb") as f:
        blob = f.read()
    fdt = Fdt(blob)
    root = fdt.root

    hw = {
        "source": {"file": args.dtb, "bytes": len(blob)},
        "soc": {
            "model": root.get_string("model"),
            "compatible": root.get_stringlist("compatible"),
            "msm_id": ["0x%x" % x for x in (root.get_cells("qcom,msm-id") or [])],
            "board_id": ["0x%x" % x for x in (root.get_cells("qcom,board-id") or [])],
        },
        "peripherals": {},
        "cpu": {},
    }

    for key, needles in WANTED:
        nodes = find(root, *needles)
        if nodes:
            hw["peripherals"][key] = [describe(n) for n in nodes if n.name]

    # CPU topology
    cpus = root.child("cpus")
    if cpus is not None:
        hw["cpu"]["count"] = len([c for c in cpus.children if c.name.startswith("cpu@")])
        hw["cpu"]["mpidr_reg"] = [
            [("0x%x" % x) for x in (c.get_cells("reg") or [])]
            for c in cpus.children if c.name.startswith("cpu@")]
        hw["cpu"]["compatible"] = sorted({
            c.get_string("compatible") for c in cpus.children
            if c.name.startswith("cpu@") and c.get_string("compatible")})
    # idle-domain cluster map, which is what the vendor DTB exposes
    for n in root.walk():
        if n.name == "cpu-map" and n.children:
            hw["cpu"]["domain_map"] = {c.name: [k.name for k in c.children]
                                       for c in n.children}

    os.makedirs(args.out, exist_ok=True)
    out = os.path.join(args.out, "hw-%s-%s.json" % (args.soc, args.device))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(hw, f, indent=2, ensure_ascii=False)

    print("== %s / %s ==" % (hw["soc"]["model"], hw["soc"]["compatible"]))
    print("   msm-id %s  board-id %s" % (hw["soc"]["msm_id"], hw["soc"]["board_id"]))
    print("   cpus: %s  clusters: %s" % (hw["cpu"].get("count"),
                                          hw["cpu"].get("domain_map")))
    print()
    for key in sorted(hw["peripherals"]):
        for d in hw["peripherals"][key]:
            r0 = d["regions"][0] if d["regions"] else None
            irq = d["interrupt"]
            print("  %-14s %-34s base=%-12s size=%-9s gsiv=%s" % (
                key, d["node"][:34],
                ("0x%X" % r0["base"]) if r0 else "-",
                ("0x%X" % r0["size"]) if r0 else "-",
                ("0x%X" % irq["gsiv"]) if irq else "-"))
    print()
    print("written: %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
