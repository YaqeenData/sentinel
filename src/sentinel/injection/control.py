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


def set_injection_enabled(
    enabled: bool,
) -> None:
    """
    Persist the live failure-injection state.

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
            {
                "enabled": enabled,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    os.replace(
        temporary_file,
        STATE_FILE,
    )


def is_injection_enabled() -> bool:
    """
    Return the current live injection state.

    Injection defaults to OFF when no state file exists.
    """

    if not STATE_FILE.exists():
        return False

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
        return False

    return bool(
        state.get(
            "enabled",
            False,
        )
    )