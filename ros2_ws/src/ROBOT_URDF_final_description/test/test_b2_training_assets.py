"""Static checks for Roadmap B source assets; never start Gazebo."""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]


def test_b2_world_and_models_are_versioned_local_assets() -> None:
    """B2 world/model source files have the approved static identities."""
    world = ET.parse(_ROOT / 'worlds/b2_training_arena.sdf').getroot()
    assert world.attrib['version'] == '1.11'
    world_node = world.find('world')
    assert (
        world_node is not None
        and world_node.attrib['name'] == 'b2_training_arena'
    )
    physics = world_node.find('physics')
    assert physics is not None
    assert float(physics.findtext('max_step_size', '0')) == 0.01
    assert float(physics.findtext('real_time_factor', '0')) == 1.0
    model = (
        ET.parse(_ROOT / 'models/mecanum_b2/model.sdf')
        .getroot()
        .find('model')
    )
    assert model is not None and model.attrib['name'] == 'mecanum_b2'
    serialized = ET.tostring(model, encoding='unicode')
    for prohibited in (
        'VelocityControl', 'MecanumDrive', 'ros2_control', 'FollowPath',
    ):
        assert prohibited not in serialized
    assert 'mecanum_sim_backend::BackendSystem' in serialized
    assert 'NATIVE_B2_BACKEND_PENDING' not in serialized
    assert (
        'REQUIRED_RESOLVED_CONFIG_HASH' in serialized
    )  # launcher binds before spawn


def test_b2_sensor_geometry_and_extrinsic_match_approved_profile() -> None:
    """The LiDAR and static transform match the approved profile."""
    model = ET.parse(_ROOT / 'models/mecanum_b2/model.sdf').getroot()
    sensor = model.find(".//sensor[@type='gpu_lidar']")
    assert sensor is not None and sensor.attrib['name'] == 'B2_GENERIC_2D_V1'
    assert float(sensor.findtext('update_rate', '0')) == 10.0
    assert sensor.findtext('topic') == '/b2/scan'
    assert sensor.findtext('./lidar/scan/horizontal/samples') == '500'
    assert float(sensor.findtext('./lidar/range/min', '0')) == 0.1
    assert float(sensor.findtext('./lidar/range/max', '0')) == 8.0
    urdf = ET.parse(_ROOT / 'urdf/mecanum_b2_static.urdf').getroot()
    origin = urdf.find('joint/origin')
    assert origin is not None
    assert origin.attrib == {'xyz': '-0.031765 0 0.140', 'rpy': '0 0 0'}
    for expected in ('0.4 0.28 0.10', '0.0485', '0.04'):
        assert expected in ET.tostring(model, encoding='unicode')


def test_contact_probe_is_an_installed_asset_not_a_runtime_claim() -> None:
    """The probe source is an asset and makes no runtime claim."""
    probe = ET.parse(_ROOT / 'models/b2_contact_probe/model.sdf').getroot()
    collision = probe.find(".//collision[@name='collision']")
    assert collision is not None
    assert collision.findtext('geometry/box/size') == '0.10 0.10 0.10'
    manifest_module = (
        _ROOT.parents[2]
        / 'ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/'
        'simulation/training_asset_binding.py'
    ).read_text()
    assert "'active_contact_probe': name == 'B2_CONTACT_V1'" in manifest_module


def test_mesh_uris_resolve_through_canonical_installed_description_share(
) -> None:
    """Mesh resource URIs use the description package share."""
    model = (_ROOT / 'models/mecanum_b2/model.sdf').read_text()
    uris = re.findall(r'<uri>(.*?)</uri>', model)
    assert uris
    for uri in uris:
        if uri.startswith('model://ROBOT_URDF_final_description/meshes/'):
            leaf = uri.rsplit('/', 1)[-1]
            assert (_ROOT / 'meshes' / leaf).is_file()


def test_b2_installed_world_models_urdf_and_manifest_are_byte_equal() -> None:
    """Installed B2 assets are byte-equal to their source files."""
    raw_base = os.environ.get('MECANUM_ROBOT_DESCRIPTION_INSTALL_BASE')
    assert raw_base, 'MECANUM_ROBOT_DESCRIPTION_INSTALL_BASE_REQUIRED'
    base = Path(raw_base).resolve(strict=True)
    from ament_index_python.packages import get_package_share_directory
    share = Path(
        get_package_share_directory('ROBOT_URDF_final_description'),
    ).resolve(strict=True)
    assert share.is_relative_to(base)
    repo_root = _ROOT.parents[2]
    assets = (
        (
            'worlds/b2_training_arena.sdf',
            'ros2_ws/src/ROBOT_URDF_final_description/worlds/'
            'b2_training_arena.sdf',
        ),
        (
            'models/mecanum_b2/model.config',
            'ros2_ws/src/ROBOT_URDF_final_description/models/'
            'mecanum_b2/model.config',
        ),
        (
            'models/mecanum_b2/model.sdf',
            'ros2_ws/src/ROBOT_URDF_final_description/models/'
            'mecanum_b2/model.sdf',
        ),
        (
            'models/b2_contact_probe/model.config',
            'ros2_ws/src/ROBOT_URDF_final_description/models/'
            'b2_contact_probe/model.config',
        ),
        (
            'models/b2_contact_probe/model.sdf',
            'ros2_ws/src/ROBOT_URDF_final_description/models/'
            'b2_contact_probe/model.sdf',
        ),
        (
            'urdf/mecanum_b2_static.urdf',
            'ros2_ws/src/ROBOT_URDF_final_description/urdf/'
            'mecanum_b2_static.urdf',
        ),
        (
            'manifests/b2/asset_manifest.json',
            'artifacts/simulation/roadmap_b_b2/asset_manifest.json',
        ),
    )
    for installed_rel, source_rel in assets:
        installed = share / installed_rel
        source = repo_root / source_rel
        assert installed.resolve().is_relative_to(base)
        assert installed.is_file() and source.is_file()
        assert installed.read_bytes() == source.read_bytes()
