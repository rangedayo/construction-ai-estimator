"""라우팅 기반 도면 길이 측정 베이스라인 — 라운드 길이-1.

1단계의 `poc_v2/tests/baseline.py` 패턴을 그대로 따르되, 길이 측정으로 대체.
한 도면의 모든 소스 DXF 파일을 측정하고, 부호별로 길이를 산출한다.

CLI
    python -m poc_v2.length.baseline_length          # 도면1~5 전체
    python -m poc_v2.length.baseline_length 도면3    # 도면3만
"""
from __future__ import annotations

import os
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

# pkg root 가 sys.path 에 있어야 `from poc_v2.length import ...` 작동
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from poc_v2.length.ground_truth_length import (  # noqa: E402
    load_ground_truth_length,
)
from poc_v2.length.measure import (  # noqa: E402
    MeasurementResult,
    measure_column_length,
)
from poc_v2.length.routing import (  # noqa: E402
    load_routing,
    method_params,
    resolve_source_path,
)

_ALL_DRAWINGS = ("도면1", "도면2", "도면3", "도면4", "도면5")
_DEFAULT_TOLERANCE_REL = 0.02  # > 1000mm 일 때 ±2%
_DEFAULT_TOLERANCE_ABS = 50.0  # ≤ 1000mm 일 때 ±50mm


@dataclass
class SymbolMeasurement:
    """한 도면의 한 부호에 대한 최종 측정 결과."""
    symbol: str
    length_mm: Optional[float]
    sources: list[str]  # 사용된 소스 파일(상대 경로) 목록
    per_source: list[dict]  # [{file, length_mm, confidence, notes}, ...]
    confidence: str  # 'high' | 'medium' | 'low'
    notes: list[str]


@dataclass
class DrawingMeasurement:
    """한 도면 단위 측정 묶음."""
    drawing: str
    symbols: dict[str, SymbolMeasurement]
    file_results: dict[str, MeasurementResult]  # source_file → measurement
    expected: dict[str, list[float]]  # 정답 길이 (부호별 인스턴스 리스트)


def _consensus_length(values: list[float]) -> tuple[Optional[float], str, list[str]]:
    """여러 소스에서 얻은 길이값을 단일 값으로 합의.

    반환: (length, confidence, notes)
        모든 값이 일치(편차 ≤ 1mm) → (mean, 'high', [])
        편차 ≤ 2%                  → (median, 'medium', [편차 메모])
        그 외                       → (median, 'low', [편차 메모])
        빈 입력                     → (None, 'low', ['측정 불가'])
    """
    if not values:
        return None, "low", ["측정 불가 — 모든 소스에서 세로 DIMENSION 없음"]

    if len(values) == 1:
        return values[0], "high", []

    spread = max(values) - min(values)
    median = statistics.median(values)
    mean = statistics.fmean(values)

    if spread <= 1.0:
        return mean, "high", []

    rel_spread = spread / median if median > 0 else float("inf")
    note = (
        f"소스간 측정 편차 {spread:.0f}mm "
        f"(min={min(values):.0f}, max={max(values):.0f}, n={len(values)})"
    )
    if rel_spread <= 0.02:
        return median, "medium", [note]
    return median, "low", [note]


def measure_drawing(
    drawing: str,
    routing_config: dict | None = None,
) -> DrawingMeasurement:
    """한 도면을 라우팅에 따라 측정해 부호별 길이를 산출."""
    config = routing_config or load_routing()

    if drawing not in config["drawings"]:
        raise ValueError(
            f"length_routing.yaml 에 {drawing!r} 정의 없음 "
            f"(가능: {list(config['drawings'].keys())})"
        )

    sources = config["drawings"][drawing]["sources"]

    file_results: dict[str, MeasurementResult] = {}
    symbol_readings: dict[str, list[dict]] = defaultdict(list)

    for source in sources:
        rel_path = source["file"]
        abs_path = resolve_source_path(rel_path)
        params = method_params(config, source["method"])

        result = measure_column_length(
            abs_path,
            method=source["method"],
            min_measurement=float(params.get("min_measurement", 100.0)),
            direction_ratio=float(params.get("direction_ratio_threshold", 5.0)),
        )
        file_results[rel_path] = result

        for symbol in source["applies_to"]:
            symbol_readings[symbol].append({
                "file": rel_path,
                "length_mm": result.length_mm,
                "confidence": result.confidence,
                "notes": list(result.notes),
            })

    symbols: dict[str, SymbolMeasurement] = {}
    for symbol, readings in symbol_readings.items():
        valid_lengths = [r["length_mm"] for r in readings if r["length_mm"] is not None]
        length, consensus_conf, notes = _consensus_length(valid_lengths)
        worst = _worst_confidence(
            [r["confidence"] for r in readings if r["length_mm"] is not None]
            + [consensus_conf]
        )
        used_files = [r["file"] for r in readings if r["length_mm"] is not None]
        symbols[symbol] = SymbolMeasurement(
            symbol=symbol,
            length_mm=length,
            sources=used_files,
            per_source=readings,
            confidence=worst,
            notes=notes,
        )

    expected = _expected_for_drawing(drawing)
    return DrawingMeasurement(
        drawing=drawing,
        symbols=symbols,
        file_results=file_results,
        expected=expected,
    )


def _worst_confidence(values: list[str]) -> str:
    """high > medium > low — 가장 보수적인 값을 반환. 입력 비면 'low'."""
    if not values:
        return "low"
    rank = {"high": 2, "medium": 1, "low": 0}
    return min(values, key=lambda v: rank.get(v, 0))


def _expected_for_drawing(drawing: str) -> dict[str, list[float]]:
    """정답지에서 도면 단위 부호→길이 리스트로 평탄화."""
    gt = load_ground_truth_length(drawings=[drawing]).get(drawing, {})
    flat: dict[str, list[float]] = defaultdict(list)
    for _source, syms in gt.items():
        for sym, lens in syms.items():
            flat[sym].extend(lens)
    return dict(flat)


def length_tolerance(expected: float) -> float:
    """길이 허용 오차 — ≤ 1000mm: ±50mm, > 1000mm: ±2%."""
    if expected <= 1000:
        return _DEFAULT_TOLERANCE_ABS
    return expected * _DEFAULT_TOLERANCE_REL


def within_length_tolerance(predicted: Optional[float], expected: float) -> bool:
    """길이 허용 오차 안에 있는지 — None 은 무조건 실패."""
    if predicted is None:
        return False
    return abs(predicted - expected) <= length_tolerance(expected)


def predict(drawing: str) -> dict[str, Optional[float]]:
    """회귀 테스트가 호출하는 단순 진입점 — {부호: 길이(mm)}."""
    measurement = measure_drawing(drawing)
    return {sym: m.length_mm for sym, m in measurement.symbols.items()}


def _fmt_len(value: Optional[float]) -> str:
    return f"{value:.0f}" if value is not None else "-"


def _print_drawing_table(measurement: DrawingMeasurement) -> None:
    """[부호] [예측] [정답] [차이] [허용] [상태] [신뢰도] [소스수] 표 출력."""
    drawing = measurement.drawing
    expected = measurement.expected
    print(
        f"{'부호':<8}{'예측(mm)':>10}{'정답(mm)':>10}{'차이':>8}"
        f"{'허용':>8}   상태   신뢰도   소스수"
    )
    print("-" * 72)

    all_symbols = sorted(set(expected.keys()) | set(measurement.symbols.keys()))
    for symbol in all_symbols:
        sym_meas = measurement.symbols.get(symbol)
        predicted = sym_meas.length_mm if sym_meas else None
        conf = sym_meas.confidence if sym_meas else "-"
        n_sources = len(sym_meas.sources) if sym_meas else 0

        exp_list = expected.get(symbol, [])
        if not exp_list:
            print(
                f"{symbol:<8}{_fmt_len(predicted):>10}{'-':>10}{'-':>8}"
                f"{'-':>8}   ----   {conf:<8} {n_sources}"
            )
            continue

        exp_value = exp_list[0]
        diff = (predicted - exp_value) if predicted is not None else None
        tol = length_tolerance(exp_value)
        ok = within_length_tolerance(predicted, exp_value)
        diff_str = f"{diff:+.0f}" if diff is not None else "-"
        print(
            f"{symbol:<8}{_fmt_len(predicted):>10}{exp_value:>10.0f}"
            f"{diff_str:>8}{tol:>8.0f}   "
            f"{'PASS' if ok else 'FAIL':<6} {conf:<8} {n_sources}"
        )
    print()
    print(f"[측정 파일 단위 결과 — {drawing}]")
    for rel_path, result in measurement.file_results.items():
        print(
            f"  {rel_path}  →  "
            f"length={_fmt_len(result.length_mm)}, conf={result.confidence}, "
            f"|V|={len(result.all_vertical_dims)}, "
            f"|H|={len(result.all_horizontal_dims)}"
        )
        for note in result.notes:
            print(f"      · {note}")


def _measure_print(drawing: str, routing_config: dict) -> bool:
    """한 도면 측정·표 출력. 도면 단위 전체 PASS 여부 반환."""
    print("=" * 72)
    print(f" 길이 베이스라인 — {drawing}")
    print("=" * 72)

    measurement = measure_drawing(drawing, routing_config)
    _print_drawing_table(measurement)

    expected = measurement.expected
    all_ok = True
    for symbol, exp_list in expected.items():
        if not exp_list:
            continue
        sym_meas = measurement.symbols.get(symbol)
        pred = sym_meas.length_mm if sym_meas else None
        if not within_length_tolerance(pred, exp_list[0]):
            all_ok = False
            break
    return all_ok


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    config = load_routing()

    targets = args if args else list(_ALL_DRAWINGS)
    overall_ok = True
    for drawing in targets:
        if drawing not in config["drawings"]:
            print(
                f"[오류] 알 수 없는 도면: {drawing} "
                f"(사용 가능: {list(config['drawings'].keys())})"
            )
            sys.exit(1)
        ok = _measure_print(drawing, config)
        overall_ok = overall_ok and ok
    print("=" * 72)
    print(f"전체 결과: {'PASS' if overall_ok else 'FAIL'}")


if __name__ == "__main__":
    main()
