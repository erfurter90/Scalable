"""One-off CLI to create (or reset the password of) the single app user.

There is no public signup endpoint by design — this is a personal, single-user app.

Usage:
    python scripts/create_user.py --username admin --password "correct horse battery staple"

If --username/--password are omitted, falls back to BOOTSTRAP_USERNAME/BOOTSTRAP_PASSWORD
from settings (.env), which is convenient for first-time local setup but should not be
relied on for anything beyond that.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default=settings.bootstrap_username)
    parser.add_argument("--password", default=settings.bootstrap_password)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == args.username).first()
        if user is None:
            user = User(username=args.username, hashed_password=hash_password(args.password))
            db.add(user)
            print(f"Created user '{args.username}'.")
        else:
            user.hashed_password = hash_password(args.password)
            print(f"Updated password for existing user '{args.username}'.")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
