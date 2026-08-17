param(
    [string]$JavaHome = "",
    [switch]$SkipJavaTests,
    [switch]$SkipPythonTests
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$PythonDir = Join-Path $Root "myai-python-agent"
$JavaDir = Join-Path $Root "myai-java-service"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "== $Message =="
}

function Invoke-Checked {
    param(
        [string]$Label,
        [scriptblock]$Command
    )
    Write-Step $Label
    & $Command
}

Set-Location $Root

Invoke-Checked "Static release quality gates" {
    & (Join-Path $ScriptDir "ci-quality-gates.ps1")
    if ($LASTEXITCODE -ne 0) {
        throw "Static release quality gates failed with exit code $LASTEXITCODE"
    }
}

Invoke-Checked "Startup diagnostics" {
    & (Join-Path $Root "start-myai.cmd") doctor -LocalMode
    if ($LASTEXITCODE -ne 0) {
        throw "Startup diagnostics failed with exit code $LASTEXITCODE"
    }
}

if (-not $SkipPythonTests) {
    Invoke-Checked "Python full test suite" {
        Set-Location $PythonDir
        & ".\.venv\Scripts\python.exe" -m unittest discover -s tests -t . -p "test_*.py"
        if ($LASTEXITCODE -ne 0) {
            throw "Python full test suite failed with exit code $LASTEXITCODE"
        }
        Set-Location $Root
    }
}

if (-not $SkipJavaTests) {
    Invoke-Checked "Java tests and package" {
        Set-Location $JavaDir
        if ($JavaHome.Trim().Length -gt 0) {
            $env:JAVA_HOME = $JavaHome
        }
        & ".\mvnw.cmd" -q verify
        if ($LASTEXITCODE -ne 0) {
            throw "Java verification failed with exit code $LASTEXITCODE"
        }
        Set-Location $Root
    }
}

Write-Step "Release smoke completed"
Write-Host "MyAI release smoke passed."
