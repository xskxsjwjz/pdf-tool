$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    python -m venv (Join-Path $ProjectRoot ".venv")
}

& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install -r (Join-Path $ProjectRoot "requirements-build.txt")
& $PythonExe -m unittest discover -s (Join-Path $ProjectRoot "tests") -v

& $PythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "PDFTool" `
    --collect-all tkinterdnd2 `
    --exclude-module PIL `
    --exclude-module reportlab `
    --add-data "$(Join-Path $ProjectRoot 'LICENSE');." `
    --add-data "$(Join-Path $ProjectRoot 'THIRD_PARTY_NOTICES.md');." `
    --add-data "$(Join-Path $ProjectRoot 'licenses\PYTHON_LICENSE.txt');licenses" `
    (Join-Path $ProjectRoot "app.py")

Write-Host "`n构建完成：$(Join-Path $ProjectRoot 'dist\PDFTool.exe')"
