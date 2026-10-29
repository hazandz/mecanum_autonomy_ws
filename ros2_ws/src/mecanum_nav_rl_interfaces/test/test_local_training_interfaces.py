"""Offline declaration and generated-message tests for the B2.1 interfaces."""

from __future__ import annotations

import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from builtin_interfaces.msg import Time

from mecanum_nav_rl_interfaces.msg import LocalTrainingSafetyInput
from mecanum_nav_rl_interfaces.msg import SimulationContactState

from rclpy.serialization import deserialize_message, serialize_message


_PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def _fields(path: Path) -> list[tuple[str, str]]:
    fields = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.split('#', 1)[0].strip()
        match = re.fullmatch('(.+?)\\s+([A-Za-z][A-Za-z0-9_]*)', line)
        if match and not re.match('^[A-Za-z0-9_]+\\s+[A-Za-z0-9_]+=', line):
            fields.append((match.group(2), match.group(1)))
    return fields


def test_safety_input_field_order_types_bounds_and_constants() -> None:
    """Check the safety-only message declaration and generated bounds."""
    assert _fields(_PACKAGE_ROOT / 'msg/LocalTrainingSafetyInput.msg') == [
        ('header', 'std_msgs/Header'),
        ('schema_version', 'uint16'),
        ('session_id', 'string<=64'),
        ('config_hash', 'string<=64'),
        ('ingress_instance_id', 'uint64'),
        ('sample_sequence', 'uint64'),
        ('episode_generation', 'uint64'),
        ('reset_epoch', 'uint32'),
        ('runtime_generation', 'uint32'),
        ('odometry_status', 'uint8'),
        ('measured_twist', 'float64[<=3]'),
        ('admission_state', 'uint8'),
        ('observation0_cutoff', 'builtin_interfaces/Time'),
        ('observation0_final_publisher_instance_id', 'uint64'),
        ('observation0_final_publish_sequence', 'uint64'),
    ]
    assert LocalTrainingSafetyInput.SCHEMA_VERSION == 1
    assert (LocalTrainingSafetyInput.ODOM_VALID,
            LocalTrainingSafetyInput.ODOM_DELAYED,
            LocalTrainingSafetyInput.ODOM_DROPPED) == (0, 1, 2)
    assert (LocalTrainingSafetyInput.ADMISSION_INHIBITED,
            LocalTrainingSafetyInput.ADMISSION_ZERO_ONLY,
            LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN) == (0, 1, 2)
    generated_types = LocalTrainingSafetyInput.get_fields_and_field_types()
    assert generated_types['session_id'] == 'string<64>'
    assert generated_types['config_hash'] == 'string<64>'
    assert generated_types['measured_twist'] == 'sequence<double, 3>'


def test_contact_state_field_order_types_fault_bits_and_constants() -> None:
    """Check contact coverage fields and bit-mask constants."""
    assert _fields(_PACKAGE_ROOT / 'msg/SimulationContactState.msg') == [
        ('header', 'std_msgs/Header'),
        ('schema_version', 'uint16'),
        ('session_id', 'string<=64'),
        ('config_hash', 'string<=64'),
        ('backend_instance_id', 'uint64'),
        ('status_sequence', 'uint64'),
        ('episode_generation', 'uint64'),
        ('reset_epoch', 'uint32'),
        ('runtime_generation', 'uint32'),
        ('physics_iteration', 'uint64'),
        ('required_collision_mask', 'uint64'),
        ('observed_collision_mask', 'uint64'),
        ('coverage_complete', 'bool'),
        ('contact_source_healthy', 'bool'),
        ('contact_active', 'bool'),
        ('paused', 'bool'),
        ('actuator_inhibited', 'bool'),
        ('local_zero_override', 'bool'),
        ('fault_flags', 'uint32'),
        ('applied_receipt_valid', 'bool'),
        ('applied_final_publisher_instance_id', 'uint64'),
        ('applied_final_publish_sequence', 'uint64'),
        ('applied_physics_iteration', 'uint64'),
        ('applied_sim_stamp', 'builtin_interfaces/Time'),
    ]
    assert SimulationContactState.SCHEMA_VERSION == 1
    assert [getattr(SimulationContactState, name) for name in (
        'FAULT_CONTEXT', 'FAULT_COMMAND_SEQUENCE', 'FAULT_COMMAND_STALE',
        'FAULT_COMMAND_INVALID', 'FAULT_CONTACT_COVERAGE',
        'FAULT_CONTACT_CLASSIFICATION', 'FAULT_CLOCK', 'FAULT_ACTUATOR',
        'FAULT_QUEUE',
    )] == [1, 2, 4, 8, 16, 32, 64, 128, 256]
    generated_types = SimulationContactState.get_fields_and_field_types()
    assert generated_types['session_id'] == 'string<64>'
    assert generated_types['config_hash'] == 'string<64>'


def test_generated_messages_round_trip_without_ros_context() -> None:
    """Round-trip generated interfaces without starting a ROS context."""
    safety = LocalTrainingSafetyInput()
    safety.header.stamp = Time(sec=10, nanosec=20)
    safety.header.frame_id = 'base_link'
    safety.schema_version = 1
    safety.session_id = 'session'
    safety.config_hash = 'a' * 64
    safety.ingress_instance_id = 3
    safety.sample_sequence = 4
    safety.episode_generation = 5
    safety.reset_epoch = 6
    safety.runtime_generation = 7
    safety.odometry_status = LocalTrainingSafetyInput.ODOM_VALID
    safety.measured_twist = [0.1, -0.2, 0.3]
    safety.admission_state = LocalTrainingSafetyInput.ADMISSION_ZERO_ONLY
    safety.observation0_cutoff = Time(sec=11, nanosec=12)
    raw = serialize_message(safety)
    restored = deserialize_message(raw, LocalTrainingSafetyInput)
    assert list(restored.measured_twist) == [0.1, -0.2, 0.3]
    assert restored.header.frame_id == 'base_link'
    assert restored.observation0_cutoff == safety.observation0_cutoff

    state = SimulationContactState()
    state.header.stamp = Time(sec=12, nanosec=13)
    state.header.frame_id = 'world'
    state.schema_version = 1
    state.session_id = 'session'
    state.config_hash = 'b' * 64
    state.backend_instance_id = 9
    state.status_sequence = 10
    state.episode_generation = 11
    state.reset_epoch = 12
    state.runtime_generation = 13
    state.physics_iteration = 14
    state.required_collision_mask = 3
    state.observed_collision_mask = 3
    state.coverage_complete = True
    state.contact_source_healthy = True
    state.contact_active = False
    state.applied_sim_stamp = Time(sec=12, nanosec=14)
    restored_state = deserialize_message(
        serialize_message(state), SimulationContactState
    )
    assert restored_state.required_collision_mask == 3
    assert restored_state.applied_sim_stamp == state.applied_sim_stamp


def test_rosidl_package_version_generation_and_legacy_message_bytes() -> None:
    """Pin package generation and preserve every prior message definition."""
    package = ET.parse(_PACKAGE_ROOT / 'package.xml').getroot()
    assert package.findtext('version') == '2.6.0'
    cmake = (_PACKAGE_ROOT / 'CMakeLists.txt').read_text(encoding='utf-8')
    generation = re.search(
        'rosidl_generate_interfaces\\(\\$\\{PROJECT_NAME\\}(.*?)\\n\\)',
        cmake,
        re.DOTALL,
    )
    assert generation is not None
    generated = re.findall('"(msg/[^"\\n]+\\.msg)"', generation.group(1))
    assert generated == [
        'msg/Heartbeat.msg', 'msg/SafetyState.msg', 'msg/NavigationState.msg',
        'msg/CommandEnvelope.msg', 'msg/FinalIssuedCommandReceipt.msg',
        'msg/SafetyLifecycleState.msg', 'msg/LocalTrainingSafetyInput.msg',
        'msg/SimulationContactState.msg',
    ]
    repository_root = _PACKAGE_ROOT.parents[2]
    base = 'bbd5a3c68e6745b5d143688266e044fa25093390'
    for message_path in generated[:-2]:
        current = (_PACKAGE_ROOT / message_path).read_bytes()
        original = subprocess.check_output(
            [
                'git',
                'show',
                f'{base}:ros2_ws/src/mecanum_nav_rl_interfaces/{message_path}',
            ],
            cwd=repository_root,
        )
        assert current == original, message_path
