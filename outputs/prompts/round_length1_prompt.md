# 라운드 길이-1 — DIMENSION 기반 기둥 길이 자동 추출

## 배경 및 목적

1단계(개수 카운팅)는 도면1~5 회귀 14/16 PASS 상태로 완료. 이제 2단계 **기둥 길이 추출**로 진입.

기둥 길이 추출 알고리즘은 사전 분석에서 결정됨:
**"세로 방향 DIMENSION 엔티티의 measurement 값 중 최댓값"**

사전 검증 결과 (모든 단면도·골구도 포함 9개 파일 100% 정확):

| 도면 | 파일 | 정답(mm) | 세로 DIM 최대값 | 결과 |
|---|---|---|---|---|
| 도면1 | 2동_Y01열골구도 | 6000 | 6000 | ✅ |
| 도면1 | 2동_Y03열골구도 | 6000 | 6000 | ✅ |
| 도면1 | 2동_Y05열골구도 | 6000 | 6000 | ✅ |
| 도면2 | 가나동_종단면도 | 7700 | 7700 | ✅ |
| 도면2 | 가나동_횡단면도 | 7700 | 7700 | ✅ |
| 도면3 | 종단면도 | 19060 | 19060 | ✅ |
| 도면3 | 계단단면도 | 19060 | 19060 | ✅ |
| 도면4 | 종단면도 | 9000 | 9000 | ✅ |
| 도면4 | 횡단면도 | 9000 | 9000 | ✅ |
| 도면5 | 주단면도1 | 10500 | 10500 | ✅ |
| 도면5 | 주단면도4 | 10500 | 10500 | ✅ |

본 라운드 목적:
1. 알고리즘을 정식 모듈로 구현
2. 회귀 테스트 인프라 구축 (1단계 패턴 그대로)
3. 시각화 도구로 사람이 검증 가능하게 만들기

본 라운드는 신규 모듈 + 회귀 테스트 + 시각화 도구 신설. 1단계 카운팅 모듈(`counter.py`·`baseline.py`)은 미수정. 1단계 회귀 영향 0.

## 사전 분석 핵심 발견

### 발견 1: 정답은 모두 DIMENSION 엔티티의 measurement에 존재
- ezdxf로 `DIMENSION` 엔티티 순회 → `get_measurement()` 호출 → 측정값 획득
- 9/9 파일에서 정답값이 DIMENSION에 정확히 존재

### 발견 2: 가장 큰 DIMENSION을 그냥 채택하면 안 됨
- 도면에는 건물 너비, 지붕 폭, 기둥 사이 간격 등 더 큰 가로 치수가 존재
- 예: 도면5 주단면도4 가장 큰 DIM = 23000mm (가로, 건물 폭) vs 정답 10500mm (세로, 기둥)

### 발견 3: 방향 판별이 핵심
- DIMENSION의 `defpoint2`·`defpoint3` 좌표 차이로 방향 판별
- 세로 치수: `abs(p2.y - p3.y) > abs(p2.x - p3.x) * 5`
- 가로 치수: `abs(p2.x - p3.x) > abs(p2.y - p3.y) * 5`
- 세로 치수 중 최댓값 = 기둥 길이

### 발견 4: LINE 기반 알고리즘은 부적합
- 빈도 기반: 골구도만 통함 (3/3), 단면도 0/8 실패
- 가장 긴 수직선: 통심선(CEN/A-CEN 레이어)이 잡혀서 항상 정답보다 김
- LINE은 fallback으로만 검토 (현재 9개 도면에서는 DIMENSION만으로 충분)

## 작업 0 — 사전 정리

`poc_v2/length/` 디렉토리 신설. 본 라운드 모든 신규 파일은 이 하위에 둠. 기존 1단계 코드 디렉토리 구조 (`poc_v2/`, `poc_v2/tests/`, `config/`)는 그대로 유지.

## 작업 1 — 정답지 로더 (`poc_v2/length/ground_truth_length.py`)

1단계의 `tests/ground_truth.py` 패턴을 그대로 따라하되, 길이 정답지(`도면_길이_정답지.xlsx`)에 맞춰 조정.

```python
def load_ground_truth_length() -> dict:
    """
    도면_길이_정답지.xlsx의 도면N-기둥-길이 시트를 파싱.
    
    Returns
    -------
    {
        "도면1": {
            "(2동)Y01열골구도, (2동)Y03,Y05열골구도": {
                "MC1": [6000, 6000, ..., 6000],  # 인스턴스별 길이 리스트
                "MC2": [...],
                ...
            },
            ...
        },
        "도면2": {
            "가,나동 횡단면도": {"SC1": [7700]*10, "SC2": [7700]*4},
        },
        ...
    }
    """
```

요구사항:
- 길이값이 `None`인 행은 제외 (예: 도면1 1동 인스턴스들 — "산출 불가")
- 부호별로 길이값을 리스트로 모으되, 정답이 항상 동일하면 단일 값으로 단순화 가능
- 시트 하단의 "── 부호별 요약 (자동) ──" 섹션은 무시
- `도면라우팅` 시트도 별도 함수 `load_routing()`으로 로드 (다음 작업에서 사용)

## 작업 2 — 측정 매핑 설정 (`config/length_routing.yaml`)

도면별 측정 소스 파일과 측정 방법을 yaml로 분리. 1단계의 `config/symbol_rules.yaml` 패턴과 동일.

```yaml
# 길이 측정 라우팅
# 각 도면별로 측정에 사용할 DXF 파일과 부호별 매핑을 정의
# 정답지의 "측정 소스 도면" 컬럼을 반영

drawings:
  도면1:
    sources:
      - file: sample_data/length/도면1-기둥-길이_2동_Y01열골구도.dxf
        sheet_name: "(2동)Y01열골구도, (2동)Y03,Y05열골구도"
        applies_to: [MC1, MC2, MC3, SC1]  # 이 파일이 측정 대상으로 삼는 부호들
        method: dimension_max_vertical
      - file: sample_data/length/도면1-기둥-길이_2동_Y03열골구도.dxf
        sheet_name: "(2동)Y01열골구도, (2동)Y03,Y05열골구도"
        applies_to: [MC1, MC2, MC3, SC1]
        method: dimension_max_vertical
      - file: sample_data/length/도면1-기둥-길이_2동_Y05열골구도.dxf
        sheet_name: "(2동)Y01열골구도, (2동)Y03,Y05열골구도"
        applies_to: [MC1, MC2, MC3, SC1]
        method: dimension_max_vertical
  
  도면2:
    sources:
      - file: sample_data/length/도면2-기둥-길이_가나동_횡단면도.dxf
        sheet_name: "가,나동 횡단면도"
        applies_to: [SC1, SC2]
        method: dimension_max_vertical
  
  도면3:
    sources:
      - file: sample_data/length/도면3-기둥-길이_종단면도.dxf
        sheet_name: "종단면도, 계단단면도"
        applies_to: [C1, C2, C3, C4]
        method: dimension_max_vertical
      - file: sample_data/length/도면3-기둥-길이_계단단면도.dxf
        sheet_name: "종단면도, 계단단면도"
        applies_to: [C1, C2, C3, C4]
        method: dimension_max_vertical
  
  도면4:
    sources:
      - file: sample_data/length/도면4-기둥-길이_종단면도.dxf
        sheet_name: "종단면도, 횡단면도"
        applies_to: [SC1, SC2]
        method: dimension_max_vertical
      - file: sample_data/length/도면4-기둥-길이_횡단면도.dxf
        sheet_name: "종단면도, 횡단면도"
        applies_to: [SC1, SC2]
        method: dimension_max_vertical
  
  도면5:
    sources:
      - file: sample_data/length/도면5-기둥-길이_주단면도1.dxf
        sheet_name: "주단면도1, 주단면도4"
        applies_to: [C1, C2, C3, C4]
        method: dimension_max_vertical
      - file: sample_data/length/도면5-기둥-길이_주단면도4.dxf
        sheet_name: "주단면도1, 주단면도4"
        applies_to: [C1, C2, C3, C4]
        method: dimension_max_vertical

# 측정 방법별 파라미터
methods:
  dimension_max_vertical:
    description: "세로 방향 DIMENSION 엔티티의 measurement 최댓값을 채택"
    direction_ratio_threshold: 5  # dy > dx * N 이면 세로 판별
    min_measurement: 100  # 100mm 미만 측정값은 무시 (디테일 치수 제외)
```

설계 원칙:
- 도면명 하드코딩은 yaml에만, 코드에는 두지 않음 (1단계 원칙 5.5)
- 방법 카테고리(`method` 필드)는 확장 가능하게 — 향후 다른 방법이 필요할 때 추가
- 같은 도면에 여러 소스 파일이 있을 때 모든 파일을 측정하고 결과를 비교 (도면3·4·5)

## 작업 3 — 길이 측정 핵심 모듈 (`poc_v2/length/measure.py`)

```python
import ezdxf
from dataclasses import dataclass
from typing import Optional

@dataclass
class DimensionInfo:
    """추출된 DIMENSION 정보"""
    measurement: float
    direction: str  # 'V', 'H', 'D' (vertical/horizontal/diagonal)
    p2: tuple  # defpoint2 좌표 (측정 시작점)
    p3: tuple  # defpoint3 좌표 (측정 끝점)
    layer: str
    override_text: Optional[str]  # 사람이 강제로 입력한 텍스트가 있는 경우
    dim_type: int  # DIMENSION 종류 (linear/aligned/angular 등)

@dataclass
class MeasurementResult:
    """측정 결과"""
    length_mm: Optional[float]
    method: str  # 'dimension_max_vertical' 등
    source_dim: Optional[DimensionInfo]  # 채택된 DIMENSION
    all_vertical_dims: list  # 모든 세로 DIMENSION (시각화/디버깅용)
    all_horizontal_dims: list  # 가로 (참고용)
    confidence: str  # 'high', 'medium', 'low'
    notes: list  # 진단 메시지

def extract_dimensions(dxf_path: str, direction_ratio: float = 5.0) -> list[DimensionInfo]:
    """DXF 파일에서 모든 DIMENSION 엔티티의 정보 추출."""
    # ezdxf로 modelspace 순회
    # DIMENSION 엔티티에서 get_measurement(), defpoint2, defpoint3 추출
    # dy / dx 비율로 방향 판별
    ...

def measure_column_length(
    dxf_path: str,
    method: str = 'dimension_max_vertical',
    min_measurement: float = 100,
    direction_ratio: float = 5.0,
) -> MeasurementResult:
    """
    DXF 파일에서 기둥 길이 측정.
    
    method='dimension_max_vertical': 세로 방향 DIMENSION 최댓값을 채택.
    """
    dims = extract_dimensions(dxf_path, direction_ratio)
    
    vertical_dims = [d for d in dims if d.direction == 'V' and d.measurement >= min_measurement]
    horizontal_dims = [d for d in dims if d.direction == 'H' and d.measurement >= min_measurement]
    
    notes = []
    
    if not vertical_dims:
        notes.append("세로 DIMENSION 없음 — 측정 불가")
        return MeasurementResult(
            length_mm=None, method=method, source_dim=None,
            all_vertical_dims=[], all_horizontal_dims=horizontal_dims,
            confidence='low', notes=notes,
        )
    
    chosen = max(vertical_dims, key=lambda d: d.measurement)
    
    # 신뢰도 판단
    # high: 가로 DIMENSION 최댓값과 명확히 구분됨 (또는 가로 없음)
    # medium: 다른 큰 세로 DIMENSION이 있음 (선택 모호)
    # low: 비고
    if horizontal_dims and max(d.measurement for d in horizontal_dims) > chosen.measurement * 1.5:
        notes.append(
            f"세로 최대 {chosen.measurement}mm, 가로 최대 {max(d.measurement for d in horizontal_dims):.0f}mm — "
            f"가로 치수가 더 크지만 기둥은 세로이므로 세로 채택"
        )
    
    confidence = 'high'
    if len(vertical_dims) >= 2:
        second_largest = sorted([d.measurement for d in vertical_dims], reverse=True)[1]
        ratio = chosen.measurement / second_largest if second_largest > 0 else float('inf')
        if ratio < 1.2:
            confidence = 'medium'
            notes.append(f"1위와 2위 차이가 작음 (비율 {ratio:.2f})")
    
    return MeasurementResult(
        length_mm=chosen.measurement,
        method=method,
        source_dim=chosen,
        all_vertical_dims=vertical_dims,
        all_horizontal_dims=horizontal_dims,
        confidence=confidence,
        notes=notes,
    )
```

설계 원칙:
- 결정론적 함수. 같은 입력 → 같은 출력
- 결과 객체에 측정에 사용된 DIMENSION 정보를 함께 반환 (시각화용)
- override_text 추출 (도면에 사람이 강제로 다른 값을 적은 경우 진단용)

## 작업 4 — 라우팅 기반 도면 측정 (`poc_v2/length/baseline_length.py`)

1단계의 `tests/baseline.py` 패턴 그대로.

```python
def measure_drawing(drawing_id: str, routing_config: dict) -> dict:
    """
    한 도면(예: 도면3)의 모든 소스 파일을 측정해 부호별 길이를 산출.
    
    Returns
    -------
    {
        "C1": {"length_mm": 19060, "sources": ["종단면도", "계단단면도"], "confidence": "high"},
        "C2": {"length_mm": 19060, "sources": ["종단면도", "계단단면도"], "confidence": "high"},
        ...
    }
    """
    sources = routing_config['drawings'][drawing_id]['sources']
    
    # 부호별로 가능한 측정값 수집
    symbol_measurements = defaultdict(list)
    for source in sources:
        result = measure_column_length(source['file'], method=source['method'])
        if result.length_mm is None:
            continue
        for symbol in source['applies_to']:
            symbol_measurements[symbol].append({
                'length': result.length_mm,
                'source_file': source['file'],
                'confidence': result.confidence,
            })
    
    # 부호별로 결정
    # 같은 부호에 여러 측정값이 있고 모두 일치하면 → 채택
    # 다르면 → 경고 + 평균/최빈 선택 + 'medium' 신뢰도
    ...

def run_baseline(routing_yaml_path: str, ground_truth_path: str):
    """
    모든 도면에 대해 측정 실행 후 정답지와 비교한 표 출력:
    [도면] [부호] [예측 mm] [정답 mm] [차이 mm] [상태] [신뢰도]
    """
    ...
```

CLI 진입점:
```bash
python -m poc_v2.length.baseline_length          # 도면1~5 전체
python -m poc_v2.length.baseline_length 도면3    # 도면3만
```

## 작업 5 — 회귀 테스트 (`poc_v2/length/tests/test_length_regression.py`)

1단계 `test_regression.py` 패턴.

```python
import pytest
from poc_v2.length.ground_truth_length import load_ground_truth_length
from poc_v2.length.baseline_length import measure_drawing
from poc_v2.length.routing import load_routing

@pytest.fixture(scope='module')
def routing():
    return load_routing('config/length_routing.yaml')

@pytest.fixture(scope='module')
def ground_truth():
    return load_ground_truth_length()

# 도면별 × 부호별 파라미터
def get_test_params():
    gt = load_ground_truth_length()
    params = []
    for drawing_id, sheets in gt.items():
        for sheet_name, symbols in sheets.items():
            for symbol, lengths in symbols.items():
                if not lengths:  # 빈 리스트 (산출 불가) 제외
                    continue
                if all(l is None for l in lengths):
                    continue
                expected = next((l for l in lengths if l is not None), None)
                if expected:
                    params.append((drawing_id, symbol, expected))
    return params

@pytest.mark.parametrize('drawing_id,symbol,expected', get_test_params())
def test_column_length(drawing_id, symbol, expected, routing, ground_truth):
    """각 (도면, 부호) 조합에 대해 측정값이 정답과 일치하는지 검증"""
    result = measure_drawing(drawing_id, routing)
    assert symbol in result, f"{drawing_id}에서 {symbol} 부호 측정 실패"
    predicted = result[symbol]['length_mm']
    
    # 톨로런스: 정답 ≤ 1000mm: ±50mm, > 1000mm: ±2%
    if expected <= 1000:
        tolerance = 50
    else:
        tolerance = expected * 0.02
    
    diff = abs(predicted - expected)
    assert diff <= tolerance, (
        f"{drawing_id} {symbol}: 예측 {predicted}mm vs 정답 {expected}mm "
        f"(차이 {diff:.0f}mm, 허용 {tolerance:.0f}mm)"
    )
```

이전 사전 분석 기준 모든 9개 파일이 오차 0mm로 통과해야 함. 도면1의 1동(산출 불가)은 정답이 None이므로 자동 제외.

`pytest -v poc_v2/length/tests/test_length_regression.py` 로 실행 가능.

## 작업 6 — 시각화 도구 (`poc_v2/length/visualize_length.py`)

1단계의 `visualize_detection.py` 패턴을 그대로 따라하되, 길이 측정에 맞춰 조정.

`poc_v3/app.py`의 `parse_dxf_for_plotly` + `build_dxf_figure`를 재사용. Streamlit 없이 순수 Plotly HTML 출력. 도면 5장 모두 처리.

기능:

### 6-1. DXF 도면 기하 렌더링 (poc_v3 재사용)
- LINE / LWPOLYLINE / POLYLINE / ARC → 회색 선
- 텍스트 라벨도 회색
- 1단계 시각화와 동일한 기본 렌더링

### 6-2. DIMENSION 오버레이
모든 DIMENSION을 도면 위에 색상별로 표시:

| 분류 | 색상 | 굵기 | 의미 |
|---|---|---|---|
| chosen (채택된 세로 DIM) | 빨강 | 4px | 측정 결과로 채택된 값 |
| other_vertical (다른 세로 DIM) | 주황 | 2px | 채택되지 않은 세로 DIM |
| horizontal (가로 DIM) | 파랑 | 2px | 가로 DIM (참고용) |
| diagonal (대각 DIM) | 회색 | 1px | 판별 불가 |

각 DIMENSION 옆에 measurement 값 텍스트로 표시. hover 시 layer·dim_type·override_text 정보 노출.

채택된 DIMENSION의 양 끝점(defpoint2·defpoint3)에 작은 십자(+) 마커 추가 — 사람이 어디서 어디까지 측정했는지 한눈에 확인 가능.

### 6-3. 정답 비교 박스
플롯 한 모서리에 작은 텍스트 박스로 결과 표시:

```
도면3 - 종단면도
부호      예측      정답      차이       상태       신뢰도
C1        19060    19060     0mm       PASS       high
C2        19060    19060     0mm       PASS       high
C3        19060    19060     0mm       PASS       high
C4        19060    19060     0mm       PASS       high
```

### 6-4. 출력
- `outputs/visualize/도면1_2동_Y01열골구도_length.html`
- `outputs/visualize/도면2_가나동_종단면도_length.html`
- ... (각 DXF 파일별 1개)

각 파일은 standalone (CDN plotly.js, 브라우저에서 바로 열림).

파일명 접미사 `_length`로 1단계 시각화(`_기둥`)와 구분.

### 6-5. CLI 진입점
```bash
python -m poc_v2.length.visualize_length                # 5개 도면 전체 처리
python -m poc_v2.length.visualize_length 도면3          # 도면3만 처리
python -m poc_v2.length.visualize_length --no-open     # 자동 브라우저 오픈 비활성화
```

기본 동작:
- 인자 없으면 전체 처리 + 첫 번째 도면 HTML을 기본 브라우저로 자동 오픈
- 특정 도면 지정 시 그 도면의 모든 파일 처리 + 첫 번째 파일 자동 오픈

## 작업 7 — 라운드 보고서 (`outputs/round_length1_보고서.md`)

가벼운 보고서.

포함 항목:

A. 라운드 목적 — DIMENSION 기반 기둥 길이 자동 측정 시스템 구축

B. 알고리즘 명세
- 핵심: "세로 DIMENSION 최댓값" (검증된 9/9 정확도)
- 방향 판별: `abs(p2.y - p3.y) > abs(p2.x - p3.x) * 5`
- 최소 측정값 필터: 100mm 이상

C. 검증 결과 표
- 도면별 × 부호별 예측 vs 정답
- 모두 오차 0mm 통과 (현재 9개 파일 기준)

D. 알려진 한계
- DIMENSION이 없는 도면(있을 경우)은 측정 불가 — fallback 미구현
- TEXT 엔티티에 길이가 적힌 비표준 도면은 미지원
- 도면 종류 자동 판별은 본 라운드 범위 외
- 보(빔) 길이 측정은 본 라운드 범위 외

E. 신설 파일 목록
- `poc_v2/length/` 하위 새 모듈들
- `config/length_routing.yaml`
- `outputs/visualize/*_length.html` (9개)

F. 향후 라운드 후보
- 라운드 길이-2: 보 길이 측정 (가로 DIMENSION 최댓값 적용)
- 라운드 길이-3: fallback 룰 (TEXT 추출, LINE 빈도) — 새 도면 추가 시 필요해질 때
- 라운드 길이-4: 총 중량 산출 (길이 × 단위중량 × 개수)

## 작업 8 — 회귀 미영향 확인

```bash
pytest -v poc_v2/tests/test_regression.py
```

1단계 카운팅 회귀 테스트가 그대로 통과하는지 확인. 본 라운드는 신규 모듈 추가만이므로 1단계 영향 0이어야 함.

## 작업 순서

1. 작업 0 (디렉토리 준비)
2. 작업 1 (정답지 로더) + 작업 2 (라우팅 yaml)
3. 작업 3 (측정 모듈 `measure.py`)
4. 작업 4 (라우팅 기반 측정 `baseline_length.py`)
5. 작업 5 (회귀 테스트) — 이 시점에 9/9 통과 확인
6. 작업 8 (1단계 회귀 미영향 확인)
7. 작업 6 (시각화) — 사람 눈으로 검증
8. 작업 7 (보고서)

작업 5와 6 사이에 1단계 회귀를 한 번 점검하는 게 안전.

## 작업 시 주의사항

- 1단계 코드 (`counter.py`, `baseline.py`, `app.py`, `config/symbol_rules.yaml`, `config/dedup_policy.yaml`)는 **건드리지 마**. 본 라운드는 신규 모듈만 추가.
- 1단계의 `tests/ground_truth.py`, `tests/test_regression.py`도 수정 금지. 길이 정답지·회귀는 `poc_v2/length/` 하위에 새로 만듦.
- 테스트는 결정론적. LLM·랜덤 요소 금지.
- 새 도면 종류가 발견되어 측정이 안 될 때는 별도 라운드에서 fallback 추가. 지금은 DIMENSION 기반만 견고하게 구현.
- 도면명·시트명 하드코딩 금지. 모두 yaml과 정답지에서 로드.
- DIMENSION 엔티티가 0개인 도면이 들어오면 측정 실패로 처리하고 `length_mm=None`, `confidence='low'`, notes에 사유 명시.

## 출력 요청

다음 순서로 결과 보고:

1. **현재 코드베이스 분석**: `poc_v2/` 구조, `counter.py`·`baseline.py` 등 1단계 코드 요약
2. **작업 0~4 구현**: 정답지 로더 → 라우팅 yaml → 측정 모듈 → 라우팅 기반 측정
3. **회귀 테스트 실행 결과**: 9개 파일 모두 PASS 확인 + 결과 표 출력
4. **1단계 회귀 미영향 확인**: `pytest -v poc_v2/tests/test_regression.py` 결과
5. **시각화 HTML 생성** + 첫 번째 파일 경로 보고
6. **보고서 작성** 및 신설 파일 목록