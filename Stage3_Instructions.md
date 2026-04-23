# Financial Tracker — v1.0.1 Stage 3 Instructions

> **Claude Code 작업 지시서 — Stage 3 착수**
> 본 문서는 Stage 3 (Replit Hotfix 반영 + LDS 구현 + 명칭/임계 정리) 통합 지시서입니다.

| 항목 | 내용 |
|---|---|
| **Baseline** | Stage 2.0~2.3 완료, PR #1~#10 merge |
| **Threshold Table 버전** | `v1.2026-04-01` (유지) |
| **Score Version** | `v1.0.1` (유지) |
| **작업 기준일** | 2026-04-22 |
| **Repo 구조** | `dashboard/` 하위 실행, GitHub root 동기화 (sync_from_github.py) |

---

## 0. 개요

### 0.1 Stage 3 의 목적

Stage 3 는 세 가지 작업을 진행합니다:

1. **Replit 로컬 hotfix 2건 GitHub 반영** — app.py 와 index.html 의 버그 수정이 Replit 에만 있고 GitHub main 에 미반영. 다음 PR 에서 충돌 방지를 위해 먼저 반영.
2. **LDS (Lindy Distance Score) 구현** — 탈렙 논문 기반. 4개 Credit 지표의 Crisis 장벽 접근도를 측정. Signal Desk UI 에 통합. Lindy Collapse Alert 발동.
3. **명칭/임계 정리** — FRA-OIS → SOFR Term Premium 명칭 변경, HY OAS 임계 v1.0 원문 정합성, v1.0 카테고리 3.4.4 재해석 정정.

### 0.2 Stage 3 의 비범위

- JPY 점수 활성화 → Stage 2.4 (30일 대기 중, 약 2026-05-16)
- ERS v0 → Stage 4
- TQQQ Decay Tracker → 진행하지 않음
- GPT v1.1 피드백 통합 → Stage 5+

### 0.3 전체 로드맵

```
[완료] Stage 1     — Layer 2 긴급 충실화
[완료] Stage 2.0   — UI 재설계 + JPY 인프라
[완료] Stage 2.1   — Coverage Ratio
[완료] Stage 2.2   — CP-EFFR 결정 (cap=0 유지)
[완료] Stage 2.3   — Korea CDS 조사 (구현 보류)

[현재] Stage 3     — Hotfix + LDS + 명칭/임계 정리 ← 본 지시서
[대기] Stage 2.4   — JPY 점수 활성화 (약 2026-05-16)
[이후] Stage 4     — ERS v0
```

---

## 0.5 Claude Code 가 모르는 변경 사항 (중요)

### A. 완료된 PR 이력 (PR #1 ~ PR #10)

Claude Code 가 인지해야 할 핵심 PR 들:

**A.1 PR #5 — Single-B OAS Series ID 정정 (가장 중요)**
- 잘못된 ID: `BAMLH0A2HYBEY` (Effective Yield) → 올바른 ID: `BAMLH0A2HYB` (OAS)
- 708bp Crisis (false positive) → 319bp Normal (실제 상태)
- `init_db()` 에 `oas_bp > 650` 자동 삭제 로직 포함
- **교훈**: FRED Series ID 는 반드시 웹에서 직접 확인. AI 산출값 cross-check 필수.

**A.2 PR #6 — UI 재설계**
- Signal Desk: Active Issues + 참고 지표 (cap=0) + Normal by Layer
- 각 지표 상세 카드 (클릭 시 펼침: 임계 시각화, 해석, 시계열 차트)
- Tier 우선순위 정렬 (Crisis → Stress → Watch → Normal)

**A.3 PR #7 — JPY 데이터 인프라**
- `jpy_swap_daily` 테이블 신설
- `save_jpy_daily_snapshot()` + KST 08:00 스케줄러
- `scripts/analyze_jpy_distribution.py` 준비 (30일 후 사용)
- **기존 코드 미변경**: `jpy_swap_data`, `_jpy_annualized()`, `refresh_jpy()` 그대로

**A.4 PR #8 — Coverage Ratio**
- LAYER_SPEC 상수 + Normalized Score (raw/max_achievable×100)
- Coverage 배지 + Layer별 coverage 표시
- **주의**: LAYER_SPEC 의 키를 `{str(k): v}` 로 문자열화해야 Flask jsonify 에러 방지

**A.5 PR #9 — CP-EFFR 결정**
- cap=0 유지 (데이터 부족으로 확정 판단 보류)
- 3개월 후 재평가 (n≥60 확보 시)

**A.6 PR #10 — Korea CDS 조사**
- 안정적 무료 API 부재 → 구현 보류
- AsianBondsOnline (ADB) 1순위 후보 → API 문의 후 결정

### B. Replit 로컬 hotfix 2건 (GitHub 미반영 — 이번 Stage 에서 반영)

**B.1 `app.py` — `_PUBLIC_PREFIXES` 확장**

현재 Replit 로컬 상태:
```python
_PUBLIC_PREFIXES = (
    "/auth/", "/health", "/static/",
    "/data", "/signal-desk", "/nyfed", "/fedop",
    "/volatility", "/jpy", "/portfolio",
    "/indicator/", "/history", "/records", "/credit"
)
```

GitHub main 상태 (구버전):
```python
_PUBLIC_PREFIXES = ("/auth/", "/health", "/static/")
```

**이유**: Flask 의 `@app.before_request` 인증 훅이 API endpoint 도 차단. JS `fetch()` 가 302 리다이렉트 → HTML 반환 → JSON 파싱 실패. 확장하여 API 경로를 인증에서 제외.

**B.2 `templates/index.html` — `data` → `d` 변수명 수정**

Fed Operation 탭의 `loadFedOp()` 함수에서:
```javascript
// 수정 전 (GitHub main)
const dw = data.discount_window;   // ← data 미정의, ReferenceError
const tga = data.tga;              // ← 동일 에러

// 수정 후 (Replit 로컬)
const dw = d.discount_window;      // ← fetch 결과가 d 에 할당됨
const tga = d.tga;
```

**원인**: `fetch('/fedop')` 결과를 `const d = await res.json()` 으로 할당했는데, 하단 DW/TGA 코드가 `data.` 로 참조. SOMA 등 상위 코드는 `d.` 로 정상 참조.

### C. v1.0 카테고리 3.4.4 재해석 필요

GPT 의 Yen Carry Unwind 프레임워크 통찰:
> "Carry trade 판단은 change 부호가 아니라 **절대값 변화 기준**. 음수값이 0 에 가까워짐 = 금리차 축소 = carry 약화 (stress)."

v1.0 원문의 USD/JPY Basis 임계가 이 사상과 반대 방향일 가능성. Stage 3 에서 정정 문서 작성.

### D. LDS (Lindy Distance Score) 도입 결정

탈렙 논문 *"린디 효과의 수학적 재정의"* (2026년 3월) 기반.

핵심 개념: **흡수 장벽 (absorbing barrier) 으로부터의 거리** 가 린디 속성 결정.
- 장벽에서 멀수록 → 파워로 생존 (린디 구간)
- 장벽에 가까울수록 → 사망력 급등

TMRS 적용: 4개 Credit 지표의 **Crisis 임계값 = 흡수 장벽**. 현재값과 장벽 사이 거리를 0~1 로 정규화.

**TW 결정 사항**:
- 대상 지표: Single-B OAS, CP Spread, HY OAS, HYG Daily (4개)
- 흡수 장벽 = TMRS Crisis 임계값
- Composite 가중치 = TMRS cap 비례 (7:6:5:4)
- UI: TMRS Score 옆 카드를 상단 LDS + 하단 Inverse Turkey 로 분할
- Alert: Composite LDS < 0.15 시 Telegram Lindy Collapse Alert 발송

### E. 시장 상태 (2026-04-21 기준)

```
TMRS: 33.6 (Normalized) / 원점수 23.5 / 70pt / 주의

Layer 1: 20.6/45 (Funding Stress 진행 중)
  🔴 RRP $0.16B (위기), SOFR-EFFR 8bp (위기)
  🔴 CP Spread 35bp, DW $5,306M (스트레스)

Layer 2: 0.0/30 (Credit 전부 Normal)
  Single-B 307bp, HY OAS 2.85%, HYG +0.09%

Layer 3: 1.6/15 (거의 평온)
  SKEW 140.7 (주의), VIX 17.9 (정상)

해석: "Funding breaks first" 단계. Credit 전이 아직 없음.
LDS 가 하락하기 시작하면 = Credit 전이 시작의 정량적 신호.
```

### F. 작업 원칙

Stage 1/2 와 동일:
1. 각 PR 마다 새 feature branch, base = main
2. ADR 작성
3. TW 검토 없이 다음 작업 금지
4. `threshold_table_version`, `score_version` 변경 금지
5. 기존 `jpy_swap_data`, `_jpy_annualized()` 수정 금지
6. `sync_from_github.py` BRANCH 변수 변경 금지

---

## 1. Stage 3 작업 내용

### 1.1 PR #11 — Replit Hotfix 반영 + MOVE Fetcher 확인

#### 1.1.1 작업 범위

Replit 로컬에만 적용된 hotfix 2건을 GitHub main 에 정식 반영 + MOVE fetcher 의 backfill 패턴 버그 확인.

#### 1.1.2 Hotfix 1 — `_PUBLIC_PREFIXES` 확장

`app.py` 의 `_PUBLIC_PREFIXES` 를 Replit 로컬 상태로 업데이트:

```python
_PUBLIC_PREFIXES = (
    "/auth/", "/health", "/static/",
    "/data", "/signal-desk", "/nyfed", "/fedop",
    "/volatility", "/jpy", "/portfolio",
    "/indicator/", "/history", "/records", "/credit",
    "/aa-input", "/fetch-now", "/signal-desk/recalculate"
)
```

추가로 `"/aa-input"`, `"/fetch-now"`, `"/signal-desk/recalculate"` 도 포함 (POST endpoint 인증 우회).

#### 1.1.3 Hotfix 2 — `data` → `d` 변수명 수정

`templates/index.html` 의 `loadFedOp()` 함수 내:

```javascript
// 변경 대상 (2곳)
const dw = data.discount_window;  → const dw = d.discount_window;
const tga = data.tga;             → const tga = d.tga;
```

**중요**: 이 외에도 `loadFedOp()` 함수 내에 `data.` 로 참조하는 곳이 더 있을 수 있음. `d.` 로 참조하는 부분과 `data.` 로 참조하는 부분을 전수 조사하여 **`d.` 로 통일**.

#### 1.1.4 MOVE Fetcher Backfill 패턴 확인

Stage 1 에서 LQD 의 backfill 패턴 버그를 발견했음:
- yfinance 기반 fetcher 가 `existing==0` 체크 없이 항상 짧은 기간만 fetch
- FRED 기반 fetcher 는 `limit=1000` 패턴으로 정상

MOVE Index 도 yfinance 기반이므로 같은 버그 가능성:

```python
# 확인할 함수: refresh_move()
# 다음 패턴이 있는지 확인:
existing = conn.execute("SELECT COUNT(*) FROM move_prices").fetchone()[0]
if existing == 0:
    hist = yf.Ticker("^MOVE").history(start="2022-01-01")  # 3년 backfill
else:
    hist = yf.Ticker("^MOVE").history(period="10d")         # 증분
```

**없으면 추가 (LQD/HYG 패턴 따름).**

#### 1.1.5 ADR

`docs/decisions/2026-04-22-stage3-replit-hotfix-sync.md`

내용:
- 2건의 hotfix 원인과 수정 내용
- MOVE fetcher 확인 결과
- Replit ↔ GitHub 동기화 교훈

#### 1.1.6 PR #11 체크리스트

- [ ] `_PUBLIC_PREFIXES` 확장 (Replit 로컬 상태와 일치)
- [ ] `loadFedOp()` 의 `data.` → `d.` 전수 수정
- [ ] `refresh_move()` backfill 패턴 확인 + 수정 (필요 시)
- [ ] ADR 작성
- [ ] 기존 다른 route/함수 영향 없음 확인

---

### 1.2 PR #12 — LDS (Lindy Distance Score) 구현

#### 1.2.1 배경 — 탈렙 논문

탈렙의 2026년 3월 논문 *"린디 효과의 수학적 재정의"*:
- 흡수 장벽 (absorbing barrier) 으로부터의 거리가 린디 속성을 결정
- 장벽에서 멀수록 파워로 생존 (린디 구간 = 안전)
- 장벽에 가까울수록 사망력 (hazard rate) 급등 (위험)
- **Remark 2**: 아무리 작은 음의 표류 (μ < 0) 도 파워로 생존을 파괴

TMRS 적용: Credit 지표의 **Crisis 임계값 = 흡수 장벽**. 현재값과 장벽 거리를 정규화.

#### 1.2.2 LDS 계산 함수

```python
def lindy_distance_score(current: float, barrier: float, direction: str = 'above') -> float:
    """
    Lindy Distance Score — 흡수 장벽으로부터의 거리를 0~1 로 정규화.
    
    Parameters:
        current: 현재 지표값
        barrier: 흡수 장벽 (= TMRS Crisis 임계값)
        direction: 'above' = 값이 장벽 위로 돌파하면 흡수 (OAS, VIX 등)
                   'below' = 값이 장벽 아래로 돌파하면 흡수 (HYG 등)
    
    Returns:
        0.0 (장벽 도달/돌파, 흡수) ~ 1.0 (장벽 원거리, 안전)
    """
    if direction == 'above':
        distance = (barrier - current) / barrier
    else:  # 'below'
        distance = (current - barrier) / abs(barrier) if barrier != 0 else 0.0
    
    return max(0.0, min(1.0, distance))
```

#### 1.2.3 대상 지표 + 흡수 장벽 정의

```python
LDS_INDICATORS = {
    'single_b_oas': {
        'name': 'Single-B OAS',
        'barrier': 600,       # bp — Crisis 임계
        'direction': 'above', # 600bp 이상이면 흡수
        'weight': 7,          # TMRS cap 비례 가중
        'unit': 'bp',
    },
    'cp_aa_spread': {
        'name': 'CP Spread (A2/P2-AA)',
        'barrier': 50,        # bp — Crisis 임계
        'direction': 'above',
        'weight': 6,
        'unit': 'bp',
    },
    'hy_oas': {
        'name': 'HY OAS',
        'barrier': 7.0,       # % — Crisis 임계
        'direction': 'above',
        'weight': 5,
        'unit': '%',
    },
    'hyg_daily': {
        'name': 'HYG 일간 변화',
        'barrier': -1.5,      # % — Crisis 임계
        'direction': 'below', # -1.5% 이하면 흡수
        'weight': 4,
        'unit': '%',
    },
}
```

#### 1.2.4 Composite LDS 계산

```python
def calculate_composite_lds(snapshot: dict) -> dict:
    """
    4개 Credit 지표의 가중 평균 LDS.
    
    Returns:
        {
            'composite': float (0~1),
            'individual': {
                'single_b_oas': {'value': ..., 'lds': ..., 'barrier': ...},
                ...
            },
            'tier': 'lindy' | 'pre_lindy' | 'hazard_rising' | 'absorption_imminent',
            'alert': bool (composite < 0.15)
        }
    """
    individual = {}
    weighted_sum = 0.0
    total_weight = 0
    
    for key, config in LDS_INDICATORS.items():
        indicator = snapshot.get(key, {})
        current_value = indicator.get('value')
        
        if current_value is None:
            continue
        
        lds = lindy_distance_score(
            current_value, config['barrier'], config['direction']
        )
        
        individual[key] = {
            'value': current_value,
            'lds': round(lds, 3),
            'barrier': config['barrier'],
            'name': config['name'],
            'unit': config['unit'],
        }
        
        weighted_sum += lds * config['weight']
        total_weight += config['weight']
    
    composite = weighted_sum / total_weight if total_weight > 0 else 0.0
    
    # Tier 판정
    if composite > 0.50:
        tier = 'lindy'
    elif composite > 0.25:
        tier = 'pre_lindy'
    elif composite > 0.10:
        tier = 'hazard_rising'
    else:
        tier = 'absorption_imminent'
    
    return {
        'composite': round(composite, 3),
        'individual': individual,
        'tier': tier,
        'alert': composite < 0.15,
    }
```

#### 1.2.5 LDS Tier 해석

| Composite LDS | Tier | 색상 | 의미 |
|---|---|---|---|
| > 0.50 | `lindy` | 🟢 | Credit 안전. 장벽 원거리. 파워로 생존 구간 |
| 0.25 ~ 0.50 | `pre_lindy` | 🟡 | 경계 필요. 일부 지표 장벽 접근 중 |
| 0.10 ~ 0.25 | `hazard_rising` | 🟠 | 사망력 급등. 다수 지표 장벽 근접 |
| < 0.10 | `absorption_imminent` | 🔴 | 흡수 임박. Crisis 돌파 직전 |

#### 1.2.6 Lindy Collapse Alert (Telegram)

```python
def check_lindy_collapse_alert(lds_result: dict):
    """
    Composite LDS < 0.15 시 Telegram 알람 발송.
    24h dedup 적용 (Inverse Turkey Alert 와 같은 패턴).
    """
    if not lds_result['alert']:
        return
    
    composite = lds_result['composite']
    individual = lds_result['individual']
    
    # 가장 위험한 지표 순서
    sorted_indicators = sorted(
        individual.items(), 
        key=lambda x: x[1]['lds']
    )
    
    detail_lines = []
    for key, info in sorted_indicators:
        emoji = '🔴' if info['lds'] < 0.10 else '🟠' if info['lds'] < 0.25 else '🟡'
        detail_lines.append(
            f"  {emoji} {info['name']}: {info['lds']:.2f} "
            f"(현재 {info['value']}{info['unit']} → 장벽 {info['barrier']}{info['unit']})"
        )
    
    message = (
        f"⚠️ [LINDY COLLAPSE WARNING]\n"
        f"Composite LDS: {composite:.3f} (임계 0.15 미만)\n\n"
        f"다수 Credit 지표가 흡수 장벽에 근접.\n"
        f"파워로 생존 구간 이탈 임박.\n\n"
        + "\n".join(detail_lines)
        + f"\n\nTier: {lds_result['tier']}"
    )
    
    send_telegram_alert(message, alert_type='lindy_collapse')
```

`telegram_alerts.py` 에 `lindy_collapse` 타입 추가. 24h dedup key 는 `"lindy_collapse"` 로 Inverse Turkey 와 독립.

#### 1.2.7 `/signal-desk` API 응답 확장

기존 `/signal-desk` 응답에 LDS 데이터 추가:

```python
@app.route("/signal-desk")
def signal_desk_data():
    # ... 기존 TMRS 계산
    
    # LDS 계산 추가
    lds_result = calculate_composite_lds(snapshot)
    
    return jsonify({
        # ... 기존 필드들
        'lds': lds_result,  # 신규
    })
```

#### 1.2.8 UI 변경 — TMRS Score 옆 카드 분할

**현재 구조** (TMRS Score 카드 + Inverse Turkey 카드):

```html
<div class="row">
  <div class="col-6"><!-- TMRS Score 카드 --></div>
  <div class="col-6"><!-- Inverse Turkey 카드 (전체) --></div>
</div>
```

**변경 구조** (Inverse Turkey 카드를 상단 LDS + 하단 IT 로 분할):

```html
<div class="row">
  <div class="col-6"><!-- TMRS Score 카드 --></div>
  <div class="col-6">
    <!-- ▲ 상단 60%: Lindy Distance Score -->
    <div class="lds-panel" style="height: 60%;">
      <h4>LINDY DISTANCE</h4>
      <div class="lds-composite">
        <span class="lds-value">🟢 0.54</span>
      </div>
      <div class="lds-indicators">
        <!-- 위험 순 정렬 (LDS 낮은 것 먼저) -->
        <div class="lds-row">
          <span>CP Sprd</span>
          <div class="lds-bar" style="width: 30%;"><!-- 0.30 --></div>
          <span>0.30</span>
        </div>
        <div class="lds-row">
          <span>S-B OAS</span>
          <div class="lds-bar" style="width: 49%;"><!-- 0.49 --></div>
          <span>0.49</span>
        </div>
        <div class="lds-row">
          <span>HY OAS</span>
          <div class="lds-bar" style="width: 59%;"><!-- 0.59 --></div>
          <span>0.59</span>
        </div>
        <div class="lds-row">
          <span>HYG Day</span>
          <div class="lds-bar" style="width: 91%;"><!-- 0.91 --></div>
          <span>0.91</span>
        </div>
      </div>
    </div>
    
    <!-- ▼ 하단 40%: Inverse Turkey -->
    <div class="it-panel" style="height: 40%;">
      <h4>INVERSE TURKEY</h4>
      <div>🐻 미감지</div>
      <div class="it-metrics">
        l12: 0.229 / l3: 0.107
      </div>
    </div>
  </div>
</div>
```

**LDS 진행 바 디자인**:
- 배경: 회색 (전체 구간)
- 채움: 녹색 → 노랑 → 빨강 그라데이션 (LDS 값에 따라)
- 정렬: LDS 낮은 것 (위험) 부터 상단에 배치

**LDS Composite 표시**:
- 🟢 (> 0.50), 🟡 (0.25~0.50), 🟠 (0.10~0.25), 🔴 (< 0.10)
- 숫자 크게 표시 (현재 "33.6" 과 비슷한 크기)

#### 1.2.9 Signal Desk 상세 카드에 LDS 추가

기존 상세 카드 (지표 클릭 시) 에 LDS 1줄 추가:

```
[Single-B OAS 클릭 시]
  현재: 307bp  전일: 310bp  7일전: 319bp
  임계: Normal <350 / Watch 350-450 / Stress 450-600 / Crisis >600
  
  🟡 Lindy Distance: 0.49 (장벽 600bp 까지 293bp 여유)
     ████████████████████░░░░░░░░░░ 49%
  
  Layer: 2 | 가중: 7pt | 기여: 0pt
  해석: ...
```

4개 LDS 대상 지표에만 표시. 나머지 지표는 LDS 줄 없음.

#### 1.2.10 ADR

`docs/decisions/2026-04-22-stage3-lindy-distance-score.md`

내용:
- 탈렙 논문 핵심 명제 (Remark 2)
- LDS 개념: Crisis 임계 = 흡수 장벽, 거리 정규화
- 4개 대상 지표 + 가중치 결정 근거
- Composite 가중 평균 방식
- UI 레이아웃 (카드 분할)
- Lindy Collapse Alert 조건 (< 0.15)
- Inverse Turkey 와의 관계 (보완적, 중복 아님)

#### 1.2.11 PR #12 체크리스트

- [ ] `lindy_distance_score()` 함수
- [ ] `LDS_INDICATORS` 상수 (4개 지표 + 장벽 + 가중)
- [ ] `calculate_composite_lds()` 함수
- [ ] `/signal-desk` 응답에 `lds` 필드 추가
- [ ] Signal Desk 우측 카드 분할 (상단 LDS 60% + 하단 IT 40%)
- [ ] LDS Composite 값 + Tier 색상 표시
- [ ] 4개 개별 지표 진행 바 (위험 순 정렬)
- [ ] Inverse Turkey 하단 유지 (l12, l3 수치 표시)
- [ ] 상세 카드에 LDS 1줄 추가 (4개 대상 지표만)
- [ ] Lindy Collapse Alert (Telegram, 24h dedup)
- [ ] `telegram_alerts.py` 에 `lindy_collapse` 타입 추가
- [ ] ADR 작성

---

### 1.3 PR #13 — 명칭/임계 정리

#### 1.3.1 FRA-OIS → SOFR Term Premium 명칭 변경

**배경**: "FRA-OIS Spread" 는 LIBOR 시대 용어. 현재 시스템은 SOFR 90일 - EFFR 을 측정하므로 "SOFR Term Premium" 이 정확.

**변경 대상**:
- `app.py` 의 변수명, 함수명, 주석 (가능한 범위)
- `templates/index.html` 의 표시명
- `snapshot` 키는 **변경 안 함** (기존 데이터 호환성) — 표시명만 변경

**주의**: snapshot 키 (`sofr_term` 등) 는 DB 에 저장된 이력과 호환되어야 하므로 변경하면 이전 레코드 조회 시 문제. **UI 표시명만 변경**.

#### 1.3.2 HY OAS 임계 v1.0 원문 정합성 확인

현재 코드의 HY OAS 임계: `3.5 / 5.0 / 7.0 %`
v1.0 카테고리 3.5.1 원문: `300 / 400 / 550 bp` (= `3.0 / 4.0 / 5.5 %`)

**확인할 것**:
1. v1.0 원문의 정확한 임계 재확인
2. 현재 코드가 어느 버전을 사용 중인지
3. 둘 중 어느 것이 더 적절한지 판단

**판단 기준**: v1.0 원문이 더 보수적 (낮은 임계 = 더 빨리 경고). TW 에게 결과 보고 후 결정.

#### 1.3.3 v1.0 카테고리 3.4.4 정정 문서

코드 변경 없음. 문서만 작성:

`docs/corrections/v1.0-jpy-basis-direction-correction.md`

내용:
- v1.0 원문의 USD/JPY Basis 임계 (±5bp / -5~-10bp 등)
- GPT 프레임워크의 통찰 ("절대값 변화 기준")
- 사상적 정정: "음수가 클수록 위험" → "절대값이 0 에 가까워질수록 위험"
- Stage 2.4 에서 이 재해석 반영한 percentile 임계 적용 예정
- 본 문서는 v1.0 통합문서의 **정오표 (errata)** 성격

#### 1.3.4 ADR

`docs/decisions/2026-04-22-stage3-naming-threshold-cleanup.md`

#### 1.3.5 PR #13 체크리스트

- [ ] FRA-OIS → SOFR Term Premium UI 표시명 변경
- [ ] HY OAS 임계 v1.0 원문 정합성 확인 + TW 보고
- [ ] `docs/corrections/v1.0-jpy-basis-direction-correction.md` 작성
- [ ] ADR 작성
- [ ] snapshot 키 변경 없음 (호환성 유지)

---

## 2. Stage 3 완료 조건

### 2.1 체크리스트 요약

- [ ] PR #11 — Replit hotfix 2건 반영 + MOVE fetcher 확인
- [ ] PR #12 — LDS 4개 지표 + Composite + UI + Alert
- [ ] PR #13 — 명칭/임계 정리 + 정정 문서
- [ ] 모든 PR GitHub main merge 완료
- [ ] Replit sync + 앱 재시작 후 정상 작동 확인

### 2.2 Stage 3 완료 후 예상 상태

```
Signal Desk 우측 카드:
  상단: LINDY DISTANCE 🟢 0.54
        CP Sprd ███░░░ 0.30
        S-B OAS ████░░ 0.49
        HY OAS  █████░ 0.59
        HYG Day ██████ 0.91
  하단: INVERSE TURKEY 🐻 미감지
        l12: 0.229 / l3: 0.107

MOVE fetcher: backfill 패턴 수정 완료 (필요 시)
Fed Operation 탭: DW/TGA 정상 렌더링 (hotfix 반영)
명칭: SOFR Term Premium (FRA-OIS 대체)
```

---

## 3. 작업 원칙 재확인

### 3.1 반드시 지킬 것

1. 새 feature branch (claude/stage3-hotfix, claude/stage3-lds, claude/stage3-naming)
2. PR base = main
3. ADR 포함
4. TW 검토 대기
5. LDS 계산에서 기존 TMRS 점수 로직 변경 없음 (병렬 독립 계산)
6. Inverse Turkey 로직 변경 없음 (하단 유지만)

### 3.2 피할 것

1. 이전 feature branch 에 추가 커밋
2. `sync_from_github.py` BRANCH 변수 변경
3. `score_version`, `threshold_table_version` 변경
4. snapshot 키 변경 (호환성)
5. LDS 를 TMRS 점수에 통합 (별도 독립 지표로만 표시)

---

## 4. 착수 메시지 (TW → Claude Code)

> Stage 2 가 모두 완료되어 Stage 3 을 시작한다.
>
> 먼저 `Stage3_Instructions.md` 를 전체 읽어줘. 특히 **Section 0.5** 를 반드시 먼저 확인 — Replit 로컬 hotfix 2건 (GitHub 미반영), LDS 도입 결정, v1.0 카테고리 3.4.4 재해석 등 너가 모르는 변경사항이 있어.
>
> 읽은 후 다음을 보고해줘:
>
> 1. Section 0.5 핵심 변경사항 이해도 요약 (5줄)
> 2. 3개 PR 중 어느 것부터 시작할지 제안
> 3. PR #12 (LDS) 구현 시 예상 기술 이슈 (있다면)
>
> **중요한 작업 원칙**:
> - Replit 로컬 hotfix 2건이 GitHub main 에 없음. PR #11 에서 이 2건을 먼저 반영해야 PR #12/#13 과 충돌 방지
> - LDS 는 TMRS 점수와 독립적으로 계산 (기존 점수 로직 변경 없음)
> - Inverse Turkey 로직 변경 없음 (UI 하단 이동만)
> - `sync_from_github.py` BRANCH 변경 금지
>
> Stage 3 시작 준비해줘.

---

**끝 (End of Stage 3 Instructions)**

*Financial Tracker — v1.0.1 Stage 3 Instructions*
*작성: 2026-04-22 | TW × Claude Opus 4.6*
