# Critical Hotfix: Single-B OAS FRED Series ID 오류 정정

**Status**: Accepted  
**Date**: 2026-04-15  
**Stage**: 2 (Critical Hotfix)  
**Related PR**: PR #5 (fix/critical)

---

## Context

TW가 FRED 사이트에서 직접 확인한 결과, Single-B OAS에 잘못된 Series ID가 사용되고 있음을 발견.

### 발견된 오류

| 항목 | 기존 (오류) | 올바른 값 |
|------|------------|----------|
| Series ID | `BAMLH0A2HYBEY` | `BAMLH0A2HYB` |
| Series명 | ICE BofA Single-B US HY **Effective Yield** | ICE BofA Single-B US HY **OAS** |
| 현재 FRED 값 | ~7.08% | ~3.19% |
| DB 저장값 (×100 bp) | ~708bp | ~319bp |
| TMRS 티어 | Crisis (>600bp) | Normal (<350bp) |

### 영향 범위

- **False positive Crisis**: 시스템이 Single-B 시장을 항상 Crisis로 판단
- **l2_score 과대평가**: Single-B OAS cap=7pt가 항상 만점(7pt) → l2_score +5~6pt 과잉
- **total_score 왜곡**: 총점에서 ~5-6점 상향 편향
- **Inverse Turkey 오탐**: l2_sev 과대 → l12_avg가 0.40 임계를 쉽게 초과

### FRED 직접 확인값 (2026-04-15 기준)

| 지표 | FRED Series | FRED 값 | 시스템 값 | 정합성 |
|------|-------------|---------|-----------|--------|
| HY OAS | BAMLH0A0HYM2 | 2.95% | 2.94% | ✓ |
| IG OAS | BAMLC0A0CM | 0.82% | 82.0bp | ✓ |
| Single-B OAS | **BAMLH0A2HYB** | **3.19%** | **319bp** | ✓ (fix 후) |

---

## Root Cause

v1.0 통합문서에 Series ID가 `BAMLH0A2HYBEY`로 잘못 기재되어 있었음.

- `BAMLH0A2HYB`  = OAS (Option-Adjusted Spread, 스프레드만)
- `BAMLH0A2HYBEY` = Effective Yield (국채금리 + OAS 합계)

v1.0 임계값(350/450/600bp)은 OAS 기준이므로 Effective Yield 적용 시 항상 과대평가.

**교훈**: FRED Series ID는 반드시 FRED 웹사이트에서 직접 확인 필요. `EY` 접미사 = Effective Yield.

---

## Decision

### 코드 변경

```python
# 변경 전
rows = fetch_fred_observations("BAMLH0A2HYBEY", limit=limit)

# 변경 후
rows = fetch_fred_observations("BAMLH0A2HYB", limit=limit)
```

### 오류 데이터 정리

`init_db()`에 일회성 마이그레이션 추가:

```python
wrong_count = conn.execute(
    "SELECT COUNT(*) FROM single_b_oas WHERE oas_bp > 650"
).fetchone()[0]
if wrong_count > 0:
    conn.execute("DELETE FROM single_b_oas WHERE oas_bp > 650")
    log.warning(f"[Single-B OAS] BAMLH0A2HYBEY 오류 데이터 {wrong_count}건 삭제")
```

**삭제 조건 근거** (`oas_bp > 650`):
- HYBEY 데이터: bp 변환 시 700+bp (현재 ~708bp, 역사적 500-900bp 범위)
- 정상 HYB OAS: 현재 319bp. 극단적 위기(2020년 3월 피크) ~550bp, 2008년 위기 일부 구간 ~700bp
- `> 650` 기준: HYBEY 데이터는 항상 이 범위에 있으나 실제 OAS는 이 범위가 극히 드묾
- 마이그레이션은 멱등: 정상 데이터는 650bp 초과 없으므로 재실행 시 0건 삭제

### 단위 처리 현황 (변경 없음, 정상)

| 지표 | FRED 출력 | 변환 | DB 저장 | 임계값 단위 |
|------|----------|------|---------|------------|
| HY OAS | % (2.94) | 없음 | % | % |
| IG OAS | % (0.82) | ×100 | bp (82) | bp |
| Single-B OAS | % (3.19) | ×100 | bp (319) | bp |

HY OAS와 IG/Single-B OAS의 단위 처리 방식이 다르나, 각각 임계값과 정합성이 있어 정상.

---

## Consequences

**긍정적:**
- False positive Crisis 즉시 해소: 708bp → 319bp (Normal)
- l2_score 정상화: 7pt 과잉 → 0pt (Normal 시 점수 기여 없음)
- total_score 편향 제거: ~5-6pt 하향 조정 예상
- Inverse Turkey 오탐 방지

**부정적:**
- 없음

**현재 시장 영향 (2026-04-15):**
- Single-B OAS 319bp = Normal → l2 기여 0pt
- Tariff shock 상황에서도 Single-B OAS는 아직 정상 구간
- (기존에는 Crisis 7pt로 잘못 기여하고 있었음)

---

## Reference

- `Financial_Tracker_Scoring_Logic_in Total.md` 카테고리 3.5.1
- FRED Series: https://fred.stlouisfed.org/series/BAMLH0A2HYB
- 오류 Series: https://fred.stlouisfed.org/series/BAMLH0A2HYBEY
- 유사 오류 예방: ADR 작성 시 FRED Series ID 직접 확인 원칙 수립
