"""일람표(부재 일람표) 영역 검출 — 라운드 5 정책 P 신호 1.

회사·도면 무관하게 작동하는 보편 룰만 쓴다. layer 이름 화이트리스트·키워드
매칭 금지. 외부 클러스터링 라이브러리(DBSCAN 등) 도입 금지.

핵심 신호:
    "좁은 bbox(도면 폭의 1/30 수준) 안에 N종 이상의 서로 다른 부호가
     각각 1~2회씩만 등장하면 그 영역은 일람표"

근거: 일람표는 '표'라는 정의상 회사 무관 패턴이다. 실제 부재 배치는 같은
부호가 한 영역에 수십 번 반복되지만, 일람표는 종류별로 1~2번만 나온다.

검출 입력은 자유 텍스트(TEXT/MTEXT) 좌표만 쓴다. 부재 실배치는 블록
인스턴스(INSERT/ATTRIB)로 그려지고 일람표는 자유 주석 텍스트로 그려지는데,
이 구분은 DXF 구조상의 차이라 회사 이름과 무관한 보편 신호다. 블록 인스턴스
좌표까지 섞으면 부재 밀집 영역이 일람표 셀을 오염시켜 검출이 불가능해진다.

counter.py 는 건드리지 않는다(이 모듈은 counter.py 외부 진단 도구).
"""
from __future__ import annotations

import os
import sys
from collections import Counter, defaultdict

import ezdxf

# poc_v2(=counter.py 위치)를 import 경로에 추가
_HERE = os.path.dirname(os.path.abspath(__file__))
_POC_DIR = os.path.dirname(_HERE)
for _path in (_POC_DIR, _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from counter import _clean_mtext, _height_ok, match_symbol  # noqa: E402


def load_text_layout(
    dxf_path: str,
    whitelist: list[str],
    min_text_height: float | None = None,
    exclude_with_spec: bool = True,
) -> tuple[dict[str, list[tuple[float, float]]], tuple[float, float, float, float]]:
    """DXF 한 번 읽어 자유 텍스트 좌표와 도면 실효 범위를 함께 반환한다.

    coords_by_symbol 에는 modelspace 의 TEXT/MTEXT 만 담는다(INSERT/ATTRIB 제외).
    규격 안내 텍스트는 exclude_with_spec=True 로 자동 제외해 일람표 검출 입력을
    실제 표 텍스트 위주로 정리한다.

    Returns
    -------
    (coords_by_symbol, drawing_extent)
        coords_by_symbol : {부호: [(x, y), ...]}
        drawing_extent   : (xmin, ymin, xmax, ymax)
    """
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    wl = set(whitelist)

    coords: dict[str, list[tuple[float, float]]] = {}
    xs: list[float] = []
    ys: list[float] = []

    for entity in msp:
        dtype = entity.dxftype()
        if dtype not in ("TEXT", "MTEXT"):
            continue
        try:
            raw = entity.dxf.text
            text = _clean_mtext(raw) if dtype == "MTEXT" else raw.strip()
            sym = match_symbol(text, wl, exclude_with_spec=exclude_with_spec)
            if sym is None:
                continue
            if not _height_ok(entity, dtype, min_text_height):
                continue
            pt = entity.dxf.insert
            x, y = float(pt.x), float(pt.y)
        except Exception:
            continue
        coords.setdefault(sym, []).append((x, y))
        xs.append(x)
        ys.append(y)

    extent = _drawing_extent(doc, xs, ys)
    return coords, extent


def _drawing_extent(
    doc, xs: list[float], ys: list[float]
) -> tuple[float, float, float, float]:
    """DXF 헤더 $EXTMIN/$EXTMAX 를 우선 쓰고, 없으면 텍스트 좌표로 대체한다."""
    try:
        emin = doc.header["$EXTMIN"]
        emax = doc.header["$EXTMAX"]
        xmin, ymin = float(emin[0]), float(emin[1])
        xmax, ymax = float(emax[0]), float(emax[1])
        if xmax > xmin and ymax > ymin:
            return (xmin, ymin, xmax, ymax)
    except Exception:
        pass
    if xs and ys:
        return (min(xs), min(ys), max(xs), max(ys))
    return (0.0, 0.0, 0.0, 0.0)


def detect_table_regions(
    coords_by_symbol: dict[str, list[tuple[float, float]]],
    drawing_extent: tuple[float, float, float, float],
    region_size_ratio: float = 1 / 30,
    min_distinct_symbols: int = 4,
    max_count_per_symbol: int = 2,
) -> list[dict]:
    """일람표 후보 영역 검출.

    알고리즘:
      1. 부호 좌표를 그리드 셀(셀 크기 = 도면 폭 × region_size_ratio)로 분할.
      2. 점이 있는 셀을 8방향 인접으로 묶어 연결 영역(connected component)을
         만든다 — 일람표가 셀 경계에 걸쳐도 한 영역으로 합쳐진다.
      3. 각 영역에서 '서로 다른 부호 수'와 '부호당 최다 등장 수'를 계산.
         서로 다른 부호 >= min_distinct_symbols AND
         부호당 최다 등장 <= max_count_per_symbol  → 일람표 후보.

    부재 밀집 영역은 같은 부호가 수십 번 나와 max_count 조건에서 탈락한다.

    Returns
    -------
    [{"bbox": (xmin, ymin, xmax, ymax),
      "symbols": {"SC1": 2, "SC2": 2, ...}}, ...]
    """
    xmin, ymin, xmax, ymax = drawing_extent
    width = xmax - xmin
    cell = width * region_size_ratio
    if cell <= 0:
        return []

    # 1. 점 → 그리드 셀
    cell_points: dict[tuple[int, int], list[tuple[str, float, float]]] = defaultdict(
        list
    )
    for symbol, points in coords_by_symbol.items():
        for x, y in points:
            ci = int((x - xmin) // cell)
            cj = int((y - ymin) // cell)
            cell_points[(ci, cj)].append((symbol, x, y))

    # 2. 점이 있는 셀을 8방향 인접으로 연결 영역으로 묶기
    seen: set[tuple[int, int]] = set()
    components: list[list[tuple[str, float, float]]] = []
    for start in list(cell_points):
        if start in seen:
            continue
        seen.add(start)
        stack = [start]
        cells: list[tuple[int, int]] = []
        while stack:
            ci, cj = stack.pop()
            cells.append((ci, cj))
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    neighbor = (ci + di, cj + dj)
                    if neighbor in cell_points and neighbor not in seen:
                        seen.add(neighbor)
                        stack.append(neighbor)
        components.append([p for c in cells for p in cell_points[c]])

    # 3. 영역별 일람표 조건 판정
    regions: list[dict] = []
    for pts in components:
        sym_count = Counter(symbol for symbol, _, _ in pts)
        if len(sym_count) < min_distinct_symbols:
            continue
        if max(sym_count.values()) > max_count_per_symbol:
            continue
        xs = [x for _, x, _ in pts]
        ys = [y for _, _, y in pts]
        regions.append(
            {
                "bbox": (min(xs), min(ys), max(xs), max(ys)),
                "symbols": dict(sym_count),
            }
        )
    return regions
