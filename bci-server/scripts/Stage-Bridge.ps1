param(
    [string]$ReferenceDir = 'C:\Users\User\Desktop\Jack\Work\MIC\Muse2Demo'
)

$ErrorActionPreference = 'Stop'
$builtSource = Join-Path $PSScriptRoot '..\bridge\windows\x64\Release'
$referenceSource = Join-Path $ReferenceDir 'muse_osc_bridge\x64\Release'
$source = if ((Test-Path -LiteralPath (Join-Path $builtSource 'muse_osc_bridge.exe')) -and
              (Test-Path -LiteralPath (Join-Path $builtSource 'libmuse.dll'))) {
    $builtSource
} else {
    $referenceSource
}
$destination = Join-Path $PSScriptRoot '..\bridge\local'
$exe = Join-Path $source 'muse_osc_bridge.exe'
$dll = Join-Path $source 'libmuse.dll'

foreach ($path in @($exe, $dll)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Bridge runtime file missing: $path"
    }
}

New-Item -ItemType Directory -Force -Path $destination | Out-Null
Copy-Item -LiteralPath $exe -Destination $destination -Force
Copy-Item -LiteralPath $dll -Destination $destination -Force
Write-Host "Staged bridge runtime from $source in $destination (git-ignored)."
Get-FileHash -LiteralPath (Join-Path $destination 'muse_osc_bridge.exe'),
    (Join-Path $destination 'libmuse.dll') -Algorithm SHA256 |
    Select-Object Path, Hash
