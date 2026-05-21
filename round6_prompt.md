# 라운드 6 — 정책 자동 활성화 (1단계 진짜 완성)

## 현재 상황 (라운드 5 종료 시점)

- **도면1**: 22/22 정확 일치 ✅
- **도면2**: 4/6 통과 (SC 분리 TEXT 보류 — 갈래 C)
- **도면4**: 3/4 통과 (SB1 좌표 중복 경고)
- **회귀 테스트**: 29 passed, 3 failed (모두 보류·위임 합의 항목)

## 라운드 6의 핵심 방향 결정 (사용자 결정 사항)

라운드 5 종료 시점 사용자 평가:

> "지금은 임의로 이 도면 들어오면 이 코드 진행 → 개수 산출로 가는 거잖아"

→ 현재 시스템은 **yaml에 도면별 분기를 사람이 수동으로 박은 상태**. 새 도면 들어오면 yaml 항목 없어서 동작 안 됨.

사용자 결정:
1. **LLM 도입 전에 룰 기반 자동 활성화부터 완성한다.** LLM은 "이 영역이 일람표인가" 같은 진짜 모호한 판단에 아껴 쓴다.
2. **정책 활성화 자체는 결정론적 측정으로 풀린다.** 일람표 영역 검출 여부, 부호+규격 패턴 빈도, height 분포 양분성 — 모두 if 문으로 판단 가능.
3. **라운드 6 = 1단계 진짜 완성.** 자동 활성화까지 완료해야 새 도면(도면5·6·N)에 손 안 대고 적용 가능.

## 작업 원칙 (라운드 3~5와 동일)

1. 한 번에 하나만 변경. 변경마다 회귀 테스트.
2. 외부 도구 추가 금지 (DBSCAN, OCR, 비전, Shapely).
3. **도면1 22/22 정확 일치 절대 깨지면 안 됨.**
4. **도면2 4/6 유지** (SC 보류 그대로).
5. **도면4 3/4 유지** (SB1 좌표 중복 경고 그대로).
6. **layer 이름 매칭 금지** (사용자 결정, 라운드 5 합의).
7. **counter.py 핵심 매칭 룰 미변경** (BR2, 블록 처리, height 필터 유지).

---

## 자동 활성화 알고리즘 정의

### 신호 1: height 분포 양분성 → `min_height` 자동 결정

`policy_p` 와 무관, `text_height_filter` 자동화.

알고리즘:
1. 도면의 정답지 부호 화이트리스트로 전체 텍스트(TEXT/MTEXT/ATTRIB·블록 내부 TEXT) 수집
2. 부호별 height 값을 누적
3. 두 무리 갈림 검사:
   - 모든 height 값을 오름차순 정렬
   - 가장 큰 갭(인접 height 값 차이)을 찾아 그 위치를 후보 컷
   - 그 갭이 *전체 height range의 일정 비율 이상* (예: 30%) 이면 "두 무리"로 판정
4. 두 무리면 → `min_height` = 작은 무리 최댓값 + 1
5. 단일 분포면 → `min_height` = None

**검증 기대값:**
- 도면1: 작은 무리 159·176 / 큰 무리 282~ → `min_height = 177` (현재 yaml 값과 일치)
- 도면2: 작은 무리 301 / 큰 무리 400 → `min_height = 302` (현재 yaml 값과 일치)
- 도면4: 단일 분포 (전부 150) → `min_height = None` (현재 yaml 값과 일치)

### 신호 2: 일람표 영역 존재 → `exclude_table_regions` 자동 결정

기존 `detect_table_region.detect_table_regions()` 재사용.

알고리즘:
1. `detect_table_regions(...)` 실행해 일람표 후보 영역 리스트 받기
2. **검출된 영역 수 ≥ 1** → `exclude_table_regions = True`
3. 0개 → `False`

**검증 기대값:**
- 도면1: 0곳 → False (라운드 2 진단에서 일람표 검출 안 됨 / 단 라운드 2 진단리포트의 "5종 5회" 영역 가능성 있어 실측 필요)
- 도면2: 진단 결과 보고 결정
- 도면4: 1곳 검출 → True (현재 yaml 값과 일치)

⚠️ **도면1에 일람표가 검출되면 충돌**: 현재 도면1은 height 필터만으로 22/22 정확 일치. 일람표 제외가 추가되면 *정상 부재를 깎을 위험*. 검증 시 도면1 카운트가 그대로 22/22인지 반드시 확인.

### 신호 3: 부호+규격 패턴 빈도 → `exclude_with_spec` 자동 결정

알고리즘:
1. 화이트리스트 부호 W에 대해, modelspace에서 `'W 규격패턴'` 형태 텍스트 수 세기
   - 규격 패턴: `\PH`, `H-`, `L-`, `PH `, 또는 `숫자x숫자` 패턴
2. **이런 텍스트가 부호별로 평균 N개 이상** (예: 화이트리스트 부호 수의 절반 이상이 이 패턴을 가짐) → True
3. 그 외 → False

⚠️ **BR2 보호 케이스 자동 식별**:
- 도면2는 `'BR2 L-80X80X7'` 텍스트가 정답에 포함됨 (BR2 부분 일치 매칭으로 BR2=4)
- `exclude_with_spec = True` 가 되면 이 텍스트가 제외되어 BR2=0 → 회귀 깨짐
- 자동 보호 로직: 화이트리스트 중 **부호+규격 형태로만 등장하는 부호**(부호 단독 텍스트가 없음)가 있으면 그 부호는 카운트해야 함 → `exclude_with_spec = False` 강제

**검증 기대값:**
- 도면1: 부호+규격 텍스트 거의 없음 → False (현재 yaml 값과 일치)
- 도면2: BR2 보호 발동 → False (현재 yaml 값과 일치)
- 도면4: SC1·SC2 다수 부호+규격 텍스트 → True, BR2 없음 → 활성화 가능 (현재 yaml 값과 일치)

---

## 작업 1 — 새 모듈 `poc_v2/tests/auto_policy.py` 작성

```python
"""도면을 분석해서 어떤 정책을 켤지 자동 결정 — 룰 기반.

LLM 호출 없음, 외부 라이브러리 없음(ezdxf만). 같은 입력 → 같은 출력.

라운드 5까지 yaml 에 도면별 분기로 박혀 있던 정책 활성화 결정을
도면 분석 결과로 자동 산출한다. yaml policy_override 로 강제 오버라이드 가능.
"""
from __future__ import annotations
import ezdxf
from collections import defaultdict, Counter


def auto_detect_policy(
    dxf_path: str,
    symbol_whitelist: list[str],
    height_gap_ratio: float = 0.3,
    spec_pattern_threshold: float = 0.3,
) -> dict:
    """도면을 분석해서 적절한 정책을 자동 결정한다.
    
    인자:
        dxf_path: DXF 파일 경로
        symbol_whitelist: 도면에서 카운트할 부호 리스트 (정답지 부호)
        height_gap_ratio: height 양분성 판정 임계값 (전체 range 대비 갭 비율)
        spec_pattern_threshold: 부호+규격 패턴 빈도 임계값 (화이트리스트 부호 수 대비)
    
    반환:
        {
            "min_height": float | None,
            "exclude_table_regions": bool,
            "exclude_with_spec": bool,
            "diagnostics": {  # 판단 근거
                "height_distribution": ...,
                "table_regions_count": ...,
                "spec_pattern_count": ...,
                "br2_protection_triggered": ...,
            }
        }
    """
    # 신호 1: height 분포 양분성
    min_height, height_diag = _detect_bimodal_height(
        dxf_path, symbol_whitelist, height_gap_ratio
    )
    
    # 신호 2: 일람표 영역 존재
    table_regions, table_diag = _detect_table_regions_for_policy(
        dxf_path, symbol_whitelist
    )
    exclude_table = len(table_regions) >= 1
    
    # 신호 3: 부호+규격 패턴 빈도
    spec_count, br2_protection, spec_diag = _detect_spec_pattern(
        dxf_path, symbol_whitelist, spec_pattern_threshold
    )
    exclude_with_spec = (spec_count >= len(symbol_whitelist) * spec_pattern_threshold)
    if br2_protection:
        exclude_with_spec = False    # 보호 발동 시 강제 비활성
    
    return {
        "min_height": min_height,
        "exclude_table_regions": exclude_table,
        "exclude_with_spec": exclude_with_spec,
        "diagnostics": {
            "height_distribution": height_diag,
            "table_regions_count": len(table_regions),
            "spec_pattern_count": spec_count,
            "br2_protection_triggered": br2_protection,
        }
    }


def _detect_bimodal_height(dxf_path, whitelist, gap_ratio):
    """height 분포가 두 무리로 갈리는지 검사 + 컷 임계값 결정."""
    # 부호별 height 수집 (ezdxf로 TEXT/MTEXT/ATTRIB·블록 내부 모두)
    # ... 구현 ...
    # 모든 height 정렬, 인접 갭 계산, 최대 갭이 range 대비 gap_ratio 이상?
    # 그렇다면 갭 위 작은 무리 최댓값 + 1을 min_height 로 반환
    pass


def _detect_table_regions_for_policy(dxf_path, whitelist):
    """기존 detect_table_region 모듈 재사용."""
    from detect_table_region import detect_table_regions, collect_free_text_coords
    # ... 구현 ...
    pass


def _detect_spec_pattern(dxf_path, whitelist, threshold):
    """부호+규격 패턴 텍스트 빈도 + BR2 보호 케이스 식별.
    
    BR2 보호 로직:
        화이트리스트 부호 중 어느 부호 W 에 대해
        "W 단독 텍스트가 modelspace 에 0개" 이고
        "'W 규격패턴' 텍스트가 1개 이상" 이면 → 그 부호는 부호+규격 형태로만
        존재함 → exclude_with_spec=True 가 되면 그 부호는 카운트 0 이 됨
        → 보호 발동 (False 강제).
    """
    # ... 구현 ...
    pass
```

---

## 작업 2 — yaml 구조 변경

기존 `text_height_filter`, `policy_p` 의 도면별 분기 *완전 폐기*. 그 자리에 자동 판단 + 오버라이드 구조:

```yaml
# 자동 판단 파라미터 (모든 도면 공통)
auto_policy_params:
  height_gap_ratio: 0.3           # height 양분성 판정 갭 비율
  spec_pattern_threshold: 0.3     # 부호+규격 패턴 빈도 임계값

# 자동 판단 오버라이드 (비상시만 사용, 기본은 null = 자동)
policy_override:
  도면1: null
  도면2: null
  도면4: null
  # 예시: 자동 판단이 잘못된 경우 다음과 같이 수동 강제 가능
  # 도면X:
  #   min_height: 177
  #   exclude_table_regions: false
  #   exclude_with_spec: false
```

`table_region_detection` 파라미터는 유지 (일람표 검출 자체의 파라미터).

⚠️ **주의**: yaml 마이그레이션 시 기존 `text_height_filter`, `policy_p` 키는 *주석 처리*해서 보존 (롤백 가능하게). 완전 삭제 X.

---

## 작업 3 — `ground_truth.py`에 새 로더 추가

기존 `load_text_height_filter()`, `load_policy_p()` 는 **deprecated 처리**:

```python
def load_auto_policy_params() -> dict:
    """auto_policy_params 섹션 로드."""
    ...

def load_policy_override(drawing_name: str) -> dict | None:
    """policy_override[drawing_name] 로드 (null 이면 None 반환)."""
    ...

# 기존 함수는 그대로 두되 호출하지 않음 (yaml 키 주석 처리됐으므로 None 반환)
```

---

## 작업 4 — `counter.py`·`baseline.py`·`test_regression.py` 자동 판단 사용

기존 호출 흐름:
```python
height_filter = load_text_height_filter()
policy_p = load_policy_p()
min_h = height_filter.get(drawing, {}).get("min_height")
table_p = policy_p.get(drawing, {}).get("exclude_table_regions", False)
spec_p = policy_p.get(drawing, {}).get("exclude_with_spec", False)
```

새 흐름:
```python
from auto_policy import auto_detect_policy

# 오버라이드 우선 확인
override = load_policy_override(drawing)
if override:
    policy = override
else:
    symbols = sorted(drawing_symbol_totals()[drawing].keys())
    policy = auto_detect_policy(dxf_path, symbol_whitelist=symbols, ...)

min_h = policy["min_height"]
table_p = policy["exclude_table_regions"]
spec_p = policy["exclude_with_spec"]
```

**중요**: `auto_detect_policy` 는 도면당 1회만 호출. 결과 캐싱 (`functools.lru_cache`).

---

## 작업 5 — 자동/수동 결과 일치 검증

가장 중요한 안전장치. 자동 판단이 라운드 5 yaml 수동 설정과 같은 결정을 내리는지 검증.

`tests/verify_auto_policy.py` 새 스크립트:

```python
"""자동 판단이 라운드 5 수동 yaml 설정과 동일한 결정인지 검증."""

EXPECTED = {
    "도면1": {"min_height": 177, "exclude_table_regions": False, "exclude_with_spec": False},
    "도면2": {"min_height": 302, "exclude_table_regions": False, "exclude_with_spec": False},
    "도면4": {"min_height": None, "exclude_table_regions": True, "exclude_with_spec": True},
}

for drawing in ["도면1", "도면2", "도면4"]:
    auto = auto_detect_policy(...)
    expected = EXPECTED[drawing]
    if auto != expected:
        print(f"⚠ {drawing}: 자동 {auto} vs 수동 {expected} 불일치")
        # 진단 출력으로 어떤 신호에서 어긋났는지 확인
    else:
        print(f"✅ {drawing}: 자동 = 수동 일치")
```

**라운드 6 의 종료 조건 1순위**: 도면1·2·4 자동 판단이 라운드 5 수동 설정과 *완전 일치*.

불일치 시:
1. 임계값(`height_gap_ratio`, `spec_pattern_threshold`) 조정
2. BR2 보호 로직 조정
3. **조정해도 안 맞으면 즉시 중단 보고.** 임의로 임계값 박지 말 것.

---

## 작업 6 — 회귀 테스트 재실행

```bash
python tests/baseline.py 도면1
python tests/baseline.py 도면2
python tests/baseline.py 도면4
pytest -v tests/test_regression.py
```

**기대 결과:**

| 도면 | 라운드 5 | 라운드 6 (자동 판단 적용) |
|---|---|---|
| 도면1 | 22/22 | **22/22** (절대 깨지면 안 됨) |
| 도면2 | 4/6 | **4/6** |
| 도면4 | 3/4 | **3/4** |

회귀 테스트: 29 passed, 3 failed (라운드 5와 동일).

**하나라도 깨지면 즉시 중단 보고.**

---

## 작업 7 — 새 도면 시뮬레이션 (선택)

yaml의 `policy_override` 에 등록 안 된 가상 도면 시나리오:
- 도면1.dxf 를 `도면1_test`라는 새 이름으로 등록 (정답지·DXF 둘 다 복사)
- `policy_override["도면1_test"]` 추가 안 함
- baseline 돌렸을 때 자동 판단으로 도면1과 같은 결과(22/22) 나오는지 확인

이게 통과되면 **새 도면(도면5·6·N)에 손 안 대고 적용 가능**이 증명됨. 1단계 진짜 완성.

(이 작업은 회귀 테스트 우선이라 시간 남으면 진행. 우선순위 낮음.)

---

## 작업 8 — 1단계 종료 리포트 작성

`round6_1단계_완성.md` 파일 작성:

### A. 1단계 전체 진척 (라운드 1~6)
- 도면1: 27% → 32% → **100%** (라운드 1 → 2 → 3)
- 도면2: 4/6 달성 (라운드 4), 라운드 6 유지
- 도면4: 0/4 → 3/4 (라운드 5), 라운드 6 유지
- 라운드 6: 자동 활성화 — 새 도면 무손 적용 가능

### B. 자동 활성화 알고리즘 정리
- 신호 1·2·3 정의와 검증 결과
- 자동/수동 일치 확인

### C. 1단계 최종 미해결 항목
- 도면2 SC 분리 TEXT
- 도면4 SB1 좌표 중복

### D. 2단계 진입 준비
- 도면4 G-MEMBGUIDE MTEXT 가 2단계 핵심 규격 데이터
- LLM 도입 자리 정리: 룰 활성화 자동화 *완료*, 남은 LLM 자리는 *모호한 분류 케이스 해석*
- 도면2 SC, 도면4 SB1은 2단계 통합 도구 검토에서 재방문

### E. 1단계 핵심 학습 (라운드 5 학습 + 라운드 6 학습)
- "AI는 결정만, 도구는 측정만" — 룰 활성화도 결정론으로 가능함을 증명
- 보편 룰의 의미 확장: 알고리즘 보편 + 적용도 자동 (라운드 5에선 적용이 수동이었음)
- 새 도면 무손 적용 가능 = 진짜 1단계 완성

---

## 최종 보고 형식

1. **변경 파일 목록**
2. **자동/수동 일치 검증 결과** (작업 5 출력)
3. **도면1·2·4 baseline 결과** (라운드 5 → 6 비교)
4. **회귀 테스트 결과** (29 passed, 3 failed 유지)
5. **`round6_1단계_완성.md` 전문**

---

## 라운드 6 종료 조건

- ✅ 도면1: 22/22 유지 (절대)
- ✅ 도면2: 4/6 유지
- ✅ 도면4: 3/4 유지
- ✅ 자동 판단이 라운드 5 수동 yaml 설정과 도면1·2·4 모두 일치
- ✅ 새 도면 무손 적용 시뮬레이션 통과 (작업 7, 선택)
- ✅ counter.py 핵심 매칭 룰(BR2·블록·height 로직) 미변경
- ✅ 외부 도구 도입 없음

다섯(필수)·여섯(전체) 충족 시 **1단계 진짜 완성. 2단계(부호 → 규격 매칭) 진입 준비.**

---

## 라운드 7 예고

라운드 7 = 2단계(부호 → 규격 매칭) 진입.

- 도면4 `G-MEMBGUIDE` MTEXT(`SC1\PH 350x175x7/11`)를 규격 데이터로 파싱
- 일람표 영역 텍스트(라운드 5에서 제외했던 것)를 규격 매핑으로 활용
- LLM 도입 인프라 구축 (모호한 분류 케이스 해석용)
- 도면2 SC, 도면4 SB1 재방문 (갈래 A/B/C 최종 결정)
