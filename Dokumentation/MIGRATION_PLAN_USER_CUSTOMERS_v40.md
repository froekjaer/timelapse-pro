# Migration plan — v40 user ↔ customer membership (many-to-many)

**Status:** proposal, not applied to production. Belongs to the PR "central
authorization model with many-to-many customers" (2026-10-10, Claude).
Production data and pre-check results are not recorded here (public
repository); they are reported to Peter directly.

## Model

| Role | Access |
|---|---|
| `super_admin` | Global — every customer (the only role with implicit global access) |
| `admin` | Administrator rights for every attached customer |
| `operator` | Operational rights for every attached customer |
| `viewer` | Read rights for every attached customer |
| any non-super_admin role without customers | No customer data |

The role is global per user (`users.role`); the customer attachments are
many-to-many (`user_customers`). Customer-specific roles do not exist in the
current architecture (no per-customer role column or table anywhere in
`database.py`, the migrations or the user API) and are not introduced here.

`users.customer_id` is kept as a **legacy mirror**: it holds the sole
membership when a user has exactly one, otherwise NULL. It is written only by
`services.user_customers.set_user_customers()`, together with the
memberships. Authorization reads the memberships plus this mirror
(`tenant_scope.user_customer_ids`); the mirror can only ever name one of the
user's own customers and never grants global access.

## Pre-checks (read-only, before deployment)

```sql
-- non-super_admin users without a customer: they lose all customer data
SELECT username, role, is_active FROM users WHERE role <> 'super_admin' AND customer_id IS NULL;
-- users whose customer no longer exists (backfill skips them)
SELECT username FROM users u WHERE customer_id IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM customers c WHERE c.id = u.customer_id);
-- memberships the backfill will create
SELECT role, count(*) FROM users u WHERE customer_id IS NOT NULL
   AND EXISTS (SELECT 1 FROM customers c WHERE c.id = u.customer_id) GROUP BY role;
-- field staff whose SSH keys are replicated to Edges (replication follows the new model)
SELECT username, role, customer_id IS NOT NULL AS has_customer, field_role FROM users
 WHERE field_role IN ('installer','technician') AND is_active;
```

Any active admin/operator/viewer in the first query must be given customers
(or made super_admin) **before** the deploy, or they lose access.

## Deployment

1. Merge in the agreed order (see HANDOVER_LOG): PR A (update approvals) →
   this PR → #297 rebased.
2. Normal governed Headend deploy. At startup `create_tables()` creates
   `user_customers`, and `backfill_user_customers()` inserts one membership
   per user from `users.customer_id`. Optionally apply
   `headend/migrations/v40_user_customers.sql` by hand first; both are
   idempotent.
3. Verify (read-only): the number of memberships equals the number of users
   with an existing `customer_id`; log in as each role and confirm the
   customer list matches the user's memberships.

## Rollback

1. Redeploy the previous release. It ignores `user_customers` and reads
   `users.customer_id`, which still holds every single-customer user's
   customer. Users with several customers have `customer_id = NULL` and are
   treated by the old code as "global" admins. **Before** rolling back, set
   their `customer_id` to one customer or deactivate them (query:
   `SELECT user_id FROM user_customers GROUP BY user_id HAVING count(*) > 1`).
2. Optional cleanup once the rollback is final: `DROP TABLE user_customers;`
   (the data can be rebuilt from `users.customer_id` only for single-customer
   users, so keep the table until the decision is final).
