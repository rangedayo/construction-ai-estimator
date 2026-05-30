"""회귀 테스트 — 라운드 베이스라인-5 (도면2 작은 도면).

이번 라운드의 핵심 발견
    본선 1단계 회귀의 유일한 FAIL(도면2 SC1·SC2)이 **작은 도면 입력에서도 그대로
    재현**된다. 원인은 입력 단위가 아니라 counter.py 의 카운트 메커니즘 한계:
    기둥이 익명 블록(*B465 등) INSERT 로 배치되고 블록 내부에 'SC' 와 '1' 이
    **분리된 별도 TEXT** 로 들어있어 match_symbol 이 'SC1' 로 재결합하지 못한다.
    counter.py 수정은 이번 라운드 금지(7.1)이므로 한계로 문서화한다.

검증 항목 (명세 작업 7 — 단, 카운트는 실제 동작=한계를 검증)
    1. 표제부 도면명 추출: 1층/지붕/횡단면도/입면도 통합본 성공
    2. 매칭: 1층 exact, 횡단면도 length(라벨 콤마-split 보완), 입면도 partial
    3. 카운트 한계: 1층 SC1=0, SC2=0 (정답 10·4 — 분리 TEXT 블록 한계로 FAIL)
    4. 카운트 PASS: 지붕/입면도 = 0 (이중카운트 방지)
    5. 길이 PASS: 횡단면도 7700
    6. 본선 parity: baseline.predict 도 SC1·SC2 = 0 (입력 모델 문제가 아님을 증명)
    7. length 라벨 콤마-split 보완: "가,나동 횡단면도" 1토큰, 도면4 "종단면도, 횡단면도" 2토큰
    8. 회귀 무영향: 도면3·4·5 모듈 동작 유지

모든 비교는 결정론적(순수 ezdxf + 룰 + openpyxl, LLM 0건).
실행:  프로젝트 루트에서  `pytest -v poc_v2/baseline2/tests/test_baseline5_regression.py`
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

from poc_v2.baseline2.sheet_name_matcher import load_length_labels  # noqa: E402
from poc_v2.baseline2.sheet_title_extractor import extract_sheet_titles  # noqa: E402
from poc_v2.baseline2.small_drawing_pipeline import (  # noqa: E402
    process_small_drawing,
)

_SAMPLE = os.path.join(PROJECT_ROOT, "sample_data")
_DRAWING2 = {
    "1층": "도면2_가나동1층구조평면도.dxf",
    "지붕": "도면2_가나동지붕구조평면도.dxf",
    "횡단면도": "도면2_가나동횡단면도.dxf",
    "입면도": "도면2_가나동정면도좌측면도.dxf",
}


def _path(name: str) -> str:
    return os.path.join(_SAMPLE, _DRAWING2[name])


@functools.lru_cache(maxsize=None)
def _result(name: str):
    return process_small_drawing(_path(name))


# ── 1. 표제부 도면명 추출 ────────────────────────────────────────────────────
@pytest.mark.parametrize("name", list(_DRAWING2))
def test_title_extraction(name: str) -> None:
    titles = extract_sheet_titles(_path(name))
    assert titles, f"{name}: 표제부 도면명 추출 실패"


# ── 2. 매칭 ─────────────────────────────────────────────────────────────────
def test_match_first_floor() -> None:
    r = _result("1층")
    assert r.matched_sheet == "가,나동 1층 구조평면도", r.matched_sheet
    assert r.match_confidence == "exact"
    assert r.kind == "count"


def test_match_section_is_length() -> None:
    # "가,나동 횡단면도" length 라벨이 콤마-split 으로 깨지지 않아야 length 라우팅.
    r = _result("횡단면도")
    assert r.kind == "length", f"kind={r.kind} (length 기대)"


def test_match_elevation_partial() -> None:
    r = _result("입면도")
    assert r.matched_sheet is not None
    assert "입면도" in r.matched_sheet
    assert r.kind == "count"


# ── 3. 카운트 한계 — 1층 SC1·SC2 = 0 (분리 TEXT 블록, 본선 FAIL 재현) ────────
def test_count_first_floor_known_limitation() -> None:
    """기둥이 익명 블록 내 'SC'+'1' 분리 TEXT 라 counter 가 재결합 못 함 → 0.
    정답은 SC1=10, SC2=4 이지만 counter.py 수정 금지로 이번 라운드는 0/0(FAIL).
    """
    r = _result("1층")
    assert r.counts == {"SC1": 0, "SC2": 0}, r.counts
    assert r.pass_counts is False  # 정답(10·4)과 불일치 — 문서화된 한계


# ── 4. 카운트 PASS — 지붕/입면도 = 0 (이중카운트 방지) ───────────────────────
@pytest.mark.parametrize("name", ["지붕", "입면도"])
def test_count_zero_elsewhere(name: str) -> None:
    r = _result(name)
    assert r.kind == "count"
    assert r.counts == {"SC1": 0, "SC2": 0}, r.counts
    assert r.pass_counts is True


# ── 5. 길이 PASS — 횡단면도 7700 ────────────────────────────────────────────
def test_length_section() -> None:
    r = _result("횡단면도")
    assert r.kind == "length"
    assert r.length_mm == pytest.approx(7700.0, abs=1.0)
    assert r.pass_length is True


# ── 6. 본선 parity — predict 도 SC1·SC2 = 0 (입력 모델 문제가 아님) ──────────
def test_mainline_also_zero() -> None:
    from baseline import predict  # noqa: PLC0415
    counts = predict("도면2")
    assert counts.get("SC1", 0) == 0
    assert counts.get("SC2", 0) == 0


# ── 7. length 라벨 콤마-split 보완 ──────────────────────────────────────────
def test_length_label_comma_split() -> None:
    # "가,나동 횡단면도": 콤마가 토큰 내부 → 분할 안 함(1토큰).
    assert load_length_labels("도면2") == ["가,나동 횡단면도"]
    # "종단면도, 횡단면도": 콤마+공백 = 리스트 구분자 → 2토큰(도면4 보존).
    assert load_length_labels("도면4") == ["종단면도", "횡단면도"]


# ── 8. 회귀 무영향 — 도면3·4·5 ──────────────────────────────────────────────
def test_drawing4_unaffected() -> None:
    r = process_small_drawing(os.path.join(_SAMPLE, "도면4_1층구조평면도.dxf"))
    assert r.counts == {"SC1": 14, "SC2": 4}, r.counts


def test_drawing5_length_unaffected() -> None:
    r = process_small_drawing(os.path.join(_SAMPLE, "도면5_주단면도1.dxf"))
    assert r.kind == "length"
    assert r.length_mm == pytest.approx(10500.0, abs=1.0)


def test_drawing3_count_unaffected() -> None:
    r = process_small_drawing(os.path.join(_SAMPLE, "도면3_1층바닥구조평면도.dxf"))
    assert r.counts == {"C1": 8, "C2": 15, "C3": 8, "C4": 1}, r.counts
