"""회귀 테스트 — 라운드 베이스라인-2 (도면4 작은 도면 5개).

검증 항목 (명세 작업 6)
    1. 표제부 도면명 추출: 도면4 5개에서 도면명 추출 성공
    2. 시트명 매칭: 5개 모두 exact 또는 partial (unmatched 없음)
    3. 카운트 PASS: 1층 구조평면도 → SC1=14, SC2=4
    4. 카운트 PASS: 지붕층 구조평면도 → SC1=0, SC2=0 (이중카운트 방지)
    5. 길이 PASS: 종단면도횡단면도 → 9000mm
    6. 규격 PASS: SC1=H-350x175x7x11, SC2=H-194x150x6x9
    7~9. 본선 무영향: 카운트·길이·규격 본선 predict 의 도면4 값이 그대로
        (전체 회귀 3종 PASS 수 유지는 `pytest poc_v2/...` 별도 실행으로 확인)

모든 비교는 결정론적(순수 ezdxf + 룰 + openpyxl, LLM 0건).
실행:  프로젝트 루트에서  `pytest -v poc_v2/baseline2/tests`
"""
from __future__ import annotations

import functools
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
for _path in (
    PROJECT_ROOT,
    os.path.join(PROJECT_ROOT, "poc_v2"),
    os.path.join(PROJECT_ROOT, "poc_v2", "tests"),
):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from poc_v2.baseline2.sheet_title_extractor import extract_sheet_titles  # noqa: E402
from poc_v2.baseline2.small_drawing_pipeline import (  # noqa: E402
    process_small_drawing,
)

_SAMPLE = os.path.join(PROJECT_ROOT, "sample_data")
_DRAWING4 = {
    "1층": "도면4_1층구조평면도.dxf",
    "지붕층": "도면4_지붕층구조평면도.dxf",
    "종단면도횡단면도": "도면4_종단면도횡단면도.dxf",
    "종단면도": "도면4_종단면도.dxf",
    "횡단면도": "도면4_횡단면도.dxf",
}


def _path(name: str) -> str:
    return os.path.join(_SAMPLE, _DRAWING4[name])


@functools.lru_cache(maxsize=None)
def _result(name: str):
    return process_small_drawing(_path(name))


# ── 1. 표제부 도면명 추출 ────────────────────────────────────────────────────
@pytest.mark.parametrize("name", list(_DRAWING4))
def test_title_extraction(name: str) -> None:
    titles = extract_sheet_titles(_path(name))
    assert titles, f"{name}: 표제부 도면명 추출 실패"


# ── 2. 시트명 매칭 (exact 또는 partial) ──────────────────────────────────────
@pytest.mark.parametrize("name", list(_DRAWING4))
def test_sheet_matching(name: str) -> None:
    result = _result(name)
    assert result.match_confidence in ("exact", "partial"), (
        f"{name}: 매칭 실패 ({result.match_confidence})"
    )
    assert result.matched_sheet is not None


# ── 3. 카운트 PASS — 1층 구조평면도 ──────────────────────────────────────────
def test_count_first_floor() -> None:
    result = _result("1층")
    assert result.counts == {"SC1": 14, "SC2": 4}, result.counts
    assert result.pass_counts is True


# ── 4. 카운트 PASS — 지붕층 구조평면도 (이중카운트 방지) ─────────────────────
def test_count_roof_zero() -> None:
    result = _result("지붕층")
    assert result.counts == {"SC1": 0, "SC2": 0}, result.counts
    assert result.pass_counts is True


# ── 5. 길이 PASS — 종단면도횡단면도 (+ cross-check 분리본) ───────────────────
def test_length_section() -> None:
    result = _result("종단면도횡단면도")
    assert result.kind == "length"
    assert result.pass_length is True
    assert result.length_mm == pytest.approx(9000.0, abs=1.0)


@pytest.mark.parametrize("name", ["종단면도", "횡단면도"])
def test_length_cross_check(name: str) -> None:
    result = _result(name)
    assert result.length_mm == pytest.approx(9000.0, abs=1.0)


# ── 6. 규격 PASS — SC1·SC2 ──────────────────────────────────────────────────
def test_spec_first_floor() -> None:
    result = _result("1층")
    assert result.pass_specs is True
    assert result.specs == {
        "SC1": "H-350x175x7x11",
        "SC2": "H-194x150x6x9",
    }, result.specs


# ── 7~9. 본선 무영향 — 공유 모듈 predict 의 도면4 값 불변 ─────────────────────
def test_mainline_count_unaffected() -> None:
    from baseline import predict as count_predict  # noqa: PLC0415
    counts = count_predict("도면4")
    assert counts.get("SC1") == 14
    assert counts.get("SC2") == 4


def test_mainline_length_unaffected() -> None:
    from poc_v2.length.baseline_length import predict as len_predict  # noqa: PLC0415
    lengths = len_predict("도면4")
    assert lengths.get("SC1") == pytest.approx(9000.0, abs=1.0)
    assert lengths.get("SC2") == pytest.approx(9000.0, abs=1.0)


def test_mainline_spec_unaffected() -> None:
    from poc_v2.length.ground_truth_spec import load_ground_truth_spec  # noqa: PLC0415
    answers = load_ground_truth_spec(drawings=["도면4"])
    by_symbol = {k[2]: v.spec_normalized for k, v in answers.items()}
    assert by_symbol.get("SC1") == "H-350x175x7x11"
    assert by_symbol.get("SC2") == "H-194x150x6x9"
