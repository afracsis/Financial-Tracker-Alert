# TW Financial App — Reference Document

> **목적**: TW님의 매크로/리스크/자산배분 의사결정 프레임워크를 코드로 구현하기 위한
> 단일 참고문서. Replit, Claude Code, Cursor 등 AI 코딩 도구에 컨텍스트로 주입할 수
> 있도록 정리되어 있습니다. 모든 수치·임계값·로직은 TW님과의 누적 대화에서 도출된
> "TW 고유 프레임워크" 기준입니다.
>
> **마지막 업데이트**: 2026-04-08
> **대상 사용자**: 단일 사용자 (TW님 본인 + 아들 계좌)
> **운용 시계**: 본인 계좌(중기+옵션 레이어), 아들 계좌(15-20년 장기 바이앤홀드)

---

## 0. 문서 사용 가이드 (for AI coding assistants)

이 문서는 다음 5개 모듈로 구성됩니다. 코드 작성 시 각 섹션을 별도 모듈로 분리하면
유지보수가 쉬워집니다.

1. **Fed & Liquidity Data Layer** — 데이터 수집 대상과 소스
2. **Market Data Layer** — 가격·변동성·금리·FX·크레딧
3. **Risk Scoring Engine (TMRS)** — TW Macro Risk Score 산출 로직
4. **Portfolio & Asset Allocation Logic** — 두 계좌의 운용 원칙
5. **Event Response Playbook** — 트리거 기반 의사결정 규칙

각 섹션은 **데이터 → 임계값 → 해석 → 액션** 순서로 통일했습니다.

---

## 1. Fed & Liquidity Data Layer

### 1.1 데이터 소스

| 카테고리 | 데이터 | 소스 | 갱신 주기 |
|---|---|---|---|
| Fed Balance Sheet | H.4.1 (Reserve Bank Credit, SOMA, RRP, TGA, Reserve Balances) | federalreserve.gov/releases/h41 | 주간 (목) |
| Fed 운영 | T-Bill Outright Purchase, Securities Lending, FX Swap | NY Fed Operations Page | 일별 |
| 단기금리 | SOFR, EFFR | NY Fed | 일별 |
| CP 금리 | AA 30D Nonfin, A2/P2 30D Nonfin | federalreserve.gov/releases/cp/rates.htm | 일별 (정적 페이지 캡처 필요) |
| Primary Credit | Discount Window borrowing | H.4.1 | 주간 |

### 1.2 핵심 H.4.1 항목과 해석 규칙

```
Reserve Bank Credit          → Fed 자산 총량. 주간 변화 = QT 속도 프록시
Securities Held Outright     → SOMA. 주간 +/- 가 핵심 (T-Bill 별도 추적)
  ├─ US Treasury Bills       → 최근 Fed가 공급 강화 시 +10~+15B/주
  ├─ Notes & Bonds           → QT로 자연 감소
  └─ MBS                     → No new operations 기조 유지
Reserve Balances             → 은행 지준금. 풍부해도 SOFR↑면 "분배 불균형"
RRP                          → 단기 유동성 흡수 풀
TGA                          → 정부 현금 잔고. 감소=재정 지출, 증가=시장 흡수
Currency in Circulation      → 추세선
```

### 1.3 핵심 해석 로직

- **Reserve Balances ↑ + SOFR ↑ 동시 발생** → "물은 있는데 파이프가 막힘" =
  은행 LCR 규제로 지준금이 묶여 비은행/딜러로 전이 안 됨. 주의 신호.
- **SOMA T-Bill 주간 +$10B 이상** → Fed의 단기 유동성 적극 공급 모드
- **TGA 주간 -$30B 이상 급감** → 정부 지출 가속 = 시장 유동성 +
- **RRP 참가기관 수 급증 (>10)** → 단기 자금시장 패닉 조짐, 수일 내 정상화 여부 추적
- **Outright Bill Purchase 제출/낙찰 비율(B/C)** → 8x 이상이면 딜러 balance sheet
  스트레스 신호 (수요 폭증)

### 1.4 코드 구현 시 주의

- federalreserve.gov CP rate 페이지는 동적 렌더링되어 단순 스크래핑 어려움.
  TW님이 수동 캡처 → OCR 또는 수기 입력 워크플로 필요.
- H.4.1은 매주 목요일 16:30 ET 발표. 한국 시각 금요일 새벽 데이터 반영.

---

## 2. Market Data Layer

### 2.1 일일 모니터링 데이터셋

| 카테고리 | 지표 | 소스 (예시) | 비고 |
|---|---|---|---|
| Equity Vol | VIX | yfinance ^VIX | 일일 |
| Rates Vol | MOVE Index | TVC:MOVE / yfinance ^MOVE | 채권 변동성 leading |
| FX | DXY | yfinance DX-Y.NYB | 임계 100 |
| FX Funding | USD/JPY 1M, 3M Forward Basis | Bloomberg/Refinitiv (수동 입력) | 캐리 청산 leading |
| Credit | HY OAS (BAMLH0A0HYM2), Single-B OAS | FRED | 후행, 임계 350bp |
| Credit ETF | HYG | yfinance | HY OAS 일중 프록시 |
| Rates | UST 2Y, 10Y, 30Y | FRED / yfinance | 곡선 모니터 |
| Korea Risk | Korea CDS 5Y | Bloomberg/수동 | EM 리스크 프록시 |
| Energy | WTI, Brent | yfinance CL=F, BZ=F | 호르무즈 시나리오 핵심 |
| Gold | Gold Spot | yfinance GC=F | 인플레/지정학 |
| Crypto | BTC | yfinance BTC-USD | 주말 유일 유동자산 → "카나리아" |

### 2.2 보조 leading 지표 (Power Law 보강 셋업)

TW님이 자체 개발한 leading 지표 묶음. 후행 지표(HY OAS 등)가 깨지기 전에 먼저
움직이는 변수들입니다.

1. **JPY/USD 1M, 3M Cross-Currency Basis Swap** — 캐리 청산 신호
2. **MOVE Index** + **MOVE/VIX 비율** — 비율 4 이상이면 채권發 위기 가능성
3. **Fed Primary Credit / Discount Window** — 은행 직접차입 = 강한 스트레스
4. **CBOE SKEW Index** — OTM Put 프리미엄 = 테일 리스크 가격
5. **CFTC COT Leveraged Funds Net E-mini Position** — 헤지펀드 포지셔닝
6. **GSIB CDS Spreads** (JPM, BAC, C, GS, MS) — 시스템 리스크 프록시

### 2.3 USD/JPY Forward Basis 해석 규칙

```
Short End (1M, 3M) — 캐리 청산 신호 구간
  • 이론값(금리차 + 베이시스) 부근 = 정상
  • 1M이 -10bp 이상 악화 → 단기 USD funding stress 진입
  • 3M이 이론값 대비 +20bp 악화 → carry unwind 압력

Long End (1Y~10Y) — 구조적 USD shortage 구간
  • 7Y, 10Y의 절대값이 지속 악화 → 구조적 달러 부족
  • 분기말 효과(3월말, 9월말)는 일시적 노이즈로 분리
```

### 2.4 핵심 원칙

- **Forward rate는 금리차 + cross-currency basis로 결정됨** (carry unwind 신호 아님)
- 진짜 carry unwind 신호는 **1M basis swap, FRA-OIS spread, MOVE Index**에서 옴
- 외부 분석이 forward rate 자체로 carry trade를 논하면 의심할 것

---

## 3. Risk Scoring Engine — TMRS (TW Macro Risk Score)

### 3.1 설계 철학

기존 시중 risk scoreboard의 결함:

1. 가중치 불투명, 이중 계산 의심
2. HY OAS 등 핵심 후행 지표 가중치 과소
3. **이벤트 리스크(CPI, FOMC, 지정학 데드라인) 미반영**
4. **개인 포지션과의 연계 부재**
5. Liquidity 항목에서 RRP 감소만 보고 SOMA 매입 동시 진행을 무시 → 모순

TMRS는 이를 해결하기 위해 **4-Layer 구조**로 설계되었습니다.

### 3.2 4-Layer 구조

| Layer | 명칭 | 가중 | 성격 |
|---|---|---|---|
| Layer 1 | Core 6-Indicator (후행) | 40 | 시장 현재 상태 |
| Layer 2 | Power Law Leading | 30 | 시장 선행 신호 |
| Layer 3 | Event Risk | 20 | 캘린더/지정학 |
| Layer 4 | Position Trigger | 10 | TW님 포지션 P&L 직결 |
| **합계** | | **100** | |

### 3.3 Layer 1 — Core 6-Indicator (40점)

| # | 지표 | 임계치 | 가중 | 산식 |
|---|---|---|---|---|
| ① | HY OAS Single-B | 350 bp | 8 | (현재값 / 350) × 8, 1.0 cap |
| ② | HYG ETF | 일간 -1% 이상 하락 | 5 | -1%당 1점 추가 |
| ③ | VIX | 25 / 33 / 45 | 8 | <25=0, 25-33=4, 33-45=6, 45+=8 |
| ④ | US 2Y Yield | 일간 ±5bp 이상 변동 | 4 | 변동성 기반 |
| ⑤ | DXY | 100 | 7 | <100=0, 100-103=4, 103+=7 |
| ⑥ | A2/P2 − AA 30D CP | +50 bp | 8 | (스프레드 / 50) × 8, 1.0 cap |

**중요**: ⑥ A2/P2 - AA 스프레드는 6-Indicator 중 가장 마지막에 깨질 지표.
이것이 +50bp를 넘으면 자금시장 본격 스트레스 진입.

### 3.4 Layer 2 — Power Law Leading (30점)

| 지표 | 가중 | 산식 |
|---|---|---|
| MOVE Index | 6 | <90=0, 90-110=3, 110+=6 |
| MOVE/VIX 비율 | 4 | <4=0, 4-5=2, 5+=4 |
| JPY 1M Basis | 6 | 이론값 부근=0, -10bp 악화=3, -20bp+=6 |
| Fed Primary Credit (Discount Window) | 5 | 0=0, >0=5 (즉시 임계) |
| CBOE SKEW | 4 | <140=0, 140-150=2, 150+=4 |
| Korea CDS 5Y | 5 | 일간 +5% 이상 변동 시 5 |

### 3.5 Layer 3 — Event Risk (20점)

캘린더/지정학 D-counter 기반. 자동 계산 가능 영역.

| 이벤트 | 가중 | D-counter 산식 |
|---|---|---|
| 지정학 데드라인 (예: 호르무즈) | 8 | D-1=8, D-3=5, D-7=3, 그 외=1 |
| 협상 진행 단계 | 4 | 결렬=4, 교착=3, 진전=2, 합의 임박=1 |
| CPI/PPI 발표 | 4 | D-1=4, D-3=3, D-7=1 |
| FOMC | 2 | D-1=2, D-7=1 |
| Fed 인사 발언 24h 이내 | 2 | 있음=2, 없음=0 |

### 3.6 Layer 4 — Position Trigger (10점, TW님 전용)

| 지표 | 가중 | 산식 |
|---|---|---|
| TQQQ vs Roll-over Trigger ($43) | 4 | $43 이상=4 (롤오버 압박) |
| VIX vs GTC 1차 ($33) | 3 | (VIX/33), 1.0 cap |
| WTI 절대 수준 | 2 | $100+=2, $90+=1 |
| TQQQ 60일 IV | 1 | 80%+=1 |

### 3.7 점수 해석 구간

| 점수 | 등급 | 행동 가이드 |
|---|---|---|
| 0–25 | 🟢 Calm | 평상 운용 |
| 26–40 | 🟡 Watch | 모니터링 강화 |
| 41–55 | 🟠 Yellow Alert | 헤지 조정 검토, GTC 점검 |
| 56–70 | 🔴 Red Alert | 1차 청산 준비, 포지션 축소 |
| 71–85 | 🚨 Crisis | GTC 강제 발동, 위험회피 모드 |
| 86–100 | ☠️ Tail Event | Black Swan 시나리오, 최대 수익실현 |

### 3.8 가장 중요한 시그널: Layer 간 디버전스

TMRS의 진짜 가치는 **절대 점수가 아니라 Layer 1·2 vs Layer 3·4 간의 갭**입니다.

```
Layer 1 (후행): 낮음    ┐
Layer 2 (선행): 낮음    ├─ 시장은 평온
Layer 3 (이벤트): 높음  ┐
Layer 4 (포지션): 높음  ├─ 이벤트·포지션은 임박
```

이 패턴 = **Taleb의 Inverse Turkey 시나리오**. 모든 것이 평온해 보이는 1,000일째에
도살자가 옴. 점수가 같은 43이어도 (Layer 분포)에 따라 의미가 완전히 달라집니다.

### 3.9 코드 구현 가이드

- 각 지표를 클래스/dict로 분리: `{name, value, threshold, weight, score_fn}`
- Layer별 합산 → 가중 정규화 → 100점 환산
- 디버전스 알람: `abs((L1+L2) - (L3+L4)) > 25` 시 Yellow flag
- 일일 시계열 누적 (CSV 또는 SQLite)
- 변화 주도자 분해(decomposition): 전일 대비 점수 변화의 어느 Layer가 기여했는지

---

## 4. Portfolio & Asset Allocation Logic

### 4.1 두 계좌의 분리 운용 원칙

| 계좌 | 시계 | 성격 | 리스크 허용 |
|---|---|---|---|
| 본인 계좌 | 중기 + 옵션 레이어 | 매크로 베팅, 헤지 | 중–고 |
| 아들 계좌 | 15–20년 장기 바이앤홀드 | 인플레 방어 + 복리 | 저–중 |

**핵심 원칙**: 두 계좌는 **물리적으로뿐만 아니라 의사결정 로직도 분리**한다.
본인 계좌의 단기 신호로 아들 계좌를 흔들지 않는다.

### 4.2 본인 계좌 구성 원칙

```
방어 베이스 (60-70%):  IAU (금 ETF) — 인플레 / 안전자산 / 구조적 상승
고베타 노출 (15-30%):  팔란티어, 테슬라 등 — 변동성 베팅
달러 현금 (가변):       옵션 실탄 (트리거 발생 시 진입)
옵션 레이어 (분리):     TQQQ Put 등 — 핵심 하방 베팅
```

**포지셔닝 철학**:
- 본업 포트폴리오는 보수적(금 중심), 옵션은 별도 레이어로 공격적
- 옵션 자금 = 총 투자금의 5–10% 이내
- 1회 베팅 = 옵션 자금의 20–25% (4–5회 기회 확보, 절대 올인 금지)
- 옵션은 1개월 → 2–3개월(또는 6개월) 만기 선호 (Theta decay 완화)

### 4.3 아들 계좌 구성 원칙

```
실물자산:    실물금 + KRX 금현물 ETF 약 40%
에너지:      엑손모빌 + 셰니어에너지 약 40%
한국 대표:   삼성전자 (보통+우선) 약 20%
글로벌 빅테크: 알파벳A (별도 비중)
```

**핵심 원칙**:
- "장기 시계열에서 인플레이션에 대항 가능한 최적 상품" = 금 + 에너지 메이저
- 투기성 자산 금지, 배당주 + 실물자산 중심
- **현금 보유보다 즉시 재투자가 원칙** — "지금보다 10% 싸게 살 타이밍"을 기다리다
  1–2년 놓치는 비용이 더 큼
- 연간 정기 적립 + 이벤트 리밸런싱

### 4.4 옵션 매매 결정 원칙 (본인 계좌)

| 원칙 | 내용 |
|---|---|
| 만기 | 3–6개월 선호. 1개월 옵션은 시간가치 소멸로 비추천 |
| 진입 타이밍 | 즉시 진입 ❌, **트리거 대기** ✅ (VIX 급등, 협상 결렬, 데드라인 D-day 등) |
| 사이즈 | 옵션 자금 = 총 자산의 5–10%, 1회 = 옵션 자금의 20–25% |
| 청산 규칙 | GTC 단계적 청산 (트랜치 분할) — 예: 3계약 / 3계약 / 1계약 |
| 롤오버 트리거 | 기초자산이 행사가 위로 일정 폭 돌파 + 시간 1/3 경과 |
| 절대 금지 | 올인 베팅, 1개월 옵션 다량 매수, 무계획 추격 매수 |

### 4.5 현재 활성 포지션 (참고용)

```
TQQQ Put
  만기: 6/18
  행사가: $40
  계약수: 7
  평균 진입 프리미엄: ~$3.50
  GTC 청산 트랜치:
    1차: $14 (3계약) — VIX 33-37 타겟
    2차: $19 (3계약) — VIX 38-45 타겟
    3차: $28 (1계약) — VIX 50+ 타겟
  롤오버 트리거: 4/10 CPI 이후 TQQQ > $43 → 9월물 검토
```

### 4.6 SQQQ 등 레버리지 인버스 ETF 사용 원칙

- **장기 보유 절대 금지**: 일일 -3배 추종 → 변동성 손실(decay)로 횡보장에서도 가치 녹음
- 적립식과는 본질적으로 맞지 않음
- 단기(수일~수주) 헤지 도구로만 사용
- 장기 헤지는 풋옵션(QQQ Put 3–6개월) 또는 현금 비중으로 대체

---

## 5. Event Response Playbook

### 5.1 이벤트 타입 분류

| 타입 | 예시 | 대응 시계 |
|---|---|---|
| 캘린더 이벤트 | CPI/PPI, FOMC, 고용지표, 어닝 | 사전 D-counter, 사후 즉시 반응 |
| 지정학 이벤트 | 호르무즈 데드라인, 무력 충돌, 협상 결렬 | 24h 이내 |
| 시장 트리거 | VIX 급등, HY OAS 임계 돌파, DXY 100 돌파 | 즉시 |
| Fed 이벤트 | 긴급 금리 결정, 발언, 운영 변경 | 즉시 |

### 5.2 트리거 → 액션 매트릭스 (본인 계좌 옵션 레이어)

| 트리거 | 시나리오 | 액션 |
|---|---|---|
| VIX 33–37 진입 | 패닉 1단계 | TQQQ Put 1차 트랜치 청산 ($14) |
| VIX 38–45 진입 | 패닉 2단계 | 2차 트랜치 청산 ($19) |
| VIX 50+ | Crisis | 3차 트랜치 청산 ($28) |
| TQQQ > $43 (CPI 후) | 상승 시나리오 | 9월물 롤오버 검토 |
| WTI > $120 + 호르무즈 봉쇄 | 에너지 슈퍼사이클 | 아들 계좌 에너지 비중 점검 |
| 휴전·협상 타결 뉴스 | 리스크온 | TQQQ 콜 단기 베팅 (소액) |
| Fed 긴급 금리인하 | 유동성 공급 | TQQQ 콜 (단, 2–3개월 만기) |

### 5.3 호르무즈 시나리오 분기 (예시)

```
협상 타결 → TQQQ $46+
  → 9월물 롤오버 즉시 실행
  → 에너지 포지션 일부 익절 검토

협상 결렬·무대응 → TQQQ $43~45 횡보
  → CPI 결과 대기
  → 6월물 holding

협상 결렬·타격 실행 → TQQQ $38~40
  → 6월물 holding
  → GTC 1차 트랜치 자동 작동 대기
  → 에너지 포지션 유지
```

### 5.4 이벤트 사전 준비 체크리스트

CPI/FOMC 같은 큰 이벤트 D-1에 자동 점검할 항목:

1. TMRS 점수와 Layer 분해 출력
2. 보유 옵션 포지션의 현재 가치 + Greek (델타, 감마, 베가)
3. GTC 주문 활성화 여부
4. 달러 현금 잔고
5. 핵심 임계값 근접도 (VIX, DXY, HY OAS)
6. 직전 동일 이벤트의 시장 반응 패턴 (1년 내)

### 5.5 사후 대응 워크플로

이벤트 발생 후 30분 이내:

1. 데이터 수집 (가격, 변동성, 금리, FX 동시 캡처)
2. TMRS 재계산 (전후 비교)
3. 어느 Layer가 가장 크게 움직였는지 분해
4. 사전 트리거 매트릭스와 매칭
5. 액션 필요 시 실행, 불필요 시 holding 사유 기록
6. 일일 로그에 의사결정 기록

---

## 6. 데이터 검증 원칙 (Anti-Hallucination)

코드 작성 시 AI 모델(Claude 포함)이 매크로 데이터를 잘못 계산하는 사례가
누적되었습니다. 다음 검증 단계를 코드에 내장하시기를 권장합니다.

1. **모든 외부 데이터는 1차 소스 우선** (FRED, NY Fed, federalreserve.gov)
2. **AI가 제시한 IV/Black-Scholes 값은 실제 시장가와 cross-check** 후 사용
3. **USD/JPY Forward는 금리차 + cross-currency basis로 결정**됨을 코드 주석에 명시
4. **Fed CP 페이지처럼 동적 렌더링되는 데이터는 수동 입력 필드 보장**
5. **금가격 등 단방향 추세 주장은 직전 5일 데이터로 자동 반증**

---

## 7. 부록: TW님 자체 개발 프레임워크 요약

### 7.1 4-Tier Liquidity Framework (원본)

```
Tier 1 (단기 자금): SOFR, RRP, Fed Repo, EFFR, SOMA
Tier 2 (크레딧):   HYG, Korea CDS 5Y, HY OAS
Tier 3 (금리):     UST 2Y/10Y/30Y, 딜러 포지셔닝
Tier 4 (글로벌):   DXY, USD/KRW, USD/JPY, VIX, WTI, Gold
```

이것이 발전하여 현재의 6-Indicator + Power Law Leading 셋업이 됨.

### 7.2 Power Law / Taleb 프레임워크 핵심 개념

- **Pareto vs Gaussian**: 시장은 정규분포가 아닌 거듭제곱 분포 (fat tail)
- **α 파라미터**: 낮을수록 꼬리가 두꺼움
- **현대 금융시장에서 α를 낮추는 요인**: 알고리즘 동조화, 레버리지 확대, 유동성 비선형성
- **조건부 α(conditional alpha)**: 평상시와 스트레스 시의 α가 완전히 다름
- **Taleb의 4사분면**: fat tail + complex payoff = 통계 모형 구조적 실패
- **Inverse Turkey**: 모든 지표가 평온할 때가 가장 위험한 순간
- **Convex Payoff**: 손실 한정 + 극단 이득 노출 = 옵션 매수의 본질
- **Jensen's Inequality**: 볼록함수의 기대값 > 기대값의 함수 → 변동성 자체가 자산

### 7.3 의사결정 시 항상 자문할 질문

1. 이 신호가 후행 지표인가, 선행 지표인가?
2. 시장이 이 리스크를 이미 가격에 반영했는가?
3. 같은 신호가 여러 카테고리에서 동시에 나오는가? (디버전스 vs 동조)
4. 내 포지션의 P&L에 직접 영향이 있는가, 간접인가?
5. 이 결정은 본인 계좌 로직인가, 아들 계좌 로직인가? (절대 섞지 않기)

---

## 8. 향후 코드 구현 시 권장 모듈 구조

```
financial_app/
├── data/
│   ├── fed_h41.py         # H.4.1 파싱·캐싱
│   ├── fred_client.py     # FRED API 래퍼
│   ├── market_data.py     # yfinance 등 가격 데이터
│   ├── manual_inputs.py   # CP 금리 등 수동 입력
│   └── cache/             # SQLite 또는 Parquet
├── scoring/
│   ├── tmrs_engine.py     # 4-Layer 점수 산출
│   ├── layer1_core.py
│   ├── layer2_leading.py
│   ├── layer3_event.py
│   ├── layer4_position.py
│   └── decomposition.py   # 일일 변화 분해
├── portfolio/
│   ├── accounts.py        # 본인 / 아들 계좌 분리
│   ├── option_layer.py    # GTC, 트랜치, 롤오버 로직
│   └── allocation.py
├── events/
│   ├── calendar.py        # CPI, FOMC, 지정학 D-counter
│   ├── triggers.py        # 트리거 매트릭스
│   └── playbook.py        # 사전·사후 워크플로
├── reports/
│   ├── daily_report.py    # 일일 markdown 리포트
│   └── alerts.py          # 임계값 알람
└── tests/
    └── test_anti_hallucination.py  # 데이터 검증
```

---

## 9. 변경 이력

- 2026-04-08: 초판 작성. Fed Data, Market Data, TMRS, Portfolio, Event Response 5개 모듈 정리.

---

*이 문서는 TW님과 Claude 간의 누적 대화에서 도출된 프레임워크를 정리한 것이며,
특정 시점의 시장 상황(2026년 3–4월 호르무즈 시나리오)을 사례로 다수 포함합니다.
시장 환경이 바뀌면 임계값과 시나리오는 조정이 필요합니다.*
