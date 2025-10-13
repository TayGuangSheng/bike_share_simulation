from datetime import datetime, timedelta
import bcrypt
from jose import JWTError, jwt
from .config import settings

ALGO = "HS256"

def create_access_token(sub: str, expires_minutes: int | None = None) -> str:
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes or settings.access_token_expire_minutes)
    to_encode = {"sub": sub, "exp": expire}
    return jwt.encode(to_encode, settings.secret_key.get_secret_value(), algorithm=ALGO)

def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.secret_key.get_secret_value(), algorithms=[ALGO])
    except JWTError as exc:
        raise ValueError("Invalid token") from exc
    sub = payload.get("sub")
    if not sub:
        raise ValueError("Token missing subject")
    return str(sub)

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False

def hash_password(plain: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")
