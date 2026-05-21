라운드 10 — 시각화 도구 (옵션 C, 기둥 부재만). 톨로런스 폐기 여부는 시각화 결과 보고 라운드 11에서 결정.
배경 및 목적
라운드 9까지 도면1~5 기둥 부재 회귀 14/16 PASS (도면5 C1·C2는 톨로런스 ±1로 통과). 카운트 결과는 숫자로만 보고 있어서 어떤 텍스트가 본체로 인정됐는지, 어떤 게 일람표/규격/필터로 제외됐는지 시각적으로 확인하기 어렵다. 라운드 11 (톨로런스 정확화 + 일람표 검출 정밀화) 의사결정의 근거 데이터 확보가 이번 라운드의 목적.
중요 — 기둥 부재만 시각화: 보 부재는 라운드 1~9에서 룰 검증을 안 한 상태(라운드 11 이후 보 부재 회귀 확장 예정). 이번 시각화는 기둥 부재로 범위 한정 — 회귀 테스트(category="기둥")와 동일 화이트리스트 사용.
본 라운드는 시각화 도구 신설만. counter.py·baseline.py·yaml·auto_policy.py 미변경. 회귀 영향 0.
참고 자료: poc_v3/app.py 의 parse_dxf_for_plotly + build_dxf_figure. 이걸 베이스로 분류 정보까지 표시하도록 확장.
작업 1 — 분류 진단 함수 신설
baseline.compute_drawing 은 카운트만 돌려준다. 시각화를 위해 각 텍스트의 좌표 + 분류 결과 가 필요. 신규 함수 추가:
poc_v2/tests/classify_text.py (신규)
목적: 도면의 modelspace 텍스트와 INSERT 블록 텍스트를 모두 훑고, baseline.compute_drawing 과 동일한 룰로 각 텍스트에 분류 라벨을 붙인다.
함수 시그니처:
pythondef classify_drawing_texts(drawing: str) -> list[dict]:
    """
    각 텍스트의 좌표 + 분류 결과를 반환. 기둥 부재 화이트리스트 기준.

    화이트리스트는 drawing_symbol_totals(category="기둥") 으로 가져온다.
    test_regression.py 와 동일한 범위 — 보 부재는 분석 대상 외.

    Returns
    -------
    [
        {
            "x": float, "y": float,
            "text": str,             # 원본 텍스트
            "symbol": str | None,    # 매칭된 부호 (None=화이트리스트 외)
            "height": float,         # 텍스트 height
            "source": str,           # "TEXT", "MTEXT", "INSERT_ATTRIB", "INSERT_BLOCK_TEXT"
            "category": str,         # 아래 6개 중 하나
            "in_region": int | None, # 일람표 영역 인덱스 (None=영역 외)
        },
        ...
    ]
    """
category 6분류:
라벨의미시각화 색counted본체로 카운트됨 (final 에 반영)녹색filtered_heightmin_height 필터로 제외회색filtered_spec규격 안내 (exclude_with_spec=True 로 제외)노란색filtered_table일람표 영역 안에 있어서 제외빨간색not_whitelist기둥 화이트리스트 매칭 실패 (보 부호 또는 부호 아님)표시 안 함slash_combo_body슬래시 결합 본체 (도면3·5의 C1/P1 등 — counted 의 하위 분류)진한 녹색
구현 방식:

화이트리스트: drawing_symbol_totals(category="기둥")[drawing].keys() 로 가져옴 — 기둥 부호만 (회귀 테스트와 동일)
ezdxf로 도면 한 번 읽고, modelspace TEXT/MTEXT/INSERT 순회
각 텍스트에 대해 counter.match_symbol을 두 번 호출:

treat_slash_as_combo=False, exclude_with_spec=False → 단순 매칭 결과 A
treat_slash_as_combo=True, exclude_with_spec=True → spec 제외 매칭 결과 B


height 검사: min_text_height 로 cutoff 여부 판단
영역 검사: 좌표가 regions[i].bbox 안에 있으면 in_region = i
분류 로직:

A 매칭 실패 → not_whitelist (보 부호도 여기로 빠짐)
height 컷에 걸림 → filtered_height
B 매칭 실패 (A 성공) → filtered_spec
슬래시 결합형 텍스트 + B 매칭 성공 → slash_combo_body
일람표 영역 안 → filtered_table
그 외 → counted



baseline.compute_drawing 의 policy·regions·min_h 를 받아 동일 룰 재현. counter.py 미수정.
작업 2 — 시각화 도구 신설
poc_v2/tests/visualize_detection.py (신규)
poc_v3/app.py 의 parse_dxf_for_plotly + build_dxf_figure 를 베이스로 확장. Streamlit 없이 순수 Plotly HTML 출력. 도면 5장 모두 처리.
기능:
2-1. DXF 도면 기하 렌더링 (poc_v3 재사용)

LINE / LWPOLYLINE / POLYLINE / ARC → 회색 선
작은 텍스트 라벨도 회색으로 깔끔하게 표시
캐시 등 streamlit 의존성 제거, 순수 ezdxf + plotly

2-2. 분류별 마커 오버레이 (기둥 부재만)
classify_drawing_texts 결과를 받아 분류별로 다른 형태 마커:
categorymarkercolorsize의미countedcircle-opengreen14본체 카운트slash_combo_bodycircledarkgreen14슬래시 결합 본체filtered_heightxgray10height 필터로 제외filtered_specxgold10규격 안내 제외filtered_tablexred12일람표 영역 제외not_whitelist(표시 안 함)--보 부호 또는 부호 아님
레전드는 부호별이 아니라 분류별. hover 시 텍스트·좌표·분류·매칭 부호 표시.
2-3. 일람표 영역 bbox 사각형
compute_drawing 의 regions 결과 → 빨간 점선 사각형으로 표시. 사각형 안에 영역 인덱스와 기둥 부호 카운트 표시 (예: "Region 0: C1(1), C2(1), C3(1), C4(1)").
2-4. 정답 비교 박스 (기둥 부재만)
플롯 한 모서리에 작은 텍스트 박스로 도면별 기둥 카운트 결과 표시:
도면5 — policy: exclude_table=True (auto), exclude_with_spec=True (auto)
부호      예측    정답    차이    상태
C1         3       2      +1     PASS (±1)
C2         5       4      +1     PASS (±1)
C3         8       8       0     PASS
C4         6       6       0     PASS
baseline.compute_drawing 결과의 final·expected 중 기둥 부호만 표시.
2-5. 출력
outputs/visualize/도면1_detection_기둥.html
outputs/visualize/도면2_detection_기둥.html
outputs/visualize/도면3_detection_기둥.html
outputs/visualize/도면4_detection_기둥.html
outputs/visualize/도면5_detection_기둥.html
각 파일은 standalone (CDN plotly.js 사용해서 브라우저에서 바로 열림). 외부 의존성 없음.
파일명에 _기둥 접미사를 붙이는 이유: 라운드 11~ 보 부재 추가될 때 _보 접미사로 별도 파일 생성 가능하도록 명명 규칙 확립.
작업 3 — CLI 진입점 + 자동 브라우저 열기
python poc_v2/tests/visualize_detection.py 실행 시:

인자 없으면 5개 도면 전부 처리, 첫 번째 도면 HTML을 기본 브라우저로 자동 오픈
인자 1개 (예: python visualize_detection.py 도면3) 면 해당 도면만 처리 + 자동 오픈
--no-open 플래그로 자동 오픈 비활성화 가능
각 도면 처리 후 콘솔에 "outputs/visualize/도면N_detection_기둥.html 생성" 로그
구현: webbrowser.open(f"file://{abs_path}") 표준 라이브러리 사용 (외부 의존 0)

작업 4 — 회귀 미영향 확인
pytest -v poc_v2/tests/test_regression.py
기대: 14 passed / 2 failed (라운드 9와 동일). 본 라운드는 시각화 도구 신설만이므로 카운트 결과 변화 0.
작업 5 — 라운드 10 보고서
outputs/round10_시각화도구.md 신설. 가벼운 보고서 (시각화는 도구 도입이지 룰 변경이 아니므로 라운드 6·8·9 처럼 무거운 형식 불필요).
포함 항목:

A. 라운드 10 목적 — 라운드 11 의사결정 근거 확보. 기둥 부재만 시각화.
B. 분석 대상 범위 명시

화이트리스트: 기둥 부호만 (drawing_symbol_totals(category="기둥"))
보 부재는 본 라운드 분석 대상 외 → not_whitelist 분류로 처리 (시각화 표시 안 함)
라운드 11 이후 보 부재 회귀 확장 시 별도 시각화 (_보.html) 추가 예정


C. 신설 파일 목록 — classify_text.py, visualize_detection.py
D. 출력 5개 HTML 위치 — outputs/visualize/도면N_detection_기둥.html
E. 도면별 시각화 결과 요약 — 사용자가 눈으로 확인할 포인트 (아래 표 형식):

도면본체 마커일람표 영역규격 제외height 컷시각적 검증 포인트도면1????일람표가 도면에 있는지 눈으로 확인 (이미지로 확인됨, 코드는 0곳 검출 — height 필터로 잘림)도면2????SC1·SC2 누락 — 분리 TEXT는 시각화에 안 잡힘 (별도 진단 필요)도면3????C1/P1 슬래시 결합 본체 위치 (라운드 8 결과 확인)도면4????일람표 영역과 본체 분리 확인도면5????C1·C2 +1 오차의 원인 위치 — 라운드 11 핵심

F. 회귀 결과 — 14/2 유지 확인
G. 다음 라운드 (11) 의사결정 자료

시각화로 도면별로 다음을 눈으로 확인 가능해진다는 점 명시:

도면1 일람표가 물리적으로 존재하는데 height 필터로 입력 단계에서 잘리는 동작 확인
도면5 C1·C2 의 +1 오차가 어디서 오는지 (일람표 검출 한계 vs 분류 알고리즘 버그)
도면3 슬래시 결합 본체의 시각적 분포

라운드 11 사전 진단 작업 시 이 시각화를 우선 도구로 활용.
출력 항목

poc_v2/tests/classify_text.py — 신규
poc_v2/tests/visualize_detection.py — 신규
outputs/round10_시각화도구.md — 신규
outputs/visualize/도면N_detection_기둥.html × 5 — 신규
회귀 결과 (14/2 유지)
콘솔 로그: 5개 도면 처리 결과 + 자동 브라우저 오픈

작업 원칙 (라운드 4~9 합의)

counter.py·baseline.py·yaml·auto_policy.py·detect_table_region.py 전부 미변경
외부 라이브러리 추가 금지: ezdxf + plotly + 표준 라이브러리만 (plotly는 poc_v3에서 이미 도입됨, webbrowser는 표준 라이브러리)
Streamlit 의존 없음 — 순수 HTML 출력
분석 범위: 기둥 부재만 — 보 부재는 본 라운드 대상 외
시각화 결과의 색·마커 일관성 유지 (라운드 11 진단 시 통일된 표 사용)

작업 시작해주세요.