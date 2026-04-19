param(
    [switch]$Clean,      # Remove volumes on teardown (-v)
    [switch]$NoScanner,  # Skip scanner + kali (useful when AWS creds are unavailable)
    [switch]$Build       # Force image rebuild (--build)
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$compose = "docker-compose.dev.yml"

# --- Dev defaults (mirror docker_runner.sh; real secrets must come from the shell env) ---
$defaults = @{
    POSTGRES_DB                = "raptor"
    POSTGRES_USER              = "raptor"
    POSTGRES_PASSWORD          = "raptor"
    DATABASE_URL               = "postgresql://raptor:raptor@postgres:5432/raptor"
    DATA_PATH                  = "/appdata/data"
    BACKUP_FOLDER              = "/appdata/backups"
    SHARED_PATH                = "/usr/app/src/shared"
    APP_PORT                   = "5000"
    MCP_SERVER_TOKEN           = "raptor-mcp-dev-token"
    RAPTOR_SERVICE_API_KEY     = "raptor-mcp-dev-service-key"
    RAPTOR_API_BASE_URL        = "http://app:5000"
    MCP_PORT                   = "8081"
    RAPTOR_API_TIMEOUT_SECONDS = "30"
    SCANNER_INTERNAL_TOKEN     = "raptor-scanner-dev-token"
}

foreach ($kv in $defaults.GetEnumerator()) {
    if (-not [System.Environment]::GetEnvironmentVariable($kv.Key)) {
        [System.Environment]::SetEnvironmentVariable($kv.Key, $kv.Value, "Process")
    }
}

# Warn early if AWS creds are absent and scanner is requested
if (-not $NoScanner -and -not $env:AWS_BEARER_TOKEN_BEDROCK) {
    Write-Warning "AWS_BEARER_TOKEN_BEDROCK is not set — scanner container will fail to start."
    Write-Warning "Set it in your shell or re-run with -NoScanner to skip scanner + kali."
}

$services = @("postgres", "ftp", "sftp", "app", "mcp")
if (-not $NoScanner) {
    $services += @("kali", "scanner")
}

Push-Location $root
try {
    # Tear down
    $downArgs = @("-f", $compose, "down", "--remove-orphans")
    if ($Clean) { $downArgs += "-v" }
    docker compose @downArgs

    # Build + start
    $upArgs = @("-f", $compose, "up", "-d")
    if ($Build) { $upArgs += "--build" }
    $upArgs += $services
    docker compose @upArgs

    # Seed SFTP zone files
    $sharedSrc = Join-Path $root "backend" "appdata" "shared"
    $primaryZone = Join-Path $sharedSrc "example.com_A_Records"
    $secondaryZone = Join-Path $sharedSrc "example1.com_A_Records"

    if (Test-Path $primaryZone) {
        docker cp $primaryZone "raptor-sftp-dev:/chroot/upload/example.com_A_Records"

        if (Test-Path $secondaryZone) {
            docker cp $secondaryZone "raptor-sftp-dev:/chroot/upload/example1.com_A_Records"
        } else {
            $zoneContent = (Get-Content $primaryZone -Raw) -replace "example\.com", "example1.com"
            $zoneContent | docker exec -i raptor-sftp-dev sh -c "cat > /chroot/upload/example1.com_A_Records"
        }

        docker exec raptor-sftp-dev sh -c `
            "chown sftpuser:sftpusers /chroot/upload/example.com_A_Records /chroot/upload/example1.com_A_Records && chmod 644 /chroot/upload/example.com_A_Records /chroot/upload/example1.com_A_Records"
    } else {
        Write-Warning "Zone file not found at $primaryZone — skipping SFTP seed."
    }

    Write-Host ""
    Write-Host "RAPTOR dev stack is up."
    Write-Host "  App:     http://localhost:1337"
    Write-Host "  MCP:     http://localhost:$($env:MCP_PORT)"
    if (-not $NoScanner) {
        Write-Host "  Scanner: http://localhost:8082  (internal)"
    }
} finally {
    Pop-Location
}
