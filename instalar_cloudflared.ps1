$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Destination = Join-Path $ProjectDir "cloudflared.exe"
$DownloadUrl = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"

Write-Host "Baixando Cloudflare Tunnel..."
Invoke-WebRequest -Uri $DownloadUrl -OutFile $Destination
Write-Host "Instalado em: $Destination"
