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
CORRECTIVE_BASE = "04a2ba5332ea56feb24dc3cf393114d8158bcb62"


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
    assert evidence["historical_run_006"]["terminal_outcome"] == "WP06_6F_RUNTIME_RUN006_FAIL_NO_RETRY_GUARD_CONSUMED"
    assert evidence["historical_run_006"]["failure"] == "GuardError:RUNTIME_ACCEPTANCE_FAILED"
    assert evidence["historical_run_006"]["guard_state"] == "CONSUMED"
    # The repository guard and guard manifest are the pre-acquisition seed;
    # the L1 evidence document records the later consumed-guard disposition.
    assert evidence["run_007_guard"]["state_before"] == guard["state"]
    assert evidence["run_007_guard"]["state"] == "CONSUMED"
    assert evidence["run_007_guard"]["acquisition_count"] == 1
    assert evidence["run_007_guard"]["capacity"] == 1
    assert evidence["run_007_guard"]["runtime_authorization"] == "GRANTED_FOR_THIS_EXACT_RUN_ONLY"
    assert evidence["RUNTIME_APPROVED"] == "NOT_APPROVED" and evidence["GATE_B"] == "NOT_STARTED"
    assert manifest["evidence_ceiling"] == "IMPLEMENTED_OFFLINE_RUN007_OWNER_AUTHORIZATION_BINDING_GUARD_PENDING"
    assert evidence["evidence_ceiling"] == "RAW_RUNTIME_EVIDENCE_AUDITED_PASS_WP06_6F_SCOPE_ONLY"
    assert manifest["owner_authorization_contract"] == evidence["owner_authorization_contract"]
    assert manifest["owner_authorization_contract"]["scope_literal"] == "WP06_6F_RUN007_ONE_OFFICIAL_RUNNER_INVOCATION_CAPACITY_ONE_NO_RETRY"
    assert evidence["runtime_eligible"] is False
    assert evidence["runtime_evidence_status"] == "RAW_RUNTIME_EVIDENCE_AUDITED_PASS"


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
    result = subprocess.run(
        ["git", "diff", "--name-only", CORRECTIVE_BASE], cwd=ROOT,
        check=True, capture_output=True, text=True,
    )
    changed = set(result.stdout.splitlines())
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT,
        check=True, capture_output=True, text=True,
    )
    changed.update(untracked.stdout.splitlines())
    allowed = {
        "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/runtime_safety/safety_lifecycle_node.py",
        "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/runtime_safety/safety_supervisor_node.py",
        "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/runtime_safety/final_twist_publisher_node.py",
        "ros2_ws/src/mecanum_nav_rl_interfaces/msg/CommandEnvelope.msg",
        "ros2_ws/src/mecanum_nav_rl/test/test_runtime_safety_contract.py",
        "ros2_ws/src/mecanum_nav_rl/test/test_final_twist_publisher_static.py",
        "ros2_ws/src/mecanum_nav_rl/test/test_safety_lifecycle_transition.py",
        "ros2_ws/src/mecanum_nav_rl_interfaces/test/test_interface_contracts.py",
        "ros2_ws/src/mecanum_nav_bringup/test/test_sim_eval_tf_ekf_runtime_contract.py",
        "docs/governance/decisions/ROADMAP_STEP4_STEP5_STEP6_CONSOLIDATED_CLOSURE.md",
        "docs/governance/evidence/ROADMAP_STEP4_STEP5_STEP6_CONSOLIDATED_CLOSURE.json",
        "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
        "docs/governance/PROJECT_EXECUTION_PLAN.md",
        "docs/governance/PROJECT_PROGRESS_LEDGER.md",
    }
    assert changed <= allowed
    protected = [
        path for path in subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", PARENT], cwd=ROOT,
            check=True, capture_output=True, text=True,
        ).stdout.splitlines()
        if __import__("re").search(r"(?:WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_00[1-7]|wp06_6f_tf_ekf_run00[1-7])", path)
    ]
    assert not changed.intersection(protected)
    for path in protected:
        committed = subprocess.run(
            ["git", "show", f"{CORRECTIVE_BASE}:{path}"], cwd=ROOT,
            check=True, capture_output=True,
        ).stdout
        assert (ROOT / path).read_bytes() == committed, f"historical WP06 bytes changed: {path}"
    forbidden = ("ground_truth", "ground-truth", "/odom", "tf_static")
    assert not any(any(token in path.lower() for token in forbidden) for path in changed)


def test_run006_raw_record_retains_historical_finalization_failure_not_system_failure():
    raw_path = Path("/home/hazan/wp06_runtime_evidence/WP06_6F_TF_EKF_RUNTIME_INGRESS_RUN_006/run_record.json")
    assert hashlib.sha256(raw_path.read_bytes()).hexdigest() == "0a67816439f35563948dddc7e2e75258c0e7ac6b39e9caab2c3bb9acade19f9a"
    record = json.loads(raw_path.read_text(encoding="utf-8"))
    assert record["terminal_outcome"] == "WP06_6F_RUNTIME_RUN006_FAIL_NO_RETRY_GUARD_CONSUMED"
    assert record["failure"] == "GuardError:RUNTIME_ACCEPTANCE_FAILED"
    assert record["teardown_pass"] is True
    assert all(value is True for value in record["acceptance"].values())
    assert [entry["name"] for entry in record["teardown"]] == ["composite", "bootstrap"]
    assert all(entry["outcome"] == "STOPPED" and entry["leader_returncode"] == 0
               and entry["live_member_pids"] == [] and entry["zombie_member_pids"] == []
               for entry in record["teardown"])
    runner006 = ROOT / "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/run_wp06_6f_tf_ekf_run006_session.py"
    source = runner006.read_text(encoding="utf-8")
    assert source.index('raise GuardError("RUNTIME_ACCEPTANCE_FAILED")') < source.index("    finally:")
    assert "RUN006_RUNNER_FINALIZATION_ORDER_FAILURE_NOT_TF_EKF_CLOCK_OR_ROBOT_FAILURE" in _load_json(MANIFEST_PATH)["historical_run_006_disposition"]["classification"]
