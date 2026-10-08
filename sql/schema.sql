-- ------------------------------------------------------------
-- 1) resources
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS resources (
    id             SERIAL PRIMARY KEY,
    resource_type  TEXT NOT NULL UNIQUE
);

-- v1 starts with Observation. Add Encounter / Patient here later.
INSERT INTO resources (resource_type)
VALUES ('Observation')
ON CONFLICT (resource_type) DO NOTHING;


-- ------------------------------------------------------------
-- 2) quality_metrics
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quality_metrics (
    id            BIGSERIAL PRIMARY KEY,
    resource_id   INTEGER NOT NULL REFERENCES resources (id),
    window_start  TIMESTAMPTZ NOT NULL,
    window_end    TIMESTAMPTZ NOT NULL,
    metric_name   TEXT NOT NULL,
    field_name    TEXT NULL,                    -- NULL for whole-record metrics
    metric_value  DOUBLE PRECISION NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT now(),

    -- Idempotent writes: same resource + window + metric + field exists only once.
    -- NULLS NOT DISTINCT => two NULL field_names count as equal.
    CONSTRAINT uq_quality_metrics_resource_window_metric_field
        UNIQUE NULLS NOT DISTINCT (resource_id, window_start, metric_name, field_name)
);

CREATE INDEX IF NOT EXISTS idx_quality_metrics_window_end
    ON quality_metrics (window_end DESC);


-- ------------------------------------------------------------
-- 3) baseline_metrics
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS baseline_metrics (
    id               BIGSERIAL PRIMARY KEY,
    resource_id      INTEGER NOT NULL REFERENCES resources (id),
    metric_name      TEXT NOT NULL,
    field_name       TEXT NULL,
    baseline_value   DOUBLE PRECISION NOT NULL,
    lower_threshold  DOUBLE PRECISION NULL,
    upper_threshold  DOUBLE PRECISION NULL,
    calculated_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_baseline_metrics_lookup
    ON baseline_metrics (resource_id, metric_name, field_name, calculated_at DESC);


-- ------------------------------------------------------------
-- 4) schema_history
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_history (
    id             BIGSERIAL PRIMARY KEY,
    resource_id    INTEGER NOT NULL REFERENCES resources (id),
    observed_at    TIMESTAMPTZ NOT NULL,
    field_name     TEXT NOT NULL,
    observed_type  TEXT NULL,
    previous_type  TEXT NULL,
    change_type    TEXT NOT NULL,

    CONSTRAINT chk_schema_history_change_type
        CHECK (change_type IN ('added', 'removed', 'type_changed'))
);

CREATE INDEX IF NOT EXISTS idx_schema_history_field
    ON schema_history (resource_id, field_name, observed_at DESC);


-- ------------------------------------------------------------
-- 5) incidents
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS incidents (
    id                  BIGSERIAL PRIMARY KEY,
    resource_id         INTEGER NOT NULL REFERENCES resources (id),
    detected_at         TIMESTAMPTZ NOT NULL,
    incident_type       TEXT NOT NULL,
    metric_name         TEXT NULL,
    field_name          TEXT NULL,
    observed_value      DOUBLE PRECISION NULL,
    baseline_value      DOUBLE PRECISION NULL,
    severity            TEXT NOT NULL,
    status              TEXT DEFAULT 'open',
    message             TEXT,
    quality_metric_id   BIGINT NULL REFERENCES quality_metrics (id),
    baseline_metric_id  BIGINT NULL REFERENCES baseline_metrics (id),
    schema_change_id    BIGINT NULL REFERENCES schema_history (id),

    CONSTRAINT chk_incidents_type
        CHECK (incident_type IN ('null_spike', 'type_change', 'volume_drop', 'schema_change')),
    CONSTRAINT chk_incidents_severity
        CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    CONSTRAINT chk_incidents_status
        CHECK (status IN ('open', 'acknowledged', 'resolved'))
);

CREATE INDEX IF NOT EXISTS idx_incidents_status_detected
    ON incidents (status, detected_at DESC);


