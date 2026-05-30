# 라운드 3 — 도면1 height 필터 적용 + 도면2 진단

## 현재 상황 요약

라운드 2까지 완료. 도면1 베이스라인 측정 결과:
- 총합 예측 375 vs 정답 331, 차이 +44
- 22개 부호 중 7개만 통과 (그중 정확히 일치는 BR2 1개뿐, 나머지 6개는 +1 과다지만 허용 룰에 걸려 통과)
- **진단 결과**: 작은 글자(height 159·176) 총 44개 = 과다분 +44와 1:1 정확 대응
- 모든 부호의 텍스트 height가 "큰 글자(부재 실표기)"와 "작은 글자(오탐, 159·176)" 두 무리로 또렷이 갈림

라운드 2에서 검증된 가설: **height > 176만 카운트하면 도면1 22개 부호 전부 정답과 정확 일치**.

이번 라운드는 이 가설을 실제 코드에 박고, 그다음 도면2가 같은 구조인지 진단까지만 한다.

---

## 작업 원칙 (반드시 지킬 것)

1. **한 번에 하나만 변경.** 변경할 때마다 회귀 테스트 돌려서 결과 보고.
2. **도면 특성은 코드에 박지 말고 설정 파일로.** 임계값 176을 counter.py에 하드코딩 금지.
3. **검증된 자산 보존.** `counter.py`의 BR2 부분 일치 매칭, 블록 내부 텍스트 처리는 절대 건드리지 말 것. 시그니처(`count_members(...)`)도 유지해서 `app.py`가 깨지지 않게.
4. **외부 도구 추가 금지.** DBSCAN, OCR, 비전 모델, Shapely 같은 거 새로 끌어오지 말 것. 1단계 본질은 ezdxf 텍스트 정확히 다루는 것.
5. **자동 감지 모드 건드리지 말 것.** 화이트리스트 방식이 정답. 자동 감지(`custom_whitelist=None`)는 진단용으로만 살아있고, 그 출력의 X·Y·F·DS·THK 등은 정답에 안 들어가도 정상.

---

## 작업 1 — 도면별 임계값 설정 파일 구조 추가

`config/symbol_rules.yaml`에 도면별 텍스트 height 임계값 항목 추가.

```yaml
# 기존 화이트리스트, 제외 prefix는 그대로 유지하고 아래만 추가
text_height_filter:
  도면1:
    min_height: 177       # height > 176만 카운트 (159·176 작은글자 제외)
  도면2:
    min_height: null      # 진단 전이므로 필터 미적용
  도면4:
    min_height: null      # 진단 전이므로 필터 미적용
```

`null`은 "필터 미적용(모든 height 카운트)"을 의미한다.

---

## 작업 2 — counter.py에 height 필터 인자 추가

`count_members(...)` 함수 시그니처에 `min_text_height: float | None = None` 인자를 추가.

```python
def count_members(
    dxf_path: str,
    xmin: float, ymin: float, xmax: float, ymax: float,
    custom_whitelist: list[str] | None = None,
    min_text_height: float | None = None,   # 새 인자
):
    ...
```

동작:
- `min_text_height is None`이면 기존 동작 그대로 (모든 height 카운트)
- `min_text_height`가 숫자면 TEXT/MTEXT의 `dxf.height`가 그 값 **이상**인 것만 카운트
- ATTRIB, 블록 내부 텍스트도 동일하게 적용 (텍스트 엔티티 종류 무관하게 height 비교)
- height 정보가 없는 엔티티는 안전하게 통과시킴 (즉 필터 대상 아님)

**주의:**
- 기본값 `None`이라 `app.py`는 그대로 작동해야 함
- BR2 부분 일치 매칭 로직은 절대 건드리지 말 것
- 좌표 bbox 필터(xmin~xmax)는 그대로 유지

---

## 작업 3 — baseline.py, test_regression.py가 설정 파일을 읽도록 수정

`baseline.py`와 `test_regression.py`가 `count_members` 호출 시 도면별 임계값을 자동으로 넘기게:

```python
# 설정 파일에서 도면별 min_height 로드
height_filter = load_text_height_filter()  # symbol_rules.yaml 읽음
min_h = height_filter.get(drawing, {}).get("min_height")
counts, _, _ = count_members(dxf, *_FULL_EXTENT, custom_whitelist=symbols, min_text_height=min_h)
```

`load_text_height_filter` 같은 헬퍼를 `ground_truth.py`나 새 모듈에 추가해도 좋음. 단, **별도 모듈 만들면 import 경로 복잡해지므로 ground_truth.py에 같이 두는 게 깔끔함**.

---

## 작업 4 — 도면1 회귀 테스트 통과 확인

`python tests/baseline.py 도면1` 실행 결과 보고.

**기대 결과:**
- 22개 부호 전부 PASS
- 총합 예측 331 vs 정답 331, 차이 0
- 차이 0인 부호 22개

**기대와 다르면 즉시 보고. 임의로 패치하지 말 것.** 예를 들어:
- 일부 부호가 여전히 +1 과다 → 임계값 177이 너무 낮음, 178이나 197로 조정해야 할 수 있음
- 어떤 부호가 -1 과소 → 정상 부재의 글자가 작아서 잘려나간 것. 매우 위험한 신호
- 차이 0이 아닌 부호 명단을 표로 보고

그다음 `pytest -v tests/test_regression.py -k 도면1` 실행 결과도 같이 보고. 22개 케이스 전부 PASS 예상.

---

## 작업 5 — 도면2 height 진단 (필터 적용 X, 분석만)

`tests/analyze_heights.py`가 도면2에도 작동하게 인자 추가:

```bash
python tests/analyze_heights.py 도면2
```

출력해야 할 것:
1. **부호별 height 출현 횟수 표** (도면1과 동일 포맷)
   - 정답지에 있는 부호만 (자동 감지 X)
   - 부호별로 height 값과 출현 횟수
2. **두 무리 갈림 여부 판정**
   - "큰 글자/작은 글자" 두 무리로 또렷이 갈리는가?
   - 갈린다면 추천 임계값은 얼마인가?
   - 안 갈린다면 분포가 어떻게 생겼는가? (단일 봉우리, 여러 봉우리, 연속 분포 등)
3. **도면1과 비교**
   - 도면2의 작은 글자 height 값이 도면1과 같은가? (159·176 그대로? 다른 값?)
   - 큰 글자 height 값 범위는?

도면2에 대한 `baseline.py` 실행도 같이 (필터 없는 상태 그대로).

---

## 작업 6 — 도면2 진단 리포트 작성

`round3_도면2_진단.md` 파일로 다음 내용 정리:

1. 도면2 height 분포 (작업 5 결과)
2. 도면2 베이스라인 (필터 없이 카운트했을 때 부호별 차이)
3. 도면2도 정책 A(height 필터) 단독으로 풀 수 있는가? 아니면 다른 패턴이 보이는가?
4. 라운드 4 권고 사항 — 임계값 절대값/상대규칙 결정, 다른 정책 필요 여부

**도면2의 임계값을 추측해서 설정 파일에 박지 말 것.** 이번 라운드는 도면2 진단까지가 끝이고, 임계값 결정은 라운드 4에서.

---

## 작업 7 — 도면4는 이번 라운드 작업 대상 아님

도면4는 ATTRIB 인코딩이라 또 다른 변수가 있음. 도면1·2가 안정된 후 라운드 5 이상에서 다룬다. 이번엔 건드리지 말 것.

---

## 최종 보고 형식

작업 끝나면 다음 4개 묶음으로 보고:

1. **변경 파일 목록**: 어떤 파일을 어떻게 수정했는지 (config/symbol_rules.yaml, counter.py, baseline.py, test_regression.py, analyze_heights.py)
2. **도면1 baseline 결과 표**: 라운드 2 결과와 라운드 3 결과 비교 표 (총합, 통과 부호 수, 차이)
3. **도면2 진단 요약**: 작업 6의 `round3_도면2_진단.md` 핵심 내용
4. **라운드 4 권고**: 도면2 임계값 결정 방향, 위험 요소

---

## 회귀 테스트 통과 기준 (라운드 3 종료 조건)

- ✅ 도면1: 22/22 부호 정확 일치 (차이 0), 총합 331=331
- ✅ 도면2: 진단 리포트 완성 (필터 미적용 상태 그대로 카운트해도 됨, 통과 안 해도 됨)
- ✅ 기존 회귀 테스트가 깨지지 않음 (app.py 정상 작동, BR2 매칭 유지)

이 셋 다 만족하면 라운드 3 종료.
