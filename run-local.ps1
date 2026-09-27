<#
.SYNOPSIS
Starts the complete SA Job Orchestrator stack for local development.

.DESCRIPTION
Native mode starts Redis (when a local server or Docker is available), applies
Alembic migrations, and launches the FastAPI API, Arq worker, and Vite frontend.
Docker mode starts the equivalent Docker Compose development stack.

The script stays attached so Ctrl+C shuts down only the processes/containers it
started. Runtime logs are written under .local-run/logs.

.EXAMPLE
.\run-local.ps1

.EXAMPLE
.\run-local.ps1 -Mode Docker

.EXAMPLE
.\run-local.ps1 -CheckOnly
#>

[CmdletBinding()]
param(
    [ValidateSet("Native", "Docker")]
    [string]$Mode = "Native",

    [switch]$CheckOnly,

    [switch]$SkipInstall,

    [switch]$InstallBrowser
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendRoot = Join-Path $repoRoot "backend"
$frontendRoot = Join-Path $repoRoot "frontend"
$runtimeRoot = Join-Path $repoRoot ".local-run"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logRoot = Join-Path $runtimeRoot "logs\$timestamp"
$ownedProcesses = [System.Collections.Generic.List[object]]::new()
$ownedRedisContainer = $null

function Write-Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Write-Good([string]$Message) {
    Write-Host "  OK  $Message" -ForegroundColor Green
}

function Write-Problem([string]$Message) {
    Write-Host "  !!  $Message" -ForegroundColor Yellow
}

function Ensure-EnvironmentFile([string]$Target, [string]$Fallback = "") {
    if (Test-Path -LiteralPath $Target) {
        return
    }

    $source = if ($Fallback -and (Test-Path -LiteralPath $Fallback)) {
        $Fallback
    } else {
        Join-Path $repoRoot ".env.example"
    }
    Copy-Item -LiteralPath $source -Destination $Target
    Write-Problem "Created $Target from $(Split-Path -Leaf $source). Add provider credentials if needed."
}

function Test-TcpPort([string]$Address, [int]$Port, [int]$TimeoutMs = 600) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $attempt = $client.BeginConnect($Address, $Port, $null, $null)
        if (-not $attempt.AsyncWaitHandle.WaitOne($TimeoutMs)) {
            return $false
        }
        $client.EndConnect($attempt)
        return $true
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Test-RedisServer {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $attempt = $client.BeginConnect("127.0.0.1", 6379, $null, $null)
        if (-not $attempt.AsyncWaitHandle.WaitOne(700)) {
            return $false
        }
        $client.EndConnect($attempt)
        $stream = $client.GetStream()
        $stream.ReadTimeout = 700
        $payload = [System.Text.Encoding]::ASCII.GetBytes("*1`r`n`$4`r`nPING`r`n")
        $stream.Write($payload, 0, $payload.Length)
        $buffer = New-Object byte[] 64
        $length = $stream.Read($buffer, 0, $buffer.Length)
        $response = [System.Text.Encoding]::ASCII.GetString($buffer, 0, $length)
        return $response.StartsWith("+PONG")
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Wait-Http([string]$Name, [string]$Uri, [int]$TimeoutSeconds = 90) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
                Write-Good "$Name is ready at $Uri"
                return
            }
        } catch {
            Start-Sleep -Milliseconds 750
        }
    } while ((Get-Date) -lt $deadline)

    throw "$Name did not become ready at $Uri within $TimeoutSeconds seconds."
}

function Invoke-Checked([string]$FilePath, [string[]]$Arguments, [string]$WorkingDirectory) {
    Push-Location $WorkingDirectory
    try {
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "$FilePath exited with code $LASTEXITCODE."
        }
    } finally {
        Pop-Location
    }
}

function Test-PythonRuntime([string]$FilePath, [string[]]$PrefixArguments) {
    if (-not (Test-Path -LiteralPath $FilePath) -and -not (Get-Command $FilePath -ErrorAction SilentlyContinue)) {
        return $false
    }
    try {
        & $FilePath @PrefixArguments -c "import fastapi, sqlalchemy, arq, alembic" 2>$null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Resolve-PythonRuntime {
    $candidates = @(
        @{ File = (Join-Path $backendRoot ".venv\Scripts\python.exe"); Prefix = @() },
        @{ File = (Join-Path $runtimeRoot "venv\Scripts\python.exe"); Prefix = @() }
    )

    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $candidates += @{ File = $pythonCommand.Source; Prefix = @() }
    }
    $pyCommand = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($pyCommand) {
        $candidates += @{ File = $pyCommand.Source; Prefix = @("-3") }
    }

    foreach ($candidate in $candidates) {
        if (Test-PythonRuntime $candidate.File $candidate.Prefix) {
            return $candidate
        }
    }

    if ($CheckOnly -or $SkipInstall) {
        return $null
    }

    $bootstrap = if ($pyCommand) {
        @{ File = $pyCommand.Source; Prefix = @("-3") }
    } elseif ($pythonCommand) {
        @{ File = $pythonCommand.Source; Prefix = @() }
    } else {
        throw "Python 3.11 or newer is required. Install Python, then rerun this script."
    }

    $venvRoot = Join-Path $runtimeRoot "venv"
    $venvPython = Join-Path $venvRoot "Scripts\python.exe"
    Write-Step "Creating the local Python runtime"
    New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
    if (-not (Test-Path -LiteralPath $venvPython)) {
        Invoke-Checked $bootstrap.File ($bootstrap.Prefix + @("-m", "venv", $venvRoot)) $repoRoot
    }
    Invoke-Checked $venvPython @("-m", "pip", "install", "--upgrade", "pip") $backendRoot
    Invoke-Checked $venvPython @("-m", "pip", "install", "-e", ".[dev]") $backendRoot

    if (-not (Test-PythonRuntime $venvPython @())) {
        throw "The Python runtime was created, but required backend imports still fail."
    }
    return @{ File = $venvPython; Prefix = @() }
}

function Start-LoggedProcess(
    [string]$Name,
    [string]$FilePath,
    [string[]]$Arguments,
    [string]$WorkingDirectory
) {
    New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
    $stdout = Join-Path $logRoot "$Name.out.log"
    $stderr = Join-Path $logRoot "$Name.err.log"
    $startParameters = @{
        FilePath = $FilePath
        ArgumentList = $Arguments
        WorkingDirectory = $WorkingDirectory
        WindowStyle = "Hidden"
        RedirectStandardOutput = $stdout
        RedirectStandardError = $stderr
        PassThru = $true
    }
    $process = Start-Process @startParameters
    $ownedProcesses.Add([pscustomobject]@{
        Name = $Name
        Process = $process
        Stdout = $stdout
        Stderr = $stderr
    })
    Write-Good "Started $Name (PID $($process.Id))"
    return $process
}

function Assert-ProcessRunning([object]$Entry) {
    if ($Entry.Process.HasExited) {
        $tail = ""
        if (Test-Path -LiteralPath $Entry.Stderr) {
            $tail = (Get-Content -LiteralPath $Entry.Stderr -Tail 20) -join "`n"
        }
        throw "$($Entry.Name) exited early with code $($Entry.Process.ExitCode).`n$tail"
    }
}

function Stop-OwnedProcesses {
    $taskkill = Get-Command taskkill.exe -ErrorAction SilentlyContinue
    for ($index = $ownedProcesses.Count - 1; $index -ge 0; $index--) {
        $entry = $ownedProcesses[$index]
        if (-not $entry.Process.HasExited) {
            if ($taskkill) {
                & $taskkill.Source /PID $entry.Process.Id /T /F 2>$null | Out-Null
            } else {
                Stop-Process -Id $entry.Process.Id -Force -ErrorAction SilentlyContinue
            }
            try { $entry.Process.WaitForExit(5000) } catch { }
        }
    }
}

function Start-LocalRedis {
    if (Test-RedisServer) {
        Write-Good "Using Redis already listening on 127.0.0.1:6379"
        return
    }

    $redis = Get-Command redis-server.exe -ErrorAction SilentlyContinue
    if (-not $redis) {
        $redis = Get-Command redis-server -ErrorAction SilentlyContinue
    }
    if (-not $redis) {
        $redis = Get-Command valkey-server -ErrorAction SilentlyContinue
    }
    if ($redis) {
        Start-LoggedProcess "redis" $redis.Source @("--port", "6379") $repoRoot | Out-Null
        $deadline = (Get-Date).AddSeconds(15)
        while ((Get-Date) -lt $deadline -and -not (Test-RedisServer)) {
            Start-Sleep -Milliseconds 500
        }
        if (-not (Test-RedisServer)) {
            throw "The local Redis process started but port 6379 never became ready."
        }
        return
    }

    $docker = Get-Command docker.exe -ErrorAction SilentlyContinue
    if ($docker) {
        $script:ownedRedisContainer = "sa-job-orchestrator-redis-$PID"
        Invoke-Checked $docker.Source @(
            "run", "--rm", "--detach", "--name", $script:ownedRedisContainer,
            "-p", "6379:6379", "redis:7-alpine"
        ) $repoRoot
        $deadline = (Get-Date).AddSeconds(30)
        while ((Get-Date) -lt $deadline -and -not (Test-RedisServer)) {
            Start-Sleep -Milliseconds 500
        }
        if (-not (Test-RedisServer)) {
            throw "The Redis container started but port 6379 never became ready."
        }
        Write-Good "Started Redis container $script:ownedRedisContainer"
        return
    }

    throw @"
Redis is required by the Arq worker but no server is running on port 6379.
Install one of these, then rerun:
  - Docker Desktop (the script will start redis:7-alpine automatically)
  - Memurai/Redis for Windows exposing redis-server.exe
  - Valkey exposing valkey-server
"@
}

function Stop-OwnedRedisContainer {
    if ($script:ownedRedisContainer) {
        $docker = Get-Command docker.exe -ErrorAction SilentlyContinue
        if ($docker) {
            & $docker.Source stop $script:ownedRedisContainer 2>$null | Out-Null
        }
    }
}

function Invoke-Doctor {
    Write-Step "Checking local prerequisites"
    $failed = $false

    $python = Resolve-PythonRuntime
    if ($python) {
        Write-Good "Backend Python dependencies are available"
    } else {
        Write-Problem "Backend dependencies are missing. Run without -CheckOnly to bootstrap them."
        $failed = $true
    }

    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($npm) {
        Write-Good "Node/npm is available"
    } else {
        Write-Problem "npm.cmd was not found. Install Node.js 20 or newer."
        $failed = $true
    }

    if (Test-Path -LiteralPath (Join-Path $frontendRoot "node_modules")) {
        Write-Good "Frontend dependencies are installed"
    } else {
        Write-Problem "Frontend dependencies are missing. A normal run will install them."
    }

    if (Test-RedisServer) {
        Write-Good "Redis is reachable on port 6379"
    } elseif ((Get-Command redis-server -ErrorAction SilentlyContinue) -or
              (Get-Command valkey-server -ErrorAction SilentlyContinue) -or
              (Get-Command docker.exe -ErrorAction SilentlyContinue)) {
        Write-Good "A Redis-compatible launcher is available"
    } else {
        Write-Problem "No Redis server or Docker installation was found."
        $failed = $true
    }

    if ($failed) {
        throw "Local prerequisite check failed."
    }
}

function Invoke-NativeStack {
    if ($CheckOnly) {
        Invoke-Doctor
        return
    }

    Ensure-EnvironmentFile (Join-Path $backendRoot ".env") (Join-Path $repoRoot ".env")

    $python = Resolve-PythonRuntime
    if (-not $python) {
        throw "No working backend Python runtime is available."
    }
    if ($InstallBrowser) {
        Write-Step "Installing Playwright Chromium"
        Invoke-Checked $python.File ($python.Prefix + @(
            "-m", "playwright", "install", "chromium"
        )) $backendRoot
    }

    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $npm) {
        throw "Node.js/npm is required. Install Node.js 20 or newer."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $frontendRoot "node_modules"))) {
        if ($SkipInstall) {
            throw "frontend/node_modules is missing and -SkipInstall was supplied."
        }
        Write-Step "Installing frontend dependencies"
        $installCommand = if (Test-Path -LiteralPath (Join-Path $frontendRoot "package-lock.json")) {
            "ci"
        } else {
            "install"
        }
        Invoke-Checked $npm.Source @($installCommand) $frontendRoot
    }

    Write-Step "Starting Redis"
    Start-LocalRedis

    Write-Step "Applying database migrations"
    Invoke-Checked $python.File ($python.Prefix + @("-m", "alembic", "upgrade", "head")) $backendRoot

    if (Test-TcpPort "127.0.0.1" 8000) {
        throw "Port 8000 is already in use. Stop the existing API before running this launcher."
    }
    if (Test-TcpPort "127.0.0.1" 3000) {
        throw "Port 3000 is already in use. Stop the existing frontend before running this launcher."
    }

    Write-Step "Starting backend, worker, and frontend"
    Start-LoggedProcess "backend" $python.File ($python.Prefix + @(
        "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"
    )) $backendRoot | Out-Null
    Start-LoggedProcess "worker" $python.File ($python.Prefix + @(
        "-m", "arq", "app.workers.tasks.WorkerSettings"
    )) $backendRoot | Out-Null
    Start-LoggedProcess "frontend" $npm.Source @(
        "run", "dev", "--", "--host", "127.0.0.1"
    ) $frontendRoot | Out-Null

    Start-Sleep -Seconds 2
    foreach ($entry in $ownedProcesses) {
        Assert-ProcessRunning $entry
    }
    Wait-Http "Backend" "http://127.0.0.1:8000/health"
    Wait-Http "Frontend" "http://127.0.0.1:3000"

    Write-Host ""
    Write-Host "SA Job Orchestrator is running" -ForegroundColor Green
    Write-Host "  App:      http://127.0.0.1:3000"
    Write-Host "  API docs: http://127.0.0.1:8000/docs"
    Write-Host "  Health:   http://127.0.0.1:8000/health"
    Write-Host "  Logs:     $logRoot"
    Write-Host "  Press Ctrl+C to stop the complete local stack."

    while ($true) {
        foreach ($entry in $ownedProcesses) {
            Assert-ProcessRunning $entry
        }
        Start-Sleep -Seconds 2
    }
}

function Invoke-DockerStack {
    $docker = Get-Command docker.exe -ErrorAction SilentlyContinue
    if (-not $docker) {
        throw "Docker Desktop is required for -Mode Docker but docker.exe was not found."
    }
    $compose = @(
        "compose",
        "-f", (Join-Path $repoRoot "docker-compose.yml"),
        "-f", (Join-Path $repoRoot "docker-compose.dev.yml")
    )

    if ($CheckOnly) {
        if (-not (Test-Path -LiteralPath (Join-Path $repoRoot ".env"))) {
            throw ".env is missing. A normal run will create it from .env.example."
        }
        Invoke-Checked $docker.Source ($compose + @("config", "--quiet")) $repoRoot
        Write-Good "Docker Compose configuration is valid"
        return
    }

    Ensure-EnvironmentFile (Join-Path $repoRoot ".env")

    Write-Step "Building the Docker development stack"
    Invoke-Checked $docker.Source ($compose + @("build")) $repoRoot
    Invoke-Checked $docker.Source ($compose + @("up", "-d", "redis")) $repoRoot

    Write-Step "Applying database migrations"
    Invoke-Checked $docker.Source ($compose + @(
        "run", "--rm", "backend", "alembic", "upgrade", "head"
    )) $repoRoot

    Write-Step "Starting backend, worker, and frontend"
    Invoke-Checked $docker.Source ($compose + @("up", "-d", "backend", "worker", "frontend")) $repoRoot
    Wait-Http "Backend" "http://127.0.0.1:8000/health" 120
    Wait-Http "Frontend" "http://127.0.0.1:3000" 120

    Write-Host ""
    Write-Host "SA Job Orchestrator is running in Docker" -ForegroundColor Green
    Write-Host "  App:      http://127.0.0.1:3000"
    Write-Host "  API docs: http://127.0.0.1:8000/docs"
    Write-Host "  Press Ctrl+C to stop the complete stack."
    $logArguments = $compose + @("logs", "--follow")
    & $docker.Source @logArguments
}

try {
    Set-Location $repoRoot
    if ($Mode -eq "Docker") {
        Invoke-DockerStack
    } else {
        Invoke-NativeStack
    }
} catch {
    Write-Host "`nLocal stack failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    if ($Mode -eq "Docker" -and -not $CheckOnly) {
        $docker = Get-Command docker.exe -ErrorAction SilentlyContinue
        if ($docker) {
            $compose = @(
                "compose",
                "-f", (Join-Path $repoRoot "docker-compose.yml"),
                "-f", (Join-Path $repoRoot "docker-compose.dev.yml")
            )
            $downArguments = $compose + @("down")
            & $docker.Source @downArguments 2>$null | Out-Null
        }
    } else {
        Stop-OwnedProcesses
        Stop-OwnedRedisContainer
    }
}
