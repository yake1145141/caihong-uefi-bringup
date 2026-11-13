/** @file
  CAIHONG bring-up: dump the ACPI tables the OS will see, then halt.

  DEPEX on EFI_SIMPLE_FILE_SYSTEM_PROTOCOL guarantees this runs after the UFS,
  partition and FAT stack are up, which is well after AcpiTableDxe and
  AcpiPlatformDxe have installed every table.

  We need this because after fixing the storage GUID, the GICC length, PPTT and
  PcdAcpiExposedTableVersions the loader still dies, so read the real RSDP/XSDT
  instead of guessing.
**/

#include <Uefi.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Library/DebugLib.h>
#include <Library/BaseLib.h>
#include <Library/BaseMemoryLib.h>
#include <Guid/Acpi.h>

STATIC
VOID
PrintSig (
  IN  CONST UINT8  *Src,
  IN  UINTN         Len
  )
{
  CHAR8  Buf[10];
  UINTN  i;

  for (i = 0; (i < Len) && (i < 9); i++) {
    Buf[i] = (CHAR8)Src[i];
  }

  Buf[i] = 0;
  DEBUG ((DEBUG_ERROR, "%a", Buf));
}

EFI_STATUS
EFIAPI
AcpiDumpEntry (
  IN EFI_HANDLE        ImageHandle,
  IN EFI_SYSTEM_TABLE  *SystemTable
  )
{
  EFI_CONFIGURATION_TABLE  *Ct;
  UINTN                    Index;
  UINTN                    Tbl;
  VOID                     *Rsdp = NULL;
  UINT8                    *Xsdt;
  UINT64                   Addr;
  UINT32                   Len;
  UINT32                   Count;

  DEBUG ((DEBUG_ERROR, "[ACPI-DUMP] entries=%d\n", (UINT32)gST->NumberOfTableEntries));

  Ct = gST->ConfigurationTable;
  for (Index = 0; Index < gST->NumberOfTableEntries; Index++) {
    if (CompareGuid (&Ct[Index].VendorGuid, &gEfiAcpi20TableGuid)) {
      Rsdp = Ct[Index].VendorTable;
      break;
    }
  }

  if (Rsdp == NULL) {
    for (Index = 0; Index < gST->NumberOfTableEntries; Index++) {
      if (CompareGuid (&Ct[Index].VendorGuid, &gEfiAcpiTableGuid)) {
        Rsdp = Ct[Index].VendorTable;
        break;
      }
    }
    DEBUG ((DEBUG_ERROR, "[ACPI-DUMP] only ACPI1.0 present (or none)\n"));
  }

  if (Rsdp == NULL) {
    DEBUG ((DEBUG_ERROR, "[ACPI-DUMP] NO RSDP AT ALL\n"));
    goto Halt;
  }

  DEBUG ((DEBUG_ERROR, "[ACPI-DUMP] rsdp=0x%lx sig=", (UINT64)(UINTN)Rsdp));
  PrintSig ((UINT8 *)Rsdp, 8);
  DEBUG ((DEBUG_ERROR, " rev=%d\n", (UINT32)((UINT8 *)Rsdp)[15]));

  CopyMem (&Len, (UINT8 *)Rsdp + 20, 4);
  CopyMem (&Addr, (UINT8 *)Rsdp + 24, 8);
  DEBUG ((DEBUG_ERROR, "[ACPI-DUMP] rsdp_len=%d xsdt=0x%lx\n", Len, Addr));
  if (Addr == 0) {
    DEBUG ((DEBUG_ERROR, "[ACPI-DUMP] XSDT IS NULL\n"));
    goto Halt;
  }

  Xsdt = (UINT8 *)(UINTN)Addr;
  CopyMem (&Len, Xsdt + 4, 4);
  DEBUG ((DEBUG_ERROR, "[ACPI-DUMP] xsdt sig="));
  PrintSig (Xsdt, 4);
  DEBUG ((DEBUG_ERROR, " len=%d\n", Len));

  Count = (Len - 36) / 8;
  DEBUG ((DEBUG_ERROR, "[ACPI-DUMP] count=%d\n", Count));

  for (Tbl = 0; Tbl < Count; Tbl++) {
    CopyMem (&Addr, Xsdt + 36 + Tbl * 8, 8);
    if (Addr == 0) {
      continue;
    }

    DEBUG ((DEBUG_ERROR, "[ACPI-DUMP]  %d ", (UINT32)Tbl));
    PrintSig ((UINT8 *)(UINTN)Addr, 4);
    CopyMem (&Len, (UINT8 *)(UINTN)Addr + 4, 4);
    DEBUG ((DEBUG_ERROR, " len=%d rev=%d\n", Len,
            (UINT32)((UINT8 *)(UINTN)Addr)[8]));

    // For the FADT, also show the DSDT pointers: Windows dereferences these.
    if ((((UINT8 *)(UINTN)Addr)[0] == 'F') &&
        (((UINT8 *)(UINTN)Addr)[1] == 'A') &&
        (((UINT8 *)(UINTN)Addr)[2] == 'C') &&
        (((UINT8 *)(UINTN)Addr)[3] == 'P'))
    {
      UINT32  Dsdt32;
      UINT64  Dsdt64;
      UINT32  Flags;

      CopyMem (&Dsdt32, (UINT8 *)(UINTN)Addr + 0x28, 4);
      CopyMem (&Dsdt64, (UINT8 *)(UINTN)Addr + 0x88, 8);
      CopyMem (&Flags, (UINT8 *)(UINTN)Addr + 0x70, 4);
      DEBUG ((DEBUG_ERROR, "[ACPI-DUMP]     FADT DSDT=0x%x X_DSDT=0x%lx flags=0x%x\n",
              Dsdt32, Dsdt64, Flags));

      if (Dsdt32 != 0) {
        DEBUG ((DEBUG_ERROR, "[ACPI-DUMP]     DSDT sig="));
        PrintSig ((UINT8 *)(UINTN)Dsdt32, 4);
        DEBUG ((DEBUG_ERROR, "\n"));
      }
    }
  }

Halt:
  DEBUG ((DEBUG_ERROR, "[ACPI-DUMP] HALT\n"));
  CpuDeadLoop ();
  return EFI_SUCCESS;
}
