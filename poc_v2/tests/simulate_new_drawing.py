"""새 도면 추가 시뮬레이션 — "height 한 줄만 추가하면 동작하는가" 직접 검증.

라운드 6 작업 7. 사용자 의문("새 도면 들어오면 yaml 항목 없어서 동작 안 됨")을
실측으로 확인한다.

절차:
  1. 도면1.dxf 를 도면1_clone.dxf 로 복사 (정답지·policy_override 미등록).
  2. min_height 한 줄(177)만 시뮬레이션으로 공급.
  3. policy_override 없음 → auto_detect_policy 가 신호 2·3 자동 결정.
  4. 자동 정책으로 카운트 → 도면1 정답(22/22)과 일치하는지 확인.

통과하면: 새 도면은 height 한 줄만 추가하면 일람표·규격 정책은 자동 적용된다.

사용법:  poc_v2 디렉토리에서  `python tests/simulate_new_drawing.py`
"""
from __future__ import annotations

import os
import shutil
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_POC_DIR = os.path.dirname(_HERE)
for _path in (_POC_DIR, _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from auto_policy import auto_detect_policy  # noqa: E402
from counter import count_members  # noqa: E402
from detect_table_region import detect_table_regions, load_text_layout  # noqa: E402
from ground_truth import (  # noqa: E402
    PROJECT_ROOT,
    drawing_symbol_totals,
    load_auto_policy_params,
    load_policy_override,
    load_table_region_params,
    within_tolerance,
)

_FULL_EXTENT = (-1e18, -1e18, 1e18, 1e18)
# 시뮬레이션: 새 도면에 사용자가 yaml 에 추가하는 단 한 줄.
_SIMULATED_MIN_HEIGHT = 177


def _predict_with_auto_policy(
    dxf_path: str, symbols: list[str], min_h: float | None
) -> tuple[dict[str, int], dict]:
    """baseline.compute_drawing 의 무(無)오버라이드 경로를 그대로 재현한다."""
    auto = auto_detect_policy(
        dxf_path, symbols, min_text_height=min_h, **load_auto_policy_params()
    )
    counts, _hits, _coords = count_members(
        dxf_path, *_FULL_EXTENT, custom_whitelist=symbols,
        min_text_height=min_h, exclude_with_spec=auto["exclude_with_spec"],
    )
    final = dict(counts)
    if auto["exclude_table_regions"]:
        text_coords, extent = load_text_layout(
            dxf_path, symbols, min_text_height=min_h, exclude_with_spec=True
        )
        for region in detect_table_regions(
            text_coords, extent, **load_table_region_params()
        ):
            for sym, n in region["symbols"].items():
                final[sym] = max(0, final.get(sym, 0) - n)
    return final, auto


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 64)
    print(" 새 도면 추가 시뮬레이션 — 도면1_clone (미등록 신규 도면)")
    print("=" * 64)

    src = os.path.join(PROJECT_ROOT, "sample_data", "도면1.dxf")
    clone = os.path.join(PROJECT_ROOT, "sample_data", "도면1_clone.dxf")
    if not os.path.exists(src):
        print(f"[오류] 원본 DXF 없음: {src}")
        return 1
    shutil.copyfile(src, clone)
    print("\n1) DXF 복사: 도면1.dxf → 도면1_clone.dxf")

    # policy_override 미등록 확인
    override = load_policy_override("도면1_clone")
    print(f"2) policy_override['도면1_clone'] = {override}  (None=자동 판단)")
    print(f"3) 시뮬레이션 공급값: min_height = {_SIMULATED_MIN_HEIGHT}  (yaml 한 줄)")

    # 클론은 도면1 과 동일 → 도면1 정답지로 검증
    expected = drawing_symbol_totals()["도면1"]
    symbols = sorted(expected.keys())

    final, auto = _predict_with_auto_policy(clone, symbols, _SIMULATED_MIN_HEIGHT)
    print(
        f"4) 자동 판단: 일람표제외={auto['exclude_table_regions']}, "
        f"규격제외={auto['exclude_with_spec']}"
    )

    passed = sum(1 for s, e in expected.items() if within_tolerance(final.get(s, 0), e))
    total = len(expected)
    pred_sum, exp_sum = sum(final.values()), sum(expected.values())
    print(
        f"5) 카운트 결과: {passed}/{total} 통과, "
        f"총합 {pred_sum} vs {exp_sum} (차이 {pred_sum - exp_sum:+d})"
    )

    ok = passed == total
    print("\n" + "=" * 64)
    if ok:
        print(" 결과: 새 도면 무손 적용 통과 ✅")
        print(" → 신규 도면은 min_height 한 줄만 추가하면 일람표·규격 정책 자동 적용.")
    else:
        print(" 결과: 실패 ⚠ — 자동 판단만으로는 신규 도면이 정답에 못 미침")
    print("=" * 64)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
