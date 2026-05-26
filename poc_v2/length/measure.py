"""DIMENSION 엔티티 기반 기둥 길이 측정 — 라운드 길이-1 핵심 모듈.

알고리즘
    "세로 방향 DIMENSION 엔티티의 measurement 값 중 최댓값" 을 채택.

사전 검증 결과
    9 개 단면도·골구도 모두 정답과 0mm 오차 (도면1~5 기둥).

방향 판별
    DIMENSION.defpoint2 ↔ defpoint3 좌표 차이로 V/H/D 분류.
    |dy| > |dx| × direction_ratio  → 'V' (세로)
    |dx| > |dy| × direction_ratio  → 'H' (가로)
    그 외                           → 'D' (대각)

LLM·랜덤 요소 없는 결정론적 함수.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import ezdxf

_OVERRIDE_PLACEHOLDER = "<>"  # ezdxf 가 override 미설정 시 반환하는 토큰


@dataclass(frozen=True)
class DimensionInfo:
    """DXF 의 한 DIMENSION 엔티티에서 추출된 결정론적 정보."""
    measurement: float
    direction: str  # 'V' | 'H' | 'D'
    p2: tuple[float, float]  # defpoint2 (측정 시작점)
    p3: tuple[float, float]  # defpoint3 (측정 끝점)
    layer: str
    override_text: Optional[str]  # 사람이 강제 입력한 텍스트(있을 경우)
    dim_type: int  # DIMENSION 종류 (linear=0/aligned=1/angular=2/…)


@dataclass
class MeasurementResult:
    """한 DXF 파일에 대한 길이 측정 결과."""
    length_mm: Optional[float]
    method: str
    source_dim: Optional[DimensionInfo]  # 채택된 DIMENSION
    all_vertical_dims: list[DimensionInfo] = field(default_factory=list)
    all_horizontal_dims: list[DimensionInfo] = field(default_factory=list)
    all_diagonal_dims: list[DimensionInfo] = field(default_factory=list)
    confidence: str = "low"  # 'high' | 'medium' | 'low'
    notes: list[str] = field(default_factory=list)


def _classify_direction(
    p2: tuple[float, float],
    p3: tuple[float, float],
    direction_ratio: float,
) -> str:
    """defpoint2/3 좌표 차이로 V/H/D 판별."""
    dx = abs(p3[0] - p2[0])
    dy = abs(p3[1] - p2[1])
    if dy > dx * direction_ratio:
        return "V"
    if dx > dy * direction_ratio:
        return "H"
    return "D"


def _extract_override(entity) -> Optional[str]:
    """DIMENSION 의 override 텍스트가 있으면 반환. `<>` 는 자동값."""
    raw = getattr(entity.dxf, "text", None)
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text == _OVERRIDE_PLACEHOLDER:
        return None
    return text


def _point_xy(point) -> tuple[float, float]:
    """ezdxf Vec3/Vec2 → (x, y) 튜플."""
    return (float(point[0]), float(point[1]))


def extract_dimensions(
    dxf_path: str,
    direction_ratio: float = 5.0,
) -> list[DimensionInfo]:
    """DXF 파일에서 모든 DIMENSION 엔티티 정보를 추출.

    measurement 가 None / 음수 / 비숫자인 엔티티 또는 defpoint2/3 가
    없는 엔티티(angular/radial) 는 제외.
    """
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    dims: list[DimensionInfo] = []
    for entity in msp:
        if entity.dxftype() != "DIMENSION":
            continue
        try:
            measurement = entity.get_measurement()
        except Exception:  # noqa: BLE001 — ezdxf 다양한 예외, 결정론 유지
            continue
        if measurement is None:
            continue
        try:
            value = float(measurement)
        except (TypeError, ValueError):
            continue
        if value < 0:
            continue

        try:
            p2 = _point_xy(entity.dxf.defpoint2)
            p3 = _point_xy(entity.dxf.defpoint3)
        except AttributeError:
            continue

        direction = _classify_direction(p2, p3, direction_ratio)
        layer = getattr(entity.dxf, "layer", "") or ""
        dim_type = int(getattr(entity.dxf, "dimtype", 0)) & 0x0F

        dims.append(DimensionInfo(
            measurement=value,
            direction=direction,
            p2=p2,
            p3=p3,
            layer=layer,
            override_text=_extract_override(entity),
            dim_type=dim_type,
        ))
    return dims


def measure_column_length(
    dxf_path: str,
    method: str = "dimension_max_vertical",
    min_measurement: float = 100.0,
    direction_ratio: float = 5.0,
) -> MeasurementResult:
    """DXF 파일 한 개에서 기둥 길이를 산출.

    method='dimension_max_vertical' (현재 유일 지원)
        세로 방향 DIMENSION 중 measurement 가 가장 큰 값을 채택.
    """
    if method != "dimension_max_vertical":
        raise ValueError(f"지원되지 않는 측정 방법: {method!r}")

    dims = extract_dimensions(dxf_path, direction_ratio=direction_ratio)
    vertical = [
        d for d in dims if d.direction == "V" and d.measurement >= min_measurement
    ]
    horizontal = [
        d for d in dims if d.direction == "H" and d.measurement >= min_measurement
    ]
    diagonal = [d for d in dims if d.direction == "D"]

    notes: list[str] = []

    if not vertical:
        notes.append("세로 DIMENSION 없음 — 측정 불가")
        return MeasurementResult(
            length_mm=None,
            method=method,
            source_dim=None,
            all_vertical_dims=[],
            all_horizontal_dims=horizontal,
            all_diagonal_dims=diagonal,
            confidence="low",
            notes=notes,
        )

    chosen = max(vertical, key=lambda d: d.measurement)

    if horizontal:
        h_max = max(d.measurement for d in horizontal)
        if h_max > chosen.measurement * 1.5:
            notes.append(
                f"세로 최대 {chosen.measurement:.0f}mm < 가로 최대 {h_max:.0f}mm "
                f"— 가로가 더 크지만 세로 채택 (기둥 가정)"
            )

    confidence = "high"
    if len(vertical) >= 2:
        sorted_v = sorted((d.measurement for d in vertical), reverse=True)
        second = sorted_v[1]
        if second > 0:
            ratio = chosen.measurement / second
            if ratio < 1.2:
                confidence = "medium"
                notes.append(
                    f"세로 1위 {chosen.measurement:.0f}mm vs "
                    f"2위 {second:.0f}mm (비율 {ratio:.2f}) — 선택 모호"
                )

    if chosen.override_text:
        notes.append(
            f"채택 DIM 에 override 텍스트 존재: {chosen.override_text!r}"
        )

    return MeasurementResult(
        length_mm=chosen.measurement,
        method=method,
        source_dim=chosen,
        all_vertical_dims=vertical,
        all_horizontal_dims=horizontal,
        all_diagonal_dims=diagonal,
        confidence=confidence,
        notes=notes,
    )
