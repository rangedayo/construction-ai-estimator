# 라운드 베이스라인-2 보고서 — 작은 도면 입력 모델 통일

**작성일**: 2026-05-30
**범위**: 도면4 작은 도면 5개 검증까지 (도면5·3·2·1은 다음 라운드)
**본선 영향**: 0 (counter/baseline/length/spec_extractor·symbol_rules.yaml 무수정)

---

## 0. TL;DR

| 항목 | 결과 |
|---|---|
| 표제부 도면명 추출 | 5/5 (100%) |
| 정답지 시트 매칭 | 5/5 (100%) — exact 2, partial 3 |
| 카운트 PASS | 2/2 (1층 SC1=14·SC2=4 / 지붕층 0·0) |
| 길이 PASS | 3/3 (단면도 3종 = 9000mm) |
| 규격 PASS | 1/1 (SC1·SC2 일람표 규격) |
| baseline2 회귀 | **19 passed** |
| 본선 회귀 3종 | 1단계 14/16 · 길이 16/16 · 규격 25/25 (불변) |

---

## 1. 라운드 범위

측정 3종(카운트·길이·규격)의 입력을 "큰 도면 1장"에서 "작은 도면 N장"으로
통일했다. 파일명이 아니라 **dxf 내부 표제부 도면명**으로 시트를 식별하고,
정답지(`도면_정답지.xlsx`·`도면_길이_정답지.xlsx`)의 세부 도면명·라우팅 라벨과
매칭한다. 이번 라운드는 도면4 검증까지.

### 작업 0 선결 이슈 — 길이 라우팅 경로 복원

작업 시작 시 길이 회귀가 0/16(FileNotFoundError)이었다. sample_data 파일이
작은 도면 통일 명명(`도면N_단면도.dxf` 등)으로 교체되며 `length_routing.yaml`이
가리키던 옛 파일명(`도면N-기둥-길이_*.dxf`)이 사라진 것이 원인. 사용자 승인 하에
**라우팅의 file 경로 10개만** 현존 파일명으로 교체(applies_to/method/sheet_label
무수정)했고, 길이 회귀가 16/16으로 복원됐다(측정값 차이 0 — 동일 기하 확인).

---

## 2. 신규 모듈 (poc_v2/baseline2/)

| 파일 | 역할 |
|---|---|
| `sheet_title_extractor.py` | 표제부 도면명 추출 (키워드+height·위치 점수화) |
| `sheet_name_matcher.py` | 정답지 시트명·길이 라벨 매칭 (exact→partial→fallback) |
| `small_drawing_pipeline.py` | 측정 통합 (카운트·길이·규격 + PASS/FAIL) |
| `export_baseline2_csv.py` | 시트별 결과 CSV CLI |
| `visualize_small.py` | 작은 도면 1장당 HTML 오버레이 |
| `tests/test_baseline2_regression.py` | 회귀 9항목 (19 케이스) |

본선 함수는 **import 해 호출만** 한다:
`counter.count_members`, `auto_policy.auto_detect_policy`,
`length.measure.measure_column_length`, `length.spec_extractor.extract_specs`,
정답지 로더들. `baseline.compute_drawing`은 도면명→큰 dxf 로 resolve 하므로
작은 도면엔 못 쓴다 — 동일 정책 로직을 작은 dxf 경로로 재현한 wrapper 사용.

---

## 3. 도면4 시트별 결과

| 파일 | 추출 도면명 | 매칭 시트 | 신뢰도 | 측정 | 정답 | 결과 |
|---|---|---|---|---|---|---|
| 도면4_1층구조평면도 | 1층구조평면도 | 1층 구조평면도 | exact | SC1=14,SC2=4 | 14,4 | **PASS** |
| 〃 (규격) | — | — | — | SC1=H-350x175x7x11<br>SC2=H-194x150x6x9 | 동일 | **PASS** |
| 도면4_지붕층구조평면도 | 지붕층 구조평면도 | 지붕층 구조평면도 | exact | SC1=0,SC2=0 | 0,0 | **PASS** |
| 도면4_종단면도횡단면도 | 단면도 | 종단면도 | partial | 9000mm | 9000 | **PASS** |
| 도면4_종단면도 | 단면도 | 종단면도 | partial | 9000mm | 9000 | **PASS** |
| 도면4_횡단면도 | 단면도 | 종단면도 | partial | 9000mm | 9000 | **PASS** |

산출물: `outputs/round_baseline2_시트별_결과.csv`,
`outputs/visualize/도면4_*.html` × 5.

---

## 4. 핵심 설계 결정 — 일람표(부재 리스트) 차감

작은 평면도는 본체 배치 + 일람표가 한 시트에 같이 있다. 큰 도면은 일람표 영역을
검출(신호1)해 빼지만, 시트로 쪼개면 일람표 부호 종류가 4종 미만이라
`min_distinct_symbols=4` 영역 검출이 발화하지 않는다(도면4 1층 일람표=기둥 SC1·SC2
2종). 그대로면 SC1=15·SC2=5 (정답 +1씩).

해결: **`spec_extractor`가 잡는 부호↔규격 페어 = 정확히 일람표 정의행**이므로,
부호별 페어 수만큼 카운트에서 차감한다. 배치 부호는 인접 규격이 없어 페어로
잡히지 않으므로 안전하다. 결과: 1층 15→14·5→4, 지붕층 1→0·1→0. 본선 함수
재사용·yaml 무수정·파라미터 변경 없음.

---

## 5. 추출률·매칭률·측정 PASS율

- **표제부 추출률**: 5/5 (100%). 도면4 각 파일은 도면명 키워드 후보가 정확히
  1개씩이라 점수화가 자명하게 단일 후보를 채택.
- **매칭률**: 5/5 (100%). 평면도 2개 exact(카운트 시트), 단면도 3개
  partial(길이 라벨 "종단면도"/"횡단면도"에 "단면도" 포함). fallback yaml 불필요.
- **측정 PASS율**: 카운트 2/2, 길이 3/3, 규격 1/1.

---

## 6. 본선 무영향 확인

```
pytest poc_v2/tests/test_regression.py                  → 14/16 (도면2 SC1·SC2 기존 FAIL)
pytest poc_v2/length/tests/test_length_regression.py    → 16/16
pytest poc_v2/length/tests/test_spec_regression.py      → 25/25
pytest poc_v2/baseline2/tests                            → 19 passed
```

신규 모듈 추가 + `length_routing.yaml` file 경로 10개 갱신(데이터 리오그 동기화)
외 본선 코드·정답지 수정 0건.

---

## 7. 알려진 한계

- **단면도 partial 매칭**: 표제부가 "단면도"로만 표기돼 종단면도/횡단면도를
  구분하지 못한다. 길이는 두 시트가 같은 9000mm라 영향 없지만, 동(棟)·시트별로
  길이가 갈리는 도면(도면1 1동/2동 등)에서는 fallback yaml 또는 동 라벨 매칭이
  필요할 수 있다.
- **입면도(배면도/우측면도) unmatched**: 카운트·길이 대상이 아니므로 CSV·HTML에서
  기본 제외(`--include-unmatched`로 포함 가능). 의도된 동작.
- **카운트 화이트리스트**: 일람표 영역 검출이 큰 도면과 같게 동작하도록 기둥+보
  병합 부호로 카운트하되, PASS 비교는 이번 라운드 스코프인 기둥만.

---

## 8. 다음 라운드 후보

도면5 → 도면3 → 도면2 → 도면1 순.

- **도면2**: 1단계 카운트 SC1·SC2가 기존 FAIL(본 라운드와 무관) — 작은 도면
  단위에서 재현되는지 별도 확인.
- **도면1**: 1동/2동 분리 처리 때문에 마지막. 동 라벨 기반 매칭 필요.
- **단면도 구분**: 종단면도/횡단면도 길이가 달라지는 도면이 나오면 표제부 단독
  매칭의 한계를 fallback yaml로 보강.

---

**문서 끝.**
