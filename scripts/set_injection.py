import sys

from sentinel.injection.control import (
    get_injection_states,
    is_injection_enabled,
    set_injection_enabled,
)


VALID_INJECTIONS = {
    "categorical",
    "missingness",
    "numeric",
    "volume",
    "schema",
}


def print_usage() -> None:
    raise SystemExit(
        "Usage:\n"
        "  python scripts/set_injection.py <injection> on\n"
        "  python scripts/set_injection.py <injection> off\n"
        "  python scripts/set_injection.py <injection> status\n"
        "  python scripts/set_injection.py status\n"
        "\n"
        "Available injections:\n"
        "  categorical\n"
        "  missingness\n"
        "  numeric\n"
        "  volume\n"
        "  schema"
    )


def print_all_statuses() -> None:
    states = get_injection_states()

    print("Sentinel injection states:")
    print()

    for injection in sorted(VALID_INJECTIONS):
        enabled = states.get(
            injection,
            False,
        )

        print(
            f"{injection:<12} "
            f"{'ON' if enabled else 'OFF'}"
        )


def main() -> None:

    # Show all injection states.
    if len(sys.argv) == 2:
        command = sys.argv[1].lower()

        if command == "status":
            print_all_statuses()
            return

        # Backwards compatibility:
        #
        # python scripts/set_injection.py on
        # python scripts/set_injection.py off
        #
        # still controls categorical injection.
        if command in {"on", "off"}:
            enabled = command == "on"

            set_injection_enabled(
                enabled,
                "categorical",
            )

            print(
                "Sentinel categorical injection: "
                + ("ON" if enabled else "OFF")
            )

            return

        print_usage()

    if len(sys.argv) != 3:
        print_usage()

    injection = sys.argv[1].lower()
    command = sys.argv[2].lower()

    if injection not in VALID_INJECTIONS:
        raise SystemExit(
            f"Unknown injection: {injection}\n"
            f"Expected one of: "
            f"{', '.join(sorted(VALID_INJECTIONS))}"
        )

    if command == "on":

        set_injection_enabled(
            True,
            injection,
        )

        print(
            f"Sentinel {injection} injection: ON"
        )

    elif command == "off":

        set_injection_enabled(
            False,
            injection,
        )

        print(
            f"Sentinel {injection} injection: OFF"
        )

    elif command == "status":

        enabled = is_injection_enabled(
            injection
        )

        print(
            f"Sentinel {injection} injection: "
            + ("ON" if enabled else "OFF")
        )

    else:
        print_usage()


if __name__ == "__main__":
    main()