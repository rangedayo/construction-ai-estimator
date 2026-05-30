"""회귀 테스트 — 라운드 베이스라인-3 (도면5 작은 도면 9개).

검증 항목 (명세 작업 8)
    1. 표제부 도면명 추출: 도면5 9개에서 도면명 추출 성공
    2. 시트명 매칭: 9개 모두 exact (unmatched 없음)
    3. 카운트 PASS: 1층바닥 구조평면도 → C1=2, C2=4, C3=8, C4=6
    4. 카운트 PASS: 나머지 평면도/단면도/입면도 → 기둥 0 (이중카운트 방지)
    5. 길이 PASS: 주단면도1·주단면도4 → 10500mm
    6. 길이 None: 정면도우측면도 (DIMENSION 0개 안전 처리)
    7. 규격 PASS: C1~C4 4종 정답지 일치
    8. 본선·도면4 무영향: 매칭 우선순위 보완이 도면4 카운트를 깨지 않음
    9. 차감 룰 동작: 1층바닥 일람표 정의행(부호↔규격 페어)만큼 차감

설계 메모
    매칭 우선순위 보완(sheet_name_matcher): 카운트 행이 placeholder(빈 dict)이고
    동시에 length 라벨이면 length 우선. → 주단면도1·4 가 length 로 라우팅돼 측정됨.
    실제 카운트 대상(비어있지 않은 행)은 항상 count 유지 → 도면4 무영향.

모든 비교는 결정론적(순수 ezdxf + 룰 + openpyxl, LLM 0건).
실행:  프로젝트 루트에서  `pytest -v poc_v2/baseline2/tests/test_baseline3_regression.py`
"""
from __future__ import annotations

import functools
import os
import sys
from collections import Counter

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
from poc_v2.length.measure import measure_column_length  # noqa: E402
from poc_v2.length.spec_extractor import extract_specs  # noqa: E402

_SAMPLE = os.path.join(PROJECT_ROOT, "sample_data")
_DRAWING5 = {
    "1층": "도면5_1층바닥구조평면도.dxf",
    "2층": "도면5_2층바닥구조평면도.dxf",
    "지붕층": "도면5_지붕층바닥구조평면도.dxf",
    "주단면도1": "도면5_주단면도1.dxf",
    "주단면도4": "도면5_주단면도4.dxf",
    "Y1축열골조도": "도면5_Y1축열골조도.dxf",
    "정면도우측면도": "도면5_정면도우측면도.dxf",
    "정면도": "도면5_정면도.dxf",
    "우측면도": "도면5_우측면도.dxf",
}


def _path(name: str) -> str:
    return os.path.join(_SAMPLE, _DRAWING5[name])


@functools.lru_cache(maxsize=None)
def _result(name: str):
    return process_small_drawing(_path(name))


# ── 1. 표제부 도면명 추출 ────────────────────────────────────────────────────
@pytest.mark.parametrize("name", list(_DRAWING5))
def test_title_extraction(name: str) -> None:
    titles = extract_sheet_titles(_path(name))
    assert titles, f"{name}: 표제부 도면명 추출 실패"


# ── 2. 시트명 매칭 (9/9 exact, unmatched 없음) ───────────────────────────────
@pytest.mark.parametrize("name", list(_DRAWING5))
def test_sheet_matching(name: str) -> None:
    result = _result(name)
    assert result.match_confidence == "exact", (
        f"{name}: 매칭 신뢰도 {result.match_confidence} (exact 기대)"
    )
    assert result.matched_sheet is not None


# ── 3. 카운트 PASS — 1층바닥 (부호 4종 + 차감 룰) ────────────────────────────
def test_count_first_floor() -> None:
    result = _result("1층")
    assert result.kind == "count"
    assert result.counts == {"C1": 2, "C2": 4, "C3": 8, "C4": 6}, result.counts
    assert result.pass_counts is True


# ── 4. 카운트 PASS — 비-기둥 시트 6개 = 0 (이중카운트 방지) ──────────────────
@pytest.mark.parametrize(
    "name", ["2층", "지붕층", "Y1축열골조도", "정면도우측면도", "정면도", "우측면도"]
)
def test_count_zero_elsewhere(name: str) -> None:
    result = _result(name)
    assert result.kind == "count"
    assert result.counts == {"C1": 0, "C2": 0, "C3": 0, "C4": 0}, result.counts
    assert result.pass_counts is True


# ── 5. 길이 PASS — 주단면도1·4 = 10500 ──────────────────────────────────────
@pytest.mark.parametrize("name", ["주단면도1", "주단면도4"])
def test_length_section(name: str) -> None:
    result = _result(name)
    assert result.kind == "length", f"{name}: kind={result.kind} (length 기대)"
    assert result.length_mm == pytest.approx(10500.0, abs=1.0)
    assert result.pass_length is True


# ── 6. 길이 None — 정면도우측면도 (DIMENSION 0개 안전 처리) ──────────────────
def test_dimension_zero_safe() -> None:
    # 입면도1 은 카운트 시트(0-행)로 라우팅되므로 pipeline 은 length 미측정.
    result = _result("정면도우측면도")
    assert result.length_mm is None
    # 측정 함수 자체도 DIMENSION 0개에서 에러 없이 None 반환해야 한다.
    measurement = measure_column_length(_path("정면도우측면도"))
    assert measurement.length_mm is None


# ── 7. 규격 PASS — C1~C4 ────────────────────────────────────────────────────
def test_spec_first_floor() -> None:
    result = _result("1층")
    assert result.pass_specs is True
    assert result.specs == {
        "C1": "H-300x300x10x15",
        "C2": "H-250x250x9x14",
        "C3": "H-450x200x9x14",
        "C4": "H-200x200x8x12",
    }, result.specs


# ── 8. 본선·도면4 무영향 — 매칭 우선순위 보완이 도면4 를 깨지 않음 ──────────
def test_drawing4_count_unaffected() -> None:
    result = process_small_drawing(
        os.path.join(_SAMPLE, "도면4_1층구조평면도.dxf")
    )
    assert result.kind == "count"
    assert result.counts == {"SC1": 14, "SC2": 4}, result.counts
    assert result.pass_counts is True


def test_drawing4_length_unaffected() -> None:
    result = process_small_drawing(
        os.path.join(_SAMPLE, "도면4_종단면도.dxf")
    )
    assert result.kind == "length"
    assert result.length_mm == pytest.approx(9000.0, abs=1.0)


def test_mainline_spec_unaffected() -> None:
    from poc_v2.length.ground_truth_spec import load_ground_truth_spec  # noqa: PLC0415
    answers = load_ground_truth_spec(drawings=["도면5"])
    by_symbol = {k[2]: v.spec_normalized for k, v in answers.items()}
    assert by_symbol.get("C1") == "H-300x300x10x15"
    assert by_symbol.get("C4") == "H-200x200x8x12"


# ── 9. 차감 룰 동작 — 1층바닥 일람표 정의행만큼 차감 ─────────────────────────
def test_deduction_rule_applied() -> None:
    # spec_extractor 가 잡는 부호↔규격 페어 = 일람표 정의행.
    pairs = Counter(e.symbol for e in extract_specs(_path("1층"), "도면5"))
    assert pairs == {"C1": 1, "C2": 1, "C3": 1, "C4": 1}, dict(pairs)
    # 최종 카운트 = 원시 - 페어. 페어가 1씩이므로 원시는 답+1(3,5,9,7)이었다.
    result = _result("1층")
    assert result.counts == {"C1": 2, "C2": 4, "C3": 8, "C4": 6}
