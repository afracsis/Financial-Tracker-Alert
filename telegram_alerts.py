"""
텔레그램 알람 엔진
- 지표별 차별화된 임계치(Threshold) 기반 알람
- 1시간 쿨다운(중복 방지)
- 3회 연속 오류 시 시스템 점검 필요 알림
- Replit Secrets (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) 사용
"""
import os
import json
import logging
import urllib.request
from datetime import datetime, timedelta

import pytz

log = logging.getLogger(__name__)
KST = pytz.timezone("Asia/Seoul")

# ── 임계치 그룹 정의 ─────────────────────────────────────────────
# indicator_key → (표시명, 임계치%, 단위)
THRESHOLDS: dict[str, tuple[str, float, str]] = {
    # [그룹 1: 거시 경제 핵심] ±3%
    "hy_index":        ("HY OA Index",       3.0, ""),
    "cp_30d":          ("CP Rate (A2/P2)",   3.0, ""),
    "jpy_1m":          ("JPY 1M 연율화비용",  3.0, "%"),
    "jpy_3m":          ("JPY 3M 연율화비용",  3.0, "%"),
    "jpy_3y":          ("JPY 3Y 연율화비용",  3.0, "%"),
    "jpy_7y":          ("JPY 7Y 연율화비용",  3.0, "%"),
    "jpy_10y":         ("JPY 10Y 연율화비용", 3.0, "%"),
    "us_13w":          ("US 13W T-Bill",     3.0, "%"),
    "us_2y":           ("US 2Y T-Note",      3.0, ""),
    "us_10y":          ("US 10Y Yield",      3.0, "%"),
    "japan_10y":       ("Japan 10Y JGB",     3.0, "%"),
    "japan_30y":       ("Japan 30Y JGB",     3.0, "%"),
    # [그룹 1B: 주요 주가지수] ±2%
    "kospi200":        ("KOSPI 200",         2.0, "pts"),
    "sp500":           ("S&P 500",           2.0, "pts"),
    "dji":             ("Dow Jones",         2.0, "pts"),
    # [그룹 2: 에너지 및 지수] ±4%
    "wti":             ("WTI Crude",         4.0, "USD/bbl"),
    "natural_gas":     ("Natural Gas",       4.0, "USD/mmBtu"),
    "nasdaq":          ("Nasdaq Futures",    4.0, "pts"),
    "dollar_index":    ("Dollar Index",      4.0, "pts"),
    "usd_krw":         ("USD/KRW",           4.0, "KRW"),
    # [그룹 3: 고변동 자산] ±5%
    "tqqq":            ("TQQQ",              5.0, "USD"),
    "sqqq":            ("SQQQ",              5.0, "USD"),
    "btc":             ("Bitcoin",           5.0, "USD"),
    "gold":            ("Gold",              5.0, "USD/oz"),
    "silver":          ("Silver",            5.0, "USD/oz"),
    # [그룹 4: 공포 지수] ±10%
    "vix":             ("VIX",              10.0, "pts"),
    "korea_cds":       ("Korea CDS 5Y",     10.0, "bps"),
    # [그룹 4B: 채권·신용 변동성] ±5%
    "move_index":      ("MOVE Index",        5.0, "pts"),
    # [그룹 5: 정책 금리] ±2%
    "effr":            ("EFFR",              2.0, "%"),
    "sofr":            ("SOFR",              2.0, "%"),
}

# Portfolio 심볼 → indicator_key 매핑
PORTFOLIO_KEY_MAP: dict[str, str] = {
    "CL=F":      "wti",
    "NG=F":      "natural_gas",
    "GC=F":      "gold",
    "SI=F":      "silver",
    "^IRX":      "us_13w",
    "DGS2":      "us_2y",
    "^TNX":      "us_10y",
    "Japan 10Y JGB": "japan_10y",
    "Japan 30Y JGB": "japan_30y",
    "^KS200":    "kospi200",
    "^GSPC":     "sp500",
    "^DJI":      "dji",
    "NQ=F":      "nasdaq",
    "TQQQ":      "tqqq",
    "SQQQ":      "sqqq",
    "^VIX":      "vix",
    "DX-Y.NYB":  "dollar_index",
    "KRW=X":     "usd_krw",
    "BTC-USD":   "btc",
    "Korea CDS 5Y": "korea_cds",
}

# ── 내부 상태 ────────────────────────────────────────────────────
_cooldown:       dict[str, datetime] = {}   # key → 마지막 알람 발송 시각(KST)
_error_counts:   dict[str, int]      = {}   # source → 연속 실패 횟수
_error_alerted:  dict[str, bool]     = {}   # source → 시스템 오류 알람 발송 여부

COOLDOWN_HOURS = 1         # 동일 지표 재알람 금지 시간(시)
ERROR_ALERT_THRESHOLD = 3  # 연속 오류 몇 번 시 시스템 알람

# ── 대시보드 URL ─────────────────────────────────────────────────
def _dashboard_url() -> str:
    domain = os.environ.get("REPLIT_DEV_DOMAIN", "")
    if domain:
        return f"https://{domain}/"
    return "https://replit.com"


# ── 텔레그램 발송 ────────────────────────────────────────────────
def send_raw(message: str) -> bool:
    """텔레그램으로 메시지를 직접 발송합니다."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id   = os.environ.get("TELEGRAM_CHAT_ID",   "")
    if not bot_token or not chat_id:
        log.warning("[Telegram] 환경변수 미설정 — 발송 건너뜀")
        return False
    try:
        url     = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = json.dumps({
            "chat_id":    chat_id,
            "text":       message,
            "parse_mode": "HTML",
        }).encode()
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
        log.info("[Telegram] 발송 성공")
        return True
    except Exception as exc:
        log.error(f"[Telegram] 발송 실패: {exc}")
        return False


# ── 쿨다운 체크 ─────────────────────────────────────────────────
def _is_cooled_down(key: str) -> bool:
    """True이면 쿨다운 중 → 알람 발송 금지."""
    last = _cooldown.get(key)
    if last is None:
        return False
    return (datetime.now(tz=KST) - last) < timedelta(hours=COOLDOWN_HOURS)


def _mark_sent(key: str) -> None:
    _cooldown[key] = datetime.now(tz=KST)


# ── 알람 메시지 포맷 ─────────────────────────────────────────────
def _build_message(name: str, current: float, previous: float,
                   change_pct: float, threshold: float, unit: str) -> str:
    now_kst = datetime.now(tz=KST).strftime("%Y-%m-%d %H:%M KST")
    direction = "상승 📈" if change_pct > 0 else "하락 📉"
    unit_str  = f" {unit}" if unit else ""
    return (
        f"🚨 <b>[금융 지표 변동 알람]</b>\n"
        f"● 지표명: <b>{name}</b>\n"
        f"● 현재가: <b>{current:.4f}{unit_str}</b>  ({change_pct:+.2f}% {direction})\n"
        f"● 이전가: {previous:.4f}{unit_str}\n"
        f"● 기준치: ±{threshold:.0f}% 초과 발생\n"
        f"● 업데이트: {now_kst}\n"
        f"🔗 <a href=\"{_dashboard_url()}\">대시보드 확인</a>"
    )


# ── 핵심 체크 함수 ───────────────────────────────────────────────
def check_and_alert(
    indicator_key: str,
    current: float | None,
    previous: float | None,
) -> bool:
    """
    지표 키에 해당하는 임계치와 비교해 알람 발송 여부를 결정합니다.
    반환: True = 알람 발송됨, False = 미발송
    """
    if indicator_key not in THRESHOLDS:
        return False
    if current is None or previous is None or previous == 0:
        return False

    name, threshold, unit = THRESHOLDS[indicator_key]
    change_pct = ((current - previous) / abs(previous)) * 100

    if abs(change_pct) <= threshold:
        return False

    if _is_cooled_down(indicator_key):
        log.debug(f"[Alert] {name} 쿨다운 중 — 발송 건너뜀")
        return False

    message = _build_message(name, current, previous, change_pct, threshold, unit)
    sent = send_raw(message)
    if sent:
        _mark_sent(indicator_key)
        log.info(f"[Alert] {name}: {change_pct:+.2f}% 변동 알람 발송")
    return sent


def check_portfolio_row(symbol: str, chg_pct: float | None, current: float | None,
                        previous: float | None) -> bool:
    """
    Portfolio 행에 대해 알람을 체크합니다.
    chg_pct = 전일 대비 변동률(%) — yfinance 제공값 사용.
    """
    key = PORTFOLIO_KEY_MAP.get(symbol)
    if not key or key not in THRESHOLDS:
        return False
    if chg_pct is None or current is None:
        return False

    name, threshold, unit = THRESHOLDS[key]
    if abs(chg_pct) <= threshold:
        return False
    if _is_cooled_down(key):
        log.debug(f"[Alert] {name} 쿨다운 중")
        return False

    prev = previous if previous is not None else current / (1 + chg_pct / 100)
    message = _build_message(name, current, prev, chg_pct, threshold, unit)
    sent = send_raw(message)
    if sent:
        _mark_sent(key)
        log.info(f"[Alert] Portfolio {name}: {chg_pct:+.2f}% 알람 발송")
    return sent


# ── 오류 카운터 ──────────────────────────────────────────────────
def record_success(source: str) -> None:
    """스크래핑/API 성공 시 오류 카운터를 리셋합니다."""
    if _error_counts.get(source, 0) > 0:
        log.info(f"[Alert] {source} 오류 카운터 리셋")
    _error_counts[source]  = 0
    _error_alerted[source] = False


def record_error(source: str, error_msg: str = "") -> None:
    """
    스크래핑/API 오류 시 카운터를 증가시키고,
    ERROR_ALERT_THRESHOLD 초과 시 시스템 알람을 발송합니다.
    """
    _error_counts[source] = _error_counts.get(source, 0) + 1
    count = _error_counts[source]
    log.warning(f"[Alert] {source} 오류 카운터: {count}/{ERROR_ALERT_THRESHOLD}")

    if count >= ERROR_ALERT_THRESHOLD and not _error_alerted.get(source, False):
        now_kst = datetime.now(tz=KST).strftime("%Y-%m-%d %H:%M KST")
        message = (
            f"⚠️ <b>[시스템 점검 필요]</b>\n"
            f"● 소스: <b>{source}</b>\n"
            f"● 연속 실패: {count}회\n"
            f"● 마지막 오류: {error_msg[:200] if error_msg else '상세 불명'}\n"
            f"● 시각: {now_kst}\n"
            f"🔗 <a href=\"{_dashboard_url()}\">대시보드 확인</a>"
        )
        sent = send_raw(message)
        if sent:
            _error_alerted[source] = True
            log.warning(f"[Alert] {source} 시스템 오류 알람 발송 완료")


# ── 편의 함수: FRED/NYFed 직접 체크 ─────────────────────────────
def check_fred(series_key: str, current: float | None, previous: float | None) -> bool:
    """series_key: 'hy_index' | 'cp_30d'"""
    return check_and_alert(series_key, current, previous)


def check_nyfed(indicator: str, current: float | None, previous: float | None) -> bool:
    """indicator: 'effr' | 'sofr'"""
    return check_and_alert(indicator, current, previous)


def check_jpy(period: str, annualized_yield: float | None,
              prev_yield: float | None) -> bool:
    """period: '1M' | '3M' | '3Y' | '7Y' | '10Y'"""
    key = f"jpy_{period.lower().replace('m','m').replace('y','y')}"
    return check_and_alert(key, annualized_yield, prev_yield)


# ── Inverse Turkey 전용 알람 ─────────────────────────────────────
# De-duplication: 24시간 이내 동일 상태 재발송 금지
#                 False→True 전환 시에만 발송 (True 지속은 1회만)
_INVERSE_TURKEY_COOLDOWN_HOURS = 24

_it_state: dict[str, bool] = {"prev": False}   # 이전 상태 추적


def alert_inverse_turkey(
    inv_turkey: bool,
    l1: float, l2: float, l3: float,
    total: float,
    inds: dict,
) -> bool:
    """
    Inverse Turkey 패턴 진입 시 텔레그램 알람 발송.

    트리거 조건:
      - inv_turkey == True 이고
      - 이전 상태가 False (False→True 전환) 이거나
      - 24시간 쿨다운 초과 (지속 알람)

    De-duplication:
      - 동일 True 상태에서 24시간 내 재발송 금지
      - True→False 전환 시 상태 리셋
    """
    _COOLDOWN_KEY = "inverse_turkey"

    # 상태 업데이트: False로 전환 시 쿨다운 리셋
    if not inv_turkey:
        if _it_state.get("prev", False):
            log.info("[Inverse Turkey] False로 전환 — 쿨다운 리셋")
            _cooldown.pop(_COOLDOWN_KEY, None)
        _it_state["prev"] = False
        return False

    # inv_turkey == True
    was_false = not _it_state.get("prev", False)
    _it_state["prev"] = True

    # 쿨다운 체크 (24시간)
    last = _cooldown.get(_COOLDOWN_KEY)
    if last is not None:
        elapsed = datetime.now(tz=KST) - last
        if elapsed < timedelta(hours=_INVERSE_TURKEY_COOLDOWN_HOURS):
            if not was_false:
                log.debug(f"[Inverse Turkey] 쿨다운 중 ({elapsed.seconds//3600}h/{_INVERSE_TURKEY_COOLDOWN_HOURS}h) — 발송 건너뜀")
                return False

    # 메시지 구성
    l1_norm = l1 / 45
    l2_norm = l2 / 30
    l3_norm = l3 / 15 if l3 > 0 else 0.0
    l12_avg = (l1_norm + l2_norm) / 2

    # 스트레스 지표 목록
    stressed = [v["name"] for v in inds.values() if v["tier"] in ("stress", "crisis")]
    stressed_str = " · ".join(stressed) if stressed else "—"

    now_kst = datetime.now(tz=KST).strftime("%Y-%m-%d %H:%M KST")
    trigger_type = "🔴 신규 진입" if was_false else "🔴 지속 (24h 경과)"

    message = (
        f"🚨 <b>[Inverse Turkey Alert]</b> {trigger_type}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"● 시각: {now_kst}\n"
        f"● TMRS: <b>{total:.1f}점</b>\n"
        f"\n"
        f"● Layer 1 (Deep):   {l1:.1f} / 45  ({l1_norm*100:.0f}%)\n"
        f"● Layer 2 (Middle): {l2:.1f} / 30  ({l2_norm*100:.0f}%)\n"
        f"● Layer 3 (Surface): {l3:.1f} / 15  ({l3_norm*100:.0f}%)\n"
        f"\n"
        f"● L1+L2 평균: <b>{l12_avg:.2f}</b>  (트리거 임계 ≥ 0.40)\n"
        f"● L3 정규화:  <b>{l3_norm:.2f}</b>  (트리거 임계 ≤ 0.25)\n"
        f"\n"
        f"● Stress 지표: {stressed_str}\n"
        f"\n"
        f"⚠️ 자금·신용시장에서 stress 누적 중, 주식시장은 아직 평온.\n"
        f"   표면에 드러나지 않은 위험이 내재된 상태입니다.\n"
        f"🔗 <a href=\"{_dashboard_url()}\">대시보드 확인</a>"
    )

    sent = send_raw(message)
    if sent:
        _cooldown[_COOLDOWN_KEY] = datetime.now(tz=KST)
        log.info(f"[Inverse Turkey] 알람 발송 완료 (L12={l12_avg:.2f}, L3={l3_norm:.2f})")
    return sent
