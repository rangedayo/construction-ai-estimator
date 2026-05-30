# 라운드 중량-1b 본작업 명세서 — 5장 통합 dedup 라우팅 + 기둥 총중량 CSV

> **작성 목적**: PoC 본 목표(도면 5장 기둥 총중량 CSV) **완성 라운드**.
> 라운드 중량-1a 에서 도면4 한 장 흐름이 검증됐고, 1b 는 동일 흐름을
> 도면1·2·3·5 로 확장. dedup_routing.yaml 스키마 확장 2종(`by_section`,
> `count_override`) 도입.
>
> **읽는 순서**: 0 → 1 → 2 → (제약 7 먼저) → 3 → 4 → 5 → 6 → 8 → 9

---

## 0. TL;DR

| 항목 | 내용 |
|---|---|
| **목표** | 5장 통합 기둥 총중량 CSV → **PoC 본 deliverable** |
| **핵심 입력** | 확장된 `config/dedup_routing.yaml` (이미 사람이 작성, 5장 전체 포함) |
| **핵심 출력** | `outputs/round_weight1b_5장_총중량.csv` + 보고서 |
| **스키마 확장** | `by_section` (도면1 동별), `skip` (도면1 1동), `count_override` (도면2) |
| **모듈 수정** | `dedup_loader.py` (스키마 확장), `weight_pipeline.py` (skip/override 분기) |
| **본선 영향** | `counter.py` / `baseline.py` / `length/*` / `spec_extractor.py` / 기존 yaml 무수정 |
| **회귀 안전망** | 기존 10종(190+13 PASS / 2 known fail) 전부 유지 |
| **이번 범위** | 5장 통합 기둥만. 보·다른 부재 다음 라운드 |

---

## 1. 배경

### 1.1 라운드 중량-1a 결과 (도면4 한 장)

- 도면4 SC1=14 × 9000mm × 48.25 kg/m = 6,079 kg
- 도면4 SC2=4 × 9000mm × 29.48 kg/m = 1,061 kg
- 도면4 합계 = **7,140 kg** (KS 표 ~7,350 대비 -2.9%, ±5% 안)
- 신규 13 PASS / 회귀 무영향

→ dedup yaml + count/length/spec 결합 + 단위중량 자동 계산 흐름이
도면4 자명 케이스에서 작동 확인.

### 1.2 1b 가 확장하는 것

| 도면 | 신규 처리 |
|---|---|
| 도면1 1동 | `skip: true` — 길이 정보 부재 (정답지 명시), 산출 대상에서 제외 |
| 도면1 2동 | `by_section` — 동·구역 키 추가. 주심도가 본체 (사용자 결정) |
| 도면2 | `count_override` — 측정 데이터 한계(baseline-5 split-TEXT)로 정답값 격리 |
| 도면3·5 | 단순 추가 — 도면4 패턴 그대로 (단일 시트) |

### 1.3 사용자 작성 확장 yaml (5장 전체, 이미 저장됨)

핵심 부분만 발췌:

```yaml
도면1:
  by_section:
    1동:
      skip: true
      skip_reason: "1동에 골구도/입면도/단면도 시트 부재로 기둥 길이 산출 불가"
    2동:
      기둥:
        MC1: { count_from: "(2동)기둥주심도", spec_from: "(2동)기둥주심도" }
        MC2: { count_from: "(2동)기둥주심도", spec_from: "(2동)기둥주심도" }
        MC3: { count_from: "(2동)기둥주심도", spec_from: "(2동)기둥주심도" }
        SC1: { count_from: "(2동)기둥주심도", spec_from: "(2동)기둥주심도" }

도면2:
  기둥:
    SC1:
      count_override: 10
      spec_from: "가,나,다동 1층 구조평면도"   # 추정 — 검증 필요
    SC2:
      count_override: 4
      spec_from: "가,나,다동 1층 구조평면도"

도면3:
  기둥:
    C1: { count_from: "1층바닥 구조평면도", spec_from: "1층바닥 구조평면도" }
    # ... C2·C3·C4 동일 패턴

도면4: (1a 와 동일)

도면5:
  기둥:
    C1: { count_from: "1층바닥 구조평면도", spec_from: "1층바닥 구조평면도" }
    # ... C2·C3·C4 동일 패턴
```

### 1.4 정답지 기준 기대 총중량 (단위중량 baseline-1 식 기준)

| 도면 | 동 | 부호 | 개수 | 길이(mm) | 규격 | 단위중량(kg/m)* | 총중량(kg)* |
|---|---|---|---|---|---|---|---|
| 도면1 | 1동 | (skip) | - | - | - | - | - |
| 도면1 | 2동 | MC1 | 15 | 6000 | H-400x200x8/13 | ~64.3 | ~5,790 |
| 도면1 | 2동 | MC2 | 4 | 6000 | H-440x300x11/18 | ~119.7 | ~2,870 |
| 도면1 | 2동 | MC3 | 2 | 6000 | H-250x250x9/14 | ~70.6 | ~850 |
| 도면1 | 2동 | SC1 | 4 | 6000 | H-300x150x6.5/9 | ~35.6 | ~850 |
| 도면2 | - | SC1 | 10 (override) | 7700 | H-250x125x6/9 | ~28.6 | ~2,200 |
| 도면2 | - | SC2 | 4 (override) | 7700 | H-200x100x5.5/8 | ~20.5 | ~630 |
| 도면3 | - | C1·C2·C3·C4 | 32 | (정답지 참조) | (정답지 참조) | (계산) | (계산) |
| 도면4 | - | SC1·SC2 | 18 | 9000 | (1a 검증값) | (1a) | **7,140** |
| 도면5 | - | C1·C2·C3·C4 | 20 | (정답지 참조) | (정답지 참조) | (계산) | (계산) |
| | | | | | | **총합** | (산출) |

`*` baseline-1 단면적×7,850 식 기준 추정. 실제 계산값은 코드가 산출.
도면3·5 의 길이·규격은 정답지에서 모두 읽어와 계산.

**알려진 측정값 차이**:
- 도면5 길이: 측정 10000mm vs 정답 10500mm (baseline-3 알려진 차이)
  → 1b 는 측정값(10000) 사용. 별도 이슈 격리.
- 단면적 식: KS D 3502 표 값 대비 -2~3% 작음 (1a 에서 -2.9% 확인)

---

## 2. 목표 (산출물)

### 2.1 5장 통합 총중량 CSV

`outputs/round_weight1b_5장_총중량.csv` 형식:

```csv
도면,동,부재종류,부호,개수,길이_mm,규격,단위중량_kg_per_m,총중량_kg,count_from,spec_from,length_from,비고
도면1,1동,기둥,(skip),,,,,,,,,길이 정보 부재로 산출 불가
도면1,2동,기둥,MC1,15,6000,H-400x200x8/13,<calc>,<calc>,(2동)기둥주심도,(2동)기둥주심도,Y01·Y03Y05 골구도,
도면1,2동,기둥,MC2,4,6000,H-440x300x11/18,<calc>,<calc>,(2동)기둥주심도,(2동)기둥주심도,Y01·Y03Y05 골구도,
도면1,2동,기둥,MC3,2,6000,H-250x250x9/14,<calc>,<calc>,(2동)기둥주심도,(2동)기둥주심도,Y03Y05 골구도,
도면1,2동,기둥,SC1,4,6000,H-300x150x6.5/9,<calc>,<calc>,(2동)기둥주심도,(2동)기둥주심도,Y01·Y03Y05 골구도,
도면2,,기둥,SC1,10,7700,H-250x125x6/9,<calc>,<calc>,(override:10),가나다동 1층 구조평면도,가나동 횡단면도,count_override
도면2,,기둥,SC2,4,7700,H-200x100x5.5/8,<calc>,<calc>,(override:4),가나다동 1층 구조평면도,가나동 횡단면도,count_override
도면3,,기둥,C1,...
도면3,,기둥,C2,...
도면3,,기둥,C3,...
도면3,,기둥,C4,...
도면4,,기둥,SC1,14,9000,H-350x175x7/11,48.25,6079.0,1층 구조평면도,1층 구조평면도,종단면도·횡단면도,
도면4,,기둥,SC2,4,9000,H-194x150x6/9,29.48,1061.4,1층 구조평면도,1층 구조평면도,종단면도·횡단면도,
도면5,,기둥,C1,...
도면5,,기둥,C2,...
도면5,,기둥,C3,...
도면5,,기둥,C4,...
총합,,,,,,,,<grand_total>,,,,
```

5장 산출 + skip 행 + 총 합계 행. 도면별 소계는 보고서에서 표로.

### 2.2 도면2 spec_from 검증

추정값 `"가,나,다동 1층 구조평면도"` 가 실제로 spec_extractor 가 MEMBER LIST
일람표를 추출한 시트인지 확인. 일치하지 않으면:

1. spec_extractor 결과에서 도면2 SC1·SC2 규격이 실제로 추출된 시트명 확인
2. dedup_routing.yaml 의 `spec_from` 을 그 시트명으로 수정
3. 재실행하여 PASS 확인

이 과정은 자연스러운 yaml 검증 사이클이고 이번 라운드 범위에 포함.

### 2.3 스키마 확장 동작 검증

- `by_section` 파싱 (도면1 1동/2동 분리)
- `skip` 처리 (1동 산출 생략 + CSV/보고서에 명시)
- `count_override` 처리 (도면2 측정 skip + 정답값 사용)
- 메모 필드(`skip_reason`, count_override_reason 등) 보고서에 자동 반영

---

## 3. 설계 원칙

### 3.1 본선 무수정

- `counter.py` / `baseline.py` / `length/baseline_length.py` / `spec_extractor.py` 무수정
- 기존 yaml (`symbol_rules.yaml`, `length_routing.yaml`) 무수정
- baseline-1 `unit_weight_calc` 무수정 (호출만)
- 1a 의 신규 모듈(`dedup_loader.py`, `weight_pipeline.py`, `export_weight_csv.py`)은
  **확장 가능** — 신규 필드 처리 추가

### 3.2 측정만, 결정 안 함

- 코드는 dedup_routing.yaml 지시대로만 동작
- `skip` 결정은 yaml 의 일, 코드는 단순 분기
- `count_override` 결정도 yaml 의 일, 코드는 측정값 무시하고 override 사용

### 3.3 회귀 안전망

- 기존 10종 회귀 모두 PASS 유지
- 1a 의 도면4 결과 불변 (회귀 13 PASS 그대로)

---

## 4. 작업

### 작업 0 — 회귀 10종 baseline 기록

```bash
pytest -v poc_v2/tests/test_regression.py                       # 14/16
pytest -v poc_v2/length/tests/test_length_regression.py         # 16/16
pytest -v poc_v2/length/tests/test_spec_regression.py           # 25/25
pytest -v poc_v2/baseline2/tests/test_baseline2_regression.py   # 19/19
pytest -v poc_v2/baseline2/tests/test_baseline3_regression.py   # 33/33
pytest -v poc_v2/baseline2/tests/test_baseline4_regression.py   # 19/19
pytest -v poc_v2/baseline2/tests/test_baseline5_regression.py   # 16/16
pytest -v poc_v2/baseline2/tests/test_baseline6_regression.py   # 48/48
pytest -v poc_v2/baseline2/tests/test_baseline7_regression.py   # 이전 라운드
pytest -v poc_v2/qto/tests/test_weight1a_regression.py          # 13/13 (1a)
```

### 작업 1 — dedup_loader 스키마 확장

`poc_v2/qto/dedup_loader.py` 수정:

```python
@dataclass
class DedupRoute:
    drawing: str
    section: str | None       # 신규: "1동" | "2동" | None
    member_kind: str          # "기둥"
    symbol: str
    count_from: str | None    # 신규: None 허용 (count_override 시)
    count_override: int | None # 신규
    spec_from: str

@dataclass
class SkipMarker:
    drawing: str
    section: str | None
    reason: str

def load_dedup_routing(path: str) -> tuple[list[DedupRoute], list[SkipMarker]]:
    """확장된 yaml 파싱.
    - by_section: 도면 아래 동·구역 키 → section 필드 채움
    - skip: SkipMarker 로 별도 리스트 반환
    - count_override: 정답값 보존, count_from 은 None 허용
    """
```

검증:
- 도면1 by_section 으로 1동(skip) + 2동(4부호) 정상 분해
- 도면2 count_override 정상 보존
- 도면3·4·5 기존 동작 유지 (1a 회귀)

### 작업 2 — weight_pipeline 확장 (skip / override 분기)

`poc_v2/qto/weight_pipeline.py` 수정:

```python
def compute_weight_for_drawing(
    drawing: str,
    dedup_routes: list[DedupRoute],
    skip_markers: list[SkipMarker],
    ...
) -> list[WeightRow]:
    # 1. skip_markers 에 해당 동·구역이 있으면 SkipRow 1개 추가 후 다음
    # 2. dedup_routes 의 각 행:
    #    - count_override 있으면 그 값 사용 (count_provider 호출 skip)
    #    - count_from 있으면 기존대로 count_provider 호출
    # 3. 나머지(length, spec, unit_weight, multiply)는 1a 그대로
```

CSV 출력 시 행 종류:
- 일반 행: 부호별 산출 결과
- skip 행: `(skip)` 마커 + skip_reason
- override 행: count 컬럼에 `(override:N)` 표기 + 비고에 `count_override`

### 작업 3 — 5장 통합 산출

`poc_v2/qto/export_weight_csv.py` 확장 (또는 신규 옵션):

```bash
python -m poc_v2.qto.export_weight_csv --all \
    --output outputs/round_weight1b_5장_총중량.csv
```

5장 순회 → 통합 CSV 출력. 최종 행에 총 합계.

### 작업 4 — 정답지 비교 검증

`도면_정답지.xlsx` / `도면_길이_정답지.xlsx` 와 비교:

| 검증 항목 | 허용 오차 |
|---|---|
| 카운트 (count_from 시트) | 정확 일치 |
| 카운트 (count_override) | yaml 값 그대로 |
| 길이 | ±50 mm (≤1000) / ±2% (>1000) |
| 규격 (정규화 후) | 정확 일치 |
| 단위중량 | KS 대비 -2~3% (단면적 식 차이, 알려진 사항) |
| 부호별 총중량 | ±5% |
| 도면별 합계 | ±5% |
| 5장 총합 | ±5% |

**특히 주의**:
- 도면1 1동 skip 동작 — CSV 에 skip 행 1개, 총중량 합계에 미포함
- 도면2 spec_from 추정값 검증 (작업 2.2 참조)
- 도면5 길이 10000 (측정값) vs 10500 (정답) 차이 — 알려진 별도 이슈, 보고서 명시

### 작업 5 — 회귀 10종 무영향

작업 0 결과와 보완 후 결과 비교. 모든 PASS 수 불변.

특히 1a 의 도면4 결과는 동일해야 함 (회귀 13 PASS 불변, 도면4 총중량 7,140 kg 그대로).

### 작업 6 — 회귀 테스트 신규

`poc_v2/qto/tests/test_weight1b_regression.py` (신규):

검증 항목:
1. dedup_loader 확장 스키마 파싱 (by_section, skip, count_override)
2. weight_pipeline skip 분기 (도면1 1동)
3. weight_pipeline override 분기 (도면2)
4. 5장 통합 산출 — 행 수, 총합 정확성
5. 도면별 합계: 도면1 2동, 도면2, 도면3, 도면5 (도면4 는 1a 가 검증)
6. 5장 총합 ±5% 안
7. **회귀 무영향**: 기존 10종 PASS 수 불변

### 작업 7 — 보고서

`outputs/round_weight1b_보고서.md`:

- 라운드 범위 (5장 통합, 기둥만)
- 스키마 확장 3종 동작 결과
- 도면별 산출값 vs 정답지 비교 표
- **도면별 소계 + 5장 총합** (CSV 보완)
- 도면2 spec_from 검증 결과 (추정값 정확성)
- 도면5 측정값 차이 명시 (10000 vs 10500)
- 단위중량 계산식 vs KS 표 차이 (-2~3%) 명시
- 회귀 10종 무영향 확인
- 알려진 한계 + 다음 라운드 후보

---

## 5. 검증 우선순위

1. **작업 0** — 회귀 10종 baseline
2. **작업 1** — dedup_loader 스키마 확장 단위 테스트
3. **작업 2** — weight_pipeline 분기 (skip/override)
4. **작업 3** — 5장 통합 CSV 생성
5. **작업 4** — 정답지 비교 + 도면2 spec_from 검증
6. **작업 5** — 회귀 10종 무영향 (절대 조건)
7. **작업 6·7** — 회귀 테스트 + 보고서

**중간 보고 권장 시점**:
- 작업 2 끝난 후 (스키마 확장 동작 확인)
- 작업 4 끝난 후 (정답지 비교 + 도면2 spec_from 검증 결과)
- 작업 7 끝난 후 (커밋 가능 상태)

---

## 6. 본선 영향 점검

작업 종료 후 회귀 11종 모두 PASS 유지:

```bash
pytest -v poc_v2/tests/test_regression.py                       # 14/16 (불변)
pytest -v poc_v2/length/tests/test_length_regression.py         # 16/16
pytest -v poc_v2/length/tests/test_spec_regression.py           # 25/25
pytest -v poc_v2/baseline2/tests/test_baseline2_regression.py   # 19/19
pytest -v poc_v2/baseline2/tests/test_baseline3_regression.py   # 33/33
pytest -v poc_v2/baseline2/tests/test_baseline4_regression.py   # 19/19
pytest -v poc_v2/baseline2/tests/test_baseline5_regression.py   # 16/16
pytest -v poc_v2/baseline2/tests/test_baseline6_regression.py   # 48/48
pytest -v poc_v2/baseline2/tests/test_baseline7_regression.py   # 이전 라운드
pytest -v poc_v2/qto/tests/test_weight1a_regression.py          # 13/13 (불변)
pytest -v poc_v2/qto/tests/test_weight1b_regression.py          # 신규
```

---

## 7. 제약사항

### 7.1 절대 금지

- 본선 모듈 수정 (`counter.py` / `baseline.py` / `length/*` / `spec_extractor.py`)
- 기존 yaml 수정 (`symbol_rules.yaml`, `length_routing.yaml`)
- 정답지 수정
- baseline-1 `unit_weight_calc` 내부 수정 (호출만)
- 1a 의 회귀 결과 변경 (도면4 총중량 7,140 kg 불변)
- 보류 코드(`poc_v2/length/total_weight.py` 등) 재활성화
- LLM·VLM·랜덤·외부 네트워크 호출

### 7.2 허용 (조건부)

- `dedup_routing.yaml` 수정 — 도면2 spec_from 검증 결과 사용자 확인 후 시트명 정정
- 1a 의 신규 모듈(`dedup_loader.py`, `weight_pipeline.py`, `export_weight_csv.py`) 확장
- 신규 출력 (`outputs/round_weight1b_*`)

### 7.3 결정론

LLM·랜덤 0건. 동일 입력 → 동일 출력. 모든 부동소수 비교는 명시적 허용오차.

---

## 8. 작업 순서

1. **작업 0** — 회귀 10종 baseline 기록
2. **작업 1** — dedup_loader 스키마 확장
3. **작업 2** — weight_pipeline 분기
4. **작업 3** — 5장 통합 CSV 산출
5. **작업 4** — 정답지 비교 (도면2 spec_from 검증 포함)
6. **작업 5** — 회귀 10종 무영향
7. **작업 6** — 회귀 테스트 신규
8. **작업 7** — 보고서

---

## 9. 알려진 한계 / 다음 라운드 후보

### 이번 라운드에서 다루지 않는 것

- **보 부재** (SG·SB 등) — `보:` 섹션 추가로 같은 흐름 확장 가능. 별도 라운드
- **단면적 식 정확화** — KS D 3502 표 값과 -2~3% 차이. KS 표 룩업 전환 검토
- **도면5 길이 측정값 차이** (10000 vs 10500) — 별도 라운드 / 측정 소스 재검토
- **도면1 1동** — 길이 정보 부재. 측정 소스 추가 검증 시까지 영구 격리
- **LLM 라우팅** — 사용자가 yaml 손으로 채우는 단계의 자동화. 별도 큰 라운드

### 1b 가 PoC 본 deliverable 완성 후 다음 라운드 후보

- **보 부재 라운드** — 같은 dedup yaml 스키마로 보 통합
- **단면적 식 정확화 라운드** — KS D 3502 표 룩업 도입
- **LLM 라우팅 라운드** — 사람 작성 yaml 을 정답으로 LLM 자동 생성·평가
- **서비스화 라운드** — CLI/API/UI 어느 형태로 갈지 결정

---

**문서 끝.**
