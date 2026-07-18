param([string]$Version)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot "lib.ps1")

Assert-Deployment
$Version = if ($null -eq $Version) { "" } else { $Version }
$Version = $Version.TrimStart("v")
if ($Version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$') {
    throw "Usage: deploy\update.cmd VERSION (for example: 1.1.1)"
}

$backup = [System.IO.Path]::GetTempFileName()
Copy-Item $Script:EnvFile $backup -Force
try {
    Set-EnvValue "BRING_SHOPPING_IMAGE" "$($Script:ImageRepository):$Version"
    Invoke-DockerCompose -ComposeArgs @("pull", "app")
    Invoke-DockerCompose -ComposeArgs @("up", "-d", "--force-recreate", "app")
    Invoke-PrivateSmoke
}
catch {
    Copy-Item $backup $Script:EnvFile -Force
    Protect-EnvFile
    try {
        Invoke-DockerCompose -ComposeArgs @("up", "-d", "--force-recreate", "app")
    }
    catch {
        Write-Warning "Update and automatic rollback both failed."
    }
    throw "Update failed; the prior image configuration was restored."
}
finally {
    Remove-Item $backup -Force -ErrorAction SilentlyContinue
}
Write-Host "Updated successfully to $Version."
