"""Shared fixtures for the OIDC SSO test suite.

The Nutify runtime package (``core.db.ups``) pulls a heavy dependency chain
(flask-socketio, pandas, eventlet, ...). These tests only exercise the
authentication logic, so we load the relevant source files standalone via
``importlib`` and inject a lightweight fake ``core.db.ups`` module that exposes
the in-memory test database. This keeps the suite fast and free of the full
application stack while still running the real production code paths.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

NUTIFY_DIR = Path(__file__).resolve().parents[1] / 'nutify'


def _load_source(module_name: str, relative_path: str):
    """Load a single source file as a standalone module."""
    source_path = NUTIFY_DIR / relative_path
    spec = importlib.util.spec_from_file_location(module_name, source_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='session')
def oidc():
    """The OIDC module under test, loaded without the heavy app stack."""
    return _load_source('nutify_oidc_under_test', 'core/auth/oidc.py')


@pytest.fixture(scope='session')
def auth_stack():
    """Flask app, in-memory DB, LoginAuth model and auth module wired together."""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db = SQLAlchemy(app)

    # Inject a lightweight fake package chain so the model's lazy
    # ``from core.db.ups import db`` resolves to our test database.
    injected = {}
    core_mod = types.ModuleType('core')
    core_mod.__path__ = []
    core_db_mod = types.ModuleType('core.db')
    core_db_mod.__path__ = []
    core_db_ups_mod = types.ModuleType('core.db.ups')
    core_db_ups_mod.db = db
    core_mod.db = core_db_mod
    core_db_mod.ups = core_db_ups_mod
    for name, module in (
        ('core', core_mod),
        ('core.db', core_db_mod),
        ('core.db.ups', core_db_ups_mod),
    ):
        injected[name] = sys.modules.get(name)
        sys.modules[name] = module

    orm = _load_source('nutify_orm_login_under_test', 'core/db/orm/orm_ups_login.py')
    auth = _load_source('nutify_auth_under_test', 'core/auth/__init__.py')

    login_model = orm.init_model(db.Model)
    auth.init_auth_module(login_model)
    auth.setup_session_config(app)

    with app.app_context():
        db.create_all()

    yield types.SimpleNamespace(app=app, db=db, LoginAuth=login_model, auth=auth)

    # Restore any modules we replaced.
    for name, original in injected.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


@pytest.fixture
def db_session(auth_stack):
    """Provide a clean database for each test and roll back afterwards."""
    with auth_stack.app.app_context():
        auth_stack.db.session.query(auth_stack.LoginAuth).delete()
        auth_stack.db.session.commit()
        yield auth_stack
        auth_stack.db.session.rollback()


@pytest.fixture
def oidc_env(monkeypatch):
    """Apply a baseline valid OIDC configuration; tests tweak as needed."""
    env = {
        'OIDC_ENABLED': 'true',
        'OIDC_ISSUER': 'https://sso.example.com',
        'OIDC_CLIENT_ID': 'nutify',
        'OIDC_CLIENT_SECRET': 'secret',
        'OIDC_ADMIN_GROUP': 'nutify-admins',
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    # Clear optional overrides so defaults are exercised.
    for key in (
        'OIDC_SCOPES',
        'OIDC_USERNAME_CLAIM',
        'OIDC_GROUPS_CLAIM',
        'OIDC_USER_GROUP',
        'OIDC_PROVIDER_NAME',
        'OIDC_BUTTON_LABEL',
        'OIDC_REDIRECT_URI',
    ):
        monkeypatch.delenv(key, raising=False)
    return monkeypatch
