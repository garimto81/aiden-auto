# Docker Intranet Firewall Rule — auto-generated 2026-05-11
# 목적: 10.10.100.0/24 인트라넷에서 호스트의 Docker 포트 접근 허용
# 보안: Private/Domain 프로파일만, Public(인터넷) 차단 유지

$RuleName = "Docker Intranet Access (10.10.100.0/24)"
$Ports = @(80, 3000, 3001, 3002, 3009, 3011, 3030, 3101, 3210, 6333, 6379, 8089, 8090, 9090, 9094, 9100, 9201, 9202, 13080, 15432, 16379, 18000)
$LogPath = "$env:TEMP\docker-intranet-firewall.log"

try {
    # 기존 동일 규칙 있으면 제거 (멱등성)
    $existing = Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue
    if ($existing) {
        Remove-NetFirewallRule -DisplayName $RuleName
        Add-Content -Path $LogPath -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') REMOVED existing rule"
    }

    $rule = New-NetFirewallRule `
        -DisplayName $RuleName `
        -Description "Allow intranet PCs (10.10.100.0/24) to access Docker containers. Auto-created 2026-05-11." `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort $Ports `
        -RemoteAddress 10.10.100.0/24 `
        -Profile Private,Domain `
        -Enabled True

    Add-Content -Path $LogPath -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') CREATED rule: $($rule.DisplayName)"
    Write-Output "SUCCESS: $($rule.DisplayName)"
    exit 0
} catch {
    Add-Content -Path $LogPath -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ERROR: $_"
    Write-Error "FAILED: $_"
    exit 1
}
