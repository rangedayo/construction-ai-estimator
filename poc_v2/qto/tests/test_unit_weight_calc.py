"""단위중량 통일 함수 회귀 테스트 — 베이스라인-1.

검증 항목 (§3.2)
    1) 단위 테스트: H-588x300x12x20 한 케이스 수동 검산값과 정확 일치
    2) 정답지 18종 모두 산출: unit_weight_kg_per_m() 이 ValueError 없이 양수 반환
    3) KS표 sanity check: config/unit_weight_table.yaml 을 **참조 전용**으로 읽어
       계산값과의 상대오차(%)를 표로 출력 — **경고만**(assert 없음). yaml 임시값이
       실제 KS 와 다른 항목이 있어(예: 428x407·450x200) hard-fail 하지 않고
       ±5% 초과 행을 콘솔에 강조 표시만 한다.
    4) 비표준 단면 산출: H-600x407x20x35(현장제작) 등 KS표 외 단면도 양수 반환
    5) 엣지 케이스: 파이프·앵글·원형철근·세그먼트 수 불일치 → ValueError

본선 회귀(1단계·길이-1·규격-1)와 완전히 독립. 표준 라이브러리 + pytest + PyYAML.

실행
    pytest -v -s poc_v2/qto/tests/test_unit_weight_calc.py
"""
from __future__ import annotations

import os
import sys

import pytest
import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from poc_v2.length.ground_truth_spec import normalize_spec  # noqa: E402
from poc_v2.qto.unit_weight_calc import (  # noqa: E402
    STEEL_DENSITY_KG_PER_M3,
    compute_section,
    parse_h_section,
    section_area_mm2,
    unit_weight_kg_per_m,
)

_KS_TABLE_PATH = os.path.join(_PROJECT_ROOT, "config", "unit_weight_table.yaml")

# ±5% sanity check 임계값.
_KS_TOLERANCE_PCT = 5.0

# 정답지 18종 (도면, 동, 부호, 규격원문) — round_length4_보고서.md §2 표와 동일.
# 규격원문은 슬래시/공백/H-무접두 변형을 그대로 살려 normalize 경로를 검증한다.
# (도면3·5 일부는 동일 단면을 공유 → 정규화 후 중복.)
_SECTIONS_18: tuple[tuple[str, str, str, str], ...] = (
    ("도면1", "1동", "MC1", "H-588x300x12/20"),
    ("도면1", "1동", "MC2", "H-200x200x8/12"),
    ("도면1", "2동", "MC1", "H-400x200x8/13"),
    ("도면1", "2동", "MC2", "H-440x300x11/18"),
    ("도면1", "2동", "MC3", "H-250x250x9x14"),
    ("도면1", "2동", "SC1", "H-300x150x6.5/9"),
    ("도면2", "—", "SC1", "H-250x125x6.0x9.0"),
    ("도면2", "—", "SC2", "H-200x100x5.5x8.0"),
    ("도면3", "—", "C1", "600x407x20x35"),  # 현장제작 — 비표준
    ("도면3", "—", "C2", "428x407x20x35"),
    ("도면3", "—", "C3", "H-400x400x13x21"),
    ("도면3", "—", "C4", "H-300x300x10x15"),
    ("도면4", "—", "SC1", "H 350x175x7/11"),  # 공백 변형
    ("도면4", "—", "SC2", "H-194x150x6/9"),
    ("도면5", "—", "C1", "H-300x300x10x15"),  # = 도면3 C4
    ("도면5", "—", "C2", "H-250x250x9x14"),  # = 도면1 MC3
    ("도면5", "—", "C3", "H-450x200x9x14"),
    ("도면5", "—", "C4", "H-200x200x8x12"),  # = 도면1 MC2 (두께 표기만 다름)
)

# KS표 비교에서 표준 단면이 아니어서 ±5% 비교 대상으로 보지 않는 단면.
_NONSTANDARD_NORMALIZED = {"H-600x407x20x35"}


def _load_ks_table() -> dict[str, float]:
    """config/unit_weight_table.yaml 을 참조 전용으로 읽어 normalize 키로 매핑.

    yaml 키는 슬래시·x 표기가 섞여 있어(예: 'H-588x300x12/20') normalize_spec 으로
    통일한 뒤 매칭한다. 임시값(멘토 확인 필요)이므로 비교/출력용으로만 쓴다.
    """
    with open(_KS_TABLE_PATH, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    table = raw.get("H형강", {}) if isinstance(raw, dict) else {}
    return {normalize_spec(k): float(v) for k, v in table.items()}


# --- 1) 단위 테스트 ---------------------------------------------------------

def test_unit_case_588_manual_calc():
    """H-588x300x12x20 — 수동 검산: A=18,576 mm², W=145.82 kg/m."""
    H, B, tw, tf = parse_h_section("H-588x300x12/20")
    assert (H, B, tw, tf) == (588.0, 300.0, 12.0, 20.0)

    area = section_area_mm2(H, B, tw, tf)
    assert area == pytest.approx(18576.0, abs=0.01)

    weight = unit_weight_kg_per_m("H-588x300x12/20")
    assert weight == pytest.approx(145.82, abs=0.01)


def test_compute_section_dict():
    """compute_section 반환 dict 의 키·값 검증."""
    result = compute_section("H-588x300x12/20")
    assert result["spec_normalized"] == "H-588x300x12x20"
    assert result["H_mm"] == 588.0
    assert result["B_mm"] == 300.0
    assert result["tw_mm"] == 12.0
    assert result["tf_mm"] == 20.0
    assert result["area_mm2"] == pytest.approx(18576.0, abs=0.1)
    assert result["unit_weight_kg_per_m"] == pytest.approx(145.82, abs=0.01)


def test_density_constant():
    assert STEEL_DENSITY_KG_PER_M3 == 7850.0


# --- 2) 정답지 18종 모두 산출 ------------------------------------------------

@pytest.mark.parametrize(
    "drawing,section,symbol,spec",
    _SECTIONS_18,
    ids=[f"{d}-{s}-{sym}" for d, s, sym, _ in _SECTIONS_18],
)
def test_all_18_sections_positive(drawing, section, symbol, spec):
    """18종 모두 ValueError 없이 양수 단위중량 반환."""
    weight = unit_weight_kg_per_m(spec)
    assert weight > 0, f"{drawing} {section} {symbol} {spec} → {weight}"


# --- 4) 비표준 단면 산출 -----------------------------------------------------

def test_nonstandard_section_computes():
    """KS표 외 단면(현장제작)도 같은 식으로 양수 산출.

    A = 407*35*2 + 20*(600-70) = 28,490 + 10,600 = 39,090 mm²
    """
    expected = 39090.0 / 1_000_000.0 * 7850.0
    weight = unit_weight_kg_per_m("H-600x407x20x35")
    assert weight == pytest.approx(expected, abs=0.01)
    assert weight > 0


# --- 5) 엣지 케이스 ----------------------------------------------------------

@pytest.mark.parametrize(
    "spec",
    [
        "□-100x100x2.3",  # 파이프
        "L-50x6",          # 앵글
        "ø16",             # 원형 철근
        "H-300x150x6.5",   # 3세그먼트
        "H-1x2x3x4x5",     # 5세그먼트
        "",                # 빈 문자열
    ],
)
def test_non_h_section_raises(spec):
    """H형강 외 단면·세그먼트 수 불일치 → ValueError."""
    with pytest.raises(ValueError):
        unit_weight_kg_per_m(spec)


# --- 3) KS표 sanity check (경고만, assert 없음) ------------------------------

def test_ks_table_sanity_check_report():
    """18종 계산값 vs KS표(임시값) 비교표 출력. ±5% 초과는 강조만, 실패 없음."""
    ks_table = _load_ks_table()

    # 18종 → 정규화 키로 dedupe (도면3·5 공유 단면 중복 제거).
    seen: dict[str, str] = {}
    for _, _, _, spec in _SECTIONS_18:
        seen.setdefault(normalize_spec(spec), spec)

    rows = []
    over_tolerance = []
    for normalized, raw in seen.items():
        info = compute_section(raw)
        calc_w = info["unit_weight_kg_per_m"]
        ks_w = ks_table.get(normalized)
        is_nonstandard = normalized in _NONSTANDARD_NORMALIZED

        if ks_w is None:
            diff_pct = None
        else:
            diff_pct = (calc_w - ks_w) / ks_w * 100.0
            if abs(diff_pct) > _KS_TOLERANCE_PCT and not is_nonstandard:
                over_tolerance.append((normalized, calc_w, ks_w, diff_pct))

        rows.append(
            (normalized, info["area_mm2"], calc_w, ks_w, diff_pct, is_nonstandard)
        )

    # 콘솔 출력 (pytest -s). Windows cp949 콘솔 호환을 위해 기호는 ASCII 로.
    lines = [
        "",
        "=== 단위중량 18종(정규화 dedupe) - 계산 vs KS표(임시값) ===",
        f"{'규격':28}{'계산 A(mm2)':>14}{'계산 W':>10}{'KS표':>9}{'차이%':>9}",
    ]
    for normalized, area, calc_w, ks_w, diff_pct, nonstd in rows:
        ks_str = f"{ks_w:.1f}" if ks_w is not None else "-"
        diff_str = f"{diff_pct:+.1f}" if diff_pct is not None else "-"
        flag = ""
        if nonstd:
            flag = "  (비표준-제외)"
        elif diff_pct is not None and abs(diff_pct) > _KS_TOLERANCE_PCT:
            flag = "  <<< +/-5% 초과 (yaml 임시값 오기 의심)"
        lines.append(
            f"{normalized:28}{area:>14,.0f}{calc_w:>10.1f}{ks_str:>9}{diff_str:>9}{flag}"
        )
    lines.append("")
    if over_tolerance:
        lines.append(
            f"[!] +/-5% 초과 {len(over_tolerance)}건 - 계산식이 아니라 KS표 임시값이 "
            "틀린 항목임(멘토 확인 후 yaml 교체 예정). 본 테스트는 경고만 한다."
        )
    else:
        lines.append("[OK] 표준 단면 전 항목 +/-5% 이내.")
    print("\n".join(lines))

    # 경고만 — 항상 통과. (사용자 결정: KS 비교는 hard-fail 하지 않음)
    assert True
