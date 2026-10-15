# WP-05 — Navigation V1 workspace source-role inventory and decision packet

| Field | Value |
|---|---|
| Classification | `L1_WORKSPACE_SOURCE_ROLE_INVENTORY_AND_DECISION_PACKET_ONLY` |
| Exact source-base snapshot | `c59d9ea65010ff80eb0202bfaa5220c5f18f25ac` |
| Inventory | `docs/governance/evidence/WP-05_NAVIGATION_V1_WORKSPACE_SOURCE_ROLE_INVENTORY.json` |
| Scope | Governance inventory/triage and routing for ten workspace source roles; exactly five allowlisted governance paths. |

## Decision and authority boundary

This record inventories existing source evidence and routes unresolved roles for later decisions. It is not source selection, a workspace source lock, or runtime authority. Static templates, policies, guards, robot-description provenance, and Gazebo transport source are evidence references only. The Gazebo transport topic `scan` is not ROS `/scan` and is not evidence of ROS `sensor_msgs/msg/LaserScan` delivery.

The inventory records all ten roles as `PENDING_IMPLEMENTATION_SOURCE_PIN`, `NOT_SELECTED`, and `runtime_eligibility: false`. It does not populate `workspace_source_locks` or change the external dependency-lock record. The references preserve exact path/byte provenance at the source-base snapshot without promoting any reference into a selected implementation source.

## Independent pending decisions and evidence

The following are separately pending and are not resolved by this inventory:

- runtime LiDAR source pin;
- ROS–Gazebo scan bridge source pin;
- scan runtime profile;
- map approval and world-frame validation;
- concrete AMCL, EKF, and Nav2 source/configuration pins;
- namespace/remap and lifecycle/startup runtime evidence;
- applicability of external package/version locks to the selected runtime;
- required measurements, including TF graph and publisher uniqueness evidence.

Missing any required source pin or evidence fails closed: no resolved Navigation V1 profile, no global `config_hash`, no Nav2 baseline bring-up, and no runtime authorization. It does not change WP-04/WP-05 technical semantics, TF ownership, map approval, Gate B, runtime evidence, or authorization. It grants or extends no `CODE_AUTHORIZATION`.

## Candidate lifecycle

At exact source base `c59d9ea65010ff80eb0202bfaa5220c5f18f25ac`, this is a review-candidate inventory snapshot. Only after independent audit PASS for the exact candidate, separate User authorization for that exact commit, fast-forward, and remote-ref verification may it be described as an integrated inventory governance record. Review push or Git ancestry alone does not establish those conditions.

## Preserved state

`WP-04: BLOCKED_BY_CONTRACT`; `GATE_A_STRUCTURAL_PRIMITIVES: PASSED`; `GATE_B: NOT_STARTED`; `WP-05: OPEN`; map remains draft/not approved; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; `RUNTIME_APPROVED: NOT_APPROVED`.
