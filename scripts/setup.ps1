param(
    [string]$Python,
    [switch]$Check,
    [switch]$NonInteractive,
    [string]$DeviceSerial,
    [ValidateSet("codex","claude","gemini","antigravity")][string]$AiCli
)
$ErrorActionPreference = "Stop"
Write-Warning 'scripts/setup.ps1 is deprecated; use the root setup.ps1 installer.'
if ($PSBoundParameters.ContainsKey('Python')) {
    throw 'The legacy -Python parameter is no longer supported. Root setup.ps1 selects Python 3.12+ from the official launchers/PATH.'
}
& (Join-Path (Split-Path -Parent $PSScriptRoot) 'setup.ps1') @PSBoundParameters
exit $LASTEXITCODE
