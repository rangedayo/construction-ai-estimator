"""작은 도면 시트별 결과 CSV — 라운드 베이스라인-2 작업 4.

sample_data 의 작은 도면 dxf 들을 파이프라인에 흘려 시트별 PASS/FAIL CSV 를
만든다. 파일명이 아니라 dxf 표제부 도면명으로 시트를 식별한다.

CLI
    python -m poc_v2.baseline2.export_baseline2_csv                       # 도면4
    python -m poc_v2.baseline2.export_baseline2_csv --drawings 도면4
    python -m poc_v2.baseline2.export_baseline2_csv --drawings 도면4,도면5
    python -m poc_v2.baseline2.export_baseline2_csv --include-unmatched   # 입면도 등 포함
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import sys
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from poc_v2.baseline2.small_drawing_pipeline import (  # noqa: E402
    SmallDrawingResult,
    process_small_drawing,
)

_SAMPLE_DIR = os.path.join(PROJECT_ROOT, "sample_data")
_OUTPUT_CSV = os.path.join(
    PROJECT_ROOT, "outputs", "round_baseline2_시트별_결과.csv"
)
_HEADER = [
    "도면", "파일명", "추출도면명", "매칭시트", "신뢰도",
    "측정카운트", "정답카운트", "카운트결과",
    "측정길이", "정답길이", "길이결과",
    "측정규격", "정답규격", "규격결과",
]


def small_drawing_files(drawing: str) -> list[str]:
    """도면의 작은 도면 dxf 경로들 (큰 도면·부산물 제외, 정렬).

    큰 통합 도면(예: 도면4.dxf)은 "_" 가 없어 글롭에 걸리지 않는다.
    """
    return sorted(glob.glob(os.path.join(_SAMPLE_DIR, f"{drawing}_*.dxf")))


def _fmt_counts(counts: dict[str, int]) -> str:
    return ",".join(f"{s}={counts[s]}" for s in sorted(counts)) if counts else ""


def _fmt_specs(specs: dict[str, str]) -> str:
    return ",".join(
        f"{s}={specs[s]}" for s in sorted(specs) if specs.get(s)
    ) if specs else ""


def _fmt_pass(value: Optional[bool]) -> str:
    if value is None:
        return "N/A"
    return "PASS" if value else "FAIL"


def _fmt_len(value: Optional[float]) -> str:
    return f"{value:.0f}" if value is not None else "N/A"


def result_to_row(result: SmallDrawingResult) -> list[str]:
    """SmallDrawingResult → CSV 한 행 (2.2 형식)."""
    is_count = result.kind == "count"
    is_length = result.kind == "length"
    return [
        result.drawing,
        os.path.basename(result.file_path),
        result.extracted_title or "",
        result.matched_sheet or "",
        result.match_confidence,
        _fmt_counts(result.counts) if is_count else "N/A",
        _fmt_counts(result.expected_counts) if is_count else "N/A",
        _fmt_pass(result.pass_counts) if is_count else "N/A",
        _fmt_len(result.length_mm) if is_length else "N/A",
        _fmt_len(result.expected_length) if is_length else "N/A",
        _fmt_pass(result.pass_length) if is_length else "N/A",
        _fmt_specs(result.specs) if is_count else "N/A",
        _fmt_specs(result.expected_specs) if is_count else "N/A",
        _fmt_pass(result.pass_specs) if is_count else "N/A",
    ]


def build_rows(
    drawings: list[str],
    include_unmatched: bool = False,
) -> list[SmallDrawingResult]:
    """도면들의 작은 도면을 처리한 결과 리스트 (unmatched 는 기본 제외)."""
    results: list[SmallDrawingResult] = []
    for drawing in drawings:
        for path in small_drawing_files(drawing):
            result = process_small_drawing(path)
            if result.kind == "unmatched" and not include_unmatched:
                continue
            results.append(result)
    return results


def export_csv(
    drawings: list[str],
    output_path: Optional[str] = None,
    include_unmatched: bool = False,
) -> tuple[str, list[SmallDrawingResult]]:
    """CSV 파일을 쓰고 (경로, 결과 리스트) 반환."""
    results = build_rows(drawings, include_unmatched)
    out = output_path or _OUTPUT_CSV
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(_HEADER)
        for result in results:
            writer.writerow(result_to_row(result))
    return out, results


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="작은 도면 시트별 결과 CSV")
    parser.add_argument("--drawings", default="도면4", help="쉼표 구분 도면명")
    parser.add_argument("--include-unmatched", action="store_true")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    drawings = [d.strip() for d in args.drawings.split(",") if d.strip()]
    out, results = export_csv(drawings, args.output, args.include_unmatched)

    print(f"CSV 생성: {out}  ({len(results)}행)")
    for r in results:
        parts = []
        if r.kind == "count":
            parts.append(f"카운트 {_fmt_pass(r.pass_counts)}")
            if r.pass_specs is not None:
                parts.append(f"규격 {_fmt_pass(r.pass_specs)}")
        elif r.kind == "length":
            parts.append(f"길이 {_fmt_pass(r.pass_length)}")
        status = ", ".join(parts) if parts else "-"
        print(
            f"  {os.path.basename(r.file_path):<28} "
            f"[{r.match_confidence}/{r.kind}] {status}"
        )


if __name__ == "__main__":
    main()
