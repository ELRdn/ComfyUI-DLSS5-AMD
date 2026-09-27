<# One-command personal-use setup from a cloned repository.
   Requires a user-supplied, legitimately obtained NR DLL or ZIP, an x64 VS
   Developer PowerShell for the native build, and explicit runtime-license acceptance.
   No proprietary assets are bundled or uploaded. Existing configs are preserved. #>
[CmdletBinding(DefaultParameterSetName = 'Zip')]
param(
    [Parameter(Mandatory = $true, ParameterSetName = 'Zip')][string]$ModelZip,
    [Parameter(Mandatory = $true, ParameterSetName = 'Dll')][string]$ModelDll,
    [string]$Python = 'python',
    [string]$HipDevice,
    [string]$FFmpeg,
    [string]$ConfigOutput,
    [switch]$AcceptRuntimeLicense
)
$ErrorActionPreference = 'Stop'
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$Setup = Join-Path $PSScriptRoot 'setup_runtime.py'
$Source = Join-Path $Root 'third_party\DLSS5-AMD-Video'
$Engine = Join-Path $Root 'local-build\native\dlss5_video_native.exe'
if (-not [Environment]::Is64BitProcess) { throw 'Use an x64 Developer PowerShell.' }
if (-not $AcceptRuntimeLicense) {
    throw 'Read the v0.2.17 personal/non-commercial license, then pass -AcceptRuntimeLicense if it applies to you.'
}
if (-not $ConfigOutput) { $ConfigOutput = Join-Path $Root 'config\backend.local.json' }
if (Test-Path -LiteralPath $ConfigOutput) { throw "Existing config is preserved: $ConfigOutput" }
$ModelPath = if ($PSCmdlet.ParameterSetName -eq 'Zip') { $ModelZip } else { $ModelDll }
if (-not (Test-Path -LiteralPath $ModelPath -PathType Leaf)) { throw "Model file not found: $ModelPath" }

function Invoke-CheckedPython {
    param([string[]]$Arguments)
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Python command failed (exit $LASTEXITCODE): $($Arguments[0])" }
}

if (-not $HipDevice) {
    $indices = @()
    $availableLibraries = 0
    foreach ($library in @('amdhip64_6.dll', 'amdhip64_7.dll')) {
        $raw = & $Python $Setup probe-hip --library $library 2>$null
        if ($LASTEXITCODE -ne 0) { continue }
        $availableLibraries++
        $report = ($raw -join "`n") | ConvertFrom-Json
        $gpuMatches = @($report.devices | Where-Object { $_.name -match 'RX 9070 XT' })
        if ($gpuMatches.Count -eq 1) { $indices += [string]$gpuMatches[0].index }
    }
    $unique = @($indices | Sort-Object -Unique)
    if ($availableLibraries -eq 0 -or $indices.Count -ne $availableLibraries -or $unique.Count -ne 1) {
        throw 'Could not identify one consistent RX 9070 XT HIP index. Run setup_runtime.py probe-hip and pass -HipDevice explicitly.'
    }
    $HipDevice = $unique[0]
}
if ($HipDevice -notmatch '^[0-9]+$') { throw '-HipDevice must be a verified numeric HIP index.' }
Write-Host "Using HIP device index $HipDevice"

if (Test-Path -LiteralPath $Source) {
    Invoke-CheckedPython -Arguments @((Join-Path $PSScriptRoot 'fetch_upstream.py'), '--verify-only')
} else {
    Invoke-CheckedPython -Arguments @((Join-Path $PSScriptRoot 'fetch_upstream.py'))
}
if (-not (Test-Path -LiteralPath $Engine -PathType Leaf)) {
    & (Join-Path $PSScriptRoot 'build_native.ps1') -Python $Python
    if (-not (Test-Path -LiteralPath $Engine -PathType Leaf)) { throw 'Native host build did not produce an executable.' }
}
Invoke-CheckedPython -Arguments @($Setup, 'prepare')
$modelOption = if ($PSCmdlet.ParameterSetName -eq 'Zip') { '--model-zip' } else { '--model-dll' }
Invoke-CheckedPython -Arguments @($Setup, 'install', $modelOption, $ModelPath,
    '--hip-device', $HipDevice, '--engine', $Engine, '--config-output', $ConfigOutput,
    '--accept-runtime-license', '--enable-config')
if ($FFmpeg) {
    Invoke-CheckedPython -Arguments @($Setup, 'configure-amf', '--ffmpeg', $FFmpeg,
        '--config', $ConfigOutput)
} else {
    Write-Warning 'NR is configured, but one-node image/video upscaling needs an AMF-enabled FFmpeg. Run configure-amf when available.'
}
Write-Host "Setup complete: $ConfigOutput"
Write-Host 'Restart ComfyUI. Setup has not established GPU inference, output quality, or commercial rights.'
