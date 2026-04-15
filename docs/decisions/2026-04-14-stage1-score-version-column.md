# tmrs_scores score_version 컬럼 추가

**Status**: Accepted  
**Date**: 2026-04-14  
**Stage**: 1  
**Related Commit**: 2cc47f4

---

## Context

Stage 1에서 Layer 2 지표 추가 및 HY OAS 가중치 변경(7→5pt)으로 인해
기존 tmrs_scores 이력과 신규 레코드의 채점 기준이 달라졌다.
버전 구분 없이 단일 테이블에 저장되면 이력 차트 해석 시 혼선이 발생한다.

---

## Decision

- **컬럼 추가**: `tmrs_scores.score_version TEXT DEFAULT 'v1.0'`
- **기존 레코드**: 모두 `'v1.0'` 태깅 (원본 보존)
- **신규 레코드**: `SCORE_VERSION = 'v1.0.1'` 상수로 자동 태깅
- **마이그레이션**: `init_db()` 내 `ALTER TABLE` + `UPDATE` (앱 재시작 시 자동 적용)
- **독립 스크립트**: `scripts/migrations/0001_add_score_version.py` (Replit에서 수동 실행 가능)
- **Threshold Table 버전 bump**: `v1.2026-04` → `v1.2026-04-01`

---

## Consequences

**긍정적:**
- 이력 데이터 연속성 유지 (삭제 없음)
- UI 차트에서 버전 전환 시점 표시 가능 (향후 구현)
- Stage 2 완료 후 선택적 재계산 시 `v1.0.1_retroactive` 테이블과 비교 가능

**부정적:**
- `v1.0` 레코드와 `v1.0.1` 레코드의 점수 직접 비교는 부정확
  (가중치 변경으로 동일 시장 조건에서 다른 점수 산출)

**DB 영향:**
- `tmrs_scores` 테이블에 `score_version` 컬럼 추가
- 기존 22개 레코드는 `'v1.0'` 태깅 유지

---

## Alternatives Considered

- **옵션 B (재계산)**: snapshot에 raw value 보존되어 있어 기술적으로 가능하나
  Stage 2 완료 후 최종 가중치 확정 시 수행하는 것이 더 의미 있음 → 보류
- **옵션 C (삭제)**: 레코드 22개로 적지만 이력 손실은 최후 수단 → 기각

---

## Reference

- `Stage1_Emergency.md` Section 2.2, 3.5
- `Financial_Tracker_v1.0.1_Instructions.md` Section 질문 4
