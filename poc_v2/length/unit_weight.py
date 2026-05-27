"""H형강 단위중량 룩업 — 라운드 길이-4.

`config/unit_weight_table.yaml` 의 `H형강` 매핑을 로드해 `spec_normalized`
키로 단위중량(kg/m)을 돌려준다. 결정론적 dict 룩업 — LLM·외부 호출 없음.

⚠ yaml 의 값은 라운드 길이-4 명세서의 임시값이다. 멘토 확인 후 KS D 3502
정확값으로 교체 예정. 코드 변경 없이 yaml 만 갈아끼우면 됨.
"""
from __future__ import annotations

import os
import sys
from typing import Optional

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from poc_v2.length.ground_truth_spec import normalize_spec  # noqa: E402

DEFAULT_TABLE_PATH = os.path.join(
    PROJECT_ROOT, "config", "unit_weight_table.yaml"
)

_TOP_KEY = "H형강"


def load_unit_weight_table(path: str | None = None) -> dict[str, float]:
    """yaml 의 `H형강` 매핑을 dict 로 로드.

    Returns
    -------
    dict[str, float]
        {spec_normalized: unit_weight_kg_per_m}.  yaml 부재시 빈 dict.
    """
    table_path = path or DEFAULT_TABLE_PATH
    if not os.path.exists(table_path):
        return {}

    with open(table_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    raw = data.get(_TOP_KEY) or {}
    # yaml 키는 가독성을 위해 슬래시 표기를 허용 (예: "H-588x300x12/20").
    # `normalize_spec` 으로 canonical 폼(슬래시 → x) 으로 변환해 저장.
    table: dict[str, float] = {}
    for key, value in raw.items():
        if value is None:
            continue
        canonical = normalize_spec(str(key).strip())
        table[canonical] = float(value)
    return table


def lookup_unit_weight(
    spec_normalized: str,
    table: dict[str, float] | None = None,
) -> Optional[float]:
    """정규화된 규격을 키로 단위중량(kg/m) 조회. 누락 키는 None.

    호출자가 이미 `normalize_spec` 으로 정규화한 값을 넘기는 것이 원칙이지만,
    안전망으로 한 번 더 정규화한다 (이중 정규화는 idempotent).
    """
    if not spec_normalized:
        return None
    lookup = table if table is not None else load_unit_weight_table()
    return lookup.get(normalize_spec(spec_normalized))
