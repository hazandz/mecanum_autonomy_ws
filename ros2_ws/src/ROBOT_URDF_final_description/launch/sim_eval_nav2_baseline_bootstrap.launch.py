"""Bootstrap the selected Tugbot depot world and the sole robot_state_publisher."""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
import xacro

FUEL_URIS = {
    "https://fuel.gazebosim.org/1.0/OpenRobotics/models/Depot": (
        "openrobotics", "depot", "OpenRobotics/Depot"
    ),
    "https://fuel.gazebosim.org/1.0/MovAi/models/Tugbot": (
        "movai", "tugbot", "MovAi/Tugbot"
    ),
}
WORLD_NAME = "world_demo"
ENTITY_NAME = "ROBOT_URDF_final"


def validate_partition(partition: str) -> str:
    if not isinstance(partition, str) or not partition.strip():
        raise RuntimeError("SIM_EVAL_GZ_PARTITION_REQUIRED")
    return partition


def validate_fuel_cache(sdf_path: str | Path, fuel_cache_root: str | Path) -> dict[str, Path]:
    """Validate the Owner-pinned Fuel URI cache binding without network access."""
    raw_root = Path(fuel_cache_root)
    expected_root = Path.home() / ".gz" / "fuel"
    if not raw_root.is_absolute():
        raise RuntimeError("SIM_EVAL_FUEL_CACHE_ROOT_MUST_BE_ABSOLUTE")
    try:
        root = raw_root.resolve(strict=True)
        canonical_root = expected_root.resolve(strict=False)
    except OSError as error:
        raise RuntimeError("SIM_EVAL_FUEL_CACHE_ROOT_INVALID") from error
    if root != canonical_root:
        raise RuntimeError("SIM_EVAL_FUEL_CACHE_ROOT_NOT_CANONICAL_HOME_CACHE")
    return validate_fuel_layout(sdf_path, root)


def validate_fuel_layout(sdf_path: str | Path, root: str | Path) -> dict[str, Path]:
    """Validate the pinned URI/version layout under a supplied root (offline-test seam)."""
    root = Path(root).resolve(strict=True)
    try:
        document = ET.parse(sdf_path).getroot()
    except (OSError, ET.ParseError) as error:
        raise RuntimeError("SIM_EVAL_WORLD_SDF_INVALID") from error
    uris = [element.text.strip() for element in document.iter("uri") if element.text]
    if len(uris) != 2 or set(uris) != set(FUEL_URIS):
        raise RuntimeError("SIM_EVAL_FUEL_URI_SET_MISMATCH")
    resolved: dict[str, Path] = {}
    for uri, (owner, model, identity) in FUEL_URIS.items():
        original_owner, original_model = identity.split("/", maxsplit=1)
        uppercase_parent = root / "fuel.gazebosim.org" / original_owner / "models" / original_model
        if os.path.lexists(uppercase_parent):
            raise RuntimeError(f"SIM_EVAL_FUEL_CACHE_PATH_CASE_MISMATCH:{identity}")
        parent = root / "fuel.gazebosim.org" / owner / "models" / model
        try:
            parent_real = parent.resolve(strict=True)
        except OSError as error:
            raise RuntimeError(f"SIM_EVAL_FUEL_CACHE_MODEL_MISSING:{identity}") from error
        if not parent_real.is_relative_to(root):
            raise RuntimeError("SIM_EVAL_FUEL_CACHE_PATH_ESCAPES_ROOT")
        versions = []
        for child in parent.iterdir():
            if not re.fullmatch(r"[0-9]+", child.name) or int(child.name) <= 0:
                continue
            try:
                real = child.resolve(strict=True)
            except OSError:
                continue
            if real.is_relative_to(root) and real.is_dir():
                versions.append((child, real))
        if len(versions) != 1:
            raise RuntimeError("SIM_EVAL_FUEL_CACHE_VERSION_AMBIGUOUS_OR_MISSING")
        version_path, real_version = versions[0]
        config = version_path / "model.config"
        model_sdf = version_path / "model.sdf"
        if not config.is_file() or not model_sdf.is_file():
            raise RuntimeError(f"SIM_EVAL_FUEL_CACHE_MODEL_CONTENT_MISSING:{identity}")
        content_paths = [config, model_sdf]
        if any(not path.resolve(strict=True).is_relative_to(root) for path in content_paths):
            raise RuntimeError("SIM_EVAL_FUEL_CACHE_PATH_ESCAPES_ROOT")
        resolved[uri] = real_version
    return resolved


def _actions(context):
    partition = validate_partition(LaunchConfiguration("gz_partition").perform(context))
    fuel_cache_root = LaunchConfiguration("fuel_cache_root").perform(context)
    # Map-frame initial pose is passed to AMCL by the composite launch. It is
    # deliberately not treated as a world-frame transform or Gazebo spawn pose.
    pose = {name: LaunchConfiguration(name).perform(context) for name in (
        "initial_pose_map_x", "initial_pose_map_y", "initial_pose_map_yaw"
    )}
    for name, value in pose.items():
        try:
            number = float(value)
        except ValueError as error:
            raise RuntimeError(f"INVALID_REQUIRED_{name.upper()}") from error
        if not __import__("math").isfinite(number):
            raise RuntimeError(f"INVALID_REQUIRED_{name.upper()}")

    ros_gz_sim_share = get_package_share_directory("ros_gz_sim")
    robot_share = get_package_share_directory("ROBOT_URDF_final_description")
    parent_resources = os.path.dirname(robot_share)
    existing_resources = os.environ.get("GZ_SIM_RESOURCE_PATH", "")
    resource_path = ":".join(item for item in (parent_resources, existing_resources) if item)
    world = os.path.join(robot_share, "launch", "tugbot_depot.sdf")
    validate_fuel_cache(world, fuel_cache_root)
    xacro_path = os.path.join(robot_share, "urdf", "ROBOT_URDF_final.xacro")
    description = {"robot_description": xacro.process_file(xacro_path).toxml()}
    return [
        SetEnvironmentVariable("GZ_SIM_RESOURCE_PATH", resource_path),
        SetEnvironmentVariable("GZ_PARTITION", partition),
        Node(
            package="robot_state_publisher", executable="robot_state_publisher",
            name="robot_state_publisher", parameters=[description, {"use_sim_time": True}],
            output="screen",
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(ros_gz_sim_share, "launch", "gz_sim.launch.py")),
            launch_arguments={"gz_args": f"-r -s -v 4 {world}"}.items(),
        ),
        Node(
            package="ros_gz_sim", executable="create", name="spawn_robot",
            arguments=["-world", WORLD_NAME, "-topic", "/robot_description", "-name", ENTITY_NAME,
                       "-allow_renaming", "false", "-x", "0", "-y", "0", "-z", "0.1", "-Y", "0"],
            output="screen",
        ),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("gz_partition"),
        DeclareLaunchArgument("fuel_cache_root"),
        DeclareLaunchArgument("initial_pose_map_x"),
        DeclareLaunchArgument("initial_pose_map_y"),
        DeclareLaunchArgument("initial_pose_map_yaw"),
        OpaqueFunction(function=_actions),
    ])
