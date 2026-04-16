# Stage 2.0: JPY 데이터 인프라 구축

**Status**: Accepted  
**Date**: 2026-04-17  
**Stage**: 2.0  
**Related PR**: PR #7

---

## Context

v1.0 카테고리 4.5에서 USD/JPY Cross-Currency Basis가 Layer 1의 주요 지표로 명시되어 있음:
- USD/JPY 1M Basis: 5pt
- USD/JPY 3M Basis: 4pt

현재 `jpy_swap_data` 테이블과 `_jpy_annualized()` 함수는 이미 구현되어 있으나,
TMRS 점수 산출과는 완전히 단절된 상태. 실시간 대시보드 표시만 구현됨.

### 즉시 점수화 불가한 이유

1. **임계값 미확정**: v1.0 카테고리 3.4.4의 임계값 방향성 재해석 필요 (Section B)
2. **데이터 분포 미파악**: percentile 기반 임계 결정을 위한 이력 데이터 부족
3. **구조적 이해 부족**: Carry Unwind 신호 방향이 v1.0 원문과 GPT 프레임워크 간 불일치

### 30일 대기 전략

지금 당장 점수화 대신 데이터 인프라를 먼저 구축하고, 30일 누적 후 분포를 분석하여
percentile 기반으로 임계를 결정한다 (Stage 2.4).

---

## Decision

### 1. `jpy_swap_daily` 테이블 신설

```sql
CREATE TABLE IF NOT EXISTS jpy_swap_daily (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    date              TEXT NOT NULL,
    period            TEXT NOT NULL,
    bid               REAL NOT NULL,
    spot_rate         REAL NOT NULL,
    implied_yield_pct REAL,
    snapshot_time     TEXT NOT NULL,
    UNIQUE(date, period)
);
```

- `jpy_swap_data`(raw, 매 fetch마다 누적)와 달리 일별 대표값 1건만 저장
- `UNIQUE(date, period)`: 같은 날 재실행 시 갱신 (`INSERT OR REPLACE`)
- `implied_yield_pct`: `_jpy_annualized(bid, spot_rate, days)` 계산값 저장

### 2. `save_jpy_daily_snapshot()` 함수

매일 KST 08:00에 5개 만기(1M/3M/3Y/7Y/10Y)의 그날 최신 값을 저장.

- 오늘 fetch가 없으면 DB 내 가장 최신 값으로 fallback + 경고 로그
- `JPY_PERIOD_DAYS` 모듈 레벨 상수 신설 (기존 로컬 변수와 동일한 값, 재사용 가능)

### 3. 스케줄러: 매일 KST 08:00

```python
scheduler.add_job(
    save_jpy_daily_snapshot,
    trigger=CronTrigger(hour="8", minute="0", timezone="Asia/Seoul"),
    id="jpy_daily_snapshot",
    **_JOB_DEFAULTS,
)
```

**08:00 KST 선택 이유**:
- NY 마감(전일 16:00 EST = 다음날 06:00 KST) 직후
- 전일 종가 데이터 확보된 상태
- TMRS 일일 배치(08:00 KST)와 동일 시각 → 자연스러운 통합

### 4. `scripts/analyze_jpy_distribution.py`

30일 누적 후 Stage 2.4에서 실행하는 분포 분석 스크립트.

출력: 각 만기별 5일 변화 분포 (min/25p/50p/75p/90p/95p/max) + Stage 2.4 임계 후보값.

---

## Carry Unwind 사상 재해석 (Stage 3 공식 정정 예정)

### v1.0 카테고리 3.4.4 원문 방향
USD/JPY Basis 임계: ±5bp / -5~-10bp / -10~-20bp / < -20bp  
→ "음수가 클수록 위험" 전제

### GPT Yen Carry Unwind Framework의 통찰
> "Carry trade 판단은 change 부호가 아니라 **절대값 변화 기준**. 실제 unwind 신호는
> 음수값의 **절대값 감소** (0에 가까워짐) = 금리차 축소 = carry 약화."

### 현재 판단
- v1.0의 이론 체계는 맞지만, 임계값 방향성이 사상과 반대일 가능성
- Stage 2.0: 인프라만 구축, 임계 확정 보류
- Stage 2.4: 30일 분포 분석 후 percentile 기반 임계 확정
- Stage 3: v1.0 카테고리 3.4.4 공식 재해석 정정

### 분석 스크립트에서의 반영

`analyze_jpy_distribution.py`는 `abs(bid)` 변화 기준으로 분포를 계산:
- 양수 변화(절대값 증가) = carry 강화 = normal
- 음수 변화(절대값 감소) = carry 약화 = stress

---

## 기존 코드 불변 원칙

- `jpy_swap_data` 테이블: 변경 없음 (raw fetch 데이터 계속 누적)
- `_jpy_annualized()` 함수: 변경 없음 (신규 함수에서 그대로 호출)
- `refresh_jpy()` 함수: 변경 없음
- `_JPY_PERIOD_DAYS` (함수 내 로컬): 변경 없음 (모듈 레벨 `JPY_PERIOD_DAYS` 별도 추가)

---

## Stage 2.4 프리뷰

Stage 2.4 (약 2026-05-17 이후) 에서 수행할 작업:

1. `analyze_jpy_distribution.py` 실행 (30일 데이터)
2. 각 만기별 percentile 분포 확인
3. TW 검토 후 임계값 확정
4. Layer 1에 5개 JPY 지표 활성화:
   - `jpy_1m_carry_change`: 5pt
   - `jpy_3m_carry_change`: 4pt
   - `jpy_curve_flattening`: 3pt
   - `jpy_long_end_collapse`: 3pt
   - `usd_jpy_spot_5d`: 2pt (보조)
5. Carry Unwind Alert (4 Level)

---

## Consequences

**긍정적:**
- 30일 누적 데이터 확보 시작 (오늘부터 카운트)
- Stage 2.4 임계 결정을 위한 실증적 기반 마련
- `_jpy_annualized()` 재사용, 기존 코드 영향 없음

**부정적:**
- 없음 (인프라 추가만, 기존 기능 영향 없음)

**주의:**
- `jpy_swap_data`에 데이터가 없는 상태에서 앱 재시작 시 snapshot 0건 저장 + 경고 로그 (정상)
- 모든 만기 데이터가 있어야 의미 있는 분석 가능

---

## Reference

- `Financial_Tracker_Scoring_Logic_in Total.md` 카테고리 4.5 (USD/JPY Cross-Currency)
- `Stage2_0_Instructions.md` Section 1.2
- `TW_Financial_App_Reference.md` (JPY Swap 대시보드)
- `scripts/analyze_jpy_distribution.py`
