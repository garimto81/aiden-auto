# 왜 내 hook 수정이 동료 PC에 안 보이나 — 근본 원인 분석

## 한 줄 답

내가 고친 곳(`~/.claude/hooks/`)은 **내 PC 안에서만 쓰는 "원본 서랍"**이고,
동료 PC는 **GitHub 라는 "공용 창고"를 통해서만** 파일을 받습니다.
원본 서랍 → 공용 창고로 옮기는 자동 배달(여러 단계 체인)이 **중간에 끊겨서**,
공용 창고에 내 수정이 도착하지 못했고, 그래서 동료 PC가 못 봅니다.

---

## 그림으로 보는 전체 흐름

```
   [내 PC]                                          [동료 PC]
   ~/.claude/hooks/  (내가 고친 곳 = 정본/원본)
        │
        │ ① SessionEnd 자동 hook
        │    (framework_github_sync.py)
        ▼
   C:\aiden-auto-repo  (배포용 git 폴더)
        │
        │ ② git commit + push
        ▼
   GitHub (garimto81/aiden-auto)  ← 공용 창고
        │
        │ ③ 동료가 plugin update (git pull)
        ▼
   동료의 plugin cache
        │
        │ ④ bootstrap.py 가 cache → ~/.claude 복사
        ▼
   동료의 ~/.claude/hooks/  ← 여기 도착해야 비로소 "보임"
```

핵심: 내 편집은 ①번 출발점에만 있습니다.
②③④ 중 **하나라도 안 되면** 동료 PC까지 도착 못 합니다.

---

## 어디서 끊겼나 (실제 로그 증거)

배달 로그(`~/.claude/state/framework-github-sync.log`)를 보면 두 종류의 실패가 보입니다.

### 증거 A — 과거: commit 자체가 실패 (배달 시작도 못 함)

```
[13:10:32] commit failed: ... timed out after 30 seconds
[16:13:02] commit failed:
[09:22:16] commit failed:
```

`commit failed` = "원본 서랍 → 공용 창고로 보낼 짐을 포장(commit)하는 단계에서 실패".
30초 타임아웃과 빈 에러가 반복됩니다. 즉 **GitHub로 올라가지 못한 채** 변경이 쌓였습니다.

### 증거 B — 최근: "no changes — skip" (배달할 게 없다고 판단)

```
[02:27:25] v6 mirror: 0 files synced global → aiden-auto-repo
[02:27:25] aiden-auto-repo: no changes — skip
```

지금은 hook이 돌긴 하는데 **"바뀐 게 없으니 안 보낸다"**고 끝납니다.
배포용 git 폴더(`C:\aiden-auto-repo`)에 내 최신 hook 수정이 반영 안 돼 있거나,
이미 한 번 올라간 뒤라 더 보낼 게 없는 상태입니다.

---

## 끊기는 4가지 흔한 지점 (가능성 높은 순)

| # | 끊기는 지점 | 일상 비유 | 증상 |
|---|-----------|----------|------|
| 1 | **②commit/push 실패** (위 증거 A) | 택배 접수 실패 | GitHub에 안 올라감 → 동료가 받을 원본이 없음 |
| 2 | **내 PC가 "배포 PC"로 분류됨** | 우체국 직원이 "넌 받는 쪽"이라 판단 | hook이 아예 push를 안 함 (`is_dev_pc()`가 False) |
| 3 | **③동료가 plugin update를 안 함** | 공용 창고에 도착했는데 동료가 안 가지러 감 | 동료 PC가 옛 버전 그대로 |
| 4 | **④bootstrap의 idempotent 보호** | 이미 같은 칸에 책이 있어 새 책을 안 꽂음 | 동료 cache엔 새 파일 있는데 `~/.claude`엔 옛 파일 그대로 |

---

## 왜 이런 구조인가 (설계 의도)

이 framework는 "정본은 `~/.claude/` **한 곳뿐**, 나머지는 자동 복사본"이라는 규칙(rule 19)을 따릅니다.
- 좋은 점: 어디서 고칠지 헷갈리지 않음 (항상 `~/.claude`에서만 편집)
- 함정: 그 한 곳의 편집이 동료까지 가려면 **자동 배달 체인이 끝까지 성공**해야 함.
  체인이 길수록(4단계) 중간 실패 지점도 많음 → 지금 겪는 문제.

특히 4번(bootstrap)은 **일부러** "기존 파일은 덮어쓰지 않음(idempotent)"으로 설계돼 있습니다
(`bootstrap.py` 154행: `if dp.exists(): continue`). 신규 설치엔 안전하지만,
**"이미 설치된 동료 PC에 업데이트를 밀어넣는" 용도로는 작동 안 합니다.** 이게 4번 함정의 정체입니다.

---

## 확인 순서 (이대로 점검하면 어디서 끊겼는지 특정 가능)

```
1단계: GitHub에 내 수정이 올라가 있나?
   → github.com/garimto81/aiden-auto 에서 해당 hook 파일 최신 내용 확인
   → 없으면 = 내 PC의 ②번(commit/push) 실패가 원인 (가장 가능성 높음)

2단계: 내 PC가 push를 시도는 했나?
   → ~/.claude/state/framework-github-sync.log 에서 "PUSHED" 가 보이나?
   → "no changes" / "commit failed" 만 있으면 = 배달 안 됨
   → "배포 PC (소비만)" 로그가 있으면 = 내 PC가 dev로 인식 안 됨 (2번 함정)

3단계: GitHub엔 있는데 동료가 못 봄?
   → 동료가 plugin marketplace update (git pull) 를 했는지 확인 (3번 함정)
   → 했는데도 안 보이면 동료 cache는 새 파일인데 ~/.claude는 옛 파일
     = bootstrap idempotent 보호 (4번 함정) → 동료 PC에서 해당 파일 수동 갱신 필요
```

---

## 결론

- **내 hook 수정은 "내 PC 원본"에만 있고, 동료에게 갈 GitHub 공용 창고까지 도달하지 못했다.**
- 로그상 직접 증거: 과거 `commit failed` 반복 + 현재 `no changes — skip`.
- 가장 유력한 끊김 지점은 **②번(GitHub commit/push 실패)** 또는 **내 PC의 dev/배포 역할 분류**.
- 위 "확인 순서 1~3단계"로 정확한 끊김 지점을 5분 안에 특정할 수 있다.

> 비유로 한 줄: 편지를 책상 서랍(내 PC)에는 썼는데, 우체통(GitHub)에 넣는 단계에서 막혀
> 동료 우편함(동료 PC)까지 배달이 안 된 상황입니다.
