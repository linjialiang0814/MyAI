param(
    [string]$PythonHost = "127.0.0.1",
    [int]$PythonPort = 8000,
    [int]$JavaPort = 8080,
    [switch]$SkipStartStop,
    [switch]$KeepRunning,
    [switch]$IncludeLiveModelProbe,
    [switch]$SkipChatSmoke,
    [switch]$SkipTaskSmoke
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$StartScript = Join-Path $ScriptDir "start-myai.ps1"
$PythonLog = Join-Path $ScriptDir "logs\python-service.log"
$JavaLog = Join-Path $ScriptDir "logs\java-service.log"
$JavaBase = "http://127.0.0.1:$JavaPort"
$PythonBase = "http://${PythonHost}:$PythonPort"
$Results = New-Object System.Collections.Generic.List[object]
$StartedBySmoke = $false

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "== $Message =="
}

function Add-Result {
    param(
        [string]$Name,
        [ValidateSet("PASS", "WARN", "FAIL")]
        [string]$Status,
        [string]$Detail = "",
        [string]$Hint = ""
    )
    $Results.Add([pscustomobject]@{
        name = $Name
        status = $Status
        detail = $Detail
        hint = $Hint
    }) | Out-Null

    $line = "[$Status] $Name"
    if ($Detail.Trim().Length -gt 0) {
        $line += " - $Detail"
    }
    if ($Status -eq "FAIL") {
        Write-Host $line -ForegroundColor Red
        if ($Hint.Trim().Length -gt 0) {
            Write-Host "       hint: $Hint" -ForegroundColor Yellow
        }
    } elseif ($Status -eq "WARN") {
        Write-Host $line -ForegroundColor Yellow
    } else {
        Write-Host $line -ForegroundColor Green
    }
}

function Invoke-SmokeCheck {
    param(
        [string]$Name,
        [scriptblock]$Check,
        [string]$Hint = ""
    )
    try {
        $detail = & $Check
        if ($null -eq $detail) {
            $detail = "ok"
        }
        Add-Result -Name $Name -Status "PASS" -Detail ([string]$detail) -Hint $Hint
    } catch {
        Add-Result -Name $Name -Status "FAIL" -Detail $_.Exception.Message -Hint $Hint
    }
}

function Wait-Http {
    param(
        [string]$Name,
        [string]$Uri,
        [int]$TimeoutSeconds = 90
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastError = ""
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return "$Name ready: HTTP $($response.StatusCode)"
            }
            $lastError = "HTTP $($response.StatusCode)"
        } catch {
            $lastError = $_.Exception.Message
        }
        Start-Sleep -Seconds 1
    }
    throw "$Name did not become ready within ${TimeoutSeconds}s. Last error: $lastError"
}

function Invoke-Json {
    param(
        [string]$Method,
        [string]$Uri,
        [object]$Body = $null,
        [Microsoft.PowerShell.Commands.WebRequestSession]$Session = $null,
        [hashtable]$Headers = @{},
        [int]$TimeoutSec = 30
    )
    $parameters = @{
        Method = $Method
        Uri = $Uri
        Headers = $Headers
        TimeoutSec = $TimeoutSec
    }
    if ($null -ne $Session) {
        $parameters.WebSession = $Session
    }
    if ($null -ne $Body) {
        $parameters.ContentType = "application/json"
        $parameters.Body = ($Body | ConvertTo-Json -Depth 12)
    }
    return Invoke-RestMethod @parameters
}

function New-FrontendSession {
    $session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    $homeResponse = Invoke-WebRequest -Uri "$JavaBase/home" -UseBasicParsing -WebSession $session -TimeoutSec 15
    $tokenMatch = [regex]::Match($homeResponse.Content, '<meta\s+name="_csrf"\s+[^>]*content="([^"]*)"')
    $headerMatch = [regex]::Match($homeResponse.Content, '<meta\s+name="_csrf_header"\s+[^>]*content="([^"]*)"')
    $headers = @{}
    if ($tokenMatch.Success -and $headerMatch.Success) {
        $headers[$headerMatch.Groups[1].Value] = $tokenMatch.Groups[1].Value
    }
    return @{
        Session = $session
        Headers = $headers
        HomeContent = $homeResponse.Content
    }
}

function Assert-Truthy {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) {
        throw $Message
    }
}

function Test-PortReleased {
    param([int]$Port)
    $deadline = (Get-Date).AddSeconds(25)
    while ((Get-Date) -lt $deadline) {
        $lines = @(cmd /c "netstat -ano -p tcp" | Select-String -Pattern ":$Port\s+.*LISTENING")
        if ($lines.Count -eq 0) {
            return "port $Port released"
        }
        Start-Sleep -Seconds 1
    }
    throw "port $Port is still LISTENING"
}

function Stop-LocalServices {
    Write-Step "Stop LocalMode services"
    & $StartScript stop -PythonPort $PythonPort -JavaPort $JavaPort -NoPause
    if ($LASTEXITCODE -ne 0) {
        throw "start-myai stop failed with exit code $LASTEXITCODE"
    }
}

Set-Location $Root

try {
    Write-Step "Preflight"
    Invoke-SmokeCheck "script files" {
        Assert-Truthy (Test-Path $StartScript) "missing scripts\start-myai.ps1"
        Assert-Truthy (Test-Path (Join-Path $Root "start-myai.cmd")) "missing start-myai.cmd"
        "startup scripts found"
    }

    if (-not $SkipStartStop) {
        Invoke-SmokeCheck "startup doctor" {
            & $StartScript doctor -LocalMode -PythonPort $PythonPort -JavaPort $JavaPort -NoPause
            if ($LASTEXITCODE -ne 0) {
                throw "doctor failed with exit code $LASTEXITCODE"
            }
            "doctor LocalMode passed"
        } "Run start-myai.cmd doctor -LocalMode and inspect dependency output."

        Stop-LocalServices

        Write-Step "Start LocalMode services"
        & $StartScript start -LocalMode -PythonHost $PythonHost -PythonPort $PythonPort -JavaPort $JavaPort -NoPause
        if ($LASTEXITCODE -ne 0) {
            throw "start-myai start failed with exit code $LASTEXITCODE"
        }
        $StartedBySmoke = $true
    }

    Write-Step "Readiness"
    Invoke-SmokeCheck "python observability readiness" {
        Wait-Http -Name "Python" -Uri "$PythonBase/observability/summary" -TimeoutSeconds 90
    } "Inspect $PythonLog"
    Invoke-SmokeCheck "java home readiness" {
        Wait-Http -Name "Java" -Uri "$JavaBase/home" -TimeoutSeconds 90
    } "Inspect $JavaLog"

    $frontend = $null
    Invoke-SmokeCheck "frontend session and csrf" {
        $script:frontend = New-FrontendSession
        Assert-Truthy ($frontend.HomeContent.Contains("agent-cockpit")) "home template did not include chat cockpit marker"
        Assert-Truthy ($frontend.HomeContent.Contains("system-health")) "home template did not include system health marker"
        Assert-Truthy ($frontend.Headers.Count -gt 0) "csrf headers were not discovered from /home"
        "home loaded with csrf"
    } "Open $JavaBase/home and inspect rendered page/auth mode."

    Write-Step "Core API smoke"
    Invoke-SmokeCheck "observability summary" {
        $summary = Invoke-Json -Method "GET" -Uri "$JavaBase/observability/summary" -Session $frontend.Session -Headers $frontend.Headers
        Assert-Truthy ($null -ne $summary.model) "summary.model missing"
        Assert-Truthy ($null -ne $summary.task) "summary.task missing"
        Assert-Truthy ($null -ne $summary.connectors) "summary.connectors missing"
        "model=$($summary.model.mode), task metrics available"
    } "Check Java observability proxy and Python /observability/summary."

    Invoke-SmokeCheck "memory settings/list/query" {
        $settings = Invoke-Json -Method "GET" -Uri "$JavaBase/memory/settings" -Session $frontend.Session -Headers $frontend.Headers
        Assert-Truthy ($null -ne $settings.settings) "memory settings payload missing settings object"
        $list = Invoke-Json -Method "GET" -Uri "$JavaBase/memory/list" -Session $frontend.Session -Headers $frontend.Headers
        Assert-Truthy ($null -ne $list) "memory list returned null"
        $query = Invoke-Json -Method "POST" -Uri "$JavaBase/memory/query" -Session $frontend.Session -Headers $frontend.Headers -Body @{ content = "phase8 local smoke memory keyword" }
        Assert-Truthy ($null -ne $query) "memory query returned null"
        "settings ok, list/query ok"
    } "Inspect Java MemoryController proxy and Python memory service logs."

    Invoke-SmokeCheck "knowledge files" {
        $files = Invoke-Json -Method "GET" -Uri "$JavaBase/knowledge/files" -Session $frontend.Session -Headers $frontend.Headers
        Assert-Truthy ($null -ne $files) "knowledge files returned null"
        "knowledge files endpoint ok"
    } "Inspect Java KnowledgeController proxy and Python knowledge service logs."

    Invoke-SmokeCheck "task tools and runs" {
        $tools = Invoke-Json -Method "GET" -Uri "$JavaBase/task/tools" -Session $frontend.Session -Headers $frontend.Headers
        Assert-Truthy ($null -ne $tools.tools) "task tools missing tools list"
        $runs = Invoke-Json -Method "GET" -Uri "$JavaBase/task/runs?limit=5" -Session $frontend.Session -Headers $frontend.Headers
        Assert-Truthy ($null -ne $runs) "task runs returned null"
        "tools=$($tools.tools.Count)"
    } "Inspect Java TaskController proxy and Python task runtime logs."

    if (-not $SkipChatSmoke) {
        Invoke-SmokeCheck "chat submit" {
            $chat = Invoke-Json -Method "POST" -Uri "$JavaBase/chat" -Session $frontend.Session -Headers $frontend.Headers -TimeoutSec 45 -Body @{
                message = "Phase 8 local smoke: reply with a short readiness confirmation."
                conversation_id = $null
            }
            Assert-Truthy (($chat.reply -as [string]).Trim().Length -gt 0) "chat reply is empty"
            Assert-Truthy (($chat.conversation_id -as [string]).Trim().Length -gt 0) "conversation_id missing"
            "conversation=$($chat.conversation_id)"
        } "Chat should fall back to Stub if the real model is unavailable. Inspect $PythonLog and $JavaLog."
    } else {
        Add-Result -Name "chat submit" -Status "WARN" -Detail "skipped by -SkipChatSmoke"
    }

    if (-not $SkipTaskSmoke) {
        Invoke-SmokeCheck "task execution" {
            $task = Invoke-Json -Method "POST" -Uri "$JavaBase/task" -Session $frontend.Session -Headers $frontend.Headers -TimeoutSec 60 -Body @{
                content = "Phase 8 local smoke: summarize current runtime readiness in one sentence."
            }
            Assert-Truthy ($null -ne $task.success) "task success field missing"
            Assert-Truthy (($task.status -as [string]).Trim().Length -gt 0) "task status missing"
            "status=$($task.status), success=$($task.success)"
        } "Task should use LocalMode fallback paths when needed. Inspect $PythonLog and $JavaLog."
    } else {
        Add-Result -Name "task execution" -Status "WARN" -Detail "skipped by -SkipTaskSmoke"
    }

    if ($IncludeLiveModelProbe) {
        Invoke-SmokeCheck "live model probe" {
            $probe = Invoke-Json -Method "POST" -Uri "$JavaBase/observability/model/probe" -Session $frontend.Session -Headers $frontend.Headers -TimeoutSec 90 -Body @{}
            Assert-Truthy (($probe.status -as [string]).Trim().Length -gt 0) "probe status missing"
            if ($probe.status -ne "healthy") {
                Add-Result -Name "live model probe health" -Status "WARN" -Detail "status=$($probe.status), real_roles=$($probe.real_roles_healthy)/$($probe.real_roles_total)"
            }
            "status=$($probe.status), real_roles=$($probe.real_roles_healthy)/$($probe.real_roles_total)"
        } "This check depends on external provider/network health; normal smoke does not require it."
    }
} finally {
    if ($StartedBySmoke -and -not $KeepRunning) {
        try {
            Stop-LocalServices
            Invoke-SmokeCheck "python port release" {
                Test-PortReleased -Port $PythonPort
            } "A stale Python process may still own port $PythonPort."
            Invoke-SmokeCheck "java port release" {
                Test-PortReleased -Port $JavaPort
            } "A stale Java process may still own port $JavaPort."
        } catch {
            Add-Result -Name "stop services" -Status "FAIL" -Detail $_.Exception.Message -Hint "Run start-myai.cmd stop and inspect scripts\logs\*.pid."
        }
    } elseif ($StartedBySmoke -and $KeepRunning) {
        Add-Result -Name "stop services" -Status "WARN" -Detail "skipped by -KeepRunning"
    }
}

Write-Step "Summary"
$passCount = @($Results | Where-Object { $_.status -eq "PASS" }).Count
$warnCount = @($Results | Where-Object { $_.status -eq "WARN" }).Count
$failCount = @($Results | Where-Object { $_.status -eq "FAIL" }).Count
Write-Host "PASS=$passCount WARN=$warnCount FAIL=$failCount"

if ($failCount -gt 0) {
    Write-Host ""
    Write-Host "Actionable logs:" -ForegroundColor Yellow
    Write-Host "  Python: $PythonLog"
    Write-Host "  Java:   $JavaLog"
    exit 1
}

Write-Host "MyAI local smoke passed."
