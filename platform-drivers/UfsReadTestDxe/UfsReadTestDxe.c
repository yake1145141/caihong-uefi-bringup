/** @file
  CAIHONG bring-up: sequential UFS block-read smoke test.

  Windows boot manager reads the 896 MB \sources\boot.wim through
  EFI_BLOCK_IO_PROTOCOL with its own FAT driver.  Small reads are known to work
  (BOOTAA64.EFI, BCD), so the open question is whether large sequential reads
  through the patched UFS stack are stable on this device.

  This driver finds the largest BlockIo device, reads up to 256 MB in 4 MB
  chunks and prints progress.  Everything goes through DEBUG_ERROR so it stays
  visible with PcdDebugPrintErrorLevel = ERROR|WARN.

  It never writes to the device.
**/

#include <Uefi.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Library/DebugLib.h>
#include <Library/BaseLib.h>
#include <Library/MemoryAllocationLib.h>
#include <Protocol/BlockIo.h>

#define CHUNK_SIZE    (4u * 1024u * 1024u)
#define TOTAL_TO_READ (256u * 1024u * 1024u)

EFI_STATUS
EFIAPI
UfsReadTestEntry (
  IN EFI_HANDLE        ImageHandle,
  IN EFI_SYSTEM_TABLE  *SystemTable
  )
{
  EFI_STATUS             Status;
  EFI_HANDLE             *Handles = NULL;
  UINTN                  HandleCount = 0;
  UINTN                  Index;
  EFI_BLOCK_IO_PROTOCOL  *BlockIo = NULL;
  EFI_BLOCK_IO_PROTOCOL  *Best = NULL;
  UINT64                 BestBlocks = 0;
  UINT64                 BestBlockSize = 0;
  UINT64                 MediaBlocks;
  UINT64                 Chunks;
  UINT64                 Chunk;
  VOID                   *Buffer = NULL;
  UINT64                 TotalRead = 0;

  DEBUG ((DEBUG_ERROR, "[UFS-TEST] start\n"));

  Status = gBS->LocateHandleBuffer (
                  ByProtocol,
                  &gEfiBlockIoProtocolGuid,
                  NULL,
                  &HandleCount,
                  &Handles
                  );
  if (EFI_ERROR (Status) || (HandleCount == 0)) {
    DEBUG ((DEBUG_ERROR, "[UFS-TEST] no BlockIo handles (%r)\n", Status));
    return EFI_SUCCESS;
  }

  DEBUG ((DEBUG_ERROR, "[UFS-TEST] %d BlockIo handle(s)\n", (UINT32)HandleCount));

  for (Index = 0; Index < HandleCount; Index++) {
    Status = gBS->HandleProtocol (Handles[Index], &gEfiBlockIoProtocolGuid, (VOID **)&BlockIo);
    if (EFI_ERROR (Status) || (BlockIo == NULL) || (BlockIo->Media == NULL)) {
      continue;
    }

    MediaBlocks = BlockIo->Media->LastBlock;
    if (MediaBlocks > BestBlocks) {
      BestBlocks    = MediaBlocks;
      BestBlockSize = BlockIo->Media->BlockSize;
      Best          = BlockIo;
    }
  }

  if (Best == NULL) {
    DEBUG ((DEBUG_ERROR, "[UFS-TEST] no usable media\n"));
    FreePool (Handles);
    return EFI_SUCCESS;
  }

  DEBUG ((
    DEBUG_ERROR,
    "[UFS-TEST] largest media: %d blocks x %d bytes = %d MB\n",
    (UINT32)BestBlocks,
    (UINT32)BestBlockSize,
    (UINT32)((BestBlocks * BestBlockSize) / (1024 * 1024))
    ));

  if (BestBlockSize == 0) {
    DEBUG ((DEBUG_ERROR, "[UFS-TEST] block size 0\n"));
    FreePool (Handles);
    return EFI_SUCCESS;
  }

  Chunks = TOTAL_TO_READ / CHUNK_SIZE;
  if (Chunks > (BestBlocks * BestBlockSize / CHUNK_SIZE)) {
    Chunks = BestBlocks * BestBlockSize / CHUNK_SIZE;
  }

  Status = gBS->AllocatePool (EfiBootServicesData, CHUNK_SIZE, &Buffer);
  if (EFI_ERROR (Status)) {
    DEBUG ((DEBUG_ERROR, "[UFS-TEST] alloc failed %r\n", Status));
    FreePool (Handles);
    return EFI_SUCCESS;
  }

  for (Chunk = 0; Chunk < Chunks; Chunk++) {
    Status = Best->ReadBlocks (
                     Best,
                     Best->Media->MediaId,
                     Chunk * (CHUNK_SIZE / BestBlockSize),
                     CHUNK_SIZE,
                     Buffer
                     );
    if (EFI_ERROR (Status)) {
      DEBUG ((
        DEBUG_ERROR,
        "[UFS-TEST] FAILED at %d MB, status=%r\n",
        (UINT32)(Chunk * CHUNK_SIZE / (1024 * 1024)),
        Status
        ));
      break;
    }

    TotalRead += CHUNK_SIZE;
    if (((Chunk + 1) % 8) == 0) {
      DEBUG ((DEBUG_ERROR, "[UFS-TEST] read %d MB ok\n", (UINT32)(TotalRead / (1024 * 1024))));
    }
  }

  DEBUG ((
    DEBUG_ERROR,
    "[UFS-TEST] done: %d MB, last status=%r\n",
    (UINT32)(TotalRead / (1024 * 1024)),
    Status
    ));

  gBS->FreePool (Buffer);
  FreePool (Handles);

  // Hold the machine here so the results stay on the panel.  This build is a
  // diagnostic only; the next build removes the halt.
  DEBUG ((DEBUG_ERROR, "[UFS-TEST] HALT (diagnostic build)\n"));
  CpuDeadLoop ();

  return EFI_SUCCESS;
}
