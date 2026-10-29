# Dump strings from a PE binary that look like configuration keys or DAL
# identifiers: the names a Qualcomm driver passes to the config map.
param(
    [Parameter(Mandatory = $true)][string]$Path
)

$bytes = [System.IO.File]::ReadAllBytes($Path)
$text = [System.Text.Encoding]::ASCII.GetString($bytes)
$strings = [regex]::Matches($text, "[ -~]{4,}") | ForEach-Object { $_.Value } | Select-Object -Unique

Write-Output "--- key-like (UPPER_SNAKE / CamelCase keys) ---"
$strings |
    Where-Object { $_ -match '^[A-Z][A-Za-z0-9_]{5,40}$' -and $_ -match '[A-Z].*[A-Z]' } |
    Where-Object { $_ -notmatch '^(EFI|DXE|PEI|MM|ARM|NULL|TRUE|FALSE|GUID|SMBIOS|ACPI|PCI)' } |
    Select-Object -First 70 |
    ForEach-Object { Write-Output ("  " + $_) }

Write-Output "--- DAL / device config ---"
$strings |
    Where-Object { $_ -match 'Dal|DAL|DeviceConfig|ConfigMap|PlatformInfo|ChipInfo|IMEM|SMEM|shm_|DTB|Fdt|FDT' } |
    Select-Object -First 40 |
    ForEach-Object { Write-Output ("  " + $_) }
