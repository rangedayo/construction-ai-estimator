"""라운드 9 사전 진단 — 도면5 기둥 추가 가능성 측정.

코드(counter.py / yaml / baseline.py / auto_policy.py / test_regression.py)
변경 전, 다음 여섯 가지를 측정해 라운드 9 작업 2 의사결정 갈래(α/β/γ)를
선택할 근거를 확보한다.

  1) modelspace TEXT/MTEXT 화이트리스트 매칭 텍스트의 height 분포
  2) 부호 표기 방식 분포 (modelspace TEXT vs INSERT 블록 TEXT vs INSERT ATTRIB)
  3) 슬래시/하이픈/공백 결합 표기 빈도
  4) 일람표 영역 검출 시뮬레이션 (4-A 5컷 미적용, 4-B 5컷 적용)
  5) 신호 3 자동 판정 시뮬레이션 (auto_policy._detect_spec_pattern)
  6) auto_policy/baseline 일람표 검출 불일치 재현 여부 (라운드 8 H 부채)
  + 사전 시뮬레이션 카운트 (override 없음 자동 / override 도면3와 동일)

LLM 호출 없음. ezdxf 만 사용. 같은 입력 → 같은 출력.
본선 코드(counter / yaml / baseline / auto_policy / test_regression) 미변경.
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

from auto_policy import _detect_spec_pattern  # noqa: E402
from counter import _clean_mtext, match_symbol  # noqa: E402
from detect_table_region import (  # noqa: E402
    detect_table_regions,
    load_text_layout,
)
from ground_truth import (  # noqa: E402
    PROJECT_ROOT,
    drawing_symbol_totals,
    load_auto_policy_params,
    load_table_region_params,
    load_text_height_filter,
    within_tolerance,
)

_TARGET_DRAWING = "도면5"
_TARGET_SYMBOLS = ("C1", "C2", "C3", "C4")
_SLASH_PATTERN = re.compile(r"^([A-Z]+\d+)/[A-Z]+\d+$")
_HYPHEN_PATTERN = re.compile(r"^([A-Z]+\d+)-")
_SPACE_PATTERN = re.compile(r"^([A-Z]+\d+) ")

# 라운드 8 baseline.py 와 동일 — 일람표 검출 입력 정리용 좌표 컷
_TABLE_SPARSE_MAX = 5


def _dxf_path(drawing: str) -> str:
    return os.path.join(PROJECT_ROOT, "sample_data", f"{drawing}.dxf")


def _iter_modelspace_text(dxf_path: str):
    """modelspace TEXT/MTEXT 만 순회 — (entity, dtype, text, height)."""
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


def _iter_block_text(doc, block_name: str):
    """블록 정의 안의 TEXT/MTEXT/ATTDEF 텍스트만 순회 — (btype, text)."""
    try:
        block = doc.blocks.get(block_name)
    except Exception:
        return
    if block is None:
        return
    for be in block:
        btype = be.dxftype()
        if btype == "TEXT":
            try:
                val = be.dxf.text.strip()
            except Exception:
                continue
        elif btype == "MTEXT":
            try:
                val = _clean_mtext(
                    be.plain_mtext() if hasattr(be, "plain_mtext") else be.dxf.text
                )
            except Exception:
                continue
        elif btype == "ATTDEF":
            try:
                val = be.dxf.text.strip()
            except Exception:
                continue
        else:
            continue
        if val:
            yield btype, val


def section_1_height_distribution() -> dict:
    """modelspace TEXT/MTEXT 의 화이트리스트(C1·C2·C3·C4) 매칭 텍스트 height 분포."""
    print("\n[진단 1] height 분포 (화이트리스트 매칭 텍스트만)")
    print("-" * 72)
    dxf = _dxf_path(_TARGET_DRAWING)
    if not os.path.exists(dxf):
        print(f"   ! DXF 없음: {dxf}")
        return {"buckets": [], "recommended_min_height": None}

    wl = set(_TARGET_SYMBOLS)
    height_to_samples: dict[float, list[str]] = defaultdict(list)
    for _e, _t, text, height in _iter_modelspace_text(dxf):
        sym = match_symbol(text, wl, exclude_with_spec=False)
        if sym is None:
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
        print(f"   → 추천 min_height (적용은 다음 단계): {recommended:.1f}")
    print(
        "   * 도면3 비교: 본체=221.8(작음), 일람표=275.6(큼), 추천 338→본체 죽음 → null 채택."
    )
    return {
        "buckets": [
            {"height": h, "count": len(s), "samples": sorted(set(s))[:5]}
            for h, s in rows
        ],
        "recommended_min_height": recommended,
    }


def section_2_representation() -> dict:
    """C1~C4 가 어떤 엔티티 경로에 그려져 있는지 분류."""
    print("\n[진단 2] 부호 표기 방식 분포 (C1~C4)")
    print("-" * 72)
    dxf = _dxf_path(_TARGET_DRAWING)
    if not os.path.exists(dxf):
        print(f"   ! DXF 없음: {dxf}")
        return {}

    wl = set(_TARGET_SYMBOLS)
    bucket_names = (
        "A.msp_단독형",
        "B.msp_슬래시결합",
        "C.msp_규격결합",
        "D.INSERT_블록TEXT",
        "E.INSERT_ATTRIB",
    )
    table: dict[str, Counter] = {b: Counter() for b in bucket_names}

    doc = ezdxf.readfile(dxf)
    msp = doc.modelspace()

    for _e, _t, text, _h in _iter_modelspace_text(dxf):
        sym = match_symbol(text, wl, exclude_with_spec=False)
        if sym is None:
            continue
        if text == sym:
            table["A.msp_단독형"][sym] += 1
        elif _SLASH_PATTERN.match(text):
            table["B.msp_슬래시결합"][sym] += 1
        else:
            table["C.msp_규격결합"][sym] += 1

    for entity in msp:
        if entity.dxftype() != "INSERT":
            continue
        try:
            block_name = entity.dxf.name
        except Exception:
            continue

        try:
            for attrib in entity.attribs:
                try:
                    val = (
                        attrib.dxf.text.strip()
                        if attrib.dxf.hasattr("text")
                        else ""
                    )
                except Exception:
                    val = ""
                if not val:
                    continue
                sym = match_symbol(val, wl, exclude_with_spec=False)
                if sym is not None:
                    table["E.INSERT_ATTRIB"][sym] += 1
        except Exception:
            pass

        for _btype, val in _iter_block_text(doc, block_name):
            sym = match_symbol(val, wl, exclude_with_spec=False)
            if sym is not None:
                table["D.INSERT_블록TEXT"][sym] += 1

    header = (
        f"   {'표기 방식':<22}"
        + "".join(f"{s:>6}" for s in _TARGET_SYMBOLS)
        + "   합계"
    )
    print(header)
    summary: dict[str, dict] = {}
    for bname in bucket_names:
        counts = table[bname]
        line = f"   {bname:<22}"
        total = 0
        for s in _TARGET_SYMBOLS:
            n = counts.get(s, 0)
            line += f"{n:>6}"
            total += n
        line += f"{total:>8}"
        print(line)
        summary[bname] = {s: counts.get(s, 0) for s in _TARGET_SYMBOLS}
        summary[bname]["합계"] = total

    print(
        "\n   * 도면3 비교: 본체이 modelspace TEXT 슬래시 결합형(C1/P1 등). "
        "도면5 동형이면 라운드 8 보편 룰 그대로 적용 가능."
    )
    return summary


def section_3_combo_patterns() -> dict:
    """modelspace TEXT/MTEXT 중 슬래시/하이픈/공백 결합 표기를 부호별로 카운트."""
    print("\n[진단 3] 결합 표기 빈도 (modelspace TEXT/MTEXT 만)")
    print("-" * 72)
    dxf = _dxf_path(_TARGET_DRAWING)
    if not os.path.exists(dxf):
        print(f"   ! DXF 없음: {dxf}")
        return {}

    wl = set(_TARGET_SYMBOLS)
    by_pattern: dict[str, Counter] = {
        "슬래시(C1/P1)": Counter(),
        "하이픈(C1-XXX)": Counter(),
        "공백(C1 350x...)": Counter(),
    }
    samples: dict[str, dict[str, list[str]]] = {
        k: defaultdict(list) for k in by_pattern
    }
    for _e, _t, text, _h in _iter_modelspace_text(dxf):
        sym = match_symbol(text, wl, exclude_with_spec=False)
        if sym is None or text == sym:
            continue
        if _SLASH_PATTERN.match(text):
            by_pattern["슬래시(C1/P1)"][sym] += 1
            samples["슬래시(C1/P1)"][sym].append(text)
        elif _HYPHEN_PATTERN.match(text):
            by_pattern["하이픈(C1-XXX)"][sym] += 1
            samples["하이픈(C1-XXX)"][sym].append(text)
        elif _SPACE_PATTERN.match(text):
            by_pattern["공백(C1 350x...)"][sym] += 1
            samples["공백(C1 350x...)"][sym].append(text)

    header = (
        f"   {'패턴':<22}"
        + "".join(f"{s:>6}" for s in _TARGET_SYMBOLS)
        + "   합계"
    )
    print(header)
    summary: dict[str, dict] = {}
    for pname, counts in by_pattern.items():
        line = f"   {pname:<22}"
        total = 0
        for s in _TARGET_SYMBOLS:
            n = counts.get(s, 0)
            line += f"{n:>6}"
            total += n
        line += f"{total:>8}"
        print(line)
        summary[pname] = {s: counts.get(s, 0) for s in _TARGET_SYMBOLS}
        summary[pname]["합계"] = total

    expected = drawing_symbol_totals(category="기둥", drawings=[_TARGET_DRAWING]).get(
        _TARGET_DRAWING, {}
    )
    if expected:
        print("\n   슬래시 결합 vs 정답 대조 (도면3 패턴이면 일치 기대):")
        for s in _TARGET_SYMBOLS:
            slash_n = by_pattern["슬래시(C1/P1)"].get(s, 0)
            exp = expected.get(s, 0)
            print(f"     {s}: 슬래시 {slash_n} / 정답 {exp}")

    print("\n   샘플 (각 패턴 최대 5):")
    for pname in by_pattern:
        flat = []
        for s in _TARGET_SYMBOLS:
            flat.extend(samples[pname].get(s, []))
        uniq = sorted(set(flat))[:5]
        if uniq:
            print(f"     {pname}: {', '.join(uniq)}")
    return summary


def _run_table_detection(label: str, coords: dict, extent: tuple) -> list[dict]:
    params = load_table_region_params()
    regions = detect_table_regions(coords, extent, **params)
    print(f"   {label}: {len(regions)}곳")
    for region in regions[:3]:
        x0, y0, x1, y1 = region["bbox"]
        syms = ", ".join(
            f"{s}({n})" for s, n in sorted(region["symbols"].items())
        )
        print(f"      bbox ({x0:.1f},{y0:.1f})~({x1:.1f},{y1:.1f})  {syms}")
    return regions


def section_4_table_detection() -> dict:
    """4-A 5컷 미적용(auto_policy 경로) vs 4-B 5컷 적용(baseline 경로)."""
    print("\n[진단 4] 일람표 검출 시뮬레이션 — auto_policy vs baseline 경로")
    print("-" * 72)
    dxf = _dxf_path(_TARGET_DRAWING)
    if not os.path.exists(dxf):
        print(f"   ! DXF 없음: {dxf}")
        return {}

    min_h = load_text_height_filter().get(_TARGET_DRAWING)
    print(f"   yaml min_height (도면5 미등록 시 None): {min_h}")

    coords, extent = load_text_layout(
        dxf,
        list(_TARGET_SYMBOLS),
        min_text_height=min_h,
        exclude_with_spec=True,
    )
    print("   load_text_layout 결과 부호별 좌표 수:")
    for s in _TARGET_SYMBOLS:
        print(f"     {s}: {len(coords.get(s, []))}")
    extras = [s for s in coords if s not in _TARGET_SYMBOLS]
    if extras:
        head = sorted(extras, key=lambda s: -len(coords[s]))[:8]
        line = ", ".join(f"{s}({len(coords[s])})" for s in head)
        print(f"   화이트리스트 외 부호 (입력 오염 지표): {line}")

    print("\n   4-A. 5컷 미적용 (auto_policy._detect_table_regions 와 동일 경로):")
    regions_no_cut = _run_table_detection("검출 영역", coords, extent)

    sparse = {s: pts for s, pts in coords.items() if len(pts) <= _TABLE_SPARSE_MAX}
    excluded = [
        (s, len(coords[s])) for s in coords if len(coords[s]) > _TABLE_SPARSE_MAX
    ]
    print(
        f"\n   4-B. 5컷 적용 (baseline.compute_drawing 와 동일 경로): "
        f"{len(coords)} 부호 → {len(sparse)} 부호 남김"
    )
    if excluded:
        line = ", ".join(f"{s}({n})" for s, n in excluded[:8])
        print(f"     5컷으로 제외된 부호: {line}")
    regions_cut = _run_table_detection("검출 영역", sparse, extent)

    return {
        "min_h": min_h,
        "coords_by_symbol": {s: len(coords.get(s, [])) for s in _TARGET_SYMBOLS},
        "extras_top": [(s, len(coords[s])) for s in extras],
        "no_cut_regions": [
            {"bbox": r["bbox"], "symbols": dict(r["symbols"])}
            for r in regions_no_cut
        ],
        "cut_regions": [
            {"bbox": r["bbox"], "symbols": dict(r["symbols"])} for r in regions_cut
        ],
    }


def section_5_spec_signal() -> dict:
    """auto_policy._detect_spec_pattern 결과 — 도면3 슬래시 부산물 재현 여부."""
    print("\n[진단 5] 신호 3 (exclude_with_spec) 자동 판정")
    print("-" * 72)
    dxf = _dxf_path(_TARGET_DRAWING)
    if not os.path.exists(dxf):
        print(f"   ! DXF 없음: {dxf}")
        return {}
    min_h = load_text_height_filter().get(_TARGET_DRAWING)
    params = load_auto_policy_params()
    threshold_ratio = params["spec_pattern_threshold"]
    n_symbols = len(_TARGET_SYMBOLS)
    threshold = n_symbols * threshold_ratio

    spec_count, protection, protected, standalone, withspec = _detect_spec_pattern(
        dxf, list(_TARGET_SYMBOLS), min_h
    )
    auto_decision = spec_count >= threshold and not protection

    print(f"   standalone_counts: {standalone}")
    print(f"   withspec_counts  : {withspec}")
    print(f"   spec_pattern_count : {spec_count}")
    print(f"   threshold (부호 {n_symbols} × {threshold_ratio}): {threshold:.1f}")
    print(f"   보호 발동(standalone 0 & withspec ≥ 1): {protection}")
    if protection:
        print(f"     보호 부호: {protected}")
    print(f"   → 자동 판정 exclude_with_spec: {auto_decision}")
    print(
        "   * 도면3 비교: 자동 True (슬래시 결합 32개가 withspec 으로 오분류 → 1→34)."
    )
    return {
        "standalone": standalone,
        "withspec": withspec,
        "spec_count": spec_count,
        "threshold": threshold,
        "protection": protection,
        "protected": protected,
        "auto_decision": auto_decision,
    }


def section_6_mismatch(sec4: dict, sec5: dict) -> dict:
    """진단 4 결과를 표 한 줄로 정리해 라운드 8 부채 재현 여부 판정."""
    print("\n[진단 6] auto_policy vs baseline 일람표 검출 불일치 재현 여부")
    print("-" * 72)
    no_cut = len(sec4.get("no_cut_regions", []))
    cut = len(sec4.get("cut_regions", []))
    print(f"   {'경로':<30}{'검출 영역 수':>14}{'신호 2 자동 판정':>22}")
    print(
        f"   {'auto_policy (5컷 미적용)':<30}"
        f"{no_cut:>14}"
        f"{('True' if no_cut >= 1 else 'False'):>22}"
    )
    diff_label = "(정답 차감 가능: " + ("Yes" if cut >= 1 else "No") + ")"
    print(
        f"   {'baseline (5컷 적용)':<30}"
        f"{cut:>14}"
        f"{diff_label:>22}"
    )
    reproduced = (no_cut == 0) and (cut >= 1)
    if reproduced:
        verdict = "재현 — 도면3 동형 부채 (auto 0곳 / baseline 1곳 이상)"
    elif no_cut >= 1 and cut >= 1:
        verdict = "비재현 — 두 경로 모두 검출 (5컷 보정 불필요)"
    elif no_cut == 0 and cut == 0:
        verdict = (
            "비재현 — 두 경로 모두 0곳 (도면5에는 일람표 없음 또는 검출 룰 한계)"
        )
    else:
        verdict = f"이례 — auto {no_cut}곳 / baseline {cut}곳"
    print(f"\n   결론: {verdict}")
    return {
        "auto_count": no_cut,
        "baseline_count": cut,
        "reproduced": reproduced,
        "verdict": verdict,
    }


def _height_filter(entity, dtype: str, min_h: float | None) -> bool:
    if min_h is None:
        return True
    try:
        h = float(
            entity.dxf.char_height if dtype == "MTEXT" else entity.dxf.height
        )
    except Exception:
        return True
    return h >= min_h


def _count_in_dxf(
    dxf: str, min_h: float | None, exclude_with_spec: bool
) -> Counter:
    """진단용 카운트 (slash-as-combo 항상 True). spec 옵션만 가른다.

    counter.count_members 의 매칭 룰을 같은 식으로 재구성 — 본선 코드 미호출.
    """
    counts: Counter = Counter()
    wl = set(_TARGET_SYMBOLS)
    doc = ezdxf.readfile(dxf)
    msp = doc.modelspace()

    def _match(text: str) -> str | None:
        return match_symbol(
            text,
            wl,
            exclude_with_spec=exclude_with_spec,
            treat_slash_as_combo=True,
        )

    for entity in msp:
        dtype = entity.dxftype()
        if dtype in ("TEXT", "MTEXT"):
            try:
                raw = entity.dxf.text
            except Exception:
                continue
            if not raw:
                continue
            text = _clean_mtext(raw) if dtype == "MTEXT" else raw.strip()
            sym = _match(text)
            if sym is None:
                continue
            if not _height_filter(entity, dtype, min_h):
                continue
            counts[sym] += 1
        elif dtype == "INSERT":
            try:
                block_name = entity.dxf.name
            except Exception:
                block_name = None
            try:
                for attrib in entity.attribs:
                    try:
                        val = (
                            attrib.dxf.text.strip()
                            if attrib.dxf.hasattr("text")
                            else ""
                        )
                    except Exception:
                        val = ""
                    if not val:
                        continue
                    sym = _match(val)
                    if sym is not None:
                        counts[sym] += 1
            except Exception:
                pass
            if block_name is None:
                continue
            for _btype, val in _iter_block_text(doc, block_name):
                sym = _match(val)
                if sym is not None:
                    counts[sym] += 1
    return counts


def section_7_simulation(sec4: dict, sec5: dict) -> dict:
    """도면5 회귀 예상 — 시나리오 A(auto), B(override 도면3 동형)."""
    print("\n[추가] 사전 시뮬레이션 카운트")
    print("-" * 72)
    dxf = _dxf_path(_TARGET_DRAWING)
    expected = drawing_symbol_totals(
        category="기둥", drawings=[_TARGET_DRAWING]
    ).get(_TARGET_DRAWING, {})
    min_h = sec4.get("min_h")

    raw = _count_in_dxf(dxf, min_h, exclude_with_spec=False)
    spec = _count_in_dxf(dxf, min_h, exclude_with_spec=True)
    print(
        "   raw (slash combo, spec 미적용)       : "
        + ", ".join(f"{s}={raw.get(s, 0)}" for s in _TARGET_SYMBOLS)
    )
    print(
        "   after_spec (exclude_with_spec=True)  : "
        + ", ".join(f"{s}={spec.get(s, 0)}" for s in _TARGET_SYMBOLS)
    )

    auto_table = len(sec4.get("no_cut_regions", [])) >= 1
    auto_spec_on = sec5["auto_decision"]
    a_base = dict(spec) if auto_spec_on else dict(raw)
    a_final: dict[str, int] = {s: a_base.get(s, 0) for s in _TARGET_SYMBOLS}
    if auto_table:
        for r in sec4["no_cut_regions"]:
            for s, n in r["symbols"].items():
                if s in a_final:
                    a_final[s] = max(0, a_final[s] - n)

    b_final: dict[str, int] = {s: spec.get(s, 0) for s in _TARGET_SYMBOLS}
    for r in sec4["cut_regions"]:
        for s, n in r["symbols"].items():
            if s in b_final:
                b_final[s] = max(0, b_final[s] - n)

    def _line(label: str, policy_desc: str, final: dict[str, int]) -> dict:
        passes = []
        for s in _TARGET_SYMBOLS:
            ok = within_tolerance(final.get(s, 0), expected.get(s, 0))
            passes.append("PASS" if ok else "FAIL")
        cells = "  ".join(
            f"{s}:{final.get(s, 0)}/{expected.get(s, 0)}({p})"
            for s, p in zip(_TARGET_SYMBOLS, passes)
        )
        pass_n = sum(1 for p in passes if p == "PASS")
        print(f"   {label:<24}{policy_desc:<30}{cells}  → {pass_n}/4")
        return {"final": final, "passes": passes, "pass_count": pass_n}

    print(
        f"\n   {'시나리오':<24}{'정책':<30}부호별 (예측/정답/판정)"
    )
    a_policy = f"신호2={auto_table}, 신호3={auto_spec_on}"
    b_policy = "신호2=True(강제), 신호3=True(강제)"
    res_a = _line("A. override 없음 (자동)", a_policy, a_final)
    res_b = _line("B. override 도면3 동형", b_policy, b_final)

    return {
        "expected": expected,
        "min_h_used": min_h,
        "raw": dict(raw),
        "after_spec": dict(spec),
        "scenario_A": res_a,
        "scenario_B": res_b,
    }


def recommend_branch(
    sec3: dict, sec4: dict, sec5: dict, sec6: dict, sec7: dict
) -> str:
    """진단 결과를 보고 α/β/γ 중 어느 갈래를 추천하는지 근거와 함께 출력."""
    print("\n" + "=" * 72)
    print(" 라운드 9 작업 2 의사결정 갈래 평가")
    print("=" * 72)

    slash_n = sec3.get("슬래시(C1/P1)", {}).get("합계", 0)
    spec_decision = sec5.get("auto_decision", False)
    auto_table = sec6.get("auto_count", 0)
    base_table = sec6.get("baseline_count", 0)
    reproduced = sec6.get("reproduced", False)
    pass_b = sec7["scenario_B"]["pass_count"]
    pass_a = sec7["scenario_A"]["pass_count"]

    print(f"  - 슬래시 결합 표기 수      : {slash_n}")
    print(f"  - 신호 3 자동 판정         : {spec_decision}")
    print(f"  - auto_policy 일람표 검출  : {auto_table}곳")
    print(f"  - baseline 일람표 검출     : {base_table}곳")
    print(f"  - 도면3 부채 재현 여부     : {reproduced}")
    print(f"  - 시나리오 A (auto) PASS   : {pass_a}/4")
    print(f"  - 시나리오 B (override) PASS: {pass_b}/4")

    if pass_b == 4 and reproduced:
        branch = "γ"
        reason = (
            "도면3 부채(auto 0 / baseline ≥1)가 도면5에서 재현됨. "
            "두 도면에서 같은 증상이 나타나면 보편 룰(통일)로 해결할 정당성이 확보된다. "
            "권장: auto_policy._detect_table_regions 에 _TABLE_SPARSE_MAX 보정 이식 → "
            "도면3 override 제거 가능성 검증 → 도면5 회귀 추가."
        )
    elif pass_b == 4 and not reproduced:
        branch = "α"
        reason = (
            "도면3 동형 패턴 (override 도면3 동형으로 4/4 PASS) 이지만 "
            "auto 경로에서도 일람표 검출이 성공한다. 도면3 특수성으로 확정. "
            "권장: yaml 에 도면5 entry 추가 (도면3 동형), baseline·test_regression 등록. "
            "auto_policy 통일 작업은 보류."
        )
    elif pass_a == 4 and not reproduced:
        branch = "α-"
        reason = (
            "시나리오 A(자동) 만으로도 4/4 PASS. override 불필요. "
            "권장: policy_override.도면5 를 null 로 두고 baseline·test_regression 등록만."
        )
    else:
        branch = "β"
        reason = (
            "도면3 룰만으로는 도면5 가 완전히 풀리지 않는다. 추가 패턴 분석 필요. "
            f"시나리오 A={pass_a}/4, B={pass_b}/4 — 새 룰 정의 후 별도 작업 2 프롬프트."
        )
    print(f"\n  → 추천 갈래: {branch}")
    print(f"     근거: {reason}")
    return branch


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 72)
    print(" 라운드 9 사전 진단 — 도면5 기둥 추가 가능성 측정")
    print("=" * 72)

    section_1_height_distribution()
    section_2_representation()
    sec3 = section_3_combo_patterns()
    sec4 = section_4_table_detection()
    sec5 = section_5_spec_signal()
    sec6 = section_6_mismatch(sec4, sec5)
    sec7 = section_7_simulation(sec4, sec5)
    recommend_branch(sec3, sec4, sec5, sec6, sec7)


if __name__ == "__main__":
    main()
