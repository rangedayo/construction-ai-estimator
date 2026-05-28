"""spec_extractor 전부재 덤프 + 도면4 일람표 검출 — 1회성 진단."""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from poc_v2.length.spec_extractor import extract_specs  # noqa: E402

DRAWINGS = ("도면1", "도면2", "도면3", "도면4", "도면5")
DXF_DIR = os.path.join(PROJECT_ROOT, "sample_data")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    print("=== spec_extractor 전체 SpecExtraction (기둥 외 부재 포함) ===")
    print(f"{'drawing':<8}{'section':<8}{'symbol':<8}{'spec_raw':<24}table_region_idx")
    print("-" * 70)
    total = 0
    for drawing in DRAWINGS:
        path = os.path.join(DXF_DIR, f"{drawing}.dxf")
        rows = extract_specs(path, drawing)
        for ex in sorted(rows, key=lambda e: (e.section or "", e.symbol)):
            sec = ex.section or "(None)"
            print(f"{drawing:<8}{sec:<8}{ex.symbol:<8}{ex.spec_raw:<24}N/A")
            total += 1
        if not rows:
            print(f"{drawing:<8}{'—':<8}{'(추출 0건)':<8}")
    print("-" * 70)
    print(f"합계 {total}건\n")

    # 도면4 일람표 검출 (카운팅 파이프라인 경로 재사용)
    print("=== 도면4 일람표(table_region) 검출 — 카운팅 파이프라인 ===")
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "poc_v2", "tests"))
    from baseline import compute_drawing  # noqa: E402

    result = compute_drawing("도면4")
    regions = result.get("regions", [])
    print(f"검출 영역 수: {len(regions)}")
    for i, r in enumerate(regions):
        bbox = r["bbox"]
        syms = r.get("symbols", {})
        print(f"  [{i}] bbox=(xmin={bbox[0]:.1f}, ymin={bbox[1]:.1f}, "
              f"xmax={bbox[2]:.1f}, ymax={bbox[3]:.1f})  부호={syms}")


if __name__ == "__main__":
    main()
