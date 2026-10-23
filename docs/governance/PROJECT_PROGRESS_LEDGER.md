# Project Progress Ledger — Mecanum Nav2 DRL

## Ledger rules

- This ledger is append-only.
- Historical entries are never edited or deleted.
- A correction creates a new entry with supersedes.
- A Git commit, source presence, build or unit test never upgrades runtime/HIL/real-robot evidence by itself.
- The newest relevant entry must be read before a new work package starts.

## Entries

### BASELINE-20261002

| Field | Value |
|---|---|
| Date | 2026-10-02 |
| Baseline branch | baseline/architecture-frozen-20261002 |
| Commit | 86beff623dba3683f643c851a4a1374c635178b3 |
| Scope | Architecture-frozen baseline source/static artifact snapshot |
| Evidence status | IMPLEMENTED_OFFLINE_ONLY |
| Runtime/HIL/real status | RUNTIME_NOT_APPROVED |
| Notes | Baseline is immutable; it must not receive new commits. |

### WP-00F-LOCAL-GITHUB-PUSH-PROBE

| Field | Value |
|---|---|
| Date | 2026-10-02 |
| Branch | probe/github-push-20261002 |
| Commit | dd1e177e948fea17e6124a85eac5b9907470ef2a |
| Scope | Empty-commit GitHub push connectivity probe |
| Evidence status | IMPLEMENTED_OFFLINE_ONLY |
| Runtime/HIL/real status | RUNTIME_NOT_APPROVED |
| Notes | No source file changed; branch is not an implementation base. |

### WP-00G-AGENTS-GIT-DELIVERY

| Field | Value |
|---|---|
| Date | 2026-10-02 |
| Branch | wp-00g-agents-git-delivery |
| Commit | 99de9d1839b0d5b1a2da95fc0958b49bac2483a0 |
| Scope | Git delivery/GitHub governance in AGENTS.md only |
| Evidence status | IMPLEMENTED_OFFLINE_ONLY |
| Runtime/HIL/real status | RUNTIME_NOT_APPROVED |
| Notes | Reviewed branch; it becomes the initial integration commit after explicit topology setup. |

### WP-00H-EXECUTION-GOVERNANCE

| Field | Value |
|---|---|
| Date | 2026-10-02 |
| Branch | wp-00h-execution-governance |
| Base commit | 99de9d1839b0d5b1a2da95fc0958b49bac2483a0 |
| Scope | Create execution plan, progress ledger, canonical source registry and execution-governance rule |
| Evidence status | PENDING_REVIEW |
| Runtime/HIL/real status | RUNTIME_NOT_APPROVED |
| Notes | This entry becomes IMPLEMENTED_OFFLINE_ONLY only after separate architecture audit of the resulting commit. |

### WP-00L-INTEGRATE-EXECUTION-GOVERNANCE

| Field | Value |
|---|---|
| Date | 2026-10-02 |
| Work branch | wp-00l-integrate-execution-governance |
| Integration base | 99de9d1839b0d5b1a2da95fc0958b49bac2483a0 |
| Candidate branch | wp-00k-governance-registry-repair |
| Candidate commit | 28848315bcdedc96fbdc703af0a9c8168a3bd69d |
| Integration commit | 07d71f78ba9b37b3103035ab3d9cf506b70c6e87 |
| Scope | Integrate architecture-audited execution governance into integration line |
| Evidence status | IMPLEMENTED_OFFLINE_ONLY |
| Runtime/HIL/real status | RUNTIME_NOT_APPROVED |
| Supersedes | WP-00H-EXECUTION-GOVERNANCE pending-review state |
| Notes | Governance is active on integration line; no runtime, HIL or real-robot evidence is created. |

### WP-01I-INTEGRATE-REPOSITORY-HYGIENE

| Field | Value |
|---|---|
| Date | 2026-10-02 |
| Work branch | wp-01i-integrate-repository-hygiene |
| Integration base | b4927775bb54754e0914a4cdd90748e992fedefe |
| Candidate branch | wp-01-repository-hygiene-untrack-cache |
| Candidate commit | 96790e3cf57514df39a15bb92bbd826adb00b99f |
| Scope | Integrate approved untracking of generated/cache Git entries and exact ignore rules |
| Evidence status | IMPLEMENTED_OFFLINE_ONLY |
| Runtime/HIL/real status | RUNTIME_NOT_APPROVED |
| Notes | Git tracking only; all untracked generated/cache files remain physically present. Historical artifacts, source, firmware and geometry assets are unchanged. |

### WP-02I-INTEGRATE-CANONICAL-SOURCE-SELECTION

| Field | Value |
|---|---|
| Date | 2026-10-02 |
| Work branch | wp-02i-integrate-canonical-source-selection |
| Integration base | 6094650e799bb66cdcc9f923a7a81c5acf44f28c |
| Candidate branch | wp-02-canonical-source-selection |
| Candidate commit | eed009d926e721ed37f27f675bbbe27e04cc14fe |
| Scope | Integrate approved V3 canonical config-input boundary and legacy exclusion rules |
| Evidence status | IMPLEMENTED_OFFLINE_ONLY |
| Runtime/HIL/real status | RUNTIME_NOT_APPROVED |
| Notes | V3 is approved only for core/offline config input. Runtime profile approval, PPO, Gazebo, HIL, deploy_sim and deploy_real remain unapproved. |

### PEP-001-REV-0.2.0-GOVERNANCE-CANDIDATE

| Field | Value |
|---|---|
| Date | 2026-10-04 |
| Work branch | wp-04-pep-amendment-governance |
| Base commit | afa23732fb6a74beafceec21c2319a52f5f87b3 |
| Scope | Candidate PEP revision 0.2.0: narrow WP-04 first deliverable to non-integrated V3 immutable contract primitives |
| Evidence status | PENDING_REVIEW |
| Runtime/HIL/real status | RUNTIME_NOT_APPROVED |
| Notes | No code or runtime authorization. WP-04 remains BLOCKED_BY_CONTRACT. Semantic bundle S2 rev.2, Observation Input Contract rev.6 and V3 Observation Boundary rev.7 remains a required recorded gate. Proposal evidence: docs-v3-observation-contract-import at d3ca85536e35b38f7f3dffcf1dfd1bc16983aae9. |

### WP-04I-INTEGRATE-PEP-001-REV-0.2.0-GOVERNANCE

| Field | Value |
|---|---|
| Date | 2026-10-04 |
| Work branch | wp-04i-integrate-pep-amendment-governance |
| Integration base | afa23732fb6a74beafceec21c2319a52f5f87b3 |
| Candidate branch | wp-04-pep-amendment-governance |
| Candidate commit | 1b4a86b15fdefcf39389a132f57c7e00c62e65fd |
| Scope | Integrate PEP-001 revision 0.2.0 governance amendment for the constrained WP-04 V3 primitive deliverable |
| Evidence status | IMPLEMENTED_OFFLINE_ONLY |
| Runtime/HIL/real status | RUNTIME_NOT_APPROVED |
| Supersedes | PEP-001-REV-0.2.0-GOVERNANCE-CANDIDATE pending-review state |
| Notes | Governance integration only. WP-04 remains BLOCKED_BY_CONTRACT; code and runtime remain unauthorized. |

### WP-04I-QOS5-ACR7-CANONICAL-BUNDLE

| Field | Value |
|---|---|
| Date | 2026-10-06 |
| Work branch | wp-04-qos5-acr7-canonical-bundle-integration |
| Integration base | f8933bcff2bb30b1dad57d71d91678e36746326f |
| Scope | Canonically record the user-approved QoS Topic Contract rev.5 / ACR rev.7 bundle and its approval/change-control record; governance and contract documents only |
| Approval record | docs/governance/decisions/QOS_REVISION_5_ACR_REVISION_7_BUNDLE_APPROVAL.md |
| QoS artifact | docs/RECEIPT_TOPIC_QOS_CONTRACT.md; rev.5; full-document SHA-256 9f87f4d09ec50aacf8c0cf69e11bff8bceb4219b8d09f68998288907afb8302b |
| ACR artifact | docs/ACR_V3_OBSERVATION_BOUNDARY_CLOSURE.md; rev.7; full-document SHA-256 cb111c84c3b8f7d1393256b4c15f28c5f0bcafa1d2a84dde08e2cb0cd823ce0f |
| Transport identity | mecanum.final-issued-receipt-topic-qos/v1; manifest SHA-256 a3bc1a965fc6885825ab961289fa4028862aa7af4b3f3156bc40542f7ee08f62 |
| Evidence status | IMPLEMENTED_OFFLINE_ONLY |
| Runtime/HIL/real status | RUNTIME_NOT_APPROVED |
| Notes | Records bundled user approval dated 2026-10-06; pre-approval draft labels are superseded for document authority/status only. Technical semantics and historical QoS rev.4 / ACR rev.6 approvals are unchanged. No WP-03 closure, dependency/status change, implementation eligibility, code authorization, or runtime authorization. Commit identity is available from Git history and is not self-embedded. |

### WP-02-CLOSE-CANONICAL-SOURCE-SELECTION

| Field | Value |
|---|---|
| Date | 2026-10-07 |
| Work package | WP-02-CANONICAL-CLOSURE-INTEGRATION |
| Work branch | wp-02-close-and-integrate-3f4a114 |
| Integration base | 3f4a1147d97143995d3cd9c56097a0fb414a40ca |
| Source candidate branch | wp-02-pep-closure-transition-candidate-3f4a114 |
| Source candidate commit | 6e962f3a14e60a017dd525a5fda9eed4f77cbe2a |
| Decision date and authority | 2026-10-07; explicit user decision in chat; approver role Project Owner/User |
| PEP revision | PEP-001 rev.0.3.0 |
| Transition | WP-02: BLOCKED_BY_GOVERNANCE -> CLOSED |
| Evidence basis | WP-02I-INTEGRATE-CANONICAL-SOURCE-SELECTION; IMPLEMENTED_OFFLINE_ONLY; V3 selection, legacy boundary, and source-registry enforcement at governance/source-selection level |
| Runtime/HIL/real status | RUNTIME_NOT_APPROVED |
| Dependency/status impact | WP-03 remains BLOCKED_BY_CONTRACT with its WP-02 and required-user-decisions dependencies; WP-04 remains BLOCKED_BY_CONTRACT with all existing dependencies unchanged |
| Notes | The PEP Ordered work packages table retains WP-02's historical Initial status BLOCKED_BY_GOVERNANCE and WP-03/WP-04 BLOCKED_BY_CONTRACT. This ledger entry records the separate authorized WP-02 transition only after canonical integration. It does not claim runtime, HIL, hardware, or physical-measurement evidence and grants no code/runtime authorization. The integration commit SHA is available from canonical Git history and the evidence export, not self-embedded in this entry. |

### WP-03-QOS6-ACR8-CANONICAL-BUNDLE-INTEGRATION-CANDIDATE

| Field | Value |
|---|---|
| Date | 2026-10-08 |
| Work package | WP-03-RECEIPT-INTERFACE-V2-CANONICAL-BUNDLE-INTEGRATION-CANDIDATE |
| Work branch | wp-03-qos6-acr8-canonical-bundle-integration-candidate |
| Integration base | 9a4c0d233e8237f01a04880fe99e8a3114528f4c |
| Approved source candidate | 8600f4c6b1bd58aa0f1976bf606dbd07b6594822 |
| User decision | 2026-10-08; Project Owner/User approved exact QoS6/ACR8 bundle and three technical target paths for canonical bundled integration |
| Approval record | docs/governance/decisions/QOS_REVISION_6_ACR_REVISION_8_BUNDLE_APPROVAL.md; SHA-256 4d740559f850f179387db802df845748068f75a21266fd1edb52402b2c72c529 |
| Contract artifacts | QoS revision 6 `4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022`; ACR revision 8 `03fef021f6b9731f811f83a5e53aae1c430bdc2ea76815a8ada416f1a5bf772c` |
| Interface pins | Receipt v2 schema `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`; dependency closure `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73`; transport v2 `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620` |
| Scope | Candidate canonical document/record integration: QoS6, ACR8, approved receipt `.msg`, closure and transport manifests, approval record, Registry selection, and this append-only Ledger entry |
| Candidate state | PENDING_REVIEW; candidate-branch tip and commit identity are available from Git history, not self-embedded |
| Runtime/HIL/real status | RUNTIME_NOT_APPROVED |
| Dependency/status impact | No transition. WP-03 and WP-04 remain BLOCKED_BY_CONTRACT; WP-04 dependency on WP-03 is unchanged. WP-02 remains CLOSED. |
| Notes | This entry records a review candidate only; its selections become active on `integration/implementation` only after the exact candidate is fast-forwarded. Historical QoS5/ACR7 approval and v1 pins are preserved. No PEP change, WP-03/WP-04 closure, implementation, code, ROSIDL generation/build, test, runtime, HIL, hardware, or deploy_real authorization is granted. |


### WP-03-CLOSE-OPEN-CONTRACTS

| Field | Value |
|---|---|
| Date | 2026-10-08 |
| Work package | `WP-03-CLOSURE-AND-SINGLE-INTEGRATION-CANDIDATE` |
| Work branch | `wp-03-close-and-integrate-once-2e7a2980` |
| Integration base | `2e7a2980cb75f0567182ea694c04328d7d8643e0` |
| Audited disposition source | `wp-03-decision-contract-reconciliation-2e7a2980@b234c2fe5831c1a0ea3c2b1805a5715773d6d2a6` |
| Audit report | `INDEPENDENT_FOCUSED_STATIC_AUDIT_WP03_DECISION_CONTRACT_RECONCILIATION_B234C2FE.md`; SHA-256 `7db8347459af8762da1b74afd99c765a9121e43c2453363049c3f00c0256110f`; `READINESS_FOR_CANONICAL_INTEGRATION: PASS` |
| PEP change control | PEP-001 rev.0.3.0 -> rev.0.4.0; initial statuses remain historical |
| Proposed transition | `WP-03: BLOCKED_BY_CONTRACT -> CLOSED`; effective only after the exact reviewed final candidate is fast-forwarded to `integration/implementation` and its remote ref is verified |
| Scope/evidence basis | Authorized D2 receipt, D3 collision/contact, map, scenario, hardware-intake and record-routing dispositions are recorded. Future obligations remain routed to PEP-001 WP-05 (canonical artifact provenance), WP-06/WP-09 (offline safety/final-publisher and task/contact work under existing dependencies), WP-11 (approved simulation runtime), and WP-12 (physical measurements/HIL); no such evidence is claimed here. |
| Dependency/status impact | WP-02 remains `CLOSED`; WP-04 remains `BLOCKED_BY_CONTRACT` and its dependency on WP-03 is unchanged. No other dependency/status transition is recorded. |
| Candidate content commit | Resolved by Git history for the exact candidate tip; not self-embedded. The audited source commit is identified above. |
| Runtime/HIL/real status | `RUNTIME_NOT_APPROVED` |
| Authorization | `CODE_AUTHORIZATION: NOT_GRANTED`; no ROS/ROSIDL, build, test, runtime, HIL, hardware operation, `deploy_real`, or deployment authorization. |
| Notes | This append-only entry is part of the review candidate. Before the PEP activation condition is met, canonical WP-03 remains `BLOCKED_BY_CONTRACT`; after the exact candidate is integrated and the remote ref verified, the transition is `CLOSED`. This record does not alter or supersede any historical Ledger entry. |


### WP-05-CANONICAL-ARTIFACT-FOUNDATION-REFRESH-CANDIDATE

| Field | Value |
|---|---|
| Date | 2026-10-09 |
| Work package | `WP-05-CANONICAL-ARTIFACT-FOUNDATION-INTEGRATION-CANDIDATE` |
| Candidate branch | `wp-05-canonical-artifact-foundation-integration-34dbb9d` |
| Integration base | `34dbb9d17bb5863880838b0c49acac81b8b6dc48` |
| Prior candidate | `wp-05-canonical-artifact-foundation-integration@28e84ea2758ef8a2f252b3da3e94114bb2705003`; parent `56815516d9a9d000a7b6e41e5290e96bbed7286b`; stale after WP-04 integration advanced the base |
| Prior audit | User-reported focused audit PASS: candidate integrity, approval-record accuracy, map hash boundary, scenario/GT isolation, hardware fail-closed boundary, Registry/Ledger consistency, WP status/authorization boundary, readiness for integration |
| Approved decision | `USER_DECISION: APPROVED_FOR_WP05_CANONICAL_ARTIFACT_FOUNDATION_PREPARATION` |
| Approved packet source | `wp-05-artifact-foundation-decision-packet-56815516@72e47bd1c0a80188abc96f8575d5b345e3767e4d`; packet SHA-256 `b6a3cc428b82d92c437c9b0809f50268d3f409f82d7715c4494c3d27f07bf8d5` |
| Scope | Refresh the already audited WP-05 governance content on the exact current integration base; decision record, pending-activation Registry references, and this append-only Ledger entry only. No concrete artifact values. |
| Candidate state | `PENDING_FOCUSED_INDEPENDENT_REAUDIT_AND_USER_INTEGRATION_AUTHORIZATION`; candidate commit SHA is resolved from Git history, not self-embedded. |
| Activation condition | Focused independent re-audit must pass, the Project Owner/User must separately authorize integration of the exact candidate commit, and that commit must then be fast-forwarded to `integration/implementation` with the remote ref verified. No integration occurs in this work package. |
| WP status/dependency impact | No transition or dependency change; WP-05 is not closed. WP-04 and all other statuses/dependencies remain unchanged. |
| Code/runtime/hardware impact | `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. No code, runtime, measurement, HIL, hardware approval, motor-enable, deployment, or physical evidence is created. |
| Evidence status | `DRAFT/PENDING_FOCUSED_INDEPENDENT_REAUDIT_AND_USER_DECISION`; governance/documentation candidate only. |
| Notes | This entry records refresh provenance and future activation conditions only. It does not activate the foundation decision, supersede prior Ledger entries, or claim canonical integration. |


### WP-05-FOUNDATION-ACTIVATION-STATUS-CORRECTION

| Field | Value |
|---|---|
| Work package | `WP-05-FOUNDATION-ACTIVATION-STATUS-CORRECTION` |
| Supersedes | `WP-05-CANONICAL-ARTIFACT-FOUNDATION-REFRESH-CANDIDATE`, only as to its pending activation state; prior provenance and audit history remain intact |
| Integrated foundation candidate | `wp-05-canonical-artifact-foundation-integration-34dbb9d@d89f5187c792932e6e77f7ff8db5045f9cce70ed` |
| Integration base and parent | `34dbb9d17bb5863880838b0c49acac81b8b6dc48` |
| Audit | Project Owner/User supplied focused independent audit verdict: all listed WP-05 candidate audit categories `PASS`; no correction required |
| User authorization and integration evidence | Project Owner/User authorized fast-forward of the exact audited candidate; delivery record confirms fast-forward to `integration/implementation` and remote ref verification at `d89f5187c792932e6e77f7ff8db5045f9cce70ed` |
| Foundation activation | The approved WP-05 artifact-foundation decision and Registry references are active on `integration/implementation` at the exact integrated candidate commit |
| WP status/dependency impact | WP-05 remains open and is not closed. No WP status or dependency changed; WP-04 remains `BLOCKED_BY_CONTRACT` with dependencies unchanged. |
| Authorization/evidence boundary | `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. No concrete map/scenario, measurement, code, runtime, HIL, hardware approval, motor enable, deployment, or physical evidence is created. |
| Correction candidate state | Pending focused independent audit of this status correction; this entry does not itself integrate the correction candidate or close WP-05. |
### WP-05-MAP-HASH-SERIALIZATION-RFC8785-CHANGE-CONTROL-CANDIDATE

| Field | Value |
|---|---|
| Date | 2026-10-09 |
| Work package | WP-05-MAP-HASH-SERIALIZATION-RFC8785-CHANGE-CONTROL |
| Integration base | c37a5bff9dd6cc32fc503cdd796b31720a58a616 |
| Candidate branch | wp-05-map-hash-serialization-rfc8785-change-control-c37a5bff |
| Source decision packet | wp-05-map-hash-serialization-decision-packet-c37a5bff@38e496dc985969cb0d6a2e421b1eb7363c9b5a1f; SHA-256 ee31375df185c124f82a1fc56ee0daa12b4aa93297d2c5fe2c6e6cb0cd353515 |
| User decision | USER_DECISION: APPROVED_FOR_WP05_MAP_HASH_SERIALIZATION_CHANGE_CONTROL; selects RFC 8785 JCS, UTF-8 without BOM or trailing newline, for the specified map-hash projection |
| Scope | Candidate clarification to Architecture §48 and pending-activation Registry note; no map artifact or source selection |
| Candidate state | PENDING_FOCUSED_INDEPENDENT_AUDIT_AND_SEPARATE_USER_INTEGRATION_AUTHORIZATION |
| Activation condition | The exact candidate must pass focused independent audit, receive separate Project Owner/User integration authorization, then be fast-forwarded to integration/implementation and remotely verified |
| WP status/dependency impact | No transition or dependency change. WP-05 remains open; WP-04 is unchanged. |
| Authorization/evidence boundary | CODE_AUTHORIZATION: NOT_GRANTED; RUNTIME_APPROVED: NOT_APPROVED. No map/scenario artifact, measurement, code, runtime, HIL, hardware approval or deployment authorization is created. |
| Notes | This entry is append-only and records a serialization change-control candidate only. It does not claim the Architecture clarification is active or that a map artifact exists. |


### WP-04-GATE-A-EXACT-SCHEMA-RECONCILIATION-CANDIDATE

| Field | Value |
|---|---|
| Date | 2026-10-09 |
| Work package | `WP-04-GATE-A-EXACT-SCHEMA-RECONCILIATION` |
| Candidate branch | `wp-04-gate-a-exact-schema-reconciliation-988a74b` |
| Integration base | `988a74b529fdb4bcf77f341db5c6d115e8511a9b` |
| User decision | `APPROVED_FOR_WP04_GATE_A_EXACT_SCHEMA_RECONCILIATION`; exact structural schema selection recorded in this candidate, not implementation authorization |
| Source decision packet | `wp-04-gate-a-exact-schema-decision-packet-c37a5bff@fc7833d0a491190c88f93d8fdd59da2feb263169`; SHA-256 `e69f0a06b6189a6558d7ee46f6c2c0f645abd6df62c618c39761b2733731042c` |
| Candidate documents | `docs/OBSERVATION_GATE_A_STRUCTURAL_SCHEMA.md`; `docs/governance/decisions/WP-04_GATE_A_EXACT_SCHEMA_DECISION.md` |
| Scope | Record the selected immutable cutoff schema, reference-only input-contract shape, exact reference pairs, value semantics and fail-closed structural error policy for focused audit; no source implementation |
| Candidate state | `PENDING_FOCUSED_INDEPENDENT_AUDIT_AND_SEPARATE_USER_INTEGRATION_AUTHORIZATION`; candidate commit identity is resolved from Git history and is not self-embedded |
| Activation condition | Only after focused independent audit of the exact candidate, separate explicit Project Owner/User authorization to integrate that exact commit, and fast-forward of that exact commit to `integration/implementation` with remote-ref verification may the schema selection become active Registry source selection |
| WP status/dependency impact | No transition or dependency change. WP-03 remains `CLOSED`; WP-04 remains `BLOCKED_BY_CONTRACT` with existing dependencies unchanged. |
| Authorization/evidence boundary | `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. No code, tests, build, ROS/ROSIDL, runtime, HIL, hardware, `deploy_sim` or `deploy_real` authorization is created. |
| Notes | This append-only candidate entry records the user-selected schema for review only. It does not activate a canonical contract, claim Gate A passed, close WP-04, supersede any historical Ledger entry, or alter PEP-001, QoS6, ACR8, WP-05, status, or dependencies. |

### WP-05-UNIFIED-MAP-ARTIFACT-SCHEMA-BASE-REFRESH-CANDIDATE

| Field | Value |
|---|---|
| Date | 2026-10-09 |
| Work package | WP-05-UNIFIED-MAP-ARTIFACT-SCHEMA-BASE-REFRESH |
| Integration base | f9987be4429349ef9110c45cf97a89728a5e4229 |
| Candidate branch | wp-05-unified-map-artifact-schema-change-control-f9987be |
| Prior audited semantics source | `wp-05-unified-map-artifact-schema-change-control-988a74b@617ef28b92b6a17bc4ba00d1b0edd7ccfcdd7b12`; parent `988a74b529fdb4bcf77f341db5c6d115e8511a9b`; stale after integration advanced to this base; provenance only, not integrable |
| Prior audit verdict | User-supplied `READINESS_FOR_USER_DECISION_TO_INTEGRATE: PASS`; refreshed candidate requires focused re-audit |
| User decision | `USER_DECISION: APPROVED_FOR_WP05_UNIFIED_MAP_ARTIFACT_SCHEMA_CHANGE_CONTROL`; preparation of the same four-path documentation-only candidate, no schema-scope expansion |
| Scope | Recreate audited map schema ACR and decision semantics, reconcile active RFC 8785 Registry wording, and append this entry; preserve WP-04 canonicalized files/status from base |
| Candidate state | PENDING_FOCUSED_INDEPENDENT_REAUDIT_AND_SEPARATE_USER_INTEGRATION_AUTHORIZATION |
| Activation condition | Focused re-audit passes; Project Owner/User separately authorizes this exact refreshed commit; exact commit is fast-forwarded to integration/implementation and remote ref is verified |
| WP status/dependency impact | No transition or dependency change. WP-05 remains OPEN; WP-04 remains BLOCKED_BY_CONTRACT. |
| Authorization/evidence boundary | CODE_AUTHORIZATION: NOT_GRANTED; RUNTIME_APPROVED: NOT_APPROVED. No map/scenario instance, source selection, measurement, code, runtime, HIL, hardware, motor-enable, or deployment authorization is created. |
| Notes | Ledger is append-only. `617ef28…` is recorded as audited stale provenance only; this entry does not copy or rewrite prior history. |

### WP-04-GATE-A-PREIMPLEMENTATION-GOVERNANCE-BUNDLE-CANDIDATE

| Field | Value |
|---|---|
| Date | 2026-10-10 |
| Work package | `WP-04-GATE-A-PREIMPLEMENTATION-GOVERNANCE-BUNDLE` |
| Integration base | `401593a4268af572ef4690177539360b1c15410a` |
| Candidate branch | `wp-04-gate-a-preimplementation-governance-bundle-401593a` |
| Scope | Four-path documentation/governance candidate: include the audited error-carrier decision record byte-identically; refresh the Gate A implementation-authorization packet to reflect the recorded error-carrier choices; reconcile Registry source-selection status for the exact structural schema; append this entry. No source or test code. |
| Decision-record provenance | Source `wp-04-gate-a-error-carrier-decision-record-401593a@f5f0a4a0351d40335ad585afa36430f3b639cea3`; path `docs/governance/decisions/WP-04_GATE_A_ERROR_CARRIER_DECISION.md`; SHA-256 `72a2c94df548cb00557b1777e10d11b96b386329894edaf34e1d81c07ed4e94d`; user-supplied focused audit verdict `READINESS_FOR_CANONICAL_INTEGRATION: PASS`. The report identity/hash was not supplied in that decision record and is not asserted here. |
| Packet provenance | `wp-04-gate-a-implementation-authorization-packet-f9987be@8ef93277502b9cc7282a544459ae3aa495b2f049`; `docs/WP-04_GATE_A_IMPLEMENTATION_AUTHORIZATION_PACKET_DRAFT.md`; SHA-256 `431c993a837a156ea2af2e6cad3e6b6d886caa544fd466f524c6bfe4dd662d11`. |
| Structural-schema activation evidence | Exact schema `docs/OBSERVATION_GATE_A_STRUCTURAL_SCHEMA.md`, SHA-256 `43537b8f0edafbe809e6f70bda86808f87b12f146ed45509c4bfbacd26956ad3`; correction candidate `wp-04-gate-a-receipt-selector-attribution-correction@f9987be4429349ef9110c45cf97a89728a5e4229`; focused re-audit report `INDEPENDENT_FOCUSED_STATIC_REAUDIT_WP04_F01_RECEIPT_SELECTOR_ATTRIBUTION_F9987BE4.md`, SHA-256 `6902ebce5ec874a5922e06c2623cba7edb09083f493d7aa8242ecc715c1f60c5`, verdict PASS; explicit user authorization for exact fast-forward was supplied; the exact commit is an ancestor of this integration base and the bytes match. Registry reconciliation records active structural-schema source selection only. |
| Candidate state | `PENDING_INDEPENDENT_AUDIT_AND_SEPARATE_USER_AUTHORIZATION_FOR_EXACT_FINAL_COMMIT`; the candidate commit identity is resolved from Git history and is not self-embedded. |
| Activation condition | The complete four-path candidate must pass independent audit, receive separate explicit Project Owner/User authorization for its exact final commit, then be fast-forwarded to `integration/implementation` with the remote ref verified. No integration occurs in this work package. |
| WP status/dependency impact | No status transition or dependency change. WP-02 remains `CLOSED`; WP-03 remains `CLOSED`; WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A remains `NOT_PASSED`. The prior exact-schema candidate Ledger entry is preserved; this entry reconciles only its pending activation state using the verified audit/authorization/integration evidence above. |
| Authorization/evidence boundary | `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. Candidate documentation integration would not itself authorize implementation, ROS, runtime, HIL, hardware, `deploy_sim`, or `deploy_real`. |
| Notes | Append-only candidate evidence. This entry does not itself integrate this bundle, pass Gate A, close WP-04, alter PEP or WP dependencies, or claim runtime evidence. |

### WP-04-STRUCTURAL-SCHEMA-REGISTRY-STATUS-RECONCILIATION-CANDIDATE

| Field | Value |
|---|---|
| Date | 2026-10-10 |
| Work package | `WP-04-STRUCTURAL-SCHEMA-REGISTRY-STATUS-RECONCILIATION` |
| Integration base | `3b357afdec00d7fb769c9d4978372772a91bc307` |
| Candidate branch | `wp-04-structural-schema-registry-status-reconciliation-3b357af` |
| Provenance | Base contains the audited preimplementation governance candidate `wp-04-gate-a-preimplementation-governance-bundle-401593a@3b357afdec00d7fb769c9d4978372772a91bc307`. The User-provided audit conclusion states its Registry activation reconciliation is adequately evidenced as active structural-schema source selection at this base. Exact schema SHA-256 is `43537b8f0edafbe809e6f70bda86808f87b12f146ed45509c4bfbacd26956ad3`; the cited integration ancestry and authorization evidence are recorded in the Registry section at base. |
| Scope | Registry wording consistency correction only: preserve the active-source-selection reconciliation and convert the older “candidate — not active” section into historical pre-activation provenance with the activation state reconciled to the same evidence. Append this Ledger entry. No schema, contract, PEP, code, test, or WP-05 change. |
| Candidate state | `PENDING_INDEPENDENT_AUDIT_AND_SEPARATE_USER_AUTHORIZATION_FOR_EXACT_FINAL_COMMIT`; this correction has no operative effect before its own integration. |
| Activation condition | The exact two-path candidate must pass independent audit, receive separate explicit Project Owner/User authorization for its final commit, and be fast-forwarded to `integration/implementation` with remote-ref verification. No integration occurs in this work package. |
| WP status/dependency impact | No status transition or dependency change. WP-02 remains `CLOSED`; WP-03 remains `CLOSED`; WP-04 remains `BLOCKED_BY_CONTRACT`; `GATE_A: NOT_PASSED`. |
| Authorization/evidence boundary | `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. No HIL, hardware, `deploy_sim`, or `deploy_real` authority is created. |
| Notes | Append-only Registry consistency candidate. It resolves contradictory current-state wording without changing the underlying schema selection, technical semantics, or historical source/audit provenance. It does not pass Gate A or close WP-04. |

### WP-05-UNIFIED-MAP-METADATA-SCHEMA-BASE-REFRESH-793514F

| Field | Value |
|---|---|
| Date | 2026-10-11 |
| Work package | WP-05-UNIFIED-MAP-METADATA-SCHEMA-BASE-REFRESH-793514F |
| Integration base | 793514f8ff3c20c13bfe84bf0529295de4d4d0b4 |
| Candidate branch | wp-05-unified-map-metadata-schema-change-control-793514f |
| Source candidate | wp-05-unified-map-metadata-schema-change-control-7f9ed36@3892edf37ab5388fd38d3cf4a41d28ae2401782e; parent 7f9ed36a10b5f4ab68eb437833f04d4842eff986; stale source provenance only; source-file hashes are recorded in the decision record |
| User decisions | Nine metadata decision groups and Option A remain USER_SUPPLIED_DECISION; no audit/authorization is inferred from the source candidate or Git refs. |
| Scope | Four-path governance refresh. No artifact instance, source, actor, measurement, or runtime evidence. |
| Supersession | Metadata remains authority for the artifact's own approval decision; append-only event/index is a separate proposed authority for predecessor/successor and effective/current disposition. Unresolved details remain PENDING_OWNER_DECISION or PROPOSAL_ONLY. |
| Candidate state | PENDING_FOCUSED_INDEPENDENT_AUDIT_AND_SEPARATE_USER_INTEGRATION_AUTHORIZATION; no activation before audit of this exact candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification. |
| WP status/dependency impact | No transition or dependency change. WP-05 remains OPEN; WP-04 remains BLOCKED_BY_CONTRACT. |
| Authorization boundary | CODE_AUTHORIZATION: NOT_GRANTED; RUNTIME_APPROVED: NOT_APPROVED. No code, runtime, HIL, hardware, motor-enable, deploy_sim, or deploy_real authority. |
| Notes | Append-only refresh entry. Neither the source candidate nor this candidate is recorded as active or canonicalized. |

### WP-04-GATE-A-STATUS-TRANSITION-BASE-REFRESH

| Field | Value |
|---|---|
| Date | 2026-10-11 |
| Work package | `WP-04-GATE-A-STATUS-TRANSITION-CANDIDATE` |
| Integration base | `d33b93d3c6389872450f1a001e3073c61f355824` |
| Candidate branch | `wp-04-gate-a-status-transition-d33b93d` |
| Prior local candidate provenance | `wp-04-gate-a-status-transition-793514f@481047c055cf7f7bdfb9e91cd6443cf0022518e3`, parent `793514f8ff3c20c13bfe84bf0529295de4d4d0b4`; its source contents were verified by their pinned SHA-256 values and are used only as provenance. The source candidate was not modified, rebased, committed again, or pushed by this work package. |
| User decision | `USER_DECISION: APPROVED_FOR_WP04_GATE_A_STRUCTURAL_PRIMITIVES_STATUS_TRANSITION`; preparation of the Gate A structural-primitives transition only |
| Candidate state | `GATE_A_STRUCTURAL_PRIMITIVES: PASSED_PENDING_FOCUSED_AUDIT_AND_CANONICAL_INTEGRATION`; no active/canonical transition is recorded here |
| Evidence scope | Implementation evidence commit `793514f8ff3c20c13bfe84bf0529295de4d4d0b4`; module `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/v3_observation_contracts.py`, SHA-256 `2d2013b3d584b1e42e71dcce85417e1402c4667dba41d95c820dd4499f7e7b3`; test `ros2_ws/src/mecanum_nav_rl/test/test_v3_observation_contract_primitives.py`, SHA-256 `8eacfca6e70bd987df9b4e00c769b9fe154e3c6632e2cb6245249f77b2fdd853`; focused pytest evidence reviewed: `69 passed in 0.21s` |
| Audit/decision provenance | Focused audit verdict and User decision supplied in the work-package context; no audit-report SHA-256 is asserted because no report hash is pinned here |
| Activation condition | The exact candidate must pass focused independent audit, receive separate explicit User authorization for its exact commit, be fast-forwarded to `integration/implementation`, and have the remote ref verified at that commit |
| WP status/dependency impact | No dependency change. WP-03 remains `CLOSED`; WP-04 remains `BLOCKED_BY_CONTRACT`; Gate B remains `NOT_STARTED`; WP-05 remains `OPEN`. The proposed transition is limited to Gate A structural primitives. |
| Authorization boundary | No new code authorization. No Gate B, connected behavior, 81D observation, ROS adapter, runtime, HIL, hardware, `deploy_sim` or `deploy_real` authority is granted. `RUNTIME_APPROVED: NOT_APPROVED`. |
| Notes | Append-only candidate evidence. It does not claim Gate A's transition is active/canonical, WP-04 is closed, or runtime evidence exists. |

### WP-05-MAP-METADATA-ACTIVATION-STATUS-BASE-REFRESH-572DA88

| Field | Value |
|---|---|
| Date | 2026-10-11 |
| Work package | WP-05-MAP-METADATA-ACTIVATION-STATUS-BASE-REFRESH |
| Integration base | `572da885d31d98929a1f8b8af4420012f1786fd6` |
| Source candidate | `wp-05-map-metadata-schema-activation-status-correction-d33b93d@e4add07d10eb4a616569d0f9a83f97493851ef04`; parent `d33b93d3c6389872450f1a001e3073c61f355824`; source/provenance only, not current candidate or base |
| Historical activation fact | Map metadata schema is `ACTIVE_ON_INTEGRATION` effective from `d33b93d3c6389872450f1a001e3073c61f355824`. Audit verdict and User authorization are `USER_SUPPLIED_EVIDENCE`; Git history verifies the integrated commit ancestry/ref facts. No audit-report hash is asserted. |
| Candidate state | This refresh records the already-occurring activation status and provenance on the current base. It is pending focused independent audit and separate User authorization for the exact refresh commit before that correction is fast-forwarded and its remote ref verified. |
| Scope | Status/provenance reconciliation only. No schema semantics change; RFC 8785 hash rule remains independently active; only `map.yaml` and `map.pgm` enter `map_content_hash`. `PENDING_OWNER_DECISION` items remain pending and the Option A supersession event/index remains `PROPOSAL_ONLY` and unapplied. |
| WP status/dependency impact | No status transition or dependency change. WP-05 remains `OPEN`; WP-04 is unchanged. |
| Authorization boundary | `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. No map artifact/approval, runtime, HIL, hardware, motor-enable, or deployment authorization is created. |
| Notes | Append-only refresh after the Gate A WP-04 transition candidate entered the integration base. Existing WP-04 plan and Ledger entries at the base are preserved unchanged. |

### WP-04-GATE-B-CONSOLIDATED-BOUNDARY-CLOSURE

| Field | Value |
|---|---|
| Date | 2026-10-11 |
| Work package | `WP-04-GATE-B-CONSOLIDATED-BOUNDARY-CLOSURE` |
| Integration base | `50476170bb545483905308e5887990ab6220c566` |
| Candidate branch | `wp-04-gate-b-boundary-closure-decision-50476170` |
| User decision provenance | Eight Owner decisions supplied under `WP04_GATE_B_CONSOLIDATED_OWNER_DECISION_PROPOSAL_572DA885`; supplied decision basis only, not represented as Git-pinned authority; no report hash asserted |
| Scope | Five-path documentation/governance candidate: Observation V3 Specification revision 1; consolidated Gate B decision record; candidate-only Registry source-selection entries; PEP-001 rev.0.7.0 boundary-closure record; this append-only Ledger entry. No code, interface, ROSIDL, profile, or runtime evidence. |
| Candidate state | `GATE_B_BOUNDARY_CLOSURE: PENDING_FOCUSED_AUDIT_AND_CANONICAL_INTEGRATION`; `GATE_B: NOT_STARTED` |
| Evidence and boundary | Pins approved QoS6/ACR8, receipt v2, transport manifest, dependency closure, and Gate A authorities. Exact wrapper public shape and receipt-to-cutoff lifecycle-member comparison remain `PENDING_OWNER_DECISION`; timing/profile values remain `PENDING_MEASUREMENT`. No Gate B implementation or runtime evidence is claimed. |
| Activation condition | This exact five-path candidate must pass focused independent audit, receive separate explicit User authorization for its exact final commit, be fast-forwarded to `integration/implementation`, and have the remote ref verified. No active/canonical Gate B boundary transition is recorded before those events. |
| WP status/dependency impact | No status transition or dependency change. WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A structural primitives remain `PASSED`; Gate B remains `NOT_STARTED`; WP-05 remains `OPEN`. |
| Authorization boundary | `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. No ROS/ROSIDL, adapter/QoS integration, runtime, HIL, hardware, `deploy_sim`, or `deploy_real` authority. |
| Notes | Candidate-only governance evidence. It does not assert Gate B readiness, Gate A semantic expansion, WP-04 closure, or map artifact/schema changes. |

### WP-05-WAREHOUSE-MAP2-CANONICAL-DRAFT-ARTIFACT

| Field | Value |
|---|---|
| Date | 2026-10-11 |
| Work package | `WP-05-WAREHOUSE-MAP2-CANONICAL-DRAFT-ARTIFACT` |
| Integration base | `68174e714cbe8aab61880113496cd7ccd7f97f5d` |
| Candidate branch | `wp-05-warehouse-map2-canonical-draft-68174e` |
| User decision | `USER_SUPPLIED_DECISION`: map ID/source pair, `github:hazandz` custodian, Git-only provenance v1, one image-path rewrite to `map.pgm`, lowercase UUIDv4, no pose graph, draft approval, `NOT_DECLARED` world/frame, and `NOT_VALIDATED` runtime compatibility |
| Evidence | Tracked source YAML and PGM at the exact integration base with SHA-256 values recorded in the decision record. The selected `tugbot_depot.sdf` is not used as artifact provenance; no world/frame or runtime validation is claimed. |
| Scope | One candidate-only governance clarification and draft static-map artifact. No artifact approval, scenario, measurement, code, runtime or hardware authority. |
| Candidate state | `PENDING_CONSOLIDATED_INDEPENDENT_AUDIT_AND_SEPARATE_USER_INTEGRATION_AUTHORIZATION`; no active/canonical instance before exact-candidate audit, separate authorization, fast-forward and remote-ref verification |
| WP status/dependency impact | No status or dependency transition. WP-05 remains `OPEN`; WP-04 remains unchanged. |
| Authorization boundary | `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. No navigation approval, world/frame validation, runtime compatibility, HIL, hardware, motor-enable, `deploy_sim`, or `deploy_real` authority. |
| Notes | The candidate ACR clarifications and draft artifact remain review evidence until this exact candidate is independently audited and separately authorized for integration. RFC 8785 hashing remains independently active; `map_content_hash` covers only `map.yaml` and `map.pgm`. |

### WP-04-GATE-B-EXACT-DATA-CONTRACT-COMPLETION-REFRESH

| Field | Value |
|---|---|
| Date | 2026-10-11 |
| Work package | `WP-04-GATE-B-EXACT-DATA-CONTRACT-COMPLETION-REFRESH` |
| Integration base | `1e14644a7d778a0c5ad32512430d775fd0e8ecd3` |
| Superseded review provenance | `wp-04-gate-b-exact-data-contract-change-control-68174e@687469f4aa2f166566e31aa91c1b1d90648c3812`; review candidate only, not integrated or active source selection |
| Correction source provenance | `wp-04-gate-b-exact-data-contract-completion-correction-68174e@73a1f73c39eb742e79f53f50d5b5d73b41be0822`, parent `68174e714cbe8aab61880113496cd7ccd7f97f5d`; unchanged source content, not integrated as this replacement |
| Replacement candidate branch | `wp-04-gate-b-exact-data-contract-completion-refresh-1e14644` |
| Scope and artifact hashes | Five-path documentation/governance replacement only. Specification rev.2 `docs/OBSERVATION_V3_SPECIFICATION.md`: `ed06bc5bd145e0eb9376df71ff42ee60069906d987c78531ba8b9e688746b1bc`; decision `docs/governance/decisions/WP-04_GATE_B_CONSOLIDATED_DECISION.md`: `9a683c12939c4f092341f8632507f8bc0ec45280ecd5e9a4b56a04a6f9828048`; remaining exact candidate file bytes are identified by the reviewed branch tip |
| Candidate state | Candidate-only pending one consolidated independent audit, separate exact-commit User integration authorization, fast-forward, and remote-ref verification; no replacement record shape is active |
| Deferred blockers | `DECISION_DEFERRED_PENDING_EXACT_NON_CIRCULAR_CONFIG_HASH_PROJECTION` and `DECISION_DEFERRED_PENDING_EXACT_RESOLVED_OBSERVATION_INPUT_PROFILE_SHAPE`; resolve both together in one consolidated resolved-config Owner decision before any code-authorization candidate is considered |
| Evidence and boundary | Carries forward selected flat binding, strict types/ranges/value semantics, lifecycle tuple and ACR8 mappings, adapter/core boundary, raw-ROS prohibition, fail-closed behavior, and `PENDING_MEASUREMENT`. OIC revision 6 remains provenance-only and cannot define fields/defaults/schema. No Gate B implementation or runtime evidence is claimed |
| WP status/dependency impact | No status transition or dependency change. WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A structural primitives remain `PASSED`; Gate B remains `NOT_STARTED`; Gate B boundary closure remains active on the base; WP-05 remains `OPEN` |
| Authorization boundary | `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. No ROS/ROSIDL, adapter, runtime, HIL, hardware, `deploy_sim`, or `deploy_real` authority |
| Notes | One append-only replacement-candidate entry. All Ledger bytes present at base are preserved; the WP-05 draft artifact and map-status state are unchanged. Neither `687469f…` nor `73a1f73…` is described as integrated by this work package. |

### WP-04-OBSERVATION-INPUT-PROFILE-ARCHITECTURE-AMENDMENT

| Field | Value |
|---|---|
| Date | 2026-10-11 |
| Work package | `WP-04-OBSERVATION-INPUT-PROFILE-ARCHITECTURE-AMENDMENT` |
| Integration base | `e89aeda5ca78859bfeedac4e7b94bcd6c7dcc7f0` |
| Candidate branch | `wp-04-observation-input-profile-architecture-amendment-e89aeda5` |
| User decision | Preserve the Architecture `ResolvedConfig` root; add no root `gate_b`; propose required nested `observation.input_profile: ObservationInputProfileV3` as a static immutable descriptor covered by the global config hash. |
| Scope | Six-path documentation/Architecture-change candidate: one ACR, revised Observation V3 Specification and Gate B decision, candidate-only Registry/PEP records, and this append-only Ledger entry. No code, test, ROSIDL, runtime profile instance, or WP-05 artifact. |
| Architecture provenance | `docs/MECANUM_NAV_DRL_Architecture.docx` at base `e89aeda5…`, SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`, dated 2026-09-16. Architecture file is unchanged and remains highest authority until the amendment is effective. |
| Proposed static schema | Required `ObservationInputProfileV3` has schema identity/revision, six snapshot/receipt/frame/topic-QoS/lifecycle-reset-barrier contract references, and immutable profile-source Git provenance. Each reference carries exact contract ID/digest and immutable source commit/path/file digest. No concrete pin is invented where active authority/evidence has not selected it. |
| Hash and eligibility | Candidate specifies global RFC 8785 JCS UTF-8 SHA-256 over the fully resolved config, excluding output `config_hash` and prohibited runtime facts. Missing/unknown/defaulted/coerced/unresolved required input or required evidence, duplicate keys, non-finite JSON, or a required pending measurement rejects the whole resolution; no partial hash. |
| Candidate state | `PENDING_FOCUSED_INDEPENDENT_AUDIT_AND_SEPARATE_USER_AUTHORIZATION_FOR_EXACT_FINAL_COMMIT`; no active `input_profile` member, resolved profile, or Architecture amendment is recorded before audit, separate exact-commit User authorization, fast-forward, and remote-ref verification. |
| Evidence boundary | ACR8/QoS6/receipt v2/Gate A authorities remain unchanged. OIC rev.6 remains provenance-only. The candidate does not claim Gate B acceptance, runtime behavior, or a concrete resolved profile. |
| WP status/dependency impact | No transition: WP-04 `BLOCKED_BY_CONTRACT`; Gate A structural primitives `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`. |
| Authorization boundary | `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. No ROS/ROSIDL, adapter, HIL, hardware, `deploy_sim`, or `deploy_real` authority. |
| Activation rule | This exact six-path candidate must pass focused independent audit, receive separate explicit User authorization for its exact final commit, be fast-forwarded to `integration/implementation`, and have its remote ref verified. Until then, Architecture and active Registry selections at the base remain controlling. |

### WP-04-OBSERVATION-INPUT-PROFILE-ARCHITECTURE-AMENDMENT-CORRECTION

| Field | Value |
|---|---|
| Date | 2026-10-11 |
| Work package | `WP-04-OBSERVATION-INPUT-PROFILE-ARCHITECTURE-AMENDMENT-CORRECTION` |
| Integration base | `e89aeda5ca78859bfeedac4e7b94bcd6c7dcc7f0` |
| Source amendment branch/commit | `wp-04-observation-input-profile-architecture-amendment-e89aeda5@d87b5a17ca0e9430d0b163aacf5b9cfcc4458d14`; direct parent/base `e89aeda5ca78859bfeedac4e7b94bcd6c7dcc7f0` |
| Correction branch | `wp-04-observation-input-profile-architecture-amendment-correction-e89aeda5` |
| Supersedes | Source amendment candidate traceability only: Registry revision-label wording, decision §3 provenance attribution, and PEP source commit/evidence reference. No technical semantics are superseded. |
| Findings | F-01: Registry distinguishes active revision 1, historical/superseded revision 2, and current candidate-only revision 3. F-02: decision identifies revision 2/`ReceiptIngressBindingV3` as exact historical pinned provenance and revision 3 as current source amendment content. F-03: PEP references immutable JSON evidence for the exact source branch, commit and base. |
| Evidence record | `docs/governance/evidence/WP-04_OBSERVATION_INPUT_PROFILE_ARCHITECTURE_AMENDMENT_PROVENANCE.json`; SHA-256 `eba5f233a2488d11b5161f6b87abd4994d749763f36eb768d4577f445e326069`; provenance/evidence only, not approval or activation |
| Scope | Five-path traceability correction only: Registry, Gate B decision, PEP, append-only Ledger, and immutable provenance JSON. The source ACR and Specification are unchanged. |
| Candidate state | Pending focused consolidated independent audit, separate exact-commit User authorization, fast-forward, and remote-ref verification; no amendment activation is recorded. |
| WP status/dependency impact | No change: WP-04 `BLOCKED_BY_CONTRACT`; Gate A structural primitives `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`. |
| Authorization boundary | `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. No runtime, ROS/ROSIDL, HIL, hardware, or deployment authority. |

### WP-05-WORLD-FRAME-EVIDENCE-GOVERNANCE-CORRECTION-REFRESH

| Field | Value |
|---|---|
| Date | 2026-10-12 |
| Work package | `WP-05-WORLD-FRAME-EVIDENCE-GOVERNANCE-CORRECTION-REFRESH` |
| Current integration base | `0b2fcd1d010bc30f54d7621e6192dd76339df6b2` |
| Historical source candidate | `wp-05-world-frame-evidence-registry-reconciliation-e89aeda5@0f42f1c9da00725c36500ff4ec1d2f75a0c8709a`, sole parent `e89aeda5ca78859bfeedac4e7b94bcd6c7dcc7f0`; remote review ref verified, not integrated |
| Supplied audit evidence | User supplied verdict `CORRECTION_REQUIRED`; no audit-report hash is asserted |
| Historical refresh provenance | `572da885d31d98929a1f8b8af4420012f1786fd6` is the prior refresh base, not the current integration base or candidate |
| Correction | PEP snapshot now distinguishes the integrated `warehouse_map2` draft from an approved/navigation-ready map. This Ledger preserves all prior entries and records that the later review-branch push of `0f42f1c…` succeeded; the supplied audit requires governance corrections. The source candidate remains unintegrated and activated neither the evidence record nor a metadata transition. |
| Current replacement candidate | `wp-05-world-frame-evidence-governance-correction-0b2fcd1`, sole parent/current base `0b2fcd1d010bc30f54d7621e6192dd76339df6b2`; pending consolidated independent audit, separate exact-commit User authorization, fast-forward, and remote-ref verification |
| Map/world/runtime state | `warehouse_map2` remains `approval_status: draft`, `world_frame: NOT_DECLARED`, `runtime_compatibility: NOT_VALIDATED`; the declaration evidence proposal does not establish equivalence, transform, metric alignment, runtime validation, navigation readiness, or map approval |
| WP status/dependency impact | No transition or dependency change. WP-05 remains `OPEN`; WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A structural primitives remain `PASSED`; Gate B remains `NOT_STARTED` |
| Authorization boundary | `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. No code, ROS/runtime, HIL, hardware, motor-enable, `deploy_sim`, or `deploy_real` authority |

### PROJECT-GOVERNANCE-RECONCILIATION-WP04-WP05

| Field | Value |
|---|---|
| Date | 2026-10-12 |
| Work package | `PROJECT-GOVERNANCE-RECONCILIATION-WP04-WP05` |
| Work branch | `project-governance-reconciliation-wp04-wp05-410d9cb` |
| Integration base | `410d9cb70518b64d3c76c2ef99b11b69d1da6701` |
| Scope | Six-path documentation reconciliation for WP-04 amendment activation wording and WP-05 map/evidence status wording; no technical semantics or status transition |
| Git-verifiable integration facts | At the stated base, Observation V3 Specification revision 3/source amendment commit `d87b5a17ca0e9430d0b163aacf5b9cfcc4458d14` and the WP-05 world-frame declaration evidence record are integration-resident. `artifacts/maps/warehouse_map2/` is present with `approval_status: draft`, `world_frame: NOT_DECLARED`, and `runtime_compatibility: NOT_VALIDATED`. These facts do not prove audit, User approval, map-world equivalence, transform, runtime validation, navigation readiness, or map approval. |
| `USER_SUPPLIED_AUDIT_EVIDENCE` | Baseline audit findings F-01 (WP-04), F-03 and F-04 (WP-05) were supplied by the User; no audit-report hash is asserted. |
| Correction basis | Historical candidate/pending wording is retained only as historical state. The integrated WP-04 governance amendment is distinguished from Gate B implementation/pass; the WP-05 draft artifact and integration-resident evidence record are distinguished from approval or metadata transition. |
| Supersedes | Stale current-state descriptions for these findings in the allowed Specification, WP-04/WP-05 decision, Registry and PEP paths. Prior Ledger entries remain unchanged as history. |
| WP status/dependency impact | No transition or dependency change. WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A structural primitives remain `PASSED`; Gate B remains `NOT_STARTED`; WP-05 remains `OPEN`. |
| Authorization boundary | `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. No implementation, ROS/runtime, HIL, hardware, deployment, or map approval authority. |
| Candidate state | This reconciliation is a review candidate pending its own focused audit, separate exact-commit User authorization, fast-forward and remote-ref verification. |


### PROJECT-GOVERNANCE-RECONCILIATION-WP04-WP05-ACR-STATUS-CORRECTION

| Field | Value |
|---|---|
| Date | 2026-10-12 |
| Work package | `PROJECT-GOVERNANCE-RECONCILIATION-WP04-WP05-ACR-STATUS-CORRECTION` |
| Source candidate | `project-governance-reconciliation-wp04-wp05-410d9cb@93e548d1bec80f33cd89e26080a61f59b53712cf`, sole parent `410d9cb70518b64d3c76c2ef99b11b69d1da6701` |
| Supersedes | The source-candidate status wording that described WP-04 revision 3 and its amendment as integrated/effective/active; prior Ledger entries remain unchanged historical records |
| Finding evidence | F-01 is `USER_SUPPLIED_INDEPENDENT_AUDIT_EVIDENCE`; no audit-report hash is asserted |
| Git-verifiable fact | Source commit `d87b5a17ca0e9430d0b163aacf5b9cfcc4458d14` is present in integration ancestry at base `410d9cb70518b64d3c76c2ef99b11b69d1da6701` |
| Authority reconciliation | The companion ACR remains `CANDIDATE_ONLY_PENDING_FOCUSED_INDEPENDENT_AUDIT_AND_CANONICAL_INTEGRATION`; ancestry alone does not prove audit or exact User authorization and does not activate the amendment |
| Correction scope | Restores downstream WP-04 status wording to integration-resident candidate/provenance pending the ACR activation conditions; no schema semantics, pins, blockers, map artifact, or metadata were changed |
| WP status/dependency impact | No transition: WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A structural primitives `PASSED`; Gate B `NOT_STARTED`; WP-05 remains `OPEN` |
| WP-05 no-regression | Draft `warehouse_map2` artifact, integration-resident world-frame evidence record, and metadata states are unchanged; no approval or metadata transition is inferred |
| Authorization boundary | `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`; no ROS/ROSIDL, runtime, HIL, hardware, or deployment authority |
| Candidate state | Pending focused independent audit, separate exact-commit User authorization, fast-forward, and remote-ref verification; this entry records no audit PASS, authorization, or activation |

### WP04-GATE-B-ACTIVE-SOURCE-SELECTION-CONTINUITY-CORRECTION

| Field | Value |
|---|---|
| Date | 2026-10-12 |
| Work package | `WP04-GATE-B-ACTIVE-SOURCE-SELECTION-RECONCILIATION` |
| Integration base | `410d9cb70518b64d3c76c2ef99b11b69d1da6701` |
| Correction source | `project-governance-reconciliation-wp04-wp05-acr-correction-410d9cb@d2345bd439e27421435a8b1730085fe2516d8da2`, direct parent `93e548d1bec80f33cd89e26080a61f59b53712cf`; source candidate only, not this successor's base |
| Active-source trace evidence | Git-verifiable at the stated base: Registry and PEP identify Observation V3 Specification revision 1 as the active controlled Gate B boundary selection at `68174e714cbe8aab61880113496cd7ccd7f97f5d`; exact path `docs/OBSERVATION_V3_SPECIFICATION.md`; full-document SHA-256 `feffb86e335d64a3a3fe0f3a1ce0866f868c8ed56ffa4412db14128c80b284ec`. Revision 2 is superseded historical review provenance. |
| Amendment boundary | Revision 3/source commit `d87b5a17ca0e9430d0b163aacf5b9cfcc4458d14` is integration-resident Git history only. Its companion ACR remains candidate-only pending focused independent audit, separate explicit User authorization for the exact commit, canonical fast-forward, and remote-ref verification. No ACR activation or revision-1 replacement is claimed. |
| Correction | Clarifies source-selection continuity across the Specification, Gate-B decision, Registry and PEP. Historical pre-integration candidate wording is retained as historical state; the current active boundary selection is distinguished from the revision-3 amendment candidate. |
| Gate B blockers and status | No semantic or status change. `DECISION_DEFERRED_PENDING_EXACT_NON_CIRCULAR_CONFIG_HASH_PROJECTION` and `DECISION_DEFERRED_PENDING_EXACT_RESOLVED_OBSERVATION_INPUT_PROFILE_SHAPE` remain blockers. WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A remains `PASSED`; Gate B remains `NOT_STARTED`. |
| WP-05 no-regression | No WP-05 file or map artifact was changed. The integrated `warehouse_map2` remains draft; `world_frame: NOT_DECLARED`; runtime compatibility `NOT_VALIDATED`. |
| Audit/authorization boundary | No audit PASS or User authorization is asserted by this entry. `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. |
| Candidate state | This source-selection continuity correction is pending its own focused independent audit, separate exact-commit User authorization, fast-forward and remote-ref verification. |

### WP04-GATE-B-GLOBAL-CONFIG-HASH-AND-INPUT-PROFILE-CHANGE-CONTROL

| Field | Value |
|---|---|
| Date | 2026-10-12 |
| Work package | `WP04-GATE-B-GLOBAL-CONFIG-HASH-AND-INPUT-PROFILE-CHANGE-CONTROL` |
| Integration base | `c1187de97c550b9968d88aa6043ed716df981b54` |
| Owner decision | User supplied `APPROVE_BOTH_AS_WRITTEN` for the global `ResolvedConfig.config_hash` policy and required nested `ObservationConfig.input_profile: ObservationInputProfileV3`; recorded here as decision provenance, not activation or authorization |
| Global hash decision | Full resolved/validated static Architecture `ResolvedConfig`; RFC 8785 JCS canonical UTF-8, no BOM or trailing newline; SHA-256; omit only output `config_hash`; reject duplicate keys, non-finite numbers and runtime-only data rather than silently filtering it; no Gate-B-only/subrecord hash |
| Input-profile decision | Required static nested `ObservationConfig.input_profile`; no root `gate_b`; profile participates in the global hash; runtime samples/state remain outside resolved configuration |
| Candidate scope | Six documentation paths: Architecture Change Record, Observation V3 Specification, Gate-B consolidated decision, Canonical Source Registry, PEP-001 and this Ledger |
| Supersedes | The unresolved Owner-decision state for `DECISION_DEFERRED_PENDING_EXACT_NON_CIRCULAR_CONFIG_HASH_PROJECTION` and `DECISION_DEFERRED_PENDING_EXACT_RESOLVED_OBSERVATION_INPUT_PROFILE_SHAPE` recorded in `WP-04-GATE-B-EXACT-DATA-CONTRACT-COMPLETION-REFRESH`; prior entries remain unchanged historical records |
| Remaining blockers | ACR amendment is candidate-only pending focused audit, separate User authorization for exact final commit, fast-forward and remote-ref verification. Concrete profile contract/source pins and required measurements remain `PENDING_OWNER_DECISION` / `PENDING_MEASUREMENT`; compiler must reject whole config without partial hash while required inputs remain unresolved |
| Active source continuity | Observation V3 Specification revision 1 remains the active Gate-B boundary-source selection until ACR activation; revision 3 at the base and this revision-4 candidate do not activate the amendment. OIC revision 6 remains provenance-only |
| Candidate state | Pending focused consolidated independent audit; no ACR activation or canonical integration is claimed |
| WP status/dependency impact | No transition or dependency change: WP-04 `BLOCKED_BY_CONTRACT`; Gate A structural primitives `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN` |
| Authorization boundary | `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`; no ROS/ROSIDL, adapter, runtime, HIL, hardware, or deployment authority |

### WP04-GATE-B-CONFIG-HASH-EXHAUSTIVE-ROOT-CORRECTION

| Field | Value |
|---|---|
| Date | 2026-10-12 |
| Work package | `WP04-GATE-B-CONFIG-HASH-EXHAUSTIVE-ROOT-CORRECTION` |
| Integration base | `c1187de97c550b9968d88aa6043ed716df981b54` |
| Source candidate / direct parent | `wp-04-gate-b-global-config-owner-decision-c1187de@e79a8f6fd6be7b50dbbfe28819a34116ecaec3ab`; parent `c1187de97c550b9968d88aa6043ed716df981b54` |
| Correction review branch | `wp-04-gate-b-config-hash-root-correction-c1187de` |
| Finding provenance | User-supplied focused independent audit finding F-01: ACR §4 and Observation V3 Specification §5.1 did not explicitly enumerate the complete Architecture §4 global hash projection roots; no audit-report hash is asserted |
| Correction scope | Six documentation paths only: ACR revision 3, Observation V3 Specification revision 5, Gate-B decision, Registry, PEP-001 revision 0.10.1, and this append-only Ledger entry |
| Candidate source pins | ACR revision 3 SHA-256 `38cb74c0b09cd9c3ecbbac30c6520e0d01f7711adb788414a0a46489e844d9f8`; Observation V3 Specification revision 5 SHA-256 `4092ee19d48a760b329ff49b9a79e39ab8389ff232aabd5dd06db83f8d83e5a2` |
| Exhaustive hash-input root set | `schema_version`, `runtime_profile`, `navigation_mode`, `project`, `topics`, `frames`, `state_estimation`, `localization`, `navigation`, `observation`, `action`, `reward`, `training`, `evaluation`, `safety`, `acceptance`; each exactly once; only output `config_hash` omitted; `observation.input_profile` remains nested under `observation` |
| Hash/failure semantics | SHA-256 over RFC 8785 JCS UTF-8 bytes after full resolution/validation, no BOM/trailing newline; duplicate keys, non-finite values, and runtime-only facts are rejected, not silently filtered; no partial config/hash |
| Candidate state | Correction successor of `e79a8f6…`, pending focused independent audit, separate explicit User authorization for its exact final commit, fast-forward, and remote-ref verification; revision 1 remains the active Gate-B boundary-source selection; ACR revision 3 and Specification revision 5 remain candidate-only |
| Supersedes | F-01 root-list omission in source candidate ACR revision 2 §4 and Specification revision 4 §5.1 only; no Owner decision or profile semantics superseded; all prior Ledger bytes remain unchanged |
| WP/status impact | No transition or dependency change: WP-04 `BLOCKED_BY_CONTRACT`; Gate A structural primitives `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN` |
| Authorization boundary | `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`; no code, test, ROS/ROSIDL, adapter, runtime, HIL, hardware, or deployment authority |

### WP04-ACR-REV3-ACTIVATION-STATUS-RECONCILIATION

| Field | Value |
|---|---|
| Date | 2026-10-12 |
| Work package | `WP04-ACR-REV3-ACTIVATION-STATUS-RECONCILIATION` |
| Exact base | `8c3de26521d7028a933f0a3ebe780fcb372f7a3a` |
| Activated event | ACR revision 3 exact-candidate audit PASS and separate exact-commit User authorization are `USER_SUPPLIED_EVIDENCE` (no audit-report hash asserted); fast-forward from `c1187de97c550b9968d88aa6043ed716df981b54` and remote-ref verification at `8c3de…` are Git-verifiable facts |
| Activated artifacts | ACR revision 3 SHA-256 `38cb74c0b09cd9c3ecbbac30c6520e0d01f7711adb788414a0a46489e844d9f8`; Observation V3 Specification revision 5 SHA-256 `4092ee19d48a760b329ff49b9a79e39ab8389ff232aabd5dd06db83f8d83e5a2` |
| Candidate scope | Status/provenance reconciliation only across ACR, Observation V3 Specification, Gate-B decision, Registry, PEP-001 revision `0.10.2`, and this append-only Ledger entry; technical semantics unchanged |
| Remaining blockers | Required contract/source pins and evidence remain pending; measurements remain `PENDING_MEASUREMENT`; no profile instance is resolved and Gate B remains `NOT_STARTED` |
| WP-05 boundary | `warehouse_map2`: `approval_status: draft`, `world_frame: NOT_DECLARED`, `runtime_compatibility: NOT_VALIDATED`; User-supplied SLAM source attribution is provenance only, not map/world equivalence, transform, metric alignment, runtime validation, or map approval |
| Candidate state | This reconciliation candidate awaits focused independent audit, separate User authorization for its exact commit, fast-forward, and remote-ref verification; it does not alter the activated ACR/spec semantics |
| WP/status impact | No transition: WP-04 `BLOCKED_BY_CONTRACT`; Gate A structural primitives `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN` |
| Authorization boundary | `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`; no ROS, HIL, hardware, or deployment authority |

### WP04-ACR3-STATUS-RECONCILIATION-POST-INTEGRATION-CORRECTION

| Field | Value |
|---|---|
| Date | 2026-10-12 |
| Work package | `WP04-ACR3-STATUS-RECONCILIATION-POST-INTEGRATION-CORRECTION` |
| Exact integration base | `3fc3e2e583550b47195720f0de2fda8fbbd7490f` |
| Integrated status event | Git history at the exact base verifies status-reconciliation commit `3fc3e2e…` is integrated. ACR revision 3 and Observation V3 Specification revision 5 remain the active technical authority from `8c3de26521d7028a933f0a3ebe780fcb372f7a3a`. |
| Evidence classification | Fast-forward/ref state and commit ancestry are Git-verifiable. The exact-candidate audit PASS and separate User authorization for ACR revision-3 activation are `USER_SUPPLIED_EVIDENCE`; no audit-report hash is asserted. |
| Prior review provenance | `4a938773cfd8f36cc81934951f4fa02dae99cb05` is an unintegrated review candidate. Its audit PASS is User-supplied evidence; delivery preflight found wording that would remain stale after integration, and no fast-forward of that commit occurred. It does not alter active technical authority. |
| Correction scope | Status/provenance consistency across ACR, Observation V3 Specification, Gate-B decision, Registry, PEP-001 revision 0.10.3 and this append-only entry; no technical contract semantics changed. |
| Historical wording | Earlier pending-audit/authorization/integration text remains untouched in prior Ledger entries and records the state at their respective earlier snapshots. It is not the current state of commit `3fc3e2e…`. |
| Remaining blockers | Required contract/source pins and evidence remain `PENDING_OWNER_DECISION`; required measurements remain `PENDING_MEASUREMENT`. No resolved profile exists, and Gate B remains `NOT_STARTED`. |
| WP-05 boundary | `warehouse_map2` remains `approval_status: draft`, `world_frame: NOT_DECLARED`, `runtime_compatibility: NOT_VALIDATED`. User-supplied SLAM-source attribution is provenance only and does not establish map/world equality, transform, metric alignment, runtime validation, or map approval. |
| Status/authorization | No status or dependency transition: WP-04 `BLOCKED_BY_CONTRACT`; Gate A structural primitives `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. |

### WP05-WAREHOUSE-MAP2-NAVIGATION-PROFILE-RESOLUTION

| Field | Value |
|---|---|
| Date | 2026-10-12 |
| Work package | `WP05-WAREHOUSE-MAP2-NAVIGATION-PROFILE-RESOLUTION` |
| Exact integration base | `29080644f3020f7ecd208dc45433c7d36ecc5e2e` |
| User-supplied decisions | Navigation V1 target is Map Server + AMCL `nav2_amcl::OmniMotionModel`; SLAM Toolbox is MAPPING-only; intended global frame is `map`; the map/SDF SLAM association is User-supplied provenance, not independently Git-proved. |
| Git-verifiable artifact facts | `warehouse_map2` exists as draft with artifact identity `4a8a23d0-7e27-4a50-8201-dd1abf1a3db4`, `map_content_hash` `2bd9ff0a40eaeb61c2359aab4bb213da623ab56746debe591edd4a54c2229f90`, `world_frame: NOT_DECLARED`, and `runtime_compatibility: NOT_VALIDATED`. |
| Static source inventory | Architecture §43/§49 sets target provider and startup order. The V3 inputs are skeletons; current legacy Nav2/launch/robot-description sources have inconsistent scan/frame/topic assumptions and are not selected as canonical profile pins. No tracked canonical `mecanum_nav_bringup` Nav2/Map Server/EKF profile config or exact package-version lock exists at the base. |
| Decision record | `docs/governance/decisions/WP-05_NAVIGATION_PROFILE_RESOLUTION_DECISION.md` records target decisions, exact-base source hashes, unresolved fields and offline/runtime evidence boundary. It is a review candidate only and does not resolve a profile or select a map for navigation. |
| Remaining decisions/evidence | Runtime profile/use scope; exact immutable Nav2/Map Server/AMCL/EKF/config/launch/package pins; concrete AMCL parameters; exact scan `header.frame_id`/TF child frame and geometry; remaps/namespaces; lifecycle implementation pins; complete static source closure and `config_hash`; later runtime TF/publisher/map/localization/lifecycle evidence. No alias is assumed. |
| Map/world/runtime boundary | SDF pin identifies source bytes only; no `map == world`, transform, metric alignment, runtime compatibility, navigation readiness or map approval is inferred. Artifact remains draft; profile, map approval and world-frame validation are independent. |
| Status/authorization | No transition/dependency change: WP-05 `OPEN`; WP-04 unchanged; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. |
| Candidate state | `wp-05-warehouse-map2-navigation-profile-resolution-29080644`, based on the exact integration base above; pending focused independent audit, separate exact-commit User authorization, fast-forward and remote-ref verification. This entry asserts no audit PASS or integration. |

### WP04-GATE-B-CANONICAL-INPUT-SOURCE-SELECTION-REFRESH

| Field | Value |
|---|---|
| Date | 2026-10-12 |
| Work package | `WP04-GATE-B-CANONICAL-INPUT-SOURCE-SELECTION-REFRESH` |
| Exact integration base | `13bfa06658e5d65cc16f97fbc3ff3ec4a72e1bf6` |
| Source wording provenance | `wp-04-gate-b-canonical-input-source-selection-29080644@d385ea98986f0d68d6f288da2efa5db3fcf66085`, parent `29080644f3020f7ecd208dc45433c7d36ecc5e2e`; not integrated and no content-audit verdict. It is not authority. |
| Owner source-selection rule | Select only sources established by current Registry/approval authority; ACR3 and Specification rev.5 remain technical authority; OIC rev.6/drafts/review candidates are provenance only; no alias, inferred ID/digest, default or measurement. |
| Verified existing pins | At integrated bundle commit `2e7a2980cb75f0567182ea694c04328d7d8643e0`: receipt v2 SHA-256 `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`; dependency closure `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73`; QoS6 transport manifest `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620`; QoS6 full-document SHA-256 `4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022`. |
| Remaining source pins | LiDAR snapshot, LocalReference, measured-twist, frame, lifecycle/reset/action-barrier contract identities/digests and immutable source pins, plus concrete profile-source reference, remain `PENDING_OWNER_DECISION`; exact bytes/provenance must be checked after approved source selection. |
| Measurement/evidence boundary | Applicable timing, freshness, skew, timeout, buffer and sensor values remain `PENDING_MEASUREMENT`; no implementation, ROS adapter/runtime, HIL or hardware evidence is asserted. |
| Candidate scope | Successor source-selection decision record, Registry inventory, and this append-only entry. PEP, ACR and Specification are unchanged. |
| Candidate state | Pending focused independent audit, separate User authorization for this exact successor commit, fast-forward, and remote-ref verification. No new technical source is activated. |
| Fail-closed boundary | Under active ACR3, any required unresolved pin/evidence/value keeps the profile unresolved; compiler rejects the whole resolved config and emits no partial ResolvedConfig or config_hash. |
| WP/status/authorization | No transition: WP-04 `BLOCKED_BY_CONTRACT`; Gate A structural primitives `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; map remains draft/not approved, world frame not declared, runtime compatibility not validated; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. |


### WP05-NAVIGATION-V1-CANONICAL-SOURCE-SELECTION-REFRESH

| Field | Value |
|---|---|
| Date | 2026-10-13 |
| Exact integration base | `71f5db2b2bd1a04a1a3a087fed2ae6547f156fb1` |
| Decision source | New `docs/governance/decisions/WP-05_NAVIGATION_V1_CANONICAL_SOURCE_SELECTION.md`; Owner source-selection boundary is recorded as `USER_SUPPLIED_DECISION`, while file hashes and artifact state are Git-verifiable at the base |
| Source selection | No executable Navigation V1 profile is canonical. V3 files are contract/intention inputs only; legacy Nav2/AMCL/launch/SLAM/Gazebo sources are `REFERENCE_ONLY_LEGACY`; geometry/SDF are evidence only |
| Pending closure | Map Server config; AMCL parameters; EKF config; launch ownership; scan header frame; `base_link → lidar` geometry; TF ownership realization; explicit remaps/namespaces; lifecycle/startup; package/version pins; complete resolved `config_hash` |
| Map boundary | `warehouse_map2` is integration-resident draft, not approved/navigation-ready; profile binding by map ID/identity/hash would not itself approve it. World-frame validation and runtime compatibility remain separate |
| Fail-closed boundary | Any missing/conflicting required selection, pin, or evidence means no resolved profile, no profile hash, and no Navigation V1 bring-up |
| Candidate state | Review candidate pending independent audit, separate explicit User authorization for the exact commit, fast-forward, and remote-ref verification; this Ledger entry does not assert audit PASS or integration |
| Status/authorization | No status/dependency transition: WP-05 `OPEN`; map `DRAFT_ON_INTEGRATION_NOT_APPROVED`; world frame `NOT_DECLARED`; runtime compatibility `NOT_VALIDATED`; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`; WP-04 unchanged |


### WP04-GATE-B-TARGET-CONTRACT-CLOSURE-DECISION

| Field | Value |
|---|---|
| Date | 2026-10-13 |
| Exact integration base | `701bb0cc5ca17b71e083d3ce4fdebd2bf46fbcee` |
| Owner decision provenance | Owner decisions in the current work-package request: receipt v2/QoS6 pins remain established; exact LiDAR target `lidar_frame` with no implicit aliases; LocalReference is navigation/global path in `base_link`; measured twist source semantics are one EKF fused-odometry publisher; TF target ownership is localization/EKF/robot description; preserve lifecycle/barrier/fail-closed semantics. This is user-supplied decision provenance, not a Git-generated approval or audit report. |
| Active authority at base | Architecture DOCX SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`; ACR technical revision 3 and Observation V3 Specification technical revision 5 remain active from `8c3de26521d7028a933f0a3ebe780fcb372f7a3a`. Proposed ACR record revision 6 and Specification revision 8 are candidate-only in this change. |
| Established pins retained | Receipt v2 interface SHA-256 `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`; dependency-closure v1 SHA-256 `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73`; QoS6 transport manifest SHA-256 `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620`; QoS6 full-document SHA-256 `4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022`. These remain established and are not reclassified as pending. |
| Remaining immutable source references | Six groups remain `PENDING_OWNER_SOURCE_SELECTION`: LiDAR snapshot, navigation/global-path LocalReference, measured-twist snapshot, frame/geometry source, lifecycle/reset/action-barrier policy, and concrete profile source. No source IDs, digests, paths, commits, aliases, defaults, topic/config pins, or package versions are invented. |
| Remaining measurements | Physical LiDAR geometry/extrinsic and applicable timing, freshness, skew, timeout, buffer, sensor, and measured-twist values remain `PENDING_MEASUREMENT`; no measurement evidence is created here. |
| Fail-closed boundary | No resolved `ObservationInputProfileV3` or partial global config/hash while a required pin/evidence/measurement is unresolved. Runtime-only data remains invalid in static config and is rejected, not silently filtered. |
| Candidate scope/state | Five allowlisted documentation paths only: ACR, Observation V3 Specification, new target-contract decision, Registry, and this append-only Ledger entry. Candidate branch `wp04-gate-b-target-contract-closure-decision-701bb0c`; pending focused independent audit, separate User authorization for the exact candidate, fast-forward, and remote-ref verification. No ACR revision 6 or Specification revision 8 activation is claimed. |
| WP/status/authorization | No transition: WP-04 `BLOCKED_BY_CONTRACT`; Gate A structural primitives `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. No code, ROS/ROSIDL, runtime, HIL, hardware, or deployment authority. |


### WP04-GATE-B-TARGET-CONTRACT-POST-INTEGRATION-STATUS-CORRECTION

| Field | Value |
|---|---|
| Date | 2026-10-13 |
| Work package | `WP04-GATE-B-TARGET-CONTRACT-POST-INTEGRATION-STATUS-CORRECTION` |
| Integration base / source candidate | `701bb0cc5ca17b71e083d3ce4fdebd2bf46fbcee` / `3eb4cde6188082a21cd59b932e9423254367f86d`; source candidate parent is the integration base |
| Finding provenance | User-supplied independent-audit finding: source candidate wording left revision 6 / revision 8 / decision in an unqualified pre-integration pending state; no audit-report hash is asserted |
| Correction scope | Status/provenance wording only in the ACR record, Observation V3 Specification, target-contract decision, Registry, and this append-only Ledger entry; no technical semantics or source pins changed |
| Source-parent snapshot | Before the source candidate's integration, it awaited focused audit, separate User authorization for its exact commit, fast-forward, and remote-ref verification; ACR revision 3 and Specification revision 5 remained the active technical authority |
| Post-integration target state | After audit PASS and separate User authorization for the exact source successor, its fast-forward, and remote-ref verification, revision 6 / revision 8 / the decision are integration-resident target-governance records only. ACR revision 3 and Specification revision 5 remain active technical authority; the target records do not define active technical semantics or resolve a profile |
| Correction-candidate snapshot | At this entry's source-parent base, the correction successor based directly on `3eb4cde…` was pending its own focused independent audit, separate User authorization for its exact commit, fast-forward, and remote-ref verification; this entry does not claim those events occurred |
| Supersedes | The unqualified present-tense pending-integration wording for source candidate `3eb4cde…` in the prior `WP04-GATE-B-TARGET-CONTRACT-CLOSURE-DECISION` entry only; prior Ledger bytes and technical decisions remain unchanged |
| Remaining boundary | Required source pins/evidence remain pending; applicable measurements remain `PENDING_MEASUREMENT`; no resolved profile or partial profile/hash; Gate B `NOT_STARTED`; WP-04 `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; WP-05 `OPEN`; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED` |


### WP04-GATE-B-SOURCE-DISPOSITION-CLOSURE

| Field | Value |
|---|---|
| Date | 2026-10-13 |
| Exact integration base | `8b2f6d5c05ae8db8ce62285bd84afc401fb0d00c` |
| Owner decision provenance | User-supplied Owner decision in this work package. Only the supplied source classifications are recorded; no audit-report hash is asserted. |
| Change class and scope | L1 source-provenance/selection-boundary candidate: `docs/governance/decisions/WP-04_GATE_B_SOURCE_DISPOSITION_CLOSURE.md`, `docs/governance/CANONICAL_SOURCE_REGISTRY.md`, and this append-only Ledger entry. No technical contract semantics or public/runtime interface is created. |
| Source-byte evidence | The ten exact source paths and SHA-256 values are recorded in the decision record and verified at immutable base `8b2f6d5c05ae8db8ce62285bd84afc401fb0d00c`. These are source-file provenance only, not contract IDs, semantic digests, profile pins, or runtime evidence. |
| Established pins retained | Final-issued receipt v2, its dependency-closure pin, and QoS6/transport-manifest pins remain established under active Registry/approval; they are not reclassified or changed. Active ACR revision 3 and Observation V3 Specification revision 5 remain technical authority. |
| Disposition and unresolved groups | LiDAR algorithm only; simulation/provenance-only; structural primitive/non-canonical policy; and Architecture-intent-only sources are not canonical runtime contracts. Six required profile-reference groups remain unresolved: LiDAR snapshot, LocalReference, measured twist, frame/TF, lifecycle/reset/action-barrier, and concrete profile source. |
| Pending evidence | LiDAR timing/range/extrinsic, scan–twist skew, freshness, buffer/timeout, measured-twist validity/covariance/provenance, receipt-after-barrier timeout, TF alignment and runtime publisher evidence remain `PENDING_MEASUREMENT`; no values are added. |
| L1/L2 boundary | This candidate records L1 source disposition only. Any later creation/change of contract semantics or a public/runtime interface requires an L2 Architecture Change Record before use. Missing required pin/evidence/measurement continues to reject the whole resolved config without a partial profile/hash. |
| Candidate lifecycle | Before integration, this is a review candidate pending independent audit, separate User authorization for the exact commit, fast-forward and remote-ref verification. After those conditions, it may be described only as an integrated source-disposition governance record, not active technical semantics or resolved profile. |
| Status/authorization | No transition: WP-04 `BLOCKED_BY_CONTRACT`; Gate A structural primitives `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. No code, ROS/ROSIDL, runtime, HIL, hardware or deployment authorization. |


### WP04-GATE-B-SOURCE-DISPOSITION-POST-INTEGRATION-STATUS-CORRECTION

| Field | Value |
|---|---|
| Date | 2026-10-13 |
| Integration base / source candidate | `8b2f6d5c05ae8db8ce62285bd84afc401fb0d00c` / `513ef03cc3c8b6d2e4f2053308d8f10b4e24f56d`; source candidate parent is the integration base |
| Finding provenance | Owner-accepted F-01 HIGH: the source candidate's lifecycle wording could read as perpetually pending after integration. This entry records the supplied finding; no audit-report hash is asserted. |
| Correction scope | Status/provenance wording only in the source-disposition decision, Registry section, and this append-only Ledger entry. No source classification, source SHA, pin, pending group, measurement, technical target, active authority, or dependency fingerprint changes. |
| Candidate lifecycle | At source parent `513ef03…`, the record is a review snapshot. This exact correction candidate, before integration, requires its own independent audit, separate User authorization for its exact commit, fast-forward, and remote-ref verification. After those conditions, the record is an integrated source-disposition governance record only. |
| Post-integration boundary | No source pin or profile is created/resolved; Gate B does not start/pass; no code/runtime transition or authorization is granted. ACR rev.3 and Specification rev.5 remain active technical authority; receipt v2/QoS6 remain established; six profile-reference groups and required measurements remain pending. |
| Status/authorization | No transition: WP-04 `BLOCKED_BY_CONTRACT`; Gate A structural primitives `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. |


### WP04-OBSERVATION-INPUT-CONTRACT-V3-ARCHITECTURE-CLOSURE

| Field | Value |
|---|---|
| Date | 2026-10-13 |
| Exact integration/source base | `5497b7e1938242422594f8150b06a32fe221ee70` |
| Architecture authority | `docs/MECANUM_NAV_DRL_Architecture.docx`, SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`; unchanged and highest authority |
| Owner decision | Owner-approved L2 abstract typed-boundary contract set for five revision-v3 identities; no concrete source/profile, runtime interface, or measurement selected |
| Scope | Eight-path documentation candidate: ACR and Specification status/contract records; new `docs/OBSERVATION_INPUT_CONTRACT_V3.md`; new JCS semantic manifest; new decision record; Registry, PEP, and this append-only entry |
| Semantic manifest | `docs/architecture/OBSERVATION_INPUT_CONTRACT_V3_SEMANTIC_MANIFEST.json`; semantic-manifest SHA-256 `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb`; this identifies canonical semantic bytes and is distinct from source-file digests |
| Authority and lifecycle | At source base, ACR revision 3 / Specification revision 5 remain active; this exact candidate awaits independent audit, separate exact-commit User authorization, fast-forward, and remote-ref verification. After those conditions, it is an integration-resident L2 target-governance record only; a separate activation/change-control is still required before new technical semantics are active |
| Contract boundary | Shared exact `episode_generation`, `reset_epoch`, `runtime_generation`, and global `config_hash` binding; receipt v2 remains unchanged and has no `config_hash` field; no root `gate_b`, Gate-B-only hash, or partial profile/hash |
| Pending items | Six concrete profile-reference groups remain unselected; applicable sensor, timing, geometry, freshness, skew, timeout/buffer, twist, TF, lifecycle, and runtime publisher evidence remain pending / `PENDING_MEASUREMENT`; no resolved profile is created |
| Evidence boundary | No source pin, code, ROSIDL, adapter, compiler, test, runtime, HIL, hardware, or deployment evidence is created. Manifest canonical-byte validation is mechanical candidate-file validation only |
| Status/authorization | No transition: WP-04 `BLOCKED_BY_CONTRACT`; Gate A structural primitives `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED` |


### WP04-OIC-V3-SEMANTIC-MANIFEST-DIGEST-CORRECTION

| Field | Value |
|---|---|
| Date | 2026-10-13 |
| Integration base / source parent | `5497b7e1938242422594f8150b06a32fe221ee70` / `af6ce9c2dc7388b0779315b306d178ded2338b51`; source parent is a direct child of the integration base |
| Finding | F-01: the OIC V3 header carried an incorrect semantic-manifest digest. The exact manifest at the source parent is unchanged and its canonical semantic digest is `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb`. |
| Correction scope | Documentation-only digest correction: update the OIC header to the established manifest digest, recompute its source-file SHA-256 as `d44d33843c32d1f0d5c747522f3add09bfde21fcb0884e21da93a52476cb4dfc`, and update references to that OIC source-file digest. The semantic manifest bytes/digest and contract semantics are unchanged. |
| Candidate lifecycle | At source parent `af6ce9c…`, the source candidate contains the F-01 discrepancy. This exact correction candidate is a review candidate pending independent audit, separate exact-commit User authorization, fast-forward, and remote-ref verification. After those conditions it remains an integrated L2 target-governance record only; a separate activation/change-control is required for technical semantics. |
| Authority and pending boundary | ACR revision 3 / Observation V3 Specification revision 5 remain active technical authority. Six concrete profile-reference groups and required source pins, evidence, and measurements remain pending; no profile is resolved and Gate B does not start/pass. |
| Status/authorization | No transition: WP-04 `BLOCKED_BY_CONTRACT`; Gate A structural primitives `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. No code, ROS/ROSIDL, runtime, HIL, hardware, or deployment authorization. |


### WP04-OIC-V3-TECHNICAL-ACTIVATION

| Field | Value |
|---|---|
| Date | 2026-10-13 |
| Exact source/integration base | `23a7e21e320395091de4dd1b1700845355dc4391` |
| Architecture authority | `docs/MECANUM_NAV_DRL_Architecture.docx`; SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`; unchanged and highest authority |
| Dependency fingerprints | Integrated abstract OIC source `af6ce9c2dc7388b0779315b306d178ded2338b51`; integrated digest correction `23a7e21e320395091de4dd1b1700845355dc4391`; OIC source-file SHA-256 `d44d33843c32d1f0d5c747522f3add09bfde21fcb0884e21da93a52476cb4dfc`; semantic-manifest SHA-256 `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb`. Source-file and semantic-manifest digests are distinct evidence roles. |
| Change class and scope | L2 abstract technical-authority activation candidate: ACR revision 8, Observation Specification revision 10, decision record, Registry, PEP-001 revision 0.10.5, and this append-only entry. OIC document and manifest bytes are unchanged. |
| Activation lifecycle | At source base `23a7e21…`, this exact work is an activation review candidate; no audit or authorization is inferred from Git. Only after independent audit PASS for the exact candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification does OIC V3 and its manifest become `ACTIVE_TECHNICAL_AUTHORITY_FOR_ABSTRACT_OIC_V3_CONTRACT_SEMANTICS_ONLY`. The effective authority is the frozen Architecture and ACR revision-3 / Specification revision-5 base authority as extended by those abstract OIC semantics; revisions 3/5 are not the sole authority for that typed boundary. |
| Activation boundary / next prerequisite | No concrete source, topic, publisher, package, runtime profile, immutable source pin, measurement, or profile instance is selected. Six profile-reference groups and required evidence/measurements remain unresolved. The next prerequisite is L1 canonical source-pin/profile-manifest closure, not code. The 16-root global config hash, nested `observation.input_profile`, receipt v2, QoS6, and contract semantics are unchanged. |
| Status/authorization | No transition: WP-04 `BLOCKED_BY_CONTRACT`; Gate A structural primitives `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. No profile resolution, code, ROS/ROSIDL, runtime, HIL, hardware, or deployment authority. |


### WP04-OIC-V3-STATIC-REFERENCE-MANIFEST-CLOSURE

| Field | Value |
|---|---|
| Date | 2026-10-13 |
| Exact integration/source base | `2186cd061ee126611f7afaacbbd9e8e2319ecc91` |
| Architecture authority | `docs/MECANUM_NAV_DRL_Architecture.docx`, SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`; unchanged and highest authority |
| Active OIC authority | `docs/OBSERVATION_INPUT_CONTRACT_V3.md`; source-file SHA-256 `d44d33843c32d1f0d5c747522f3add09bfde21fcb0884e21da93a52476cb4dfc`; semantic manifest `docs/architecture/OBSERVATION_INPUT_CONTRACT_V3_SEMANTIC_MANIFEST.json`; semantic-manifest SHA-256 `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb` |
| Established receipt/QoS pins | Receipt v2 interface SHA-256 `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`; dependency-closure v1 SHA-256 `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73`; QoS6 document SHA-256 `4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022`; QoS transport manifest v2 SHA-256 `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620` |
| Candidate scope | Four-path L1 documentation/governance candidate: new seven-group static-reference JSON and decision record, Registry entry, and this append-only Ledger entry. No contract semantics, runtime source, profile instance, code, or measurement is created. |
| Manifest identity | `docs/governance/evidence/WP-04_OBSERVATION_INPUT_PROFILE_V3_STATIC_REFERENCE_MANIFEST.json`; exactly five active OIC v3 contract-reference groups plus established final-issued receipt v2 and QoS6 groups. OIC document SHA and semantic-manifest digest, receipt/schema/dependency hashes, QoS document and transport-manifest hashes are distinct evidence roles. No `config_hash` is computed or published. |
| Candidate lifecycle | At exact source base `2186cd061ee126611f7afaacbbd9e8e2319ecc91`, this is a review-candidate snapshot pending independent audit, separate exact-commit User authorization, fast-forward, and remote-ref verification. After those conditions for this exact candidate, it is an integrated L1 static-reference governance record only, not a resolved profile or runtime evidence. |
| Pending boundary | Concrete runtime source bindings for LiDAR, LocalReference, measured twist, frame/TF, lifecycle/barrier, and profile source remain unresolved. Required measurements/evidence remain pending, including LiDAR timing/range/extrinsic, scan-to-twist skew, freshness/buffer/timeout, twist validity/covariance/provenance, receipt-after-barrier timeout, TF alignment, and runtime publisher evidence. Missing any required source pin, measurement, or evidence means no profile resolution, no global config hash, and no Navigation/Gate B bring-up; no default/alias/legacy/simulation substitution. |
| Status/authorization | No transition: WP-04 `BLOCKED_BY_CONTRACT`; Gate A structural primitives `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. No code, test, ROS/ROSIDL, runtime, HIL, hardware, or deployment authority. |


### WP04-OIC-V3-RUNTIME-BINDING-ARCHITECTURE-DECISION

| Field | Value |
|---|---|
| Date | 2026-10-13 |
| Exact source/integration base | `7e72998c7bc8f9fb0a042672a9444879cd9baedd` |
| Architecture authority | `docs/MECANUM_NAV_DRL_Architecture.docx`; SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`; unchanged and highest authority |
| Active dependency fingerprints | OIC source SHA-256 `d44d33843c32d1f0d5c747522f3add09bfde21fcb0884e21da93a52476cb4dfc`; OIC semantic-manifest SHA-256 `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb`; static-reference manifest SHA-256 `639a83454fe9a1e1bf49f98334ba81aa5a78944644d99dfbe599082f4b5918d6`; receipt v2/QoS6 established pins unchanged |
| Change class and scope | L2 public runtime-interface/TF/lifecycle target-binding candidate; seven allowlisted documentation/governance paths, including runtime-binding contract SHA-256 `ce2c979788658b45facbabdc3f7063f8663bf71380ab839531afcf7e204173b1` and semantic-manifest SHA-256 `e800f7169304624d81334c26a638c27c9cbaa11a6df0ba5531b1718ee914f76f` |
| Owner-selected target | LiDAR `/scan` LaserScan exact `lidar_frame`; LocalReference from successful ComputePathToPose Path in `map` to `base_link`; measured twist `/odometry/filtered` Odometry in `odom`/`base_link` from one target EKF; TF ownership localization/EKF/robot_state_publisher for the three specified edges; SafetyLifecycle action/reset barrier and lifecycle tuple with unchanged receipt v2/QoS6/internal typed ingress context. |
| Candidate lifecycle | At the exact source base this is a review-candidate snapshot. After independent audit PASS, separate exact User authorization, fast-forward, and remote-ref verification for the exact candidate, it becomes active L2 runtime-binding technical authority for target bindings only; no separate activation candidate is required. No audit or authorization is inferred from Git ancestry. |
| Pending boundary | No executable source/package/launch/EKF pin, concrete profile, geometry/extrinsic, range, covariance, timeout, cadence, latency, freshness, skew, buffer, or runtime evidence is selected. Required implementation pins remain `PENDING_IMPLEMENTATION_SOURCE_PIN`; required measurements remain `PENDING_MEASUREMENT`. Missing required pins/evidence fail closed: no profile resolution, global `config_hash`, or Gate B bring-up. |
| Non-goals/status | OIC semantics, OIC/static manifests, receipt v2/QoS6, global 16-root hash policy and `observation.input_profile` are unchanged. No profile resolution, Gate B start/pass, WP-04 closure, code/runtime/HIL/hardware/deployment authorization, or status transition. WP-04 `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. |


### WP04-OIC-V3-RUNTIME-BINDING-ACR-REVISION-TRACEABILITY-CORRECTION

| Field | Value |
|---|---|
| Date | 2026-10-13 |
| Exact integration base / source parent | `7e72998c7bc8f9fb0a042672a9444879cd9baedd` / `69b84c68324b0958140da203bccde46fb9f9f618` |
| Finding | `F-01`, recorded as `USER_SUPPLIED_INDEPENDENT_AUDIT_EVIDENCE`: the Registry called the new runtime-binding record “ACR revision 9” although its identity is `ACR-OBSERVATION-RUNTIME-BINDING-V3`, Record revision `1`. |
| Correction scope | Registry authority/revision traceability wording only, plus this append-only Ledger entry. The base `ARCH_CHANGE_RECORD_OBSERVATION_INPUT_PROFILE_V3.md` is Record revision 8; Observation V3 Specification revision 9 is Specification provenance, not an ACR revision. |
| Technical and status boundary | No change to five target runtime bindings, pins, pending measurements, fail-closed behavior, active authority, WP status, dependency, or authorization. No profile, `config_hash`, source pin, timeout, package version, runtime evidence, or measurement is created. |
| Candidate lifecycle | The correction candidate still requires its own independent audit and separate exact-commit User decision to integrate. Only after authorization, fast-forward, and remote-ref verification may it be integrated. This entry does not infer audit or authorization from Git ancestry. |
| Supersedes | F-01 Registry ACR revision/identity traceability wording in source candidate `69b84c68324b0958140da203bccde46fb9f9f618`; no historical Ledger entry is edited or removed. |
| Status/authorization | No transition: WP-04 `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. |


### WP04-OIC-V3-BOUNDED-FAIL-CLOSED-IMPLEMENTATION-AUTHORIZATION

| Field | Value |
|---|---|
| Date | 2026-10-13 |
| Exact integration base | `5e5075b5860034527350629c686c2d26651fbfeb` |
| Authority fingerprints | Architecture DOCX SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`; active OIC source-file SHA-256 `d44d33843c32d1f0d5c747522f3add09bfde21fcb0884e21da93a52476cb4dfc`; OIC semantic-manifest SHA-256 `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb`; runtime-binding contract SHA-256 `ce2c979788658b45facbabdc3f7063f8663bf71380ab839531afcf7e204173b1`; runtime-binding semantic-manifest SHA-256 `e800f7169304624d81334c26a638c27c9cbaa11a6df0ba5531b1718ee914f76f` |
| Change class and scope | L1 bounded code-authorization governance candidate; exact four-path scope: new decision record, Registry, PEP-001, and this append-only entry. No code or implementation evidence is created. |
| Conditional authorization | Only after independent audit PASS for the exact candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification: `BOUNDED_FAIL_CLOSED_IMPLEMENTATION_AUTHORIZATION` for typed internal snapshot/context structures, strict fail-closed validator, pure-core assembler/synchronizer, and dependency-injected internal input boundaries only. |
| Evidence boundary | No audit verdict or authorization is inferred from Git ancestry. At the exact base/current review snapshot, `CODE_AUTHORIZATION: NOT_GRANTED`. The candidate records the four lifecycle conditions; post-integration scope is bounded governance authorization only. |
| Fail-closed invariants | Missing/mismatched contract identity, lifecycle tuple, config binding, or invalid typed input => reject/no vector. No partial vector/hash, defaults, alias/coercion, zero-fill, legacy/simulation fallback, or fabricated source/version/measurement. Required source/package/version pins and measurements remain pending. |
| Explicit non-goals | No ROS endpoints or runtime ingress; no launch/runtime YAML, TF runtime, Nav2/AMCL/EKF setup, public ROS interface, `ResolvedConfig`, global `config_hash`, resolved profile, Gate B start/pass, WP-04 closure, test acceptance claim, runtime/HIL/hardware/deployment authority, or WP-05/map change. `RUNTIME_APPROVED: NOT_APPROVED`. |
| Status/dependency | No transition at source base: WP-04 `BLOCKED_BY_CONTRACT`; Gate A structural primitives `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`. |


### WP04-OIC-V3-BOUNDED-CODE-AUTHORIZATION-STATUS-CORRECTION

| Field | Value |
|---|---|
| Date | 2026-10-13 |
| Integration base / direct parent | `5e5075b5860034527350629c686c2d26651fbfeb` / `a7c5811e15e3dd909b655b199372299c3cf2e5d9` |
| Finding | F-01, recorded as `USER_SUPPLIED_INDEPENDENT_AUDIT_EVIDENCE`: the source candidate did not express the canonical post-integration code-authorization status token consistently across the decision, Registry, PEP, and Ledger. No audit-report hash is asserted. |
| Correction scope | Status-token and lifecycle traceability only across the four allowlisted governance paths. It does not change L1 authorization scope, fail-closed rules, technical authority, profile/source pins, measurements, Gate B, WP-05, or runtime authorization. |
| Source-base/review status | Before integration of the exact correction candidate: `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. Review push and Git ancestry do not grant authorization. |
| Conditional post-integration status | Only after independent audit PASS for the exact correction candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification: `CODE_AUTHORIZATION: GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_ONLY`; `RUNTIME_APPROVED: NOT_APPROVED`. `BOUNDED_FAIL_CLOSED_IMPLEMENTATION_AUTHORIZATION` remains the scope name; the status token is its canonical post-integration representation. |
| Boundary | The token retains only the previously recorded typed snapshot/context structures, fail-closed validators, pure-core assembler/synchronizer seams, and dependency-injected internal adapter boundaries. No ROS/runtime, profile/config resolution, inferred source/version pin, Gate B start/pass, or WP-05/map change is authorized. |
| Supersedes | The ambiguous post-integration status routing in the source candidate `a7c5811e15e3dd909b655b199372299c3cf2e5d9`; prior Ledger history remains byte-for-byte unchanged. |
| Status | WP-04 `BLOCKED_BY_CONTRACT`; Gate A structural primitives `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; source-base `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`. |


### WP05-NAVIGATION-V1-RUNTIME-BINDING-REFRESH-16E4D812 — review candidate preparation

- Exact integration base: `16e4d81296f5db0fb322349bfe673cb5bd2c1534`.
- Current review branch: `wp05-navigation-v1-runtime-binding-refresh-16e4d812`; candidate commit is created only after the checks recorded for this work package.
- Source-content provenance only: prior review candidate `wp05-navigation-v1-runtime-binding-architecture-5249a11@4ff6b96783c940e7f4c523ed553d3ad75f8a5a55`, direct parent `5249a11e69408abf845e8568258989a70edefb35`. It was not cherry-picked/rebased, is not this candidate's parent/current base, and is not treated as integrated or audit-passed by this refresh.
- Scope: refresh the seven allowlisted L2 governance/contract/manifest paths; no map artifact, code, runtime config, ROSIDL, or WP-04 code change.
- Target authority is conditional on independent audit PASS for the exact successor commit, separate exact-commit User authorization, fast-forward, and remote-ref verification. After those conditions, status is `ACTIVE_L2_NAVIGATION_V1_RUNTIME_BINDING_TECHNICAL_AUTHORITY_FOR_TARGET_BINDINGS_ONLY`; no separate activation candidate is required.
- Pending: package/version and config/launch source pins; AMCL/EKF parameter/config pins; scan/TF adapter and geometry source; remap/namespace; lifecycle/startup pins; TF/publisher, scan, EKF, lifecycle, localization-quality, and map/runtime measurements. Fail closed: no resolved profile, global `config_hash`, or bring-up.
- Status unchanged: WP-05 `OPEN`; map draft/not approved; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; WP-04 `BLOCKED_BY_CONTRACT`, Gate A `PASSED`, Gate B `NOT_STARTED`; current bounded internal-seam `CODE_AUTHORIZATION` remains unchanged; `RUNTIME_APPROVED: NOT_APPROVED`.
- `supersedes`: none; this is a new review snapshot, not a correction of historical Ledger entries.

### WP04-OIC-V3-NONEXECUTING-OBSERVATION-INGRESS-SOURCE-AUTHORIZATION

| Field | Value |
|---|---|
| Date | 2026-10-13 |
| Exact integration/source base | `346138368a5a3599779f36d629c6fc0e0233338a` |
| Change class and scope | L1 bounded implementation-source authorization candidate; exact four-path scope: new decision record, Registry, PEP-001, and this append-only entry. No source/test file is created. |
| Dependency fingerprints | Architecture SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`; OIC source SHA-256 `d44d33843c32d1f0d5c747522f3add09bfde21fcb0884e21da93a52476cb4dfc`; OIC semantic-manifest SHA-256 `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb`; WP-04 runtime-binding semantic-manifest SHA-256 `e800f7169304624d81334c26a638c27c9cbaa11a6df0ba5531b1718ee914f76f`; WP-05 Navigation V1 runtime-binding ACR SHA-256 `3e74cdcb6136f60a6ad2822a853f2ae9926cf971059f3c2470c874802d6fae0d` and semantic-manifest SHA-256 `33855c9c95f9c0594ddd8805514658e4f5cb8255a219938a7913438470edbf31`; integrated pure-core candidate `16e4d81296f5db0fb322349bfe673cb5bd2c1534`; receipt v2/QoS6 established pins unchanged. |
| Owner decision recorded | `mecanum_nav_rl` owns future nonexecuting observation-ingress adapter sources and related static/unit tests, limited to the two approved package directories. ROS message objects may be accepted as typed inputs, with no runtime graph or ROS operations. Target bindings and fail-closed boundaries are in the companion decision. |
| Source-base/current status | Before integration of this exact candidate: `CODE_AUTHORIZATION: GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_ONLY`; `RUNTIME_APPROVED: NOT_APPROVED`. No audit or authorization is inferred from this candidate's Git ancestry or review push. |
| Conditional post-integration status | Only after independent audit PASS for the exact candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification: `CODE_AUTHORIZATION: GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_AND_NONEXECUTING_OBSERVATION_INGRESS_ADAPTER_SOURCES_ONLY`; `RUNTIME_APPROVED: NOT_APPROVED`. |
| Boundary and non-goals | No code/test source, ROS graph, launch/runtime config, profile, global `config_hash`, package/version pin, measurement, map approval, runtime evidence, Gate B start/pass, WP-04 closure, WP-05 status change, runtime/HIL/hardware/deploy authority. |
| Ledger semantics | Append-only; no prior history edited or removed. This record is a review snapshot before integration and, after the four conditions, an integrated L1 bounded implementation-source authorization only—not runtime approval, implementation completion, or runtime evidence. |


### WP05-NAVIGATION-V1-DEPENDENCY-LOCK-AND-STATIC-BRINGUP-SOURCE-AUTHORIZATION — review candidate at `2a537a9cfa9f9c5b0bec1f9c629fec8e2f98a225`

- Candidate branch: `wp05-navigation-v1-dependency-lock-source-authorization-2a537a`; exact source-base review snapshot `2a537a9cfa9f9c5b0bec1f9c629fec8e2f98a225`.
- Scope: five governance paths defining the future dependency-lock schema, `mecanum_nav_bringup` ownership/layout, and conditional static-source/static-acceptance authorization. No package/source/launch/runtime YAML/test or lock instance is created here.
- Dependency fingerprints: Architecture `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`; WP-05 L2 ACR `3e74cdcb6136f60a6ad2822a853f2ae9926cf971059f3c2470c874802d6fae0d`; L2 semantic manifest `33855c9c95f9c0594ddd8805514658e4f5cb8255a219938a7913438470edbf31`; WP-04 ingress-authorization decision `d6df3bf6811918adb044ea890f8be8b3ed67342820641f9b46e47f6fbd1ddde4`; `warehouse_map2` map-content hash `2bd9ff0a40eaeb61c2359aab4bb213da623ab56746debe591edd4a54c2229f90`.
- Current pre-integration status: `CODE_AUTHORIZATION: GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_AND_NONEXECUTING_OBSERVATION_INGRESS_ADAPTER_SOURCES_ONLY`; `RUNTIME_APPROVED: NOT_APPROVED`. After independent audit PASS for exact candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification only: `CODE_AUTHORIZATION: GRANTED_BOUNDED_FAIL_CLOSED_INTERNAL_SEAMS_NONEXECUTING_OBSERVATION_INGRESS_AND_STATIC_NAVIGATION_V1_BRINGUP_SOURCES_ONLY`; `RUNTIME_APPROVED: NOT_APPROVED`.
- Candidate status: pending independent audit and separate exact-commit User authorization. Push/ancestry alone does not grant the extension.
- Pending vocabulary: `PENDING_EXTERNAL_PACKAGE_LOCK`; `PENDING_IMPLEMENTATION_SOURCE_PIN`. No actual package versions, `.deb` digests, source SHAs, parameter values, geometry, or launch composition are populated.
- Fail-closed: no resolved Navigation V1 profile/global `config_hash`, bring-up, map approval, runtime/HIL/hardware/deployment authority. `warehouse_map2` remains draft; world frame `NOT_DECLARED`; runtime compatibility `NOT_VALIDATED`. WP-04 remains blocked, Gate A passed, Gate B not started; WP-05 remains open.
- `supersedes`: none; this is a new append-only candidate entry.


### WP04-WP05-RUNTIME-MEASUREMENT-PLAN-AND-EVIDENCE-SCHEMA — review candidate at `cc0018560b20a52fa6d3c9cf26abbe0ef4c6227a`

| Field | Value |
|---|---|
| Date | 2026-10-14 |
| Exact integration/source base | `cc0018560b20a52fa6d3c9cf26abbe0ef4c6227a` |
| Change class and scope | `L1_RUNTIME_MEASUREMENT_GOVERNANCE_PLAN_ONLY`; exactly five governance paths: decision, evidence JSON Schema, Registry, PEP-001, and this append-only entry. No harness, runtime config, source pin, lock instance, measurement result, threshold, profile, `config_hash`, or approval artifact. |
| Dependency fingerprints | Architecture `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`; OIC source `d44d33843c32d1f0d5c747522f3add09bfde21fcb0884e21da93a52476cb4dfc`; OIC semantic manifest `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb`; WP-04 runtime-binding manifest `e800f7169304624d81334c26a638c27c9cbaa11a6df0ba5531b1718ee914f76f`; WP-05 Navigation V1 runtime-binding ACR `3e74cdcb6136f60a6ad2822a853f2ae9926cf971059f3c2470c874802d6fae0d` and manifest `33855c9c95f9c0594ddd8805514658e4f5cb8255a219938a7913438470edbf31`; warehouse_map2 content hash `2bd9ff0a40eaeb61c2359aab4bb213da623ab56746debe591edd4a54c2229f90`. These identify referenced dependencies and do not select new pins. |
| Source-base lifecycle | At exact base above, the decision/schema are review-candidate snapshots. Independent audit PASS, separate exact-commit User authorization, fast-forward, and remote-ref verification remain required. |
| Conditional post-integration status | Only after all four exact-candidate conditions: `INTEGRATED_L1_RUNTIME_MEASUREMENT_GOVERNANCE_PLAN_ONLY`; not active L2 technical authority, runtime evidence, runtime authorization, map approval, or Gate B pass. |
| Pending | Source/package/version pins, immutable lock instances, required measurements and any independently authorized collection/acceptance review. No threshold is set; measurement values remain `PENDING_MEASUREMENT`. |
| Status and boundaries | WP-04 `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; map draft/not approved; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; current code authorization unchanged; `RUNTIME_APPROVED: NOT_APPROVED`. Ledger remains append-only; this candidate is not current as integrated merely because it is pushed or has Git ancestry. |
| `supersedes` | None; new entry. No historical Ledger entry is modified or removed. |


### WP04-WP05-RUNTIME-MEASUREMENT-SCHEMA-MINITEMS-CORRECTION — review snapshot

| Field | Value |
|---|---|
| Date | 2026-10-14 |
| Exact integration base | `cc0018560b20a52fa6d3c9cf26abbe0ef4c6227a` |
| Direct parent/source candidate | `5b8ac68f51814f9520e1e72a28da5ad35fcfacea`; sole parent `cc0018560b20a52fa6d3c9cf26abbe0ef4c6227a` |
| Finding | `F-01`; `USER_SUPPLIED_INDEPENDENT_AUDIT_EVIDENCE`; no audit-report hash asserted. |
| Correction scope | Exactly five allowlisted governance paths. Move `minItems: 1` to the acceptance-conditional `metrics_inventory` array level; preserve schema ID and revision `1`. No other schema or plan semantics change. |
| Lifecycle | This correction is a review snapshot. Independent audit PASS for the exact correction, separate exact-commit User authorization, fast-forward, and remote-ref verification remain required. Only after all conditions may records be described as `INTEGRATED_L1_RUNTIME_MEASUREMENT_GOVERNANCE_PLAN_ONLY`. |
| Boundary/status | No source/package pin or lock instance, threshold, harness, measurement result, profile, `config_hash`, map approval, runtime authorization, or acceptance conclusion. WP-04 `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; map draft/not approved; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; code authorization unchanged; `RUNTIME_APPROVED: NOT_APPROVED`. |
| `supersedes` | None; append-only correction entry. Earlier Ledger history remains byte-for-byte unchanged. |


### WP04-OIC-V3-IMPLEMENTATION-SOURCE-PIN-CLOSURE — review snapshot

| Field | Value |
|---|---|
| Date | 2026-10-14 |
| Exact integration/source base | `8675047aa61835621f6d1e31aff567b75c87094c` |
| Change class and scope | `L1_IMPLEMENTATION_SOURCE_PIN_CLOSURE_DOCUMENTATION_ONLY`; exactly four governance paths: new implementation-source pin manifest, new decision, Registry routing, and this append-only entry. The 15 listed workspace sources are immutable-byte references at the base, not new source changes. |
| Authority fingerprints | Architecture DOCX `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`; OIC source `d44d33843c32d1f0d5c747522f3add09bfde21fcb0884e21da93a52476cb4dfc`; OIC semantic manifest `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb`; WP-04 runtime-binding manifest `e800f7169304624d81334c26a638c27c9cbaa11a6df0ba5531b1718ee914f76f`; static-reference manifest `639a83454fe9a1e1bf49f98334ba81aa5a78944644d99dfbe599082f4b5918d6`; WP-05 Navigation V1 runtime-binding ACR `3e74cdcb6136f60a6ad2822a853f2ae9926cf971059f3c2470c874802d6fae0d` and manifest `33855c9c95f9c0594ddd8805514658e4f5cb8255a219938a7913438470edbf31`. |
| Implementation-source disposition | Fifteen exact workspace paths/hashes at this base are recorded as `PINNED_IMPLEMENTATION_SOURCE_ONLY`; every entry has runtime implication `NOT_A_RUNTIME_SOURCE_PIN`. The 8 `mecanum_nav_rl` sources and 7 `mecanum_nav_bringup` sources establish source-byte provenance only. No test source is presented as runtime source. |
| Pending groups | `PENDING_EXTERNAL_PACKAGE_LOCK` for Nav2, Map Server, AMCL, `robot_localization`, RSP, TF2 and other external dependencies; `PENDING_RUNTIME_SOURCE_PIN` for LiDAR driver, Nav2 path producer, concrete AMCL/EKF/RSP config/launch, lifecycle/startup, remap/namespace and map binding; `PENDING_MEASUREMENT` for LiDAR cadence/latency/range/extrinsic, scan–twist skew, buffer, TF graph, publisher uniqueness, lifecycle health and localization quality. |
| Lifecycle/evidence boundary | At this base this is a review-candidate snapshot. Only after independent audit PASS for the exact candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification is it an integrated L1 implementation-source-pin governance record. No audit hash is asserted. Implementation-source provenance is not runtime evidence and does not activate authority. |
| Non-goals/status | No runtime source selection, external package/ROS-distribution lock, resolved profile, global `config_hash`, Gate B bring-up, map approval, runtime evidence, or code/runtime authorization change. WP-04 `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; map `DRAFT_ON_INTEGRATION_NOT_APPROVED`; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; `RUNTIME_APPROVED: NOT_APPROVED`. |
| `supersedes` | None; new append-only entry. No historical Ledger content is edited or removed. |


### ARCHITECTURE-AUTHORITY-PROVENANCE-RECONCILIATION-432EEAC — review snapshot

| Field | Value |
|---|---|
| Work package | `ARCHITECTURE-AUTHORITY-PROVENANCE-RECONCILIATION-432EEAC` |
| Exact integration base | `457926439220756f5dc18ed62c9d1143715668fc` |
| Candidate branch | `architecture-authority-provenance-reconciliation-4579264` |
| Finding provenance | `USER_SUPPLIED_INDEPENDENT_AUDIT_EVIDENCE`; no audit-report hash is asserted. |
| Authority identities | Current Git-verifiable Architecture DOCX blob SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`; historical provenance only is commit `86beff623dba3683f643c851a4a1374c635178b3`, SHA-256 `f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860`; transition commit `988a74b529fdb4bcf77f341db5c6d115e8511a9b`. |
| Scope | Reconcile provenance/status wording in the exact 26 listed legacy/draft documents; add one decision record and Registry routing; append this entry. Architecture DOCX and all technical content remain unchanged. |
| Candidate lifecycle | Review candidate only at the exact source base. Independent audit, separate exact-commit User authorization, fast-forward, and remote-ref verification are required; none is inferred from Git ancestry or a review push. |
| Evidence boundary | `GOVERNANCE_PROVENANCE_RECONCILIATION_ONLY`. No technical semantics or status/dependency transition is created. WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; map remains draft; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; `RUNTIME_APPROVED: NOT_APPROVED`. |
| `supersedes` | None; append-only entry. Earlier Ledger history is not changed. |

### WP05-NAVIGATION-V1-DEPENDENCY-LOCK-PROVENANCE-ENVELOPE-L2-AMENDMENT-CORRECTED — review snapshot

| Field | Value |
|---|---|
| Date | 2026-10-15 |
| Exact integration/source base | `f23af59d7a9458175928c2647532339ff933158b` |
| Scope | L2 governance-schema interface amendment: require a closed typed `artifact_baseline_provenance` envelope; update static validator and synthetic test fixture/tests. The 14 logical roots and package-lock semantics remain unchanged; `launch_ros` is not a logical root. |
| Lifecycle | Review candidate only at the exact source-base snapshot. Independent audit PASS, separate explicit User authorization for the exact commit, fast-forward, and remote-ref verification are required before this amendment is described as active authority for dependency-lock provenance schema semantics only. |
| Evidence boundary | Offline structural validation of caller-supplied values only. No filesystem, artifact bundle, Docker, network, or runtime inspection; no assertion that external artifacts exist. No concrete lock instance, profile source, package pin, profile resolution, or `config_hash`. |
| Non-goals/status | No Navigation runtime semantics, TF/lifecycle ownership, map approval, runtime authorization, or WP-04 change. WP-05 `OPEN`; map remains draft; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; `RUNTIME_APPROVED: NOT_APPROVED`; WP-04 `BLOCKED_BY_CONTRACT`; Gate B `NOT_STARTED`. |
| `supersedes` | None; append-only entry. |


### WP05-CONCRETE-14-ROOT-EXTERNAL-DEPENDENCY-LOCK-RECORD — review snapshot

| Field | Value |
|---|---|
| Date | 2026-10-15 |
| Exact integration/source base | `ab5c62f866985b72cbaff370fae38cdd6192dbcc` |
| Candidate branch | `wp05-concrete-14-root-external-dependency-lock-ab5c62f` |
| Scope | L1 external dependency-lock record and focused static test; exactly six allowlisted paths. The JSON lock conforms to schema v2 with exactly 14 ordered logical roots and an empty `workspace_source_locks` array. |
| External artifact provenance | Collection source commit `f23af59d7a9458175928c2647532339ff933158b`, separate from the candidate base; closure manifest SHA-256 `54077ab6ee43af793ec266f92e6ea74fc21ee5af9606b1939ca83fc49714600e`; closure 1,280 artifacts/700,260,532 bytes; base image `ubuntu@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55`. The artifact locator is not runtime authority. |
| Lifecycle | Review candidate only. Independent audit PASS for the exact candidate, separate explicit User authorization for that exact commit, fast-forward, and remote-ref verification remain required. |
| Evidence boundary | `EXTERNAL_PACKAGE_LOCK_PROVENANCE_ONLY`. Local `.deb` identity/version/architecture/hash were checked against the closure manifest. The record is not a complete runtime-validator input because ten workspace-source roles are absent; no workspace source pin or profile is created. |
| Pending/non-goals | No static profile source, `config_hash`, map approval, world-frame validation, runtime compatibility evidence, Gate B pass, runtime evidence, or runtime authorization. `warehouse_map2` remains draft/not approved; WP-05 `OPEN`; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; `RUNTIME_APPROVED: NOT_APPROVED`; WP-04 `BLOCKED_BY_CONTRACT`; Gate B `NOT_STARTED`. |
| `supersedes` | None; append-only entry. Earlier Ledger history is not changed. |

### WP05-NAVIGATION-V1-STATIC-POLICY-SOURCE-PIN-CLOSURE — review snapshot

| Field | Value |
|---|---|
| Date | 2026-10-15 |
| Exact integration/source base | `c1d37b3d7ec349c0942790063d57887e5d201484` |
| Scope | L1 provenance closure for the three existing static policy sources, recorded as `PINNED_STATIC_POLICY_SOURCE_ONLY`; exactly four allowlisted paths. |
| Source identity | The manifest pins commit `c1d37b3d7ec349c0942790063d57887e5d201484` and exact path/SHA-256 pairs for namespace/remap, lifecycle/startup, and health-gate policy sources. |
| Evidence boundary | `STATIC_POLICY_SOURCE_PROVENANCE_ONLY`. This records Git source identity only; policy content remains `STATIC_TEMPLATE_ONLY`, with `runtime_eligible: false`. |
| Pending/non-goals | All ten workspace-source roles remain `PENDING_IMPLEMENTATION_SOURCE_PIN`; no `workspace_source_locks` update, Nav2 activation, lifecycle transition, runtime graph, profile resolution, `config_hash`, map approval, runtime evidence, or runtime authorization. WP-05 remains `OPEN`; map remains draft/not approved; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; `RUNTIME_APPROVED: NOT_APPROVED`; WP-04 `BLOCKED_BY_CONTRACT`; Gate B `NOT_STARTED`. |
| Candidate lifecycle | Review candidate only. No audit PASS, integration of this candidate, or authorization is asserted. |
| `supersedes` | None; append-only entry. Earlier Ledger history remains byte-for-byte unchanged. |
### WP04-WP05-SHARED-LIDAR-FRAME-TF-RSP-OWNERSHIP-DECISION — review candidate

| Field | Value |
|---|---|
| Exact integration/source base | `de71ae4d4ecb86724b1a02bdccad6f70315de7bc` |
| Provenance | `USER_SUPPLIED_ARCHITECT_OWNER_DECISION`; no audit-report hash or Git-derived Owner decision is asserted. |
| Scope | L2 public frame identity/TF ownership governance only. Literal `lidar_frame` is the shared public frame; `robot_state_publisher` is sole target owner of direct edge `base_link → lidar_frame`. `RPLiDAR_A1M8_1` is `LEGACY_GEOMETRY_PROVENANCE_ONLY`; legacy transform remains `PENDING_MEASUREMENT_AND_CANONICAL_SOURCE_SELECTION`. |
| Candidate lifecycle | Review-only at this exact source-base snapshot. Independent audit PASS for the exact candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification are required before the conditional status `ACTIVE_L2_SHARED_TF_RSP_GOVERNANCE_FOR_FRAME_ID_AND_OWNERSHIP_ONLY`. |
| Evidence boundary | Governance decision only. No robot-description source, geometry pin/verification, measurement, runtime graph/evidence, source pin, profile, `config_hash`, map approval, world-frame declaration, or runtime authorization is created. Legacy Xacro values are not copied or selected. |
| Fail-closed/pending | Canonical RSP source design and pin plus measurement-backed extrinsic selection remain pending; frame mismatch, alias/bridge/static transform, missing evidence/pin, or owner conflict blocks profile resolution, Nav2 baseline, Observation V3 runtime vector, and Gate B start/pass. |
| Status | WP-04 `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; map `DRAFT_ON_INTEGRATION_NOT_APPROVED`; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; `RUNTIME_APPROVED: NOT_APPROVED`. |
| `supersedes` | None; new append-only entry. Existing Ledger history is unchanged. |
### WP04-WP05-CANONICAL-RSP-DESCRIPTION-SOURCE-CREATION-AUTHORIZATION — review candidate

| Field | Value |
|---|---|
| Exact integration/source base | `fa862f26eed6cfa30a553ccf6f1befcad532a1f9` |
| Provenance | `USER_SUPPLIED_ARCHITECT_OWNER_DECISION`; no audit result or report hash is asserted. |
| Scope | L1 conditional authorization for a later canonical RSP description-source candidate within integrated L2 `base_link → lidar_frame` semantics; future allowlist is exactly four paths under `ROBOT_URDF_final_description`. This candidate creates no source. |
| Lifecycle | Review-only. Audit PASS for this exact candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification are required before `INTEGRATED_L1_CANONICAL_RSP_DESCRIPTION_SOURCE_CREATION_AUTHORIZATION_ONLY`. A later source candidate additionally requires the complete extrinsic packet and explicit Owner acceptance. |
| Evidence boundary | No source pin, geometry verification, measurement, runtime graph/evidence, profile, `config_hash`, map approval, world-frame declaration, Gate B authorization, or runtime authorization. Legacy `RPLiDAR_A1M8_1` geometry remains provenance only and is not copied or pinned. |
| Pending prerequisite | Extrinsic evidence packet: robot/LiDAR identity; `base_link` coordinate convention; six finite `x/y/z/roll/pitch/yaw` values; method, instrument, date, operator; repeated observations; uncertainty; raw evidence digest; explicit Owner acceptance. |
| Status | WP-04 `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; map `DRAFT_ON_INTEGRATION_NOT_APPROVED`; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; `RUNTIME_APPROVED: NOT_APPROVED`. |
| `supersedes` | None; new append-only entry. Existing Ledger history is unchanged. |
### WP04-WP05-CANONICAL-RSP-SOURCE-PIN-CLOSURE — review snapshot

| Field | Value |
|---|---|
| Date | 2026-10-15 |
| Exact integration/source base | `d4ae75e34a62730da0576f51c1a49dd67b9d8d3b` |
| Scope | L1 provenance closure for exactly four already-integrated robot-description/RSP source and static-test files. Manifest and decision are review candidates; no source file is modified by this candidate. |
| Source identity | Each exact commit/path/SHA-256 entry is `PINNED_CANONICAL_DESCRIPTION_SOURCE_ONLY`, owned by `ROBOT_URDF_final_description`, with boundary `NOT_A_RUNTIME_SOURCE_PIN`; consumer scope is WP-04 Observation V3 and WP-05 Navigation V1 source provenance only. |
| CAD packet provenance | `USER_SUPPLIED` Owner-accepted CAD nominal packet `WP04-WP05-YDLIDAR-X3PRO-CAD-EXTRINSIC-V1`, fingerprint `40fe44cb3647376b3b1f793761091e101051d7e141e4687e67e2f03632e430de`. This does not establish hardware-as-built measurement; that verification remains pending. |
| Evidence level | `INTEGRATED_SOURCE_PROVENANCE_AND_STATIC_TEST_EVIDENCE_ONLY` for the source inputs; static pytest evidence is not runtime evidence. |
| Pending/non-goals | `YDLIDAR_X3_PRO_RUNTIME_SOURCE_PIN: PENDING`; `SCAN_RUNTIME_PROFILE: PENDING`; `HARDWARE_AS_BUILT_EXTRINSIC_VERIFICATION: PENDING`. No runtime source pin, resolved profile, `config_hash`, map approval, Gate B start/pass, runtime evidence, or runtime authorization. WP-04 `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; `RUNTIME_APPROVED: NOT_APPROVED`. |
| Candidate lifecycle | Review-only at this exact source-base snapshot. No independent audit PASS, integration, or authorization for this candidate is asserted. |
| `supersedes` | None; append-only entry. Earlier Ledger history remains byte-for-byte unchanged. |


### WP04-YDLIDAR-X3-PRO-STATIC-SIMULATION-SCAN-SOURCE-CREATION-AUTHORIZATION — review snapshot

| Field | Value |
|---|---|
| Exact integration/source base | `53d56e1787487fd90c6d92e8f4f51a3eca23773f` |
| Classification | `L1_STATIC_SOURCE_CREATION_AUTHORIZATION_ONLY`; candidate review only. |
| Vendor provenance | YDLidar-SDK commit `42a82ed10d2304094c111fc63dee8e4a229b79b7`, `doc/Dataset.md`, SHA-256 `ec5e27ab30b1e4d13a4b25bc4770a106d05f54ba5b191f21374af11a6d2b4897`; X3/X3 Pro row: 115200 baud, 3 K samples/s, 0.10–8.0 m, 4–8 Hz (PWM), single-channel. |
| Future allowlist | Exactly the Gazebo description and `test_navigation_v1_lidar_frame_tf_contract.py`; no source file is changed by this governance candidate. |
| Static derivation | 6.0 Hz nominal simulation rate; 500 samples from `3000 samples/s ÷ 6.0 Hz = 500 samples/scan`; transport topic `scan` only. |
| Evidence boundary | Vendor documentation and a bounded static-source authorization only; not a runtime source pin, ROS `/scan`, `sensor_msgs/msg/LaserScan`, runtime evidence, or hardware measurement. |
| Pending | `YDLIDAR_X3_PRO_RUNTIME_SOURCE_PIN: PENDING`; `ROS_GAZEBO_SCAN_BRIDGE_SOURCE_PIN: PENDING`; `SCAN_RUNTIME_PROFILE: PENDING`; `LIDAR_CADENCE_MEASUREMENT: PENDING_MEASUREMENT`; `LIDAR_LATENCY_FRESHNESS_MEASUREMENT: PENDING_MEASUREMENT`; `NO_RETURN_BEHAVIOR_MEASUREMENT: PENDING_MEASUREMENT`; `HARDWARE_AS_BUILT_EXTRINSIC_VERIFICATION: PENDING`. |
| Status | WP-04 `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; map `DRAFT_ON_INTEGRATION_NOT_APPROVED`; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; `RUNTIME_APPROVED: NOT_APPROVED`. |
| Candidate lifecycle | Review candidate only; no audit PASS, integration, or authorization is asserted. |
| `supersedes` | None; append-only entry. Earlier Ledger history remains byte-for-byte unchanged. |


### WP00-POST-INTEGRATION-STATUS-RECONCILIATION — review snapshot at `9f2762d875024df927aa581580e746bc35436e80`

| Field | Value |
|---|---|
| Integration snapshot | `origin/integration/implementation` = `9f2762d875024df927aa581580e746bc35436e80` |
| Git sequence | WP-04 `e9695d21fb2d9c76fe7e35f0081f648bc401fe51` is the direct parent of WP-05 integration `9f2762d875024df927aa581580e746bc35436e80`. |
| WP-04 disposition | `INTEGRATED_L1_STATIC_SIMULATION_SCAN_SOURCE_CREATION_AUTHORIZATION_ONLY`; authorizes only a future static Gazebo LiDAR source candidate in the exact two-path allowlist. It is not a runtime source pin, ROS bridge, runtime profile, runtime evidence, or runtime authorization. |
| WP-05 disposition | `INTEGRATED_STATIC_TEMPLATE_SOURCES_ONLY`; exactly the AMCL, EKF, lifecycle static templates, static-source test, and `setup.py` package-data registration at the five paths listed in the corresponding Registry entry. |
| WP-05 boundary | Not `WORKSPACE_SOURCE_ROLE_PIN`, `RUNTIME_SOURCE_PIN`, `RESOLVED_PROFILE_INPUT`, `MAP_APPROVAL`, `RUNTIME_EVIDENCE`, or `RUNTIME_AUTHORIZATION`; no resolved profile or `config_hash`. This post-integration static reconciliation does not assert WP-05 pre-integration independent audit. |
| Next-step routing | L1 post-integration reconciliation → WP-04 static Gazebo LiDAR source candidate within the authorized allowlist → WP-05 source-role/profile closure preparation → each later candidate starts from exact current integration. Prospective only; later steps are not complete. |
| Historical correction | Supersedes only stale present-tense next-step wording that canonical RSP source creation remained outstanding; prior review snapshots and all earlier Ledger bytes remain unchanged. No audit, runtime evidence, or authorization is inferred from ancestry. |
| Status | `WP-04: BLOCKED_BY_CONTRACT`; `GATE_A_STRUCTURAL_PRIMITIVES: PASSED`; `GATE_B: NOT_STARTED`; `WP-05: OPEN`; `MAP_ARTIFACT: DRAFT_ON_INTEGRATION_NOT_APPROVED`; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; `RUNTIME_APPROVED: NOT_APPROVED`; `YDLIDAR_X3_PRO_RUNTIME_SOURCE_PIN: PENDING`; `ROS_GAZEBO_SCAN_BRIDGE_SOURCE_PIN: PENDING`; `SCAN_RUNTIME_PROFILE: PENDING`. |
| `supersedes` | Only stale current-routing wording about the canonical RSP source being absent; historical review snapshots remain immutable. New append-only entry. |


### WP05-NAVIGATION-V1-WORKSPACE-SOURCE-ROLE-INVENTORY-AND-DECISION-PACKET — source-base review snapshot

| Field | Value |
|---|---|
| Date / source base | 2026-10-15; exact `origin/integration/implementation` base `c59d9ea65010ff80eb0202bfaa5220c5f18f25ac`. |
| Scope | L1 governance inventory/triage and routing only; exactly five paths: new JSON inventory, new decision packet, Registry routing, PEP routing, and this appended entry. No source, test, launch, policy/template, package metadata, map, schema, external lock, or Architecture file is changed. |
| Inventory disposition | Exactly ten workspace source roles are listed in required order. Every role is `PENDING_IMPLEMENTATION_SOURCE_PIN`, `NOT_SELECTED`, and `runtime_eligibility: false`. Existing files are evidence references only with explicit dispositions; no `workspace_source_locks` are created and the external lock is unchanged. |
| Candidate lifecycle | This is the review-candidate snapshot at the exact source base. Independent audit PASS for the exact candidate, separate User authorization for the exact commit, fast-forward, and remote-ref verification are required before it may be described as an integrated inventory governance record. No audit hash or verdict is inferred or fabricated. |
| Fail-closed boundary | Missing pins/evidence means no resolved Navigation V1 profile, no global `config_hash`, no Nav2 baseline bring-up, and no runtime authorization. Pending items remain runtime LiDAR source pin; ROS–Gazebo scan bridge source pin; scan runtime profile; map approval/world-frame validation; concrete AMCL/EKF/Nav2 source/config pins; namespace/remap and lifecycle/startup runtime evidence; package/version lock applicability; and required measurements. Gazebo transport `scan` is not ROS `/scan`. |
| Preserved state | WP-04 `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; map `DRAFT_ON_INTEGRATION_NOT_APPROVED`; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; `RUNTIME_APPROVED: NOT_APPROVED`. No `CODE_AUTHORIZATION` extension or other status transition. |
| `supersedes` | None; append-only routing entry. All bytes at base are retained as an exact prefix. |


### WP05_SIM_EVAL_WAREHOUSE_MAP2_STATIC_APPROVAL_EVIDENCE_PACKET — review candidate

| Field | Value |
|---|---|
| Exact integration/source base | `7fe8b24758636dcac540b33a73bf5e3b7febbe6b` |
| Review branch | `wp05-sim-eval-map-approval-evidence-7fe8b24` |
| Candidate commit | The exact commit resolved by the review branch tip after commit creation; the delivery report supplies its SHA-1. The Ledger does not embed its own commit identifier. |
| Scope | L2 map-approval evidence schema and static selection decision for `warehouse_map2` for `sim_eval + NAV2_BASELINE`; approval-evidence scope only is `SIM_EVAL_NAV2_BASELINE_STATIC_MAP_ARTIFACT_SELECTION`. |
| Evidence level | `STATIC_ARTIFACT_PROVENANCE_AND_APPROVAL_EVIDENCE_SCHEMA_ONLY` |
| Lifecycle | Review candidate only. Independent audit PASS, separate exact-candidate User authorization, fast-forward integration, and remote-ref verification are required before the evidence record becomes integration-resident. |
| Preserved state | Map metadata remains `draft`; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; no profile resolution, `config_hash`, Map Server load evidence, runtime authority, or WP-05 closure. WP-04/WP-05 and Gate A/Gate B statuses are unchanged; `RUNTIME_APPROVED: NOT_APPROVED`. |
| `supersedes` | None; this is one append-only entry. |


### WP05_WAREHOUSE_MAP2_STATIC_APPROVAL_METADATA_ACTIVATION — review candidate

| Field | Value |
|---|---|
| Exact integration/source base | `a8eed8712ad7e20ae4d9e7665a4d07dacbde9047` |
| Review branch | `wp05-warehouse-map2-approval-activation-a8eed87` |
| Candidate commit | The commit containing this append-only entry at the review-branch tip; its exact SHA is in the delivery report. |
| Scope | L1 activation candidate for the exact `warehouse_map2` subject: approval scope `SIM_EVAL_NAV2_BASELINE_STATIC_MAP_ARTIFACT_SELECTION`; world state `DECLARED_UNVERIFIED`. |
| Lifecycle | Review only. Independent audit PASS, separate exact-candidate User authorization, fast-forward integration, and remote-ref verification remain required. |
| Proposed metadata after activation | `approval_status: approved`; `WORLD_FRAME: DECLARED_UNVERIFIED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`. Static profile input eligible for Step 5 only; not a resolved profile and not navigation-ready. Prior draft/`NOT_DECLARED` entries are historical source-base snapshots. |
| Preserved state and limits | WP-04/WP-05 and Gate A/Gate B statuses unchanged. No map bytes/content hash change, map/world equivalence, transform, metric alignment, Map Server load, AMCL/TF evidence, runtime authority, `ResolvedConfigV3`, `config_hash`, or WP-05 closure. |
| Evidence level | `STATIC_ARTIFACT_PROVENANCE_AND_APPROVAL_EVIDENCE_SCHEMA_ONLY` |
| `supersedes` | None; append-only entry. |


### WP05_SIM_EVAL_NAV2_BASELINE_STATIC_PROFILE_INPUT_CLOSURE_5A — review candidate

| Field | Value |
|---|---|
| Exact integration/source base | `2864a215782cc1901aa259a49d885fa0c132cf7a` |
| Review branch | `wp05-sim-eval-static-profile-closure-2864a21` |
| Candidate commit | The commit containing this append-only entry at the review-branch tip; exact SHA is reported in delivery. |
| Scope | Step 5A static profile input closure for `sim_eval + NAV2_BASELINE`; `STATIC_PROFILE_INPUT_CLOSURE_ONLY`, `runtime_eligible: false`. |
| Evidence level | `STATIC_PROFILE_INPUT_CLOSURE_ONLY_NOT_RUNTIME_PROFILE_RESOLUTION` |
| Candidate lifecycle | Review candidate only. Exact-candidate independent audit PASS, separate User authorization, fast-forward integration, and remote-ref verification remain required. |
| Status | WP-04 `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`; WP-05 `OPEN`; map approved only for static selection; `WORLD_FRAME: DECLARED_UNVERIFIED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; `RUNTIME_APPROVED: NOT_APPROVED`. |
| Boundary | No `workspace_source_locks`, resolved profile, `ResolvedConfigV3`, `config_hash`, runtime bridge/endpoint pin, Map Server load, launch graph, runtime evidence, runtime authorization, or WP-05 closure. WP06 and runtime assembly remain prerequisites for any later campaign. |
| `supersedes` | None; append-only entry. Historical Ledger snapshots are unchanged. |


### WP06_RECEIPT_V2_ROSIDL_ENABLEMENT_ATOMIC_REPLACEMENT — review candidate

| Field | Value |
|---|---|
| Exact integration/source base | `c8b178a2f1feee115a3a01553afaec616cabf737` |
| Review branch | `wp06-receipt-rosidl-enablement-atomic-c8b178a` |
| Classification | `L2_PUBLIC_INTERFACE_BUILD_ENABLEMENT_AND_HISTORICAL_STATUS_SUPERSESSION` |
| Candidate scope | Atomic L2 disposition for receipt v2 historical annotations plus ROSIDL generation declaration; no receipt `.msg` byte changes. |
| Candidate lifecycle | Review only. After exact-candidate independent audit PASS, separate exact-commit User authorization, integration, and remote-ref verification: `WP06_RECEIPT_V2_ROSIDL_GENERATION: IMPLEMENTED_OFFLINE_BUILD_INTERFACE_ONLY`. |
| Evidence boundary | Receipt ID/schema revision, schema SHA, QoS6 and dependency-closure pins remain unchanged. No runtime node/topic/publisher/subscriber/QoS/evidence, `ResolvedConfigV3`, `config_hash`, Gate B transition, or runtime authorization. `RUNTIME_APPROVED: NOT_APPROVED`. |
| Status | WP-04/WP-05 and Gate A/Gate B statuses unchanged. |
| `supersedes` | None; append-only entry. Earlier Ledger bytes remain an exact prefix. |


### WP06_COMMAND_SAFETY_CORE_JERK_ENVELOPE_CORRECTED_ATOMIC_L2 — review candidate

| Field | Value |
|---|---|
| Exact integration/source base | `d0b1234f1c23961c5dd7c04a35c9ec39d6077629` |
| Review branch | `wp06-command-safety-core-jerk-envelope-fix-d0b1234` |
| Candidate commit | The commit containing this append-only entry; its exact SHA is reported at delivery and is not self-embedded here. |
| Classification | `L2_COMMAND_SAFETY_CORE_JERK_ENVELOPE_CORRECTED_PURE_LOGIC_IMPLEMENTATION` |
| Scope | Independently created pure Python deterministic fail-closed decision core and focused offline tests; exact eight-path allowlist. Neither rejected candidate `a3c9f7074f96a2d5632bb1cddd3ecffb18e1c58a` nor `89f064af2af1afbc86cf9e10eb43c974709ae1e0` is reused. |
| Corrections | F-01 exact `uint32` reset epoch/runtime generation and `uint64` sequence/source-instance domains; F-02 latched E-stop/critical fault, explicit manual reset and changed epoch, zero release cycle/no auto-resume; F-03 zero/cache barriers for reset, identity changes and handovers; F-04 per-axis intersection of hard-velocity-derived, acceleration, and prior-acceleration-centered jerk intervals, empty intersection `FAULT` + zero + cache clear, with no post-limit velocity clipping. |
| Candidate lifecycle | Review only. Independent audit PASS, separate User authorization for this exact commit, integration, and remote-ref verification are required before an integrated status update. |
| Evidence level | `PURE_CORE_SOURCE_AND_OFFLINE_UNIT_TEST_ONLY` |
| Boundary | Unpublished `SafetyCommandDecision`; no runtime SafetySupervisor, ROS node/graph, `/cmd_vel` publisher, FinalTwistPublisher, receipt runtime, collision/TTC, physical E-stop integration, profile/config hash, runtime evidence, Gate B transition, or runtime authorization. `RUNTIME_APPROVED: NOT_APPROVED`. WP-04/WP-05 and Gate A/Gate B remain unchanged. |
| `supersedes` | Rejected candidates are not reused; this candidate starts from the exact integration base. Earlier Ledger bytes remain unchanged. |

### WP06_SIM_EVAL_WHEEL_IMU_RUNTIME_INGRESS_ROSIDL_SEQUENCE_CORRECTED — review candidate

| Field | Value |
|---|---|
| Exact integration/source base | `43c94789f628b4211189fc391326e0b119cbb6d3` |
| Review branch | `wp06-sim-eval-wheel-imu-ingress-rosidl-sequence-fix-43c9478` |
| Scope | Fresh replacement from the exact base for the bounded sim_eval wheel/IMU ingress. Neither rejected candidate `38d52b19b8cacecbe49961f77df47eaacfd8c3c4` nor `3f40b6dcf34e07f9f9df33889df2c9379163d3fd` is an ancestor or source. |
| Corrections | F-01 wheel invalid-interval barrier and trusted-pose retention; F-02 atomic forced and effective `use_sim_time=true` verification before endpoints; F-03 indexed numeric `Sequence` acceptance including direct `array('d')` baseline and valid integration tests, while iterators/generators and text/bytes are rejected. Prior list-only fixtures did not demonstrate ROSIDL sequence representation acceptance. |
| Evidence level | Source plus offline parser/unit/build checks only; not runtime evidence. `runtime_eligible: false`. |
| Ownership and boundary | WP06-6E remains the sole ROS–Gazebo bridge owner. No TF publisher, bridge implementation, ROS graph execution, runtime evidence or runtime authorization. `/odom` and `/ground_truth/odom` are not accepted ingress/EKF inputs. |
| Candidate lifecycle | Review candidate only; independent audit and separate exact-candidate User authorization remain pending. No status change to WP-04/WP-05, Gate A/Gate B, or `RUNTIME_APPROVED: NOT_APPROVED`. |
| `supersedes` | None; append-only candidate record. Earlier Ledger bytes remain an exact prefix. |


### WP06_SIM_EVAL_WHEEL_IMU_RUNTIME_INGRESS_ROLLBACK_PRECEDENCE_CORRECTION — corrective review commit

| Field | Value |
|---|---|
| Integration base | `43c94789f628b4211189fc391326e0b119cbb6d3` |
| Existing review branch | `wp06-sim-eval-wheel-imu-ingress-rosidl-sequence-fix-43c9478` |
| Corrective commit parent | `4ccb0491408c8b8bfbf0c34f5cb33329ec9979c6` |
| Corrective commit | Recorded by Git; not self-embedded in this append-only entry. |
| Correction | F-04 `ROLLBACK_TIMESTAMP_PRECEDENCE`: extract/validate timestamp before reading wheel payload; a valid backward timestamp resets pose and baseline before payload validation, even if that payload is malformed. The next valid sample is baseline-only; a subsequent valid sample is required for integration. |
| Retained corrections | F-01 invalid-interval barrier; F-02 forced/effective sim time before endpoint creation; F-03 indexed `Sequence` and `array.array('d')` acceptance. |
| Candidate lifecycle | Corrective commit on the existing review candidate, not a new base candidate. Review only; no integration or PR. |
| Evidence level | `IMPLEMENTED_OFFLINE_BUILD_AND_TEST_ONLY`; no runtime evidence. `runtime_eligible: false`. |
| Ownership and status | WP06-6E remains sole bridge owner. No TF publisher, bridge implementation, ROS/Gazebo execution, runtime authorization, or WP-04/WP-05/Gate A/Gate B status change. `RUNTIME_APPROVED: NOT_APPROVED`. |


### WP05_SIM_EVAL_NAV2_BASELINE_STATIC_PROFILE_GAZEBO_SOURCE_PIN_RECONCILIATION — review candidate

| Field | Value |
|---|---|
| Exact integration/source base | `4f491edca1d46dee259d57350ad520a0334e4049` |
| Review branch | `wp05-sim-eval-static-profile-gazebo-pin-reconcile-4f491ed` |
| Candidate commit | Exact branch tip; not embedded in this append-only record. |
| Classification | `L1_STATIC_PROFILE_CURRENT_SOURCE_PIN_RECONCILIATION_ONLY` |
| Scope | Reconcile only `source_commit` and current `gazebo_lidar_source` SHA across the Step 5A YAML, Python descriptor and manifest. The Gazebo source and historical inventory are unchanged. |
| Drift | Current Gazebo source `1e97b6ea340adc9aecaf320cc432007c6bb37f5922cdc0366dbee50a9a26ff0e`; prior current-profile pin `a97b092f7343d04679ed1417539e47d217b20d18afc3364a27cf14110d9dece8`. |
| Evidence level | `STATIC_PROFILE_INPUT_CLOSURE_ONLY_NOT_RUNTIME_PROFILE_RESOLUTION` |
| Lifecycle | Review candidate only; independent audit PASS, separate exact-candidate User authorization, integration and remote-ref verification remain required. |
| Status and boundary | Step 5A remains static-only; WP-05 `OPEN`; WP-04 `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`. No endpoint/bridge/runtime pin, resolved profile, `ResolvedConfigV3`, `config_hash`, runtime evidence or runtime authorization. |
| `supersedes` | None; append-only candidate entry. |


### WP06_SIM_EVAL_SCAN_ENDPOINT_PROBE — review candidate

| Field | Value |
|---|---|
| Exact integration/source base | `46be7a2bde222475fbaaaac8a6749211edfd2ba0` |
| Review branch | `wp06-sim-eval-scan-endpoint-probe-46be7a2` |
| Candidate commit | Exact review-branch tip; not embedded in this append-only entry. |
| Classification | `L2_SIM_EVAL_SCAN_ENDPOINT_PROBE_SOURCE_IMPLEMENTATION` |
| Scope | Import-inert probe source, static descriptor, offline fake-runner tests and governance; no probe execution. |
| Endpoint boundary | `<topic>scan</topic>` is relative and not a full Gazebo Transport endpoint; future observations are `OBSERVED_NOT_PINNED` and need separate Owner decision before WP06-6E. |
| Future runtime gate | Separate capacity-one `APPROVED_RUNTIME` packet with exact command, pass/fail, stop conditions and explicit User approval. |
| Bridge ownership | WP06-6E remains sole owner of canonical ROS–Gazebo bridge implementation. |
| Evidence level | `IMPLEMENTED_OFFLINE_BUILD_AND_TEST_ONLY`; no runtime evidence. |
| Status/boundary | WP-04 `BLOCKED_BY_CONTRACT`; WP-05 `OPEN`; Gate A `PASSED`; Gate B `NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`. No endpoint pin, bridge, ROS `/scan` publisher, TF, profile resolution, runtime evidence or authorization. |
| Lifecycle | Review candidate only; independent audit and separate exact-commit User authorization remain required before integration. |
| `supersedes` | None; append-only entry. |


### WP06_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUNTIME_GUARD_CORRECTED — review candidate

| Field | Value |
|---|---|
| Exact integration/source base | `bfc1ef3cfe4ba98beefbe7f18607b97a41e52d15` |
| Review branch | `wp06-sim-eval-scan-probe-runtime-guard-fix-bfc1ef3` |
| Classification | `L2_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUNTIME_BOOTSTRAP_AND_CAPACITY_ONE_GUARD` |
| Authority packet | `docs/governance/decisions/WP-06_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUNTIME_BOOTSTRAP_AND_GUARD.md`, SHA-256 `d053fb4e6623cd753d63d4e1c646c476124579946671d389a16aba333d1b69e6` |
| Guard seed | `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`; capacity one; exact run ID `WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_001`. |
| F-01/F-02/F-03 correction | Bootstrap explicitly sets `GZ_PARTITION=wp06_scan_probe_run_001` before Gazebo include; authority packet is byte-SHA-bound; exact integrated ref plus future User authorization is required before pending-to-consumed transition. |
| Evidence level | `IMPLEMENTED_OFFLINE_GUARD_AND_BOOTSTRAP_SOURCE_ONLY`; guard not consumed and no runtime execution. |
| Status/boundary | After audit, integration, remote-ref verification and separate exact User authorization only: `RUNTIME_GUARD_IMPLEMENTED_AWAITING_EXACT_USER_AUTHORIZATION`. No endpoint pin, bridge, runtime evidence/authorization or Gate B transition. WP-04 `BLOCKED_BY_CONTRACT`; WP-05 `OPEN`; Gate A `PASSED`; Gate B `NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`. |
| `supersedes` | Rejected review commit `2b5fa296b2bf9cdfa732bdb8e7b435b96b8fdda4`; no source or commit was used. |


### WP06_SIM_EVAL_SCAN_ENDPOINT_PROBE_DETERMINISTIC_BOOTSTRAP_REMEDIATION — review candidate

| Field | Value |
|---|---|
| Exact integration/source base | `be5f63e7a01be0bca0b838e1ae5265bbb7145be8` |
| Review branch | `wp06-scan-probe-deterministic-bootstrap-be5f63e` |
| Candidate commit | Exact review-branch tip; not embedded in this append-only entry. |
| Classification | `L2_SIM_EVAL_SCAN_ENDPOINT_PROBE_DETERMINISTIC_BOOTSTRAP_REMEDIATION` |
| Scope | Local Fuel-free scan-probe world and explicit server-only Run 002 bootstrap; no runtime execution. |
| Run 001 | Guard remains byte-identical and pending at base; if this candidate is integrated, Run 001 is `NOT_CONSUMED_AND_INVALIDATED_BY_EXACT_INTEGRATION_MISMATCH`. |
| Run 002 | Capacity one, future-only, state `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`; not runtime authorization. |
| Readiness gate | Future bootstrap requires `ros_gz_sim create` to print exactly `Entity creation successful.`; no fixed delay substitutes for readiness. |
| Evidence level | `IMPLEMENTED_OFFLINE_GUARD_AND_BOOTSTRAP_SOURCE_ONLY`; no runtime evidence. |
| Preserved boundary | No endpoint pin, ROS `/scan`, bridge, TF, runtime evidence/authorization, resolved profile, `ResolvedConfigV3`, `config_hash` or Gate B transition. WP06-6E remains sole bridge owner. WP-04 `BLOCKED_BY_CONTRACT`; WP-05 `OPEN`; Gate A `PASSED`; Gate B `NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`. |
| `supersedes` | None; earlier Ledger bytes remain an exact prefix. |


### WP06_SIM_EVAL_SCAN_ENDPOINT_PROBE_DETERMINISTIC_BOOTSTRAP_RUN002_COMPLETION_FIX — corrective review commit

| Field | Value |
|---|---|
| Integration base | `be5f63e7a01be0bca0b838e1ae5265bbb7145be8` |
| Review branch | `wp06-scan-probe-deterministic-bootstrap-be5f63e` |
| Direct parent | `97aeecdff640187ac0b3ad152a22befe442a1a2f` |
| Classification | `L2_SIM_EVAL_SCAN_ENDPOINT_PROBE_DETERMINISTIC_BOOTSTRAP_REMEDIATION` corrective review commit |
| Run 002 | Independent guard/supervisor/manifest source implemented offline; guard remains `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`; no runtime authorization. Exact integrated refs, clean worktree, corrected authority packet, manifest, source pins, command, partition and run ID are checked before consumption. |
| Bootstrap readiness | Future run requires exact `Entity creation successful.` log before the one-shot supervisor. |
| Run 001 | Guard, tools and manifest are byte-identical to the direct parent; not modified or consumed. |
| World correction | `<gravity>` is a direct child of the local world and is outside `<physics>`; no remote assets or navigation-fidelity claim. |
| Evidence level | `IMPLEMENTED_OFFLINE_GUARD_AND_BOOTSTRAP_SOURCE_ONLY`; this corrective candidate did not execute runtime. |
| Boundary/status | No endpoint pin, bridge, ROS `/scan`, TF evidence, runtime evidence/approval, `ResolvedConfigV3`, `config_hash` or Gate B transition. `RUNTIME_APPROVED: NOT_APPROVED`; WP-04 `BLOCKED_BY_CONTRACT`; WP-05 `OPEN`; Gate A `PASSED`; Gate B `NOT_STARTED`. |
| `supersedes` | Corrects Run 002 supervisor compatibility and SDF gravity semantics on the existing review branch; prior Ledger bytes are an exact prefix. |


### WP06_6D_SCAN_PROBE_OBSERVATION_AND_TEARDOWN_REMEDIATION — review candidate

| Field | Value |
|---|---|
| Exact integration/source base | `b15e0fd6e83f840822b8ba11f68dbdf31de0978e` |
| Review branch | `wp06-scan-probe-observation-teardown-b15e0fd` |
| Candidate commit | Exact candidate tip reported at delivery; not self-embedded in this append-only entry. |
| Classification | `L2_RUNTIME_OBSERVABILITY_AND_PROCESS_OWNERSHIP_REMEDIATION` |
| Scope | Probe v2 parser/transcripts, Run 003 bootstrap, capacity-one guard and one-shot process-session source; Run 002 paths/evidence untouched. |
| Guard state | `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`; not consumed. |
| Evidence level | `IMPLEMENTED_OFFLINE_GUARD_AND_SESSION_SOURCE_ONLY`; no runtime execution/evidence. |
| Boundary | Future unique publisher observation is `OBSERVED_NOT_PINNED`. No bridge, ROS `/scan`, TF evidence, runtime profile, `ResolvedConfigV3`, `config_hash`, Gate B transition or runtime authorization. |
| Status | WP-04 `BLOCKED_BY_CONTRACT`; WP-05 `OPEN`; Gate A `PASSED`; Gate B `NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`. |
| `supersedes` | None; review candidate only. Previous Ledger bytes remain an exact prefix. |


### WP06_SCAN_PROBE_RUN003_HARMONIC_PUBLISHER_GRAMMAR_CORRECTION — corrective review candidate

| Field | Value |
|---|---|
| Integration base | `b15e0fd6e83f840822b8ba11f68dbdf31de0978e` |
| Existing review tip corrected | `e9ccee03123c3ec2baf82a66ce5a60bcbf1f9dfb`; not integrated and not runtime-authorized. |
| Scope | Structured publisher-section parsing with canonical unbracketed address/type grammar; exact `gz.msgs.LaserScan` only; subscriber-only entries excluded. |
| Evidence level | Source, offline tests and build only; no runtime evidence. |
| Run 003 guard | `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`; not consumed. |
| Boundary/status | No endpoint pin, bridge, ROS `/scan`, TF evidence, runtime profile, `ResolvedConfigV3`, `config_hash`, Gate B transition or runtime authorization. Existing WP/Gate statuses unchanged. |
| `supersedes` | Corrects the Run 003 publisher grammar statement and parser behavior recorded for review tip `e9ccee03123c3ec2baf82a66ce5a60bcbf1f9dfb`; previous Ledger bytes remain an exact prefix. |


### WP06_6D_SCAN_PROBE_READINESS_AND_TEARDOWN_ACCOUNTING_REMEDIATION — review candidate

| Field | Status / evidence |
|---|---|
| Base / branch | `db464f741e24a81b3f9587f827fc145c533d8d6c` / `wp06-scan-probe-readiness-teardown-run004-db464f7` |
| Scope | New independent Run 004 server-only launch, service-gated spawn/session runner, capacity-one pending guard, governance and offline tests. Run 002/003 historical paths are outside the candidate and untouched. |
| Run 003 disposition | Historical failure remains unchanged: no probe result/endpoint. Its readiness and teardown fields are not rewritten or reinterpreted. |
| Guard / evidence | Run 004 seed `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`; evidence ceiling `IMPLEMENTED_OFFLINE_GUARD_AND_SESSION_SOURCE_ONLY`; no runtime execution or guard consumption. |
| Future boundary | Requires independent audit, exact candidate integration/ref verification and separate Owner authorization for the exact integrated commit. A future match is only `GZ_LASERSCAN_ENDPOINT_OBSERVED_NOT_PINNED`. |
| Statuses | WP-04 `BLOCKED_BY_CONTRACT`; WP-05 `OPEN`; Gate A `PASSED`; Gate B `NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`. No ROS `/scan`, bridge, TF evidence, runtime authorization, profile resolution, `ResolvedConfigV3`, `config_hash`, or Gate B transition. |


### WP06_6D_SCAN_PROBE_PERSISTENT_TRANSPORT_DISCOVERY_FIX — review candidate

| Field | Status / evidence |
|---|---|
| Integration base / branch | `83f13d67ab212fec03b18cd2ed830349b7013ab3` / `wp06-scan-probe-persistent-transport-run005-83f13d` |
| Scope | Independent Run 005 launch, pending capacity-one guard, delayed binding check, one persistent partition-bound transport node, service-list snapshots, create/probe session source and offline tests. |
| Run 004 disposition | Historical service-discovery false-negative is not evidence of LiDAR failure; Run 004 artifacts are not modified or reinterpreted. Run 002/003/004 source and guard paths are outside this candidate diff. |
| Evidence ceiling | `IMPLEMENTED_OFFLINE_GUARD_AND_SESSION_SOURCE_ONLY`; no runtime or guard consumption. |
| Future boundary | Requires independent audit, exact integration and separate Owner authorization. Future match is only `GZ_LASERSCAN_ENDPOINT_OBSERVED_NOT_PINNED`. |
| Statuses | WP-04 `BLOCKED_BY_CONTRACT`; WP-05 `OPEN`; Gate A `PASSED`; Gate B `NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`. No ROS `/scan`, bridge, TF, endpoint pin, `ResolvedConfigV3`, `config_hash`, runtime evidence or Gate B transition. |
| `supersedes` | None; this is a new Run 005 candidate. Prior Ledger bytes remain an exact prefix. |


### WP06_RUN005_REVIEW_COMMIT_RUNTIME_AUTHORIZATION_TOPOLOGY_FIX — corrective review commit

| Field | Status / evidence |
|---|---|
| Parent / integration base | Parent `00911030081c821d1159f4b48941c0c1cd000638`; integration base remains `83f13d67ab212fec03b18cd2ed830349b7013ab3`. |
| Preflight topology | Future runtime requires `HEAD == --expected-review-commit`; integration ref equals `--expected-integration-base`; base is an ancestor. Candidate authority/source/manifest/evidence/guard blobs are compared with the exact review commit, never the integration base. |
| Guard | Run005 context rebound to corrected decision/manifest/source pins; capacity one and `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`; not consumed. Binding import still must succeed before acquisition. |
| Runtime routing | Runtime requires independent audit and separate Owner authorization naming the exact review commit. Runtime PASS does not authorize integration; only afterward may Owner decide integration of that exact commit. |
| Evidence ceiling | `IMPLEMENTED_OFFLINE_GUARD_AND_SESSION_SOURCE_ONLY`; no runtime executed, no endpoint pin, ROS `/scan`, bridge, TF evidence, runtime approval, `ResolvedConfigV3`, `config_hash` or Gate B transition. `RUNTIME_APPROVED: NOT_APPROVED`; WP-04/WP-05/Gate A/Gate B unchanged. |
| `supersedes` | Corrects the Run005 review/integration preflight topology recorded at review parent `00911030081c821d1159f4b48941c0c1cd000638`; all earlier Ledger bytes remain an exact prefix. |


### WP06-RUN005-TRANSPORT13-PREACQUIRE-NODE-CORRECTION

| Field | Value |
|---|---|
| Work item | WP06_RUN005_TRANSPORT13_BINDING_AND_PREACQUIRE_NODE_FIX |
| Base / parent | 83f13d67ab212fec03b18cd2ed830349b7013ab3 / bcad2cb61cc15fb09b521f082dab9250c77cd5d3 |
| Scope | Require python3-gz-transport13 and construct/capability-check one partition-bound Node before run directory creation and guard consumption; reuse it for service discovery. |
| Evidence status | IMPLEMENTED_OFFLINE_GUARD_AND_SESSION_SOURCE_ONLY |
| Guard | Run 005 remains PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION; capacity 1; not consumed. |
| Supersedes | The Run 005 binding/pre-acquisition defect recorded by the preceding candidate state; prior ledger entries remain unchanged. |
| Notes | Offline candidate only. No apt/sudo, ROS, Gazebo, launch, runner, runtime, bridge, ROS /scan, endpoint pin, or runtime authorization. |


### WP06-RUN005-HARMONIC-TOPIC-INFO-RAW-TRANSCRIPT-PARSER-CORRECTION

| Field | Value |
|---|---|
| Work item | WP06_6D_SCAN_PROBE_PERSISTENT_TRANSPORT_DISCOVERY_FIX |
| Parent / integration base | 20814c9009cee588f6b330ee227f69d886949593 / 83f13d67ab212fec03b18cd2ed830349b7013ab3 |
| Scope | Parser-only correction for the exact Harmonic publisher record plus no-subscribers footer; exact raw transcript replayed offline. |
| Historical Run005 | Runtime invoked once; historical terminal outcome remains PROBE_NOT_EXACTLY_ONE_MATCH; host authorization is consumed. No retry. |
| Offline replay | EXACTLY_ONE_MATCH; GZ_LASERSCAN_ENDPOINT_OBSERVED_NOT_PINNED; not a ROS endpoint pin or bridge claim. |
| Guard source seed | PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION; capacity 1. This Git seed does not authorize another Run005 runtime. |
| Evidence status | Parser source and offline test only; historical run record is unmodified. |
| `supersedes` | Corrects the Run005 parser outcome interpretation without rewriting historical runtime outcome or earlier ledger bytes. |


### WP06_SIM_EVAL_ROS_GAZEBO_SCAN_BRIDGE — review candidate

| Field | Value |
|---|---|
| Base / branch | `abcdffb4d1683c6b337b7c8a8916d0c9317d111e` / `wp06-sim-eval-ros-gz-scan-bridge-abcdffb` |
| Classification | `L2_PROFILE_SPECIFIC_ROS_GAZEBO_SCAN_BRIDGE_IMPLEMENTATION` |
| Mapping | One `/scan` `gz.msgs.LaserScan` to `/scan` `sensor_msgs/msg/LaserScan`, `GZ_TO_ROS`; lazy false; queues 10/10; `use_sim_time: true`; partition default `sim_eval`. |
| Evidence | Source/config/launch plus offline tests/build only; no runtime bridge connection or ROS publication evidence. |
| Runtime boundary | No ephemeral TCP endpoint pin, ROS `/scan` observation, TF/odom/command bridge, profile resolution, `ResolvedConfigV3`, `config_hash`, Gate B transition or runtime authorization. Runtime compatibility `NOT_VALIDATED`; `RUNTIME_APPROVED: NOT_APPROVED`. |
| Status | WP-04 `BLOCKED_BY_CONTRACT`; WP-05 `OPEN`; Gate A `PASSED`; Gate B `NOT_STARTED`. |
| `supersedes` | None; new review candidate. All earlier ledger bytes are preserved as a prefix. |


### WP06_6E_PROFILE_SPECIFIC_DEPENDENCY_LOCK_TEST_CORRECTION — corrective review candidate

| Field | Value |
|---|---|
| Candidate base / branch | `abcdffb4d1683c6b337b7c8a8916d0c9317d111e` / `wp06-sim-eval-ros-gz-scan-bridge-abcdffb` |
| Correction | The dependency-lock test distinguishes the exact 14 common Navigation V1 roots from `ros_gz_bridge`, `launch`, and `launch_ros`, which are profile-specific `sim_eval` runtime dependencies. |
| WP-05 lock files | External 14-root JSON lock and source-lock YAML template are unchanged; profile-specific dependencies are absent from both. |
| Package manifest | All 14 common roots followed by the 3 profile-specific `exec_depend` entries. |
| Evidence ceiling | Offline source/test/build only; runtime compatibility remains `NOT_VALIDATED`, no runtime authorization or Gate B transition. |
| Status | `RUNTIME_APPROVED: NOT_APPROVED`; WP-04/WP-05/Gate A/Gate B statuses unchanged. |
| `supersedes` | None; appends this correction without changing prior ledger bytes. |


### WP06_6E_LIDAR_FRAME_SOURCE_CONTRACT_CORRECTION — corrective review candidate

| Field | Value |
|---|---|
| Branch / base / parent | `wp06-sim-eval-ros-gz-scan-bridge-abcdffb` / `abcdffb4d1683c6b337b7c8a8916d0c9317d111e` / `7b6d3354130bcb82062e1a8fec0648dffa042a64` |
| Finding | Historical Run 001 passed ROS `/scan` type, one data publisher, non-empty ranges and teardown. `/parameter_events` and `/rosout` are standard endpoints. Its sole audited failure was observed `header.frame_id=ROBOT_URDF_final/base_link/YDLIDAR_X3_PRO` instead of `lidar_frame`. Historical runtime evidence is unchanged and not a full pass. |
| Correction | Add source-owned `<frame_id>lidar_frame</frame_id>` to the existing Gazebo LiDAR sensor and update the `gazebo_lidar_source` SHA-256 in the three current static descriptors. No bridge header rewrite, TF publisher, adapter, remap or ROS node. |
| WP-05 preservation | `source_commit`, map bindings, other pins, external 14-root lock, static policy manifest, historical inventory and WP-04/WP-05/Gate A/Gate B states remain unchanged. |
| Evidence status | Source, offline tests and build only. Run 001 remains historical evidence; no retry. A new capacity-one runtime requires independent audit and separate Owner authorization for the exact corrective commit. No endpoint pin or Gate B transition; `RUNTIME_APPROVED: NOT_APPROVED`. |
| `supersedes` | Clarifies the WP06-6E Run 001 frame-contract finding while preserving all preceding Ledger bytes. |


### WP06_6E_HARMONIC_GZ_FRAME_ID_CORRECTIVE_CANDIDATE — review candidate

| Field | Value |
|---|---|
| Branch / base / parent | `wp06-sim-eval-ros-gz-scan-bridge-abcdffb` / `abcdffb4d1683c6b337b7c8a8916d0c9317d111e` / `61c7f886ce7ebb09c77dc6ac1f6befb5420ae08e` |
| Source correction | Preserve the existing direct sensor child `<frame_id>lidar_frame</frame_id>` and add exactly one direct child `<gz_frame_id>lidar_frame</gz_frame_id>` to the `YDLIDAR_X3_PRO` `gpu_lidar` under `gazebo reference="lidar_frame"`. Current Gazebo source SHA-256: `9ff2dd9578b069cc492c9ff05e7f7f0d952c8bad0c5ecd9710ccea63d9fb1bbd`. |
| Provenance | Reconcile only the current static-profile YAML, Python descriptor, and WP-05 static-profile manifest pin. WP-05 dependency lock, map bytes/hash, static policy manifest, and historical inventory remain unchanged. |
| Historical runtime | Run 002 remains `WP06_6E_RUNTIME_FRAME_CONTRACT_FAIL_NO_RETRY`; its runtime record is unchanged and no retry is performed. No historical runtime result is promoted to a full pass. |
| Evidence status | Source/offline-test/build only. The bridge does not rewrite the header; no adapter, ROS node, TF publisher, endpoint pin, new runtime evidence, runtime authorization, or Gate B transition is created. A new capacity-one runtime requires independent audit and separate Owner authorization for the exact corrective commit. `RUNTIME_APPROVED: NOT_APPROVED`. |
| Statuses | WP-04 `BLOCKED_BY_CONTRACT`; WP-05 `OPEN`; Gate A `PASSED`; Gate B `NOT_STARTED`; unchanged. |
| `supersedes` | Clarifies the source frame contract while preserving all historical Run 001/Run 002 evidence and prior Ledger bytes. |


### WP06_6E_RUNTIME_DUAL_FRAME_EVIDENCE_DISPOSITION — L1 governance/evidence disposition

| Field | Value |
|---|---|
| Integrated source / base | `8bd998d6c118239d70f1d4a7b73e145795e8f921` |
| Runtime evidence provenance | `/home/hazan/wp06_runtime_evidence/WP06_6E_ROS_GAZEBO_SCAN_BRIDGE_RUNTIME_RUN_003`; raw files remain outside Git and unchanged. |
| Independent disposition | `WP06_6E_RUNTIME_DUAL_FRAME_CONTRACT_EVIDENCE_AUDIT_PASS`, based on recalculated raw hashes and independent transcript parsing. |
| Bounded acceptance | ROS `/scan` type `sensor_msgs/msg/LaserScan`; one data publisher; bridge publishers `/scan`, `/parameter_events`, `/rosout`; no forbidden odom/command/TF/map publishers; frame `lidar_frame`; 129 non-empty ranges; teardown clean with no live/zombie members. |
| Record discrepancy | Historical `run_record.json` remains `WP06_6E_RUNTIME_DUAL_FRAME_CONTRACT_FAIL_NO_RETRY`; parser mishandled YAML multi-document output and node-info indentation. Embedded self-hash is not a trust anchor. Addendum does not replace raw transcripts. Run 003 was not replayed. |
| Historical boundary | Run 001 and Run 002 remain unchanged historical failures. |
| Status | `WP06_6E_SCAN_BRIDGE_RUNTIME_OBSERVED_AND_AUDITED_PASS` for scan-bridge scope only; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`. No whole-navigation-profile validation, endpoint pin, TF evidence, profile resolution, `ResolvedConfigV3`, `config_hash`, or runtime authorization. |
| `supersedes` | Supersedes only the current WP06-6E scan-bridge runtime-evidence status wording; does not alter historical records or broader WP/Gate statuses. All base Ledger bytes remain an exact prefix. |


### WP06_6C_SIM_EVAL_WHEEL_IMU_RUNTIME_INGRESS_ACTIVATION — L2 review candidate

| Field | Value |
|---|---|
| Base / branch | `bd749560e50e11963873c33a51f806e420c38392` / `wp06-6c-wheel-imu-ingress-activation-bd74956` |
| Classification | `L2_PROFILE_SPECIFIC_WHEEL_IMU_RUNTIME_INGRESS_IMPLEMENTATION` |
| Data path | GZ `/joint_states` (`gz.msgs.Model`) → staging `/sim_eval/wheel_joint_states` (`sensor_msgs/msg/JointState`) → existing wheel emulator → `/wheel/odometry_raw`; GZ `/sim_eval/imu/raw` (`gz.msgs.IMU`) → staging `/sim_eval/imu_raw` (`sensor_msgs/msg/Imu`) → existing normalizer → `/imu/data`. Both mappings are `GZ_TO_ROS`. |
| IMU source frame | Existing `sim_eval_base_imu` has exact direct `frame_id=base_link` and `gz_frame_id=base_link`. |
| Gazebo source pin | Old `9ff2dd9578b069cc492c9ff05e7f7f0d952c8bad0c5ecd9710ccea63d9fb1bbd`; candidate `7bbaa475578600d8e18e437fa83720483b90b4af2bf4212157152429576a2`. Current WP-05 profile provenance only is reconciled. |
| Preservation | WP-05 14-root lock, historical inventory, static-policy manifest, WP06-6E Run 003 disposition manifest and raw evidence are unchanged. Run 003 remains historical scan-bridge-scope evidence at the prior source hash. |
| Evidence/status | `IMPLEMENTED_OFFLINE_BRIDGE_AND_INGRESS_SOURCE_ONLY`; `runtime_eligible: false`; runtime evidence `NOT_CREATED`; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`. |
| Boundary | No bridge for `/odom`, `/ground_truth/odom`, `/tf`, or `/tf_static`; no EKF, Nav2, AMCL, Map Server, command publisher, profile resolution, `ResolvedConfigV3`, `config_hash`, runtime authorization or navigation-ready claim. |
| `supersedes` | None; new WP06-6C candidate. Prior Ledger bytes are retained as exact prefix. |

### WP06_6C_RUN001_IMU_OBSERVABILITY_CORRECTION

| Field | Value |
|---|---|
| Branch / parent | `wp06-6c-wheel-imu-ingress-activation-bd74956` / `577b2b1223a8136d91753a7ea1f72fc0e6c73d93` |
| Historical result | Run 001 remains immutable `WP06_6C_RUNTIME_FAIL_NO_RETRY`; all 35 artifact hashes match the external manifest and checksum file. No `/sim_eval/imu_raw` payload was captured; the `/imu/data` echo timed out with empty stdout/stderr. |
| Root-cause finding | `RUN001_RAW_IMU_STAGING_SAMPLE_NOT_CAPTURED_ROOT_CAUSE_NOT_PROVABLE`; source emission (A), bridge transfer (B), and normalizer rejection (C) are all `NOT_PROVEN`. Publisher/subscriber counts are not payload proof. |
| Correction | Bounded structured first-accept/first-rejection diagnostics and an offline `yaml.safe_load_all` transcript parser. No sensor/bridge/normalizer acceptance semantics, wheel behavior, or public ROS topics changed. |
| Future evidence | Capture Gazebo `/sim_eval/imu/raw`, ROS staging `/sim_eval/imu_raw` payload and verbose topic info, canonical `/imu/data`, and the structured gate diagnostics. |
| Evidence status | `IMPLEMENTED_OFFLINE_OBSERVABILITY_SOURCE_AND_TESTS_ONLY`; `runtime_eligible: false`; no corrective runtime evidence or authorization. `RUNTIME_APPROVED: NOT_APPROVED`; Gate B `NOT_STARTED`. |
| Supersedes | Clarifies Run 001 observability and future evidence needs only; historical record and all preceding Ledger bytes remain unchanged. |


### WP06_6C_GAZEBO_SHA_PROVENANCE_TRANSCRIPTION_CORRECTION

| Field | Value |
|---|---|
| Date | 2026-10-17 |
| Scope | Governance provenance correction only for the current WP06-6C Gazebo source pin. |
| Correction | A malformed 61-character historical transcription in the preceding WP06-6C entry is a transcription error. The authoritative Gazebo source SHA-256 is `7bbaa475578600d8e18e437fa83720483b90b4af2bf4212151257152429576a2`. |
| Reconciliation | Registry, WP06-6C decision, and WP06-6C evidence already contain the authoritative SHA; this entry reconciles governance provenance only. |
| Boundary | No source, bridge, normalizer, wheel behavior, Run 001 runtime result, or authorization state changed. Historical bytes remain intact; this Ledger entry is append-only. |
| `supersedes` | Corrects only the current Gazebo SHA transcription in the immediately preceding WP06-6C candidate entry. |


### WP06_6C_IMU_WORLD_SYSTEM_ROOT_CAUSE_FIX — corrective review candidate

| Field | Value |
|---|---|
| Branch / parent | `wp06-6c-wheel-imu-ingress-activation-bd74956` / `660008e590518b454973b3c71190198c1830f215` |
| Classification | `L2_CORRECTIVE_SOURCE_ACTIVATION` |
| Proven root cause | `GAZEBO_IMU_SYSTEM_PLUGIN_ABSENT`; Run 002 raw evidence showed no Gazebo publisher on `/sim_eval/imu/raw`, while scan and wheel paths operated; the world had the Sensors system but lacked the IMU system. |
| Correction | Added exactly one direct world-level `gz-sim-imu-system` plugin; offline XML regression requires exactly one world-level Sensors and IMU system and rejects removal or renaming. |
| Historical boundary | Run 002 remains immutable historical failure; no runtime retry occurred. This correction does not establish sensor, bridge, or normalizer runtime PASS. |
| Evidence status | Offline source/test/build evidence only; `runtime_eligible: false`; runtime evidence `NOT_CREATED`; `RUNTIME_APPROVED: NOT_APPROVED`; Gate B `NOT_STARTED`. |
| `supersedes` | Supersedes only the current Run 002 root-cause remediation routing; historical runtime artifacts and prior Ledger bytes remain unchanged. |

### WP06_6C_RUNTIME_RUN003_EVIDENCE_DISPOSITION — L1 candidate

| Field | Value |
|---|---|
| Branch / parent | `wp06-6c-wheel-imu-ingress-activation-bd74956` / `9c945a4d52058e3f3cb3b8285e5cb017582fd8af` |
| Runtime identity | `WP06_6C_WHEEL_IMU_RUNTIME_INGRESS_RUN_003`; review source `9c945a4d52058e3f3cb3b8285e5cb017582fd8af`; integration base `bd749560e50e11963873c33a51f806e420c38392`. |
| Audit | `WP06_6C_RUNTIME_RUN003_INDEPENDENT_EVIDENCE_AUDIT_PASS`; external `SHA256SUMS.txt` verifies 24/24 entries and manifest-pinned raw artifacts are recalculated. |
| Bounded result | Gazebo IMU → ROS staging → normalizer → `/imu/data`; wheel ingress; effective `use_sim_time`; clean teardown. This does not validate the whole ROS graph, global TF, EKF, Nav2, AMCL, Map Server, or navigation profile. |
| Historical boundary | Run 001 and Run 002 remain immutable historical failures; their evidence is not modified or reinterpreted. |
| Status | `WP06_6C_RUN003_RUNTIME_EVIDENCE_AUDITED_PASS_BOUNDED_INGRESS_SCOPE`; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`; no new runtime authorization. |
| Integration routing | Eligible only pending final independent audit of the exact L1 disposition commit and Owner decision. |
| `supersedes` | Supersedes only current WP06-6C runtime-evidence status wording; all prior Ledger bytes remain an exact prefix. |


### WP06-6F TF/EKF runtime state-estimation ingress with isolated clock — L2 review candidate

| Field | Value |
|---|---|
| Base / branch | `8b73bcb0b026fe337c023f6a30205dbe89d31eb5` / `wp06-6f-tf-ekf-clock-ingress-8b73bcb` |
| Classification | `L2_PROFILE_SPECIFIC_TF_EKF_RUNTIME_STATE_ESTIMATION_INGRESS` |
| Clock route | One dedicated `GZ_TO_ROS` mapping: Gazebo `/clock` (`gz.msgs.Clock`) to ROS `/clock` (`rosgraph_msgs/msg/Clock`). The legacy launch route is excluded. |
| Composite | Existing 6C wheel/IMU ingress, one clock bridge, one `robot_localization/ekf_node`; no bootstrap/RSP duplicate, navigation stack, or command publisher. Partition is fixed to `wp06_scan_probe_run_002`. |
| TF ownership | EKF is intended sole dynamic owner of `odom -> base_link`; bootstrap RSP retains static `base_link -> lidar_frame`; no `map -> odom`. Runtime ownership remains unvalidated. |
| Evidence/status | `IMPLEMENTED_OFFLINE_TF_EKF_SOURCE_AND_GUARD_ONLY`; guard `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity 1, not consumed; runtime evidence `NOT_CREATED`; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`. |
| Historical boundary | WP06-6C Run 003 remains independently audited bounded ingress evidence only. WP06-6C/6D/6E sources and historical runtime records remain unchanged. |
| `supersedes` | None. All parent Ledger bytes are retained as an exact prefix. |


### WP06-6F multi-sample runtime observer corrective continuation

| Field | Value |
|---|---|
| Scope | One rclpy observer call records multi-sample `/clock`, filtered odometry, dynamic TF edge GID, static transient-local TF, and `map -> odom` absence. |
| Evidence ceiling | `IMPLEMENTED_OFFLINE_MULTISAMPLE_RUNTIME_OBSERVER_AND_GUARD_ONLY`; no runtime executed. |
| Guard | `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity 1, acquisition count 0, `runtime_authorization: NOT_GRANTED`; unchanged and unconsumed. |
| Acceptance closure | Decision, evidence JSON, and guard manifest carry a collector/artifact/parser/pass/failure/test matrix for every runtime acceptance. |
| `supersedes` | Supersedes only the prior WP06-6F evidence ceiling and single-sample observer design statement; no runtime result or architecture status. |


### WP06_6F_CPP_GID_OBSERVER_CORRECTIVE_CANDIDATE

| Field | Value |
|---|---|
| Historical Run 001 | Immutable observer API mismatch failure: Python rclpy Jazzy rejected `create_subscription(..., with_info=True)`. This is not evidence of a TF/EKF failure; no retry or historical artifact mutation. |
| Corrective design | New `ament_cmake` C++ observer consumes `rclcpp::MessageInfo` and underlying RMW publisher GID, maps each dynamic `odom -> base_link` edge GID to exactly one graph endpoint owned by the configured EKF endpoint, and fails closed with `TF_EDGE_PUBLISHER_GID_UNMAPPABLE` when mapping is unavailable. No node-name fallback or global `/tf` publisher count. Python is offline JSON parsing/validation only. |
| Run 002 | Separate capacity-one guard is `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity 1, acquisition count 0, `runtime_authorization: NOT_GRANTED`; not authorized or consumed. |
| Evidence ceiling | Offline/source/test/build only. No runtime execution, retry, integration, runtime approval, or Gate B transition. `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`. |
| `supersedes` | Corrects only the WP06-6F observer implementation and future Run 002 guard routing; Run 001 records and artifacts remain unchanged. |

### WP06-6F dynamic TF QoS compatibility corrective

| Field | Value |
|---|---|
| Parent / scope | `cb16bed6a14cb7518f9e55f6d4adfe21dbd07467`; observer QoS compatibility only, no runtime execution. |
| Dynamic `/tf` QoS | `KEEP_LAST(100)`, `BEST_EFFORT`, `VOLATILE`; C++ observer source SHA-256 `3e2e3227d4933a2cf0863b31810556c01116fb9598bb8ba850c1beb974f0b635`. |
| Static `/tf_static` QoS | Preserved as `KEEP_LAST(1)`, `RELIABLE`, `TRANSIENT_LOCAL`. |
| Validation | Schema v2 records both profiles; Python validator fails closed and tests cover reliable/transient-local dynamic `/tf` rejection; acceptance matrix has a dedicated collector/parser/test row. |
| Run boundary | Run 001 remains immutable observer API mismatch failure, not a TF/EKF failure. Run 002 remains pending, capacity 1, acquisition count 0, `runtime_authorization: NOT_GRANTED`. |
| Evidence ceiling | Offline source/test/build only; no runtime authorization, runtime evidence, integration, `RUNTIME_APPROVED`, or Gate B transition. |
| `supersedes` | Supersedes only the prior dynamic `/tf` observer QoS implementation detail; historical run records and other acceptance criteria are unchanged. Parent Ledger bytes remain an exact prefix. |


### WP06-6F static TF publisher ownership observer correction

| Field | Value |
|---|---|
| Change | Observer schema v3 captures `/tf_static` publisher GID from `rclcpp::MessageInfo`, snapshots `/tf_static` graph endpoints, and requires the unique GID mapping to identify the root-namespace `robot_state_publisher` TFMessage endpoint. Static transform matching alone no longer establishes ownership. |
| Failure disposition | GID unmappable, GID non-unique, and publisher not `robot_state_publisher` have separate fail-closed literals. Dynamic `/tf` and static `/tf_static` QoS contracts remain unchanged and recorded. |
| Run boundary | Run 001 remains immutable historical observer API mismatch failure. Run 002 remains PENDING, capacity 1, acquisition count 0, `runtime_authorization: NOT_GRANTED`; no runtime was executed or authorized. |
| Evidence ceiling | Offline source/test/build only; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`. Parent ledger bytes remain an exact prefix. |
| `supersedes` | Supersedes only the prior assumption that validating the static transform and QoS sufficed; it does not alter historical runtime evidence. |


### WP06-6F observer JSON container corrective continuation

| Field | Value |
|---|---|
| Run 002 disposition | Historical observer execution failure: JSON brace-init created nested arrays; `edge.at("publisher_gid")` raised `json.exception.type_error.304`. This is not evidence of TF/EKF/clock failure. Run 002 guard/manifest and external runtime evidence remain unchanged; no retry. |
| Correction | Five C++ collections now use explicit empty JSON arrays; C++ regression exercises valid TF object GID extraction and checks document shape. Python offline validation rejects nested arrays and non-object rows with structured literals. |
| Run 003 | Separate runner/guard/test/manifest; guard `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity 1, acquisition count 0, `runtime_authorization: NOT_GRANTED`; not authorized or consumed. |
| Evidence ceiling | Offline source/test/build only; `runtime_eligible: false`; runtime evidence `NOT_CREATED`; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`. |
| `supersedes` | Corrects only current observer JSON collection behavior and Run 003 routing. Historical Run 002 runtime evidence is immutable. All prior Ledger bytes are an exact prefix. |


### WP06-6F Run003 source-pin closure

| Field | Value |
|---|---|
| Corrected observer | C++ collection source SHA-256 `6ab41da8d6486e06d2f9031482e1037f1f9a6c8f828aaddeadfdaadcba2460c6`; Python offline parser SHA-256 `163e02eb8db27a8e9f355c6f343d30a6291b37289f2bdc3e486bab85922d7c9e`. |
| Run 002 | Historical observer JSON-container execution failure (`json.exception.type_error.304`), not evidence of TF/EKF/clock failure; historical runtime files remain unchanged. |
| Run 003 | Separate capacity-one guard PENDING, acquisition count 0, `runtime_authorization: NOT_GRANTED`; no authorization or runtime evidence. |
| Evidence ceiling | Offline source/test/build only; `runtime_eligible: false`; `runtime_evidence_status: NOT_CREATED`; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`. |
| `supersedes` | Corrects only the Run003 source-pin/status routing. Prior Ledger bytes are retained as an exact prefix. |


### WP06-6F Run003 final observer source-pin correction

| Field | Value |
|---|---|
| Source pins | C++ observer `70c74e56988ce750aa9c808e929d68df06a04f7a6d8bfeb175c74e40c2b014b7`; Python offline validator `163e02eb8db27a8e9f355c6f343d30a6291b37289f2bdc3e486bab85922d7c9e`. This entry corrects only the pin values recorded in the preceding uncommitted candidate note; no historical Run002 artifact is modified. |
| Run 002 / Run 003 | Run002 remains historical observer execution failure, not a TF/EKF/clock failure. Run003 guard remains pending, capacity 1, acquisition count 0, `runtime_authorization: NOT_GRANTED`. |
| Evidence ceiling | Offline source/test/build only; no runtime authorization or Gate B transition. |
| `supersedes` | Supersedes only the source-pin values in the immediately preceding candidate-only Ledger entry; all base Ledger bytes remain an exact prefix. |


### WP06-6F governance reconciliation — Run 002 consumed, Run 003 pending

| Field | Value |
|---|---|
| `supersedes` | Supersedes prior current-status statements in WP06-6F governance that described Run 002 as pending, unauthorized, unexecuted, or not acquired. Earlier Ledger bytes are retained unchanged as the required prefix. |
| Run 002 | Executed exactly once at review commit `8939b7d8d0268eb595f906bcc97581d6dc62b581`; external guard state is `CONSUMED`, `acquisition_count=1`. It failed in observer execution with nested-array `json.exception.type_error.304`. It is not evidence of a TF, EKF, clock, or `robot_state_publisher` failure, and it was not retried. |
| Run 003 | The sole pending guard: `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity 1, acquisition count 0, `runtime_authorization=NOT_GRANTED`. |
| Current pins | C++ observer SHA-256 `70c74e56988ce750aa9c808e929d68df06a04f7a6d8bfeb175c74e40c2b014b7`; Python validator SHA-256 `163e02eb8db27a8e9f355c6f343d30a6291b37289f2bdc3e486bab85922d7c9e`. |
| Evidence ceiling | `IMPLEMENTED_OFFLINE_JSON_COLLECTION_CORRECTION_RUN003_GUARD_PENDING`; `runtime_eligible: false`; runtime evidence `NOT_CREATED`; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`. |

### WP06_6F_RUN003_CROSS_LANGUAGE_JSON_VALIDATION_CORRECTIVE_CANDIDATE

| Field | Record |
|---|---|
| Parent/base | `3f2748dc2ef809610fe0f4ebb88aef5db24d9924` / integration base `8b73bcb0b026fe337c023f6a30205dbe89d31eb5`. |
| Run003 disposition | `RUN003_VALID_JSON_REJECTED_BY_CROSS_LANGUAGE_BYTE_CANONICALITY_CHECK`; `NOT_A_TF_EKF_CLOCK_OR_ROBOT_FAILURE`. Run003 guard was consumed once; raw evidence is unchanged and the run was not retried. |
| Correction | Python observer reader uses strict JSON parsing plus semantic validation; it no longer compares C++ bytes to Python serialization. Acceptance remains recomputed from validated raw values. |
| Run004 | `RUN004_SEMANTIC_VALIDATION_GUARD_PENDING`; pending seed, capacity 1, acquisition count 0, `runtime_authorization=NOT_GRANTED`; no authorization or runtime execution. |
| Evidence ceiling | `IMPLEMENTED_OFFLINE_CROSS_LANGUAGE_JSON_SEMANTIC_VALIDATION_RUN004_GUARD_PENDING`; `runtime_eligible: false`; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`. |
| `supersedes` | Supersedes only current WP06-6F status and the incorrect cross-language byte-canonicality requirement; historical Run001/Run002/Run003 records remain immutable. All parent Ledger bytes are an exact prefix. |


### WP06_6F_RUN004_CHECKER_CONTRACT_CORRECTIVE_CANDIDATE — Run005 pending

| Field | Record |
|---|---|
| `supersedes` | Supersedes only the current WP06-6F checker contract and pending-run routing; Run001–Run004 historical artifacts and outcomes are unchanged. |
| Run004 | Historical terminal outcome `WP06_6F_RUNTIME_RUN004_FAIL_NO_RETRY_GUARD_CONSUMED`. The EKF's `/set_pose` administrative subscriber was rejected and substring checking mistook `/odometry/filtered` for `/odom`; this is not a TF/EKF/clock/robot failure. No retry. |
| Run005 checker | Exact section-parsed topic names; EKF data-plane `/clock`, `/imu/data`, `/wheel/odometry_raw`; `/set_pose` allowed only as an EKF subscriber. Dedicated type/publisher/subscriber transcript and bounded echo require `geometry_msgs/msg/PoseWithCovarianceStamped`, one EKF subscriber, zero publishers, and no payload. Publisher failure literal: `EKF_SET_POSE_EXTERNAL_PUBLISHER_OBSERVED`. |
| Run005 guard | `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity 1, acquisition count 0, `runtime_authorization=NOT_GRANTED`; not authorized or executed. |
| Evidence ceiling | `IMPLEMENTED_OFFLINE_RUN004_CHECKER_CONTRACT_CORRECTION_RUN005_GUARD_PENDING`; runtime eligible false, evidence not created, `RUNTIME_APPROVED: NOT_APPROVED`, `GATE_B: NOT_STARTED`. |


### WP06_6F_RUN005_TOPOLOGY_FALSE_NEGATIVE_CORRECTION_RUN006_CANDIDATE

| Field | Record |
|---|---|
| Parent/base | `ca2e9798a49be6c9b3429ef0fd161410539ca12a`; integration base `8b73bcb0b026fe337c023f6a30205dbe89d31eb5`. |
| Run005 disposition | Historical terminal outcome `WP06_6F_RUNTIME_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED`, immutable. Raw topology included `/parameter_events` and `/rosout`; the checker included these ROS-standard endpoints in the EKF business equality and falsely rejected topology. Other stated runtime criteria passed; no TF/EKF/clock/robot failure is inferred; no retry. |
| Run006 correction | New runner classifies exact `Publishers`/`Subscribers` sections, permits `/parameter_events` in either direction and `/rosout` only as a publisher, then requires exact business endpoint sets. Wrong-direction standard endpoints and every unapproved endpoint still fail closed. `/set_pose` remains restricted and requires zero publishers plus an empty timed echo. |
| Run006 guard | Separate guard: `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity 1, acquisition count 0, `runtime_authorization=NOT_GRANTED`; not authorized or executed. |
| Evidence ceiling | `IMPLEMENTED_OFFLINE_RUN005_TOPOLOGY_FALSE_NEGATIVE_CORRECTION_RUN006_GUARD_PENDING`; `runtime_eligible: false`; runtime evidence `NOT_CREATED`; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`. |
| `supersedes` | Supersedes only current WP06-6F topology-checker status. Run001–Run005 source guards and historical evidence remain unchanged. All parent Ledger bytes are an exact prefix. |


### WP06-6F Run007 finalization-order corrective candidate

| Field | Record |
|---|---|
| `supersedes` | Supersedes only the current WP06-6F candidate status describing Run006 as pending; earlier Ledger bytes and Run006 historical artifacts remain immutable. |
| Run006 | Historical terminal outcome remains `WP06_6F_RUNTIME_RUN006_FAIL_NO_RETRY_GUARD_CONSUMED`; external raw record has all final acceptance values true and clean teardown, while the failure was emitted by the pre-teardown check. This is a runner finalization-order failure, not a TF/EKF/clock/robot failure. No retry. |
| Run007 correction | A distinct runner separates pre-teardown runtime acceptance from teardown acceptance and computes final acceptance and the single terminal outcome only after composite-then-bootstrap teardown. Teardown failures receive teardown-specific literals. |
| Run007 guard | `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity 1, acquisition count 0, `runtime_authorization=NOT_GRANTED`; no authorization or runtime execution. |
| Evidence ceiling | `IMPLEMENTED_OFFLINE_RUN006_FINALIZATION_ORDER_CORRECTION_RUN007_GUARD_PENDING`; runtime eligible false, runtime evidence not created, `RUNTIME_APPROVED: NOT_APPROVED`, `GATE_B: NOT_STARTED`. |

### WP06-6F Run007 exact Owner authorization binding corrective

| Field | Record |
|---|---|
| `supersedes` | Supersedes only the current Run007 authorization-flow description; historical run outcomes, guard seeds, and runtime artifacts remain immutable. |
| Parent/base | `a1348313dab704964e67572fd18dcdcecf1f66d7`; integration base `8b73bcb0b026fe337c023f6a30205dbe89d31eb5`. |
| Authorization scope | `WP06_6F_RUN007_ONE_OFFICIAL_RUNNER_INVOCATION_CAPACITY_ONE_NO_RETRY`; five required non-empty values must bind to the exact Run007 ID, review commit, and integration base before acquisition. |
| Guard/record contract | Seed remains `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity 1, acquisition count 0, `runtime_authorization=NOT_GRANTED`. Only atomic acquire after preflight may record exact Owner metadata, acquired refs, `GRANTED_FOR_THIS_EXACT_RUN_ONLY`, and count 1. Run record schema v2 preserves all five authorization fields and guard state before/after. Invalid/missing values stop before guard lock and evidence-directory creation. |
| Evidence ceiling | `IMPLEMENTED_OFFLINE_RUN007_OWNER_AUTHORIZATION_BINDING_GUARD_PENDING`; source/test/governance only. No runtime authorization, acquisition, runtime evidence, `RUNTIME_APPROVED`, or Gate B transition. |

### WP06-6F Run007 independent runtime evidence disposition

| Field | Record |
|---|---|
| Disposition | `WP06_6F_RUN007_INDEPENDENT_EVIDENCE_AUDIT_PASS`; L1 governance/evidence disposition candidate. |
| Runtime source / integration base | `93468611748e3966cd6fa7fa280e840651d2c895` / `8b73bcb0b026fe337c023f6a30205dbe89d31eb5`. |
| External evidence | `/home/hazan/wp06_runtime_evidence/WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_007`; 34 manifest entries; `sha256sum -c SHA256SUMS.txt` PASS. Canonical disposition manifest: `docs/governance/evidence/WP-06_6F_TF_EKF_RUNTIME_INGRESS_RUN_007_MANIFEST.json`. |
| Scope | WP06-6F ingress, clock, EKF filtered odometry, bounded TF edges/ownership/QoS, `/set_pose` boundary, and teardown only. No whole ROS graph or navigation-profile claim. |
| Run001–Run006 | Immutable historical; no records, guards, manifests, transcripts, raw evidence, or terminal outcomes rewritten. |
| Authorization/Gate | Run007 guard is consumed, acquisition count 1, exact-run authorization recorded. This disposition issues no new authorization; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`. |
| `supersedes` | Supersedes only prior current-status statements that Run007 evidence was pending independent audit; historical entries are retained byte-for-byte. |


### STEP-07_GATE_B_AUTHORITY_INPUT_CLOSURE_SURVEY — L2 governance/evidence candidate

| Field | Record |
|---|---|
| Exact integration base / sole parent | `5471e8860050326215bb83761629e9969def16ea` |
| Review branch | `step-07-gate-b-authority-input-closure-5471e88` |
| Architecture authority | `docs/MECANUM_NAV_DRL_Architecture.docx`, SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204` |
| Scope | Read-only authority/provenance survey for six Gate B input groups and three cross-cutting contracts. Only the survey decision/evidence plus Registry, PEP, and this append-only Ledger are in scope. |
| Findings | No Gate B concrete profile is closed. LiDAR, LocalReference, measured twist, frame/TF, lifecycle/barrier are `PARTIAL`; concrete profile is `UNRESOLVED`. Receipt v2/QoS6, SafetyLifecycle/SafetySupervisor/final command ownership, and PPO boundary are recorded as partial closure with explicit gaps. `INTERFACE_STATUS_COMMENT_VS_CMAKE_GENERATOR_CONTRADICTION` is unresolved; neither side is selected by this survey. |
| WP06 evidence boundary | WP06-6F Run007 remains audited PASS only within its ingress/clock/EKF/TF scope; it does not prove Nav2, map, `map -> odom`, whole ROS graph, SafetyLifecycle, or PPO. Missing `map -> odom` in that run is not treated as runtime failure. |
| Step naming | “Step-7” is this survey roadmap step, distinct from PEP `WP-07-BRIDGE-FIRMWARE-OFFLINE`; WP-07 remains `BLOCKED_BY_DEPENDENCY`. |
| Decision/status | `STEP07_L2_SURVEY_PASS_IMPLEMENTATION_NOT_AUTHORIZED`; no implementation/runtime authorization or Gate B transition. `GATE_B: NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`; WP-04/WP-07 statuses and dependencies unchanged. |
| Evidence ceiling | Governance/source provenance only; no build/test/runtime/HIL/hardware evidence is created. |
| `supersedes` | None; new survey entry only. All parent Ledger bytes are preserved as an exact prefix. |


### ROADMAP_STEP4_STEP5_STEP6_CONSOLIDATED_CLOSURE — L2 candidate

| Field | Record |
|---|---|
| Source base | `d44ba711395a50d3ba8b9f91e6f64d1eca8ca5a1`; candidate branch `roadmap-step4-step5-step6-consolidated-closure-d44ba71`. |
| Authority | Frozen Architecture SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`; supplied Owner decisions select `sim_eval` + `NAV2_BASELINE`, map/world source identity, localization/TF ownership, safety ownership and runtime command routing. |
| Status | Step 4 `CLOSED_FOR_SIM_EVAL`; Step 5 `IMPLEMENTED_OFFLINE_ONLY`; Step 6 `IMPLEMENTED_OFFLINE_ONLY`; roadmap Step 7 `NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`. PEP WP-07 status/dependencies unchanged. |
| Evidence | Candidate source/config/interface pins and map/world manifest are recorded in `docs/governance/evidence/ROADMAP_STEP4_STEP5_STEP6_CONSOLIDATED_CLOSURE.json` and `docs/governance/evidence/STEP4_SIM_EVAL_ARTIFACT_BUNDLE_MANIFEST.json`. Evidence ceiling `STATIC_SOURCE_OFFLINE_BUILD_TEST_READY_FOR_STEP7_RUNTIME_CAMPAIGN`; final offline checks are pending at ledger creation. |
| Boundary | No ROS/Gazebo/runtime, Nav2 live, AMCL convergence, full TF runtime, Gate B, PPO training, HIL, or hardware validation is claimed. WP06-6F Run007 remains bounded to its audited ingress/clock/EKF/TF scope; historical WP06 artifacts are unchanged. |
| Next prerequisites | Local world asset-cache preflight; separate exact capacity-one runtime authorization; initial pose/partition; full composite runtime evidence; independent evidence audit; Owner decision. |


### ROADMAP_STEP4_STEP5_STEP6_CONSOLIDATED_CLOSURE — offline verification record

| Field | Record |
|---|---|
| Candidate source base | `d44ba711395a50d3ba8b9f91e6f64d1eca8ca5a1`; branch `roadmap-step4-step5-step6-consolidated-closure-d44ba71`. |
| Offline verification | Five-package colcon build PASS; `mecanum_nav_rl/test` 687 passed; `mecanum_nav_bringup/test` 232 passed; interface colcon test 11 passed; py_compile 25 Python files; installed ROSIDL imports, three console executables, and installed launch/config byte equality PASS. JSON/YAML/XML, duplicate-key, UTF-8/canonical, config-hash, source-pin, historical WP06 preservation, exact scope, Ledger prefix, and diff checks PASS. |
| Test interpreter | Temporary external venv; Pydantic `2.10.6`; `pip freeze` SHA-256 `8fc5de359c1faf157acf11c35b740cd433abbe4d3a432158d88ff75e6677d26e`. Build/install/log directories remain outside the Git worktree. |
| Evidence boundary | Offline source/build/test only. No runtime, Nav2-live, AMCL convergence, full TF runtime, Gate B, PPO training, HIL, or hardware result. Step 4 `CLOSED_FOR_SIM_EVAL`; Step 5/6 `IMPLEMENTED_OFFLINE_ONLY`; Step 7 `NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`. |


### ROADMAP_STEP4_STEP5_STEP6_CONSOLIDATED_CLOSURE_CORRECTIVE_L2 — offline candidate record (2026-10-19)

| Field | Record |
|---|---|
| Review branch / base | `roadmap-step4-step5-step6-consolidated-closure-d44ba71`; exact parent `d8db18aa3a5819b42d130221904281cec3360cae`; integration reference was not changed. |
| Classification | `L2_CORRECTIVE_RUNTIME_ASSEMBLY_AND_SAFETY_CLOSURE`; only the pre-authorized corrective allowlist is changed. |
| Map/Fuel closure | Absolute canonical map root and four artifact hashes checked before Map Server configuration. Fuel cache root is restricted to `$HOME/.gz/fuel`, the exact two SDF URIs and one positive-version cache directory per model, with `model.config` and `model.sdf`; this does not equate local cache content to remote Fuel content. |
| Lifecycle/safety closure | Lifecycle configure/activate remain `NON_READY` until explicit rearm; reset/rearm services and generation transitions are unit-tested. Safety limits/freshness are parsed from YAML-backed parameters; sim E-stop defaults active and release requires explicit launch authorization plus fresh valid inputs and READY barrier. |
| V3 ownership | `/imu/data` and `/wheel/odometry_raw` publisher owner is `mecanum_base_bridge`; resolved config JCS SHA-256 `5b3bb2be3bc4d8ff5f9f1524b5ecd52f735c63622e3dd6ddd3e67aa9e6ce1071`. |
| Offline verification | Five-package colcon build PASS; `mecanum_nav_rl/test` 698 passed; `mecanum_nav_bringup/test` 234 passed; interface colcon test 11 passed; focused corrective tests 37 passed; ROSIDL imports, three installed safety executables, and installed launch/config byte equality PASS. |
| Evidence | `docs/governance/evidence/ROADMAP_STEP4_STEP5_STEP6_CONSOLIDATED_CLOSURE.json`, SHA-256 `8769f701291ad9f57881130500ea3ecd12885a0ceb19530a759015573942ede1`; 44 source pins are recorded there. Pydantic test dependency is `2.10.6`; build/install/log/test ROS directories are external to the Git worktree. |
| Limits | Source/build/offline-test evidence only. No ROS/Gazebo/runtime/HIL/hardware was run. Step 4 `CLOSED_FOR_SIM_EVAL`; Step 5/6 `IMPLEMENTED_OFFLINE_ONLY`; Step 7 `NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`. Independent audit remains pending. |


### ROADMAP_STEP4_STEP5_STEP6_CONSOLIDATED_CLOSURE_CORRECTIVE_L2 — evidence accounting correction (2026-10-19)

| Field | Record |
|---|---|
| Corrected evidence identity | Current closure evidence SHA-256 is `01075f9930e796f79760d999a1fb06c05d289ecd0d6ce79b9d35400c270db14b`; the prior ledger entry’s `8769f701...` value is superseded for current evidence accounting only. |
| Corrected scope | Exact current candidate diff contains 21 paths, all within the authorized allowlist; `ppo.yaml` is byte-identical to base and absent from the diff. |
| Verification record | Five-package build PASS; `mecanum_nav_rl/test` 698 passed; `mecanum_nav_bringup/test` 234 passed; interfaces colcon test 11 passed; final integrity/source-pin checks are recorded in the candidate evidence. |
| Status and boundary | Step 4 `CLOSED_FOR_SIM_EVAL`; Step 5/6 `IMPLEMENTED_OFFLINE_ONLY`; Step 7 `NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`. No runtime execution or runtime claim. |


### ROADMAP_STEP4_STEP5_STEP6_SAFETY_LIFECYCLE_RECEIPT_CORRECTIVE_L2 — offline verification correction (2026-10-19)

| Field | Record |
|---|---|
| Parent / scope | Exact parent `04a2ba5332ea56feb24dc3cf393114d8158bcb62`; current corrective has exactly 14 allowed paths. The historical Run001–Run007 artifact and runner set remains byte-identical to the corrective base. |
| Lifecycle and receipt contract | Lifecycle parent callbacks manage publisher activation/deactivation; activation remains NON_READY until explicit rearm. `CommandEnvelope` carries `episode_generation`; NAV2 final publication requires matching episode/reset/runtime identity. Each successful final Twist publish is followed by one identity-matching receipt, including zero safe-stop; command-publish exceptions produce no receipt. |
| Verification | Five-package build PASS; `mecanum_nav_rl/test` 701 passed; `mecanum_nav_bringup/test` 234 passed; ROSIDL interface colcon test 11 passed; isolated lifecycle and receipt contract tests PASS; historical-preservation and exact 14-path contract PASS. |
| Evidence | Current decision SHA-256 `0e1a84b8c2a8147db8ce57522aa55648241df110920830b29e28145273e988d5`; current evidence JSON SHA-256 `536b35461eb2e538e44eb2727e0aec28d670f3d1e5b5ec8be3378d992c962aad`; 46 exact path/hash/size source pins. |
| Boundary | Offline source/build/test only. No ROS/Gazebo runtime, Nav2 live, HIL, hardware, Gate B transition or runtime approval. Step 7 remains `NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`. |


### Safety lifecycle receipt corrective — source-pin accounting correction (2026-10-19)

| Field | Record |
|---|---|
| Corrected pin | `ros2_ws/src/mecanum_nav_rl/test/test_safety_lifecycle_transition.py` SHA-256 `25596f1b81ca0d3b53422123c9bba386e6e8a743b9b6d107259e6579650637bf`, size `3696` bytes. |
| Current evidence | `docs/governance/evidence/ROADMAP_STEP4_STEP5_STEP6_CONSOLIDATED_CLOSURE.json` SHA-256 `f757d8e9b035c23e27f01d44afa37082f4e62a061324ace6b0cf5fa91e349ff3`; its 46 source pins match current bytes. |
| Boundary | This append-only correction records a trailing-newline normalization before delivery. No historical WP06 data, runtime status, Gate B, or Step 7 status changes. |

### ROADMAP_STEP4_STEP5_STEP6_EVIDENCE_RECONCILIATION_L1 — 2026-10-19

| Field | Record |
|---|---|
| Underlying L2 corrective | Exact commit `dbc00940f9f70a4ee3a846ceb6fde1964c35ff19`; sole parent `04a2ba5332ea56feb24dc3cf393114d8158bcb62`; exactly 14 changed paths; 46 source pins verified against exact Git blobs including path, SHA-256 and byte size. |
| Scope distinction | Underlying L2 packet is the 14-path source/test/interface/governance change. This L1 reconciliation is a separate commit scope of exactly five governance paths only. |
| Offline tests | `mecanum_nav_rl` pytest: 701 passed; `mecanum_nav_bringup` pytest: 234 passed; interface `colcon test`: 11 passed. These are the recorded offline results for the exact underlying commit; no tests were rerun for this governance-only reconciliation. |
| Corrective semantics recorded | Lifecycle managed-publisher callback delegation; `CommandEnvelope.episode_generation`; SafetySupervisor identity propagation; NAV2 identity validation in FinalTwistPublisher; receipt only after successful final command publication; associated static regression coverage. |
| Supersedes | Earlier current-metadata attributions of the underlying packet’s parent, changed-path scope, pin count and test totals are superseded by this reconciliation. Prior Ledger entries are retained unchanged as historical records. |
| Decision / evidence / Registry / PEP SHA-256 | Decision `0d5927d672b1d7c8083c50638f9b77ec8b9eac94f17a3b27bb460aa3ae167920`; evidence JSON `16a513a01e2ba71aaac99d6c4cee71ca36c22ce6cec811d1a0e92a60d78c6e39`; Registry `f4b4edd2b882b7b573502b3b0a86198c29556dc8ca11656f29a8813707c5f076`; PEP `03a7516ed7cb449df3549559d331f3a927db40251ec62bfaf6f0efe920d32e44`. |
| Status and evidence ceiling | Step 4 `CLOSED_FOR_SIM_EVAL`; Step 5/6 `IMPLEMENTED_OFFLINE_ONLY`; Step 7 `NOT_STARTED`; `GATE_B: NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`. Evidence ceiling remains `STATIC_SOURCE_OFFLINE_BUILD_TEST_READY_FOR_STEP7_RUNTIME_CAMPAIGN`. No runtime claim. |


### STEP07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN001 — L2 review candidate

- Base: `f7f98c683d59cf4c62e462da9f37d4ffb2455c80`; Architecture SHA-256: `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.
- Scope: source/offline-test campaign guard, one-shot runner, evidence validator, C++ ROS observer, installed Gate-B Observation81 collector, and governance records. Exact pins and acceptance matrix: `docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN001_L2_EVIDENCE.json`.
- Guard seed remains pending, capacity one, acquisition count zero, runtime authorization not granted. No runner, ROS, Gazebo, Nav2, launch runtime, HIL, hardware, or PPO was executed.
- Evidence ceiling: `IMPLEMENTED_SOURCE_AND_OFFLINE_TEST_CAMPAIGN_MACHINERY_ONLY`; runtime evidence `NOT_CREATED`; Gate B `NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`. This does not alter Step 4–6 or PEP work-package statuses.


### Step-7 integrated NAV2_BASELINE Run001 candidate — offline verification

- Candidate source/offline verification: six-package colcon build PASS; `mecanum_nav_rl/test` 705 passed; `mecanum_nav_bringup/test` 237 passed; observer GTest 11 passed; interfaces colcon test 11 passed; focused campaign tests 36 passed.
- Installed closure: ROSIDL import, C++ observer executable, Gate-B console script, installed parser import and checked source-byte equality PASS.
- Test interpreter: `/tmp/roadmap-step4-pydantic.ymkohe/venv/bin/python`, Python 3.12.3, Pydantic 2.10.6. Build/install/log directories were external to the Git worktree.
- Evidence ceiling remains `IMPLEMENTED_SOURCE_AND_OFFLINE_TEST_CAMPAIGN_MACHINERY_ONLY`; no runtime execution, Gate B transition or `RUNTIME_APPROVED` claim.

### Step-7 Run001 candidate — TF ownership/evidence-matrix reconciliation

- The C++ observer and offline validator now require an observed `map -> odom` GID to map uniquely to the AMCL `/tf` publisher endpoint, and require `world -> map` to remain absent. This follows the fixed Owner TF contract; it does not assert map/world numeric equality.
- The evidence and guard manifest now enumerate each observer acceptance separately, including map-to-odom AMCL ownership, world-to-map absence, and explicit owners for scan, wheel/IMU ingress, filtered odometry, map, lifecycle state, final receipt, and `/cmd_vel` boundary. Source pins and guard-seed digest were refreshed from current bytes; the guard remains pending with capacity one and no runtime authorization.
- Reverification after the correction: six-package external colcon build PASS; focused campaign tests 36 passed; `mecanum_nav_rl/test` 705 passed; `mecanum_nav_bringup/test` 237 passed; observer and interfaces colcon tests 22 passed, zero failures. Runtime remains unexecuted; Gate B remains `NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`.

### STEP07 Run001 separated bootstrap/composite topology correction — offline verification

| Field | Record |
|---|---|
| Base and scope | Base `f7f98c683d59cf4c62e462da9f37d4ffb2455c80`; exact 23-path candidate scope, the prior 21 paths plus the composite launch and its static test. |
| Topology | Bootstrap and composite are separate one-shot process groups; composite is explicitly launched with `start_bootstrap:=false`; map/Fuel preflight stays active in both composite modes. Teardown verifies composite SIGINT/empty group before bootstrap SIGINT/empty group. |
| Verification | Six-package colcon build PASS; `mecanum_nav_rl/test` 705 passed; `mecanum_nav_bringup/test` 238 passed; observer/interface colcon tests 11 each passed; focused tests 45 passed; installed closure PASS. |
| Governance hashes | Decision `f03d04e1c6ccca2229773d4e417a68c3c280d778a2a01835b920cca1b3f172b2`; evidence `ec4c059ff3a0fa39df0b887426ae0517efda9b9820ecab6a2bad6a34135a973c`; guard manifest `11343554c3d0dec9b82ee7ef90a976e67828913fbfc991962988ba81f40830fb`; Registry `108952d170fdb8eee723bc1103b91b0776483575cdd24cebc5b797b24eac435e`; Plan `39365b348706cdfaff2d9d931d427ec018b551fa5cbc386ca10a452de49be33f`. |
| Boundary | No runtime/runner execution. Run001 guard remains pending, capacity one, acquisition count zero, `runtime_authorization=NOT_GRANTED`; Gate B remains `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. Historical WP06 Run001–Run007 files remain unchanged. |

### Step-7 Run001 lifecycle endpoint/QoS contract correction — review candidate

The corrective source contract uses `/mecanum/safety_lifecycle_state`, type `mecanum_nav_rl_interfaces/msg/SafetyLifecycleState`, and a unique `safety_lifecycle` publisher offering RELIABLE + VOLATILE + KEEP_LAST(10). C++ and Gate-B observer subscriptions use dedicated QoS with the same policy, separate from `/tf_static` and receipt QoS. The raw graph validator rejects the obsolete slash-separated endpoint and recomputes exact endpoint ownership/QoS. Receipt remains RELIABLE + TRANSIENT_LOCAL + KEEP_LAST(1). Source-pin count stays 16; refreshed changed-source pins:

| Path | SHA-256 | Size (bytes) |
|---|---|---:|
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py` | `210694c3b9c270e20d4650ca7bb8362ee703c62a0a22bfe6e4f21a8cab970190` | 23255 |
| `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py` | `448d2302755c0fc3ce270109bca7266d877db4743050da2f9216c3aa2d97aab3` | 13715 |
| `ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp` | `d713d8c67145bfdaf55d4f55c0ab5fcb4b2114013a1aa9d69cff3c27fd925519` | 29652 |
| `ros2_ws/src/step07_nav2_baseline_runtime_observer/test/test_step07_nav2_baseline_runtime_observer.cpp` | `5f2f16d1a06b17cdf5831747c89c76e7c1cdc7743ee7505c685be15e3f8708af` | 7981 |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py` | `32f1c754bfe65268317d2a2cebe34982285a0273a071fb9fb2f25649df4dc4f4` | 21067 |
| `ros2_ws/src/mecanum_nav_rl/test/test_step07_gate_b_observer_node.py` | `4f0f661f507846dd0623877a5a6b93a56e9029f93d1f7f988c745896ab06ae70` | 4580 |

Guard seed remains PENDING, capacity=1, acquisition_count=0, runtime authorization NOT_GRANTED. This candidate has offline-only scope; it makes no runtime, Gate-B, integration, or approval claim.

### Verification disposition for lifecycle endpoint/QoS correction

Offline build and independent checks completed so far: six-package colcon build passed; focused Step-7 tests passed 33; `mecanum_nav_rl/test` passed 707; observer and ROSIDL colcon tests passed 25 with zero failures. Full `mecanum_nav_bringup/test` reported 236 passed and two failures in `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py`. That path is outside this corrective's exact 13-path allowlist. One assertion freezes the current diff to the prior campaign 23-path set; another still expects obsolete `/mecanum/safety/lifecycle_state`. No edit was made to that path. Delivery is blocked; no commit or push is made. Runtime remains unexecuted, the Run001 seed remains pending/unconsumed, and Gate B remains NOT_STARTED.

### Step-7 Run001 lifecycle-QoS test-contract closure — verification continuation

| Field | Record |
|---|---|
| Scope | Exact 14-path corrective candidate; the root campaign remains the exact 23-path diff from `f7f98c683d59cf4c62e462da9f37d4ffb2455c80` to `6fbddb3db1a38908ed470f549a1c8182e022a37f`. |
| Source-pin closure | Exactly 16 unique pins. The already-pinned contract-test path `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py` is refreshed to SHA-256 `8f03f5feef72d81eb86600f2dfcabffe18765fd4db57c1484bd67ec5250dd6db`, size 27451 bytes. |
| Offline verification | Six-package external colcon build PASS; focused Step-7 tests 49 passed; `mecanum_nav_rl/test` 707 passed; `mecanum_nav_bringup/test` 239 passed; C++ observer and ROSIDL colcon tests 25 passed, zero failures; installed closure PASS. |
| Disposition | This entry supersedes the provisional blocked verification disposition above for the current corrective snapshot. No runtime execution; Run001 guard remains pending and unconsumed; Gate B `NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`. |

### Step-7 Run001 acceptance-matrix closure corrective — offline only

| Field | Record |
|---|---|
| Scope | Exact eight-path matrix/test/governance correction on top of `5fa2e89f84d683723eba8eb989cfef59059ae603`; root campaign remains 23 paths and the lifecycle-QoS corrective remains 14 paths. |
| Acceptance closure | Both current matrices list the seven lifecycle/receipt-related observer acceptance IDs. They retain one row each for `lifecycle_endpoint_qos_contract`, `receipt_qos_contract`, and `obsolete_lifecycle_topic_absent`, omit retired `lifecycle_state_publisher_owner`, and use `ACCEPTANCE_FAILED:<acceptance_id>` for raw observer failures. |
| Parser behavior | The semantic validator can reject an observed obsolete topic earlier with `LIFECYCLE_TOPIC_OBSOLETE_OR_IN_USE`; this does not replace the raw observer acceptance literal. |
| Evidence boundary | Source pin set remains 16 unique entries; the validator test pin is refreshed in guard/evidence/manifest. Run001 guard remains PENDING, capacity one, acquisition count zero, `runtime_authorization=NOT_GRANTED`. No runtime, evidence directory, Gate-B transition, integration, or approval is claimed. |

### Step-7 Run001 acceptance-matrix scope-chain closure — offline only

| Field | Record |
|---|---|
| Base/scope | Current corrective is based on `5fa2e89f84d683723eba8eb989cfef59059ae603` and is limited to the exact nine approved paths. |
| Immutable chain | Root campaign `f7f98c683d59cf4c62e462da9f37d4ffb2455c80..6fbddb3db1a38908ed470f549a1c8182e022a37f` remains 23 paths; lifecycle-QoS corrective `6fbddb3db1a38908ed470f549a1c8182e022a37f..5fa2e89f84d683723eba8eb989cfef59059ae603` remains 14 paths. |
| Source pin | The existing contract-test pin remains one of exactly 16 unique paths and is refreshed in the guard, evidence and manifest to SHA-256 `41de1850413727308aac4c49a7104f40576789d830ce3f96102ba04a0991f280` and size `28656` bytes. |
| Boundary | Run001 guard remains pending, capacity one, acquisition count zero and `runtime_authorization=NOT_GRANTED`; no runtime, Gate-B transition or integration is claimed. |


### Step-7 Run002 pre-acquire failure evidence corrective — offline candidate

| Field | Record |
|---|---|
| Base and scope | Exact base `5a44cd9910e9b6d6058d8d2d9252a86f7cf9dcd8`; 12-path Run002 corrective allowlist. |
| Historical boundary | Run001 remains `STEP07_RUN001_OFFICIAL_RUNNER_INVOKED_PREACQUIRE_FAILURE_NO_RETRY`; no raw literal or replacement evidence is invented. |
| Run002 seed | PENDING; capacity 1; acquisition count 0; `runtime_authorization=NOT_GRANTED`; retry disabled. |
| Correction | Build/host-preflight failure after exact source/guard and runtime-worktree preparation is recorded with canonical record, failure document, manifest, and checksums before guard acquisition; no lock, runtime process, or teardown. |
| Evidence ceiling | Offline mechanism only; no runtime execution; `GATE_B=NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. |


### Run002 source-pin cross-reference reconciliation

Exactly 16 unique Run002-specific source pins (SHA-256 and byte size) are shared by the pending Run002 guard, its L2 evidence, guard manifest, and Registry inventory. This entry is append-only and does not revise Run001 history or runtime status.


### STEP07 Run002 reference-aware historical guard-test correction

The 13-path Run002 corrective adds reference-aware checking of the unchanged Run001 guard pins from Git blobs at `5a44cd9910e9b6d6058d8d2d9252a86f7cf9dcd8`; missing objects and hash/size mismatches fail closed. Run002’s own 16 unique pins remain current-worktree checks. The verified scope chain is 23 → 14 → 9 → 13 paths. This entry supersedes only the provisional 12-path Run002 scope note; Run001 history, guard, outcome, Gate B and runtime-approval status remain unchanged.


### STEP07 Run003 Fuel path normalization corrective — candidate

Exact base `6d730bd54d7f99429ee4832a3f6f96beffae020f`; exact direct scope is the 13 paths recorded in the Run003 evidence. Run002 remains historical `STEP07_NAV2_BASELINE_RUN002_PREACQUIRE_PREFLIGHT_FAILED_NO_GUARD_CONSUMED`, root cause `FUEL_CACHE_PATH_CASE_NORMALIZATION_MISMATCH`, with no retry or artifact rewrite; its pre-acquire evidence mechanism was demonstrated. Run003 maps the two case-sensitive SDF URIs to exact lowercase owner/model cache paths, without download or ambiguous search. Depot host asset remains unverified and unprovisioned by this candidate. Run003 guard remains PENDING, capacity 1, acquisition count 0, `runtime_authorization=NOT_GRANTED`. Evidence ceiling is offline source/tests only; Step 7 and Gate B remain `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. Decision SHA-256 `77f7711392af8bbfa72b59042e8190a9f526ae0f2a05924bc75f2fe55cec94b8`; evidence SHA-256 `c870b6f641f27a74716e0e28896e266fd5b3c6171e17714cc29d264100bbdcd8`; manifest SHA-256 `d4e998d624c0de11fbb3f07d4be4c96d43a13741a1e90fe7414b79055bb0dba2`.


### STEP07 Run003 scope and historical Run002 test reconciliation — Owner-authorized correction

The active Run003 candidate scope is exactly 14 paths: the prior 13-path Run003 candidate plus `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run002_runtime_guard.py`. This test validates each Run002 historical source pin from the Git blob at `6d730bd54d7f99429ee4832a3f6f96beffae020f`, checking SHA-256 and byte size with no worktree fallback; it also verifies the Run002 guard blob itself is byte-identical. Run002 semantics, guard, runner, evidence, manifest and historical outcome remain unchanged, and Run002 is not retried. The Run003 runtime source-pin set remains exactly 16 entries and does not add the historical test path. Run003 remains PENDING, capacity 1, acquisition count 0, `runtime_authorization=NOT_GRANTED`; no runtime/evidence is claimed, Gate B remains `NOT_STARTED`, and `RUNTIME_APPROVED` remains `NOT_APPROVED`. Current decision SHA-256 `04ef84ed664fcdde8d0d9e6eb902632e1a001e8687f3caa077a33dfccadf3d29`; evidence SHA-256 `3c2ef0305b1031f69979131a5b371c46b61607008f2756b5d4abc3ace2907054`; guard-manifest SHA-256 `ec8d70b5c851f32f0bfbd808a2bb8430b8f0907e3528473104aa86824ac32178`. This entry supersedes the earlier candidate-only 13-path Run003 scope description; all parent Ledger bytes remain an exact prefix.


### STEP07 Run003 14-path scope and pinned contract-test hash reconciliation

Run003 direct scope is exactly 14 paths, including the Owner-authorized historical Run002 guard-test correction. The scope-chain test now compares the exact Run003 path set and preserves historical cardinalities 23 → 14 → 9 → 13 → 14. The existing Run003 source-pin inventory remains 16 unique entries; its already-pinned bringup contract test is SHA-256 `dbe624a21d85b10b0e035514d20d156d7eea7fa253562c3d1c2bdb8cfc8509fd`, size 32084 bytes. Run002 historical pin verification reads the exact Git blobs at `6d730bd54d7f99429ee4832a3f6f96beffae020f`, rejects missing objects and mismatches, and verifies the Run002 guard byte-identically without worktree fallback. This entry supersedes the previous candidate-only Run003 scope/hash references; parent Ledger bytes remain an exact prefix. Decision SHA-256 `04ef84ed664fcdde8d0d9e6eb902632e1a001e8687f3caa077a33dfccadf3d29; evidence SHA-256 `c5ab90e50bbfd778ba4fd3f190bd69a5578bdf49ff02026923215e1fd24b4af2; manifest SHA-256 `ee823d94d6a8d2e6dc2602201a43d7f29526d42e29202b8f5c2b6f145049d399. Run003 remains PENDING/capacity-one/acquisition-zero/NOT_GRANTED; no runtime executed, Gate B remains NOT_STARTED, and RUNTIME_APPROVED remains NOT_APPROVED.


### STEP07 Run003 scope assertion and pin finalization

The exact active Run003 scope test now includes the Owner-authorized Run002 historical guard test and asserts exactly 14 distinct paths. The historical 23/14/9/13 path scopes remain separate. The existing 16-pin Run003 inventory is refreshed for its existing pinned bringup contract-test path to SHA-256 `d16c487554495e73dbbdd8f7df857b383897db6a804c85aef9a1572c2486203d`, size 32084 bytes; no additional source pin was added. Evidence/manifest guard-seed references were recomputed. This entry supersedes the preceding candidate-only pin references; all Ledger bytes at the base remain an exact prefix. Decision SHA-256 `04ef84ed664fcdde8d0d9e6eb902632e1a001e8687f3caa077a33dfccadf3d29; evidence SHA-256 `2f26ff124310e55568605f8e8d9958fa19c673955e257bcd41bc35fe0bc762f6; guard manifest SHA-256 `121b0f1b02dce97811397168286a55bddc99160b61062fb09b8e93fdde57fa65.


### STEP07 Run004 Python runtime environment closure — L1 candidate

| Field | Disposition |
|---|---|
| Base / integration | `fdc0e299515bda2286832aabec635948629517b5` / `f7f98c683d59cf4c62e462da9f37d4ffb2455c80` |
| Scope | Exact 17-path Run004 candidate; 20 unique source pins are a distinct inventory. |
| Run003 | Historical immutable `STEP07_NAV2_BASELINE_RUN003_PREACQUIRE_PREFLIGHT_FAILED_NO_GUARD_CONSUMED`; missing Pydantic V2 in Python 3.12 overlay (`PYDANTIC_V2_RUNTIME_ENVIRONMENT_CLOSURE_MISSING`); not a Fuel/Nav2/Gate B/safety/robot-runtime failure; no retry. |
| Pins | Run001/Run002/Run003 verified via exact Git blobs at pinned commits, SHA-256 and size, no checkout fallback; Run004 verified from current worktree bytes. |
| Environment | `/home/hazan/step07_runtime_python312_pydantic_2_10_6/bin/python`, Python 3.12, `pydantic==2.10.6`; Owner-invoked external venv helper only; runner performs no installation/network access. |
| Offline verification | Step-7 tools 138 passed; RL 707 passed; bringup 239 passed; six-package build PASS; observer/ROSIDL tests 25 passed; py_compile 9 files PASS. |
| Guard / ceiling | PENDING, capacity 1, acquisition 0, `runtime_authorization=NOT_GRANTED`; no runtime evidence; Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. |
| Decision / evidence / manifest SHA-256 | `4764d4e183f51ed5a58a3807c5c51ddd67e429b04c13f0c184c98947c716de66` / `65365fa083db06098e3dfe63568a9ba1ff7f78eda596c9c3c2ab301e1a20a444` / `7fd9eb0d27e45fa348233b0f7df7de8cf34ba0caa550c28c701c52e80f4a1c6d` |
| `supersedes` | Supersedes only the pending Run004 environment-closure candidate description and its previous incomplete pin-reference reconciliation; Run001–Run003 historical evidence/outcomes remain immutable. All parent Ledger bytes remain an exact prefix. |


### STEP07 Run004 provisioning helper environment decoupling — L1 corrective

| Field | Disposition |
|---|---|
| `supersedes` | Supersedes the prior Run004 helper contract only; original Run004 17-path candidate and Run001–Run003 history remain unchanged. |
| Base / scope | `cbf59ff938d8b96ec650859d9367bc6cb840f0c6`; exact 11-path corrective scope, with exact four-path source/test Phase A. |
| Correction | Provisioning helper validates outside-repository Python 3.12, exact Pydantic 2.10.6, executable path and package/version fingerprint. It does not require or import `rclpy`; that check remains in the runner after ROS and overlay source. |
| Pins | Run004 20 unique current-worktree source pins; Run001–Run003 exact historical Git blobs, SHA-256/size, no fallback. |
| Offline verification | Step-7 tools 139 passed; bringup 239; RL 707; six-package build PASS; observer/ROSIDL tests PASS; py_compile/static parsing PASS; exact scopes and history PASS. |
| Guard / evidence | Run004 PENDING, capacity 1, acquisition 0, `runtime_authorization=NOT_GRANTED`; no runtime evidence; Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. |
| Decision / evidence / manifest SHA-256 | `f4dd7b7c4b24eceeae85bb08812ea32ac9c3029b681f127816349176c6997b0a` / `e3b9eaab981f7bcb44192fcc1d61af53c79878f79103037a3857adc4389ff8ff` / `1369bac8fd60586a8e2231ff9f458cdc2820cfa599c32ab6e35df98533a0c376` |
| Evidence ceiling | Source/offline candidate only; no runtime claim. Parent Ledger bytes are an exact prefix. |


### STEP07 Run005 installed package-prefix closure — offline candidate

Run004 remains the historical immutable outcome `STEP07_NAV2_BASELINE_RUN004_PREACQUIRE_PREFLIGHT_FAILED_NO_GUARD_CONSUMED`, with sole root cause `PACKAGE_PREFIX_CLOSURE_MISSING_ROBOT_URDF_FINAL_DESCRIPTION`; it was not retried. Run005 closes this source-level prefix omission by collecting and validating the exact eight package prefixes and ensuring every installed-file equality target has a collected prefix before byte comparison. No runtime semantics, Python/Pydantic, Fuel, map/world, TF, Gate-B, safety, or retry/capacity contract changed.

Exact Run005 base/sole-parent target: `b7105ccb651da6d0dcb916d7544481f7beacaae1`. Exact current delivery scope: 13 paths. Runtime source-pin inventory: 21 unique paths, SHA-256/size checked against current Run005 candidate bytes; historical Run001–Run004 pins read exact Git blobs with no worktree fallback. Historical path scopes remain 23 → 14 → 9 → 13 → 14 → 17 → 11; Run005 current scope is 13. Offline tests/build and all recorded static closures passed; no runtime was executed. Run005 guard remains pending/capacity-one/acquisition-zero/NOT_GRANTED; Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`.

Decision SHA-256 `3fe0df3816bcbfd4569ae9279b2e6be3ecf8f6041bc07295e1a14455a3ded51c`; evidence SHA-256 `fdc65d78e947fd302acc5e4885d4f2aefefc14d98e98632c8e2d8cbdbf05b777`; manifest SHA-256 `c8abea65d820b6b850e6853e7f52bd1566ff99f1c60647126f30ac871f1d4986`; Registry SHA-256 `4feffc633d5f16d9a35ced9a81b06b9d4fa5837d4789e9dd8ba0e3c2d562a793`; PEP SHA-256 `9c4f9cf66520546fb53f656c438068b896a660142bb7d9e39ff9b2fd80b53da9`. This entry is append-only; the complete parent Ledger remains an exact byte prefix. Evidence ceiling: `SOURCE_OFFLINE_TEST_CANDIDATE_ONLY_NO_RUNTIME_EVIDENCE`.


### STEP07 Run005 final-scope/source-pin reconciliation — Phase A pass

This entry supersedes the earlier Run005 provisional scope-test and pin references. The contract test requires exact 13-path `RUN005_PATHS` whether the worktree is dirty or the candidate is committed. Its already-existing Run005 pin is `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py`, SHA-256 `50e826ba266c8177ec73c450c0a8a3ea77ae33184d98b0c534c4f08f1d6f409b`, size `40187`; Run005 still has 21 unique source pins. Historical Run001–Run004 pins are checked from exact Git blobs with no worktree fallback. Historical scope counts remain 23 → 14 → 9 → 13 → 14 → 17 → 11; current Run005 scope is 13.

Phase A passed: focused scope/historical tests 46; Step-7 tools 182; bringup 239; RL 707; six-package external build; observer/ROSIDL colcon tests; installed equality 6/6; JSON/YAML/XML duplicate-key validation; Python compile; historical and scope preservation. Run004 remains immutable with sole root cause `PACKAGE_PREFIX_CLOSURE_MISSING_ROBOT_URDF_FINAL_DESCRIPTION` and was not retried. Run005 remains pending, capacity one, acquisition zero, `runtime_authorization=NOT_GRANTED`; no runtime executed; Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`.

Decision SHA-256 `6b9cb13114504f3c2b33e7187c6d32b227f79e2a101c6f57f89a99a21038f72c`; evidence SHA-256 `5a7c70bb5c9a21300d23ab0d2318223fcb1909ff6326b0b6540aba4863baedae`; manifest SHA-256 `b51c528653b9b6b58118f020e05c6d2148ae419fc8acb89563cd268dc2542986`; Registry SHA-256 `84c006da0f6fdf523e06027f1d863d0b0cedca7c698cd1b3e2fe69578a2d6b91`; PEP SHA-256 `3a594acf33142261e167f84c8834b1c7babccaeb46c77150c9597e794f12846a`. Parent Ledger bytes remain an exact prefix. Evidence ceiling `SOURCE_OFFLINE_TEST_CANDIDATE_ONLY_NO_RUNTIME_EVIDENCE`.


### STEP07_RUN005_ATTEMPT_002_FUEL_CASE_NORMALIZATION_CORRECTIVE

| Field | Result |
|---|---|
| Work item | Run005 attempt_002 canonical Fuel filesystem case correction; no new Run ID. |
| `supersedes` | Supersedes only attempt_001 candidate interpretation and current bootstrap cache-path mapping. Attempt_001 runtime outcome/evidence/consumed guard/lock remain immutable; all earlier Ledger bytes remain an exact byte prefix. |
| Attempt_001 | `STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED`; root `SIM_EVAL_FUEL_CACHE_MODEL_MISSING:OpenRobotics/Depot` → `BOOTSTRAP_EXITED_BEFORE_READINESS`; run_record SHA-256 `374565871f170fb2cbd7a9c089a2d0f47dd4e34d217357769259ef74f5409040`; no retry. |
| Attempt_002 correction | Bootstrap retains original Fuel URI casing but maps to lowercase `openrobotics/depot` and `movai/tugbot`; uppercase parents reject. No SDF/cache/network changes. |
| Scope and pins | Exact attempt_002 scope 12 paths; attempt_001 exact historical scope 13 paths. Current runtime source pins 22 unique paths; attempt_001 pins verified from Git blobs at `71ca32471f8e042a0048d319ca39cb9deff0c6f4`, SHA-256/size, no fallback. |
| Offline checks | Focused Fuel/bootstrap/Run005 tests 56 PASS; Step-7 tools 184 PASS; RL 707 PASS; bringup non-scope tests 237 PASS, with exact-scope assertions completed in final verification; six-package external build and observer/ROSIDL 25 PASS; bootstrap installed bytes equal source. No runtime. |
| Guard/evidence | Attempt_002 seed PENDING, capacity 1, acquisition 0, `runtime_authorization=NOT_GRANTED`; Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. |
| Hashes | Guard `056ffa3bc5397233c4bc7c52fabda0a21e5b55e15fb5ae509c5350e66551b85e`; evidence `30565cbc2f3cd8d8a2d8d0790cb58999d1bee9df8a370fdddf725123cfbffd99`; manifest `6a433566058add66dc50cda7b513df3328f650729bb997627f783c68dac747e8`; decision `d21b0d3cd4a9f79d9bc1204ac0617fef4282d2cb9277111c1ce90d0de9aa1682`; Registry `ea9d9f8c9fa162a81ba0bcf98e1fb354b9ca247ee5158fde87f686cce649a3b8`; Plan `48dc42186ff6626026fb8dd7f02d56926dedec3c24bdc9d885f8c51b4d377e3e`. |
| Evidence ceiling | `SOURCE_OFFLINE_TEST_CANDIDATE_ONLY_NO_RUNTIME_EVIDENCE`; exact attempt_002 commit requires independent audit and new Owner authorization before any runtime. |


### STEP07 Run005 attempt_002 final scope-test and source-pin reconciliation

This append-only entry supersedes the preceding attempt_002 test-result and source-pin metadata. The two stale fixed-count assertions were replaced with exact equality against `RUN005_ATTEMPT_002_PATHS`; no runtime or runner semantics changed. The exact direct attempt_002 scope is 12 paths in dirty and committed states. Attempt_001 remains immutable at the 13-path `b7105ccb651da6d0dcb916d7544481f7beacaae1..71ca32471f8e042a0048d319ca39cb9deff0c6f4` diff.

The current Run005 source-pin inventory is exactly 22 unique paths. The corrected contract-test entry is SHA-256 `62f62468215d920d650657f158300b401fc4bfe83f04dd5a1be09c8cb5bcf7b2`, size 41631 bytes; the bootstrap launch remains pinned. Historical attempt_001 pins are verified only from exact Git blobs at `71ca32471f8e042a0048d319ca39cb9deff0c6f4` with SHA-256/size checks and no current-worktree fallback.

Offline results: focused tests 72 passed; full Step-7 tools 184 passed; bringup 239 passed; RL 707 passed; six-package external build passed; observer/ROSIDL colcon tests 25 passed; Python compilation and installed bootstrap launch byte equality passed. Canonical JSON/duplicate-key/encoding checks, YAML/XML parsing, 22/22 pins, guard/evidence/manifest coherence, exact scope/history preservation, and diff checks passed. Guard remains `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity 1, acquisition 0, `runtime_authorization=NOT_GRANTED`; no lock. No runtime executed; Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`.

| Record | SHA-256 |
|---|---|
| Decision | `ba12bd8e4d24a17e3455622770cf0449dc2724216b93411ee8444fa4ae7d58db` |
| Evidence | `79ebedc1c3831760be2b8c5bc2c588588cd237e377d1ba0ff6ff759ff2ee1ed2` |
| Guard manifest | `b95b01b7f98490ae9e157e471790d1d36cb835c8330f91c1ddfc2b1de09b4caa` |
| Guard | `ad5feb501244511edbe2fe9aded8e53d984453182aff0b3d14939e8a46dff181` |
| Canonical Source Registry | `d6b0ba9b3492f17006a887e7316db117806ceea1936fe317e14194947ca7903f` |
| Project Execution Plan | `05f3f27bb736a306cbd5cac71a8c026b994932fe20f711559a783542655564af` |

Evidence ceiling: `SOURCE_OFFLINE_TEST_CANDIDATE_ONLY_NO_RUNTIME_EVIDENCE`. This entry supersedes only prior current-attempt_002 scope/pin/test metadata. The exact parent Ledger byte sequence remains an unchanged prefix.


### STEP07 Run005 attempt_002 isolated runtime checkout corrective — offline candidate

| Field | Result |
|---|---|
| `supersedes` | Supersedes the prior attempt_002 runner checkout-creation method and its 12-path scope/pin summary only. Run005 attempt_001 remains immutable, consumed, and not retried; all parent Ledger bytes remain an exact byte prefix. |
| Base / scope | Corrective base and required sole parent `72d04391a9d6d83e3e18589212d566f17dc220d1`. Cumulative attempt_002 scope from `71ca32471f8e042a0048d319ca39cb9deff0c6f4` is exactly 13 paths; exact path-set test works in dirty and committed candidate states. |
| Correction | Runner now clones locally from the exact clean source checkout with `git clone --no-hardlinks --no-checkout`, checks out the exact review HEAD detached, verifies private destination `.git`, no alternates, clean status and official origin, and confirms source ref/status/origin and Git metadata are unchanged. It does not use linked worktree commands or network clone. |
| Pins | 22 unique current Run005 source pins; runner, runner-test and contract-test SHA-256/size values are refreshed in guard, evidence, manifest and Registry. Attempt_001 source pins remain exact Git-blob checks at `71ca32471f8e042a0048d319ca39cb9deff0c6f4`, with no current-worktree fallback. |
| Offline verification | Isolated-checkout runner tests 36 passed; focused bootstrap/scope tests 29 passed; Step-7 tools 185 passed; `mecanum_nav_bringup/test` 239 passed; `mecanum_nav_rl/test` 707 passed; six-package external build PASS; observer/ROSIDL tests 25 passed; py_compile and installed bootstrap byte equality PASS. |
| Guard / evidence | Attempt_002 guard remains `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity 1, acquisition count 0, `runtime_authorization=NOT_GRANTED`, no lock. No runtime or official runner was invoked; Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. Evidence ceiling remains `SOURCE_OFFLINE_TEST_CANDIDATE_ONLY_NO_RUNTIME_EVIDENCE`. |
| Record hashes | Decision `ddff30ade74efaf4d8d8e202de4decdb5594766589097a29a2d6780e7f088180`; evidence `6f4ad54ecfd3b51a17c3a1251ef1322a63b4a9222fca1c47220dfa0bcdb8a24b`; guard manifest `22e1d9b6bc9d013a831b0ffbb06bddce8a18b05c1ab6092fac88a42a61761818`; guard `4be7b4bd00324ba023c11a2717cdfcc91f8d9418ace98b47de40e2f181cc178f`; Registry `1b685ed46e820c48971ccced80be39644b2632c499c442d31bfd06cd3438c76a`; Execution Plan `d7a433e0502f6ab2ff0c23e4a7fa518cdf3e9862af22491e1e17c24b39aaef76`. |
| Next prerequisite | Independent audit of the exact corrective commit; no runtime authorization is granted by this candidate. |


### STEP07 Run005 attempt_002 partition and Nav2 pre-acquire corrective

| Field | Result |
|---|---|
| Date | 2026-10-20 |
| Branch / base | `step07-integrated-nav2-gateb-campaign-f7f98c6` / `87af41f45d721969f2767d36291252e3b14e3dcb` |
| Work item | Run005 attempt_002 caller-owned partition, Nav2 provider and installed runtime artifact closure corrective; no new Run ID. |
| `supersedes` | Supersedes only active attempt_002 candidate scope/pin/verification metadata. The original attempt_002 13-path scope, attempt_001 outcome, and invocation_002 runtime evidence remain immutable. Parent Ledger bytes are retained as an exact prefix. |
| Current scope / pins | Exact 16-path direct corrective scope from `87af41f45d721969f2767d36291252e3b14e3dcb`. Exactly 34 unique current source pins (22 existing + 12 new), distinct from changed-path count. |
| Corrections | Child launch validates and forwards caller partition; Nav2 node executable/prefix and plugin-provider checks run before acquire; 15 installed runtime artifacts require byte equality; four Nav2 provider dependencies are profile-specific while WP05 common lock remains 14 roots. |
| Historical invocation_002 | Immutable terminal `STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED`; `COMPOSITE_EXITED_BEFORE_READINESS` caused by `LEGACY_WP06_PARTITION_LOCK`; consumed and not retried. |
| Offline verification | Focused 89; Step-7 tools 205; bringup 244; RL 707; six-package external build PASS; observer 13 C++ cases and ROSIDL 8 cases PASS; installed equality 15/15; source pins 34/34; exact scope/history checks PASS. |
| Guard / evidence | Source seed remains PENDING, capacity 1, acquisition 0, `runtime_authorization=NOT_GRANTED`; Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. No runtime executed in this corrective. Evidence ceiling `SOURCE_OFFLINE_TEST_CANDIDATE_ONLY_NO_RUNTIME_EVIDENCE`. |
| Record hashes | Decision `8e6437172e324cf0407a612209ab2759ca02634b95a003f4b685ede2bd58e90a`; Registry `c75d979c58b555c9dfed76667f96f7bcc5151033b779c9f96d43066f983a4831`; Plan `6555238df7353670e8ca35fee1260b4bcad1f60466e0c3d9faddda03f722168a`; guard `1c8468d3df731719522e64d8b21370ce33543ff07f9c1835aa920bd5c8f0b520`; evidence `265807e5cc1da274dd0f08ffcdede4791838d6e334904c1dbfbf2b6d3341fe51`; manifest `424104bafd0e164720499e6e5204a7de4d7916c87ac1d596db92ae6093c0bc87`. |
| Next prerequisite | Independent audit of the exact corrective commit; no runtime authorization is granted. |


### STEP-7 Run005 attempt_002 output-parent preflight reliability corrective

| Field | Result |
|---|---|
| `supersedes` | Supersedes only active Run005 attempt_002 runner/output-preflight metadata. All earlier Ledger bytes are an exact prefix. |
| Base / scope | Corrective base and sole-parent target `c408ccd2a2f7b11787f725a24e818ffa038e3d36`; exact direct corrective set 11 paths. The preceding partition/Nav2 corrective remains its historical 16-path diff from `87af41f45d721969f2767d36291252e3b14e3dcb`. |
| Runner correction | Removed unused `socket.if_nameindex()`. Both output targets now undergo absolute/absent/real-parent/non-symlink/non-nested checks and exclusive sentinel create/write/fsync/close/unlink probes before private clone, build, host preflight, evidence writes, guard acquisition, or process invocation. Invalid and unwritable parent failures produce stable literals and no second evidence write. |
| Invocation_003 | Invoked once; pre-acquire `PermissionError: [Errno 1] Operation not permitted` from the removed interface probe; attempted evidence persistence failed with `OSError: [Errno 30] Read-only file system`. No evidence bundle; no guard acquisition/consumption or lock; runtime execution false; bootstrap/composite/C++ observer/Gate-B observer counts zero. Runtime checkout had been created. No retry. |
| Source pins | Exactly 34 unique Run005 pins, distinct from the 11 changed paths; four existing entries refreshed, no new entry. Current source/test pin closure is SHA-256/size checked. |
| Offline checks | Focused runner/output tests 68 passed; Step-7 tools 218 passed; bringup 244; RL 707; six-package external build PASS; observer C++ 13 and ROSIDL 8 cases PASS; installed equality 15/15; 34/34 pins; exact 11-path scope and historical chain PASS. No runtime executed. |
| Guard / evidence ceiling | Source guard PENDING, capacity 1, acquisition 0, `runtime_authorization=NOT_GRANTED`, no lock. Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`; `SOURCE_OFFLINE_TEST_CANDIDATE_ONLY_NO_RUNTIME_EVIDENCE`. |
| Record hashes | Decision `3d42d895ee8bc3a583e3b2f2dd08caa751afa0a12b23914ce2e1af5ccc7ba735`; Registry `ece7c9142e77dff08fbd84aa4f1e2c0534aa4de432233dbb16516093a22484df`; Plan `69f168e695b20993a95664384e37d0dcca95d915a36a8455a6349bf35a0c7884`; guard `db5cfd94b9623c1497ba103444e931064c04cf76e7ebe455ba8a7f29a313752e`; evidence `39b220725d48f19f7b140da97868bc9c31ba5321c21dfa5c1be14572ca050813`; manifest `66bb591039054556824e0c032d552247d5319e8b5ec240bddea7960bf99bd17d`. |


### STEP-7 Run005 attempt_002 exact GZ_PARTITION process identity corrective

| Field | Result |
|---|---|
| `supersedes` | Supersedes only current Run005 attempt_002 stale-process detection and associated scope/pin metadata. Earlier Ledger bytes remain an exact parent prefix. Invocation_001 through invocation_004 historical outcomes remain immutable. |
| Base / scope | Sole-parent target `da82b2e5d65eedd80f42000283dccc42a5f6ed66`; exact direct corrective set is 11 paths. The preceding output-parent correction remains its historical 11-path diff from `c408ccd2a2f7b11787f725a24e818ffa038e3d36`. |
| Runner correction | Stale process means a non-ancestry PID whose raw NUL-delimited environment contains the exact entry `GZ_PARTITION=mecanum_step7_nav2_run005_f7f98c6`. No cmdline or textual heuristic is used. Process-disappearance and inaccessible-environment errors are ignored; diagnostics are numeric PIDs sorted numerically. |
| Invocation_004 | Invoked once; exit 2; pre-acquire literal `PREACQUIRE_FAILURE:RuntimeError:STALE_PARTITION_PROCESS_FOUND`. Runner count 1; bootstrap/composite/C++ observer/Gate-B observer counts 0. Guard stayed pending, acquisition 0, no lock; runtime false; teardown not applicable. Evidence SHA256SUMS verification PASS. No retry. |
| Source pins | Exactly 34 unique current pins; three existing entries refreshed by SHA-256 and size. |
| Offline verification | Focused runner 72; Step-7 tools 222; bringup 244; nav_rl 707; six-package external build PASS; observer CTest 1/1; ROSIDL CTest 3/3; installed equality 15/15; 34/34 pins; exact scope/history PASS. No runtime was run in this corrective. |
| Record hashes | Decision `{decision_sha}`; Registry `{registry_sha}`; Plan `{plan_sha}`; guard `{guard_sha}`; evidence `{evidence_sha}`; manifest `{manifest_sha}`. |
| Evidence status | `SOURCE_OFFLINE_TEST_CANDIDATE_ONLY_NO_RUNTIME_EVIDENCE`; Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. |
| Next prerequisite | Independent audit of the exact corrective commit. No runtime authorization is created by this record. |


### STEP-7 Run005 attempt_002 exact GZ_PARTITION process identity — final reconciliation

| Field | Result |
|---|---|
| `supersedes` | Supersedes the preceding current-candidate pin/test-count metadata only. Prior ledger bytes remain an exact parent prefix; historical runtime artifacts are unchanged. |
| Base / scope | Corrective parent `da82b2e5d65eedd80f42000283dccc42a5f6ed66`; exact direct scope is 11 authorized paths. |
| Implementation | Stale-process detection excludes ancestry and matches only a complete NUL-delimited `GZ_PARTITION=mecanum_step7_nav2_run005_f7f98c6` entry in `/proc/<pid>/environ`; inaccessible or vanished non-ancestry entries are ignored. |
| Offline verification | Focused runner/guard 82; Step-7 tools 223; bringup 244; nav_rl 707; six-package external build PASS; observer CTest 1/1 (13 cases); ROSIDL 25 tests PASS; installed artifacts 15/15; py_compile 4 files; 34/34 unique current pins. |
| Historical invocation_004 | Immutable pre-acquire `STALE_PARTITION_PROCESS_FOUND`, checksum verification PASS, no guard consumption/lock, no bootstrap/composite/observer calls, no retry. |
| Guard / evidence | PENDING, capacity 1, acquisition 0, `runtime_authorization=NOT_GRANTED`; Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`; evidence ceiling `SOURCE_OFFLINE_TEST_CANDIDATE_ONLY_NO_RUNTIME_EVIDENCE`. |
| Record hashes | Decision `ab30bbbf37f4961e70c4369e3c370590438d12f16031cb9d0fc5850653694311`; Registry `cd615016ac39364067ef8474f7d1343882cc102c775b398a201a6122c2af80ff`; Plan `9ef449ec0a8bf67f16cbcdd3cbc0e9df8513949074d0f759cbcf23e37bfcaf65`; guard `e71580a8c3ffb0feb7740f8aa194ad2206ce18f9e60cfc9fb4b5ad1c600da36a`; evidence `fe28092b4589cf85b270fdc6e8696197687626aa32ca33f85e3360f36db462e6`; manifest `a012aae26afbc5af4c025f7d70d3ef6a562b34c4659c361cccdf86622f9c5f93`. |
| Next action | Independent audit of the exact corrective commit. |

### STEP-7 Run005 attempt_002 host transport and terminal evidence corrective

| Field | Result |
|---|---|
| `supersedes` | Supersedes only active Run005 attempt_002 host preflight and terminal-record handling metadata. Earlier Ledger bytes remain an exact parent prefix. Invocation_001–005 artifacts remain immutable. |
| Base / scope | Parent target `99d5c29c1c302260a8971e19e46f93d778a52f86`; exact current direct scope is the 11 authorized paths. |
| Host transport | Before guard acquisition: exact campaign `GZ_PARTITION`, valid `socket.if_nameindex()` entry, UDP loopback bind/close without sending, and `gz topic -l`. Stable failure prefix `GZ_TRANSPORT_HOST_CAPABILITY_UNAVAILABLE:`; pre-acquire evidence, no lock/process. |
| Terminal handling | After acquisition, SIGTERM raises `RUNNER_INTERRUPTED_BY_SIGNAL:SIGTERM`, then composite-before-bootstrap teardown and terminal record/manifest/checksum finalization. Prior signal handler restored. SIGKILL is uncapturable and may prevent final evidence. |
| Invocation_005 history | Immutable saved run record `5ffa675f8ec846d09a6c7e70ebaa3689eb7566f03398db565c4bd53874b360da` exists and reports `BOOTSTRAP_READINESS_TIMEOUT`; bootstrap 1, composite 0, observers 0; guard consumed; teardown completed but not clean. Bootstrap log records `getifaddrs` and UDP socket permission failures. The run record exists, so “external termination prevented final record” is contradicted by the saved artifact and is not adopted. |
| Source pins | 34/34 existing unique current-worktree source pins refreshed by SHA-256 and byte size; no pin added. |
| Evidence status | Source/offline candidate only; no runtime run in this corrective; Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. |
| Record hashes | Decision `f1da8032e445e743f3c5b2182972c60a6494a568eb1706684687126887f566f6`; Registry `2d16d344dff91e079c270b5a3513e83f63ef791b5482802a18975496128986d4`; Plan `39dee18a77ec1b4283c05e79872d5310a7b1cec1350b30a23acb9e538a47c53d`; guard `1b11297c2a8ff391c4bcf556ca6c11a935b85b8d0f489441d8d467faf367cf5c`; evidence `a0dee26a56d10a896939588f4f0b3b1b287fbf293edf313cd69c9e3ba276beee`; manifest `84cd34016d1c2784df0ad4a911507dae02b3f067bb9fe9758e5d4db45b6abc7f`. |
| Next action | Independent audit of the exact corrective commit; future runtime only under a separate exact Owner authorization and a live session/poll that waits through terminal exit. |


### STEP-7 Run005 attempt_002 terminal verdict and ROS discovery preflight corrective

| Field | Result |
|---|---|
| Base / scope | `87ee34b1a945ecc12b525fe9f4711a368c0bdbc3`; exact current direct diff is the authorized 11-path set. The 34 runtime source pins are a separate inventory. |
| Terminal verdict | PASS requires all acceptance booleans true, no failure literals, and complete, ordered, clean, verified teardown. Any SIGTERM, pre-teardown failure, false acceptance, or unverified/incomplete teardown is FAIL. Verdict failure is recorded as outcome, distinct from checksum/filesystem finalization errors. |
| Teardown / signals | Best-effort composite before bootstrap; inaccessible `/proc`, kill or wait failures remain unverified and fail. SIGTERM is converted to `RUNNER_INTERRUPTED_BY_SIGNAL:SIGTERM`; original handler is restored. SIGKILL, power loss, or unwritable filesystem cannot guarantee durable evidence. |
| ROS host preflight | After ROS/overlay sourcing and before guard acquisition, check CLI flags and run bounded `ros2 topic list --no-daemon --spin-time 3`; empty graph is allowed. Permission/socket errors, timeout, nonzero, or network-error output fail closed with pre-acquire evidence. Exact-partition `gz topic -l` remains. This is capability evidence only, not a runtime graph pass. |
| Invocation_005 | Immutable record exists; `BOOTSTRAP_READINESS_TIMEOUT` after acquisition, bootstrap 1, composite/observers 0, teardown completed but not clean/order-correct. Bootstrap log contains interface/socket permission errors. Evidence does not support the claim that external termination prevented the record. No history changed. |
| Offline verification | Focused Run005 runner/guard 116; scope 2; Step-7 tools 257; bringup 244; nav_rl 707; six-package external build PASS; observer 13 and ROSIDL 25 PASS; installed source equality 15/15; source pins 34/34; JSON/YAML/XML, history, scope, Ledger-prefix and diff checks PASS. No runtime was run. |
| Guard / evidence | Seed remains PENDING, capacity 1, acquisition 0, `runtime_authorization=NOT_GRANTED`, no lock. Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`; evidence ceiling `SOURCE_OFFLINE_TEST_CANDIDATE_ONLY_NO_RUNTIME_EVIDENCE`. |
| Next action | Independent audit of the exact corrective commit; a later runtime requires separate exact Owner authorization. |


### STEP-7 Run005 attempt_002 SIGTERM/guard handoff corrective — final offline reconciliation

| Field | Result |
|---|---|
| `supersedes` | Supersedes only current Run005 attempt_002 SIGTERM boundary/finalization semantics and associated source-pin/scope metadata. All prior Ledger bytes remain an exact parent prefix; invocation_001–005 historical artifacts remain immutable. |
| Base / scope | Parent `bee34dd2d689fe585ae12000058b2f2903196659`; current direct corrective scope is the exact authorized 11-path set. |
| Signal/acquisition boundary | Handler is installed before pre-acquire. Pre-acquire SIGTERM preserves pending guard state and emits pre-acquire evidence if writable. SIGTERM is masked only around acquisition/handoff; acquired state is marked before unmasking. A pending signal after mutation is a consumed FAIL. |
| Terminal evidence | SIGTERM in campaign enters FAIL handling. In teardown/finalization the handler latches without throwing; best-effort composite-before-bootstrap teardown continues. Before handler restoration, interruption resynchronizes run_record, manifest, and checksums to FAIL when writable. Prior handler is restored once. SIGKILL, power loss, and unwritable storage cannot guarantee durable evidence. Verdict failure is distinct from checksum/filesystem failure. |
| Phase A verification | Focused runner/guard 122; scope-chain 2; Step-7 tools 263; bringup 244; nav_rl 707; six-package external build PASS; observer C++ 13 and ROSIDL 8 PASS; installed-source equality 15/15; py_compile 4 Python files; current pins 34/34; canonical JSON/YAML/XML, historical Git blobs, exact scope, and diff checks PASS. |
| Guard / evidence | Seed remains PENDING, capacity 1, acquisition 0, `runtime_authorization=NOT_GRANTED`, no lock. No runner/runtime was invoked. Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`; evidence ceiling `SOURCE_OFFLINE_TEST_CANDIDATE_ONLY_NO_RUNTIME_EVIDENCE`. |
| Current pin refresh | Four existing pins refreshed by SHA-256 and exact size; 34 unique paths retained. Changed-path set and runtime pin inventory remain distinct. |
| Next action | Independent audit of the exact corrective commit. A later runtime still requires separate exact Owner authorization. |


### Run005 attempt_002 — guard mutation/process ownership corrective

`supersedes`: chỉ thay metadata/current source của corrective trên base `53b7790c23c7d4969612259a8ee06be0353babd2`; giữ toàn bộ parent-byte-prefix và lịch sử invocation.

Corrective L1 trên base `53b7790c23c7d4969612259a8ee06be0353babd2`, vẫn Run005 attempt_002. Direct scope là exact 13 path; runtime source-pin inventory giữ 34 path duy nhất. Guard mutation exception chỉ được xóa lock khi strict runtime readback xác nhận đúng seed PENDING chưa acquire. Sau replacement hoặc unmask failure, strict readback CONSUMED đúng commit/authorization/count=1 đi vào post-acquire FAIL và terminal evidence. Readback không xác định giữ lock, ghi UNVERIFIED và không fallback sang source checkout.

Cả bốn component dùng cùng owned-spawn helper: SIGTERM được latch trong registration; child handle được ghi ledger trước PGID/snapshot. Teardown lấy ledger kể cả khi caller chưa nhận assignment. Chỉ signal process group đã xác minh; nếu không xác minh được, thử dừng chính child đã biết và ghi FAIL/unverified. Thứ tự composite trước bootstrap, acceptance, partition, QoS và capacity-one không đổi.

Phase A PASS: focused runner 142, guard 15, historical guard 19; full Step-7 tools 299, bringup 244, RL 707; build sáu package ngoài worktree; observer 13 và ROSIDL 8; py_compile sáu file; installed/source equality 15/15; source pins 34/34 sau reconciliation, JSON/YAML/XML và history/scope/diff checks. Không official runtime invocation trong corrective này.

Giữ lịch sử invocation_001–005, consumed guards/locks/evidence/runtime worktrees bất biến. Source seed còn PENDING, capacity 1, acquisition 0, runtime_authorization=NOT_GRANTED, không lock. Gate B NOT_STARTED; RUNTIME_APPROVED=NOT_APPROVED. Giới hạn: SIGKILL, mất điện hoặc filesystem không ghi được vẫn có thể ngăn terminal evidence. Evidence ceiling: SOURCE_OFFLINE_TEST_ONLY_PENDING_INDEPENDENT_AUDIT. Bước tiếp theo: independent audit exact corrective commit; runtime cần authorization riêng.

Sáu source pins được refresh theo exact bytes:

- `artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py`: SHA-256 `4f9e56c939a5dfa362672ae63d61395c6b263ccd049ff23098a0bae693f8a117`, 90789 bytes.
- `artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_run005_runtime_guard.py`: SHA-256 `325889d73bfcb4eb5b33a8373a6fc22b73fa5571893adb7626e6d8caed963dce`, 9843 bytes.
- `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py`: SHA-256 `add635ab907ea8b0b927c2dd2eea4d9ab05527d1630db6b1e6de24132fd98ce3`, 104828 bytes.
- `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py`: SHA-256 `d1432e3453bbf8145537bc41265fcfc7bce562a10ebfe6568b21c1ad2cd448be`, 17078 bytes.
- `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_runtime_guard.py`: SHA-256 `120f24891f6c39eb5af814393c879e479f4736cadd14a2bb35821a6a546ce28b`, 12752 bytes.
- `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py`: SHA-256 `376bc411bb5983be062279e8c7f5696f1af448d4fea5d48b31048ec69eb5727a`, 52485 bytes.


## 2026-10-21 — Run005 attempt_002 composite/Gate-B corrective L2

supersedes: active source/offline scope của guard mutation/process ownership corrective tại `bb5fc04fe8e309c52e468f766893ef60625e6821`; không supersede kết quả runtime lịch sử.


### Run005 attempt_002 — corrective L2 composite/Gate-B

Base `bb5fc04fe8e309c52e468f766893ef60625e6821`; exact direct scope 23 path, union pins 37/37. Owner phê duyệt L2 cho lifecycle orchestration, clock/binding/TF, observer lifetime và scan validity; filename decision L1 giữ nguyên. SOURCE_OFFLINE_TEST_ONLY_PENDING_INDEPENDENT_AUDIT. Focused 46, tools 301, bringup 248, RL 715 PASS; sáu-package external build, observer 13, ROSIDL 8, installed/source 19/19 PASS. Guard seed PENDING/capacity 1/acquisition 0/NOT_GRANTED; Gate B NOT_STARTED; RUNTIME_APPROVED NOT_APPROVED. Không official runner/runtime/integration; lịch sử và guard/ownership tại base bất biến. Next action: independent audit exact corrective commit; runtime cần authorization riêng.

Decision: `docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md`; SHA-256 `e245967f9c5b324c4d67dae70ca046bc3b8d80252197411c3021ebca3856ed36`.

- `artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json`: `2442328059cfea2143ea3660ad578bf8a69a535493459f7aec510a725c12e6aa`.
- `docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json`: `1d206e32f5604ff425d30b3dbd8b2a377593a602d9e163e18a47065ce8995afe`.
- `docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json`: `3c7ab3855df8fac785c21de85d1e3e522fffbb87aaf090b63a64fb81737f0b36`.


### 2026-10-21 — Run005 attempt_002 evidence-validator identity/verdict correction

`supersedes`: chỉ metadata/active source state của candidate offline hiện hành; không sửa bất kỳ runtime invocation hoặc historical evidence nào.

L1 corrective trên base `c8e34ead42c9c3fa6d79bf73dc221a9cc599d42a`, exact direct scope 10 path. Evidence validator nhận diện duy nhất `STEP07_NAV2_BASELINE_RUN_005` và đúng terminal verdict strings của Run005. PASS yêu cầu mọi acceptance=true, `failure_reason_literals=[]`, teardown completed/clean/order_correct/verified. FAIL terminal cần ít nhất một failure literal. Run001 identity và terminal strings cũ bị từ chối. Inventory giữ 37 source pins duy nhất; changed paths và runtime pins là các tập riêng.

Focused validator tests: 15 passed; focused validator/scope tests: 9 passed. Full Step-7 tools sau pin refresh: 306 passed (trước refresh: 305 passed, 1 stale-pin failure; sau cập nhật entry hiện hữu đã chạy lại và xanh). `mecanum_nav_bringup/test`: 249 passed; `mecanum_nav_rl/test` với external install base: 715 passed; six-package external build PASS; observer 13 cases và ROSIDL 8 cases PASS; `py_compile` 3 Python files PASS; installed/source runtime artifact equality 15/15 PASS. Source pins 37/37 SHA-256/size; exact current scope 10 path; canonical JSON/duplicate-key/encoding, YAML/XML, historical Git-blob and Ledger prefix checks PASS.

Đây chỉ là sửa identity/verdict của evidence validator. Không có official runner/runtime invocation; Run005 guard seed vẫn PENDING, capacity 1, acquisition count 0, `runtime_authorization=NOT_GRANTED`, không lock; Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. Evidence ceiling: `SOURCE_OFFLINE_TEST_ONLY_PENDING_INDEPENDENT_AUDIT`. Next action: independent audit exact corrective commit.


### 2026-10-21 — Run005 attempt_002 GZ_IP transport binding / graceful teardown L2 corrective

| Field | Value |
|---|---|
| Work item | STEP07_RUN005_ATTEMPT_002_GZ_IP_TRANSPORT_BINDING_AND_GRACEFUL_TEARDOWN |
| Parent / integration base | f72ac2112e0d1545a72b6a9a12764664d508aaa8 / f7f98c683d59cf4c62e462da9f37d4ffb2455c80 |
| Scope | Exact 13-path current corrective set; existing 37 unique source pins, unchanged membership. |
| Change | Validate one local IPv4 on the structured IPv4 default-route interface; bind campaign `GZ_IP` with exact `GZ_PARTITION` through all campaign children; bounded one-shot transport publish probe before guard; distinguish clean from graceful teardown and reject PASS after escalation. |
| Historical invocation_007 | Immutable runtime failure: bootstrap ready; composite readiness timeout with multicast `Network is unreachable`; final snapshot clean but lifecycle_manager required escalation. Not graceful and not PASS. No historical artifact changed. |
| Verification | Focused runner/validator 159 PASS; scope 4 PASS; bringup 250 PASS; RL 715 PASS; external six-package build PASS; observer 13 and ROSIDL 8 PASS; py_compile PASS; installed/source equality 15/15 PASS. Full Step-7 tools is rerun after one-time pin refresh. |
| Guard / evidence ceiling | Seed PENDING, capacity 1, acquisition 0, runtime authorization NOT_GRANTED, no lock. No runtime executed in this corrective; Gate B NOT_STARTED; RUNTIME_APPROVED NOT_APPROVED. SOURCE_OFFLINE_TEST_ONLY_PENDING_INDEPENDENT_AUDIT. |
| Next action | Independent audit exact corrective commit; any later runtime needs separate exact Owner authorization. |


### Run005 GZ_IP/graceful corrective — verification correction

`supersedes`: trường Verification của entry “2026-10-21 — Run005 attempt_002 GZ_IP transport binding / graceful teardown L2 corrective” ngay phía trên; parent-byte-prefix và lịch sử còn lại không đổi.

| Check | Result |
|---|---|
| Scope / guard-contract focused | 35 passed; exact historical/current scope focused 4 passed. |
| Full Step-7 tools | 307 passed sau làm mới pin và thêm guard regression test. |
| Full bringup / RL | 250 / 715 passed; RL dùng `/tmp/run005_l2_colcon_install`. |
| Build / observer / ROSIDL | Sáu package external build PASS; observer 13 và ROSIDL 8 PASS. |
| Python / installed source | `py_compile` PASS; installed runtime artifacts 15/15 byte-equal. |
| Runtime | Không chạy runner/runtime; invocation_007 giữ nguyên là historical failure, teardown không graceful. |


### Run005 attempt_002 — default-route resolver corrective

Base `e921b04e9ef8dc933a76966cf101613fab0f8062`; active exact scope 11 paths. Invocation_009 remains immutable pre-acquire failure `GZ_TRANSPORT_HOST_CAPABILITY_UNAVAILABLE:DEFAULT_ROUTE_EXIT_NONZERO`, guard unconsumed and no retry. Resolver changes are offline only; no runtime/network probe was run by this corrective.

Verification before final source-pin reconciliation: runner transport tests passed; bringup 251 passed; RL 715 passed with `/tmp/run005_composite_install` external install base; six-package external build passed; observer 13 and ROSIDL 8 passed; installed/source equality 15/15; py_compile passed. Full Step-7 tools had 308 passed and one expected stale existing source-pin mismatch for the modified runner; the guard pin entry was then refreshed without changing the 37-path inventory. Full Step-7 tools and final coherence are rerun after that refresh.

Guard seed remains PENDING, capacity 1, acquisition count 0, runtime authorization `NOT_GRANTED`, no lock. Gate B remains `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. Evidence ceiling: `SOURCE_OFFLINE_TEST_ONLY_PENDING_INDEPENDENT_AUDIT`.


### Run005 attempt_002 default-route resolver corrective — final offline verification

This entry supersedes the interim verification snapshot immediately above; all earlier ledger bytes are preserved. Exact base `e921b04e9ef8dc933a76966cf101613fab0f8062`; direct corrective scope is the exact 11-path allowlist. The pure-Python resolver does not invoke `ip`; it parses `/proc/net/route`, verifies the lowest-metric route interface through sysfs, uses UDP `connect()` to TEST-NET without sending, and confirms the selected source via interface address lookup. Exact `GZ_PARTITION` and validated `GZ_IP` continue through the bounded publish probe and campaign child processes.

Invocation_009 remains immutable: pre-acquire failure `GZ_TRANSPORT_HOST_CAPABILITY_UNAVAILABLE:DEFAULT_ROUTE_EXIT_NONZERO`, guard not consumed, no retry. The saved literal does not establish why the former command returned nonzero. This corrective did not modify invocation_009 evidence/runtime checkout/guard/lock and ran no runtime.

Verification: focused runner/guard/scope 180 passed; full Step-7 tools 310 passed; bringup 251 passed; RL 715 passed with external install base `/tmp/run005_default_route_l1_install`; six-package external colcon build passed; observer 13/13 and ROSIDL 8/8 passed; `py_compile` passed for four Python files; installed/source runtime files 15/15 equal; source pins 37/37 SHA-256 and byte size; JSON canonical/duplicate-key/UTF-8, YAML duplicate-key parsing, XML parsing, historical preservation, exact scope, Ledger parent-byte-prefix, and diff checks passed.

Current artifact hashes — guard `6539bda341ace90f2c595572063b8c95ba41ea92017c6c803847722adf5097e5`, evidence `e563268b209f8c96adbd25aa426cf2f15004a1d9ff799871320aaab5f5bd7789`, manifest `5c147a1d58feaa1d3dd5571a6dbb4e7d377019284c4fc805b1587c645f9588e6`. Guard remains PENDING, capacity 1, acquisition count 0, `runtime_authorization=NOT_GRANTED`, with no lock. Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. Evidence ceiling: `SOURCE_OFFLINE_TEST_ONLY_PENDING_INDEPENDENT_AUDIT`; next action is independent audit of the exact corrective commit.


### 2026-10-22 — Run005 attempt_002 L1 costmap integer / teardown escalation corrective

`supersedes`: active source/offline candidate state only; no historical runtime verdict or evidence is superseded.

Branch `step07-integrated-nav2-gateb-campaign-f7f98c6`; source base / intended sole parent `a383f258b02a0f9a22b2dc72fb937dbcaba6973a`; exact authorized corrective scope in evidence is 12 paths. The runtime YAML now represents required local costmap `width` and `height` as integer `4`; global costmap contains neither field. The focused contract parses YAML and requires exact integer scalar types for any existing global/local costmap width/height while retaining historical scope assertions. Runner teardown now marks `process_group_teardown_graceful=false` if launcher log/record has SIGTERM or SIGKILL escalation after SIGINT, even if the final snapshot is clean. Invocation_010 remains immutable historical runtime FAIL: controller_server `InvalidParameterTypeException` from YAML float `height: 4.0`, followed by composite readiness timeout. No historical evidence, consumed guard, lock or runtime checkout was modified; no runtime was invoked.

Phase A freeze was recorded after source checks: focused regression tests PASS; full Step-7 tools 311 PASS; bringup full suite had 252 PASS in the clean-scope run; RL 715 PASS with external install base; six-package external build PASS; observer 13 and ROSIDL 8 PASS; `py_compile` PASS; installed/source equality 15/15 PASS. A final bringup rerun returned 247 passed / 5 failed because generated untracked colcon `log/` paths caused existing exact-scope assertions to fail. The directory was left untouched. Thus final worktree exact-allowlist verification fails and delivery checks are not all green. `git diff --check` and `git diff --cached --check` pass. No commit or push was made.

Source pin inventory remains 37 unique paths with refreshed hashes and byte sizes; membership unchanged. Guard seed remains PENDING, capacity 1, acquisition count 0, `runtime_authorization=NOT_GRANTED`, no source lock; Gate B `NOT_STARTED`, `RUNTIME_APPROVED=NOT_APPROVED`. Evidence ceiling `SOURCE_OFFLINE_TEST_ONLY_PENDING_INDEPENDENT_AUDIT`.

Final record hashes at ledger append: guard `b98e77c860522645e1830c287ae5dc6189d797b1a00027bd6ca15ec3841ab095`; evidence `4974523366b717f97ff520f256f26786ca4a83d48ad940d506b61205820c88b8`; manifest `0ba6417ab937973a3f39151ab92487b16fc2157898a4ec9edb7e2e5121f5d940`. Next action: resolve the untracked colcon log scope contamination under an explicit permitted workspace-hygiene action, rerun required exact-scope checks, then review the exact candidate commit before any separate runtime authorization.


### 2026-10-22 — Run005 attempt_002 actual-scope reconciliation

`supersedes`: exact-scope interpretation and interim final-test snapshot in the immediately preceding Run005 L1 corrective entry; it does not supersede any runtime verdict.

The Owner-authorized one-time cleanup precheck confirmed exactly the 11 reported tracked candidate paths plus only `log/COLCON_IGNORE`, symlinks `log/latest` and `log/latest_test-result`, and `log/test-result_2026-10-22_08-55-51/logger_all.log`; no symlink was followed. Only the specified `log/` directory was removed. Actual direct diff against `a383f258b02a0f9a22b2dc72fb937dbcaba6973a` is 11 paths. The authorized allowlist has 12 paths and additionally permits unchanged `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py`. Guard, evidence, manifest and contract test now encode these as separate sets.

After the scope correction, Phase A passed: bringup 253, RL 715 with external install base, focused scope-chain tests 5, full Step-7 tools 311 after pin refresh, six-package external build, observer 13, ROSIDL 8, `py_compile` four files, and installed/source equality 15/15. All generated build/test/log output remained under `/tmp`; no worktree `build/`, `install/`, or `log/` remains. Source pins retain 37 unique paths; membership is unchanged.

Guard remains PENDING, capacity 1, acquisition 0, runtime authorization NOT_GRANTED, no lock. Gate B NOT_STARTED and RUNTIME_APPROVED NOT_APPROVED. No runtime invocation occurred. Evidence ceiling remains source/offline only.


### 2026-10-22 — Run005 attempt_002 QoS evidence-chain L1 source-pin closure

`supersedes`: current candidate pin/scope metadata only; invocation_011 and all earlier runtime outcomes remain immutable.

| Item | Result |
|---|---|
| Branch / base | `step07-integrated-nav2-gateb-campaign-f7f98c6` / `9fad09f333b93c8f63d9c4044af41d04d40be8c0` |
| Phase A | `SOURCE_FREEZE=TRUE`; offline-only |
| Actual direct paths / authorized allowlist | 14 / 15; decision path is the sole authorized unchanged path |
| Source pins | 38 unique, all SHA-256 and byte sizes verified |
| Focused runner/validator/guard; Step-7 | 181; 313 PASS |
| Bringup; RL | 254; 715 PASS (external install `/tmp/run005_qos_final_install`) |
| Build / observer / ROSIDL | Six-package external build PASS; 14/14 observer; 8/8 ROSIDL |
| Python / byte equality | `py_compile` 6 files PASS; 15/15 data artifacts and 2/2 QoS modules byte-equal |
| Runtime | None invoked; invocation_011 remains historical runtime FAIL and unchanged |
| Guard | PENDING, capacity 1, acquisition 0, `runtime_authorization=NOT_GRANTED`, no lock; Gate B NOT_STARTED; RUNTIME_APPROVED NOT_APPROVED |
| Evidence ceiling | `SOURCE_OFFLINE_TEST_ONLY_PENDING_INDEPENDENT_AUDIT` |

No Safety, Nav2, controller, Gazebo, launch, or public interface semantics changed. The new pin is the existing runtime source `safety_lifecycle_node.py`; test-only observer source is not pinned. Decision wording remains unchanged. Parent Ledger bytes are an exact prefix.

Governance hashes (SHA-256 / byte size): guard `77711360f20dfaf22bd2dd5f9f1a6b76cb7d630ea1b5f3e6d1618e4482dc0761` / 28563; evidence `d20cac642752803d7009a6610ce211d9eaec287c0a08d2fb0c4e1df3c365f1b5` / 48417; manifest `6ba081717bf1767dfa644b055e000398daf4c47788b2764caa61805cea4b63a4` / 44581; Registry `19ca00299aff85295bfd377f0b3759a14613624ef243d32ed61acc2b8d958555` / 191945; PEP `c551a9b6a0e3a514ad26615a0a31fe76c100e36ad56571709ac4c37e0cbafa75` / 148527.


### Run005 L1 source-pin closure — hash-reference correction

`supersedes`: only the guard/evidence/manifest hashes recorded in the immediately preceding 2026-10-22 QoS evidence-chain closure entry; no test result, scope, pin, or historical runtime disposition changes. This append-only correction synchronizes `guard_seed_sha256` after final scope metadata was written.

- Guard: `77711360f20dfaf22bd2dd5f9f1a6b76cb7d630ea1b5f3e6d1618e4482dc0761` (28563 bytes)
- Evidence: `2ebb6a8ec506c8f4c383b189600ea5b9f336e11975ed53faf5fec56084ce5593` (48417 bytes)
- Manifest: `09ae1dea2f396caec042903bc14f1835c106259818ffaa05b8868e325c4c01cf` (44581 bytes)

Actual scope remains 14 paths; authorized allowlist 15 with the decision document unchanged. `SOURCE_FREEZE=TRUE`; guard PENDING/capacity 1/acquisition 0/NOT_GRANTED; no runtime.


### 2026-10-23 — Run005 attempt_002 Gate-B evidence collector lifecycle/order L1 corrective

`supersedes`: active source/offline candidate metadata only. Invocation_014 and earlier runtime outcomes/evidence remain immutable.

Branch `step07-integrated-nav2-gateb-campaign-f7f98c6`; base/intended parent `a04ec4d317830e01a4613fc5251f2152b9e9946e`; official `origin`. Direct scope 16 paths; authorized allowlist 17. `SOURCE_FREEZE=TRUE` means offline-only source freeze.

Both ROS collectors and the runner-owned evidence-chain readiness artifact are checked before the exact action-server check and one config-bound goal trigger. Runner waits for Gate-B artifact, stops and awaits C++ collection, records chain outcome/failure, then settles collectors before composite/bootstrap teardown. C++ validates context before endpoint queries and records fail-closed partial evidence. Exactly five valid 81D samples remain mandatory; missing correlation is a structured failure. Source pending and runtime-checkout consumed guards are distinct.

Verification: focused runner/validator/collector 182; Step-7 318; bringup 254; RL 716 (646 + 70 separate processes; external install `/tmp/step07-run005-l1-corrective/install`); six-package external build; observer 16/16 and ROSIDL 8/8; py_compile 7; installed/source equality 15 artifacts + 3 modules; 38/38 pins; canonical JSON/YAML/XML; exact scope and invocation_014 preservation. Preservation inventory 2,404 entries, SHA-256 `cf9bf612b2ec886acb1465ae3230c1de232e80140f83ff8eb682790cb7fb132d`. Parent Ledger bytes are an exact prefix.

Invocation_014 remains `STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED`, evidence untouched. Source guard PENDING/capacity 1/acquisition 0/`runtime_authorization=NOT_GRANTED`, no lock. Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. No runtime invocation, Gate-B PASS, or real readiness claim. Evidence ceiling `SOURCE_OFFLINE_TEST_ONLY_PENDING_INDEPENDENT_AUDIT`.

Guard/evidence/manifest hashes: `886adc9908e0ec778c38c904f1e40eb81bbe64b637d505ab7feedd82fe1d6350` / `01da0c2f85bbe160a01003130d5bfd4fbc01b022d5ffd3525957da8a3c944965` / `2252ff0c4f83457a23d5a0c8eb85b0f86fd48ce606b2c2c9cc4b0f49a4f2c437`.


### 2026-10-23 — Run005 L1 final scope-test and pin closure correction

`supersedes`: only the final scope-test verification line in the immediately preceding Run005 L1 collector corrective entry; all other source/test results and all historical runtime dispositions remain as recorded.

Final coherence exposed five older bringup scope assertions that did not include the new exact L1 reconciled set. The contract test now accepts that exact set while preserving equality checks. Full `mecanum_nav_bringup/test` passed 254/254; `py_compile` passed. The existing pin for `ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py` was refreshed; the inventory remains 38 entries.

Guard remains PENDING/capacity 1/acquisition 0/`runtime_authorization=NOT_GRANTED`, no lock. Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. No runtime invocation.

Updated hashes: guard `034b40893d24a26c449892088ccd0c3c0c0b365867721240f031dc0c9abb4533` (28883 bytes); evidence `d3e02fa5a5fc63a5c3efc49b9b5fa10814b0a55ea7d789731351e35cd8d1c6b9` (49383 bytes); manifest `957dcc1cf75a0547ccfa4ec49f6150eaf35cd7561fd30834b6b2e7bbbe929a9d` (44929 bytes). Parent Ledger bytes remain an exact prefix.


## 2026-10-23 — Run005 attempt_002 collector verdict/lifecycle L1 candidate

- `supersedes`: active source/offline Run005 L1 corrective candidate metadata only; it does not supersede or alter Invocation_014/015 runtime history.
- Branch/base: `step07-integrated-nav2-gateb-campaign-f7f98c6` / `7f5d16ffa4edca34672b5af82397df9bde186829`. Candidate `STEP07_RUN005_ATTEMPT_002_COLLECTOR_VERDICT_LIFECYCLE_L1_CANDIDATE_PENDING_INDEPENDENT_AUDIT`. Exact changed-path set 16; authorized set 17 with only `test_step07_run005_runtime_guard.py` unchanged.
- Invocation_015 is immutable `STEP07_NAV2_BASELINE_RUN005_FAIL_NO_RETRY_GUARD_CONSUMED`: C++ observer READY artifact then exit 2 for `QOS_METADATA_UNOBSERVABLE:receipt_qos_contract`; action server not probed, Gate-B not started, no goal, zero vectors, no evidence window, teardown clean/graceful false. Source seed PENDING and runtime checkout guard CONSUMED are distinct objects.
- Phase A/A.5: focused 209; Step-7 321; bringup 254; RL 717; six-package external build PASS; observer 17 and ROSIDL 8; py_compile 7; installed/source byte equality 15 runtime artifacts + 3 Python modules; 38/38 current source pins. Historical Invocation_014/015 inventory: 4,021 entries, SHA-256 `e936cdd3fa38a1aa4f6c25e9114fb01eadb2b1ab7d89e21f0775202244cecbb4`.
- Governance hashes: guard `9d38ab512d026f5e2824a1f4742a61b87e41836967e96bf99230f189d0d2c02e`, evidence `24c513375de0225bdd1235ccfa0479255b7ddeee2e6516c3af497a7fd6e716a3`, manifest `12594c1093aabab8f210d89f20508b42ef9167f6532815589166b8a67c6c03c7`, decision `01db420b913e77d304176a23c43f9f36ba142013c80373e8970a76d8178e002a`. Parent Ledger byte prefix: `6354f918bc8b98f15203249cb1b30adf79e1704e8b40c22fffb04e145d60f607` (275590 bytes).
- `SOURCE_FREEZE=TRUE` is source/offline only. Guard PENDING/capacity 1/acquisition 0/`runtime_authorization=NOT_GRANTED`, no source lock; Gate B `NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`. No runtime, integration, commit or push has occurred at this entry. Independent audit is the next action.


## 2026-10-23 — Run005 attempt_002 Invocation_016 lifecycle/QoS observer corrective

- `PLAN_UPDATE_PROPOSAL`: Step-7 Run005 attempt_002 L1 corrective; branch `step07-integrated-nav2-gateb-campaign-f7f98c6`; base `09014a320cd8dedb242c99d70cd24ffa0d8cd980`; candidate commit pending the one authorized commit after final checks.
- Status: source/offline candidate pending independent audit; not a completed runtime milestone. Phase A/A.5: Step-7 325, bringup 255, RL 718, six-package external build PASS, observer 20, ROSIDL 8, `py_compile` 7, installed/source 18/18, pins 38/38. Historical Invocation_014/015/016 inventory is byte-identical (7,330 entries; SHA-256 `b3d09f92abd0f4d943e30656ee7f57c5a62f0cd04d6490ee0a6c5810bcec69a6`).
- Root cause: Invocation_016 READY child PID was incorrectly compared with its `ros2 run` launcher PID; timeout settlement caused observer exit 2. Final raw graph has lifecycle QoS false because Gate-B subscriber was not started; receipt history/depth was UNOBSERVABLE (`UNKNOWN/0`) while observed reliability/durability matched. No action-server attempt, Gate-B collector, vectors or evidence window. Historical artifacts remain unchanged.
- Scope: exact 15 changed paths from `09014a320cd8dedb242c99d70cd24ffa0d8cd980`; authorized set 17. Guard PENDING/capacity 1/acquisition 0/NOT_GRANTED, no source lock. Gate B NOT_STARTED; RUNTIME_APPROVED NOT_APPROVED. No runtime, integration, HIL, hardware or Fuel provisioning.
- Blocker: independent audit. Next action: independent audit; runtime needs separate approval.
- Record hashes: guard `a1cace23adbafa80e40bfd7a0965e85e0d58b9a16c1b536028b81ed018c3a42b`, evidence `b0d684bf86f3dc4c98bf73fb6c009cce6c858a39f5ee6fbea6f2e84813848530`, manifest `286f06372abaaf73317ed2ec45c6d3e415fd605dbf4176f13ce46403aef3795b`, decision `069b7328f29dd5bbec531fba46dbcc5656f6f632019f96a86db8b50f118081e4`.


### 2026-10-23 — Run005 Invocation_017 corrective consolidated closure

`supersedes`: active candidate scope/pin metadata only; no historical invocation outcome is superseded.

- Branch/base: `step07-integrated-nav2-gateb-campaign-f7f98c6` / `31555b8ff2472811994907791f0d9b8d7f56498f`. Phase A source scope 6; Phase A.5 refreshed five existing hashes/sizes and retained 38/38 membership; Phase B actual scope 13; closure allowlist 14 with `test_step07_run005_runtime_guard.py` unchanged.
- Pre-Phase-B offline checks: focused runner/validator 179; bringup scope 6/full 256; RL 718; six-package build; observer 20; ROSIDL 8; py_compile 5; equality harness 2; parser/canonicality 25; historical Git-blob checks 4 — PASS. Post-reconciliation Step-7/coherence results follow their checks.
- Guard/evidence/manifest SHA-256: `030e8d66a44bc13eea2c40ef5643908aaa89ffe43a26edd64b853c1bac5a2016` / `64a64924215adeab8272c6aac7e3b69b0a2845f157815050521bdeb620ded9a0` / `0340916536b696dcb052d11ea79ab6b8cc246af77918bbce23b386f3febe1db3`. Decision `69337b9db5d70b4c70cf36a12f3818148791ce08f2ee88640cf7abe715e77aca`; Registry `9e3f20c87f5a2f73582b4fd3d5625610bacc027203a6d406a495d3fc53cf6f06`; Plan `0dde728c9f50aa97642d339e669a26fc695f2235a15d797840b108ef68579725`. Parent Ledger bytes remain exact prefix.
- Guard remains `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, capacity 1, acquisition 0, runtime authorization NOT_GRANTED; Gate B NOT_STARTED; `RUNTIME_APPROVED=NOT_APPROVED`. No runtime/integration/HIL/hardware/Fuel provisioning. Evidence ceiling `SOURCE_OFFLINE_TEST_ONLY_PENDING_INDEPENDENT_AUDIT`.
