"""기둥 총중량 곱셈 파이프라인 — 라운드 중량-1a/1b.

곱셈 = 개수 × 길이 × 단위중량. 측정 3종(카운트·길이·규격) 은 baseline-1~7
에서 이미 PASS 했고, 본 모듈은 그 측정 결과를 **소비** 만 한다 (측정 모듈
회귀에 영향 0).

1b 확장
    * `skip_markers`: 산출 제외 섹션(도면1 1동) → SkipRow 1개.
    * `count_override`: 측정 카운트 한계(도면2) → 정답값 사용, count_provider 미호출.
    * `section`: 동·구역(도면1 2동) 을 행에 보존.
    * spec_provider 는 count>0 게이트 없이 spec_from 시트에서 직접 규격 추출
      (count_override 부호도 규격을 얻을 수 있게).

설계
    `compute_weight_for_drawing` 는 순수 함수 — provider 4종을 인자로 받아
    dedup_routing.yaml 이 지시한 시트에서만 값을 취해 곱한다. 측정 모듈
    의존(ezdxf 등) 은 `build_default_providers` 의 지연 import 안에만 둔다.

결정론
    LLM·랜덤 0건. 동일 입력 → 동일 출력. 총중량은 명시적 반올림만 적용.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Union

from poc_v2.qto.dedup_loader import DedupRoute, SkipMarker

# provider 시그니처 (얇은 어댑터로 구현)
CountProvider = Callable[[str, str, str], int]            # (도면, 시트, 부호) → 개수
LengthProvider = Callable[[str, str], tuple[Optional[float], str]]  # (도면, 부호) → (mm, 소스시트)
SpecProvider = Callable[[str, str, str], str]             # (도면, 시트, 부호) → 정규화 규격
UnitWeightFn = Callable[[str], float]                     # 정규화 규격 → kg/m

_MM_PER_M = 1000.0


@dataclass(frozen=True)
class WeightRow:
    """도면 한 장의 부호별 총중량 산출 행."""
    drawing: str
    member_kind: str
    symbol: str
    count: int
    length_mm: float
    spec_normalized: str
    unit_weight_kg_per_m: float
    total_weight_kg: float
    count_from_sheet: str
    spec_from_sheet: str
    length_from_sheet: str
    # 1b 확장 필드 (기본값 — 1a 호출부 무영향)
    section: Optional[str] = None
    count_is_override: bool = False
    note: str = ""


@dataclass(frozen=True)
class SkipRow:
    """산출 대상에서 제외된 (도면, 섹션) 표시 행."""
    drawing: str
    member_kind: str
    section: Optional[str]
    reason: str


WeightOrSkip = Union[WeightRow, SkipRow]


def compute_weight_for_drawing(
    drawing: str,
    dedup_routes: list[DedupRoute],
    *,
    skip_markers: Optional[list[SkipMarker]] = None,
    count_provider: CountProvider,
    length_provider: LengthProvider,
    spec_provider: SpecProvider,
    unit_weight_fn: UnitWeightFn,
) -> list[WeightOrSkip]:
    """도면 한 장의 부호별 총중량 행 + skip 행 생성.

    dedup_routes 중 `drawing` 에 해당하는 것만 처리한다. skip_markers 의 해당
    도면 섹션은 SkipRow 로 먼저 방출한다.
    """
    rows: list[WeightOrSkip] = []

    for marker in skip_markers or []:
        if marker.drawing != drawing:
            continue
        rows.append(SkipRow(
            drawing=drawing,
            member_kind="기둥",
            section=marker.section,
            reason=marker.reason,
        ))

    for route in dedup_routes:
        if route.drawing != drawing:
            continue

        if route.count_override is not None:
            count = route.count_override
            count_is_override = True
            count_from_label = f"(override:{count})"
            note = "count_override"
        else:
            assert route.count_from is not None
            count = count_provider(drawing, route.count_from, route.symbol)
            count_is_override = False
            count_from_label = route.count_from
            note = ""

        length_mm, length_sheet = length_provider(drawing, route.symbol)
        spec = spec_provider(drawing, route.spec_from, route.symbol)

        if length_mm is None:
            raise ValueError(f"{drawing}/{route.symbol}: 길이 측정값 없음 — 곱셈 불가")
        if not spec:
            raise ValueError(
                f"{drawing}/{route.symbol}: {route.spec_from!r} 시트에서 규격 추출 실패"
            )

        unit_weight = unit_weight_fn(spec)
        total = count * (length_mm / _MM_PER_M) * unit_weight

        rows.append(WeightRow(
            drawing=drawing,
            member_kind=route.member_kind,
            symbol=route.symbol,
            count=count,
            length_mm=length_mm,
            spec_normalized=spec,
            unit_weight_kg_per_m=round(unit_weight, 2),
            total_weight_kg=round(total, 1),
            count_from_sheet=count_from_label,
            spec_from_sheet=route.spec_from,
            length_from_sheet=length_sheet,
            section=route.section,
            count_is_override=count_is_override,
            note=note,
        ))

    return rows


def _weight_rows(rows: list[WeightOrSkip]) -> list[WeightRow]:
    return [r for r in rows if isinstance(r, WeightRow)]


def total_weight_kg(rows: list[WeightOrSkip]) -> float:
    """WeightRow 들의 총중량 합계 (SkipRow 제외, 반올림 1자리)."""
    return round(sum(r.total_weight_kg for r in _weight_rows(rows)), 1)


def total_count(rows: list[WeightOrSkip]) -> int:
    """WeightRow 들의 개수 합계 (SkipRow 제외)."""
    return sum(r.count for r in _weight_rows(rows))


# ── 기본 provider 어댑터 (측정 모듈을 얇게 감쌈) ────────────────────────────

def build_default_providers() -> tuple[CountProvider, LengthProvider,
                                        SpecProvider, UnitWeightFn]:
    """baseline-2/6 측정 + length_routing + baseline-1 단위중량을 감싼
    실측 provider 4종을 반환.

    측정 모듈 의존(ezdxf) 은 이 함수 안에서만 import 한다. 도면별 결과·시트별
    규격은 캐시해 DXF 재파싱을 막는다.

    규격(spec) 은 count>0 게이트 없이 spec_from 시트의 dxf 에서 직접 추출한다.
    count_override 부호(도면2) 도 규격을 얻을 수 있고, 카운트와 규격이 결합되지
    않는다(1a 도면4 결과는 동일 — 직접 추출도 같은 정규화값).
    """
    from poc_v2.baseline2.export_baseline2_csv import build_rows  # noqa: PLC0415
    from poc_v2.length.baseline_length import measure_drawing  # noqa: PLC0415
    from poc_v2.length.routing import load_routing  # noqa: PLC0415
    from poc_v2.length.spec_extractor import extract_specs  # noqa: PLC0415
    from poc_v2.qto.unit_weight_calc import unit_weight_kg_per_m  # noqa: PLC0415

    _count_cache: dict[str, dict[str, object]] = {}
    _len_cache: dict[str, object] = {}
    _spec_cache: dict[tuple[str, str], dict[str, str]] = {}
    _routing = load_routing()

    def _count_results_by_sheet(drawing: str) -> dict[str, object]:
        """도면의 count 종류 SmallDrawingResult 를 매칭시트명으로 인덱싱."""
        if drawing not in _count_cache:
            by_sheet = {
                r.matched_sheet: r
                for r in build_rows([drawing])
                if r.kind == "count"
            }
            _count_cache[drawing] = by_sheet
        return _count_cache[drawing]

    def count_provider(drawing: str, sheet: str, symbol: str) -> int:
        result = _count_results_by_sheet(drawing).get(sheet)
        if result is None:
            raise ValueError(
                f"{drawing}: dedup count_from 시트 {sheet!r} 의 count 결과 없음 "
                f"(가능: {sorted(_count_results_by_sheet(drawing))})"
            )
        return int(result.counts.get(symbol, 0))

    def _specs_for_sheet(drawing: str, sheet: str) -> dict[str, str]:
        """spec_from 시트의 dxf 에서 부호→정규화규격 (캐시)."""
        result = _count_results_by_sheet(drawing).get(sheet)
        if result is None:
            raise ValueError(
                f"{drawing}: dedup spec_from 시트 {sheet!r} 결과 없음 "
                f"(가능: {sorted(_count_results_by_sheet(drawing))})"
            )
        key = (drawing, result.file_path)
        if key not in _spec_cache:
            _spec_cache[key] = {
                e.symbol: e.spec_normalized for e in extract_specs(result.file_path, drawing)
            }
        return _spec_cache[key]

    def spec_provider(drawing: str, sheet: str, symbol: str) -> str:
        return _specs_for_sheet(drawing, sheet).get(symbol, "")

    def _length_sheet_label(drawing: str, symbol: str) -> str:
        """length_routing.yaml 에서 부호에 적용되는 소스 시트 라벨(중복 제거)."""
        labels: list[str] = []
        sources = _routing["drawings"].get(drawing, {}).get("sources", [])
        for source in sources:
            if symbol in source.get("applies_to", []):
                label = source.get("sheet_label", "")
                if label and label not in labels:
                    labels.append(label)
        return " / ".join(labels)

    def length_provider(drawing: str, symbol: str) -> tuple[Optional[float], str]:
        if drawing not in _len_cache:
            _len_cache[drawing] = measure_drawing(drawing)
        measurement = _len_cache[drawing]
        sym_meas = measurement.symbols.get(symbol)
        length = sym_meas.length_mm if sym_meas else None
        return length, _length_sheet_label(drawing, symbol)

    return count_provider, length_provider, spec_provider, unit_weight_kg_per_m
