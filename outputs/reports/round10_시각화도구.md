# 라운드 10 — 시각화 도구 (기둥 부재 한정)

## A. 목적

라운드 11 (톨로런스 정확화 + 일람표 검출 정밀화) 의사결정의 근거 데이터 확보.
지금까지는 카운트(숫자)만 보고 있어서, 어떤 텍스트가 본체로 인정됐는지·
어떤 텍스트가 일람표/규격/필터로 제외됐는지를 시각적으로 확인할 수 없었다.
이번 라운드는 그 가시화 도구만 신설한다. **기둥 부재만** 분석 대상.

본 라운드는 **시각화 도구 신설만**. counter.py·baseline.py·yaml·auto_policy.py·
detect_table_region.py 미변경. 회귀 영향 0.

## B. 분석 대상 범위

- **화이트리스트**: `drawing_symbol_totals(category="기둥")` — 회귀 테스트와 동일 범위
- **보 부재**: 본 라운드 분석 대상 외 → `not_whitelist` 분류로 빠지고 시각화에 표시 안 됨
- **확장 계획**: 라운드 11 이후 보 부재 회귀 추가 시 별도 시각화 (`도면N_detection_보.html`) 추가 예정

## C. 신설 파일

- `poc_v2/tests/classify_text.py` — 분류 진단 함수 `classify_drawing_texts(drawing)` (기둥 한정)
- `poc_v2/tests/visualize_detection.py` — Plotly HTML 시각화 + CLI 진입점 + 자동 브라우저 오픈
- `outputs/round10_시각화도구.md` — 본 보고서

`classify_text.py` 는 룰을 새로 정의하지 않는다. `baseline.compute_drawing` 의
policy·regions·min_h 를 받아 `counter.match_symbol` 을 두 번(strict·combo) 호출해
동일 룰을 텍스트 단위로 재현한다. 화이트리스트만 기둥 부호로 제한.

## D. 출력 5개 HTML 위치

- `outputs/visualize/도면1_detection_기둥.html`
- `outputs/visualize/도면2_detection_기둥.html`
- `outputs/visualize/도면3_detection_기둥.html`
- `outputs/visualize/도면4_detection_기둥.html`
- `outputs/visualize/도면5_detection_기둥.html`

각 파일은 CDN plotly.js 를 쓰는 standalone HTML — 브라우저로 바로 열린다.

각 HTML 에는 다음이 포함된다:
- DXF 기하 (LINE/LWPOLYLINE/POLYLINE/ARC/CIRCLE) — 회색
- 작은 텍스트 라벨 — 옅은 회색
- 분류별 마커 오버레이 (legend = 분류명, hover = text·symbol·source·height·좌표)
- 일람표 영역 bbox — 빨간 점선 사각형 + `Region N: C1(1), ...` (기둥 부호만 노출)
- 좌상단 카운트 비교 박스 — 기둥 부호별 예측·정답·차이·상태 (PASS / PASS (±1) / FAIL)

## E. 도면별 시각화 결과 요약

| 도면 | counted | slash_combo | filtered_table | filtered_spec | filtered_height | 시각적 검증 포인트 |
|---|---:|---:|---:|---:|---:|---|
| 도면1 | 96 | 0 | 0 | 0 | 20 | **일람표가 도면에 물리적으로 있는지 눈으로 확인.** 코드는 0곳 검출 — height 필터(min_height=177)로 작은 글자 일람표 후보가 입력 단계에서 잘렸을 가능성. height 컷 20개 위치를 보면 일람표 텍스트인지 확인 가능. |
| 도면2 | 0 | 0 | 0 | 0 | 2 | **SC1·SC2 본체 마커가 한 개도 없음.** 정답 SC1=10·SC2=4 인데 매칭 0 — 라운드 5 갈래 C(분리 TEXT) 문제. 도면의 SC1·SC2 표기가 화이트리스트 패턴과 어긋난 형태(예: 분리 텍스트, 다른 prefix)임을 시각으로 확인. 별도 진단 필요. |
| 도면3 | 0 | 32 | 4 | 1 | 0 | **C1~C4 본체가 전부 슬래시 결합형** (예: "C1/P1") — counted=0, slash_combo=32. 라운드 8 결정이 맞음을 시각으로 확인. 일람표 region 1곳에서 C1~C4 각 1개 제외. |
| 도면4 | 18 | 0 | 4 | 18 | 0 | **일람표 영역(region 1곳) + 규격 안내 18개 분리 확인.** SC1/SC2/SG1/SB1 본체 18곳, 일람표 영역 안 4개 텍스트가 카운트에서 제외됨. |
| 도면5 | 2 | 20 | 4 | 0 | 0 | **C1·C2 +1 오차의 원인 위치 — 라운드 11 핵심.** 본체 단독 마커 2개 + 슬래시 결합 20개. 일람표 region 2곳 중 기둥 region(C1~C4) 1곳에서 4개 제외. C1=3(정답 2) / C2=5(정답 4) 의 "초과 1개"가 단독 마커인지 슬래시 결합인지 시각으로 식별 가능. |

분류 카운트는 텍스트 엔티티 단위라 카운트 결과(부재 수) 와 정확히 1:1 일치하지 않는다
(INSERT 1개에서 ATTRIB 가 여러 부호를 가질 수 있음, dedup 차이 등). 본 표의 숫자는
**시각적 진단용 분류 분포**일 뿐이고, 회귀 카운트는 `baseline.compute_drawing` 이
독립적으로 계산한 값(HTML 좌상단 요약 박스에 표시)이 정답이다.

## F. 회귀 결과

```
pytest -v poc_v2/tests/test_regression.py
============= 2 failed, 14 passed, 7 warnings in 66.82s =============
FAILED  도면2-SC1
FAILED  도면2-SC2
```

라운드 9 와 동일 (14 passed / 2 failed). 시각화 도구는 카운트 경로를 건드리지 않음 — 의도대로 회귀 영향 0.

## G. 다음 라운드 (11) 의사결정 자료

시각화로 다음을 눈으로 확인할 수 있게 됐다:

1. **도면1 일람표 존재 여부 vs height 필터 입력 단계 컷** — 사용자 질문.
   - 일람표가 물리적으로 있는데 height 필터(min=177)로 입력 단계에서 잘려 region=0 이 됐을 가능성. HTML 에서 회색 텍스트로 깔린 작은 글자 일람표 위치를 확인.
   - height 컷 20개 마커 위치 (회색 X) 로 어떤 글자가 입력에서 잘렸는지 추적 가능.
2. **도면5 C1·C2 +1 오차의 원인** — 라운드 11 핵심.
   - C1 본체 카운트 3 vs 정답 2, C2 5 vs 정답 4 — 시각화로 단독 마커 2개 + 슬래시 결합 20개 위치 식별.
   - region 2곳 (기둥+보) 검출됐고 4개 텍스트 제외됨. 어느 마커가 region 안/밖인지 hover 로 확인.
   - 톨로런스 폐기 여부 결정: 시각으로 "초과 1개"가 진짜 부재인지 일람표/주석/슬래시 결합인지 판별 후 결론.
3. **도면3 슬래시 결합 본체의 시각적 분포** — 라운드 8 결정 검증.
   - C1~C4 단독 텍스트 0개, 슬래시 결합 32개 — counter 의 슬래시 결합 처리가 의미 있음을 시각으로 확인.
4. **도면2 SC1·SC2 분리 TEXT 진단** — 라운드 5 갈래 C.
   - 본체 마커가 0개 — 화이트리스트 매칭이 안 됨. HTML 에서 회색 텍스트(`not_whitelist` 라 표시는 안 되지만 작은 라벨로 깔림)에서 SC1·SC2 가 어떤 형태로 그려져 있는지 추적. 별도 진단 도구가 필요할 수 있음.

라운드 11 사전 진단 작업 시 위 HTML 을 우선 도구로 활용. 톨로런스 폐기 여부는
도면5 의 시각적 확인 결과 (어떤 마커가 카운트 오차의 원인인지) 를 보고 결정한다.

## H. CLI 사용법

```
python poc_v2/tests/visualize_detection.py              # 5개 도면 전부 + 첫 도면 자동 오픈
python poc_v2/tests/visualize_detection.py 도면3        # 한 도면만 + 자동 오픈
python poc_v2/tests/visualize_detection.py --no-open    # 자동 오픈 비활성
```

`webbrowser.open(file:///...)` 표준 라이브러리 사용 — 외부 의존 0.

콘솔 로그 (라운드 10-2 실행 결과):

```
outputs/visualize/도면1_detection_기둥.html 생성  (counted=96, slash_combo_body=0, filtered_height=20, filtered_spec=0, filtered_table=0)
outputs/visualize/도면2_detection_기둥.html 생성  (counted=0, slash_combo_body=0, filtered_height=2, filtered_spec=0, filtered_table=0)
outputs/visualize/도면3_detection_기둥.html 생성  (counted=0, slash_combo_body=32, filtered_height=0, filtered_spec=1, filtered_table=4)
outputs/visualize/도면4_detection_기둥.html 생성  (counted=18, slash_combo_body=0, filtered_height=0, filtered_spec=18, filtered_table=4)
outputs/visualize/도면5_detection_기둥.html 생성  (counted=2, slash_combo_body=20, filtered_height=0, filtered_spec=0, filtered_table=4)
```

## I. 정리 메모

라운드 10 (v1, 기둥+보 병합 화이트리스트) 의 산출물 `도면N_detection.html` 5개가
`outputs/visualize/` 에 함께 남아 있다. 라운드 10-2 가 v1 을 대체하므로, 정리하고
싶다면 다음 명령으로 삭제 가능 (안전상 자동 삭제는 하지 않았음):

```
rm outputs/visualize/도면[1-5]_detection.html
```
