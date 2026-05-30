"""부재 부호 카운팅 로직 — DXF TEXT/MTEXT 엔티티 기반"""
import re
from collections import Counter

import ezdxf

WHITELIST = {
    "CRG1", "MC1", "MC2", "MC3", "MT1",
    "RSB1", "RSB2", "RSB3", "RSG1", "RSG2", "RSG3",
    "SB1", "SB2", "SB3", "SC1", "SG1", "SG2", "SG3",
    "VG1", "VT1", "WG1",
}

_MTEXT_ESCAPE = re.compile(r"\{[^}]*\}|\\[A-Za-z0-9.:;-]+;?|[{}]")


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
) -> tuple[Counter, list[tuple[float, float, str]]]:
    """
    Returns
    -------
    counts : Counter  {symbol: count}
    hits   : list of (x, y, symbol) for matched entities
    """
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    counts: Counter = Counter()
    hits: list[tuple[float, float, str]] = []

    for entity in msp:
        dtype = entity.dxftype()
        if dtype not in ("TEXT", "MTEXT"):
            continue

        raw = entity.dxf.text
        text = _clean_mtext(raw) if dtype == "MTEXT" else raw.strip()

        if text not in WHITELIST:
            continue

        coord = _entity_insert(entity)
        if coord is None:
            continue

        x, y = coord
        if xmin <= x <= xmax and ymin <= y <= ymax:
            counts[text] += 1
            hits.append((x, y, text))

    return counts, hits
