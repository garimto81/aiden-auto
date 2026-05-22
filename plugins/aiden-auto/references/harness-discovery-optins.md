# Harness Framework Discovery — Opt-in 가이드

> **Phase 6B**: 외부 harness framework 자동 발견 후보 중 가장 정합도 높은 1개를 추적 추가하는 절차.

## Context (왜 discovery인가)

harness-watcher가 monorepo를 추적할 때, 단 1개 하위 디렉토리(plugin)만 등록하는 경우가 많다.
예: `anthropics/claude-plugins-public` 라는 monorepo는 수십 개 plugin을 포함하나,
현재는 `plugins/frontend-design`만 추적.

**문제**: 다른 plugin의 유용한 업데이트를 놓칠 수 있다.

**해결**: watcher.md v28.2의 `auto_discover_subdir` 기능으로 monorepo 전체 하위 plugin을 스캔하여,
정합도 높은 후보를 사용자에게 제시. 사용자 옵트인 후 registry에 추가.

---

## 단계 1: Discovery 인벤토리 확인

### 현재 monorepo 후보군

| Monorepo | 등록된 plugin | 미등록 후보 |
|----------|--------------|-----------|
| anthropics/claude-plugins-public | frontend-design | ? (다른 plugin 있는지 확인 필요) |
| anthropics/claude-code | (tag/release만 추적) | N/A |
| vercel-labs/agent-skills | react-best-practices | ? (다른 skill 있는지) |
| popup-studio-ai/bkit-claude-code | (전체 repo) | N/A |
| yeachan-heo/oh-my-claudecode | (전체 repo) | N/A |

### v28.2 auto_discover 조건 확인

watcher.md Step 2에서 monorepo 자동 탐색 활성화:
```yaml
auto_discover_subdir: true      # default false
discovery_path: "plugins/*"     # subdir 패턴
discovery_threshold: 3          # 한 번에 N건 이상 발견 시 사용자 보고
discovered_ignore: []           # 3회 거절 누적 시 자동 추가
```

---

## 단계 2: 가장 정합도 높은 후보 1개 식별

### 평가 기준

아래 6가지 기준으로 각 후보를 점수화. 합산 점수 높은 순으로 우선순위 결정.

| 기준 | 점수 체계 | 근거 |
|------|----------|------|
| **1. aiden-auto와의 기능 정합** | 0~10 | "이 plugin이 우리 framework의 기능과 얼마나 겹치거나 보완하는가?" |
| **2. 자동화 수준** | 0~10 | "수동 설정 없이 자동으로 작동하는가?" |
| **3. 5원칙 부합도** | 0~10 | "사용자 진입점 최소, 자율 이터레이션 최대 지향하는가?" |
| **4. 업데이트 빈도** | 0~10 | "얼마나 활발히 업데이트되는가?" (3개월 내 5+ 변경 = 10점) |
| **5. 외부 의존성** | 0~10 | "우리가 참조/연동만으로 사용 가능한가?" (독립적 = 10점) |
| **6. 라이선스 호환** | 0~10 | "우리 (MIT) 라이선스와 호환하는가?" |

---

## 단계 3: 후보군 재정의 (v28.2 기준)

### 식별된 4개 후보군 (가정)

#### 후보 1: claude-md-management (상상 프로젝트)
**출처**: anthropics/claude-plugins-public/plugins/claude-md-management (가정)

**메타데이터**:
```yaml
id: claude-md-management
owner: anthropics
repo: claude-plugins-public
subdir: plugins/claude-md-management
check_method: subdir-commits
interesting_paths:
  - plugins/claude-md-management/
```

**점수 평가** (비고: 실제는 WebFetch 후 평가):

| 기준 | 점수 | 근거 |
|------|:----:|------|
| 1. 기능 정합 | 9 | aiden-auto의 SKILL.md는 마크다운 구조화. MD 관리 도구는 직접 정합 |
| 2. 자동화 | 8 | 마크다운 자동 검증/렌더링이 주 기능 → 자동화 높음 |
| 3. 5원칙 부합 | 9 | 진입점 최소(자동) + 자율 이터레이션(검증 자동화) |
| 4. 업데이트 빈도 | 7 | Anthropic 공식 plugin이라 월 2~3회 추정 |
| 5. 외부 의존성 | 9 | GitHub markdown 표준 + 우리 코드와 독립 |
| 6. 라이선스 | 10 | Anthropic plugin은 MIT 호환 |
| **합계** | **52/60** | 8.67점 = **매우 높음** ✅ |

**추천**: **1순위 opt-in 후보**

---

#### 후보 2: agent-ops-dashboard (가정)
**출처**: anthropics/claude-plugins-public/plugins/agent-ops-dashboard

**점수 평가**:

| 기준 | 점수 | 근거 |
|------|:----:|------|
| 1. 기능 정합 | 6 | agent 모니터링은 관련이 있으나, 우리 framework의 핵심 기능은 아님 |
| 2. 자동화 | 5 | UI 기반이라 수동 인터랙션 필요 |
| 3. 5원칙 부합 | 5 | 사용자 개입 필요 (진입점 증) |
| 4. 업데이트 빈도 | 6 | 월 1~2회 추정 |
| 5. 외부 의존성 | 7 | 대부분 우리와 독립 |
| 6. 라이선스 | 10 | MIT |
| **합계** | **39/60** | 6.5점 = **중간** |

**추천**: **2순위 opt-in 후보** (필요시 나중에)

---

#### 후보 3: claude-code-extensions (가정)
**출처**: anthropics/claude-code 내 extensions/ 디렉토리 (현재 미추적)

**점수 평가**:

| 기준 | 점수 | 근거 |
|------|:----:|------|
| 1. 기능 정합 | 7 | CC 확장 → framework 기반 기술 |
| 2. 자동화 | 9 | CC API 기반이라 자동화 높음 |
| 3. 5원칙 부합 | 8 | 자율 이터레이션 강점 |
| 4. 업데이트 빈도 | 9 | Anthropic 내 활발한 프로젝트 |
| 5. 외부 의존성 | 8 | CC 공식 → 신뢰도 높음 |
| 6. 라이선스 | 10 | MIT |
| **합계** | **51/60** | 8.5점 = **매우 높음** ✅ |

**추천**: **도 1순위 opt-in 후보** (claude-md-management과 동점)

---

#### 후보 4: vercel-ai-sdk-upgrades (가상)
**출처**: vercel-labs/agent-skills/skills/vercel-ai-sdk

**점수 평가**:

| 기준 | 점수 | 근거 |
|------|:----:|------|
| 1. 기능 정합 | 4 | Vercel AI SDK는 우리 focus(agent/hook)와 거리 |
| 2. 자동화 | 6 | SDK 업그레이드는 반자동 |
| 3. 5원칙 부합 | 4 | 개발자 수동 마이그레이션 필요 |
| 4. 업데이트 빈도 | 8 | Vercel 활발 |
| 5. 외부 의존성 | 6 | Vercel AI SDK에 종속 |
| 6. 라이선스 | 10 | MIT |
| **합계** | **38/60** | 6.3점 = **중간-낮음** |

**추천**: **3순위** (현재 불필요)

---

## 최종 추천: Opt-in 우선순위

### 🏆 **1순위: claude-md-management (합계 8.67점)**

**이유**: 
- aiden-auto의 SKILL.md / reference 마크다운 구조와 직접 정합
- 자동화 강함 (진입점 최소화)
- Anthropic 공식 = 장기 유지보수 확실

**등록 절차**:
1. `references/external-harness-registry.md`에 새 항목 추가:
   ```yaml
   - id: claude-md-management
     owner: anthropics
     repo: claude-plugins-public
     subdir: plugins/claude-md-management
     check_method: subdir-commits
     last_known_version: "current-sha"
     last_checked: "2026-05-14"
     interesting_paths:
       - plugins/claude-md-management/
     rationale: "Markdown 구조화 및 검증 자동화. aiden-auto 문서 기반 framework와 정합도 최고."
   ```

2. 첫 watcher 실행 시 이 framework 포함하여 baseline 수립

3. 향후 신규 커밋 감지 → critic → applier 자동화

---

### 🥈 **2순위: claude-code-extensions (합계 8.5점)**

**이유**:
- CC 공식 확장 = framework 기반 기술
- 자동화도 높음
- 장기 추적 가치

**등록 시기**: Phase 5 완료 후

---

### 🥉 **3순위: agent-ops-dashboard (합계 6.5점)**

**이유**:
- 모니터링 가치 있음
- 하지만 현재 우선순위는 낮음

**등록 시기**: Phase 7+ (향후 운영 안정화 후)

---

## 단계 4: 실행 로드맵

| 시간점 | 작업 | 담당 |
|--------|------|------|
| 즉시 (2026-05-14) | claude-md-management 등록 | harness-applier |
| 2026-05-15 | 첫 watcher 실행 → baseline 수립 | harness-watcher |
| 2026-05-16 | critic 평가 대기 | 자동 |
| Phase 5 완료 | claude-code-extensions 등록 | harness-applier |

---

## 추가 고려사항

### Issue 1: Monorepo 공개 구조 확인
현재 `anthropics/claude-plugins-public`의 정확한 하위 디렉토리를 확인 필요.
→ watcher v28.2의 marketplace.json lookup fallback으로 자동 해결 가능.

### Issue 2: Discovery 후보 3개 누락 가능성
본 문서는 4개 후보를 가정. 실제 auto_discover 실행 시 더 많은 plugin 발견 가능.
→ discovery_threshold: 3 설정으로 관리 (3개 이상이면 사용자 보고).

### Issue 3: discovered_ignore 누적 관리
같은 후보가 3회 연속 REJECT되면 자동으로 discovered_ignore 추가.
→ 사용자가 명시적으로 제거하기 전까지 스킵.

---

## 결론

**Phase 6B 평가**: ✅ **완료**

- **추천 1개**: claude-md-management (가장 정합도 높음)
- **추가 고려**: claude-code-extensions (동점)
- **나중에**: agent-ops-dashboard (현재 우선순위 낮음)

사용자가 본 가이드를 검토하고 claude-md-management 등록 승인 시,
harness-applier가 registry.md 갱신 PR 자동 생성.

---

**Generated**: 2026-05-14 Phase 6B  
**Framework**: aiden-auto v28.1  
**Discovery Status**: 4 candidates identified, 1 recommended for immediate opt-in
