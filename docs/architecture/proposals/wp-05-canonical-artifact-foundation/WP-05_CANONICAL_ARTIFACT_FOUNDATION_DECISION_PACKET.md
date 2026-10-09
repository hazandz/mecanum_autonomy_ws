# WP-05 Canonical Artifact Foundation — Decision Packet

**Work package:** `WP-05-CANONICAL-ARTIFACT-FOUNDATION`
**Status:** `DRAFT_FOR_INDEPENDENT_AUDIT_AND_USER_DECISION`
**Base:** `integration/implementation@56815516d9a9d000a7b6e41e5290e96bbed7286b`
**Authority:** Frozen Architecture, especially §48; authorized WP-03 dispositions; PEP-001 rev.0.4.0 and the canonical source registry at the stated base.

This packet is a documentation candidate only. It proposes foundation boundaries for canonical map, scenario, and hardware identity/provenance. It creates no concrete artifact instance and grants no code, runtime, simulation, HIL, hardware, motor-enable, deployment, or measurement authorization. It does not amend Architecture, PEP, Progress Ledger, Canonical Source Registry, QoS, ACR, receipt interfaces, or WP-04. The status supplied for this packet is: WP-02 `CLOSED`, WP-03 `CLOSED`, WP-04 `BLOCKED_BY_CONTRACT`, WP-05 pending independent audit and user decision, `CODE_AUTHORIZATION: NOT_GRANTED`, `RUNTIME_APPROVED: NOT_APPROVED`.

## 1. Decision scope and evidence boundaries

This packet distinguishes four things:

1. **Artifact-foundation schema:** required identity, provenance, serialization, hashing, and lifecycle fields/rules. This packet proposes boundaries only.
2. **Selected and approved artifact instance:** a concrete immutable map, scenario, or hardware profile populated with approved values and evidence. None is selected or created here.
3. **Git/document provenance:** the base, branch, commit, packet digest, review disposition, and source references for this proposal. These identify this document only; they are not an artifact approval or runtime evidence.
4. **Runtime evidence:** evidence collected in a separately authorized run under the applicable gate. This packet creates none.

`artifacts/simulation/**` is historical/reference evidence. Maps retained in ROS packages are likewise historical/reference inputs and do not become canonical map artifacts by their presence or by copying. Canonical locations and identities below require a separately selected, reviewed, and approved instance.

## 2. Map foundation

### 2.1 Canonical location and inherited decisions

Preserve the sole canonical root `artifacts/maps/<map_id>/`. WP-03 records the Project Owner/User as `MapCustodian` and map approver unless an immutable map record names a delegate and that delegate’s authority. WP-03 selected no `map_id`, map bytes, coordinates, hash, approval, or runtime evidence.

Frozen Architecture §48 controls the content-hash boundary. The two map-content members are `map.yaml` and `map.pgm`. The `map_content_hash` is derived from the canonical JSON manifest projection whose file entries pin each member’s role, relative filename, byte size, and raw-file SHA-256. The proposed non-self-referential rule omits the `map_content_hash` result field from its own digest input; the resulting value binds exactly the `map.yaml` and `map.pgm` members through those entries. `metadata.yaml` is outside this content-hash input. Do not extend this boundary to metadata or the optional pose graph under this packet.

### 2.2 Proposed members and roles

| Member | Foundation role and required identity/provenance | Hash boundary |
|---|---|---|
| `map.yaml` | Required map-server metadata for the paired occupancy image, including the selected image reference and map interpretation parameters. Its exact relative path, size, and SHA-256 are pinned in `map_manifest.json`. Concrete values and runtime interpretation remain unselected. | Included as a pinned raw-byte member of `map_content_hash`. |
| `map.pgm` | Required occupancy-image bytes named by the map metadata. Its role, exact relative path, byte size, and SHA-256 are pinned in `map_manifest.json`. | Included as a pinned raw-byte member of `map_content_hash`. |
| `map_manifest.json` | Required, versioned manifest identifying the map content members by role, relative path, size, and SHA-256, and recording the resulting `map_content_hash`. The proposed digest rule is SHA-256 over the canonical JSON UTF-8 serialization of the manifest projection with the `map_content_hash` result field omitted. A specific canonicalization profile such as `RFC8785_JCS_UTF8` remains proposed for Project Owner approval if it is not already pinned by an approved contract. Omitting the result field from its own digest input prevents self-reference. | Pins the two content members and records the derived `map_content_hash`; the digest input is the canonical manifest projection without that result field. It is not included as a third raw-file entry. |
| `metadata.yaml` | Required provenance/approval sidecar recording `map_id`, map version, the resulting `map_content_hash`, custodian/approver identity or authorized delegate, approval-record reference, and provenance needed to identify the reviewed source/revision. It must not mutate the content identity. | Excluded from `map_content_hash`, as Architecture §48 specifies. |
| `slam_pose_graph.posegraph` | Optional continuation-provenance member for later SLAM continuation. If present, its identity, source map hash, tool/format provenance, and independent SHA-256 should be recorded under a separately versioned rule. | Outside `map_content_hash`; do not imply it is required or hash-bound to map content. |

This packet does not select a `map_id`, map bytes, map frame, map origin/resolution, pose graph, approval status, map-server behavior, Nav2 parameters, or delegate. No map is approved by a manifest or hash alone. The map artifact must remain outside ROS package source as required by Architecture and the Project Tree.

## 3. Scenario foundation

### 3.1 Canonical location and serialization

Preserve `artifacts/scenarios/<scenario_id>/scenario.json` and the approved serialization convention `RFC8785_JCS_UTF8`. Preserve the `ScenarioCustodian` and approver role recorded by WP-03: Project Owner/User unless a delegate is named in the immutable scenario record.

### 3.2 Required foundation fields

The future immutable scenario record must provide, at minimum:

| Field | Required meaning |
|---|---|
| `scenario_id` | Explicitly selected, immutable scenario identity; no implicit latest/default lookup. |
| `scenario_version` and schema/provenance identifier | Version of the selected scenario values and schema contract. |
| `scenario_content_sha256` | SHA-256 identity for the canonical scenario content. To avoid a self-referential digest, the approved schema must define the digest input unambiguously, for example the JCS UTF-8 serialization with this digest member omitted; this exact rule remains for approval. |
| `gazebo_world_name` and `world_file_sha256` | Exact world identity and byte revision to which the scenario is bound; neither alone establishes coordinate-frame equivalence. |
| `coordinate_reference_id` | Explicit coordinate-reference identity. The approved oracle convention is `GT_ODOM_2D`; it is evaluator/oracle-only. |
| `approval_provenance` | Custodian/approver or authorized delegate, approval record identity, and evidence/hash references. No approval is supplied here. |
| `lifecycle_change_policy` | Required explicit rule for when a different immutable scenario may take effect and how prior facts/caches are invalidated. The value remains undecided; no mid-episode mutation is permitted by this proposal. |

`GT_ODOM_2D` is evaluator/oracle-only. Raw Ground Truth must not enter PPO, policy input, `ObservationAssembler`, `ObservationEncoder`, observation core, or deployment policy path. A scenario identity or hash cannot establish reset, contact/collision, settling, TF authority, or a runtime oracle fact.

### 3.3 Non-canonical candidate and provisional values

Every Candidate B or provisional scenario value appearing in existing `DRAFT` documents remains **`DRAFT / NON_CANONICAL / NOT_SELECTED_BY_THIS_PACKET`**, including values previously shown with a checked box or a “selected” label in a draft decision packet. This classification includes, without adopting any of them:

- Candidate identifiers such as `world_demo_candidate_b_v1`, A/B/C, `P0_TO_P1`, `P0_TO_P2`, `P1_TO_P2`, and probe labels `B0_START_P0` through `B5_RECT_UL`.
- Proposed world name/hash references such as `world_demo` and the draft world-file digest; static source/runtime metadata is not a selected scenario identity or coordinate conversion.
- P0/P1/P2 and B0–B5 pose/goal/corner literals; the `0.25 m` radius; rectangle bounds `x[-4.5,-1.5]`, `y[-3.5,-2.5]`; boundary-is-invalid; “none for v1” zones; disabled randomization; and proposed generation-change rules.
- Any other candidate bounds, goal/start, zone, seed, difficulty, randomization sample, scenario name, or provisional rule in scenario-related `DRAFT` material.

Relevant drafts include `S3_First_Scenario_Candidate_Review_DRAFT.md`, `S3_First_Simulation_Scenario_Candidate_And_Evidence_Plan_DRAFT.md`, `S3_Scenario_V1_User_Decision_Packet_DRAFT.md`, the Candidate B controlled-suitability and replacement packets/reviews, and the scenario artifact/oracle design drafts. Those documents may preserve evidence lineage, but their values are not canonical and are not selected here. No `scenario.json`, scenario ID, goal/start/bounds/zone/randomization value, Gazebo authorization, or task oracle is created or approved.

## 4. Hardware foundation

Preserve the existing canonical root `artifacts/hardware/<hardware_profile_id>/hardware_manifest.yaml`, the current JCS/SHA-256 `hardware_config_hash` contract and domain separator, and the distinct `approval.yaml` record. Preserve the manifest as the single source for hardware geometry/configuration; generated bridge/firmware geometry must later be verified against the same approved hash.

A usable `hardware_config_hash` may be computed only after every required measured value is present, valid, and approved under the separate approval record. Missing, null, or `TBD_MEASURED` inputs fail closed. The present files remain unchanged: every current `TBD_MEASURED`/null value stays as-is, `approval_status: DRAFT`, `motor_enable_allowed: false`, `approved_hardware_config_hash_hex: null`, and required evidence stays pending.

This packet infers no measurement, copies no value from source/simulation/another robot, approves no hardware, enables no motor, and authorizes no HIL, runtime, or deployment.

## 5. Decision table and later routing

| Category | Decision/boundary |
|---|---|
| Inherited from WP-03 | Canonical map root and `MapCustodian`; scenario root, `RFC8785_JCS_UTF8`, `ScenarioCustodian`, and `GT_ODOM_2D` isolation; hardware owner/approver roles, separate approval record, fail-closed measured values. These are contract dispositions, not concrete artifacts or runtime evidence. |
| Proposed for Project Owner/User approval | Map member-role/schema details and canonical manifest serialization profile; scenario foundation field schema and exact non-self-referential content-hash rule; approval-provenance representation and lifecycle-change policy; any versioned optional pose-graph provenance rule. |
| Deliberately unresolved | Map/scenario IDs and bytes, frame/coordinates, map-server/Nav2 configuration, pose graph, scenario world/goal/start/bounds/zones/randomization values, scenario approval, all missing hardware measurements, and hardware approval/hash. |
| Later work routing | Concrete map/scenario selection and approval require a separately scoped, approved artifact work package and the relevant simulation gates before runtime use. Physical values, hardware approval and HIL remain with the applicable measurement/HIL work package and Gate 3/4 obligations. Nothing here satisfies those gates. |

## 6. Non-claims and requested review

This candidate does not modify WP-04 Gate A, QoS/ACR, receipt schema, PEP status/dependencies, or the WP-03 closure record. It creates no artifact instance, measurement, code, runtime configuration, runtime guard, or approval; it makes no status transition. The requested next action is an independent static audit of this exact branch and commit, followed by the Project Owner/User’s decision on the proposed foundation fields and rules.

**Evidence state:** `DRAFT/PENDING_USER_APPROVAL`; `RUNTIME_NOT_APPROVED`; no `IMPLEMENTED_CORE`, runtime, HIL, or real-robot claim is made.
