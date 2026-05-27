# 라운드 길이-4 본작업 명세서 (초안 v0.1)

> **작성 목적**: 길이-4 라운드 = 부호별 규격 추출 + 단위중량 룩업 + 총중량 산출. 
> 이 명세서를 Claude Code에 전달해 구현하기 전에, 사용자·멘토와 합의용으로 작성.
>
> **읽는 순서 추천**: 0 → 1 → 2 → (필요시 7 제약사항 먼저) → 3 → 4 → 5 → 6 → 8 → 9

---

## 0. TL;DR (한 페이지 요약)

| 항목 | 내용 |
|---|---|
| **목표** | 도면1~5의 기둥 부재에 대해 `총중량(kg) = 개수 × 길이(m) × 단위중량(kg/m)` 산출 |
| **핵심 신규 모듈** | `poc_v2/length/spec_extractor.py` (부호↔규격 추출), `poc_v2/length/unit_weight.py` (단위중량 룩업), `poc_v2/length/total_weight.py` (총중량 합산) |
| **본선 영향** | counter.py / baseline.py / yaml 미수정. 1단계 회귀 14/16 유지 |
| **신규 데이터** | `config/unit_weight_table.yaml` (KS D 3502 H형강 단위중량) |
| **정답지** | `도면_길이_정답지.xlsx` 비고에서 규격 자동 파싱하여 검증 |
| **검증 기준** | (1) 1단계 14/16 회귀 유지, (2) 규격 추출 정답율, (3) 총중량 산출 가능 케이스 보고 |
| **산출물** | `outputs/round_length4_보고서.md`, `outputs/visualize/도면N_specs_기둥.html`, `outputs/round_length4_총중량.csv` |

---

## 1. 배경

### 1.1 PoC 전체 진행 단계

```
1단계 (개수)   ✅ 14/16 PASS — 부호별 카운트
길이-1 (길이)  ✅ 16/16 PASS, 오차 0mm — 세로 DIMENSION 최댓값
길이-4 (이번)  ⏳ 규격 + 단위중량 + 총중량
```

### 1.2 총중량 산출 공식

```
총중량(kg) = 개수 × 길이(m) × 단위중량(kg/m)
```

- **개수**: 1단계 카운트 결과 그대로 사용 (변경 없음)
- **길이**: 길이-1 측정 결과 그대로 사용 (변경 없음)
- **단위중량**: KS D 3502 H형강 표준 (신규 룩업 테이블)
- **규격**: 단위중량 룩업의 키 (신규 추출 대상)

### 1.3 사전조사 결과 (도면1 일람표 검출 실패)

라운드 길이-4 사전조사 (`outputs/round_length4_사전조사_도면1일람표.md`)에서 발견:

- **원인**: H1 (height 176.4 < min_height 177) + H3 (min_distinct_symbols=4 미달) 직렬 차단
- **결론**: detect_table_regions 임계 미수정. 독립 수집기 분리로 우회.

---

## 2. 목표 (산출물)

### 2.1 최종 산출물

각 도면·동·부호에 대해:

```
{
  "drawing": "도면1",
  "section": "1동",           # null 또는 동 식별자
  "symbol": "MC1",
  "count": 12,                # 1단계 결과 인용
  "length_mm": null,          # 길이-1 결과 인용 (1동은 측정 불가)
  "spec": "H-588x300x12/20",  # 길이-4 신규 추출
  "spec_note": null,          # "(현장제작)" 등 부가 메모
  "unit_weight_kg_per_m": 154.0,  # 단위중량 룩업 결과
  "total_weight_kg": null,    # 길이 없으면 산출 불가, null
  "skip_reason": "1동 길이 측정 불가 (소스 도면 없음)"
}
```

### 2.2 산출 가능/불가 케이스

| 도면·동 | 개수 | 길이 | 규격 | 총중량 |
|---|---|---|---|---|
| 도면1 1동 | ✅ | ❌ (소스 없음) | ✅ (이번 라운드) | ❌ |
| 도면1 2동 | ✅ | ✅ (6000mm) | ✅ (이번 라운드) | ✅ |
| 도면2 | ✅ | ✅ (7700mm) | ✅ (이번 라운드) | ✅ |
| 도면3 | ✅ | ✅ (19060mm) | ✅ (이번 라운드) | ✅ |
| 도면4 | ✅ | ✅ (9000mm) | ✅ (이번 라운드) | ✅ |
| 도면5 | ✅ | ✅ (10500mm) | ✅ (이번 라운드) | ✅ |

→ 5/6 케이스 총중량 산출 가능. 1/6은 길이 측정 불가로 보류 (이번 라운드 범위 외).

---

## 3. 설계 원칙

### 3.1 독립 수집기 분리 — 회귀 안전망 절대 조건

**왜 분리하는가**: 카운팅 파이프라인과 규격 추출은 텍스트를 보는 목적이 정반대.

| | 카운팅 (기존 counter.py) | 규격 추출 (신규 spec_extractor.py) |
|---|---|---|
| height 필터 | 적용 (작은 글자 = 노이즈) | 미적용 (작은 글자 = 정답) |
| 일람표 영역 | 제외 대상 | 정답 소스 |
| 결과 | 부호별 개수 | 부호별 규격 |

**보장**:
- counter.py / baseline.py / config/symbol_rules.yaml 무수정
- detect_table_regions 임계값 (min_distinct_symbols=4 등) 무수정
- 1단계 회귀 14/16 PASS 그대로

### 3.2 "AI는 결정만, 도구는 측정만" 원칙

- 일람표 안의 부호↔규격 매핑: 코드가 좌표·y띠로 측정
- 규격 정규식: 코드가 결정론적으로 적용
- 단위중량 룩업: 결정론적 yaml 테이블

LLM·RAG 도입은 이번 라운드 범위 외 (다음 라운드 후보).

### 3.3 보편 룰 우선, 도면별 특수성은 yaml override로 최소화

- 도면명 하드코딩 금지
- 도면별 차이는 일람표 구조(컬럼 수, H 접두사 유무 등)의 보편 변형으로 처리

---

## 4. 도면별 일람표 구조 — 사전조사 종합

사용자가 보내준 일람표 이미지 5장에서 직접 확인된 구조.

### 4.1 도면1 — 2벌 일람표 (동별)

**1동 일람표** (1~3층 기둥주심도):
```
구 분 │ 부 호 │ 크 기              │ 비 고
기 둥 │ MC1  │ H- 588x300x12/20  │ SM355
      │ MC2  │ H- 200x200x8/12   │ SM275
```

**2동 일람표** (기둥주심도):
```
구 분 │ 부 호 │ 크 기              │ 비 고
기 둥 │ MC1  │ H- 400x200x8/13   │ SM275
      │ MC2  │ H- 440x300x11/18  │ SM275
      │ MC3  │ H- 250x250x9x14   │ SM275
      │ SC1  │ H- 300x150x6.5/9  │ SM275
```

**특이사항**: 같은 부호(MC1, MC2)가 동마다 다른 규격 → **(도면, 동, 부호) 키 필요**.  
**동 판별**: 일람표 근처의 시트 제목 텍스트 `(1동)`, `(2동)`에서 추출.

### 4.2 도면2 — 영문 헤더 `MEMBER LIST`

```
MARK  │ MEMBER LIST       │ MAT'L
SC1   │ H-250x125x6.0x9.0 │ SS275
SC2   │ H-200x100x5.5x8.0 │ SS275
BRACE │ Ø19R-BAR(W/T.B)   │
```

**특이사항**: BRACE는 부호명이 아니라 부재 종류. 가새는 적산 외 → 무시.

### 4.3 도면3 — 4컬럼, H 접두사 없음

```
C1 │ 600x407x20x35 (현장제작) │ P1 │ 500x700
C2 │ 428x407x20x35           │ P2 │ 500x500
C3 │ 400x400x13x21           │ P3 │ 500x500
C4 │ 300x300x10x15           │ P4 │ 400x400
```

**특이사항**:
- H 접두사 없음 (정규식 `H?` 선택 캡처)
- C/P 합성기둥: 한 행에 부호 2종 + 규격 2종 → x 거리 매칭
- P1~P4는 콘크리트 기둥 (적산 외)

### 4.4 도면4 — 일람표 4개 분리

```
■ 기둥 일람표:    SC1 H 350x175x7/11, SC2 H 194x150x6/9
■ 가새 일람표:    SBR1 SR 20         (적산 외)
■ 매트기초 일람표: MF1 400 (두께)     (적산 외)
■ 재료강도:       콘크리트 C24, 철근 SD400, 철골 SS275
```

**특이사항**:
- 일람표 종류별 4개로 분리. "■ 기둥 일람표"라는 제목 텍스트로 식별
- H와 숫자 사이 공백 (`H 350x175x7/11`)
- 강재 등급은 재료강도 표에 통합 — 이번 라운드 무시

### 4.5 도면5 — 도면3과 동형, H 접두사 없음

```
C1 │ 300x300x10x15 │ P1 │ 400x400
C2 │ 250x250x9x14  │ P2 │ 300x300
C3 │ 450x200x9x14  │ P3 │ 300x600
C4 │ 200x200x8x12  │ P4 │ 300x300
```

---

## 5. 데이터 구조

### 5.1 정답지 (`도면_길이_정답지.xlsx` 비고)

비고 형식 (이미 사용자가 작성 완료):
```
{부호} 규격: {규격 원문} [(부가 메모)]
```

예시:
- `MC1 규격: H-588x300x12/20`
- `C1 규격: 600x407x20x35 (현장제작)`
- `SC1 규격: H 350x175x7/11`

**원본 보존 원칙**: 일람표에 적힌 그대로 (H 접두사 유무, 공백 차이 포함).  
**등급 제외**: 이번 라운드는 중량 계산이 목표라 등급 무관.

### 5.2 단위중량 테이블 (`config/unit_weight_table.yaml`)

KS D 3502 표준에서 도면1~5에 등장하는 H형강만 우선 수록.

```yaml
# H형강 단위중량 (kg/m) — KS D 3502 기준
# 키 형식: H-{H}x{B}x{tw}x{tf}  (모두 mm)
H형강:
  # 도면1 1동
  "H-588x300x12/20": 151.0    # MC1
  "H-200x200x8/12":   49.9    # MC2
  # 도면1 2동
  "H-400x200x8/13":   65.4
  "H-440x300x11/18": 124.0
  "H-250x250x9x14":   71.8
  "H-300x150x6.5/9":  36.7
  # 도면2
  "H-250x125x6.0x9.0": 29.6
  "H-200x100x5.5x8.0": 21.3
  # 도면3
  "H-600x407x20x35": 175.0    # 현장제작 (KS 표준 외 가능성, 멘토 확인 필요)
  "H-428x407x20x35": 140.0
  "H-400x400x13x21": 172.0
  "H-300x300x10x15":  94.0
  # 도면4
  "H-350x175x7/11":   49.6
  "H-194x150x6/9":    30.6
  # 도면5
  "H-450x200x9x14":   66.2
  "H-250x250x9x14":   71.8    # 도면3과 중복 — 정상
  "H-200x200x8x12":   49.9    # 도면1 1동과 동형 — 정상
  "H-300x300x10x15":  94.0    # 도면3과 중복 — 정상
```

> **주의**: 위 단위중량 값은 명세서 작성 시 임의로 적은 예시. **실제 KS D 3502 표를 참조해 정확한 값으로 채워야 함**. 작업 단계에서 멘토 검토 또는 KS 자료 참조 필수.

### 5.3 spec_extractor 출력 스키마

```python
@dataclass
class SpecExtraction:
    drawing: str           # "도면1"
    section: str | None    # "1동" | "2동" | None
    symbol: str            # "MC1"
    spec_raw: str          # "H- 588x300x12/20" (도면 원본 그대로)
    spec_normalized: str   # "H-588x300x12/20" (단위중량 룩업용)
    spec_note: str | None  # "(현장제작)" 등
    
    # 추출 위치 정보 (시각화·디버깅용)
    table_region_idx: int | None  # 일람표 영역 인덱스
    symbol_coord: tuple[float, float]   # 부호 텍스트 좌표
    spec_coord: tuple[float, float]     # 규격 텍스트 좌표
```

### 5.4 총중량 합산 결과 (CSV)

`outputs/round_length4_총중량.csv`:

```
drawing,section,symbol,count,length_mm,spec,unit_weight_kg_per_m,total_weight_kg,skip_reason
도면1,1동,MC1,12,,H-588x300x12/20,151.0,,1동 길이 측정 불가 (소스 도면 없음)
도면1,1동,MC2,10,,H-200x200x8/12,49.9,,1동 길이 측정 불가
도면1,2동,MC1,15,6000,H-400x200x8/13,65.4,5886.0,
도면1,2동,MC2,4,6000,H-440x300x11/18,124.0,2976.0,
...
```

---

## 6. 세부 작업 단계

### 작업 1 — 단위중량 테이블 yaml 신설

**파일**: `config/unit_weight_table.yaml`  
**내용**: 5.2의 17종 H형강 단위중량.  
**값 확정**: KS D 3502 표 참조. 도면3 `H-600x407x20x35 (현장제작)` 등 KS 외 단면은 별도 메모.  
**로더**: `poc_v2/length/unit_weight.py`의 `load_unit_weight_table()` + `lookup_unit_weight(spec_normalized)` 함수.

### 작업 2 — 규격 정답지 파서 신설

**파일**: `poc_v2/length/ground_truth_spec.py`  
**기능**: `도면_길이_정답지.xlsx`의 비고 컬럼에서 `{부호} 규격: {규격} [(메모)]` 패턴 파싱.  
**출력**: `{(drawing, section, symbol): SpecAnswer(spec_raw, spec_note)}` 매핑.  
**정규식**:
```python
r'^(?P<symbol>\w+)\s*규격:\s*(?P<spec>[^()\n]+?)(?:\s*\((?P<note>[^)]+)\))?\s*$'
```

### 작업 3 — 독립 spec_extractor 신설

**파일**: `poc_v2/length/spec_extractor.py`  
**의존**: ezdxf만. counter.py / baseline.py 호출 없음.  
**입력**: DXF 경로  
**출력**: `list[SpecExtraction]`

**처리 단계**:
1. modelspace의 모든 TEXT/MTEXT 수집 (**height 필터 미적용**)
2. 각 텍스트를 3가지로 분류:
   - **부호 후보**: `^[A-Z]{1,5}\d{1,2}$` 패턴, 화이트리스트 매칭
   - **규격 후보**: `^H?[\s-]*\d+[x×]\d+[x×][\d./]+([x×][\d./]+)?$` 패턴
   - **시트 제목 후보**: `(1동)`, `(2동)`, `1~3층 기둥주심도` 등
3. 부호 후보·규격 후보를 y 띠(±tol) 단위로 그룹핑
4. 같은 y 띠 안에서 부호↔규격 매칭:
   - 부호 1개 + 규격 1개 → 그대로 매칭
   - 부호 N개 + 규격 N개 → x 거리 최소 매칭 (헝가리안 또는 단순 greedy)
5. 동 정보 부여: 매칭된 부호 좌표와 가장 가까운 시트 제목 텍스트에서 `(N동)` 추출 (없으면 None)
6. spec_normalized 생성: `"H- 588x300x12/20"` → `"H-588x300x12/20"` (공백 제거, H 없으면 H- 추가)

**핵심 파라미터** (yaml 노출 또는 함수 인자):
- `y_band_tolerance`: 같은 y 띠로 묶는 허용 범위 (예: ±20)
- `min_symbol_pattern_height`: 부호 후보 최소 height (너무 작은 텍스트는 후보에서 제외)

### 작업 4 — 적산 외 부재 필터링

**무시 대상** (`steel_excluded` 패턴):
- `BRACE`, `SBR\d+` (가새)
- `MF\d+` (매트기초)
- `P\d+` (콘크리트 매입 기둥, C/P 합성의 P부분)
- `BR\d+` (가새, 1단계와 동일 기준)

→ spec_extractor의 부호 후보 단계에서 제외.

### 작업 5 — 도면4 일람표 종류 식별

도면4는 일람표 4개 분리. "기둥 일람표" 안의 부호만 채택.

**식별 룰**:
- 일람표 영역 안에 `기둥 일람표`, `MEMBER LIST` 등의 헤더 텍스트가 있으면 → 채택
- `가새 일람표`, `매트기초 일람표`, `재료강도` 헤더가 있으면 → 제외
- 헤더가 없으면 → 매칭된 부호의 화이트리스트 카테고리(기둥/가새/보)로 역추론

### 작업 6 — 총중량 합산 모듈

**파일**: `poc_v2/length/total_weight.py`  
**입력**: 
- 1단계 카운트 결과 (`baseline.compute_drawing`)
- 길이-1 측정 결과 (`length.baseline_length`)
- 규격 추출 결과 (`spec_extractor`)
- 단위중량 테이블 (`unit_weight`)

**처리**:
1. (drawing, section, symbol) 키로 4개 데이터를 조인
2. 모든 컴포넌트가 있으면 `count × length_mm/1000 × unit_weight` 계산
3. 누락 컴포넌트가 있으면 `skip_reason` 채움

**출력**: 5.4의 CSV

### 작업 7 — 시각화

**파일**: `poc_v2/length/visualize_specs.py`  
**산출**: `outputs/visualize/도면N_specs_기둥.html` × 5

**렌더링**:
- 도면 기하 (회색)
- 매칭된 부호 (녹색 동그라미)
- 매칭된 규격 (파랑 사각형)
- 부호↔규격 페어링 선 (점선)
- 시트 제목 (`(1동)` 등) — 텍스트 라벨

### 작업 8 — 회귀 테스트

**파일**: `poc_v2/length/tests/test_spec_regression.py`  
**검증 항목**:
1. **규격 정확성**: 추출된 spec_normalized == 정답지 spec_normalized (도면 5개 × 부호 18종)
2. **동 식별 정확성**: 도면1의 1동·2동 구분 정확
3. **적산 외 부재 미포함**: P1~P4, BRACE, SBR1, MF1 등이 결과에 없음
4. **1단계 회귀 유지**: `pytest -v poc_v2/tests/test_regression.py` → 14/16 PASS 그대로

### 작업 9 — 보고서

**파일**: `outputs/round_length4_보고서.md`  
**내용**:
- 추출 결과 표 (5/6 케이스 총중량 산출)
- 규격 매핑 정답율
- 도면별 일람표 검출 상태
- 1단계 회귀 미영향 확인
- 알려진 한계 (도면1 1동 길이 부재 등)
- 다음 라운드 후보

---

## 7. 제약 사항

### 7.1 본선 코드 무수정 (절대 조건)

다음 파일·yaml은 **읽기만 가능, 수정 금지**:
- `poc_v2/counter.py`
- `poc_v2/baseline.py`
- `poc_v2/tests/auto_policy.py`
- `poc_v2/tests/detect_table_region.py`
- `poc_v2/tests/classify_text.py`
- `config/symbol_rules.yaml`
- `config/length_routing.yaml`

### 7.2 변경 가능 영역

- 신규 추가: `poc_v2/length/spec_extractor.py`, `unit_weight.py`, `total_weight.py`, `ground_truth_spec.py`, `visualize_specs.py`
- 신규 추가: `poc_v2/length/tests/test_spec_regression.py`
- 신규 추가: `config/unit_weight_table.yaml`
- 신규 추가: `outputs/round_length4_보고서.md`, `outputs/visualize/도면N_specs_기둥.html`, `outputs/round_length4_총중량.csv`

### 7.3 회귀 안전망

- `pytest -v poc_v2/tests/test_regression.py` → 14/16 PASS 유지 필수
- `pytest -v poc_v2/length/tests/test_length_regression.py` → 16/16 PASS 유지 필수

### 7.4 LLM·외부 라이브러리 금지

- DBSCAN, PaddleOCR, Shapely 등 외부 라이브러리 도입 금지 (이전 라운드 원칙 계승)
- LLM·RAG 도입 금지 (다음 라운드 후보)
- ezdxf, plotly, pytest, openpyxl, PyYAML만 사용

---

## 8. 검증 기준

### 8.1 규격 추출 정답율

각 (도면, 동, 부호) 케이스에 대해:
- 추출된 spec_normalized == 정답지 spec_normalized → PASS
- 추출 안 됨 또는 불일치 → FAIL

**목표**: 18/18 PASS (도면1×6 + 도면2×2 + 도면3×4 + 도면4×2 + 도면5×4).

### 8.2 총중량 산출 가능 케이스

**목표**: 5/6 케이스 (도면1 1동 제외) 총중량 산출.

### 8.3 회귀 안전망

- 1단계 14/16 유지
- 길이-1 16/16 유지

### 8.4 적산 외 부재 미혼입

P1~P4, BRACE, SBR1, MF1 등이 결과에 없음 확인.

---

## 9. 산출물 (Deliverables)

| 파일 | 종류 | 설명 |
|---|---|---|
| `poc_v2/length/spec_extractor.py` | 코드 | 독립 규격 추출기 |
| `poc_v2/length/unit_weight.py` | 코드 | 단위중량 룩업 |
| `poc_v2/length/total_weight.py` | 코드 | 총중량 합산 |
| `poc_v2/length/ground_truth_spec.py` | 코드 | 비고 파싱 |
| `poc_v2/length/visualize_specs.py` | 코드 | 시각화 |
| `poc_v2/length/tests/test_spec_regression.py` | 테스트 | 회귀 |
| `config/unit_weight_table.yaml` | 데이터 | KS D 3502 |
| `outputs/round_length4_총중량.csv` | 데이터 | 최종 산출 |
| `outputs/visualize/도면N_specs_기둥.html` × 5 | 시각화 | 도면별 |
| `outputs/round_length4_보고서.md` | 문서 | 라운드 보고 |

---

## 10. 알려진 한계 (다음 라운드 후보)

- 도면1 1동: 길이 측정 소스 없음 → 총중량 산출 불가. 다음 라운드에서 멘토 확인 후 1동 길이 수동 입력 또는 시트 자르기로 해결.
- 보(Beam) 규격·총중량: 이번 라운드 범위 외. 길이-2 라운드에서 보 길이 측정 완료 후 동일 룰 적용.
- 단위중량 테이블 KS 표 검증: 명세서의 임시값을 KS D 3502 정확값으로 교체 필요.
- 도면3 `H-600x407x20x35 (현장제작)` KS 표준 외 단면: 단위중량 실측 또는 멘토 확인.
- LLM 라우팅: 시트 종류 자동 분류 등 자동화 라운드 후보.

---

## 11. 멘토 확인 필요 사항

1. **단위중량 테이블 값** — yaml의 임시값 확인 후 교체
2. **도면1 1동 길이 처리** — 1동 길이 측정 어떻게 할지 (이번 라운드 외)
3. **도면3 현장제작 단면의 단위중량** — 실측인지 표준 추정인지
4. **적산 외 부재 정의 확정** — P, BRACE, SBR, MF 외에 추가 제외 부재 있는지

---

**문서 끝.**
