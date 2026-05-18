"""텍스트 높이 분포 진단 (도면 인자 지정 가능, 진단만).

각 부호에 대해 도면 전체의 출현 위치별 텍스트 height 를 모아 히스토그램을
그리고, "큰 글자부터 누적해 어느 height 까지 세면 정답 개수에 맞는지"의
추천 임계값을 계산한다. **임계값을 실제로 적용하지는 않는다 — 진단 출력만.**

도면 전체 차원에서 height 가 "큰 글자 / 작은 글자" 두 무리로 갈리는지도
판정한다 (전역 임계값 후보 탐색).

사용법:
    poc_v2 디렉토리에서  `python tests/analyze_heights.py [도면1|도면2|도면4]`
    (인자 생략 시 도면1)
"""
from __future__ import annotations

import os
import sys
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
_POC_DIR = os.path.dirname(_HERE)
for _path in (_POC_DIR, _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from ground_truth import PROJECT_ROOT, drawing_symbol_totals  # noqa: E402
from symbol_extract import extract_occurrences  # noqa: E402

_DXF_FILES = {
    "도면1": "도면1.dxf",
    "도면2": "도면2.dxf",
    "도면4": "도면4.dxf",
}
# 참고용 — 도면1 진단에서 확인된 "작은 글자(오탐)" height 값
_REFERENCE_SMALL_HEIGHTS = (159, 176)


def _dxf_path(drawing: str) -> str:
    return os.path.join(
        PROJECT_ROOT, "sample_data", _DXF_FILES.get(drawing, f"{drawing}.dxf")
    )


def _recommend_threshold(
    height_counts: list[tuple[int, int]],
    expected: int,
) -> tuple[int | None, str]:
    """큰 height 부터 누적하며 정답에 가장 근접하는 임계값을 찾는다.

    Parameters
    ----------
    height_counts : (height, count) 리스트 — height 내림차순 정렬되어 있어야 함
    expected      : 정답 개수

    Returns (추천 height 임계값, 설명문). 정확히 일치하는 누적이 있으면 그 height,
    없으면 정답에 가장 가까운 누적의 height.
    """
    if not height_counts or expected <= 0:
        return None, "정답 0 또는 출현 없음 — 추천 불가"

    cumulative = 0
    best_height: int | None = None
    best_gap: int | None = None
    for height, count in height_counts:
        cumulative += count
        gap = abs(cumulative - expected)
        if best_gap is None or gap < best_gap:
            best_gap = gap
            best_height = height

    if best_gap == 0:
        return best_height, f"height >= {best_height} 누적이 정답({expected})과 정확히 일치"
    return best_height, (
        f"height >= {best_height} 누적이 정답({expected})에 가장 근접 "
        f"(오차 {best_gap}개)"
    )


def _analyze_symbol(symbol: str, heights: list[float], expected: int) -> None:
    # height 를 정수로 버킷팅 (도면 height 는 사실상 이산값)
    bucket = Counter(round(h) for h in heights)
    ordered = sorted(bucket.items(), key=lambda kv: -kv[0])  # height 내림차순

    print(f"\n{symbol} (정답 {expected}, 출현 {len(heights)}회)")
    cumulative = 0
    for height, count in ordered:
        cumulative += count
        marker = ""
        if cumulative == expected:
            marker = "  ← 누적 일치"
        elif cumulative - count < expected <= cumulative:
            marker = f"  ← 누적 {cumulative}, 정답 통과"
        print(f"  height {height:>5}: {count:>3}회   누적 {cumulative:>3}{marker}")
    _, reason = _recommend_threshold(ordered, expected)
    print(f"  추천 임계값: {reason}")


def _global_verdict(
    all_heights: list[float],
    total_expected: int,
) -> None:
    """도면 전체 height 히스토그램 + 두 무리 갈림 판정 + 전역 임계값 후보."""
    hist = Counter(round(h) for h in all_heights)
    distinct = sorted(hist)
    total_occ = len(all_heights)

    print("\n" + "-" * 60)
    print(" [전역] 도면 전체 텍스트 height 분포")
    print("-" * 60)
    print(f" 정답 총합 {total_expected} / 출현 총합 {total_occ} "
          f"(과다 {total_occ - total_expected:+d})")
    print(f" 등장 height 값 {len(distinct)}종:")
    for h in distinct:
        bar = "#" * min(50, hist[h])
        print(f"   height {h:>5}: {hist[h]:>4}회  {bar}")

    # 전역 임계값 스캔 — height >= h 누적이 정답 총합과 맞는 h 탐색
    print("\n [전역] 임계값 후보 스캔 (height >= h 누적 vs 정답 총합)")
    best_h: int | None = None
    best_gap: int | None = None
    for h in distinct:
        cum_ge = sum(c for hh, c in hist.items() if hh >= h)
        gap = abs(cum_ge - total_expected)
        mark = "  ← 정답 총합과 일치" if gap == 0 else ""
        if best_gap is None or gap < best_gap:
            best_gap, best_h = gap, h
        if gap == 0 or gap <= max(2, total_expected * 0.02):
            print(f"   height >= {h:>5}: 누적 {cum_ge:>4}{mark}")

    # 두 무리 갈림 판정 — 인접 distinct height 사이 최대 간격
    print("\n [전역] 두 무리 갈림 판정")
    if len(distinct) < 2:
        print("   height 값이 1종뿐 — 두 무리로 갈리지 않음 (단일 봉우리)")
    else:
        gaps = [
            (distinct[i + 1] - distinct[i], distinct[i], distinct[i + 1])
            for i in range(len(distinct) - 1)
        ]
        max_gap, lo, hi = max(gaps, key=lambda g: g[0])
        span = distinct[-1] - distinct[0]
        ratio = max_gap / span if span else 0.0
        print(f"   최대 간격: height {lo} ~ {hi} 사이 {max_gap} "
              f"(전체 범위 {span}의 {ratio * 100:.0f}%)")
        if ratio >= 0.25:
            print(f"   → 두 무리로 갈림. 작은무리 <= {lo}, 큰무리 >= {hi}")
        else:
            print("   → 뚜렷한 갈림 없음 (연속 분포 또는 다봉 분포 의심)")

    if best_h is not None:
        verdict = (
            f"height >= {best_h} 가 정답 총합과 정확히 일치"
            if best_gap == 0
            else f"height >= {best_h} 가 정답 총합에 가장 근접 (오차 {best_gap})"
        )
        print(f"\n [전역] 추천 전역 임계값: {verdict}")
    print(f" 참고 — 도면1의 작은 글자 height: {_REFERENCE_SMALL_HEIGHTS}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    drawing = sys.argv[1] if len(sys.argv) > 1 else "도면1"

    totals = drawing_symbol_totals()
    if drawing not in totals:
        print(f"[오류] 알 수 없는 도면: {drawing}  (사용 가능: {sorted(totals)})")
        sys.exit(1)

    expected = totals[drawing]
    symbols = sorted(expected.keys())
    occurrences = extract_occurrences(_dxf_path(drawing), symbols)

    by_symbol: dict[str, list[float]] = {}
    for occ in occurrences:
        by_symbol.setdefault(occ.symbol, []).append(occ.height)

    print("=" * 60)
    print(f" 텍스트 높이 분포 진단  ({drawing})")
    print(" (임계값 적용 안 함 — 진단 출력만)")
    print("=" * 60)

    for symbol in symbols:
        heights = by_symbol.get(symbol, [])
        _analyze_symbol(symbol, heights, expected[symbol])

    _global_verdict(
        [occ.height for occ in occurrences],
        sum(expected.values()),
    )

    print("\n" + "=" * 60)
    print(" 진단 종료 — 추천 임계값은 다음 라운드 정책 결정 입력용")
    print("=" * 60)


if __name__ == "__main__":
    main()
