/*
 * shimprobe.S -- BootShim with a visible progress marker.
 *
 * SPDX-License-Identifier: GPL-2.0-only
 *
 * Same job as BootShim.S (copy the UEFI firmware volume to UEFI_BASE and jump
 * to it), with two additions used only for bring-up:
 *
 *   1. before copying, fill the panel with solid BLUE
 *   2. after copying, before jumping, fill it with solid MAGENTA
 *
 * Combined with the earlier all-green probe this turns the panel into a
 * three-state indicator:
 *
 *   screen stays on the bootloader logo  -> the loader never executed us
 *   screen turns BLUE and stays          -> we ran, the copy faulted
 *   screen turns MAGENTA and stays       -> the copy finished and we jumped;
 *                                           anything after this is UEFI's fault
 *   screen turns MAGENTA then changes    -> UEFI started and drew something
 *
 * That is enough to tell a loader/packaging problem apart from a firmware
 * problem without a UART.
 *
 * The 64-byte prefix is a valid AArch64 Image header (magic "ARM\x64" at
 * offset 0x38); the payload (BootShim's real work + the FD) follows inline.
 *
 * Build: see scripts/make_shimprobe.sh.  UEFI_BASE / UEFI_SIZE come from -D.
 */

    .text
    .globl _start

_start:
    /* ---- AArch64 Image header (64 bytes) ---- */
    b       code
    .long   0                        /* code1                             */
    .quad   UEFI_BASE                /* text_offset                       */
    .quad   UEFI_SIZE                /* image_size                        */
    .quad   0                        /* flags                             */
    .quad   0
    .quad   0
    .quad   0
    .ascii  "ARM\x64"                /* magic at 0x38                     */
    .long   0

code:
    /* ---- marker 1: solid blue ---- */
    movz    x0, #0xD510, lsl #16     /* FB base 0xD5100000                */
    movz    x1, #0x0000, lsl #16
    movk    x1, #0x00FF              /* 0xFF0000FF = opaque blue          */
    ldr     x2, =6360000
1:
    str     w1, [x0], #4
    subs    x2, x2, #1
    b.ne    1b

    /* ---- copy payload to UEFI_BASE ---- */
    adr     x4, payload              /* source: FD appended after us      */
    ldr     x5, =UEFI_BASE           /* destination                       */
    ldr     x6, =UEFI_SIZE           /* bytes to copy                     */
2:
    ldp     x2, x3, [x4], #16
    stp     x2, x3, [x5], #16
    subs    x6, x6, #16
    b.ne    2b

    /* ---- marker 2: solid magenta ---- */
    movz    x0, #0xD510, lsl #16
    movz    x1, #0xFF00
    movk    x1, #0xFF00, lsl #16     /* 0xFFFF00FF = opaque magenta       */
    ldr     x2, =6360000
3:
    str     w1, [x0], #4
    subs    x2, x2, #1
    b.ne    3b

    /* ---- jump ---- */
    ldr     x5, =UEFI_BASE
    br      x5

4:  b       4b                       /* never reached                     */

    .ltorg

    .balign 16
payload:                             /* FD is appended here               */
