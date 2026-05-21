라운드 9 작업 2 — 도면5 기둥 회귀 추가 (갈래 α-).
배경
라운드 9 사전 진단(outputs/round9_사전진단.md) 완료. 핵심 결과:

도면5 본체는 슬래시 결합형(C1/P1·C2/P2·C3/P3·C4/P4), 도면3와 동형
라운드 8 부채(auto_policy/baseline 일람표 검출 불일치) 비재현 — 도면5는 본체가 자유 텍스트 입력에 끼지 않아 5컷 적용/미적용 결과 동일
자동 판정만으로 4/4 PASS 가능 (시나리오 A 시뮬 통과)
결정: 갈래 α- 채택 — policy_override.도면5 = null, min_height = null

도면3 부채는 도면3 특수성으로 확정. 도면5는 라운드 6 simulate_new_drawing 정신대로 "min_height 한 줄(이 경우 null)"만 추가하면 자동 정책으로 풀린다.
작업 — 4개 파일 변경 + 회귀
작업 2-A. config/symbol_rules.yaml
text_height_filter 블록에 도면5 entry 추가:
yamltext_height_filter:
  도면1:
    min_height: 177
  도면2:
    min_height: 302
  도면3:
    min_height: null
  도면4:
    min_height: null
  도면5:
    min_height: null    # 라운드 9: 본체(448.0) ↔ 일람표(413.4) 갭 34.6 으로
                        # 분리 깨끗하지 않음 (라운드 6 D항 원칙). 자동 정책으로 4/4 PASS.
policy_override 블록에 도면5 entry 추가:
yamlpolicy_override:
  도면1: null
  도면2: null
  # 도면3: 라운드 8 검증으로 효과 분리 확인
  #   (기존 주석 유지)
  도면3:
    exclude_table_regions: true
    exclude_with_spec: true
  도면4: null
  도면5: null  # 라운드 9: 자동 판정이 정확 작동 (사전 진단 6 비재현 확정).
               # 도면3와 본체 표기는 동형(슬래시 결합)이지만, auto_policy 의
               # exclude_with_spec=True 필터링으로 자유 텍스트 입력이 깨끗 →
               # _TABLE_SPARSE_MAX=5 보정 부재의 영향을 받지 않음 → 신호 2 자동 ON.
               # 라운드 6 D항·라운드 8 H항 인계 메모대로 "도면3 특수성 확정 / override 유지".
작업 2-B. poc_v2/tests/baseline.py
_DEFAULT_DXF_FILES 에 도면5 등록:
python_DEFAULT_DXF_FILES = {
    "도면1": "도면1.dxf",
    "도면2": "도면2.dxf",
    "도면3": "도면3.dxf",
    "도면4": "도면4.dxf",
    "도면5": "도면5.dxf",
}
도면5.dxf 파일은 사용자가 sample_data/도면5.dxf 경로에 배치. 없으면 안내.
작업 2-C. poc_v2/tests/test_regression.py
drawings 화이트리스트에 "도면5" 추가:
python_TOTALS = drawing_symbol_totals(
    category="기둥",
    drawings=["도면1", "도면2", "도면3", "도면4", "도면5"],
)
작업 2-D. counter.py · auto_policy.py · detect_table_region.py — 미변경
라운드 8 보편 룰(슬래시 매칭 + 일람표 5컷)이 그대로 작동. 어떤 코드도 손대지 않는다.
작업 3 — 회귀 실행 + 시뮬레이션 대조
pytest -v poc_v2/tests/test_regression.py
기대 결과: 14 passed / 2 failed

도면1 MC1·MC2·MC3·SC1 (4 PASS)
도면2 SC1·SC2 (2 FAIL — 라운드 5 갈래 C 보류, 변동 없음)
도면3 C1·C2·C3·C4 (4 PASS)
도면4 SC1·SC2 (2 PASS)
도면5 C1·C2·C3·C4 (4 PASS — 신규)

회귀 결과가 사전 시뮬레이션 카운트와 일치하는지 대조:
부호사전 시뮬 rawafter_spec일람표 1곳 차감정답회귀 결과톨로런스C14432?±1C26654?±1C39988?정확C47766?정확
C1·C2가 ±1 톨로런스로 PASS인 것은 정상 (라운드 6 합의: 정답 5 이하 ±1 / 그 외 상대오차 5%).
작업 4 — 라운드 9 보고서 작성
파일명: outputs/round9_도면5_기둥_추가.md. 라운드 6·8 보고서 형식 그대로.
포함 섹션:
A. 1단계 전체 진척 (라운드 1~9) — 도면5 신규 4/4 추가, 회귀 14/16.
B. 라운드 9 변경 사항 — yaml 2줄(text_height_filter·policy_override), baseline.py 1줄, test_regression.py 1줄. counter.py·auto_policy.py·detect_table_region.py 미변경 명시.
C. 사전 진단 결과 요약 — outputs/round9_사전진단.md 핵심 표 참조 (height 분포 / 표기 방식 / 슬래시 결합 / 일람표 검출 비교 / 갈래 추천).
D. 갈래 α- 결정 근거 — 다음 문장 명시:

도면5는 슬래시 결합 표기가 본체 카운트와 정확히 일치하고(C1/P1=2, C2/P2=4, C3/P3=8, C4/P4=6 = 정답), auto_policy 의 신호 2·3 자동 판정이 모두 옳은 결과를 산출(시나리오 A 시뮬 4/4 PASS). 라운드 6 "AI는 결정만, 도구는 측정만" 원칙대로 자동 판정을 신뢰하고 override 를 박지 않는다.

라운드 6 simulate_new_drawing 검증과 일치하는 경로 — 신규 도면이 자동 정책으로 풀린 두 번째 사례(첫 번째: 도면1_clone, 라운드 6).
E. 라운드 8 부채 추적 결과
라운드 8 H 섹션의 인계 메모 인용:

"재현되지 않으면 도면3 특수성으로 확정하고 override 유지."

도면5 진단 결과: 비재현. 도면5 본체가 슬래시 결합형이라 load_text_layout(exclude_with_spec=True) 에서 None 필터링 → 자유 텍스트 입력이 깨끗 → 5컷 적용/미적용 결과 동일.
→ 부채 항목 "auto_policy/baseline 일람표 검출 입력 전처리 불일치" 를 "도면3 특수성으로 확정" 상태로 갱신. 라운드 H 표에서 "신규" → "확정".
F. 회귀 결과
pytest 14 passed / 2 failed. 사전 시뮬레이션과 회귀 결과 대조표 (위 작업 3 표).
G. 도면1·2·3·4 무손상 확인
도면케이스결과비고도면1MC1·MC2·MC3·SC14/4 PASS절대 조건 유지도면2SC1·SC20/2 (사전 보류)변동 없음도면3C1·C2·C3·C44/4 PASS라운드 8 결과 유지도면4SC1·SC22/2 PASS절대 조건 유지
H. 1단계 미해결 항목 업데이트
항목라운드상태비고도면2 SC1·SC2 분리 TEXT4·5보류변동 없음도면4 SB1 좌표 중복5보류변동 없음신호 1 (min_height) 자동화6·8·9보류도면5 도 갭 분리 깨끗하지 않음 — 라운드 6 D항 결론 재확인auto_policy/baseline 일람표 검출 입력 전처리 불일치8 → 9도면3 특수성 확정도면5 진단으로 비재현 확인. 통일 작업 정당성 부족 — override 유지
I. 1단계 핵심 학습 (라운드 9 추가)

라운드 8 부채가 도면3 특수성으로 확정됨 — 인계 메모의 "재현 여부로 결정" 약속이 정직하게 이행됨. 도면 하나로 일반화하지 않고 두 도면 비교로 근거 확보한 사례.
라운드 6 "AI는 결정만, 도구는 측정만" 의 자동 정책이 *두 번째 신규 도면(도면5)*에서 잘 동작함을 검증. 도면1_clone(라운드 6) 에 이어 자동화 신뢰도 누적.
도면 3·5 둘 다 슬래시 결합 표기를 쓰지만, 자유 텍스트의 밀도(도면3: 본체+일람표 자유 텍스트 / 도면5: 일람표만 자유 텍스트)에 따라 auto_policy 판정 결과가 갈린다 — 표기 형식이 같아도 도면 구조에 따라 자동 판정 결과가 달라질 수 있음. 라운드 6의 자동화 한계 인식 정교화.

J. 라운드 9 종료 조건 점검

✅ 도면1·2·3·4 회귀 무손상
✅ 도면5 4/4 신규 추가
✅ counter.py·auto_policy.py·detect_table_region.py 미변경
✅ 외부 라이브러리·LLM 도입 없음
✅ yaml 추가 2줄 + baseline·test_regression 등록 1줄씩 (최소 변경)
✅ 라운드 8 부채 추적 약속 이행 — 도면3 특수성 확정
✅ 갈래 α- 결정 근거 명시 (자동 판정 우선 원칙)

K. 변경 파일 목록
파일변경config/symbol_rules.yamltext_height_filter.도면5.min_height: null 추가, policy_override.도면5: null 추가 (도면3와의 차이 주석 포함)poc_v2/tests/baseline.py_DEFAULT_DXF_FILES 에 "도면5": "도면5.dxf" 추가poc_v2/tests/test_regression.pydrawings 화이트리스트에 "도면5" 추가outputs/round9_사전진단.md신규 — 사전 진단 보고서outputs/round9_도면5_기둥_추가.md신규 — 본 보고서 (라운드 9 마감)
counter.py·auto_policy.py·detect_table_region.py·ground_truth.py 미변경.
출력 항목

yaml 두 블록(text_height_filter, policy_override) diff
baseline.py·test_regression.py diff
회귀 결과 (14/2 기대)
사전 시뮬 vs 회귀 결과 대조표
라운드 9 보고서 파일 경로

작업 시작해주세요.