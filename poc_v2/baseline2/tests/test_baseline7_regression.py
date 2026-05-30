"""라운드 베이스라인-7 회귀 — 분리본 시트 routing 일반화.

검증 대상 (누적 한계 3종 중 분리본 routing)
    1. 도면1 Y03 단독본  : 메커니즘 B(영숫자 열 식별자 suffix 공유 전개) →
                           component/length, 측정 6000 PASS.
    2. 도면3 종단면도 분리본: 메커니즘 A(결합 표제부 split) → component/length,
                           측정 19060 PASS.
    3. 도면5 Y1축열골조도 : length_routing.yaml 미등록으로 격리. count 유지
                           (yaml 무수정 원칙상 이번 라운드 범위 외).

split 룰 단위 검증
    * 메커니즘 A 결합 구분자(", "·"、"·줄바꿈)만 split — 도면2 "가,나동"은 보존.
    * 메커니즘 B 영숫자 열 식별자만 suffix 전개 — 한글 동 라벨은 절대 전개 안 됨.

회귀 무영향 sentinel
    * 도면4 통합본(partial→length)·도면5 주단면도(exact→length) 동작 불변.

모든 비교는 결정론적(순수 ezdxf + 룰 + openpyxl, LLM 0건).
"""
from __future__ import annotations

import functools
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
for _path_entry in (
    PROJECT_ROOT,
    os.path.join(PROJECT_ROOT, "poc_v2"),
):
    if _path_entry not in sys.path:
        sys.path.insert(0, _path_entry)

from poc_v2.baseline2.sheet_name_matcher import (  # noqa: E402
    _expand_id_pair,
    _split_components,
)
from poc_v2.baseline2.small_drawing_pipeline import (  # noqa: E402
    process_small_drawing,
)

_SAMPLE = os.path.join(PROJECT_ROOT, "sample_data")


def _path(name: str) -> str:
    return os.path.join(_SAMPLE, name)


@functools.lru_cache(maxsize=None)
def _result(name: str):
    return process_small_drawing(_path(name))


# ── 1. 메커니즘 B — 도면1 Y03 단독본 component/length 6000 PASS ───────────────
def test_drawing1_y03_standalone_component_length() -> None:
    r = _result("도면1-2동_Y03열골구도.dxf")
    assert r.match_confidence == "component", r.match_confidence
    assert r.kind == "length"
    assert r.matched_sheet == "(2동)Y03,Y05열골구도", r.matched_sheet
    assert r.length_mm == pytest.approx(6000.0, abs=1.0), r.length_mm
    assert r.pass_length is True


# ── 2. 메커니즘 A — 도면3 종단면도 분리본 component/length 19060 PASS ─────────
def test_drawing3_section_split_component_length() -> None:
    r = _result("도면3_종단면도.dxf")
    assert r.match_confidence == "component", r.match_confidence
    assert r.kind == "length"
    assert r.length_mm == pytest.approx(19060.0, abs=1.0), r.length_mm
    assert r.pass_length is True


# ── 3. 도면5 Y1축열골조도 — 격리 (length_routing.yaml 미등록) ────────────────
def test_drawing5_y1_axis_isolated_not_length() -> None:
    """Y1축열은 length_routing.yaml 에 측정 소스가 없어 component 로도 분해할
    length 라벨이 없다. yaml 무수정 원칙상 length 라우팅 불가 — count 유지.
    알려진 한계로 격리(다음 라운드 yaml 등록 후보)."""
    r = _result("도면5_Y1축열골조도.dxf")
    assert r.kind != "length", f"Y1축열이 length 로 라우팅됨: {r.kind}"
    assert r.match_confidence != "component", r.match_confidence


# ── 4. split 룰 단위 — 결합 구분자만 split (도면2 "가,나동" 보존) ─────────────
@pytest.mark.parametrize(
    "text,expected",
    [
        ("종단면도, 계단단면도", ["종단면도", "계단단면도"]),
        ("주단면도1, 주단면도4", ["주단면도1", "주단면도4"]),
        ("종단면도、횡단면도", ["종단면도", "횡단면도"]),
        # 공백 없는 콤마 = 토큰 내부 → split 안 됨 (베이스라인-5 보존).
        ("가,나동 종단면도", ["가,나동 종단면도"]),
        ("종단면도,계단단면도", ["종단면도,계단단면도"]),
        ("단일도면명", ["단일도면명"]),
    ],
)
def test_split_components_rule(text: str, expected: list[str]) -> None:
    assert _split_components(text) == expected


# ── 5. split 룰 단위 — 영숫자 열 식별자만 suffix 전개 (한글 동 라벨 보존) ─────
@pytest.mark.parametrize(
    "label,expected",
    [
        # 영숫자 열 식별자 결합 → suffix 공유 전개.
        ("(2동)Y03,Y05열골구도", ["(2동)Y03열골구도", "(2동)Y05열골구도"]),
        ("X1,X2주단면도", ["X1주단면도", "X2주단면도"]),
        # 한글 동 라벨은 _ID_PAIR 에 매칭 안 됨 → 전개 안 됨.
        ("가,나동 횡단면도", ["가,나동 횡단면도"]),
        # 영숫자 패턴 없으면 원본 유지.
        ("종단면도", ["종단면도"]),
        ("주단면도1", ["주단면도1"]),
    ],
)
def test_expand_id_pair_rule(label: str, expected: list[str]) -> None:
    assert _expand_id_pair(label) == expected


# ── 6. 회귀 무영향 sentinel — 도면4·도면5 통합본 동작 불변 ────────────────────
def test_drawing4_combined_still_length() -> None:
    """도면4 종단면도(통합본)는 partial→length 로 이미 잡힘. component 단계
    미도달 — 동작 불변."""
    r = process_small_drawing(_path("도면4_종단면도.dxf"))
    assert r.kind == "length", r.kind
    assert r.match_confidence in ("exact", "partial"), r.match_confidence


def test_drawing5_main_section_still_length() -> None:
    """도면5 주단면도1 은 exact→length(라벨 직접 일치). 동작 불변."""
    r = process_small_drawing(_path("도면5_주단면도1.dxf"))
    assert r.kind == "length", r.kind
    assert r.match_confidence == "exact", r.match_confidence
    assert r.length_mm == pytest.approx(10500.0, abs=1.0), r.length_mm
