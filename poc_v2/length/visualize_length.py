"""기둥 길이 측정 시각화 — 라운드 길이-1.

1단계 `poc_v2/tests/visualize_detection.py` 패턴을 따라하되, 마커 분류 대신
DIMENSION 오버레이 + 채택값 강조 + 정답 비교 박스를 표시한다.

분류·색상:
    chosen        — 빨강, 굵기 4    (채택된 세로 DIM)
    other_vertical — 주황, 굵기 2   (다른 세로 DIM)
    horizontal    — 파랑, 굵기 2    (가로 DIM)
    diagonal      — 회색, 굵기 1    (대각 DIM)

CLI
    python -m poc_v2.length.visualize_length            # 5개 도면 전체 + 첫 HTML 오픈
    python -m poc_v2.length.visualize_length 도면3      # 도면3만
    python -m poc_v2.length.visualize_length --no-open  # 자동 오픈 비활성화
"""
from __future__ import annotations

import math
import os
import sys
import webbrowser

import ezdxf
import plotly.graph_objects as go

# 프로젝트 루트를 sys.path 에 추가 — `from poc_v2.length import …` 보장
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from poc_v2.length.baseline_length import (  # noqa: E402
    DrawingMeasurement,
    measure_drawing,
    within_length_tolerance,
)
from poc_v2.length.ground_truth_length import PROJECT_ROOT  # noqa: E402
from poc_v2.length.measure import DimensionInfo, MeasurementResult  # noqa: E402
from poc_v2.length.routing import load_routing, resolve_source_path  # noqa: E402

_ARC_N = 48
_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "outputs", "visualize")
_ALL_DRAWINGS = ("도면1", "도면2", "도면3", "도면4", "도면5")

_COLOR = {
    "chosen": "#d62728",
    "other_vertical": "#ff7f0e",
    "horizontal": "#1f77b4",
    "diagonal": "#7f7f7f",
}
_WIDTH = {
    "chosen": 4.0,
    "other_vertical": 2.0,
    "horizontal": 2.0,
    "diagonal": 1.0,
}


def _parse_dxf_geometry(dxf_path: str) -> dict:
    """LINE/LWPOLYLINE/POLYLINE/ARC/CIRCLE + 작은 텍스트 라벨을 추출.

    `poc_v2/tests/visualize_detection.py:parse_dxf_geometry` 와 같은 형태.
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
            except Exception:  # noqa: BLE001
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
            except Exception:  # noqa: BLE001
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
            except Exception:  # noqa: BLE001
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
            except Exception:  # noqa: BLE001
                pass

        elif dtype == "CIRCLE":
            try:
                cx, cy = entity.dxf.center.x, entity.dxf.center.y
                r = entity.dxf.radius
                angles = [2 * math.pi * i / _ARC_N for i in range(_ARC_N + 1)]
                arc_x += [cx + r * math.cos(a) for a in angles] + [None]
                arc_y += [cy + r * math.sin(a) for a in angles] + [None]
            except Exception:  # noqa: BLE001
                pass

        elif dtype in ("TEXT", "MTEXT"):
            try:
                pt = entity.dxf.insert
                raw = entity.dxf.text or ""
                label = raw.strip()
                if label:
                    text_x.append(pt.x)
                    text_y.append(pt.y)
                    text_labels.append(label)
            except Exception:  # noqa: BLE001
                pass

    return {
        "line_x": line_x, "line_y": line_y,
        "arc_x": arc_x, "arc_y": arc_y,
        "text_x": text_x, "text_y": text_y, "text_labels": text_labels,
    }


def _add_geometry(fig: go.Figure, geo: dict) -> None:
    """도면 기하·작은 텍스트 라벨을 회색으로 깔아준다."""
    geo_color = "#505050"
    text_color = "#a0a0a0"

    if geo["line_x"]:
        fig.add_trace(go.Scatter(
            x=geo["line_x"], y=geo["line_y"], mode="lines",
            line=dict(color=geo_color, width=0.7),
            hoverinfo="skip", showlegend=False, name="_lines",
        ))
    if geo["arc_x"]:
        fig.add_trace(go.Scatter(
            x=geo["arc_x"], y=geo["arc_y"], mode="lines",
            line=dict(color=geo_color, width=0.7),
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


def _add_dim_category(
    fig: go.Figure,
    dims: list[DimensionInfo],
    cat: str,
    legend_prefix: str,
) -> None:
    """한 카테고리(DIM 묶음) 를 두 트레이스로 추가 — 선 + 라벨/마커."""
    if not dims:
        return

    line_xs: list = []
    line_ys: list = []
    label_xs: list = []
    label_ys: list = []
    labels: list = []
    customdata: list = []
    for d in dims:
        line_xs += [d.p2[0], d.p3[0], None]
        line_ys += [d.p2[1], d.p3[1], None]
        mx = (d.p2[0] + d.p3[0]) / 2
        my = (d.p2[1] + d.p3[1]) / 2
        label_xs.append(mx)
        label_ys.append(my)
        labels.append(f"{d.measurement:.0f}")
        customdata.append([
            d.layer or "-",
            d.dim_type,
            d.direction,
            d.override_text or "-",
        ])

    fig.add_trace(go.Scatter(
        x=line_xs, y=line_ys, mode="lines",
        line=dict(color=_COLOR[cat], width=_WIDTH[cat]),
        name=f"{legend_prefix} — {len(dims)}개",
        hoverinfo="skip",
        legendgroup=cat,
    ))
    fig.add_trace(go.Scatter(
        x=label_xs, y=label_ys, mode="markers+text",
        text=labels,
        textfont=dict(
            size=11 if cat == "chosen" else 9,
            color=_COLOR[cat],
        ),
        textposition="middle right",
        marker=dict(
            symbol="circle",
            size=6 if cat == "chosen" else 4,
            color=_COLOR[cat],
        ),
        customdata=customdata,
        hovertemplate=(
            "measurement: %{text} mm<br>"
            "direction: %{customdata[2]}<br>"
            "layer: %{customdata[0]}<br>"
            "dim_type: %{customdata[1]}<br>"
            "override: %{customdata[3]}<br>"
            "(x, y) = (%{x:.1f}, %{y:.1f})"
            f"<extra>{cat}</extra>"
        ),
        showlegend=False,
        legendgroup=cat,
    ))


def _dimension_traces(fig: go.Figure, result: MeasurementResult) -> None:
    """DIMENSION 카테고리별로 트레이스 추가 + 채택 DIM 끝점 강조."""
    chosen = result.source_dim

    chosen_dims = [chosen] if chosen is not None else []
    other_v = [d for d in result.all_vertical_dims if d is not chosen]
    _add_dim_category(fig, chosen_dims, "chosen", "채택 (세로 최대)")
    _add_dim_category(fig, other_v, "other_vertical", "다른 세로 DIM")
    _add_dim_category(fig, list(result.all_horizontal_dims), "horizontal", "가로 DIM")
    _add_dim_category(fig, list(result.all_diagonal_dims), "diagonal", "대각 DIM")

    if chosen is not None:
        fig.add_trace(go.Scatter(
            x=[chosen.p2[0], chosen.p3[0]],
            y=[chosen.p2[1], chosen.p3[1]],
            mode="markers",
            marker=dict(
                symbol="cross", size=14, color=_COLOR["chosen"],
                line=dict(color="black", width=1),
            ),
            name="채택 DIM 끝점",
            hoverinfo="skip",
        ))


def _status_label(predicted: float | None, expected: float | None) -> str:
    if expected is None:
        return "----"
    if predicted is None:
        return "FAIL"
    if abs(predicted - expected) <= 0.5:
        return "PASS"
    if within_length_tolerance(predicted, expected):
        return "PASS(±tol)"
    return "FAIL"


def _summary_box(
    drawing: str,
    rel_path: str,
    result: MeasurementResult,
    drawing_measurement: DrawingMeasurement,
) -> str:
    """파일 시각화용 정답 비교 박스 HTML."""
    expected = drawing_measurement.expected
    title = f"<b>{drawing} — {os.path.basename(rel_path)}</b>"
    pred = result.length_mm
    conf = result.confidence
    file_line = (
        f"이 파일 측정: <b>{(f'{pred:.0f}' if pred is not None else '-')} mm</b>"
        f" (conf={conf}, |V|={len(result.all_vertical_dims)},"
        f" |H|={len(result.all_horizontal_dims)})"
    )
    notes_html = "<br>".join(f"· {n}" for n in result.notes) if result.notes else ""

    rows = ["<span style='font-family:monospace'>",
            f"{'부호':<6}{'예측':>8}{'정답':>8}{'차이':>7}  상태  신뢰도"]
    for symbol in sorted(expected):
        sym_meas = drawing_measurement.symbols.get(symbol)
        p = sym_meas.length_mm if sym_meas else None
        e = expected[symbol][0]
        c = sym_meas.confidence if sym_meas else "-"
        diff_str = f"{p - e:+.0f}" if p is not None else "-"
        rows.append(
            f"{symbol:<6}{(f'{p:.0f}' if p is not None else '-'):>8}"
            f"{e:>8.0f}{diff_str:>7}  "
            f"{_status_label(p, e):<10} {c}"
        )
    rows.append("</span>")

    body = "<br>".join([title, file_line])
    if notes_html:
        body += "<br>" + notes_html
    body += "<br>" + "<br>".join(rows)
    return body


def _add_summary_annotation(
    fig: go.Figure,
    drawing: str,
    rel_path: str,
    result: MeasurementResult,
    drawing_measurement: DrawingMeasurement,
) -> None:
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.005, y=0.995,
        xanchor="left", yanchor="top",
        text=_summary_box(drawing, rel_path, result, drawing_measurement),
        font=dict(size=11, color="#202020"),
        showarrow=False,
        align="left",
        bgcolor="rgba(255,255,255,0.92)",
        bordercolor="#606060",
        borderwidth=1,
    )


def _safe_stem(rel_path: str) -> str:
    """파일명 안전화 — 확장자 제거 + 디렉토리 제거."""
    base = os.path.basename(rel_path)
    if base.lower().endswith(".dxf"):
        base = base[:-4]
    return base


def visualize_source(
    drawing: str,
    rel_path: str,
    drawing_measurement: DrawingMeasurement,
    out_dir: str = _OUTPUT_DIR,
) -> str:
    """한 소스 DXF 의 길이 시각화 HTML 생성."""
    os.makedirs(out_dir, exist_ok=True)
    abs_path = resolve_source_path(rel_path)
    geo = _parse_dxf_geometry(abs_path)
    result = drawing_measurement.file_results[rel_path]

    fig = go.Figure()
    _add_geometry(fig, geo)
    _dimension_traces(fig, result)
    _add_summary_annotation(fig, drawing, rel_path, result, drawing_measurement)

    fig.update_layout(
        title=f"{drawing} — {os.path.basename(rel_path)}  (DIMENSION 기반 길이 측정)",
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

    out_path = os.path.join(out_dir, f"{_safe_stem(rel_path)}_length.html")
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


def visualize_drawing(drawing: str, routing_config: dict) -> list[str]:
    """한 도면의 모든 소스 파일에 대해 HTML 생성. 경로 리스트 반환."""
    measurement = measure_drawing(drawing, routing_config)
    rel_paths = list(measurement.file_results.keys())
    return [visualize_source(drawing, rp, measurement) for rp in rel_paths]


def _parse_args(argv: list[str]) -> tuple[list[str], bool]:
    auto_open = True
    drawings: list[str] = []
    for arg in argv:
        if arg == "--no-open":
            auto_open = False
        else:
            drawings.append(arg)
    if not drawings:
        drawings = list(_ALL_DRAWINGS)
    return drawings, auto_open


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    targets, auto_open = _parse_args(sys.argv[1:])
    config = load_routing()

    generated: list[str] = []
    for drawing in targets:
        if drawing not in config["drawings"]:
            print(
                f"[오류] 알 수 없는 도면: {drawing} "
                f"(사용 가능: {list(config['drawings'].keys())})"
            )
            sys.exit(1)
        outs = visualize_drawing(drawing, config)
        for out in outs:
            rel = os.path.relpath(out, PROJECT_ROOT).replace("\\", "/")
            print(f"{rel} 생성")
            generated.append(out)

    if auto_open and generated:
        first = os.path.abspath(generated[0])
        url = "file:///" + first.replace("\\", "/")
        print(f"브라우저로 오픈: {url}")
        webbrowser.open(url)


if __name__ == "__main__":
    main()
