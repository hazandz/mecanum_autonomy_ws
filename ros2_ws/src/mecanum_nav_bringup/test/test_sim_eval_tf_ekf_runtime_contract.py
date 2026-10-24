"""Offline tests for the clock bridge and WP06-6F EKF contract."""

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

import yaml
import pytest

from mecanum_nav_bringup.sim_eval_tf_ekf_runtime_contract import (
    CLOCK_CONFIG_PATH,
    CLOCK_MAPPING,
    DECISION_PATH,
    EKF_CONFIG_PATH,
    EXPECTED_EKF_PARAMETERS,
    FORBIDDEN_BRIDGE_TOPICS,
    PARTITION,
    validate_clock_mapping,
    validate_ekf_config,
)


ROOT = Path(__file__).resolve().parents[4]
PACKAGE = ROOT / "ros2_ws/src/mecanum_nav_bringup"
CLOCK_PATH = PACKAGE / "config/bridge/sim_eval_clock.runtime.yaml"
EKF_PATH = PACKAGE / "config/state_estimation/ekf_sim.yaml"
LAUNCH_PATH = PACKAGE / "launch/sim_eval_tf_ekf_state_estimation.launch.py"
CONTRACT_PATH = PACKAGE / "mecanum_nav_bringup/sim_eval_tf_ekf_runtime_contract.py"
SETUP_PATH = PACKAGE / "setup.py"
PACKAGE_XML = PACKAGE / "package.xml"
MANIFEST_PATH = ROOT / "docs/governance/evidence/WP-06_6F_TF_EKF_RUNTIME_INGRESS_RUN_007_GUARD_MANIFEST.json"
GUARD_PATH = ROOT / "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/approval_guards/WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_007.json"
PROFILE_PATH = PACKAGE / "config/profiles/sim_eval_nav2_baseline.static.yaml"
NAV2_RUNTIME_CONFIG_PATH = PACKAGE / "config/navigation/sim_eval_nav2_baseline.runtime.yaml"
PROFILE_CONTRACT_PATH = PACKAGE / "mecanum_nav_bringup/sim_eval_static_profile_contract.py"
WP05_MANIFEST_PATH = ROOT / "docs/governance/evidence/WP-05_SIM_EVAL_NAV2_BASELINE_STATIC_PROFILE_MANIFEST.json"
BASE = "8b73bcb0b026fe337c023f6a30205dbe89d31eb5"
PARENT = "d44ba711395a50d3ba8b9f91e6f64d1eca8ca5a1"
CORRECTIVE_BASE = "6fbddb3db1a38908ed470f549a1c8182e022a37f"
STEP07_CAMPAIGN_BASE = "f7f98c683d59cf4c62e462da9f37d4ffb2455c80"
ACCEPTANCE_MATRIX_BASE = "5fa2e89f84d683723eba8eb989cfef59059ae603"
RUN002_BASE = "5a44cd9910e9b6d6058d8d2d9252a86f7cf9dcd8"
RUN002_COMMIT = "6d730bd54d7f99429ee4832a3f6f96beffae020f"
RUN003_COMMIT = "fdc0e299515bda2286832aabec635948629517b5"
RUN004_BASE = RUN003_COMMIT
RUN004_CORRECTIVE_BASE = "cbf59ff938d8b96ec650859d9367bc6cb840f0c6"
RUN004_HOST_CORRECTIVE_COMMIT = "b7105ccb651da6d0dcb916d7544481f7beacaae1"
RUN005_ATTEMPT_001_BASE = RUN004_HOST_CORRECTIVE_COMMIT
RUN005_ATTEMPT_001_COMMIT = "71ca32471f8e042a0048d319ca39cb9deff0c6f4"
RUN005_BASE = RUN005_ATTEMPT_001_COMMIT
RUN005_ATTEMPT_002_CORRECTIVE_BASE = "87af41f45d721969f2767d36291252e3b14e3dcb"
RUN005_ATTEMPT_002_PREVIOUS_CORRECTIVE_COMMIT = "c408ccd2a2f7b11787f725a24e818ffa038e3d36"
RUN005_ATTEMPT_002_OUTPUT_PRECONDITION_COMMIT = "da82b2e5d65eedd80f42000283dccc42a5f6ed66"
RUN005_ATTEMPT_002_HOST_TRANSPORT_BASE = "99d5c29c1c302260a8971e19e46f93d778a52f86"
RUN005_ATTEMPT_002_TERMINAL_ROS_DISCOVERY_BASE = "87ee34b1a945ecc12b525fe9f4711a368c0bdbc3"
RUN005_ATTEMPT_002_SIGTERM_HANDOFF_BASE = "bee34dd2d689fe585ae12000058b2f2903196659"
RUN005_ATTEMPT_002_TERMINAL_ROS_DISCOVERY_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
RUN005_ATTEMPT_002_TERMINAL_ROS_DISCOVERY_PHASE_A_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
}
RUN005_OWNERSHIP_BASE = "53b7790c23c7d4969612259a8ee06be0353babd2"
RUN005_OWNERSHIP_PATHS = RUN005_ATTEMPT_002_TERMINAL_ROS_DISCOVERY_PATHS | {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_run005_runtime_guard.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_runtime_guard.py",
}
RUN005_OWNERSHIP_PHASE_A_PATHS = RUN005_ATTEMPT_002_TERMINAL_ROS_DISCOVERY_PHASE_A_PATHS | {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_run005_runtime_guard.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_runtime_guard.py",
}
STEP07_CAMPAIGN_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_001.json",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_runtime_guard.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run001.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_runtime_guard.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run001.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/CMakeLists.txt",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/package.xml",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/test/test_step07_nav2_baseline_runtime_observer.cpp",
    "ros2_ws/src/mecanum_nav_rl/setup.py",
    "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py",
    "ros2_ws/src/mecanum_nav_rl/test/test_step07_gate_b_observer_node.py",
    "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_nav2_baseline_system.launch.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_nav2_baseline_system_launch.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN001_L2_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN001_L2_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN001_GUARD_MANIFEST.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
CORRECTIVE_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_001.json",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/test/test_step07_nav2_baseline_runtime_observer.cpp",
    "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py",
    "ros2_ws/src/mecanum_nav_rl/test/test_step07_gate_b_observer_node.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN001_L2_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN001_L2_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN001_GUARD_MANIFEST.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
CURRENT_CORRECTIVE_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_001.json",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN001_L2_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN001_L2_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN001_GUARD_MANIFEST.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
RUN002_CORRECTIVE_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_002.json",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_run002_runtime_guard.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run002.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run002_runtime_guard.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run002.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_runtime_guard.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN002_L2_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN002_L2_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN002_GUARD_MANIFEST.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
RUN003_CORRECTIVE_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_003.json",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_run003_runtime_guard.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run003.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run003_runtime_guard.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run003.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_runtime_guard.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run002_runtime_guard.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN003_L2_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN003_GUARD_MANIFEST.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN003_L2_EVIDENCE.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}


class UniqueLoader(yaml.SafeLoader):
    pass


def _unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def _no_duplicate_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json(path):
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert not raw.endswith(b"\n")
    def reject_constant(value):
        raise ValueError(f"JSON_NONFINITE_FORBIDDEN:{value}")
    parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate_json,
                        parse_constant=reject_constant)
    assert raw == json.dumps(parsed, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
    return parsed


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_clock_mapping_is_exact_and_rejects_banned_or_extra_mappings():
    raw = CLOCK_PATH.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    document = yaml.load(raw.decode("utf-8"), Loader=UniqueLoader)
    assert document == [CLOCK_MAPPING]
    assert validate_clock_mapping(document)
    for forbidden in FORBIDDEN_BRIDGE_TOPICS:
        assert forbidden not in {item["ros_topic_name"] for item in document}
        assert forbidden not in {item["gz_topic_name"] for item in document}
    assert not validate_clock_mapping(document + [copy.deepcopy(CLOCK_MAPPING)])
    changed = copy.deepcopy(document)
    changed[0]["direction"] = "BIDIRECTIONAL"
    assert not validate_clock_mapping(changed)
    changed = copy.deepcopy(document)
    changed[0]["gz_topic_name"] = "/odom"
    assert not validate_clock_mapping(changed)
    changed = copy.deepcopy(document)
    changed[0]["ros_type_name"] = "rosgraph_msgs/msg/String"
    assert not validate_clock_mapping(changed)


def test_ekf_contract_has_only_approved_inputs_and_fusion():
    raw = EKF_PATH.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    document = yaml.load(raw.decode("utf-8"), Loader=UniqueLoader)
    assert validate_ekf_config(document)
    params = document["ekf_filter_node"]["ros__parameters"]
    assert params["odom0"] == "/wheel/odometry_raw"
    assert params["imu0"] == "/imu/data"
    assert params["use_sim_time"] is True
    assert params["publish_tf"] is True
    assert params["world_frame"] == params["odom_frame"] == "odom"
    assert params["base_link_frame"] == "base_link"
    assert params["use_control"] is False
    assert params["reset_on_time_jump"] is True
    assert sum(params["odom0_config"]) == 2
    assert params["odom0_config"][6:8] == [True, True]
    assert sum(params["imu0_config"]) == 2
    assert params["imu0_config"][5] is True and params["imu0_config"][11] is True
    mutated = copy.deepcopy(document)
    mutated["ekf_filter_node"]["ros__parameters"]["use_control"] = True
    assert not validate_ekf_config(mutated)
    mutated = copy.deepcopy(document)
    mutated["ekf_filter_node"]["ros__parameters"]["odom0"] = "/odom"
    assert not validate_ekf_config(mutated)


def test_nav2_costmap_dimensions_use_integer_parameter_types():
    raw = NAV2_RUNTIME_CONFIG_PATH.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    document = yaml.load(raw.decode("utf-8"), Loader=UniqueLoader)
    for costmap_name in ("global_costmap", "local_costmap"):
        node = document.get(costmap_name, {})
        nested = node.get(costmap_name, {}) if isinstance(node, dict) else {}
        parameters = nested.get("ros__parameters", {}) if isinstance(nested, dict) else {}
        for dimension in ("height", "width"):
            if dimension in parameters:
                assert type(parameters[dimension]) is int, (
                    f"{costmap_name}.{dimension} must be a YAML integer, "
                    f"got {parameters[dimension]!r} ({type(parameters[dimension]).__name__})"
                )
def test_composite_launch_has_only_ingress_clock_and_ekf_actions():
    source = LAUNCH_PATH.read_text(encoding="utf-8")
    tree = __import__("ast").parse(source)
    calls = [node for node in __import__("ast").walk(tree) if isinstance(node, __import__("ast").Call)]
    node_calls = [node for node in calls if isinstance(node.func, __import__("ast").Name) and node.func.id == "Node"]
    include_calls = [node for node in calls if isinstance(node.func, __import__("ast").Name) and node.func.id == "IncludeLaunchDescription"]
    assert len(node_calls) == 2
    assert len(include_calls) == 1
    assert "mecanum_base_bridge" in source and "sim_eval_wheel_imu_ingress.launch.py" in source
    assert "ros_gz_bridge" in source and "robot_localization" in source
    assert 'SetEnvironmentVariable("GZ_PARTITION", partition)' in source
    assert '"gz_partition": partition' in source
    assert "wp06_scan_probe_run_002" not in source
    for forbidden in ("robot_state_publisher", "gazebo.launch.py", "nav2", "amcl", "slam", "map_server", "cmd_vel", "static_transform_publisher", "bootstrap.launch.py"):
        assert forbidden not in source.lower()
    assert "use_sim_time" in source and '"true"' in source
    assert "LaunchDescriptionSource" in source or "PythonLaunchDescriptionSource" in source


def test_tf_ownership_retains_bootstrap_rsp_and_xacro_static_edge():
    bootstrap_path = ROOT / "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_scan_probe_bootstrap.launch.py"
    xacro_path = ROOT / "ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro"
    bootstrap = bootstrap_path.read_text(encoding="utf-8")
    xacro = xacro_path.read_text(encoding="utf-8")
    composite = LAUNCH_PATH.read_text(encoding="utf-8")
    assert bootstrap.count('package="robot_state_publisher"') == 1
    assert '{"use_sim_time": True}' in bootstrap
    assert "robot_state_publisher" not in composite
    assert "sim_eval_scan_probe_bootstrap.launch.py" not in composite
    assert 'name="base_link_to_lidar_frame"' in xacro
    assert '<parent link="base_link"' in xacro
    assert '<child link="lidar_frame"' in xacro
    assert "xyz=\"-0.031765 0 0.140\"" in xacro
    assert "rpy=\"0 0 0\"" in xacro
    from mecanum_nav_bringup.sim_eval_tf_ekf_runtime_contract import expected_tf_contract
    contract = expected_tf_contract()
    assert contract["dynamic_edge"] == {"parent": "odom", "child": "base_link", "owner": "ekf_filter_node"}
    assert contract["static_edge"]["owner"] == "bootstrap_robot_state_publisher"
    assert contract["static_edge"]["translation"] == [-0.031765, 0.0, 0.140]
    assert contract["forbidden_edge"] == {"parent": "map", "child": "odom"}


def test_setup_installs_only_the_two_explicit_wp06f_artifacts():
    source = SETUP_PATH.read_text(encoding="utf-8")
    assert source.count('"config/bridge/sim_eval_clock.runtime.yaml"') == 1
    assert source.count('"launch/sim_eval_tf_ekf_state_estimation.launch.py"') == 1
    assert "gazebo.launch.py" not in source
    assert "glob(" not in source and "glob.glob" not in source
    package = ET.parse(PACKAGE_XML).getroot()
    deps = [node.text for node in package.findall("exec_depend")]
    assert deps.count("rosgraph_msgs") == 1
    baseline = ET.fromstring(subprocess.run(
        ["git", "show", f"{BASE}:ros2_ws/src/mecanum_nav_bringup/package.xml"],
        cwd=ROOT, check=True, capture_output=True,
    ).stdout)
    baseline_deps = [node.text for node in baseline.findall("exec_depend")]
    inserted_runtime_roots = [
        "mecanum_nav_rl", "mecanum_nav_rl_interfaces", "nav2_msgs", "lifecycle_msgs"
    ]
    baseline_profile_roots = {"ros_gz_bridge", "launch", "launch_ros"}
    common_roots = [item for item in baseline_deps if item not in baseline_profile_roots]
    expected = common_roots + [
        "ros_gz_bridge",
        "rosgraph_msgs",
        *inserted_runtime_roots,
        "launch",
        "launch_ros",
        "nav2_behaviors",
        "nav2_navfn_planner",
        "nav2_dwb_controller",
        "nav2_behavior_tree",
    ]
    assert deps == expected
    assert len(deps) == len(set(deps))
    assert deps.index("rosgraph_msgs") == deps.index("ros_gz_bridge") + 1


def test_run002_guard_and_manifest_remain_parent_byte_identical():
    run002_manifest = ROOT / "docs/governance/evidence/WP-06_6F_TF_EKF_RUNTIME_INGRESS_RUN_002_GUARD_MANIFEST.json"
    run002_guard = ROOT / "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/approval_guards/WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_002.json"
    manifest = _load_json(run002_manifest)
    guard = _load_json(run002_guard)
    assert manifest["run_id"] == guard["run_id"] == "WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_002"
    assert manifest["gz_partition"] == guard["gz_partition"] == PARTITION
    assert guard["state"] == "PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION"
    assert guard["capacity"] == 1
    assert guard["acquisition_count"] == 0
    assert guard["runtime_authorization"] == "NOT_GRANTED"
    assert guard["expected_review_commit"] is None
    for relative in (
        "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/approval_guards/WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_002.json",
        "docs/governance/evidence/WP-06_6F_TF_EKF_RUNTIME_INGRESS_RUN_002_GUARD_MANIFEST.json",
    ):
        original = subprocess.run(["git", "show", f"{PARENT}:{relative}"], cwd=ROOT, check=True, capture_output=True).stdout
        assert (ROOT / relative).read_bytes() == original


def test_run001_to_run007_repository_runtime_evidence_is_base_identical():
    inventory = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", PARENT],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    run_pattern = __import__("re").compile(
        r"(?:WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_00[1-7]|wp06_6f_tf_ekf_run00[1-7])"
    )
    protected = [path for path in inventory if run_pattern.search(path)]
    assert protected, "historical Run001–Run007 repository inventory must be discoverable"
    for relative in protected:
        original = subprocess.run(
            ["git", "show", f"{PARENT}:{relative}"],
            cwd=ROOT, check=True, capture_output=True,
        ).stdout
        current = ROOT / relative
        assert current.is_file() and current.read_bytes() == original, relative


def test_run007_seed_and_historical_disposition_are_immutable():
    manifest_path = MANIFEST_PATH
    guard_path = GUARD_PATH
    evidence_path = ROOT / "docs/governance/evidence/WP-06_SIM_EVAL_TF_EKF_RUNTIME_STATE_ESTIMATION_INGRESS_L2_EVIDENCE.json"
    manifest, guard, evidence = map(_load_json, (manifest_path, guard_path, evidence_path))
    run_id = "WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_007"
    assert manifest["run_id"] == guard["run_id"] == evidence["run_id"] == run_id
    assert guard["state"] == "PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION"
    assert guard["capacity"] == 1 and guard["acquisition_count"] == 0
    assert guard["runtime_authorization"] == "NOT_GRANTED"
    assert guard["guard_manifest_sha256"] == _sha(manifest_path)
    assert len(manifest["evidence_sha256"]) == 64
    assert all(char in "0123456789abcdef" for char in manifest["evidence_sha256"])
    assert manifest["guard_seed"] == {"path": guard["guard_path"], "state": guard["state"], "capacity": 1, "consumed": False}
    assert manifest["source_pins"] == evidence["source_pins"]
    for relative, expected in manifest["source_pins"].items():
        assert len(expected) == 64 and all(char in "0123456789abcdef" for char in expected)
    for relative in (str(manifest_path.relative_to(ROOT)), str(guard_path.relative_to(ROOT)), str(evidence_path.relative_to(ROOT))):
        original = subprocess.run(
            ["git", "show", f"{PARENT}:{relative}"], cwd=ROOT,
            check=True, capture_output=True,
        ).stdout
        assert (ROOT / relative).read_bytes() == original, relative
    assert manifest["runtime_eligible"] is False and evidence["runtime_eligible"] is False
    # The guard manifest is the pre-run seed record; the L1 evidence document
    # records the later independent audit disposition. Preserve and validate
    # each historical layer without conflating their different timestamps.
    assert manifest["runtime_evidence_status"] == "NOT_CREATED"
    assert evidence["runtime_evidence_status"] == "RAW_RUNTIME_EVIDENCE_AUDITED_PASS"


RUN004_CORRECTIVE_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_004.json",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_run004_runtime_guard.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run004.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run004_runtime_guard.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run004.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/prepare_step07_runtime_python_environment.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_prepare_step07_runtime_python_environment.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_runtime_python_requirements.txt",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_runtime_guard.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run003_runtime_guard.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN004_L1_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN004_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN004_GUARD_MANIFEST.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}

RUN004_PHASE_A_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/prepare_step07_runtime_python_environment.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_prepare_step07_runtime_python_environment.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run004.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
}

RUN004_FINAL_CORRECTIVE_PATHS = {
    *RUN004_PHASE_A_PATHS,
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_004.json",
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN004_L1_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN004_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN004_GUARD_MANIFEST.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}

RUN004_HOST_CORRECTIVE_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/prepare_step07_runtime_python_environment.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_prepare_step07_runtime_python_environment.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run004.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_004.json",
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN004_L1_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN004_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN004_GUARD_MANIFEST.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}

RUN005_ATTEMPT_001_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_run005_runtime_guard.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run004_runtime_guard.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}

RUN005_ATTEMPT_002_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
    "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_nav2_baseline_bootstrap.launch.py",
    "ros2_ws/src/ROBOT_URDF_final_description/test/test_sim_eval_nav2_baseline_bootstrap_launch.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}

RUN005_ATTEMPT_002_CORRECTIVE_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
    "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_tf_ekf_state_estimation.launch.py",
    "ros2_ws/src/mecanum_nav_bringup/package.xml",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_nav2_baseline_system_launch.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_dependency_lock_schema.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_state_estimation_launch.py",
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
RUN005_ATTEMPT_002_SOURCE_PHASE_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
    "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_tf_ekf_state_estimation.launch.py",
    "ros2_ws/src/mecanum_nav_bringup/package.xml",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_nav2_baseline_system_launch.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_dependency_lock_schema.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_state_estimation_launch.py",
}

RUN005_ATTEMPT_002_OUTPUT_PRECONDITION_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
RUN005_ATTEMPT_002_PARTITION_SOURCE_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
}
RUN005_ATTEMPT_002_HOST_TRANSPORT_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
RUN005_ATTEMPT_002_HOST_TRANSPORT_PHASE_A_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
}

RUN005_COMPOSITE_BASE = "bb5fc04fe8e309c52e468f766893ef60625e6821"
RUN005_COMPOSITE_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
    "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_nav2_baseline_system.launch.py",
    "ros2_ws/src/mecanum_nav_bringup/config/navigation/sim_eval_nav2_baseline.runtime.yaml",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_nav2_baseline_system_launch.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_nav2_baseline_static_contract.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/runtime_safety/safety_supervisor_node.py",
    "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/runtime_safety/final_twist_publisher_node.py",
    "ros2_ws/src/mecanum_nav_rl/config/safety/sim_eval_nav2_baseline_safety.yaml",
    "ros2_ws/src/mecanum_nav_rl/package.xml",
    "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py",
    "ros2_ws/src/mecanum_nav_rl/test/test_step07_gate_b_observer_node.py",
    "ros2_ws/src/mecanum_nav_rl/test/test_runtime_safety_contract.py",
    "ros2_ws/src/mecanum_nav_rl/test/test_final_twist_publisher_static.py",
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
RUN005_COMPOSITE_GOVERNANCE_PATHS = {
    path for path in RUN005_COMPOSITE_PATHS
    if path.startswith("docs/governance/") or "/approval_guards/" in path
}
RUN005_COMPOSITE_PHASE_A_PATHS = RUN005_COMPOSITE_PATHS - RUN005_COMPOSITE_GOVERNANCE_PATHS
RUN005_COMPOSITE_VALID_SCOPES = (
    RUN005_COMPOSITE_PHASE_A_PATHS,
    RUN005_COMPOSITE_PHASE_A_PATHS | {path for path in RUN005_COMPOSITE_GOVERNANCE_PATHS if "/approval_guards/" in path},
    RUN005_COMPOSITE_PATHS,
)

RUN005_INVOCATION_017_BASE = "31555b8ff2472811994907791f0d9b8d7f56498f"
RUN005_INVOCATION_017_PHASE_A_SOURCE_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/test/test_step07_nav2_baseline_runtime_observer.cpp",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
}
RUN005_INVOCATION_017_PHASE_A5_PATHS = RUN005_INVOCATION_017_PHASE_A_SOURCE_PATHS | {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
}
RUN005_INVOCATION_017_PHASE_B_RECONCILED_PATHS = RUN005_INVOCATION_017_PHASE_A5_PATHS | {
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
RUN005_INVOCATION_017_VALID_PHASE_SCOPES = (
    RUN005_INVOCATION_017_PHASE_A_SOURCE_PATHS,
    RUN005_INVOCATION_017_PHASE_A5_PATHS,
    RUN005_INVOCATION_017_PHASE_B_RECONCILED_PATHS,
)
RUN005_INVOCATION_017_AUTHORIZED_ALLOWLIST = (
    RUN005_INVOCATION_017_PHASE_B_RECONCILED_PATHS
    | {"artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
       "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py",
       "ros2_ws/src/mecanum_nav_rl/test/test_step07_gate_b_observer_node.py",
       "ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp"}
)

RUN005_VALIDATOR_CORRECTIVE_BASE = "c8e34ead42c9c3fa6d79bf73dc221a9cc599d42a"
RUN005_VALIDATOR_CORRECTIVE_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
RUN005_VALIDATOR_SOURCE_PATHS = RUN005_VALIDATOR_CORRECTIVE_PATHS - {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
RUN005_GZ_IP_GRACEFUL_BASE = "f72ac2112e0d1545a72b6a9a12764664d508aaa8"
RUN005_GZ_IP_GRACEFUL_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
RUN005_GZ_IP_GRACEFUL_PHASE_A_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
}

RUN005_DEFAULT_ROUTE_BASE = "e921b04e9ef8dc933a76966cf101613fab0f8062"
RUN005_DEFAULT_ROUTE_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
RUN005_DEFAULT_ROUTE_PHASE_A_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
}
RUN005_NAV2_HEIGHT_TEARDOWN_BASE = "a383f258b02a0f9a22b2dc72fb937dbcaba6973a"
RUN005_NAV2_HEIGHT_TEARDOWN_PHASE_A_PATHS = {
    "ros2_ws/src/mecanum_nav_bringup/config/navigation/sim_eval_nav2_baseline.runtime.yaml",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
}
RUN005_NAV2_HEIGHT_TEARDOWN_PATHS = RUN005_NAV2_HEIGHT_TEARDOWN_PHASE_A_PATHS | {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
RUN005_NAV2_HEIGHT_TEARDOWN_AUTHORIZED_ALLOWLIST = RUN005_NAV2_HEIGHT_TEARDOWN_PATHS | {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
}
RUN005_QOS_TRACE_BASE = "9fad09f333b93c8f63d9c4044af41d04d40be8c0"
RUN005_QOS_TRACE_PHASE_A_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/test/test_step07_nav2_baseline_runtime_observer.cpp",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py",
    "ros2_ws/src/mecanum_nav_rl/test/test_step07_gate_b_observer_node.py",
}
RUN005_QOS_TRACE_PHASE_A5_PATHS = RUN005_QOS_TRACE_PHASE_A_PATHS | {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
}
RUN005_QOS_TRACE_PATHS = {
    *RUN005_QOS_TRACE_PHASE_A5_PATHS,
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
RUN005_QOS_TRACE_AUTHORIZED_ALLOWLIST = RUN005_QOS_TRACE_PATHS | {
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
}

RUN005_COLLECTOR_VERDICT_BASE = "7f5d16ffa4edca34672b5af82397df9bde186829"
RUN005_COLLECTOR_VERDICT_PHASE_A_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/test/test_step07_nav2_baseline_runtime_observer.cpp",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py",
    "ros2_ws/src/mecanum_nav_rl/test/test_step07_gate_b_observer_node.py",
}
RUN005_COLLECTOR_VERDICT_PHASE_A5_PATHS = RUN005_COLLECTOR_VERDICT_PHASE_A_PATHS | {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
}
RUN005_COLLECTOR_VERDICT_RECONCILED_PATHS = RUN005_COLLECTOR_VERDICT_PHASE_A5_PATHS | {
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
RUN005_COLLECTOR_VERDICT_AUTHORIZED_PATHS = RUN005_COLLECTOR_VERDICT_RECONCILED_PATHS | {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
}

RUN005_LIFECYCLE_QOS_BASE = "09014a320cd8dedb242c99d70cd24ffa0d8cd980"
RUN005_LIFECYCLE_QOS_PHASE_A_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/test/test_step07_nav2_baseline_runtime_observer.cpp",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py",
    "ros2_ws/src/mecanum_nav_rl/test/test_step07_gate_b_observer_node.py",
}
RUN005_LIFECYCLE_QOS_PHASE_A5_PATHS = RUN005_LIFECYCLE_QOS_PHASE_A_PATHS | {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
}
RUN005_LIFECYCLE_QOS_RECONCILED_PATHS = RUN005_LIFECYCLE_QOS_PHASE_A5_PATHS | {
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
RUN005_LIFECYCLE_QOS_AUTHORIZED_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
    "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py",
    "ros2_ws/src/mecanum_nav_rl/test/test_step07_gate_b_observer_node.py",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/test/test_step07_nav2_baseline_runtime_observer.cpp",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}

RUN005_L1_REVIEW_BASE = "a04ec4d317830e01a4613fc5251f2152b9e9946e"
RUN005_L1_PHASE_A_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/test/test_step07_nav2_baseline_runtime_observer.cpp",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py",
    "ros2_ws/src/mecanum_nav_rl/test/test_step07_gate_b_observer_node.py",
}
RUN005_L1_AUTHORIZED_PATHS = RUN005_L1_PHASE_A_PATHS | {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
RUN005_L1_RECONCILED_PATHS = RUN005_L1_PHASE_A_PATHS | {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}

# Invocation_019 output-probe corrective lineage. Keep this separate from the
# earlier host-transport and Invocation_017 scope contracts.
RUN005_INVOCATION_019_BASE = "9a92b94b6f0d0d9a0f4ebdc8133ebecb34e6129f"
RUN005_INVOCATION_019_PHASE_A_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
}
RUN005_INVOCATION_019_PHASE_A5_PATHS = RUN005_INVOCATION_019_PHASE_A_PATHS | {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
}
RUN005_INVOCATION_019_PHASE_B_PATHS = RUN005_INVOCATION_019_PHASE_A5_PATHS | {
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
RUN005_INVOCATION_019_PHASE_SCOPES = {
    "PHASE_A": RUN005_INVOCATION_019_PHASE_A_PATHS,
    "PHASE_A5": RUN005_INVOCATION_019_PHASE_A5_PATHS,
    "PHASE_B": RUN005_INVOCATION_019_PHASE_B_PATHS,
}
RUN005_INVOCATION_019_GUARD = ROOT / (
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/"
    "STEP07_NAV2_BASELINE_RUN_005.json")

RUN005_AUDIT21_BASE = "21eab3580be48de9f00585cba904445dae7ce62f"
RUN005_AUDIT21_PHASE_A_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py",
    "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py",
    "ros2_ws/src/mecanum_nav_rl/test/test_step07_gate_b_observer_node.py",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/test/test_step07_nav2_baseline_runtime_observer.cpp",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
}
RUN005_AUDIT21_PHASE_A5_PATHS = RUN005_AUDIT21_PHASE_A_PATHS | (
    RUN005_INVOCATION_019_PHASE_A5_PATHS - RUN005_INVOCATION_019_PHASE_A_PATHS)
RUN005_AUDIT21_PHASE_B_PATHS = RUN005_AUDIT21_PHASE_A5_PATHS | (
    RUN005_INVOCATION_019_PHASE_B_PATHS - RUN005_INVOCATION_019_PHASE_A5_PATHS)
RUN005_AUDIT21_PHASE_SCOPES = {"PHASE_A": RUN005_AUDIT21_PHASE_A_PATHS,
    "PHASE_A5": RUN005_AUDIT21_PHASE_A5_PATHS, "PHASE_B": RUN005_AUDIT21_PHASE_B_PATHS}

RUN005_R1R2_BASE = "71713d0a79b006580510169924732d6791c87858"
RUN005_R1R2_SOURCE_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
}
RUN005_R1R2_PIN_CLOSURE_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
}
RUN005_R1R2_PHASE_A5_PATHS = RUN005_R1R2_SOURCE_PATHS | RUN005_R1R2_PIN_CLOSURE_PATHS
RUN005_R1R2_PHASE_B_GOVERNANCE_PATHS = {
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
RUN005_R1R2_PHASE_B_PATHS = RUN005_R1R2_PHASE_A5_PATHS | RUN005_R1R2_PHASE_B_GOVERNANCE_PATHS
RUN005_R1R2_AUTHORIZED_PATHS = RUN005_R1R2_PHASE_B_PATHS | {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
}
RUN005_R1R2_PHASE_SCOPES = {"PHASE_A": RUN005_R1R2_SOURCE_PATHS,
    "PHASE_A5": RUN005_R1R2_PHASE_A5_PATHS, "PHASE_B": RUN005_R1R2_PHASE_B_PATHS}

# Current R3/R4 corrective. Its lineage starts at the delivered R1/R2
# endpoint; historical phase sets above remain pinned to their own bases.
RUN005_R3_BASE = "bbac7448be59cc4afa54902744f1d4cf14fdf66c"
RUN005_R3_PHASE_A_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
}
RUN005_R3_PHASE_A5_PATHS = RUN005_R3_PHASE_A_PATHS | {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
}
RUN005_R3_PHASE_B_PATHS = RUN005_R3_PHASE_A5_PATHS | {
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
RUN005_R3_AUTHORIZED_PATHS = RUN005_R3_PHASE_B_PATHS | {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
}
RUN005_R3_PHASE_SCOPES = {"PHASE_A": RUN005_R3_PHASE_A_PATHS,
    "PHASE_A5": RUN005_R3_PHASE_A5_PATHS, "PHASE_B": RUN005_R3_PHASE_B_PATHS}

# R5 corrects only lineage metadata. The delivered R3/R4 commit remains the
# historical endpoint, while this candidate starts from that exact endpoint.
RUN005_R3_COMMIT = "dcc36a39f410651f5e7a142fa52eeda5daa50012"
RUN005_R5_BASE = RUN005_R3_COMMIT
RUN005_R5_SOURCE_PATHS = {
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
}
RUN005_R5_PIN_CLOSURE_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
}
RUN005_R5_PHASE_A5_PATHS = RUN005_R5_SOURCE_PATHS | RUN005_R5_PIN_CLOSURE_PATHS
RUN005_R5_PHASE_B_PATHS = RUN005_R5_PHASE_A5_PATHS | {
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
RUN005_R5_AUTHORIZED_PATHS = set(RUN005_R5_PHASE_B_PATHS)
RUN005_R5_PHASE_SCOPES = {"PHASE_A": RUN005_R5_SOURCE_PATHS,
    "PHASE_A5": RUN005_R5_PHASE_A5_PATHS, "PHASE_B": RUN005_R5_PHASE_B_PATHS}

# Invocation_020 offline corrective starts from its delivered, clean source
# endpoint. Keep this separate from every historical corrective scope above.
RUN005_INVOCATION_020_BASE = "d123c708bb3b0fd80c8096daa9836da50440db85"
RUN005_INVOCATION_020_COMMIT = "dee7d5dec565e51252f6a851c5959f07b8b8b512"
RUN005_R5_COMMIT = RUN005_INVOCATION_020_BASE
RUN005_INVOCATION_020_PHASE_A_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py",
    "ros2_ws/src/mecanum_nav_rl/test/test_step07_gate_b_observer_node.py",
}
RUN005_INVOCATION_020_PHASE_A5_PATHS = RUN005_INVOCATION_020_PHASE_A_PATHS | {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
}
RUN005_INVOCATION_020_PHASE_B_PATHS = RUN005_INVOCATION_020_PHASE_A5_PATHS | {
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
RUN005_INVOCATION_020_AUTHORIZED_PATHS = RUN005_INVOCATION_020_PHASE_B_PATHS | {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/test/test_step07_nav2_baseline_runtime_observer.cpp",
}
RUN005_INVOCATION_020_PHASE_SCOPES = {
    "PHASE_A": RUN005_INVOCATION_020_PHASE_A_PATHS,
    "PHASE_A5": RUN005_INVOCATION_020_PHASE_A5_PATHS,
    "PHASE_B": RUN005_INVOCATION_020_PHASE_B_PATHS,
}

# Invocation_020 failure-chain consistency corrective starts from its exact
# delivered endpoint; it has distinct phase metadata and does not rewrite the
# historical Invocation_020 scope above.
RUN005_INVOCATION_021_BASE = "dee7d5dec565e51252f6a851c5959f07b8b8b512"
RUN005_INVOCATION_021_COMMIT = "50fd738de91283c2c879f58fa6286ce5e15fc4bf"
RUN005_INVOCATION_021_PHASE_A_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
}
RUN005_INVOCATION_021_PHASE_A5_PATHS = RUN005_INVOCATION_021_PHASE_A_PATHS | {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
}
RUN005_INVOCATION_021_PHASE_B_PATHS = RUN005_INVOCATION_021_PHASE_A5_PATHS | {
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
RUN005_INVOCATION_021_AUTHORIZED_PATHS = RUN005_INVOCATION_021_PHASE_B_PATHS | {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
}
RUN005_INVOCATION_021_PHASE_SCOPES = {
    "PHASE_A": RUN005_INVOCATION_021_PHASE_A_PATHS,
    "PHASE_A5": RUN005_INVOCATION_021_PHASE_A5_PATHS,
    "PHASE_B": RUN005_INVOCATION_021_PHASE_B_PATHS,
}

# Observer acceptance persistence corrective starts at Invocation_021's exact
# delivered endpoint and has separate phase scopes.
RUN005_INVOCATION_022_BASE = RUN005_INVOCATION_021_COMMIT
RUN005_INVOCATION_022_PHASE_A_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
}
RUN005_INVOCATION_022_PHASE_A5_PATHS = RUN005_INVOCATION_022_PHASE_A_PATHS | {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
}
RUN005_INVOCATION_022_PHASE_B_PATHS = RUN005_INVOCATION_022_PHASE_A5_PATHS | {
    "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
RUN005_INVOCATION_022_AUTHORIZED_PATHS = RUN005_INVOCATION_022_PHASE_B_PATHS | {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py",
}
RUN005_INVOCATION_022_PHASE_SCOPES = {
    "PHASE_A": RUN005_INVOCATION_022_PHASE_A_PATHS,
    "PHASE_A5": RUN005_INVOCATION_022_PHASE_A5_PATHS,
    "PHASE_B": RUN005_INVOCATION_022_PHASE_B_PATHS,
}

# The approved Run005 temporal-coherence implementation starts from the exact
# reviewed design commit. Its phase sets are independent of prior Invocation
# scopes and are checked against base..HEAD (including staged and untracked
# paths) or the committed base..candidate range.
RUN005_TEMPORAL_L2_BASE = "66849ee6af092dce973075bcd438bd3d936fd2a3"
RUN005_TEMPORAL_L2_PHASE_A_PATHS = {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_run005_runtime_guard.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
    "ros2_ws/src/mecanum_nav_rl/config/v3/resolved/sim_eval_nav2_baseline.resolved.json",
    "ros2_ws/src/mecanum_nav_rl/config/v3/contracts/step07_run005_temporal_coherence.v1.json",
    "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/config/step07_temporal_contract.py",
    "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/config/v3_compiler.py",
    "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/config/v3_models.py",
    "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/config/v3_validators.py",
    "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py",
    "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_lifecycle_ingress.py",
    "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_temporal_state.py",
    "ros2_ws/src/mecanum_nav_rl/setup.py",
    "ros2_ws/src/mecanum_nav_rl/test/test_config_v3_compiler.py",
    "ros2_ws/src/mecanum_nav_rl/test/test_step07_gate_b_observer_node.py",
    "ros2_ws/src/mecanum_nav_rl/test/test_step07_lifecycle_ingress.py",
    "ros2_ws/src/mecanum_nav_rl/test/test_step07_temporal_state.py",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/CMakeLists.txt",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/package.xml",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/include/step07_nav2_baseline_runtime_observer/lifecycle_ingress.hpp",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/src/lifecycle_ingress.cpp",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/test/test_lifecycle_ingress.cpp",
    "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
}
RUN005_TEMPORAL_L2_PHASE_A5_PATHS = RUN005_TEMPORAL_L2_PHASE_A_PATHS | {
    "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
}
RUN005_TEMPORAL_L2_PHASE_B_PATHS = RUN005_TEMPORAL_L2_PHASE_A5_PATHS | {
    "docs/governance/decisions/STEP-07_RUN005_TEMPORAL_COHERENCE_L2_OFFLINE_IMPLEMENTATION_DECISION.md",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
    "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
}
RUN005_TEMPORAL_L2_AUTHORIZED_PATHS = RUN005_TEMPORAL_L2_PHASE_B_PATHS | {
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py",
    "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
    "ros2_ws/src/mecanum_nav_rl/test/test_config_v3_schema.py",
    "ros2_ws/src/mecanum_nav_rl/test/test_config_v3_assets.py",
    "ros2_ws/src/step07_nav2_baseline_runtime_observer/test/test_step07_nav2_baseline_runtime_observer.cpp",
}
RUN005_TEMPORAL_L2_PHASE_SCOPES = {
    "PHASE_A": RUN005_TEMPORAL_L2_PHASE_A_PATHS,
    "PHASE_A5": RUN005_TEMPORAL_L2_PHASE_A5_PATHS,
    "PHASE_B": RUN005_TEMPORAL_L2_PHASE_B_PATHS,
}


def _r3_scope_document(phase, base=RUN005_R3_BASE):
    paths = RUN005_R3_PHASE_SCOPES[phase]
    return {"current_candidate_base_commit": base,
        "SOURCE_FREEZE": "FALSE" if phase == "PHASE_A" else "TRUE",
        "current_corrective_scope": {"base_commit": base, "phase": phase,
            "path_count": len(paths), "paths": sorted(paths)}}


def _validate_r3_scope(actual, document, untracked=(), expected_base=RUN005_R3_BASE):
    scope = document.get("current_corrective_scope", {})
    phase = scope.get("phase")
    if (phase not in RUN005_R3_PHASE_SCOPES
            or document.get("current_candidate_base_commit") != expected_base
            or scope.get("base_commit") != expected_base):
        raise AssertionError("RUN005_R3_PHASE_OR_BASE_INVALID")
    expected = RUN005_R3_PHASE_SCOPES[phase]
    if scope.get("paths") != sorted(expected) or scope.get("path_count") != len(expected):
        raise AssertionError("RUN005_R3_METADATA_SCOPE_MISMATCH")
    if phase != "PHASE_A" and document.get("SOURCE_FREEZE") != "TRUE":
        raise AssertionError("RUN005_R3_SOURCE_FREEZE_INVALID")
    if set(actual) != expected or untracked:
        raise AssertionError(f"RUN005_R3_EXACT_SCOPE_MISMATCH:{sorted(actual)}:{sorted(untracked)}")
    if not set(actual) <= RUN005_R3_AUTHORIZED_PATHS:
        raise AssertionError("RUN005_R3_PATH_OUTSIDE_AUTHORIZATION")
    return phase


def _r3_git_changed_paths(root=ROOT, base=RUN005_R3_BASE):
    actual = set(subprocess.run(["git", "diff", "--name-only", base], cwd=root,
        check=True, capture_output=True, text=True).stdout.splitlines())
    untracked = set(subprocess.run(["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root, check=True, capture_output=True, text=True).stdout.splitlines())
    return actual, untracked


def _r5_scope_document(phase, base=RUN005_R5_BASE):
    paths = RUN005_R5_PHASE_SCOPES[phase]
    return {"current_candidate_base_commit": base,
        "corrective_commit_parent": base,
        "SOURCE_FREEZE": "FALSE" if phase == "PHASE_A" else "TRUE",
        "current_corrective_scope": {"base_commit": base, "phase": phase,
            "path_count": len(paths), "paths": sorted(paths)}}


def _validate_r5_scope(actual, document, untracked=(), expected_base=RUN005_R5_BASE):
    scope = document.get("current_corrective_scope", {})
    phase = scope.get("phase")
    if (phase not in RUN005_R5_PHASE_SCOPES
            or document.get("current_candidate_base_commit") != expected_base
            or document.get("corrective_commit_parent") != expected_base
            or scope.get("base_commit") != expected_base):
        raise AssertionError("RUN005_R5_PHASE_OR_LINEAGE_INVALID")
    expected = RUN005_R5_PHASE_SCOPES[phase]
    if scope.get("paths") != sorted(expected) or scope.get("path_count") != len(expected):
        raise AssertionError("RUN005_R5_METADATA_SCOPE_MISMATCH")
    if phase != "PHASE_A" and document.get("SOURCE_FREEZE") != "TRUE":
        raise AssertionError("RUN005_R5_SOURCE_FREEZE_INVALID")
    if set(actual) != expected or untracked:
        raise AssertionError(f"RUN005_R5_EXACT_SCOPE_MISMATCH:{sorted(actual)}:{sorted(untracked)}")
    if set(actual) - RUN005_R5_AUTHORIZED_PATHS:
        raise AssertionError("RUN005_R5_PATH_OUTSIDE_AUTHORIZATION")
    return phase


def _r5_git_changed_paths(root=ROOT, base=RUN005_R5_BASE):
    actual = set(subprocess.run(["git", "diff", "--name-only", base], cwd=root,
        check=True, capture_output=True, text=True).stdout.splitlines())
    untracked = set(subprocess.run(["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root, check=True, capture_output=True, text=True).stdout.splitlines())
    return actual, untracked


def _invocation020_scope_document(phase):
    paths = RUN005_INVOCATION_020_PHASE_SCOPES[phase]
    return {"current_candidate_base_commit": RUN005_INVOCATION_020_BASE,
        "corrective_commit_parent": RUN005_INVOCATION_020_BASE,
        "SOURCE_FREEZE": "FALSE" if phase == "PHASE_A" else "TRUE",
        "current_corrective_scope": {"base_commit": RUN005_INVOCATION_020_BASE,
            "phase": phase, "path_count": len(paths), "paths": sorted(paths)},
        "authorized_allowlist": {"base_commit": RUN005_INVOCATION_020_BASE,
            "path_count": len(RUN005_INVOCATION_020_AUTHORIZED_PATHS),
            "paths": sorted(RUN005_INVOCATION_020_AUTHORIZED_PATHS)}}


def _validate_invocation020_scope(actual, document, untracked=()):
    scope = document.get("current_corrective_scope", {})
    phase = scope.get("phase")
    if (phase not in RUN005_INVOCATION_020_PHASE_SCOPES
            or document.get("current_candidate_base_commit") != RUN005_INVOCATION_020_BASE
            or document.get("corrective_commit_parent") != RUN005_INVOCATION_020_BASE
            or scope.get("base_commit") != RUN005_INVOCATION_020_BASE):
        raise AssertionError("INVOCATION020_PHASE_OR_LINEAGE_INVALID")
    expected = RUN005_INVOCATION_020_PHASE_SCOPES[phase]
    if scope.get("paths") != sorted(expected) or scope.get("path_count") != len(expected):
        raise AssertionError("INVOCATION020_METADATA_SCOPE_MISMATCH")
    authorized = document.get("authorized_allowlist", {})
    if (authorized.get("base_commit") != RUN005_INVOCATION_020_BASE
            or authorized.get("paths") != sorted(RUN005_INVOCATION_020_AUTHORIZED_PATHS)
            or authorized.get("path_count") != len(RUN005_INVOCATION_020_AUTHORIZED_PATHS)):
        raise AssertionError("INVOCATION020_AUTHORIZED_ALLOWLIST_MISMATCH")
    if phase == "PHASE_A" and document.get("SOURCE_FREEZE") != "FALSE":
        raise AssertionError("INVOCATION020_SOURCE_FREEZE_INVALID")
    if phase != "PHASE_A" and document.get("SOURCE_FREEZE") != "TRUE":
        raise AssertionError("INVOCATION020_SOURCE_FREEZE_INVALID")
    if set(actual) != expected or untracked:
        raise AssertionError(f"INVOCATION020_EXACT_SCOPE_MISMATCH:{sorted(actual)}:{sorted(untracked)}")
    if set(actual) - RUN005_INVOCATION_020_AUTHORIZED_PATHS:
        raise AssertionError("INVOCATION020_PATH_OUTSIDE_AUTHORIZATION")
    return phase


def _invocation020_git_changed_paths(root=ROOT):
    base = RUN005_INVOCATION_020_BASE
    actual = set(subprocess.run(["git", "diff", "--name-only", base], cwd=root,
        check=True, capture_output=True, text=True).stdout.splitlines())
    untracked = set(subprocess.run(["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root, check=True, capture_output=True, text=True).stdout.splitlines())
    return actual, untracked


def _invocation021_scope_document(phase):
    paths = RUN005_INVOCATION_021_PHASE_SCOPES[phase]
    return {"current_candidate_base_commit": RUN005_INVOCATION_021_BASE,
        "corrective_commit_parent": RUN005_INVOCATION_021_BASE,
        "SOURCE_FREEZE": "FALSE" if phase == "PHASE_A" else "TRUE",
        "current_corrective_scope": {"base_commit": RUN005_INVOCATION_021_BASE,
            "phase": phase, "path_count": len(paths), "paths": sorted(paths)},
        "authorized_allowlist": {"base_commit": RUN005_INVOCATION_021_BASE,
            "path_count": len(RUN005_INVOCATION_021_AUTHORIZED_PATHS),
            "paths": sorted(RUN005_INVOCATION_021_AUTHORIZED_PATHS)}}


def _validate_invocation021_scope(actual, document, untracked=()):
    scope = document.get("current_corrective_scope", {})
    phase = scope.get("phase")
    if (phase not in RUN005_INVOCATION_021_PHASE_SCOPES
            or document.get("current_candidate_base_commit") != RUN005_INVOCATION_021_BASE
            or document.get("corrective_commit_parent") != RUN005_INVOCATION_021_BASE
            or scope.get("base_commit") != RUN005_INVOCATION_021_BASE):
        raise AssertionError("INVOCATION021_PHASE_OR_LINEAGE_INVALID")
    expected = RUN005_INVOCATION_021_PHASE_SCOPES[phase]
    if scope.get("paths") != sorted(expected) or scope.get("path_count") != len(expected):
        raise AssertionError("INVOCATION021_METADATA_SCOPE_MISMATCH")
    authorized = document.get("authorized_allowlist", {})
    if (authorized.get("base_commit") != RUN005_INVOCATION_021_BASE
            or authorized.get("paths") != sorted(RUN005_INVOCATION_021_AUTHORIZED_PATHS)
            or authorized.get("path_count") != len(RUN005_INVOCATION_021_AUTHORIZED_PATHS)):
        raise AssertionError("INVOCATION021_AUTHORIZED_ALLOWLIST_MISMATCH")
    if document.get("SOURCE_FREEZE") != ("FALSE" if phase == "PHASE_A" else "TRUE"):
        raise AssertionError("INVOCATION021_SOURCE_FREEZE_INVALID")
    if set(actual) != expected or untracked:
        raise AssertionError(f"INVOCATION021_EXACT_SCOPE_MISMATCH:{sorted(actual)}:{sorted(untracked)}")
    if set(actual) - RUN005_INVOCATION_021_AUTHORIZED_PATHS:
        raise AssertionError("INVOCATION021_PATH_OUTSIDE_AUTHORIZATION")
    return phase


def _invocation021_git_changed_paths(root=ROOT):
    base = RUN005_INVOCATION_021_BASE
    actual = set(subprocess.run(["git", "diff", "--name-only", base], cwd=root,
        check=True, capture_output=True, text=True).stdout.splitlines())
    untracked = set(subprocess.run(["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root, check=True, capture_output=True, text=True).stdout.splitlines())
    return actual, untracked


def _invocation021_current_scope_document(actual):
    path = ROOT / "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json"
    document = _load_json(path)
    if document.get("current_candidate_base_commit") == RUN005_INVOCATION_021_BASE:
        return document
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True).stdout.strip()
    if head == RUN005_INVOCATION_021_BASE and actual == RUN005_INVOCATION_021_PHASE_A_PATHS:
        return _invocation021_scope_document("PHASE_A")
    raise AssertionError("INVOCATION021_CURRENT_PHASE_METADATA_MISSING")


def _invocation022_scope_document(phase):
    paths = RUN005_INVOCATION_022_PHASE_SCOPES[phase]
    return {"current_candidate_base_commit": RUN005_INVOCATION_022_BASE,
        "corrective_commit_parent": RUN005_INVOCATION_022_BASE,
        "SOURCE_FREEZE": "FALSE" if phase == "PHASE_A" else "TRUE",
        "current_corrective_scope": {"base_commit": RUN005_INVOCATION_022_BASE,
            "phase": phase, "path_count": len(paths), "paths": sorted(paths)},
        "authorized_allowlist": {"base_commit": RUN005_INVOCATION_022_BASE,
            "path_count": len(RUN005_INVOCATION_022_AUTHORIZED_PATHS),
            "paths": sorted(RUN005_INVOCATION_022_AUTHORIZED_PATHS)}}


def _validate_invocation022_scope(actual, document, untracked=()):
    scope = document.get("current_corrective_scope", {})
    phase = scope.get("phase")
    if (phase not in RUN005_INVOCATION_022_PHASE_SCOPES
            or document.get("current_candidate_base_commit") != RUN005_INVOCATION_022_BASE
            or document.get("corrective_commit_parent") != RUN005_INVOCATION_022_BASE
            or scope.get("base_commit") != RUN005_INVOCATION_022_BASE):
        raise AssertionError("INVOCATION022_PHASE_OR_LINEAGE_INVALID")
    expected = RUN005_INVOCATION_022_PHASE_SCOPES[phase]
    if scope.get("paths") != sorted(expected) or scope.get("path_count") != len(expected):
        raise AssertionError("INVOCATION022_METADATA_SCOPE_MISMATCH")
    authorized = document.get("authorized_allowlist", {})
    if (authorized.get("base_commit") != RUN005_INVOCATION_022_BASE
            or authorized.get("paths") != sorted(RUN005_INVOCATION_022_AUTHORIZED_PATHS)
            or authorized.get("path_count") != len(RUN005_INVOCATION_022_AUTHORIZED_PATHS)):
        raise AssertionError("INVOCATION022_AUTHORIZED_ALLOWLIST_MISMATCH")
    if document.get("SOURCE_FREEZE") != ("FALSE" if phase == "PHASE_A" else "TRUE"):
        raise AssertionError("INVOCATION022_SOURCE_FREEZE_INVALID")
    if set(actual) != expected or untracked:
        raise AssertionError(f"INVOCATION022_EXACT_SCOPE_MISMATCH:{sorted(actual)}:{sorted(untracked)}")
    if set(actual) - RUN005_INVOCATION_022_AUTHORIZED_PATHS:
        raise AssertionError("INVOCATION022_PATH_OUTSIDE_AUTHORIZATION")
    return phase


def _invocation022_git_changed_paths(root=ROOT):
    base = RUN005_INVOCATION_022_BASE
    actual = set(subprocess.run(["git", "diff", "--name-only", base], cwd=root,
        check=True, capture_output=True, text=True).stdout.splitlines())
    untracked = set(subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=root,
        check=True, capture_output=True, text=True).stdout.splitlines())
    return actual, untracked


def _invocation022_current_scope_document(actual):
    path = ROOT / "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json"
    document = _load_json(path)
    if document.get("current_candidate_base_commit") == RUN005_INVOCATION_022_BASE:
        return document
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True).stdout.strip()
    if head == RUN005_INVOCATION_022_BASE and actual == RUN005_INVOCATION_022_PHASE_A_PATHS:
        return _invocation022_scope_document("PHASE_A")
    raise AssertionError("INVOCATION022_CURRENT_PHASE_METADATA_MISSING")


def _temporal_l2_scope_document(phase):
    paths = RUN005_TEMPORAL_L2_PHASE_SCOPES[phase]
    return {"current_candidate_base_commit": RUN005_TEMPORAL_L2_BASE,
        "corrective_commit_parent": RUN005_TEMPORAL_L2_BASE,
        "SOURCE_FREEZE": "FALSE" if phase == "PHASE_A" else "TRUE",
        "current_corrective_scope": {"base_commit": RUN005_TEMPORAL_L2_BASE,
            "phase": phase, "path_count": len(paths), "paths": sorted(paths)},
        "authorized_allowlist": {"base_commit": RUN005_TEMPORAL_L2_BASE,
            "path_count": len(RUN005_TEMPORAL_L2_AUTHORIZED_PATHS),
            "paths": sorted(RUN005_TEMPORAL_L2_AUTHORIZED_PATHS)}}


def _validate_temporal_l2_scope(actual, document, untracked=()):
    scope = document.get("current_corrective_scope", {})
    phase = scope.get("phase")
    if (phase not in RUN005_TEMPORAL_L2_PHASE_SCOPES
            or document.get("current_candidate_base_commit") != RUN005_TEMPORAL_L2_BASE
            or document.get("corrective_commit_parent") != RUN005_TEMPORAL_L2_BASE
            or scope.get("base_commit") != RUN005_TEMPORAL_L2_BASE):
        raise AssertionError("RUN005_TEMPORAL_L2_PHASE_OR_LINEAGE_INVALID")
    expected = RUN005_TEMPORAL_L2_PHASE_SCOPES[phase]
    if scope.get("paths") != sorted(expected) or scope.get("path_count") != len(expected):
        raise AssertionError("RUN005_TEMPORAL_L2_METADATA_SCOPE_MISMATCH")
    authorized = document.get("authorized_allowlist", {})
    if (authorized.get("base_commit") != RUN005_TEMPORAL_L2_BASE
            or authorized.get("paths") != sorted(RUN005_TEMPORAL_L2_AUTHORIZED_PATHS)
            or authorized.get("path_count") != len(RUN005_TEMPORAL_L2_AUTHORIZED_PATHS)):
        raise AssertionError("RUN005_TEMPORAL_L2_AUTHORIZED_ALLOWLIST_MISMATCH")
    if document.get("SOURCE_FREEZE") != ("FALSE" if phase == "PHASE_A" else "TRUE"):
        raise AssertionError("RUN005_TEMPORAL_L2_SOURCE_FREEZE_INVALID")
    if set(actual) != expected:
        raise AssertionError(f"RUN005_TEMPORAL_L2_EXACT_SCOPE_MISMATCH:{sorted(actual)}")
    if set(actual) - RUN005_TEMPORAL_L2_AUTHORIZED_PATHS:
        raise AssertionError("RUN005_TEMPORAL_L2_PATH_OUTSIDE_AUTHORIZATION")
    if set(untracked) - set(actual):
        raise AssertionError(f"RUN005_TEMPORAL_L2_UNTRACKED_OUTSIDE_SCOPE:{sorted(untracked)}")
    if any(path.startswith(("build/", "install/", "log/", ".pytest_cache/"))
           or "/__pycache__/" in path for path in untracked):
        raise AssertionError("RUN005_TEMPORAL_L2_GENERATED_UNTRACKED_PATH")
    return phase


def _temporal_l2_git_changed_paths(root=ROOT):
    actual = set(subprocess.run(["git", "diff", "--name-only", RUN005_TEMPORAL_L2_BASE],
        cwd=root, check=True, capture_output=True, text=True).stdout.splitlines())
    actual.update(subprocess.run(["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root, check=True, capture_output=True, text=True).stdout.splitlines())
    untracked = set(subprocess.run(["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root, check=True, capture_output=True, text=True).stdout.splitlines())
    return actual, untracked


def _temporal_l2_current_scope_document(actual):
    path = ROOT / "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json"
    if path.is_file():
        document = _load_json(path)
        if document.get("current_candidate_base_commit") == RUN005_TEMPORAL_L2_BASE:
            return document
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True).stdout.strip()
    if head == RUN005_TEMPORAL_L2_BASE:
        for phase in ("PHASE_A", "PHASE_A5"):
            if set(actual) == RUN005_TEMPORAL_L2_PHASE_SCOPES[phase]:
                return _temporal_l2_scope_document(phase)
    raise AssertionError("RUN005_TEMPORAL_L2_CURRENT_PHASE_METADATA_MISSING")


def _invocation020_current_scope_document(actual):
    evidence_path = ROOT / "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json"
    document = _load_json(evidence_path)
    if document.get("current_candidate_base_commit") == RUN005_INVOCATION_020_BASE:
        return document
    # Before the one metadata reconciliation, the only recognized live
    # candidate state is the exact Phase-A set from the fixed delivered base.
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True).stdout.strip()
    if head == RUN005_INVOCATION_020_BASE and actual == RUN005_INVOCATION_020_PHASE_A_PATHS:
        return _invocation020_scope_document("PHASE_A")
    raise AssertionError("INVOCATION020_CURRENT_PHASE_METADATA_MISSING")


def _r5_current_scope_document():
    return json.loads(subprocess.run(["git", "show",
        f"{RUN005_R5_COMMIT}:artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json"],
        cwd=ROOT, check=True, capture_output=True, text=True).stdout)


def _r1r2_scope_document(phase, base=RUN005_R1R2_BASE):
    paths = RUN005_R1R2_PHASE_SCOPES[phase]
    return {"current_candidate_base_commit": base,
        "SOURCE_FREEZE": "FALSE" if phase == "PHASE_A" else "TRUE",
        "current_corrective_scope": {"base_commit": base,
            "phase": phase, "path_count": len(paths), "paths": sorted(paths)}}


def _validate_r1r2_scope(actual, document, untracked=(), expected_base=RUN005_R1R2_BASE):
    scope = document.get("current_corrective_scope", {})
    phase = scope.get("phase")
    if (phase not in RUN005_R1R2_PHASE_SCOPES
            or document.get("current_candidate_base_commit") != expected_base
            or scope.get("base_commit") != expected_base):
        raise AssertionError("RUN005_R1R2_PHASE_OR_BASE_INVALID")
    expected = RUN005_R1R2_PHASE_SCOPES[phase]
    if scope.get("paths") != sorted(expected) or scope.get("path_count") != len(expected):
        raise AssertionError("RUN005_R1R2_METADATA_SCOPE_MISMATCH")
    if phase != "PHASE_A" and document.get("SOURCE_FREEZE") != "TRUE":
        raise AssertionError("RUN005_R1R2_SOURCE_FREEZE_INVALID")
    if set(actual) != expected or untracked:
        raise AssertionError(f"RUN005_R1R2_EXACT_SCOPE_MISMATCH:{sorted(actual)}:{sorted(untracked)}")
    if not set(actual) <= RUN005_R1R2_AUTHORIZED_PATHS:
        raise AssertionError("RUN005_R1R2_PATH_OUTSIDE_AUTHORIZATION")
    return phase


def _r1r2_git_changed_paths(root=ROOT, base=RUN005_R1R2_BASE):
    actual = set(subprocess.run(["git", "diff", "--name-only", base], cwd=root,
        check=True, capture_output=True, text=True).stdout.splitlines())
    untracked = set(subprocess.run(["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root, check=True, capture_output=True, text=True).stdout.splitlines())
    return actual, untracked


def _r1r2_current_scope_document():
    document = _load_json(ROOT / "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json")
    if document.get("current_candidate_base_commit") != RUN005_R1R2_BASE:
        parent = json.loads(subprocess.run(["git", "show", f"{RUN005_R1R2_BASE}:artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json"],
            cwd=ROOT, check=True, capture_output=True, text=True).stdout)
        if document != parent:
            raise AssertionError("RUN005_R1R2_INITIAL_METADATA_NOT_EXACT_BASE")
        return _r1r2_scope_document("PHASE_A")
    return document


def test_run005_r1r2_lineage_preserves_f1_f5_closure_and_exact_phase_sets():
    assert RUN005_R1R2_BASE == "71713d0a79b006580510169924732d6791c87858"
    assert subprocess.run(["git", "rev-parse", f"{RUN005_R1R2_BASE}^"], cwd=ROOT,
        check=True, capture_output=True, text=True).stdout.strip() == "21eab3580be48de9f00585cba904445dae7ce62f"
    historical = set(subprocess.run(["git", "diff", "--name-only",
        "21eab3580be48de9f00585cba904445dae7ce62f..71713d0a79b006580510169924732d6791c87858"],
        cwd=ROOT, check=True, capture_output=True, text=True).stdout.splitlines())
    assert historical == RUN005_AUDIT21_PHASE_B_PATHS
    assert len(RUN005_R1R2_SOURCE_PATHS) == 3
    assert len(RUN005_R1R2_PHASE_A5_PATHS) == 6
    assert len(RUN005_R1R2_PHASE_B_PATHS) == 10
    assert len(RUN005_R1R2_AUTHORIZED_PATHS) == 12


def test_run005_r1r2_current_candidate_exact_scope_from_fixed_base():
    # R1/R2 is historical after R3 begins; assert its committed endpoint only.
    actual = set(subprocess.run(["git", "diff", "--name-only",
        f"{RUN005_R1R2_BASE}..{RUN005_R3_BASE}"], cwd=ROOT,
        check=True, capture_output=True, text=True).stdout.splitlines())
    assert actual == RUN005_R1R2_PHASE_B_PATHS


@pytest.mark.parametrize("phase", ["PHASE_A", "PHASE_A5", "PHASE_B"])
def test_run005_r1r2_scope_accepts_only_declared_exact_phase(phase):
    assert _validate_r1r2_scope(RUN005_R1R2_PHASE_SCOPES[phase],
        _r1r2_scope_document(phase)) == phase


@pytest.mark.parametrize("fault", ["missing_governance", "extra", "historical", "phase_mismatch",
                                    "metadata_paths", "wrong_base", "freeze", "untracked"])
def test_run005_r1r2_phase_scope_rejects_ambiguous_or_unauthorized_paths(fault):
    document = _r1r2_scope_document("PHASE_B")
    actual = set(RUN005_R1R2_PHASE_B_PATHS)
    untracked = set()
    if fault == "missing_governance":
        actual.remove("docs/governance/PROJECT_PROGRESS_LEDGER.md")
    elif fault == "extra":
        actual.add("unapproved.txt")
    elif fault == "historical":
        actual.add("artifacts/simulation/STEP07_NAV2_BASELINE_RUN_005_ATTEMPT_002_INVOCATION_019/run_record.json")
    elif fault == "phase_mismatch":
        document = _r1r2_scope_document("PHASE_A")
    elif fault == "metadata_paths":
        document["current_corrective_scope"]["paths"].pop()
    elif fault == "wrong_base":
        document["current_candidate_base_commit"] = "21eab3580be48de9f00585cba904445dae7ce62f"
    elif fault == "freeze":
        document["SOURCE_FREEZE"] = "FALSE"
    else:
        untracked.add("log/new.txt")
    with pytest.raises(AssertionError, match="RUN005_R1R2_"):
        _validate_r1r2_scope(actual, document, untracked)


def test_run005_r1r2_diff_scope_covers_staged_unstaged_untracked_and_post_commit(tmp_path):
    paths = sorted(RUN005_R1R2_SOURCE_PATHS)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "offline@example.invalid"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Offline Scope Fixture"], cwd=tmp_path, check=True)
    for path in paths:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", *paths], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "scope base"], cwd=tmp_path, check=True)
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True,
                          capture_output=True, text=True).stdout.strip()
    (tmp_path / paths[0]).write_text("staged change\n", encoding="utf-8")
    subprocess.run(["git", "add", paths[0]], cwd=tmp_path, check=True)
    (tmp_path / paths[1]).write_text("unstaged change\n", encoding="utf-8")
    (tmp_path / paths[2]).write_text("staged then unstaged\n", encoding="utf-8")
    subprocess.run(["git", "add", paths[2]], cwd=tmp_path, check=True)
    (tmp_path / paths[2]).write_text("unstaged after stage\n", encoding="utf-8")
    actual, untracked = _r1r2_git_changed_paths(tmp_path, base)
    assert actual == RUN005_R1R2_SOURCE_PATHS and not untracked
    _validate_r1r2_scope(actual, _r1r2_scope_document("PHASE_A", base), expected_base=base)
    subprocess.run(["git", "add", *paths], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "scope phase A"], cwd=tmp_path, check=True)
    actual, untracked = _r1r2_git_changed_paths(tmp_path, base)
    assert actual == RUN005_R1R2_SOURCE_PATHS and not untracked
    _validate_r1r2_scope(actual, _r1r2_scope_document("PHASE_A", base), expected_base=base)
    (tmp_path / "untracked.txt").write_text("untracked\n", encoding="utf-8")
    actual, untracked = _r1r2_git_changed_paths(tmp_path, base)
    with pytest.raises(AssertionError, match="RUN005_R1R2_EXACT_SCOPE_MISMATCH"):
        _validate_r1r2_scope(actual, _r1r2_scope_document("PHASE_A", base),
                             untracked, expected_base=base)


def test_run005_r3_lineage_preserves_r1r2_endpoint_and_declares_exact_scopes():
    assert subprocess.run(["git", "rev-parse", f"{RUN005_R3_BASE}^"], cwd=ROOT,
        check=True, capture_output=True, text=True).stdout.strip() == RUN005_R1R2_BASE
    historical = set(subprocess.run(["git", "diff", "--name-only",
        f"{RUN005_R1R2_BASE}..{RUN005_R3_BASE}"], cwd=ROOT,
        check=True, capture_output=True, text=True).stdout.splitlines())
    assert historical == RUN005_R1R2_PHASE_B_PATHS
    assert [len(RUN005_R3_PHASE_SCOPES[key]) for key in ("PHASE_A", "PHASE_A5", "PHASE_B")] == [4, 7, 11]
    assert len(RUN005_R3_AUTHORIZED_PATHS) == 12


@pytest.mark.parametrize("phase", ["PHASE_A", "PHASE_A5", "PHASE_B"])
def test_run005_r3_declared_phase_accepts_only_its_exact_scope(phase):
    assert _validate_r3_scope(RUN005_R3_PHASE_SCOPES[phase], _r3_scope_document(phase)) == phase


def test_run005_r3_r4_historical_record_keeps_exact_delivery_lineage_and_scope():
    assert subprocess.run(["git", "rev-parse", f"{RUN005_R3_COMMIT}^"], cwd=ROOT,
        check=True, capture_output=True, text=True).stdout.strip() == RUN005_R3_BASE
    actual = set(subprocess.run(["git", "diff", "--name-only",
        f"{RUN005_R3_BASE}..{RUN005_R3_COMMIT}"], cwd=ROOT,
        check=True, capture_output=True, text=True).stdout.splitlines())
    assert actual == RUN005_R3_PHASE_B_PATHS
    evidence = _load_json(ROOT / "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json")
    manifest = _load_json(ROOT / "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json")
    for document in (evidence, manifest):
        historical = document["r3_r4_corrective"]
        assert historical["commit_sha"] == RUN005_R3_COMMIT
        assert historical["base_commit"] == historical["sole_parent"] == RUN005_R3_BASE
        assert historical["status"] == "HISTORICAL_SUPERSEDED_BY_R5_LINEAGE_METADATA_CORRECTION"
        assert historical["historical_scope"] == {
            "base_commit": RUN005_R3_BASE,
            "phase": "PHASE_B",
            "path_count": len(RUN005_R3_PHASE_B_PATHS),
            "paths": sorted(RUN005_R3_PHASE_B_PATHS),
        }
        assert historical["historical_authorized_allowlist"] == {
            "base_commit": RUN005_R3_BASE,
            "path_count": len(RUN005_R3_AUTHORIZED_PATHS),
            "paths": sorted(RUN005_R3_AUTHORIZED_PATHS),
        }


@pytest.mark.parametrize("phase", ["PHASE_A", "PHASE_A5", "PHASE_B"])
def test_run005_r5_declared_phase_accepts_only_exact_scope_and_lineage(phase):
    assert _validate_r5_scope(RUN005_R5_PHASE_SCOPES[phase],
        _r5_scope_document(phase)) == phase


@pytest.mark.parametrize("fault", ["missing_governance", "extra", "historical",
    "phase", "base", "parent", "metadata", "freeze", "untracked"])
def test_run005_r5_phase_scope_rejects_wrong_parent_or_inexact_scope(fault):
    document = _r5_scope_document("PHASE_B")
    actual = set(RUN005_R5_PHASE_B_PATHS)
    untracked = set()
    if fault == "missing_governance":
        actual.remove("docs/governance/PROJECT_PROGRESS_LEDGER.md")
    elif fault == "extra":
        actual.add("unapproved.py")
    elif fault == "historical":
        actual.add("/home/hazan/step07_runtime_evidence/STEP07_NAV2_BASELINE_RUN_005_ATTEMPT_002_INVOCATION_019/run_record.json")
    elif fault == "phase":
        document = _r5_scope_document("PHASE_A")
    elif fault == "base":
        document["current_candidate_base_commit"] = RUN005_R3_BASE
    elif fault == "parent":
        document["corrective_commit_parent"] = RUN005_R1R2_BASE
    elif fault == "metadata":
        document["current_corrective_scope"]["paths"].pop()
    elif fault == "freeze":
        document["SOURCE_FREEZE"] = "FALSE"
    else:
        untracked.add("untracked.txt")
    with pytest.raises(AssertionError, match="RUN005_R5_"):
        _validate_r5_scope(actual, document, untracked)


def test_run005_r5_rejects_stale_r3_parent_but_r1r2_parent_remains_historical():
    assert RUN005_R1R2_BASE == "71713d0a79b006580510169924732d6791c87858"
    assert subprocess.run(["git", "rev-parse", f"{RUN005_R3_COMMIT}^"], cwd=ROOT,
        check=True, capture_output=True, text=True).stdout.strip() != RUN005_R1R2_BASE
    stale = {"r3_r4_corrective": {"base_commit": RUN005_R3_BASE,
        "sole_parent": RUN005_R1R2_BASE}}
    with pytest.raises(AssertionError, match="RUN005_R3_R4_STALE_PARENT"):
        _validate_r3_r4_historical_parent(stale["r3_r4_corrective"])
    # R1/R2's own historical parent is still correct and tested above.
    assert subprocess.run(["git", "rev-parse", f"{RUN005_R1R2_BASE}^"], cwd=ROOT,
        check=True, capture_output=True, text=True).stdout.strip() == "21eab3580be48de9f00585cba904445dae7ce62f"


def _validate_r3_r4_historical_parent(record):
    if (record.get("base_commit") != RUN005_R3_BASE
            or record.get("sole_parent") != RUN005_R3_BASE):
        raise AssertionError("RUN005_R3_R4_STALE_PARENT")


def test_run005_r5_current_metadata_exact_scope_uses_fixed_base_and_actual_diff():
    document = _r5_current_scope_document()
    actual = set(subprocess.run(["git", "diff", "--name-only",
        f"{RUN005_R5_BASE}..{RUN005_R5_COMMIT}"], cwd=ROOT,
        check=True, capture_output=True, text=True).stdout.splitlines())
    untracked = set()
    assert _validate_r5_scope(actual, document, untracked) in RUN005_R5_PHASE_SCOPES
    expected_scope = {"base_commit": RUN005_R5_BASE, "phase": "PHASE_B",
        "path_count": len(RUN005_R5_PHASE_B_PATHS), "paths": sorted(RUN005_R5_PHASE_B_PATHS)}
    expected_allowlist = {"base_commit": RUN005_R5_BASE,
        "path_count": len(RUN005_R5_AUTHORIZED_PATHS), "paths": sorted(RUN005_R5_AUTHORIZED_PATHS)}
    for relative in (
        "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
        "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
    ):
        metadata = json.loads(subprocess.run(["git", "show", f"{RUN005_R5_COMMIT}:{relative}"],
            cwd=ROOT, check=True, capture_output=True, text=True).stdout)
        assert metadata["current_candidate_base_commit"] == RUN005_R5_BASE
        assert metadata["corrective_commit_parent"] == RUN005_R5_BASE
        assert metadata["current_corrective_scope"] == metadata["latest_corrective_scope"] == expected_scope
        assert metadata["authorized_allowlist"] == metadata["latest_corrective_authorized_allowlist"] == expected_allowlist
        _validate_r3_r4_historical_parent(metadata["r3_r4_corrective"])


def test_run005_r5_git_scope_covers_staged_unstaged_untracked_and_post_commit(tmp_path):
    paths = sorted(RUN005_R5_SOURCE_PATHS)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "offline@example.invalid"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Offline Scope Fixture"], cwd=tmp_path, check=True)
    for path in paths:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", *paths], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "scope base"], cwd=tmp_path, check=True)
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True,
        capture_output=True, text=True).stdout.strip()
    target = tmp_path / paths[0]
    target.write_text("staged change\n", encoding="utf-8")
    subprocess.run(["git", "add", paths[0]], cwd=tmp_path, check=True)
    actual, untracked = _r5_git_changed_paths(tmp_path, base)
    assert actual == RUN005_R5_SOURCE_PATHS and not untracked
    _validate_r5_scope(actual, _r5_scope_document("PHASE_A", base), expected_base=base)
    subprocess.run(["git", "commit", "-qm", "phase A"], cwd=tmp_path, check=True)
    actual, untracked = _r5_git_changed_paths(tmp_path, base)
    assert actual == RUN005_R5_SOURCE_PATHS and not untracked
    _validate_r5_scope(actual, _r5_scope_document("PHASE_A", base), expected_base=base)
    (tmp_path / "unexpected.txt").write_text("untracked\n", encoding="utf-8")
    actual, untracked = _r5_git_changed_paths(tmp_path, base)
    with pytest.raises(AssertionError, match="RUN005_R5_EXACT_SCOPE_MISMATCH"):
        _validate_r5_scope(actual, _r5_scope_document("PHASE_A", base), untracked, base)


@pytest.mark.parametrize("fault", ["missing_governance", "extra", "historical", "phase", "base", "metadata", "freeze", "untracked"])
def test_run005_r3_scope_rejects_inexact_or_mismatched_phase(fault):
    document = _r3_scope_document("PHASE_B")
    actual = set(RUN005_R3_PHASE_B_PATHS)
    untracked = set()
    if fault == "missing_governance":
        actual.remove("docs/governance/PROJECT_PROGRESS_LEDGER.md")
    elif fault == "extra":
        actual.add("unapproved.py")
    elif fault == "historical":
        actual.add("/home/hazan/step07_runtime_evidence/STEP07_NAV2_BASELINE_RUN_005_ATTEMPT_002_INVOCATION_019/run_record.json")
    elif fault == "phase":
        document = _r3_scope_document("PHASE_A")
    elif fault == "base":
        document["current_candidate_base_commit"] = RUN005_R1R2_BASE
    elif fault == "metadata":
        document["current_corrective_scope"]["paths"].pop()
    elif fault == "freeze":
        document["SOURCE_FREEZE"] = "FALSE"
    else:
        untracked.add("log/logger_all.log")
    with pytest.raises(AssertionError, match="RUN005_R3_"):
        _validate_r3_scope(actual, document, untracked)


def _audit21_scope_fixture(phase):
    paths = RUN005_AUDIT21_PHASE_SCOPES[phase]
    return {"current_candidate_base_commit": RUN005_AUDIT21_BASE,
        "SOURCE_FREEZE": "FALSE" if phase == "PHASE_A" else "TRUE",
        "current_corrective_scope": {"base_commit": RUN005_AUDIT21_BASE,
            "phase": phase, "path_count": len(paths), "paths": sorted(paths)}}


def _validate_audit21_scope(actual, document, untracked=()):
    scope = document.get("current_corrective_scope", {})
    phase = scope.get("phase")
    if (phase not in RUN005_AUDIT21_PHASE_SCOPES
            or document.get("current_candidate_base_commit") != RUN005_AUDIT21_BASE
            or scope.get("base_commit") != RUN005_AUDIT21_BASE):
        raise AssertionError("AUDIT21_PHASE_OR_BASE_INVALID")
    expected = RUN005_AUDIT21_PHASE_SCOPES[phase]
    if scope.get("paths") != sorted(expected) or scope.get("path_count") != len(expected):
        raise AssertionError("AUDIT21_METADATA_SCOPE_MISMATCH")
    if set(actual) != expected or untracked:
        raise AssertionError(f"AUDIT21_EXACT_SCOPE_MISMATCH:{sorted(actual)}:{untracked}")
    if phase != "PHASE_A" and document.get("SOURCE_FREEZE") != "TRUE":
        raise AssertionError("AUDIT21_SOURCE_FREEZE_INVALID")
    return phase


def _audit21_changed_paths(document):
    if document.get("current_candidate_base_commit") != RUN005_AUDIT21_BASE:
        # Trạng thái đầu Phase A duy nhất: metadata chưa đổi từ exact parent.
        parent = json.loads(subprocess.run(
            ["git", "show", f"{RUN005_AUDIT21_BASE}:{RUN005_INVOCATION_019_GUARD.relative_to(ROOT)}"],
            cwd=ROOT, check=True, capture_output=True, text=True).stdout)
        if document != parent:
            raise AssertionError("AUDIT21_INITIAL_METADATA_NOT_EXACT_PARENT")
        document = _audit21_scope_fixture("PHASE_A")
    actual = set(subprocess.run(["git", "diff", "--name-only", RUN005_AUDIT21_BASE],
        cwd=ROOT, check=True, capture_output=True, text=True).stdout.splitlines())
    untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"],
        cwd=ROOT, check=True, capture_output=True, text=True).stdout.splitlines()
    _validate_audit21_scope(actual, document, untracked)
    return actual


def _validate_invocation019_phase_scope(actual, document, untracked=()):
    """Đối chiếu diff từ base với phase được metadata khai báo, không dùng dirty."""
    scope = document.get("current_corrective_scope", {})
    phase = scope.get("phase")
    # Metadata Phase B chưa delivery trước corrective này ghi phase bằng key
    # có tên rõ ràng trong scope_chain. Chỉ hỗ trợ đúng biểu diễn cũ đó.
    if phase is None and document.get("scope_chain", {}).get(
            "run005_invocation_019_output_probe_phase_b_actual_scope") == 10:
        phase = "PHASE_B"
    if phase not in RUN005_INVOCATION_019_PHASE_SCOPES:
        raise AssertionError("INVOCATION019_METADATA_PHASE_INVALID")
    expected = RUN005_INVOCATION_019_PHASE_SCOPES[phase]
    if (scope.get("base_commit") != RUN005_INVOCATION_019_BASE
            or document.get("current_candidate_base_commit") != RUN005_INVOCATION_019_BASE):
        raise AssertionError("INVOCATION019_METADATA_BASE_MISMATCH")
    if scope.get("paths") != sorted(expected) or scope.get("path_count") != len(expected):
        raise AssertionError(f"INVOCATION019_METADATA_SCOPE_MISMATCH:{phase}")
    if phase != "PHASE_A" and document.get("SOURCE_FREEZE") != "TRUE":
        raise AssertionError("INVOCATION019_SOURCE_FREEZE_NOT_PROVEN")
    if set(actual) != expected:
        raise AssertionError(f"INVOCATION019_EXACT_SCOPE_MISMATCH:{phase}:{sorted(actual)}")
    if untracked:
        raise AssertionError(f"INVOCATION019_UNTRACKED_PATHS:{sorted(untracked)}")
    return phase


def _invocation019_changed_paths(document):
    # Diff từ base gồm cả thay đổi đã commit, staged và unstaged. Bởi vậy cùng
    # contract dùng được trước commit, sau commit sạch và khi index đang dirty.
    actual = set(subprocess.run(
        ["git", "diff", "--name-only", RUN005_INVOCATION_019_BASE], cwd=ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.splitlines())
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    _validate_invocation019_phase_scope(actual, document, untracked)
    return actual

def test_run005_qos_trace_actual_scope_and_allowlist_are_distinct_and_exact():
    assert len(RUN005_QOS_TRACE_PHASE_A_PATHS) == 9
    assert len(RUN005_QOS_TRACE_PHASE_A5_PATHS) == 13
    assert len(RUN005_QOS_TRACE_PATHS) == 16
    assert len(RUN005_QOS_TRACE_AUTHORIZED_ALLOWLIST) == 17
    assert RUN005_QOS_TRACE_AUTHORIZED_ALLOWLIST - RUN005_QOS_TRACE_PATHS == {
        "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
    }


def _candidate_changed_paths():
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    parent = subprocess.run(
        ["git", "rev-parse", "HEAD^"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT,
        check=True, capture_output=True, text=True,
    ).stdout
    dirty = bool(status.strip())
    if head == RUN005_TEMPORAL_L2_BASE or parent == RUN005_TEMPORAL_L2_BASE:
        actual, untracked = _temporal_l2_git_changed_paths()
        document = _temporal_l2_current_scope_document(actual)
        _validate_temporal_l2_scope(actual, document, untracked)
        return actual, dirty
    if head == RUN005_INVOCATION_022_BASE or parent == RUN005_INVOCATION_022_BASE:
        actual, untracked = _invocation022_git_changed_paths()
        document = _invocation022_current_scope_document(actual)
        _validate_invocation022_scope(actual, document, untracked)
        return actual, dirty
    if head == RUN005_INVOCATION_021_BASE or parent == RUN005_INVOCATION_021_BASE:
        actual, untracked = _invocation021_git_changed_paths()
        document = _invocation021_current_scope_document(actual)
        _validate_invocation021_scope(actual, document, untracked)
        return actual, dirty
    if head == RUN005_INVOCATION_020_BASE or parent == RUN005_INVOCATION_020_BASE:
        actual, untracked = _invocation020_git_changed_paths()
        document = _invocation020_current_scope_document(actual)
        _validate_invocation020_scope(actual, document, untracked)
        return actual, dirty
    if head == RUN005_R5_BASE or parent == RUN005_R5_BASE:
        document = _r5_current_scope_document()
        actual, untracked = _r5_git_changed_paths()
        _validate_r5_scope(actual, document, untracked)
        return actual, dirty
    if head == RUN005_R3_BASE or parent == RUN005_R3_BASE:
        # R3/R4 scope is checked only as the immutable committed endpoint.
        actual = set(subprocess.run(["git", "diff", "--name-only",
            f"{RUN005_R3_BASE}..{RUN005_R3_COMMIT}"], cwd=ROOT,
            check=True, capture_output=True, text=True).stdout.splitlines())
        if actual != RUN005_R3_PHASE_B_PATHS:
            raise AssertionError("RUN005_R3_HISTORICAL_SCOPE_MISMATCH")
        return actual, dirty
    if head == RUN005_R1R2_BASE or parent == RUN005_R1R2_BASE:
        document = _r1r2_current_scope_document()
        actual, untracked = _r1r2_git_changed_paths()
        _validate_r1r2_scope(actual, document, untracked)
        return actual, dirty
    if head == RUN005_AUDIT21_BASE or parent == RUN005_AUDIT21_BASE:
        return _audit21_changed_paths(_load_json(RUN005_INVOCATION_019_GUARD)), dirty
    if head == RUN005_INVOCATION_019_BASE or parent == RUN005_INVOCATION_019_BASE:
        return _invocation019_changed_paths(_load_json(RUN005_INVOCATION_019_GUARD)), dirty
    if head == RUN005_INVOCATION_017_BASE or parent == RUN005_INVOCATION_017_BASE:
        changed = set(subprocess.run(
            ["git", "diff", "--name-only", RUN005_INVOCATION_017_BASE], cwd=ROOT,
            check=True, capture_output=True, text=True,
        ).stdout.splitlines())
        if changed not in RUN005_INVOCATION_017_VALID_PHASE_SCOPES:
            raise AssertionError(
                f"Run005 Invocation_017 candidate phase scope is not exact: {sorted(changed)}")
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT,
            check=True, capture_output=True, text=True,
        ).stdout.splitlines()
        if not set(untracked) <= changed:
            raise AssertionError(f"Invocation_017 untracked paths outside exact phase scope: {untracked}")
        return changed, head == RUN005_INVOCATION_017_BASE

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    parent = subprocess.run(
        ["git", "rev-parse", "HEAD^"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip() if not dirty else None
    if head == RUN005_LIFECYCLE_QOS_BASE or parent == RUN005_LIFECYCLE_QOS_BASE:
        allowed = (RUN005_LIFECYCLE_QOS_PHASE_A_PATHS,
                   RUN005_LIFECYCLE_QOS_PHASE_A5_PATHS,
                   RUN005_LIFECYCLE_QOS_RECONCILED_PATHS,
                   RUN005_LIFECYCLE_QOS_AUTHORIZED_PATHS)
        if dirty:
            changed = {line[3:] for line in status.splitlines() if len(line) >= 4}
            if changed not in allowed:
                raise AssertionError(f"Run005 lifecycle QoS corrective scope is not exact: {sorted(changed)}")
        elif parent == RUN005_LIFECYCLE_QOS_BASE:
            changed = set(subprocess.run(["git", "diff", "--name-only", "HEAD^", "HEAD"],
                cwd=ROOT, check=True, capture_output=True, text=True).stdout.splitlines())
            assert changed in allowed
        else:
            changed = set()
        untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"],
            cwd=ROOT, check=True, capture_output=True, text=True).stdout.splitlines()
        assert set(untracked) <= changed
        return changed, dirty
    if head == RUN005_COLLECTOR_VERDICT_BASE or parent == RUN005_COLLECTOR_VERDICT_BASE:
        if dirty:
            changed = {line[3:] for line in status.splitlines() if len(line) >= 4}
            allowed = (RUN005_COLLECTOR_VERDICT_PHASE_A_PATHS,
                       RUN005_COLLECTOR_VERDICT_PHASE_A5_PATHS,
                       RUN005_COLLECTOR_VERDICT_RECONCILED_PATHS,
                       RUN005_COLLECTOR_VERDICT_AUTHORIZED_PATHS)
            if changed not in allowed:
                raise AssertionError(f"Run005 collector verdict corrective scope is not exact: {sorted(changed)}")
        elif parent == RUN005_COLLECTOR_VERDICT_BASE:
            changed = set(subprocess.run(["git", "diff", "--name-only", "HEAD^", "HEAD"],
                cwd=ROOT, check=True, capture_output=True, text=True).stdout.splitlines())
            assert changed in (RUN005_COLLECTOR_VERDICT_PHASE_A_PATHS,
                               RUN005_COLLECTOR_VERDICT_PHASE_A5_PATHS,
                               RUN005_COLLECTOR_VERDICT_RECONCILED_PATHS,
                               RUN005_COLLECTOR_VERDICT_AUTHORIZED_PATHS)
        else:
            changed = set()
        untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"],
            cwd=ROOT, check=True, capture_output=True, text=True).stdout.splitlines()
        assert set(untracked) <= changed
        return changed, dirty
    if head == RUN005_L1_REVIEW_BASE or parent == RUN005_L1_REVIEW_BASE:
        if dirty:
            changed = {line[3:] for line in status.splitlines() if len(line) >= 4}
            allowed = (RUN005_L1_PHASE_A_PATHS, RUN005_L1_RECONCILED_PATHS,
                       RUN005_L1_AUTHORIZED_PATHS)
            if changed not in allowed:
                raise AssertionError(f"Run005 L1 evidence collector corrective scope is not exact: {sorted(changed)}")
        elif parent == RUN005_L1_REVIEW_BASE:
            changed = set(subprocess.run(
                ["git", "diff", "--name-only", "HEAD^", "HEAD"], cwd=ROOT,
                check=True, capture_output=True, text=True,
            ).stdout.splitlines())
            assert changed in (RUN005_L1_PHASE_A_PATHS, RUN005_L1_RECONCILED_PATHS,
                               RUN005_L1_AUTHORIZED_PATHS)
        else:
            changed = set()
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT,
            check=True, capture_output=True, text=True,
        ).stdout.splitlines()
        assert set(untracked) <= changed
        assert not any(path.startswith(("build/", "install/", "log/", ".pytest_cache/"))
                       or "/__pycache__/" in path for path in untracked), untracked
        return changed, dirty
    if head == RUN005_QOS_TRACE_BASE or parent == RUN005_QOS_TRACE_BASE:
        if dirty:
            changed = {line[3:] for line in status.splitlines() if len(line) >= 4}
            if changed not in (RUN005_QOS_TRACE_PHASE_A_PATHS, RUN005_QOS_TRACE_PHASE_A5_PATHS, RUN005_QOS_TRACE_PATHS):
                raise AssertionError(f"Run005 QoS/trace corrective scope is not exact: {sorted(changed)}")
        elif parent == RUN005_QOS_TRACE_BASE:
            changed = set(subprocess.run(
                ["git", "diff", "--name-only", "HEAD^", "HEAD"], cwd=ROOT,
                check=True, capture_output=True, text=True,
            ).stdout.splitlines())
            assert changed in (RUN005_QOS_TRACE_PHASE_A_PATHS, RUN005_QOS_TRACE_PHASE_A5_PATHS, RUN005_QOS_TRACE_PATHS)
        else:
            changed = set()
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT,
            check=True, capture_output=True, text=True,
        ).stdout.splitlines()
        assert set(untracked) <= changed
        assert not any(path.startswith(("build/", "install/", "log/", ".pytest_cache/"))
                       or "/__pycache__/" in path for path in untracked), untracked
        return changed, dirty
    if head == RUN005_NAV2_HEIGHT_TEARDOWN_BASE or parent == RUN005_NAV2_HEIGHT_TEARDOWN_BASE:
        if dirty:
            changed = {line[3:] for line in status.splitlines() if len(line) >= 4}
            if changed not in (RUN005_NAV2_HEIGHT_TEARDOWN_PHASE_A_PATHS,
                               RUN005_NAV2_HEIGHT_TEARDOWN_PATHS):
                raise AssertionError(f"Run005 Nav2-height/teardown corrective scope is not exact: {sorted(changed)}")
        elif parent == RUN005_NAV2_HEIGHT_TEARDOWN_BASE:
            changed = set(subprocess.run(
                ["git", "diff", "--name-only", "HEAD^", "HEAD"], cwd=ROOT,
                check=True, capture_output=True, text=True,
            ).stdout.splitlines())
            assert changed == RUN005_NAV2_HEIGHT_TEARDOWN_PATHS
        else:
            changed = set()
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT,
            check=True, capture_output=True, text=True,
        ).stdout.splitlines()
        assert set(untracked) <= changed
        assert not any(path.startswith(("build/", "install/", "log/", ".pytest_cache/"))
                       or "/__pycache__/" in path for path in untracked), untracked
        return changed, dirty
    if head == RUN005_DEFAULT_ROUTE_BASE or parent == RUN005_DEFAULT_ROUTE_BASE:
        if dirty:
            changed = {line[3:] for line in status.splitlines() if len(line) >= 4}
            if changed not in (RUN005_DEFAULT_ROUTE_PHASE_A_PATHS, RUN005_DEFAULT_ROUTE_PATHS):
                raise AssertionError(f"Run005 default-route corrective scope is not exact: {sorted(changed)}")
        elif parent == RUN005_DEFAULT_ROUTE_BASE:
            changed = set(subprocess.run(
                ["git", "diff", "--name-only", "HEAD^", "HEAD"], cwd=ROOT,
                check=True, capture_output=True, text=True,
            ).stdout.splitlines())
            assert changed == RUN005_DEFAULT_ROUTE_PATHS
        else:
            changed = set()
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT,
            check=True, capture_output=True, text=True,
        ).stdout.splitlines()
        assert set(untracked) <= changed
        assert not any(path.startswith(("build/", "install/", "log/", ".pytest_cache/"))
                       or "/__pycache__/" in path for path in untracked), untracked
        return changed, dirty
    if head == RUN005_GZ_IP_GRACEFUL_BASE or parent == RUN005_GZ_IP_GRACEFUL_BASE:
        if dirty:
            changed = {line[3:] for line in status.splitlines() if len(line) >= 4}
            if changed not in (RUN005_GZ_IP_GRACEFUL_PHASE_A_PATHS, RUN005_GZ_IP_GRACEFUL_PATHS):
                raise AssertionError(f"Run005 GZ_IP/graceful candidate scope is not exact: {sorted(changed)}")
        elif parent == RUN005_GZ_IP_GRACEFUL_BASE:
            changed = set(subprocess.run(
                ["git", "diff", "--name-only", "HEAD^", "HEAD"], cwd=ROOT,
                check=True, capture_output=True, text=True,
            ).stdout.splitlines())
            assert changed == RUN005_GZ_IP_GRACEFUL_PATHS
        else:
            changed = set()
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT,
            check=True, capture_output=True, text=True,
        ).stdout.splitlines()
        assert set(untracked) <= changed
        assert not any(path.startswith(("build/", "install/", "log/", ".pytest_cache/"))
                       or "/__pycache__/" in path for path in untracked), untracked
        return changed, dirty
    if head == RUN005_VALIDATOR_CORRECTIVE_BASE or parent == RUN005_VALIDATOR_CORRECTIVE_BASE:
        if dirty:
            changed = {line[3:] for line in status.splitlines() if len(line) >= 4}
            if changed not in (RUN005_VALIDATOR_SOURCE_PATHS, RUN005_VALIDATOR_CORRECTIVE_PATHS):
                raise AssertionError(f"Run005 validator corrective path set is not exact: {sorted(changed)}")
        elif parent == RUN005_VALIDATOR_CORRECTIVE_BASE:
            changed = set(subprocess.run(
                ["git", "diff", "--name-only", "HEAD^", "HEAD"], cwd=ROOT,
                check=True, capture_output=True, text=True,
            ).stdout.splitlines())
            assert changed == RUN005_VALIDATOR_CORRECTIVE_PATHS
        else:
            changed = set()
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT,
            check=True, capture_output=True, text=True,
        ).stdout.splitlines()
        assert set(untracked) <= changed
        assert not any(path.startswith(("build/", "install/", "log/", ".pytest_cache/"))
                       or "/__pycache__/" in path for path in untracked), untracked
        return changed, dirty
    if dirty:
        assert subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
            capture_output=True, text=True,
        ).stdout.strip() == RUN005_COMPOSITE_BASE
        changed = {line[3:] for line in status.splitlines() if len(line) >= 4}
    else:
        assert subprocess.run(
            ["git", "rev-parse", "HEAD^"], cwd=ROOT, check=True,
            capture_output=True, text=True,
        ).stdout.strip() == RUN005_COMPOSITE_BASE
        changed = set(subprocess.run(
            ["git", "diff", "--name-only", "HEAD^", "HEAD"], cwd=ROOT,
            check=True, capture_output=True, text=True,
        ).stdout.splitlines())
    if changed not in RUN005_COMPOSITE_VALID_SCOPES:
        raise AssertionError(
            f"Run005 attempt_002 host transport corrective path set is not exact: {sorted(changed)}"
        )
    return changed, dirty


def _assert_run005_attempt002_historical_scope():
    historical = subprocess.run(
        ["git", "diff", "--name-only", f"{RUN005_ATTEMPT_001_COMMIT}..{RUN005_ATTEMPT_002_CORRECTIVE_BASE}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(historical) == RUN005_ATTEMPT_002_PATHS
    previous_corrective = subprocess.run(
        ["git", "diff", "--name-only", f"{RUN005_ATTEMPT_002_CORRECTIVE_BASE}..{RUN005_ATTEMPT_002_PREVIOUS_CORRECTIVE_COMMIT}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(previous_corrective) == RUN005_ATTEMPT_002_CORRECTIVE_PATHS
    output_precondition = subprocess.run(
        ["git", "diff", "--name-only",
         f"{RUN005_ATTEMPT_002_PREVIOUS_CORRECTIVE_COMMIT}..{RUN005_ATTEMPT_002_OUTPUT_PRECONDITION_COMMIT}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(output_precondition) == RUN005_ATTEMPT_002_OUTPUT_PRECONDITION_PATHS
    assert subprocess.run(
        ["git", "rev-parse", f"{RUN005_ATTEMPT_002_OUTPUT_PRECONDITION_COMMIT}^"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.strip() == RUN005_ATTEMPT_002_PREVIOUS_CORRECTIVE_COMMIT
    host_transport = subprocess.run(
        ["git", "diff", "--name-only",
         f"{RUN005_ATTEMPT_002_HOST_TRANSPORT_BASE}..{RUN005_ATTEMPT_002_TERMINAL_ROS_DISCOVERY_BASE}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(host_transport) == RUN005_ATTEMPT_002_HOST_TRANSPORT_PATHS
    assert subprocess.run(
        ["git", "rev-parse", f"{RUN005_ATTEMPT_002_TERMINAL_ROS_DISCOVERY_BASE}^"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.strip() == RUN005_ATTEMPT_002_HOST_TRANSPORT_BASE
    terminal_ros_discovery = subprocess.run(
        ["git", "diff", "--name-only",
         f"{RUN005_ATTEMPT_002_TERMINAL_ROS_DISCOVERY_BASE}..{RUN005_ATTEMPT_002_SIGTERM_HANDOFF_BASE}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(terminal_ros_discovery) == RUN005_ATTEMPT_002_TERMINAL_ROS_DISCOVERY_PATHS
    assert subprocess.run(
        ["git", "rev-parse", f"{RUN005_ATTEMPT_002_SIGTERM_HANDOFF_BASE}^"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.strip() == RUN005_ATTEMPT_002_TERMINAL_ROS_DISCOVERY_BASE
    guard_handoff = subprocess.run(
        ["git", "diff", "--name-only", f"{RUN005_ATTEMPT_002_SIGTERM_HANDOFF_BASE}..{RUN005_OWNERSHIP_BASE}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(guard_handoff) == RUN005_ATTEMPT_002_TERMINAL_ROS_DISCOVERY_PATHS
    assert subprocess.run(["git", "rev-parse", f"{RUN005_OWNERSHIP_BASE}^"],
                          cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip() == RUN005_ATTEMPT_002_SIGTERM_HANDOFF_BASE


def test_guard_ownership_corrective_remains_exact_historical_scope():
    paths = subprocess.run(["git", "diff", "--name-only", f"{RUN005_OWNERSHIP_BASE}..{RUN005_COMPOSITE_BASE}"],
                           cwd=ROOT, check=True, capture_output=True, text=True).stdout.splitlines()
    assert set(paths) == RUN005_OWNERSHIP_PATHS


def test_run005_invocation017_lineage_has_exact_phase_scopes():
    assert RUN005_INVOCATION_017_BASE == "31555b8ff2472811994907791f0d9b8d7f56498f"
    assert RUN005_INVOCATION_017_BASE != RUN005_COMPOSITE_BASE
    assert len(RUN005_INVOCATION_017_PHASE_A_SOURCE_PATHS) == 6
    assert RUN005_INVOCATION_017_PHASE_A_SOURCE_PATHS == {
        "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
        "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py",
        "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
        "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_gate_b_evidence_validator.py",
        "ros2_ws/src/step07_nav2_baseline_runtime_observer/test/test_step07_nav2_baseline_runtime_observer.cpp",
        "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    }
    assert RUN005_INVOCATION_017_PHASE_A5_PATHS == (
        RUN005_INVOCATION_017_PHASE_A_SOURCE_PATHS | {
            "artifacts/simulation/step07_nav2_baseline_campaign/approval_guards/STEP07_NAV2_BASELINE_RUN_005.json"})
    assert RUN005_INVOCATION_017_PHASE_B_RECONCILED_PATHS == (
        RUN005_INVOCATION_017_PHASE_A5_PATHS | {
            "docs/governance/decisions/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_DECISION.md",
            "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_L1_EVIDENCE.json",
            "docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN005_GUARD_MANIFEST.json",
            "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
            "docs/governance/PROJECT_EXECUTION_PLAN.md",
            "docs/governance/PROJECT_PROGRESS_LEDGER.md"})
    assert RUN005_INVOCATION_017_PHASE_A_SOURCE_PATHS < RUN005_INVOCATION_017_PHASE_A5_PATHS
    assert RUN005_INVOCATION_017_PHASE_A5_PATHS < RUN005_INVOCATION_017_PHASE_B_RECONCILED_PATHS
    assert len(RUN005_INVOCATION_017_AUTHORIZED_ALLOWLIST) == 17
    assert RUN005_INVOCATION_017_PHASE_B_RECONCILED_PATHS <= RUN005_INVOCATION_017_AUTHORIZED_ALLOWLIST
    assert RUN005_INVOCATION_017_AUTHORIZED_ALLOWLIST - RUN005_INVOCATION_017_PHASE_B_RECONCILED_PATHS == {
        "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
        "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py",
        "ros2_ws/src/mecanum_nav_rl/test/test_step07_gate_b_observer_node.py",
        "ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp",
    }
    # The immutable Invocation_017 closure is checked against its committed
    # endpoint; current candidates on later bases are validated separately.
    historical = set(subprocess.run(
        ["git", "diff", "--name-only",
         f"{RUN005_INVOCATION_017_BASE}..711c06d146e596b4ec74b8a3d546bcf71fcba5ef"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines())
    assert historical == RUN005_INVOCATION_017_PHASE_B_RECONCILED_PATHS
    assert subprocess.run(
        ["git", "rev-parse", "711c06d146e596b4ec74b8a3d546bcf71fcba5ef^"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.strip() == RUN005_INVOCATION_017_BASE
    changed, _base_worktree = _candidate_changed_paths()
    if subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                      capture_output=True, text=True).stdout.strip() == RUN005_INVOCATION_017_BASE:
        assert changed in RUN005_INVOCATION_017_VALID_PHASE_SCOPES


def test_run005_invocation019_output_probe_lineage_has_exact_phase_scopes():
    assert RUN005_INVOCATION_019_BASE == "9a92b94b6f0d0d9a0f4ebdc8133ebecb34e6129f"
    assert RUN005_INVOCATION_019_PHASE_A_PATHS == {
        "artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py",
        "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_run_step07_nav2_baseline_run005.py",
        "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
    }
    assert RUN005_INVOCATION_019_PHASE_A_PATHS < RUN005_INVOCATION_019_PHASE_A5_PATHS
    assert RUN005_INVOCATION_019_PHASE_A5_PATHS < RUN005_INVOCATION_019_PHASE_B_PATHS
    assert len(RUN005_INVOCATION_019_PHASE_A_PATHS) == 3
    assert len(RUN005_INVOCATION_019_PHASE_A5_PATHS) == 6
    assert len(RUN005_INVOCATION_019_PHASE_B_PATHS) == 10
    historical = set(subprocess.run(["git", "diff", "--name-only",
        f"{RUN005_INVOCATION_019_BASE}..{RUN005_AUDIT21_BASE}"], cwd=ROOT,
        check=True, capture_output=True, text=True).stdout.splitlines())
    assert historical == RUN005_INVOCATION_019_PHASE_B_PATHS


def test_run005_invocation020_current_lineage_has_exact_phase_scopes():
    assert RUN005_INVOCATION_020_BASE == "d123c708bb3b0fd80c8096daa9836da50440db85"
    assert subprocess.run(["git", "rev-parse", f"{RUN005_INVOCATION_020_BASE}^"], cwd=ROOT,
        check=True, capture_output=True, text=True).stdout.strip() == "dcc36a39f410651f5e7a142fa52eeda5daa50012"
    assert RUN005_INVOCATION_020_PHASE_A_PATHS < RUN005_INVOCATION_020_PHASE_A5_PATHS
    assert RUN005_INVOCATION_020_PHASE_A5_PATHS < RUN005_INVOCATION_020_PHASE_B_PATHS
    assert len(RUN005_INVOCATION_020_PHASE_A_PATHS) == 7
    assert len(RUN005_INVOCATION_020_PHASE_A5_PATHS) == 10
    assert len(RUN005_INVOCATION_020_PHASE_B_PATHS) == 14
    assert len(RUN005_INVOCATION_020_AUTHORIZED_PATHS) == 17
    assert RUN005_INVOCATION_020_PHASE_B_PATHS <= RUN005_INVOCATION_020_AUTHORIZED_PATHS
    historical = set(subprocess.run(["git", "diff", "--name-only",
        f"{RUN005_INVOCATION_020_BASE}^..{RUN005_INVOCATION_020_BASE}"], cwd=ROOT,
        check=True, capture_output=True, text=True).stdout.splitlines())
    assert historical == RUN005_R5_PHASE_B_PATHS
    assert subprocess.run(["git", "rev-parse", f"{RUN005_INVOCATION_020_COMMIT}^"], cwd=ROOT,
        check=True, capture_output=True, text=True).stdout.strip() == RUN005_INVOCATION_020_BASE
    delivered = set(subprocess.run(["git", "diff", "--name-only",
        f"{RUN005_INVOCATION_020_BASE}..{RUN005_INVOCATION_020_COMMIT}"], cwd=ROOT,
        check=True, capture_output=True, text=True).stdout.splitlines())
    assert delivered == RUN005_INVOCATION_020_PHASE_B_PATHS


@pytest.mark.parametrize("phase", ["PHASE_A", "PHASE_A5", "PHASE_B"])
def test_invocation020_declared_phase_accepts_only_exact_scope(phase):
    document = _invocation020_scope_document(phase)
    assert _validate_invocation020_scope(
        RUN005_INVOCATION_020_PHASE_SCOPES[phase], document) == phase


@pytest.mark.parametrize("fault", ["missing", "extra", "phase", "base", "metadata", "allowlist", "untracked"])
def test_invocation020_phase_metadata_rejects_scope_and_lineage_mismatch(fault):
    document = _invocation020_scope_document("PHASE_B")
    actual = set(RUN005_INVOCATION_020_PHASE_B_PATHS)
    untracked = set()
    if fault == "missing":
        actual.remove("docs/governance/PROJECT_PROGRESS_LEDGER.md")
    elif fault == "extra":
        actual.add("unexpected.py")
    elif fault == "phase":
        document["current_corrective_scope"]["phase"] = "PHASE_A"
    elif fault == "base":
        document["corrective_commit_parent"] = RUN005_R5_BASE
    elif fault == "metadata":
        document["current_corrective_scope"]["paths"].pop()
    elif fault == "allowlist":
        document["authorized_allowlist"]["paths"].append("historical.json")
    else:
        untracked.add("untracked.txt")
    with pytest.raises(AssertionError, match="INVOCATION020_"):
        _validate_invocation020_scope(actual, document, untracked)


def test_run005_invocation021_historical_delivery_keeps_exact_phase_scope():
    assert RUN005_INVOCATION_021_BASE == "dee7d5dec565e51252f6a851c5959f07b8b8b512"
    assert subprocess.run(["git", "rev-parse", f"{RUN005_INVOCATION_021_BASE}^"], cwd=ROOT,
        check=True, capture_output=True, text=True).stdout.strip() == "d123c708bb3b0fd80c8096daa9836da50440db85"
    assert RUN005_INVOCATION_021_PHASE_A_PATHS < RUN005_INVOCATION_021_PHASE_A5_PATHS
    assert RUN005_INVOCATION_021_PHASE_A5_PATHS < RUN005_INVOCATION_021_PHASE_B_PATHS
    assert len(RUN005_INVOCATION_021_PHASE_A_PATHS) == 4
    assert len(RUN005_INVOCATION_021_PHASE_A5_PATHS) == 7
    assert len(RUN005_INVOCATION_021_PHASE_B_PATHS) == 11
    assert len(RUN005_INVOCATION_021_AUTHORIZED_PATHS) == 12
    prior = set(subprocess.run(["git", "diff", "--name-only",
        "d123c708bb3b0fd80c8096daa9836da50440db85..dee7d5dec565e51252f6a851c5959f07b8b8b512"],
        cwd=ROOT, check=True, capture_output=True, text=True).stdout.splitlines())
    assert prior == RUN005_INVOCATION_020_PHASE_B_PATHS
    assert subprocess.run(["git", "rev-parse", f"{RUN005_INVOCATION_021_COMMIT}^"], cwd=ROOT,
        check=True, capture_output=True, text=True).stdout.strip() == RUN005_INVOCATION_021_BASE
    delivered = set(subprocess.run(["git", "diff", "--name-only",
        f"{RUN005_INVOCATION_021_BASE}..{RUN005_INVOCATION_021_COMMIT}"], cwd=ROOT,
        check=True, capture_output=True, text=True).stdout.splitlines())
    assert delivered == RUN005_INVOCATION_021_PHASE_B_PATHS


def test_run005_invocation022_current_lineage_has_exact_phase_scopes():
    assert RUN005_INVOCATION_022_BASE == "50fd738de91283c2c879f58fa6286ce5e15fc4bf"
    assert subprocess.run(["git", "rev-parse", f"{RUN005_INVOCATION_022_BASE}^"], cwd=ROOT,
        check=True, capture_output=True, text=True).stdout.strip() == "dee7d5dec565e51252f6a851c5959f07b8b8b512"
    assert len(RUN005_INVOCATION_022_PHASE_A_PATHS) == 4
    assert len(RUN005_INVOCATION_022_PHASE_A5_PATHS) == 7
    assert len(RUN005_INVOCATION_022_PHASE_B_PATHS) == 11
    assert len(RUN005_INVOCATION_022_AUTHORIZED_PATHS) == 12
    historical = set(subprocess.run(["git", "diff", "--name-only",
        f"{RUN005_INVOCATION_021_BASE}..{RUN005_INVOCATION_021_COMMIT}"], cwd=ROOT,
        check=True, capture_output=True, text=True).stdout.splitlines())
    assert historical == RUN005_INVOCATION_021_PHASE_B_PATHS
    # Invocation_022 is historical after the L2 corrective base; its exact
    # delivered endpoint is checked above. Current dirty/committed scope is
    # validated by the separate temporal L2 lineage test.


@pytest.mark.parametrize("phase", ["PHASE_A", "PHASE_A5", "PHASE_B"])
def test_invocation022_declared_phase_accepts_only_exact_scope(phase):
    assert _validate_invocation022_scope(
        RUN005_INVOCATION_022_PHASE_SCOPES[phase], _invocation022_scope_document(phase)) == phase


@pytest.mark.parametrize("fault", ["missing", "extra", "wrong_phase", "wrong_base",
                                    "scope_metadata", "allowlist", "untracked"])
def test_invocation022_phase_metadata_rejects_inexact_scope_and_lineage(fault):
    document = _invocation022_scope_document("PHASE_B")
    actual = set(RUN005_INVOCATION_022_PHASE_B_PATHS)
    untracked = set()
    if fault == "missing":
        actual.remove("docs/governance/PROJECT_PROGRESS_LEDGER.md")
    elif fault == "extra":
        actual.add("unexpected.py")
    elif fault == "wrong_phase":
        document["current_corrective_scope"]["phase"] = "PHASE_A"
    elif fault == "wrong_base":
        document["corrective_commit_parent"] = RUN005_INVOCATION_021_BASE
    elif fault == "scope_metadata":
        document["current_corrective_scope"]["paths"].pop()
    elif fault == "allowlist":
        document["authorized_allowlist"]["paths"].pop()
    else:
        untracked.add("scratch.txt")
    with pytest.raises(AssertionError, match="INVOCATION022_"):
        _validate_invocation022_scope(actual, document, untracked)


def test_run005_temporal_l2_current_lineage_has_exact_phase_scope():
    assert subprocess.run(["git", "cat-file", "-e",
        f"{RUN005_TEMPORAL_L2_BASE}^{{commit}}"], cwd=ROOT,
        capture_output=True, text=True).returncode == 0
    ancestry = subprocess.run(["git", "merge-base", "--is-ancestor",
        RUN005_TEMPORAL_L2_BASE, "HEAD"], cwd=ROOT, capture_output=True, text=True)
    assert ancestry.returncode == 0
    assert len(RUN005_TEMPORAL_L2_PHASE_A_PATHS) == 26
    assert len(RUN005_TEMPORAL_L2_PHASE_A5_PATHS) == 29
    assert len(RUN005_TEMPORAL_L2_PHASE_B_PATHS) == 33
    assert len(RUN005_TEMPORAL_L2_AUTHORIZED_PATHS) == 37
    actual, untracked = _temporal_l2_git_changed_paths()
    document = _temporal_l2_current_scope_document(actual)
    phase = _validate_temporal_l2_scope(actual, document, untracked)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
        check=True, capture_output=True, text=True).stdout.strip()
    parent = subprocess.run(["git", "rev-parse", "HEAD^"], cwd=ROOT,
        check=True, capture_output=True, text=True).stdout.strip()
    if head == RUN005_TEMPORAL_L2_BASE:
        if actual == RUN005_TEMPORAL_L2_PHASE_B_PATHS:
            assert phase == "PHASE_B"
        else:
            assert phase == ("PHASE_A5" if actual == RUN005_TEMPORAL_L2_PHASE_A5_PATHS else "PHASE_A")
    elif parent == RUN005_TEMPORAL_L2_BASE:
        assert phase == "PHASE_B"
    else:
        assert phase in RUN005_TEMPORAL_L2_PHASE_SCOPES


@pytest.mark.parametrize("phase", ["PHASE_A", "PHASE_A5", "PHASE_B"])
def test_run005_temporal_l2_phase_metadata_accepts_only_its_exact_set(phase):
    assert _validate_temporal_l2_scope(
        RUN005_TEMPORAL_L2_PHASE_SCOPES[phase], _temporal_l2_scope_document(phase)) == phase


@pytest.mark.parametrize("fault", ["missing", "extra", "wrong_parent", "wrong_phase",
                                    "metadata", "allowlist", "untracked"])
def test_run005_temporal_l2_scope_rejects_lineage_and_set_mismatches(fault):
    document = _temporal_l2_scope_document("PHASE_B")
    actual = set(RUN005_TEMPORAL_L2_PHASE_B_PATHS)
    untracked = set()
    if fault == "missing":
        actual.remove("docs/governance/PROJECT_PROGRESS_LEDGER.md")
    elif fault == "extra":
        actual.add("unexpected.txt")
    elif fault == "wrong_parent":
        document["corrective_commit_parent"] = "71713d0a79b006580510169924732d6791c87858"
    elif fault == "wrong_phase":
        document["current_corrective_scope"]["phase"] = "PHASE_A"
    elif fault == "metadata":
        document["current_corrective_scope"]["paths"].pop()
    elif fault == "allowlist":
        document["authorized_allowlist"]["paths"].append("historical/Invocation_021")
    else:
        untracked.add("scratch.tmp")
    with pytest.raises(AssertionError, match="RUN005_TEMPORAL_L2_"):
        _validate_temporal_l2_scope(actual, document, untracked)


@pytest.mark.parametrize("phase", ["PHASE_A", "PHASE_A5", "PHASE_B"])
def test_invocation021_declared_phase_accepts_only_exact_scope(phase):
    assert _validate_invocation021_scope(
        RUN005_INVOCATION_021_PHASE_SCOPES[phase], _invocation021_scope_document(phase)) == phase


@pytest.mark.parametrize("fault", ["missing", "extra", "wrong_phase", "wrong_base",
                                    "scope_metadata", "allowlist", "untracked"])
def test_invocation021_phase_metadata_rejects_inexact_scope_and_lineage(fault):
    document = _invocation021_scope_document("PHASE_B")
    actual = set(RUN005_INVOCATION_021_PHASE_B_PATHS)
    untracked = set()
    if fault == "missing":
        actual.remove("docs/governance/PROJECT_PROGRESS_LEDGER.md")
    elif fault == "extra":
        actual.add("unexpected.py")
    elif fault == "wrong_phase":
        document["current_corrective_scope"]["phase"] = "PHASE_A"
    elif fault == "wrong_base":
        document["corrective_commit_parent"] = "d123c708bb3b0fd80c8096daa9836da50440db85"
    elif fault == "scope_metadata":
        document["current_corrective_scope"]["paths"].pop()
    elif fault == "allowlist":
        document["authorized_allowlist"]["paths"].pop()
    else:
        untracked.add("scratch.txt")
    with pytest.raises(AssertionError, match="INVOCATION021_"):
        _validate_invocation021_scope(actual, document, untracked)


def _invocation019_scope_fixture(phase):
    paths = RUN005_INVOCATION_019_PHASE_SCOPES[phase]
    return {"current_candidate_base_commit": RUN005_INVOCATION_019_BASE,
            "SOURCE_FREEZE": "FALSE" if phase == "PHASE_A" else "TRUE",
            "current_corrective_scope": {
                "base_commit": RUN005_INVOCATION_019_BASE, "phase": phase,
                "path_count": len(paths), "paths": sorted(paths)}}


@pytest.mark.parametrize("phase", ["PHASE_A", "PHASE_A5", "PHASE_B"])
def test_invocation019_each_declared_phase_accepts_only_its_exact_scope(phase):
    document = _invocation019_scope_fixture(phase)
    assert _validate_invocation019_phase_scope(
        RUN005_INVOCATION_019_PHASE_SCOPES[phase], document) == phase


@pytest.mark.parametrize("change", ["missing_governance", "extra_path", "historical", "wrong_phase"])
def test_invocation019_phase_b_rejects_missing_extra_historical_and_phase_mismatch(change):
    document = _invocation019_scope_fixture("PHASE_B")
    actual = set(RUN005_INVOCATION_019_PHASE_B_PATHS)
    if change == "missing_governance":
        actual.remove("docs/governance/PROJECT_PROGRESS_LEDGER.md")
    elif change == "extra_path":
        actual.add("unapproved.py")
    elif change == "historical":
        actual.add("artifacts/simulation/STEP07_NAV2_BASELINE_RUN_005_ATTEMPT_002_INVOCATION_019/run_record.json")
    else:
        document = _invocation019_scope_fixture("PHASE_A")
    with pytest.raises(AssertionError, match="INVOCATION019_EXACT_SCOPE_MISMATCH"):
        _validate_invocation019_phase_scope(actual, document)


@pytest.mark.parametrize("field", ["phase", "base", "paths", "freeze", "untracked"])
def test_invocation019_rejects_inconsistent_metadata_and_untracked_paths(field):
    document = _invocation019_scope_fixture("PHASE_B")
    untracked = []
    if field == "phase":
        document["current_corrective_scope"]["phase"] = "PHASE_A"
    elif field == "base":
        document["current_corrective_scope"]["base_commit"] = RUN005_COMPOSITE_BASE
    elif field == "paths":
        document["current_corrective_scope"]["paths"].append("unapproved.py")
    elif field == "freeze":
        document["SOURCE_FREEZE"] = "FALSE"
    else:
        untracked = ["log/logger_all.log"]
    with pytest.raises(AssertionError, match="INVOCATION019_"):
        _validate_invocation019_phase_scope(RUN005_INVOCATION_019_PHASE_B_PATHS, document, untracked)


def test_invocation019_diff_uses_fixed_base_before_and_after_commit(monkeypatch):
    from types import SimpleNamespace
    commands = []
    stage = {}
    def git(command, **kwargs):
        commands.append(command)
        if command == ["git", "rev-parse", "HEAD"]:
            return SimpleNamespace(stdout=stage["head"])
        if command == ["git", "rev-parse", "HEAD^"]:
            return SimpleNamespace(stdout=stage["parent"])
        if command == ["git", "status", "--porcelain", "--untracked-files=all"]:
            return SimpleNamespace(stdout=stage["status"])
        if command == ["git", "diff", "--name-only", RUN005_INVOCATION_019_BASE]:
            return SimpleNamespace(stdout="\n".join(sorted(RUN005_INVOCATION_019_PHASE_B_PATHS)))
        assert command == ["git", "ls-files", "--others", "--exclude-standard"]
        return SimpleNamespace(stdout="")
    monkeypatch.setattr(subprocess, "run", git)
    monkeypatch.setitem(globals(), "_load_json",
                        lambda _path: _invocation019_scope_fixture("PHASE_B"))
    for head, parent, status in (
        (RUN005_INVOCATION_019_BASE, "711c06d146e596b4ec74b8a3d546bcf71fcba5ef", " M runner.py\n"),
        ("a" * 40, RUN005_INVOCATION_019_BASE, ""),
        ("a" * 40, RUN005_INVOCATION_019_BASE, " M runner.py\n"),
    ):
        stage.update(head=head, parent=parent, status=status)
        changed, dirty = _candidate_changed_paths()
        assert changed == RUN005_INVOCATION_019_PHASE_B_PATHS
        assert dirty is bool(status)
    assert commands.count(["git", "diff", "--name-only", RUN005_INVOCATION_019_BASE]) == 3


@pytest.mark.parametrize("raw", [b'{"v":NaN}', b'{"v":Infinity}', b'{"v":-Infinity}',
    b'{"v":1,"v":2}', b'\xef\xbb\xbf{"v":1}', b'{"v":1}\n', b'{"z":1,"a":2}'])
def test_scope_json_loader_rejects_nonfinite_duplicate_bom_newline_and_noncanonical(tmp_path, raw):
    path = tmp_path / "scope.json"
    path.write_bytes(raw)
    with pytest.raises((AssertionError, ValueError)):
        _load_json(path)


def test_current_step07_campaign_scope_chain_is_exact_and_historical_wp06_is_not_relaxed():
    changed, _dirty = _candidate_changed_paths()
    _assert_run005_attempt002_historical_scope()
    attempt001 = subprocess.run(
        ["git", "diff", "--name-only", f"{RUN005_ATTEMPT_001_BASE}..{RUN005_ATTEMPT_001_COMMIT}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(attempt001) == RUN005_ATTEMPT_001_PATHS
    assert subprocess.run(
        ["git", "rev-parse", f"{RUN005_ATTEMPT_001_COMMIT}^"], cwd=ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.strip() == RUN005_ATTEMPT_001_BASE
    original_run004 = subprocess.run(
        ["git", "diff", "--name-only", f"{RUN004_BASE}..{RUN004_CORRECTIVE_BASE}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(original_run004) == RUN004_CORRECTIVE_PATHS
    run004_host_diff = subprocess.run(
        ["git", "diff", "--name-only", f"{RUN004_CORRECTIVE_BASE}..{RUN004_HOST_CORRECTIVE_COMMIT}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(run004_host_diff) == RUN004_HOST_CORRECTIVE_PATHS
    assert subprocess.run(
        ["git", "rev-parse", f"{RUN004_HOST_CORRECTIVE_COMMIT}^"], cwd=ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.strip() == RUN004_CORRECTIVE_BASE
    assert changed in RUN005_COMPOSITE_VALID_SCOPES or changed in (
        RUN005_LIFECYCLE_QOS_PHASE_A_PATHS,
        RUN005_LIFECYCLE_QOS_PHASE_A5_PATHS,
        RUN005_LIFECYCLE_QOS_RECONCILED_PATHS,
        RUN005_LIFECYCLE_QOS_AUTHORIZED_PATHS,
        RUN005_L1_RECONCILED_PATHS,
        RUN005_COLLECTOR_VERDICT_PHASE_A_PATHS,
        RUN005_COLLECTOR_VERDICT_PHASE_A5_PATHS,
        RUN005_COLLECTOR_VERDICT_RECONCILED_PATHS,
        RUN005_COLLECTOR_VERDICT_AUTHORIZED_PATHS,
        RUN005_VALIDATOR_SOURCE_PATHS, RUN005_VALIDATOR_CORRECTIVE_PATHS,
        RUN005_GZ_IP_GRACEFUL_PHASE_A_PATHS, RUN005_GZ_IP_GRACEFUL_PATHS,
        RUN005_DEFAULT_ROUTE_PHASE_A_PATHS, RUN005_DEFAULT_ROUTE_PATHS,
        RUN005_NAV2_HEIGHT_TEARDOWN_PHASE_A_PATHS, RUN005_NAV2_HEIGHT_TEARDOWN_PATHS,
        RUN005_QOS_TRACE_PHASE_A_PATHS, RUN005_QOS_TRACE_PHASE_A5_PATHS, RUN005_QOS_TRACE_PATHS,
        *RUN005_INVOCATION_017_VALID_PHASE_SCOPES,
        RUN005_INVOCATION_019_PHASE_A_PATHS,
        RUN005_INVOCATION_019_PHASE_A5_PATHS,
        RUN005_INVOCATION_019_PHASE_B_PATHS,
        *RUN005_AUDIT21_PHASE_SCOPES.values(), *RUN005_R1R2_PHASE_SCOPES.values(),
        *RUN005_R3_PHASE_SCOPES.values(), *RUN005_R5_PHASE_SCOPES.values(),
        *RUN005_INVOCATION_020_PHASE_SCOPES.values(),
        *RUN005_INVOCATION_021_PHASE_SCOPES.values(),
        *RUN005_INVOCATION_022_PHASE_SCOPES.values(),
        *RUN005_TEMPORAL_L2_PHASE_SCOPES.values(),
    )

    assert subprocess.run(
        ["git", "rev-parse", f"{RUN005_ATTEMPT_002_PREVIOUS_CORRECTIVE_COMMIT}^"], cwd=ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.strip() == RUN005_ATTEMPT_002_CORRECTIVE_BASE
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(untracked) <= changed, f"untracked paths outside the exact current phase allowlist: {untracked}"
    assert not any(path.startswith(("build/", "install/", "log/", ".pytest_cache/"))
                   or "/__pycache__/" in path for path in untracked), untracked


def test_run005_lifecycle_qos_phase_scope_and_authorized_set_are_exact():
    assert len(RUN005_LIFECYCLE_QOS_PHASE_A_PATHS) == 8
    assert len(RUN005_LIFECYCLE_QOS_PHASE_A5_PATHS) == 10
    assert len(RUN005_LIFECYCLE_QOS_RECONCILED_PATHS) == 15
    assert len(RUN005_LIFECYCLE_QOS_AUTHORIZED_PATHS) == 17
    assert RUN005_LIFECYCLE_QOS_PHASE_A_PATHS <= RUN005_LIFECYCLE_QOS_PHASE_A5_PATHS
    assert RUN005_LIFECYCLE_QOS_PHASE_A5_PATHS <= RUN005_LIFECYCLE_QOS_RECONCILED_PATHS
    assert RUN005_LIFECYCLE_QOS_RECONCILED_PATHS <= RUN005_LIFECYCLE_QOS_AUTHORIZED_PATHS
    assert RUN005_LIFECYCLE_QOS_AUTHORIZED_PATHS - RUN005_LIFECYCLE_QOS_RECONCILED_PATHS == {
        "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py",
        "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
    }


def test_run005_nav2_height_corrective_distinguishes_actual_diff_from_authorized_allowlist():
    changed = set(subprocess.run(
        ["git", "diff", "--name-only", f"{RUN005_NAV2_HEIGHT_TEARDOWN_BASE}..{RUN005_QOS_TRACE_BASE}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines())
    assert changed == RUN005_NAV2_HEIGHT_TEARDOWN_PATHS
    assert len(changed) == 11
    assert len(RUN005_NAV2_HEIGHT_TEARDOWN_AUTHORIZED_ALLOWLIST) == 12
    authorized_only = {
        "artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run005_runtime_guard.py",
    }
    assert RUN005_NAV2_HEIGHT_TEARDOWN_AUTHORIZED_ALLOWLIST - changed == authorized_only


def test_run005_validator_identity_corrective_scope_is_exact():
    historical = set(subprocess.run(
        ["git", "diff", "--name-only",
         f"{RUN005_VALIDATOR_CORRECTIVE_BASE}..{RUN005_GZ_IP_GRACEFUL_BASE}"], cwd=ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.splitlines())
    assert historical == RUN005_VALIDATOR_CORRECTIVE_PATHS
    assert subprocess.run(["git", "rev-parse", f"{RUN005_GZ_IP_GRACEFUL_BASE}^"], cwd=ROOT,
                          check=True, capture_output=True, text=True).stdout.strip() == RUN005_VALIDATOR_CORRECTIVE_BASE
    current, _dirty = _candidate_changed_paths()
    assert current in (RUN005_GZ_IP_GRACEFUL_PHASE_A_PATHS, RUN005_GZ_IP_GRACEFUL_PATHS,
                       RUN005_L1_RECONCILED_PATHS,
                       RUN005_LIFECYCLE_QOS_PHASE_A_PATHS,
                       RUN005_LIFECYCLE_QOS_PHASE_A5_PATHS,
                       RUN005_LIFECYCLE_QOS_RECONCILED_PATHS,
                       RUN005_LIFECYCLE_QOS_AUTHORIZED_PATHS,
        RUN005_COLLECTOR_VERDICT_PHASE_A_PATHS,
        RUN005_COLLECTOR_VERDICT_PHASE_A5_PATHS,
        RUN005_COLLECTOR_VERDICT_RECONCILED_PATHS,
        RUN005_COLLECTOR_VERDICT_AUTHORIZED_PATHS,
                       RUN005_DEFAULT_ROUTE_PHASE_A_PATHS, RUN005_DEFAULT_ROUTE_PATHS,
                       RUN005_NAV2_HEIGHT_TEARDOWN_PHASE_A_PATHS,
                       RUN005_NAV2_HEIGHT_TEARDOWN_PATHS,
                       RUN005_QOS_TRACE_PHASE_A_PATHS, RUN005_QOS_TRACE_PHASE_A5_PATHS, RUN005_QOS_TRACE_PATHS,
                       *RUN005_INVOCATION_017_VALID_PHASE_SCOPES,
                       RUN005_INVOCATION_019_PHASE_A_PATHS,
                       RUN005_INVOCATION_019_PHASE_A5_PATHS,
                       RUN005_INVOCATION_019_PHASE_B_PATHS,
                       *RUN005_AUDIT21_PHASE_SCOPES.values(), *RUN005_R1R2_PHASE_SCOPES.values(),
                       *RUN005_R3_PHASE_SCOPES.values(), *RUN005_R5_PHASE_SCOPES.values(),
                       *RUN005_INVOCATION_020_PHASE_SCOPES.values(),
                       *RUN005_INVOCATION_021_PHASE_SCOPES.values(),
                       *RUN005_INVOCATION_022_PHASE_SCOPES.values(),
                       *RUN005_TEMPORAL_L2_PHASE_SCOPES.values())

    # The original root campaign remains the immutable 23-path diff from its
    # integration base through the first topology-corrected campaign commit.
    root_diff = subprocess.run(
        ["git", "diff", "--name-only", f"{STEP07_CAMPAIGN_BASE}..{CORRECTIVE_BASE}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(root_diff) == STEP07_CAMPAIGN_PATHS
    root_parent = subprocess.run(
        ["git", "rev-parse", f"{CORRECTIVE_BASE}^"], cwd=ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert root_parent == STEP07_CAMPAIGN_BASE

    lifecycle_qos_diff = subprocess.run(
        ["git", "diff", "--name-only", f"{CORRECTIVE_BASE}..{ACCEPTANCE_MATRIX_BASE}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(lifecycle_qos_diff) == CORRECTIVE_PATHS

    acceptance_diff = subprocess.run(
        ["git", "diff", "--name-only", f"{ACCEPTANCE_MATRIX_BASE}..{RUN002_BASE}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(acceptance_diff) == CURRENT_CORRECTIVE_PATHS

    run002_diff = subprocess.run(
        ["git", "diff", "--name-only", f"{RUN002_BASE}..{RUN002_COMMIT}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(run002_diff) == RUN002_CORRECTIVE_PATHS

    run003_diff = subprocess.run(
        ["git", "diff", "--name-only", f"{RUN002_COMMIT}..{RUN003_COMMIT}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(run003_diff) == RUN003_CORRECTIVE_PATHS
    assert len(run003_diff) == 14

    protected_fragments = (
        "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/approval_guards/",
        "docs/governance/evidence/WP-06_6F_TF_EKF_RUNTIME_INGRESS_RUN_00",
        "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/run_wp06_6f_tf_ekf_run00",
    )
    assert not any(any(path.startswith(fragment) for fragment in protected_fragments) for path in current)
    assert all(path.startswith("artifacts/simulation/step07_nav2_baseline_campaign/") or
               path.startswith("ros2_ws/src/") or path.startswith("docs/governance/")
               for path in current)


def test_step07_lifecycle_endpoint_and_distinct_qos_contract_across_nodes():
    lifecycle_topic = "/mecanum/safety_lifecycle_state"
    obsolete_topic = "/mecanum/safety/lifecycle_state"
    gate_path = ROOT / "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py"
    lifecycle_path = ROOT / "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/runtime_safety/safety_lifecycle_node.py"
    receipt_path = ROOT / "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/runtime_safety/final_twist_publisher_node.py"
    cpp_path = ROOT / "ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp"
    gate = gate_path.read_text(encoding="utf-8")
    lifecycle = lifecycle_path.read_text(encoding="utf-8")
    receipt = receipt_path.read_text(encoding="utf-8")
    cpp = cpp_path.read_text(encoding="utf-8")

    assert ("with_" + "info=") not in gate and ("with_" + "info=True") not in gate
    assert "create_publisher" not in gate
    assert gate.count("send_goal_async(") == 2
    assert "STATUS_SUCCEEDED" in gate
    assert '"/ground_truth/odom"' not in gate
    assert f'LIFECYCLE_STATE_TOPIC = "{lifecycle_topic}"' in gate
    assert f'OBSOLETE_LIFECYCLE_STATE_TOPIC = "{obsolete_topic}"' in gate
    import ast
    tree = ast.parse(gate)
    subscriptions = []
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        if isinstance(call.func, ast.Attribute) and call.func.attr == "create_subscription":
            topic = call.args[1]
            if isinstance(topic, ast.Constant) and isinstance(topic.value, str):
                subscriptions.append(topic.value)
            elif isinstance(topic, ast.Name) and topic.id == "LIFECYCLE_STATE_TOPIC":
                subscriptions.append(lifecycle_topic)
            else:
                raise AssertionError(f"unexpected subscription topic expression: {ast.dump(topic)}")
    assert set(subscriptions) == {
        "/scan", "/odometry/filtered", lifecycle_topic, "/mecanum/final_issued_command"
    }
    assert len(subscriptions) == 4 and obsolete_topic not in subscriptions

    lifecycle_policy = {"history": "KEEP_LAST", "depth": 10,
                        "reliability": "RELIABLE", "durability": "VOLATILE"}
    receipt_policy = {"history": "KEEP_LAST", "depth": 1,
                      "reliability": "RELIABLE", "durability": "TRANSIENT_LOCAL"}
    assert f'"{lifecycle_topic}"' in lifecycle
    assert "LIFECYCLE_STATE_QOS_CONTRACT = {" in gate
    assert '"history": "KEEP_LAST", "depth": 10' in gate
    assert '"reliability": "RELIABLE", "durability": "VOLATILE"' in gate
    assert "depth=10" in lifecycle and "HistoryPolicy.KEEP_LAST" in lifecycle
    assert "ReliabilityPolicy.RELIABLE" in lifecycle
    assert "DurabilityPolicy.VOLATILE" in lifecycle
    assert "lifecycle_state_qos" in cpp
    assert "return rclcpp::QoS(rclcpp::KeepLast(10)).reliable().durability_volatile();" in cpp

    assert f'"{lifecycle_topic}"' in receipt
    assert '"/mecanum/final_issued_command"' in receipt
    assert "FINAL_RECEIPT_QOS_CONTRACT = {" in gate
    assert '"history": "KEEP_LAST", "depth": 1' in gate
    assert '"reliability": "RELIABLE", "durability": "TRANSIENT_LOCAL"' in gate
    assert "TRANSIENT_LOCAL" in receipt and "depth=1" in receipt
    assert "ReliabilityPolicy.RELIABLE" in receipt
    assert "transient_local()" in cpp
    assert "return rclcpp::QoS(rclcpp::KeepLast(1)).reliable().transient_local();" in cpp


def test_step07_gate_b_observer_has_exact_policy_safe_subscriptions_and_no_publisher():
    path = ROOT / "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py"
    source = path.read_text(encoding="utf-8")
    assert ("with_" + "info=") not in source
    assert "create_publisher" not in source
    assert '"/ground_truth/odom"' not in source
    import re
    import ast
    tree = ast.parse(source)
    found = []
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        if isinstance(call.func, ast.Attribute) and call.func.attr == "create_subscription":
            topic = call.args[1]
            found.append(topic.value if isinstance(topic, ast.Constant) else "LIFECYCLE_STATE_TOPIC")
    assert set(found) == {
        "/scan", "/odometry/filtered", "LIFECYCLE_STATE_TOPIC", "/mecanum/final_issued_command"
    }
    assert len(found) == 4
    assert 'LIFECYCLE_STATE_TOPIC = "/mecanum/safety_lifecycle_state"' in source
    assert 'OBSOLETE_LIFECYCLE_STATE_TOPIC = "/mecanum/safety/lifecycle_state"' in source


def test_step07_static_command_route_preserves_single_final_cmd_vel_owner():
    composite_path = ROOT / "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_nav2_baseline_system.launch.py"
    bridge_path = ROOT / "ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_cmd_vel.runtime.yaml"
    safety_source = ROOT / "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/runtime_safety/final_twist_publisher_node.py"
    composite = composite_path.read_text(encoding="utf-8")
    bridge = yaml.load(bridge_path.read_text(encoding="utf-8"), Loader=UniqueLoader)
    final_publisher = safety_source.read_text(encoding="utf-8")
    assert composite.count('("cmd_vel", "/mecanum/nav2_candidate_cmd")') == 2
    assert 'executable="final_twist_publisher"' in composite
    assert bridge == [{"ros_topic_name": "/cmd_vel", "gz_topic_name": "/cmd_vel",
                       "ros_type_name": "geometry_msgs/msg/Twist",
                       "gz_type_name": "gz.msgs.Twist", "direction": "ROS_TO_GZ"}]
    assert "create_publisher" in final_publisher and '"/cmd_vel"' in final_publisher
    assert "/ground_truth/odom" not in composite and '"/odom"' not in composite
    assert "world -> map" not in composite


def test_step07_gate_b_observer_has_only_policy_safe_subscriptions_and_no_with_info():
    test_step07_gate_b_observer_has_exact_policy_safe_subscriptions_and_no_publisher()


def test_run007_matrix_covers_run_acceptance_and_post_teardown_finalization():
    manifest = _load_json(MANIFEST_PATH)
    matrix = manifest["acceptance_to_collector_matrix"]
    ids = {item["acceptance_id"] for item in matrix}
    assert {"ekf_set_pose_admin_endpoint", "ekf_set_pose_zero_publishers_no_payload", "runtime_session_completed_without_exception"} <= ids
    row = next(item for item in matrix if item["acceptance_id"] == "ekf_set_pose_zero_publishers_no_payload")
    assert row["raw_artifact_path"] == "transcripts/set_pose_info.stdout.bin;transcripts/set_pose_echo.stdout.bin"
    assert row["failure_reason_literal"] == "EKF_SET_POSE_EXTERNAL_PUBLISHER_OBSERVED"
    assert all(all(item.get(k) for k in ("collector", "raw_artifact_path", "parser_or_validator", "pass_condition", "failure_reason_literal", "offline_test_name")) for item in matrix)

def test_wp05_ekf_current_profile_pin_reconciles_without_runtime_claim():
    profile = yaml.load(PROFILE_PATH.read_text(encoding="utf-8"), Loader=UniqueLoader)
    manifest = _load_json(WP05_MANIFEST_PATH)
    relative = "ros2_ws/src/mecanum_nav_bringup/config/state_estimation/ekf_sim.yaml"
    expected = _sha(EKF_PATH)
    yaml_entry = next(item for item in profile["static_configuration_sources"] if item["role"] == "robot_localization_ekf")
    json_entry = next(item for item in manifest["static_configuration_sources"] if item["role"] == "robot_localization_ekf")
    assert yaml_entry == json_entry == {"role": "robot_localization_ekf", "path": relative, "sha256": expected}
    assert profile["runtime_eligible"] is False and manifest["runtime_eligible"] is False


def test_historical_runtime_conservation_and_candidate_scope():
    changed, _dirty = _candidate_changed_paths()
    _assert_run005_attempt002_historical_scope()
    original_run004 = subprocess.run(
        ["git", "diff", "--name-only", f"{RUN004_BASE}..{RUN004_CORRECTIVE_BASE}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(original_run004) == RUN004_CORRECTIVE_PATHS
    run004_host_diff = subprocess.run(
        ["git", "diff", "--name-only", f"{RUN004_CORRECTIVE_BASE}..{RUN004_HOST_CORRECTIVE_COMMIT}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(run004_host_diff) == RUN004_HOST_CORRECTIVE_PATHS
    assert changed in RUN005_COMPOSITE_VALID_SCOPES or changed in (
        RUN005_LIFECYCLE_QOS_PHASE_A_PATHS,
        RUN005_LIFECYCLE_QOS_PHASE_A5_PATHS,
        RUN005_LIFECYCLE_QOS_RECONCILED_PATHS,
        RUN005_LIFECYCLE_QOS_AUTHORIZED_PATHS,
        RUN005_L1_RECONCILED_PATHS,
        RUN005_COLLECTOR_VERDICT_PHASE_A_PATHS,
        RUN005_COLLECTOR_VERDICT_PHASE_A5_PATHS,
        RUN005_COLLECTOR_VERDICT_RECONCILED_PATHS,
        RUN005_COLLECTOR_VERDICT_AUTHORIZED_PATHS,
        RUN005_VALIDATOR_SOURCE_PATHS, RUN005_VALIDATOR_CORRECTIVE_PATHS,
        RUN005_GZ_IP_GRACEFUL_PHASE_A_PATHS, RUN005_GZ_IP_GRACEFUL_PATHS,
        RUN005_DEFAULT_ROUTE_PHASE_A_PATHS, RUN005_DEFAULT_ROUTE_PATHS,
        RUN005_NAV2_HEIGHT_TEARDOWN_PHASE_A_PATHS, RUN005_NAV2_HEIGHT_TEARDOWN_PATHS,
        RUN005_QOS_TRACE_PHASE_A_PATHS, RUN005_QOS_TRACE_PHASE_A5_PATHS, RUN005_QOS_TRACE_PATHS,
        *RUN005_INVOCATION_017_VALID_PHASE_SCOPES,
        RUN005_INVOCATION_019_PHASE_A_PATHS,
        RUN005_INVOCATION_019_PHASE_A5_PATHS,
        RUN005_INVOCATION_019_PHASE_B_PATHS,
        *RUN005_AUDIT21_PHASE_SCOPES.values(), *RUN005_R1R2_PHASE_SCOPES.values(),
        *RUN005_R3_PHASE_SCOPES.values(), *RUN005_R5_PHASE_SCOPES.values(),
        *RUN005_INVOCATION_020_PHASE_SCOPES.values(),
        *RUN005_INVOCATION_021_PHASE_SCOPES.values(),
        *RUN005_INVOCATION_022_PHASE_SCOPES.values(),
        *RUN005_TEMPORAL_L2_PHASE_SCOPES.values(),
    )
    attempt001 = subprocess.run(
        ["git", "diff", "--name-only", f"{RUN005_ATTEMPT_001_BASE}..{RUN005_ATTEMPT_001_COMMIT}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(attempt001) == RUN005_ATTEMPT_001_PATHS
    protected = [
        path for path in subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", STEP07_CAMPAIGN_BASE], cwd=ROOT,
            check=True, capture_output=True, text=True,
        ).stdout.splitlines()
        if __import__("re").search(r"(?:WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_00[1-7]|wp06_6f_tf_ekf_run00[1-7])", path)
    ]
    for relative in protected:
        original = subprocess.run(
            ["git", "show", f"{PARENT}:{relative}"], cwd=ROOT,
            check=True, capture_output=True,
        ).stdout
        assert (ROOT / relative).read_bytes() == original, relative


def test_run005_gz_ip_graceful_teardown_corrective_scope_is_exact():
    changed, _dirty = _candidate_changed_paths()
    assert changed in (RUN005_GZ_IP_GRACEFUL_PHASE_A_PATHS, RUN005_GZ_IP_GRACEFUL_PATHS,
                       RUN005_L1_RECONCILED_PATHS,
                       RUN005_LIFECYCLE_QOS_PHASE_A_PATHS,
                       RUN005_LIFECYCLE_QOS_PHASE_A5_PATHS,
                       RUN005_LIFECYCLE_QOS_RECONCILED_PATHS,
                       RUN005_LIFECYCLE_QOS_AUTHORIZED_PATHS,
        RUN005_COLLECTOR_VERDICT_PHASE_A_PATHS,
        RUN005_COLLECTOR_VERDICT_PHASE_A5_PATHS,
        RUN005_COLLECTOR_VERDICT_RECONCILED_PATHS,
        RUN005_COLLECTOR_VERDICT_AUTHORIZED_PATHS,
                       RUN005_DEFAULT_ROUTE_PHASE_A_PATHS, RUN005_DEFAULT_ROUTE_PATHS,
                       RUN005_NAV2_HEIGHT_TEARDOWN_PHASE_A_PATHS,
                       RUN005_NAV2_HEIGHT_TEARDOWN_PATHS,
                       RUN005_QOS_TRACE_PHASE_A_PATHS, RUN005_QOS_TRACE_PHASE_A5_PATHS, RUN005_QOS_TRACE_PATHS,
                       *RUN005_INVOCATION_017_VALID_PHASE_SCOPES,
                       RUN005_INVOCATION_019_PHASE_A_PATHS,
                       RUN005_INVOCATION_019_PHASE_A5_PATHS,
                       RUN005_INVOCATION_019_PHASE_B_PATHS,
                       *RUN005_AUDIT21_PHASE_SCOPES.values(), *RUN005_R1R2_PHASE_SCOPES.values(),
                       *RUN005_R3_PHASE_SCOPES.values(), *RUN005_R5_PHASE_SCOPES.values(),
                       *RUN005_INVOCATION_020_PHASE_SCOPES.values(),
                       *RUN005_INVOCATION_021_PHASE_SCOPES.values(),
                           *RUN005_INVOCATION_022_PHASE_SCOPES.values(),
                           *RUN005_TEMPORAL_L2_PHASE_SCOPES.values())


def test_run005_default_route_resolver_corrective_scope_is_exact():
    changed, _dirty = _candidate_changed_paths()
    assert changed in (RUN005_DEFAULT_ROUTE_PHASE_A_PATHS, RUN005_DEFAULT_ROUTE_PATHS,
                       RUN005_L1_RECONCILED_PATHS,
                       RUN005_LIFECYCLE_QOS_PHASE_A_PATHS,
                       RUN005_LIFECYCLE_QOS_PHASE_A5_PATHS,
                       RUN005_LIFECYCLE_QOS_RECONCILED_PATHS,
                       RUN005_LIFECYCLE_QOS_AUTHORIZED_PATHS,
        RUN005_COLLECTOR_VERDICT_PHASE_A_PATHS,
        RUN005_COLLECTOR_VERDICT_PHASE_A5_PATHS,
        RUN005_COLLECTOR_VERDICT_RECONCILED_PATHS,
        RUN005_COLLECTOR_VERDICT_AUTHORIZED_PATHS,
                       RUN005_NAV2_HEIGHT_TEARDOWN_PHASE_A_PATHS,
                       RUN005_NAV2_HEIGHT_TEARDOWN_PATHS,
                       RUN005_QOS_TRACE_PHASE_A_PATHS, RUN005_QOS_TRACE_PHASE_A5_PATHS, RUN005_QOS_TRACE_PATHS,
                       *RUN005_INVOCATION_017_VALID_PHASE_SCOPES,
                       RUN005_INVOCATION_019_PHASE_A_PATHS,
                       RUN005_INVOCATION_019_PHASE_A5_PATHS,
                       RUN005_INVOCATION_019_PHASE_B_PATHS,
                       *RUN005_AUDIT21_PHASE_SCOPES.values(), *RUN005_R1R2_PHASE_SCOPES.values(),
                       *RUN005_R3_PHASE_SCOPES.values(), *RUN005_R5_PHASE_SCOPES.values(),
                       *RUN005_INVOCATION_020_PHASE_SCOPES.values(),
                           *RUN005_INVOCATION_021_PHASE_SCOPES.values(),
                           *RUN005_INVOCATION_022_PHASE_SCOPES.values(),
                           *RUN005_TEMPORAL_L2_PHASE_SCOPES.values())


@pytest.mark.parametrize('phase',['PHASE_A','PHASE_A5','PHASE_B'])
def test_audit21_exact_phase_scopes_and_fixed_lineage(phase):
    assert [len(RUN005_AUDIT21_PHASE_SCOPES[p]) for p in ('PHASE_A','PHASE_A5','PHASE_B')]==[9,12,16]
    assert _validate_audit21_scope(RUN005_AUDIT21_PHASE_SCOPES[phase],_audit21_scope_fixture(phase))==phase


@pytest.mark.parametrize('fault',['missing','extra','historical','wrong_phase','untracked'])
def test_audit21_phase_b_rejects_inexact_scope_and_metadata(fault):
    doc=_audit21_scope_fixture('PHASE_B');actual=set(RUN005_AUDIT21_PHASE_B_PATHS);untracked=[]
    if fault=='missing':actual.remove('docs/governance/PROJECT_PROGRESS_LEDGER.md')
    elif fault=='extra':actual.add('unapproved.py')
    elif fault=='historical':actual.add('Invocation_019/run_record.json')
    elif fault=='wrong_phase':doc=_audit21_scope_fixture('PHASE_A')
    else:untracked=['log/logger_all.log']
    with pytest.raises(AssertionError,match='AUDIT21_'):_validate_audit21_scope(actual,doc,untracked)


@pytest.mark.parametrize('status',['',' M runner.py\n','M  runner.py\n','MM runner.py\n'])
def test_audit21_pre_post_commit_and_staged_unstaged_scope_uses_base_diff(monkeypatch,status):
    from types import SimpleNamespace as NS
    commands=[]
    def git(command,**kwargs):
        commands.append(command)
        if command==['git','rev-parse','HEAD']:return NS(stdout=RUN005_AUDIT21_BASE if status else 'b'*40)
        if command==['git','rev-parse','HEAD^']:return NS(stdout=RUN005_AUDIT21_BASE)
        if command==['git','status','--porcelain','--untracked-files=all']:return NS(stdout=status)
        if command==['git','diff','--name-only',RUN005_AUDIT21_BASE]:return NS(stdout='\n'.join(sorted(RUN005_AUDIT21_PHASE_B_PATHS)))
        assert command==['git','ls-files','--others','--exclude-standard'];return NS(stdout='')
    monkeypatch.setattr(subprocess,'run',git)
    monkeypatch.setitem(globals(),'_load_json',lambda _: _audit21_scope_fixture('PHASE_B'))
    actual,dirty=_candidate_changed_paths();assert actual==RUN005_AUDIT21_PHASE_B_PATHS and dirty==bool(status)
    assert ['git','diff','--name-only',RUN005_AUDIT21_BASE] in commands
