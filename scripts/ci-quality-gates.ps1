[CmdletBinding()]
param(
    [string]$NodeExecutable = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$Failures = New-Object System.Collections.Generic.List[string]

function Write-Gate {
    param([string]$Message)
    Write-Host ""
    Write-Host "== $Message =="
}

function Add-Failure {
    param([string]$Message)
    $Failures.Add($Message) | Out-Null
    Write-Host "FAIL: $Message" -ForegroundColor Red
}

function Test-FileSignature {
    param(
        [string]$Path,
        [byte[]]$Expected
    )

    $stream = [System.IO.File]::OpenRead($Path)
    try {
        if ($stream.Length -lt $Expected.Length) {
            return $false
        }
        $buffer = New-Object byte[] $Expected.Length
        $read = $stream.Read($buffer, 0, $buffer.Length)
        if ($read -ne $Expected.Length) {
            return $false
        }
        for ($index = 0; $index -lt $Expected.Length; $index += 1) {
            if ($buffer[$index] -ne $Expected[$index]) {
                return $false
            }
        }
        return $true
    } finally {
        $stream.Dispose()
    }
}

$ArtifactPatterns = @(
    "(^|/)(?:\.env|[^/]+\.env)(?:\.|$)",
    "(^|/)(\.venv|venv|target|build|dist|release-artifacts|logs?|\.runtime|\.tmp|\.ollama|models|chroma_db|knowledge_data|memory_settings)/",
    "(^|/)pytest-cache-files-[^/]+/",
    "\.(db|db-shm|db-wal|sqlite|sqlite3|log|pem|key|p12|pfx|jks|keystore|jar|exe|dll|msi|whl|pyz|gguf|safetensors|onnx|pt|pth|ckpt|zip(?:\.sha256)?)$"
)

function Test-IsForbiddenRepositoryArtifact {
    param([string]$RelativePath)

    $normalized = $RelativePath.Replace("\", "/")
    if ($normalized -match "(^|/)(?:\.env|[^/]+\.env)\.example$") {
        return $false
    }
    foreach ($pattern in $ArtifactPatterns) {
        if ($normalized -match $pattern) {
            return $true
        }
    }
    return $false
}

function Assert-RuleContracts {
    $cases = @(
        [pscustomobject]@{ Path = ".env"; Forbidden = $true },
        [pscustomobject]@{ Path = "config/app.env"; Forbidden = $true },
        [pscustomobject]@{ Path = "config/app.env.local"; Forbidden = $true },
        [pscustomobject]@{ Path = "myai-python-agent/.env.local"; Forbidden = $true },
        [pscustomobject]@{ Path = ".env.example"; Forbidden = $false },
        [pscustomobject]@{ Path = "config/app.env.example"; Forbidden = $false },
        [pscustomobject]@{ Path = "release/MyAI.zip.sha256"; Forbidden = $true },
        [pscustomobject]@{ Path = ".ollama/models/blobs/sha256-example"; Forbidden = $true },
        [pscustomobject]@{ Path = "models/qwen/model.gguf"; Forbidden = $true },
        [pscustomobject]@{ Path = "weights/embedding.safetensors"; Forbidden = $true },
        [pscustomobject]@{ Path = "myai-python-agent/app/model/model_factory.py"; Forbidden = $false }
    )
    foreach ($case in $cases) {
        $actual = Test-IsForbiddenRepositoryArtifact -RelativePath $case.Path
        if ($actual -ne $case.Forbidden) {
            throw "Internal artifact rule contract failed for '$($case.Path)'."
        }
    }
}

function Get-RepositoryFiles {
    Push-Location $Root
    try {
        $relativePaths = @(& git -c core.quotepath=false ls-files --cached --others --exclude-standard 2>$null)
        if ($LASTEXITCODE -ne 0) {
            throw "git ls-files failed with exit code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }

    return @(
        $relativePaths |
            Where-Object { $_.Trim().Length -gt 0 } |
            Sort-Object -Unique |
            ForEach-Object {
                [pscustomobject]@{
                    RelativePath = $_.Replace("\", "/")
                    FullPath = Join-Path $Root $_
                }
            } |
            Where-Object { Test-Path -LiteralPath $_.FullPath -PathType Leaf }
    )
}

function Resolve-NodeExecutable {
    if ($NodeExecutable.Trim().Length -gt 0) {
        if (Test-Path -LiteralPath $NodeExecutable -PathType Leaf) {
            return (Resolve-Path -LiteralPath $NodeExecutable).Path
        }
        $explicitCommand = Get-Command $NodeExecutable -ErrorAction SilentlyContinue
        if ($null -ne $explicitCommand) {
            return $explicitCommand.Source
        }
        throw "Node.js executable was not found: $NodeExecutable"
    }

    $pathCommand = Get-Command "node" -ErrorAction SilentlyContinue
    if ($null -ne $pathCommand) {
        return $pathCommand.Source
    }

    $bundledNode = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
    if (Test-Path -LiteralPath $bundledNode -PathType Leaf) {
        return $bundledNode
    }

    throw "Node.js 20 or newer is required for the frontend syntax gate."
}

Assert-RuleContracts
$RepositoryFiles = Get-RepositoryFiles
if ($RepositoryFiles.Count -eq 0) {
    throw "No repository files were discovered."
}

Write-Gate "Version marker"
$versionPath = Join-Path $Root "VERSION"
if (-not (Test-Path -LiteralPath $versionPath -PathType Leaf)) {
    Add-Failure "VERSION is missing."
} else {
    $version = (Get-Content -LiteralPath $versionPath -Raw -Encoding UTF8).Trim()
    if ($version -notmatch "^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$") {
        Add-Failure "VERSION must use a SemVer-compatible release marker; found '$version'."
    } else {
        Write-Host "MyAI version: $version"
    }
}

Write-Gate "Repository artifact hygiene"
$failureCountBeforeGate = $Failures.Count
foreach ($file in $RepositoryFiles) {
    $path = $file.RelativePath
    if (Test-IsForbiddenRepositoryArtifact -RelativePath $path) {
        Add-Failure "Runtime, secret, or generated artifact must not be committed: $path"
    }
}
if ($Failures.Count -eq $failureCountBeforeGate) {
    Write-Host "Repository artifact hygiene: ok"
}

Write-Gate "Documentation image formats"
$failureCountBeforeGate = $Failures.Count
$documentationImages = @(
    $RepositoryFiles |
        Where-Object { $_.RelativePath -match "^docs/assets/.+\.(?i:png|jpe?g)$" }
)
foreach ($imageFile in $documentationImages) {
    $extension = [System.IO.Path]::GetExtension($imageFile.RelativePath).ToLowerInvariant()
    $expectedSignature = switch ($extension) {
        ".png" { [byte[]](0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A) }
        ".jpg" { [byte[]](0xFF, 0xD8) }
        ".jpeg" { [byte[]](0xFF, 0xD8) }
    }
    if (-not (Test-FileSignature -Path $imageFile.FullPath -Expected $expectedSignature)) {
        Add-Failure "Image extension and file signature do not match: $($imageFile.RelativePath)"
    }
}
if ($Failures.Count -eq $failureCountBeforeGate) {
    Write-Host "Documentation images checked: $($documentationImages.Count)"
}

Write-Gate "Documentation links"
$markdownFiles = @($RepositoryFiles | Where-Object { $_.RelativePath.EndsWith(".md", [System.StringComparison]::OrdinalIgnoreCase) })
$markdownLink = [regex]"(?<!!)\[[^\]\r\n]*\]\((?<target>[^)\r\n]+)\)"
foreach ($document in $markdownFiles) {
    $content = Get-Content -LiteralPath $document.FullPath -Raw -Encoding UTF8
    foreach ($match in $markdownLink.Matches($content)) {
        $rawTarget = $match.Groups["target"].Value.Trim()
        if ($rawTarget.StartsWith("<") -and $rawTarget.Contains(">")) {
            $target = $rawTarget.Substring(1, $rawTarget.IndexOf(">") - 1)
        } else {
            $target = ($rawTarget -split "\s+", 2)[0]
        }
        if ($target -match "^(?i:https?|mailto|data):" -or $target.StartsWith("#")) {
            continue
        }
        $target = ($target -split "[#?]", 2)[0]
        if (-not $target.EndsWith(".md", [System.StringComparison]::OrdinalIgnoreCase)) {
            continue
        }
        try {
            $target = [System.Uri]::UnescapeDataString($target)
        } catch {
            Add-Failure "Invalid encoded documentation link: $($document.RelativePath) -> $target"
            continue
        }
        if ([System.IO.Path]::IsPathRooted($target) -and -not $target.StartsWith("/")) {
            Add-Failure "Machine-specific absolute documentation link: $($document.RelativePath) -> $target"
            continue
        }
        $resolved = if ($target.StartsWith("/")) {
            Join-Path $Root $target.TrimStart("/")
        } else {
            Join-Path (Split-Path -Parent $document.FullPath) $target
        }
        if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
            Add-Failure "Broken documentation link: $($document.RelativePath) -> $target"
        }
    }
}
Write-Host "Documentation files checked: $($markdownFiles.Count)"

Write-Gate "Python dependency pins"
$requirementsFiles = @(
    $RepositoryFiles |
        Where-Object { [System.IO.Path]::GetFileName($_.RelativePath) -match "^requirements.*\.txt$" }
)
if ($requirementsFiles.Count -eq 0) {
    Add-Failure "No Python requirements file was found."
}
foreach ($requirementsFile in $requirementsFiles) {
    $lineNumber = 0
    foreach ($line in Get-Content -LiteralPath $requirementsFile.FullPath -Encoding UTF8) {
        $lineNumber += 1
        $requirement = $line.Trim()
        if ($requirement.Length -eq 0 -or $requirement.StartsWith("#")) {
            continue
        }
        if ($requirement -notmatch "^[A-Za-z0-9_.-]+==[^\s;]+(?:\s*;.*)?$") {
            Add-Failure "Unpinned dependency: $($requirementsFile.RelativePath):$lineNumber"
        }
    }
}
Write-Host "Requirements files checked: $($requirementsFiles.Count)"

Write-Gate "Sensitive value and default scan"
$failureCountBeforeGate = $Failures.Count
$textExtensions = @(".cfg", ".cmd", ".env", ".example", ".html", ".ini", ".java", ".js", ".json", ".md", ".properties", ".ps1", ".py", ".toml", ".txt", ".xml", ".yaml", ".yml")
$secretPatterns = @(
    [pscustomobject]@{ Name = "private key"; Pattern = "-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----" },
    [pscustomobject]@{ Name = "AWS access key"; Pattern = "\bAKIA[0-9A-Z]{16}\b" },
    [pscustomobject]@{ Name = "GitHub token"; Pattern = "\bgh[pousr]_[A-Za-z0-9]{24,}\b" },
    [pscustomobject]@{ Name = "Slack token"; Pattern = "\bxox[baprs]-[A-Za-z0-9-]{16,}\b" },
    [pscustomobject]@{ Name = "provider API key"; Pattern = "\bsk-[A-Za-z0-9_-]{16,}\b" },
    [pscustomobject]@{ Name = "Hugging Face token"; Pattern = "\bhf_[A-Za-z0-9]{30,}\b" },
    [pscustomobject]@{ Name = "GitLab token"; Pattern = "\bglpat-[A-Za-z0-9_-]{20,}\b" },
    [pscustomobject]@{ Name = "npm token"; Pattern = "\bnpm_[A-Za-z0-9]{36}\b" },
    [pscustomobject]@{ Name = "Google API key"; Pattern = "\bAIza[0-9A-Za-z_-]{35}\b" },
    [pscustomobject]@{ Name = "scanner contract marker"; Pattern = "\bMYAI_TEST_ONLY_[A-Z0-9]{16}\b" },
    [pscustomobject]@{ Name = "machine-specific Windows user path"; Pattern = "\b[A-Za-z]:(?:\\{1,2}|/)Users(?:\\{1,2}|/)[^\\/\s]+(?:\\{1,2}|/)" }
)

function Test-IsAllowedSecretMatch {
    param([string]$Value)

    if ($Value -eq "sk-example-secret-value") {
        return $true
    }

    # Keep one explicitly synthetic Windows path in the redaction regression
    # suite without allowing a real workstation username through the gate.
    $normalized = $Value.Replace("\\", "/").Replace("//", "/")
    return $normalized -match "^[A-Za-z]:/Users/MYAI_TEST_USER/$"
}

function Assert-SecretScannerContracts {
    param([object[]]$Patterns)

    $contractPattern = $Patterns |
        Where-Object { $_.Name -eq "scanner contract marker" } |
        Select-Object -First 1
    if ($null -eq $contractPattern) {
        throw "Internal secret scanner contract marker is missing."
    }

    $syntheticPositive = "MYAI_TEST_ONLY_" + ("A" * 16)
    $syntheticNegative = "MYAI_TEST_ONLY_" + ("A" * 15)
    if (-not [regex]::IsMatch($syntheticPositive, $contractPattern.Pattern)) {
        throw "Internal secret scanner positive contract failed."
    }
    if ([regex]::IsMatch($syntheticNegative, $contractPattern.Pattern)) {
        throw "Internal secret scanner negative contract failed."
    }
    if (-not (Test-IsAllowedSecretMatch -Value "sk-example-secret-value")) {
        throw "Internal secret scanner placeholder allowlist contract failed."
    }

    $pathPattern = $Patterns |
        Where-Object { $_.Name -eq "machine-specific Windows user path" } |
        Select-Object -First 1
    if ($null -eq $pathPattern) {
        throw "Internal machine-specific path scanner is missing."
    }
    $slash = "\"
    $escapedSlash = $slash + $slash
    foreach ($pathCandidate in @(
        "C:" + $slash + "Users" + $slash + "real-user" + $slash,
        "C:" + $escapedSlash + "Users" + $escapedSlash + "real-user" + $escapedSlash,
        "C:" + "/Users/real-user/"
    )) {
        if (-not [regex]::IsMatch($pathCandidate, $pathPattern.Pattern)) {
            throw "Internal machine-specific path scanner contract failed."
        }
    }
    $syntheticPath = "C:" + $escapedSlash + "Users" + $escapedSlash + "MYAI_TEST_USER" + $escapedSlash
    if (-not (Test-IsAllowedSecretMatch -Value $syntheticPath)) {
        throw "Internal synthetic path allowlist contract failed."
    }
}

Assert-SecretScannerContracts -Patterns $secretPatterns
foreach ($file in $RepositoryFiles) {
    $extension = [System.IO.Path]::GetExtension($file.RelativePath).ToLowerInvariant()
    if ($textExtensions -notcontains $extension) {
        continue
    }
    $lineNumber = 0
    foreach ($line in Get-Content -LiteralPath $file.FullPath -Encoding UTF8 -ErrorAction Stop) {
        $lineNumber += 1
        foreach ($secretPattern in $secretPatterns) {
            $matches = [regex]::Matches($line, $secretPattern.Pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
            foreach ($match in $matches) {
                if (Test-IsAllowedSecretMatch -Value $match.Value) {
                    continue
                }
                Add-Failure "Potential $($secretPattern.Name) in $($file.RelativePath):$lineNumber (value suppressed)"
            }
        }
    }
}

$defaultConfigPaths = @(
    $RepositoryFiles |
        Where-Object {
            $_.RelativePath -match "(^|/)application[^/]*\.properties$" -or
            $_.RelativePath -match "(^|/)(?:\.env|[^/]+\.env)\.example$"
        } |
        ForEach-Object { $_.RelativePath } |
        Sort-Object -Unique
)
foreach ($relativePath in $defaultConfigPaths) {
    $path = Join-Path $Root $relativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        Add-Failure "Required default configuration is missing: $relativePath"
        continue
    }
    $lineNumber = 0
    foreach ($line in Get-Content -LiteralPath $path -Encoding UTF8) {
        $lineNumber += 1
        if ($line.TrimStart().StartsWith("#") -or $line -notmatch "^\s*([^=]+?)\s*=\s*(.*?)\s*$") {
            continue
        }
        $key = $Matches[1].Trim()
        $value = $Matches[2].Trim().Trim('"').Trim("'")
        if ($key -notmatch "(?i)(password|secret|credential|api[._-]?key|(?:^|[._-])token(?:$|[._-]))") {
            continue
        }
        $isSafePlaceholder = (
            $value.Length -eq 0 -or
            $value -match "^\$\{[A-Za-z0-9_]+:\}$" -or
            $value -match "^(?i:your[_-].*|example|placeholder|<[^>]+>)$" -or
            ($key -eq "myai.local-user.password" -and $value -eq '${MYAI_LOCAL_PASSWORD:local-password}')
        )
        if (-not $isSafePlaceholder) {
            Add-Failure "Non-placeholder sensitive default in ${relativePath}:$lineNumber for '$key' (value suppressed)"
        }
    }
}
if ($Failures.Count -eq $failureCountBeforeGate) {
    Write-Host "Sensitive values and defaults: ok"
}

Write-Gate "Frontend script syntax"
try {
    $node = Resolve-NodeExecutable
    $checker = Join-Path $ScriptDir "check-frontend-syntax.mjs"
    & $node $checker $Root
    if ($LASTEXITCODE -ne 0) {
        Add-Failure "Frontend syntax checker exited with code $LASTEXITCODE."
    }
} catch {
    Add-Failure $_.Exception.Message
}

Write-Host ""
if ($Failures.Count -gt 0) {
    Write-Host "Quality gates failed with $($Failures.Count) issue(s)." -ForegroundColor Red
    exit 1
}

Write-Host "MyAI static quality gates passed." -ForegroundColor Green
