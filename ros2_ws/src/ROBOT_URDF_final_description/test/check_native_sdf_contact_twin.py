#!/usr/bin/env python3
"""Fail-closed static validation for native SDF contact and pose-frame parity."""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import os
import stat
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

MODEL_NAME = "ROBOT_URDF_final"
LINK_NAME = "base_link"
COLLISION_NAME = "s3_d3_base_contact_collision"
SENSOR_NAME = "s3_d3_base_contact_sensor"
RAW_TOPIC = "/s3_d3/contact/raw"
FORBIDDEN = ("cmd_vel", "bridge", "TouchPlugin", "fixed_joint_lump", "control", "<plugin")
ZERO_POSE = "0 0 0 0 0 0"

INERTIALS = {
    "base_link": ("-0.004680971074212348 0.001013778159962492 0.022702840329693212 0 0 0", "2", "0.032621", "-2.7e-05", "0.003248", "0.088559", "0.000162", "0.100296"),
    "Wheel_LF_1": ("7.730831169672214e-09 0.020486354622651984 7.0657725812633965e-06 0 0 0", "0.15", "0.000111", "-0.0", "-0.0", "0.000179", "0.0", "0.000111"),
    "Wheel_RF_1": ("8.176073262866623e-09 -0.020486352801042898 7.067794141380618e-06 0 0 0", "0.15", "0.000111", "0.0", "-0.0", "0.000179", "-0.0", "0.000111"),
    "Wheel_RB_1": ("-1.1186073178848233e-09 -0.020486363591042916 7.059103033960068e-06 0 0 0", "0.15", "0.000111", "0.0", "0.0", "0.000179", "-0.0", "0.000111"),
    "Wheel_LB_1": ("-1.5638501049686226e-09 0.02048636176944614 7.061124594778118e-06 0 0 0", "0.15", "0.000111", "-0.0", "0.0", "0.000179", "0.0", "0.000111"),
    "IntelRealsense_D435_Multibody_1": ("0.01195124704164778 -0.0026011079695855525 -6.051171193946492e-05 0 0 0", "0.35", "0.000227", "-1e-06", "-0.0", "3.2e-05", "-0.0", "0.000229"),
    "RPLiDAR_A1M8_1": ("-0.05153713704514566 8.887643777943633e-05 0.027012153068496997 0 0 0", "0.7", "0.000423", "-6e-06", "4.5e-05", "0.000745", "5e-06", "0.000767"),
}
JOINTS = {
    "Wheel_LF_Joint": ("continuous", "0.108 0.11109 -0.0175 0 0 0", "base_link", "Wheel_LF_1", "0.0 1.0 0.0"),
    "Wheel_RF_Joint": ("continuous", "0.108 -0.11109 -0.0175 0 0 0", "base_link", "Wheel_RF_1", "0.0 1.0 0.0"),
    "Wheel_RB_Joint": ("continuous", "-0.108 -0.11109 -0.0175 0 0 0", "base_link", "Wheel_RB_1", "0.0 1.0 0.0"),
    "Wheel_LB_Joint": ("continuous", "-0.108 0.11109 -0.0175 0 0 0", "base_link", "Wheel_LB_1", "0.0 1.0 0.0"),
    "Camera_Joint": ("fixed", "0.043208 0.0 0.095165 0 0 0", "base_link", "IntelRealsense_D435_Multibody_1", None),
    "Lidar_Joint": ("fixed", "0.0432 0.0 0.107565 0 0 0", "base_link", "RPLiDAR_A1M8_1", None),
}
CHILD_TO_JOINT = {values[3]: name for name, values in JOINTS.items()}
VISUALS = {
    "IntelRealsense_D435_Multibody_1": (
        "s3_d3_camera_visual",
        "-0.043208 0.0 -0.095165 0 0 0",
        "ROBOT_URDF_final_description/meshes/IntelRealsense_D435_Multibody_1.stl",
        "0.001 0.001 0.001",
    ),
    "RPLiDAR_A1M8_1": (
        "s3_d3_lidar_visual",
        "-0.0432 0.0 -0.107565 0 0 0",
        "ROBOT_URDF_final_description/meshes/RPLiDAR_A1M8_1.stl",
        "0.001 0.001 0.001",
    ),
}


class ValidationError(ValueError):
    """A static twin invariant was not met."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def text_of(parent: ET.Element, path: str, label: str) -> str:
    child = parent.find(path)
    require(child is not None and child.text is not None, f"missing {label}")
    return child.text.strip()


def exactly_one(items: list[ET.Element], label: str) -> ET.Element:
    require(len(items) == 1, f"expected exactly one {label}, found {len(items)}")
    return items[0]


def validate_inertial(link: ET.Element, expected: tuple[str, ...]) -> None:
    inertial = exactly_one(link.findall("./inertial"), f"{link.attrib['name']} inertial")
    observed = (
        text_of(inertial, "./pose", "inertial pose"),
        text_of(inertial, "./mass", "inertial mass"),
        text_of(inertial, "./inertia/ixx", "ixx"),
        text_of(inertial, "./inertia/ixy", "ixy"),
        text_of(inertial, "./inertia/ixz", "ixz"),
        text_of(inertial, "./inertia/iyy", "iyy"),
        text_of(inertial, "./inertia/iyz", "iyz"),
        text_of(inertial, "./inertia/izz", "izz"),
    )
    require(observed == expected, f"inertial mismatch for {link.attrib['name']}")


def validate_contact(base_link: ET.Element) -> None:
    collision = exactly_one(base_link.findall("./collision[@name='s3_d3_base_contact_collision']"), "base contact collision")
    require(text_of(collision, "./pose", "collision pose") == ZERO_POSE, "unexpected collision pose")
    require(text_of(collision, "./geometry/box/size", "box size") == "0.4 0.28 0.10", "unexpected box size")
    sensor = exactly_one(base_link.findall("./sensor"), "contact sensor")
    require(sensor.attrib == {"name": SENSOR_NAME, "type": "contact"}, "unexpected contact sensor identity")
    require(text_of(sensor, "./always_on", "always_on").lower() == "true", "always_on must be true")
    require(text_of(sensor, "./update_rate", "update_rate") == "100", "update_rate must be 100")
    require(sensor.find("./topic") is None, "contact topic must not be a direct sensor child")
    contact = exactly_one(sensor.findall("./contact"), "contact configuration")
    require(text_of(contact, "./collision", "contact collision") == COLLISION_NAME, "contact target mismatch")
    require(text_of(contact, "./topic", "contact topic") == RAW_TOPIC, "contact topic mismatch")


def validate_pose_relation(link: ET.Element) -> None:
    name = link.attrib["name"]
    if name == LINK_NAME:
        require(link.find("./pose") is None, "base link pose must remain source-neutral")
        return
    pose = exactly_one(link.findall("./pose"), f"{name} link pose")
    require(pose.attrib == {"relative_to": CHILD_TO_JOINT[name]}, f"link pose frame mismatch: {name}")
    require((pose.text or "").strip() == ZERO_POSE, f"link pose value mismatch: {name}")


def validate_joint(joint: ET.Element) -> None:
    name = joint.attrib["name"]
    expected_type, expected_pose, expected_parent, expected_child, expected_axis = JOINTS[name]
    require(joint.attrib.get("type") == expected_type, f"joint type mismatch: {name}")
    pose = exactly_one(joint.findall("./pose"), f"joint pose: {name}")
    require(pose.attrib == {"relative_to": "base_link"}, f"joint pose frame mismatch: {name}")
    require((pose.text or "").strip() == expected_pose, f"joint pose mismatch: {name}")
    require(text_of(joint, "./parent", "joint parent") == expected_parent, f"joint parent mismatch: {name}")
    require(text_of(joint, "./child", "joint child") == expected_child, f"joint child mismatch: {name}")
    if expected_axis is None:
        require(joint.find("./axis") is None, f"fixed joint has axis: {name}")
        return
    axis = exactly_one(joint.findall("./axis"), f"wheel axis: {name}")
    xyz = exactly_one(axis.findall("./xyz"), f"wheel axis vector: {name}")
    require(xyz.attrib == {"expressed_in": "base_link"}, f"wheel axis frame mismatch: {name}")
    require((xyz.text or "").strip() == expected_axis, f"joint axis mismatch: {name}")
    require(axis.find("./limit") is None and axis.find("./dynamics") is None, "limits/dynamics must remain deferred")


def validate_visual_contract(link: ET.Element) -> None:
    name = link.attrib["name"]
    visuals = link.findall("./visual")
    if name not in VISUALS:
        require(not visuals, f"visual is not permitted on {name}")
        return
    visual = exactly_one(visuals, f"{name} visual")
    expected_name, expected_pose, expected_uri, expected_scale = VISUALS[name]
    require(visual.attrib == {"name": expected_name}, f"visual identity mismatch: {name}")
    pose = exactly_one(visual.findall("./pose"), f"visual pose: {name}")
    require(pose.attrib == {"relative_to": name}, f"visual pose frame mismatch: {name}")
    require((pose.text or "").strip() == expected_pose, f"visual pose mismatch: {name}")
    require(text_of(visual, "./geometry/mesh/uri", "visual mesh URI") == expected_uri, f"visual URI mismatch: {name}")
    require(text_of(visual, "./geometry/mesh/scale", "visual mesh scale") == expected_scale, f"visual scale mismatch: {name}")
    require(visual.find("./material") is None, f"visual material is not approved: {name}")
    require(not visual.findall("./plugin"), f"visual plugin is not approved: {name}")


def validate_model_root(root: ET.Element) -> None:
    require(root.tag == "sdf" and root.attrib.get("version") == "1.11", "root must be SDF 1.11")
    model = exactly_one(root.findall("./model"), "model")
    require(model.attrib.get("name") == MODEL_NAME, "unexpected model name")
    links = model.findall("./link")
    require({link.attrib.get("name") for link in links} == set(INERTIALS), "link set mismatch")
    require(len(links) == 7, "expected exactly seven links")
    for link in links:
        validate_pose_relation(link)
        validate_inertial(link, INERTIALS[link.attrib["name"]])
        validate_visual_contract(link)
        require(not link.findall("./sensor") or link.attrib["name"] == LINK_NAME, "only base link may contain sensor")
    base_link = exactly_one(model.findall("./link[@name='base_link']"), "base_link")
    validate_contact(base_link)
    wheel_names = {"Wheel_LF_1", "Wheel_RF_1", "Wheel_RB_1", "Wheel_LB_1"}
    for wheel in wheel_names:
        wheel_link = exactly_one(model.findall(f"./link[@name='{wheel}']"), wheel)
        collision = exactly_one(wheel_link.findall("./collision"), f"{wheel} collision")
        require(text_of(collision, "./pose", f"{wheel} collision pose") == "0 0 0 1.5708 0 0", "wheel collision pose mismatch")
        require(text_of(collision, "./geometry/cylinder/radius", f"{wheel} radius") == "0.0485", "wheel radius mismatch")
        require(text_of(collision, "./geometry/cylinder/length", f"{wheel} length") == "0.04", "wheel length mismatch")
    for name in ("IntelRealsense_D435_Multibody_1", "RPLiDAR_A1M8_1"):
        link = exactly_one(model.findall(f"./link[@name='{name}']"), name)
        require(not link.findall("./collision"), "resource collision parity must remain deferred")
    joints = model.findall("./joint")
    require({joint.attrib.get("name") for joint in joints} == set(JOINTS), "joint set mismatch")
    require(len(joints) == 6, "expected exactly six joints")
    for joint in joints:
        validate_joint(joint)
    require(not model.findall(".//plugin"), "native twin must not contain plugins")
    require(len(model.findall(".//visual")) == 2, "expected exactly two approved visuals")
    serialized = ET.tostring(model, encoding="unicode")
    for literal in FORBIDDEN:
        require(literal not in serialized, f"forbidden literal: {literal}")


def validate_model_config(config_path: Path) -> None:
    root = ET.parse(config_path).getroot()
    require(root.tag == "model", "model.config root must be <model>")
    require(text_of(root, "./name", "model.config name") == MODEL_NAME, "model.config name mismatch")
    sdf = root.find("./sdf")
    require(sdf is not None and sdf.attrib.get("version") == "1.11", "model.config SDF version mismatch")
    require((sdf.text or "").strip() == "model.sdf", "model.config must reference model.sdf")
    require("STATIC_CONTACT_TWIN_NOT_RUNTIME_READY" in text_of(root, "./description", "model.config description"), "missing static-only marker")


def sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_regular_or_expected_source_symlink(path: Path, source: Path, label: str) -> None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as exc:
        raise ValidationError(f"missing installed {label}: {path}") from exc
    if stat.S_ISLNK(mode):
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise ValidationError(f"broken installed {label} symlink: {path}") from exc
        require(resolved == source.resolve(strict=True), f"installed {label} symlink does not resolve to source")
        require(resolved.is_file(), f"installed {label} source target is not regular")
        return
    require(stat.S_ISREG(mode), f"installed {label} must be a regular file or source symlink")


def validate_install_parity(package_root: Path, install_share: Path) -> tuple[str, str]:
    source_model_root = package_root / "models" / MODEL_NAME
    source_model = source_model_root / "model.sdf"
    source_config = source_model_root / "model.config"
    try:
        share_root = install_share.resolve(strict=True)
    except OSError as exc:
        raise ValidationError(f"installed package share unavailable: {install_share}") from exc
    require(share_root.is_dir(), "installed package share is not a directory")
    installed_model_root = share_root / "models" / MODEL_NAME
    installed_model = installed_model_root / "model.sdf"
    installed_config = installed_model_root / "model.config"
    try:
        require(installed_model.parent == installed_model_root, "installed model path escaped model directory")
        require(installed_config.parent == installed_model_root, "installed config path escaped model directory")
        require(installed_model_root.resolve(strict=True).is_relative_to(share_root), "installed model directory is outside package share")
    except OSError as exc:
        raise ValidationError(f"installed model directory unavailable: {installed_model_root}") from exc
    require_regular_or_expected_source_symlink(installed_model, source_model, "model.sdf")
    require_regular_or_expected_source_symlink(installed_config, source_config, "model.config")
    model_sha = sha256_bytes(installed_model)
    config_sha = sha256_bytes(installed_config)
    require(model_sha == sha256_bytes(source_model), "installed model.sdf SHA-256 mismatch")
    require(config_sha == sha256_bytes(source_config), "installed model.config SHA-256 mismatch")
    validate_model_root(ET.parse(installed_model).getroot())
    validate_model_config(installed_config)
    return model_sha, config_sha


def validate_world_contact_system(world_path: Path) -> None:
    root = ET.parse(world_path).getroot()
    worlds = root.findall("./world")
    require(len(worlds) == 1, "expected exactly one world")
    systems = [plugin for plugin in worlds[0].findall("./plugin") if plugin.attrib.get("name") == "gz::sim::systems::Contact"]
    require(len(systems) == 1 and systems[0].attrib.get("filename") == "gz-sim-contact-system", "world Contact system mismatch")


def validate_setup_metadata(setup_path: Path) -> None:
    tree = ast.parse(setup_path.read_text(encoding="utf-8"), filename=str(setup_path))
    constants = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    require("models" in constants and MODEL_NAME in constants, "setup.py does not install native model")


def run_negative_fixtures(root: ET.Element) -> None:
    fixtures = []
    altered = copy.deepcopy(root); altered.find("./model/link[@name='Wheel_LF_1']").clear(); fixtures.append(altered)
    altered = copy.deepcopy(root); altered.find("./model/joint[@name='Wheel_LF_Joint']/parent").text = "wrong"; fixtures.append(altered)
    altered = copy.deepcopy(root); altered.find("./model/joint[@name='Wheel_LF_Joint']/axis/xyz").text = "1 0 0"; fixtures.append(altered)
    altered = copy.deepcopy(root); altered.find("./model/link[@name='base_link']/inertial/mass").text = "3"; fixtures.append(altered)
    altered = copy.deepcopy(root); ET.SubElement(altered.find("./model"), "plugin", {"name": "forbidden"}); fixtures.append(altered)
    altered = copy.deepcopy(root); altered.find("./model/joint[@name='Wheel_LF_Joint']/pose").attrib.clear(); fixtures.append(altered)
    altered = copy.deepcopy(root); altered.find("./model/link[@name='Wheel_LF_1']/pose").attrib["relative_to"] = "base_link"; fixtures.append(altered)
    altered = copy.deepcopy(root); altered.find("./model/link[@name='IntelRealsense_D435_Multibody_1']/pose").attrib["relative_to"] = "Lidar_Joint"; fixtures.append(altered)
    altered = copy.deepcopy(root); altered.find("./model/link[@name='RPLiDAR_A1M8_1']/pose").attrib["relative_to"] = "Camera_Joint"; fixtures.append(altered)
    altered = copy.deepcopy(root); altered.find("./model/joint[@name='Wheel_LF_Joint']/axis/xyz").attrib["expressed_in"] = "Wheel_LF_1"; fixtures.append(altered)
    altered = copy.deepcopy(root); altered.find("./model/link[@name='IntelRealsense_D435_Multibody_1']/visual/geometry/mesh/uri").text = "wrong.stl"; fixtures.append(altered)
    altered = copy.deepcopy(root); altered.find("./model/link[@name='IntelRealsense_D435_Multibody_1']/visual").clear(); fixtures.append(altered)
    altered = copy.deepcopy(root); camera = altered.find("./model/link[@name='IntelRealsense_D435_Multibody_1']"); camera.append(copy.deepcopy(camera.find("./visual"))); fixtures.append(altered)
    altered = copy.deepcopy(root); altered.find("./model/link[@name='RPLiDAR_A1M8_1']/visual/pose").text = "0 0 0 0 0 0"; fixtures.append(altered)
    altered = copy.deepcopy(root); altered.find("./model/link[@name='RPLiDAR_A1M8_1']/visual/geometry/mesh/scale").text = "1 1 1"; fixtures.append(altered)
    altered = copy.deepcopy(root); wheel = altered.find("./model/link[@name='Wheel_LF_1']"); wheel.append(copy.deepcopy(altered.find("./model/link[@name='IntelRealsense_D435_Multibody_1']/visual"))); fixtures.append(altered)
    altered = copy.deepcopy(root); ET.SubElement(altered.find("./model/link[@name='IntelRealsense_D435_Multibody_1']"), "collision", {"name": "forbidden_camera_collision"}); fixtures.append(altered)
    for fixture in fixtures:
        try:
            validate_model_root(fixture)
        except ValidationError:
            continue
        raise AssertionError("negative fixture unexpectedly passed")


def main() -> int:
    package_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=package_root / "models" / MODEL_NAME / "model.sdf")
    parser.add_argument("--config", type=Path, default=package_root / "models" / MODEL_NAME / "model.config")
    parser.add_argument("--world", type=Path, default=package_root / "launch" / "tugbot_depot.sdf")
    parser.add_argument("--setup", type=Path, default=package_root / "setup.py")
    parser.add_argument("--installed-package-share", type=Path)
    parser.add_argument("--negative-fixtures", action="store_true")
    args = parser.parse_args()
    root = ET.parse(args.model).getroot()
    validate_model_root(root)
    validate_model_config(args.config)
    validate_world_contact_system(args.world)
    validate_setup_metadata(args.setup)
    if args.installed_package_share is not None:
        model_sha, config_sha = validate_install_parity(package_root, args.installed_package_share)
        print(f"installed_model_sha256={model_sha}")
        print(f"installed_config_sha256={config_sha}")
    if args.negative_fixtures:
        run_negative_fixtures(root)
    print("native_sdf_contact_twin=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ET.ParseError, ValidationError, OSError, SyntaxError) as exc:
        print(f"native_sdf_contact_twin=FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
