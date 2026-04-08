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

# ── NY Fed API ─────────────────────────────────────────────────
NYFED_BASE = "https://markets.newyorkfed.org/api"
NYFED_HEADERS = {"Accept": "application/json"}


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


# ── 스케줄 작업 ────────────────────────────────────────────────

def make_refresh_job(series_id: str, meta: dict):
    """
    특정 지표의 갱신 함수를 반환합니다.
    각 지표마다 독립적인 클로저를 생성합니다.
    갱신 후 텔레그램 알람 체크를 수행합니다.
    """
    # FRED series_id → telegram_alerts indicator_key 매핑
    _FRED_ALERT_KEYS = {
        "BAMLH0A0HYM2":        "hy_index",
        "RIFSPPNA2P2D30NB":    "cp_30d",
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

    # Portfolio 종합 시장 데이터: 매 5분마다 갱신
    scheduler.add_job(
        refresh_portfolio,
        trigger=IntervalTrigger(minutes=5, timezone=KST),
        id="refresh_portfolio",
    )
    log.info("[Portfolio] 스케줄 등록: 매 5분")

    # MOVE Index: 매일 07:00 / 22:00 KST (시장 마감 후 갱신)
    scheduler.add_job(
        refresh_move,
        trigger=CronTrigger(hour="7,22", minute="5", timezone="Asia/Seoul"),
        id="refresh_move",
    )
    log.info("[MOVE] 스케줄 등록: 매일 7,22시 5분 KST")

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
    """HY OA Index와 CP 금리 두 지표를 함께 반환합니다."""
    hy = _build_indicator_payload("BAMLH0A0HYM2")
    cp = _build_indicator_payload("RIFSPPNA2P2D30NB")

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
        # 신규 CP 필드
        "cp": cp,
        # 공통
        "server_time_kst": now_kst_str(),
    })


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

    conn.close()

    return jsonify({
        "effr": effr,
        "sofr": sofr,
        "rrp": rrp,
        "spread": spread,
        "spread_date": spread_date,
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

    conn.close()
    return jsonify({
        "soma": {
            "latest_date": soma_latest["asof_date"] if soma_latest else None,
            "total_bil":   soma_latest["total_bil"]  if soma_latest else None,
            "prev_date":   soma_prev["asof_date"]    if soma_prev else None,
            "change_bil":  soma_change,
        } if soma_latest else None,
        "ambs":       ambs,
        "seclending": seclending,
        "tsy":        tsy,
        "rrp":        rrp_data,
        "rp":         rp_data,
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

    conn.close()
    return jsonify({
        "move":   move_data,
        "hy_oas": hy_data,
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

    return jsonify({"soma_weekly": soma_weekly, "daily_ops": daily_ops})


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
_PORTFOLIO_CACHE_TTL = 60  # 초 (1분)


def refresh_portfolio() -> None:
    """Portfolio 데이터를 수집해 메모리 캐시에 저장합니다.
    수집 후 각 지표별 임계치 초과 시 텔레그램 알람을 발송합니다.
    """
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
        log.info("[Portfolio] 캐시 미스 — 실시간 수집")
        refresh_portfolio()
        with _portfolio_lock:
            cached = _portfolio_cache.get("data")

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

    # 4. Portfolio 갱신 + 알람
    try:
        refresh_portfolio()
    except Exception as exc:
        log.error(f"[Startup] Portfolio 갱신 오류: {exc}")

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

    log.info("[Startup] 전체 초기 수집 및 알람 체크 완료")


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
