"""`config/dedup_routing.yaml` 로더 — 라운드 중량-1a.

같은 (도면, 부호) 가 여러 시트에 등장하는 중복 함정에서 "어느 시트 값을
칠지" 를 사람이 yaml 로 명시한다. 본 모듈은 그 yaml 을 읽기만 한다 — 결정은
사람(yaml) 의 일, 코드는 지시받은 시트만 따른다.

스키마 (도면4 예시)::

    도면4:
      기둥:
        SC1:
          count_from: "1층 구조평면도"
          spec_from: "1층 구조평면도"

`length_routing.yaml` 패턴과 동일하게 pyyaml 부재 시 use 시점에 ImportError.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
DEFAULT_DEDUP_PATH = os.path.join(PROJECT_ROOT, "config", "dedup_routing.yaml")


@dataclass(frozen=True)
class DedupRoute:
    """한 (도면, 부재종류, 부호) 의 중복 라우팅 — 어느 시트에서 측정할지."""
    drawing: str
    member_kind: str   # "기둥" | "보" (이번 라운드는 "기둥"만)
    symbol: str
    count_from: str    # 카운트를 가져올 시트명
    spec_from: str     # 규격을 가져올 시트명


def _require_sheet(value: object, *, drawing: str, kind: str, symbol: str,
                   field: str) -> str:
    """시트명이 비어있지/None 이 아닌 문자열인지 검증 후 반환."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"dedup_routing.yaml: {drawing}/{kind}/{symbol} 의 {field} 가 "
            f"비어있거나 문자열이 아님 ({value!r})"
        )
    return value.strip()


def load_dedup_routing(path: str | None = None) -> list[DedupRoute]:
    """config/dedup_routing.yaml 을 파싱해 평면 DedupRoute 리스트로 반환.

    검증
        * count_from / spec_from 가 빈 문자열·None 이면 ValueError.
        * 같은 (도면, 부호) 가 여러 번 등장하면 ValueError (사람 실수 잡기).
        * 주석(`#`) 키나 비-dict 본문은 무시(메모 블록 허용).
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
    seen: set[tuple[str, str]] = set()  # (drawing, symbol) 중복 검출

    for drawing, kinds in config.items():
        if not isinstance(kinds, dict):
            continue  # 메모·스칼라 등 무시
        for member_kind, symbols in kinds.items():
            if not isinstance(symbols, dict):
                continue
            for symbol, fields in symbols.items():
                if not isinstance(fields, dict):
                    raise ValueError(
                        f"dedup_routing.yaml: {drawing}/{member_kind}/{symbol} "
                        f"본문이 매핑이 아님 ({fields!r})"
                    )
                key = (str(drawing), str(symbol))
                if key in seen:
                    raise ValueError(
                        f"dedup_routing.yaml: ({drawing}, {symbol}) 가 중복 정의됨 "
                        f"— 한 부호는 한 번만 라우팅 가능"
                    )
                seen.add(key)

                count_from = _require_sheet(
                    fields.get("count_from"), drawing=str(drawing),
                    kind=str(member_kind), symbol=str(symbol), field="count_from",
                )
                spec_from = _require_sheet(
                    fields.get("spec_from"), drawing=str(drawing),
                    kind=str(member_kind), symbol=str(symbol), field="spec_from",
                )
                routes.append(DedupRoute(
                    drawing=str(drawing),
                    member_kind=str(member_kind),
                    symbol=str(symbol),
                    count_from=count_from,
                    spec_from=spec_from,
                ))

    return routes


def routes_for_drawing(drawing: str, path: str | None = None) -> list[DedupRoute]:
    """특정 도면의 라우팅만 추려 반환 (정렬: 부재종류 → 부호)."""
    routes = [r for r in load_dedup_routing(path) if r.drawing == drawing]
    return sorted(routes, key=lambda r: (r.member_kind, r.symbol))
