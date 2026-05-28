"""부호↔규격 독립 추출기 — 라운드 길이-4.

DXF 의 modelspace TEXT/MTEXT 만 입력으로 사용해 일람표의 부호와 규격을
y-띠 매칭으로 페어링한다. 카운팅 파이프라인(counter.py / baseline.py) 과
완전히 독립 — height 필터·일람표 자동검출 모듈을 거치지 않는다.

처리 순서
    1) modelspace TEXT/MTEXT 수집 → 클린 문자열·height·좌표 추출
    2) 각 텍스트를 분류로 태깅
        - 부호 후보: `^[A-Z]{1,5}\\d{1,2}$` + steel_excluded 화이트리스트 차감
        - 규격 후보: 4-세그먼트 H형강 형식 + 정규화 후 4-세그먼트 보장
        - 동 라벨 후보: `\\((\\d+동)\\)` 포함 문자열
        - 시트 제목 후보: 평면도·단면도·주심도·부호도·골구도·입면도 등
        - 일람표 제목 후보: `일람표` / `MEMBER LIST`
    3) 부호별로 y±tol·x>symbol.x 범위에서 최소 x-거리 규격 매칭
    4) 매칭된 부호의 동·출처 지정: 거리(2D) 가장 가까운 동 라벨/시트 제목/일람표
       제목에서 추출
    5) 전수 보존(라운드 규격-1, C안) — dedupe 하지 않고 매칭된 모든 페어를 반환.
       같은 (drawing, symbol) 이 1층·지붕층 등 여러 위치에 있으면 각각 보존하고,
       출처(source_sheet, source_table_title) 로 구분한다. "어느 위치 규격을
       쓸지" 결정은 LLM 라우팅 라운드의 일 — 여기서는 측정만 한다.

매개변수는 함수 인자로 노출 — yaml 신설 없이 호출자가 조정 가능.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from typing import Optional

import ezdxf

_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from poc_v2.length.ground_truth_spec import normalize_spec  # noqa: E402

_MTEXT_ESCAPE = re.compile(r"\{[^}]*\}|\\[A-Za-z0-9.:;-]+;?|[{}]")
_SYMBOL_RE = re.compile(r"^[A-Z]{1,5}\d{1,2}$")
# 4-세그먼트 H형강 — `H?\s*-?\s*N[x×/]N[x×/]N(.N)?[x×/]N(.N)?`
_SPEC_RE = re.compile(
    r"^H?\s*-?\s*\d{2,4}"
    r"\s*[xX×/]\s*\d{2,4}"
    r"\s*[xX×/]\s*\d+(?:\.\d+)?"
    r"\s*[xX×/]\s*\d+(?:\.\d+)?\s*$"
)
_SECTION_RE = re.compile(r"\((\d+동)\)")
# 시트 제목 — 도면류 (일람표는 별도). 한 글자라도 포함하면 시트 제목 후보.
_SHEET_TITLE_RE = re.compile(r"(평면도|단면도|주심도|부호도|골구도|입면도|배치도|상세도)")
# 일람표(부재 리스트) 제목 — `일람표` 또는 `MEMBER LIST`.
_TABLE_TITLE_RE = re.compile(r"(일람표|MEMBER\s*LIST)", re.IGNORECASE)

# 적산 외 부재 — 결과에서 항상 제외 (P 콘크리트 매입, BR·SBR 가새, MF 매트기초)
DEFAULT_EXCLUDED_PREFIXES: tuple[str, ...] = ("P", "BR", "SBR", "MF", "BRACE")


@dataclass(frozen=True)
class SpecExtraction:
    """(도면, 동, 부호) 단위 추출 결과 — 전수 보존(dedupe 없음).

    같은 (drawing, symbol) 이 여러 위치에서 나오면 각각 별도 인스턴스로 보존되며
    source_sheet / source_table_title 로 출처가 구분된다.
    """
    drawing: str
    section: Optional[str]
    symbol: str
    spec_raw: str
    spec_normalized: str
    spec_note: Optional[str]
    symbol_coord: tuple[float, float]
    spec_coord: tuple[float, float]
    # 출처 정보 (라운드 규격-1, C안) — LLM 라우팅이 위치를 고를 수 있게 보존.
    source_sheet: Optional[str] = None        # "1층구조평면도" | "(1동) 기둥주심도-1" 등
    source_table_title: Optional[str] = None  # "기둥 일람표" | "MEMBER LIST" 등


@dataclass(frozen=True)
class _TextItem:
    text: str
    x: float
    y: float
    height: float


def _clean(raw: str) -> str:
    return _MTEXT_ESCAPE.sub("", raw).strip()


def _is_excluded(symbol: str, excluded_prefixes: tuple[str, ...]) -> bool:
    """부호명이 적산 외 접두사로 시작하는지. 기둥 C 와 충돌하지 않게 정확 매칭."""
    for p in excluded_prefixes:
        if symbol == p:
            return True
        if symbol.startswith(p) and len(symbol) > len(p) and symbol[len(p)].isdigit():
            return True
    return False


def _collect_text_items(dxf_path: str) -> list[_TextItem]:
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    items: list[_TextItem] = []
    for entity in msp:
        kind = entity.dxftype()
        if kind == "TEXT":
            raw = entity.dxf.text
            height = float(entity.dxf.height)
        elif kind == "MTEXT":
            raw = entity.text
            height = float(entity.dxf.char_height)
        else:
            continue
        cleaned = _clean(raw)
        if not cleaned:
            continue
        try:
            insert = entity.dxf.insert
        except AttributeError:
            continue
        items.append(_TextItem(cleaned, float(insert.x), float(insert.y), height))
    return items


def _classify(
    items: list[_TextItem], excluded_prefixes: tuple[str, ...]
) -> tuple[list[_TextItem], list[_TextItem], list[tuple[str, _TextItem]]]:
    """텍스트 리스트를 (부호, 규격, 동라벨) 로 분류."""
    symbols: list[_TextItem] = []
    specs: list[_TextItem] = []
    sections: list[tuple[str, _TextItem]] = []
    for item in items:
        section_match = _SECTION_RE.search(item.text)
        if section_match:
            sections.append((section_match.group(1), item))

        if _SYMBOL_RE.match(item.text):
            if not _is_excluded(item.text, excluded_prefixes):
                symbols.append(item)
            continue

        if _SPEC_RE.match(item.text):
            normalized = normalize_spec(item.text)
            # 정규화 후에도 4-세그먼트(=구분자 3개) 보장
            if normalized.count("x") + normalized.count("/") >= 3:
                specs.append(item)
    return symbols, specs, sections


def _assign_section(
    symbol_item: _TextItem, sections: list[tuple[str, _TextItem]]
) -> Optional[str]:
    """매칭된 부호 좌표에서 2D 거리 가장 가까운 동 라벨을 채택."""
    if not sections:
        return None
    best_label: Optional[str] = None
    best_dist = float("inf")
    sx, sy = symbol_item.x, symbol_item.y
    for label, item in sections:
        dx = item.x - sx
        dy = item.y - sy
        dist = (dx * dx + dy * dy) ** 0.5
        if dist < best_dist:
            best_dist = dist
            best_label = label
    return best_label


def _collect_titles(
    items: list[_TextItem],
) -> tuple[list[_TextItem], list[_TextItem]]:
    """텍스트에서 (시트 제목, 일람표 제목) 후보를 수집.

    `_classify` 와 분리해 둔다 — 기존 호출부(dump 진단 등)의 3-튜플 시그니처를
    깨지 않기 위해 별도 패스로 처리한다.
    """
    sheet_titles: list[_TextItem] = []
    table_titles: list[_TextItem] = []
    for item in items:
        if _TABLE_TITLE_RE.search(item.text):
            table_titles.append(item)
        elif _SHEET_TITLE_RE.search(item.text):
            sheet_titles.append(item)
    return sheet_titles, table_titles


def _nearest_title(
    coord: tuple[float, float], titles: list[_TextItem]
) -> Optional[str]:
    """좌표에서 2D 거리 가장 가까운 제목 텍스트. 후보 없으면 None.

    시트 제목용 — 평면도 등은 일람표 영역 아래쪽에 있고 같은 층끼리 x 가 가까워
    단순 2D 최근접으로 1층/지붕층이 올바로 갈린다.
    """
    if not titles:
        return None
    cx, cy = coord
    best_text: Optional[str] = None
    best_dist = float("inf")
    for item in titles:
        dx = item.x - cx
        dy = item.y - cy
        dist = dx * dx + dy * dy
        if dist < best_dist:
            best_dist = dist
            best_text = item.text
    return best_text


def _nearest_title_above(
    coord: tuple[float, float], titles: list[_TextItem]
) -> Optional[str]:
    """좌표보다 위(y 큰)에 있는 제목 중 2D 거리 최근접 텍스트. 없으면 None.

    일람표 제목용 — 일람표는 헤더가 표 위에 붙고 좌우로 여러 표가 세로로 쌓여
    있어, 단순 2D 최근접은 한 칸 아래 표의 헤더(예: 기둥 행이 아래쪽 가새 헤더)
    를 잘못 집는다. '부호보다 위에 있는' 헤더로 제한하면, 2D 거리가 같은 열의
    바로 위 헤더를 고르게 되어 열·표 구분이 자연스럽게 된다.
    """
    above = [t for t in titles if t.y > coord[1]]
    return _nearest_title(coord, above)


def _match_symbol_to_spec(
    symbol: _TextItem,
    specs: list[_TextItem],
    y_tol: float,
    max_x_distance: float,
) -> Optional[_TextItem]:
    """부호와 같은 y-띠에 있고 x 가 큰(=우측) 가장 가까운 규격 후보."""
    best: Optional[_TextItem] = None
    best_dx = float("inf")
    for spec in specs:
        if abs(spec.y - symbol.y) > y_tol:
            continue
        dx = spec.x - symbol.x
        if dx <= 0 or dx > max_x_distance:
            continue
        if dx < best_dx:
            best_dx = dx
            best = spec
    return best


def extract_specs(
    dxf_path: str,
    drawing: str,
    *,
    excluded_prefixes: tuple[str, ...] = DEFAULT_EXCLUDED_PREFIXES,
    y_tolerance_ratio: float = 0.5,
    min_y_tolerance: float = 50.0,
    max_x_distance: float = 5000.0,
) -> list[SpecExtraction]:
    """DXF 에서 (도면, 동, 부호, 규격) 페어링 결과 리스트를 반환.

    전수 보존(C안): dedupe 하지 않는다. 매칭된 모든 부호↔규격 페어를 반환하며,
    같은 (drawing, symbol) 이 여러 위치(예: 도면4 1층·지붕층 일람표)에서 나오면
    각각 별도 인스턴스로 보존하고 source_sheet / source_table_title 로 구분한다.
    """
    items = _collect_text_items(dxf_path)
    symbols, specs, sections = _classify(items, excluded_prefixes)
    sheet_titles, table_titles = _collect_titles(items)

    results: list[SpecExtraction] = []
    for sym in symbols:
        y_tol = max(min_y_tolerance, y_tolerance_ratio * sym.height)
        matched = _match_symbol_to_spec(sym, specs, y_tol, max_x_distance)
        if matched is None:
            continue
        normalized = normalize_spec(matched.text)
        if not normalized:
            continue
        section = _assign_section(sym, sections)
        coord = (sym.x, sym.y)
        results.append(
            SpecExtraction(
                drawing=drawing,
                section=section,
                symbol=sym.text,
                spec_raw=matched.text,
                spec_normalized=normalized,
                spec_note=None,
                symbol_coord=coord,
                spec_coord=(matched.x, matched.y),
                source_sheet=_nearest_title(coord, sheet_titles),
                source_table_title=_nearest_title_above(coord, table_titles),
            )
        )

    return results
