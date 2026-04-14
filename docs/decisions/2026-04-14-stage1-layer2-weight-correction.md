# Layer 2 가중치 정정 — HY OAS 7→5pt, CP-EFFR cap=0 보류

**Status**: Accepted  
**Date**: 2026-04-14  
**Stage**: 1  
**Related Commit**: 6624390

---

## Context

Stage 1 착수 시 v1.0 문서(카테고리 4.6)와 현재 코드의 Layer 2 가중치 간 충돌 발견.

**이슈 1: HY OAS 7pt vs 5pt**

| 출처 | HY OAS 가중치 |
|------|--------------|
| v1.0 카테고리 4.6 원문 | **5pt** |
| 현재 코드 (c11b4ef, 2026-04-09 최초 구현) | **7pt** |

git log 조사 결과:
- 7pt는 최초 TMRS 구현 커밋(c11b4ef)에서 이미 7pt로 시작
- 5pt→7pt로 변경된 커밋 이력 없음
- 변경 사유 담긴 commit message, ADR, 코드 주석 전무
- **판정: 근거 없는 임시 수치**

**이슈 2: CP-EFFR 5pt**

| 출처 | CP-EFFR |
|------|---------|
| v1.0 Layer 2 가중치 표 | **존재하지 않음** |
| v1.0 카테고리 3.4.5 | A2/P2-AA Spread가 **Layer 1**, 가중 6pt로 존재 |
| 현재 코드 | Layer 2, cap=5pt (독자 구현) |

CP-EFFR은 v1.0에 없는 지표이며, v1.0의 A2/P2-AA Spread와 유사 정보를 측정할 가능성이
높아 redundancy 검증 없이 임의 가중치를 부여하는 것은 사상 훼손.

---

## Decision (C안)

**HY OAS**: 7pt → **5pt 복원** (v1.0 카테고리 4.6 원본 준수)

**CP-EFFR**: cap **0pt** (점수 기여 보류)
- 지표값/tier는 snapshot 및 Credit 탭 UI에 계속 표시
- Layer 2 점수 기여만 0으로 설정
- Stage 2에서 A2/P2-AA Spread(Layer 1, 6pt)와 상관관계 분석 후 정식 처리

**Stage 1 종료 시점 Layer 2 구성:**
| 지표 | cap | 상태 |
|------|-----|------|
| Single-B OAS | 7pt | Stage 1 신규 |
| HY OAS | 5pt | 복원 |
| IG OAS | 3pt | Stage 1 신규 |
| LQD daily | 2pt | Stage 1 신규 |
| CP-EFFR | 0pt | 보류 |
| **합계** | **17pt** | |

---

## Consequences

**긍정적:**
- v1.0 원본 사상 복원
- CP-EFFR 데이터는 보존되어 Stage 2 분석에 활용 가능
- Layer 2 max 명확화 (17pt)

**부정적:**
- HY OAS 5pt 복원으로 기존 점수 이력 대비 최대 2pt 하락 가능
  (score_version 컬럼으로 구분 관리)
- CP-EFFR이 실제로 독립적 정보를 담고 있을 경우 일시적 신호 손실

**DB 영향:**
- 없음 (가중치는 코드 로직, DB 스키마 변경 없음)

---

## Alternatives Considered

- **A안 (문서 기준 20pt 맞추기)**: HY OAS 5pt + CP-EFFR 3pt → 합계 20pt.
  CP-EFFR에 임의 가중치 부여는 사상 훼손 → 기각
- **B안 (코드 유지)**: 이력 연속성 유지. 그러나 근거 없는 수치 유지는 향후 혼선 → 기각

---

## Reference

- `Financial_Tracker_Scoring_Logic_in Total.md` 카테고리 3.4.5, 4.6
- `Stage1_Emergency.md` Section 3.4
- git commit c11b4ef (2026-04-09): 최초 TMRS 구현 — HY OAS 7pt 최초 등장
