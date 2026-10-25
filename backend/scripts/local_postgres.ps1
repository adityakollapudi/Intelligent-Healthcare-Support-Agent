<#
.SYNOPSIS
    Runs a private, development-only PostgreSQL cluster for IHSA without Docker.

.DESCRIPTION
    Uses an existing PostgreSQL installation's binaries to create a separate cluster in
    backend/.local/pgdata, listening only on 127.0.0.1:<Port> with "trust" authentication.
    It never touches other PostgreSQL services on this machine.
    Trust authentication is acceptable ONLY because the cluster is bound to localhost and
    holds synthetic data. Do not use this for anything else.

.EXAMPLE
    .\scripts\local_postgres.ps1 init     # create cluster + ihsa_dev and ihsa_test databases
    .\scripts\local_postgres.ps1 start
    .\scripts\local_postgres.ps1 status
    .\scripts\local_postgres.ps1 stop
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("init", "start", "stop", "status")]
    [string]$Command,
    [int]$Port = 55432,
    [string]$PgBin = $env:IHSA_PG_BIN
)

$ErrorActionPreference = "Stop"
$backendDir = Split-Path -Parent $PSScriptRoot
$dataDir = Join-Path $backendDir ".local\pgdata"
$logFile = Join-Path $backendDir ".local\postgres.log"

if (-not $PgBin) {
    $candidate = Get-ChildItem "C:\Program Files\PostgreSQL" -Directory -ErrorAction SilentlyContinue |
        Sort-Object { [int]($_.Name -replace '\D', '') } -Descending |
        ForEach-Object { Join-Path $_.FullName "bin" } |
        Where-Object { Test-Path (Join-Path $_ "initdb.exe") } |
        Select-Object -First 1
    if (-not $candidate) { throw "PostgreSQL binaries not found. Set IHSA_PG_BIN to the folder containing initdb.exe." }
    $PgBin = $candidate
}
$initdb = Join-Path $PgBin "initdb.exe"
$pgctl = Join-Path $PgBin "pg_ctl.exe"
$psql = Join-Path $PgBin "psql.exe"

function Invoke-PgCtl([string[]]$PgArgs) {
    # pg_ctl's server child inherits console handles; piping its output (| Out-Null) would
    # block until the server exits, so start it directly and wait only for pg_ctl itself.
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $pgctl
    $psi.Arguments = ($PgArgs | ForEach-Object { '"' + $_ + '"' }) -join ' '
    $psi.UseShellExecute = $false
    $p = [System.Diagnostics.Process]::Start($psi)
    $p.WaitForExit()
    return $p.ExitCode
}

function Test-Running { (Invoke-PgCtl @("-D", $dataDir, "status")) -eq 0 }

switch ($Command) {
    "init" {
        if (Test-Path (Join-Path $dataDir "PG_VERSION")) {
            Write-Host "Cluster already initialized at $dataDir"
        } else {
            New-Item -ItemType Directory -Force $dataDir | Out-Null
            & $initdb -D $dataDir -U postgres --auth=trust --encoding=UTF8 --locale=C | Out-Null
            Add-Content (Join-Path $dataDir "postgresql.conf") "`nlisten_addresses = '127.0.0.1'`nport = $Port`n"
            Write-Host "Initialized cluster at $dataDir (port $Port)"
        }
        if (-not (Test-Running)) { Invoke-PgCtl @("-D", $dataDir, "-l", $logFile, "-w", "start") | Out-Null }
        foreach ($db in @("ihsa_dev", "ihsa_test")) {
            $exists = & $psql -h 127.0.0.1 -p $Port -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$db'"
            if (-not $exists) { & $psql -h 127.0.0.1 -p $Port -U postgres -c "CREATE DATABASE $db" | Out-Null; Write-Host "Created database $db" }
        }
        Write-Host "Running. DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:$Port/ihsa_dev"
    }
    "start" { if (Test-Running) { Write-Host "Already running" } else { exit (Invoke-PgCtl @("-D", $dataDir, "-l", $logFile, "-w", "start")) } }
    "stop" { exit (Invoke-PgCtl @("-D", $dataDir, "-m", "fast", "-w", "stop")) }
    "status" { exit (Invoke-PgCtl @("-D", $dataDir, "status")) }
}
