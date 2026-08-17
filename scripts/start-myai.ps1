param(
    [ValidateSet("start", "stop", "restart", "status", "doctor")]
    [string]$Action = "start",
    [string]$MysqlServiceName = "",
    [string]$DbUrl = "jdbc:mysql://localhost:3306/login_demo?useSSL=false&serverTimezone=UTC&characterEncoding=utf8",
    [string]$DbUsername = "root",
    [string]$DbPassword = "",
    [string]$PythonHost = "127.0.0.1",
    [int]$PythonPort = 8000,
    [int]$JavaPort = 8080,
    [string]$EnvFile = "",
    [switch]$SkipMysql,
    [switch]$LocalMode,
    [switch]$NoPause
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$PythonDir = Join-Path $Root "myai-python-agent"
$JavaDir = Join-Path $Root "myai-java-service"
$LogDir = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$PythonPidFile = Join-Path $LogDir "python-service.pid"
$JavaPidFile = Join-Path $LogDir "java-service.pid"

if ($EnvFile.Trim().Length -eq 0) {
    $EnvFile = Join-Path $PSScriptRoot "start-myai.env"
}

function Import-StartupEnv {
    param([string]$Path)
    $values = @{}
    if (-not (Test-Path $Path)) {
        return $values
    }

    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if ($line.Length -gt 0 -and -not $line.StartsWith("#")) {
            $parts = $line.Split("=", 2)
            if ($parts.Count -eq 2) {
                $values[$parts[0].Trim()] = $parts[1].Trim()
            }
        }
    }
    return $values
}

$StartupEnv = Import-StartupEnv -Path $EnvFile

if (-not $PSBoundParameters.ContainsKey("DbUrl")) {
    if ($StartupEnv.ContainsKey("DB_URL")) {
        $DbUrl = $StartupEnv["DB_URL"]
    } elseif ($env:DB_URL) {
        $DbUrl = $env:DB_URL
    }
}
if (-not $PSBoundParameters.ContainsKey("DbUsername")) {
    if ($StartupEnv.ContainsKey("DB_USERNAME")) {
        $DbUsername = $StartupEnv["DB_USERNAME"]
    } elseif ($env:DB_USERNAME) {
        $DbUsername = $env:DB_USERNAME
    }
}
if (-not $PSBoundParameters.ContainsKey("DbPassword")) {
    if ($StartupEnv.ContainsKey("DB_PASSWORD")) {
        $DbPassword = $StartupEnv["DB_PASSWORD"]
    } elseif ($env:DB_PASSWORD) {
        $DbPassword = $env:DB_PASSWORD
    }
}
if (-not $PSBoundParameters.ContainsKey("MysqlServiceName") -and $StartupEnv.ContainsKey("MYSQL_SERVICE_NAME")) {
    $MysqlServiceName = $StartupEnv["MYSQL_SERVICE_NAME"]
}

if ($LocalMode) {
    $DbUrl = "jdbc:sqlite:myai-local.db"
    $DbUsername = ""
    $DbPassword = ""
    $SkipMysql = $true
}

function Test-PortOpen {
    param([string]$HostName, [int]$Port)
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $connect = $client.BeginConnect($HostName, $Port, $null, $null)
        $ok = $connect.AsyncWaitHandle.WaitOne(800, $false)
        if ($ok) {
            $client.EndConnect($connect)
        }
        $client.Close()
        return $ok
    } catch {
        return $false
    }
}

function Resolve-JavaExe {
    $candidates = @()
    if ($env:JAVA_HOME) {
        $candidates += (Join-Path $env:JAVA_HOME "bin\java.exe")
    }
    $candidates += (Join-Path $env:USERPROFILE ".jdks\openjdk-23.0.1\bin\java.exe")
    $candidates += "java"

    foreach ($candidate in $candidates) {
        try {
            $command = Get-Command $candidate -ErrorAction Stop
            $path = $command.Source
            if ($path -match "\\Common Files\\Oracle\\Java\\javapath\\java.exe$" -and $candidates.Count -gt 1) {
                continue
            }
            & $path -version *> $null
            if ($LASTEXITCODE -eq 0) {
                return $path
            }
        } catch {
            continue
        }
    }

    return "java"
}

function Wait-Port {
    param([string]$Name, [string]$HostName, [int]$Port, [int]$TimeoutSeconds = 60)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortOpen -HostName $HostName -Port $Port) {
            Write-Host "$Name is ready on $HostName`:$Port"
            return $true
        }
        Start-Sleep -Seconds 1
    }
    Write-Warning "$Name did not respond on $HostName`:$Port within $TimeoutSeconds seconds."
    return $false
}

function Get-PortProcessIds {
    param([int]$Port)
    $ids = @()
    try {
        $ids = @(Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
            Where-Object { $_.State -eq "Listen" -or $_.State -eq "Established" } |
            Select-Object -ExpandProperty OwningProcess -Unique)
    } catch {
        $ids = @()
    }
    if ($ids.Count -gt 0) {
        return $ids
    }

    try {
        $pattern = "^\s*TCP\s+\S+:$Port\s+\S+\s+(LISTENING|ESTABLISHED)\s+(\d+)\s*$"
        return @(netstat -ano | ForEach-Object {
            if ($_ -match $pattern) {
                [int]$Matches[2]
            }
        } | Select-Object -Unique)
    } catch {
        return @()
    }
}

function Stop-PidFileProcess {
    param([string]$Name, [string]$PidFile)
    if (-not (Test-Path $PidFile)) {
        return
    }

    $pidText = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($pidText -match "^\d+$") {
        $process = Get-Process -Id ([int]$pidText) -ErrorAction SilentlyContinue
        if ($null -ne $process) {
            Write-Host "Stopping tracked $Name process pid: $pidText"
            Stop-Process -Id ([int]$pidText) -Force -ErrorAction SilentlyContinue
        }
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

function Stop-PortProcesses {
    param([string]$Name, [int]$Port)
    for ($attempt = 1; $attempt -le 5; $attempt++) {
        $processIds = Get-PortProcessIds -Port $Port
        if ($processIds.Count -eq 0) {
            Write-Host "$Name port $Port is free."
            return
        }

        foreach ($processId in $processIds) {
            $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
            if ($null -ne $process) {
                Write-Host "Stopping $Name process on port $Port, pid: $processId ($($process.ProcessName))"
                Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            }
        }
        Start-Sleep -Seconds 1
    }

    $remaining = Get-PortProcessIds -Port $Port
    if ($remaining.Count -gt 0) {
        Write-Warning "$Name port $Port is still owned by pid(s): $($remaining -join ', ')"
    }
}

function Show-ServiceStatus {
    Write-Host "Python service port ${PythonPort}: $(if (Test-PortOpen -HostName $PythonHost -Port $PythonPort) { 'running' } else { 'stopped' })"
    Write-Host "Java service port ${JavaPort}: $(if (Test-PortOpen -HostName '127.0.0.1' -Port $JavaPort) { 'running' } else { 'stopped' })"
}

function Write-DiagnosticCheck {
    param(
        [string]$Level,
        [string]$Name,
        [string]$Message,
        [string]$Fix = ""
    )
    $prefix = "OK"
    $color = "Green"
    if ($Level -eq "WARN") {
        $prefix = "WARN"
        $color = "Yellow"
    } elseif ($Level -eq "FAIL") {
        $prefix = "FAIL"
        $color = "Red"
    }
    Write-Host ("[{0}] {1}: {2}" -f $prefix, $Name, $Message) -ForegroundColor $color
    if ($Fix.Trim().Length -gt 0) {
        Write-Host ("      Fix: {0}" -f $Fix)
    }
}

function Test-ExternalCommand {
    param([string]$Command)
    $cmd = Get-Command $Command -ErrorAction SilentlyContinue
    return $null -ne $cmd
}

function Test-DirectoryWritable {
    param([string]$Path)
    try {
        New-Item -ItemType Directory -Force -Path $Path | Out-Null
        $probe = Join-Path $Path ".myai-write-test"
        Set-Content -Path $probe -Value "ok" -Encoding ASCII -Force
        Remove-Item $probe -Force -ErrorAction SilentlyContinue
        return $true
    } catch {
        return $false
    }
}

function Get-EnvValue {
    param([hashtable]$Values, [string]$Name, [string]$Default = "")
    $processValue = [Environment]::GetEnvironmentVariable($Name)
    if ($null -ne $processValue) {
        $trimmed = $processValue.Trim()
        return $(if ($trimmed.Length -gt 0) { $trimmed } else { $Default })
    }
    if ($Values.ContainsKey($Name)) {
        $trimmed = $Values[$Name].Trim()
        return $(if ($trimmed.Length -gt 0) { $trimmed } else { $Default })
    }
    return $Default
}

function Get-EnvBool {
    param([hashtable]$Values, [string]$Name, [bool]$Default)
    $value = Get-EnvValue -Values $Values -Name $Name -Default ""
    if ($value.Trim().Length -eq 0) {
        return $Default
    }
    return $value.Trim().ToLowerInvariant() -in @("1", "true", "yes", "on")
}

function Test-HttpEndpoint {
    param([string]$Value)
    try {
        $uri = [System.Uri]$Value
        return $uri.IsAbsoluteUri -and $uri.Scheme -in @("http", "https") -and $uri.Host.Trim().Length -gt 0
    } catch {
        return $false
    }
}

function Test-LoopbackEndpoint {
    param([string]$Value)
    try {
        $uri = [System.Uri]$Value
        if ($uri.Host.ToLowerInvariant() -eq "localhost") {
            return $true
        }
        $address = $null
        if ([System.Net.IPAddress]::TryParse($uri.Host, [ref]$address)) {
            return [System.Net.IPAddress]::IsLoopback($address)
        }
        return $false
    } catch {
        return $false
    }
}

function Test-FiniteNumberAtLeast {
    param(
        [string]$Value,
        [double]$Minimum,
        [double]$Maximum = [double]::PositiveInfinity
    )
    try {
        $number = [double]::Parse($Value, [System.Globalization.CultureInfo]::InvariantCulture)
        return (-not [double]::IsNaN($number)) -and (-not [double]::IsInfinity($number)) -and $number -ge $Minimum -and $number -le $Maximum
    } catch {
        return $false
    }
}

function Test-IntegerAtLeast {
    param([string]$Value, [int]$Minimum)
    try {
        $number = [int]::Parse($Value, [System.Globalization.CultureInfo]::InvariantCulture)
        return $number -ge $Minimum
    } catch {
        return $false
    }
}

function Invoke-StartupDiagnostics {
    Write-Host "MyAI startup diagnostics"
    Write-Host "Root: $Root"
    Write-Host "Mode: $(if ($LocalMode) { 'LocalMode / SQLite' } else { 'Configured database' })"
    Write-Host ""

    $script:DoctorFailures = 0
    $script:DoctorWarnings = 0
    function Add-Check {
        param([string]$Level, [string]$Name, [string]$Message, [string]$Fix = "")
        Write-DiagnosticCheck -Level $Level -Name $Name -Message $Message -Fix $Fix
        if ($Level -eq "FAIL") {
            $script:DoctorFailures += 1
        } elseif ($Level -eq "WARN") {
            $script:DoctorWarnings += 1
        }
    }

    if (Test-Path $PythonDir) {
        Add-Check "OK" "Python project" $PythonDir
    } else {
        Add-Check "FAIL" "Python project" "Directory not found." "Restore myai-python-agent under the project root."
    }

    if (Test-Path $JavaDir) {
        Add-Check "OK" "Java project" $JavaDir
    } else {
        Add-Check "FAIL" "Java project" "Directory not found." "Restore myai-java-service under the project root."
    }

    if (Test-DirectoryWritable -Path $LogDir) {
        Add-Check "OK" "Log directory" "Writable: $LogDir"
    } else {
        Add-Check "FAIL" "Log directory" "Not writable: $LogDir" "Check filesystem permissions."
    }

    if (Test-Path $EnvFile) {
        Add-Check "OK" "Startup env" "Found: $EnvFile"
    } else {
        Add-Check "WARN" "Startup env" "Missing: $EnvFile" "Copy scripts/start-myai.env.example to scripts/start-myai.env if you use MySQL."
    }

    $pythonEnvFile = Join-Path $PythonDir ".env"
    $pythonEnv = Import-StartupEnv -Path $pythonEnvFile
    if (Test-Path $pythonEnvFile) {
        Add-Check "OK" "Python .env" "Found: $pythonEnvFile"
    } else {
        Add-Check "WARN" "Python .env" "Missing: $pythonEnvFile" "Create myai-python-agent/.env when using non-stub LLM or embedding providers."
    }

    $diagnosticPythonExe = Join-Path $PythonDir ".venv\Scripts\python.exe"
    if (Test-Path $diagnosticPythonExe) {
        Add-Check "OK" "Python executable" $diagnosticPythonExe
    } elseif (Test-ExternalCommand -Command "python") {
        $diagnosticPythonExe = "python"
        Add-Check "WARN" "Python executable" "Using python from PATH." "Create .venv for reproducible local startup."
    } else {
        $diagnosticPythonExe = ""
        Add-Check "FAIL" "Python executable" "No .venv python and no python in PATH." "Create myai-python-agent/.venv and install dependencies."
    }

    if ($diagnosticPythonExe.Trim().Length -gt 0) {
        try {
            $version = & $diagnosticPythonExe --version 2>&1
            Add-Check "OK" "Python version" ($version -join " ")
        } catch {
            Add-Check "FAIL" "Python version" "Could not run python." "Check Python installation."
        }
        try {
            & $diagnosticPythonExe -c "import fastapi, uvicorn, dotenv" 2>$null
            if ($LASTEXITCODE -eq 0) {
                Add-Check "OK" "Python dependencies" "fastapi, uvicorn, python-dotenv import successfully."
            } else {
                Add-Check "FAIL" "Python dependencies" "Required imports failed." "Install Python dependencies in myai-python-agent/.venv."
            }
        } catch {
            Add-Check "FAIL" "Python dependencies" "Required imports failed." "Install Python dependencies in myai-python-agent/.venv."
        }
    }

    $javaHome = [Environment]::GetEnvironmentVariable("JAVA_HOME")
    if ($javaHome -and (Test-Path $javaHome)) {
        Add-Check "OK" "JAVA_HOME" $javaHome
    } else {
        Add-Check "WARN" "JAVA_HOME" "JAVA_HOME is not set or does not exist." "Set JAVA_HOME to a JDK if Maven cannot find Java."
    }
    $javaCommandPath = "java"
    if ($javaHome -and (Test-Path (Join-Path $javaHome "bin\java.exe"))) {
        $javaCommandPath = Join-Path $javaHome "bin\java.exe"
    }
    if ((Test-Path $javaCommandPath) -or (Test-ExternalCommand -Command "java")) {
        try {
            $previousErrorActionPreference = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            $javaVersionOutput = & $javaCommandPath -version 2>&1
            $javaExitCode = $LASTEXITCODE
            $ErrorActionPreference = $previousErrorActionPreference
            if ($javaExitCode -eq 0) {
                $javaVersion = $javaVersionOutput | Where-Object { $_ -and $_.ToString().Trim().Length -gt 0 } | Select-Object -First 1
                Add-Check "OK" "Java command" ($javaVersion -join " ")
            } else {
                Add-Check "FAIL" "Java command" "java -version exited with code $javaExitCode." "Install a JDK or fix PATH/JAVA_HOME."
            }
        } catch {
            $ErrorActionPreference = "Stop"
            Add-Check "FAIL" "Java command" "Could not run java." "Install a JDK or fix PATH/JAVA_HOME."
        }
    } else {
        Add-Check "FAIL" "Java command" "java is not available on PATH." "Install a JDK or set PATH/JAVA_HOME."
    }

    $mvnw = Join-Path $JavaDir "mvnw.cmd"
    $jar = Get-ChildItem -Path (Join-Path $JavaDir "target") -Filter "*.jar" -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notmatch "\.original$" } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($jar) {
        Add-Check "OK" "Java launcher" "Built jar available: $($jar.Name)"
    } elseif (Test-Path $mvnw) {
        Add-Check "OK" "Java launcher" "Maven wrapper available: $mvnw"
    } else {
        Add-Check "FAIL" "Java launcher" "No jar and no mvnw.cmd found." "Restore Maven wrapper or build the Java service jar."
    }

    foreach ($portSpec in @(
        @{ Name = "Python port"; Host = $PythonHost; Port = $PythonPort },
        @{ Name = "Java port"; Host = "127.0.0.1"; Port = $JavaPort }
    )) {
        $portOpen = Test-PortOpen -HostName $portSpec.Host -Port $portSpec.Port
        if ($portOpen) {
            $owners = Get-PortProcessIds -Port $portSpec.Port
            Add-Check "WARN" $portSpec.Name "$($portSpec.Host):$($portSpec.Port) is already listening. pid(s): $($owners -join ', ')" "If this is a stale process, run .\start-myai.cmd stop."
        } else {
            Add-Check "OK" $portSpec.Name "$($portSpec.Host):$($portSpec.Port) is free."
        }
    }

    if ($LocalMode) {
        Add-Check "OK" "Database mode" "LocalMode uses SQLite and skips MySQL."
    } elseif ($SkipMysql) {
        Add-Check "WARN" "Database mode" "MySQL startup is skipped." "Ensure the database in DB_URL is already reachable."
    } else {
        $dbPort = Get-DbPort
        if (Test-PortOpen -HostName "127.0.0.1" -Port $dbPort) {
            Add-Check "OK" "MySQL port" "127.0.0.1:$dbPort is reachable."
        } else {
            Add-Check "WARN" "MySQL port" "127.0.0.1:$dbPort is not reachable." "Start MySQL or use -LocalMode."
        }
        if ($DbPassword.Trim().Length -eq 0) {
            Add-Check "WARN" "DB password" "DB_PASSWORD is empty." "Set DB_PASSWORD in scripts/start-myai.env or use -LocalMode."
        } else {
            Add-Check "OK" "DB password" "Configured."
        }
    }

    foreach ($pathSpec in @(
        @{ Name = "Python Chroma dir"; Path = Join-Path $PythonDir "chroma_db" },
        @{ Name = "Knowledge data dir"; Path = Join-Path $PythonDir "knowledge_data" },
        @{ Name = "Runtime dir"; Path = Join-Path $PythonDir ".runtime" }
    )) {
        $parent = Split-Path -Parent $pathSpec.Path
        if (Test-DirectoryWritable -Path $parent) {
            Add-Check "OK" $pathSpec.Name "Parent is writable: $parent"
        } else {
            Add-Check "FAIL" $pathSpec.Name "Parent is not writable: $parent" "Check workspace permissions."
        }
    }

    $provider = (Get-EnvValue -Values $pythonEnv -Name "MYAI_LLM_PROVIDER" -Default "stub").ToLowerInvariant()
    $chatProvider = (Get-EnvValue -Values $pythonEnv -Name "MYAI_CHAT_PROVIDER" -Default $provider).ToLowerInvariant()
    $taskProvider = (Get-EnvValue -Values $pythonEnv -Name "MYAI_TASK_PROVIDER" -Default $provider).ToLowerInvariant()
    $memoryProvider = (Get-EnvValue -Values $pythonEnv -Name "MYAI_MEMORY_PROVIDER" -Default $provider).ToLowerInvariant()
    $embeddingProvider = (Get-EnvValue -Values $pythonEnv -Name "MYAI_EMBEDDING_PROVIDER" -Default "stub").ToLowerInvariant()
    $fallback = Get-EnvBool -Values $pythonEnv -Name "MYAI_LLM_FALLBACK_TO_STUB" -Default $true
    $arkKey = Get-EnvValue -Values $pythonEnv -Name "ARK_API_KEY" -Default ""
    $defaultModelId = Get-EnvValue -Values $pythonEnv -Name "ARK_MODEL_ID" -Default ""
    $embeddingDefaultModelId = Get-EnvValue -Values $pythonEnv -Name "ARK_EMBEDDING_MODEL_ID" -Default ""
    $openAiBaseUrl = Get-EnvValue -Values $pythonEnv -Name "MYAI_OPENAI_COMPATIBLE_BASE_URL" -Default "http://127.0.0.1:11434/v1"
    $openAiEmbeddingBaseUrl = Get-EnvValue -Values $pythonEnv -Name "MYAI_OPENAI_COMPATIBLE_EMBEDDING_BASE_URL" -Default $openAiBaseUrl
    $arkBaseUrl = Get-EnvValue -Values $pythonEnv -Name "ARK_BASE_URL" -Default "https://ark.cn-beijing.volces.com/api/v3"
    $roleSpecs = @(
        [pscustomobject]@{ Name = "chat"; Kind = "llm"; Provider = $chatProvider; ModelId = (Get-EnvValue -Values $pythonEnv -Name "MYAI_CHAT_MODEL_ID" -Default $defaultModelId) },
        [pscustomobject]@{ Name = "task"; Kind = "llm"; Provider = $taskProvider; ModelId = (Get-EnvValue -Values $pythonEnv -Name "MYAI_TASK_MODEL_ID" -Default $defaultModelId) },
        [pscustomobject]@{ Name = "memory"; Kind = "llm"; Provider = $memoryProvider; ModelId = (Get-EnvValue -Values $pythonEnv -Name "MYAI_MEMORY_MODEL_ID" -Default $defaultModelId) },
        [pscustomobject]@{ Name = "embedding"; Kind = "embedding"; Provider = $embeddingProvider; ModelId = (Get-EnvValue -Values $pythonEnv -Name "MYAI_EMBEDDING_MODEL_ID" -Default $embeddingDefaultModelId) }
    )
    $supportedProviders = @("stub", "volcengine", "openai_compatible")
    $modelConfigIssues = 0

    foreach ($roleSpec in $roleSpecs) {
        if ($roleSpec.Provider -notin $supportedProviders) {
            Add-Check "FAIL" "Model config ($($roleSpec.Name))" "Unsupported provider '$($roleSpec.Provider)'." "Use stub, volcengine, or openai_compatible."
            $modelConfigIssues += 1
            continue
        }
        if ($roleSpec.Provider -eq "stub") {
            continue
        }

        $canLlmFallback = $roleSpec.Kind -eq "llm" -and $fallback
        $failureLevel = $(if ($canLlmFallback) { "WARN" } else { "FAIL" })
        if ($roleSpec.ModelId.Trim().Length -eq 0) {
            Add-Check $failureLevel "Model config ($($roleSpec.Name))" "Provider '$($roleSpec.Provider)' has no model ID." "Set the matching MYAI_*_MODEL_ID value."
            $modelConfigIssues += 1
        }

        $endpoint = $(if ($roleSpec.Provider -eq "volcengine") {
            $arkBaseUrl
        } elseif ($roleSpec.Kind -eq "embedding") {
            $openAiEmbeddingBaseUrl
        } else {
            $openAiBaseUrl
        })
        if (-not (Test-HttpEndpoint -Value $endpoint)) {
            Add-Check $failureLevel "Model config ($($roleSpec.Name))" "Invalid HTTP(S) endpoint '$endpoint'." "Set a valid absolute provider base URL."
            $modelConfigIssues += 1
        } elseif ($roleSpec.Provider -eq "openai_compatible" -and -not (Test-LoopbackEndpoint -Value $endpoint)) {
            Add-Check "WARN" "Model endpoint ($($roleSpec.Name))" "OpenAI-compatible endpoint is not loopback: $endpoint" "Use 127.0.0.1 for the supported local baseline, or explicitly secure remote transport and authentication."
            $modelConfigIssues += 1
        }

        if ($roleSpec.Provider -eq "volcengine" -and $arkKey.Trim().Length -eq 0) {
            Add-Check $failureLevel "Model config ($($roleSpec.Name))" "Volcengine provider requires ARK_API_KEY." "Set ARK_API_KEY or change this role's provider."
            $modelConfigIssues += 1
        }
    }

    $numberSpecs = @(
        [pscustomobject]@{ Name = "MYAI_LLM_TEMPERATURE"; Value = (Get-EnvValue -Values $pythonEnv -Name "MYAI_LLM_TEMPERATURE" -Default "0.7"); Kind = "number"; Minimum = 0.0; Maximum = 2.0 },
        [pscustomobject]@{ Name = "MYAI_LLM_REQUEST_TIMEOUT_SECONDS"; Value = (Get-EnvValue -Values $pythonEnv -Name "MYAI_LLM_REQUEST_TIMEOUT_SECONDS" -Default "3"); Kind = "number"; Minimum = 0.1 },
        [pscustomobject]@{ Name = "MYAI_LLM_MAX_RETRIES"; Value = (Get-EnvValue -Values $pythonEnv -Name "MYAI_LLM_MAX_RETRIES" -Default "0"); Kind = "integer"; Minimum = 0 },
        [pscustomobject]@{ Name = "MYAI_LLM_MAX_TOKENS"; Value = (Get-EnvValue -Values $pythonEnv -Name "MYAI_LLM_MAX_TOKENS" -Default "512"); Kind = "integer"; Minimum = 1 },
        [pscustomobject]@{ Name = "MYAI_EMBEDDING_REQUEST_TIMEOUT_SECONDS"; Value = (Get-EnvValue -Values $pythonEnv -Name "MYAI_EMBEDDING_REQUEST_TIMEOUT_SECONDS" -Default "3"); Kind = "number"; Minimum = 0.1 },
        [pscustomobject]@{ Name = "MYAI_EMBEDDING_MAX_RETRIES"; Value = (Get-EnvValue -Values $pythonEnv -Name "MYAI_EMBEDDING_MAX_RETRIES" -Default "0"); Kind = "integer"; Minimum = 0 },
        [pscustomobject]@{ Name = "MYAI_EMBEDDING_EXPECTED_DIMENSIONS"; Value = (Get-EnvValue -Values $pythonEnv -Name "MYAI_EMBEDDING_EXPECTED_DIMENSIONS" -Default "0"); Kind = "integer"; Minimum = 0 }
    )
    foreach ($numberSpec in $numberSpecs) {
        $valid = $(if ($numberSpec.Kind -eq "integer") {
            Test-IntegerAtLeast -Value $numberSpec.Value -Minimum ([int]$numberSpec.Minimum)
        } else {
            $maximum = $(if ($null -ne $numberSpec.Maximum) { [double]$numberSpec.Maximum } else { [double]::PositiveInfinity })
            Test-FiniteNumberAtLeast -Value $numberSpec.Value -Minimum ([double]$numberSpec.Minimum) -Maximum $maximum
        })
        if (-not $valid) {
            $range = $(if ($null -ne $numberSpec.Maximum) {
                "$($numberSpec.Minimum)..$($numberSpec.Maximum)"
            } else {
                ">= $($numberSpec.Minimum)"
            })
            Add-Check "FAIL" "Model config ($($numberSpec.Name))" "Invalid value '$($numberSpec.Value)'; expected $($numberSpec.Kind) $range." "Correct the value in myai-python-agent/.env or the process environment."
            $modelConfigIssues += 1
        }
    }
    $seed = Get-EnvValue -Values $pythonEnv -Name "MYAI_LLM_SEED" -Default ""
    if ($seed.Trim().Length -gt 0 -and -not (Test-IntegerAtLeast -Value $seed -Minimum ([int]::MinValue))) {
        Add-Check "FAIL" "Model config (MYAI_LLM_SEED)" "Invalid integer seed '$seed'." "Use an integer seed or leave it empty."
        $modelConfigIssues += 1
    }
    $embeddingDimensions = Get-EnvValue -Values $pythonEnv -Name "MYAI_EMBEDDING_EXPECTED_DIMENSIONS" -Default "0"
    if ($embeddingProvider -ne "stub" -and (Test-IntegerAtLeast -Value $embeddingDimensions -Minimum 0) -and [int]$embeddingDimensions -eq 0) {
        Add-Check "WARN" "Model config (embedding)" "Embedding dimensions are not pinned." "Set MYAI_EMBEDDING_EXPECTED_DIMENSIONS for stable persistent indexes."
        $modelConfigIssues += 1
    }

    if ($modelConfigIssues -eq 0) {
        Add-Check "OK" "Model config" "chat=$chatProvider, task=$taskProvider, memory=$memoryProvider, embedding=$embeddingProvider."
    }

    Write-Host ""
    Write-Host "Diagnostics summary: $($script:DoctorFailures) failure(s), $($script:DoctorWarnings) warning(s)."
    if ($script:DoctorFailures -gt 0) {
        Write-Host "Startup is likely to fail until failures are fixed." -ForegroundColor Red
        exit 1
    }
    Write-Host "No blocking startup failures detected." -ForegroundColor Green
}

function Stop-MyAiServices {
    Write-Host "Stopping MyAI services ..."
    Stop-PidFileProcess -Name "Python launcher" -PidFile $PythonPidFile
    Stop-PidFileProcess -Name "Java launcher" -PidFile $JavaPidFile
    Start-Sleep -Seconds 1
    Stop-PortProcesses -Name "Python service" -Port $PythonPort
    Stop-PortProcesses -Name "Java service" -Port $JavaPort
    Start-Sleep -Seconds 1
    Write-Host "Stop completed. MySQL is left running."
    Show-ServiceStatus
}

function Get-DbPort {
    if ($DbUrl -match ":(\d+)/") {
        return [int]$Matches[1]
    }
    return 3306
}

function Start-MysqlIfNeeded {
    if ($SkipMysql) {
        Write-Host "Skipping MySQL startup."
        return
    }

    $dbPort = Get-DbPort

    if (Test-PortOpen -HostName "127.0.0.1" -Port $dbPort) {
        Write-Host "MySQL already appears to be listening on 127.0.0.1:$dbPort"
        return
    }

    $service = $null
    if ($MysqlServiceName.Trim().Length -gt 0) {
        $service = Get-Service -Name $MysqlServiceName -ErrorAction SilentlyContinue
    } else {
        $service = Get-Service -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match "^MySQL" -or $_.DisplayName -match "MySQL" } |
            Select-Object -First 1
    }

    if ($null -eq $service) {
        Write-Warning "MySQL service was not found. Start MySQL manually, or rerun with -MysqlServiceName <service-name>."
        return
    }

    if ($service.Status -ne "Running") {
        Write-Host "Starting MySQL service: $($service.Name)"
        try {
            Start-Service -Name $service.Name
        } catch {
            Write-Warning "Could not start MySQL service automatically. Try running this script as administrator, or start MySQL manually."
            return
        }
    }

    Wait-Port -Name "MySQL" -HostName "127.0.0.1" -Port $dbPort -TimeoutSeconds 30 | Out-Null
}

function Start-BackgroundService {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [string]$Command,
        [string]$LogFile,
        [string]$PidFile
    )

    Write-Host "Starting $Name ..."
    $launcherName = ($Name -replace "[^A-Za-z0-9_-]", "-").ToLowerInvariant() + ".launcher.ps1"
    $launcherPath = Join-Path $LogDir $launcherName
    @"
Start-Transcript -Path '$LogFile' -Force
try {
    Set-Location '$WorkingDirectory'
    `$ErrorActionPreference = 'Stop'
    $Command
} catch {
    Write-Error `$_.Exception.Message
    exit 1
} finally {
    Stop-Transcript
}
"@ | Set-Content -Path $launcherPath -Encoding UTF8

    $process = Start-Process -FilePath "powershell" `
        -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $launcherPath `
        -WindowStyle Hidden `
        -PassThru

    Write-Host "$Name pid: $($process.Id), log: $LogFile"
    Write-Host "$Name launcher: $launcherPath"
    if ($PidFile.Trim().Length -gt 0) {
        Set-Content -Path $PidFile -Value $process.Id -Encoding ASCII
    }
}

function Find-JavaLauncher {
    $jar = Get-ChildItem -Path (Join-Path $JavaDir "target") -Filter "*.jar" -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notmatch "\.original$" } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if ($null -ne $jar) {
        $knownJdk = Join-Path $env:USERPROFILE ".jdks\openjdk-23.0.1\bin\java.exe"
        $javaExe = if (Test-Path $knownJdk) { $knownJdk } else { Resolve-JavaExe }
        return @{
            Type = "jar"
            Command = "`& '$javaExe' -jar '$($jar.FullName)'"
        }
    }

    $mvnw = Join-Path $JavaDir "mvnw.cmd"
    $mavenUserHome = Join-Path $JavaDir ".maven-home"
    $mavenRepo = Join-Path $JavaDir ".m2repo"
    return @{
        Type = "maven"
        Command = @"
`$env:MAVEN_USER_HOME = '$mavenUserHome'
`& '$mvnw' "-Dmaven.repo.local=$mavenRepo" spring-boot:run
"@
    }
}

if ($Action -eq "stop") {
    Stop-MyAiServices
    return
}

if ($Action -eq "status") {
    Show-ServiceStatus
    return
}

if ($Action -eq "doctor") {
    Invoke-StartupDiagnostics
    return
}

if ($Action -eq "restart") {
    Stop-MyAiServices
    Write-Host ""
}

Start-MysqlIfNeeded

$pythonExe = Join-Path $PythonDir ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "python"
}

$pythonLog = Join-Path $LogDir "python-service.log"
$javaLog = Join-Path $LogDir "java-service.log"

if (Test-PortOpen -HostName $PythonHost -Port $PythonPort) {
    Write-Host "Python service already appears to be running on $PythonHost`:$PythonPort"
} else {
    Start-BackgroundService `
        -Name "Python FastAPI service" `
        -WorkingDirectory $PythonDir `
        -Command "`& '$pythonExe' -m uvicorn app.main:app --host $PythonHost --port $PythonPort" `
        -LogFile $pythonLog `
        -PidFile $PythonPidFile
    Wait-Port -Name "Python service" -HostName $PythonHost -Port $PythonPort -TimeoutSeconds 60 | Out-Null
}

if (Test-PortOpen -HostName "127.0.0.1" -Port $JavaPort) {
    Write-Host "Java service already appears to be running on 127.0.0.1:$JavaPort"
} else {
    $pythonBaseUrl = "http://$PythonHost`:$PythonPort"
    $javaLauncher = Find-JavaLauncher
    Write-Host "Java startup mode: $($javaLauncher.Type)"
    $javaCommand = @"
`$env:DB_URL = '$DbUrl'
`$env:DB_USERNAME = '$DbUsername'
`$env:DB_PASSWORD = '$DbPassword'
`$env:SERVER_PORT = '$JavaPort'
`$env:SERVER_ADDRESS = '127.0.0.1'
`$env:PYTHON_SERVICE_BASE_URL = '$pythonBaseUrl'
$(if ($LocalMode) { "`$env:SPRING_PROFILES_ACTIVE = 'local'`n`$env:MYAI_AUTH_MODE = 'local'" } else { "" })
$($javaLauncher.Command)
"@
    Start-BackgroundService `
        -Name "Java Spring Boot service" `
        -WorkingDirectory $JavaDir `
        -Command $javaCommand `
        -LogFile $javaLog `
        -PidFile $JavaPidFile
    Wait-Port -Name "Java service" -HostName "127.0.0.1" -Port $JavaPort -TimeoutSeconds 90 | Out-Null
}

Write-Host ""
if (Test-PortOpen -HostName "127.0.0.1" -Port $JavaPort) {
    Write-Host "Services started: 127.0.0.1:$JavaPort"
    Write-Host "Open in browser: http://127.0.0.1:$JavaPort"
} else {
    Write-Warning "Java is not listening on port $JavaPort. Check scripts\logs\java-service.log."
    Write-Warning "For the easiest local startup, run .\start-myai.cmd with no arguments or use -LocalMode. For MySQL mode, verify DB_URL, DB_USERNAME, and DB_PASSWORD in scripts\start-myai.env."
    Stop-MyAiServices
    if (-not $NoPause) {
        Write-Host ""
        Read-Host "Startup failed. Press Enter to exit"
    }
    exit 1
}
Write-Host "Logs: $LogDir"
Write-Host "Stop command: .\start-myai.cmd stop"

if (-not $NoPause) {
    Write-Host ""
    Write-Host "Press Ctrl+C to stop MyAI services and release ports."
    try {
        while ($true) {
            Start-Sleep -Seconds 1
        }
    } finally {
        Write-Host ""
        Stop-MyAiServices
    }
}
