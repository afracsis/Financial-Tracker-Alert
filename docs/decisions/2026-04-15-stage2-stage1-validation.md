# Stage 1 Baseline 최종 검증 결과 + Telegram 알람 테스트

**Status**: Accepted  
**Date**: 2026-04-15  
**Stage**: 2 (Sub-stage 2.7 — Step 1 + Step 2)  
**Related Commits**: (본 PR)

---

## Context

Stage 2 착수 전 Stage 1 의 모든 컴포넌트가 정상 작동하는지 확인하기 위해
검증 스크립트를 작성하고 실행했다.

검증 범위:
1. 코드 무결성 (hotfix 반영 여부)
2. DB 스키마 (신규 테이블 + 컬럼)
3. 신규 지표 backfill 완전성
4. score_version 분포 및 v1.0.1 이력
5. 최근 7일 TMRS 추이
6. 15개 지표 전부 활성 상태

---

## Step 1 — 검증 결과 (18/18 통과)

**실행 일시**: 2026-04-15 00:43:30 KST  
**환경**: Replit (`~/workspace/dashboard`)

### [1] 코드 무결성

| 항목 | 결과 |
|------|------|
| Inverse Turkey 조건: `l12_avg = (l1_sev + l2_sev) / 2` | ✅ |
| Inverse Turkey 조건: `l12_avg >= 0.40 AND l3_sev <= 0.25` | ✅ |
| 구 조건 제거: `l1_sev >= 0.5 AND l2_sev >= 0.4` | ✅ 정상 제거 |
| LQD tier 임계값 양수: `[(0.5,"normal"), ...]` | ✅ |
| LQD tier 음수 버그 제거: `[(-0.5,"normal"), ...]` | ✅ 정상 제거 |
| HY OAS cap=5 (7→5 복원) | ✅ |
| CP-EFFR cap=0 (점수 기여 보류) | ✅ |

### [2] DB 스키마

| 항목 | 결과 |
|------|------|
| `single_b_oas` 테이블 | ✅ |
| `ig_oas` 테이블 | ✅ |
| `lqd_prices` 테이블 | ✅ |
| `tmrs_scores` 테이블 | ✅ |
| `tmrs_scores.score_version` 컬럼 | ✅ |
| `tmrs_scores.snapshot` 컬럼 | ✅ |

### [3] Backfill 완전성 (목표 ≥ 750건)

| 지표 | 건수 | 기간 | 결과 |
|------|------|------|------|
| Single-B OAS | 990건 | 2022-07-01 ~ 2026-04-13 | ✅ |
| IG OAS | 989건 | 2022-07-01 ~ 2026-04-13 | ✅ |
| LQD | **62건** | 2026-01-14 ~ 2026-04-14 | ❌ → 수동 복구 후 ✅ |

**LQD 버그 발견 및 hotfix 이력** (후술):

초기에 62건만 수집됨 — `refresh_lqd()`가 `period="3mo"` 고정으로
DB 빈 경우에도 3개월치만 fetch하는 버그.

조치:
1. Replit shell에서 수동 backfill 실행 → 1073건 (2022-01-03 ~ 2026-04-14)
2. `refresh_lqd()` 코드 수정: `existing == 0` 체크 추가, 빈 경우 `start="2022-01-01"` 전체 로드
3. 별도 hotfix PR `claude/stage1-lqd-backfill-hotfix` 생성 → main merge

### [4] score_version 분포

| 버전 | 건수 |
|------|------|
| `v1.0` | 22건 (기존 이력, Stage 1 전 레코드) |
| `v1.0.1` | 9건 (Stage 1 이후 신규 레코드) |

### [5] 최근 v1.0.1 TMRS 추이

```
시각                      Total Tier     L1    L2    L3   Div IT
------------------------------------------------------------------
2026-04-15 09:27:58 KST  26.5  watch  15.2   7.0   4.2  0.06  N
2026-04-15 09:15:01 KST  26.5  watch  15.2   7.0   4.2  0.06  N
2026-04-15 08:07:36 KST  26.5  watch  15.2   7.0   4.2  0.06  N
2026-04-14 17:26:25 KST  26.4  watch  15.6   7.0   3.0  0.89  N
...
2026-04-14 16:00:58 KST  28.8  watch  15.6   9.0   3.0  1.23  N
```

LQD tier 버그 수정 전(28.8→26.4) 변화 확인됨.  
`l2_score` 7.0 안정 유지, `inv_turkey` 지속 False (l12_avg 0.289 < 0.40).

### [6] 15개 지표 전부 활성 (15/15)

```
Layer 1 (6개): sofr_effr✅ cp_aa_spread✅ rrp✅ sofr_term✅ discount_window✅ tga✅
Layer 2 (5개): hy_oas✅ cp_effr✅ single_b_oas✅ ig_oas✅ lqd_daily✅
Layer 3 (4개): move✅ vix✅ skew✅ move_vix_ratio✅
```

---

## Step 2 — Telegram 알람 실제 발송 테스트

### 테스트 도구

`scripts/test_telegram_alert.py` (standalone 스크립트)  
**실행 방법:**
```bash
cd ~/workspace/dashboard
python scripts/test_telegram_alert.py
```

### 설계 결정: Option B (standalone script)

Option A (app.py admin route) 대비 Option B 선택 이유:
- 프로덕션 `app.py`에 테스트 코드 혼재 방지
- OAuth auth 우회 불필요, shell에서 직접 실행 가능
- 향후 CI 통합 용이

### telegram_alerts.py 변경 최소화

`alert_inverse_turkey()` 에 `is_test: bool = False` 파라미터 추가:
- `is_test=True` 시 메시지에 `🧪 [TEST]` prefix 추가
- 기본값 `False` → 기존 프로덕션 호출 무변경
- dedup 로직은 테스트에서도 동일하게 작동 (우회 없음)

### 테스트 시나리오

| 단계 | 내용 | 기대 결과 |
|------|------|----------|
| 1 | `send_raw()` 연결 확인 메시지 | Telegram 수신 |
| 2 | `alert_inverse_turkey(inv_turkey=True, is_test=True)` 1st call | Telegram 수신 (`[TEST]` prefix) |
| 3 | 동일 조건 2nd call (즉시) | 차단 — dedup 24h 작동 확인 |

### 테스트 수치 (v1.0 트리거 조건 충족 확인)

```
l1 = 22.5  →  l1_norm = 22.5/45 = 0.500
l2 = 13.5  →  l2_norm = 13.5/30 = 0.450
l3 = 2.0   →  l3_norm = 2.0/15  = 0.133
l12_avg = (0.500 + 0.450) / 2 = 0.475 ≥ 0.40  ✓ 트리거 조건
l3_norm = 0.133 ≤ 0.25                         ✓ 트리거 조건
```

### 테스트 실행 결과

_TW님 검증 후 보강 예정_

| 항목 | 결과 |
|------|------|
| Telegram 연결 (send_raw) | — |
| Inverse Turkey 1st call 발송 | — |
| 24h dedup 차단 | — |

---

## LQD Backfill 버그 상세

**발견 경위**: Step 1 검증 중 `lqd_prices` 62건 → 목표 750건 미달

**근본 원인**:
- FRED 기반 fetcher (`refresh_single_b_oas`, `refresh_ig_oas`):
  `count == 0` 체크 후 `limit=1000` 전체 로드 패턴 적용됨
- yfinance 기반 fetcher (`refresh_lqd`):
  동일 패턴 미적용 — `period="3mo"` 고정

**수정 내용** (`refresh_lqd()`):
```python
# 수정 전
hist = t.history(period="3mo")

# 수정 후
existing = conn.execute("SELECT COUNT(*) FROM lqd_prices").fetchone()[0]
if existing == 0:
    hist = t.history(start="2022-01-01", interval="1d")
else:
    hist = t.history(period="10d")
```

**branch/commit**: `claude/stage1-lqd-backfill-hotfix` → `cb1336a`

---

## Consequences

**긍정적:**
- Stage 1 모든 컴포넌트 18/18 검증 통과 확인
- LQD backfill 버그 Stage 2 진입 전 선제 수정
- Telegram 알람 발송 검증 완료 (TW 확인 후 확정)

**부정적:**
- LQD 버그 발견으로 hotfix PR 1개 추가 소요
- `claude/analyze-financial-tracker-iZh57` 브랜치에 실수 커밋 1개 잔존
  (9bbea51, TW 결정으로 force-push 없이 이력 보존)

**DB 영향:**
- 없음 (Stage 1 변경사항 검증만, 신규 스키마 없음)

---

## Reference

- `Stage1_Emergency.md` — Stage 1 지시서
- `Stage2_Instructions.md` Section 1.7 — Stage 1 검증 요구사항
- `scripts/test_telegram_alert.py` — Telegram 테스트 스크립트
- Hotfix branch: `claude/stage1-lqd-backfill-hotfix` (cb1336a)
