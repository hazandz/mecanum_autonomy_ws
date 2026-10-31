"""Launch contract tests use byte fixtures and never spawn child processes."""
import xml.etree.ElementTree as ET
from pathlib import Path

from mecanum_nav_bringup.local_training_launch_contract import (
    bind_world_for_scenario, parse_gui_argument,
)

import pytest

import yaml


def test_gui_argument_accepts_only_exact_values():
    """Only lowercase exact GUI values are accepted."""
    assert parse_gui_argument('true') is True
    assert parse_gui_argument('false') is False
    for value in ('True', 'False', '1', '0', 'yes', ' false ', ''):
        with pytest.raises(ValueError, match='exactly'):
            parse_gui_argument(value)


def test_scenario_binding_includes_probe_only_for_contact_and_binds_identity():
    """Contact scenario adds the probe and all scenarios bind identity."""
    root = Path(__file__).resolve().parents[4]
    source = (
        root / 'ros2_ws/src/ROBOT_URDF_final_description/worlds/'
        'b2_training_arena.sdf'
    ).read_bytes()
    model = (
        root / 'ros2_ws/src/ROBOT_URDF_final_description/models/'
        'mecanum_b2/model.sdf'
    ).read_bytes()
    hash_value = 'a' * 64
    contact = ET.fromstring(
        bind_world_for_scenario(
            source, model, 'B2_CONTACT_V1', 'run-1', hash_value, hash_value,
            17,
        ),
    )
    noncontact = ET.fromstring(
        bind_world_for_scenario(
            source, model, 'B2_SOAK_V1', 'run-2', hash_value, hash_value,
            18,
        ),
    )
    assert contact.find(".//include[@name='b2_contact_probe']") is not None
    assert noncontact.find(".//include[@name='b2_contact_probe']") is None
    assert contact.findtext(
        ".//plugin[@name='mecanum_sim_backend::BackendSystem']/session_id",
    ) == 'run-1'
    assert contact.findtext(
        ".//plugin[@name='mecanum_sim_backend::BackendSystem']/config_hash",
    ) == hash_value
    assert contact.findtext(
        './/plugin[@name="mecanum_sim_backend::BackendSystem"]/'
        'coordinator_ingress_instance_id',
    ) == '17'


def test_bound_world_rejects_missing_identity_or_backend():
    """A world without the bound model identity is rejected."""
    source = b"<sdf version='1.11'><world name='bad'/></sdf>"
    with pytest.raises(ValueError, match='mecanum_b2'):
        bind_world_for_scenario(
            source, b"<sdf version='1.11'><model name='mecanum_b2'/></sdf>",
            'B2_SOAK_V1', 'run', 'a' * 64, 'b' * 64, 17,
        )


def test_bridge_contains_exact_fixture_service_mappings():
    """The installed bridge contract declares the three fixture services."""
    root = Path(__file__).resolve().parents[4]
    config = yaml.safe_load((
        root / 'ros2_ws/src/mecanum_nav_bringup/config/bridge/'
        'local_training.runtime.yaml'
    ).read_text(encoding='utf-8'))
    services = {
        item['service_name']: (
            item['ros_type_name'], item['gz_req_type_name'],
            item['gz_rep_type_name'],
        )
        for item in config if 'service_name' in item
    }
    assert services['/world/b2_training_arena/create'] == (
        'ros_gz_interfaces/srv/SpawnEntity',
        'gz.msgs.EntityFactory', 'gz.msgs.Boolean',
    )
    assert services['/world/b2_training_arena/set_pose'] == (
        'ros_gz_interfaces/srv/SetEntityPose',
        'gz.msgs.Pose', 'gz.msgs.Boolean',
    )
    assert services['/world/b2_training_arena/remove'] == (
        'ros_gz_interfaces/srv/DeleteEntity',
        'gz.msgs.Entity', 'gz.msgs.Boolean',
    )
    assert services['/world/b2_training_arena/control'] == (
        'ros_gz_interfaces/srv/ControlWorld',
        'gz.msgs.WorldControl', 'gz.msgs.Boolean',
    )
    assert len(services) == 4
