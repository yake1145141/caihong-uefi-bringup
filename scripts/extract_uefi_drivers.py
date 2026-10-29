#!/usr/bin/env python3
"""
Extract the UEFI driver modules out of a Qualcomm UEFI image (uefi.img).

Why
---
Mu-Silicium requires a per-device set of prebuilt UEFI drivers
(Binaries/<device>/QcomPkg/Drivers/*).  Those binaries are not published for
SM8650, so the caihong port currently borrows the SM8550 set as a placeholder
(docs/bringup-log.md B12.2), which makes the firmware un-usable on real
hardware.

The device's own `uefi.img` partition *is* a UEFI firmware volume containing
exactly those drivers, so they can be recovered from firmware the user already
owns.  This script does that.

Structure of uefi.img (verified, see docs/bringup-log.md B14)
------------------------------------------------------------
  ELF64 AArch64, e_type=EXEC, e_entry=0xA7000000 (= the ABL UEFI_FD base)
  one EFI firmware volume at file offset 0x1000, FvLength 0x300000
    FFS 0x000048  type 0xF0  padding
    FFS 0x000FE8  type 0x03  DXE core
    FFS 0x050000  type 0x02  driver
    FFS 0x051118  type 0x0B  nested FV, GUIDed section 1d301fe9-... = gzip
    FFS 0x194030  type 0x0B  nested FV, GUIDed section 1d301fe9-... = gzip

The nested volumes are plain gzip streams, so no EDK2 tooling is needed.

Usage:
    python scripts/extract_uefi_drivers.py <uefi.img> <out-dir>
"""

import gzip
import hashlib
import json
import os
import struct
import sys
import uuid

FV_SIGNATURE = b"_FVH"
FS_GUID_FFS3 = uuid.UUID("8c8ce578-8a3d-4f1c-9935-896185c32dd3")

# EFI_FV_FILETYPE_*
FT_RAW = 0x01
FT_FREEFORM = 0x02
FT_DXE_CORE = 0x03
FT_PEIM = 0x04
FT_DRIVER = 0x07 if False else 0x07  # see note below
FT_COMBINED_PEIM_DRIVER = 0x08
FT_APPLICATION = 0x09
FT_FV_IMAGE = 0x0B
FT_PAD = 0xF0
FILE_TYPE_NAMES = {
    0x01: "RAW", 0x02: "FREEFORM", 0x03: "DXE_CORE", 0x04: "PEIM",
    0x05: "DXE_CORE2", 0x06: "PEIM2", 0x07: "DRIVER", 0x08: "COMBINED",
    0x09: "APPLICATION", 0x0A: "MM", 0x0B: "FV_IMAGE", 0x0C: "MM_CORE",
    0xF0: "PAD",
}

# EFI_SECTION_*
SEC_COMPRESSION = 0x01
SEC_GUID_DEFINED = 0x02
SEC_DISPOSABLE = 0x03
SEC_PE32 = 0x10
SEC_PIC = 0x11
SEC_TE = 0x12
SEC_DXE_DEPEX = 0x13
SEC_UI = 0x15
SEC_FV_IMAGE = 0x17
SEC_RAW = 0x19
SEC_USER_INTERFACE = 0x15

# EDK2 gzip guided-section GUID (payload is a plain gzip stream)
GUID_GZIP = uuid.UUID("1d301fe9-be79-4353-91c2-d23bc959ae0c")


def u24(b, off):
    return b[off] | (b[off + 1] << 8) | (b[off + 2] << 16)


def sha(b):
    return hashlib.sha256(b).hexdigest()


# --------------------------------------------------------------------------
# Firmware volume
# --------------------------------------------------------------------------
def iter_ffs(fv):
    """Yield (offset, guid, type, size, raw_file_bytes) for each FFS file."""
    if len(fv) < 0x38 or fv[0x28:0x2c] != FV_SIGNATURE:
        raise ValueError("not a firmware volume")
    fv_len = struct.unpack("<Q", fv[0x20:0x28])[0]
    hdr_len = struct.unpack("<H", fv[0x30:0x32])[0]
    fv = fv[:fv_len] if fv_len <= len(fv) else fv
    pos = hdr_len
    while pos + 24 <= len(fv):
        name = fv[pos:pos + 16]
        ftype = fv[pos + 18]
        size = u24(fv, pos + 20)
        # NOTE: an all-0xFF GUID is *not* an end marker here -- this device's
        # volume starts with an EFI_FV_FILETYPE_PAD file whose name field is
        # 0xFF-filled.  Trust the file size instead, and only give up when the
        # size is impossible.
        if size < 24 or pos + size > len(fv):
            break
        yield pos, uuid.UUID(bytes_le=name), ftype, size, fv[pos:pos + size]
        pos += (size + 7) & ~7


# --------------------------------------------------------------------------
# Sections
# --------------------------------------------------------------------------
def iter_sections(blob, depth=0, out=None):
    """Walk a section stream, yielding (type, payload). Handles nesting."""
    if out is None:
        out = []
    pos = 0
    while pos + 4 <= len(blob):
        size = u24(blob, pos)
        stype = blob[pos + 3]
        if size < 4 or pos + size > len(blob):
            break
        payload = blob[pos + 4:pos + size]
        yield stype, payload
        if stype in (SEC_COMPRESSION, SEC_GUID_DEFINED):
            # Recurse only when the section was already decompressed by the
            # caller; otherwise the payload is opaque here.
            pass
        pos += (size + 3) & ~3
    return out


def decompress_guided(payload):
    """Handle an EFI_SECTION_GUID_DEFINED payload; return inner section stream.

    Only the gzip GUID is supported, which is what this device uses.
    """
    if len(payload) < 20:
        return None, "guid-defined section too small"
    g = uuid.UUID(bytes_le=payload[0:16])
    data_off, attrs = struct.unpack("<HH", payload[16:20])
    if g != GUID_GZIP:
        return None, "unsupported guided GUID %s" % g
    # DataOffset is measured from the START OF THE SECTION HEADER, which
    # includes the 4-byte common section header already stripped from
    # `payload`.  Keeping the raw offset here shifted the gzip stream by 4
    # bytes and made zlib report "not a gzip file".
    skip = data_off - 4
    if skip < 0 or skip > len(payload):
        return None, "bad DataOffset %d" % data_off
    body = payload[skip:]
    try:
        inner = gzip.decompress(body)
    except OSError as exc:
        return None, "gzip failed: %s" % exc
    return inner, None


# --------------------------------------------------------------------------
# Driver identity
# --------------------------------------------------------------------------
def ui_name(sections):
    """Return the module name from its EFI_SECTION_USER_INTERFACE section.

    EDK2 stores the name as a NUL-terminated UCS-2/UTF-16LE string, so decoding
    as UTF-8 yields only the first character (every second byte is 0x00).
    Detect that pattern before falling back to ASCII.
    """
    for stype, payload in sections:
        if stype != SEC_UI:
            continue
        if len(payload) >= 2 and payload[1] == 0x00:
            try:
                s = payload.decode("utf-16-le")
            except UnicodeDecodeError:
                s = payload.decode("utf-8", "replace")
            s = s.split("\x00")[0].strip()
            if s:
                return s
        s = payload.split(b"\x00")[0].decode("utf-8", "replace").strip()
        if s:
            return s
    return None


def pe32(sections):
    for stype, payload in sections:
        if stype == SEC_PE32:
            return payload
    return None


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 64
    img, outdir = sys.argv[1], sys.argv[2]
    with open(img, "rb") as f:
        d = f.read()

    os.makedirs(outdir, exist_ok=True)
    report = {"image": os.path.basename(img), "bytes": len(d),
              "sha256": sha(d), "volumes": [], "drivers": []}

    # ---- locate every FV in the image (ELF-stripped, so scan) -------------
    fv_offsets = []
    i = 0
    while True:
        i = d.find(FV_SIGNATURE, i)
        if i < 0:
            break
        off = i - 0x28
        if off >= 0:
            fv_offsets.append(off)
        i += 1
    print("firmware volumes found: %d" % len(fv_offsets))

    queue = [(off, 0) for off in fv_offsets]
    seen = set()
    while queue:
        off, level = queue.pop(0)
        if off in seen:
            continue
        seen.add(off)
        fv = d[off:]
        if len(fv) < 0x38 or fv[0x28:0x2c] != FV_SIGNATURE:
            continue
        fv_len = struct.unpack("<Q", fv[0x20:0x28])[0]
        fs_guid = uuid.UUID(bytes_le=fv[0x10:0x20])
        print("\n== FV @0x%X level=%d len=0x%X fs=%s"
              % (off, level, fv_len, fs_guid))
        report["volumes"].append({"offset": off, "level": level,
                                  "length": fv_len, "fs_guid": str(fs_guid)})
        for fpos, fguid, ftype, fsize, fraw in iter_ffs(fv):
            tname = FILE_TYPE_NAMES.get(ftype, "0x%02X" % ftype)
            if ftype == FT_PAD:
                continue
            body = fraw[24:]
            secs = list(iter_sections(body))

            # nested volume inside a guided/compressed section?
            nested = None
            for stype, payload in secs:
                if stype == SEC_GUID_DEFINED:
                    inner, err = decompress_guided(payload)
                    if inner:
                        nested = inner
                        break
            if nested is not None:
                print("   FFS @0x%06X %-10s size=0x%-7X -> nested %d bytes"
                      % (fpos, tname, fsize, len(nested)))
                np_ = os.path.join(outdir, "nested_%08X.fv" % (off + fpos))
                with open(np_, "wb") as f:
                    f.write(nested)
                # The decompressed blob is itself a *section stream*
                # (typically an empty RAW section followed by an FV_IMAGE
                # section), so the firmware volume does not start at offset 0.
                # Splice the blob in and scan it for volume headers rather
                # than assuming a layout.
                base_off = len(d)
                d = d + nested
                j = 0
                while True:
                    j = d.find(FV_SIGNATURE, base_off + j)
                    if j < 0:
                        break
                    cand = j - 0x28
                    if cand >= base_off:
                        queue.append((cand, level + 1))
                    j += 1
                continue

            img_sec = pe32(secs)
            name = ui_name(secs) or str(fguid)
            if img_sec:
                safe = "".join(c if (c.isalnum() or c in "-_. ") else "_"
                               for c in name) or str(fguid)
                sub = os.path.join(outdir, safe)
                os.makedirs(sub, exist_ok=True)
                path = os.path.join(sub, safe + ".efi")
                with open(path, "wb") as f:
                    f.write(img_sec)
                depex = None
                for stype, payload in secs:
                    if stype == SEC_DXE_DEPEX:
                        depex = payload
                        break
                if depex:
                    with open(os.path.join(sub, safe + ".depex"), "wb") as f:
                        f.write(depex)
                report["drivers"].append({
                    "name": name, "file_type": tname, "guid": str(fguid),
                    "pe32_bytes": len(img_sec), "pe32_sha256": sha(img_sec),
                    "depex_bytes": len(depex) if depex else 0,
                    "efi": os.path.relpath(path, outdir),
                })
                print("   FFS @0x%06X %-10s %-28s PE32 %d bytes"
                      % (fpos, tname, name[:28], len(img_sec)))
            else:
                print("   FFS @0x%06X %-10s size=0x%-7X (no PE32: %s)"
                      % (fpos, tname, fsize,
                         ",".join("0x%02X" % s for s, _ in secs)))

    with open(os.path.join(outdir, "extract-report.json"), "w",
              encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print("\ndrivers with PE32 extracted: %d" % len(report["drivers"]))
    print("report: %s" % os.path.join(outdir, "extract-report.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
