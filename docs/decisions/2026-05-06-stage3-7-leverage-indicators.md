# ADR: Stage 3.7 — Leverage / Speculation 지표 (3-h, 3-i, 3-j)

**날짜**: 2026-05-06  
**상태**: 승인됨  
**레이어**: Layer 3 (Valuation & Leverage)

---

## 배경

Stage 3.5에서 ERP / Buffett / CAPE (Layer 3-e, 3-f, 3-g) 3개 Valuation 지표를 추가했다.  
Stage 3.7은 투자자 레버리지 및 투기 과열을 측정하는 3개 지표를 추가한다.

- **3-h** Margin Debt / GDP (FINRA)
- **3-i** Net Credit Ratio = Free Credit / Margin Debt (FINRA)
- **3-j** CBOE Equity Put/Call Ratio (CBOE)

Layer 3 스펙: 7 → 10 (Stage 3.5) → **13개**, 만점 15 → 22 → **28점**.

---

## 결정

### 데이터 소스

| 지표 | 소스 | 갱신 주기 |
|------|------|-----------|
| Margin Debt / GDP | FINRA margin-statistics.xlsx | 월 1회 (전월 데이터 ~20일 공시) |
| Net Credit Ratio | 동일 Excel (Free Credit 컬럼) | 월 1회 |
| Put/Call Ratio | CBOE equitypc.csv | 일별 |

### FINRA Excel 다운로드 전략

**전략 A (우선)**: FINRA 페이지 HTML 파싱으로 `.xlsx` 링크 추출  
**전략 B (fallback)**: 최근 6개월 URL `{YYYY-MM}/margin-statistics.xlsx` 순차 시도  
이유: FINRA URL 날짜 폴더가 매월 변경되며 정확한 공시일이 불규칙하다.

### CBOE 접근

- `https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/equitypc.csv`
- FRED에 별도 Equity P/C 시리즈 없음. CBOE CDN 직접 접근 확인 (HTTP 200).

### GDP 재사용

Buffett Indicator 에서 이미 수집하는 FRED `GDP` 시리즈를 재사용.  
`fetch_fred_observations("GDP")` → 분기별 데이터. 날짜 ±2개월 허용으로 조인.

### 임계값

| 지표 | normal | watch | stress | crisis |
|------|--------|-------|--------|--------|
| Margin/GDP | < 2.5% | 2.5~3.0% | 3.0~3.8% | > 3.8% |
| Net Credit | > 0.40 | 0.30~0.40 | 0.20~0.30 | < 0.20 |
| Put/Call | ≥ 0.60 | 0.50~0.60 | 0.40~0.50 | < 0.40 |

역대 참고치: 닷컴 Margin/GDP 2.6%, 금융위기 2.5%, 2026.1 역대 최고 4.07%.  
Put/Call < 0.40 = 역대 극단 과열.

### Cap 설정

각 지표 cap=2pt. 3개 합계 max 6pt → l3 총 28pt (22 + 6).

### l3 계산 갱신

```python
l3 = min(round(l3, 2), 28.0)   # 22 → 28
l3_sev = l3 / 28 if l3 > 0 else 0.0  # /22 → /28
```

### 스케줄러

- `refresh_put_call`: 매일 07:45 / 22:45 KST
- `refresh_margin_debt`: 매월 20일 08:00 KST (FINRA 공시 예상일 이후)

### Startup

- Step 17: `refresh_margin_debt()` + `refresh_put_call()` 초기 로드
- Step 18: `_compute_tmrs(trigger="startup_leverage")` 재계산

---

## 기각된 대안

- **FRED MARGIN (Margin Debt FRED 시리즈)**: FRED 시리즈 `BOGZ1FL663067003Q`는 분기별이며 FINRA보다 지연. FINRA 직접 파싱 선택.
- **Total Put/Call (PCALL)**: Total P/C는 index 옵션 헤지 수요로 오염. Equity P/C만 투기 측정에 적합.
- **FRED PCALL 시리즈**: 제공 안 됨.
