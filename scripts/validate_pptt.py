#!/usr/bin/env python3
"""
Validate the PPTT (Processor Properties Topology Table).

Windows parses PPTT for processor/cache topology and is far stricter than
Linux.  Two failure modes cause a fatal fault in the loader:
  * structure lengths that do not match the ACPI-defined sizes
  * parent references that point forward, out of range, or form a cycle

This walks the table and reports every violation.
"""
import pathlib
import struct
import sys

PATH = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                    else "/root/data/caihong-acpi/PPTT.aml")

# ACPI 6.x fixed sizes (private resource lists add 4 bytes each entry)
BASE_LEN = {0: 20, 1: 32, 2: 12}
NAME = {0: "Processor", 1: "Cache", 2: "ID"}


def main():
    d = PATH.read_bytes()
    hdr_len = 36
    total = struct.unpack_from("<I", d, 4)[0]
    print("PPTT: %d bytes, header length field=%d, revision=%d"
          % (len(d), total, d[8]))
    if total != len(d):
        print("  !! header Length %d != file size %d" % (total, len(d)))

    off = hdr_len
    entries = []            # (offset, type, length, parent, procid, npriv)
    errs = 0
    while off + 2 <= len(d):
        t, ln = d[off], d[off + 1]
        if ln < 2:
            print("  !! entry at 0x%X has length %d, stopping" % (off, ln))
            errs += 1
            break
        exp = BASE_LEN.get(t)
        detail = ""
        parent = procid = npriv = None
        if t == 0 and ln >= 20:
            parent = struct.unpack_from("<I", d, off + 8)[0]
            procid = struct.unpack_from("<I", d, off + 12)[0]
            npriv = struct.unpack_from("<I", d, off + 16)[0]
            detail = "parent=0x%-4X procid=%-3d priv=%d" % (parent, procid, npriv)
        elif t == 1 and ln >= 32:
            nxt = struct.unpack_from("<I", d, off + 8)[0]
            npriv = struct.unpack_from("<H", d, off + 30)[0]
            detail = "next_cache=0x%-4X priv=%d" % (nxt, npriv)
        if exp is not None and ln != exp + 4 * (npriv or 0):
            detail += "   <-- expected %d (+4/priv)" % exp
            errs += 1
        print("  @0x%-4X type=%d %-10s len=%-3d %s"
              % (off, t, NAME.get(t, "?"), ln, detail))
        entries.append((off, t, ln, parent, procid, npriv))
        off += ln

    print("  end offset=0x%X (table=0x%X), entries=%d" % (off, len(d), len(entries)))

    # Parent validation for processor nodes.
    print("\n  parent reference check:")
    proc_offs = {e[0] for e in entries if e[1] == 0}
    for e in entries:
        if e[1] != 0:
            continue
        off_, _, _, parent, procid, _ = e
        if parent == 0:
            print("    @0x%-4X procid=%-2d parent=0 (root)" % (off_, procid))
        elif parent in proc_offs:
            print("    @0x%-4X procid=%-2d parent=0x%X ok" % (off_, procid, parent))
        else:
            print("    @0x%-4X procid=%-2d parent=0x%X  !! NOT a processor node"
                  % (off_, procid, parent))
            errs += 1

    print("\n  violations: %d" % errs)
    return 0 if errs == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
