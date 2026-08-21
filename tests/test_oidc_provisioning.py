"""Integration tests for SSO user provisioning and login."""

from __future__ import annotations


def test_creates_new_sso_user(db_session):
    LoginAuth = db_session.LoginAuth
    with db_session.app.app_context():
        user = LoginAuth.get_or_create_oidc_user('alice', 'user')
        assert user.id is not None
        assert user.username == 'alice'
        assert user.role == 'user'
        assert user.is_admin is False
        assert user.is_active is True


def test_sso_user_has_unusable_local_password(db_session):
    LoginAuth = db_session.LoginAuth
    with db_session.app.app_context():
        user = LoginAuth.get_or_create_oidc_user('alice', 'user')
        assert user.check_password('') is False
        assert user.check_password('anything') is False
        assert user.password_hash.startswith('!')


def test_admin_group_provisions_administrator(db_session):
    LoginAuth = db_session.LoginAuth
    with db_session.app.app_context():
        user = LoginAuth.get_or_create_oidc_user('boss', 'administrator')
        assert user.role == 'administrator'
        assert user.is_admin is True


def test_second_login_updates_role(db_session):
    LoginAuth = db_session.LoginAuth
    with db_session.app.app_context():
        # The primary admin (id 1) is always created locally via setup first.
        LoginAuth.create_user('admin', 'localpass', role='administrator', is_admin=True)

        user = LoginAuth.get_or_create_oidc_user('carol', 'user')
        user_id = user.id
        assert user_id != 1
        assert user.role == 'user'

        promoted = LoginAuth.get_or_create_oidc_user('carol', 'administrator')
        assert promoted.id == user_id  # same account, not a duplicate
        assert promoted.role == 'administrator'
        assert promoted.is_admin is True

        # A later login without the admin group demotes again.
        demoted = LoginAuth.get_or_create_oidc_user('carol', 'user')
        assert demoted.id == user_id
        assert demoted.role == 'user'
        assert demoted.is_admin is False


def test_second_login_does_not_duplicate(db_session):
    LoginAuth = db_session.LoginAuth
    with db_session.app.app_context():
        LoginAuth.get_or_create_oidc_user('dave', 'user')
        LoginAuth.get_or_create_oidc_user('dave', 'user')
        assert LoginAuth.query.filter_by(username='dave').count() == 1


def test_primary_admin_is_never_demoted(db_session):
    """The local admin fallback (id 1) must survive an SSO login collision."""
    LoginAuth = db_session.LoginAuth
    with db_session.app.app_context():
        admin = LoginAuth.create_user('admin', 'localpass', role='administrator', is_admin=True)
        assert admin.id == 1

        # An SSO login for the same username must not strip admin rights.
        same = LoginAuth.get_or_create_oidc_user('admin', 'user')
        assert same.id == 1
        assert same.role == 'administrator'
        assert same.is_admin is True
        # Local password login for the fallback admin still works.
        assert same.check_password('localpass') is True


def test_reactivates_disabled_user(db_session):
    LoginAuth = db_session.LoginAuth
    with db_session.app.app_context():
        LoginAuth.create_user('admin', 'localpass', role='administrator', is_admin=True)

        user = LoginAuth.get_or_create_oidc_user('erin', 'user')
        user.is_active = False
        db_session.db.session.commit()

        reactivated = LoginAuth.get_or_create_oidc_user('erin', 'user')
        assert reactivated.is_active is True


def test_login_oidc_user_establishes_session(db_session):
    auth = db_session.auth
    with db_session.app.test_request_context():
        user = auth.login_oidc_user('frank', 'administrator')
        assert user is not None
        assert auth.is_authenticated() is True
        current = auth.get_current_user()
        assert current['username'] == 'frank'
        assert current['role'] == 'administrator'
