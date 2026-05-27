"""라운드 길이-4 사전조사 — 도면1 일람표 검출 실패 원인 진단.

격리 위치(outputs/diagnose/). 본선 코드(counter.py / baseline.py / yaml) 무수정.
회귀 영향 0. 진단 출력만 한다.

다음 라운드 길이-4 에서 일람표 영역을 부호별 규격 소스로 활용하기 전에,
도면1 일람표가 왜 detect_table_regions 에 안 잡히는지 확인한다.

검증할 가설:
    H1: 일람표 텍스트 height 가 min_height=177 미만 → height 필터에서 컷
    H2: 일람표 안 부호가 INSERT ATTRIB / 블록 내 TEXT 안에 묻혀 있어
        detect_table_regions 입력(modelspace TEXT/MTEXT)이 빈다
    H3: 매칭은 됐는데 detect_table_regions 임계값(min_distinct_symbols=4,
        max_count_per_symbol=2)에 못 걸린다
"""
from __future__ import annotations

import os
import sys
from collections import Counter

import ezdxf

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
_POC_TESTS = os.path.join(_PROJECT_ROOT, "poc_v2", "tests")
_POC = os.path.join(_PROJECT_ROOT, "poc_v2")
for _p in (_POC, _POC_TESTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from counter import _clean_mtext, match_symbol, _text_height  # noqa: E402
from detect_table_region import detect_table_regions, load_text_layout  # noqa: E402
from ground_truth import (  # noqa: E402
    drawing_symbol_totals,
    load_table_region_params,
    load_text_height_filter,
)

DXF_PATH = os.path.join(_PROJECT_ROOT, "sample_data", "도면1.dxf")
DRAWING = "도면1"

# 의심 영역: 좌측 하단. extent 의 좌하 30%×40% 를 1차 후보로 본다.
# (시각화 HTML 에서 H-200x200x8/13 줄이 보이는 위치)


def _bbox_left_bottom_quarter(doc):
    emin = doc.header["$EXTMIN"]
    emax = doc.header["$EXTMAX"]
    xmin, ymin = float(emin[0]), float(emin[1])
    xmax, ymax = float(emax[0]), float(emax[1])
    width = xmax - xmin
    height = ymax - ymin
    bx0, bx1 = xmin, xmin + width * 0.30
    by0, by1 = ymin, ymin + height * 0.40
    return (bx0, by0, bx1, by1), (xmin, ymin, xmax, ymax)


def _in_bbox(x, y, bbox):
    return bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]


def collect_in_bbox(doc, bbox, whitelist):
    """좌하 bbox 안의 TEXT / MTEXT / INSERT(ATTRIB·블록 내 TEXT) 전부."""
    msp = doc.modelspace()
    rows = []
    for ent in msp:
        dtype = ent.dxftype()
        if dtype in ("TEXT", "MTEXT"):
            try:
                raw = ent.dxf.text
                text = _clean_mtext(raw) if dtype == "MTEXT" else raw.strip()
                pt = ent.dxf.insert
                x, y = float(pt.x), float(pt.y)
                if not _in_bbox(x, y, bbox):
                    continue
                if not text:
                    continue
                h = _text_height(ent, dtype)
                sym = match_symbol(text, whitelist)
                sym_spec = match_symbol(text, whitelist, exclude_with_spec=True)
                rows.append({
                    "text": text,
                    "x": x,
                    "y": y,
                    "height": h or 0.0,
                    "source": dtype,
                    "match": sym,
                    "match_excl_spec": sym_spec,
                })
            except Exception:
                pass
        elif dtype == "INSERT":
            try:
                pt = ent.dxf.insert
                x, y = float(pt.x), float(pt.y)
            except Exception:
                continue
            if not _in_bbox(x, y, bbox):
                continue
            block_name = getattr(ent.dxf, "name", "?")
            # ATTRIB
            try:
                for attrib in ent.attribs:
                    try:
                        val = (
                            attrib.dxf.text.strip()
                            if attrib.dxf.hasattr("text") else ""
                        )
                        if not val:
                            continue
                        try:
                            h = float(attrib.dxf.height)
                        except Exception:
                            h = 0.0
                        sym = match_symbol(val, whitelist)
                        sym_spec = match_symbol(val, whitelist, exclude_with_spec=True)
                        rows.append({
                            "text": val,
                            "x": x,
                            "y": y,
                            "height": h,
                            "source": f"INSERT_ATTRIB[{block_name}]",
                            "match": sym,
                            "match_excl_spec": sym_spec,
                        })
                    except Exception:
                        pass
            except Exception:
                pass
            # 블록 정의 내 TEXT / MTEXT / ATTDEF
            try:
                block = doc.blocks.get(ent.dxf.name)
                if block:
                    for be in block:
                        btype = be.dxftype()
                        if btype == "TEXT":
                            try:
                                val = be.dxf.text.strip()
                            except Exception:
                                val = ""
                        elif btype == "MTEXT":
                            try:
                                val = _clean_mtext(be.plain_mtext())
                            except Exception:
                                val = ""
                        elif btype == "ATTDEF":
                            try:
                                val = be.dxf.text.strip()
                            except Exception:
                                val = ""
                        else:
                            continue
                        if not val:
                            continue
                        h_type = "TEXT" if btype == "ATTDEF" else btype
                        h = _text_height(be, h_type)
                        sym = match_symbol(val, whitelist)
                        sym_spec = match_symbol(val, whitelist, exclude_with_spec=True)
                        rows.append({
                            "text": val,
                            "x": x,
                            "y": y,
                            "height": h or 0.0,
                            "source": f"INSERT_BLOCKDEF[{block_name}]/{btype}",
                            "match": sym,
                            "match_excl_spec": sym_spec,
                        })
            except Exception:
                pass
    return rows


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    expected = drawing_symbol_totals()[DRAWING]
    whitelist = set(expected.keys())
    min_h = load_text_height_filter().get(DRAWING)
    table_params = load_table_region_params()

    doc = ezdxf.readfile(DXF_PATH)
    bbox, extent = _bbox_left_bottom_quarter(doc)

    print("=" * 78)
    print(f" 라운드 길이-4 사전조사 — {DRAWING} 일람표 검출 실패 진단")
    print("=" * 78)
    print(f" DXF extent: x={extent[0]:.1f}~{extent[2]:.1f}  "
          f"y={extent[1]:.1f}~{extent[3]:.1f}")
    print(f" 진단 bbox (좌하 30%×40%): "
          f"x={bbox[0]:.1f}~{bbox[2]:.1f}  y={bbox[1]:.1f}~{bbox[3]:.1f}")
    print(f" 회귀 화이트리스트(={DRAWING} expected): {sorted(whitelist)}")
    print(f" min_text_height (yaml): {min_h}")
    print(f" table_region_detection (yaml): {table_params}")
    print()

    rows = collect_in_bbox(doc, bbox, whitelist)
    print(f"[좌하 bbox 내 모든 텍스트 엔티티: {len(rows)}건]")
    print("-" * 78)
    print(f"{'#':>3}  {'source':<34} {'h':>7}  {'match':<6} {'match_es':<8} text")
    for i, r in enumerate(rows):
        print(
            f"{i:>3}  {r['source']:<34} {r['height']:>7.1f}  "
            f"{(r['match'] or '-'):<6} {(r['match_excl_spec'] or '-'):<8} "
            f"{r['text'][:60]}"
        )
    print()

    # ── H1: height 분포 ─────────────────────────────────────────────────────
    print("[H1] 좌하 bbox 텍스트 height 분포 vs min_height =", min_h)
    print("-" * 78)
    height_counter = Counter(round(r["height"]) for r in rows)
    for h, c in sorted(height_counter.items()):
        mark = ""
        if min_h is not None:
            mark = "  (PASS)" if h >= min_h else "  (FILTERED OUT)"
        print(f"  height {h:>7}: {c:>4}회{mark}")
    if min_h is not None:
        survived = sum(c for h, c in height_counter.items() if h >= min_h)
        culled = sum(c for h, c in height_counter.items() if h < min_h)
        print(f"  → min_height={min_h} 적용 시 통과 {survived}건 / 제외 {culled}건")
    print()

    # ── H2: source 별 매칭 분포 ─────────────────────────────────────────────
    print("[H2] 좌하 bbox 에서 화이트리스트 매칭된 부호의 source 분포")
    print("-" * 78)
    matched = [r for r in rows if r["match"] is not None]
    print(f"  매칭 부호 총 {len(matched)}건")
    src_of_match = Counter(r["source"].split("[")[0] for r in matched)
    for src, c in src_of_match.most_common():
        print(f"    {src:<24} : {c}건")
    sym_per_source: dict[str, Counter] = {}
    for r in matched:
        bucket = r["source"].split("[")[0]
        sym_per_source.setdefault(bucket, Counter())[r["match"]] += 1
    for src, ctr in sym_per_source.items():
        print(f"  -- {src} 매칭 부호별 카운트 --")
        for s, n in ctr.most_common():
            print(f"     {s}: {n}")
    h_spec_rows = [r for r in rows if r["text"].upper().startswith("H-")]
    print(f"\n  'H-규격' 으로 시작하는 텍스트 (예: H-200x200x8/13): {len(h_spec_rows)}건")
    for r in h_spec_rows[:20]:
        print(f"     ({r['x']:.0f},{r['y']:.0f})  h={r['height']:.0f}  "
              f"src={r['source']}  text={r['text'][:60]}")
    print()

    # ── H3: detect_table_regions 실제 호출 결과 (baseline 과 동일 입력) ────
    print("[H3] detect_table_regions 실제 호출 — load_text_layout 출력 검증")
    print("-" * 78)
    text_coords, drawing_extent = load_text_layout(
        DXF_PATH, sorted(whitelist), min_text_height=min_h, exclude_with_spec=True
    )
    print(f"  load_text_layout 결과 — 자유 텍스트 부호 수: {len(text_coords)}")
    for sym in sorted(text_coords):
        pts = text_coords[sym]
        in_bbox_pts = [p for p in pts if _in_bbox(p[0], p[1], bbox)]
        print(f"    {sym}: 전체 {len(pts)}좌표, 좌하 bbox 안 {len(in_bbox_pts)}좌표")
        for p in in_bbox_pts[:3]:
            print(f"        ({p[0]:.0f}, {p[1]:.0f})")

    sparse_coords = {s: pts for s, pts in text_coords.items() if len(pts) <= 5}
    print(f"\n  sparse(<=5) 보정 후 부호 수: {len(sparse_coords)}")
    for sym in sorted(sparse_coords):
        pts = sparse_coords[sym]
        in_bbox_pts = [p for p in pts if _in_bbox(p[0], p[1], bbox)]
        if in_bbox_pts:
            print(f"    {sym}: 좌하 bbox 안 {len(in_bbox_pts)}개")

    regions = detect_table_regions(sparse_coords, drawing_extent, **table_params)
    print(f"\n  detect_table_regions 결과: {len(regions)}곳")
    for i, reg in enumerate(regions):
        print(f"    region[{i}] bbox={reg['bbox']}")
        print(f"               symbols={reg['symbols']}")

    syms_in_bbox = set(
        sym for sym, pts in text_coords.items()
        if any(_in_bbox(p[0], p[1], bbox) for p in pts)
    )
    syms_in_bbox_sparse = set(
        sym for sym, pts in sparse_coords.items()
        if any(_in_bbox(p[0], p[1], bbox) for p in pts)
    )
    print(f"\n  좌하 bbox 안 자유 텍스트 화이트리스트 부호 종류: {len(syms_in_bbox)} "
          f"(sparse 보정 후 {len(syms_in_bbox_sparse)})")
    print(f"    -- 부호: {sorted(syms_in_bbox)}")
    print(f"    -- sparse: {sorted(syms_in_bbox_sparse)}")
    print(f"    -- 임계 min_distinct_symbols={table_params['min_distinct_symbols']}")
    print(f"    → 임계 충족? "
          f"{len(syms_in_bbox_sparse) >= table_params['min_distinct_symbols']}")
    print()

    print("=" * 78)
    print(" 진단 종료")
    print("=" * 78)


if __name__ == "__main__":
    main()
