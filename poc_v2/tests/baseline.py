"""베이스라인 측정 + 라운드 5 정책 P 진단.

라운드 2 방침: 페이지 분할 폐기. 도면 전체를 한 번 카운트해 정답지의 부호별
합계와 비교한다.

라운드 5 정책 P (회사 무관 보편 룰):
  - 신호 1: 일람표 영역 자동 검출 → 카운트 제외 (exclude_table_regions)
  - 신호 2: 규격 안내 텍스트("부호 + 규격") 제외 (exclude_with_spec)
  - 신호 3: 동일 좌표 부호 중복 진단 (제거 X, 경고 메모만)

도면별 정책 P 활성 여부는 config/symbol_rules.yaml 의 policy_p 로 결정한다.
counter.py 의 핵심 매칭 룰(BR2·블록·height)은 건드리지 않는다.

사용법:
    poc_v2 디렉토리에서  `python tests/baseline.py 도면4`
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

from auto_policy import auto_detect_policy  # noqa: E402
from counter import count_members, diagnose_duplicate_coords  # noqa: E402
from detect_table_region import detect_table_regions, load_text_layout  # noqa: E402
from ground_truth import (  # noqa: E402
    PROJECT_ROOT,
    drawing_symbol_totals,
    load_auto_policy_params,
    load_policy_override,
    load_table_region_params,
    load_text_height_filter,
    within_tolerance,
)

# 도면 전체를 포함하도록 충분히 큰 bbox
_FULL_EXTENT = (-1e18, -1e18, 1e18, 1e18)
_DEFAULT_DXF_FILES = {
    "도면1": "도면1.dxf",
    "도면2": "도면2.dxf",
    "도면3": "도면3.dxf",
    "도면4": "도면4.dxf",
    "도면5": "도면5.dxf",
}
_DUP_TOLERANCE_MM = 1.0
# 라운드 8: 일람표 검출 입력 정리용 좌표 수 임계값. 부호당 자유 텍스트가
# 이 값을 초과하면 본체 부재(modelspace TEXT/MTEXT) 로 간주해 검출 입력에서
# 제외한다. 일람표는 부호당 1~2개씩만 등장하는 패턴이라는 정의에 부합.
_TABLE_SPARSE_MAX = 5


def _dxf_path(drawing: str) -> str:
    return os.path.join(
        PROJECT_ROOT, "sample_data", _DEFAULT_DXF_FILES.get(drawing, f"{drawing}.dxf")
    )


def compute_drawing(drawing: str) -> dict:
    """한 도면을 정책 P 까지 적용해 카운트·진단 결과를 모두 계산한다.

    baseline.py(출력)와 test_regression.py(검증)가 공유하는 단일 계산 경로.

    Returns
    -------
    dict
        expected      : 정답지 합계 {부호: int}
        raw           : exclude_with_spec 미적용 카운트 {부호: int}
        after_spec    : exclude_with_spec 적용 카운트 {부호: int}
        final         : 일람표 영역까지 제외한 최종 카운트 {부호: int}
        regions       : 검출된 일람표 후보 [{bbox, symbols}]
        dup           : 좌표 중복 진단 {부호: [{coord, count}]}
        policy        : {exclude_table_regions, exclude_with_spec}
        min_h         : 적용된 텍스트 height 필터
    """
    expected = drawing_symbol_totals()[drawing]
    symbols = sorted(expected.keys())
    dxf = _dxf_path(drawing)
    min_h = load_text_height_filter().get(drawing)

    # 정책 결정 — 신호 1(min_h)은 위 yaml 수동, 신호 2·3 은 자동 판단.
    # policy_override 가 있으면 자동 판단을 무시하고 강제한다.
    override = load_policy_override(drawing)
    if override is not None:
        policy = override
        policy_source = "override"
    else:
        auto = auto_detect_policy(
            dxf, symbols, min_text_height=min_h, **load_auto_policy_params()
        )
        policy = {
            "exclude_table_regions": auto["exclude_table_regions"],
            "exclude_with_spec": auto["exclude_with_spec"],
        }
        policy_source = "auto"

    # 1) 규격 안내 미적용 카운트 (라운드 4 베이스라인)
    raw_counts, _h, coords = count_members(
        dxf, *_FULL_EXTENT, custom_whitelist=symbols, min_text_height=min_h
    )
    raw = dict(raw_counts)

    # 2) 규격 안내 적용 카운트 (정책 P 신호 2)
    # treat_slash_as_combo=True: 슬래시 결합(예: "C1/P1")은 본체 텍스트이므로
    # 규격 제외 모드에서도 본체로 인정한다. 라운드 8 도면3 케이스 보정.
    if policy["exclude_with_spec"]:
        spec_counts, _h2, _c2 = count_members(
            dxf, *_FULL_EXTENT, custom_whitelist=symbols,
            min_text_height=min_h, exclude_with_spec=True,
            treat_slash_as_combo=True,
        )
        after_spec = dict(spec_counts)
    else:
        after_spec = dict(raw)

    # 3) 일람표 영역 검출 (정책 P 신호 1) — 자유 텍스트 좌표만 입력
    # 라운드 8: 부호당 좌표가 많은(_TABLE_SPARSE_MAX 초과) 부호는 본체가 자유
    # 텍스트로 그려진 경우(도면3 처럼)라 일람표 검출 입력을 오염시킨다.
    # 보편 휴리스틱으로 좌표 수 컷을 적용해 본체 부호를 자동 거른다. 도면1·2 는
    # 신호 1 자동 OFF, 도면4 는 자유 텍스트 좌표가 모두 임계값 이하라 영향 없음.
    text_coords, extent = load_text_layout(
        dxf, symbols, min_text_height=min_h, exclude_with_spec=True
    )
    sparse_coords = {
        s: pts for s, pts in text_coords.items() if len(pts) <= _TABLE_SPARSE_MAX
    }
    regions = detect_table_regions(sparse_coords, extent, **load_table_region_params())

    # 4) 일람표 영역 카운트 제외
    final = dict(after_spec)
    if policy["exclude_table_regions"]:
        for region in regions:
            for sym, n in region["symbols"].items():
                final[sym] = max(0, final.get(sym, 0) - n)

    # 5) 좌표 중복 진단 (정책 P 신호 3) — 카운트는 건드리지 않는다
    dup = diagnose_duplicate_coords(coords, tolerance_mm=_DUP_TOLERANCE_MM)

    return {
        "drawing": drawing,
        "expected": expected,
        "raw": raw,
        "after_spec": after_spec,
        "final": final,
        "regions": regions,
        "dup": dup,
        "policy": policy,
        "policy_source": policy_source,
        "min_h": min_h,
    }


def predict(drawing: str) -> dict[str, int]:
    """정책 P 까지 적용한 도면별 최종 카운트 — 회귀 테스트가 호출."""
    return compute_drawing(drawing)["final"]


def _dup_note(dup_entries: list[dict]) -> str:
    """좌표 중복 진단 → 한 줄 경고 메모."""
    if not dup_entries:
        return ""
    locations = len(dup_entries)
    extra = sum(d["count"] - 1 for d in dup_entries)
    return f"⚠ 동일 좌표 {locations}곳 (중복 {extra}개)"


def _print_symbol_table(result: dict) -> None:
    """부호별 [예측] [정답] [차이] [오차%] [상태] [메모] 표 출력."""
    expected = result["expected"]
    final = result["final"]
    dup = result["dup"]
    print(f"{'부호':<8}{'예측':>7}{'정답':>7}{'차이':>7}{'오차%':>8}   상태   메모")
    print("-" * 64)
    for symbol in sorted(expected):
        pred = final.get(symbol, 0)
        exp = expected[symbol]
        diff = pred - exp
        err_pct = abs(diff) / exp * 100 if exp > 0 else 0.0
        ok = within_tolerance(pred, exp)
        note = _dup_note(dup.get(symbol, []))
        print(
            f"{symbol:<8}{pred:>7}{exp:>7}{diff:>+7}{err_pct:>7.0f}%   "
            f"{'PASS' if ok else 'FAIL':<6} {note}"
        )


def _print_policy_p_diagnosis(result: dict) -> None:
    """[정책 P 진단] 섹션 출력 — 일람표·규격 안내·좌표 중복."""
    print("\n[정책 P 진단]")

    regions = result["regions"]
    if regions:
        print(f"- 일람표 후보 영역: {len(regions)}곳")
        for region in regions:
            x0, y0, x1, y1 = region["bbox"]
            syms = ", ".join(
                f"{s}({n})" for s, n in sorted(region["symbols"].items())
            )
            print(f"    bbox: ({x0:.1f}, {y0:.1f}) ~ ({x1:.1f}, {y1:.1f})")
            print(f"    포함 부호: {syms}")
    else:
        print("- 일람표 후보 영역: 없음")

    # 규격 안내 텍스트 수 = (규격 미적용) - (규격 적용)
    spec_total = sum(result["raw"].values()) - sum(result["after_spec"].values())
    if result["policy"]["exclude_with_spec"]:
        spec_by_sym = ", ".join(
            f"{s}({result['raw'][s] - result['after_spec'].get(s, 0)})"
            for s in sorted(result["raw"])
            if result["raw"][s] - result["after_spec"].get(s, 0) > 0
        )
        print(f"- 규격 안내 텍스트: {spec_total}개  [{spec_by_sym}]")
    else:
        print("- 규격 안내 텍스트 제외: 비활성 (정책 P off)")

    dup = result["dup"]
    if dup:
        for sym in sorted(dup):
            entries = dup[sym]
            locations = len(entries)
            total = sum(d["count"] for d in entries)
            extra = sum(d["count"] - 1 for d in entries)
            print(
                f"- 좌표 중복: {sym} {locations}곳 {total}개 "
                f"(중복 {extra}개 — 경고만, 카운트 그대로)"
            )
    else:
        print(f"- 좌표 중복: 없음 (tolerance {_DUP_TOLERANCE_MM}mm)")


def _measure(drawing: str) -> None:
    dxf = _dxf_path(drawing)
    print("=" * 64)
    print(f" 합계 베이스라인 + 정책 P 진단 — {drawing}  ({os.path.basename(dxf)})")
    print("=" * 64)

    if not os.path.exists(dxf):
        print(f"[오류] DXF 파일을 찾을 수 없습니다: {dxf}")
        return

    result = compute_drawing(drawing)
    policy = result["policy"]
    min_h = result["min_h"]

    filter_note = (
        f"height >= {min_h} 필터" if min_h is not None else "height 필터 미적용"
    )
    policy_note = (
        f"[{result['policy_source']}] "
        f"일람표제외={policy['exclude_table_regions']}, "
        f"규격제외={policy['exclude_with_spec']}"
    )
    print(f"\n[1] 도면 전체 카운트 vs 정답지 합계  ({filter_note}; 정책P {policy_note})\n")
    _print_symbol_table(result)

    expected = result["expected"]
    final = result["final"]
    matched = sum(
        1 for s, e in expected.items() if within_tolerance(final.get(s, 0), e)
    )
    rel_errors = [
        abs(final.get(s, 0) - e) / e for s, e in expected.items() if e > 0
    ]
    avg_rel_error = sum(rel_errors) / len(rel_errors) if rel_errors else 0.0
    pred_sum = sum(final.values())
    exp_sum = sum(expected.values())
    print(
        f"\n요약: {len(expected)}개 부호 중 {matched}개 통과, "
        f"평균오차 {avg_rel_error * 100:.0f}%, "
        f"총합 {pred_sum} vs {exp_sum} (차이 {pred_sum - exp_sum:+d})"
    )

    _print_policy_p_diagnosis(result)

    # 정답지에 없는데 자동 감지로 잡히는 부호 (오탐 진단용)
    auto_counts, _ah, _ac = count_members(dxf, *_FULL_EXTENT, custom_whitelist=None)
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
