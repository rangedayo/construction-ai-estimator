# 핸드오프 작업-1 명세서 — 환경 재현성 검증

> **작성 목적**: 새 팀원이 깃헙 클론 → `pip install` → `pytest` 한 사이클로 회귀
> 11종이 모두 PASS 되는 상태를 보장. 개발 중 누락된 의존성·하드코딩 경로·미세
> 환경 가정을 찾아 fix.
>
> **읽는 순서**: 0 → 1 → 2 → 3 → 4 → 5

---

## 0. TL;DR

| 항목 | 내용 |
|---|---|
| **목표** | 별도 폴더에 새 venv 만들고 클린 install → pytest 회귀 11종 PASS |
| **부수 목표** | requirements.txt 가 실제 의존성과 일치하는지, Python 버전 명시되어 있는지 점검 |
| **본선 영향** | 코드 자체는 무수정 원칙. 환경 설정 파일(`requirements.txt`, `pyproject.toml` 등)만 수정 |
| **산출물** | 정비된 의존성 파일 + 클린 install 검증 보고서 |
| **금지** | 회귀 깨지면 즉시 중단. 본선·yaml·테스트 코드 수정 금지 (환경 파일만) |

---

## 1. 현재 상태 baseline 기록

먼저 현재 `.venv` 에서 회귀 11종 PASS 확인:

```bash
pytest -v poc_v2/tests/test_regression.py                       # 14/16
pytest -v poc_v2/length/tests/test_length_regression.py         # 16/16
pytest -v poc_v2/length/tests/test_spec_regression.py           # 25/25
pytest -v poc_v2/baseline2/tests/test_baseline2_regression.py   # 19/19
pytest -v poc_v2/baseline2/tests/test_baseline3_regression.py   # 33/33
pytest -v poc_v2/baseline2/tests/test_baseline4_regression.py   # 19/19
pytest -v poc_v2/baseline2/tests/test_baseline5_regression.py   # 16/16
pytest -v poc_v2/baseline2/tests/test_baseline6_regression.py   # 48/48
pytest -v poc_v2/baseline2/tests/test_baseline7_regression.py   # 이전 결과
pytest -v poc_v2/qto/tests/test_weight1a_regression.py          # 13/13
pytest -v poc_v2/qto/tests/test_weight1b_regression.py          # 15/15
```

합계: 234 passed / 2 known-fail (도면2 SC1·SC2)

---

## 2. requirements.txt 점검

### 2.1 실제 사용 의존성 추출

`pip freeze` 그대로 쓰지 말 것 — 개발 중 깔린 부수 패키지·전이 의존성까지 다 들어
가서 진짜로 필요한 게 뭔지 흐려진다.

대신:
1. 코드 전체에서 `import` 문 grep → 외부 패키지 목록 추출 (ezdxf, openpyxl,
   PyYAML, pytest, plotly 등)
2. 각 패키지의 현재 설치 버전 확인 (`pip show <package>`)
3. requirements.txt 를 **직접 의존성만** 으로 재작성, 버전 핀 명시

예시 형태:
```
ezdxf==1.x.x
openpyxl==3.x.x
PyYAML==6.x.x
pytest==8.x.x
plotly==5.x.x
# 필요시 추가
```

전이 의존성(예: numpy, pandas 등 다른 패키지가 끌고 오는 것)은 명시 안 함 — 직접
의존성만 적으면 pip 가 알아서 깐다.

### 2.2 Python 버전 명시

README 또는 `pyproject.toml` (없으면 신규) 에 Python 3.11 명시.
이미 `pyproject.toml` 이 있다면 `requires-python = ">=3.11,<3.12"` 형태로 핀.

---

## 3. 클린 install 테스트

### 3.1 별도 폴더에 새 venv

기존 작업 디렉터리와 완전히 분리된 곳에서 진행:

```bash
# 임시 폴더 생성 (예시 경로)
mkdir /tmp/clean-install-test    # Linux/Mac
# 또는 Windows: mkdir C:\temp\clean-install-test

cd /tmp/clean-install-test

# 프로젝트 클론 또는 복사 (현재 working tree 그대로 가져오기)
# 옵션 A: 새 폴더에 git clone (push 된 최신 상태)
# 옵션 B: 작업 디렉터리에서 .venv 빼고 통째로 복사

# 새 venv
python3.11 -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate

# 클린 install
pip install -r requirements.txt

# 회귀 11종 실행
pytest -v poc_v2/
```

### 3.2 흔히 튀어나오는 문제

다음 케이스들을 적극적으로 잡아낼 것:

- **import error**: requirements.txt 에서 빠진 패키지
- **FileNotFoundError**: 하드코딩된 절대경로 (`C:\Users\...`, `/home/...` 등) —
  코드에 있으면 `os.path.join` + `PROJECT_ROOT` 패턴으로 정비. **단 본선
  코드 수정 금지 원칙** — 정말로 막힌 경우만 보고하고 사용자 결정 받기.
- **PYTHONPATH 의존**: `from poc_v2.xxx import ...` 가 안 되면 `pyproject.toml`
  의 패키지 설정 또는 `conftest.py` 점검
- **인코딩 이슈**: 한글 파일명 또는 UTF-8 BOM 관련. 윈도우 환경에서 자주 발생.

### 3.3 발견된 문제 fix

문제 발견 시:
1. 어떤 문제인지 정확히 진단 (어느 test가 어떤 에러로 실패)
2. **환경 파일 (requirements.txt, pyproject.toml) 만 수정해서 해결 가능한지** 먼저 시도
3. 본선 코드 수정이 필요한 경우 fix 시도 전에 사용자에게 보고

---

## 4. 재검증

수정 후:

1. 새 venv 다시 만들기 (또는 `pip uninstall -y -r requirements.txt && pip install -r requirements.txt`)
2. 회귀 11종 재실행
3. 모두 PASS 확인
4. 동시에 원래 `.venv` 에서도 회귀 PASS 유지되는지 확인 (의존성 다운그레이드 부작용 방지)

---

## 5. 보고서

**파일**: `outputs/handoff_task1_보고서.md` (신규)

내용:
- 클린 install 시도 결과 (PASS / FAIL)
- requirements.txt 변경 사항 (before / after)
- Python 버전 명시 위치
- 발견된 문제와 fix 내용
- 본선 코드 수정 필요했는지 (필요했다면 어느 부분·왜)
- 새 팀원 온보딩 시 추가로 주의할 점

---

## 6. 제약사항

### 6.1 절대 금지
- 본선 모듈 코드 수정 (사용자 결정 없이)
- yaml 파일 수정
- 테스트 파일 수정 (clean install 환경에서 실패하는 testify 결과를 가리기 위해)
- 이미 PASS 되는 회귀 깨뜨리기

### 6.2 허용
- `requirements.txt`, `pyproject.toml`, `.python-version` 등 환경 파일 신규/수정
- `conftest.py` 신규 (sys.path 설정용, 필요시)
- `outputs/handoff_task1_*` 신규

---

**문서 끝.**
