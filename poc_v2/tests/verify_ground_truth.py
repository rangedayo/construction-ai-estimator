"""정답지 로더 출력 1차 확인 — 사람이 눈으로 보고 검증한다.

라운드 7: 새 정답지 포맷(`도면N-기둥`/`도면N-보` 분리) 로딩 결과 확인.
회귀 테스트 범위(기둥, 도면1·2·4)와 전체(category=None) 두 케이스를 찍는다.
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from ground_truth import drawing_symbol_totals  # noqa: E402


def _format_dict(d: dict[str, int]) -> str:
    return "{" + ", ".join(f"{k}: {v}" for k, v in sorted(d.items())) + "}"


def main() -> None:
    print('[category="기둥", drawings=["도면1", "도면2", "도면4"]]')
    columns = drawing_symbol_totals(
        category="기둥",
        drawings=["도면1", "도면2", "도면4"],
    )
    for drawing in sorted(columns):
        print(f"  {drawing}: {_format_dict(columns[drawing])}")

    print()
    print("[category=None, drawings=None] (전체)")
    everything = drawing_symbol_totals()
    for drawing in sorted(everything):
        print(f"  {drawing}: {_format_dict(everything[drawing])}")


if __name__ == "__main__":
    main()
