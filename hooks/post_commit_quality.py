#!/usr/bin/env python3
"""
post-commit Hook - 커밋 메시지 품질 점수 측정

커밋 후 자동으로 실행되어 Conventional Commit 형식 준수도를 평가합니다.
품질 점수가 낮으면 /commit --rewrite 1 개선 제안을 출력합니다.
"""

import subprocess
import re
import sys
import json
from pathlib import Path

# Windows cp949 인코딩 에러 방지
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')


CONVENTIONAL_COMMIT_PATTERN = re.compile(
    r'^(feat|fix|docs|style|refactor|perf|test|chore|ci|build|revert)'
    r'(\([a-zA-Z0-9_/-]+\))?(!)?:\s+.+',
    re.MULTILINE
)

EMOJI_PATTERN = re.compile(
    r'[\U0001F300-\U0001F9FF]|[\u2600-\u26FF]|[\u2700-\u27BF]'
)


def get_last_commit_message() -> str:
    """마지막 커밋 메시지 가져오기"""
    try:
        result = subprocess.run(
            ['git', 'log', '-1', '--pretty=%B'],
            capture_output=True,
            text=True,
            encoding='utf-8',
        )
        return result.stdout.strip()
    except Exception:
        return ''


def score_commit_message(message: str) -> tuple[int, list[str]]:
    """커밋 메시지 품질 점수 계산 (0-100)"""
    score = 0
    details = []

    if not message:
        return 0, ['빈 커밋 메시지']

    lines = message.split('\n')
    subject = lines[0].strip()
    body = '\n'.join(lines[2:]).strip() if len(lines) > 2 else ''

    # Conventional Commit 형식: +40점
    if CONVENTIONAL_COMMIT_PATTERN.match(subject):
        score += 40
        details.append('✅ Conventional Commit 형식 (+40)')
    else:
        details.append('❌ Conventional Commit 형식 미준수 (+0)')

    # 이모지 포함: +10점
    if EMOJI_PATTERN.search(subject):
        score += 10
        details.append('✅ 이모지 포함 (+10)')
    else:
        details.append('⚠️ 이모지 없음 (+0)')

    # Subject 명확성 (10자+ 의미있는 내용): +20점
    # 한글 또는 영문 2단어 이상
    meaningful = bool(re.search(r'[가-힣]{4,}|[A-Za-z]{3,}\s+[A-Za-z]{3,}', subject))
    if meaningful:
        score += 20
        details.append('✅ 명확한 subject (+20)')
    else:
        details.append('⚠️ subject가 너무 짧거나 모호 (+0)')

    # Body 설명 포함: +20점
    if body and len(body) > 10:
        score += 20
        details.append('✅ Body 설명 포함 (+20)')
    else:
        details.append('⚠️ Body 설명 없음 (+0)')

    # Subject 길이: +10점 (≤50자) or +5점 (51-72자)
    subject_len = len(subject)
    if subject_len <= 50:
        score += 10
        details.append(f'✅ Subject 길이 최적 {subject_len}자 (+10)')
    elif subject_len <= 72:
        score += 5
        details.append(f'⚠️ Subject 길이 보통 {subject_len}자 (+5)')
    else:
        details.append(f'❌ Subject 너무 김 {subject_len}자 (+0)')

    return min(score, 100), details


def main():
    message = get_last_commit_message()
    if not message:
        sys.exit(0)

    # 자동 생성 커밋 (merge, revert 등) 스킵
    if message.startswith(('Merge ', 'Revert ', 'Initial commit')):
        sys.exit(0)

    score, details = score_commit_message(message)

    if score < 60:
        print(f'\n⚠️ 커밋 품질 낮음 ({score}/100)')
        print('   개선하려면: /commit --rewrite 1')
    elif score < 80:
        print(f'\n📊 커밋 품질 보통 ({score}/100)')

    # 로그 저장 (선택적)
    log_dir = Path('C:/claude/.claude/logs')
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'commit_quality.jsonl'
    try:
        entry = json.dumps({
            'score': score,
            'subject': message.split('\n')[0][:80],
            'ts': __import__('datetime').datetime.now().isoformat(),
        }, ensure_ascii=False)
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(entry + '\n')
    except Exception:
        pass


if __name__ == '__main__':
    main()
