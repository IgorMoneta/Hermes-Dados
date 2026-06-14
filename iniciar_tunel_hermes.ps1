$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

$Cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if ($Cloudflared) {
    $CloudflaredPath = $Cloudflared.Source
} else {
    $LocalCloudflared = Join-Path $ProjectDir "cloudflared.exe"
    if (Test-Path $LocalCloudflared) {
        $CloudflaredPath = $LocalCloudflared
    } else {
        throw "cloudflared nao encontrado. Execute instalar_cloudflared.ps1."
    }
}

Write-Host ""
Write-Host "Criando endereco HTTPS publico para a API local..."
$StateDir = Join-Path $ProjectDir "data\state"
$Stdout = Join-Path $StateDir "cloudflared.stdout.log"
$Stderr = Join-Path $StateDir "cloudflared.stderr.log"
$UrlPath = Join-Path $StateDir "hermes-tunnel-url.txt"
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
Remove-Item -LiteralPath $Stdout, $Stderr -Force -ErrorAction SilentlyContinue

$Process = Start-Process `
    -FilePath $CloudflaredPath `
    -ArgumentList @("tunnel", "--url", "http://127.0.0.1:8787", "--no-autoupdate") `
    -WindowStyle Hidden `
    -RedirectStandardOutput $Stdout `
    -RedirectStandardError $Stderr `
    -PassThru

$Url = $null
for ($Attempt = 0; $Attempt -lt 30 -and -not $Url; $Attempt++) {
    Start-Sleep -Seconds 1
    $Log = ((Get-Content $Stdout, $Stderr -Raw -ErrorAction SilentlyContinue) -join "`n")
    $Match = [regex]::Match($Log, "https://[a-z0-9-]+\.trycloudflare\.com")
    if ($Match.Success) {
        $Url = $Match.Value
    }
}
if (-not $Url) {
    Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
    throw "Nao foi possivel obter a URL do tunel. Consulte data\state\cloudflared.stderr.log."
}

[System.IO.File]::WriteAllText($UrlPath, $Url)
Write-Host ""
Write-Host "Tunel Hermes ativo:"
Write-Host $Url
Write-Host ""
Write-Host "A URL foi salva em data\state\hermes-tunnel-url.txt."
Write-Host "Mantenha esta janela aberta."
Wait-Process -Id $Process.Id
