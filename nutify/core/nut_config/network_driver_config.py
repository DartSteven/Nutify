"""Network NUT driver endpoint normalization and validation."""

import re


NETWORK_DRIVER_MARKERS = ('snmp', 'netxml', 'ipmi')
LOCAL_SERVER_ENDPOINTS = {
    '0.0.0.0',
    '127.0.0.1',
    '::',
    '::1',
    '[::1]',
    'localhost',
}


def is_network_driver(driver_name):
    """Return whether a NUT driver expects a network endpoint in `port`."""
    normalized = str(driver_name or '').strip().lower()
    return any(marker in normalized for marker in NETWORK_DRIVER_MARKERS)


def is_missing_network_endpoint(value):
    """Return whether a network driver endpoint is absent or device-only `auto`."""
    return str(value or '').strip().lower() in {'', 'auto'}


def normalize_primary_network_endpoint(payload):
    """Migrate the legacy server-address value into a missing network-driver port."""
    normalized = dict(payload or {})
    driver = normalized.get('ups_driver')
    if not is_network_driver(driver):
        return normalized

    endpoint = normalized.get('ups_port')
    if not is_missing_network_endpoint(endpoint):
        return normalized

    legacy_endpoint = str(normalized.get('server_address') or '').strip()
    if legacy_endpoint.lower() not in LOCAL_SERVER_ENDPOINTS and legacy_endpoint:
        normalized['ups_port'] = legacy_endpoint
    return normalized


def validate_primary_network_endpoint(payload):
    """Validate the primary network driver's `port` endpoint."""
    driver = str((payload or {}).get('ups_driver') or '').strip()
    endpoint = (payload or {}).get('ups_port')
    if not is_network_driver(driver) or not is_missing_network_endpoint(endpoint):
        return []
    return [
        f"Network driver '{driver}' requires the UPS hostname or IP address in Port/Device; "
        "'auto' is valid only for local device drivers."
    ]


def _unquote(value):
    normalized = str(value or '').strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {'"', "'"}:
        return normalized[1:-1]
    return normalized


def parse_ups_conf_sections(content):
    """Parse section names plus driver/port values needed for endpoint validation."""
    sections = []
    current = None
    assignment_pattern = re.compile(r'^\s*([A-Za-z][A-Za-z0-9_.-]*)\s*=\s*(.*?)\s*$')

    for raw_line in str(content or '').splitlines():
        section_match = re.match(r'^\s*\[([^]]+)]\s*(?:#.*)?$', raw_line)
        if section_match:
            if current:
                sections.append(current)
            current = {'name': section_match.group(1).strip()}
            continue
        if current is None or raw_line.lstrip().startswith('#'):
            continue
        assignment_match = assignment_pattern.match(raw_line)
        if not assignment_match:
            continue
        key = assignment_match.group(1).strip().lower()
        if key in {'driver', 'port'}:
            current[key] = _unquote(assignment_match.group(2))

    if current:
        sections.append(current)
    return sections


def validate_ups_conf_network_endpoints(content):
    """Reject generated or edited network UPS sections with no usable endpoint."""
    errors = []
    for section in parse_ups_conf_sections(content):
        driver = str(section.get('driver') or '').strip()
        if not is_network_driver(driver) or not is_missing_network_endpoint(section.get('port')):
            continue
        errors.append(
            f"UPS '{section['name']}' uses network driver '{driver}' but Port/Device is "
            "'auto'. Enter the UPS hostname or IP address before testing."
        )
    return errors
