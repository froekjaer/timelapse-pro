CREATE TABLE IF NOT EXISTS customer_risk_inputs (
    id BIGSERIAL PRIMARY KEY,
    customer_id VARCHAR(36) NOT NULL,
    monthly_service_price NUMERIC(14,2) NOT NULL CHECK (monthly_service_price > 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'DKK',
    effective_from DATE NOT NULL,
    effective_to DATE NULL,
    source VARCHAR(100) NOT NULL DEFAULT 'customer_contract',
    note TEXT NULL,
    validated_by VARCHAR(100) NOT NULL,
    validated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT customer_risk_inputs_dates CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE INDEX IF NOT EXISTS ix_customer_risk_inputs_customer
    ON customer_risk_inputs (customer_id, effective_from DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_customer_risk_inputs_active
    ON customer_risk_inputs (customer_id) WHERE effective_to IS NULL;
