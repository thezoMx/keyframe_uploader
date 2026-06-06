# Build a standalone KeyframeUploaderServer.exe for non-technical users.
# Requires: pip install pyinstaller
# The resulting exe still reads config.json from the same folder it runs in.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $here
try {
    pyinstaller --onefile --name KeyframeUploaderServer `
        --add-data "config.json;." `
        server.py
    Write-Host "Built dist/KeyframeUploaderServer.exe" -ForegroundColor Green
    Write-Host "Ship it alongside a config.json the user can edit." -ForegroundColor Yellow
}
finally {
    Pop-Location
}
