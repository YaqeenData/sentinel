import sys

from sentinel.injection.control import (
    is_injection_enabled,
    set_injection_enabled,
)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage:\n"
            "  python scripts/set_injection.py on\n"
            "  python scripts/set_injection.py off\n"
            "  python scripts/set_injection.py status"
        )

    command = sys.argv[1].lower()

    if command == "on":
        set_injection_enabled(True)
        print("Sentinel controlled injection: ON")

    elif command == "off":
        set_injection_enabled(False)
        print("Sentinel controlled injection: OFF")

    elif command == "status":
        enabled = is_injection_enabled()

        print(
            "Sentinel controlled injection: "
            + ("ON" if enabled else "OFF")
        )

    else:
        raise SystemExit(
            "Expected: on, off, or status"
        )


if __name__ == "__main__":
    main()