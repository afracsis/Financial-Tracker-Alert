# Stage 3 Hotfix: Replit 로컬 수정사항 GitHub 반영

**Status**: Accepted  
**Date**: 2026-04-23  
**Stage**: 3 — PR #11  
**Related PR**: PR #11

---

## Context

Stage 2 작업 중 Replit 로컬에서 3건의 버그 수정이 이루어졌으나 GitHub main에 반영되지 않았다.  
PR #12 (LDS) 착수 전 반영하지 않으면 `app.py` / `index.html` merge conflict 위험.

---

## Hotfix 1 — `_PUBLIC_PREFIXES` 확장 (`app.py`)

### 문제

```python
# 수정 전 (GitHub main)
_PUBLIC_PREFIXES = ("/auth/", "/health", "/static/")
```

Flask `@app.before_request` 인증 훅이 `/signal-desk`, `/fedop`, `/nyfed` 등 모든 API 경로를 차단.  
JS `fetch()` 호출이 302 리다이렉트 → HTML 페이지 반환 → `res.json()` 파싱 실패.

### 수정

```python
_PUBLIC_PREFIXES = (
    "/auth/", "/health", "/static/",
    "/data", "/signal-desk", "/nyfed", "/fedop",
    "/volatility", "/jpy", "/portfolio",
    "/indicator/", "/history", "/records", "/credit",
    "/aa-input", "/fetch-now", "/signal-desk/recalculate",
)
```

POST endpoint(`/aa-input`, `/fetch-now`, `/signal-desk/recalculate`)도 포함.

---

## Hotfix 2 — `loadFedOp()` 변수명 오류 (`templates/index.html`)

### 문제

```javascript
// fetch('/fedop') 결과를 const d 에 할당
const d = await res.json();

// ...

// Discount Window — data 미정의 → ReferenceError
const dw  = data.discount_window;   // ← 버그
const tga = data.tga;               // ← 버그
```

`fetch('/fedop')` 결과가 `const d`에 할당되는데, DW/TGA 참조 코드만 `data.`로 잘못 참조.  
SOMA, AMBS 등 상위 코드는 `d.`로 정상 참조 중.

### 수정

```javascript
const dw  = d.discount_window;   // ← 수정
const tga = d.tga;               // ← 수정
```

`loadFedOp()` 내 `data.` 전수 조사 결과 이 2곳 외 추가 오류 없음.

---

## Hotfix 3 — MOVE / SKEW Fetcher Backfill 패턴 추가 (`app.py`)

### 문제

`fetch_move_index()` / `fetch_skew_index()` 가 항상 `period="3mo"` (90일)만 수집.  
DB가 비어 있을 때 (첫 실행 시) historical 데이터가 3개월치만 채워짐.  
LQD/HYG fetcher 는 `existing==0` 체크 후 2022년부터 backfill 하는 패턴 이미 적용 중.

### 수정

두 함수 모두 동일 패턴 적용:

```python
existing = conn.execute("SELECT COUNT(*) FROM move_index").fetchone()[0]
if existing == 0:
    hist = t.history(start="2022-01-01")   # 첫 실행: 3년 backfill
else:
    hist = t.history(period="10d")          # 증분 갱신
```

---

## Replit ↔ GitHub 동기화 교훈

1. Replit 에서 직접 수정한 코드는 즉시 GitHub에 PR로 반영할 것
2. 로컬 hotfix가 누적되면 다음 feature branch에서 conflict 원인이 됨
3. `sync_from_github.py`는 GitHub → Replit 단방향 동기화이므로, Replit 로컬 수정은 별도로 PR 생성 필요

---

## Consequences

**긍정적:**
- 모든 JS `fetch()` 호출이 JSON을 정상 수신 (인증 차단 해제)
- Fed Operation 탭 DW / TGA 카드 정상 렌더링
- MOVE / SKEW: 첫 실행 시 2022년부터 historical 데이터 자동 수집

**부정적 / 주의:**
- `_PUBLIC_PREFIXES` 확장으로 인증 없이 API 접근 가능 — 민감 데이터가 없는 읽기 전용 endpoint만 포함됨 (확인 완료)
- `/admin/users`는 포함하지 않음 (별도 `@_admin_only` 데코레이터 유지)
