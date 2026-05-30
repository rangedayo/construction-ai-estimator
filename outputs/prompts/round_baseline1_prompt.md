# 라운드 베이스라인-1: 단위중량 통일 함수

## 0. TL;DR

| 항목 | 내용 |
|---|---|
| **목표** | 단위중량 = 단면적 × 밀도(7,850 kg/m³) 한 식으로 통일한 신규 모듈 작성 |
| **신규 파일** | `poc_v2/qto/unit_weight_calc.py`, `poc_v2/qto/tests/test_unit_weight_calc.py` |
| **본선 영향** | 0건. 기존 회귀 14/16 + 16/16 + 25 PASS 유지 |
| **검증** | 정답지 18종 H형강 모두 산출 + KS표값과 ±5% 안 일치 |
| **라이브러리** | 표준 라이브러리 + pytest (ezdxf 불요) |

---

## 1. 배경 — 멘토 답변

질문 1·2에 대한 멘토님 답이 같은 결론으로 모임:

> "KS 표 룩업은 복잡해서 미리 계산해둔 결과일 뿐, 원리는 단면적×밀도. 표준이든 비표준이든 단면적만 구하면 7,850 kg/㎥ 한 값을 곱해서 단위중량."

함의:
- 보류 중이던 `config/unit_weight_table.yaml` 룩업 분기는 폐기 (단, 검증 참조용으로는 보존)
- 비표준 단면(현장제작 `600x407x20x35` 등)도 같은 식 — 분기 없음
- yaml 대신 함수, 룩업 대신 계산

H형강 단면적 공식 (위 플랜지 + 아래 플랜지 + 웹 세 직사각형):

```
A(mm²) = B × tf × 2 + tw × (H − tf × 2)
W(kg/m) = A(m²) × 7,850
```

검증 예시:
- `H-588x300x12/20` → A = 300×20×2 + 12×(588−40) = **18,576 mm²** → **145.8 kg/m**
- KS표값 151.0 kg/m — 차이 +3.5% (모서리 곡률 포함분, 무시 수준)

---

## 2. 신규 모듈

### 2.1 위치

`poc_v2/qto/` 새 패키지 신설 (베이스라인 라운드 산출물 보관처).

- `poc_v2/qto/__init__.py`
- `poc_v2/qto/unit_weight_calc.py`
- `poc_v2/qto/tests/__init__.py`
- `poc_v2/qto/tests/test_unit_weight_calc.py`

기존 `poc_v2/length/unit_weight.py`(보류)와 헷갈리지 않게 새 패키지로 분리. 보류 코드는 건드리지 않음.

### 2.2 함수 시그니처

```python
# poc_v2/qto/unit_weight_calc.py

STEEL_DENSITY_KG_PER_M3 = 7850.0

def parse_h_section(spec: str) -> tuple[float, float, float, float]:
    """규격 문자열 → (H, B, tw, tf) mm 단위 4튜플.
    
    내부에서 spec_extractor.normalize_spec()으로 정규화 후 파싱.
    'H-588x300x12/20', 'H 350x175x7/11', '600x407x20x35' 등 변형 모두 처리.
    
    Raises
    ------
    ValueError: 4세그먼트 파싱 실패, 또는 H형강 외 단면(파이프·앵글 등).
    """

def section_area_mm2(H: float, B: float, tw: float, tf: float) -> float:
    """H형강 4세그먼트 단면적 = B×tf×2 + tw×(H − tf×2)."""

def unit_weight_kg_per_m(
    spec: str,
    density: float = STEEL_DENSITY_KG_PER_M3,
) -> float:
    """규격 문자열 → kg/m. 내부에서 정규화·파싱·계산."""

def compute_section(spec: str) -> dict:
    """베이스라인 csv 컬럼 채우기용 — 한 번에 H·B·tw·tf·area·weight 반환.
    
    Returns
    -------
    {
        'spec_normalized': 'H-588x300x12x20',
        'H_mm': 588, 'B_mm': 300, 'tw_mm': 12, 'tf_mm': 20,
        'area_mm2': 18576.0,
        'unit_weight_kg_per_m': 145.82,
    }
    """
```

### 2.3 정규화는 재사용

`poc_v2.length.spec_extractor.normalize_spec()`을 import해 그대로 사용 (슬래시→x, 공백 제거, H- 접두사 처리 등 이미 들어 있음). 신규 모듈은 정규화 결과만 파싱.

### 2.4 엣지 케이스

| 입력 | 동작 |
|---|---|
| `H-588x300x12/20` (슬래시) | normalize_spec이 슬래시→x 변환 후 4세그먼트 파싱 |
| `H 350x175x7/11` (공백) | 정규화 후 동일 처리 |
| `600x407x20x35` (H 접두사 없음, 현장제작) | 정상 — 4세그먼트만 맞으면 H형강 가정 |
| `□-100x100x2.3` (파이프) | ValueError — 본 라운드 범위 외 |
| `L-50x6` (앵글) | ValueError — 범위 외 |
| `ø16` (원형 철근) | ValueError — 범위 외 |
| 3세그먼트 / 5세그먼트 | ValueError |

---

## 3. 회귀 테스트 — sanity check

### 3.1 파일

`poc_v2/qto/tests/test_unit_weight_calc.py`

### 3.2 검증 항목

1. **단위 테스트** — 한 케이스 수동 계산값과 정확 일치:
   - `H-588x300x12x20` → area 18,576, weight 145.82 (±0.01)
2. **정답지 18종 모두 산출** — `outputs/round_length4_보고서.md` 또는 정답지에서 추출한 18종 모든 H형강에 대해 `unit_weight_kg_per_m()`이 ValueError 없이 양수 반환.
3. **KS표 sanity check** — `config/unit_weight_table.yaml`을 **참조 전용**으로 읽어, 18종 각각 계산값과 KS표값의 상대오차가 ±5% 안인지 확인. 5% 넘는 항목이 있으면 표를 콘솔에 찍고 실패시킴.
4. **비표준 단면 산출** — `H-600x407x20x35` 등 KS표 외 단면도 정상 값 반환 (KS표 비교는 항목 없으니 sanity check 대상에서만 제외).
5. **엣지 케이스** — 파이프(`□-100x100x2.3`), 앵글(`L-50x6`)에 대해 ValueError raise 확인.

### 3.3 콘솔 출력 — 18종 비교 표

테스트가 마지막에 다음 형식 표를 출력 (pytest -v -s로 확인 가능):

```
규격                       계산 A(mm²)   계산 W(kg/m)   KS표(kg/m)   차이%
H-588x300x12x20            18,576.0      145.82         151.0        +3.5
H-200x200x8x12             6,353.0       49.87          49.9         +0.1
...
```

5% 안에 다 들어오면 PASS. 벗어난 게 있으면 그 행을 강조 표시.

---

## 4. 제약

### 4.1 본선 무수정 (절대 조건)

읽기만, 수정 0:
- `poc_v2/counter.py`, `poc_v2/auto_policy.py`, `poc_v2/tests/baseline.py`, `poc_v2/tests/ground_truth.py`, `poc_v2/tests/detect_table_region.py`, `poc_v2/tests/test_regression.py`
- `poc_v2/length/measure.py`, `baseline_length.py`, `ground_truth_length.py`, `routing.py`, `spec_extractor.py`, `ground_truth_spec.py`, `visualize_*.py`, `export_spec_csv.py`
- `poc_v2/length/tests/*`
- `config/symbol_rules.yaml`, `length_routing.yaml`, `dedup_policy.yaml`

### 4.2 보류 코드 무수정

- `poc_v2/length/unit_weight.py` — 보류 유지. 신규 모듈은 옆에 새로 만드는 것이지 이걸 갈아끼우는 게 아님.
- `poc_v2/length/total_weight.py` — 보류 유지.
- `config/unit_weight_table.yaml` — 보류. 단 신규 테스트의 KS표 sanity check에서 **참조 전용**으로 읽기만 함 (yaml 내용 수정 금지).

### 4.3 라이브러리

- 표준 라이브러리 + pytest + PyYAML(yaml 로드용).
- ezdxf·plotly·openpyxl 불요.
- LLM·외부 API 불요.

---

## 5. 회귀 미영향 확인 (필수)

신규 모듈 추가만이므로 기존 회귀에 영향 0이어야 함. 작업 완료 후 다음 4개 모두 PASS 확인:

```bash
pytest -v poc_v2/tests/test_regression.py                  # 14/16
pytest -v poc_v2/length/tests/test_length_regression.py    # 16/16
pytest -v poc_v2/length/tests/test_spec_regression.py      # 25 passed
pytest -v poc_v2/qto/tests/test_unit_weight_calc.py        # 신규 (전부 PASS)
```

---

## 6. 출력 요청 (작업 보고 형식)

다음 순서로 보고:

1. **신설 파일 목록** + 각 함수 시그니처 한 줄 요약
2. **단위 테스트 결과** — H-588x300x12x20 한 케이스 수동 검산값과 일치 확인
3. **18종 비교 표** — 위 3.3 형식. KS표값 ±5% 안 PASS 여부
4. **비표준 단면 산출 결과** — H-600x407x20x35 등 (KS표 없는 항목) 값 출력
5. **위 4개 pytest 결과** — 본선 회귀 무영향 확인
6. **알려진 한계** — 예: H형강 외 단면 미지원, 본 라운드 범위 외임을 명시

---

## 7. 다음 라운드 후보 (작업 범위 외, 참고용)

- **개수 중복 판별** — 멘토 원칙 "평면도 한 장에서만 카운트" 코드화
- **콘크리트 기초팀 분할** — F·MF·HD·SR·SBR 본격 적산 (멘토님 새 도면 받은 뒤)
- **지붕 15도 가정 활용** — 도면1 1동 길이 보류 해결 (평면도 좌표 + 삼각함수)

본 라운드 범위는 단위중량 함수까지만.

---

**문서 끝.**