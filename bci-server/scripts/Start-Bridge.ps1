param(
    [string]$ReferenceDir = 'C:\Users\User\Desktop\Jack\Work\MIC\Muse2Demo'
)

$ErrorActionPreference = 'Stop'
$localDir = Join-Path $PSScriptRoot '..\bridge\local'
$exe = Join-Path $localDir 'muse_osc_bridge.exe'
$dll = Join-Path $localDir 'libmuse.dll'
if (-not (Test-Path -LiteralPath $exe) -or -not (Test-Path -LiteralPath $dll)) {
    & (Join-Path $PSScriptRoot 'Stage-Bridge.ps1') -ReferenceDir $ReferenceDir
}
Write-Host 'Starting Muse bridge. Start the BCI API in live mode in a second terminal.'
& $exe
