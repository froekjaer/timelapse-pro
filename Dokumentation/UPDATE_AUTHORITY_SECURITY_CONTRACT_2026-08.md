# Update Authority Security Contract — H-1/H-2/H-3 closure

Status: Proposed implementation evidence for review.

This slice makes one canonical predicate authoritative for whether an Edge may receive or report an update. The predicate binds all of the following dimensions together:

- authenticated device identity,
- explicit target-device narrowing where present,
- update scope (`global`, `customer`, `site`, `device`),
- device/customer/site relationship,
- update environment versus Edge environment.

Security properties:

1. An authenticated Edge that is not an authorized target MUST receive HTTP 403 when attempting to report progress or terminal status for the update.
2. Customer- and site-scoped approved updates MUST be deliverable to devices that actually belong to that customer/site.
3. Test/LAB/R&D updates MUST NOT be returned to production Edges. Production updates MUST NOT be returned to test/LAB/R&D Edges.
4. An explicit `target_device_ids` list narrows authorization but MUST NOT bypass environment isolation.
5. Missing/unknown Edge environment fails closed.
6. Policy delivery and report ingestion MUST use the same canonical authority predicate.

This closes the current-main instances of z.ai update-flow findings H-1, H-2 and H-3 without changing credentials, GPIO, capture data, artifact cryptography or deployment mechanics.
