"""픽셀 좌표 ↔ DXF 좌표 변환 유틸리티"""


def dxf_to_pixel(
    dx: float,
    dy: float,
    png_w: int,
    png_h: int,
    dxf_xmin: float,
    dxf_ymin: float,
    dxf_xmax: float,
    dxf_ymax: float,
) -> tuple[float, float]:
    """DXF 좌표를 PNG 픽셀 좌표로 변환 (pixel_to_dxf의 역변환)."""
    px = (dx - dxf_xmin) / (dxf_xmax - dxf_xmin) * png_w
    py = (dxf_ymax - dy) / (dxf_ymax - dxf_ymin) * png_h
    return px, py


def pixel_to_dxf(
    px: float,
    py: float,
    png_w: int,
    png_h: int,
    dxf_xmin: float,
    dxf_ymin: float,
    dxf_xmax: float,
    dxf_ymax: float,
) -> tuple[float, float]:
    """
    PNG 픽셀 좌표를 DXF 좌표로 변환.
    PNG는 좌상단 원점, DXF는 좌하단 원점이므로 y를 반전.
    """
    dxf_x = dxf_xmin + (px / png_w) * (dxf_xmax - dxf_xmin)
    dxf_y = dxf_ymax - (py / png_h) * (dxf_ymax - dxf_ymin)
    return dxf_x, dxf_y


def pixel_bbox_to_dxf_bbox(
    left: float,
    top: float,
    width: float,
    height: float,
    png_w: int,
    png_h: int,
    dxf_xmin: float,
    dxf_ymin: float,
    dxf_xmax: float,
    dxf_ymax: float,
) -> tuple[float, float, float, float]:
    """
    streamlit-drawable-canvas 박스 (left, top, width, height in pixels)를
    DXF bbox (xmin, ymin, xmax, ymax)로 변환.
    """
    dx1, dy1 = pixel_to_dxf(
        left, top, png_w, png_h, dxf_xmin, dxf_ymin, dxf_xmax, dxf_ymax
    )
    dx2, dy2 = pixel_to_dxf(
        left + width, top + height, png_w, png_h, dxf_xmin, dxf_ymin, dxf_xmax, dxf_ymax
    )
    # y가 뒤집혔으므로 min/max 재정렬
    return min(dx1, dx2), min(dy1, dy2), max(dx1, dx2), max(dy1, dy2)
