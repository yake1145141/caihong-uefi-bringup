<#
.SYNOPSIS
    Build and verify the caihong (SM8650) ACPI table set on Windows.

.DESCRIPTION
    Produces:
      build/acpi/DSDT.aml                       from acpi/caihong/DSDT.dsl
      build/acpi/{FACP,APIC,GTDT,DBG2,PPTT}.aml derived from the upstream
                                                SM8550 ("Kailua") SoC tables

    Every table is then (a) checksum-verified and (b) disassembled with iasl as
    an independent structural check.  A table that fails either step fails the
    script.

    Uses the iasl.exe that ships inside the Mu-Qcom checkout
    (Silicium-ACPI/Compiler/iasl.exe, ACPICA 20230628), so no separate ACPICA
    install is required.

.PARAMETER MuQcomDir
    Path to the Mu-Qcom checkout. Defaults to .\source\Mu-Qcom-musabcel

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\build_acpi.ps1
#>
[CmdletBinding()]
param(
    [string]$MuQcomDir = '',
    [string]$OutDir    = ''
)

$ErrorActionPreference = 'Stop'

# $PSScriptRoot is not reliably available while evaluating parameter defaults
# under Windows PowerShell 5.1, so resolve paths in the body.
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $scriptDir '..')).Path
if (-not $MuQcomDir) { $MuQcomDir = Join-Path $root 'source\Mu-Qcom-musabcel' }
if (-not $OutDir)    { $OutDir    = Join-Path $root 'build\acpi' }
$MuQcomDir = (Resolve-Path $MuQcomDir -ErrorAction Stop).Path
$OutDir = [System.IO.Path]::GetFullPath($OutDir)

$iasl = Join-Path $MuQcomDir 'Silicium-ACPI\Compiler\iasl.exe'
if (-not (Test-Path $iasl)) {
    throw "iasl.exe not found at $iasl. Clone Mu-Qcom (which vendors it) or point -MuQcomDir at a checkout."
}
$kailua = Join-Path $MuQcomDir 'Silicium-ACPI\SoCs\Qualcomm\Kailua'
if (-not (Test-Path $kailua)) {
    throw "Upstream SM8550 SoC table directory not found: $kailua"
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

function Invoke-Iasl {
    param([string[]]$Arguments, [string]$What)
    $out = & $iasl @Arguments 2>&1
    $text = ($out | Out-String)
    Write-Host $text.Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "iasl failed while $What (exit $LASTEXITCODE)"
    }
    return $text
}

Write-Host "== 1/4 compile caihong DSDT =="
$dsl = Join-Path $root 'acpi\caihong\DSDT.dsl'
if (-not (Test-Path $dsl)) { throw "missing $dsl" }
$aml = Join-Path $OutDir 'DSDT.aml'
if (Test-Path $aml) { Remove-Item $aml -Force }
$txt = Invoke-Iasl -Arguments @('-p', $aml, '-vi', $dsl) -What 'compiling DSDT.dsl'
if ($txt -match 'Compilation failed') { throw 'DSDT compilation failed' }
if (-not (Test-Path $aml)) { throw 'DSDT.aml was not produced' }
Write-Host ("   DSDT.aml: {0} bytes" -f (Get-Item $aml).Length)

Write-Host "== 2/4 derive SM8650 SoC tables from the SM8550 set (assertions enforced) =="
python (Join-Path $root 'scripts\build_soc_acpi.py') --kailua $kailua --out $OutDir `
    --json (Join-Path $OutDir 'soc-tables.json')
if ($LASTEXITCODE -ne 0) { throw 'build_soc_acpi.py refused to generate the SoC tables' }

Write-Host "== 3/4 verify checksums =="
# Enumerate exactly the tables this project is responsible for.  iasl leaves
# namespace files (ns_dsdt.nsp) and temporary disassembly output behind, so a
# wildcard glob would both pick up junk and give false confidence.
$expected = @('DSDT.aml', 'FACP.aml', 'APIC.aml', 'GTDT.aml', 'DBG2.aml', 'PPTT.aml')
foreach ($name in $expected) {
    $full = Join-Path $OutDir $name
    if (-not (Test-Path $full)) { throw "expected table was not produced: $name" }
}
foreach ($name in $expected) {
    $full = Join-Path $OutDir $name
    $bytes = [System.IO.File]::ReadAllBytes($full)
    $sum = 0
    foreach ($b in $bytes) { $sum = ($sum + $b) -band 0xFF }
    if ($sum -ne 0) { throw "${name}: ACPI checksum invalid (sum=0x$('{0:X2}' -f $sum))" }
    Write-Host ("   OK  {0,-10} {1,6} bytes  checksum ok" -f $name, $bytes.Length)
}

Write-Host "== 4/4 disassemble as an independent structural check =="
Push-Location $OutDir
try {
    # iasl writes informational text to stderr; with $ErrorActionPreference=Stop
    # Windows PowerShell 5.1 turns that into a terminating error.  Relax it for
    # this call only and judge success on exit code + produced output instead.
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $dis = & $iasl -d $expected 2>&1 | Out-String
        $rc = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $prev }

    if ($rc -ne 0) {
        Write-Host $dis
        throw "iasl failed to disassemble the generated tables (exit $rc)"
    }
    if ($dis -match 'Error\s+\d') {
        Write-Host $dis
        throw 'iasl reported errors while disassembling the generated tables'
    }
    foreach ($name in $expected) {
        $dslOut = [System.IO.Path]::ChangeExtension($name, '.dsl')
        $p = Join-Path $OutDir $dslOut
        if (-not (Test-Path $p) -or (Get-Item $p).Length -eq 0) {
            throw "disassembly of $name produced no usable $dslOut"
        }
    }
    Write-Host ("   disassembled {0} tables without error" -f $expected.Count)
}
finally { Pop-Location }

Write-Host ''
Write-Host 'ACPI build + verification PASSED'
Get-ChildItem $OutDir -Filter '*.aml' | Where-Object { $expected -contains $_.Name } | ForEach-Object {
    Write-Host ("   {0,-10} {1,6} bytes" -f $_.Name, $_.Length)
}
