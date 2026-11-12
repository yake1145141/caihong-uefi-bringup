#!/usr/bin/env python3
"""
Integrate the caihong ACPI tables into the *working* Mu-Silicium tree, then
enable the ACPI drivers in the platform FDF/DSC.

Local AML tables live in E:\\caihong-windows\\build\\acpi and are uploaded to
/root/data/caihong-acpi on the build host.  The working UEFI tree is
/root/data/caihong-work/uefi.

Reference implementation: pong (enables the same three ACPI components).
"""
import pathlib
import sys

UEFI = pathlib.Path("/root/data/caihong-work/uefi")
SRC = pathlib.Path("/root/data/caihong-acpi")
DEST = UEFI / "Silicium-ACPI/Platforms/OnePlus/caihong"
FDF = UEFI / "Platforms/OnePlus/caihongPkg/caihong.fdf"
DSC = UEFI / "Platforms/OnePlus/caihongPkg/caihong.dsc"

NAMES = ["APIC", "DBG2", "DSDT", "FACP", "GTDT", "PPTT"]


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    for n in NAMES:
        s = SRC / f"{n}.aml"
        if not s.is_file():
            print("ERROR: missing", s)
            return 1
        (DEST / f"{n}.aml").write_bytes(s.read_bytes())
        print("copied", n)

    inf = DEST / "AcpiTables.inf"
    lines = [
        "[Defines]",
        "  INF_VERSION                    = 0x00010005",
        "  BASE_NAME                      = AcpiTables",
        "  FILE_GUID                      = 7E374E25-8E01-4FEE-87F2-390C23C606CE",
        "  MODULE_TYPE                    = USER_DEFINED",
        "  VERSION_STRING                 = 1.0",
        "",
        "[Binaries]",
    ] + [f"  ASL|{n}.aml" for n in NAMES] + [""]
    inf.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", inf)

    # --- FDF: uncomment the three ACPI lines ---
    t = FDF.read_text(encoding="utf-8", errors="surrogateescape")
    t = t.replace(
        "  #INF MdeModulePkg/Universal/Acpi/AcpiTableDxe/AcpiTableDxe.inf",
        "  INF MdeModulePkg/Universal/Acpi/AcpiTableDxe/AcpiTableDxe.inf",
    ).replace(
        "  #INF MdeModulePkg/Universal/Acpi/AcpiPlatformDxe/AcpiPlatformDxe.inf",
        "  INF MdeModulePkg/Universal/Acpi/AcpiPlatformDxe/AcpiPlatformDxe.inf",
    ).replace(
        "  #INF RuleOverride = ACPITABLE caihong/AcpiTables.inf",
        "  INF RuleOverride = ACPITABLE caihong/AcpiTables.inf",
    )
    FDF.write_text(t, encoding="utf-8", errors="surrogateescape")
    print("FDF ACPI enabled:", [l.strip() for l in t.splitlines() if "Acpi" in l or "ACPITABLE" in l][:4])

    # --- DSC: add the component ---
    d = DSC.read_text(encoding="utf-8", errors="surrogateescape")
    d = d.replace("  #caihong/AcpiTables.inf", "  caihong/AcpiTables.inf")
    if "caihong/AcpiTables.inf" not in d:
        print("ERROR: DSC ACPI component line not found")
        return 1
    DSC.write_text(d, encoding="utf-8", errors="surrogateescape")
    print("DSC ACPI component enabled")

    return 0


if __name__ == "__main__":
    sys.exit(main())
