# Evaluation Schema — 5 객관 지표 + Verdict 룰

> Reader Agent 가 평가 출력 시 따르는 schema. 환각 방지 + variance ↓ + 자동 집계 가능.

## 5 객관 지표 정의

### 1. recall (회상도)

**정의**: 문서 read 직후 핵심 thesis 5개를 회상할 수 있는가?

**측정**:
- RVP (Reader Value Proposition) 의 `key_thesis_5` 와 매칭
- read 직후 (별도 lookup 없이) 회상 가능한 항목 / 5

**점수**:
| 점수 | 기준 |
|:---:|------|
| 5/5 | 5개 모두 회상 가능 |
| 4/5 | 4개 회상 (1개 모호) |
| 3/5 | 3개 회상 (PASS 경계) |
| 2/5 | 2개 이하 (FAIL) |
| 1/5 | 1개 이하 (FAIL) |

**PASS 기준**: 4/5 이상

---

### 2. ambiguity (모호 지점)

**정의**: 문서 read 중 의문이 발생하는 지점의 수.

**측정**:
- 정확한 위치 (§X.Y) + 인용 + 의문 1줄 명시
- 예: `§1.4 마지막 단락 "1단계 운영 방식..." — 갑자기 등장한 framing, 왜 여기?`

**점수**: 항목 수 (절대 수치)

**PASS 기준**: 5 항목 이하

---

### 3. cognitive (인지 부담)

**정의**: 문서 전체의 인지 부담 정도.

**측정**:
- 5 챕터 연속 산문 (시각 자료 0) → -1
- 한 단락 200자 초과 → -1 (개수 무관)
- 약어 첫 등장 풀이 누락 → -1
- 다이어그램 없는 흐름 설명 → -1

**점수**: 5점 만점에서 위반 항목수 차감

| 점수 | 기준 |
|:---:|------|
| 5/5 | 위반 0 |
| 4/5 | 위반 1 |
| 3/5 | 위반 2 (PASS 경계) |
| 2/5 | 위반 3 |
| 1/5 | 위반 4+ |

**PASS 기준**: 4/5 이상

---

### 4. identity (정체성 일관성) ⚠️ 가장 중요

**정의**: 각 챕터의 본문 메시지가 챕터의 정체성과 일치하는가?

**측정**:
- 각 챕터의 frontmatter / 챕터 제목 / 도입부에서 챕터 정체성 추출
- 본문 read 후 본문 메시지가 정체성과 매칭되는지 평가
- 위반 = 정체성과 다른 시점/주제 침투

**위반 예시 (직전 사고)**:
- §1.6 "미션 = 정확한 번역가" 정체성에 "1단계 → 2단계 무인화 진화" 침투
- §7.3 "현재 입출력 센서" 정체성에 "2단계 미래 컴포넌트 80줄" 침투

**점수**: 5점 만점에서 위반 챕터수 차감

| 점수 | 기준 |
|:---:|------|
| 5/5 | 위반 0 |
| 4/5 | 위반 1 |
| 3/5 | 위반 2 (FAIL) |
| 2/5 | 위반 3 |
| 1/5 | 위반 4+ |

**PASS 기준**: 5/5 (위반 0). identity 위반은 **즉시 MAJOR verdict**.

---

### 5. artifice (작위 식별) ⚠️ 가장 중요

**정의**: 작위적 / 강제 삽입 느낌의 단락 식별.

**측정**:
- 정확한 위치 (§X.Y) + 인용 + 작위 사유 1줄 명시
- 예: `§1.4 마지막 단락 "본 입력 모델은 1단계..." — 챕터 흐름과 무관, 강제 cross-reference`

**작위 패턴**:
- 매 챕터에 같은 cross-reference 반복 (§9 참조 같은)
- 챕터 정체성과 무관한 footer 단락
- 직전 단락과 흐름이 끊긴 갑작스런 등장
- 다른 챕터의 주제가 침투

**점수**: 항목 수 (절대 수치)

**PASS 기준**: 0 항목. artifice 위반은 **즉시 MAJOR verdict**.

---

### 6. emotional_engagement (몰입·재미) 🆕 advisory

**정의**: 문서를 끝까지 읽고 싶게 만드는가? (글맛)

> ⚠️ **advisory 지표**: 명료성 지표(1~5)와 달리 **MAJOR/REJECT 를 유발하지 않는다**. 명료한 문서가 밋밋하면 MINOR 개선 권고만. 명료성이 항상 바닥(floor), 글맛은 천장(ceiling).

**측정**:
- 서사 흐름: 도입→전개→마무리가 끌고 가는가
- 문체 리듬: 문장 길이 변주 / 목소리(voice) 존재
- 비유 신선도: 진부 관용구 0, 살아있는 비유

**점수**: 5점 척도

| 점수 | 기준 |
|:---:|------|
| 5/5 | 손을 못 떼게 함 (탁월) |
| 4/5 | 읽는 맛 분명 (PASS 경계) |
| 3/5 | 정확하나 밋밋 |
| 2/5 | 단조·흐름 끊김 |
| 1/5 | 글맛 전무 |

**advisory PASS 기준**: 3/5 이상이면 충분. 2/5 이하 → MINOR 권고 (블로킹 X).

---

### 7. memorability (기억에 남음) 🆕 advisory

**정의**: 24시간 후 한 장면/문장이 또렷이 남는가?

> ⚠️ **advisory 지표**: emotional_engagement 와 동일 — MAJOR/REJECT 권한 없음.

**측정**:
- read 직후가 아닌 "하루 뒤 떠오르는 한 컷" 가정
- 또렷한 장면/비유/문장 1개 이상 → 높음

**점수**: 5점 척도 (5=또렷한 한 컷 / 1=읽자마자 증발)

**advisory PASS 기준**: 3/5 이상. 2/5 이하 → MINOR 권고 (블로킹 X).

---

## 출력 schema (Reader Agent 응답 형식)

```json
{
  "reader_id": "P1",
  "reader_name": "외부 시니어 개발자",
  "audience": "외부 개발팀",
  "filepath": "docs/1. Product/Foundation.md",
  "read_completed": true,
  "scores": {
    "recall": 4,
    "ambiguity": 2,
    "cognitive": 4,
    "identity": 3,
    "artifice": 1,
    "emotional_engagement": 3,
    "memorability": 2
  },
  "ambiguity_points": [
    {
      "location": "§1.4 마지막 단락",
      "quote": "본 입력 모델은 1단계 운영 방식이며...",
      "concern": "갑자기 등장한 framing, 왜 여기?"
    },
    {
      "location": "§9.2 X1/X2/Y1/Y2",
      "quote": "X1 → X2 → X3 → X4 / Y1 ==> Y2",
      "concern": "단계 이름이 코드로 추상화되어 의미 떨어짐"
    }
  ],
  "identity_violations": [
    {
      "chapter": "§1.6 미션",
      "expected_identity": "EBS 정체성 (정확한 번역가 + 5 핵심 가치)",
      "actual_message": "1단계 Trinity → 2단계 무인화 진화 framing",
      "severity": "high"
    },
    {
      "chapter": "§7.3 Vision Layer",
      "expected_identity": "현재 입출력 센서",
      "actual_message": "2단계 미래 컴포넌트 80줄",
      "severity": "high"
    }
  ],
  "artifice_points": [
    {
      "location": "§1.4 마지막 단락",
      "quote": "본 입력 모델은 1단계 운영 방식이며, 2단계 진화 시...",
      "reason": "챕터 흐름과 무관, 강제 cross-reference"
    }
  ],
  "post_reading_critique": "Foundation 의 3 입력 Trinity 개념은 명확하다. RFID/CC/룰 의 trinity 가 §1.3-1.5 에 잘 풀어져 있다. 그러나 §1.6 미션 챕터부터 갑자기 '1단계 → 2단계' 진화 framing 이 시작되어 '내가 지금 정체성을 읽는지 로드맵을 읽는지' 헷갈리기 시작한다. §7.3 Vision Layer 가 통째로 80줄 들어오면서 '이 챕터는 현재인가 미래인가' 의문이 폭발. §Ch.9 까지 가서야 무인화의 자연스러운 home 을 만나지만 이미 인지 부담 누적. Verdict: MAJOR — identity 위반 2건 + artifice 1건이 가장 큰 문제.",
  "verdict": "MAJOR",
  "verdict_reason": "identity 3/5 (위반 2) + artifice 1 (위반 1) → 즉시 MAJOR",
  "improvement_plan": [
    "§1.6 미션 챕터의 '1단계 → 2단계' framing 제거, 5 핵심 가치 본문 복원",
    "§7.3 Vision Layer 챕터 → §Ch.9 영역으로 이동 또는 짧게 축소",
    "§1.4 마지막 단락 cross-reference 삭제"
  ]
}
```

---

## Verdict 판정 룰 (자동 집계)

```python
def determine_verdict(scores, identity_violations, artifice_points):
    # 1. 즉시 MAJOR/REJECT 조건
    if scores["identity"] < 5 or len(artifice_points) > 0:
        if scores["identity"] <= 2 or len(artifice_points) >= 5:
            return "REJECT"
        return "MAJOR"

    # 2. recall / cognitive 둘 다 PASS
    if scores["recall"] >= 4 and scores["cognitive"] >= 4 and scores["ambiguity"] <= 5:
        # 2b. 글맛 advisory 검사 (MINOR 한정 — 절대 MAJOR/REJECT 유발 안 함)
        #     명료성은 바닥(floor), 글맛은 천장(ceiling). 글맛 낮음 = 개선 권고일 뿐.
        lit_low = scores.get("emotional_engagement", 3) <= 2 or scores.get("memorability", 3) <= 2
        # 3. 명료성 완벽(만점)일 때만 글맛이 verdict 를 좌우한다.
        #    (명료성이 약한 PASS면 어차피 아래 4번 MINOR — 글맛 무관.
        #     즉 글맛 강등은 "명료성 만점인데 글맛만 낮은" 좁은 교집합에서만 발동. 의도된 동작.)
        if scores["recall"] == 5 and scores["cognitive"] == 5 and scores["ambiguity"] == 0:
            return "MINOR" if lit_low else "APPROVE"
        # 4. 일부 약한 PASS → MINOR
        return "MINOR"

    # 5. 다수 FAIL → MAJOR
    fail_count = sum([
        scores["recall"] < 4,
        scores["cognitive"] < 4,
        scores["ambiguity"] > 5,
    ])
    if fail_count >= 2:
        return "MAJOR"

    return "MINOR"
```

## Aggregator 룰 (Primary + Secondary 합)

> **운영 SSOT = `reader-panel-workflow.md` 의 aggregate()** (v2.1, advisory 3-인자 + 글맛 MINOR clamp 포함). 아래 가중평균 버전은 점수 환산 참고용. **glmat advisory(P6)는 두 버전 모두에서 MINOR 천장** — 명료성을 누르지 못함.

```python
def aggregate(primary_verdict, secondary_verdict, advisory_verdict=None):
    # advisory_verdict(POLISHED/READABLE/FLAT)는 MINOR 이상 격상 불가 (clamp).
    # 명료성(primary/secondary)만 MAJOR/REJECT 권한 보유.
    # 우선순위: REJECT > MAJOR > MINOR > APPROVE
    priority = {"REJECT": 4, "MAJOR": 3, "MINOR": 2, "APPROVE": 1}

    p_priority = priority[primary_verdict]
    s_priority = priority[secondary_verdict]

    # Primary 가중 (1.5x)
    weighted_p = p_priority * 1.5
    weighted_s = s_priority * 1.0

    # 가중 평균 → 최종 verdict
    avg = (weighted_p + weighted_s) / 2.5

    if avg >= 3.5:
        return "REJECT"
    elif avg >= 2.5:
        return "MAJOR"
    elif avg >= 1.5:
        return "MINOR"
    return "APPROVE"
```

**예외 룰** (가중 무시):
- 어느 한 명이라도 REJECT → 자동 REJECT
- 어느 한 명이라도 identity 위반 발견 → 자동 MAJOR 이상

---

## 직전 사고로 검증 (Foundation v3.1)

가상 평가:

```yaml
primary_p1:  # 외부 시니어 개발자
  recall: 4/5      # 3 입력 Trinity 회상 가능, 무인화 path 회상 모호
  ambiguity: 4    # §1.4 마지막, §1.6 1단계 framing, §7.3 통째, §9.2 추상 코드
  cognitive: 3/5   # 5 챕터 연속 산문 1회 + Vision Layer 통째 무거움
  identity: 2/5    # §1.6 + §7.3 + §1.4 = 3 챕터 위반
  artifice: 4     # §1.4 마지막, §5.4, §7.3, §9.1 표
  verdict: MAJOR (identity 2/5)
  verdict_reason: "identity 위반 3건 + artifice 4건"

secondary_p4:  # 18세 일반인
  recall: 3/5      # 3 입력 회상 일부, 무인화 6 카메라 모호
  ambiguity: 6    # 1단계/2단계 framing 매번 등장
  cognitive: 4/5   # 시각 자료 풍부하지만 복잡
  identity: 3/5    # 같은 위반 식별
  artifice: 3     # 작위 침투 일부 식별
  verdict: MAJOR

aggregated_verdict: MAJOR
aggregated_action: "writer 재호출 (iter 1/3)"
```

→ **본 워크플로우가 있었다면 Foundation v3.1 commit 전에 잡혔을 것**.

---

## Schema 진화

**활성 지표 (현재 7 종)**: recall · ambiguity · cognitive · identity · artifice (명료성 5) + emotional_engagement · memorability (글맛 advisory 2 — v2.0 활성화).

추후 추가 가능 지표:
- **actionability** — 읽은 후 다음 행동 명확성
- **trust** — 문서 신뢰도 (출처 / 근거)

신규 지표 추가 시 본 schema 갱신 + version bump.

> **지표 등급 (v2.0)**: 명료성 5종 = **블로킹(MAJOR/REJECT 가능)**. 글맛 2종 = **advisory(MINOR 한정)**. 글맛은 명료성을 누르지 못한다 — 명료한 문서를 글맛 부족만으로 reject 금지. prose-critic agent 가 글맛 2종을 전담 평가.

## Edit History

| 날짜 | 버전 | 트리거 | 변경 |
|------|:----:|--------|------|
| 2026-05-06 | v1.0 | /chapter-doc skill 신설 | 5 객관 지표 + Verdict 룰 + Aggregator 최초 정의 |
| 2026-06-01 | v2.0 | 문학적 매력 전담 장치 추가 (사용자 결정) | emotional_engagement · memorability 를 "추후 추가" → 활성 지표 #6·#7 승격 (advisory/MINOR 한정). determine_verdict 에 글맛 강등 분기 추가 (명료성 게이트 불변). prose-critic agent 신설 연동 |
