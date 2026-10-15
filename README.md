# Sentinel

**Real-time data health monitoring for streaming healthcare data.**

> **The pipeline can be green while the data is unhealthy.**

Sentinel is a data-engineering prototype that watches a stream of synthetic FHIR healthcare data and flags data-quality problems that can stay invisible while the surrounding pipeline keeps running normally.

It currently monitors Patient, Encounter and Observation data and turns abnormal behavior into incidents that a data team can investigate.

**Sentinel monitors data health — not patient health.**

## Links

- **Case study:** <https://yaqeendata.github.io/sentinel/>
- **Demo video:** a short recorded walkthrough is on the case-study site.

## Why Sentinel?

Infrastructure monitoring tells us whether Kafka is running, a database is reachable, jobs succeed and dashboards load. All of that can look healthy while the data itself quietly becomes unhealthy:

- expected fields disappear
- values become unexpectedly empty
- fewer records arrive than expected
- numbers start behaving differently
- the mix of categories shifts

Unhealthy data keeps flowing into dashboards, analytics, machine-learning systems and reports. Sentinel helps make those changes visible earlier, so a data team can investigate before the problem spreads.

## The healthcare data

FHIR is a standard used by healthcare systems to structure and exchange healthcare information. Sentinel monitors three FHIR resources:

| Resource | In plain words |
| --- | --- |
| **Patient** | Who the person is |
| **Encounter** | A visit or healthcare interaction |
| **Observation** | A measurement, assessment, status or recorded clinical fact |

All healthcare data used by Sentinel is **synthetic**. It is generated with [Synthea](https://github.com/synthetichealth/synthea) and does not describe real people.

## What Sentinel checks

| Check | Question it answers |
| --- | --- |
| Contract Validation | Does the record still follow the expected rules? |
| Missingness | Did information that is normally present disappear? |
| Volume | Are we receiving the amount of data we expect? |
| Numeric Drift | Did numeric values start behaving differently? |
| Categorical Drift | Did the mix of categories unexpectedly change? |

**Monitor → Detect → Investigate → Recover**

## Architecture

![Sentinel architecture: live streaming path and historical reference path](Sentinel_Website/sentinel-site/public/assets/architecture/sentinel-architecture-final.webp)

Sentinel has two paths that meet in the detection engine.

**Live path.** Synthea generates synthetic FHIR data, a Python producer publishes it to Apache Kafka, and Sentinel groups the stream into 60-second windows. The detection engine checks each window, writes metrics and incidents to PostgreSQL, and a Streamlit dashboard shows them.

**Reference path.** Synthea also generated a historical set of synthetic FHIR data. Google Cloud Storage holds it (raw in Bronze, normalized in Silver), and it is profiled into a baseline of what healthy data looks like. The detection engine compares live windows against that baseline.

Google Cloud only stores the historical data; Synthea is where it comes from. In this repository the producer reads Synthea's FHIR output files directly — no HAPI FHIR server is started or needed (see the [architecture notes](docs/architecture/README.md)).

More detail: [docs/architecture/README.md](docs/architecture/README.md)

## Getting started

### Requirements

| Needed for | Requirement |
| --- | --- |
| Everything | Python 3.12 and [Poetry](https://python-poetry.org/) |
| Kafka and PostgreSQL | Docker with Docker Compose |
| Live data stream | Java, and Synthea's `synthea-with-dependencies.jar` from the [Synthea releases](https://github.com/synthetichealth/synthea/releases) |
| Rebuilding baselines only (optional) | Google Cloud credentials and access to the project's GCS bucket |

The local demo does **not** need Google Cloud: the baselines the monitor uses are already committed in `config/baselines.json`.

### 1. Clone and install

```bash
git clone https://github.com/YaqeenData/sentinel.git
cd sentinel
poetry install
```

### 2. Configure

```bash
cp .env.example .env
```

Open `.env` and set at least:

| Variable | What to put |
| --- | --- |
| `POSTGRES_PASSWORD` | Any local password (the default `change-me` also works locally) |
| `SYNTHEA_JAR` | Absolute path to `synthea-with-dependencies.jar` |

The other values in `.env.example` (`POSTGRES_*`, `KAFKA_*`, `REPLAY_RATE`, `SYNTHEA_POPULATION`) work as they are for a local demo. `GCP_PROJECT_ID` and `GCS_BUCKET` are only used by the Google Cloud workflow.

`.env` is ignored by Git. Never commit it.

### 3. Start Kafka and PostgreSQL

```bash
docker compose up -d
docker compose ps
```

This starts Apache Kafka (port 9092) and PostgreSQL (host port 5433). The Kafka topic (`fhir-observations`) does not need to be created by hand.

Create the Sentinel tables once:

```bash
docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < sql/schema.sql
```

The tables are **not** created automatically, and the script is safe to run again.

### 4. Baselines

Nothing to do for the demo: `config/baselines.json` is already in the repository.

To rebuild it from historical data in Google Cloud Storage (needs `GCP_PROJECT_ID`, `GCS_BUCKET` and `gcloud auth application-default login`):

```bash
poetry run python -m sentinel.baseline.builder
```

### 5. Start the monitor

```bash
poetry run python scripts/run_monitor.py
```

The monitor reads the Kafka stream, groups events into 60-second windows, runs the data-health checks, and writes metrics and incidents to PostgreSQL. Start it **before** the stream: by default it only reads messages that arrive after it starts.

### 6. Start the data stream

In a new terminal:

```bash
poetry run python -m sentinel.streaming.replay
```

This repeatedly generates a fresh batch of synthetic patients with Synthea and publishes their Patient, Encounter and Observation resources to Kafka. Stop it with `Ctrl+C`.

### 7. Start the dashboard

In a new terminal:

```bash
poetry run streamlit run src/sentinel/dashboard/app.py
```

Streamlit prints the local address (usually <http://localhost:8501>). The dashboard has Overview, Data Quality and Incidents pages and reads from PostgreSQL.

### Startup order at a glance

| Terminal | Command | Purpose |
| --- | --- | --- |
| 1 | `docker compose up -d`, then create tables once | Kafka and PostgreSQL |
| 2 | `poetry run python scripts/run_monitor.py` | Detect and record incidents |
| 3 | `poetry run python -m sentinel.streaming.replay` | Produce the live stream |
| 4 | `poetry run streamlit run src/sentinel/dashboard/app.py` | Watch it |
| 5 | `poetry run python scripts/set_injection.py ...` | Break the stream on purpose (next section) |

Give the monitor a few minutes of healthy data before injecting a failure, so it has something healthy to compare against.

## Run a controlled demo

Because the data is synthetic, Sentinel can break its own stream on purpose and show how it responds:

Healthy stream → inject a known problem → Sentinel detects it → an incident opens → investigate → restore healthy data → the incident resolves

With the monitor, stream and dashboard running, switch a failure on and off from another terminal:

```bash
poetry run python scripts/set_injection.py on volume
poetry run python scripts/set_injection.py off volume
```

Every script and failure type is described in [docs/experiments/README.md](docs/experiments/README.md).

## Testing

```bash
poetry run pytest -q
```

## Project structure

```text
sentinel/
├── config/              # Monitoring settings and committed baselines
├── data/sample/         # Small synthetic FHIR sample
├── docs/                # Architecture and experiment guides
├── scripts/             # Monitor, experiment and injection commands
├── sql/                 # PostgreSQL schema
├── src/sentinel/        # Sentinel application code
├── tests/               # Automated tests
├── Sentinel_Website/    # Case-study website (React, Vite)
├── docker-compose.yml   # Kafka and PostgreSQL
├── pyproject.toml
└── README.md
```

## Tech stack

- **Streaming:** Python, Apache Kafka
- **Healthcare data:** FHIR, Synthea
- **Storage:** Google Cloud Storage, PostgreSQL, Parquet
- **Monitoring:** Streamlit, Plotly
- **Engineering:** Poetry, Pytest, Docker, GitHub Actions
- **Website:** React, TypeScript, Vite, GitHub Pages

## Current scope

Sentinel is a controlled prototype, not a production clinical system. Today it supports:

- synthetic FHIR data: Patient, Encounter and Observation
- five data-health check categories
- historical reference behavior from a baseline
- incident lifecycle: open, acknowledged, resolved
- a Streamlit dashboard for data teams

A real hospital deployment would need additional governance, security, domain validation, broader FHIR coverage and production operations.

## Team

| Name | Role | Links |
| --- | --- | --- |
| Yaqeen Alhalal | Team Lead & Data Engineer | [LinkedIn](https://www.linkedin.com/in/yaqeen-alhalal-8388541a3/) · [Portfolio](https://www.yaqeenalhalal.dev) |
| Sama Alharbi | Data Engineer | [LinkedIn](https://www.linkedin.com/in/sama-a-831753201/) · [Portfolio](https://samaalharbi2.github.io/) |
| Sarah Masshi | Data Engineer | [LinkedIn](https://www.linkedin.com/in/sarah-maashi-5baa26282) |
| Rutanah Maghrabi | Data Engineer | [LinkedIn](https://www.linkedin.com/in/rutanah-maghrabi-22b3201b2) |

## Case study

For the full project story, architecture, product walkthrough, engineering decisions, limitations and production path, see the [Sentinel Case Study](https://yaqeendata.github.io/sentinel/).

**The pipeline can be green while the data is unhealthy.**
