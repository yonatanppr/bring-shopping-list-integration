$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot "lib.ps1")

Assert-Deployment
$newCapability = New-Capability
Set-EnvValue "MCP_CAPABILITY" $newCapability
Invoke-DockerCompose -ComposeArgs @("up", "-d", "--force-recreate", "app")
Invoke-PrivateSmoke
Write-Host "The old MCP URL is invalid. Reconfigure ChatGPT immediately:"
Write-ChatGptSteps $newCapability
