"""라운드 베이스라인-2 — 작은 도면 입력 모델 통일.

큰 도면(`도면N.dxf`) 대신 시트 단위로 분리된 작은 도면 dxf 1장을 입력으로 받아,
표제부 도면명을 자동 추출(`sheet_title_extractor`)하고 정답지 시트명과 매칭
(`sheet_name_matcher`)한 뒤, 본선 측정 함수(카운트·길이·규격)를 재사용해
시트별 PASS/FAIL 을 산출한다(`small_drawing_pipeline`).

설계 원칙
    * 본선 무수정 — counter.py / baseline.py / length/* / config/*.yaml 그대로.
      이 패키지는 본선 함수를 import 해 호출만 한다.
    * 결정론 — LLM·랜덤 0건. 동일 입력 → 동일 출력.
"""
