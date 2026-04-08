# Financial Macro Monitoring & Risk Framework (Reference Notes)

---

## 1. Objective

This document consolidates key frameworks, signals, and interpretations used for:

- Fed liquidity analysis
- Market stress detection
- Risk scoring system (0–100)
- Asset allocation & trading triggers
- Event-driven macro response (e.g. geopolitical shocks)

---

## 2. Core Philosophy

### 2.1 Market Structure

Markets operate in layered structure:

1. Surface layer → Equity / VIX / headlines
2. Middle layer → Credit spreads / HY OAS
3. Deep layer → Funding (repo, basis, CP)

Key principle:

"Funding breaks first → credit next → equities last"

---

## 3. Key Indicators

### 3.1 Funding Stress

- USDJPY Cross Currency Basis (1M, 3M)
- FRA-OIS spread
- Repo / Reverse Repo usage
- SOFR vs EFFR stability

Interpretation:

- 1M basis < -60 → early stress
- 3M basis < -100 → structural stress
- FRA-OIS > 50bp → funding breakdown

---

### 3.2 Credit Stress

#### Short-term (early signal)
- A2/P2 Commercial Paper (30D)

Thresholds:
- <4.00 → normal
- 4.00–4.20 → stress building
- >4.20 → credit tightening

#### Long-term (confirmation)
- HY OAS (ICE BofA)

Thresholds:
- <3.5% → risk-on
- 3.5–5% → stress
- >5% → crisis

---

### 3.3 Volatility

- VIX (equity vol)
- MOVE (bond vol)

Interpretation:

- VIX reacts late
- MOVE reacts early (rates instability)

---

### 3.4 Liquidity

- Reverse Repo (RRP)
- Fed Securities Lending
- SOMA balance sheet

Interpretation:

- RRP spike → liquidity drain
- Securities lending ↑ → collateral shortage

---

## 4. Risk Scoring System (0–100)

### 4.1 Components

| Category | Weight |
|----------|--------|
| Funding | 25 |
| Credit (CP) | 20 |
| Credit (HY) | 20 |
| Volatility | 15 |
| Liquidity | 20 |

---

### 4.2 Interpretation

| Score | Meaning |
|------|--------|
| 0–30 | Stable |
| 30–50 | Early stress |
| 50–70 | Escalating |
| 70–100 | Crisis |

---

## 5. Market Stage Model

### Stage 1: Early Stress
- Funding weak
- Credit stable
- Equities 상승

### Stage 2: Credit Break
- HY OAS 상승
- CP 상승

### Stage 3: Liquidity Crisis
- Repo dysfunction
- Central bank intervention

### Stage 4: Panic
- Equity collapse
- VIX spike

---

## 6. Key Signal Logic

### Early Warning (Best Entry Zone)

- Submitted liquidity demand ↑
- Accepted stable
- Basis widening

Meaning:
"Hidden stress building"

---

### Crisis Confirmation

- Accepted ↑ sharply
- SOFR spike
- HY OAS breakout

Meaning:
"Crisis already started"

---

## 7. Event Overlay (Geopolitics)

Example: US–Iran tension

### Scenario A: De-escalation
- Oil ↓
- VIX ↓
- Risk assets ↑

### Scenario B: Escalation
- Oil ↑ sharply
- Funding stress ↑
- Risk assets ↓

### Important Concept

"Event does not create crisis; it triggers existing stress"

---

## 8. Current Structural Pattern

Observed pattern:

- Equity stable
- Credit mixed
- Funding stressed

Interpretation:

"Surface calm, internal tension"

---

## 9. Trading Framework

### 9.1 Positioning (Example: TQQQ Put)

#### Entry
- Early stress phase

#### Add
- Credit confirmation

#### Exit
- Panic (VIX spike / policy response)

---

### 9.2 Key Triggers

Add Risk (Bearish):

- A2/P2 > 4.20
- HY OAS > 3.5
- 3M basis < -140

Reduce Risk:

- Central bank liquidity injection
- HY spread tightening

---

## 10. USDJPY Basis Interpretation

- Negative = USD shortage
- More negative = higher stress

Important:

- Level ≠ change
- Change = momentum

---

## 11. Historical Pattern

### 2020 COVID

1. Funding stress
2. Equity drop
3. Fed intervention

### 2008 GFC

1. Funding freeze
2. Credit collapse
3. System crisis

---

## 12. Key Insight Summary

- Markets break from inside (funding)
- Credit confirms
- Equity reacts last

---

## 13. Implementation Ideas (for App)

### Modules

1. Data ingestion (Fed, FRED, market APIs)
2. Indicator calculation
3. Risk scoring engine
4. Alert system
5. Dashboard visualization

---

### Suggested Features

- Daily automated risk score
- Threshold-based alerts
- Event overlay tagging
- Historical comparison (2008, 2020)

---

## 14. Final Principle

"Crisis is not when data looks bad; it is when data changes regime"

---

