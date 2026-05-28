from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


BCRYPT_ROUNDS = 12


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.APP_SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """토큰을 디코딩하여 user_id(sub)를 반환. 실패 시 None."""
    try:
        payload = jwt.decode(
            token,
            settings.APP_SECRET_KEY,
            algorithms=[ALGORITHM],  # none 알고리즘 명시적 차단
            options={"verify_exp": True},
        )
        return payload.get("sub")
    except JWTError:
        return None
