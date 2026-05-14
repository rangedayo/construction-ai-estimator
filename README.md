# construction-ai-estimator

건설 도면(DXF)에서 부재 부호를 자동으로 카운트하는 AI 기반 물량산출 PoC.

## 개요

CAD 도면 위에 박스를 그리면 지정 영역 안의 부재 부호(VG1, MT1, VT1 등)를 자동으로 집계합니다.
Plotly 인터랙티브 시각화로 각 부재의 DXF 좌표를 줌인해 검증할 수 있습니다.

## 프로젝트 구조

```
construction-ai-estimator/
├── poc_v2/
│   ├── app.py            # Streamlit 메인 앱
│   ├── counter.py        # DXF TEXT/MTEXT 부재 카운팅 로직
│   ├── coord_utils.py    # 픽셀 ↔ DXF 좌표 변환 유틸리티
│   └── requirements.txt  # Python 의존성
└── sample_data/
    └── *.dxf             # 테스트용 도면 파일
```

## 실행 방법

### 1. 환경 설정

Python 3.11 기준.

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r poc_v2/requirements.txt
```

### 2. 앱 실행

```bash
cd poc_v2
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 열림.

## 사용 방법

1. **DXF 업로드** — 좌측 상단 업로더에서 DXF 파일 선택
2. **부호 설정** — 자동 감지(영문+숫자 패턴) 또는 직접 입력 선택
3. **박스 그리기 탭** — 도면 위에 드래그로 카운트할 영역 지정 → 결과 테이블 확인
4. **인터랙티브 시각화 탭** — Plotly 도면에서 마커 위치 줌인 검증

## 의존성

| 패키지 | 용도 |
|--------|------|
| streamlit | 웹 UI |
| streamlit-drawable-canvas | 박스 그리기 캔버스 |
| ezdxf | DXF 파일 파싱 |
| matplotlib | DXF → PNG 렌더링 |
| pillow | 이미지 리사이즈 |
| plotly | 인터랙티브 도면 시각화 |
