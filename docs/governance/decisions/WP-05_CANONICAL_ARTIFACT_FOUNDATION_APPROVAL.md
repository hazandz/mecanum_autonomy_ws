# WP-05 Canonical Artifact Foundation — Approval Record

**Record state:** `APPROVED_DECISION_CANONICALIZED_ON_INTEGRATION`
**Work package:** `WP-05-CANONICAL-ARTIFACT-FOUNDATION`
**Candidate base:** `integration/implementation@34dbb9d17bb5863880838b0c49acac81b8b6dc48`
**Candidate branch:** `wp-05-canonical-artifact-foundation-integration-34dbb9d`

## 1. Approved source and decision

The Project Owner/User decision authorizes preparation of this WP-05 canonical-integration candidate.

- **Exact decision:** `USER_DECISION: APPROVED_FOR_WP05_CANONICAL_ARTIFACT_FOUNDATION_PREPARATION`
- **Approved packet branch:** `wp-05-artifact-foundation-decision-packet-56815516`
- **Approved packet commit:** `72e47bd1c0a80188abc96f8575d5b345e3767e4d`
- **Approved packet SHA-256:** `b6a3cc428b82d92c437c9b0809f50268d3f409f82d7715c4494c3d27f07bf8d5`
- **Decision scope:** prepare exactly one governance-documentation candidate recording the approved WP-05 map, scenario, and hardware artifact-foundation boundaries in this record, the Canonical Source Registry, and an append-only Progress Ledger entry. The packet is the decision source; it does not select a concrete artifact instance.

The decision adopts the candidate boundaries in the approved packet: canonical map root `artifacts/maps/<map_id>/` with `map_content_hash` limited to `map.yaml` and `map.pgm`; canonical scenario root `artifacts/scenarios/<scenario_id>/scenario.json` with the `RFC8785_JCS_UTF8` convention; evaluator/oracle-only `GT_ODOM_2D` and raw-Ground-Truth isolation; and fail-closed hardware provenance retaining unavailable `TBD_MEASURED`/null values, `approval_status: DRAFT`, and `motor_enable_allowed: false`. No concrete map/scenario/hardware values or approvals are selected.

## 2. Previous candidate audit and refresh

The previous candidate at branch `wp-05-canonical-artifact-foundation-integration`, commit `28e84ea2758ef8a2f252b3da3e94114bb2705003` (parent `56815516d9a9d000a7b6e41e5290e96bbed7286b`), received the following focused audit results as recorded in the Project Owner/User instruction: `CANDIDATE_INTEGRITY: PASS`; `APPROVAL_RECORD_ACCURACY: PASS`; `MAP_HASH_BOUNDARY: PASS`; `SCENARIO_AND_GT_ISOLATION: PASS`; `HARDWARE_FAIL_CLOSED_BOUNDARY: PASS`; `REGISTRY_AND_LEDGER_CONSISTENCY: PASS`; `WP_STATUS_AND_AUTHORIZATION_BOUNDARY: PASS`; `READINESS_FOR_CANONICAL_INTEGRATION: PASS`. That candidate is stale because `integration/implementation` advanced to `34dbb9d17bb5863880838b0c49acac81b8b6dc48` with WP-04 integration. It is retained unchanged as prior audit evidence and is not the candidate proposed for integration now.

At review time, this refreshed candidate carried forward only the audited WP-05 foundation content and updated its candidate provenance/activation state for the new exact base. It was then pending focused independent re-audit.

## 3. Candidate activation boundary at review time

At the time this refreshed candidate was prepared, this record and its Registry references were **not active on the candidate branch**. Activation required all of the following for the exact candidate commit:

1. focused independent re-audit passes;
2. the Project Owner/User separately authorizes integration of that exact audited commit; and
3. that exact commit is fast-forwarded to `integration/implementation`, followed by verification that the remote integration ref points to it.

The candidate under review was branch `wp-05-canonical-artifact-foundation-integration-34dbb9d`, based on `34dbb9d17bb5863880838b0c49acac81b8b6dc48`. Its commit SHA was intentionally not self-embedded in that candidate record.

## 4. Activation correction — exact integrated candidate

The Project Owner/User supplied the focused audit verdict for exact candidate `d89f5187c792932e6e77f7ff8db5045f9cce70ed`: all listed audit categories passed, with no correction required. The Project Owner/User authorized the exact candidate for fast-forward integration. The delivery record confirms that commit was fast-forwarded from `34dbb9d17bb5863880838b0c49acac81b8b6dc48` to `integration/implementation`, and the remote integration ref was verified at `d89f5187c792932e6e77f7ff8db5045f9cce70ed`.

Accordingly, this foundation decision and its Registry references are active on `integration/implementation` at that exact commit. WP-05 remains open; no WP status/dependency transition or code, runtime, simulation, HIL, measurement, hardware, motor-enable, deployment, or `deploy_real` authorization is granted. `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`.
