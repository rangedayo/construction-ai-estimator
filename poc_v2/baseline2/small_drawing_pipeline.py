"""작은 도면 측정 파이프라인 — 라운드 베이스라인-2 작업 3.

작은 도면 dxf 1장 → 표제부 도면명 추출 → 정답지 시트 매칭 → 시트 종류에 맞는
측정(카운트·길이·규격) → 정답 비교 PASS/FAIL.

본선 무수정 (회귀 안전망)
    카운트  : counter.count_members + auto_policy.auto_detect_policy 재사용.
              큰 도면용 baseline.compute_drawing 은 도면명→큰 dxf 로 resolve 하므로
              작은 도면엔 못 쓴다. 동일 정책 로직을 작은 dxf 경로로 재현한다.
    길이    : length.measure.measure_column_length 그대로 호출.
    규격    : length.spec_extractor.extract_specs 그대로 호출.

일람표(부재 리스트) 차감
    작은 평면도에는 본체 배치 + 일람표가 함께 있다. 큰 도면은 일람표 영역을
    검출해 빼지만, 시트 단위로 쪼개면 일람표 부호 종류가 4종 미만이라 영역
    검출이 발화하지 않는다(도면4 1층=기둥 2종). 대신 spec_extractor 가 잡는
    "부호↔규격 페어"는 정확히 일람표 정의행이므로, 부호별 페어 수만큼 카운트에서
    차감한다. (배치 부호는 인접 규격이 없어 페어로 잡히지 않는다.)
"""
from __future__ import annotations

import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
_POC_DIR = os.path.join(PROJECT_ROOT, "poc_v2")
_TESTS_DIR = os.path.join(_POC_DIR, "tests")
for _path in (PROJECT_ROOT, _POC_DIR, _TESTS_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from auto_policy import auto_detect_policy  # noqa: E402
from counter import count_members  # noqa: E402
from ground_truth import (  # noqa: E402
    drawing_symbol_totals,
    load_auto_policy_params,
    load_policy_override,
    load_text_height_filter,
    within_tolerance,
)

from poc_v2.baseline2.sheet_name_matcher import (  # noqa: E402
    SheetMatch,
    load_count_sheet_rows,
    match_sheet,
)
from poc_v2.baseline2.sheet_title_extractor import extract_sheet_titles  # noqa: E402
from poc_v2.length.baseline_length import within_length_tolerance  # noqa: E402
from poc_v2.length.ground_truth_spec import (  # noqa: E402
    load_ground_truth_spec,
    load_section_instances,
)
from poc_v2.length.measure import measure_column_length  # noqa: E402
from poc_v2.length.spec_extractor import extract_specs  # noqa: E402

_FULL_EXTENT = (-1e18, -1e18, 1e18, 1e18)
_COLUMN_CATEGORY = "기둥"  # 이번 라운드 스코프
_DRAWING_RE = re.compile(r"^(도면\d+)")
_DONG_RE = re.compile(r"(\d+동)")  # 도면1-2동_... → "2동" (없으면 None)
_COORD_MATCH_EPS = 1.0  # 페어 부호 좌표 ↔ 카운트 좌표 겹침 판정(mm). 겹침=0.0, 비겹침≥5천


@dataclass
class SmallDrawingResult:
    """작은 도면 1장의 추출·매칭·측정·비교 결과."""
    file_path: str
    drawing: str
    extracted_title: Optional[str]
    matched_sheet: Optional[str]
    match_confidence: str            # exact | partial | fallback | unmatched
    kind: str                        # count | length | unmatched

    # 측정
    counts: dict[str, int] = field(default_factory=dict)
    length_mm: Optional[float] = None
    specs: dict[str, str] = field(default_factory=dict)

    # 정답
    expected_counts: dict[str, int] = field(default_factory=dict)
    expected_length: Optional[float] = None
    expected_specs: dict[str, str] = field(default_factory=dict)

    # PASS/FAIL (측정 대상 아니면 None)
    pass_counts: Optional[bool] = None
    pass_length: Optional[bool] = None
    pass_specs: Optional[bool] = None


def drawing_from_path(file_path: str) -> str:
    """파일명에서 도면 식별자 추출 ("도면4_종단면도.dxf" → "도면4")."""
    base = os.path.basename(file_path)
    match = _DRAWING_RE.match(base)
    return match.group(1) if match else os.path.splitext(base)[0]


def _column_symbols(drawing: str) -> list[str]:
    """이번 라운드 비교 대상 — 도면의 기둥 부호 유니버스."""
    totals = drawing_symbol_totals(category=_COLUMN_CATEGORY, drawings=[drawing])
    return sorted(totals.get(drawing, {}).keys())


def _count_columns(dxf_path: str, drawing: str) -> dict[str, int]:
    """작은 도면에서 부호별 최종 카운트(일람표 차감 적용).

    화이트리스트는 기둥+보 병합(일람표 영역·규격 매칭 휴리스틱이 큰 도면과
    동일하게 동작하도록). 반환 dict 는 전체 부호이며, 기둥 필터는 호출부에서.
    """
    symbols = sorted(drawing_symbol_totals(drawings=[drawing]).get(drawing, {}).keys())
    if not symbols:
        return {}
    min_h = load_text_height_filter().get(drawing)

    override = load_policy_override(drawing)
    if override is not None:
        exclude_with_spec = override["exclude_with_spec"]
    else:
        auto = auto_detect_policy(
            dxf_path, symbols, min_text_height=min_h, **load_auto_policy_params()
        )
        exclude_with_spec = auto["exclude_with_spec"]

    counts, _hits, coords_by_symbol = count_members(
        dxf_path, *_FULL_EXTENT, custom_whitelist=symbols,
        min_text_height=min_h, exclude_with_spec=exclude_with_spec,
        treat_slash_as_combo=True,
    )
    after = dict(counts)

    # 일람표 정의행 차감 — 단, 페어의 부호 좌표가 카운트된 배치 좌표와
    # 겹칠 때만. 일람표 부호 텍스트가 배치로 함께 카운트된 경우(도면3·4·5)만
    # 과다카운트이므로 차감 대상이다. 도면1 처럼 페어가 별도 범례 위치라
    # 애초에 카운트되지 않은 경우(좌표 수천 단위 이격) 차감하면 이중차감이 된다.
    member_list: Counter = Counter()
    for spec in extract_specs(dxf_path, drawing):
        sx, sy = spec.symbol_coord
        placed = coords_by_symbol.get(spec.symbol, [])
        if any(
            abs(cx - sx) <= _COORD_MATCH_EPS and abs(cy - sy) <= _COORD_MATCH_EPS
            for cx, cy in placed
        ):
            member_list[spec.symbol] += 1
    final = {
        sym: max(0, after.get(sym, 0) - member_list.get(sym, 0))
        for sym in set(after) | set(member_list)
    }
    return final


def _drawing_column_length(drawing: str) -> Optional[float]:
    """정답지 인스턴스에서 도면의 기둥 길이(공통값)를 가져온다."""
    instances = load_section_instances(drawings=[drawing])
    lengths = [
        inst.length_mm for inst in instances.values() if inst.length_mm is not None
    ]
    return max(lengths) if lengths else None


def _expected_column_specs(
    drawing: str, dong: Optional[str] = None
) -> dict[str, str]:
    """정답지 규격 → {기둥 부호: 정규화 규격}.

    dong 이 주어지면 그 동(section)의 규격만 쓴다. 도면1 처럼 같은 부호가 동별로
    다른 규격(1동 MC1 ≠ 2동 MC1)을 가질 때 동을 섞지 않기 위함. dong=None 이면
    전체(도면2~5: section 단일이라 무영향).
    """
    answers = load_ground_truth_spec(drawings=[drawing])
    columns = set(_column_symbols(drawing))
    out: dict[str, str] = {}
    for (_d, section, symbol), answer in answers.items():
        if symbol not in columns:
            continue
        if dong is not None and section is not None and section != dong:
            continue
        out[symbol] = answer.spec_normalized
    return out


def process_small_drawing(file_path: str) -> SmallDrawingResult:
    """작은 도면 dxf 1장을 처리해 SmallDrawingResult 를 반환한다."""
    drawing = drawing_from_path(file_path)
    dong_match = _DONG_RE.search(os.path.basename(file_path))
    dong = dong_match.group(1) if dong_match else None
    titles = extract_sheet_titles(file_path)
    extracted_title = titles[0].raw_text if titles else None

    columns = _column_symbols(drawing)
    # column_symbols 를 넘겨 골구도처럼 count 행이 보 부호뿐(기둥 0)인 시트가
    # length 라벨이면 length 로 라우팅되게 한다(기둥 스코프 placeholder).
    match: SheetMatch = match_sheet(
        drawing,
        [t.raw_text for t in titles],
        dong=dong,
        column_symbols=set(columns),
    )

    result = SmallDrawingResult(
        file_path=file_path,
        drawing=drawing,
        extracted_title=extracted_title,
        matched_sheet=match.matched_sheet,
        match_confidence=match.confidence,
        kind=match.kind,
    )

    if match.kind == "count":
        # 카운트 — 매칭된 시트의 기둥 정답과 비교
        sheet_rows = load_count_sheet_rows(drawing, category=_COLUMN_CATEGORY)
        expected = sheet_rows.get(match.matched_sheet, {})
        result.expected_counts = {s: expected.get(s, 0) for s in columns}

        all_counts = _count_columns(file_path, drawing)
        result.counts = {s: all_counts.get(s, 0) for s in columns}
        result.pass_counts = all(
            within_tolerance(result.counts[s], result.expected_counts[s])
            for s in columns
        ) if columns else None

        # 규격 — 배치가 있는(count>0) 기둥 부호만 비교
        expected_specs = _expected_column_specs(drawing, dong)
        extracted = {
            e.symbol: e.spec_normalized
            for e in extract_specs(file_path, drawing)
            if e.symbol in columns
        }
        present = [s for s in columns if result.counts.get(s, 0) > 0]
        if present:
            result.specs = {s: extracted.get(s, "") for s in present}
            result.expected_specs = {s: expected_specs.get(s, "") for s in present}
            result.pass_specs = all(
                extracted.get(s) == expected_specs.get(s) for s in present
            )

    elif match.kind == "length":
        measurement = measure_column_length(file_path)
        result.length_mm = measurement.length_mm
        result.expected_length = _drawing_column_length(drawing)
        if result.expected_length is not None:
            result.pass_length = within_length_tolerance(
                result.length_mm, result.expected_length
            )

    return result
