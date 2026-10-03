param(
    [ValidateSet('auto', 'conda', 'venv')][string]$Manager = 'auto',
    [ValidateRange(1, 65535)][int]$Port = 8765,
    [switch]$Update,
    [switch]$Check
)
$ErrorActionPreference = 'Stop'
$launchArgs = @((Join-Path $PSScriptRoot 'launch.py'), '--manager', $Manager, '--port', "$Port")
if ($Update) { $launchArgs += '--update' }
if ($Check) { $launchArgs += '--check' }

$condaCommand = $null
if ($env:CONDA_EXE -and (Test-Path -LiteralPath $env:CONDA_EXE -PathType Leaf)) {
    $condaCommand = $env:CONDA_EXE
} elseif (Get-Command conda -ErrorAction SilentlyContinue) {
    $condaCommand = 'conda'
}
if ($Manager -ne 'venv' -and $condaCommand) {
    & $condaCommand run --no-capture-output -n base python @launchArgs
    exit $LASTEXITCODE
}
if ($Manager -eq 'conda') {
    Write-Error 'Conda not found. Run from Anaconda Prompt/initialized PowerShell; no pip fallback was attempted.'
    exit 1
}
# Prefer the Windows Python launcher and Python 3.12, then a PATH interpreter.
if (Get-Command py -ErrorAction SilentlyContinue) {
    $savedPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & py -3.12 -c 'import sys' 2>$null
    $hasPython312 = $LASTEXITCODE -eq 0
    $ErrorActionPreference = $savedPreference
    if ($hasPython312) { & py -3.12 @launchArgs; exit $LASTEXITCODE }
    & py -3 @launchArgs
    exit $LASTEXITCODE
}
foreach ($pythonCommand in @('python', 'python3')) {
    if (Get-Command $pythonCommand -ErrorAction SilentlyContinue) {
        & $pythonCommand @launchArgs
        exit $LASTEXITCODE
    }
}
Write-Error 'Python not found. Install Miniconda/Anaconda or Python 3.12, reopen the terminal, and retry.'
exit 1
