/*
 * fbtest.S -- minimal AArch64 "kernel" used purely as a bring-up probe.
 *
 * SPDX-License-Identifier: GPL-2.0-only
 *
 * WHAT IT DOES
 *   Fills the Qualcomm ABL "Display Reserved" region with a solid colour and
 *   then spins forever.  Nothing else: no UEFI, no BootShim, no stack setup.
 *
 * WHY
 *   After fixing the two loader problems (vbmeta verification flags and the
 *   boot image header version) the device stopped falling back to fastboot but
 *   still showed only the bootloader's first screen -- no UEFI output, no USB
 *   enumeration.  That state is ambiguous: it looks identical whether the
 *   bootloader never jumped to our code, or jumped and the payload faulted
 *   immediately.
 *
 *   This probe resolves the ambiguity with one observation of the panel:
 *     screen turns green  -> the bootloader handed control over and the
 *                            display region really is writable at that address;
 *                            therefore our UEFI is what is failing, and the next
 *                            step is UEFI-side debugging.
 *     screen unchanged    -> the bootloader did NOT execute the payload, and the
 *                            problem is in how the image is packaged, not in the
 *                            firmware itself.
 *
 * The 64-byte prefix is a valid AArch64 Linux Image header (magic "ARM\x64" at
 * offset 0x38), which is what the Qualcomm bootloader validates before it will
 * jump -- the same trick Mu-Silicium's BootShim uses.
 *
 * Address: 0xD5100000 is this device's XBL "Display_Reserved" base, recovered
 * from xbl_config.img (see docs/abl-memory-map.json).  The region is 0x2B00000
 * (44 MiB); a 3000x2120 32bpp frame is 25.4 MiB, so filling it cannot run past
 * the reserved area.
 */

    .text
    .globl _start

_start:
    /* ---- AArch64 Image header (64 bytes) ---- */
    b       code
    .long   0                        /* code1: unused                     */
    .quad   0xD5100000               /* text_offset: FB base              */
    .quad   0                        /* image_size: 0 = unspecified       */
    .quad   0                        /* flags: LE kernel                  */
    .quad   0                        /* res2[0]                           */
    .quad   0                        /* res2[1]                           */
    .quad   0                        /* res2[2]                           */
    .ascii  "ARM\x64"                /* magic at 0x38                     */
    .long   0                        /* res4                              */

code:
    movz    x0, #0xD510, lsl #16     /* x0 = 0xD5100000 (FB base)         */
    movz    x1, #0xFF00, lsl #16
    movk    x1, #0xFF00              /* x1 = 0xFF00FF00 (opaque green)    */
    ldr     x2, =6360000             /* 3000 * 2120 pixels                */

fill:
    str     w1, [x0], #4
    subs    x2, x2, #1
    b.ne    fill

hang:
    b       hang                     /* never returns                     */

    .ltorg
