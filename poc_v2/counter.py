"""부재 부호 카운팅 로직 — DXF TEXT/MTEXT 및 INSERT 블록 엔티티 기반"""
import re
from collections import Counter
from typing import Callable

import ezdxf

WHITELIST = {
    "MC1", "MC2", "MC3", "SC1", "SC2",
    "SG1", "SG2", "SG3", "WG1", "CRG1", "VG1", "MT1",
    "SB1", "SB2", "SB3", "VT1",
    "RSG1", "RSG2", "RSG3", "RSB1", "RSB2", "RSB3",
    "BR1", "BR2",
}

_MTEXT_ESCAPE = re.compile(r"\{[^}]*\}|\\[A-Za-z0-9.:;-]+;?|[{}]")
_AUTO_DETECT = re.compile(r"^[A-Z]{1,5}\d{1,2}$")


def _clean_mtext(raw: str) -> str:
    return _MTEXT_ESCAPE.sub("", raw).strip()


def match_symbol(
    text: str,
    whitelist: set[str],
    exclude_with_spec: bool = False,
) -> str | None:
    """텍스트를 화이트리스트 부호와 매칭한다 — 정확 일치 + 안전한 부분 일치.

    "BR2 L-80X80X7" → "BR2", "MC1 추가" → "MC1" 처럼 부호 뒤에 규격·주석이
    붙은 경우도 잡는다. 단 "MC10"이 "MC1"으로 잘못 매칭되지 않도록, 부호 뒤
    첫 글자가 숫자이면 다른 부호로 보고 건너뛴다.

    exclude_with_spec
        False(기본) → 기존 동작 그대로. 부호 뒤 공백/하이픈이 와도 부호로 매칭.
        True         → 라운드 5 정책 P 신호 2. '부호 + 공백/하이픈/줄바꿈(\\P)
                       + 규격' 형태(예: "SC1 350x175x7/11")는 규격 안내 표기로
                       보고 카운트에서 제외(None 반환). 정확 일치는 그대로 통과.

    주의: exclude_with_spec=True 를 BR2 가 있는 도면에 쓰면 "BR2 L-80X80X7"
    매칭이 깨진다. 도면4 처럼 BR2 가 없는 도면에서만 활성화할 것.
    """
    text = text.strip()
    if text in whitelist:
        return text
    # 긴 부호부터 검사해 "RSG1" 같은 부호가 짧은 부호에 가로채이지 않게 한다.
    for w in sorted(whitelist, key=len, reverse=True):
        if text.startswith(w):
            after = text[len(w):]
            if not after:
                return w
            if after[0] in (" ", "-"):
                # 규격 안내 표기 제외 모드: 부호 뒤 규격이 붙으면 카운트 안 함
                if exclude_with_spec:
                    return None
                return w
            # MTEXT \P(줄바꿈) 뒤 규격이 붙은 형태도 규격 안내로 본다
            if exclude_with_spec and after.startswith("\\P"):
                return None
            # "MC1" 뒤에 숫자가 오면 "MC10" 같은 다른 부호임 → 매칭 안 함
            if after[0].isdigit():
                continue
    return None


def _text_height(entity, dtype: str) -> float | None:
    """텍스트 엔티티의 글자 높이를 추출한다. 없으면 None.

    MTEXT 는 char_height, 그 외(TEXT/ATTRIB/ATTDEF)는 height 속성을 쓴다.
    """
    try:
        if dtype == "MTEXT":
            return float(entity.dxf.char_height)
        return float(entity.dxf.height)
    except Exception:
        return None


def _height_ok(entity, dtype: str, min_text_height: float | None) -> bool:
    """height 필터 통과 여부. 필터 미적용이거나 height 정보가 없으면 통과."""
    if min_text_height is None:
        return True
    height = _text_height(entity, dtype)
    if height is None:
        return True  # height 정보 없는 엔티티는 안전하게 통과 (필터 대상 아님)
    return height >= min_text_height


def _collect_from_insert(
    entity,
    doc,
    match_fn: Callable[[str], str | None],
    min_text_height: float | None = None,
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
                sym = match_fn(val) if val else None
                if (
                    sym and sym not in seen
                    and _height_ok(attrib, "ATTRIB", min_text_height)
                ):
                    found.append((x, y, sym))
                    seen.add(sym)
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
                    sym = match_fn(val) if val else None
                    if (
                        sym and sym not in seen
                        and _height_ok(be, btype, min_text_height)
                    ):
                        found.append((x, y, sym))
                        seen.add(sym)
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
    min_text_height: float | None = None,
    exclude_with_spec: bool = False,
) -> tuple[Counter, list[tuple[float, float, str]], dict[str, list[tuple[float, float]]]]:
    """
    Parameters
    ----------
    custom_whitelist
        None  → 자동 감지 (영문 대문자 1~5자 + 숫자 1~2자 패턴)
        list  → 해당 부호만 카운트
    min_text_height
        None  → height 필터 미적용 (모든 height 카운트, 기존 동작)
        숫자  → 텍스트 height 가 그 값 이상인 엔티티만 카운트.
                height 정보가 없는 엔티티는 안전하게 통과시킨다.
    exclude_with_spec
        False(기본) → 기존 동작.
        True         → 라운드 5 정책 P 신호 2. '부호 + 규격' 형태 텍스트
                       (예: "SC1 350x175x7/11")를 카운트에서 제외한다.
                       custom_whitelist 가 지정된 경우에만 효과가 있다.

    Returns
    -------
    counts          : Counter  {symbol: count}
    hits            : list of (x, y, symbol) for matched entities
    coords_by_symbol: dict {symbol: [(x, y), ...]}
    """
    if custom_whitelist is None:
        match_fn: Callable[[str], str | None] = (
            lambda t: t.strip() if _AUTO_DETECT.match(t.strip()) else None
        )
    else:
        whitelist_set = set(custom_whitelist)
        match_fn = lambda t: match_symbol(t, whitelist_set, exclude_with_spec)

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
                sym = match_fn(text)
                if sym is None:
                    continue
                if not _height_ok(entity, dtype, min_text_height):
                    continue
                pt = entity.dxf.insert
                x, y = float(pt.x), float(pt.y)
                if xmin <= x <= xmax and ymin <= y <= ymax:
                    _record(x, y, sym)
            except Exception:
                pass

        elif dtype == "INSERT":
            for x, y, text in _collect_from_insert(
                entity, doc, match_fn, min_text_height
            ):
                if xmin <= x <= xmax and ymin <= y <= ymax:
                    _record(x, y, text)

    return counts, hits, coords_by_symbol


def diagnose_duplicate_coords(
    coords_by_symbol: dict[str, list[tuple[float, float]]],
    tolerance_mm: float = 1.0,
) -> dict[str, list[dict]]:
    """동일 좌표(tolerance 이내) 부호 중복 진단 — 라운드 5 정책 P 신호 3.

    같은 부호의 엔티티가 tolerance_mm 이내 거의 같은 좌표에 2개 이상 겹쳐 있는
    곳을 찾는다. 자동 제거는 하지 않는다(카운트는 그대로). 적산 전문가 검수
    단계에 넘길 경고 메모용 진단 정보만 돌려준다.

    Returns
    -------
    {부호: [{"coord": (x, y), "count": n}, ...]}
        n >= 2 인 중복 지점만 포함. 중복이 없는 부호는 키 자체가 없다.
    """
    result: dict[str, list[dict]] = {}
    for symbol, coords in coords_by_symbol.items():
        # 대표 좌표 단위로 묶는다 — [rep_x, rep_y, count]
        groups: list[list[float]] = []
        for x, y in coords:
            for group in groups:
                if (
                    abs(x - group[0]) <= tolerance_mm
                    and abs(y - group[1]) <= tolerance_mm
                ):
                    group[2] += 1
                    break
            else:
                groups.append([x, y, 1])
        dups = [
            {"coord": (g[0], g[1]), "count": int(g[2])}
            for g in groups
            if g[2] >= 2
        ]
        if dups:
            result[symbol] = dups
    return result
