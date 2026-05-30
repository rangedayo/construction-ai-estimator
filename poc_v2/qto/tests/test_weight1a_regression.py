"""라운드 중량-1a 회귀 테스트 — 도면4 기둥 총중량 흐름.

검증 (명세 §4 작업 6)
    1. dedup_loader 정상 동작 + 검증 (빈 시트·중복 에러)
    2. weight_pipeline 순수 함수 (fake provider 로 결정론 확인)
    3. 도면4 실측 산출 (SC1·SC2 + 합계)
    4. 단위중량·총중량 ±5% 허용오차
    5. CSV 형식 (헤더·행 수·합계 행 위치)
"""
from __future__ import annotations

import csv
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from poc_v2.qto.dedup_loader import (  # noqa: E402
    DedupRoute,
    load_dedup_routing,
    routes_for_drawing,
)
from poc_v2.qto.export_weight_csv import _HEADER, export_csv  # noqa: E402
from poc_v2.qto.weight_pipeline import (  # noqa: E402
    compute_weight_for_drawing,
    total_count,
    total_weight_kg,
)

_REL_TOL = 0.05  # ±5% — baseline-1 단면적 식 vs KS 표 차이 흡수


# ── 작업 1: dedup_loader ─────────────────────────────────────────────────

def test_load_dedup_routing_도면4_two_routes():
    routes = routes_for_drawing("도면4")
    assert len(routes) == 2
    by_symbol = {r.symbol: r for r in routes}
    assert set(by_symbol) == {"SC1", "SC2"}
    for route in routes:
        assert route.member_kind == "기둥"
        assert route.count_from == "1층 구조평면도"
        assert route.spec_from == "1층 구조평면도"


def test_load_dedup_routing_ignores_memo_blocks():
    """실제 yaml 의 주석/메모는 무시하고 기둥 라우팅만 로드."""
    routes = load_dedup_routing()
    assert all(isinstance(r, DedupRoute) for r in routes)
    assert {(r.drawing, r.symbol) for r in routes} == {("도면4", "SC1"), ("도면4", "SC2")}


def test_dedup_empty_sheet_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "도면9:\n  기둥:\n    X1:\n      count_from: \"\"\n      spec_from: \"S\"\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="count_from"):
        load_dedup_routing(str(bad))


def test_dedup_duplicate_symbol_raises(tmp_path):
    dup = tmp_path / "dup.yaml"
    dup.write_text(
        "도면9:\n"
        "  기둥:\n    X1:\n      count_from: \"A\"\n      spec_from: \"A\"\n"
        "  보:\n    X1:\n      count_from: \"B\"\n      spec_from: \"B\"\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="중복"):
        load_dedup_routing(str(dup))


# ── 작업 2: weight_pipeline 순수 함수 (fake provider) ────────────────────

def test_compute_weight_pure_with_fakes():
    routes = [
        DedupRoute("도면X", "기둥", "A1", "본체시트", "일람표시트"),
    ]
    rows = compute_weight_for_drawing(
        "도면X", routes,
        count_provider=lambda d, s, sym: 10,
        length_provider=lambda d, sym: (6000.0, "단면도"),
        spec_provider=lambda d, s, sym: "H-100x100x6x8",
        unit_weight_fn=lambda spec: 20.0,
    )
    assert len(rows) == 1
    row = rows[0]
    # 10 × 6.0m × 20.0 = 1200.0
    assert row.total_weight_kg == pytest.approx(1200.0)
    assert row.count == 10
    assert row.length_mm == 6000.0
    assert row.count_from_sheet == "본체시트"
    assert row.spec_from_sheet == "일람표시트"
    assert row.length_from_sheet == "단면도"


def test_compute_weight_missing_length_raises():
    routes = [DedupRoute("도면X", "기둥", "A1", "s", "s")]
    with pytest.raises(ValueError, match="길이"):
        compute_weight_for_drawing(
            "도면X", routes,
            count_provider=lambda d, s, sym: 1,
            length_provider=lambda d, sym: (None, ""),
            spec_provider=lambda d, s, sym: "H-100x100x6x8",
            unit_weight_fn=lambda spec: 20.0,
        )


# ── 작업 3·4: 도면4 실측 산출 + ±5% 검증 ─────────────────────────────────

@pytest.fixture(scope="module")
def 도면4_rows():
    from poc_v2.qto.export_weight_csv import compute_rows  # noqa: PLC0415
    return compute_rows("도면4")


def test_도면4_counts_exact(도면4_rows):
    by = {r.symbol: r for r in 도면4_rows}
    assert by["SC1"].count == 14
    assert by["SC2"].count == 4


def test_도면4_length_exact(도면4_rows):
    by = {r.symbol: r for r in 도면4_rows}
    assert by["SC1"].length_mm == pytest.approx(9000.0, abs=50)
    assert by["SC2"].length_mm == pytest.approx(9000.0, abs=50)


def test_도면4_spec_normalized(도면4_rows):
    by = {r.symbol: r for r in 도면4_rows}
    assert by["SC1"].spec_normalized == "H-350x175x7x11"
    assert by["SC2"].spec_normalized == "H-194x150x6x9"


def test_도면4_unit_weight_range(도면4_rows):
    by = {r.symbol: r for r in 도면4_rows}
    # SC1 단면적 6146mm² → ~48.2 kg/m, SC2 3756mm² → ~29.5 kg/m
    assert by["SC1"].unit_weight_kg_per_m == pytest.approx(48.25, rel=_REL_TOL)
    assert by["SC2"].unit_weight_kg_per_m == pytest.approx(29.48, rel=_REL_TOL)


def test_도면4_total_weight_within_5pct(도면4_rows):
    by = {r.symbol: r for r in 도면4_rows}
    # 계산식 기준 결정론 값
    assert by["SC1"].total_weight_kg == pytest.approx(6079.0, rel=_REL_TOL)
    assert by["SC2"].total_weight_kg == pytest.approx(1061.4, rel=_REL_TOL)
    # KS 표 참고값(필렛 반영) 대비 ±5%
    assert by["SC1"].total_weight_kg == pytest.approx(6250.0, rel=_REL_TOL)
    assert by["SC2"].total_weight_kg == pytest.approx(1100.0, rel=_REL_TOL)


def test_도면4_sum(도면4_rows):
    assert total_count(도면4_rows) == 18
    assert total_weight_kg(도면4_rows) == pytest.approx(7350.0, rel=_REL_TOL)


# ── 작업 6.5: CSV 형식 ───────────────────────────────────────────────────

def test_csv_format(도면4_rows, tmp_path):
    out = tmp_path / "weight.csv"
    path, rows = export_csv("도면4", str(out), rows=도면4_rows)
    assert os.path.exists(path)
    with open(path, encoding="utf-8-sig", newline="") as handle:
        records = list(csv.reader(handle))
    # 헤더 + 2 부호 행 + 합계 행 = 4
    assert records[0] == _HEADER
    assert len(records) == 4
    assert records[-1][2] == "합계"
    assert records[-1][0] == "도면4"
    # 합계 개수 = 18
    assert records[-1][3] == "18"
