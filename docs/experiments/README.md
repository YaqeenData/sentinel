# Running Sentinel Experiments

Sentinel uses synthetic healthcare data, so failures can be introduced deliberately without affecting real systems or patients. Controlled experiments let us check that Sentinel responds when the stream becomes unhealthy, and notices when it recovers.

```text
Healthy stream
      ↓
Inject a known problem
      ↓
Sentinel evaluates the monitoring window
      ↓
Incident opens
      ↓
Inspect evidence in the dashboard
      ↓
Restore healthy data
      ↓
Sentinel detects recovery
      ↓
Incident resolves
```

## Before you start

Follow **Getting started** in the [root README](../../README.md) until these are running:

1. Kafka and PostgreSQL (`docker compose up -d`, tables created)
2. The monitor: `poetry run python scripts/run_monitor.py`
3. The live stream: `poetry run python -m sentinel.streaming.replay`
4. Optionally the dashboard: `poetry run streamlit run src/sentinel/dashboard/app.py`

Let the stream run healthy for several minutes first. The monitor needs a few healthy 60-second windows before it judges volume and missingness.

## What can be injected

The injection switches are changed while the replay keeps running. Failures are applied to the raw FHIR records before they reach Kafka, so the monitor sees them as it would see a real upstream problem.

| Kind | What it does to the stream |
| --- | --- |
| `categorical` | Changes part of the smoking-status Observations to a different category (category drift). This is the default kind |
| `nulls` | Sends about 30% of the monitored numeric readings without a value |
| `volume` | Sends only about 25% of the usual Observations |
| `numeric` | Shifts heart rate, systolic blood pressure and glucose values upward |
| `contract` | Breaks about 10% of Observations (a number sent as text, a missing patient reference, or an invalid status) |
| `patient` | Breaks the contract of a share of Patient records |
| `encounter` | Moves part of the ambulatory (`AMB`) Encounters to emergency (`EMER`), a class drift |
| `encounter_contract` | Breaks the contract of a share of Encounter records |

The shares above are constants in `src/sentinel/injection/live_failures.py` and `config/monitoring.yaml`.

## `scripts/set_injection.py`

Switch one failure on or off by hand, or check what is on.

```text
python scripts/set_injection.py on   [kind]
python scripts/set_injection.py off  [kind]
python scripts/set_injection.py status

kind: categorical, nulls, volume, numeric, contract, patient,
      encounter, encounter_contract, or all   (default: categorical)
```

```bash
poetry run python scripts/set_injection.py status
poetry run python scripts/set_injection.py on volume
poetry run python scripts/set_injection.py off volume
poetry run python scripts/set_injection.py off all
```

**Expected result:** the command prints each kind as ON or OFF. While a kind is ON, the matching check should open an incident within a few windows; after you switch it OFF and healthy windows return, the incident should resolve. The switch state is stored in `data/replay/injection_state.json` (ignored by Git).

## `scripts/run_scenario.py`

Runs a timed sequence of failures for you by flipping the same switches. It needs the monitor and replay running in other terminals. Each failure runs on its own, so every incident has one clear cause.

```text
python scripts/run_scenario.py [--warmup MIN] [--on MIN] [--recover MIN]
                               [--kinds KIND [KIND ...]] [--loop]
```

| Flag | Meaning | Default |
| --- | --- | --- |
| `--warmup` | Healthy minutes before the first failure | 25 |
| `--on` | Minutes each failure stays on | 4 |
| `--recover` | Healthy minutes after each failure | 4 |
| `--kinds` | Which failures to run, in order. Choices: `volume`, `nulls`, `numeric`, `contract`, `patient`, `encounter`, `encounter_contract` | all of them |
| `--loop` | Repeat until stopped with `Ctrl+C` | off |

```bash
# One failure, shorter timings
poetry run python scripts/run_scenario.py --kinds volume --warmup 8 --on 4 --recover 4

# The full sequence
poetry run python scripts/run_scenario.py
```

The script switches every failure off when it exits. It does not touch the `categorical` kind.

## `scripts/run_experiment.py`

A self-contained **categorical drift** experiment that takes no arguments. It reads the Kafka stream itself, waits for enough healthy smoking-status data, then enables its own injection and stores an incident in PostgreSQL when drift is detected.

```bash
poetry run python scripts/run_experiment.py
```

Run it **instead of** `run_monitor.py`, not alongside it: both read Kafka with the same default consumer group (`KAFKA_CONSUMER_GROUP`). The replay must still be running. **Expected result:** it prints the healthy phase, then `DRIFT DETECTED`, then the stored incident ID, and exits.

## Other checks

- `scripts/check_contract_stream.py [seconds]` runs only the contract check on the live Kafka stream (add `--save` to store incidents).
- `scripts/check_contract_gcs.py [rows_per_window]` runs the contract check on historical data in Google Cloud Storage; it needs `GCP_PROJECT_ID`, `GCS_BUCKET` and Google credentials.

## Recommended demo flow

1. Start everything as described in the root README (infrastructure, monitor, replay, dashboard).
2. Wait about 5–10 minutes so the dashboard shows healthy windows.
3. Turn on one failure:

   ```bash
   poetry run python scripts/set_injection.py on volume
   ```

4. Watch the **Overview** and **Incidents** pages until an incident opens, and read its evidence.
5. Restore healthy data:

   ```bash
   poetry run python scripts/set_injection.py off volume
   ```

6. Watch the incident resolve once healthy windows return.
7. Repeat with another kind, for example `nulls` or `contract`.
