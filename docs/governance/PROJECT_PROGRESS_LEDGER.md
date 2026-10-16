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
