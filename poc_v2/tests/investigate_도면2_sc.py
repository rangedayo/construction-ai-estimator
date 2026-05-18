"""도면2 SC 누락 원인 진단 — 라운드 4 작업 4.

목적: 도면2의 SC1·SC2 부재가 DXF 의 어디에 어떻게 저장돼 있는지 *조사만* 한다.
counter.py 에 룰을 추가하거나 매칭 로직을 바꾸지 않는다. 이 스크립트는
진단 데이터(표·통계)만 생성한다.

조사 항목:
  4-A. SC 부재의 위치 단서 — modelspace TEXT/MTEXT 및 INSERT 블록 내부 텍스트
  4-B. 분리 TEXT 패턴 정량화 — 'S'+'C'+숫자 가 어떻게 쪼개져 저장됐는지
  4-C. 다른 부호의 누락 가능성 점검
  4-D. 결과 표

사용법:  poc_v2 디렉토리에서  `python tests/investigate_도면2_sc.py`
"""
from __future__ import annotations

import os
import re
import sys
from collections import Counter

import ezdxf

_HERE = os.path.dirname(os.path.abspath(__file__))
_POC_DIR = os.path.dirname(_HERE)
for _path in (_POC_DIR, _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from counter import _clean_mtext, count_members  # noqa: E402
from ground_truth import PROJECT_ROOT, drawing_symbol_totals  # noqa: E402

_DXF_PATH = os.path.join(PROJECT_ROOT, "sample_data", "도면2.dxf")
_DRAWING = "도면2"

# SC 분리 단서로 볼 짧은 텍스트 (S / C / 숫자 조각)
_FRAGMENT = re.compile(r"^(S|C|SC|C1|C2|S C|1|2)$", re.IGNORECASE)
# 근접 판정 거리 (도면2 큰 글자 height 가 400 이므로 그 ~6배 반경)
_NEAR_DIST = 2500.0


def _entity_text(entity) -> str:
    """TEXT/MTEXT/ATTRIB/ATTDEF 의 표시 문자열을 정규화해 돌려준다."""
    dtype = entity.dxftype()
    try:
        if dtype == "MTEXT":
            raw = entity.plain_mtext() if hasattr(entity, "plain_mtext") else entity.dxf.text
            return _clean_mtext(raw)
        if dtype in ("TEXT", "ATTRIB", "ATTDEF"):
            return entity.dxf.text.strip() if entity.dxf.hasattr("text") else ""
    except Exception:
        return ""
    return ""


def _entity_pos(entity):
    """엔티티의 대표 좌표 (insert 또는 align_point). 실패 시 None."""
    for attr in ("insert", "align_point"):
        try:
            pt = getattr(entity.dxf, attr)
            return (float(pt.x), float(pt.y))
        except Exception:
            continue
    return None


def section(title: str) -> None:
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def investigate() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if not os.path.exists(_DXF_PATH):
        print(f"[오류] DXF 없음: {_DXF_PATH}")
        return

    doc = ezdxf.readfile(_DXF_PATH)
    msp = doc.modelspace()

    section("도면2 SC 누락 조사 — 라운드 4 작업 4")
    print(f"DXF: {_DXF_PATH}")

    # ── 4-A. modelspace 직접 배치 TEXT/MTEXT 중 SC 단서 ──────────────────────
    section("4-A. modelspace 직접 TEXT/MTEXT 중 SC 관련 텍스트")
    msp_sc_texts: list[tuple[str, float, tuple[float, float] | None, str]] = []
    for e in msp:
        dt = e.dxftype()
        if dt not in ("TEXT", "MTEXT"):
            continue
        txt = _entity_text(e)
        if not txt:
            continue
        upper = txt.upper()
        if "SC" in upper or _FRAGMENT.match(txt):
            try:
                h = float(e.dxf.char_height if dt == "MTEXT" else e.dxf.height)
            except Exception:
                h = -1.0
            msp_sc_texts.append((txt, h, _entity_pos(e), dt))
    if msp_sc_texts:
        print(f"{'텍스트':<14}{'height':>9}  {'타입':<7}좌표")
        print("-" * 60)
        for txt, h, pos, dt in sorted(msp_sc_texts, key=lambda r: r[0]):
            pos_s = f"({pos[0]:.0f}, {pos[1]:.0f})" if pos else "(좌표없음)"
            print(f"{txt[:13]:<14}{h:>9.0f}  {dt:<7}{pos_s}")
        print(f"\n→ modelspace 직접 SC 단서 텍스트 {len(msp_sc_texts)}개")
    else:
        print("→ modelspace 직접 배치 텍스트에는 SC 단서 없음")

    # ── INSERT / 블록 정의 전수 조사 ─────────────────────────────────────────
    inserts = [e for e in msp if e.dxftype() == "INSERT"]
    section("4-A(계속). INSERT 블록 통계")
    block_name_counter: Counter = Counter(e.dxf.name for e in inserts)
    anon = {n: c for n, c in block_name_counter.items() if n.startswith("*")}
    named = {n: c for n, c in block_name_counter.items() if not n.startswith("*")}
    print(f"modelspace INSERT 총 {len(inserts)}개, "
          f"블록종류 {len(block_name_counter)}종 "
          f"(익명 {len(anon)}종 / 명명 {len(named)}종)")

    # 각 블록 정의 안의 텍스트 조각 수집
    block_texts: dict[str, list[str]] = {}
    for name in block_name_counter:
        try:
            block = doc.blocks.get(name)
        except Exception:
            block = None
        if block is None:
            continue
        frags: list[str] = []
        for be in block:
            if be.dxftype() in ("TEXT", "MTEXT", "ATTDEF"):
                t = _entity_text(be)
                if t:
                    frags.append(t)
        block_texts[name] = frags

    # SC 관련 텍스트를 품은 블록
    sc_blocks: list[tuple[str, int, list[str]]] = []
    for name, frags in block_texts.items():
        joined = " ".join(frags).upper()
        if "SC" in joined or any(_FRAGMENT.match(f) for f in frags):
            sc_blocks.append((name, block_name_counter[name], frags))
    section("4-A(계속). SC 단서를 품은 블록 정의")
    if sc_blocks:
        for name, cnt, frags in sorted(sc_blocks, key=lambda r: -r[1]):
            kind = "익명" if name.startswith("*") else "명명"
            print(f"  블록 [{name}] ({kind}, INSERT {cnt}회)  텍스트조각={frags}")
    else:
        print("  → SC 단서를 품은 블록 정의 없음")

    # ── 4-B. 분리 TEXT 패턴 정량화 ───────────────────────────────────────────
    section("4-B. 'S' / 'C' / 숫자 분리 패턴 정량화")

    # (1) 블록 내부 분리: 한 블록 정의 안에서 조각이 어떻게 쪼개졌나
    split_block_patterns: Counter = Counter()
    for name, cnt, frags in sc_blocks:
        norm = tuple(f.upper() for f in sorted(frags))
        split_block_patterns[norm] += cnt
    print("[B-1] SC 단서 블록의 내부 텍스트조각 조합 (조합 → INSERT 누적 횟수)")
    if split_block_patterns:
        for combo, cnt in split_block_patterns.most_common():
            print(f"    {list(combo)}  → {cnt}회")
    else:
        print("    (해당 없음)")

    # (2) modelspace 분리: 'S','C','SC','1','2' 등 독립 TEXT 의 인접 결합
    frag_entities: list[tuple[str, tuple[float, float]]] = []
    for e in msp:
        if e.dxftype() not in ("TEXT", "MTEXT"):
            continue
        txt = _entity_text(e)
        pos = _entity_pos(e)
        if txt and pos and _FRAGMENT.match(txt):
            frag_entities.append((txt.upper(), pos))
    print(f"\n[B-2] modelspace 독립 조각 텍스트('S'/'C'/'SC'/'1'/'2' 등): "
          f"{len(frag_entities)}개")
    frag_kind = Counter(t for t, _ in frag_entities)
    for t, c in frag_kind.most_common():
        print(f"    '{t}' × {c}")

    # 'S' 조각 기준으로 _NEAR_DIST 안의 'C'/'SC'/숫자 조각이 함께 있는지
    near_groups = 0
    for t, (x, y) in frag_entities:
        if t not in ("S", "SC"):
            continue
        nearby = [
            ot for ot, (ox, oy) in frag_entities
            if (ot != t or (ox, oy) != (x, y))
            and abs(ox - x) <= _NEAR_DIST and abs(oy - y) <= _NEAR_DIST
        ]
        if nearby:
            near_groups += 1
    print(f"    → 'S'/'SC' 조각 주변 {_NEAR_DIST:.0f} 반경에 다른 조각이 "
          f"함께 있는 경우: {near_groups}건")

    # ── 4-C. 다른 부호의 누락 점검 ───────────────────────────────────────────
    section("4-C. 도면2 전체 부호별 누락/과다 점검 (필터 미적용 기준)")
    expected = drawing_symbol_totals()[_DRAWING]
    symbols = sorted(expected.keys())
    counts_nofilter, _h, _c = count_members(
        _DXF_PATH, -1e18, -1e18, 1e18, 1e18, custom_whitelist=symbols
    )
    print(f"{'부호':<8}{'정답':>6}{'검출(무필터)':>14}{'차이':>8}   분류")
    print("-" * 52)
    for s in symbols:
        exp = expected[s]
        pred = counts_nofilter.get(s, 0)
        diff = pred - exp
        if diff < 0:
            cls = "누락(검출<정답)"
        elif diff > 0:
            cls = "과다(검출>정답)"
        else:
            cls = "일치"
        print(f"{s:<8}{exp:>6}{pred:>14}{diff:>+8}   {cls}")

    # ── 4-D. 결과 표 ─────────────────────────────────────────────────────────
    section("4-D. SC 누락 조사 결과 요약")
    # 필터 적용(302) 검출 — baseline 라운드4 값과 동일하게 산출
    counts_filtered, _h2, _c2 = count_members(
        _DXF_PATH, -1e18, -1e18, 1e18, 1e18,
        custom_whitelist=symbols, min_text_height=302,
    )
    print(f"{'부호':<8}{'정답':>6}{'검출(필터302)':>15}{'누락추정':>10}   원인후보")
    print("-" * 64)
    for s in ("SC1", "SC2"):
        exp = expected.get(s, 0)
        pred = counts_filtered.get(s, 0)
        miss = exp - pred
        cause = (
            f"분리/저-height TEXT (SC단서블록 {len(sc_blocks)}종, "
            f"독립조각 {len(frag_entities)}개)"
        )
        print(f"{s:<8}{exp:>6}{pred:>15}{miss:>10}   {cause}")

    print("\n[조사 결론]")
    if not sc_blocks and not frag_entities and not msp_sc_texts:
        print("  SC 텍스트 자체를 DXF 에서 찾지 못함 — TEXT 가 아닌 다른 표현"
              "(LINE 작도 등) 가능성.")
    else:
        print(f"  - modelspace 직접 SC 텍스트: {len(msp_sc_texts)}개")
        print(f"  - SC 단서 블록 정의: {len(sc_blocks)}종")
        print(f"  - modelspace 독립 조각 텍스트: {len(frag_entities)}개")
        print("  ※ 이 데이터는 진단용이며 counter.py 룰은 변경하지 않음.")


if __name__ == "__main__":
    investigate()
