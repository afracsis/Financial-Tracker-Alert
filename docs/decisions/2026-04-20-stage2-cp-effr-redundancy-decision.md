# Stage 2.2: CP-EFFR Redundancy Decision — cap=0 유지 (재평가 보류)

**Status**: Accepted (조건부 — 3개월 운영 후 재평가)
**Date**: 2026-04-20
**Stage**: 2.2
**Related PR**: PR #9

---

## Context

Stage 1에서 CP-EFFR 지표를 `cap=0` (점수 기여 없음)으로 보류했다.  
사유: v1.0 Layer 2 가중치 표에 없는 독자 구현 지표이며, Layer 1의 `cp_aa_spread`와 redundancy 가능성.

Stage 2.2에서 두 지표의 historical 상관관계를 분석해 cap 수준을 확정하는 것이 목표였다.

---

## 분석 결과

**분석 도구**: `scripts/analyze_cp_effr.py`  
**데이터 소스**: `tmrs_scores.snapshot` (Primary) → raw tables (Fallback)  
**분석 기간**: 6 거래일 (데이터 수집 초기 단계)

| 지표 | 결과 | 기준 |
|------|------|------|
| Level Pearson r | **+0.8382** | HIGH (> 0.80) |
| Daily Δ Pearson r | **+0.7495** | MEDIUM (0.50–0.80) |

### 지표 구조

| | cp_effr | cp_aa_spread |
|---|---|---|
| 공통 구성요소 | **A2/P2 CP** − EFFR | **A2/P2 CP** − AA CP |
| 차이 | 절대 자금조달 비용 (vs 무위험률) | CP 시장 내 신용등급 프리미엄 |

두 지표는 A2/P2 CP rate를 공통 구성요소로 공유한다. Level 상관이 HIGH인 것은 이 구조적 요인에 기인한다. Daily Δ 상관(0.75)은 완전 redundancy 기준(>0.80) 미만이나, n=6으로 통계적 신뢰도가 매우 낮다.

---

## Decision

### cap=0 유지 (코드 변경 없음)

**근거:**
1. **데이터 부족**: n=6 (6 거래일)은 상관계수의 통계적 유의성을 담보하기 어렵다. 통상적으로 Pearson 상관의 신뢰 가능한 추정에는 n≥30이 필요하다.
2. **Level HIGH + Daily Δ MEDIUM**: Level 상관은 완전 redundancy 기준을 충족하나, Daily Δ는 부분 독립 구간(MEDIUM)에 위치한다. Mixed 신호에 해당하며, 소량 데이터에서는 보수적 판단이 타당하다.
3. **점수 왜곡 방지**: 데이터 불충분 상태에서 cap 상향 시 TMRS 점수 기여가 과대 또는 과소 반영될 위험.

코드 변경 없음 — `_compute_tmrs()`의 `cp_effr cap=0` 유지.

---

## 재평가 조건

| 조건 | 기준 |
|------|------|
| 재평가 시점 | 운영 3개월 후 (n≥60 거래일 확보 시) |
| 재평가 방법 | `python scripts/analyze_cp_effr.py` 재실행 |
| cap=0 유지 조건 | 둘 다 > 0.80 확인 시 |
| cap=2 부여 조건 | 둘 다 0.50–0.80 확인 시 |
| cap=3 부여 조건 | 둘 다 < 0.50 확인 시 |
| Mixed 시 | TW와 협의 후 결정 |

---

## Consequences

**긍정적:**
- 데이터 부족 상황에서 보수적 결정 → TMRS 점수 안정성 유지
- 분석 인프라(`scripts/analyze_cp_effr.py`) 완비 → 재평가 즉시 실행 가능
- 기존 코드(`cp_effr cap=0`) 변경 없음 — 완전 하위 호환

**부정적 / 주의:**
- n=6 기준의 r=+0.8382 (Level)는 과대추정 가능성 있음
- Daily Δ r=+0.7495는 부분 독립 구간 — 3개월 후 cap=2 가능성 열려 있음
- `cp_aa_spread`와 중복 캡처 위험은 운영 데이터 축적 전까지 잠정 수용

---

## Reference

- `Stage2_Instructions.md` Section 1.5
- `scripts/analyze_cp_effr.py` — 재평가 시 동일 스크립트 사용
- `app.py`: `_compute_tmrs()` L830–840 (`cp_effr cap=0`)
- 선행 ADR: `docs/decisions/2026-04-14-stage1-cp-effr-weight-zero.md`
