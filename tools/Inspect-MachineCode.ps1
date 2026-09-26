param(
    [string]$Function = 'collides',
    [ValidateRange(1, 4096)][int]$Count = 96
)
# Read-only inspection. Does not execute the game and needs no extra modules.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$exe = Join-Path $root 'TetrisMachine.exe'
$map = Get-Content -LiteralPath (Join-Path $root 'docs\machine-map.json') -Raw | ConvertFrom-Json
[byte[]]$bytes = [IO.File]::ReadAllBytes($exe)
if ($map.functions -notcontains $Function) { throw "Unknown function: $Function" }
$rva = [int]$map.labels.PSObject.Properties[$Function].Value
$functionEnd = [int]$map.labels.PSObject.Properties[($Function + '_end')].Value
$pe = [BitConverter]::ToInt32($bytes, 0x3c)
if ([BitConverter]::ToUInt16($bytes, $pe + 4) -ne 0x8664) { throw 'Not an AMD64 executable' }
$sections = [BitConverter]::ToUInt16($bytes, $pe + 6)
$optionalSize = [BitConverter]::ToUInt16($bytes, $pe + 20)
$table = $pe + 24 + $optionalSize
$offset = -1
for ($i = 0; $i -lt $sections; $i++) {
    $s = $table + 40 * $i
    $virtualSize = [BitConverter]::ToInt32($bytes, $s + 8)
    $virtualAddress = [BitConverter]::ToInt32($bytes, $s + 12)
    $rawOffset = [BitConverter]::ToInt32($bytes, $s + 20)
    if ($rva -ge $virtualAddress -and $rva -lt ($virtualAddress + $virtualSize)) {
        $offset = $rawOffset + $rva - $virtualAddress
        break
    }
}
if ($offset -lt 0) { throw 'Function RVA is not inside a PE section' }
$n = [Math]::Min($Count, $functionEnd - $rva)
[byte[]]$code = New-Object byte[] $n
[Array]::Copy($bytes, $offset, $code, 0, $n)
"File: $exe"
"Function: $Function"
'RVA: 0x{0:X}; actual file offset: 0x{1:X}; bytes: {2}' -f $rva, $offset, $n
'Format-Hex offsets below are relative to the start of this extracted block.'
Format-Hex -InputObject $code
'Current EXE SHA256:'
(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
'Byte listing (same code with labels):'
Join-Path $root 'docs\machine-code.hex'
