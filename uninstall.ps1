param([switch]$DryRun, [switch]$RemoveSettings, [string]$ConfirmRoot)
$ErrorActionPreference = 'Stop'
foreach ($Candidate in @(@('py', '-3.12'), @('py', '-3'), @('python'))) {
    if (-not (Get-Command $Candidate[0] -ErrorAction SilentlyContinue)) { continue }
    $Program = $Candidate[0]
    $Prefix = @($Candidate | Select-Object -Skip 1)
    try {
        $ErrorActionPreference = 'Continue'
        & $Program @Prefix -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)' 2>$null
        if (-not $? -or $LASTEXITCODE -ne 0) { continue }
    } catch { continue } finally { $ErrorActionPreference = 'Stop' }
    $UninstallArgs = @((Join-Path $PSScriptRoot 'tools/uninstall.py'), '--launcher-pid', "$PID")
    if ($DryRun) { $UninstallArgs += '--dry-run' }
    if ($RemoveSettings) { $UninstallArgs += '--remove-settings' }
    if ($ConfirmRoot) { $UninstallArgs += @('--confirm-root', $ConfirmRoot) }
    & $Program @Prefix @UninstallArgs
    exit $LASTEXITCODE
}
throw 'ACTION_REQUIRED: Python 3.12+ is required. See README for manual removal.'
