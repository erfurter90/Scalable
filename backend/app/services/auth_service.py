from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models.user import User


def authenticate(db: Session, username: str, password: str) -> User | None:
    """Returns the User if credentials are valid, else None. Deliberately returns None
    rather than raising for both "user not found" and "wrong password" so the router
    can give a single generic error — never revealing which half was wrong."""
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
