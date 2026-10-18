"""Offline tests for the clock bridge and WP06-6F EKF contract."""

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

import yaml

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
MANIFEST_PATH = ROOT / "docs/governance/evidence/WP-06_6F_TF_EKF_RUNTIME_INGRESS_RUN_002_GUARD_MANIFEST.json"
GUARD_PATH = ROOT / "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/approval_guards/WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_002.json"
PROFILE_PATH = PACKAGE / "config/profiles/sim_eval_nav2_baseline.static.yaml"
PROFILE_CONTRACT_PATH = PACKAGE / "mecanum_nav_bringup/sim_eval_static_profile_contract.py"
WP05_MANIFEST_PATH = ROOT / "docs/governance/evidence/WP-05_SIM_EVAL_NAV2_BASELINE_STATIC_PROFILE_MANIFEST.json"
BASE = "8b73bcb0b026fe337c023f6a30205dbe89d31eb5"
PARENT = "90fb75b182b9de102e8d7eb48c5263137b7073ec"


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
    parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate_json)
    assert raw == json.dumps(parsed, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
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
    assert "GZ_PARTITION" in source and PARTITION in source
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
    assert [dep for dep in deps if dep != "rosgraph_msgs"] == baseline_deps
    assert deps.index("rosgraph_msgs") == deps.index("ros_gz_bridge") + 1


def test_wp06f_run002_json_guard_and_source_pin_closure_are_coherent():
    manifest = _load_json(MANIFEST_PATH)
    guard = _load_json(GUARD_PATH)
    assert manifest["run_id"] == guard["run_id"] == "WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_002"
    assert manifest["gz_partition"] == guard["gz_partition"] == PARTITION
    assert guard["state"] == "PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION"
    assert guard["capacity"] == 1
    assert guard["acquisition_count"] == 0
    assert guard["runtime_authorization"] == "NOT_GRANTED"
    assert guard["expected_review_commit"] is None
    assert guard["guard_manifest_sha256"] == _sha(MANIFEST_PATH)
    assert guard["decision_sha256"] == _sha(ROOT / DECISION_PATH)
    assert manifest["decision_sha256"] == guard["decision_sha256"]
    assert manifest["base_commit"] == BASE
    assert manifest["evidence_ceiling"] == "IMPLEMENTED_OFFLINE_CPP_GID_OBSERVER_AND_PENDING_RUN002_GUARD_ONLY"
    assert "dynamic_tf_subscription_qos" in {row["acceptance_id"] for row in manifest["acceptance_to_collector_matrix"]}
    pins = manifest["source_pins"]
    for relative in (EKF_CONFIG_PATH, CLOCK_CONFIG_PATH, DECISION_PATH):
        assert pins[relative] == _sha(ROOT / relative)
    assert pins["ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_tf_ekf_state_estimation.launch.py"] == _sha(LAUNCH_PATH)
    assert pins["ros2_ws/src/mecanum_nav_bringup/mecanum_nav_bringup/sim_eval_tf_ekf_runtime_contract.py"] == _sha(CONTRACT_PATH)
    for relative in (
        "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/run_wp06_6f_tf_ekf_session.py",
        "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/test_wp06_6f_tf_ekf_runtime_session.py",
        "ros2_ws/src/mecanum_nav_bringup/mecanum_nav_bringup/sim_eval_tf_ekf_runtime_observer.py",
        "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_observer.py",
        "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
        "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/wp06_6f_tf_ekf_runtime_guard.py",
        "ros2_ws/src/wp06_6f_tf_ekf_runtime_observer/src/wp06_6f_tf_ekf_runtime_observer.cpp",
        "ros2_ws/src/wp06_6f_tf_ekf_runtime_observer/test/test_wp06_6f_tf_ekf_runtime_observer.cpp",
    ):
        assert pins[relative] == _sha(ROOT / relative)
    assert all(len(value) == 64 and all(char in "0123456789abcdef" for char in value) for value in pins.values())
    assert len(pins) >= 30
    run001_guard = "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/approval_guards/WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_001.json"
    original = subprocess.run(["git", "show", f"{PARENT}:{run001_guard}"], cwd=ROOT, check=True, capture_output=True).stdout
    assert (ROOT / run001_guard).read_bytes() == original


def test_wp05_ekf_current_profile_pin_reconciles_without_runtime_claim():
    profile = yaml.load(PROFILE_PATH.read_text(encoding="utf-8"), Loader=UniqueLoader)
    manifest = _load_json(WP05_MANIFEST_PATH)
    relative = "ros2_ws/src/mecanum_nav_bringup/config/state_estimation/ekf_sim.yaml"
    expected = _sha(EKF_PATH)
    yaml_entry = next(item for item in profile["static_configuration_sources"] if item["role"] == "robot_localization_ekf")
    json_entry = next(item for item in manifest["static_configuration_sources"] if item["role"] == "robot_localization_ekf")
    assert yaml_entry == json_entry == {"role": "robot_localization_ekf", "path": relative, "sha256": expected}
    assert profile["runtime_eligible"] is False and manifest["runtime_eligible"] is False


def test_protected_runtime_and_6c_6d_6e_paths_are_not_in_diff():
    result = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT, check=True, capture_output=True, text=True)
    changed = {line[3:] for line in result.stdout.splitlines()}
    allowed = {
        "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/approval_guards/WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_002.json",
        "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/run_wp06_6f_tf_ekf_session.py",
        "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/wp06_6f_tf_ekf_runtime_guard.py",
        "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/test_wp06_6f_tf_ekf_runtime_session.py",
        "ros2_ws/src/wp06_6f_tf_ekf_runtime_observer/src/wp06_6f_tf_ekf_runtime_observer.cpp",
        "ros2_ws/src/wp06_6f_tf_ekf_runtime_observer/test/test_wp06_6f_tf_ekf_runtime_observer.cpp",
        "ros2_ws/src/mecanum_nav_bringup/mecanum_nav_bringup/sim_eval_tf_ekf_runtime_observer.py",
        "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_observer.py",
        "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
        "docs/governance/decisions/WP-06_SIM_EVAL_TF_EKF_RUNTIME_STATE_ESTIMATION_INGRESS_L2_DECISION.md",
        "docs/governance/evidence/WP-06_SIM_EVAL_TF_EKF_RUNTIME_STATE_ESTIMATION_INGRESS_L2_EVIDENCE.json",
        "docs/governance/evidence/WP-06_6F_TF_EKF_RUNTIME_INGRESS_RUN_002_GUARD_MANIFEST.json",
        "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
        "docs/governance/PROJECT_EXECUTION_PLAN.md",
        "docs/governance/PROJECT_PROGRESS_LEDGER.md",
    }
    assert changed == allowed
    assert not any("WP06_6C" in path or "WP06_6E" in path or "WP06_6D" in path for path in changed)
