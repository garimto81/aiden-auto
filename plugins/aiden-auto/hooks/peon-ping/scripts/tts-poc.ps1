param(
    [string]$Text,
    [string]$Voice,
    [double]$Volume
)
if (-not $Text) { $Text = "claude project completed" }
if (-not $Voice) { $Voice = "ko-KR-SunHiNeural" }
if (-not $Volume) { $Volume = 0.7 }

$ErrorActionPreference = "Stop"
$InstallDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$CacheDir = Join-Path $InstallDir "tts-cache"
$OutputFile = Join-Path $CacheDir "poc-test.mp3"

Write-Host "=== peon-ping TTS POC ===" -ForegroundColor Cyan
Write-Host "Text: $Text"
Write-Host "Voice: $Voice"
Write-Host "Output: $OutputFile"

# Step 1: edge-tts check
Write-Host "[1/4] Checking edge-tts..." -ForegroundColor Yellow
$null = & python -m edge_tts --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: edge-tts not installed" -ForegroundColor Red
    exit 1
}
Write-Host "  OK" -ForegroundColor Green

# Step 2: cache dir
Write-Host "[2/4] Preparing cache dir..." -ForegroundColor Yellow
if (-not (Test-Path $CacheDir)) {
    New-Item -ItemType Directory -Path $CacheDir -Force | Out-Null
}
Write-Host "  OK" -ForegroundColor Green

# Step 3: Generate TTS
Write-Host "[3/4] Generating TTS..." -ForegroundColor Yellow
$sw = [System.Diagnostics.Stopwatch]::StartNew()
& python -m edge_tts --voice $Voice --text $Text --write-media $OutputFile 2>&1
$genResult = $LASTEXITCODE
$sw.Stop()

if ($genResult -ne 0 -or -not (Test-Path $OutputFile)) {
    Write-Host "FAIL: TTS generation failed" -ForegroundColor Red
    exit 1
}

$ms = $sw.ElapsedMilliseconds
$kb = [math]::Round((Get-Item $OutputFile).Length / 1024, 1)
Write-Host "  OK: ${ms}ms, ${kb}KB" -ForegroundColor Green

# Step 4: Play
Write-Host "[4/4] Playing..." -ForegroundColor Yellow
try {
    Add-Type -AssemblyName PresentationCore
    $player = New-Object System.Windows.Media.MediaPlayer
    $player.Open([Uri]::new("file:///$($OutputFile -replace '\\','/')"))
    $player.Volume = $Volume
    Start-Sleep -Milliseconds 200
    $player.Play()
    $waitMax = 80
    while ($waitMax -gt 0 -and $player.Position.TotalMilliseconds -eq 0) {
        Start-Sleep -Milliseconds 100
        $waitMax--
    }
    if ($player.NaturalDuration.HasTimeSpan) {
        $rem = $player.NaturalDuration.TimeSpan.TotalMilliseconds - $player.Position.TotalMilliseconds
        if ($rem -gt 0 -and $rem -lt 8000) {
            Start-Sleep -Milliseconds ([int]$rem + 200)
        }
    } else {
        Start-Sleep -Seconds 3
    }
    $player.Close()
    Write-Host "  OK: Playback done" -ForegroundColor Green
} catch {
    Write-Host "  WARN: Playback error: $_" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== POC Result ===" -ForegroundColor Cyan
Write-Host "  Generation: ${ms}ms"
Write-Host "  File size: ${kb}KB"
Write-Host "  Cache path: $OutputFile"
Write-Host "  PASS: Cache-first TTS is feasible" -ForegroundColor Green
