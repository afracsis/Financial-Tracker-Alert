# Stage 3 — 명칭/임계 정리

**Status**: Accepted  
**Date**: 2026-04-22  
**Stage**: 3 — PR #13  
**Related PR**: PR #13

---

## Context

Stage 3의 마지막 PR. 코드 기능 변경 없이 표시명 정확성, 임계 원문 정합성, v1.0 정오표를 정리한다.

---

## 1. FRA-OIS → SOFR Term Premium 명칭 변경

### 배경

"FRA-OIS Spread"는 LIBOR 시대 용어.  
현재 시스템은 SOFR 90일 평균 − SOFR 익일물을 측정하므로 "SOFR Term Premium"이 정확한 명칭.

### 변경 범위

| 위치 | 변경 전 | 변경 후 |
|------|---------|---------|
| `app.py` L2816 (주석) | `# SOFR 90일 평균 — FRA-OIS 프록시` | `# SOFR 90일 평균 — SOFR Term Premium 계산용` |
| `templates/index.html` HTML 주석 | `<!-- SOFR 텀 프리미엄 (FRA-OIS 프록시) -->` | `<!-- SOFR Term Premium -->` |
| `templates/index.html` 라벨 텍스트 | `SOFR 텀 프리미엄 · FRA-OIS 프록시 (90일 평균 − 익일물)` | `SOFR Term Premium · 90일 평균 − 익일물 (bp)` |
| `templates/index.html` JS 주석 | `// SOFR 텀 프리미엄 (FRA-OIS 프록시)` | `// SOFR Term Premium (90일 평균 − 익일물)` |

**중요**: snapshot 키 `sofr_term`, DB 컬럼, API 응답 필드명은 변경하지 않음 (DB 이력 호환성).

---

## 2. HY OAS 임계 v1.0 원문 정합성 확인

### 현황

| | Normal 이하 | Watch | Stress | Crisis |
|--|-------------|-------|--------|--------|
| **현재 코드** | < 3.5% | 3.5~5.0% | 5.0~7.0% | > 7.0% |
| **v1.0 원문** | < 3.0% | 3.0~4.0% | 4.0~5.5% | > 5.5% |

현재 코드(3.5/5.0/7.0%)는 v1.0 원문(3.0/4.0/5.5% = 300/400/550bp)보다 완화된 기준을 사용.

### 비교 분석

- v1.0 원문이 **더 보수적**: 현재 시장(HY OAS 약 2.85%)에서는 모두 Normal이나, 위기 신호를 더 일찍 포착
- 현재 코드가 **더 완화**: Watch 트리거가 v1.0보다 0.5%p 높음 → 신호 포착 지연 가능
- LDS 흡수 장벽 7.0%는 현재 코드 Crisis 임계와 일치 (별도 독립 계산이므로 임계 변경 시 LDS 영향 없음)

### 결정 (TW 확정: 선택지 A)

v1.0 원문(3.0/4.0/5.5%)으로 복원. LDS 흡수 장벽도 7.0% → 5.5%로 함께 정합.

변경 내용:
- `THRESHOLD_TABLE["hy_oas"]`: `["< 3.5%","3.5~5.0%","5.0~7.0%","> 7.0%"]` → `["< 3.0%","3.0~4.0%","4.0~5.5%","> 5.5%"]`
- `_compute_tmrs()` `_tier()` 기준: `(3.5, 5.0, 7.0)` → `(3.0, 4.0, 5.5)`
- `LDS_INDICATORS["hy_oas"]["barrier"]`: `7.0` → `5.5`

---

## 3. v1.0 카테고리 3.4.4 정정 문서

**파일**: `docs/corrections/v1.0-jpy-basis-direction-correction.md`

**요약**:
- v1.0 원문은 "음수값이 클수록 위험" 방향으로 기술
- GPT 프레임워크 통찰: "음수값이 0에 가까워질수록 위험" (캐리 청산 관점)
- 역사적 선례 (2024년 8월 Yen Carry 급발진)와 일치하는 재해석
- Stage 2.4 구현 시 percentile 기반 역방향 임계 적용 예정
- 코드 변경 없음 (Stage 2.4 대기 중)

---

## Consequences

**긍정적:**
- UI 표시명이 SOFR 시대 표준 용어와 일치
- v1.0 문서의 JPY Basis 방향성 오류가 공식 정오표로 기록
- HY OAS 임계 불일치가 투명하게 문서화됨

**부정적 / 주의:**
- HY OAS 임계 낮아짐(3.5→3.0%) → 현재 시장(2.85%)이 Watch 경계에 근접. 소폭 상승 시 Watch 진입
- LDS 흡수 장벽 5.5%는 7.0%보다 보수적이므로 LDS Composite가 소폭 하락 예상 (더 민감한 경보)
- snapshot 키 변경 없음 → 내부 코드의 `sofr_term` 키는 여전히 LIBOR 시대 표현 잔존 (기능 문제 없음)
