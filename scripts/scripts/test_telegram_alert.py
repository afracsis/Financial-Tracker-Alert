#!/usr/bin/env python3
"""
Stage 2.7 — Telegram Inverse Turkey 알람 실제 발송 테스트

사용법 (Replit Shell):
    cd ~/workspace/dashboard
    python scripts/test_telegram_alert.py

검증 항목:
    1. Telegram bot token / chat_id 환경변수 설정 확인
    2. send_raw() 연결 테스트 — 실제 메시지 발송
    3. Inverse Turkey 알람 첫 번째 발송 (False→True 전환, 즉시 발송)
    4. 24h dedup 검증 — 즉시 재호출 시 차단 확인

기대 결과:
    Telegram 에서 메시지 2개 수신:
      #1 — [TEST] 연결 확인 메시지
      #2 — [TEST] Inverse Turkey Alert (1st call)
    3번째 메시지는 도착하지 않아야 함 (dedup 차단)
"""

import os
import sys

# dashboard 폴더를 모듈 경로에 추가 (Replit: ~/workspace/dashboard)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import telegram_alerts
from datetime import datetime
import pytz

KST = pytz.timezone("Asia/Seoul")

PASS = "✅"
FAIL = "❌"


def main() -> None:
    now_kst = datetime.now(tz=KST)
    test_id = now_kst.strftime("%Y%m%d-%H%M%S")
    now_str = now_kst.strftime("%Y-%m-%d %H:%M:%S KST")

    print("=" * 62)
    print("  Stage 2.7 — Telegram Inverse Turkey 알람 발송 테스트")
    print(f"  실행 시각 : {now_str}")
    print(f"  Test ID   : {test_id}")
    print("=" * 62)

    results: list[tuple[str, str]] = []

    # ── 1. 환경변수 확인 ─────────────────────────────────────────
    print("\n[1] 환경변수 확인")
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id   = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not bot_token:
        print(f"  {FAIL}  TELEGRAM_BOT_TOKEN 미설정")
        print("       Replit Secrets 에서 설정 후 재시도하세요.")
        sys.exit(1)
    if not chat_id:
        print(f"  {FAIL}  TELEGRAM_CHAT_ID 미설정")
        print("       Replit Secrets 에서 설정 후 재시도하세요.")
        sys.exit(1)

    print(f"  {PASS}  TELEGRAM_BOT_TOKEN : ***{bot_token[-4:]}")
    print(f"  {PASS}  TELEGRAM_CHAT_ID   : {chat_id}")

    # ── 2. 연결 테스트 (send_raw) ────────────────────────────────
    print("\n[2] Telegram 연결 테스트 — send_raw()")
    connect_msg = (
        f"🧪 <b>[TEST] Financial Tracker — Telegram 연결 확인</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"● Test ID  : {test_id}\n"
        f"● 시각     : {now_str}\n"
        f"● Sequence : 1 of 2\n"
        f"● 목적     : Stage 2.7 Telegram bot 연결 검증\n"
        f"\n"
        f"이 메시지가 도착하면 bot token / chat_id 정상 작동 확인됩니다.\n"
        f"실제 알람이 아닙니다."
    )
    r_connect = telegram_alerts.send_raw(connect_msg)
    status = PASS if r_connect else FAIL
    note   = "발송 성공" if r_connect else "발송 실패 — bot token 또는 네트워크 확인 필요"
    print(f"  {status}  {note}")
    results.append((status, "send_raw() 연결 테스트"))

    if not r_connect:
        print("\n  ⛔ 연결 실패로 테스트 중단합니다.")
        sys.exit(1)

    # ── 3. Inverse Turkey 1st call (False→True 즉시 발송) ────────
    print("\n[3] Inverse Turkey 알람 — 1st call (False→True 전환, 즉시 발송 예상)")

    # 테스트 전 상태 초기화 (clean slate)
    telegram_alerts._it_state["prev"] = False
    telegram_alerts._cooldown.pop("inverse_turkey", None)

    # 테스트용 mock 지표 (실제 위기 시나리오 수치)
    mock_inds = {
        "single_b_oas":    {"name": "Single-B OAS",    "tier": "crisis", "cap": 7,  "layer": 2},
        "hy_oas":          {"name": "HY OAS",           "tier": "stress", "cap": 5,  "layer": 2},
        "discount_window": {"name": "Discount Window",  "tier": "stress", "cap": 5,  "layer": 1},
        "rrp":             {"name": "RRP 잔고",          "tier": "crisis", "cap": 4,  "layer": 1},
        "vix":             {"name": "VIX",              "tier": "normal", "cap": 4,  "layer": 3},
        "move":            {"name": "MOVE Index",       "tier": "normal", "cap": 4,  "layer": 3},
    }
    # 테스트 수치: l12_avg=(22.5/45 + 13.5/30)/2 = (0.500+0.450)/2 = 0.475 ≥ 0.40
    #              l3_norm = 2.0/15 = 0.133 ≤ 0.25 → 트리거 조건 충족
    r1 = telegram_alerts.alert_inverse_turkey(
        inv_turkey=True,
        l1=22.5, l2=13.5, l3=2.0, total=38.0,
        inds=mock_inds,
        is_test=True,
    )
    status1 = PASS if r1 else FAIL
    note1   = "발송됨 (예상대로)" if r1 else "미발송 (예상 외 — dedup 또는 발송 오류)"
    print(f"  {status1}  1st call 결과: {note1}")
    results.append((status1, "Inverse Turkey 1st call (False→True)"))

    # ── 4. 24h dedup 테스트 (2nd call: True 지속 → 차단) ─────────
    print("\n[4] 24h dedup 테스트 — 2nd call (True 지속, 즉시 재호출 → 차단 예상)")
    r2 = telegram_alerts.alert_inverse_turkey(
        inv_turkey=True,
        l1=22.5, l2=13.5, l3=2.0, total=38.0,
        inds=mock_inds,
        is_test=True,
    )
    dedup_ok = not r2   # 차단됐어야 함
    status2  = PASS if dedup_ok else FAIL
    note2    = "차단됨 (dedup 정상)" if dedup_ok else "재발송됨 — dedup 미작동! 코드 확인 필요"
    print(f"  {status2}  2nd call 결과: {note2}")
    results.append((status2, "24h dedup (True 지속 시 차단)"))

    # ── 최종 결과 ─────────────────────────────────────────────────
    print("\n" + "=" * 62)
    passed = sum(1 for m, _ in results if m == PASS)
    failed = len(results) - passed
    print(f"  결과: {passed}개 통과 / {failed}개 실패  (총 {len(results)}개 항목)")

    if failed == 0:
        print("  🎉 Telegram 알람 전체 검증 통과")
    else:
        print("  ⛔ 실패 항목:")
        for m, label in results:
            if m == FAIL:
                print(f"     - {label}")

    print("=" * 62)
    print(f"\n  TW님 확인 사항 (Telegram 앱에서):")
    print(f"  ┌─ Test ID: [{test_id}]")
    print(f"  ├─ 메시지 #1: [TEST] Financial Tracker 연결 확인  → 도착해야 함")
    print(f"  ├─ 메시지 #2: [TEST] Inverse Turkey Alert (1st call)  → 도착해야 함")
    print(f"  └─ 메시지 #3: 없어야 함 (dedup 차단 확인)")
    print()


if __name__ == "__main__":
    main()
