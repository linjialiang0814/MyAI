param(
    [string]$OutputDirectory = "",
    [switch]$SkipJavaBuild,
    [string]$JavaHome = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
if ($OutputDirectory.Trim().Length -eq 0) {
    $OutputDirectory = Join-Path $Root "dist"
}
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
$version = (Get-Content -LiteralPath (Join-Path $Root "VERSION") -Raw).Trim()
if ($version -notmatch "^[0-9A-Za-z][0-9A-Za-z._-]*$") {
    throw "VERSION contains characters that are unsafe for an artifact name."
}

$artifactBase = "MyAI-$version-windows-x64"
$stageParent = Join-Path ([System.IO.Path]::GetTempPath()) ("myai-portable-" + [guid]::NewGuid().ToString("N"))
$packageRoot = Join-Path $stageParent $artifactBase
$zipPath = Join-Path $OutputDirectory "$artifactBase.zip"
$zipChecksumPath = "$zipPath.sha256"

function Copy-RequiredFile {
    param([string]$Source, [string]$RelativeDestination)
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
        throw "Required portable source file is missing: $Source"
    }
    $destination = Join-Path $packageRoot ($RelativeDestination -replace "/", "\")
    $parent = Split-Path -Parent $destination
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    Copy-Item -LiteralPath $Source -Destination $destination -Force
}

function Get-Sha256 {
    param([string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

try {
    New-Item -ItemType Directory -Force -Path $packageRoot | Out-Null

    if (-not $SkipJavaBuild) {
        if ($JavaHome.Trim().Length -gt 0) {
            $env:JAVA_HOME = [System.IO.Path]::GetFullPath($JavaHome)
        }
        Push-Location (Join-Path $Root "myai-java-service")
        try {
            & ".\mvnw.cmd" -q verify
            if ($LASTEXITCODE -ne 0) {
                throw "Java package build failed with exit code $LASTEXITCODE."
            }
        } finally {
            Pop-Location
        }
    }

    $jar = Get-ChildItem -LiteralPath (Join-Path $Root "myai-java-service\target") -Filter "*.jar" -File |
        Where-Object { $_.Name -notmatch "\.original$" } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -eq $jar) {
        throw "No Spring Boot jar found under myai-java-service/target. Build it first or omit -SkipJavaBuild."
    }

    $git = Get-Command git -ErrorAction SilentlyContinue
    if ($null -eq $git) {
        throw "git is required when building the portable artifact so only tracked Python sources are copied."
    }
    $trackedPython = @(& git -C $Root ls-files -- "myai-python-agent/app")
    if ($LASTEXITCODE -ne 0 -or $trackedPython.Count -eq 0) {
        throw "Could not enumerate tracked Python application files."
    }
    foreach ($relative in $trackedPython) {
        if ($relative -match "(^|/)(\.env|__pycache__|chroma_db|knowledge_data|memory_settings|\.runtime|logs?)(/|$)" -or
            $relative -match "\.(db|sqlite3?|log|pyc)$") {
            throw "Unsafe tracked Python runtime artifact matched the portable selection: $relative"
        }
        $appRelative = $relative.Substring("myai-python-agent/".Length)
        Copy-RequiredFile -Source (Join-Path $Root ($relative -replace "/", "\")) -RelativeDestination "app/python/$appRelative"
    }

    Copy-RequiredFile -Source (Join-Path $Root "myai-python-agent\requirements.txt") -RelativeDestination "app/python/requirements.txt"
    foreach ($fixtureName in @(
        "knowledge_eval.json",
        "mcp_eval.json",
        "memory_governance_eval.json",
        "memory_llm_calibration.json",
        "task_runtime_eval.json"
    )) {
        Copy-RequiredFile `
            -Source (Join-Path $Root "myai-python-agent\tests\fixtures\$fixtureName") `
            -RelativeDestination "app/python/tests/fixtures/$fixtureName"
    }
    Copy-RequiredFile -Source $jar.FullName -RelativeDestination "app/java/myai.jar"
    Copy-RequiredFile -Source (Join-Path $Root "VERSION") -RelativeDestination "VERSION"
    Copy-RequiredFile -Source (Join-Path $Root "packaging\windows\README.md") -RelativeDestination "README.md"
    Copy-RequiredFile -Source (Join-Path $Root "packaging\windows\config\app.env.example") -RelativeDestination "config/app.env.example"
    Copy-RequiredFile -Source (Join-Path $Root "packaging\windows\scripts\portable-app.ps1") -RelativeDestination "scripts/portable-app.ps1"
    foreach ($entrypoint in @("setup", "doctor", "start", "stop", "status", "reset")) {
        Copy-RequiredFile -Source (Join-Path $Root "packaging\windows\$entrypoint.cmd") -RelativeDestination "$entrypoint.cmd"
    }
    Copy-RequiredFile -Source (Join-Path $Root "demo\README.md") -RelativeDestination "demo/README.md"
    Copy-RequiredFile -Source (Join-Path $Root "demo\sample-knowledge.txt") -RelativeDestination "demo/sample-knowledge.txt"

    $files = @(
        Get-ChildItem -LiteralPath $packageRoot -Recurse -File |
            Sort-Object FullName |
            ForEach-Object {
                $relative = $_.FullName.Substring($packageRoot.Length + 1).Replace("\", "/")
                [ordered]@{
                    path = $relative
                    size = [long]$_.Length
                    sha256 = Get-Sha256 -Path $_.FullName
                }
            }
    )
    $manifest = [ordered]@{
        schema_version = 1
        product = "MyAI"
        version = $version
        target = "windows-x64"
        prerequisites = @(
            "Windows 10 or later with Windows PowerShell 5.1 or PowerShell 7",
            "64-bit CPython 3.12",
            "64-bit Java runtime 17 or later",
            "Network access during setup unless a complete compatible wheel directory is supplied"
        )
        entrypoints = [ordered]@{
            setup = "setup.cmd"
            doctor = "doctor.cmd"
            start = "start.cmd"
            stop = "stop.cmd"
            status = "status.cmd"
            reset = "reset.cmd"
        }
        files = $files
    }
    $manifestPath = Join-Path $packageRoot "manifest.json"
    $manifestText = (($manifest | ConvertTo-Json -Depth 8) -replace "`r`n", "`n").TrimEnd("`n") + "`n"
    [System.IO.File]::WriteAllText($manifestPath, $manifestText, (New-Object System.Text.UTF8Encoding($false)))
    $manifestHash = Get-Sha256 -Path $manifestPath
    Set-Content -LiteralPath (Join-Path $packageRoot "manifest.sha256") -Value "$manifestHash  manifest.json" -Encoding ASCII

    New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
    Remove-Item -LiteralPath $zipPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $zipChecksumPath -Force -ErrorAction SilentlyContinue
    Compress-Archive -LiteralPath $packageRoot -DestinationPath $zipPath -CompressionLevel Optimal
    $zipHash = Get-Sha256 -Path $zipPath
    Set-Content -LiteralPath $zipChecksumPath -Value "$zipHash  $([System.IO.Path]::GetFileName($zipPath))" -Encoding ASCII

    Write-Host "Portable artifact: $zipPath"
    Write-Host "SHA-256 file:     $zipChecksumPath"
} finally {
    if (Test-Path -LiteralPath $stageParent) {
        $resolvedStage = [System.IO.Path]::GetFullPath($stageParent)
        $tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
        if ($resolvedStage.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase) -and
            (Split-Path -Leaf $resolvedStage).StartsWith("myai-portable-")) {
            Remove-Item -LiteralPath $resolvedStage -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}
