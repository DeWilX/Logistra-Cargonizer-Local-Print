param([string]$PythonPath)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$buildPython = $null
$pythonArguments = @()
if ($PythonPath) {
    $buildPython = (Resolve-Path -LiteralPath $PythonPath).Path
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $buildPython = (Get-Command py).Source
    $pythonArguments = @('-3')
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $buildPython = (Get-Command python).Source
}
if (-not $buildPython) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw 'Python un winget nav atrasti. Instalē Python no python.org, tad palaid šo failu vēlreiz.'
    }
    winget install --id Python.Python.3.12 --exact --scope user --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { throw 'Python instalēšana neizdevās.' }
    $buildPython = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
    if (-not (Test-Path $buildPython)) { throw 'Python instalēts, bet ceļš nav atrasts. Atver jaunu PowerShell logu un palaid vēlreiz.' }
}
& $buildPython @pythonArguments -m venv .build-venv-windows
if ($LASTEXITCODE -ne 0) { throw 'Neizdevās izveidot būvēšanas vidi.' }
& .\.build-venv-windows\Scripts\python.exe -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Neizdevās instalēt PyInstaller.' }
& .\.build-venv-windows\Scripts\python.exe -m unittest discover -s tests -q
if ($LASTEXITCODE -ne 0) { throw 'Testi neizdevās.' }
& .\.build-venv-windows\Scripts\python.exe build_app.py
if ($LASTEXITCODE -ne 0) { throw 'EXE būvēšana neizdevās.' }
Write-Host 'Gatavs: dist\Logistra-Print.exe. Lietotājam Python vairs nav vajadzīgs.'
