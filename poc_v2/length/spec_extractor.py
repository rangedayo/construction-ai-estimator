"""부호↔규격 독립 추출기 — 라운드 길이-4.

DXF 의 modelspace TEXT/MTEXT 만 입력으로 사용해 일람표의 부호와 규격을
y-띠 매칭으로 페어링한다. 카운팅 파이프라인(counter.py / baseline.py) 과
완전히 독립 — height 필터·일람표 자동검출 모듈을 거치지 않는다.

처리 순서
    1) modelspace TEXT/MTEXT 수집 → 클린 문자열·height·좌표 추출
    2) 각 텍스트를 세 분류로 태깅
        - 부호 후보: `^[A-Z]{1,5}\\d{1,2}$` + steel_excluded 화이트리스트 차감
        - 규격 후보: 4-세그먼트 H형강 형식 + 정규화 후 4-세그먼트 보장
        - 동 라벨 후보: `\\((\\d+동)\\)` 포함 문자열
    3) 부호별로 y±tol·x>symbol.x 범위에서 최소 x-거리 규격 매칭
    4) 매칭된 부호의 동 지정: 거리(2D) 가장 가까운 동 라벨에서 추출
    5) (drawing, section, symbol) 중복 시 좌표 거리 가까운 페어를 채택

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

# 적산 외 부재 — 결과에서 항상 제외 (P 콘크리트 매입, BR·SBR 가새, MF 매트기초)
DEFAULT_EXCLUDED_PREFIXES: tuple[str, ...] = ("P", "BR", "SBR", "MF", "BRACE")


@dataclass(frozen=True)
class SpecExtraction:
    """(도면, 동, 부호) 단위 추출 결과."""
    drawing: str
    section: Optional[str]
    symbol: str
    spec_raw: str
    spec_normalized: str
    spec_note: Optional[str]
    symbol_coord: tuple[float, float]
    spec_coord: tuple[float, float]


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
    """DXF 에서 (도면, 동, 부호, 규격) 페어링 결과 리스트를 반환."""
    items = _collect_text_items(dxf_path)
    symbols, specs, sections = _classify(items, excluded_prefixes)

    candidates: dict[
        tuple[str, Optional[str], str], tuple[float, SpecExtraction]
    ] = {}
    for sym in symbols:
        y_tol = max(min_y_tolerance, y_tolerance_ratio * sym.height)
        matched = _match_symbol_to_spec(sym, specs, y_tol, max_x_distance)
        if matched is None:
            continue
        section = _assign_section(sym, sections)
        normalized = normalize_spec(matched.text)
        if not normalized:
            continue
        distance = ((matched.x - sym.x) ** 2 + (matched.y - sym.y) ** 2) ** 0.5
        extraction = SpecExtraction(
            drawing=drawing,
            section=section,
            symbol=sym.text,
            spec_raw=matched.text,
            spec_normalized=normalized,
            spec_note=None,
            symbol_coord=(sym.x, sym.y),
            spec_coord=(matched.x, matched.y),
        )
        key = (drawing, section, sym.text)
        existing = candidates.get(key)
        if existing is None or distance < existing[0]:
            candidates[key] = (distance, extraction)

    return [v[1] for v in candidates.values()]
