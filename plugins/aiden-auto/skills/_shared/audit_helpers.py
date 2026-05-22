"""5종 audit 스크립트 공유 helper — stub-aware classification.

목적:
- 진짜 의도되지 않은 중복(real_duplicate)과 의도된 패턴(stub/shadow/mirror)을 구분
- false positive 제거: aiden-auto v28.1 stub, claude-code-plugins shadow marketplace 등
- 5종 audit이 import 가능한 단일 정본

설계 원칙:
- 표준 라이브러리만 (yaml/toml 의존성 없음)
- import 실패 시 audit이 fallback 가능하도록 모든 함수는 안전 default 반환
- 모든 분류는 보수적 (확신할 때만 의도된 것으로 분류, 나머진 real_duplicate)
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

# stub redirect 키워드 패턴 (대소문자 무시)
_STUB_KEYWORDS = re.compile(
    r"\bdeprecated\b|\bredirect stub\b|\bredirect to\b|local stub",
    re.IGNORECASE,
)

# 정본 명시 패턴 (한글 + 영문)
_CANONICAL_HINT = re.compile(r"정본|canonical|plugin\s+\w+\s+v\d", re.IGNORECASE)

# stub 본문 줄 수 임계값 — 5종 audit 통일 (이전 80/10 불일치 해소)
_STUB_BODY_LINE_THRESHOLD = 30

_ENABLED_SETTINGS = Path.home() / ".claude" / "settings.json"
_INSTALLED_PLUGINS = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
_MARKETPLACES_DIR = Path.home() / ".claude" / "plugins" / "marketplaces"

# 작동 영향 0 으로 안전하게 분류 가능한 intent 집합 (5종 audit 공유, DRY)
# real_duplicate, priority_resolution_drift, project_global_drift 는 정리 필요 → 제외
BENIGN_INTENTS: frozenset = frozenset({
    "shadow_marketplace",
    "byte_identical_mirror",
    "redirect_stub",
    "project_global_mirror",
    "plugin_namespaced",
    "priority_resolution_local_wins",
    "priority_resolution_global_wins",
    "localization_override",
    # A-5 (2026-05-18 audit-loop): plugin cache 의 multi-version 잔재 — 사용자 작동 영향 0
    "plugin_multi_version_cache",
    # A-6 (2026-05-18 audit-loop): 외부 plugin 의 cache/marketplaces 자체 drift — 우리 권한 밖
    "external_plugin_internal_drift",
})

# A-9 (2026-05-18 audit-loop critic FP-1): CANONICAL_PLUGINS SSOT 단일 정본.
# audit_skills/audit_commands/audit_matrix 의 이중 정의 제거 → 본 import 단일 경로.
# 정밀 검증 대상 plugin (drift / NAME_MISMATCH / WEAK_DESC 등 strict 적용).
# 그 외는 외부 plugin — plugin 저자 책임 (BENIGN 분류 + masked counter 집계).
#
# 동적 확장 (A-9 보강): ~/.claude/state/audit-config.json 에 canonical_plugins 배열 정의 시
# 본 frozenset 에 추가 등록 (기본값에 합집합). config 파일 부재 시 기본값만 사용.
# IMPORTANT: _CANONICAL_DEFAULT 는 절대 축소 금지. _extra 는 합집합으로만 추가됨.
# A-20 (Cycle 18 critic RS-3): import json 중복 alias 제거 — 상단 `import json` 재사용.
# A-14 (Cycle 18 critic FN-1): silent fallback 제거 — 설정 오류 stderr 경고.
_CANONICAL_DEFAULT = {"aiden-auto"}
_CONFIG_PATH = Path("C:/claude/.claude/state/audit-config.json")
try:
    if _CONFIG_PATH.is_file():
        _cfg = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        _extra = _cfg.get("canonical_plugins", [])
        if isinstance(_extra, list):
            CANONICAL_PLUGINS: frozenset = frozenset(_CANONICAL_DEFAULT | set(_extra))
        else:
            print(f"[WARN] audit-config.json: canonical_plugins 가 list 아님 — 기본값 사용",
                  file=sys.stderr)
            CANONICAL_PLUGINS = frozenset(_CANONICAL_DEFAULT)
    else:
        CANONICAL_PLUGINS = frozenset(_CANONICAL_DEFAULT)
except Exception as _e:
    print(f"[WARN] audit-config.json 로드 실패: {_e} — 기본값(aiden-auto)만 사용",
          file=sys.stderr)
    CANONICAL_PLUGINS = frozenset(_CANONICAL_DEFAULT)


def is_canonical_plugin(plugin_name: str | None) -> bool:
    """plugin 이름이 CANONICAL_PLUGINS 에 속하는지 확인 (None 안전)."""
    return bool(plugin_name) and plugin_name in CANONICAL_PLUGINS


def analyze_drift_direction(paths: list[Path]) -> dict:
    """A-12 (critic FP-2): cache vs marketplaces drift 방향 분석.

    Returns dict with keys:
      cache_paths, marketplaces_paths, cache_newer (bool or None — None if 비교 불가).

    cache_newer = True 시 잠재 위험 (예상치 못한 cache 변조).
    audit 보고에 노출하여 사용자 시야 확보.
    """
    cache_paths: list[Path] = []
    market_paths: list[Path] = []
    for p in paths:
        if "marketplaces" in p.parts:
            market_paths.append(p)
        elif any(p.parts[i] == "plugins" and p.parts[i + 1] == "cache"
                 for i in range(len(p.parts) - 1)):
            cache_paths.append(p)
    cache_newer: bool | None = None
    if cache_paths and market_paths:
        try:
            cache_mtime = max(p.stat().st_mtime for p in cache_paths)
            market_mtime = max(p.stat().st_mtime for p in market_paths)
            cache_newer = cache_mtime > market_mtime
        except OSError:
            cache_newer = None
    return {
        "cache_paths": [str(p) for p in cache_paths],
        "marketplaces_paths": [str(p) for p in market_paths],
        "cache_newer": cache_newer,
    }


def is_redirect_stub(body: str, fm: dict | None = None) -> bool:
    """파일이 정본을 가리키는 redirect stub인지 판단.

    조건 (any of):
    1. frontmatter description 또는 version에 'deprecated' 포함
    2. body 80줄 미만 + stub 키워드(deprecated/redirect/stub) 포함
    3. body에 '정본' + 'plugin' 동시 명시
    """
    fm = fm or {}
    if "deprecated" in fm.get("description", "").lower():
        return True
    if "deprecated" in str(fm.get("version", "")).lower():
        return True
    body_lines = [l for l in body.splitlines() if l.strip()]
    if len(body_lines) < _STUB_BODY_LINE_THRESHOLD and _STUB_KEYWORDS.search(body):
        return True
    if "정본" in body and re.search(r"\bplugin\b", body, re.IGNORECASE):
        return True
    return False


# 세션 수명 캐시 (settings.json/installed_plugins.json은 audit 실행 중 변경되지 않음)
_active_cache: set[str] | None = None
_installed_cache: set[str] | None = None
_shadow_cache: set[str] | None = None


def get_active_marketplaces() -> set[str]:
    """settings.json의 enabledPlugins에 등록된 marketplace 집합 (캐시됨)."""
    global _active_cache
    if _active_cache is not None:
        return _active_cache
    try:
        s = json.loads(_ENABLED_SETTINGS.read_text(encoding="utf-8"))
        ep = s.get("enabledPlugins", {})
        marketplaces: set[str] = set()
        for k, v in ep.items():
            if v and "@" in k:
                marketplaces.add(k.split("@", 1)[1])
        _active_cache = marketplaces
    except Exception:
        _active_cache = set()
    return _active_cache


def get_installed_marketplaces() -> set[str]:
    """installed_plugins.json에서 실제 install된 plugin들의 marketplace 집합 (캐시됨)."""
    global _installed_cache
    if _installed_cache is not None:
        return _installed_cache
    try:
        d = json.loads(_INSTALLED_PLUGINS.read_text(encoding="utf-8"))
        plugins = d.get("plugins", {})
        marketplaces: set[str] = set()
        for k in plugins.keys():
            if "@" in k:
                marketplaces.add(k.split("@", 1)[1])
        _installed_cache = marketplaces
    except Exception:
        _installed_cache = set()
    return _installed_cache


def get_shadow_marketplaces() -> set[str]:
    """디스크엔 있으나 enabledPlugins + installed 어디에도 없는 marketplace.

    100% 그림자 (어떤 plugin도 활성/설치 안 됨). 세션 캐시됨.
    """
    global _shadow_cache
    if _shadow_cache is not None:
        return _shadow_cache
    if not _MARKETPLACES_DIR.is_dir():
        _shadow_cache = set()
        return _shadow_cache
    disk = {p.name for p in _MARKETPLACES_DIR.iterdir() if p.is_dir()}
    _shadow_cache = disk - get_active_marketplaces() - get_installed_marketplaces()
    return _shadow_cache


def _reset_caches() -> None:
    """테스트용 캐시 리셋."""
    global _active_cache, _installed_cache, _shadow_cache
    _active_cache = None
    _installed_cache = None
    _shadow_cache = None


def path_marketplace(path: Path) -> str | None:
    """경로가 marketplace 내부면 marketplace 이름 반환, 아니면 None.

    Rule 19 v2.0 정합 (2026-05-18 audit-loop):
      - marketplaces/<mkt>/...
      - plugins/cache/<mkt>/...
    """
    parts = path.parts
    if "marketplaces" in parts:
        idx = parts.index("marketplaces")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    # cache 구조
    for i in range(len(parts) - 1):
        if parts[i] == "plugins" and parts[i + 1] == "cache":
            if i + 2 < len(parts):
                return parts[i + 2]
            return None
    return None


def path_plugin(path: Path) -> str | None:
    """경로가 plugin 내부면 plugin 이름 반환.

    지원 구조 (Rule 19 v2.0 정합, 2026-05-18 audit-loop):
      - marketplaces/<mkt>/{plugins|external_plugins}/<plugin>/...
      - plugins/cache/<mkt>/<plugin>/<version>/...   (실제 CC 로드 위치)

    P9 patch 와 정합: path_source() 가 cache 를 'plugin' 으로 분류하므로
    path_plugin() 도 cache 경로에서 plugin 이름을 정확히 추출해야 함
    (그렇지 않으면 all_in_different_plugins() 가 잘못 False 반환).
    """
    parts = path.parts
    # marketplaces 구조
    if "marketplaces" in parts:
        mkt_idx = parts.index("marketplaces")
        # parts[mkt_idx+1] = marketplace name
        # parts[mkt_idx+2] = 'plugins' or 'external_plugins'
        # parts[mkt_idx+3] = plugin name
        if mkt_idx + 3 < len(parts) and parts[mkt_idx + 2] in ("plugins", "external_plugins"):
            return parts[mkt_idx + 3]
        return None
    # cache 구조: plugins/cache/<mkt>/<plugin>/<version>/...
    for i in range(len(parts) - 1):
        if parts[i] == "plugins" and parts[i + 1] == "cache":
            # parts[i+2] = marketplace name (예: garimto81-aiden-auto, claude-plugins-official)
            # parts[i+3] = plugin name      (예: aiden-auto, superpowers, slack)
            if i + 3 < len(parts):
                return parts[i + 3]
            return None
    return None


def is_in_shadow_marketplace(path: Path) -> bool:
    """경로가 shadow marketplace 내부면 True. 작동 영향 0."""
    m = path_marketplace(path)
    return m is not None and m in get_shadow_marketplaces()


def all_in_different_plugins(paths: list[Path]) -> bool:
    """모든 path가 서로 다른 plugin 소속이면 True (plugin namespace 분리).

    외부 marketplace에서 여러 plugin이 같은 이름의 skill을 제공하는 경우.
    각 plugin이 자체 namespace 안에서 작동하므로 충돌 없음.
    """
    plugins: set[str] = set()
    for p in paths:
        pl = path_plugin(p)
        if not pl:
            return False
        plugins.add(pl)
    return len(plugins) == len(paths)


# project local 경로 prefix (Cycle 9 critic: Windows 대소문자 일관성)
_LOCAL_PREFIX = "c:/claude/.claude"


def path_source(path: Path) -> str:
    """경로 출처 분류: 'local' / 'global' / 'plugin'.

    parts 기반 (substring 매칭 회피).
    Windows 대소문자 무관성: 모두 lowercase로 비교 (forward-slash 정규화).

    Rule 19 v2.0 정합 (2026-05-18 audit-loop):
      marketplaces/ + cache/ 모두 plugin 영역으로 분류 (이전엔 marketplaces 만).
      cache/ 는 실제 CC 로드 위치이므로 plugin 영역 필수.
    """
    parts = path.parts
    if "marketplaces" in parts:
        return "plugin"
    # plugins/cache/ 정확한 sequence (substring "cache" 오분류 회피)
    for i in range(len(parts) - 1):
        if parts[i] == "plugins" and parts[i + 1] == "cache":
            return "plugin"
    s = str(path).replace("\\", "/").lower()
    if s.startswith(_LOCAL_PREFIX):
        return "local"
    return "global"


# 비영어 언어 감지용 unicode 범위 (한글/일본어/중국어/키릴/아랍/히브리/태국/베트남)
# 정밀 unicode escape 사용 (regex 가독성 + Cycle 9 한글 `힣` 매칭 실패 수정)
_NON_ASCII_LANG = re.compile(
    r"[가-힣"   # 한글 음절 (가~힣, U+D7A3 끝값 정확)
    r"ㄱ-ㆎ"    # 한글 호환 자모 (ㄱ-ㆎ)
    r"ぁ-ゟ"    # 일본어 히라가나
    r"゠-ヿ"    # 일본어 카타카나
    r"･-ﾟ"    # 일본어 반각 카타카나
    r"一-鿿"    # CJK Unified Ideographs (기본)
    r"㐀-䶿"    # CJK 확장 A
    r"Ѐ-ӿ"    # 키릴
    r"Ԁ-ԯ"    # 키릴 보조
    r"؀-ۿ"    # 아랍
    r"֐-׿"    # 히브리
    r"฀-๿"    # 태국
    # 주의: Latin-1 Supplement (U+00C0-U+00FF, À-ÿ) 는 의도적 제외 —
    # 영어권 라틴 액센트 (café, naïve, résumé, über, façade)가 false positive 발생
    # 베트남어 특수 문자 (ế, ộ 등)는 Latin Extended Additional 로 충분
    r"Ḁ-ỿ"    # 라틴 확장 추가 (베트남어 ế 등, U+1E00-U+1EFF)
    r"]"
)


def is_localization_diff(paths: list[Path]) -> bool:
    """두 파일의 diff가 언어 번역 차이만인지 판단.

    원리: diff된 줄(replace 영역) 중 한쪽에만 비영어 문자(한글/일본어/중국어/키릴/아랍)가
    포함되어 있고 다른쪽은 영어 only면 의도된 localization으로 판단.

    예: 'description: 한글 설명' ↔ 'description: English desc'
    """
    if len(paths) != 2:
        return False
    try:
        import difflib
        a = paths[0].read_text(encoding="utf-8", errors="replace").splitlines()
        b = paths[1].read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return False

    diff_a: list[str] = []
    diff_b: list[str] = []
    matcher = difflib.SequenceMatcher(None, a, b)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            diff_a.extend(a[i1:i2])
        if tag in ("replace", "insert"):
            diff_b.extend(b[j1:j2])

    # Cycle 12 MED-1: 양쪽 모두 diff 있어야 localization 판단 (delete-only false positive 방지)
    if not (diff_a and diff_b):
        return False

    a_nonascii_lines = sum(1 for line in diff_a if _NON_ASCII_LANG.search(line))
    b_nonascii_lines = sum(1 for line in diff_b if _NON_ASCII_LANG.search(line))

    a_ratio = a_nonascii_lines / len(diff_a) if diff_a else 0
    b_ratio = b_nonascii_lines / len(diff_b) if diff_b else 0

    # 두 조건 중 하나라도 만족 (Cycle 9 임계값 sensitivity 수정):
    # (1) ratio 차이 ≥ 0.3 + 한쪽에 비영어 라인 ≥ 1 → 명확한 언어 분리
    # (2) 절대값: 한쪽 ≥ 50% + 다른쪽 ≤ 10% (기존 strict 조건 보존)
    ratio_diff = abs(a_ratio - b_ratio)
    has_nonascii = (a_nonascii_lines >= 1) or (b_nonascii_lines >= 1)
    if has_nonascii and ratio_diff >= 0.3:
        return True
    if a_ratio >= 0.5 and b_ratio <= 0.1:
        return True
    if b_ratio >= 0.5 and a_ratio <= 0.1:
        return True
    return False


def all_byte_identical(paths: list[Path]) -> bool:
    """모든 path의 파일이 SHA256 동일하면 True (byte-level mirror).

    단일 path는 trivially True (자기 자신과 동일).
    파일 읽기 실패 시 False (안전 default).
    """
    if len(paths) <= 1:
        return True
    hashes: set[str] = set()
    for p in paths:
        try:
            hashes.add(hashlib.sha256(p.read_bytes()).hexdigest())
        except Exception:
            return False
    return len(hashes) == 1


def classify_duplicate_intent(
    paths: list[Path],
    bodies: list[str] | None = None,
    fms: list[dict] | None = None,
) -> str:
    """다중 path 중복의 의도 분류.

    Returns:
        'shadow_marketplace'      : 한쪽이 비활성 marketplace 잔재 → 작동 영향 0
        'byte_identical_mirror'   : 모든 path가 byte-identical → 작동 동일
        'redirect_stub'           : stub + canonical 의도된 redirect → 작동 정상
        'project_global_mirror'   : project + global byte-identical mirror → 작동 동일
        'plugin_namespaced'       : 서로 다른 plugin이 같은 이름 사용 → 충돌 없음
        'priority_resolution_*'   : local/global이 plugin을 그림자화 (byte-identical)
        'priority_resolution_drift': 우선순위 해소 + 내용 drift → 잠재 위험 (WARN)
        'project_global_drift'    : project + global drift → 잠재 위험 (WARN)
        'real_duplicate'          : 진짜 의도되지 않은 중복 → 정리 필요
    """
    if len(paths) < 2:
        return "real_duplicate"

    bodies = bodies or [""] * len(paths)
    fms = fms or [{}] * len(paths)
    shadow = get_shadow_marketplaces()

    # case 1: 한 path라도 shadow marketplace에 있음 → shadow
    for p in paths:
        m = path_marketplace(p)
        if m and m in shadow:
            return "shadow_marketplace"

    # case 2: 모든 파일이 byte-identical → 어느 쪽 이겨도 결과 동일
    if all_byte_identical(paths):
        return "byte_identical_mirror"

    # case 2.5: localization diff (한글↔영어 번역만 다름) → 의도된 customization
    if is_localization_diff(paths):
        return "localization_override"

    # case 3: 일부는 stub, 나머지(>=1)는 canonical → redirect_stub
    stub_flags = [is_redirect_stub(b, fm) for b, fm in zip(bodies, fms)]
    stub_count = sum(stub_flags)
    if 1 <= stub_count < len(paths):
        return "redirect_stub"

    # case 4: 정확히 project + global 쌍 (drift 검사 추가 — critic HIGH-1 대응)
    sources = [path_source(p) for p in paths]
    if sorted(sources) == ["global", "local"] and stub_count == 0:
        # byte-identical이 아니면 drift → 잠재 위험 (WARN)
        # case 2 (all_byte_identical)에서 이미 걸렀어야 하지만 명시 재검증
        return "project_global_mirror" if all_byte_identical(paths) else "project_global_drift"

    # case 5: 모든 path가 서로 다른 plugin 소속 → namespace 분리
    if all_in_different_plugins(paths):
        return "plugin_namespaced"

    # case 5.5: 같은 plugin 의 marketplaces+cache mirror (byte_identical) 를
    #   1 effective path 로 dedupe 후 namespace 재검사 (2026-05-18 audit-loop A-3)
    # 이유: aiden-auto 가 marketplaces 와 cache 양쪽에 같은 파일을 가지면
    #   all_in_different_plugins 가 2 (plugins) != 3 (paths) 로 False 반환 →
    #   case 5 가 누락되고 real_duplicate 로 낙하하는 false positive 발생.
    #
    # A-22 (Cycle 20 critic): plugin_groups dict 는 case 5.5/5.6/5.7 에서 공유 사용.
    # case 순서 변경 시 NameError 위험 — case 5.5 의 변수가 5.6/5.7 진입 시점에 살아있어야 함.
    plugin_groups: dict[str, list[Path]] = {}
    for p in paths:
        pl = path_plugin(p)
        if pl:
            plugin_groups.setdefault(pl, []).append(p)
    if plugin_groups:
        # 각 plugin 그룹 내부가 byte_identical 이면 effective 1 path 로 대표
        effective_paths: list[Path] = []
        all_groups_uniform = True
        for pl, group in plugin_groups.items():
            if len(group) == 1 or all_byte_identical(group):
                effective_paths.append(group[0])
            else:
                all_groups_uniform = False
                break
        # plugin 미소속 path (local/global) 도 effective 에 포함
        for p in paths:
            if not path_plugin(p):
                effective_paths.append(p)
        if all_groups_uniform and len(effective_paths) >= 2:
            if all_in_different_plugins(effective_paths):
                return "plugin_namespaced"

    # case 5.6: plugin_multi_version_cache — 같은 plugin 의 다른 version 디렉토리 (cache/<plugin>/<version>/)
    #   에 같은 파일이 보관됨. Claude Code 가 plugin 업데이트 시 옛 version 잔존.
    #   활성 version 1개만 실제 로드되므로 사용자 작동 영향 0.
    #   (2026-05-18 audit-loop A-5)
    if plugin_groups and len(plugin_groups) == 1:
        only_plugin = next(iter(plugin_groups.keys()))
        # 모든 path 가 같은 plugin 의 cache 트리에 있고, version dir 만 다름
        version_dirs: set[str] = set()
        all_in_cache = True
        for p in paths:
            parts = p.parts
            cache_idx = None
            for i in range(len(parts) - 1):
                if parts[i] == "plugins" and parts[i + 1] == "cache":
                    cache_idx = i
                    break
            if cache_idx is None:
                all_in_cache = False
                break
            # parts[cache_idx+2] = marketplace, parts[cache_idx+3] = plugin, parts[cache_idx+4] = version
            if cache_idx + 4 < len(parts):
                version_dirs.add(parts[cache_idx + 4])
        if all_in_cache and len(version_dirs) >= 2:
            return "plugin_multi_version_cache"

    # case 5.7: external_plugin_internal_drift — 외부 plugin 의 cache + marketplaces
    #   양쪽에 같은 plugin 의 파일이 SHA 다르게 존재. plugin 저자가 marketplaces 의 manifest
    #   snapshot 과 cache 의 활성 release 를 별도 관리하는 경우.
    #   외부 plugin (whitelist 외) 의 이런 drift 는 우리 권한 밖이므로 BENIGN 분류.
    #   (2026-05-18 audit-loop A-6 — 유연 아키텍처)
    if plugin_groups and len(plugin_groups) == 1:
        only_plugin = next(iter(plugin_groups.keys()))
        # CANONICAL_PLUGINS SSOT (A-9): 본 모듈 상단 정의 import 사용
        if not is_canonical_plugin(only_plugin):
            # cache + marketplaces 양쪽에 분포 확인
            has_cache = any("cache" in p.parts and p.parts[max(0, p.parts.index("cache") - 1)] == "plugins" for p in paths if "cache" in p.parts)
            has_market = any("marketplaces" in p.parts for p in paths)
            if has_cache and has_market:
                # A-16 (Cycle 18 critic DI-1): A-12 reference 제거. analyze_drift_direction()
                # 함수는 별도 분석 도구로 보존 (audit-loop 외부 호출 가능). 본 case 는 BENIGN
                # 판정만 — 외부 plugin 의 자체 drift 는 plugin 저자 책임. 방향 정보가 필요하면
                # 별도로 analyze_drift_direction(paths) 호출.
                return "external_plugin_internal_drift"

    # case 6: 우선순위 해소 — local 또는 global이 plugin을 그림자화
    # Claude Code 우선순위: project local > global > plugin
    # byte-identical이면 진짜 benign, drift면 WARN (v28.1 마이그레이션 잔재 가능)
    # v2 보강 (2026-05-18 audit-loop): user 그룹(local+global) vs plugin 그룹이
    #   각자 내부 동일이면 정상 customize 패턴 → BENIGN 분류
    if "local" in sources and "plugin" in sources:
        if all_byte_identical(paths):
            return "priority_resolution_local_wins"
        user_paths = [p for p, s in zip(paths, sources) if s in ("local", "global")]
        plugin_paths = [p for p, s in zip(paths, sources) if s == "plugin"]
        if user_paths and plugin_paths:
            user_uniform = len(user_paths) == 1 or all_byte_identical(user_paths)
            plugin_uniform = len(plugin_paths) == 1 or all_byte_identical(plugin_paths)
            if user_uniform and plugin_uniform:
                return "priority_resolution_local_wins"
        return "priority_resolution_drift"
    if "global" in sources and "plugin" in sources and "local" not in sources:
        if all_byte_identical(paths):
            return "priority_resolution_global_wins"
        global_paths = [p for p, s in zip(paths, sources) if s == "global"]
        plugin_paths = [p for p, s in zip(paths, sources) if s == "plugin"]
        if global_paths and plugin_paths:
            global_uniform = len(global_paths) == 1 or all_byte_identical(global_paths)
            plugin_uniform = len(plugin_paths) == 1 or all_byte_identical(plugin_paths)
            if global_uniform and plugin_uniform:
                return "priority_resolution_global_wins"
        return "priority_resolution_drift"

    # all-stubs (stub_count == len(paths)): 정본 없이 stub만 → real_duplicate 로 낙하
    return "real_duplicate"


def read_text_safe(path: Path) -> str:
    """파일 안전 읽기. 실패 시 빈 문자열."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def parse_frontmatter_simple(text: str) -> tuple[dict, str]:
    """YAML frontmatter 간단 파싱. (fm dict, body str) 반환.

    YAML block scalar (> 또는 |) 지원.
    A-7 (2026-05-18 audit-loop): implicit multi-line string 지원
    (key: 다음 줄에 들여쓴 quoted/unquoted string 이 이어지는 경우).
    """
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_block = text[3:end].strip()
    body = text[end + 4:].strip()
    fm: dict = {}
    lines = fm_block.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        # A-13 (2026-05-18 audit-loop): hyphen 포함 키 (user-invocable, audit-exclude 등) 지원
        m = re.match(r"^([A-Za-z][\w\-]*)\s*:\s*(.*)", line)
        if m:
            key = m.group(1)
            val = m.group(2).strip()
            if val in (">", "|", ">-", "|-", ">+", "|+"):
                block: list[str] = []
                i += 1
                while i < len(lines) and (lines[i].startswith(" ") or lines[i].startswith("\t")):
                    block.append(lines[i].strip())
                    i += 1
                fm[key] = " ".join(block)
                continue
            elif val == "":
                # A-7: implicit multi-line string — 다음 줄들이 들여쓴 값
                block: list[str] = []
                i += 1
                while i < len(lines) and (lines[i].startswith(" ") or lines[i].startswith("\t")):
                    stripped = lines[i].strip().strip('"').strip("'")
                    if stripped:
                        block.append(stripped)
                    i += 1
                if block:
                    fm[key] = " ".join(block)
                continue
            else:
                # quoted string 의 양 따옴표 제거
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                # A-13: YAML boolean 변환 (true/false/yes/no/on/off)
                _vlower = val.lower()
                if _vlower in ("true", "yes", "on"):
                    fm[key] = True
                elif _vlower in ("false", "no", "off"):
                    fm[key] = False
                else:
                    fm[key] = val
        i += 1
    return fm, body


# 디버그/검증용 — 직접 실행 시 marketplace 상태 출력
def _selftest() -> None:
    print("=== audit_helpers self-test ===")
    print(f"active marketplaces  : {sorted(get_active_marketplaces())}")
    print(f"installed marketplaces: {sorted(get_installed_marketplaces())}")
    print(f"shadow marketplaces  : {sorted(get_shadow_marketplaces())}")


if __name__ == "__main__":
    _selftest()
