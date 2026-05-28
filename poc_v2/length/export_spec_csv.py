"""규격 추출 CSV 내보내기 — 라운드 규격-1.

`spec_extractor.extract_specs` 의 전수 보존 결과(중복 포함)를 그대로 CSV 로
떨군다. 중량 산출(total_weight)·단위중량(unit_weight)은 이 라운드에서 호출하지
않는다 — 여기서는 부호↔규격 측정값과 출처만 기록한다.

CLI
    python -m poc_v2.length.export_spec_csv
    → outputs/round_spec1_규격추출.csv 생성
"""
from __future__ import annotations

import csv
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from poc_v2.length.spec_extractor import extract_specs  # noqa: E402

_DRAWINGS = ("도면1", "도면2", "도면3", "도면4", "도면5")
_DXF_DIR = os.path.join(PROJECT_ROOT, "sample_data")
_OUTPUT_CSV = os.path.join(PROJECT_ROOT, "outputs", "round_spec1_규격추출.csv")

CSV_HEADER = [
    "drawing", "section", "symbol", "spec_raw", "spec_normalized", "spec_note",
    "source_sheet", "source_table_title", "symbol_x", "symbol_y",
]


def export(path: str = _OUTPUT_CSV) -> int:
    """모든 도면의 추출 건(기둥·보·가새 포함, P 등 차감 부재 제외)을 CSV 로 기록."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    count = 0
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
        for drawing in _DRAWINGS:
            dxf_path = os.path.join(_DXF_DIR, f"{drawing}.dxf")
            if not os.path.exists(dxf_path):
                continue
            extractions = extract_specs(dxf_path, drawing)
            extractions.sort(
                key=lambda e: (e.section or "", e.symbol, e.symbol_coord[0])
            )
            for ex in extractions:
                writer.writerow([
                    ex.drawing,
                    ex.section or "",
                    ex.symbol,
                    ex.spec_raw,
                    ex.spec_normalized,
                    ex.spec_note or "",
                    ex.source_sheet or "",
                    ex.source_table_title or "",
                    f"{ex.symbol_coord[0]:.1f}",
                    f"{ex.symbol_coord[1]:.1f}",
                ])
                count += 1
    return count


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    count = export()
    print(f"규격 추출 {count}건 → {_OUTPUT_CSV}")


if __name__ == "__main__":
    main()
