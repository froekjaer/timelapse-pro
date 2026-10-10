-- TimeLapse Pro - v40 user ↔ customer membership (many-to-many)
-- Peter (2026-10-10): a user can be attached to several customers; the role
-- (users.role) is global for the user and applies to every attached customer.
-- Only super_admin has implicit global access. See
-- Dokumentation/MIGRATION_PLAN_USER_CUSTOMERS_v40.md.
--
-- The Headend applies the same steps itself at startup (create_tables() +
-- services.user_customers.backfill_user_customers), so running this file by
-- hand is optional. Both are idempotent.

CREATE TABLE IF NOT EXISTS user_customers (
    user_id     INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    customer_id VARCHAR(36) NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ DEFAULT now(),
    created_by  VARCHAR(100),
    PRIMARY KEY (user_id, customer_id)
);
CREATE INDEX IF NOT EXISTS ix_user_customers_customer_id ON user_customers (customer_id);

-- Backfill from the legacy single-customer column. users.customer_id stays
-- (legacy mirror: the sole membership, else NULL) so a rollback to the
-- previous release keeps single-customer users working.
INSERT INTO user_customers (user_id, customer_id, created_by)
SELECT u.id, u.customer_id, 'backfill:users.customer_id'
  FROM users u
 WHERE u.customer_id IS NOT NULL
   AND EXISTS (SELECT 1 FROM customers c WHERE c.id = u.customer_id)
   AND NOT EXISTS (SELECT 1 FROM user_customers m WHERE m.user_id = u.id AND m.customer_id = u.customer_id);
