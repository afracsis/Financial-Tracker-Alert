# 금융 지표 대시보드 (Financial Indicator Dashboard)

## Overview

pnpm workspace monorepo using TypeScript + Python Flask. The main deliverable is a Korean-language financial dashboard tracking HY OA Index (BAMLH0A0HYM2) and A2/P2 비금융 CP 금리 30일 (RIFSPPNA2P2D30NB) from FRED.

## Stack

- **Monorepo tool**: pnpm workspaces
- **Node.js version**: 24
- **Package manager**: pnpm
- **TypeScript version**: 5.9
- **API framework**: Express 5 (api-server)
- **Database**: PostgreSQL + Drizzle ORM (api-server), SQLite (flask dashboard)
- **Validation**: Zod (`zod/v4`), `drizzle-zod`
- **API codegen**: Orval (from OpenAPI spec)
- **Build**: esbuild (CJS bundle)

## Artifacts

### financial-dashboard (Flask, Python)
- **Location**: `dashboard/` (runs from workspace root)
- **URL**: `/` (preview path)
- **Port**: 18955
- **Workflow**: `artifacts/financial-dashboard: web`
- **Command**: `python /home/runner/workspace/dashboard/app.py`
- **Database**: `dashboard/data.db` (SQLite)
- **Data sources** (INDICATORS dict in `dashboard/app.py`):
  - `BAMLH0A0HYM2` → table `hy_index` (HY OA Index, 989+ rows)
  - `RIFSPPNA2P2D30NB` → table `cp_30d` (A2/P2 비금융 CP 금리 30일, 953+ rows)
- **Schedule**: 매일 07:00 & 22:00 KST via APScheduler CronTrigger (per-indicator, configurable)

### 6-Tab UI (Portfolio가 첫 번째 기본 탭)
- **Portfolio** (기본탭): 종합 시장 상황판 — yfinance(에너지/원자재/금리/KOSPI200/S&P500/Dow Jones/Nasdaq/주식/FX/크립토) + Playwright(Japan 10Y/30Y JGB, Korea CDS 5Y) · 1분 캐시 · 상승빨강/하락파랑 · ▲▼ 아이콘 · 2% 이상 대변동 ◆ 배지 · 데이터 없음 시 노란 "Source Check" 표시
- **Fed Rate**: EFFR / SOFR / SOFR-EFFR 스프레드 카드 + 4선 Plotly 차트 (Target Range 음영)
- **JPY Swap**: USD/JPY 포워드 레이트 5개 기간 (1M/3M/3Y/7Y/10Y) 테이블 (Playwright 스크래핑) + Spot Rate 표시 + 연율화 비용(%) 컬럼 + ▲▼ Change 아이콘 + 하단 Japan 30Y JGB 참조 패널
- **Credit**: HY OA Index + A2/P2 CP금리 카드 + 60일 Plotly 이중축 차트
- **Fed Operation**: SOMA 주간변화 / AMBS / SecLending / TSY Outright 카드 + SOMA 주간 변화 막대 그래프 + 일별 오퍼레이션 스택 바 차트 (낙찰비율 배지 포함)
- **Data History**: 아코디언 방식 전체 이력 테이블

### NY Fed API Endpoints
- EFFR/SOFR: `rates/unsecured/effr/last/N.json`, `rates/secured/sofr/last/N.json`
- RRP: `rp/reverserepo/propositions/search.json?startDate=...&endDate=...`
- SOMA: `soma/summary.json` (전체 주간 이력)
- AMBS: `ambs/all/results/details/last/30.json` → `ambs.auctions[]`
- SecLending: `seclending/all/results/details/last/30.json` → `seclending.operations[]`
- TSY Outright: `tsy/all/results/details/last/30.json` → `treasury.auctions[]`

### Flask Routes
- `/data` — FRED 지표 최신 카드 데이터
- `/records` — 전체 이력
- `/history` — 60일 차트용
- `/nyfed` — EFFR/SOFR/RRP/Spread 요약
- `/nyfed/history` — EFFR/SOFR 90일 이력
- `/fedop` — SOMA변화/AMBS/SecLending/TSY 요약
- `/fedop/history` — SOMA 주간 이력 + 일별 오퍼레이션 이력
- `/jpy` — USD/JPY 포워드 레이트 최신 5개 기간 데이터 + 상태
- `/jpy/history` — 1M & 3M 24시간 이력

### SQLite Tables
- `hy_index`, `cp_30d` — FRED 지표
- `nyfed_effr`, `nyfed_sofr`, `nyfed_rrp` — NY Fed 기준금리
- `fedop_soma`, `fedop_ambs`, `fedop_seclending`, `fedop_tsy` — 연준 오퍼레이션
- `jpy_swap_data` — USD/JPY 포워드 레이트 (period, bid, change_val, spot_rate, fetched_at); annualized_yield는 /jpy 라우트에서 실시간 계산
- `jpy_swap_status` — 스크래핑 상태 (status: ok/retry, message, updated_at)

### Other Features
- **Telegram Alert Engine** (`dashboard/telegram_alerts.py`): 5그룹 차별화 임계치, 1시간 쿨다운, 3회 연속 오류 시 시스템 알람
  - [그룹1] HY OA, CP Rate, JPY 연율화비용, 국채금리: ±3%
  - [그룹2] WTI, Natural Gas, Nasdaq, Dollar Index, USD/KRW: ±4%
  - [그룹3] TQQQ, SQQQ, BTC, Gold, Silver: ±5%
  - [그룹4] VIX, Korea CDS: ±10%
  - [그룹5] EFFR, SOFR: ±2%
  - 통합 지점: `make_refresh_job` (FRED), `refresh_nyfed` (NY Fed), `refresh_jpy` (JPY), `refresh_portfolio` (Portfolio)
- Manual refresh endpoint: `GET /fetch-now`
- KST-based scheduling (07:00 & 22:00 KST)

## Required Secrets
- `FRED_API_KEY` — FRED API key (https://fred.stlouisfed.org/)
- `SESSION_SECRET` — session secret (existing)
- `TELEGRAM_BOT_TOKEN` — Telegram bot token from BotFather
- `TELEGRAM_CHAT_ID` — Telegram chat ID

## Key Commands

- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- `pnpm --filter @workspace/api-server run dev` — run API server locally

See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details.
