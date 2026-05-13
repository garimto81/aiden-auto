# BatchProcessor 사용 가이드

Google Docs 스킬 Phase 1: 배치 변환 및 자동 트리거 기능

## 개요

`BatchProcessor`와 `AutoTriggerHandler`는 여러 마크다운 파일을 Google Docs로 효율적으로 변환하는 기능을 제공합니다.

## 주요 기능

### 1. BatchConverter

여러 파일을 병렬로 변환하여 시간을 절약합니다.

**특징**:
- 비동기 병렬 처리 (기본 3개 동시 실행)
- 세마포어 기반 동시성 제어
- 개별 파일 실패 시 나머지 계속 처리
- 상세한 진행 상황 출력

**사용 예제**:

```python
from pathlib import Path
from lib.google_docs import BatchConverter

# 초기화
converter = BatchConverter(
    folder_id=None,  # 기본 폴더 사용
    parallel=3,      # 동시 3개씩 처리
)

# 방법 1: 파일 리스트 변환
files = [
    Path("tasks/prds/PRD-0001.md"),
    Path("tasks/prds/PRD-0002.md"),
]

results = converter.convert_directory(Path("tasks/prds"))

# 방법 2: 디렉토리 변환
results = converter.convert_directory(
    directory=Path("tasks/prds"),
    pattern="*.md",
    recursive=False,
)

# 결과 확인
for result in results:
    if result.success:
        print(f"✓ {result.source_file.name} → {result.doc_url}")
    else:
        print(f"✗ {result.source_file.name}: {result.error}")
```

### 2. AutoTriggerHandler

키워드 또는 파일 패턴 기반으로 자동 변환을 트리거합니다.

**트리거 조건**:

| 유형 | 예시 |
|------|------|
| 키워드 | `prd to gdocs`, `md to docs`, `--to-gdocs`, `google docs로` |
| 파일 패턴 | `tasks/prds/*.md`, `**/PRD-*.md`, `docs/prds/*.md` |

**사용 예제**:

```python
from pathlib import Path
from lib.google_docs import AutoTriggerHandler

# 초기화
handler = AutoTriggerHandler(folder_id=None)

# 트리거 여부 확인
if handler.should_trigger(user_input="prd to gdocs"):
    print("트리거 조건 충족!")

# 파일 패턴 확인
if handler.should_trigger(file_path=Path("tasks/prds/PRD-0001.md")):
    print("파일 패턴 매칭!")

# 변환 실행
doc_url = handler.execute(Path("tasks/prds/PRD-0001.md"))
print(f"문서 생성: {doc_url}")

# 변환 제안 생성
suggestion = handler.suggest_conversion(Path("tasks/prds/PRD-0001.md"))
print(f"변환 권장: {suggestion['should_convert']}")
print(f"이유: {suggestion['reason']}")
print(f"신뢰도: {suggestion['confidence']:.1%}")
```

## API 레퍼런스

### BatchConverter

#### `__init__(folder_id=None, parallel=3)`

**매개변수**:
- `folder_id` (str | None): Google Drive 폴더 ID (None이면 기본 폴더)
- `parallel` (int): 병렬 처리 수 (기본 3)

#### `convert_batch(files: list[Path]) -> list[ConvertResult]`

여러 파일을 병렬로 변환합니다.

**반환**: 변환 결과 리스트

#### `convert_directory(directory: Path, pattern="*.md", recursive=False) -> list[ConvertResult]`

디렉토리 내 모든 파일을 변환합니다.

**매개변수**:
- `directory` (Path): 검색할 디렉토리
- `pattern` (str): 파일 패턴 (기본: `*.md`)
- `recursive` (bool): 재귀 검색 여부

### AutoTriggerHandler

#### `__init__(folder_id=None)`

**매개변수**:
- `folder_id` (str | None): Google Drive 폴더 ID

#### `should_trigger(user_input=None, file_path=None) -> bool`

트리거 조건을 평가합니다.

**매개변수**:
- `user_input` (str | None): 사용자 입력 텍스트
- `file_path` (Path | None): 대상 파일 경로

**반환**: 트리거 여부

#### `execute(target: str | Path) -> str`

변환을 실행하고 문서 URL을 반환합니다.

**매개변수**:
- `target` (str | Path): 변환할 파일 경로 또는 마크다운 텍스트

**반환**: 생성된 문서 URL

**예외**:
- `ValueError`: 파일이 존재하지 않거나 읽을 수 없는 경우
- `Exception`: Google Docs API 에러

#### `suggest_conversion(file_path: Path) -> dict`

변환 제안을 생성합니다 (자동 감지용).

**반환**: 제안 정보 딕셔너리
```python
{
    'should_convert': bool,
    'reason': str,
    'confidence': float,  # 0.0 ~ 1.0
    'file_path': Path,
}
```

### ConvertResult

변환 결과를 나타내는 데이터클래스입니다.

**필드**:
- `source_file` (Path): 원본 파일 경로
- `success` (bool): 성공 여부
- `doc_url` (str | None): 생성된 문서 URL (성공 시)
- `error` (str | None): 에러 메시지 (실패 시)

## 에러 처리

### 개별 파일 실패

`BatchConverter`는 개별 파일 실패 시 나머지 파일 처리를 계속합니다.

```python
results = converter.convert_directory(Path("tasks/prds"))

# 실패한 파일만 필터링
failed = [r for r in results if not r.success]
for result in failed:
    print(f"실패: {result.source_file.name}")
    print(f"  에러: {result.error}")
```

### API 제한 회피

Google Docs API는 요청 제한이 있습니다. `parallel` 값을 조정하여 제어하세요.

```python
# 느리지만 안정적
converter = BatchConverter(parallel=1)

# 빠르지만 제한에 걸릴 수 있음
converter = BatchConverter(parallel=5)
```

## 테스트

단위 테스트가 포함되어 있습니다.

```bash
# BatchConverter 테스트
pytest lib/google_docs/tests/test_batch_processor.py -v

# AutoTriggerHandler 테스트
pytest lib/google_docs/tests/test_auto_trigger.py -v
```

## 다음 단계 (Phase 2)

- CLI 통합 (`lib/google_docs/cli.py`)
- `/skill gdocs` 커맨드 구현
- 실시간 변환 모니터링
- 변환 이력 추적
