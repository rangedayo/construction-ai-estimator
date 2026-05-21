# 라운드 5 — 정책 P (ezdxf 기반 보편 룰) + 좌표 중복 진단

## 현재 상황

- **도면1**: 22/22 정확 일치 ✅ (라운드 3 height 필터로 해결)
- **도면2**: 4/6 통과 (SB/SG height 필터로 해결, SC1·SC2 분리 TEXT는 보류 — 갈래 C)
- **도면4**: 본격 작업은 이번 라운드

## 핵심 방향 결정 (사용자 결정 사항)

1. **회사 무관 보편 룰만 사용.** layer 이름 화이트리스트(`S-SBEAM-SYM` 등) 금지. layer 이름 키워드 매칭(`*beam*`) 도 금지. 회사마다 layer 이름이 달라서 무한 패치 함정.
2. **외부 도구(PaddleOCR PP-Structure, DBSCAN, Shapely 등) 도입 보류.** 1단계는 ezdxf 본질에 집중. 2단계에서 통합 검토.
3. **도면4를 정책 P로 진행. 5% 오차 일부 남아도 1단계 마무리하고 2단계 진입.** 완벽주의로 1단계에 발 묶이지 말 것.

## 정책 P 정의 — ezdxf 기반 보편 룰

회사·도면 무관하게 작동하는 신호 두 개:

### 신호 1 — 일람표 검출 (좌표·종류 분포)
- 도면 폭(또는 부재 표시 영역 폭)의 1/30 이내 좁은 bbox 안에
- N종(예: 4종) 이상의 서로 다른 부호가 각 1~2회씩만 등장
- → 그 영역은 일람표로 분류, 카운트 제외

근거: 일람표는 "표"라는 정의상 회사 무관 패턴.

### 신호 2 — 규격 안내 식별 (텍스트 형태)
- 텍스트가 `'부호 + 공백/하이픈/줄바꿈(\P) + 규격 패턴'` 형태
- 예: `'SC1\PH 350x175x7/11'`
- → 카운트 제외 (단 라운드 2의 BR2 부분 일치 매칭과 충돌 회피)

근거: 규격은 회사·국가 무관하게 별도 표기 패턴.

### 신호 3 — 좌표 중복 진단 (자동 제거 X)
- 같은 부호의 ATTRIB/TEXT/MTEXT가 1mm 이내 동일 좌표에 N개 존재
- → 경고 메모로 출력. 카운트는 그대로. 적산 전문가 검수 단계 위임.

---

## 라운드 5 작업 원칙

1. 한 번에 하나만 변경. 변경마다 회귀 테스트.
2. 도면 특성은 yaml로. counter.py에 하드코딩 금지.
3. **외부 도구 추가 금지** — DBSCAN, OCR, 비전 모델, Shapely.
4. **도면1 22/22 정확 일치는 절대 깨지면 안 됨.**
5. **도면2 분리 TEXT 결합 룰 추가 금지** (갈래 C 유지).
6. **layer 이름 매칭 금지** (사용자 결정).

---

## 작업 1 — 일람표 영역 검출 함수 (counter.py 외부)

새 모듈 `poc_v2/tests/detect_table_region.py`. counter.py 미변경:

```python
def detect_table_regions(
    coords_by_symbol: dict[str, list[tuple[float, float]]],
    drawing_extent: tuple[float, float, float, float],
    region_size_ratio: float = 1 / 30,
    min_distinct_symbols: int = 4,
    max_count_per_symbol: int = 2,
) -> list[dict]:
    """일람표 후보 영역 검출.
    
    반환: [{"bbox": (xmin,ymin,xmax,ymax), 
            "symbols": {"SC1":2, "SC2":2, ...}}, ...]
    """
```

알고리즘:
- 도면 부호 좌표를 그리드 셀(셀 크기 = `드로잉 폭 × region_size_ratio`)로 분할
- 각 셀의 *서로 다른 부호 수*와 *부호당 등장 수* 계산
- 두 조건 만족 셀 → 일람표 후보

파라미터는 yaml에서 조정:
```yaml
table_region_detection:
  region_size_ratio: 0.033
  min_distinct_symbols: 4
  max_count_per_symbol: 2
```

---

## 작업 2 — 규격 안내 텍스트 식별 (counter.py 내부)

`match_symbol`에 옵션 추가. 기존 BR2 부분 일치는 유지:

```python
def match_symbol(
    text: str, 
    whitelist: list[str],
    exclude_with_spec: bool = False,
) -> str | None:
    text = text.strip()
    if text in whitelist:
        return text
    for w in whitelist:
        if text.startswith(w + " ") or text.startswith(w + "-") or text.startswith(w + "\\P"):
            if exclude_with_spec:
                return None    # 규격 안내는 카운트 안 함
            after = text[len(w):]
            if after and after[0].isdigit():
                continue
            return w
    return None
```

**주의:**
- `exclude_with_spec=False`(기본값)이면 기존 동작 그대로 → 도면1·2 회귀 안 깨짐
- yaml로 도면별 설정. 도면4만 활성화.
- **도면2에 `exclude_with_spec=True` 적용 금지** — BR2 매칭(`'BR2 L-80X80X7'` → BR2)이 깨짐. 도면4는 BR2 없어서 안전.

---

## 작업 3 — yaml에 정책 P 도면별 설정 추가

```yaml
# 기존 (라운드 3)
text_height_filter:
  도면1: { min_height: 177 }
  도면2: { min_height: 302 }
  도면4: { min_height: null }

# 신규
policy_p:
  도면1:
    exclude_table_regions: false
    exclude_with_spec: false
  도면2:
    exclude_table_regions: false
    exclude_with_spec: false    # BR2 매칭 보호
  도면4:
    exclude_table_regions: true
    exclude_with_spec: true

table_region_detection:
  region_size_ratio: 0.033
  min_distinct_symbols: 4
  max_count_per_symbol: 2
```

---

## 작업 4 — `counter.py`에 좌표 중복 진단 함수 추가 (제거 X)

별도 함수로 진단만:

```python
def diagnose_duplicate_coords(
    coords_by_symbol: dict[str, list[tuple[float, float]]],
    tolerance_mm: float = 1.0,
) -> dict[str, list[dict]]:
    """동일 좌표(tolerance 이내) 부호 중복 진단."""
```

baseline.py·test_regression.py가 카운트와 별개로 호출. **카운트는 그대로 유지, 메모만 추가.**

---

## 작업 5 — ground_truth.py에 yaml 로더 추가

라운드 3 패턴 따라:

```python
def load_policy_p() -> dict[str, dict]: ...
def load_table_region_params() -> dict: ...
```

---

## 작업 6 — baseline.py 출력 확장

기존 표 + 메모 컬럼:

```
부호    예측   정답   차이   오차%   상태   메모
SB1     48     36     +12    33%    FAIL   ⚠ 동일 좌표 12곳에 2개씩
SC1     14     14     0      0%     PASS
```

추가로 별도 섹션:

```
[정책 P 진단]
- 일람표 후보 영역: 1곳
  bbox: (xmin, ymin) ~ (xmax, ymax)
  포함 부호: SC1(2), SC2(2), SB1(2), SG1(2)
- 규격 안내 텍스트: 18개 (예: SC1\PH 350x175x7/11)
- 좌표 중복: SB1 12곳 24개 (경고만, 카운트 그대로)
```

---

## 작업 7 — 모든 도면에서 정책 P 진단 + 베이스라인 실행

```bash
python tests/baseline.py 도면1
python tests/baseline.py 도면2
python tests/baseline.py 도면4
```

**기대 결과:**

| 도면 | 라운드 4 통과 | 라운드 5 통과 (예상) | 주요 변화 |
|---|---|---|---|
| 도면1 | 22/22 | 22/22 | policy_p 비활성 → 변화 없음 |
| 도면2 | 4/6 | 4/6 | policy_p 비활성 → 변화 없음 |
| 도면4 | 1/4 | **3/4** | 일람표·규격 안내 제외 |

**도면4 예상 상세:**
- SC1: 14 ✅ (규격 안내 `SC1\PH...` 14개 제외)
- SC2: 4 ✅ (규격 안내 4개 제외)
- SG1: 14 ✅
- SB1: 좌표 중복으로 여전히 FAIL — **사용자 결정대로 1단계는 여기서 마무리, 경고 메모로 처리**

---

## 작업 8 — 회귀 테스트 통과 확인

```bash
pytest -v tests/test_regression.py
```

도면1이 단 하나라도 깨지면 즉시 중단 보고.

---

## 작업 9 — 멘토 보고용 리포트

`round5_정책P_좌표중복_진단.md` 작성:

### A. 1단계 진척 최종 요약
- 도면1: 22/22 ✅
- 도면2: 4/6 (SC 보류)
- 도면4: 3/4 (SB1 좌표 중복 경고 메모)

### B. 정책 P 정의 및 적용 결과
- 일람표 영역 자동 검출 알고리즘
- 규격 안내 텍스트 식별 알고리즘
- 도면4 적용 결과 표

### C. 좌표 중복 진단 결과 (모든 도면)
- 도면1·2·4 각각의 중복 현황
- 도면4 SB1 12쌍이 +12 차이를 정확히 설명

### D. 1단계 마무리 선언 및 2단계 진입 의제

**1단계 미해결 항목:**
- 도면2 SC1·SC2 분리 TEXT (갈래 C로 보류)
- 도면4 SB1 좌표 중복 (적산 전문가 검수 단계 위임)

**2단계 진입 시 도구 재검토:**
- PaddleOCR PP-Structure (일람표 추출 자동화)
- DBSCAN (영역 클러스터링 정교화)
- 도면2 SC 갈래 A/B/C 최종 결정
- 비전 모델 (도면2 SC, 도면4 SB1 중복 검증)

### E. 1단계 핵심 학습
- "도면별 특성은 yaml로" 원칙 검증
- "AI는 결정만, 도구는 측정만" 원칙 검증
- catastrophic regression 방지 회귀 테스트 효과
- 멘토 미팅 의제: 1단계 종료 선언, 2단계 킥오프

---

## 최종 보고 형식

1. **변경 파일 목록** (yaml, counter.py, ground_truth.py, baseline.py, 새 모듈 detect_table_region.py)
2. **도면1·2·4 baseline 결과 표** (메모·정책 P 진단 포함)
3. **회귀 테스트 결과** (도면1 22/22 유지)
4. **정책 P 진단 결과 표**
5. **`round5_정책P_좌표중복_진단.md` 전문**

---

## 라운드 5 종료 조건

- ✅ 도면1: 22/22 유지 (절대)
- ✅ 도면2: 4/6 유지
- ✅ 도면4: SC1·SC2·SG1 정확 일치, SB1은 FAIL + 좌표 중복 경고
- ✅ 정책 P 모든 도면 진단 적용
- ✅ counter.py 매칭 룰 핵심 미변경 (BR2·블록·height 유지)
- ✅ layer 이름 매칭·외부 도구 도입 없음

여섯 만족 시 **1단계 종료 선언, 2단계 진입 준비**.

## 라운드 6 예고

라운드 6 = 2단계(부호 → 규격 매칭) 진입. 

도면4의 `G-MEMBGUIDE` MTEXT가 1단계엔 제외 대상이지만 2단계엔 핵심 규격 데이터. 도면2 SC, 도면4 SB1 미해결 항목은 2단계 통합 도구 검토 후 재방문.
