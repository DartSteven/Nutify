"""Connection helpers for Multi-NUT targets."""

from __future__ import annotations

import subprocess
import time
from typing import Dict, Tuple

from core.db.ups.utils import calculate_realpower
from core.logger import system_logger as logger
from core.settings import UPSC_BIN
from core.upsc_readiness import (
    contains_stale_marker,
    evaluate_upsc_readiness,
    is_transient_readiness_error,
    parse_upsc_output as parse_shared_upsc_output,
)

from .renamer import canonicalize_payload


def _safe_float(value):
    """Convert value to float when possible."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def _contains_stale_marker(text: str | None) -> bool:
    return contains_stale_marker(text)


def build_target_identifier(ups_name: str, host: str, port: int | None = None) -> str:
    """Build NUT target spec used by upsc."""
    normalized_host = str(host or '').strip()
    if not normalized_host:
        return str(ups_name or '').strip()
    normalized_port = 3493 if port in (None, 0) else int(port)
    if normalized_port == 3493:
        return f"{ups_name}@{normalized_host}"
    return f"{ups_name}@{normalized_host}:{normalized_port}"


def parse_upsc_output(raw_stdout: str) -> Dict[str, str]:
    """Parse raw upsc output into dict with dot-separated keys."""
    return parse_shared_upsc_output(raw_stdout)


def normalize_metrics(raw_payload: Dict[str, str], target_id: int | None = None) -> Dict[str, object]:
    """Normalize raw NUT payload to canonical DB-compatible keys."""
    canonical_payload = canonicalize_payload(
        raw_payload=raw_payload,
        target_id=target_id,
        include_auto_suggestion=True,
    )
    # Ensure all scalar values are normalized even when injected by mappings.
    return {key: _safe_float(value) for key, value in canonical_payload.items()}


def run_upsc_command(
    ups_name: str,
    host: str,
    port: int | None = None,
    command_path: str | None = None,
    timeout: int = 10,
    target_id: int | None = None,
) -> Tuple[bool, Dict[str, str], str]:
    """Run upsc and return parsed payload."""
    cmd = command_path or UPSC_BIN
    primary_target = build_target_identifier(ups_name, host, port)

    def execute_once(target_identifier: str) -> Tuple[bool, Dict[str, str], str]:
        try:
            result = subprocess.run(
                [cmd, target_identifier],
                capture_output=True,
                text=True,
                timeout=max(1, int(timeout)),
            )
        except subprocess.TimeoutExpired:
            return False, {}, f"Command timed out after {timeout} seconds ({cmd} {target_identifier})"
        except Exception as exc:
            logger.error(f"Error running upsc for target {target_identifier}: {exc}")
            return False, {}, f"{exc} ({cmd} {target_identifier})"

        if result.returncode != 0:
            error = result.stderr.strip() or f"upsc exited with {result.returncode}"
            return False, {}, f"{error} ({cmd} {target_identifier})"

        stderr_message = (result.stderr or '').strip()
        if _contains_stale_marker(stderr_message):
            return False, {}, f"{stderr_message} ({cmd} {target_identifier})"

        payload = parse_upsc_output(result.stdout)
        if not payload:
            return False, {}, f"upsc returned empty payload ({cmd} {target_identifier})"

        for key_name in ('driver.state', 'driver.status', 'ups.status'):
            if _contains_stale_marker(payload.get(key_name)):
                return False, {}, f"upsc returned stale state on {key_name} ({cmd} {target_identifier})"

        ready, readiness_error = evaluate_upsc_readiness(payload)
        if not ready:
            return False, {}, f"{readiness_error} ({cmd} {target_identifier})"

        payload = calculate_realpower(payload, target_id=target_id)
        return True, payload, ""

    success, payload, error = execute_once(primary_target)
    if success:
        return True, payload, ""

    normalized_host = str(host or '').strip().lower()
    local_hosts = {'127.0.0.1', 'localhost'}
    if normalized_host not in local_hosts:
        return False, {}, error

    fallback_targets = []
    if normalized_host == '127.0.0.1':
        fallback_targets.append(build_target_identifier(ups_name, 'localhost', port))
    elif normalized_host == 'localhost':
        fallback_targets.append(build_target_identifier(ups_name, '127.0.0.1', port))
    fallback_targets.append(build_target_identifier(ups_name, '', port))

    seen = {primary_target}
    fallback_errors = [error]
    for fallback_target in fallback_targets:
        if not fallback_target or fallback_target in seen:
            continue
        seen.add(fallback_target)
        success, payload, fallback_error = execute_once(fallback_target)
        if success:
            return True, payload, ""
        fallback_errors.append(fallback_error)

    return False, {}, " | ".join(item for item in fallback_errors if item)


def test_target_connection(payload: Dict[str, object]) -> Dict[str, object]:
    """Validate target payload and test live upsc connection."""
    ups_name = str(payload.get('ups_name', '')).strip()
    host = str(payload.get('host', '')).strip()
    port = int(payload.get('port') or 3493)
    timeout = int(payload.get('timeout') or 10)
    readiness_timeout = max(float(payload.get('readiness_timeout') or 0), 0.0)
    readiness_interval = max(float(payload.get('readiness_interval') or 1), 0.0)
    command_path = str(payload.get('command_path') or UPSC_BIN).strip()

    if not ups_name or not host:
        return {
            'success': False,
            'message': 'ups_name and host are required',
            'metrics': {},
        }

    deadline = time.monotonic() + readiness_timeout
    while True:
        success, raw_payload, error = run_upsc_command(
            ups_name=ups_name,
            host=host,
            port=port,
            command_path=command_path,
            timeout=timeout,
            target_id=payload.get('target_id'),
        )
        if success or not is_transient_readiness_error(error) or time.monotonic() >= deadline:
            break
        time.sleep(readiness_interval)

    if not success:
        return {
            'success': False,
            'message': error,
            'metrics': {},
        }

    normalized = normalize_metrics(raw_payload)
    return {
        'success': True,
        'message': 'Connection successful',
        'metrics': {
            'ups_status': normalized.get('ups_status'),
            'battery_charge': normalized.get('battery_charge'),
            'ups_load': normalized.get('ups_load'),
            'ups_realpower': normalized.get('ups_realpower'),
            'input_voltage': normalized.get('input_voltage'),
            'device_model': normalized.get('device_model'),
        },
        'raw': raw_payload,
    }
