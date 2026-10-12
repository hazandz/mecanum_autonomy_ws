# WP-04 Gate B source-disposition closure

**Status:** `CANDIDATE_ONLY_PENDING_INDEPENDENT_AUDIT_AND_SEPARATE_INTEGRATION_AUTHORIZATION`
**Change class:** `L1_SOURCE_PROVENANCE_AND_SELECTION_BOUNDARY`
**Work package:** `WP04-GATE-B-SOURCE-DISPOSITION-CLOSURE`
**Exact integration base:** `8b2f6d5c05ae8db8ce62285bd84afc401fb0d00c`
**Architecture:** `docs/MECANUM_NAV_DRL_Architecture.docx`, SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`
**Owner decision provenance:** User-supplied Owner decision in the work-package request. This record does not claim an audit report or create an audit-report hash.

## 1. Purpose and authority boundary

This L1 record classifies the supplied source files by their permitted evidence
boundary. It does not select any source as a canonical runtime contract, create
or resolve an `ObservationInputProfileV3`, or change technical semantics. At
the source base, this is a review candidate. Only after independent audit,
separate User authorization for the exact candidate, fast-forward, and remote
ref verification may it be described as an integrated source-disposition
governance record. Even then it is not active technical semantics, a resolved
profile, Gate B completion, or implementation/runtime authorization.

Architecture remains the highest authority. ACR revision 3 and Observation V3
Specification revision 5 remain the active ObservationInputProfile schema and
semantics. Existing final-issued receipt v2 and QoS6 pins remain established;
this record does not change or reclassify them. OIC revision 6, review
candidates, drafts, source examples, and configuration intent files do not
supply missing runtime-contract authority.

## 2. Git-verified source disposition

The source-byte identity for every path below was checked at immutable source
commit `8b2f6d5c05ae8db8ce62285bd84afc401fb0d00c`. These are provenance/source
file digests only. They are not contract IDs, semantic digests, profile pins,
or proof of runtime behavior.

| Source path | Source commit | SHA-256 | Permitted classification and evidence boundary |
|---|---|---|---|
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/lidar.py` | `8b2f6d5c05ae8db8ce62285bd84afc401fb0d00c` | `9422bfb38bb56140114792662f25ca7019ab95c1d4af1471dd4b3f874deedb8a` | Pure algorithm source only: 72-sector LiDAR binning. Not a runtime snapshot or ROS ingress contract, header-frame authority, range/extrinsic policy, or profile reference. |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/goal_features.py` | `8b2f6d5c05ae8db8ce62285bd84afc401fb0d00c` | `2f6e966bf1f5969536128dc2aef24aa47be3e0e16b0994e862ce971349437ed8` | Simulation-only/provenance-only. Not the canonical Gate B LocalReference contract or source. |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/measured_twist.py` | `8b2f6d5c05ae8db8ce62285bd84afc401fb0d00c` | `a11f7eeea3db6539b6ee35633666f4a2e00b9ced174e02edc67163d546529e1a` | Simulation-only/provenance-only. Not the canonical measured-twist runtime contract or source. |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/simulation/simulated_odometry.py` | `8b2f6d5c05ae8db8ce62285bd84afc401fb0d00c` | `a62a3cfc58962c94b8e03aaba2b174df6c779a30b185d50366ecd6dd98b8139c` | Simulation-only/provenance-only. Not a canonical runtime odometry contract or source. |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/synchronizer.py` | `8b2f6d5c05ae8db8ce62285bd84afc401fb0d00c` | `b47f6179fddf44ba5e688c227247adf7347850119d42a25d0cb027b1f6d672fe` | Structural primitive/non-canonical policy source. Not selected lifecycle/reset/action-barrier runtime policy or receipt-admission authority. |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/previous_command.py` | `8b2f6d5c05ae8db8ce62285bd84afc401fb0d00c` | `a1f162c44f8cb001dea66e32b70aadb0b2aed175d3bb4bf216a4bcd9279d3f50` | Structural primitive/non-canonical policy source. Not selected lifecycle/reset/action-barrier runtime policy or receipt-admission authority. |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/lifecycle_types.py` | `8b2f6d5c05ae8db8ce62285bd84afc401fb0d00c` | `e53b32ff37abc4bff62d12bfad1bf6e1837ae9ebd6808f56a5c74bd77288b97b` | Structural primitive/non-canonical policy source. Not selected lifecycle/reset/action-barrier runtime policy or receipt-admission authority. |
| `ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/episode_lifecycle.py` | `8b2f6d5c05ae8db8ce62285bd84afc401fb0d00c` | `f2ef6c5943ebb9b115f872872c1533de70a0b146caaee377f3739e7b9fb9fe16` | Structural primitive/non-canonical policy source. Not selected lifecycle/reset/action-barrier runtime policy or receipt-admission authority. |
| `ros2_ws/src/mecanum_nav_rl/config/v3/frames.yaml` | `8b2f6d5c05ae8db8ce62285bd84afc401fb0d00c` | `815bff5df49f6de07a48e61275a21c728904ff699b771a0c970507483d0ff9da` | Architecture-intent input only. Does not establish a frame-contract/profile-contract ID, digest, alias, geometry, freshness, or runtime authority. |
| `ros2_ws/src/mecanum_nav_rl/config/v3/topics.yaml` | `8b2f6d5c05ae8db8ce62285bd84afc401fb0d00c` | `7dc2156aef44e83ca767528774fff6acd543814be3a0d9eb0b6373c4f5217a2d` | Architecture-intent input only. Does not establish a topic/QoS/profile-contract ID, digest, alias, freshness, or runtime authority. |

No listed source is called a canonical runtime contract or a selected profile
reference. No new contract ID, semantic digest, topic, frame alias, measurement,
timeout, package version, or runtime fact is introduced.

## 3. Established pins and unresolved profile references

The already established final-issued receipt v2 interface pin, dependency-
closure pin, QoS6 transport-manifest pin, and QoS6 full-document pin remain as
recorded by the active Registry and integrated approval. They are not pending
and are not changed by this L1 source-disposition record. This does not claim
ROSIDL generation, ROS endpoint compatibility, QoS runtime compatibility, or
receipt delivery evidence.

The following six profile-reference groups remain unresolved; none of the
source classifications in §2 fills an ACR3-required contract reference:

1. LiDAR runtime snapshot contract.
2. LocalReference runtime contract.
3. Measured-twist runtime contract.
4. Frame/TF contract and physical geometry/extrinsic.
5. Lifecycle/reset/action-barrier runtime policy contract.
6. Concrete immutable profile source.

Where a required source is not selected by active authority, the item remains
`PENDING_OWNER_SOURCE_SELECTION`. No source is promoted by filename, package,
similar names, architecture intent, pure algorithm reuse, or simulation code.
The final-issued receipt v2/QoS6 pins remain established as stated above.

The following remain `PENDING_MEASUREMENT`: LiDAR timing/range/extrinsic,
scan–twist skew, freshness, buffer/timeout, measured-twist validity/covariance/
provenance, receipt-after-barrier timeout, TF alignment, and runtime publisher
evidence. No numeric value or evidence is supplied here.

## 4. L1/L2 boundary and fail-closed rule

This L1 change closes source disposition only. Any later work that needs to
create or change contract semantics or a public/runtime interface requires an
L2 Architecture Change Record before those semantics are used to resolve a
profile. A source selection alone cannot create such semantics.

Under active ACR revision 3, if any required source pin, evidence, or
measurement remains unresolved, the compiler must reject the entire resolved
configuration and must not emit a partial `ObservationInputProfileV3` or
partial global `config_hash`. Gate B remains `NOT_STARTED`; WP-04 remains
`BLOCKED_BY_CONTRACT`. No code, ROS/ROSIDL, adapter, runtime, HIL, hardware, or
deployment authorization is granted.

## 5. Candidate lifecycle and status boundary

At integration base `8b2f6d5c05ae8db8ce62285bd84afc401fb0d00c`, this record,
the Registry update, and its appended Ledger entry form a review candidate
pending independent audit, separate User authorization for the exact final
commit, fast-forward, and remote-ref verification. After all those conditions
are satisfied, the record may be described as an integrated
source-disposition governance record only; it does not become active technical
semantics, select a canonical runtime contract, resolve a profile, or pass
Gate B.

```text
WP-04: BLOCKED_BY_CONTRACT
GATE_A_STRUCTURAL_PRIMITIVES: PASSED
GATE_B: NOT_STARTED
WP-05: OPEN
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
```
