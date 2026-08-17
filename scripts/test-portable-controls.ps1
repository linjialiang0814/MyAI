param(
    [Parameter(Mandatory = $true)]
    [string]$PackageRoot
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$PackageRoot = [System.IO.Path]::GetFullPath($PackageRoot)
$controlPath = Join-Path $PackageRoot "scripts\portable-app.ps1"
if (-not (Test-Path -LiteralPath $controlPath -PathType Leaf)) {
    throw "Portable control script is missing: $controlPath"
}
$source = Get-Content -LiteralPath $controlPath -Raw
$switchOffset = $source.LastIndexOf('switch ($Action)')
if ($switchOffset -lt 0) { throw "Could not load portable control functions." }
$definitions = $source.Substring(0, $switchOffset)

$probePath = Join-Path $PackageRoot "runtime\control-test.ps1"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $probePath) | Out-Null
$probe = @"
$definitions

function Assert-True([bool]`$Condition, [string]`$Message) {
    if (-not `$Condition) { throw `$Message }
}

Assert-True (Test-PackageRootLength -Path `$Root) "Control package root exceeds the supported path length."
`$longRoot = "C:\" + ("x" * `$MaxPackageRootLength)
Assert-True (-not (Test-PackageRootLength -Path `$longRoot)) "An overlong package root was accepted."
`$pathGateRejected = `$false
`$savedRoot = `$Root
try {
    `$Root = `$longRoot
    try { Assert-PackageRootLength } catch { `$pathGateRejected = `$true }
} finally {
    `$Root = `$savedRoot
}
Assert-True `$pathGateRejected "Setup's overlong package-root preflight did not fail closed."

if (-not (Test-Path -LiteralPath `$ConfigPath)) {
    `$testConfig = (Get-Content -LiteralPath `$ConfigTemplate -Raw) -replace "(?m)^MYAI_LOCAL_PASSWORD=.*$", "MYAI_LOCAL_PASSWORD=portable-control-test-password"
    Set-Content -LiteralPath `$ConfigPath -Value `$testConfig -Encoding UTF8
}
`$config = Get-ConfigValues
`$env:MYAI_CHAT_PROVIDER = "parent-provider"
`$env:ARK_API_KEY = "parent-secret"
`$env:SPRING_APPLICATION_JSON = '{"server":{"address":"0.0.0.0"}}'
`$env:JAVA_TOOL_OPTIONS = "-Dserver.address=0.0.0.0"
`$env:JDK_JAVA_OPTIONS = "-Dspring.config.location=C:\foreign"
`$env:PYTHONPATH = "C:\foreign-python"
`$env:PYTHONHOME = "C:\foreign-home"
`$env:PYTHONUSERBASE = "C:\foreign-userbase"
`$env:PIP_TARGET = "C:\foreign-pip-target"
Clear-InheritedRuntimeEnvironment
Set-PackageLocalTemp | Out-Null
Assert-True ([string]::IsNullOrEmpty(`$env:MYAI_CHAT_PROVIDER)) "Preflight inherited a model provider."
Assert-True ([string]::IsNullOrEmpty(`$env:JAVA_TOOL_OPTIONS)) "Preflight inherited JAVA_TOOL_OPTIONS."
Assert-True ([string]::IsNullOrEmpty(`$env:PYTHONHOME)) "Preflight inherited PYTHONHOME."
Assert-True ([string]::IsNullOrEmpty(`$env:PYTHONUSERBASE)) "Preflight inherited PYTHONUSERBASE."
Assert-True ([string]::IsNullOrEmpty(`$env:PIP_TARGET)) "Preflight inherited PIP_TARGET."
Assert-True (`$env:TEMP -eq (Join-Path `$RuntimeDir "temp")) "Preflight TEMP is not package-local."
Assert-True (`$env:TMP -eq (Join-Path `$RuntimeDir "temp")) "Preflight TMP is not package-local."
`$env:MYAI_CHAT_PROVIDER = "parent-provider"
`$env:ARK_API_KEY = "parent-secret"
`$env:SPRING_APPLICATION_JSON = '{"server":{"address":"0.0.0.0"}}'
`$env:JAVA_TOOL_OPTIONS = "-Dserver.address=0.0.0.0"
`$env:JDK_JAVA_OPTIONS = "-Dspring.config.location=C:\foreign"
`$env:PYTHONPATH = "C:\foreign-python"
`$env:PYTHONHOME = "C:\foreign-home"
`$env:PYTHONUSERBASE = "C:\foreign-userbase"
`$env:PIP_TARGET = "C:\foreign-pip-target"
Set-PortableEnvironment -Values `$config -PythonPort 8000 -JavaPort 8080
Assert-True (`$env:MYAI_CHAT_PROVIDER -eq "stub") "Portable config did not override the parent provider."
Assert-True ([string]::IsNullOrEmpty(`$env:ARK_API_KEY)) "Portable environment inherited an ARK secret."
Assert-True ([string]::IsNullOrEmpty(`$env:SPRING_APPLICATION_JSON)) "Portable environment inherited Spring configuration."
Assert-True ([string]::IsNullOrEmpty(`$env:JAVA_TOOL_OPTIONS)) "Portable environment inherited JAVA_TOOL_OPTIONS."
Assert-True ([string]::IsNullOrEmpty(`$env:JDK_JAVA_OPTIONS)) "Portable environment inherited JDK_JAVA_OPTIONS."
Assert-True ([string]::IsNullOrEmpty(`$env:PYTHONPATH)) "Portable environment inherited PYTHONPATH."
Assert-True ([string]::IsNullOrEmpty(`$env:PYTHONHOME)) "Portable environment inherited PYTHONHOME."
Assert-True ([string]::IsNullOrEmpty(`$env:PYTHONUSERBASE)) "Portable environment inherited PYTHONUSERBASE."
Assert-True ([string]::IsNullOrEmpty(`$env:PIP_TARGET)) "Portable environment inherited PIP_TARGET."
Assert-True (`$env:PYTHONDONTWRITEBYTECODE -eq "1") "Python bytecode writes were not disabled."
Assert-True (`$env:TEMP -eq (Join-Path `$RuntimeDir "temp")) "TEMP is not package-local."
Assert-True (`$env:TMP -eq (Join-Path `$RuntimeDir "temp")) "TMP is not package-local."
Assert-True (`$env:MYAI_MCP_FILESYSTEM_ROOTS -eq (Join-Path `$Root "demo")) "Filesystem MCP root is not package/demo."
Assert-True (`$env:MYAI_MCP_GIT_ENABLED -eq "false") "Git MCP must be disabled in the portable baseline."

`$doctorRoundTrip = (Invoke-Doctor -OutputJson | ConvertTo-Json -Depth 5 | ConvertFrom-Json)
Assert-True (`$doctorRoundTrip.schema_version -eq 1) "Doctor JSON schema version is invalid."
Assert-True (`$doctorRoundTrip.status -in @("passed", "failed")) "Doctor JSON status is invalid."
Assert-True (`$doctorRoundTrip.failures -ge 0) "Doctor JSON failure count is invalid."
Assert-True (@(`$doctorRoundTrip.checks).Count -ge 6) "Doctor JSON checks are incomplete."

`$badConfig = Get-Content -LiteralPath `$ConfigPath -Raw
try {
    Add-Content -LiteralPath `$ConfigPath -Value "SPRING_APPLICATION_JSON={}" -Encoding UTF8
    `$reservedRejected = `$false
    try { Get-ConfigValues | Out-Null } catch { `$reservedRejected = `$true }
    Assert-True `$reservedRejected "Reserved configuration variable was accepted."
} finally {
    Set-Content -LiteralPath `$ConfigPath -Value `$badConfig -Encoding UTF8
}

`$foreignRoot = Join-Path (Split-Path -Parent `$Root) "foreign-package"
`$process = Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-Command", "Start-Sleep -Seconds 60", "portable-control-probe") -PassThru -WindowStyle Hidden
try {
    `$process.Refresh()
    [ordered]@{
        schema_version = 1
        role = "python"
        pid = `$process.Id
        start_time_utc_ticks = `$process.StartTime.ToUniversalTime().Ticks
        package_root = `$foreignRoot
        executable_path = `$process.Path
        command_marker = "portable-control-probe"
    } | ConvertTo-Json | Set-Content -LiteralPath `$PythonPidPath -Encoding UTF8
    Assert-True (`$null -eq (Get-OwnedProcess -MetadataPath `$PythonPidPath -ExpectedRole "python")) "Foreign package metadata was accepted."
    Stop-OwnedProcess -Name "Python" -MetadataPath `$PythonPidPath -ExpectedRole "python"
    Assert-True (`$null -ne (Get-Process -Id `$process.Id -ErrorAction SilentlyContinue)) "Foreign package process was stopped."
} finally {
    Stop-Process -Id `$process.Id -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath `$PythonPidPath -Force -ErrorAction SilentlyContinue
}

`$ownedMarker = "portable-owned-tree-probe"
`$ownedChildPidPath = Join-Path `$RuntimeDir "owned-child.pid"
`$ownedExecutable = (Get-Command "powershell.exe" -ErrorAction Stop).Source
Assert-True (-not [string]::IsNullOrWhiteSpace(`$ownedExecutable)) "PowerShell executable path is empty."
`$invalidPortMetadata = Join-Path `$RuntimeDir "invalid-port.pid.json"
`$invalidPortRejected = `$false
try {
    Write-ProcessMetadata -Process (Get-Process -Id `$PID) -Role "python" -Path `$invalidPortMetadata -CommandMarker "invalid-port-probe" -ExpectedExecutablePath `$ownedExecutable -ServicePort 0
} catch {
    `$invalidPortRejected = `$true
} finally {
    Remove-Item -LiteralPath `$invalidPortMetadata -Force -ErrorAction SilentlyContinue
}
Assert-True `$invalidPortRejected "Process metadata accepted an invalid service port."
`$ownedParentScript = Join-Path `$RuntimeDir "owned-parent.ps1"
`$ownedChildScript = Join-Path `$RuntimeDir "owned-child.ps1"
`$portReservation = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
try {
    `$portReservation.Start()
    `$ownedServicePort = [int]`$portReservation.LocalEndpoint.Port
} finally {
    `$portReservation.Stop()
}
Assert-True (`$ownedServicePort -ge 1024 -and `$ownedServicePort -le 65535) "Owned service probe did not obtain a valid port."
@'
param([Parameter(Mandatory = `$true)][int]`$Port)
`$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, `$Port)
try {
    `$listener.Start()
    Start-Sleep -Seconds 60
} finally {
    `$listener.Stop()
}
'@ | Set-Content -LiteralPath `$ownedChildScript -Encoding UTF8
@'
param(
    [Parameter(Mandatory = `$true)][string]`$ChildPidPath,
    [Parameter(Mandatory = `$true)][string]`$ChildScript,
    [Parameter(Mandatory = `$true)][int]`$ServicePort,
    [Parameter(Mandatory = `$true)][string]`$Marker
)
`$child = Start-Process -FilePath powershell.exe -ArgumentList @('-NoProfile', '-File', ('"{0}"' -f `$ChildScript), [string]`$ServicePort) -PassThru -WindowStyle Hidden
Set-Content -LiteralPath `$ChildPidPath -Value `$child.Id -Encoding ASCII
Start-Sleep -Seconds 60
# portable-owned-tree-probe
'@ | Set-Content -LiteralPath `$ownedParentScript -Encoding UTF8
`$ownedProcess = Start-Process -FilePath `$ownedExecutable -ArgumentList @(
    "-NoProfile",
    "-File",
    ('"{0}"' -f `$ownedParentScript),
    ('"{0}"' -f `$ownedChildPidPath),
    ('"{0}"' -f `$ownedChildScript),
    [string]`$ownedServicePort,
    `$ownedMarker
) -PassThru -WindowStyle Hidden
`$ownedChildPid = 0
try {
    `$ownedProcess.Refresh()
    Write-ProcessMetadata -Process `$ownedProcess -Role "python" -Path `$PythonPidPath -CommandMarker `$ownedMarker -ExpectedExecutablePath `$ownedExecutable -ServicePort `$ownedServicePort
    `$childDeadline = (Get-Date).AddSeconds(5)
    while ((Get-Date) -lt `$childDeadline -and (
        -not (Test-Path -LiteralPath `$ownedChildPidPath) -or
        (Get-Content -LiteralPath `$ownedChildPidPath -Raw -ErrorAction SilentlyContinue).Trim().Length -eq 0
    )) { Start-Sleep -Milliseconds 100 }
    `$ownedChildPid = [int](Get-Content -LiteralPath `$ownedChildPidPath -Raw).Trim()
    Assert-True (`$null -ne (Get-Process -Id `$ownedChildPid -ErrorAction SilentlyContinue)) "Owned process tree child was not created."
    `$portDeadline = (Get-Date).AddSeconds(5)
    while ((Get-Date) -lt `$portDeadline -and -not (Test-PortOpen -Port `$ownedServicePort)) { Start-Sleep -Milliseconds 100 }
    Assert-True (Test-PortOpen -Port `$ownedServicePort) "Owned process tree service port did not open."
    Stop-OwnedProcess -Name "Python" -MetadataPath `$PythonPidPath -ExpectedRole "python"
    Assert-True (`$null -eq (Get-Process -Id `$ownedProcess.Id -ErrorAction SilentlyContinue)) "Owned root process was not stopped."
    Assert-True (`$null -eq (Get-Process -Id `$ownedChildPid -ErrorAction SilentlyContinue)) "Owned child process was not stopped."
    Assert-True (-not (Test-PortOpen -Port `$ownedServicePort)) "Owned service port was not stopped."
    Assert-True (-not (Test-Path -LiteralPath `$PythonPidPath)) "Owned process metadata was not removed."
} finally {
    if (`$null -ne `$ownedProcess) { Invoke-TaskKillTree -ProcessId `$ownedProcess.Id -Force | Out-Null }
    if (`$ownedChildPid -gt 0) { Stop-Process -Id `$ownedChildPid -Force -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath `$PythonPidPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath `$ownedChildPidPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath `$ownedParentScript -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath `$ownedChildScript -Force -ErrorAction SilentlyContinue
}

`$nestedLink = Join-Path `$DataDir "nested-link"
New-Item -ItemType Directory -Force -Path `$DataDir | Out-Null
try {
    New-Item -ItemType Junction -Path `$nestedLink -Target (Join-Path `$Root "demo") -ErrorAction Stop | Out-Null
    `$resetRejected = `$false
    try { Assert-SafeResetDirectory -Path `$DataDir -ExpectedLeaf "data" | Out-Null } catch { `$resetRejected = `$true }
    Assert-True `$resetRejected "Reset accepted a descendant reparse point."
} finally {
    if (Test-Path -LiteralPath `$nestedLink) { [System.IO.Directory]::Delete(`$nestedLink) }
}

Write-Host "Portable control checks passed."
"@
Set-Content -LiteralPath $probePath -Value $probe -Encoding UTF8
try {
    & $probePath
} catch {
    Write-Host $_.ScriptStackTrace
    throw
} finally {
    Remove-Item -LiteralPath $probePath -Force -ErrorAction SilentlyContinue
}
