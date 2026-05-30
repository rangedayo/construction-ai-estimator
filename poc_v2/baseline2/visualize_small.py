"""작은 도면 시각화 — 라운드 베이스라인-2 작업 5.

작은 도면 1장당 HTML 1개. 도면 기하 위에 측정 결과를 오버레이한다.
    - 회색 LINE/POLYLINE/ARC 골격 (visualize_specs._parse_geometry 재사용)
    - 매칭된 기둥 부호 (녹색 마커 + 카운트 라벨)
    - 부호↔규격 페어 (파랑 마커 + 페어링 점선)
    - 길이 측정 수직선 (빨강 굵은 선 + 양 끝 십자 + 측정값)
    - 좌상단: 표제부 추출 도면명 / 매칭 시트 / 신뢰도
    - PASS/FAIL 배지

CLI
    python -m poc_v2.baseline2.visualize_small                  # 도면4
    python -m poc_v2.baseline2.visualize_small --drawings 도면4
    python -m poc_v2.baseline2.visualize_small --no-open
"""
from __future__ import annotations

import argparse
import os
import sys

import plotly.graph_objects as go

_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from poc_v2.baseline2.export_baseline2_csv import small_drawing_files  # noqa: E402
from poc_v2.baseline2.small_drawing_pipeline import (  # noqa: E402
    _FULL_EXTENT,
    SmallDrawingResult,
    _column_symbols,
    process_small_drawing,
)
from poc_v2.length.measure import measure_column_length  # noqa: E402
from poc_v2.length.spec_extractor import extract_specs  # noqa: E402
from poc_v2.length.visualize_specs import _parse_geometry  # noqa: E402

# counter.count_members 로 부호 hit 좌표 확보
sys.path.insert(0, os.path.join(PROJECT_ROOT, "poc_v2"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "poc_v2", "tests"))
from counter import count_members  # noqa: E402

_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "outputs", "visualize")


def _add_geometry(fig: go.Figure, dxf_path: str) -> None:
    line_x, line_y, arc_x, arc_y = _parse_geometry(dxf_path)
    if line_x:
        fig.add_trace(go.Scatter(
            x=line_x, y=line_y, mode="lines",
            line=dict(color="lightgray", width=1),
            name="기하", hoverinfo="skip",
        ))
    if arc_x:
        fig.add_trace(go.Scatter(
            x=arc_x, y=arc_y, mode="lines",
            line=dict(color="lightgray", width=1),
            name="원호", hoverinfo="skip", showlegend=False,
        ))


def _add_count_overlay(fig: go.Figure, dxf_path: str, columns: list[str]) -> None:
    """기둥 부호 hit 좌표를 녹색 마커로."""
    _counts, hits, _coords = count_members(
        dxf_path, *_FULL_EXTENT, custom_whitelist=columns,
        exclude_with_spec=True, treat_slash_as_combo=True,
    )
    xs = [h[0] for h in hits]
    ys = [h[1] for h in hits]
    labels = [h[2] for h in hits]
    if xs:
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="markers+text",
            marker=dict(color="green", size=10, symbol="circle-open",
                        line=dict(width=2)),
            text=labels, textposition="top center",
            textfont=dict(size=9, color="green"),
            name="부호(카운트 후보)",
        ))


def _add_spec_overlay(fig: go.Figure, dxf_path: str, drawing: str) -> None:
    """부호↔규격 페어(일람표) — 파랑 마커 + 페어링 점선."""
    specs = extract_specs(dxf_path, drawing)
    for e in specs:
        sx, sy = e.symbol_coord
        px, py = e.spec_coord
        fig.add_trace(go.Scatter(
            x=[sx, px], y=[sy, py], mode="lines",
            line=dict(color="royalblue", width=1, dash="dot"),
            hoverinfo="skip", showlegend=False,
        ))
        fig.add_trace(go.Scatter(
            x=[px], y=[py], mode="markers+text",
            marker=dict(color="royalblue", size=8, symbol="square"),
            text=[f"{e.symbol}: {e.spec_normalized}"],
            textposition="middle right", textfont=dict(size=8, color="royalblue"),
            hoverinfo="text", showlegend=False,
        ))


def _add_length_overlay(fig: go.Figure, dxf_path: str) -> None:
    """채택된 세로 DIMENSION 을 빨간 굵은 선 + 십자 + 라벨로."""
    m = measure_column_length(dxf_path)
    if m.source_dim is None:
        return
    (x2, y2), (x3, y3) = m.source_dim.p2, m.source_dim.p3
    fig.add_trace(go.Scatter(
        x=[x2, x3], y=[y2, y3], mode="lines+markers",
        line=dict(color="red", width=3),
        marker=dict(color="red", size=12, symbol="cross-thin",
                    line=dict(width=3)),
        name=f"길이 {m.length_mm:.0f}mm",
    ))
    midx, midy = (x2 + x3) / 2, (y2 + y3) / 2
    fig.add_annotation(
        x=midx, y=midy, text=f"<b>{m.length_mm:.0f}mm</b>",
        showarrow=False, font=dict(color="red", size=13),
        bgcolor="white", bordercolor="red",
    )


def _badge(value, label: str) -> str:
    if value is None:
        return ""
    color = "#2e7d32" if value else "#c62828"
    text = "PASS" if value else "FAIL"
    return (
        f"<span style='background:{color};color:white;padding:2px 8px;"
        f"border-radius:4px;margin-right:6px'>{label} {text}</span>"
    )


def _title_html(result: SmallDrawingResult) -> str:
    badges = (
        _badge(result.pass_counts, "카운트")
        + _badge(result.pass_specs, "규격")
        + _badge(result.pass_length, "길이")
    )
    return (
        f"<b>{os.path.basename(result.file_path)}</b><br>"
        f"표제부 추출: <b>{result.extracted_title or '(없음)'}</b> → "
        f"매칭: <b>{result.matched_sheet or '(없음)'}</b> "
        f"[{result.match_confidence}/{result.kind}]<br>{badges}"
    )


def visualize_one(file_path: str, output_dir: str | None = None) -> str:
    """작은 도면 1장을 시각화해 HTML 경로 반환."""
    result = process_small_drawing(file_path)
    drawing = result.drawing
    columns = _column_symbols(drawing)

    fig = go.Figure()
    _add_geometry(fig, file_path)

    if result.kind == "count":
        _add_count_overlay(fig, file_path, columns)
        _add_spec_overlay(fig, file_path, drawing)
    elif result.kind == "length":
        _add_length_overlay(fig, file_path)

    fig.update_layout(
        title=dict(text=_title_html(result), x=0.01, xanchor="left",
                   font=dict(size=13)),
        showlegend=True,
        plot_bgcolor="white",
        yaxis=dict(scaleanchor="x", scaleratio=1),
        margin=dict(t=90, l=20, r=20, b=20),
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)

    out_dir = output_dir or _OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(file_path))[0]
    out_path = os.path.join(out_dir, f"{base}.html")
    fig.write_html(out_path, include_plotlyjs="cdn")
    return out_path


def visualize_drawings(
    drawings: list[str],
    include_unmatched: bool = False,
    output_dir: str | None = None,
) -> list[str]:
    """도면들의 작은 도면을 시각화 (매칭된 시트만 기본)."""
    paths: list[str] = []
    for drawing in drawings:
        for file_path in small_drawing_files(drawing):
            result = process_small_drawing(file_path)
            if result.kind == "unmatched" and not include_unmatched:
                continue
            paths.append(visualize_one(file_path, output_dir))
    return paths


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="작은 도면 시각화")
    parser.add_argument("--drawings", default="도면4")
    parser.add_argument("--include-unmatched", action="store_true")
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()

    drawings = [d.strip() for d in args.drawings.split(",") if d.strip()]
    paths = visualize_drawings(drawings, args.include_unmatched)
    print(f"HTML {len(paths)}개 생성:")
    for p in paths:
        print(f"  {p}")
    if paths and not args.no_open:
        import webbrowser
        webbrowser.open(f"file://{paths[0]}")


if __name__ == "__main__":
    main()
