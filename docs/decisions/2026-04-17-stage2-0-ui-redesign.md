# Stage 2.0: Signal Desk Indicator Status UI 재설계

**Status**: Accepted  
**Date**: 2026-04-17  
**Stage**: 2.0  
**Related PR**: PR #6

---

## Context

기존 Signal Desk의 INDICATOR STATUS 섹션은 17개 지표를 flat dot list로 표시하여:
- 어느 지표가 스트레스 상태인지 즉시 파악 어려움
- cap=0 지표(보류 중)와 활성 지표 구분 없음
- 지표별 임계값·해석·이력 차트 확인 불가
- 우측 2컬럼에 끼어 있어 공간 부족

---

## Decision

### 1. INDICATOR STATUS → 전폭(full-width) 배치

우측 컬럼에서 분리, 2컬럼 그리드 하단에 전폭 섹션으로 이동.  
Inverse Turkey 카드는 우측 컬럼에 단독 유지.

### 2. 3-섹션 구조

```
⚠️ Active Issues (N)          ← cap>0, tier≠normal, Crisis→Stress→Watch 순 정렬
📊 참고 지표 (cap=0)           ← cap==0 지표 (보류/참고용)
✓  Normal (N)                  ← cap>0, tier==normal (Layer별 collapsible)
```

### 3. `<details>` 카드 구조

각 지표는 `<details>` 요소로 구현:

**`<summary>`**: Layer 배지 | 티어 아이콘 | 지표명 | 현재값 | 티어 라벨  
**펼치면**:
- 4-단계 티어 바 (Normal/Watch/Stress/Crisis)
- 현재 / 전일 / 7일전 값 (티어 색상 적용)
- 해석 텍스트 (`INDICATOR_INTERPRETATIONS`)
- 임계값 그리드 (`INDICATOR_THRESHOLDS`, 4열)
- 30일 Plotly 미니 차트

### 4. prev / week 값 출처

`tmrs_scores.snapshot` JSON 이력에서 추출:
- **prev**: 오늘과 다른 날짜의 가장 최신 snapshot
- **week**: 7일 전 날짜에 가장 가까운 snapshot

별도 테이블 조회 없이 단일 source of truth 유지.

### 5. Plotly + `<details>` 충돌 해결

`<details>` 닫힘 상태에서 Plotly 는 0×0 으로 렌더됨.  
→ `toggle` 이벤트에서 `Plotly.relayout(el, {autosize:true})` 호출.

### 6. 성능 전략: Hybrid preload / lazy-load

| 섹션 | 전략 |
|------|------|
| Active Issues | 카드 `open` 상태로 렌더, 즉시 차트 fetch |
| 참고 지표 | 카드 `open` 상태로 렌더, 즉시 차트 fetch |
| Normal by Layer | 기본 닫힘, layer group `toggle` 시 해당 그룹 전체 lazy-load |

개별 카드 `toggle` 시에도 `loadAndRenderChart(key)` 호출 (미로드 시).

### 7. 신규 백엔드

**`GET /indicator/<key>/timeseries?days=30`**  
`tmrs_scores.snapshot` 이력에서 날짜 중복 제거(하루 1건) 후 시계열 반환.

**`INDICATOR_INTERPRETATIONS`** / **`INDICATOR_THRESHOLDS`** 모듈 레벨 상수:  
`/signal-desk` 응답에 포함, JS에서 직접 사용.

---

## Consequences

**긍정적:**
- Active Issues 즉시 가시화 → 스트레스 상황 파악 시간 단축
- cap=0 참고 지표 명시적 구분 → 혼동 방지
- 지표별 맥락(임계값·해석·이력) 온디맨드 제공
- Normal 지표 lazy-load → 초기 로드 성능 유지

**부정적 / 주의:**
- `<details>` 기반 UX는 모바일에서 탭/클릭 경험이 다를 수 있음
- Normal 섹션 lazy-load 시 첫 펼침에 약간의 지연 발생 (API fetch)

---

## Reference

- `Stage2_0_Instructions.md` Section 0.5 / PR #6 결정 사항
- `docs/decisions/2026-04-17-stage2-0-jpy-infrastructure.md` (동일 Stage PR #7)
- `app.py`: `INDICATOR_INTERPRETATIONS`, `INDICATOR_THRESHOLDS`, `/signal-desk`, `/indicator/<key>/timeseries`
- `templates/index.html`: `renderIndicatorStatus()`, `buildIndicatorCard()`, `loadAndRenderChart()`
