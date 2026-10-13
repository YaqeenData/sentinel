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


DEFAULT_INJECTION = "categorical"


def _read_state() -> dict[str, bool]:
    """
    Read all injection states.

    If no state file exists, return an empty state.
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

    # Backwards compatibility with the old format:
    #
    # {
    #     "enabled": true
    # }
    #
    if "enabled" in state:
        return {
            DEFAULT_INJECTION: bool(
                state["enabled"]
            )
        }

    return {
        str(name): bool(enabled)
        for name, enabled in state.items()
    }


def _write_state(
    state: dict[str, bool],
) -> None:
    """
    Persist all injection states atomically.
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
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    os.replace(
        temporary_file,
        STATE_FILE,
    )


def set_injection_enabled(
    enabled: bool,
    injection: str = DEFAULT_INJECTION,
) -> None:
    """
    Enable or disable one named injection.
    """

    state = _read_state()

    state[injection] = enabled

    _write_state(state)


def is_injection_enabled(
    injection: str = DEFAULT_INJECTION,
) -> bool:
    """
    Return whether one named injection is enabled.

    Defaults to categorical injection so existing
    replay code continues working unchanged.
    """

    state = _read_state()

    return state.get(
        injection,
        False,
    )


def get_injection_states() -> dict[str, bool]:
    """
    Return all configured injection states.
    """

    return _read_state()