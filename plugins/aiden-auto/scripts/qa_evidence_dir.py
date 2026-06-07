#!/usr/bin/env python3
"""QA 증거 폴더 이름 생성기 — 정본 명명 규칙 {YYYYMMDD_HHMM_Description}.

사용자 결정 (2026-06-08): QA 처리 폴더는 항상
    {YYYYMMDD_HHMM_Description}
형식으로 저장한다 (예: 20260608_1430_card-deck-images).

이전엔 cycle*/goal-*/qa-YYYYMMDD-HHMMSS 등 제각각이라 혼란 → 본 헬퍼가
타임스탬프(로컬 시각, 사람이 QA 돌린 시점 직관) + 설명(kebab 정규화)을
결합해 단일 형식을 강제한다. /auto QA 워크플로우(chapter-qa.md)가 호출.

Universal Deployment: hardcoded path 0, 표준 라이브러리만, 3 OS 동일 작동.

사용:
    python qa_evidence_dir.py "card deck images"
        → 20260608_1430_card-deck-images
    python qa_evidence_dir.py "RC2 색 정합" --parent integration-tests/evidence
        → integration-tests/evidence/20260608_1430_rc2-색-정합   (경로까지 출력)
    python qa_evidence_dir.py "x" --utc        # UTC 시각 사용 (기본 로컬)

stdout = 폴더 이름(또는 --parent 지정 시 전체 경로) 한 줄. 부작용 없음(생성 X).
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone


def slugify(text: str, max_words: int = 6) -> str:
    """설명 → kebab-case 슬러그. 공백/특수문자 정리, 한글은 보존."""
    t = text.strip().lower()
    # 경로 구분자·따옴표 제거
    t = t.replace("/", " ").replace("\\", " ").replace('"', "").replace("'", "")
    # 영숫자/한글/공백/하이픈만 남김
    t = re.sub(r"[^0-9a-z가-힣\s-]", "", t)
    # 공백 묶음 → 단일 하이픈
    words = [w for w in re.split(r"[\s_-]+", t) if w]
    if not words:
        words = ["qa"]
    slug = "-".join(words[:max_words])
    return slug[:48].strip("-") or "qa"


def build_name(description: str, use_utc: bool = False) -> str:
    now = datetime.now(timezone.utc) if use_utc else datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M")
    return f"{stamp}_{slugify(description)}"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="QA 증거 폴더 이름 생성 ({YYYYMMDD_HHMM_Description})")
    ap.add_argument("description", help="QA 회차 설명 (예: 'card deck images')")
    ap.add_argument("--parent", default="", help="앞에 붙일 부모 경로 (지정 시 전체 경로 출력)")
    ap.add_argument("--utc", action="store_true", help="로컬 대신 UTC 시각 사용")
    args = ap.parse_args(argv)

    name = build_name(args.description, use_utc=args.utc)
    if args.parent:
        parent = args.parent.rstrip("/\\")
        sys.stdout.write(f"{parent}/{name}\n")
    else:
        sys.stdout.write(name + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
