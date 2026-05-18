"""작업 6 — 부호 밀집 영역 진단 (도면1 전용, 진단만).

같은 부호가 좁은 영역에 여러 번 모인 곳, 그리고 서로 다른 부호가 좁은
영역에 모인 곳(일람표 후보)을 단순 거리 기준으로 검출한다.

군집화는 단순 single-linkage(반경 내 연결) 방식만 쓴다 — DBSCAN 등 외부
군집화 도구는 쓰지 않는다(라운드 2 주의사항).

출력:
  - 콘솔: 발견된 밀집 영역 bbox 리스트
  - outputs/도면1_density.html: 작업 5 분포 시각화 위에 밀집 영역 사각형 오버레이

사용법:  poc_v2 디렉토리에서  `python tests/analyze_density.py`
"""
from __future__ import annotations

import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_POC_DIR = os.path.dirname(_HERE)
for _path in (_POC_DIR, _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from ground_truth import PROJECT_ROOT, drawing_symbol_totals  # noqa: E402
from symbol_extract import Occurrence, extract_occurrences  # noqa: E402
from visualize_distribution import _build_distribution  # noqa: E402

_DRAWING = "도면1"
_DXF = os.path.join(PROJECT_ROOT, "sample_data", "도면1.dxf")
_OUT_DIR = os.path.join(PROJECT_ROOT, "outputs")

# 군집 반경 — 도면 대각선 길이의 비율로 설정(임의 시작값, 결과 보고 라운드3에서 조정)
_RADIUS_FRACTION = 0.04
# 같은 부호 밀집으로 볼 최소 출현 수
_SAME_SYMBOL_MIN = 6
# 일람표 후보로 볼 최소 '서로 다른 부호' 종 수
_MIXED_SYMBOL_MIN = 5


def _diagonal(points: list[tuple[float, float]]) -> float:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return math.hypot(max(xs) - min(xs), max(ys) - min(ys))


def cluster_by_radius(
    points: list[tuple[float, float]],
    radius: float,
) -> list[list[int]]:
    """반경 내 연결(single-linkage) 군집화 — 점 인덱스 군집 리스트 반환.

    단순 거리 기준만 쓴다. n 이 수백 규모라 O(n^2) 로도 충분히 빠르다.
    """
    unvisited = list(range(len(points)))
    clusters: list[list[int]] = []
    r2 = radius * radius

    while unvisited:
        cluster = [unvisited.pop(0)]
        changed = True
        while changed:
            changed = False
            for i in list(unvisited):
                xi, yi = points[i]
                for c in cluster:
                    xc, yc = points[c]
                    if (xi - xc) ** 2 + (yi - yc) ** 2 <= r2:
                        cluster.append(i)
                        unvisited.remove(i)
                        changed = True
                        break
        clusters.append(cluster)
    return clusters


def _bbox(occ: list[Occurrence]) -> tuple[float, float, float, float]:
    xs = [o.x for o in occ]
    ys = [o.y for o in occ]
    return min(xs), min(ys), max(xs), max(ys)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    symbols = sorted(drawing_symbol_totals()[_DRAWING].keys())
    occurrences = extract_occurrences(_DXF, symbols)
    if not occurrences:
        print("[오류] 출현 데이터 없음")
        return

    all_pts = [(o.x, o.y) for o in occurrences]
    radius = _diagonal(all_pts) * _RADIUS_FRACTION

    print("=" * 64)
    print(f" 작업 6 — 부호 밀집 영역 진단  ({_DRAWING})")
    print(f" 군집 반경 = 도면 대각선 × {_RADIUS_FRACTION}  ≈ {radius:.0f}")
    print("=" * 64)

    by_symbol: dict[str, list[Occurrence]] = {}
    for occ in occurrences:
        by_symbol.setdefault(occ.symbol, []).append(occ)

    # ── 1) 같은 부호 밀집 영역 ────────────────────────────────────────────────
    same_regions: list[tuple[str, int, tuple]] = []
    for symbol in sorted(by_symbol):
        occ = by_symbol[symbol]
        pts = [(o.x, o.y) for o in occ]
        for cluster in cluster_by_radius(pts, radius):
            if len(cluster) >= _SAME_SYMBOL_MIN:
                members = [occ[i] for i in cluster]
                same_regions.append((symbol, len(cluster), _bbox(members)))

    print(f"\n[1] 같은 부호 밀집 영역 (출현 >= {_SAME_SYMBOL_MIN})")
    if same_regions:
        for symbol, n, bb in sorted(same_regions, key=lambda r: -r[1]):
            print(
                f"  {symbol:<6} {n:>3}회  "
                f"bbox=({bb[0]:.0f}, {bb[1]:.0f})~({bb[2]:.0f}, {bb[3]:.0f})"
            )
    else:
        print("  (없음)")

    # ── 2) 서로 다른 부호 밀집 영역 (일람표 후보) ─────────────────────────────
    mixed_clusters = cluster_by_radius(all_pts, radius)
    mixed_regions: list[tuple[int, int, set, tuple]] = []
    for cluster in mixed_clusters:
        members = [occurrences[i] for i in cluster]
        distinct = {m.symbol for m in members}
        if len(distinct) >= _MIXED_SYMBOL_MIN:
            mixed_regions.append((len(members), len(distinct), distinct, _bbox(members)))

    print(f"\n[2] 서로 다른 부호 밀집 영역 — 일람표 후보 (부호종 >= {_MIXED_SYMBOL_MIN})")
    if mixed_regions:
        for n, n_distinct, distinct, bb in sorted(mixed_regions, key=lambda r: -r[1]):
            print(
                f"  {n_distinct}종 / {n}회  "
                f"bbox=({bb[0]:.0f}, {bb[1]:.0f})~({bb[2]:.0f}, {bb[3]:.0f})"
            )
            print(f"     부호: {', '.join(sorted(distinct))}")
    else:
        print("  (없음)")

    # ── 3) Plotly HTML — 분포 시각화 + 밀집 영역 사각형 오버레이 ──────────────
    os.makedirs(_OUT_DIR, exist_ok=True)
    fig = _build_distribution(by_symbol)

    for symbol, _n, bb in same_regions:
        fig.add_shape(
            type="rect", x0=bb[0], y0=bb[1], x1=bb[2], y1=bb[3],
            line=dict(color="#1f77b4", width=1.5, dash="dot"),
            fillcolor="rgba(31,119,180,0.05)", layer="below",
        )
    for _n, _nd, _distinct, bb in mixed_regions:
        fig.add_shape(
            type="rect", x0=bb[0], y0=bb[1], x1=bb[2], y1=bb[3],
            line=dict(color="#cc0000", width=2),
            fillcolor="rgba(204,0,0,0.06)", layer="below",
        )
    fig.update_layout(
        title=f"{_DRAWING} 밀집 영역 — 파란 점선=같은 부호 밀집, 빨강=일람표 후보"
    )

    out_path = os.path.join(_OUT_DIR, f"{_DRAWING}_density.html")
    fig.write_html(out_path, include_plotlyjs="cdn")
    print(f"\n[저장] {out_path}")
    print("\n진단 종료 — 밀집/일람표 후보 좌표는 라운드 3 영역 제외 정책 입력용")


if __name__ == "__main__":
    main()
