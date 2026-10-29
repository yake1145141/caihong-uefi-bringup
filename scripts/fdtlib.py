#!/usr/bin/env python3
"""
Minimal, dependency-free Flattened Device Tree (FDT / DTB) parser and DTS dumper.

Why hand-rolled: the target build host is Windows with CPython 3.12, where the
`libfdt` bindings are painful to build. The FDT binary format is simple and
stable; parsing it directly removes an external dependency from the pipeline.

Supports:
  * standard FDT blob parsing (any version >= 3)
  * printing a .dts-like textual representation
  * cell decoding helpers (/memreserve/, <...>, [..], strings)

Reference: devicetree.org "Devicetree Specification v0.4", chapter 5 (Flattened
Device Tree format).
"""

import struct

FDT_MAGIC = 0xD00DFEED
FDT_BEGIN_NODE = 0x1
FDT_END_NODE = 0x2
FDT_PROP = 0x3
FDT_NOP = 0x4
FDT_END = 0x9


class FdtError(Exception):
    pass


class Node:
    __slots__ = ("name", "props", "children", "parent")

    def __init__(self, name, parent=None):
        self.name = name
        self.props = {}          # name -> raw bytes
        self.children = []       # list[Node]
        self.parent = parent

    # -- convenience ------------------------------------------------------
    def path(self):
        parts = []
        n = self
        while n is not None and n.parent is not None:
            parts.append(n.name)
            n = n.parent
        return "/" + "/".join(reversed(parts))

    def get_cells(self, name):
        raw = self.props.get(name)
        if raw is None:
            return None
        if len(raw) % 4:
            raise FdtError("property %s of %s is not 32-bit aligned" % (name, self.path()))
        return list(struct.unpack(">%dI" % (len(raw) // 4), raw))

    def get_u32(self, name, default=None):
        c = self.get_cells(name)
        if not c:
            return default
        return c[0]

    def get_string(self, name):
        raw = self.props.get(name)
        if raw is None:
            return None
        return raw.split(b"\x00")[0].decode("utf-8", "replace")

    def get_stringlist(self, name):
        raw = self.props.get(name)
        if raw is None:
            return None
        return [s.decode("utf-8", "replace") for s in raw.split(b"\x00") if s]

    def child(self, name):
        for c in self.children:
            if c.name == name:
                return c
        return None

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def find_compatible(self, *compat):
        """Yield nodes whose compatible stringlist contains any of `compat`."""
        out = []
        for n in self.walk():
            cl = n.get_stringlist("compatible") or []
            if any(c in cl for c in compat):
                out.append(n)
        return out

    def __repr__(self):
        return "<Node %s props=%d children=%d>" % (self.path(), len(self.props), len(self.children))


class Fdt:
    def __init__(self, blob):
        if len(blob) < 40:
            raise FdtError("blob too small (%d bytes)" % len(blob))
        (magic, totalsize, off_struct, off_strings, off_rsvmap,
         version, last_comp, boot_cpuid, size_strings, size_struct) = struct.unpack(">10I", blob[:40])
        if magic != FDT_MAGIC:
            raise FdtError("bad FDT magic 0x%08x (expected 0x%08x)" % (magic, FDT_MAGIC))
        if totalsize > len(blob):
            raise FdtError("header totalsize %d exceeds buffer %d" % (totalsize, len(blob)))
        self.blob = blob[:totalsize]
        self.version = version
        self.boot_cpuid_phys = boot_cpuid
        self.memreserve = self._parse_memreserve(off_rsvmap)
        self.root = self._parse_struct(off_struct, off_strings)

    # -- internals --------------------------------------------------------
    def _parse_memreserve(self, off):
        out = []
        pos = off
        while pos + 16 <= len(self.blob):
            addr, size = struct.unpack(">QQ", self.blob[pos:pos + 16])
            if addr == 0 and size == 0:
                break
            out.append((addr, size))
            pos += 16
        return out

    def _parse_struct(self, off_struct, off_strings):
        blob = self.blob
        pos = off_struct
        stack = []
        root = None

        def cstr(pos):
            end = blob.find(b"\x00", pos)
            if end < 0:
                raise FdtError("unterminated string in struct block @%d" % pos)
            return blob[pos:end].decode("utf-8", "replace"), end + 1

        while True:
            if pos + 4 > len(blob):
                raise FdtError("struct block truncated (no FDT_END)")
            (tok,) = struct.unpack(">I", blob[pos:pos + 4])
            pos += 4
            if tok == FDT_BEGIN_NODE:
                name, pos = cstr(pos)
                pos = (pos + 3) & ~3
                node = Node(name, stack[-1] if stack else None)
                if stack:
                    stack[-1].children.append(node)
                elif root is None:
                    root = node
                stack.append(node)
            elif tok == FDT_END_NODE:
                if not stack:
                    raise FdtError("unbalanced FDT_END_NODE")
                stack.pop()
            elif tok == FDT_PROP:
                if len(stack) == 0:
                    raise FdtError("FDT_PROP outside any node")
                ln, nameoff = struct.unpack(">II", blob[pos:pos + 8])
                pos += 8
                val = blob[pos:pos + ln]
                if len(val) != ln:
                    raise FdtError("property value truncated")
                pos = (pos + ln + 3) & ~3
                pname, _ = cstr(off_strings + nameoff)
                stack[-1].props[pname] = bytes(val)
            elif tok == FDT_NOP:
                continue
            elif tok == FDT_END:
                break
            else:
                raise FdtError("unknown FDT token 0x%x @%d" % (tok, pos - 4))
        if root is None:
            raise FdtError("no root node found")
        return root

    # -- dumping ----------------------------------------------------------
    def to_dts(self, include_memreserve=True):
        lines = ["/dts-v1/;", ""]
        if include_memreserve:
            for addr, size in self.memreserve:
                lines.append("/memreserve/ 0x%016x 0x%016x;" % (addr, size))
            if self.memreserve:
                lines.append("")
        self._dump_node(self.root, lines, 0)
        return "\n".join(lines) + "\n"

    def _dump_node(self, node, lines, depth):
        ind = "\t" * depth
        if depth == 0:
            lines.append("/ {")
        else:
            label = node.name if node.name else ""
            lines.append("%s%s {" % (ind, label))
        for k, v in node.props.items():
            lines.append("%s\t%s = %s;" % (ind, k, _format_value(v)))
        if node.props and node.children:
            lines.append("")
        for c in node.children:
            self._dump_node(c, lines, depth + 1)
        lines.append("%s};%s" % (ind, "" if depth else ""))


def _format_value(v):
    if len(v) == 0:
        return "true"
    # Heuristic: a genuine string / stringlist ends with NUL and has no empty
    # interior segment.  This is required to avoid mis-rendering 32-bit cell
    # arrays such as <0 0> (bytes 00 00 00 00) or <0 0x2400> as "" lists.
    if v.endswith(b"\x00"):
        segs = v.split(b"\x00")[:-1]
        if segs and all(len(s) > 0 for s in segs):
            try:
                parts = [s.decode("utf-8") for s in segs]
            except UnicodeDecodeError:
                parts = None
            if parts is not None and all(
                    all(32 <= ord(ch) < 127 for ch in p) for p in parts):
                if len(parts) == 1:
                    return '"%s"' % parts[0]
                return ", ".join('"%s"' % p for p in parts)
    # 32-bit cell list
    if len(v) % 4 == 0 and len(v) <= 256:
        cells = struct.unpack(">%dI" % (len(v) // 4), v)
        return "<%s>" % " ".join("0x%x" % c if c > 9 else "%d" % c for c in cells)
    return "[%s]" % " ".join("%02x" % b for b in v)


# ---------------------------------------------------------------------------
# Android DTBO (device tree overlay) container
# ---------------------------------------------------------------------------
DTBO_MAGIC = 0xD7B7AB1E


class DtboEntry:
    __slots__ = ("size", "offset", "id", "rev", "data")

    def __init__(self, size, offset, dt_id, rev, data):
        self.size = size
        self.offset = offset
        self.id = dt_id
        self.rev = rev
        self.data = data

    def __repr__(self):
        return "<DtboEntry id=%d rev=%d size=%d off=0x%x>" % (self.id, self.rev, self.size, self.offset)


def parse_dtbo_partition(blob, page_size=2048):
    """Parse an Android `dtbo` partition image.

    Layout: one or more concatenated DTBO blobs, each padded to `page_size`.
    Header is big-endian:
        magic, total_size, header_size, dt_entry_size,
        dt_entry_count, dt_entries_offset, page_size, version
    Entry (big-endian):
        dt_size, dt_offset, dt_id, dt_rev
    """
    entries = []
    pos = 0
    blob_index = 0
    while pos + 32 <= len(blob):
        (magic,) = struct.unpack(">I", blob[pos:pos + 4])
        if magic != DTBO_MAGIC:
            # tail padding or end of useful data
            break
        (magic, total_size, header_size, dt_entry_size,
         dt_entry_count, dt_entries_offset, hdr_page_size, version) = struct.unpack(
            ">8I", blob[pos:pos + 32])
        if total_size == 0 or pos + total_size > len(blob):
            raise FdtError("DTBO blob #%d has bad total_size %d (have %d)" %
                           (blob_index, total_size, len(blob) - pos))
        ent_off = pos + dt_entries_offset
        for i in range(dt_entry_count):
            eo = ent_off + i * dt_entry_size
            if eo + 16 > pos + total_size:
                raise FdtError("DTBO entry %d out of bounds" % i)
            dt_size, dt_offset, dt_id, dt_rev = struct.unpack(">4I", blob[eo:eo + 16])
            start = pos + dt_offset
            if start + dt_size > len(blob):
                raise FdtError("DTBO entry %d payload out of bounds" % i)
            entries.append(DtboEntry(dt_size, start, dt_id, dt_rev, bytes(blob[start:start + dt_size])))
        step = total_size if total_size else hdr_page_size
        step = (step + hdr_page_size - 1) // hdr_page_size * hdr_page_size
        pos += step
        blob_index += 1
    return entries


# ---------------------------------------------------------------------------
# Android boot image (v3/v4) - vendor_boot carries the DTB
# ---------------------------------------------------------------------------
ANDROID_MAGIC = b"ANDROID!"
VENDOR_BOOT_MAGIC = b"VNDRBOOT"


def parse_android_boot_image(blob):
    """Parse Android boot/vendor_boot image (header v3/v4).

    Boot image header v3/v4 layout (all little-endian):
      magic[8], kernel_size, ramdisk_size, os_version, header_size,
      reserved[4], header_version, cmdline[1536]
      -> v4 appends: signature_size
    Vendor boot header v3/v4 (little-endian):
      magic[8], header_version, page_size, kernel_addr, ramdisk_addr,
      vendor_ramdisk_size, cmdline[2048], tags_addr, name[16],
      header_size, dtb_size, dtb_addr
      -> v4 appends: vendor_ramdisk_table_size, vendor_ramdisk_table_entry_num,
                     vendor_ramdisk_table_entry_size, bootconfig_size
    """
    if len(blob) < 64 or blob[:8] != ANDROID_MAGIC:
        raise FdtError("not an Android boot image (magic=%r)" % blob[:8])
    (header_version,) = struct.unpack("<I", blob[40:44])  # offset differs per image type; caller checks
    return header_version


def parse_vendor_boot(blob):
    """Parse vendor_boot.img v3/v4. Returns dict with cmdline/dtb/ramdisks."""
    if len(blob) < 8 or blob[:8] != VENDOR_BOOT_MAGIC:
        raise FdtError("not an Android vendor_boot image (magic=%r)" % blob[:8])
    (header_version,) = struct.unpack("<I", blob[8:12])
    (page_size,) = struct.unpack("<I", blob[12:16])
    if header_version not in (3, 4):
        raise FdtError("unsupported vendor_boot header version %d" % header_version)
    if page_size == 0 or page_size & (page_size - 1):
        raise FdtError("implausible page_size %d" % page_size)

    base = 0
    # vendor boot header v3/v4 fixed part is 2112 bytes:
    #   magic[8] 8 | header_version 8 | page_size 12 | kernel_addr 16
    #   ramdisk_addr 20 | vendor_ramdisk_size 24 | cmdline[2048] 28
    #   tags_addr 2076 | name[16] 2080 | header_size 2096 | dtb_size 2100
    #   dtb_addr (u64!) 2104  -> v4 fields start at 2112
    (kernel_addr, ramdisk_addr, vendor_ramdisk_size) = struct.unpack("<3I", blob[16:28])
    cmdline = blob[28:28 + 2048].split(b"\x00")[0].decode("utf-8", "replace")
    (tags_addr,) = struct.unpack("<I", blob[2076:2080])
    name = blob[2080:2096].split(b"\x00")[0].decode("utf-8", "replace")
    (vheader_size,) = struct.unpack("<I", blob[2096:2100])
    (dtb_size,) = struct.unpack("<I", blob[2100:2104])
    (dtb_addr,) = struct.unpack("<Q", blob[2104:2112])

    out = {
        "header_version": header_version,
        "page_size": page_size,
        "cmdline": cmdline,
        "name": name,
        "vendor_ramdisk_size": vendor_ramdisk_size,
        "dtb_size": dtb_size,
        "dtb_addr": dtb_addr,
        "dtb": None,
        "ramdisks": [],
        "bootconfig": None,
    }

    def page_align(x):
        return (x + page_size - 1) // page_size * page_size

    hdr_end = page_align(vheader_size)
    rd_start = hdr_end
    rd_end = rd_start + page_align(vendor_ramdisk_size)
    dtb_start = rd_end
    dtb_end = dtb_start + page_align(dtb_size)
    if dtb_size and dtb_end <= len(blob):
        out["dtb"] = bytes(blob[dtb_start:dtb_start + dtb_size])

    if header_version == 4 and vheader_size >= 2128:
        (tab_size, tab_num, tab_entsize, bootconfig_size) = struct.unpack("<4I", blob[2112:2128])
        out["vendor_ramdisk_table"] = {"size": tab_size, "num": tab_num, "entry_size": tab_entsize}
        tab_start = dtb_end
        for i in range(tab_num):
            eo = tab_start + i * tab_entsize
            if eo + tab_entsize > len(blob) or i > 64:
                break
            # vendor_ramdisk_table_entry_v4 is 108 bytes:
            #   ramdisk_size, ramdisk_offset, ramdisk_type, ramdisk_name[32],
            #   board_id[16]
            (size, offset, vtype_) = struct.unpack("<3I", blob[eo:eo + 12])
            rd_name = blob[eo + 12:eo + 44].split(b"\x00")[0].decode("utf-8", "replace")
            board_id = list(struct.unpack("<16I", blob[eo + 44:eo + 108]))
            out["ramdisks"].append({
                "size": size, "offset": offset, "type": vtype_,
                "name": rd_name, "board_id": board_id,
                "data": bytes(blob[rd_start + offset: rd_start + offset + size]),
            })
        bc_start = tab_start + page_align(tab_size)
        if bootconfig_size and bc_start + bootconfig_size <= len(blob):
            out["bootconfig"] = bytes(blob[bc_start:bc_start + bootconfig_size])
    return out


def parse_boot_v4(blob):
    """Parse boot.img header v4 (kernel + generic ramdisk)."""
    if len(blob) < 8 or blob[:8] != ANDROID_MAGIC:
        raise FdtError("not an Android boot image")
    (kernel_size, ramdisk_size, os_version, header_size) = struct.unpack("<4I", blob[8:24])
    (header_version,) = struct.unpack("<I", blob[40:44])
    cmdline = blob[44:44 + 1536].split(b"\x00")[0].decode("utf-8", "replace")
    out = {"header_version": header_version, "kernel_size": kernel_size,
           "ramdisk_size": ramdisk_size, "cmdline": cmdline}
    if header_version == 4:
        (sig_size,) = struct.unpack("<I", blob[1580:1584])
        out["signature_size"] = sig_size
    if page_size_ok := (header_version >= 3):
        ps = 4096
        k_start = (header_size + ps - 1) // ps * ps
        out["kernel"] = bytes(blob[k_start:k_start + kernel_size])
        r_start = k_start + (kernel_size + ps - 1) // ps * ps
        out["ramdisk"] = bytes(blob[r_start:r_start + ramdisk_size])
    return out


if __name__ == "__main__":
    import sys
    with open(sys.argv[1], "rb") as f:
        data = f.read()
    fdt = Fdt(data)
    print(fdt.to_dts())
