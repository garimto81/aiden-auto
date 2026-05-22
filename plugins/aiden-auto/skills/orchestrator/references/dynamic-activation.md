# 동적 Stream 추가 + 수정

## 트리거 (Observer Mode 중)

다음 패턴 발화 시 Architect Mode 일시 전환:

```
- "Stream X 추가"
- "QA 팀 추가"
- "Backend 코드 시작"
- "Stream X 일시 중단"
- "Stream X SCOPE 확장"
- "신규 작업 추가"
```

## 시퀀스

```python
def handle_dynamic_request(user_input):
    # 1. 현재 GitHub 상태 fetch
    state = fetch_current_state()
    
    # 2. 요청 분석
    request = parse_user_intent(user_input)
    # request = {action: 'add_stream', name: 'QA', scope: 'integration-tests/', ...}
    
    # 3. 영향 분석
    impact = analyze_impact(request, state)
    # impact = {
    #   conflicts: [],          # 기존 Stream과 충돌
    #   blocked_by_inferred: ['S1', 'S2'],
    #   placement: 'P4',
    # }
    
    # 4. 매트릭스 갱신 결정
    new_stream_id = next_available_id(state)  # S7, S8, ...
    
    # 5. team_assignment.yaml v+1 갱신
    update_team_assignment({
        'streams': {
            new_stream_id: {
                'name': request.name,
                'absorbs_existing': request.absorbs or [],
                'phases': infer_phases(request),
                'blocked_by': impact.blocked_by_inferred,
                'blocks': []
            }
        }
    })
    
    # 6. setup_stream_worktree.py 실행
    run_setup(new_stream_id)
    
    # 7. sync_design_to_github.py 실행
    run_sync()  # CODEOWNERS, workflows 갱신
    
    # 8. 사용자 보고
    print_summary(new_stream_id)
```

## 사용자 보고 형식

```
✅ {Stream Name} ({SX}) 추가 완료

📂 워크트리: {path}
🌿 흡수 폴더: {absorbs_existing}
🔗 의존성: {blocked_by} 완료 후 unblock
   현재 상태: {READY|BLOCKED}

📋 GitHub 인프라 갱신:
   - CODEOWNERS 추가
   - branch protection 갱신
   - 3개 workflow 적용

▶️ 작업 시작:
   code {worktree_path}
```

## SCOPE 수정 시퀀스

```
사용자: "Stream S2 SCOPE에 mobile/ 추가"
    │
    v
Orchestrator:
  1. 영향 분석:
     - mobile/ 다른 Stream에 매핑됐나? → 충돌 검사
     - 변경이 작업 중 Stream에 영향?
  
  2. 충돌 시:
     - 사용자에게 충돌 보고 (예외적 진입점)
     - 해결책 제안 (예: mobile/을 S2에서 빼고 S2에 추가)
  
  3. 충돌 없으면:
     - team_assignment.yaml 갱신
     - sync_design_to_github.py 실행
     - 활성 워크트리 .team 파일도 갱신 (수동 git pull 필요 알림)
```

## Stream 일시 중단

```
사용자: "Stream S3 일시 중단"
    │
    v
Orchestrator:
  1. 활성 PR 확인
  2. 활성 PR 있으면:
     - draft로 변환
     - issue label: status:paused
  3. 워크트리는 보존 (작업 재개 가능)
  4. 사용자 보고
```

## Stream 완전 제거

```
사용자: "Stream S5 제거"
    │
    v
Orchestrator (예외적 진입점 — 파괴적):
  1. 활성 PR 확인
  2. 활성 PR 있으면 사용자 확인 필수
  3. 활성 PR 없으면:
     - 워크트리 제거 (`git worktree remove`)
     - 브랜치 삭제 (`git branch -D`)
     - team_assignment.yaml 에서 제거
     - sync_design_to_github.py 실행
  4. 사용자 보고
```

## 진입점 분석

| 동적 액션 | 사용자 진입점 |
|----------|:----:|
| Stream 추가 | 1회 (요청 발화) |
| SCOPE 확장 (충돌 없음) | 1회 |
| SCOPE 확장 (충돌) | 2회 (요청 + 해결 결정) |
| 일시 중단 | 1회 |
| 완전 제거 (PR 없음) | 1회 |
| 완전 제거 (PR 있음) | 2회 (요청 + 파괴 확인) |

## Architect Mode 일시 전환 후 복귀

```python
def temporary_architect_mode(handler):
    """동적 요청 처리 후 Observer 모드 복귀"""
    monitor.pause()
    try:
        result = handler()
    finally:
        monitor.resume()
    return result
```

평균 처리 시간: 2-5분. 그 후 Observer 모드 복귀.
