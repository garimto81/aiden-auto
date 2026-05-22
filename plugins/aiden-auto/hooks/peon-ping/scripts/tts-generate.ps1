# tts-generate.ps1 — edge-tts wrapper for peon-ping dynamic TTS
# Generates MP3 from text template, caches in tts-cache/{project}/{category}.mp3
# Usage: tts-generate.ps1 -Project ebs -DisplayName "EBS" -Category "task.complete" -Voice "ko-KR-SunHiNeural" -Template "{project} completed" -OutputDir "./tts-cache"

param(
    [Parameter(Mandatory=$true)][string]$Project,
    [string]$DisplayName,
    [Parameter(Mandatory=$true)][string]$Category,
    [string]$Voice,
    [string]$Template,
    [string]$OutputDir
)

if (-not $Voice) { $Voice = "ko-KR-SunHiNeural" }
if (-not $DisplayName) { $DisplayName = $Project }
if (-not $Template) { $Template = "{project} task completed" }
if (-not $OutputDir) {
    $InstallDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
    $OutputDir = Join-Path $InstallDir "tts-cache"
}

$projectDir = Join-Path $OutputDir $Project
$outputFile = Join-Path $projectDir "$Category.mp3"

# Skip if already cached
if (Test-Path $outputFile) { exit 0 }

# Compose message from template
$message = $Template -replace '\{project\}', $DisplayName

# Ensure output directory exists
if (-not (Test-Path $projectDir)) {
    New-Item -ItemType Directory -Path $projectDir -Force | Out-Null
}

# Log file for debugging generation failures
$logFile = Join-Path (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)) "tts-generate.log"

# Generate TTS via edge-tts (use & operator to preserve quoted args)
# T3 (2026-05-19): PowerShell 5.1 의 `2>$errFile` 가 native exe stderr 를
# NativeCommandError ErrorRecord 로 wrap 하여 $? 가 false 가 되고 catch 블록으로
# 점프하는 트랩을 회피. `2>&1` 로 stderr 를 stdout 에 합치고 $LASTEXITCODE 만 검사 —
# ErrorActionPreference='Continue' 보장하여 ErrorRecord wrap 발생 0.
try {
    $prevErrorAction = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $combinedOutput = & python -m edge_tts --voice $Voice --text $message --write-media $outputFile 2>&1
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $prevErrorAction

    if ($exitCode -ne 0 -or -not (Test-Path $outputFile)) {
        $errMsg = ($combinedOutput | ForEach-Object { $_.ToString() }) -join "`n"
        if (-not $errMsg) { $errMsg = "unknown" }
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] FAIL: $Project/$Category - exit=$exitCode err=$errMsg" | Add-Content $logFile -ErrorAction SilentlyContinue
        exit 1
    }
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] OK: $Project/$Category -> $outputFile" | Add-Content $logFile -ErrorAction SilentlyContinue
} catch {
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ERR: $Project/$Category - $_" | Add-Content $logFile -ErrorAction SilentlyContinue
    exit 1
}

exit 0
