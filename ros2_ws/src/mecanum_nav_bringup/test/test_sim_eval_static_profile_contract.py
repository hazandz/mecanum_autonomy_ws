"""Offline checks for the static-only sim_eval profile input closure."""

import ast
import copy
import hashlib
import json
from pathlib import Path

import yaml

from mecanum_nav_bringup.sim_eval_static_profile_contract import (
    STATIC_PROFILE_DESCRIPTOR,
    STATIC_PROFILE_EXCLUSIONS,
    validate_sim_eval_nav2_baseline_static_profile_descriptor,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[2]
PROFILE_PATH = PACKAGE_ROOT / "config/profiles/sim_eval_nav2_baseline.static.yaml"
MANIFEST_PATH = REPO_ROOT / "docs/governance/evidence/WP-05_SIM_EVAL_NAV2_BASELINE_STATIC_PROFILE_MANIFEST.json"
BASE_COMMIT = "4f491edca1d46dee259d57350ad520a0334e4049"
PREVIOUS_SOURCE_COMMIT = "2864a215782cc1901aa259a49d885fa0c132cf7a"
PREVIOUS_GAZEBO_SHA256 = "a97b092f7343d04679ed1417539e47d217b20d18afc3364a27cf14110d9dece8"
CURRENT_GAZEBO_SHA256 = "7bbaa475578600d8e18e437fa83720483b90b4af2bf4212151257152429576a2"
HISTORICAL_INVENTORY_SHA256 = "8b81c656b004201fc8a4be1139aa60652039dd834b957d5c2a96726e161a424e"


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def _reject_duplicate_json_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_profile():
    raw = PROFILE_PATH.read_bytes()
    assert raw.decode("utf-8").encode("utf-8") == raw
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"PENDING_" not in raw
    value = yaml.load(raw.decode("utf-8"), Loader=UniqueKeyLoader)
    return raw, value


def _load_manifest():
    raw = MANIFEST_PATH.read_bytes()
    assert raw.decode("utf-8").encode("utf-8") == raw
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert not raw.endswith(b"\n")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_json_keys)
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert raw == canonical
    return raw, value


def test_yaml_and_manifest_are_exact_static_descriptors():
    _, profile = _load_profile()
    _, manifest = _load_manifest()
    assert profile == STATIC_PROFILE_DESCRIPTOR
    assert validate_sim_eval_nav2_baseline_static_profile_descriptor(profile)
    expected_manifest = {
        **copy.deepcopy(STATIC_PROFILE_DESCRIPTOR),
        "schema": "mecanum_sim_eval_nav2_baseline_static_profile_manifest/v1",
        "exclusions": copy.deepcopy(STATIC_PROFILE_EXCLUSIONS),
    }
    assert manifest == expected_manifest
    assert manifest["classification"] == "STATIC_PROFILE_INPUT_CLOSURE_ONLY"
    assert manifest["runtime_eligible"] is False
    setup_source = (PACKAGE_ROOT / "setup.py").read_text(encoding="utf-8")
    assert '"share/" + package_name + "/config/profiles"' in setup_source
    assert '"config/profiles/sim_eval_nav2_baseline.static.yaml"' in setup_source


def test_canonical_map_identity_and_metadata_remain_valid():
    _, profile = _load_profile()
    map_artifact = profile["map_artifact"]
    # The WP05 source-pin snapshot is historical only. Keep independent map
    # identity checks active without comparing current source to old pins.
    map_manifest = REPO_ROOT / "artifacts/maps/warehouse_map2/map_manifest.json"
    map_yaml = REPO_ROOT / map_artifact["map_yaml_repository_path"]
    assert _sha256(map_manifest) == map_artifact["canonical_manifest_sha256"]
    assert _sha256(map_yaml) == "5073762401784f67e856b5018656ad869ecc26e723f85e5979054eadc7876a68"

    metadata_path = REPO_ROOT / "artifacts/maps/warehouse_map2/metadata.yaml"
    metadata = yaml.load(metadata_path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    assert metadata["map_id"] == map_artifact["map_id"]
    assert metadata["artifact_identity"] == map_artifact["artifact_identity"]
    assert metadata["custody_approval"]["approval_status"] == map_artifact["approval_status"]
    assert metadata["custody_approval"]["approval_evidence"]["sha256"] == "25f16fb3f7e1a668b73fc3d1e14ba51d851a55a2046a1560c44cf5f5aaaa5f7d"
    assert metadata["world_frame"]["state"] == map_artifact["world_frame_state"]
    assert metadata["world_frame"]["evidence_ref"]["sha256"] == "4002e9cd93363f488eb92149d51ca60598922ac11bf252720b8b01a245407294"
    assert metadata["runtime_compatibility"]["state"] == "NOT_VALIDATED"

    approval = json.loads(
        (REPO_ROOT / "docs/governance/evidence/WP-05_WAREHOUSE_MAP2_SIM_EVAL_STATIC_APPROVAL.json").read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_json_keys,
    )
    approval_path = REPO_ROOT / "docs/governance/evidence/WP-05_WAREHOUSE_MAP2_SIM_EVAL_STATIC_APPROVAL.json"
    assert _sha256(approval_path) == "25f16fb3f7e1a668b73fc3d1e14ba51d851a55a2046a1560c44cf5f5aaaa5f7d"
    assert approval["subject"]["map_id"] == map_artifact["map_id"]
    assert approval["subject"]["artifact_identity"] == map_artifact["artifact_identity"]
    assert approval["subject"]["map_content_hash"] == map_artifact["map_content_hash"]
    assert approval["approval"]["approval_status"] == "approved"
    assert approval["approval"]["scope"] == map_artifact["approval_scope"]
    assert all(value is False for value in approval["limitations"].values())

    world = json.loads(
        (REPO_ROOT / "docs/governance/evidence/WP-05_WAREHOUSE_MAP2_WORLD_FRAME_DECLARATION.json").read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_json_keys,
    )
    world_path = REPO_ROOT / "docs/governance/evidence/WP-05_WAREHOUSE_MAP2_WORLD_FRAME_DECLARATION.json"
    assert _sha256(world_path) == "4002e9cd93363f488eb92149d51ca60598922ac11bf252720b8b01a245407294"
    assert world["subject"]["map_id"] == map_artifact["map_id"]
    assert world["subject"]["artifact_identity"] == map_artifact["artifact_identity"]
    assert world["subject"]["map_content_hash"] == map_artifact["map_content_hash"]
    assert world["declaration"]["world_frame_state"] == "DECLARED_UNVERIFIED"
    assert world["declaration"]["transform_claim"] == "NONE"
    assert all(value is False for value in world["limitations"].values())


def _historical_wp05_gazebo_pin_reconciliation_preserves_historical_inventory():
    profile_raw, profile = _load_profile()
    manifest_raw, manifest = _load_manifest()
    python_raw = (PACKAGE_ROOT / "mecanum_nav_bringup/sim_eval_static_profile_contract.py").read_bytes()
    gazebo_path = "ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo"
    current_yaml_pin = next(
        entry for entry in profile["static_ingress_contracts"]
        if entry["role"] == "gazebo_lidar_source"
    )
    current_python_pin = next(
        entry for entry in STATIC_PROFILE_DESCRIPTOR["static_ingress_contracts"]
        if entry["role"] == "gazebo_lidar_source"
    )
    current_manifest_pin = next(
        entry for entry in manifest["static_ingress_contracts"]
        if entry["role"] == "gazebo_lidar_source"
    )
    assert BASE_COMMIT == "4f491edca1d46dee259d57350ad520a0334e4049"
    assert profile["source_commit"] == BASE_COMMIT
    assert current_yaml_pin["path"] == current_python_pin["path"] == current_manifest_pin["path"] == gazebo_path
    assert current_yaml_pin["classification"] == current_python_pin["classification"] == current_manifest_pin["classification"] == "GAZEBO_TRANSPORT_PROVENANCE_ONLY"
    assert current_yaml_pin["sha256"] == current_python_pin["sha256"] == current_manifest_pin["sha256"] == CURRENT_GAZEBO_SHA256
    assert _sha256(REPO_ROOT / gazebo_path) == CURRENT_GAZEBO_SHA256
    assert PREVIOUS_SOURCE_COMMIT not in profile_raw.decode("utf-8")
    assert PREVIOUS_GAZEBO_SHA256 not in profile_raw.decode("utf-8")
    assert PREVIOUS_SOURCE_COMMIT.encode() not in python_raw + manifest_raw
    assert PREVIOUS_GAZEBO_SHA256.encode() not in python_raw + manifest_raw

    # The inventory is a historical snapshot and intentionally retains the old provenance pin.
    inventory_path = REPO_ROOT / "docs/governance/evidence/WP-05_NAVIGATION_V1_WORKSPACE_SOURCE_ROLE_INVENTORY.json"
    inventory_raw = inventory_path.read_bytes()
    inventory = json.loads(inventory_raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_json_keys)
    historical_entry = next(
        reference
        for role in inventory["roles"]
        for reference in role.get("evidence_references", [])
        if reference["repository_relative_path"] == gazebo_path
    )
    assert historical_entry["source_file_sha256"] == PREVIOUS_GAZEBO_SHA256
    assert _sha256(inventory_path) == HISTORICAL_INVENTORY_SHA256


def test_validator_fails_closed_on_profile_map_source_and_runtime_mutations():
    mutations = []
    changed = copy.deepcopy(STATIC_PROFILE_DESCRIPTOR)
    changed["profile"]["runtime_profile"] = "other"
    mutations.append(changed)
    changed = copy.deepcopy(STATIC_PROFILE_DESCRIPTOR)
    changed["map_artifact"]["map_content_hash"] = "0" * 64
    mutations.append(changed)
    changed = copy.deepcopy(STATIC_PROFILE_DESCRIPTOR)
    changed["static_configuration_sources"][0]["sha256"] = "0" * 64
    mutations.append(changed)
    changed = copy.deepcopy(STATIC_PROFILE_DESCRIPTOR)
    changed["runtime_eligible"] = True
    mutations.append(changed)
    changed = copy.deepcopy(STATIC_PROFILE_DESCRIPTOR)
    changed["config_hash"] = "invented"
    mutations.append(changed)
    changed = copy.deepcopy(STATIC_PROFILE_DESCRIPTOR)
    changed["workspace_source_locks"] = []
    mutations.append(changed)
    changed = copy.deepcopy(STATIC_PROFILE_DESCRIPTOR)
    changed["static_configuration_sources"].reverse()
    mutations.append(changed)
    for descriptor in mutations:
        assert not validate_sim_eval_nav2_baseline_static_profile_descriptor(descriptor)


def test_profile_does_not_create_runtime_resolution_or_execution_fields():
    raw, profile = _load_profile()
    _, manifest = _load_manifest()
    assert validate_sim_eval_nav2_baseline_static_profile_descriptor(profile)
    # The profile's exact closed schema has no runtime locks, endpoints, or launch graph fields.
    forbidden_keys = {
        "ResolvedConfigV3", "config_hash", "workspace_source_locks", "external_package_locks",
        "bridge_endpoint", "bridge_implementation", "runtime_evidence", "runtime_authorization",
        "map_server_runtime_binding", "launch_graph",
    }
    def collect_keys(value):
        if isinstance(value, dict):
            for key, nested in value.items():
                yield key
                yield from collect_keys(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from collect_keys(nested)
    assert forbidden_keys.isdisjoint(set(collect_keys(profile)))
    assert forbidden_keys.isdisjoint(set(collect_keys(manifest)))
    assert b"PENDING_" not in raw
    assert profile["runtime_eligible"] is False
    assert profile["map_artifact"]["approval_status"] == "approved"
    assert profile["map_artifact"]["world_frame_state"] == "DECLARED_UNVERIFIED"
    assert profile["map_artifact"]["runtime_compatibility_state"] == "NOT_VALIDATED"


def test_validator_module_is_pure_python_without_runtime_imports():
    source = (PACKAGE_ROOT / "mecanum_nav_bringup/sim_eval_static_profile_contract.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {"rclpy", "launch", "launch_ros", "gazebo", "gz", "ros_gz_bridge", "ros_gz_sim", "nav2"}
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add((node.module or "").split(".")[0])
    assert imports.isdisjoint(forbidden)
    assert "open" not in {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert BASE_COMMIT == STATIC_PROFILE_DESCRIPTOR["source_commit"]
