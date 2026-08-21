"""Unit tests for the group -> role mapping."""

from __future__ import annotations


def test_admin_group_maps_to_administrator(oidc, oidc_env):
    assert oidc.resolve_role(['nutify-admins']) == 'administrator'


def test_admin_group_is_case_insensitive(oidc, oidc_env):
    assert oidc.resolve_role(['Nutify-Admins']) == 'administrator'


def test_non_admin_maps_to_user_when_no_user_group(oidc, oidc_env):
    # No OIDC_USER_GROUP configured: everyone who is not an admin is a user.
    assert oidc.resolve_role(['some-team']) == 'user'


def test_no_groups_maps_to_user_when_no_user_group(oidc, oidc_env):
    assert oidc.resolve_role([]) == 'user'


def test_multiple_admin_groups(oidc, oidc_env):
    oidc_env.setenv('OIDC_ADMIN_GROUP', 'ops, nutify-admins , infra')
    assert oidc.resolve_role(['infra']) == 'administrator'


def test_no_admin_group_configured(oidc, oidc_env):
    oidc_env.delenv('OIDC_ADMIN_GROUP', raising=False)
    assert oidc.resolve_role(['anything']) == 'user'


def test_user_group_member_maps_to_user(oidc, oidc_env):
    oidc_env.setenv('OIDC_USER_GROUP', 'nutify-users')
    assert oidc.resolve_role(['nutify-users']) == 'user'


def test_user_group_is_case_insensitive(oidc, oidc_env):
    oidc_env.setenv('OIDC_USER_GROUP', 'nutify-users')
    assert oidc.resolve_role(['Nutify-Users']) == 'user'


def test_multiple_user_groups(oidc, oidc_env):
    oidc_env.setenv('OIDC_USER_GROUP', 'staff, nutify-users , guests')
    assert oidc.resolve_role(['guests']) == 'user'


def test_gating_rejects_member_of_no_group(oidc, oidc_env):
    # With a user group configured, a user in neither group is rejected.
    oidc_env.setenv('OIDC_USER_GROUP', 'nutify-users')
    assert oidc.resolve_role(['some-other-team']) is None


def test_gating_rejects_when_user_has_no_groups(oidc, oidc_env):
    oidc_env.setenv('OIDC_USER_GROUP', 'nutify-users')
    assert oidc.resolve_role([]) is None


def test_admin_wins_over_user_group(oidc, oidc_env):
    oidc_env.setenv('OIDC_USER_GROUP', 'nutify-users')
    assert oidc.resolve_role(['nutify-admins', 'nutify-users']) == 'administrator'


def test_admin_allowed_even_when_gating_active(oidc, oidc_env):
    # Admin membership grants access regardless of user-group gating.
    oidc_env.setenv('OIDC_USER_GROUP', 'nutify-users')
    assert oidc.resolve_role(['nutify-admins']) == 'administrator'
