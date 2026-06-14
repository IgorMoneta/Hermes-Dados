@echo off
start "Hermes API Local" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0iniciar_ponte_hermes.ps1"
timeout /t 4 /nobreak >nul
start "Hermes Cloudflare Tunnel" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0iniciar_tunel_hermes.ps1"
