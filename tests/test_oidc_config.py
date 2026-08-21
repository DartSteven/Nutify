"""Unit tests for OIDC configuration, enablement and claim parsing."""

from __future__ import annotations


def test_disabled_without_enabled_flag(oidc, oidc_env):
    oidc_env.delenv('OIDC_ENABLED', raising=False)
    assert oidc.is_oidc_enabled() is False


def test_disabled_when_config_incomplete(oidc, oidc_env):
    oidc_env.delenv('OIDC_CLIENT_SECRET', raising=False)
    assert oidc.is_oidc_configured() is False
    assert oidc.is_oidc_enabled() is False


def test_enabled_with_full_config(oidc, oidc_env):
    assert oidc.is_oidc_configured() is True
    assert oidc.is_oidc_enabled() is True


def test_public_config_hides_secrets(oidc, oidc_env):
    oidc_env.setenv('OIDC_PROVIDER_NAME', 'Authentik')
    config = oidc.get_public_config()
    assert config['enabled'] is True
    assert config['login_url'] == '/auth/oidc/login'
    assert config['button_label'] == 'Sign in with Authentik'
    serialized = str(config)
    assert 'secret' not in serialized
    assert 'sso.example.com' not in serialized


def test_public_config_custom_button_label(oidc, oidc_env):
    oidc_env.setenv('OIDC_BUTTON_LABEL', 'Company Login')
    assert oidc.get_public_config()['button_label'] == 'Company Login'


def test_scopes_always_include_openid(oidc, oidc_env):
    oidc_env.setenv('OIDC_SCOPES', 'profile email')
    assert oidc._get_scopes().split()[0] == 'openid'


def test_scopes_default(oidc, oidc_env):
    assert oidc._get_scopes() == 'openid profile email groups'


def test_extract_username_priority(oidc, oidc_env):
    claims = {'preferred_username': 'alice', 'email': 'alice@example.com', 'sub': 'uuid'}
    assert oidc._extract_username(claims) == 'alice'


def test_extract_username_falls_back_to_email(oidc, oidc_env):
    claims = {'email': 'bob@example.com', 'sub': 'uuid'}
    assert oidc._extract_username(claims) == 'bob@example.com'


def test_extract_username_falls_back_to_sub(oidc, oidc_env):
    assert oidc._extract_username({'sub': 'uuid-123'}) == 'uuid-123'


def test_extract_username_empty_when_missing(oidc, oidc_env):
    assert oidc._extract_username({'name': 'No Id'}) == ''


def test_extract_username_custom_claim(oidc, oidc_env):
    oidc_env.setenv('OIDC_USERNAME_CLAIM', 'nickname')
    assert oidc._extract_username({'nickname': 'ace', 'sub': 'x'}) == 'ace'


def test_extract_groups_from_list(oidc, oidc_env):
    assert oidc._extract_groups({'groups': ['a', 'b']}) == ['a', 'b']


def test_extract_groups_from_string(oidc, oidc_env):
    assert oidc._extract_groups({'groups': 'a, b c'}) == ['a', 'b', 'c']


def test_extract_groups_missing(oidc, oidc_env):
    assert oidc._extract_groups({}) == []


def test_extract_groups_custom_claim(oidc, oidc_env):
    oidc_env.setenv('OIDC_GROUPS_CLAIM', 'roles')
    assert oidc._extract_groups({'roles': ['admin']}) == ['admin']
