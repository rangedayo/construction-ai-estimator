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

from baseline import predict  # noqa: E402
from ground_truth import drawing_symbol_totals, within_tolerance  # noqa: E402


@functools.lru_cache(maxsize=None)
def _whole_drawing_counts(drawing: str) -> dict[str, int]:
    """도면 전체 부호별 최종 카운트(도면당 1회, 캐시).

    라운드 5 부터 baseline.predict 를 거쳐 정책 P(일람표·규격 안내 제외)까지
    적용된 카운트를 쓴다. 정책 P 가 비활성인 도면1·2 는 기존 동작과 동일하다.
    """
    return predict(drawing)


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
