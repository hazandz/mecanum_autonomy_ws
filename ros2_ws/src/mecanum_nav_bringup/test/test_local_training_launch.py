"""Launch contract tests use byte fixtures and never spawn child processes."""
import xml.etree.ElementTree as ET
from pathlib import Path

from mecanum_nav_bringup.local_training_launch_contract import (
    bind_world_for_scenario, parse_gui_argument,
)

import pytest


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
        ),
    )
    noncontact = ET.fromstring(
        bind_world_for_scenario(
            source, model, 'B2_SOAK_V1', 'run-2', hash_value, hash_value,
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


def test_bound_world_rejects_missing_identity_or_backend():
    """A world without the bound model identity is rejected."""
    source = b"<sdf version='1.11'><world name='bad'/></sdf>"
    with pytest.raises(ValueError, match='mecanum_b2'):
        bind_world_for_scenario(
            source, b"<sdf version='1.11'><model name='mecanum_b2'/></sdf>",
            'B2_SOAK_V1', 'run', 'a' * 64, 'b' * 64,
        )
