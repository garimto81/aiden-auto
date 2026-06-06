# TL;DR — 한 줄 결론

내 PC의 hook 변경은 GitHub(전사 공용 보관소)까지는 자동으로 올라가지만, 동료 PC가 그걸 직접 받아오는(pull) 단계가 자동이 아니라서 — 동료가 "업데이트 받기"를 한 번 눌러주기 전까지는 안 보이는 게 정상입니다.

## 무슨 일이 있었나

내 PC에서 `~/.claude/hooks` 아래 hook 파일(자동 동작을 켜고 끄는 작은 프로그램)을 고쳤습니다. 그런데 회사 동료 PC에서 같은 framework를 쓰는데도 그 변경이 보이지 않습니다.

## 진짜 원인

```
   내 PC                    GitHub                동료 PC
  (원고 작성)          (출판사 공용 서가)        (서점 진열대)
  ~/.claude/hooks   →   aiden-auto-repo    →    plugin 받기
        │   (자동)          │   (수동!)
        └─ 글 고침 →        └─ 동료가 직접 가지러 와야 함
```

내 PC는 세션 종료 시 자동 배달(`framework_github_sync.py`)로 GitHub까지 올립니다(자동). 하지만 동료 PC에는 "새 버전 자동 당겨오기"가 없어, 동료가 `claude plugin marketplace update`를 직접 눌러야 내려옵니다. 또 배달 직원은 정본(dev) PC에서만 동작 — 동료(소비) PC에서 고친 건 아무 데도 안 올라갑니다(의도된 설계).

## 어떻게 알아냈나 (근거)

| 확인한 것 | 발견 |
|----------|------|
| `framework_github_sync.py` | `~/.claude/hooks` → `aiden-auto-repo` → GitHub push 자동 |
| `if not is_dev_pc(): return` | 소비 PC에서는 배달 자체 안 돎 (의도) |
| rule 19 배포 경로 | "aiden-auto-repo → GitHub → (CC pull) → 동료" — pull은 수동 |

## 수정 제안 (아직 적용 안 함)

1. (권장) 동료가 `claude plugin marketplace update` 1회 실행 — 정상 경로, 가장 간단.
2. (반복 귀찮으면) 동료 PC 시작 시 자동 pull 장치 추가 — framework 구조 변경이라 정책 결정 필요.

> 적용하려면 알려주세요. 지금은 제안만 한 상태입니다.

## 아직 모르는 점

- 동료가 이미 update를 눌렀는데도 안 보이면 → plugin cache 옛 버전 고착/plugin 비활성 등 한 칸 더 안쪽 가능성.
- 내 마지막 변경이 세션 종료까지 GitHub에 실제 올라갔는지(최신 commit 확인 필요).

---
> 한 줄 요약: 내 변경은 GitHub까지 자동으로 올라가지만, 동료가 받아오는 "업데이트 받기"는 수동이라 — 동료가 한 번 눌러주면 보입니다.
