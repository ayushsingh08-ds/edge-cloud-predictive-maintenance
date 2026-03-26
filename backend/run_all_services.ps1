param(
    [ValidateSet("normal", "degrading", "failing")]
    [string]$Mode = "normal"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

function Test-PythonCandidate {
    param([string]$PythonCmd)

    try {
        # Use cmd.exe so stderr logs from native libraries (e.g., TensorFlow) don't
        # get treated as PowerShell errors under strict error preferences.
        $probe = "`"$PythonCmd`" -c `"import numpy, pika, sklearn, tensorflow`" >nul 2>nul"
        & cmd.exe /c $probe
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

$pathPythonCandidates = @()
try {
    $pathPythonCandidates = Get-Command python -All -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty Source -Unique
} catch {
    $pathPythonCandidates = @()
}

$pythonCandidates = @(
    (Join-Path $ProjectRoot ".venv\Scripts\python.exe"),
    (Join-Path $ProjectRoot ".venv\bin\python.exe")
) + $pathPythonCandidates

# Remove empty and duplicate entries while preserving order.
$seenCandidates = @{}
$pythonCandidates = @(
    foreach ($candidate in $pythonCandidates) {
        if (-not [string]::IsNullOrWhiteSpace($candidate) -and -not $seenCandidates.ContainsKey($candidate)) {
            $seenCandidates[$candidate] = $true
            $candidate
        }
    }
)

$PythonExe = $null
$testedCandidates = @()
foreach ($candidate in $pythonCandidates) {
    if (Test-Path $candidate) {
        $isValid = Test-PythonCandidate -PythonCmd $candidate
        $testedCandidates += "${candidate} => ${isValid}"
        if ($isValid) {
            $PythonExe = $candidate
            break
        }
    }
}

if (-not $PythonExe) {
    $details = $testedCandidates -join "; "
    if ([string]::IsNullOrWhiteSpace($details)) {
        $details = "No python candidates were discovered from PATH"
    }
    Write-Error "Could not find a working Python interpreter with numpy, pika, sklearn, tensorflow. Probe results: $details"
}

Write-Host "Using Python interpreter: $PythonExe"
& $PythonExe -c "import sys; print('Python executable:', sys.executable); print('Python version:', sys.version.split()[0])"

function Start-ServiceTerminal {
    param(
        [string]$Title,
        [string]$RunCommand
    )

    $psCommand = "`$Host.UI.RawUI.WindowTitle = '$Title'; Set-Location '$ProjectRoot'; $RunCommand"

    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-Command", $psCommand
    )
}

# Best effort: start RabbitMQ container if it exists, then fallback to compose service.
$rabbitStarted = $false
try {
    docker start rabbitmq | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $rabbitStarted = $true
        Write-Host "RabbitMQ container started: rabbitmq"
    }
} catch {
    $composeFile = Join-Path (Split-Path -Parent $ProjectRoot) "docker\docker-compose.yml"
    if (Test-Path $composeFile) {
        try {
            docker compose -f $composeFile up -d rabbitmq | Out-Null
            if ($LASTEXITCODE -eq 0) {
                $rabbitStarted = $true
                Write-Host "RabbitMQ started via docker compose service: rabbitmq"
            }
        } catch {
            Write-Host "RabbitMQ startup failed via both docker start and docker compose. Ensure broker is available on localhost:5672"
        }
    } else {
        Write-Host "RabbitMQ container start skipped. Compose file not found and broker must be running on localhost:5672"
    }
}

if (-not $rabbitStarted) {
    $composeFile = Join-Path (Split-Path -Parent $ProjectRoot) "docker\docker-compose.yml"
    if (Test-Path $composeFile) {
        docker compose -f $composeFile up -d rabbitmq | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $rabbitStarted = $true
            Write-Host "RabbitMQ started via docker compose service: rabbitmq"
        } else {
            Write-Host "RabbitMQ is not running. Please start broker manually and verify localhost:5672."
        }
    }
}

function Start-ServiceScript {
    param(
        [string]$Title,
        [string]$ScriptRelativePath,
        [string]$ExtraArgs = ""
    )

    $scriptPath = Join-Path $ProjectRoot $ScriptRelativePath
    if (-not (Test-Path $scriptPath)) {
        Write-Host "Missing service script: $ScriptRelativePath"
        return $false
    }

    # Run service files as modules so top-level package imports (e.g. messaging.*) resolve reliably.
    $moduleName = ($ScriptRelativePath -replace '/', '.' -replace '\\', '.') -replace '\.py$', ''
    $command = "& '$PythonExe' -u -m $moduleName"
    if (-not [string]::IsNullOrWhiteSpace($ExtraArgs)) {
        $command = "$command $ExtraArgs"
    }

    Start-ServiceTerminal -Title $Title -RunCommand $command
    return $true
}

function Start-ServiceModule {
    param(
        [string]$Title,
        [string]$ModuleName
    )

    $modulePath = "$($ModuleName.Replace('.', '\\')).py"
    $moduleFile = Join-Path $ProjectRoot $modulePath
    if (-not (Test-Path $moduleFile)) {
        Write-Host "Missing service module file: $modulePath"
        return $false
    }

    $command = "& '$PythonExe' -u -m $ModuleName"
    Start-ServiceTerminal -Title $Title -RunCommand $command
    return $true
}

$startedServices = 0
if (Start-ServiceScript -Title "Alert Manager" -ScriptRelativePath "services\notification\alert_service\alert_manager.py") { $startedServices++ }
if (Start-ServiceScript -Title "Decision Engine" -ScriptRelativePath "services\predictive_maintenance\decision_engine\decision_engine.py") { $startedServices++ }
if (Start-ServiceScript -Title "Anomaly Detector" -ScriptRelativePath "services\edge\anomaly_detection\anomaly_detector.py") { $startedServices++ }
if (Start-ServiceScript -Title "Data Adapter" -ScriptRelativePath "services\edge\data_adapter\data_adapter.py") { $startedServices++ }
if (Start-ServiceScript -Title "RUL Predictor" -ScriptRelativePath "services\predictive_maintenance\rul_prediction\rul_predictor.py") { $startedServices++ }

# Give consumers a moment before starting producer.
Start-Sleep -Seconds 2
if (Start-ServiceScript -Title "Sensor Simulator" -ScriptRelativePath "services\simulation\sensor_simulator\sensor_simulator.py" -ExtraArgs "--mode $Mode") { $startedServices++ }

if ($startedServices -eq 0) {
    Write-Error "No service launch targets were started. Verify script/module paths in run_all_services.ps1 before retrying."
}

# Start integration test scripts we added for new backend modules.
$testScripts = @(
    @{ Title = "Test - Production Graph"; Script = "test_production_graph.py" },
    @{ Title = "Test - Routing Engine"; Script = "test_routing_engine.py" },
    @{ Title = "Test - Product Simulation"; Script = "test_product_simulation.py" },
    @{ Title = "Test - Digital Twin"; Script = "test_digital_twin.py" },
    @{ Title = "Test - API Gateway"; Script = "test_api.py" },
    @{ Title = "Test - WebSocket"; Script = "test_websocket.py" },
    @{ Title = "Test - Analytics"; Script = "test_analytics.py" }
)

foreach ($test in $testScripts) {
    $scriptPath = Join-Path $ProjectRoot $test.Script
    if (Test-Path $scriptPath) {
        Start-ServiceTerminal -Title $test.Title -RunCommand "& '$PythonExe' -u '$scriptPath'"
    } else {
        Write-Host "Skipping missing test script: $($test.Script)"
    }
}

Write-Host "Started all services in separate PowerShell windows."
Write-Host "Simulator mode: $Mode"
Write-Host "Note: RUL Predictor requires 50 sensor.cleaned samples per machine before first cloud.rul message (about 50 seconds at 1Hz)."
Write-Host "Started integration test windows for: production graph, routing, simulation, digital twin, API, websocket, analytics."
