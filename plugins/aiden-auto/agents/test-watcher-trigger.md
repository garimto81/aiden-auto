---
name: test-watcher-trigger
description: Phase 2.6 파일럿 — machine_framework_watcher.py 작동 검증용 임시 파일. ~/.claude/ Edit 발생 시 4 mirror auto-sync가 정상 작동하는지 확인.
model: haiku
tools: Read
---

# Test Watcher Trigger (Phase 2.6 파일럿)

이 파일은 v4 Phase 2.6 파일럿 검증용입니다.

## 검증 목적

- ~/.claude/agents/test-watcher-trigger.md 가 Write 도구로 생성됨
- PostToolUse hook (machine_framework_watcher.py) 가 자동 실행
- 4 mirror (project source + cache v28.2.0 + v28.1.0 + marketplaces) 모두에 동일 파일 sync 확인
- ~/.claude/.backup/{timestamp}/ 백업 디렉토리 생성 확인 (atomic write 정상 작동)
- ~/.claude/state/machine-framework-sync.log 로그 기록 확인

## 작성 시각

2026-05-14 Phase 2.6 파일럿

## 정리

검증 완료 후 이 파일은 삭제 또는 보존 (테스트 증거용).
