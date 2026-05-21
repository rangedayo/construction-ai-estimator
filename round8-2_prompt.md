# 라운드 8 작업 2 — 옵션 2 채택 (policy_override 로 도면3 신호 3 강제 ON)

## 결정 배경

라운드 8 사전 진단(`outputs/round8_사전진단.md`) 결과 옵션 2 채택. 근거:

- 옵션 2 만이 도면1·2·4 베이스라인 영향 0% 보장
- 라운드 6에서 도입한 `policy_override` 의 정당한 사용 (자동 판단이 못 잡는 예외)
- 보정 시뮬레이션에서 도면3 4/4 PASS 확인됨

## 변경 파일 (총 4개)

### 1. `poc_v2/counter.py` — match_symbol 슬래시 단어 경계 추가

라운드 2에서 도입한 부분일치 매칭의 단어 경계 문자에 슬래시(`/`) 추가.

**MC10 오매칭 방지 룰 유지**: 부호 뒤 첫 글자가 숫자면 매칭 실패. 슬래시는 숫자가 아니므로 통과.

검증: `C1/P1` 텍스트 → `C1` 매칭 PASS. `MC10` 텍스트 → `MC1` 매칭 FAIL (라운드 2 동작 그대로).

### 2. `config/symbol_rules.yaml` — 도면3 두 줄 추가

```yaml
text_height_filter:
  도면1:
    min_height: 177
  도면2:
    min_height: 302
  도면3:
    min_height: null    # 추가. 도면3 height 구조가 도면1·2와 정반대(본체가 작은 글자)이므로 필터 사용 금지.
  도면4:
    min_height: null

policy_override:
  도면3:                # 추가. 신호 3 자동 판정이 규격 텍스트 1개로 임계값 미달이라 강제 ON.
    exclude_table_regions: true
    exclude_with_spec: true
```

**주석 그대로 yaml에 박을 것.** 라운드 9 이후 다른 작업자가 와도 왜 도면3만 override 했는지 알 수 있게.

### 3. `poc_v2/tests/baseline.py` — _DEFAULT_DXF_FILES 에 도면3 추가

도면3 DXF 파일 경로를 baseline 함수의 기본 인자에 추가. 정확한 경로는 프로젝트 구조에 맞게.

### 4. `poc_v2/tests/test_regression.py` — drawings 화이트리스트에 도면3 추가

```python
_TOTALS = drawing_symbol_totals(
    category="기둥",
    drawings=["도면1", "도면2", "도면3", "도면4"],
)
```

## 절대 조건 — 회귀 안전망

작업 후 `pytest -v` 결과:

- **도면1 기둥 4종 (MC1, MC2, MC3, SC1) — 전부 PASS 유지** (절대 조건)
- **도면2 기둥 SC1·SC2 — 라운드 6 baseline 그대로 FAIL 유지** (분리 TEXT 미해결)
- **도면3 기둥 4종 (C1, C2, C3, C4) — 전부 PASS** (이번 라운드 신규)
- **도면4 기둥 SC1·SC2 — 전부 PASS 유지** (절대 조건)

**기대 결과: 10 / 12 통과.**

도면2 두 건 외 다른 케이스가 FAIL이면:

- 도면1·4 깨졌으면 → 즉시 롤백, 원인 분석
- 도면3 일부 FAIL이면 → 사전 진단 시뮬레이션(`outputs/round8_사전진단.md` 보정 시뮬레이션 표)과 실제 결과 비교해서 어디서 어긋났는지 분석

## 작업 순서

1. 1번 (counter.py 매칭 확장) 완료
2. **중간 회귀**: `pytest -v` 로 도면1·2·4 결과가 라운드 7 baseline (6 PASS / 2 FAIL)과 완전히 동일한지 확인 — 슬래시 매칭 추가만으로 기존 회귀가 안 깨지는지 검증
3. 2번 (yaml 두 줄 추가) 완료
4. 3번 (baseline.py 경로 추가) 완료
5. 4번 (test_regression.py drawings 확장) 완료
6. **최종 회귀**: `pytest -v` 로 10/12 확인

중간 회귀(2단계)에서 도면1·2·4가 깨지면 즉시 1단계로 롤백.

## 금지 사항

- `auto_policy.py` 변경 금지 (자동 판정 로직 그대로)
- `auto_policy_params.spec_pattern_threshold` 값 변경 금지 (도면1·2·4 영향 보호)
- `ground_truth.py`, `detect_table_region.py` 변경 금지
- 외부 라이브러리 추가 금지

## 작업 완료 보고 양식

1. 변경된 4개 파일의 diff
2. **중간 회귀 결과** (도면1·2·4만 검사 시 6 PASS / 2 FAIL 동일성 확인)
3. **최종 회귀 결과** — 통과/실패 케이스 수
4. 도면3 4종 결과 (C1, C2, C3, C4 각각 예측/정답/PASS-FAIL)
5. 사전 진단의 보정 시뮬레이션과 실제 결과 대조 (일치/불일치)
6. 부작용 발생 여부
