# Launch the KeyframeUploader companion server.
# Usage: right-click -> Run with PowerShell, or:  ./run.ps1
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $py) { $py = (Get-Command py -ErrorAction SilentlyContinue) }
if (-not $py) {
    Write-Host "Python not found. Install Python 3.8+ from https://python.org and re-run." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
& $py.Source (Join-Path $here "server.py")
