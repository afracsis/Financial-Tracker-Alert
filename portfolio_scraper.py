"""
Portfolio 종합 시장 스크래퍼
- yfinance: 에너지/원자재/금리/주식/FX/크립토
- FRED API: US 2Y T-Note (DGS2)
- CNBC API: Korea CDS 5Y
- Playwright: Japan 10Y JGB (Investing.com)
"""
import os
import re
import json
import asyncio
import logging
import shutil
import urllib.request
from datetime import datetime
from pathlib import Path

import pytz

log = logging.getLogger(__name__)
KST = pytz.timezone("Asia/Seoul")

# ── Chromium 경로 ────────────────────────────────────────────────
def _find_chromium() -> str | None:
    path = shutil.which("chromium") or shutil.which("chromium-browser")
    if path:
        return path
    nix_root = Path("/nix/store")
    if nix_root.exists():
        candidates = sorted(nix_root.glob("*-chromium-*/bin/chromium"), reverse=True)
        if candidates:
            return str(candidates[0])
    return None

CHROMIUM_PATH = _find_chromium()

# ── yfinance 티커 정의 ───────────────────────────────────────────
YFINANCE_TICKERS = [
    # (symbol, display_name, category, unit)
    ("CL=F",      "WTI Crude",        "Energy",   "USD/bbl"),
    ("NG=F",      "Natural Gas",      "Energy",   "USD/mmBtu"),
    ("GC=F",      "Gold",             "Metals",   "USD/oz"),
    ("SI=F",      "Silver",           "Metals",   "USD/oz"),
    ("^IRX",      "US 13W T-Bill",    "Rates",    "%"),
    # US 2Y T-Note은 FRED DGS2로 대체 (^ZT는 yfinance에서 제공 중단)
    ("^TNX",      "US 10Y Yield",     "Rates",    "%"),
    ("^KS200",    "KOSPI 200",        "Equity",   "pts"),
    ("^GSPC",     "S&P 500",          "Equity",   "pts"),
    ("^DJI",      "Dow Jones",        "Equity",   "pts"),
    ("NQ=F",      "Nasdaq Futures",   "Equity",   "pts"),
    ("TQQQ",      "TQQQ",             "Equity",   "USD"),
    ("SQQQ",      "SQQQ",             "Equity",   "USD"),
    ("^VIX",      "VIX",              "Equity",   "pts"),
    ("DX-Y.NYB",  "Dollar Index",     "FX",       "pts"),
    ("KRW=X",     "USD/KRW",          "FX",       "KRW"),
    ("BTC-USD",   "Bitcoin",          "Crypto",   "USD"),
]

SCRAPED_ITEMS = [
    "Japan 10Y JGB",
    "Japan 30Y JGB",
    "Korea CDS 5Y",
]

# Investing.com 페이지 URL
JAPAN_10Y_URL = "https://www.investing.com/rates-bonds/japan-10-year-bond-yield"
JAPAN_30Y_URL = "https://www.investing.com/rates-bonds/japan-30-year-bond-yield"
# Korea CDS 5Y: Investing.com Playwright (HTTP는 403, CNBC KOCDS5는 미지원)
# WGB는 JavaScript 로딩으로 HTTP scrape 불가, Playwright도 타임아웃
KOREA_CDS_URL = "https://www.investing.com/rates-bonds/south-korea-5-years-cds"
# 구 WGB URL (참조용 보존)
WGB_KOREA_CDS_URL = "https://worldgovernmentbonds.com/cds-historical-data/south-korea/5-years/"

# Spot 값 파싱 패턴
_PRICE_PATTERNS = [
    re.compile(r'data-test="instrument-price-last"[^>]*>\s*([\d,\.]+)\s*<'),
    re.compile(r'"last":\s*([\d\.]+)'),
    re.compile(r'id="last_last"[^>]*>\s*([\d,\.]+)\s*<'),
]
_CHANGE_PATTERNS = [
    re.compile(r'data-test="instrument-price-change"[^>]*>\s*([-\d,\.]+)\s*<'),
    re.compile(r'data-test="instrument-price-change-percent"[^>]*>\s*\(?([-\d\.]+)%?\)?\s*<'),
]
_CHANGE_PCT_PATTERNS = [
    re.compile(r'data-test="instrument-price-change-percent"[^>]*>[^(]*\(?([+-]?[\d\.]+)%?\)?\s*<'),
    re.compile(r'"changePercent":\s*([-\d\.]+)'),
]


def _parse_price(html: str) -> float | None:
    for pat in _PRICE_PATTERNS:
        m = pat.search(html)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                pass
    return None


def _parse_change(html: str) -> tuple[float | None, float | None]:
    chg = None
    pct = None
    for pat in _CHANGE_PATTERNS:
        m = pat.search(html)
        if m:
            try:
                chg = float(m.group(1).replace(",", ""))
                break
            except ValueError:
                pass
    for pat in _CHANGE_PCT_PATTERNS:
        m = pat.search(html)
        if m:
            try:
                pct = float(m.group(1).replace(",", ""))
                break
            except ValueError:
                pass
    return chg, pct


# ── FRED DGS2: US 2Y T-Note ─────────────────────────────────────
def fetch_fred_dgs2() -> dict:
    """FRED API에서 DGS2 (미국 2년물 국채 일일 수익률)를 가져옵니다."""
    now_kst = datetime.now(tz=KST).strftime("%Y-%m-%d %H:%M KST")
    api_key = os.environ.get("FRED_API_KEY", "")
    if not api_key:
        log.error("[Portfolio] FRED_API_KEY 없음 — DGS2 수집 불가")
        return _dgs2_empty(now_kst)

    url = (
        "https://api.stlouisfed.org/fred/series/observations"
        f"?series_id=DGS2&api_key={api_key}&file_type=json"
        "&sort_order=desc&limit=5"
    )
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())

        obs = [o for o in data.get("observations", []) if o.get("value", ".") != "."]
        if not obs:
            log.warning("[Portfolio] DGS2: 유효 관측값 없음")
            return _dgs2_empty(now_kst)

        last = float(obs[0]["value"])
        prev = float(obs[1]["value"]) if len(obs) >= 2 else None
        chg  = round(last - prev, 4) if prev is not None else None
        pct  = round((chg / prev) * 100, 2) if (prev and prev != 0) else None

        log.info(f"[Portfolio] DGS2 수집 완료: {last}% (전일비 {chg:+.4f})" if chg is not None else f"[Portfolio] DGS2 수집 완료: {last}%")
        return {
            "symbol":     "DGS2",
            "name":       "US 2Y T-Note",
            "category":   "Rates",
            "unit":       "%",
            "last":       round(last, 4),
            "chg":        chg,
            "chg_pct":    pct,
            "source":     "FRED",
            "updated_at": now_kst,
        }
    except Exception as exc:
        log.error(f"[Portfolio] DGS2 FRED 오류: {exc}")
        return _dgs2_empty(now_kst)


def _dgs2_empty(now_kst: str) -> dict:
    return {
        "symbol": "DGS2", "name": "US 2Y T-Note", "category": "Rates", "unit": "%",
        "last": None, "chg": None, "chg_pct": None, "source": "FRED", "updated_at": now_kst,
    }


def _safe_float(v) -> float | None:
    try:
        return float(v) if v not in (None, "", "N/A") else None
    except (TypeError, ValueError):
        return None


# ── WorldGovernmentBonds HTTP scrape: Korea CDS 5Y ───────────────
_WGB_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/138.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://worldgovernmentbonds.com/",
}
# 다양한 WGB 페이지 파싱 패턴
_WGB_PRICE_PATTERNS = [
    re.compile(r'class="[^"]*bold[^"]*">\s*([\d,\.]+)\s*<'),
    re.compile(r'CDS.*?:\s*([\d,\.]+)\s*bps', re.DOTALL),
    re.compile(r'<td[^>]*>\s*([\d,\.]+)\s*</td>.*?<td[^>]*>[0-9]{4}-[0-9]{2}-[0-9]{2}</td>', re.DOTALL),
    re.compile(r'dataValues\s*=\s*\[[^\]]*\[([\d\.]+)'),
    re.compile(r'"value"\s*:\s*([\d\.]+)'),
    re.compile(r'<th[^>]*>\s*([\d,\.]+)\s*</th>'),
]
_WGB_CHG_PATTERNS = [
    re.compile(r'([+-][\d,\.]+)\s*bps'),
    re.compile(r'([+-][\d,\.]+)\s*\(([+-]?[\d\.]+)%\)'),
]
_WGB_PCT_PATTERNS = [
    re.compile(r'\(([+-]?[\d\.]+)%\)'),
    re.compile(r'([+-]?[\d\.]+)%\s*</span>'),
]


def fetch_korea_cds_wgb() -> dict:
    """
    WorldGovernmentBonds.com에서 Korea CDS 5Y를 HTTP로 가져옵니다.
    실패 시 last=None / status='연결 시도 중'.
    """
    import ssl as _ssl
    now_kst = datetime.now(tz=KST).strftime("%Y-%m-%d %H:%M KST")
    try:
        _no_verify_ctx = _ssl.create_default_context()
        _no_verify_ctx.check_hostname = False
        _no_verify_ctx.verify_mode = _ssl.CERT_NONE
        req = urllib.request.Request(WGB_KOREA_CDS_URL, headers=_WGB_HEADERS)
        with urllib.request.urlopen(req, timeout=20, context=_no_verify_ctx) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        last = None
        for pat in _WGB_PRICE_PATTERNS:
            m = pat.search(html)
            if m:
                try:
                    v = float(m.group(1).replace(",", ""))
                    if 5 < v < 2000:   # 합리적인 CDS bps 범위
                        last = v
                        break
                except (ValueError, IndexError):
                    pass

        chg = None
        for pat in _WGB_CHG_PATTERNS:
            m = pat.search(html)
            if m:
                try:
                    chg = float(m.group(1).replace(",", ""))
                    break
                except (ValueError, IndexError):
                    pass

        pct = None
        for pat in _WGB_PCT_PATTERNS:
            m = pat.search(html)
            if m:
                try:
                    pct = float(m.group(1))
                    break
                except (ValueError, IndexError):
                    pass

        if last is None:
            log.warning(f"[Portfolio] WGB Korea CDS 파싱 실패 (HTML {len(html)}자)")
            # 디버그 저장
            try:
                with open("/tmp/wgb_korea_cds_debug.html", "w", encoding="utf-8") as f:
                    f.write(html)
            except Exception:
                pass
        else:
            log.info(f"[Portfolio] Korea CDS WGB 수집 완료: {last} bps")

        now_kst = datetime.now(tz=KST).strftime("%Y-%m-%d %H:%M KST")
        return {
            "symbol": "Korea CDS 5Y", "name": "Korea CDS 5Y",
            "category": "CDS", "unit": "bps",
            "last": last, "chg": chg, "chg_pct": pct,
            "source": "worldgovernmentbonds.com", "updated_at": now_kst,
            **({"status": "연결 시도 중"} if last is None else {}),
        }
    except Exception as exc:
        log.warning(f"[Portfolio] WGB Korea CDS 오류: {exc}")
        return {
            "symbol": "Korea CDS 5Y", "name": "Korea CDS 5Y",
            "category": "CDS", "unit": "bps",
            "last": None, "chg": None, "chg_pct": None,
            "source": "worldgovernmentbonds.com",
            "updated_at": datetime.now(tz=KST).strftime("%Y-%m-%d %H:%M KST"),
            "status": "연결 시도 중",
        }



# ── yfinance 데이터 수집 ─────────────────────────────────────────
def fetch_yfinance() -> list[dict]:
    """yfinance로 모든 티커의 최신 가격 + 전일비를 수집합니다."""
    try:
        import yfinance as yf
    except ImportError:
        log.error("[Portfolio] yfinance 미설치")
        return []

    symbols = [t[0] for t in YFINANCE_TICKERS]
    now_kst = datetime.now(tz=KST).strftime("%Y-%m-%d %H:%M KST")

    try:
        raw = yf.download(
            tickers=symbols,
            period="5d",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
    except Exception as exc:
        log.error(f"[Portfolio] yfinance download 오류: {exc}")
        return []

    results = []
    for symbol, name, category, unit in YFINANCE_TICKERS:
        try:
            if len(symbols) == 1:
                df = raw
            else:
                df = raw[symbol] if symbol in raw.columns.get_level_values(0) else None

            if df is None or df.empty or len(df) < 1:
                results.append(_empty_row(symbol, name, category, unit, now_kst))
                continue

            close_col = "Close"
            if close_col not in df.columns:
                results.append(_empty_row(symbol, name, category, unit, now_kst))
                continue

            closes = df[close_col].dropna()
            if len(closes) == 0:
                results.append(_empty_row(symbol, name, category, unit, now_kst))
                continue

            last = float(closes.iloc[-1])
            prev = float(closes.iloc[-2]) if len(closes) >= 2 else None
            chg  = round(last - prev, 4) if prev is not None else None
            pct  = round((chg / prev) * 100, 2) if (prev and prev != 0) else None

            results.append({
                "symbol":   symbol,
                "name":     name,
                "category": category,
                "unit":     unit,
                "last":     round(last, 4),
                "chg":      chg,
                "chg_pct":  pct,
                "source":   "yfinance",
                "updated_at": now_kst,
            })
        except Exception as exc:
            log.warning(f"[Portfolio] {symbol} 처리 오류: {exc}")
            results.append(_empty_row(symbol, name, category, unit, now_kst))

    return results


def _empty_row(symbol, name, category, unit, ts) -> dict:
    return {
        "symbol": symbol, "name": name, "category": category, "unit": unit,
        "last": None, "chg": None, "chg_pct": None,
        "source": "yfinance", "updated_at": ts,
    }


# ── Playwright 스크래핑 (Japan 10Y JGB + Korea CDS 5Y) ──────────
def _nowkst() -> str:
    return datetime.now(tz=KST).strftime("%Y-%m-%d %H:%M KST")


async def _scrape_investing_page(
    ctx, url: str, name: str,
    category: str = "Rates", unit: str = "%",
    source: str = "investing.com",
    networkidle: bool = False,
) -> dict:
    """Investing.com 페이지에서 가격/변동 추출."""
    try:
        log.info(f"[Playwright] {name}: 페이지 로드 시작 → {url}")
        page = await ctx.new_page()
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        if networkidle:
            # CDS 등 동적 로딩 페이지: domcontentloaded 후 JS 실행 완료 대기
            await page.goto(url, wait_until="domcontentloaded", timeout=35000)
            await asyncio.sleep(8)   # JS + AJAX 데이터 로딩 대기 8초
            # live DOM에서 JavaScript로 가격 추출 시도
            try:
                price_text = await page.evaluate("""() => {
                    const sels = [
                        '[data-test="instrument-price-last"]',
                        '#last_last',
                        '.instrument-price_last__KQzyA',
                        '.text-5xl',
                        '.text-4xl',
                        'span[class*="price"]:not(svg *)',
                        '[class*="lastPrice"]:not(svg *)',
                        '[class*="last-price"]:not(svg *)',
                    ];
                    for (const sel of sels) {
                        const el = document.querySelector(sel);
                        if (el) {
                            const txt = el.textContent.trim().replace(/,/g, '');
                            if (/^\\d+(\\.\\d+)?$/.test(txt)) return txt;
                        }
                    }
                    return null;
                }""")
                if price_text:
                    log.info(f"[Playwright] {name}: JS 평가로 가격 추출 → {price_text}")
            except Exception as eval_err:
                log.warning(f"[Playwright] {name}: JS 평가 실패 — {eval_err}")
                price_text = None
        else:
            await page.goto(url, wait_until="domcontentloaded", timeout=35000)
            price_text = None
            # 가격 요소가 나타날 때까지 최대 15초 대기
            try:
                await page.wait_for_selector(
                    '[data-test="instrument-price-last"], .instrument-price_last__KQzyA, '
                    '.text-2xl, [class*="last-price"], [class*="lastPrice"]',
                    timeout=15000,
                )
                log.info(f"[Playwright] {name}: 가격 셀렉터 발견")
            except Exception as sel_err:
                log.warning(f"[Playwright] {name}: 셀렉터 타임아웃 — 현재 HTML로 시도 ({sel_err})")
        await asyncio.sleep(3)  # JS 렌더링 대기 3초
        html = await page.content()
        await page.close()

        # networkidle 모드: JS 평가로 얻은 price_text를 우선 사용
        if networkidle and price_text:
            try:
                last = float(price_text)
            except ValueError:
                last = None
        else:
            last = _parse_price(html)
        chg, pct = _parse_change(html)
        # networkidle 모드에서도 HTML에서 못찾으면 재시도
        if last is None:
            last = _parse_price(html)

        if last is None:
            log.error(f"[Playwright] {name}: 가격 파싱 실패 — HTML {len(html)}자, "
                      f"첫 300자: {html[:300].replace(chr(10), ' ')}")
            try:
                fname = f"/tmp/invest_debug_{name.replace(' ', '_')}.html"
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(html)
                log.info(f"[Playwright] {name} 디버그 HTML → {fname}")
            except Exception:
                pass
        else:
            log.info(f"[Playwright] {name}: 수집 완료 last={last} chg={chg} pct={pct}%")

        return {
            "symbol": name, "name": name,
            "category": category, "unit": unit,
            "last": last, "chg": chg, "chg_pct": pct,
            "source": source, "updated_at": _nowkst(),
            **({"status": "연결 시도 중"} if last is None else {}),
        }
    except Exception as exc:
        log.error(f"[Playwright] {name} 스크래핑 오류: {type(exc).__name__}: {exc}")
        return {
            "symbol": name, "name": name,
            "category": category, "unit": unit,
            "last": None, "chg": None, "chg_pct": None,
            "source": source, "updated_at": _nowkst(), "status": "연결 시도 중",
        }


_WGB_CURRENT = re.compile(r'Current CDS:\s*<b>([\d,\.]+)</b>', re.IGNORECASE)
_WGB_WEEK_PCT = re.compile(r'w3-text-(?:red|teal)[^>]*>\s*([+-][\d,\.]+)\s*%\s*</td>')


async def _scrape_wgb_cds_page(ctx, url: str, name: str) -> dict:
    """WorldGovernmentBonds 페이지에서 CDS 데이터 추출 (Playwright).
    ※ CNBC KOCDS5는 심볼 미지원(404)으로 WGB를 사용합니다.
    """
    try:
        log.info(f"[Playwright] {name}: 페이지 로드 시작 → {url}")
        page = await ctx.new_page()
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        # WGB는 Partytown 서비스워커로 인해 60초가량 소요됨 — 65초 타임아웃
        await page.goto(url, wait_until="domcontentloaded", timeout=65000)
        # "Current CDS:" 텍스트가 나타날 때까지 최대 8초 대기
        try:
            await page.wait_for_selector("tfoot td", timeout=8000)
            log.info(f"[Playwright] {name}: tfoot 셀렉터 발견")
        except Exception as sel_err:
            log.warning(f"[Playwright] {name}: tfoot 셀렉터 타임아웃 — 현재 HTML로 시도 ({sel_err})")
        await asyncio.sleep(3)  # JS 렌더링 대기 3초
        html = await page.content()
        await page.close()

        # Current CDS 추출
        last = None
        m = _WGB_CURRENT.search(html)
        if m:
            try:
                last = float(m.group(1).replace(",", ""))
            except ValueError:
                pass

        # 1주일 변동률 추출 (첫 번째 색상 행)
        pct = None
        m2 = _WGB_WEEK_PCT.search(html)
        if m2:
            try:
                pct = float(m2.group(1).replace(",", ""))
            except ValueError:
                pass

        chg = round(last * pct / 100, 2) if (last and pct is not None) else None

        if last is None:
            log.error(f"[Playwright] WGB {name}: Current CDS 파싱 실패 — HTML {len(html)}자, "
                      f"'Current CDS' 포함 여부: {'Current CDS' in html}")
            try:
                fname = f"/tmp/wgb_debug_{name.replace(' ', '_')}.html"
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(html)
                log.info(f"[Playwright] {name} 디버그 HTML → {fname}")
            except Exception:
                pass
        else:
            log.info(f"[Playwright] Korea CDS WGB 수집 완료: {last} bps, pct={pct}%")

        return {
            "symbol": name, "name": name,
            "category": "CDS", "unit": "bps",
            "last": last, "chg": chg, "chg_pct": pct,
            "source": "worldgovernmentbonds.com", "updated_at": _nowkst(),
            **({"status": "연결 시도 중"} if last is None else {}),
        }
    except Exception as exc:
        log.error(f"[Playwright] WGB {name} 스크래핑 오류: {type(exc).__name__}: {exc}")
        return {
            "symbol": name, "name": name,
            "category": "CDS", "unit": "bps",
            "last": None, "chg": None, "chg_pct": None,
            "source": "worldgovernmentbonds.com", "updated_at": _nowkst(), "status": "연결 시도 중",
        }


def _make_empty_scraped(symbol, name, category, unit, source, now_kst) -> dict:
    return {"symbol": symbol, "name": name, "category": category, "unit": unit,
            "last": None, "chg": None, "chg_pct": None,
            "source": source, "updated_at": now_kst, "status": "연결 시도 중"}


async def _scrape_cds_intercept(ctx, url: str, name: str) -> dict:
    """Korea CDS 가격 수집 — Investing.com WebSocket + AJAX 응답 인터셉션 방식."""
    import json as _json
    captured: list[tuple[str, float, str]] = []

    _WS_PRICE = re.compile(
        r'"(?:last|bid|ask|close|price)"\s*:\s*"?([\d,\.]+)"?', re.IGNORECASE
    )

    def _check_text(text: str, src: str):
        for m in _WS_PRICE.finditer(text):
            try:
                fval = float(m.group(1).replace(",", ""))
                if 5.0 < fval < 500.0:
                    captured.append((m.group(0)[:40], fval, src[-60:]))
            except ValueError:
                pass

    async def _on_response(response):
        try:
            if "investing.com" not in response.url:
                return
            ct = response.headers.get("content-type", "")
            if "json" not in ct:
                return
            body = await response.body()
            text = body.decode("utf-8", errors="replace")
            _check_text(text, f"xhr:{response.url}")
        except Exception:
            pass

    def _on_websocket(ws):
        def _on_frame(frame):
            try:
                _check_text(str(frame.payload), f"ws:{ws.url}")
            except Exception:
                pass
        ws.on("framereceived", _on_frame)

    try:
        log.info(f"[Playwright] {name}: WS+XHR 인터셉션 시작 → {url}")
        page = await ctx.new_page()
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page.on("response", _on_response)
        page.on("websocket", _on_websocket)
        await page.goto(url, wait_until="domcontentloaded", timeout=35000)
        await asyncio.sleep(10)  # WebSocket 연결 + 가격 스트리밍 대기 10초

        if captured:
            log.info(f"[Playwright] {name}: 인터셉션 가격 후보 {len(captured)}개 — {captured[:3]}")
        else:
            log.warning(f"[Playwright] {name}: WS/XHR 인터셉션 가격 미수집")

        # JS evaluate 시도 (DOM 직접 조회)
        price_text = None
        try:
            price_text = await page.evaluate("""() => {
                const sels = [
                    '[data-test=\"instrument-price-last\"]',
                    '#last_last',
                    '.instrument-price_last__KQzyA',
                    '.text-5xl', '.text-4xl',
                    '[class*=\"lastPrice\"]:not(svg *)',
                    '[class*=\"last-price\"]:not(svg *)',
                ];
                for (const sel of sels) {
                    const el = document.querySelector(sel);
                    if (el) {
                        const txt = el.textContent.trim().replace(/,/g, '');
                        if (/^\\d+(\\.\\d+)?$/.test(txt)) return txt;
                    }
                }
                return null;
            }""")
        except Exception as eval_err:
            log.warning(f"[Playwright] {name}: JS 평가 실패 — {eval_err}")

        html = await page.content()
        await page.close()

        last = None
        if price_text:
            try:
                last = float(price_text)
                log.info(f"[Playwright] {name}: JS evaluate 가격 → {last}")
            except ValueError:
                pass
        if last is None and captured:
            last = captured[0][1]
            log.info(f"[Playwright] {name}: 인터셉션 가격 사용 → {last}")
        if last is None:
            last = _parse_price(html)
        chg, pct = _parse_change(html)

        if last is None:
            log.error(f"[Playwright] {name}: 모든 방법 실패 — HTML {len(html)}자")
            try:
                fname = f"/tmp/invest_debug_{name.replace(' ', '_')}.html"
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(html)
            except Exception:
                pass
        else:
            log.info(f"[Playwright] {name}: 수집 완료 last={last} chg={chg} pct={pct}%")

        return {
            "symbol": name, "name": name,
            "category": "CDS", "unit": "bps",
            "last": last, "chg": chg, "chg_pct": pct,
            "source": "investing.com(CDS)", "updated_at": _nowkst(),
            **({"status": "연결 시도 중"} if last is None else {}),
        }
    except Exception as exc:
        log.error(f"[Playwright] {name} 인터셉션 오류: {type(exc).__name__}: {exc}")
        return {
            "symbol": name, "name": name,
            "category": "CDS", "unit": "bps",
            "last": None, "chg": None, "chg_pct": None,
            "source": "investing.com(CDS)", "updated_at": _nowkst(), "status": "연결 시도 중",
        }


async def _scrape_all_async() -> list[dict]:
    """Japan 10Y/30Y JGB (Investing.com) + Korea CDS 5Y (WGB) — Playwright 병렬 스크래핑."""
    now_kst = _nowkst()
    if not CHROMIUM_PATH:
        log.error("[Portfolio] Chromium 없음 — Playwright 스크래핑 건너뜀")
        return [
            _make_empty_scraped("Japan 10Y JGB", "Japan 10Y JGB", "Rates", "%", "investing.com", now_kst),
            _make_empty_scraped("Japan 30Y JGB", "Japan 30Y JGB", "Rates", "%", "investing.com", now_kst),
            _make_empty_scraped("Korea CDS 5Y",  "Korea CDS 5Y",  "CDS",   "bps", "worldgovernmentbonds.com", now_kst),
        ]

    from playwright.async_api import async_playwright  # type: ignore

    ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/138.0.0.0 Safari/537.36"
    )
    # JGB용 브라우저 (Investing.com 최적화)
    _jgb_args = [
        "--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled", "--disable-gpu", "--no-zygote",
        "--disable-extensions", "--disable-background-networking",
        "--disable-default-apps", "--mute-audio", "--disable-sync",
    ]
    # WGB용 브라우저 — Partytown 서비스워커를 위해 --disable-background-networking 제외
    _wgb_args = [
        "--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled", "--disable-gpu", "--no-zygote",
        "--disable-default-apps", "--mute-audio", "--disable-sync",
    ]

    async with async_playwright() as p:
        browser_jgb = await p.chromium.launch(
            executable_path=CHROMIUM_PATH, headless=True, args=_jgb_args,
        )
        browser_wgb = await p.chromium.launch(
            executable_path=CHROMIUM_PATH, headless=True, args=_wgb_args,
        )
        ctx_inv10 = await browser_jgb.new_context(
            user_agent=ua, locale="en-US",
            viewport={"width": 1280, "height": 900},
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        ctx_inv30 = await browser_jgb.new_context(
            user_agent=ua, locale="en-US",
            viewport={"width": 1280, "height": 900},
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        ctx_wgb = await browser_wgb.new_context(
            user_agent=ua, locale="en-US",
            viewport={"width": 1280, "height": 900},
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
            ignore_https_errors=True,
        )
        _empty_cds = {
            "symbol": "Korea CDS 5Y", "name": "Korea CDS 5Y",
            "category": "CDS", "unit": "bps",
            "last": None, "chg": None, "chg_pct": None,
            "source": "worldgovernmentbonds.com", "updated_at": _nowkst(),
            "status": "연결 시도 중",
        }

        _empty_jgb10 = _make_empty_scraped(
            "Japan 10Y JGB", "Japan 10Y JGB", "Rates", "%", "investing.com", _nowkst()
        )
        _empty_jgb30 = _make_empty_scraped(
            "Japan 30Y JGB", "Japan 30Y JGB", "Rates", "%", "investing.com", _nowkst()
        )

        async def _jgb10_with_timeout():
            try:
                # goto 35s + wait_for_selector 15s + sleep 3s → 55초 개별 타임아웃
                return await asyncio.wait_for(
                    _scrape_investing_page(ctx_inv10, JAPAN_10Y_URL, "Japan 10Y JGB",
                                           category="Rates", unit="%"),
                    timeout=55,
                )
            except asyncio.TimeoutError:
                log.error("[Playwright] Japan 10Y JGB: 55초 개별 타임아웃 — 빈 결과 반환")
                return _empty_jgb10
            except Exception as exc:
                log.error(f"[Playwright] Japan 10Y JGB: 오류 — {exc}")
                return _empty_jgb10

        async def _jgb30_with_timeout():
            try:
                # goto 35s + wait_for_selector 15s + sleep 3s → 55초 개별 타임아웃
                return await asyncio.wait_for(
                    _scrape_investing_page(ctx_inv30, JAPAN_30Y_URL, "Japan 30Y JGB",
                                           category="Rates", unit="%"),
                    timeout=55,
                )
            except asyncio.TimeoutError:
                log.error("[Playwright] Japan 30Y JGB: 55초 개별 타임아웃 — 빈 결과 반환")
                return _empty_jgb30
            except Exception as exc:
                log.error(f"[Playwright] Japan 30Y JGB: 오류 — {exc}")
                return _empty_jgb30

        async def _cds_with_timeout():
            try:
                # WGB Playwright: 65초 goto + 8초 대기 → 85초 개별 타임아웃
                return await asyncio.wait_for(
                    _scrape_wgb_cds_page(ctx_wgb, WGB_KOREA_CDS_URL, "Korea CDS 5Y"),
                    timeout=85,
                )
            except asyncio.TimeoutError:
                log.error("[Playwright] Korea CDS 5Y: 85초 개별 타임아웃 — 빈 결과 반환")
                return _empty_cds

        try:
            japan10_result, japan30_result, korea_result = await asyncio.gather(
                _jgb10_with_timeout(),
                _jgb30_with_timeout(),
                _cds_with_timeout(),
            )
            return [japan10_result, japan30_result, korea_result]
        finally:
            await browser_jgb.close()
            await browser_wgb.close()


def _run_playwright_scrape() -> list[dict]:
    """별도 스레드에서 asyncio.run()으로 Playwright 실행 (타임아웃 래퍼용)."""
    return asyncio.run(_scrape_all_async())


def fetch_scraped() -> list[dict]:
    """동기 인터페이스: Japan 10Y/30Y JGB + Korea CDS 5Y Playwright 스크래핑.
    최대 160초 하드 타임아웃 적용 — 초과 시 빈 결과 반환.
    (Korea CDS는 별도 85초 개별 타임아웃; WGB Partytown으로 인해 60초 필요)
    """
    import concurrent.futures
    now_kst = _nowkst()
    _empty = [
        _make_empty_scraped("Japan 10Y JGB", "Japan 10Y JGB", "Rates", "%", "investing.com", now_kst),
        _make_empty_scraped("Japan 30Y JGB", "Japan 30Y JGB", "Rates", "%", "investing.com", now_kst),
        _make_empty_scraped("Korea CDS 5Y",  "Korea CDS 5Y",  "CDS",   "bps", "worldgovernmentbonds.com", now_kst),
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_playwright_scrape)
        try:
            return future.result(timeout=160)
        except concurrent.futures.TimeoutError:
            log.error("[Portfolio] Playwright 스크래핑 160초 초과 — 타임아웃, 빈 결과 반환")
            return _empty
        except Exception as exc:
            log.error(f"[Portfolio] 스크래핑 오류: {exc}")
            return _empty


# ── FRED Japan 10Y Fallback ──────────────────────────────────────
def _fetch_fred_japan10y() -> dict | None:
    """FRED IRLTLT01JPM156N: 일본 10Y 국채 수익률 (월별, Playwright 실패 시 fallback).
    yfinance·CNBC·Stooq 모두 JGB 미지원으로 FRED 월별 데이터를 사용합니다.
    """
    now_kst = _nowkst()
    api_key = os.environ.get("FRED_API_KEY", "")
    if not api_key:
        return None
    url = (
        "https://api.stlouisfed.org/fred/series/observations"
        f"?series_id=IRLTLT01JPM156N&api_key={api_key}&file_type=json"
        "&sort_order=desc&limit=3"
    )
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        obs = [o for o in data.get("observations", []) if o.get("value", ".") != "."]
        if not obs:
            return None
        last = float(obs[0]["value"])
        prev = float(obs[1]["value"]) if len(obs) >= 2 else None
        chg  = round(last - prev, 4) if prev is not None else None
        pct  = round((chg / prev) * 100, 2) if (prev and prev != 0) else None
        log.info(f"[Portfolio] Japan 10Y FRED fallback: {last}% (월별, {obs[0]['date']})")
        return {
            "symbol": "Japan 10Y JGB", "name": "Japan 10Y JGB",
            "category": "Rates", "unit": "%",
            "last": round(last, 4), "chg": chg, "chg_pct": pct,
            "source": "FRED(월별)", "updated_at": now_kst,
        }
    except Exception as exc:
        log.error(f"[Portfolio] Japan 10Y FRED fallback 오류: {exc}")
        return None


# ── 통합 수집 ────────────────────────────────────────────────────
def fetch_all() -> dict:
    """
    yfinance + FRED(DGS2) + Playwright(Japan 10Y/30Y JGB, Korea CDS 5Y/WGB)를
    통합해 반환합니다.
    - JGB 10Y: Playwright(Investing.com) 우선, 실패 시 FRED 월별 fallback
    - JGB 30Y: Playwright(Investing.com) 전용
    - Korea CDS: Playwright(WGB) 전용 (CNBC KOCDS5 미지원)
    반환: {"rows": [...], "updated_at": "2026-..."}
    """
    log.info("[Portfolio] 전체 데이터 수집 시작")
    yf_rows      = fetch_yfinance()
    dgs2_row     = fetch_fred_dgs2()
    scraped_rows = fetch_scraped()  # [Japan 10Y JGB, Japan 30Y JGB, Korea CDS 5Y]

    japan10_row = scraped_rows[0] if len(scraped_rows) > 0 else None
    japan30_row = scraped_rows[1] if len(scraped_rows) > 1 else None
    cds_row     = scraped_rows[2] if len(scraped_rows) > 2 else None

    # JGB 10Y fallback: Playwright 실패 시 FRED 월별 데이터 사용
    if japan10_row is None or japan10_row.get("last") is None:
        fred_japan10 = _fetch_fred_japan10y()
        if fred_japan10:
            japan10_row = fred_japan10
            log.info("[Portfolio] Japan 10Y: FRED fallback 사용")

    # 삽입 순서:
    # ^IRX → DGS2(US 2Y) → ^TNX → Japan 10Y JGB → Japan 30Y JGB → ... → Korea CDS 5Y (맨 끝)
    combined = []
    for row in yf_rows:
        combined.append(row)
        if row["symbol"] == "^IRX":
            combined.append(dgs2_row)           # US 2Y T-Note (FRED)
        elif row["symbol"] == "^TNX":
            if japan10_row:
                combined.append(japan10_row)    # Japan 10Y JGB
            if japan30_row:
                combined.append(japan30_row)    # Japan 30Y JGB

    if cds_row:
        combined.append(cds_row)               # Korea CDS 5Y — 맨 끝

    now_kst = _nowkst()
    log.info(f"[Portfolio] 수집 완료: {len(combined)}개 지표")
    return {"rows": combined, "updated_at": now_kst}
