#!/usr/bin/env python3
"""
sync_from_github.py — GitHub → Replit 파일 동기화 스크립트

사용법 (Replit Shell에서):
    cd ~/workspace/dashboard
    python sync_from_github.py

환경변수 (Replit Secrets에 추가):
    GITHUB_TOKEN : GitHub Personal Access Token
                   (Settings → Developer settings → Personal access tokens → Fine-grained)
                   repo 읽기 권한만 있으면 됩니다.
"""

import os
import urllib.request
import urllib.error

# ── 설정 ─────────────────────────────────────────────────────────────
REPO   = "afracsis/Financial-Tracker-Alert"
BRANCH = "main"  # Stage 1 검증 브랜치 (검증 완료 후 main 전환)

# 이 스크립트가 있는 폴더(dashboard/)를 기준으로 저장
DEST = os.path.dirname(os.path.abspath(__file__))

# 동기화할 파일 목록
FILES = [
    "app.py",
    "auth.py",
    "telegram_alerts.py",
    "portfolio_scraper.py",
    "jpy_scraper.py",
    "gunicorn.conf.py",
    "templates/index.html",
    "templates/login.html",
]
# ─────────────────────────────────────────────────────────────────────


def _download(filename: str, token: str) -> bytes:
    url = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{filename}"
    headers = {"User-Agent": "replit-sync-script/1.0"}
    if token:
        headers["Authorization"] = f"token {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} — {filename}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"네트워크 오류 — {e.reason}")


def sync():
    token = os.environ.get("GITHUB_TOKEN", "")

    print("=" * 55)
    print("  GitHub → Replit 동기화 시작")
    print(f"  저장소 : {REPO} @ {BRANCH}")
    print(f"  저장위치: {DEST}")
    if token:
        print("  인증    : GITHUB_TOKEN 사용 중 ✓")
    else:
        print("  인증    : 없음 (public repo 전용)")
    print("=" * 55)

    success, fail = 0, 0

    for filename in FILES:
        dest_path = os.path.join(DEST, filename)

        # 하위 폴더(templates/ 등) 자동 생성
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        try:
            content = _download(filename, token)
            with open(dest_path, "wb") as f:
                f.write(content)
            size_kb = len(content) / 1024
            print(f"  ✓  {filename:<40} {size_kb:>6.1f} KB")
            success += 1
        except Exception as e:
            print(f"  ✗  {filename:<40} 실패: {e}")
            fail += 1

    print("=" * 55)
    print(f"  완료: {success}개 성공 / {fail}개 실패")

    if fail > 0:
        print()
        print("  [힌트] 실패한 경우 아래를 확인하세요:")
        print("  1) Replit Secrets에 GITHUB_TOKEN이 있는지 확인")
        print("  2) Token에 Contents: Read 권한이 있는지 확인")
        print("  3) 저장소 이름이 올바른지 확인:", REPO)

    print("=" * 55)

    if success > 0 and fail == 0:
        print()
        print("  동기화 완료! 앱을 재시작하면 변경사항이 반영됩니다.")
        print("  (Replit에서 Stop → Run 클릭)")


if __name__ == "__main__":
    sync()
