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
