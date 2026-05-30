"""라운드 중량-1b 회귀 테스트 — 5장 통합 기둥 총중량 흐름.

검증 (명세 §4 작업 6)
    1. dedup_loader 확장 스키마 (by_section, skip, count_override)
    2. weight_pipeline skip 분기 (도면1 1동)
    3. weight_pipeline override 분기 (도면2)
    4. 5장 통합 산출 — 행 수·총합
    5. 도면별 소계 (도면1 2동·도면2·도면3·도면5)
    6. 5장 총합 ±5%
    7. CSV 형식 (13열·skip 행·총합 행)
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
    SkipMarker,
    load_dedup,
    skips_for_drawing,
)
from poc_v2.qto.export_weight_csv import (  # noqa: E402
    _HEADER_1B,
    export_all_csv,
    subtotal_by_drawing,
)
from poc_v2.qto.weight_pipeline import (  # noqa: E402
    SkipRow,
    WeightRow,
    compute_weight_for_drawing,
    total_count,
    total_weight_kg,
)

_REL = 0.05  # ±5%


# ── 작업 1: dedup_loader 확장 스키마 ─────────────────────────────────────

def test_load_dedup_by_section_and_skip():
    routes, skips = load_dedup()
    d1 = [r for r in routes if r.drawing == "도면1"]
    assert {r.symbol for r in d1} == {"MC1", "MC2", "MC3", "SC1"}
    assert all(r.section == "2동" for r in d1)
    assert all(r.count_from == "(2동)기둥주심도" for r in d1)
    d1_skips = [s for s in skips if s.drawing == "도면1"]
    assert len(d1_skips) == 1
    assert d1_skips[0].section == "1동"
    assert d1_skips[0].reason


def test_load_dedup_count_override():
    routes, _ = load_dedup()
    d2 = {r.symbol: r for r in routes if r.drawing == "도면2"}
    assert d2["SC1"].count_override == 10
    assert d2["SC2"].count_override == 4
    assert d2["SC1"].count_from is None
    assert d2["SC1"].spec_from == "가,나동 1층 구조평면도"


def test_dedup_both_count_from_and_override_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "도면9:\n  기둥:\n    X1:\n      count_from: \"A\"\n"
        "      count_override: 3\n      spec_from: \"A\"\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="동시"):
        load_dedup(str(bad))


def test_dedup_neither_count_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "도면9:\n  기둥:\n    X1:\n      spec_from: \"A\"\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="count_from"):
        load_dedup(str(bad))


def test_skips_for_drawing():
    assert skips_for_drawing("도면1")
    assert skips_for_drawing("도면4") == []


# ── 작업 2·3: weight_pipeline skip/override 분기 (fake provider) ─────────

def test_skip_branch_emits_skiprow():
    rows = compute_weight_for_drawing(
        "도면1", [],
        skip_markers=[SkipMarker("도면1", "1동", "길이 부재")],
        count_provider=lambda *a: 0,
        length_provider=lambda *a: (6000.0, "s"),
        spec_provider=lambda *a: "H-100x100x6x8",
        unit_weight_fn=lambda s: 20.0,
    )
    assert len(rows) == 1
    assert isinstance(rows[0], SkipRow)
    assert rows[0].section == "1동"


def test_override_branch_skips_count_provider():
    def _boom(*a):
        raise AssertionError("count_provider 가 override 인데 호출됨")

    routes = [DedupRoute("도면2", None, "기둥", "SC1", None, 10, "일람표")]
    rows = compute_weight_for_drawing(
        "도면2", routes,
        count_provider=_boom,
        length_provider=lambda *a: (7700.0, "횡단면도"),
        spec_provider=lambda *a: "H-250x125x6.0x9.0",
        unit_weight_fn=lambda s: 28.59,
    )
    assert len(rows) == 1
    row = rows[0]
    assert isinstance(row, WeightRow)
    assert row.count == 10
    assert row.count_is_override is True
    assert row.count_from_sheet == "(override:10)"
    assert row.note == "count_override"
    # 10 × 7.7 × 28.59 = 2201.4
    assert row.total_weight_kg == pytest.approx(2201.4, rel=_REL)


# ── 작업 3·4·5: 5장 통합 실측 ────────────────────────────────────────────

@pytest.fixture(scope="module")
def all_rows():
    from poc_v2.qto.export_weight_csv import compute_all_rows  # noqa: PLC0415
    return compute_all_rows()


def test_skip_row_present(all_rows):
    skips = [r for r in all_rows if isinstance(r, SkipRow)]
    assert len(skips) == 1
    assert skips[0].drawing == "도면1" and skips[0].section == "1동"


def test_row_count_and_total_columns(all_rows):
    weight_rows = [r for r in all_rows if isinstance(r, WeightRow)]
    # 도면1 2동 4 + 도면2 2 + 도면3 4 + 도면4 2 + 도면5 4 = 16
    assert len(weight_rows) == 16
    # 총 개수 = 25+14+32+18+20 = 109
    assert total_count(all_rows) == 109


def test_도면1_2동_subtotal(all_rows):
    by = {(r.drawing, r.symbol): r for r in all_rows if isinstance(r, WeightRow)}
    assert by[("도면1", "MC1")].count == 15
    assert by[("도면1", "MC1")].length_mm == 6000.0
    assert by[("도면1", "MC1")].spec_normalized == "H-400x200x8x13"
    assert by[("도면1", "MC1")].total_weight_kg == pytest.approx(5790, rel=_REL)
    assert by[("도면1", "MC2")].total_weight_kg == pytest.approx(2870, rel=_REL)


def test_도면2_override_subtotal(all_rows):
    by = {(r.drawing, r.symbol): r for r in all_rows if isinstance(r, WeightRow)}
    assert by[("도면2", "SC1")].count == 10
    assert by[("도면2", "SC1")].spec_normalized == "H-250x125x6.0x9.0"
    assert by[("도면2", "SC1")].total_weight_kg == pytest.approx(2200, rel=_REL)
    assert by[("도면2", "SC2")].total_weight_kg == pytest.approx(630, rel=_REL)


def test_도면3_5_counts_lengths(all_rows):
    by = {(r.drawing, r.symbol): r for r in all_rows if isinstance(r, WeightRow)}
    assert by[("도면3", "C2")].count == 15
    assert by[("도면3", "C2")].length_mm == 19060.0
    assert by[("도면5", "C3")].count == 8
    assert by[("도면5", "C3")].length_mm == 10500.0


def test_도면4_unchanged_from_1a(all_rows):
    """1a 도면4 결과 불변 — SC1 6079.0, SC2 1061.4."""
    by = {(r.drawing, r.symbol): r for r in all_rows if isinstance(r, WeightRow)}
    assert by[("도면4", "SC1")].total_weight_kg == pytest.approx(6079.0, abs=2)
    assert by[("도면4", "SC2")].total_weight_kg == pytest.approx(1061.4, abs=2)


def test_grand_total(all_rows):
    subs = subtotal_by_drawing(all_rows)
    assert set(subs) == {"도면1", "도면2", "도면3", "도면4", "도면5"}
    assert subs["도면4"] == pytest.approx(7140.4, abs=2)
    assert total_weight_kg(all_rows) == pytest.approx(sum(subs.values()), abs=1)
    assert total_weight_kg(all_rows) > 180000  # 도면3 장신 기둥 지배


# ── 작업 7.5: CSV 형식 (13열) ────────────────────────────────────────────

def test_csv_1b_format(all_rows, tmp_path):
    out = tmp_path / "w1b.csv"
    path, rows = export_all_csv(str(out), rows=all_rows)
    with open(path, encoding="utf-8-sig", newline="") as handle:
        records = list(csv.reader(handle))
    assert records[0] == _HEADER_1B
    assert len(records[0]) == 13
    # 헤더 + 17 데이터행(skip 1 + weight 16) + 총합 = 19
    assert len(records) == 1 + 17 + 1
    assert records[-1][0] == "총합"
    skip_lines = [r for r in records if r[3] == "(skip)"]
    assert len(skip_lines) == 1
    assert skip_lines[0][0] == "도면1" and skip_lines[0][1] == "1동"
