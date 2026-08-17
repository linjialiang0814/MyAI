param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 11435,
    [switch]$ValidateOnly
)

$ErrorActionPreference = "Stop"

function Get-EnvironmentPathEntries {
    param([ValidateSet("Process", "User", "Machine")][string]$Target)

    $pathValue = [Environment]::GetEnvironmentVariable("Path", $Target)
    if ([string]::IsNullOrWhiteSpace($pathValue)) {
        return @()
    }

    return @(
        $pathValue.Split([IO.Path]::PathSeparator) |
            ForEach-Object { [Environment]::ExpandEnvironmentVariables($_.Trim().Trim('"')) } |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    )
}

function Resolve-OllamaExecutable {
    $command = Get-Command ollama.exe -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -ne $command -and (Test-Path -LiteralPath $command.Source -PathType Leaf)) {
        return [pscustomobject]@{
            Path = [IO.Path]::GetFullPath($command.Source)
            Source = "process PATH"
        }
    }

    $candidates = @()
    foreach ($target in @("User", "Machine")) {
        foreach ($directory in Get-EnvironmentPathEntries -Target $target) {
            $candidates += [pscustomobject]@{
                Path = Join-Path $directory "ollama.exe"
                Source = "$($target.ToLowerInvariant()) PATH"
            }
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        $candidates += [pscustomobject]@{
            Path = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
            Source = "default user install"
        }
    }

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate.Path -PathType Leaf) {
            return [pscustomobject]@{
                Path = [IO.Path]::GetFullPath($candidate.Path)
                Source = $candidate.Source
            }
        }
    }

    throw "Ollama was not found in the current, user, or machine PATH, or in the default user installation directory. Install it before starting the thesis runtime."
}

function Resolve-OllamaModelsPath {
    # Read the user-scoped value explicitly because an already-running shell may
    # not contain environment changes made by a recent Ollama installation.
    foreach ($target in @("User", "Process", "Machine")) {
        $value = [Environment]::GetEnvironmentVariable("OLLAMA_MODELS", $target)
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            $expanded = [Environment]::ExpandEnvironmentVariables($value.Trim().Trim('"'))
            return [pscustomobject]@{
                Path = [IO.Path]::GetFullPath($expanded)
                Source = "$($target.ToLowerInvariant()) environment"
            }
        }
    }

    if ([string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
        throw "OLLAMA_MODELS is not configured and USERPROFILE is unavailable."
    }
    return [pscustomobject]@{
        Path = [IO.Path]::GetFullPath((Join-Path $env:USERPROFILE ".ollama\models"))
        Source = "default user model directory"
    }
}

$ollama = Resolve-OllamaExecutable
$models = Resolve-OllamaModelsPath
$ollamaPath = $ollama.Path
$ollamaModelsPath = $models.Path

if ($ValidateOnly) {
    Write-Host "Ollama executable: $ollamaPath ($($ollama.Source))"
    Write-Host "Ollama models: $ollamaModelsPath ($($models.Source))"
    if (-not (Test-Path -LiteralPath $ollamaModelsPath -PathType Container)) {
        Write-Warning "The resolved model directory does not exist yet."
    }
    return
}

# The frozen thesis launcher requests CPU AVX2 because the pinned NVIDIA 546.30
# driver is incompatible with Ollama 0.32.6's bundled CUDA runner on this host.
# Keeping this as a separate loopback service avoids changing the normal app
# endpoint on 11434 and makes the execution backend explicit and repeatable.
$env:OLLAMA_HOST = "127.0.0.1:$Port"
$env:OLLAMA_LLM_LIBRARY = "cpu_avx2"
$env:CUDA_VISIBLE_DEVICES = "-1"
$env:GGML_VK_VISIBLE_DEVICES = "-1"
$env:OLLAMA_CONTEXT_LENGTH = "4096"
$env:OLLAMA_NUM_PARALLEL = "1"
$env:OLLAMA_KEEP_ALIVE = "30m"
$env:OLLAMA_MODELS = $ollamaModelsPath

Write-Host "Starting frozen thesis Ollama runtime on http://127.0.0.1:$Port"
Write-Host "Ollama executable: $ollamaPath ($($ollama.Source))"
Write-Host "Ollama models: $ollamaModelsPath ($($models.Source))"
Write-Host "Requested library=cpu_avx2, verified placement=CPU-only, context=4096, parallel=1; press Ctrl+C to stop."

& $ollamaPath serve
exit $LASTEXITCODE
