# Stream Matrix 자동 추론 알고리즘

## 트리거

스킬 호출 직후 Phase -1에서 자동 실행.

## 입력 (자동 수집)

```python
inputs = {
    'repo_root':      git_rev_parse_show_toplevel(),
    'project_name':   basename(repo_root),
    'top_folders':    list_top_level_folders(repo_root),
    'tech_stack':     detect_tech_stack(repo_root),
    'docs_present':   detect_docs(repo_root),
    'tests_present':  detect_tests(repo_root),
    'monorepo':       detect_monorepo(repo_root),
    'user_intent':    last_user_message(),
    'existing_design': check_existing_team_assignment(repo_root),
}
```

## 알고리즘

### Step 1. 기존 매트릭스 우선

```python
if exists(f"{repo_root}/docs/orchestrator/team_assignment.yaml"):
    # 이미 정립된 프로젝트 (예: EBS v10.3)
    # 자동 추론 스킵, 기존 매트릭스 사용
    return load_existing_matrix()
```

### Step 2. 사용자 의도 분류

```python
INTENT_PATTERNS = {
    'parallel_dev': [
        '병렬 개발', '동시 작업', '여러 팀',
        '팀 분담', 'multi-team'
    ],
    'planning_phase': [
        '기획', 'PRD', '설계', '문서화'
    ],
    'code_implementation': [
        '구현', '코드 작성', 'implement'
    ],
    'migration': [
        '마이그레이션', '리팩토링 대규모', 'migration'
    ],
    'qa_addition': [
        'QA 추가', '테스트 강화', '검증 추가'
    ]
}

intent = match_intent(user_intent, INTENT_PATTERNS)
```

### Step 3. 폴더 → Stream 매핑 (휴리스틱)

```python
FOLDER_TO_STREAM = {
    # 직접 매핑 (확실)
    'frontend':         'Frontend Stream',
    'backend':          'Backend Stream',
    'mobile':           'Mobile Stream',
    'web':              'Web Stream',
    'api':              'API Stream',
    'shared':           'Shared Stream',
    
    # EBS 패턴
    'team1-frontend':   'Frontend Stream',
    'team2-backend':    'Backend Stream',
    'team3-engine':     'Engine Stream',
    'team4-cc':         'Command Center Stream',
    
    # Monorepo 패턴 (apps/*, packages/*)
    'apps/web':         'Web App Stream',
    'apps/mobile':      'Mobile App Stream',
    'apps/api':         'API Stream',
    'packages/ui':      'UI Package Stream',
    'packages/shared':  'Shared Package Stream',
    
    # 테스트
    'integration-tests':'Integration Test Stream',
    'e2e':              'E2E Test Stream',
    'tests':            'Test Stream',
}
```

### Step 4. Foundation Stream 자동 신설

```python
# PRD/문서가 없거나 분산되어 있으면 Foundation Stream 신설
if not docs_present or docs_scattered():
    streams['S1'] = {
        'name': 'Foundation',
        'role': 'PRD + 핵심 설계 문서',
        'absorbs_existing': [],
        'phases': {
            'P1': {
                'scope_owns': ['docs/PRD.md', 'docs/architecture.md']
            }
        },
        'blocked_by': [],
        'blocks': all_other_stream_ids()
    }
```

### Step 5. 의존성 그래프 추론

```python
DEPENDENCY_HEURISTICS = {
    # Foundation은 항상 first
    'Foundation Stream': {'blocked_by': []},
    
    # 코드 Stream은 Foundation 후
    '*Code*':            {'blocked_by': ['Foundation Stream']},
    
    # Test Stream은 코드 Stream 후
    '*Test*':            {'blocked_by': all_code_streams()},
    
    # QA Stream은 모든 후
    '*QA*':              {'blocked_by': all_streams_except_self()},
    
    # Frontend는 Backend API 의존 (있으면)
    'Frontend*':         {'blocked_by': ['Backend Stream'] if has_backend else []},
}
```

### Step 6. 매트릭스 검증

```python
def validate_matrix(matrix):
    # 1. 모든 폴더가 정확히 한 Stream에 매핑
    for folder in top_folders:
        owners = [s for s in matrix if folder in s.absorbs_existing]
        assert len(owners) <= 1, f"Folder {folder} owned by multiple streams"
    
    # 2. SCOPE 교집합 0
    for s1, s2 in combinations(matrix, 2):
        assert disjoint(s1.scope_owns, s2.scope_owns)
    
    # 3. 의존성 사이클 없음
    assert is_dag(matrix.dependency_graph)
    
    # 4. 도달 불가 Stream 없음
    assert all_reachable(matrix.dependency_graph)
```

### Step 7. 사용자 1회 검토

추론된 매트릭스를 사용자에게 표로 보여주고 1회 검토:

```
🤖 Stream 매트릭스 자동 추론 결과:

+--------+--------------------+------------------+--------+----------+
| Stream | 이름                | 흡수 폴더         | Phase  | 의존성    |
+--------+--------------------+------------------+--------+----------+
| S1     | Foundation         | (신설)           | P1     | (없음)    |
| S2     | Frontend Stream    | frontend/        | P2     | S1       |
| S3     | Backend Stream     | backend/         | P2     | S1       |
| S4     | Shared Stream      | shared/          | P2     | S1       |
| S5     | Integration Test   | integration-tests/ | P3   | S2,S3,S4 |
+--------+--------------------+------------------+--------+----------+
```

위 매트릭스(작업 갈래 나누기 표)를 보여준 뒤 AskUserQuestion 으로 승인 받는다:

```
AskUserQuestion(
  question="여러 세션이 동시에 나눠서 일할 작업 갈래(Stream)를 위 표처럼 자동으로 나눠봤어요. 이대로 시작할까요?",
  header="Stream 승인",
  multiSelect=false,
  options=[
    {label: "진행", description: "위 표 그대로 승인 — 각 작업 갈래대로 세션 폴더를 만들고 바로 시작합니다. (권장: 표가 맞으면 이걸 고르세요)"},
    {label: "수정", description: "작업 갈래를 더하거나 뺍니다 — 예: 검수(QA) 갈래 추가, 통합 테스트 갈래 제외 등. 무엇을 바꿀지 알려주면 표를 다시 만들어 보여드립니다."},
    {label: "취소", description: "지금은 갈래 나누기를 멈춥니다 — 세션 폴더를 만들지 않고 작업을 시작하지 않습니다."}
  ]
)
```

"수정" 선택 시 매트릭스 갱신 후 재확인. "진행" 선택 시 즉시 Phase 0 Step 3로.

## 추론 실패 케이스 + 대응

| 케이스 | 대응 |
|------|------|
| 폴더 0개 (빈 레포) | Foundation Stream 1개만 신설, "단일 Stream으로 진행" 안내 |
| 폴더 매핑 모호 (frontend 인지 web 인지 etc) | 사용자에게 1회 확인 (예외적 진입점) |
| 의존성 추론 모호 | 직렬화 가정 (가장 안전) + 사용자가 검토에서 수정 가능 |
| Monorepo (apps/* + packages/*) | apps별 + packages별 별도 Stream |
| 너무 많은 폴더 (10개+) | 사용자에게 "Stream 8개 이상이면 비효율적. 그룹화 권장" 알림 |

## 추론 정확도 개선 (학습)

매 호출마다 사용자 검토 결과(수정 사항)를 `~/.claude/skills/orchestrator/state/inference_corrections.json` 에 기록:

```json
{
  "corrections": [
    {
      "date": "2026-05-07",
      "project": "myapp",
      "auto_inferred": ["frontend", "backend"],
      "user_corrected": ["frontend", "backend", "qa"],
      "lesson": "프로젝트에 e2e/ 폴더 있으면 QA Stream 자동 추가"
    }
  ]
}
```

다음 호출 시 lessons 자동 적용. 시간이 지날수록 추론 정확도 향상.

## EBS 특화 처리 (호환성)

EBS 프로젝트에서 호출 시:
1. 기존 v10.3 매트릭스 발견 (`docs/4. Operations/team_assignment.yaml`)
2. 자동 추론 스킵
3. 사용자 검토도 스킵 (이미 정립됨)
4. 즉시 Phase 0 Step 3로 진행

다른 프로젝트에서 호출 시:
1. Phase -1 자동 분석
2. Step 7 사용자 1회 검토
3. 그 외 모두 자율
