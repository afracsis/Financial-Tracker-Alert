# Inverse Turkey 트리거 조건 문서-코드 불일치 정정

**Status**: Accepted  
**Date**: 2026-04-14  
**Stage**: 1 (hotfix)  
**Related Commit**: (본 커밋)

---

## Context

Stage 1 검증 과정(2026-04-14)에서 Inverse Turkey 트리거 조건의
코드-문서 불일치 발견.

| 출처 | 조건 |
|------|------|
| v1.0 카테고리 4.11.1 | `l12_avg >= 0.40 AND l3_norm <= 0.25` |
| Stage 1 코드 (e43e170) | `l1_sev >= 0.5 AND l2_sev >= 0.4 AND l3_sev <= 0.2` |

**차이점:**
1. **집계 방식**: 문서는 l1/l2 평균(l12_avg), 코드는 개별 임계값 동시 충족
   - 문서 조건: l1이 낮아도 l2가 높으면 평균으로 보완 가능
   - 코드 조건: l1, l2 모두 독립적으로 임계값 충족 필요 (더 엄격)
2. **l3 임계값**: 문서 0.25 vs 코드 0.20

**현재 시장 조건에서의 영향:**
- l2_sev = 7/30 = 0.233 → 코드 조건(0.4) 미충족 → inv_turkey = False
- l2_sev = 7/30 = 0.233, l1 값에 따라 l12_avg 계산 → 문서 조건 충족 여부 달라짐

---

## Decision

v1.0 문서 기준으로 코드 수정:

```python
# 수정 전
inv_turkey = bool(l1_sev >= 0.5 and l2_sev >= 0.4 and l3_sev <= 0.2)

# 수정 후
l12_avg = (l1_sev + l2_sev) / 2
inv_turkey = bool(l12_avg >= 0.40 and l3_sev <= 0.25)
```

`l12_avg` 변수는 Divergence 계산에도 이미 암묵적으로 사용 중이므로
명시적 변수로 추출하여 가독성 향상.

---

## Consequences

**긍정적:**
- v1.0 설계 의도 복원: l1 또는 l2 중 하나가 높으면 Inverse Turkey 감지 가능
- l3 임계값 0.25 → 0.25 (0.20에서 완화) — 주식 시장이 약간 상승해도 패턴 감지

**부정적:**
- 없음

**현재 시장 조건 영향:**
- 분모 30 기준 l2_sev = 7/30 = 0.233 → l12_avg는 l1 값에 의존
- Stage 2 지표 추가 전까지는 l2 단독으로 l12_avg >= 0.40 달성 어려움
  (l2_sev가 0.80 이상이어야 l1=0으로도 평균 0.40 도달)
- 구조적 한계는 Stage 2 (HYG 추가) 완료 후 해소 예정

**l2_sev 분모 관련 별도 이슈:**
- 현재 분모: 30 (v1.0 spec max)
- Stage 1 활성 max: 17pt
- 분모 30 유지 → 현재 Single-B crisis(7pt)만으로 l2_sev = 0.233 (구조적 저평가)
- 분모 변경은 별도 ADR 및 TW 승인 필요 (Stage 2 착수 전 결정 예정)

---

## Alternatives Considered

- **코드 조건 유지**: 개별 임계값 충족이 더 보수적이나 v1.0 설계 의도와 다름 → 기각
- **Stage 2로 이월**: TW 지시에 따라 Stage 1 hotfix로 즉시 처리 → 채택

---

## Reference

- `Financial_Tracker_Scoring_Logic_in Total.md` 카테고리 4.11.1
- `Stage1_Emergency.md` Section 3.6
- 원래 코드 커밋: e43e170
