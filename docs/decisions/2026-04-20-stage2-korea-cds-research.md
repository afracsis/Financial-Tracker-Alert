# Stage 2.3: Korea CDS 5Y — 데이터 소스 조사 결과 및 구현 보류 결정

**Status**: Accepted  
**Date**: 2026-04-20  
**Stage**: 2.3  
**Related PR**: PR #10

---

## Context

Stage 1에서 Korea CDS 5Y 지표를 데이터 소스 부재로 제외했다.  
Stage 2.3에서 무료·저비용 대안 소스를 체계적으로 조사해 구현 가능성을 평가했다.

조사 대상: KRX, BOK ECOS, Investing.com, Yahoo Finance, CME/ICE, FSS/NICE/KIS,  
World Government Bonds, AsianBondsOnline, CBONDS, Trading Economics, FRED, BIS, DTCC, ISDA, NYU Stern

상세 결과: `docs/research/korea-cds-data-sources.md`

---

## 조사 결과 요약

### 즉시 사용 불가 소스 (6개)

| 소스 | 사유 |
|------|------|
| KRX | CDS 데이터 미제공 |
| BOK ECOS | CDS 시계열 없음 (API는 우수) |
| Yahoo Finance | OTC CDS 상장 없음 |
| FSS / NICE / KIS | 규제기관·기업신용등급사, sovereign CDS 무관 |
| FRED | Korea CDS 시리즈 없음 (확인 완료) |
| CME | Futures 중심, sovereign CDS 아님 |

### 기술적으로 가능하나 리스크 있는 소스 (3개)

| 소스 | 방법 | 리스크 |
|------|------|--------|
| Investing.com | HTML 스크래핑 | Cloudflare 차단, ToS 위반 가능성, 잦은 구조 변경 |
| World Government Bonds | HTML 스크래핑 | 레이아웃 변경 시 파손, 공식 지원 없음 |
| CBONDS | 일별 수동 또는 유료 bulk | Historical API 미지원 |

### 유망 후보 (추가 조사 필요, 2개)

| 소스 | 상태 | 다음 단계 |
|------|------|-----------|
| **AsianBondsOnline (ADB)** | Data Portal 존재, API 스펙 미공개 | asianbonds_info@adb.org 문의 |
| **Trading Economics** | Korea CDS 5Y 웹 표시 확인, API 유료 | 무료 tier 또는 저비용 플랜 확인 |

---

## Decision

### 구현 보류 — 별도 Stage에서 진행

**코드 변경 없음.** `docs/` 추가만.

**근거:**
1. **즉시 구현 가능한 안정적 무료 API 없음**: 공식 API가 있는 소스(BOK ECOS, FRED)는 CDS 데이터가 없고, CDS 데이터가 있는 소스(Investing.com, World Govt Bonds)는 공식 API가 없어 스크래핑에 의존해야 함.
2. **스크래핑 안정성 리스크**: 운영 환경에서 스크래핑 기반 지표는 사이트 변경 시 TMRS 계산 누락 위험. 다른 지표(FRED API, NY Fed API 등)의 안정성과 불균형.
3. **AsianBondsOnline 가능성**: ADB 공공기관 포털에 API가 있을 경우 최적 소스. 문의 결과 확인 전 구현 착수 불합리.
4. **우선순위**: Korea CDS는 v1.0 Layer 2 spec 8개 중 마지막 미구현 지표 1개. 현재 Layer 2 Coverage 75% (7/8 구현)로 다른 Layer 개선 우선순위가 높음.

---

## 후속 액션 (별도 Stage)

| 액션 | 담당 | 기한 |
|------|------|------|
| AsianBondsOnline API 문의 (asianbonds_info@adb.org) | TW | 2주 이내 |
| API 응답에 따른 구현 결정 | TW + Claude | 문의 결과 수신 후 |
| World Govt Bonds 스크래퍼 PoC (API 없을 경우 대안) | Claude | AsianBondsOnline API 불가 확인 시 |
| Trading Economics 무료 tier Korea CDS 가용성 확인 | TW | 선택적 |

---

## Consequences

**긍정적:**
- 무분별한 스크래핑 구현을 방지 → TMRS 안정성 유지
- 조사 인프라(`docs/research/korea-cds-data-sources.md`) 완비 → 이후 구현 시 참조
- AsianBondsOnline API 가용 시 빠른 구현 착수 가능

**부정적 / 주의:**
- Korea CDS 미구현으로 Layer 2 Coverage 75% (7/8) 현 상태 유지
- LAYER_SPEC `"divergence"` Coverage 20% (1/5)와 함께 전체 Coverage 상승 제한 요인

---

## Reference

- `docs/research/korea-cds-data-sources.md` — 소스별 상세 조사 결과
- `Stage2_Instructions.md` Section 1.6
- `app.py`: `LAYER_SPEC` Layer 2 spec_indicators=8 (Korea CDS 포함 목표)
- `docs/decisions/2026-04-17-stage2-coverage-ratio.md` — Coverage Ratio 컨텍스트
