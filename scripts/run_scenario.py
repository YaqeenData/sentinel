"""
Run a timed failure scenario against the live replay.

The script only flips the injection switches (the same ones as
scripts/set_injection.py). The replay applies the failures and the
monitor detects them, so all three run side by side:

    Terminal 1: python scripts/run_monitor.py
    Terminal 2: python -m sentinel.streaming.replay
    Terminal 3: python scripts/run_scenario.py

Each kind runs on its own, so every incident has one clear cause:

    healthy warm-up → volume ON → OFF → nulls ON → OFF
                    → numeric ON → OFF → contract ON → OFF
                    → patient ON → OFF → encounter ON → OFF
                    → encounter_contract ON → OFF
"""

import argparse
import time
from datetime import datetime

from sentinel.injection.control import (
    injection_status,
    set_injection_kind,
)


# Kinds handled by the live replay (injection/live_failures.py),
# in the order they are run. "patient" breaks the Patient contract,
# "encounter" moves part of the AMB Encounters to EMER (class drift),
# "encounter_contract" breaks the Encounter contract.
SCENARIO_KINDS = (
    "volume",
    "nulls",
    "numeric",
    "contract",
    "patient",
    "encounter",
    "encounter_contract",
)


def now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def wait(
    minutes: float,
    label: str,
) -> None:
    """Sleep while printing a countdown once a minute."""

    remaining = int(minutes * 60)

    while remaining > 0:
        print(
            f"\r[{now()}] {label} | "
            f"{remaining // 60:02d}:{remaining % 60:02d} left ",
            end="",
            flush=True,
        )

        step = min(60, remaining)
        time.sleep(step)
        remaining -= step

    print()


def switch(
    kind: str,
    enabled: bool,
) -> None:
    set_injection_kind(kind, enabled)

    print(
        f"[{now()}] {kind.upper()} injection "
        + ("ON  🔥" if enabled else "OFF ✅")
    )


def all_off(
    kinds: tuple[str, ...],
) -> None:
    for kind in kinds:
        set_injection_kind(kind, False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Timed live failure scenario for Sentinel.",
    )

    parser.add_argument(
        "--warmup",
        type=float,
        default=25.0,
        help=(
            "Healthy minutes before the first failure. Long enough "
            "for the numeric reference (100 patients) to freeze. "
            "Default: 25."
        ),
    )

    parser.add_argument(
        "--on",
        type=float,
        default=4.0,
        help="Minutes each failure stays ON. Default: 4.",
    )

    parser.add_argument(
        "--recover",
        type=float,
        default=4.0,
        help="Healthy minutes after each failure. Default: 4.",
    )

    parser.add_argument(
        "--kinds",
        nargs="+",
        choices=SCENARIO_KINDS,
        default=list(SCENARIO_KINDS),
        help="Which failures to run, in order. Default: all.",
    )

    parser.add_argument(
        "--loop",
        action="store_true",
        help="Repeat the scenario until stopped with Ctrl+C.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    kinds = tuple(args.kinds)

    print("=" * 60)
    print("SENTINEL FAILURE SCENARIO")
    print("=" * 60)
    print(f"Failures:  {' → '.join(kinds)}")
    print(f"Warm-up:   {args.warmup:g} min healthy")
    print(f"Each:      {args.on:g} min ON, then {args.recover:g} min OFF")
    print(f"Loop:      {'yes' if args.loop else 'no'}")
    print(
        "Categorical: "
        + ("ON" if injection_status()["categorical"] else "OFF")
        + " (not touched by this script)"
    )
    print("=" * 60)

    # Start clean so the warm-up only sees healthy data.
    all_off(kinds)

    try:
        wait(args.warmup, "Warm-up (all scenario failures OFF)")

        round_number = 1

        while True:
            print(f"\n--- Round {round_number} ---")

            for kind in kinds:
                switch(kind, True)
                wait(args.on, f"{kind} ON, watch the monitor")

                switch(kind, False)
                wait(args.recover, f"{kind} OFF, incident should resolve")

            if not args.loop:
                break

            round_number += 1

        print(f"\n[{now()}] Scenario finished. All scenario failures OFF.")

    except KeyboardInterrupt:
        print()
        print(f"[{now()}] Stopped by user.")

    finally:
        # Never leave a failure running after the script exits.
        all_off(kinds)


if __name__ == "__main__":
    main()