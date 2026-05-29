$ErrorActionPreference = "SilentlyContinue"
Get-Process python* | Stop-Process -Force
Get-Process python* | Stop-Process -Force
Start-Sleep -Seconds 2
Write-Host "All Python processes killed"
