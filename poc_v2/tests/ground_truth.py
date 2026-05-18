"""도면 정답지(xlsx) 로더 — 회귀 테스트용 결정론적 정답 데이터.

라운드 2 방침: 페이지 분할 폐기. 정답지를 페이지 단위로 분해하지 않고
'도면 전체에서 부호별 합계'만 로드한다.

정답지(`reference_materials/도면 정답지.xlsx`)는 시트마다 매트릭스 형태:
    행 = 도면 페이지,  열 = 부재 부호,  셀 = 해당 페이지의 부호 개수

셀 값 해석 규칙:
    빈 셀(None)  → 그 페이지에 그 부호 없음
    0            → 부호는 등장하나 개수 0개
    '합계' 행/열  → 집계용이므로 제외 (페이지 셀을 직접 합산한다)

LLM 호출 등 비결정 요소 없이 순수하게 xlsx만 파싱한다.
"""
from __future__ import annotations

import os

import openpyxl

# tests/ground_truth.py → poc_v2/tests → poc_v2 → 프로젝트 루트
_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
ANSWER_KEY_PATH = os.path.join(
    PROJECT_ROOT, "reference_materials", "도면 정답지.xlsx"
)
SYMBOL_RULES_PATH = os.path.join(
    PROJECT_ROOT, "config", "symbol_rules.yaml"
)

_TOTAL_LABEL = "합계"


def load_text_height_filter(
    path: str | None = None,
) -> dict[str, float | None]:
    """symbol_rules.yaml 의 text_height_filter → {도면명: min_height}.

    min_height 가 null(YAML) 이면 None 으로, 숫자면 그대로 돌려준다.
    설정 파일이나 pyyaml 이 없으면 빈 dict (= 모든 도면 필터 미적용).
    """
    try:
        import yaml  # noqa: PLC0415
    except ImportError:
        return {}
    cfg_path = path or SYMBOL_RULES_PATH
    if not os.path.exists(cfg_path):
        return {}
    with open(cfg_path, encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    raw = config.get("text_height_filter", {}) or {}
    return {
        drawing: (spec or {}).get("min_height")
        for drawing, spec in raw.items()
    }


def drawing_symbol_totals(
    path: str | None = None,
) -> dict[str, dict[str, int]]:
    """{도면명: {부호: 도면 전체 합계}} 형태로 정답지를 파싱해 반환한다.

    정답지의 '합계' 행을 신뢰하지 않고 페이지 셀에서 직접 합산한다
    (합계 행은 수기 입력이라 오차가 있을 수 있음). 빈 셀은 0으로 보고
    한 번이라도 등장한 부호만 결과에 포함한다.
    """
    workbook = openpyxl.load_workbook(path or ANSWER_KEY_PATH, data_only=True)
    totals: dict[str, dict[str, int]] = {}

    for sheet_name in workbook.sheetnames:
        worksheet = workbook[sheet_name]
        rows = list(worksheet.iter_rows(values_only=True))
        if not rows:
            continue

        header = rows[0]
        # (열 인덱스, 부호명) — 0번 열(도면명)과 '합계' 열은 제외
        symbol_columns: list[tuple[int, str]] = []
        for col_idx, raw_name in enumerate(header[1:], start=1):
            if raw_name is None:
                continue
            label = str(raw_name).strip()
            if not label or label == _TOTAL_LABEL:
                continue
            symbol_columns.append((col_idx, label))

        aggregated: dict[str, int] = {}
        for row in rows[1:]:
            raw_page = row[0]
            if raw_page is None:
                continue
            page_name = str(raw_page).strip()
            if not page_name or page_name == _TOTAL_LABEL:
                continue
            for col_idx, symbol in symbol_columns:
                value = row[col_idx] if col_idx < len(row) else None
                if value is None or value == "":
                    continue
                aggregated[symbol] = aggregated.get(symbol, 0) + int(value)

        totals[sheet_name] = aggregated

    return totals


def within_tolerance(
    predicted: int,
    expected: int,
    rel_tol: float = 0.05,
    small_count: int = 5,
) -> bool:
    """예측 개수가 정답 허용 오차 안에 있는지 판정.

    expected 가 small_count(기본 5) 이하면 ±1 까지 허용한다(작은 수에서
    5%는 너무 빡빡함). 그 외에는 상대오차 rel_tol(기본 5%) 이하면 통과.
    """
    diff = abs(predicted - expected)
    if expected <= small_count:
        return diff <= 1
    return diff <= expected * rel_tol
