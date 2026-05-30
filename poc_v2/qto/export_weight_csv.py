"""도면 총중량 CSV 산출 CLI — 라운드 중량-1a.

dedup_routing.yaml + 측정 provider 4종을 엮어 도면 한 장의 부호별 총중량
행 + 합계 행을 CSV 로 쓴다.

CLI
    python -m poc_v2.qto.export_weight_csv --drawing 도면4
    python -m poc_v2.qto.export_weight_csv --drawing 도면4 \
        --output outputs/round_weight1a_도면4_총중량.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from poc_v2.qto.dedup_loader import routes_for_drawing  # noqa: E402
from poc_v2.qto.weight_pipeline import (  # noqa: E402
    WeightRow,
    build_default_providers,
    compute_weight_for_drawing,
    total_count,
    total_weight_kg,
)

_HEADER = [
    "도면", "부재종류", "부호", "개수", "길이_mm", "규격",
    "단위중량_kg_per_m", "총중량_kg",
    "count_from", "spec_from", "length_from",
]
_BLANK = "-"


def _default_output(drawing: str) -> str:
    return os.path.join(
        PROJECT_ROOT, "outputs", f"round_weight1a_{drawing}_총중량.csv"
    )


def _row_to_csv(row: WeightRow) -> list[str]:
    return [
        row.drawing,
        row.member_kind,
        row.symbol,
        str(row.count),
        f"{row.length_mm:.0f}",
        row.spec_normalized,
        f"{row.unit_weight_kg_per_m:.2f}",
        f"{row.total_weight_kg:.1f}",
        row.count_from_sheet,
        row.spec_from_sheet,
        row.length_from_sheet,
    ]


def _total_row(rows: list[WeightRow]) -> list[str]:
    drawing = rows[0].drawing if rows else ""
    kinds = {r.member_kind for r in rows}
    member_kind = next(iter(kinds)) if len(kinds) == 1 else "전체"
    return [
        drawing, member_kind, "합계",
        str(total_count(rows)),
        _BLANK, _BLANK, _BLANK,
        f"{total_weight_kg(rows):.1f}",
        _BLANK, _BLANK, _BLANK,
    ]


def compute_rows(drawing: str) -> list[WeightRow]:
    """도면의 부호별 총중량 행 산출 (실측 provider 사용)."""
    routes = routes_for_drawing(drawing)
    if not routes:
        raise ValueError(
            f"dedup_routing.yaml 에 {drawing!r} 라우팅 없음 — 이번 라운드 범위 외?"
        )
    count_p, length_p, spec_p, unit_fn = build_default_providers()
    return compute_weight_for_drawing(
        drawing, routes,
        count_provider=count_p,
        length_provider=length_p,
        spec_provider=spec_p,
        unit_weight_fn=unit_fn,
    )


def export_csv(
    drawing: str,
    output_path: Optional[str] = None,
    rows: Optional[list[WeightRow]] = None,
) -> tuple[str, list[WeightRow]]:
    """CSV 파일을 쓰고 (경로, 행 리스트) 반환. rows 를 주면 재계산 생략."""
    if rows is None:
        rows = compute_rows(drawing)
    out = output_path or _default_output(drawing)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(_HEADER)
        for row in rows:
            writer.writerow(_row_to_csv(row))
        if rows:
            writer.writerow(_total_row(rows))
    return out, rows


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="도면 총중량 CSV (라운드 중량-1a)")
    parser.add_argument("--drawing", default="도면4", help="도면명 (예: 도면4)")
    parser.add_argument("--output", default=None, help="출력 CSV 경로")
    args = parser.parse_args()

    out, rows = export_csv(args.drawing, args.output)
    print(f"CSV 생성: {out}  ({len(rows)}행 + 합계)")
    for r in rows:
        print(
            f"  {r.member_kind} {r.symbol:<5} "
            f"개수={r.count:>3} × 길이={r.length_mm:.0f}mm × "
            f"단위중량={r.unit_weight_kg_per_m:.2f}kg/m "
            f"= {r.total_weight_kg:.1f}kg  [{r.spec_normalized}]"
        )
    print(f"  합계: 개수={total_count(rows)}, 총중량={total_weight_kg(rows):.1f}kg")


if __name__ == "__main__":
    main()
