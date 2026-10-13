"""
Dashboard-side logic for Sentinel. No Streamlit, no SQL.

Responsibilities
----------------
- load ``config/monitoring.yaml`` and flatten the categorical-drift block
- describe which detectors exist and which FHIR resources they cover
- derive current data health from OPEN incidents only
- classify a metric value against its configured threshold
- recover a detected category distribution from an incident message, only
  when it is unambiguous AND reproduces the stored Jensen–Shannon distance
- human-readable labels and timestamp formatting

Nothing here fabricates data: every function either transforms real values
from PostgreSQL / monitoring.yaml or returns ``None``.
"""

from __future__ import annotations

import ast
import json
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml


CONFIG_RELATIVE_PATH = Path("config") / "monitoring.yaml"

# Presentation-only: fraction of the threshold at which a value is shown as
# "approaching". It does not affect detection.
NEAR_THRESHOLD_RATIO = 0.75

# Max allowed difference between the JSD recomputed from a recovered
# distribution and the JSD the detector stored. Messages usually round
# proportions, so a small tolerance is needed.
JSD_VERIFY_TOLERANCE = 0.01

SEVERITY_ORDER = ("low", "medium", "high", "critical")
STATUS_ORDER = ("open", "acknowledged", "resolved")
_SEVERITY_RANK = {name: rank for rank, name in enumerate(SEVERITY_ORDER)}

# The resource set shown on the Overview card (from the Sentinel slide).
# Resources are only marked as monitored when a configured detector covers
# them — listing them here never implies they are healthy.
OVERVIEW_RESOURCES = ("Patient", "Observation", "Encounter")

# Short chart labels for SNOMED smoking-status codes. Labels only, never
# values. Displays from monitoring.yaml are used in tooltips.
_SHORT_CATEGORY_LABELS = {
    "266919005": "Never smoked",
    "8517006": "Ex-smoker",
    "449868002": "Daily smoker",
}

_FALLBACK_CATEGORY_DISPLAYS = {
    "266919005": "Never smoked tobacco (finding)",
    "8517006": "Ex-smoker (finding)",
    "449868002": "Smokes tobacco daily (finding)",
}

_LABELS = {
    "jensen_shannon_distance": "Jensen–Shannon Distance",
    "categorical_code": "Categorical code",
    "latest_status_per_patient": "Latest status per patient",
    "ks_statistic": "KS Statistic",
    "null_rate": "Null Rate",
    "class_code": "Encounter class",
}


# ---------------------------------------------------------------------------
# Detector registry (product metadata, not data)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Detector:
    key: str
    name: str
    signal: str
    method: str
    incident_types: tuple[str, ...]
    config_keys: tuple[str, ...]


DETECTORS: tuple[Detector, ...] = (
    Detector(
        "contract",
        "Contract validation",
        "Required fields · allowed values · value/type consistency",
        "Deterministic FHIR contract validation",
        (
            "missing_required_field",
            "invalid_value",
            "type_mismatch",
        ),
        ("contract",),
    ),
    # Same incident types as "contract", on Patient rows.
    # Kept after "contract" so DETECTORS[0] stays the Observation contract.
    Detector(
        "patient_contract",
        "Patient contract validation",
        "Required fields · allowed gender · valid birth date · marital status",
        "Deterministic FHIR contract validation",
        (
            "missing_required_field",
            "invalid_value",
            "type_mismatch",
        ),
        ("patient_contract",),
    ),
    # Same incident types as "contract", on Encounter rows.
    Detector(
        "encounter_contract",
        "Encounter contract validation",
        "Required fields · status · class · start/end time · unique id",
        "Deterministic FHIR contract validation",
        (
            "missing_required_field",
            "invalid_value",
            "type_mismatch",
        ),
        ("encounter_contract",),
    ),
    Detector(
        "null_spike",
        "Null spike",
        "Null proportion per window",
        "Robust historical threshold + minimum absolute rule",
        ("null_spike",),
        ("null_spike", "missingness"),
    ),
    Detector(
        "volume",
        "Volume drop / spike",
        "Count per processing window",
        "Robust historical threshold + percentage guardrail",
        ("volume_drop", "volume_spike"),
        ("volume",),
    ),
    Detector(
        "numeric_drift",
        "Numeric distribution drift",
        "Numeric values",
        "KS test + effect-size guardrail",
        ("numeric_drift",),
        ("numeric_drift",),
    ),
    Detector(
        "categorical_drift",
        "Categorical distribution drift",
        "Category proportions",
        "Jensen–Shannon distance + threshold",
        ("categorical_drift",),
        ("categorical_drift",),
    ),
    # Same incident type as "categorical_drift", on Encounter rows.
    # The resource decides which one an incident belongs to
    # (views._detector_for).
    Detector(
        "encounter_class_drift",
        "Encounter class drift",
        "Share of each encounter class (AMB, EMER, IMP, ...) in the last 1000 encounters",
        "Jensen–Shannon distance vs Silver baseline + threshold",
        ("categorical_drift",),
        ("encounter_class_drift",),
    ),
)

CONTRACT_INCIDENT_TYPES = DETECTORS[0].incident_types


@dataclass(frozen=True)
class DetectorStatus:
    detector: Detector
    configured: bool
    incident_count: int
    resource_type: str | None

    @property
    def active(self) -> bool:
        return self.configured or self.incident_count > 0


def detector_statuses(
    config: dict, incident_counts_by_type: dict[str, int]
) -> list[DetectorStatus]:
    """
    A detector is 'active' when monitoring.yaml configures it or PostgreSQL
    already holds incidents of its types. Otherwise it is planned.
    """

    statuses = []
    for detector in DETECTORS:
        section = next(
            (config.get(key) for key in detector.config_keys if config.get(key)),
            None,
        )
        statuses.append(
            DetectorStatus(
                detector=detector,
                configured=section is not None,
                incident_count=sum(
                    incident_counts_by_type.get(t, 0) for t in detector.incident_types
                ),
                resource_type=_section_resource(section),
            )
        )
    return statuses


def _section_resource(section: Any) -> str | None:
    if not isinstance(section, dict):
        return None
    explicit = section.get("resource_type") or section.get("resource")
    if isinstance(explicit, str):
        return explicit
    if "observation" in section:
        return "Observation"
    return None


def monitored_resources(statuses: list[DetectorStatus]) -> dict[str, list[str]]:
    """resource_type -> names of configured detectors covering it."""

    coverage: dict[str, list[str]] = {}
    for status in statuses:
        if status.configured and status.resource_type:
            coverage.setdefault(status.resource_type, []).append(status.detector.name)
    return coverage


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def resolve_config_path() -> Path:
    """Find monitoring.yaml from the working directory or the repo root."""

    candidates = [
        Path.cwd() / CONFIG_RELATIVE_PATH,
        Path(__file__).resolve().parents[3] / CONFIG_RELATIVE_PATH,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    searched = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"monitoring.yaml not found (searched: {searched})")


def load_monitoring_config(path: Path | None = None) -> dict:
    with open(path or resolve_config_path(), "r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def categorical_settings(config: dict) -> dict[str, Any] | None:
    """
    Flatten the ``categorical_drift`` block into what the UI needs.

    Returns ``None`` when the block is absent. Raises ``ValueError`` naming
    the missing key when the block exists but is incomplete.
    """

    block = config.get("categorical_drift")
    if not block:
        return None
    try:
        injection = block.get("injection") or {}
        displays = {
            str(category["code"]): category["display"]
            for category in (
                injection.get("source_category"),
                injection.get("target_category"),
            )
            if category and category.get("code") and category.get("display")
        }
        baseline = {
            str(code): float(value)
            for code, value in block["baseline"]["proportions"].items()
        }
        return {
            "observation_code": str(block["observation"]["code"]),
            "observation_display": block["observation"]["display"],
            "field_name": block["field_name"],
            "method": block["detection"]["method"],
            "threshold": float(block["detection"]["threshold"]),
            "min_samples": int(block["detection"]["min_samples"]),
            "baseline_level": block["baseline"]["level"],
            "baseline": baseline,
            "incident_type": block["incident"]["type"],
            "metric_name": block["incident"]["metric_name"],
            "category_displays": displays,
        }
    except KeyError as missing:
        raise ValueError(
            f"monitoring.yaml is missing categorical_drift key {missing}"
        ) from None

def numeric_settings(config: dict) -> dict[str, Any] | None:
    """
    Flatten the ``numeric_drift`` block into what the UI needs.

    Returns ``None`` when the block is absent. Raises ``ValueError`` naming
    the missing key when the block exists but is incomplete.
    """

    block = config.get("numeric_drift")
    if not block:
        return None
    try:
        observations = {
            str(observation["code"]): {
                "display": observation["display"],
                "unit": observation.get("unit", ""),
            }
            for observation in block["observations"]
        }
        severity_thresholds = {
            level: float(value)
            for level, value in block["severity"].items()
        }
        return {
            "resource_type": block["resource_type"],
            "field_name": block["field_name"],
            "observations": observations,
            "method": block["detection"]["method"],
            "alpha": float(block["detection"]["alpha"]),
            "min_effect": float(block["detection"]["min_effect"]),
            "min_samples": int(block["detection"]["min_samples"]),
            "severity_thresholds": severity_thresholds,
            "incident_type": block["incident"]["type"],
            "metric_name": block["incident"]["metric_name"],
        }
    except KeyError as missing:
        raise ValueError(
            f"monitoring.yaml is missing numeric_drift key {missing}"
        ) from None


# Readable names for FHIR v3 ActCode encounter classes.
ENCOUNTER_CLASS_LABELS = {
    "AMB": "Ambulatory",
    "EMER": "Emergency",
    "IMP": "Inpatient",
    "HH": "Home health",
    "VR": "Virtual",
    "ACUTE": "Inpatient acute",
    "NONAC": "Inpatient non-acute",
    "OBSENC": "Observation encounter",
    "PRENC": "Pre-admission",
    "SS": "Short stay",
    "FLD": "Field",
}

BASELINES_FILE_NAME = "baselines.json"


def load_silver_baselines(config_path: Path | None = None) -> dict | None:
    """config/baselines.json (built from Silver), or None when it is missing."""

    path = (config_path or resolve_config_path()).parent / BASELINES_FILE_NAME
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, ValueError):
        return None


def encounter_class_settings(
    config: dict,
    baselines: dict | None,
) -> dict[str, Any] | None:
    """
    Flatten the ``encounter_class_drift`` block plus the Silver class
    proportions into what the UI needs.

    Returns ``None`` when the block or the Silver proportions are missing,
    the same rule the monitor uses to switch the check off.
    """

    block = config.get("encounter_class_drift")
    silver = (baselines or {}).get("encounter_class") or {}
    proportions = silver.get("proportions")
    if not block or not proportions:
        return None
    try:
        injection = block.get("injection") or {}
        return {
            "resource_type": block.get("resource_type", "Encounter"),
            "field_name": block.get("field_name", "class_code"),
            "method": block["detection"].get("method", "jensen_shannon_distance"),
            "threshold": float(block["detection"]["threshold"]),
            "min_samples": int(block["detection"]["min_samples"]),
            "incident_type": block["incident"]["type"],
            "metric_name": block["incident"]["metric_name"],
            "baseline": {str(code): float(share) for code, share in proportions.items()},
            "baseline_encounters": silver.get("encounters"),
            "baseline_source": (baselines or {}).get("source"),
            "baseline_built_at": (baselines or {}).get("built_at"),
            "injection": (
                f"{injection['source_class']} → {injection['target_class']} "
                f"({float(injection['fraction']):.0%})"
                if injection.get("source_class") and injection.get("target_class")
                else None
            ),
        }
    except KeyError as missing:
        raise ValueError(
            f"monitoring.yaml is missing encounter_class_drift key {missing}"
        ) from None


def encounter_class_label(code: str) -> str:
    return ENCOUNTER_CLASS_LABELS.get(code, code)


_ENCOUNTER_OBSERVED_PATTERN = re.compile(r"Observed:\s*(.*?)\.\s*Silver baseline:", re.S)
_ENCOUNTER_SHARE_PATTERN = re.compile(r"([A-Z]+)\s+([0-9]*\.?[0-9]+)%")


def recover_encounter_distribution(
    message: str | None,
    observed_jsd: float | None,
    baseline: dict[str, float],
) -> RecoveryResult:
    """
    Class proportions at detection, read from an Encounter class drift
    message ("Observed: AMB 69.1%, EMER 30.3%, ...").

    Same rule as the smoking check: only returned when the JSD recomputed
    from them against the Silver baseline matches the stored JSD.
    """

    if not message:
        return RecoveryResult(None, "Incident has no message context.")
    if observed_jsd is None:
        return RecoveryResult(None, "Incident has no stored JSD to verify against.")

    match = _ENCOUNTER_OBSERVED_PATTERN.search(message)
    shares = (
        {code: float(value) for code, value in _ENCOUNTER_SHARE_PATTERN.findall(match.group(1))}
        if match
        else {}
    )
    if len(shares) < 2 or sum(shares.values()) <= 0:
        return RecoveryResult(
            None, "The incident message does not contain the observed class shares."
        )

    total = sum(shares.values())
    parsed = {code: shares.get(code, 0.0) / total for code in set(baseline) | set(shares)}

    recomputed = jensen_shannon_distance(baseline, parsed)
    if abs(recomputed - observed_jsd) > JSD_VERIFY_TOLERANCE:
        return RecoveryResult(
            None,
            f"Shares found in the message give JSD {recomputed:.4f}, which "
            f"does not match the stored {observed_jsd:.4f}, so they are not shown.",
        )
    return RecoveryResult(RecoveredDistribution(parsed, recomputed, observed_jsd), "")


def category_display(code: str, settings: dict[str, Any]) -> str:
    return (
        settings["category_displays"].get(code)
        or _FALLBACK_CATEGORY_DISPLAYS.get(code)
        or code
    )


def category_short_label(code: str, settings: dict[str, Any]) -> str:
    if code in _SHORT_CATEGORY_LABELS:
        return _SHORT_CATEGORY_LABELS[code]
    return re.sub(r"\s*\([^()]*\)\s*$", "", category_display(code, settings))


# ---------------------------------------------------------------------------
# Human-readable names
# ---------------------------------------------------------------------------


def humanize(identifier: str | None) -> str:
    """categorical_drift -> Categorical Drift."""

    if not identifier:
        return "—"
    if identifier in _LABELS:
        return _LABELS[identifier]
    return identifier.replace("_", " ").strip().title()


def sentence_case(identifier: str | None) -> str:
    """latest_status_per_patient -> Latest status per patient."""

    if not identifier:
        return "—"
    if identifier in _LABELS:
        return _LABELS[identifier]
    text = identifier.replace("_", " ").strip()
    return text[:1].upper() + text[1:]


def format_value(value: float | None, digits: int = 4) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    return f"{value:.{digits}f}"


# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------


def display_timezone():
    """
    Timezone for displayed timestamps: SENTINEL_DISPLAY_TZ (IANA name) if
    set, otherwise the machine's local timezone.
    """

    name = os.getenv("SENTINEL_DISPLAY_TZ")
    if name:
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError:
            pass
    return datetime.now().astimezone().tzinfo


def to_display_tz(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(display_timezone())


def format_timestamp(moment: datetime | None, with_seconds: bool = True) -> str:
    if moment is None:
        return "—"
    local = to_display_tz(moment)
    pattern = "%d %b %Y, %H:%M:%S" if with_seconds else "%d %b %Y, %H:%M"
    return f"{local.strftime(pattern)} {tz_label(local)}"


def tz_label(moment: datetime) -> str:
    offset = moment.utcoffset()
    if offset is None or offset.total_seconds() == 0:
        return "UTC"
    name = moment.tzname() or ""
    if name and not name.startswith(("+", "-")):
        return name
    minutes = int(offset.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    hours, mins = divmod(abs(minutes), 60)
    return f"UTC{sign}{hours}" + (f":{mins:02d}" if mins else "")


def relative_time(moment: datetime | None, now: datetime | None = None) -> str:
    if moment is None:
        return "—"
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    seconds = int((now - moment).total_seconds())
    if seconds < 0:
        return "just now"
    for size, unit in ((86400, "d"), (3600, "h"), (60, "min")):
        if seconds >= size:
            return f"{seconds // size} {unit} ago"
    return f"{seconds} s ago"


# ---------------------------------------------------------------------------
# Health and threshold state
# ---------------------------------------------------------------------------


class HealthState(NamedTuple):
    label: str  # Healthy / Attention / Critical
    tone: str  # green / amber / rose
    detail: str


def worst_severity(severities) -> str | None:
    ranked = [s for s in severities if s in _SEVERITY_RANK]
    return max(ranked, key=_SEVERITY_RANK.get) if ranked else None


def assess_health(open_by_severity: dict[str, int]) -> HealthState:
    """
    Current data health from OPEN incidents only. Resolved or acknowledged
    history does not make the data permanently unhealthy.
    """

    counts = {s: n for s, n in open_by_severity.items() if n}
    open_total = sum(counts.values())
    if open_total == 0:
        return HealthState("Healthy", "green", "No open data-health incidents")

    worst = worst_severity(counts) or "medium"
    noun = "incident" if open_total == 1 else "incidents"
    if _SEVERITY_RANK[worst] >= _SEVERITY_RANK["high"]:
        return HealthState(
            "Critical", "rose", f"{open_total} open {noun} · highest severity {worst}"
        )
    return HealthState("Attention", "amber", f"{open_total} open {noun} require attention")


def resource_state(
    resource_type: str,
    coverage: dict[str, list[str]],
    open_by_resource: dict[str, dict[str, int]],
) -> tuple[str, str]:
    """(label, tone) for one FHIR resource on the Overview card."""

    open_counts = open_by_resource.get(resource_type, {})
    if resource_type not in coverage and not any(open_counts.values()):
        return "Not monitored yet", "muted"
    health = assess_health(open_counts)
    return health.label, health.tone


def severity_tone(severity: str | None) -> str:
    return {
        "low": "cyan",
        "medium": "amber",
        "high": "rose",
        "critical": "rose",
    }.get((severity or "").lower(), "muted")


def status_tone(status: str | None) -> str:
    return {
        "open": "amber",
        "acknowledged": "blue",
        "resolved": "green",
    }.get((status or "").lower(), "muted")


def threshold_state(value: float | None, threshold: float) -> str:
    """'normal' | 'near' | 'exceeded' | 'unknown' for a value vs threshold."""

    if value is None:
        return "unknown"
    if value >= threshold:
        return "exceeded"
    if value >= threshold * NEAR_THRESHOLD_RATIO:
        return "near"
    return "normal"


THRESHOLD_STATE_TONE = {
    "normal": "cyan",
    "near": "amber",
    "exceeded": "rose",
    "unknown": "muted",
}


class IncidentContext(NamedTuple):
    title: str  # e.g. "Tobacco smoking status"
    subtitle: str  # e.g. "FHIR Observation · 72166-2"
    metric_label: str  # e.g. "Jensen–Shannon Distance"
    observed: float | None
    reference: float | None  # threshold or scalar baseline
    reference_label: str  # "threshold" / "baseline"
    comparator: str  # ">", "<", "="
    tone: str  # tone of the observed value
    # Optional display overrides. When empty, the card formats the numbers.
    observed_label: str = "observed"
    observed_text: str | None = None  # e.g. "3" instead of "3.0000"
    reference_text: str | None = None
    note: str | None = None  # one line under the numbers


def incident_context(incident: dict, settings: dict[str, Any] | None) -> IncidentContext:
    """
    How to present one incident. A categorical-drift incident that matches
    monitoring.yaml is compared with the configured threshold; anything else
    is compared with its stored scalar baseline (if any).
    """

    observed = incident.get("observed_value")
    matches_categorical = (
        settings is not None
        and incident.get("incident_type") == settings["incident_type"]
        and incident.get("metric_name") == settings["metric_name"]
        # The categorical_drift settings describe the Observation (smoking)
        # check. Encounter class drift uses the same incident type and metric,
        # so it is told apart by its resource.
        and (incident.get("resource_type") or "Observation") == "Observation"
    )
    if matches_categorical:
        reference = settings["threshold"]
        title = settings["observation_display"]
        subtitle = f"FHIR {incident.get('resource_type') or 'Observation'} · {settings['observation_code']}"
        reference_label = "threshold"
        tone = severity_tone(incident.get("severity"))
    else:
        reference = incident.get("baseline_value")
        field = incident.get("field_name")
        title = sentence_case(field) if field else humanize(incident.get("metric_name"))
        subtitle = f"FHIR {incident.get('resource_type') or '—'}"
        reference_label = "baseline"
        tone = severity_tone(incident.get("severity"))

    if observed is None or reference is None:
        comparator = ""
    elif observed > reference:
        comparator = ">"
    elif observed < reference:
        comparator = "<"
    else:
        comparator = "="

    return IncidentContext(
        title=title,
        subtitle=subtitle,
        metric_label=humanize(incident.get("metric_name")),
        observed=observed,
        reference=reference,
        reference_label=reference_label,
        comparator=comparator,
        tone=tone,
    )


# ---------------------------------------------------------------------------
# Jensen–Shannon distance (used only to VERIFY recovered distributions)
# ---------------------------------------------------------------------------


def jensen_shannon_distance(
    p: dict[str, float], q: dict[str, float], base: float = 2.0
) -> float:
    """
    sqrt(JS divergence), same definition as scipy.spatial.distance.jensenshannon.
    Base 2 reproduces the values Sentinel's detector stores.
    """

    codes = set(p) | set(q)
    p_total = sum(p.values()) or 1.0
    q_total = sum(q.values()) or 1.0
    pv = [p.get(c, 0.0) / p_total for c in codes]
    qv = [q.get(c, 0.0) / q_total for c in codes]
    mv = [(a + b) / 2 for a, b in zip(pv, qv)]

    def kl(x, y):
        return sum(a * math.log(a / b) for a, b in zip(x, y) if a > 0)

    divergence = max(0.0, 0.5 * kl(pv, mv) + 0.5 * kl(qv, mv))
    return math.sqrt(divergence / math.log(base))


# ---------------------------------------------------------------------------
# Detected-distribution recovery from the incident message
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RecoveredDistribution:
    proportions: dict[str, float]
    recomputed_jsd: float
    stored_jsd: float


class RecoveryResult(NamedTuple):
    distribution: RecoveredDistribution | None
    reason: str  # why it is unavailable; empty when recovered


def recover_detected_distribution(
    message: str | None,
    observed_jsd: float | None,
    settings: dict[str, Any],
) -> RecoveryResult:
    """
    Recover detected category proportions from an incident message.

    The result is only returned when:
    - the message unambiguously contains one observed distribution over the
      configured baseline categories (codes or their displays), and
    - the JSD recomputed from it against the configured baseline matches the
      JSD the detector stored in ``incidents.observed_value``.

    Otherwise the distribution is reported as unavailable, never guessed.
    """

    baseline: dict[str, float] = settings["baseline"]
    if not message:
        return RecoveryResult(None, "Incident has no message context.")
    if observed_jsd is None:
        return RecoveryResult(None, "Incident has no stored JSD to verify against.")

    parsed = parse_distribution(message, settings)
    if parsed is None:
        return RecoveryResult(
            None,
            "The incident message does not contain an unambiguous category "
            "distribution.",
        )

    recomputed = jensen_shannon_distance(baseline, parsed)
    if abs(recomputed - observed_jsd) > JSD_VERIFY_TOLERANCE:
        return RecoveryResult(
            None,
            f"Proportions found in the message give JSD {recomputed:.4f}, which "
            f"does not match the stored {observed_jsd:.4f}, so they are not shown.",
        )
    return RecoveryResult(RecoveredDistribution(parsed, recomputed, observed_jsd), "")


_OBSERVED_WORDS = ("observed", "detected", "current", "live", "window", "actual")
_BASELINE_WORDS = ("baseline", "expected", "reference", "historical")
_PAIR_PATTERN = re.compile(
    r"""["']?(?P<code>\d{5,18})["']?         # SNOMED code, optionally quoted
        (?:\s*\([^()]{0,80}\))?             # optional "(Never smoked ...)"
        \s*[:=]\s*
        (?P<value>\d+(?:\.\d+)?)\s*(?P<pct>%)?""",
    re.VERBOSE,
)
_DICT_PATTERN = re.compile(r"\{[^{}]*\}")


def parse_distribution(message: str, settings: dict[str, Any]) -> dict[str, float] | None:
    """Parse proportions over the baseline categories, or ``None``."""

    baseline_codes = set(settings["baseline"])
    text = _codes_for_displays(message, baseline_codes, settings)

    candidates = _dict_candidates(text, baseline_codes)
    if not candidates:
        candidates = _pair_candidates(text, baseline_codes)

    chosen = _choose_observed(candidates)
    if chosen is None:
        return None
    return _normalise(chosen, baseline_codes)


def _codes_for_displays(message: str, codes: set[str], settings: dict[str, Any]) -> str:
    """Replace category display names with their codes so one parser handles both."""

    names: list[tuple[str, str]] = []
    for code in codes:
        full = category_display(code, settings)
        names.append((full, code))
        stripped = re.sub(r"\s*\([^()]*\)\s*$", "", full)
        if stripped != full:
            names.append((stripped, code))
    for name, code in sorted(names, key=lambda item: -len(item[0])):
        if name and name != code:
            message = re.sub(re.escape(name), code, message, flags=re.IGNORECASE)
    return message


def _dict_candidates(message: str, known: set[str]) -> list[tuple[str, dict]]:
    found = []
    previous_end = 0
    for match in _DICT_PATTERN.finditer(message):
        context = message[max(previous_end, match.start() - 60) : match.start()]
        previous_end = match.end()
        parsed = _parse_literal(match.group())
        if not isinstance(parsed, dict):
            continue
        values = _numeric_known(parsed, known)
        if values:
            found.append((context, values))
    return found


def _parse_literal(text: str) -> Any:
    for parser in (json.loads, ast.literal_eval):
        try:
            return parser(text)
        except (ValueError, SyntaxError, TypeError):
            continue
    return None


def _numeric_known(mapping: dict, known: set[str]) -> dict[str, float] | None:
    values: dict[str, float] = {}
    for key, value in mapping.items():
        code = str(key).strip()
        if code not in known:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        values[code] = float(value)
    return values or None


def _pair_candidates(message: str, known: set[str]) -> list[tuple[str, dict]]:
    """
    Parse 'code: value' pairs. If a code repeats (e.g. baseline and observed
    both listed), split on labelling keywords and parse each segment.
    """

    def parse(segment: str) -> tuple[dict[str, float], bool, int]:
        values: dict[str, float] = {}
        repeated = False
        first = -1
        for match in _PAIR_PATTERN.finditer(segment):
            code = match["code"]
            if code not in known:
                continue
            if first < 0:
                first = match.start()
            if code in values:
                repeated = True
            values[code] = float(match["value"])
        return values, repeated, first

    values, repeated, first = parse(message)
    if not values:
        return []
    if not repeated:
        return [(message[max(0, first - 60) : first], values)]

    keyword = re.compile(
        r"\b(" + "|".join(_OBSERVED_WORDS + _BASELINE_WORDS) + r")\b", re.I
    )
    starts = [m.start() for m in keyword.finditer(message)] + [len(message)]
    segments = []
    for begin, end in zip(starts, starts[1:]):
        segment = message[begin:end]
        segment_values, segment_repeated, _ = parse(segment)
        if segment_values and not segment_repeated:
            segments.append((segment[:60], segment_values))
    return segments


def _choose_observed(candidates: list[tuple[str, dict]]) -> dict | None:
    if not candidates:
        return None
    if len(candidates) == 1:
        context, values = candidates[0]
        baseline_only = _labelled(context, _BASELINE_WORDS) and not _labelled(
            context, _OBSERVED_WORDS
        )
        return None if baseline_only else values

    observed = [
        values
        for context, values in candidates
        if _labelled(context, _OBSERVED_WORDS) and not _labelled(context, _BASELINE_WORDS)
    ]
    return observed[0] if len(observed) == 1 else None


def _labelled(context: str, words: tuple[str, ...]) -> bool:
    lowered = context.lower()
    return any(re.search(rf"\b{word}\b", lowered) for word in words)


def _normalise(values: dict[str, float], known: set[str]) -> dict[str, float] | None:
    if len(values) < 2 or any(v < 0 for v in values.values()):
        return None
    total = sum(values.values())
    if total <= 0:
        return None

    is_proportion = abs(total - 1.0) <= 0.02 and all(v <= 1 for v in values.values())
    is_percentage = abs(total - 100.0) <= 2.0
    is_count = all(float(v).is_integer() for v in values.values())
    if not (is_proportion or is_percentage or is_count):
        return None
    return {code: values.get(code, 0.0) / total for code in known}