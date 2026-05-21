"""정책 자동 활성화 — 신호 2·3 한정 (라운드 6).

라운드 6 사전 검증 결과: 신호 1(min_height)은 answer-key-free 자동화가
구조적으로 불가능하다(도면1 height 갭 구조가 정답과 정반대). 따라서
min_height 는 yaml(text_height_filter)에 수동으로 유지하고, 이 모듈은
결정론적으로 풀리는 신호 2·3 만 자동 판단한다.

  신호 2 — 일람표 영역 존재 → exclude_table_regions
  신호 3 — 부호+규격 패턴 빈도(+ 규격형 전용 부호 보호) → exclude_with_spec

LLM 호출 없음, 외부 라이브러리 없음(ezdxf 만). 같은 입력 → 같은 출력.
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict
from functools import lru_cache

import ezdxf

# poc_v2(=counter.py 위치)와 tests/ 를 import 경로에 추가
_HERE = os.path.dirname(os.path.abspath(__file__))
_POC_DIR = os.path.dirname(_HERE)
for _path in (_POC_DIR, _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from counter import _clean_mtext, _height_ok, match_symbol  # noqa: E402
from detect_table_region import (  # noqa: E402
    detect_table_regions,
    load_text_layout,
)
from ground_truth import load_table_region_params  # noqa: E402


def auto_detect_policy(
    dxf_path: str,
    symbol_whitelist: list[str],
    min_text_height: float | None = None,
    spec_pattern_threshold: float = 0.3,
) -> dict:
    """도면을 분석해 신호 2·3 정책을 자동 결정한다.

    Parameters
    ----------
    dxf_path
        DXF 파일 경로.
    symbol_whitelist
        도면에서 카운트할 부호 리스트(정답지 부호).
    min_text_height
        yaml text_height_filter 에서 받은 height 필터. 신호 2·3 모두 이
        필터를 적용한 뒤 측정한다(작은 글자 오탐을 미리 거른 상태로 판단).
    spec_pattern_threshold
        신호 3 임계값. 규격형 텍스트 수 ≥ 화이트리스트 부호 수 × 이 비율
        이면 exclude_with_spec=True.

    Returns
    -------
    dict
        exclude_table_regions : bool
        exclude_with_spec     : bool
        diagnostics           : 판단 근거
    """
    return _auto_detect_policy_cached(
        dxf_path,
        tuple(sorted(symbol_whitelist)),
        min_text_height,
        spec_pattern_threshold,
    )


@lru_cache(maxsize=None)
def _auto_detect_policy_cached(
    dxf_path: str,
    whitelist: tuple[str, ...],
    min_text_height: float | None,
    spec_pattern_threshold: float,
) -> dict:
    """auto_detect_policy 의 캐시 본체 — 인자가 모두 해시 가능하도록 분리."""
    symbols = list(whitelist)

    # 신호 2 — 일람표 영역 존재
    table_regions = _detect_table_regions(dxf_path, symbols, min_text_height)
    exclude_table = len(table_regions) >= 1

    # 신호 3 — 부호+규격 패턴 빈도 + 규격형 전용 부호 보호
    spec_count, protection, protected_symbols, standalone, withspec = (
        _detect_spec_pattern(dxf_path, symbols, min_text_height)
    )
    threshold = len(symbols) * spec_pattern_threshold
    exclude_with_spec = spec_count >= threshold
    if protection:
        # 규격형으로만 등장하는 부호가 있으면 그 부호가 카운트 0 이 되므로 강제 비활성
        exclude_with_spec = False

    return {
        "exclude_table_regions": exclude_table,
        "exclude_with_spec": exclude_with_spec,
        "diagnostics": {
            "table_regions_count": len(table_regions),
            "table_regions": table_regions,
            "spec_pattern_count": spec_count,
            "spec_pattern_threshold_count": threshold,
            "protection_triggered": protection,
            "protected_symbols": protected_symbols,
            "standalone_counts": dict(standalone),
            "withspec_counts": dict(withspec),
        },
    }


def _detect_table_regions(
    dxf_path: str,
    whitelist: list[str],
    min_height: float | None,
) -> list[dict]:
    """신호 2 — 일람표 영역 검출. detect_table_region 모듈 재사용.

    min_height 를 적용한 자유 텍스트로 검출한다. 도면2 처럼 일람표가 작은
    글자로 그려진 경우, height 필터로 일람표 텍스트가 사라져 0곳이 된다.
    """
    coords, extent = load_text_layout(
        dxf_path, whitelist, min_text_height=min_height, exclude_with_spec=True
    )
    return detect_table_regions(coords, extent, **load_table_region_params())


def _detect_spec_pattern(
    dxf_path: str,
    whitelist: list[str],
    min_height: float | None,
) -> tuple[int, bool, list[str], dict[str, int], dict[str, int]]:
    """신호 3 — 부호+규격 패턴 빈도 + 규격형 전용 부호 보호.

    modelspace 의 TEXT/MTEXT/ATTRIB 텍스트를 훑어 각 텍스트를 분류한다:
      - 단독형  : "SC1" 처럼 부호 그 자체            → standalone
      - 규격형  : "SC1 350x175x7/11" 처럼 부호+규격  → withspec

    분류는 counter.match_symbol 을 그대로 재사용한다. exclude_with_spec
    플래그를 끄면 규격형도 매칭되고, 켜면 규격형은 None 이 되는 성질을 써서
    두 호출 결과 차이로 규격형을 식별한다 — 카운팅 본선과 정확히 일치.

    보호 로직: 화이트리스트 부호 W 가 'W 단독 텍스트 0개' 이고 'W 규격형
    텍스트 1개 이상' 이면, exclude_with_spec=True 일 때 그 부호가 카운트
    0 이 된다 → 보호 발동(False 강제). 라운드 6 검증: 도면1 BR2 가 이 경우.

    Returns
    -------
    (spec_count, protection, protected_symbols, standalone, withspec)
    """
    wl = set(whitelist)
    standalone: dict[str, int] = defaultdict(int)
    withspec: dict[str, int] = defaultdict(int)

    doc = ezdxf.readfile(dxf_path)
    for entity in doc.modelspace():
        dtype = entity.dxftype()
        if dtype in ("TEXT", "MTEXT"):
            _classify_text(entity, dtype, wl, min_height, standalone, withspec)
        elif dtype == "INSERT":
            for attrib in getattr(entity, "attribs", []):
                _classify_text(attrib, "ATTRIB", wl, min_height, standalone, withspec)

    spec_count = sum(withspec.values())
    protected_symbols = sorted(
        w for w in wl if withspec.get(w, 0) > 0 and standalone.get(w, 0) == 0
    )
    protection = bool(protected_symbols)
    return spec_count, protection, protected_symbols, dict(standalone), dict(withspec)


def _classify_text(
    entity,
    dtype: str,
    wl: set[str],
    min_height: float | None,
    standalone: dict[str, int],
    withspec: dict[str, int],
) -> None:
    """한 텍스트 엔티티를 단독형/규격형으로 분류해 카운터에 누적한다."""
    # MTEXT 는 dxf.hasattr("text") 가 False 라 hasattr 가드를 쓰면 안 된다.
    # counter.count_members 와 동일하게 dxf.text 를 직접 읽는다.
    try:
        raw = entity.dxf.text
    except Exception:
        return
    if not raw:
        return
    text = _clean_mtext(raw) if dtype == "MTEXT" else raw.strip()
    plain = match_symbol(text, wl, exclude_with_spec=False)
    if plain is None:
        return
    if not _height_ok(entity, dtype, min_height):
        return
    strict = match_symbol(text, wl, exclude_with_spec=True)
    if strict is not None:
        standalone[plain] += 1   # 단독형(정확 일치)
    else:
        withspec[plain] += 1     # 규격형(부호 + 규격)
