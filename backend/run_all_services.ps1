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

# Best effort: start RabbitMQ container if it exists.
try {
    docker start rabbitmq-cloud | Out-Null
} catch {
    Write-Host "RabbitMQ container start skipped. Ensure broker is running on localhost:5672"
}

Start-ServiceTerminal -Title "Alert Manager" -RunCommand "& '$PythonExe' -u '$ProjectRoot\scripts\run_alert_manager.py'"
Start-ServiceTerminal -Title "Decision Engine" -RunCommand "& '$PythonExe' -u '$ProjectRoot\scripts\run_decision_engine.py'"
Start-ServiceTerminal -Title "Anomaly Detector" -RunCommand "& '$PythonExe' -u -m services.edge.anomaly_detection.anomaly_detector"
Start-ServiceTerminal -Title "Data Adapter" -RunCommand "& '$PythonExe' -u '$ProjectRoot\scripts\run_adapter.py'"
Start-ServiceTerminal -Title "RUL Predictor" -RunCommand "& '$PythonExe' -u '$ProjectRoot\scripts\run_rul_predictor.py'"

# Give consumers a moment before starting producer.
Start-Sleep -Seconds 2
Start-ServiceTerminal -Title "Sensor Simulator" -RunCommand "& '$PythonExe' -u '$ProjectRoot\scripts\run_sensor_simulator.py' --mode $Mode"

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
