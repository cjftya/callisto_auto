param([switch]$Check, [switch]$NonInteractive, [string]$DeviceSerial, [ValidateSet("codex","claude","gemini")][string]$AiCli)
$ErrorActionPreference = 'Stop'
# No execution-policy, system PATH or provider configuration changes.
$Candidates = @(@('py', '-3.12'), @('py', '-3'), @('python'))
$PythonCommand = $null
foreach ($Candidate in $Candidates) {
    if (-not (Get-Command $Candidate[0] -ErrorAction SilentlyContinue)) { continue }
    $Program = $Candidate[0]
    $Prefix = @($Candidate | Select-Object -Skip 1)
    $ProbeErrorActionPreference = $ErrorActionPreference
    try {
        # Missing launcher runtimes can write stderr under Windows PowerShell 5.1.
        # Only this probe may fail; keep bootstrap errors terminating as before.
        $ErrorActionPreference = 'Continue'
        & $Program @Prefix -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)' 2>$null
        if ($? -and $LASTEXITCODE -eq 0) { $PythonCommand = $Candidate; break }
    } catch {
        continue
    } finally {
        $ErrorActionPreference = $ProbeErrorActionPreference
    }
}
if (-not $PythonCommand) {
    if ($Check -or $NonInteractive -or [Console]::IsInputRedirected -or -not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw 'ACTION_REQUIRED: Install Python 3.12+ with pip, then rerun .\setup.ps1.'
    }
    $Consent = Read-Host 'Python 3.12+ is missing. Install Python 3.12 using winget (Python.Python.3.12)? [y/N]'
    if ($Consent -ne 'y') { throw 'ACTION_REQUIRED: Python installation was not approved.' }
    & winget install --id Python.Python.3.12 --exact --source winget
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    throw 'ACTION_REQUIRED: Open a new PowerShell window and rerun .\setup.ps1.'
}
$Program = $PythonCommand[0]
$Prefix = @($PythonCommand | Select-Object -Skip 1)
$BootstrapArgs = @((Join-Path $PSScriptRoot 'tools/bootstrap.py'))
if ($Check) { $BootstrapArgs += '--check' }
if ($DeviceSerial) { $BootstrapArgs += @('--device-serial', $DeviceSerial) }
if ($AiCli) { $BootstrapArgs += @('--ai-cli', $AiCli) }
if ($NonInteractive) { $BootstrapArgs += '--non-interactive' }
& $Program @Prefix @BootstrapArgs
exit $LASTEXITCODE
