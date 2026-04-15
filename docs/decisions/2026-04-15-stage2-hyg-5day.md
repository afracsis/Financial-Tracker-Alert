# Stage 2: HYG ETF 5일 변화율 지표 추가

**Status**: Accepted  
**Date**: 2026-04-15  
**Stage**: 2  
**Related PR**: PR #4

---

## Context

HYG 일간 변화율(2-f)이 단기 노이즈에 취약한 반면, 5거래일 누적 변화율은 추세성 있는 신용 압박을 포착.  
v1.0 카테고리 3.5.3에 5day 변화율이 별도 지표로 명시됨.

---

## Decision

HYG 5일 변화율을 Layer 2에 추가 (cap 3pt):

```python
# 2-g. HYG 5일 변화율 (%) — cap 3pt  [Stage 2 신규]
hyg_5d_rows = conn.execute(
    "SELECT close_price FROM hyg_prices ORDER BY date DESC LIMIT 6"
).fetchall()
if len(hyg_5d_rows) >= 6:
    latest_close = hyg_5d_rows[0]["close_price"]
    close_5ago   = hyg_5d_rows[5]["close_price"]
    if close_5ago and close_5ago > 0:
        chg_5d = round((latest_close / close_5ago - 1) * 100, 4)
        inds["hyg_5day"] = dict(
            name="HYG 5일 변화율", layer=2, cap=3, value=chg_5d, unit="%",
            tier=_tier(-chg_5d, [(1.0,"normal"), (2.5,"watch"), (5.0,"stress"), (None,"crisis")]),
        )
```

| 티어 | 5일 변화율 (절댓값) |
|------|-------------------|
| Normal  | < 1.0% |
| Watch   | 1.0% ~ 2.5% |
| Stress  | 2.5% ~ 5.0% |
| Crisis  | > 5.0% |

- **계산식**: `(latest / close_5ago - 1) * 100` — 최근 6개 레코드(5거래일 전 대비)
- **방향**: inverse (낙폭이 클수록 stress)
- **데이터 소스**: `hyg_prices` 테이블 공유 (별도 수집 없음)
- **최소 데이터**: 6개 레코드 미만 시 지표 생략 (초기 수집 직후 안전)

---

## Implementation Notes

- `hyg_prices` 테이블은 `refresh_hyg()`가 관리하며 `hyg_daily`와 공유
- `LIMIT 6`으로 최신 6개 종가를 조회 → `rows[0]`(오늘) / `rows[5]`(5거래일 전)
- `_credit_latest_hyg()` 헬퍼에서 `change_5day` 필드로 함께 반환

---

## Consequences

**긍정적:**
- 단기 노이즈를 줄인 추세 확인 지표로 `hyg_daily`와 상호 보완
- 추가 API 호출 없이 기존 `hyg_prices` 테이블 재사용

**부정적:**
- 없음

---

## Reference

- `Financial_Tracker_Scoring_Logic_in Total.md` 카테고리 3.5.3
- `Stage2_Instructions.md`
- ADR: `2026-04-15-stage2-hyg-daily.md`
