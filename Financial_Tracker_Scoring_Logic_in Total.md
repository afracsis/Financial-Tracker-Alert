# Financial Tracker — Scoring Logic

> **Reference Document for Scoring Book Dashboard**  
> 본 문서는 Financial Tracker 앱 내 Scoring Book 대시보드의 logic backbone 입니다. 시장 시그널 탐지를 1차 목적으로 하며, 자산 배분과 포지션 관리는 의도적으로 본 시스템 범위 밖입니다.

| 항목 | 내용 |
|---|---|
| **Document Title** | Financial Tracker — Scoring Logic |
| **Version** | v1.0 (2026-04-08) |
| **Author** | TW × Claude (Opus 4.6) |
| **Source Documents** | (1) Claude Reference v1, (2) GPT PDF, (3) Gemini DOCX |
| **Purpose** | Scoring Book dashboard logic 정의 |
| **Scope** | Market signal detection (TMRS + ERS) |
| **Out of Scope** | Asset allocation, option position management, account separation philosophy |
| **License** | TW 개인 사용 |

---

## 목차

1. **Core Philosophy & Mental Model** — 3-Layer Market Structure
2. **Data Sources & Monitoring Universe** — 50+ 지표 inventory
3. **Indicator Thresholds & Triggers** — 4-구간 임계값
4. **Risk Scoring Engine — TMRS v2** — 100점 산출 엔진
5. **Event Risk Score — ERS** — 이벤트 기반 점수 시스템
6. **Quantitative Modeling & Verification** — Anti-Hallucination + Bull/Bear
7. **Power Law & Fat-Tail Foundations** — 사상적 근거 + 향후 코드 영역

---

## 본 문서의 구성 원칙

본 문서는 4가지 원칙으로 작성되었습니다.

1. **Decision-grade detail** — 코드 작성 시 의문이 남지 않도록 산식·임계값·코드 예시까지 포함
2. **Korean prose + English technical terms** — TW님 가독성 + 코딩 에이전트 호환성
3. **Self-contained** — 외부 문서 참조 없이 본 문서만으로 시스템 구현 가능
4. **Versioned** — Threshold table, weight, 임계값은 모두 버전 명시. 향후 calibration 가능

본 문서의 모든 결정은 7개 카테고리의 누적 논의를 거친 결과이며, 변경 시 전체 일관성을 검토해야 합니다.

---

## 용어 정리 (Glossary)

본 문서 전체에서 사용되는 핵심 용어입니다.

| 용어 | 정의 |
|---|---|
| **TMRS** | TW Macro Risk Score — 시장 데이터 기반 0–100 점수 |
| **ERS** | Event Risk Score — 이벤트 데이터 기반 0–100 점수 |
| **Layer** | 3-Layer Market Structure 의 한 단계 (Deep / Middle / Surface) |
| **Inverse Turkey** | 표면 평온 + 진앙 stress 패턴 — 본 시스템의 핵심 알람 |
| **Solo Cap** | 단일 지표가 점수에 기여할 수 있는 최대치 |
| **Divergence** | 레이어 간 또는 시스템 간 비대칭 신호 |
| **Threshold Table** | 카테고리 3에서 정의된 임계값 모음 (버전 관리됨) |
| **Decomposition** | 점수 변화의 출처를 Layer/지표 단위로 분해한 출력 |
| **Conditional α** | 시장 regime에 따라 변하는 tail thickness 파라미터 |
| **Regime** | 시장의 거시 환경 단계 (ZIRP/Hiking/QT/Stagflation 등) |

---

# Category 1. Core Philosophy & Mental Model

## 1.1 카테고리의 역할

본 카테고리는 시스템 전체의 사상적 출발점이며, 이후 모든 카테고리(데이터 수집, 임계값, 스코어링 엔진, 출력)의 설계 결정 근거가 됩니다. 본 카테고리에서 정해진 명제와 멘탈 모델이 흔들리면, 이후 카테고리의 모든 수치와 산식이 의미를 잃습니다.

본 카테고리는 코드로 직접 구현되지 않지만, **시스템 운영 중 의문이 생길 때 돌아와야 할 기준점** 역할을 합니다.

## 1.2 핵심 명제 (Foundational Thesis)

> **"Funding breaks first → Credit confirms → Equities react last"**
>
> 시장 위기는 표면(주가)이 아니라 심층(자금시장)에서 시작된다. 표면 지표는 항상 후행한다.

이 명제는 본 시스템 전체의 설계 원칙이며, 데이터 수집·스코어링·알람 우선순위까지 모두 이 명제의 인과 방향을 따릅니다. 본 명제는 다음 두 가지 관찰에 근거합니다.

**관찰 1**: 역사상 모든 주요 금융 위기(2007 서브프라임, 2008 리먼, 2011 유럽재정위기, 2020 COVID, 2023 SVB)에서 funding stress가 equity drawdown 보다 *최소 수일에서 수개월* 먼저 관찰되었습니다.

**관찰 2**: 일반 시장 참여자와 미디어는 equity price 와 VIX 만 봅니다. Funding 영역(SOFR, FX basis, CP spread)은 전문 트레이더와 정책 당국만 봅니다. 이 *정보 비대칭*이 본 시스템의 존재 이유입니다.

## 1.3 3-Layer Market Structure

위기는 **Deep → Middle → Surface** 순서로 표면화됩니다. 따라서 모니터링과 스코어링도 동일한 깊이 순서로 구성합니다.

```
┌─────────────────────────────────────────────────────────┐
│  SURFACE LAYER  (Layer 3 — Reaction)                     │
│  ──────────────────────────────────                      │
│  • Equities (S&P 500, Nasdaq, KOSPI)                     │
│  • VIX, VVIX, SKEW                                       │
│  • FX (DXY, USD/KRW)                                     │
│  • Commodities (WTI, Gold)                               │
│  • 시장 헤드라인 / 뉴스 sentiment                          │
│                                                          │
│  특징: 가장 늦게 움직임 (lagging)                          │
│       대중이 보는 위기 = 이 레이어                          │
│       의사결정 근거로 쓰면 이미 늦음                        │
│                                                          │
└──────────────────────▲──────────────────────────────────┘
                       │ 
                       │ confirms
                       │
┌──────────────────────┴──────────────────────────────────┐
│  MIDDLE LAYER  (Layer 2 — Confirmation)                  │
│  ──────────────────────────────────                      │
│  • HY OAS (High Yield Credit Spread)                     │
│  • Single-B OAS (가장 위험한 등급)                         │
│  • A2/P2 − AA Commercial Paper Spread                    │
│  • HYG / LQD ETF (intraday proxy)                        │
│  • Korea CDS, GSIB CDS (시스템 리스크)                    │
│                                                          │
│  특징: 중간 속도 (coincident)                              │
│       Funding stress 가 실물 신용으로 전이된 단계           │
│       이 레이어가 움직이면 위기는 confirmed                  │
│                                                          │
└──────────────────────▲──────────────────────────────────┘
                       │
                       │ propagates to
                       │
┌──────────────────────┴──────────────────────────────────┐
│  DEEP LAYER  (Layer 1 — Origin)                          │
│  ──────────────────────────────────                      │
│  • SOFR / EFFR / Repo                                    │
│  • USD/JPY Cross-Currency Basis (1M, 3M)                 │
│  • FRA-OIS Spread                                        │
│  • Reserve Balances / RRP / TGA / SOMA                   │
│  • Fed Discount Window borrowing (Primary Credit)        │
│  • Outright Bill Purchase (Submitted vs Accepted)        │
│                                                          │
│  특징: 가장 먼저 움직임 (leading)                          │
│       위기의 진앙 — 여기서 보이지 않으면 위기가 아님         │
│       전문가 영역, 정보 비대칭의 원천                       │
│                                                          │
└─────────────────────────────────────────────────────────┘

      위기 진행 방향: Deep → Middle → Surface
      모니터링 우선순위: Deep > Middle > Surface
      가중치 순서:      Deep > Middle > Surface (카테고리 4 참조)
```

## 1.4 레이어별 역할 정의

| 레이어 | 명칭 | 시간적 성격 | 역할 | 위기 진행 단계 표현 |
|---|---|---|---|---|
| **Layer 1** | Deep / Funding | Leading (선행) | 진앙 탐지 | "Hidden stress building" |
| **Layer 2** | Middle / Credit | Coincident (동행) | 확증 (confirmation) | "Stress confirmed, spreading" |
| **Layer 3** | Surface / Equities | Lagging (후행) | 현실화 (realization) | "Crisis visible to all" |

각 레이어는 *어떤 종류의 신호*를 제공하는지 명확히 다릅니다. 본 시스템은 세 신호를 모두 받지만, **출력 우선순위와 가중치는 명확히 차등**합니다.

## 1.5 4-Tier Liquidity Framework → 3-Layer 매핑

TW님이 이전에 자체 개발하신 4-Tier Liquidity Framework는 본 3-Layer 구조와 다음과 같이 매핑됩니다.

| 기존 4-Tier | 핵심 지표 | 신규 3-Layer |
|---|---|---|
| Tier 1 (단기 자금) | SOFR, RRP, Repo, EFFR, SOMA | **Layer 1** (Deep) |
| Tier 2 (크레딧) | HYG, Korea CDS, HY OAS | **Layer 2** (Middle) — 일부는 Layer 1 |
| Tier 3 (금리) | UST 2Y/10Y/30Y, 딜러 포지셔닝 | **Cross-Layer** — 카테고리 2에서 분류 |
| Tier 4 (글로벌) | DXY, USD/KRW, USD/JPY, VIX, WTI, Gold | **Layer 3** (Surface) |

본 시스템은 4-Tier를 더 이상 별도 유지하지 않으며, 3-Layer가 표준 분류 체계입니다. 4-Tier는 *역사적 reference* 로만 보존됩니다.

## 1.6 본 시스템에서의 함의

3-Layer 멘탈 모델은 본 시스템의 다음 5가지 설계 결정에 직접 반영됩니다.

### 1.6.1 데이터 수집 우선순위

Deep Layer 데이터는 가능한 자주(intraday), 가능한 정확하게 수집합니다. Surface Layer는 정해진 종가 기준으로 충분합니다.

```
Deep Layer:    intraday (가능한 모든 갱신)
Middle Layer:  일별 종가 + 일중 보조 (HYG ETF 등)
Surface Layer: 일별 종가
```

이 우선순위는 카테고리 2 (Data Sources) 에서 각 지표의 갱신 빈도로 구체화됩니다.

### 1.6.2 스코어링 가중치 방향성

동일한 stress 정도라도 **Deep Layer 에서 발생한 신호에 더 높은 가중**을 부여합니다. 카테고리 4 (TMRS v2) 에서 결정된 가중치는 다음과 같습니다.

```
Layer 1 Deep      45점
Layer 2 Middle    30점
Layer 3 Surface   15점
Cross-Layer       10점
─────────────────
Total            100점
```

Deep 가중치가 Surface 의 3배입니다. 이것이 카테고리 1 사상의 정량화입니다.

### 1.6.3 알람 우선순위

| Layer | 알람 즉각성 | 채널 |
|---|---|---|
| Layer 1 임계 돌파 | 즉시 | 푸시 알림 + 일일 리포트 최상단 |
| Layer 2 임계 돌파 | 일일 | 일일 리포트 강조 |
| Layer 3 임계 돌파 | 일일 | 일일 리포트 본문 |
| Cross-Layer Divergence | 즉시 | 푸시 알림 + 강조 |

### 1.6.4 디버전스 감지의 핵심

Layer 1·2 가 stress 신호를 보내는데 Layer 3 가 평온하다면, **그것이 가장 위험한 상태**입니다. 이 비대칭이 본 시스템의 가장 중요한 출력값입니다.

이 패턴은 카테고리 7 (Power Law) 에서 다루는 *Inverse Turkey 시나리오* 의 직접 신호이며, 카테고리 4 (TMRS v2) 에서 별도 알람으로 구현됩니다.

### 1.6.5 사용자 의사결정 시점

Layer 3 가 움직인 후의 의사결정은 이미 늦습니다. 본 시스템은 사용자가 Layer 1·2 의 신호로 *선제적으로* 행동할 수 있게 돕는 것이 목적입니다.

이 원칙은 본 시스템의 *raison d'être* 이며, 시중 risk dashboard 와의 가장 큰 차이점입니다. 시중 dashboard 는 VIX, S&P drawdown 같은 Surface 지표를 중심으로 설계되어 있어, 사용자가 신호를 보았을 때는 이미 시장이 30% 이상 빠진 후입니다.

## 1.7 Power Law / Fat-tail 사상과의 관계

본 카테고리의 3-Layer 멘탈 모델은 카테고리 7 (Power Law & Fat-Tail Foundations) 의 사상적 토대 위에 서 있습니다. 정확한 관계는 다음과 같습니다.

- **카테고리 1 (3-Layer)**: *어디서 위기가 시작되는가* → 공간적 모델
- **카테고리 7 (Power Law)**: *왜 위기가 그렇게 작동하는가* → 분포적 모델

두 카테고리는 독립적으로 이해 가능하지만, 함께 보면 본 시스템 설계의 모든 결정이 일관된 사상에서 나왔음이 명확해집니다. 본 카테고리가 *what to look at* 을 정의한다면, 카테고리 7 은 *why it matters* 을 정의합니다.

본 카테고리에서는 Power Law 사상을 직접 다루지 않으며, *함의*만 언급합니다. 깊은 논의는 카테고리 7 에서 진행합니다.

## 1.8 카테고리 1에서 의도적으로 제외한 항목

| 항목 | 처리 | 사유 |
|---|---|---|
| **본인/아들 계좌 분리 철학** | **삭제** | 본 시스템 1차 목적은 마켓 시그널 탐지. 자산 연계는 추후 단계 |
| **Power Law / Fat-tail / Taleb 사상** | **카테고리 7 로 분리** | 사상의 깊이를 단독으로 다룰 가치. 카테고리 1 을 가볍게 유지 |
| **Inverse Turkey 알람 로직** | **카테고리 4 로 이동** | 스코어링 엔진의 구체 알람 메커니즘 |
| **4-Tier Liquidity Framework (원본)** | **3-Layer 로 흡수** | 1.5 에서 매핑 표시. 별도 유지 불필요 |
| **객관성 / 1차 소스 원칙** | **카테고리 6 으로 이동** | 데이터 검증 규칙의 일부 |
| **위기 사례 history (2008, 2020 등)** | **본 문서 외부로** | 학술 영역. 향후 별도 reference 가능 |

## 1.9 카테고리 1 마무리

본 카테고리는 짧고 단순해 보이지만, **본 시스템 전체의 골격**입니다. 다음 6개 카테고리에서 결정될 모든 수치, 산식, 알람 로직은 모두 본 카테고리의 3-Layer 사상에서 파생됩니다.

본 카테고리에서 미해결로 남긴 사항은 없습니다. 다음 카테고리(데이터 소스)에서 이 골격에 50개 이상의 지표를 채워넣는 작업을 진행합니다.

---

# Category 2. Data Sources & Monitoring Universe

## 2.1 카테고리의 역할

본 카테고리는 카테고리 1 에서 정한 3-Layer 골격에 **각 레이어가 어떤 데이터로 채워지는가**를 결정합니다. 50+ 지표를 Deep / Middle / Surface / Cross-Layer 로 분류하고, 각 지표의 1차 소스 / API / 갱신 빈도 / 운영 메모를 명시합니다.

## 2.2 설계 원칙

본 카테고리는 다음 4가지 원칙을 따릅니다.

1. **레이어별 데이터 분리** — 모든 지표는 원칙적으로 정확히 하나의 레이어에 속함. 불가피한 경우만 cross-layer 로 별도 표시
2. **소스 우선순위** — 1차 소스(공식 발표) > FRED > 시장 데이터 API (yfinance 등) > 사용자 수동 입력
3. **갱신 빈도와 시스템 부하의 균형** — Deep Layer 는 가능한 자주, Surface Layer 는 일일 종가로 충분
4. **수동 입력 워크플로 보장** — Bloomberg/Refinitiv 부재 데이터(JPY basis, FRA-OIS 등)는 수동 입력 필드를 반드시 보장

## 2.3 데이터 소스 우선순위 표

| 우선순위 | 소스 | 신뢰도 | 자동화 가능 | 비용 | 사용 영역 |
|---|---|---|---|---|---|
| 1 | federalreserve.gov | ★★★★★ | 부분 (정적 페이지) | 무료 | H.4.1, 정책 발표 |
| 2 | NY Fed Operations | ★★★★★ | 부분 | 무료 | Outright Bill, RRP, Repo |
| 3 | FRED API | ★★★★ | 완전 | 무료 | 모든 시계열 |
| 4 | Treasury Direct | ★★★★ | 완전 | 무료 | T-Bill auctions |
| 5 | yfinance | ★★★ | 완전 | 무료 | 주식, ETF, FX, 원자재 |
| 6 | Polygon.io / IEX | ★★★★ | 완전 | 유료 (월 $50–) | 일중 데이터 보강 |
| 7 | Bloomberg / Refinitiv | ★★★★★ | 완전 | 비쌈 ($2k+/월) | (개인 사용자 부재) |
| 8 | 사용자 수동 입력 | ★★★ | 없음 | 무료 (시간 비용) | Bloomberg 부재 데이터 |

본 시스템은 **우선순위 1–5 + 8** 만 사용합니다. 6번(Polygon)은 v2 이후 선택적 도입이 가능하며, 7번(Bloomberg)은 사용 불가능을 전제로 합니다.

---

## 2.4 Layer 1 — Deep Layer (Funding)

위기의 진앙. 가장 먼저 움직이는 데이터들. 이 레이어에서 신호가 잡히지 않으면 위기가 아닙니다. **가장 중요한 레이어이며, 가장 자주, 가장 정확하게 수집**합니다.

### 2.4.1 단기 자금금리 (Short-term Funding Rates)

| 지표 | 소스 | Series ID | 갱신 | 메모 |
|---|---|---|---|---|
| **SOFR** | NY Fed / FRED | `SOFR` | 일별 (16:00 ET) | 담보 조달 금리 베이스 |
| **EFFR** | NY Fed / FRED | `EFFR` | 일별 | 무담보 익일물 |
| **SOFR − EFFR Spread** | 계산 | — | 일별 | 양수 확대 = 담보 부족 신호 |
| **8-week T-Bill yield** | Treasury / FRED | `DGS3MO` 등 | 일별 | 단기 시장 수요 프록시 |
| **8-week T-Bill B/C ratio** | Treasury Direct | — | 주간 (auction 시) | 입찰 수요 leading 지표 |

**운영 메모**: SOFR 는 NY Fed 가 매일 16:00 ET 에 발표합니다. 한국 시각으로 새벽 5–6시. 자동 fetch 시 EST/EDT 변환 필수.

### 2.4.2 Fed 운영 데이터 (Fed Operations)

| 지표 | 소스 | 갱신 | 메모 |
|---|---|---|---|
| **Outright T-Bill Purchase** | NY Fed Operations | 일별 (운영 시) | **Submitted / Accepted 양쪽 추적** |
| **Securities Lending** | NY Fed Operations | 일별 | 담보 부족 신호 |
| **FX Swap Operations** | NY Fed | 일별 (운영 시) | 글로벌 USD shortage — binary |
| **Primary Credit (Discount Window)** | H.4.1 | 주간 | 0 vs >0 (binary 임계) |
| **Reverse Repo (RRP) — 잔액** | NY Fed / FRED | 일별 | 단기 자금 흡수 풀 |
| **Reverse Repo (RRP) — 참가 기관 수** | NY Fed | 일별 | 패닉 조짐 leading 지표 |

> **★ Submitted vs Accepted Pattern (GPT 흡수)**
>
> Outright Bill Purchase 에서 딜러가 *제출한* 양(submitted)과 Fed 가 *받아들인* 양(accepted)의 갭이 leading 신호입니다.
>
> ```
> Early Warning:    Submitted ↑ + Accepted 안정     → "Hidden stress building"
> Crisis Confirmed: Accepted ↑↑ + SOFR ↑ + HY OAS ↑ → "Crisis already started"
> ```
>
> 본 시스템은 두 값과 그 비율(B/C ratio)을 모두 시계열로 저장합니다. **B/C 8x 이상이면 딜러 balance sheet 스트레스 신호**입니다. 이 패턴은 카테고리 4 의 Cross-Layer Divergence 신호 5개 중 하나로 직접 사용됩니다.

### 2.4.3 Fed Balance Sheet (H.4.1 Weekly)

H.4.1 은 주간(목요일 16:30 ET 발표) 공시 문서로, Deep Layer 의 여러 지표를 동시에 제공합니다. 한 번의 fetch 로 7개 항목을 수집할 수 있습니다.

| 항목 | 의미 | FRED Series ID | 해석 규칙 |
|---|---|---|---|
| **Reserve Balances** | 은행 지준금 | `WRESBAL` | 충분해도 SOFR↑이면 분배 불균형 의심 |
| **TGA (Treasury General Account)** | 정부 현금 잔고 | `WTREGEN` | -$30B/주 이상 감소 = 시장 유동성 + |
| **ON RRP** | 단기 자금 흡수 풀 | `RRPONTSYD` | 잔액 감소 + 참가기관 ↑ = 패닉 조짐 |
| **SOMA — T-Bills** | Fed 의 단기국채 보유 | `WSHOTSL` (집계) | 주간 +$10B 이상 = 적극 유동성 공급 |
| **SOMA — Notes & Bonds** | 중장기 보유 | `WSHONBL` | QT 로 자연 감소 |
| **SOMA — MBS** | 모기지 채권 보유 | `WSHOMCB` | 현재 No new operations 기조 |
| **Currency in Circulation** | 추세선 | `WCURCIR` | |

### 2.4.4 글로벌 USD Funding (Cross-Currency)

| 지표 | 소스 | 갱신 | 자동화 | 메모 |
|---|---|---|---|---|
| **USD/JPY 1M Basis Swap** | Bloomberg/Refinitiv | 일별 | ❌ | **수동 입력 필수** |
| **USD/JPY 3M Basis Swap** | 동일 | 일별 | ❌ | 수동 입력 |
| **USD/JPY 7Y / 10Y Forward Basis** | 동일 | 일별 | ❌ | 구조적 USD shortage 추적 |
| **FRA-OIS Spread** | Bloomberg | 일별 | ❌ | 수동 입력 (50bp 임계) |
| **EUR/USD Cross-Currency Basis (참고)** | 동일 | 일별 | ❌ | EM 자금 환경 점검 |

**중요한 개념적 명시**:

> **이론값 (Theoretical Value)** = 금리차 + Cross-Currency Basis
>
> Forward rate 자체는 carry unwind 신호가 아닙니다. 실제 carry unwind 신호는 **이론값 대비 편차**, **1M basis swap 의 절대값**, 그리고 **FRA-OIS spread** 에서 옵니다. 본 시스템은 이론값 대비 편차를 핵심 지표로 사용하며, 절대값은 보조 참고용입니다.
>
> 외부 분석(특히 다른 AI 모델)이 forward rate 자체로 carry trade 를 논하면 의심해야 합니다. 본 원칙은 카테고리 6 (Anti-Hallucination) 의 검증 규칙과 직접 연결됩니다.

### 2.4.5 단기 신용 / Funding 경계 (Commercial Paper)

| 지표 | 소스 | Series ID | 갱신 | 자동화 | 메모 |
|---|---|---|---|---|---|
| **AA Nonfin CP 30D** | Fed CP page | `RIFSPPNAAD30NB` | 일별 | ⚠️ | **수동 캡처 권장** |
| **A2/P2 Nonfin CP 30D** | Fed CP page | `RIFSPPNA2P2D30NB` | 일별 | ⚠️ | 수동 캡처 |
| **A2/P2 − AA 30D Spread** | 계산 | — | 일별 | ⚠️ | **+50bp = stress 임계** |

**운영 메모**: federalreserve.gov/releases/cp/rates.htm 은 동적 렌더링 페이지로 단순 스크래핑이 어렵습니다. TW님이 매일 캡처 → 수기 입력 워크플로로 운영 중. 코드 구현 시 수동 입력 필드를 우선 보장하고, OCR 자동화는 후순위로 배치합니다. FRED API 로도 시도 가능하지만 발표 지연(1–2일)이 있어 일중 신호로는 부적합합니다.

### 2.4.6 Layer 1 요약

```
Layer 1 (Deep / Funding) 총 23 지표
  ├─ 단기금리            (5)
  ├─ Fed 운영            (6) — Submitted/Accepted 포함
  ├─ H.4.1 항목          (7)
  ├─ Cross-currency      (5)
  └─ CP                  (3)
```

이 중 **수동 입력이 필수인 지표는 8개**입니다 (Cross-currency 5 + CP 3). 나머지 15개는 FRED API 또는 NY Fed 페이지에서 자동 fetch 가능합니다.

---

## 2.5 Layer 2 — Middle Layer (Credit)

Funding stress 가 실물 신용시장으로 전이되었음을 **확증**하는 데이터들. 위기의 후행 확정 신호입니다. Layer 1 에 비해 수가 적지만 *결정적*입니다.

### 2.5.1 미국 회사채 스프레드

| 지표 | 소스 | Series ID | 갱신 | 메모 |
|---|---|---|---|---|
| **HY OAS (BofA Aggregate)** | FRED | `BAMLH0A0HYM2` | 일별 (1일 lag) | 350bp = stress 진입 |
| **Single-B OAS** | FRED | `BAMLH0A2HYBEY` | 일별 | TW 6-Indicator 핵심 |
| **BB OAS** | FRED | `BAMLH0A1HYBB` | 일별 | 보조 |
| **CCC OAS** | FRED | `BAMLH0A3HYCEY` | 일별 | 가장 민감한 tail 지표 |
| **IG OAS (Aggregate)** | FRED | `BAMLC0A0CM` | 일별 | 시스템 리스크 점검 |

**중요**: FRED HY OAS 는 *일별 종가*만 제공하며 1영업일 lag 가 있습니다. 일중 신호는 ETF (HYG/JNK) 로 보완합니다.

### 2.5.2 Credit ETF (Intraday Proxy)

FRED 데이터의 lag 를 보완하기 위한 일중 프록시입니다.

| 지표 | 소스 | Ticker | 갱신 | 메모 |
|---|---|---|---|---|
| **HYG** | yfinance | `HYG` | 일중 | HY 일중 프록시 (가장 중요) |
| **LQD** | yfinance | `LQD` | 일중 | IG 일중 프록시 |
| **JNK** | yfinance | `JNK` | 일중 | HY 보조 (HYG 와 divergence 점검) |
| **EMB** | yfinance | `EMB` | 일중 | EM USD 채권 (참고) |

**HYG vs JNK Divergence**: 두 ETF 모두 HY 를 추종하지만 구성 종목이 다릅니다. 두 ETF 의 일간 변화율이 0.5% 이상 갭이 발생하면 *HY 시장 내부 mispricing* 신호로 봅니다. 운영 1년 이상 누적 후 calibration 가능합니다.

### 2.5.3 시스템 / EM Credit

| 지표 | 소스 | 갱신 | 자동화 | 메모 |
|---|---|---|---|---|
| **Korea CDS 5Y** | Bloomberg / 수동 | 일별 | ❌ | EM 리스크 프록시 |
| **GSIB CDS — JPM** | Bloomberg / 수동 | 일별 | ❌ | 시스템 리스크 |
| **GSIB CDS — BAC** | 동일 | 일별 | ❌ | |
| **GSIB CDS — Citi** | 동일 | 일별 | ❌ | |
| **GSIB CDS — GS** | 동일 | 일별 | ❌ | |
| **GSIB CDS — MS** | 동일 | 일별 | ❌ | |
| **GSIB CDS 평균** | 계산 | 일별 | — | 일평균 |

**무료 대체 소스**: 한국 CDS 는 KRX 또는 한국은행 통계에서 부분 fetch 가능. GSIB CDS 는 무료 소스가 거의 없어 사실상 수동 입력 필수.

### 2.5.4 Layer 2 요약

```
Layer 2 (Middle / Credit) 총 15 지표
  ├─ 회사채 스프레드      (5)
  ├─ Credit ETF          (4)
  └─ 시스템 / EM         (6)
```

수동 입력 지표는 6개 (Korea CDS + GSIB CDS 5개). 나머지 9개는 자동 fetch.

---

## 2.6 Layer 3 — Surface Layer (Equities & Vol)

대중이 보는 위기. 가장 늦게 움직입니다. 이 레이어 신호만으로 의사결정하면 *이미 늦은 시점*입니다. 그럼에도 본 시스템에 포함되는 이유는:
- Layer 1·2 와의 디버전스 측정에 필수
- 사용자가 직관적으로 이해 가능한 *맥락 정보* 제공
- 일부 지표(MOVE, SKEW)는 후행이 아닌 leading 성격을 가짐

### 2.6.1 Equity Indices

| 지표 | 소스 | Ticker | 갱신 | 메모 |
|---|---|---|---|---|
| **S&P 500** | yfinance | `^GSPC` | 일중 | 미국 대표 지수 |
| **Nasdaq Composite** | yfinance | `^IXIC` | 일중 | 기술주 중심 |
| **Russell 2000** | yfinance | `^RUT` | 일중 | 소형주 (신용 민감) |
| **KOSPI** | yfinance | `^KS11` | 일중 | 한국 |
| **TQQQ** | yfinance | `TQQQ` | 일중 | 레버리지 ETF (변동성 reference) |

지수 *변화율*은 카테고리 3 에서 임계값을 정의하지만, 카테고리 4 의 점수 산출에는 *직접 포함하지 않습니다*. 후행성이 너무 강해 leading 가치가 없기 때문입니다. *맥락 정보*로만 표시됩니다.

### 2.6.2 Equity Volatility

| 지표 | 소스 | Ticker | 갱신 | 메모 |
|---|---|---|---|---|
| **VIX** | yfinance | `^VIX` | 일중 | 후행 vol — 가장 유명 |
| **VVIX** | yfinance | `^VVIX` | 일중 | vol of vol |
| **CBOE SKEW** | CBOE | `^SKEW` | 일별 | OTM Put 가격 = 테일 리스크 |
| **VIX9D** | yfinance | `^VIX9D` | 일중 | 9일 vol — short-term |
| **VIX 1M Futures** | CBOE | — | 일별 | term structure |

**SKEW 의 leading 성격**: SKEW 는 이름과 달리 후행이 아닌 약한 leading 신호입니다. 펀드매니저가 OTM Put 을 매수하면 SKEW 가 먼저 오릅니다. VIX 보다 며칠 앞서 움직이는 경우가 많습니다.

### 2.6.3 Bond Volatility

| 지표 | 소스 | Ticker | 갱신 | 메모 |
|---|---|---|---|---|
| **MOVE Index** | yfinance / TVC | `^MOVE` | 일별 | 채권 변동성 — Leading 성격 |
| **MOVE / VIX 비율** | 계산 | — | 일별 | **>4 = 채권發 위기 가능성** |

> **MOVE 의 레이어 귀속 — 명시적 결정**
>
> MOVE 는 채권 변동성으로 본질적으로 Deep Layer 에 가깝습니다. 그러나 본 시스템에서는 *Surface Layer 에 분류*하되, **MOVE/VIX 비율은 Cross-Layer Divergence 신호로 별도 처리**합니다.
>
> 이 분리의 이유: MOVE 자체는 *vol 지표*로서 VIX 와 함께 그룹핑하는 것이 코드 구조상 깔끔하고, 진짜 leading 가치는 *MOVE 단독*이 아니라 *MOVE/VIX 갭*에서 나오기 때문입니다. 카테고리 3 의 임계값과 카테고리 4 의 가중치 모두 이 결정을 따릅니다.

### 2.6.4 FX & Commodities

| 지표 | 소스 | Ticker | 갱신 | 메모 |
|---|---|---|---|---|
| **DXY** | yfinance | `DX-Y.NYB` | 일중 | **100 임계 — cross-layer 신호** |
| **USD/KRW** | yfinance | `KRW=X` | 일중 | EM 자금 흐름 |
| **USD/JPY Spot** | yfinance | `JPY=X` | 일중 | 캐리 청산 보조 |
| **WTI Crude** | yfinance | `CL=F` | 일중 | 지정학 시나리오 핵심 |
| **Brent Crude** | yfinance | `BZ=F` | 일중 | 글로벌 유가 |
| **Gold Spot** | yfinance | `GC=F` | 일중 | 인플레/지정학 |
| **Silver Spot** | yfinance | `SI=F` | 일중 | 보조 |

**DXY 의 cross-layer 처리**: DXY 100 돌파는 단순 Surface 신호가 아니라 *글로벌 USD shortage* 의 한 표현입니다. 카테고리 4 의 Cross-Layer Divergence 5개 신호 중 하나로 별도 추적됩니다.

### 2.6.5 Crypto (보조 — "주말 카나리아")

| 지표 | 소스 | Ticker | 갱신 | 메모 |
|---|---|---|---|---|
| **BTC/USD** | yfinance | `BTC-USD` | 24/7 | 주말 유일 유동자산 → 충격 흡수 카나리아 |
| **ETH/USD** | yfinance | `ETH-USD` | 24/7 | BTC 보조 |

**주말 카나리아 개념**: 토/일요일에는 전통 시장이 휴장이지만 BTC 는 24/7 거래됩니다. 따라서 주말에 발생한 거시 충격(지정학, 정책 발표)이 BTC 에 *먼저* 반영됩니다. 월요일 시장 개장 전 미리 위기 신호를 탐지할 수 있습니다.

### 2.6.6 Layer 3 요약

```
Layer 3 (Surface / Equity) 총 19 지표
  ├─ Equity indices       (5)
  ├─ Equity vol           (5)
  ├─ Bond vol             (2) — cross-layer 보조
  ├─ FX / Commodities     (7)
  └─ Crypto               (2)
```

**모두 자동 fetch 가능**합니다. yfinance 가 무료로 거의 모든 데이터를 제공합니다.

---

## 2.7 Cross-Layer / Meta Data

특정 레이어에 속하지 않거나 여러 레이어에 걸친 메타 데이터입니다.

### 2.7.1 Positioning Meta

| 지표 | 성격 | 소스 | 갱신 | 자동화 | 메모 |
|---|---|---|---|---|---|
| **CFTC COT — Leveraged Funds Net E-mini** | 헤지펀드 포지션 | CFTC | 주간 (금) | ✅ | S&P 선물 net long/short |
| **CFTC COT — Asset Manager Net** | 기관 포지션 | CFTC | 주간 (금) | ✅ | |
| **AAII Sentiment Survey** | 개인 sentiment | AAII | 주간 (목) | ✅ | Bull/Bear/Neutral |
| **NAAIM Exposure Index** | 운용사 노출 | NAAIM | 주간 | ✅ | 0–200 스케일 |

### 2.7.2 Event Meta (카테고리 5 ERS 와 연계)

| 지표 | 성격 | 소스 | 갱신 |
|---|---|---|---|
| **경제지표 발표 캘린더** | 캘린더 | TradingEconomics / FRED | 일별 |
| **Fed 인사 발언 스케줄** | 캘린더 | Fed Calendar | 비정기 |
| **Treasury Auction 일정** | 캘린더 | Treasury Direct | 사전 공시 |
| **지정학 데드라인 캘린더** | 수동 | 사용자 입력 | 비정기 |

이벤트 캘린더 데이터는 카테고리 5 (Event Risk Score) 에서 자세히 다루며, 본 카테고리에서는 *데이터 소스가 존재한다*는 점만 명시합니다.

---

## 2.8 데이터 품질 / 운영 메모

본 시스템 구현 시 주의해야 할 운영적 사항들입니다.

| 이슈 | 영향 지표 | 대응 |
|---|---|---|
| federalreserve.gov CP page 는 동적 렌더링 | AA / A2/P2 CP | 수동 입력 우선, OCR 후순위 |
| FRED HY OAS 는 1일 lag | HY OAS, Single-B OAS | HYG ETF 로 일중 보완 |
| Bloomberg 데이터 부재 (개인 사용자) | JPY basis, FRA-OIS, GSIB CDS | 수동 입력 워크플로 필수 |
| H.4.1 은 주 1회 발표 (목 16:30 ET) | Reserve Balances, TGA, SOMA | 한국 시각 금요일 새벽 자동 갱신 |
| 일부 데이터는 미국 종가 기준 | HY OAS 등 | 한국 시각 다음 날 갱신 (lag 1 영업일) |
| yfinance API rate limit | 모든 시장 데이터 | 캐싱 필수 (일별 데이터는 1일 캐싱) |
| FRED API 일일 호출 제한 | FRED 시리즈 | API key 필요, 무료 한도 충분 |
| 데이터 시간대 혼선 (KST/EST/UTC) | 모든 데이터 | timestamp 를 UTC 로 통일하고 표시만 KST |

## 2.9 데이터 캐싱 권장 사항

본 시스템의 데이터 부하를 줄이기 위한 캐싱 전략입니다.

| 데이터 | TTL | 저장소 |
|---|---|---|
| 일별 종가 (FRED, yfinance) | 24h | SQLite |
| H.4.1 (주간) | 7일 | SQLite |
| 일중 가격 (HYG, VIX 등) | 5분 | Memory |
| 수동 입력 데이터 | 영구 | SQLite |
| 계산된 점수 (TMRS, ERS) | 영구 | SQLite (시계열) |

캐싱 layer 는 Python 의 경우 `requests-cache` 또는 자체 SQLite wrapper 가 권장됩니다. **시계열 데이터는 절대 삭제하지 않습니다** — 향후 carbon backtest 와 calibration 에 필수입니다.

## 2.10 카테고리 2 요약 — 한눈에 보기

```
Layer 1 (Deep / Funding)        23 지표
  ├─ 단기금리            (5)
  ├─ Fed 운영            (6) — Submitted/Accepted 포함
  ├─ H.4.1 항목          (7)
  ├─ Cross-currency      (5)
  └─ CP                  (3)

Layer 2 (Middle / Credit)       15 지표
  ├─ 회사채 스프레드      (5)
  ├─ Credit ETF          (4)
  └─ 시스템 / EM         (6)

Layer 3 (Surface / Equity)      19 지표
  ├─ Equity indices       (5)
  ├─ Equity vol           (5)
  ├─ Bond vol             (2)
  ├─ FX / Commodities     (7)
  └─ Crypto               (2)

Cross-Layer / Meta              8 지표 / 카테고리

총                              65 지표 / 데이터 카테고리
```

이 중 **수동 입력 필수: 14 개**, **자동 fetch 가능: 51 개**.

## 2.11 카테고리 2에서 의도적 추가/배제

| 항목 | 처리 | 사유 |
|---|---|---|
| **Submitted vs Accepted Pattern** | **추가** (Layer 1) | GPT 흡수 — leading 신호로 가치 |
| **MOVE Index** | **잠정 Surface** | 채권 vol 이지만 vol 그룹에 분류, MOVE/VIX 만 cross-layer |
| **DXY** | **잠정 Surface** | FX 는 cross-layer 성격, 임계 알람 별도 |
| **BTC** | **Surface 포함** | "주말 카나리아" 역할로 유지 |
| **4-Tier Liquidity Framework (Claude 원본)** | **3-Layer 로 흡수** | Tier 1·2 → Layer 1, Tier 3 → Layer 2, Tier 4 → Layer 3 |
| **수동 입력 필드 명시** | **추가** | 코드 구현 시 우선 보장해야 할 워크플로 |
| **CFTC COT 데이터** | **Cross-Layer Meta 추가** | 포지셔닝 정보, 주간 갱신 |
| **AAII / NAAIM Sentiment** | **Cross-Layer Meta 추가** | 미시적 위치 점검 |
| **CCC OAS, VIX9D 등 보조 지표** | **추가** | Version Z 디테일 |

## 2.12 카테고리 2에서 미결로 남긴 사항

다음 사항들은 카테고리 2 단독으로는 결정하기 어려우며, 카테고리 3·4 와 연계해 결정합니다.

1. **MOVE 의 최종 레이어 귀속** — 본 카테고리에서는 Surface 에 두고 MOVE/VIX 만 cross-layer 처리. 카테고리 4 에서 가중치 결정 시 다시 검토.
2. **DXY 의 처리** — Surface 로 두되 100 돌파를 cross-layer 알람으로 별도 처리. 카테고리 3·4 에서 구체화.
3. **수동 입력 데이터의 운영 주기** — 매일 입력 vs 주 2–3회 입력. 운영 부담과 정확도의 트레이드오프.
4. **Bloomberg/Refinitiv 부재 데이터의 대체 소스** — 특히 JPY basis swap, FRA-OIS 의 무료/저비용 대안 추가 조사 필요.
5. **CFTC COT 의 활용도** — 본 시스템 가중치에 직접 반영할지, *맥락 정보*로만 표시할지.

---

# Category 3. Indicator Thresholds & Triggers

## 3.1 카테고리의 역할

본 카테고리는 카테고리 2 에서 정리한 65개 지표 각각에 대해 **stress 임계값**을 결정합니다. 이 임계값들은 카테고리 4 (TMRS v2 스코어링 엔진) 의 직접 인풋이 됩니다.

자산 배분/포지션 관련 임계값(TQQQ $43, VIX 청산 트랜치 등)은 시그널 탐지 범위 밖이므로 *제외*합니다.

## 3.2 설계 원칙

임계값 결정에 적용할 5가지 기준입니다.

1. **상대 스프레드 우선** — 가능하면 절대값 대신 상대값 사용. 금리 regime 이 바뀌어도 의미가 일관됨
2. **4-구간 분류** — Normal / Watch / Stress / Crisis. 카테고리 4 스코어링 엔진의 인풋
3. **출처 명시** — 각 임계값의 근거 (TW 누적 분석 / FRED 역사적 분포 / 시중 컨센서스)
4. **이중 표현** — 가능하면 절대값과 percentile rank 를 병기. 절대값은 직관적, percentile 은 regime-robust
5. **버전 관리** — 본 문서의 모든 임계는 *Threshold Table v1 (2026-04)*. 변경 시 changelog 필수

## 3.3 임계값 표현 방식 (4가지 방법론)

본 시스템은 지표 특성에 따라 4가지 표현 방식을 혼용합니다.

| 방식 | 이름 | 적용 대상 | 예시 |
|---|---|---|---|
| **A** | 절대값 임계 | 의미가 금리 regime 과 무관한 지표 | DXY 100, VIX 25 |
| **B** | 스프레드 임계 | 두 지표의 차이가 본질인 경우 | A2/P2 − AA +50bp |
| **C** | 변화율 임계 | 절대값보다 변화의 속도가 중요한 경우 | HYG 일간 -1% |
| **D** | Percentile Rank | 1년/3년 분포에서의 상대 위치 | HY OAS 90th percentile |

같은 지표에 여러 방식을 동시에 적용하는 경우도 있습니다 (예: VIX 는 절대값 + 1년 percentile 병기).

### 3.3.1 4-구간 의미 통일

본 카테고리의 모든 임계값은 다음 4-구간으로 분류됩니다.

| 구간 | 의미 | 카테고리 4 정규화 점수 |
|---|---|---|
| **Normal** | 평상 운용 가능, 신호 없음 | 0.00 |
| **Watch** | 약한 신호, 모니터링 강화 | 0.40 |
| **Stress** | 명확한 신호, 일중 점검 | 0.75 |
| **Crisis** | 강한 신호, 즉시 알람 | 1.00 |

이 4-구간은 **모든 지표에 일관되게 적용**됩니다. Layer 4 의 점수 변환 산식(카테고리 4.3) 도 이 구간 정의를 직접 사용합니다.

### 3.3.2 Percentile 의 lookback 기간

Percentile 임계는 다음과 같이 lookback 기간을 정합니다.

| 지표 성격 | Lookback | 사유 |
|---|---|---|
| 일별 가격/변동성 (HYG, VIX, DXY 등) | 1년 (252 거래일) | 노이즈 제거 + 최근 regime 반영 |
| 주간 데이터 (H.4.1) | 2년 (104 주) | 데이터 부족 보완 |
| Credit spread (HY OAS, IG OAS) | 3년 (756 거래일) | 사이클 1회 포함 |
| Cross-currency basis | 1년 | 정책 변화 민감 |
| 단기 funding rate | 6개월 | 가장 빠른 regime 변화 |

운영 1년 후 데이터로 lookback 기간 적정성을 재검증합니다.

---

## 3.4 Layer 1 — Deep Layer 임계값 (Funding)

### 3.4.1 단기 자금금리

| 지표 | 방식 | Normal | Watch | Stress | Crisis | 출처 신뢰도 |
|---|---|---|---|---|---|---|
| **SOFR − EFFR Spread** | B | < 0bp | 0–3bp | 3–8bp | > 8bp | ★★★ |
| **SOFR vs Fed Funds 상단** | B | < -2bp | -2 ~ +2bp | +2 ~ +5bp | > +5bp | ★★★★ |
| **8-week T-Bill B/C ratio** | A | > 3.0x | 2.5–3.0x | 2.0–2.5x | < 2.0x | ★★★ |
| **8-week T-Bill yield 변화율** | C | ±5bp/일 | 5–10bp/일 | 10–20bp/일 | > 20bp/일 | ★★ |

> **핵심 운영 규칙**: SOFR 가 Fed Funds 상단을 지속적으로 넘으면 Fed 의 Rate Corridor 가 깨졌다는 신호. 즉시 Crisis 등급이며, 점수와 무관하게 별도 알람을 발생시킵니다 (카테고리 4.10.4 참조).

### 3.4.2 Fed 운영 데이터

| 지표 | 방식 | Normal | Watch | Stress | Crisis | 출처 신뢰도 |
|---|---|---|---|---|---|---|
| **Outright Bill Purchase B/C** | A | < 5x | 5–7x | 7–9x | > 9x | ★★★ |
| **Submitted 주간 변화율** | C | ±10% | +10~+25% | +25~+50% | > +50% | ★★★ |
| **RRP 참가 기관 수** | A | ≤ 8 | 9–12 | 13–16 | > 16 | ★★★ |
| **Securities Lending 일별 변화** | C | ±5% | +5~+15% | +15~+30% | > +30% | ★★★ |
| **Primary Credit (Discount Window)** | A (binary) | 0 | — | — | > 0 | ★★★★★ |
| **FX Swap Operations** | A (binary) | None | — | — | Active | ★★★★★ |

> **Submitted vs Accepted 패턴 의미**:  
> Submitted ↑ + Accepted 안정 = Watch~Stress (hidden building)  
> Submitted ↑↑ + Accepted ↑↑ 동시 = Crisis  
>
> Primary Credit 과 FX Swap 은 binary 임계입니다. 0 에서 양수로 전환되는 *순간* 즉시 Crisis 신호이며 점수와 별개로 푸시 알림 발생.

### 3.4.3 H.4.1 항목 (조건부 + 추세)

H.4.1 항목들은 단일 임계보다 *주간 변화 방향*과 *다른 지표와의 조합*이 중요합니다. 따라서 일부 지표는 *조건부* 임계를 사용합니다.

| 지표 | 방식 | Normal | Watch | Stress | Crisis | 메모 |
|---|---|---|---|---|---|---|
| **Reserve Balances 주간 변화** | C | ±$20B | -$20~-$50B | -$50~-$100B | < -$100B | 감소 = 유동성 흡수 |
| **TGA 주간 변화** | C | ±$20B | -$30B 이하 | — | — | 감소는 시장 +, Stress 별도 정의 어려움 |
| **SOMA T-Bill 주간 변화** | C | ±$5B | +$10~$15B | +$15~$25B | > +$25B | Fed 적극 공급 신호 (역방향) |
| **Reserve Balances + SOFR ↑ 동시** | 조건부 | 미발생 | — | — | 발생 | 분배 불균형 = 즉시 Stress |
| **RRP 주간 평균 잔액 변화율** | C | ±$30B | -$50B 이하 | -$100B 이하 | -$150B 이하 | 단기 자금 흡수 풀 감소 |

**SOMA T-Bill 의 비대칭성**: SOMA T-Bill *증가*는 Fed 의 적극적 유동성 공급 신호로 *시장에 긍정적*입니다. 따라서 Stress/Crisis 임계는 일반적인 stress 방향과 *반대*입니다 (감소가 아닌 *증가*가 stress 신호 — Fed 가 시장을 구제해야 할 정도라는 뜻).

본 시스템은 SOMA T-Bill 의 양의 변화율을 stress 로 *해석*하지만, *행동 권고*는 정반대 방향입니다 (시장 안정화 신호). 카테고리 4 에서 해석 로직 추가.

### 3.4.4 글로벌 USD Funding (Cross-Currency)

GPT 는 절대값(-60 / -100 / -140)을, TW 는 *이론값 대비 편차*를 사용합니다. 본 시스템은 후자를 채택합니다.

| 지표 | 방식 | Normal | Watch | Stress | Crisis | 출처 신뢰도 |
|---|---|---|---|---|---|---|
| **USD/JPY 1M Basis** (이론값 대비 편차) | B | ±5bp | -5~-10bp | -10~-20bp | < -20bp | ★★★ |
| **USD/JPY 3M Basis** (이론값 대비 편차) | B | ±10bp | -10~-20bp | -20~-40bp | < -40bp | ★★★ |
| **USD/JPY 7Y Forward Basis** | C (방향) | 안정 | 악화 | 큰 폭 악화 | 지속 악화 | ★★ |
| **USD/JPY 10Y Forward Basis** | C (방향) | 안정 | 악화 | 큰 폭 악화 | 지속 악화 | ★★ |
| **FRA-OIS Spread** | A | < 25bp | 25–40bp | 40–50bp | > 50bp | ★★★★ (GPT 흡수) |
| **EUR/USD Basis** (참고) | B | ±5bp | -5~-15bp | -15~-30bp | < -30bp | ★★ |

> **이론값 정의**: 이론값 = 금리차 + cross-currency basis swap 수준. 이론값 자체는 carry unwind 신호가 아닙니다. 실제 신호는 이론값 대비 *편차*에서 옵니다.
>
> Long end (7Y, 10Y) 는 단일 시점 임계 부적절. *지속적 악화 추세*만 별도로 추적합니다. 일별 변화의 *3주 이동평균*이 음의 방향으로 유지되면 stress.

### 3.4.5 단기 신용 / Funding 경계 (CP)

| 지표 | 방식 | Normal | Watch | Stress | Crisis | 출처 신뢰도 |
|---|---|---|---|---|---|---|
| **A2/P2 − AA 30D Spread** | B | < +30bp | +30~+45bp | +45~+60bp | > +60bp | ★★★★★ TW 핵심 |
| **AA 30D 절대 수준** | D | < 60p | 60–80p | 80–95p | > 95p | ★★★ (1년 분포) |
| **A2/P2 30D 절대 수준** | D | < 60p | 60–80p | 80–95p | > 95p | ★★★ |

> **A2/P2 − AA 스프레드**는 Layer 1 의 *마지막 임계*입니다. 이것이 +50bp 를 넘으면 자금시장 본격 스트레스 진입. **TW 6-Indicator 프레임의 가장 핵심 지표** 중 하나로, 가중치도 가장 높게 부여됩니다 (카테고리 4.4 참조).
>
> GPT 가 제안한 절대값 임계 (4.00 / 4.20)는 *현재 금리 regime* 에서만 유효합니다. 본 시스템은 절대값 대신 percentile rank 로 보조 추적만 합니다.

---

## 3.5 Layer 2 — Middle Layer 임계값 (Credit)

### 3.5.1 미국 회사채 스프레드

| 지표 | 방식 | Normal | Watch | Stress | Crisis | 출처 신뢰도 |
|---|---|---|---|---|---|---|
| **HY OAS (Aggregate)** | A + D | < 300bp / < 60p | 300–400bp / 60–80p | 400–550bp / 80–95p | > 550bp / > 95p | ★★★★★ |
| **Single-B OAS** | A | < 350bp | 350–450bp | 450–600bp | > 600bp | ★★★★★ TW 핵심 |
| **BB OAS** | A | < 200bp | 200–280bp | 280–400bp | > 400bp | ★★★ |
| **CCC OAS** | A | < 700bp | 700–900bp | 900–1200bp | > 1200bp | ★★★ |
| **IG OAS** | A | < 100bp | 100–130bp | 130–180bp | > 180bp | ★★★★ |
| **HY OAS 주간 변화** | C | ±10bp | +10~+25bp | +25~+50bp | > +50bp | ★★★ |
| **HY − IG Ratio** | A | < 3.5x | 3.5–4.5x | 4.5–6x | > 6x | ★★ |

> 절대값과 percentile 을 병기하는 이유: 현재 (2026년 4월) HY OAS 는 역사적으로 낮은 수준이지만, 그 안에서도 *상대적 변동*이 있습니다. Percentile 은 이를 잡아냅니다.
>
> Single-B 는 HY 내에서도 가장 위험한 등급. TW 6-Indicator 의 핵심 지표이며 본 시스템의 신뢰도 ★★★★★ 등급입니다.

### 3.5.2 Credit ETF (일중 프록시)

| 지표 | 방식 | Normal | Watch | Stress | Crisis | 출처 신뢰도 |
|---|---|---|---|---|---|---|
| **HYG 일간 변화율** | C | > -0.3% | -0.3~-0.7% | -0.7~-1.5% | < -1.5% | ★★★★ |
| **HYG 5일 누적 변화** | C | > -1% | -1~-2.5% | -2.5~-5% | < -5% | ★★★ |
| **LQD 일간 변화율** | C | > -0.5% | -0.5~-1% | -1~-2% | < -2% | ★★★ |
| **JNK 일간 변화율** | C | > -0.3% | -0.3~-0.7% | -0.7~-1.5% | < -1.5% | ★★★ |
| **HYG vs JNK divergence** | 조건부 | < 0.3% 갭 | 0.3–0.5% | 0.5–1.0% | > 1.0% | ★★ (검증 필요) |
| **EMB 일간 변화율** | C | > -0.5% | -0.5~-1% | -1~-2% | < -2% | ★★ |

### 3.5.3 시스템 / EM Credit

| 지표 | 방식 | Normal | Watch | Stress | Crisis | 출처 신뢰도 |
|---|---|---|---|---|---|---|
| **Korea CDS 5Y (절대)** | A | < 35bp | 35–45bp | 45–60bp | > 60bp | ★★★★ |
| **Korea CDS 5Y (일간 변화율)** | C | ±3% | +3~+5% | +5~+10% | > +10% | ★★★ |
| **GSIB CDS 평균 일간 변화율** | C | ±3% | +3~+7% | +7~+15% | > +15% | ★★★★ |
| **GSIB CDS 평균 절대 수준** | D | < 60p | 60–80p | 80–95p | > 95p | ★★★ |

Korea CDS 는 절대값과 일간 변화율을 *동시에* 봅니다. 일간 +5% 이상의 변동은 절대값 수준과 무관하게 EM stress 신호입니다.

---

## 3.6 Layer 3 — Surface Layer 임계값 (Equities & Vol)

### 3.6.1 Equity Volatility

| 지표 | 방식 | Normal | Watch | Stress | Crisis | 출처 신뢰도 |
|---|---|---|---|---|---|---|
| **VIX (절대)** | A | < 18 | 18–25 | 25–35 | > 35 | ★★★ 역사 평균 |
| **VIX (1년 percentile)** | D | < 50p | 50–75p | 75–90p | > 90p | ★★★ regime 보정 |
| **VIX 5일 변화율** | C | ±10% | +10~+25% | +25~+50% | > +50% | ★★★ |
| **VVIX** | A | < 90 | 90–105 | 105–125 | > 125 | ★★ |
| **CBOE SKEW** | A | < 135 | 135–145 | 145–155 | > 155 | ★★★ |
| **VIX9D / VIX 비율** | A | < 1.0 | 1.0–1.1 | 1.1–1.2 | > 1.2 | ★★ (단기 panic) |

> VIX 는 절대값과 percentile 동시 적용. 현재 regime 에서는 VIX 25 가 historical 평균보다 높지만 1년 분포에서는 75p 정도일 수 있습니다. 두 신호가 어긋나면 regime change 가능성을 의심.

### 3.6.2 Bond Volatility (Cross-Layer)

| 지표 | 방식 | Normal | Watch | Stress | Crisis | 출처 신뢰도 |
|---|---|---|---|---|---|---|
| **MOVE Index** | A | < 90 | 90–110 | 110–135 | > 135 | ★★★ |
| **MOVE / VIX 비율** | A | < 3.5 | 3.5–4 | 4–5 | > 5 | ★★ cross-layer 핵심 |

> MOVE/VIX 비율 4 초과는 *Layer 1·2 가 Layer 3 보다 먼저 움직이고 있다*는 정량적 증거입니다. Inverse Turkey 시나리오의 직접 신호이며, 카테고리 4 디버전스 알람의 핵심 인풋입니다.

### 3.6.3 FX & Commodities

| 지표 | 방식 | Normal | Watch | Stress | Crisis | 출처 신뢰도 |
|---|---|---|---|---|---|---|
| **DXY (절대)** | A | < 99 | 99–101 | 101–104 | > 104 | ★★★ TW 100 임계 |
| **DXY 일간 변화율** | C | ±0.3% | +0.3~+0.7% | +0.7~+1.5% | > +1.5% | ★★★ |
| **USD/KRW 일간 변화율** | C | ±0.5% | +0.5~+1% | +1~+2% | > +2% | ★★★ EM 신호 |
| **WTI 일간 변화율** | C | ±2% | ±2~±5% | ±5~±10% | > ±10% | ★★★ 지정학 |
| **WTI 절대 수준** | A | $60–90 | $90–105 | $105–125 | > $125 | ★★ 인플레 |
| **Gold 일간 변화율** | C | ±1% | +1~+3% | +3~+5% | > +5% | ★★★ 안전자산 |
| **Gold 5일 누적 변화** | C | < +3% | +3~+5% | +5~+10% | > +10% | ★★ |

> WTI 는 절대 수준과 변화율을 *동시에* 봅니다. $90 이하 안정 환경에서의 +5% 와 $110 환경에서의 +5% 는 시장 의미가 다릅니다.
>
> DXY 100 돌파는 cross-layer 알람으로 별도 처리됩니다 (카테고리 4).

### 3.6.4 Equity Indices

지수 자체는 절대 임계가 의미 없습니다. 일간/주간 변화율과 vol 환경 결합으로만 평가합니다.

| 지표 | 방식 | Normal | Watch | Stress | Crisis | 메모 |
|---|---|---|---|---|---|---|
| **S&P 500 일간 변화율** | C | ±0.7% | ±0.7~±1.5% | ±1.5~±3% | > ±3% | 점수 제외, 맥락 정보 |
| **Nasdaq 일간 변화율** | C | ±0.9% | ±0.9~±2% | ±2~±4% | > ±4% | 점수 제외, 맥락 정보 |
| **KOSPI 일간 변화율** | C | ±1% | ±1~±2% | ±2~±4% | > ±4% | EM 신호, 맥락 정보 |

이 지표들은 카테고리 4 의 점수 산출에 *직접 포함되지 않으며*, *맥락 정보*로만 출력에 표시됩니다.

### 3.6.5 Crypto

| 지표 | 방식 | Normal | Watch | Stress | Crisis | 메모 |
|---|---|---|---|---|---|---|
| **BTC 24h 변화율** | C | ±3% | ±3~±7% | ±7~±15% | > ±15% | 주말 카나리아 |
| **BTC 주말 갭 (월요일 vs 금요일)** | C | ±5% | ±5~±10% | > ±10% | — | 주말 단독 신호 |
| **ETH 24h 변화율** | C | ±4% | ±4~±9% | ±9~±18% | > ±18% | BTC 보조 |

---

## 3.7 Cross-Layer 임계값 (디버전스 신호)

특정 단일 지표가 아닌 *여러 레이어 간 비대칭*을 감지하는 임계값들입니다. 카테고리 4 스코어링 엔진에서 가장 중요한 인풋이 됩니다.

| 신호 | 정의 | Watch | Stress | Crisis | 의미 |
|---|---|---|---|---|---|
| **MOVE / VIX 비율** | 채권 vol ÷ 주식 vol | > 4 | > 5 | > 6 | 채권發 위기 임박 |
| **L1 Stress + L3 Calm** | L1 정규화 ≥ 0.40 AND L3 정규화 ≤ 0.25 | 1일 발생 | 2일 연속 | 3일 이상 | **Inverse Turkey** |
| **HY OAS 안정 + HYG 일중 -1%** | 종가 vs 일중 divergence | 발생 | — | — | 일중 신호 leading |
| **Submitted ↑ + Accepted 안정** | 갭 확대 (Submitted +25%, Accepted ±10%) | 발생 | 1주 지속 | 2주 이상 | Hidden funding stress |
| **DXY 100 돌파 + WTI ↑ 동시** | 두 조건 동시 충족 | 발생 | — | — | 글로벌 USD shortage 가능 |

> **가장 중요한 신호는 L1 Stress + L3 Calm 패턴**입니다. 이것이 본 시스템 전체의 존재 이유 — 표면이 평온할 때 진앙에서 잡아내는 것. 카테고리 4 의 Inverse Turkey 알람과 직접 연결됩니다.

---

## 3.8 동적 임계값 / Regime Adjustment 가이드

위 임계값들은 *2026년 현재 regime* 을 기준으로 설정되어 있습니다. 시간이 지나면서 다음 두 가지 방법으로 자동 보정되도록 코드를 설계해야 합니다.

### 3.8.1 분기별 Percentile Rebase

분기마다 (또는 상시) 각 지표의 1년/3년 분포를 재계산하여 percentile 기반 임계를 자동 갱신합니다.

```python
def rebase_thresholds(series, lookback_days=252):
    """
    1년 lookback 으로 percentile 임계 재계산
    
    series: pandas.Series with datetime index
    lookback_days: 252 (1Y) or 756 (3Y)
    
    returns: dict with normal/watch/stress/crisis thresholds
    """
    recent = series.iloc[-lookback_days:]
    return {
        'normal': recent.quantile(0.50),
        'watch':  recent.quantile(0.75),
        'stress': recent.quantile(0.90),
        'crisis': recent.quantile(0.95),
    }
```

### 3.8.2 Regime Marker 수동 입력

큰 regime change(예: Fed 정책 전환, 글로벌 충격 후)는 알고리즘이 즉시 반영하기 어렵습니다. 사용자가 *regime marker* 를 수동으로 입력해서 임계 테이블을 reload 하는 기능이 필요합니다.

```python
@dataclass
class Regime:
    name: str           # "ZIRP", "Hiking", "QT", "Stagflation"
    start_date: date
    threshold_set: str  # "v1.2026-04" 등 어느 임계 테이블을 사용할지
    notes: str          # 사용자 메모
```

### 3.8.3 임계 테이블 버전 관리

본 카테고리에서 정의한 임계는 *Threshold Table v1 (2026-04)* 입니다. 코드 구현 시 명시적 버전을 부여하고, 변경 시 changelog 를 남깁니다.

```python
THRESHOLD_TABLE_VERSION = "v1.2026-04"
THRESHOLD_TABLE_LAST_UPDATED = "2026-04-08"
```

본 시스템의 모든 출력에 이 버전이 표시됩니다. 버전이 다른 점수 간 직접 비교는 *오해를 만들 수 있으므로* 시각적으로 구분합니다 (카테고리 6 검증 규칙).

---

## 3.9 출처 및 신뢰도 등급

각 임계값의 출처와 신뢰도를 5단계로 표시합니다.

| 등급 | 의미 | 예시 |
|---|---|---|
| **★★★★★** | TW 누적 분석 + 시중 컨센서스 일치 + binary | A2/P2−AA +50bp, Primary Credit > 0 |
| **★★★★** | TW 누적 분석 단독 + 명확한 임계 | HY OAS 350bp Single-B, FRA-OIS 50bp |
| **★★★** | 시중 자료 / FRED 분포 / 운영 평균 | VIX 25, DXY 100 |
| **★★** | 본 시스템 추정 (검증 필요) | MOVE/VIX 4 cross-layer, HYG vs JNK 0.5% |
| **★** | 대략적 추정 (운영 후 calibration 필수) | Crypto, secondary indicators |

★★ 이하 등급 임계값들은 실제 운영 후 1–3개월 데이터로 재검증해야 합니다. 코드에 *flag* 로 표시해두면 좋습니다.

```python
@dataclass
class Threshold:
    indicator: str
    normal: float
    watch: float
    stress: float
    crisis: float
    confidence: int       # 1-5 stars
    needs_validation: bool  # True if confidence <= 2
```

---

## 3.10 카테고리 3 요약 — 한눈에 보기

```
Layer 1 (Deep / Funding)        총 25 지표 임계
  ├─ 단기금리            (4)
  ├─ Fed 운영            (6)
  ├─ H.4.1 조건부        (5)
  ├─ Cross-currency      (6)
  └─ CP                  (3)  + Aux 1

Layer 2 (Middle / Credit)       총 17 지표 임계
  ├─ 회사채 스프레드      (7)
  ├─ Credit ETF          (6)
  └─ 시스템 / EM         (4)

Layer 3 (Surface / Equity)      총 23 지표 임계
  ├─ Equity vol          (6)
  ├─ Bond vol            (2) — cross-layer
  ├─ FX/Commodities      (7)
  ├─ Equity indices      (3) — 점수 제외
  └─ Crypto              (3)

Cross-Layer Divergence          총 5 신호
```

신뢰도별 분포: ★★★★★ ~ 8개 / ★★★★ ~ 15개 / ★★★ ~ 30개 / ★★ ~ 12개 / ★ ~ 5개

## 3.11 카테고리 3에서 의도적 추가/배제

| 항목 | 처리 | 사유 |
|---|---|---|
| 자산/포지션 임계 (TQQQ $43, VIX 청산 트랜치) | **제외** | 1차 목적은 시그널 탐지 |
| 절대값 + Percentile 병기 | **추가** | regime robustness |
| Cross-Layer Divergence Signals | **신설** | 카테고리 1·2 의 핵심 사상의 정량화 |
| GPT 절대값 임계 (A2/P2 4.00, HY OAS 5%) | **보조 참고** | 본 임계는 TW 상대값 기반, GPT 값은 percentile 로 대체 |
| Regime Adjustment 가이드 | **신설** | 임계 테이블의 시간적 robustness 확보 |
| Submitted 주간 변화율 | **추가** | GPT 흡수 |
| MOVE/VIX 비율 | **Cross-Layer 로 격상** | 디버전스 핵심 지표 |
| 출처/신뢰도 등급 | **신설** | 임계값 검증 우선순위 결정 |
| Threshold Table 버전 관리 | **신설** | 카테고리 6 의 검증 규칙과 연계 |
| HY OAS 주간 변화율 (가속도) | **추가** | Version Z 디테일 |
| HYG vs JNK divergence | **추가 (★★)** | 검증 필요한 보조 신호 |

## 3.12 카테고리 3에서 미결로 남긴 사항

1. **MOVE 의 최종 레이어 귀속** — 본 카테고리에서는 일단 Surface 에 두고 MOVE/VIX 만 cross-layer 처리. 카테고리 4 에서 가중치 결정 시 다시 검토.
2. **★ 등급 임계값들의 실제 검증** — 본 시스템 운영 1–3개월 후 데이터로 재조정 필요.
3. **Percentile lookback 기간의 지표별 차별화** — 1년 vs 3년 vs 5년. 지표마다 최적 lookback 이 다를 수 있음.
4. **임계값의 시간 단위 평활화** — 일별 종가 vs 주간 평균 vs 5일 이동평균. 일부 지표는 노이즈가 커서 평활화 필요할 수 있음.
5. **HYG vs JNK divergence 임계 0.5% 의 calibration** — 운영 데이터 누적 후 재검증.
6. **CCC OAS 의 활용** — 본 카테고리에 추가했으나 카테고리 4 점수에 포함시킬지 미결.

---

# Category 4. Risk Scoring Engine — TMRS v2

## 4.1 카테고리의 역할

본 카테고리는 카테고리 1·2·3 에서 결정된 사항들을 모두 인풋으로 받아 **0–100 스코어를 산출하는 엔진**을 설계합니다. 이 엔진이 본 시스템의 *심장*이며, Scoring Book 대시보드의 메인 출력이 됩니다.

핵심은 카테고리 1 의 사상 *"Funding breaks first → Credit confirms → Equities react last"* 를 정량화하는 것입니다. 단순한 지표 합산이 아니라, **레이어별 가중 + 디버전스 감지 + 독립 알람 시스템**의 결합입니다.

## 4.2 설계 원칙

본 스코어링 엔진은 다음 5가지 원칙을 따릅니다.

1. **Deep > Middle > Surface 가중치 순서** — 카테고리 1 의 인과 사상을 점수에 직접 반영
2. **Cross-Layer Divergence 는 별도 가산 카테고리** — 단일 지표가 아닌 *레이어 간 비대칭*을 정량화
3. **Solo Cap 규칙** — 단일 지표 오류로 전체 점수가 폭주하지 않도록 각 지표의 최대 기여도 제한
4. **점수 + 알람의 이원화** — 절대 점수와 Inverse Turkey 알람은 *독립적*으로 작동. 점수가 낮아도 알람이 켜질 수 있음
5. **Decomposition 필수** — 매일 점수 *변화의 출처*를 분해하여 출력 (어느 Layer / 어느 지표가 움직였는가)

## 4.3 점수 구조 개요

```
┌──────────────────────────────────────────────────────────┐
│  TMRS v2 — Total 100 points                              │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Layer 1 (Deep / Funding)        45 pt                  │
│    └─ Solo Cap per indicator:    max 6 pt               │
│                                                          │
│  Layer 2 (Middle / Credit)       30 pt                  │
│    └─ Solo Cap per indicator:    max 7 pt               │
│                                                          │
│  Layer 3 (Surface / Equity)      15 pt                  │
│    └─ Solo Cap per indicator:    max 4 pt               │
│                                                          │
│  Cross-Layer Divergence          10 pt                  │
│    └─ Solo Cap per signal:       max 4 pt               │
│                                                          │
│  ─────────────────────────────────────                  │
│  Total                          100 pt                  │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### 4.3.1 가중치 결정 근거

| Layer | 가중 | 비율 | 근거 |
|---|---|---|---|
| **Deep** | 45 | 45% | 카테고리 1 사상의 직접 반영. Leading 신호가 가장 가치 있음 |
| **Middle** | 30 | 30% | Confirmation 역할. Deep 에 비해 약간 낮지만 충분한 무게 |
| **Surface** | 15 | 15% | 후행 신호. 점수에 영향은 주지만 결정적 역할은 아님 |
| **Divergence** | 10 | 10% | 별도 카테고리. 디버전스 자체가 위기 신호 |

### 4.3.2 Inverse Turkey 시나리오 점수 시뮬레이션

세 Layer 합 = 90점 (Surface 가 Deep 의 1/3 수준). Inverse Turkey 시나리오에서는 Surface 가 평온하므로 자연스럽게 최대 90점에서 Surface 15점이 빠진 75점이 *Calm 상태에서의 위기 신호 상한* 이 됩니다. 여기에 Divergence 10점이 가산되어 85점까지 도달 가능합니다.

```
Inverse Turkey 가설 시나리오:
  Layer 1 점수 = 35 / 45  (78% — 거의 max)
  Layer 2 점수 = 22 / 30  (73% — 거의 max)
  Layer 3 점수 = 3 / 15   (20% — 거의 calm)
  Divergence  = 10 / 10   (100% — 최대 가산)
  ────────────────────────────────
  TMRS Total  = 70 / 100
```

이 70점은 명목상 Red Alert 등급에 해당하지만, *Layer 분해 출력*을 보면 Surface 가 거의 0인 *비정상 패턴*임이 명확합니다. 본 시스템은 점수와 함께 Layer 분해를 항상 출력함으로써 이런 패턴을 탐지합니다.

## 4.4 4-구간 → 점수 변환 산식

카테고리 3 에서 정의한 Normal / Watch / Stress / Crisis 4구간을 점수로 변환하는 표준 산식입니다.

### 4.4.1 기본 정규화 점수

| 구간 | 정규화 점수 | 산출값 (가중치 W 에 대해) |
|---|---|---|
| Normal | 0.00 | 0 × W |
| Watch | 0.40 | 0.40 × W |
| Stress | 0.75 | 0.75 × W |
| Crisis | 1.00 | 1.00 × W |

### 4.4.2 선형 보간 산식

같은 Watch 구간 내에서도 임계 가까이로 갈수록 점수가 올라가도록 보간합니다.

```python
def indicator_score(value, thresholds, weight, mode='interpolated'):
    """
    지표 값을 점수로 변환
    
    value: 현재 지표 값
    thresholds: dict {'normal', 'watch', 'stress', 'crisis'}
    weight: Layer 4 에서 정의된 가중치
    mode: 'interpolated' (권장) or 'stepwise'
    
    returns: 0 ~ weight 사이의 점수
    """
    if mode == 'stepwise':
        # 단순 4-구간
        if value < thresholds['watch']:
            normalized = 0.00
        elif value < thresholds['stress']:
            normalized = 0.40
        elif value < thresholds['crisis']:
            normalized = 0.75
        else:
            normalized = 1.00
    
    else:  # 'interpolated'
        if value < thresholds['watch']:
            # Normal → Watch 보간
            ratio = (value - thresholds['normal']) / (
                thresholds['watch'] - thresholds['normal']
            )
            normalized = 0.00 + 0.40 * max(0, min(1, ratio))
        elif value < thresholds['stress']:
            # Watch → Stress 보간
            ratio = (value - thresholds['watch']) / (
                thresholds['stress'] - thresholds['watch']
            )
            normalized = 0.40 + 0.35 * ratio
        elif value < thresholds['crisis']:
            # Stress → Crisis 보간
            ratio = (value - thresholds['stress']) / (
                thresholds['crisis'] - thresholds['stress']
            )
            normalized = 0.75 + 0.25 * ratio
        else:
            normalized = 1.00
    
    return normalized * weight
```

> **보간을 쓰는 이유**: 점수가 부드럽게 변화해서 일일 변화 추적이 의미 있어집니다. 단순 4구간만 쓰면 점수가 *계단형*으로 움직여 추세 관찰이 어렵습니다. **본 시스템은 보간(interpolated) 을 권장**합니다.

### 4.4.3 역방향 임계 처리

일부 지표는 *낮을수록 stress* 입니다 (예: 8-week T-Bill B/C ratio). 이 경우 임계 비교 방향을 반전시킵니다.

```python
def indicator_score_inverse(value, thresholds, weight):
    """
    역방향 지표 (낮을수록 stress)
    
    예: B/C ratio Normal > 3.0, Crisis < 2.0
    """
    if value > thresholds['watch']:
        normalized = 0.00
    elif value > thresholds['stress']:
        ratio = (thresholds['watch'] - value) / (
            thresholds['watch'] - thresholds['stress']
        )
        normalized = 0.00 + 0.40 * ratio
    elif value > thresholds['crisis']:
        ratio = (thresholds['stress'] - value) / (
            thresholds['stress'] - thresholds['crisis']
        )
        normalized = 0.40 + 0.60 * ratio
    else:
        normalized = 1.00
    
    return normalized * weight
```

각 지표 정의에 `direction: 'normal' | 'inverse'` 필드를 추가합니다.

### 4.4.4 Binary 임계 처리

Primary Credit, FX Swap 등 binary 임계 지표는 별도 처리합니다.

```python
def indicator_score_binary(value, weight):
    """
    Binary 지표: 0 = Normal, > 0 = Crisis
    """
    return 0.0 if value == 0 else float(weight)
```

---

## 4.5 Layer 1 가중치 배분 (Deep — 45점)

| 카테고리 | 지표 | 가중 | Solo Cap | Direction | 메모 |
|---|---|---|---|---|---|
| **단기금리** | SOFR − EFFR Spread | 4 | 4 | normal | Rate corridor 깨짐 신호 |
| | SOFR vs Fed Funds 상단 | 4 | 4 | normal | 상단 돌파 = Crisis |
| **Fed 운영** | Outright Bill Purchase B/C | 5 | 5 | normal | 딜러 stress |
| | Submitted 주간 변화율 | 4 | 4 | normal | Hidden building |
| | RRP 참가 기관 수 | 3 | 3 | normal | 패닉 조짐 |
| | Primary Credit | 5 | 5 | binary | 즉시 Crisis |
| **H.4.1 조건부** | Reserve Balances + SOFR 동시 | 4 | 4 | conditional | 분배 불균형 |
| | SOMA T-Bill 주간 변화 | 2 | 2 | normal | Fed 공급 페이스 |
| **Cross-Currency** | USD/JPY 1M Basis (편차) | 5 | 5 | inverse | TW 핵심 |
| | USD/JPY 3M Basis (편차) | 4 | 4 | inverse | |
| | FRA-OIS Spread | 3 | 3 | normal | GPT 흡수 |
| **CP** | A2/P2 − AA 30D Spread | 6 | 6 | normal | 6-Indicator 핵심 |
| **합계** | | **45** | | | |

### 4.5.1 가중치 우선순위 사유

| 우선순위 | 지표 | 가중 | 사유 |
|---|---|---|---|
| 1 | A2/P2 − AA 30D Spread | 6 | TW 6-Indicator 의 마지막 임계, 신뢰도 ★★★★★ |
| 2 | USD/JPY 1M Basis | 5 | 글로벌 USD shortage 의 가장 직접 신호 |
| 2 | Outright Bill Purchase B/C | 5 | 딜러 balance sheet stress |
| 2 | Primary Credit | 5 | Binary, 발생 자체가 시스템 위기 |
| 5 | USD/JPY 3M Basis | 4 | 1M 보조 |
| 5 | SOFR − EFFR Spread | 4 | 단기 자금 stress 가장 빠른 신호 |
| 5 | SOFR vs Fed Funds | 4 | Rate corridor 무결성 |
| 5 | Submitted 주간 변화율 | 4 | Hidden building 신호 |
| 5 | Reserve Balances + SOFR | 4 | 분배 불균형 |
| 10 | RRP 참가 기관 수 | 3 | 패닉 조짐 |
| 10 | FRA-OIS Spread | 3 | 보조 (수동 입력) |
| 12 | SOMA T-Bill 주간 변화 | 2 | 보조 (Fed 의 의도 반영) |

### 4.5.2 산출 예시

만약 어느 날 Submitted 가 Stress 구간(0.75)이고 다른 모든 Layer 1 지표가 Normal 이면:

```
Layer 1 점수 = 0.75 × 4 (Submitted weight) = 3.0 / 45
```

이 정도 점수 자체는 작지만, *어느 지표가 움직였는지* 가 더 중요합니다. Decomposition 출력에서 명시됩니다.

또 다른 시나리오: A2/P2 − AA 가 Crisis(1.00) + 1M Basis 가 Stress(0.75) + Submitted 가 Watch(0.40):

```
Layer 1 점수 = (1.00 × 6) + (0.75 × 5) + (0.40 × 4)
            = 6.0 + 3.75 + 1.6
            = 11.35 / 45 (25%)
```

여전히 절대 점수는 낮지만, 이는 명백한 *복합 funding stress* 패턴입니다.

---

## 4.6 Layer 2 가중치 배분 (Middle — 30점)

| 카테고리 | 지표 | 가중 | Solo Cap | Direction | 메모 |
|---|---|---|---|---|---|
| **회사채 스프레드** | Single-B OAS | 7 | 7 | normal | TW 6-Indicator 핵심 |
| | HY OAS (Aggregate) | 5 | 5 | normal | |
| | IG OAS | 3 | 3 | normal | 시스템 리스크 점검 |
| **Credit ETF** | HYG 일간 변화율 | 4 | 4 | normal | 일중 신호 |
| | HYG 5일 누적 변화 | 3 | 3 | normal | 추세 |
| | LQD 일간 변화율 | 2 | 2 | normal | IG 일중 |
| **시스템 / EM** | Korea CDS 5Y | 4 | 4 | normal | EM 프록시 |
| | GSIB CDS 평균 | 2 | 2 | normal | 시스템 |
| **합계** | | **30** | | | |

> Single-B OAS 를 가장 무겁게(7점) 둔 이유는 카테고리 3 의 출처 신뢰도 ★★★★★ 등급이며, 카테고리 1 의 *Credit confirmation* 역할에서 가장 정밀한 신호이기 때문입니다.
>
> CCC OAS 는 카테고리 3 에 추가되었지만 본 가중치 표에는 *제외*했습니다. 사유: HY 와 Single-B 와의 상관관계가 높아 중복 신호. 향후 운영 데이터로 독립 신호인지 검증 후 추가 검토.

---

## 4.7 Layer 3 가중치 배분 (Surface — 15점)

| 카테고리 | 지표 | 가중 | Solo Cap | Direction | 메모 |
|---|---|---|---|---|---|
| **Equity Vol** | VIX (절대 + percentile) | 4 | 4 | normal | 후행 vol |
| | VVIX | 1 | 1 | normal | vol of vol |
| | CBOE SKEW | 1 | 1 | normal | 테일 가격 |
| **Bond Vol** | MOVE Index | 3 | 3 | normal | 채권 vol — Surface 잠정 귀속 |
| **FX / Commodities** | DXY (절대 + 변화율) | 3 | 3 | normal | 100 임계 + cross-layer |
| | WTI (절대 + 변화율) | 2 | 2 | normal | 지정학 |
| | USD/KRW | 1 | 1 | normal | EM |
| **합계** | | **15** | | | |

> Equity indices 변화율(S&P, Nasdaq, KOSPI)은 점수 산출에서 *제외*합니다. 이유: 지수 자체는 후행성이 너무 강해 leading 가치 없음. 단, Decomposition 출력에서는 *맥락 정보* 로 함께 표시합니다.
>
> Crypto (BTC) 도 점수 제외. 주말 카나리아 역할은 별도 알람으로 처리합니다 (4.10.4 참조).

---

## 4.8 Cross-Layer Divergence 가중치 배분 (10점)

이 카테고리는 *단일 지표가 아닌 패턴*을 점수화합니다. 카테고리 3.7 에서 정의한 5개 신호를 그대로 사용합니다.

| 신호 | 가중 | Solo Cap | 메모 |
|---|---|---|---|
| **MOVE / VIX 비율** (>4) | 3 | 3 | 정량 디버전스 |
| **L1 Stress + L3 Calm** (Inverse Turkey) | 4 | 4 | 본 시스템 핵심 |
| **HY OAS 안정 + HYG 일중 -1%** | 1 | 1 | 일중 leading |
| **Submitted ↑ + Accepted 안정** | 1 | 1 | Hidden funding |
| **DXY 100 돌파 + WTI ↑ 동시** | 1 | 1 | USD shortage |
| **합계** | **10** | | |

### 4.8.1 산출 산식

```python
def divergence_score():
    score = 0
    
    # 1. MOVE/VIX 비율 (4 / 5 / 6 임계)
    move_vix = move / vix
    if move_vix > 6:    score += 3
    elif move_vix > 5:  score += 2
    elif move_vix > 4:  score += 1
    
    # 2. Inverse Turkey
    l12_avg = (layer1_normalized + layer2_normalized) / 2
    l3_avg = layer3_normalized
    if l12_avg >= 0.40 and l3_avg <= 0.25:
        days = inverse_turkey_consecutive_days()
        if days >= 3:    score += 4
        elif days >= 2:  score += 3
        else:            score += 2  # 1일 발생
    
    # 3. HY OAS 안정 + HYG 일중 -1%
    if hy_oas_change_5d < 5 and hyg_intraday_change < -0.01:
        score += 1
    
    # 4. Submitted ↑ + Accepted 안정
    if submitted_change_4w > 0.25 and abs(accepted_change_4w) < 0.10:
        score += 1
    
    # 5. DXY 100 돌파 + WTI ↑ 동시
    if dxy >= 100 and wti_change_5d > 0.05:
        score += 1
    
    return min(score, 10)  # 합계 10 cap
```

### 4.8.2 디버전스 신호의 우선순위

5개 신호 중 **Inverse Turkey 가 압도적으로 중요**합니다 (가중 4점, 전체의 40%). 나머지 4개는 상대적으로 보조 신호입니다.

이 비대칭은 의도적입니다. 본 시스템의 가장 중요한 출력은 *표면 평온 + 진앙 폭발* 패턴이며, MOVE/VIX 비율은 그 정량 보강 신호이고, 나머지 3개는 추가 확증 신호입니다.

---

## 4.9 Layer 합산 규칙

### 4.9.1 Layer 내부 합산

각 Layer 의 점수는 **단순 가중 합산**으로 구합니다.

```python
def layer1_score():
    return sum(
        indicator_score(value, thresholds, weight, direction)
        for indicator in layer1_indicators
    )

def layer2_score():
    return sum(...)  # 동일

def layer3_score():
    return sum(...)  # 동일

def total_tmrs():
    return (
        layer1_score() +
        layer2_score() +
        layer3_score() +
        divergence_score()
    )
```

### 4.9.2 Layer Max Score (보조 출력)

각 Layer 내에서 *가장 위험한 단일 지표 점수* 도 함께 추적합니다. Layer 합산만으로는 "전체적으로 약하게 깜빡" vs "한 지표가 폭발" 구분이 안 되므로, 최대값을 보조 표시합니다.

```python
def layer_max_indicator(layer_indicators):
    """
    Layer 내 가장 위험한 지표 식별
    """
    scores = {
        ind.name: indicator_score(ind.value, ind.thresholds, ind.weight, ind.direction)
        for ind in layer_indicators
    }
    max_indicator = max(scores, key=scores.get)
    return max_indicator, scores[max_indicator]

# 출력 예시
# layer1_max = ("A2/P2−AA 30D", 5.4)  # weight 6 중 5.4
```

### 4.9.3 Solo Cap 규칙

각 지표의 최대 기여도는 4.5–4.7 의 *Solo Cap* 열로 제한됩니다 (실질적으로는 weight 와 동일하게 설정). 이는 단일 데이터 오류로 점수가 폭주하는 것을 막습니다.

추가로, **Layer 1 단일 지표 max ≤ 30% of 45 (= 13.5)** 룰을 둡니다. 즉 Layer 1 안에서 어느 한 지표도 13.5점을 초과할 수 없습니다. 4.5 표는 이미 이 룰을 준수합니다 (max = 6).

```python
def enforce_solo_cap(score, indicator_cap, layer_cap_pct=0.30, layer_total=45):
    """
    Solo Cap 규칙 적용
    """
    layer_max = layer_total * layer_cap_pct
    return min(score, indicator_cap, layer_max)
```

### 4.9.4 최종 점수

```
TMRS Total = Layer 1 + Layer 2 + Layer 3 + Divergence
           ∈ [0, 100]
```

---

## 4.10 최종 점수 해석 구간 (0–100)

| 점수 | 등급 | 시각 | 의미 | 권장 모니터링 빈도 |
|---|---|---|---|---|
| 0–25 | **Calm** | 🟢 | 모든 레이어 평온 | 일일 1회 |
| 26–40 | **Watch** | 🟡 | 일부 레이어에서 약한 신호 | 일일 1회 + 알람 활성 |
| 41–55 | **Yellow Alert** | 🟠 | Multi-indicator stress 또는 Divergence | 일중 추가 점검 |
| 56–70 | **Red Alert** | 🔴 | 다층 stress 진입 | 일중 다회 + 푸시 |
| 71–85 | **Crisis** | 🚨 | 본격 위기 진행 | 실시간 |
| 86–100 | **Tail Event** | ☠️ | Black Swan 시나리오 | 실시간 + 24시간 |

> 본 시스템은 점수의 *절대 수준* 보다 **변화의 출처와 디버전스** 가 더 중요합니다. 점수 60 이라도 모든 레이어에서 균등하게 올라온 것이라면 *진행 중인 알려진 위기* 에 가깝고, 점수 45 라도 Layer 1 만 폭발한 상태라면 *Inverse Turkey 직전 신호* 로 더 위험할 수 있습니다.

### 4.10.1 등급별 권장 행동 (참고)

본 시스템은 *행동 권고* 가 아니라 *행동 등급* 만 제공합니다. 실제 행동은 사용자가 결정합니다. 다만 참고용 가이드는 다음과 같습니다.

| 등급 | 일반 시장 모니터링 행동 |
|---|---|
| Calm | 정상 운용 |
| Watch | 일일 리포트 확인, 보유 자산 점검 |
| Yellow | 헤지 도구 점검, 추가 stress test |
| Red | 포지션 리뷰, 헤지 강화 |
| Crisis | 광범위 위험 회피 모드 |
| Tail | 모든 리스크 자산 재평가 |

위 가이드는 자산 연계 영역이지만, 점수 등급의 *의미*를 이해하기 위한 참고로 본 카테고리에 포함합니다.

---

## 4.11 Inverse Turkey 알람 시스템 (점수와 독립 작동)

이것이 본 시스템의 *가장 중요한 출력*입니다. 점수와 별개로 작동하며, 점수가 낮아도 켜질 수 있습니다.

### 4.11.1 트리거 조건

```python
def inverse_turkey_trigger():
    l1_norm = layer1_score() / 45
    l2_norm = layer2_score() / 30
    l3_norm = layer3_score() / 15
    
    l12_avg = (l1_norm + l2_norm) / 2
    
    return l12_avg >= 0.40 and l3_norm <= 0.25
```

여기서 `_norm` 은 해당 Layer 점수를 그 Layer 의 max 로 나눈 값입니다 (0–1 스케일).

> Layer 1+2 평균이 약 Watch 수준(0.40) 이상인데 Layer 3 가 거의 Normal 수준(0.25 이하)이면 발생. 카테고리 3.7 에서 정의한 정성적 패턴의 정량화입니다.

### 4.11.2 Severity 단계

| Level | 명칭 | 조건 | 출력 |
|---|---|---|---|
| 0 | None | 트리거 조건 미충족 | 알람 없음 |
| 1 | Notice | 1일 발생 (당일) | 일일 리포트 강조 표시 |
| 2 | Warning | 2일 연속 발생 | 푸시 알림 + 강조 |
| 3 | Critical | 3일 이상 연속 발생 | 즉시 알림 + 모든 출력 최상단 |

```python
def inverse_turkey_level():
    if not inverse_turkey_trigger():
        return 0
    
    days = consecutive_trigger_days()
    if days >= 3:    return 3  # Critical
    elif days >= 2:  return 2  # Warning
    else:            return 1  # Notice
```

### 4.11.3 알람과 점수의 관계

```
TMRS Score 65 + Inverse Turkey Level 0 → 진행 중인 위기 (대중도 인지)
TMRS Score 45 + Inverse Turkey Level 3 → 표면 평온, 진앙 폭발 (대중 미인지) ★★★ 가장 위험
TMRS Score 80 + Inverse Turkey Level 0 → 후기 위기 (이미 늦음)
```

본 시스템은 사용자가 두 출력을 *동시에* 보면서 의사결정하도록 설계됩니다. **Inverse Turkey Level 3 는 점수가 무엇이든 최우선 알람**입니다.

### 4.11.4 추가 독립 알람 트리거 (점수 외부)

다음 조건들도 점수와 별개로 즉시 알람을 발생시킵니다.

| 트리거 | 알람 | 사유 |
|---|---|---|
| Primary Credit > 0 | Critical | Binary 임계, 발생 자체가 시스템 위기 |
| FX Swap Operations Active | Critical | 글로벌 USD shortage |
| SOFR > Fed Funds 상단 + 5bp | Critical | Rate corridor 깨짐 |
| BTC 24h ±15% (주말) | Notice | 월요일 시장 대비 |
| MOVE/VIX > 6 | Warning | 채권發 위기 임박 |
| Submitted 주간 +50% | Warning | 딜러 stress 급증 |
| DXY 일간 +1.5% | Warning | 글로벌 USD shock |

이 알람들은 점수에 *이미 반영*되어 있지만, 임계 돌파 *순간*에 별도 푸시 알림이 발생합니다.

---

## 4.12 Score Decomposition / Top Movers

본 시스템은 매일 *점수 자체* 뿐 아니라 *변화의 출처* 를 함께 출력합니다.

### 4.12.1 일별 변화 분해

```
Δ TMRS_today = Δ Layer1 + Δ Layer2 + Δ Layer3 + Δ Divergence
```

각 Layer 의 변화량을 따로 출력하여 어느 Layer 가 점수 상승/하락을 주도했는지 보여줍니다.

```python
def daily_decomposition(today_scores, yesterday_scores):
    return {
        'delta_total': today_scores['total'] - yesterday_scores['total'],
        'delta_layer1': today_scores['layer1'] - yesterday_scores['layer1'],
        'delta_layer2': today_scores['layer2'] - yesterday_scores['layer2'],
        'delta_layer3': today_scores['layer3'] - yesterday_scores['layer3'],
        'delta_divergence': today_scores['divergence'] - yesterday_scores['divergence'],
    }
```

### 4.12.2 Top Movers (지표 단위)

전일 대비 점수 변화가 가장 큰 지표 5개를 출력합니다.

```python
def top_movers(yesterday_scores, today_scores, n=5):
    """
    개별 지표 단위 점수 변화 top N
    """
    deltas = {
        k: today_scores[k] - yesterday_scores[k]
        for k in today_scores
        if k not in ['total', 'layer1', 'layer2', 'layer3', 'divergence']
    }
    sorted_deltas = sorted(
        deltas.items(),
        key=lambda x: abs(x[1]),
        reverse=True
    )
    return sorted_deltas[:n]
```

### 4.12.3 Layer Contribution Chart

매일 출력에 다음과 같은 시각화를 포함합니다 (CLI 또는 대시보드).

```
Layer 1 (Deep)        ████████░░░░░░░░░░░░  18 / 45  (40%)  Δ +2.5
Layer 2 (Middle)      ███░░░░░░░░░░░░░░░░░   8 / 30  (27%)  Δ +0.5
Layer 3 (Surface)     ██░░░░░░░░░░░░░░░░░░   3 / 15  (20%)  Δ -0.2
Divergence            ███░░░░░░░░░░░░░░░░░   3 / 10  (30%)  Δ +1.0
                                                            ─────
TMRS Total                                   32 / 100        Δ +3.8
                                                            
Inverse Turkey Alert: Level 1 (Notice) — 1일째

Top Movers:
  1. Submitted 주간 변화율    +1.6  (Watch → Stress)
  2. HYG 일간 변화율         +1.2  (Normal → Watch)
  3. MOVE/VIX 비율           +1.0  (Cross-layer)
  4. A2/P2−AA 30D Spread     +0.8
  5. Korea CDS 5Y            -0.5
```

---

## 4.13 출력 데이터 구조

본 엔진의 일일 출력은 다음 구조를 가집니다.

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Tuple, Optional

@dataclass
class TMRSOutput:
    # === 1. 핵심 점수 ===
    total_score: float          # 0-100
    grade: str                  # Calm/Watch/Yellow/Red/Crisis/Tail
    
    # === 2. Layer별 분해 ===
    layer1_score: float         # 0-45
    layer2_score: float         # 0-30
    layer3_score: float         # 0-15
    divergence_score: float     # 0-10
    
    # 정규화 (0-1, Inverse Turkey 계산용)
    layer1_normalized: float    # 0-1
    layer2_normalized: float    # 0-1
    layer3_normalized: float    # 0-1
    
    # === 3. Layer Max (보조) ===
    layer1_max_indicator: str
    layer1_max_value: float
    layer2_max_indicator: str
    layer2_max_value: float
    layer3_max_indicator: str
    layer3_max_value: float
    
    # === 4. Top Movers (전일 대비) ===
    top_movers: List[Tuple[str, float]]  # [(indicator, delta), ...]
    
    # === 5. 알람 상태 ===
    inverse_turkey_level: int    # 0-3
    inverse_turkey_days: int     # 연속 발생 일수
    active_alerts: List[str]     # binary 알람 리스트
    
    # === 6. 변화량 ===
    delta_total: float
    delta_layer1: float
    delta_layer2: float
    delta_layer3: float
    delta_divergence: float
    
    # === 7. 메타 ===
    timestamp: datetime
    threshold_table_version: str  # "v1.2026-04"
    regime_marker: Optional[str]  # 현재 regime label
    
    # === 8. 맥락 정보 (점수 미반영) ===
    context: dict = field(default_factory=dict)
    # 예: {'sp500_change': -0.012, 'nasdaq_change': -0.018, 'btc_24h': 0.03}
```

이 구조는 SQLite 또는 Parquet 으로 *영구 저장* 됩니다. 시계열 누적이 향후 calibration 의 인풋이 됩니다.

---

## 4.14 카테고리 4 요약 — 한눈에 보기

```
TMRS v2 — 100점 구조

Layer 1 Deep      45점 (12개 지표, max solo cap 6)
Layer 2 Middle    30점 ( 8개 지표, max solo cap 7)
Layer 3 Surface   15점 ( 7개 지표, max solo cap 4)
Divergence        10점 ( 5개 신호, max solo cap 4)

해석 6단계:
  0-25 Calm  →  26-40 Watch  →  41-55 Yellow
  56-70 Red  →  71-85 Crisis  →  86-100 Tail

독립 알람:
  Inverse Turkey      Level 0/1/2/3 (점수 무관)
  Binary Alerts       Primary Credit / FX Swap / SOFR 돌파 등

핵심 출력:
  Total + Layer 분해 + Top Movers + Active Alerts
  + Delta 분해 (전일 대비) + 맥락 정보
```

## 4.15 카테고리 4에서 의도적 추가/배제

| 항목 | 처리 | 사유 |
|---|---|---|
| 4-Layer 구조 (Core/Leading/Event/Position) | **버림** | 카테고리 1·2 결정에 따라 3-Layer + Divergence 로 재구성 |
| Event Risk Layer (CPI/FOMC D-counter) | **본 시스템 제외** | 카테고리 5 ERS 로 분리 |
| Position Trigger Layer (TQQQ/VIX 트랜치) | **본 시스템 제외** | 자산 연계 추후 단계 |
| 단순 4구간 점수 vs 보간 | **보간 권장** | 일일 변화 추적 가능 |
| Solo Cap 규칙 | **신설** | 단일 지표 폭주 방지 |
| Inverse Turkey 별도 알람 | **신설** | 점수와 독립 작동 — 본 시스템 핵심 |
| Layer Max Score 보조 출력 | **추가** | "전체 약함" vs "한 지표 폭발" 구분 |
| Score Decomposition | **신설** | 매일 변화의 출처 추적 필수 |
| Threshold Table Versioning | **추가** | 카테고리 3 의 regime adjustment 연계 |
| 맥락 정보 (점수 미반영 데이터) | **추가** | Equity index, BTC 등 후행 지표 컨텍스트 |
| Direction (normal/inverse/binary) 필드 | **추가** | 역방향 임계 처리 |

## 4.16 카테고리 4에서 미결로 남긴 사항

1. **보간 vs 단순 4구간** — 실제 운영 1개월 후 데이터로 어느 쪽이 더 robust 한지 검증 필요
2. **Solo Cap 수치의 구체 검증** — 현재는 weight = cap 으로 동일 설정. 운영 후 일부 cap 조정 가능
3. **Inverse Turkey 임계의 정확성** — `L1+L2 평균 ≥ 0.40` & `L3 ≤ 0.25` 가 정확한지 historical backtest 필요 (카테고리 7.10.4 영역)
4. **Divergence 5개 신호의 가중치 균형** — 운영 데이터로 어느 신호가 가장 잘 작동하는지 확인 후 재조정
5. **Layer 3 가중치 15 가 너무 낮은지 여부** — 사상적으로는 맞지만 실전 검증 필요
6. **MOVE 의 최종 귀속** — 본 카테고리에서는 Surface (3점)에 두고 MOVE/VIX 는 Divergence 로 처리. 이 분리가 최적인지 검증
7. **Threshold Table 업데이트 주기** — 분기 vs 반기 vs 필요 시
8. **점수 산출 빈도** — 일 1회 vs 일중 다회. 일중 데이터(HYG, VIX, DXY 등)는 일중 갱신 가능
9. **CCC OAS 의 활용** — 카테고리 3 에 추가했으나 본 가중치 표에는 미포함

## 4.17 카테고리 4 마무리 — 핵심 통찰

이 스코어링 엔진의 가장 중요한 설계 결정은 **"점수와 알람의 이원화"** 입니다.

- **점수**는 시장 전반의 stress level 을 한 숫자로 요약 (0–100)
- **알람**은 특정 패턴 (Inverse Turkey, binary triggers)을 점수와 무관하게 즉시 신호

대부분의 시중 risk scoring 시스템은 점수만 출력합니다. 그 결과 *진행 중인 위기*는 잘 잡지만 *Inverse Turkey 시나리오*는 놓칩니다. 본 시스템은 이 둘을 분리해서 관리합니다.

```
TMRS 65 + Inverse Turkey Level 0 = 일반적 risk scoring 과 동일 (위기 진행)
TMRS 45 + Inverse Turkey Level 3 = 본 시스템만 잡아내는 신호 (Hidden building) ★
```

후자가 정확히 카테고리 1 의 사상이 시스템 출력으로 구체화된 형태입니다.

---

# Category 5. Event Risk Score — ERS

## 5.1 카테고리의 역할

본 카테고리는 카테고리 4 의 TMRS 와 별개로 **이벤트 기반 0–100 점수 시스템(ERS)** 을 정의합니다. 두 점수는 Scoring Book 대시보드에 *나란히* 표시되며, 두 점수의 디버전스 자체가 또 다른 형태의 위기 신호가 됩니다.

ERS 는 캘린더 이벤트(CPI, FOMC), 지정학 사건(호르무즈), 뉴스 흐름(Fed 발언, 정책 변화)의 3가지 정보원을 정량화합니다.

## 5.2 핵심 설계 결정 — TMRS 와 분리

먼저 가장 중요한 결정입니다.

| 옵션 | 장점 | 단점 |
|---|---|---|
| **A. TMRS 에 Event Layer 통합** | 단일 점수로 단순 | TMRS 가 *시장 데이터*가 아닌 *주관적 입력*에 오염됨 |
| **B. 별도 점수 (ERS) + 대시보드 병렬 표시** | TMRS 순수성 유지, 두 점수 디버전스 감지 가능 | 점수가 두 개라 학습 곡선 |

**본 시스템은 옵션 B 를 채택**합니다. 카테고리 4 에서 Event Layer 를 의도적으로 제외했던 결정과 일관되며, 무엇보다 **두 점수가 분리되어 있어야 둘 사이의 디버전스를 측정할 수 있습니다.** "큰 이벤트 임박했는데 시장은 평온" = 또 다른 형태의 Inverse Turkey 입니다.

대시보드 구성:

```
┌─────────────────────────────────────────────────────┐
│  Financial Tracker — Main Dashboard                  │
├─────────────────────────────────────────────────────┤
│                                                      │
│   TMRS:  32 / 100   🟡 Watch                        │
│   ERS:   71 / 100   🔴 High Event Risk              │
│                                                      │
│   Divergence:  Δ +39  ⚠️ "Market underpricing event"│
│                                                      │
└─────────────────────────────────────────────────────┘
```

## 5.3 ERS 3-Tier 구조

이벤트는 성격이 매우 다른 세 종류로 나뉩니다. 각각 다른 정량화 방법이 필요합니다.

```
┌──────────────────────────────────────────────────────┐
│  ERS — Total 100 points                              │
├──────────────────────────────────────────────────────┤
│                                                      │
│  Tier 1: Scheduled Events    40 pt                  │
│    └─ 캘린더 기반, 100% 자동                          │
│    └─ CPI, FOMC, NFP, 발표 일정                       │
│                                                      │
│  Tier 2: Geopolitical State  35 pt                  │
│    └─ 룰 기반 + 수동 입력                             │
│    └─ Escalation Level 0–10                         │
│                                                      │
│  Tier 3: News Flow           25 pt                  │
│    └─ LLM 보조 + 키워드 매칭                          │
│    └─ 자동 분류 + sentiment                           │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### 5.3.1 가중치 결정 근거

| Tier | 가중 | 사유 |
|---|---|---|
| **Scheduled (40)** | 가장 큼 | 객관성 가장 높음. 시점이 확정됨. 100% 자동 가능 |
| **Geopolitical (35)** | 큼 | TW 매크로 분석에서 가장 큰 영향 (호르무즈 등) |
| **News (25)** | 가장 작음 | 노이즈가 많지만 무시할 수 없음 |

---

## 5.4 Tier 1 — Scheduled Events (40점)

캘린더 기반으로 100% 자동 계산 가능한 부분입니다. 가장 객관적이고, TW 가 이미 주간 단위로 트래킹하시는 영역입니다.

### 5.4.1 이벤트 분류와 기본 Magnitude

이벤트별로 *시장 영향도(magnitude)* 를 사전에 고정 부여합니다.

| 이벤트 | Magnitude | 발표 빈도 | 비고 |
|---|---|---|---|
| **CPI / Core CPI** | 10 | 월 1회 | 가장 큰 가격 결정 변수 |
| **FOMC 결정** | 10 | 8주 1회 | 정책 변경 가능성 |
| **Powell 기자회견 (FOMC 후)** | 9 | 8주 1회 | 톤 변화 |
| **PCE (Fed 선호 지표)** | 9 | 월 1회 | |
| **NFP / Unemployment** | 8 | 월 1회 | 노동시장 |
| **PPI** | 6 | 월 1회 | CPI 보조 |
| **GDP (분기)** | 6 | 분기 1회 | |
| **ISM Manufacturing** | 5 | 월 1회 | |
| **ISM Services** | 5 | 월 1회 | |
| **Retail Sales** | 5 | 월 1회 | |
| **Treasury Auction (10Y)** | 5 | 월 1회 | TW 관심 |
| **Treasury Auction (30Y)** | 5 | 월 1회 | TW 관심 |
| **Treasury Auction (8-week Bill)** | 4 | 주 1회 | Layer 1 직접 관련 |
| **Powell/Fed 인사 발언** | 4 | 비정기 | |
| **JOLTS** | 4 | 월 1회 | |
| **Initial Jobless Claims** | 3 | 주 1회 | |
| **Consumer Confidence** | 3 | 월 1회 | |
| **Michigan Sentiment** | 3 | 월 2회 | |
| **Beige Book** | 3 | 6주 1회 | |
| **Industrial Production** | 2 | 월 1회 | |
| **Housing Starts** | 2 | 월 1회 | |

이건 *기본값*이며, TW 트래킹 우선순위에 따라 조정 가능합니다. 운영 후 historical 시장 반응으로 calibration 합니다.

### 5.4.2 D-counter Decay

이벤트가 가까워질수록 점수가 올라갑니다. 단순 선형 decay 가 아니라 *비선형 감쇠* 를 적용합니다.

```python
def event_proximity_score(magnitude, days_until):
    """
    이벤트 접근도 점수
    
    D-1: 1.0 × magnitude
    D-3: 0.7 × magnitude
    D-7: 0.4 × magnitude
    D-14: 0.2 × magnitude
    D-30+: 0.05 × magnitude
    """
    if days_until <= 1:    return magnitude * 1.0
    elif days_until <= 3:  return magnitude * 0.7
    elif days_until <= 7:  return magnitude * 0.4
    elif days_until <= 14: return magnitude * 0.2
    else:                  return magnitude * 0.05
```

### 5.4.3 Cluster Bonus (이벤트 충돌)

여러 이벤트가 짧은 기간에 몰리면 단순 합산이 아닌 **추가 가산점** 을 줍니다. 시장이 한 이벤트의 영향을 소화하기 전에 다음 이벤트가 오면 변동성이 비선형적으로 커지기 때문입니다.

```python
def cluster_bonus(events_within_5days):
    """
    5일 이내 magnitude 8+ 이벤트가 2개 이상이면 가산
    """
    high_impact = [e for e in events_within_5days if e.magnitude >= 8]
    if len(high_impact) >= 3: return 8
    if len(high_impact) == 2: return 4
    return 0
```

### 5.4.4 Tier 1 합산 산식

```python
def tier1_score():
    # 1. 모든 다가오는 이벤트의 proximity 점수 합산
    base_sum = sum(
        event_proximity_score(e.magnitude, e.days_until)
        for e in upcoming_events_within_30days
    )
    
    # 2. Cluster bonus
    events_5d = [e for e in upcoming_events_within_30days if e.days_until <= 5]
    cluster = cluster_bonus(events_5d)
    
    # 3. 합산 후 40 cap
    return min(base_sum + cluster, 40)
```

### 5.4.5 산출 예시

다음 시나리오를 가정합니다.

- D-1: CPI (magnitude 10)
- D-3: Powell 발언 (magnitude 4)
- D-5: Treasury 10Y Auction (magnitude 5)
- D-12: FOMC (magnitude 10)

```python
base_sum = (10 * 1.0) + (4 * 0.7) + (5 * 0.4) + (10 * 0.2)
         = 10.0 + 2.8 + 2.0 + 2.0
         = 16.8

# 5일 이내 magnitude 8+: CPI 1개 → cluster bonus = 0
cluster = 0

tier1_score = 16.8 / 40
```

만약 CPI 와 FOMC 가 같은 주에 몰린다면:

```python
base_sum = (10 * 1.0) + (10 * 0.4) + ...
         = 10.0 + 4.0 + ...
         
# 5일 이내 magnitude 8+: CPI + FOMC = 2개 → cluster bonus = 4
cluster = 4

tier1_score 가 크게 증가
```

---

## 5.5 Tier 2 — Geopolitical State (35점)

가장 어려운 영역입니다. 본질적으로 주관적이지만 *룰 기반 + 수동 입력* 으로 정량화 가능합니다.

### 5.5.1 핵심 아이디어 — Escalation Level

지정학 사건마다 0–10 escalation level 을 할당합니다. TW 가 (또는 시스템이 LLM 보조로) 매일 또는 사건 발생 시 업데이트합니다.

| Level | 상태 | 예시 (호르무즈 시나리오) |
|---|---|---|
| 0 | 평온 | 평상시 |
| 1 | 긴장 | 외교적 압박 시작 |
| 2 | 경고 | 양측 발언 격화 |
| 3 | 협상 | 공식 협상 진행 중 |
| 4 | 교착 | 협상 중단 |
| 5 | 군사 동원 | 함대 이동, 미사일 배치 |
| 6 | 국지적 충돌 | 소규모 교전 |
| 7 | 데드라인 임박 | D-3 이내 |
| 8 | 데드라인 만료 | 직접 충돌 위험 |
| 9 | 본격 충돌 | 군사 작전 시작 |
| 10 | 전면전 | 시장 패닉 |

### 5.5.2 점수 산출 산식 — 단일 이벤트

단순히 level × 가중이 아니라 **현재 level + 변화율 + proximity** 세 요소로 분해합니다.

```python
def tier2_score_single(event):
    # 1. 현재 level (max 20점)
    current = event.escalation_level * 2  # 0-10 → 0-20
    
    # 2. 변화율 (max 10점) — 어제 대비 escalation 변화
    delta = event.escalation_level - event.yesterday_level
    if delta >= 3:    velocity = 10
    elif delta >= 2:  velocity = 7
    elif delta >= 1:  velocity = 4
    elif delta == 0:  velocity = 0
    elif delta < 0:   velocity = -3  # de-escalation 은 감점
    
    # 3. Proximity to TW market (max 5점)
    # 호르무즈/대만/유럽 등에 따라 사전 부여
    proximity = event.market_proximity_weight  # 0-5
    
    return min(max(current + velocity + proximity, 0), 35)
```

### 5.5.3 Multi-Event 처리

여러 지정학 사건이 동시에 진행 중일 수 있습니다 (예: 호르무즈 + 대만 + 우크라이나). 이 경우 *최대값 + 보조 가산* 으로 처리합니다.

```python
def tier2_multi_event(events):
    sorted_events = sorted(
        events,
        key=lambda e: tier2_score_single(e),
        reverse=True
    )
    
    main = tier2_score_single(sorted_events[0])  # 100% 반영
    secondary = (
        tier2_score_single(sorted_events[1]) * 0.4
        if len(sorted_events) > 1 else 0
    )
    tertiary = (
        tier2_score_single(sorted_events[2]) * 0.2
        if len(sorted_events) > 2 else 0
    )
    
    return min(main + secondary + tertiary, 35)
```

### 5.5.4 Market Proximity Weight

지정학 사건마다 *TW 시장에 얼마나 가까운가* 의 가중치(0–5)를 사전 부여합니다.

| 영역 | Proximity Weight | 사유 |
|---|---|---|
| 호르무즈 / 중동 (유가) | 5 | 직접 영향 (인플레, 에너지) |
| 대만 해협 (반도체) | 5 | 직접 영향 (한국 경제) |
| 한반도 | 5 | 직접 영향 (한국 시장) |
| 우크라이나 / 동유럽 | 3 | 간접 영향 (에너지, EU) |
| 남중국해 (영유권) | 3 | 간접 영향 (해운) |
| 아프리카 분쟁 | 1 | 거의 영향 없음 |
| 라틴아메리카 분쟁 | 1 | |

이 가중치는 사용자 환경(지역, 자산 구성)에 따라 조정 가능합니다.

### 5.5.5 사용자 입력 인터페이스

대시보드에 **Geopolitical Event Manager** 화면을 두고 사건을 등록·편집·종료할 수 있게 합니다.

```
[Active Geopolitical Events]
─────────────────────────────────────────
Hormuz Strait Tension       Level 7  ↑   D-2     [Edit]
Taiwan Strait               Level 3  →   ongoing [Edit]
Russia-Ukraine              Level 5  ↓   ongoing [Edit]
─────────────────────────────────────────
[+ Add Event]   [Update Levels]   [Archive Resolved]
```

수동 업데이트 부담이 있지만, TW 는 매크로 분석을 매일 하시기 때문에 이미 머릿속에 있는 정보를 저장만 하면 되는 수준입니다. 하루 1분 이내 작업입니다.

### 5.5.6 Geopolitical Event 데이터 구조

```python
@dataclass
class GeopoliticalEvent:
    name: str                          # "Hormuz Strait Tension"
    region: str                        # "Middle East"
    escalation_level: int              # 0-10
    yesterday_level: int               # 어제의 level (변화율 계산용)
    market_proximity_weight: int       # 0-5
    
    started_date: datetime
    last_updated: datetime
    notes: str                         # 사용자 메모
    
    is_active: bool = True
    deadline_date: Optional[datetime]  # 데드라인이 있는 경우
    
    # 시계열
    history: List[Tuple[datetime, int]]  # [(date, level), ...]
```

---

## 5.6 Tier 3 — News Flow (25점)

뉴스는 가장 노이즈가 많지만 무시할 수 없습니다. 두 가지 접근을 결합합니다.

### 5.6.1 Approach A — 키워드 매칭 (룰 기반, 무료)

특정 키워드 출현 빈도와 sentiment 를 점수화합니다.

```python
HIGH_IMPACT_KEYWORDS = {
    # 지정학
    'hormuz': 8, 'strait of hormuz': 8,
    'iran strike': 9, 'israel iran': 7, 'iran nuclear': 6,
    'taiwan invasion': 9, 'pelosi taiwan': 5, 'taiwan strait': 6,
    'north korea missile': 5,
    
    # Fed / 정책
    'fed emergency': 10, 'rate cut emergency': 10,
    'powell hawkish': 6, 'powell dovish': 6,
    'fed pivot': 7, 'fed surprise': 8,
    
    # 시스템 리스크
    'bank failure': 9, 'svb': 9, 'credit suisse': 9,
    'systemic risk': 8, 'too big to fail': 7,
    'liquidity crisis': 9, 'contagion': 8,
    
    # 신용
    'china evergrande': 7, 'default': 6,
    'high yield collapse': 8,
    
    # 시장
    'flash crash': 8, 'market halt': 9,
    'circuit breaker': 8,
    
    # 인플레
    'hyperinflation': 7, 'stagflation': 6,
}

SOURCE_CREDIBILITY = {
    'reuters.com': 1.0,
    'bloomberg.com': 1.0,
    'ft.com': 1.0,
    'wsj.com': 0.95,
    'cnbc.com': 0.7,
    'marketwatch.com': 0.6,
    # ...
}

def tier3_keyword_score(news_items_24h):
    score = 0
    matched_keywords = []
    
    for item in news_items_24h:
        text = (item.title + ' ' + item.summary).lower()
        for keyword, weight in HIGH_IMPACT_KEYWORDS.items():
            if keyword in text:
                credibility = SOURCE_CREDIBILITY.get(item.source_domain, 0.5)
                score += weight * credibility
                matched_keywords.append((keyword, item.source))
    
    return min(score, 15), matched_keywords  # 15 cap (Tier 3 max 25)
```

뉴스 소스는 Bloomberg, Reuters, FT, WSJ 같은 1차 소스를 RSS 또는 무료 API 로 수집합니다.

### 5.6.2 Approach B — LLM 분류 (Anthropic API 활용)

뉴스 아이템을 Claude API 에 보내서 자동 분류합니다. 이게 진짜 가치 있는 부분입니다.

```python
import anthropic

def llm_classify_news(news_text, client):
    prompt = f"""
다음 뉴스를 매크로 시장 영향 관점에서 분류하세요.

뉴스: {news_text}

JSON 형식으로 응답:
{{
  "market_impact": "high" | "medium" | "low" | "none",
  "direction": "risk_off" | "risk_on" | "neutral",
  "category": "monetary" | "geopolitical" | "credit" | "growth" | "inflation",
  "magnitude_score": 0-10,
  "rationale": "한 문장 설명"
}}
"""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",  # 비용 최소화
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Parse JSON from response
    text = response.content[0].text
    try:
        return json.loads(text.strip().strip('```json').strip('```'))
    except json.JSONDecodeError:
        return None

def tier3_llm_score(news_items_24h, client):
    score = 0
    classified = []
    
    for item in news_items_24h:
        classification = llm_classify_news(item.text, client)
        if classification is None:
            continue
            
        if classification['market_impact'] == 'high':
            score += classification['magnitude_score']
            classified.append((item, classification))
    
    return min(score, 10), classified  # 10 cap
```

> **Haiku 4.5 를 쓰는 이유**: 뉴스 분류는 단순 작업이라 Opus 까지 쓸 필요 없고, 비용이 1/10 이하입니다. 하루 100개 뉴스를 분류해도 매우 저렴합니다 (월 $1–5 수준).

### 5.6.3 Tier 3 합산

```python
def tier3_score(news_items_24h, client=None):
    keyword, _ = tier3_keyword_score(news_items_24h)  # max 15
    
    if client is not None:
        llm, _ = tier3_llm_score(news_items_24h, client)  # max 10
        return min(keyword + llm, 25)
    else:
        return min(keyword, 25)  # LLM 없이 keyword 만
```

LLM 호출이 실패하거나 비활성 상태면 keyword 만으로 점수 계산합니다.

### 5.6.4 News Source 권장 목록

| 소스 | 비용 | API/RSS | 우선순위 |
|---|---|---|---|
| Reuters Top News RSS | 무료 | RSS | 1 |
| Bloomberg Markets RSS | 무료 (제한) | RSS | 1 |
| FT Markets | 무료 (제한) | RSS | 2 |
| WSJ Markets | 유료 | RSS | 2 |
| Marketwatch | 무료 | RSS | 3 |
| ZeroHedge | 무료 | RSS | 3 (편향 주의) |
| Yahoo Finance | 무료 | API | 3 |
| Google News (재무 카테고리) | 무료 | RSS | 보조 |

본 시스템은 1순위 소스만으로 시작하고, 운영 후 다른 소스 추가 검토.

---

## 5.7 ERS 최종 합산 및 해석

```python
def calculate_ers(client=None):
    t1 = tier1_score()                       # 0-40
    t2 = tier2_multi_event(active_events)    # 0-35
    t3 = tier3_score(news_24h, client)       # 0-25
    
    total = t1 + t2 + t3
    
    return {
        'total': total,
        'tier1': t1,
        'tier2': t2,
        'tier3': t3,
        'grade': interpret_ers(total),
    }

def interpret_ers(score):
    if score < 21:    return 'Calm'
    elif score < 41:  return 'Watch'
    elif score < 61:  return 'Elevated'
    elif score < 81:  return 'High'
    else:             return 'Critical'
```

| 점수 | 등급 | 의미 |
|---|---|---|
| 0–20 | **Calm** | 평온, 캘린더 비어 있음 |
| 21–40 | **Watch** | 일반적 monitoring |
| 41–60 | **Elevated** | 중간 수준 이벤트 압력 |
| 61–80 | **High** | 큰 이벤트 임박 또는 진행 중 |
| 81–100 | **Critical** | 다중 이벤트 충돌 |

---

## 5.8 TMRS ↔ ERS 디버전스 — 두 번째 Inverse Turkey

이게 사실 이 시스템 전체에서 가장 중요한 출력입니다.

### 5.8.1 디버전스 시나리오 4분면

```
                ERS Low        ERS High
              ┌───────────┬────────────┐
   TMRS High  │     A     │     B      │
              │  진행 중   │  명확 위기  │
              ├───────────┼────────────┤
   TMRS Low   │     C     │     D      │
              │  평온       │  ⚠️ 핵심   │
              └───────────┴────────────┘
```

| 사분면 | 의미 | 권고 |
|---|---|---|
| **A** (TMRS↑ ERS↓) | 알려지지 않은 시장 stress | 원인 조사 필요 |
| **B** (TMRS↑ ERS↑) | 명확한 위기 진행 | 모두가 인지 — 이미 늦음 |
| **C** (TMRS↓ ERS↓) | 진짜 평온 | 정상 운용 |
| **D** (TMRS↓ ERS↑) | **시장이 이벤트를 과소평가** ★ | **선제적 헤지 검토** |

> **사분면 D 가 본 시스템의 가장 가치 있는 출력** 입니다. 큰 이벤트(CPI 임박, 호르무즈 D-2)가 코앞인데 시장이 평온하다면 — 시장은 그 이벤트를 *이미 가격에 반영했다고 믿거나*, 아니면 *과소평가하고 있는* 것입니다. 후자라면 inverse turkey 시나리오가 됩니다.

### 5.8.2 Divergence Score 산출

```python
def tmrs_ers_divergence(tmrs, ers):
    divergence = ers - tmrs
    
    if divergence > 30:
        return {
            'level': 'critical',
            'pattern': 'Market severely underpricing event risk',
            'action': 'Consider preemptive hedging',
            'quadrant': 'D',
        }
    elif divergence > 15:
        return {
            'level': 'warning',
            'pattern': 'Event risk exceeds market stress',
            'action': 'Increase monitoring frequency',
            'quadrant': 'D',
        }
    elif divergence < -15:
        return {
            'level': 'warning',
            'pattern': 'Market stress exceeds known events',
            'action': 'Investigate hidden cause',
            'quadrant': 'A',
        }
    else:
        return {
            'level': 'normal',
            'pattern': 'Aligned',
            'quadrant': 'B' if (tmrs + ers) > 80 else 'C',
        }
```

이 출력이 대시보드에 항상 표시되도록 합니다.

---

## 5.9 한계와 주의점

ERS 는 강력하지만 다음 한계를 명확히 인식해야 합니다.

| 한계 | 설명 | 완화 |
|---|---|---|
| **Tier 2 주관성** | Escalation level 은 본질적으로 주관적 | 룰북 작성, 예시 누적, 사후 검증 |
| **Tier 3 노이즈** | 뉴스 sentiment 는 변동 큼 | 24시간 이동평균, 1차 소스만 |
| **Magnitude 사전 부여** | CPI=10, NFP=8 등은 임의적 | 분기마다 historical 시장 반응으로 검증·재조정 |
| **이벤트 정의 자체의 모호함** | "지정학 사건"의 경계가 불분명 | TW 트래킹 universe 로 명시적 제한 |
| **Cluster bonus 의 비선형성** | 5일 내 충돌 가산점이 과도할 수 있음 | 운영 후 calibration |
| **LLM 비용** | API 호출 누적 | Haiku 사용, 캐싱, 1일 1회 batch |
| **LLM hallucination** | LLM 분류 자체가 틀릴 수 있음 | 카테고리 6 검증 규칙 적용 |
| **이벤트의 사후 평가 부재** | 이벤트가 *실제로 시장에 영향* 미쳤는지 측정 안 됨 | 운영 1년 후 이벤트별 시장 반응 추적 모듈 추가 |

## 5.10 단계적 구현 (v0 → v3)

전체 ERS 를 한 번에 만들지 마시고 **v0 단순 버전으로 시작** 하는 것을 권합니다.

### 5.10.1 v0 (1주일 내 구현 가능)

- Tier 1만 구현 (캘린더 + D-counter, 자동)
- Tier 2 는 단순 escalation level 1개 입력 필드 (multi-event 없음)
- Tier 3 생략

```python
class ERS_v0:
    def calculate(self):
        t1 = tier1_score()
        t2 = self.single_event_level * 2 if self.single_event_level else 0
        return t1 + t2  # max 60 (Tier 1 40 + Tier 2 20)
```

### 5.10.2 v1 (1개월 후)

- Tier 2 multi-event 추가
- Tier 3 키워드 매칭만 추가

```python
class ERS_v1:
    def calculate(self):
        t1 = tier1_score()
        t2 = tier2_multi_event(self.active_events)
        t3 = tier3_keyword_score(self.news_24h)
        return t1 + t2 + t3
```

### 5.10.3 v2 (검증 후)

- Tier 3 LLM 분류 추가
- Cluster bonus tuning

```python
class ERS_v2:
    def __init__(self, anthropic_client):
        self.client = anthropic_client
    
    def calculate(self):
        t1 = tier1_score()
        t2 = tier2_multi_event(self.active_events)
        t3 = tier3_score(self.news_24h, self.client)
        return t1 + t2 + t3
```

### 5.10.4 v3 (운영 데이터 누적 후)

- Magnitude 가중치 historical calibration
- 디버전스 임계값 재조정
- 이벤트 사후 영향 추적 모듈 추가

이 점진적 접근이 robust 한 결과를 만듭니다. 처음부터 전체를 구현하면 어느 부분이 작동하는지 검증하기 어렵습니다.

---

## 5.11 ERS 출력 데이터 구조

```python
@dataclass
class ERSOutput:
    # === 핵심 점수 ===
    total_score: float          # 0-100
    grade: str                  # Calm/Watch/Elevated/High/Critical
    
    # === Tier별 분해 ===
    tier1_score: float          # 0-40 (Scheduled)
    tier2_score: float          # 0-35 (Geopolitical)
    tier3_score: float          # 0-25 (News)
    
    # === Tier 1 상세 ===
    upcoming_events: List[EventInfo]  # 30일 이내 이벤트
    cluster_bonus_applied: int        # 적용된 cluster bonus
    
    # === Tier 2 상세 ===
    active_geopolitical_events: List[GeopoliticalEvent]
    main_event: Optional[str]         # 가장 영향 큰 사건명
    
    # === Tier 3 상세 ===
    news_keyword_matches: List[str]
    news_llm_classifications: List[dict]
    
    # === TMRS와의 디버전스 ===
    tmrs_score: float                 # 함께 출력
    divergence: float                 # ers - tmrs
    quadrant: str                     # A/B/C/D
    divergence_action: str            # 권고 행동
    
    # === 메타 ===
    timestamp: datetime
    version: str                      # "v0" | "v1" | "v2" | "v3"
```

---

## 5.12 카테고리 5 요약 — 한눈에 보기

```
ERS — 100점 구조

Tier 1 Scheduled    40점 (캘린더 자동)
  ├─ 20+ 이벤트 magnitude 사전 부여
  ├─ D-counter decay (1.0 → 0.05)
  └─ Cluster bonus (5일 내 충돌)

Tier 2 Geopolitical 35점 (수동 입력 + LLM 보조)
  ├─ Escalation Level 0-10
  ├─ Current + Velocity + Proximity
  └─ Multi-event 100% / 40% / 20%

Tier 3 News         25점 (자동)
  ├─ Keyword matching (max 15)
  └─ LLM classification (max 10, Haiku 4.5)

해석 5단계:
  0-20 Calm  →  21-40 Watch  →  41-60 Elevated
  61-80 High →  81-100 Critical

핵심 출력:
  ERS Total + Tier 분해 + 활성 이벤트 리스트
  + TMRS-ERS 디버전스 4사분면 + 권고 행동
```

## 5.13 카테고리 5에서 의도적 추가/배제

| 항목 | 처리 | 사유 |
|---|---|---|
| TMRS 와 분리 (옵션 B) | **채택** | 디버전스 측정 가능 |
| 3-Tier 구조 | **채택** | 이벤트 성격별 분리 |
| Escalation Level 0-10 | **채택** | 충분한 세분화 |
| LLM 분류 (Haiku 4.5) | **포함** | 비용 매우 낮음, 가치 큼 |
| 단계적 구현 (v0-v3) | **권장** | Robust 운영 |
| 이벤트 입력 UI | **포함** | 매일 1분 워크플로 |
| Magnitude 사전 부여 | **포함** | 카테고리 6 검증 적용 |
| 이벤트 사후 평가 모듈 | **v3 예정** | 운영 1년 후 |

## 5.14 카테고리 5에서 미결로 남긴 사항

1. **Magnitude 가중치의 정확성** — CPI 10, FOMC 10 등이 실제 시장 영향과 비례하는지 검증 필요
2. **Tier 2 escalation level 의 객관성 확보** — 룰북 또는 예시 누적 필요
3. **Tier 3 keyword 사전의 완성도** — 운영 중 누락 키워드 추가
4. **News source 자동 fetch 의 신뢰성** — RSS feed 안정성, fallback
5. **이벤트 사후 평가 모듈의 구체 설계** — v3 단계
6. **Magnitude 의 historical calibration 방법** — 자동 vs 수동
7. **Tier 2 의 LLM 보조** — geopolitical news 를 LLM 으로 escalation level 자동 추정 가능?

## 5.15 카테고리 5 마무리 — 핵심 통찰

이벤트 점수 시스템의 가장 큰 가치는 *점수 자체* 가 아닙니다. **TMRS 와의 디버전스 측정 도구** 가 됩니다.

```
TMRS 단독:           시장 스트레스 측정
ERS 단독:            이벤트 압력 측정
TMRS ↔ ERS 디버전스:  "시장이 이벤트를 어떻게 가격에 반영하는가" 측정 ★
```

세 번째가 이 시스템의 진짜 출력입니다. 사분면 D (TMRS↓ + ERS↑) 는 본 시스템 전체에서 가장 가치 있는 신호이며, 카테고리 4 의 단일 시스템 Inverse Turkey 와는 다른 *두 번째 형태의 inverse turkey* 입니다.

본 시스템은 TMRS 의 *내부 디버전스* (Layer 1·2 vs Layer 3) 와 ERS-TMRS *시스템 간 디버전스* 의 두 가지를 모두 모니터링합니다. 이 이중 디버전스 감지가 시중 dashboard 와의 가장 큰 차별점입니다.

---

# Category 6. Quantitative Modeling & Verification

## 6.1 카테고리의 역할

본 카테고리는 데이터 처리·계산·해석 과정에서 발생할 수 있는 오류와 편향을 방지하기 위한 **운영 규칙**입니다. 산식이나 임계값이 아니라 *코드와 사람 모두가 따라야 할 행동 규칙* 입니다.

다른 카테고리(데이터, 임계, 점수)는 *무엇을 어떻게* 측정할지를 다루지만, 본 카테고리는 *그 측정이 신뢰할 만한가* 를 보장합니다. 본 카테고리의 규칙이 지켜지지 않으면 다른 모든 카테고리의 출력은 무의미해집니다.

본 카테고리의 핵심은 두 가지입니다.

1. **Anti-Hallucination 검증 규칙 (5개)** — AI 또는 데이터 소스의 오류 방지
2. **Bull/Bear 양방향 대조 원칙** — 인지 편향 방지

---

## 6.2 Anti-Hallucination 검증 규칙 (5개)

### 6.2.1 규칙 1 — 1차 소스 우선

모든 데이터는 1차 소스에서 직접 수집한다. AI 모델이 *기억으로 답변한* 수치는 절대 시스템에 입력하지 않는다.

```
우선순위:
  1. 공식 발표 (federalreserve.gov, bls.gov, treasury.gov)
  2. FRED API (Federal Reserve Bank of St. Louis)
  3. 시장 데이터 API (yfinance, Polygon 등)
  4. 사용자 수동 입력 (Bloomberg/Refinitiv 부재 데이터)
  5. ❌ AI 모델의 기억 답변 (절대 사용 금지)
```

**구현 가이드**: 시스템의 모든 데이터 입력 함수는 *소스 메타데이터를 기록* 합니다.

```python
@dataclass
class DataPoint:
    indicator: str
    value: float
    timestamp: datetime
    source: str           # "fred", "yfinance", "manual", "fed.gov"
    source_url: Optional[str]
    fetched_at: datetime
    confidence: int       # 1-5
```

`source` 가 'ai_memory' 또는 'unknown' 인 데이터는 시스템 입력이 거부됩니다.

### 6.2.2 규칙 2 — AI 산출값 cross-check 의무

본 시스템 또는 외부 AI(Claude, GPT, Gemini)가 산출한 모든 *계산값* 은 코드 또는 1차 데이터로 검증한 후에만 사용한다.

특히 다음 영역은 AI 오류가 빈번하다.

| 영역 | 일반적 오류 | 검증 방법 |
|---|---|---|
| **옵션 가격 / IV 계산** | Black-Scholes 산식 오류, 단위 혼동 | 시장가와 cross-check |
| **USD/JPY Forward 합성** | 금리차만 사용, basis 누락 | 본 문서 카테고리 2.4.4 참조 |
| **가격 변동 방향 주장** | 단방향 추세 가정 | 직전 5–10일 데이터 자동 반증 (규칙 4) |
| **Percentile / 과거 분포** | 잘못된 lookback, 정렬 오류 | scipy.stats 로 재계산 |
| **점수 산출** | 가중치 잘못 곱셈, cap 누락 | unit test |

**구현 가이드**: AI 가 산출한 값은 항상 별도 검증 함수를 거칩니다.

```python
def verify_ai_calculation(label, ai_value, verification_fn):
    """
    AI 가 계산한 값을 1차 검증
    """
    independent_value = verification_fn()
    
    if abs(ai_value - independent_value) / abs(independent_value) > 0.05:
        log_warning(
            f"AI value mismatch for {label}: "
            f"AI={ai_value}, verified={independent_value}"
        )
        return independent_value  # 검증값 우선
    
    return ai_value
```

### 6.2.3 규칙 3 — 동적 페이지 데이터는 수동 입력 우선

federalreserve.gov/releases/cp/rates.htm 같은 동적 렌더링 페이지는 자동 스크래핑이 실패하기 쉽다. 이런 데이터는 *수동 입력 워크플로를 우선 보장* 하고, OCR/자동화는 후순위로 한다.

**수동 입력 대상 데이터** (현재 시점):

| 지표 | 사유 | 자동화 시도 가능성 |
|---|---|---|
| AA 30D / A2/P2 30D Commercial Paper | 동적 페이지 | OCR 또는 FRED 1일 lag |
| USD/JPY Cross-Currency Basis Swap | Bloomberg 부재 | 거의 불가 |
| FRA-OIS Spread | Bloomberg 부재 | 거의 불가 |
| Korea CDS 5Y | 무료 소스 부재 | 부분 가능 (KRX) |
| GSIB CDS (5종) | 무료 소스 부재 | 거의 불가 |

**구현 가이드**: 수동 입력 데이터는 다음 UX 를 제공합니다.

```
[Manual Input Required]
─────────────────────────────────────────
AA 30D CP Rate:        [______]  Last: 4.35 (어제)
A2/P2 30D CP Rate:     [______]  Last: 4.74
USD/JPY 1M Basis:      [______]  Last: -42.1 bp
FRA-OIS:               [______]  Last: 27 bp
Korea CDS 5Y:          [______]  Last: 35 bp
─────────────────────────────────────────
[Submit] [Skip Today (use yesterday)] [Mark as Stale]
```

미입력 시 어제 값을 그대로 사용하되 *stale* 플래그를 표시합니다.

### 6.2.4 규칙 4 — 단방향 추세 주장 자동 반증

"X 는 계속 오르고 있다" / "Y 는 추세적으로 하락 중" 같은 단방향 주장은 직전 5–10일 데이터로 자동 반증한다. 시스템 출력에서 추세 방향을 명시할 때 다음 형식을 강제한다.

```python
def trend_statement(series, lookback=10):
    """
    단정적 추세 주장 대신 정량적 분해
    
    "금이 계속 오르고 있다" 대신
    "지난 10일 중 6일 상승, 누적 +2.3%"
    """
    recent = series.iloc[-lookback:]
    direction = "up" if recent.iloc[-1] > recent.iloc[0] else "down"
    daily_changes = recent.diff().dropna()
    
    same_direction_days = (
        (daily_changes > 0).sum() if direction == "up"
        else (daily_changes < 0).sum()
    )
    
    total_change = recent.iloc[-1] - recent.iloc[0]
    percent_change = (total_change / recent.iloc[0]) * 100
    
    return {
        'direction': direction,
        'consistency': f"{same_direction_days}/{len(daily_changes)} days",
        'total_change': total_change,
        'percent_change': percent_change,
        'verbal': (
            f"지난 {lookback}일 중 {same_direction_days}일 "
            f"{'상승' if direction == 'up' else '하락'}, "
            f"누적 {percent_change:+.2f}%"
        )
    }
```

이 함수의 출력 형식이 본 시스템의 *모든 추세 주장* 표준이 됩니다. 시스템이 자체적으로 또는 사용자에게 어떤 자산의 추세를 언급할 때는 항상 이 형식을 사용합니다.

### 6.2.5 규칙 5 — Threshold Table 버전 명시

카테고리 3 에서 정의한 임계값들은 시간이 지나면 갱신됩니다. 모든 시스템 출력에 *어느 버전의 임계 테이블이 사용되었는지* 명시한다.

```python
@dataclass
class TMRSOutput:
    # ... (기존 필드들)
    threshold_table_version: str  # "v1.2026-04"
```

이를 통해 "왜 이 점수가 나왔는지" 사후 검증이 가능합니다. 임계 변경 후 과거 점수와 직접 비교는 오해를 만들 수 있으므로, 버전이 다른 점수는 시각적으로 구분합니다.

**구현 가이드**:

```python
def render_score_chart(scores_history):
    """
    시계열 차트에서 threshold version 변경 지점 표시
    """
    for date, score in scores_history:
        version = score.threshold_table_version
        if version != current_version:
            # 점선 또는 색 변경으로 구분
            mark_version_boundary(date, version)
```

---

## 6.3 Bull/Bear 양방향 대조 원칙

### 6.3.1 핵심 사상

본 시스템이 시장 상태를 평가할 때, *한쪽 방향의 논리만 채택하는 것* 은 시스템 자체를 컨센서스 트레이드의 일부로 만듭니다. 카테고리 7 의 사상에 따르면 컨센서스는 곧 위기의 씨앗입니다.

따라서 본 시스템은 모든 주요 출력에서 **bullish 해석과 bearish 해석을 동시에 생성** 하고, 두 해석 간 갭(divergence)도 별도로 측정합니다.

### 6.3.2 구현 형태

```python
@dataclass
class MarketView:
    bullish_case: str       # "왜 시장이 안전한가"
    bearish_case: str       # "왜 시장이 위험한가"
    consensus_lean: str     # "bull" | "bear" | "balanced"
    divergence_score: float # 두 케이스의 강도 차이
```

`divergence_score` 가 클수록 한 방향 논리가 우세 = 컨센서스 쏠림 = 추가 경계 신호.

### 6.3.3 일일 리포트에서의 활용

일일 리포트에 항상 두 케이스를 병기합니다.

```
┌─────────────────────────────────────────────────────┐
│  Daily Macro View — 2026-04-08                       │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Bullish Case:                                       │
│  • Fed 의 적극적 T-Bill 매입 (+$14.8B/주)            │
│  • HY OAS 313bp, 임계 하회                           │
│  • CP 스프레드 +38bp, 안정 구간                       │
│                                                      │
│  Bearish Case:                                       │
│  • 호르무즈 데드라인 D-2                              │
│  • DXY 100 돌파, 글로벌 USD 강세                      │
│  • Korea CDS 일간 +5.5%                              │
│                                                      │
│  Lean: 50/50 balanced                                │
│  Divergence Score: 0.15 (낮음 — 양쪽 균형)           │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### 6.3.4 의사결정 로그 누적

TW (또는 LLM) 가 두 케이스 중 하나를 결론으로 채택할 때, 그 사유를 로그에 기록합니다. 시간이 지나면 *어느 쪽 논리가 더 자주 맞았는가* 가 데이터로 누적되고, 본 시스템 자체의 바이어스를 검증할 수 있습니다.

```python
@dataclass
class DecisionLog:
    timestamp: datetime
    market_view: MarketView
    chosen_lean: str        # "bull" | "bear"
    rationale: str
    
    # 사후 검증 (1주일/1개월 후)
    actual_outcome_1w: Optional[float]   # 1주일 후 시장 변화
    actual_outcome_1m: Optional[float]   # 1개월 후
    was_correct: Optional[bool]          # 결론이 옳았는가
```

### 6.3.5 카테고리 5 (ERS) 와의 연계

ERS 의 Tier 3 뉴스 LLM 분류에 Bull/Bear 분리 출력을 포함하면 자연스러운 통합이 됩니다.

```python
def llm_classify_news_v2(news_text, client):
    prompt = f"""
다음 뉴스를 매크로 시장 영향 관점에서 분류하세요.

뉴스: {news_text}

JSON 형식으로 응답:
{{
  "market_impact": "high" | "medium" | "low" | "none",
  "direction": "risk_off" | "risk_on" | "neutral",
  "category": "monetary" | "geopolitical" | "credit" | "growth" | "inflation",
  "magnitude_score": 0-10,
  "rationale": "한 문장 설명",
  
  "bullish_interpretation": "이 뉴스가 시장에 긍정적인 이유 (1-2문장)",
  "bearish_interpretation": "이 뉴스가 시장에 부정적인 이유 (1-2문장)",
  "which_is_stronger": "bull" | "bear" | "balanced"
}}
"""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,  # 더 긴 응답
        messages=[{"role": "user", "content": prompt}]
    )
    return json.loads(response.content[0].text)
```

이렇게 하면 ERS 점수 산출과 동시에 카테고리 6 의 양방향 대조 데이터가 자동으로 누적됩니다.

---

## 6.4 카테고리 6 마무리

본 카테고리는 짧지만, 시스템이 *정확한 신호를 만드는 것* 과 *정확한 신호처럼 보이는 노이즈를 만드는 것* 의 차이를 결정합니다.

검증 규칙 없는 모니터링 시스템은:
- 본인이 만든 환각을 데이터처럼 사용하기 쉽고
- 한 방향 논리에 매료되기 쉽고
- 임계값 변경의 영향을 추적하지 못하고
- 추세를 단정적으로 주장하는 함정에 빠집니다

5개 검증 규칙과 1개 양방향 원칙이 본 시스템의 *위생 규칙* 입니다.

본 카테고리는 코드에 직접 구현되는 부분과 운영 규칙(워크플로) 부분이 혼재되어 있습니다. 코드 부분은 카테고리 4·5 의 모듈에 분산 구현되며, 운영 규칙 부분은 본 문서가 *유일한 reference* 입니다.

## 6.5 카테고리 6 요약 — 한눈에 보기

```
6개 핵심 규칙

[검증 5개]
1. 1차 소스 우선        — AI 기억 답변 금지
2. AI 산출값 cross-check — 자동 검증 함수
3. 동적 페이지는 수동 입력 — Workflow 우선
4. 단방향 추세 자동 반증 — 정량 분해 강제
5. Threshold version 명시 — 사후 검증 가능

[인지편향 1개]
6. Bull/Bear 양방향 대조 — 매일 두 케이스 병기
```

## 6.6 카테고리 6에서 미결로 남긴 사항

1. **AI 산출값 검증의 자동화 수준** — 모든 AI 호출에 검증 함수를 내장할지, 일부만 적용할지
2. **수동 입력 데이터의 stale 임계** — 몇 일 이상 미입력 시 시스템이 거부할지
3. **Bull/Bear 양방향 대조의 적용 범위** — 일일 리포트만 vs 모든 출력
4. **의사결정 로그의 자동 검증 주기** — 1주일 vs 1개월 vs 둘 다
5. **Threshold version 변경 시 과거 점수 재계산 여부** — 일관성 vs 현실성

---

# Category 7. Power Law & Fat-Tail Foundations

## 7.1 카테고리의 역할

본 카테고리는 카테고리 1–6 의 모든 설계 결정이 **왜 그렇게 결정되었는가** 에 대한 사상적 근거를 정리합니다. 코드에 직접 옮겨지는 산식이나 임계값은 본 카테고리 7.10 (향후 코드 영역) 외에는 없지만, 이 사상이 없으면 시스템 전체가 흔들립니다.

구체적으로 다음 결정들이 모두 본 카테고리의 사상에서 나왔습니다.

- 카테고리 1 의 Deep > Middle > Surface 인과 방향
- 카테고리 3 의 percentile rank 병기 (정규분포 가정 회피)
- 카테고리 3 의 Regime Adjustment 가이드
- 카테고리 4 의 Solo Cap 규칙
- 카테고리 4 의 점수와 알람 이원화
- 카테고리 4 의 Inverse Turkey 알람 (점수 무관 작동)
- 카테고리 5 의 TMRS ↔ ERS 디버전스 4사분면
- 카테고리 6 의 Bull/Bear 양방향 대조 원칙

따라서 본 카테고리는 다른 카테고리들의 *backing document* 역할을 합니다. 향후 시스템 수정·확장 시 결정 근거를 찾을 때 참조됩니다.

또한 본 카테고리는 향후 코드로 구현 가능한 5개 영역(7.10)을 포함합니다. 이 영역들은 본 시스템의 *주력 출력* 이 아니라 *보조 진단 도구* 로 운영됩니다.

## 7.2 핵심 명제

> **시장 수익률은 정규분포(Gaussian)가 아니라 거듭제곱 분포(Power Law)를 따른다. 표준 통계 모델은 이 사실을 구조적으로 누락한다. 위기는 "예외"가 아니라 분포의 일부이며, 우리가 모델을 잘못 잡았기 때문에 "예외"로 보일 뿐이다.**

이 명제가 본 시스템 전체의 출발점입니다. Nassim Taleb 의 *Black Swan* (2007) 과 *Antifragile* (2012) 에서 가장 명확하게 정리된 사상이며, Mandelbrot 의 *The (Mis)Behavior of Markets* (2004) 가 학문적 토대를 제공합니다.

본 시스템은 이 명제를 *학술적으로 옳다* 고 단정하지 않습니다. 다만 *정규분포보다는 덜 틀렸다* 는 입장을 취합니다.

## 7.3 Pareto vs Gaussian — 두 분포의 차이

### 7.3.1 시각적 차이

```
정규분포 (Gaussian)              거듭제곱 분포 (Pareto / Power Law)
                                 
       │ ╱╲                              │ ╲
       │╱  ╲                             │  ╲
       ╱    ╲                            │   ╲___
      ╱      ╲                           │       ╲___
─────╱        ╲─────                     │           ╲_____
                                         │
       꼬리 얇음                                꼬리 두꺼움
       극단값 거의 없음                          극단값 자주 발생
```

### 7.3.2 수학적 차이

| 속성 | Gaussian | Power Law |
|---|---|---|
| 확률밀도 함수 | exp(-x²/2σ²) | x^(-α) |
| 평균 | 항상 정의됨 | α > 1 일 때만 정의 |
| 분산 | 항상 정의됨 | α > 2 일 때만 정의 |
| 첨도 (Kurtosis) | 3 (정의) | α > 4 일 때만 정의 |
| -10% 이하 확률 (예시) | 약 0.13% | 약 2-4% (α=3) |
| -30% 이하 확률 | 사실상 0 | 측정 가능 |
| -50% 이하 확률 | 천문학적으로 작음 | 드물지만 가능 |

### 7.3.3 핵심 함의

**Power Law 는 α 값에 따라 분산이 무한이 될 수 있습니다.** 즉 표준편차로 리스크를 측정한다는 발상 자체가 의미를 잃습니다.

이것이 본 시스템이 *어떤 산출값도 ±σ 로 표현하지 않는* 이유입니다. 카테고리 4 의 모든 점수는 percentile 기반이며, 카테고리 3 의 임계값은 4-구간 표현입니다. 정규분포 가정이 시스템의 어떤 출력에도 들어 있지 않습니다.

### 7.3.4 본 시스템에 대한 함의

이 차이가 카테고리 3 의 *percentile rank 병기* 와 카테고리 4 의 *Solo Cap 규칙* 의 근거입니다.

- **Percentile rank** 는 어떤 분포 가정도 하지 않습니다. 데이터 자체가 자기 분포입니다.
- **Solo Cap** 은 "단일 지표가 정규분포 가정 하에 산출된 점수로 폭주하는 것" 을 방지합니다. Power Law 환경에서는 한 지표가 ±10σ 움직일 수 있는데, 정규분포 산식은 이것을 *무한대 위험* 으로 잘못 환산합니다.

---

## 7.4 α 파라미터 — Tail Thickness 의 정량화

Power Law 의 tail 두께를 결정하는 단일 파라미터입니다.

| α 값 | 의미 | 시장 사례 |
|---|---|---|
| α > 4 | 거의 정규분포 | 매우 안정적 시장 |
| 3 < α ≤ 4 | 약한 fat tail | 평상시 미국 주식 |
| 2 < α ≤ 3 | 중간 fat tail | 평상시 EM, 신용시장 |
| 1 < α ≤ 2 | 강한 fat tail | 위기 시 모든 시장 |
| α ≤ 1 | 평균 무정의 | 카오스 (드물게 관찰) |

**α 가 낮을수록 꼬리가 두껍고 극단 사건이 자주 발생** 합니다.

본 시스템의 Threshold Adjustment 가이드(카테고리 3.8) 는 사실상 *α 변화에 대응* 하는 메커니즘입니다. α 가 평상시(예: 3.5) 에서 위기(예: 1.5) 로 점프하면, 동일한 절대 임계값이 *전혀 다른 의미* 를 가지게 됩니다.

---

## 7.5 Conditional Alpha — 가장 중요한 통찰

평상시의 α 와 위기 시의 α 가 *완전히 다른 값* 이라는 사실. 이것이 본 시스템의 가장 깊은 사상적 근거입니다.

```
평상시:        α ≈ 3.5    (꼬리 얇음, 극단값 드뭄)
                   ↓
스트레스 진입:  α ≈ 2.5    (꼬리 두꺼워짐)
                   ↓
위기 가속:     α ≈ 1.5    (꼬리 매우 두꺼움)
                   ↓
패닉:         α ≈ 1.0    (사실상 카오스)
```

**같은 시장이 시간에 따라 다른 분포를 따른다** 는 것입니다. 이 변화는 부드럽지 않고 *점프* 로 일어납니다.

### 7.5.1 α 를 낮추는 메커니즘

현대 금융시장에서 α 를 구조적으로 낮추는 세 가지 요인입니다.

**1. 알고리즘 트레이딩의 동조화**

같은 신호에 같은 방향으로 반응하는 알고리즘들이 시장 참여자의 다수를 차지하면, 가격 움직임이 가격 움직임을 강화하는 양의 피드백 루프가 형성됩니다. 알고리즘이 시장의 50% 를 차지할 때와 90% 를 차지할 때의 α 는 다릅니다.

**2. 레버리지의 구조적 확대**

레버리지 비율 L 을 적용하면 α 가 대략 α/L 로 변환됩니다. TQQQ 같은 3배 레버리지는 기초자산의 α 를 1/3 로 낮춥니다. 시장 전체의 평균 레버리지가 올라가면 시스템 전체의 α 가 동시에 낮아집니다.

**3. 유동성의 비선형성**

평상시에는 풍부하던 유동성이 스트레스 시에는 *동시에* 사라집니다. 이것이 카테고리 1 의 Deep Layer 가 가장 먼저 깨지는 이유입니다. 유동성이 풍부할 때의 α 와 유동성이 사라질 때의 α 는 사실상 다른 시장입니다.

### 7.5.2 본 시스템에 대한 함의

Conditional α 사상이 본 시스템의 다음 두 결정의 직접 근거입니다.

- **카테고리 4 의 점수/알람 이원화** — 점수는 *현재 α* 를 반영하고, 알람은 *α 의 변화* 를 반영합니다. 둘이 다른 정보를 제공합니다.
- **카테고리 4 의 Inverse Turkey 알람** — α 가 평상시 수준일 때 (= Layer 3 평온), Layer 1·2 가 stress 를 보내고 있다면 그것은 *α 가 곧 점프할 신호* 입니다.

---

## 7.6 Inverse Turkey — 시스템 설계의 심장

칠면조의 우화입니다. 1,000일 동안 매일 모이를 받아먹은 칠면조에게 1,000일째 데이터로 1,001일째를 예측하라고 하면, 그 어떤 통계 모델도 *추수감사절 도살* 을 예측하지 못합니다. 모든 지표가 *역사상 가장 평온* 하다고 말할 것입니다.

### 7.6.1 시장 관점에서의 의미

위기는 *가장 평온해 보이는 순간* 에 옵니다. 그 이유는:

- 평온이 길어질수록 시장 참여자는 평온이 *영구적* 이라고 믿음
- 그 믿음 위에 레버리지가 쌓임 (평균 회귀 베팅)
- 변동성 매도(short vol) 포지션이 누적
- α 가 *내부적으로* 낮아지지만 *외부적으로* 는 보이지 않음
- 작은 충격이 비대칭적으로 큰 반응을 유발 (점프)

### 7.6.2 본 시스템의 답변

본 시스템은 이 우화에 두 가지 메커니즘으로 대응합니다.

**메커니즘 1: 표면이 아닌 진앙을 본다 (카테고리 1·2·3·4)**

칠면조가 농부의 부엌(Deep Layer)을 봤다면 1,000일째 도살을 예측할 수 있었을 것입니다. 본 시스템의 Deep Layer 우선순위가 이 사상의 직접 구현입니다.

**메커니즘 2: 평온 자체를 신호로 읽는다 (카테고리 4 의 Inverse Turkey 알람)**

```
조건: Layer 1·2 가 stress + Layer 3 평온
→ Inverse Turkey Level 1/2/3
→ 점수와 무관하게 즉시 알람
```

이것은 단순한 디버전스 감지가 아닙니다. **"평온은 위기의 부재가 아니라 위기의 직전 상태일 수 있다" 는 사상** 의 정량화입니다.

---

## 7.7 Taleb 의 4사분면 (Fourth Quadrant Problem)

Taleb 이 모든 모델링을 분류한 매트릭스입니다.

| | 단순 보상 (simple payoff) | 복잡 보상 (complex payoff) |
|---|---|---|
| **얇은 꼬리 (정규분포)** | 1사분면: 안전 — 모델 작동 | 2사분면: 관리 가능 |
| **두꺼운 꼬리 (Power Law)** | 3사분면: 관리 가능 | **4사분면: 통계 모델 구조적 실패** |

### 7.7.1 현대 금융시장의 위치

현대 금융시장은 압도적으로 4사분면에 있습니다. 두꺼운 꼬리(Power Law) + 복잡한 보상 구조(파생상품, 레버리지, 상호 연결된 거래상대방).

이 사분면에서는:

- 과거 데이터 기반 VaR 모델이 *구조적으로* 리스크를 과소평가합니다
- "100년에 한 번" 사건이 실제로는 10–20년에 한 번 옵니다
- 모델의 신뢰구간은 무의미합니다

### 7.7.2 본 시스템에 대한 함의

본 시스템이 출력하는 어떤 점수도 *확률적 보장* 을 제공하지 않습니다. "TMRS 60 = 위기 확률 X%" 같은 해석은 4사분면 환경에서 의미 없습니다. 본 시스템은 *확률 추정기* 가 아니라 *조기 경보 시스템* 입니다.

이것이 카테고리 4 의 점수 해석 구간이 *확률* 이 아니라 *행동 권고* (Calm/Watch/Yellow/Red/Crisis/Tail) 로 표현된 이유입니다.

---

## 7.8 시스템 사상의 종합 — 7개 핵심 원칙

본 카테고리의 모든 내용을 본 시스템 운영에 적용하면 다음 7개 원칙으로 압축됩니다.

### 원칙 1. 정규분포 가정 금지

어떤 산출값도 ±σ 로 표현하지 않는다. Percentile 과 4구간(Normal/Watch/Stress/Crisis) 으로만 표현한다.

### 원칙 2. 진앙 우선

Deep Layer 는 항상 Surface Layer 보다 먼저, 자주, 정확하게 본다.

### 원칙 3. 평온 의심

모든 지표가 평온할 때가 가장 위험할 수 있다. Inverse Turkey 알람은 점수와 독립적으로 작동한다.

### 원칙 4. 변화 > 절대값

같은 절대값이라도 *어디서 와서 어디로 가는지* 가 더 중요하다. Top Movers 와 Layer Decomposition 출력이 점수보다 자주 봐야 할 정보다.

### 원칙 5. 디버전스 감지

단일 지표보다 *여러 지표 간 비대칭* 이 더 가치 있는 신호다. Cross-Layer Divergence (카테고리 4) 와 TMRS↔ERS Divergence (카테고리 5) 는 본 시스템의 가장 중요한 출력이다.

### 원칙 6. Solo Cap

단일 지표가 전체 점수를 폭주시키지 못하게 한다. 한 데이터 오류가 시스템 전체를 오염시키지 않게 한다.

### 원칙 7. 확률 아닌 행동 권고

본 시스템은 위기 *확률* 을 추정하지 않는다. 대신 *지금 무엇을 해야 하는가* 에 대한 행동 등급을 제공한다.

---

## 7.9 한계와 주의점

이 사상 자체에도 한계가 있습니다. 이를 명시해두지 않으면 시스템이 또 다른 형태의 *과신* 을 만들 수 있습니다.

### 한계 1. α 자체를 측정하기 어렵다

본 시스템은 α 를 직접 추정하지 않습니다. 추정하려면 충분한 tail event 가 필요한데, 그 데이터를 얻을 즈음에는 이미 늦습니다. 본 시스템은 α 를 *간접 추론* 만 합니다 (디버전스 패턴, regime change marker 등). 7.10.1 의 Hill Estimator 모듈도 *추정* 일 뿐 진짜 α 가 아닙니다.

### 한계 2. Power Law 도 모델이다

Taleb 은 Power Law 도 결국 *모델* 이라고 명시합니다. 실제 시장이 정확히 Power Law 를 따른다고 단정할 수 없습니다. 본 시스템은 "정규분포보다는 Power Law 가 덜 틀렸다" 는 입장이지 "Power Law 가 옳다" 는 입장이 아닙니다.

### 한계 3. 사상이 맞아도 구현이 틀릴 수 있다

Inverse Turkey 알람의 임계값(L1+L2 ≥ 0.40, L3 ≤ 0.25)은 본 시스템이 임의로 설정한 것입니다. 사상은 옳지만 구체 임계가 작동할지는 검증이 필요합니다. 7.10.4 의 Backtester 가 이 검증을 위한 것입니다.

### 한계 4. 확증 편향 위험

Inverse Turkey 사상에 너무 매료되면 *모든 평온* 을 위기 직전 신호로 오해할 수 있습니다. 진짜 평온도 존재합니다. 카테고리 4 의 알람 단계(Notice/Warning/Critical) 와 연속 발생 일수 조건이 이 편향에 대한 약한 방어책이며, 카테고리 6 의 Bull/Bear 양방향 대조 원칙이 또 다른 방어책입니다.

### 한계 5. 시간 비대칭

Power Law 사상은 *극단 사건의 빈도* 를 강조하지만, 평상시 시장의 정상적 작동을 평가절하할 수 있습니다. 본 시스템이 항상 "곧 위기다" 라고 외치면 결국 무시됩니다 ("Crying Wolf" 문제). 카테고리 4 의 Calm 등급(0–25점)이 *진짜 평온도 인정한다* 는 점이 이 균형의 핵심입니다.

---

## 7.10 향후 코드 구현 가능 영역

본 카테고리 7 은 사상 영역이지만, *그 사상을 정량화하는 도구* 는 코드로 구현 가능합니다. 5가지 영역을 우선순위 순으로 제안합니다.

### 7.10.1 영역 1 — α (Tail Index) 추정 모듈

**난이도: 중**

자산 수익률 시계열에서 α 를 추정합니다. **Hill Estimator** 가 가장 표준적입니다.

```python
import numpy as np
from typing import Optional

def hill_estimator(returns, k_fraction=0.05) -> Optional[float]:
    """
    Hill Estimator 로 tail index α 추정
    
    Parameters
    ----------
    returns : np.array or pd.Series
        일별 수익률 시계열
    k_fraction : float
        상위 k% 를 tail 로 간주 (보통 5%)
    
    Returns
    -------
    alpha : float or None
        추정된 tail index. 낮을수록 두꺼운 꼬리.
        데이터 부족 시 None.
    
    Notes
    -----
    Hill (1975) 의 표준 추정법.
    losses 만 사용 (left tail).
    """
    # 음의 수익률(손실)만 사용
    losses = -returns[returns < 0]
    if len(losses) < 50:
        return None  # 데이터 부족
    
    # 절대값 기준 정렬
    sorted_losses = np.sort(losses)[::-1]  # 큰 순
    k = max(int(len(sorted_losses) * k_fraction), 10)
    
    # Hill 추정
    log_ratios = np.log(sorted_losses[:k] / sorted_losses[k])
    alpha_inverse = log_ratios.mean()
    
    return 1.0 / alpha_inverse
```

**활용 방법**: 본 시스템의 모니터링 대상 자산(S&P, Nasdaq, HYG, IWM 등) 별로 α 를 매주 재계산하여 시계열로 누적. α 의 *변화* 자체가 신호가 됩니다.

```python
def weekly_alpha_update(asset_universe):
    """
    매주 α 시계열 업데이트
    """
    results = {}
    for asset in asset_universe:
        returns = fetch_returns(asset, days=252)
        alpha = hill_estimator(returns)
        if alpha is not None:
            results[asset] = alpha
    
    save_to_timeseries('alpha_estimates', results)
    return results
```

**대시보드 출력**: Scoring Book 의 보조 위젯으로 표시.

```
[Tail Index Monitor — α estimates]
─────────────────────────────────
S&P 500     α = 3.1   (Δ -0.3 vs 4w ago) ⚠️
Nasdaq      α = 2.8   (Δ -0.4) ⚠️
HYG         α = 2.5   (Δ -0.2)
EMB         α = 2.2   (Δ -0.1)
─────────────────────────────────
* α 가 낮아지는 추세 = fat tail 강화
```

### 7.10.2 영역 2 — Conditional α 추적

**난이도: 중상**

시간 윈도우별로 α 를 분리 계산하여 *α 변화* 를 시계열화합니다.

```python
import pandas as pd

def rolling_alpha(returns: pd.Series, window=252, step=21) -> pd.DataFrame:
    """
    1년 rolling window 로 α 시계열 산출
    
    Parameters
    ----------
    returns : pd.Series
        datetime index 가진 수익률 시계열
    window : int
        rolling window 크기 (252 = 1Y)
    step : int
        업데이트 주기 (21 = 1개월)
    
    Returns
    -------
    DataFrame with columns ['date', 'alpha']
    """
    alphas = []
    for end in range(window, len(returns), step):
        window_returns = returns.iloc[end-window:end]
        alpha = hill_estimator(window_returns.values)
        if alpha is not None:
            alphas.append({
                'date': returns.index[end],
                'alpha': alpha
            })
    return pd.DataFrame(alphas)
```

**활용**: α 가 평상시(예: 3.5) 에서 위기 시(예: 1.5) 로 점프하는 패턴을 *역사적으로 검증*. 본 시스템 운영 중 α 가 평상시 수준에서 *하락 추세* 에 들어가면 별도 알람.

이 알람은 카테고리 4 의 Cross-Layer Divergence 6번째 신호로 추가 가능합니다.

```python
def alpha_decay_signal(alpha_series, lookback_weeks=4):
    """
    α 가 4주 이상 하락 추세인지 감지
    """
    if len(alpha_series) < lookback_weeks:
        return False
    
    recent = alpha_series.tail(lookback_weeks)
    return all(
        recent.iloc[i] >= recent.iloc[i+1]
        for i in range(len(recent)-1)
    )
```

### 7.10.3 영역 3 — Fat-Tail Monte Carlo Simulator

**난이도: 중**

Student-t 또는 Pareto 분포 기반 시뮬레이션. 카테고리 7 의 사상을 *시나리오 생성* 에 활용합니다.

```python
import numpy as np
from scipy.stats import t

def fat_tail_simulation(
    initial_value: float,
    days: int,
    n_paths: int = 10000,
    df: float = 4,
    sigma: float = 0.02
) -> np.ndarray:
    """
    Student-t 기반 fat-tail 가격 경로 시뮬레이션
    
    Parameters
    ----------
    initial_value : float
        시작 가격
    days : int
        시뮬레이션 기간 (영업일)
    n_paths : int
        시뮬레이션 경로 수
    df : float
        Student-t 자유도 (3-5 권장, 낮을수록 fat tail)
    sigma : float
        일일 변동성
    
    Returns
    -------
    paths : ndarray
        shape (days, n_paths)
    """
    # Student-t 샘플링 (분산 정규화)
    z = t.rvs(df=df, size=(days, n_paths))
    z = z * np.sqrt((df - 2) / df)
    
    # 가격 경로 생성
    daily_returns = sigma * z
    log_paths = np.cumsum(daily_returns, axis=0)
    paths = initial_value * np.exp(log_paths)
    
    return paths

def compare_normal_vs_fat_tail(
    initial: float,
    days: int,
    sigma: float
) -> dict:
    """
    정규분포 vs Student-t 시나리오 비교
    """
    n_sims = 10000
    
    # 정규분포
    z_normal = np.random.randn(days, n_sims)
    paths_normal = initial * np.exp(np.cumsum(sigma * z_normal, axis=0))
    
    # Student-t (df=4)
    paths_t = fat_tail_simulation(initial, days, n_sims, df=4, sigma=sigma)
    
    # 극단 시나리오 빈도 비교
    final_normal = paths_normal[-1, :]
    final_t = paths_t[-1, :]
    
    threshold_drawdown = initial * 0.80  # -20%
    
    return {
        'normal_pct_below_threshold': (final_normal < threshold_drawdown).mean(),
        'fat_tail_pct_below_threshold': (final_t < threshold_drawdown).mean(),
        'fat_tail_premium': (
            (final_t < threshold_drawdown).mean() /
            max((final_normal < threshold_drawdown).mean(), 1e-9)
        ),
    }
```

**활용**: 현재 시장 상태에서 향후 N일 내 *극단 시나리오의 빈도* 를 정량화. 정규분포 기반과 Student-t 기반 결과를 나란히 출력하여 차이가 곧 *fat-tail 프리미엄* 이 됩니다.

```
[Scenario Simulator — Next 30 trading days]
─────────────────────────────────────────
S&P 500 (current = 5832)
  
  Probability of -20% drawdown:
    Normal model:    0.04%
    Student-t (df=4): 1.8%
    Fat-tail premium: 45x

  → 정규분포 기반 의사결정의 위험성 정량화
─────────────────────────────────────────
```

### 7.10.4 영역 4 — Inverse Turkey Backtester

**난이도: 상**

본 시스템의 Inverse Turkey 알람이 *역사적으로 작동했는가* 를 검증하는 모듈입니다.

```python
from datetime import timedelta
import pandas as pd

def backtest_inverse_turkey(
    historical_data: pd.DataFrame,
    lookforward_days: int = 20
) -> pd.DataFrame:
    """
    과거 데이터에서 Inverse Turkey 트리거 발생 시점을 찾고,
    그 후 lookforward_days 동안의 시장 반응을 측정
    
    Parameters
    ----------
    historical_data : pd.DataFrame
        TMRS 필요한 모든 지표의 historical data
    lookforward_days : int
        트리거 후 관찰 기간
    
    Returns
    -------
    DataFrame with trigger dates and outcome metrics
    """
    triggers = find_inverse_turkey_triggers(historical_data)
    
    results = []
    for trigger_date in triggers:
        future_window = historical_data.loc[
            trigger_date : trigger_date + timedelta(days=lookforward_days)
        ]
        
        if len(future_window) < lookforward_days * 0.5:
            continue
        
        results.append({
            'trigger_date': trigger_date,
            'tmrs_at_trigger': historical_data.loc[trigger_date, 'tmrs_total'],
            'max_drawdown_pct': calculate_max_drawdown(future_window['sp500']),
            'vix_peak': future_window['vix'].max(),
            'vix_at_trigger': historical_data.loc[trigger_date, 'vix'],
            'crisis_materialized': future_window['vix'].max() > 30,
            'days_to_vix_peak': (future_window['vix'].idxmax() - trigger_date).days,
        })
    
    return pd.DataFrame(results)

def find_inverse_turkey_triggers(historical_data):
    """
    과거 데이터에서 IT 조건 만족 일자 추출
    """
    triggers = []
    for date in historical_data.index:
        l1_norm = historical_data.loc[date, 'layer1_score'] / 45
        l2_norm = historical_data.loc[date, 'layer2_score'] / 30
        l3_norm = historical_data.loc[date, 'layer3_score'] / 15
        
        if (l1_norm + l2_norm) / 2 >= 0.40 and l3_norm <= 0.25:
            triggers.append(date)
    
    return triggers

def calculate_max_drawdown(prices):
    """
    Max drawdown 계산
    """
    cummax = prices.cummax()
    drawdown = (prices - cummax) / cummax
    return drawdown.min()

def evaluate_backtest(backtest_results):
    """
    백테스트 결과 통계
    """
    total_triggers = len(backtest_results)
    if total_triggers == 0:
        return {'note': 'No triggers found in history'}
    
    crisis_rate = backtest_results['crisis_materialized'].mean()
    avg_drawdown = backtest_results['max_drawdown_pct'].mean()
    avg_vix_peak = backtest_results['vix_peak'].mean()
    
    return {
        'total_triggers': total_triggers,
        'crisis_materialization_rate': crisis_rate,
        'avg_drawdown_after_trigger': avg_drawdown,
        'avg_vix_peak_after_trigger': avg_vix_peak,
        'false_positive_rate': 1 - crisis_rate,
    }
```

**활용**: 카테고리 4 에서 설정한 Inverse Turkey 임계값(L1+L2 ≥ 0.40, L3 ≤ 0.25) 이 적정한지 검증. 임계 조정의 근거가 됩니다.

단, 이건 본 시스템의 모든 다른 모듈이 작동한 후에 가능합니다 (역사 데이터에 대해 본 시스템의 점수를 소급 적용해야 하므로). 운영 6개월 이상 누적 후 의미 있는 백테스트 가능.

### 7.10.5 영역 5 — Power Law Distribution Fitter

**난이도: 상**

자산 수익률 분포가 정규분포 vs Power Law 중 어느 쪽에 더 잘 fit 하는지 통계적으로 비교.

```python
# 의존성: pip install powerlaw
import powerlaw
import numpy as np

def compare_distributions(returns: np.ndarray) -> dict:
    """
    수익률이 정규분포 vs Power Law 중 어느 쪽인지 비교
    
    Returns
    -------
    dict with keys:
        - alpha: Power law tail index
        - power_law_better: bool
        - p_value: 비교 검정의 p-value
        - interpretation: 자연어 해석
    """
    losses = -returns[returns < 0]
    if len(losses) < 100:
        return {'note': 'Insufficient data'}
    
    # Power Law fit
    fit = powerlaw.Fit(losses, discrete=False)
    alpha = fit.alpha
    
    # 정규분포 vs Power Law 비교 (log-likelihood ratio)
    R, p = fit.distribution_compare('power_law', 'lognormal')
    
    if R > 0 and p < 0.1:
        interpretation = 'Power Law fits better'
    elif R < 0 and p < 0.1:
        interpretation = 'Lognormal fits better'
    else:
        interpretation = 'Inconclusive'
    
    return {
        'alpha': alpha,
        'power_law_better': R > 0,
        'p_value': p,
        'log_likelihood_ratio': R,
        'interpretation': interpretation,
    }

def quarterly_distribution_check(asset_universe):
    """
    분기별 자산별 분포 성격 진단
    """
    results = {}
    for asset in asset_universe:
        returns = fetch_returns(asset, days=63)  # 1 quarter
        results[asset] = compare_distributions(returns)
    
    return results
```

**활용**: 분기별로 자산별 분포 성격을 재진단. "이번 분기는 S&P 가 정규분포에 가까웠다" vs "Power Law 성격이 강해졌다" 는 정보 자체가 regime change marker 가 됩니다.

```
[Quarterly Distribution Diagnosis — Q2 2026]
─────────────────────────────────────────
S&P 500    α = 3.2   Power Law fits better (p=0.02)
Nasdaq     α = 2.7   Power Law fits better (p=0.01)
HYG        α = 2.4   Power Law fits better (p=0.001)
LQD        α = 4.1   Inconclusive (p=0.3)
─────────────────────────────────────────
* HY 가 가장 fat-tail. IG 는 정규분포에 가까움.
```

---

## 7.11 향후 코드 구현 우선순위 권장

위 5개 영역을 모두 한 번에 만들 필요는 없습니다. **본 시스템이 어느 정도 자리잡은 후 (운영 3–6개월)** 다음 순서로 추가하시는 것을 권합니다.

| 단계 | 영역 | 의존성 | 가치 | 예상 소요 |
|---|---|---|---|---|
| 1 | α 추정 (영역 1) | 시계열 데이터만 | 즉시 활용 가능 | 2–3일 |
| 2 | Conditional α (영역 2) | 영역 1 의 확장 | regime change 정량화 | 1주 |
| 3 | Distribution Fitter (영역 5) | `powerlaw` 라이브러리 | 분기별 진단 | 3–5일 |
| 4 | Fat-Tail Simulator (영역 3) | 영역 1·2 결과 활용 | 시나리오 생성 | 1주 |
| 5 | Inverse Turkey Backtester (영역 4) | 모든 다른 모듈 완성 | 임계값 검증 | 2–3주 |

### 7.11.1 단계별 가치 설명

**단계 1 (α 추정)**: 가장 빠르게 가치를 보이는 모듈. 의존성이 거의 없고 (numpy 만 있으면 됨) Hill Estimator 는 30 줄 이내. 즉시 대시보드 위젯으로 표시 가능.

**단계 2 (Conditional α)**: 단계 1 의 자연스러운 확장. 시계열 누적이 필요해 데이터 6개월 이상 필요.

**단계 3 (Distribution Fitter)**: 분기별 진단으로 충분. 운영 부담 작음. `powerlaw` 라이브러리 의존성 추가.

**단계 4 (Monte Carlo)**: 시나리오 생성 도구. 직접 alarm 에 사용되지는 않지만 사용자 의사결정 보조.

**단계 5 (Backtester)**: 가장 어렵지만 가장 가치가 있습니다. 본 시스템 전체의 *자기 검증* 이기 때문입니다. 하지만 운영 1년 이상의 데이터가 누적된 후에야 의미 있는 결과 도출 가능.

### 7.11.2 단계별 데이터 요구사항

| 단계 | 필요 데이터 |
|---|---|
| 1 | 자산 수익률 시계열 1년 이상 |
| 2 | 단계 1 + 시계열 누적 6개월 이상 |
| 3 | 자산 수익률 시계열 1분기 이상 |
| 4 | 자산 수익률 시계열 1년 이상 (변동성 추정용) |
| 5 | 본 시스템 점수 히스토리 1년 이상 + 자산 수익률 |

---

## 7.12 카테고리 7 향후 확장에 대한 한계

영역 1–5 를 모두 구현해도 한계는 그대로 유지됩니다.

- **α 추정은 본질적으로 후행적** 입니다. 충분한 tail event 가 있어야 추정 가능한데, 그때는 이미 위기가 진행 중입니다.
- **Backtesting 결과는 과거에 대한 것** 입니다. 미래 위기가 과거 패턴을 따를 보장이 없습니다 (4사분면 문제).
- **모든 코드 구현은 모델** 입니다. Power Law 자체가 모델인 것과 같은 한계입니다.

따라서 영역 1–5 는 본 시스템의 *주력 출력* 이 아니라 *보조 진단 도구* 로 운영해야 합니다. 주력은 여전히 카테고리 4 의 TMRS 와 카테고리 5 의 ERS 이며, 영역 1–5 는 *왜 그 점수들이 그렇게 나오는가* 에 대한 깊은 설명을 제공하는 역할입니다.

---

## 7.13 카테고리 7 마무리

이 카테고리는 코드로 직접 구현되는 부분이 적지만, **시스템이 흔들릴 때 돌아와야 할 기준점** 입니다.

향후 시스템 운영 중 다음과 같은 상황이 발생하면 본 카테고리를 다시 읽어야 합니다.

| 상황 | 참조 섹션 |
|---|---|
| 점수가 낮은데 위기가 발생했을 때 | 원칙 3 (평온 의심), 원칙 5 (디버전스), 7.6 (Inverse Turkey) |
| 임계값을 조정하고 싶을 때 | 7.5 (Conditional α), 카테고리 3.8 (Regime Adjustment) |
| 시스템 출력을 *확률*로 해석하고 싶을 때 | 7.7 (4사분면) |
| 단일 지표에 가중치를 더 주고 싶을 때 | 원칙 6 (Solo Cap), 카테고리 4.9.3 |
| 새 지표를 추가하고 싶을 때 | 원칙 2 (진앙 우선) → 어느 Layer 에 둘지 결정 |
| α 정량화를 시도하고 싶을 때 | 7.10.1–7.10.5 |
| Backtest 결과가 본 시스템과 모순될 때 | 7.9 한계 1–4 |

본 카테고리의 사상은 코드가 아니라 *습관* 입니다. 본 시스템을 매일 운영하면서 이 사상을 내재화하는 것이 가장 중요합니다.

## 7.14 카테고리 7에서 의도적으로 추가/배제

| 항목 | 처리 | 사유 |
|---|---|---|
| 향후 코드 구현 5개 영역 | **추가 (7.10)** | TW 향후 확장 의지 반영 |
| Black-Scholes vs Student-t 옵션 가격 | **부분 포함 (7.10.3)** | 자산 연계가 아닌 시나리오 생성 도구로 |
| n^(1/α) 최대값 성장 공식 (Thiel) | **제외** | 투자 의사결정용, 리스크 모니터링 무관 |
| Bull/Bear 양방향 대조 | **카테고리 6 에 분리** | 데이터 검증 영역 |
| Jensen's Inequality 상세 수학 | **요약만 언급** | 본 문서 외부 (TW 9장 워드 문서) |
| Pareto 분포의 derivation | **제외** | 학술 영역 |
| 7개 핵심 원칙 | **추가 (7.8)** | 운영 시 빠른 참조 |
| 향후 코드 우선순위 가이드 | **추가 (7.11)** | 단계적 구현 |

## 7.15 카테고리 7에서 미결로 남긴 사항

1. **α 추정 모듈 (7.10.1) 의 첫 구현 시점** — 본 시스템 안정화 후 언제부터?
2. **Backtester (7.10.4) 의 데이터 요구량** — 1년 vs 2년 vs 3년
3. **7개 핵심 원칙의 운영 매뉴얼** — 어떻게 매일 상기할 것인가
4. **Power Law 사상의 사용자 교육** — 본 문서가 충분한지, 별도 가이드 필요한지
5. **5개 코드 영역의 dashboard 통합 방식** — 별도 위젯 vs TMRS 통합

---

# 부록 A. 전체 카테고리 구조 요약

본 문서에서 다룬 7개 카테고리를 한 페이지로 요약합니다.

```
┌──────────────────────────────────────────────────────────────┐
│  Financial Tracker — Scoring Logic                            │
│  v1.0 (2026-04-08)                                            │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│  Category 1. Core Philosophy & Mental Model                   │
│    └─ 3-Layer Market Structure (Deep → Middle → Surface)      │
│    └─ "Funding breaks first, Credit confirms, Equities react" │
│                                                                │
│  Category 2. Data Sources & Monitoring Universe               │
│    └─ 65 지표 / 3 Layer + Cross-Layer Meta                    │
│    └─ 수동 입력 14 / 자동 fetch 51                             │
│                                                                │
│  Category 3. Indicator Thresholds & Triggers                  │
│    └─ 4-구간 (Normal / Watch / Stress / Crisis)                │
│    └─ Threshold Table v1.2026-04, 5-star confidence           │
│                                                                │
│  Category 4. Risk Scoring Engine — TMRS v2                    │
│    └─ 100점 = L1(45) + L2(30) + L3(15) + Divergence(10)       │
│    └─ Solo Cap + Inverse Turkey Alert (점수 독립)              │
│                                                                │
│  Category 5. Event Risk Score — ERS                           │
│    └─ 100점 = Scheduled(40) + Geopolitical(35) + News(25)     │
│    └─ TMRS↔ERS Divergence 4사분면 (D가 핵심)                   │
│                                                                │
│  Category 6. Quantitative Modeling & Verification             │
│    └─ Anti-Hallucination 5 rules                              │
│    └─ Bull/Bear 양방향 대조 원칙                                │
│                                                                │
│  Category 7. Power Law & Fat-Tail Foundations                 │
│    └─ 7 핵심 원칙 + Conditional α + Inverse Turkey 사상        │
│    └─ 향후 코드 5개 영역 (α 추정 / Conditional / MC / BT / Fit) │
│                                                                │
└──────────────────────────────────────────────────────────────┘
```

---

# 부록 B. 본 문서에서 제외된 항목 (Out of Scope)

본 시스템의 1차 목적은 **시장 시그널 탐지** 입니다. 다음 영역은 본 문서에서 의도적으로 제외되었습니다.

| 제외 영역 | 사유 | 향후 처리 |
|---|---|---|
| **자산 배분 철학** | 시그널 탐지와 직교. 본인/아들 계좌 분리 로직은 별도 문서 | 필요 시 별도 카테고리 신설 |
| **옵션 포지션 관리** | TQQQ Put, VIX 청산 트랜치 등은 포지션 영역 | 별도 Position Book 문서 |
| **시각화 / UI** | 대시보드 렌더링, 차트 구성 등 | 구현 단계에서 별도 결정 |
| **코드 구조 / 디렉토리** | 아키텍처, DB 스키마, API 설계 | 구현 단계에서 결정 |
| **출력 템플릿** | 일일 리포트 포맷, 알림 메시지 문구 | 운영 중 점진 개선 |
| **사용자 계정 / 인증** | 개인 사용 전제 | 필요 시 별도 설계 |

위 영역은 본 Scoring Logic 문서가 확정된 후, *별도 문서* 로 설계합니다. Scoring Logic 이 우선인 이유는 다른 모든 설계가 이 문서의 출력을 인풋으로 받기 때문입니다.

---

# 부록 C. Changelog

| 버전 | 일자 | 변경 내용 |
|---|---|---|
| **v1.0** | 2026-04-08 | 최초 발행. 7개 카테고리 확정 |

**v1.0 주요 결정 사항**:

- 카테고리 재번호 (옵션 B): 1→1, 2→2, 3→3, 4→4, 7→5(ERS), 8→6(Verification), 10→7(Power Law)
- 카테고리 5 (Asset Allocation), 6 (Output/Viz), 9 (Code Structure) 는 제외
- TMRS v2 가중치 최종 확정: 45 / 30 / 15 / 10
- ERS 는 TMRS 와 분리 (옵션 B) — 두 점수 디버전스 측정 가능
- Inverse Turkey 알람은 점수와 독립 작동 (L1+L2 ≥ 0.40 AND L3 ≤ 0.25)
- Threshold Table v1.2026-04 기준 설정
- 카테고리 7 에 향후 코드 구현 5개 영역 추가

---

# 부록 D. 참고 문헌 및 개념 출처

본 문서의 사상적 토대가 된 자료들입니다. (본 문서는 어떤 내용도 *verbatim* 인용하지 않습니다.)

## 사상적 근거

- **Nassim Nicholas Taleb**, *The Black Swan* (2007) — Inverse Turkey 우화, 4사분면 문제
- **Nassim Nicholas Taleb**, *Antifragile* (2012) — Convexity, volatility exposure 사상
- **Benoit Mandelbrot**, *The (Mis)Behavior of Markets* (2004) — Power Law distribution, fractal market hypothesis
- **Peter Thiel**, *Zero to One* (2014) — Power law 투자 철학 (카테고리 7 의 보조 참조)

## 기술적 근거

- **BIS Quarterly Review** — Cross-currency basis swap 해석
- **NY Fed Operations** — Outright Bill Purchase 운영 메커니즘
- **Federal Reserve H.4.1** — Balance sheet 구조 이해
- **BofA ICE HY OAS Methodology** — Credit spread 지표 정의
- **Hill, B.M. (1975)** — "A Simple General Approach to Inference About the Tail of a Distribution" — Hill Estimator 출처 (카테고리 7.10.1)

## 본 시스템 직접 기여 사상

- **TW 6-Indicator Framework** — A2/P2−AA CP, Single-B OAS, VIX, UST 2Y, DXY, HY OAS 를 묶은 daily monitoring set
- **TW 4-Tier Liquidity Framework** — SOFR, RRP, SOMA 계열 지표를 계층적으로 본 모니터링 (본 시스템의 3-Layer 의 prototype)
- **Claude 3-Layer Market Structure** — TW 4-Tier 에서 재구성한 Deep/Middle/Surface 구조
- **Inverse Turkey Alert (본 문서 신규)** — 표면 평온 + 진앙 stress 패턴의 정량화 (L1+L2 vs L3 임계 조건)
- **TMRS ↔ ERS Divergence 4사분면 (본 문서 신규)** — 시장 스트레스와 이벤트 압력의 분리 측정

---

# 부록 E. 용어 전체 색인

본 문서 전체에서 등장하는 주요 용어의 정의와 위치입니다.

| 용어 | 정의 위치 | 1차 사용 카테고리 |
|---|---|---|
| 3-Layer Market Structure | 1.3 | 1, 2, 3, 4 |
| α (Tail Index) | 7.4 | 7 |
| Anti-Hallucination Rules | 6.2 | 6 |
| A2/P2 − AA Spread | 2.4.5, 3.4.5 | 1, 2, 3, 4 |
| Backtester (Inverse Turkey) | 7.10.4 | 7 |
| B/C Ratio (Bid-to-Cover) | 2.4.2, 3.4.1 | 2, 3 |
| Bull/Bear 양방향 대조 | 6.3 | 6 |
| Conditional α | 7.5 | 7 |
| Cross-Currency Basis | 2.4.4, 3.4.4 | 2, 3 |
| Cross-Layer Divergence | 3.7, 4.8 | 3, 4 |
| Decomposition (점수 분해) | 4.12 | 4 |
| Deep Layer | 1.3, 2.4 | 1, 2 |
| ERS (Event Risk Score) | 5 전체 | 5 |
| Escalation Level (0-10) | 5.5.1 | 5 |
| Fat-Tail Simulation | 7.10.3 | 7 |
| Fourth Quadrant | 7.7 | 7 |
| Hill Estimator | 7.10.1 | 7 |
| Inverse Turkey | 1.6.4, 4.11, 7.6 | 1, 4, 7 |
| Layer Max Indicator | 4.9.2 | 4 |
| LLM News Classification | 5.6.2 | 5 |
| Middle Layer | 1.3, 2.5 | 1, 2 |
| MOVE / VIX Ratio | 2.6.2, 3.6.2, 4.8 | 2, 3, 4 |
| Percentile Rank | 3.3, 3.3.2 | 3 |
| Power Law | 7.2, 7.3 | 7 |
| Regime Adjustment | 3.8 | 3 |
| Solo Cap | 4.3, 4.9.3 | 4, 7 |
| Submitted vs Accepted Pattern | 2.4.2, 3.4.2 | 2, 3, 4 |
| Surface Layer | 1.3, 2.6 | 1, 2 |
| Threshold Table Version | 3.8.3, 6.2.5 | 3, 6 |
| TMRS (TW Macro Risk Score) | 4 전체 | 4 |
| TMRS ↔ ERS Divergence | 5.8 | 5 |
| Top Movers | 4.12.2 | 4 |
| Trend Statement (verbal) | 6.2.4 | 6 |

---

# 부록 F. 본 문서 사용 가이드

## F.1 처음 읽을 때

권장 순서는 카테고리 번호 순(1 → 2 → 3 → 4 → 5 → 6 → 7) 입니다. 각 카테고리는 이전 카테고리의 결정을 전제로 합니다.

가장 짧은 순서로 이해하려면:

1. **카테고리 1** (15분) — 사상 이해
2. **카테고리 4 의 4.2–4.3** (10분) — 스코어링 구조
3. **카테고리 4 의 4.11** (5분) — Inverse Turkey
4. **카테고리 5 의 5.8** (5분) — TMRS↔ERS 디버전스
5. **카테고리 7 의 7.8** (5분) — 7 핵심 원칙

이 순서면 40분 안에 시스템의 *뼈대* 를 이해할 수 있습니다. 나머지 세부 사항은 구현 단계에서 참조로 읽으시면 됩니다.

## F.2 구현 단계에서

- 데이터 수집 코드: **카테고리 2**
- 임계값 하드코딩: **카테고리 3**
- 스코어링 엔진 구현: **카테고리 4**
- 이벤트 시스템 구현: **카테고리 5**
- 검증 로직 작성: **카테고리 6**
- 사상적 결정이 필요할 때: **카테고리 7**

## F.3 운영 중 의문 발생 시

| 의문 | 참조 섹션 |
|---|---|
| "왜 Layer 3 가중치가 15 로 낮은가?" | 1.3, 1.6.2, 4.3.1 |
| "왜 점수가 낮은데 알람이 켜졌는가?" | 4.11, 7.6 |
| "왜 같은 임계값인데 다른 점수인가?" | 3.8, 6.2.5 |
| "이 데이터는 어디서 오는가?" | 2.3, 2.4–2.7 |
| "TMRS 와 ERS 가 다르게 움직이는 이유는?" | 5.8 |
| "왜 1차 소스만 써야 하는가?" | 6.2.1, 7.9 |

## F.4 시스템 확장 / 수정 시

모든 수정은 본 문서의 *changelog (부록 C)* 에 반영합니다. 특히 다음 사항은 신중한 검토가 필요합니다.

1. **Threshold Table 변경** → 새 버전 부여, 과거 점수와 비교 시 시각 구분
2. **가중치 변경** → 카테고리 1 사상과 일관성 검토
3. **새 지표 추가** → 어느 Layer 에 배치할지 카테고리 1·2 기준으로 결정
4. **새 카테고리 추가** → 기존 7 카테고리와 중복/충돌 검토

---

# 끝 (End of Document)

**Financial Tracker — Scoring Logic v1.0**

*작성: 2026-04-08 | TW × Claude Opus 4.6*  
*본 문서는 Financial Tracker 앱 내 Scoring Book 대시보드의 logic backbone 입니다.*
