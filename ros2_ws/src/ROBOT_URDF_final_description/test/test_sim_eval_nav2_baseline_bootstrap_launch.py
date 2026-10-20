"""Static import contract for the bootstrap; no launch execution occurs."""
from pathlib import Path
import importlib.util
import shutil
import pytest

from launch import LaunchDescription

ROOT = Path(__file__).resolve().parents[4]


def test_bootstrap_launch_imports_without_starting_processes(monkeypatch, tmp_path) -> None:
    import importlib.util

    monkeypatch.setenv("ROS_HOME", str(tmp_path / "ros_home"))
    monkeypatch.setenv("ROS_LOG_DIR", str(tmp_path / "ros_log"))

    path = ROOT / "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_nav2_baseline_bootstrap.launch.py"
    spec = importlib.util.spec_from_file_location("sim_eval_nav2_baseline_bootstrap", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert isinstance(module.generate_launch_description(), LaunchDescription)


def test_bootstrap_requires_explicit_partition_and_map_initial_pose() -> None:
    path = ROOT / "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_nav2_baseline_bootstrap.launch.py"
    source = path.read_text(encoding="utf-8")
    for argument in ("gz_partition", "fuel_cache_root", "initial_pose_map_x", "initial_pose_map_y", "initial_pose_map_yaw"):
        assert f'DeclareLaunchArgument("{argument}")' in source
    assert 'SetEnvironmentVariable("GZ_PARTITION", partition)' in source
    assert 'package="robot_state_publisher"' in source
    assert "Map-frame initial pose" in source
    assert "world-frame transform" in source
    assert "wp06_scan_probe_run_002" not in source
    assert "Path.cwd()" not in source
    assert "requests." not in source and "urlopen(" not in source
    assert "fuel download" not in source.lower()


def _module():
    path = ROOT / "ros2_ws/src/ROBOT_URDF_final_description/launch/sim_eval_nav2_baseline_bootstrap.launch.py"
    spec = importlib.util.spec_from_file_location("sim_eval_bootstrap_fuel_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _synthetic_sdf(path: Path, uris=None) -> Path:
    uris = uris or [
        "https://fuel.gazebosim.org/1.0/OpenRobotics/models/Depot",
        "https://fuel.gazebosim.org/1.0/MovAi/models/Tugbot",
    ]
    path.write_text("<sdf><world name='w'>" + "".join(f"<include><uri>{uri}</uri></include>" for uri in uris) + "</world></sdf>", encoding="utf-8")
    return path


def _cache(root: Path, owner: str, model: str, version: str = "1") -> Path:
    version_dir = root / "fuel.gazebosim.org" / owner / "models" / model / version
    version_dir.mkdir(parents=True)
    (version_dir / "model.config").write_text("<model/>", encoding="utf-8")
    (version_dir / "model.sdf").write_text("<sdf/>", encoding="utf-8")
    return version_dir


def test_exact_fuel_uris_and_single_complete_cache_versions_are_accepted(tmp_path) -> None:
    module = _module()
    sdf = _synthetic_sdf(tmp_path / "world.sdf")
    root = tmp_path / "fuel"
    _cache(root, "openrobotics", "depot")
    _cache(root, "movai", "tugbot")
    resolved = module.validate_fuel_layout(sdf, root)
    assert set(resolved) == set(module.FUEL_URIS)
    actual = ROOT / "ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf"
    import xml.etree.ElementTree as ET
    actual_uris = [e.text.strip() for e in ET.parse(actual).getroot().iter("uri") if e.text]
    assert actual_uris == list(module.FUEL_URIS)
    assert module.validate_partition("owner-selected-partition") == "owner-selected-partition"
    with pytest.raises(RuntimeError, match="SIM_EVAL_GZ_PARTITION_REQUIRED"):
        module.validate_partition("")
    with pytest.raises(RuntimeError, match="SIM_EVAL_GZ_PARTITION_REQUIRED"):
        module.validate_partition("   ")


def test_fuel_cache_root_must_be_absolute_and_canonical_home_cache(tmp_path) -> None:
    module = _module()
    sdf = _synthetic_sdf(tmp_path / "world.sdf")
    with pytest.raises(RuntimeError, match="SIM_EVAL_FUEL_CACHE_ROOT_MUST_BE_ABSOLUTE"):
        module.validate_fuel_cache(sdf, "relative/cache")
    with pytest.raises(RuntimeError, match="SIM_EVAL_FUEL_CACHE_ROOT_NOT_CANONICAL_HOME_CACHE"):
        module.validate_fuel_cache(sdf, str(tmp_path))


def test_missing_each_model_is_rejected(tmp_path) -> None:
    module = _module()
    sdf = _synthetic_sdf(tmp_path / "world.sdf")
    root = tmp_path / "fuel"
    _cache(root, "movai", "tugbot")
    with pytest.raises(RuntimeError, match="SIM_EVAL_FUEL_CACHE_MODEL_MISSING:OpenRobotics/Depot"):
        module.validate_fuel_layout(sdf, root)
    shutil.rmtree(root / "fuel.gazebosim.org" / "movai")
    _cache(root, "openrobotics", "depot")
    with pytest.raises(RuntimeError, match="SIM_EVAL_FUEL_CACHE_MODEL_MISSING:MovAi/Tugbot"):
        module.validate_fuel_layout(sdf, root)


def test_missing_model_config_or_sdf_is_rejected(tmp_path) -> None:
    module = _module()
    sdf = _synthetic_sdf(tmp_path / "world.sdf")
    root = tmp_path / "fuel"
    depot = _cache(root, "openrobotics", "depot")
    _cache(root, "movai", "tugbot")
    (depot / "model.config").unlink()
    with pytest.raises(RuntimeError, match="SIM_EVAL_FUEL_CACHE_MODEL_CONTENT_MISSING:OpenRobotics/Depot"):
        module.validate_fuel_layout(sdf, root)
    (depot / "model.config").write_text("<model/>", encoding="utf-8")
    (depot / "model.sdf").unlink()
    with pytest.raises(RuntimeError, match="SIM_EVAL_FUEL_CACHE_MODEL_CONTENT_MISSING:OpenRobotics/Depot"):
        module.validate_fuel_layout(sdf, root)


def test_ambiguous_versions_and_case_mismatched_uris_fail_closed(tmp_path) -> None:
    module = _module()
    sdf = _synthetic_sdf(tmp_path / "world.sdf")
    root = tmp_path / "fuel"
    _cache(root, "openrobotics", "depot", "1")
    _cache(root, "openrobotics", "depot", "2")
    _cache(root, "movai", "tugbot")
    with pytest.raises(RuntimeError, match="SIM_EVAL_FUEL_CACHE_VERSION_AMBIGUOUS_OR_MISSING"):
        module.validate_fuel_layout(sdf, root)
    changed = _synthetic_sdf(tmp_path / "case.sdf", [
        "https://fuel.gazebosim.org/1.0/openrobotics/models/Depot",
        "https://fuel.gazebosim.org/1.0/MovAi/models/Tugbot",
    ])
    with pytest.raises(RuntimeError, match="SIM_EVAL_FUEL_URI_SET_MISMATCH"):
        module.validate_fuel_layout(changed, root)


def test_cache_symlink_cannot_escape_selected_root(tmp_path) -> None:
    module = _module()
    sdf = _synthetic_sdf(tmp_path / "world.sdf")
    root = tmp_path / "fuel"
    _cache(root, "movai", "tugbot")
    outside = _cache(tmp_path / "outside", "openrobotics", "depot")
    parent = root / "fuel.gazebosim.org" / "openrobotics" / "models"
    parent.mkdir(parents=True)
    (parent / "depot").symlink_to(outside.parent, target_is_directory=True)
    with pytest.raises(RuntimeError, match="SIM_EVAL_FUEL_CACHE_PATH_ESCAPES_ROOT"):
        module.validate_fuel_layout(sdf, root)


def test_uppercase_fuel_parent_is_rejected_even_when_lowercase_cache_is_valid(tmp_path) -> None:
    module = _module()
    sdf = _synthetic_sdf(tmp_path / "world.sdf")
    root = tmp_path / "fuel"
    _cache(root, "openrobotics", "depot")
    _cache(root, "movai", "tugbot")
    uppercase = root / "fuel.gazebosim.org" / "OpenRobotics" / "models" / "Depot"
    uppercase.mkdir(parents=True)
    with pytest.raises(RuntimeError, match="SIM_EVAL_FUEL_CACHE_PATH_CASE_MISMATCH:OpenRobotics/Depot"):
        module.validate_fuel_layout(sdf, root)


@pytest.mark.parametrize("version", ["0", "-1", "1.0", "latest"])
def test_non_positive_or_non_integer_version_is_rejected(tmp_path, version) -> None:
    module = _module()
    sdf = _synthetic_sdf(tmp_path / "world.sdf")
    root = tmp_path / "fuel"
    _cache(root, "openrobotics", "depot", version)
    _cache(root, "movai", "tugbot")
    with pytest.raises(RuntimeError, match="SIM_EVAL_FUEL_CACHE_VERSION_AMBIGUOUS_OR_MISSING"):
        module.validate_fuel_layout(sdf, root)
