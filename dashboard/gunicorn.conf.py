"""
Gunicorn 운영 설정 — Financial Market Tracker v1.0
24시간 무중단 운영 최적화
"""
import os

# ── 서버 바인딩 ─────────────────────────────────────────────────
bind    = f"0.0.0.0:{os.environ.get('PORT', '18955')}"
backlog = 64

# ── 워커 설정 ───────────────────────────────────────────────────
# APScheduler + yfinance + Playwright는 단일 프로세스에서 실행해야 함
# preload_app=True 사용 시 fork 후 라이브러리 circular import 문제 발생 → 사용 안 함
workers      = 1
worker_class = "gthread"
threads      = 4      # 동시 요청 처리 (I/O 대기 중 다른 요청 처리)
timeout      = 180    # Playwright 스크래핑 소요 시간 고려 (WGB CDS: ~65s, 총 ~160s)
keepalive    = 10

# ── 로깅 ───────────────────────────────────────────────────────
accesslog  = "-"
errorlog   = "-"
loglevel   = "info"
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(D)sµs'

# ── 프로세스 이름 ───────────────────────────────────────────────
proc_name = "financial-market-tracker"

# ── Graceful 재시작 ─────────────────────────────────────────────
graceful_timeout = 30
