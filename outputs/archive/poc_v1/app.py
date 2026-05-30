"""도면 부재 카운팅 PoC — Streamlit 앱"""
import io
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm
import streamlit as st

from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
import ezdxf

from counter import count_members

# ── 한글 폰트 설정 ──────────────────────────────────────────────
def _setup_korean_font():
    candidates = ["Malgun Gothic", "NanumGothic", "AppleGothic", "DejaVu Sans"]
    available = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in available:
            plt.rcParams["font.family"] = name
            return
    plt.rcParams["font.family"] = "DejaVu Sans"

_setup_korean_font()
plt.rcParams["axes.unicode_minus"] = False

# ── DXF → PNG 렌더링 ─────────────────────────────────────────────
@st.cache_data(show_spinner="도면 렌더링 중…")
def render_dxf(dxf_bytes: bytes) -> tuple[bytes, tuple[float, float, float, float]]:
    """DXF 바이트를 PNG 바이트로 변환하고 모델공간 extents 반환"""
    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
        f.write(dxf_bytes)
        tmp_path = f.name

    doc = ezdxf.readfile(tmp_path)
    msp = doc.modelspace()

    fig, ax = plt.subplots(figsize=(20, 15))
    ctx = RenderContext(doc)
    out = MatplotlibBackend(ax)
    Frontend(ctx, out).draw_layout(msp, finalize=True)

    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")

    extents = (
        ax.get_xlim()[0], ax.get_ylim()[0],
        ax.get_xlim()[1], ax.get_ylim()[1],
    )

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)

    Path(tmp_path).unlink(missing_ok=True)
    return buf.read(), extents


def render_with_overlay(
    dxf_bytes: bytes,
    xmin: float, ymin: float,
    xmax: float, ymax: float,
    hits: list[tuple[float, float, str]],
) -> bytes:
    """원본 도면 위에 빨간 박스 + 노란 점을 그린 PNG 반환"""
    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
        f.write(dxf_bytes)
        tmp_path = f.name

    doc = ezdxf.readfile(tmp_path)
    msp = doc.modelspace()

    fig, ax = plt.subplots(figsize=(20, 15))
    ctx = RenderContext(doc)
    out = MatplotlibBackend(ax)
    Frontend(ctx, out).draw_layout(msp, finalize=True)

    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")

    # 빨간 선택 영역 박스
    rect = mpatches.Rectangle(
        (xmin, ymin), xmax - xmin, ymax - ymin,
        linewidth=2, edgecolor="red", facecolor="none", zorder=10,
    )
    ax.add_patch(rect)

    # 노란 부재 위치 점
    if hits:
        xs = [h[0] for h in hits]
        ys = [h[1] for h in hits]
        ax.scatter(xs, ys, c="yellow", s=60, zorder=11, edgecolors="orange", linewidths=0.8)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)

    Path(tmp_path).unlink(missing_ok=True)
    return buf.read()


# ── Streamlit UI ─────────────────────────────────────────────────
st.set_page_config(page_title="도면 부재 카운팅 PoC", layout="wide")
st.title("도면 부재 카운팅 PoC")

uploaded = st.file_uploader("DXF 파일을 업로드하세요", type=["dxf"])

if uploaded is None:
    st.info("DXF 파일을 업로드하면 도면이 표시됩니다.")
    st.stop()

dxf_bytes = uploaded.read()
png_bytes, extents = render_dxf(dxf_bytes)

st.subheader("업로드된 도면")
st.image(png_bytes, use_container_width=True)

# ── 영역 좌표 입력 ─────────────────────────────────────────────
with st.expander("영역 좌표 입력 및 카운트 실행", expanded=True):
    col1, col2, col3, col4 = st.columns(4)
    xmin = col1.number_input("xmin", value=290000.0, format="%.1f")
    ymin = col2.number_input("ymin", value=1196000.0, format="%.1f")
    xmax = col3.number_input("xmax", value=410000.0, format="%.1f")
    ymax = col4.number_input("ymax", value=1208000.0, format="%.1f")

    run = st.button("카운트 실행", type="primary")

if not run:
    st.stop()

# ── 카운팅 실행 ─────────────────────────────────────────────────
with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
    f.write(dxf_bytes)
    tmp_dxf = f.name

try:
    counts, hits = count_members(tmp_dxf, xmin, ymin, xmax, ymax)
finally:
    Path(tmp_dxf).unlink(missing_ok=True)

# ── 결과 표시 ──────────────────────────────────────────────────
st.subheader("카운트 결과 도면 (빨간 박스 = 선택 영역 / 노란 점 = 매칭 부재)")
overlay_png = render_with_overlay(dxf_bytes, xmin, ymin, xmax, ymax, hits)
st.image(overlay_png, use_container_width=True)

st.subheader("부재 부호 카운트")
if counts:
    rows = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    st.table({"부호": [r[0] for r in rows], "개수": [r[1] for r in rows]})
    st.success(f"총 {sum(counts.values())}개 부재 발견 ({len(counts)}종류)")
else:
    st.warning("선택한 영역 내에 화이트리스트 부재가 없습니다.")
