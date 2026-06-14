$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigPath = Join-Path $ProjectDir ".env.local"

if (Test-Path $ConfigPath) {
    Write-Host "A configuracao local ja existe em .env.local."
    Write-Host "Apague o arquivo para gerar um novo token."
    exit 0
}

$TokenBytes = New-Object byte[] 32
$Generator = New-Object System.Security.Cryptography.RNGCryptoServiceProvider
$Generator.GetBytes($TokenBytes)
$Generator.Dispose()
$Token = ([BitConverter]::ToString($TokenBytes) -replace "-", "").ToLowerInvariant()

$Content = @"
HERMES_API_TOKEN=$Token
HERMES_TIMEOUT_SECONDS=20
"@
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($ConfigPath, $Content, $Utf8NoBom)

Write-Host ""
Write-Host "Ponte Hermes configurada."
Write-Host "Token salvo somente em: $ConfigPath"
Write-Host "Este arquivo esta protegido pelo .gitignore."
Write-Host ""
Write-Host "Token para cadastrar no Streamlit Cloud:"
Write-Host $Token
