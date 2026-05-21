"""분류 시각화 도구 (라운드 10) — DXF 기하 + 분류별 마커 오버레이 HTML.

poc_v3/app.py 의 parse_dxf_for_plotly + build_dxf_figure 를 베이스로 확장.
Streamlit 의존성 제거, ezdxf + plotly 만 사용. 도면 5장 모두 standalone
HTML 로 출력 (브라우저에서 바로 열림).

사용법:
    python poc_v2/tests/visualize_detection.py            # 5개 도면 전부
    python poc_v2/tests/visualize_detection.py 도면3      # 한 도면만

출력:
    outputs/visualize/도면N_detection.html  × 5
"""
from __future__ import annotations

import math
import os
import sys
from collections import Counter

import ezdxf
import plotly.graph_objects as go

_HERE = os.path.dirname(os.path.abspath(__file__))
_POC_DIR = os.path.dirname(_HERE)
for _path in (_POC_DIR, _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from baseline import compute_drawing, _dxf_path  # noqa: E402
from classify_text import classify_drawing_texts  # noqa: E402
from counter import _clean_mtext  # noqa: E402
from ground_truth import PROJECT_ROOT, within_tolerance  # noqa: E402

_ARC_N = 48
_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "outputs", "visualize")
_ALL_DRAWINGS = ("도면1", "도면2", "도면3", "도면4", "도면5")

# 분류별 마커 스타일 (라운드 10 사양표)
_CATEGORY_STYLE: dict[str, dict] = {
    "counted": {
        "label": "counted (본체 카운트)",
        "marker": "circle-open",
        "color": "green",
        "size": 14,
        "line_width": 2.5,
    },
    "slash_combo_body": {
        "label": "slash_combo_body (슬래시 결합 본체)",
        "marker": "circle",
        "color": "darkgreen",
        "size": 14,
        "line_width": 0,
    },
    "filtered_height": {
        "label": "filtered_height (height 필터 제외)",
        "marker": "x",
        "color": "gray",
        "size": 10,
        "line_width": 1,
    },
    "filtered_spec": {
        "label": "filtered_spec (규격 안내 제외)",
        "marker": "x",
        "color": "gold",
        "size": 10,
        "line_width": 1,
    },
    "filtered_table": {
        "label": "filtered_table (일람표 영역 제외)",
        "marker": "x",
        "color": "red",
        "size": 12,
        "line_width": 1.5,
    },
}
_CATEGORY_ORDER = (
    "counted",
    "slash_combo_body",
    "filtered_height",
    "filtered_spec",
    "filtered_table",
)


def parse_dxf_geometry(dxf_path: str) -> dict:
    """LINE/LWPOLYLINE/POLYLINE/ARC/CIRCLE + 작은 텍스트 라벨 추출.

    poc_v3.parse_dxf_for_plotly 와 동일 로직이지만 Streamlit 캐시 의존 제거.
    """
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    line_x: list = []
    line_y: list = []
    arc_x: list = []
    arc_y: list = []
    text_x: list = []
    text_y: list = []
    text_labels: list = []

    for entity in msp:
        dtype = entity.dxftype()

        if dtype == "LINE":
            try:
                s, e = entity.dxf.start, entity.dxf.end
                line_x += [s.x, e.x, None]
                line_y += [s.y, e.y, None]
            except Exception:
                pass

        elif dtype == "LWPOLYLINE":
            try:
                pts = [(p[0], p[1]) for p in entity.get_points()]
                if not pts:
                    continue
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                if entity.closed:
                    xs.append(xs[0])
                    ys.append(ys[0])
                line_x += xs + [None]
                line_y += ys + [None]
            except Exception:
                pass

        elif dtype == "POLYLINE":
            try:
                verts = list(entity.vertices)
                if not verts:
                    continue
                xs = [v.dxf.location.x for v in verts]
                ys = [v.dxf.location.y for v in verts]
                if entity.is_closed:
                    xs.append(xs[0])
                    ys.append(ys[0])
                line_x += xs + [None]
                line_y += ys + [None]
            except Exception:
                pass

        elif dtype == "ARC":
            try:
                cx, cy = entity.dxf.center.x, entity.dxf.center.y
                r = entity.dxf.radius
                a0 = math.radians(entity.dxf.start_angle)
                a1 = math.radians(entity.dxf.end_angle)
                if a1 <= a0:
                    a1 += 2 * math.pi
                angles = [a0 + (a1 - a0) * i / _ARC_N for i in range(_ARC_N + 1)]
                arc_x += [cx + r * math.cos(a) for a in angles] + [None]
                arc_y += [cy + r * math.sin(a) for a in angles] + [None]
            except Exception:
                pass

        elif dtype == "CIRCLE":
            try:
                cx, cy = entity.dxf.center.x, entity.dxf.center.y
                r = entity.dxf.radius
                angles = [2 * math.pi * i / _ARC_N for i in range(_ARC_N + 1)]
                arc_x += [cx + r * math.cos(a) for a in angles] + [None]
                arc_y += [cy + r * math.sin(a) for a in angles] + [None]
            except Exception:
                pass

        elif dtype in ("TEXT", "MTEXT"):
            try:
                pt = entity.dxf.insert
                raw = entity.dxf.text
                label = _clean_mtext(raw) if dtype == "MTEXT" else raw.strip()
                if label:
                    text_x.append(pt.x)
                    text_y.append(pt.y)
                    text_labels.append(label)
            except Exception:
                pass

    return {
        "line_x": line_x,
        "line_y": line_y,
        "arc_x": arc_x,
        "arc_y": arc_y,
        "text_x": text_x,
        "text_y": text_y,
        "text_labels": text_labels,
    }


def _add_geometry(fig: go.Figure, geo: dict) -> None:
    """도면 기하·작은 텍스트 라벨을 회색으로 깔아준다."""
    geo_color = "#505050"
    text_color = "#a0a0a0"

    if geo["line_x"]:
        fig.add_trace(go.Scatter(
            x=geo["line_x"], y=geo["line_y"], mode="lines",
            line=dict(color=geo_color, width=0.8),
            hoverinfo="skip", showlegend=False, name="_lines",
        ))
    if geo["arc_x"]:
        fig.add_trace(go.Scatter(
            x=geo["arc_x"], y=geo["arc_y"], mode="lines",
            line=dict(color=geo_color, width=0.8),
            hoverinfo="skip", showlegend=False, name="_arcs",
        ))
    if geo["text_x"]:
        fig.add_trace(go.Scatter(
            x=geo["text_x"], y=geo["text_y"], mode="text",
            text=geo["text_labels"],
            textfont=dict(size=7, color=text_color),
            hovertemplate="%{text}<extra></extra>",
            showlegend=False, name="_text",
        ))


def _add_category_markers(fig: go.Figure, classified: list[dict]) -> None:
    """분류별로 마커 트레이스 한 개씩 추가 (legend = 분류명)."""
    by_category: dict[str, list[dict]] = {c: [] for c in _CATEGORY_ORDER}
    for record in classified:
        cat = record["category"]
        if cat in by_category:
            by_category[cat].append(record)

    for cat in _CATEGORY_ORDER:
        points = by_category[cat]
        if not points:
            continue
        style = _CATEGORY_STYLE[cat]
        fig.add_trace(go.Scatter(
            x=[p["x"] for p in points],
            y=[p["y"] for p in points],
            mode="markers",
            name=f"{style['label']} — {len(points)}개",
            marker=dict(
                symbol=style["marker"],
                size=style["size"],
                color=style["color"],
                line=dict(color=style["color"], width=style["line_width"]),
            ),
            customdata=[
                [p["text"], p["symbol"] or "-", p["source"],
                 f"{p['height']:.1f}" if p["height"] is not None else "-"]
                for p in points
            ],
            hovertemplate=(
                "text: %{customdata[0]}<br>"
                "symbol: %{customdata[1]}<br>"
                "source: %{customdata[2]}<br>"
                "height: %{customdata[3]}<br>"
                "(x, y) = (%{x:.1f}, %{y:.1f})<extra>" + cat + "</extra>"
            ),
        ))


def _add_region_boxes(fig: go.Figure, regions: list[dict]) -> None:
    """일람표 영역 bbox 를 빨간 점선 사각형 + 라벨로 표시."""
    for i, region in enumerate(regions):
        x0, y0, x1, y1 = region["bbox"]
        fig.add_shape(
            type="rect",
            x0=x0, y0=y0, x1=x1, y1=y1,
            line=dict(color="red", width=2, dash="dot"),
            fillcolor="rgba(255, 0, 0, 0.05)",
            layer="below",
        )
        syms = ", ".join(
            f"{s}({n})" for s, n in sorted(region["symbols"].items())
        )
        fig.add_annotation(
            x=x0, y=y1,
            xanchor="left", yanchor="bottom",
            text=f"<b>Region {i}</b>: {syms}",
            font=dict(color="red", size=11),
            showarrow=False,
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="red",
            borderwidth=1,
        )


def _build_summary_text(drawing: str, result: dict) -> str:
    """플롯 모서리에 표시할 정답 비교 박스 텍스트 (HTML)."""
    policy = result["policy"]
    expected = result["expected"]
    final = result["final"]
    source = result["policy_source"]

    header = (
        f"<b>{drawing}</b> — policy[{source}]: "
        f"exclude_table={policy['exclude_table_regions']}, "
        f"exclude_with_spec={policy['exclude_with_spec']}"
    )
    rows = ["<span style='font-family:monospace'>",
            f"{'부호':<6}{'예측':>6}{'정답':>6}{'차이':>6}  상태"]
    for symbol in sorted(expected):
        pred = final.get(symbol, 0)
        exp = expected[symbol]
        diff = pred - exp
        ok = within_tolerance(pred, exp)
        rows.append(
            f"{symbol:<6}{pred:>6}{exp:>6}{diff:>+6}  {'PASS' if ok else 'FAIL'}"
        )
    rows.append("</span>")
    return header + "<br>" + "<br>".join(rows)


def _add_summary_annotation(fig: go.Figure, drawing: str, result: dict) -> None:
    """플롯 좌상단에 카운트 비교 박스 표시."""
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.005, y=0.995,
        xanchor="left", yanchor="top",
        text=_build_summary_text(drawing, result),
        font=dict(size=11, color="#202020"),
        showarrow=False,
        align="left",
        bgcolor="rgba(255,255,255,0.92)",
        bordercolor="#606060",
        borderwidth=1,
    )


def _build_figure(drawing: str) -> go.Figure:
    """도면 한 장의 시각화 Figure 조립."""
    dxf = _dxf_path(drawing)
    geo = parse_dxf_geometry(dxf)
    result = compute_drawing(drawing)
    classified = classify_drawing_texts(drawing)

    fig = go.Figure()
    _add_geometry(fig, geo)
    _add_region_boxes(fig, result["regions"])
    _add_category_markers(fig, classified)
    _add_summary_annotation(fig, drawing, result)

    fig.update_layout(
        title=f"{drawing} — 분류 시각화 (라운드 10)",
        height=900,
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=10, r=10, t=50, b=10),
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=False, zeroline=False, scaleanchor="x", scaleratio=1),
        legend=dict(
            orientation="v",
            yanchor="top", y=0.99,
            xanchor="right", x=0.999,
            bgcolor="rgba(255,255,255,0.92)",
            bordercolor="#606060",
            borderwidth=1,
        ),
        dragmode="pan",
    )
    return fig


def visualize_drawing(drawing: str, out_dir: str = _OUTPUT_DIR) -> str:
    """한 도면을 standalone HTML 로 저장하고 경로 반환."""
    os.makedirs(out_dir, exist_ok=True)
    fig = _build_figure(drawing)
    out_path = os.path.join(out_dir, f"{drawing}_detection.html")
    fig.write_html(
        out_path,
        include_plotlyjs="cdn",
        config={
            "scrollZoom": True,
            "displayModeBar": True,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
        },
    )
    return out_path


def category_counts(drawing: str) -> Counter:
    """리포트용 — 도면별 분류 카운트 요약."""
    classified = classify_drawing_texts(drawing)
    return Counter(r["category"] for r in classified)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) > 1:
        targets = [sys.argv[1]]
    else:
        targets = list(_ALL_DRAWINGS)

    for drawing in targets:
        if drawing not in _ALL_DRAWINGS:
            print(f"[오류] 알 수 없는 도면: {drawing}  (사용 가능: {list(_ALL_DRAWINGS)})")
            sys.exit(1)
        out = visualize_drawing(drawing)
        rel = os.path.relpath(out, PROJECT_ROOT).replace("\\", "/")
        counts = category_counts(drawing)
        summary = ", ".join(
            f"{c}={counts.get(c, 0)}" for c in _CATEGORY_ORDER
        )
        print(f"{rel} 생성  ({summary})")


if __name__ == "__main__":
    main()
