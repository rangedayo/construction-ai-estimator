"""라운드 8 사전 진단 — 도면3 기둥 추가 가능성 측정.

코드(counter.py / yaml / baseline.py / test_regression.py) 변경 전,
다음 네 가지를 측정해 작업 2 진행 가능 여부를 판단한다:

  1-A) 도면3 height 분포 — min_height 추천값 산출
  1-B) 슬래시 패턴 도면별 통계 — 룰 확장 부작용 위험 평가
  1-C) 도면3 신호 2·3 자동 판정 결과
  1-D) 슬래시 매칭 확장 시뮬레이션 — 진짜 코드 변경 없이 가상 매칭

LLM 호출 없음. ezdxf 만 사용. 같은 입력 → 같은 출력.
"""
from __future__ import annotations

import os
import re
import sys
from collections import Counter, defaultdict

import ezdxf

_HERE = os.path.dirname(os.path.abspath(__file__))
_POC_DIR = os.path.dirname(_HERE)
for _path in (_POC_DIR, _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from auto_policy import auto_detect_policy  # noqa: E402
from counter import _clean_mtext  # noqa: E402
from ground_truth import (  # noqa: E402
    PROJECT_ROOT,
    drawing_symbol_totals,
    load_auto_policy_params,
    load_text_height_filter,
)

_TARGET_DRAWING = "도면3"
_SLASH_PATTERN = re.compile(r"^([A-Z]+\d+)/[A-Z]+\d+$")
_SYMBOL_LIKE = re.compile(r"^[A-Z]+\d+")


def _dxf_path(drawing: str) -> str:
    return os.path.join(PROJECT_ROOT, "sample_data", f"{drawing}.dxf")


def _iter_text_entities(dxf_path: str):
    """modelspace 의 TEXT/MTEXT 만 순회. (entity, dtype, text, height) 반환."""
    doc = ezdxf.readfile(dxf_path)
    for entity in doc.modelspace():
        dtype = entity.dxftype()
        if dtype not in ("TEXT", "MTEXT"):
            continue
        try:
            raw = entity.dxf.text
        except Exception:
            continue
        if not raw:
            continue
        text = _clean_mtext(raw) if dtype == "MTEXT" else raw.strip()
        try:
            if dtype == "MTEXT":
                height = float(entity.dxf.char_height)
            else:
                height = float(entity.dxf.height)
        except Exception:
            height = None
        yield entity, dtype, text, height


def section_a_height_distribution() -> dict:
    """도면3 modelspace TEXT/MTEXT 중 부호-패턴 텍스트만 골라 height 분포 출력."""
    print("\n[1-A] 도면3 height 분포 (부호 패턴 매칭 텍스트만)")
    print("-" * 72)
    dxf = _dxf_path(_TARGET_DRAWING)
    if not os.path.exists(dxf):
        print(f"   ! DXF 없음: {dxf}")
        return {"recommended_min_height": None, "buckets": []}

    height_to_samples: dict[float, list[str]] = defaultdict(list)
    for _e, _t, text, height in _iter_text_entities(dxf):
        if not _SYMBOL_LIKE.match(text):
            continue
        head = text.split("/")[0].split("-")[0].split(" ")[0]
        if not re.match(r"^[A-Z]+\d+$", head):
            continue
        # 도면3 명명체계(C/G/B/RG/RB/CG/CRG/RSG) 부호 또는 정답지 부호만
        if head not in {"C1", "C2", "C3", "C4"} and not head.startswith(
            ("C", "G", "B", "RG", "RB", "CG", "RSG")
        ):
            continue
        if height is None:
            continue
        bucket = round(height, 1)
        height_to_samples[bucket].append(text)

    rows = sorted(height_to_samples.items())
    print(f"   {'height':>10}  {'count':>6}   샘플(최대 5)")
    for h, samples in rows:
        sample_str = ", ".join(sorted(set(samples))[:5])
        print(f"   {h:>10.1f}  {len(samples):>6}   {sample_str}")

    heights_sorted = sorted(height_to_samples)
    recommended: float | None = None
    if len(heights_sorted) >= 2:
        gaps = [
            (
                heights_sorted[i + 1] - heights_sorted[i],
                heights_sorted[i],
                heights_sorted[i + 1],
            )
            for i in range(len(heights_sorted) - 1)
        ]
        biggest = max(gaps, key=lambda g: g[0])
        recommended = biggest[2]
        print(
            f"\n   → 가장 큰 갭: {biggest[1]:.1f} → {biggest[2]:.1f} "
            f"(Δ={biggest[0]:.1f})"
        )
        print(
            f"   → 추천 min_height: {recommended:.0f} (위쪽 height 만 카운트)"
        )
    else:
        print("   → height 분포가 1개 무리 — 필터 불필요할 수도 있음")
    return {"recommended_min_height": recommended, "buckets": rows}


def section_b_slash_pattern_per_drawing() -> dict:
    """도면1·2·3·4 전체에서 ^[A-Z]+\\d+/[A-Z]+\\d+$ 텍스트 빈도."""
    print("\n[1-B] 슬래시 패턴 (^[A-Z]+\\d+/[A-Z]+\\d+$) 도면별 카운트")
    print("-" * 72)
    print(
        f"   {'도면':<8}{'슬래시 텍스트':>14}{'유니크':>10}   샘플(최대 5)"
    )
    summary: dict[str, dict] = {}
    for drawing in ("도면1", "도면2", "도면3", "도면4"):
        dxf = _dxf_path(drawing)
        if not os.path.exists(dxf):
            print(f"   {drawing:<8}{'(파일 없음)':>14}")
            summary[drawing] = {"total": 0, "unique": []}
            continue
        slash_texts: list[str] = []
        for _e, _t, text, _h in _iter_text_entities(dxf):
            if _SLASH_PATTERN.match(text):
                slash_texts.append(text)
        uniq = sorted(set(slash_texts))
        sample = ", ".join(uniq[:5])
        print(
            f"   {drawing:<8}{len(slash_texts):>14}{len(uniq):>10}   {sample}"
        )
        summary[drawing] = {"total": len(slash_texts), "unique": uniq}
    return summary


def section_c_auto_policy() -> dict:
    """도면3 에 대한 auto_detect_policy 결과 출력."""
    print("\n[1-C] 도면3 신호 2·3 자동 판정")
    print("-" * 72)
    dxf = _dxf_path(_TARGET_DRAWING)
    expected = drawing_symbol_totals(
        category="기둥", drawings=[_TARGET_DRAWING]
    )
    symbols = sorted(expected.get(_TARGET_DRAWING, {}).keys())
    min_h = load_text_height_filter().get(_TARGET_DRAWING)
    print(f"   화이트리스트(정답지): {symbols}")
    print(f"   yaml min_height: {min_h}")

    decision = auto_detect_policy(
        dxf, symbols, min_text_height=min_h, **load_auto_policy_params()
    )
    diag = decision["diagnostics"]
    print(
        f"   exclude_table_regions: {decision['exclude_table_regions']}"
    )
    print(f"     - 일람표 후보 영역: {diag['table_regions_count']}곳")
    for region in diag["table_regions"][:3]:
        x0, y0, x1, y1 = region["bbox"]
        syms = ", ".join(
            f"{s}({n})" for s, n in sorted(region["symbols"].items())
        )
        print(
            f"        bbox ({x0:.1f},{y0:.1f})~({x1:.1f},{y1:.1f})  {syms}"
        )
    print(f"   exclude_with_spec: {decision['exclude_with_spec']}")
    print(f"     - 규격형 텍스트 수: {diag['spec_pattern_count']}")
    print(
        f"     - 임계값(부호 수×0.3): "
        f"{diag['spec_pattern_threshold_count']:.1f}"
    )
    print(f"     - 단독형: {diag['standalone_counts']}")
    print(f"     - 규격형: {diag['withspec_counts']}")
    if diag["protection_triggered"]:
        print(
            f"     - 보호 발동(규격형 전용 부호): "
            f"{diag['protected_symbols']}"
        )
    return {
        "policy": {
            "exclude_table_regions": decision["exclude_table_regions"],
            "exclude_with_spec": decision["exclude_with_spec"],
        },
        "diagnostics": diag,
    }


def _match_with_slash(text: str, whitelist: set[str]) -> str | None:
    """counter.match_symbol 의 가상 확장본 — 슬래시(/)를 단어 경계에 추가."""
    text = text.strip()
    if text in whitelist:
        return text
    for w in sorted(whitelist, key=len, reverse=True):
        if text.startswith(w):
            after = text[len(w):]
            if not after:
                return w
            if after[0] in (" ", "-", "/"):
                return w
            if after[0].isdigit():
                continue
    return None


def section_d_simulation(
    policy: dict, recommended_min_height: float | None
) -> dict:
    """도면3 기둥 시뮬레이션 — 슬래시 매칭 ON + 신호 2·3 자동 + height 필터."""
    print(
        "\n[1-D] 도면3 기둥 슬래시 매칭 시뮬레이션 "
        "(코드 변경 없음, 가상 매칭)"
    )
    print("-" * 72)
    dxf = _dxf_path(_TARGET_DRAWING)
    expected = drawing_symbol_totals(
        category="기둥", drawings=[_TARGET_DRAWING]
    )[_TARGET_DRAWING]
    symbols = set(expected.keys())
    min_h = recommended_min_height

    counts: Counter = Counter()
    matched_samples: dict[str, list[str]] = defaultdict(list)
    for entity, dtype, text, height in _iter_text_entities(dxf):
        sym = _match_with_slash(text, symbols)
        if sym is None:
            continue
        if min_h is not None and height is not None and height < min_h:
            continue
        counts[sym] += 1
        matched_samples[sym].append(text)

    final = dict(counts)
    if policy["exclude_table_regions"]:
        # 일람표 한 곳에서 C1·C2·C3·C4 각 1개 → 1씩 차감 (시뮬 근사)
        # 본선 baseline.compute_drawing 은 detect_table_region 으로 정확 처리.
        for sym in ("C1", "C2", "C3", "C4"):
            if sym in final and final[sym] > 0:
                final[sym] -= 1

    if policy["exclude_with_spec"]:
        for sym in list(final.keys()):
            spec_like = [
                t
                for t in matched_samples.get(sym, [])
                if t != sym and not _SLASH_PATTERN.match(t)
            ]
            final[sym] = max(0, final[sym] - len(spec_like))

    print(
        f"   {'부호':<6}{'예측':>6}{'정답':>6}{'차이':>6}   "
        f"상태   샘플(최대 5)"
    )
    pass_count = 0
    for sym in sorted(expected):
        pred = final.get(sym, 0)
        exp = expected[sym]
        diff = pred - exp
        ok = abs(diff) <= 1 if exp <= 5 else abs(diff) <= exp * 0.05
        if ok:
            pass_count += 1
        sample = ", ".join(sorted(set(matched_samples.get(sym, [])))[:5])
        status = "PASS" if ok else "FAIL"
        print(
            f"   {sym:<6}{pred:>6}{exp:>6}{diff:>+6}   "
            f"{status:<6} {sample}"
        )
    print(f"\n   → {pass_count}/{len(expected)} 통과")
    return {
        "pass_count": pass_count,
        "total": len(expected),
        "predictions": {s: final.get(s, 0) for s in expected},
        "expected": expected,
        "min_h_used": min_h,
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 72)
    print(" 라운드 8 사전 진단 — 도면3 기둥 추가 가능성 측정")
    print("=" * 72)

    sec_a = section_a_height_distribution()
    sec_b = section_b_slash_pattern_per_drawing()
    sec_c = section_c_auto_policy()
    sec_d = section_d_simulation(
        sec_c["policy"], sec_a["recommended_min_height"]
    )

    print("\n" + "=" * 72)
    print(" 진단 결과 요약 — 작업 2 진행 조건 평가")
    print("=" * 72)
    cond_b = all(
        len(sec_b.get(d, {}).get("unique", [])) == 0
        for d in ("도면1", "도면2", "도면4")
    )
    cond_c = (
        sec_c["policy"]["exclude_table_regions"]
        and sec_c["policy"]["exclude_with_spec"]
    )
    cond_d = sec_d["pass_count"] == sec_d["total"]
    print(f"  조건 B (도면1·2·4 슬래시 패턴 0): {'OK' if cond_b else 'FAIL'}")
    print(f"  조건 C (도면3 신호 2·3 자동 ON): {'OK' if cond_c else 'FAIL'}")
    print(f"  조건 D (도면3 시뮬 4/4 PASS):    {'OK' if cond_d else 'FAIL'}")
    if cond_b and cond_c and cond_d:
        print("\n  ⇒ 작업 2 진행 가능")
    else:
        print("\n  ⇒ 작업 2 보류 — 멘토 결정 필요")


if __name__ == "__main__":
    main()
