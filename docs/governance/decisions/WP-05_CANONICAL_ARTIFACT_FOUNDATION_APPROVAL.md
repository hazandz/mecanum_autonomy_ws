# WP-05 Canonical Artifact Foundation — Approval Record

**Record state:** `APPROVED_DECISION_CANDIDATE_PENDING_INDEPENDENT_AUDIT_AND_CANONICAL_ACTIVATION`
**Work package:** `WP-05-CANONICAL-ARTIFACT-FOUNDATION`
**Candidate base:** `integration/implementation@56815516d9a9d000a7b6e41e5290e96bbed7286b`
**Candidate branch:** `wp-05-canonical-artifact-foundation-integration`

## 1. Approved source and decision

The Project Owner/User decision authorizes preparation of this WP-05 canonical-integration candidate.

- **Exact decision:** `USER_DECISION: APPROVED_FOR_WP05_CANONICAL_ARTIFACT_FOUNDATION_PREPARATION`
- **Approved packet branch:** `wp-05-artifact-foundation-decision-packet-56815516`
- **Approved packet commit:** `72e47bd1c0a80188abc96f8575d5b345e3767e4d`
- **Approved packet SHA-256:** `b6a3cc428b82d92c437c9b0809f50268d3f409f82d7715c4494c3d27f07bf8d5`
- **Decision scope:** prepare exactly one governance-documentation candidate recording the approved WP-05 map, scenario, and hardware artifact-foundation boundaries in this record, the Canonical Source Registry, and an append-only Progress Ledger entry. The packet is the decision source; it does not select a concrete artifact instance.

The decision adopts the candidate boundaries in the approved packet: canonical map root `artifacts/maps/<map_id>/` with `map_content_hash` limited to `map.yaml` and `map.pgm`; canonical scenario root `artifacts/scenarios/<scenario_id>/scenario.json` with the `RFC8785_JCS_UTF8` convention; evaluator/oracle-only `GT_ODOM_2D` and raw-Ground-Truth isolation; and fail-closed hardware provenance retaining unavailable `TBD_MEASURED`/null values, `approval_status: DRAFT`, and `motor_enable_allowed: false`. No concrete map/scenario/hardware values or approvals are selected.

## 2. Candidate activation boundary

This record and its Registry references are **not active on this candidate branch**. Activation requires both:

1. an independent static audit that passes for the exact candidate commit; and
2. a separately authorized fast-forward of that exact audited commit to `integration/implementation`, followed by verification that the remote integration ref points to it.

The candidate commit SHA is identified by Git history after commit and is intentionally not self-embedded here. Until the activation conditions are met, this record is a review candidate only. This candidate does not close WP-05, transition any WP status/dependency, or grant code, runtime, simulation, HIL, measurement, hardware, motor-enable, deployment, or `deploy_real` authorization. `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`.
