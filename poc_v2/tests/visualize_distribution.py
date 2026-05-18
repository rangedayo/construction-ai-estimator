"""작업 5 — 부호 분포 영역 시각화 (Plotly HTML, 도면1 전용).

두 개의 HTML 을 outputs/ 에 생성한다.

1. 도면1_distribution.html
   모든 철골 부호 텍스트의 (x, y) 위치 산점도.
   - 부호별 다른 색상, 토글 가능한 레전드
   - 마커 크기 = 텍스트 height (큰 글자는 크게)
   - hover: 부호명·높이·원본 텍스트

2. 도면1_heights.html
   X축 = 부호명, Y축 = height 산점도.
   - 점 크기 = (부호, height) 버킷 개수
   - 임계값 후보를 가로선으로 표시

사용법:  poc_v2 디렉토리에서  `python tests/visualize_distribution.py`
"""
from __future__ import annotations

import os
import sys
from collections import Counter

import plotly.graph_objects as go
import plotly.express as px

_HERE = os.path.dirname(os.path.abspath(__file__))
_POC_DIR = os.path.dirname(_HERE)
for _path in (_POC_DIR, _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from ground_truth import PROJECT_ROOT, drawing_symbol_totals  # noqa: E402
from symbol_extract import Occurrence, extract_occurrences  # noqa: E402

_DRAWING = "도면1"
_DXF = os.path.join(PROJECT_ROOT, "sample_data", "도면1.dxf")
_OUT_DIR = os.path.join(PROJECT_ROOT, "outputs")

# 마커 크기 범위 — height 를 이 픽셀 범위로 선형 매핑
_MARKER_MIN, _MARKER_MAX = 6.0, 26.0
_PALETTE = px.colors.qualitative.Dark24


def _scale_sizes(heights: list[float]) -> list[float]:
    """height 리스트를 마커 픽셀 크기 범위로 선형 정규화한다."""
    if not heights:
        return []
    lo, hi = min(heights), max(heights)
    if hi == lo:
        return [(_MARKER_MIN + _MARKER_MAX) / 2] * len(heights)
    span = hi - lo
    return [
        _MARKER_MIN + (h - lo) / span * (_MARKER_MAX - _MARKER_MIN)
        for h in heights
    ]


def _build_distribution(
    by_symbol: dict[str, list[Occurrence]],
) -> go.Figure:
    """부호별 (x, y) 위치 산점도 — 마커 크기 = height."""
    fig = go.Figure()
    for idx, symbol in enumerate(sorted(by_symbol)):
        occ = by_symbol[symbol]
        color = _PALETTE[idx % len(_PALETTE)]
        fig.add_trace(go.Scatter(
            x=[o.x for o in occ],
            y=[o.y for o in occ],
            mode="markers",
            name=f"{symbol} ({len(occ)})",
            legendgroup=symbol,
            marker=dict(
                size=_scale_sizes([o.height for o in occ]),
                color=color,
                line=dict(width=0.5, color="#333333"),
                opacity=0.8,
            ),
            customdata=[(o.symbol, round(o.height), o.raw) for o in occ],
            hovertemplate=(
                "%{customdata[0]}  (height %{customdata[1]})<br>"
                "원본: %{customdata[2]}<br>"
                "(%{x:.0f}, %{y:.0f})<extra></extra>"
            ),
        ))
    fig.update_layout(
        title=f"{_DRAWING} 철골 부호 분포 — 마커 크기 = 텍스트 height",
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis=dict(showgrid=True, gridcolor="#eeeeee", zeroline=False),
        yaxis=dict(
            showgrid=True, gridcolor="#eeeeee", zeroline=False,
            scaleanchor="x", scaleratio=1,
        ),
        legend=dict(title="부호 (클릭=토글)", bgcolor="rgba(255,255,255,0.9)"),
        height=900,
        dragmode="pan",
    )
    return fig


def _build_heights(
    by_symbol: dict[str, list[Occurrence]],
) -> go.Figure:
    """X = 부호명, Y = height 산점도 — 점 크기 = 버킷 개수."""
    fig = go.Figure()

    all_heights: list[int] = []
    for idx, symbol in enumerate(sorted(by_symbol)):
        occ = by_symbol[symbol]
        bucket = Counter(round(o.height) for o in occ)
        all_heights.extend(bucket.elements())
        heights = sorted(bucket)
        counts = [bucket[h] for h in heights]
        fig.add_trace(go.Scatter(
            x=[symbol] * len(heights),
            y=heights,
            mode="markers",
            name=symbol,
            legendgroup=symbol,
            marker=dict(
                size=[8 + c * 2 for c in counts],
                color=_PALETTE[idx % len(_PALETTE)],
                line=dict(width=0.5, color="#333333"),
                opacity=0.85,
            ),
            customdata=counts,
            hovertemplate=(
                f"{symbol}<br>height %{{y}}<br>"
                "개수 %{customdata}<extra></extra>"
            ),
        ))

    # 임계값 후보 가로선 — 도면 전체에서 가장 빈번한 height 상위 3개
    candidates = [h for h, _ in Counter(all_heights).most_common(3)]
    for h in candidates:
        fig.add_hline(
            y=h,
            line=dict(color="#cc0000", width=1, dash="dash"),
            annotation_text=f"임계값 후보 height={h}",
            annotation_position="right",
        )

    fig.update_layout(
        title=f"{_DRAWING} 부호별 텍스트 height 분포 (점 크기 = 개수)",
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis=dict(title="부호", showgrid=False),
        yaxis=dict(title="텍스트 height", showgrid=True, gridcolor="#eeeeee"),
        showlegend=False,
        height=700,
    )
    return fig


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    symbols = sorted(drawing_symbol_totals()[_DRAWING].keys())
    occurrences = extract_occurrences(_DXF, symbols)

    by_symbol: dict[str, list[Occurrence]] = {}
    for occ in occurrences:
        by_symbol.setdefault(occ.symbol, []).append(occ)

    os.makedirs(_OUT_DIR, exist_ok=True)

    dist_path = os.path.join(_OUT_DIR, f"{_DRAWING}_distribution.html")
    _build_distribution(by_symbol).write_html(dist_path, include_plotlyjs="cdn")
    print(f"[저장] {dist_path}")

    heights_path = os.path.join(_OUT_DIR, f"{_DRAWING}_heights.html")
    _build_heights(by_symbol).write_html(heights_path, include_plotlyjs="cdn")
    print(f"[저장] {heights_path}")

    print(f"\n총 출현 {len(occurrences)}회 / 부호 {len(by_symbol)}종")
    print("브라우저에서 두 HTML 을 열어 분포를 확인하세요.")


if __name__ == "__main__":
    main()
