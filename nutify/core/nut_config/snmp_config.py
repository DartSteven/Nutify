"""SNMP driver configuration normalization and rendering."""

import re


SNMP_VERSIONS = {'v1', 'v2c', 'v3'}
SNMP_SECURITY_LEVELS = {'noAuthNoPriv', 'authNoPriv', 'authPriv'}


def _value(payload, snake_name, nut_name=None, default=''):
    value = payload.get(snake_name)
    if value is None and nut_name:
        value = payload.get(nut_name)
    normalized = str(value or '').strip()
    return normalized or default


def normalize_snmp_settings(payload):
    """Return one canonical SNMP settings dictionary from API or NUT names."""
    source = payload if isinstance(payload, dict) else {}
    version = _value(source, 'snmp_version', default='v1').lower()
    security_level = _value(
        source, 'snmp_sec_level', 'secLevel', 'authPriv'
    )
    return {
        'snmp_version': version,
        'snmp_community': _value(source, 'snmp_community', 'community'),
        'snmp_sec_level': security_level,
        'snmp_sec_name': _value(source, 'snmp_sec_name', 'secName'),
        'snmp_auth_protocol': _value(
            source, 'snmp_auth_protocol', 'authProtocol', 'SHA'
        ),
        'snmp_auth_password': _value(
            source, 'snmp_auth_password', 'authPassword'
        ),
        'snmp_priv_protocol': _value(
            source, 'snmp_priv_protocol', 'privProtocol', 'AES'
        ),
        'snmp_priv_password': _value(
            source, 'snmp_priv_password', 'privPassword'
        ),
        'snmp_mibs': _value(source, 'snmp_mibs', 'mibs'),
    }


def validate_snmp_settings(settings):
    """Return user-facing validation errors for canonical SNMP settings."""
    values = normalize_snmp_settings(settings)
    version = values['snmp_version']
    if version not in SNMP_VERSIONS:
        return [f"Unsupported SNMP version '{version}'."]

    if version in {'v1', 'v2c'}:
        if not values['snmp_community']:
            return ['SNMP community is required for SNMP v1 and v2c.']
        return []

    level = values['snmp_sec_level']
    errors = []
    if level not in SNMP_SECURITY_LEVELS:
        errors.append(f"Unsupported SNMPv3 security level '{level}'.")
    if not values['snmp_sec_name']:
        errors.append('SNMPv3 security name is required.')
    if level in {'authNoPriv', 'authPriv'}:
        if not values['snmp_auth_protocol']:
            errors.append('SNMPv3 authentication protocol is required.')
        if not values['snmp_auth_password']:
            errors.append('SNMPv3 authentication password is required.')
    if level == 'authPriv':
        if not values['snmp_priv_protocol']:
            errors.append('SNMPv3 privacy protocol is required.')
        if not values['snmp_priv_password']:
            errors.append('SNMPv3 privacy password is required.')
    return errors


def quote_nut_value(value):
    """Quote one NUT configuration value without changing its content."""
    escaped = str(value or '').replace('\\', '\\\\').replace('"', '\\"')
    return f'"{escaped}"'


def render_snmp_lines(settings, indent='    '):
    """Render driver-specific ups.conf lines for SNMP v1, v2c, or v3."""
    values = normalize_snmp_settings(settings)
    lines = [f"{indent}snmp_version = {quote_nut_value(values['snmp_version'])}"]
    if values['snmp_version'] in {'v1', 'v2c'}:
        lines.append(
            f"{indent}community = {quote_nut_value(values['snmp_community'])}"
        )
    else:
        lines.extend([
            f"{indent}secLevel = {quote_nut_value(values['snmp_sec_level'])}",
            f"{indent}secName = {quote_nut_value(values['snmp_sec_name'])}",
        ])
        if values['snmp_sec_level'] in {'authNoPriv', 'authPriv'}:
            lines.extend([
                f"{indent}authProtocol = {quote_nut_value(values['snmp_auth_protocol'])}",
                f"{indent}authPassword = {quote_nut_value(values['snmp_auth_password'])}",
            ])
        if values['snmp_sec_level'] == 'authPriv':
            lines.extend([
                f"{indent}privProtocol = {quote_nut_value(values['snmp_priv_protocol'])}",
                f"{indent}privPassword = {quote_nut_value(values['snmp_priv_password'])}",
            ])
    if values['snmp_mibs']:
        lines.append(f"{indent}mibs = {quote_nut_value(values['snmp_mibs'])}")
    return lines


def append_missing_snmp_lines(ups_conf, settings):
    """Append missing SNMP fields to a generated single-target ups.conf."""
    content = str(ups_conf or '')
    if not content.strip():
        return content
    additions = []
    for line in render_snmp_lines(settings):
        key = line.strip().split('=', 1)[0].strip()
        if not re.search(
            rf'^\s*{re.escape(key)}\s*=', content, re.IGNORECASE | re.MULTILINE
        ):
            additions.append(line)
    if not additions:
        return content
    return content.rstrip() + '\n' + '\n'.join(additions) + '\n'
