$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot "lib.ps1")

function Assert-Platform {
    if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
        throw "This entry point is for Windows. On macOS or Linux use ./deploy/bootstrap.sh."
    }
    if (-not [System.Environment]::Is64BitOperatingSystem) {
        throw "A 64-bit operating system is required."
    }
    $architecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
    if ($architecture -notin @("X64", "Arm64")) {
        throw "Unsupported architecture: $architecture. Use 64-bit AMD64 or ARM64."
    }
}

function Add-DockerToPath {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\resources\bin"),
        (Join-Path $env:ProgramFiles "Docker\Docker\resources\bin")
    )
    foreach ($dockerBin in $candidates) {
        if ((Test-Path $dockerBin) -and ($env:Path -notlike "*$dockerBin*")) {
            $env:Path = "$dockerBin;$env:Path"
        }
    }
}

function Start-DockerDesktop {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\Docker Desktop.exe"),
        (Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe")
    )
    $desktop = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $desktop) {
        throw "Docker Desktop is installed but its executable was not found."
    }
    Start-Process $desktop
    Wait-DockerReady
}

function Install-DockerIfNeeded {
    Add-DockerToPath
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $docker) {
        Write-Host "Docker Desktop with Linux containers and Compose is required."
        $architecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
        if ($architecture -eq "Arm64") {
            throw "Install Docker Desktop for Windows Arm (Early Access) from https://docs.docker.com/desktop/setup/install/windows-install/ and rerun this command."
        }
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
            throw "Install Docker Desktop from https://docs.docker.com/desktop/setup/install/windows-install/ and rerun this command."
        }
        if (-not (Read-Yes "Install Docker Desktop with winget now?")) {
            throw "Docker installation declined."
        }
        & winget install --id Docker.DockerDesktop --exact --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) {
            throw "winget could not install Docker Desktop."
        }
        Add-DockerToPath
    }
    & docker compose version *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "The Docker Compose plugin is required."
    }
    if (-not (Test-DockerReady)) {
        Write-Host "Starting Docker Desktop..."
        Start-DockerDesktop
    }
}

function Read-PlainPassword {
    $secure = Read-Host "Bring password" -AsSecureString
    $pointer = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function Configure-Environment {
    Write-Host "Bring credentials are written only to a user-restricted .env file."
    $email = Read-Host "Bring email"
    $password = Read-PlainPassword
    if ([string]::IsNullOrWhiteSpace($email) -or [string]::IsNullOrEmpty($password)) {
        throw "Email and password are required."
    }
    $hostname = Read-Host "Tailscale device name [bring-shopping]"
    if ([string]::IsNullOrWhiteSpace($hostname)) {
        $hostname = "bring-shopping"
    }
    if ($hostname -notmatch '^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$') {
        throw "Invalid Tailscale device name."
    }
    Set-EnvValue "BRING_EMAIL" $email
    Set-EnvValue "BRING_PASSWORD" $password
    Set-EnvValue "BRING_REQUEST_TIMEOUT_SECONDS" "20"
    Set-EnvValue "MCP_CAPABILITY" (New-Capability)
    Set-EnvValue "MCP_HTTP_MAX_BODY_BYTES" "1048576"
    Set-EnvValue "MCP_HTTP_RATE_PER_MINUTE" "120"
    Set-EnvValue "MCP_HTTP_RATE_BURST" "30"
    Set-EnvValue "MCP_HTTP_MAX_CONCURRENCY" "4"
    Set-EnvValue "TAILSCALE_HOSTNAME" $hostname
    Set-EnvValue "BRING_SHOPPING_IMAGE" "$($Script:ImageRepository):1.1.0"
    $password = $null
}

function Prepare-Image {
    & docker compose --project-directory $Script:ProjectDir pull app
    if ($LASTEXITCODE -eq 0) {
        return
    }
    Write-Host "The published image could not be pulled."
    if (-not (Read-Yes "Build the same image locally from this clone?")) {
        throw "No application image is available."
    }
    Invoke-DockerCompose -ComposeArgs @("build", "app")
}

function Connect-Tailscale {
    Invoke-DockerCompose -ComposeArgs @("up", "-d", "tailscale")
    & docker compose --project-directory $Script:ProjectDir exec -T tailscale tailscale ip -4 *> $null
    if ($LASTEXITCODE -eq 0) {
        return
    }
    Write-Host "Open the one-time URL shown below and approve this device."
    Invoke-DockerCompose -ComposeArgs @("exec", "tailscale", "tailscale", "login", "--timeout=10m")
}

function Select-BringList {
    $lines = @(& docker compose --project-directory $Script:ProjectDir run --rm --no-deps app bring-shopping lists)
    if ($LASTEXITCODE -ne 0) {
        throw "Bring authentication or list discovery failed."
    }
    $lines = @($lines | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($lines.Count -eq 0) {
        throw "No Bring shopping lists are available to this account."
    }
    Write-Host ""
    Write-Host "Available Bring lists (name, UUID):"
    $lines | ForEach-Object { Write-Host "  $_" }
    if ($lines.Count -eq 1) {
        $selected = ($lines[0] -split "`t")[-1]
        if (-not (Read-Yes "Use this list UUID ($selected)?")) {
            throw "List selection cancelled."
        }
    }
    else {
        $selected = Read-Host "Enter the exact UUID to use"
        $matches = @($lines | Where-Object { ($_ -split "`t")[-1] -eq $selected })
        if ($matches.Count -ne 1) {
            throw "That UUID was not listed exactly once."
        }
    }
    Set-EnvValue "BRING_LIST_UUID" $selected
}

function Start-AndExpose {
    Invoke-DockerCompose -ComposeArgs @("up", "-d", "app")
    Invoke-PrivateSmoke
    Write-Host "Enabling the public HTTPS Funnel. Tailscale may show one approval URL."
    Invoke-DockerCompose -ComposeArgs @("exec", "tailscale", "tailscale", "funnel", "--bg", "http://127.0.0.1:8000")
    Write-ClientUrl (Get-Capability)
}

Assert-Platform
Install-DockerIfNeeded
Configure-Environment
Prepare-Image
Connect-Tailscale
Select-BringList
Start-AndExpose
Write-Host ""
Write-Host "Setup complete. Follow docs\deployment.md to connect an MCP client."
