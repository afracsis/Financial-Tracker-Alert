"""Stage 2.2: CP-EFFR vs A2/P2-AA Spread redundancy analysis.

Two data sources (tried in order):
  1. PRIMARY — tmrs_scores.snapshot JSON (always available if TMRS has run)
     Extracts cp_effr.value and cp_aa_spread.value from each snapshot row.
  2. FALLBACK — raw tables: cp_30d, nyfed_effr, aa_manual
     Used only if snapshot method yields < 10 data points.

Computes Pearson correlation (level + daily changes) between:
  - cp_effr     : A2/P2 CP − EFFR  (pp)
  - cp_aa_spread: A2/P2 CP − AA CP  (bp)

Decision thresholds (both correlations):
  > 0.80        → full redundancy → keep cap=0
  0.50 – 0.80   → partial        → cap=2
  < 0.50        → independent    → cap=3
  mixed         → report to TW

Usage (on Replit shell):
    python scripts/analyze_cp_effr.py
"""

import json
import os
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data.db")


def _require_pandas():
    try:
        import pandas as pd
        return pd
    except ImportError:
        print("pandas not installed — running without rolling correlation.")
        return None


# ── Method 1: extract from tmrs_scores.snapshot ───────────────────────────

def from_snapshots(conn: sqlite3.Connection):
    rows = conn.execute(
        "SELECT calculated_at, snapshot FROM tmrs_scores ORDER BY calculated_at"
    ).fetchall()

    records = []
    for row in rows:
        date = row["calculated_at"][:10]
        snap = json.loads(row["snapshot"] or "{}")
        if "cp_effr" in snap and "cp_aa_spread" in snap:
            cp_effr_v = snap["cp_effr"].get("value")
            cp_aa_v   = snap["cp_aa_spread"].get("value")
            if cp_effr_v is not None and cp_aa_v is not None:
                records.append({
                    "date":       date,
                    "cp_effr":    float(cp_effr_v),
                    "cp_aa":      float(cp_aa_v),
                })

    # deduplicate by date (keep latest per day)
    seen: dict = {}
    for r in records:
        seen[r["date"]] = r
    return sorted(seen.values(), key=lambda x: x["date"])


# ── Method 2: raw tables ───────────────────────────────────────────────────

def from_raw_tables(conn: sqlite3.Connection):
    cp30 = {r["date"]: r["value"]
            for r in conn.execute(
                "SELECT date, value FROM cp_30d ORDER BY date").fetchall()}
    effr = {r["date"]: r["rate"]
            for r in conn.execute(
                "SELECT date, rate FROM nyfed_effr ORDER BY date").fetchall()}
    aa   = {r["date"]: r["value"]
            for r in conn.execute(
                "SELECT date, value FROM aa_manual ORDER BY date").fetchall()}

    records = []
    for date in sorted(set(cp30) & set(effr) & set(aa)):
        cp_effr_v = round(cp30[date] - effr[date], 4)
        cp_aa_v   = round((cp30[date] - aa[date]) * 100, 4)   # pp → bp
        records.append({"date": date, "cp_effr": cp_effr_v, "cp_aa": cp_aa_v})
    return records


# ── correlation helpers ───────────────────────────────────────────────────

def pearson(xs, ys) -> float:
    n = len(xs)
    if n < 2:
        return float("nan")
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx  = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy  = sum((y - my) ** 2 for y in ys) ** 0.5
    if dx == 0 or dy == 0:
        return float("nan")
    return num / (dx * dy)


def diff_series(vals: list) -> list:
    return [vals[i] - vals[i - 1] for i in range(1, len(vals))]


# ── main ──────────────────────────────────────────────────────────────────

def main() -> None:
    if not os.path.exists(DB_PATH):
        print(f"ERROR: DB not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Method 1
    records = from_snapshots(conn)
    source  = "tmrs_scores.snapshot"

    # Fallback to Method 2 if too few rows
    if len(records) < 10:
        print(f"snapshot method: {len(records)} rows — 부족, raw tables로 전환")
        records = from_raw_tables(conn)
        source  = "raw tables (cp_30d × nyfed_effr × aa_manual)"

    conn.close()

    print(f"\n=== 데이터 소스: {source} ===")
    print(f"유효 날짜 수: {len(records)}")

    if len(records) < 5:
        print("\n데이터 부족 (< 5 거래일) — 분석 불가.")
        print("TMRS를 최소 5회 이상 계산하거나 aa_manual 데이터를 입력하세요.")
        return

    dates    = [r["date"] for r in records]
    cp_effr  = [r["cp_effr"] for r in records]
    cp_aa    = [r["cp_aa"] for r in records]

    print(f"기간: {dates[0]} ~ {dates[-1]}")

    # ── 기초 통계 ─────────────────────────────────────────────
    def stats(vals, name):
        return (f"{name}: mean={sum(vals)/len(vals):.4f}  "
                f"min={min(vals):.4f}  max={max(vals):.4f}  n={len(vals)}")

    print(f"\n=== 기초 통계 ===")
    print(stats(cp_effr, "cp_effr (pp)"))
    print(stats(cp_aa,   "cp_aa   (bp)"))

    # ── Level 상관계수 ────────────────────────────────────────
    corr_level = pearson(cp_effr, cp_aa)

    # ── Daily Δ 상관계수 ──────────────────────────────────────
    d_effr = diff_series(cp_effr)
    d_aa   = diff_series(cp_aa)
    corr_chg = pearson(d_effr, d_aa)

    print(f"\n=== Pearson 상관계수 ===")
    print(f"Level (수준)       r = {corr_level:+.4f}")
    print(f"Daily Δ (변화율)   r = {corr_chg:+.4f}")

    # ── Rolling (pandas 있을 때) ───────────────────────────────
    pd = _require_pandas()
    if pd and len(records) >= 20:
        import pandas as _pd
        df = _pd.DataFrame(records)
        roll_n = min(30, len(df) // 2)
        df["cp_effr_chg"] = df["cp_effr"].diff()
        df["cp_aa_chg"]   = df["cp_aa"].diff()
        df["roll_level"] = df["cp_effr"].rolling(roll_n).corr(df["cp_aa"])
        df["roll_chg"]   = df["cp_effr_chg"].rolling(roll_n).corr(df["cp_aa_chg"])
        recent = df[["date", "roll_level", "roll_chg"]].dropna().tail(10)
        print(f"\n=== Rolling {roll_n}일 상관계수 (최근 10개) ===")
        for _, rw in recent.iterrows():
            print(f"  {rw['date']}  level={rw['roll_level']:+.4f}  chg={rw['roll_chg']:+.4f}")

    # ── 결정 기준 평가 ────────────────────────────────────────
    def classify(r: float) -> str:
        if r > 0.80:  return "HIGH   (>0.80)"
        if r >= 0.50: return "MEDIUM (0.50–0.80)"
        return             "LOW    (<0.50)"

    print(f"\n=== 결정 기준 평가 ===")
    print(f"Level  : {classify(corr_level)}")
    print(f"Changes: {classify(corr_chg)}")

    both_high   = corr_level > 0.80 and corr_chg > 0.80
    both_medium = 0.50 <= corr_level <= 0.80 and 0.50 <= corr_chg <= 0.80
    both_low    = corr_level < 0.50 and corr_chg < 0.50

    print(f"\n=== 권장 결정 ===")
    if both_high:
        print("→ [cap=0 유지] 완전 redundancy: A2/P2-AA Spread 와 중복")
        print("  코드 변경 없음, ADR 만 작성.")
    elif both_medium:
        print("→ [cap=2 부여] 부분 redundancy")
        print("  _compute_tmrs() 에서 cp_effr cap=0 → cap=2 변경 필요.")
    elif both_low:
        print("→ [cap=3 부여] 독립 신호 — Layer 2 정식 편입")
        print("  _compute_tmrs() 에서 cp_effr cap=0 → cap=3 변경 필요.")
    else:
        print("→ [Mixed] TW 확인 후 결정 필요")
        print(f"  Level r = {corr_level:+.4f} | Daily Δ r = {corr_chg:+.4f}")


if __name__ == "__main__":
    main()
