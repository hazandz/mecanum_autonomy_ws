# A0 Architecture–Config Contract Reconciliation

**Increment:** Phase A0.1 — document and static-source only  
**Status:** `RECONCILED_FOR_CORE_ONLY_A0.2_PLANNING — RUNTIME NOT APPROVED`  
**Scope date:** 2026-10-01

## 1. Authority record

| Item | Evidence | Result |
| --- | --- | --- |
| Primary architecture authority | [`MECANUM_NAV_DRL_Architecture.docx`](MECANUM_NAV_DRL_Architecture.docx) | Present; DOCX internal release date **16/09/2026**; states `ARCHITECTURE_FROZEN`, `IMPLEMENTATION_READY`, `NOT_YET_REAL_ROBOT_VALIDATED`. |
| Architecture SHA-256 | `f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860` | Recorded from the workspace DOCX. |
| Internal configuration schema | Architecture §4, table “Model”, `ResolvedConfig.schema_version: Literal["3.0"]` | **3.0** is the required target schema. |
| Project-tree authority | [`MECANUM_NAV_DRL_Project_Tree.txt`](MECANUM_NAV_DRL_Project_Tree.txt) | Present; SHA-256 `1ca7ea9473cf3e1be826c9c7aa40c4b24ffa9115577d04852eeaecbb2e46f098`. |
| External/user-provided architecture DOCX | No additional DOCX was available in the audit scope | `MISSING_FROM_AUDIT_SCOPE`; no authority conflict was observable. |

**Authority conclusion:** `CONFIRMED`. The DOCX and project tree are the authority. Existing Python, YAML, ACRs, and S3 drafts are implementation or supplementary-decision evidence only; none overrides the DOCX.

### Supplementary documents read

- [`ACR_S1_Simulated_Odometry_And_Ground_Truth_Isolation.md`](ACR_S1_Simulated_Odometry_And_Ground_Truth_Isolation.md): `APPROVED`; explicitly referenced by architecture Decision D13.
- [`ACR_S2_Snapshot_Synchronization_Temporal_Contract.md`](ACR_S2_Snapshot_Synchronization_Temporal_Contract.md): `DRAFT — PENDING_USER_APPROVAL`; it does not change schema or runtime graph.
- [`S3_D2_Final_Issued_Command_Receipt_Design_DRAFT.md`](S3_D2_Final_Issued_Command_Receipt_Design_DRAFT.md), [`S3_D6_Episode_Limit_Decision_Packet_DRAFT.md`](S3_D6_Episode_Limit_Decision_Packet_DRAFT.md), and [`S3_GT_2D_Coordinate_Relation_Decision_Packet_DRAFT.md`](S3_GT_2D_Coordinate_Relation_Decision_Packet_DRAFT.md): supplemental drafts/decision records. Their unresolved decisions remain unresolved and must not be converted to defaults.

## 2. Architecture configuration contract

References below use the DOCX heading/table because an OOXML document does not provide stable source-page numbering during static extraction.

| Requirement | Authority location | Required contract |
| --- | --- | --- |
| Immutable resolved configuration | §4 “Typed immutable configuration”; table “Model” | A frozen, `extra="forbid"` `ResolvedConfig` at schema **3.0** containing profile, mode, hash, project, topic/QoS, frame, estimation, localization, navigation, observation, action, reward, training, evaluation, safety, and acceptance contracts. |
| Fixed resolution chain | §4 | `base → runtime profile → navigation mode → approved experiment override → approved measured hardware registry → validation → immutable ResolvedConfig → config_hash`. |
| Hash lifecycle | §4 | Hash canonical JSON after resolution, excluding runtime timestamps; preserve it with model/checkpoint/rollout manifest/report. Runtime cannot mutate configuration. |
| Profile and mode | §5; table “RuntimeProfile / NavigationMode”; Decision D03 | Independent `RuntimeProfile = sim_train, sim_eval, deploy_sim, deploy_real` and `NavigationMode = LOCAL_TRAINING, MAPPING, NAV2_BASELINE, HYBRID_AI_LOCAL`; compiler must reject an invalid matrix pair. |
| Profile/mode matrix | §5; table 8 and table 31 | `sim_train` allows `LOCAL_TRAINING`; `sim_eval` allows `NAV2_BASELINE` or `HYBRID_AI_LOCAL`; `deploy_sim`/`deploy_real` allow `MAPPING`, `NAV2_BASELINE`, or `HYBRID_AI_LOCAL`. `use_sim_time` is true except `deploy_real`. |
| Tokens by target | §1 and table “Token” | Preserve `FIXED_ARCH`; permit `SIM_BASELINE` only in `sim_*`; reject `TBD_MEASURED` from `deploy_real`/Gate 4; reject `TBD_PROJECT_ACCEPTANCE` from final evaluation; resolve `REQUIRED_BUILD_INPUT` before build/deploy output. No silent placeholder defaults. |
| Topics and QoS | §§11–12; tables 12–14 | Resolved topic contracts need exact name/type/owner/QoS/frame/freshness. Required QoS mappings include scan, raw/filtered odometry, contacts, command, heartbeat, navigation state, safety state, diagnostics, clock, and TF. |
| Frames/TF | §§13–14; tables 15–17; D01/D02/D08/D13 | Main tree is `map → odom → base_link → lidar_frame`; only EKF owns `odom → base_link`; SLAM or AMCL owns `map → odom` by mode. `sim_train` has no new public odometry/TF authority in MVP. |
| Observation/action | §§20–21; D05 | `obs-v3-l72-g3-t3-c3-f32`, 81 `float32`: 72 LiDAR sectors + distance/sin/cos + measured `vx/vy/wz` + previous issued `vx/vy/wz`; action is normalized three-axis holonomic `[vx, vy, wz]` in `[-1, 1]`. |
| Limits and real deployment | §§21, 34, 38–39; D12 | Simulation baseline may be explicit only as simulation. Real motion/stopping values remain `TBD_MEASURED`; `deploy_real` remains blocked until VALID measurements, HIL, approved artifacts, and Gate 4. |
| Map identity | §48; D09 | `artifacts/maps` canonical manifest and hash are the map source of truth; package-local mutable copies are not. |
| Command/safety configuration | §§31–34; D06/D07 | Envelope requires epoch, runtime generation, source instance, and sequence. Safety is the final selector/limiter; `FinalTwistPublisher` is the sole `/cmd_vel` publisher. |
| GT isolation | §§2, 13, 15; D13 and approved ACR S1 | `sim_train` uses hidden GT only through internal `SimulatedOdometryEmulator`; policy/encoder/synchronizer must not receive GT topic, world/model pose, raw buffer, or GT-reachable object. `sim_eval`/deploy policies are also GT-isolated. |
| Goal completion | §46; D10 | Initial mission goal is position-only, with continuous settle validation of `vx`, `vy`, and `wz`; this belongs to navigation/termination configuration and cannot be invented from a generic timeout. |
| Fail-closed validation | §§1, 36, 50; table 25 | Validators must reject invalid profile/mode, unresolved target-specific tokens, topic/QoS/TF/map/command-model incompatibility, and missing required build inputs before runtime. |

## 3. Current source inventory

The current package is [`ros2_ws/src/mecanum_nav_rl`](../ros2_ws/src/mecanum_nav_rl). “Source of truth” below means only the role the file currently attempts to serve; it does not elevate the file above the architecture DOCX.

| File/path | Current function and literals | Profile/mode coverage | Assessment |
| --- | --- | --- | --- |
| [`config/base.yaml`](../ros2_ws/src/mecanum_nav_rl/config/base.yaml) | `schema_version: "1.0"`; 72/3/3/3/81 observation and 3D normalized action | No explicit mode; common base | `STALE_OR_CONFLICTING`: v1 conflicts with required v3; observation/action literals align. |
| [`config/profiles/sim_train.yaml`](../ros2_ws/src/mecanum_nav_rl/config/profiles/sim_train.yaml) | `sim_train`, `use_sim_time: true`, `world`, `odom`, `base_link`, `RPLiDAR_A1M8_1`; sim baseline limits 0.40/0.40/1.00 | One profile only; no navigation mode | `PARTIAL_MATCH`: source labels limits as simulation baseline, but lacks D03 matrix and target token enforcement. |
| [`config/models.py`](../ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/config/models.py) | Frozen Pydantic models; `RuntimeProfile` has all four names; `ResolvedConfig` is schema `1.0` with runtime/frames/obs/action/motion only | No `NavigationMode`; deploy checks are frame/use-sim-time only | `PARTIAL_MATCH`: helpful v1 scaffold, not the v3 architecture model. |
| [`config/loader.py`](../ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/config/loader.py) | UTF-8 YAML reader; rejects duplicate/non-string keys; validates to v1 `ResolvedConfig` | Generic input only | `PARTIAL_MATCH`: fail-closed YAML mechanics exist, not architecture-specific semantic validation. |
| [`config/compiler.py`](../ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/config/compiler.py) | Deep-merges `base < profile`; caller supplies expected profile | Two layers, profile check only | `PARTIAL_MATCH`: omits mode, approved override, measurement registry, complete validation, freeze/hash assignment chain. |
| [`config/hashing.py`](../ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/config/hashing.py) | Canonical sorted JSON plus SHA-256 (version `v1`) | v1 model only | `PARTIAL_MATCH`: technique matches the intended pattern; required config-hash field/provenance and v3 payload are absent. |
| [`config/agent_spec.py`](../ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/config/agent_spec.py) | Immutable policy spec; locks ordered 81-D observation, 3-D action, `[-1,1]`, limits from v1 config | No mode/profile gating | `PARTIAL_MATCH`: D05 compatible, but depends on incomplete v1 resolved config. |
| [`config/__init__.py`](../ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/config/__init__.py) | Docstring only | N/A | `NOT_IMPLEMENTED` as public architecture-facing config API. |
| `config/validators.py` | Does not exist | N/A | `NOT_IMPLEMENTED`; architecture table 25 expects architecture-specific validators. |
| `config/profiles/sim_eval.yaml` | Does not exist | Required `sim_eval` | `NOT_IMPLEMENTED`. |
| `config/profiles/deploy_sim.yaml` | Does not exist | Required `deploy_sim` | `NOT_IMPLEMENTED`. |
| `config/profiles/deploy_real.yaml` | Does not exist | Required locked `deploy_real` profile | `NOT_IMPLEMENTED`; absence is safer than inventing real limits but still leaves the contract unrepresented. |
| `config/{topics,qos,frames,acceptance,measurements}.yaml` | Do not exist | Required resolution inputs in architecture project tree | `NOT_IMPLEMENTED`. |
| `config/algorithms/ppo.yaml` | Does not exist | Required architecture project-tree input | `NOT_IMPLEMENTED`. |
| [`package.xml`](../ros2_ws/src/mecanum_nav_rl/package.xml) | Declares broad ROS/Gazebo dependencies, but no config asset contract | N/A | `UNVERIFIED`: metadata is not a resolved-config implementation. |
| [`setup.py`](../ros2_ws/src/mecanum_nav_rl/setup.py) | Installs package metadata only; `console_scripts` empty; config YAML is not listed in `data_files` | N/A | `PARTIAL_MATCH`: ament package scaffold, but config assets would not be installed by this metadata. |
| [`README.md`](../ros2_ws/src/mecanum_nav_rl/README.md) | Says package has only a scaffold and no environment/training | N/A | `STALE_OR_CONFLICTING`: core/config sources now exist, while no conclusion about runtime readiness follows. |

## 4. Requirement traceability summary

| # | Architecture requirement | Static evidence | Status |
| --- | --- | --- | --- |
| 1 | Schema `3.0` | All current YAML/model literals are `1.0` | `MISSING` |
| 2 | Complete frozen v3 `ResolvedConfig` | Frozen/forbid v1 subset only | `PARTIAL_MATCH` |
| 3 | Four `RuntimeProfile` names | Enum has all four exact names | `MATCHES_ARCH` |
| 4 | `NavigationMode` enum | No source enum/model | `MISSING` |
| 5 | Valid profile–mode matrix | Compiler checks profile only | `MISSING` |
| 6 | Four profile overlays | Only `sim_train.yaml` exists | `PARTIAL_MATCH` |
| 7 | Five-stage merge order | Only base/profile merge exists | `PARTIAL_MATCH` |
| 8 | Canonical resolved hash and provenance | Canonical SHA utility exists, but v1 model and no required field/provenance | `PARTIAL_MATCH` |
| 9 | Target-specific token classes | Comments distinguish simulation baseline; no typed token/policy | `MISSING` |
| 10 | Topic/QoS contracts | No config model/YAML | `MISSING` |
| 11 | Profile TF/frame contract | Frame fields/profile checks exist; no edge/authority contract | `PARTIAL_MATCH` |
| 12 | Estimation/localization/navigation configs | Absent | `MISSING` |
| 13 | Fixed 81-D observation | YAML, model, and AgentSpec agree | `MATCHES_ARCH` |
| 14 | Fixed 3D holonomic action | YAML, model, and AgentSpec agree | `MATCHES_ARCH` |
| 15 | Limit target policy / deploy-real lock | Positive limits and comments only; no `TBD_MEASURED` policy | `PARTIAL_MATCH` |
| 16 | Canonical map identity | No map config/validator | `MISSING` |
| 17 | Envelope/safety config | No corresponding resolved-config field | `MISSING` |
| 18 | Fail-closed semantic validators | YAML loader rejects malformed input; architecture validation suite absent | `PARTIAL_MATCH` |
| 19 | GT isolation configuration | Approved ACR S1 establishes policy; v1 config does not express it | `PARTIAL_MATCH` |
| 20 | D10 goal/settle config | No navigation/termination configuration | `MISSING` |

**Counts:** `MATCHES_ARCH = 3`; `PARTIAL_MATCH = 7`; `MISSING = 10`.

## 5. Conflicts and gaps

### 5.1 `IMPLEMENTATION_GAP`

- v3 typed models: `NavigationMode`, full `ResolvedConfig`, project metadata, topic/QoS, estimation, localization, navigation, reward/training/evaluation/safety/acceptance fields.
- Complete profile overlays and explicit D03 matrix validation.
- Token-class validation for `FIXED_ARCH`, `SIM_BASELINE`, `TBD_MEASURED`, `TBD_PROJECT_ACCEPTANCE`, and `REQUIRED_BUILD_INPUT`.
- Architecture-specific validators from table 25, including profile/mode, map identity, topic/QoS, TF, command, and model compatibility.
- Config sources for topics, QoS, frames, acceptance, measurements, PPO, and map identity; profile-specific `sim_eval`, `deploy_sim`, and locked `deploy_real` inputs.
- Package-install treatment for configuration assets and a public compiler/config boundary.

### 5.2 `MIGRATION_GAP`

- `schema_version: "1.0"`, `ResolvedConfig.schema_version: Literal["1.0"]`, and `CONFIG_HASH_VERSION = "v1"` are not the architecture schema 3.0 contract.
- Existing compiler semantics (`base < profile`) are a proper deep-merge primitive but are not the architecture merge chain.
- Profile name enum exists without `NavigationMode`; exposing the four profile names alone can falsely imply the four complete profile contracts exist.
- `sim_train.yaml` uses a `world_frame` because the v1 model comments describe policy use of world GT. Architecture D13/ACR S1 instead requires policy-safe internal noisy emulator output; this requires an explicit v3 GT-isolation contract, not a silent continuation of the v1 semantic.
- README’s “only scaffold” statement is stale relative to current core/config source, while the package remains far short of the architecture’s runtime configuration surface.

### 5.3 `REQUIRES_USER_DECISION`

These are not generic missing-code decisions; the architecture or approved record leaves their values/owner intentionally open.

| Needed decision | Why code must not choose it |
| --- | --- |
| S2 synchronization capacities, receive-age budgets, overflow recovery, and lifecycle ingress provenance | ACR S2 marks them `REQUIRED_MEASUREMENT`/pending approval; it forbids deriving values from observed defaults. |
| Final command receipt owner/boundary and normalized conversion provenance | S3 D2 remains `DRAFT — PENDING_USER_DECISION`; no component may claim final-issued command evidence beforehand. |
| Episode-limit mode/value and checkpoint provenance | S3 D6 retains `REQUIRED_USER_DECISION`; profile YAML cannot provide invented limits. |
| Build inputs for collision contract and measured-real registry values | Architecture marks them `REQUIRED_BUILD_INPUT`/`TBD_MEASURED`; values must come from the designated evidence source, not from default YAML. |

## 6. Proposed core-only implementation sequence

The sequence is planning only. It neither creates runtime authority nor permits ROS, Gazebo, Gym/PPO training, D3 capture, or hardware work.

| Increment | Objective and likely files | Invariant/test | Exclusions and dependencies |
| --- | --- | --- | --- |
| **A0.2 — v3 typed schema** | `mecanum_nav_rl/config/models.py`, `agent_spec.py`, package-local tests | Frozen/forbid v3 model; D03 enum/matrix; D05 stays exact 81/3; unresolved token represented, never defaulted | No YAML migration/runtime. Keep S2/D2/D6 unresolved values typed but unselected. |
| **A0.3 — compiler and validators** | `compiler.py`, `loader.py`, `hashing.py`, new `validators.py`, tests | Exact five-stage merge, canonical post-resolution SHA, profile/mode/token fail-closed cases | No ROS/Gazebo reads or runtime YAML reads. Depends on A0.2 types. |
| **A0.4 — overlay and build-input boundary** | config data assets and package install metadata, focused tests | Four profile overlays; absent/invalid build inputs and `deploy_real` TBD values reject deterministically; package asset path is explicit | No measured values, no map/collision generation, no safety publisher. Depends on A0.3. |
| **A0.5 — migration reconciliation tests** | config/core tests and README/contract reconciliation only as needed | v1 inputs rejected or explicitly migration-scoped; D13 isolation and D10 configuration interfaces do not regress; config hash provenance tested | No runtime integration, PPO training, Gym environment, D3 work, or hardware. Depends on A0.2–A0.4 and approved decisions only where their concrete fields are required. |

## 7. Decision conclusion

**Can A0.2 start now?** Yes, for the core-only typed schema/model contract. The architecture already locks the schema shape, profile/mode names and matrix, observation/action contracts, and fail-closed policy. A0.2 must represent unresolved inputs without assigning their values.

**What prevents a later compiler/profile completion?** The four decisions in §5.3: S2 temporal parameters, D2 receipt boundary, D6 episode-limit policy, and authoritative measured/build inputs. They do **not** block creation of the v3 types or structural validation; they block selecting their operational values and accepting target configs that require them.

**Does A0.2 need runtime approval?** No. It is pure core/config schema work and must not construct runtime nodes, launch files, processes, guards, or hardware paths.

**Prior audit material requiring stale marking after reconciliation:**

- [`README.md`](../ros2_ws/src/mecanum_nav_rl/README.md) status text is stale because it calls the package only a scaffold despite existing core/config modules.
- Any source/report treating v1 `ResolvedConfig` or the single `sim_train.yaml` as the current architecture-complete configuration is stale/conflicting.
- ACR S1’s “no emulator implementation exists” migration-status sentence should be treated as older implementation evidence, not as an override of the current source inventory; it remains authoritative for GT isolation policy.
- ACR S2, S3 D2, and S3 D6 remain drafts/pending decisions; their proposed values must not be reported as resolved-config defaults.

## 8. Non-actions and validation

- Read-only inspection and DOCX extraction were used for authority/source reconciliation.
- No Python/package execution, build, test, lint, ROS, Gazebo, `gz`, launch, plugin, collector, guard, or hardware action occurred.
- No source Python, YAML, package metadata, architecture/project-tree authority, ACR, artifact, generated output, runtime packet, or guard was modified.
- The sole change in this increment is this Markdown reconciliation document. Markdown structure and scoped whitespace/diff checks are the only validation actions permitted after writing it.
