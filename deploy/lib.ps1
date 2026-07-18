$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Script:DeployDir = $PSScriptRoot
$Script:ProjectDir = Split-Path -Parent $Script:DeployDir
$Script:EnvFile = Join-Path $Script:ProjectDir ".env"
$Script:ImageRepository = "ghcr.io/yonatanppr/bring-shopping-list-integration"

function Invoke-DockerCompose {
    param([string[]]$ComposeArgs)

    & docker compose --project-directory $Script:ProjectDir @ComposeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose failed with exit code $LASTEXITCODE."
    }
}

function Test-DockerReady {
    & docker info *> $null
    return $LASTEXITCODE -eq 0
}

function Wait-DockerReady {
    for ($attempt = 0; $attempt -lt 90; $attempt++) {
        if (Test-DockerReady) {
            return
        }
        Start-Sleep -Seconds 2
    }
    throw "Docker Desktop did not become ready within three minutes."
}

function Read-Yes {
    param([string]$Prompt)

    $answer = Read-Host "$Prompt [y/N]"
    return $answer -eq "y" -or $answer -eq "Y"
}

function Protect-EnvFile {
    if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
        return
    }
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $acl = Get-Acl $Script:EnvFile
    $acl.SetAccessRuleProtection($true, $false)
    $rule = [System.Security.AccessControl.FileSystemAccessRule]::new(
        $identity,
        "FullControl",
        "Allow"
    )
    $acl.SetAccessRule($rule)
    Set-Acl -Path $Script:EnvFile -AclObject $acl
}

function Set-EnvValue {
    param(
        [string]$Name,
        [string]$Value
    )

    $temporary = "$($Script:EnvFile).tmp.$PID"
    $lines = @()
    if (Test-Path $Script:EnvFile) {
        $lines = @([System.IO.File]::ReadAllLines($Script:EnvFile) | Where-Object {
            -not $_.StartsWith("$Name=")
        })
    }
    $escaped = $Value.Replace("\", "\\").Replace("'", "\'")
    $lines += "$Name='$escaped'"
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText(
        $temporary,
        (($lines -join [Environment]::NewLine) + [Environment]::NewLine),
        $encoding
    )
    Move-Item -Force $temporary $Script:EnvFile
    Protect-EnvFile
}

function New-Capability {
    $bytes = New-Object byte[] 32
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    }
    finally {
        $generator.Dispose()
    }
    return -join ($bytes | ForEach-Object { $_.ToString("x2") })
}

function Get-Capability {
    if (-not (Test-Path $Script:EnvFile)) {
        throw "MCP capability is missing: .env does not exist."
    }
    foreach ($line in [System.IO.File]::ReadAllLines($Script:EnvFile)) {
        if ($line -match "^MCP_CAPABILITY='([0-9a-f]{64})'$") {
            return $Matches[1]
        }
    }
    throw "MCP capability is missing or invalid."
}

function Get-PublicBaseUrl {
    $output = @(& docker compose --project-directory $Script:ProjectDir exec -T tailscale tailscale funnel status 2>$null)
    if ($LASTEXITCODE -ne 0) {
        return $null
    }
    foreach ($line in $output) {
        if ($line -match '(https://[^\s]+)') {
            return $Matches[1].TrimEnd('/')
        }
    }
    return $null
}

function Invoke-PrivateSmoke {
    $output = @(& docker compose --project-directory $Script:ProjectDir exec -T app bring-shopping-mcp-smoke 2>$null)
    if ($LASTEXITCODE -ne 0) {
        throw "Private MCP initialization failed. Check the app container logs."
    }
    $output | ForEach-Object { Write-Host $_ }
}

function Write-ChatGptSteps {
    param([string]$Capability)

    $baseUrl = Get-PublicBaseUrl
    if (-not $baseUrl) {
        Write-Host "Funnel has no public URL yet."
        Write-Host "Run: docker compose exec tailscale tailscale funnel --bg http://127.0.0.1:8000"
        Write-Host "Then rerun deploy\status.cmd."
        return
    }
    Write-Host ""
    Write-Host "ChatGPT setup (developer mode):"
    Write-Host "  1. Settings -> Apps & Connectors -> Create."
    Write-Host "  2. Use this MCP server URL: $baseUrl/$Capability/mcp"
    Write-Host "  3. Choose No Authentication. The unguessable URL is the credential."
    Write-Host "  4. Never paste or publish that URL anywhere else."
}

function Assert-Deployment {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue) -or -not (Test-DockerReady)) {
        throw "Docker is not running. Start Docker Desktop first."
    }
    if (-not (Test-Path $Script:EnvFile)) {
        throw "Setup is incomplete: .env is missing. Run deploy\bootstrap.cmd first."
    }
    $services = @(& docker compose --project-directory $Script:ProjectDir ps --status running --services)
    if ($LASTEXITCODE -ne 0 -or $services -notcontains "app") {
        throw "Setup is incomplete: the app service is not running. Run deploy\bootstrap.cmd."
    }
}
