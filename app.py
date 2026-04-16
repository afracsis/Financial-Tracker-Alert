"""
금융 지표 대시보드 — Flask 백엔드
- FRED API 연동 (HY OA Index, A2/P2 CP 금리)
- NY Fed API 연동 (EFFR, SOFR, RRP)
- KST(Asia/Seoul) 기준 시간 표시 (pytz)
- APScheduler: 지표별 개별 스케줄 설정
- SQLite 중복 저장 방지 (UNIQUE date + INSERT OR IGNORE)
"""
import os
import json
import sqlite3
import logging
import time
import threading
import urllib.request

try:
    import yfinance as yf
    _yf_available = True
except ImportError:
    _yf_available = False
import urllib.parse
from datetime import datetime, timedelta, date as date_type
from functools import wraps

import pytz
from flask import Flask, render_template, jsonify, make_response, redirect, request
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

import jpy_scraper        # JPY 포워드 레이트 스크래퍼
import portfolio_scraper  # 종합 포트폴리오 시장 스크래퍼
import telegram_alerts    # 텔레그램 알람 엔진
from auth import auth_bp, init_auth, ALLOWED_EMAILS  # Google OAuth 인증

# ── 로깅: KST 기준 포맷터 ──────────────────────────────────────
KST = pytz.timezone("Asia/Seoul")


class KSTFormatter(logging.Formatter):
    """모든 로그 시각을 KST로 출력합니다."""
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=KST)
        return dt.strftime(datefmt or "%Y-%m-%d %H:%M:%S KST")


handler = logging.StreamHandler()
handler.setFormatter(KSTFormatter("%(asctime)s %(levelname)s %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[handler])
log = logging.getLogger(__name__)

# ── Flask ──────────────────────────────────────────────────────
app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True

# ── 보안 / 세션 설정 ────────────────────────────────────────────
app.secret_key = os.environ.get("SESSION_SECRET", os.urandom(32))
app.config["PERMANENT_SESSION_LIFETIME"]  = timedelta(days=30)
app.config["REMEMBER_COOKIE_DURATION"]    = timedelta(days=30)
app.config["REMEMBER_COOKIE_HTTPONLY"]    = True
app.config["REMEMBER_COOKIE_SECURE"]      = True
app.config["REMEMBER_COOKIE_SAMESITE"]    = "None"   # OAuth 리디렉션 시 쿠키 전달 필요
app.config["SESSION_COOKIE_SAMESITE"]     = "None"   # OAuth CSRF state 쿠키 전달 필요
app.config["SESSION_COOKIE_HTTPONLY"]     = True
app.config["SESSION_COOKIE_SECURE"]       = True

# Replit 리버스 프록시 환경 — HTTPS + 올바른 remote_addr 인식
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")
FRED_API_BASE = "https://api.stlouisfed.org/fred/series/observations"

# ── 버전 상수 ───────────────────────────────────────────────────
THRESHOLD_TABLE_VERSION = "v1.2026-04-01"  # Stage 1 패치 bump (기존 v1.2026-04)
SCORE_VERSION           = "v1.0.1"         # tmrs_scores 레코드 태깅용

# ── NY Fed API ─────────────────────────────────────────────────
NYFED_BASE = "https://markets.newyorkfed.org/api"
NYFED_HEADERS = {"Accept": "application/json"}

# ── JPY 만기별 일수 (Stage 2.0 인프라, Stage 2.4 점수화에서 사용) ─
# 기존 함수 내 로컬 변수(_JPY_PERIOD_DAYS, PERIOD_DAYS)와 동일한 값.
# 신규 save_jpy_daily_snapshot() 및 analyze_jpy_distribution.py 에서 참조.
JPY_PERIOD_DAYS: dict[str, int] = {
    "1M":  30,
    "3M":  90,
    "3Y":  1095,
    "7Y":  2555,
    "10Y": 3650,
}


# ══════════════════════════════════════════════════════════════
# 지표 레지스트리
# 각 지표마다 개별 스케줄을 설정합니다.
# 새로운 지표를 추가할 때 이 딕셔너리에 항목을 추가하세요.
#
# schedule 필드 설명 (APScheduler CronTrigger 형식):
#   hour      : 실행 시각 (KST 기준, 쉼표로 여러 시각 지정 가능)
#   minute    : 분 (기본값 0)
#   timezone  : 항상 "Asia/Seoul" 권장
# ══════════════════════════════════════════════════════════════
INDICATORS = {
    "BAMLH0A0HYM2": {
        "name": "HY OA Index",
        "description": "ICE BofA US High Yield Index Option-Adjusted Spread",
        "table": "hy_index",
        "color": "#4299e1",   # 차트 색상
        "schedule": {
            "hour": "7,22",   # KST 07:00 및 22:00
            "minute": "0",
            "timezone": "Asia/Seoul",
        },
    },
    "RIFSPPNA2P2D30NB": {
        "name": "A2/P2 비금융 CP 금리 (30일)",
        "description": "30-Day A2/P2 Nonfinancial Commercial Paper Interest Rate",
        "table": "cp_30d",
        "color": "#f6ad55",   # 차트 색상
        "schedule": {
            "hour": "7,22",   # KST 07:00 및 22:00 (HY OA 동일 주기)
            "minute": "0",
            "timezone": "Asia/Seoul",
        },
    },
    "VIXCLS": {
        "name": "VIX (CBOE)",
        "description": "CBOE Volatility Index — daily close via FRED",
        "table": "vix_index",
        "color": "#9f7aea",
        "schedule": {
            "hour": "7,22",
            "minute": "10",   # FRED/NY Fed 갱신(minute=0) 이후
            "timezone": "Asia/Seoul",
        },
    },
    # AA 30D CP는 FRED API 미지원(HTTP 400) → 수동 입력 방식으로 관리 (aa_manual 테이블)
}


# ── DB ────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """등록된 모든 지표 테이블을 초기화합니다."""
    conn = get_db()
    for series_id, meta in INDICATORS.items():
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {meta['table']} (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                date       TEXT    NOT NULL UNIQUE,
                value      REAL    NOT NULL,
                fetched_at TEXT    NOT NULL
            )
        """)
        log.info(f"테이블 준비 완료: {meta['table']} ({series_id})")

    # NY Fed 전용 테이블 (EFFR / SOFR: rate + volume, RRP: accepted amount)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS nyfed_effr (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            date           TEXT    NOT NULL UNIQUE,
            rate           REAL    NOT NULL,
            volume_billions REAL,
            fetched_at     TEXT    NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS nyfed_sofr (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            date           TEXT    NOT NULL UNIQUE,
            rate           REAL    NOT NULL,
            volume_billions REAL,
            fetched_at     TEXT    NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS nyfed_rrp (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            date            TEXT    NOT NULL UNIQUE,
            total_amt_billions REAL NOT NULL,
            fetched_at      TEXT    NOT NULL
        )
    """)
    # nyfed_effr에 target_low / target_high 컬럼 추가 (마이그레이션)
    for col in ("target_low", "target_high"):
        try:
            conn.execute(f"ALTER TABLE nyfed_effr ADD COLUMN {col} REAL")
            log.info(f"nyfed_effr: {col} 컬럼 추가 완료")
        except Exception:
            pass  # 이미 존재하는 경우 무시

    # ── Fed Operation 전용 테이블 ────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fedop_soma (
            asof_date  TEXT NOT NULL PRIMARY KEY,
            total_bil  REAL NOT NULL,
            mbs_bil    REAL,
            fetched_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fedop_ambs (
            operation_id TEXT NOT NULL PRIMARY KEY,
            op_date      TEXT NOT NULL,
            direction    TEXT,
            accepted_bil REAL,
            op_type      TEXT,
            fetched_at   TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fedop_seclending (
            operation_id     TEXT NOT NULL PRIMARY KEY,
            op_date          TEXT NOT NULL,
            par_accepted_bil REAL,
            fetched_at       TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fedop_tsy (
            operation_id TEXT NOT NULL PRIMARY KEY,
            op_date      TEXT NOT NULL,
            direction    TEXT,
            accepted_bil REAL,
            op_type      TEXT,
            fetched_at   TEXT NOT NULL
        )
    """)
    # ── submitted_bil 컬럼 마이그레이션 (기존 테이블에 추가) ────
    for tbl, col in [
        ("fedop_ambs",       "submitted_bil"),
        ("fedop_seclending", "submitted_bil"),
        ("fedop_tsy",        "submitted_bil"),
    ]:
        try:
            conn.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} REAL")
            log.info(f"{tbl}: {col} 컬럼 추가 완료")
        except Exception:
            pass  # 이미 존재하는 경우 무시
    # seclending: par_accepted_bil → accepted_bil 통일 (신규 행은 accepted_bil 컬럼도 유지)
    try:
        conn.execute("ALTER TABLE fedop_seclending ADD COLUMN accepted_bil REAL")
    except Exception:
        pass

    # ── MOVE Index 테이블 ──────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS move_index (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            date       TEXT    NOT NULL UNIQUE,
            value      REAL,
            fetched_at TEXT    NOT NULL
        )
    """)

    # ── CBOE SKEW Index ───────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS skew_index (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            date       TEXT    NOT NULL UNIQUE,
            value      REAL,
            fetched_at TEXT    NOT NULL
        )
    """)

    # ── Discount Window Primary Credit (FRED WLCFLPCL, $백만) ────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS discount_window (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            date       TEXT    NOT NULL UNIQUE,
            value      REAL,
            fetched_at TEXT    NOT NULL
        )
    """)

    # ── TGA (Treasury General Account, FRED WTREGEN, $백만) ──────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tga_balance (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            date       TEXT    NOT NULL UNIQUE,
            value      REAL,
            fetched_at TEXT    NOT NULL
        )
    """)

    # ── SOFR 90일 평균 (FRED SOFR90DAYAVG, %) ────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sofr_90d (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            date       TEXT    NOT NULL UNIQUE,
            value      REAL,
            fetched_at TEXT    NOT NULL
        )
    """)
    log.info("Phase 2 지표 테이블 준비 완료 (skew_index, discount_window, tga_balance, sofr_90d)")

    # ── RP / RRP 오퍼레이션 결과 테이블 ─────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fedop_rrp (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            op_date             TEXT    NOT NULL UNIQUE,
            total_accepted_bil  REAL,
            total_submitted_bil REAL,
            fetched_at          TEXT    NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fedop_rp (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            op_date             TEXT    NOT NULL UNIQUE,
            total_accepted_bil  REAL,
            total_submitted_bil REAL,
            fetched_at          TEXT    NOT NULL
        )
    """)
    log.info("NY Fed 테이블 준비 완료 (nyfed_effr, nyfed_sofr, nyfed_rrp, fedop_*, fedop_rrp, fedop_rp)")

    # ── JPY 포워드 레이트 테이블 ──────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jpy_swap_data (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            period     TEXT NOT NULL,
            bid        REAL,
            change_val REAL,
            spot_rate  REAL,
            fetched_at TEXT NOT NULL
        )
    """)
    # 기존 테이블에 spot_rate 컬럼이 없으면 추가 (마이그레이션)
    existing_cols = [r[1] for r in conn.execute("PRAGMA table_info(jpy_swap_data)").fetchall()]
    if "spot_rate" not in existing_cols:
        conn.execute("ALTER TABLE jpy_swap_data ADD COLUMN spot_rate REAL")
        log.info("jpy_swap_data: spot_rate 컬럼 추가 완료")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jpy_period_time ON jpy_swap_data(period, fetched_at)")

    # ── Stage 2.0: JPY 일별 Snapshot 테이블 ──────────────────────
    # 매일 KST 08:00 에 각 만기(1M/3M/3Y/7Y/10Y)의 bid + implied_yield 저장.
    # 30일 누적 후 Stage 2.4 에서 percentile 기반 임계 확정 및 TMRS 통합.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jpy_swap_daily (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            date             TEXT    NOT NULL,
            period           TEXT    NOT NULL,
            bid              REAL    NOT NULL,
            spot_rate        REAL    NOT NULL,
            implied_yield_pct REAL,
            snapshot_time    TEXT    NOT NULL,
            UNIQUE(date, period)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jpy_daily_date   ON jpy_swap_daily(date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jpy_daily_period ON jpy_swap_daily(period)")
    log.info("Stage 2.0 신규 테이블 준비 완료 (jpy_swap_daily)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS jpy_swap_status (
            id         INTEGER PRIMARY KEY DEFAULT 1,
            status     TEXT NOT NULL DEFAULT 'init',
            message    TEXT,
            updated_at TEXT NOT NULL
        )
    """)
    # 초기 상태 행 삽입 (없을 경우에만)
    conn.execute(
        "INSERT OR IGNORE INTO jpy_swap_status (id, status, updated_at) VALUES (1, 'init', ?)",
        (datetime.now(tz=KST).strftime("%Y-%m-%d %H:%M:%S KST"),),
    )
    log.info("JPY Swap 테이블 준비 완료")

    # ── 사용자(인증) 로그 테이블 ─────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email       TEXT NOT NULL PRIMARY KEY,
            name        TEXT,
            first_login TEXT NOT NULL,
            last_login  TEXT NOT NULL,
            last_ip     TEXT,
            login_count INTEGER NOT NULL DEFAULT 1
        )
    """)
    log.info("users 테이블 준비 완료")

    # ── AA 30D CP 수동 입력 테이블 ───────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS aa_manual (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            date       TEXT    NOT NULL UNIQUE,
            value      REAL    NOT NULL,
            note       TEXT,
            entered_at TEXT    NOT NULL
        )
    """)
    log.info("aa_manual 테이블 준비 완료")

    # ── TMRS 점수 이력 테이블 ─────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tmrs_scores (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            calculated_at  TEXT    NOT NULL,
            trigger        TEXT    NOT NULL,
            total_score    REAL    NOT NULL,
            total_tier     TEXT    NOT NULL,
            l1_score       REAL,
            l2_score       REAL,
            l3_score       REAL,
            div_score      REAL,
            indicator_tiers TEXT,
            inverse_turkey INTEGER DEFAULT 0,
            interpretation TEXT,
            snapshot       TEXT,
            score_version  TEXT    DEFAULT 'v1.0'
        )
    """)
    # score_version 컬럼 마이그레이션 (기존 DB 호환)
    existing_tmrs_cols = [r[1] for r in conn.execute("PRAGMA table_info(tmrs_scores)").fetchall()]
    if "score_version" not in existing_tmrs_cols:
        conn.execute("ALTER TABLE tmrs_scores ADD COLUMN score_version TEXT DEFAULT 'v1.0'")
        conn.execute("UPDATE tmrs_scores SET score_version = 'v1.0' WHERE score_version IS NULL")
        log.info("tmrs_scores: score_version 컬럼 추가 + 기존 레코드 'v1.0' 태깅 완료")
    log.info("tmrs_scores 테이블 준비 완료")

    # ── Stage 1: Layer 2 신규 지표 테이블 ───────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS single_b_oas (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            date       TEXT    NOT NULL UNIQUE,
            oas_bp     REAL    NOT NULL,
            fetched_at TEXT    NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_single_b_oas_date ON single_b_oas(date)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ig_oas (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            date       TEXT    NOT NULL UNIQUE,
            oas_bp     REAL    NOT NULL,
            fetched_at TEXT    NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ig_oas_date ON ig_oas(date)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS lqd_prices (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            date             TEXT    NOT NULL UNIQUE,
            close_price      REAL    NOT NULL,
            daily_change_pct REAL,
            fetched_at       TEXT    NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lqd_prices_date ON lqd_prices(date)")

    log.info("Stage 1 신규 테이블 준비 완료 (single_b_oas, ig_oas, lqd_prices)")

    # ── Stage 2: HYG ETF 가격 테이블 ─────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hyg_prices (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            date             TEXT    NOT NULL UNIQUE,
            close_price      REAL    NOT NULL,
            daily_change_pct REAL,
            fetched_at       TEXT    NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hyg_prices_date ON hyg_prices(date)")
    log.info("Stage 2 신규 테이블 준비 완료 (hyg_prices)")

    # ── Hotfix migration: BAMLH0A2HYBEY(Effective Yield) → BAMLH0A2HYB(OAS) ─
    # HYBEY는 국채금리+스프레드 합계(≈7%)이므로 bp 변환 시 700+bp — 항상 Crisis.
    # 올바른 HYB(OAS)는 현재 3.19% = 319bp (Normal).
    # 감지 조건: oas_bp > 650 레코드 삭제 (HYBEY 범위, 정상 OAS 이 범위 거의 없음)
    try:
        wrong_count = conn.execute(
            "SELECT COUNT(*) FROM single_b_oas WHERE oas_bp > 650"
        ).fetchone()[0]
        if wrong_count > 0:
            conn.execute("DELETE FROM single_b_oas WHERE oas_bp > 650")
            log.warning(
                f"[Single-B OAS] BAMLH0A2HYBEY 오류 데이터 {wrong_count}건 삭제 "
                "(Effective Yield → OAS 시리즈 마이그레이션)"
            )
    except Exception:
        pass  # 최초 실행 시 테이블 없을 수 있음 (무시)

    conn.commit()
    conn.close()


# ── FRED API ──────────────────────────────────────────────────

def fetch_fred_observations(series_id: str, limit: int = 10) -> list | None:
    """
    FRED API에서 관측값을 가져옵니다.
    :param series_id: FRED 시리즈 코드 (예: BAMLH0A0HYM2)
    :param limit: 최근 몇 개 가져올지 (초기 로드 시 1000 사용)
    :return: observations 리스트 또는 None
    """
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        log.error("FRED_API_KEY 환경변수가 설정되지 않았습니다.")
        return None

    params = urllib.parse.urlencode({
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": limit,
        "observation_start": "2020-01-01",
    })
    url = f"{FRED_API_BASE}?{params}"

    _max_retries = 3
    _backoff = [2, 4, 8]  # 초 단위 대기 (지수 백오프)

    for attempt in range(1, _max_retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            observations = data.get("observations", [])
            log.info(f"[{series_id}] FRED에서 {len(observations)}개 관측값 수신")
            return observations
        except Exception as e:
            wait = _backoff[attempt - 1] if attempt <= len(_backoff) else 8
            if attempt < _max_retries:
                log.warning(f"[{series_id}] FRED API 시도 {attempt}/{_max_retries} 실패: {e} — {wait}초 후 재시도")
                time.sleep(wait)
            else:
                log.error(f"[{series_id}] FRED API {_max_retries}회 모두 실패: {e}")
                return None


def upsert_observations(table: str, observations: list) -> int:
    """
    관측값을 DB에 저장합니다.
    - 동일 날짜(UNIQUE date) 데이터는 INSERT OR IGNORE로 중복 저장 방지
    - '.' 값(결측치)은 건너뜁니다
    :return: 신규 저장된 건수
    """
    if not observations:
        return 0

    conn = get_db()
    inserted = 0
    fetched_at = now_kst_str()

    for obs in observations:
        date = obs.get("date", "")
        value_str = obs.get("value", ".")
        if value_str in (".", "") or not date:
            continue
        try:
            value = float(value_str)
        except ValueError:
            continue

        cursor = conn.execute(
            f"INSERT OR IGNORE INTO {table} (date, value, fetched_at) VALUES (?, ?, ?)",
            (date, value, fetched_at),
        )
        if cursor.rowcount > 0:
            inserted += 1

    conn.commit()
    conn.close()
    log.info(f"[{table}] 신규 저장: {inserted}건 (중복 무시)")
    return inserted


# ── 시간 유틸 ──────────────────────────────────────────────────

def now_kst() -> datetime:
    """현재 KST 시각을 반환합니다."""
    return datetime.now(tz=KST)


def now_kst_str() -> str:
    """현재 KST 시각을 문자열로 반환합니다."""
    return now_kst().strftime("%Y-%m-%d %H:%M:%S KST")


# ════════════════════════════════════════════════════════════════
# TMRS (TW Macro Risk Score) 엔진 — v1
# Layer 1(자금 45pt) + Layer 2(신용 30pt) + Layer 3(주식 15pt) + Divergence(10pt)
# ════════════════════════════════════════════════════════════════

_TIER_SCORE = {"normal": 0.00, "watch": 0.40, "stress": 0.75, "crisis": 1.00}
_TIER_META  = {
    "normal": {"ko": "정상",     "color": "#68d391", "emoji": "🟢"},
    "watch":  {"ko": "주의",     "color": "#f6ad55", "emoji": "🟡"},
    "stress": {"ko": "스트레스", "color": "#fc8181", "emoji": "🔴"},
    "crisis": {"ko": "위기",     "color": "#9b2c2c", "emoji": "🚨"},
}

# ── 지표별 해석 텍스트 (Signal Desk 상세 카드용) ─────────────────
# v1.0 통합문서 카테고리 3.4–3.6 요약
INDICATOR_INTERPRETATIONS: dict[str, str] = {
    "sofr_effr":      "담보(SOFR)·무담보(EFFR) 금리 괴리. 확대 시 단기 자금시장 스트레스 — 은행 간 신뢰 약화 신호.",
    "cp_aa_spread":   "A2/P2 CP − AA 금리차. 확대 시 비은행 기업의 단기 조달 비용 급등 — CP 시장 경색.",
    "rrp":            "Fed RRP 잔고. 소진 시 시스템 유동성 완충재 고갈. QT로 구조적 감소 중 — 유동성 취약성 증가.",
    "sofr_term":      "SOFR 90일 평균 − 당일 SOFR 괴리. 텀 프리미엄 확대 = 중기 자금 조달 스트레스 선행.",
    "discount_window": "Fed 긴급 창구 이용액. 급증 시 은행 시스템의 구조적 자금 조달 문제 — 최후 수단 사용.",
    "tga":            "재무부 현금 계좌 주간 변화. 급감 시 부채한도 위기 또는 재정 긴장 신호.",
    "hy_oas":         "고수익채권 OAS. 상승 시 Credit 시장 전반의 위험 회피 심화 — Funding stress 의 Credit 전이 신호.",
    "cp_effr":        "[보류 중 · cap=0] A2/P2 CP − EFFR 괴리. Stage 2.2 에서 A2/P2-AA 스프레드와 중복성 검토 후 정식 처리 예정.",
    "single_b_oas":   "Single-B 등급 OAS. HY 중 가장 위험한 등급. Credit 위험의 가장 민감한 선행 지표 — 319bp 이하는 정상.",
    "ig_oas":         "투자등급 OAS. 상승 시 우량 기업까지 Credit 스트레스 전이 — 최후 단계의 신호.",
    "lqd_daily":      "LQD 일간 변화율 (투자등급 채권 ETF). 급락 시 기관 투자자의 유동성 확보 매도 — IG 시장 경색.",
    "hyg_daily":      "HYG 일간 변화율 (HY 채권 ETF). 급락 시 HY 시장의 실시간 유동성 압박 — Credit 위험 실시간 탐지.",
    "hyg_5day":       "HYG 5거래일 누적 변화율. 단기 노이즈를 줄인 HY 채권 시장 추세 — hyg_daily 의 확증 지표.",
    "move":           "채권 내재 변동성. 상승 시 금리 불확실성 증가 — MOVE/VIX 비율과 함께 Inverse Turkey 판별에 사용.",
    "vix":            "주식 내재 변동성. 자금·신용 스트레스 대비 낮으면 Inverse Turkey 패턴 (시장 미반응 위험).",
    "skew":           "CBOE SKEW. 상승 시 꼬리 위험(tail risk) 프리미엄 급등 — 블랙스완 헤지 수요 증가.",
    "move_vix_ratio": "MOVE/VIX 비율. 상승 시 채권 스트레스가 주식 시장 선행 — Inverse Turkey 의 핵심 전조 지표.",
}

# ── 지표별 임계값 설명 (단계별 텍스트, 상세 카드 표시용) ─────────
INDICATOR_THRESHOLDS: dict[str, list] = {
    # [normal_range, watch_range, stress_range, crisis_range]
    "sofr_effr":      ["< 0bp",     "0 ~ 3bp",    "3 ~ 8bp",     "> 8bp"],
    "cp_aa_spread":   ["< 20bp",    "20 ~ 35bp",  "35 ~ 50bp",   "> 50bp"],
    "rrp":            ["> $100B",   "$50 ~ 100B",  "$10 ~ 50B",   "< $10B"],
    "sofr_term":      ["< 5bp",     "5 ~ 15bp",   "15 ~ 30bp",   "> 30bp"],
    "discount_window":["$0",        "< $5,000M",  "< $50,000M",  "> $50,000M"],
    "tga":            ["< |$30B|",  "|$30 ~ 75B|","| $75 ~ 150B|","> |$150B|"],
    "hy_oas":         ["< 3.5%",   "3.5 ~ 5.0%", "5.0 ~ 7.0%",  "> 7.0%"],
    "cp_effr":        ["< 0.30pp", "0.30 ~ 0.60pp","0.60 ~ 1.00pp","> 1.00pp"],
    "single_b_oas":   ["< 350bp",  "350 ~ 450bp","450 ~ 600bp",  "> 600bp"],
    "ig_oas":         ["< 100bp",  "100 ~ 130bp","130 ~ 180bp",  "> 180bp"],
    "lqd_daily":      ["> -0.5%",  "-0.5 ~ -1.0%","-1.0 ~ -2.0%","< -2.0%"],
    "hyg_daily":      ["> -0.3%",  "-0.3 ~ -0.7%","-0.7 ~ -1.5%","< -1.5%"],
    "hyg_5day":       ["< ±1.0%",  "±1.0 ~ 2.5%","±2.5 ~ 5.0%",  "> ±5.0%"],
    "move":           ["< 80",     "80 ~ 100",   "100 ~ 150",    "> 150"],
    "vix":            ["< 20",     "20 ~ 30",    "30 ~ 45",      "> 45"],
    "skew":           ["< 130",    "130 ~ 145",  "145 ~ 160",    "> 160"],
    "move_vix_ratio": ["< 4",      "4 ~ 5",      "5 ~ 6",        "> 6"],
}


def _tier(value: float, bounds: list) -> str:
    """bounds: [(upper_exclusive, tier), ..., (None, 'crisis')] 낮은 위험 → 높은 위험 순"""
    for upper, t in bounds:
        if upper is None or value < upper:
            return t
    return bounds[-1][1]


def _compute_tmrs(trigger: str = "manual") -> dict:
    """TMRS 점수를 계산하고 DB에 저장한 뒤 결과 dict를 반환합니다."""
    conn = get_db()
    inds: dict = {}

    # ── Layer 1: 자금시장 (Deep) — 45pt 상한 ─────────────────────

    # 1-a. SOFR-EFFR 스프레드 (bp) — cap 6pt
    sofr = conn.execute("SELECT rate FROM nyfed_sofr ORDER BY date DESC LIMIT 1").fetchone()
    effr = conn.execute("SELECT rate FROM nyfed_effr ORDER BY date DESC LIMIT 1").fetchone()
    if sofr and effr:
        v = round((sofr["rate"] - effr["rate"]) * 100, 2)
        inds["sofr_effr"] = dict(
            name="SOFR-EFFR 스프레드", layer=1, cap=6, value=v, unit="bp",
            tier=_tier(v, [(0,"normal"), (3,"watch"), (8,"stress"), (None,"crisis")]),
        )

    # 1-b. A2/P2 − AA CP 스프레드 (bp) — cap 6pt
    cp30 = conn.execute("SELECT value FROM cp_30d ORDER BY date DESC LIMIT 1").fetchone()
    aa   = conn.execute("SELECT value FROM aa_manual ORDER BY date DESC LIMIT 1").fetchone()
    if cp30 and aa:
        v = round((cp30["value"] - aa["value"]) * 100, 2)
        inds["cp_aa_spread"] = dict(
            name="CP 스프레드 (A2/P2−AA)", layer=1, cap=6, value=v, unit="bp",
            tier=_tier(v, [(20,"normal"), (35,"watch"), (50,"stress"), (None,"crisis")]),
        )

    # 1-c. RRP 잔고 (B$, 낮을수록 위험) — cap 4pt
    # 2025년 기준 QT로 인한 구조적 소진 반영: 임계값 하향 조정
    rrp = conn.execute("SELECT total_amt_billions FROM nyfed_rrp ORDER BY date DESC LIMIT 1").fetchone()
    if rrp and rrp["total_amt_billions"] is not None:
        v = rrp["total_amt_billions"]
        inds["rrp"] = dict(
            name="RRP 잔고", layer=1, cap=4, value=v, unit="B$",
            tier=_tier(-v, [(-100,"normal"), (-50,"watch"), (-10,"stress"), (None,"crisis")]),
        )

    # 1-d. SOFR 텀 프리미엄 (SOFR90DAYAVG − SOFR, bp) — cap 6pt
    sofr_90 = conn.execute("SELECT value FROM sofr_90d ORDER BY date DESC LIMIT 1").fetchone()
    if sofr and sofr_90:
        v = round((sofr_90["value"] - sofr["rate"]) * 100, 2)
        inds["sofr_term"] = dict(
            name="SOFR 텀 프리미엄", layer=1, cap=6, value=v, unit="bp",
            tier=_tier(abs(v), [(5,"normal"), (15,"watch"), (30,"stress"), (None,"crisis")]),
        )

    # 1-e. Discount Window 잔액 ($백만) — cap 5pt
    dw = conn.execute("SELECT value FROM discount_window ORDER BY date DESC LIMIT 1").fetchone()
    if dw is not None:
        v = dw["value"] if dw["value"] is not None else 0.0
        inds["discount_window"] = dict(
            name="Discount Window", layer=1, cap=5, value=v, unit="$백만",
            tier="normal" if v == 0 else ("watch" if v < 5_000 else ("stress" if v < 50_000 else "crisis")),
        )

    # 1-f. TGA 주간 변화 ($백만) — cap 4pt (급감=위험, 급증=흡수)
    tga_rows = conn.execute("SELECT value FROM tga_balance ORDER BY date DESC LIMIT 2").fetchall()
    if len(tga_rows) >= 2:
        tga_chg = tga_rows[0]["value"] - tga_rows[1]["value"]  # 양수=증가(흡수), 음수=감소(공급)
        v = round(tga_chg / 1_000, 1)  # $십억 단위
        inds["tga"] = dict(
            name="TGA 주간변화", layer=1, cap=4, value=v, unit="$B",
            tier=_tier(abs(v), [(30,"normal"), (75,"watch"), (150,"stress"), (None,"crisis")]),
        )

    # ── Layer 2: 신용시장 (Credit) — 30pt 상한 ────────────────────

    # 2-a. HY OAS (%) — cap 5pt  [v1.0 카테고리 4.6 원본 복원: 7→5]
    # ADR: 2026-04-14-stage1-layer2-weight-correction.md
    hy = conn.execute("SELECT value FROM hy_index ORDER BY date DESC LIMIT 1").fetchone()
    if hy:
        v = hy["value"]
        inds["hy_oas"] = dict(
            name="HY OAS", layer=2, cap=5, value=v, unit="%",
            tier=_tier(v, [(3.5,"normal"), (5.0,"watch"), (7.0,"stress"), (None,"crisis")]),
        )

    # 2-b. A2/P2 CP − EFFR 스프레드 — cap=0 (점수 기여 보류)  [Stage 1 결정]
    # 지표는 snapshot/UI에 표시하되 Layer 2 점수 기여 없음.
    # 사유: v1.0 Layer 2 가중치 표에 없는 독자 구현 지표.
    #       Stage 2에서 A2/P2-AA Spread(Layer 1, 6pt)와 redundancy 평가 후 정식 처리.
    # ADR: 2026-04-14-stage1-cp-effr-weight-zero.md
    if cp30 and effr:
        v = round(cp30["value"] - effr["rate"], 4)
        inds["cp_effr"] = dict(
            name="A2/P2 CP−EFFR", layer=2, cap=0, value=v, unit="pp",
            tier=_tier(v, [(0.30,"normal"), (0.60,"watch"), (1.00,"stress"), (None,"crisis")]),
        )

    # 2-c. Single-B OAS (bp) — cap 7pt  [Stage 1 신규]
    # v1.0 카테고리 3.5.1: <350bp normal / 350-450 watch / 450-600 stress / >600 crisis
    sb_row = conn.execute("SELECT oas_bp FROM single_b_oas ORDER BY date DESC LIMIT 1").fetchone()
    if sb_row and sb_row["oas_bp"]:
        v = sb_row["oas_bp"]
        inds["single_b_oas"] = dict(
            name="Single-B OAS", layer=2, cap=7, value=v, unit="bp",
            tier=_tier(v, [(350,"normal"), (450,"watch"), (600,"stress"), (None,"crisis")]),
        )

    # 2-d. IG OAS (bp) — cap 3pt  [Stage 1 신규]
    # v1.0 카테고리 3.5.1: <100bp normal / 100-130 watch / 130-180 stress / >180 crisis
    ig_row = conn.execute("SELECT oas_bp FROM ig_oas ORDER BY date DESC LIMIT 1").fetchone()
    if ig_row and ig_row["oas_bp"]:
        v = ig_row["oas_bp"]
        inds["ig_oas"] = dict(
            name="IG OAS", layer=2, cap=3, value=v, unit="bp",
            tier=_tier(v, [(100,"normal"), (130,"watch"), (180,"stress"), (None,"crisis")]),
        )

    # 2-e. LQD 일간 변화율 (%) — cap 2pt  [Stage 1 신규]
    # v1.0 카테고리 3.5.2: >-0.5% normal / -0.5~-1% watch / -1~-2% stress / <-2% crisis
    # Direction: inverse (음수가 클수록 stress → 값 부호 반전하여 _tier 적용)
    lqd_row = conn.execute(
        "SELECT daily_change_pct FROM lqd_prices WHERE daily_change_pct IS NOT NULL ORDER BY date DESC LIMIT 1"
    ).fetchone()
    if lqd_row and lqd_row["daily_change_pct"] is not None:
        v = lqd_row["daily_change_pct"]
        inds["lqd_daily"] = dict(
            name="LQD 일간 변화율", layer=2, cap=2, value=v, unit="%",
            tier=_tier(-v, [(0.5,"normal"), (1.0,"watch"), (2.0,"stress"), (None,"crisis")]),
        )

    # 2-f. HYG 일간 변화율 (%) — cap 4pt  [Stage 2 신규]
    # v1.0 카테고리 3.5.3: >-0.3% normal / -0.3~-0.7% watch / -0.7~-1.5% stress / <-1.5% crisis
    # Direction: inverse (음수가 클수록 stress → 값 부호 반전하여 _tier 적용)
    hyg_row = conn.execute(
        "SELECT daily_change_pct FROM hyg_prices WHERE daily_change_pct IS NOT NULL ORDER BY date DESC LIMIT 1"
    ).fetchone()
    if hyg_row and hyg_row["daily_change_pct"] is not None:
        v = hyg_row["daily_change_pct"]
        inds["hyg_daily"] = dict(
            name="HYG 일간 변화율", layer=2, cap=4, value=v, unit="%",
            tier=_tier(-v, [(0.3,"normal"), (0.7,"watch"), (1.5,"stress"), (None,"crisis")]),
        )

    # 2-g. HYG 5일 변화율 (%) — cap 3pt  [Stage 2 신규]
    # v1.0 카테고리 3.5.3: <1% normal / 1~2.5% watch / 2.5~5% stress / >5% crisis (절댓값 기준)
    # Direction: inverse (5일간 낙폭이 클수록 stress)
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

    # ── Layer 3: 주식·변동성 (Surface) — 15pt 상한 ───────────────

    # 3-a. MOVE Index — cap 4pt
    mv = conn.execute("SELECT value FROM move_index ORDER BY date DESC LIMIT 1").fetchone()
    if mv and mv["value"]:
        v = mv["value"]
        inds["move"] = dict(
            name="MOVE Index", layer=3, cap=4, value=v, unit="",
            tier=_tier(v, [(80,"normal"), (100,"watch"), (150,"stress"), (None,"crisis")]),
        )

    conn.close()

    # ── Layer 3-b: VIX — cap 4pt (이중 소스) ──────────────────────
    # daily_08 → FRED DB (공식 전일 종가)
    # 그 외    → yfinance ^VIX 현물 실시간 → FRED 폴백
    # (VX=F 선물 티커는 yfinance에서 지원 중단됨 → ^VIX 단일 소스)
    _vix_val  = None
    _vix_name = "VIX"

    if trigger != "daily_08" and _yf_available:
        try:
            import threading as _th
            _result: list = []

            def _yf_fetch():
                hist = yf.Ticker("^VIX").history(period="5d", interval="1d")
                if not hist.empty:
                    _result.append((round(float(hist["Close"].iloc[-1]), 2), "VIX 현물"))

            _t = _th.Thread(target=_yf_fetch, daemon=True)
            _t.start()
            _t.join(timeout=10)  # 최대 10초 대기
            if _result:
                _vix_val, _vix_name = _result[0]
                log.info(f"[VIX] 실시간: {_vix_val}")
            elif _t.is_alive():
                log.warning("[VIX] yfinance 타임아웃 (10s) — FRED DB 폴백")
        except Exception as _e:
            log.warning(f"[VIX] yfinance 실패 ({_e}) — FRED DB 폴백")

    if _vix_val is None:
        _vc = get_db()
        _vr = _vc.execute("SELECT value FROM vix_index ORDER BY date DESC LIMIT 1").fetchone()
        _vc.close()
        if _vr:
            _vix_val  = _vr["value"]
            _vix_name = "VIX (FRED)"

    if _vix_val is not None:
        inds["vix"] = dict(
            name=_vix_name, layer=3, cap=4, value=_vix_val, unit="",
            tier=_tier(_vix_val, [(20,"normal"), (25,"watch"), (35,"stress"), (None,"crisis")]),
        )

    # ── Layer 3-c: CBOE SKEW — cap 4pt ──────────────────────────
    _skew_conn = get_db()
    _skew_row  = _skew_conn.execute("SELECT value FROM skew_index ORDER BY date DESC LIMIT 1").fetchone()
    _skew_conn.close()
    if _skew_row and _skew_row["value"]:
        v = _skew_row["value"]
        inds["skew"] = dict(
            name="CBOE SKEW", layer=3, cap=4, value=v, unit="",
            tier=_tier(v, [(130,"normal"), (145,"watch"), (160,"stress"), (None,"crisis")]),
        )

    # ── Layer 3-d: MOVE/VIX 비율 — cap 3pt ───────────────────────
    if _vix_val is not None and "move" in inds:
        move_val = inds["move"]["value"]
        if move_val and _vix_val > 0:
            ratio = round(move_val / _vix_val, 2)
            inds["move_vix_ratio"] = dict(
                name="MOVE/VIX 비율", layer=3, cap=3, value=ratio, unit="",
                tier=_tier(ratio, [(4,"normal"), (5,"watch"), (6,"stress"), (None,"crisis")]),
            )

    # ── 레이어별 점수 계산 ────────────────────────────────────────
    l1 = l2 = l3 = 0.0
    for ind in inds.values():
        pts = _TIER_SCORE[ind["tier"]] * ind["cap"]
        if   ind["layer"] == 1: l1 += pts
        elif ind["layer"] == 2: l2 += pts
        elif ind["layer"] == 3: l3 += pts

    l1 = min(round(l1, 2), 45.0)
    l2 = min(round(l2, 2), 30.0)
    l3 = min(round(l3, 2), 15.0)

    # ── Cross-Layer Divergence — 10pt 상한 ───────────────────────
    l1_sev = l1 / 45
    l2_sev = l2 / 30
    l3_sev = l3 / 15 if l3 > 0 else 0.0
    div = round(min(max(((l1_sev + l2_sev) / 2 - l3_sev) * 10, 0), 10), 2)
    total = round(l1 + l2 + l3 + div, 1)

    # ── 전체 Tier ─────────────────────────────────────────────────
    total_tier = _tier(total, [(20,"normal"), (40,"watch"), (65,"stress"), (None,"crisis")])

    # ── Inverse Turkey 판별 ───────────────────────────────────────
    # v1.0 카테고리 4.11.1: l12_avg >= 0.40 AND l3_norm <= 0.25
    # ADR: 2026-04-14-stage1-inv-turkey-condition-hotfix.md
    l12_avg = (l1_sev + l2_sev) / 2
    inv_turkey = bool(l12_avg >= 0.40 and l3_sev <= 0.25)

    # ── Inverse Turkey Telegram 알람 (Stage 1: 연결 완료) ────────
    try:
        telegram_alerts.alert_inverse_turkey(
            inv_turkey, l1, l2, l3, total, inds
        )
    except Exception as _it_exc:
        log.error(f"[Inverse Turkey] 알람 발송 오류: {_it_exc}")

    # ── 해석 텍스트 생성 ─────────────────────────────────────────
    interp = _tmrs_interpret(total, total_tier, l1, l2, l3, div, inv_turkey, inds)

    # ── DB 저장 ───────────────────────────────────────────────────
    tiers_j    = json.dumps({k: v["tier"] for k, v in inds.items()}, ensure_ascii=False)
    snapshot_j = json.dumps(
        {k: {"value": v["value"], "tier": v["tier"], "name": v["name"],
             "cap": v.get("cap"), "unit": v.get("unit",""), "layer": v.get("layer")}
         for k, v in inds.items()},
        ensure_ascii=False,
    )
    c = get_db()
    c.execute(
        """INSERT INTO tmrs_scores
           (calculated_at, trigger, total_score, total_tier,
            l1_score, l2_score, l3_score, div_score,
            indicator_tiers, inverse_turkey, interpretation, snapshot,
            score_version)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (now_kst_str(), trigger, total, total_tier,
         l1, l2, l3, div, tiers_j, int(inv_turkey), interp, snapshot_j,
         SCORE_VERSION),
    )
    c.commit()
    c.close()
    log.info(f"[TMRS] 계산 완료: {total}점 ({total_tier}) | trigger={trigger}")
    return {
        "total_score": total, "total_tier": total_tier,
        "l1_score": l1, "l2_score": l2, "l3_score": l3, "div_score": div,
        "indicators": inds, "inverse_turkey": inv_turkey,
        "interpretation": interp, "calculated_at": now_kst_str(),
    }


def _tmrs_interpret(total, tier, l1, l2, l3, div, inv_turkey, inds) -> str:
    """룰 기반 TMRS 해석 텍스트 (한국어)."""
    if not inds:
        return "데이터 수집 중입니다. 지표가 업데이트된 후 자동으로 평가됩니다."

    l1_sev = l1 / 45
    l2_sev = l2 / 30
    l3_sev = l3 / 15 if l3 > 0 else 0.0
    dom = max([("자금시장(Layer 1)", l1_sev),
               ("신용시장(Layer 2)", l2_sev),
               ("주식·변동성(Layer 3)", l3_sev)], key=lambda x: x[1])
    stressed = [v["name"] for v in inds.values() if v["tier"] in ("stress", "crisis")]

    if inv_turkey:
        return (
            f"⚠️ Inverse Turkey 패턴 감지 (TMRS {total:.0f}점): "
            "자금·신용시장에서 심각한 이상 신호가 누적되고 있으나 주식시장은 아직 반응하지 않은 상태입니다. "
            "시장이 인식하지 못한 위험이 내재된 상황으로 각별한 주의가 필요합니다."
        )
    if tier == "normal":
        return (
            f"✅ 안정 구간 (TMRS {total:.0f}점): "
            "자금·신용·주식시장 전반적으로 정상 수준이 유지되고 있습니다. "
            "일상적인 모니터링을 지속합니다."
        )
    if tier == "watch":
        s = f"🟡 주의 구간 (TMRS {total:.0f}점): {dom[0]}에서 초기 경고 신호가 감지됩니다. "
        s += (f"{', '.join(stressed[:2])} 추이를 집중 모니터링하십시오."
              if stressed else "아직 스트레스 수준은 아니나 지속 관찰이 필요합니다.")
        return s
    if tier == "stress":
        s = f"🔴 스트레스 구간 (TMRS {total:.0f}점): "
        s += f"{', '.join(stressed[:3])} 등에서 명확한 이상 신호가 확인됩니다. " if stressed else ""
        s += f"{dom[0]}이 주요 스트레스 원인입니다. 포지션 및 리스크 점검을 권장합니다."
        return s
    return (
        f"🚨 위기 구간 (TMRS {total:.0f}점): "
        "복합적인 위기 신호가 다수 레이어에서 동시 감지됩니다. "
        "즉각적인 리스크 관리 행동이 필요합니다."
    )


def _tmrs_after_update():
    """지표 갱신 잡 완료 후 호출: TMRS 즉시 재계산 + Tier 변경 시 텔레그램 알림."""
    try:
        result = _compute_tmrs(trigger="indicator_update")
        # 이전 기록과 Tier 비교
        conn = get_db()
        rows = conn.execute(
            "SELECT total_tier FROM tmrs_scores ORDER BY calculated_at DESC LIMIT 2"
        ).fetchall()
        conn.close()
        if len(rows) == 2 and rows[0]["total_tier"] != rows[1]["total_tier"]:
            msg = (
                f"[Signal Desk] TMRS Tier 변경\n"
                f"{rows[1]['total_tier'].upper()} → {rows[0]['total_tier'].upper()}\n"
                f"점수: {result['total_score']}점\n"
                f"{result['interpretation']}"
            )
            telegram_alerts.send_message(msg)
            log.info(f"[TMRS] Tier 변경 알림 발송: {rows[1]['total_tier']} → {rows[0]['total_tier']}")
    except Exception as exc:
        log.error(f"[TMRS] 갱신 후 재계산 오류: {exc}")


# ── 스케줄 작업 ────────────────────────────────────────────────

def make_refresh_job(series_id: str, meta: dict):
    """
    특정 지표의 갱신 함수를 반환합니다.
    각 지표마다 독립적인 클로저를 생성합니다.
    갱신 후 텔레그램 알람 체크를 수행합니다.
    """
    # FRED series_id → telegram_alerts indicator_key 매핑
    _FRED_ALERT_KEYS = {
        "BAMLH0A0HYM2":     "hy_index",
        "RIFSPPNA2P2D30NB": "cp_30d",
    }

    def refresh_job():
        log.info(f"[{series_id}] 정기 갱신 시작 ({now_kst_str()})")
        observations = fetch_fred_observations(series_id, limit=10)
        if observations:
            count = upsert_observations(meta["table"], observations)
            log.info(f"[{series_id}] 정기 갱신 완료: {count}건 신규 저장")
            telegram_alerts.record_success(f"fred_{series_id}")

            # ── 알람 체크: 직전 2개 레코드 비교 ────────────────
            alert_key = _FRED_ALERT_KEYS.get(series_id)
            if alert_key and count > 0:
                try:
                    conn = get_db()
                    rows = conn.execute(
                        f"SELECT value FROM {meta['table']} ORDER BY date DESC LIMIT 2"
                    ).fetchall()
                    conn.close()
                    if len(rows) >= 2:
                        telegram_alerts.check_and_alert(
                            alert_key, rows[0]["value"], rows[1]["value"]
                        )
                except Exception as exc:
                    log.error(f"[{series_id}] 알람 체크 오류: {exc}")
            # TMRS 재계산 (지표 업데이트 시마다)
            _tmrs_after_update()
        else:
            log.warning(f"[{series_id}] 정기 갱신 실패 — FRED API 응답 없음")
            telegram_alerts.record_error(f"fred_{series_id}", "FRED API 응답 없음")

    refresh_job.__name__ = f"refresh_{series_id}"
    return refresh_job


_scheduler: BackgroundScheduler | None = None  # 전역 스케줄러 (refresh_jpy 재시도에 사용)


def start_scheduler() -> BackgroundScheduler:
    """
    INDICATORS에 등록된 각 지표에 대해 개별 스케줄을 등록합니다.
    새로운 지표를 INDICATORS에 추가하면 자동으로 스케줄이 등록됩니다.

    24시간 안정 운영 설정:
    - misfire_grace_time=300: 서버 재시작 등으로 실행 시각을 놓쳐도 5분 이내면 즉시 실행
    - coalesce=True: 여러 번 놓쳐도 한 번만 실행 (중복 방지)
    - max_instances=1: 동일 작업이 동시에 2개 이상 실행되지 않도록 제한
    """
    # 공통 잡 옵션
    _JOB_DEFAULTS = dict(
        misfire_grace_time=300,  # 5분 grace period
        coalesce=True,
        max_instances=1,
        replace_existing=True,
    )

    scheduler = BackgroundScheduler(
        timezone=KST,
        job_defaults=_JOB_DEFAULTS,
    )

    for series_id, meta in INDICATORS.items():
        sched = meta["schedule"]
        trigger = CronTrigger(
            hour=sched.get("hour", "8"),
            minute=sched.get("minute", "0"),
            timezone=sched.get("timezone", "Asia/Seoul"),
        )
        job_fn = make_refresh_job(series_id, meta)
        scheduler.add_job(job_fn, trigger=trigger, id=f"refresh_{series_id}")
        log.info(
            f"[{series_id}] 스케줄 등록: "
            f"매일 {sched.get('hour', '8')}시 {sched.get('minute', '0')}분 KST"
        )

    # NY Fed 갱신 스케줄 (매일 07:00 / 22:00 KST)
    scheduler.add_job(
        refresh_nyfed,
        trigger=CronTrigger(hour="7,22", minute="0", timezone="Asia/Seoul"),
        id="refresh_nyfed",
    )
    log.info("[NY Fed] 스케줄 등록: 매일 7,22시 0분 KST")

    # JPY 포워드 레이트: 매 1시간마다 갱신
    scheduler.add_job(
        refresh_jpy,
        trigger=IntervalTrigger(hours=1, timezone=KST),
        id="refresh_jpy_hourly",
    )
    log.info("[JPY] 스케줄 등록: 매 1시간")

    # Portfolio 종합 시장 데이터: 매 15분마다 갱신
    # (Playwright Chromium 메모리 누적 방지 — 5분 → 15분)
    scheduler.add_job(
        refresh_portfolio,
        trigger=IntervalTrigger(minutes=15, timezone=KST),
        id="refresh_portfolio",
    )
    log.info("[Portfolio] 스케줄 등록: 매 15분")

    # TMRS Signal Desk: 매일 08:00 KST 정기 계산
    scheduler.add_job(
        lambda: _compute_tmrs(trigger="daily_08"),
        trigger=CronTrigger(hour="8", minute="0", timezone="Asia/Seoul"),
        id="tmrs_daily", **_JOB_DEFAULTS,
    )
    log.info("[TMRS] 스케줄 등록: 매일 08:00 KST")

    # MOVE Index: 매일 07:00 / 22:00 KST (시장 마감 후 갱신)
    scheduler.add_job(
        refresh_move,
        trigger=CronTrigger(hour="7,22", minute="5", timezone="Asia/Seoul"),
        id="refresh_move",
    )
    log.info("[MOVE] 스케줄 등록: 매일 7,22시 5분 KST")

    # CBOE SKEW: 매일 07:10 / 22:10 KST
    scheduler.add_job(
        refresh_skew,
        trigger=CronTrigger(hour="7,22", minute="10", timezone="Asia/Seoul"),
        id="refresh_skew",
    )
    log.info("[SKEW] 스케줄 등록: 매일 7,22시 10분 KST")

    # SOFR 90일 평균: 매일 07:05 / 22:05 KST
    scheduler.add_job(
        refresh_sofr_90d,
        trigger=CronTrigger(hour="7,22", minute="5", timezone="Asia/Seoul"),
        id="refresh_sofr_90d",
    )
    log.info("[SOFR 90d] 스케줄 등록: 매일 7,22시 5분 KST")

    # Discount Window + TGA: 매주 금요일 07:30 KST (H.4.1 목요일 발표 다음날)
    def _refresh_h41():
        refresh_discount_window()
        refresh_tga()

    scheduler.add_job(
        _refresh_h41,
        trigger=CronTrigger(day_of_week="fri", hour="7", minute="30", timezone="Asia/Seoul"),
        id="refresh_h41_weekly",
    )
    log.info("[H4.1] 스케줄 등록: 매주 금요일 7시 30분 KST (Discount Window + TGA)")

    # Stage 1: Single-B OAS + IG OAS (FRED, 매일 07:15 / 22:15 KST)
    scheduler.add_job(
        refresh_single_b_oas,
        trigger=CronTrigger(hour="7,22", minute="15", timezone="Asia/Seoul"),
        id="refresh_single_b_oas",
        **_JOB_DEFAULTS,
    )
    log.info("[Single-B OAS] 스케줄 등록: 매일 7,22시 15분 KST")

    scheduler.add_job(
        refresh_ig_oas,
        trigger=CronTrigger(hour="7,22", minute="15", timezone="Asia/Seoul"),
        id="refresh_ig_oas",
        **_JOB_DEFAULTS,
    )
    log.info("[IG OAS] 스케줄 등록: 매일 7,22시 15분 KST")

    # Stage 1: LQD ETF (yfinance, 매일 07:20 / 22:20 KST)
    scheduler.add_job(
        refresh_lqd,
        trigger=CronTrigger(hour="7,22", minute="20", timezone="Asia/Seoul"),
        id="refresh_lqd",
        **_JOB_DEFAULTS,
    )
    log.info("[LQD] 스케줄 등록: 매일 7,22시 20분 KST")

    # Stage 2: HYG ETF (yfinance, 매일 07:20 / 22:20 KST)
    scheduler.add_job(
        refresh_hyg,
        trigger=CronTrigger(hour="7,22", minute="20", timezone="Asia/Seoul"),
        id="refresh_hyg",
        **_JOB_DEFAULTS,
    )
    log.info("[HYG] 스케줄 등록: 매일 7,22시 20분 KST")

    # Stage 2.0: JPY 일별 snapshot (매일 08:00 KST — NY 마감 직후, TMRS 배치와 동일 시각)
    scheduler.add_job(
        save_jpy_daily_snapshot,
        trigger=CronTrigger(hour="8", minute="0", timezone="Asia/Seoul"),
        id="jpy_daily_snapshot",
        **_JOB_DEFAULTS,
    )
    log.info("[JPY Daily] 스케줄 등록: 매일 08:00 KST")

    scheduler.start()
    log.info("스케줄러 시작 완료 (misfire_grace=5분, coalesce=True, max_instances=1)")
    return scheduler


def initial_load():
    """앱 시작 시 DB가 비어있으면 FRED 이력 전체를 한 번 로드합니다."""
    for series_id, meta in INDICATORS.items():
        conn = get_db()
        count = conn.execute(f"SELECT COUNT(*) FROM {meta['table']}").fetchone()[0]
        conn.close()

        if count == 0:
            log.info(f"[{series_id}] DB 비어있음 — FRED 이력 전체 로드 중...")
            observations = fetch_fred_observations(series_id, limit=1000)
            if observations:
                saved = upsert_observations(meta["table"], observations)
                log.info(f"[{series_id}] 초기 로드 완료: {saved}건 저장")
            else:
                log.error(f"[{series_id}] 초기 로드 실패 — FRED_API_KEY를 확인하세요")
        else:
            log.info(f"[{series_id}] 기존 데이터 {count}건 존재 — 최신 데이터 갱신")
            observations = fetch_fred_observations(series_id, limit=10)
            if observations:
                upsert_observations(meta["table"], observations)

    # NY Fed 초기 로드 (이력 90일 + 최신 갱신)
    log.info("[NY Fed] 초기 데이터 로드 시작...")
    conn = get_db()
    effr_count = conn.execute("SELECT COUNT(*) FROM nyfed_effr").fetchone()[0]
    conn.close()

    # target_low가 모두 NULL이면 재로드 필요 (마이그레이션 이전 데이터)
    conn2 = get_db()
    null_target = conn2.execute(
        "SELECT COUNT(*) FROM nyfed_effr WHERE target_low IS NULL"
    ).fetchone()[0]
    conn2.close()

    if effr_count < 30 or null_target > 0:
        log.info(f"[NY Fed] 이력 로드 필요 (count={effr_count}, null_target={null_target}) — 90일치 로드 중...")
        for series, table in [("effr", "nyfed_effr"), ("sofr", "nyfed_sofr")]:
            hist = fetch_nyfed_rate_history(series, n=90)
            if hist:
                upsert_nyfed_rate_history(table, hist)
    else:
        log.info(f"[NY Fed] 기존 EFFR {effr_count}건 (target 정상) — 최신 갱신은 startup 스레드에서 수행")


# ── NY Fed API ─────────────────────────────────────────────────

def _nyfed_get(url: str) -> dict | None:
    """NY Fed API에 GET 요청을 보내고 JSON을 반환합니다."""
    try:
        req = urllib.request.Request(url, headers=NYFED_HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        log.error(f"[NY Fed] 요청 실패 {url}: {e}")
        return None


def fetch_nyfed_rate(series: str) -> dict | None:
    """
    EFFR 또는 SOFR 최신 값을 가져옵니다.
    EFFR은 targetRateFrom / targetRateTo(정책 범위)도 함께 반환합니다.
    :param series: 'effr' 또는 'sofr'
    :return: {'date', 'rate', 'volume_billions', ?'target_low', ?'target_high'} 또는 None
    """
    path_map = {
        "effr": f"{NYFED_BASE}/rates/unsecured/effr/last/1.json",
        "sofr": f"{NYFED_BASE}/rates/secured/sofr/last/1.json",
    }
    url = path_map.get(series)
    if not url:
        return None

    data = _nyfed_get(url)
    if not data:
        return None

    rates = data.get("refRates", [])
    if not rates:
        return None

    r = rates[0]
    result = {
        "date": r.get("effectiveDate"),
        "rate": r.get("percentRate"),
        "volume_billions": r.get("volumeInBillions"),
    }
    if series == "effr":
        result["target_low"]  = r.get("targetRateFrom")
        result["target_high"] = r.get("targetRateTo")
    return result


def fetch_nyfed_rate_history(series: str, n: int = 90) -> list | None:
    """
    EFFR / SOFR 최근 N일치 이력을 가져옵니다.
    EFFR은 정책 범위(target_low / target_high)도 포함합니다.
    """
    path_map = {
        "effr": f"{NYFED_BASE}/rates/unsecured/effr/last/{n}.json",
        "sofr": f"{NYFED_BASE}/rates/secured/sofr/last/{n}.json",
    }
    url = path_map.get(series)
    if not url:
        return None

    data = _nyfed_get(url)
    if not data:
        return None

    result = []
    for r in data.get("refRates", []):
        item = {
            "date": r.get("effectiveDate"),
            "rate": r.get("percentRate"),
            "volume_billions": r.get("volumeInBillions"),
        }
        if series == "effr":
            item["target_low"]  = r.get("targetRateFrom")
            item["target_high"] = r.get("targetRateTo")
        result.append(item)
    log.info(f"[NY Fed] {series.upper()} 이력 {len(result)}건 수신 (last {n}일)")
    return result


def fetch_nyfed_rrp() -> dict | None:
    """
    역레포(RRP) 최신 데이터를 가져옵니다.
    :return: {'date', 'total_amt_billions'} 또는 None
    """
    today = date_type.today()
    start = (today - timedelta(days=7)).isoformat()
    end = today.isoformat()
    url = (
        f"{NYFED_BASE}/rp/reverserepo/propositions/search.json"
        f"?startDate={start}&endDate={end}"
    )
    data = _nyfed_get(url)
    if not data:
        return None

    ops = data.get("repo", {}).get("operations", [])
    if not ops:
        return None

    # 최신 영업일 첫 번째 항목
    latest = ops[0]
    raw_amt = latest.get("totalAmtAccepted", 0)
    return {
        "date": latest.get("operationDate"),
        "total_amt_billions": round(raw_amt / 1e9, 4),
    }


def upsert_nyfed_rate(table: str, record: dict) -> int:
    """EFFR/SOFR 데이터를 DB에 저장합니다. EFFR은 target_low/high 포함."""
    if not record or not record.get("date") or record.get("rate") is None:
        return 0
    conn = get_db()
    if table == "nyfed_effr":
        cursor = conn.execute(
            "INSERT OR IGNORE INTO nyfed_effr "
            "(date, rate, volume_billions, target_low, target_high, fetched_at) VALUES (?, ?, ?, ?, ?, ?)",
            (record["date"], record["rate"], record.get("volume_billions"),
             record.get("target_low"), record.get("target_high"), now_kst_str()),
        )
    else:
        cursor = conn.execute(
            f"INSERT OR IGNORE INTO {table} (date, rate, volume_billions, fetched_at) VALUES (?, ?, ?, ?)",
            (record["date"], record["rate"], record.get("volume_billions"), now_kst_str()),
        )
    inserted = cursor.rowcount
    conn.commit()
    conn.close()
    log.info(f"[{table}] 신규 저장: {inserted}건 (date={record['date']})")
    return inserted


def upsert_nyfed_rate_history(table: str, records: list) -> int:
    """EFFR/SOFR 이력 데이터를 일괄 저장합니다."""
    if not records:
        return 0
    conn = get_db()
    inserted = 0
    fetched_at = now_kst_str()
    for rec in records:
        date = rec.get("date")
        rate = rec.get("rate")
        if not date or rate is None:
            continue
        if table == "nyfed_effr":
            # OR REPLACE: 기존 레코드가 있어도 target_low/high를 갱신
            cursor = conn.execute(
                "INSERT OR REPLACE INTO nyfed_effr "
                "(date, rate, volume_billions, target_low, target_high, fetched_at) VALUES (?, ?, ?, ?, ?, ?)",
                (date, rate, rec.get("volume_billions"),
                 rec.get("target_low"), rec.get("target_high"), fetched_at),
            )
        else:
            cursor = conn.execute(
                f"INSERT OR IGNORE INTO {table} (date, rate, volume_billions, fetched_at) VALUES (?, ?, ?, ?)",
                (date, rate, rec.get("volume_billions"), fetched_at),
            )
        if cursor.rowcount > 0:
            inserted += 1
    conn.commit()
    conn.close()
    log.info(f"[{table}] 이력 저장: {inserted}건 신규")
    return inserted


def upsert_nyfed_rrp(record: dict) -> int:
    """RRP 데이터를 DB에 저장합니다."""
    if not record or not record.get("date") or record.get("total_amt_billions") is None:
        return 0
    conn = get_db()
    cursor = conn.execute(
        "INSERT OR IGNORE INTO nyfed_rrp (date, total_amt_billions, fetched_at) VALUES (?, ?, ?)",
        (record["date"], record["total_amt_billions"], now_kst_str()),
    )
    inserted = cursor.rowcount
    conn.commit()
    conn.close()
    log.info(f"[nyfed_rrp] 신규 저장: {inserted}건 (date={record['date']})")
    return inserted


# ── MOVE Index 수집 (yfinance ^MOVE) ─────────────────────────────

def fetch_move_index(days: int = 35) -> list[dict]:
    """
    Yahoo Finance에서 ^MOVE (ICE BofA MOVE Index) 히스토리를 수집합니다.
    반환: [{'date': 'YYYY-MM-DD', 'value': float}, ...]  날짜 오름차순
    """
    try:
        import yfinance as yf
        t    = yf.Ticker("^MOVE")
        hist = t.history(period="3mo")
        if hist.empty:
            log.warning("[MOVE] yfinance 응답 없음")
            return []
        rows = []
        for ts, row in hist.iterrows():
            d = ts.date().isoformat()
            v = round(float(row["Close"]), 4)
            rows.append({"date": d, "value": v})
        rows.sort(key=lambda x: x["date"])
        log.info(f"[MOVE] {len(rows)}건 수집 (최신: {rows[-1]['date']} = {rows[-1]['value']:.2f})")
        return rows
    except Exception as exc:
        log.error(f"[MOVE] 수집 오류: {exc}")
        return []


def upsert_move_index(rows: list[dict]) -> int:
    """MOVE 지수를 DB에 저장합니다. 반환: 신규 저장 건수."""
    if not rows:
        return 0
    conn  = get_db()
    saved = 0
    for r in rows:
        cur = conn.execute(
            "INSERT OR IGNORE INTO move_index (date, value, fetched_at) VALUES (?,?,?)",
            (r["date"], r["value"], now_kst_str()),
        )
        saved += cur.rowcount
    conn.commit()
    conn.close()
    log.info(f"[move_index] 신규 저장: {saved}건")
    return saved


def refresh_move() -> int:
    """MOVE 지수 수집 → DB 저장 → 텔레그램 알람 체크."""
    rows = fetch_move_index()
    count = upsert_move_index(rows)
    if rows:
        telegram_alerts.record_success("move_index")
        if count > 0 and len(rows) >= 2:
            try:
                telegram_alerts.check_and_alert(
                    "move_index", rows[-1]["value"], rows[-2]["value"]
                )
            except Exception as exc:
                log.error(f"[MOVE] 알람 체크 오류: {exc}")
    else:
        telegram_alerts.record_error("move_index", "yfinance ^MOVE 응답 없음")
    return count


# ── CBOE SKEW Index 수집 (yfinance ^SKEW) ────────────────────────

def fetch_skew_index(days: int = 35) -> list[dict]:
    """Yahoo Finance에서 ^SKEW (CBOE SKEW Index) 히스토리를 수집합니다."""
    try:
        import yfinance as yf
        t    = yf.Ticker("^SKEW")
        hist = t.history(period="3mo")
        if hist.empty:
            log.warning("[SKEW] yfinance 응답 없음")
            return []
        rows = []
        for ts, row in hist.iterrows():
            d = ts.date().isoformat()
            v = round(float(row["Close"]), 4)
            rows.append({"date": d, "value": v})
        rows.sort(key=lambda x: x["date"])
        log.info(f"[SKEW] {len(rows)}건 수집 (최신: {rows[-1]['date']} = {rows[-1]['value']:.2f})")
        return rows
    except Exception as exc:
        log.error(f"[SKEW] 수집 오류: {exc}")
        return []


def upsert_skew_index(rows: list[dict]) -> int:
    """SKEW 지수를 DB에 저장합니다."""
    if not rows:
        return 0
    conn  = get_db()
    saved = 0
    for r in rows:
        cur = conn.execute(
            "INSERT OR IGNORE INTO skew_index (date, value, fetched_at) VALUES (?,?,?)",
            (r["date"], r["value"], now_kst_str()),
        )
        saved += cur.rowcount
    conn.commit()
    conn.close()
    log.info(f"[skew_index] 신규 저장: {saved}건")
    return saved


def refresh_skew() -> int:
    """SKEW 지수 수집 → DB 저장."""
    rows  = fetch_skew_index()
    count = upsert_skew_index(rows)
    if not rows:
        telegram_alerts.record_error("skew_index", "yfinance ^SKEW 응답 없음")
    else:
        telegram_alerts.record_success("skew_index")
    return count


# ── Stage 1: Single-B OAS / IG OAS / LQD (Layer 2 응급 충실화) ──────

def _upsert_oas_table(table: str, rows: list, value_key: str = "oas_bp") -> int:
    """OAS 테이블 공통 upsert (single_b_oas, ig_oas)."""
    if not rows:
        return 0
    conn = get_db()
    saved = 0
    for r in rows:
        try:
            v = float(r.get("value", 0))
            if v <= 0 or r.get("value") == ".":
                continue
            # FRED는 % 단위 → bp 변환
            oas_bp = round(v * 100, 2)
            cur = conn.execute(
                f"INSERT OR IGNORE INTO {table} (date, oas_bp, fetched_at) VALUES (?,?,?)",
                (r["date"], oas_bp, now_kst_str()),
            )
            saved += cur.rowcount
        except Exception:
            continue
    conn.commit()
    conn.close()
    log.info(f"[{table}] 신규 저장: {saved}건")
    return saved


def refresh_single_b_oas() -> int:
    """FRED BAMLH0A2HYB (Single-B US HY OAS) 수집 → DB 저장.

    v1.0 문서 카테고리 3.5.1 / Layer 2 가중 7pt
    임계: Normal <350bp / Watch 350-450bp / Stress 450-600bp / Crisis >600bp

    주의: BAMLH0A2HYBEY (Effective Yield) 와 혼동 금지.
    - BAMLH0A2HYB  = OAS (스프레드만, ~3.19% = 319bp) ← 올바른 시리즈
    - BAMLH0A2HYBEY = Effective Yield (국채금리+OAS 합계, ~7.08% = 708bp) ← 오류
    """
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM single_b_oas").fetchone()[0]
    conn.close()

    limit = 1000 if count == 0 else 10
    if count == 0:
        log.info("[Single-B OAS] DB 비어있음 — 이력 로드 중...")

    rows = fetch_fred_observations("BAMLH0A2HYB", limit=limit)
    if rows:
        saved = _upsert_oas_table("single_b_oas", rows)
        if count == 0:
            log.info(f"[Single-B OAS] 초기 로드 완료: {saved}건")
        telegram_alerts.record_success("single_b_oas")
        return saved
    log.warning("[Single-B OAS] FRED 응답 없음")
    telegram_alerts.record_error("single_b_oas", "FRED BAMLH0A2HYB 응답 없음")
    return 0


def refresh_ig_oas() -> int:
    """FRED BAMLC0A0CM (IG US Corporate OAS) 수집 → DB 저장.

    v1.0 문서 카테고리 3.5.1 / Layer 2 가중 3pt
    임계: Normal <100bp / Watch 100-130bp / Stress 130-180bp / Crisis >180bp
    """
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM ig_oas").fetchone()[0]
    conn.close()

    limit = 1000 if count == 0 else 10
    if count == 0:
        log.info("[IG OAS] DB 비어있음 — 이력 로드 중...")

    rows = fetch_fred_observations("BAMLC0A0CM", limit=limit)
    if rows:
        saved = _upsert_oas_table("ig_oas", rows)
        if count == 0:
            log.info(f"[IG OAS] 초기 로드 완료: {saved}건")
        telegram_alerts.record_success("ig_oas")
        return saved
    log.warning("[IG OAS] FRED 응답 없음")
    telegram_alerts.record_error("ig_oas", "FRED BAMLC0A0CM 응답 없음")
    return 0


def refresh_lqd() -> int:
    """LQD ETF 일간 가격 + 변화율 수집 → DB 저장 (yfinance).

    v1.0 문서 카테고리 3.5.2 / Layer 2 가중 2pt
    임계(daily_change_pct): Normal >-0.5% / Watch -0.5~-1% / Stress -1~-2% / Crisis <-2%
    Direction: inverse (음수 클수록 stress)
    """
    if not _yf_available:
        log.warning("[LQD] yfinance 미설치 — 스킵")
        return 0
    try:
        import yfinance as yf
        t = yf.Ticker("LQD")

        # DB 비어있으면 3년 이력 전체 로드, 있으면 최근 10일만 갱신
        conn_chk = get_db()
        existing = conn_chk.execute("SELECT COUNT(*) FROM lqd_prices").fetchone()[0]
        conn_chk.close()
        if existing == 0:
            log.info("[LQD] DB 비어있음 — 이력 로드 중 (2022-01-01 ~)")
            hist = t.history(start="2022-01-01", interval="1d")
        else:
            hist = t.history(period="10d")

        if hist.empty:
            log.warning("[LQD] yfinance 응답 없음")
            telegram_alerts.record_error("lqd_prices", "yfinance LQD 응답 없음")
            return 0

        conn  = get_db()
        saved = 0
        prev_close = None
        for ts, row in hist.iterrows():
            d     = ts.date().isoformat()
            close = round(float(row["Close"]), 4)
            chg_pct = None
            if prev_close is not None and prev_close > 0:
                chg_pct = round((close - prev_close) / prev_close * 100, 4)
            prev_close = close
            cur = conn.execute(
                """INSERT OR IGNORE INTO lqd_prices
                   (date, close_price, daily_change_pct, fetched_at)
                   VALUES (?,?,?,?)""",
                (d, close, chg_pct, now_kst_str()),
            )
            saved += cur.rowcount

        conn.commit()
        conn.close()
        log.info(f"[LQD] {saved}건 저장")
        telegram_alerts.record_success("lqd_prices")
        return saved
    except Exception as exc:
        log.error(f"[LQD] 수집 오류: {exc}")
        telegram_alerts.record_error("lqd_prices", str(exc))
        return 0


def refresh_hyg() -> int:
    """HYG ETF 일간 가격 + 변화율 수집 → DB 저장 (yfinance).

    v1.0 문서 카테고리 3.5.3 / Layer 2 가중 4pt
    임계(daily_change_pct): Normal >-0.3% / Watch -0.3~-0.7% / Stress -0.7~-1.5% / Crisis <-1.5%
    Direction: inverse (음수가 클수록 stress)
    5day 변화율 (cap 3pt): Normal <1% / Watch 1~2.5% / Stress 2.5~5% / Crisis >5% (절댓값 기준)
    """
    if not _yf_available:
        log.warning("[HYG] yfinance 미설치 — 스킵")
        return 0
    try:
        import yfinance as yf
        t = yf.Ticker("HYG")
        conn_chk = get_db()
        existing = conn_chk.execute("SELECT COUNT(*) FROM hyg_prices").fetchone()[0]
        conn_chk.close()
        if existing == 0:
            log.info("[HYG] DB 비어있음 — 이력 로드 중 (2022-01-01 ~)")
            hist = t.history(start="2022-01-01", interval="1d")
        else:
            hist = t.history(period="10d")
        if hist.empty:
            log.warning("[HYG] yfinance 응답 없음")
            telegram_alerts.record_error("hyg_prices", "yfinance HYG 응답 없음")
            return 0

        conn  = get_db()
        saved = 0
        prev_close = None
        for ts, row in hist.iterrows():
            d     = ts.date().isoformat()
            close = round(float(row["Close"]), 4)
            chg_pct = None
            if prev_close is not None and prev_close > 0:
                chg_pct = round((close - prev_close) / prev_close * 100, 4)
            prev_close = close
            cur = conn.execute(
                """INSERT OR IGNORE INTO hyg_prices
                   (date, close_price, daily_change_pct, fetched_at)
                   VALUES (?,?,?,?)""",
                (d, close, chg_pct, now_kst_str()),
            )
            saved += cur.rowcount

        conn.commit()
        conn.close()
        log.info(f"[HYG] {saved}건 저장")
        telegram_alerts.record_success("hyg_prices")
        return saved
    except Exception as exc:
        log.error(f"[HYG] 수집 오류: {exc}")
        telegram_alerts.record_error("hyg_prices", str(exc))
        return 0


# ── Discount Window / TGA / SOFR90d (FRED API) ───────────────────

def refresh_discount_window() -> int:
    """FRED WLCFLPCL (Primary Credit 잔액, $백만) 수집 → DB 저장."""
    rows = fetch_fred_observations("WLCFLPCL", limit=60)
    if rows:
        count = upsert_observations("discount_window", rows)
        log.info(f"[Discount Window] {count}건 신규 저장")
        return count
    log.warning("[Discount Window] FRED 응답 없음")
    return 0


def refresh_tga() -> int:
    """FRED WTREGEN (TGA 잔액, $백만) 수집 → DB 저장."""
    rows = fetch_fred_observations("WTREGEN", limit=60)
    if rows:
        count = upsert_observations("tga_balance", rows)
        log.info(f"[TGA] {count}건 신규 저장")
        return count
    log.warning("[TGA] FRED 응답 없음")
    return 0


def refresh_sofr_90d() -> int:
    """FRED SOFR90DAYAVG (SOFR 90일 평균, %) 수집 → DB 저장."""
    rows = fetch_fred_observations("SOFR90DAYAVG", limit=60)
    if rows:
        count = upsert_observations("sofr_90d", rows)
        log.info(f"[SOFR 90d] {count}건 신규 저장")
        return count
    log.warning("[SOFR 90d] FRED 응답 없음")
    return 0


# ── RP / RRP 오퍼레이션 결과 수집 ────────────────────────────────

def _fetch_one_rprp(kind: str) -> dict | None:
    """
    kind: 'reverserepo'(RRP) 또는 'repo'(RP)
    NY Fed /api/rp/{kind}/results/lastTwoWeeks.json 에서 최신 1건 반환
    반환 형식: {op_date, total_accepted_bil, total_submitted_bil} 또는 None
    """
    url  = f"{NYFED_BASE}/rp/{kind}/results/lastTwoWeeks.json"
    data = _nyfed_get(url)
    if not data:
        log.warning(f"[{kind.upper()}] API 응답 없음")
        return None

    # 응답 구조 탐색: repo.operations 또는 최상위 operations
    repo_obj = data.get("repo", data)
    ops = repo_obj.get("operations") or []
    if not ops:
        # 일부 응답은 propositions 키에 들어오기도 함
        ops = repo_obj.get("propositions") or []
    if not ops:
        log.warning(f"[{kind.upper()}] 오퍼레이션 데이터 없음 — keys: {list(data.keys())}")
        return None

    # 날짜 기준 최신 오퍼레이션 1건
    ops_sorted = sorted(ops, key=lambda x: x.get("operationDate") or "", reverse=True)
    op = ops_sorted[0]
    op_date = op.get("operationDate")

    # 금액 필드: totalAmtAccepted / totalAmtSubmitted (달러)
    raw_accepted  = op.get("totalAmtAccepted")  or op.get("totalAccepted")  or 0
    raw_submitted = op.get("totalAmtSubmitted") or op.get("totalSubmitted") or 0

    rec = {
        "op_date":             op_date,
        "total_accepted_bil":  round(float(raw_accepted)  / 1e9, 4),
        "total_submitted_bil": round(float(raw_submitted) / 1e9, 4),
    }
    log.info(f"[{kind.upper()}] {op_date}: accepted={rec['total_accepted_bil']:.4f}B  submitted={rec['total_submitted_bil']:.4f}B")
    return rec


def fetch_fedop_rprp() -> dict:
    """
    RRP(역레포)와 RP(레포) 최신 오퍼레이션 결과를 각각 수집.
    반환: {'rrp': {...}, 'rp': {...}}
    """
    rrp_rec = _fetch_one_rprp("reverserepo")
    rp_rec  = _fetch_one_rprp("repo")
    return {"rrp": rrp_rec, "rp": rp_rec}


def upsert_fedop_rprp(rrp_rec: dict | None, rp_rec: dict | None) -> None:
    """RRP / RP 오퍼레이션 결과를 DB에 저장합니다."""
    conn = get_db()
    for table, rec in [("fedop_rrp", rrp_rec), ("fedop_rp", rp_rec)]:
        if not rec or not rec.get("op_date"):
            continue
        conn.execute(
            f"INSERT OR REPLACE INTO {table} "
            "(op_date, total_accepted_bil, total_submitted_bil, fetched_at) VALUES (?,?,?,?)",
            (rec["op_date"], rec["total_accepted_bil"], rec["total_submitted_bil"], now_kst_str()),
        )
        log.info(f"[{table}] 저장: {rec['op_date']}")
    conn.commit()
    conn.close()


# ── Fed Operation 데이터 수집 ──────────────────────────────────

FEDOP_AMBS_URL    = f"{NYFED_BASE}/ambs/all/results/details/last/30.json"
FEDOP_SECLEND_URL = f"{NYFED_BASE}/seclending/all/results/details/last/30.json"
FEDOP_TSY_URL     = f"{NYFED_BASE}/tsy/all/results/details/last/30.json"
FEDOP_SOMA_URL    = f"{NYFED_BASE}/soma/summary.json"


def fetch_fedop_soma() -> list[dict]:
    """SOMA 주간 보유 현황을 반환합니다. 반환: [{asof_date, total_bil, mbs_bil}, ...]"""
    data = _nyfed_get(FEDOP_SOMA_URL)
    if not data:
        return []
    items = data.get("soma", {}).get("summary", [])
    result = []
    for it in items:
        try:
            total = float(it.get("total") or 0)
            mbs   = float(it.get("mbs")   or 0)
            result.append({
                "asof_date": it["asOfDate"],
                "total_bil": round(total / 1e9, 4),
                "mbs_bil":   round(mbs   / 1e9, 4),
            })
        except Exception:
            continue
    return result


def fetch_fedop_ambs() -> list[dict]:
    """AMBS 낙찰 결과를 반환합니다. 반환: [{operation_id, op_date, direction, accepted_bil, op_type}, ...]"""
    data = _nyfed_get(FEDOP_AMBS_URL)
    if not data:
        return []
    auctions = data.get("ambs", {}).get("auctions", [])
    result = []
    for op in auctions:
        try:
            accepted_str  = op.get("totalAcceptedOrigFace") or op.get("totalAcceptedCurrFace") or "0"
            submitted_str = op.get("totalSubmittedOrigFace") or op.get("totalSubmittedCurrFace") or "0"
            accepted_bil  = round(float(accepted_str)  / 1e9, 6)
            submitted_bil = round(float(submitted_str) / 1e9, 6)
            result.append({
                "operation_id": op["operationId"],
                "op_date":      op["operationDate"],
                "direction":    op.get("operationDirection", ""),
                "accepted_bil": accepted_bil,
                "submitted_bil": submitted_bil,
                "op_type":      op.get("operationType", ""),
            })
        except Exception:
            continue
    return result


def fetch_fedop_seclending() -> list[dict]:
    """증권대여 낙찰 결과를 반환합니다. 반환: [{operation_id, op_date, accepted_bil, submitted_bil}, ...]"""
    data = _nyfed_get(FEDOP_SECLEND_URL)
    if not data:
        return []
    ops = data.get("seclending", {}).get("operations", [])
    result = []
    for op in ops:
        try:
            par_accepted  = float(op.get("totalParAmtAccepted")  or 0)
            par_submitted = float(op.get("totalParAmtSubmitted") or 0)
            result.append({
                "operation_id":  op["operationId"],
                "op_date":       op["operationDate"],
                "par_accepted_bil": round(par_accepted  / 1e9, 6),
                "accepted_bil":  round(par_accepted  / 1e9, 6),
                "submitted_bil": round(par_submitted / 1e9, 6),
            })
        except Exception:
            continue
    return result


def fetch_fedop_tsy() -> list[dict]:
    """국채 아웃라이트 낙찰 결과를 반환합니다. 반환: [{operation_id, op_date, direction, accepted_bil, submitted_bil, op_type}, ...]"""
    data = _nyfed_get(FEDOP_TSY_URL)
    if not data:
        return []
    auctions = data.get("treasury", {}).get("auctions", [])
    result = []
    for op in auctions:
        try:
            accepted  = float(op.get("totalParAmtAccepted")  or 0)
            submitted = float(op.get("totalParAmtSubmitted") or 0)
            result.append({
                "operation_id":  op["operationId"],
                "op_date":       op["operationDate"],
                "direction":     op.get("operationDirection", ""),
                "accepted_bil":  round(accepted  / 1e9, 6),
                "submitted_bil": round(submitted / 1e9, 6),
                "op_type":       op.get("operationType", ""),
            })
        except Exception:
            continue
    return result


def upsert_fedop_soma(records: list[dict]) -> int:
    """SOMA 주간 데이터를 DB에 저장합니다."""
    if not records:
        return 0
    conn  = get_db()
    now   = now_kst_str()
    count = 0
    for r in records:
        cur = conn.execute(
            "INSERT OR IGNORE INTO fedop_soma (asof_date, total_bil, mbs_bil, fetched_at) VALUES (?,?,?,?)",
            (r["asof_date"], r["total_bil"], r.get("mbs_bil"), now),
        )
        count += cur.rowcount
    conn.commit()
    conn.close()
    log.info(f"[fedop_soma] 신규 저장: {count}건")
    return count


def upsert_fedop_ambs(records: list[dict]) -> int:
    conn  = get_db()
    now   = now_kst_str()
    count = 0
    for r in records:
        cur = conn.execute(
            "INSERT OR REPLACE INTO fedop_ambs "
            "(operation_id, op_date, direction, accepted_bil, submitted_bil, op_type, fetched_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (r["operation_id"], r["op_date"], r.get("direction"),
             r.get("accepted_bil"), r.get("submitted_bil"), r.get("op_type"), now),
        )
        count += cur.rowcount
    conn.commit()
    conn.close()
    log.info(f"[fedop_ambs] 저장: {count}건 (submitted_bil 포함)")
    return count


def upsert_fedop_seclending(records: list[dict]) -> int:
    conn  = get_db()
    now   = now_kst_str()
    count = 0
    for r in records:
        cur = conn.execute(
            "INSERT OR REPLACE INTO fedop_seclending "
            "(operation_id, op_date, par_accepted_bil, accepted_bil, submitted_bil, fetched_at) "
            "VALUES (?,?,?,?,?,?)",
            (r["operation_id"], r["op_date"],
             r.get("par_accepted_bil"), r.get("accepted_bil"),
             r.get("submitted_bil"), now),
        )
        count += cur.rowcount
    conn.commit()
    conn.close()
    log.info(f"[fedop_seclending] 저장: {count}건 (submitted_bil 포함)")
    return count


def upsert_fedop_tsy(records: list[dict]) -> int:
    conn  = get_db()
    now   = now_kst_str()
    count = 0
    for r in records:
        cur = conn.execute(
            "INSERT OR REPLACE INTO fedop_tsy "
            "(operation_id, op_date, direction, accepted_bil, submitted_bil, op_type, fetched_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (r["operation_id"], r["op_date"], r.get("direction"),
             r.get("accepted_bil"), r.get("submitted_bil"), r.get("op_type"), now),
        )
        count += cur.rowcount
    conn.commit()
    conn.close()
    log.info(f"[fedop_tsy] 신규 저장: {count}건")
    return count


def refresh_fedop():
    """Fed Operation 지표(SOMA, AMBS, SecLending, TSY)를 갱신합니다."""
    log.info("[FedOp] 갱신 시작")
    soma = fetch_fedop_soma()
    if soma:
        upsert_fedop_soma(soma)
    ambs = fetch_fedop_ambs()
    if ambs:
        upsert_fedop_ambs(ambs)
    seclend = fetch_fedop_seclending()
    if seclend:
        upsert_fedop_seclending(seclend)
    tsy = fetch_fedop_tsy()
    if tsy:
        upsert_fedop_tsy(tsy)
    log.info("[FedOp] 갱신 완료")


def refresh_nyfed():
    """NY Fed 전체 지표(EFFR, SOFR, RRP, FedOp)를 한 번에 갱신합니다."""
    log.info(f"[NY Fed] 갱신 시작 ({now_kst_str()})")
    nyfed_ok = True
    for series, table in [("effr", "nyfed_effr"), ("sofr", "nyfed_sofr")]:
        rec = fetch_nyfed_rate(series)
        if rec:
            upsert_nyfed_rate(table, rec)
            telegram_alerts.record_success(f"nyfed_{series}")
            # ── 알람 체크: 직전 2개 레코드 비교 ────────────────
            try:
                conn = get_db()
                rows = conn.execute(
                    f"SELECT rate FROM {table} ORDER BY date DESC LIMIT 2"
                ).fetchall()
                conn.close()
                if len(rows) >= 2:
                    telegram_alerts.check_and_alert(series, rows[0]["rate"], rows[1]["rate"])
            except Exception as exc:
                log.error(f"[NY Fed] {series} 알람 체크 오류: {exc}")
        else:
            log.warning(f"[NY Fed] {series.upper()} 갱신 실패")
            telegram_alerts.record_error(f"nyfed_{series}", f"{series.upper()} API 응답 없음")
            nyfed_ok = False

    rrp = fetch_nyfed_rrp()
    if rrp:
        upsert_nyfed_rrp(rrp)
    else:
        log.warning("[NY Fed] RRP 갱신 실패")

    refresh_fedop()
    log.info(f"[NY Fed] 갱신 완료 ({now_kst_str()})")


# ── 텔레그램 알람 (telegram_alerts 모듈로 위임) ─────────────────
# 구 check_telegram_alert 함수는 telegram_alerts.py로 이전되었습니다.
# 기존 라우트 코드에서 참조하는 "alert" 키는 None으로 대체됩니다.


# ── 인증 미들웨어: 보호가 필요하지 않은 경로 목록 ─────────────
_PUBLIC_PREFIXES = ("/auth/", "/health", "/static/")

@app.before_request
def require_login():
    """로그인되지 않은 사용자는 /auth/login으로 리디렉션합니다."""
    # 공개 경로는 통과
    if any(request.path.startswith(p) for p in _PUBLIC_PREFIXES):
        return None
    if not current_user.is_authenticated:
        return redirect(f"/auth/login?next={request.path}")
    return None


def _admin_only(f):
    """관리자 전용 라우트 데코레이터."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            return jsonify({"error": "관리자 권한이 필요합니다."}), 403
        return f(*args, **kwargs)
    return decorated


# ── 관리자 API ─────────────────────────────────────────────────

@app.route("/admin/users")
@_admin_only
def admin_users():
    """관리자 전용: 전체 사용자 로그인 이력을 반환합니다."""
    conn = get_db()
    rows = conn.execute(
        "SELECT email, name, first_login, last_login, last_ip, login_count "
        "FROM users ORDER BY last_login DESC"
    ).fetchall()
    conn.close()
    return jsonify({
        "users": [dict(r) for r in rows],
        "total": len(rows),
    })


# ── Flask 라우트 ───────────────────────────────────────────────

@app.route("/")
def index():
    resp = make_response(render_template("index.html"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp


def _parse_fetched_at(raw: str) -> str:
    """fetched_at 문자열을 KST 포맷으로 통일합니다."""
    if not raw:
        return None
    if "KST" in raw:
        return raw
    try:
        utc_dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if utc_dt.tzinfo is None:
            utc_dt = pytz.utc.localize(utc_dt)
        return utc_dt.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S KST")
    except Exception:
        return raw


def _build_indicator_payload(series_id: str) -> dict:
    """지표 하나의 데이터 페이로드를 만들어 반환합니다."""
    meta = INDICATORS[series_id]
    conn = get_db()
    rows = conn.execute(
        f"SELECT date, value, fetched_at FROM {meta['table']} ORDER BY date DESC LIMIT 60"
    ).fetchall()
    conn.close()

    records = [{"date": r["date"], "value": r["value"]} for r in rows]
    records_asc = list(reversed(records))

    current = records[0] if records else None
    previous = records[1] if len(records) > 1 else None

    change = change_pct = last_fetched_kst = None
    alert = None  # 알람은 make_refresh_job 내 스케줄 갱신 시점에 발송됨

    if rows:
        last_fetched_kst = _parse_fetched_at(rows[0]["fetched_at"])

    if current and previous:
        change = round(current["value"] - previous["value"], 4)
        change_pct = round((change / previous["value"]) * 100, 2)

    return {
        "series_id": series_id,
        "indicator_name": meta["name"],
        "description": meta.get("description", ""),
        "color": meta.get("color", "#4299e1"),
        "current": current,
        "previous": previous,
        "change": change,
        "change_pct": change_pct,
        "alert": alert,
        "records": records_asc,
        "total_count": len(records_asc),
        "observation_date": current["date"] if current else None,
        "last_fetched_at": last_fetched_kst,
        "next_schedule": _get_next_schedule_str(meta["schedule"]),
    }


@app.route("/data")
def get_data():
    """HY OA Index, A2/P2 CP, AA CP, A2/P2-AA 스프레드를 반환합니다."""
    hy = _build_indicator_payload("BAMLH0A0HYM2")
    cp = _build_indicator_payload("RIFSPPNA2P2D30NB")

    # AA: 수동 입력 테이블에서 조회 (FRED 미지원 — aa_manual 테이블 사용)
    _aa_conn = get_db()
    _aa_rows = _aa_conn.execute(
        "SELECT date, value, entered_at FROM aa_manual ORDER BY date DESC LIMIT 60"
    ).fetchall()
    _aa_conn.close()
    _aa_records  = [{"date": r["date"], "value": r["value"]} for r in _aa_rows]
    _aa_current  = _aa_records[0] if _aa_records else None
    _aa_previous = _aa_records[1] if len(_aa_records) > 1 else None
    _aa_change = _aa_change_pct = None
    if _aa_current and _aa_previous and _aa_previous["value"]:
        _aa_change     = round(_aa_current["value"] - _aa_previous["value"], 4)
        _aa_change_pct = round((_aa_change / _aa_previous["value"]) * 100, 2)
    _aa_entered_at = _parse_fetched_at(_aa_rows[0]["entered_at"]) if _aa_rows else None
    aa = {
        "series_id":        "AA_MANUAL",
        "indicator_name":   "AA 비금융 CP 금리 30일 (수동)",
        "description":      "AA-rated Nonfinancial Commercial Paper 30-Day Rate (수동 입력)",
        "color":            "#68d391",
        "current":          _aa_current,
        "previous":         _aa_previous,
        "change":           _aa_change,
        "change_pct":       _aa_change_pct,
        "alert":            None,
        "records":          list(reversed(_aa_records)),
        "total_count":      len(_aa_records),
        "observation_date": _aa_current["date"] if _aa_current else None,
        "last_fetched_at":  _aa_entered_at,
        "next_schedule":    "수동 입력",
    }

    # ── A2/P2 - AA 스프레드 계산 (단위: bp) ─────────────────────
    spread_current_bp  = None
    spread_change_bp   = None
    spread_change_pct  = None
    spread_records     = []
    SPREAD_THRESHOLD   = 50  # bp

    cp_recs = cp.get("records", []) if cp else []
    aa_recs = aa.get("records", []) if aa else []

    if cp_recs and aa_recs:
        cp_dict = {r["date"]: r["value"] for r in cp_recs}
        aa_dict = {r["date"]: r["value"] for r in aa_recs}
        common  = sorted(set(cp_dict) & set(aa_dict), reverse=True)
        spread_records = [
            {"date": d, "value": round((cp_dict[d] - aa_dict[d]) * 100, 2)}
            for d in common
        ]
        if spread_records:
            spread_current_bp = spread_records[0]["value"]
            if len(spread_records) >= 2:
                prev_bp = spread_records[1]["value"]
                spread_change_bp  = round(spread_current_bp - prev_bp, 2)
                if prev_bp:
                    spread_change_pct = round((spread_change_bp / abs(prev_bp)) * 100, 2)

    return jsonify({
        # 기존 HY 필드 (하위 호환)
        "current": hy["current"],
        "previous": hy["previous"],
        "change": hy["change"],
        "change_pct": hy["change_pct"],
        "alert": hy["alert"],
        "records": hy["records"],
        "total_count": hy["total_count"],
        "observation_date": hy["observation_date"],
        "last_fetched_at": hy["last_fetched_at"],
        "next_schedule": hy["next_schedule"],
        "indicator_name": hy["indicator_name"],
        # A2/P2 CP
        "cp": cp,
        # AA CP (신규)
        "aa": aa,
        # A2/P2 - AA 스프레드 (신규)
        "spread": {
            "current_bp":   spread_current_bp,
            "change_bp":    spread_change_bp,
            "change_pct":   spread_change_pct,
            "records":      spread_records,
            "threshold_bp": SPREAD_THRESHOLD,
            "alert":        spread_current_bp is not None and spread_current_bp > SPREAD_THRESHOLD,
        },
        # Stage 1: Layer 2 신규 지표 최신값
        "single_b_oas":  _credit_latest("single_b_oas", "oas_bp"),
        "ig_oas":        _credit_latest("ig_oas", "oas_bp"),
        "lqd":           _credit_latest_lqd(),
        # Stage 2: HYG ETF
        "hyg":           _credit_latest_hyg(),
        # 공통
        "server_time_kst": now_kst_str(),
    })


def _credit_latest(table: str, val_col: str) -> dict | None:
    """OAS 테이블 최신 2개 레코드를 가져와 변화량 포함 dict 반환."""
    conn = get_db()
    rows = conn.execute(
        f"SELECT date, {val_col} AS value FROM {table} ORDER BY date DESC LIMIT 35"
    ).fetchall()
    conn.close()
    if not rows:
        return None
    latest = {"date": rows[0]["date"], "value": rows[0]["value"]}
    prev   = {"date": rows[1]["date"], "value": rows[1]["value"]} if len(rows) > 1 else None
    change = change_pct = None
    if prev and prev["value"]:
        change     = round(latest["value"] - prev["value"], 2)
        change_pct = round(change / prev["value"] * 100, 2)
    history = [{"date": r["date"], "value": r["value"]} for r in reversed(rows)]
    return {"latest": latest, "prev": prev, "change": change, "change_pct": change_pct, "history": history}


def _credit_latest_lqd() -> dict | None:
    """LQD 최신값 + 일간 변화율 포함 dict 반환."""
    conn = get_db()
    rows = conn.execute(
        "SELECT date, close_price, daily_change_pct FROM lqd_prices ORDER BY date DESC LIMIT 35"
    ).fetchall()
    conn.close()
    if not rows:
        return None
    latest = {"date": rows[0]["date"], "close": rows[0]["close_price"], "change_pct": rows[0]["daily_change_pct"]}
    history = [{"date": r["date"], "close": r["close_price"], "change_pct": r["daily_change_pct"]}
               for r in reversed(rows)]
    return {"latest": latest, "history": history}


def _credit_latest_hyg() -> dict | None:
    """HYG 최신값 + 일간 변화율 + 5일 변화율 포함 dict 반환."""
    conn = get_db()
    rows = conn.execute(
        "SELECT date, close_price, daily_change_pct FROM hyg_prices ORDER BY date DESC LIMIT 35"
    ).fetchall()
    conn.close()
    if not rows:
        return None
    latest = {"date": rows[0]["date"], "close": rows[0]["close_price"], "change_pct": rows[0]["daily_change_pct"]}
    chg_5day = None
    if len(rows) >= 6:
        c0 = rows[0]["close_price"]
        c5 = rows[5]["close_price"]
        if c5 and c5 > 0:
            chg_5day = round((c0 / c5 - 1) * 100, 4)
    history = [{"date": r["date"], "close": r["close_price"], "change_pct": r["daily_change_pct"]}
               for r in reversed(rows)]
    return {"latest": latest, "change_5day": chg_5day, "history": history}


@app.route("/signal-desk")
def signal_desk_data():
    """Signal Desk: 최신 TMRS 점수 + 이력 + prev/week snapshot 반환."""
    conn = get_db()
    latest = conn.execute(
        "SELECT * FROM tmrs_scores ORDER BY calculated_at DESC LIMIT 1"
    ).fetchone()
    history = conn.execute(
        "SELECT calculated_at, total_score, total_tier FROM tmrs_scores ORDER BY calculated_at DESC LIMIT 30"
    ).fetchall()
    # prev/week snapshot 추출 — tmrs_scores 이력에서 날짜 기준 탐색
    recent_snaps = conn.execute(
        "SELECT calculated_at, snapshot FROM tmrs_scores ORDER BY calculated_at DESC LIMIT 60"
    ).fetchall()
    conn.close()

    prev_snapshot: dict = {}
    week_snapshot: dict = {}
    if latest and recent_snaps:
        latest_date = latest["calculated_at"][:10]
        # prev: 가장 최근의 다른 날 snapshot
        for row in recent_snaps[1:]:
            if row["calculated_at"][:10] != latest_date:
                prev_snapshot = json.loads(row["snapshot"] or "{}")
                break
        # week: 7일 전 날짜에 가장 가까운 snapshot
        try:
            target = (datetime.strptime(latest_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
            best, best_diff = {}, None
            for row in recent_snaps:
                d = abs((datetime.strptime(row["calculated_at"][:10], "%Y-%m-%d")
                         - datetime.strptime(target, "%Y-%m-%d")).days)
                if best_diff is None or d < best_diff:
                    best_diff, best = d, json.loads(row["snapshot"] or "{}")
            week_snapshot = best
        except Exception:
            pass

    if latest:
        tiers    = json.loads(latest["indicator_tiers"] or "{}")
        snapshot = json.loads(latest["snapshot"] or "{}")
        result = {
            "total_score":    latest["total_score"],
            "total_tier":     latest["total_tier"],
            "l1_score":       latest["l1_score"],
            "l2_score":       latest["l2_score"],
            "l3_score":       latest["l3_score"],
            "div_score":      latest["div_score"],
            "inverse_turkey": bool(latest["inverse_turkey"]),
            "interpretation": latest["interpretation"],
            "calculated_at":  latest["calculated_at"],
            "trigger":        latest["trigger"],
            "indicator_tiers":   tiers,
            "snapshot":          snapshot,
            "prev_snapshot":     prev_snapshot,
            "week_snapshot":     week_snapshot,
            "tier_meta":         _TIER_META,
            "interpretations":   INDICATOR_INTERPRETATIONS,
            "thresholds":        INDICATOR_THRESHOLDS,
            "history":           [dict(r) for r in history],
        }
    else:
        result = {"total_score": None, "calculated_at": None, "history": []}

    return jsonify(result)


@app.route("/indicator/<key>/timeseries")
def indicator_timeseries(key: str):
    """단일 지표의 30일 시계열 반환 — tmrs_scores.snapshot JSON 이력에서 추출."""
    days = request.args.get("days", 30, type=int)
    days = max(7, min(90, days))

    conn = get_db()
    rows = conn.execute(
        "SELECT calculated_at, snapshot FROM tmrs_scores ORDER BY calculated_at DESC LIMIT ?",
        (days * 4,),   # 하루 여러 번 계산 가능하므로 버퍼
    ).fetchall()
    conn.close()

    # 날짜별 중복 제거 (가장 최신 1건 유지)
    seen: dict = {}
    for row in rows:
        date = row["calculated_at"][:10]
        if date not in seen:
            snap = json.loads(row["snapshot"] or "{}")
            if key in snap:
                seen[date] = {
                    "date":  date,
                    "ts":    row["calculated_at"],
                    "value": snap[key].get("value"),
                    "tier":  snap[key].get("tier"),
                }

    result = sorted(seen.values(), key=lambda r: r["date"])[-days:]
    return jsonify(result)


@app.route("/signal-desk/recalculate", methods=["POST"])
def signal_desk_recalculate():
    """Signal Desk: 수동 TMRS 즉시 재계산."""
    if not current_user.is_authenticated:
        return jsonify({"error": "로그인이 필요합니다."}), 401
    try:
        result = _compute_tmrs(trigger="manual")
        return jsonify({"ok": True, "total_score": result["total_score"],
                        "total_tier": result["total_tier"],
                        "calculated_at": result["calculated_at"]})
    except Exception as e:
        log.error(f"[TMRS] 수동 재계산 오류: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/aa-input", methods=["POST"])
def aa_input():
    """AA 비금융 CP 금리 30일 수동 입력 엔드포인트."""
    if not current_user.is_authenticated:
        return jsonify({"error": "로그인이 필요합니다."}), 401
    body = request.get_json(silent=True) or {}
    date_str  = body.get("date", "").strip()
    value_str = str(body.get("value", "")).strip()
    note      = body.get("note", "").strip()
    if not date_str or not value_str:
        return jsonify({"error": "date와 value 필드가 필요합니다."}), 400
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "날짜 형식이 잘못됐습니다 (YYYY-MM-DD)."}), 400
    try:
        value = float(value_str)
    except ValueError:
        return jsonify({"error": "value는 숫자여야 합니다."}), 400
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO aa_manual (date, value, note, entered_at) VALUES (?, ?, ?, ?)",
        (date_str, value, note or None, now_kst_str()),
    )
    conn.commit()
    conn.close()
    log.info(f"[AA 수동] {date_str} = {value} (입력자: {getattr(current_user, 'email', 'unknown')})")
    return jsonify({"ok": True, "date": date_str, "value": value})


@app.route("/records")
def get_records():
    meta = INDICATORS["BAMLH0A0HYM2"]
    conn = get_db()
    rows = conn.execute(
        f"SELECT date, value, fetched_at FROM {meta['table']} ORDER BY date DESC LIMIT 30"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/history")
def get_history():
    """두 지표 모두의 누적 데이터(최신 순)를 반환합니다."""
    conn = get_db()
    result = {}
    for series_id, meta in INDICATORS.items():
        rows = conn.execute(
            f"SELECT date, value FROM {meta['table']} ORDER BY date DESC"
        ).fetchall()
        records = [{"date": r["date"], "value": r["value"]} for r in rows]
        # day-over-day change 계산 (최신 순이므로 i+1이 전일)
        enriched = []
        for i, rec in enumerate(records):
            prev = records[i + 1] if i + 1 < len(records) else None
            change = round(rec["value"] - prev["value"], 4) if prev else None
            change_pct = round((change / prev["value"]) * 100, 2) if prev and prev["value"] else None
            enriched.append({
                "date": rec["date"],
                "value": rec["value"],
                "change": change,
                "change_pct": change_pct,
            })
        result[series_id] = {
            "indicator_name": meta["name"],
            "description": meta.get("description", ""),
            "color": meta.get("color", "#4299e1"),
            "records": enriched,
            "total_count": len(enriched),
        }
    conn.close()
    return jsonify(result)


@app.route("/nyfed")
def get_nyfed():
    """NY Fed 최신 데이터 (EFFR, SOFR, RRP + Spread)를 반환합니다."""
    conn = get_db()
    fetched_at = now_kst_str()

    def _latest_rate(table: str):
        row = conn.execute(
            f"SELECT date, rate, volume_billions FROM {table} ORDER BY date DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def _latest_rrp():
        row = conn.execute(
            "SELECT date, total_amt_billions FROM nyfed_rrp ORDER BY date DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    effr = _latest_rate("nyfed_effr")
    sofr = _latest_rate("nyfed_sofr")
    rrp  = _latest_rrp()

    # ── 공통 날짜 기반 스프레드 계산 ─────────────────────────────
    # EFFR과 SOFR은 발표 시점이 달라 최신일이 다를 수 있으므로
    # 반드시 두 지표가 모두 존재하는 가장 최근 날짜를 찾아 계산합니다.
    spread      = None
    spread_date = None

    effr_dates = {r["date"] for r in conn.execute("SELECT DISTINCT date FROM nyfed_effr").fetchall()}
    sofr_dates = {r["date"] for r in conn.execute("SELECT DISTINCT date FROM nyfed_sofr").fetchall()}
    common_dates = sorted(effr_dates & sofr_dates, reverse=True)

    if common_dates:
        cdate = common_dates[0]
        er = conn.execute("SELECT rate FROM nyfed_effr WHERE date=?", (cdate,)).fetchone()
        sr = conn.execute("SELECT rate FROM nyfed_sofr WHERE date=?", (cdate,)).fetchone()
        if er and sr and er["rate"] is not None and sr["rate"] is not None:
            spread      = round(sr["rate"] - er["rate"], 4)   # SOFR - EFFR
            spread_date = cdate

    # SOFR 90일 평균 — FRA-OIS 프록시
    sofr_90_row = conn.execute("SELECT date, value FROM sofr_90d ORDER BY date DESC LIMIT 1").fetchone()
    sofr_90d = None
    if sofr_90_row:
        sofr_90d = {"date": sofr_90_row["date"], "rate": sofr_90_row["value"]}

    # SOFR 텀 프리미엄 (SOFR90DAYAVG − SOFR 익일물, bp)
    term_spread      = None
    term_spread_date = None
    if sofr_90d and sofr and sofr.get("rate") is not None:
        term_spread      = round((sofr_90d["rate"] - sofr["rate"]) * 100, 2)
        term_spread_date = sofr_90d["date"]

    conn.close()

    return jsonify({
        "effr": effr,
        "sofr": sofr,
        "rrp": rrp,
        "spread": spread,
        "spread_date": spread_date,
        "sofr_90d": sofr_90d,
        "term_spread": term_spread,
        "term_spread_date": term_spread_date,
        "server_time_kst": fetched_at,
    })


@app.route("/nyfed/history")
def get_nyfed_history():
    """EFFR/SOFR 90일 시계열 데이터를 반환합니다. (차트용)"""
    conn = get_db()
    effr_rows = conn.execute(
        "SELECT date, rate, volume_billions, target_low, target_high "
        "FROM nyfed_effr ORDER BY date ASC"
    ).fetchall()
    sofr_rows = conn.execute(
        "SELECT date, rate, volume_billions FROM nyfed_sofr ORDER BY date ASC"
    ).fetchall()
    conn.close()

    effr_data = [
        {
            "date": r["date"],
            "rate": r["rate"],
            "volume": r["volume_billions"],
            "target_low": r["target_low"],
            "target_high": r["target_high"],
        }
        for r in effr_rows
    ]
    sofr_data = [
        {"date": r["date"], "rate": r["rate"], "volume": r["volume_billions"]}
        for r in sofr_rows
    ]
    return jsonify({"effr": effr_data, "sofr": sofr_data})


@app.route("/fedop")
def get_fedop():
    """Fed Operation 최신 요약 (SOMA 주간 변화, AMBS, SecLending, TSY)을 반환합니다."""
    conn = get_db()

    # ── SOMA: 최신 2주 데이터로 주간 변화 계산 ──────────────────
    soma_rows = conn.execute(
        "SELECT asof_date, total_bil, mbs_bil FROM fedop_soma ORDER BY asof_date DESC LIMIT 2"
    ).fetchall()
    soma_latest  = dict(soma_rows[0]) if len(soma_rows) > 0 else None
    soma_prev    = dict(soma_rows[1]) if len(soma_rows) > 1 else None
    soma_change  = None
    if soma_latest and soma_prev:
        soma_change = round(soma_latest["total_bil"] - soma_prev["total_bil"], 4)

    # ── AMBS: 가장 최신 날짜 오퍼레이션 ─────────────────────────
    ambs_row = conn.execute(
        "SELECT op_date, direction, "
        "SUM(accepted_bil) as total_bil, SUM(submitted_bil) as total_submitted, "
        "GROUP_CONCAT(op_type, ' / ') as types "
        "FROM fedop_ambs GROUP BY op_date ORDER BY op_date DESC LIMIT 1"
    ).fetchone()
    ambs = None
    if ambs_row:
        ambs = dict(ambs_row)
        if ambs.get("total_submitted") and ambs["total_submitted"] > 0:
            ambs["accept_ratio"] = round(ambs["total_bil"] / ambs["total_submitted"] * 100, 1)
        else:
            ambs["accept_ratio"] = None

    # ── SecLending: 가장 최신 ────────────────────────────────────
    seclend_row = conn.execute(
        "SELECT op_date, SUM(par_accepted_bil) as total_bil, SUM(submitted_bil) as total_submitted "
        "FROM fedop_seclending GROUP BY op_date ORDER BY op_date DESC LIMIT 1"
    ).fetchone()
    seclending = None
    if seclend_row:
        seclending = dict(seclend_row)
        if seclending.get("total_submitted") and seclending["total_submitted"] > 0:
            seclending["accept_ratio"] = round(seclending["total_bil"] / seclending["total_submitted"] * 100, 1)
        else:
            seclending["accept_ratio"] = None

    # ── TSY Outright: 가장 최신 날짜 ────────────────────────────
    tsy_row = conn.execute(
        "SELECT op_date, direction, "
        "SUM(accepted_bil) as total_bil, SUM(submitted_bil) as total_submitted, "
        "GROUP_CONCAT(op_type, ' / ') as types "
        "FROM fedop_tsy GROUP BY op_date ORDER BY op_date DESC LIMIT 1"
    ).fetchone()
    tsy = None
    if tsy_row:
        tsy = dict(tsy_row)
        if tsy.get("total_submitted") and tsy["total_submitted"] > 0:
            tsy["accept_ratio"] = round(tsy["total_bil"] / tsy["total_submitted"] * 100, 1)
        else:
            tsy["accept_ratio"] = None

    # ── RRP (역레포): nyfed_rrp 테이블 활용 (최신 2건으로 전일 대비 변화) ──
    rrp_rows = conn.execute(
        "SELECT date AS op_date, total_amt_billions AS total_accepted_bil "
        "FROM nyfed_rrp ORDER BY date DESC LIMIT 2"
    ).fetchall()
    if rrp_rows:
        rrp_latest = dict(rrp_rows[0])
        rrp_prev   = dict(rrp_rows[1]) if len(rrp_rows) > 1 else None
        rrp_change = None
        if rrp_prev and rrp_latest["total_accepted_bil"] is not None and rrp_prev["total_accepted_bil"] is not None:
            rrp_change = round(rrp_latest["total_accepted_bil"] - rrp_prev["total_accepted_bil"], 4)
        rrp_data = {
            "op_date":             rrp_latest["op_date"],
            "total_accepted_bil":  rrp_latest["total_accepted_bil"],
            "total_submitted_bil": None,
            "accept_ratio":        None,
            "change_bil":          rrp_change,
            "prev_date":           rrp_prev["op_date"] if rrp_prev else None,
        }
    else:
        rrp_data = None

    # ── RP (레포): fedop_rp 테이블 (최근 RP 오퍼레이션 없으면 null) ──
    rp_rows = conn.execute(
        "SELECT op_date, total_accepted_bil, total_submitted_bil "
        "FROM fedop_rp ORDER BY op_date DESC LIMIT 2"
    ).fetchall()
    if rp_rows:
        rp_latest = dict(rp_rows[0])
        rp_prev   = dict(rp_rows[1]) if len(rp_rows) > 1 else None
        rp_change = None
        if rp_prev and rp_latest["total_accepted_bil"] is not None and rp_prev["total_accepted_bil"] is not None:
            rp_change = round(rp_latest["total_accepted_bil"] - rp_prev["total_accepted_bil"], 4)
        rp_ratio = None
        if rp_latest.get("total_submitted_bil") and rp_latest["total_submitted_bil"] > 0:
            rp_ratio = round(rp_latest["total_accepted_bil"] / rp_latest["total_submitted_bil"] * 100, 1)
        rp_data = {
            "op_date":             rp_latest["op_date"],
            "total_accepted_bil":  rp_latest["total_accepted_bil"],
            "total_submitted_bil": rp_latest.get("total_submitted_bil"),
            "accept_ratio":        rp_ratio,
            "change_bil":          rp_change,
            "prev_date":           rp_prev["op_date"] if rp_prev else None,
        }
    else:
        rp_data = None

    # ── Discount Window (FRED WLCFLPCL) ─────────────────────────
    dw_rows = conn.execute(
        "SELECT date, value FROM discount_window ORDER BY date DESC LIMIT 2"
    ).fetchall()
    dw_data = None
    if dw_rows:
        dw_latest = dict(dw_rows[0])
        dw_prev   = dict(dw_rows[1]) if len(dw_rows) > 1 else None
        dw_chg    = None
        if dw_prev and dw_latest["value"] is not None and dw_prev["value"] is not None:
            dw_chg = round(dw_latest["value"] - dw_prev["value"], 0)
        dw_data = {
            "date":        dw_latest["date"],
            "value_mil":   dw_latest["value"],
            "prev_date":   dw_prev["date"]  if dw_prev else None,
            "change_mil":  dw_chg,
        }

    # ── TGA (FRED WTREGEN) ───────────────────────────────────────
    tga_rows = conn.execute(
        "SELECT date, value FROM tga_balance ORDER BY date DESC LIMIT 2"
    ).fetchall()
    tga_data = None
    if tga_rows:
        tga_latest = dict(tga_rows[0])
        tga_prev   = dict(tga_rows[1]) if len(tga_rows) > 1 else None
        tga_chg    = None
        if tga_prev and tga_latest["value"] is not None and tga_prev["value"] is not None:
            tga_chg = round(tga_latest["value"] - tga_prev["value"], 0)
        tga_data = {
            "date":       tga_latest["date"],
            "value_mil":  tga_latest["value"],
            "prev_date":  tga_prev["date"]  if tga_prev else None,
            "change_mil": tga_chg,
        }

    conn.close()
    return jsonify({
        "soma": {
            "latest_date": soma_latest["asof_date"] if soma_latest else None,
            "total_bil":   soma_latest["total_bil"]  if soma_latest else None,
            "prev_date":   soma_prev["asof_date"]    if soma_prev else None,
            "change_bil":  soma_change,
        } if soma_latest else None,
        "ambs":             ambs,
        "seclending":       seclending,
        "tsy":              tsy,
        "rrp":              rrp_data,
        "rp":               rp_data,
        "discount_window":  dw_data,
        "tga":              tga_data,
    })


@app.route("/volatility")
def get_volatility():
    """Volatility 탭 — MOVE Index + HY OAS 최신값 + 30일 스파크라인 데이터."""
    conn = get_db()

    def _vol_payload(table: str, date_col: str = "date", val_col: str = "value", n: int = 35):
        rows = conn.execute(
            f"SELECT {date_col} AS d, {val_col} AS v "
            f"FROM {table} ORDER BY {date_col} DESC LIMIT {n}"
        ).fetchall()
        if not rows:
            return None
        latest   = {"date": rows[0]["d"], "value": rows[0]["v"]}
        prev     = {"date": rows[1]["d"], "value": rows[1]["v"]} if len(rows) > 1 else None
        change     = None
        change_pct = None
        if prev and latest["value"] is not None and prev["value"] is not None:
            change     = round(latest["value"] - prev["value"], 4)
            change_pct = round(change / prev["value"] * 100, 2) if prev["value"] else None
        history = [{"date": r["d"], "value": r["v"]} for r in reversed(rows)]
        return {
            "latest":     latest,
            "prev":       prev,
            "change":     change,
            "change_pct": change_pct,
            "history":    history,
        }

    move_data  = _vol_payload("move_index")
    hy_data    = _vol_payload("hy_index")
    skew_data  = _vol_payload("skew_index")

    # MOVE/VIX 비율 계산
    move_vix_ratio = None
    move_latest = conn.execute("SELECT value FROM move_index ORDER BY date DESC LIMIT 1").fetchone()
    vix_latest  = conn.execute("SELECT value FROM vix_index  ORDER BY date DESC LIMIT 1").fetchone()
    move_prev   = conn.execute("SELECT value FROM move_index ORDER BY date DESC LIMIT 1 OFFSET 1").fetchone()
    vix_prev    = conn.execute("SELECT value FROM vix_index  ORDER BY date DESC LIMIT 1 OFFSET 1").fetchone()
    if move_latest and vix_latest and vix_latest["value"] and vix_latest["value"] > 0:
        ratio_val  = round(move_latest["value"] / vix_latest["value"], 3)
        ratio_prev = None
        if move_prev and vix_prev and vix_prev["value"] and vix_prev["value"] > 0:
            ratio_prev = round(move_prev["value"] / vix_prev["value"], 3)
        move_vix_ratio = {
            "value":      ratio_val,
            "prev_value": ratio_prev,
            "change":     round(ratio_val - ratio_prev, 3) if ratio_prev is not None else None,
        }

    conn.close()
    return jsonify({
        "move":           move_data,
        "hy_oas":         hy_data,
        "skew":           skew_data,
        "move_vix_ratio": move_vix_ratio,
    })


@app.route("/fedop/history")
def get_fedop_history():
    """Fed Operation 차트용 이력 데이터를 반환합니다."""
    conn = get_db()

    # ── SOMA: 최근 16주 주간 변화 계산 ──────────────────────────
    soma_rows = conn.execute(
        "SELECT asof_date, total_bil FROM fedop_soma ORDER BY asof_date DESC LIMIT 16"
    ).fetchall()
    soma_weekly = []
    soma_sorted = sorted(soma_rows, key=lambda r: r["asof_date"])
    for i in range(1, len(soma_sorted)):
        curr = soma_sorted[i]
        prev = soma_sorted[i - 1]
        change = round(curr["total_bil"] - prev["total_bil"], 4)
        soma_weekly.append({
            "date":       curr["asof_date"],
            "total_bil":  curr["total_bil"],
            "change_bil": change,
        })

    # ── Daily Ops: AMBS + SecLending + TSY 날짜 병합 (낙찰비율 포함) ──
    ambs_rows = conn.execute(
        "SELECT op_date, SUM(accepted_bil) as ambs_bil, SUM(submitted_bil) as ambs_sub "
        "FROM fedop_ambs GROUP BY op_date ORDER BY op_date DESC LIMIT 30"
    ).fetchall()
    seclend_rows = conn.execute(
        "SELECT op_date, SUM(par_accepted_bil) as seclend_bil, SUM(submitted_bil) as seclend_sub "
        "FROM fedop_seclending GROUP BY op_date ORDER BY op_date DESC LIMIT 30"
    ).fetchall()
    tsy_rows = conn.execute(
        "SELECT op_date, SUM(accepted_bil) as tsy_bil, SUM(submitted_bil) as tsy_sub "
        "FROM fedop_tsy GROUP BY op_date ORDER BY op_date DESC LIMIT 30"
    ).fetchall()

    # ── Discount Window 이력 (최근 52주) ────────────────────────
    dw_hist_rows = conn.execute(
        "SELECT date, value FROM discount_window ORDER BY date DESC LIMIT 52"
    ).fetchall()
    dw_history = [{"date": r["date"], "value": r["value"]} for r in reversed(dw_hist_rows)]

    # ── TGA 이력 (최근 52주) ────────────────────────────────────
    tga_hist_rows = conn.execute(
        "SELECT date, value FROM tga_balance ORDER BY date DESC LIMIT 52"
    ).fetchall()
    tga_history = [{"date": r["date"], "value": r["value"]} for r in reversed(tga_hist_rows)]

    conn.close()

    def _ratio(accepted, submitted):
        try:
            if submitted and float(submitted) > 0:
                return round(float(accepted) / float(submitted) * 100, 1)
        except Exception:
            pass
        return None

    ambs_map    = {r["op_date"]: {"bil": r["ambs_bil"],    "ratio": _ratio(r["ambs_bil"],    r["ambs_sub"])}    for r in ambs_rows}
    seclend_map = {r["op_date"]: {"bil": r["seclend_bil"], "ratio": _ratio(r["seclend_bil"], r["seclend_sub"])} for r in seclend_rows}
    tsy_map     = {r["op_date"]: {"bil": r["tsy_bil"],     "ratio": _ratio(r["tsy_bil"],     r["tsy_sub"])}     for r in tsy_rows}

    all_dates = sorted(
        set(ambs_map) | set(seclend_map) | set(tsy_map), reverse=True
    )[:30]

    daily_ops = []
    for d in sorted(all_dates):
        a = ambs_map.get(d, {})
        s = seclend_map.get(d, {})
        t = tsy_map.get(d, {})
        daily_ops.append({
            "date":         d,
            "ambs_bil":     a.get("bil", 0) or 0,
            "ambs_ratio":   a.get("ratio"),
            "seclend_bil":  s.get("bil", 0) or 0,
            "seclend_ratio": s.get("ratio"),
            "tsy_bil":      t.get("bil", 0) or 0,
            "tsy_ratio":    t.get("ratio"),
        })

    return jsonify({
        "soma_weekly":     soma_weekly,
        "daily_ops":       daily_ops,
        "discount_window": dw_history,
        "tga":             tga_history,
    })


# ── JPY Swap 갱신 ─────────────────────────────────────────────

JPY_RETRY_MINUTES = 10   # 차단 시 재시도 간격(분)
_jpy_retry_job_id = "refresh_jpy_retry"


def _set_jpy_status(conn, status: str, message: str = "") -> None:
    conn.execute(
        "INSERT OR REPLACE INTO jpy_swap_status (id, status, message, updated_at) VALUES (1, ?, ?, ?)",
        (status, message, now_kst_str()),
    )
    conn.commit()


def _save_jpy_data(forward_data: dict, spot_rate: float | None) -> int:
    """스크래핑 결과를 jpy_swap_data 테이블에 저장합니다."""
    conn = get_db()
    now = now_kst_str()
    count = 0
    for period, vals in forward_data.items():
        conn.execute(
            "INSERT INTO jpy_swap_data (period, bid, change_val, spot_rate, fetched_at) VALUES (?, ?, ?, ?, ?)",
            (period, vals.get("bid"), vals.get("change"), spot_rate, now),
        )
        count += 1
    conn.commit()
    conn.close()
    return count


def _jpy_annualized(bid: float | None, spot: float | None, days: int) -> float | None:
    """연율화 비용(%) = (bid / 100 / spot) × (360 / days) × 100"""
    if bid is None or spot is None or spot == 0:
        return None
    try:
        return round((bid / 100 / spot) * (360 / days) * 100, 4)
    except Exception:
        return None


def save_jpy_daily_snapshot() -> int:
    """매일 KST 08:00 에 JPY swap 5개 만기의 일별 snapshot 저장.

    Stage 2.0 인프라 구축 — Stage 2.4 에서 30일 누적 후 percentile 임계 확정.

    동작:
      1. 각 만기(1M/3M/3Y/7Y/10Y)별로 오늘 fetch 된 가장 최근 값 조회
         (오늘 데이터 없으면 DB 내 가장 최신 값으로 대체 + 경고)
      2. _jpy_annualized() 로 implied_yield_pct 계산
      3. jpy_swap_daily 에 INSERT OR REPLACE (같은 날 재실행 시 갱신)

    GPT 가이드 핵심: 분석 시 bid 의 절대값 변화 기준 사용
      - abs(bid) 감소 = 0 에 가까워짐 = carry 약화 (stress 신호)
      - abs(bid) 증가 = carry 강화 (normal)
    Stage 2.4 에서 scripts/analyze_jpy_distribution.py 로 분포 분석.
    """
    today_kst = datetime.now(tz=KST).strftime("%Y-%m-%d")
    now_iso   = datetime.now(tz=KST).isoformat()

    conn = get_db()
    saved_count    = 0
    missing_periods: list[str] = []

    for period, days in JPY_PERIOD_DAYS.items():
        # 오늘 KST 날짜 기준 최신 fetch 먼저 시도
        row = conn.execute(
            """SELECT bid, spot_rate FROM jpy_swap_data
               WHERE period = ? AND date(fetched_at) = ?
               ORDER BY fetched_at DESC LIMIT 1""",
            (period, today_kst),
        ).fetchone()

        if row is None:
            # 오늘 fetch 없으면 DB 내 가장 최신 값으로 fallback
            row = conn.execute(
                """SELECT bid, spot_rate FROM jpy_swap_data
                   WHERE period = ?
                   ORDER BY fetched_at DESC LIMIT 1""",
                (period,),
            ).fetchone()
            if row is None:
                missing_periods.append(period)
                continue
            log.debug(f"[JPY Daily] {period}: 오늘 fetch 없음 — 최신 값으로 대체")

        bid       = row["bid"]
        spot_rate = row["spot_rate"]
        implied   = _jpy_annualized(bid, spot_rate, days)

        conn.execute(
            """INSERT OR REPLACE INTO jpy_swap_daily
               (date, period, bid, spot_rate, implied_yield_pct, snapshot_time)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (today_kst, period, bid, spot_rate, implied, now_iso),
        )
        saved_count += 1

    conn.commit()
    conn.close()

    if missing_periods:
        log.warning(
            f"[JPY Daily] {today_kst} snapshot: {saved_count}/5 저장, "
            f"누락 만기: {missing_periods} (jpy_swap_data 미수집)"
        )
    else:
        log.info(f"[JPY Daily] {today_kst} snapshot 저장 완료 ({saved_count}/5 만기)")

    return saved_count


def refresh_jpy() -> None:
    """
    JPY 포워드 레이트 스크래핑 후 DB 저장.
    실패 시 10분 후 재시도 잡을 등록합니다.
    갱신 후 연율화 비용 변동 알람을 체크합니다.
    """
    _JPY_PERIOD_DAYS = {"1M": 30, "3M": 90, "3Y": 1095, "7Y": 2555, "10Y": 3650}

    log.info("[JPY] 갱신 시작")
    conn = get_db()
    try:
        result = jpy_scraper.scrape_jpy_forward()
        forward_data = result.get("forward") if result else None
        spot_rate    = result.get("spot_rate") if result else None
        if forward_data and len(forward_data) >= 3:
            spot_msg = f" / Spot={spot_rate}" if spot_rate else " / Spot 수신 실패"
            _set_jpy_status(conn, "ok", f"{len(forward_data)}개 기간 수신{spot_msg}")
            conn.close()
            saved = _save_jpy_data(forward_data, spot_rate)
            log.info(f"[JPY] 저장 완료: {saved}건 ({list(forward_data.keys())}) spot={spot_rate}")
            telegram_alerts.record_success("jpy")

            # ── 알람 체크: 각 만기별 연율화 비용 비교 ────────────
            if spot_rate:
                try:
                    conn2 = get_db()
                    for period, days in _JPY_PERIOD_DAYS.items():
                        rows = conn2.execute(
                            "SELECT bid, spot_rate FROM jpy_swap_data "
                            "WHERE period=? ORDER BY fetched_at DESC LIMIT 2",
                            (period,),
                        ).fetchall()
                        if len(rows) >= 2:
                            cur_yield = _jpy_annualized(
                                rows[0]["bid"],
                                rows[0]["spot_rate"] or spot_rate,
                                days,
                            )
                            prev_yield = _jpy_annualized(
                                rows[1]["bid"],
                                rows[1]["spot_rate"] or spot_rate,
                                days,
                            )
                            key = f"jpy_{period.lower()}"
                            telegram_alerts.check_and_alert(key, cur_yield, prev_yield)
                    conn2.close()
                except Exception as exc:
                    log.error(f"[JPY] 알람 체크 오류: {exc}")

            # 재시도 잡이 존재하면 제거
            if _scheduler is not None:
                try:
                    _scheduler.remove_job(_jpy_retry_job_id)
                    log.info("[JPY] 재시도 잡 제거")
                except Exception:
                    pass
        else:
            msg = "데이터 수신 실패 — 차단 또는 구조 변경"
            log.warning(f"[JPY] {msg}")
            _set_jpy_status(conn, "retry", msg)
            conn.close()
            telegram_alerts.record_error("jpy", msg)
            # 10분 후 재시도 잡 등록
            if _scheduler is not None:
                from datetime import datetime as _dt
                run_at = _dt.now(tz=KST) + timedelta(minutes=JPY_RETRY_MINUTES)
                try:
                    _scheduler.remove_job(_jpy_retry_job_id)
                except Exception:
                    pass
                _scheduler.add_job(
                    refresh_jpy,
                    trigger="date",
                    run_date=run_at,
                    id=_jpy_retry_job_id,
                    replace_existing=True,
                )
                log.info(f"[JPY] {JPY_RETRY_MINUTES}분 후 재시도 잡 등록")
    except Exception as exc:
        conn.close()
        log.error(f"[JPY] refresh_jpy 예외: {exc}")
        telegram_alerts.record_error("jpy", str(exc))


@app.route("/jpy")
def get_jpy():
    """JPY 포워드 레이트 최신 카드 데이터 + 상태 + 연율화 비용 반환."""
    conn = get_db()
    PERIODS = ["1M", "3M", "3Y", "7Y", "10Y"]
    PERIOD_DAYS = {"1M": 30, "3M": 90, "3Y": 1095, "7Y": 2555, "10Y": 3650}

    def _annualized_yield(bid: float | None, spot: float | None, days: int) -> float | None:
        """연율화 비용(%) = (포워드포인트 / 100 / Spot) × (360 / Days) × 100"""
        if bid is None or spot is None or spot == 0:
            return None
        try:
            return round((bid / 100 / spot) * (360 / days) * 100, 2)
        except Exception:
            return None

    # 각 기간의 최신 데이터
    result = {}
    for p in PERIODS:
        row = conn.execute(
            "SELECT bid, change_val, spot_rate, fetched_at FROM jpy_swap_data "
            "WHERE period = ? ORDER BY fetched_at DESC LIMIT 1",
            (p,),
        ).fetchone()
        if row:
            d = dict(row)
            d["annualized_yield"] = _annualized_yield(d["bid"], d["spot_rate"], PERIOD_DAYS[p])
            result[p] = d
        else:
            result[p] = None

    # 현재 상태
    status_row = conn.execute(
        "SELECT status, message, updated_at FROM jpy_swap_status WHERE id = 1"
    ).fetchone()
    conn.close()

    # spot_rate: 가장 최근에 수집된 값 사용
    spot_rate = None
    for p in PERIODS:
        if result[p] and result[p].get("spot_rate"):
            spot_rate = result[p]["spot_rate"]
            break

    # Japan 30Y JGB — 포트폴리오 캐시에서 추출
    japan30y = None
    with _portfolio_lock:
        cached = _portfolio_cache.get("data")
    if cached:
        for r in cached.get("rows", []):
            if r.get("symbol") == "Japan 30Y JGB":
                japan30y = {
                    "last":     r.get("last"),
                    "chg":      r.get("chg"),
                    "chg_pct":  r.get("chg_pct"),
                    "status":   r.get("status"),
                    "updated_at": r.get("updated_at"),
                }
                break

    return jsonify({
        "data":       result,
        "spot_rate":  spot_rate,
        "status":     dict(status_row) if status_row else {"status": "init", "message": "", "updated_at": ""},
        "japan30y":   japan30y,
    })


@app.route("/jpy/history")
def get_jpy_history():
    """JPY 1M & 3M 최근 24시간 Bid 이력 반환 (선 그래프용)."""
    conn = get_db()
    cutoff = (datetime.now(tz=KST) - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S KST")

    history = {}
    for period in ["1M", "3M"]:
        rows = conn.execute(
            "SELECT bid, change_val, fetched_at FROM jpy_swap_data "
            "WHERE period = ? AND fetched_at >= ? ORDER BY fetched_at ASC",
            (period, cutoff),
        ).fetchall()
        history[period] = [dict(r) for r in rows]

    conn.close()
    return jsonify(history)


# ── Portfolio 종합 시장 데이터 ────────────────────────────────────

_portfolio_cache: dict = {"data": None, "updated_at": None}
_portfolio_lock = threading.Lock()
_PORTFOLIO_CACHE_TTL = 900  # 초 (15분) — 스케줄 주기와 일치시켜 Playwright 중복 실행 방지
_portfolio_refreshing = threading.Event()  # Playwright 이중 실행 방지


def refresh_portfolio() -> None:
    """Portfolio 데이터를 수집해 메모리 캐시에 저장합니다.
    수집 후 각 지표별 임계치 초과 시 텔레그램 알람을 발송합니다.
    """
    if _portfolio_refreshing.is_set():
        log.info("[Portfolio] 이미 갱신 중 — 중복 실행 건너뜀")
        return
    _portfolio_refreshing.set()
    log.info("[Portfolio] 갱신 시작")
    try:
        result = portfolio_scraper.fetch_all()
        with _portfolio_lock:
            _portfolio_cache["data"]       = result
            _portfolio_cache["updated_at"] = datetime.now(tz=KST)
        rows = result.get("rows", [])
        log.info(f"[Portfolio] 캐시 갱신 완료: {len(rows)}개 지표")
        telegram_alerts.record_success("portfolio")

        # ── 알람 체크: chg_pct가 임계치 초과인 지표 ───────────────
        for row in rows:
            try:
                telegram_alerts.check_portfolio_row(
                    symbol   = row.get("symbol", ""),
                    chg_pct  = row.get("chg_pct"),
                    current  = row.get("last"),
                    previous = None,  # yfinance chg_pct 사용 (previous 불필요)
                )
            except Exception as exc_r:
                log.debug(f"[Portfolio] 행 알람 체크 오류 {row.get('symbol')}: {exc_r}")

    except Exception as exc:
        log.error(f"[Portfolio] refresh_portfolio 오류: {exc}")
        telegram_alerts.record_error("portfolio", str(exc))
    finally:
        _portfolio_refreshing.clear()  # 완료 후 플래그 해제


@app.route("/portfolio")
def get_portfolio():
    """
    종합 시장 지표 반환.
    - 캐시가 60초 이내이면 즉시 반환
    - 캐시가 없거나 만료됐으면 실시간 fetch 후 반환
    """
    now = datetime.now(tz=KST)
    with _portfolio_lock:
        cached = _portfolio_cache.get("data")
        updated = _portfolio_cache.get("updated_at")

    cache_fresh = (
        cached is not None and
        updated is not None and
        (now - updated).total_seconds() < _PORTFOLIO_CACHE_TTL
    )

    if not cache_fresh:
        # 스케줄러가 백그라운드에서 수집 중이거나 곧 수집 예정 — 즉시 Playwright 실행 금지
        # (캐시 미스 시 HTTP 요청 스레드에서 Playwright 실행하면 OOM 위험)
        if not _portfolio_refreshing.is_set():
            log.info("[Portfolio] 캐시 미스 — 백그라운드 갱신 요청")
            threading.Thread(target=refresh_portfolio, daemon=True, name="portfolio_bg").start()

    if not cached:
        return jsonify({"rows": [], "updated_at": now_kst_str(), "status": "loading"})

    return jsonify({**cached, "status": "ok"})


@app.route("/fetch-now")
def fetch_now():
    """수동으로 FRED 데이터를 즉시 갱신합니다."""
    results = {}
    for series_id, meta in INDICATORS.items():
        observations = fetch_fred_observations(series_id, limit=10)
        if observations:
            count = upsert_observations(meta["table"], observations)
            results[series_id] = {"success": True, "new_records": count}
        else:
            results[series_id] = {"success": False, "message": "FRED API 호출 실패"}

    return jsonify({
        "results": results,
        "fetched_at": now_kst_str(),
    })


def _get_next_schedule_str(sched_cfg: dict) -> str:
    """다음 스케줄 예정 시각을 사람이 읽기 쉬운 형태로 반환합니다."""
    hours = sched_cfg.get("hour", "8").split(",")
    minute = sched_cfg.get("minute", "0").zfill(2)
    return " / ".join(f"매일 {h.strip()}:{minute} KST" for h in hours)


# ── 헬스체크 엔드포인트 ────────────────────────────────────────

@app.route("/health")
def health():
    """
    서버 및 스케줄러 상태 확인 엔드포인트.
    모니터링 도구, Replit 헬스체크, 외부 ping 서비스에서 활용합니다.
    """
    sched_running = _scheduler is not None and _scheduler.running
    jobs = []
    if sched_running:
        for job in _scheduler.get_jobs():
            jobs.append({
                "id":       job.id,
                "next_run": job.next_run_time.strftime("%Y-%m-%d %H:%M:%S KST")
                            if job.next_run_time else None,
            })

    portfolio_age_sec = None
    with _portfolio_lock:
        ptf_updated = _portfolio_cache.get("updated_at")
    if ptf_updated:
        portfolio_age_sec = int((datetime.now(tz=KST) - ptf_updated).total_seconds())

    status = "ok" if sched_running else "degraded"
    return jsonify({
        "status":            status,
        "server_time_kst":   now_kst_str(),
        "scheduler_running": sched_running,
        "scheduler_jobs":    jobs,
        "portfolio_cache_age_sec": portfolio_age_sec,
        "version":           "1.0",
    }), 200 if status == "ok" else 503


# ── 앱 초기화 (Gunicorn + 직접 실행 공용) ──────────────────────

def _startup_full_refresh() -> None:
    """
    앱 시작 시 모든 API에서 즉시 최신 데이터를 수집하고 알람을 체크합니다.
    스케줄러 정기 갱신과 동일한 로직(알람 포함)으로 순차 실행됩니다.
    """
    log.info("[Startup] 전체 초기 수집 시작 (FRED → NYFed → JPY → Portfolio)")

    # 1. FRED 지표: 최신 데이터 갱신 + 알람 체크
    _FRED_ALERT_KEYS = {
        "BAMLH0A0HYM2":     "hy_index",
        "RIFSPPNA2P2D30NB": "cp_30d",
    }
    for series_id, meta in INDICATORS.items():
        try:
            obs = fetch_fred_observations(series_id, limit=10)
            if obs:
                upsert_observations(meta["table"], obs)
                telegram_alerts.record_success(f"fred_{series_id}")
                alert_key = _FRED_ALERT_KEYS.get(series_id)
                if alert_key:
                    conn = get_db()
                    rows = conn.execute(
                        f"SELECT value FROM {meta['table']} ORDER BY date DESC LIMIT 2"
                    ).fetchall()
                    conn.close()
                    if len(rows) >= 2:
                        telegram_alerts.check_and_alert(
                            alert_key, rows[0]["value"], rows[1]["value"]
                        )
            else:
                telegram_alerts.record_error(f"fred_{series_id}", "FRED API 응답 없음")
        except Exception as exc:
            log.error(f"[Startup] FRED {series_id} 오류: {exc}")

    # 2. NY Fed 갱신 + 알람
    try:
        refresh_nyfed()
    except Exception as exc:
        log.error(f"[Startup] NYFed 갱신 오류: {exc}")

    # 3. JPY 갱신 + 알람
    try:
        refresh_jpy()
    except Exception as exc:
        log.error(f"[Startup] JPY 갱신 오류: {exc}")

    # 4. Portfolio — startup 시 즉시 실행 생략 (Playwright OOM 방지)
    # 첫 수집은 스케줄러 15분 주기 잡이 담당
    log.info("[Startup] Portfolio 초기 수집 생략 — 스케줄러 첫 실행 시 자동 수집")

    # 5. MOVE Index 갱신 + 알람 (DB 비어있으면 3개월치 초기 로드)
    try:
        conn = get_db()
        move_count = conn.execute("SELECT COUNT(*) FROM move_index").fetchone()[0]
        conn.close()
        if move_count == 0:
            log.info("[MOVE] DB 비어있음 — 3개월 이력 초기 로드")
        refresh_move()
    except Exception as exc:
        log.error(f"[Startup] MOVE 갱신 오류: {exc}")

    # 6. CBOE SKEW 초기 로드
    try:
        conn = get_db()
        skew_count = conn.execute("SELECT COUNT(*) FROM skew_index").fetchone()[0]
        conn.close()
        refresh_skew()
        if skew_count == 0:
            log.info("[SKEW] DB 비어있음 — 3개월 이력 초기 로드 완료")
    except Exception as exc:
        log.error(f"[Startup] SKEW 갱신 오류: {exc}")

    # 7. SOFR 90일 평균 초기 로드
    try:
        conn = get_db()
        s90_count = conn.execute("SELECT COUNT(*) FROM sofr_90d").fetchone()[0]
        conn.close()
        if s90_count == 0:
            log.info("[SOFR 90d] DB 비어있음 — 이력 로드 중...")
            upsert_observations("sofr_90d", fetch_fred_observations("SOFR90DAYAVG", limit=500) or [])
        else:
            refresh_sofr_90d()
    except Exception as exc:
        log.error(f"[Startup] SOFR 90d 갱신 오류: {exc}")

    # 8. Discount Window 초기 로드
    try:
        conn = get_db()
        dw_count = conn.execute("SELECT COUNT(*) FROM discount_window").fetchone()[0]
        conn.close()
        if dw_count == 0:
            log.info("[Discount Window] DB 비어있음 — 이력 로드 중...")
            upsert_observations("discount_window",
                fetch_fred_observations("WLCFLPCL", limit=500) or [])
        else:
            refresh_discount_window()
    except Exception as exc:
        log.error(f"[Startup] Discount Window 갱신 오류: {exc}")

    # 9. TGA 초기 로드
    try:
        conn = get_db()
        tga_count = conn.execute("SELECT COUNT(*) FROM tga_balance").fetchone()[0]
        conn.close()
        if tga_count == 0:
            log.info("[TGA] DB 비어있음 — 이력 로드 중...")
            upsert_observations("tga_balance",
                fetch_fred_observations("WTREGEN", limit=500) or [])
        else:
            refresh_tga()
    except Exception as exc:
        log.error(f"[Startup] TGA 갱신 오류: {exc}")

    # 10. Single-B OAS 초기 로드 (Stage 1)
    try:
        refresh_single_b_oas()
    except Exception as exc:
        log.error(f"[Startup] Single-B OAS 갱신 오류: {exc}")

    # 11. IG OAS 초기 로드 (Stage 1)
    try:
        refresh_ig_oas()
    except Exception as exc:
        log.error(f"[Startup] IG OAS 갱신 오류: {exc}")

    # 12. LQD ETF 초기 로드 (Stage 1)
    try:
        refresh_lqd()
    except Exception as exc:
        log.error(f"[Startup] LQD 갱신 오류: {exc}")

    # 13. HYG ETF 초기 로드 (Stage 2)
    try:
        refresh_hyg()
    except Exception as exc:
        log.error(f"[Startup] HYG 갱신 오류: {exc}")

    # 14. JPY 일별 snapshot 초기 저장 (Stage 2.0)
    # jpy_swap_data 에 데이터가 있는 경우에만 저장 (없으면 0건 저장 + 경고 로그)
    try:
        saved = save_jpy_daily_snapshot()
        log.info(f"[Startup] JPY daily snapshot: {saved}/5 만기 저장")
    except Exception as exc:
        log.error(f"[Startup] JPY daily snapshot 오류: {exc}")

    log.info("[Startup] 전체 초기 수집 및 알람 체크 완료 (Stage 2.0 포함)")


def _startup() -> None:
    """DB 초기화 → 인증 초기화 → 이력 로드 → 스케줄러 시작 → 전체 초기 수집 스레드 실행."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return  # 이미 초기화됨 (Gunicorn 멀티 worker 재진입 방지)

    init_db()

    # Google OAuth + Flask-Login 초기화
    app.register_blueprint(auth_bp)
    init_auth(app, DB_PATH)
    log.info("[Auth] Google OAuth 인증 초기화 완료")

    initial_load()  # DB 비어있을 때 이력 전체 로드

    _scheduler = start_scheduler()

    import threading
    threading.Thread(target=_startup_full_refresh, daemon=True, name="startup_refresh").start()
    log.info("[Startup] 전체 초기 수집 스레드 시작 (FRED + NYFed + JPY + Portfolio)")


import signal as _signal

def _shutdown_handler(signum, frame):
    log.info(f"[Shutdown] 시그널 {signum} 수신 — 스케줄러 종료 중...")
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    log.info("[Shutdown] 완료")

_signal.signal(_signal.SIGTERM, _shutdown_handler)
_signal.signal(_signal.SIGINT,  _shutdown_handler)

# Gunicorn 이 모듈을 import할 때 자동 초기화
_startup()


# ── 직접 실행 (python app.py) ──────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
