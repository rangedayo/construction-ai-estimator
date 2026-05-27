"""부호↔규격 페어링 시각화 — 라운드 길이-4.

`spec_extractor.extract_specs` 결과를 도면 기하 위에 오버레이한다.

CLI
    python -m poc_v2.length.visualize_specs            # 도면1~5 전체
    python -m poc_v2.length.visualize_specs 도면3      # 도면3만
    python -m poc_v2.length.visualize_specs --no-open  # 자동 오픈 비활성화
"""
from __future__ import annotations

import math
import os
import sys
import webbrowser

import ezdxf
import plotly.graph_objects as go

_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from poc_v2.length.spec_extractor import (  # noqa: E402
    SpecExtraction,
    _SECTION_RE,
    extract_specs,
)

_ALL_DRAWINGS = ("도면1", "도면2", "도면3", "도면4", "도면5")
_DXF_DIR = os.path.join(PROJECT_ROOT, "sample_data")
_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "outputs", "visualize")
_ARC_N = 24


def _parse_geometry(dxf_path: str) -> tuple[list, list, list, list]:
    """LINE/POLY/ARC/CIRCLE → 회색 도면 골격."""
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    line_x: list = []
    line_y: list = []
    arc_x: list = []
    arc_y: list = []

    for entity in msp:
        dtype = entity.dxftype()
        try:
            if dtype == "LINE":
                s, e = entity.dxf.start, entity.dxf.end
                line_x += [s.x, e.x, None]
                line_y += [s.y, e.y, None]
            elif dtype == "LWPOLYLINE":
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
            elif dtype == "ARC":
                cx, cy = entity.dxf.center.x, entity.dxf.center.y
                r = entity.dxf.radius
                a0 = math.radians(entity.dxf.start_angle)
                a1 = math.radians(entity.dxf.end_angle)
                if a1 <= a0:
                    a1 += 2 * math.pi
                angles = [a0 + (a1 - a0) * i / _ARC_N for i in range(_ARC_N + 1)]
                arc_x += [cx + r * math.cos(a) for a in angles] + [None]
                arc_y += [cy + r * math.sin(a) for a in angles] + [None]
            elif dtype == "CIRCLE":
                cx, cy = entity.dxf.center.x, entity.dxf.center.y
                r = entity.dxf.radius
                angles = [2 * math.pi * i / _ARC_N for i in range(_ARC_N + 1)]
                arc_x += [cx + r * math.cos(a) for a in angles] + [None]
                arc_y += [cy + r * math.sin(a) for a in angles] + [None]
        except Exception:  # noqa: BLE001
            continue
    return line_x, line_y, arc_x, arc_y


def _collect_section_labels(dxf_path: str) -> list[tuple[float, float, str]]:
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    out: list[tuple[float, float, str]] = []
    for entity in msp:
        if entity.dxftype() not in ("TEXT", "MTEXT"):
            continue
        try:
            raw = entity.dxf.text if entity.dxftype() == "TEXT" else entity.text
            label = raw.strip()
            if _SECTION_RE.search(label):
                pt = entity.dxf.insert
                out.append((float(pt.x), float(pt.y), label))
        except Exception:  # noqa: BLE001
            continue
    return out


def _build_figure(
    drawing: str,
    dxf_path: str,
    extractions: list[SpecExtraction],
) -> go.Figure:
    line_x, line_y, arc_x, arc_y = _parse_geometry(dxf_path)
    sections = _collect_section_labels(dxf_path)

    fig = go.Figure()
    if line_x:
        fig.add_trace(go.Scatter(
            x=line_x, y=line_y, mode="lines",
            line=dict(color="#505050", width=0.7),
            hoverinfo="skip", showlegend=False, name="_geometry",
        ))
    if arc_x:
        fig.add_trace(go.Scatter(
            x=arc_x, y=arc_y, mode="lines",
            line=dict(color="#505050", width=0.7),
            hoverinfo="skip", showlegend=False, name="_arcs",
        ))
    if sections:
        fig.add_trace(go.Scatter(
            x=[s[0] for s in sections],
            y=[s[1] for s in sections],
            mode="text",
            text=[s[2] for s in sections],
            textfont=dict(size=10, color="#8b4fbf"),
            hoverinfo="text",
            showlegend=False, name="_sections",
        ))

    if extractions:
        fig.add_trace(go.Scatter(
            x=[ex.symbol_coord[0] for ex in extractions],
            y=[ex.symbol_coord[1] for ex in extractions],
            mode="markers+text",
            marker=dict(symbol="circle", color="#2ca02c", size=10,
                        line=dict(color="#0a4a0a", width=1)),
            text=[f"{ex.symbol}<br>({ex.section or '-'})" for ex in extractions],
            textposition="top center",
            textfont=dict(size=9, color="#0a4a0a"),
            hovertext=[
                f"{ex.drawing} / {ex.section or '-'} / {ex.symbol}<br>"
                f"규격: {ex.spec_normalized}" for ex in extractions
            ],
            hoverinfo="text",
            name="부호", legendgroup="symbol",
        ))
        fig.add_trace(go.Scatter(
            x=[ex.spec_coord[0] for ex in extractions],
            y=[ex.spec_coord[1] for ex in extractions],
            mode="markers+text",
            marker=dict(symbol="square", color="#1f77b4", size=8,
                        line=dict(color="#0a3060", width=1)),
            text=[ex.spec_raw for ex in extractions],
            textposition="bottom center",
            textfont=dict(size=8, color="#0a3060"),
            hoverinfo="text",
            name="규격", legendgroup="spec",
        ))
        pair_x: list = []
        pair_y: list = []
        for ex in extractions:
            pair_x += [ex.symbol_coord[0], ex.spec_coord[0], None]
            pair_y += [ex.symbol_coord[1], ex.spec_coord[1], None]
        fig.add_trace(go.Scatter(
            x=pair_x, y=pair_y, mode="lines",
            line=dict(color="#888", width=1, dash="dot"),
            hoverinfo="skip", showlegend=False, name="_pair",
        ))

    fig.update_layout(
        title=f"{drawing} — 부호↔규격 페어링 (n={len(extractions)})",
        xaxis=dict(scaleanchor="y", scaleratio=1.0, showgrid=False, zeroline=False),
        yaxis=dict(showgrid=False, zeroline=False),
        paper_bgcolor="white", plot_bgcolor="white",
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


def visualize(drawing: str, open_browser: bool = False) -> str:
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    dxf_path = os.path.join(_DXF_DIR, f"{drawing}.dxf")
    extractions = extract_specs(dxf_path, drawing)
    fig = _build_figure(drawing, dxf_path, extractions)
    out_path = os.path.join(_OUTPUT_DIR, f"{drawing}_specs_기둥.html")
    fig.write_html(out_path, include_plotlyjs="cdn")
    if open_browser:
        webbrowser.open("file://" + out_path)
    return out_path


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    open_first = "--no-open" not in sys.argv[1:]
    targets = args if args else list(_ALL_DRAWINGS)
    paths: list[str] = []
    for drawing in targets:
        path = visualize(drawing, open_browser=False)
        paths.append(path)
        print(f"  {drawing} → {path}")
    if open_first and paths:
        webbrowser.open("file://" + paths[0])


if __name__ == "__main__":
    main()
