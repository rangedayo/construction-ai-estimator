# 라운드 길이-1 보고서 — DIMENSION 기반 기둥 길이 자동 추출

## A. 라운드 목적

1단계(개수 카운팅)가 회귀 14/16 PASS 로 정착한 시점에서, 2단계 **기둥 길이 추출** 진입.
사전 분석에서 알고리즘이 확정된 상태였다:

> "세로 방향 DIMENSION 엔티티의 measurement 값 중 최댓값"

본 라운드는 다음 셋을 신설했다.

1. **측정 모듈** — DXF → DIMENSION 추출 → 방향 판별 → 세로 최대값 채택.
2. **회귀 인프라** — 1단계와 동일한 패턴의 정답지 로더 + pytest 파라미터화.
3. **시각화 도구** — DIMENSION 오버레이 + 채택값 강조 HTML.

1단계 카운팅 모듈(`counter.py`·`baseline.py`·`config/symbol_rules.yaml`)은 **수정 없음**.
신규 모듈은 `poc_v2/length/` 패키지와 `config/length_routing.yaml` 에만 존재한다.

## B. 알고리즘 명세

### 핵심
세로(V) DIMENSION 중 measurement 가 가장 큰 엔티티의 값을 채택.

### 방향 판별
DIMENSION.defpoint2 와 defpoint3 좌표 차이로 판별.

| 조건 | 분류 |
|---|---|
| `|dy| > |dx| × 5` | V (세로) |
| `|dx| > |dy| × 5` | H (가로) |
| 그 외             | D (대각) |

### 파라미터 (`config/length_routing.yaml` → `methods.dimension_max_vertical`)
- `direction_ratio_threshold: 5.0` — V/H 분리 비율
- `min_measurement: 100.0` — 100mm 미만 디테일 치수 무시

### 신뢰도
| 조건 | confidence |
|---|---|
| 단일 측정, 1·2위 측정값 비율 ≥ 1.2 | high |
| 1·2위 측정값 비율 < 1.2          | medium |
| 측정 실패 / 소스간 편차 > 2%      | low |

같은 부호에 여러 소스가 있을 때는 측정값 합의를 추가로 평가한다 (편차 ≤ 1mm: high / ≤ 2%: medium / 그 외: low). 부호 최종 신뢰도는 파일 단위 신뢰도와 합의 신뢰도 중 더 보수적인 값.

## C. 검증 결과 — 회귀 16/16 PASS

`pytest -v poc_v2/length/tests/test_length_regression.py`

| 도면 | 부호 | 예측(mm) | 정답(mm) | 차이 | 상태 |
|---|---|---|---|---|---|
| 도면1 | MC1 | 6000 | 6000 | 0 | PASS |
| 도면1 | MC2 | 6000 | 6000 | 0 | PASS |
| 도면1 | MC3 | 6000 | 6000 | 0 | PASS |
| 도면1 | SC1 | 6000 | 6000 | 0 | PASS |
| 도면2 | SC1 | 7700 | 7700 | 0 | PASS |
| 도면2 | SC2 | 7700 | 7700 | 0 | PASS |
| 도면3 | C1  | 19060 | 19060 | 0 | PASS |
| 도면3 | C2  | 19060 | 19060 | 0 | PASS |
| 도면3 | C3  | 19060 | 19060 | 0 | PASS |
| 도면3 | C4  | 19060 | 19060 | 0 | PASS |
| 도면4 | SC1 | 9000 | 9000 | 0 | PASS |
| 도면4 | SC2 | 9000 | 9000 | 0 | PASS |
| 도면5 | C1  | 10500 | 10500 | 0 | PASS |
| 도면5 | C2  | 10500 | 10500 | 0 | PASS |
| 도면5 | C3  | 10500 | 10500 | 0 | PASS |
| 도면5 | C4  | 10500 | 10500 | 0 | PASS |

**16/16 통과, 평균 오차 0mm.** 허용 오차(≤ 1000mm: ±50, > 1000mm: ±2%) 와 무관하게 정확.

### 신뢰도 분포
- high: 도면3 계단단면도 1 파일
- medium: 나머지 9 파일

`medium` 은 알고리즘 정확도 저하가 아니라 "1위·2위 측정값이 동일"한 경우(같은 층고가 좌·우측 기둥에서 동시에 표기) 로 부수적 진단 메모. 다음 라운드에서 `ratio == 1.0` 케이스를 high 로 분류하는 미세 조정 후보.

## D. 1단계 회귀 미영향 확인

`pytest -v poc_v2/tests/test_regression.py` → **14/16 PASS** (도면2 SC1·SC2 2개 실패).
이 두 케이스는 **본 라운드 이전부터 알려진 부채** (memory:baseline-test-infra: "도면2 4/6", git log: "회귀 14/16").
즉 본 라운드 신규 모듈 추가에 의한 1단계 영향 0.

## E. 알려진 한계 (다음 라운드 후보 포함)

- DIMENSION 이 없는 도면(있을 경우) → 측정 불가. fallback 미구현.
- TEXT 엔티티에 길이가 적힌 비표준 도면은 미지원.
- 도면 종류 자동 판별은 본 라운드 범위 외 (yaml 로 명시).
- 보(빔) 길이 측정은 본 라운드 범위 외.
- DIMENSION override 텍스트(사람이 강제 입력) 가 있을 경우, 본 라운드는 measurement 만 사용. 향후 override 우선 채택 옵션 후보.
- `confidence='medium'` 의 9 파일 중 다수는 ratio == 1.0 (동일값) 부수효과. 룰 미세 조정 후보.

## F. 신설 파일 목록

```
poc_v2/length/
├── __init__.py
├── ground_truth_length.py        # 길이 정답지 로더
├── routing.py                    # length_routing.yaml 로더
├── measure.py                    # DIMENSION 추출 + dimension_max_vertical
├── baseline_length.py            # 라우팅 기반 도면 측정 + CLI
├── visualize_length.py           # plotly HTML 시각화 + CLI
└── tests/
    ├── __init__.py
    └── test_length_regression.py # pytest 회귀 (16 케이스)

config/length_routing.yaml         # 도면별 측정 소스·부호 매핑

outputs/visualize/
├── 도면1-기둥-길이_2동_Y01열골구도_length.html
├── 도면1-기둥-길이_2동_Y03열골구도_length.html
├── 도면1-기둥-길이_2동_Y05열골구도_length.html
├── 도면2-기둥-길이_가나동_횡단면도_length.html
├── 도면3-기둥-길이_종단면도_length.html
├── 도면3-기둥-길이_계단단면도_length.html
├── 도면4-기둥-길이_종단면도_length.html
├── 도면4-기둥-길이_횡단면도_length.html
├── 도면5-기둥-길이_주단면도1_length.html
└── 도면5-기둥-길이_주단면도4_length.html

outputs/round_length1_보고서.md     # 본 문서
```

수정된 파일: 없음.

## G. 향후 라운드 후보

| 라운드 | 내용 |
|---|---|
| 길이-2 | 보(빔) 길이 측정 — 가로 DIMENSION 최댓값 적용 + 평면도 LINE 직접 측정 |
| 길이-3 | fallback 룰 — DIMENSION 없는 도면용 (TEXT 추출, LINE 빈도 등) |
| 길이-4 | 총 중량 산출 — 길이 × 단위중량(`강재단위중량` 시트) × 개수 |
| 길이-5 | `confidence='medium'` 룰 미세 조정 — ratio == 1.0 케이스를 high 로 |

## H. 실행 명령 모음

```bash
# 길이 베이스라인 (도면1~5)
python -m poc_v2.length.baseline_length
python -m poc_v2.length.baseline_length 도면3

# 회귀 테스트 (16 케이스)
pytest -v poc_v2/length/tests/test_length_regression.py

# 1단계 회귀 미영향 확인 (14/16, 알려진 부채 2개)
pytest -v poc_v2/tests/test_regression.py

# 시각화 HTML 생성
python -m poc_v2.length.visualize_length            # 전체 + 첫 HTML 자동 오픈
python -m poc_v2.length.visualize_length 도면3       # 도면3만
python -m poc_v2.length.visualize_length --no-open  # 오픈 비활성화
```
