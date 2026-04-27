# Stage 3.5 — Valuation 지표 추가 (ERP / Buffett Indicator / Shiller CAPE)

**Status**: Accepted  
**Date**: 2026-04-24  
**Stage**: 3.5 — PR #14  
**Related PR**: PR #14

---

## Context

Layer 3 (Surface — Equity/Vol) 는 변동성(VIX/MOVE/SKEW)만 측정하여 *"시장이 지금 얼마나 흔들리는가"* 에만 답한다.  
Stage 3.5 는 *"시장이 얼마나 취약한 상태인가"* (= 잠재 낙폭) 를 추가하여 TMRS 를 완성한다.

**핵심 통찰**:
> Valuation 자체보다 *"고평가 상태에서 자금 조건이 악화되는 순간"* 이 진짜 신호다.

---

## 3개 지표 선택 근거

| 지표 | 역할 | 특징 |
|------|------|------|
| **ERP** (Equity Risk Premium) | 금리 환경 반영 | 주식 vs 국채 실시간 비교. 금리 상승기 즉각 반응 |
| **Buffett Indicator** | 거시 밸류 레벨 | 전체 시장 시총/GDP. 주기적 과대평가 측정 |
| **Shiller CAPE** | 역사적 맥락 | 10년 평균 실질이익 기준. 닷컴(44)/GFC(27)/현재(~40) 비교 |

### 거부된 지표

- **P/S ratio**: CAPE 와 방향 redundancy → 제외
- **Discount Rate Adjusted PE**: ERP 와 중복 → 제외
- **Earnings Quality (Profit Margin, Revision)**: 무료 데이터 부재 → 보류

---

## 데이터 소스 (TW 확인 완료)

| 지표 | 구성 요소 | 소스 | 확인 상태 |
|------|-----------|------|-----------|
| ERP | 10Y Treasury | FRED `DGS10` | ✅ 일별 |
| ERP | S&P 500 PE | `yf.Ticker("SPY").info['trailingPE']` → multpl.com fallback | ✅ (fallback 포함) |
| Buffett | Wilshire 5000 | `yf.Ticker("^W5000").history()` (FRED WILL5000IND 2024-06 폐기) | ✅ |
| Buffett | GDP | FRED `GDP` | ✅ 분기별 |
| CAPE | Shiller CAPE | shillerdata.com CSV → multpl.com fallback | ✅ 월별 |

### 중요: FRED WILL5000IND 폐기 대응

FRED의 Wilshire 5000 시리즈(WILL5000IND)는 **2024년 6월 3일 폐기**됨.  
Yahoo Finance 는 여전히 `^W5000` 티커로 동일 데이터 제공 → yfinance 로 수집.

---

## Buffett Indicator 계산 방식

```python
buffett_pct = (w5000_index / gdp_billions) * 100
```

검증:
- 2009 trough: W5000 ≈ 7,000 / GDP ≈ 14,000B → 50% ✓
- 2000 peak: W5000 ≈ 14,000 / GDP ≈ 10,000B → 140% ✓
- 2024 현재: W5000 ≈ 57,000 / GDP ≈ 29,000B → ~197% ✓

**Tier 판단**: percentile 기반 (2015년~ 분포), 절대값 임계 미사용.

| Percentile | Tier |
|------------|------|
| < 50th | Normal |
| 50~75th | Watch |
| 75~90th | Stress |
| > 90th | Crisis |

---

## Layer 3 가중치 변경

| | 변경 전 | 변경 후 |
|--|---------|---------|
| spec_indicators | 7 | 10 |
| spec_max_score | 15pt | 22pt |
| l3 score cap | 15.0 | 22.0 |
| l3 severity 분모 | /15 | /22 |

### 신규 가중 배분

| 지표 | cap | 기존/신규 |
|------|-----|---------|
| VIX | 3pt | 기존 |
| MOVE | 3pt | 기존 |
| SKEW | 3pt | 기존 |
| MOVE/VIX | 2pt | 기존 |
| **ERP** | **3pt** | **신규** |
| **Buffett** | **2pt** | **신규** |
| **CAPE** | **2pt** | **신규** |
| 합계 | **18pt** | (spec 22pt) |

---

## Valuation Composite (Regime Map 용)

```python
_VAL_SPEC = {
    "erp":     {"weight": 3, "direction": "inverse",    "normal": 3.0, "crisis": 0.0},
    "buffett": {"weight": 2, "direction": "percentile", "normal": 50, "crisis": 90},
    "cape":    {"weight": 2, "direction": "normal",     "normal": 20, "crisis": 36},
}
# composite = 가중 평균 norm (0=저평가, 1=극단적 과대평가)
# Regime Map Y축으로 사용 (PR #15)
```

---

## 스케줄

| 함수 | 주기 | 시각 (KST) |
|------|------|------------|
| `refresh_erp()` | 일별 | 07:30, 22:30 |
| `refresh_buffett()` | 일별 | 07:35, 22:35 |
| `refresh_cape()` | 일별 체크 (월별 변경) | 07:40 |

---

## Consequences

**긍정적:**
- TMRS Layer 3 spec 대비 coverage 57% → 82% (18/22pt 활성)
- "잠재 낙폭" 측정으로 Funding Stress + Credit + Valuation 통합 분석 가능
- Regime Map Y축 데이터 확보 (PR #15 전제조건 충족)
- 현재 CAPE ~40 → Crisis (닷컴 수준) 즉시 표시

**부정적 / 주의:**
- ERP PE 소스가 yfinance SPY 불안정 시 multpl.com 월별 scraping에 의존 (fragile)
- CAPE 소스 shillerdata.com/multpl.com HTML 구조 변경 시 breakage 위험
- Buffett 절대값 ~197%가 임계(>90th pct)에 해당할 경우 Layer 3 score 즉시 상승 → normalized TMRS 소폭 하락
- l3 분모 /15→/22 변경으로 Divergence 계산 소폭 변동 (l3_sev 감소)
