"""
JPY 외환 포워드 레이트 + Spot Rate 스크래퍼
- investing.com/currencies/usd-jpy-forward-rates  → 포워드 포인트 (1M/3M/3Y/7Y/10Y)
- investing.com/currencies/usd-jpy                → 현물 환율 (Spot Rate)
"""
import re
import asyncio
import logging
import shutil
from pathlib import Path

log = logging.getLogger(__name__)

TARGET_PERIODS = {"1M", "3M", "3Y", "7Y", "10Y"}
INVEST_FWD_URL  = "https://www.investing.com/currencies/usd-jpy-forward-rates"
INVEST_SPOT_URL = "https://www.investing.com/currencies/usd-jpy"

# ── Chromium 실행 경로 탐색 ─────────────────────────────────────
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
log.info(f"[jpy_scraper] Chromium: {CHROMIUM_PATH}")


# ── 포워드 레이트 파싱 ───────────────────────────────────────────
_ROW_RE = re.compile(
    r'USDJPY&nbsp;(\w+)&nbsp;FWD</td>'
    r'<td id="bid_\d+">([\d\.\-]+)</td>'
    r'<td id="ask_\d+">[^<]*</td>'
    r'<td id="high_\d+">[^<]*</td>'
    r'<td id="low_\d+">[^<]*</td>'
    r'<td[^>]*id="change_\d+">([\d\.\-]+)</td>'
)

# ── Spot Rate 파싱 (여러 패턴 시도) ─────────────────────────────
_SPOT_PATTERNS = [
    re.compile(r'data-test="instrument-price-last"[^>]*>\s*([\d,\.]+)\s*<'),
    re.compile(r'"last":\s*([\d\.]+)'),
    re.compile(r'id="last_last"[^>]*>\s*([\d,\.]+)\s*<'),
    re.compile(r'"price":\s*([\d\.]+).*?"symbol":\s*"USDJPY"', re.DOTALL),
    re.compile(r'<span[^>]*class="[^"]*instrument-price[^"]*"[^>]*>\s*([\d,\.]+)\s*</span>'),
]


def parse_forward(html: str) -> dict | None:
    result = {}
    for m in _ROW_RE.finditer(html):
        period = m.group(1)
        if period in TARGET_PERIODS:
            try:
                result[period] = {
                    "bid":    float(m.group(2)),
                    "change": float(m.group(3)),
                }
            except ValueError:
                pass
    return result or None


def parse_spot(html: str) -> float | None:
    for pat in _SPOT_PATTERNS:
        m = pat.search(html)
        if m:
            try:
                val = float(m.group(1).replace(",", ""))
                if 100 <= val <= 200:    # USD/JPY 현실적 범위 검증
                    log.info(f"[jpy_scraper] Spot Rate 파싱 성공: {val}")
                    return val
            except ValueError:
                pass
    return None


# ── Playwright 스크래퍼 ─────────────────────────────────────────
async def _scrape_async() -> dict | None:
    """비동기 스크래퍼. 포워드 레이트 + Spot Rate를 함께 수집합니다."""
    if not CHROMIUM_PATH:
        log.error("[jpy_scraper] Chromium 실행 파일을 찾을 수 없습니다.")
        return None

    from playwright.async_api import async_playwright  # type: ignore

    launch_args = [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
        "--disable-extensions",
        "--disable-gpu",
    ]
    ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/138.0.0.0 Safari/537.36"
    )
    ctx_kwargs = dict(
        user_agent=ua,
        locale="en-US",
        viewport={"width": 1280, "height": 900},
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        },
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=CHROMIUM_PATH,
            headless=True,
            args=launch_args,
        )
        try:
            # ── 1. 포워드 레이트 페이지 ────────────────────────────
            ctx = await browser.new_context(**ctx_kwargs)
            page = await ctx.new_page()
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            log.info("[jpy_scraper] 포워드 레이트 페이지 로드 시작...")
            await page.goto(INVEST_FWD_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(4)
            fwd_html = await page.content()
            log.info(f"[jpy_scraper] 포워드 HTML 수신: {len(fwd_html):,}자")

            forward_data = parse_forward(fwd_html)
            if forward_data:
                log.info(f"[jpy_scraper] 포워드 파싱 성공: {list(forward_data.keys())}")
            else:
                log.warning("[jpy_scraper] 포워드 데이터 파싱 실패")

            # 포워드 페이지에서 Spot Rate 시도
            spot_rate = parse_spot(fwd_html)

            # ── 2. Spot Rate 페이지 (포워드 페이지에서 못 찾은 경우) ──
            if spot_rate is None:
                log.info("[jpy_scraper] Spot Rate 별도 페이지 로드 시작...")
                spot_page = await ctx.new_page()
                await spot_page.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                )
                try:
                    await spot_page.goto(INVEST_SPOT_URL, wait_until="domcontentloaded", timeout=25000)
                    await asyncio.sleep(3)
                    spot_html = await spot_page.content()
                    log.info(f"[jpy_scraper] Spot HTML 수신: {len(spot_html):,}자")
                    spot_rate = parse_spot(spot_html)
                    if spot_rate:
                        log.info(f"[jpy_scraper] Spot Rate (별도 페이지): {spot_rate}")
                    else:
                        log.warning("[jpy_scraper] Spot Rate 파싱 실패 — 두 페이지 모두 불가")
                except Exception as exc:
                    log.error(f"[jpy_scraper] Spot 페이지 오류: {exc}")
                finally:
                    await spot_page.close()

            if not forward_data:
                return None

            return {
                "forward":   forward_data,
                "spot_rate": spot_rate,
            }

        except Exception as exc:
            log.error(f"[jpy_scraper] 오류: {exc}")
            return None
        finally:
            await browser.close()


def scrape_jpy_forward() -> dict | None:
    """
    동기 인터페이스.
    반환: {"forward": {period: {bid, change}}, "spot_rate": float|None}
    실패: None
    """
    try:
        return asyncio.run(_scrape_async())
    except Exception as exc:
        log.error(f"[jpy_scraper] asyncio.run 오류: {exc}")
        return None
