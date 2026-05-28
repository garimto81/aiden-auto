# Screenshot Capture Script
# 스크린 캡처 좌우 여백 없이 캡처하는 스크립트
#
# Usage:
#   .\screenshot-capture.ps1 -InputFile "path/to/file.html" -OutputFile "path/to/output.png"
#   .\screenshot-capture.ps1 -InputFile "file.html" -OutputFile "output.png" -Width 900 -Height 600
#   .\screenshot-capture.ps1 -InputDir "docs/mockups/" -OutputDir "docs/images/"
#
# Parameters:
#   -InputFile   : 단일 HTML 파일 경로
#   -OutputFile  : 출력 PNG 파일 경로
#   -InputDir    : HTML 파일들이 있는 디렉토리 (일괄 처리)
#   -OutputDir   : 출력 이미지 디렉토리 (일괄 처리)
#   -Width       : Viewport 너비 (기본값: 900)
#   -Height      : Viewport 높이 (기본값: 600)
#   -FullPage    : 전체 페이지 캡처 (기본값: true)

param(
    [string]$InputFile,
    [string]$OutputFile,
    [string]$InputDir,
    [string]$OutputDir,
    [int]$Width = 900,
    [int]$Height = 600,
    [bool]$FullPage = $true
)

# Playwright 존재 확인
$playwrightPath = Get-Command npx -ErrorAction SilentlyContinue
if (-not $playwrightPath) {
    Write-Error "npx가 설치되어 있지 않습니다. Node.js를 설치해주세요."
    exit 1
}

# 단일 파일 캡처 함수
function Capture-Single {
    param(
        [string]$Input,
        [string]$Output,
        [int]$ViewportWidth,
        [int]$ViewportHeight,
        [bool]$Full
    )

    $viewportSize = "${ViewportWidth},${ViewportHeight}"
    $args = @("playwright", "screenshot", $Input, $Output, "--viewport-size=`"$viewportSize`"")

    if ($Full) {
        $args += "--full-page"
    }

    Write-Host "Capturing: $Input -> $Output" -ForegroundColor Cyan
    Write-Host "  Viewport: ${ViewportWidth}x${ViewportHeight}" -ForegroundColor Gray

    & npx $args

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] Success" -ForegroundColor Green
        return $true
    } else {
        Write-Host "  [FAIL] Error capturing screenshot" -ForegroundColor Red
        return $false
    }
}

# 단일 파일 모드
if ($InputFile -and $OutputFile) {
    $success = Capture-Single -Input $InputFile -Output $OutputFile -ViewportWidth $Width -ViewportHeight $Height -Full $FullPage
    if ($success) {
        Write-Host "`nDone!" -ForegroundColor Green
    }
    exit
}

# 디렉토리 일괄 처리 모드
if ($InputDir -and $OutputDir) {
    # 출력 디렉토리 생성
    if (-not (Test-Path $OutputDir)) {
        New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    }

    # HTML 파일 목록
    $htmlFiles = Get-ChildItem -Path $InputDir -Filter "*.html" | Sort-Object Name

    if ($htmlFiles.Count -eq 0) {
        Write-Host "No HTML files found in: $InputDir" -ForegroundColor Yellow
        exit 1
    }

    Write-Host "Found $($htmlFiles.Count) HTML files" -ForegroundColor Cyan
    Write-Host "Viewport: ${Width}x${Height}" -ForegroundColor Gray
    Write-Host ""

    $successCount = 0
    $failCount = 0

    foreach ($file in $htmlFiles) {
        $outputName = [System.IO.Path]::GetFileNameWithoutExtension($file.Name) + ".png"
        $outputPath = Join-Path $OutputDir $outputName

        $success = Capture-Single -Input $file.FullName -Output $outputPath -ViewportWidth $Width -ViewportHeight $Height -Full $FullPage

        if ($success) {
            $successCount++
        } else {
            $failCount++
        }
    }

    Write-Host ""
    Write-Host "========================================" -ForegroundColor White
    Write-Host "Total: $($htmlFiles.Count) | Success: $successCount | Failed: $failCount" -ForegroundColor $(if ($failCount -eq 0) { "Green" } else { "Yellow" })
    exit
}

# 사용법 출력
Write-Host @"
Screenshot Capture Script - No Margin Edition

Usage:
  Single file:
    .\screenshot-capture.ps1 -InputFile "file.html" -OutputFile "output.png"
    .\screenshot-capture.ps1 -InputFile "file.html" -OutputFile "output.png" -Width 1200

  Batch processing:
    .\screenshot-capture.ps1 -InputDir "docs/mockups/" -OutputDir "docs/images/"

Options:
  -Width      Viewport width (default: 900)
  -Height     Viewport height (default: 600)
  -FullPage   Capture full page (default: true)

Examples:
  # Standard mockup capture (900x600)
  .\screenshot-capture.ps1 -InputFile "login.html" -OutputFile "login.png"

  # Wide mockup (1200x800)
  .\screenshot-capture.ps1 -InputFile "dashboard.html" -OutputFile "dashboard.png" -Width 1200 -Height 800

  # Batch all mockups
  .\screenshot-capture.ps1 -InputDir "C:\claude\wsoptv_ott\docs\mockups\PRD-0002" -OutputDir "C:\claude\wsoptv_ott\docs\images\PRD-0002"
"@
