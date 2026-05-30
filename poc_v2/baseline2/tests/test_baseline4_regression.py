"""회귀 테스트 — 라운드 베이스라인-4 (도면3 작은 도면).

검증 항목 (명세 작업 8)
    1. 표제부 도면명 추출: 도면3 통합본 6개에서 도면명 추출 성공
    2. 매칭 충돌 회피: 1층바닥 / 중간1층바닥 이 각각 올바른 정답지 시트로 (서로 안 뒤바뀜)
    3. 카운트 PASS: 1층바닥 → C1=8, C2=15, C3=8, C4=1
    4. 카운트 PASS: 나머지 평면도/단면도/입면도 → 기둥 0 (이중카운트 방지)
    5. 길이 PASS: 종단면도계단단면도 → 19060mm (다층 합산, 단일 DIMENSION)
    6. 규격 PASS: C1~C4 4종 (비표준 C1=H-600x407x20x35, C2=H-428x407x20x35 포함)
    7. 입면도-2 fallback 매칭: 배면도우측면도 → 입면도-2 (override yaml)
    8. 본선·도면4·5 무영향: 매칭 보완/override 가 기존 회귀를 깨지 않음
    9. 차감 룰 동작: 1층바닥 일람표 정의행(부호↔규격 페어)만큼 차감 (시나리오 A)

설계 메모
    매칭 충돌(1층바닥 ⊂ 중간1층바닥)은 표제부가 정확한 문자열을 추출 → exact 매칭이
    partial 보다 우선하므로 자동 회피됨(코드 수정 불필요).
    입면도-2 는 표제부가 "(배면도)" 로만 추출돼 어휘가 겹치지 않음 → config/
    sheet_name_overrides.yaml fallback 으로 해결(7.2 허용).

모든 비교는 결정론적(순수 ezdxf + 룰 + openpyxl, LLM 0건).
실행:  프로젝트 루트에서  `pytest -v poc_v2/baseline2/tests/test_baseline4_regression.py`
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
from poc_v2.length.spec_extractor import extract_specs  # noqa: E402

_SAMPLE = os.path.join(PROJECT_ROOT, "sample_data")
# 통합본 6개 (명세 2.1)
_DRAWING3 = {
    "1층바닥": "도면3_1층바닥구조평면도.dxf",
    "중간1층바닥": "도면3_중간1층바닥구조평면도.dxf",
    "2층바닥": "도면3_2층바닥구조평면도.dxf",
    "지붕층": "도면3_지붕층구조평면도.dxf",
    "종단면도계단단면도": "도면3_종단면도계단단면도.dxf",
    "배면도우측면도": "도면3_배면도우측면도.dxf",
}


def _path(name: str) -> str:
    return os.path.join(_SAMPLE, _DRAWING3[name])


@functools.lru_cache(maxsize=None)
def _result(name: str):
    return process_small_drawing(_path(name))


# ── 1. 표제부 도면명 추출 ────────────────────────────────────────────────────
@pytest.mark.parametrize("name", list(_DRAWING3))
def test_title_extraction(name: str) -> None:
    titles = extract_sheet_titles(_path(name))
    assert titles, f"{name}: 표제부 도면명 추출 실패"


# ── 2. 매칭 충돌 회피 — 1층바닥 / 중간1층바닥 ────────────────────────────────
def test_matching_no_collision() -> None:
    first = _result("1층바닥")
    middle = _result("중간1층바닥")
    assert first.matched_sheet == "1층바닥 구조평면도", first.matched_sheet
    assert middle.matched_sheet == "중간1층바닥 구조평면도", middle.matched_sheet
    assert first.match_confidence == "exact"
    assert middle.match_confidence == "exact"
    # 결과가 뒤바뀌지 않았는지: 1층바닥만 비-0, 중간1층바닥은 0
    assert first.counts == {"C1": 8, "C2": 15, "C3": 8, "C4": 1}
    assert middle.counts == {"C1": 0, "C2": 0, "C3": 0, "C4": 0}


# ── 3. 카운트 PASS — 1층바닥 (부호 4종 + 차감 룰) ────────────────────────────
def test_count_first_floor() -> None:
    result = _result("1층바닥")
    assert result.kind == "count"
    assert result.counts == {"C1": 8, "C2": 15, "C3": 8, "C4": 1}, result.counts
    assert result.pass_counts is True


# ── 4. 카운트 PASS — 비-기둥 시트 = 0 (이중카운트 방지) ──────────────────────
@pytest.mark.parametrize(
    "name", ["중간1층바닥", "2층바닥", "지붕층", "배면도우측면도"]
)
def test_count_zero_elsewhere(name: str) -> None:
    result = _result(name)
    assert result.kind == "count"
    assert result.counts == {"C1": 0, "C2": 0, "C3": 0, "C4": 0}, result.counts
    assert result.pass_counts is True


# ── 5. 길이 PASS — 종단면도계단단면도 = 19060 (다층 합산, 단일 DIMENSION) ────
def test_length_section() -> None:
    result = _result("종단면도계단단면도")
    assert result.kind == "length", f"kind={result.kind} (length 기대)"
    assert result.length_mm == pytest.approx(19060.0, abs=1.0)
    assert result.pass_length is True


# ── 6. 규격 PASS — C1~C4 (비표준 포함) ──────────────────────────────────────
def test_spec_first_floor() -> None:
    result = _result("1층바닥")
    assert result.pass_specs is True
    assert result.specs == {
        "C1": "H-600x407x20x35",  # 비표준 (현장제작)
        "C2": "H-428x407x20x35",  # 비표준
        "C3": "H-400x400x13x21",
        "C4": "H-300x300x10x15",
    }, result.specs


# ── 7. 입면도-2 fallback 매칭 — 배면도우측면도 ───────────────────────────────
def test_elevation_fallback() -> None:
    result = _result("배면도우측면도")
    assert result.matched_sheet == "입면도-2", result.matched_sheet
    assert result.match_confidence == "fallback"
    assert result.kind == "count"
    assert result.pass_counts is True


# ── 8. 본선·도면4·5 무영향 ──────────────────────────────────────────────────
def test_drawing4_unaffected() -> None:
    result = process_small_drawing(
        os.path.join(_SAMPLE, "도면4_1층구조평면도.dxf")
    )
    assert result.counts == {"SC1": 14, "SC2": 4}, result.counts


def test_drawing5_unaffected() -> None:
    result = process_small_drawing(
        os.path.join(_SAMPLE, "도면5_주단면도1.dxf")
    )
    assert result.kind == "length"
    assert result.length_mm == pytest.approx(10500.0, abs=1.0)


def test_mainline_spec_unaffected() -> None:
    from poc_v2.length.ground_truth_spec import load_ground_truth_spec  # noqa: PLC0415
    answers = load_ground_truth_spec(drawings=["도면3"])
    by_symbol = {k[2]: v.spec_normalized for k, v in answers.items()}
    assert by_symbol.get("C1") == "H-600x407x20x35"
    assert by_symbol.get("C4") == "H-300x300x10x15"


# ── 9. 차감 룰 동작 — 1층바닥 일람표 정의행만큼 차감 (시나리오 A) ────────────
def test_deduction_rule_applied() -> None:
    pairs = Counter(e.symbol for e in extract_specs(_path("1층바닥"), "도면3"))
    assert pairs == {"C1": 1, "C2": 1, "C3": 1, "C4": 1}, dict(pairs)
    # 최종 = 원시 - 페어. raw [9,16,9,2] → -1 each → [8,15,8,1].
    result = _result("1층바닥")
    assert result.counts == {"C1": 8, "C2": 15, "C3": 8, "C4": 1}
