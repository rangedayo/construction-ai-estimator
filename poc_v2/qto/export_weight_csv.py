"""도면 총중량 CSV 산출 CLI — 라운드 중량-1a/1b.

dedup_routing.yaml + 측정 provider 4종을 엮어 부호별 총중량 행 + 합계 행을
CSV 로 쓴다.

CLI
    # 1a — 도면 한 장 (11열)
    python -m poc_v2.qto.export_weight_csv --drawing 도면4

    # 1b — 5장 통합 (13열: 동·비고 포함, skip/총합 행)
    python -m poc_v2.qto.export_weight_csv --all \
        --output outputs/round_weight1b_5장_총중량.csv
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

from poc_v2.qto.dedup_loader import load_dedup, routes_for_drawing  # noqa: E402
from poc_v2.qto.weight_pipeline import (  # noqa: E402
    SkipRow,
    WeightOrSkip,
    WeightRow,
    build_default_providers,
    compute_weight_for_drawing,
    total_count,
    total_weight_kg,
)

ALL_DRAWINGS = ("도면1", "도면2", "도면3", "도면4", "도면5")
_BLANK = "-"
_EMPTY = ""

# 1a 단일 도면 형식 (11열) — 회귀 호환 위해 불변
_HEADER = [
    "도면", "부재종류", "부호", "개수", "길이_mm", "규격",
    "단위중량_kg_per_m", "총중량_kg",
    "count_from", "spec_from", "length_from",
]

# 1b 5장 통합 형식 (13열) — 동·비고 추가
_HEADER_1B = [
    "도면", "동", "부재종류", "부호", "개수", "길이_mm", "규격",
    "단위중량_kg_per_m", "총중량_kg",
    "count_from", "spec_from", "length_from", "비고",
]


# ── 1a: 단일 도면 (11열) ─────────────────────────────────────────────────

def _default_output(drawing: str) -> str:
    return os.path.join(
        PROJECT_ROOT, "outputs", f"round_weight1a_{drawing}_총중량.csv"
    )


def _row_to_csv(row: WeightRow) -> list[str]:
    return [
        row.drawing, row.member_kind, row.symbol, str(row.count),
        f"{row.length_mm:.0f}", row.spec_normalized,
        f"{row.unit_weight_kg_per_m:.2f}", f"{row.total_weight_kg:.1f}",
        row.count_from_sheet, row.spec_from_sheet, row.length_from_sheet,
    ]


def _total_row(rows: list[WeightRow]) -> list[str]:
    drawing = rows[0].drawing if rows else ""
    kinds = {r.member_kind for r in rows}
    member_kind = next(iter(kinds)) if len(kinds) == 1 else "전체"
    return [
        drawing, member_kind, "합계", str(total_count(rows)),
        _BLANK, _BLANK, _BLANK, f"{total_weight_kg(rows):.1f}",
        _BLANK, _BLANK, _BLANK,
    ]


def compute_rows(drawing: str) -> list[WeightRow]:
    """도면의 부호별 총중량 행 산출 (실측 provider). 1a 진입점."""
    routes = routes_for_drawing(drawing)
    if not routes:
        raise ValueError(
            f"dedup_routing.yaml 에 {drawing!r} 라우팅 없음 — 이번 라운드 범위 외?"
        )
    count_p, length_p, spec_p, unit_fn = build_default_providers()
    rows = compute_weight_for_drawing(
        drawing, routes,
        count_provider=count_p, length_provider=length_p,
        spec_provider=spec_p, unit_weight_fn=unit_fn,
    )
    return [r for r in rows if isinstance(r, WeightRow)]


def export_csv(
    drawing: str,
    output_path: Optional[str] = None,
    rows: Optional[list[WeightRow]] = None,
) -> tuple[str, list[WeightRow]]:
    """단일 도면 CSV(11열) 를 쓰고 (경로, 행 리스트) 반환."""
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


# ── 1b: 5장 통합 (13열) ──────────────────────────────────────────────────

def _default_all_output() -> str:
    return os.path.join(PROJECT_ROOT, "outputs", "round_weight1b_5장_총중량.csv")


def _row_to_csv_1b(row: WeightRow) -> list[str]:
    return [
        row.drawing, row.section or _EMPTY, row.member_kind, row.symbol,
        str(row.count), f"{row.length_mm:.0f}", row.spec_normalized,
        f"{row.unit_weight_kg_per_m:.2f}", f"{row.total_weight_kg:.1f}",
        row.count_from_sheet, row.spec_from_sheet, row.length_from_sheet,
        row.note,
    ]


def _skip_to_csv_1b(row: SkipRow) -> list[str]:
    return [
        row.drawing, row.section or _EMPTY, row.member_kind, "(skip)",
        _EMPTY, _EMPTY, _EMPTY, _EMPTY, _EMPTY,
        _EMPTY, _EMPTY, _EMPTY, row.reason,
    ]


def _grand_total_row_1b(rows: list[WeightOrSkip]) -> list[str]:
    return [
        "총합", _EMPTY, _EMPTY, _EMPTY, _EMPTY, _EMPTY, _EMPTY, _EMPTY,
        f"{total_weight_kg(rows):.1f}", _EMPTY, _EMPTY, _EMPTY, _EMPTY,
    ]


def compute_all_rows() -> list[WeightOrSkip]:
    """5장 전체 순회 — WeightRow/SkipRow 평면 리스트. provider 캐시 공유."""
    routes_all, skips_all = load_dedup()
    count_p, length_p, spec_p, unit_fn = build_default_providers()
    rows: list[WeightOrSkip] = []
    for drawing in ALL_DRAWINGS:
        dwg_routes = sorted(
            (r for r in routes_all if r.drawing == drawing),
            key=lambda r: (r.section or "", r.member_kind, r.symbol),
        )
        dwg_skips = [s for s in skips_all if s.drawing == drawing]
        rows.extend(compute_weight_for_drawing(
            drawing, dwg_routes,
            skip_markers=dwg_skips,
            count_provider=count_p, length_provider=length_p,
            spec_provider=spec_p, unit_weight_fn=unit_fn,
        ))
    return rows


def export_all_csv(
    output_path: Optional[str] = None,
    rows: Optional[list[WeightOrSkip]] = None,
) -> tuple[str, list[WeightOrSkip]]:
    """5장 통합 CSV(13열) 를 쓰고 (경로, 행 리스트) 반환."""
    if rows is None:
        rows = compute_all_rows()
    out = output_path or _default_all_output()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(_HEADER_1B)
        for row in rows:
            if isinstance(row, SkipRow):
                writer.writerow(_skip_to_csv_1b(row))
            else:
                writer.writerow(_row_to_csv_1b(row))
        writer.writerow(_grand_total_row_1b(rows))
    return out, rows


def subtotal_by_drawing(rows: list[WeightOrSkip]) -> dict[str, float]:
    """도면별 총중량 소계 (보고서용)."""
    out: dict[str, float] = {}
    for row in rows:
        if isinstance(row, WeightRow):
            out[row.drawing] = round(out.get(row.drawing, 0.0) + row.total_weight_kg, 1)
    return out


def _print_all_summary(rows: list[WeightOrSkip]) -> None:
    for row in rows:
        if isinstance(row, SkipRow):
            print(f"  {row.drawing} {row.section or '':<3} (skip) — {row.reason}")
        else:
            sec = f"{row.section} " if row.section else ""
            ov = " [override]" if row.count_is_override else ""
            print(
                f"  {row.drawing} {sec}{row.member_kind} {row.symbol:<5} "
                f"개수={row.count:>3} × {row.length_mm:.0f}mm × "
                f"{row.unit_weight_kg_per_m:.2f}kg/m = {row.total_weight_kg:.1f}kg{ov}"
            )
    print("  " + "-" * 50)
    for dwg, sub in subtotal_by_drawing(rows).items():
        print(f"  {dwg} 소계: {sub:.1f}kg")
    print(f"  ▶ 5장 총합: {total_weight_kg(rows):.1f}kg (총 {total_count(rows)}개)")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="도면 총중량 CSV (라운드 중량-1a/1b)")
    parser.add_argument("--drawing", default="도면4", help="단일 도면명 (1a)")
    parser.add_argument("--all", action="store_true", help="5장 통합 산출 (1b)")
    parser.add_argument("--output", default=None, help="출력 CSV 경로")
    args = parser.parse_args()

    if args.all:
        out, rows = export_all_csv(args.output)
        print(f"CSV 생성: {out}  ({len(rows)}행 + 총합)")
        _print_all_summary(rows)
        return

    out, rows = export_csv(args.drawing, args.output)
    print(f"CSV 생성: {out}  ({len(rows)}행 + 합계)")
    for r in rows:
        print(
            f"  {r.member_kind} {r.symbol:<5} 개수={r.count:>3} × "
            f"길이={r.length_mm:.0f}mm × 단위중량={r.unit_weight_kg_per_m:.2f}kg/m "
            f"= {r.total_weight_kg:.1f}kg  [{r.spec_normalized}]"
        )
    print(f"  합계: 개수={total_count(rows)}, 총중량={total_weight_kg(rows):.1f}kg")


if __name__ == "__main__":
    main()
