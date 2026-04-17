"""
Google OAuth 인증 블루프린트
- authlib + Flask-Login
- 화이트리스트: ADMIN_EMAILS 환경변수
- 30일 영구 세션 (remember=True)
- SQLite users 테이블 자동 기록
"""
import os
import sqlite3
import logging
from datetime import datetime

import pytz
from flask import (
    Blueprint, redirect, url_for, request, render_template, g
)
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user, current_user
)
from authlib.integrations.flask_client import OAuth

log = logging.getLogger(__name__)
KST = pytz.timezone("Asia/Seoul")

# ── 관리자/허용 이메일 화이트리스트 ──────────────────────────
ALLOWED_EMAILS: set[str] = set(
    e.strip() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()
)

# ── Flask-Login / OAuth 인스턴스 (앱 등록 전) ───────────────
login_manager = LoginManager()
oauth = OAuth()

# ── 인메모리 사용자 저장소 ────────────────────────────────────
_user_store: dict[str, "User"] = {}
_DB_PATH = ""


class User(UserMixin):
    """Flask-Login 호환 사용자 모델 (Google OAuth)."""
    def __init__(self, email: str, name: str, picture: str = ""):
        self.id      = email
        self.email   = email
        self.name    = name
        self.picture = picture

    def is_admin(self) -> bool:
        return self.email in ALLOWED_EMAILS


# ── 블루프린트 ────────────────────────────────────────────────
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def init_auth(app, db_path: str) -> None:
    """Flask 앱에 Google OAuth + Flask-Login을 초기화합니다."""
    global _DB_PATH
    _DB_PATH = db_path

    # Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = None

    # Authlib OAuth
    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=os.environ.get("GOOGLE_CLIENT_ID"),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

    @login_manager.user_loader
    def load_user(user_id: str):
        return _user_store.get(user_id)


def _record_login(email: str, name: str, ip: str) -> None:
    """users 테이블에 로그인 시각/IP를 기록합니다."""
    now_kst = datetime.now(tz=KST).strftime("%Y-%m-%d %H:%M:%S KST")
    try:
        conn = sqlite3.connect(_DB_PATH)
        conn.execute("""
            INSERT INTO users (email, name, last_login, last_ip, login_count, first_login)
            VALUES (?, ?, ?, ?, 1, ?)
            ON CONFLICT(email) DO UPDATE SET
                name        = excluded.name,
                last_login  = excluded.last_login,
                last_ip     = excluded.last_ip,
                login_count = login_count + 1
        """, (email, name, now_kst, ip, now_kst))
        conn.commit()
        conn.close()
    except Exception as exc:
        log.error(f"[Auth] users 기록 실패: {exc}")


# ── 라우트 ────────────────────────────────────────────────────

@auth_bp.route("/login")
def login():
    """SIGNALS 로그인 페이지를 표시합니다."""
    if current_user.is_authenticated:
        return redirect("/")
    return render_template("login.html")


@auth_bp.route("/google")
def google_login():
    """Google OAuth 플로우를 시작합니다."""
    # Replit 프록시 환경에서 HTTPS redirect_uri 생성
    scheme = "https"
    host   = request.host
    redirect_uri = f"{scheme}://{host}/auth/callback"
    log.info(f"[Auth] Google 로그인 시작 → redirect_uri={redirect_uri}")
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route("/callback")
def callback():
    """Google OAuth 콜백: 토큰 교환 → 화이트리스트 확인 → 로그인."""
    try:
        token    = oauth.google.authorize_access_token()
        userinfo = token.get("userinfo") or {}
        email    = userinfo.get("email", "")
        name     = userinfo.get("name", email)
        picture  = userinfo.get("picture", "")

        # 화이트리스트 확인
        if ALLOWED_EMAILS and email not in ALLOWED_EMAILS:
            log.warning(f"[Auth] 미허가 접근 시도: {email}")
            return render_template(
                "login.html",
                error=f"접근 권한이 없습니다 ({email}). 관리자에게 문의하세요."
            )

        # User 생성 및 저장
        user = User(email=email, name=name, picture=picture)
        _user_store[email] = user

        # 30일 영구 로그인
        login_user(user, remember=True)

        # IP 추출 (Replit 리버스 프록시 고려)
        ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.remote_addr
            or "unknown"
        )
        _record_login(email, name, ip)
        log.info(f"[Auth] 로그인 성공: {email} ({ip})")

        # next 파라미터가 있으면 그쪽으로, 아니면 홈으로
        next_url = request.args.get("next") or "/"
        return redirect(next_url)

    except Exception as exc:
        import traceback
        log.error(f"[Auth] 콜백 오류 상세: {exc}\n{traceback.format_exc()}")
        # Google이 직접 에러를 콜백으로 전달하는 경우 (access_denied, redirect_uri_mismatch 등)
        error_code = request.args.get("error")
        error_desc = request.args.get("error_description", "")
        if error_code:
            log.error(f"[Auth] Google 오류 코드: {error_code} / 설명: {error_desc}")
            msg = f"Google 인증 오류: {error_code}"
            if error_desc:
                msg += f" — {error_desc}"
        else:
            msg = f"로그인 중 오류가 발생했습니다: {exc}"
        return render_template("login.html", error=msg)


@auth_bp.route("/logout")
def logout():
    """로그아웃 후 로그인 페이지로 이동합니다."""
    email = getattr(current_user, "email", "unknown")
    log.info(f"[Auth] 로그아웃: {email}")
    logout_user()
    return redirect("/auth/login")
