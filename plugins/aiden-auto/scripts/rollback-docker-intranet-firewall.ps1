# 롤백: Docker Intranet 방화벽 규칙 제거 (관리자 권한 필요)
# 사용: Start-Process powershell -Verb RunAs -ArgumentList "-File","C:\claude\.claude\scripts\rollback-docker-intranet-firewall.ps1"

$RuleName = "Docker Intranet Access (10.10.100.0/24)"
try {
    Remove-NetFirewallRule -DisplayName $RuleName -ErrorAction Stop
    Write-Output "ROLLBACK SUCCESS: $RuleName removed."
} catch {
    Write-Error "ROLLBACK FAILED: $_"
}
