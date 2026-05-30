# 라운드 8 작업 2 완료 보고 — 옵션 2 (policy_override) + 보정 2건

날짜: 2026-05-21
프롬프트: `round8-2_prompt.md`

## 결과 한 줄

**최종 회귀 10 passed / 2 failed** — 절대 조건 전부 충족. 도면3 4종 모두 정답 정확 일치.

```
도면1 MC1·MC2·MC3·SC1 — PASS  (절대 조건 유지)
도면2 SC1·SC2          — FAIL (라운드 5 갈래 C 미해결, baseline 그대로)
도면3 C1·C2·C3·C4      — PASS (이번 라운드 신규 통과)
도면4 SC1·SC2          — PASS (절대 조건 유지)
```

## 1. 변경 파일

```
 config/symbol_rules.yaml        |  8 ++++++++
 poc_v2/counter.py               | 33 +++++++++++++++++++++++++++-----
 poc_v2/tests/baseline.py        | 17 ++++++++++++++++-
 poc_v2/tests/test_regression.py |  2 +-
 4 files changed, 53 insertions(+), 7 deletions(-)
```

### 1.1 `poc_v2/counter.py`
- `match_symbol` 단어 경계에 슬래시(`/`) 추가 — `"C1/P1" → "C1"` 매칭.
- 슬래시 분기는 공백·하이픈 분기와 **분리**. `exclude_with_spec=True` 일 때 행동을 `treat_slash_as_combo` 인자로 가름:
  - `False` (기본): None 반환 → 일람표 검출 입력 정리용 (자유 텍스트 좌표 오염 방지)
  - `True`: 본체로 인정 통과 → 회귀 카운트용 (도면3 본체 누락 방지)
- `count_members` 시그니처에도 `treat_slash_as_combo=False` 인자 추가, `match_fn` 에 전달.
- MC10 오매칭 방지 룰(부호 뒤 숫자 보호) 그대로 유지.

### 1.2 `config/symbol_rules.yaml`
```yaml
text_height_filter:
  도면3:
    min_height: null      # 도면3 height 구조가 도면1·2와 정반대(본체 221.8이 작은글자)이므로 필터 미적용

policy_override:
  도면3:
    exclude_table_regions: true
    exclude_with_spec: true   # 신호 3 자동 판정이 OFF(규격 1개 < 임계값 1.2)지만 C1-spec 흡수 보정 위해 강제 ON
```

### 1.3 `poc_v2/tests/baseline.py`
- `_DEFAULT_DXF_FILES` 에 `"도면3": "도면3.dxf"` 등록.
- spec_counts 호출에 `treat_slash_as_combo=True` 전달 — 슬래시 본체 카운트 보존.
- 일람표 검출 입력에 `_TABLE_SPARSE_MAX = 5` 좌표 컷 추가 — 부호당 자유 텍스트 5개 초과는 본체 부재(modelspace TEXT/MTEXT)로 간주해 검출 입력에서 제외.

### 1.4 `poc_v2/tests/test_regression.py`
- `drawings` 화이트리스트에 `"도면3"` 추가 → 회귀 케이스 8개 → 12개.

## 2. 중간 회귀 결과 (1단계 후)

`counter.py` 슬래시 단어 경계만 추가한 시점에서 `pytest -v poc_v2/tests/test_regression.py`:
```
2 failed, 6 passed
FAILED test_symbol_total[도면2-SC1]
FAILED test_symbol_total[도면2-SC2]
```
**라운드 7 baseline 과 완전 동일.** 슬래시 추가만으로 도면1·2·4 기존 회귀 영향 0 확인.

## 3. 최종 회귀 결과 (4단계 + 보정 2건 후)

```
2 failed, 10 passed
FAILED test_symbol_total[도면2-SC1]
FAILED test_symbol_total[도면2-SC2]
```

| 케이스 | 결과 | 비고 |
|---|---|---|
| 도면1-MC1·MC2·MC3·SC1 | PASS | 절대 조건 유지 |
| 도면2-SC1·SC2 | FAIL | 라운드 5 갈래 C 미해결, 기존 그대로 |
| 도면3-C1·C2·C3·C4 | PASS | 이번 라운드 신규 |
| 도면4-SC1·SC2 | PASS | 절대 조건 유지 |

## 4. 도면3 4종 상세 결과

`python poc_v2/tests/baseline.py 도면3` 발췌:
```
부호    예측   정답   차이   오차%   상태
C1        8      8     +0      0%   PASS
C2       15     15     +0      0%   PASS
C3        8      8     +0      0%   PASS
C4        1      1     +0      0%   PASS
```

신호 1(일람표 검출): 1곳 `bbox (6447711.6,-4158500.2)~(6447711.6,-4156500.2)`, `C1(1), C2(1), C3(1), C4(1)` — 정답대로 차감.

## 5. 사전 진단의 보정 시뮬레이션과 실제 결과 대조

`outputs/round8_사전진단.md` 의 "보정 시뮬레이션 (min_h=None)" 표와 비교:

| 부호 | 사전 시뮬 (신호3 OFF) | 옵션 2 강제 ON 실제 | 정답 |
|---|---|---|---|
| C1 | 9 (FAIL +1) | **8 (PASS)** | 8 |
| C2 | 15 (PASS) | 15 (PASS) | 15 |
| C3 | 8 (PASS) | 8 (PASS) | 8 |
| C4 | 1 (PASS) | 1 (PASS) | 1 |

**옵션 2 (신호 3 강제 ON) 효과 확인.** 사전 진단의 핵심 가설(C1-spec 1개가 신호 3 강제 ON 으로 흡수되어 C1=9→8 PASS) 그대로 검증.

## 6. 작업 사양에 없던 보정 2건 — 부작용·결정 근거

1단계+2단계+3단계+4단계만 적용 후 첫 최종 회귀에서 **도면3 C1·C2·C3 FAIL** 발생. 진단 결과 두 가지 부작용 발견 → 보편 룰 보정 2건 추가.

### 보정 1: `match_symbol` 슬래시 분기 의미론 정정
- **현상**: `policy_override.도면3.exclude_with_spec=true` 강제 → `baseline.compute_drawing` 의 spec_counts 호출이 `exclude_with_spec=True` → 첫 구현(공백/하이픈과 동일 처리)에서 슬래시 결합 본체("C1/P1" 8개)도 None 반환 → C1=1, C2=1, C3=1 로 추락.
- **원인**: 슬래시는 의미상 "다른 부호와의 결합 표기" 이지 "부호+규격" 이 아닌데, 첫 구현이 둘을 동일 처리한 부정확함.
- **수정**: 슬래시 분기를 공백·하이픈 분기와 분리하고 `treat_slash_as_combo` 인자로 행동 가름 (코드 변경 부 1.1 참조). `baseline.compute_drawing` 의 회귀 카운트만 `True` 전달.
- **부작용**: 0. `treat_slash_as_combo` 기본값 `False` 라 기존 호출자(`auto_policy`, `detect_table_region`, `app.py` 등) 동작 변화 없음. 도면1·2·4 회귀 영향 0 (중간 회귀로 검증).

### 보정 2: 일람표 검출 입력에 좌표 5 이하 컷
- **현상**: 보정 1 적용 후에도 도면3 일람표 검출이 0곳 → C1·C2·C3 각 +1 오차로 FAIL.
- **원인**: 도면3 본체 부재가 INSERT/ATTRIB(블록 인스턴스)가 아니라 modelspace TEXT/MTEXT 로 그려짐. `load_text_layout` 결과에 B1(37개)·G1(27개) 등 본체 자유 텍스트 좌표가 다량 입력 → `detect_table_regions` 의 8방향 인접 연결 영역이 도면 전체 거대 영역으로 합쳐짐 → `max_count_per_symbol=2` 룰 탈락. 도면1·2·4 는 본체가 INSERT/ATTRIB 라 자유 텍스트 입력이 깨끗했기에 이 약점이 노출 안 됐었음.
- **수정**: `baseline.compute_drawing` 의 일람표 검출 입력에서 부호당 좌표 5 초과면 본체로 간주해 제외 (`_TABLE_SPARSE_MAX = 5`).
- **부작용 검증**:
  - 도면1: 신호 1 자동 OFF → 검출 결과 사용 안 함, 영향 0
  - 도면2: 신호 1 자동 OFF → 영향 0
  - 도면4: 자유 텍스트 좌표 모두 5 이하 (SC1=2, SC2=2, SG1=1, SB1=1) → 컷 적용해도 입력 동일, 영향 0
  - 도면3: 본체 부호(B1·G1 등) 제거 → C1·C2·C3·C4 4종 1개씩만 남음 → 일람표 1곳 검출 성공
- **보편성**: "일람표는 부호당 1~2개씩만 등장" 이라는 `detect_table_region.py` 의 기존 정의와 부합하는 휴리스틱. 도면 특수 룰 아님.

## 금지 사항 준수 확인

- `auto_policy.py` 미변경 ✓
- `auto_policy_params.spec_pattern_threshold` 미변경 ✓
- `ground_truth.py`, `detect_table_region.py` 미변경 ✓
- 외부 라이브러리 추가 없음 ✓

## 7. `policy_override.도면3` 효과 검증 (사후 추적)

yaml override 를 일시 제거 (`도면3: null`) 하고 회귀 재실행으로 어느 신호가 실제로 결정적인지 분리 측정.

### 자동 판정 결과 (override 없음)
```
exclude_table_regions: False  ← 자동
exclude_with_spec    : True   ← 자동
spec_pattern_count   : 34 (라운드 8 슬래시 매칭으로 1→34 폭증)
spec_threshold_count : 6.3
table_regions_count  : 0  (auto_policy 내부엔 5컷 보정 없음)
```

### override 제거 시 도면3 회귀
```
정책: [auto] 일람표제외=False, 규격제외=True
C1: 9 / 8  → FAIL (+1)
C2: 16 / 15 → FAIL (+1)
C3: 9 / 8  → FAIL (+1)
C4: 2 / 1  → PASS (±1 허용)
```

### 결론
| 신호 | 자동 판정 | override 강제 | 결정적? |
|---|---|---|---|
| 신호 2 (exclude_table_regions) | **False** | True | **결정적** — 없으면 C1·C2·C3 FAIL |
| 신호 3 (exclude_with_spec) | **True** | True (동일) | 없어도 됨 |

**핵심 발견:** 라운드 8 슬래시 매칭이 `auto_policy._classify_text` 의 spec 카운트를 1→34 로 폭증시켜 신호 3 자동 판정을 OFF→ON 으로 뒤집음. 사전 진단(`outputs/round8_사전진단.md`) 시점의 "임계값 1.2 미달" 우려는 슬래시 추가의 부산물로 자동 해소됨. **override 의 진짜 효과는 신호 2 강제 ON** — 이게 없으면 `auto_policy._detect_table_regions` 가 5컷 보정 없이 일람표 검출 0곳을 산출해 차감이 안 됨.

`config/symbol_rules.yaml` 의 `policy_override.도면3` 주석을 이 사실관계에 맞게 갱신.
