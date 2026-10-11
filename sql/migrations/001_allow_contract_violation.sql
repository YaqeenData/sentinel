-- Allow contract-validation incidents in the incidents table.
-- schema.sql already includes this for new databases; run this once on existing ones.

ALTER TABLE incidents DROP CONSTRAINT IF EXISTS chk_incidents_type;

ALTER TABLE incidents ADD CONSTRAINT chk_incidents_type
    CHECK (incident_type IN (
        'null_spike', 'type_change', 'volume_drop', 'schema_change',
        'numeric_drift', 'categorical_drift', 'contract_violation'
    ));