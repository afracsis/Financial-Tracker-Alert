# Single-B OAS Layer 2 통합

**Status**: Accepted  
**Date**: 2026-04-14  
**Stage**: 1  
**Related Commit**: 9626101

---

## Context

v1.0 문서 카테고리 4.6의 Layer 2 지표 중 최대 가중치(7pt)를 가진 Single-B OAS가
미구현 상태였다. Layer 2의 실질 max 점수 부족의 핵심 원인.

---

## Decision

- **데이터 소스**: FRED `BAMLH0A2HYBEY` (BofA ICE Single-B US HY OAS)
- **DB 테이블**: `single_b_oas (date, oas_bp, fetched_at)`
- **단위 변환**: FRED 제공값(%) × 100 = bp
- **Layer / 가중치**: Layer 2, cap = 7pt (Solo Cap 동일)
- **임계값** (v1.0 카테고리 3.5.1 원문):
  - Normal: < 350 bp
  - Watch: 350–450 bp
  - Stress: 450–600 bp
  - Crisis: > 600 bp
- **스케줄**: 매일 07:15 / 22:15 KST
- **초기 로드**: DB 비어있을 시 전체 이력 자동 백필 (limit=1000)

---

## Consequences

**긍정적:**
- Layer 2 max 점수 +7pt (2pt → 9pt → 이후 추가와 합산)
- 가장 중요한 Credit 스트레스 선행 지표 확보
- l2_norm 상승으로 Inverse Turkey 트리거 가능성 증가

**부정적:**
- 현재 Single-B OAS 수준이 Normal 구간이면 점수 기여 없음

**DB 영향:**
- `single_b_oas` 테이블 신규 생성
- 초기 실행 시 수년치 이력 자동 로드

---

## Alternatives Considered

- **HYG ETF proxy 사용**: 유동성 기반 지표라 OAS와 다른 정보 → 별도 지표로 Stage 2에서 추가
- **수동 입력**: 데이터 연속성 불안정 → 기각

---

## Reference

- `Financial_Tracker_Scoring_Logic_in Total.md` 카테고리 3.5.1, 4.6
- `Stage1_Emergency.md` Section 3.1
