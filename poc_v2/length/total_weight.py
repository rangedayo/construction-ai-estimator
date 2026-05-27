"""총중량 합산 — 라운드 길이-4.

(도면, 동, 부호) 단위로 count·length·spec·unit_weight 를 조인해
총중량(kg) = count × length(m) × unit_weight(kg/m) 을 산출한다.

데이터 소스
    count, length_mm  : 정답지 (`load_section_instances`)
        ※ 1단계 baseline 은 도면 단위 합계만 — 동별 분해가 없어 라운드 길이-4
           에서는 정답지 인스턴스 행으로 per-section 카운트를 임시 대체.
    spec              : DXF (`spec_extractor.extract_specs`)
    unit_weight       : yaml (`unit_weight.lookup_unit_weight`)
        ※ yaml 값은 명세서 임시값 — 멘토 확인 후 정확값 교체 예정.

CLI
    python -m poc_v2.length.total_weight
    → outputs/round_length4_총중량.csv 생성
"""
from __future__ import annotations

import csv
import os
import sys
from dataclasses import dataclass
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from poc_v2.length.ground_truth_spec import (  # noqa: E402
    InstanceAnswer,
    SpecAnswer,
    load_ground_truth_spec,
    load_section_instances,
)
from poc_v2.length.spec_extractor import (  # noqa: E402
    SpecExtraction,
    extract_specs,
)
from poc_v2.length.unit_weight import (  # noqa: E402
    load_unit_weight_table,
    lookup_unit_weight,
)

_DEFAULT_DRAWINGS = ("도면1", "도면2", "도면3", "도면4", "도면5")
_DXF_DIR = os.path.join(PROJECT_ROOT, "sample_data")
_OUTPUT_CSV = os.path.join(PROJECT_ROOT, "outputs", "round_length4_총중량.csv")


@dataclass
class WeightRow:
    drawing: str
    section: Optional[str]
    symbol: str
    count: int
    length_mm: Optional[float]
    spec_raw: Optional[str]
    spec_normalized: Optional[str]
    spec_note: Optional[str]
    unit_weight_kg_per_m: Optional[float]
    total_weight_kg: Optional[float]
    skip_reason: Optional[str]

    def as_csv_row(self) -> list[str]:
        def fmt(x: object) -> str:
            if x is None:
                return ""
            if isinstance(x, float):
                return f"{x:.1f}"
            return str(x)
        return [
            self.drawing,
            self.section or "",
            self.symbol,
            str(self.count),
            fmt(self.length_mm),
            self.spec_raw or "",
            self.spec_normalized or "",
            self.spec_note or "",
            fmt(self.unit_weight_kg_per_m),
            fmt(self.total_weight_kg),
            self.skip_reason or "",
        ]


CSV_HEADER = [
    "drawing", "section", "symbol", "count", "length_mm",
    "spec_raw", "spec_normalized", "spec_note",
    "unit_weight_kg_per_m", "total_weight_kg", "skip_reason",
]


def _dxf_path(drawing: str) -> str:
    return os.path.join(_DXF_DIR, f"{drawing}.dxf")


def compute_weights(
    drawings: tuple[str, ...] = _DEFAULT_DRAWINGS,
) -> list[WeightRow]:
    """모든 도면에 대해 (도면, 동, 부호) 단위 총중량 행 생성."""
    instance_map = load_section_instances(drawings=list(drawings))
    answer_map = load_ground_truth_spec(drawings=list(drawings))
    unit_table = load_unit_weight_table()

    extraction_map: dict[tuple[str, Optional[str], str], SpecExtraction] = {}
    for drawing in drawings:
        path = _dxf_path(drawing)
        if not os.path.exists(path):
            continue
        for extraction in extract_specs(path, drawing):
            key = (extraction.drawing, extraction.section, extraction.symbol)
            extraction_map[key] = extraction

    rows: list[WeightRow] = []
    for key, instance in sorted(
        instance_map.items(), key=lambda kv: (kv[0][0], kv[0][1] or "", kv[0][2])
    ):
        extraction = extraction_map.get(key)
        answer = answer_map.get(key)
        spec_source = _resolve_spec(extraction, answer)
        rows.append(_build_row(instance, spec_source, unit_table))
    return rows


def _resolve_spec(
    extraction: Optional[SpecExtraction],
    answer: Optional[SpecAnswer],
) -> Optional[tuple[str, str, Optional[str]]]:
    """추출 결과를 우선, 없으면 정답지 폴백. (raw, normalized, note) 반환."""
    if extraction is not None:
        note = answer.spec_note if answer else None
        return (extraction.spec_raw, extraction.spec_normalized, note)
    if answer is not None:
        return (answer.spec_raw, answer.spec_normalized, answer.spec_note)
    return None


def _build_row(
    instance: InstanceAnswer,
    spec: Optional[tuple[str, str, Optional[str]]],
    unit_table: dict[str, float],
) -> WeightRow:
    if spec is None:
        return WeightRow(
            drawing=instance.drawing,
            section=instance.section,
            symbol=instance.symbol,
            count=instance.count,
            length_mm=instance.length_mm,
            spec_raw=None,
            spec_normalized=None,
            spec_note=None,
            unit_weight_kg_per_m=None,
            total_weight_kg=None,
            skip_reason="규격 추출 실패",
        )

    spec_raw, spec_normalized, spec_note = spec
    unit_weight = lookup_unit_weight(spec_normalized, unit_table)

    skip_reasons: list[str] = []
    if instance.length_mm is None:
        skip_reasons.append("길이 측정 불가 (소스 도면 없음)")
    if unit_weight is None:
        skip_reasons.append(f"단위중량 누락 (yaml 키 부재: {spec_normalized})")

    if skip_reasons:
        return WeightRow(
            drawing=instance.drawing,
            section=instance.section,
            symbol=instance.symbol,
            count=instance.count,
            length_mm=instance.length_mm,
            spec_raw=spec_raw,
            spec_normalized=spec_normalized,
            spec_note=spec_note,
            unit_weight_kg_per_m=unit_weight,
            total_weight_kg=None,
            skip_reason="; ".join(skip_reasons),
        )

    total = instance.count * (instance.length_mm / 1000.0) * unit_weight
    return WeightRow(
        drawing=instance.drawing,
        section=instance.section,
        symbol=instance.symbol,
        count=instance.count,
        length_mm=instance.length_mm,
        spec_raw=spec_raw,
        spec_normalized=spec_normalized,
        spec_note=spec_note,
        unit_weight_kg_per_m=unit_weight,
        total_weight_kg=total,
        skip_reason=None,
    )


def write_csv(rows: list[WeightRow], path: str = _OUTPUT_CSV) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
        for row in rows:
            writer.writerow(row.as_csv_row())


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    rows = compute_weights()
    write_csv(rows)

    produced = sum(1 for r in rows if r.total_weight_kg is not None)
    skipped = len(rows) - produced
    total_weight = sum(r.total_weight_kg or 0.0 for r in rows)

    print(f"산출 행: {len(rows)}  (총중량 산출 {produced}, 보류 {skipped})")
    print(f"총중량 합계: {total_weight:,.1f} kg")
    print(f"CSV: {_OUTPUT_CSV}")

    print(
        f"\n{'drawing':<8}{'section':<6}{'symbol':<6}{'cnt':>4}"
        f"{'len(mm)':>9}{'unit':>8}{'total(kg)':>12}  spec / reason"
    )
    for row in rows:
        section = row.section or "-"
        length = f"{row.length_mm:.0f}" if row.length_mm is not None else "-"
        unit = (
            f"{row.unit_weight_kg_per_m:.1f}"
            if row.unit_weight_kg_per_m is not None
            else "-"
        )
        total = (
            f"{row.total_weight_kg:.1f}" if row.total_weight_kg is not None else "-"
        )
        spec = row.spec_normalized or "?"
        reason = row.skip_reason or ""
        print(
            f"{row.drawing:<8}{section:<6}{row.symbol:<6}{row.count:>4}"
            f"{length:>9}{unit:>8}{total:>12}  {spec}  {reason}"
        )


if __name__ == "__main__":
    main()
