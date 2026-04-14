# Financial Tracker — v1.0.1 Stage 1 Instructions (긴급 재조정판)

> **Claude Code 작업 지시서 — Stage 1 착수**
> 본 문서는 v1.0.1 Instructions 문서의 Section 6 (질문 4개) 답변 검토 후 확정된 Stage 1 실행 지시서입니다.
> Section 6 답변에서 **시스템 구조적 결함이 발견** 되어 Stage 순서를 **긴급 재조정** 했습니다.

| 항목 | 내용 |
|---|---|
| **Baseline** | `docs/scoring/Financial_Tracker_v1.0.1_Instructions.md` |
| **Threshold Table 버전** | `v1.2026-04` → `v1.2026-04-01` (패치 bump) |
| **작업 기준일** | 2026-04-14 |
| **실제 TMRS 테이블** | `tmrs_scores` (기존 지시서의 `tmrs_history` 가 아님 — 정정) |

---

## 0. 긴급 재조정 배경 — 왜 Stage 순서를 바꾸는가

Section 6 질문 4개 답변 검토 중 현재 TMRS 상태가 **v1.0 사상이 정확히 경고한 "Inverse Turkey 상황" 에 도달했으나 시스템이 이를 감지하지 못하는 구조적 결함** 이 발견되었습니다.

### 0.1 현재 TMRS 실제 상태 (2026-04-14 13:37 KST)

```
Total:      20.60 → Tier: watch
Layer 1:    15.55 / 45  (34%)
Layer 2:     2.00 / 30  ( 7%)   ← 구조적 문제의 원인
Layer 3:     3.00 / 15  (20%)
Divergence:  0.06 / 10  ( 1%)
Inverse Turkey: 0              ← 켜졌어야 할 알람이 구조적으로 불가능
```

### 0.2 시장 실제 상태 (snapshot 기준)

```
Deep Layer 지표:
  - RRP 거의 소진 ($0.227B, Crisis 구간 지속)
  - Discount Window: Stress
  - TGA 주간변화: Stress
  - CP 스프레드 (A2/P2-AA): Watch
  - SOFR Term Premium: Watch

Surface Layer 지표:
  - VIX: 19.12 (Normal)
  - MOVE: 74.4 (Normal)
  - MOVE/VIX 비율: 3.89 (Normal)
```

이것은 v1.0 문서 카테고리 1 의 명제 *"Funding breaks first → Credit confirms → Equities react last"* 의 **진행 중인 교과서적 사례** 입니다.

### 0.3 왜 Inverse Turkey 알람이 꺼져 있는가

v1.0 문서 카테고리 4.11.1 정의:
```python
def inverse_turkey_trigger():
    l1_norm = l1_score / 45
    l2_norm = l2_score / 30
    l3_norm = l3_score / 15
    l12_avg = (l1_norm + l2_norm) / 2
    return l12_avg >= 0.40 and l3_norm <= 0.25
```

현재 `l12_avg = 0.206` (0.40 미만) — trigger 미충족은 맞지만, **원인이 사상적 문제가 아니라 Layer 2 저커버리지** 입니다.

### 0.4 Layer 2 커버리지 분석

```
Layer 2 스펙 지표 (v1.0):
  - Single-B OAS (7점) ← 최대 가중, 미구현
  - HY OAS (5점)       ← 구현됨 (현재 Normal)
  - IG OAS (3점)        ← 미구현
  - HYG daily (4점)     ← 미구현
  - HYG 5day (3점)      ← 미구현
  - LQD daily (2점)     ← 미구현
  - Korea CDS (4점)     ← 데이터 부재
  - GSIB CDS (2점)      ← 데이터 부재

현재 활성 Layer 2:
  - HY OAS: normal (0점)
  - CP-EFFR: watch (약 2점)
  - Layer 2 실제 기여 = 2.0 / 30 (7%)
```

Layer 2 max 가 명목상 30 점이지만 **실질 활성 가능 점수는 7점 내외**. 따라서 `l2_norm` 이 구조적으로 0.23 을 초과할 수 없어 Inverse Turkey 감지가 **원천 차단** 되어 있습니다.

### 0.5 결론 — 긴급 정비 필요

**"우리가 만든 조기경보 시스템이 조기경보를 내야 할 순간에 조기경보를 내지 못하는 상태"** 가 지금입니다. 명칭 정리나 임계값 조정보다 **Layer 2 응급 충실화가 최우선**입니다.

---

## 1. Stage 재조정 결과

### 기존 순서 (Instructions 문서 Section 7)

```
Stage 1 → 명칭/임계 정리 (FRA-OIS, MOVE, RRP)
Stage 2 → Layer 2 충실화
Stage 3 → ERS v0
```

### 긴급 재조정 순서

```
Stage 1 [긴급] → Single-B OAS 응급 추가 + IG OAS + LQD
Stage 2       → Layer 2 잔여 (HYG daily/5day) + Coverage Ratio
Stage 3       → 명칭/임계 정리 (기존 Stage 1 내용)
Stage 4       → ERS v0 (기존 Stage 3 내용)
```

### 변경 사유 요약

| 항목 | 기존 | 변경 | 사유 |
|---|---|---|---|
| 최우선 작업 | 명칭 정리 | Layer 2 응급 | 시스템 감지 기능 복원 |
| Single-B OAS | Stage 2 | Stage 1 | 가중 7점 — 최대 영향 |
| 명칭/임계 정리 | Stage 1 | Stage 3 | 기능 정상화 후 진행 |

---

## 2. 사전 확정 사항 (TW 결정 완료)

### 2.1 SOFR Term Premium 임계값 — Percentile 기반 권고안 수용

최근 6개월(97일) 분포:
```
Min : -1.08 bp    Mean : 17.07 bp
25p :  5.78 bp    Std  : 12.49 bp
50p : 14.67 bp
75p : 26.39 bp
90p : 34.77 bp
95p : 40.05 bp
Max : 47.25 bp
```

**확정 임계값**:

| Zone | Percentile | 해당 값 (bp, 2026-04 기준) | 비고 |
|---|---|---|---|
| Normal | < 75p | < 26 bp | 평상시 상위 25% 까지 정상 |
| Watch | 75p–90p | 26–35 bp | 경계 |
| Stress | 90p–95p | 35–40 bp | 뚜렷한 stress |
| Crisis | > 95p | > 40 bp | 최극단 5% |

**구현 방식**: Percentile 기반 + 절대값 병기 (카테고리 3.3 방법 D + A 병기, MOVE 와 동일 로직)

```python
SOFR_TERM_PREMIUM_THRESHOLDS_ABS = {
    'normal': 25,   # bp
    'watch': 35,
    'stress': 45,
    'crisis': 55,
}
SOFR_TERM_PREMIUM_THRESHOLDS_PCT = {
    'normal': 75,   # percentile
    'watch': 90,
    'stress': 95,
}
# 두 임계 중 더 보수적(높은 점수) 선택
```

이 임계값은 Stage 3 (명칭/임계 정리) 에서 적용. Stage 1 에서는 아직 반영 안 함.

### 2.2 마이그레이션 전략 — 옵션 A + 재계산 선택

snapshot 필드에 raw value 가 보존되어 있어 재계산 가능성 확인됨.

**확정 전략**:

```
Stage 1 착수 시:
  - tmrs_scores 에 score_version 컬럼 추가 (default 'v1.0')
  - 기존 22개 레코드는 'v1.0' 태깅 유지

Stage 2 완료 후 (선택):
  - 과거 22개 레코드를 새 가중치로 재계산 여부 검토
  - 재계산 시 'v1.0.1_retroactive' 테이블에 저장 (원본 보존)
  - UI 에서 원본/재계산 선택 가능
```

**재계산은 필수가 아닌 선택** 사항. TW 판단에 따라 Stage 2 완료 후 결정.

### 2.3 실제 테이블 이름 — `tmrs_scores`

기존 v1.0.1 Instructions 의 `tmrs_history` 는 잘못된 추측. 실제 테이블은 `tmrs_scores`. 모든 migration script 에서 이 이름 사용.

### 2.4 snapshot 스키마 (현재)

```json
{
  "sofr_effr": { "value": -3.0, "tier": "normal", "name": "SOFR-EFFR 스프레드" },
  "cp_aa_spread": { "value": 34.0, "tier": "watch", "name": "CP 스프레드 (A2/P2−AA)" },
  "rrp": { "value": 0.227, "tier": "crisis", "name": "RRP 잔고" },
  "sofr_term": { "value": 5.79, "tier": "watch", "name": "SOFR 텀 프리미엄" },
  "discount_window": { "value": 5873.0, "tier": "stress", "name": "Discount Window" },
  "tga": { "value": -99.3, "tier": "stress", "name": "TGA 주간변화" },
  "hy_oas": { "value": 2.94, "tier": "normal", "name": "HY OAS" },
  "cp_effr": { "value": 0.43, "tier": "watch", "name": "A2/P2 CP−EFFR" },
  "move": { "value": 74.42, "tier": "normal", "name": "MOVE Index" },
  "vix": { "value": 19.12, "tier": "normal", "name": "VIX 현물" },
  "skew": { "value": 156.93, "tier": "stress", "name": "CBOE SKEW" },
  "move_vix_ratio": { "value": 3.89, "tier": "normal", "name": "MOVE/VIX 비율" }
}
```

Stage 1 에서 **Single-B OAS, IG OAS, LQD** 3개 key 가 이 구조에 추가되어야 함.

---

## 3. Stage 1 작업 내용

**목표**: Layer 2 응급 충실화로 Inverse Turkey 감지 기능 복원

**예상 소요**: 3-4시간 (Claude Code 의 Section 6 답변 기준)

**범위**:
- 3개 신규 지표 (Single-B OAS, IG OAS, LQD) 데이터 수집 + 점수 엔진 연동 + UI
- score_version 컬럼 추가
- Layer 2 가중치 재분배 (Korea CDS / GSIB CDS 제외)
- Telegram 알람에 Inverse Turkey 트리거 연결 (보류 사항 해결)

### 3.1 Single-B OAS 추가 (최우선)

#### 3.1.1 데이터 수집

- **FRED series ID**: `BAMLH0A2HYBEY` (BofA ICE Single-B US High Yield OAS)
- **갱신 빈도**: 일별 (1일 lag 허용)
- **Historical backfill**: 최소 3년 (2023-01-01 이후)
- **DB 테이블 신규**: `single_b_oas`

```sql
CREATE TABLE single_b_oas (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL UNIQUE,
    oas_bp REAL NOT NULL,      -- basis points
    fetched_at TEXT NOT NULL
);
CREATE INDEX idx_single_b_oas_date ON single_b_oas(date);
```

- **Fetch 함수**: 기존 `fetch_fred_observations()` 패턴 복제
- **Scheduler**: 기존 HY OAS 스케줄에 합류 (매일 동일 시각)

#### 3.1.2 임계값 (v1.0 카테고리 3.5.1 원문)

| Zone | 임계 |
|---|---|
| Normal | < 350 bp |
| Watch | 350–450 bp |
| Stress | 450–600 bp |
| Crisis | > 600 bp |

Direction: `normal` (값이 클수록 stress)

#### 3.1.3 점수 엔진 연동

- **Layer**: 2 (Middle / Credit)
- **가중**: 7점 (Layer 2 내 최대)
- **Solo Cap**: 7점
- **Mode**: interpolated scoring

#### 3.1.4 snapshot 스키마 추가

```json
"single_b_oas": {
  "value": <실제 bp 값>,
  "tier": "normal" | "watch" | "stress" | "crisis",
  "name": "Single-B OAS"
}
```

#### 3.1.5 UI 추가

- **위치**: Credit 탭 (기존 HY OAS 카드 옆)
- **위젯 형식**: 기존 HY OAS 카드를 그대로 복제하여 Single-B OAS 로 적용
- **차트**: 최근 1년 시계열 + 임계 구간 overlay
- **표시**: 현재 값 / Zone / 기여 점수

### 3.2 IG OAS 추가

#### 3.2.1 데이터 수집

- **FRED series ID**: `BAMLC0A0CM` (BofA ICE US Corporate Master OAS)
- **갱신 빈도**: 일별 (1일 lag 허용)
- **DB 테이블 신규**: `ig_oas`

```sql
CREATE TABLE ig_oas (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL UNIQUE,
    oas_bp REAL NOT NULL,
    fetched_at TEXT NOT NULL
);
CREATE INDEX idx_ig_oas_date ON ig_oas(date);
```

#### 3.2.2 임계값 (v1.0 카테고리 3.5.1)

| Zone | 임계 |
|---|---|
| Normal | < 100 bp |
| Watch | 100–130 bp |
| Stress | 130–180 bp |
| Crisis | > 180 bp |

Direction: `normal`

#### 3.2.3 점수 엔진 연동

- **Layer**: 2
- **가중**: 3점
- **Solo Cap**: 3점

#### 3.2.4 snapshot 추가

```json
"ig_oas": { "value": <bp>, "tier": "<zone>", "name": "IG OAS" }
```

#### 3.2.5 UI

Credit 탭에 카드 추가 (HY OAS / Single-B OAS 와 같은 섹션).

### 3.3 LQD ETF 추가

#### 3.3.1 데이터 수집

- **yfinance ticker**: `LQD`
- **지표**: `lqd_daily_change_pct` (전일 대비 변화율)
- **갱신 빈도**: 일중 (HYG 와 동일 주기)
- **DB 테이블 신규**: `lqd_prices`

```sql
CREATE TABLE lqd_prices (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    close_price REAL NOT NULL,
    daily_change_pct REAL,
    fetched_at TEXT NOT NULL
);
CREATE INDEX idx_lqd_timestamp ON lqd_prices(timestamp);
```

#### 3.3.2 임계값 (v1.0 카테고리 3.5.2)

| Zone | 임계 |
|---|---|
| Normal | > -0.5% |
| Watch | -0.5% ~ -1% |
| Stress | -1% ~ -2% |
| Crisis | < -2% |

Direction: `inverse` (값이 작을수록/음수가 클수록 stress)

#### 3.3.3 점수 엔진 연동

- **Layer**: 2
- **가중**: 2점
- **Solo Cap**: 2점

#### 3.3.4 snapshot 추가

```json
"lqd_daily": { "value": <pct>, "tier": "<zone>", "name": "LQD 일간 변화율" }
```

#### 3.3.5 UI

Credit 탭에 카드 추가 (보조 지표로서).

### 3.4 Layer 2 가중치 재분배

#### 3.4.1 Stage 1 종료 시점의 Layer 2 구성

```
Single-B OAS      7   [신규]
HY OAS            5   [기존]
IG OAS            3   [신규]
LQD daily         2   [신규]
CP-EFFR           3   [기존 - 재확인]
(HYG daily        4)  [Stage 2 에서 추가]
(HYG 5day         3)  [Stage 2 에서 추가]
(Korea CDS        0)  [optional, 데이터 부재]
(GSIB CDS         0)  [optional, 데이터 부재]
─────────────────────
Stage 1 종료 후 Layer 2 max: 20점
Stage 2 종료 후 Layer 2 max: 27점 (HYG 추가 후)
v1.0 스펙 Layer 2 max      : 30점 (Korea CDS + GSIB 포함 시)
```

#### 3.4.2 CP-EFFR 가중 확인

현재 snapshot 에 `cp_effr` 가 있고 `tier: watch` 로 작동 중. 현재 코드의 가중치 확인 필요. v1.0 문서에는 명시 없음 — Claude Code 의 독자 구현으로 추정.

**작업**: CP-EFFR 의 현재 가중치 확인 후 유지 여부 판단. 가중 3점으로 잠정 명시. TW 검토 시 재논의.

#### 3.4.3 Inverse Turkey 동작 시뮬레이션

Stage 1 완료 후 예상 상태 (현재 시장 조건 유지 가정):

```
Layer 2 실제 기여 예상:
  - Single-B OAS: normal (현재 수준) → 0점
  - HY OAS: normal → 0점
  - IG OAS: normal → 0점
  - LQD daily: normal → 0점
  - CP-EFFR: watch → 약 1.2점
  - 합계: 약 1.2 / 20 (6%)
  
l2_norm = 0.06
l1_norm = 0.346 (변화 없음)
l12_avg = 0.203

여전히 Inverse Turkey 트리거 미충족 (0.40 미만)
```

**중요 인사이트**: Stage 1 만으로는 Inverse Turkey 감지 복원이 불충분. Single-B OAS / IG OAS / LQD 가 모두 현재 *Normal* 이기 때문. 

Stage 1 의 가치는 **"향후 Credit stress 가 발생하면 즉시 감지할 수 있는 상태로 만드는 것"** 이며, 현재 시점의 즉시 감지 복원은 Stage 2 (HYG 포함) 완료 후에 가능할 가능성이 높음.

### 3.5 score_version 컬럼 추가

#### 3.5.1 Migration Script

**파일 위치**: `scripts/migrations/0001_add_score_version.py`

```python
"""
Migration: Add score_version column to tmrs_scores
Date: 2026-04-14
Related: v1.0.1 Stage 1
"""
import sqlite3

def migrate(db_path="data.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 컬럼 존재 여부 확인
    cursor.execute("PRAGMA table_info(tmrs_scores)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'score_version' not in columns:
        cursor.execute("""
            ALTER TABLE tmrs_scores
            ADD COLUMN score_version TEXT DEFAULT 'v1.0'
        """)
        print("✓ score_version 컬럼 추가 완료")
    else:
        print("✗ score_version 컬럼 이미 존재 — 스킵")
    
    # 기존 22개 레코드는 'v1.0' 유지 (DEFAULT)
    cursor.execute("""
        UPDATE tmrs_scores SET score_version = 'v1.0'
        WHERE score_version IS NULL
    """)
    
    conn.commit()
    
    # 검증
    cursor.execute("""
        SELECT score_version, COUNT(*) 
        FROM tmrs_scores 
        GROUP BY score_version
    """)
    print("\n버전별 레코드 수:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}")
    
    conn.close()

if __name__ == "__main__":
    migrate()
```

#### 3.5.2 Stage 1 이후 신규 레코드 태깅

TMRS 계산 로직에 다음 추가:

```python
SCORE_VERSION = "v1.0.1"  # Stage 1 이후부터

def save_tmrs_score(..., score_version=SCORE_VERSION):
    conn.execute("""
        INSERT INTO tmrs_scores (..., score_version) 
        VALUES (..., ?)
    """, (..., score_version))
```

#### 3.5.3 threshold_table_version bump

시스템 상수 파일에서 버전 업데이트:

```python
# config.py 또는 constants.py
THRESHOLD_TABLE_VERSION = "v1.2026-04-01"  # 기존 v1.2026-04 에서 bump
```

이 값은 TMRS 계산 결과에 포함되어 로깅/UI 표시.

### 3.6 Telegram Inverse Turkey 알람 연결 (보너스)

v1.0.1 Instructions 에는 없었으나, Claude Code 비교표에서 *"Telegram 알람 TMRS 연동 — Inverse Turkey 트리거 시 자동 알람 미연결"* 로 보류된 사항. Stage 1 에 포함하여 해결.

#### 3.6.1 작업 내용

- 기존 `telegram_alerts.py` 의 Inverse Turkey hook 구현
- 트리거 조건: `inverse_turkey_level` 이 0 → 1 로 전환되거나 1 → 2 로 승격될 때
- 메시지 포맷:

```
🚨 Inverse Turkey Alert [Level 1]
Time: 2026-04-XX HH:MM KST
TMRS: 45.2 / Tier: Yellow Alert

Layer 1 (Deep):  28.5 / 45  (63%)
Layer 2 (Middle): 18.2 / 27  (67%)
Layer 3 (Surface): 3.0 / 15  (20%)

L1+L2 avg: 0.65  (threshold 0.40 ↑)
L3 norm:   0.20  (threshold 0.25 ↓)

해석: 진앙(Deep/Middle)에서 stress 누적 중, 
      표면(Surface)은 평온 — Inverse Turkey 패턴 진입.
```

#### 3.6.2 De-duplication

같은 Level 에서 반복 알람 방지. 24시간 내 같은 Level 알람 1회만 발송.

### 3.7 테스트 및 검증

#### 3.7.1 Smoke Test

```bash
# Migration 실행
python scripts/migrations/0001_add_score_version.py

# 신규 지표 fetch 테스트
python -c "from dashboard.fetchers import refresh_single_b_oas; refresh_single_b_oas()"
python -c "from dashboard.fetchers import refresh_ig_oas; refresh_ig_oas()"
python -c "from dashboard.fetchers import refresh_lqd; refresh_lqd()"

# TMRS 재계산
python -c "from dashboard.scoring import compute_tmrs; print(compute_tmrs())"
```

#### 3.7.2 검증 항목

- [ ] `single_b_oas`, `ig_oas`, `lqd_prices` 테이블 생성 확인
- [ ] FRED / yfinance 데이터 수집 성공
- [ ] Historical backfill 수행 (최소 1년)
- [ ] 새 TMRS 계산에 3개 지표 반영 확인
- [ ] `snapshot` JSON 에 3개 key 추가 확인
- [ ] Credit 탭 UI 에 3개 카드 표시 확인
- [ ] `score_version` 컬럼 추가 + 기존 데이터 'v1.0' 태깅 확인
- [ ] Layer 2 점수 상승 확인 (기존 2.0 → 예상 약 1.5-4.0, Zone 에 따라)
- [ ] Inverse Turkey trigger 조건 재계산 정상 작동 확인

### 3.8 ADR 작성

각 작업 단위에 대해 `docs/decisions/` 에 ADR 작성:

- `2026-04-14-stage1-layer2-emergency.md` — 긴급 재조정 배경
- `2026-04-14-stage1-single-b-oas.md`
- `2026-04-14-stage1-ig-oas.md`
- `2026-04-14-stage1-lqd.md`
- `2026-04-14-stage1-score-version-column.md`
- `2026-04-14-stage1-telegram-inverse-turkey.md`

**ADR 형식**:
```markdown
# [제목]
Status: Accepted
Date: 2026-04-14
Stage: 1

## Context
v1.0 문서와 현재 시스템 상태에서 왜 이 결정이 필요했는가.

## Decision
무엇을 결정했는가 (임계값/가중치/테이블 스키마 포함).

## Consequences
- 긍정적: [효과]
- 부정적: [side effect / breaking change]
- DB 영향: [migration 필요 여부]

## Alternatives considered
[다른 방안 및 기각 사유]

## Reference
- v1.0 scoring_logic 카테고리 X.Y
- v1.0.1 Instructions Section Z
- Section 6 답변 결과
```

---

## 4. Stage 1 완료 조건

### 4.1 체크리스트

- [ ] 3.1 Single-B OAS 완전 구현
  - [ ] DB 테이블 + fetch 함수 + 스케줄러
  - [ ] Historical backfill (3년)
  - [ ] 점수 엔진 연동 (가중 7점)
  - [ ] snapshot 추가
  - [ ] Credit 탭 UI
- [ ] 3.2 IG OAS 완전 구현
  - [ ] DB 테이블 + fetch 함수
  - [ ] 점수 엔진 연동 (가중 3점)
  - [ ] snapshot 추가
  - [ ] Credit 탭 UI
- [ ] 3.3 LQD 완전 구현
  - [ ] DB 테이블 + fetch 함수
  - [ ] 점수 엔진 연동 (가중 2점)
  - [ ] snapshot 추가
  - [ ] Credit 탭 UI
- [ ] 3.4 Layer 2 가중치 재분배 완료
  - [ ] CP-EFFR 현재 가중치 확인 및 문서화
  - [ ] Layer 2 max 를 20점으로 고정 (Stage 1 종료 시점)
- [ ] 3.5 score_version 컬럼 추가
  - [ ] Migration script 실행
  - [ ] 기존 22개 레코드 'v1.0' 태깅
  - [ ] 신규 레코드 'v1.0.1' 태깅 로직
  - [ ] threshold_table_version 상수 bump
- [ ] 3.6 Telegram Inverse Turkey 알람 연결
  - [ ] Hook 구현
  - [ ] De-duplication
  - [ ] 메시지 포맷 구현
- [ ] 3.7 Smoke test 전체 항목 통과
- [ ] 3.8 ADR 6개 작성

### 4.2 TW 검토 요청 공유 사항

Stage 1 완료 시 다음 항목을 TW 에게 공유:

1. **변경 파일 리스트** — git diff 요약
2. **DB migration 결과** — 신규 테이블 생성 + score_version 컬럼 추가 검증
3. **TMRS 계산 결과 before/after**
   - Before: `snapshot` 에 12개 지표
   - After: `snapshot` 에 15개 지표 (3개 추가)
   - Layer 2 score 변화 (실제 수치)
   - Total score 변화
   - Inverse Turkey level 변화 (있다면)
4. **3개 신규 지표 현재 값 + 과거 1년 시계열 분포** — 각 지표의 현재 Zone 확인
5. **Credit 탭 스크린샷**
6. **ADR 6개 목록 + 각 문서 링크**
7. **발견한 이슈/이견** — 있으면 명시

### 4.3 TW 검토 후 Stage 2 착수

TW 검토 완료 전까지 **Stage 2 착수 금지**. 명시적 "Stage 2 진행" 지시가 있은 후에만 다음 단계로 이동.

---

## 5. 작업 원칙 재확인

### 5.1 반드시 지킬 것

1. **Breaking change 는 명시** — 특히 Layer 2 max 변화 (30 → 20) 는 기존 해석 구간과 충돌 가능성 있음
2. **각 Stage 별 PR 분리** — 3.1 / 3.2 / 3.3 / 3.5 / 3.6 각각 가능한 작은 단위 PR
3. **TW 검토 없이 다음 Stage 착수 금지**
4. **임의 사상 변경 금지** — v1.0 과 다른 결정이 필요하면 반드시 TW 와 상의

### 5.2 피할 것

1. **Layer 2 max 를 30 으로 유지하려고 임의 가중치 조정** — 사상 훼손
2. **Solo Cap 초과** — 3개 신규 지표 각자의 weight = cap
3. **snapshot 스키마 임의 변경** — 기존 12개 key 는 그대로 보존, 3개만 추가
4. **score_version 이 'v1.0.1' 인데 v1.0 지표 구성 사용** — Stage 1 종료 = v1.0.1 완성은 아님. 점진 이전.

### 5.3 의문 발생 시

구현 중 다음 상황 발생 시 TW 에게 즉시 문의:

- v1.0 문서와 현실 코드가 충돌하는 지점
- 임계값을 조정해야 할 데이터 상황
- Layer 2 가중치 재분배에 대한 다른 아이디어
- Telegram 알람 포맷 개선안
- ADR 작성 시 불명확한 사유

---

## 6. 참조 문서

- `docs/scoring/scoring_logic_v1.0.md` — 원본 통합문서
- `docs/scoring/Financial_Tracker_v1.0.1_Instructions.md` — 전체 지시서 (기존)
- `docs/scoring/Section6_Answers.md` — TW 가 제공한 Claude Code 답변 (권장 — 별도 보존)

---

## 7. Stage 전체 로드맵 (참고)

```
[Stage 1 — 긴급] 2026-04-14 ~ (2-3일)
  ├─ Single-B OAS 추가
  ├─ IG OAS 추가
  ├─ LQD 추가
  ├─ score_version 컬럼
  └─ Telegram Inverse Turkey 연결

[Stage 2] Stage 1 검토 후
  ├─ HYG daily + 5day 추가
  ├─ Coverage Ratio 필드 / UI
  ├─ Korea CDS 대체 소스 조사
  └─ (선택) 기존 22개 레코드 재계산

[Stage 3] Stage 2 검토 후 — 기존 Stage 1 내용
  ├─ FRA-OIS → SOFR Term Premium 명칭 정리
  ├─ SOFR Term Premium 임계값 적용 (Section 2.1 확정안)
  ├─ MOVE Index percentile 병기
  └─ RRP 지표 이원화

[Stage 4] Stage 3 검토 후 — 기존 Stage 3 내용
  ├─ ERS Tier 1 구현
  ├─ ERS UI 탭
  └─ TMRS-ERS Divergence 4사분면 위젯

[최종] 모든 Stage 완료 후
  └─ v1.0.1 Implementation Delta 문서 작성 + 깃허브 업로드
```

---

## 8. 착수 메시지 (TW → Claude Code)

이 문서와 함께 Claude Code 에 다음 메시지를 전달:

> Section 6 의 질문 4개 답변을 검토한 결과 **시스템 구조적 결함** 이 발견되어 Stage 순서를 긴급 재조정했다.
>
> `docs/scoring/Stage1_Emergency.md` 를 전체 읽어줘. 읽은 후 이해한 내용을 5-7줄로 요약해서 보여줘.
>
> 요약 확인 후, **Stage 1 의 체크리스트 (Section 4.1) 순서대로 착수**해줘. 단, 다음 사항을 지켜줘:
>
> 1. 각 지표 추가마다 **독립 PR** 로 분리 (3.1, 3.2, 3.3 각각)
> 2. Migration script (3.5) 는 가장 먼저 실행
> 3. 구현 중 v1.0 문서와 현실 코드가 충돌하면 **즉시 내게 문의** — 임의 결정 금지
> 4. 모든 작업에 대해 **ADR 6개 작성** (Section 3.8)
>
> Stage 1 전체 완료 후 Section 4.2 의 공유 사항 8개를 모두 정리해서 내게 보고해줘. **Stage 2 는 내 명시적 지시 전까지 착수 금지.**
>
> Stage 1 착수 시작해.

---

**끝 (End of Stage 1 Instructions)**

*Financial Tracker — v1.0.1 Stage 1 Emergency Instructions*
*작성: 2026-04-14 | TW × Claude Opus 4.6*
