# Financial Tracker — v1.0 대비 구현 현황

> Baseline: `Financial_Tracker_Scoring_Logic_in Total.md` (Threshold Table v1, 2026-04)
> 기준일: 2026-04-14

---

## (1) 구현 완료 ✅

### TMRS 엔진

| 항목 | 상세 |
|------|------|
| **4-레이어 구조** | Layer 1 (45pt) + Layer 2 (30pt) + Layer 3 (15pt) + Divergence (10pt) = 100pt |
| **Layer 1 — Deep/Funding** | SOFR-EFFR 스프레드, CP 스프레드(A2/P2-AA), RRP 잔고, SOFR 텀 프리미엄(FRA-OIS 프록시), Discount Window, TGA 주간변화 → 6개 지표 활성 |
| **Layer 2 — Credit** | HY OAS, A2/P2 CP−EFFR 스프레드 → 2개 지표 활성 |
| **Layer 3 — Surface** | VIX, MOVE Index, CBOE SKEW, MOVE/VIX 비율 → 4개 지표 활성 |
| **Divergence (Cross-Layer)** | Inverse Turkey 감지 (L1+L2 stress & L3 calm), 레이어간 델타 계산 |
| **일일 자동 계산** | APScheduler 08:00 KST 트리거, tmrs_history DB 저장 |
| **TMRS 해석 텍스트** | 5단계 (Calm/Watch/Yellow/Red/Crisis) 자동 생성 |

---

### 데이터 수집 파이프라인

| 지표 | 소스 | 수집 주기 |
|------|------|----------|
| SOFR, EFFR, RRP | NY Fed API | 일 1~2회 |
| SOFR 90일 평균 (SOFR90DAYAVG) | FRED API | 매일 07:05 KST |
| HY OAS (BAMLH0A0HYM2) | FRED API | 매일 |
| A2/P2 CP 30일 금리 | FRED API | 매일 |
| VIX (VIXCLS) | FRED + yfinance ^VIX | 매일 + 실시간 |
| MOVE Index | yfinance ^MOVE | 매일 07:00 KST |
| CBOE SKEW | yfinance ^SKEW | 매일 07:10 KST |
| Discount Window (WLCFLPCL) | FRED API | 주 1회 (금) |
| TGA 잔고 (WTREGEN) | FRED API | 주 1회 (금) |
| Fed Operations (SOMA, Bills, Repo, Sec Lending) | NY Fed API | 일 2회 |
| JPY Spot + 선물환 (1M/3M/3Y/7Y/10Y) | Refinitiv 스크래핑 | 일 4회 + retry |
| 포트폴리오 (주식/옵션) | Playwright 스크래핑 | 15분 |

---

### UI 대시보드 (9탭 중 8탭)

| 탭 | 상태 |
|----|------|
| Signal Desk | 완전 구현 (TMRS 스코어, 레이어 바, 해석 텍스트, 이력) |
| Portfolio | 완전 구현 (실시간 가격, 옵션 IV) |
| Fed Rate | 완전 구현 (SOFR, EFFR, RRP, SOFR 텀 프리미엄) |
| JPY Swap | 완전 구현 (Spot, 선물환, 베이시스) |
| Credit | 부분 구현 (HY OAS, HYG, CP 스프레드) |
| Fed Operation | 완전 구현 (SOMA, Bills, RP/RRP, Discount Window, TGA) |
| Volatility | 완전 구현 (VIX, MOVE, SKEW, MOVE/VIX, 스파크라인) |
| Data History | 기본 구현 (테이블 표시) |

---

### 인프라

- Google OAuth 인증 (ALLOWED_EMAILS 기반 접근 제어)
- KST 기준 로깅
- Telegram 알람 발송 (`telegram_alerts.py`)
- SQLite 영속 저장 (중복 방지 `INSERT OR IGNORE`)
- Gunicorn + APScheduler 프로덕션 배포

---

## (2) 진행 중 / 부분 구현 ⚠️

| 항목 | 현재 상태 | 남은 작업 |
|------|----------|----------|
| **ERS Tier 1 (스케줄 이벤트)** | 스펙만 존재, 코드 없음 | CPI/FOMC D-카운터 + 감쇠(decay) 로직 구현 |
| **CP 스프레드 자동화 (A2/P2−AA)** | 수동 입력 (`aa_manual` 테이블) | FRED DCPN30 vs AA30 자동 계산 |
| **Credit 탭 지표 확충** | HY OAS만 활성 | Korea CDS 5Y, GSIB CDS, HYG ETF daily change 추가 필요 |
| **Layer 2 지표** | 현재 2개 / 스펙 8개 | Single-B OAS, Korea CDS, HYG, CCC OAS 미구현 |
| **Telegram 알람 TMRS 연동** | 기반 코드 존재 | Inverse Turkey 트리거 시 자동 알람 미연결 |

---

## (3) 미착수 ❌

| 항목 | v1.0 스펙 내용 |
|------|--------------|
| **ERS 전체 (Tier 2, 3)** | Tier 2: 지정학 escalation 레벨 수동 입력 UI + 점수화 / Tier 3: 뉴스 키워드 매칭 + Anthropic API 분류 |
| **TMRS-ERS 다이버전스 매트릭스** | 4분면 시각화 (TMRS↑/ERS↓, TMRS↓/ERS↑ 등) 및 해석 |
| **ERS 탭 UI** | 현재 placeholder만 존재 |
| **DXY 레이어 통합** | Layer 3 지표 (Weight 3), 현재 TMRS 계산에 미반영 |
| **Power Law / Fat-Tail 분석** | α parameter 추정, Conditional VaR, Monte Carlo 시뮬레이터 |
| **Regime Adjustment** | 분기별 percentile rebasing, 임계값 동적 조정 |
| **Korea CDS 5Y** | Layer 2 지표 (Weight 4), 데이터 소스 확보 미완 |
| **CFTC COT (레버리지 펀드 포지션)** | Positioning 지표로 스펙 언급, 미수집 |
| **멀티 어카운트 분리** | TW 본인 계좌 (중기+옵션) vs. 자녀 계좌 (15~20년 바이앤홀드) 분리 로직 |
| **Bull/Bear 시나리오 생성** | 듀얼 케이스 분석, 포워드 쇼크 시나리오 |

---

## (4) v1.0과 다르게 결정한 사항 🔄

| # | 항목 | v1.0 스펙 | 실제 결정 | 이유 |
|---|------|-----------|----------|------|
| 1 | **SOFR-EFFR 스프레드 방향성** | 절대값 기준 티어 (스프레드 클수록 위험) | 방향성 티어 (SOFR < EFFR = normal, SOFR > EFFR = stress) | SOFR < EFFR가 구조적 정상 상태. 절대값 로직은 정상 구간을 위험으로 잘못 분류 |
| 2 | **MOVE Index 임계값** | <90 / 90-110 / 110-130 / 130+ | <80 / 80-100 / 100-150 / 150+ | 2025년 이후 금리 변동성 상승으로 기준선 하향 조정; 80 이하가 실질적 안정 구간 |
| 3 | **Korea CDS 5Y 구현** | Layer 2 필수 지표 (Weight 4) | 1차 릴리즈에서 제외 | 실시간 공개 API 없음 (Bloomberg/Refinitiv 유료 전용). 추후 수동 입력 방식 검토 |
| 4 | **FRA-OIS 프록시** | 직접 FRA-OIS 스프레드 수집 | SOFR90DAYAVG − SOFR로 대체 | IBA/CME FRA 데이터 공개 API 없음. FRED SOFR90DAYAVG가 텀 프리미엄의 실용적 근사치 |
| 5 | **VIX 소스** | VX=F 선물 (Forward VIX) 우선 | ^VIX 현물 yfinance 실시간 + FRED 폴백 | yfinance에서 VX=F 지원 중단. ^VIX 단일 소스 구조로 변경 |
| 6 | **RRP 임계값** | <$1T normal / $1-1.5T watch | <$100B normal / <$50B watch / <$10B stress | QT 진행으로 구조적 RRP 소진 완료. 2025년 이후 $100B 이하가 새로운 정상 구간 |

---

## 전체 완성도 요약

| 카테고리 | 완성도 |
|---------|--------|
| TMRS 엔진 코어 | ✅ ~95% |
| 데이터 수집 파이프라인 | ✅ ~80% (Layer 1/3 완성, Layer 2 보강 필요) |
| UI 대시보드 | ✅ ~85% (ERS 탭 제외) |
| ERS 엔진 전체 | ❌ ~5% (스펙만 완성) |
| 고급 분석 (Power Law 등) | ❌ 0% |
