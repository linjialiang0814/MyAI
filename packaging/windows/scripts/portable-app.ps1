param(
    [Parameter(Position = 0)]
    [ValidateSet("setup", "doctor", "start", "stop", "status", "reset")]
    [string]$Action = "status",
    [switch]$Force,
    [switch]$SkipDependencies,
    [switch]$Offline,
    [string]$WheelDirectory = "",
    [switch]$NoBrowser,
    [switch]$Json
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = [System.IO.Path]::GetFullPath((Split-Path -Parent $ScriptDir))
$ConfigDir = Join-Path $Root "config"
$ConfigPath = Join-Path $ConfigDir "app.env"
$ConfigTemplate = Join-Path $ConfigDir "app.env.example"
$DataDir = Join-Path $Root "data"
$RuntimeDir = Join-Path $Root "runtime"
$LogDir = Join-Path $RuntimeDir "logs"
$VenvDir = Join-Path $RuntimeDir "python"
$PythonPidPath = Join-Path $RuntimeDir "python.pid.json"
$JavaPidPath = Join-Path $RuntimeDir "java.pid.json"
$MaxPackageRootLength = 100

function Test-PackageRootLength {
    param([Parameter(Mandatory = $true)][string]$Path)
    return ([System.IO.Path]::GetFullPath($Path).TrimEnd("\").Length -le $MaxPackageRootLength)
}

function Assert-PackageRootLength {
    if (-not (Test-PackageRootLength -Path $Root)) {
        throw "The extracted package path is too long ($($Root.Length) characters; maximum $MaxPackageRootLength). Move the package to a short user-writable path such as C:\MyAI, then rerun setup.cmd."
    }
}

function Write-Check {
    param([string]$Level, [string]$Name, [string]$Message)
    $script:DoctorChecks += [ordered]@{ level = $Level.ToLowerInvariant(); name = $Name; message = $Message }
    if (-not $script:DoctorJsonMode) {
        $color = if ($Level -eq "OK") { "Green" } elseif ($Level -eq "WARN") { "Yellow" } else { "Red" }
        Write-Host ("[{0}] {1}: {2}" -f $Level, $Name, $Message) -ForegroundColor $color
    }
}

function Clear-InheritedRuntimeEnvironment {
    $names = @(
        [Environment]::GetEnvironmentVariables("Process").Keys |
            ForEach-Object { [string]$_ } |
            Where-Object {
                $_ -match "^(MYAI_|ARK_|SPRING_)" -or
                $_ -match "^PIP_" -or
                $_ -in @("JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS", "PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE")
            }
    )
    foreach ($name in $names) {
        [Environment]::SetEnvironmentVariable($name, $null, "Process")
    }
    # Windows environment names are case-insensitive, but a process launched
    # from a case-sensitive host can contain both PATH and Path. Start-Process
    # rejects such a dictionary, so collapse this one standard variable.
    $pathEntries = @(
        [Environment]::GetEnvironmentVariables("Process").Keys |
            ForEach-Object { [string]$_ } |
            Where-Object { $_.Equals("PATH", [System.StringComparison]::OrdinalIgnoreCase) }
    )
    if ($pathEntries.Count -gt 1) {
        $pathValue = [Environment]::GetEnvironmentVariable("PATH", "Process")
        foreach ($name in $pathEntries) {
            [Environment]::SetEnvironmentVariable($name, $null, "Process")
        }
        [Environment]::SetEnvironmentVariable("Path", $pathValue, "Process")
    }
}

function Set-PackageLocalTemp {
    $localTemp = Join-Path $RuntimeDir "temp"
    New-Item -ItemType Directory -Force -Path $localTemp | Out-Null
    $env:TEMP = $localTemp
    $env:TMP = $localTemp
    return $localTemp
}

function Get-ConfigValues {
    $values = @{}
    if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
        return $values
    }
    foreach ($raw in Get-Content -LiteralPath $ConfigPath) {
        $line = $raw.Trim()
        if ($line.Length -eq 0 -or $line.StartsWith("#")) { continue }
        $parts = $line.Split("=", 2)
        if ($parts.Count -ne 2 -or $parts[0].Trim() -notmatch "^[A-Z][A-Z0-9_]*$") {
            throw "Invalid configuration line in config/app.env."
        }
        $name = $parts[0].Trim()
        if ($name -match "^(SPRING_|PIP_|JAVA_TOOL_OPTIONS$|JDK_JAVA_OPTIONS$|_JAVA_OPTIONS$|PYTHONPATH$|PYTHONHOME$|PYTHONUSERBASE$|TEMP$|TMP$)") {
            throw "Configuration variable is reserved by the portable runtime: $name"
        }
        if ($name -notin @("PYTHON_PORT", "JAVA_PORT") -and
            -not $name.StartsWith("MYAI_", [System.StringComparison]::Ordinal) -and
            -not $name.StartsWith("ARK_", [System.StringComparison]::Ordinal)) {
            throw "Configuration variable is outside the portable allowlist: $name"
        }
        $values[$name] = $parts[1]
    }
    return $values
}

function Get-ConfiguredPort {
    param([hashtable]$Values, [string]$Name, [int]$Default)
    if (-not $Values.ContainsKey($Name)) { return $Default }
    $number = 0
    if (-not [int]::TryParse($Values[$Name], [ref]$number) -or $number -lt 1024 -or $number -gt 65535) {
        throw "$Name must be an integer from 1024 to 65535."
    }
    return $number
}

function Get-PythonLauncher {
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($null -ne $py) {
        try {
            $version = (& $py.Source -3.12 -c "import struct,sys; print('%d.%d:%d' % (sys.version_info.major,sys.version_info.minor,struct.calcsize('P')*8))" 2>$null).Trim()
            if ($version -eq "3.12:64") { return @{ File = $py.Source; Prefix = @("-3.12") } }
        } catch {}
    }
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($null -ne $python) {
        try {
            $version = (& $python.Source -c "import struct,sys; print('%d.%d:%d' % (sys.version_info.major,sys.version_info.minor,struct.calcsize('P')*8))" 2>$null).Trim()
            if ($version -eq "3.12:64") { return @{ File = $python.Source; Prefix = @() } }
        } catch {}
    }
    return $null
}

function Get-JavaExe {
    if ($env:JAVA_HOME) {
        $candidate = Join-Path $env:JAVA_HOME "bin\java.exe"
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
    $java = Get-Command java.exe -ErrorAction SilentlyContinue
    if ($null -ne $java) { return $java.Source }
    return ""
}

function Get-JavaMajor {
    param([string]$JavaExe)
    if ($JavaExe.Trim().Length -eq 0) { return 0 }
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = (& $JavaExe -version 2>&1 | Select-Object -First 1).ToString()
        if ($output -match 'version "1\.(\d+)') { return [int]$Matches[1] }
        if ($output -match 'version "(\d+)') { return [int]$Matches[1] }
    } catch {} finally { $ErrorActionPreference = $previousPreference }
    return 0
}

function Test-Java64Bit {
    param([string]$JavaExe)
    if ($JavaExe.Trim().Length -eq 0) { return $false }
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = (& $JavaExe -XshowSettings:properties -version 2>&1 | Out-String)
        return $output -match "sun\.arch\.data\.model\s*=\s*64"
    } catch {
        return $false
    } finally { $ErrorActionPreference = $previousPreference }
}

function Test-PortOpen {
    param([int]$Port)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $wait = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        return $wait.AsyncWaitHandle.WaitOne(500, $false) -and ($client.EndConnect($wait) -eq $null)
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Wait-Port {
    param([int]$Port, [int]$TimeoutSeconds)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortOpen -Port $Port) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Get-OwnedProcess {
    param([string]$MetadataPath, [ValidateSet("python", "java")][string]$ExpectedRole)
    if (-not (Test-Path -LiteralPath $MetadataPath -PathType Leaf)) { return $null }
    try {
        $metadata = Get-Content -LiteralPath $MetadataPath -Raw | ConvertFrom-Json
        if ([int]$metadata.schema_version -ne 1 -or [string]$metadata.role -cne $ExpectedRole) { return $null }
        if (-not [System.IO.Path]::GetFullPath([string]$metadata.package_root).TrimEnd("\").Equals(
            $Root.TrimEnd("\"),
            [System.StringComparison]::OrdinalIgnoreCase
        )) { return $null }
        $process = Get-Process -Id ([int]$metadata.pid) -ErrorAction SilentlyContinue
        if ($null -eq $process) { return $null }
        if ([long]$process.StartTime.ToUniversalTime().Ticks -ne [long]$metadata.start_time_utc_ticks) { return $null }
        if (-not [System.IO.Path]::GetFullPath($process.Path).Equals(
            [System.IO.Path]::GetFullPath([string]$metadata.executable_path),
            [System.StringComparison]::OrdinalIgnoreCase
        )) { return $null }
        $commandLine = $null
        $commandLineReadable = $false
        try {
            $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $($process.Id)" -ErrorAction Stop
            if ($null -eq $processInfo) { return $null }
            $commandLine = [string]$processInfo.CommandLine
            $commandLineReadable = $true
        } catch [Microsoft.Management.Infrastructure.CimException] {
            # Some managed Windows environments deny WMI/CIM process-command reads.
            # The canonical package root, role, PID, exact start time and executable
            # checks above remain mandatory; command marker is defense-in-depth.
        } catch [System.Management.Automation.CommandNotFoundException] {
            # Windows PowerShell 5.1 normally has Get-CimInstance, but minimal hosts
            # may omit it. Do not make safe PID ownership unusable in that case.
        }
        if ($commandLineReadable -and (
            [string]::IsNullOrWhiteSpace($commandLine) -or
            $commandLine.IndexOf([string]$metadata.command_marker, [System.StringComparison]::OrdinalIgnoreCase) -lt 0
        )) { return $null }
        return $process
    } catch {
        return $null
    }
}

function Get-ProcessMetadataState {
    param([string]$MetadataPath, [ValidateSet("python", "java")][string]$ExpectedRole)
    if (-not (Test-Path -LiteralPath $MetadataPath -PathType Leaf)) { return "absent" }
    if ($null -ne (Get-OwnedProcess -MetadataPath $MetadataPath -ExpectedRole $ExpectedRole)) { return "running" }
    return "stale"
}

function Write-ProcessMetadata {
    param(
        [System.Diagnostics.Process]$Process,
        [string]$Role,
        [string]$Path,
        [string]$CommandMarker,
        [string]$ExpectedExecutablePath,
        [ValidateRange(1024, 65535)]
        [int]$ServicePort
    )
    if ([string]::IsNullOrWhiteSpace($ExpectedExecutablePath)) {
        throw "Expected executable path is required for $Role process metadata."
    }
    $resolvedExecutablePath = [System.IO.Path]::GetFullPath(([string]$ExpectedExecutablePath).Trim())
    [ordered]@{
        schema_version = 1
        role = $Role
        pid = $Process.Id
        start_time_utc_ticks = $Process.StartTime.ToUniversalTime().Ticks
        package_root = $Root
        executable_path = $resolvedExecutablePath
        command_marker = $CommandMarker
        service_port = $ServicePort
    } | ConvertTo-Json | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Get-NativeProcessTreeIds {
    param([int]$ProcessId)
    if ($null -eq ("MyAI.PortableProcessTree" -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Runtime.InteropServices;

namespace MyAI {
    public static class PortableProcessTree {
        private const uint TH32CS_SNAPPROCESS = 0x00000002;

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
        private struct PROCESSENTRY32 {
            public uint dwSize;
            public uint cntUsage;
            public uint th32ProcessID;
            public IntPtr th32DefaultHeapID;
            public uint th32ModuleID;
            public uint cntThreads;
            public uint th32ParentProcessID;
            public int pcPriClassBase;
            public uint dwFlags;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)]
            public string szExeFile;
        }

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr CreateToolhelp32Snapshot(uint flags, uint processId);

        [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
        private static extern bool Process32First(IntPtr snapshot, ref PROCESSENTRY32 entry);

        [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
        private static extern bool Process32Next(IntPtr snapshot, ref PROCESSENTRY32 entry);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CloseHandle(IntPtr handle);

        public static int[] GetIdsDeepestFirst(int rootProcessId) {
            IntPtr snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
            if (snapshot == new IntPtr(-1)) {
                throw new Win32Exception(Marshal.GetLastWin32Error());
            }

            Dictionary<int, List<int>> childrenByParent = new Dictionary<int, List<int>>();
            try {
                PROCESSENTRY32 entry = new PROCESSENTRY32();
                entry.dwSize = (uint)Marshal.SizeOf(typeof(PROCESSENTRY32));
                if (Process32First(snapshot, ref entry)) {
                    do {
                        int parentId = unchecked((int)entry.th32ParentProcessID);
                        int childId = unchecked((int)entry.th32ProcessID);
                        List<int> children;
                        if (!childrenByParent.TryGetValue(parentId, out children)) {
                            children = new List<int>();
                            childrenByParent[parentId] = children;
                        }
                        children.Add(childId);
                        entry.dwSize = (uint)Marshal.SizeOf(typeof(PROCESSENTRY32));
                    } while (Process32Next(snapshot, ref entry));
                }
            } finally {
                CloseHandle(snapshot);
            }

            List<int> rootFirst = new List<int>();
            Stack<int> pending = new Stack<int>();
            HashSet<int> seen = new HashSet<int>();
            pending.Push(rootProcessId);
            while (pending.Count > 0) {
                int current = pending.Pop();
                if (!seen.Add(current)) { continue; }
                rootFirst.Add(current);
                List<int> children;
                if (childrenByParent.TryGetValue(current, out children)) {
                    foreach (int child in children) { pending.Push(child); }
                }
            }
            rootFirst.Reverse();
            return rootFirst.ToArray();
        }
    }
}
'@
    }
    return @([MyAI.PortableProcessTree]::GetIdsDeepestFirst($ProcessId))
}

function Invoke-TaskKillTree {
    param([int]$ProcessId, [switch]$Force)
    $arguments = @("/PID", [string]$ProcessId, "/T")
    if ($Force) { $arguments += "/F" }
    try {
        $taskkill = Start-Process -FilePath "taskkill.exe" -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
        if ($taskkill.ExitCode -eq 0) { return $true }
    } catch {
        if (-not $Force) { return $false }
    }
    if (-not $Force) { return $false }

    # Some managed Windows environments allow terminating owned processes but
    # deny taskkill's tree enumeration. Fall back to the native Toolhelp
    # snapshot API, stopping descendants before the already-validated root.
    try {
        $treeIds = @(Get-NativeProcessTreeIds -ProcessId $ProcessId)
        foreach ($treeId in $treeIds) {
            Stop-Process -Id $treeId -Force -ErrorAction SilentlyContinue
        }
        return $null -eq (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
    } catch {
        return $false
    }
}

function Stop-OwnedProcess {
    param(
        [string]$Name,
        [string]$MetadataPath,
        [ValidateSet("python", "java")][string]$ExpectedRole,
        [int]$ExpectedPort = 0
    )
    if ($ExpectedPort -le 0 -and (Test-Path -LiteralPath $MetadataPath -PathType Leaf)) {
        try {
            $storedPort = [int](Get-Content -LiteralPath $MetadataPath -Raw | ConvertFrom-Json).service_port
            if ($storedPort -ge 1024 -and $storedPort -le 65535) { $ExpectedPort = $storedPort }
        } catch {}
    }
    $process = Get-OwnedProcess -MetadataPath $MetadataPath -ExpectedRole $ExpectedRole
    if ($null -eq $process) {
        if (Test-Path -LiteralPath $MetadataPath) {
            if ($ExpectedPort -gt 0 -and (Test-PortOpen -Port $ExpectedPort)) {
                Write-Warning "$Name PID metadata is stale while port $ExpectedPort is still open; ownership metadata was preserved."
            } else {
                Write-Warning "$Name PID metadata is stale; no process was stopped."
                Remove-Item -LiteralPath $MetadataPath -Force
            }
        }
        return
    }
    Write-Host "Stopping owned $Name process tree (PID $($process.Id)) ..."
    $gracefulRequested = Invoke-TaskKillTree -ProcessId $process.Id
    $deadline = if ($gracefulRequested) { (Get-Date).AddSeconds(10) } else { Get-Date }
    while ((Get-Date) -lt $deadline -and (
        $null -ne (Get-Process -Id $process.Id -ErrorAction SilentlyContinue) -or
        ($ExpectedPort -gt 0 -and (Test-PortOpen -Port $ExpectedPort))
    )) {
        Start-Sleep -Milliseconds 250
    }
    if ($null -ne (Get-Process -Id $process.Id -ErrorAction SilentlyContinue)) {
        $sameProcess = Get-OwnedProcess -MetadataPath $MetadataPath -ExpectedRole $ExpectedRole
        if ($null -ne $sameProcess) {
            Invoke-TaskKillTree -ProcessId $sameProcess.Id -Force | Out-Null
            $forceDeadline = (Get-Date).AddSeconds(5)
            while ((Get-Date) -lt $forceDeadline -and (
                $null -ne (Get-Process -Id $process.Id -ErrorAction SilentlyContinue) -or
                ($ExpectedPort -gt 0 -and (Test-PortOpen -Port $ExpectedPort))
            )) {
                Start-Sleep -Milliseconds 100
            }
        }
    }
    $rootStopped = $null -eq (Get-Process -Id $process.Id -ErrorAction SilentlyContinue)
    $portStopped = $ExpectedPort -le 0 -or -not (Test-PortOpen -Port $ExpectedPort)
    if ($rootStopped -and $portStopped) {
        Remove-Item -LiteralPath $MetadataPath -Force -ErrorAction SilentlyContinue
    } else {
        Write-Warning "$Name process tree or port $ExpectedPort could not be stopped; ownership metadata was preserved."
    }
}

function Stop-PortableApp {
    Stop-OwnedProcess -Name "Java" -MetadataPath $JavaPidPath -ExpectedRole "java"
    Stop-OwnedProcess -Name "Python" -MetadataPath $PythonPidPath -ExpectedRole "python"
}

function Protect-ConfigFile {
    try {
        $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
        $sid = $identity.User.Value
        & icacls.exe $ConfigPath /inheritance:r /grant:r "*$($sid):(R,W)" *> $null
        if ($LASTEXITCODE -ne 0) { throw "icacls exit code $LASTEXITCODE" }
    } catch {
        Write-Warning "Could not narrow config/app.env ACL. Restrict this file manually before adding secrets."
    }
}

function New-RandomPassword {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

function Invoke-Setup {
    Clear-InheritedRuntimeEnvironment
    Assert-PackageRootLength
    New-Item -ItemType Directory -Force -Path $ConfigDir, $DataDir, $RuntimeDir, $LogDir | Out-Null
    Set-PackageLocalTemp | Out-Null
    if (-not (Test-PackageInventory)) { throw "Package inventory validation failed; obtain a fresh verified artifact." }
    if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
        if (-not (Test-Path -LiteralPath $ConfigTemplate -PathType Leaf)) { throw "config/app.env.example is missing." }
        $password = New-RandomPassword
        $content = Get-Content -LiteralPath $ConfigTemplate -Raw
        $content = [regex]::Replace($content, "(?m)^MYAI_LOCAL_PASSWORD=.*$", "MYAI_LOCAL_PASSWORD=$password")
        Set-Content -LiteralPath $ConfigPath -Value $content -Encoding UTF8
        Protect-ConfigFile
        Write-Host "Created private config/app.env with a random local password (not displayed)."
    } else {
        Protect-ConfigFile
        Write-Host "Keeping existing config/app.env."
    }

    $launcher = Get-PythonLauncher
    if ($null -eq $launcher) { throw "64-bit CPython 3.12 was not found. Install it, then rerun setup.cmd." }
    $venvPython = Join-Path $VenvDir "Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        $arguments = @($launcher.Prefix) + @("-m", "venv", $VenvDir)
        & $launcher.File @arguments
        if ($LASTEXITCODE -ne 0) { throw "Could not create the Python environment." }
    }
    if (-not $SkipDependencies) {
        $pipArguments = @("-m", "pip", "--isolated", "install", "--disable-pip-version-check", "--no-cache-dir")
        if ($Offline) {
            if ($WheelDirectory.Trim().Length -eq 0) { throw "-Offline requires -WheelDirectory <path>." }
            $wheelPath = [System.IO.Path]::GetFullPath($WheelDirectory)
            if (-not (Test-Path -LiteralPath $wheelPath -PathType Container)) { throw "Wheel directory does not exist: $wheelPath" }
            $pipArguments += @("--no-index", "--find-links", $wheelPath)
        }
        $pipArguments += @("-r", (Join-Path $Root "app\python\requirements.txt"))
        & $venvPython @pipArguments
        if ($LASTEXITCODE -ne 0) { throw "Python dependency installation failed." }
    }
    Write-Host "Setup completed. Run doctor.cmd next."
}

function Test-PackageInventory {
    $manifestPath = Join-Path $Root "manifest.json"
    $checksumPath = Join-Path $Root "manifest.sha256"
    if (-not (Test-Path -LiteralPath $manifestPath) -or -not (Test-Path -LiteralPath $checksumPath)) { return $false }
    $line = (Get-Content -LiteralPath $checksumPath -Raw).Trim()
    if ($line -notmatch "^([0-9a-fA-F]{64})\s{2}manifest\.json$") { return $false }
    if ((Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Matches[1].ToLowerInvariant()) { return $false }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ([int]$manifest.schema_version -ne 1 -or [string]$manifest.product -ne "MyAI" -or [string]$manifest.target -ne "windows-x64") { return $false }
    $expected = @("manifest.json", "manifest.sha256")
    foreach ($file in @($manifest.files)) {
        $relative = [string]$file.path
        if ($relative.Length -eq 0 -or $relative.Contains("\") -or $relative.StartsWith("/") -or $relative -match "(^|/)\.\.(/|$)") { return $false }
        $expected += $relative
        $path = Join-Path $Root (([string]$file.path) -replace "/", "\")
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return $false }
        $info = Get-Item -LiteralPath $path
        if ([long]$info.Length -ne [long]$file.size) { return $false }
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne ([string]$file.sha256).ToLowerInvariant()) { return $false }
    }
    $actualImmutable = @(
        Get-ChildItem -LiteralPath $Root -Recurse -File -Force |
            ForEach-Object { $_.FullName.Substring($Root.Length + 1).Replace("\", "/") } |
            Where-Object {
                $_ -ne "config/app.env" -and
                -not $_.StartsWith("data/", [System.StringComparison]::OrdinalIgnoreCase) -and
                -not $_.StartsWith("runtime/", [System.StringComparison]::OrdinalIgnoreCase)
            }
    )
    if (@($actualImmutable | Where-Object { $_ -notin $expected }).Count -gt 0 -or
        @($expected | Where-Object { $_ -notin $actualImmutable }).Count -gt 0) { return $false }
    return $true
}

function Invoke-Doctor {
    param([switch]$OutputJson)
    Clear-InheritedRuntimeEnvironment
    $script:DoctorJsonMode = [bool]$OutputJson
    $script:DoctorChecks = @()
    $failures = 0
    if (Test-PackageRootLength -Path $Root) {
        Write-Check "OK" "Package path" "package root length is safe for pinned dependencies"
    } else {
        Write-Check "FAIL" "Package path" "path is $($Root.Length) characters; move the package to a short user-writable path such as C:\MyAI (maximum $MaxPackageRootLength)"
        $failures++
    }
    Set-PackageLocalTemp | Out-Null
    if (Test-PackageInventory) { Write-Check "OK" "Package" "manifest and packaged files are intact" } else { Write-Check "FAIL" "Package" "manifest validation failed"; $failures++ }
    if (Test-Path -LiteralPath $ConfigPath -PathType Leaf) {
        try {
            $doctorConfig = Get-ConfigValues
            if (-not $doctorConfig.ContainsKey("MYAI_LOCAL_PASSWORD") -or ([string]$doctorConfig["MYAI_LOCAL_PASSWORD"]).Length -lt 24) {
                throw "local password is missing or too short"
            }
            Write-Check "OK" "Configuration" "config/app.env has a non-default local password"
        } catch {
            Write-Check "FAIL" "Configuration" "config/app.env is invalid; rerun setup after safely removing the file"
            $failures++
        }
    } else { Write-Check "FAIL" "Configuration" "run setup.cmd first"; $failures++ }
    $venvPython = Join-Path $VenvDir "Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
        try {
            $value = (& $venvPython -c "import fastapi,uvicorn,chromadb,struct,sys; print('%d.%d:%d' % (sys.version_info.major,sys.version_info.minor,struct.calcsize('P')*8))").Trim()
            if ($value -eq "3.12:64") { Write-Check "OK" "Python" "isolated Python 3.12 x64 dependencies are ready" } else { throw "unexpected runtime $value" }
        } catch { Write-Check "FAIL" "Python" "isolated dependencies are incomplete"; $failures++ }
    } else { Write-Check "FAIL" "Python" "run setup.cmd first"; $failures++ }
    $java = Get-JavaExe
    $major = Get-JavaMajor -JavaExe $java
    if ($major -ge 17 -and (Test-Java64Bit -JavaExe $java)) { Write-Check "OK" "Java" "64-bit Java $major is available" } else { Write-Check "FAIL" "Java" "64-bit Java 17 or later is required"; $failures++ }
    foreach ($path in @($DataDir, $RuntimeDir)) {
        try {
            New-Item -ItemType Directory -Force -Path $path | Out-Null
            $probe = Join-Path $path ".write-probe"
            Set-Content -LiteralPath $probe -Value "ok" -Encoding ASCII
            Remove-Item -LiteralPath $probe -Force
            Write-Check "OK" "Writable" $path
        } catch { Write-Check "FAIL" "Writable" $path; $failures++ }
    }
    return [ordered]@{
        schema_version = 1
        status = $(if ($failures -eq 0) { "passed" } else { "failed" })
        failures = $failures
        checks = @($script:DoctorChecks)
    }
}

function Set-PortableEnvironment {
    param([hashtable]$Values, [int]$PythonPort, [int]$JavaPort)
    Clear-InheritedRuntimeEnvironment
    foreach ($key in $Values.Keys) {
        if ($key -notin @("PYTHON_PORT", "JAVA_PORT")) {
            $value = [string]$Values[$key]
            if ($value.Length -gt 0) {
                [Environment]::SetEnvironmentVariable($key, $value, "Process")
            } else {
                [Environment]::SetEnvironmentVariable($key, "", "Process")
            }
        }
    }
    $chroma = (Join-Path $DataDir "chroma").Replace("\", "/")
    $knowledge = (Join-Path $DataDir "knowledge").Replace("\", "/")
    $memorySettings = (Join-Path $DataDir "memory-settings").Replace("\", "/")
    $runtimeDb = (Join-Path $DataDir "agent-runtime\runtime.db").Replace("\", "/")
    $javaDb = (Join-Path $DataDir "myai-local.db").Replace("\", "/")
    $localTemp = Set-PackageLocalTemp
    $env:MYAI_CHROMA_DIR = $chroma
    $env:MYAI_KNOWLEDGE_DATA_DIR = $knowledge
    $env:MYAI_MEMORY_SETTINGS_DIR = $memorySettings
    $env:MYAI_RUNTIME_DB_PATH = $runtimeDb
    $env:MYAI_OBSERVABILITY_STORE_PATH = (Join-Path $DataDir "observability\eval_runs.jsonl").Replace("\", "/")
    $env:MYAI_EVAL_WORK_DIR = (Join-Path $RuntimeDir "eval-work").Replace("\", "/")
    $env:SPRING_PROFILES_ACTIVE = "local"
    $env:MYAI_AUTH_MODE = "local"
    $env:DB_URL = "jdbc:sqlite:$javaDb"
    $env:DB_USERNAME = ""
    $env:DB_PASSWORD = ""
    $env:SERVER_ADDRESS = "127.0.0.1"
    $env:SERVER_PORT = [string]$JavaPort
    $env:PYTHON_SERVICE_BASE_URL = "http://127.0.0.1:$PythonPort"
    $env:PYTHONUNBUFFERED = "1"
    $env:PYTHONDONTWRITEBYTECODE = "1"
    $env:TEMP = $localTemp
    $env:TMP = $localTemp
    if ([string]::IsNullOrWhiteSpace($env:MYAI_MCP_FILESYSTEM_ROOTS)) {
        $env:MYAI_MCP_FILESYSTEM_ROOTS = (Join-Path $Root "demo")
    }
    if ([string]::IsNullOrWhiteSpace($env:MYAI_MCP_GIT_ENABLED)) {
        $env:MYAI_MCP_GIT_ENABLED = "false"
    }
}

function Start-PortableApp {
    $doctorResult = Invoke-Doctor
    if ([int]$doctorResult.failures -gt 0) { throw "Doctor found $($doctorResult.failures) blocking problem(s)." }
    Write-Host "Doctor passed."
    $values = Get-ConfigValues
    $pythonPort = Get-ConfiguredPort -Values $values -Name "PYTHON_PORT" -Default 8000
    $javaPort = Get-ConfiguredPort -Values $values -Name "JAVA_PORT" -Default 8080
    if ($pythonPort -eq $javaPort) { throw "PYTHON_PORT and JAVA_PORT must be different." }
    New-Item -ItemType Directory -Force -Path $DataDir, $RuntimeDir, $LogDir | Out-Null
    Set-PortableEnvironment -Values $values -PythonPort $pythonPort -JavaPort $javaPort

    $python = Get-OwnedProcess -MetadataPath $PythonPidPath -ExpectedRole "python"
    if ($null -eq $python) {
        if (Test-PortOpen -Port $pythonPort) { throw "Port $pythonPort is already used by a process not owned by this package." }
        Remove-Item -LiteralPath $PythonPidPath -Force -ErrorAction SilentlyContinue
        $pythonExe = Join-Path $VenvDir "Scripts\python.exe"
        $pythonAppDir = Join-Path $Root "app\python"
        $python = Start-Process -FilePath $pythonExe `
            -ArgumentList @("-m", "uvicorn", "app.main:app", "--app-dir", ('"{0}"' -f $pythonAppDir), "--host", "127.0.0.1", "--port", $pythonPort) `
            -WorkingDirectory (Join-Path $Root "app\python") -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $LogDir "python.out.log") `
            -RedirectStandardError (Join-Path $LogDir "python.err.log")
        Write-ProcessMetadata -Process $python -Role "python" -Path $PythonPidPath -CommandMarker $pythonAppDir -ExpectedExecutablePath $pythonExe -ServicePort $pythonPort
        if (-not (Wait-Port -Port $pythonPort -TimeoutSeconds 60)) { Stop-PortableApp; throw "Python service did not become ready. See runtime/logs/python.err.log." }
    } elseif (-not (Test-PortOpen -Port $pythonPort)) {
        throw "The owned Python process is not listening on its configured port. Run stop.cmd, then start again."
    }

    $java = Get-OwnedProcess -MetadataPath $JavaPidPath -ExpectedRole "java"
    if ($null -eq $java) {
        if (Test-PortOpen -Port $javaPort) { Stop-OwnedProcess -Name "Python" -MetadataPath $PythonPidPath -ExpectedRole "python"; throw "Port $javaPort is already used by a process not owned by this package." }
        Remove-Item -LiteralPath $JavaPidPath -Force -ErrorAction SilentlyContinue
        $javaExe = Get-JavaExe
        $jarPath = Join-Path $Root "app\java\myai.jar"
        $javaTemp = Join-Path $RuntimeDir "java-tmp"
        New-Item -ItemType Directory -Force -Path $javaTemp | Out-Null
        $java = Start-Process -FilePath $javaExe -ArgumentList @(
            ('"-Djava.io.tmpdir={0}"' -f $javaTemp),
            ('"-Dorg.sqlite.tmpdir={0}"' -f $javaTemp),
            "-jar",
            ('"{0}"' -f $jarPath)
        ) -WorkingDirectory $Root -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $LogDir "java.out.log") `
            -RedirectStandardError (Join-Path $LogDir "java.err.log")
        Write-ProcessMetadata -Process $java -Role "java" -Path $JavaPidPath -CommandMarker $jarPath -ExpectedExecutablePath $javaExe -ServicePort $javaPort
        if (-not (Wait-Port -Port $javaPort -TimeoutSeconds 90)) { Stop-PortableApp; throw "Java service did not become ready. See runtime/logs/java.err.log." }
    } elseif (-not (Test-PortOpen -Port $javaPort)) {
        throw "The owned Java process is not listening on its configured port. Run stop.cmd, then start again."
    }
    Write-Host "MyAI is running at http://127.0.0.1:$javaPort"
    if (-not $NoBrowser) { Start-Process "http://127.0.0.1:$javaPort" }
}

function Show-Status {
    $values = Get-ConfigValues
    $pythonPort = Get-ConfiguredPort -Values $values -Name "PYTHON_PORT" -Default 8000
    $javaPort = Get-ConfiguredPort -Values $values -Name "JAVA_PORT" -Default 8080
    $python = Get-OwnedProcess -MetadataPath $PythonPidPath -ExpectedRole "python"
    $java = Get-OwnedProcess -MetadataPath $JavaPidPath -ExpectedRole "java"
    $pythonMetadataState = Get-ProcessMetadataState -MetadataPath $PythonPidPath -ExpectedRole "python"
    $javaMetadataState = Get-ProcessMetadataState -MetadataPath $JavaPidPath -ExpectedRole "java"
    Write-Host "Python: $(if ($null -ne $python -and (Test-PortOpen -Port $pythonPort)) { "owned/running pid=$($python.Id)" } elseif ($null -ne $python) { "owned process not listening pid=$($python.Id)" } elseif ($pythonMetadataState -eq "stale") { "stopped (stale PID metadata)" } elseif (Test-PortOpen -Port $pythonPort) { "port occupied by another process" } else { "stopped" })"
    Write-Host "Java:   $(if ($null -ne $java -and (Test-PortOpen -Port $javaPort)) { "owned/running pid=$($java.Id)" } elseif ($null -ne $java) { "owned process not listening pid=$($java.Id)" } elseif ($javaMetadataState -eq "stale") { "stopped (stale PID metadata)" } elseif (Test-PortOpen -Port $javaPort) { "port occupied by another process" } else { "stopped" })"
}

function Assert-SafeResetDirectory {
    param([string]$Path, [string]$ExpectedLeaf)
    $rootResolved = (Resolve-Path -LiteralPath $Root).Path.TrimEnd("\")
    $full = [System.IO.Path]::GetFullPath($Path).TrimEnd("\")
    if ((Split-Path -Leaf $full) -ne $ExpectedLeaf -or
        -not $full.Equals("$rootResolved\$ExpectedLeaf", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe reset target: $full"
    }
    if (Test-Path -LiteralPath $full) {
        $item = Get-Item -LiteralPath $full -Force
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Reset target must not be a link: $full" }
        if ((Resolve-Path -LiteralPath $full).Path.TrimEnd("\") -ne $full) { throw "Reset target path resolution changed: $full" }
        $links = @(Get-ChildItem -LiteralPath $full -Recurse -Force -ErrorAction Stop | Where-Object {
            ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0
        })
        if ($links.Count -gt 0) { throw "Reset target contains a link and was not removed: $($links[0].FullName)" }
    }
    return $full
}

function Invoke-Reset {
    Stop-PortableApp
    $safeData = Assert-SafeResetDirectory -Path $DataDir -ExpectedLeaf "data"
    $safeRuntime = Assert-SafeResetDirectory -Path $RuntimeDir -ExpectedLeaf "runtime"
    if (-not $Force) {
        $answer = Read-Host "Delete this package's data and runtime state? Type RESET to continue"
        if ($answer -cne "RESET") { Write-Host "Reset cancelled."; return }
    }
    foreach ($target in @($safeData, $safeRuntime)) {
        if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
    }
    New-Item -ItemType Directory -Force -Path $DataDir, $RuntimeDir | Out-Null
    Write-Host "Local data and runtime state were reset. config/app.env was preserved."
}

if ($Json -and $Action -ne "doctor") {
    throw "-Json is supported only by doctor.cmd."
}

switch ($Action) {
    "setup" { Invoke-Setup }
    "doctor" {
        $doctorResult = Invoke-Doctor -OutputJson:$Json
        if ($Json) {
            $doctorResult | ConvertTo-Json -Depth 5
        } elseif ([int]$doctorResult.failures -eq 0) {
            Write-Host "Doctor passed."
        }
        if ([int]$doctorResult.failures -gt 0) { exit 1 }
    }
    "start" { Start-PortableApp }
    "stop" { Stop-PortableApp; Show-Status }
    "status" { Show-Status }
    "reset" { Invoke-Reset }
}
