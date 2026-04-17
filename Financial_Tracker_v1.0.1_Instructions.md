# Financial Tracker — v1.0.1 Code Alignment Instructions

> **Claude Code 작업 지시서**
> 본 문서는 현재 구현된 Financial Tracker 를 Scoring Logic v1.0 사상과 정렬하기 위한 3단계 정비 작업 지시서입니다.

| 항목 | 내용 |
|---|---|
| **Target Version** | v1.0.1 (Patch level — 사상 변경 없음, 정렬만) |
| **Baseline** | `docs/scoring/scoring_logic_v1.0.md` |
| **Threshold Table 버전** | v1.2026-04 → **v1.2026-04-01** (패치 버전으로 bump) |
| **작업 기준일** | 2026-04-14 |
| **작성자** | TW × Claude (Opus 4.6)  |

---

## 0. 개요 및 작업 원칙

### 0.1 배경

Claude Code 가 그동안 Financial Tracker 앱 개발을 진행하면서 TMRS 엔진을 프로덕션 수준까지 완성했습니다. 그 과정에서 v1.0 문서와 다르게 결정한 사항 6개가 발생했고, Layer 2 지표 다수가 미구현 상태이며, ERS 엔진 전체가 아직 착수되지 않은 상태입니다.

본 지시서는 이 **구현 gap** 을 3단계로 나눠 메우는 작업입니다.

### 0.2 작업 원칙

1. **Breaking change 는 명시적으로 표기** — 기존 DB 이력 데이터와의 호환성 반드시 고려
2. **각 Stage 는 별도 PR** — Stage 내부에서도 가능하면 작은 단위로 분할
3. **각 Stage 완료 후 TW님과 검토** — 다음 Stage 착수 전 반드시 확인
4. **ADR (Architecture Decision Record) 작성** — 각 Stage 별 의사결정 기록을 `docs/decisions/` 에 남김
5. **threshold_table_version 업데이트** — 패치 버전으로 bump (`v1.2026-04` → `v1.2026-04-01`)

### 0.3 작업 순서

```
[착수 전] 질문 사항 4개 답변 제공 (Section 6)
     ↓
Stage 1 — Naming & Threshold Sanity (영향 작음)
     ↓
  TW 검토
     ↓
Stage 2 — Layer 2 충실화 (가장 중요, 영향 큼)
     ↓
  TW 검토
     ↓
Stage 3 — ERS v0 착수 (새 기능)
     ↓
  TW 검토
     ↓
[v1.0.1 Delta 문서 작성 — 별도 작업]
```

---

## 1. Stage 1 — Naming & Threshold Sanity

**목표**: 명칭 오류, 임계값 체계 정렬, 지표 이원화. 영향 범위 작음.

### 1.1 FRA-OIS → SOFR Term Premium 명칭 정리

#### 문제
현재 "FRA-OIS" 라는 이름으로 `SOFR90DAYAVG - SOFR` 값이 저장되고 있습니다. 실제 측정 대상과 이름이 다르며, v1.0 문서의 FRA-OIS 임계값 (< 25bp / 25-40bp / 40-50bp / > 50bp) 은 *진짜 FRA-OIS* 기준이므로 현재 지표에 그대로 적용하면 **false signal 가능성** 이 있습니다.

#### 작업 내용

**A. 지표 ID/이름 변경**
- 지표 ID: `fra_ois` → `sofr_term_premium`
- 표시명: "FRA-OIS Spread" → "SOFR Term Premium (FRA-OIS proxy)"
- 모든 UI/로그/알람 표시 일관되게 수정

**B. DB 마이그레이션**
- Column 이름 변경 script 작성
- 기존 이력 데이터 보존 (단순 rename)
- 마이그레이션 스크립트: `scripts/migrations/0001_rename_fra_ois.py`

**C. 임계값 재calibration**
- 최근 6개월 (최소 126 거래일) SOFR Term Premium 분포 계산
- 분포 통계 출력: min / 25p / 50p / 75p / 90p / 95p / max
- **TW님 결정 대기**: 출력된 분포를 보고 새 임계값 결정 (percentile 기반 권장)
- 임계값 결정 전까지는 기존 임계값을 `legacy_threshold` 로 유지하되, 점수 산출 시 *warning flag* 발생

**D. ADR 작성**
`docs/decisions/2026-04-XX-stage1-sofr-term-premium-renaming.md`

### 1.2 MOVE Index 임계 Percentile 병기

#### 문제
Claude Code 가 결정한 MOVE 임계 (<80 / 80-100 / 100-150 / 150+) 는 2025년 이후 금리 변동성 상승을 반영한 합리적 조정이지만, 근거가 "현재 regime 관찰" 뿐입니다. Regime 변화 시 자동 보정이 안 됩니다.

#### 작업 내용

**A. 절대값 임계 유지 + Percentile 임계 병기**
- 절대값 임계: `MOVE_THRESHOLDS_ABS` = {normal: 80, watch: 100, stress: 150}
- Percentile 임계: `MOVE_THRESHOLDS_PCT` = {normal: 50p, watch: 75p, stress: 90p, crisis: 95p}
- Lookback: 1년 (252 거래일)

**B. 점수 산출 로직**
```python
def get_move_score(current_value, historical_series, weight):
    """
    절대값과 Percentile 두 임계 중 더 보수적(높은 점수) 선택
    """
    # 절대값 기반 점수
    score_abs = indicator_score(
        current_value,
        MOVE_THRESHOLDS_ABS,
        weight,
        direction='normal',
        mode='interpolated'
    )
    
    # Percentile 기반 점수
    pct_rank = (historical_series < current_value).mean()
    score_pct = percentile_to_score(pct_rank, MOVE_THRESHOLDS_PCT, weight)
    
    # 더 보수적(높은 점수) 선택
    return max(score_abs, score_pct)
```

**C. UI 표시**
- MOVE 위젯에 두 임계 모두 표시
- 예: "MOVE 125 = 절대 Watch(100-150) / Percentile Stress(90p 초과) → **Stress 로 평가**"
- 두 임계가 일치하지 않을 때 명확히 표시

**D. ADR 작성**
`docs/decisions/2026-04-XX-stage1-move-percentile-overlay.md`

### 1.3 RRP 지표 이원화

#### 문제
Claude Code 가 RRP 임계를 절대값 기준 (<$100B / <$50B / <$10B) 으로 변경했는데, v1.0 문서 카테고리 3.4.3 의 RRP 임계는 *주간 변화율 기준* (±$30B / -$50B 이하 / -$100B 이하 / -$150B 이하) 이었습니다.

둘 다 유효한 지표이므로 **두 개의 독립 지표로 분리** 하는 것이 올바른 해결입니다.

#### 작업 내용

**A. 지표 분리**
- `rrp_level` (신규): 절대 잔액 기준
  - 임계: Claude Code 가 결정한 <$100B / <$50B / <$10B 유지
  - 사유: QT 완료 후 $100B 이하가 새 정상
- `rrp_weekly_change` (신규): 주간 변화율 기준
  - 임계: v1.0 원문 ±$30B / -$50B / -$100B / -$150B 유지
  - 사유: 추세 감지 — QT/QE regime 무관 유효

**B. 가중치 분할**
- 기존 RRP 지표 가중치가 3점이었다면:
  - `rrp_level`: 2점
  - `rrp_weekly_change`: 1점
- 둘 모두 Layer 1 (Deep / Funding) 에 할당

**C. DB 스키마**
- 기존 `rrp_history` 테이블에 `weekly_change_pct` column 추가
- 신규 지표 ID 각각 등록

**D. ADR 작성**
`docs/decisions/2026-04-XX-stage1-rrp-indicator-split.md`

### 1.4 Stage 1 완료 조건

- [ ] 1.1 A–D 완료
- [ ] 1.2 A–D 완료
- [ ] 1.3 A–D 완료
- [ ] `threshold_table_version` = `v1.2026-04-01` bump
- [ ] DB 마이그레이션 성공, 기존 이력 손실 없음
- [ ] TMRS 계산 결과 before/after 비교 output 생성
- [ ] TW님 검토 요청 — 다음 항목 공유
  - 변경된 파일 리스트
  - DB 마이그레이션 결과
  - SOFR Term Premium 분포 통계 (1.1 C 결과)
  - TMRS 출력 예시 (v1.0 vs v1.0.1)
  - 발견한 이슈/이견

---

## 2. Stage 2 — Layer 2 충실화 (가장 중요)

**목표**: Layer 2 (Middle / Credit) 의 미구현 지표 추가, 특히 Single-B OAS.

### 2.1 배경 — 왜 가장 중요한가

현재 Layer 2 는 스펙 8개 지표 중 2개만 활성화되어 있어 **실질 max score 가 약 10/30 (33%)** 입니다. 특히 v1.0 문서에서 Layer 2 최대 가중 7점을 할당한 **Single-B OAS 가 빠진 상태** 입니다.

이 상태에서는 TMRS 가 v1.0 스펙대로 작동하지 않으며, "TMRS 65 = Red Alert" 같은 해석이 잘못된 신호를 줄 수 있습니다.

### 2.2 Single-B OAS 추가 (최우선)

#### 작업 내용

**A. 데이터 수집**
- FRED series ID: `BAMLH0A2HYBEY` (BofA ICE Single-B US High Yield OAS)
- 갱신 빈도: 일별 (1일 lag 허용)
- Historical backfill: 최소 5년 (2021-01-01 이후)
- DB table: `single_b_oas_history`

**B. 임계값 (v1.0 카테고리 3.5.1)**
| Zone | 임계 | 정규화 점수 |
|---|---|---|
| Normal | < 350bp | 0.00 |
| Watch | 350–450bp | 0.40 |
| Stress | 450–600bp | 0.75 |
| Crisis | > 600bp | 1.00 |

**C. 점수 엔진 연동**
- Layer 2 가중 **7점** 할당 (Layer 2 내 최대)
- Solo Cap: 7점
- Direction: `normal`
- Interpolated scoring 적용

**D. UI 추가**
- Credit 탭에 Single-B OAS 위젯 추가
- 차트: 최근 1년 시계열 + 임계 구간 overlay
- 현재 값 + Zone + 기여 점수 표시

### 2.3 HYG ETF 일간 변화율 추가

#### 작업 내용

**A. 데이터 수집**
- yfinance ticker: `HYG`
- 지표 1: `hyg_daily_change_pct` — 일간 변화율
- 지표 2: `hyg_5day_cumulative_change_pct` — 5일 누적 변화 (보조)
- Historical backfill: 최소 3년
- DB table: `hyg_price_history` (이미 있으면 재사용)

**B. 임계값 (v1.0 카테고리 3.5.2)**

`hyg_daily_change_pct`:
| Zone | 임계 |
|---|---|
| Normal | > -0.3% |
| Watch | -0.3% ~ -0.7% |
| Stress | -0.7% ~ -1.5% |
| Crisis | < -1.5% |

`hyg_5day_cumulative_change_pct`:
| Zone | 임계 |
|---|---|
| Normal | > -1% |
| Watch | -1% ~ -2.5% |
| Stress | -2.5% ~ -5% |
| Crisis | < -5% |

**C. 가중치**
- `hyg_daily_change_pct`: Layer 2 가중 4점
- `hyg_5day_cumulative_change_pct`: Layer 2 가중 3점
- Solo Cap 각각 지표 가중과 동일
- Direction: `inverse` (값이 작을수록 stress — 음의 값이 stress)

### 2.4 Layer 2 가중치 재분배

#### 현행 v1.0 스펙 vs v1.0.1 권장

| 지표 | v1.0 가중 | v1.0.1 상태 | v1.0.1 가중 |
|---|---|---|---|
| Single-B OAS | 7 | **신규 추가** | 7 |
| HY OAS | 5 | 기존 유지 | 5 |
| IG OAS | 3 | **신규 추가** (2.5 참조) | 3 |
| HYG daily | 4 | **신규 추가** | 4 |
| HYG 5day | 3 | **신규 추가** | 3 |
| LQD daily | 2 | **신규 추가** (2.5 참조) | 2 |
| Korea CDS | 4 | 제외 (데이터 소스 부재) | **0 (optional)** |
| GSIB CDS | 2 | 데이터 가용성 조사 필요 | 2 (수동) or 0 |
| **합계 (Korea CDS 제외)** | **26** | | **26** |
| **합계 (Korea CDS 포함)** | **30** | | **30** |

#### Korea CDS 처리 결정 — TW 권장안

**선택한 방안**: "Korea CDS optional 유지, Layer 2 max 26점"

**근거**:
1. 임의로 다른 지표 가중치를 올려 30점 맞추면 v1.0 사상 훼손
2. Korea CDS 데이터 조달 시 자연스럽게 30점 복원 가능
3. TMRS Total 이 100 → 96 으로 감소하지만, coverage ratio 표시로 해석 보완

**결과**:
- TMRS Total max score: **100 → 96** (잠정)
- 해석 구간(Calm/Watch/Yellow/Red/Crisis) 재calibration 필요
  - v1.0: 0-25 / 26-40 / 41-55 / 56-70 / 71-85 / 86-100
  - v1.0.1 잠정: 0-24 / 25-38 / 39-53 / 54-67 / 68-82 / 83-96
  - 또는 **normalized_score = raw / max * 100** 로 변환 후 기존 구간 적용 (권장)

**구현 권장**: `normalized_score` 방식으로 기존 해석 구간 유지. UI 에는 raw + normalized 모두 표시.

### 2.5 Korea CDS 대체 데이터 소스 조사

#### 배경
Claude Code 가 Bloomberg/Refinitiv 유료 전용으로 판단했으나, **무료로 일별 수준은 확보 가능** 할 수 있습니다. 다음을 조사해서 결과 보고.

#### 조사 대상

| 소스 | URL | 예상 정밀도 |
|---|---|---|
| KRX 공시 | https://data.krx.co.kr | 중 |
| 한국은행 ECOS | https://ecos.bok.or.kr | 중 |
| Investing.com | https://www.investing.com/rates-bonds/south-korea-cds-5-years | 중 (스크래핑) |
| CMA (Credit Market Analysis) | 유료 | 고 |

**작업**:
- 각 소스의 일별 업데이트 가능성, API/스크래핑 안정성, 가격 데이터 정밀도 조사
- 조사 결과 `docs/research/korea-cds-data-sources.md` 작성
- Stage 2 에서는 **조사만**, 실제 통합은 후속 작업

### 2.6 IG OAS, LQD ETF 구현 가능성 확인

#### 작업 내용

**IG OAS**
- FRED series ID: `BAMLC0A0CM` (BofA ICE US Corporate Master OAS)
- 데이터 가용성 확인
- 구현 가능하면 Layer 2 가중 3점 추가

**LQD ETF**
- yfinance ticker: `LQD`
- 일간 변화율 지표 추가
- 임계값 (v1.0):
  - Normal: > -0.5%
  - Watch: -0.5% ~ -1%
  - Stress: -1% ~ -2%
  - Crisis: < -2%
- Layer 2 가중 2점

### 2.7 Coverage Ratio 출력 강화

#### 작업 내용

**A. TMRSOutput 데이터 구조 확장**

```python
@dataclass
class TMRSOutput:
    # ===== 기존 필드 =====
    total_score: float
    grade: str
    layer1_score: float
    layer2_score: float
    layer3_score: float
    divergence_score: float
    # ... (기타 기존 필드)
    
    # ===== 신규 필드 (v1.0.1) =====
    
    # Layer 별 active / spec 지표 수
    layer1_active_indicators: int
    layer1_spec_indicators: int
    layer1_coverage: float          # active / spec
    
    layer2_active_indicators: int
    layer2_spec_indicators: int
    layer2_coverage: float
    
    layer3_active_indicators: int
    layer3_spec_indicators: int
    layer3_coverage: float
    
    divergence_active_signals: int
    divergence_spec_signals: int
    divergence_coverage: float
    
    # 전체 커버리지 (가중 평균)
    overall_coverage: float
    
    # 점수 정규화 (v1.0.1 핵심)
    raw_score: float                # 실제 합산 (0-96 등)
    max_achievable_score: float     # 현재 활성 지표 기준 최대 (예: 96)
    normalized_score: float         # raw / max * 100
    
    # 플래그
    is_partial_implementation: bool  # overall_coverage < 0.80 이면 True
    
    # 메타
    threshold_table_version: str    # "v1.2026-04-01"
```

**B. UI 경고 표시**

`is_partial_implementation == True` 이면:
- Signal Desk 탭 상단에 warning badge: "⚠️ 부분 구현 상태 (coverage 65%)"
- 점수 해석 툴팁에 경고 추가: *"현재 지표 커버리지 65%. 완전 구현 대비 점수 해석에 주의 필요."*

**C. 점수 표시 방식**

- 메인 TMRS: `normalized_score` 표시 (기존 해석 구간 그대로 적용 가능)
- 부가 표시: `raw_score / max_achievable_score` (예: "62 / 96")
- 코드/API 출력에는 모든 필드 포함

### 2.8 Stage 2 완료 조건

- [ ] 2.2 Single-B OAS 완전 구현 (데이터+점수+UI)
- [ ] 2.3 HYG daily + 5day 구현
- [ ] 2.4 Layer 2 가중치 재분배 확정
- [ ] 2.5 Korea CDS 소스 조사 완료 (문서 작성)
- [ ] 2.6 IG OAS, LQD 구현 (가능 시)
- [ ] 2.7 Coverage Ratio 필드/UI 반영
- [ ] `threshold_table_version` = `v1.2026-04-01` (Stage 1 과 동일)
- [ ] TW님 검토 요청 — 다음 항목 공유
  - 변경된 파일 리스트
  - 새 Layer 2 지표 historical backfill 결과
  - Coverage ratio 변화 (before / after)
  - TMRS 출력 예시 (Single-B OAS 추가 전후 비교)
  - normalize_score vs raw_score 양쪽 비교
  - Korea CDS 조사 결과 문서
  - 발견한 이슈/이견

---

## 3. Stage 3 — ERS v0 착수

**목표**: Event Risk Score 엔진의 v0 구현 — Tier 1 (스케줄 이벤트) 만 구현, Tier 2·3 는 추후.

### 3.1 배경

v1.0 문서 카테고리 5 의 핵심 가치는 **TMRS ↔ ERS Divergence 4사분면** 측정입니다. 현재 ERS 가 없어 이 가치를 활용할 수 없는 상태입니다.

v1.0 카테고리 5.10 의 점진 구현 가이드에 따라 **v0 (Tier 1 만)** 부터 착수합니다.

### 3.2 ERS Tier 1 — Scheduled Events

#### 작업 내용

**A. 경제지표 캘린더 연동**

Section 6 의 질문 3 (이벤트 캘린더 API 선택지) 답변 후 결정. 후보:
- TradingEconomics API (무료 tier 월 500 호출)
- FRED Economic Calendar
- Investing.com 스크래핑
- 수동 CSV 업로드 (v0 fallback)

**B. 이벤트 magnitude 사전 정의**

v1.0 카테고리 5.4.1 의 20+ 이벤트 표 전체 구현. 예시:

```python
EVENT_MAGNITUDES = {
    # magnitude 10
    'CPI': 10,
    'Core CPI': 10,
    'FOMC Decision': 10,
    
    # magnitude 9
    'Powell Press Conference': 9,
    'PCE': 9,
    
    # magnitude 8
    'NFP': 8,
    'Unemployment Rate': 8,
    
    # magnitude 6
    'PPI': 6,
    'GDP': 6,
    
    # magnitude 5
    'ISM Manufacturing': 5,
    'ISM Services': 5,
    'Retail Sales': 5,
    'Treasury 10Y Auction': 5,
    'Treasury 30Y Auction': 5,
    
    # magnitude 4
    'Treasury 8-week Bill Auction': 4,
    'Fed Speaker': 4,
    'JOLTS': 4,
    
    # magnitude 3
    'Initial Jobless Claims': 3,
    'Consumer Confidence': 3,
    'Michigan Sentiment': 3,
    'Beige Book': 3,
    
    # magnitude 2
    'Industrial Production': 2,
    'Housing Starts': 2,
}
```

**C. D-counter Decay 로직**

v1.0 카테고리 5.4.2 산식 그대로:

```python
def event_proximity_score(magnitude, days_until):
    """
    이벤트 접근도 점수
    """
    if days_until <= 1:    return magnitude * 1.0
    elif days_until <= 3:  return magnitude * 0.7
    elif days_until <= 7:  return magnitude * 0.4
    elif days_until <= 14: return magnitude * 0.2
    else:                  return magnitude * 0.05
```

**D. Cluster Bonus 로직**

v1.0 카테고리 5.4.3:

```python
def cluster_bonus(events_within_5days):
    """
    5일 이내 magnitude 8+ 이벤트가 2개 이상이면 가산
    """
    high_impact = [e for e in events_within_5days if e.magnitude >= 8]
    if len(high_impact) >= 3: return 8
    if len(high_impact) == 2: return 4
    return 0
```

**E. Tier 1 최종 점수 산출**

```python
def tier1_score():
    # 1. 모든 다가오는 이벤트 proximity 점수 합산
    base_sum = sum(
        event_proximity_score(e.magnitude, e.days_until)
        for e in upcoming_events_within_30days
    )
    
    # 2. Cluster bonus
    events_5d = [e for e in upcoming_events_within_30days if e.days_until <= 5]
    cluster = cluster_bonus(events_5d)
    
    # 3. 합산 후 40 cap
    return min(base_sum + cluster, 40)
```

**F. DB Schema**

```sql
-- 이벤트 캘린더
CREATE TABLE events_calendar (
    id INTEGER PRIMARY KEY,
    event_name VARCHAR(100),
    event_category VARCHAR(50),   -- 'CPI', 'FOMC', etc.
    magnitude INTEGER,            -- 2-10
    scheduled_datetime DATETIME,
    country VARCHAR(10),          -- 'US', 'KR', etc.
    source VARCHAR(50),           -- 'tradingeconomics', 'manual', etc.
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- ERS 일별 이력
CREATE TABLE ers_history (
    id INTEGER PRIMARY KEY,
    calculation_datetime DATETIME,
    tier1_score FLOAT,            -- 0-40 (v0 는 tier1 만)
    tier2_score FLOAT DEFAULT 0,  -- 향후 v1 에서 구현
    tier3_score FLOAT DEFAULT 0,  -- 향후 v2 에서 구현
    total_score FLOAT,            -- tier1 + tier2 + tier3
    upcoming_events_json TEXT,    -- 30일 이내 이벤트 리스트
    cluster_bonus_applied INTEGER,
    grade VARCHAR(20),            -- Calm/Watch/Elevated/High/Critical
    version VARCHAR(10)           -- 'v0'
);
```

### 3.3 ERS UI 탭 구현

#### 작업 내용

**A. 현재 placeholder 교체**

기존 ERS 탭을 실제 UI 로 교체.

**B. 위젯 구성**

1. **Tier 1 점수 카드**
   - 현재 Tier 1 점수 (0-40) 대형 표시
   - 등급 (Calm/Watch/Elevated/High/Critical) — 단, v0 는 Tier 1 만이므로 해석 주의
   - 기여 이벤트 수
   
2. **다가오는 이벤트 리스트 (30일 이내)**
   - 각 이벤트: 이름 / D-counter / Magnitude / 개별 기여 점수
   - 색상 구분: 고영향(magnitude 8+) 강조
   
3. **Tier 2·3 Placeholder**
   - "Tier 2 (Geopolitical): Coming in v1.x" 표시
   - "Tier 3 (News Flow): Coming in v2.x" 표시

4. **ERS 시계열 차트**
   - 최근 30일 Tier 1 점수 추이
   - 이벤트 발생 시점 marker 표시

**C. 해석 구간** (v1.0 카테고리 5.7)

v0 는 Tier 1 만이므로 점수 범위가 0-40 입니다. 등급 구간을 *비례 축소*:

| 원래 (0-100) | v0 (0-40) | 등급 |
|---|---|---|
| 0-20 | 0-8 | Calm |
| 21-40 | 9-16 | Watch |
| 41-60 | 17-24 | Elevated |
| 61-80 | 25-32 | High |
| 81-100 | 33-40 | Critical |

단, 이 비례 축소는 *Tier 1 만의 구조적 한계* 임을 UI 에 명시:
*"현재 ERS v0 — Tier 2·3 미반영. 정확한 해석은 완전 구현 후 가능."*

**D. 일일 자동 계산**

APScheduler 에 ERS 계산 job 추가:
- 트리거 시각: 08:05 KST (TMRS 직후)
- 이벤트 캘린더 업데이트 → Tier 1 점수 계산 → DB 저장

### 3.4 TMRS-ERS Divergence 4사분면 위젯

#### 작업 내용

**A. 위치**

Signal Desk 탭 하단에 신규 섹션 추가.

**B. 차트 구성**

- **X축**: TMRS normalized_score (0-100)
- **Y축**: ERS Tier 1 점수를 0-100 스케일로 변환 (`tier1_score / 40 * 100`)
- **현재 포인트**: 큰 dot + 오늘 날짜 label
- **Trail**: 지난 30일 이력 (faded dots, 최근일수록 진함)
- **사분면 구분선**: X=50, Y=50 기준선

**C. 사분면 라벨**

```
           ERS Low (Y<50)    ERS High (Y≥50)
         ┌───────────────┬─────────────────┐
TMRS     │                │                  │
High     │    A           │      B           │
(X≥50)   │  Hidden        │  Known           │
         │  Stress        │  Crisis          │
         │  (조사 필요)    │  (이미 늦음)      │
         ├───────────────┼─────────────────┤
TMRS     │    C           │      D           │
Low      │  Calm          │  ⚠️ Market       │
(X<50)   │  Normal        │  Underpricing    │
         │                │  (선제 헤지)      │
         └───────────────┴─────────────────┘
```

**D. 사분면 D 진입 시 경고**

`tmrs < 50 AND ers_normalized >= 50` 조건 충족 시:
- UI 상단에 경고 배너: "⚠️ Sector D 진입 — 시장이 이벤트 리스크를 과소평가 중"
- Telegram 알람 발송 (기존 알람 시스템 연동)

**E. 향후 확장 준비**

Tier 2·3 추가 시 Y축이 자동으로 0-100 full scale 로 전환되도록 설계:

```python
def calculate_ers_normalized_score(ers_output):
    """
    Tier 1 만: tier1_score / 40 * 100
    Tier 1+2: (tier1 + tier2) / 75 * 100
    Tier 1+2+3: total_score (이미 0-100)
    """
    if ers_output.tier2_score == 0 and ers_output.tier3_score == 0:
        return ers_output.tier1_score / 40 * 100
    # ... 등
```

### 3.5 Stage 3 완료 조건

- [ ] 3.2 Tier 1 계산 엔진 구현
- [ ] 3.3 ERS 탭 UI 구현
- [ ] 3.4 TMRS-ERS Divergence 위젯 구현
- [ ] 3.4 D 사분면 경고 + Telegram 알람
- [ ] 일일 자동 계산 스케줄러 연동
- [ ] TW님 검토 요청 — 다음 항목 공유
  - ERS 탭 스크린샷
  - Divergence 위젯 스크린샷
  - 최근 7일 ERS 계산 결과
  - 현재 사분면 위치
  - 발견한 이슈/이견

---

## 4. Stage 4 — 문서화 (각 Stage 병행)

각 Stage PR 에 다음 ADR 문서 생성 또는 갱신.

### 4.1 ADR 형식

```markdown
# [제목]

**Status**: Accepted  
**Date**: YYYY-MM-DD  
**Stage**: 1 / 2 / 3  
**Related PR**: #XXX  

## Context
왜 이 결정이 필요했는가? v1.0 문서와의 관계는?

## Decision
무엇을 결정했는가? 구체 임계값/가중치/산식 포함.

## Consequences
- 긍정적: 어떤 문제가 해결되는가
- 부정적: 어떤 side effect / breaking change 가 발생하는가
- DB 마이그레이션 영향
- 기존 이력 데이터 해석 영향

## Alternatives considered
왜 다른 방안이 아닌 이 방안을 선택했는가.

## Reference
- `docs/scoring/scoring_logic_v1.0.md` 카테고리 X.Y
- (해당 시) GPT 피드백 v1.1 액션 플랜 항목 #N
```

### 4.2 Stage 1 ADR 목록 (예상)

- `2026-04-XX-stage1-sofr-term-premium-renaming.md`
- `2026-04-XX-stage1-move-percentile-overlay.md`
- `2026-04-XX-stage1-rrp-indicator-split.md`
- `2026-04-XX-stage1-threshold-version-bump.md`

### 4.3 Stage 2 ADR 목록 (예상)

- `2026-04-XX-stage2-single-b-oas-integration.md`
- `2026-04-XX-stage2-hyg-indicators.md`
- `2026-04-XX-stage2-layer2-weight-rebalance.md`
- `2026-04-XX-stage2-korea-cds-deferral.md`
- `2026-04-XX-stage2-normalized-score.md`
- `2026-04-XX-stage2-coverage-ratio-ui.md`

### 4.4 Stage 3 ADR 목록 (예상)

- `2026-04-XX-stage3-ers-v0-tier1.md`
- `2026-04-XX-stage3-event-calendar-source.md`
- `2026-04-XX-stage3-divergence-quadrant-widget.md`
- `2026-04-XX-stage3-sector-d-alert.md`

---

## 5. 통합 검증 체크리스트

모든 Stage 완료 후 최종 검증.

### 5.1 기능 검증

- [ ] TMRS 계산 pipeline 에러 없이 작동
- [ ] 모든 새 지표의 historical backfill 완료
- [ ] 일일 스케줄러 정상 동작 (TMRS + ERS + Divergence)
- [ ] Coverage ratio 가 모든 출력에 반영
- [ ] Normalized score 가 기본 표시, raw score 는 부가 표시
- [ ] Telegram 알람 정상 발송 (Sector D 진입 시)

### 5.2 사상 검증

- [ ] Solo Cap 규칙 유지 (단일 지표 폭주 방지)
- [ ] Inverse Turkey 알람이 점수와 독립 작동
- [ ] Threshold Table 버전 명시 (`v1.2026-04-01`)
- [ ] 수동 입력 필드 명확히 표시
- [ ] Bull/Bear 양방향 대조 데이터 수집 기반 유지 (기존)

### 5.3 문서 검증

- [ ] 모든 ADR 작성 완료
- [ ] README / CLAUDE.md 의 지표 리스트 갱신
- [ ] API docstring 업데이트

---

## 6. 질문 사항 — Stage 1 착수 전 필수 답변

다음 4개 질문에 대한 답변을 먼저 제공한 후 Stage 1 에 착수하세요.

### 질문 1. SOFR Term Premium 분포 통계

현재 `SOFR90DAYAVG - SOFR` 값의 최근 6개월 (최소 126 거래일) 분포 통계를 제공:

- Min / 25p / 50p (median) / 75p / 90p / 95p / Max
- 평균 / 표준편차
- 히스토그램 (ASCII 또는 간단 차트)

이 분포를 보고 TW님이 새 임계값을 결정할 것.

### 질문 2. Layer 2 보조 지표 구현 가능성

다음 지표의 현재 구현 가능성 상태:

- **IG OAS** (FRED `BAMLC0A0CM`): 현재 코드베이스에서 즉시 추가 가능? 필요 작업량?
- **LQD ETF** (yfinance `LQD`): 즉시 추가 가능?
- **GSIB CDS** (무료 소스 부재): 수동 입력 UI 구현 가능? 우선순위?

### 질문 3. 이벤트 캘린더 API 선택지

다음 소스들의 장단점 평가:

- **TradingEconomics API**
  - 무료 tier 월 호출 제한
  - 안정성
  - 데이터 품질
- **FRED Economic Calendar**
  - 커버리지 (FOMC, CPI 포함 여부)
  - 업데이트 지연
- **Investing.com 스크래핑**
  - 법적/기술적 risk
  - 차단 가능성
- **수동 CSV 업로드**
  - v0 fallback 으로 운영 가능성
  - TW 주간 업데이트 부담

각 소스의 현 상태 기준 평가 제공.

### 질문 4. 기존 `tmrs_history` DB 마이그레이션 전략

Layer 2 가중치 재분배 시 기존 점수 이력과의 호환 전략:

- **옵션 A**: 기존 이력 보존 + `score_version` column 추가 (권장)
- **옵션 B**: 기존 이력을 새 가중치로 재계산 (데이터 가용 시)
- **옵션 C**: 기존 이력 삭제 후 새로 시작 (최후 수단)

현재 `tmrs_history` 의 레코드 수, 가장 오래된 데이터 시점, 재계산 feasibility 제공.

---

## 7. 작업 Flow 요약

```
[Phase 0 — 착수 전]
질문 4개 답변 제공 → TW 검토 → Stage 우선순위 확정

[Phase 1 — Stage 1]
Stage 1.1 (FRA-OIS 명칭) → 1.2 (MOVE) → 1.3 (RRP) → PR → TW 검토

[Phase 2 — Stage 2]
Stage 2.2 (Single-B OAS) → 2.3 (HYG) → 2.4 (가중치) → 
2.5 (Korea CDS 조사) → 2.6 (IG OAS, LQD) → 2.7 (Coverage Ratio) → 
PR → TW 검토

[Phase 3 — Stage 3]
Stage 3.2 (ERS Tier 1) → 3.3 (UI) → 3.4 (Divergence 위젯) → 
PR → TW 검토

[Phase 4 — 최종]
TW 가 Claude (Opus 4.6) 과 별도 작업:
  - v1.0.1 Implementation Delta 문서 작성
  - 깃허브 업로드
  - v1.0 원본 보존
```

---

## 8. 마무리

본 지시서는 v1.0 사상을 훼손하지 않고 구현 gap 만 메우는 **sanity 정비 작업** 입니다. 새로운 사상이나 크게 다른 방향으로의 확장은 포함하지 않았습니다.

GPT 피드백 v1.1 (Velocity / Persistence / Backtesting) 은 본 지시서 이후의 별도 작업 단계이며, v1.0.1 이 안정화된 후 착수할 예정입니다.

각 Stage 완료 시마다 TW님께 공유하여 검토받고, 다음 Stage 착수 전 반드시 확인을 거치세요. 의문이나 이견이 있으면 즉시 TW님께 문의하세요 — Claude Code 가 임의로 결정해서는 안 되는 영역입니다.

**끝 (End of Instructions)**

*Financial Tracker — v1.0.1 Code Alignment Instructions*  
*작성: 2026-04-14 | TW × Claude Opus 4.6*
