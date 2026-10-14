# Sentinel

**Real-time data health monitoring for streaming healthcare data.**

> The pipeline can be green while the data is wrong.

Sentinel is a data engineering capstone that detects data-quality problems in real-time FHIR streams, even when the underlying pipeline continues to run successfully.

It validates incoming records, profiles streaming windows, compares live behavior with healthy baselines, detects drift and anomalies, manages incidents in PostgreSQL, and surfaces data-health signals through a Streamlit dashboard.

**Sentinel monitors data health — not patient health.**

[View the Sentinel case study](https://yaqeendata.github.io/sentinel/)

---

## The Problem

Infrastructure monitoring can tell us whether a pipeline is running.

It does not necessarily tell us whether the data flowing through it is still trustworthy.

A pipeline may remain completely operational while:

- required fields disappear,
- null rates suddenly increase,
- numeric distributions shift,
- categorical distributions change,
- record volume drops,
- or upstream schemas change.

Nothing has to crash for bad data to reach downstream systems.

Sentinel explores one question:

> **The pipeline is green — but is the data healthy?**

---

## Architecture

Sentinel separates the live streaming path from the historical reference path, bringing both together in the detection engine to evaluate the health of incoming data.

<p align="center">
  <img
    src="assets/architecture/sentinel-architecture-16x9.dark.png"
    alt="Sentinel system architecture showing the live FHIR streaming pipeline and historical baseline path"
    width="100%"
  />
</p>

### Architecture Flow

**Live monitoring**

`Synthea → HAPI FHIR → Python Producer → Apache Kafka → 60-Second Windows → Sentinel Detection Engine → PostgreSQL → Streamlit`

**Reference / baseline**

`Google Cloud → Baseline Profiling → Sentinel Detection Engine`

The live stream is evaluated in 60-second processing windows while historical healthy data provides the reference behavior used by Sentinel's drift and quality detectors.

### What Each Component Does

| Component | Role |
| --- | --- |
| **Synthea** | Generates realistic but fully synthetic healthcare data for testing and replay. |
| **HAPI FHIR** | Hosts FHIR resources such as `Patient`, `Encounter`, and `Observation`. |
| **Python Producer** | Reads FHIR resources and publishes them as streaming events. |
| **Apache Kafka** | Provides the streaming backbone between data production and real-time monitoring. |
| **60-Second Windows** | Groups live events into fixed processing windows for profiling and detection. |
| **Google Cloud** | Stores historical, raw, and processed datasets used by the reference pipeline. |
| **Baseline Profiling** | Builds the expected healthy behavior used for comparison with live data. |
| **Sentinel Detection Engine** | Runs contract validation, missingness, numeric drift, categorical drift, and volume monitoring. |
| **PostgreSQL** | Persists quality metrics, incidents, statuses, and monitoring history. |
| **Streamlit** | Provides the internal data-observability dashboard for engineering teams. |

> **Sentinel monitors data health, not patient health.**

---

## Detection Engine

Sentinel currently monitors several classes of data-quality failure.

| Detector | Purpose |
| --- | --- |
| **Contract Validation** | Detects missing required fields, invalid types, and structural violations |
| **Missingness** | Detects unexpected increases in null values |
| **Numeric Drift** | Detects changes in numeric distributions |
| **Categorical Drift** | Detects changes in categorical distributions |
| **Volume** | Detects abnormal changes in incoming record volume |

### Numeric Drift

Numeric drift uses a two-sample Kolmogorov-Smirnov test together with sample-size and effect-size safeguards.

### Categorical Drift

Categorical distributions are compared using Jensen-Shannon distance.

### Volume Monitoring

Volume detection compares the current window against historical behavior using robust statistics and percentage-based guardrails.

---

## Controlled Failure Injection

Sentinel includes controlled failure-injection utilities so detector behavior can be demonstrated and tested deliberately.

Supported scenarios include:

- contract violations,
- missingness spikes,
- numeric drift,
- categorical drift,
- volume anomalies,
- and schema changes.

This makes it possible to observe the complete lifecycle from healthy data to detection, incident creation, and recovery.

---

## Tech Stack

### Streaming & Processing

- Python
- Apache Kafka
- Pandas
- Polars
- SciPy

### Healthcare Data

- FHIR
- Synthea
- HAPI FHIR

### Cloud & Storage

- Google Cloud
- PostgreSQL
- Parquet

### Monitoring

- Streamlit
- Plotly

### Engineering

- Poetry
- Pytest
- Git
- GitHub Actions

### Case Study Website

- React
- TypeScript
- Vite
- GitHub Pages

---

## Repository Structure

```text
sentinel/
├── .github/
│   └── workflows/
│
├── assets/
│   └── architecture/
│       ├── google-cloud.svg
│       ├── hapi-fhir.png
│       ├── kafka.svg
│       ├── postgresql.svg
│       ├── python.svg
│       ├── sentinel-architecture.svg
│       ├── streamlit.svg
│       └── synthea.png
│
├── data/
│   └── sample/
│       ├── Patient.ndjson
│       ├── Encounter.ndjson
│       ├── Observation.ndjson
│       └── README.md
│
├── docs/
│   └── proposal/
│       └── Sentinel Proposal.pptx
│
├── notebooks/
│   └── 01_data_exploration.ipynb
│
├── scripts/
│   ├── build_baselines.py
│   ├── check_contract_gcs.py
│   ├── check_contract_stream.py
│   ├── replay_stream.py
│   ├── run_experiment.py
│   ├── run_monitor.py
│   ├── run_scenario.py
│   └── set_injection.py
│
├── src/
│   └── sentinel/
│       ├── baseline/
│       ├── dashboard/
│       ├── detection/
│       ├── ingestion/
│       ├── injection/
│       ├── profiling/
│       ├── storage/
│       ├── streaming/
│       └── transformation/
│
├── tests/
│
├── Sentinel_Website/
│   └── sentinel-site/
│
├── .gitignore
├── pyproject.toml
├── poetry.lock
└── README.md
```

---

## Sample Data

A small synthetic FHIR dataset is included in:

```text
data/sample/
```

It contains:

- 5 Patient resources
- 25 Encounter resources
- 39 Observation resources

The sample is referentially coherent: included Encounter and Observation references resolve to resources contained in the sample.

The full replay dataset is generated locally and excluded from Git because of its size.

All healthcare records used by Sentinel are synthetic. They do not represent real patients.

---

## Installation

Sentinel uses **Python 3.12** and Poetry.

Install the project dependencies:

```bash
poetry install
```

Run the automated tests:

```bash
poetry run pytest -q
```

The current test suite contains **54 passing tests**.

---

## Running Sentinel

### Start the Monitoring Engine

```bash
poetry run python scripts/run_monitor.py
```

### Run a Controlled Experiment

```bash
poetry run python scripts/run_experiment.py
```

### Launch the Dashboard

```bash
poetry run streamlit run src/sentinel/dashboard/app.py
```

Additional scripts for baseline generation, streaming replay, contract validation, scenarios, and failure injection are available under `scripts/`.

---

## Dashboard

The Streamlit dashboard is designed for data engineering and data-quality teams.

It surfaces:

- data-quality incidents,
- incident severity and status,
- quality metrics,
- baseline comparisons,
- drift signals,
- schema changes,
- and streaming data health.

The dashboard is an internal data-observability interface.

It is **not a clinical monitoring system and does not monitor individual patient health**.

---

## Testing

The automated test suite covers key parts of Sentinel, including:

- contract validation,
- missingness detection,
- categorical drift,
- volume drift,
- controlled failure injection,
- Observation transformations,
- streaming profiles,
- and window management.

Run the complete suite with:

```bash
poetry run pytest -q
```

Current result:

```text
54 passed
```

---

## What Sentinel Demonstrates

Sentinel brings together several data engineering and data-observability concepts:

- real-time streaming ingestion,
- FHIR data processing,
- windowed stream processing,
- data contracts,
- statistical drift detection,
- baseline engineering,
- data-quality monitoring,
- incident lifecycle management,
- controlled failure injection,
- PostgreSQL persistence,
- automated testing,
- and observability dashboards.

The goal is not to replace infrastructure monitoring, but to complement it with visibility into the health of the data itself.

---

## Team

Sentinel was built by:

- Yaqeen Alhalal
- Sama Alharbi
- Sarah Masshi
- Rutanah Maghrabi

---

## Case Study

For the complete project story, architecture, detector design, controlled experiments, engineering decisions, limitations, and reflections:

**https://yaqeendata.github.io/sentinel/**
