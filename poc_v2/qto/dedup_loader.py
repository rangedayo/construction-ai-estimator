"""`config/dedup_routing.yaml` 로더 — 라운드 중량-1a/1b.

같은 (도면, 부호) 가 여러 시트에 등장하는 중복 함정에서 "어느 시트 값을
칠지" 를 사람이 yaml 로 명시한다. 본 모듈은 그 yaml 을 읽기만 한다 — 결정은
사람(yaml) 의 일, 코드는 지시받은 시트만 따른다.

스키마 (1b 확장 포함)::

    도면4:                         # 단일 섹션 (동 구분 없음)
      기둥:
        SC1: {count_from: "1층 구조평면도", spec_from: "1층 구조평면도"}

    도면1:                         # by_section — 동·구역별 분리
      by_section:
        1동: {skip: true, skip_reason: "..."}
        2동:
          기둥:
            MC1: {count_from: "(2동)기둥주심도", spec_from: "(2동)기둥주심도"}

    도면2:                         # count_override — 측정 한계 격리
      기둥:
        SC1: {count_override: 10, spec_from: "가,나동 1층 구조평면도"}

필드 규칙
    * spec_from 은 항상 필수(비어있으면 ValueError).
    * count_from / count_override 는 **정확히 하나만** 있어야 한다.
    * count_override 는 양의 정수.
    * skip:true 인 섹션은 SkipMarker 로 분리, 라우팅에서 제외.

`length_routing.yaml` 패턴과 동일하게 pyyaml 부재 시 use 시점에 ImportError.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
DEFAULT_DEDUP_PATH = os.path.join(PROJECT_ROOT, "config", "dedup_routing.yaml")

_BY_SECTION_KEY = "by_section"


@dataclass(frozen=True)
class DedupRoute:
    """한 (도면, 섹션, 부재종류, 부호) 의 중복 라우팅."""
    drawing: str
    section: Optional[str]          # "1동" | "2동" | None (단일 섹션)
    member_kind: str                # "기둥" | "보" (이번 라운드는 "기둥"만)
    symbol: str
    count_from: Optional[str]       # 카운트 시트명. count_override 시 None.
    count_override: Optional[int]   # 측정 대신 쓸 정답 카운트. count_from 시 None.
    spec_from: str                  # 규격을 가져올 시트명 (항상 필수)


@dataclass(frozen=True)
class SkipMarker:
    """산출 대상에서 제외되는 (도면, 섹션) 과 그 사유."""
    drawing: str
    section: Optional[str]
    reason: str


def _require_sheet(value: object, *, ctx: str, field: str) -> str:
    """시트명이 비어있지/None 이 아닌 문자열인지 검증 후 반환."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"dedup_routing.yaml: {ctx} 의 {field} 가 비어있거나 문자열이 아님 ({value!r})"
        )
    return value.strip()


def _parse_count(fields: dict, *, ctx: str) -> tuple[Optional[str], Optional[int]]:
    """fields 에서 count_from XOR count_override 를 검증·추출."""
    has_from = "count_from" in fields and fields["count_from"] is not None
    has_override = "count_override" in fields and fields["count_override"] is not None

    if has_from and has_override:
        raise ValueError(
            f"dedup_routing.yaml: {ctx} 에 count_from 과 count_override 가 동시 존재 "
            f"— 정확히 하나만 허용"
        )
    if not has_from and not has_override:
        raise ValueError(
            f"dedup_routing.yaml: {ctx} 에 count_from 도 count_override 도 없음"
        )

    if has_override:
        raw = fields["count_override"]
        if not isinstance(raw, int) or isinstance(raw, bool) or raw < 0:
            raise ValueError(
                f"dedup_routing.yaml: {ctx} 의 count_override 가 음이 아닌 정수가 아님 ({raw!r})"
            )
        return None, raw

    return _require_sheet(fields["count_from"], ctx=ctx, field="count_from"), None


def _parse_kinds(
    drawing: str,
    section: Optional[str],
    kinds: dict,
    routes: list[DedupRoute],
    seen: set[tuple[str, Optional[str], str]],
) -> None:
    """member_kind → symbol → fields 한 덩이를 DedupRoute 들로 평탄화."""
    for member_kind, symbols in kinds.items():
        if not isinstance(symbols, dict):
            continue
        for symbol, fields in symbols.items():
            ctx = f"{drawing}/{section or '-'}/{member_kind}/{symbol}"
            if not isinstance(fields, dict):
                raise ValueError(f"dedup_routing.yaml: {ctx} 본문이 매핑이 아님 ({fields!r})")

            key = (drawing, section, str(symbol))
            if key in seen:
                raise ValueError(
                    f"dedup_routing.yaml: ({drawing}, {section}, {symbol}) 중복 정의됨 "
                    f"— 한 (도면,섹션,부호) 는 한 번만 라우팅 가능"
                )
            seen.add(key)

            count_from, count_override = _parse_count(fields, ctx=ctx)
            spec_from = _require_sheet(fields.get("spec_from"), ctx=ctx, field="spec_from")
            routes.append(DedupRoute(
                drawing=drawing,
                section=section,
                member_kind=str(member_kind),
                symbol=str(symbol),
                count_from=count_from,
                count_override=count_override,
                spec_from=spec_from,
            ))


def load_dedup(path: str | None = None) -> tuple[list[DedupRoute], list[SkipMarker]]:
    """확장 yaml 을 (DedupRoute 리스트, SkipMarker 리스트) 로 파싱.

    - `by_section`: 도면 아래 동·구역 키 → section 필드 채움
    - `skip: true`: SkipMarker 로 분리, 라우팅 제외
    - `count_override`: 정답 카운트 보존, count_from 은 None
    """
    import yaml  # noqa: PLC0415 — optional dep, fail fast at use time

    cfg_path = path or DEFAULT_DEDUP_PATH
    if not os.path.exists(cfg_path):
        raise FileNotFoundError(f"dedup_routing.yaml not found: {cfg_path}")
    with open(cfg_path, encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}

    if not isinstance(config, dict):
        raise ValueError(f"{cfg_path} 최상위가 매핑이 아님: {type(config).__name__}")

    routes: list[DedupRoute] = []
    skips: list[SkipMarker] = []
    seen: set[tuple[str, Optional[str], str]] = set()

    for drawing, body in config.items():
        if not isinstance(body, dict):
            continue  # 메모·스칼라 무시
        drawing = str(drawing)

        if _BY_SECTION_KEY in body:
            sections = body[_BY_SECTION_KEY]
            if not isinstance(sections, dict):
                raise ValueError(f"dedup_routing.yaml: {drawing}/by_section 이 매핑이 아님")
            for section, sec_body in sections.items():
                section = str(section)
                if not isinstance(sec_body, dict):
                    continue
                if sec_body.get("skip"):
                    skips.append(SkipMarker(
                        drawing=drawing,
                        section=section,
                        reason=str(sec_body.get("skip_reason", "")),
                    ))
                    continue
                _parse_kinds(drawing, section, sec_body, routes, seen)
        else:
            _parse_kinds(drawing, None, body, routes, seen)

    return routes, skips


def load_dedup_routing(path: str | None = None) -> list[DedupRoute]:
    """DedupRoute 리스트만 반환 (skip 제외). 1a 호환 진입점."""
    routes, _skips = load_dedup(path)
    return routes


def routes_for_drawing(drawing: str, path: str | None = None) -> list[DedupRoute]:
    """특정 도면의 라우팅만 추려 반환 (정렬: 섹션 → 부재종류 → 부호)."""
    routes = [r for r in load_dedup_routing(path) if r.drawing == drawing]
    return sorted(routes, key=lambda r: (r.section or "", r.member_kind, r.symbol))


def skips_for_drawing(drawing: str, path: str | None = None) -> list[SkipMarker]:
    """특정 도면의 SkipMarker 만 추려 반환 (정렬: 섹션)."""
    _routes, skips = load_dedup(path)
    return sorted(
        (s for s in skips if s.drawing == drawing),
        key=lambda s: s.section or "",
    )
