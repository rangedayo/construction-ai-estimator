"""단위중량 통일 함수 — 베이스라인-1.

멘토 원칙: "KS 표 룩업은 미리 계산해둔 결과일 뿐, 원리는 단면적 × 밀도.
표준이든 비표준이든 단면적만 구하면 7,850 kg/㎥ 한 값을 곱해 단위중량."

따라서 본 모듈은 룩업·분기 없이 한 식으로 단위중량을 산출한다.

    A(mm²) = B × tf × 2 + tw × (H − tf × 2)        # H형강 4세그먼트
    W(kg/m) = A(m²) × 7,850

규격 정규화는 기존 `normalize_spec` 을 재사용한다. 이 함수는 본래
`poc_v2/length/ground_truth_spec.py` 에 정의돼 있고 `spec_extractor` 가
re-export 한다 — 여기서는 ezdxf 의존을 끌어오지 않도록(§4.3) 원본 모듈에서
직접 import 한다. 슬래시→x, 공백 제거, H- 접두사 보정 규칙이 모두 들어 있다.

LLM·외부 API 불요. 표준 라이브러리만 사용.
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from poc_v2.length.ground_truth_spec import normalize_spec  # noqa: E402

# 강재 밀도 (kg/㎥). KS D 3502 H형강도 이 한 값으로 환산.
STEEL_DENSITY_KG_PER_M3 = 7850.0

# mm² → m² 환산 계수 (1 m² = 1e6 mm²).
_MM2_PER_M2 = 1_000_000.0

# H형강 단면 세그먼트 수 (H, B, tw, tf).
_H_SECTION_SEGMENTS = 4


def parse_h_section(spec: str) -> tuple[float, float, float, float]:
    """규격 문자열 → (H, B, tw, tf) mm 단위 4튜플.

    내부에서 `normalize_spec()` 으로 정규화한 뒤 'x' 로 분해한다.
    'H-588x300x12/20', 'H 350x175x7/11', '600x407x20x35' 등 변형 모두 처리.

    H형강이 아닌 단면(파이프 □·앵글 L·원형철근 ø 등)은 정규화 후에도
    세그먼트에 비숫자 기호가 남아 float 변환에서 걸러진다.

    Raises
    ------
    ValueError
        4세그먼트 파싱 실패(세그먼트 수 불일치 또는 비숫자), 또는 H형강 외 단면.
    """
    if not spec or not spec.strip():
        raise ValueError("빈 규격 문자열")

    normalized = normalize_spec(spec)
    # normalize_spec 은 항상 'H-' 접두사를 붙인다. 본문만 떼어내 분해.
    if not normalized.startswith("H-"):
        raise ValueError(f"정규화 실패: {spec!r} → {normalized!r}")
    body = normalized[len("H-"):]

    segments = body.split("x")
    if len(segments) != _H_SECTION_SEGMENTS:
        raise ValueError(
            f"H형강 4세그먼트 아님: {spec!r} → {normalized!r} "
            f"({len(segments)}세그먼트). 파이프·앵글·원형철근 등 본 라운드 범위 외."
        )

    try:
        values = tuple(float(seg) for seg in segments)
    except ValueError as exc:
        # □/L/ø 등 비숫자 기호가 세그먼트에 남은 경우 — H형강 외 단면.
        raise ValueError(
            f"H형강 외 단면(비숫자 세그먼트): {spec!r} → {normalized!r}"
        ) from exc

    if any(v <= 0 for v in values):
        raise ValueError(f"치수는 양수여야 함: {spec!r} → {values}")

    H, B, tw, tf = values
    if H - tf * 2 <= 0:
        raise ValueError(
            f"플랜지 두께 합이 춤(H) 이상 — H형강 단면 불성립: {spec!r} → {values}"
        )
    return H, B, tw, tf


def section_area_mm2(H: float, B: float, tw: float, tf: float) -> float:
    """H형강 4세그먼트 단면적(mm²) = B×tf×2 + tw×(H − tf×2).

    위·아래 플랜지 직사각형 2개 + 웹 직사각형 1개. 모서리 곡률(필렛)은
    무시 — KS 표값 대비 +3~4% 작게 나오는 정도로, 멘토 확인상 무시 수준.
    """
    flanges = B * tf * 2.0
    web = tw * (H - tf * 2.0)
    return flanges + web


def unit_weight_kg_per_m(
    spec: str,
    density: float = STEEL_DENSITY_KG_PER_M3,
) -> float:
    """규격 문자열 → 단위중량(kg/m). 내부에서 정규화·파싱·계산."""
    H, B, tw, tf = parse_h_section(spec)
    area_mm2 = section_area_mm2(H, B, tw, tf)
    return area_mm2 / _MM2_PER_M2 * density


def compute_section(spec: str) -> dict:
    """베이스라인 csv 컬럼 채우기용 — H·B·tw·tf·area·weight 한 번에 반환.

    Returns
    -------
    dict
        {
            'spec_normalized': 'H-588x300x12x20',
            'H_mm': 588.0, 'B_mm': 300.0, 'tw_mm': 12.0, 'tf_mm': 20.0,
            'area_mm2': 18576.0,
            'unit_weight_kg_per_m': 145.82,
        }
    """
    H, B, tw, tf = parse_h_section(spec)
    area_mm2 = section_area_mm2(H, B, tw, tf)
    weight = area_mm2 / _MM2_PER_M2 * STEEL_DENSITY_KG_PER_M3
    return {
        "spec_normalized": normalize_spec(spec),
        "H_mm": H,
        "B_mm": B,
        "tw_mm": tw,
        "tf_mm": tf,
        "area_mm2": round(area_mm2, 1),
        "unit_weight_kg_per_m": round(weight, 2),
    }
