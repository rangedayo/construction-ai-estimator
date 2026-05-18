"""진단용 부호 출현 추출기 — 부호별 위치·텍스트 높이·원본 텍스트 수집.

`counter.count_members` 는 개수만 돌려주므로 높이 진단·시각화에 쓸 수 없다.
이 모듈은 같은 매칭 규칙(`counter.match_symbol`)을 쓰되 각 출현의 좌표와
텍스트 height, 원본 문자열까지 모은다. 진단 스크립트(작업 4·5·6) 전용이며
카운팅 본선 코드(counter.py)는 건드리지 않는다.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import ezdxf

# poc_v2(=counter.py 위치)를 import 경로에 추가
_HERE = os.path.dirname(os.path.abspath(__file__))
_POC_DIR = os.path.dirname(_HERE)
for _path in (_POC_DIR, _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from counter import _clean_mtext, match_symbol  # noqa: E402


@dataclass(frozen=True)
class Occurrence:
    """도면에서 화이트리스트 부호가 한 번 출현한 기록."""

    symbol: str   # 매칭된 표준 부호 (예: "MC1")
    x: float
    y: float
    height: float  # 텍스트 height (TEXT) / char_height (MTEXT)
    raw: str       # 원본 텍스트 (부호 + 규격·주석 포함)


def _text_height(entity, dtype: str) -> float:
    """TEXT/MTEXT 엔티티의 글자 높이를 best-effort 로 추출한다."""
    try:
        if dtype == "MTEXT":
            return float(entity.dxf.char_height)
        return float(entity.dxf.height)
    except Exception:
        return 0.0


def extract_occurrences(
    dxf_path: str,
    whitelist: list[str] | set[str],
) -> list[Occurrence]:
    """도면 전체에서 화이트리스트 부호 출현을 모두 수집한다.

    counter.count_members 와 동일하게 TEXT/MTEXT 와 INSERT(ATTRIB·블록 내부
    TEXT)를 훑되, 각 출현의 좌표·height·원본 텍스트까지 기록한다.
    한 INSERT 안에서 같은 부호가 중복 집계되지 않도록 seen 으로 막는다.
    """
    whitelist_set = set(whitelist)
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    occurrences: list[Occurrence] = []

    for entity in msp:
        dtype = entity.dxftype()

        if dtype in ("TEXT", "MTEXT"):
            try:
                raw = entity.dxf.text
                text = _clean_mtext(raw) if dtype == "MTEXT" else raw.strip()
                sym = match_symbol(text, whitelist_set)
                if sym is None:
                    continue
                pt = entity.dxf.insert
                occurrences.append(Occurrence(
                    symbol=sym,
                    x=float(pt.x),
                    y=float(pt.y),
                    height=_text_height(entity, dtype),
                    raw=text,
                ))
            except Exception:
                pass

        elif dtype == "INSERT":
            try:
                pt = entity.dxf.insert
                x, y = float(pt.x), float(pt.y)
            except Exception:
                continue
            seen: set[str] = set()

            # 1. ATTRIB — INSERT 인스턴스 속성값
            try:
                for attrib in entity.attribs:
                    try:
                        val = (
                            attrib.dxf.text.strip()
                            if attrib.dxf.hasattr("text") else ""
                        )
                        sym = match_symbol(val, whitelist_set) if val else None
                        if sym and sym not in seen:
                            seen.add(sym)
                            try:
                                h = float(attrib.dxf.height)
                            except Exception:
                                h = 0.0
                            occurrences.append(
                                Occurrence(sym, x, y, h, val)
                            )
                    except Exception:
                        pass
            except Exception:
                pass

            # 2. 블록 정의 내부 TEXT/ATTDEF — ATTRIB 가 없을 때만
            if not seen:
                try:
                    block = doc.blocks.get(entity.dxf.name)
                    if block:
                        for be in block:
                            btype = be.dxftype()
                            if btype in ("TEXT", "ATTDEF"):
                                val = (
                                    be.dxf.text.strip()
                                    if be.dxf.hasattr("text") else ""
                                )
                            elif btype == "MTEXT":
                                val = (
                                    _clean_mtext(be.plain_mtext())
                                    if hasattr(be, "plain_mtext") else ""
                                )
                            else:
                                continue
                            sym = match_symbol(val, whitelist_set) if val else None
                            if sym and sym not in seen:
                                seen.add(sym)
                                h_type = "TEXT" if btype == "ATTDEF" else btype
                                occurrences.append(Occurrence(
                                    sym, x, y, _text_height(be, h_type), val,
                                ))
                except Exception:
                    pass

    return occurrences
