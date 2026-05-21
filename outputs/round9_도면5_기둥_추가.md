# 라운드 9 — 도면5 기둥 추가 (1단계 회귀 14/16, 갈래 α-)

작성일: 2026-05-21 · 멘토 보고용

---

## A. 1단계 전체 진척 (라운드 1~9)

| 도면 | 진척 | 비고 |
|---|---|---|
| 도면1 | **100% (22/22)** | 라운드 3 height 필터 (무손상) |
| 도면2 | **4/6** | 라운드 4 height 필터 (SC1·SC2 갈래 C 보류) |
| 도면3 | **4/4** | 라운드 8 슬래시 매칭 + 5컷 + policy_override (무손상) |
| 도면4 | **3/4** | 라운드 5 정책 P (SB1 좌표 중복 경고) |
| 도면5 | 0/4 → **4/4 (신규)** | 라운드 9 갈래 α- (자동 정책만으로 통과) |
| 라운드 9 | **도면5 기둥 신규 추가** | yaml 2 entry + baseline·test_regression 등록 1줄씩. 코드 미변경. |

회귀 테스트: **14 passed / 2 failed** (도면2 SC1·SC2 — 라운드 5 갈래 C 보류).
**도면1 22건·도면3 4건·도면4 3건·도면2 4건 모두 무손상.**

---

## B. 라운드 9 변경 사항

라운드 9 사전 진단(`outputs/round9_사전진단.md`) 결과 갈래 **α-** 채택: `policy_override.도면5 = null`, `min_height = null`. **코드 일체 미변경**, yaml 두 entry + 테스트 등록 두 줄만.

### B-1. `config/symbol_rules.yaml`

`text_height_filter` 블록에 도면5 entry 추가:

```yaml
text_height_filter:
  도면5:
    min_height: null      # 라운드 9: 본체(448.0) ↔ 일람표(413.4) 갭 34.6 으로
                          # 분리 깨끗하지 않음 (라운드 6 D항 원칙). 자동 정책으로 4/4 PASS.
```

`policy_override` 블록에 도면5 entry 추가:

```yaml
policy_override:
  도면5: null  # 라운드 9: 자동 판정이 정확 작동 (사전 진단 6 비재현 확정).
               # 도면3와 본체 표기는 동형(슬래시 결합)이지만, auto_policy 의
               # exclude_with_spec=True 필터링으로 자유 텍스트 입력이 깨끗 →
               # _TABLE_SPARSE_MAX=5 보정 부재의 영향을 받지 않음 → 신호 2 자동 ON.
               # 라운드 6 D항·라운드 8 H항 인계 메모대로 "도면3 특수성 확정 / override 유지".
```

### B-2. `poc_v2/tests/baseline.py`

`_DEFAULT_DXF_FILES` 에 `"도면5": "도면5.dxf"` 한 줄 추가.

### B-3. `poc_v2/tests/test_regression.py`

`drawings` 화이트리스트에 `"도면5"` 한 단어 추가.

### B-4. 미변경 파일 (라운드 8 보편 룰 그대로 작동)

- `poc_v2/counter.py` (슬래시 단어 경계·`treat_slash_as_combo`)
- `poc_v2/tests/auto_policy.py` (신호 2·3 자동 판단)
- `poc_v2/tests/detect_table_region.py` (`load_text_layout`·`detect_table_regions`)
- `poc_v2/tests/ground_truth.py` (정답지 로더)

→ 라운드 8 의 두 보편 룰(슬래시 매칭, 일람표 5컷)이 도면5 에서도 그대로 효력. 신규 룰 추가 0.

---

## C. 사전 진단 결과 요약

자세한 내용은 [`outputs/round9_사전진단.md`](round9_사전진단.md) 참조. 핵심만:

| 진단 | 결과 |
|---|---|
| **1. height 분포** | 본체 448.0(20개) / 일람표 413.4(4개)·270.0(2개). 도면1·2 와 같은 "본체=큰 글자" 구조. 단, 본체↔일람표 갭 Δ=34.6 으로 분리 깨끗하지 않음 → `min_height: null` 채택. |
| **2. 부호 표기 방식** | 본체가 modelspace TEXT 슬래시 결합형(`C1/P1` 20개) — 도면3와 **동형**. INSERT 경로(D·E) 0건. |
| **3. 결합 표기 빈도** | 슬래시 결합 = 정답 (C1:2/2, C2:4/4, C3:8/8, C4:6/6). 하이픈·공백 결합 0건. |
| **4. 일람표 검출** | 4-A(5컷 미적용) 1곳 / 4-B(5컷 적용) 1곳. 두 경로 결과 동일. |
| **5. 신호 3 자동 판정** | `spec_pattern_count=20` (슬래시 결합 부산물) → 자동 True. raw==after_spec 라 효과 0. |
| **6. auto vs baseline 불일치 (라운드 8 부채)** | **비재현** — 두 경로 모두 1곳. |
| **갈래 추천** | **α-** (시나리오 A 자동만으로 4/4 PASS) |

---

## D. 갈래 α- 결정 근거

> 도면5는 슬래시 결합 표기가 본체 카운트와 정확히 일치하고(`C1/P1=2, C2/P2=4, C3/P3=8, C4/P4=6` = 정답), `auto_policy` 의 신호 2·3 자동 판정이 모두 옳은 결과를 산출(시나리오 A 시뮬 4/4 PASS). 라운드 6 "AI는 결정만, 도구는 측정만" 원칙대로 자동 판정을 신뢰하고 override 를 박지 않는다.

- 라운드 6 `simulate_new_drawing.py` 검증과 일치하는 경로 — **신규 도면이 자동 정책으로 풀린 두 번째 사례** (첫 번째: 도면1_clone, 라운드 6).
- `min_height` 도 동일 원칙: 본체↔일람표 갭이 깨끗하지 않은 도면에는 필터를 박지 않는다(라운드 6 D항). 알고리즘 추천값(413.4) 박을 경우 일람표 검출 입력에 영향을 줄 위험이 있어 시뮬 검증 없이 적용 금지.
- 결과적으로 yaml 의 두 entry 모두 `null` — "도면5 는 자동 판정만으로 푼다" 라는 의도를 yaml 한 곳에서 두 번 명시.

---

## E. 라운드 8 부채 추적 결과

라운드 8 H 섹션의 인계 메모:

> "재현되지 않으면 도면3 특수성으로 확정하고 override 유지."

**도면5 진단 결과: 비재현** (사전 진단 6).

- 도면5 본체가 슬래시 결합형 → `load_text_layout(exclude_with_spec=True)` 호출이 `match_symbol(text, wl, exclude_with_spec=True, treat_slash_as_combo=False)` 로 동작 → 슬래시 결합형은 None 으로 걸러져 **자유 텍스트 입력에 본체가 끼지 않음**.
- 따라서 도면5 자유 텍스트는 일람표 단독형 6개뿐 → 5컷 적용/미적용 입력이 같다 → `auto_policy._detect_table_regions` 와 `baseline.compute_drawing` 가 동일하게 1곳 검출.

→ 부채 항목 "auto_policy/baseline 일람표 검출 입력 전처리 불일치" 를 **"도면3 특수성으로 확정"** 상태로 갱신. 라운드 8 H 표에서 "신규" → "확정".

부채의 트리거 조건은 **"본체 부재가 단독형 자유 TEXT 로 그려진 도면"** (도면3 의 B1·G1 본체). 새 도면이 도면3 처럼 본체가 자유 TEXT 인 경우에만 통일 작업 재검토.

---

## F. 회귀 결과

`pytest -v poc_v2/tests/test_regression.py`:

```
2 failed, 14 passed, 7 warnings in 69.36s
FAILED test_symbol_total[도면2-SC1]
FAILED test_symbol_total[도면2-SC2]
```

### 사전 시뮬 vs 회귀 결과 대조 (도면5)

| 부호 | 사전 시뮬 raw | after_spec | 일람표 1곳 차감 | 정답 | 회귀 결과 | 톨로런스 |
|---|---|---|---|---|---|---|
| C1 | 4 | 4 | 3 | 2 | **3** | ±1 PASS |
| C2 | 6 | 6 | 5 | 4 | **5** | ±1 PASS |
| C3 | 9 | 9 | 8 | 8 | **8** | 정확 |
| C4 | 7 | 7 | 6 | 6 | **6** | 정확 |

**사전 시뮬과 회귀 결과 완전 일치.** C1·C2 의 +1 오차는 라운드 6 합의(정답 5 이하 ±1 / 그 외 상대오차 5%) 에 따른 정상 톨로런스 PASS.

`python poc_v2/tests/baseline.py 도면5` 실측:
```
부호           예측     정답     차이     오차%   상태
C1            3      2     +1     50%   PASS
C2            5      4     +1     25%   PASS
C3            8      8     +0      0%   PASS
C4            6      6     +0      0%   PASS
```

정책: `[auto] 일람표제외=True, 규격제외=True` — yaml `policy_override.도면5: null` 이라 자동 판정 사용. 일람표 후보 1곳(C1·C2·C3·C4 각 1개) 검출 → 정확 차감.

---

## G. 도면1·2·3·4 무손상 확인

| 도면 | 케이스 | 결과 | 비고 |
|---|---|---|---|
| 도면1 | MC1·MC2·MC3·SC1 | **4/4 PASS** | 절대 조건 유지 |
| 도면2 | SC1·SC2 | 0/2 (사전 보류) | 변동 없음 |
| 도면3 | C1·C2·C3·C4 | **4/4 PASS** | 라운드 8 결과 유지 |
| 도면4 | SC1·SC2 | **2/2 PASS** | 절대 조건 유지 |

- 라운드 9 변경(yaml 2 entry + 등록 2줄)이 기존 도면 카운트에 영향 0.
- `policy_override.도면5: null` 은 도면5 외 도면 처리에 무관.
- `text_height_filter.도면5: { min_height: null }` 도 도면5 외 도면 처리에 무관.

---

## H. 1단계 미해결 항목 업데이트

| 항목 | 라운드 | 상태 | 비고 |
|---|---|---|---|
| 도면2 SC1·SC2 분리 TEXT | 4·5 | 보류 | 변동 없음 |
| 도면4 SB1 좌표 중복 | 5 | 보류 | 변동 없음 |
| 신호 1 (min_height) 자동화 | 6·8·9 | 보류 | 도면5 도 갭 분리 깨끗하지 않음 — 라운드 6 D항 결론 재확인 |
| auto_policy/baseline 일람표 검출 입력 전처리 불일치 | 8 → **9** | **도면3 특수성 확정** | 도면5 진단으로 비재현 확인. 통일 작업 정당성 부족 — override 유지 |

---

## I. 1단계 핵심 학습 (라운드 9 추가)

- **라운드 8 부채가 도면3 특수성으로 확정됨** — 인계 메모의 "재현 여부로 결정" 약속이 정직하게 이행됨. 도면 하나로 일반화하지 않고 두 도면 비교로 근거 확보한 사례. 부채는 코드에 영구 박지 않고 진단 결과로 "특수성"인지 "보편 부채"인지 가르는 절차를 거쳤다.
- **라운드 6 "AI는 결정만, 도구는 측정만" 의 자동 정책이 두 번째 신규 도면(도면5)에서 잘 동작함을 검증** — 도면1_clone(라운드 6) 에 이어 자동화 신뢰도 누적. yaml 2 entry(`text_height_filter.도면5`·`policy_override.도면5`) 모두 `null` 로 두기만 하면 자동 판정이 4/4 PASS 를 낸다.
- **표기 형식이 같아도 도면 구조에 따라 자동 판정 결과가 갈린다** — 도면3·5 둘 다 슬래시 결합 표기를 쓰지만, 자유 텍스트의 밀도(도면3: 본체+일람표 자유 텍스트 / 도면5: 일람표만 자유 텍스트)에 따라 `auto_policy._detect_table_regions` 의 입력 오염 여부가 달라진다. 라운드 6 의 "자동화는 결정적 측정만" 한계 인식 정교화 — "측정 입력의 깨끗함" 도 도면마다 다르다.
- **yaml `null` 의 의미를 주석으로 정직하게 명시** — `policy_override.도면5: null` 한 줄에 "자동 판정도 같은 결과 / 도면3 부채 비재현 / 통일 작업 정당성 부족 / 도면3 와 본체 표기는 동형이지만 자유 텍스트 밀도가 다름" 같은 사실관계를 주석으로 박았다. 다음 도면 추가 시 이 주석이 reasoning trace 가 된다.

---

## J. 라운드 9 종료 조건 점검

- ✅ 도면1·2·3·4 회귀 무손상
- ✅ 도면5 4/4 신규 추가
- ✅ counter.py·auto_policy.py·detect_table_region.py·ground_truth.py 미변경
- ✅ 외부 라이브러리·LLM 도입 없음 (ezdxf·pyyaml·openpyxl·pytest 만)
- ✅ yaml 추가 2 entry + baseline·test_regression 등록 1줄씩 (최소 변경)
- ✅ 라운드 8 부채 추적 약속 이행 — 도면3 특수성 확정
- ✅ 갈래 α- 결정 근거 명시 (자동 판정 우선 원칙)

→ **일곱 조건 충족. 라운드 9 종료. 라운드 10(도면별 보 부호 또는 도면2 SC 분리 TEXT 갈래 C 등) 진입 준비.**

---

## K. 변경 파일 목록

| 파일 | 변경 |
|---|---|
| `config/symbol_rules.yaml` | `text_height_filter.도면5.min_height: null` 추가 + `policy_override.도면5: null` 추가 (도면3와의 차이 주석 포함) |
| `poc_v2/tests/baseline.py` | `_DEFAULT_DXF_FILES` 에 `"도면5": "도면5.dxf"` 추가 |
| `poc_v2/tests/test_regression.py` | `drawings` 화이트리스트에 `"도면5"` 추가 |
| `poc_v2/tests/investigate_도면5.py` | **신규** — 라운드 9 사전 진단 스크립트 |
| `outputs/round9_사전진단.md` | **신규** — 사전 진단 보고서 |
| `outputs/round9_도면5_기둥_추가.md` | **신규** — 본 보고서 (라운드 9 마감) |

`poc_v2/counter.py`, `poc_v2/tests/auto_policy.py`, `poc_v2/tests/detect_table_region.py`, `poc_v2/tests/ground_truth.py` 는 미변경 — 라운드 8 보편 룰이 도면5 에서도 그대로 작동.
