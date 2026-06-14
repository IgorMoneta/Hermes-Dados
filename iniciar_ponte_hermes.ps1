$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

$Python = Join-Path $ProjectDir ".venv\Scripts\python.exe"
$ConfigPath = Join-Path $ProjectDir ".env.local"

if (-not (Test-Path $Python)) {
    throw "Ambiente Python nao encontrado. Execute iniciar_demo.bat primeiro."
}
if (-not (Test-Path $ConfigPath)) {
    & (Join-Path $ProjectDir "configurar_ponte_hermes.ps1")
}

Get-Content -LiteralPath $ConfigPath | ForEach-Object {
    if ($_ -match "^\s*([^#][^=]*)=(.*)$") {
        [Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), "Process")
    }
}

$env:PYTHONPATH = Join-Path $ProjectDir "src"
$HermesHome = Join-Path $env:LOCALAPPDATA "hermes"
if (Test-Path (Join-Path $HermesHome "auth.json")) {
    $env:HERMES_HOME = $HermesHome
}

Write-Host ""
Write-Host "API local do Hermes iniciada."
Write-Host "Endereco local: http://127.0.0.1:8787"
Write-Host "Teste de saude: http://127.0.0.1:8787/health"
Write-Host ""
& $Python -m uvicorn hermes_api:app --host 127.0.0.1 --port 8787
