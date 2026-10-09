param(
    [string]$SdkDir = 'C:\Users\User\Desktop\Jack\Work\MIC\Muse2Demo\libmuse_windows_8.0.5'
)

$ErrorActionPreference = 'Stop'
$SdkDir = (Resolve-Path -LiteralPath $SdkDir).Path
$project = Join-Path $PSScriptRoot '..\bridge\windows\muse_osc_bridge.vcxproj'
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
if (-not (Test-Path -LiteralPath $vswhere)) {
    throw 'Visual Studio Build Tools (vswhere.exe) not found.'
}
$installation = & $vswhere -latest -products '*' -property installationPath | Select-Object -First 1
if (-not $installation) { throw 'Visual Studio Build Tools installation not found.' }
$msbuild = Join-Path $installation 'MSBuild\Current\Bin\MSBuild.exe'
if (-not (Test-Path -LiteralPath $msbuild)) { throw 'MSBuild.exe not found.' }
$vcvars = Join-Path $installation 'VC\Auxiliary\Build\vcvars64.bat'
if (-not (Test-Path -LiteralPath $vcvars)) { throw 'vcvars64.bat not found.' }
$environmentLines = & cmd.exe /d /c "call `"$vcvars`" >nul && set"
if ($LASTEXITCODE -ne 0) { throw 'Could not initialize Visual Studio C++ tools.' }
foreach ($line in $environmentLines) {
    if ($line -match '^([^=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
    }
}
& $msbuild $project '/p:Configuration=Release' '/p:Platform=x64' "/p:MuseSdkDir=$SdkDir" '/v:minimal'
if ($LASTEXITCODE -ne 0) { throw "Bridge build failed with exit code $LASTEXITCODE" }
$output = Join-Path $PSScriptRoot '..\bridge\windows\x64\Release'
$localDir = Join-Path $PSScriptRoot '..\bridge\local'
New-Item -ItemType Directory -Force -Path $localDir | Out-Null
Copy-Item -LiteralPath (Join-Path $output 'muse_osc_bridge.exe') -Destination $localDir -Force
Copy-Item -LiteralPath (Join-Path $output 'libmuse.dll') -Destination $localDir -Force
Write-Host 'Build complete. Staged rebuilt bridge in bridge/local (git-ignored).'
