param(
    [Parameter(Mandatory = $true)]
    [string]$ArtifactPath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ArtifactPath = [System.IO.Path]::GetFullPath($ArtifactPath)
if (-not (Test-Path -LiteralPath $ArtifactPath -PathType Leaf)) {
    throw "Portable artifact does not exist: $ArtifactPath"
}
if ([System.IO.Path]::GetExtension($ArtifactPath).ToLowerInvariant() -ne ".zip") {
    throw "Portable artifact must be a .zip file."
}

function Get-Sha256 {
    param([string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Assert-ChecksumFile {
    param([string]$ChecksumPath, [string]$PayloadPath, [string]$ExpectedName)
    $line = (Get-Content -LiteralPath $ChecksumPath -Raw).Trim()
    if ($line -notmatch "^([0-9a-fA-F]{64})\s{2}(.+)$") {
        throw "Invalid checksum format: $ChecksumPath"
    }
    if ($Matches[2] -ne $ExpectedName) {
        throw "Checksum filename mismatch in $ChecksumPath."
    }
    $actual = Get-Sha256 -Path $PayloadPath
    if ($actual -ne $Matches[1].ToLowerInvariant()) {
        throw "SHA-256 mismatch for $PayloadPath"
    }
}

$externalChecksum = "$ArtifactPath.sha256"
if (Test-Path -LiteralPath $externalChecksum -PathType Leaf) {
    Assert-ChecksumFile -ChecksumPath $externalChecksum -PayloadPath $ArtifactPath -ExpectedName ([System.IO.Path]::GetFileName($ArtifactPath))
} else {
    throw "External ZIP checksum is required: $externalChecksum"
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::OpenRead($ArtifactPath)
try {
    if ($archive.Entries.Count -eq 0) {
        throw "Portable archive is empty."
    }
    $topLevels = @($archive.Entries | ForEach-Object { ($_.FullName -replace "\\", "/").Split("/")[0] } | Sort-Object -Unique)
    if ($topLevels.Count -ne 1 -or $topLevels[0] -notmatch "^MyAI-[0-9A-Za-z._-]+-windows-x64$") {
        throw "Portable archive must contain exactly one MyAI-<version>-windows-x64 root."
    }
    $rootName = $topLevels[0]
    $entryNames = @{}
    foreach ($entry in $archive.Entries) {
        $name = $entry.FullName -replace "\\", "/"
        if ($name.StartsWith("/") -or $name -match "(^|/)\.\.(/|$)" -or $name -match "^[A-Za-z]:") {
            throw "Unsafe archive path: $($entry.FullName)"
        }
        $normalizedName = $name.TrimEnd("/").ToLowerInvariant()
        if ($normalizedName.Length -gt 0) {
            if ($entryNames.ContainsKey($normalizedName)) {
                throw "Duplicate archive entry path: $name"
            }
            $entryNames[$normalizedName] = $true
        }
    }
} finally {
    $archive.Dispose()
}

$temp = Join-Path ([System.IO.Path]::GetTempPath()) ("myai-verify-" + [guid]::NewGuid().ToString("N"))
try {
    New-Item -ItemType Directory -Force -Path $temp | Out-Null
    Expand-Archive -LiteralPath $ArtifactPath -DestinationPath $temp -Force
    $packageRoot = Join-Path $temp $rootName
    $manifestPath = Join-Path $packageRoot "manifest.json"
    $manifestChecksum = Join-Path $packageRoot "manifest.sha256"
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf) -or
        -not (Test-Path -LiteralPath $manifestChecksum -PathType Leaf)) {
        throw "manifest.json or manifest.sha256 is missing."
    }
    Assert-ChecksumFile -ChecksumPath $manifestChecksum -PayloadPath $manifestPath -ExpectedName "manifest.json"

    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.schema_version -ne 1 -or $manifest.product -ne "MyAI" -or $manifest.target -ne "windows-x64") {
        throw "Unsupported portable manifest identity or schema."
    }
    if ($rootName -ne "MyAI-$($manifest.version)-windows-x64") {
        throw "Archive root does not match manifest version."
    }
    $requiredEntrypoints = @("setup.cmd", "doctor.cmd", "start.cmd", "stop.cmd", "status.cmd", "reset.cmd")
    foreach ($entrypoint in $requiredEntrypoints) {
        if (-not (Test-Path -LiteralPath (Join-Path $packageRoot $entrypoint) -PathType Leaf)) {
            throw "Required entrypoint is missing: $entrypoint"
        }
    }

    $expected = @{}
    foreach ($file in @($manifest.files)) {
        $relative = [string]$file.path
        if ($relative.Length -eq 0 -or $relative.Contains("\") -or $relative.StartsWith("/") -or
            $relative -match "(^|/)\.\.(/|$)" -or $expected.ContainsKey($relative)) {
            throw "Unsafe or duplicate manifest path: $relative"
        }
        $expected[$relative] = $file
    }
    $actualPaths = @(
        Get-ChildItem -LiteralPath $packageRoot -Recurse -File |
            ForEach-Object { $_.FullName.Substring($packageRoot.Length + 1).Replace("\", "/") } |
            Where-Object { $_ -notin @("manifest.json", "manifest.sha256") }
    )
    $unexpected = @($actualPaths | Where-Object { -not $expected.ContainsKey($_) })
    $missing = @($expected.Keys | Where-Object { $_ -notin $actualPaths })
    if ($unexpected.Count -gt 0 -or $missing.Count -gt 0) {
        throw "Manifest inventory mismatch. Missing=[$($missing -join ', ')] Unexpected=[$($unexpected -join ', ')]"
    }
    foreach ($relative in $expected.Keys) {
        $path = Join-Path $packageRoot ($relative -replace "/", "\")
        $info = Get-Item -LiteralPath $path
        if ([long]$info.Length -ne [long]$expected[$relative].size) {
            throw "Size mismatch: $relative"
        }
        if ((Get-Sha256 -Path $path) -ne ([string]$expected[$relative].sha256).ToLowerInvariant()) {
            throw "SHA-256 mismatch: $relative"
        }
    }
    Write-Host "Portable artifact verified: $ArtifactPath"
    Write-Host "Version: $($manifest.version); files: $($expected.Count)"
} finally {
    if (Test-Path -LiteralPath $temp) {
        Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
    }
}
