# 라운드 베이스라인-7 보고서 — 분리본 시트 routing 일반화

> **목표**: 누적된 분리본 시트 routing 한계 3종을 `sheet_name_matcher.py` 일반화
> 룰(component 매칭)로 통합 해결. 새 도면 추가 없는 일반화 라운드.
> **결과**: 도면1·3 PASS, 도면5 격리. 본선·yaml·정답지 무수정. 회귀 무영향.

---

## 1. 요약

| 항목 | 내용 |
|---|---|
| 수정 파일 | `poc_v2/baseline2/sheet_name_matcher.py` 1개 (+ 회귀 테스트 2개) |
| 본선 영향 | `counter.py`·`baseline.py`·`length/`·`spec_extractor.py`·모든 yaml **무수정** |
| 신규 단계 | 매칭 순서에 `component` 추가 (exact→partial→**component**→fallback→unmatched) |
| 누적 한계 | 도면1 Y03·도면3 종단면도 **해결**, 도면5 Y1축열 **격리** |
| 회귀 | 9종 전부 PASS 유지 (도면2 SC1·SC2 기존 2 fail 불변) |
| 결정론 | LLM·랜덤·외부 호출 0건 |

---

## 2. 분석 — 실측이 명세서(baseline-4 시점)와 다름

명세서 1.1은 baseline-4 시점 증상 기준이었으나, baseline-5/6에서 추가된
placeholder→length 우선 로직 때문에 실제 현 증상이 달랐다. 보완 전 실측:

| 케이스 | 분리본 표제부 | 보완 전 매칭 | 보완 전 kind |
|---|---|---|---|
| 도면1 Y03 단독본 | `Y03열 골구도` | None | **unmatched** |
| 도면3 종단면도 분리본 | `종단면도, 계단단면도` | `종단면도,계단단면도` | exact **count** |
| 도면5 Y1축열골조도 | `Y1축열 골조도` | `Y1 축열 골조도` | exact **count** |

세 케이스 모두 count 행이 placeholder(기둥 부호 0). 핵심은 length 라우팅으로
보내는 매칭 경로가 없었다는 것.

### 2.1 length 측정 후보의 실체

`length_routing.yaml` 의 `sheet_label` 이 곧 length 매칭 후보다. `load_length_labels`
가 `", "`(콤마+공백)·`"、"`로 분해(베이스라인-5 룰: 공백 없는 콤마는 토큰 내부로 보존):

| 도면 | 원본 `sheet_label` | 분해된 length 라벨 |
|---|---|---|
| 도면1 | `"(2동)Y01열골구도, (2동)Y03,Y05열골구도"` | `["(2동)Y01열골구도", "(2동)Y03,Y05열골구도"]` |
| 도면3 | `"종단면도, 계단단면도"` | `["종단면도", "계단단면도"]` |
| 도면5 | `"주단면도1, 주단면도4"` | `["주단면도1", "주단면도4"]` ← **Y1 라벨 없음** |

---

## 3. 해결 — component 매칭 2개 메커니즘

`sheet_name_matcher.py` 에 `component` 단계 추가. 두 독립 메커니즘.

### 3.1 메커니즘 A — 결합 표제부 split (도면3 해결)

분리본 표제부가 결합형(`'종단면도, 계단단면도'`)이라 placeholder count 행에
exact 단락(short-circuit)되어 count 로 가던 문제.

→ count 히트가 **placeholder 일 때**, 직접 length 히트가 없으면 표제부를 결합
구분자(`", "`·`"、"`·줄바꿈)로 쪼갠 컴포넌트를 length 라벨과 (exact→partial) 매칭.
일치하면 length 우선. 기존 placeholder→length 우선 로직의 "결합 표제부" 확장.

```
표제부 "종단면도, 계단단면도"
  → split ["종단면도", "계단단면도"]
  → length 라벨 "종단면도" 와 exact 일치 → length 라우팅 (component)
```

### 3.2 메커니즘 B — 열 식별자 suffix 공유 전개 (도면1 해결)

exact·partial 완전 실패(unmatched) 시, length 라벨 중 **영숫자 열 식별자 결합**
패턴(`[A-Za-z]+\d+,[A-Za-z]+\d+`)을 suffix 공유로 전개해 표제부와 partial 매칭.

```
length 라벨 "(2동)Y03,Y05열골구도"
  → 전개 ["(2동)Y03열골구도", "(2동)Y05열골구도"]
  → 표제부 "Y03열골구도" ⊂ "(2동)Y03열골구도" partial 일치 → length (component)
```

### 3.3 split 룰 명세 (베이스라인-5 충돌 회피)

| 구분자 | 처리 | 예시 |
|---|---|---|
| `", "` (콤마+공백) | split | `종단면도, 계단단면도` → 2개 |
| `"、"` | split | `종단면도、횡단면도` → 2개 |
| `"\n"`, `"\n("` | split | 줄바꿈 결합 |
| `","` (공백 없는 콤마) | **보존** (메커니즘 A) | `가,나동 종단면도` → 1개 |
| `[A-Za-z]+\d+,[A-Za-z]+\d+` | suffix 전개 (메커니즘 B만) | `Y03,Y05열골구도` → 2개 |

**핵심**: 메커니즘 B의 전개는 **영숫자 패턴 한정**이라 도면2 한글 동 라벨
`가,나동`은 `_ID_PAIR` 에 매칭되지 않아 **절대 전개되지 않는다**. 베이스라인-5의
"토큰 내부 콤마 보존"과 충돌하지 않음.

---

## 4. 검증 결과 (`round_baseline7_분리본검증.csv`)

| 케이스 | 보완 후 매칭 | 신뢰도 | 측정 | 정답 | 결과 |
|---|---|---|---|---|---|
| 도면1 Y03 단독본 | `(2동)Y03,Y05열골구도` | component/length | 6000 | 6000 | **PASS** |
| 도면3 종단면도 분리본 | `종단면도` | component/length | 19060 | 19060 | **PASS** |
| 도면5 Y1축열골조도 | `Y1 축열 골조도` | exact/count | N/A | 10500 | **격리** |

---

## 5. 회귀 무영향 검증

보완 후 회귀 9종 재실행. 보완 전후 fail 수 비교:

| 항목 | 보완 전 | 보완 후 |
|---|---|---|
| 도면2 SC1·SC2 (기존 데이터 한계) | 2 fail | 2 fail (불변) |
| `test_y03_standalone_unmatched` (baseline-6 한계 단언) | PASS(unmatched) | **의도적 갱신** → `test_y03_standalone_resolved_in_baseline7` (component/length) |
| 그 외 전부 | PASS | PASS |

부수적(예기치 못한) 회귀 0건. component 단계는 placeholder count(메커니즘 A) 또는
unmatched(메커니즘 B)에서만 발동하므로, 통합본이 exact/partial 로 잡히는 도면4·5는
component 단계에 도달하지 않아 영향 없음.

> baseline-6 `test_y03_standalone_unmatched` 갱신은 회귀가 아니라 **이번 라운드가
> 해결한 한계의 단언 갱신**이다(명세서 1.1 baseline-6 한계 항목).

---

## 6. 알려진 남은 한계

1. **도면5 Y1축열골조도 routing** — `length_routing.yaml` 에 Y1축열 측정 소스가
   등록돼 있지 않다(라벨은 `주단면도1, 주단면도4` 뿐). component 로 분해할 length
   라벨이 없어, **yaml 무수정 원칙(명세서 7.1)상 이번 라운드 해결 불가**. 명세서
   2.2 표는 "length 라우팅"을 낙관했으나 현실(yaml 미등록)과 불일치. count 유지로
   격리. → 다음 라운드 `length_routing.yaml` 에 Y1축열 소스 등록 후보.
2. **도면2 SC1·SC2 카운트** — 익명 블록 내 분리 TEXT(`'SC'`+`'1'`) 데이터 인코딩
   한계. counter 레이어 문제로 본질이 다름. 이번 범위 외, 격리 유지.

---

## 7. 다음 라운드 후보

- 도면5 Y1축열 `length_routing.yaml` 등록 (yaml 수정 라운드)
- 도면2 블록 내부 split-TEXT 재결합 (`counter.py` 수정)
- 보 부호 카운트 / 단위중량 산출

---

**문서 끝.**
