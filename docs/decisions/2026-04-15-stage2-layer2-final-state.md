# Stage 2 완료: Layer 2 최종 구성 상태

**Status**: Accepted  
**Date**: 2026-04-15  
**Stage**: 2  
**Related PR**: PR #4

---

## Context

Stage 2 (PR #4) 완료 이후 Layer 2 구성 및 TMRS 전체 구조를 문서화.

---

## Layer 2 지표 구성 (Stage 2 완료 기준)

| ID | 지표명 | 소스 | Cap | 티어 임계값 | ADR |
|----|--------|------|-----|-------------|-----|
| `hy_oas` | HY OAS | FRED BAMLH0A0HYM2 | 5pt | 3.5 / 5.0 / 7.0 % | stage1-layer2-weight-correction |
| `cp_effr` | A2/P2 CP−EFFR | FRED + NY Fed | 0pt* | 0.30 / 0.60 / 1.00 pp | stage1-cp-effr-weight-zero |
| `single_b_oas` | Single-B OAS | FRED BAMLH0A3HYC | 7pt | 350 / 450 / 600 bp | stage1-single-b-oas |
| `ig_oas` | IG OAS | FRED BAMLC0A0CM | 3pt | 100 / 130 / 180 bp | stage1-ig-oas |
| `lqd_daily` | LQD 일간 변화율 | yfinance LQD | 2pt | -0.5 / -1.0 / -2.0 % (inverse) | stage1-lqd |
| `hyg_daily` | HYG 일간 변화율 | yfinance HYG | 4pt | -0.3 / -0.7 / -1.5 % (inverse) | stage2-hyg-daily |
| `hyg_5day` | HYG 5일 변화율 | yfinance HYG (공유) | 3pt | ±1.0 / ±2.5 / ±5.0 % (inverse) | stage2-hyg-5day |

*`cp_effr`: cap=0, 점수 기여 없음. UI/snapshot 표시만.

---

## Layer 2 점수 상한 현황

| 단계 | 활성 합계 | v1.0 상한 | 달성률 |
|------|-----------|-----------|--------|
| v1.0 원본 | — | 30pt | — |
| Stage 1 완료 | 17pt | 30pt | 56.7% |
| **Stage 2 완료** | **24pt** | 30pt | **80.0%** |

---

## TMRS 전체 구조 (Stage 2 완료)

| Layer | 상한 | 활성 | 주요 지표 |
|-------|------|------|-----------|
| Layer 1 (Funding) | 45pt | ~45pt | EFFR, SOFR, RRP, TGA, Discount Window, CP, SOFR90d, JPY |
| Layer 2 (Credit)  | 30pt | 24pt | HY OAS, S-B OAS, IG OAS, LQD, HYG daily, HYG 5day |
| Layer 3 (Surface) | 15pt | 15pt | VIX, MOVE, SKEW, MOVE/VIX |
| Divergence        | 10pt | 10pt | l12_avg − l3_sev |
| **Total**         | **100pt** | ~94pt | |

---

## 미해소 항목 (Stage 3+)

1. **l2_sev 분모**: 현재 `/30` (v1.0 spec max). Stage 2 활성 max = 24pt → l2_sev 최대 0.80.  
   분모 변경은 별도 ADR 및 TW 승인 필요.
2. **A2/P2 CP−EFFR (cap=0)**: Stage 3에서 A2/P2-AA Spread(Layer 1)와 중복성 평가 후 정식 처리.
3. **남은 Layer 2 항목 6pt**: v1.0 명시 항목 중 미구현 — Stage 3 착수 전 식별 필요.

---

## Reference

- `Financial_Tracker_Scoring_Logic_in Total.md` 카테고리 3.5
- `Stage2_Instructions.md`
- PR #1 (Stage 1), PR #4 (Stage 2 HYG)
