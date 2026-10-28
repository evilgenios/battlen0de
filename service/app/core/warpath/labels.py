"""Human-readable labels for raw protocol state codes — ported verbatim
from the latest Discord bot (message (1).py). Anything not in these maps
falls back to showing the raw numeric code rather than guessing a label
for a state this project has no confirmed mapping for."""

from __future__ import annotations

VEHICLE_STATE_NAMES = {
    1: 'Idle',
    2: 'Traveling to resource',
    3: 'Gathering',
    4: 'Returning',
    5: 'Destroyed',
    6: 'Repairing',
    7: 'Building',
    8: 'Demolishing',
    9: 'Gathering super mine',
    10: 'Delivering resources',
}

# Vehicle states the official client's "return all" action recalls.
RECALLABLE_VEHICLE_STATES = {2, 3, 9}


def vehicle_state_label(state: int) -> str:
    return VEHICLE_STATE_NAMES.get(state, f'State {state}')


def base_state_label(snapshot: dict) -> str:
    if snapshot.get('base_is_destroyed'):
        return 'Destroyed'
    if snapshot.get('base_is_car'):
        return 'Airlifted - needs rebuilding'
    return 'Deployed'
