# A0.3 — V3 Config Compiler and Validation

Status: `IMPLEMENTED_CORE_ONLY — OFFLINE_VALIDATED — RUNTIME NOT APPROVED`

## Authority and scope

This increment follows the frozen architecture in
[MECANUM_NAV_DRL_Architecture.docx](MECANUM_NAV_DRL_Architecture.docx), whose
SHA-256 was verified as
`f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860`, and the
reconciliation and V3 type-foundation records:

- [A0 Architecture Config Contract Reconciliation](A0_Architecture_Config_Contract_Reconciliation.md)
- [A0.2 V3 Config Type Foundation](A0_2_V3_Config_Type_Foundation.md)

A0.3 is a pure configuration-core increment. It creates no production V3 YAML,
runtime profile, map artifact, hardware registry, ROS node, Gazebo process, or
command path. Legacy V1 models, loader, compiler, hashing, agent specification,
and YAML inputs remain separate and unchanged.

## Public core APIs

| Module | API | Responsibility |
| --- | --- | --- |
| `v3_loader.py` | `load_v3_mapping`, `load_v3_yaml_mapping` | Copy an in-memory mapping or explicitly named UTF-8 YAML layer; reject malformed YAML, duplicate keys, and non-string keys. |
| `v3_compiler.py` | `compile_v3_config` | Deterministically merge architecture layers, validate policy and semantics, then create immutable `ResolvedConfigV3`. |
| `v3_compiler.py` | `ApprovalProvenanceV3`, `ApprovedExperimentOverrideV3`, `ApprovedMeasuredRegistryV3` | Require explicit IDs and lowercase SHA-256 approval/registry provenance for privileged layers. |
| `v3_hashing.py` | `canonical_v3_hash_payload`, `canonical_v3_config_json`, `config_v3_sha256` | Produce the V3-specific canonical identity before `provenance.config_hash` is injected. |
| `v3_validators.py` | `validate_resolved_config_v3` | Enforce static, representable architecture semantics only. |

None of these modules import ROS, Gazebo, Gymnasium, Stable-Baselines3,
subprocess, a runtime graph, environment variables, a map artifact, or network
state.

## Compile order and approval rule

`compile_v3_config` accepts distinct layers and always applies them in this
fixed precedence order:

```text
base
→ runtime-profile overlay
→ navigation-mode overlay
→ approved experiment override
→ approved measured-hardware registry
→ policy and semantic validation
→ immutable ResolvedConfigV3
→ canonical SHA-256 config_hash
```

Merge is recursive, deterministic, and copies all input. Replacing a mapping
with a scalar (or the reverse) is rejected rather than silently changing shape.
An experiment override must be an `ApprovedExperimentOverrideV3`; a registry
must be an `ApprovedMeasuredRegistryV3`. A Boolean or self-declared YAML field
cannot establish approval. `deploy_real` additionally requires the registry
wrapper and `motion_limits.source_class == MEASURED_REGISTRY`.

The compiler rejects an input `provenance.config_hash`. Only the compiler may
add that field after resolution, so callers cannot select the final identity.

## Policy, token, and semantic gates

The compiler calls both `validate_profile_mode_v3` and
`validate_tokenized_input_v3`. It rejects invalid D03 pairs, incorrect
`use_sim_time`, token use outside its permitted context, and every unresolved
`TokenizedConfigInputV3` before model construction. It never substitutes a
default for an unresolved token.

The static semantic validator enforces only data represented by V3:

- D03 profile/mode and time-source contract;
- D05 81-dimensional `float32` observation and normalized `[vx, vy, wz]`
  action contract;
- EKF ownership of `odom -> base_link` and `robot_state_publisher` ownership of
  `base_link -> lidar_frame`;
- one `map -> odom` authority matching the selected localization provider;
- FinalTwistPublisher as final `/cmd_vel` owner;
- map/provenance sections and the measured source requirement for `deploy_real`.

It deliberately does not claim live TF, topic/QoS behavior, Gazebo behavior,
map existence or approval, command receipts, or runtime readiness.

## Canonical hash definition

The pre-hash payload is exactly:

```json
{
  "config_hash_schema": "mecanum_nav_rl.resolved_config.v3",
  "resolved_config_without_config_hash": { "...": "fully resolved V3 data" }
}
```

It is UTF-8 JSON with sorted keys, compact separators, ASCII escaping, and
`allow_nan=false`; its digest is SHA-256. The payload excludes
`provenance.config_hash`, then that digest is inserted into the immutable final
model. Unknown fields, including a caller-supplied runtime timestamp, fail
strict model validation rather than being silently ignored.

## Offline validation coverage

`test_config_v3_compiler.py` covers five-layer precedence, nested merge
copying, D03/time enforcement, token policy calls, unresolved-token rejection,
privileged provenance, deploy-real registry requirements, canonical hash
stability/semantic change, self-referential hash rejection, loader errors, and
unknown runtime fields. `test_config_v3_schema.py` continues all A0.2/A0.2.1
tests and scans every V3 module for prohibited runtime imports.

## A0.3.1 source-class and compiler-evidence hardening

A0.3.1 closes the representation gap between an unresolved
`TokenizedConfigInputV3(token=SIM_BASELINE)` and the final resolved
`motion_limits.source_class`. The compiler now validates the final source class
before it computes the hash or constructs `ResolvedConfigV3`:

| Runtime profile | Allowed final `motion_limits.source_class` | Required provenance |
| --- | --- | --- |
| `sim_train` | `SIM_BASELINE` or `MEASURED_REGISTRY` | A measured source requires an `ApprovedMeasuredRegistryV3` wrapper. |
| `sim_eval` | `SIM_BASELINE` or `MEASURED_REGISTRY` | A measured source requires an `ApprovedMeasuredRegistryV3` wrapper. |
| `deploy_sim` | `MEASURED_REGISTRY` only | Required wrapper; its `motion_limits.source_id` and final source ID must equal its `registry_id`. |
| `deploy_real` | `MEASURED_REGISTRY` only | Required wrapper; its `motion_limits.source_id` and final source ID must equal its `registry_id`. |

The measured wrapper must itself contribute a `motion_limits` mapping declaring
`MEASURED_REGISTRY` and the same registry ID. This is synthetic test provenance
only; it does not create a hardware measurement or registry artifact. The
semantic validator additionally rejects `SIM_BASELINE` for either deployment
profile even when a resolved model is validated outside the compiler.

The compiler tests now call `compile_v3_config` directly for all target policy
failures: `TBD_MEASURED` in `deploy_real` and at Gate 4,
`TBD_PROJECT_ACCEPTANCE` in final evaluation, and `REQUIRED_BUILD_INPUT` at
both build and deploy output. They also cover malformed YAML, exact final hash
assignment, TF/localization authority mismatch, an empty topic/QoS contract,
and a specific Pydantic error for an unknown runtime timestamp. No hash
algorithm or hash-payload schema changed.


## Classification

- `SOURCE_IMPLEMENTATION`: V3 loader, compiler, hash, and static semantic
  validator core.
- `OFFLINE_EVIDENCE`: Python test/build evidence is recorded only after the
  required commands complete successfully.
- `RUNTIME_EVIDENCE`: none.
- `RUNTIME_NOT_APPROVED`: A0.3 grants no runtime authorization.

`A0.3 COMPLETE ONLY IF ALL OFFLINE VALIDATION PASSES`.

`A0.4 NOT STARTED`.
