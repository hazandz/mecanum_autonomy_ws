"""Pure structural validator for the non-executable sim_eval profile inputs."""

from collections.abc import Mapping


STATIC_PROFILE_DESCRIPTOR = {
    "schema": "mecanum_sim_eval_nav2_baseline_static_profile/v1",
    "classification": "STATIC_PROFILE_INPUT_CLOSURE_ONLY",
    "runtime_eligible": False,
    "source_commit": "4f491edca1d46dee259d57350ad520a0334e4049",
    "profile": {
        "runtime_profile": "sim_eval",
        "navigation_mode": "NAV2_BASELINE",
        "use_sim_time": True,
    },
    "map_artifact": {
        "map_id": "warehouse_map2",
        "artifact_identity": "4a8a23d0-7e27-4a50-8201-dd1abf1a3db4",
        "map_content_hash": "2bd9ff0a40eaeb61c2359aab4bb213da623ab56746debe591edd4a54c2229f90",
        "canonical_manifest_sha256": "7e0a380b0d8df32f9a4fc30dd0dbbe9ed08aafdcd5efb3764bccd844b98c1cb1",
        "map_yaml_repository_path": "artifacts/maps/warehouse_map2/map.yaml",
        "approval_scope": "SIM_EVAL_NAV2_BASELINE_STATIC_MAP_ARTIFACT_SELECTION",
        "approval_status": "approved",
        "world_frame_state": "DECLARED_UNVERIFIED",
        "runtime_compatibility_state": "NOT_VALIDATED",
    },
    "static_configuration_sources": [
        {"role": "nav2_baseline", "path": "ros2_ws/src/mecanum_nav_bringup/config/navigation/nav2_baseline.yaml", "sha256": "1dabf8855ce39f74514620b1934f54c23aacc513257c8d5485f705d1aac69f91"},
        {"role": "amcl_omni", "path": "ros2_ws/src/mecanum_nav_bringup/config/localization/amcl_omni.yaml", "sha256": "c6e58320aa1b35f4c74ca7442bf00357266ad51428522ca93d4565c1d6617e60"},
        {"role": "robot_localization_ekf", "path": "ros2_ws/src/mecanum_nav_bringup/config/state_estimation/ekf_sim.yaml", "sha256": "6053950facb8eaf99243363158d7fd75e146215ab1241f383225e2c8518c0d71"},
        {"role": "lifecycle_startup", "path": "ros2_ws/src/mecanum_nav_bringup/config/lifecycle/navigation_v1_startup.yaml", "sha256": "d9de3a9841c3f4f8823020fdf76b7e5dae6761e87f7f7dde11a8b80af1aa475a"},
        {"role": "remap_namespace", "path": "ros2_ws/src/mecanum_nav_bringup/config/remaps/navigation_v1.yaml", "sha256": "1cd358d552e04ad75f63583ee019f9b680a471f14cf6d436e542b34714e4fdbc"},
    ],
    "static_ingress_contracts": [
        {"role": "wheel_imu_ingress", "path": "ros2_ws/src/mecanum_base_bridge/config/sim_eval_wheel_imu_ingress.static.yaml", "sha256": "ab062b85f38a6a688c3a97691ee7e120791f8e0f2feb13d340b9fb245d5aaf22", "classification": "STATIC_INGRESS_CONTRACT_ONLY"},
        {"role": "wheel_imu_ingress_validator", "path": "ros2_ws/src/mecanum_base_bridge/mecanum_base_bridge/sim_eval_wheel_imu_ingress_contract.py", "sha256": "964216d0e031927458d875c914d87a0a49797da9ce238596024bf0d0dce2f18a", "classification": "STATIC_INGRESS_CONTRACT_ONLY"},
        {"role": "lidar_bridge_contract", "path": "ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_lidar_scan_bridge.static.yaml", "sha256": "60a012fd2fd8f743658cdfb4fc3e910d728b17b2bea5d7dece3316bd4f12ff7e", "classification": "STATIC_BRIDGE_BOUNDARY_ONLY"},
        {"role": "lidar_bridge_validator", "path": "ros2_ws/src/mecanum_nav_bringup/mecanum_nav_bringup/sim_eval_lidar_scan_bridge_contract.py", "sha256": "984ee08b9338ae407c779efe5a69c1f55862cf6e739b9a9e6454da5054c0f5ed", "classification": "STATIC_BRIDGE_BOUNDARY_ONLY"},
        {"role": "typed_lidar_binding", "path": "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/v3_sim_eval_lidar_bridge_binding.py", "sha256": "b4d2f12ac85e0a103c37ea914481c6ef278587a3960f931448455239b094ba2a", "classification": "STATIC_TYPED_BINDING_ONLY"},
        {"role": "robot_description", "path": "ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro", "sha256": "d80f46f3b5f273257072d800b9ba0b34c763128bfeefc32959363babf106cc0d", "classification": "STATIC_TF_PROVENANCE_ONLY"},
        {"role": "robot_state_publisher_launch", "path": "ros2_ws/src/ROBOT_URDF_final_description/launch/navigation_v1_robot_state_publisher.launch.py", "sha256": "b5c939ed662b5f789d008dd34777363ffeb5bbc373b596e97b75c1e097dcb511", "classification": "STATIC_TF_PROVENANCE_ONLY"},
        {"role": "gazebo_lidar_source", "path": "ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo", "sha256": "7bbaa475578600d8e18e437fa83720483b90b4af2bf4212151257152429576a2", "classification": "GAZEBO_TRANSPORT_PROVENANCE_ONLY"},
    ],
    "external_dependency_lock": {
        "path": "docs/governance/evidence/WP-05_NAVIGATION_V1_EXTERNAL_14_ROOT_DEPENDENCY_LOCK.json",
        "sha256": "a603933a9e14668f35b88b77221270b5dc5a597d9b9bfba2447c8e297d44587e",
    },
    "static_policy_source_manifest": {
        "path": "docs/governance/evidence/WP-05_NAVIGATION_V1_STATIC_POLICY_SOURCE_PIN_MANIFEST.json",
        "sha256": "217e7431033ca428e454c4cac3b41b955522f2c5ee420448317d2c5acb5a69a5",
    },
    "deferred_runtime_requirements": [
        "ROS_GAZEBO_SCAN_BRIDGE_IMPLEMENTATION_AND_ENDPOINT",
        "OBSERVED_SCAN_TIMING_AND_QOS",
        "UNIQUE_LIVE_TF_PUBLISHER_EVIDENCE",
        "LIFECYCLE_HEALTH_EVIDENCE",
        "WORLD_FRAME_VALIDATION_AND_RUNTIME_COMPATIBILITY",
        "WP06_SAFETY_AND_FINAL_COMMAND_PATH",
        "GLOBAL_RESOLVED_CONFIG_V3_INPUTS",
    ],
}

STATIC_PROFILE_EXCLUSIONS = [
    "RESOLVED_CONFIG_V3",
    "CONFIG_HASH",
    "WORKSPACE_SOURCE_LOCK",
    "RUNTIME_SOURCE_PIN",
    "RUNTIME_EVIDENCE",
    "RUNTIME_AUTHORIZATION",
    "MAP_SERVER_RUNTIME_LOAD",
    "LAUNCH_GRAPH_CREATION",
]


def _matches_exactly(actual, expected):
    if isinstance(expected, Mapping):
        if not isinstance(actual, Mapping) or set(actual.keys()) != set(expected.keys()):
            return False
        return all(_matches_exactly(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        if type(actual) is not list or len(actual) != len(expected):
            return False
        return all(_matches_exactly(item, wanted) for item, wanted in zip(actual, expected))
    if type(actual) is not type(expected):
        return False
    return actual == expected


def validate_sim_eval_nav2_baseline_static_profile_descriptor(descriptor):
    """Return True only for the exact static input descriptor; never resolve it."""
    try:
        return _matches_exactly(descriptor, STATIC_PROFILE_DESCRIPTOR)
    except Exception:
        return False
