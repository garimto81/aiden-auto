# Observer Mode — Phase 1+ 모니터링

## 트리거

Phase 0 종료 직후 자동 진입. 영구 모드.

## 핵심 원칙

> **Orchestrator는 코드/문서 한 줄도 작성하지 않는다. GitHub만 본다.**

활동:
1. 30초 간격 GitHub 폴링
2. 의존성 위반 자동 감지 + 경고
3. 사용자 동적 요청 처리 (Architect Mode 일시 전환)
4. 24h+ idle Stream 사용자 escalate

## 폴링 명령어 (단일)

```bash
gh issue list --state all --limit 50 \
  --json number,title,state,labels,assignees,createdAt,updatedAt \
  > /tmp/orch_issues.json

gh pr list --state all --limit 50 \
  --json number,title,state,mergeable,headRefName,labels,statusCheckRollup,mergedAt,createdAt,updatedAt \
  > /tmp/orch_prs.json
```

## 분석 알고리즘

```python
def analyze_state(issues, prs, team_assignment):
    state = {}
    
    for stream_id, config in team_assignment['streams'].items():
        # 이 Stream의 활성 PR/issue 매칭
        stream_label = f"stream:{stream_id}"
        stream_issues = [i for i in issues if stream_label in i['labels']]
        stream_prs = [p for p in prs if stream_label in p['labels']]
        
        # 진행 상태 분류
        if not stream_issues:
            state[stream_id] = "IDLE"
        elif any(p['state'] == 'OPEN' and 'draft' in p['labels'] for p in stream_prs):
            state[stream_id] = "IN_PROGRESS"
        elif any(p['state'] == 'OPEN' and 'ready' in p['labels'] for p in stream_prs):
            state[stream_id] = "REVIEW"
        elif any(p['state'] == 'MERGED' for p in stream_prs):
            state[stream_id] = "DONE"
        else:
            state[stream_id] = "UNKNOWN"
        
        # 의존성 위반 검사
        for upstream in config.get('blocked_by', []):
            if state.get(upstream) != "DONE" and state[stream_id] in ['IN_PROGRESS', 'REVIEW']:
                state[f'violation_{stream_id}'] = upstream
    
    return state
```

## 상황판 출력 (사용자 요청 시)

```
+--------+-------+----------+-------------+--------+
| Stream | 상태   | Issue    | PR          | Last   |
+--------+-------+----------+-------------+--------+
| S1     | DONE  | #142     | #143 ✓      | 2h ago |
| S2     | INPROG| #144     | #145 (draft)| 30m ago|
| S3     | INPROG| #146     | #147 (draft)| 15m ago|
| S4     | INPROG| #148     | #149 (CI)   | 5m ago |
| S5     | IDLE  | -        | -           | -      |
| S6     | IDLE  | -        | -           | -      |
+--------+-------+----------+-------------+--------+

진행 매트릭스:
  Phase 1 (Foundation):    ✅ DONE
  Phase 2 (Lobby/CC/RIVE): 🔄 3/3 진행 중
  Phase 3 (AI Track/Proto):⏸ S2~S4 머지 대기
```

## 의존성 위반 자동 처리

```python
def handle_violation(stream_id, upstream):
    """upstream Stream이 DONE 아닌데 stream_id가 IN_PROGRESS인 경우"""
    
    # 1. 경고 issue 자동 생성 (강제는 GitHub Action이 함)
    body = f"""
## ⚠️ Dependency Violation Detected

Stream: {stream_id}
Status: IN_PROGRESS
Blocked by: {upstream} (status: {upstream_state})

이 Stream의 워크트리에서 작업이 진행 중이지만,
의존하는 Stream이 아직 완료되지 않았습니다.

권장 행동:
- {stream_id} 작업을 일시 중단
- {upstream} 완료까지 대기
- {upstream} merge 시 자동 unblock 알림

자동 차단:
- PreToolUse hook이 Edit/Write를 차단하고 있음
- PR 생성은 가능하나 머지는 GitHub action이 차단
"""
    subprocess.run([
        'gh', 'issue', 'create',
        '--title', f'⚠️ {stream_id} dependency violation',
        '--label', f'orchestrator-warning,stream:{stream_id}',
        '--body', body
    ])
```

## 24h+ Idle 처리

```python
def handle_idle_stream(stream_id, last_activity):
    if (now - last_activity) > timedelta(hours=24):
        # 사용자에게 1회 escalate (반복 X)
        if not already_escalated(stream_id):
            print(f"⚠️ {stream_id} idle 24h+. 사용자 확인 필요:")
            print(f"   원인: blocking issue / 작업 중단 / 누락")
            print(f"   조치: 'Stream {stream_id} 상태 확인' 같은 명시 요청")
            mark_escalated(stream_id)
```

## 동적 요청 처리

사용자가 다음 패턴 발화 시 → Architect Mode 일시 전환:

```
- "Stream X 추가"
- "QA 팀 추가"
- "Backend 코드 시작"
- "Stream X scope 확장"
- "Stream X 일시 중단"
```

→ `references/dynamic-activation.md` 참조.

## 사용자 진입점 측정

Observer Mode 운영 중 사용자 진입점:

| 액션 | 횟수 | 비고 |
|------|:----:|------|
| 상황판 보기 요청 | N회 | 자연스러운 모니터링 |
| 동적 추가/수정 | M회 | Architect 일시 전환 |
| 24h idle escalate 응답 | 1회/Stream | 매우 드뭄 |
| 모니터링 자체 | 0회 | 자동 |

## 종료 조건

Observer Mode는 영구. 명시적 종료 없음.

다만 다음 경우 일시 정지:
- 사용자가 "오케스트레이터 일시 중단" 명시
- 모든 Stream DONE 상태 (프로젝트 종료 신호)

## 폴링 비용 관리

GitHub API rate limit (5000/h authenticated):
- 30초 폴링 = 120/h
- gh issue + pr = 2 API calls
- 총 240/h → 4.8% 사용 (안전)

만약 rate limit 도달:
- 폴링 간격 60초로 자동 확장
- conditional requests (etag) 사용
