"""기둥 길이 회귀 테스트 — 라운드 길이-1.

각 (도면, 부호) 페어를 정답지에서 자동 생성한 파라미터로 검증.
1단계 회귀(`poc_v2/tests/test_regression.py`)와 독립.

허용 오차
    expected ≤ 1000mm : ±50mm
    expected > 1000mm : ±2%

실행
    프로젝트 루트에서  `pytest -v poc_v2/length/tests`
"""
from __future__ import annotations

import functools
import os
import sys
from typing import Optional

import pytest

# 프로젝트 루트를 sys.path 에 추가 (poc_v2.length 패키지 import 용)
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from poc_v2.length.baseline_length import (  # noqa: E402
    predict,
    within_length_tolerance,
)
from poc_v2.length.ground_truth_length import (  # noqa: E402
    load_ground_truth_length,
)


@functools.lru_cache(maxsize=None)
def _whole_drawing_lengths(drawing: str) -> dict[str, Optional[float]]:
    """도면 단위 부호→길이 (도면당 1회 측정·캐시)."""
    return predict(drawing)


def _build_cases() -> list:
    """(도면, 부호, 정답 길이) 케이스를 정답지에서 자동 생성.

    같은 부호가 여러 인스턴스로 등장하지만 정답 길이는 모두 동일하다는
    데이터 특성을 이용해 첫 번째 유효 길이를 expected 로 사용한다.
    측정 소스가 "(소스 도면 없음)" 인 인스턴스(예: 도면1 1동)는 ground_truth
    로더가 자동 제외한 상태로 들어온다.
    """
    gt = load_ground_truth_length()
    cases: list = []
    for drawing in sorted(gt):
        sym_to_lens: dict[str, list[float]] = {}
        for _source, syms in gt[drawing].items():
            for sym, lens in syms.items():
                sym_to_lens.setdefault(sym, []).extend(lens)
        for symbol in sorted(sym_to_lens):
            lens = [length for length in sym_to_lens[symbol] if length is not None]
            if not lens:
                continue
            expected = lens[0]
            cases.append(
                pytest.param(drawing, symbol, expected, id=f"{drawing}-{symbol}")
            )
    return cases


_CASES = _build_cases()


@pytest.mark.parametrize("drawing,symbol,expected", _CASES)
def test_column_length(drawing: str, symbol: str, expected: float) -> None:
    """도면별 × 부호별 길이가 정답 허용 오차 안에 있는지 검증."""
    lengths = _whole_drawing_lengths(drawing)
    predicted = lengths.get(symbol)
    assert within_length_tolerance(predicted, expected), (
        f"[{drawing}] 부호 {symbol}: 예측 {predicted} mm / 정답 {expected:.0f} mm"
    )
