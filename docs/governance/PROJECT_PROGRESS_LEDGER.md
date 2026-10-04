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
