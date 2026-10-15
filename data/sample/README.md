# Sentinel Sample Data

A small set of **synthetic** FHIR resources generated with [Synthea](https://github.com/synthetichealth/synthea). It does not contain real patient information.

| File | Resources | What a record is |
| --- | --- | --- |
| `Patient.ndjson` | 5 | A person |
| `Encounter.ndjson` | 25 | A visit or healthcare interaction |
| `Observation.ndjson` | 39 | A measurement, assessment or recorded fact |

Each line is one FHIR resource as JSON (NDJSON).

## How the files relate

The sample is referentially coherent: every Encounter refers to one of the Patients, and every Observation refers to one of the Patients and one of the Encounters. These counts and references were checked against the files.

## Why it is included

It lets you look at what Sentinel's input data looks like without running Synthea or connecting to Google Cloud. It is for exploration and examples; the automated tests and the monitor do not read it.

The data Sentinel actually streams is generated fresh by Synthea at run time (into `data/replay/`, which Git ignores), and the much larger historical dataset used for baselines is not stored in this repository.
