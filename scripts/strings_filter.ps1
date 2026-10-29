# Extract printable ASCII strings from a binary and show those that look like
# error messages or configuration keys.  Used to find out what a prebuilt
# Qualcomm driver is looking for when it returns EFI_NOT_FOUND.
param(
    [Parameter(Mandatory = $true)][string]$Path,
    [int]$MinLength = 6
)

$bytes = [System.IO.File]::ReadAllBytes($Path)
$text = [System.Text.Encoding]::ASCII.GetString($bytes)

# split on non-printable characters
$strings = [regex]::Matches($text, "[ -~]{$MinLength,}") | ForEach-Object { $_.Value }

Write-Output ("total strings: " + $strings.Count)
Write-Output "--- error / config looking strings ---"
$strings |
    Where-Object {
        $_ -match 'ERROR|Error|error|FAIL|Fail|fail|not found|Not Found|NOT_FOUND|ASSERT|assert|Config|config|CFG|Key|key|Missing|missing|Invalid|invalid|Unsupported|unsupported'
    } |
    Select-Object -Unique |
    Select-Object -First 60 |
    ForEach-Object { Write-Output ("  " + $_) }
