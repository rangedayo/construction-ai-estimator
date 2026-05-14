"""부재 부호 카운팅 로직 — DXF TEXT/MTEXT 엔티티 기반"""
import re
from collections import Counter
from typing import Callable

import ezdxf

WHITELIST = {
    "CRG1", "MC1", "MC2", "MC3", "MT1",
    "RSB1", "RSB2", "RSB3", "RSG1", "RSG2", "RSG3",
    "SB1", "SB2", "SB3", "SC1", "SG1", "SG2", "SG3",
    "VG1", "VT1", "WG1",
}

_MTEXT_ESCAPE = re.compile(r"\{[^}]*\}|\\[A-Za-z0-9.:;-]+;?|[{}]")
_AUTO_DETECT = re.compile(r"^[A-Z]{1,5}\d{1,2}$")


def _clean_mtext(raw: str) -> str:
    """MTEXT 서식 코드 제거 후 순수 텍스트 반환"""
    return _MTEXT_ESCAPE.sub("", raw).strip()


def _entity_insert(entity) -> tuple[float, float] | None:
    """TEXT / MTEXT 엔티티에서 삽입 좌표 반환"""
    try:
        if entity.dxftype() in ("TEXT", "MTEXT"):
            pt = entity.dxf.insert
            return float(pt.x), float(pt.y)
        return None
    except Exception:
        return None


def count_members(
    dxf_path: str,
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
    custom_whitelist: list[str] | None = None,
) -> tuple[Counter, list[tuple[float, float, str]], dict[str, list[tuple[float, float]]]]:
    """
    Parameters
    ----------
    custom_whitelist
        None  → 자동 감지 (영문 대문자 1~5자 + 숫자 1~2자 패턴)
        list  → 해당 부호만 카운트

    Returns
    -------
    counts          : Counter  {symbol: count}
    hits            : list of (x, y, symbol) for matched entities
    coords_by_symbol: dict {symbol: [(x, y), ...]}
    """
    if custom_whitelist is None:
        match_fn: Callable[[str], bool] = lambda t: bool(_AUTO_DETECT.match(t))
    else:
        whitelist_set = set(custom_whitelist)
        match_fn = lambda t: t in whitelist_set

    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    counts: Counter = Counter()
    hits: list[tuple[float, float, str]] = []
    coords_by_symbol: dict[str, list[tuple[float, float]]] = {}

    for entity in msp:
        dtype = entity.dxftype()
        if dtype not in ("TEXT", "MTEXT"):
            continue

        raw = entity.dxf.text
        text = _clean_mtext(raw) if dtype == "MTEXT" else raw.strip()

        if not match_fn(text):
            continue

        coord = _entity_insert(entity)
        if coord is None:
            continue

        x, y = coord
        if xmin <= x <= xmax and ymin <= y <= ymax:
            counts[text] += 1
            hits.append((x, y, text))
            coords_by_symbol.setdefault(text, []).append((x, y))

    return counts, hits, coords_by_symbol
