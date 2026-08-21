"""Integration tests for the OIDC callback with a mocked provider.

These tests replace the Authlib client with a fake so the full token-exchange
and claim-resolution path runs without contacting a real identity provider.
"""

from __future__ import annotations

import pytest


class _FakeClient:
    """Stand-in for an Authlib OAuth client."""

    def __init__(self, token=None, userinfo=None, raise_on_token=False):
        self._token = token or {}
        self._userinfo = userinfo
        self._raise_on_token = raise_on_token

    def authorize_access_token(self):
        if self._raise_on_token:
            raise RuntimeError('state mismatch')
        return self._token

    def userinfo(self, token=None):
        if self._userinfo is None:
            raise RuntimeError('userinfo endpoint disabled')
        return self._userinfo


class _FakeOAuth:
    def __init__(self, client):
        self._client = client

    def create_client(self, name):
        return self._client


@pytest.fixture
def mock_provider(oidc, oidc_env, monkeypatch):
    """Install a fake provider client and return a configuration helper."""

    def _install(token=None, userinfo=None, raise_on_token=False):
        client = _FakeClient(token=token, userinfo=userinfo, raise_on_token=raise_on_token)
        monkeypatch.setattr(oidc, '_oauth', _FakeOAuth(client))
        monkeypatch.setattr(oidc, '_registered', True)
        return client

    return _install


def test_callback_resolves_admin_identity(oidc, mock_provider):
    mock_provider(token={'userinfo': {'preferred_username': 'alice', 'groups': ['nutify-admins']}})
    identity = oidc.complete_login()
    assert identity['username'] == 'alice'
    assert identity['role'] == 'administrator'
    assert identity['groups'] == ['nutify-admins']


def test_callback_resolves_regular_user(oidc, mock_provider):
    mock_provider(token={'userinfo': {'preferred_username': 'bob', 'groups': ['staff']}})
    identity = oidc.complete_login()
    assert identity['username'] == 'bob'
    assert identity['role'] == 'user'


def test_callback_enriches_groups_from_userinfo_endpoint(oidc, mock_provider):
    # id_token lacks groups; the userinfo endpoint supplies them.
    mock_provider(
        token={'userinfo': {'preferred_username': 'carol'}},
        userinfo={'groups': ['nutify-admins']},
    )
    identity = oidc.complete_login()
    assert identity['role'] == 'administrator'


def test_callback_missing_username_raises(oidc, mock_provider):
    mock_provider(token={'userinfo': {'groups': ['staff']}}, userinfo={})
    with pytest.raises(oidc.OidcError):
        oidc.complete_login()


def test_callback_rejects_user_outside_authorized_groups(oidc, oidc_env, mock_provider):
    # Gating on: a configured user group means non-members are rejected.
    oidc_env.setenv('OIDC_USER_GROUP', 'nutify-users')
    mock_provider(token={'userinfo': {'preferred_username': 'mallory', 'groups': ['strangers']}})
    with pytest.raises(oidc.OidcError):
        oidc.complete_login()


def test_callback_allows_user_group_member_when_gating(oidc, oidc_env, mock_provider):
    oidc_env.setenv('OIDC_USER_GROUP', 'nutify-users')
    mock_provider(token={'userinfo': {'preferred_username': 'dave', 'groups': ['nutify-users']}})
    identity = oidc.complete_login()
    assert identity['username'] == 'dave'
    assert identity['role'] == 'user'


def test_callback_token_exchange_failure_raises(oidc, mock_provider):
    mock_provider(raise_on_token=True)
    with pytest.raises(oidc.OidcError):
        oidc.complete_login()


def test_complete_login_disabled_raises(oidc, oidc_env, monkeypatch):
    monkeypatch.delenv('OIDC_ENABLED', raising=False)
    with pytest.raises(oidc.OidcError):
        oidc.complete_login()
