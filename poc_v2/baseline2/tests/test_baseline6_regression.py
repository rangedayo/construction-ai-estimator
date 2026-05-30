"""회귀 테스트 — 라운드 베이스라인-6 (도면1 작은 도면, PoC 한 사이클 완성).

이번 라운드의 핵심 발견·수정
    (1) 동 라벨 분리: 표제부에 (1동)/(2동) 라벨이 없어(기둥주심도만 표기)
        partial 매칭이 엉뚱한 동을 잡았다. 파일명에서 동을 추출해 match_sheet 에
        dong= 으로 넘겨 시트·length 라벨 후보를 동별로 좁혔다.
    (2) 이중차감 교정: 도면1 부호도/주심도는 raw 카운트가 이미 정답인데(범례
        부호가 배치로 카운트되지 않음) 일람표 차감이 무조건 빼서 -1 FAIL 했다.
        차감을 "페어 부호 좌표가 카운트된 배치 좌표와 겹칠 때만"으로 정밀화
        (도면3·4·5 는 겹침 dist=0.0 이라 차감 동작 불변).
    (3) 길이 라우팅: 2동 골구도는 count 행에 보 부호(VG1·SG1)만 있고 기둥은 0.
        기둥 스코프에선 placeholder 로 보고 length 라벨이 우선하도록 보완해
        6000mm 측정이 발화한다(column_symbols 파라미터, 기본 None=기존 동작).

검증 항목 (명세 작업 7)
    1. 표제부 도면명 추출: 18개 파일 전부 성공
    2. 동 라벨 매칭: 1동/2동 정확 분리
    3. 카운트 PASS: 모든 매칭 시트 정답 일치 (이중차감 없음)
    4. 길이 PASS: 2동 골구도 6000, 길이 라우팅 발화
    5. 길이 N/A: 1동 시트는 length 로 라우팅되지 않음(전부 count)
    6. 규격 PASS: 1동 MC1 ≠ 2동 MC1 (동별 규격 분리 보존)
    7. 회귀 무영향: 도면3·4·5 작은 도면 동작 유지
    8. 한계: 분리본 Y03열골구도 unmatched (통합 Y03,Y05 라벨에 부분일치 안 됨)

모든 비교는 결정론적(순수 ezdxf + 룰 + openpyxl, LLM 0건).
실행:  프로젝트 루트에서  `pytest -v poc_v2/baseline2/tests/test_baseline6_regression.py`
"""
from __future__ import annotations

import functools
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
for _path in (
    PROJECT_ROOT,
    os.path.join(PROJECT_ROOT, "poc_v2"),
    os.path.join(PROJECT_ROOT, "poc_v2", "tests"),
):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from poc_v2.baseline2.sheet_title_extractor import extract_sheet_titles  # noqa: E402
from poc_v2.baseline2.small_drawing_pipeline import (  # noqa: E402
    process_small_drawing,
)

_SAMPLE = os.path.join(PROJECT_ROOT, "sample_data")

# 도면1 작은 도면 18개 (통합본 16 + 분리본 Y03·Y05).
_FILES = [
    "도면1-1동_1~3층기둥부호도.dxf",
    "도면1-1동_1~3층기둥주심도.dxf",
    "도면1-1동_2층바닥보복도.dxf",
    "도면1-1동_3층바닥보복도.dxf",
    "도면1-1동_기초구조도.dxf",
    "도면1-1동_옥상바닥보복도.dxf",
    "도면1-1동_옥상층기둥부호도.dxf",
    "도면1-1동_옥상층기둥주심도.dxf",
    "도면1-2동_SL+4.0M구조평면도.dxf",
    "도면1-2동_SL+4.7M구조평면도.dxf",
    "도면1-2동_Y01열골구도.dxf",
    "도면1-2동_Y03Y05열골구도.dxf",
    "도면1-2동_Y03열골구도.dxf",
    "도면1-2동_Y05열골구도.dxf",
    "도면1-2동_기둥부호도.dxf",
    "도면1-2동_기둥주심도.dxf",
    "도면1-2동_기초구조도.dxf",
    "도면1-2동_지붕구조평면도.dxf",
]


def _path(name: str) -> str:
    return os.path.join(_SAMPLE, name)


@functools.lru_cache(maxsize=None)
def _result(name: str):
    return process_small_drawing(_path(name))


# ── 1. 표제부 도면명 추출 — 18개 전부 성공 ──────────────────────────────────
@pytest.mark.parametrize("name", _FILES)
def test_title_extraction(name: str) -> None:
    titles = extract_sheet_titles(_path(name))
    assert titles, f"{name}: 표제부 도면명 추출 실패"


# ── 2. 동 라벨 매칭 — 1동/2동 정확 분리 ─────────────────────────────────────
def test_dong_label_1dong() -> None:
    r = _result("도면1-1동_1~3층기둥주심도.dxf")
    assert r.matched_sheet is not None
    assert "(1동)" in r.matched_sheet, r.matched_sheet


def test_dong_label_2dong() -> None:
    r = _result("도면1-2동_기둥주심도.dxf")
    assert r.matched_sheet == "(2동)기둥주심도", r.matched_sheet


def test_dong_no_crossover() -> None:
    """2동 파일이 (1동) 시트로, 1동 파일이 (2동) 시트로 새지 않아야 한다."""
    r1 = _result("도면1-1동_1~3층기둥부호도.dxf")
    r2 = _result("도면1-2동_기둥부호도.dxf")
    assert "(2동)" not in (r1.matched_sheet or "")
    assert "(1동)" not in (r2.matched_sheet or "")


# ── 3. 카운트 PASS — 이중차감 없음 ──────────────────────────────────────────
def test_count_1dong_main() -> None:
    """1동 부호도-1·주심도-1: MC1=12, MC2=6 (좌표 매칭으로 이중차감 없음)."""
    for name in ("도면1-1동_1~3층기둥부호도.dxf", "도면1-1동_1~3층기둥주심도.dxf"):
        r = _result(name)
        assert r.counts.get("MC1") == 12, (name, r.counts)
        assert r.counts.get("MC2") == 6, (name, r.counts)
        assert r.pass_counts is True, (name, r.counts, r.expected_counts)


def test_count_1dong_roof() -> None:
    """1동 옥상층 부호도-2·주심도-2: MC2=4."""
    for name in ("도면1-1동_옥상층기둥부호도.dxf", "도면1-1동_옥상층기둥주심도.dxf"):
        r = _result(name)
        assert r.counts.get("MC2") == 4, (name, r.counts)
        assert r.pass_counts is True


def test_count_2dong_main() -> None:
    """2동 부호도·주심도: MC1=15, MC2=4, MC3=2, SC1=4 (이중차감 없음)."""
    for name in ("도면1-2동_기둥부호도.dxf", "도면1-2동_기둥주심도.dxf"):
        r = _result(name)
        assert r.counts.get("MC1") == 15, (name, r.counts)
        assert r.counts.get("MC2") == 4, (name, r.counts)
        assert r.counts.get("MC3") == 2, (name, r.counts)
        assert r.counts.get("SC1") == 4, (name, r.counts)
        assert r.pass_counts is True, (name, r.counts, r.expected_counts)


def test_count_plan_with_member() -> None:
    """평면도에 부재 있는 케이스 — (2동)SL+4.0M구조평면도 MC3=2 (정답지 기준)."""
    r = _result("도면1-2동_SL+4.0M구조평면도.dxf")
    assert r.counts.get("MC3") == 2, r.counts
    assert r.pass_counts is True


@pytest.mark.parametrize(
    "name",
    [
        "도면1-1동_2층바닥보복도.dxf",
        "도면1-1동_3층바닥보복도.dxf",
        "도면1-1동_기초구조도.dxf",
        "도면1-1동_옥상바닥보복도.dxf",
        "도면1-2동_SL+4.7M구조평면도.dxf",
        "도면1-2동_기초구조도.dxf",
        "도면1-2동_지붕구조평면도.dxf",
    ],
)
def test_count_zero_sheets(name: str) -> None:
    """기둥 0 시트는 카운트 0 + PASS (이중카운트/오검출 없음)."""
    r = _result(name)
    assert r.kind == "count"
    assert all(v == 0 for v in r.counts.values()), (name, r.counts)
    assert r.pass_counts is True


# ── 4. 길이 PASS — 2동 골구도 6000, 라우팅 발화 ─────────────────────────────
@pytest.mark.parametrize(
    "name",
    [
        "도면1-2동_Y01열골구도.dxf",
        "도면1-2동_Y03Y05열골구도.dxf",
        "도면1-2동_Y05열골구도.dxf",
    ],
)
def test_length_2dong_rafter(name: str) -> None:
    r = _result(name)
    assert r.kind == "length", f"{name}: kind={r.kind} (length 기대)"
    assert r.length_mm == pytest.approx(6000.0, abs=1.0), (name, r.length_mm)
    assert r.pass_length is True


# ── 5. 길이 N/A — 1동 시트는 length 로 라우팅되지 않음 ──────────────────────
@pytest.mark.parametrize(
    "name", [f for f in _FILES if "1동" in f]
)
def test_1dong_never_length(name: str) -> None:
    r = _result(name)
    assert r.kind != "length", f"{name}: 1동인데 length 라우팅됨"


# ── 6. 규격 PASS — 동별 분리 (1동 MC1 ≠ 2동 MC1) ────────────────────────────
def test_spec_dong_separation() -> None:
    r1 = _result("도면1-1동_1~3층기둥부호도.dxf")
    r2 = _result("도면1-2동_기둥부호도.dxf")
    assert r1.specs.get("MC1") == "H-588x300x12x20", r1.specs
    assert r2.specs.get("MC1") == "H-400x200x8x13", r2.specs
    assert r1.specs["MC1"] != r2.specs["MC1"]
    assert r1.pass_specs is True
    assert r2.pass_specs is True


# ── 7. 회귀 무영향 — 도면3·4·5 ──────────────────────────────────────────────
def test_drawing4_unaffected() -> None:
    r = process_small_drawing(os.path.join(_SAMPLE, "도면4_1층구조평면도.dxf"))
    assert r.counts == {"SC1": 14, "SC2": 4}, r.counts


def test_drawing5_length_unaffected() -> None:
    r = process_small_drawing(os.path.join(_SAMPLE, "도면5_주단면도1.dxf"))
    assert r.kind == "length"
    assert r.length_mm == pytest.approx(10500.0, abs=1.0)


def test_drawing3_count_unaffected() -> None:
    r = process_small_drawing(os.path.join(_SAMPLE, "도면3_1층바닥구조평면도.dxf"))
    assert r.counts == {"C1": 8, "C2": 15, "C3": 8, "C4": 1}, r.counts


# ── 8. (구) 한계 — 분리본 Y03열골구도, 베이스라인-7 에서 해결 ─────────────────
def test_y03_standalone_resolved_in_baseline7() -> None:
    """베이스라인-6 까지는 통합 라벨 "(2동)Y03,Y05열골구도" 에 "Y03열골구도"
    단독본이 부분일치 안 돼 unmatched 였다(Y03·Y05 사이 다른 토큰). 베이스라인-7
    의 component 매칭(메커니즘 B — 영숫자 열 식별자 suffix 공유 전개)이 이 한계를
    해결: "(2동)Y03,Y05열골구도" → "(2동)Y03열골구도" 전개 후 partial 매칭 →
    length 6000 PASS. 자세한 검증은 test_baseline7_regression.py 참조."""
    r = _result("도면1-2동_Y03열골구도.dxf")
    assert r.match_confidence == "component", r.match_confidence
    assert r.kind == "length"
    assert r.length_mm == pytest.approx(6000.0, abs=1.0), r.length_mm
    assert r.pass_length is True
