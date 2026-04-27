# Financial Tracker — v1.0.1 Stage 3.5 Instructions

> **Claude Code 작업 지시서 — Stage 3.5 착수**
> 본 문서는 Stage 3.5 (Equity Valuation 지표 추가 + Fragility Regime Map) 지시서입니다.

| 항목 | 내용 |
|---|---|
| **Baseline** | Stage 3 완료, PR #1~#13 merge |
| **Threshold Table 버전** | `v1.2026-04-01` (유지) |
| **Score Version** | `v1.0.1` (유지) |
| **작업 기준일** | 2026-04-24 |
| **Repo 구조** | `dashboard/` 하위 실행, GitHub root 동기화 (sync_from_github.py) |

---

## 0. 개요

### 0.1 Stage 3.5 의 목적

현재 Layer 3 (Surface — Equity/Vol) 는 **변동성** (VIX, MOVE, SKEW, MOVE/VIX) 만 측정합니다. 이는 *"시장이 지금 얼마나 흔들리고 있는가"* 에 대한 답이지만, **"시장이 얼마나 취약한 상태인가"** (= 잠재 낙폭) 는 답하지 못합니다.

카테고리 1 의 *"Equities react last"* 에서 **"얼마나 세게 react 할지"** 를 결정하는 변수가 바로 valuation 입니다.

**핵심 통찰**:
> Valuation 자체보다 **"valuation 이 높은 상태에서 자금 조건이 악화되는 순간"** 이 진짜 신호다.

이를 TMRS 에 반영하여:
1. **Layer 3 에 3개 Valuation 지표 추가** — ERP, Buffett Indicator, Shiller CAPE
2. **Fragility Regime Map 위젯 추가** — X축 (Liquidity) × Y축 (Valuation) 4사분면
3. **Signal Desk UI 확장** — 우측 카드 하단을 Inverse Turkey + Regime Map 으로 분할

### 0.2 Stage 3.5 의 비범위

- ERS v0 → Stage 4
- JPY 점수 활성화 → Stage 2.4 (대기 중)
- Earnings Quality 지표 (Profit Margin, Earnings Revision) → 무료 데이터 부재로 보류
- P/S ratio → CAPE 와 redundancy, 구현 안 함
- Discount Rate Adjusted PE → ERP 와 중복, 구현 안 함

### 0.3 전체 로드맵

```
[완료] Stage 1     — Layer 2 긴급 충실화
[완료] Stage 2.0~2.3 — UI + JPY 인프라 + Coverage + CP-EFFR + Korea CDS
[완료] Stage 3     — Hotfix + LDS + 명칭/임계 정리

[현재] Stage 3.5   — Valuation 지표 + Regime Map ← 본 지시서
[대기] Stage 2.4   — JPY 점수 활성화 (약 2026-05-07)
[이후] Stage 4     — ERS v0
```

---

## 0.5 Claude Code 가 모르는 변경 사항

### A. Stage 3 완료 이력 (PR #11~#13)

**A.1 PR #11 — Replit Hotfix + MOVE/SKEW Backfill**
- `_PUBLIC_PREFIXES` 3개 → 14개 경로 확장 (API 인증 우회)
- `loadFedOp()` 의 `data.` → `d.` 전수 수정 (Fed Operation DW/TGA 렌더링 버그 해결)
- `fetch_move_index()` + `fetch_skew_index()` backfill 패턴 수정 (`existing==0` 시 2022년부터)
- yfinance 패턴 버그 총 3건 수정 완료 (LQD + MOVE + SKEW)

**A.2 PR #12 — LDS (Lindy Distance Score) 구현**
- 4개 Credit 지표 (Single-B OAS, CP Spread, HY OAS, HYG Daily) 의 Crisis 장벽 접근도 측정
- `lindy_distance_score()`, `calculate_composite_lds()` 함수
- Signal Desk 우측 카드 분할: 상단 LDS + 하단 Inverse Turkey
- `alert_lindy_collapse()` — Composite LDS < 0.15 시 Telegram 알람 (24h dedup)
- 현재 Composite LDS ≈ 0.54 (🟢 린디 구간)

**A.3 PR #13 — 명칭/임계 정리**
- FRA-OIS → SOFR Term Premium UI 표시명 변경
- HY OAS 임계 v1.0 원문 복원: 3.5/5.0/7.0% → 3.0/4.0/5.5%
- LDS HY OAS barrier 도 7.0 → 5.5 동시 변경
- `docs/corrections/v1.0-jpy-basis-direction-correction.md` 정정 문서 작성

### B. 현재 시스템 상태

```
TMRS: 33.6 (Normalized) / 원점수 23.5 / 70pt / 주의
Coverage: 55.6%

Layer 1: 20.6/45 (Funding Stress 진행 중)
  🔴 RRP $0.16B (위기), SOFR-EFFR 8bp (위기)
  🔴 CP Spread 35bp, DW $5,306M (스트레스)

Layer 2: 0.0/30 (Credit 전부 Normal)

Layer 3: 1.6/15 (거의 평온, 변동성 낮음)
  ⚠ CBOE SKEW 140.7 (주의)
  🟢 VIX 17.9, MOVE 65.9 (정상)

LDS: 🟢 0.54 (린디 구간)
Inverse Turkey: 미감지

해석: "Funding breaks first" 단계. 
      Valuation 추가로 "떨어질 공간이 얼마나 큰가" 측정 가능해짐.
```

### C. Signal Desk 우측 카드 현재 구조

```
현재:
┌─────────────────────────────────────────┐
│  LINDY DISTANCE              🟢 0.54    │
│  (4개 지표 진행 바)                      │  상단
├─────────────────────────────────────────┤
│  INVERSE TURKEY                         │
│  🐻 미감지                              │  하단
│  l12: 0.229 / l3: 0.107                │
└─────────────────────────────────────────┘

변경 후:
┌─────────────────────────────────────────┐
│  LINDY DISTANCE              🟢 0.54    │
│  (4개 지표 진행 바)                      │  상단 55%
├────────────────────┬────────────────────┤
│  INVERSE TURKEY    │  FRAGILITY REGIME  │
│  🐻 미감지         │  (4사분면 미니맵)   │  하단 45%
│  l12: 0.229        │  ★ Crash Risk     │  (좌 50% + 우 50%)
│  l3: 0.107         │                    │
└────────────────────┴────────────────────┘
```

### D. 작업 원칙

Stage 1~3 과 동일:
1. 각 PR 마다 새 feature branch, base = main
2. ADR 작성
3. TW 검토 없이 다음 작업 금지
4. 기존 LDS, Inverse Turkey 로직 변경 없음
5. 기존 Layer 1/2 지표 로직 변경 없음

---

## 1. Stage 3.5 작업 내용

### 1.1 PR #14 — Valuation 데이터 수집 + Layer 3 점수 통합

#### 1.1.1 작업 범위

3개 Valuation 지표를 Layer 3 에 추가합니다. 기존 Layer 3 변동성 지표 (VIX/MOVE/SKEW/MOVE-VIX) 는 그대로 유지.

#### 1.1.2 지표 1 — Equity Risk Premium (ERP)

**정의**: S&P 500 Earnings Yield − 10Y Treasury Yield

```python
ERP = (1 / SP500_PE) * 100 - Treasury_10Y

# 예시: PE=25, 10Y=4.5%
# ERP = 4.0% - 4.5% = -0.5%
```

**의미**: 주식이 국채 대비 제공하는 초과 수익률. 낮을수록 주식이 채권 대비 비쌈. 금리 환경을 직접 반영하는 핵심 지표.

**데이터 소스**:
- **10Y Treasury Yield**: FRED Series `DGS10` (일별, 이미 비슷한 FRED 데이터 수집 인프라 존재)
- **S&P 500 PE**: 두 가지 옵션
  - 옵션 A: yfinance `^GSPC` 의 `.info['trailingPE']` (실시간, 단 가용성 불안정)
  - 옵션 B: FRED Series `MULTPL/SP500_PE_RATIO_MONTH` 또는 multpl.com CSV (월별)
  - **권장: 옵션 A 시도 → 실패 시 옵션 B fallback**

**DB 테이블**:

```sql
CREATE TABLE IF NOT EXISTS valuation_erp (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL UNIQUE,
    sp500_pe REAL,
    treasury_10y REAL,
    erp_pct REAL NOT NULL,       -- ERP (%)
    fetched_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_erp_date ON valuation_erp(date);
```

**임계값**:

| Zone | 임계 | 의미 |
|---|---|---|
| Normal | > 3.0% | 주식이 채권 대비 충분한 프리미엄 제공 |
| Watch | 1.5% ~ 3.0% | 프리미엄 축소 |
| Stress | 0.0% ~ 1.5% | 주식과 채권 수익률 거의 동등 |
| Crisis | < 0.0% | 주식이 채권보다 수익 낮음 (극단적 과대평가) |

Direction: `inverse` (ERP 낮을수록 stress)

**점수 엔진**:
- Layer: 3
- 가중 (cap): 3pt
- Mode: interpolated scoring

**Snapshot 키**:
```json
"erp": {
    "value": -0.5,
    "tier": "crisis",
    "name": "Equity Risk Premium",
    "cap": 3,
    "unit": "%",
    "layer": 3
}
```

#### 1.1.3 지표 2 — Buffett Indicator (Market Cap / GDP)

**정의**: Wilshire 5000 Total Market Index / GDP × 100

**데이터 소스**:
- **Wilshire 5000**: FRED Series `WILL5000IND` (일별)
- **GDP**: FRED Series `GDP` (분기별, 단위: 십억 달러)

**주의**: GDP 는 분기별 발표. 최신 GDP 는 직전 분기 값을 유지하여 일별 계산에 사용.

```python
def calculate_buffett_indicator():
    """
    Buffett Indicator = Wilshire 5000 / GDP * 100
    
    주의: Wilshire 5000 은 지수값이므로 
    실제 시가총액(조 달러)으로 변환 필요.
    FRED WILL5000IND 는 지수값 (약 40,000~50,000 수준)
    
    대안: FRED 'DDDM01USA156NWDB' (Stock Market Total Value to GDP)
    이 시리즈가 있으면 직접 사용 가능 (연별).
    
    실용적 접근:
    FRED 'WILL5000IND' (일별) / 'GDP' (분기별)
    비율의 절대값보다는 Z-score 또는 percentile 로 해석.
    """
```

**DB 테이블**:

```sql
CREATE TABLE IF NOT EXISTS valuation_buffett (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL UNIQUE,
    wilshire_5000 REAL,
    gdp_billions REAL,
    buffett_pct REAL NOT NULL,   -- Buffett Indicator (%)
    fetched_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_buffett_date ON valuation_buffett(date);
```

**임계값**:

| Zone | 임계 | 의미 |
|---|---|---|
| Normal | < 100% | 적정 또는 저평가 |
| Watch | 100% ~ 140% | 과대평가 시작 |
| Stress | 140% ~ 180% | 과대평가 |
| Crisis | > 180% | 극단적 과대평가 |

Direction: 정방향 (높을수록 stress)

**점수 엔진**:
- Layer: 3
- 가중 (cap): 2pt

**Snapshot 키**:
```json
"buffett": {
    "value": 190.5,
    "tier": "crisis",
    "name": "Buffett Indicator",
    "cap": 2,
    "unit": "%",
    "layer": 3
}
```

**FRED 데이터 구현 시 주의사항**:
- FRED 에서 Wilshire 5000 과 GDP 를 별도로 가져와서 비율 계산
- GDP 는 분기별이므로 `period="10d"` 가 아닌 `limit=5` 정도로 최근 데이터 확보
- Wilshire 5000 은 지수값이므로 GDP 와 직접 나누면 의미 없는 숫자가 나올 수 있음
- **대안**: FRED 에 이미 계산된 시리즈가 있는지 먼저 확인. 예: `DDDM01USA156NWDB` (연별) 또는 유사 시리즈
- 적절한 시리즈가 없으면: Wilshire 5000 을 시가총액으로 변환하는 계수 적용 (약 1.15 ~ 1.2 곱하면 조 달러 근사)
- **TW 에게 FRED 시리즈 확인 결과 먼저 보고 후 구현 방식 결정**

#### 1.1.4 지표 3 — Shiller CAPE (Cyclically Adjusted PE)

**정의**: S&P 500 Price / 10년 평균 실질 EPS

**데이터 소스**:
- **1순위**: FRED 에 CAPE 관련 시리즈가 있는지 확인
- **2순위**: multpl.com 에서 CSV/JSON 다운로드 (https://www.multpl.com/shiller-pe/table/by-month)
- **3순위**: Yale Shiller Dataset (Excel) — http://www.econ.yale.edu/~shiller/data.htm

**갱신 빈도**: 월별 (일별 변동이 의미 없는 지표)

**DB 테이블**:

```sql
CREATE TABLE IF NOT EXISTS valuation_cape (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL UNIQUE,    -- 월 기준 (YYYY-MM-01)
    cape_ratio REAL NOT NULL,
    fetched_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cape_date ON valuation_cape(date);
```

**임계값**:

| Zone | 임계 | 의미 |
|---|---|---|
| Normal | < 20 | 적정 (장기 평균 17 근방) |
| Watch | 20 ~ 28 | 과대평가 시작 |
| Stress | 28 ~ 36 | 과대평가 |
| Crisis | > 36 | 극단적 과대평가 (2000년 닷컴 수준) |

Direction: 정방향 (높을수록 stress)

**점수 엔진**:
- Layer: 3
- 가중 (cap): 2pt

**Snapshot 키**:
```json
"cape": {
    "value": 34.2,
    "tier": "stress",
    "name": "Shiller CAPE",
    "cap": 2,
    "unit": "",
    "layer": 3
}
```

#### 1.1.5 Layer 3 가중치 변경

**변경 전** (Stage 3 완료 시점):

| 지표 | 가중 | 상태 |
|---|---|---|
| VIX | 3pt | 구현 |
| MOVE | 3pt | 구현 |
| SKEW | 3pt | 구현 |
| MOVE/VIX | 2pt | 구현 |
| (미구현 3개) | 4pt | 미구현 |
| **합계** | **11pt (활성)** | spec 15pt |

**변경 후** (Stage 3.5 완료):

| 지표 | 가중 | 상태 |
|---|---|---|
| VIX | 3pt | 기존 |
| MOVE | 3pt | 기존 |
| ERP | 3pt | **신규** |
| SKEW | 3pt | 기존 |
| Buffett | 2pt | **신규** |
| CAPE | 2pt | **신규** |
| MOVE/VIX | 2pt | 기존 |
| (미구현 3개) | 4pt | 미구현 |
| **합계** | **18pt (활성)** | spec 22pt |

**LAYER_SPEC 업데이트 필요**:

```python
# Stage 2.1 에서 정의된 LAYER_SPEC
LAYER_SPEC = {
    '1': {'spec_indicators': 12, 'spec_max_score': 45},
    '2': {'spec_indicators': 8,  'spec_max_score': 30},
    '3': {'spec_indicators': 10, 'spec_max_score': 22},  # 7 → 10, 15 → 22
    'divergence': {'spec_indicators': 5, 'spec_max_score': 10},
}
```

**Coverage 영향**: Layer 3 coverage 가 4/7 (57%) → 7/10 (70%) 로 개선.
**max_achievable 변화**: 70pt → 77pt.
**Normalized score 변화**: 기존 23.5/70=33.6 → 23.5/77=30.5 (valuation 지표 점수 추가 전 기준).

#### 1.1.6 데이터 수집 함수 + 스케줄러

```python
def refresh_erp():
    """
    Equity Risk Premium 일별 수집.
    ERP = (1/PE)*100 - 10Y Treasury Yield
    
    스케줄: 매일 07:30, 22:30 KST (기존 FRED 수집과 비슷한 시각)
    """

def refresh_buffett():
    """
    Buffett Indicator 수집.
    GDP 는 분기별이므로 직전 분기 값 유지.
    Wilshire 5000 은 일별.
    
    스케줄: 매일 07:30 KST
    """

def refresh_cape():
    """
    Shiller CAPE 월별 수집.
    월 1회 갱신이면 충분.
    
    스케줄: 매월 1일 08:00 KST (또는 매일 체크하되 변경 시만 저장)
    """
```

**Backfill 패턴**: LQD/HYG 와 같은 패턴 적용 필수.
```python
existing = conn.execute("SELECT COUNT(*) FROM valuation_erp").fetchone()[0]
if existing == 0:
    # 3년치 backfill
else:
    # 증분 갱신
```

#### 1.1.7 `_compute_tmrs()` 에 3개 지표 추가

기존 `_compute_tmrs()` 함수의 Layer 3 섹션에 3개 지표의 tier 판정 + 점수 계산 + snapshot 추가.

기존 VIX/MOVE/SKEW 패턴을 그대로 따름.

#### 1.1.8 Valuation Composite 계산 (Regime Map 용)

```python
def calculate_valuation_composite(snapshot: dict) -> dict:
    """
    3개 Valuation 지표의 가중 평균 normalized score.
    Regime Map 의 Y축으로 사용.
    
    Returns:
        {
            'composite': float (0~1, 높을수록 고평가),
            'individual': {
                'erp': {'value': ..., 'norm': ..., 'tier': ...},
                'buffett': {...},
                'cape': {...},
            },
            'regime_label': 'low' | 'high'
        }
    """
    VALUATION_INDICATORS = {
        'erp': {'weight': 3, 'crisis': 0.0, 'normal': 3.0, 'direction': 'inverse'},
        'buffett': {'weight': 2, 'crisis': 180, 'normal': 100, 'direction': 'normal'},
        'cape': {'weight': 2, 'crisis': 36, 'normal': 20, 'direction': 'normal'},
    }
    
    weighted_sum = 0.0
    total_weight = 0
    individual = {}
    
    for key, config in VALUATION_INDICATORS.items():
        indicator = snapshot.get(key, {})
        value = indicator.get('value')
        if value is None:
            continue
        
        # 0~1 정규화 (0=normal, 1=crisis)
        if config['direction'] == 'inverse':
            norm = max(0, min(1, (config['normal'] - value) / (config['normal'] - config['crisis'])))
        else:
            norm = max(0, min(1, (value - config['normal']) / (config['crisis'] - config['normal'])))
        
        individual[key] = {
            'value': value,
            'norm': round(norm, 3),
            'tier': indicator.get('tier', 'normal'),
        }
        
        weighted_sum += norm * config['weight']
        total_weight += config['weight']
    
    composite = weighted_sum / total_weight if total_weight > 0 else 0.0
    
    return {
        'composite': round(composite, 3),
        'individual': individual,
        'regime_label': 'high' if composite > 0.5 else 'low',
    }
```

#### 1.1.9 Signal Desk 상세 카드에 Valuation 지표 추가

ERP, Buffett, CAPE 3개 지표에 대해 기존 패턴과 동일한 상세 카드 구현:
- 현재값 + 전일 + 7일전
- 임계 시각화 바
- Layer/가중/기여 표시
- 해석 텍스트

```python
INDICATOR_INTERPRETATIONS.update({
    'erp': "Equity Risk Premium. 주식 vs 국채 초과수익. 낮을수록 주식이 상대적으로 비쌈.",
    'buffett': "Buffett Indicator. 전체 시장 시가총액 / GDP. 100% 초과 시 과대평가.",
    'cape': "Shiller CAPE. 10년 평균 실질이익 기준 PE. 장기 평균 17, 현재 30+ 수준.",
})
```

#### 1.1.10 ADR

`docs/decisions/2026-04-24-stage3-5-valuation-indicators.md`

내용:
- 3개 지표 선택 근거 (ERP: 금리 반영, Buffett: 거시 레벨, CAPE: 역사적 맥락)
- 거부된 지표 (P/S: CAPE 와 redundancy, Discount Rate PE: ERP 와 중복)
- Earnings Quality 보류 사유 (무료 데이터 부재)
- Layer 3 가중치 변경 (11pt → 18pt)
- LAYER_SPEC 업데이트 (spec 7→10, max 15→22)
- 사상적 의미: "잠재 낙폭" 측정으로 Inverse Turkey 보완

#### 1.1.11 PR #14 체크리스트

- [ ] ERP 데이터 수집 함수 + DB 테이블
- [ ] Buffett Indicator 수집 함수 + DB 테이블
- [ ] CAPE 수집 함수 + DB 테이블
- [ ] 3개 지표 backfill (existing==0 패턴)
- [ ] `_compute_tmrs()` 에 3개 지표 tier + 점수 추가
- [ ] snapshot 에 erp/buffett/cape 키 추가
- [ ] LAYER_SPEC 업데이트 (Layer 3: spec 10, max 22)
- [ ] `calculate_valuation_composite()` 함수 (Regime Map 용)
- [ ] 스케줄러 등록 (ERP/Buffett: 일별, CAPE: 월별 또는 일별 체크)
- [ ] `_startup_full_refresh()` 에 초기 수집 추가
- [ ] Signal Desk 상세 카드 (3개 지표)
- [ ] INDICATOR_INTERPRETATIONS 추가 (3개)
- [ ] INDICATOR_THRESHOLDS 추가 (3개)
- [ ] `/signal-desk` 응답에 `valuation_composite` 필드 추가
- [ ] `sync_from_github.py` FILES 업데이트 (필요 시)
- [ ] ADR 작성
- [ ] **데이터 소스 확보 시 TW 에게 먼저 보고** (특히 Buffett Indicator 의 FRED 시리즈 + CAPE 소스)

---

### 1.2 PR #15 — Fragility Regime Map 위젯 + UI 통합

#### 1.2.1 작업 범위

Signal Desk 우측 카드의 하단을 좌우 분할하여 Inverse Turkey (좌) + Regime Map (우) 배치.

#### 1.2.2 Regime Map 4사분면 정의

```
         │
 High    │  Bubble      │  CRASH RISK
Valuation│  Expansion   │  ZONE ★
         │              │
─────────┼──────────────┼─────────────
         │              │
  Low    │  Strong      │  Value
Valuation│  Long Entry  │  Trap
         │              │
         └──────────────┴─────────────
          Easy Liquidity  Tight Liquidity
```

**X축 — Liquidity Tightness**:
- Layer 1 Normalized Score 사용: `l1_score / 45`
- 0 (Easy) ~ 1 (Tight)
- 중간선: 0.5

**Y축 — Valuation Level**:
- `valuation_composite` 사용 (Section 1.1.8 에서 계산)
- 0 (Low) ~ 1 (High)
- 중간선: 0.5

**현재 위치 ★ 표시**:
- X = 20.6/45 = 0.458 (중간선 바로 아래)
- Y = valuation composite (PR #14 구현 후 계산)

**4사분면 라벨 + 색상**:

| 사분면 | 라벨 | 색상 | 의미 |
|---|---|---|---|
| 좌상 | Bubble Expansion | 🟡 노랑 | 고평가 + 유동성 풍부 = 버블 확장 |
| **우상** | **Crash Risk Zone** | 🔴 빨강 | 고평가 + 유동성 경색 = **가장 위험** |
| 좌하 | Strong Long Entry | 🟢 녹색 | 저평가 + 유동성 풍부 = 매수 기회 |
| 우하 | Value Trap | 🟠 주황 | 저평가 + 유동성 경색 = 함정 |

#### 1.2.3 UI 레이아웃 — 우측 카드 하단 분할

**현재** (PR #12 이후):

```html
<div class="right-card">
    <div class="lds-panel"><!-- LDS 상단 --></div>
    <div class="it-panel"><!-- Inverse Turkey 하단 전체 --></div>
</div>
```

**변경 후**:

```html
<div class="right-card">
    <!-- 상단 55%: LDS -->
    <div class="lds-panel" style="flex: 0 0 55%;">
        <!-- 기존 LDS 코드 그대로 -->
    </div>
    
    <!-- 하단 45%: IT + Regime 좌우 분할 -->
    <div class="bottom-panels" style="flex: 0 0 45%; display: flex;">
        <!-- 좌 50%: Inverse Turkey -->
        <div class="it-panel" style="flex: 1;">
            <h4>INVERSE TURKEY</h4>
            <div>🐻 미감지</div>
            <div class="it-metrics">l12: 0.229 / l3: 0.107</div>
        </div>
        
        <!-- 우 50%: Regime Map -->
        <div class="regime-panel" style="flex: 1;">
            <h4>FRAGILITY REGIME</h4>
            <div class="regime-map">
                <!-- SVG 또는 CSS 기반 4사분면 -->
            </div>
            <div class="regime-label">★ Crash Risk Zone</div>
        </div>
    </div>
</div>
```

#### 1.2.4 Regime Map 렌더링 — CSS/SVG 미니맵

```html
<!-- 순수 CSS 기반 4사분면 미니맵 -->
<div class="regime-map" style="position: relative; width: 100%; height: 120px;">
    <!-- 4사분면 배경 -->
    <div style="position:absolute; top:0; left:0; width:50%; height:50%; 
                background: rgba(234,179,8,0.15);">
        <!-- 좌상: Bubble -->
    </div>
    <div style="position:absolute; top:0; right:0; width:50%; height:50%; 
                background: rgba(239,68,68,0.15);">
        <!-- 우상: Crash Risk -->
    </div>
    <div style="position:absolute; bottom:0; left:0; width:50%; height:50%; 
                background: rgba(34,197,94,0.15);">
        <!-- 좌하: Strong Long -->
    </div>
    <div style="position:absolute; bottom:0; right:0; width:50%; height:50%; 
                background: rgba(249,115,22,0.15);">
        <!-- 우하: Value Trap -->
    </div>
    
    <!-- 축 라벨 -->
    <div style="position:absolute; bottom:-15px; left:5px; font-size:9px;">Easy</div>
    <div style="position:absolute; bottom:-15px; right:5px; font-size:9px;">Tight</div>
    <div style="position:absolute; top:2px; left:-20px; font-size:9px; 
                transform:rotate(-90deg);">High</div>
    <div style="position:absolute; bottom:2px; left:-20px; font-size:9px; 
                transform:rotate(-90deg);">Low</div>
    
    <!-- 현재 위치 ★ (JS 에서 동적 배치) -->
    <div id="regime-dot" style="position:absolute; font-size:16px; 
                transform:translate(-50%,-50%);">★</div>
</div>
```

JavaScript 에서 동적 배치:

```javascript
function updateRegimeMap(l1_norm, val_composite) {
    const dot = document.getElementById('regime-dot');
    if (!dot) return;
    
    // X = l1_norm (0=left=easy, 1=right=tight)
    // Y = val_composite (0=bottom=low, 1=top=high)
    const x = Math.max(0, Math.min(1, l1_norm)) * 100;
    const y = (1 - Math.max(0, Math.min(1, val_composite))) * 100;
    
    dot.style.left = x + '%';
    dot.style.top = y + '%';
    
    // 사분면 라벨 업데이트
    const label = document.getElementById('regime-label');
    if (l1_norm > 0.5 && val_composite > 0.5) {
        label.textContent = '★ Crash Risk Zone';
        label.style.color = '#ef4444';
    } else if (l1_norm <= 0.5 && val_composite > 0.5) {
        label.textContent = 'Bubble Expansion';
        label.style.color = '#eab308';
    } else if (l1_norm <= 0.5 && val_composite <= 0.5) {
        label.textContent = 'Strong Long Entry';
        label.style.color = '#22c55e';
    } else {
        label.textContent = 'Value Trap';
        label.style.color = '#f97316';
    }
}
```

#### 1.2.5 `/signal-desk` API 응답 확장

기존 응답에 Regime Map 데이터 추가:

```python
@app.route("/signal-desk")
def signal_desk_data():
    # ... 기존 TMRS + LDS 계산
    
    val_composite = calculate_valuation_composite(snapshot)
    l1_norm = l1_score / 45
    
    # Regime 판정
    regime = {
        'l1_norm': round(l1_norm, 3),
        'val_composite': val_composite['composite'],
        'quadrant': _determine_quadrant(l1_norm, val_composite['composite']),
        'individual': val_composite['individual'],
    }
    
    return jsonify({
        # ... 기존 필드
        'valuation': val_composite,  # 신규
        'regime': regime,            # 신규
    })
```

#### 1.2.6 ADR

`docs/decisions/2026-04-24-stage3-5-fragility-regime-map.md`

내용:
- 4사분면 설계 근거
- X축 (Layer 1 normalized) Y축 (Valuation composite) 선택 이유
- UI 레이아웃 (카드 하단 좌우 분할)
- 역사적 검증: 2000, 2007, 2021 — Crash Risk Zone 에 해당
- Inverse Turkey 와의 관계 (보완적)

#### 1.2.7 PR #15 체크리스트

- [ ] Signal Desk 우측 카드 하단 좌우 분할 (IT + Regime)
- [ ] Regime Map 4사분면 CSS/SVG 미니맵
- [ ] 현재 위치 ★ 동적 배치 (JS)
- [ ] 사분면 라벨 + 색상 동적 변경
- [ ] `/signal-desk` 에 `valuation` + `regime` 데이터 추가
- [ ] ADR 작성
- [ ] 기존 LDS 패널 영향 없음 확인
- [ ] 기존 Inverse Turkey 로직 변경 없음 (UI 위치만 조정)

---

## 2. Stage 3.5 완료 조건

### 2.1 체크리스트

- [ ] PR #14 — 3개 Valuation 지표 + Layer 3 점수 통합
- [ ] PR #15 — Regime Map 위젯 + UI 분할
- [ ] 모든 PR GitHub main merge 완료
- [ ] Replit sync + 앱 재시작 후 정상 작동

### 2.2 완료 후 예상 상태

```
Signal Desk:
┌─────────────────────┐  ┌─────────────────────────────────┐
│  TMRS SCORE          │  │  LINDY DISTANCE       🟢 0.54   │
│                      │  │  CP Sprd ███░░░ 0.30            │
│  30.5  주의          │  │  S-B OAS ████░░ 0.49            │
│  원점수 23.5/77pt    │  │  HY OAS  █████░ 0.59            │
│  Coverage 61%        │  │  HYG Day ██████ 0.91            │
│                      │  ├──────────────┬──────────────────┤
│  Layer 1: 20.6/45    │  │ INV. TURKEY  │ FRAGILITY REGIME │
│  Layer 2: 0.0/30     │  │ 🐻 미감지    │ [4사분면 미니맵]  │
│  Layer 3: 1.6/22     │  │ l12: 0.229   │ ★ Crash Risk    │
│  Div:     1.2/10     │  │ l3:  0.073   │                  │
└─────────────────────┘  └──────────────┴──────────────────┘

Layer 3 (22pt spec):
  기존: VIX, MOVE, SKEW, MOVE/VIX (11pt)
  신규: ERP, Buffett, CAPE (7pt)
  합계: 18pt 활성 / 22pt spec

Coverage: 55.6% → ~61% (개선)
```

### 2.3 TW 검토 시 공유 사항

각 PR 완료 시:
1. 변경 파일 리스트
2. 데이터 소스 확보 결과 (특히 Buffett/CAPE)
3. 현재 Valuation 지표 값 + Tier
4. Regime Map 현재 위치 (어느 사분면)
5. TMRS 점수 변화 (Layer 3 score, total, normalized)
6. Signal Desk 스크린샷
7. 발견 이슈

---

## 3. 작업 원칙 재확인

### 3.1 반드시 지킬 것

1. 새 feature branch (`claude/stage3-5-valuation`, `claude/stage3-5-regime-map`)
2. PR base = main
3. ADR 포함
4. TW 검토 대기
5. 기존 Layer 1/2 로직 변경 없음
6. 기존 LDS 로직 변경 없음 (Regime Map 은 별도 독립 계산)
7. Inverse Turkey 로직 변경 없음 (UI 위치 조정만)
8. **데이터 소스 확보 시 TW 에게 먼저 보고** (FRED 시리즈 ID 등)

### 3.2 피할 것

1. 이전 feature branch 에 추가 커밋
2. `sync_from_github.py` BRANCH 변수 변경
3. `score_version`, `threshold_table_version` 변경
4. snapshot 기존 키 변경
5. Layer 1/2 가중치 변경
6. CAPE 데이터 소스를 TW 확인 없이 스크래핑 구현

### 3.3 의문 발생 시

다음 시 즉시 TW 문의:
- FRED 에서 적절한 Buffett Indicator 시리즈를 못 찾을 때
- CAPE 데이터 소스 접근 문제
- ERP 의 S&P 500 PE 데이터가 yfinance 에서 불안정할 때
- Regime Map 의 X/Y 축 정규화 방식에 이견
- Layer 3 spec 변경이 Coverage Ratio 에 미치는 영향

---

## 4. 착수 메시지 (TW → Claude Code)

> Stage 3 완료 후 Stage 3.5 를 시작한다.
>
> 먼저 `Stage3_5_Instructions.md` 를 전체 읽어줘. 특히 **Section 0.5** 확인 — Stage 3 에서 완료된 LDS 구현, HY OAS 임계 복원, MOVE/SKEW backfill 수정 등을 알아야 해.
>
> 읽은 후 다음을 보고해줘:
>
> 1. Section 0.5 핵심 변경사항 이해도 요약 (3줄)
> 2. 3개 Valuation 지표의 데이터 소스 확보 가능성 (FRED 시리즈 확인 결과)
> 3. PR #14/#15 중 어느 것부터 시작할지 제안
> 4. 예상 기술 이슈 (있다면)
>
> **특히 중요**:
> - ERP 의 S&P 500 PE 데이터를 yfinance 에서 가져올 수 있는지 확인
> - Buffett Indicator 를 위한 FRED 시리즈 (Wilshire 5000 + GDP) 확인
> - CAPE 를 위한 무료 데이터 소스 확인
> - **데이터 소스 확인 결과를 먼저 보고해줘. 구현 전에 TW 가 검토할거야.**
>
> **작업 원칙**:
> - 새 feature branch 2개 (`claude/stage3-5-valuation`, `claude/stage3-5-regime-map`)
> - PR base = main
> - 기존 LDS, Inverse Turkey, Layer 1/2 로직 변경 없음
> - 데이터 소스 확보 시 TW 에게 먼저 보고
> - FRED Series ID 는 반드시 FRED 웹사이트에서 직접 확인 (Single-B OAS 사례 교훈)
>
> Stage 3.5 시작 준비해줘.

---

**끝 (End of Stage 3.5 Instructions)**

*Financial Tracker — v1.0.1 Stage 3.5 Instructions*
*작성: 2026-04-24 | TW × Claude Opus 4.6*
