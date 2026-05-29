# 라운드 베이스라인-1 보고서 — 단위중량 통일 함수

> **목표**: 단위중량 = 단면적 × 밀도(7,850 kg/㎥) 한 식으로 통일한 신규 모듈.
> 본선·보류 코드 무수정, 신규 패키지 `poc_v2/qto/` 로 분리.

---

## 1. 신설 파일 + 함수 시그니처

| 경로 | 종류 | 역할 |
|---|---|---|
| [poc_v2/qto/__init__.py](../poc_v2/qto/__init__.py) | 패키지 | qto(수량/중량) 패키지 마커 |
| [poc_v2/qto/unit_weight_calc.py](../poc_v2/qto/unit_weight_calc.py) | 코드 | 단위중량 계산 (룩업·분기 없음) |
| [poc_v2/qto/tests/__init__.py](../poc_v2/qto/tests/__init__.py) | 패키지 | 테스트 패키지 마커 |
| [poc_v2/qto/tests/test_unit_weight_calc.py](../poc_v2/qto/tests/test_unit_weight_calc.py) | 테스트 | 단위·18종·KS sanity·비표준·엣지 |

함수 시그니처:

- `parse_h_section(spec) -> (H, B, tw, tf)` — `normalize_spec` 재사용 후 4세그먼트 파싱. H형강 외/세그먼트 수 불일치 시 `ValueError`.
- `section_area_mm2(H, B, tw, tf) -> float` — `B×tf×2 + tw×(H−tf×2)`.
- `unit_weight_kg_per_m(spec, density=7850.0) -> float` — 정규화·파싱·계산 일괄.
- `compute_section(spec) -> dict` — H·B·tw·tf·area·weight 한 번에 반환.

정규화는 기존 `normalize_spec`(원본: `poc_v2/length/ground_truth_spec.py`, `spec_extractor` 가 re-export)을 재사용. ezdxf 의존을 끌어오지 않도록 원본 모듈에서 직접 import.

---

## 2. 단위 테스트 — H-588x300x12x20 수동 검산

```
A = 300×20×2 + 12×(588−40) = 12,000 + 6,576 = 18,576 mm²
W = 18,576 × 1e-6 × 7,850 = 145.82 kg/m
```

테스트 `test_unit_case_588_manual_calc` 가 area 18,576.0(±0.01), weight 145.82(±0.01) 정확 일치 확인. **PASS**.

---

## 3. 18종 비교 표 — 계산 vs KS표(임시값)

(정규화 dedupe 후 15 distinct. `pytest -s` 콘솔 출력 동일.)

| 규격(normalized) | 계산 A(mm²) | 계산 W | KS표 | 차이% | 판정 |
|---|---:|---:|---:|---:|---|
| H-588x300x12x20 | 18,576 | 145.8 | 151.0 | −3.4 | OK |
| H-200x200x8x12 | 6,208 | 48.7 | 49.9 | −2.3 | OK |
| H-400x200x8x13 | 8,192 | 64.3 | 65.4 | −1.7 | OK |
| H-440x300x11x18 | 15,244 | 119.7 | 124.0 | −3.5 | OK |
| H-250x250x9x14 | 8,998 | 70.6 | 71.8 | −1.6 | OK |
| H-300x150x6.5x9 | 4,533 | 35.6 | 36.7 | −3.1 | OK |
| H-250x125x6.0x9.0 | 3,642 | 28.6 | 29.6 | −3.4 | OK |
| H-200x100x5.5x8.0 | 2,612 | 20.5 | 21.3 | −3.8 | OK |
| H-600x407x20x35 | 39,090 | 306.9 | 175.0 | +75.3 | 비표준·제외 |
| H-428x407x20x35 | 35,650 | 279.9 | 140.0 | +99.9 | **±5% 초과 — yaml 임시값 오기** |
| H-400x400x13x21 | 21,454 | 168.4 | 172.0 | −2.1 | OK |
| H-300x300x10x15 | 11,700 | 91.8 | 94.0 | −2.3 | OK |
| H-350x175x7x11 | 6,146 | 48.2 | 49.6 | −2.7 | OK |
| H-194x150x6x9 | 3,756 | 29.5 | 30.6 | −3.7 | OK |
| H-450x200x9x14 | 9,398 | 73.8 | 66.2 | +11.4 | **±5% 초과 — yaml 임시값 오기** |

**판정**: 표준 단면 12종은 모두 −3.8 ~ −1.6%(필렛 무시분)로 ±5% 이내. ±5% 초과 2종(428x407, 450x200)은 **계산식이 아니라 yaml 임시값이 실제 KS와 다른 항목**이다 (실제 KS ≈ 283, 76 kg/m → 계산값 279.9, 73.8 이 오히려 정답에 근접). 사용자 결정에 따라 KS 비교는 **경고만**(assert 없음) 하므로 테스트는 통과한다. 멘토 yaml 교체 시 자동 해소.

---

## 4. 비표준 단면 산출 — KS표 없는 항목

- `H-600x407x20x35`(도면3 C1, 현장제작): A = 407×35×2 + 20×(600−70) = **39,090 mm²** → **306.9 kg/m**. 분기 없이 같은 식으로 정상 산출(`test_nonstandard_section_computes` PASS).

---

## 5. 회귀 무영향 확인 (pytest 4종)

| 대상 | 결과 | 비고 |
|---|---|---|
| `poc_v2/tests/test_regression.py` | 14 passed, 2 failed | 도면2 SC1·SC2 — **기존 FAIL**, 본 라운드 무관 (14/16 유지) |
| `poc_v2/length/tests/test_length_regression.py` | 16 passed | 16/16 |
| `poc_v2/length/tests/test_spec_regression.py` | 25 passed | 변동 없음 |
| `poc_v2/qto/tests/test_unit_weight_calc.py` | **29 passed** | 신규, 전부 PASS |

신규 모듈 추가만 — 본선/보류 코드 0 수정. 기존 회귀 상태 그대로 유지.

---

## 6. 알려진 한계

- **H형강 외 단면 미지원**: 파이프(□)·앵글(L)·원형철근(ø)·박스 등은 `ValueError`. 본 라운드 범위 외(명세 §2.4).
- **필렛 무시**: 모서리 곡률 미반영으로 KS 표값 대비 약 −2~4% 작게 산출. 멘토 확인상 무시 수준.
- **4세그먼트 비-H 오분류 가능성**: 정규화 후 첫 세그먼트에 기호(□/L/ø)가 남으면 float 변환에서 걸러지나, 순수 숫자 4세그먼트 박스형강 등은 H형강으로 가정(명세 §2.4 동일 정책).
- **KS 임시값**: `config/unit_weight_table.yaml` 은 임시값 — 428x407·450x200·600x407 항목이 실제 KS와 상이. 멘토 검토 후 교체 필요(코드 무수정).
