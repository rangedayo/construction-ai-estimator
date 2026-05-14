"""도면 부재 카운팅 PoC v2 — 박스 그리기 + Plotly 인터랙티브 시각화"""
import io
import math
import re
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import plotly.graph_objects as go
import streamlit as st
from PIL import Image
from streamlit_drawable_canvas import st_canvas
import ezdxf
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

from counter import count_members
from coord_utils import pixel_bbox_to_dxf_bbox

MAX_CANVAS_W = 1400

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


def _clean_mtext(raw: str) -> str:
    return _MTEXT_ESCAPE.sub("", raw).strip()


def _setup_korean_font() -> None:
    candidates = ["Malgun Gothic", "NanumGothic", "AppleGothic", "DejaVu Sans"]
    available = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in available:
            plt.rcParams["font.family"] = name
            return
    plt.rcParams["font.family"] = "DejaVu Sans"


_setup_korean_font()
plt.rcParams["axes.unicode_minus"] = False


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


@st.cache_data(show_spinner="도면 렌더링 중…")
def render_dxf(dxf_bytes: bytes) -> tuple[bytes, dict]:
    """DXF → PNG 변환 + 좌표 매핑 정보 반환"""
    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
        f.write(dxf_bytes)
        tmp_path = f.name

    try:
        doc = ezdxf.readfile(tmp_path)
        msp = doc.modelspace()

        fig, ax = plt.subplots(figsize=(20, 15))
        ax.set_facecolor("white")
        fig.patch.set_facecolor("white")

        ctx = RenderContext(doc)
        out = MatplotlibBackend(ax)
        Frontend(ctx, out).draw_layout(msp, finalize=True)

        dxf_xmin, dxf_xmax = ax.get_xlim()
        dxf_ymin, dxf_ymax = ax.get_ylim()

        # 축 장식 제거 후 axes 영역만 정확히 저장
        ax.set_axis_off()
        fig.canvas.draw()
        axes_extent = ax.get_window_extent().transformed(
            fig.dpi_scale_trans.inverted()
        )
        buf = io.BytesIO()
        fig.savefig(
            buf, format="png", dpi=100,
            bbox_inches=axes_extent, facecolor="white",
        )
        plt.close(fig)
        buf.seek(0)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    # 캔버스 너비 1400px 이하로 리사이즈
    img = Image.open(buf)
    orig_w, orig_h = img.size
    scale = min(1.0, MAX_CANVAS_W / orig_w)
    canvas_w = int(orig_w * scale)
    canvas_h = int(orig_h * scale)
    img_resized = img.resize((canvas_w, canvas_h), Image.LANCZOS)

    out_buf = io.BytesIO()
    img_resized.save(out_buf, format="PNG")
    out_buf.seek(0)

    return out_buf.read(), {
        "dxf_xmin": dxf_xmin,
        "dxf_ymin": dxf_ymin,
        "dxf_xmax": dxf_xmax,
        "dxf_ymax": dxf_ymax,
        "png_width": canvas_w,
        "png_height": canvas_h,
    }


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
st.set_page_config(page_title="도면 부재 카운팅 PoC v2", layout="wide")
st.title("도면 부재 카운팅 PoC v2")

uploaded = st.file_uploader("DXF 파일을 업로드하세요", type=["dxf"])

if uploaded is None:
    st.info("DXF 파일을 업로드하면 도면 위에 박스를 그릴 수 있습니다.")
    st.stop()

dxf_bytes = uploaded.read()
png_bytes, coord_map = render_dxf(dxf_bytes)
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

# ── 탭 UI ────────────────────────────────────────────────────────────────────
tab_canvas, tab_plotly = st.tabs(["📐 박스 그리기 (카운트)", "🔍 인터랙티브 시각화 (검증)"])

with tab_canvas:
    canvas_w = coord_map["png_width"]
    canvas_h = coord_map["png_height"]
    bg_image = Image.open(io.BytesIO(png_bytes))

    st.write("도면 위에 박스를 그려 카운트할 영역을 선택하세요.")
    canvas_result = st_canvas(
        fill_color="rgba(255, 0, 0, 0.1)",
        stroke_width=3,
        stroke_color="#FF0000",
        background_image=bg_image,
        update_streamlit=True,
        height=canvas_h,
        width=canvas_w,
        drawing_mode="rect",
        key="canvas",
    )

    objects = (
        canvas_result.json_data.get("objects", [])
        if canvas_result.json_data
        else []
    )

    if not objects:
        with st.expander("디버그 정보"):
            st.write(f"캔버스 크기: {canvas_w} × {canvas_h} px")
            st.write(
                f"DXF 범위: x=[{coord_map['dxf_xmin']:.1f}, {coord_map['dxf_xmax']:.1f}]  "
                f"y=[{coord_map['dxf_ymin']:.1f}, {coord_map['dxf_ymax']:.1f}]"
            )
            st.write(f"모드: {'자동 감지' if custom_whitelist is None else '직접 입력'}")
        st.info("도면 위에 박스를 그리면 카운트 결과가 표시됩니다.")
    else:
        last = objects[-1]
        px_left = last["left"]
        px_top = last["top"]
        px_w = last["width"] * last.get("scaleX", 1)
        px_h = last["height"] * last.get("scaleY", 1)

        xmin, ymin, xmax, ymax = pixel_bbox_to_dxf_bbox(
            px_left, px_top, px_w, px_h,
            canvas_w, canvas_h,
            coord_map["dxf_xmin"], coord_map["dxf_ymin"],
            coord_map["dxf_xmax"], coord_map["dxf_ymax"],
        )

        with st.expander("디버그 정보"):
            st.write(f"캔버스 크기: {canvas_w} × {canvas_h} px")
            st.write(
                f"DXF 범위: x=[{coord_map['dxf_xmin']:.1f}, {coord_map['dxf_xmax']:.1f}]  "
                f"y=[{coord_map['dxf_ymin']:.1f}, {coord_map['dxf_ymax']:.1f}]"
            )
            st.write(
                f"박스 (픽셀): left={px_left:.0f}, top={px_top:.0f}, "
                f"w={px_w:.0f}, h={px_h:.0f}"
            )
            st.write(
                f"변환된 DXF 좌표: xmin={xmin:.1f}, ymin={ymin:.1f}, "
                f"xmax={xmax:.1f}, ymax={ymax:.1f}"
            )

        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
            f.write(dxf_bytes)
            tmp_dxf = f.name

        try:
            counts, hits, coords_by_symbol = count_members(
                tmp_dxf, xmin, ymin, xmax, ymax, custom_whitelist
            )
        finally:
            Path(tmp_dxf).unlink(missing_ok=True)

        st.session_state["counts"] = counts
        st.session_state["hits"] = hits
        st.session_state["coords_by_symbol"] = coords_by_symbol

        result_label = (
            "이 영역에서 발견된 부호"
            if custom_whitelist is None
            else "입력하신 부호 중 발견된 것"
        )
        st.subheader(f"부재 부호 카운트 결과 — {result_label}")
        if counts:
            rows = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
            st.table({"부호": [r[0] for r in rows], "개수": [r[1] for r in rows]})
            st.success(f"총 {sum(counts.values())}개 부재 발견 ({len(counts)}종류)")
            st.info("👉 '인터랙티브 시각화' 탭에서 마커 위치를 줌인하여 확인하세요.")
        else:
            st.warning("이 영역에는 매칭되는 부호가 없습니다.")

with tab_plotly:
    counts_viz = st.session_state.get("counts", {})
    coords_by_symbol_viz = st.session_state.get("coords_by_symbol", {})

    if not counts_viz:
        st.info("'박스 그리기' 탭에서 영역을 선택하면 여기에 마커가 표시됩니다.")

    fig = build_dxf_figure(plotly_data, coords_by_symbol_viz, counts_viz)
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

    if counts_viz:
        st.write("**카운트 검증:**")
        for sym in sorted(coords_by_symbol_viz.keys()):
            tbl = counts_viz[sym]
            mkr = len(coords_by_symbol_viz[sym])
            ok = tbl == mkr
            st.write(f"{'✅' if ok else '❌'} **{sym}**: 테이블 {tbl}개 = 마커 {mkr}개")
