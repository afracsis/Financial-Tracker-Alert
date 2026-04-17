# Financial Market Tracker — 전체 소스 코드

## 프로젝트 개요
한국어 금융 시장 대시보드 (Flask + SQLite + Gunicorn)
배포 URL: https://financial-tracker-alert.replit.app

## 파일 구조
```
dashboard/
├── app.py                  # 메인 Flask 앱 (2,038줄)
│                           # - DB 초기화(init_db)
│                           # - FRED / NY Fed / MOVE / JPY / Portfolio 수집
│                           # - API 라우트 (/data, /nyfed, /fedop, /volatility ...)
│                           # - 스케줄러(APScheduler)
│
├── auth.py                 # Google OAuth 인증 (181줄)
│                           # - Flask-Login + authlib
│                           # - 화이트리스트(ALLOWED_EMAILS)
│                           # - 세션 30일 유지
│
├── telegram_alerts.py      # 텔레그램 알람 엔진 (268줄)
│                           # - 지표별 임계치(Threshold) 기반
│                           # - 1시간 쿨다운
│                           # - check_and_alert() / record_success() / record_error()
│
├── portfolio_scraper.py    # 종합 시장 스크래퍼 (884줄)
│                           # - yfinance: 에너지/원자재/금리/주식/FX/크립토
│                           # - FRED API: US 2Y T-Note (DGS2)
│                           # - Playwright: Japan 10Y/30Y JGB, Korea CDS
│
├── jpy_scraper.py          # JPY 포워드 레이트 스크래퍼 (189줄)
│                           # - Playwright: Investing.com
│                           # - 1M / 3M / 3Y / 7Y / 10Y
│
├── gunicorn.conf.py        # Gunicorn 설정 (30줄)
│                           # - port 18955, gthread worker
│                           # - on_starting() → _startup() 호출
│
└── templates/
    ├── index.html          # 메인 대시보드 UI (2,333줄)
    │                       # - 7탭: Portfolio / Fed Rate / JPY Swap /
    │                       #        Credit / Fed Operation / Volatility /
    │                       #        Data History (+ Admin)
    │                       # - Plotly.js 차트
    │                       # - 스파크라인 (Volatility 탭)
    │
    └── login.html          # 로그인 페이지 (173줄)
                            # - Google OAuth 버튼
                            # - SIGNALS 브랜딩
```

## 주요 데이터 소스
| 지표 | 출처 |
|---|---|
| EFFR / SOFR | NY Fed API |
| RRP (역레포) | NY Fed API (rp/reverserepo/propositions) |
| MOVE Index | Yahoo Finance (^MOVE) |
| HY OAS | FRED (BAMLH0A0HYM2) |
| CP Rate 30D | FRED (RIFSPPNA2P2D30NB) |
| Fed SOMA / AMBS / SecLending / TSY | NY Fed API |
| JPY Swap 1M/3M/3Y/7Y/10Y | Investing.com (Playwright) |
| Japan 10Y/30Y JGB | Investing.com (Playwright) |
| Korea CDS 5Y | WorldGovernmentBonds (Playwright) |
| VIX, S&P500, WTI, Gold 등 | Yahoo Finance (yfinance) |
| US 2Y T-Note | FRED (DGS2) |

## DB 테이블 목록 (SQLite: data.db)
- hy_index, cp_30d
- nyfed_effr, nyfed_sofr, nyfed_rrp
- fedop_soma, fedop_ambs, fedop_seclending, fedop_tsy
- fedop_rrp, fedop_rp
- move_index
- jpy_swap_data
- portfolio_data
- users

## 알람 임계치 (telegram_alerts.py)
- HY OAS: ±3% | CP Rate: ±3%
- MOVE Index: ±5%
- VIX: ±10% | Korea CDS: ±10%
- EFFR/SOFR: ±2%
- 주가지수: ±2% | 에너지/원자재: ±4~5%

## 환경 변수 (Replit Secrets)
- FRED_API_KEY
- GOOGLE_CLIENT_ID
- GOOGLE_CLIENT_SECRET
- SESSION_SECRET
- TELEGRAM_BOT_TOKEN (선택)
- TELEGRAM_CHAT_ID (선택)
- ADMIN_EMAILS
