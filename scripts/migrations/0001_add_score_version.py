"""
Migration 0001: Add score_version column to tmrs_scores
Date: 2026-04-14
Stage: 1 (Emergency Layer 2 充실화)
Related: v1.0.1 Stage 1

목적:
  - v1.0.1 이후 점수 레코드에 버전 태그를 붙여 이력 연속성 유지
  - 기존 레코드 → 'v1.0' 태깅 (원본 보존)
  - Stage 1 완료 이후 신규 레코드 → 'v1.0.1' 태깅
"""
import os
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data.db")


def migrate(db_path: str = DB_PATH):
    if not os.path.exists(db_path):
        print(f"[Migration 0001] DB 파일 없음: {db_path}")
        print("  → Replit 환경에서 실행하세요: python scripts/migrations/0001_add_score_version.py")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # ── 1. score_version 컬럼 존재 여부 확인 ──────────────────────
    cursor.execute("PRAGMA table_info(tmrs_scores)")
    columns = [row[1] for row in cursor.fetchall()]

    if "score_version" not in columns:
        cursor.execute("""
            ALTER TABLE tmrs_scores
            ADD COLUMN score_version TEXT DEFAULT 'v1.0'
        """)
        print("[Migration 0001] ✓ score_version 컬럼 추가 완료")
    else:
        print("[Migration 0001] score_version 컬럼 이미 존재 — 스킵")

    # ── 2. 기존 레코드 NULL → 'v1.0' 채우기 ──────────────────────
    cursor.execute("""
        UPDATE tmrs_scores SET score_version = 'v1.0'
        WHERE score_version IS NULL
    """)
    updated = cursor.rowcount
    print(f"[Migration 0001] ✓ 기존 레코드 'v1.0' 태깅: {updated}건")

    conn.commit()

    # ── 3. 검증 출력 ──────────────────────────────────────────────
    cursor.execute("""
        SELECT score_version, COUNT(*) AS cnt
        FROM tmrs_scores
        GROUP BY score_version
        ORDER BY score_version
    """)
    print("\n[Migration 0001] 버전별 레코드 수:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}건")

    cursor.execute("""
        SELECT calculated_at, total_score, score_version
        FROM tmrs_scores
        ORDER BY calculated_at DESC
        LIMIT 3
    """)
    print("\n[Migration 0001] 최근 3개 레코드:")
    for row in cursor.fetchall():
        print(f"  {row[0]} | score={row[1]:.1f} | version={row[2]}")

    conn.close()
    print("\n[Migration 0001] ✓ 완료")
    return True


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    migrate(path)
