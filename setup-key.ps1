$ErrorActionPreference = 'Stop'
$key = Read-Host 'Cargonizer API key' -AsSecureString
if ($key.Length -eq 0) { throw 'API key is empty' }
$key | ConvertFrom-SecureString | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'api-key.dpapi')
Write-Host 'Saved for this Windows user on this PC. Do not share api-key.dpapi.'
