#!/usr/bin/env python3
"""
JPY Swap Daily Snapshot 분포 분석 스크립트

용도:
  Stage 2.4 에서 percentile 기반 임계값 확정 시 실행.
  30일 이상 jpy_swap_daily 데이터 누적 후 사용.

실행:
  python scripts/analyze_jpy_distribution.py [lookback_days]

예시:
  python scripts/analyze_jpy_distribution.py        # 기본 30일
  python scripts/analyze_jpy_distribution.py 60     # 60일 조회

핵심 개념 (GPT Yen Carry Unwind Framework):
  - 분석 기준: bid 의 절대값 변화 (change in abs(bid))
  - abs(bid) 감소 → 0 에 가까워짐 → carry 약화 (stress 신호)
  - abs(bid) 증가 → carry 강화 (normal)
  - v1.0 카테고리 3.4.4 의 방향성 재해석 (Stage 3 에서 공식 정정 예정)

출력:
  - 각 만기별 5일 변화 분포 (min/25p/50p/75p/90p/95p/max)
  - Stage 2.4 임계 후보값 (percentile 기반)
  - 데이터 부족 시 명시적 경고

참조:
  - Stage2_0_Instructions.md Section 1.2.8
  - docs/decisions/2026-04-17-stage2-0-jpy-infrastructure.md
"""

import sqlite3
import sys
import os
from pathlib import Path

# scripts/ 디렉토리 → 루트 디렉토리 참조
ROOT_DIR = Path(__file__).parent.parent
DB_PATH  = ROOT_DIR / "data.db"

PERIODS = ["1M", "3M", "3Y", "7Y", "10Y"]

# v1.0 카테고리 4.5 Layer 1 가중치 (Stage 2.4 에서 활성화 예정)
V1_WEIGHTS = {
    "1M":  5,   # USD/JPY 1M Basis
    "3M":  4,   # USD/JPY 3M Basis
    "3Y":  None,  # v1.0 명시 없음 (추가 검토)
    "7Y":  None,
    "10Y": None,
}


def percentile(sorted_list: list, p: float) -> float:
    """0~100 범위 p 의 percentile 값 반환."""
    if not sorted_list:
        return float("nan")
    idx = int(len(sorted_list) * p / 100)
    idx = min(idx, len(sorted_list) - 1)
    return sorted_list[idx]


def analyze_jpy_distribution(lookback_days: int = 30) -> None:
    if not DB_PATH.exists():
        print(f"ERROR: DB 파일 없음 → {DB_PATH}")
        print("Replit 에서 실행 시 dashboard/ 디렉토리 확인 필요.")
        return

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # 전체 누적 건수 먼저 확인
    total = conn.execute("SELECT COUNT(*) FROM jpy_swap_daily").fetchone()[0]

    print("=" * 60)
    print("  JPY Swap Daily Distribution Analysis")
    print(f"  Lookback: {lookback_days}일  |  DB 전체 누적: {total}건")
    print(f"  DB: {DB_PATH}")
    print("=" * 60)

    if total == 0:
        print()
        print("  [주의] jpy_swap_daily 테이블이 비어있습니다.")
        print("  Stage 2.0 JPY 인프라 deploy 후 매일 08:00 KST 에 자동 저장됩니다.")
        print("  30일 누적 후 이 스크립트를 재실행하세요.")
        conn.close()
        return

    any_analysis = False

    for period in PERIODS:
        rows = conn.execute(
            """
            SELECT date, bid, implied_yield_pct
            FROM jpy_swap_daily
            WHERE period = ?
              AND date >= date('now', ?)
            ORDER BY date ASC
            """,
            (period, f"-{lookback_days} days"),
        ).fetchall()

        n = len(rows)
        weight = V1_WEIGHTS.get(period)
        weight_str = f"{weight}pt" if weight else "v1.0 미명시"

        print()
        print(f"─── {period} (v1.0 Layer 1 가중: {weight_str}) ───")

        if n < 20:
            print(f"  데이터 부족: {n}일 (분포 분석 최소 20일 필요)")
            all_rows = conn.execute(
                "SELECT COUNT(*) FROM jpy_swap_daily WHERE period = ?", (period,)
            ).fetchone()[0]
            print(f"  전체 누적: {all_rows}일 | 목표까지 {max(0, 20 - all_rows)}일 남음")
            continue

        any_analysis = True

        # 최신/최고/최저 요약
        bids = [r["bid"] for r in rows]
        yields = [r["implied_yield_pct"] for r in rows if r["implied_yield_pct"] is not None]

        print(f"  기간: {rows[0]['date']} ~ {rows[-1]['date']}  ({n}일)")
        print(f"  Bid 범위: {min(bids):.1f} ~ {max(bids):.1f} bp")
        if yields:
            print(f"  Implied Yield: {yields[-1]:.3f}%  "
                  f"(범위 {min(yields):.3f}% ~ {max(yields):.3f}%)")

        # 5일 전 대비 bid 절대값 변화 계산
        abs_changes_5d: list[float] = []
        yield_changes_5d: list[float] = []

        for i in range(5, n):
            abs_now   = abs(rows[i]["bid"])
            abs_5ago  = abs(rows[i - 5]["bid"])
            abs_changes_5d.append(abs_now - abs_5ago)   # 양수: 절대값 증가(carry 강화), 음수: 감소(stress)

            yld_now  = rows[i]["implied_yield_pct"]
            yld_5ago = rows[i - 5]["implied_yield_pct"]
            if yld_now is not None and yld_5ago is not None:
                yield_changes_5d.append(yld_now - yld_5ago)

        if not abs_changes_5d:
            print("  (5일 변화 계산 불가 — 데이터 5건 미만)")
            continue

        sc = sorted(abs_changes_5d)
        m  = len(sc)

        print()
        print("  [Bid 절대값 5일 변화 분포]")
        print(f"    Min : {sc[0]:+8.3f}  (음수=절대값 감소=carry 약화=stress)")
        print(f"    25p : {percentile(sc, 25):+8.3f}")
        print(f"    50p : {percentile(sc, 50):+8.3f}  (중앙값)")
        print(f"    75p : {percentile(sc, 75):+8.3f}")
        print(f"    90p : {percentile(sc, 90):+8.3f}")
        print(f"    95p : {percentile(sc, 95):+8.3f}")
        print(f"    Max : {sc[-1]:+8.3f}  (양수=절대값 증가=carry 강화=normal)")

        # Stage 2.4 후보 임계
        p75 = percentile(sc, 75)
        p90 = percentile(sc, 90)
        p95 = percentile(sc, 95)

        print()
        print("  [Stage 2.4 임계 후보 (percentile 기반, 확정 전 참고용)]")
        print(f"    Normal : < p75  ({p75:+.3f})")
        print(f"    Watch  : p75~p90  ({p75:+.3f} ~ {p90:+.3f})")
        print(f"    Stress : p90~p95  ({p90:+.3f} ~ {p95:+.3f})")
        print(f"    Crisis : > p95  ({p95:+.3f})")

        if yield_changes_5d:
            ysc = sorted(yield_changes_5d)
            print()
            print("  [Implied Yield 5일 변화 분포 (참고)]")
            print(f"    Min/50p/Max: "
                  f"{ysc[0]:+.4f}% / {percentile(ysc, 50):+.4f}% / {ysc[-1]:+.4f}%")

    conn.close()

    print()
    print("=" * 60)
    if any_analysis:
        print("  분석 완료.")
        print()
        print("  [해석 기준]")
        print("    양수 변화 = abs(bid) 증가 = carry 강화 = 정상")
        print("    음수 변화 = abs(bid) 감소 = carry 약화 = stress 신호")
        print()
        print("  [주의]")
        print("    - 본 임계는 후보값입니다. TW 검토 후 Stage 2.4 에서 확정.")
        print("    - v1.0 카테고리 3.4.4 방향성 재해석 → Stage 3 공식 정정 예정.")
    else:
        print("  분석 가능한 만기 없음 (모두 20일 미만).")
        print("  30일 이상 누적 후 재실행하세요.")
    print("=" * 60)


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    analyze_jpy_distribution(days)
