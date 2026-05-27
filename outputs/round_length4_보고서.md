# 라운드 길이-4 보고서 — 규격 추출 + 단위중량 룩업 + 총중량 산출

> **목적**: 도면1~5 기둥 부재에 대해 `총중량(kg) = 개수 × 길이(m) × 단위중량(kg/m)` 자동 산출.
> 본선(counter.py / baseline.py / yaml) 무수정, 독립 수집기 분리로 회귀 안전망 유지.

---

## 0. 요약

| 항목 | 수치 |
|---|---|
| 규격 추출 정답율 | **18 / 18** (도면1×6 + 도면2×2 + 도면3×4 + 도면4×2 + 도면5×4) |
| 단위중량 룩업 성공율 | **18 / 18** (yaml 임시값 기준) |
| 총중량 산출 가능 케이스 | **16 / 18** (도면1 1동 MC1·MC2 2건은 길이 부재로 보류) |
| 총중량 합계 (임시값) | **129,313.1 kg** |
| 1단계 회귀 | **14 / 16** PASS — 기존 상태 그대로 유지 (도면2 SC1·SC2 FAIL은 라운드 길이-4 무관) |
| 길이-1 회귀 | **16 / 16** PASS — 영향 없음 |
| 길이-4 신규 회귀 | **44 / 44** PASS |

---

## 1. 신규·수정 파일

### 1.1 신규 코드·데이터

| 경로 | 종류 | 역할 |
|---|---|---|
| [config/unit_weight_table.yaml](../config/unit_weight_table.yaml) | 데이터 | H형강 단위중량 — **임시값** (멘토 확인 후 교체 예정) |
| [poc_v2/length/unit_weight.py](../poc_v2/length/unit_weight.py) | 코드 | yaml 로더 + `lookup_unit_weight(spec_normalized)` |
| [poc_v2/length/ground_truth_spec.py](../poc_v2/length/ground_truth_spec.py) | 코드 | 정답지 비고 파서 + `normalize_spec` + section-aware 인스턴스 카운트 |
| [poc_v2/length/spec_extractor.py](../poc_v2/length/spec_extractor.py) | 코드 | DXF에서 (부호↔규격) 페어링 — 독립 모듈 |
| [poc_v2/length/total_weight.py](../poc_v2/length/total_weight.py) | 코드 | 총중량 합산·CSV 산출 |
| [poc_v2/length/visualize_specs.py](../poc_v2/length/visualize_specs.py) | 코드 | 부호·규격·페어링·동라벨 시각화 |
| [poc_v2/length/tests/test_spec_regression.py](../poc_v2/length/tests/test_spec_regression.py) | 테스트 | 18케이스 회귀 + 적산외 부재 미혼입 + 총중량 보류 확인 |

### 1.2 무수정 파일 (본선 회귀 안전망)

`counter.py`, `baseline.py`, `auto_policy.py`, `detect_table_region.py`,
`classify_text.py`, `config/symbol_rules.yaml`, `config/length_routing.yaml`,
`poc_v2/length/baseline_length.py`, `ground_truth_length.py` — 본 라운드에서 손대지 않음.

---

## 2. 결과 — 총중량 (임시 단위중량 기준)

[outputs/round_length4_총중량.csv](round_length4_총중량.csv)

| 도면 | 동 | 부호 | 개수 | 길이(mm) | 규격 (normalized) | 단위중량 (kg/m) | 총중량 (kg) | 비고 |
|---|---|---|---:|---:|---|---:|---:|---|
| 도면1 | 1동 | MC1 | 12 | — | H-588x300x12x20 | 151.0 | — | 길이 측정 불가 (소스 도면 없음) |
| 도면1 | 1동 | MC2 | 10 | — | H-200x200x8x12 | 49.9 | — | 길이 측정 불가 (소스 도면 없음) |
| 도면1 | 2동 | MC1 | 15 | 6,000 | H-400x200x8x13 | 65.4 | 5,886.0 | |
| 도면1 | 2동 | MC2 | 4 | 6,000 | H-440x300x11x18 | 124.0 | 2,976.0 | |
| 도면1 | 2동 | MC3 | 2 | 6,000 | H-250x250x9x14 | 71.8 | 861.6 | |
| 도면1 | 2동 | SC1 | 4 | 6,000 | H-300x150x6.5x9 | 36.7 | 880.8 | |
| 도면2 | — | SC1 | 10 | 7,700 | H-250x125x6.0x9.0 | 29.6 | 2,279.2 | |
| 도면2 | — | SC2 | 4 | 7,700 | H-200x100x5.5x8.0 | 21.3 | 656.0 | |
| 도면3 | — | C1 | 8 | 19,060 | H-600x407x20x35 | 175.0 | 26,684.0 | 현장제작 — KS 외 단면 가능성 |
| 도면3 | — | C2 | 15 | 19,060 | H-428x407x20x35 | 140.0 | 40,026.0 | |
| 도면3 | — | C3 | 8 | 19,060 | H-400x400x13x21 | 172.0 | 26,226.6 | |
| 도면3 | — | C4 | 1 | 19,060 | H-300x300x10x15 | 94.0 | 1,791.6 | |
| 도면4 | — | SC1 | 14 | 9,000 | H-350x175x7x11 | 49.6 | 6,249.6 | |
| 도면4 | — | SC2 | 4 | 9,000 | H-194x150x6x9 | 30.6 | 1,101.6 | |
| 도면5 | — | C1 | 2 | 10,500 | H-300x300x10x15 | 94.0 | 1,974.0 | |
| 도면5 | — | C2 | 4 | 10,500 | H-250x250x9x14 | 71.8 | 3,015.6 | |
| 도면5 | — | C3 | 8 | 10,500 | H-450x200x9x14 | 66.2 | 5,560.8 | |
| 도면5 | — | C4 | 6 | 10,500 | H-200x200x8x12 | 49.9 | 3,143.7 | |

### 도면별 소계 (산출분만)

| 도면 | 총중량 (kg) |
|---|---:|
| 도면1 | 10,604.4 |
| 도면2 | 2,935.2 |
| 도면3 | 94,728.2 |
| 도면4 | 7,351.2 |
| 도면5 | 13,694.1 |
| **합계** | **129,313.1** |

> ⚠ 위 총중량은 yaml 임시 단위중량 기반. 멘토 확인 후 정확값으로 yaml만 갈아끼우면 동일 코드로 재산출 가능.

---

## 3. 설계 결정

### 3.1 독립 수집기 분리

`counter.py` 의 카운팅 파이프라인은 **height 필터**·**일람표 영역 제외**·**규격 안내 텍스트 제외** 를 거친다. 본 라운드의 spec_extractor 는 정반대 목적(일람표 안의 부호·규격 추출)이므로 카운팅 모듈을 호출하지 않고 ezdxf 만 사용해 독립 동작한다.

→ 1단계 회귀 14/16 PASS 그대로, 길이-1 회귀 16/16 PASS 그대로.

### 3.2 spec_normalized 캐노니컬 폼

정답지·DXF 일람표에 슬래시(`H-250x250x9/14`) 와 x 표기(`H-250x250x9x14`)가 혼재. `normalize_spec()` 이 본문의 `/` 를 `x` 로 일괄 치환해 두 표기를 동일 키로 룩업 — yaml 도 가독성을 위해 슬래시를 그대로 두되 로더에서 정규화. 추출·정답·룩업 모두 같은 canonical 경로를 사용.

### 3.3 동 식별 (도면1)

DXF modelspace 의 `(N동)` 패턴 텍스트(`(1동) 기둥부호도-1`, `(2동) 기둥주심도` 등) 좌표를 동 라벨 후보로 수집. 매칭된 부호 좌표에서 2D 거리 가장 가까운 라벨을 채택. 도면1 의 1동·2동 일람표를 정확히 분리.

### 3.4 적산 외 부재 필터

`spec_extractor.DEFAULT_EXCLUDED_PREFIXES = ("P", "BR", "SBR", "MF", "BRACE")`. 부호 후보 단계에서 차감해 P1~P4(콘크리트 매입), BR1·BR2 / SBR1(가새), MF1(매트기초) 가 결과에 들어오지 않도록 보장. 테스트 `test_excluded_prefixes_absent` 가 5개 도면 모두에서 검증.

> 정확 매칭 + 접두사 직후 숫자 보장 — `"C1"` 이 `"BR"` prefix 와 충돌하지 않게 처리.

### 3.5 per-section 카운트의 임시 소스

1단계 baseline 은 (도면, 부호) 단위 합계만 제공해 도면1 1동·2동 같이 같은 부호가 다른 규격을 갖는 경우 분해가 안 됨. 본 라운드는 정답지의 인스턴스 행 직접 집계(`load_section_instances`)를 임시 카운트 소스로 사용. 향후 1단계가 per-section 분해를 지원하면 동일 인터페이스로 교체 가능.

---

## 4. 단위중량 임시값 — 멘토 확인 필요

[config/unit_weight_table.yaml](../config/unit_weight_table.yaml) 의 모든 값은 **명세서 §5.2의 예시값을 그대로 옮긴 초안**.

### 멘토 확인 후 교체 절차

1. yaml 의 키는 그대로 두고 값만 KS D 3502 정확값으로 수정
2. `python -m poc_v2.length.total_weight` 실행 → CSV 재산출
3. 코드(`unit_weight.py`, `total_weight.py`, `spec_extractor.py`) 무수정

### 특히 주의할 항목

- `H-600x407x20x35` (도면3 C1, 현장제작) — KS 표준 외 단면 가능성. 단위중량 실측치 또는 표준 추정치 확인 필요.
- yaml 키는 슬래시·x 표기 자유. canonical 폼(`x`)으로 로드되므로 가독성에 맞춰 적어도 룩업 동일.

---

## 5. 검증

### 5.1 회귀 결과

```
pytest -v poc_v2/tests/test_regression.py poc_v2/length/tests/
=> 74 passed, 2 failed
  - 1단계 14/16 PASS (도면2 SC1·SC2 FAIL — 라운드 길이-4 이전부터 존재)
  - 길이-1 16/16 PASS
  - 길이-4 신규 44/44 PASS
```

### 5.2 길이-4 회귀 항목

- `test_spec_extraction_matches_ground_truth` × 18: 추출 규격이 정답지와 일치
- `test_unit_weight_lookup_succeeds` × 18: 정답 규격이 yaml 에 등록됨
- `test_excluded_prefixes_absent` × 5: P/BR/SBR/MF/BRACE 부호 미혼입
- `test_total_weight_deferred_only_for_도면1_1동`: 보류 케이스 = (도면1 1동 MC1·MC2) 정확히
- `test_total_weight_produced_for_remaining_cases`: 나머지 16건 모두 산출
- `test_unit_weight_table_not_empty`: yaml 로드 가능

---

## 6. 시각화

[outputs/visualize/](visualize/) 디렉토리:

- `도면1_specs_기둥.html` ~ `도면5_specs_기둥.html` (×5)

레이어
- 회색: 도면 기하 (LINE/POLY/ARC/CIRCLE)
- 녹색 동그라미: 매칭된 부호 + 라벨 (부호 + 동)
- 파랑 사각형: 매칭된 규격 + 라벨 (원문 텍스트)
- 점선: 부호↔규격 페어링
- 보라색 텍스트: 시트 동 라벨 `(1동)`, `(2동)`

---

## 7. 알려진 한계 (다음 라운드 후보)

1. **도면1 1동 길이 부재** — 1단계는 카운트 가능하나 길이 측정 소스 DXF 가 없음. 1동 비구도·입면도·단면도 시트가 별도 제공되거나 수동 입력 시 즉시 산출 가능.
2. **단위중량 KS 정확값 미반영** — yaml 임시값 그대로. 멘토 확인 후 교체 예정.
3. **현장제작 단면** — 도면3 `H-600x407x20x35` 는 KS 표준 외 단면 가능성. 실측 또는 멘토 확정 필요.
4. **보(Beam) 규격·총중량** — 본 라운드 범위 외. 길이-2 라운드에서 보 길이 측정 완료 후 동일 룰 적용 예정. `load_ground_truth_spec` 는 `-기둥-길이` 시트만 읽도록 한정돼 있어 보 분리 작업은 시트 패턴만 확장하면 됨.
5. **1단계 per-section 분해** — 도면1 1동 vs 2동 같이 같은 부호가 동마다 다른 규격일 때 1단계 카운트가 합산되는 한계. 현재는 정답지 인스턴스 행으로 우회. 1단계가 동 정보를 부호별로 분해해 주면 그대로 교체.

---

## 8. 멘토 확인 사항

1. **`config/unit_weight_table.yaml` 17개 값** — KS D 3502 정확값 확인 후 교체
2. **도면3 `H-600x407x20x35 (현장제작)`** — 단위중량 실측인지 표준 추정인지
3. **도면1 1동 길이 측정 처리 방안** — 본 라운드 외, 다음 라운드 결정
4. **적산 외 부재 정의 확정** — 현재 P, BR, SBR, MF, BRACE 외 추가 제외 부재 여부

---

## 9. 산출물 인덱스

| 파일 | 설명 |
|---|---|
| [outputs/round_length4_총중량.csv](round_length4_총중량.csv) | (drawing, section, symbol) × 18행 총중량 결과 |
| [outputs/visualize/도면1_specs_기둥.html](visualize/도면1_specs_기둥.html) | 도면1 페어링 시각화 |
| [outputs/visualize/도면2_specs_기둥.html](visualize/도면2_specs_기둥.html) | 도면2 페어링 시각화 |
| [outputs/visualize/도면3_specs_기둥.html](visualize/도면3_specs_기둥.html) | 도면3 페어링 시각화 |
| [outputs/visualize/도면4_specs_기둥.html](visualize/도면4_specs_기둥.html) | 도면4 페어링 시각화 |
| [outputs/visualize/도면5_specs_기둥.html](visualize/도면5_specs_기둥.html) | 도면5 페어링 시각화 |
| [config/unit_weight_table.yaml](../config/unit_weight_table.yaml) | 단위중량 yaml — 멘토 확인 대기 |

---

**문서 끝.**
