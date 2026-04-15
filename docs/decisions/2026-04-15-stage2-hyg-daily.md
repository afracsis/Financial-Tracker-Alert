# Stage 2: HYG ETF 일간 변화율 지표 추가

**Status**: Accepted  
**Date**: 2026-04-15  
**Stage**: 2  
**Related PR**: PR #4

---

## Context

Stage 1 완료 기준 Layer 2 활성 상한 = 17pt (HY OAS 5 + Single-B OAS 7 + IG OAS 3 + LQD 2).  
v1.0 카테고리 3.5.3에 HYG ETF 지표가 명시되어 있으나 Stage 1에서는 범위 외로 이월됨.

HYG (iShares iBoxx HY Corporate Bond ETF)는 고수익채권 시장의 실시간 유동성 압박을 가격 변화율로 포착.  
LQD(투자등급 채권 ETF)와 상호 보완: LQD는 투자등급, HYG는 하이일드 — 신용 스펙트럼 전체 커버.

---

## Decision

v1.0 카테고리 3.5.3 기준으로 HYG 일간 변화율을 Layer 2에 추가:

```python
# 2-f. HYG 일간 변화율 (%) — cap 4pt  [Stage 2 신규]
hyg_row = conn.execute(
    "SELECT daily_change_pct FROM hyg_prices WHERE daily_change_pct IS NOT NULL ORDER BY date DESC LIMIT 1"
).fetchone()
if hyg_row and hyg_row["daily_change_pct"] is not None:
    v = hyg_row["daily_change_pct"]
    inds["hyg_daily"] = dict(
        name="HYG 일간 변화율", layer=2, cap=4, value=v, unit="%",
        tier=_tier(-v, [(0.3,"normal"), (0.7,"watch"), (1.5,"stress"), (None,"crisis")]),
    )
```

| 티어 | 일간 변화율 |
|------|------------|
| Normal  | > -0.3% |
| Watch   | -0.3% ~ -0.7% |
| Stress  | -0.7% ~ -1.5% |
| Crisis  | < -1.5% |

- **방향**: inverse (낙폭이 클수록 stress)
- **데이터 소스**: yfinance `HYG` 티커
- **DB**: `hyg_prices` 테이블 (Stage 2 init_db 신규)
- **Backfill**: 빈 DB 시 `start="2022-01-01"` 이력 로드, 이후 `period="10d"` 증분

---

## Layer 2 상한 변화

| 구성 요소 | Stage 1 | Stage 2 |
|-----------|---------|---------|
| HY OAS    | 5pt     | 5pt     |
| Single-B OAS | 7pt | 7pt     |
| IG OAS    | 3pt     | 3pt     |
| LQD daily | 2pt     | 2pt     |
| **HYG daily** | —   | **4pt** |
| **HYG 5day**  | —   | **3pt** |
| **활성 합계** | 17pt | **24pt** |
| v1.0 상한 | 30pt    | 30pt    |

---

## Consequences

**긍정적:**
- Layer 2 활성 상한 17pt → 24pt 향상 (v1.0 30pt 대비 80% 달성)
- HY 신용 스트레스 실시간 감지 강화 (LQD는 투자등급만 포착)
- Inverse Turkey l2_sev = l2/30 범위 확대 → 패턴 감지 민감도 향상

**부정적:**
- HYG와 HY OAS 간 상관관계 높음 → 과잉 가중 가능성 존재
- Stage 3에서 중복성 평가 예정

---

## Reference

- `Financial_Tracker_Scoring_Logic_in Total.md` 카테고리 3.5.3
- `Stage2_Instructions.md`
