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
MANIFEST_PATH = ROOT / "docs/governance/evidence/WP-06_6F_TF_EKF_RUNTIME_INGRESS_RUN_007_GUARD_MANIFEST.json"
GUARD_PATH = ROOT / "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/approval_guards/WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_007.json"
PROFILE_PATH = PACKAGE / "config/profiles/sim_eval_nav2_baseline.static.yaml"
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
    inserted_runtime_roots = [
        "mecanum_nav_rl", "mecanum_nav_rl_interfaces", "nav2_msgs", "lifecycle_msgs"
    ]
    expected = list(baseline_deps)
    launch_position = expected.index("launch")
    expected[launch_position:launch_position] = inserted_runtime_roots
    expected.insert(expected.index("ros_gz_bridge") + 1, "rosgraph_msgs")
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

def _candidate_changed_paths():
    status = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"], cwd=ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    if status:
        changed = {line[3:] for line in status if line}
        if changed == RUN005_ATTEMPT_002_PATHS:
            return changed, True
        raise AssertionError(f"dirty Run005 attempt_002 path set is not exact: {sorted(changed)}")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    parent = subprocess.run(
        ["git", "rev-parse", "HEAD^"], cwd=ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if parent == RUN005_BASE:
        names = subprocess.run(
            ["git", "diff", "--name-only", "HEAD^", "HEAD"], cwd=ROOT,
            check=True, capture_output=True, text=True,
        ).stdout.splitlines()
        changed = set(names)
        if changed != RUN005_ATTEMPT_002_PATHS:
            raise AssertionError("clean Run005 attempt_002 does not match its exact authorized path set")
        return changed, False
    raise AssertionError(f"clean worktree is not the attempt_002 base or committed candidate: HEAD={head}")


def test_current_step07_campaign_scope_chain_is_exact_and_historical_wp06_is_not_relaxed():
    changed, _dirty = _candidate_changed_paths()
    assert changed == RUN005_ATTEMPT_002_PATHS
    assert len(changed) == len(RUN005_ATTEMPT_002_PATHS)
    attempt001 = subprocess.run(
        ["git", "diff", "--name-only", f"{RUN005_ATTEMPT_001_BASE}..{RUN005_ATTEMPT_001_COMMIT}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(attempt001) == RUN005_ATTEMPT_001_PATHS
    assert len(attempt001) == 13
    assert subprocess.run(
        ["git", "rev-parse", f"{RUN005_ATTEMPT_001_COMMIT}^"], cwd=ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.strip() == RUN005_ATTEMPT_001_BASE
    original_run004 = subprocess.run(
        ["git", "diff", "--name-only", f"{RUN004_BASE}..{RUN004_CORRECTIVE_BASE}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(original_run004) == RUN004_CORRECTIVE_PATHS
    assert len(original_run004) == 17
    run004_host_diff = subprocess.run(
        ["git", "diff", "--name-only", f"{RUN004_CORRECTIVE_BASE}..{RUN004_HOST_CORRECTIVE_COMMIT}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(run004_host_diff) == RUN004_HOST_CORRECTIVE_PATHS
    assert len(run004_host_diff) == 11
    assert subprocess.run(
        ["git", "rev-parse", f"{RUN004_HOST_CORRECTIVE_COMMIT}^"], cwd=ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.strip() == RUN004_CORRECTIVE_BASE
    assert set(changed) == RUN005_ATTEMPT_002_PATHS
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(untracked) <= changed, f"untracked paths outside the exact current phase allowlist: {untracked}"
    assert not any(path.startswith(("build/", "install/", "log/", ".pytest_cache/"))
                   or "/__pycache__/" in path for path in untracked), untracked
    assert not any(path.startswith(("build/", "install/", "log/")) for path in changed)

    # The original root campaign remains the immutable 23-path diff from its
    # integration base through the first topology-corrected campaign commit.
    root_diff = subprocess.run(
        ["git", "diff", "--name-only", f"{STEP07_CAMPAIGN_BASE}..{CORRECTIVE_BASE}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(root_diff) == STEP07_CAMPAIGN_PATHS
    assert len(root_diff) == 23
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
    assert len(lifecycle_qos_diff) == 14

    acceptance_diff = subprocess.run(
        ["git", "diff", "--name-only", f"{ACCEPTANCE_MATRIX_BASE}..{RUN002_BASE}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(acceptance_diff) == CURRENT_CORRECTIVE_PATHS
    assert len(acceptance_diff) == 9

    run002_diff = subprocess.run(
        ["git", "diff", "--name-only", f"{RUN002_BASE}..{RUN002_COMMIT}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(run002_diff) == RUN002_CORRECTIVE_PATHS
    assert len(run002_diff) == 13

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
    assert not any(any(path.startswith(fragment) for fragment in protected_fragments) for path in changed)
    assert all(path.startswith("artifacts/simulation/step07_nav2_baseline_campaign/") or
               path.startswith("ros2_ws/src/") or path.startswith("docs/governance/")
               for path in changed)


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
    assert changed == RUN005_ATTEMPT_002_PATHS
    assert len(changed) == len(RUN005_ATTEMPT_002_PATHS)
    original_run004 = subprocess.run(
        ["git", "diff", "--name-only", f"{RUN004_BASE}..{RUN004_CORRECTIVE_BASE}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(original_run004) == RUN004_CORRECTIVE_PATHS
    assert len(original_run004) == 17
    run004_host_diff = subprocess.run(
        ["git", "diff", "--name-only", f"{RUN004_CORRECTIVE_BASE}..{RUN004_HOST_CORRECTIVE_COMMIT}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(run004_host_diff) == RUN004_HOST_CORRECTIVE_PATHS
    assert len(run004_host_diff) == 11
    assert set(changed) == RUN005_ATTEMPT_002_PATHS
    attempt001 = subprocess.run(
        ["git", "diff", "--name-only", f"{RUN005_ATTEMPT_001_BASE}..{RUN005_ATTEMPT_001_COMMIT}"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(attempt001) == RUN005_ATTEMPT_001_PATHS
    assert len(attempt001) == 13
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
