# Stage 3.5 — Fragility Regime Map 위젯

**Status**: Accepted  
**Date**: 2026-04-28  
**Stage**: 3.5 — PR #16  
**Related PR**: PR #16

---

## Context

PR #14 (ERP/Buffett/CAPE)로 Valuation 지표가 확보됨. 이제 두 차원을 결합한 시각적 위치 판단 도구가 필요하다.

> "고평가 자체보다 *고평가 + 유동성 경색의 동시 발생*이 Crash의 전제조건이다." — v1.0 핵심 통찰

---

## 4사분면 설계 근거

```
         │
 High    │  Bubble        │  CRASH RISK ★
Valuation│  Expansion     │  ZONE
         │                │
─────────┼────────────────┼─────────────
         │                │
  Low    │  Strong        │  Value
Valuation│  Long Entry    │  Trap
         │                │
         └────────────────┴─────────────
          Easy Liquidity    Tight Liquidity
```

| 사분면 | 색상 | 의미 |
|--------|------|------|
| 좌상: Bubble Expansion | 🟡 노랑 | 고평가 + 유동성 풍부. 버블 확장기. 추세 지속 가능하나 취약성 누적 |
| **우상: Crash Risk Zone** | 🔴 빨강 | 고평가 + 유동성 경색. **역사적으로 가장 위험한 조합** |
| 좌하: Strong Long Entry | 🟢 녹색 | 저평가 + 유동성 풍부. 장기 매수 최적 조건 |
| 우하: Value Trap | 🟠 주황 | 저평가처럼 보이나 유동성 경색으로 가격 추가 하락 가능 |

---

## 축 선택 근거

**X축 — Liquidity Tightness (Layer 1 Normalized)**  
- `l1_score / 45` (0=Easy, 1=Tight)
- Layer 1은 SOFR/EFFR, 국채 Basis, SOFR Term Premium, IORB 등 순수 자금시장 지표
- 실시간 반응성이 가장 빠름 — 경색 초기 신호를 가장 먼저 포착

**Y축 — Valuation Level (Valuation Composite)**  
- `calculate_valuation_composite(snapshot)` (0=Low, 1=High)
- ERP(weight=3) + Buffett(weight=2) + CAPE(weight=2) 가중 평균 normalized score
- 각 지표 정규화: normal→0, crisis→1 (ERP는 inverse 방향)

---

## 역사적 검증

| 시기 | X (l1_norm) | Y (val_comp) | 사분면 |
|------|-------------|--------------|--------|
| 2000 닷컴 피크 | ~0.3 (Easy) | ~0.95 (CAPE 44) | Bubble Expansion → Crash Risk |
| 2007 GFC 직전 | ~0.7 (Tight) | ~0.75 | **Crash Risk Zone** ✓ |
| 2021 코로나 버블 | ~0.1 (QE) | ~0.80 (CAPE 38) | Bubble Expansion |
| 2026-04 현재 | ~0.46 (중간) | ~0.85 (CAPE 40.7) | Bubble Expansion (Crash 경계) |

---

## UI 레이아웃

Signal Desk 우측 카드 하단을 좌우 분할:
- 좌 50%: Inverse Turkey (기존, 위치만 이동)
- 우 50%: Fragility Regime Map (신규)

LDS 패널(상단 55%)은 변경 없음.

---

## Inverse Turkey 와의 관계

| | Inverse Turkey | Regime Map |
|--|----------------|------------|
| 측정 대상 | 자금/신용 스트레스 vs 주식시장 괴리 | 밸류에이션 취약성 위치 |
| 시간 지평 | 단기 (현재 스프레드/OAS 기반) | 중장기 (CAPE 10년 평균 포함) |
| 신호 성격 | 이진 (감지/미감지) | 연속 (★ 위치) |
| 보완 관계 | Crash Risk Zone + IT 동시 감지 = 최고 경보 | — |

---

## Consequences

**긍정적:**
- Valuation 데이터 시각화 완성 (PR #14 전제조건 활용)
- 4사분면 직관적 — "현재 어디 있나"를 한눈에 파악
- 순수 CSS + 단일 JS 함수 — 외부 라이브러리 불필요

**부정적 / 주의:**
- Regime Map은 월별 CAPE 기반으로 반응이 느림 (월 1회 갱신)
- l1_norm 중간선 0.5는 임의 — 정확한 "경색" 기준은 v1.0 미정의
- 현재 위치(Bubble Expansion ↔ Crash Risk 경계)는 CAPE 수준이 유지되는 한 우상방 압력 지속
