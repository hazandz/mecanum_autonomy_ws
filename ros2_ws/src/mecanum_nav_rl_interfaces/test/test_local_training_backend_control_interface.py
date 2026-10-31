"""Static and generated-type checks for the B2.2 control service."""

from __future__ import annotations

import re
from pathlib import Path

from builtin_interfaces.msg import Time

from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl

from rclpy.serialization import deserialize_message, serialize_message


SERVICE_PATH = Path(__file__).resolve().parents[1] / 'srv'
SERVICE = SERVICE_PATH / 'LocalTrainingBackendControl.srv'


def _sections() -> tuple[list[str], list[str]]:
    request, response = SERVICE.read_text(encoding='utf-8').split('---')
    return request.splitlines(), response.splitlines()


def _fields(lines: list[str]) -> list[tuple[str, str]]:
    fields = []
    for line in lines:
        declaration = line.split('#', 1)[0].strip()
        match = re.fullmatch(r'(.+?)\s+([A-Za-z][A-Za-z0-9_]*)', declaration)
        if match:
            fields.append((match.group(2), match.group(1)))
    return fields


def test_request_and_response_field_order_types_and_bounds() -> None:
    """Pin service field declarations and generated bounded-string types."""
    request_lines, response_lines = _sections()
    assert _fields(request_lines) == [
        ('schema_version', 'uint16'), ('operation', 'uint8'),
        ('probe_action', 'uint8'),
        ('coordinator_ingress_instance_id', 'uint64'),
        ('request_sequence', 'uint64'),
        ('expected_binding_revision', 'uint64'),
        ('expected_backend_instance_id', 'uint64'),
        ('session_id', 'string<=64'),
        ('config_hash', 'string<=64'), ('asset_manifest_sha256', 'string<=64'),
        ('episode_generation', 'uint64'), ('reset_epoch', 'uint32'),
        ('runtime_generation', 'uint32'), ('lifecycle_sequence', 'uint64'),
        ('primary_state', 'uint8'), ('barrier_state', 'uint8'),
        ('lifecycle_header_stamp', 'builtin_interfaces/Time'),
        ('lifecycle_frame_id', 'string<=64'),
        ('barrier_stamp', 'builtin_interfaces/Time'),
        ('motion_permitted', 'bool'),
        ('final_publisher_instance_id', 'uint64'),
        ('policy_source_instance_id', 'uint64'),
        ('safe_stop_source_instance_id', 'uint64'),
        ('next_safe_stop_sequence', 'uint64'),
        ('pending_step_index', 'uint64'),
        ('pending_source_sequence', 'uint64'),
        ('pending_transition_id', 'string<=36'),
        ('action_barrier_stamp', 'builtin_interfaces/Time'),
        ('observation0_cutoff', 'builtin_interfaces/Time'),
        ('selected_zero_final_publisher_instance_id', 'uint64'),
        ('selected_zero_final_publish_sequence', 'uint64'),
        ('adjacent_boundary_final_publisher_instance_id', 'uint64'),
        ('adjacent_boundary_final_publish_sequence', 'uint64'),
        ('probe_start_request_sequence', 'uint64'),
    ]
    assert _fields(response_lines) == [
        ('schema_version', 'uint16'), ('result', 'uint8'),
        ('reason_code', 'uint16'), ('request_sequence', 'uint64'),
        ('backend_instance_id', 'uint64'), ('binding_revision', 'uint64'),
        ('applied_binding_revision', 'uint64'),
        ('applied_physics_iteration', 'uint64'),
        ('applied_sim_stamp', 'builtin_interfaces/Time'),
        ('contact_capability_state', 'uint8'),
        ('capability_revision', 'uint64'),
        ('proof_backend_instance_id', 'uint64'),
        ('proof_session_id', 'string<=64'),
        ('proof_config_hash', 'string<=64'),
        ('proof_asset_manifest_sha256', 'string<=64'),
        ('proof_collision_registry_sha256', 'string<=64'),
        ('proof_world_name', 'string<=128'),
        ('proof_physics_engine_plugin', 'string<=128'),
        ('proof_gz_sim_version', 'string<=32'),
        ('proof_physics_engine_fingerprint_sha256', 'string<=64'),
        ('probe_model_scoped_name', 'string<=128'),
        ('probe_model_entity_id', 'uint64'),
        ('probe_collision_scoped_name', 'string<=128'),
        ('probe_collision_entity_id', 'uint64'),
        ('floor_collision_scoped_name', 'string<=128'),
        ('floor_collision_entity_id', 'uint64'),
        ('contact_sample_count', 'uint16'),
        ('contact_first_iteration', 'uint64'),
        ('contact_last_iteration', 'uint64'),
        ('contact_first_stamp', 'builtin_interfaces/Time'),
        ('contact_last_stamp', 'builtin_interfaces/Time'),
        ('covered_empty_sample_count', 'uint16'),
        ('empty_first_iteration', 'uint64'),
        ('empty_last_iteration', 'uint64'),
        ('empty_first_stamp', 'builtin_interfaces/Time'),
        ('empty_last_stamp', 'builtin_interfaces/Time'),
    ]
    request_types = (
        LocalTrainingBackendControl.Request.get_fields_and_field_types()
    )
    response_types = (
        LocalTrainingBackendControl.Response.get_fields_and_field_types()
    )
    assert request_types['session_id'] == 'string<64>'
    assert request_types['pending_transition_id'] == 'string<36>'
    assert response_types['proof_world_name'] == 'string<128>'
    assert response_types['proof_gz_sim_version'] == 'string<32>'


def test_exact_operation_result_reason_and_capability_constants() -> None:
    """Pin exact operation, result, reason and capability enumerations."""
    request = LocalTrainingBackendControl.Request
    response = LocalTrainingBackendControl.Response
    assert request.SCHEMA_VERSION == 1
    assert response.RESPONSE_SCHEMA_VERSION == 1
    assert [getattr(request, field) for field in (
        'OP_BIND_SESSION', 'OP_BIND_PENDING_STEP', 'OP_CONFIRM_OBSERVATION0',
        'OP_INHIBIT', 'OP_VERIFY_CONTACT_CAPABILITY', 'OP_BIND_RESET_CONTEXT',
    )] == [1, 2, 3, 4, 5, 6]
    assert [getattr(request, field) for field in (
        'PROBE_ACTION_NONE', 'PROBE_ACTION_START', 'PROBE_ACTION_QUERY',
        'PROBE_ACTION_ABORT', 'PRIMARY_UNCONFIGURED', 'PRIMARY_INACTIVE',
        'PRIMARY_ACTIVE', 'BARRIER_INIT', 'BARRIER_READY',
        'BARRIER_NON_READY',
        'BARRIER_FAULT',
    )] == [0, 1, 2, 3, 0, 1, 2, 0, 1, 2, 3]
    assert [getattr(response, field) for field in (
        'RESULT_QUEUED', 'RESULT_APPLIED', 'RESULT_REJECTED', 'RESULT_FAULTED',
    )] == [2, 3, 4, 5]
    assert [getattr(response, field) for field in (
        'REASON_NONE', 'REASON_BAD_SCHEMA', 'REASON_BAD_OPERATION',
        'REASON_IDENTITY_MISMATCH', 'REASON_BACKEND_RESTARTED',
        'REASON_LIFECYCLE_MISMATCH', 'REASON_BARRIER_INVALID',
        'REASON_REVISION_MISMATCH', 'REASON_REQUEST_REPLAY',
        'REASON_REQUEST_GAP', 'REASON_DUPLICATE_CONTENT_CONFLICT',
        'REASON_QUEUE_OVERFLOW', 'REASON_BUSY',
        'REASON_PENDING_STEP_MISMATCH',
        'REASON_OBSERVATION0_PROOF_MISMATCH', 'REASON_CONTACT_PROBE_NOT_READY',
        'REASON_CONTACT_PROBE_FAILED', 'REASON_UNUSED_FIELD_NONZERO',
        'REASON_FAULT_LATCHED', 'REASON_CONTROL_EXPIRED',
        'REASON_CONTEXT_NOT_NEW',
        'REASON_FIXTURE_CONFLICT', 'REASON_CANCELLED',
    )] == list(range(23))
    assert [getattr(response, field) for field in (
        'CAPABILITY_UNKNOWN', 'CAPABILITY_RUNNING', 'CAPABILITY_VERIFIED',
        'CAPABILITY_FAILED', 'CAPABILITY_INVALIDATED',
    )] == [0, 1, 2, 3, 4]


def test_generated_service_serialization_without_ros_context() -> None:
    """Round-trip generated service request and response without ROS init."""
    request = LocalTrainingBackendControl.Request()
    request.schema_version = 1
    request.operation = request.OP_INHIBIT
    request.probe_action = request.PROBE_ACTION_NONE
    request.coordinator_ingress_instance_id = 2
    request.request_sequence = 1
    request.expected_backend_instance_id = 9
    request.session_id = 'session'
    request.config_hash = 'a' * 64
    request.asset_manifest_sha256 = 'b' * 64
    request.lifecycle_header_stamp = Time(sec=10, nanosec=2)
    response = LocalTrainingBackendControl.Response()
    response.schema_version = response.RESPONSE_SCHEMA_VERSION
    response.result = response.RESULT_APPLIED
    response.request_sequence = 1
    response.backend_instance_id = 9
    response.contact_capability_state = response.CAPABILITY_UNKNOWN
    restored_request = deserialize_message(
        serialize_message(request), LocalTrainingBackendControl.Request
    )
    restored_response = deserialize_message(
        serialize_message(response), LocalTrainingBackendControl.Response
    )
    assert (
        restored_request.lifecycle_header_stamp
        == request.lifecycle_header_stamp
    )
    assert restored_response.backend_instance_id == 9
