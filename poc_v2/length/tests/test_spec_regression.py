"""부호↔규격 추출 회귀 테스트 — 라운드 규격-1 (전수 보존 / 중량 제외).

검증 항목 (§5)
    1) 규격 정확성: 각 (도면[,동], 부호)의 정답 규격이 추출된 spec_normalized
       집합에 **포함**되는지 (dedupe 제거로 건수가 늘어도 정답이 안에 있으면 PASS)
    2) section 정확성: 도면1 1동·2동 부호가 올바른 section 으로 분류되는지
       (정답 키가 그대로 추출 키에 존재하는지로 검증)
    3) 적산 외 부재(P, BR, SBR, MF) 미혼입
    4) 보 부호(SB·SG 등) 전수 보존 — 결과에 존재
    5) 도면4 SC1 이 1층·지붕층 2건으로 보존 (dedupe 제거 확인)

중량 산출(total_weight)·단위중량(unit_weight) 테스트는 이번 라운드 범위 밖이라
제거했다. 해당 코드는 보류 상태로 삭제하지 않았다 (LLM 라우팅 라운드 이후 재개).

본선 회귀(1단계 `poc_v2/tests/test_regression.py`, 길이-1
`poc_v2/length/tests/test_length_regression.py`)는 본 파일과 독립이다.

실행
    pytest -v poc_v2/length/tests/test_spec_regression.py
"""
from __future__ import annotations

import functools
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from poc_v2.length.ground_truth_spec import load_ground_truth_spec  # noqa: E402
from poc_v2.length.spec_extractor import (  # noqa: E402
    DEFAULT_EXCLUDED_PREFIXES,
    extract_specs,
)

_DRAWINGS = ("도면1", "도면2", "도면3", "도면4", "도면5")


@functools.lru_cache(maxsize=None)
def _extractions(drawing: str) -> tuple:
    dxf_path = os.path.join(_PROJECT_ROOT, "sample_data", f"{drawing}.dxf")
    return tuple(extract_specs(dxf_path, drawing))


@functools.lru_cache(maxsize=None)
def _spec_set_by_key(drawing: str) -> dict:
    """(drawing, section, symbol) → 추출된 spec_normalized 집합 (전수)."""
    by_key: dict = {}
    for e in _extractions(drawing):
        by_key.setdefault((e.drawing, e.section, e.symbol), set()).add(
            e.spec_normalized
        )
    return by_key


def _spec_cases() -> list:
    gt = load_ground_truth_spec()
    cases: list = []
    for key, ans in sorted(
        gt.items(), key=lambda kv: (kv[0][0], kv[0][1] or "", kv[0][2])
    ):
        drawing, section, symbol = key
        section_id = section or "전체"
        cases.append(
            pytest.param(
                drawing, section, symbol, ans.spec_normalized,
                id=f"{drawing}-{section_id}-{symbol}",
            )
        )
    return cases


@pytest.mark.parametrize("drawing,section,symbol,expected_spec", _spec_cases())
def test_ground_truth_spec_is_extracted(
    drawing: str, section, symbol: str, expected_spec: str
) -> None:
    """정답 규격이 (도면[,동],부호)의 추출 규격 집합에 포함되는지.

    동시에 정답 키가 추출 키에 존재함을 확인하므로 도면1 1동·2동 section
    정확성도 함께 검증된다.
    """
    by_key = _spec_set_by_key(drawing)
    key = (drawing, section, symbol)
    assert key in by_key, (
        f"[{drawing}] {section}/{symbol} 추출 실패 — 추출 키 수 {len(by_key)}"
    )
    assert expected_spec in by_key[key], (
        f"[{drawing}] {section}/{symbol}: 정답 {expected_spec!r} 가 추출 집합 "
        f"{sorted(by_key[key])!r} 에 없음"
    )


@pytest.mark.parametrize("drawing", _DRAWINGS)
def test_excluded_prefixes_absent(drawing: str) -> None:
    """추출 결과에 적산 외 부재(P, BR, SBR, MF) 부호가 섞이지 않았는지."""
    for e in _extractions(drawing):
        symbol = e.symbol
        for prefix in DEFAULT_EXCLUDED_PREFIXES:
            offending = symbol == prefix or (
                symbol.startswith(prefix)
                and len(symbol) > len(prefix)
                and symbol[len(prefix)].isdigit()
            )
            assert not offending, (
                f"[{drawing}] 적산 외 부호 {symbol!r} 가 결과에 포함됨"
            )


def test_beam_symbols_preserved() -> None:
    """보 부호(SB·SG)가 전수 보존되는지 — 도면2 의 4종으로 확인."""
    symbols = {e.symbol for e in _extractions("도면2")}
    for beam in ("SB1", "SB2", "SG1", "SG2"):
        assert beam in symbols, f"보 부호 {beam!r} 가 도면2 추출에서 누락됨"


def test_도면4_SC1_preserved_for_both_floors() -> None:
    """dedupe 제거로 도면4 SC1 이 1층·지붕층 2건으로 보존되는지."""
    sc1 = [e for e in _extractions("도면4") if e.symbol == "SC1"]
    assert len(sc1) >= 2, f"도면4 SC1 보존 실패 — {len(sc1)}건"
    sheets = {e.source_sheet for e in sc1}
    assert len(sheets) >= 2, (
        f"도면4 SC1 출처 시트가 구분되지 않음 — {sheets!r}"
    )
