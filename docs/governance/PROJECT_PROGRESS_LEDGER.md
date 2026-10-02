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
