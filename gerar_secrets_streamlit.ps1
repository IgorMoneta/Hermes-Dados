$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigPath = Join-Path $ProjectDir ".env.local"
$UrlPath = Join-Path $ProjectDir "data\state\hermes-tunnel-url.txt"
$OutputPath = Join-Path $ProjectDir "data\state\SECRETS_STREAMLIT_PRONTO.toml"

if (-not (Test-Path $ConfigPath)) {
    throw "Execute configurar_ponte_hermes.ps1 primeiro."
}
if (-not (Test-Path $UrlPath)) {
    throw "Inicie o tunel e registre a URL antes de gerar os Secrets."
}

$Config = @{}
Get-Content -LiteralPath $ConfigPath | ForEach-Object {
    if ($_ -match "^\s*([^#][^=]*)=(.*)$") {
        $Config[$Matches[1].Trim()] = $Matches[2].Trim()
    }
}
$Url = (Get-Content -LiteralPath $UrlPath -Raw).Trim()
$Content = @"
HERMES_API_URL = "$Url"
HERMES_API_TOKEN = "$($Config["HERMES_API_TOKEN"])"
HERMES_TIMEOUT_SECONDS = "45"
"@
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($OutputPath, $Content, $Utf8NoBom)

Write-Host "Secrets prontos em:"
Write-Host $OutputPath
Write-Host "Nao envie esse arquivo para o GitHub."
