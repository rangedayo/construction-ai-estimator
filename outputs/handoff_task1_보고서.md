# 핸드오프 작업-1 보고서 — 환경 재현성 검증

> **작성일**: 2026-05-31
> **목표**: 별도 폴더 새 venv → 클린 install → 회귀 11종 PASS 보장, 의존성 파일 정비
> **원칙 준수**: 본선 코드·yaml·테스트 코드 **무수정**. 환경 파일만 신규/정비.

---

## 0. 결론 (TL;DR)

| 항목 | 결과 |
|---|---|
| **클린 install** | ✅ PASS (exit 0, 직접 의존성 9종 핀 버전 설치 성공) |
| **클린 venv 회귀** | ✅ **234 passed / 2 known-fail** — 원본 `.venv` baseline과 **완전 동일** |
| **본선 코드 수정** | ❌ 없음 (불필요) |
| **하드코딩 절대경로** | ❌ 0건 (모든 경로 `__file__` 기반 상대경로) |
| **🔴 온보딩 블로커** | **테스트 데이터(`sample_data/`·`reference_materials/`)가 `.gitignore` 대상** → 순수 `git clone` 만으로는 회귀 불가. **사용자 결정 필요** (§5) |

---

## 1. Baseline 기록 (정비 전, 원본 `.venv`)

```
2 failed, 234 passed, 7 warnings in 178.12s
FAILED test_regression.py::test_symbol_total[도면2-SC1]
FAILED test_regression.py::test_symbol_total[도면2-SC2]
```

- **234 passed / 2 known-fail** — 핸드오프 §1 기대치와 정확히 일치.
- 2건(도면2 SC1·SC2)은 프로젝트가 수용한 기존 known-fail (블록 split-TEXT 한계). xfail 마킹은 없으나 baseline에 포함됨. **테스트 무수정 원칙상 손대지 않음.**

---

## 2. requirements.txt 정비

### 2.1 위치 결정

- **기존 파일 발견**: `poc_v2/requirements.txt` (README line 35 가 가리키는 경로). 루트에는 없었음.
- 작업 초반 루트에 신규 생성했다가 **중복 방지** 위해 삭제, 기존 `poc_v2/requirements.txt` 를 in-place 정비하는 방식으로 통일 (단일 소스).

### 2.2 직접 의존성 추출

`pip freeze` 미사용. 코드 전체 `import` 문 grep → 외부 패키지만 분류:

| 분류 | 패키지 | 사용처 |
|---|---|---|
| **코어 (회귀 필수)** | ezdxf, openpyxl, PyYAML, pytest | 측정 파이프라인 + 테스트. **회귀 11종은 이 4종만으로 충분** |
| **앱/시각화 (회귀 불필요)** | streamlit, streamlit-drawable-canvas, matplotlib, plotly, Pillow | `app.py` / `visualize_*.py` 전용. 테스트는 import 안 함 |

> 검증: matplotlib·plotly·streamlit·PIL 을 import 하는 파일은 `app.py` 및 `visualize_*.py` 5개뿐이며, 어떤 테스트 파일도 이들을 import 하지 않음.

### 2.3 Before / After

**Before** (`poc_v2/requirements.txt`, 핀 없음):
```
streamlit
streamlit-drawable-canvas
ezdxf
matplotlib
pillow
plotly
# 테스트 인프라 / 설정 파일용
openpyxl
pyyaml
pytest
```

**After** (버전 핀 + 코어/앱 그룹 분리 + 온보딩 주석):
```
# --- 앱 + 시각화 (app.py / visualize_*.py 전용) ---
streamlit==1.33.0
streamlit-drawable-canvas==0.9.3
ezdxf==1.4.3
matplotlib==3.10.9
pillow==10.4.0
plotly==6.7.0
# --- 테스트 인프라 / 설정 파일 파싱 (pytest 회귀에 필요한 코어) ---
openpyxl==3.1.5
pyyaml==6.0.3
pytest==9.0.3
```

- 전이 의존성(numpy, pandas, pyparsing 등)은 미명시 — pip 가 자동 해결.
- 핀 버전은 현재 `.venv` 실측 설치 버전. (참고: 핸드오프 예시는 pytest 8.x 였으나 실제 설치는 **9.0.3**.)

### 2.4 Python 버전 명시

| 위치 | 내용 |
|---|---|
| `pyproject.toml` (**신규**) | `requires-python = ">=3.11,<3.12"` (메타데이터 전용, 빌드 대상 아님) |
| `.python-version` (기존) | `3.11.9` |
| `README.md` (기존) | "Python 3.11 기준" 명시 + 올바른 install 경로 |

---

## 3. 클린 install 테스트

### 3.1 방법

핸드오프 §3.1 **옵션 B**(작업 트리 코드/데이터 재사용 + 격리된 새 venv) 채택:

```bash
mkdir C:\temp\clean-install-test
py -3.11 -m venv C:\temp\clean-install-test\.venv     # Python 3.11.9
<temp>\.venv\Scripts\python.exe -m pip install -r poc_v2/requirements.txt
<temp>\.venv\Scripts\python.exe -m pytest poc_v2/...   # repo 코드/데이터 대상
```

> 트리를 통째로 복사하는 대신, **격리된 site-packages(temp venv)** 로 repo 코드를 실행.
> 의존성 격리 검증 목적엔 동일하며, 기밀 데이터를 임시 폴더로 복제하지 않아 더 안전.

### 3.2 결과

- **install**: exit 0. 9종 모두 핀 버전 정확히 설치 (ezdxf 1.4.3, streamlit 1.33.0, pytest 9.0.3 등). 버전 충돌 없음.
- **회귀 11종**: `2 failed, 234 passed in 180.46s` — 원본 baseline과 **바이트 단위로 동일한 결과**.
- import error / FileNotFoundError / PYTHONPATH 오류 **0건**.

### 3.3 흔한 문제 점검 결과

| 점검 항목 | 결과 |
|---|---|
| import error (빠진 패키지) | 없음 — 9종 직접 의존성 전부 커버 |
| 하드코딩 절대경로 | **0건**. `grep C:\Users\|/home/\|/Users/` 결과 없음 |
| PYTHONPATH 의존 | 안전. 각 테스트가 상단에서 `os.path.dirname(os.path.abspath(__file__))` 로 `sys.path` 자가 삽입. `conftest.py` 불필요 |
| 데이터 경로 | 안전. `ground_truth.py` 가 `PROJECT_ROOT`(=`__file__` 기반)로 `reference_materials/도면_정답지.xlsx` 해석 → cwd 독립 |
| 인코딩(한글 파일명) | 문제 없음 (Windows 3.11.9, 회귀 전부 통과) |

---

## 4. 재검증 (회귀 미손상 확인)

- 클린 venv 회귀가 **pyproject.toml 신규 파일이 존재하는 상태**에서 234 passed → 환경 파일 추가가 기존 PASS 를 깨지 않음.
- pytest collection 영향 확인: `--collect-only` 결과 31 tests 수집(변화 없음), `rootdir` 동일(repo root). pyproject 는 `configfile` 로 인식되나 `[tool.pytest.ini_options]` 가 없어 수집/경로 동작 불변.
- 핀 버전 = 원본 `.venv` 실측 버전이므로 원본 환경도 동일하게 동작.

---

## 5. 🔴 발견된 온보딩 블로커 — 사용자 결정 필요

### 문제

`.gitignore` 에 다음이 등록되어 있어 **git 추적에서 제외**됨:
```
sample_data/            # 회귀가 읽는 입력 DXF 전체
reference_materials/    # 정답지 도면_정답지.xlsx / 도면_길이_정답지.xlsx
```

회귀 테스트는 이 둘을 **반드시** 읽는다(`ground_truth.py` → `reference_materials/...xlsx`, 파이프라인 → `sample_data/*.dxf`).
따라서 **새 팀원이 순수 `git clone` 후 `pip install` → `pytest` 하면 `FileNotFoundError` 로 회귀가 전부 깨진다.** 핸드오프의 전제("클론 한 사이클로 PASS")가 데이터 부재로 성립하지 않음.

### 왜 자동 fix 하지 않았는가

- 두 폴더는 README 상 **"기밀(confidential)"** 로 의도적으로 gitignore 된 것 — 단순 누락이 아님.
- 기밀 데이터를 git 추적에 올리는 것은 보안 영향이 크고, push 시 외부 노출 위험. **사용자 결정 사항**(핸드오프 §3.3·§6.1).

### 권장 선택지 (택1)

1. **별도 비공개 데이터 채널** — 데이터를 git 밖(사내 스토리지/Git LFS 비공개)으로 배포하고, README 에 "클론 후 `sample_data/`·`reference_materials/` 를 X 위치에서 받아 루트에 배치" 온보딩 절차 추가. (기밀 유지 + 재현성 확보, 권장)
2. **익명화 픽스처 커밋** — 회귀에 필요한 최소 DXF·정답지를 익명화/축약해 `tests/fixtures/` 로 커밋. (클론만으로 PASS 가능하나 픽스처 제작 공수 필요)
3. **현행 유지 + 문서화** — gitignore 그대로 두고, README 에 "회귀 실행엔 별도 데이터 필요" 명시만. (가장 보수적)

> 본 작업은 환경 파일 범위라 위 결정은 보류. 결정 시 README 온보딩 절차에 반영 가능.

---

## 6. 변경 파일 요약

| 파일 | 작업 | 비고 |
|---|---|---|
| `poc_v2/requirements.txt` | 정비 | 버전 핀 + 코어/앱 그룹 분리 + 온보딩 주석 |
| `pyproject.toml` | 신규 | `requires-python = ">=3.11,<3.12"` 메타데이터 |
| `outputs/handoff_task1_보고서.md` | 신규 | 본 보고서 |
| 본선/yaml/테스트 코드 | **무수정** | 원칙 준수 |

---

## 7. 새 팀원 온보딩 추가 주의점

1. **Python 3.11 필수** (`<3.12`). 3.12+ 에서는 핀된 streamlit 1.33.0 등 호환성 미검증.
2. **install 경로**: `pip install -r poc_v2/requirements.txt` (루트 아님, `poc_v2/` 하위).
3. **테스트 데이터**: §5 미해결 시 클론만으로 회귀 불가 — 데이터 수급 절차 확인 필수.
4. **앱만 쓸 거면** 코어 4종은 불필요하나, requirements 는 단일 파일이라 전체 설치됨(무해).
5. **known-fail 2건**(도면2 SC1·SC2)은 정상 — 실패가 아니라 수용된 한계.

---

**문서 끝.**
