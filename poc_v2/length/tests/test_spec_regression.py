"""기둥 규격·단위중량 회귀 테스트 — 라운드 길이-4.

검증 항목
    1) 추출된 (도면, 동, 부호) 키가 정답지와 동일
    2) spec_normalized 가 정답과 일치
    3) yaml 룩업으로 단위중량을 얻을 수 있음
    4) 적산 외 부재(P, BR, SBR, MF) 미혼입
    5) 총중량 보류 건수가 도면1 1동 2건과 일치

별도 회귀 — 1단계(`poc_v2/tests/test_regression.py`) 및 길이-1
(`poc_v2/length/tests/test_length_regression.py`) 은 본 파일에서 영향받지
않는다(이 파일은 자체 신규 모듈만 import).

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
    SpecExtraction,
    extract_specs,
)
from poc_v2.length.total_weight import compute_weights  # noqa: E402
from poc_v2.length.unit_weight import (  # noqa: E402
    load_unit_weight_table,
    lookup_unit_weight,
)


@functools.lru_cache(maxsize=None)
def _extractions(drawing: str) -> dict:
    dxf_path = os.path.join(_PROJECT_ROOT, "sample_data", f"{drawing}.dxf")
    return {
        (e.drawing, e.section, e.symbol): e
        for e in extract_specs(dxf_path, drawing)
    }


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
def test_spec_extraction_matches_ground_truth(
    drawing: str, section, symbol: str, expected_spec: str
) -> None:
    """추출 결과가 정답지 비고의 규격과 일치하는지."""
    extractions = _extractions(drawing)
    key = (drawing, section, symbol)
    assert key in extractions, (
        f"[{drawing}] {section}/{symbol} 부호 추출 실패 — "
        f"추출된 키 수 {len(extractions)}"
    )
    extracted: SpecExtraction = extractions[key]
    assert extracted.spec_normalized == expected_spec, (
        f"[{drawing}] {section}/{symbol}: "
        f"추출 {extracted.spec_normalized!r} vs 정답 {expected_spec!r}"
    )


@pytest.mark.parametrize("drawing,section,symbol,expected_spec", _spec_cases())
def test_unit_weight_lookup_succeeds(
    drawing: str, section, symbol: str, expected_spec: str
) -> None:
    """정답 규격이 yaml 단위중량 테이블에 등록돼 있는지."""
    weight = lookup_unit_weight(expected_spec)
    assert weight is not None and weight > 0, (
        f"[{drawing}] {section}/{symbol}: "
        f"단위중량 룩업 실패 — spec_normalized={expected_spec!r}"
    )


@pytest.mark.parametrize("drawing", ["도면1", "도면2", "도면3", "도면4", "도면5"])
def test_excluded_prefixes_absent(drawing: str) -> None:
    """추출 결과에 적산 외 부재(P, BR, SBR, MF) 부호가 섞이지 않았는지."""
    extractions = _extractions(drawing)
    for key in extractions:
        symbol = key[2]
        for prefix in DEFAULT_EXCLUDED_PREFIXES:
            offending = (
                symbol == prefix
                or (
                    symbol.startswith(prefix)
                    and len(symbol) > len(prefix)
                    and symbol[len(prefix)].isdigit()
                )
            )
            assert not offending, (
                f"[{drawing}] 적산 외 부호 {symbol!r} 가 결과에 포함됨"
            )


@functools.lru_cache(maxsize=1)
def _weight_rows() -> tuple:
    return tuple(compute_weights())


def test_total_weight_deferred_only_for_도면1_1동() -> None:
    """총중량 보류는 도면1 1동 (MC1·MC2) 두 건이어야 한다."""
    rows = _weight_rows()
    deferred = [r for r in rows if r.total_weight_kg is None]
    deferred_keys = {(r.drawing, r.section, r.symbol) for r in deferred}
    assert deferred_keys == {
        ("도면1", "1동", "MC1"),
        ("도면1", "1동", "MC2"),
    }, f"보류 키가 예상과 다름: {deferred_keys}"


def test_total_weight_produced_for_remaining_cases() -> None:
    """도면1 2동·도면2~5 의 모든 (drawing,section,symbol) 에서 총중량 산출."""
    rows = _weight_rows()
    produced = [r for r in rows if r.total_weight_kg is not None]
    assert len(produced) == 16, (
        f"총중량 산출 건수 예상 16, 실제 {len(produced)}"
    )


def test_unit_weight_table_not_empty() -> None:
    assert load_unit_weight_table(), (
        "단위중량 테이블이 비었음 — config/unit_weight_table.yaml 확인"
    )
