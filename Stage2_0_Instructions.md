# Financial Tracker — v1.0.1 Stage 2.0 Instructions

> **Claude Code 작업 지시서 — Stage 2.0 착수**
> 본 문서는 Stage 2.0 (UI 재설계 + JPY 데이터 인프라) 통합 지시서입니다.
> 기존 Stage 2 계획은 Stage 2.1 이후로 순서가 재배열되었습니다.

| 항목 | 내용 |
|---|---|
| **Baseline** | Stage 1 완료, PR #1/#2/#3/#4/#5 merge 완료 |
| **Threshold Table 버전** | `v1.2026-04-01` (유지, 임계값 신설 없음) |
| **Score Version** | `v1.0.1` (유지) |
| **작업 기준일** | 2026-04-17 |
| **Repo 구조** | `dashboard/` 하위 실행, GitHub root 동기화 (sync_from_github.py) |

---

## 0. 개요

### 0.1 Stage 2.0 의 목적

Stage 2 진행 중 **3가지 중요한 발견** 이 있었고, 이를 반영하여 작업 순서를 재배열합니다.

**발견 1 — UI 개선 필요**
Signal Desk 의 Indicator Status 에 17개 지표가 일렬 나열되어 있어 사용자가 우선순위를 파악하기 어려움. Layer 사상이 UI 에 반영 안 됨.

**발견 2 — JPY Cross-Currency 지표 누락**
v1.0 카테고리 4.5 에서 USD/JPY 1M Basis (5pt), 3M Basis (4pt) 가 Layer 1 의 주요 지표로 명시되어 있으나, 현재 구현에서 완전히 빠져있음. TW 의 JPY Swap 대시보드에 데이터는 이미 있으나 TMRS 점수 산출에 연결되지 않음.

**발견 3 — v1.0 카테고리 3.4.4 의 재해석 필요**
GPT 의 Yen Carry Unwind 프레임워크 검토 결과, v1.0 의 USD/JPY Basis 임계 (편차 기반) 해석이 사상과 반대 방향일 가능성. 실제 Carry Unwind 는 *"절대값 감소"* (0 에 가까워짐) 가 신호. v1.0 의 이론 체계는 맞지만 임계값 구체 수치는 재검토 대상.

### 0.2 Stage 2.0 의 범위

1. **UI 재설계** — Signal Desk 의 Indicator Status 를 Active Issues + Layer 별 collapsible 구조로 재편 + 지표별 상세 카드
2. **JPY 데이터 인프라** — 일별 snapshot 테이블 + 자동 저장 로직 + 분포 분석 스크립트 준비

### 0.3 Stage 2.0 의 비범위 (의도적 제외)

- **JPY 점수화** — Stage 2.4 로 분리 (30일 데이터 누적 후)
- **Coverage Ratio** — Stage 2.1 로 재배열 (기존 Stage 2 의 Section 1.4)
- **CP-EFFR 결정** — Stage 2.2 로 재배열
- **Korea CDS 조사** — Stage 2.3 으로 재배열
- **다른 탭 UI 변경** — 이번 범위 밖 (Credit/Fed Rate/JPY Swap 탭 등은 그대로 유지)

### 0.4 전체 로드맵 (재배열)

```
[Stage 2.0 — 본 지시서] 2026-04-17 ~
  ├─ PR #6: UI 재설계 (Indicator Status 재구성 + 상세 카드)
  └─ PR #7: JPY 데이터 인프라 (일별 snapshot + 자동 저장)

[30일 누적 기간] 2026-04-17 ~ 2026-05-17
  이 기간 동안 JPY 일별 snapshot 자동 누적
  병렬로 Stage 2.1 / 2.2 / 2.3 진행

[Stage 2.1] Stage 2.0 검토 후
  └─ PR #8: Coverage Ratio (기존 Stage 2 의 Section 1.4)

[Stage 2.2] Stage 2.1 검토 후
  └─ PR #9: CP-EFFR 결정 (기존 Stage 2 의 Section 1.5)

[Stage 2.3] Stage 2.2 검토 후
  └─ PR #10: Korea CDS 조사 (기존 Stage 2 의 Section 1.6)

[Stage 2.4 — 30일 후, 약 2026-05-17 이후]
  └─ PR #11: JPY 분포 분석 + percentile 임계 확정 + 5개 지표 Layer 1 통합
              + Carry Unwind Alert (4 Level) + 예외 필터

[Stage 3] Stage 2.4 검토 후
  명칭/임계 정리 + v1.0 카테고리 3.4.4 재해석 정정

[Stage 4] Stage 3 검토 후
  ERS v0 (Tier 1)
```

### 0.5 작업 원칙

Stage 1/2 에서 확립된 원칙 그대로:

1. **Breaking change 는 명시적으로 표기**
2. **각 sub-stage 는 별도 PR** (본 Stage 는 2개 독립 PR)
3. **각 PR 완료 후 TW 검토 후 다음 진행**
4. **ADR 작성** (`docs/decisions/`)
5. **`threshold_table_version` 변경 없음**
6. **임의 결정 금지** — v1.0 사상과 충돌 시 즉시 TW 문의

---

## 0.5 Claude Code 가 모르는 변경 사항 (중요)

**중요**: Claude Code 가 마지막으로 인지한 상태는 Stage 2 착수 직전 (Section 0.5 의 baseline). 그 후 다음 변경이 있었으므로 Stage 2.0 시작 전 반드시 인지해야 합니다.

### A. 완료된 PR 들

**A.1 PR #1 — Stage 1 전체 merge (1cb668a)** (인지됨)
기존 Stage 2 지시서에서 이미 안내된 사항.

**A.2 PR #2 — LQD backfill hotfix (cb1336a)**
- `refresh_lqd()` 의 backfill 패턴 버그 수정
- `existing == 0` 체크 추가하여 빈 DB 에서 3년치 backfill
- 같은 yfinance 패턴이 MOVE, VIX 등에도 적용되어야 할 수 있음 (Stage 3 에서 검토)

**A.3 PR #3 — Telegram Inverse Turkey 테스트 (claude/stage2-validation)**
- `scripts/test_telegram_alert.py` 추가
- 24h dedup 작동 검증 완료
- Stage 1 의 Telegram 알람 기능 실제 발송 확인

**A.4 PR #4 — HYG daily + 5day + Layer 2 가중치 (claude/stage2-hyg)**
- HYG daily (가중 4pt, inverse) + HYG 5day (가중 3pt, inverse) 추가
- Layer 2 max: 17 → 24pt (v1.0 대비 80%)
- `sync_from_github.py` FILES 목록 업데이트 (자기 자신 + scripts/test_telegram_alert.py 포함)
- ADR 3건 추가

**A.5 PR #5 — Single-B OAS Series ID Fix (critical hotfix)**
가장 중요한 수정:
- **잘못된 Series ID**: `BAMLH0A2HYBEY` (Effective Yield, 국채금리+스프레드)
- **올바른 Series ID**: `BAMLH0A2HYB` (OAS, 순수 스프레드)
- 발견 경위: TW 가 FRED 웹사이트에서 직접 값 확인 (3.19% = 319bp) vs 시스템 값 (708bp) 불일치 감지
- `init_db()` 에 `oas_bp > 650` 레코드 자동 삭제 로직 추가 (Effective Yield 오류 데이터 정리)
- 결과: Single-B OAS 708bp Crisis (false positive) → 319bp Normal (실제 상태)
- **TMRS 점수 변화**: 26.5 → 18.2 (정확한 시장 상태 반영)

**이 수정의 의미**:
- Stage 1 에서 "Single-B OAS Crisis 탐지 = 시스템 성공" 이라 판단했던 것은 오류
- 실제 현재 시장은 Layer 1 (Funding) 에서만 stress, Credit (Layer 2) 은 Normal
- 카테고리 6.2.1 *"1차 소스 우선"* 원칙이 TW 의 직접 확인으로 작동한 사례

### B. 사상적 발견 — JPY Cross-Currency

**B.1 JPY 통합 결정**

v1.0 카테고리 4.5 에서 USD/JPY 1M Basis (5pt), 3M Basis (4pt) 가 Layer 1 Cross-Currency 그룹으로 명시되어 있으나 현재 미구현. TW 의 JPY Swap 대시보드에 필요 데이터가 이미 존재 (1M/3M/3Y/7Y/10Y 만기 + Implied Yield 계산 로직).

**B.2 GPT 프레임워크의 통찰**

Yen Carry Unwind Detection Framework 의 핵심 통찰:
> "Carry trade 판단은 change 부호가 아니라 **절대값 변화 기준**. 실제 unwind 신호는 음수값의 **절대값 감소** (0 에 가까워짐) = 금리차 축소 = carry 약화."

**B.3 v1.0 카테고리 3.4.4 재해석**

v1.0 원문의 USD/JPY Basis 임계 (±5bp / -5~-10bp / -10~-20bp / < -20bp) 는 *"음수가 클수록 위험"* 전제인데, 사상적으로는 *"절대값이 0 에 가까워질수록 위험"* 이 맞음. 이 정정은 Stage 3 에서 공식 처리.

**B.4 구현 전략**

30일 대기 전략:
1. 현재는 JPY 데이터 인프라만 구축 (일별 snapshot 저장)
2. 30일 누적 후 percentile 기반 임계 결정
3. Stage 2.4 에서 5개 JPY 지표를 Layer 1 에 활성화

### C. UI 문제 발견

Signal Desk 의 Indicator Status 에 17개 지표 일렬 나열:
- Layer 구분 없음 (v1.0 사상 UI 미반영)
- 가나다순 정렬 (중요도 없음)
- Crisis/Normal 혼재 (진짜 이슈 지표가 눈에 안 띔)

TW 제안 방향 (하이브리드):
- 상단 고정: Active Issues (Crisis → Stress → Watch 순)
- 하단 접힘: Normal Indicators by Layer (Layer 별 collapsible)
- 각 지표 클릭 시 상세 카드 (임계 시각화, 해석, 시계열 차트)

### D. 시장 상태 변화

Stage 2 진행 중 시장 상태:
```
2026-04-15 후반:   Total 26.5 (Single-B false positive 포함)
2026-04-15 말:     Total 18.2 (Single-B 정정 후, 실제 상태)

현재 특징:
  Layer 1 (Deep): Stress (15.3/45)
    - RRP 잔고: Crisis ($0.31B)
    - Discount Window, TGA, CP 스프레드: Stress
  Layer 2 (Credit): Normal (0.0/30)
    - Single-B OAS 319bp, HY OAS 2.95%, IG OAS 82bp 모두 Normal
  Layer 3 (Surface): 일부 stress (CBOE SKEW 149.94)
  
해석: "Funding breaks first" 단계, Credit 으로의 전이 아직 시작 안 됨
```

### E. Replit ↔ GitHub 동기화 구조 확인

- `sync_from_github.py` BRANCH = `"main"` (유지)
- FILES 목록에 `scripts/test_telegram_alert.py`, `sync_from_github.py` 포함
- dashboard/ 하위 실행, GitHub root 동기화

### F. 작업 원칙 재확인

**절대 하지 말 것**:
- 이전 feature branch (analyze-financial-tracker-iZh57, stage1-lqd-backfill-hotfix, stage2-validation, stage2-hyg, 등) 에 추가 커밋
- `sync_from_github.py` 의 BRANCH 변수 변경
- 이미 완료된 PR 의 작업 재시도

**반드시 할 것**:
- 각 PR 마다 새 feature branch
- PR base = main
- ADR 작성
- Stage 2.0 의 두 PR 완료 보고 시 TW 검토 대기

---

## 1. Stage 2.0 작업 내용

본 Stage 는 2개의 독립 PR 로 구성됩니다.

### 1.1 PR #6 — UI 재설계 (Indicator Status + 상세 카드)

#### 1.1.1 작업 범위

**포함**:
- Signal Desk 의 Indicator Status 섹션 재설계
- 각 지표 상세 카드 (클릭 시 펼침)

**제외**:
- Credit 탭, Fed Rate 탭, JPY Swap 탭 등 다른 탭
- Navigation, Header, Footer
- TMRS Score 표시 영역 (현재 유지)

#### 1.1.2 Indicator Status 새 구조

```
┌─ INDICATOR STATUS ─────────────────────────────────┐
│                                                      │
│ ⚠️  Active Issues (<N>)                              │
│ ─────────────────────────────────                    │
│ [L1]🔴 RRP 잔고           0.31      위기            │
│ [L1]🔴 Discount Window    5873      스트레스        │
│ [L1]🔴 TGA 주간변화       -99.30    스트레스        │
│ [L1]🔴 CP 스프레드        35.00     스트레스        │
│ [L3]🔴 CBOE SKEW          149.94    스트레스        │
│ [L1]🟡 A2/P2 CP-EFFR      0.44      주의            │
│                                                      │
│ ✓ Normal Indicators by Layer                        │
│ ─────────────────────────────────                    │
│ ▶ Layer 1 (2)   [▼ 펼치기]                          │
│ ▶ Layer 2 (7)   [▼ 펼치기]                          │
│ ▶ Layer 3 (3)   [▼ 펼치기]                          │
└──────────────────────────────────────────────────────┘
```

**Active Issues 섹션 규칙**:
- Crisis → Stress → Watch 순 정렬
- Layer 번호 배지 [L1]/[L2]/[L3] 를 지표명 앞에 표시
- 정렬은 클라이언트 측 JavaScript 로 처리 (성능)

**Normal Indicators 섹션 규칙**:
- Layer 별 그룹화 (L1/L2/L3)
- 기본 접힘 상태 (`<details>` 태그 사용 권장)
- 각 Layer 옆에 지표 수 표시 (예: "Layer 1 (2)")
- 펼치면 해당 Layer 의 Normal 지표들 일렬 표시

#### 1.1.3 지표 상세 카드

각 지표 클릭 시 (또는 `<details>` 펼침 시) 아래 형식으로 상세 정보 표시:

**레이아웃**:
```
┌─────────────────────────────────────────────────┐
│ <지표명>                        <아이콘> <Zone 한글>│
│ ─────────────────────────────────────               │
│ 현재값:     <value> <unit>                           │
│ 전일:       <prev_value> <unit>  (<prev_change_pct>)│
│ 1주일 전:   <week_value> <unit>  (<week_change_pct>)│
│                                                      │
│ 임계 구간:                                           │
│   Normal:  <normal_range>                           │
│   Watch:   <watch_range>                            │
│   Stress:  <stress_range>                           │
│   Crisis:  <crisis_range>                           │
│   ← 현재 위치                                       │
│                                                      │
│ Layer: <N> (<Layer 이름>)                          │
│ 가중:  <cap>pt / Solo Cap: <cap>pt                  │
│ 현재 기여: <contribution>pt (<pct>% 활용)           │
│                                                      │
│ 해석:                                                │
│ <간단한 해석 텍스트>                                │
│                                                      │
│ [최근 1개월 시계열 차트]                            │
└─────────────────────────────────────────────────┘
```

#### 1.1.4 지표별 해석 텍스트

각 지표의 "해석" 영역에 짧은 (1-2줄) 설명 표시. 예시:

```python
INDICATOR_INTERPRETATIONS = {
    'rrp': "RRP 가 거의 소진된 상태. QT 로 구조적 유동성 버퍼가 사라짐.",
    'single_b_oas': "High Yield 중 가장 위험한 등급. Credit 위험의 가장 민감한 지표.",
    'hy_oas': "전체 HY 시장 스프레드. Credit 시장의 종합 건강도.",
    # ... 모든 지표
}
```

v1.0 문서의 각 지표 설명 (카테고리 3.4-3.6) 을 요약하여 사용.

#### 1.1.5 시계열 차트

**옵션 A**: 기존 Chart.js 활용 (현재 Credit 탭 등에서 사용 중)
**옵션 B**: 간단한 sparkline (CSS 기반)

권장: **옵션 A**. 일관성 + 사용자 경험.

차트 범위: 최근 30일 (일별 데이터). 데이터 부족 시 최근 사용 가능한 기간.

#### 1.1.6 구현 세부사항

**A. Backend API 확장**

`/signal` endpoint (또는 해당 route) 에 다음 정보 추가:

```python
@app.route("/signal")
def signal_data():
    # ... 기존 TMRS 계산
    
    # 각 지표에 상세 정보 추가
    for key, indicator in snapshot.items():
        indicator.update({
            'prev_value': get_previous_value(key, 1),
            'prev_change_pct': calc_change_pct(key, 1),
            'week_value': get_previous_value(key, 7),
            'week_change_pct': calc_change_pct(key, 7),
            'thresholds': get_thresholds(key),
            'cap': get_cap(key),
            'contribution': get_current_contribution(key),
            'contribution_pct': get_contribution_pct(key),
            'layer': get_layer(key),
            'layer_name': get_layer_name(key),
            'interpretation': INDICATOR_INTERPRETATIONS.get(key, ""),
            'timeseries_30d': get_timeseries(key, days=30),
        })
    
    return jsonify({...})
```

**B. Frontend HTML/JS**

`templates/index.html` 의 Signal Desk 섹션 전체 재작성.

JavaScript 로 정렬/필터링:

```javascript
function renderIndicatorStatus(data) {
    const tierPriority = {
        'crisis': 1,
        'stress': 2,
        'watch': 3,
        'normal': 4
    };
    
    // Active Issues 분리
    const active = Object.entries(data.snapshot)
        .filter(([k, v]) => v.tier !== 'normal')
        .sort((a, b) => tierPriority[a[1].tier] - tierPriority[b[1].tier]);
    
    // Normal: Layer 별 그룹화
    const normal = Object.entries(data.snapshot)
        .filter(([k, v]) => v.tier === 'normal');
    
    const normalByLayer = {1: [], 2: [], 3: []};
    normal.forEach(([k, v]) => {
        normalByLayer[v.layer].push([k, v]);
    });
    
    // 렌더링
    renderActiveIssues(active);
    renderNormalByLayer(normalByLayer);
}
```

**C. 상세 카드 펼침**

`<details>` HTML5 태그 사용하여 순수 CSS 로 펼침 구현. JavaScript 의존성 최소화.

```html
<details class="indicator-detail">
    <summary>
        <span class="layer-badge">L1</span>
        <span class="icon crisis">🔴</span>
        <span class="name">RRP 잔고</span>
        <span class="value">0.31</span>
        <span class="zone-ko">위기</span>
    </summary>
    <div class="detail-content">
        <!-- 상세 정보 -->
    </div>
</details>
```

#### 1.1.7 ADR 작성

`docs/decisions/2026-04-17-stage2-0-ui-redesign.md`

내용:
- UI 개선 배경 (17개 지표 일렬 나열 문제)
- 하이브리드 C안 선택 근거
- Layer 사상 반영 방식
- 상세 카드 정보 설계
- 향후 확장 가능성

#### 1.1.8 PR #6 체크리스트

- [ ] Active Issues 섹션 구현
- [ ] Normal Indicators Layer 별 collapsible 구현
- [ ] Layer 배지 ([L1]/[L2]/[L3]) 표시
- [ ] Tier 우선순위 정렬 (Crisis → Stress → Watch → Normal)
- [ ] 각 지표 상세 카드 (임계 시각화, 해석, 시계열)
- [ ] Backend API 확장 (prev/week 값, 해석, 시계열 등)
- [ ] INDICATOR_INTERPRETATIONS 상수 정의 (15개 이상 지표)
- [ ] 시계열 차트 (Chart.js) 통합
- [ ] ADR 작성
- [ ] 기존 다른 탭 (Credit, Fed Rate, JPY Swap 등) 영향 없음 확인

---

### 1.2 PR #7 — JPY 데이터 인프라

#### 1.2.1 작업 범위

**포함**:
- 일별 snapshot 테이블 (`jpy_swap_daily`) 신설
- 매일 KST 08:00 자동 snapshot 저장 로직
- 분포 분석 준비 스크립트 (30일 후 사용)

**제외**:
- JPY 점수화 (TMRS 에 통합) → Stage 2.4
- Carry Unwind Alert → Stage 2.4
- 예외 필터 → Stage 2.4

#### 1.2.2 현재 데이터 구조 (참고)

기존 `jpy_swap_data` 테이블:
```
컬럼: id, period, bid, change_val, fetched_at, spot_rate
구조: long-format (period 로 만기 구분)
문제: 일별 단일 값 없음, 매 fetch 누적
```

기존 `_jpy_annualized()` 함수 (이미 app.py 에 존재):
```python
def _jpy_annualized(bid: float | None, spot: float | None, days: int) -> float | None:
    """연율화 비용(%) = (bid / 100 / spot) × (360 / days) × 100"""
    if bid is None or spot is None or days <= 0:
        return None
    return (bid / 100 / spot) * (360 / days) * 100
```

이 함수는 그대로 활용.

#### 1.2.3 신규 테이블 — `jpy_swap_daily`

```sql
CREATE TABLE IF NOT EXISTS jpy_swap_daily (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,              -- YYYY-MM-DD (KST 기준)
    period TEXT NOT NULL,             -- '1M', '3M', '3Y', '7Y', '10Y'
    bid REAL NOT NULL,                -- basis point (negative, 기존과 동일)
    spot_rate REAL NOT NULL,          -- USD/JPY spot at snapshot time
    implied_yield_pct REAL,           -- 연율화 비용 (%) = _jpy_annualized()
    snapshot_time TEXT NOT NULL,      -- 실제 snapshot 시각 (ISO 8601)
    UNIQUE(date, period)              -- 같은 날짜 같은 만기 중복 방지
);

CREATE INDEX IF NOT EXISTS idx_jpy_daily_date ON jpy_swap_daily(date);
CREATE INDEX IF NOT EXISTS idx_jpy_daily_period ON jpy_swap_daily(period);
```

`init_db()` 에 위 SQL 추가.

#### 1.2.4 Period 별 Days 매핑

`PERIOD_DAYS` 상수 (이미 존재하는 경우 재사용, 없으면 추가):

```python
PERIOD_DAYS = {
    '1M': 30,
    '3M': 90,
    '3Y': 3 * 365,    # 1095
    '7Y': 7 * 365,    # 2555
    '10Y': 10 * 365,  # 3650
}
```

#### 1.2.5 Daily Snapshot 저장 함수

```python
def save_jpy_daily_snapshot():
    """
    매일 KST 08:00 에 JPY swap 의 그날 기준 snapshot 을 저장.
    
    이유:
      - TMRS 일일 계산 시각과 동일 (08:00 KST)
      - 기존 TMRS 배치와 자연스럽게 통합
      - NY 마감 (06:00 KST) 직후이므로 전일 종가 확보됨
    
    동작:
      1. 각 만기 (1M/3M/3Y/7Y/10Y) 별로 오늘 날짜의 가장 최근 fetch 값 조회
      2. Implied Yield 계산
      3. jpy_swap_daily 테이블에 저장 (UPSERT)
      4. 데이터 없는 만기는 로그 경고 후 스킵
    """
    from datetime import datetime
    import pytz
    
    KST = pytz.timezone('Asia/Seoul')
    today_kst = datetime.now(KST).strftime('%Y-%m-%d')
    now_iso = datetime.now(KST).isoformat()
    
    conn = get_db()
    saved_count = 0
    missing_periods = []
    
    periods = ['1M', '3M', '3Y', '7Y', '10Y']
    
    for period in periods:
        # 오늘 날짜 가장 최근 fetch 조회
        latest = conn.execute("""
            SELECT bid, spot_rate, fetched_at
            FROM jpy_swap_data
            WHERE period = ?
              AND date(fetched_at) = ?
            ORDER BY fetched_at DESC
            LIMIT 1
        """, (period, today_kst)).fetchone()
        
        if not latest:
            # 오늘 fetch 가 없으면 가장 최근 값 (어제 또는 그 이전)
            latest = conn.execute("""
                SELECT bid, spot_rate, fetched_at
                FROM jpy_swap_data
                WHERE period = ?
                ORDER BY fetched_at DESC
                LIMIT 1
            """, (period,)).fetchone()
            
            if not latest:
                missing_periods.append(period)
                continue
        
        implied_yield = _jpy_annualized(
            latest['bid'], 
            latest['spot_rate'], 
            PERIOD_DAYS[period]
        )
        
        conn.execute("""
            INSERT OR REPLACE INTO jpy_swap_daily
            (date, period, bid, spot_rate, implied_yield_pct, snapshot_time)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            today_kst, period, 
            latest['bid'], latest['spot_rate'],
            implied_yield, now_iso
        ))
        saved_count += 1
    
    conn.commit()
    conn.close()
    
    if missing_periods:
        log.warning(
            f"[JPY Daily] {today_kst} snapshot: "
            f"{saved_count}/5 저장, 누락: {missing_periods}"
        )
    else:
        log.info(f"[JPY Daily] {today_kst} snapshot 저장 완료 (5개 만기)")
    
    return saved_count
```

#### 1.2.6 스케줄러 등록

기존 APScheduler 에 추가:

```python
scheduler.add_job(
    save_jpy_daily_snapshot,
    'cron',
    hour=8,
    minute=0,
    timezone='Asia/Seoul',
    id='jpy_daily_snapshot',
    replace_existing=True
)
log.info("[Scheduler] JPY daily snapshot: 매일 08:00 KST")
```

TMRS 일일 계산 직전에 실행되도록 시각 맞춤.

#### 1.2.7 `_startup_full_refresh()` 에 초기 저장 추가

앱 재시작 시 즉시 1회 snapshot 저장:

```python
def _startup_full_refresh():
    # ... 기존 단계들
    
    # Stage 2.0: JPY daily snapshot 초기 저장
    try:
        saved = save_jpy_daily_snapshot()
        log.info(f"[Startup] JPY daily snapshot: {saved}/5 저장")
    except Exception as e:
        log.warning(f"[Startup] JPY daily snapshot 실패: {e}")
```

#### 1.2.8 분포 분석 준비 스크립트

`scripts/analyze_jpy_distribution.py` 신규 작성 (30일 후 사용):

```python
#!/usr/bin/env python3
"""
JPY Swap Daily Snapshot 의 historical 분포 분석

용도: Stage 2.4 의 percentile 기반 임계값 결정
실행: python scripts/analyze_jpy_distribution.py [lookback_days]

기본 lookback: 30일
"""

import sqlite3
import sys
import os
from pathlib import Path

# dashboard/ 디렉토리의 data.db 참조
DASHBOARD_DIR = Path(__file__).parent.parent
DB_PATH = DASHBOARD_DIR / "data.db"


def analyze_jpy_distribution(lookback_days=30):
    """
    각 만기별 5일 변화 분포 분석.
    
    핵심: bid 의 absolute value 변화 (GPT 가이드 기준)
    - 음수값이 0 에 가까워짐 = 절대값 감소 = Carry 약화 (stress)
    - 음수값이 더 음수가 됨 = 절대값 증가 = Carry 강화 (normal)
    """
    if not DB_PATH.exists():
        print(f"ERROR: DB 파일 없음 - {DB_PATH}")
        return
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    print(f"=== JPY Swap Daily Distribution Analysis ===")
    print(f"Lookback: {lookback_days} days")
    print(f"DB: {DB_PATH}")
    print()
    
    periods = ['1M', '3M', '3Y', '7Y', '10Y']
    
    for period in periods:
        rows = conn.execute("""
            SELECT date, bid, implied_yield_pct
            FROM jpy_swap_daily
            WHERE period = ?
              AND date >= date('now', ?)
            ORDER BY date
        """, (period, f'-{lookback_days} days')).fetchall()
        
        n_records = len(rows)
        
        if n_records < 20:
            print(f"--- {period} ---")
            print(f"  데이터 부족: {n_records}일 (최소 20일 필요)")
            print(f"  누적 대기 중...\n")
            continue
        
        # 5일 전 대비 절대값 변화
        bid_abs_changes_5d = []
        yield_changes_5d = []
        
        for i in range(5, n_records):
            bid_now = rows[i]['bid']
            bid_5d_ago = rows[i-5]['bid']
            
            # 절대값 변화 (GPT 가이드 핵심)
            abs_change = abs(bid_now) - abs(bid_5d_ago)
            bid_abs_changes_5d.append(abs_change)
            
            # Implied Yield 변화
            yld_now = rows[i]['implied_yield_pct']
            yld_5d_ago = rows[i-5]['implied_yield_pct']
            if yld_now is not None and yld_5d_ago is not None:
                yield_changes_5d.append(yld_now - yld_5d_ago)
        
        print(f"=== {period} — {n_records}일 기간 ===")
        print(f"  Bid range: {rows[0]['bid']:.1f} ~ {rows[-1]['bid']:.1f} (bp)")
        print(f"  현재 Implied Yield: {rows[-1]['implied_yield_pct']:.2f}%" 
              if rows[-1]['implied_yield_pct'] else "N/A")
        
        # 절대값 5일 변화 분포
        if bid_abs_changes_5d:
            sorted_ch = sorted(bid_abs_changes_5d)
            n = len(sorted_ch)
            
            print(f"\n  [Bid 절대값 5일 변화 분포]")
            print(f"  Min: {sorted_ch[0]:+7.2f}  (음수: 절대값 증가 = 정상)")
            print(f"  25p: {sorted_ch[n//4]:+7.2f}")
            print(f"  50p: {sorted_ch[n//2]:+7.2f}")
            print(f"  75p: {sorted_ch[3*n//4]:+7.2f}")
            print(f"  90p: {sorted_ch[int(n*0.9)]:+7.2f}")
            print(f"  95p: {sorted_ch[int(n*0.95)]:+7.2f}")
            print(f"  Max: {sorted_ch[-1]:+7.2f}  (양수: 절대값 감소 = stress)")
            
            # 제안 임계값 (percentile 기반)
            print(f"\n  [제안 Percentile 임계 — Stage 2.4 참고용]")
            print(f"    Normal:  < 75p ({sorted_ch[3*n//4]:+.2f})")
            print(f"    Watch:   75p ~ 90p ({sorted_ch[3*n//4]:+.2f} ~ {sorted_ch[int(n*0.9)]:+.2f})")
            print(f"    Stress:  90p ~ 95p ({sorted_ch[int(n*0.9)]:+.2f} ~ {sorted_ch[int(n*0.95)]:+.2f})")
            print(f"    Crisis:  > 95p ({sorted_ch[int(n*0.95)]:+.2f})")
        
        print()
    
    conn.close()
    
    print("=" * 50)
    print("참고:")
    print("  - 양수 = bid 절대값 감소 = carry 약화 (stress 신호)")
    print("  - 음수 = bid 절대값 증가 = carry 강화 (normal)")
    print("  - GPT 가이드: 절대값 감소 + implied yield 감소 = unwind")
    print("  - Stage 2.4 에서 이 분포를 기반으로 최종 임계 확정")


if __name__ == "__main__":
    lookback = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    analyze_jpy_distribution(lookback)
```

**실행 권한**:

```bash
chmod +x scripts/analyze_jpy_distribution.py
```

#### 1.2.9 sync_from_github.py FILES 업데이트

`analyze_jpy_distribution.py` 를 FILES 목록에 추가:

```python
FILES = [
    # 기존 파일들
    "app.py",
    "auth.py",
    "telegram_alerts.py",
    "portfolio_scraper.py",
    "jpy_scraper.py",
    "gunicorn.conf.py",
    "templates/index.html",
    "templates/login.html",
    "sync_from_github.py",
    "scripts/test_telegram_alert.py",
    # Stage 2.0 신규
    "scripts/analyze_jpy_distribution.py",
]
```

#### 1.2.10 ADR 작성

`docs/decisions/2026-04-17-stage2-0-jpy-infrastructure.md`

내용:
- JPY 데이터 인프라 구축 배경
- `jpy_swap_daily` 테이블 스키마 설계
- KST 08:00 snapshot 시각 선택 이유
- GPT 가이드의 "절대값 변화 기준" 통찰
- v1.0 카테고리 3.4.4 재해석 (Stage 3 에서 공식 정정 예정)
- 30일 대기 전략
- Stage 2.4 계획 프리뷰

#### 1.2.11 PR #7 체크리스트

- [ ] `jpy_swap_daily` 테이블 신설 (`init_db()`)
- [ ] `save_jpy_daily_snapshot()` 함수 작성
- [ ] APScheduler 에 매일 KST 08:00 등록
- [ ] `_startup_full_refresh()` 에 초기 저장 추가
- [ ] `PERIOD_DAYS` 상수 정의 확인 (이미 있으면 재사용)
- [ ] `scripts/analyze_jpy_distribution.py` 작성
- [ ] `sync_from_github.py` FILES 에 `scripts/analyze_jpy_distribution.py` 추가
- [ ] ADR 작성
- [ ] 기존 `jpy_swap_data` 테이블 동작 영향 없음 확인

---

## 2. Stage 2.0 완료 조건

### 2.1 PR #6 (UI 재설계) 완료 조건

- [ ] 모든 1.1.x 체크리스트 항목 완료
- [ ] Signal Desk 탭만 변경 (다른 탭 영향 없음)
- [ ] Active Issues 정렬이 Crisis → Stress → Watch 순으로 작동
- [ ] Normal Indicators 가 Layer 별로 그룹핑
- [ ] 각 지표 상세 카드에 필요 정보 (prev/week/임계/해석) 표시
- [ ] 시계열 차트 작동 (최근 30일)
- [ ] ADR 작성

### 2.2 PR #7 (JPY 인프라) 완료 조건

- [ ] 모든 1.2.x 체크리스트 항목 완료
- [ ] `jpy_swap_daily` 테이블 생성 확인 (Replit sync 후)
- [ ] 매일 08:00 스케줄러 작동 (다음날 확인 가능)
- [ ] `_startup_full_refresh()` 실행 시 첫 snapshot 저장 확인
- [ ] `analyze_jpy_distribution.py` 실행 시 "데이터 부족" 메시지 출력 (정상, 아직 누적 전)
- [ ] ADR 작성

### 2.3 TW 검토 요청 공유 사항

각 PR 완료 시:

1. **변경 파일 리스트**
2. **DB 변경 사항** (신규 테이블, 스키마 변경)
3. **PR URL**
4. **Screenshots** — UI 변경은 특히 before/after 필수
5. **실행 결과**:
   - UI: Signal Desk 실제 표시
   - JPY 인프라: `jpy_swap_daily` 테이블에 첫 snapshot 저장 확인
6. **발견한 이슈/이견**

### 2.4 PR 분리 진행 순서

```
[Day 1]
  PR #6 (UI) 착수 → TW 검토
  병렬: PR #7 (JPY 인프라) 착수 → TW 검토

[Day 2]
  두 PR 모두 merge 완료
  Replit sync + 앱 재시작
  다음 날 08:00 스케줄러 작동 확인
```

두 PR 은 독립적이므로 병렬 진행 가능. 순서 상관없음.

---

## 3. 30일 후 Stage 2.4 프리뷰 (참고용)

Stage 2.4 는 본 Stage 의 직접 연결 작업이지만 **본 Stage 범위 밖** 입니다. 인프라 이해를 위한 참고.

### 3.1 Stage 2.4 의 작업

```
PR #11 — JPY Carry Unwind 점수 통합

1. analyze_jpy_distribution.py 실행 (30일 데이터 기반)
2. 각 만기별 percentile 분포 확인
3. 임계값 확정:
   Normal:  < 75p (평상시)
   Watch:   75p ~ 90p
   Stress:  90p ~ 95p
   Crisis:  > 95p

4. Layer 1 에 5개 JPY 지표 추가:
   jpy_implied_yield_1m_change   5pt (역방향)
   jpy_implied_yield_3m_change   4pt
   jpy_curve_flattening          3pt
   jpy_long_end_collapse         3pt
   usd_jpy_spot_5d               2pt (보조)
   총 17pt

5. Carry Unwind Alert (4 Level):
   Level 1: Carry Weakening
   Level 2: Carry Unwind Risk
   Level 3: Active Unwind
   Level 4: Systemic Collapse

6. 예외 필터:
   Case 1: Spot 상승 + carry 감소 → 단순 금리 변화 (무시)
   Case 2: Short-end 만 변화 → noise (무시)

7. v1.0 카테고리 3.4.4 재해석 (Stage 3 에서 공식 정정)
```

### 3.2 Stage 2.4 전제 조건

- `jpy_swap_daily` 에 30일 이상 데이터 누적
- 모든 5개 만기 데이터 존재
- 각 만기별 분포 통계 정상 (outlier 검증)

---

## 4. 작업 원칙 재확인

### 4.1 반드시 지킬 것

1. 새 feature branch 사용 — `claude/stage2-0-ui`, `claude/stage2-0-jpy-infra` 형식
2. PR base = main
3. 각 PR 에 ADR 포함
4. TW 검토 없이 다음 작업 금지
5. 기존 `jpy_swap_data` 테이블 및 `_jpy_annualized()` 함수는 **절대 수정하지 말 것** (신규 테이블/함수 추가만)

### 4.2 피할 것

1. 이전 feature branch 에 추가 커밋
2. `sync_from_github.py` BRANCH 변수 변경
3. JPY 점수를 TMRS 에 통합 (Stage 2.4 범위)
4. Credit/Fed Rate/JPY Swap 등 **다른 탭 변경**
5. `threshold_table_version` 변경

### 4.3 의문 발생 시

다음 상황 발생 시 즉시 TW 문의:

- 기존 코드 구조가 예상과 다름 (특히 `_jpy_annualized()` 관련)
- `PERIOD_DAYS` 정의가 다른 곳에 있음
- UI 변경이 다른 탭에 영향 줌
- jpy_swap_data 데이터가 예상과 다른 형식
- ADR 작성 시 불명확한 배경

---

## 5. 참조 문서

GitHub main 에 모두 존재:

- `Financial_Tracker_Scoring_Logic_in Total.md` — v1.0 통합문서
- `Financial_Tracker_v1.0.1_Instructions.md` — 전체 v1.0.1 지시서
- `Stage1_Emergency.md` — Stage 1 긴급 지시서
- `Stage2_Instructions.md` — 원본 Stage 2 지시서 (순서 재배열 전)
- `TW_Financial_App_Reference.md` — TW 작업 컨텍스트
- `docs/decisions/` 의 Stage 1 + Stage 2 ADR 들

---

## 6. 착수 메시지 (TW → Claude Code)

이 지시서를 GitHub main 에 업로드한 후, Claude Code 에 다음 메시지를 전달:

> Stage 2 진행 중 발견된 사항 반영해서 작업 순서를 재배열했다. 
>
> 먼저 `Stage2_0_Instructions.md` 를 전체 읽어줘. 특히 **Section 0.5 (Claude Code 가 모르는 변경사항)** 를 반드시 먼저 확인. Stage 1 이후 merge 된 PR 5개 (LQD hotfix 포함 Single-B OAS Series ID 정정까지) 의 이력을 알아야 해.
>
> 읽은 후 다음을 보고해줘:
>
> 1. Section 0.5 의 핵심 발견 5가지 이해도 요약 (5-7줄)
> 2. Stage 2.0 의 두 PR (PR #6 UI, PR #7 JPY 인프라) 중 어느 것부터 시작할지 제안
> 3. PR #6 의 상세 카드 구현 시 예상되는 기술적 이슈 (있다면)
>
> 이 3가지 보고 후 내가 검토하고 착수 지시 줄게.
>
> **중요한 작업 원칙**:
> - 새 feature branch 2개 (`claude/stage2-0-ui`, `claude/stage2-0-jpy-infra`)
> - PR base = main
> - 두 PR 은 독립적 (병렬 진행 가능)
> - 각 PR 완료 후 내 검토 대기
> - **기존 jpy_swap_data 테이블과 `_jpy_annualized()` 함수는 절대 수정 금지** (신규 테이블/함수 추가만)
> - sync_from_github.py BRANCH 변경 금지
>
> Stage 2.0 시작 준비해줘.

---

**끝 (End of Stage 2.0 Instructions)**

*Financial Tracker — v1.0.1 Stage 2.0 Instructions*
*작성: 2026-04-17 | TW × Claude Opus 4.6*
