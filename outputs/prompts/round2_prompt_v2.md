# 라운드 2 — 합계 기준 카운팅 + 진단 라운드

## 이전 라운드 결과 요약

`baseline-test-infra` 메모리 참고. 도면 1에 대해 확인된 사항:
- 총 합계 예측 371 vs 정답 331, 차이 +40
- 22개 부호 중 통과 6개 (27%)
- BR2만 과소(-4), 나머지 모두 과다 카운트
- 자동감지 모드는 통심선·기초·상세참조까지 오탐 → 화이트리스트 방식이 정답
- 도면 1에 "일람표"/"LIST"/"MEMBER" 키워드 텍스트가 0개. 키워드 기반 일람표 식별 불가
- MC1 텍스트 높이 분포: 큰 글씨(282) 30회 + 중간(198) 24회 + 작은(159·176) 7회. 정답 54 = 큰+중간. **작은 글자 7개가 +7 오차의 정체**

## 이번 라운드 방침 변경

멘토 조언과 정답지 구조 재검토 결과, **페이지 분할은 영구 폐기**하고 도면 전체 합계 기준으로 진행. 1단계 목표를 다시 정의:

> **"어떤 도면이든 그 도면에서 보이는 철골 부호 종류, 개수, 길이를 정확히 파악"**

근거:
1. 정답지 합계 행이 이미 더블카운팅 포함이므로 합계만 맞추면 됨
2. 페이지 자동 분할은 부호 위치 침범으로 오히려 정확도 하락 (페이지 단위 9.6%, 합계 단위 더 좋음)
3. 멘토 조언: "도면 단위가 아니라 부재 단위"

이번 라운드 목표: **합계 기준 5% 이내 오차 달성을 위한 진단 + BR2 매칭 적용**.

## 사전 정리 작업 (먼저 실행)

페이지 분할 코드를 정리. 다음을 **삭제**:
- `config/drawings.yaml` (페이지 bbox 정의)
- `config/dedup_policy.yaml` (페이지 더블카운팅 정책)
- `poc_v2/tests/test_regression.py`의 `test_page_count` 함수
- `tests/ground_truth.py`에서 페이지 단위로 분해하는 로직 — 부호별 합계만 로드하도록 단순화

**유지**:
- `config/symbol_rules.yaml` (철골 화이트리스트, 더 명확하게 정리)
- `app.py`, `counter.py` (수정은 작업 2에서만)

## 철골 부호 화이트리스트 (확정)

`config/symbol_rules.yaml`에 다음을 명시:

```yaml
# 1단계 카운팅 대상 — 철골 부재만
steel_whitelist:
  columns:    [MC1, MC2, MC3, SC1, SC2]
  girders:    [SG1, SG2, SG3, WG1, CRG1, VG1, MT1]
  beams:      [SB1, SB2, SB3, VT1]
  roof_beams: [RSG1, RSG2, RSG3, RSB1, RSB2, RSB3]
  braces:     [BR1, BR2]

# 카운트 제외 prefix (자동 거름)
excluded_prefixes:
  foundation: [F, FS, MF]      # 콘크리트 기초
  rebar:      [HD, D, SR, SBR] # 철근
  detail:     [DS, DT]         # 상세 참조
  thickness:  [THK]            # 두께 표기
  grid:       [X, Y]           # 통심선 (X01, Y01 등)

# 카운트 제외 패턴 (자동 거름)
excluded_patterns:
  - "^H-\\d"  # H-200x100 같은 규격 표기
  - "^\\d+$"  # 순수 숫자
```

도면 1의 정답지 합계 행에서 등장하는 부호 22개:
MC1, MC2, MC3, SC1, SG1, SG2, SG3, SB1, SB2, SB3, RSG1, RSG2, RSG3, RSB1, RSB2, RSB3, WG1, CRG1, MT1, VG1, VT1, BR2.

## 작업 1 — 회귀 테스트 합계 모드

`poc_v2/tests/test_regression.py`를 합계 단위 테스트로 재구성:

```python
@pytest.mark.parametrize("drawing_id,symbol", [...])  # (도면id, 부호) 조합
def test_symbol_total(drawing_id, symbol):
    """도면 전체에서 부호별 총합이 정답지 합계와 일치"""
    predicted = count_total(drawing_id, symbol)
    expected = ground_truth_total(drawing_id, symbol)
    # 통과 기준: 오차 ≤ 5%. 단 개수 ≤ 5인 경우는 ±1 허용
    assert is_within_tolerance(predicted, expected)
```

도면 1·2·4 정답지 합계 행에서 (도면, 부호) 페어를 자동 생성.

## 작업 2 — BR2 부분 일치 매칭 (검증된 효과, 적용)

`counter.py`에 부분 일치 매칭 함수 추가:

```python
def match_symbol(text: str, whitelist: set[str]) -> str | None:
    text = text.strip()
    if text in whitelist:
        return text
    # "BR2 L-80X80X7" → "BR2", "MC1 추가" → "MC1"
    # 단 "MC10"이 "MC1"으로 잘못 매칭되는 것 방지
    for w in sorted(whitelist, key=len, reverse=True):
        if text.startswith(w):
            after = text[len(w):]
            if not after:
                return w
            if after[0] in (" ", "-"):
                return w
            # "MC1" 뒤에 숫자 오면 "MC10" 같은 다른 부호임
            if after[0].isdigit():
                continue
    return None
```

기존 `count_members`의 매칭 로직을 이 함수 호출로 교체. 시그니처 유지하여 `app.py` 무수정.

**검증된 효과**: 도면 1에서 BR2 0개 → 4개 정확 일치.

## 작업 3 — 합계 베이스라인 측정

작업 2 적용 후 측정. `tests/baseline.py`를 합계 모드로 단순화:

```bash
python tests/baseline.py 도면1
```

출력 형식:
```
부호    예측    정답    차이    오차%   상태
MC1     61      54      +7      13%     FAIL
MC2     35      28      +7      25%     FAIL
...
BR2     4       4       0       0%      PASS
...
요약: 22개 부호 중 N개 통과, 평균오차 X%, 총합 Y vs Z
```

## 작업 4 — 텍스트 높이 분포 진단

`tests/analyze_heights.py` 작성:

각 부호에 대해 도면 1 전체에서:
1. 모든 등장 위치와 텍스트 height 수집
2. height 히스토그램 (모드 자동 탐지)
3. 정답 개수와 비교해서 "어느 height 범위까지 카운트하면 정답에 맞을지" 추천

출력 예시:
```
MC1 (정답 54):
  height 282: 30회
  height 198: 24회   ← 누적 54, 정답 일치
  height 176: 4회    ← 누적 58, 정답 초과
  height 159: 3회    ← 누적 61
  추천 임계값: height >= 198 (현재 정답과 매칭)

VG1 (정답 36):
  ...
```

**중요**: 이번 라운드에서 임계값 적용은 안 함. 진단만. 도면 2/4도 같이 분석한 후 일반화 가능한 정책을 라운드 3에서 결정.

## 작업 5 — 부호 분포 영역 시각화 (Plotly HTML)

`tests/visualize_distribution.py` 작성:

도면 1의 모든 철골 부호 텍스트 위치를 Plotly로 시각화:
- 부호별 다른 색상 마커
- 마커 크기 = 텍스트 height (큰 글자는 크게, 작은 글자는 작게)
- hover에 부호명·높이·원본 텍스트 표시
- 같은 부호의 마커들을 토글 가능한 레전드로

목적: 사용자가 직접 보면서
- 작은 글자 부호가 어디에 군집해있는지 (단면도/일람표 후보)
- 큰 글자 부호와 어떻게 분리되는지
- 일람표로 의심되는 격자 패턴이 보이는지

출력: `outputs/도면1_distribution.html` (브라우저에서 열기)

추가로 텍스트 height만 가지고 산점도도 그려:
- X축: 부호 이름
- Y축: height
- 점 크기: 개수
- 임계값 후보를 가로선으로 표시

출력: `outputs/도면1_heights.html`

## 작업 6 — 부호 밀집 영역 진단

`tests/analyze_density.py` 작성:

도면 1에서 같은 부호가 일정 거리 안에 여러 번 등장하는 영역 검출:
- 각 부호별로 위치 좌표 추출
- 인접한 위치들을 단순 거리 기준으로 그룹화 (반경 임의 설정, 결과 보고 조정)
- 한 그룹에 N개 이상 모이면 "밀집 영역"으로 표시
- 또는 *서로 다른 부호*가 좁은 영역에 모인 경우 (일람표 후보)

알고리즘은 단순 거리 기반으로 시작. 복잡한 군집화 도구(DBSCAN 등)는 사용하지 말 것. 결과 보고 필요시 라운드 3에서 정교화.

출력:
- 콘솔: 발견된 밀집 영역 bbox 리스트
- Plotly HTML: 작업 5 시각화 위에 밀집 영역 사각형 오버레이

## 작업 우선순위와 순서

1. **사전 정리** (페이지 분할 코드 삭제)
2. **작업 2** (BR2 부분 일치 매칭) — 코드 작은 변경
3. **작업 1** (회귀 테스트 합계 모드)
4. **작업 3** (합계 베이스라인 측정) — 작업 2의 효과 확인
5. **작업 5** (Plotly 분포 시각화) — 사용자가 데이터 직접 확인
6. **작업 4** (높이 분포 진단)
7. **작업 6** (밀집 영역 진단)

## 종료 조건과 다음 라운드 예고

이번 라운드 종료 = 작업 1~6 완료 + 진단 리포트.

진단 리포트 필수 내용:
- 작업 2 적용 후 합계 정확도 변화
- 작업 4 결과: 각 부호별 추천 height 임계값 (적용은 안 함)
- 작업 5 시각화 결과: 작은 글자 군집 위치, 큰 글자 분포
- 작업 6 결과: 발견된 밀집 영역 좌표 (일람표/단면도 후보)
- 라운드 3에서 적용할 정책 후보 (높이 필터링? 영역 제외? 둘 다?)

라운드 3에서는:
- 진단 결과 바탕으로 높이 필터링 or 영역 제외 정책 결정·적용
- 도면 2/4 추가하면서 회귀 테스트 확장
- 합계 기준 5% 이내 달성

## 작업 시 주의사항

- 페이지 분할 관련 코드·설정은 **완전 삭제**. 회복할 일 없음
- `app.py`는 무수정. `counter.py`는 작업 2의 매칭 함수 추가만
- 외부 라이브러리 추가 금지: DBSCAN, PaddleOCR, Shapely, 비전 모델 등. ezdxf + 표준 라이브러리 + matplotlib/plotly만 사용
- 진단 스크립트(작업 4, 5, 6)는 도면 1만 대상. 도면 2/4는 라운드 3에서 같이 분석
- Plotly 출력은 `outputs/` 디렉토리에 HTML로 저장
- 코드 변경 전에 항상 회귀 테스트 먼저 실행. 변경 후에도 실행해서 비교
