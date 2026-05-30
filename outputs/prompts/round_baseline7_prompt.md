# 라운드 베이스라인-7 본작업 명세서 — 분리본 시트 routing 일반화

> **작성 목적**: baseline-3/4/6 세 라운드에서 누적된 **분리본 시트 routing 한계** 3종을
> 일반화된 룰로 통합 해결. 도면 검증이 아닌 **일반화 라운드** — 새 도면을 추가하지 않고
> 누적된 미해결 케이스에 집중.
>
> **읽는 순서**: 0 → 1 → 2 → (제약 7 먼저) → 3 → 4 → 5 → 6 → 8 → 9

---

## 0. TL;DR

| 항목 | 내용 |
|---|---|
| **목표** | 누적 한계 3종(Y1축열·종단면도 분리본·Y03 단독본) routing을 일반화 룰로 해결 |
| **핵심 가설** | 정답지 결합 시트명(`"종단면도,계단단면도"`)을 콤마/줄바꿈으로 split해 컴포넌트로 추가 매칭 키 생성. 분리본 표제부 도면명이 컴포넌트와 일치하면 통합본 시트로 매칭 → length 라우팅 자동 |
| **신규 모듈** | 없음 — `sheet_name_matcher`에 일반화 보완 |
| **본선 영향** | `counter.py` / `baseline.py` / `length/baseline_length.py` / `spec_extractor.py` / 모든 yaml 무수정 |
| **회귀 안전망** | 기존 8종(1단계 14/16, 길이 16/16, 규격 25/25, baseline2~6 누적) 전부 유지 |
| **이번 범위** | 분리본 routing 일반화 + 누적 한계 3종 PASS |
| **산출물** | 보완된 `sheet_name_matcher.py`, `outputs/round_baseline7_분리본검증.csv`, `outputs/round_baseline7_보고서.md` |

---

## 1. 배경

### 1.1 누적 한계 3종 (모두 분리본 routing)

| 라운드 | 케이스 | 증상 | 정답지 시트명 |
|---|---|---|---|
| baseline-3 | 도면5_Y1축열골조도 | [count] 라우팅 (0=0 PASS지만 의도 다름) | 라우팅에 "주단면도1, 주단면도4, Y1 축열 골조도" 결합 |
| baseline-4 | 도면3_종단면도(분리본) | [count] 라우팅 (placeholder count 매칭) | "종단면도,계단단면도" 결합 |
| baseline-6 | 도면1_Y03(단독본) | unmatched | "(2동)Y03,Y05열골구도" 결합 |

### 1.2 공통 패턴

세 케이스 모두 같은 구조:
1. 정답지 시트명 또는 라우팅이 **A,B 결합 형식** (콤마 또는 줄바꿈)
2. 사용자가 cross-check 용도로 **분리본 dxf 파일** 생성
3. 분리본 표제부 도면명이 결합 시트명과 직접 매칭 안 됨

해결 방향: 정답지 결합 시트명을 split해 컴포넌트를 추가 매칭 키로 등록. 분리본 표제부가
컴포넌트와 일치하면 통합본과 같은 시트 키로 매칭 → 자동으로 length 라우팅에 포함됨.

### 1.3 도면2 split-TEXT는 이번 범위 외

도면2 SC1·SC2 카운트 FAIL은 **데이터 인코딩 한계**(블록 내부 분리 TEXT)로 본질이 다름.
도면2 한 도면 특이 케이스라 baseline 레이어 보완으로 해결 시 over-engineering. 그대로
"알려진 데이터 한계" 격리 유지. 이번 라운드 작업 범위 아님.

---

## 2. 목표 (산출물)

### 2.1 일반화된 매칭 룰

`sheet_name_matcher.py`에 분리본 매칭 룰 추가:

```python
def match_sheet_with_components(extracted_title, answer_sheets):
    """결합 시트명을 컴포넌트로 분해해 분리본 매칭.

    예시:
        정답지 시트: "종단면도,계단단면도"
        → 컴포넌트: ["종단면도", "계단단면도"]
        → 분리본 표제부 "종단면도" 매칭 시 통합본 키 "종단면도,계단단면도"로 라우팅
    """
    # 1. 기존 exact/partial 매칭 시도
    # 2. 실패 시 결합 시트명 split (콤마+공백, 줄바꿈)
    # 3. 컴포넌트와 표제부 일치하면 통합본 키 반환 + confidence='component'
```

### 2.2 누적 한계 3종 결과

| 케이스 | 기대 결과 |
|---|---|
| 도면5_Y1축열골조도 | length 라우팅. 측정값 보고 (정답 10500 vs 표준 측정 10000 — 측정값 일치는 별도 이슈) |
| 도면3_종단면도(분리본) | length 라우팅. 측정값 19060 PASS (통합본과 동일) |
| 도면1_Y03(단독본) | exact match → 통합본 "Y03,Y05열골구도"로. length 라우팅. 측정값 6000 PASS |

### 2.3 검증 CSV

`outputs/round_baseline7_분리본검증.csv`:
```
도면,분리본파일,통합본시트키,매칭전라우팅,매칭후라우팅,측정값,정답,PASS/FAIL
도면5,Y1축열골조도,주단면도1·4·Y1결합,count,length,10000,10500,FAIL(라우팅PASS/측정값FAIL)
도면3,종단면도,종단면도,계단단면도,count,length,19060,19060,PASS
도면1,Y03열골구도,(2동)Y03,Y05열골구도,unmatched,length,6000,6000,PASS
```

라우팅 일반화는 PASS, 측정값 일치는 별도 보고 (Y1축열의 10000 vs 10500은 이번 라운드 fix
범위 외).

---

## 3. 설계 원칙

### 3.1 본선 무수정 + baseline 모듈 일반화 보완

수정 범위: `sheet_name_matcher.py`만 (또는 small_drawing_pipeline 매칭 호출부).
다른 baseline 모듈, 본선, yaml, 정답지 무수정.

### 3.2 결합 시트명 split 규칙

baseline-5의 콤마-split 버그 수정 룰과 호환:
- 구분자: `"콤마+공백"`, `"、"`, `"\n"`, `"\n("` (정답지의 줄바꿈 결합 형식)
- 토큰 내부 콤마는 보존 (예: "가,나동" 같은 동 라벨)

예시:
```
"종단면도,계단단면도"        → 콤마만, 공백 없음 → split? 보존?
"종단면도, 계단단면도"       → 콤마+공백 → split → ["종단면도", "계단단면도"]
"주단면도1, 주단면도4, Y1 축열 골조도" → split → 3개 컴포넌트
"(2동)Y03,Y05열골구도"      → 콤마만, 공백 없음 → 특수 케이스 (Y패턴)
```

**모호 케이스**: "(2동)Y03,Y05열골구도" 같은 공백 없는 콤마. baseline-5 룰로는 토큰 내부
보존이라 split 안 됨. 이번 라운드에 **"Y\d+,Y\d+" 패턴 같은 한정 케이스만 split** 허용
규칙 추가? 또는 정답지 시트명의 콤마 split을 length 매칭 시에만 더 관대하게?

→ **작업 1에서 케이스별 분석 후 결정**. 토큰 내부 콤마 보존(baseline-5)과 결합 split(이번 라운드)이 충돌하지 않는 룰을 찾아야 함.

### 3.3 분리본 매칭 신뢰도

새로운 confidence 등급 추가:
- `exact` (기존)
- `partial` (기존)
- `component` (신규) — 결합 시트명의 컴포넌트로 매칭됨
- `fallback` (기존)
- `unmatched` (기존)

`component` 매칭은 통합본과 같은 정답값을 공유. cross-check 용도.

### 3.4 기존 회귀 보존 절대 조건

매칭 보완으로 baseline-2/3/4/5/6 회귀 8종이 깨지면 안 됨. 특히:
- baseline-3 도면5_정면도우측면도 (입면도1 매칭, 카운트 0) — split 룰이 영향 주면 안 됨
- baseline-4 도면3_1층바닥 vs 중간1층바닥 — 시트명 split이 매칭 충돌 일으키면 안 됨
- baseline-6 도면1 16+ 시트 매칭 — 동 라벨과 결합 형식이 함께 있는 케이스 안전 처리

### 3.5 "AI는 결정만, 도구는 측정만"

LLM·랜덤·외부 호출 0건. 결정론 보장.

---

## 4. 작업 항목

### 작업 0 — 회귀 사전 확인

```bash
pytest -v poc_v2/tests/test_regression.py                      # 14/16
pytest -v poc_v2/length/tests/test_length_regression.py        # 16/16
pytest -v poc_v2/length/tests/test_spec_regression.py          # 25/25
pytest -v poc_v2/baseline2/tests/test_baseline2_regression.py  # 19/19
pytest -v poc_v2/baseline2/tests/test_baseline3_regression.py  # 33/33
pytest -v poc_v2/baseline2/tests/test_baseline4_regression.py  # 19/19
pytest -v poc_v2/baseline2/tests/test_baseline5_regression.py  # 16/16
pytest -v poc_v2/baseline2/tests/test_baseline6_regression.py  # 48/48
```

전부 PASS 기록. 매칭 보완 전후 비교 기준.

### 작업 1 — 결합 시트명 split 룰 분석

**1-1 정답지 결합 시트명 인벤토리**:
정답지 전체에서 결합 형식 시트명을 추출해 패턴 분석:
- 콤마+공백 결합 (예: "주단면도1, 주단면도4, Y1 축열 골조도")
- 콤마만 결합 (예: "종단면도,계단단면도", "(2동)Y03,Y05열골구도")
- 줄바꿈 결합 (예: "가,나동 입면도\n(가,나동 정면도, 가,나동 좌측면도)")

각 케이스에서 split이 안전한지 검증:
- 토큰 내부 콤마가 split되면 안 되는 케이스 있는지
- 도면명 일부분으로 어디까지 split할지 (예: "주단면도1" vs "주단면도1, 주단면도4")

**1-2 split 룰 정의**:
- 구분자 우선순위: `\n`, `\n(`, `, ` (콤마+공백), 모호 케이스만 `,` (공백 없음)
- 토큰 보호: 동 라벨 `(N동)`, 알파벳+숫자 결합 `Y\d+` 등 패턴은 컴포넌트 단위로 보호

### 작업 2 — sheet_name_matcher 보완

`match_sheet_with_components` 추가 (또는 기존 match 함수에 component 단계 추가).

매칭 순서:
1. exact (정규화 후 정확 일치)
2. partial (한쪽이 다른쪽 포함)
3. **component (신규)** — 결합 시트명 split 후 컴포넌트 일치
4. fallback yaml
5. unmatched

`component` 매칭 시 통합본 시트 키 반환. 분리본은 통합본과 같은 정답값·라우팅 공유.

### 작업 3 — 누적 한계 3종 검증

**3-1 도면5_Y1축열골조도**:
- 매칭 결과: length 라우팅으로 가는지
- 측정값: 표준 측정 10000 vs 정답 10500. 라우팅 PASS, 측정값 FAIL 보고.

**3-2 도면3_종단면도(분리본)**:
- 매칭 결과: length 라우팅
- 측정값: 19060 PASS (통합본과 동일)

**3-3 도면1_Y03(단독본)**:
- 매칭 결과: 통합본 "Y03,Y05열골구도"와 같은 시트 키로
- 측정값: 6000 PASS

### 작업 4 — 회귀 8종 무영향 검증

매칭 보완 후 회귀 8종 재실행. PASS 수 변동 없어야 함.

특히 주의:
- baseline-4 도면3_1층바닥 vs 중간1층바닥 충돌 회피 유지
- baseline-6 도면1 동 라벨 매칭 유지
- baseline-3 도면5_정면도우측면도 (입면도1) 매칭 유지

### 작업 5 — 검증 CSV + 보고서

**CSV**: `outputs/round_baseline7_분리본검증.csv` (2.3 형식)

**보고서**: `outputs/round_baseline7_보고서.md`
- 누적 한계 3종 해결 결과 표
- 일반화된 split 룰 명세 (구분자, 토큰 보호)
- 회귀 8종 무영향 확인
- 알려진 남은 한계:
  - Y1축열골조도 측정값 10000 vs 10500 (라우팅은 풀렸지만 측정값 차이는 별도 이슈)
  - 도면2 SC1·SC2 블록 split-TEXT (이번 범위 외, 격리 유지)
- 다음 라운드 후보 (LLM 라우팅, 보 부호 카운트, 단위중량 산출 등)

### 작업 6 — 회귀 테스트 신규

**파일**: `poc_v2/baseline2/tests/test_baseline7_regression.py`
**검증 항목**:
1. 누적 한계 3종 매칭 결과 (component 신뢰도)
2. 도면3 종단면도 분리본 19060 PASS
3. 도면1 Y03 단독본 6000 PASS
4. 도면5 Y1축열골조도 length 라우팅 (측정값은 SKIP 또는 별도 케이스)
5. 회귀 8종 무영향

---

## 5. 검증 우선순위

1. **작업 0** — 회귀 8종 기록
2. **작업 1** — 결합 시트명 인벤토리 + split 룰 정의 (가장 신중)
3. **작업 2** — sheet_name_matcher 보완
4. **작업 3** — 누적 한계 3종 검증
5. **작업 4** — 회귀 8종 무영향 (절대 조건)
6. **작업 5·6** — CSV + 보고서 + 회귀 테스트

작업 1에서 split 룰이 기존 매칭에 영향 주는지 신중히 분석. 토큰 내부 콤마 보존
(baseline-5)과 결합 split (이번 라운드)이 충돌하면 룰 재설계.

---

## 6. 본선 영향 점검

작업 종료 후 회귀 9종 모두 PASS 유지:

```bash
pytest -v poc_v2/tests/test_regression.py                      # 14/16
pytest -v poc_v2/length/tests/test_length_regression.py        # 16/16
pytest -v poc_v2/length/tests/test_spec_regression.py          # 25/25
pytest -v poc_v2/baseline2/tests/test_baseline2_regression.py  # 19/19
pytest -v poc_v2/baseline2/tests/test_baseline3_regression.py  # 33/33
pytest -v poc_v2/baseline2/tests/test_baseline4_regression.py  # 19/19
pytest -v poc_v2/baseline2/tests/test_baseline5_regression.py  # 16/16
pytest -v poc_v2/baseline2/tests/test_baseline6_regression.py  # 48/48
pytest -v poc_v2/baseline2/tests/test_baseline7_regression.py  # 신규
```

---

## 7. 제약사항

### 7.1 절대 금지
- 본선 모듈 수정
- yaml 수정 (`symbol_rules.yaml`, `length_routing.yaml`)
- 정답지 수정
- 기존 baseline 모듈을 분리본 케이스만으로 좁히는 수정 (도면4·5·3·2·1 회귀 깨짐)
- 외부 라이브러리 추가
- LLM·VLM 호출

### 7.2 허용 (조건부)
- `sheet_name_matcher` 또는 호출부에 **일반화된 분리본 매칭 룰** 추가
- fallback yaml에 매칭 실패 케이스 등록 (자동 매칭 실패한 것만)

### 7.3 결정론
LLM·랜덤 0건. 동일 입력 → 동일 출력.

---

## 8. 작업 순서

1. **작업 0** — 회귀 8종 기록
2. **작업 1** — 결합 시트명 인벤토리 + split 룰 정의
3. **작업 2** — sheet_name_matcher 보완
4. **작업 3** — 누적 한계 3종 검증
5. **작업 4** — 회귀 8종 무영향 (필수)
6. **작업 5** — CSV + 보고서
7. **작업 6** — 회귀 테스트 신규

**중간 보고**:
- 작업 1 후 split 룰 명세 (사용자 검토 권장 — baseline-5와 충돌 가능성)
- 작업 3 후 누적 한계 3종 결과
- 작업 4 후 회귀 8종 결과

---

## 9. 산출물 체크리스트

- [ ] `poc_v2/baseline2/sheet_name_matcher.py` 보완
- [ ] `poc_v2/baseline2/tests/test_baseline7_regression.py` (신규)
- [ ] `config/sheet_name_overrides.yaml` 갱신 (필요 시만)
- [ ] `outputs/round_baseline7_분리본검증.csv`
- [ ] `outputs/round_baseline7_보고서.md`
- [ ] 회귀 9종 PASS 유지 확인

---

**문서 끝.**
