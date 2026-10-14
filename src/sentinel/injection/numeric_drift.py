"""
Inject numeric distribution drift into Observation values.

The values stay valid numbers, so the contract detector still passes.
Only the distribution moves, which is what the numeric drift detector looks for.
"""

import copy
import os

import numpy as np
import pandas as pd


SILVER_PATH = os.getenv("SENTINEL_SILVER_PATH")

# Measurements we inject into (LOINC code -> readable name).
INJECTABLE_CODES = {
    "8867-4": "Heart rate",
    "8480-6": "Systolic Blood Pressure",
    "2339-0": "Glucose",
}

# Default drift size: shift = SHIFT_K * standard deviation of the healthy values.
SHIFT_K = 0.75


def load_baseline(codes=INJECTABLE_CODES, path: str | None = SILVER_PATH) -> dict[str, list[float]]:
    """Read the healthy values for each code. Returns {code: [values]}."""
    if not path:
        raise ValueError(
            "SENTINEL_SILVER_PATH is not configured. "
            "Set it to the Observation Silver Parquet path."
        )

    df = pd.read_parquet(path, columns=["code", "numeric_value"])
    df = df[df["code"].isin(list(codes))].dropna(subset=["numeric_value"])
    return {code: group["numeric_value"].tolist() for code, group in df.groupby("code")}


def shift_for(reference, k: float = SHIFT_K) -> float:
    """Drift size that fits this measurement: k standard deviations."""
    return round(k * float(np.std(reference)), 2)


def sample_healthy(reference, n: int, seed: int) -> np.ndarray:
    """Draw n values at random from the healthy values (same seed = same sample)."""
    rng = np.random.default_rng(seed)
    return rng.choice(np.asarray(reference, dtype=float), size=n, replace=True)


def inject_shift(values, shift: float) -> np.ndarray:
    """Move every value by a fixed amount (location drift)."""
    return np.asarray(values, dtype=float) + shift


def _code_of(item: dict) -> str | None:
    """Read the code from a flat row ("code": "8867-4") or a raw FHIR item."""
    code = item.get("code")
    if isinstance(code, dict):
        coding = code.get("coding") or [{}]
        return coding[0].get("code")
    return code


def _shift_value(item: dict, shift: float) -> None:
    """Shift the numeric value of one flat row or one raw FHIR item, in place."""
    quantity = item.get("valueQuantity")
    if isinstance(quantity, dict) and quantity.get("value") is not None:
        quantity["value"] = round(quantity["value"] + shift, 2)
    elif item.get("numeric_value") is not None:
        item["numeric_value"] = round(item["numeric_value"] + shift, 2)


def inject_record(record: dict, code: str, shift: float) -> dict:
    """
    Return a copy of one Observation with the value of `code` shifted.

    Works on a flat normalized row and on a raw FHIR Observation, including
    values stored inside "component" (e.g. systolic inside a blood pressure panel).
    Records that do not contain `code` come back unchanged.
    """
    out = copy.deepcopy(record)

    if _code_of(out) == code:
        _shift_value(out, shift)

    for component in out.get("component") or []:
        if _code_of(component) == code:
            _shift_value(component, shift)

    return out


if __name__ == "__main__":
    baseline = load_baseline()

    print(f"{'code':<10}{'name':<26}{'n':>6}{'median':>9}{'std':>8}{'shift':>8}")
    for code, name in INJECTABLE_CODES.items():
        values = baseline[code]
        print(f"{code:<10}{name:<26}{len(values):>6}{np.median(values):>9.2f}"
              f"{np.std(values):>8.2f}{shift_for(values):>8.2f}")