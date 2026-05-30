"""도면 부재 카운팅 PoC v3 — DXF 업로드 시 전체 도면 자동 카운트 + Plotly 인터랙티브 시각화"""
import math
import re
import tempfile
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st
import ezdxf

from counter import count_members

# coord_utils는 현재 미사용(박스 그리기 폐기). 영역 한정 기능 재도입 시 재활용 예정.

_NAMED_COLORS: dict[str, str] = {
    "VG1": "red",
    "MT1": "blue",
    "VT1": "green",
}
_CYCLE_COLORS = [
    "orange", "purple", "cyan", "magenta",
    "brown", "gold", "lime", "deeppink",
    "teal", "coral", "indigo", "olive",
]

_MTEXT_ESCAPE = re.compile(r"\{[^}]*\}|\\[A-Za-z0-9.:;-]+;?|[{}]")
_ARC_N = 48

# 전체 도면 카운트용 무한 범위 (counter.py의 xmin<=x<=xmax 검사를 항상 통과)
_FULL_MIN = float("-inf")
_FULL_MAX = float("inf")


def _clean_mtext(raw: str) -> str:
    return _MTEXT_ESCAPE.sub("", raw).strip()


def _assign_colors(symbols: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    cycle_idx = 0
    for sym in symbols:
        if sym in _NAMED_COLORS:
            result[sym] = _NAMED_COLORS[sym]
        else:
            result[sym] = _CYCLE_COLORS[cycle_idx % len(_CYCLE_COLORS)]
            cycle_idx += 1
    return result


@st.cache_data(show_spinner="Plotly 도면 변환 중…")
def parse_dxf_for_plotly(dxf_bytes: bytes) -> dict:
    """
    DXF 엔티티 → Plotly 트레이스 데이터.
    LINE/LWPOLYLINE/POLYLINE은 None 구분자로 묶어 트레이스 수를 최소화.
    """
    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
        f.write(dxf_bytes)
        tmp_path = f.name

    try:
        doc = ezdxf.readfile(tmp_path)
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

    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {
        "line_x": line_x,
        "line_y": line_y,
        "arc_x": arc_x,
        "arc_y": arc_y,
        "text_x": text_x,
        "text_y": text_y,
        "text_labels": text_labels,
    }


def build_dxf_figure(
    trace_data: dict,
    coords_by_symbol: dict[str, list[tuple[float, float]]],
    counts,
    height: int = 900,
) -> go.Figure:
    """Plotly Figure: DXF 기하 트레이스 + 부재 마커 오버레이"""
    fig = go.Figure()

    GEO_COLOR = "#505050"
    TEXT_COLOR = "#303030"

    if trace_data["line_x"]:
        fig.add_trace(go.Scatter(
            x=trace_data["line_x"],
            y=trace_data["line_y"],
            mode="lines",
            line=dict(color=GEO_COLOR, width=0.8),
            hoverinfo="skip",
            showlegend=False,
            name="_lines",
        ))

    if trace_data["arc_x"]:
        fig.add_trace(go.Scatter(
            x=trace_data["arc_x"],
            y=trace_data["arc_y"],
            mode="lines",
            line=dict(color=GEO_COLOR, width=0.8),
            hoverinfo="skip",
            showlegend=False,
            name="_arcs",
        ))

    if trace_data["text_x"]:
        fig.add_trace(go.Scatter(
            x=trace_data["text_x"],
            y=trace_data["text_y"],
            mode="text",
            text=trace_data["text_labels"],
            textfont=dict(size=7, color=TEXT_COLOR),
            hovertemplate="%{text}<extra></extra>",
            showlegend=False,
            name="_text",
        ))

    if coords_by_symbol:
        symbol_colors = _assign_colors(sorted(coords_by_symbol.keys()))
        for sym in sorted(coords_by_symbol.keys()):
            coords = coords_by_symbol[sym]
            xs = [c[0] for c in coords]
            ys = [c[1] for c in coords]
            color = symbol_colors[sym]
            fig.add_trace(go.Scatter(
                x=xs,
                y=ys,
                mode="markers",
                name=f"{sym} ({counts[sym]}개)",
                marker=dict(
                    symbol="circle-open",
                    size=14,
                    color=color,
                    line=dict(color=color, width=2.5),
                ),
                hovertemplate=f"{sym} / (%{{x:.1f}}, %{{y:.1f}})<extra></extra>",
                legendgroup=sym,
            ))

    fig.update_layout(
        height=height,
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=False, zeroline=False, scaleanchor="x", scaleratio=1),
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.01,
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="#aaaaaa",
            borderwidth=1,
        ),
        dragmode="pan",
    )
    return fig


# ── Streamlit UI ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="도면 부재 카운팅 PoC v3", layout="wide")
st.title("도면 부재 카운팅 PoC v3")
st.caption("DXF를 업로드하면 도면 전체의 부재 부호를 자동으로 카운트합니다.")

uploaded = st.file_uploader("DXF 파일을 업로드하세요", type=["dxf"])

if uploaded is None:
    st.info("DXF 파일을 업로드하면 전체 도면 자동 카운트 결과가 표시됩니다.")
    st.stop()

dxf_bytes = uploaded.read()
plotly_data = parse_dxf_for_plotly(dxf_bytes)

# ── 부재 부호 설정 ────────────────────────────────────────────────────────────
st.subheader("카운트할 부재 부호 설정")
mode = st.radio(
    "부호 입력 방식",
    ["자동 감지 (영문+숫자 패턴 자동 추출)", "직접 입력"],
    index=0,
)

if mode == "직접 입력":
    symbols_input = st.text_input(
        "부호를 콤마로 구분하여 입력 (예: SC1, SG1, VG1)",
        value="",
    )
    custom_whitelist: list[str] | None = [
        s.strip() for s in symbols_input.split(",") if s.strip()
    ] or None
else:
    custom_whitelist = None

# ── 전체 도면 자동 카운트 ─────────────────────────────────────────────────────
# 박스 그리기 폐기: 도면 전체 범위(무한 bbox)로 counter.py를 호출해 모든 부재를 집계.
with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
    f.write(dxf_bytes)
    tmp_dxf = f.name

try:
    counts, hits, coords_by_symbol = count_members(
        tmp_dxf, _FULL_MIN, _FULL_MIN, _FULL_MAX, _FULL_MAX, custom_whitelist
    )
finally:
    Path(tmp_dxf).unlink(missing_ok=True)

result_label = (
    "도면 전체에서 발견된 부호"
    if custom_whitelist is None
    else "입력하신 부호 중 발견된 것"
)

st.subheader(f"부재 부호 카운트 결과 — {result_label}")
if counts:
    rows = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    st.table({"부호": [r[0] for r in rows], "개수": [r[1] for r in rows]})
    st.success(f"총 {sum(counts.values())}개 부재 발견 ({len(counts)}종류)")
else:
    st.warning("매칭되는 부호가 없습니다.")

# ── Plotly 인터랙티브 시각화 ──────────────────────────────────────────────────
st.subheader("인터랙티브 시각화 (검증)")
st.write("도면 기하 + 부재 마커 오버레이 — 줌/팬으로 마커 위치를 확인하세요.")

fig = build_dxf_figure(plotly_data, coords_by_symbol, counts)
st.plotly_chart(
    fig,
    use_container_width=True,
    config={
        "scrollZoom": True,
        "displayModeBar": True,
        "modeBarButtonsToRemove": ["lasso2d", "select2d"],
        "toImageButtonOptions": {"format": "png", "scale": 2},
    },
)

if counts:
    st.write("**카운트 검증:**")
    for sym in sorted(coords_by_symbol.keys()):
        tbl = counts[sym]
        mkr = len(coords_by_symbol[sym])
        ok = tbl == mkr
        st.write(f"{'✅' if ok else '❌'} **{sym}**: 테이블 {tbl}개 = 마커 {mkr}개")
