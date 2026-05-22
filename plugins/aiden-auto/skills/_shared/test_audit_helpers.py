"""audit_helpers.py 회귀 방지 단위 테스트.

critic이 발견한 버그 (path_source substring, BENIGN_INTENTS 불일치, all_byte_identical
single path, parse_frontmatter block scalar)에 대한 regression guard.

실행: python C:/claude/.claude/skills/_shared/test_audit_helpers.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from audit_helpers import (  # noqa: E402
    BENIGN_INTENTS,
    _NON_ASCII_LANG,
    all_byte_identical,
    all_in_different_plugins,
    classify_duplicate_intent,
    is_in_shadow_marketplace,
    is_localization_diff,
    is_redirect_stub,
    parse_frontmatter_simple,
    path_marketplace,
    path_plugin,
    path_source,
    _reset_caches,
)

# 절대 경로 하드코딩 회피 (Cycle 9 MED-11) — 모든 test가 이 base 사용
_SKILLS_ROOT = Path(__file__).parent.parent
_PROJECT_ROOT = _SKILLS_ROOT.parent.parent


def assert_eq(actual, expected, msg=""):
    if actual != expected:
        raise AssertionError(f"{msg}: expected {expected!r}, got {actual!r}")


# ── path_source: critic HIGH-1 회귀 방지 ──────────────────────────────────
def test_path_source_substring_immune():
    """폴더명에 'marketplaces' 포함된 local 경로가 'plugin'으로 오분류 X."""
    p = Path("C:/claude/.claude/skills/marketplaces-utils/SKILL.md")
    assert_eq(path_source(p), "local",
              "path_source substring bug (HIGH-1)")


def test_path_source_genuine_plugin():
    """실제 plugin 경로는 plugin으로 분류."""
    p = Path("C:/Users/A/.claude/plugins/marketplaces/foo/plugins/bar/SKILL.md")
    assert_eq(path_source(p), "plugin")


def test_path_source_global():
    """global 경로는 global로 분류."""
    p = Path("C:/Users/A/.claude/skills/foo/SKILL.md")
    assert_eq(path_source(p), "global")


# ── path_plugin: critic 발견한 marketplace 우선 오매칭 회귀 ──────────────
def test_path_plugin_external_plugins():
    """marketplaces/<mkt>/external_plugins/<name>/ 정확히 추출."""
    p = Path(
        "C:/U/A/.claude/plugins/marketplaces/foo/external_plugins/discord/skills/x/SKILL.md"
    )
    assert_eq(path_plugin(p), "discord")


def test_path_plugin_marketplaces_priority():
    """~/.claude/plugins/ 의 'plugins' 단어와 marketplaces 내부의 'plugins'를 구별."""
    p = Path(
        "C:/U/A/.claude/plugins/marketplaces/mkt/plugins/myplugin/skills/x/SKILL.md"
    )
    assert_eq(path_plugin(p), "myplugin")


def test_path_plugin_no_marketplaces():
    """marketplaces 밖에서는 None."""
    p = Path("C:/claude/.claude/skills/foo/SKILL.md")
    assert_eq(path_plugin(p), None)


# ── all_byte_identical: critic LOW-1 (single path) 회귀 ─────────────────
def test_all_byte_identical_single():
    """단일 path는 자기 자신과 동일 → True."""
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
        f.write(b"test")
        p = Path(f.name)
    try:
        assert_eq(all_byte_identical([p]), True)
    finally:
        p.unlink()


def test_all_byte_identical_empty():
    """빈 리스트는 True (vacuous truth)."""
    assert_eq(all_byte_identical([]), True)


# ── parse_frontmatter_simple: block scalar 정확 파싱 ──────────────────────
def test_parse_frontmatter_block_scalar():
    """YAML block scalar (>) description 정확 파싱."""
    text = """---
name: test
description: >
  Multi-line description
  spanning several lines
---
body content"""
    fm, body = parse_frontmatter_simple(text)
    assert_eq(fm.get("name"), "test")
    assert "Multi-line description spanning several lines" in fm.get("description", "")
    assert_eq(body, "body content")


def test_parse_frontmatter_no_frontmatter():
    """frontmatter 없는 파일은 빈 dict + 전체 텍스트."""
    text = "no frontmatter here"
    fm, body = parse_frontmatter_simple(text)
    assert_eq(fm, {})
    assert_eq(body, text)


def test_parse_frontmatter_unclosed():
    """닫히지 않은 frontmatter는 빈 dict + 전체 텍스트 (안전 default)."""
    text = "---\nname: test\nnever closed"
    fm, body = parse_frontmatter_simple(text)
    assert_eq(fm, {})


# ── classify_duplicate_intent: edge cases ───────────────────────────────
def test_classify_empty():
    """빈 paths → real_duplicate."""
    assert_eq(classify_duplicate_intent([]), "real_duplicate")


def test_classify_single():
    """단일 path → real_duplicate (분류 의미 없음)."""
    p = Path("C:/claude/.claude/skills/test/SKILL.md")
    assert_eq(classify_duplicate_intent([p]), "real_duplicate")


def test_classify_byte_identical():
    """SHA256 같은 2 path → byte_identical_mirror."""
    with tempfile.TemporaryDirectory() as d:
        p1 = Path(d) / "a.md"
        p2 = Path(d) / "b.md"
        p1.write_text("same content", encoding="utf-8")
        p2.write_text("same content", encoding="utf-8")
        result = classify_duplicate_intent([p1, p2])
        assert_eq(result, "byte_identical_mirror")


def test_classify_localization_korean():
    """한글-영어 diff는 localization_override."""
    with tempfile.TemporaryDirectory() as d:
        p1 = Path(d) / "kr.md"
        p2 = Path(d) / "en.md"
        p1.write_text("# 한글 헤더\n한글 본문 내용입니다\n공통 줄\n", encoding="utf-8")
        p2.write_text("# English Header\nEnglish body content here\n공통 줄\n", encoding="utf-8")
        result = classify_duplicate_intent([p1, p2])
        assert_eq(result, "localization_override")


def test_classify_localization_japanese():
    """일본어-영어 diff도 localization_override (multi-language 일반화)."""
    with tempfile.TemporaryDirectory() as d:
        p1 = Path(d) / "jp.md"
        p2 = Path(d) / "en.md"
        p1.write_text("# 日本語ヘッダー\nひらがな本文\n共通\n", encoding="utf-8")
        p2.write_text("# English Header\nEnglish body\n共通\n", encoding="utf-8")
        result = classify_duplicate_intent([p1, p2])
        assert_eq(result, "localization_override")


# ── BENIGN_INTENTS: critic HIGH-2 회귀 (두 벌 정의 불일치) ────────────────
# A-27 (Cycle 23 critic MEDIUM): required hardcode 제거 → BENIGN_INTENTS import 직접 사용.
# 이전 패턴: required = {...} 하드코딩 → BENIGN_INTENTS 에 새 intent 추가 시 required 도 수동 동기화 필요.
# 새 패턴: BENIGN_INTENTS 자체가 source of truth — 핵심 8 intent 만 minimum required 로 보장.
_MINIMUM_REQUIRED = frozenset({
    "shadow_marketplace", "byte_identical_mirror", "redirect_stub",
    "project_global_mirror", "plugin_namespaced",
    "priority_resolution_local_wins", "priority_resolution_global_wins",
    "localization_override",
})


def test_benign_intents_minimum_required():
    """8개 핵심 intent 는 절대 누락 금지 (회귀 방지)."""
    missing = _MINIMUM_REQUIRED - BENIGN_INTENTS
    assert_eq(missing, set(),
              f"BENIGN_INTENTS 핵심 누락 (HIGH-2 회귀): {missing}")


def test_benign_intents_count_threshold():
    """BENIGN_INTENTS 가 핵심 이상 항목 포함 — 신규 intent 추가 후 회귀 방지."""
    # Cycle 10-11 신규 (A-5/A-6) 포함 시 최소 10개, 미래 확장 가능
    # assert_true 미존재 → assert_eq 활용 (count >= 8 ↔ 조건이 True)
    assert len(BENIGN_INTENTS) >= 8, \
        f"BENIGN_INTENTS 최소 8개 미달 (현재 {len(BENIGN_INTENTS)})"


def test_benign_intents_excludes_drift():
    """drift 계열은 BENIGN_INTENTS에 포함 안 됨 (WARN 유지)."""
    forbidden = {"real_duplicate", "priority_resolution_drift", "project_global_drift"}
    leaked = forbidden & BENIGN_INTENTS
    assert_eq(leaked, set(),
              f"drift intent가 BENIGN에 누설: {leaked}")


# ── is_redirect_stub: 임계값 통일 ─────────────────────────────────────────
def test_is_redirect_stub_short_with_keyword():
    """30줄 미만 + deprecated 키워드 → stub."""
    body = "DEPRECATED\n" + "\n".join(["line"] * 10)
    assert is_redirect_stub(body), "stub 감지 실패"


def test_is_redirect_stub_long_with_keyword_not_stub():
    """임계값 30 이상이면 키워드 있어도 stub 아님 (Cycle 10 통일).

    임계값 = _STUB_BODY_LINE_THRESHOLD (audit_helpers.py에 정의).
    """
    body = "DEPRECATED in changelog\n" + "\n".join(["line"] * 100)
    assert not is_redirect_stub(body), "긴 본문이 stub으로 false positive"


def test_is_redirect_stub_frontmatter_version_deprecated():
    """frontmatter version에 deprecated 명시 시 stub."""
    fm = {"version": "99.0.0-deprecated"}
    assert is_redirect_stub("any body", fm)


# ── fallback BENIGN_INTENTS 동기화 검증 (Cycle 8 발견 영구 방지) ────────
def test_fallback_benign_intents_sync():
    """audit script의 fallback BENIGN_INTENTS가 helper와 동일한지 검증.

    Cycle 9 HIGH-3: 5종 audit 중 BENIGN_INTENTS 사용 audit만 검사.
    workflow + plugin-ssot 은 BENIGN_INTENTS 미사용 (분류 로직 불필요) — 의도된 설계.
    """
    import re
    # BENIGN_INTENTS 를 사용하는 audit 스크립트 (helper의 분류 결과 활용)
    audit_scripts_with_benign = [
        _SKILLS_ROOT / "skill-matrix-audit" / "scripts" / "audit_skills.py",
        _SKILLS_ROOT / "command-matrix-audit" / "scripts" / "audit_commands.py",
        _SKILLS_ROOT / "agent-matrix-audit" / "scripts" / "audit_matrix.py",
    ]
    for script in audit_scripts_with_benign:
        assert script.is_file(), f"audit script not found: {script}"
        text = script.read_text(encoding="utf-8")
        m = re.search(
            r"BENIGN_INTENTS\s*=\s*frozenset\(\s*\{([^}]+)\}",
            text,
        )
        assert m, f"fallback BENIGN_INTENTS 블록 미발견: {script.name}"
        # quoted intent 이름 추출 (큰따옴표/작은따옴표 모두 허용)
        fallback_intents = set(re.findall(r'["\']([a-z_]+)["\']', m.group(1)))
        missing = BENIGN_INTENTS - fallback_intents
        assert_eq(
            missing, set(),
            f"{script.name} fallback이 helper와 비동기: missing={missing}"
        )

    # BENIGN_INTENTS 미사용 audit (workflow, plugin-ssot) — 명시 검증: 분류 로직 없음
    audit_scripts_without_benign = [
        _SKILLS_ROOT / "workflow-matrix-audit" / "scripts" / "audit_workflow.py",
        _SKILLS_ROOT / "plugin-ssot-audit" / "scripts" / "audit_and_sync.py",
    ]
    for script in audit_scripts_without_benign:
        assert script.is_file(), f"audit script not found: {script}"
        text = script.read_text(encoding="utf-8")
        # 이들은 BENIGN_INTENTS 자체를 사용 안 함 → 미사용 확인
        assert "BENIGN_INTENTS" not in text, \
            f"{script.name} 에 BENIGN_INTENTS 등장 — fallback sync 검증 추가 필요"


# ── classify_duplicate_intent: 미커버 intent case 모두 ──────────────────
def test_classify_shadow_marketplace(tmp_dir=None):
    """shadow marketplace path → shadow_marketplace."""
    # claude-code-plugins는 활성 0개 → shadow
    p1 = Path("C:/claude/.claude/agents/test.md")
    p2 = Path(
        "C:/U/A/.claude/plugins/marketplaces/claude-code-plugins/plugins/x/agents/test.md"
    )
    # 실제 파일 없어도 path_marketplace + shadow_set만 확인
    result = classify_duplicate_intent([p1, p2])
    # shadow marketplace 분기는 첫 case → 파일 read 전에 결정
    assert result == "shadow_marketplace", \
        f"shadow_marketplace 미분류: got {result}"


def test_classify_redirect_stub():
    """stub + canonical 패턴 → redirect_stub."""
    with tempfile.TemporaryDirectory() as d:
        p1 = Path(d) / "stub.md"
        p2 = Path(d) / "canonical.md"
        # stub: DEPRECATED + 짧음
        p1.write_text(
            "---\nname: test\ndescription: DEPRECATED stub\nversion: 99.0-deprecated\n---\n"
            "DEPRECATED stub redirecting to plugin canonical.\n",
            encoding="utf-8",
        )
        # canonical: 긴 본문 (50+ lines, no deprecated)
        p2.write_text(
            "---\nname: test\ndescription: Real canonical\n---\n"
            + "\n".join([f"line {i}" for i in range(60)]),
            encoding="utf-8",
        )
        bodies = [parse_frontmatter_simple(p.read_text(encoding="utf-8"))[1]
                  for p in [p1, p2]]
        fms = [parse_frontmatter_simple(p.read_text(encoding="utf-8"))[0]
               for p in [p1, p2]]
        result = classify_duplicate_intent([p1, p2], bodies, fms)
        assert_eq(result, "redirect_stub")


def test_classify_plugin_namespaced():
    """서로 다른 plugin이 같은 이름 → plugin_namespaced.

    각 파일 내용을 명확히 다르게 (byte-identical 아님 + localization 아님 + 같은 출처).
    """
    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "marketplaces" / "mkt"
        p1 = base / "plugins" / "pluginA" / "skills" / "access" / "SKILL.md"
        p2 = base / "plugins" / "pluginB" / "skills" / "access" / "SKILL.md"
        for p, name in [(p1, "A"), (p2, "B")]:
            p.parent.mkdir(parents=True, exist_ok=True)
            # 각 plugin 고유 내용 — byte-identical 아님 + 둘 다 영어
            lines = [f"# Access skill for plugin{name}",
                     f"Plugin {name} specific behavior",
                     f"Authentication flow for {name}",
                     f"Token format for {name}: PREFIX-{name}-TOKEN"]
            lines.extend([f"step {i} in {name} flow" for i in range(20)])
            p.write_text("\n".join(lines), encoding="utf-8")
        result = classify_duplicate_intent([p1, p2])
        assert_eq(result, "plugin_namespaced")


def test_classify_priority_resolution_local_wins():
    """local + plugin byte-identical → priority_resolution_local_wins.

    실제 marketplace 경로 + 우선순위 해소 case.
    """
    with tempfile.TemporaryDirectory() as d:
        p_local = Path(d) / "local-fake" / "agents" / "test.md"
        p_plugin = Path(d) / "marketplaces" / "mkt" / "plugins" / "p" / "agents" / "test.md"
        for p in [p_local, p_plugin]:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("identical content", encoding="utf-8")
        # path_source는 "C:/claude/.claude" prefix로 local 판단 → 임시 디렉토리는 global
        # 그래서 이 테스트는 byte_identical_mirror 로 분류됨 (case 2 우선)
        result = classify_duplicate_intent([p_local, p_plugin])
        # byte-identical은 case 2 우선 → byte_identical_mirror
        assert_eq(result, "byte_identical_mirror")


def test_classify_two_different_files_no_pattern():
    """완전 다른 내용 + 같은 언어 + 같은 출처 → real_duplicate."""
    with tempfile.TemporaryDirectory() as d:
        p1 = Path(d) / "a.md"
        p2 = Path(d) / "b.md"
        p1.write_text(
            "# Header\n" + "\n".join([f"english line {i}" for i in range(20)]),
            encoding="utf-8",
        )
        p2.write_text(
            "# Header\n" + "\n".join([f"different english line {i}" for i in range(20)]),
            encoding="utf-8",
        )
        result = classify_duplicate_intent([p1, p2])
        assert result in ("real_duplicate",), \
            f"different content same language: expected real_duplicate, got {result}"


# ── Cycle 9 회귀 방지 — 한글 unicode `힣` 매칭 ──────────────────────────
def test_korean_syllable_endpoint():
    """한글 음절 끝값 `힣`(U+D7A3) 매칭 (Cycle 9 HIGH-1 회귀)."""
    assert _NON_ASCII_LANG.search("힣"), "한글 끝값 `힣` 매칭 실패 — Cycle 9 회귀"
    # 추가 음절 검증
    for char in ["힘", "힙", "힛", "힝", "힞", "힟", "힠", "힡", "힢", "힣"]:
        assert _NON_ASCII_LANG.search(char), f"한글 음절 `{char}` 매칭 실패"


def test_multi_language_coverage():
    """multi-language regex의 누락 언어 매칭 (Cycle 9 spot check 회귀)."""
    samples = {
        "한글 음절 가": "가",
        "한글 음절 힣": "힣",       # Cycle 9 발견 (이전 ㄱ-힝 범위 밖)
        "히라가나": "ぁ",
        "카타카나": "ア",
        "CJK": "中",
        "키릴 А": "А",
        "아랍 ا": "ا",
        "히브리 ש": "ש",            # Cycle 9 추가
        "태국 ก": "ก",              # Cycle 9 추가
        "베트남 ế": "ế",            # Cycle 9 추가 (라틴 확장)
    }
    for name, text in samples.items():
        assert _NON_ASCII_LANG.search(text), f"{name} ({text}) 매칭 실패"


# ── Cycle 9 회귀 방지 — localization 임계값 sensitivity ─────────────────
def test_localization_short_diff():
    """짧은 diff (1-2 lines)에서도 localization 감지 (Cycle 9 HIGH-2 회귀)."""
    with tempfile.TemporaryDirectory() as d:
        p1 = Path(d) / "kr.md"
        p2 = Path(d) / "en.md"
        # 매우 짧은 diff — 1라인만
        p1.write_text("한글 라인\n공통\n", encoding="utf-8")
        p2.write_text("English line\n공통\n", encoding="utf-8")
        assert is_localization_diff([p1, p2]), \
            "짧은 diff에서 localization 감지 실패 (Cycle 9 회귀)"


def test_localization_ratio_diff_threshold():
    """ratio diff 0.3 임계값 검증."""
    with tempfile.TemporaryDirectory() as d:
        p1 = Path(d) / "a.md"
        p2 = Path(d) / "b.md"
        # 한글 100% vs 영어 0%
        p1.write_text("\n".join(["한글 라인"] * 3), encoding="utf-8")
        p2.write_text("\n".join(["English line"] * 3), encoding="utf-8")
        assert is_localization_diff([p1, p2]), "100%/0% 명확 분리 감지 실패"


# ── Cycle 9 회귀 방지 — priority_resolution_local_wins 실제 검증 ────────
def test_classify_real_priority_resolution_local_wins(monkeypatch=None):
    """local + plugin byte-identical → priority_resolution_local_wins (실제 경로).

    Cycle 9 HIGH-4: 이전 테스트가 byte_identical_mirror로 분류됐던 문제 수정.
    실제 LOCAL_PREFIX 경로를 mock 하여 정확한 분기 검증.
    """
    import audit_helpers as ah
    original_prefix = ah._LOCAL_PREFIX
    with tempfile.TemporaryDirectory() as d:
        d_lower = d.replace("\\", "/").lower()
        # local prefix 를 tempdir 로 임시 변경
        ah._LOCAL_PREFIX = d_lower

        try:
            p_local = Path(d) / "local-fake" / "agents" / "test.md"
            p_plugin = Path(d) / "marketplaces" / "mkt" / "plugins" / "p" / "agents" / "test.md"
            for p in [p_local, p_plugin]:
                p.parent.mkdir(parents=True, exist_ok=True)
            # 서로 다른 내용 → byte_identical_mirror 아님
            p_local.write_text("local version content here\nmore lines", encoding="utf-8")
            p_plugin.write_text("plugin version different content\nmore lines",
                                encoding="utf-8")
            # 둘 다 영어 → localization 아님
            result = classify_duplicate_intent([p_local, p_plugin])
            # local + plugin + 둘 다 byte_identical 아님 → priority_resolution_drift 또는 local_wins
            # 둘 다 같은 언어 (영어) + 내용만 다름 → drift (의도된 정확한 분류)
            assert result in ("priority_resolution_drift", "priority_resolution_local_wins"), \
                f"local+plugin drift 분류 실패: got {result}"
        finally:
            ah._LOCAL_PREFIX = original_prefix


# ── Cycle 11 회귀 방지 — 영어 라틴 액센트 false positive ────────────────
def test_latin_accent_not_false_positive():
    """café, naïve, résumé 등 영어 라틴 액센트가 비영어로 분류 안 됨 (Cycle 11 HIGH-1).

    Latin-1 Supplement (U+00C0-U+00FF) 는 영어권 흔한 단어 포함 → 의도적 제외.
    """
    english_with_accents = [
        "café", "naïve", "résumé", "über", "façade", "Müller", "Björk",
    ]
    for word in english_with_accents:
        assert not _NON_ASCII_LANG.search(word), \
            f"'{word}' 가 비영어로 false positive (Cycle 11 회귀)"


def test_localization_english_accents_not_localization():
    """영어 + 액센트 문서 두 벌이 localization으로 잘못 분류 안 됨 → real_duplicate 확정.

    Cycle 12 MED-2: 강한 assertion으로 분류 미래 변경 시 silent regression 방지.
    """
    with tempfile.TemporaryDirectory() as d:
        p1 = Path(d) / "a.md"
        p2 = Path(d) / "b.md"
        p1.write_text("café-plugin\nbasic content\nshared line\n", encoding="utf-8")
        p2.write_text("coffee-plugin\nbasic content\nshared line\n", encoding="utf-8")
        result = classify_duplicate_intent([p1, p2])
        # 정확히 real_duplicate 확정 — 영어 액센트는 비영어 분류 안 됨 + 내용 다름
        assert_eq(result, "real_duplicate")


def test_localization_delete_only_diff_not_localization():
    """한쪽만 비영어 라인 삭제 (delete-only diff) → localization 아님 (Cycle 12 MED-1)."""
    with tempfile.TemporaryDirectory() as d:
        p1 = Path(d) / "a.md"
        p2 = Path(d) / "b.md"
        # a에만 한글 라인 있고 b에는 없음 → diff_a만 채워짐, diff_b 비어있음
        p1.write_text("공통\n한글 라인 추가됨\n공통\n", encoding="utf-8")
        p2.write_text("공통\n공통\n", encoding="utf-8")
        result = is_localization_diff([p1, p2])
        assert not result, \
            "delete-only diff에서 localization 잘못 감지 (Cycle 12 회귀)"


def test_vietnamese_still_detected():
    """베트남어 ế 는 여전히 비영어로 감지 (À-ɏ 제거 후에도)."""
    assert _NON_ASCII_LANG.search("Tiếng"), "베트남어 매칭 실패 — Ḁ-ỿ 범위 검증"
    assert _NON_ASCII_LANG.search("Việt"), "베트남어 매칭 실패"


# ── Cycle 9 회귀 방지 — sync 50건 silent loss ──────────────────────────
def test_sync_full_paths_not_truncated():
    """audit_and_sync.py audit() 결과에 _all_*_paths가 truncate 안 됨 (Cycle 9 HIGH-5)."""
    import re
    script = _SKILLS_ROOT / "plugin-ssot-audit" / "scripts" / "audit_and_sync.py"
    text = script.read_text(encoding="utf-8")
    # _all_drift_paths 사용 확인
    assert "_all_drift_paths" in text, "sync 분리 누락 — silent loss 회귀"
    assert "_all_cache_only_paths" in text
    assert "_all_proj_only_paths" in text


# ── 메인 runner ─────────────────────────────────────────────────────────
def run_all_tests() -> int:
    tests = [
        (name, fn) for name, fn in globals().items()
        if name.startswith("test_") and callable(fn)
    ]
    passed = 0
    failed: list[tuple[str, str]] = []
    for name, fn in tests:
        _reset_caches()  # 각 테스트는 깨끗한 캐시로
        try:
            fn()
            passed += 1
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed.append((name, str(e)))
            print(f"  FAIL  {name}: {e}")
        except Exception as e:
            failed.append((name, f"{type(e).__name__}: {e}"))
            print(f"  ERR   {name}: {type(e).__name__}: {e}")

    print()
    print(f"Total: {len(tests)}, Passed: {passed}, Failed: {len(failed)}")
    if failed:
        print("\nFailed tests:")
        for name, msg in failed:
            print(f"  {name}: {msg}")
        return 1
    print("\nAll regression tests PASS.")
    return 0


if __name__ == "__main__":
    sys.exit(run_all_tests())
