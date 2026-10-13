import json
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]

STATE_FILE = (
    PROJECT_ROOT
    / "data"
    / "replay"
    / "injection_state.json"
)

# Live failure kinds that can be switched on and off separately.
# "categorical" keeps the original "enabled" key so older code
# and existing state files keep working.
KINDS = (
    "categorical",
    "nulls",
    "volume",
    "numeric",
    "contract",
    "patient",
    "encounter",
    "encounter_contract",
)

_STATE_KEYS = {
    "categorical": "enabled",
    "nulls": "nulls",
    "volume": "volume",
    "numeric": "numeric",
    "contract": "contract",
    "patient": "patient",
    "encounter": "encounter",
    "encounter_contract": "encounter_contract",
}


def _read_state() -> dict:
    """
    Read the state file.

    A missing or unreadable file means every injection is OFF.
    """

    if not STATE_FILE.exists():
        return {}

    try:
        state = json.loads(
            STATE_FILE.read_text(
                encoding="utf-8"
            )
        )
    except (
        json.JSONDecodeError,
        OSError,
    ):
        return {}

    return state if isinstance(state, dict) else {}


def _write_state(
    state: dict,
) -> None:
    """
    Persist the state atomically.

    The state is stored in a small JSON file so an already-running
    replay process can detect changes without being restarted.
    """

    STATE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_file = STATE_FILE.with_suffix(
        ".tmp"
    )

    temporary_file.write_text(
        json.dumps(
            state,
            indent=2,
        ),
        encoding="utf-8",
    )

    os.replace(
        temporary_file,
        STATE_FILE,
    )


def _check_kind(
    kind: str,
) -> None:
    if kind not in KINDS:
        raise ValueError(
            f"Unknown injection kind {kind!r}. "
            f"Expected one of: {', '.join(KINDS)}."
        )


def set_injection_kind(
    kind: str,
    enabled: bool,
) -> None:
    """Switch one injection kind on or off, keeping the others."""

    _check_kind(kind)

    state = _read_state()
    state[_STATE_KEYS[kind]] = bool(enabled)

    _write_state(state)


def is_kind_enabled(
    kind: str,
) -> bool:
    """Return whether one injection kind is currently ON."""

    _check_kind(kind)

    return bool(
        _read_state().get(
            _STATE_KEYS[kind],
            False,
        )
    )


def injection_status() -> dict[str, bool]:
    """Every kind and whether it is ON, read in one go."""

    state = _read_state()

    return {
        kind: bool(
            state.get(
                _STATE_KEYS[kind],
                False,
            )
        )
        for kind in KINDS
    }


def set_injection_enabled(
    enabled: bool,
) -> None:
    """
    Persist the live categorical injection state.

    Kept for the existing replay code; same as
    set_injection_kind("categorical", enabled).
    """

    set_injection_kind(
        "categorical",
        enabled,
    )


def is_injection_enabled() -> bool:
    """
    Return the current live categorical injection state.

    Injection defaults to OFF when no state file exists.
    """

    return is_kind_enabled(
        "categorical"
    )