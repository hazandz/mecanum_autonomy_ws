# A0.4 — V3 Config Assets and Package Boundary

Status: `IMPLEMENTED_CORE_ONLY — OFFLINE_VALIDATED_A0.4.1 — RUNTIME NOT APPROVED`

## Authority and scope

This parallel V3 input skeleton follows the frozen architecture authority
[MECANUM_NAV_DRL_Architecture.docx](MECANUM_NAV_DRL_Architecture.docx), whose
SHA-256 was verified as
`f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860`.
It also follows the reconciliation, type, compiler, and source-class records:

- [A0 Architecture Config Contract Reconciliation](A0_Architecture_Config_Contract_Reconciliation.md)
- [A0.2 V3 Config Type Foundation](A0_2_V3_Config_Type_Foundation.md)
- [A0.3 V3 Config Compiler and Validation](A0_3_V3_Config_Compiler_And_Validation.md)

The files below are tokenized V3 input skeleton assets only. They introduce no
runtime discovery, no profile auto-selection, no asset assembler, and no claim
that an asset containing a token is a `ResolvedConfigV3`. They are not a
resolved, runnable, or compiler-ready configuration.

## Asset tree

```text
config/v3/
├── base.yaml
├── profiles/{sim_train,sim_eval,deploy_sim,deploy_real}.yaml
├── modes/{local_training,mapping,nav2_baseline,hybrid_ai_local}.yaml
├── topics.yaml
├── qos.yaml
├── frames.yaml
├── acceptance.yaml
├── measurements.yaml
└── algorithms/ppo.yaml
```

V1 files remain at `config/base.yaml` and `config/profiles/sim_train.yaml` and
are not overwritten or used as a V3 runtime-discovery fallback.

## Fixed literals and unresolved boundary

The assets encode only architecture-fixed values: schema `3.0`; D03 profile and
mode names; D05 72 LiDAR sectors plus three local-reference, three measured
twist, and three previous-issued-command fields for an 81-dimensional
`float32` observation; normalized `[vx, vy, wz]` action bounds; EKF ownership
of `odom -> base_link`; `robot_state_publisher` ownership of
`base_link -> lidar_frame`; FinalTwistPublisher ownership of `/cmd_vel`; and
canonical map source root `artifacts/maps`.

Every unselected value uses the exact `TokenizedConfigInputV3` shape:

```yaml
field_path: exact.target.path
token: REQUIRED_BUILD_INPUT
reference_id: decision_or_authority_identifier
```

Only `FIXED_ARCH`, `SIM_BASELINE`, `TBD_MEASURED`,
`TBD_PROJECT_ACCEPTANCE`, and `REQUIRED_BUILD_INPUT` occur. The assets do not
substitute `TBD`, `TODO`, `null`, numeric fake limits, `default`, or `unknown`.
There is no measured registry, map artifact, acceptance threshold, S2 timing,
D2 receipt boundary, D6 limit, or D10 numeric threshold in this increment.

## Profile and mode boundary

| Runtime profile | `use_sim_time` | Permitted mode assets |
| --- | --- | --- |
| `sim_train` | `true` | `LOCAL_TRAINING` |
| `sim_eval` | `true` | `NAV2_BASELINE`, `HYBRID_AI_LOCAL` |
| `deploy_sim` | `true` | `MAPPING`, `NAV2_BASELINE`, `HYBRID_AI_LOCAL` |
| `deploy_real` | `false` | `MAPPING`, `NAV2_BASELINE`, `HYBRID_AI_LOCAL` |

`deploy_real.yaml` deliberately holds `TBD_MEASURED` and
`REQUIRED_BUILD_INPUT` token objects for its motion and build prerequisites. It
is not a deploy-ready configuration. Mode assets encode only locked ownership:
PPO local control for local training; teleop through safety for mapping; Nav2
baseline controller; and Nav2 planner plus LocalReference and PPO local control
for hybrid AI local mode.

## Install boundary

`setup.py` enumerates every V3 YAML asset deterministically. Installation
places them under:

```text
share/mecanum_nav_rl/config/v3/
```

including the `profiles/`, `modes/`, and `algorithms/` subdirectories. It does
not add a console script, runtime dependency, map/model/checkpoint/artifact, or
V1 YAML modification.

## Offline validation

`test_colcon_runner.py` explicitly registers the existing V3 schema, compiler,
and asset test modules in addition to every pre-existing non-V3 module.
`test_config_v3_assets.py` checks the complete tree, strict loader parsing,
token taxonomy, and compares each profile asset directly against the
model-owned D03 profile-to-mode mapping; it does not maintain a second D03
matrix literal. It also checks mode literals, deploy-real tokenization,
fail-closed compiler rejection of tokenized inputs, prohibited approval claims,
legacy V1 file presence, and byte-identical installed assets after the package
build. The existing compiler and schema tests continue to cover the core policy
and strict V3 model.

A0.4.1 offline validation passed on 2026-10-01 after V3 test inclusion:

- `python -m pytest src/mecanum_nav_rl/test/test_config_v3_schema.py -q`: 50 passed.
- `python -m pytest src/mecanum_nav_rl/test/test_config_v3_compiler.py -q`: 22 passed.
- `python -m pytest src/mecanum_nav_rl/test/test_config_v3_assets.py -q`: 8 passed.
- `python -m pytest src/mecanum_nav_rl/test -q`: 371 passed.
- `python -m colcon build --packages-select mecanum_nav_rl --symlink-install`: passed.
- `python -m colcon test --packages-select mecanum_nav_rl`: passed; its raw log
  records all three V3 modules and 370 registered pytest cases.
- `python -m colcon test-result --verbose`: 21 tests, 0 errors, 0 failures,
  0 skipped.

This is offline evidence only. This document makes no ROS, Gazebo, runtime, or
hardware readiness claim.

## Classification

- `SOURCE_IMPLEMENTATION`: A0.4/A0.4.1 tokenized V3 input skeleton, package
  install boundary, and V3 colcon-test inclusion.
- `OFFLINE_EVIDENCE`: standard pytest, package build, colcon test, and
  package-install parity passed on 2026-10-01; this remains offline evidence only.
- `RUNTIME_EVIDENCE`: none.
- `RUNTIME_NOT_APPROVED`: no asset authorizes runtime or hardware.

`A0.4 COMPLETE ONLY IF ALL OFFLINE VALIDATION PASSES`.

`A0.5 NOT STARTED`.
