# Stage 2.1: Coverage Ratio + Normalized Score

**Status**: Accepted  
**Date**: 2026-04-17  
**Stage**: 2.1  
**Related PR**: PR #8

---

## Context

현재 TMRS는 v1.0 목표 지표(32개) 중 일부만 구현된 상태에서 원점수(raw score)를 100점 만점으로 표시한다. 이는 두 가지 왜곡을 일으킨다:

1. **과소 평가**: 미구현 지표가 많은 레이어의 스트레스가 점수에 충분히 반영되지 않음  
   → 구현된 지표들이 모두 Crisis여도 총점이 낮게 표시될 수 있음
2. **불투명성**: 현재 점수가 몇 % 완성도의 시스템에서 산출된 것인지 알 수 없음

---

## Decision

### 1. `LAYER_SPEC` 상수

v1.0 완성 목표를 코드로 명문화:

```python
LAYER_SPEC = {
    1:           {"spec_indicators": 12, "spec_max_score": 45},
    2:           {"spec_indicators":  8, "spec_max_score": 30},
    3:           {"spec_indicators":  7, "spec_max_score": 15},
    "divergence":{"spec_indicators":  5, "spec_max_score": 10},
}
```

### 2. `_coverage_from_snapshot(snapshot)` — Coverage 계산

`snapshot`의 `cap`/`layer` 필드를 기반으로 자동 계산. **비침투적**: `calculate_tmrs()` 변경 없음.

| Layer | Active (cap>0) | Inactive (cap=0) | Spec | Coverage |
|-------|---------------|-----------------|------|----------|
| L1 | 6 | 0 | 12 | 50% |
| L2 | 6 | 1 (CP-EFFR) | 8 | 75% |
| L3 | 4 | 0 | 7 | 57% |
| Divergence | 1* | 0 | 5 | 20% |
| **Overall** | — | — | — | **≈ 48%** |

*Divergence: `move_vix_ratio`가 Inverse Turkey 로직을 구동 (Layer 3으로 태깅). 전용 Divergence 지표 추가 시 자동 갱신.

**가중 평균**: `Σ(active/spec × spec_max) / Σ(spec_max)`  
→ 만점이 큰 레이어(L1=45)가 더 많이 반영됨.

### 3. `_normalized_score(snapshot, raw_total)` — 정규화 점수

```
max_achievable = Σ cap (active 지표만)
normalized     = (raw_total / max_achievable) × 100
```

현재 max_achievable ≈ 73pt (L1=31, L2=24, L3=15, div=3).

**정규화 티어 임계값**: raw score 티어와 동일한 20/40/65 기준 적용.  
근거: "구현된 지표 중 몇 %가 스트레스 상태인가"를 측정하므로, 동일 임계가 의미를 유지함.

### 4. Signal Desk UI 변경

- **메인 점수**: normalized score 표시 (raw 기준 → 실제 위험도 기반)
- **원점수 부표시**: `원점수 X.X / Ypt`
- **티어 배지**: normalized_tier 기준 적용
- **Coverage 배지**: `Coverage N%` (< 50%: 빨강, 50–80%: 노랑, ≥ 80%: 없음)
- **Layer 바 옆**: `active(+inactive)/spec` 표시 (색상 동일 기준)

### 5. 비침투적 설계

- `calculate_tmrs()`, `tmrs_scores` 테이블: **변경 없음**
- Coverage + normalized는 `/signal-desk` 응답에서 on-the-fly 계산
- 기존 `total_score` (raw) DB 저장 유지 → 이력 차트 등 기존 기능 영향 없음

---

## Layer 2 Coverage 주석

v1.0 Layer 2 spec 8개:

| 지표 | 구현 | cap | 비고 |
|------|------|-----|------|
| HY OAS | ✓ | 5pt | |
| CP-EFFR | ✓ | 0pt | cap=0, 비활성 (Stage 2.2 검토) |
| Single-B OAS | ✓ | 7pt | PR #5에서 series ID 수정 완료 |
| IG OAS | ✓ | 3pt | |
| LQD daily | ✓ | 2pt | |
| HYG daily | ✓ | 4pt | |
| HYG 5day | ✓ | 3pt | |
| **Korea CDS** | ✗ | — | 미구현 (데이터 소스 미확정) |

구현 7/8 (87.5%), active 6/8 (75%).

---

## Consequences

**긍정적:**
- 현재 Coverage 수준에서의 실제 스트레스 강도를 정규화하여 표시
- v1.0 목표 대비 진척도를 코드로 명문화 → 새 지표 추가 시 자동 반영
- 기존 저장 데이터(raw score) 변경 없음 — 완전 하위 호환

**부정적 / 주의:**
- normalized_score가 raw_score보다 높게 표시될 수 있음 (특히 Coverage 낮을 때)  
  → 사용자가 "더 위험해 보인다"고 오해할 수 있으나, 이는 정확한 해석
- Divergence Coverage 근사값(1/5) — 전용 지표 추가 전까지 고정

---

## Reference

- `Stage2_Instructions.md` Section 1.4
- `Financial_Tracker_Scoring_Logic_in Total.md` v1.0 지표 목록
- `app.py`: `LAYER_SPEC`, `_coverage_from_snapshot()`, `_normalized_score()`
- `templates/index.html`: `renderSignalDesk()` — normalized + coverage UI
