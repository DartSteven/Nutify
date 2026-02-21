"""
CLI utility to reset the primary admin password.
"""

import argparse
import getpass
import os

from flask import Flask

from core.db.model_classes import init_model_classes
from core.db.ups import db
from core.logger import system_logger as logger
from core.settings import DB_URI, INSTANCE_PATH


def build_app() -> Flask:
    """Create a minimal Flask app for database access."""
    app = Flask(__name__, instance_path=INSTANCE_PATH)
    app.config['SQLALCHEMY_DATABASE_URI'] = DB_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    secret_key = os.getenv('SECRET_KEY')
    if secret_key:
        app.config['SECRET_KEY'] = secret_key

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset the Nutify admin password.")
    parser.add_argument(
        '--username',
        default=None,
        help='Admin username to reset (defaults to ID 1 or current admin).'
    )
    parser.add_argument(
        '--password',
        default=None,
        help='New admin password (if omitted, you will be prompted).'
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    new_password = args.password
    if not new_password:
        new_password = getpass.getpass('New admin password: ')
        confirm = getpass.getpass('Confirm new admin password: ')
        if new_password != confirm:
            print("❌ Passwords do not match.")
            return 1

    if len(new_password) < 6:
        print("❌ Password must be at least 6 characters long.")
        return 1

    app = build_app()
    db.init_app(app)

    with app.app_context():
        models = init_model_classes(db, lambda: None)
        login_model = models.LoginAuth
        login_model.__table__.create(db.engine, checkfirst=True)

        success = login_model.reset_admin_password(new_password, username=args.username)
        if success:
            print("✅ Admin password reset successfully.")
            return 0

    print("❌ Failed to reset admin password.")
    return 1


if __name__ == '__main__':
    raise SystemExit(main())