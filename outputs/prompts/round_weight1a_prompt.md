# 라운드 중량-1a 본작업 명세서 — 도면4 dedup 라우팅 + 총중량 CSV

> **작성 목적**: PoC 본 목표(기둥 총중량 CSV 산출)의 **첫 사이클을 도면4 한 장에서 완성**.
> dedup_routing.yaml 스키마가 실제로 작동하는지 + count/length/spec 결합 곱셈 흐름이
> 끝까지 도는지 검증. **도면1·2·3·5 는 다음 라운드(1b)** 에서 동일 흐름으로 확장.
>
> **읽는 순서**: 0 → 1 → 2 → (제약 7 먼저) → 3 → 4 → 5 → 6 → 8 → 9

---

## 0. TL;DR

| 항목 | 내용 |
|---|---|
| **목표** | 도면4 기둥(SC1·SC2) 총중량 산출 → CSV. dedup yaml 스키마 검증 |
| **핵심 입력** | 신규 `config/dedup_routing.yaml` (이미 사람이 작성해 두었음, 도면4 섹션만) |
| **핵심 출력** | `outputs/round_weight1a_도면4_총중량.csv` (도면4 기둥 합계 ≈ 7,350 kg) |
| **신규 모듈** | `poc_v2/qto/dedup_loader.py`, `poc_v2/qto/weight_pipeline.py`, `poc_v2/qto/export_weight_csv.py` |
| **재사용** | baseline-1 `unit_weight_calc`, `length_routing.yaml`, `symbol_rules.yaml`, baseline-2/6 측정 결과 |
| **본선 영향** | `counter.py` / `baseline.py` / `length/baseline_length.py` / `spec_extractor.py` / 모든 yaml 무수정 |
| **회귀 안전망** | 기존 9종(190 PASS / 2 known fail) 전부 유지 |
| **이번 범위** | 도면4 기둥만. 보·다른 도면 다음 라운드 |

---

## 1. 배경

### 1.1 PoC 본 목표와 이번 라운드 위치

PoC 목표: 도면 5장에서 **기둥 총중량 CSV** 산출.
- 측정 3종(카운트·길이·규격) — baseline-1~7 에서 모두 PASS
- 분리본 routing 일반화 — baseline-7 완료
- **곱셈·CSV 산출 단계 — 이번 라운드**

곱셈 = `개수 × 길이 × 단위중량`. 그런데 같은 (도면, 부호) 가 여러 시트에 등장하는
중복 함정이 있어(규격-1 보고서 §4 참조), "어느 시트 값을 칠지" 를 결정해야
곱셈이 가능하다. → **dedup_routing.yaml 신설**.

### 1.2 도면4 를 첫 사이클로 고른 이유

도면4 는 dedup 결정이 **자명한** 케이스 (정답지 기준):
- 카운트 출처: 1층 구조평면도 (SC1=14, SC2=4)
- 지붕층 구조평면도는 정답지상 "분석 대상=보" → 기둥 카운트 0
- 일람표: 1층 구조평면도 시트 안에 있음 → spec_from 도 동일
- 보 부재(SG·SB) 는 이번 라운드 범위 외

도면1(주심도 vs 부호도 중복) 같은 복잡한 dedup 케이스 전에 **자명한
케이스로 스키마와 곱셈 흐름이 작동하는지 먼저 검증**한 뒤 1b 라운드에서 확장한다.

### 1.3 사용자 작성 `dedup_routing.yaml` (도면4 섹션, 이미 저장됨)

```yaml
도면4:
  기둥:
    SC1:
      count_from: "1층 구조평면도"
      spec_from: "1층 구조평면도"
    SC2:
      count_from: "1층 구조평면도"
      spec_from: "1층 구조평면도"
```

필드 의미:
- `count_from` : 카운트를 가져올 시트 (= 본체 평면도/주심도)
- `spec_from`  : 규격을 가져올 시트 (= 일람표가 있는 시트)
- 길이 라우팅은 `length_routing.yaml` 에서 별도 관리.
- 단위중량은 spec → 단면적 × 7,850 kg/m³ 로 baseline-1 `unit_weight_calc` 가 자동 계산.

---

## 2. 목표 (산출물)

### 2.1 도면4 총중량 CSV

`outputs/round_weight1a_도면4_총중량.csv` 형식:

```csv
도면,부재종류,부호,개수,길이_mm,규격,단위중량_kg_per_m,총중량_kg,count_from,spec_from,length_from
도면4,기둥,SC1,14,9000,H-350x175x7/11,<calc>,<calc>,1층 구조평면도,1층 구조평면도,종단면도·횡단면도
도면4,기둥,SC2,4,9000,H-194x150x6/9,<calc>,<calc>,1층 구조평면도,1층 구조평면도,종단면도·횡단면도
도면4,기둥,합계,18,-,-,-,<sum>,-,-,-
```

기대 값 (단위중량 baseline-1 단면적 × 7,850 식 기준):
| 부호 | 개수 | 길이(m) | 단위중량(kg/m) | 총중량(kg) |
|---|---|---|---|---|
| SC1 | 14 | 9.0 | ~48.3 (단면적 6,146 mm²) | ~6,086 |
| SC2 | 4 | 9.0 | ~30.0 (단면적 3,816 mm²) | ~1,082 |
| 합계 | 18 | | | **~7,170** |

단면적 식이 KS D 3502 표 값(필렛 반영) 대비 약 -2~3% 작게 나옴 — 알려진 차이이고
이번 라운드 fix 범위 아님. 검증 허용 오차 ±5% (단위중량 식 차이 흡수).

### 2.2 dedup 스키마 검증

곱셈이 끝까지 돌면서 스키마가 **충분/부족** 했는지 보고서에 기록:
- 필드 부족: 새 필드 필요했다면 명시 (예: 동·구역 분리 필요 시)
- 명명 모호: 시트명 매칭이 ambiguous 했던 경우 기록
- 1b 라운드 전에 스키마 확장 필요한 것 목록화

---

## 3. 설계 원칙

### 3.1 본선 무수정

- `counter.py` / `baseline.py` / `length/baseline_length.py` / `spec_extractor.py` 무수정.
- 기존 yaml (`symbol_rules.yaml`, `length_routing.yaml`) 무수정.
- 신규 yaml (`dedup_routing.yaml`) 은 사람이 작성, 코드는 읽기만.
- baseline-1 `unit_weight_calc` 는 그대로 호출 (수정 안 함).

### 3.2 측정만, 결정 안 함 — 코드는 yaml만 보고 결정론

- 코드는 dedup_routing.yaml 이 지시한 시트에서만 측정값을 채택.
- 어느 시트가 본체인지 판단은 yaml(사람) 의 일.
- LLM 호출·랜덤 0건. 동일 입력 → 동일 출력.

### 3.3 회귀 안전망 — 절대 조건

- 기존 9종 회귀 (190 PASS / 2 known fail) 모두 PASS 유지.
- 곱셈 모듈은 측정 결과를 **소비** 만 하므로 측정 모듈 회귀에 영향 없어야 함.

---

## 4. 작업

### 작업 0 — 회귀 9종 기록 (필수 선행)

곱셈·CSV 모듈 추가 전·후 회귀 결과 비교용 baseline 기록.

```bash
pytest -v poc_v2/tests/test_regression.py                       # 14/16
pytest -v poc_v2/length/tests/test_length_regression.py         # 16/16
pytest -v poc_v2/length/tests/test_spec_regression.py           # 25/25
pytest -v poc_v2/baseline2/tests/test_baseline2_regression.py   # 19/19 (도면4)
pytest -v poc_v2/baseline2/tests/test_baseline3_regression.py   # 33/33 (도면5)
pytest -v poc_v2/baseline2/tests/test_baseline4_regression.py   # 19/19 (도면3)
pytest -v poc_v2/baseline2/tests/test_baseline5_regression.py   # 16/16 (도면2)
pytest -v poc_v2/baseline2/tests/test_baseline6_regression.py   # 48/48 (도면1)
pytest -v poc_v2/baseline2/tests/test_baseline7_regression.py   # ?/? (분리본)
```

### 작업 1 — dedup_routing.yaml 로더 모듈

**파일**: `poc_v2/qto/dedup_loader.py` (신규)

```python
@dataclass
class DedupRoute:
    drawing: str
    member_kind: str   # "기둥" | "보" (이번 라운드는 "기둥"만)
    symbol: str
    count_from: str    # 시트명
    spec_from: str     # 시트명

def load_dedup_routing(path: str) -> list[DedupRoute]:
    """config/dedup_routing.yaml 을 파싱해 평면 리스트 반환."""
```

검증:
- 시트명이 빈 문자열·None 일 때 명확한 에러
- 같은 (도면, 부호) 가 여러 번 등장 시 에러 (사람 실수 잡기)
- 도면4 만 있는 yaml 도 정상 로드

### 작업 2 — weight_pipeline 모듈

**파일**: `poc_v2/qto/weight_pipeline.py` (신규)

```python
@dataclass
class WeightRow:
    drawing: str
    member_kind: str
    symbol: str
    count: int
    length_mm: float
    spec_normalized: str
    unit_weight_kg_per_m: float
    total_weight_kg: float
    count_from_sheet: str
    spec_from_sheet: str
    length_from_sheet: str

def compute_weight_for_drawing(
    drawing: str,
    dedup_routes: list[DedupRoute],
    *,
    count_provider,    # (drawing, sheet, symbol) → int
    length_provider,   # (drawing, symbol) → (mm, source_sheet)
    spec_provider,     # (drawing, sheet, symbol) → spec_normalized
    unit_weight_fn,    # spec_normalized → kg/m  (baseline-1 unit_weight_calc)
) -> list[WeightRow]:
    """도면 한 장의 부호별 총중량 행 생성."""
```

호출 순서:
1. dedup_routes 에서 도면4 / 기둥 / SC1 행을 꺼냄
2. count_provider(도면4, "1층 구조평면도", "SC1") → 14
3. length_provider(도면4, "SC1") → (9000, "종단면도·횡단면도")
4. spec_provider(도면4, "1층 구조평면도", "SC1") → "H-350x175x7/11"
5. unit_weight_fn("H-350x175x7/11") → 48.3 (예시값)
6. 총중량 = 14 × 9.0 × 48.3 = 6,086

count/length/spec provider 는 기존 baseline-2/6 모듈 / `length_routing` /
`spec_extractor` 결과를 얇게 감싸는 어댑터로 구현.

### 작업 3 — 도면4 산출 + CSV 출력

**파일**: `poc_v2/qto/export_weight_csv.py` (신규 CLI)

```bash
python -m poc_v2.qto.export_weight_csv --drawing 도면4 \
    --output outputs/round_weight1a_도면4_총중량.csv
```

출력 형식 §2.1 참조. 부호별 행 + 합계 행.

### 작업 4 — 정답지 비교 검증

`도면_정답지.xlsx` / `도면_길이_정답지.xlsx` 의 도면4 행과 비교:

| 검증 항목 | 정답값 | 산출값 | 허용 오차 |
|---|---|---|---|
| SC1 카운트 | 14 | 14 | 정확 일치 |
| SC2 카운트 | 4 | 4 | 정확 일치 |
| SC1 길이 | 9000 mm | 9000 mm | ±50 mm |
| SC2 길이 | 9000 mm | 9000 mm | ±50 mm |
| SC1 규격 | H-350x175x7/11 | (추출값) | 정규화 후 정확 일치 |
| SC2 규격 | H-194x150x6/9 | (추출값) | 정규화 후 정확 일치 |
| SC1 총중량 | (KS 표 기준 ~6,250) | (계산값) | ±5% |
| SC2 총중량 | (KS 표 기준 ~1,100) | (계산값) | ±5% |
| 도면4 합계 | (KS 표 기준 ~7,350) | (계산값) | ±5% |

오차 ±5% 사유: baseline-1 단면적 식이 KS D 3502 표 값(필렛 반영) 대비 약 -2~3%.
이 차이는 알려진 한계이고 이번 라운드 fix 범위 아님. 단면적 식 정확화는 별도 라운드.

### 작업 5 — 회귀 9종 무영향 확인

작업 0 결과와 보완 후 결과 비교. 모든 PASS 수 불변이어야 함.

특히 주의:
- `unit_weight_calc` 호출이 측정 모듈에 부수효과 없는지
- dedup_loader 실패가 측정 회귀에 영향 안 미치는지

### 작업 6 — 회귀 테스트 신규

**파일**: `poc_v2/qto/tests/test_weight1a_regression.py` (신규)

검증 항목:
1. dedup_loader 정상 동작 (도면4 2행 로드)
2. weight_pipeline 도면4 산출 (SC1·SC2 2행 + 합계)
3. 단위중량 계산: SC1 약 48±5% kg/m, SC2 약 30±5% kg/m
4. 총중량: SC1 ≈ 6,086 ±5%, SC2 ≈ 1,082 ±5%, 합계 ≈ 7,170 ±5%
5. CSV 파일 형식 검증 (헤더·행 수·합계 행 위치)
6. **회귀 무영향**: 기존 9종 PASS 수 불변 (호출 안 함, 본 테스트만)

### 작업 7 — 보고서

**파일**: `outputs/round_weight1a_보고서.md`

내용:
- 라운드 범위 (도면4 한 장, 기둥만)
- dedup_routing.yaml 스키마 동작 결과
- 도면4 산출값 vs 정답지 비교 표
- 단위중량 계산식 vs KS 표 차이 (-2~3%) 명시
- **스키마 검토 결과**: 도면4 에서 부족했던 필드 목록 (1b 라운드 입력)
- 회귀 9종 무영향 확인
- 알려진 한계 / 다음 라운드(1b)

---

## 5. 검증 우선순위

1. **작업 0** — 회귀 9종 baseline 기록
2. **작업 1** — dedup_loader 단위 테스트로 yaml 파싱 정확성 검증
3. **작업 2~3** — weight_pipeline 흐름이 도면4 한 장에서 끝까지 도는지
4. **작업 4** — 정답지 비교 (이번 라운드 핵심 검증)
5. **작업 5** — 회귀 9종 무영향 (절대 조건)
6. **작업 6~7** — 회귀 테스트 + 보고서

작업 4 에서 정답지와 ±5% 안 맞으면 단면적 식·곱셈·중간 측정값 중 어디가 어긋났는지
보고만 하고 fix 는 다음 라운드. **이번 라운드는 "흐름이 끝까지 도는지" 검증이 우선.**

---

## 6. 본선 영향 점검

작업 종료 후 회귀 10종 모두 PASS 유지:

```bash
pytest -v poc_v2/tests/test_regression.py                       # 14/16 (불변)
pytest -v poc_v2/length/tests/test_length_regression.py         # 16/16
pytest -v poc_v2/length/tests/test_spec_regression.py           # 25/25
pytest -v poc_v2/baseline2/tests/test_baseline2_regression.py   # 19/19
pytest -v poc_v2/baseline2/tests/test_baseline3_regression.py   # 33/33
pytest -v poc_v2/baseline2/tests/test_baseline4_regression.py   # 19/19
pytest -v poc_v2/baseline2/tests/test_baseline5_regression.py   # 16/16
pytest -v poc_v2/baseline2/tests/test_baseline6_regression.py   # 48/48
pytest -v poc_v2/baseline2/tests/test_baseline7_regression.py   # 이전 라운드 결과
pytest -v poc_v2/qto/tests/test_weight1a_regression.py          # 신규
```

---

## 7. 제약사항

### 7.1 절대 금지

- 본선 모듈 수정 (`counter.py` / `baseline.py` / `length/*` / `spec_extractor.py`)
- 기존 yaml 수정 (`symbol_rules.yaml`, `length_routing.yaml`)
- 정답지 수정
- baseline-1 `unit_weight_calc` 내부 수정 (호출만)
- LLM·VLM·랜덤·외부 네트워크 호출
- 보류 코드(`poc_v2/length/total_weight.py` / `unit_weight.py` / `unit_weight_table.yaml`)
  재활성화 — baseline-1 `unit_weight_calc` 만 사용

### 7.2 허용 (조건부)

- 신규 yaml (`config/dedup_routing.yaml`) — 이번 라운드 신규 파일이라 무수정 원칙 무관
- 신규 모듈 (`poc_v2/qto/dedup_loader.py`, `weight_pipeline.py`, `export_weight_csv.py`)
- 신규 출력 (`outputs/round_weight1a_*`, `outputs/visualize/도면4_총중량.html` 선택)

### 7.3 결정론

LLM·랜덤 0건. 동일 입력 → 동일 출력. 모든 부동소수 비교는 명시적 허용오차.

---

## 8. 작업 순서

1. **작업 0** — 회귀 9종 baseline 기록
2. **작업 1** — dedup_loader
3. **작업 2** — weight_pipeline (count/length/spec provider 어댑터 포함)
4. **작업 3** — export_weight_csv CLI
5. **작업 4** — 정답지 비교
6. **작업 5** — 회귀 9종 무영향
7. **작업 6** — 회귀 테스트 신규
8. **작업 7** — 보고서

**중간 보고 권장 시점**:
- 작업 2 끝난 후 (스키마 동작 확인, 1b 전에 스키마 확장 필요한지 사용자 검토)
- 작업 4 끝난 후 (정답지 비교 결과)
- 작업 7 끝난 후 (커밋 가능 상태)

---

## 9. 알려진 한계 / 다음 라운드(1b) 후보

### 이번 라운드에서 다루지 않는 것

- **도면1·2·3·5** — 다음 라운드(1b)에서 dedup_routing.yaml 확장 + 동일 흐름 적용
- **보 부재** (SG·SB 등) — 1b 이후 별도 라운드
- **단면적 식 정확화** — KS D 3502 표 값과 ±2~3% 차이. 별도 라운드에서 필렛 반영
  또는 KS 표 룩업으로 전환 검토
- **도면2 SC1·SC2 카운트** — 데이터 한계, 정답지 override 처리(1b 라운드에서 yaml 필드 추가)
- **LLM 라우팅** — 사람이 yaml 손으로 채우는 단계. LLM 자동 생성은 별도 큰 라운드

### 1b 라운드 미리보기

- dedup_routing.yaml 확장 (도면1·2·3·5)
- 도면1 by_section 구조 추가 (1동·2동)
- 도면2 count_override 필드 추가 (데이터 한계 격리)
- 5장 통합 총중량 CSV → **PoC 본 deliverable**

---

**문서 끝.**
