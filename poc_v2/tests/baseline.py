"""베이스라인 측정 — 현재 counter.py 가 정답지 합계를 얼마나 맞히는지 측정.

라운드 2 방침: 페이지 분할 폐기. 도면 전체를 한 번 카운트해 정답지의
부호별 합계와 비교한다. 코드는 전혀 수정하지 않는다.

사용법:
    poc_v2 디렉토리에서  `python tests/baseline.py 도면1`
    (인자 생략 시 도면1)
"""
from __future__ import annotations

import os
import sys

# poc_v2(=counter.py 위치)와 tests/ 를 import 경로에 추가
_HERE = os.path.dirname(os.path.abspath(__file__))
_POC_DIR = os.path.dirname(_HERE)
for _path in (_POC_DIR, _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from counter import count_members  # noqa: E402
from ground_truth import (  # noqa: E402
    PROJECT_ROOT,
    drawing_symbol_totals,
    load_text_height_filter,
    within_tolerance,
)

# 도면 전체를 포함하도록 충분히 큰 bbox
_FULL_EXTENT = (-1e18, -1e18, 1e18, 1e18)
_DEFAULT_DXF_FILES = {
    "도면1": "도면1.dxf",
    "도면2": "도면2.dxf",
    "도면4": "도면4.dxf",
}


def _dxf_path(drawing: str) -> str:
    return os.path.join(
        PROJECT_ROOT, "sample_data", _DEFAULT_DXF_FILES.get(drawing, f"{drawing}.dxf")
    )


def _print_symbol_table(predicted: dict[str, int], expected: dict[str, int]) -> None:
    """부호별 [예측] [정답] [차이] [오차%] [상태] 표 출력."""
    print(f"{'부호':<8}{'예측':>7}{'정답':>7}{'차이':>7}{'오차%':>8}   상태")
    print("-" * 48)
    for symbol in sorted(expected):
        pred = predicted.get(symbol, 0)
        exp = expected[symbol]
        diff = pred - exp
        err_pct = abs(diff) / exp * 100 if exp > 0 else 0.0
        ok = within_tolerance(pred, exp)
        print(
            f"{symbol:<8}{pred:>7}{exp:>7}{diff:>+7}{err_pct:>7.0f}%   "
            f"{'PASS' if ok else 'FAIL'}"
        )


def _measure(drawing: str) -> None:
    expected = drawing_symbol_totals()[drawing]
    symbols = sorted(expected.keys())
    dxf = _dxf_path(drawing)

    print("=" * 48)
    print(f" 합계 베이스라인 측정 — {drawing}  ({os.path.basename(dxf)})")
    print("=" * 48)

    if not os.path.exists(dxf):
        print(f"[오류] DXF 파일을 찾을 수 없습니다: {dxf}")
        return

    # 1) 정답지 부호 화이트리스트로 도면 전체 카운트 (도면별 height 필터 적용)
    min_h = load_text_height_filter().get(drawing)
    counts, _hits, _coords = count_members(
        dxf, *_FULL_EXTENT, custom_whitelist=symbols, min_text_height=min_h
    )
    predicted = dict(counts)

    filter_note = (
        f"height >= {min_h} 필터 적용" if min_h is not None
        else "height 필터 미적용"
    )
    print(f"\n[1] 도면 전체 카운트 vs 정답지 합계  ({filter_note})\n")
    _print_symbol_table(predicted, expected)

    # 2) 정확도 / 평균 오차 요약
    total_symbols = len(expected)
    matched = sum(
        1 for s, e in expected.items() if within_tolerance(predicted.get(s, 0), e)
    )
    rel_errors = [
        abs(predicted.get(s, 0) - e) / e for s, e in expected.items() if e > 0
    ]
    avg_rel_error = sum(rel_errors) / len(rel_errors) if rel_errors else 0.0
    pred_sum = sum(predicted.values())
    exp_sum = sum(expected.values())

    print(
        f"\n요약: {total_symbols}개 부호 중 {matched}개 통과, "
        f"평균오차 {avg_rel_error * 100:.0f}%, "
        f"총합 {pred_sum} vs {exp_sum} (차이 {pred_sum - exp_sum:+d})"
    )

    # 3) 정답지에 없는데 자동 감지로 잡히는 부호 (일람표/규격 오탐 진단용)
    auto_counts, _auto_hits, _auto_coords = count_members(
        dxf, *_FULL_EXTENT, custom_whitelist=None
    )
    extra = {sym: n for sym, n in auto_counts.items() if sym not in expected}
    print("\n[3] 자동 감지로 추가 발견된 부호 (정답지 미등록 — 오탐 후보)")
    if extra:
        for sym, n in sorted(extra.items(), key=lambda kv: -kv[1])[:25]:
            print(f"    {sym:<10}{n:>6}")
        if len(extra) > 25:
            print(f"    … 외 {len(extra) - 25}종")
    else:
        print("    (없음)")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    drawing = sys.argv[1] if len(sys.argv) > 1 else "도면1"
    available = set(drawing_symbol_totals().keys())
    if drawing not in available:
        print(f"[오류] 알 수 없는 도면: {drawing}  (사용 가능: {sorted(available)})")
        sys.exit(1)
    _measure(drawing)


if __name__ == "__main__":
    main()
