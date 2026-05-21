"""분류 진단 — 도면 텍스트별 좌표 + 분류 라벨 산출 (라운드 10).

baseline.compute_drawing 은 카운트(숫자)만 돌려준다. 시각화·진단을 위해
각 텍스트가 어떤 분류로 처리됐는지(본체로 카운트됐는지, 일람표/규격/필터로
제외됐는지) 좌표와 함께 돌려주는 진단용 함수.

counter.py·baseline.py·auto_policy.py·detect_table_region.py 미수정.
이 모듈은 룰을 새로 정의하지 않고 그대로 재사용한다.

분류 라벨 6종:
  counted            본체로 카운트 (final 에 반영)
  slash_combo_body   슬래시 결합 본체 (counted 의 하위 분류 — 도면3·5 의 "C1/P1")
  filtered_height    min_height 필터로 제외
  filtered_spec      "부호 + 규격" 안내 텍스트로 제외
  filtered_table     일람표 영역 안에 있어서 제외
  not_whitelist      화이트리스트 매칭 실패 (부호 아님 — 시각화 시 표시 안 함)
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Optional

import ezdxf

_HERE = os.path.dirname(os.path.abspath(__file__))
_POC_DIR = os.path.dirname(_HERE)
for _path in (_POC_DIR, _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from baseline import compute_drawing, _dxf_path  # noqa: E402
from counter import _clean_mtext, match_symbol  # noqa: E402


@dataclass(frozen=True)
class _TextRecord:
    """한 텍스트 엔티티의 원시 추출 결과 (분류 전)."""

    x: float
    y: float
    text: str
    height: Optional[float]
    source: str


def classify_drawing_texts(drawing: str) -> list[dict]:
    """도면의 모든 텍스트를 baseline 룰로 분류해 좌표·라벨 형태로 반환.

    Parameters
    ----------
    drawing
        도면명 ("도면1" ~ "도면5").

    Returns
    -------
    list of dict
        {x, y, text, symbol, height, source, category, in_region}
        category 는 위 6분류 중 하나.
    """
    dxf = _dxf_path(drawing)
    result = compute_drawing(drawing)
    expected_symbols = sorted(result["expected"].keys())
    whitelist = set(expected_symbols)
    policy = result["policy"]
    min_h = result["min_h"]
    regions = result["regions"]

    records = _extract_text_records(dxf)
    return [_classify(r, whitelist, policy, min_h, regions) for r in records]


def _extract_text_records(dxf_path: str) -> list[_TextRecord]:
    """DXF 의 modelspace 텍스트 + INSERT 하위 텍스트를 한 번에 수집."""
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    records: list[_TextRecord] = []

    for entity in msp:
        dtype = entity.dxftype()
        if dtype in ("TEXT", "MTEXT"):
            records.extend(_text_record(entity, dtype))
        elif dtype == "INSERT":
            records.extend(_insert_records(entity, doc))

    return records


def _text_record(entity, dtype: str) -> list[_TextRecord]:
    """modelspace TEXT/MTEXT 한 개를 _TextRecord 로 변환."""
    try:
        raw = entity.dxf.text
    except Exception:
        return []
    if not raw:
        return []
    text = _clean_mtext(raw) if dtype == "MTEXT" else raw.strip()
    if not text:
        return []
    try:
        pt = entity.dxf.insert
        x, y = float(pt.x), float(pt.y)
    except Exception:
        return []
    height = _safe_height(entity, dtype)
    return [_TextRecord(x=x, y=y, text=text, height=height, source=dtype)]


def _insert_records(entity, doc) -> list[_TextRecord]:
    """INSERT 의 ATTRIB·블록 정의 텍스트를 _TextRecord 로 변환.

    counter._collect_from_insert 와 동일한 우선순위 — ATTRIB 가 있으면
    블록 정의 텍스트는 무시. 동일 (INSERT, 텍스트) 중복은 제거.
    """
    try:
        pt = entity.dxf.insert
        x, y = float(pt.x), float(pt.y)
    except Exception:
        return []

    seen: set[str] = set()
    records: list[_TextRecord] = []

    try:
        attribs = list(entity.attribs)
    except Exception:
        attribs = []
    for attrib in attribs:
        try:
            val = attrib.dxf.text.strip() if attrib.dxf.hasattr("text") else ""
        except Exception:
            val = ""
        if not val or val in seen:
            continue
        seen.add(val)
        height = _safe_height(attrib, "ATTRIB")
        records.append(
            _TextRecord(x=x, y=y, text=val, height=height, source="INSERT_ATTRIB")
        )

    if records:
        return records

    try:
        block = doc.blocks.get(entity.dxf.name)
    except Exception:
        block = None
    if block is None:
        return records
    for be in block:
        btype = be.dxftype()
        if btype == "TEXT":
            try:
                val = be.dxf.text.strip() if be.dxf.hasattr("text") else ""
            except Exception:
                val = ""
        elif btype == "MTEXT":
            try:
                val = _clean_mtext(be.plain_mtext()) if hasattr(be, "plain_mtext") else ""
            except Exception:
                val = ""
        elif btype == "ATTDEF":
            try:
                val = be.dxf.text.strip() if be.dxf.hasattr("text") else ""
            except Exception:
                val = ""
        else:
            continue
        if not val or val in seen:
            continue
        seen.add(val)
        height = _safe_height(be, btype)
        records.append(
            _TextRecord(x=x, y=y, text=val, height=height, source="INSERT_BLOCK_TEXT")
        )

    return records


def _safe_height(entity, dtype: str) -> Optional[float]:
    """텍스트 height 안전 추출. MTEXT 는 char_height, 그 외는 height."""
    try:
        if dtype == "MTEXT":
            return float(entity.dxf.char_height)
        return float(entity.dxf.height)
    except Exception:
        return None


def _classify(
    record: _TextRecord,
    whitelist: set[str],
    policy: dict,
    min_h: Optional[float],
    regions: list[dict],
) -> dict:
    """단일 텍스트 레코드 → 분류 결과 dict.

    분류 순서 (라운드 10 사양):
      1) A 매칭 실패           → not_whitelist
      2) height < min_h        → filtered_height
      3) B_strict 실패 + B_combo 성공 (= 슬래시 결합)
         · policy.exclude_with_spec=True → slash_combo_body (본체 인정)
         · False                          → counted (정책 미적용)
      4) B_strict·B_combo 모두 실패 (= 순수 규격 텍스트)
         · policy.exclude_with_spec=True → filtered_spec
         · False                          → counted
      5) B_strict 성공 (단독형)            → counted
      6) 5 단계 통과 후 일람표 영역 + 자유 텍스트 + policy 활성 → filtered_table 로 덮어쓰기
    """
    match_a = match_symbol(
        record.text, whitelist, exclude_with_spec=False, treat_slash_as_combo=False
    )
    if match_a is None:
        return _to_dict(record, symbol=None, category="not_whitelist", in_region=None)

    if (
        min_h is not None
        and record.height is not None
        and record.height < min_h
    ):
        return _to_dict(record, symbol=match_a, category="filtered_height", in_region=None)

    match_b_strict = match_symbol(
        record.text, whitelist, exclude_with_spec=True, treat_slash_as_combo=False
    )
    match_b_combo = match_symbol(
        record.text, whitelist, exclude_with_spec=True, treat_slash_as_combo=True
    )

    if match_b_strict is None and match_b_combo is not None:
        if policy.get("exclude_with_spec"):
            category = "slash_combo_body"
        else:
            category = "counted"
    elif match_b_strict is None and match_b_combo is None:
        if policy.get("exclude_with_spec"):
            return _to_dict(
                record, symbol=match_a, category="filtered_spec", in_region=None
            )
        category = "counted"
    else:
        category = "counted"

    in_region = _find_region(record.x, record.y, regions)
    is_free_text = record.source in ("TEXT", "MTEXT")
    if (
        policy.get("exclude_table_regions")
        and is_free_text
        and in_region is not None
    ):
        return _to_dict(
            record, symbol=match_a, category="filtered_table", in_region=in_region
        )

    return _to_dict(record, symbol=match_a, category=category, in_region=in_region)


def _find_region(x: float, y: float, regions: list[dict]) -> Optional[int]:
    """좌표가 어떤 일람표 영역 bbox 에 포함되는지 인덱스 반환. 없으면 None."""
    for i, region in enumerate(regions):
        x0, y0, x1, y1 = region["bbox"]
        if x0 <= x <= x1 and y0 <= y <= y1:
            return i
    return None


def _to_dict(
    record: _TextRecord,
    symbol: Optional[str],
    category: str,
    in_region: Optional[int],
) -> dict:
    return {
        "x": record.x,
        "y": record.y,
        "text": record.text,
        "symbol": symbol,
        "height": record.height,
        "source": record.source,
        "category": category,
        "in_region": in_region,
    }
