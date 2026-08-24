"""Event transition helpers for Multi-NUT polling."""

from __future__ import annotations

import re
from dataclasses import dataclass
from os import environ
from threading import Lock
from typing import Dict, List, Optional


@dataclass
class _PowerState:
    """Last observed power state for one target."""

    on_battery: bool
    low_battery: bool
    replace_battery: bool
    forced_shutdown: bool


@dataclass
class _CommunicationState:
    """Consecutive polling failures and emitted outage state for one target."""

    consecutive_failures: int = 0
    comm_bad_emitted: bool = False
    nocomm_emitted: bool = False


_state_lock = Lock()
_target_states: Dict[int, _PowerState] = {}
_communication_states: Dict[int, _CommunicationState] = {}


def _positive_int_env(name: str, default: int) -> int:
    try:
        return max(1, int(environ.get(name, default)))
    except (TypeError, ValueError):
        return default


COMM_BAD_FAILURE_THRESHOLD = _positive_int_env('NUTIFY_COMM_BAD_FAILURE_THRESHOLD', 2)
NOCOMM_FAILURE_THRESHOLD = max(
    COMM_BAD_FAILURE_THRESHOLD + 1,
    _positive_int_env('NUTIFY_NOCOMM_FAILURE_THRESHOLD', 3),
)


def _safe_float(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_status_tokens(status_value: object) -> set[str]:
    normalized = str(status_value or '').upper().strip()
    if not normalized:
        return set()
    return {token for token in re.split(r'[^A-Z0-9]+', normalized) if token}


def _derive_power_state(metrics: Dict[str, object]) -> Optional[_PowerState]:
    tokens = _parse_status_tokens(metrics.get('ups_status'))

    on_battery = bool({'OB', 'ONBATT'} & tokens)
    online = bool({'OL', 'ONLINE'} & tokens)
    low_battery = bool({'LB', 'LOWBATT'} & tokens)
    replace_battery = bool({'RB', 'REPLBATT'} & tokens)
    forced_shutdown = bool({'FSD', 'SHUTDOWN'} & tokens)

    battery_charge = _safe_float(metrics.get('battery_charge'))
    battery_charge_low = _safe_float(metrics.get('battery_charge_low'))
    if (
        on_battery
        and battery_charge is not None
        and battery_charge_low is not None
        and battery_charge <= battery_charge_low
    ):
        low_battery = True

    if not tokens and battery_charge is None and battery_charge_low is None:
        return None

    if not on_battery and not online and tokens:
        # Unknown/other status token (for example CHRG): do not infer power transition.
        return None

    return _PowerState(
        on_battery=on_battery,
        low_battery=low_battery,
        replace_battery=replace_battery,
        forced_shutdown=forced_shutdown,
    )


def collect_poll_success_events(target_id: int) -> List[str]:
    """Clear polling outage state and emit COMMOK only after confirmed COMMBAD."""
    with _state_lock:
        state = _communication_states.pop(int(target_id), None)
        if state is None:
            return []
        return ['COMMOK'] if state.comm_bad_emitted else []


def collect_poll_failure_events(target_id: int) -> List[str]:
    """Debounce transient failures and emit each communication event once."""
    target_id_int = int(target_id)
    events: List[str] = []
    with _state_lock:
        state = _communication_states.get(target_id_int)
        if state is None:
            state = _CommunicationState()
            _communication_states[target_id_int] = state

        state.consecutive_failures += 1
        if (
            state.consecutive_failures >= COMM_BAD_FAILURE_THRESHOLD
            and not state.comm_bad_emitted
        ):
            state.comm_bad_emitted = True
            events.append('COMMBAD')
        if (
            state.consecutive_failures >= NOCOMM_FAILURE_THRESHOLD
            and not state.nocomm_emitted
        ):
            state.nocomm_emitted = True
            events.append('NOCOMM')
    return events


def collect_power_transition_events(target_id: int, metrics: Dict[str, object]) -> List[str]:
    """
    Compute ONBATT/ONLINE/LOWBATT transitions from current metrics.

    The first valid sample seeds state only; events are emitted on transitions.
    """
    derived_state = _derive_power_state(metrics or {})
    if derived_state is None:
        return []

    target_id_int = int(target_id)
    events: List[str] = []

    with _state_lock:
        previous = _target_states.get(target_id_int)
        _target_states[target_id_int] = derived_state

    if previous is None:
        return []

    if not previous.on_battery and derived_state.on_battery:
        events.append('ONBATT')
    elif previous.on_battery and not derived_state.on_battery:
        events.append('ONLINE')

    if not previous.low_battery and derived_state.low_battery:
        events.append('LOWBATT')
    if not previous.replace_battery and derived_state.replace_battery:
        events.append('REPLBATT')
    if not previous.forced_shutdown and derived_state.forced_shutdown:
        events.append('SHUTDOWN')

    return events
