"""Password hashing and session-token signing for the single-user auth boundary."""

import bcrypt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import get_settings

settings = get_settings()
_serializer = URLSafeTimedSerializer(settings.secret_key, salt="finanz-agent-session")


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_session_token(user_id: int) -> str:
    """Signed, timestamped token carrying only the user id. Stored client-side as an
    httpOnly cookie; validity is re-checked (signature + max_age) on every request."""
    return _serializer.dumps({"user_id": user_id})


def read_session_token(token: str, max_age_seconds: int) -> int | None:
    """Returns the user_id if the token is valid and unexpired, else None."""
    try:
        data = _serializer.loads(token, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None
    return data.get("user_id")
