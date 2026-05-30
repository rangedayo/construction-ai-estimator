# 라운드 베이스라인-2 본작업 명세서 — 작은 도면 입력 모델 통일

> **작성 목적**: PoC 입력 모델을 "큰 도면 1장"에서 "작은 도면 N장"으로 통일하고,
> dxf 내부 표제부 도면명을 자동 추출해 정답지와 매칭한 뒤 시트 단위로 카운트·길이·규격 측정의
> PASS/FAIL을 검증한다. 이 라운드는 **도면4 검증까지**가 범위. 도면5·3·2·1은 다음 라운드.
>
> **읽는 순서**: 0 → 1 → 2 → (제약 7 먼저) → 3 → 4 → 5 → 6 → 8 → 9

---

## 0. TL;DR

| 항목 | 내용 |
|---|---|
| **목표** | 작은 도면 dxf 입력 → 표제부 도면명 자동 추출 → 정답지 매칭 → 측정 3종(카운트·길이·규격) → 시트별 PASS/FAIL + HTML |
| **핵심 신규 모듈** | `poc_v2/baseline2/sheet_title_extractor.py`, `sheet_name_matcher.py`, `small_drawing_pipeline.py`, `visualize_small.py` |
| **본선 영향** | `counter.py` / `baseline.py` / `length/baseline_length.py` / `spec_extractor.py` / 모든 yaml 무수정 |
| **회귀 안전망** | 1단계 14/16, 길이-1 16/16, 규격-1 25/25 그대로 유지 |
| **이번 범위** | 도면4 작은 도면 5개 검증까지 |
| **검증 기준** | (1) 표제부 도면명 추출 100%, (2) 정답지 매칭 100%, (3) 도면4 카운트·길이·규격 PASS, (4) 기존 회귀 무영향 |
| **산출물** | `outputs/round_baseline2_시트별_결과.csv`, `outputs/visualize/도면4_*.html` ×5, `outputs/round_baseline2_보고서.md` |

---

## 1. 배경

### 1.1 입력 모델 통일 결정

지금까지 측정 3종이 **큰 도면(`도면N.dxf`) 1장**을 입력으로 받았다. 새 라운드에서는
멘토 프로세스가 큰 도면을 시트 단위로 분리한 **작은 도면 N장**을 입력으로 통일한다.
근거(베이스라인 컨텍스트에서 확정):

- 적산 전문가 관점에서 "작은 도면 파일명 던지기"가 최종 서비스 모델
- 멘토님이 작은 도면 저장 프로세스를 이미 갖고 계심
- 정답지가 이미 작은 도면 단위(시트별 부호 개수)로 기록되어 있음

### 1.2 시트 식별 방법

dxf 내부 **표제부의 도면명 텍스트**를 키로 사용한다. 사전 검증:

- `도면5_정면도우측면도.dxf` 표제부에 `'입면도1'` 텍스트 정확히 존재 → 정답지 시트명 `"입면도1"` 100% 일치
- `도면4_종단면도횡단면도.dxf` 표제부에 `'단면도'` 텍스트 존재 → 정답지 길이 라우팅에 매칭 가능

→ 파일명은 무관. 코드가 dxf 안 표제부를 읽어 시트를 식별한다.

### 1.3 정답지 그대로 사용

`도면_정답지.xlsx`·`도면_길이_정답지.xlsx`의 "도면명" 컬럼이 사실 작은 도면 단위 시트 이름.
표제부 원문이라 자동 매칭의 키로 그대로 사용 가능. 정답지 무수정.

---

## 2. 목표 (산출물)

### 2.1 최종 산출물

작은 도면 dxf 1장 입력 → 다음 4가지를 출력:

```python
@dataclass
class SmallDrawingResult:
    file_path: str                    # 입력 파일 경로
    drawing: str                      # "도면4" — 파일명에서 추출
    extracted_title: str | None       # dxf 표제부에서 추출한 도면명 ("1층 구조평면도")
    matched_sheet: str | None         # 정답지 시트명 매칭 결과 ("1층 구조평면도")
    match_confidence: str             # "exact" | "partial" | "fallback" | "unmatched"

    # 측정 결과
    counts: dict[str, int]            # {"SC1": 14, "SC2": 4}
    length_mm: float | None           # 9000 (단면도류만)
    specs: list[SpecExtraction]       # 부호↔규격 (작은 도면 1장 단위)

    # 정답 비교
    expected_counts: dict[str, int]   # 정답지에서 가져옴
    expected_length: float | None
    expected_specs: dict[str, str]

    pass_counts: bool                 # 카운트 PASS/FAIL
    pass_length: bool | None          # 단면도 아니면 None
    pass_specs: bool
```

### 2.2 CSV 형식

`outputs/round_baseline2_시트별_결과.csv`:

```
도면,파일명,추출도면명,매칭시트,신뢰도,측정카운트,정답카운트,카운트결과,측정길이,정답길이,길이결과,측정규격,정답규격,규격결과
도면4,도면4_1층구조평면도.dxf,1층 구조평면도,1층 구조평면도,exact,"SC1=14,SC2=4","SC1=14,SC2=4",PASS,N/A,N/A,N/A,"SC1=H-350x175x7/11,SC2=H-194x150x6/9","SC1=H-350x175x7/11,SC2=H-194x150x6/9",PASS
도면4,도면4_지붕층구조평면도.dxf,지붕층 구조평면도,지붕층 구조평면도,exact,"SC1=0,SC2=0","SC1=0,SC2=0",PASS,N/A,N/A,N/A,,,N/A
도면4,도면4_종단면도횡단면도.dxf,단면도,종단면도/횡단면도,partial,N/A,N/A,N/A,9000,9000,PASS,,,N/A
```

### 2.3 HTML 시각화

작은 도면 1장당 HTML 1개:

```
outputs/visualize/도면4_1층구조평면도.html
outputs/visualize/도면4_지붕층구조평면도.html
outputs/visualize/도면4_종단면도횡단면도.html
outputs/visualize/도면4_종단면도.html        # 분리본 (선택)
outputs/visualize/도면4_횡단면도.html        # 분리본 (선택)
```

내용:
- 도면 기하 (회색 LINE/POLYLINE)
- 매칭된 부호 (녹색 동그라미) + 카운트 라벨
- 매칭된 규격 (파랑 사각형) + 페어링 점선
- 길이 측정에 사용된 수직선 (빨간 굵은 선) + 양 끝점 십자 마커, 측정값 라벨
- 표제부 도면명 추출 결과를 좌상단 박스에 표시 (확인용)
- 정답 비교 결과 PASS/FAIL 배지

---

## 3. 설계 원칙

### 3.1 본선 무수정 (회귀 안전망 절대 조건)

| 파일 | 상태 |
|---|---|
| `poc_v2/counter.py` | 무수정 |
| `poc_v2/baseline.py` | 무수정 |
| `poc_v2/auto_policy.py` / `detect_table_region.py` / `classify_text.py` | 무수정 |
| `poc_v2/length/baseline_length.py` | 무수정 |
| `poc_v2/length/spec_extractor.py` | 무수정 |
| `config/symbol_rules.yaml` / `length_routing.yaml` | 무수정 |

신규 모듈은 본선 함수를 **import해 호출**만 한다. 인자만 작은 도면용으로 조정.

### 3.2 측정 함수 재사용

본선 함수들은 이미 modelspace 인자를 받는 구조라 작은 도면이 그대로 들어가도 동작.

- **카운트**: `baseline.compute_drawing(dxf_path, ...)` — 작은 도면 dxf 경로 그대로 전달
- **길이**: `length.baseline_length`의 세로 DIMENSION 최댓값 함수 — modelspace에서 직접 측정
- **규격**: `spec_extractor.extract_from_dxf(dxf_path)` — 작은 도면 그대로 전달

만약 본선 함수가 큰 도면 가정의 영역 분리 로직에 의존한다면 (예: detect_table_regions 결과),
**작은 도면에서는 자동으로 우회**되는지 확인하고 우회되도록 인자 조정. 함수 자체는 수정 X.

### 3.3 fallback yaml — 최후의 수단

표제부 도면명 자동 매칭이 실패한 케이스만 yaml에 매핑을 박는다.
**자동으로 풀리는 것은 yaml에 적지 않는다** (보편 룰 우선).

```yaml
# config/sheet_name_overrides.yaml
도면4:
  단면도: ["종단면도", "횡단면도"]   # 표제부 "단면도" 1개 → 정답지 라우팅의 2개 매칭
```

### 3.4 "AI는 결정만, 도구는 측정만"

- 표제부 도면명 추출: 좌표·height 기반 결정론적 휴리스틱
- 시트명 매칭: 정규화 후 결정론적 비교, 모호하면 fallback yaml
- LLM·VLM 호출 0건

---

## 4. 작업 항목

### 작업 0 — 회귀 사전 확인

작업 시작 전 기존 회귀 3종 실행해 베이스라인 PASS 수 기록:

```bash
pytest -v poc_v2/tests/test_regression.py
pytest -v poc_v2/length/tests/test_length_regression.py
pytest -v poc_v2/length/tests/test_spec_regression.py
```

기록: 1단계 14/16, 길이-1 16/16, 규격-1 25/25. 작업 종료 시 동일한지 재확인.

### 작업 1 — 표제부 도면명 추출기

**파일**: `poc_v2/baseline2/sheet_title_extractor.py`
**입력**: 작은 도면 dxf 경로
**처리**:
1. modelspace의 TEXT/MTEXT 전부 수집 (MTEXT 이스케이프 제거)
2. **도면명 키워드** 포함 텍스트만 후보화:
   `평면도`, `단면도`, `입면도`, `주심도`, `부호도`, `골구도`, `골조도`,
   `정면도`, `측면도`, `배면도`, `구조도`, `보복도`
3. 후보 중 height·좌표 기준 점수화:
   - height가 도면 내 큰 텍스트 그룹에 속하면 가점
   - 좌표가 우측·우하단(표제부 영역)이면 가점
4. 최고점 후보를 도면명으로 채택. 동률이면 모두 반환 (도면4 "단면도" 케이스).

**출력**:
```python
@dataclass
class SheetTitle:
    raw_text: str
    height: float
    coord: tuple[float, float]
    score: float
```

`list[SheetTitle]` 반환 (보통 1개, 모호 시 2~3개).

### 작업 2 — 정답지 시트명 매칭

**파일**: `poc_v2/baseline2/sheet_name_matcher.py`
**입력**: `(drawing: "도면4", extracted_titles: list[str])`
**처리**:
1. 정답지(`도면_정답지.xlsx`)에서 해당 도면의 시트명 목록 로드
2. 정규화: 공백·콤마·괄호·줄바꿈·하이픈 제거, 소문자화
3. 매칭 순서:
   - **exact**: 정규화된 추출 도면명 == 정규화된 정답지 시트명
   - **partial**: 한쪽이 다른쪽을 포함 (도면4 "단면도" ⊂ 정답지 라우팅 "종단면도, 횡단면도")
   - **fallback**: yaml override 참조
   - **unmatched**: 위 셋 다 실패
4. 동(1동/2동) 정보가 있으면 우선 매칭에 사용 (도면1 케이스 대비)

**출력**:
```python
@dataclass
class SheetMatch:
    matched_sheet: str | None
    confidence: Literal["exact", "partial", "fallback", "unmatched"]
    candidates: list[str]
```

### 작업 3 — 작은 도면 측정 파이프라인

**파일**: `poc_v2/baseline2/small_drawing_pipeline.py`
**입력**: 작은 도면 dxf 경로
**처리**:
1. `sheet_title_extractor` 호출 → 도면명 후보
2. `sheet_name_matcher` 호출 → 정답지 시트 키
3. **시트 종류 분류** (정답지 기반):
   - 카운트 대상 (정답지에 부호 카운트 행 존재) → 카운트 측정
   - 길이 측정 소스 (정답지 라우팅 또는 측정 소스 도면 컬럼) → 길이 측정
   - 일람표 포함 시트 (규격 정답지에 부호 존재) → 규격 추출
4. 각 측정에 본선 함수 재사용:
   - 카운트: `baseline.compute_drawing(small_dxf_path, ...)` 시그니처 확인 후 호출. 정책 인자는 작은 도면용 최소화.
   - 길이: `length.baseline_length.measure_max_vertical(small_dxf_path, ...)` 또는 기존 함수
   - 규격: `spec_extractor.extract_from_dxf(small_dxf_path)`
5. 정답지와 비교 → PASS/FAIL

**출력**: `SmallDrawingResult` (2.1 참조)

### 작업 4 — 결과 통합 CSV

**파일**: `poc_v2/baseline2/export_baseline2_csv.py` (CLI)
**기능**: `sample_data/`의 작은 도면 dxf 전체를 입력으로 받아 파이프라인 호출, 2.2 형식의 CSV 생성.
**호출**:
```bash
python -m poc_v2.baseline2.export_baseline2_csv --drawings 도면4
python -m poc_v2.baseline2.export_baseline2_csv --drawings 도면4,도면5  # 다음 라운드
```

### 작업 5 — 시각화

**파일**: `poc_v2/baseline2/visualize_small.py`
**산출**: 작은 도면 1장당 HTML 1개 (2.3 참조)
**렌더링 모듈 재사용**: 기존 `visualize_specs.py` 또는 `visualize/` 디렉토리의 도형 렌더 함수 활용.

### 작업 6 — 회귀 테스트

**파일**: `poc_v2/baseline2/tests/test_baseline2_regression.py`
**검증 항목**:
1. **표제부 추출**: 도면4 작은 도면 5개에서 도면명 추출 성공
2. **시트명 매칭**: 도면4 5개 모두 정답지 시트와 매칭 (exact 또는 partial)
3. **카운트 PASS**: 도면4 1층 구조평면도 → SC1=14, SC2=4
4. **카운트 PASS**: 도면4 지붕층 구조평면도 → SC1=0, SC2=0 (중복 제거 검증 — 1층 14개를 또 14개 잡으면 FAIL)
5. **길이 PASS**: 도면4 종단면도횡단면도 → 9000mm
6. **규격 PASS**: SC1=H-350x175x7/11, SC2=H-194x150x6/9
7. **회귀 무영향**: `pytest -v poc_v2/tests/test_regression.py` → 14/16 유지
8. **회귀 무영향**: `pytest -v poc_v2/length/tests/test_length_regression.py` → 16/16 유지
9. **회귀 무영향**: `pytest -v poc_v2/length/tests/test_spec_regression.py` → 25/25 유지

### 작업 7 — 보고서

**파일**: `outputs/round_baseline2_보고서.md`
**내용**:
- 라운드 범위 (도면4까지) 명시
- 작업 1~6 결과 요약
- 도면4 5개 시트별 PASS/FAIL 표
- 표제부 추출률·매칭률·측정 PASS율
- 본선 무영향 확인 (회귀 3종 결과)
- 알려진 한계 (어떤 도면이 partial이고 왜)
- 다음 라운드 후보 (도면5 → 도면3 → 도면2 → 도면1 순)

---

## 5. 검증 우선순위 (단계적)

### 5.1 이번 라운드 (도면4만)

**도면4 작은 도면 5개**:
1. `도면4_1층구조평면도.dxf` — 카운트 SC1=14, SC2=4 / 규격 추출 / 길이 N/A
2. `도면4_지붕층구조평면도.dxf` — 카운트 0 (이중카운트 방지 검증 포인트)
3. `도면4_종단면도횡단면도.dxf` — 길이 9000mm
4. `도면4_종단면도.dxf` — cross-check (같은 9000)
5. `도면4_횡단면도.dxf` — cross-check (같은 9000)

이번 라운드 PASS 기준:
- 카운트: 1·2번 PASS
- 길이: 3번 PASS (4·5는 cross-check 검증용, FAIL이어도 라운드 PASS)
- 규격: 1번 PASS (SC1·SC2 규격 정답지 일치)

### 5.2 다음 라운드 후보 (이번 작업 범위 외)

도면5 → 도면3 → 도면2 → 도면1 순. 도면1은 1동/2동 분리 처리 때문에 마지막.

---

## 6. 본선 영향 점검

작업 종료 후 다음 회귀가 그대로 PASS 유지되어야 함:

```bash
pytest -v poc_v2/tests/test_regression.py                  # 14/16 (기존 2건 실패 무관)
pytest -v poc_v2/length/tests/test_length_regression.py    # 16/16
pytest -v poc_v2/length/tests/test_spec_regression.py      # 25/25
```

신규 모듈 추가만 있고 본선 코드/yaml 수정 0건이어야 함.

---

## 7. 제약사항

### 7.1 절대 금지
- 본선 모듈(`counter.py`, `baseline.py`, `length/baseline_length.py`, `spec_extractor.py`) 수정
- `config/symbol_rules.yaml`, `length_routing.yaml` 수정
- 정답지(`도면_정답지.xlsx`, `도면_길이_정답지.xlsx`) 수정
- 외부 라이브러리 추가 (DBSCAN, PaddleOCR, LLM 호출 등) — ezdxf + 표준 라이브러리 + openpyxl + 기존 시각화 라이브러리만
- 도면명 자동 매칭으로 풀리는 것을 yaml override에 미리 박기 (보편 룰 우선 원칙 위반)

### 7.2 우회 가능
- 본선 함수가 큰 도면 가정으로 동작 안 하면 → **신규 모듈 안에서 modelspace를 직접 다루는 wrapper** 작성. 본선 함수 코드는 그대로.
- 표제부 도면명 추출이 일부 도면에서 실패하면 → `sheet_name_overrides.yaml`에 그 케이스만 등록.

### 7.3 결정론 보장
- 모든 처리는 결정론적 (LLM·랜덤 0건)
- 동일 입력 → 동일 출력

---

## 8. 작업 순서 권고

1. **작업 0** — 기존 회귀 3종 베이스라인 기록
2. **작업 1** — 표제부 도면명 추출기 + 도면4 5개 파일에 직접 호출해 결과 확인
3. **작업 2** — 시트명 매칭 + 도면4 매칭 검증 (5/5 매칭되는지)
4. **작업 3** — 측정 파이프라인. 본선 함수 시그니처 먼저 확인하고 호출 wrapper 작성.
5. **작업 4** — CSV CLI
6. **작업 5** — 시각화 HTML
7. **작업 6** — 회귀 테스트 작성·실행, 본선 회귀 재실행
8. **작업 7** — 보고서

각 작업 종료 시 사용자에게 중간 보고. 특히:
- 작업 1·2 종료 후 매칭률 표 보고 (도면4 5/5인지)
- 작업 3 종료 후 측정 결과 보고 (카운트·길이·규격 정답 비교)
- 작업 6 종료 후 회귀 결과 보고

---

## 9. 산출물 체크리스트

이번 라운드 종료 시:

- [ ] `poc_v2/baseline2/sheet_title_extractor.py`
- [ ] `poc_v2/baseline2/sheet_name_matcher.py`
- [ ] `poc_v2/baseline2/small_drawing_pipeline.py`
- [ ] `poc_v2/baseline2/export_baseline2_csv.py`
- [ ] `poc_v2/baseline2/visualize_small.py`
- [ ] `poc_v2/baseline2/tests/test_baseline2_regression.py`
- [ ] `config/sheet_name_overrides.yaml` (필요시만)
- [ ] `outputs/round_baseline2_시트별_결과.csv` (도면4)
- [ ] `outputs/visualize/도면4_*.html` × 5
- [ ] `outputs/round_baseline2_보고서.md`
- [ ] 회귀 3종 PASS 유지 확인

---

**문서 끝.**
