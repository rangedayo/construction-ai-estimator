"""부재 부호 카운팅 로직 — DXF TEXT/MTEXT 및 INSERT 블록 엔티티 기반"""
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
    return _MTEXT_ESCAPE.sub("", raw).strip()


def _collect_from_insert(
    entity,
    doc,
    match_fn: Callable[[str], bool],
) -> list[tuple[float, float, str]]:
    """INSERT 엔티티에서 (x, y, symbol) 목록 추출.

    ATTRIB(인스턴스 속성값) → 블록 정의 내 TEXT/ATTDEF(기본값) 순으로 확인.
    같은 INSERT에서 동일 부호가 중복 집계되지 않도록 seen으로 deduplicate.
    """
    try:
        pt = entity.dxf.insert
        x, y = float(pt.x), float(pt.y)
    except Exception:
        return []

    found: list[tuple[float, float, str]] = []
    seen: set[str] = set()

    # 1. ATTRIB: INSERT에 직접 붙은 속성값 (도면4 등)
    try:
        for attrib in entity.attribs:
            try:
                val = attrib.dxf.text.strip() if attrib.dxf.hasattr("text") else ""
                if val and match_fn(val) and val not in seen:
                    found.append((x, y, val))
                    seen.add(val)
            except Exception:
                pass
    except Exception:
        pass

    # 2. 블록 정의 내 TEXT / ATTDEF — ATTRIB가 없을 때만 (도면2 등)
    if not found:
        try:
            block = doc.blocks.get(entity.dxf.name)
            if block:
                for be in block:
                    btype = be.dxftype()
                    if btype == "TEXT":
                        val = be.dxf.text.strip() if be.dxf.hasattr("text") else ""
                    elif btype == "MTEXT":
                        val = _clean_mtext(be.plain_mtext()) if hasattr(be, "plain_mtext") else ""
                    elif btype == "ATTDEF":
                        val = be.dxf.text.strip() if be.dxf.hasattr("text") else ""
                    else:
                        continue
                    if val and match_fn(val) and val not in seen:
                        found.append((x, y, val))
                        seen.add(val)
        except Exception:
            pass

    return found


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

    def _record(x: float, y: float, text: str) -> None:
        counts[text] += 1
        hits.append((x, y, text))
        coords_by_symbol.setdefault(text, []).append((x, y))

    for entity in msp:
        dtype = entity.dxftype()

        if dtype in ("TEXT", "MTEXT"):
            try:
                raw = entity.dxf.text
                text = _clean_mtext(raw) if dtype == "MTEXT" else raw.strip()
                if not match_fn(text):
                    continue
                pt = entity.dxf.insert
                x, y = float(pt.x), float(pt.y)
                if xmin <= x <= xmax and ymin <= y <= ymax:
                    _record(x, y, text)
            except Exception:
                pass

        elif dtype == "INSERT":
            for x, y, text in _collect_from_insert(entity, doc, match_fn):
                if xmin <= x <= xmax and ymin <= y <= ymax:
                    _record(x, y, text)

    return counts, hits, coords_by_symbol
