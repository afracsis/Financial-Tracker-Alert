# Financial Tracker — v1.0.1 Stage 3.7 Instructions

> **Claude Code 작업 지시서 — Stage 3.7 착수**
> 본 문서는 Stage 3.7 (Leverage/Speculation 지표 추가) 지시서입니다.

| 항목 | 내용 |
|---|---|
| **Baseline** | Stage 3.5 완료, PR #1~#19 merge |
| **Threshold Table 버전** | `v1.2026-04-01` (유지) |
| **Score Version** | `v1.0.1` (유지) |
| **작업 기준일** | 2026-05-06 |
| **Repo 구조** | `dashboard/` 하위 실행, GitHub root 동기화 (sync_from_github.py) |

---

## 0. 개요

### 0.1 Stage 3.7 의 목적

현재 Layer 3 는 **변동성** (VIX, MOVE, SKEW) 과 **Valuation** (ERP, Buffett, CAPE) 을 측정합니다. 그러나 **"얼마나 빚으로 샀는가"** (Leverage) 와 **"투기가 얼마나 과열인가"** (Speculation) 는 측정하지 못합니다.

핵심 통찰:
> 높은 Valuation + 높은 Leverage = 하락 시 강제 청산 캐스케이드
> "떨어질 공간 크고 + 떨어지면 강제 매도까지" = 구조적 fragility 극대화

현재 실제 수치:
- FINRA Margin Debt / GDP: 3.83% (역대 최고 4.07% 근접)
- Net Credit Balance: −$793.5B (역대 최저 근방, Free Credit / Margin Debt ≈ 0.17)
- FINRA Margin Debt YoY: +38.7% (극단적 증가 속도)

3개 Leverage 지표를 Layer 3 에 추가합니다.

### 0.2 Stage 3.7 의 비범위

- JPY 점수 활성화 → Stage 2.4 (약 5일 후)
- ERS v0 → Stage 4 (JPY 이후)
- 한국 시장 레버리지 지표 (신용거래융자 등) → 향후 별도 Stage
- AAII Sentiment → 주별 수동 데이터, 보류
- 0DTE Option Volume → 안정적 무료 데이터 부재, 보류
- Household Equity Allocation → 분기별 + 10주 후행, 보류

### 0.3 전체 로드맵

```
[완료] Stage 1 ~ Stage 3.5                              ✅
[현재] Stage 3.7   — Leverage 지표 추가 ← 본 지시서
[대기] Stage 2.4   — JPY 점수 활성화 (약 2026-05-12)
[이후] Stage 4     — ERS v0
```

---

## 0.5 Claude Code 가 모르는 변경 사항

### A. Stage 3.5 완료 이력 (PR #14~#19)

**A.1 PR #14 + #15 — Valuation 3개 지표 추가**
- ERP (Equity Risk Premium): SPY trailingPE + FRED DGS10 → 3pt Layer 3
- Buffett Indicator: yfinance ^W5000 + FRED GDP → 2pt Layer 3 (percentile 기반 tier)
- Shiller CAPE: multpl.com 스크래핑 → 2pt Layer 3
- ERP/CAPE 파싱 hotfix: multpl.com 의 `†` / `&#x2002;` 특수문자 처리
- Layer 3 spec: 7→10, max: 15→22

**A.2 PR #16 + #17 — Regime Map 위젯**
- Signal Desk 우측 카드 하단 분할: IT (좌) + Regime Map (우)
- 4사분면: X축 = l1_norm, Y축 = valuation composite
- Buffett percentile snapshot 누락 버그 수정

**A.3 PR #18 + #19 — UI 미세 조정**
- Portfolio/JPY Swap 새로고침 버튼 수정/추가
- Volatility MOVE/VIX 카드 렌더링 버그 수정 (badgeId=null TypeError)

### B. 현재 시스템 상태 (2026-05-06)

```
TMRS: 31.8 (Normalized) / 원점수 24.5 / 77pt / 주의
Coverage: 58.3%

Layer 1: 14.7/45   6/12    Funding (완화 추세)
Layer 2: 0.0/30    6+1/8   Credit (전부 Normal)
Layer 3: 9.8/22    7/10    Equity (Valuation Crisis)
  ERP:     -0.86%  Crisis
  Buffett: 228%    Crisis  
  CAPE:    40.7    Crisis
  VIX 17.9, MOVE 65.9 정상

LDS: 🟢 0.516
Regime Map: ★ Bubble Expansion (Crash Risk 경계)
Inverse Turkey: 미감지
```

### C. 현재 Signal Desk 우측 카드 구조

```
┌─────────────────────────────────────────┐
│  LINDY DISTANCE              🟢 0.516   │  상단 55%
│  CP Sprd  ███░░░  0.26                  │
│  S-B OAS  ████░░  0.48                  │
│  HY OAS   █████░  0.48                  │
│  HYG Day  ██████  1.00                  │
├────────────────────┬────────────────────┤
│  INVERSE TURKEY    │  FRAGILITY REGIME  │
│  🐻 미감지         │  [4사분면 미니맵]   │  하단 45%
│  l12: 0.163        │  ★ Bubble Exp.    │
│  l3: 0.445         │                    │
└────────────────────┴────────────────────┘
```

### D. 데이터 소스 사전 조사 결과

**FINRA Margin Statistics**:
- URL: https://www.finra.org/rules-guidance/key-topics/margin-accounts/margin-statistics
- 제공: Debit Balance (Margin Debt) + Free Credit Balance (Cash + Margin)
- 갱신: 월별 (매월 3주차에 전월 데이터 발표)
- 포맷: Excel 다운로드 (1997년~)
- 현재 수치 (2026년 3월): Margin Debt $1.22조, Free Credit $203.7B

**CBOE Put/Call Ratio**:
- CBOE 일별 제공
- FRED 에 관련 시리즈 존재 가능 (Claude Code 가 확인 필요)
- 대안: yfinance 또는 CBOE 웹 스크래핑

### E. 작업 원칙

Stage 1~3.5 와 동일:
1. 새 feature branch, base = main
2. ADR 작성
3. TW 검토 없이 다음 작업 금지
4. 기존 Valuation/LDS/Inverse Turkey 로직 변경 없음
5. **데이터 소스 확보 시 TW 에게 먼저 보고** (FRED Series ID 직접 확인 원칙)
6. **월별 데이터 (Margin/Net Credit) 는 CAPE 와 같은 패턴으로 구현** (변경 시만 저장)

---

## 1. Stage 3.7 작업 내용

### 1.1 PR #20 — Leverage/Speculation 3개 지표 + Layer 3 통합

#### 1.1.1 지표 1 — Margin Debt / GDP

**정의**: FINRA 마진 부채 / 미국 명목 GDP × 100

**의미**: 경제 규모 대비 투자자 레버리지. 역사적으로 버블 피크와 강한 상관.

**데이터 소스**:
- Margin Debt: FINRA Excel 다운로드에서 Debit Balance 추출
  - 대안 1: FINRA 웹페이지 HTML 스크래핑
  - 대안 2: 수동 입력 (월 1회)
  - **Claude Code 가 가장 안정적인 자동화 방법 조사 → TW 에게 보고**
- GDP: FRED Series `GDP` (분기별, 이미 Buffett Indicator 에서 사용 중 — 재사용)

**DB 테이블**:

```sql
CREATE TABLE IF NOT EXISTS leverage_margin_debt (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL UNIQUE,      -- YYYY-MM-01 (월별)
    margin_debt_mil REAL NOT NULL,  -- Debit Balance (백만 달러)
    free_credit_mil REAL,           -- Free Credit Balance (백만 달러)
    gdp_billions REAL,              -- GDP (십억 달러, 직전 분기)
    margin_gdp_pct REAL,            -- Margin Debt / GDP * 100
    net_credit_ratio REAL,          -- Free Credit / Margin Debt
    fetched_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_margin_date ON leverage_margin_debt(date);
```

**주의**: Margin Debt 와 Free Credit 을 **같은 테이블**에 저장. 같은 FINRA 소스에서 동시 확보. Net Credit Ratio 도 같이 계산하여 저장.

**임계값**:

| Zone | 임계 | 역사적 근거 |
|---|---|---|
| Normal | < 2.5% | 장기 중앙값 (2000년 이전 평균) |
| Watch | 2.5 ~ 3.0% | 닷컴/금융위기 피크 수준 |
| Stress | 3.0 ~ 3.8% | 2021 피크 근접 |
| Crisis | > 3.8% | 역대 최고 구간 |

Direction: 정방향 (높을수록 stress)

**점수 엔진**:
- Layer: 3
- 가중 (cap): 2pt
- Mode: interpolated scoring

**Snapshot 키**:
```json
"margin_gdp": {
    "value": 3.83,
    "tier": "crisis",
    "name": "Margin Debt / GDP",
    "cap": 2,
    "unit": "%",
    "layer": 3
}
```

#### 1.1.2 지표 2 — Net Credit Ratio (Free Credit / Margin Debt)

**정의**: Free Credit Balance / Margin Debt

**의미**: 투자자 현금 소진도. 낮을수록 현금이 거의 없이 빚으로 투자 중 = 강제 청산에 취약.

**데이터**: leverage_margin_debt 테이블에 이미 포함 (같은 FINRA 소스). 별도 테이블 불필요.

**임계값**:

| Zone | 임계 | 의미 |
|---|---|---|
| Normal | > 0.40 | 현금이 빚의 40%+ (여유) |
| Watch | 0.30 ~ 0.40 | 현금 여유 감소 |
| Stress | 0.20 ~ 0.30 | 현금 거의 소진 |
| Crisis | < 0.20 | 극단 레버리지 (현재 약 0.17) |

Direction: inverse (낮을수록 stress)

**점수 엔진**:
- Layer: 3
- 가중 (cap): 2pt

**Snapshot 키**:
```json
"net_credit_ratio": {
    "value": 0.167,
    "tier": "crisis",
    "name": "Net Credit Ratio",
    "cap": 2,
    "unit": "",
    "layer": 3
}
```

#### 1.1.3 지표 3 — Put/Call Ratio (CBOE Equity)

**정의**: CBOE Equity Put 거래량 / Call 거래량

**의미**: 옵션 시장 투기 과열도. 콜 과다 (< 0.50) 는 투기 과열, 풋 과다 (> 1.0) 는 공포.

**데이터 소스** (Claude Code 가 조사하여 TW 보고):
- 1순위: FRED 에 CBOE Put/Call 관련 시리즈 검색
- 2순위: CBOE 웹사이트 직접 스크래핑
- 3순위: 기타 무료 API (macrotrends, ycharts 등)
- **데이터 소스 확보 결과를 TW 에게 먼저 보고 후 구현**

**DB 테이블**:

```sql
CREATE TABLE IF NOT EXISTS leverage_put_call (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL UNIQUE,
    put_call_ratio REAL NOT NULL,
    fetched_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pc_date ON leverage_put_call(date);
```

**임계값** (과열 방향 = 콜 과다 = 비율 낮음):

| Zone | 임계 | 의미 |
|---|---|---|
| Normal | 0.60 ~ 0.85 | 균형 |
| Watch | 0.50 ~ 0.60 | 콜 편향 시작 |
| Stress | 0.40 ~ 0.50 | 투기 과열 |
| Crisis | < 0.40 | 극단 콜 광풍 (버블 후기) |

Direction: inverse (낮을수록 stress — 콜 과다 = 투기 과열)

**주의**: 이 지표는 **과열 방향만** stress 로 측정. 극단 비관 (> 1.0) 은 역발상 매수 신호이지만 TMRS 에서는 이 방향을 stress 로 취급하지 않음 (Valuation 과 일관성).

**점수 엔진**:
- Layer: 3
- 가중 (cap): 2pt

**Snapshot 키**:
```json
"put_call": {
    "value": 0.45,
    "tier": "stress",
    "name": "Put/Call Ratio",
    "cap": 2,
    "unit": "",
    "layer": 3
}
```

#### 1.1.4 Layer 3 가중치 변경

**변경 전** (Stage 3.5):

| 그룹 | 지표 | 가중 | 상태 |
|---|---|---|---|
| Vol | VIX, MOVE, SKEW, MOVE/VIX | 11pt | 기존 |
| Val | ERP, Buffett, CAPE | 7pt | 기존 |
| **합계** | | **18pt** | spec 22pt |

**변경 후** (Stage 3.7):

| 그룹 | 지표 | 가중 | 상태 |
|---|---|---|---|
| Vol | VIX, MOVE, SKEW, MOVE/VIX | 11pt | 기존 |
| Val | ERP, Buffett, CAPE | 7pt | 기존 |
| Lev | Margin/GDP, Net Credit, Put/Call | 6pt | **신규** |
| **합계** | | **24pt** | spec 28pt |

**LAYER_SPEC 업데이트**:

```python
LAYER_SPEC = {
    '1': {'spec_indicators': 12, 'spec_max_score': 45},
    '2': {'spec_indicators': 8,  'spec_max_score': 30},
    '3': {'spec_indicators': 13, 'spec_max_score': 28},  # 10→13, 22→28
    'divergence': {'spec_indicators': 5, 'spec_max_score': 10},
}
```

#### 1.1.5 Backfill

**Margin Debt + Net Credit**:
- FINRA Excel 에 1997년~ 월별 데이터 존재
- 최근 5년 (2021~) backfill 권장
- `existing == 0` 패턴 적용

**Put/Call Ratio**:
- 데이터 소스에 따라 backfill 범위 결정
- FRED 시리즈 사용 시 limit=1000 패턴
- 스크래핑 시 최근 1년 backfill

#### 1.1.6 스케줄러 등록

```python
# Margin Debt + Net Credit: 월 1회 (매월 20일 08:00 KST)
# FINRA 가 매월 3주차 발표하므로 20일 이후 체크
scheduler.add_job(refresh_margin_debt, 'cron', day=20, hour=8, ...)

# Put/Call Ratio: 일별 (07:30, 22:30 KST)
scheduler.add_job(refresh_put_call, 'cron', hour='7,22', minute=30, ...)
```

#### 1.1.7 Signal Desk 상세 카드

3개 지표에 대해 기존 패턴과 동일한 상세 카드:

```python
INDICATOR_INTERPRETATIONS.update({
    'margin_gdp': "Margin Debt / GDP. 경제 규모 대비 투자자 레버리지. 역대 최고 4.07% (2026.1). 닷컴 2.6%, 금융위기 2.5%.",
    'net_credit_ratio': "Net Credit Ratio. 현금 대비 빚 비율. 낮을수록 투자자 현금 소진 — 강제 청산에 취약.",
    'put_call': "Put/Call Ratio. CBOE 옵션 거래량 비율. 낮을수록 콜 과다 = 투기 과열.",
})
```

#### 1.1.8 ADR

`docs/decisions/2026-05-06-stage3-7-leverage-indicators.md`

내용:
- 3개 지표 선택 근거
- 거부된 지표 (AAII: 주별 수동, 0DTE: 데이터 부재, Household Allocation: 분기별 후행)
- 임계값 설계 근거 (역사적 분포)
- FINRA 데이터 확보 방식
- Layer 3 가중치 변경 (18pt → 24pt)
- 사상적 의미: Valuation + Leverage = fragility 의 두 축

#### 1.1.9 PR #20 체크리스트

- [ ] `leverage_margin_debt` 테이블 신설
- [ ] `leverage_put_call` 테이블 신설
- [ ] `refresh_margin_debt()` 함수 (FINRA 데이터 확보 + GDP 결합)
- [ ] `refresh_put_call()` 함수
- [ ] Backfill (existing==0 패턴)
- [ ] `_compute_tmrs()` 에 3개 지표 tier + 점수 추가
- [ ] snapshot 에 margin_gdp / net_credit_ratio / put_call 키 추가
- [ ] LAYER_SPEC 업데이트 (Layer 3: spec 13, max 28)
- [ ] 스케줄러 등록
- [ ] `_startup_full_refresh()` 에 초기 수집 추가
- [ ] Signal Desk 상세 카드 (3개 지표)
- [ ] INDICATOR_INTERPRETATIONS + INDICATOR_THRESHOLDS 추가
- [ ] ADR 작성
- [ ] **데이터 소스 확보 결과 TW 먼저 보고** (특히 FINRA 자동화 + Put/Call 소스)

---

## 2. Stage 3.7 완료 조건

### 2.1 체크리스트

- [ ] PR #20 merge
- [ ] Replit sync + 앱 재시작
- [ ] 3개 지표 데이터 수집 확인
- [ ] TMRS snapshot 에 3개 키 존재
- [ ] Layer 3 점수 변화 확인
- [ ] Signal Desk 상세 카드 정상 표시
- [ ] Coverage 변화 확인

### 2.2 완료 후 예상 상태

```
Layer 3:
  Vol:  VIX(3) + MOVE(3) + SKEW(3) + MOVE/VIX(2) = 11pt
  Val:  ERP(3) + Buffett(2) + CAPE(2) = 7pt
  Lev:  Margin/GDP(2) + Net Credit(2) + Put/Call(2) = 6pt
  합계: 24pt 활성 / 28pt spec

Coverage: ~61% → ~63% (Layer 3 개선)
max_achievable: 77pt → 83pt
```

---

## 3. 작업 원칙 재확인

### 3.1 반드시 지킬 것

1. 새 feature branch `claude/stage3-7-leverage`
2. PR base = main
3. ADR 포함
4. 기존 Valuation/LDS/Inverse Turkey/Regime Map 로직 변경 없음
5. **FINRA 데이터 소스 확보 결과 TW 먼저 보고**
6. **FRED Series ID 웹에서 직접 확인** (Single-B OAS 교훈)
7. **월별 데이터 (Margin/Net Credit) 는 CAPE 패턴** (변경 시만 저장)

### 3.2 피할 것

1. 이전 feature branch 에 추가 커밋
2. FINRA 소스 없이 임의 수치 입력
3. Put/Call 의 극단 비관 방향 (> 1.0) 을 stress 로 측정 (과열 방향만)
4. Layer 1/2 가중치 변경

---

## 4. 착수 메시지 (TW → Claude Code)

> Stage 3.5 완료 후 Stage 3.7 을 시작한다.
>
> 먼저 `Stage3_7_Instructions.md` 를 전체 읽어줘. 특히 **Section 0.5** 확인.
>
> 읽은 후 다음을 보고해줘:
>
> 1. Section 0.5 핵심 변경사항 이해도 요약 (3줄)
> 2. **데이터 소스 확보 가능성 조사 결과**:
>    - FINRA Margin Statistics: Excel 자동 다운로드 가능한지, 스크래핑 가능한지
>    - CBOE Put/Call Ratio: FRED 시리즈 존재 여부, 대안 소스
> 3. 예상 기술 이슈 (있다면)
>
> **데이터 소스 확인 결과를 먼저 보고해줘. 구현 전에 TW 가 검토할거야.**
>
> **작업 원칙**:
> - 새 feature branch `claude/stage3-7-leverage`
> - PR base = main
> - 기존 Valuation/LDS/Regime Map 로직 변경 없음
> - FINRA 데이터 확보 방식 TW 에게 먼저 보고
> - FRED Series ID 는 반드시 웹에서 직접 확인
>
> Stage 3.7 시작 준비해줘.

---

**끝 (End of Stage 3.7 Instructions)**

*Financial Tracker — v1.0.1 Stage 3.7 Instructions*
*작성: 2026-05-06 | TW × Claude Opus 4.6*
