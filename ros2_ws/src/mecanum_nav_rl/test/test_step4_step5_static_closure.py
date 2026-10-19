"""Offline closure tests for map, resolved profile, routing, and receipt source."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import pytest
import yaml
from pydantic import ValidationError

from mecanum_nav_rl.config.v3_compiler import compile_resolved_document_v3
from mecanum_nav_rl.config.v3_hashing import config_v3_sha256
from mecanum_nav_rl.config.v3_models import ResolvedConfigV3
from mecanum_nav_rl.config.v3_validators import validate_resolved_config_v3

ROOT = Path(__file__).resolve().parents[4]
ARCH = "432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204"
MAP_EXPECTED = {
    "map.yaml": "5073762401784f67e856b5018656ad869ecc26e723f85e5979054eadc7876a68",
    "map.pgm": "32f8a3eb626ebddecc15843748de0db8c6f7adc1b45a5edc1b1b1886407aef55",
    "metadata.yaml": "45450a2d62b38560200d11fef6ece8505eef5a3e3d73e27f7b091de022e793c1",
    "map_manifest.json": "7e0a380b0d8df32f9a4fc30dd0dbbe9ed08aafdcd5efb3764bccd844b98c1cb1",
}


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json(path: Path):
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8")
    return raw, json.loads(text, object_pairs_hook=_unique_pairs)


def test_resolved_config_is_full_16_section_profile_and_reproducible() -> None:
    path = ROOT / "ros2_ws/src/mecanum_nav_rl/config/v3/resolved/sim_eval_nav2_baseline.resolved.json"
    raw, document = _load_json(path)
    assert not raw.endswith(b"\n")
    assert set(document) == {
        "schema_version", "project", "runtime", "provenance", "frames_tf", "topics_qos",
        "state_estimation", "localization", "navigation", "observation", "action",
        "motion_limits", "map_identity", "command_safety", "reward", "training",
        "evaluation", "acceptance",
    }
    assert len(set(document) - {"schema_version", "provenance"}) == 16
    assert document["runtime"] == {"runtime_profile": "sim_eval", "navigation_mode": "NAV2_BASELINE", "use_sim_time": True}
    assert document["project"]["architecture_sha256"] == ARCH
    assert document["map_identity"]["map_id"] == "warehouse_map2"
    assert document["frames_tf"]["map_to_odom_authority"] == "AMCL_Omni"
    assert document["frames_tf"]["odom_to_base_link_authority"] == "EKF"
    assert document["frames_tf"]["base_link_to_lidar_authority"] == "robot_state_publisher"
    assert document["navigation"]["controller_owner"] == "Nav2ControllerServer"
    assert document["navigation"]["local_reference_contract_id"] == "nav2_msgs/action/ComputePathToPose"
    assert document["motion_limits"] == {
        "source_class": "SIM_BASELINE", "source_id": "sim_eval_nav2_baseline_owner_decision",
        "max_vx_mps": 0.25, "max_vy_mps": 0.20, "max_wz_radps": 0.80,
    }
    def unresolved(value):
        if isinstance(value, dict):
            if {"field_path", "token", "reference_id"}.issubset(value):
                return True
            return any(unresolved(child) for child in value.values())
        if isinstance(value, list):
            return any(unresolved(child) for child in value)
        return isinstance(value, str) and (value.startswith("TBD_") or value.startswith("REQUIRED_"))
    assert not unresolved(document)
    assert set(document["observation"]) == {"input_profile"}
    assert document["observation"]["input_profile"]["dimension"] == 81
    unhashed = json.loads(raw)
    unhashed["provenance"].pop("config_hash")
    config = compile_resolved_document_v3(unhashed)
    validate_resolved_config_v3(config)
    assert config.provenance.config_hash == document["provenance"]["config_hash"]
    assert config.provenance.config_hash == config_v3_sha256(unhashed)
    assert config.model_dump(mode="json")["provenance"]["config_hash"] == document["provenance"]["config_hash"]


def test_jcs_numeric_serialization_and_non_finite_rejection() -> None:
    payload = {"numbers": [333333333.33333329, 1e30, 4.50, 2e-3, 1e-27, -0.0]}
    assert config_v3_sha256({"provenance": {"source_manifest_sha256": "a" * 64}, "payload": payload})
    from mecanum_nav_rl.config.v3_hashing import _jcs
    assert _jcs(payload) == '{"numbers":[333333333.3333333,1e+30,4.5,0.002,1e-27,0]}'
    with pytest.raises(ValueError, match="provenance mapping"):
        config_v3_sha256({"payload": payload})
    assert config_v3_sha256({"provenance": {"config_hash": "ignored", "source_manifest_sha256": "a" * 64}, "payload": payload}) == config_v3_sha256({"provenance": {"source_manifest_sha256": "a" * 64}, "payload": payload})
    with pytest.raises(ValueError, match="non-finite"):
        _jcs(float("nan"))


def test_map_artifact_bundle_and_world_binding_are_exact() -> None:
    map_root = ROOT / "artifacts/maps/warehouse_map2"
    for name, expected in MAP_EXPECTED.items():
        assert hashlib.sha256((map_root / name).read_bytes()).hexdigest() == expected
    _, manifest = _load_json(map_root / "map_manifest.json")
    assert manifest["map_id"] == "warehouse_map2"
    assert manifest["artifact_identity"] == "4a8a23d0-7e27-4a50-8201-dd1abf1a3db4"
    assert manifest["map_content_hash"] == "2bd9ff0a40eaeb61c2359aab4bb213da623ab56746debe591edd4a54c2229f90"
    _, binding = _load_json(map_root / "sim_eval_navigation_world_binding.json")
    assert binding["map_world_semantics"]["map_is_gazebo_world"] is False
    assert binding["map_world_semantics"]["world_to_map_published"] is False
    assert binding["map_world_semantics"]["runtime_compatibility_state"] == "NOT_VALIDATED"
    assert binding["provenance"] == {
        "sim_eval_scan_probe.world.sdf": "DIAGNOSTIC_WORLD_ONLY",
        "tugbot_depot.sdf": "USER_ATTESTED_MAP_CREATION_WORLD_PROVENANCE",
        "warehouse_world.sdf": "REFERENCE_ONLY",
    }
    world = ROOT / "ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf"
    assert hashlib.sha256(world.read_bytes()).hexdigest() == binding["simulation_world"]["sha256"]


def test_receipt_rosidl_source_and_command_routes_are_bounded() -> None:
    interface_root = ROOT / "ros2_ws/src/mecanum_nav_rl_interfaces"
    cmake = (interface_root / "CMakeLists.txt").read_text(encoding="utf-8")
    assert '"msg/FinalIssuedCommandReceipt.msg"' in cmake
    assert '"msg/SafetyLifecycleState.msg"' in cmake
    receipt = (interface_root / "msg/FinalIssuedCommandReceipt.msg").read_text(encoding="utf-8")
    assert "mecanum.final-issued-receipt/v2" in receipt
    assert "Not installed in a ROSIDL package" not in receipt
    assert "uint64 final_publish_sequence" in receipt
    bridge = yaml.safe_load((ROOT / "ros2_ws/src/mecanum_nav_bringup/config/bridge/sim_eval_cmd_vel.runtime.yaml").read_text())
    assert bridge == [{"ros_topic_name": "/cmd_vel", "gz_topic_name": "/cmd_vel", "ros_type_name": "geometry_msgs/msg/Twist", "gz_type_name": "gz.msgs.Twist", "direction": "ROS_TO_GZ"}]
    launch = (ROOT / "ros2_ws/src/mecanum_nav_bringup/launch/sim_eval_nav2_baseline_system.launch.py").read_text()
    assert '("cmd_vel", "/mecanum/nav2_candidate_cmd")' in launch
    assert "final_twist_publisher" in launch
    publisher = (ROOT / "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/runtime_safety/final_twist_publisher_node.py").read_text()
    assert 'create_publisher(Twist, "/cmd_vel"' in publisher
    assert publisher.count('create_publisher(Twist, "/cmd_vel"') == 1
    assert publisher.index("self._cmd_pub.publish(final_command)") < publisher.index("self._receipt_pub.publish(receipt)")
    assert 'create_publisher(Twist, "/cmd_vel"' not in launch


def test_bootstrap_requires_runtime_arguments_without_map_world_claim() -> None:
    source = (ROOT / "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_nav2_baseline_bootstrap.launch.py").read_text()
    for arg in ("gz_partition", "initial_pose_map_x", "initial_pose_map_y", "initial_pose_map_yaw"):
        assert f'DeclareLaunchArgument("{arg}")' in source
    assert "Map-frame initial pose" in source
    assert "world-frame transform" in source
    assert "SetEnvironmentVariable(\"GZ_PARTITION\", EXPECTED_PARTITION)" in source
