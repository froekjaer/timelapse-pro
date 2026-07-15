CREATE TABLE IF NOT EXISTS customer_risk_profiles (
    id BIGSERIAL PRIMARY KEY,
    customer_id VARCHAR(36) NOT NULL,
    version INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'submitted'
        CHECK (status IN ('submitted','validated','rejected','superseded')),
    product_value_dkk NUMERIC(16,2) NULL CHECK (product_value_dkk >= 0),
    daily_downtime_cost_dkk NUMERIC(16,2) NULL CHECK (daily_downtime_cost_dkk >= 0),
    recreation_cost_dkk NUMERIC(16,2) NULL CHECK (recreation_cost_dkk >= 0),
    contractual_penalty_dkk NUMERIC(16,2) NULL CHECK (contractual_penalty_dkk >= 0),
    business_dependency INTEGER NOT NULL CHECK (business_dependency BETWEEN 1 AND 5),
    availability_impact INTEGER NOT NULL CHECK (availability_impact BETWEEN 1 AND 5),
    integrity_impact INTEGER NOT NULL CHECK (integrity_impact BETWEEN 1 AND 5),
    confidentiality_impact INTEGER NOT NULL CHECK (confidentiality_impact BETWEEN 1 AND 5),
    recovery_objective_hours DOUBLE PRECISION NULL CHECK (recovery_objective_hours >= 0),
    max_tolerable_downtime_hours DOUBLE PRECISION NULL CHECK (max_tolerable_downtime_hours >= 0),
    personal_data_level VARCHAR(30) NOT NULL DEFAULT 'none',
    assumptions TEXT NULL,
    submitted_by VARCHAR(100) NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    validated_by VARCHAR(100) NULL,
    validated_at TIMESTAMPTZ NULL,
    validation_note TEXT NULL,
    UNIQUE (customer_id, version)
);

CREATE INDEX IF NOT EXISTS ix_customer_risk_profiles_customer_status
    ON customer_risk_profiles (customer_id, status, version DESC);
