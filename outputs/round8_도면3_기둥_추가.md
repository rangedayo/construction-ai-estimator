# 라운드 8 — 도면3 기둥 추가 (1단계 회귀 10/12)

작성일: 2026-05-21 · 멘토 보고용

---

## A. 1단계 전체 진척 (라운드 1~8)

| 도면 | 진척 | 비고 |
|---|---|---|
| 도면1 | **100% (22/22)** | 라운드 3 height 필터 (무손상) |
| 도면2 | **4/6** | 라운드 4 height 필터 (SC1·SC2 갈래 C 보류) |
| 도면3 | 0/4 → **4/4 (신규)** | 라운드 8 슬래시 매칭 + 일람표 5컷 + policy_override |
| 도면4 | **3/4** | 라운드 5 정책 P (SB1 좌표 중복 경고) |
| 라운드 8 | **도면3 회귀 신규 통과** | counter.py 슬래시 단어 경계 + baseline.py 5컷 보정 |

회귀 테스트: **10 passed / 2 failed** (도면2 SC1·SC2 — 라운드 5 갈래 C 보류).
**도면1 22건·도면4 3건·도면2 4건 모두 무손상.**

---

## B. 라운드 8 변경 사항

라운드 7 사전 진단으로 정답지 포맷 v2 적응을 마치고, 라운드 8 에서 **도면3 기둥 4종 회귀**를 추가했다. 핵심은 두 가지 보편 룰 보정.

### B-1. `poc_v2/counter.py` — 슬래시 단어 경계 추가

- `match_symbol` 단어 경계에 `/` 추가 → `"C1/P1"` 같은 결합 표기에서 본체 부호 매칭 가능.
- `treat_slash_as_combo` 인자 신설 (`count_members` 시그니처에도 동일).
  - `False` (기본): 슬래시 결합은 None 반환 → 일람표 검출 입력 정리용 (자유 텍스트 좌표 오염 방지).
  - `True`: 본체로 통과 → 회귀 카운트용 (도면3 본체 누락 방지).
- 슬래시 분기를 공백·하이픈 분기와 **분리**. 슬래시는 의미상 "다른 부호와의 결합" 이지 "규격" 이 아니라는 의미론을 코드로 반영.
- MC10 오매칭 방지 룰(부호 뒤 숫자 보호) 유지.

### B-2. `poc_v2/tests/baseline.py` — 일람표 검출 입력 5컷

- `_TABLE_SPARSE_MAX = 5` 상수 도입. `compute_drawing` 의 일람표 검출 입력에서 부호당 자유 텍스트 5개 초과면 **본체 부재로 간주해 제외**.
- 이유: 도면3 본체 부재가 `INSERT`/`ATTRIB`(블록 인스턴스)가 아닌 modelspace `TEXT`/`MTEXT` 로 그려짐. B1(37개)·G1(27개) 등 본체 좌표가 검출 입력을 오염시켜 8방향 인접 연결로 거대 영역이 합쳐졌고, `max_count_per_symbol=2` 룰 탈락.
- `spec_counts` 호출에 `treat_slash_as_combo=True` 전달.
- `_DEFAULT_DXF_FILES` 에 `"도면3": "도면3.dxf"` 등록.

### B-3. `config/symbol_rules.yaml`

```yaml
text_height_filter:
  도면3:
    min_height: null    # 본체 221.8 이 작은글자라 컷 적용 시 본체 사망

policy_override:
  도면3:
    exclude_table_regions: true
    exclude_with_spec: true
```

### B-4. `poc_v2/tests/test_regression.py`

- `drawings` 화이트리스트에 `"도면3"` 추가 → 회귀 케이스 8개 → 12개.

### B-5. 보정 2건의 도면1·2·4 영향 0 검증

| 도면 | 슬래시 매칭 영향 | 5컷 영향 |
|---|---|---|
| 도면1 | 슬래시 텍스트 0개 → 매칭 0건 | 신호 1 자동 OFF, 검출 결과 미사용 |
| 도면2 | 슬래시 텍스트 0개 → 매칭 0건 | 신호 1 자동 OFF, 검출 결과 미사용 |
| 도면4 | 슬래시 텍스트 0개 → 매칭 0건 | 자유 텍스트 좌표 모두 5 이하 → 컷 적용해도 입력 동일 |

→ **도면1·2·4 회귀 영향 0**, 중간·최종 회귀로 검증 완료.

---

## C. 도면3 사전 진단 결과 vs 실제

### C-1. height 분포 — 도면1·2 와 정반대 구조

| height | count | 샘플 | 역할 |
|---|---|---|---|
| 221.8 | 319 | B1, B2, B3, C1/P1, C2/P2 | **본체 (정답)** |
| 225.2 | 2 | C1-600x407x20x35 | 규격 안내 |
| 275.6 | 31 | B1, B2, C1, C2 | 일람표 |
| 337.5 | 2 | CB1, CG2 | 보 부호 (본 라운드 무관) |

- 도면1·2 는 본체가 큰 글자, 작은 글자는 주석/오탐 → `min_height` 위쪽 컷이 정답.
- **도면3 은 본체(221.8)가 가장 작은 글자**, 일람표(275.6)가 더 큼. "큰 갭 위쪽" 알고리즘이 추천한 `min_height=338` 은 본체 전부를 죽임.
- 라운드 6 D항(신호 1 자동화 구조적 불가) 와 같은 함정이 도면3 에서 다시 확인됨.
- 결정: `text_height_filter.도면3.min_height = null` (필터 미적용).

### C-2. 슬래시 결합 표기 발견

| 도면 | 슬래시 텍스트 | 유니크 |
|---|---|---|
| 도면1 | 0 | 0 |
| 도면2 | 0 | 0 |
| 도면3 | 32 | C1/P1, C2/P2, C3/P3, C4/P4 |
| 도면4 | 0 | 0 |

- counter.py 슬래시 매칭 룰 확장의 도면1·2·4 부작용 위험 0 으로 확인 → 보편 룰 안전.

### C-3. 사전 진단 시점의 신호 3 임계값 미달 우려

- 사전 진단: 규격형 텍스트 1개 (`C1-600x407x20x35`), 임계값 4×0.3=1.2 → `1 < 1.2` → 자동 OFF.
- 사전 시뮬레이션: C1=9 (FAIL +1) — C1-spec 1개가 카운트에 흡수.
- 옵션 2 (policy_override 강제 ON) 채택 결정 근거.

### C-4. 실제 결과 (라운드 8 작업 2 완료)

```
부호    예측   정답   차이   오차%   상태
C1        8      8     +0      0%   PASS
C2       15     15     +0      0%   PASS
C3        8      8     +0      0%   PASS
C4        1      1     +0      0%   PASS
```

신호 1(일람표 검출): 1곳 `bbox (6447711.6,-4158500.2)~(6447711.6,-4156500.2)`, `C1(1), C2(1), C3(1), C4(1)` — 정답대로 차감.

---

## D. 회귀 결과

`pytest -v poc_v2/tests/test_regression.py`:

```
2 failed, 10 passed
FAILED test_symbol_total[도면2-SC1]
FAILED test_symbol_total[도면2-SC2]
```

| 케이스 | 결과 | 비고 |
|---|---|---|
| 도면1-MC1·MC2·MC3·SC1 | PASS | 절대 조건 유지 |
| 도면2-SC1·SC2 | FAIL | 라운드 5 갈래 C 미해결 (분리 TEXT) |
| 도면3-C1·C2·C3·C4 | PASS | **이번 라운드 신규** |
| 도면4-SC1·SC2 | PASS | 절대 조건 유지 |

실패 2건은 라운드 4·5 부터의 알려진 보류 항목, 이번 라운드 작업과 무관.

---

## E. 도면1·2·4 무손상 확인

| 도면 | 케이스 | 결과 |
|---|---|---|
| 도면1 | MC1 (15), MC2 (5), MC3 (3), SC1 (7) | 4/4 PASS |
| 도면2 | (회귀 화이트리스트: SC1·SC2) | 0/2 (사전 보류 항목) |
| 도면4 | SC1 (2), SC2 (2) | 2/2 PASS |

- 슬래시 매칭 추가 후 중간 회귀: 라운드 7 baseline 과 동일 (`6 passed / 2 failed`).
- 5컷 보정 추가 후 최종 회귀: 도면1·2·4 6개 케이스 결과 변화 0.
- counter.py 의 슬래시 단어 경계는 도면1·2·4 에 슬래시 텍스트가 0건이므로 기존 매칭 동작 변화 없음을 보장.
- baseline.py 의 5컷은 도면1·2 신호 1 자동 OFF, 도면4 자유 텍스트 좌표가 모두 5 이하라 입력 동일.

→ **절대 조건(도면1 22/22·도면4 3/4 비-SB1·도면2 비-SC) 전부 유지**.

---

## F. `policy_override.도면3` 효과 검증 (신규)

라운드 8 작업 2 종료 후, 멘토와의 사후 검증을 위해 **`config/symbol_rules.yaml` 의 `policy_override.도면3` 을 임시 `null` 로 두고** 회귀를 재실행. 어느 신호가 실제로 결정적인지 분리 측정한다.

### F-1. 검증 방법

1. `policy_override.도면3` 을 임시 `null` 로 설정 (yaml 만 한 줄 토글).
2. `python poc_v2/tests/baseline.py 도면3` 실행 → 자동 판정 결과 캡처.
3. `pytest -v poc_v2/tests/test_regression.py::test_symbol_total` 의 도면3 케이스 4건 결과 캡처.
4. 검증 끝나면 yaml 원복.

### F-2. 결과 표

| 항목 | override 있음 (라운드 8 본작업) | override 없음 (자동) |
|---|---|---|
| 신호 2 (exclude_table_regions) | True (강제) | **False** |
| 신호 3 (exclude_with_spec)     | True (강제) | **True** (자동) |
| spec_pattern_count             | (해당 없음) | 34 (슬래시 매칭 부산물) |
| spec_threshold_count           | (해당 없음) | 6.3 (4 × ratio 후 보정) |
| table_regions_count            | (해당 없음) | 0 (auto_policy 내부 5컷 없음) |
| C1 (정답 8)  | **8 PASS**  | 9 FAIL (+1) |
| C2 (정답 15) | **15 PASS** | 16 FAIL (+1) |
| C3 (정답 8)  | **8 PASS**  | 9 FAIL (+1) |
| C4 (정답 1)  | **1 PASS**  | 2 PASS (±1 허용) |

### F-3. 신호 2 가 결정적인 이유

- `auto_policy._detect_table_regions` 는 `detect_table_region.load_text_layout` 만 호출하고 baseline 의 `_TABLE_SPARSE_MAX=5` 보정을 **거치지 않는다**.
- 그래서 도면3 본체 자유 텍스트(B1 37개·G1 27개 등)가 검출 입력을 오염 → 8방향 인접 연결로 거대 영역이 합쳐져 `max_count_per_symbol=2` 룰 탈락 → 일람표 0곳 검출 → 자동 OFF.
- override 로 `exclude_table_regions: true` 를 강제하면 baseline 자체 검출(5컷 적용 후 1곳)이 차감에 반영돼 C1·C2·C3·C4 각 -1 → 모두 PASS.

### F-4. 신호 3 자동 ON 부산물

- 사전 진단(`outputs/round8_사전진단.md` 1-C) 시점에는 규격형 텍스트가 1개라 임계값 1.2 미달 → 자동 OFF 예측이었다.
- 라운드 8 작업 2 에서 counter.py 슬래시 매칭이 추가되자 `auto_policy._classify_text` 가 **슬래시 결합형 32개(C1/P1·C2/P2·C3/P3·C4/P4)를 "본체 + 규격(P1·P2·...)" 패턴으로 오분류** → `spec_pattern_count` 가 1→34 로 폭증.
- 임계값(부호 4개 × 0.3 + 인플레 보정 = 약 6.3)을 자동 통과 → 자동 판정도 True.
- 결과: override 의 `exclude_with_spec: true` 는 자동과 동일 → **효과 없음**. 사전 진단의 "1개 < 1.2 미달" 우려는 의도치 않게 해소됨.

### F-5. 사후 검증 종합

- 라운드 8 작업 2 보고서(`outputs/round8_작업2_완료보고.md` 7절) 의 결론과 일치.
- override 자체는 라운드 6 가 비상 수단으로 설계한 의도된 기능이고 정상 동작했다.
- 그러나 **신호 2 가 자동 판정에서 False 로 떨어진 이유는 `auto_policy` 와 `baseline` 의 일람표 검출 입력 전처리가 일치하지 않는 구조적 불일치** 때문이다. 도면3 에 한정해서는 override 로 안전하게 메웠지만, 라운드 9 도면5 에서 같은 증상이 재현되는지 확인 후 통일 작업 여부를 결정해야 한다.

---

## G. 1단계 핵심 학습 (라운드 8 추가)

- **`policy_override` 는 라운드 6 설계대로 작동** — 비상 수단이 처음으로 정당하게 사용된 사례(도면3). 자동 판정이 못 잡는 케이스를 yaml 한 줄로 메우는 라운드 6 의 안전망이 의도대로 효력을 발휘했다.
- **구조적 불일치를 솔직히 드러냄** — 사후 검증으로 `auto_policy` 와 `baseline` 의 일람표 검출 입력 전처리가 다르다는 부채를 발견. 라운드 8 을 무리해서 닫는 대신 인계 메모에 명시하고 라운드 9 에서 재현 여부로 통일 작업을 결정한다.
- **사전 진단의 "1.2 미달" 우려가 부산물로 해소됨** — 슬래시 매칭이 `auto_policy._classify_text` 에서 의도하지 않게 spec 카운트를 폭증시킨 경로. 의미론적으론 오분류지만 자동 판정 결과는 우연히 정답에 부합했다. **자동 = 결정론적이라도 의도와 결과가 어긋날 수 있음**을 보여주는 사례 (라운드 6 학습의 변주).
- **보편 룰로 보정** — 라운드 8 의 두 보정(슬래시 의미론 분리, 일람표 5컷)은 도면3 한정 룰이 아니라 modelspace TEXT 본체·결합 표기를 다루는 모든 도면에 유효한 보편 휴리스틱. 라운드 9 보 부호 확장에서도 같은 보정이 그대로 효과를 낼 것으로 기대.

---

## H. 1단계 미해결 항목 업데이트

| 항목 | 라운드 | 상태 | 비고 |
|---|---|---|---|
| 도면2 SC1·SC2 분리 TEXT | 4·5 | 보류 | 갈래 C, `counter.py` TEXT 결합 로직 손질 필요 |
| 도면4 SB1 좌표 중복 | 5 | 보류 | DXF 엔티티 중복, 적산 전문가 검수 위임 |
| 신호 1 (min_height) 자동화 | 6·8 | 보류 | height 무리 구조가 도면마다 정반대, 외부 신호 필요 |
| **auto_policy/baseline 일람표 검출 입력 전처리 불일치** | **8** | **신규** | `auto_policy._detect_table_regions` 는 `_TABLE_SPARSE_MAX=5` 보정 없음. 라운드 9 도면5 에서 같은 신호 2 자동 OFF 가 재현되는지 확인 후 통일 결정 |

### 다음 인계 메모 반영 예정

> **구조적 부채 — `auto_policy._detect_table_regions` 는 `detect_table_region.load_text_layout` 만 호출하고 baseline 의 `_TABLE_SPARSE_MAX=5` 보정을 거치지 않음. 라운드 9 도면5 에서 같은 신호 2 자동 OFF 가 재현되면 두 모듈의 일람표 검출 입력 통일을 결정 (override 제거 가능성). 재현되지 않으면 도면3 특수성으로 확정하고 override 유지.**

---

## I. 라운드 8 종료 조건 점검

- ✅ 도면1 22/22 회귀 무손상
- ✅ 도면2 4/6, 도면4 3/4 회귀 무손상
- ✅ 도면3 4/4 신규 추가
- ✅ counter.py 핵심 매칭 룰 미변경 — 슬래시 단어 경계만 추가, `treat_slash_as_combo` 기본값 `False` 라 기존 호출자 영향 0 (일반화 가능한 보편 룰)
- ✅ 외부 라이브러리·LLM 도입 없음 (ezdxf·pyyaml 만)
- ✅ 보정 2건(슬래시 의미론 분리, 일람표 5컷) 의 도면1·2·4 영향 0 검증
- ✅ 보고서에 구조적 부채(auto_policy/baseline 입력 전처리 불일치) 솔직 명시

→ **일곱 조건 충족. 라운드 8 종료. 라운드 9 (도면3·5 보 부호 또는 도면5 기둥) 진입 준비.**

---

## J. 변경 파일 목록

| 파일 | 변경 |
|---|---|
| `config/symbol_rules.yaml` | `text_height_filter.도면3.min_height: null`, `policy_override.도면3` 추가, 헤더 + 도면3 주석을 사실관계대로 갱신 (라운드 8 마감) |
| `poc_v2/counter.py` | `match_symbol` 단어 경계에 `/` 추가, `treat_slash_as_combo` 인자 신설 (`count_members` 시그니처에도 동일) |
| `poc_v2/tests/baseline.py` | `_DEFAULT_DXF_FILES` 에 도면3 등록, `_TABLE_SPARSE_MAX = 5` 일람표 검출 입력 컷, `spec_counts` 에 `treat_slash_as_combo=True` 전달 |
| `poc_v2/tests/test_regression.py` | `drawings` 화이트리스트에 `"도면3"` 추가 |
| `poc_v2/tests/investigate_도면3.py` | **신규** — 사전 진단 스크립트 |
| `outputs/round8_사전진단.md` | **신규** — 사전 진단 보고서 |
| `outputs/round8_작업2_완료보고.md` | **신규** — 작업 2 완료 보고서 |
| `outputs/round8_도면3_기둥_추가.md` | **신규** — 본 보고서 (라운드 8 마감) |

`auto_policy.py`, `ground_truth.py`, `detect_table_region.py` 는 미변경 (라운드 9 이후 통일 작업 후보).
