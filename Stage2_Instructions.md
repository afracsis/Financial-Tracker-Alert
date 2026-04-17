# Financial Tracker — v1.0.1 Stage 2 Instructions

> **Claude Code 작업 지시서 — Stage 2 착수**
> 본 문서는 Stage 1 완료 검증 후 진행하는 Stage 2 정비 작업 지시서입니다.
> Stage 2 의 핵심은 **Layer 2 충실화 마무리 + Coverage Ratio 출력 + ERS 사상 준비** 입니다.

| 항목 | 내용 |
|---|---|
| **Baseline** | `Stage1_Emergency.md` 완료, PR #1 merged (1cb668a) |
| **Threshold Table 버전** | `v1.2026-04-01` (Stage 1 과 동일, 임계값 변경 없음) |
| **Score Version** | `v1.0.1` 유지 (Stage 1 과 동일) |
| **작업 기준일** | 2026-04-15 |
| **실제 TMRS 테이블** | `tmrs_scores` |
| **Repo 구조** | `dashboard/` 하위 실행, GitHub root 동기화 (sync_from_github.py 사용) |

---

## 0. 개요

### 0.1 Stage 2 의 목적

Stage 1 에서 Layer 2 의 핵심 지표 (Single-B OAS) 를 응급 추가하여 Inverse Turkey 감지 *구조적 가능성* 을 복원했습니다. 그러나 Stage 1 종료 시점 Layer 2 max 가 17점 (v1.0 스펙 30점 대비 57%) 으로 여전히 불완전합니다.

Stage 2 는 다음을 달성합니다:

1. **Layer 2 의 추가 보강** — HYG daily/5day 추가로 Layer 2 max 24점 회복
2. **Coverage Ratio 출력 체계** — 부분 구현 상태를 사용자가 명확히 인지할 수 있도록
3. **CP-EFFR 정식 처리 결정** — Stage 1 에서 보류한 사항의 redundancy 평가 후 결론
4. **Korea CDS 대체 소스 조사** — 실제 통합은 후속 작업, 본 Stage 에서는 조사만
5. **Stage 1 보류 사항 검증** — Telegram 알람 실제 발송 테스트 등

### 0.2 Stage 2 의 비목적 (의도적 제외)

다음은 Stage 2 범위 밖이며, 별도 Stage 에서 다룹니다:

- **명칭/임계 정리** (FRA-OIS → SOFR Term Premium 명칭, MOVE percentile 병기 등) → Stage 3
- **ERS Tier 1 구현** → Stage 4
- **GPT v1.1 피드백 (Velocity / Persistence / Backtesting)** → Stage 5 이후
- **Power Law 코드 영역 (Hill Estimator 등)** → 운영 6개월 이상 후

### 0.3 작업 원칙

Stage 1 에서 확립된 원칙 그대로 유지:

1. **Breaking change 는 명시적으로 표기**
2. **각 sub-stage 는 별도 PR** (가능한 작은 단위)
3. **각 sub-stage 완료 후 TW 검토**
4. **ADR 작성** (`docs/decisions/`)
5. **`threshold_table_version` 변경 없음** (Stage 2 는 임계값 신규 정의 없음)
6. **임의 결정 금지** — v1.0 사상과 충돌 시 즉시 TW 문의

### 0.4 Stage 1 → Stage 2 작업 흐름 (이번에 변경됨)

```
[변경 전 — Stage 1]
Claude Code → feature branch push → PR 생성 → TW merge → Replit pull

[변경 후 — Stage 2 부터]
Claude Code → 새 feature branch (claude/stage2-*) 에 push 
            → PR 생성 (base: main)
            → TW 가 GitHub 에서 merge
            → TW 가 Replit shell 에서 sync_from_github.py 실행 
              (이제 main 에서 자동 pull)
            → TW 검증 후 다음 sub-stage 진행
```

---

## 0.5 Claude Code 가 모르는 변경 사항 (Stage 1 완료 ~ Stage 2 착수 전)

**중요**: Claude Code 가 마지막으로 인지한 상태는 *"Stage 1 코드를 feature branch 에 push 완료, Stage 2 진행 지시 대기 중"* 입니다. 이후 다음 변경이 있었으므로 Stage 2 시작 전에 반드시 인지해야 합니다.

### A. GitHub Repository 변경

**A.1 PR #1 생성 + merge 완료**

- PR 번호: #1
- Merge commit hash: `1cb668a`
- Merge 시각: 2026-04-15 (TW 가 GitHub 웹 UI 에서 직접 merge)
- Merge 방식: Create a merge commit (15개 커밋 보존)
- Title: "Stage 1: Layer 2 Emergency + Phase 2 indicators + ADR documentation"

**A.2 main 브랜치 현재 상태**

main 브랜치 (1cb668a) 에 Stage 1 모든 결과물이 안착됨:

```
github.com/afracsis/Financial-Tracker-Alert/main
├── docs/decisions/                        ← ADR 7개 ✓
│   ├── 2026-04-14-stage1-layer2-emergency.md
│   ├── 2026-04-14-stage1-single-b-oas.md
│   ├── 2026-04-14-stage1-ig-oas.md
│   ├── 2026-04-14-stage1-lqd.md
│   ├── 2026-04-14-stage1-score-version-column.md
│   ├── 2026-04-14-stage1-layer2-weight-correction.md
│   └── 2026-04-14-stage1-telegram-inverse-turkey.md
├── scripts/migrations/                    ← Migration 0001 ✓
│   └── 0001_add_score_version.py
├── templates/
├── app.py                                 ← Stage 1 코드 + Inverse Turkey hotfix (fc6420f)
├── auth.py
├── telegram_alerts.py                     ← Inverse Turkey 알람 + 24h dedup
├── sync_from_github.py                    ← BRANCH = "main" (변경됨)
├── gunicorn.conf.py
├── jpy_scraper.py
├── portfolio_scraper.py
├── .gitignore
├── README.md
├── Financial_Tracker_Scoring_Logic_in Total.md
├── Financial_Tracker_v1.0.1_Instructions.md
├── Stage1_Emergency.md
├── TW_Financial_App_Reference.md
└── financial_app_reference_notes by GPT.md
```

**A.3 Feature branch 보존**

- `claude/analyze-financial-tracker-iZh57` 브랜치는 **삭제하지 않고 보존**
- 이력 추적 목적
- Stage 2 는 **새 feature branch 에서 작업** (이 브랜치에 추가 커밋 금지)

### B. Replit 환경 변경

**B.1 sync_from_github.py BRANCH 변수 변경**

```python
# 이전 (Stage 1 검증용):
BRANCH = "claude/analyze-financial-tracker-iZh57"

# 현재 (Stage 1 merge 완료 후):
BRANCH = "main"
```

이 변경 의미:
- Replit 이 이제 **GitHub main 에서 직접 pull**
- Stage 2 작업이 main 에 merge 되면 즉시 Replit 에 반영 가능
- **Stage 2 작업 중 이 변수를 다시 변경하지 말 것**

**B.2 정리 작업 완료**

- Replit repo root 의 이상한 파일 3개 (`0`, `1`, `'ingle_b_oas|...'`) 삭제 완료
- 이는 과거 shell 명령 오류로 생성된 것
- Stage 2 작업과 무관

### C. 시장 상태 변화 (참고용)

Stage 1 검증 시점 → Stage 2 착수 시점 (약 24시간) 사이 시장 상태 변화:

```
2026-04-14 13:37 KST (Stage 1 검증):
  total_score: 20.6
  l2_score:    7.0  (Single-B OAS Crisis 713bp)
  Tier:        Watch

2026-04-15 08:07 KST (Stage 2 착수 직전):
  total_score: 26.5  (+5.9, 약 +28%)
  l2_score:    7.0   (변동 없음, Single-B OAS Crisis 지속)
  score_version: v1.0.1
```

해석:
- Single-B OAS 가 Crisis 구간 지속 — tariff shock 신용시장 영향 진행 중
- 24시간 동안 Layer 1 또는 Layer 3 에서 추가 stress 발생 (어디서 발생했는지는 Stage 2 진행 중 확인 가치)
- **이 상황은 카테고리 1 의 "Funding breaks first → Credit confirms → Equities react last" 명제가 실시간 진행 중인 사례**

Stage 2 에서 HYG 추가 시 Layer 2 의 신용시장 변화를 더 정밀하게 추적 가능.

### D. Stage 1 작업 검증 — 완전 통과

TW 가 Replit shell 에서 직접 검증한 결과:

| 검증 항목 | 결과 |
|---|---|
| Single-B OAS 데이터 수집 | ✅ 713bp Crisis 정상 탐지 |
| IG OAS 데이터 수집 | ✅ 82bp Normal |
| LQD daily | ✅ Normal |
| HY OAS 가중치 복원 | ✅ 7→5pt 복원 확인 |
| CP-EFFR 0pt 보류 | ✅ tier=watch 표시되나 점수 기여 0 |
| score_version 컬럼 | ✅ v1.0.1 신규 레코드 정상 누적 |
| Inverse Turkey 트리거 hotfix (fc6420f) | ✅ 적용됨 |
| sync_from_github.py main 전환 | ✅ 정상 작동 |

### E. 작업 워크플로우 (Stage 2 부터 적용)

```
1. Claude Code 가 새 feature branch 생성
   - 브랜치명 예시: claude/stage2-hyg-coverage
   - Base: github/main (1cb668a)

2. 각 sub-stage 별로 독립 PR
   - 예: stage2.1 (HYG daily), stage2.2 (HYG 5day), stage2.3 (Coverage Ratio)
   - Base: main, Compare: 해당 feature branch

3. TW 가 GitHub 에서 PR merge
   - "Create a merge commit" 방식 (히스토리 보존)
   - PR 본문에 ADR 링크 + Stage 1 처럼 verification 정보 포함

4. TW 가 Replit shell 에서 sync 실행
   ```bash
   cd ~/workspace/dashboard
   python sync_from_github.py
   ```

5. TW 검증 (각 sub-stage 별 제공된 검증 스크립트 실행)

6. 검증 통과 시 다음 sub-stage 진행
```

### F. Replit 자동 체크포인트 커밋 처리

- `Replit-Commit-Author: Agent` 메타데이터를 가진 자동 커밋이 발생할 수 있음
- 이는 Replit 체크포인트 시스템의 자동 생성물 (Agent 가 자율적으로 작업한 것 아님)
- **무시하고 진행**
- Stage 2 의 모든 의도적 변경은 Claude Code 가 GitHub 에서 작업 → main 으로 통합

---

## 1. Stage 2 작업 내용

### 1.1 Stage 2.1 — HYG daily 추가

#### 1.1.1 배경

v1.0 카테고리 4.6 의 Layer 2 가중치 표에서 HYG daily 는 가중 4점 (Layer 2 의 Single-B 다음으로 큰 무게). 일중 신호로서 HY OAS 의 1일 lag 를 보완하는 핵심 지표.

#### 1.1.2 데이터 수집

- **yfinance ticker**: `HYG`
- **갱신 빈도**: 일중 (기존 Stage 1 의 LQD 와 같은 주기)
- **DB 테이블 신규**: `hyg_prices`

```sql
CREATE TABLE IF NOT EXISTS hyg_prices (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL UNIQUE,
    close_price REAL NOT NULL,
    daily_change_pct REAL,
    fetched_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hyg_timestamp ON hyg_prices(timestamp);
```

- **Historical backfill**: 최소 3년 (2023-01-01 이후)
- **Initial load**: Stage 1 의 `_initial_load_stage1()` 패턴 참고

#### 1.1.3 임계값 (v1.0 카테고리 3.5.2)

| Zone | 임계 |
|---|---|
| Normal | > -0.3% |
| Watch | -0.3% ~ -0.7% |
| Stress | -0.7% ~ -1.5% |
| Crisis | < -1.5% |

Direction: `inverse` (값이 작을수록/음수가 클수록 stress)

#### 1.1.4 점수 엔진 연동

- **Layer**: 2 (Middle / Credit)
- **가중**: 4점
- **Solo Cap**: 4점
- **Mode**: interpolated scoring

#### 1.1.5 snapshot 스키마 추가

```json
"hyg_daily": {
  "value": <pct>,
  "tier": "normal" | "watch" | "stress" | "crisis",
  "name": "HYG 일간 변화율",
  "cap": 4,
  "unit": "%",
  "layer": 2
}
```

(Stage 1 에서 LQD 의 snapshot 키가 cap/unit/layer 포함하도록 변경되었으므로 동일 패턴)

#### 1.1.6 UI 추가

- **위치**: Credit 탭, 기존 LQD 카드 옆 (또는 Single-B OAS / IG OAS 와 같은 섹션)
- **위젯 형식**: Stage 1 의 LQD 카드와 동일 패턴
- **표시**: 현재 일간 변화율 / Zone / 기여 점수 / 1일 sparkline

#### 1.1.7 ADR 작성

`docs/decisions/2026-04-15-stage2-hyg-daily.md`

내용: 가중치 4점 결정 근거, direction inverse 처리, 일중 데이터 fetch 주기.

### 1.2 Stage 2.2 — HYG 5일 누적 변화 추가

#### 1.2.1 배경

HYG daily 가 일중 단기 신호라면, 5일 누적 변화는 *추세* 신호. 일시적 spike 가 아닌 지속적 stress 누적을 감지.

#### 1.2.2 데이터

기존 `hyg_prices` 테이블 활용. 별도 테이블 불필요. 계산만 추가.

```python
def compute_hyg_5day_cumulative_change():
    """
    최근 5거래일 HYG 누적 변화율
    """
    rows = conn.execute("""
        SELECT close_price FROM hyg_prices
        ORDER BY timestamp DESC LIMIT 6
    """).fetchall()
    
    if len(rows) < 6:
        return None
    
    latest = rows[0]['close_price']
    five_days_ago = rows[5]['close_price']
    return (latest / five_days_ago - 1) * 100
```

#### 1.2.3 임계값 (v1.0 카테고리 3.5.2)

| Zone | 임계 |
|---|---|
| Normal | > -1% |
| Watch | -1% ~ -2.5% |
| Stress | -2.5% ~ -5% |
| Crisis | < -5% |

Direction: `inverse`

#### 1.2.4 점수 엔진 연동

- **Layer**: 2
- **가중**: 3점
- **Solo Cap**: 3점

#### 1.2.5 snapshot 추가

```json
"hyg_5day": {
  "value": <pct>,
  "tier": "<zone>",
  "name": "HYG 5일 누적 변화",
  "cap": 3,
  "unit": "%",
  "layer": 2
}
```

#### 1.2.6 UI 추가

Credit 탭에 보조 카드 추가. HYG daily 와 같은 행에 배치.

#### 1.2.7 ADR 작성

`docs/decisions/2026-04-15-stage2-hyg-5day.md`

### 1.3 Stage 2.3 — Layer 2 가중치 재정리

#### 1.3.1 Stage 2 종료 시점 Layer 2 구성

| 지표 | 가중 | 상태 |
|---|---|---|
| Single-B OAS | 7 | Stage 1 |
| HY OAS | 5 | Stage 1 (복원) |
| HYG daily | 4 | **Stage 2.1 신규** |
| IG OAS | 3 | Stage 1 |
| HYG 5day | 3 | **Stage 2.2 신규** |
| LQD daily | 2 | Stage 1 |
| CP-EFFR | 0 | 보류 (Stage 2.5 에서 결정) |
| Korea CDS | 0 | 데이터 부재 (Stage 2.6 에서 조사) |
| GSIB CDS | 0 | 데이터 부재 |
| **합계** | **24** | (v1.0 스펙 30점 대비 80%) |

#### 1.3.2 Layer 2 max 변화

```
Stage 1 종료: 17점
Stage 2 종료: 24점 (+7점)
```

#### 1.3.3 Inverse Turkey 트리거 영향 시뮬레이션

Stage 2 종료 후 가능한 시나리오:

```
[시나리오 A — 현재 상태 유지 시]
  Single-B OAS Crisis 7pt + 나머지 모두 Normal = 7pt
  l2_norm = 7/30 = 0.233 (분모 30 유지 시)
  
  → 여전히 Inverse Turkey 트리거 미충족 (l12_avg ≈ 0.29)
  → HYG 가 Stress/Crisis 진입 시 즉시 트리거 가능

[시나리오 B — HYG 가 Stress 로 진입 시]
  Single-B 7pt + HYG daily 3pt + HYG 5day 2.25pt = 12.25pt
  l2_norm = 12.25/30 = 0.408
  l1_norm = 0.346 (현재 수준 유지 가정)
  l12_avg = (0.346 + 0.408) / 2 = 0.377
  
  → 트리거 미충족 (0.40 미만, 0.023 부족)
  → HYG 가 Crisis 진입 시 즉시 트리거 가능

[시나리오 C — HYG 가 Crisis 로 진입 시]
  Single-B 7pt + HYG daily 4pt + HYG 5day 3pt = 14pt
  l2_norm = 14/30 = 0.467
  l12_avg = (0.346 + 0.467) / 2 = 0.406
  
  → 트리거 충족 (0.40 ↑) → Inverse Turkey 발화 ★
```

**핵심 인사이트**: Stage 2 종료 후 시스템은 *"신용시장 stress 가 종합적으로 발생할 때 즉시 감지 가능한 상태"* 가 됩니다. Single-B OAS 단독 Crisis 만으로는 트리거 안 되지만, 거기에 HYG 의 추가 stress 가 동반되면 즉시 발화.

### 1.4 Stage 2.4 — Coverage Ratio 출력 체계 (Critical)

#### 1.4.1 배경

현재 TMRS 가 출력하는 점수는 명목상 0–100 점이지만, Layer 2 가 30점 → 24점 (Stage 2 후) → 17점 (Stage 1) → 점진적으로 회복 중. 사용자가 점수 해석 시 **현재 커버리지 상태를 명확히 인지** 해야 함.

#### 1.4.2 TMRSOutput 데이터 구조 확장

기존 `tmrs_scores` 테이블은 그대로 유지하되, 출력 객체에 신규 필드 추가:

```python
@dataclass
class TMRSOutput:
    # ===== 기존 필드 (Stage 1 까지) =====
    total_score: float
    grade: str
    layer1_score: float
    layer2_score: float
    layer3_score: float
    divergence_score: float
    inverse_turkey: int
    score_version: str
    snapshot: dict
    indicator_tiers: dict
    interpretation: str
    calculated_at: datetime
    
    # ===== 신규 필드 (Stage 2.4) =====
    
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
    
    # 점수 정규화 (Stage 2.4 핵심)
    raw_score: float                # 실제 합산 (0-86 등, 현재 max)
    max_achievable_score: float     # 현재 활성 지표 기준 최대
    normalized_score: float         # raw / max * 100
    
    # 플래그
    is_partial_implementation: bool  # overall_coverage < 0.80 이면 True
```

#### 1.4.3 Spec 지표 수 정의 (v1.0 기준)

```python
LAYER_SPEC = {
    1: {  # Deep / Funding
        'spec_indicators': 12,  # v1.0 카테고리 4.5
        'spec_max_score': 45,
    },
    2: {  # Middle / Credit
        'spec_indicators': 8,   # v1.0 카테고리 4.6
        'spec_max_score': 30,
    },
    3: {  # Surface / Equity
        'spec_indicators': 7,   # v1.0 카테고리 4.7
        'spec_max_score': 15,
    },
    'divergence': {
        'spec_signals': 5,      # v1.0 카테고리 4.8
        'spec_max_score': 10,
    }
}
```

#### 1.4.4 Coverage 계산 로직

```python
def calculate_coverage(snapshot, layer):
    """
    Layer 별 커버리지 계산
    """
    active_indicators = [
        k for k, v in snapshot.items()
        if v.get('layer') == layer and v.get('cap', 0) > 0
    ]
    spec = LAYER_SPEC[layer]['spec_indicators']
    return {
        'active': len(active_indicators),
        'spec': spec,
        'coverage': len(active_indicators) / spec
    }

def calculate_overall_coverage(coverages):
    """
    전체 커버리지 = 각 Layer max 점수 가중 평균
    """
    weights = {
        1: 45/100,  # Layer 1 가중
        2: 30/100,
        3: 15/100,
        'divergence': 10/100,
    }
    return sum(
        coverages[k]['coverage'] * weights[k]
        for k in weights
    )
```

#### 1.4.5 Normalized Score 계산

```python
def calculate_normalized_score(raw_score, snapshot):
    """
    현재 활성 지표의 max achievable 기준으로 정규화
    """
    max_achievable = sum(v.get('cap', 0) for v in snapshot.values())
    
    if max_achievable == 0:
        return {'raw': raw_score, 'max': 0, 'normalized': 0}
    
    normalized = (raw_score / max_achievable) * 100
    
    return {
        'raw': raw_score,
        'max': max_achievable,
        'normalized': normalized,
    }
```

#### 1.4.6 UI 표시 변경

**Signal Desk 탭 상단**:

```
┌─────────────────────────────────────────────────────────┐
│  TMRS Score                                              │
│                                                          │
│   Normalized:  31.4 / 100  🟡 Watch                      │
│   Raw:         27.0 / 86                                 │
│                                                          │
│   ⚠️ 부분 구현 상태 (Coverage 65%)                        │
│      Layer 1: 6/12 (50%)                                 │
│      Layer 2: 6/8  (75%)                                 │
│      Layer 3: 4/7  (57%)                                 │
│      Divergence: 1/5 (20%)                               │
└─────────────────────────────────────────────────────────┘
```

해석 등급은 **normalized_score 기준** 으로 적용 (기존 0–25 / 26–40 등 구간 그대로 사용).

#### 1.4.7 경고 표시 로직

- `overall_coverage < 0.50` → 🔴 "심각한 부분 구현" 경고
- `overall_coverage 0.50 ~ 0.80` → 🟡 "부분 구현" 경고  
- `overall_coverage >= 0.80` → 경고 없음

#### 1.4.8 ADR 작성

`docs/decisions/2026-04-15-stage2-coverage-ratio.md`

내용: normalized vs raw 분리 사유, overall_coverage 가중 평균 방식, UI 경고 임계.

### 1.5 Stage 2.5 — CP-EFFR 정식 처리 결정

#### 1.5.1 배경

Stage 1 에서 CP-EFFR 지표를 cap=0 (점수 기여 0) 으로 보류했음. 사유: v1.0 문서 Layer 2 에 없는 지표이며, Layer 1 의 A2/P2-AA Spread 와 redundancy 가능성. 

Stage 2 에서 정식 처리 결정 필요.

#### 1.5.2 분석 작업

**Step 1 — 데이터 가용성 확인**

```python
# CP-EFFR 와 A2/P2-AA Spread 의 historical 데이터 추출
cp_effr_data = conn.execute("""
    SELECT date, value FROM cp_effr_history 
    ORDER BY date
""").fetchall()  # 또는 실제 테이블명 확인

cp_aa_data = conn.execute("""
    SELECT date, value FROM cp_30d 
    ORDER BY date
""").fetchall()
```

**Step 2 — 상관관계 계산**

```python
import pandas as pd
import numpy as np

# 두 시계열을 같은 날짜로 정렬
df_cp_effr = pd.DataFrame(cp_effr_data, columns=['date', 'cp_effr'])
df_cp_aa = pd.DataFrame(cp_aa_data, columns=['date', 'cp_aa'])
merged = df_cp_effr.merge(df_cp_aa, on='date')

# Pearson 상관계수
corr_pearson = merged['cp_effr'].corr(merged['cp_aa'])

# 일간 변화율 상관계수
merged['cp_effr_chg'] = merged['cp_effr'].diff()
merged['cp_aa_chg'] = merged['cp_aa'].diff()
corr_changes = merged['cp_effr_chg'].corr(merged['cp_aa_chg'])

print(f"Level correlation: {corr_pearson:.3f}")
print(f"Daily change correlation: {corr_changes:.3f}")
```

**Step 3 — 결정 기준**

| 상관계수 (level + change) | 결정 |
|---|---|
| 둘 다 > 0.80 | **완전 redundancy → CP-EFFR 영구 cap=0 유지, 지표 자체 제거 검토** |
| 둘 다 0.50 ~ 0.80 | **부분 redundancy → CP-EFFR cap=2 (낮은 가중치) 부여, snapshot 유지** |
| 둘 다 < 0.50 | **독립 신호 → CP-EFFR cap=3 정식 가중치 부여, Layer 2 에 정식 편입** |
| Mixed (level 높고 change 낮음 등) | **TW 에게 결과 공유 후 결정** |

#### 1.5.3 Layer 2 가중치 영향

CP-EFFR 가 정식 가중치 받는 경우:
- 부분 redundancy (cap=2): Layer 2 max 24 → 26
- 독립 신호 (cap=3): Layer 2 max 24 → 27

Layer 2 spec 30 점 회복에 점진적 기여.

#### 1.5.4 ADR 작성

`docs/decisions/2026-04-15-stage2-cp-effr-redundancy-decision.md`

내용:
- 상관관계 분석 결과 (수치 포함)
- 최종 결정 (cap 값)
- v1.0 사상과의 관계 (Layer 2 에 없던 지표를 어떻게 정당화할 것인가)
- 향후 재평가 시점 (예: 운영 1년 후)

### 1.6 Stage 2.6 — Korea CDS 대체 소스 조사 (조사만)

#### 1.6.1 배경

Stage 1 에서 Korea CDS 5Y 를 데이터 소스 부재로 제외 (Bloomberg/Refinitiv 유료 전용 판단). 그러나 무료 또는 저비용 대안이 있을 수 있음.

#### 1.6.2 조사 대상

| 소스 | URL | 평가 기준 |
|---|---|---|
| **KRX 공시** | https://data.krx.co.kr | 데이터 가용성, API 존재, 갱신 빈도 |
| **한국은행 ECOS** | https://ecos.bok.or.kr | 시계열 수집 가능성, API key 필요 여부 |
| **Investing.com** | https://www.investing.com/rates-bonds/south-korea-cds-5-years | 스크래핑 안정성, 차단 가능성 |
| **Yahoo Finance KS bond** | yfinance | Korea bond 관련 ticker 존재 여부 |
| **CME / ICE 공개 데이터** | 각 거래소 | Korea CDS futures/options 가용성 |
| **금융감독원 / 신용평가사** | 한국 공시 | CDS 관련 통계 보고서 |

#### 1.6.3 조사 산출물

`docs/research/korea-cds-data-sources.md` 작성. 형식:

```markdown
# Korea CDS 5Y Data Source Research

## Date: 2026-04-15
## Stage: 2.6
## Status: Research only (no implementation)

## Sources Evaluated

### 1. KRX 공시
- URL: https://data.krx.co.kr
- Data availability: [Yes/No/Partial]
- API: [Yes/No, 인증 방식]
- Update frequency: [daily/weekly/manual]
- Cost: [무료/유료/조건부]
- Implementation feasibility: [High/Medium/Low]
- Notes: ...

### 2. 한국은행 ECOS
... (동일 형식)

(나머지 소스들)

## Recommendation

- 1순위 추천 소스: ...
- 사유: ...
- 예상 구현 작업량: ...
- Stage 2.6 후속 작업으로 분리하는 사유: ...

## Decision

본 조사 결과를 바탕으로 다음 중 결정:
- [ ] 즉시 구현 (Stage 2 범위 확장)
- [ ] 별도 Stage 로 분리 (예: Stage 2.7 또는 Stage 6)
- [ ] 영구 보류 (소스 부재 확정)
```

#### 1.6.4 ADR 작성

`docs/decisions/2026-04-15-stage2-korea-cds-research.md`

조사 결과 요약 + 결정 (구현 시점 / 별도 Stage / 영구 보류).

### 1.7 Stage 2.7 — Stage 1 보류 사항 검증

#### 1.7.1 Telegram 알람 실제 발송 테스트

Stage 1 에서 코드는 작성되었으나 실제 발송 검증은 안 됨.

**작업 내용**:

```python
# 테스트 트리거 함수 작성
def test_inverse_turkey_alert():
    """
    Stage 2.7 검증 — 실제 Telegram 발송 테스트
    """
    test_payload = {
        'level': 1,
        'tmrs_total': 99.9,  # 테스트 값
        'l1_score': 22.5,
        'l2_score': 15.0,
        'l3_score': 3.0,
        'l12_avg': 0.40,
        'l3_norm': 0.20,
        'timestamp': datetime.now(),
        'is_test': True,
    }
    return send_inverse_turkey_alert(test_payload)
```

테스트 메시지 포맷:
```
🧪 [TEST] Inverse Turkey Alert [Level 1]
This is a Stage 2.7 verification message.
실제 알람이 아닙니다. 시스템 작동 확인 중.
Time: 2026-04-15 HH:MM KST
```

**검증 항목**:
- [ ] Telegram bot token 정상 작동
- [ ] 메시지 수신 확인 (TW 가 Telegram 에서 직접)
- [ ] 24h dedup 작동 확인 (테스트 메시지 2회 발송 시 1회만 받음)
- [ ] 메시지 포맷 가독성

#### 1.7.2 3개 신규 지표 historical backfill 완전성 확인

```python
def verify_stage1_backfill():
    for table in ['single_b_oas', 'ig_oas', 'lqd_prices']:
        rows = conn.execute(f"""
            SELECT COUNT(*) cnt, MIN(date) oldest, MAX(date) latest
            FROM {table}
        """).fetchone()
        
        # 3년치 약 750 거래일 기준
        is_complete = rows['cnt'] >= 700
        print(f"{table}: {rows['cnt']} rows | {rows['oldest']} ~ {rows['latest']} | {'OK' if is_complete else 'INCOMPLETE'}")
```

부족하면 추가 backfill 실행.

#### 1.7.3 v1.0.1 TMRS 이력 최근 7일 검토

```python
def verify_v101_history():
    rows = conn.execute("""
        SELECT calculated_at, total_score, l1_score, l2_score, 
               l3_score, div_score, inverse_turkey
        FROM tmrs_scores
        WHERE score_version = 'v1.0.1'
        ORDER BY calculated_at DESC LIMIT 50
    """).fetchall()
    
    # 시간 간격 일관성 (스케줄러 정상 작동 여부)
    # Score 변동 추세
    # Inverse Turkey 발화 여부
```

#### 1.7.4 ADR 작성

`docs/decisions/2026-04-15-stage2-stage1-validation.md`

Stage 1 의 모든 컴포넌트 작동 확인 결과 + 발견된 이슈 + 조치.

---

## 2. Stage 2 완료 조건

### 2.1 체크리스트

#### 코드 변경

- [ ] 1.1 HYG daily 완전 구현
  - [ ] DB 테이블 + fetch 함수 + 스케줄러
  - [ ] Historical backfill (3년)
  - [ ] 점수 엔진 연동 (가중 4점, inverse direction)
  - [ ] snapshot 추가 (cap/unit/layer 포함)
  - [ ] Credit 탭 UI
- [ ] 1.2 HYG 5day 완전 구현
  - [ ] 계산 함수
  - [ ] 점수 엔진 연동 (가중 3점, inverse direction)
  - [ ] snapshot 추가
  - [ ] Credit 탭 UI
- [ ] 1.4 Coverage Ratio 출력 체계
  - [ ] TMRSOutput 데이터 구조 확장
  - [ ] LAYER_SPEC 상수 정의
  - [ ] Coverage 계산 함수
  - [ ] Normalized score 계산 함수
  - [ ] DB 컬럼 추가 (필요 시) — `tmrs_scores` 에 신규 컬럼들
  - [ ] Signal Desk UI 변경 (normalized + raw + coverage 표시)
  - [ ] 경고 임계 로직 (< 50%, 50-80%, ≥ 80%)
- [ ] 1.5 CP-EFFR 정식 처리 결정
  - [ ] 상관관계 분석 코드
  - [ ] 결과 기반 cap 결정
  - [ ] Layer 2 가중치 업데이트 (필요 시)

#### 조사 / 검증

- [ ] 1.6 Korea CDS 소스 조사 완료
  - [ ] `docs/research/korea-cds-data-sources.md` 작성
  - [ ] 권장 소스 결정
- [ ] 1.7.1 Telegram 알람 실제 발송 테스트
- [ ] 1.7.2 Historical backfill 완전성 확인
- [ ] 1.7.3 v1.0.1 TMRS 이력 검토

#### 문서

- [ ] ADR 7개 작성
  - [ ] 2026-04-15-stage2-hyg-daily.md
  - [ ] 2026-04-15-stage2-hyg-5day.md
  - [ ] 2026-04-15-stage2-coverage-ratio.md
  - [ ] 2026-04-15-stage2-cp-effr-redundancy-decision.md
  - [ ] 2026-04-15-stage2-korea-cds-research.md
  - [ ] 2026-04-15-stage2-stage1-validation.md
  - [ ] 2026-04-15-stage2-layer2-final-state.md (Layer 2 의 Stage 2 종료 시점 최종 가중치 정리)

#### 동기화

- [ ] 모든 sub-stage 가 GitHub main 에 merge 완료
- [ ] Replit 에서 sync_from_github.py 실행 후 정상 작동 확인
- [ ] 신규 데이터 (HYG) fetch 정상

### 2.2 TW 검토 요청 시 공유 사항

각 sub-stage 완료 시:

1. **변경 파일 리스트** (git diff 요약)
2. **DB 변경 사항** (신규 테이블, 스키마 변경)
3. **TMRS 계산 결과 before/after**
   - Layer 2 score 변화
   - Total score 변화 (raw + normalized)
   - Coverage ratio 변화
4. **신규 지표 현재값 + 분포** (HYG)
5. **상관관계 분석 결과** (CP-EFFR)
6. **Korea CDS 조사 결과 요약**
7. **Telegram 알람 테스트 결과** (스크린샷 또는 메시지 ID)
8. **PR URL** + merge 여부
9. **발견한 이슈/이견**

### 2.3 Stage 2 완료 후 예상 상태

```
Layer 2 max 점수: 17 → 24 (Korea CDS 제외)
Layer 2 활성 지표 수: 5 → 7 (HYG 2개 추가)

Coverage Ratio:
  Layer 1: 6/12 (50%) [변화 없음]
  Layer 2: 5/8 → 7/8 (62.5% → 87.5%)
  Layer 3: 4/7 (57%) [변화 없음]
  Divergence: 1/5 (20%) [변화 없음, Stage 4 에서 ERS 도입 시 변화]
  Overall: 약 55% (가중 평균)

TMRS:
  Raw score: 현재 26.5 → 시장 stress 정도에 따라 변동
  Max achievable: 86 (현재) → 93 (Stage 2 후, HYG 추가)
  Normalized: 30.8 → ?

Inverse Turkey 트리거:
  Stage 1: 구조적으로 불가능에 가까움
  Stage 2: HYG Stress/Crisis 시 즉시 트리거 가능
```

---

## 3. 작업 원칙 재확인

### 3.1 반드시 지킬 것

1. **새 feature branch 에서 작업** — `claude/stage2-*` 형식
2. **각 sub-stage 별 PR 분리** — 단, 관련된 작업 묶을 수 있음 (예: HYG daily + HYG 5day 한 PR)
3. **PR base 는 main**, base 가 feature branch 가 아님
4. **각 PR 본문에 ADR 링크 포함**
5. **TW 검토 없이 다음 sub-stage 착수 금지**
6. **Solo Cap 규칙 유지**
7. **v1.0 사상과 충돌 시 즉시 TW 문의**
8. **score_version 'v1.0.1' 유지** (Stage 2 도 v1.0.1 의 일부)

### 3.2 피할 것

1. **이전 feature branch (claude/analyze-financial-tracker-iZh57) 에 추가 커밋**
2. **sync_from_github.py BRANCH 변수 변경** (이미 main 으로 정렬됨)
3. **Layer 2 max 를 30 으로 맞추려고 임의 가중치 부여** (Korea CDS / GSIB CDS 가 0 인 것은 의도)
4. **snapshot 기존 key 임의 변경** (cap/unit/layer 추가는 OK, 의미 변경은 금지)
5. **Stage 1 의 ADR 수정** (new ADR 만 추가)
6. **threshold_table_version 변경** (Stage 2 는 임계값 신설 없음)

### 3.3 의문 발생 시

다음 상황 발생 시 즉시 TW 에게 문의:

- v1.0 문서와 현실 코드가 충돌하는 지점 (Stage 1 의 HY OAS 7pt 같은 사례)
- HYG fetch 시 yfinance API 변경/오류
- CP-EFFR 상관관계가 mixed signal (level 높고 change 낮은 등)
- Korea CDS 조사 중 의외의 발견 (예: 매우 좋은 무료 소스)
- Coverage Ratio 의 spec 지표 수 정의 모호성
- v1.0 의 Layer 1·3 spec 이 현실과 다른 점 발견 (Stage 3 에서 다룰 사항이지만 발견 시 보고)

---

## 4. 참조 문서

GitHub main 에 모두 존재:

- `Financial_Tracker_Scoring_Logic_in Total.md` — v1.0 통합문서 (사상적 baseline)
- `Financial_Tracker_v1.0.1_Instructions.md` — 전체 v1.0.1 지시서
- `Stage1_Emergency.md` — Stage 1 긴급 지시서
- `TW_Financial_App_Reference.md` — TW 작업 컨텍스트
- `docs/decisions/` 의 Stage 1 ADR 7개 — 의사결정 이력
- `scripts/migrations/0001_add_score_version.py` — Migration 패턴 참고

---

## 5. Stage 전체 로드맵 (참고)

```
[Stage 1 — 완료] 2026-04-14
  ├─ Single-B OAS 추가 ✓
  ├─ IG OAS 추가 ✓
  ├─ LQD 추가 ✓
  ├─ score_version 컬럼 ✓
  ├─ Telegram Inverse Turkey ✓
  ├─ Inverse Turkey hotfix ✓
  └─ ADR 7개 ✓

[Stage 2 — 본 지시서] 2026-04-15 ~
  ├─ HYG daily + 5day 추가
  ├─ Coverage Ratio 출력 체계
  ├─ CP-EFFR 정식 처리 결정
  ├─ Korea CDS 소스 조사
  ├─ Stage 1 보류 사항 검증
  └─ ADR 7개

[Stage 3] Stage 2 검토 후 — 명칭/임계 정리
  ├─ FRA-OIS → SOFR Term Premium 명칭 정리
  ├─ SOFR Term Premium 임계값 적용 (percentile 기반)
  ├─ MOVE Index percentile 병기
  └─ RRP 지표 이원화 (잠재적 — 이미 단일 지표로 운영 중)

[Stage 4] Stage 3 검토 후 — ERS v0
  ├─ ERS Tier 1 구현 (스케줄 이벤트)
  ├─ ERS UI 탭
  └─ TMRS-ERS Divergence 4사분면 위젯

[Stage 5+] GPT v1.1 피드백 통합 (Velocity / Persistence / Backtesting)

[최종] v1.0.1 → v1.1 Implementation Delta 문서 작성
```

---

## 6. 착수 메시지 (TW → Claude Code)

이 문서를 GitHub main 에 업로드한 후, Claude Code 에 다음 메시지를 전달:

> Stage 1 이 PR #1 (1cb668a) 으로 GitHub main 에 merge 완료되어 Stage 2 를 시작한다.
>
> **먼저 `Stage2_Instructions.md` (또는 GitHub main 의 해당 경로) 를 전체 읽어줘.** 특히 **Section 0.5 (Claude Code 가 모르는 변경 사항)** 를 반드시 먼저 확인해야 해. Stage 1 이후 GitHub 동기화 정비, sync 도구 변경, baseline 확정 등의 변경이 있어서 너가 마지막으로 알고 있는 상태와 다를 수 있어.
>
> 읽은 후 다음을 보고해줘:
>
> 1. Section 0.5 의 baseline 변경사항 이해도 요약 (3-5줄)
> 2. Stage 2 의 7개 sub-stage 중 작업 우선순위 제안
> 3. PR 분리 전략 제안 (어느 sub-stage 들을 묶을지)
>
> 이 3가지 보고 후 내가 검토하고 sub-stage 1 부터 착수 지시 줄게.
>
> **중요한 작업 원칙**:
> - 새 feature branch 사용 (예: `claude/stage2-hyg`, `claude/stage2-coverage` 등)
> - 이전 feature branch (`claude/analyze-financial-tracker-iZh57`) 에 추가 커밋 금지
> - PR base 는 항상 main
> - 각 sub-stage 완료 후 내 검토 후에 다음 진행
> - sync_from_github.py BRANCH 변수 변경 금지 (이미 main 으로 정렬됨)
>
> Stage 2 시작 준비해줘.

---

**끝 (End of Stage 2 Instructions)**

*Financial Tracker — v1.0.1 Stage 2 Instructions*  
*작성: 2026-04-15 | TW × Claude Opus 4.6*
