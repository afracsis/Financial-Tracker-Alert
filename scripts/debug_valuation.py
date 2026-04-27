"""
디버그 스크립트 — ERP / Buffett / CAPE 수집 진단

Replit 에서 실행:
    cd ~/workspace && python scripts/debug_valuation.py

출력 내용:
    1) 네트워크 접근 가능성 (multpl.com, GitHub)
    2) 각 함수별 수집 결과 + 에러 메시지
    3) DB 현황
    4) TMRS snapshot 키 확인
"""

import sys
import os
import sqlite3
import urllib.request
import re
import html

# ── 경로 설정 (dashboard/ 하위에서 실행되는 경우 대비) ─────────────
_this_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_this_dir)
sys.path.insert(0, _root_dir)

DB_PATH = os.path.join(_root_dir, "data.db")

print("=" * 60)
print("Financial Tracker — Valuation 디버그 스크립트")
print("=" * 60)


# ── 1. 네트워크 테스트 ──────────────────────────────────────────────
def http_get(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return body, None
    except Exception as e:
        return None, str(e)


print("\n[1] 네트워크 연결 테스트")
_URLS = [
    ("multpl.com PE",    "https://www.multpl.com/s-p-500-pe-ratio/table/by-month"),
    ("multpl.com CAPE",  "https://www.multpl.com/shiller-pe/table/by-month"),
    ("GitHub datasets",  "https://raw.githubusercontent.com/datasets/s-and-p-500/master/data/monthly.csv"),
    ("FRED DGS10 API",   f"https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&limit=3&api_key={os.environ.get('FRED_API_KEY','MISSING')}"),
]

for name, url in _URLS:
    body, err = http_get(url, timeout=10)
    if err:
        print(f"  ❌ {name}: {err}")
    else:
        print(f"  ✅ {name}: {len(body)}자 수신 | 첫줄: {body[:120].replace(chr(10),' ')}")


# ── 2. multpl.com PE HTML 파싱 진단 ────────────────────────────────
def parse_multpl(body):
    """app.py _parse_multpl_table() 와 동일 로직 (HTML entity + † 대응)."""
    found = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.DOTALL):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL)
        if len(cells) < 2:
            continue
        d_text  = re.sub(r"<[^>]+>", "", cells[0]).strip()
        val_raw = html.unescape(re.sub(r"<[^>]+>", "", cells[1]))
        val_m   = re.search(r"-?[\d]+\.?[\d]*", val_raw)
        if val_m:
            found.append((d_text, val_m.group(), val_raw.strip()))
    return found


print("\n[2] multpl.com S&P 500 PE HTML 파싱 (HTML entity 대응)")
body, err = http_get("https://www.multpl.com/s-p-500-pe-ratio/table/by-month")
if err:
    print(f"  ❌ HTTP 오류: {err}")
else:
    found = parse_multpl(body)
    print(f"  파싱된 행 수: {len(found)}")
    for d, v, raw in found[:5]:
        print(f"  날짜: '{d}' | raw: {repr(raw[:30])} | float: {v}")
    if not found:
        print(f"  ⚠️  tr/td 구조를 찾지 못함. HTML 샘플:\n{body[2000:3000]}")


# ── 3. multpl.com CAPE HTML 파싱 진단 ──────────────────────────────
print("\n[3] multpl.com Shiller CAPE HTML 파싱 (HTML entity 대응)")
body, err = http_get("https://www.multpl.com/shiller-pe/table/by-month")
if err:
    print(f"  ❌ HTTP 오류: {err}")
else:
    found = parse_multpl(body)
    print(f"  파싱된 행 수: {len(found)}")
    for d, v, raw in found[:5]:
        print(f"  날짜: '{d}' | raw: {repr(raw[:30])} | float: {v}")
    if not found:
        print(f"  ⚠️  tr/td 구조를 찾지 못함. HTML 샘플:\n{body[2000:3000]}")


# ── 4. GitHub datasets monthly.csv 파싱 진단 ───────────────────────
print("\n[4] GitHub datasets/s-and-p-500 monthly.csv 파싱")
body, err = http_get("https://raw.githubusercontent.com/datasets/s-and-p-500/master/data/monthly.csv")
if err:
    print(f"  ❌ HTTP 오류: {err}")
else:
    lines = body.strip().split("\n")
    print(f"  총 행 수: {len(lines)}")
    print(f"  헤더: {lines[0]}")
    print(f"  최근 3행:")
    for l in lines[-3:]:
        print(f"    {l}")


# ── 5. yfinance SPY PE 테스트 ──────────────────────────────────────
print("\n[5] yfinance SPY trailingPE")
try:
    import yfinance as yf
    info = yf.Ticker("SPY").info
    pe = info.get("trailingPE")
    fpe = info.get("forwardPE")
    print(f"  trailingPE: {pe}")
    print(f"  forwardPE:  {fpe}")
except ImportError:
    print("  ❌ yfinance 미설치")
except Exception as e:
    print(f"  ❌ 오류: {e}")


# ── 6. FRED DGS10 테스트 ──────────────────────────────────────────
print("\n[6] FRED DGS10 (10Y Treasury)")
api_key = os.environ.get("FRED_API_KEY", "")
if not api_key:
    print("  ❌ FRED_API_KEY 환경변수 없음")
else:
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&limit=3&sort_order=desc&file_type=json&api_key={api_key}"
    body, err = http_get(url)
    if err:
        print(f"  ❌ 오류: {err}")
    else:
        import json
        try:
            data = json.loads(body)
            obs = data.get("observations", [])
            print(f"  최근 {len(obs)}건:")
            for o in obs:
                print(f"    {o['date']}: {o['value']}")
        except Exception as e:
            print(f"  ❌ 파싱 오류: {e} | 응답: {body[:200]}")


# ── 7. DB 현황 ──────────────────────────────────────────────────────
print("\n[7] DB 현황")
if not os.path.exists(DB_PATH):
    print(f"  ❌ DB 파일 없음: {DB_PATH}")
else:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    for tbl in ("valuation_erp", "valuation_buffett", "valuation_cape"):
        try:
            cnt = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            latest = conn.execute(f"SELECT * FROM {tbl} ORDER BY date DESC LIMIT 1").fetchone()
            print(f"  {tbl}: {cnt}건", end="")
            if latest:
                print(f" | 최신: {dict(latest)}")
            else:
                print()
        except Exception as e:
            print(f"  {tbl}: ❌ {e}")
    conn.close()


# ── 8. TMRS 최신 snapshot 키 확인 ─────────────────────────────────
print("\n[8] TMRS 최신 snapshot 키 (valuation 포함 여부)")
if os.path.exists(DB_PATH):
    import json as _json
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT calculated_at, snapshot FROM tmrs_scores ORDER BY calculated_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if row:
        snap = _json.loads(row["snapshot"] or "{}")
        print(f"  계산 시각: {row['calculated_at']}")
        print(f"  snapshot 키 ({len(snap)}개): {sorted(snap.keys())}")
        for key in ("erp", "buffett", "cape"):
            if key in snap:
                print(f"  ✅ {key}: {snap[key]}")
            else:
                print(f"  ❌ {key}: MISSING")
    else:
        print("  tmrs_scores 데이터 없음")

print("\n" + "=" * 60)
print("진단 완료. 위 결과를 TW에게 공유해주세요.")
print("=" * 60)
