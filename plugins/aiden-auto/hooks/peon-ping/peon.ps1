# peon-ping hook for Claude Code (Windows native)
# Called by Claude Code hooks on SessionStart, Stop, Notification, PermissionRequest, PostToolUseFailure, PreCompact

param(
    [string]$Command = "",
    [string]$Arg1 = "",
    [string]$Arg2 = ""
)

# M4 (2026-05-19): Hook-mode silent stream suppression.
# Root cause of `'M' is not recognized as an internal or external command` leak:
# Start-Process -WindowStyle Hidden only hides the window, not stderr/stdout streams,
# which inherit to the parent console and surface in Claude Code UI.
# Hook mode (no -Command arg) silences all non-essential streams. CLI mode is unaffected.
if (-not $Command) {
    $ErrorActionPreference = 'SilentlyContinue'
    $ProgressPreference = 'SilentlyContinue'
    $WarningPreference = 'SilentlyContinue'
    $InformationPreference = 'SilentlyContinue'
}

# Raw config read; repair is done at install/update time, so hook only needs plain read.
function Get-PeonConfigRaw {
    param([string]$Path)
    return Get-Content $Path -Raw
}

# --- CLI commands ---
if ($Command) {
    $InstallDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $ConfigPath = Join-Path $InstallDir "config.json"

    # Ensure config exists
    if (-not (Test-Path $ConfigPath)) {
        Write-Host "Error: peon-ping not configured. Config not found at $ConfigPath" -ForegroundColor Red
        exit 1
    }

    switch -Regex ($Command) {
        "^--toggle$" {
            $raw = Get-PeonConfigRaw $ConfigPath
            $cfg = $raw | ConvertFrom-Json
            $newState = -not $cfg.enabled
            $raw = Get-Content $ConfigPath -Raw
            $raw = $raw -replace '"enabled"\s*:\s*(true|false)', "`"enabled`": $($newState.ToString().ToLower())"
            Set-Content $ConfigPath -Value $raw -Encoding UTF8
            $state = if ($newState) { "ENABLED" } else { "PAUSED" }
            Write-Host "peon-ping: $state" -ForegroundColor Cyan
            return
        }
        "^--(pause|mute)$" {
            $raw = Get-Content $ConfigPath -Raw
            $raw = $raw -replace '"enabled"\s*:\s*(true|false)', '"enabled": false'
            Set-Content $ConfigPath -Value $raw -Encoding UTF8
            Write-Host "peon-ping: PAUSED" -ForegroundColor Yellow
            return
        }
        "^--(resume|unmute)$" {
            $raw = Get-Content $ConfigPath -Raw
            $raw = $raw -replace '"enabled"\s*:\s*(true|false)', '"enabled": true'
            Set-Content $ConfigPath -Value $raw -Encoding UTF8
            Write-Host "peon-ping: ENABLED" -ForegroundColor Green
            return
        }
        "^--status$" {
            try {
                $cfg = Get-PeonConfigRaw $ConfigPath | ConvertFrom-Json
                $state = if ($cfg.enabled) { "ENABLED" } else { "PAUSED" }
                Write-Host "peon-ping: $state | pack: $($cfg.active_pack) | volume: $($cfg.volume)" -ForegroundColor Cyan
            } catch {
                Write-Host "Error reading config: $_" -ForegroundColor Red
                exit 1
            }
            return
        }
        "^--packs$" {
            $packsDir = Join-Path $InstallDir "packs"
            $cfg = Get-PeonConfigRaw $ConfigPath | ConvertFrom-Json
            $available = Get-ChildItem -Path $packsDir -Directory | Where-Object {
                (Get-ChildItem -Path (Join-Path $_.FullName "sounds") -File -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0
            } | ForEach-Object { $_.Name } | Sort-Object

            switch ($Arg1) {
                "use" {
                    if (-not $Arg2) {
                        Write-Host "Usage: peon packs use <pack-name>" -ForegroundColor Yellow
                        return
                    }
                    $newPack = $Arg2
                    if ($newPack -notin $available) {
                        Write-Host "Pack '$newPack' not found. Available: $($available -join ', ')" -ForegroundColor Red
                        return
                    }
                    $raw = Get-Content $ConfigPath -Raw
                    $raw = $raw -replace '"active_pack"\s*:\s*"[^"]*"', "`"active_pack`": `"$newPack`""
                    Set-Content $ConfigPath -Value $raw -Encoding UTF8
                    Write-Host "peon-ping: switched to '$newPack'" -ForegroundColor Green
                    return
                }
                "next" {
                    $idx = [array]::IndexOf($available, $cfg.active_pack)
                    $newPack = $available[($idx + 1) % $available.Count]
                    $raw = Get-Content $ConfigPath -Raw
                    $raw = $raw -replace '"active_pack"\s*:\s*"[^"]*"', "`"active_pack`": `"$newPack`""
                    Set-Content $ConfigPath -Value $raw -Encoding UTF8
                    Write-Host "peon-ping: switched to '$newPack'" -ForegroundColor Green
                    return
                }
                default {
                    # "list" or no subcommand - show available packs
                    Write-Host "Available packs:" -ForegroundColor Cyan
                    foreach ($packName in $available) {
                        $soundCount = (Get-ChildItem -Path (Join-Path $packsDir "$packName\sounds") -File -ErrorAction SilentlyContinue | Measure-Object).Count
                        $marker = if ($packName -eq $cfg.active_pack) { " <-- active" } else { "" }
                        Write-Host "  $packName ($soundCount sounds)$marker"
                    }
                    return
                }
            }
        }
        "^--pack$" {
            $cfg = Get-PeonConfigRaw $ConfigPath | ConvertFrom-Json
            $packsDir = Join-Path $InstallDir "packs"
            $available = Get-ChildItem -Path $packsDir -Directory | Where-Object {
                (Get-ChildItem -Path (Join-Path $_.FullName "sounds") -File -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0
            } | ForEach-Object { $_.Name } | Sort-Object

            if ($Arg1 -eq "use") {
                # "peon pack use <name>" - treat Arg2 as the pack name
                if (-not $Arg2) {
                    Write-Host "Usage: peon pack use <pack-name>" -ForegroundColor Yellow
                    return
                }
                $newPack = $Arg2
            } elseif ($Arg1 -eq "next") {
                # "peon pack next" - cycle to next
                $idx = [array]::IndexOf($available, $cfg.active_pack)
                $newPack = $available[($idx + 1) % $available.Count]
            } elseif ($Arg1) {
                $newPack = $Arg1
            } else {
                $idx = [array]::IndexOf($available, $cfg.active_pack)
                $newPack = $available[($idx + 1) % $available.Count]
            }

            if ($newPack -notin $available) {
                Write-Host "Pack '$newPack' not found. Available: $($available -join ', ')" -ForegroundColor Red
                return
            }

            $raw = Get-Content $ConfigPath -Raw
            $raw = $raw -replace '"active_pack"\s*:\s*"[^"]*"', "`"active_pack`": `"$newPack`""
            Set-Content $ConfigPath -Value $raw -Encoding UTF8
            Write-Host "peon-ping: switched to '$newPack'" -ForegroundColor Green
            return
        }
        "^--volume$" {
            if ($Arg1) {
                $vol = [math]::Round([math]::Max(0.0, [math]::Min(1.0, [double]::Parse($Arg1.Trim(), [System.Globalization.CultureInfo]::InvariantCulture))), 2)
                $volStr = $vol.ToString([System.Globalization.CultureInfo]::InvariantCulture)
                $raw = Get-Content $ConfigPath -Raw
                $raw = $raw -replace '"volume"\s*:\s*[\d.,]+', "`"volume`": $volStr"
                Set-Content $ConfigPath -Value $raw -Encoding UTF8
                Write-Host "peon-ping: volume set to $vol" -ForegroundColor Green
            } else {
                Write-Host "Usage: peon --volume 0.5" -ForegroundColor Yellow
            }
            return
        }
        "^--help$" {
            Write-Host "peon-ping commands:" -ForegroundColor Cyan
            Write-Host "  --toggle       Toggle enabled/paused"
            Write-Host "  --pause        Pause sounds"
            Write-Host "  --resume       Resume sounds"
            Write-Host "  --mute         Alias for --pause"
            Write-Host "  --unmute       Alias for --resume"
            Write-Host "  --status       Show current status"
            Write-Host "  --packs        List available sound packs"
            Write-Host "  --pack [name]  Switch pack (or cycle)"
            Write-Host "  --volume N     Set volume (0.0-1.0)"
            Write-Host "  --help         Show this help"
            return
        }
    }
    return
}

# --- Hook mode (called by Claude Code via stdin JSON) ---
$InstallDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigPath = Join-Path $InstallDir "config.json"
$StatePath = Join-Path $InstallDir ".state.json"

# Read config
try {
    $config = Get-PeonConfigRaw $ConfigPath | ConvertFrom-Json
} catch {
    exit 0
}

if (-not $config.enabled) { exit 0 }

# Read hook input from stdin (StreamReader with UTF-8 auto-strips BOM on Windows)
$hookInput = ""
try {
    if (-not [Console]::IsInputRedirected) { exit 0 }
    $stream = [Console]::OpenStandardInput()
    $reader = New-Object System.IO.StreamReader($stream, [System.Text.Encoding]::UTF8)
    $hookInput = $reader.ReadToEnd()
    $reader.Close()
} catch {
    exit 0
}

if (-not $hookInput) { exit 0 }

try {
    $event = $hookInput | ConvertFrom-Json
} catch {
    exit 0
}

$rawEvent = $event.hook_event_name
if (-not $rawEvent) { exit 0 }

# Extract project name from cwd: use the leaf folder of the session's working directory.
# This is the folder Claude Code was launched in — independent of which files get edited.
$projectName = ""
if ($event.cwd) {
    $cwd = $event.cwd -replace '/', '\'
    $projectName = Split-Path $cwd -Leaf
}

# Cursor IDE sends camelCase via Third-party skills; Claude Code sends PascalCase.
# Map to PascalCase so the switch below matches.
$cursorMap = @{
    "sessionStart" = "SessionStart"
    "sessionEnd" = "SessionEnd"
    "beforeSubmitPrompt" = "UserPromptSubmit"
    "stop" = "Stop"
    "preToolUse" = "UserPromptSubmit"
    "postToolUse" = "PostToolUse"
    "subagentStop" = "SubagentStop"
    "subagentStart" = "SubagentStart"
    "preCompact" = "PreCompact"
}
# cursorMap is camelCase (Cursor IDE). Hashtable.ContainsKey is case-insensitive,
# which would incorrectly match Claude Code's PascalCase events (e.g. PreToolUse -> preToolUse).
# Only apply cursorMap when rawEvent starts lowercase (camelCase = Cursor).
$hookEvent = if ($rawEvent.Length -gt 0 -and [char]::IsLower($rawEvent[0]) -and $cursorMap.ContainsKey($rawEvent)) { $cursorMap[$rawEvent] } else { $rawEvent }

# Extract session ID (Claude Code: session_id, Cursor: conversation_id)
$sessionId = if ($event.session_id) { $event.session_id } elseif ($event.conversation_id) { $event.conversation_id } else { "default" }

# Helper function to convert PSCustomObject to hashtable (PS 5.1 compat)
function ConvertTo-Hashtable {
    param([Parameter(ValueFromPipeline)]$obj)
    if ($obj -is [hashtable]) { return $obj }
    if ($obj -is [System.Collections.IEnumerable] -and $obj -isnot [string]) {
        return @($obj | ForEach-Object { ConvertTo-Hashtable $_ })
    }
    if ($obj -is [PSCustomObject]) {
        $ht = @{}
        foreach ($prop in $obj.PSObject.Properties) {
            $ht[$prop.Name] = ConvertTo-Hashtable $prop.Value
        }
        return $ht
    }
    return $obj
}

# Read state
$state = @{}
try {
    if (Test-Path $StatePath) {
        $raw = Get-Content $StatePath -Raw
        if ($raw -and $raw.Trim().Length -gt 0) {
            $stateObj = $raw | ConvertFrom-Json
            $converted = ConvertTo-Hashtable $stateObj
            if ($converted -is [hashtable]) { $state = $converted }
        }
    }
} catch {
    $state = @{}
}

# --- Session cleanup: expire old sessions ---
$now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$ttlDays = if ($config.session_ttl_days) { $config.session_ttl_days } else { 7 }
$cutoff = $now - ($ttlDays * 86400)
$sessionPacks = if ($state.ContainsKey("session_packs")) { $state["session_packs"] } else { @{} }
$sessionPacksClean = @{}
foreach ($sid in $sessionPacks.Keys) {
    $packData = $sessionPacks[$sid]
    if ($packData -is [hashtable]) {
        # New format with timestamp
        $lastUsed = if ($packData.ContainsKey("last_used")) { $packData["last_used"] } else { 0 }
        if ($lastUsed -gt $cutoff) {
            if ($sid -eq $sessionId) {
                $packData["last_used"] = $now
            }
            $sessionPacksClean[$sid] = $packData
        }
    } elseif ($sid -eq $sessionId) {
        # Old format, upgrade active session
        $sessionPacksClean[$sid] = @{ pack = $packData; last_used = $now }
    } elseif ($packData -is [string]) {
        # Old format for inactive sessions - keep for now (migration path)
        $sessionPacksClean[$sid] = $packData
    }
}
$state["session_packs"] = $sessionPacksClean
$stateDirty = $false
if ($sessionPacksClean.Count -ne $sessionPacks.Count) {
    $stateDirty = $true
}

# --- Map Claude Code hook event -> CESP manifest category ---
$category = $null
$ntype = $event.notification_type

switch ($hookEvent) {
    "SessionStart" {
        $category = "session.start"
    }
    "Stop" {
        $category = "task.complete"
        $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        $window = if ($config.silent_window_seconds) { $config.silent_window_seconds } else { 30 }

        # Guard 1: 직전 SubagentStop 윈도우 이내면 무음 (sub agent 영향 Stop 차단)
        $lastSubagentStop = if ($state.ContainsKey("last_subagent_stop")) { $state["last_subagent_stop"] } else { 0 }
        if (($now - $lastSubagentStop) -lt $window) {
            $category = $null
        }

        # Guard 2: 직전 Task tool 호출 윈도우 이내면 무음 (sub agent 진행 중 차단)
        $lastTaskTool = if ($state.ContainsKey("last_task_tool")) { $state["last_task_tool"] } else { 0 }
        if (($now - $lastTaskTool) -lt $window) {
            $category = $null
        }

        # Guard 3: 기존 debounce (연속 Stop 차단)
        $lastStop = if ($state.ContainsKey("last_stop_time")) { $state["last_stop_time"] } else { 0 }
        if (($now - $lastStop) -lt $window) {
            $category = $null
        }
        $state["last_stop_time"] = $now
    }
    "PostToolUse" {
        # 작업 진행 중 도구 사용 — 완료 알림 불필요
        $category = $null
    }
    "SubagentStop" {
        # 서브에이전트 종료 — Stop Guard 1을 위한 시각 기록
        $state["last_subagent_stop"] = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        $category = $null
    }
    "Notification" {
        if ($ntype -eq "idle_prompt") {
            $category = "input.required"
        } else {
            $category = $null
        }
    }
    "PermissionRequest" {
        $category = "input.required"
    }
    "PreToolUse" {
        # Task tool: Stop Guard 2를 위한 시각 기록 후 무음 종료
        if ($event.tool_name -eq "Task") {
            $state["last_task_tool"] = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
            $category = $null
        } elseif ($event.tool_name -eq "AskUserQuestion") {
            # 사용자 질문 도구 — 입력 필요
            $category = "input.required"
        } else {
            $category = "input.required"
        }
    }
    "UserPromptSubmit" {
        # Detect rapid prompts for "annoyed" easter egg
        $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        $annoyedThreshold = if ($config.annoyed_threshold) { $config.annoyed_threshold } else { 3 }
        $annoyedWindow = if ($config.annoyed_window_seconds) { $config.annoyed_window_seconds } else { 10 }

        $allPrompts = if ($state.ContainsKey("prompt_timestamps")) { $state["prompt_timestamps"] } else { @{} }
        $recentPrompts = @()
        if ($allPrompts.ContainsKey($sessionId)) {
            $recentPrompts = @($allPrompts[$sessionId] | Where-Object { ($now - $_) -lt $annoyedWindow })
        }
        $recentPrompts += $now
        $allPrompts[$sessionId] = $recentPrompts
        $state["prompt_timestamps"] = $allPrompts

        if ($recentPrompts.Count -ge $annoyedThreshold) {
            $category = "user.spam"
        }
    }
    "PostToolUseFailure" {
        $category = "task.error"
    }
    "SubagentStart" {
        $category = "task.acknowledge"
    }
}

# Save state
try {
    $state | ConvertTo-Json -Depth 3 | Set-Content $StatePath -Encoding UTF8
} catch {}

if (-not $category) { exit 0 }

# Check if category is enabled
try {
    $catEnabled = $config.categories.$category
    if ($catEnabled -eq $false) { exit 0 }
} catch {}

# --- Pick a sound ---
$activePack = $config.active_pack
if (-not $activePack) { $activePack = "peon" }

# Support pack rotation
$rotationMode = $config.pack_rotation_mode
if (-not $rotationMode) { $rotationMode = "random" }

if ($rotationMode -eq "agentskill" -or $rotationMode -eq "session_override") {
    # Explicit per-session assignments (from skill)
    $sessionPacks = $state.session_packs
    if (-not $sessionPacks) { $sessionPacks = @{} }
    if ($sessionPacks.ContainsKey($sessionId) -and $sessionPacks[$sessionId]) {
        $packData = $sessionPacks[$sessionId]
        # Handle both old string format and new dict format
        if ($packData -is [hashtable]) {
            $candidate = $packData.pack
        } else {
            $candidate = $packData
        }
        $candidateDir = Join-Path $InstallDir "packs\$candidate"
        if ($candidate -and (Test-Path $candidateDir -PathType Container)) {
            $activePack = $candidate
            # Update timestamp
            $sessionPacks[$sessionId] = @{ pack = $candidate; last_used = [int][double]::Parse((Get-Date -UFormat %s)) }
            $state.session_packs = $sessionPacks
            $stateDirty = $true
        } else {
            # Pack missing, use default and clean up
            $activePack = $config.active_pack
            if (-not $activePack) { $activePack = "peon" }
            $sessionPacks.Remove($sessionId)
            $state.session_packs = $sessionPacks
            $stateDirty = $true
        }
    } else {
        # No assignment: check session_packs["default"] (Cursor users without conversation_id)
        $defaultData = $sessionPacks.default
        if ($defaultData) {
            $candidate = if ($defaultData -is [hashtable]) { $defaultData.pack } else { $defaultData }
            $candidateDir = Join-Path $InstallDir "packs\$candidate"
            if ($candidate -and (Test-Path $candidateDir -PathType Container)) {
                $activePack = $candidate
            } else {
                $activePack = $config.active_pack
                if (-not $activePack) { $activePack = "peon" }
            }
        } else {
            $activePack = $config.active_pack
            if (-not $activePack) { $activePack = "peon" }
        }
    }
} elseif ($config.pack_rotation -and $config.pack_rotation.Count -gt 0) {
    # Automatic rotation
    $activePack = $config.pack_rotation | Get-Random
}

$packDir = Join-Path $InstallDir "packs\$activePack"
$manifestPath = Join-Path $packDir "openpeon.json"
if (-not (Test-Path $manifestPath)) { exit 0 }

try {
    $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
} catch { exit 0 }

# Get sounds for this category
$catSounds = $null
try {
    $catSounds = $manifest.categories.$category.sounds
} catch {}
if (-not $catSounds -or $catSounds.Count -eq 0) { exit 0 }

# Anti-repeat: avoid last played sound
$lastKey = "last_$category"
$lastPlayed = ""
if ($state.ContainsKey($lastKey)) {
    $lastPlayed = $state[$lastKey]
}

$candidates = @($catSounds | Where-Object { (Split-Path $_.file -Leaf) -ne $lastPlayed })
if ($candidates.Count -eq 0) { $candidates = @($catSounds) }

$chosen = $candidates | Get-Random
$soundFile = Split-Path $chosen.file -Leaf
$soundPath = Join-Path $packDir "sounds\$soundFile"

if (-not (Test-Path $soundPath)) { exit 0 }

# Icon resolution chain (CESP 짠5.5)
$iconPath = ""
$iconCandidate = ""
if ($chosen.icon) { $iconCandidate = $chosen.icon }
elseif ($manifest.categories.$category.icon) { $iconCandidate = $manifest.categories.$category.icon }
elseif ($manifest.icon) { $iconCandidate = $manifest.icon }
elseif (Test-Path (Join-Path $packDir "icon.png")) { $iconCandidate = "icon.png" }
if ($iconCandidate) {
    $resolved = [System.IO.Path]::GetFullPath((Join-Path $packDir $iconCandidate))
    $packRoot = [System.IO.Path]::GetFullPath($packDir) + [System.IO.Path]::DirectorySeparatorChar
    if ($resolved.StartsWith($packRoot) -and (Test-Path $resolved -PathType Leaf)) {
        $iconPath = $resolved
    }
}

# Save last played
$state[$lastKey] = $soundFile
try {
    $state | ConvertTo-Json -Depth 3 | Set-Content $StatePath -Encoding UTF8
} catch {}

# --- TTS check: if cached TTS exists, play it INSTEAD of sound effect ---
$volume = $config.volume
if (-not $volume) { $volume = 0.5 }

$playTTS = $false
$ttsFile = ""

if ($config.tts -and $config.tts.enabled -and $projectName -and $category) {
    $ttsDir = Join-Path $InstallDir "tts-cache\$projectName"
    $ttsFile = Join-Path $ttsDir "$category.mp3"

    if (Test-Path $ttsFile) {
        # TTS cache hit: play TTS instead of sound effect
        $playTTS = $true
    } else {
        # TTS cache miss: trigger background generation for next time
        $template = $null
        try { $template = $config.tts.templates.$category } catch {}
        if ($template) {
            $genScript = Join-Path $InstallDir "scripts\tts-generate.ps1"
            $voice = if ($config.tts.voice) { $config.tts.voice } else { "ko-KR-SunHiNeural" }
            $displayName = $projectName
            try {
                $alias = $config.tts.project_aliases.$projectName
                if ($alias) { $displayName = $alias }
            } catch {}
            $ttsOutputDir = Join-Path $InstallDir "tts-cache"
            # L3 (2026-05-19): Primary path = pythonw.exe + tts_generate.py.
            # pythonw is the Windows GUI-subsystem Python interpreter — no console
            # is ever allocated, no console host can ever spawn. This eliminates
            # the entire `Start-Process powershell` chain that was the last
            # remaining PowerShell subprocess in the peon-ping flow.
            # Fallback (tts-generate.ps1) retained for environments where
            # pythonw / edge_tts is unavailable.
            $genPy = Join-Path $InstallDir "scripts\tts_generate.py"
            $pyArgs = @($genPy, $projectName, $displayName, $category, $voice, $template, $ttsOutputDir)
            $pythonwAvailable = $null -ne (Get-Command pythonw -ErrorAction SilentlyContinue)
            if ($pythonwAvailable -and (Test-Path $genPy)) {
                # M4 (2026-05-19): RedirectStandardOutput/Error to NUL device.
                # -WindowStyle Hidden alone leaks stderr to parent console (Claude Code UI).
                # NUL device absorbs both streams so child native command errors stay invisible.
                Start-Process -WindowStyle Hidden -FilePath "pythonw" -ArgumentList $pyArgs `
                    -RedirectStandardOutput "NUL" -RedirectStandardError "NUL"
            } else {
                # Fallback: legacy PowerShell wrapper with hardened argv (T1+T2).
                $argList = @(
                    '-NoProfile', '-WindowStyle', 'Hidden',
                    '-File', $genScript,
                    '-Project', $projectName,
                    '-DisplayName', $displayName,
                    '-Category', $category,
                    '-Voice', $voice,
                    '-Template', $template,
                    '-OutputDir', $ttsOutputDir
                )
                # M4 (2026-05-19): Same NUL redirect as primary path.
                Start-Process -WindowStyle Hidden -FilePath "powershell" -ArgumentList $argList `
                    -RedirectStandardOutput "NUL" -RedirectStandardError "NUL"
            }
        }
    }
}

# --- Play audio (TTS replaces sound effect, not additive) ---
if ($playTTS) {
    $ttsVol = if ($config.tts.volume) { $config.tts.volume } else { $volume }
    $actualPath = $ttsFile
} else {
    $ttsVol = $volume
    $actualPath = $soundPath
}

try {
    if ($actualPath -match '\.wav$') {
        Add-Type -AssemblyName System.Windows.Forms
        $sp = New-Object System.Media.SoundPlayer $actualPath
        $sp.PlaySync()
        $sp.Dispose()
    } else {
        Add-Type -AssemblyName PresentationCore
        $player = New-Object System.Windows.Media.MediaPlayer
        $player.Open([Uri]::new("file:///$($actualPath -replace '\\','/')"))
        $player.Volume = $ttsVol
        Start-Sleep -Milliseconds 150
        $player.Play()
        $timeout = 50
        while ($timeout -gt 0 -and $player.Position.TotalMilliseconds -eq 0) {
            Start-Sleep -Milliseconds 100
            $timeout--
        }
        if ($player.NaturalDuration.HasTimeSpan) {
            $remaining = $player.NaturalDuration.TimeSpan.TotalMilliseconds - $player.Position.TotalMilliseconds
            if ($remaining -gt 0 -and $remaining -lt 5000) {
                Start-Sleep -Milliseconds ([int]$remaining + 100)
            }
        } else {
            Start-Sleep -Seconds 2
        }
        $player.Close()
    }
} catch {}

exit 0
