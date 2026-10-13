import time
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.email import send_otp_email
from app.core.images import ImageError, check_image, read_upload
from app.core.ratelimit import SlidingWindowLimiter
from app.core.security import (
    create_access_token,
    generate_otp,
    get_current_user,
    get_current_user_any,
    hash_otp,
    hash_password,
    verify_otp,
    verify_password,
)
from app.api.routes.listings import _delete_upload_files
from app.core.storage import storage
from app.db.session import get_db  # <-- point this at your existing db session dependency
from app.models.otp import OTPCode
from app.models.user import User
from app.schemas.auth import (
    AccountTypeRequest,
    ForgotPasswordRequest,
    InterestsRequest,
    LoginCodeRequest,
    LoginResponse,
    OtpLoginRequest,
    PasswordLoginRequest,
    ProfileRequest,
    ProfileUpdateRequest,
    ResetPasswordRequest,
    SetPasswordRequest,
    SignupRequest,
    SignupVerifyRequest,
    UserOut,
    ViewsRequest,
)

router = APIRouter(prefix="/api", tags=["auth"])

MAX_AVATAR_BYTES = 5 * 1024 * 1024
VIEW_HISTORY_MAX = 50


def _check_domain(email: str) -> None:
    # Owners (OWNER_EMAILS) may use a personal address; everyone else needs a college email.
    if email.lower() in {e.lower() for e in settings.OWNER_EMAILS}:
        return
    domain = email.split("@")[-1].lower()
    if domain not in settings.ALLOWED_EMAIL_DOMAINS:
        raise HTTPException(status_code=400, detail=f"{domain} is not a recognised campus email")


def _issue_otp(db: Session, email: str, purpose: str) -> str:
    """Invalidate any earlier unused code for this email and store a new one (caller commits)."""
    otp = generate_otp()
    expires_at = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
    db.query(OTPCode).filter(OTPCode.email == email).delete()
    db.add(OTPCode(email=email, code_hash=hash_otp(otp), expires_at=expires_at, purpose=purpose))
    return otp


def _consume_otp(db: Session, email: str, otp: str, purpose: str) -> None:
    """Check a code; it works once, only for its purpose, and dies after too many wrong guesses."""
    record = (
        db.query(OTPCode)
        .filter(OTPCode.email == email, OTPCode.purpose == purpose)
        .order_by(OTPCode.created_at.desc())
        .first()
    )
    if not record or record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Code expired, request a new one")
    if record.attempts >= settings.OTP_MAX_ATTEMPTS:
        raise HTTPException(status_code=400, detail="Too many wrong codes. Request a new one.")
    if not verify_otp(otp.strip(), record.code_hash):
        record.attempts += 1
        db.commit()
        raise HTTPException(status_code=400, detail="Incorrect code")
    db.delete(record)


def _login_response(user: User) -> dict:
    return {"token": create_access_token(user.id), "user": user}


def _find_user(db: Session, email: str) -> User | None:
    return db.query(User).filter(func.lower(User.email) == email.lower()).first()


INVALID_LOGIN = "Invalid email or password"
LOCKED_MESSAGE = "Too many failed attempts. Try again in a few minutes, or use Forgot password."
_login_ip_limiter = SlidingWindowLimiter(settings.LOGIN_IP_LIMIT, settings.LOGIN_IP_WINDOW_MINUTES * 60)
# Stops email bombing and protects the Brevo quota (each code is one email).
_code_email_limiter = SlidingWindowLimiter(1, settings.CODE_EMAIL_COOLDOWN_SECONDS)
_code_ip_limiter = SlidingWindowLimiter(settings.CODE_IP_LIMIT, settings.CODE_IP_WINDOW_MINUTES * 60)
CODE_TOO_SOON = "Please wait a minute before asking for another code."


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _may_send_code(request: Request, email: str) -> bool:
    return _code_ip_limiter.allow(_client_ip(request)) and _code_email_limiter.allow(email.lower())


# ---------- signup (code proves the college email; account + password created after) ----------


@router.post("/auth/signup")
def signup(payload: SignupRequest, request: Request, db: Session = Depends(get_db)):
    """Step 1: send a code. Nothing is created until the code is verified (step 2)."""
    _check_domain(payload.email)
    existing = _find_user(db, payload.email)
    if existing and existing.verified:
        raise HTTPException(status_code=409, detail="An account with this email already exists. Log in instead.")
    if not _may_send_code(request, payload.email):
        raise HTTPException(status_code=429, detail=CODE_TOO_SOON)
    otp = _issue_otp(db, payload.email, "signup")
    db.commit()
    send_otp_email(payload.email, otp)
    return {"message": "OTP sent"}


@router.post("/auth/signup/verify", response_model=LoginResponse)
def signup_verify(payload: SignupVerifyRequest, db: Session = Depends(get_db)):
    """Step 2: check the code, then create the verified account with its password."""
    _check_domain(payload.email)
    existing = _find_user(db, payload.email)
    if existing and existing.verified:
        raise HTTPException(status_code=409, detail="An account with this email already exists. Log in instead.")
    _consume_otp(db, payload.email, payload.otp, "signup")

    # A row may exist from the old flow (signup started, never verified); finish it.
    user = existing or User(email=payload.email)
    if not existing:
        db.add(user)
    user.account_type = payload.account_type
    user.verified = True
    user.password_hash = hash_password(payload.password)
    user.password_changed_at = datetime.utcnow()  # logs out every older session
    db.commit()
    db.refresh(user)
    return _login_response(user)


# ---------- login ----------


@router.post("/auth/login", response_model=LoginResponse)
def login(payload: PasswordLoginRequest, request: Request, db: Session = Depends(get_db)):
    """Email + password. One generic error for a wrong email OR password."""
    if not _login_ip_limiter.allow(_client_ip(request)):
        raise HTTPException(status_code=429, detail="Too many login attempts. Wait a few minutes and try again.")

    user = _find_user(db, payload.email)
    now = datetime.utcnow()
    if not user or not user.verified:
        verify_password(payload.password, None)  # same work as a real check, so timing gives nothing away
        raise HTTPException(status_code=401, detail=INVALID_LOGIN)
    if user.locked_until and user.locked_until > now:
        raise HTTPException(status_code=429, detail=LOCKED_MESSAGE)
    if not user.password_hash:
        # Accounts from before passwords existed: the frontend falls back to a one-time code,
        # then makes them create a password.
        raise HTTPException(status_code=403, detail={
            "code": "password_not_set",
            "message": "You haven't set a password yet. We'll email you a code to log in.",
        })
    if not verify_password(payload.password, user.password_hash):
        user.failed_logins = (user.failed_logins or 0) + 1
        locked = user.failed_logins >= settings.LOGIN_MAX_FAILURES
        if locked:
            user.locked_until = now + timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
            user.failed_logins = 0
        db.commit()
        raise HTTPException(status_code=429 if locked else 401, detail=LOCKED_MESSAGE if locked else INVALID_LOGIN)

    user.failed_logins = 0
    user.locked_until = None
    db.commit()
    db.refresh(user)
    return _login_response(user)


@router.post("/auth/login-code")
def login_code(payload: LoginCodeRequest, request: Request, db: Session = Depends(get_db)):
    """Send a one-time login code. Only for existing accounts that have no password yet;
    everyone else logs in with their password (or uses Forgot password)."""
    _check_domain(payload.email)
    user = _find_user(db, payload.email)
    if not user or not user.verified:
        raise HTTPException(status_code=404, detail="No account with this email yet. Sign up first.")
    if user.password_hash:
        raise HTTPException(status_code=400, detail="This account has a password. Log in with it, or use Forgot password.")
    if not _may_send_code(request, payload.email):
        raise HTTPException(status_code=429, detail=CODE_TOO_SOON)
    otp = _issue_otp(db, payload.email, "login")
    db.commit()
    send_otp_email(payload.email, otp)
    return {"message": "OTP sent"}


@router.post("/auth/login/otp", response_model=LoginResponse)
def login_with_code(payload: OtpLoginRequest, db: Session = Depends(get_db)):
    """One-time code login for accounts without a password. Afterwards the app shows the
    mandatory "Create a password" step (and every other endpoint refuses until it's done)."""
    user = _find_user(db, payload.email)
    if not user or not user.verified:
        raise HTTPException(status_code=400, detail="Code expired, request a new one")
    if user.password_hash:
        raise HTTPException(status_code=400, detail="This account has a password. Log in with it, or use Forgot password.")
    _consume_otp(db, payload.email, payload.otp, "login")
    db.commit()
    db.refresh(user)
    return _login_response(user)


# ---------- passwords ----------


@router.post("/auth/set-password", response_model=LoginResponse)
def set_password(
    payload: SetPasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_any),
):
    """First password for an account that doesn't have one. Changing an existing password
    goes through Forgot password (which proves the email again)."""
    if user.password_hash:
        raise HTTPException(status_code=409, detail="You already have a password. Use Forgot password to change it.")
    user.password_hash = hash_password(payload.password)
    user.password_changed_at = datetime.utcnow()  # logs out every older session
    db.commit()
    db.refresh(user)
    # The change logs out older sessions, including this one, so hand back a fresh one.
    return _login_response(user)


@router.post("/auth/password/forgot")
def forgot_password(payload: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Email a reset code. Same answer whether or not the account exists (and when rate-limited,
    so the limit can't be used to find out which emails have accounts)."""
    _check_domain(payload.email)
    user = _find_user(db, payload.email)
    if user and user.verified and _may_send_code(request, payload.email):
        otp = _issue_otp(db, payload.email, "reset")
        db.commit()
        send_otp_email(payload.email, otp)
    return {"message": "If an account exists for this email, we've sent it a code."}


@router.post("/auth/password/reset", response_model=LoginResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Check the reset code, set the new password, unlock the account and log in."""
    _consume_otp(db, payload.email, payload.otp, "reset")
    user = _find_user(db, payload.email)
    if not user or not user.verified:
        raise HTTPException(status_code=400, detail="Code expired, request a new one")
    user.password_hash = hash_password(payload.password)
    user.password_changed_at = datetime.utcnow()  # logs out every older session
    user.failed_logins = 0
    user.locked_until = None
    db.commit()
    db.refresh(user)
    return _login_response(user)


@router.post("/auth/profile", response_model=UserOut)
def complete_profile(
    payload: ProfileRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    user.name = payload.name
    user.college = payload.college
    user.course = payload.course
    user.year = payload.year
    user.phone = payload.phone
    user.profile_completed = True
    db.commit()
    db.refresh(user)
    return user


@router.post("/auth/interests", response_model=UserOut)
def save_interests(
    payload: InterestsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    user.interests = payload.interests
    db.commit()
    db.refresh(user)
    return user


@router.post("/auth/account-type", response_model=UserOut)
def set_account_type(
    payload: AccountTypeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Buyers can upgrade to seller. Going back is blocked so a seller's
    # existing listings never end up owned by an account that can't manage them.
    if user.account_type == "seller" and payload.account_type == "buyer":
        raise HTTPException(status_code=400, detail="Seller accounts can't switch back to buyer")
    user.account_type = payload.account_type
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/me", response_model=UserOut)
def update_profile(
    payload: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/me/avatar", response_model=UserOut)
def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        data = read_upload(file.file, MAX_AVATAR_BYTES)
        content_type, ext = check_image(data)  # by the actual bytes, not the file name or browser's label
    except ImageError as e:
        raise HTTPException(status_code=400, detail=str(e).replace("Images must", "Profile picture must"))

    key = f"avatars/{uuid.uuid4().hex}{ext}"
    storage.put_public(key, data, content_type)

    old = user.avatar_url
    user.avatar_url = storage.public_url(key, str(request.base_url))
    db.commit()
    db.refresh(user)
    if old:
        _delete_upload_files([old])
    return user


@router.delete("/users/me/avatar", response_model=UserOut)
def remove_avatar(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    old = user.avatar_url
    user.avatar_url = None
    db.commit()
    db.refresh(user)
    if old:
        _delete_upload_files([old])
    return user


@router.post("/users/me/views", status_code=204)
def record_views(
    payload: ViewsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Append opened listings/resources to the user's history (used for recommendations),
    so it follows them across devices. Keeps the most recent VIEW_HISTORY_MAX entries."""
    now = time.time() * 1000
    added = [{"kind": v.kind, "key": v.key, "ts": now} for v in payload.views]
    # Assign a new list so SQLAlchemy notices the JSON column changed.
    user.view_history = [*(user.view_history or []), *added][-VIEW_HISTORY_MAX:]
    db.commit()


@router.post("/auth/refresh", response_model=LoginResponse)
def refresh_session(user: User = Depends(get_current_user_any)):
    """Swap a still-valid session for a fresh 30-day one. The app calls this on start-up, so
    regular users never get logged out. Old sessions killed by a password change can't renew."""
    return _login_response(user)


@router.get("/users/me", response_model=UserOut)
def me(user: User = Depends(get_current_user_any)):  # allowed before a password exists, so the app can ask for one
    return user
