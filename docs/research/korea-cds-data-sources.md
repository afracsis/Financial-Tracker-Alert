# Korea CDS 5Y Data Source Research

**Date**: 2026-04-20  
**Stage**: 2.3  
**Status**: Research only (no implementation)  
**Related PR**: PR #10

---

## Background

Stage 1에서 Korea CDS 5Y를 데이터 소스 부재로 제외.  
Bloomberg / Refinitiv 유료 전용 판단이었으나, 무료·저비용 대안 존재 여부를 조사.

---

## Sources Evaluated

### 1. KRX 공시 (Korea Exchange)

- **URL**: https://data.krx.co.kr
- **Data availability**: ❌ No — sovereign CDS 미제공
- **API**: ❌ — Data Marketplace에 CDS 없음
- **Update frequency**: N/A
- **Cost**: N/A
- **Implementation feasibility**: ❌
- **Notes**: KRX는 주식·채권·파생상품 거래소이나 OTC 신용파생상품(CDS) 데이터를 공시하지 않음. ICE와 협업하는 데이터 서비스도 equity/bond 중심, sovereign CDS 미포함.

---

### 2. 한국은행 ECOS

- **URL**: https://ecos.bok.or.kr
- **Data availability**: ❌ No — CDS 시계열 없음
- **API**: ✅ Yes — Open API (무료 API key 발급, https://ecos.bok.or.kr/api/)
- **Update frequency**: Daily (API 자체는 일별 갱신)
- **Cost**: 무료
- **Implementation feasibility**: ❌ (CDS 데이터 없음)
- **Notes**: ECOS API는 통화·금리·외환보유고·경제지표를 제공하나 sovereign CDS spread 시계열 없음. Python 래퍼(PublicDataReader)로 접근 용이하나 활용 불가.

---

### 3. Investing.com

- **URL**: https://www.investing.com/rates-bonds/south-korea-cds-5-year-usd-historical-data
- **Data availability**: ✅ Yes — 실시간 + 장기 historical 데이터 보유
- **API**: ❌ No — 공식 API 없음
- **Update frequency**: Daily
- **Cost**: 무료 (웹 인터페이스)
- **Implementation feasibility**: ⚠️ Medium
- **Notes**: 웹에서 Korea CDS 5Y 데이터 확인 가능. HTML 스크래핑 기술적으로 가능하나 안티봇 차단(Cloudflare), 사이트 구조 변경 위험, ToS 제한. `investpy` 라이브러리가 존재하나 공식 지원 아님. **운영 환경 사용 권장하지 않음**.

---

### 4. Yahoo Finance (yfinance)

- **URL**: yfinance Python 라이브러리
- **Data availability**: ❌ No — CDS 상품 미상장
- **API**: N/A
- **Update frequency**: N/A
- **Cost**: N/A
- **Implementation feasibility**: ❌
- **Notes**: CDS는 OTC 파생상품으로 Yahoo Finance에 상장되지 않음. 한국 관련 ticker(^KS11, ^KQ11)는 주가지수이며 CDS와 무관.

---

### 5. CME / ICE 공개 데이터

- **URL**: https://www.ice.com/cds-settlement-prices/icc/single-name-instruments
- **Data availability**: ⚠️ Partial — ICE Clear Credit의 일별 settlement price 공개
- **API**: ⚠️ Limited — 상세 데이터 접근에 pricing license 필요
- **Update frequency**: Daily (end-of-day settlement)
- **Cost**: 기본 공시 무료 / historical·상세 데이터 유료 라이선스
- **Implementation feasibility**: ⚠️ Low
- **Notes**: ICE Clear Credit이 sovereign CDS settlement price를 공시하며 Korea 포함 가능성. 그러나 체계적 historical 수집에는 S&P Global / Markit 라이선스 계약이 필요해 사실상 유료.

---

### 6. 금융감독원(FSS) / 신용평가사(NICE·KIS)

- **URL**: https://www.fss.or.kr / https://www.nicerating.com
- **Data availability**: ❌ No
- **API**: ❌
- **Update frequency**: N/A
- **Cost**: N/A
- **Implementation feasibility**: ❌
- **Notes**: FSS는 감독·규제 기관으로 sovereign CDS 통계 미제공. NICE·KIS는 국내 기업신용등급 기관으로 sovereign CDS spread 데이터와 무관.

---

### 7. World Government Bonds ⭐ 1순위 후보

- **URL**: http://www.worldgovernmentbonds.com/cds-historical-data/south-korea/5-years/
- **Data availability**: ✅ Yes — 장기 historical + 일별 갱신
- **API**: ❌ No — 공식 API 없음
- **Update frequency**: Daily
- **Cost**: 무료
- **Implementation feasibility**: ⚠️ Medium (HTML 스크래핑)
- **Notes**: ICE Data Derivatives를 원본 소스로 사용. 클린한 HTML 구조로 BeautifulSoup 스크래핑 기술적 가능. 공식 API 부재로 레이아웃 변경 시 스크래퍼 파손 위험. 대형 사이트(Investing.com)보다 안티봇 조치가 약해 스크래핑 안정성 상대적으로 양호.

---

### 8. AsianBondsOnline (ADB) ⭐ 2순위 후보

- **URL**: https://asianbondsonline.adb.org/data-portal/
- **Data availability**: ✅ Yes — ASEAN+3 sovereign CDS 5Y 포함
- **API**: ⚠️ Data Portal 있음 (구체적 API 스펙 미공개)
- **Update frequency**: Daily / Weekly
- **Cost**: 무료
- **Implementation feasibility**: ⚠️ Medium
- **Notes**: ADB가 운영하는 아시아 채권시장 포털. EEA CDS 5Y 데이터에 한국 포함. API 상세는 asianbonds_info@adb.org 문의 필요. 공공기관 운영으로 데이터 안정성 높음. **추가 조사 가치 있음.**

---

### 9. CBONDS

- **URL**: https://cbonds.com/indexes/13895/
- **Data availability**: ✅ Yes — ICE Data Derivatives 소스로 일별 갱신
- **API**: ⚠️ API 존재하나 **CDS historical 데이터는 API 미지원** (기술적 제한)
- **Update frequency**: Daily
- **Cost**: 일별 현재값 무료 / historical bulk 유료
- **Implementation feasibility**: ⚠️ Low
- **Notes**: CBONDS Index ID 13895가 Korea CDS 5Y를 추적. API로 현재값 조회 가능하나 historical 시계열은 API 미지원 — 일회성 bulk 다운로드(유료) 또는 일별 수동 수집만 가능.

---

### 10. Trading Economics API

- **URL**: https://tradingeconomics.com/south-korea/credit-default-swap
- **Data availability**: ⚠️ Likely Yes — 300,000+ 지표 제공
- **API**: ✅ Yes — 공식 REST API
- **Update frequency**: Real-time / Daily
- **Cost**: 구독 필요 (무료 Lite tier 있으나 CDS 포함 여부 미확인)
- **Implementation feasibility**: ✅ High (API 있는 경우)
- **Notes**: Korea CDS 5Y 데이터를 웹에서 표시하나 API 접근에는 플랜별 요금 발생. 무료 tier에서 CDS 포함 여부 미확인. 저비용 구독 시 가장 구현 용이한 옵션.

---

### 11. 기타 조사 소스

| 소스 | 결과 | 비고 |
|------|------|------|
| NYU Stern Damodaran | ✅ 있음 (월별 Excel 파일) | 실시간 아님, 주기적 업데이트 |
| FRED (St. Louis Fed) | ❌ 없음 | Korea CDS 시리즈 없음 (확인 완료) |
| BIS Data Portal | ⚠️ 연구 데이터 | 분기별, 일별 가격 아님 |
| DTCC Trade Warehouse | ⚠️ 집계 데이터 | 기관용, 일별 가격 아님 |
| ISDA SwapsInfo | ⚠️ 주별 notional | 가격 아님 |

---

## 종합 비교표

| 소스 | 데이터 | API | 일별 | 무료 | 구현 난이도 | 안정성 |
|------|:------:|:---:|:----:|:----:|:-----------:|:------:|
| KRX | ❌ | ❌ | — | — | — | — |
| BOK ECOS | ❌ | ✅ | ✅ | ✅ | — | — |
| Investing.com | ✅ | ❌ | ✅ | ✅ | 스크래핑 | ⚠️ 낮음 |
| Yahoo Finance | ❌ | ❌ | — | — | — | — |
| ICE Settlement | ⚠️ | ⚠️ | ✅ | ⚠️ | 라이선스 필요 | — |
| FSS / NICE / KIS | ❌ | ❌ | — | — | — | — |
| **World Govt Bonds** | **✅** | ❌ | **✅** | **✅** | **스크래핑** | **⚠️ 중간** |
| **AsianBondsOnline** | **✅** | **⚠️** | **✅** | **✅** | **문의 필요** | **✅ 높음** |
| CBONDS | ✅ | ⚠️ | ✅ | ⚠️ | 낮음 | ✅ 중간 |
| Trading Economics | ⚠️ | ✅ | ✅ | ⚠️ | 낮음 | ✅ 높음 |
| FRED | ❌ | ✅ | — | ✅ | — | — |
| NYU Damodaran | ✅ | ❌ | ❌ | ✅ | 수동 | ✅ 높음 |

---

## Recommendation

### 1순위: AsianBondsOnline (ADB Data Portal)

**사유:**
- ADB 공공기관 운영 → 데이터 안정성·지속성 높음
- ASEAN+3 sovereign CDS 5Y 공식 포함
- 무료
- Data Portal API 존재 가능성 (요청 후 확인 필요)

**다음 단계**: `asianbonds_info@adb.org`에 Korea CDS 5Y 데이터 접근 API 문의.

### 2순위: World Government Bonds 스크래핑

**사유:**
- 즉시 구현 가능 (API 문의 불필요)
- ICE Data Derivatives 소스 — 데이터 품질 양호
- 무료, 일별 갱신

**리스크**: 사이트 구조 변경 시 스크래퍼 파손. 운영 중 모니터링 필수.

### 3순위: Trading Economics API (소액 구독)

**사유:**
- 공식 REST API → 스크래핑 안정성 문제 없음
- Korea CDS 5Y 포함 여부 확인 필요 (무료 tier 문의)

---

## Decision

- [x] **별도 Stage로 분리** (Stage 2.3은 조사 완료, 구현은 Stage 2.x에서)

**근거:**
1. 즉시 구현 가능한 API 기반 무료 소스 없음 — 모든 후보가 스크래핑이거나 유료/문의 필요
2. AsianBondsOnline API 가용성 미확인 → 확인 후 구현 결정
3. 스크래핑 기반 구현은 운영 안정성 리스크로 신중한 접근 필요
4. Korea CDS는 v1.0 Layer 2 spec 8개 중 마지막 미구현 지표 — 우선순위 상대적으로 낮음

**후속 액션 (별도 Stage에서):**
1. AsianBondsOnline API 문의 및 응답 확인
2. World Government Bonds 스크래퍼 PoC 작성 및 안정성 검증 (30일 테스트)
3. Trading Economics 무료 tier에서 Korea CDS 가용성 확인
