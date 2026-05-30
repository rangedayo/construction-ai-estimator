# 라운드 베이스라인-3 보고서 — 도면5 검증 (일람표 차감 룰 일반화)

> 베이스라인-2(도면4, 부호 2종)에서 확립한 작은 도면 파이프라인을 도면5
> (부호 4종 C1~C4, 작은 도면 9개)로 확장. **일람표 차감 룰의 일반화 검증**이
> 핵심. 본선·yaml·정답지 무수정. baseline-2 모듈 재사용 + 매칭 우선순위 보완 1건.

---

## 1. 결론 요약

| 항목 | 결과 |
|---|---|
| 표제부 추출 | **9/9** 성공 |
| 시트 매칭 | **9/9 exact** (unmatched 0) |
| 카운트 | **7/7 PASS** (1층바닥 비-0, 나머지 6개 0) |
| 길이 | **2/2 PASS** (주단면도1·4 = 10500mm) |
| 규격 | **1/1 PASS** (C1~C4 4종) |
| 차감 룰 시나리오 | **A (정상)** — 부호 4종에서도 일관 작동, 이중차감 없음 |
| 회귀 5종 | 본선 1단계 14/16 · 길이 16/16 · 규격 25/25 · baseline2 19/19 · **baseline3 33/33** |

도면5 9개 시트 전부 정답과 일치(측정 대상별 PASS). 산출물 3종 생성 완료.

---

## 2. 시트별 결과 (`round_baseline3_시트별_결과.csv`)

| 파일 | 추출도면명 | 매칭 | kind | 카운트 | 길이 | 규격 |
|---|---|---|---|---|---|---|
| 도면5_1층바닥구조평면도 | 1층바닥 구조평면도 | exact | count | C1=2,C2=4,C3=8,C4=6 ✅ | N/A | C1~C4 ✅ |
| 도면5_2층바닥구조평면도 | 2층바닥 구조평면도 | exact | count | 0 ✅ | N/A | N/A |
| 도면5_지붕층바닥구조평면도 | 지붕층바닥 구조평면도 | exact | count | 0 ✅ | N/A | N/A |
| 도면5_주단면도1 | 주단면도1 | exact | length | N/A | 10500 ✅ | N/A |
| 도면5_주단면도4 | 주단면도4 | exact | length | N/A | 10500 ✅ | N/A |
| 도면5_Y1축열골조도 | Y1축열 골조도 | exact | count | 0 ✅ | N/A | N/A |
| 도면5_정면도우측면도 | 입면도1 | exact | count | 0 ✅ | N/A | N/A |
| 도면5_정면도 | 입면도1 | exact | count | 0 ✅ | N/A | N/A |
| 도면5_우측면도 | 입면도1 | exact | count | 0 ✅ | N/A | N/A |

기둥 비교 대상은 C1~C4. 비-기둥 시트는 raw 에 보(G/MG/RB/RG/RS)가 있어도
기둥 필터 후 0 → 이중카운트 방지 확인.

---

## 3. 차감 룰 일반화 판정 — **시나리오 A**

명세 3.2 시나리오 표 기준, 1층바닥 구조평면도 실행 데이터:

| 부호 | 원시 카운트 (exclude_with_spec=True 적용 후) | 일람표 페어(정의행) | 차감 후 | 정답 |
|---|---|---|---|---|
| C1 | 3 | 1 | **2** | 2 ✅ |
| C2 | 5 | 1 | **4** | 4 ✅ |
| C3 | 9 | 1 | **8** | 8 ✅ |
| C4 | 7 | 1 | **6** | 6 ✅ |

- **부호 4종에서도 차감 룰이 정확히 작동.** 페어(부호↔규격) 수만큼만 차감.
- **이중 차감 없음**: 영역 검출이 일람표를 선제거했다면 원시가 이미 답(2/4/8/6)
  이고 추가 차감 시 미달(시나리오 B)이 났을 것. 원시가 답+1 이고 차감 후 정확히
  일치 → 영역 검출은 일람표를 건드리지 않았고 차감 룰 단독으로 PASS. **시나리오 A.**
- baseline-2 차감 룰 코드 **무수정**. 도면4·5 공통으로 동작.

---

## 4. 변경 사항 — 매칭 우선순위 보완 1건

**파일**: `poc_v2/baseline2/sheet_name_matcher.py` (`match_sheet` exact 블록)

**문제**: 도면5 카운트 정답지에는 단면도(주단면도1·4)·입면도·골조도가 모두 0-행
(placeholder)으로 등록돼 있다. 기존 "exact 카운트 우선" 로직은 이 placeholder
행에 먼저 매칭돼 주단면도1·4 가 length 측정으로 가지 못했다(전부 count 라우팅).

**보완**: 카운트 행이 placeholder(빈 dict = 부호 0개)이고 **동시에** length 라벨
(`length_routing` 이 사람이 지정한 측정 소스)이면 length 를 우선한다. 실제 카운트
대상(비어있지 않은 행)은 **항상 count 유지**.

```python
hit_count = _find_exact(norm_titles, norm_count)
hit_length = _find_exact(norm_titles, norm_length)
if hit_count is not None:
    if hit_length is not None and not count_rows.get(hit_count):  # placeholder
        return SheetMatch(hit_length, "exact", "length", candidates)
    return SheetMatch(hit_count, "exact", "count", candidates)
if hit_length is not None:
    return SheetMatch(hit_length, "exact", "length", candidates)
```

**일반화 근거**: `length_routing.yaml` 의 sheet_label 은 사람이 명시한 측정 소스
신호이므로, 정답지에 자동 채워진 0-행보다 강하다. 도면4 는 카운트 행과 length
라벨이 겹치지 않으므로 **무영향**(회귀 19/19 유지로 확인).

---

## 5. 부수 검증

### 5.1 C/P 합성 부호 (작업 4)
C3 규격 정답 `H-450x200x9x14` (`C3/P3` 슬래시 결합 표기 가능). 결과:
- 카운트: C3=8 정확(차감 후). `treat_slash_as_combo=True` 로 C3/P3 본체가 C3 로 인정.
- 규격: C3 → `H-450x200x9x14` 정확 매칭.
- **PASS.** 별도 fix 불필요.

### 5.2 DIMENSION 0개 도면 (작업 5)
`도면5_정면도우측면도.dxf`(입면도1, DIMENSION 0개):
- 카운트 시트(0-행)로 라우팅 → 기둥 0 PASS.
- `measure_column_length` 직접 호출 시 **에러 없이 `length=None`** 반환 확인.
- HTML 시각화 정상 생성(기하만, 오버레이 없음).
- **안전 처리 PASS.**

### 5.3 Y1 축열 골조도 (작업 6) — ⚠️ 한계
- 매칭: 카운트 시트의 `Y1 축열 골조도` 0-행으로 라우팅 → kind=count → 기둥 0 PASS.
- **명세 의도와 차이**: 명세 1.2/2.1 은 Y1 을 길이 cross-check 소스(10500)로 기대.
  하지만 `length_routing.yaml` 도면5 sources 에 **Y1 은 미등록**(주단면도1·4 뿐).
  → length 라벨이 아니므로 length 로 라우팅되지 않음.
- 또한 측정값 자체가 `measure_column_length` 기준 **10000mm**(≠10500). 골조도는
  단면도와 DIMENSION 구조가 달라 표준 세로-최댓값 방법으로 10500 이 나오지 않음.
- **이번 라운드 fix 안 함**(7.1 length_routing 수정 금지 + 본선 무수정 원칙).
  카운트 0=0 PASS 는 정상. 다음 라운드 후보로 기록(§7).

---

## 6. 회귀 무영향 (5종)

```
poc_v2/tests/test_regression.py                      14/16  (도면2 SC1·SC2 기존 FAIL, 불변)
poc_v2/length/tests/test_length_regression.py        16/16
poc_v2/length/tests/test_spec_regression.py          25/25
poc_v2/baseline2/tests/test_baseline2_regression.py  19/19  (도면4)
poc_v2/baseline2/tests/test_baseline3_regression.py  33/33  (도면5, 신규)
```

매칭 우선순위 보완 전/후 본선 4종 결과 동일(74 passed / 2 failed). 결정론(LLM·랜덤 0건).

---

## 7. 알려진 한계 · 다음 라운드 후보

| # | 한계 | 영향 | 다음 라운드 |
|---|---|---|---|
| 1 | **Y1 축열 골조도 length cross-check 미충족** | Y1 이 count 라우팅(0 PASS)되어 길이 10500 cross-check 안 됨. length_routing 미등록 + 표준 측정 10000≠10500 | 골조도 측정 방법 추가 또는 length_routing 에 Y1 등록(정답지 라우팅 정합성 재검토) |
| 2 | 차감 룰 도면3·2·1 미검증 | 도면5 까지만 일반화 확인 | 도면3 → 2 → 1 확대 |
| 3 | 단면도 표제부 종/횡 미구분 (도면3 등 향후) | 시트별 길이 갈리면 매칭 모호 | `config/sheet_name_overrides.yaml` fallback |
| 4 | 도면2 카운트 SC1·SC2 본선 FAIL | 작은 도면 단위 재현 미확인 | 도면2 라운드에서 점검 |

---

## 8. 산출물

- `outputs/round_baseline3_시트별_결과.csv` — 도면5 9행
- `outputs/visualize/도면5_*.html` × 9
- `poc_v2/baseline2/tests/test_baseline3_regression.py` — 33 tests
- `poc_v2/baseline2/sheet_name_matcher.py` — 매칭 우선순위 보완(placeholder vs length 라벨)
- `outputs/round_baseline3_보고서.md` — 본 문서

**문서 끝.**
