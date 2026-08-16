# Update Authority Security Contract — H-1/H-2/H-3 closure

Status: Proposed implementation evidence for review.

This slice establishes explicit authority for both update delivery and update reporting. Delivery uses one canonical scope/environment predicate; reporting is bound to the durable target ledger, with scope resolution allowed only to establish the initial target binding.

The authority model binds the following dimensions together:

- authenticated device identity,
- explicit target-device narrowing where present,
- update scope (`global`, `customer`, `site`, `device`),
- device/customer/site relationship,
- update environment versus Edge environment,
- durable per-device `UpdateTarget` deployment state.

Security properties:

1. An authenticated Edge that is not an authorized target MUST receive HTTP 403 when attempting to report progress or terminal status for the update.
2. Customer- and site-scoped approved updates MUST be deliverable to devices that actually belong to that customer/site.
3. Test/LAB/R&D updates MUST NOT be returned to production Edges. Production updates MUST NOT be returned to test/LAB/R&D Edges.
4. An explicit `target_device_ids` list narrows authorization but MUST NOT bypass environment isolation.
5. Missing/unknown Edge environment fails closed for policy delivery.
6. Once an `UpdateTarget` exists, report authorization remains bound to that durable target even if the device is later removed/decommissioned from the live CMDB during rollout.
7. A first report without an existing target row is accepted only if current scope/target resolution proves that device is an intended target.

This closes the current-main instances of z.ai update-flow findings H-1, H-2 and H-3 without changing credentials, GPIO, capture data, artifact cryptography or deployment mechanics.
