"""Event transition helpers for Multi-NUT polling."""

from __future__ import annotations

import re
from dataclasses import dataclass
from threading import Lock
from typing import Dict, List, Optional


@dataclass
class _PowerState:
    """Last observed power state for one target."""

    on_battery: bool
    low_battery: bool
    replace_battery: bool
    forced_shutdown: bool
    nocomm_emitted: bool = False


_state_lock = Lock()
_target_states: Dict[int, _PowerState] = {}


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
    if battery_charge is not None and battery_charge_low is not None and battery_charge <= battery_charge_low:
        low_battery = True

    if low_battery:
        on_battery = True

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


def reset_target_power_state(target_id: int) -> None:
    """Forget cached state for one target (for example after communication loss)."""
    with _state_lock:
        _target_states.pop(int(target_id), None)


def register_poll_success(target_id: int) -> None:
    """Clear communication outage marker when polling is healthy again."""
    with _state_lock:
        state = _target_states.get(int(target_id))
        if state is None:
            return
        state.nocomm_emitted = False


def collect_poll_failure_events(target_id: int, had_previous_error: bool) -> List[str]:
    """Emit NOCOMM once per continuous outage after initial COMMBAD."""
    target_id_int = int(target_id)
    with _state_lock:
        state = _target_states.get(target_id_int)
        if state is None:
            state = _PowerState(
                on_battery=False,
                low_battery=False,
                replace_battery=False,
                forced_shutdown=False,
            )
            _target_states[target_id_int] = state

        if not had_previous_error:
            state.nocomm_emitted = False
            return []

        if state.nocomm_emitted:
            return []
        state.nocomm_emitted = True
        return ['NOCOMM']


def collect_power_transition_events(target_id: int, metrics: Dict[str, object]) -> List[str]:
    """
    Compute ONBATT/ONLINE/LOWBATT transitions from current metrics.

    The first valid sample does not emit ONLINE by design to avoid startup noise.
    """
    derived_state = _derive_power_state(metrics or {})
    if derived_state is None:
        return []

    target_id_int = int(target_id)
    events: List[str] = []

    with _state_lock:
        previous = _target_states.get(target_id_int)
        nocomm_emitted = bool(previous.nocomm_emitted) if previous else False
        derived_state.nocomm_emitted = nocomm_emitted
        _target_states[target_id_int] = derived_state

    if previous is None:
        if derived_state.on_battery:
            events.append('ONBATT')
        if derived_state.low_battery:
            events.append('LOWBATT')
        if derived_state.replace_battery:
            events.append('REPLBATT')
        if derived_state.forced_shutdown:
            events.append('SHUTDOWN')
        return events

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
