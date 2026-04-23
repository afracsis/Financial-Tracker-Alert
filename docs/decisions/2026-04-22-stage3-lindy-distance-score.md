# Stage 3 — Lindy Distance Score (LDS) 구현

**Status**: Accepted  
**Date**: 2026-04-22  
**Stage**: 3 — PR #12  
**Related PR**: PR #12

---

## Context

Stage 3 Signal Desk는 Taleb (2026) "Fragility, Lindy, and Ruin" 논문의 핵심 명제를 금융 지표 모니터링에 적용한다.  
기존 Inverse Turkey Score가 "과거 분포 대비 꼬리 리스크"를 측정한다면,  
LDS는 "Crisis 흡수 장벽까지의 현재 거리"를 실시간으로 정규화하여 제공한다.

---

## 탈렙 논문 핵심 명제 (Remark 2)

> *"A system approaching an absorbing barrier is fragile — the distance to the barrier, not the current level, determines systemic risk."*

흡수 장벽(absorbing barrier)이란 되돌아올 수 없는 임계점을 의미한다.  
금융 시스템에서는 신용 스프레드가 특정 수준을 돌파하면 피드백 루프가 시작되어 자기 강화적 붕괴가 발생한다.  
LDS는 이 장벽까지의 거리를 0~1로 정규화하여, 1=장벽으로부터 멀리 있음(안전), 0=장벽 도달(위기)로 표현한다.

---

## LDS 개념

### Crisis 임계 = 흡수 장벽

각 Credit 지표에 대해 역사적 위기 선례(GFC, COVID, 2022 LDI)를 기반으로 흡수 장벽을 설정한다.  
장벽은 고정값이며, 단기 시장 변동으로 변경하지 않는다.

### 거리 정규화

```
direction = "above" (스프레드 확대가 위험):
    LDS = (barrier - current) / barrier  ← 0이면 장벽 도달

direction = "below" (가격/수익 하락이 위험):
    LDS = (current - barrier) / |barrier|
```

결과는 `max(0.0, min(1.0, value))`로 클리핑하여 0~1 범위를 보장한다.

---

## 4개 대상 지표 및 가중치 결정 근거

| 지표 | 키 | 흡수 장벽 | 방향 | 가중치 | 근거 |
|------|-----|-----------|------|--------|------|
| Single-B OAS | `single_b_oas` | 600 bp | above | 7 | GFC 피크 ≈ 1800 bp; 600 bp는 HY stress 분기점 |
| CP Spread (A2/P2-AA) | `cp_aa_spread` | 50 bp | above | 6 | 2008년 CP 시장 붕괴 직전 50+ bp |
| HY OAS | `hy_oas` | 7.0% | above | 5 | 700 bp = 광범위한 high-yield 경색 임계 |
| HYG 일간 변화 | `hyg_daily` | -1.5% | below | 4 | 단일일 -1.5% = 패닉 청산 신호 |

가중치는 시스템적 전염 가능성 순서로 부여.  
Single-B OAS(7)가 최고: 레버리지 차입이 직접 영향을 받으면 피드백 루프 속도가 가장 빠름.  
HYG 일간 변화(4)가 최저: 단기 노이즈 가능성 내포.

---

## Composite 가중 평균 방식

```python
composite = Σ(lds_i × weight_i) / Σ(weight_i)
```

데이터가 없는 지표는 계산에서 제외 (분모에서도 제거).  
Tier 분류:

| Composite | Tier |
|-----------|------|
| > 0.50 | `lindy` — 정상 안전 구간 |
| 0.25 ~ 0.50 | `pre_lindy` — 주의 모니터링 |
| 0.10 ~ 0.25 | `hazard_rising` — 위험 상승 |
| < 0.10 | `absorption_imminent` — 장벽 임박 |

---

## UI 레이아웃 — 카드 분할

기존 Signal Desk 우측 카드 (Inverse Turkey 전용) → 상하 분할:

- **상단 60%**: LDS 패널
  - Composite 수치 + Tier 배지 (색상 코딩)
  - 4개 지표별 거리 바 (LDS 오름차순 정렬 → 가장 위험한 지표가 상단)
- **하단 40%**: Inverse Turkey 패널 (기존 유지)

Indicator 카드에도 해당 4개 지표에 한해 LDS 거리 바를 추가 (8번째 파라미터로 전달).

---

## Lindy Collapse Alert 조건

```
composite < 0.15 → alert = True → Telegram 전송
```

24h 중복 방지 (Inverse Turkey 패턴과 동일):
- 첫 발생 시: 즉시 전송 + cooldown 시작
- Cooldown 내 재발생: 전송 생략
- Cooldown 만료 후 재발생: 다시 전송
- alert 해제 시: cooldown 리셋 (다음 이벤트 즉시 포착)

---

## Inverse Turkey와의 관계

| | Inverse Turkey Score | LDS |
|--|----------------------|-----|
| 측정 대상 | 현재 값이 과거 분포의 꼬리에 위치하는 정도 | 위기 흡수 장벽까지의 절대 거리 |
| 기준 | 자기 분포 (rolling) | 외부 고정 장벽 |
| 시계 | 과거 → 현재 | 현재 → 미래 |
| 역할 | 이상값 감지 | 위기 근접도 경보 |

두 지표는 보완적이며 중복이 아니다.  
IT가 "분포 이탈"을 탐지하는 반면, LDS는 "장벽 근접"을 탐지한다.  
IT Score 상승 없이도 LDS가 낮아질 수 있고 (구조적 크리프), 반대 경우도 가능하다.

---

## Consequences

**긍정적:**
- 탈렙 논문의 흡수 장벽 개념이 실시간 대시보드에 직접 구현됨
- Composite LDS 단일 수치로 Credit 시스템 안전성 한눈에 파악 가능
- Telegram 알림이 threshold 기반 (< 0.15) + 24h 중복 방지로 노이즈 최소화
- Indicator 카드 LDS 바로 개별 지표의 위기 근접도 시각화

**부정적 / 주의:**
- 흡수 장벽 값은 역사적 선례 기반으로 설정되었으나 고정값이므로, 시장 구조 변화 시 재검토 필요
- `hyg_daily` 는 당일 데이터에 의존하므로 마감 후 정확한 값이 나오기 전까지 intraday noise 가능
- 4개 지표 중 하나라도 DB에 없으면 해당 지표 제외 처리 → Composite 편향 가능성 (현재는 데이터 존재 확인됨)
