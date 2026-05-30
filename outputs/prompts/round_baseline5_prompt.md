# 라운드 베이스라인-5 본작업 명세서 — 도면2 검증 (본선 FAIL의 작은 도면 입력 해결 가능성)

> **작성 목적**: 베이스라인-2/3/4에서 확립한 파이프라인을 도면2에 확장.
> **본선 1단계 회귀 14/16 PASS의 유일한 FAIL이 도면2 SC1·SC2**.
> 작은 도면 입력 모델로 가면 이 FAIL이 자연 해결될 수 있는지가 이번 라운드의 핵심 질문.
>
> **읽는 순서**: 0 → 1 → 2 → (제약 7 먼저) → 3 → 4 → 5 → 6 → 8 → 9

---

## 0. TL;DR

| 항목 | 내용 |
|---|---|
| **목표** | 도면2 작은 도면 5개 → 카운트·길이·규격 PASS |
| **핵심 검증 포인트** | (1) **본선 1단계 FAIL이던 도면2 SC1·SC2가 작은 도면 입력에선 PASS인가**, (2) 시트명 줄바꿈 결합 형식 매칭, (3) MEMBER LIST 일람표 형식 처리, (4) 블록 INSERT 카운트 |
| **신규 모듈** | 원칙적으로 없음 — baseline-2/3/4 모듈 재사용 |
| **본선 영향** | `counter.py` / `baseline.py` / `length/baseline_length.py` / `spec_extractor.py` / 모든 yaml 무수정 |
| **회귀 안전망** | 1단계 14/16, 길이-1 16/16, 규격-1 25/25, baseline2 19/19, baseline3 33/33, baseline4 19/19 모두 유지 |
| **이번 범위** | 도면2만. 도면1은 다음 라운드. |
| **PoC 가치 증명 후보** | 도면2 SC1·SC2 PASS 시 "작은 도면 입력 모델이 본선 한계를 자연 해결"을 보고서에 명시 |
| **산출물** | `outputs/round_baseline5_시트별_결과.csv`, `outputs/visualize/도면2_*.html` ×5, `outputs/round_baseline5_보고서.md` |

---

## 1. 배경

### 1.1 베이스라인 누적 결과

| 라운드 | 도면 | 부호 종수 | 결과 | 코드 변경 |
|---|---|---|---|---|
| baseline-2 | 도면4 | 2 (SC1·SC2) | PASS | 모듈 신규 |
| baseline-3 | 도면5 | 4 (C1~C4) | PASS | 매칭 보완 1건 + 차감 룰 도입 |
| baseline-4 | 도면3 | 4 (C1~C4) | PASS | **0건** (override 1줄) |
| **baseline-5** | **도면2** | **2 (SC1·SC2)** | ? | ? |

차감 룰은 부호 2종(도면4) → 4종(도면5·3)에서 시나리오 A로 일관 작동. 도면2도 부호 2종이라
도면4와 같은 패턴 예상.

### 1.2 도면2의 신규 검증 포인트

| # | 검증 포인트 | 위험·기회 |
|---|---|---|
| 1 | **본선 1단계 FAIL의 자연 해결 가능성** | 1단계 14/16의 유일한 FAIL인 도면2 SC1·SC2가 작은 도면 입력에선 PASS일 가능성. PASS면 **PoC 입력 모델 전환의 가장 강력한 가치 증명** |
| 2 | **시트명 줄바꿈 결합 형식** | 정답지 시트명이 `"가,나,다동 1층 구조평면도\n(가,나동 1층 구조평면도)"` 형식 — 줄바꿈으로 두 변형이 결합. 표제부엔 어느 한쪽 또는 다른 표기일 수 있음 |
| 3 | **MEMBER LIST 일람표 형식** | 도면4(한글 "기둥 일람표")·도면5(헤더 없는 4컬럼)·도면3(4컬럼 C/P)와 다른 변형. 영어 헤더 "MEMBER LIST" |
| 4 | **블록 INSERT·ATTRIB 카운트** | 도면2는 1단계 노트에 "익명 블록(`*B479`) 내부 분리 TEXT" 또는 "ATTRIB" 카운트가 필요한 도면으로 명시. 작은 도면에서도 동일 카운트 메커니즘이 작동해야 함 |

### 1.3 정답지 핵심 값 (도면2)

**카운트 (`도면2-기둥` 시트)**:
- `가,나,다동 1층 구조평면도(\n가,나동 1층 구조평면도)`: SC1=10, SC2=4 (합 14)
- 나머지 4개 시트(입면도·종단면도·횡단면도·지붕 구조평면도): 모두 0

**길이 (`도면2-기둥-길이` 시트)**:
- SC1 10개 + SC2 4개 = 14개 인스턴스, 모두 **7700mm**
- 측정 소스: 가,나동 횡단면도

**규격 (`도면2-기둥-길이` 시트 비고)**:
- SC1 = H-250x125x6.0x9.0 SS275
- SC2 = H-200x100x5.5x8.0 SS275

### 1.4 본선 1단계 FAIL 상태 (작업 0에서 명시 기록)

작업 0에서 `pytest -v poc_v2/tests/test_regression.py` 실행 시 도면2 SC1·SC2가 FAIL로
표시되는 그 두 건이 이번 라운드의 비교 기준. 작은 도면 입력 결과와 비교하여:

- **본선 큰 도면 측정값**: 작업 0에서 정확히 몇으로 잡히는지 기록 (예: SC1=0·SC2=0 또는
  SC1=4·SC2=2 같은 부분 잡힘)
- **본선 작은 도면 측정값**: 작업 2 결과
- 두 값을 보고서에 나란히 표시

---

## 2. 목표 (산출물)

### 2.1 도면2 작은 도면 5개 검증

| 파일 | 카운트 정답 | 길이 정답 | 규격 정답 |
|---|---|---|---|
| `도면2_가나동1층구조평면도.dxf` | SC1=10, SC2=4 | N/A | SC1·SC2 2종 |
| `도면2_가나동지붕구조평면도.dxf` | 0 | N/A | (없음) |
| `도면2_가나동종단면도.dxf` | 0 | N/A | (없음) |
| `도면2_가나동횡단면도.dxf` | 0 | 7700 | (없음) |
| `도면2_가나동정면도좌측면도.dxf` (=입면도) | 0 | N/A | (없음) |

분리본(`정면도`, `좌측면도`)이 있으면 cross-check 용도.

### 2.2 CSV·HTML 형식

`outputs/round_baseline5_시트별_결과.csv` — 기존 라운드와 동일 형식, 도면2 5행 + 분리본.
`outputs/visualize/도면2_*.html` × 5 — visualize_small 재사용.

### 2.3 본선 FAIL 비교 표 (보고서에 추가)

```
부호    본선 큰도면(FAIL)    작은도면(이번)    정답    개선?
SC1     예: 0 또는 4         예: 10           10      YES/NO
SC2     예: 0 또는 2         예: 4            4       YES/NO
```

이 표가 보고서 §4에 들어가야 함. 작은 도면 입력 모델의 가치를 가시화.

---

## 3. 설계 원칙

### 3.1 본선 무수정 + baseline-2/3/4 모듈 재사용

신규 코드 없음. 기존 모듈이 도면2에 그대로 동작하는지 검증이 우선.

수정이 필요한 경우:
- 시트명 줄바꿈 결합 매칭이 안 풀리면 → `sheet_name_matcher`에 일반화된 보완 (도면4·5·3
  회귀 PASS 유지)
- MEMBER LIST 헤더가 spec_extractor에서 안 잡히면 → 별도 케이스로 처리, 본선 함수는 무수정

### 3.2 도면2 카운트 메커니즘 점검

도면2는 1단계 노트(`1단계 기둥 개수 세기.md`)에 다음 패턴이 명시:

- 블록 익명 (`*B479` 등) 내부에 분리 TEXT (예: `['SC', '1']` 두 엔티티가 같은 블록에)
- 또는 INSERT ATTRIB로 부호 값

기존 `counter.py`가 이미 이 두 패턴 지원 (블록 정의 내부 TEXT 카운트 + ATTRIB 카운트).
**작은 도면 입력에서도 동일 메커니즘이 작동하는지 확인**.

만약 작은 도면에서도 SC1·SC2가 0으로 잡히면:
- 작은 도면 dxf에 블록 정의가 보존되어 있는지 확인 (분리 시 블록 정의 누락 가능성)
- modelspace의 INSERT 인스턴스와 블록 정의가 짝지어 살아있는지

### 3.3 줄바꿈 결합 시트명 매칭

정답지 시트명: `"가,나,다동 1층 구조평면도\n(가,나동 1층 구조평면도)"`

표제부 텍스트 예상:
- `"가,나,다동 1층 구조평면도"` (메인)
- 또는 `"(가,나동) 1층 구조평면도"`
- 또는 단순 `"1층 구조평면도"`

매칭 전략:
- 정답지 시트명을 줄바꿈으로 split → 두 변형 모두 매칭 후보로 사용
- 표제부 텍스트가 둘 중 어느 하나에 exact 또는 partial 매칭되면 OK
- 정규화 시 `\n`은 공백으로 치환 또는 분할 처리

### 3.4 MEMBER LIST 일람표

spec_extractor에서 `source_table_title`이 "MEMBER LIST"로 잡혀야 함 (라운드 규격-1
보고서에서 이미 확인된 케이스). 차감 룰은 부호 종수 무관하게 페어 수 차감이므로 도면2에서도
동일 작동 예상 — raw [12, 5] → 페어 2개 차감 → [10, 4] PASS.

### 3.5 "AI는 결정만, 도구는 측정만"

LLM·랜덤·외부 호출 0건. 결정론 보장.

---

## 4. 작업 항목

### 작업 0 — 회귀 사전 확인 + 본선 FAIL 값 기록

```bash
pytest -v poc_v2/tests/test_regression.py                      # 14/16
pytest -v poc_v2/length/tests/test_length_regression.py        # 16/16
pytest -v poc_v2/length/tests/test_spec_regression.py          # 25/25
pytest -v poc_v2/baseline2/tests/test_baseline2_regression.py  # 19/19
pytest -v poc_v2/baseline2/tests/test_baseline3_regression.py  # 33/33
pytest -v poc_v2/baseline2/tests/test_baseline4_regression.py  # 19/19
```

**추가로**: 1단계 회귀의 도면2 SC1·SC2 측정값을 구체적으로 기록한다.

```bash
# baseline 측정값 확인 (큰 도면 입력)
python -m poc_v2.tests.baseline --drawing 도면2 2>&1 | grep -E "SC1|SC2"
```

이 값이 보고서 §4의 본선 FAIL 비교 표 좌측 컬럼이 된다.

### 작업 1 — 도면2 표제부 추출·매칭

도면2 5개 파일(통합본) + 분리본에 baseline-2/3/4의 매칭 호출.

**기대**:
- 모든 파일 도면명 추출 성공
- 1층 구조평면도가 정답지의 `"가,나,다동 1층 구조평면도\n(가,나동 1층 구조평면도)"` 시트로 매칭
- 입면도 통합본(`도면2_가나동정면도좌측면도.dxf`)이 정답지 `"가,나동 입면도\n(가,나동 정면도, 가,나동 좌측면도)"`에 매칭
- 횡단면도가 length 라우팅으로

**충돌·실패 시**: 보고 후 매칭 로직 일반화 보완.

### 작업 2 — 도면2 측정 3종 실행

baseline-2의 `small_drawing_pipeline`을 도면2에 호출:

1. 카운트: 1층 구조평면도에서 SC1=10, SC2=4 (정답)
2. 길이: 횡단면도에서 7700
3. 규격: 1층 구조평면도에서 SC1, SC2

원시 측정값 로깅 (차감 전·후, 블록 INSERT 처리 결과).

### 작업 3 — 본선 FAIL 비교 + 차감 룰 판정

**3-1 본선 FAIL vs 작은 도면 결과**:
작업 0의 본선 측정값과 작업 2 결과를 비교해 2.3 표 작성:

- 작은 도면이 PASS면 → "작은 도면 입력 모델이 본선 한계 해결" 명시 (PoC 가치 증명)
- 작은 도면도 FAIL이면 → 동일 한계가 작은 도면에도 적용. 블록 정의 보존 여부 점검

**3-2 차감 룰**:
- raw [12, 5] → 페어 2개 차감 → [10, 4]? 시나리오 A 예상
- B/C 시나리오면 분석

### 작업 4 — 블록 INSERT·ATTRIB 카운트 검증

도면2_가나동1층구조평면도.dxf의 블록 구조 점검:

```python
# 사전 점검 일회성
import ezdxf
doc = ezdxf.readfile('sample_data/도면2_가나동1층구조평면도.dxf')

# 1) modelspace INSERT 인스턴스
inserts = list(doc.modelspace().query('INSERT'))
print(f"INSERT 인스턴스: {len(inserts)}")
for ins in inserts[:5]:
    print(f"  {ins.dxf.name}, ATTRIB: {len(list(ins.attribs))}")

# 2) 블록 정의가 보존되어 있는지
for block in doc.blocks:
    if block.name.startswith('*'):  # 익명 블록
        texts = [e for e in block if e.dxftype() in ('TEXT', 'MTEXT')]
        if texts:
            print(f"익명 블록 {block.name}, TEXT 수: {len(texts)}")
            break
```

이 점검으로 작은 도면 dxf에 블록 정의·INSERT가 살아있는지 확인. counter.py가 활용할 데이터가 있어야 SC1·SC2 카운트 가능.

### 작업 5 — 길이·규격 부수 검증

- 횡단면도 길이 7700 PASS
- 1층 구조평면도 규격 SC1=H-250x125x6.0x9.0, SC2=H-200x100x5.5x8.0 PASS
- MEMBER LIST 일람표 → source_table_title이 정답지의 형식으로 잡히는지

### 작업 6 — CSV + 시각화

baseline-2의 `export_baseline2_csv` 재사용 — `--drawings 도면2`.
visualize_small 재사용으로 도면2 HTML 생성.

### 작업 7 — 회귀 테스트

**파일**: `poc_v2/baseline2/tests/test_baseline5_regression.py` (신규)
**검증 항목**:
1. 도면2 5개 표제부 추출 성공
2. 도면2 5개 매칭 성공
3. 카운트 PASS: 1층 구조평면도 SC1=10, SC2=4
4. 카운트 PASS: 나머지 4개 = 0
5. 길이 PASS: 횡단면도 7700
6. 규격 PASS: SC1, SC2
7. **회귀 무영향**: 기존 6종 모두 PASS 유지
8. 본선 FAIL 비교 표 생성 (보고서용)

### 작업 8 — 보고서

**파일**: `outputs/round_baseline5_보고서.md`
**내용**:
- 도면2 5개 시트별 PASS/FAIL 표
- **§4: 본선 FAIL vs 작은 도면 결과 비교 표** (2.3) — 이번 라운드의 메인 발견
- 줄바꿈 결합 시트명 매칭 결과
- 차감 룰 시나리오 판정
- MEMBER LIST 일람표 처리
- 블록 INSERT 카운트 메커니즘 작동 확인
- 본선 회귀 6종 무영향
- 알려진 한계
- **PoC 가치 증명 결론**: 작은 도면 입력 모델이 본선 1단계 14/16 한계를 자연 해결했는가
- 다음 라운드 후보 (도면1)

---

## 5. 검증 우선순위

1. **사전 점검 (작업 0)** — 본선 FAIL 값 정확히 기록 (비교 기준)
2. **매칭 (작업 1)** — 줄바꿈 결합 시트명이 풀리는지
3. **본선 FAIL 비교 (작업 2~3)** — 이번 라운드의 핵심 발견 가능 지점
4. **블록 INSERT (작업 4)** — 카운트가 정답에서 벗어나면 원인 파악
5. **부수 검증 + 산출물 (작업 5~8)**

작업 3이 핵심. 만약 작은 도면 입력에서도 SC1·SC2가 0으로 나오면 작업 4 점검에서 원인을
파악해야 함.

---

## 6. 본선 영향 점검

작업 종료 후 회귀 7종 모두 PASS 유지:

```bash
pytest -v poc_v2/tests/test_regression.py                      # 14/16 (FAIL은 본선 큰 도면 기준, 이번 라운드 무관)
pytest -v poc_v2/length/tests/test_length_regression.py        # 16/16
pytest -v poc_v2/length/tests/test_spec_regression.py          # 25/25
pytest -v poc_v2/baseline2/tests/test_baseline2_regression.py  # 19/19
pytest -v poc_v2/baseline2/tests/test_baseline3_regression.py  # 33/33
pytest -v poc_v2/baseline2/tests/test_baseline4_regression.py  # 19/19
pytest -v poc_v2/baseline2/tests/test_baseline5_regression.py  # 신규
```

---

## 7. 제약사항

### 7.1 절대 금지
- 본선 모듈 수정 (`counter.py`, `baseline.py`, `length/baseline_length.py`, `spec_extractor.py`)
- yaml 수정 (`symbol_rules.yaml`, `length_routing.yaml`)
- 정답지 수정
- 기존 baseline 모듈을 도면2 케이스만으로 좁히는 수정
- 외부 라이브러리 추가
- LLM·VLM 호출

### 7.2 허용 (조건부)
- 기존 baseline 모듈에 **일반화된 보완** (도면4·5·3·2 모두 PASS 유지)
- fallback yaml에 매칭 실패 케이스 등록 (자동 매칭 실패한 것만)

### 7.3 결정론
LLM·랜덤 0건. 동일 입력 → 동일 출력.

---

## 8. 작업 순서

1. **작업 0** — 회귀 6종 + 본선 FAIL 값 기록
2. **작업 1** — 매칭 검증
3. **작업 2** — 측정 3종 실행
4. **작업 3** — 본선 비교 + 차감 룰 (핵심)
5. **작업 4** — 블록 INSERT 점검 (필요 시)
6. **작업 5** — 부수 검증
7. **작업 6** — CSV + 시각화
8. **작업 7** — 회귀 테스트
9. **작업 8** — 보고서

**중간 보고**:
- 작업 0 후 본선 FAIL 값
- 작업 3 후 본선 vs 작은 도면 비교 표 (핵심 발견)
- 작업 7 후 회귀 7종 결과

---

## 9. 산출물 체크리스트

- [ ] `poc_v2/baseline2/tests/test_baseline5_regression.py` (신규)
- [ ] 기존 baseline 모듈에 매칭 보완 (필요 시만)
- [ ] `config/sheet_name_overrides.yaml` 갱신 (필요 시만)
- [ ] `outputs/round_baseline5_시트별_결과.csv` (도면2)
- [ ] `outputs/visualize/도면2_*.html` × 5
- [ ] `outputs/round_baseline5_보고서.md` (**§4 본선 비교 표 필수**)
- [ ] 회귀 7종 PASS 유지 확인

---

**문서 끝.**
