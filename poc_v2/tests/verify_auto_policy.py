"""자동 판단(신호 2·3)이 라운드 5 수동 yaml 설정과 동일한지 검증.

라운드 6 종료 조건 1순위: 도면1·2·4 자동 = 수동 완전 일치.
불일치 시 진단 출력으로 어떤 신호에서 어긋났는지 보여준다.

사용법:  poc_v2 디렉토리에서  `python tests/verify_auto_policy.py`
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_POC_DIR = os.path.dirname(_HERE)
for _path in (_POC_DIR, _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from auto_policy import auto_detect_policy  # noqa: E402
from ground_truth import (  # noqa: E402
    PROJECT_ROOT,
    drawing_symbol_totals,
    load_auto_policy_params,
    load_text_height_filter,
)

# 라운드 5 수동 yaml(policy_p) 설정 — 자동 판단이 이것과 일치해야 한다.
EXPECTED = {
    "도면1": {"exclude_table_regions": False, "exclude_with_spec": False},
    "도면2": {"exclude_table_regions": False, "exclude_with_spec": False},
    "도면4": {"exclude_table_regions": True, "exclude_with_spec": True},
}

_DXF_FILES = {"도면1": "도면1.dxf", "도면2": "도면2.dxf", "도면4": "도면4.dxf"}


def _dxf_path(drawing: str) -> str:
    return os.path.join(
        PROJECT_ROOT, "sample_data", _DXF_FILES.get(drawing, f"{drawing}.dxf")
    )


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 64)
    print(" 자동 정책 판단 검증 — 신호 2·3 자동 vs 라운드 5 수동 yaml")
    print("=" * 64)

    height_filter = load_text_height_filter()
    params = load_auto_policy_params()
    all_match = True

    for drawing, expected in EXPECTED.items():
        min_h = height_filter.get(drawing)
        symbols = sorted(drawing_symbol_totals()[drawing].keys())
        auto = auto_detect_policy(
            _dxf_path(drawing), symbols, min_text_height=min_h, **params
        )
        actual = {k: auto[k] for k in expected}
        diag = auto["diagnostics"]

        if actual == expected:
            print(f"\n✅ {drawing}: 자동 = 수동 일치  {actual}")
        else:
            all_match = False
            print(f"\n⚠ {drawing}: 불일치")
            print(f"    자동: {actual}")
            print(f"    수동: {expected}")
        print(
            f"    근거 — 일람표 {diag['table_regions_count']}곳 / "
            f"규격형 텍스트 {diag['spec_pattern_count']}개 "
            f"(임계 {diag['spec_pattern_threshold_count']:.1f}) / "
            f"보호 {diag['protection_triggered']} {diag['protected_symbols']}"
        )

    print("\n" + "=" * 64)
    if all_match:
        print(" 결과: 도면1·2·4 자동 = 수동 완전 일치 ✅")
    else:
        print(" 결과: 불일치 발견 ⚠ — 임계값/보호 로직 점검 필요")
    print("=" * 64)
    return 0 if all_match else 1


if __name__ == "__main__":
    sys.exit(main())
