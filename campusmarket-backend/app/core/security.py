import hashlib
import hmac
import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db  # <-- point this at your existing db session dependency
from app.models.user import User

bearer_scheme = HTTPBearer()
optional_bearer_scheme = HTTPBearer(auto_error=False)


def generate_otp(length: int = 6) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(length))


def hash_otp(otp: str) -> str:
    return hashlib.sha256(f"{otp}{settings.OTP_PEPPER}".encode()).hexdigest()


def verify_otp(otp: str, hashed: str) -> bool:
    return hmac.compare_digest(hash_otp(otp), hashed)


# --- Passwords (argon2id; never store or log the plain text) ---

_hasher = PasswordHasher()
# Checked against when the email doesn't exist, so a wrong email takes as long as a wrong password.
_DUMMY_HASH = _hasher.hash("not-a-real-password-0")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(user_id) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return uuid.UUID(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired, log in again")
    except (jwt.InvalidTokenError, KeyError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user_any(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Any logged-in user, including accounts that still have to create a password.
    Only GET /users/me and POST /auth/set-password use this directly."""
    user_id = decode_access_token(credentials.credentials)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


PASSWORD_REQUIRED = {"code": "password_required", "message": "Create a password to continue"}


def get_current_user(user: User = Depends(get_current_user_any)) -> User:
    """Logged in AND has a password. Accounts created before passwords existed are blocked
    from everything (all other dependencies build on this one) until they set one."""
    if not user.password_hash:
        raise HTTPException(status_code=403, detail=PASSWORD_REQUIRED)
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """Like get_current_user, but guests (no or bad token) get None instead of a 401.
    Accounts that still need to create a password are treated as guests too."""
    if not credentials:
        return None
    try:
        user_id = decode_access_token(credentials.credentials)
    except HTTPException:
        return None
    user = db.query(User).filter(User.id == user_id).first()
    return user if user and user.password_hash else None


def require_verified(user: User = Depends(get_current_user)) -> User:
    """Logged in AND verified college email. Guards everything marketplace-related."""
    if not user.verified:
        raise HTTPException(status_code=403, detail="Verify your college email first")
    return user


def require_seller(user: User = Depends(get_current_user)) -> User:
    if user.account_type != "seller" and not user.is_admin:
        raise HTTPException(status_code=403, detail="Only seller accounts can list items")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """The owner(s) in OWNER_EMAILS and the admins they approved."""
    if not user.is_admin or not user.verified:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def require_owner(user: User = Depends(get_current_user)) -> User:
    """Only owners can approve or remove admins."""
    if not user.is_owner or not user.verified:
        raise HTTPException(status_code=403, detail="Only the owner can change who is an admin")
    return user
