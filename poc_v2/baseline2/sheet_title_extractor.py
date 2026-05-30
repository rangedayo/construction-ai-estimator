"""표제부 도면명 추출기 — 라운드 베이스라인-2 작업 1.

작은 도면 dxf 1장의 modelspace TEXT/MTEXT 에서 "도면명"(표제부 제목)을 추출한다.
파일명은 쓰지 않는다 — dxf 내부 표제부 텍스트가 정답지 시트명 매칭의 키다.

휴리스틱 (결정론적, LLM 0건)
    1. modelspace TEXT/MTEXT 수집 (MTEXT 이스케이프 제거)
    2. 도면명 키워드(_TITLE_KEYWORDS) 포함 텍스트만 후보화
    3. 점수 = height (주) + 위치 가점 (표제부는 보통 우측·하단)
    4. 최고점 후보 채택. 동률(_SCORE_TIE_RATIO 이내)이면 모두 반환
       (도면4 "단면도" 처럼 한 후보만 나오는 경우가 일반적).

본선 무수정 — 이 모듈은 ezdxf 만 직접 쓴다.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass

import ezdxf

_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

_MTEXT_ESCAPE = re.compile(r"\{[^}]*\}|\\[A-Za-z0-9.:;-]+;?|[{}]")

# 도면명 키워드 — 하나라도 포함하면 표제부 제목 후보.
_TITLE_KEYWORDS: tuple[str, ...] = (
    "평면도", "단면도", "입면도", "주심도", "부호도", "골구도", "골조도",
    "정면도", "측면도", "배면도", "구조도", "보복도",
)

# 위치 가점 — 텍스트 분포 기준 우측·하단(표제부 영역) 비율 임계값.
_RIGHT_FRACTION = 0.5
_BOTTOM_FRACTION = 0.5
_POSITION_BONUS = 0.15  # height 대비 가점 비율 (최고 height 의 15%)
# 동률 판정 — 최고점의 이 비율 이상이면 같은 순위로 보고 함께 반환.
_SCORE_TIE_RATIO = 0.98


@dataclass(frozen=True)
class SheetTitle:
    """표제부에서 추출한 도면명 후보 1건."""
    raw_text: str
    height: float
    coord: tuple[float, float]
    score: float


@dataclass(frozen=True)
class _TextItem:
    text: str
    x: float
    y: float
    height: float


def _clean(raw: str) -> str:
    return _MTEXT_ESCAPE.sub("", raw).strip()


def _collect_text_items(dxf_path: str) -> list[_TextItem]:
    """modelspace 의 TEXT/MTEXT → (clean text, x, y, height)."""
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


def _is_title_candidate(text: str) -> bool:
    return any(keyword in text for keyword in _TITLE_KEYWORDS)


def _text_extent(items: list[_TextItem]) -> tuple[float, float, float, float]:
    """텍스트 좌표 분포의 bbox (xmin, ymin, xmax, ymax)."""
    xs = [it.x for it in items]
    ys = [it.y for it in items]
    return (min(xs), min(ys), max(xs), max(ys))


def extract_sheet_titles(dxf_path: str) -> list[SheetTitle]:
    """작은 도면 dxf 의 표제부 도면명 후보 리스트 (점수 내림차순).

    후보가 없으면 빈 리스트. 보통 1개, 모호하면 동률 후보를 함께 반환한다.
    """
    items = _collect_text_items(dxf_path)
    candidates = [it for it in items if _is_title_candidate(it.text)]
    if not candidates:
        return []

    xmin, ymin, xmax, ymax = _text_extent(items)
    width = (xmax - xmin) or 1.0
    height_span = (ymax - ymin) or 1.0
    max_height = max(it.height for it in candidates) or 1.0

    scored: list[SheetTitle] = []
    for it in candidates:
        score = it.height
        right = (it.x - xmin) / width >= _RIGHT_FRACTION
        bottom = (it.y - ymin) / height_span <= (1.0 - _BOTTOM_FRACTION)
        if right and bottom:
            score += max_height * _POSITION_BONUS
        scored.append(SheetTitle(it.text, it.height, (it.x, it.y), score))

    scored.sort(key=lambda s: s.score, reverse=True)
    top = scored[0].score
    return [s for s in scored if s.score >= top * _SCORE_TIE_RATIO]


def extract_title_texts(dxf_path: str) -> list[str]:
    """추출된 도면명 텍스트만 (매칭기 입력용 편의 함수)."""
    return [t.raw_text for t in extract_sheet_titles(dxf_path)]
