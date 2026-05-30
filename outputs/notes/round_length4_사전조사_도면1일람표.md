# 라운드 길이-4 사전조사 — 도면1 일람표 검출 실패 원인 진단

## 0. 요약 (TL;DR)

- **결론: 가설 H1 + H3 복합 원인. H2 는 기각.**
- 도면1 일람표 텍스트 height = **176.4** 인데 yaml `min_height = 177` → height 필터에서 부호·H-규격이 **전부 컷**.
- 가령 height 필터를 통과시켜도 도면1 일람표는 등록 부호가 **MC1·MC2 단 2종** → `detect_table_regions` 임계 `min_distinct_symbols=4` 미달 → 어차피 검출 불가.
- → 다른 도면(3·4·5)처럼 "부호 N종이 한 표에 모인 큰 일람표"가 아니라, **기둥주심도 표제부에 붙은 2종짜리 mini-표**라는 구조적 차이.

진단 산출물:
- 스크립트: [outputs/diagnose/round_length4_도면1_table.py](diagnose/round_length4_도면1_table.py)
- 원본 출력: [outputs/diagnose/round_length4_도면1_table.txt](diagnose/round_length4_도면1_table.txt)
- 본선 코드(counter.py / baseline.py / yaml) 무수정. 회귀 1단계 14/16 그대로.

---

## 1. 진단 대상·범위

| 항목 | 값 |
|---|---|
| DXF | `sample_data/도면1.dxf` |
| extent | x = 48,110.0 ~ 409,302.6 / y = 1,074,728.3 ~ 1,210,809.2 |
| 진단 bbox(좌하 30%×40%) | x = 48,110.0 ~ 156,467.8 / y = 1,074,728.3 ~ 1,129,160.7 |
| 회귀 화이트리스트 | 19종 (MC1·MC2·MC3·MT1·RSB1~3·RSG1~3·SB1~3·SC1·SG1~3·VG1·VT1) |
| min_text_height(yaml) | **177** |
| table_region_detection(yaml) | region_size_ratio = 0.033, min_distinct_symbols = **4**, max_count_per_symbol = **2** |
| bbox 내 텍스트 엔티티 총수 | 138건 (전부 modelspace TEXT) |

---

## 2. 일람표 영역에서 실제로 발견된 텍스트

### 2.1 일람표 본체 (좌하 bbox, height ≈ 176.4)

| # | source | height | match | text |
|---|---|---:|---|---|
| 16 | TEXT | 176.4 | – | `크 기` |
| 17 | TEXT | **176.4** | – | `H- 588x300x12/20` |
| 18 | TEXT | **176.4** | – | `H- 200x200x8/12` |
| 19 | TEXT | 176.4 | – | `기 둥` |
| 20 | TEXT | 176.4 | – | `구 분` |
| 21 | TEXT | **176.4** | **MC1** | `MC1` |
| 22 | TEXT | 176.4 | – | `부 호` |
| 23 | TEXT | **176.4** | **MC2** | `MC2` |
| 24 | TEXT | 176.4 | – | `SM355` |
| 25 | TEXT | 176.4 | – | `비 고` |
| 26 | TEXT | 176.4 | – | `SM275` |

(인덱스 49~59 에 동일 표가 한 벌 더 등장 — 도면1 은 1동·옥상층 두 도면 표제부가 좌하 영역에 같이 그려져 있음. 즉 일람표가 두 개 있다.)

### 2.2 본체(modelspace) MC1·MC2 (height ≈ 197.5)

bbox 안에 본체 MC1·MC2 가 다수 등장 (#28~31, #60~78 등 24건). height **197.5** 로 일람표 부호 텍스트(176.4)보다 **약 21 큼**.

### 2.3 NOTE 텍스트 (height 175.0)

`* MC1 외부 판넬 접한 부위에는 …` 같은 안내문이 같은 영역에 있음 (#80~88). MC1 이 텍스트 안에 포함돼 있지만 `match_symbol` 은 정확 일치/안전한 prefix 만 보므로 매칭되지 않음 (`match` = `-`).

### 2.4 표제부 (도면번호·승인·SCALE 등, height 152~205)

bbox 의 나머지(약 100건)는 표제부·회사 정보. 화이트리스트 매칭 0건.

### 2.5 좌하 bbox 안 화이트리스트 매칭 결과

```
TEXT (modelspace) : 26건
  MC1 : 14
  MC2 : 12
INSERT_ATTRIB     : 0건
INSERT_BLOCKDEF   : 0건
```

매칭 부호는 **MC1·MC2 두 종**. 그중 height 176.4(일람표용)는 4건(MC1×2 + MC2×2 — 일람표 두 벌이므로), 나머지 22건은 height 197.5 본체.

---

## 3. 가설 검증

### H1 (height 필터에서 컷) — **확정**

좌하 bbox 의 height 히스토그램 vs `min_height = 177`:

| height | 건수 | 판정 |
|---:|---:|---|
| 152 | 6 | FILTERED OUT |
| 167 | 25 | FILTERED OUT |
| 175 | 10 | FILTERED OUT |
| **176** | **22** | **FILTERED OUT** ← 일람표 헤더·부호·H-규격 전부 |
| 190 | 14 | PASS |
| 198 | 22 | PASS ← 본체 MC1·MC2 |
| 200 | 8 | PASS |
| 203 | 16 | PASS |
| 205 | 10 | PASS |
| 343 | 2 | PASS |
| 500 | 2 | PASS |
| 3000 | 1 | PASS |

→ 일람표 부호(MC1·MC2 @ **176.4**) 와 H-규격 텍스트 4건이 **min_height = 177 바로 아래**라서 정확히 컷된다. 헤더 텍스트(`크 기`·`기 둥`·`구 분`·`부 호`·`SM355`·`SM275`·`비 고`)도 모두 176.4 라 같이 컷.

> 의미: yaml 의 177 은 "큰 본체(197.5) ↔ 작은 헤더(176.4)" 갭 21 의 중간값. 이 갭이 도면1 의 본체 자동 분리를 가능하게 한 결정적 수치인데, 그 대가로 일람표는 표째로 사라진다.

### H2 (INSERT ATTRIB / 블록 내부에 묻힘) — **기각**

- 좌하 bbox 의 INSERT_ATTRIB 매칭 0건, INSERT_BLOCKDEF 매칭 0건.
- 일람표 부호(MC1/MC2)와 H-규격(H-588x300x12/20 등)은 **modelspace TEXT 엔티티로 자유롭게 그려져 있음**. 같은 셀에 묻혀 있지도 않음 (서로 다른 TEXT 엔티티, 좌표 다름).
- 도면2 처럼 "INSERT 블록 안에 텍스트가 묻힌" 패턴은 도면1 일람표에는 **재현 안 됨**.

### H3 (detect_table_regions 임계 미달) — **확정 (보조 원인, H1 통과해도 단독으로 실패)**

`baseline.compute_drawing` 과 동일 입력으로 `load_text_layout` + `detect_table_regions` 호출 결과:

```
load_text_layout(min_text_height=177, exclude_with_spec=True)
  → 자유 텍스트 19종, 좌하 bbox 안 = MC1(12) + MC2(10) 두 종
sparse 보정(_TABLE_SPARSE_MAX=5)
  → MC1(54전체)·MC2(28전체) 모두 5 초과 → 컷
  → sparse 후 bbox 안 부호 종수 = 0
detect_table_regions → 0곳
```

3중 컷:
1. height 필터(177) 가 일람표 부호 4건을 컷 → bbox 안 자유 텍스트가 **본체 카운트(MC1@197.5·MC2@197.5)만** 남음.
2. 본체 카운트는 부호당 좌표 수가 많아(MC1 54·MC2 28) baseline 의 `_TABLE_SPARSE_MAX = 5` 보정에서 제외됨 → bbox 안 부호 종수 0.
3. 가령 1단계를 우회해서 일람표 부호 4건이 살아남아도 종수 = 2 < `min_distinct_symbols = 4` → 일람표 후보 탈락.

→ **H1 을 풀어도 H3 이 단독으로 실패**. 두 원인이 직렬로 걸려 있다.

---

## 4. 길이-4 본작업 권고

### 4.1 "도면1 일람표를 region 으로 잡는다"는 시도는 권장 안 함

도면1 일람표의 구조적 특성:
- **부호 2종(MC1·MC2)만 등록**. 다른 부호(SC1·SG1 등)는 1동 부재가 아니라서 일람표에 자체적으로 없음.
- 본체 카운트와 부호 종류가 **완전히 겹침** (본체도 MC1·MC2 만).
- 도면 3·4·5 처럼 N(≥4)종 모이는 일람표가 아님. detect_table_regions 의 보편 휴리스틱("N종이 각 1~2회")이 정의상 안 걸린다.
- 임계값(min_distinct_symbols) 을 2로 낮추면 **다른 도면의 부재 밀집 영역도 일람표로 오판**될 위험 → 1단계 14/16 회귀 깨질 가능성 있음.

### 4.2 권장: 부호 ↔ 규격 매핑을 **카운팅 파이프라인과 분리해 독립 추출**

길이-4 의 본질은 "부호 → 규격(H-200x200x8/12 → 200mm) → 길이별 가중치". 이 매핑은 카운팅이 아닌 **부호별 1회 lookup 테이블** 이라 다른 데이터 경로로 가야 한다.

권장 설계 (구현은 본작업에서):

1. **신규 모듈 `poc_v2/length/spec_lookup.py` (가칭)** — counter.py / baseline.py 무관.
2. **height 필터를 적용하지 않은 별도 수집기** 로 modelspace 의 TEXT/MTEXT 전체를 훑는다.
3. 한 줄에 **부호 패턴(`^[A-Z]{1,5}\d{1,2}$`) + 같은 y(±tol) 안에 H-규격 패턴(`^H[ -]?\d+x\d+x\d+/?\d*$`)** 이 등장하는 페어를 찾는다.
   - 도면1 의 #17(`H- 588x300x12/20`, y≈1077651) + 옆 셀 부호 — 일람표 행 단위 매칭.
   - 도면 3·4·5 는 이미 region 으로 잡히므로 region 안의 부호↔규격을 그대로 사용 가능.
4. 같은 부호가 여러 표에서 다른 규격으로 나오면 **최빈값** 또는 **세부 도면별 분리**를 yaml override 로 결정 (도면1 의 두 벌짜리 표는 동일 매핑이므로 dedupe).

이렇게 가면:
- 도면1 일람표 region 자체는 검출 못 해도(어차피 카운트엔 안 쓰임) **부호↔규격 매핑은 정확히 얻어진다**.
- 1단계 카운팅 필터(min_height = 177, _TABLE_SPARSE_MAX = 5) 는 **건드릴 필요 없음** → 회귀 0.

### 4.3 만약 길이-4 가 "region 안의 부호 목록" 에 의존한다면

- 도면1 만 `policy_override` 에 region bbox 를 yaml 수동 등록하는 비상 옵션 (도면3 override 와 동형).
- 또는 "region 검출 입력에 height 필터 미적용" 모드를 detect_table_region 옵션으로 추가. 단 이 경우 sparse_max·max_count_per_symbol 도 동시 조정해야 도면1 본체와 분리 가능. **위험도 높음 — 1단계 회귀 재검증 필수.**
- 본 권고는 4.2 (독립 추출) 우선.

---

## 5. 부가 관찰 (길이-4 본작업에서 활용 가능)

- 도면1 좌하 영역에 **일람표가 두 벌** 등장 (인덱스 16~26 = 옥상층 / 49~59 = 1~3층). 두 벌의 부호·규격은 동일하므로 dedupe 가능.
- H-규격 표기에 **공백 있음**(`H- 588x300x12/20`). 정규식은 `^H[ -]*?\d+x\d+x\d+/?\d*$` 처럼 공백 허용으로 짤 것.
- 일람표 부호(MC1@176.4) 와 본체 부호(MC1@197.5) 의 **y 좌표 페어링 거리** 가 단순. 도면1 일람표는 한 행 안에 부호·재질(SM355/SM275)·H-규격·비고가 같은 y 띠 안에 정렬 — y±20 정도 tol 로 충분.
- NOTE 텍스트(`* MC1 외부 판넬…`)의 height 175.0 도 min_height 177 아래로 컷되어 매칭 0건. 길이-4 매핑에 잡힐 위험 없음.

---

## 6. 본선 영향 점검

- counter.py / baseline.py / config/symbol_rules.yaml **무수정**.
- 추가된 파일: `outputs/diagnose/round_length4_도면1_table.py`, `outputs/diagnose/round_length4_도면1_table.txt` (격리 위치, import 경로만 poc_v2/tests 참조).
- 회귀 1단계 14/16 그대로 유지 (테스트 미실행 — 코드 변경 없음).
