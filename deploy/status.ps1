$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot "lib.ps1")

Assert-Deployment
Invoke-DockerCompose -ComposeArgs @("ps")
Invoke-PrivateSmoke
Write-ChatGptSteps (Get-Capability)
