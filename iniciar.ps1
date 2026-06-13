$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

$Python = Join-Path $ProjectDir ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Host "Preparando o ambiente da aplicacao..."
    python -m venv .venv
    & $Python -m pip install -r requirements.txt
}

if (-not (Test-Path "data\inbox\property_prices.csv")) {
    & $Python scripts\generate_property_prices.py
}

$env:PYTHONPATH = "$ProjectDir\src"
$HermesHome = Join-Path $env:LOCALAPPDATA "hermes"
if (Test-Path (Join-Path $HermesHome "auth.json")) {
    $env:HERMES_HOME = $HermesHome
}
Write-Host ""
Write-Host "Hermes Analytics iniciando..."
Write-Host "Neste PC: http://localhost:8501"
Write-Host "Em outro computador: use http://IP-DESTE-PC:8501"
Write-Host ""
& $Python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501
