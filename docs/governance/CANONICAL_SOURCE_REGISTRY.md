# Canonical Source Registry — Mecanum Nav2 DRL

## Registry role

This registry identifies operational source selection. It does not override MECANUM_NAV_DRL_Architecture.docx, approved ACRs or explicit user decisions.

## Registry entries

| Source/path | Classification | Permitted use |
|---|---|---|
| docs/MECANUM_NAV_DRL_Architecture.docx | ARCHITECTURE_AUTHORITY | Highest architecture authority |
| AGENTS.md | EXECUTION_GOVERNANCE | Codex work rules; not architecture authority |
| docs/MECANUM_NAV_DRL_Project_Tree.txt | PROJECT_STRUCTURE_AUTHORITY | Expected project layout; not architecture override |
| ros2_ws/src/mecanum_nav_rl/config/v3/** | APPROVED_FOR_CORE | Only permitted config-input family for new canonical/offline implementation; effective composition remains caller-owned and contract-bound |
| ros2_ws/src/mecanum_nav_rl/config/base.yaml and config/profiles/** outside V3 | PRE_V3_NONCANONICAL | Historical/reference only unless explicit decision changes status |
| ros2_ws/src/mecanum_nav_rl/** pure core | IMPLEMENTED_CORE_PENDING_P0_REMEDIATION | Reuse only through approved work packages |
| ros2_ws/src/mecanum_nav_rl_interfaces/msg/** | CANONICAL_INTERFACE_CONTRACT | Typed interface source; changes require contract review |
| ros2_ws/src/mecanum_base_bridge/** | CODEC_CORE_ONLY | Codec/diagnostic evidence only; not serial/ROS/odometry runtime |
| firmware_STM32/** | FIRMWARE_SOURCE_PENDING_OFFLINE_AND_HIL_EVIDENCE | Firmware implementation work only under contract/hardware approval |
| ros2_ws/src/ROBOT_URDF_final_description/urdf/**, meshes/**, models/** | ROBOT_GEOMETRY_SIMULATION_SOURCE | Geometry/simulation source; not proof of official runtime control profile |
| ros2_ws/src/ROBOT_URDF_final_description/ROBOT_URDF_final_description/mecanum_env.py | LEGACY_NONCANONICAL | Excluded from official runtime/architecture evidence |
| ros2_ws/src/ROBOT_URDF_final_description/ROBOT_URDF_final_description/train_ai.py | UNCLASSIFIED_LEGACY_DEPENDENT | Not allowed as canonical training/runtime entrypoint pending explicit decision |
| artifacts/maps/<map_id> | REQUIRED_CANONICAL_MAP_LOCATION_MISSING | Must become map source of truth; do not use ROS-package map copies as canonical |
| artifacts/hardware/<hardware_profile_id>/hardware_manifest.yaml | CANONICAL_LOCATION_PRESENT_VALIDITY_PENDING | Hardware source location exists; values/approval require separate evidence |
| artifacts/simulation/** historical reports/tools | HISTORICAL_OFFLINE_EVIDENCE | Audit/provenance only; never automatic runtime approval |
| docs/*DRAFT*, approval packet draft and legacy report | DRAFT_OR_HISTORICAL_EVIDENCE | Read for context; not implementation authority without approval |
| .venv/**, build/**, install/**, log/**, __pycache__/** | GENERATED_NONCANONICAL | Must not be introduced into future integration commits |

## Required source-selection rules

- A new work package must state which registry entries it reads and writes.
- If a source is DRAFT, HISTORICAL, LEGACY, NONCANONICAL, PENDING or MISSING, Codex must not treat it as runtime-ready or silently promote it.
- Missing canonical locations must be created only through an approved work package with provenance/hash rules; never by copying arbitrary legacy files.
- Changes to this registry require an explicit governance prompt and must include architecture/ACR impact analysis.

- New canonical/offline implementation that consumes configuration must use the V3 config family through an approved V3 composition/loader surface; it must not directly select the V1 loader, `config/base.yaml` or pre-V3 `config/profiles/**`.
- `APPROVED_FOR_CORE` for the V3 config family is not approval of any runtime profile, PPO training, Gazebo execution, HIL, deploy_sim or deploy_real.
- This decision does not resolve caller-owned composition, token/provenance, NavigationContractV3, localization/state contract, map provenance or hardware approval; those remain blocked until their own approved contracts.
- Existing legacy code may remain for historical/reference purposes but must not become a canonical entrypoint by import, wrapper or indirect delegation.
