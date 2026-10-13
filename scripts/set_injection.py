import sys

from sentinel.injection.control import (
    KINDS,
    injection_status,
    set_injection_kind,
)


USAGE = (
    "Usage:\n"
    "  python scripts/set_injection.py on   [kind]\n"
    "  python scripts/set_injection.py off  [kind]\n"
    "  python scripts/set_injection.py status\n"
    "\n"
    f"kind: {', '.join(KINDS)} or all "
    "(default: categorical)"
)


def print_status() -> None:
    print("Sentinel controlled injection:")

    for kind, enabled in injection_status().items():
        print(
            f"  {kind:<12} "
            + ("ON" if enabled else "OFF")
        )


def main() -> None:
    args = [
        argument.lower()
        for argument in sys.argv[1:]
    ]

    if not args or len(args) > 2:
        raise SystemExit(USAGE)

    command = args[0]

    if command == "status":
        if len(args) != 1:
            raise SystemExit(USAGE)

        print_status()
        return

    if command not in ("on", "off"):
        raise SystemExit(USAGE)

    target = (
        args[1]
        if len(args) == 2
        else "categorical"
    )

    if target == "all":
        kinds = KINDS
    elif target in KINDS:
        kinds = (target,)
    else:
        raise SystemExit(
            f"Unknown kind {target!r}.\n\n{USAGE}"
        )

    for kind in kinds:
        set_injection_kind(
            kind,
            command == "on",
        )

    print_status()


if __name__ == "__main__":
    main()