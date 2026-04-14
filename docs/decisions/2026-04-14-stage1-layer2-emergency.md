# Stage 1 긴급 재조정 — Layer 2 응급 충실화 배경

**Status**: Accepted  
**Date**: 2026-04-14  
**Stage**: 1 (Emergency)  
**Related Commits**: 9626101, 812a215, b23a645

---

## Context

v1.0.1 Instructions Section 6 답변 검토 중, 2026-04-14 13:37 KST 기준 TMRS 실제 상태가
v1.0 문서가 정의한 "Inverse Turkey" 패턴에 도달했음에도 시스템이 이를 감지하지 못하는
구조적 결함이 발견되었다.

**현재 시장 snapshot (2026-04-14):**
- Layer 1: 15.55 / 45 (34%) — RRP Crisis, Discount Window Stress, TGA Stress
- Layer 2: 2.00 / 30 (7%) — 구조적 저커버리지
- Layer 3: 3.00 / 15 (20%) — VIX 19, MOVE 74 (정상)

**Inverse Turkey 미발화 원인:**
- v1.0 트리거 조건: `l12_avg = (l1_norm + l2_norm) / 2 >= 0.40`
- 현재 `l2_norm = 2/30 = 0.067` → `l12_avg = (0.346 + 0.067) / 2 = 0.206`
- Layer 2 max 활성 가능 점수가 7점 내외여서 l2_norm이 구조적으로 0.23을 초과 불가
- 결과: Inverse Turkey 감지 기능이 **원천 차단**된 상태

---

## Decision

기존 Stage 1 (명칭/임계 정리) → Stage 3으로 연기.  
Layer 2 응급 충실화를 Stage 1 최우선으로 재조정.

단계별 목표:
- Stage 1: Single-B OAS(7pt) + IG OAS(3pt) + LQD(2pt) 추가 → Layer 2 max 17pt
- Stage 2: HYG daily(4pt) + HYG 5day(3pt) 추가 → Layer 2 max 24pt
- Stage 2 완료 후 Inverse Turkey 감지 가능 조건 충족 목표

---

## Consequences

**긍정적:**
- Credit stress 발생 시 즉각 감지 가능한 구조로 복원
- Inverse Turkey 트리거 수학적 가능 조건 회복 (l2_norm 상승)
- Layer 2 데이터 소스 다변화 (FRED 2종 + yfinance 1종)

**부정적:**
- 명칭/임계 정리(기존 Stage 1)가 Stage 3으로 밀려남
- Stage 1 완료 후에도 현재 시장 조건(모든 신규 지표 Normal)에서는 즉시 발화 불가
  → Stage 2(HYG) 완료 후 실질 감지력 회복

**DB 영향:**
- single_b_oas, ig_oas, lqd_prices 테이블 신규 추가
- 기존 데이터 손실 없음

---

## Alternatives Considered

- **단순 Layer 2 max 변경 없이 Divergence 공식 조정**: v1.0 사상 훼손 → 기각
- **Korea CDS 임시 수동 입력으로 Layer 2 충전**: 신뢰성 낮은 데이터 사용 → 기각

---

## Reference

- `Financial_Tracker_Scoring_Logic_in Total.md` 카테고리 1, 4.11.1
- `Stage1_Emergency.md` Section 0, 1
