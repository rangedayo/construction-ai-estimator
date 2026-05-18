"""회귀 테스트 — 시스템 카운트와 정답지 합계를 비교한다.

라운드 2 방침: 페이지 분할 폐기. 도면을 페이지로 쪼개지 않고 '도면 전체'를
한 번 카운트해 정답지의 부호별 합계와 비교한다.

(도면, 부호) 페어는 도면 1·2·4 정답지에서 자동 생성된다.

허용 오차: 정답이 5 이하면 ±1, 그 외엔 상대오차 5% 이하
(ground_truth.within_tolerance).
모든 비교는 결정론적이다(순수 ezdxf + 룰 기반, LLM 호출 없음).

실행:  poc_v2 디렉토리에서  `pytest -v`
"""
from __future__ import annotations

import functools
import os
import sys

import pytest

# poc_v2(=counter.py 위치)와 tests/ 를 import 경로에 추가
_HERE = os.path.dirname(os.path.abspath(__file__))
_POC_DIR = os.path.dirname(_HERE)
for _path in (_POC_DIR, _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from counter import count_members  # noqa: E402
from ground_truth import (  # noqa: E402
    PROJECT_ROOT,
    drawing_symbol_totals,
    load_text_height_filter,
    within_tolerance,
)

# 도면 전체를 포함하도록 충분히 큰 bbox (좌표 필터를 항상 통과)
_FULL_EXTENT = (-1e18, -1e18, 1e18, 1e18)

_DEFAULT_DXF_FILES = {
    "도면1": "도면1.dxf",
    "도면2": "도면2.dxf",
    "도면4": "도면4.dxf",
}


def _dxf_path(drawing: str) -> str:
    return os.path.join(
        PROJECT_ROOT, "sample_data", _DEFAULT_DXF_FILES.get(drawing, f"{drawing}.dxf")
    )


# 도면별 텍스트 height 임계값 (config/symbol_rules.yaml 기반)
_HEIGHT_FILTER = load_text_height_filter()


@functools.lru_cache(maxsize=None)
def _whole_drawing_counts(drawing: str) -> dict[str, int]:
    """도면 전체에서 정답지에 등장하는 부호들을 카운트(도면당 1회, 캐시)."""
    symbols = sorted(drawing_symbol_totals()[drawing].keys())
    min_h = _HEIGHT_FILTER.get(drawing)
    counts, _hits, _coords = count_members(
        _dxf_path(drawing), *_FULL_EXTENT,
        custom_whitelist=symbols, min_text_height=min_h,
    )
    return dict(counts)


# ── 파라미터 케이스 빌드 — (도면, 부호) 페어 자동 생성 ──────────────────────────
_TOTALS = drawing_symbol_totals()

_TOTAL_CASES: list = []
for _drawing in sorted(_TOTALS):
    for _symbol, _expected in sorted(_TOTALS[_drawing].items()):
        _TOTAL_CASES.append(
            pytest.param(_drawing, _symbol, _expected, id=f"{_drawing}-{_symbol}")
        )


@pytest.mark.parametrize("drawing,symbol,expected", _TOTAL_CASES)
def test_symbol_total(drawing: str, symbol: str, expected: int) -> None:
    """도면 전체에서 부호별 총합이 정답지 합계와 허용 오차 내인지 검증."""
    predicted = _whole_drawing_counts(drawing).get(symbol, 0)
    assert within_tolerance(predicted, expected), (
        f"[{drawing}] 부호 {symbol}: 예측 {predicted} / 정답합계 {expected} "
        f"(차이 {predicted - expected:+d})"
    )
