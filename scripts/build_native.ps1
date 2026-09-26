<# Build the inspected external native host. No admin rights or driver changes.
   Run from a Visual Studio x64 Developer PowerShell with C++/Windows SDK/CMake.
   This helper was source-reviewed, not executed on Windows in this delivery. #>
[CmdletBinding()]
param(
    [string]$Python = 'python',
    [string]$Upstream = (Join-Path $PSScriptRoot '..\third_party\DLSS5-AMD-Video'),
    [string]$BuildDirectory = (Join-Path $PSScriptRoot '..\local-build\native')
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Upstream = [IO.Path]::GetFullPath($Upstream)
$BuildDirectory = [IO.Path]::GetFullPath($BuildDirectory)
if (-not [Environment]::Is64BitProcess) { throw 'Use an x64 Developer PowerShell.' }
foreach ($Tool in @('git', 'cmake', 'cl', 'nmake')) {
    if (-not (Get-Command $Tool -ErrorAction SilentlyContinue)) {
        throw "Missing $Tool. Use an x64 Visual Studio Developer PowerShell with C++ and Windows SDK."
    }
}
if (Test-Path $BuildDirectory) { throw 'Choose a fresh build directory; existing files are never removed.' }
& $Python (Join-Path $PSScriptRoot 'fetch_upstream.py') --destination $Upstream --verify-only
if ($LASTEXITCODE -ne 0) { throw 'Pinned source verification failed.' }
# Do not execute the upstream maintainer's machine-specific build.ps1.
& cmake -S (Join-Path $Upstream 'native') -B $BuildDirectory -G 'NMake Makefiles' -DCMAKE_BUILD_TYPE=Release
if ($LASTEXITCODE -ne 0) { throw 'CMake configuration failed.' }
& cmake --build $BuildDirectory
if ($LASTEXITCODE -ne 0) { throw 'Native build failed.' }
$Engine = Join-Path $BuildDirectory 'dlss5_video_native.exe'
if (-not (Test-Path $Engine -PathType Leaf)) { throw 'Expected executable was not produced.' }
$Lock = Get-Content (Join-Path $Root 'upstream.lock.json') -Raw | ConvertFrom-Json
$Record = [ordered]@{
    schema = 1
    expected_source_commit = $Lock.commit
    engine = $Engine
    engine_sha256 = (Get-FileHash $Engine -Algorithm SHA256).Hash.ToLowerInvariant()
    built_utc = [DateTime]::UtcNow.ToString('o')
    gpu_tested = $false
    cryptographically_attested = $false
}
$Record | ConvertTo-Json | Set-Content (Join-Path $BuildDirectory 'build-record.json') -Encoding UTF8
Write-Host "Built host only: $Engine"
Write-Host 'External runtime/model assets are NOT included. Follow docs/WINDOWS_SETUP.md.'
