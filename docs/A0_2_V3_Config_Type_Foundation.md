# A0.2 V3 Configuration Type Foundation

**Status:** `IMPLEMENTED_CORE_ONLY — RUNTIME NOT APPROVED`

A0.2 adds architecture-target v3 types in
[`v3_models.py`](../ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/config/v3_models.py)
and pure D03/token policy in
[`v3_policy.py`](../ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/config/v3_policy.py).
They are parallel to unchanged legacy v1 YAML, models, loader, compiler,
hashing, and AgentSpec.

| Architecture requirement | A0.2 type/policy | Offline test evidence |
| --- | --- | --- |
| D03 profile/mode matrix | `RuntimeProfileV3`, `NavigationModeV3`, `validate_profile_mode_v3` | Every allowed pair and an invalid pair |
| §4 immutable v3 surface | Strict frozen nested `ResolvedConfigV3` | Extra, mutation, missing section, identity/hash, and numeric invalidity |
| Token policy | `ConfigTokenV3`, `TokenizedConfigInputV3`, `validate_tokenized_input_v3` | Target/stage failures without token resolution |
| D05 observation/action | `ObservationContractV3`, `ActionContractV3` | Exact 81-D and three-axis literals |

Unresolved and deliberately unselected: S2 timing/buffer/lifecycle values, D2
final-issued receipt ownership, D6 episode limits, D10 numeric settle thresholds,
real motion limits, map hashes, collision build inputs, and measured hardware
registry values. `TokenizedConfigInputV3` represents such inputs only before
resolution; `ResolvedConfigV3` cannot accept tokenized sections.

### A0.2.1 D03 invariant hardening

`RuntimeSelectionV3` now enforces the D03 profile/mode matrix during public
Pydantic construction; `ResolvedConfigV3` therefore cannot exist with an
invalid pair. The standalone policy validator is re-exported from the same
model-owned source-of-truth rather than carrying a copied matrix. This remains
`IMPLEMENTED_CORE_ONLY — RUNTIME NOT APPROVED`; it creates no compiler migration,
runtime integration, or runtime approval.

A0.3, and not A0.2/A0.2.1, may rewire compiler, loader, validator, and hash behavior.
No ROS, Gazebo, Nav2, Gymnasium, Stable-Baselines3, runtime I/O, process, guard,
or hardware behavior is introduced here.
