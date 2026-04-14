# Telegram Inverse Turkey 알람 연결

**Status**: Accepted  
**Date**: 2026-04-14  
**Stage**: 1  
**Related Commit**: e43e170

---

## Context

기존 구현 현황 보고(2026-04-14)에서 "Telegram 알람 TMRS 연동 — Inverse Turkey 트리거 시
자동 알람 미연결"이 진행 중(⚠️) 상태로 확인됨. Stage 1에서 함께 처리.

**기존 알람 시스템 한계:**
- `check_and_alert()`: 지표별 % 변동 기반 — Inverse Turkey 패턴 감지 불가
- Inverse Turkey는 단일 지표 변동이 아닌 레이어 간 구조적 패턴

---

## Decision

`telegram_alerts.py`에 `alert_inverse_turkey()` 전용 함수 추가.

**트리거 조건:**
- `inv_turkey == True` 이고
- False→True 전환 시 즉시 발송 (신규 패턴 진입)
- True 지속 시 24시간 쿨다운 (지속 알람)

**De-duplication 전략:**
- `_it_state["prev"]` dict로 이전 True/False 상태 추적
- False→True: 쿨다운 무관 즉시 발송
- True 지속: 24시간 내 재발송 금지 (기존 1시간 쿨다운과 별도 관리)
- True→False: 쿨다운 완전 리셋 (다음 진입 시 즉시 발송 보장)

**메시지 포함 정보:**
- 발생 시각 (KST), TMRS 총점
- Layer 1/2/3 절대값 + 정규화값 (%)
- L1+L2 평균, L3 정규화값 (트리거 조건 수치)
- 현재 Stress/Crisis 구간 지표 목록
- 신규 진입 vs 지속(24h 경과) 구분 표시

**앱 연동:**
- `_compute_tmrs()` 내 `inv_turkey` 판별 직후 `alert_inverse_turkey()` 호출
- try/except로 알람 실패 시 TMRS 계산 흐름 보호

---

## Consequences

**긍정적:**
- v1.0 핵심 경보 기능 구현 완료
- Inverse Turkey 신규 감지 시 즉시 알람, 지속 시 과도한 알람 방지
- TMRS 계산과 분리된 try/except 구조로 알람 실패가 점수 계산에 영향 없음

**부정적:**
- 현재 시장 조건에서 Layer 2 저커버리지로 Inverse Turkey 트리거 미충족
  → Stage 2(HYG 추가) 완료 후 실질 동작 확인 필요
- 메모리 내 `_it_state` 딕셔너리 — Gunicorn 재시작 시 상태 리셋 (첫 계산에서 재알람 가능)

**DB 영향:**
- 없음 (상태는 인메모리 관리)

---

## Alternatives Considered

- **DB 기반 상태 추적**: Gunicorn 재시작에도 상태 유지. 구현 복잡도 상승 → Stage 2 이후 검토
- **기존 check_and_alert() 확장**: 레이어 간 패턴 감지에 부적합 → 전용 함수로 분리

---

## Reference

- `Financial_Tracker_Scoring_Logic_in Total.md` 카테고리 4.11.1
- `Stage1_Emergency.md` Section 3.6
- `telegram_alerts.py`: `alert_inverse_turkey()` 함수
