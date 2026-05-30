# 라운드 규격-1 프롬프트 — 부호별 규격 추출 + 시각화 검증

> **이 라운드의 범위**: 도면1~5에서 부호↔규격 페어링을 **빠짐없이 추출**하고, 
> 사람이 **시각화로 눈으로 검증**할 수 있게 한다.
> **중량 산출은 이 라운드에서 다루지 않는다** (개수 중복·규격 중복 판별이 
> LLM 라우팅으로 먼저 해결돼야 하기 때문 — 아래 §1.3 참조).

---

## 0. TL;DR

| 항목 | 내용 |
|---|---|
| **목표** | 부호↔규격 추출을 전수 보존(dedupe 제거) + 출처 정보 부여 + 시각화 검증 |
| **제외** | 중량 산출(`total_weight`), 단위중량 룩업(`unit_weight`) — 이번 라운드 미사용 |
| **핵심 변경** | (1) spec_extractor dedupe 제거, (2) 출처(source) 필드 추가, (3) 시각화 개선 |
| **본선 영향** | counter.py / baseline.py / yaml 무수정. 1단계 14/16·길이-1 16/16 유지 |
| **검증** | (도면, 부호)별 추출 규격 집합이 정답지 규격과 일치 |
| **산출물** | `outputs/visualize/도면N_specs_기둥.html` ×5, `outputs/round_spec1_규격추출.csv`, `outputs/round_spec1_보고서.md` |

---

## 1. 배경

### 1.1 이전 라운드 (길이-4)에서 한 것

길이-4에서 `spec_extractor.py`로 부호↔규격 추출 + 단위중량 + 총중량까지 구현해
기둥 규격 18/18 추출 성공, 총중량 16/18 산출(임시 단위중량)을 달성했다.
시각화로 검증하던 중 아래 §1.3의 구조적 문제를 발견했다.

### 1.2 이번 라운드에서 바뀌는 것

길이-4 결과물 중 **중량 산출 부분을 들어내고**, 규격 추출의 정확성·완전성에만
집중한다. 중량 코드는 삭제하지 않고 보류한다(LLM 라우팅 라운드 이후 재활용).

### 1.3 왜 중량 산출을 미루는가 — 발견한 함정

중량 = `개수 × 길이 × 단위중량`. 이 중 **개수**와 **단위중량의 키인 규격**에
중복 문제가 있다:

- **개수 중복**: 같은 부재가 여러 도면에 표기됨.
  - 도면4: 1층 구조평면도 SC1 14개 = 지붕층 구조평면도 SC1 14개 = **같은 14개 관통 기둥**. 합산하면 이중 카운트.
  - 도면1: 기둥주심도-1과 부호도-1이 같은 기둥을 중복 표기.
- **규격 중복**: 같은 부호가 여러 일람표에 등장.
  - 도면4: 1층 일람표 SC1·지붕층 일람표 SC1 — 두 곳에 존재(규격은 동일).
  - 같은 부호가 위치마다 다른 규격일 가능성도 있음(현재 도면엔 없으나 일반적으로 가능).

→ "어느 도면/일람표의 값을 진짜로 칠지"는 **LLM 라우팅이 결정할 일**이다.
그게 정해지기 전에 중량을 곱하면 이중 카운트가 발생한다.
**측정(코드)은 전부 보존하고, 결정(어느 걸 쓸지)은 LLM 라우팅 라운드로 미룬다.**
("AI는 결정만, 도구는 측정만" 원칙)

---

## 2. 목표 (산출물)

각 도면의 모든 부호↔규격 페어를 **빠짐없이** 추출하되, 어디서 나왔는지
출처를 함께 기록한다. 중복(같은 부호 여러 건)도 합치지 않고 그대로 보존한다.

```python
@dataclass
class SpecExtraction:
    drawing: str               # "도면4"
    section: str | None        # "1동" | "2동" | None (도면1만 있음)
    symbol: str                # "SC1"
    spec_raw: str              # "H 350x175x7/11" (도면 원본 그대로)
    spec_normalized: str       # "H-350x175x7/11" (표기 정규화)
    spec_note: str | None      # "(현장제작)" 등
    symbol_coord: tuple[float, float]
    spec_coord: tuple[float, float]
    # 신규 — 출처 정보 (C안: dedupe 제거하고 출처 보존)
    source_sheet: str | None       # "1층 구조평면도" | "지붕층 구조평면도" | "(1동)기둥주심도-1"
    source_table_title: str | None # "기둥 일람표" | "보 일람표" | "MEMBER LIST" 등 (있으면)
```

---

## 3. 설계 원칙

### 3.1 전수 보존 (dedupe 제거) — C안

- 기존 spec_extractor의 dedupe 로직을 **제거**한다.
- 같은 (drawing, symbol)이 여러 일람표/위치에서 나오면 **모두 보존**한다.
- 각 건에 출처(source_sheet, source_table_title)를 부여해 나중에 LLM이
  "어느 위치 규격을 쓸지" 판단할 수 있게 한다.

### 3.2 본선 무수정 — 회귀 안전망

- counter.py / baseline.py / auto_policy.py / detect_table_region.py /
  classify_text.py / symbol_rules.yaml / length_routing.yaml 무수정.
- 1단계 14/16, 길이-1 16/16 유지.

### 3.3 측정만, 결정 안 함

- spec_extractor는 부호↔규격을 **측정**만 한다.
- 중복 제거·우선순위 선택 등 **결정**은 하지 않는다 (LLM 라우팅 라운드의 일).

---

## 4. 도면별 일람표 구조 (참고 — 사전조사 종합)

| 도면 | 일람표 구조 | 특이사항 |
|---|---|---|
| 도면1 | 1동(2종)·2동(4종) 2벌 | `(1동)`,`(2동)` 시트 제목으로 section 판별 |
| 도면2 | `MEMBER LIST` 영문 헤더 | BRACE는 적산 외 |
| 도면3 | 4컬럼 C/P | H 접두사 없음, P는 적산 외 |
| 도면4 | 일람표 4종 분리, **1층·지붕층 2시트에 각각** | "■ 기둥 일람표" 헤더, H와 숫자 사이 공백 |
| 도면5 | 4컬럼 C/P | H 접두사 없음, P는 적산 외 |

**적산 외 부재** (현재 `DEFAULT_EXCLUDED_PREFIXES`): P, BR, SBR, MF, BRACE.
→ **이 라운드에서는 이 차감을 유지하되, 보·가새 부호(SB·SG·G·B·RG 등)는
추출되어도 그대로 둔다** (다음 보 라운드에서 활용). 즉 기둥만 남기는 필터는
넣지 않는다 — 전수 보존이 목적.

---

## 5. 세부 작업 단계

### 작업 1 — spec_extractor.py: dedupe 제거 + 출처 추가

1. 기존 dedupe 로직 제거 (모든 추출 보존).
2. `SpecExtraction`에 `source_sheet`, `source_table_title` 필드 추가.
3. **source_sheet 판별**: 부호 좌표(symbol_coord)에서 가장 가까운 시트 제목
   텍스트를 찾아 부여. 시트 제목 패턴 예: `1층 구조평면도`, `지붕층 구조평면도`,
   `(1동) 기둥주심도-1`, `옥상층 기둥주심도` 등.
   (길이-4 진단에서 쓴 "인접 평면도 좌표 거리 판별" 로직 재사용 가능)
4. **source_table_title 판별**: 부호 좌표 위쪽 근처의 일람표 제목 텍스트
   (`■ 기둥 일람표`, `보 일람표`, `MEMBER LIST` 등)를 찾아 부여. 없으면 None.
5. dedupe를 제거했으므로 도면4 SC1은 1층·지붕층 2건으로 보존되어야 한다.

### 작업 2 — 중량 관련 코드 보류 처리

- `total_weight.py`, `unit_weight.py`, `config/unit_weight_table.yaml`은
  **삭제하지 않는다**. 다음 라운드 재활용 예정.
- 이번 라운드의 실행 경로(CLI·시각화·테스트)에서 이들을 **호출하지 않는다**.
- 보고서에 "중량 코드는 보류 상태, LLM 라우팅 이후 재개" 명시.

### 작업 3 — visualize_specs.py 개선

산출: `outputs/visualize/도면N_specs_기둥.html` ×5

개선 사항:
1. **모든 추출 건 표시** (중복도 다 보이게). dedupe 제거 반영.
2. 각 페어링에 **출처 라벨** 표시: `source_sheet` (예: "1층 구조평면도").
3. **section 표시 개선**: 기존 `(-)` 대신, section이 None이면 라벨 생략하고
   대신 source_sheet를 보여준다.
4. 색상 약속:
   - 🟢 녹색 동그라미 = 추출된 부호
   - 🔵 파랑 사각형 = 추출된 규격
   - 점선 = 부호↔규격 페어링
   - 텍스트 라벨 = 부호명 + 출처 시트
5. 같은 부호가 여러 건이면 각각 다른 위치에 표시되어 **중복이 눈에 보이게**.

### 작업 4 — 규격 추출 CSV

산출: `outputs/round_spec1_규격추출.csv`

컬럼:
```
drawing, section, symbol, spec_raw, spec_normalized, spec_note,
source_sheet, source_table_title, symbol_x, symbol_y
```

모든 추출 건(기둥·보·가새 포함, P 등 차감 부재 제외) 수록.

### 작업 5 — 회귀 테스트 (규격 정확성만)

**파일**: `poc_v2/length/tests/test_spec_regression.py` (기존 수정)

검증 항목:
1. **규격 정확성**: 각 (drawing, symbol)에 대해, 추출된 spec_normalized 집합이
   정답지 비고의 spec_normalized를 **포함**하는지 확인.
   - dedupe 제거로 추출 건수가 늘어도, 정답 규격이 그 안에 있으면 PASS.
   - 도면1은 (drawing, section, symbol) 단위로 검증 (1동·2동 구분).
2. **section 정확성**: 도면1의 1동·2동 부호가 올바른 section으로 분류되는지.
3. **적산 외 부재 차감 확인**: P1~P4 등 `DEFAULT_EXCLUDED_PREFIXES`가
   결과에 없는지.
4. **보 부호 보존 확인**: SB·SG 등 보 부호가 결과에 **존재**하는지
   (전수 보존 검증 — 빠지면 안 됨).
5. **중량 테스트 제거/비활성화**: 기존 total_weight 관련 테스트는
   skip 처리 또는 제거 (이번 라운드 범위 외).
6. **본선 회귀 유지**:
   - `pytest -v poc_v2/tests/test_regression.py` → 14/16 PASS
   - `pytest -v poc_v2/length/tests/test_length_regression.py` → 16/16 PASS

### 작업 6 — 보고서

**파일**: `outputs/round_spec1_보고서.md`

내용:
- 라운드 범위 재정의 (규격 추출 + 시각화 검증, 중량 제외)
- 도면별 추출 결과 (기둥·보·가새 건수, 출처 포함)
- 규격 정확성 검증 결과
- §1.3의 함정(개수 중복·규격 중복) 정리 — **다음 LLM 라우팅 라운드의 입력**
- 중량 코드 보류 상태 명시
- 1단계·길이-1 회귀 미영향 확인
- 다음 라운드 후보 (LLM 라우팅, 보 길이 등)

---

## 6. 제약 사항

### 6.1 본선 무수정 (절대 조건)
- counter.py / baseline.py / auto_policy.py / detect_table_region.py /
  classify_text.py / symbol_rules.yaml / length_routing.yaml — 읽기만.

### 6.2 보류 (삭제 금지, 호출 안 함)
- total_weight.py / unit_weight.py / config/unit_weight_table.yaml

### 6.3 변경 가능
- spec_extractor.py (dedupe 제거, 출처 추가)
- visualize_specs.py (시각화 개선)
- ground_truth_spec.py (필요시 검증 로직 조정)
- tests/test_spec_regression.py (규격 정확성 위주로 재구성)
- 신규: outputs/round_spec1_규격추출.csv, round_spec1_보고서.md, 시각화 HTML 갱신

### 6.4 라이브러리·LLM
- ezdxf, plotly, pytest, openpyxl, PyYAML만 사용.
- LLM·RAG·외부 CV 라이브러리 도입 금지 (다음 라운드 후보).

---

## 7. 검증 기준

| 기준 | 목표 |
|---|---|
| 규격 정확성 | 각 (도면[,동], 부호)의 정답 규격이 추출 집합에 포함 |
| section 정확성 | 도면1 1동·2동 정확 분류 |
| 전수 보존 | 도면4 SC1이 1층·지붕층 2건으로 보존 / 보 부호 존재 |
| 적산 외 차감 | P1~P4 등 미포함 |
| 본선 회귀 | 1단계 14/16, 길이-1 16/16 유지 |
| 시각화 | 5개 HTML에서 페어링·출처가 눈으로 검증 가능 |

---

## 8. 알려진 한계 / 다음 라운드 후보

- **중량 산출**: LLM 라우팅으로 개수·규격 중복 판별이 끝난 뒤 재개.
- **LLM 라우팅 (다음 큰 단계)**: 시트 종류 분류, 개수 중복 판별(어느 도면이
  본체인지), 규격 중복 판별(어느 일람표 규격을 쓸지).
- **보 길이/규격**: spec_extractor에 이미 보 부호가 보존됨 → 보 길이 측정 후 결합.
- **도면1 1동 길이**: 측정 소스 부재, 별도 처리.
- **단위중량 KS 검증**: 보류 중인 unit_weight_table.yaml의 임시값 → KS D 3502 확정.

---

**문서 끝.**
