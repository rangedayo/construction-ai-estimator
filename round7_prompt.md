# 라운드 6 (수정판) — 신호 2·3 자동화 (height는 수동 유지)

## 라운드 6 사전 검증 결과 반영

이전 라운드 6 프롬프트는 사전 검증에서 **신호 1(height) 자동화가 구조적으로 불가능**함이 드러나 폐기됨.

핵심 발견:
- 도면1 정답 22/22 맞추려면 min_height 가 176~198 사이여야 하지만 갭 구조상 가장 큰 갭은 198→282(46%)
- "가장 큰 갭" 알고리즘 → min_height=199 → 도면1 20/22 → 절대 제약 위반
- 도면별 height 비율 정반대: 도면2 0.75 vs 도면4 0.33 → 단일 비율 룰 불가
- **결론: 어느 height 무리가 진짜 부재인지는 정답지에만 있음. 외부 신호 없이 결정론 안 풀림.**

사용자 결정: **옵션 1 — min_height 만 수동, 신호 2·3 자동화.**

## 라운드 6 (수정판) 목표

- 신호 2 (일람표): 자동 결정
- 신호 3 (규격 패턴, BR2 보호 포함): 자동 결정
- 신호 1 (min_height): yaml 수동 (라운드 5 값 그대로)
- 자동/수동 일치 검증
- 도면1·2·4 회귀 유지

## 솔직한 한계 인정

- 사용자 의도("새 도면 무손 적용") *부분 달성*: height 한 줄은 새 도면마다 yaml 추가 필요
- 신호 2·3 자동화는 완료: 일람표·규격 정책은 자동 적용
- 신호 1 완전 자동화는 외부 신호 필요 → 라운드 7 LLM 또는 정답지 합산 기반 재검토

## 사전 검증 추가 정정

이전 프롬프트 오류:
- **"도면2 BR2 보호"는 오류.** 정답지 확인 결과 BR2 는 *도면1에만 등장*(도면2엔 BR2 열 없음). 보호 발동 도면은 *도면1*.
- 신호 3 자동 결과: 도면1=False(BR2 보호), 도면2=False(규격 텍스트 0), 도면4=True. 라운드 5 yaml 과 동일.

---

## 작업 원칙 (라운드 3~5 동일)

1. 한 번에 하나만 변경. 변경마다 회귀 테스트.
2. 외부 도구 추가 금지.
3. **도면1 22/22 절대 깨지면 안 됨.**
4. 도면2 4/6, 도면4 3/4 유지.
5. counter.py 핵심 매칭 룰(BR2·블록·height 로직) 미변경.
6. layer 이름 매칭 금지.

---

## 작업 1 — yaml 구조 변경

`text_height_filter` **그대로 유지**(라운드 5 값 박힘). `policy_p` 만 폐기:

```yaml
# 기존 (유지)
text_height_filter:
  도면1: { min_height: 177 }
  도면2: { min_height: 302 }
  도면4: { min_height: null }

# 폐기 (주석 처리)
# policy_p:
#   도면1: { exclude_table_regions: false, exclude_with_spec: false }
#   ...

# 신규
auto_policy_params:
  spec_pattern_threshold: 0.3

policy_override:
  도면1: null    # 자동 판단 사용
  도면2: null
  도면4: null
  # 비상 시: 도면X: { exclude_table_regions: true, exclude_with_spec: false }

# 기존 (유지)
table_region_detection:
  region_size_ratio: 0.033
  min_distinct_symbols: 4
  max_count_per_symbol: 2
```

⚠️ `text_height_filter` 절대 폐기 금지. 신호 1 수동 유지가 결정 사항.

---

## 작업 2 — 새 모듈 `poc_v2/tests/auto_policy.py`

```python
"""정책 자동 활성화 — 신호 2·3 한정.

신호 1(min_height)은 answer-key-free 자동화 불가로 yaml 수동 유지.
신호 2·3은 결정론적 측정으로 자동 가능.
LLM 호출 없음, ezdxf만.
"""

def auto_detect_policy(
    dxf_path: str,
    symbol_whitelist: list[str],
    min_text_height: float | None = None,
    spec_pattern_threshold: float = 0.3,
) -> dict:
    """신호 2·3 자동 판단.
    
    인자:
        dxf_path: DXF 경로
        symbol_whitelist: 화이트리스트 부호
        min_text_height: yaml에서 받은 height 필터 (신호 2 검출에 적용)
        spec_pattern_threshold: 신호 3 임계값
    
    반환:
        {
            "exclude_table_regions": bool,
            "exclude_with_spec": bool,
            "diagnostics": {...}
        }
    """
    # 신호 2: 일람표 검출
    # 중요: min_text_height 적용 *후* 텍스트로 검출.
    # 도면2 작은 글자 일람표가 사라져 0곳 검출됨.
    table_regions = _detect_table_regions(dxf_path, symbol_whitelist, min_text_height)
    exclude_table = len(table_regions) >= 1
    
    # 신호 3: 부호+규격 패턴 + 보호
    spec_count, br2_protection = _detect_spec_pattern(
        dxf_path, symbol_whitelist, min_text_height
    )
    exclude_with_spec = (spec_count >= len(symbol_whitelist) * spec_pattern_threshold)
    if br2_protection:
        exclude_with_spec = False
    
    return {
        "exclude_table_regions": exclude_table,
        "exclude_with_spec": exclude_with_spec,
        "diagnostics": {
            "table_regions_count": len(table_regions),
            "spec_pattern_count": spec_count,
            "br2_protection_triggered": br2_protection,
        }
    }


def _detect_table_regions(dxf_path, whitelist, min_height):
    """기존 detect_table_region 재사용. min_height 적용 후 검출."""
    # collect_free_text_coords 에 min_height 인자 필요할 수 있음 - 추가 구현
    # ...


def _detect_spec_pattern(dxf_path, whitelist, min_height):
    """부호+규격 패턴 빈도 + 보호 케이스.
    
    보호 로직:
        화이트리스트 부호 W 중
        - "W 단독" 텍스트가 0개
        - "W 규격패턴" 텍스트가 1개 이상
        → 보호 발동 (exclude_with_spec=False 강제).
    
    검증 기대값:
        도면1: BR2가 "BR2 L-80X80X7" 형태로만 등장 → 보호 발동 → False
        도면2: 부호+규격 텍스트 0개 → False
        도면4: SC1/SC2 부호+규격 다수, BR2 없음 → True
    """
    # ...
```

---

## 작업 3 — `ground_truth.py` 로더 추가

```python
# 기존 load_text_height_filter() 유지

def load_auto_policy_params() -> dict: ...
def load_policy_override(drawing: str) -> dict | None: ...
# load_policy_p() 는 deprecated (yaml 키 폐기됨).
```

---

## 작업 4 — baseline.py·test_regression.py 자동 판단 사용

```python
# 신호 1: yaml 그대로
height_filter = load_text_height_filter()
min_h = height_filter.get(drawing, {}).get("min_height")

# 신호 2·3: 자동 (오버라이드 우선)
override = load_policy_override(drawing)
if override:
    policy = override
else:
    symbols = sorted(drawing_symbol_totals()[drawing].keys())
    params = load_auto_policy_params()
    policy = auto_detect_policy(dxf_path, symbols, min_h, **params)

table_p = policy["exclude_table_regions"]
spec_p = policy["exclude_with_spec"]
```

`auto_detect_policy` 캐싱 필수 (`functools.lru_cache`).

---

## 작업 5 — 자동/수동 일치 검증

`tests/verify_auto_policy.py`:

```python
EXPECTED = {
    "도면1": {"exclude_table_regions": False, "exclude_with_spec": False},
    "도면2": {"exclude_table_regions": False, "exclude_with_spec": False},
    "도면4": {"exclude_table_regions": True, "exclude_with_spec": True},
}

for drawing in EXPECTED:
    min_h = load_text_height_filter()[drawing]["min_height"]
    symbols = sorted(drawing_symbol_totals()[drawing].keys())
    auto = auto_detect_policy(_dxf_path(drawing), symbols, min_h)
    
    if all(auto[k] == EXPECTED[drawing][k] for k in EXPECTED[drawing]):
        print(f"✅ {drawing}: 일치")
    else:
        print(f"⚠ {drawing}: 자동 {auto} vs 수동 {EXPECTED[drawing]} 불일치")
```

**라운드 6 종료 조건 1순위**: 도면1·2·4 모두 자동 = 수동.

**불일치 시:**
1. `spec_pattern_threshold` 조정
2. BR2 보호 로직 디버그
3. **그래도 안 맞으면 즉시 중단 보고. 임의 임계값 박지 말 것.**

---

## 작업 6 — 회귀 테스트

```bash
python tests/baseline.py 도면1 도면2 도면4
pytest -v tests/test_regression.py
```

기대: 도면1 22/22, 도면2 4/6, 도면4 3/4 유지. `29 passed, 3 failed`.

도면1 하나라도 깨지면 즉시 중단 보고.

---

## 작업 7 — 새 도면 추가 시뮬레이션

**사용자 의문 직접 검증.** 도면1.dxf → `도면1_clone.dxf` 복사, 정답지 시트도 `도면1_clone` 복사.

1. `policy_override["도면1_clone"]` 추가 안 함 (자동 판단 활성)
2. `text_height_filter["도면1_clone"]: { min_height: 177 }` 만 추가 (한 줄)
3. baseline 실행 → 22/22 PASS 기대

**리포트에 결과 포함**: "새 도면 추가 시 height 한 줄만 추가하면 동작"이 사실인지 명시적 확인.

---

## 작업 8 — 1단계 종료 리포트

`round6_1단계_부분완성.md`:

### A. 1단계 진척 (라운드 1~6)
- 도면1: 27% → 32% → 100%
- 도면2: 4/6 달성 (라운드 4) 유지
- 도면4: 0/4 → 3/4 (라운드 5) 유지
- 라운드 6: 신호 2·3 자동화 (신호 1 수동)

### B. 자동 활성화 — 신호 2·3
- 알고리즘 정리
- 자동/수동 일치 검증 결과
- BR2 보호 발동 도면 정정 (도면1)

### C. 미달성 — 신호 1 수동 유지

**솔직한 한계 표현 (멘토 보고 핵심):**

> "라운드 6 사전 검증에서 height 임계값의 answer-key-free 자동화가 구조적으로 불가능함을 확인. 도면별 'height 무리 갈림'이 갭 구조만으론 결정 안 되고(도면1 갭 분포가 정답과 정반대), 도면별 비율도 정반대(도면2 0.75 vs 도면4 0.33)라 단일 룰 불가. 1단계 범위에서는 yaml 한 줄(min_height)이 도면당 수동 추가됨. 신호 1 완전 자동화는 라운드 7 LLM 도입 또는 정답지 합산 기반(옵션 2) 방식으로 재검토."

**사용자 의문 답:**
- 새 도면 추가 시 height 한 줄 yaml 추가 필요 = 사실
- 신호 2·3 (일람표·규격 정책)은 자동 = 약 80% 자동화
- height 완전 자동화는 외부 신호(정답지·LLM·비전) 필요

### D. 1단계 미해결 (2단계 위임)
- 도면2 SC 분리 TEXT (갈래 C)
- 도면4 SB1 좌표 중복 (검수 위임)
- **신호 1 자동화** (수동 → LLM/정답지 기반)

### E. 2단계 진입 준비
- 도면4 G-MEMBGUIDE MTEXT = 2단계 핵심 규격 데이터
- LLM 도입 자리: 신호 1 자동화 + 모호한 분류 케이스 해석
- 옵션 2(정답지 합산) 재고려 가능

### F. 1단계 핵심 학습
- "AI는 결정만, 도구는 측정만" 원칙 검증
- **결정론 룰 기반의 한계 발견** — 외부 신호 없이 안 풀리는 결정이 존재함을 사전 검증으로 확인. LLM 도입의 정당성 근거.
- catastrophic regression 방지 회귀 테스트 효과
- **솔직한 한계 인정의 가치** — 사전 검증으로 구조적 불가능을 *코드 변경 전*에 발견. 임의 임계값 박지 않음.

---

## 최종 보고 형식

1. 변경 파일 목록
2. 자동/수동 일치 검증 (작업 5)
3. 도면1·2·4 baseline (라운드 5 → 6)
4. 회귀 테스트 (29/3 유지)
5. 새 도면 시뮬레이션 (작업 7)
6. `round6_1단계_부분완성.md` 전문

---

## 라운드 6 종료 조건

- ✅ 도면1 22/22 유지
- ✅ 도면2 4/6, 도면4 3/4 유지
- ✅ 신호 2·3 자동 = 수동 (도면1·2·4 모두)
- ✅ 새 도면 시뮬레이션 통과
- ✅ counter.py 핵심 매칭 룰 미변경
- ✅ 외부 도구 도입 없음
- ✅ 리포트에 신호 1 한계 솔직 명시

여덟 충족 시 **1단계 부분 완성. 2단계 진입.**

---

## 라운드 7 예고

라운드 7 = 2단계(부호 → 규격 매칭).

- 도면4 G-MEMBGUIDE MTEXT 를 규격 데이터로 파싱
- LLM 도입 인프라
- **신호 1 자동화 재검토**: LLM 호출 또는 옵션 2 (정답지 합산)
- 도면2 SC, 도면4 SB1 재방문
