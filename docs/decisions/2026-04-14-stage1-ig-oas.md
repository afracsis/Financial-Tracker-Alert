# IG OAS Layer 2 통합

**Status**: Accepted  
**Date**: 2026-04-14  
**Stage**: 1  
**Related Commit**: 9626101 (코드), 812a215 (논리 기록)

---

## Context

v1.0 문서 카테고리 4.6의 Layer 2 지표 중 IG OAS(3pt)가 미구현 상태.
FRED에서 무료로 제공되며 기존 HY OAS와 동일한 패턴으로 즉시 구현 가능.

---

## Decision

- **데이터 소스**: FRED `BAMLC0A0CM` (BofA ICE US Corporate Master OAS)
- **DB 테이블**: `ig_oas (date, oas_bp, fetched_at)`
- **단위 변환**: FRED 제공값(%) × 100 = bp
- **Layer / 가중치**: Layer 2, cap = 3pt
- **임계값** (v1.0 카테고리 3.5.1):
  - Normal: < 100 bp
  - Watch: 100–130 bp
  - Stress: 130–180 bp
  - Crisis: > 180 bp
- **스케줄**: 매일 07:15 / 22:15 KST (Single-B OAS와 동일 시각)

---

## Consequences

**긍정적:**
- IG 등급 Credit 전반의 스트레스 수준 측정 가능
- HY OAS와 함께 사용 시 Credit 시장 전체 구조 파악 (IG/HY 동반 확대 = 시스템 리스크)
- Layer 2 max +3pt 기여

**부정적:**
- 현재 IG OAS 수준이 Normal 구간 → 즉각 점수 기여 없음

**DB 영향:**
- `ig_oas` 테이블 신규 생성

---

## Reference

- `Financial_Tracker_Scoring_Logic_in Total.md` 카테고리 3.5.1, 4.6
- `Stage1_Emergency.md` Section 3.2
