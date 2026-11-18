"""Runner campaign B2.3, quyền runtime từ packet/guard do Owner cấp trước.

Import module không tạo ROS context hoặc tiến trình. Worker chỉ được khởi tạo
sau khi controller đã consume đúng packet và pin context của transient unit.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import math
from collections import deque
from pathlib import Path
import threading
import time

MODULE = 'mecanum_nav_rl.runtime_simulation.b23_runner'
SERVICE_PROPERTIES = ('Type=exec','Restart=no','RemainAfterExit=yes','MemoryMax=5G',
    'OOMPolicy=stop','TimeoutStartSec=5s','TimeoutStopSec=2s',
    'KillMode=control-group','KillSignal=SIGTERM','SendSIGKILL=yes',
    'FinalKillSignal=SIGKILL','RuntimeRandomizedExtraSec=0')
CASE_PHASES = {'R01a': 'smoke', 'R01b': 'fault_task', 'R01c': 'fault_task',
    'R01d': 'fault_task', 'R01e': 'fault_task', 'R02a':'fault_task',
    'R02b':'fault_task', 'R02c':'fault_task', 'R02d':'fault_task',
    'R02e':'fault_task', 'R02f':'fault_task', 'R02g':'fault_task', 'R03a':'fault_task',
    'R03b':'fault_task', 'R04a':'fault_task', 'R04b':'fault_task',
    'R04c':'fault_task', 'R04d':'fault_task', 'R05':'fault_task',
    'R06a':'fault_task', 'R06b':'fault_task', 'R06c':'fault_task',
    'R07a':'fault_task', 'R07b':'fault_task', 'R07c':'fault_task',
    'R07d':'fault_task', 'R09a':'fault_task',
    'R09b':'fault_task', 'R08': 'soak'}
CASE_HOOKS = {
    'R01a': (),
    'R01b': ('external_pause_after_w1_before_native_dispatch',),
    'R01c': ('delay_native_pause_ack_1500ms_once',),
    'R01d': ('drop_native_pause_ack_once',),
    'R01e': ('pause_request_replay_after_terminal',),
    'R02a': (),
    'R02b': ('native_hold_admission_until_receipt',),
    'R02c': ('hold_policy_receipt_until_safe_stop',),
    'R02d': ('hold_policy_receipt_until_admission_inhibited',),
    'R02e': ('pre_bind_admission_sample',),
    'R02f': ('safety_hold_after_adapter_issuance',),
    'R02g': ('closing_paths_after_policy_nonzero',),
    'R03a': ('drop_native_policy_receipt_once',),
    'R03b': ('mutate_native_policy_transition_id_once',),
    'R04a': ('delay_noisy_odometry_delivery_300ms_once',),
    'R04b': ('drop_policy_noisy_odometry_delivery',),
    'R04c': ('delay_scan_delivery_650ms_once',),
    'R04d': ('delay_lifecycle_delivery_650ms_once',),
    'R05': ('mask_contact_coverage_after_verified',),
    'R06a': ('set_pose_ack_with_wrong_target',),
    'R06b': ('omit_one_settle_physics_iteration',),
    'R06c': ('hold_observation0_adjacent_receipt_until_reset_deadline',),
    'R07a': ('unexpected_pause_during_active_session',),
    'R07b': ('time_only_rollback_after_contact_proof',),
    'R07c': (),
    'R07d': (),
    'R09a': (),
    'R09b': (),
    'R08': (),
}

CASE_SCENARIOS = {
    'R09a': ('sim_train_local_training_goal_settle.resolved.json', 'B2_GOAL_SETTLE_V1.json'),
    'R09b': ('sim_train_local_training_contact.resolved.json', 'B2_CONTACT_V1.json'),
}

R09B_TASK_FIXTURE = {
    'entity_name': 'obstacle_0',
    'entity_type': 'MODEL',
    'frame': 'world',
    'initial_pose': {'x_m': 2.5, 'y_m': 0.0, 'z_m': 0.5, 'yaw_rad': 0.0},
    # The base half-length is 0.20 m; the 0.20 m fixture starts at x=0.17,
    # giving 0.03 m overlap while keeping it beyond the lidar 0.10 m minimum.
    'contact_pose': {'x_m': 0.27, 'y_m': 0.0, 'z_m': 0.5, 'yaw_rad': 0.0},
}


def validate_r09b_task_fixture(value):
    """Pin R09b SetEntityPose to the existing world fixture and two poses."""
    if value != R09B_TASK_FIXTURE:
        raise ValueError('R09b task fixture binding/pose differs from the approved packet')
    return R09B_TASK_FIXTURE


def bind_install_ament_prefix(environment, install_prefix):
    """Ensure runtime ament lookups see the exact packet-bound install first."""
    import os
    prefix = str(Path(install_prefix).resolve(strict=True))
    existing = environment.get('AMENT_PREFIX_PATH', '')
    if not isinstance(existing, str):
        raise TypeError('AMENT_PREFIX_PATH must be a path string')
    paths = [prefix]
    paths.extend(item for item in existing.split(os.pathsep)
        if item and str(Path(item).resolve()) != prefix)
    bound = dict(environment)
    bound['AMENT_PREFIX_PATH'] = os.pathsep.join(paths)
    return bound


def verify_r09a_goal_settle(transition):
    """Require a committed, healthy B1 GOAL terminal under zero command."""
    from mecanum_nav_rl.termination.manager import TerminationReason
    if (not transition.termination.terminated
            or transition.termination.reason is not TerminationReason.GOAL
            or transition.goal_settle_result is None
            or not transition.goal_settle_result.healthy
            or not transition.goal_settle_result.success
            or transition.command_history != (0., 0., 0.)):
        raise RuntimeError('R09a terminal was not a healthy zero-command B1 goal settle')
    return {'goal_settled':True, 'goal_distance_m':transition.goal_settle_result.distance_m,
        'zero_command':True, 'transition_id':transition.transition_identity.transition_id}


def verify_r09b_task_contact(transition, contact_state):
    """Require the exact contact pulse consumed by this B1 terminal commit."""
    from mecanum_nav_rl.termination.manager import TerminationReason
    transition_id = transition.transition_identity.transition_id
    consumed = getattr(contact_state, 'consumed_transition_ids', ())
    if (not transition.termination.terminated
            or transition.termination.reason is not TerminationReason.COLLISION
            or not contact_state.source_healthy
            or transition_id not in consumed):
        raise RuntimeError('R09b lacks a healthy B1-committed task contact terminal')
    return {'task_contact_committed':True,
        'contact_active_at_commit':bool(contact_state.contact_active),
        'contact_pulse_consumed_by_b1':True,
        'transition_id':transition_id}


async def restore_r09b_fixture_after_contact_pulse(io, *, deadline_ns,
                                                  after_status_sequence,
                                                  after_physics_iteration,
                                                  zero_receipt,
                                                  zero_applied_state,
                                                  zero_applied_received_ns):
    """Capture a healthy fixture contact pulse, then clear contact before B1 cutoff."""
    def matching_status(*, active, after_sequence=0, after_iteration=0):
        status = io.ingress.backend_state
        if status is None:
            return None
        if (status.backend_instance_id != io.descriptor['backend_instance_id']
                or status.session_id != io.descriptor['session_id']
                or status.config_hash != io.descriptor['config_hash']
                or not status.coverage_complete or not status.contact_source_healthy
                or status.required_collision_mask == 0
                or status.required_collision_mask != status.observed_collision_mask
                or status.fault_flags or status.paused
                or status.status_sequence <= after_sequence
                or status.physics_iteration <= after_iteration
                or bool(status.contact_active) is not active):
            return None
        return status

    contact = await io.until(lambda: matching_status(active=True,
        after_sequence=after_status_sequence,
        after_iteration=after_physics_iteration),
        deadline_ns=deadline_ns, phase='R09b healthy fixture contact pulse')
    contact_facts = {'entity_name':io.descriptor['task_fixture']['entity_name'],
        'backend_instance_id':int(contact.backend_instance_id),
        'session_id':contact.session_id, 'config_hash':contact.config_hash,
        'status_sequence':int(contact.status_sequence),
        'physics_iteration':int(contact.physics_iteration),
        'sim_stamp_ns':int(contact.header.stamp.sec)*1_000_000_000
            +int(contact.header.stamp.nanosec), 'steady_ns':io.now()}
    io.emit('R09B_FIXTURE_CONTACT_PULSE_OBSERVED', contact_facts)
    await io.set_r09b_task_fixture_pose(pose_name='initial_pose',
        deadline_ns=deadline_ns, zero_receipt=None)
    empty = await io.until(lambda: matching_status(active=False,
        after_sequence=contact.status_sequence,
        after_iteration=contact.physics_iteration), deadline_ns=deadline_ns,
        phase='R09b fixture restored covered-empty before B1 cutoff')
    empty_facts = {'entity_name':io.descriptor['task_fixture']['entity_name'],
        'backend_instance_id':int(empty.backend_instance_id),
        'session_id':empty.session_id, 'config_hash':empty.config_hash,
        'coverage_complete':bool(empty.coverage_complete),
        'contact_active':bool(empty.contact_active),
        'status_sequence':int(empty.status_sequence),
        'physics_iteration':int(empty.physics_iteration),
        'sim_stamp_ns':int(empty.header.stamp.sec)*1_000_000_000
            +int(empty.header.stamp.nanosec), 'steady_ns':io.now()}
    io.emit('R09B_FIXTURE_RESTORED_COVERED_EMPTY', empty_facts)
    return {'contact':contact_facts, 'restored_empty':empty_facts}


def require_r09_scenario(artifact_result, expected_scenario_id):
    """Validate the scenario identity carried by the production loader result."""
    from mecanum_nav_rl.tasks.scenario_artifact import ScenarioArtifactLoadResult
    if not isinstance(artifact_result, ScenarioArtifactLoadResult):
        raise TypeError('R09 requires a ScenarioArtifactLoadResult')
    if not artifact_result.ready or artifact_result.artifact is None:
        raise RuntimeError('R09 scenario artifact is not ready')
    identity = artifact_result.artifact.identity
    if identity.scenario_id != expected_scenario_id:
        raise RuntimeError('R09 packet scenario identity mismatch')
    return identity


def service_properties_for(active_s):
    """Unit cap exactly covers active and cleanup budgets for the packet."""
    if type(active_s) is not int or active_s not in (120, 900):
        raise ValueError('unsupported B2.3 active runtime budget')
    return (*SERVICE_PROPERTIES, f'RuntimeMaxSec={active_s + 60}s')


def verify_r07b_revocation(*, response, original_proof, sim_before_ns,
                           sim_after_ns, sim_time_jump_delta_ns, replay_ack,
                           fresh_ack, inhibit_ack):
    """Require rollback, revoked QUERY replay/fresh response, and INHIBIT ACK."""
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    if type(sim_time_jump_delta_ns) is not int or sim_time_jump_delta_ns >= 0:
        raise RuntimeError('R07b did not observe simulation time rollback')
    if original_proof.response.contact_capability_state != Control.Response.CAPABILITY_VERIFIED:
        raise RuntimeError('R07b original contact proof was not verified')
    for label, ack in (('replayed', replay_ack), ('fresh', fresh_ack)):
        if (ack.request.operation != Control.Request.OP_VERIFY_CONTACT_CAPABILITY
                or ack.response.result != Control.Response.RESULT_REJECTED
                or ack.response.reason_code != Control.Response.REASON_CONTACT_PROBE_FAILED
                or ack.response.contact_capability_state == Control.Response.CAPABILITY_VERIFIED
                or ack.response.proof_backend_instance_id != 0
                or ack.response.proof_session_id or ack.response.proof_config_hash
                or ack.response.proof_asset_manifest_sha256):
            raise RuntimeError('R07b ' + label + ' QUERY exposed proof after clock rollback')
    if (replay_ack.request_bytes != original_proof.request_bytes
            or replay_ack.response_bytes == original_proof.response_bytes):
        raise RuntimeError('R07b exact QUERY replay did not return a revoked response')
    if (response.contact_capability_state == Control.Response.CAPABILITY_VERIFIED
            or response.proof_backend_instance_id != 0 or response.proof_session_id):
        raise RuntimeError('R07b contact proof remains valid after rollback')
    if (inhibit_ack.request.operation != Control.Request.OP_INHIBIT
            or inhibit_ack.response.result != Control.Response.RESULT_APPLIED
            or inhibit_ack.response.reason_code != Control.Response.REASON_NONE):
        raise RuntimeError('R07b lacks the native applied INHIBIT after rollback')
    return {'clock_rollback_observed':True, 'contact_proof_invalidated':True,
        'native_inhibit_applied':True, 'simulation_time_before_ns':sim_before_ns,
        'simulation_time_after_ns':sim_after_ns,
        'simulation_time_jump_delta_ns':sim_time_jump_delta_ns,
        'contact_state':response.contact_capability_state,
        'query_replay_revoked':True,'fresh_query_revoked':True,
        'inhibit_request_sequence':inhibit_ack.request.request_sequence,
        'inhibit_revision':inhibit_ack.response.applied_binding_revision}


def verify_r07b_backend_restart(*, original_proof, sim_time_jump_delta_ns,
                                replay_error, replay_identity_ack, replacement_ack, inhibit_ack,
                                fresh_ack, replacement_status,
                                old_backend_instance_id):
    """Chấm riêng nhánh Gazebo thay backend trong time-only reset.

    Không xem timeout của replay cũ là ACK revocation. Nhánh này chỉ đạt khi
    identity backend mới được chứng minh, session cũ bị từ chối, backend mới
    được INHIBIT và QUERY mới không có proof.
    """
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    from mecanum_nav_rl_interfaces.msg import SimulationContactState
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendControlError
    if type(sim_time_jump_delta_ns) is not int or sim_time_jump_delta_ns >= 0:
        raise RuntimeError('R07b did not observe simulation time rollback')
    if original_proof.response.contact_capability_state != Control.Response.CAPABILITY_VERIFIED:
        raise RuntimeError('R07b original contact proof was not verified')
    if isinstance(replay_error, TimeoutError):
        if replay_identity_ack is not None:
            raise RuntimeError('R07b replay timeout unexpectedly includes an identity ACK')
    elif isinstance(replay_error, BackendControlError):
        replayed = replay_identity_ack
        if (replayed is None
                or replayed.request_bytes != original_proof.request_bytes
                or replayed.request.operation != Control.Request.OP_VERIFY_CONTACT_CAPABILITY
                or replayed.request.probe_action != Control.Request.PROBE_ACTION_QUERY
                or replayed.response.backend_instance_id == old_backend_instance_id
                or replayed.response.request_sequence != original_proof.request.request_sequence
                or replayed.response.result != Control.Response.RESULT_REJECTED
                or replayed.response.reason_code != Control.Response.REASON_IDENTITY_MISMATCH
                or replayed.response.contact_capability_state == Control.Response.CAPABILITY_VERIFIED
                or replayed.response.proof_backend_instance_id != 0
                or replayed.response.proof_session_id
                or replayed.response.proof_config_hash
                or replayed.response.proof_asset_manifest_sha256):
            raise RuntimeError('R07b exact QUERY replay did not retain a rejected replacement-identity ACK')
    else:
        raise RuntimeError('R07b old QUERY replay failure type is not an expected bounded outcome')
    stale = replacement_ack
    new_id = stale.response.backend_instance_id
    if (stale.request.operation != Control.Request.OP_INHIBIT
            or stale.request.expected_backend_instance_id != old_backend_instance_id
            or stale.request.session_id != original_proof.request.session_id
            or stale.response.result != Control.Response.RESULT_REJECTED
            or stale.response.reason_code != Control.Response.REASON_IDENTITY_MISMATCH
            or new_id == old_backend_instance_id
            or stale.response.request_sequence != stale.request.request_sequence):
        raise RuntimeError('R07b replacement backend identity was not bounded to old-session rejection')
    for label, ack in (('new INHIBIT', inhibit_ack), ('new QUERY', fresh_ack)):
        if (ack.response.backend_instance_id != new_id
                or ack.request.expected_backend_instance_id != new_id
                or ack.request.session_id != original_proof.request.session_id
                or ack.response.request_sequence != ack.request.request_sequence):
            raise RuntimeError('R07b ' + label + ' identity binding mismatch')
    if (inhibit_ack.request.operation != Control.Request.OP_INHIBIT
            or inhibit_ack.response.result != Control.Response.RESULT_APPLIED
            or inhibit_ack.response.reason_code != Control.Response.REASON_NONE
            or inhibit_ack.response.contact_capability_state == Control.Response.CAPABILITY_VERIFIED
            or inhibit_ack.response.proof_backend_instance_id != 0
            or inhibit_ack.response.proof_session_id):
        raise RuntimeError('R07b replacement backend lacks an applied proof-free INHIBIT')
    if (fresh_ack.request.operation != Control.Request.OP_VERIFY_CONTACT_CAPABILITY
            or fresh_ack.request.probe_action != Control.Request.PROBE_ACTION_QUERY
            or fresh_ack.response.result != Control.Response.RESULT_REJECTED
            or fresh_ack.response.reason_code != Control.Response.REASON_CONTACT_PROBE_NOT_READY
            or fresh_ack.response.contact_capability_state == Control.Response.CAPABILITY_VERIFIED
            or fresh_ack.response.proof_backend_instance_id != 0
            or fresh_ack.response.proof_session_id
            or fresh_ack.response.proof_config_hash
            or fresh_ack.response.proof_asset_manifest_sha256):
        raise RuntimeError('R07b replacement QUERY returned stale or unverifiable proof')
    status = replacement_status
    expected_restart_faults = (SimulationContactState.FAULT_CONTACT_COVERAGE
                               | SimulationContactState.FAULT_QUEUE)
    if (status['backend_instance_id'] != new_id
            or status['session_id'] != original_proof.request.session_id
            or status['config_hash'] != stale.request.config_hash
            or type(status['status_sequence']) is not int or status['status_sequence'] <= 0
            or type(status['physics_iteration']) is not int or status['physics_iteration'] <= 0
            or status['received_ns'] <= inhibit_ack.observed_steady_ns
            or status['fault_flags'] != expected_restart_faults
            or not status['local_zero_override'] or not status['actuator_inhibited']):
        raise RuntimeError('R07b replacement backend status did not prove expected fail-closed zero after ACK')
    return {'clock_rollback_observed':True, 'backend_restarted':True,
        'old_backend_instance_id':old_backend_instance_id,
        'new_backend_instance_id':new_id,
        'old_query_replay_unavailable_due_backend_replacement':True,
        'old_query_replay_identity_ack_observed':replay_identity_ack is not None,
        'old_session_rejected':True, 'replacement_backend_inhibit_applied':True,
        'replacement_backend_zero_status_confirmed':True,
        'replacement_backend_fault_flags':status['fault_flags'],
        'replacement_backend_fault_flags_expected':expected_restart_faults,
        'fresh_query_has_no_contact_proof':True,
        'simulation_time_jump_delta_ns':sim_time_jump_delta_ns,
        'inhibit_request_sequence':inhibit_ack.request.request_sequence,
        'inhibit_revision':inhibit_ack.response.applied_binding_revision,
        'replacement_status_sequence':status['status_sequence'],
        'replacement_status_iteration':status['physics_iteration']}


def verify_r07c_backend_restart(*, original_proof, old_backend_instance_id,
                                old_process, replacement, old_identity_rejection,
                                query_ack, inhibit_ack, replacement_status):
    """Require owned server replacement, old binding rejection and inhibited new backend."""
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    new_id = int(replacement_status['backend_instance_id'])
    if (original_proof is None
            or original_proof.response.contact_capability_state != Control.Response.CAPABILITY_VERIFIED
            or old_process.get('group_absent') is not True
            or replacement.get('pid') == old_process.get('pid')
            or new_id == old_backend_instance_id
            or replacement.get('backend_instance_id') not in (None, new_id)):
        raise RuntimeError('R07c backend process/instance replacement was not proven')
    if (old_identity_rejection.request.operation != Control.Request.OP_INHIBIT
            or old_identity_rejection.response.result != Control.Response.RESULT_REJECTED
            or old_identity_rejection.response.reason_code != Control.Response.REASON_IDENTITY_MISMATCH
            or old_identity_rejection.response.backend_instance_id != new_id):
        raise RuntimeError('R07c old backend control identity was not rejected')
    if (query_ack.request.operation != Control.Request.OP_VERIFY_CONTACT_CAPABILITY
            or query_ack.response.contact_capability_state == Control.Response.CAPABILITY_VERIFIED
            or query_ack.response.result != Control.Response.RESULT_REJECTED
            or query_ack.response.reason_code != Control.Response.REASON_CONTACT_PROBE_NOT_READY
            or query_ack.response.proof_backend_instance_id != 0
            or query_ack.response.proof_session_id
            or query_ack.response.proof_config_hash
            or query_ack.response.proof_asset_manifest_sha256):
        raise RuntimeError('R07c replacement backend exposed old contact proof')
    if (inhibit_ack.request.operation != Control.Request.OP_INHIBIT
            or inhibit_ack.response.result != Control.Response.RESULT_APPLIED
            or inhibit_ack.response.reason_code != Control.Response.REASON_NONE
            or not replacement_status['local_zero_override']
            or not replacement_status['actuator_inhibited']):
        raise RuntimeError('R07c replacement backend did not remain natively inhibited')
    return {'backend_restarted':True,'contact_proof_not_inherited':True,
        'old_control_rejected':True,'replacement_inhibit_applied':True,
        'old_server_group_absent':True,'old_backend_instance_id':old_backend_instance_id,
        'replacement_backend_instance_id':new_id}


def verify_r07d_final_publisher_restart(*, old_publisher_instance_id,
                                         old_process, replacement, backend_status,
                                         inhibit_ack, new_receipts):
    """Require a distinct unbound final process while native output stays zero/inhibited."""
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    publisher_id = int(replacement['publisher_instance_id'])
    fault_flags = backend_status.get('fault_flags')
    expected_fault_flags = (0, *r07d_restart_fault_flags())
    if (old_process.get('group_absent') is not True
            or replacement.get('pid') == old_process.get('pid')
            or publisher_id == old_publisher_instance_id
            or replacement.get('binding_ack_exists') is not False
            or new_receipts):
        raise RuntimeError('R07d final publisher process replacement/binding boundary invalid')
    if (inhibit_ack.request.operation != Control.Request.OP_INHIBIT
            or inhibit_ack.response.result != Control.Response.RESULT_APPLIED
            or type(fault_flags) is not int
            or fault_flags not in expected_fault_flags
            or not backend_status.get('local_zero_override')
            or not backend_status.get('actuator_inhibited')):
        raise RuntimeError('R07d backend zero/inhibit was not confirmed after publisher restart')
    return {'final_publisher_restarted':True,'old_final_group_absent':True,
        'replacement_unbound':True,'replacement_emitted_no_receipt':True,
        'native_fault_flags':fault_flags,
        'native_zero_inhibited':True,'old_publisher_instance_id':old_publisher_instance_id,
        'replacement_publisher_instance_id':publisher_id}


def r07d_restart_fault_flags():
    """Only watchdog stale and its receipt-gate sequence invalidation are expected."""
    from mecanum_nav_rl_interfaces.msg import SimulationContactState
    return (SimulationContactState.FAULT_COMMAND_STALE,
        SimulationContactState.FAULT_COMMAND_SEQUENCE | SimulationContactState.FAULT_COMMAND_STALE)


def r07d_post_restart_zero_status(ingress, inhibit_ack):
    """Return only a zero/inhibited backend sample received after the INHIBIT ACK."""
    state = ingress.backend_state
    received_ns = ingress.backend_received_ns
    if (state is None or type(received_ns) is not int
            or received_ns <= inhibit_ack.observed_steady_ns
            or not state.local_zero_override or not state.actuator_inhibited):
        return None
    return state


def r07d_backend_status_record(state, received_steady_ns):
    """Record native status with the ingress receive time, not a message field."""
    if type(received_steady_ns) is not int or received_steady_ns < 0:
        raise ValueError('R07d backend status lacks a valid ingress receive timestamp')
    return {'backend_instance_id':int(state.backend_instance_id),
        'local_zero_override':bool(state.local_zero_override),
        'actuator_inhibited':bool(state.actuator_inhibited),
        'fault_flags':int(state.fault_flags),
        'status_sequence':int(state.status_sequence),
        'received_ns':received_steady_ns}


def pin_initial_final_publisher_identity(descriptor_base, boot, final_pid):
    """Giữ publisher instance đầu tiên trong descriptor cha dùng cho R07d."""
    publisher_id = boot.get('publisher_instance_id')
    identity = boot.get('identity')
    if (type(publisher_id) is not int or publisher_id <= 0
            or type(final_pid) is not int or final_pid <= 0
            or not isinstance(identity, dict) or identity.get('pid') != final_pid
            or boot.get('run_id') != descriptor_base.get('run_id')
            or boot.get('invocation_id') != descriptor_base.get('invocation_id')):
        raise RuntimeError('initial final publisher binding cannot be pinned to this invocation')
    previous = descriptor_base.get('final_publisher_instance_id')
    if previous is not None and previous != publisher_id:
        raise RuntimeError('initial final publisher binding conflicts with pinned identity')
    descriptor_base.update(final_publisher_instance_id=publisher_id,
        final_publisher_pid=final_pid)
    return publisher_id


async def query_replacement_backend_then_inhibit(control, *, query_deadline_ns,
                                                  inhibit_deadline_ns,
                                                  probe_start_request_sequence):
    """Đọc proof trên backend mới trước INHIBIT kết thúc session client.

    BackendControlSession.inhibit() cố ý khóa mọi mutation/query tiếp theo.
    Vì vậy QUERY mới phải được gửi trước; sau đó chỉ ACK INHIBIT mới chứng
    minh backend đã đóng quyền chuyển động.
    """
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendControlError
    try:
        fresh_ack = await control.transact(Control.Request.OP_VERIFY_CONTACT_CAPABILITY,
            deadline_ns=query_deadline_ns,
            probe_action=Control.Request.PROBE_ACTION_QUERY,
            probe_start_request_sequence=probe_start_request_sequence)
    except BackendControlError as error:
        if error.ack is None:
            raise
        fresh_ack = error.ack
    inhibit_ack = await control.inhibit(deadline_ns=inhibit_deadline_ns)
    return fresh_ack, inhibit_ack


async def prepare_r07d_final_publisher_restart(io, b1, packet):
    """Tạo context episode thật để có thể drain admission trước restart R07d.

    R07d bắt đầu từ session bind/contact proof, khi noise emulator chưa reset.
    SafetyInput chỉ được tạo từ noisy sample có lifecycle đang hoạt động; vì
    vậy inhibit-and-drain ngay sau bind không thể sinh native watermark.
    Dùng reset bình thường đã được packet pin trước khi yêu cầu drain.
    """
    from mecanum_nav_rl.simulation.local_training_reset import ResetTarget

    if not packet.get('episode_seeds') or not isinstance(packet.get('reset_target'), dict):
        raise ValueError('R07d packet lacks the pinned reset seed/target')
    await io.reset_episode(b1, seed=packet['episode_seeds'][0],
        target=ResetTarget(**packet['reset_target']), paused_hold_s=.250)
    if (not io.ingress._noise_ready or io.ingress.lifecycle is None
            or io.ingress.lifecycle.episode_generation <= 0):
        raise RuntimeError('R07d reset did not establish an active noisy lifecycle')
    io.emit('B23_R07D_ACTIVE_CONTEXT_READY', {
        'episode_generation':int(io.ingress.lifecycle.episode_generation),
        'reset_epoch':int(io.ingress.lifecycle.reset_epoch),
        'runtime_generation':int(io.ingress.lifecycle.runtime_generation),
        'steady_ns':io.now()})
    drained = await io.inhibit_and_drain(deadline_ns=io.deadline_ns)
    # R07d does not reopen POLICY. Freeze further coordinator safety inputs
    # after native inhibit is drained so a delayed/stale oracle callback cannot
    # create a new admission while the final publisher is being replaced.
    await io.freeze_admission(deadline_ns=io.deadline_ns)
    return drained


def r07b_stale_rollback_input_reason(topic, message, wire, ingress):
    """Nhận diện đúng sample cũ cần quarantine trước khi ingress latch lỗi."""
    stamp = int(message.header.stamp.sec) * 1_000_000_000 + int(message.header.stamp.nanosec)
    with ingress.lock:
        if topic == '/mecanum/final_issued_command':
            watermark = ingress._last_receipt_stamp_ns
            if stamp < watermark:
                return 'receipt_source_stamp_below_pinned_high_watermark', stamp, watermark
        elif topic == '/mecanum/internal/ground_truth/odom':
            watermark = ingress._last_gt_stamp
            if stamp < watermark:
                return 'oracle_source_stamp_below_pinned_high_watermark', stamp, watermark
            if stamp == watermark and wire != ingress._last_gt_bytes:
                return 'oracle_same_stamp_bytes_conflict_with_pinned_sample', stamp, watermark
        elif topic == '/scan':
            existing = ingress.scans.get(stamp)
            if existing is not None and wire != existing.message_bytes:
                return 'scan_same_stamp_bytes_conflict_with_pinned_sample', stamp, stamp
    return None


def r07b_post_rollback_backend_disposition(io, *, old_backend_instance_id,
                                           rollback_observed_ns):
    """Return only native status received after rollback, bound to this session.

    The Gazebo clock callback can observe time_only rollback before the
    backend's next physics update. Sending QUERY in that interval can race the
    backend's proof invalidation and return the pre-rollback cached proof.
    Wait for either the pinned backend's applied CLOCK fault/zero or a status
    from a replacement instance before issuing any post-rollback QUERY.
    """
    descriptor = io.descriptor
    ingress = io.ingress
    state = ingress.backend_state
    received_ns = ingress.backend_received_ns
    if (state is not None and received_ns > rollback_observed_ns
            and state.backend_instance_id == old_backend_instance_id
            and state.session_id == descriptor['session_id']
            and state.config_hash == descriptor['config_hash']
            and state.fault_flags & 64 and state.local_zero_override
            and state.actuator_inhibited):
        return {
            'kind':'pinned_backend_clock_fault',
            'backend_instance_id':int(state.backend_instance_id),
            'status_sequence':int(state.status_sequence),
            'physics_iteration':int(state.physics_iteration),
            'fault_flags':int(state.fault_flags),
            'local_zero_override':bool(state.local_zero_override),
            'actuator_inhibited':bool(state.actuator_inhibited),
            'received_ns':int(received_ns),
        }
    for status in reversed(io._r07b_replacement_backend_statuses):
        if (status['received_ns'] > rollback_observed_ns
                and status['backend_instance_id'] != old_backend_instance_id
                and status['session_id'] == descriptor['session_id']
                and status['config_hash'] == descriptor['config_hash']
                and status['status_sequence'] > 0
                and status['physics_iteration'] > 0
                and status['local_zero_override']
                and status['actuator_inhibited']):
            return {'kind':'replacement_backend', **status}
    return None


def verify_r07a_unexpected_pause(*, world_ack, world_pause_state, backend_state,
                                 pre_pause_policy_step_identities,
                                 post_pause_policy_step_identities, reset_count_before,
                                 reset_count_after):
    """Require external pause to fault/zero without admitting a new POLICY step."""
    if world_ack is not True or world_pause_state is not True:
        raise RuntimeError('R07a world pause ACK/state was not confirmed')
    if (backend_state is None or backend_state.fault_flags != 1
            or not backend_state.local_zero_override or backend_state.actuator_inhibited is False):
        raise RuntimeError('R07a lacks native unexpected-pause fault and zero override')
    if not pre_pause_policy_step_identities:
        raise RuntimeError('R07a did not observe its committed POLICY step before unexpected pause')
    if post_pause_policy_step_identities != pre_pause_policy_step_identities:
        raise RuntimeError('R07a observed a new POLICY step identity after unexpected pause')
    if reset_count_after != reset_count_before:
        raise RuntimeError('R07a reset/observation0 advanced after unexpected pause')
    return {'world_pause_acknowledged':True,'world_pause_state':world_pause_state,
        'native_fault_flags':backend_state.fault_flags,
        'native_zero_override':True,'policy_step_identities_unchanged':True,
        'reset_count_unchanged':True}


def verify_r07a_resumed_inhibition(*, backend_state,
        pre_pause_policy_step_identities, post_resume_policy_step_identities,
        reset_count_before, reset_count_after):
    """Verify the invalidated gate stays faulted and motion remains inhibited after resume."""
    from mecanum_nav_rl_interfaces.msg import SimulationContactState
    expected_faults = (SimulationContactState.FAULT_CONTEXT |
        SimulationContactState.FAULT_COMMAND_SEQUENCE |
        SimulationContactState.FAULT_COMMAND_STALE)
    if (backend_state is None or backend_state.paused
            or backend_state.fault_flags != expected_faults
            or not backend_state.local_zero_override
            or not backend_state.actuator_inhibited):
        raise RuntimeError('R07a resumed backend did not retain the exact invalidated-gate zero/inhibit state')
    if post_resume_policy_step_identities != pre_pause_policy_step_identities:
        raise RuntimeError('R07a observed a new POLICY step identity after resume')
    if reset_count_after != reset_count_before:
        raise RuntimeError('R07a reset/observation0 advanced after resume')
    return {'resumed_fault_flags':backend_state.fault_flags,
        'gate_invalidation_and_zero_inhibit_verified':True,
        'policy_step_identities_unchanged':True,
        'reset_count_unchanged':True,
        'status_sequence':backend_state.status_sequence,
        'physics_iteration':backend_state.physics_iteration}


def policy_receipt_count(receipts):
    """Count copied receipt-v2 views using the pure-core source enum."""
    from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
    return sum(1 for receipt in receipts if receipt.source == ReceiptSource.POLICY)


def policy_step_identities(receipts):
    """Return distinct source-step identities, ignoring timer republishes."""
    from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
    return frozenset((receipt.session_id, receipt.ingress_config_hash,
        (receipt.lifecycle.episode_generation, receipt.lifecycle.reset_epoch,
         receipt.lifecycle.runtime_generation), receipt.source_instance_id,
        receipt.source_sequence, receipt.step_index, receipt.transition_id)
        for receipt in receipts if receipt.source == ReceiptSource.POLICY)


def should_emit_policy_cutoff_pending(seen_cutoff_reasons, cutoff_ns, reason):
    """Emit a pending fact once per cutoff/reason, independent of other cutoffs."""
    key = (cutoff_ns, reason)
    if key in seen_cutoff_reasons:
        return False
    seen_cutoff_reasons.add(key)
    return True


SOAK_ACTIONS = (
    (0.40, 0.0, 0.0), (-0.40, 0.0, 0.0), (0.0, 0.40, 0.0),
    (0.0, 0.0, 0.40), (0.30, 0.30, 0.0), (0.30, -0.25, 0.30),
)


def soak_action(episode_index, step_index):
    """D04 slot schedule: five zero steps, then 20 case steps, then zero."""
    if type(episode_index) is not int or not 0 <= episode_index < 30:
        raise ValueError('soak episode index outside B2_SOAK_V1')
    if type(step_index) is not int or not 1 <= step_index <= (34 if episode_index < 10 else 33):
        raise ValueError('soak step index outside B2_SOAK_V1 slot')
    if 6 <= step_index <= 25:
        return SOAK_ACTIONS[episode_index % len(SOAK_ACTIONS)]
    return (0.0, 0.0, 0.0)


def r02b_admission_release_target_ns(now_ros_ns, scan_period_ns):
    """Return the next scan cutoff R02b must observe before binding a step.

    R02b measures the native 40 ms admission hold. The runner waits for an
    actual Safety tick after this boundary while no new POLICY slot is bound,
    so cutoff deferral cannot be folded into the admission-order measurement.
    """
    if (type(now_ros_ns) is not int or now_ros_ns < 0
            or type(scan_period_ns) is not int or scan_period_ns <= 0):
        raise ValueError('R02b scan release phase requires nonnegative ROS time and positive period')
    next_boundary = (now_ros_ns // scan_period_ns + 1) * scan_period_ns
    return next_boundary


def case_environment(case, hooks):
    """Bind the single native ACK fault hook to its case-scoped child env."""
    if case == 'R02b' and hooks == ['native_hold_admission_until_receipt']:
        return {'B23_ADMISSION_ORDER_FAULT': 'receipt_before_admission'}
    if case == 'R01c' and hooks == ['delay_native_pause_ack_1500ms_once']:
        return {'B23_PAUSE_ACK_FAULT': 'delay_1500ms_once'}
    if case == 'R01d' and hooks == ['drop_native_pause_ack_once']:
        return {'B23_PAUSE_ACK_FAULT': 'drop_once'}
    if case == 'R03a' and hooks == ['drop_native_policy_receipt_once']:
        return {'B23_RECEIPT_FAULT': 'drop_policy_once'}
    if case == 'R03b' and hooks == ['mutate_native_policy_transition_id_once']:
        return {'B23_RECEIPT_FAULT': 'mutate_policy_transition_id_once'}
    if case == 'R02c' and hooks == ['hold_policy_receipt_until_safe_stop']:
        return {'B23_RECEIPT_FAULT': 'hold_policy_until_safe_stop'}
    if case == 'R02d' and hooks == ['hold_policy_receipt_until_admission_inhibited']:
        return {'B23_RECEIPT_FAULT': 'hold_policy_until_inhibit'}
    if case == 'R02e':
        return {}
    if case == 'R05' and hooks == ['mask_contact_coverage_after_verified']:
        return {'B23_CONTACT_COVERAGE_FAULT':'mask_coverage_after_verified'}
    return {}


def verify_r05_contact_query_revocation(root, *, original_ack, replay_ack,
                                        fresh_ack, backend_state):
    """Bind proof revocation to a pinned coverage mask and both QUERY paths."""
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    if original_ack is None or original_ack.response.contact_capability_state != \
            Control.Response.CAPABILITY_VERIFIED:
        raise RuntimeError('R05 lacks the original verified QUERY response')
    for label, ack in (('replay', replay_ack), ('fresh', fresh_ack)):
        if ack is None or ack.response.contact_capability_state == \
                Control.Response.CAPABILITY_VERIFIED:
            raise RuntimeError('R05 ' + label + ' QUERY returned a stale verified proof')
        proof = ack.response
        if (proof.proof_backend_instance_id != 0 or proof.proof_session_id
                or proof.proof_config_hash or proof.proof_asset_manifest_sha256
                or proof.proof_world_name or proof.proof_collision_registry_sha256
                or proof.proof_physics_engine_fingerprint_sha256
                or proof.probe_model_entity_id or proof.probe_collision_entity_id
                or proof.floor_collision_entity_id or proof.contact_sample_count
                or proof.covered_empty_sample_count):
            raise RuntimeError('R05 ' + label + ' QUERY still contains old proof fields')
    rows = [json.loads(line) for line in
        (Path(root)/'native-events.jsonl').read_text().splitlines() if line.strip()]
    masked = [row for row in rows if row.get('kind') == 'B23_CONTACT_COVERAGE_MASKED'
        and row.get('fields',{}).get('masked') == '1']
    if not masked:
        raise RuntimeError('R05 lacks native pinned contact coverage mask evidence')
    event = masked[0].get('fields',{})
    if not event.get('entity') or int(event.get('iteration','0')) <= 0:
        raise RuntimeError('R05 coverage mask evidence lacks pinned entity/iteration')
    if (backend_state is None or not backend_state.local_zero_override
            or int(backend_state.fault_flags) & 16 == 0):
        raise RuntimeError('R05 contact loss did not close motion with contact coverage fault')
    return {'masked_entity':event['entity'], 'masked_iteration':int(event['iteration']),
        'original_query_verified':True, 'replay_query_revoked':True,
        'fresh_query_revoked':True, 'policy_closed':True,
        'native_fault_flags':int(backend_state.fault_flags)}


def expected_r05_revoked_query_ack(error, *, start_request_sequence):
    """Return only the exact native rejection that proves a fresh QUERY is revoked."""
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendControlError
    if not isinstance(error, BackendControlError) or error.ack is None:
        raise RuntimeError('R05 fresh QUERY rejection lacks its native ACK') from error
    ack = error.ack
    request, response = ack.request, ack.response
    if (request.operation != Control.Request.OP_VERIFY_CONTACT_CAPABILITY
            or request.probe_action != Control.Request.PROBE_ACTION_QUERY
            or request.probe_start_request_sequence != start_request_sequence
            or response.result != Control.Response.RESULT_REJECTED
            or response.reason_code != Control.Response.REASON_CONTACT_PROBE_FAILED
            or response.contact_capability_state == Control.Response.CAPABILITY_VERIFIED):
        raise RuntimeError('R05 fresh QUERY rejection does not match revoked probe identity/state') from error
    return ack


def enable_r04_adapter_fault_dispatch(adapter_class):
    """Install a no-op-by-default dispatch seam before Safety subscriptions bind callbacks."""
    for method_name in ('on_safety_input', 'on_scan', 'on_lifecycle'):
        original = getattr(adapter_class, method_name)
        if getattr(original, '_b23_r04_dispatch', False):
            continue
        def dispatch(adapter, message, _original=original, _method=method_name):
            injector = getattr(adapter, '_b23_r04_injector', None)
            if injector is None:
                return _original(adapter, message)
            return injector(_method, message, _original)
        dispatch._b23_r04_dispatch = True
        setattr(adapter_class, method_name, dispatch)


def install_r04_delivery_fault(adapter, case, emit, *, delay_s=None):
    """Inject only at the actual Safety callback boundary; preserve message bytes."""
    expected = {
        'R04a': ('on_safety_input', 'delay_noisy_odometry_delivery_300ms_once', 0.300),
        'R04b': ('on_safety_input', 'drop_policy_noisy_odometry_delivery', None),
        'R04c': ('on_scan', 'delay_scan_delivery_650ms_once', 0.650),
        'R04d': ('on_lifecycle', 'delay_lifecycle_delivery_650ms_once', 0.650),
    }
    try:
        method_name, hook_name, production_delay = expected[case]
    except KeyError as error:
        raise ValueError('unsupported R04 delivery fault') from error
    import threading
    state = {'triggered': 0, 'scheduled': 0, 'delivered': 0, 'timers': [],
        'lock': threading.Lock(), 'case':case,
        'delay_s': (production_delay if delay_s is None else delay_s),
        'ingress_scheduled':False, 'repeat_held':0, 'target_lifecycle':None}
    def eligible(message):
        if case == 'R04a':
            return message.admission_state == message.ADMISSION_POLICY_OPEN
        if case == 'R04b':
            return message.admission_state == message.ADMISSION_POLICY_OPEN
        return True
    def callback(actual_method, message, original):
        if actual_method != method_name:
            return original(adapter, message)
        if not eligible(message):
            return original(adapter, message)
        if case == 'R04b':
            state['triggered'] += 1
            emit('B23_R04_NOISY_ODOMETRY_DROPPED', {
                'case': case, 'sample_sequence': message.sample_sequence,
                'header_stamp_ns': message.header.stamp.sec * 1_000_000_000 + message.header.stamp.nanosec,
                'steady_ns': time.monotonic_ns()})
            return None
        with state['lock']:
            if state['triggered']:
                if case == 'R04d':
                    target = state['target_lifecycle']
                    if (state['delivered'] == 0 and target is not None
                            and int(message.sequence) >= target[0]):
                        state['repeat_held'] += 1
                        held_count = state['repeat_held']
                        emit('B23_R04_LIFECYCLE_REPEAT_HELD', {
                            'case':case, 'sequence':int(message.sequence),
                            'target_sequence':target[0],
                            'identity':[int(message.episode_generation),
                                int(message.reset_epoch),int(message.runtime_generation)],
                            'steady_ns':time.monotonic_ns(),'held_count':held_count})
                        return None
                return original(adapter, message)
            state['triggered'] += 1
            if case == 'R04d':
                state['target_lifecycle'] = (int(message.sequence),
                    int(message.episode_generation), int(message.reset_epoch),
                    int(message.runtime_generation))
        delay = production_delay if delay_s is None else delay_s
        received_ns = time.monotonic_ns()
        header = getattr(message, 'header', None)
        stamp = getattr(header, 'stamp', None)
        stamp_ns_value = (stamp.sec * 1_000_000_000 + stamp.nanosec
                          if stamp is not None else None)
        emit('B23_R04_DELIVERY_DELAY_SCHEDULED', {
            'case': case, 'hook': hook_name, 'delay_s': delay,
            'source_stamp_ns': stamp_ns_value,
            'sample_sequence': getattr(message, 'sample_sequence', None),
            'callback_received_ns': received_ns})
        delivered_message = copy.deepcopy(message)
        def deliver():
            emit('B23_R04_DELIVERY_DELAYED_CALLBACK', {
                'case': case, 'hook': hook_name, 'delay_s': delay,
                'source_stamp_ns': stamp_ns_value,
                'sample_sequence': getattr(delivered_message, 'sample_sequence', None),
                'delivery_ns': time.monotonic_ns()})
            try:
                original(adapter, delivered_message)
            finally:
                state['delivered'] += 1
        # The awaited policy transaction can block its asyncio loop while ROS
        # callbacks continue.  A loop timer then fires after the test window;
        # a real timer keeps the injected delivery delay independent of that loop.
        timer = threading.Timer(delay, deliver)
        timer.daemon = True
        state['timers'].append(timer)
        # Keep scheduling distinct from callback execution.  The policy step
        # may fail before this bounded delayed callback runs; the R04a error
        # path must still know that exactly one delivery was scheduled.
        state['scheduled'] += 1
        timer.start()
        return None
    adapter._b23_r04_injector = callback
    return state


def r04_policy_step_fault_plan(case):
    """Arm R04 delivery faults on the policy step their contract measures.

    R04a/R04b deliberately invalidate the current step. R04c first needs one
    committed POLICY transition as a control, then delays a scan during the
    following step to prove stale-input rejection. Arming R04c on the control
    step can phase-align its first cutoff with the not-yet-applied newest
    receipt and prevent the control transaction from completing.
    """
    plans = {
        'R04a': ('R04a', None),
        'R04b': ('R04b', None),
        'R04c': (None, 'R04c'),
    }
    try:
        return plans[case]
    except (KeyError, TypeError) as error:
        raise ValueError('unsupported R04 POLICY-step fault plan') from error


def r04d_final_lifecycle_dispatch(original, marker_path, emit, schedule):
    """Delay the final-publisher lifecycle callback only during the R04d window.

    R04d measures a delayed Safety callback. Keeping the final publisher on its
    previously bound identity during that same window prevents it from emitting
    a receipt with a lifecycle tuple the native backend has not bound yet. The
    packet-scoped marker is written by the worker immediately before the reset
    lifecycle request; outside that interval this is a transparent dispatch.
    """
    marker_path = Path(marker_path)
    pending = {}
    def dispatch(node, message):
        if not marker_path.exists():
            return original(node, message)
        marker = json.loads(marker_path.read_bytes())
        if (marker.get('schema') != 'b23_r04d_delay_marker/v1'
                or marker.get('run_id') != node._b23_r04d_run_id
                or marker.get('invocation_id') != node._b23_r04d_invocation_id
                or type(marker.get('baseline_sequence')) is not int
                or not isinstance(marker.get('baseline_identity'), list)
                or len(marker['baseline_identity']) != 3
                or any(type(value) is not int for value in marker['baseline_identity'])
                or type(marker.get('delay_ns')) is not int
                or marker['delay_ns'] <= 0):
            raise RuntimeError('R04d final lifecycle marker ownership/schema mismatch')
        sequence = int(message.sequence)
        if sequence <= marker['baseline_sequence']:
            return original(node, message)
        key = (sequence, int(message.episode_generation), int(message.reset_epoch),
            int(message.runtime_generation))
        if list(key[1:]) == marker['baseline_identity']:
            return original(node, message)
        if key in pending:
            return None
        received_ns = time.monotonic_ns()
        pending[key] = True
        release_after_ns = received_ns + marker['delay_ns']
        source_stamp_ns = (int(message.header.stamp.sec) * 1_000_000_000
            + int(message.header.stamp.nanosec))
        emit('R04D_FINAL_LIFECYCLE_DELIVERY_SCHEDULED', {
            'run_id': marker['run_id'], 'invocation_id': marker['invocation_id'],
            'sequence': sequence, 'identity': list(key[1:]),
            'source_stamp_ns': source_stamp_ns, 'received_ns': received_ns,
            'release_after_ns': release_after_ns, 'delay_ns': marker['delay_ns']})
        def deliver():
            pending.pop(key, None)
            delivered_ns = time.monotonic_ns()
            original(node, message)
            emit('R04D_FINAL_LIFECYCLE_DELIVERY_COMPLETED', {
                'run_id': marker['run_id'], 'invocation_id': marker['invocation_id'],
                'sequence': sequence, 'identity': list(key[1:]),
                'source_stamp_ns': source_stamp_ns,
                'received_ns': received_ns, 'delivery_ns': delivered_ns})
        schedule(node, release_after_ns, deliver)
        return None
    return dispatch


def r04d_stale_safety_rejection_after_delivery(events, *, delivery_ns, source_stamp_ns):
    """Select only the stale-Safety fact observed after the injected callback ran."""
    for name, facts in events:
        if (name == 'SAFETY_REJECTED'
                and 'LIFECYCLE_STALE_OR_FUTURE' in facts.get('reasons', ())
                and type(facts.get('steady_ns')) is int
                and facts['steady_ns'] >= delivery_ns
                and type(facts.get('ros_ns')) is int
                and facts['ros_ns'] - source_stamp_ns > 500_000_000):
            return facts
    return None


def r04d_final_lifecycle_delivery(rows, *, sequence, identity):
    """Find the exact live final-publisher lifecycle delivery for this reset."""
    return next((row.get('facts', {}) for row in rows
        if row.get('event') == 'R04D_FINAL_LIFECYCLE_DELIVERY_COMPLETED'
        and row.get('facts', {}).get('sequence') == sequence
        and row.get('facts', {}).get('identity') == identity
        and type(row.get('facts', {}).get('delivery_ns')) is int), None)


def r04d_ingress_lifecycle_delay_s(safety_lifecycle_delay_s):
    """Keep ingress bound until after both lifecycle consumers can switch."""
    if (type(safety_lifecycle_delay_s) not in (int, float)
            or safety_lifecycle_delay_s <= 0):
        raise ValueError('R04d Safety lifecycle delay must be positive')
    # The held new-context SAFE_STOP receipt is released after the same delay
    # from the final-publisher callback. Let ingress switch just after that
    # callback, so old-context receipts cannot straddle the ingress binding.
    final_publisher_delay_s = 0.700
    return max(float(safety_lifecycle_delay_s) + 0.075,
        final_publisher_delay_s + 0.025)


def r04d_final_publisher_precedes_ingress(final_delivery_ns, ingress_delivery_ns):
    """Require publisher identity to switch before ingress accepts the new lifecycle."""
    return (type(final_delivery_ns) is int and type(ingress_delivery_ns) is int
        and final_delivery_ns <= ingress_delivery_ns)


def r04d_final_safe_stop_dispatch(original, marker_path, emit, schedule, *, safe_stop_source):
    """Keep a new-context zero receipt out of the native gate until R04d observes stale Safety."""
    marker_path = Path(marker_path)
    pending = set()
    def dispatch(node, envelope):
        if not marker_path.exists():
            return original(node, envelope)
        marker = json.loads(marker_path.read_bytes())
        if (marker.get('schema') != 'b23_r04d_delay_marker/v1'
                or marker.get('run_id') != node._b23_r04d_run_id
                or marker.get('invocation_id') != node._b23_r04d_invocation_id
                or not isinstance(marker.get('baseline_identity'), list)
                or len(marker['baseline_identity']) != 3
                or type(marker.get('delay_ns')) is not int or marker['delay_ns'] <= 0
                or type(marker.get('safe_stop_source_instance_id')) is not int):
            raise RuntimeError('R04d final SAFE_STOP marker ownership/schema mismatch')
        identity = [int(envelope.episode_generation), int(envelope.reset_epoch),
            int(envelope.runtime_generation)]
        if (envelope.source != safe_stop_source
                or envelope.source_instance_id != marker['safe_stop_source_instance_id']
                or identity == marker['baseline_identity']):
            return original(node, envelope)
        key = (int(envelope.sequence), *identity)
        if key in pending:
            return None
        pending.add(key)
        received_ns = time.monotonic_ns()
        release_after_ns = received_ns + marker['delay_ns']
        emit('R04D_FINAL_NEW_CONTEXT_SAFE_STOP_HELD', {
            'run_id':marker['run_id'],'invocation_id':marker['invocation_id'],
            'source_sequence':int(envelope.sequence),'source_instance_id':int(envelope.source_instance_id),
            'identity':identity,'received_ns':received_ns,'release_after_ns':release_after_ns,
            'delay_ns':marker['delay_ns']})
        def deliver():
            original(node, envelope)
            emit('R04D_FINAL_NEW_CONTEXT_SAFE_STOP_RELEASED', {
                'run_id':marker['run_id'],'invocation_id':marker['invocation_id'],
                'source_sequence':int(envelope.sequence),'identity':identity,
                'received_ns':received_ns,'delivery_ns':time.monotonic_ns()})
        schedule(node, release_after_ns, deliver)
        return None
    return dispatch


def verify_r02e_prebind_admission_rejected(rows, *, held_sample_sequence,
                                           fresh_sample_sequence, pending_token,
                                           session_id, backend_instance_id,
                                           ingress_instance_id,
                                           allow_pending=False):
    """Require native enqueue order before judging stale/current slot admission."""
    accepted = [row for row in rows if row.get('kind') == 'B23_ADMISSION_ACCEPTED']
    if any(int(row.get('fields', {}).get('sample', '0')) == held_sample_sequence for row in accepted):
        raise RuntimeError('R02e pre-bind sample was accepted by the new native slot')
    expected_identity = {'session': str(session_id),
        'backend': str(backend_instance_id), 'ingress': str(ingress_instance_id)}
    enqueue_rows = [(index, row) for index, row in enumerate(rows)
        if row.get('kind') == 'B23_SAFETY_INPUT_ENQUEUED']
    by_sample = {}
    for sample_sequence in (held_sample_sequence, fresh_sample_sequence):
        matching = [(index, row) for index, row in enqueue_rows
            if int(row.get('fields', {}).get('sample', '0')) == sample_sequence]
        if not matching:
            if allow_pending:
                return None
            raise RuntimeError('R02e native SafetyInput enqueue evidence is incomplete')
        if len(matching) != 1:
            raise RuntimeError('R02e native SafetyInput enqueue was not unique')
        index, row = matching[0]
        fields = row.get('fields', {})
        if any(fields.get(key) != value for key, value in expected_identity.items()):
            raise RuntimeError('R02e native SafetyInput enqueue identity mismatch')
        by_sample[sample_sequence] = index
    if by_sample[held_sample_sequence] >= by_sample[fresh_sample_sequence]:
        raise RuntimeError('R02e pre-bind SafetyInput was enqueued after the fresh input')
    fresh = [row for row in accepted
        if int(row.get('fields', {}).get('sample', '0')) == fresh_sample_sequence]
    if not fresh and allow_pending:
        return None
    if len(fresh) != 1 or not any(pending_token):
        raise RuntimeError('R02e fresh post-bind admission was not accepted exactly once')
    fresh_accept_index = next(index for index, row in enumerate(rows)
        if row.get('kind') == 'B23_ADMISSION_ACCEPTED'
        and int(row.get('fields', {}).get('sample', '0')) == fresh_sample_sequence)
    if fresh_accept_index <= by_sample[fresh_sample_sequence]:
        raise RuntimeError('R02e fresh admission acceptance preceded its native enqueue')
    return {'prebind_sample_sequence': held_sample_sequence,
        'prebind_native_accept_count': 0,
        'postbind_sample_sequence': fresh_sample_sequence,
        'postbind_native_accept_count': 1,
        'prebind_enqueued_before_fresh': True,
        'pending_token_nonzero': True}


def verify_r02e_safety_input_enqueued(rows, *, sample_sequence, session_id,
                                     backend_instance_id, ingress_instance_id,
                                     allow_pending=False):
    """Bind one native callback-queue record to this run's exact sample identity."""
    matching = [row for row in rows if row.get('kind') == 'B23_SAFETY_INPUT_ENQUEUED'
        and int(row.get('fields', {}).get('sample', '0')) == sample_sequence]
    if not matching and allow_pending:
        return None
    if len(matching) != 1:
        raise RuntimeError('R02e native SafetyInput enqueue evidence is missing or duplicated')
    row = matching[0]
    fields = row.get('fields', {})
    if (fields.get('session') != str(session_id)
            or fields.get('backend') != str(backend_instance_id)
            or fields.get('ingress') != str(ingress_instance_id)):
        raise RuntimeError('R02e native SafetyInput enqueue identity mismatch')
    return row


def complete_jsonl_rows(path):
    """Read complete newline-terminated records, leaving a partial tail pending."""
    raw = Path(path).read_bytes()
    rows = []
    for line in raw.splitlines(keepends=True):
        if not line.endswith(b'\n'):
            break
        if line.strip():
            rows.append(json.loads(line))
    return rows


def policy_bind_launch_window_remaining_ns(ros_ns, period_ns):
    """Return whether the next scan cutoff leaves the measured bind window."""
    if type(ros_ns) is not int or ros_ns < 0:
        raise ValueError('ROS time must be a non-negative integer')
    if type(period_ns) is not int or period_ns <= 0:
        raise ValueError('scan period must be a positive integer')
    phase_ns = ros_ns % period_ns
    return period_ns - phase_ns if phase_ns else 0


def policy_bind_launch_window_ready(remaining_ns):
    """Select the measured 40-60 ms pre-scan window for a pending bind.

    Runtime evidence showed that an 80 ms window could spend about 20 ms on
    the bind ACK, about 69 ms waiting for the first post-ACK sample, then
    cross a deferred scan edge and exceed the unchanged 100 ms native
    watchdog. The narrower later window leaves that sensor wait inside the
    watchdog budget while retaining the existing post-cutoff tick check.
    """
    return type(remaining_ns) is int and 40_000_000 <= remaining_ns <= 60_000_000


def r05_contact_coverage_mask_event(path):
    """Poll the delayed native event without treating its not-yet-created file as fatal."""
    try:
        rows = complete_jsonl_rows(path)
    except FileNotFoundError:
        return None
    return next((row for row in rows
        if row.get('kind') == 'B23_CONTACT_COVERAGE_MASKED'
        and row.get('fields', {}).get('masked') == '1'), None)


async def verify_r03_receipt_fault(io, *, case, step_index, error):
    """Bind injected native receipt disposition to the real published POLICY."""
    import re
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import B1SnapshotPending
    native_fault_match = (re.fullmatch(r'native fault flags=([1-9][0-9]*)', str(error))
        if isinstance(error, RuntimeError) else None)
    expected_native_flags = int(native_fault_match.group(1)) if native_fault_match else None
    if not isinstance(error, (B1SnapshotPending, TimeoutError)) and expected_native_flags is None:
        raise RuntimeError('R03 did not stop through the expected cutoff/receipt path')
    rows = [json.loads(line) for line in
        (Path(io.descriptor['run_root'])/'native-events.jsonl').read_text().splitlines() if line.strip()]
    mode = 'drop_policy_once' if case == 'R03a' else 'mutate_policy_transition_id_once'
    injected = [row for row in rows if row.get('kind') == 'B23_RECEIPT_FAULT'
        and row.get('fields', {}).get('mode') == mode]
    if len(injected) != 1:
        raise RuntimeError('R03 native receipt hook evidence is missing or repeated')
    fault_fields = injected[0].get('fields', {})
    try:
        fault_sequence = int(fault_fields['sequence'])
        fault_publisher = int(fault_fields['publisher'])
        fault_source_sequence = int(fault_fields['source_sequence'])
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError('R03 native receipt hook identity is incomplete') from error
    # Bind the injected fault to the publisher's durable pre-transport record.
    # For R03a the point of the hook is that the matching receipt never reaches
    # io.ingress.receipts, so that receive-side collection cannot prove which
    # final publication the native hook dropped.
    publication_rows = _ledger_rows(io.descriptor['run_root'], 'policy_final_published.jsonl')
    publications = [row.get('facts', {}) for row in publication_rows
        if row.get('event') == 'policy_final_published'
        and row.get('facts', {}).get('source_sequence') == step_index
        and row.get('facts', {}).get('publisher_instance_id') == io.final.publisher_instance_id
        and row.get('facts', {}).get('publish_sequence') == fault_sequence]
    if (fault_publisher != io.final.publisher_instance_id or fault_source_sequence != step_index
            or len(publications) != 1):
        raise RuntimeError('R03 native hook does not bind to one exact final POLICY publication')
    publication = publications[0]
    if (publication.get('step_index') != step_index
            or type(publication.get('source_instance_id')) is not int
            or type(publication.get('steady_ns')) is not int
            or not publication.get('transition_id')
            or not isinstance(publication.get('receipt_cdr_hex'), str)
            or not publication['receipt_cdr_hex']):
        raise RuntimeError('R03 final POLICY publication evidence is incomplete')
    from rclpy.serialization import deserialize_message
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
    try:
        published_receipt = deserialize_message(
            bytes.fromhex(publication['receipt_cdr_hex']), FinalIssuedCommandReceipt)
    except (TypeError, ValueError) as decode_error:
        raise RuntimeError('R03 final POLICY receipt bytes are invalid') from decode_error
    if (published_receipt.source != FinalIssuedCommandReceipt.SOURCE_POLICY
            or published_receipt.sequence != step_index
            or published_receipt.step_index != step_index
            or published_receipt.source_instance_id != publication['source_instance_id']
            or published_receipt.transition_id != publication['transition_id']
            or published_receipt.final_publisher_instance_id != fault_publisher
            or published_receipt.final_publish_sequence != fault_sequence):
        raise RuntimeError('R03 final publication bytes do not match the native hook identity')
    receipt_ingress = [row for row in rows if row.get('kind') == 'B23_POLICY_RECEIPT_INGRESS'
        and row.get('fields', {}).get('sequence') == str(fault_sequence)]
    if (case == 'R03a' and receipt_ingress) or (case == 'R03b' and len(receipt_ingress) != 1):
        raise RuntimeError('R03 native receipt ingress does not match packet fault')
    state = io.ingress.backend_state
    if expected_native_flags is not None and (state is None or state.fault_flags != expected_native_flags):
        raise RuntimeError('R03 native fault stop reason does not match observed backend state')
    observe_deadline = min(io.deadline_ns, io.now() + 250_000_000)
    while ((state is None or state.fault_flags == 0 or not state.local_zero_override)
           and io.now() < observe_deadline):
        before = io.now()
        await io.pause(min(.005, max(0., (observe_deadline-before)/1e9)))
        if io.now() <= before:
            raise RuntimeError('R03 fault evidence wait did not advance monotonic time')
        state = io.ingress.backend_state
    if state is None or state.fault_flags == 0 or not state.local_zero_override:
        raise RuntimeError('R03 did not observe native fault with zero override')
    if any(row[0] == 'POLICY_STEP_COMPLETE' and row[1].get('step_index') == step_index
           for row in io.events):
        raise RuntimeError('R03 unexpectedly completed a POLICY step')
    if case == 'R03b':
        fields = injected[0]['fields']
        if fields.get('original_transition_id') == fields.get('mutated_transition_id'):
            raise RuntimeError('R03b did not mutate only the native receipt copy')
    return {'expected_fault': True, 'case': case, 'step_index': step_index,
        'stop_reason': ('native_fault_flags=' + str(expected_native_flags)
            if expected_native_flags is not None else type(error).__name__),
        'published_policy_sequence': fault_sequence,
        'native_fault_flags': state.fault_flags, 'local_zero_override': True,
        'policy_step_committed': False, 'native_receipt_hook': fault_fields}


async def verify_r01_pause_ack_failure(io, error):
    """Require an expired pause ACK, observed native fault/zero, and no commit."""
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendControlError
    ack = error.ack if isinstance(error, BackendControlError) else None
    if ack is not None:
        if (ack.response.result != ack.response.RESULT_REJECTED
                or ack.response.reason_code != Control.Response.REASON_CONTROL_EXPIRED):
            raise RuntimeError('pause ACK fault did not produce CONTROL_EXPIRED rejection')
    elif not isinstance(error, TimeoutError):
        raise RuntimeError('pause ACK fault was not reached; reset failed first: '
            + repr(error)) from error
    # The service rejection and the status topic use separate DDS paths. Let
    # the already-running ingress pump collect the corresponding native status
    # for a short bounded evidence window; this does not extend reset or ACK
    # deadlines and never treats the ACK alone as proof of native zero.
    observe_until = min(io.deadline_ns, io.now() + 250_000_000)
    state = io.ingress.backend_state
    while ((state is None or state.fault_flags == 0 or not state.local_zero_override)
           and io.now() < observe_until):
        before = io.now()
        await io.pause(min(0.005, max(0., (observe_until - before) / 1e9)))
        if io.now() <= before:
            raise RuntimeError('pause fault evidence wait did not advance monotonic time')
        state = io.ingress.backend_state
    if state is None or state.fault_flags == 0 or not state.local_zero_override:
        raise RuntimeError('pause ACK fault did not retain native fault and zero override')
    if any(name in {'RESET_POSE_MUTATION_ARMED','B1_RESET_STARTED','B1_RESET_COMMITTED',
                    'RESET_COMPLETE'} for name, _ in io.events):
        raise RuntimeError('pause ACK fault continued reset or committed observation0')
    return {'error_type':type(error).__name__,
        'reason_code':ack.response.reason_code if ack is not None else None,
        'native_fault_flags':state.fault_flags, 'local_zero_override':True,
        'no_pose_mutation':True, 'no_observation0_commit':True}


def case_fault_hooks(case, requested=None):
    """Return the exact hook set allowed for this campaign case."""
    if case not in CASE_HOOKS:
        raise ValueError('unsupported B2.3 campaign case: ' + str(case))
    expected = CASE_HOOKS[case]
    if requested is None:
        return list(expected)
    if requested not in expected:
        raise ValueError('fault hook is not approved for campaign case: ' + str(requested))
    return [requested]


def campaign_phase(case):
    """Return the fixed campaign phase for a supported case."""
    try:
        return CASE_PHASES[case]
    except KeyError as error:
        raise ValueError('unsupported B2.3 campaign case: ' + str(case)) from error


def verify_owned_restart_request(request, *, run_id, invocation_id, case,
                                 role, process_identity_record):
    """Bind one restart request to this run and the exact currently owned PID."""
    identity = request.get('identity') if isinstance(request, dict) else None
    identity_fields = ('pid', 'uid', 'start_ticks', 'argv', 'pgid', 'sid')
    stable_identity_matches = (
        isinstance(identity, dict)
        and isinstance(process_identity_record, dict)
        and all(identity.get(field) == process_identity_record.get(field)
                for field in identity_fields)
        and all(type(identity.get(field)) is int and identity[field] > 0
                for field in ('pid', 'start_ticks', 'pgid', 'sid'))
        and type(identity.get('uid')) is int and identity['uid'] >= 0
        and isinstance(identity.get('argv'), list)
        and bool(identity['argv'])
        and all(isinstance(value, str) and value for value in identity['argv'])
    )
    if (not isinstance(request, dict)
            or request.get('schema') != 'b23_owned_restart_request/v1'
            or request.get('run_id') != run_id
            or request.get('invocation_id') != invocation_id
            or request.get('case') != case
            or request.get('target_role') != role
            or request.get('operation') != 'restart_owned_process'
            or not stable_identity_matches):
        raise ValueError('owned restart request identity mismatch')
    allowed = {'R07c':'server', 'R07d':'final'}
    if allowed.get(case) != role:
        raise ValueError('owned restart role is not authorized for this case')
    return True


async def stop_exact_owned_process(supervisor, record, *, identity, deadline_ns):
    """Stop one identity-pinned process group with bounded TERM/KILL escalation."""
    import signal
    current = process_identity(record.pid)
    keys = ('pid','uid','start_ticks','argv','pgid','sid')
    if any(current.get(key) != identity.get(key) for key in keys):
        raise RuntimeError('owned restart target identity changed before signal')
    if record.process.returncode is None:
        await supervisor.launcher.stop_group(record.process, signal.SIGTERM)
        while time.monotonic_ns() < deadline_ns:
            if record.process.returncode is not None and not supervisor.launcher.group_alive(record.process):
                break
            await asyncio.sleep(min(.01, max(0., (deadline_ns-time.monotonic_ns())/1e9)))
        if record.process.returncode is None or supervisor.launcher.group_alive(record.process):
            current = process_identity(record.pid)
            if any(current.get(key) != identity.get(key) for key in keys):
                raise RuntimeError('owned restart target identity changed before SIGKILL')
            await supervisor.launcher.stop_group(record.process, signal.SIGKILL)
            while time.monotonic_ns() < deadline_ns:
                if record.process.returncode is not None and not supervisor.launcher.group_alive(record.process):
                    break
                await asyncio.sleep(min(.01, max(0., (deadline_ns-time.monotonic_ns())/1e9)))
    if record.process.returncode is None or supervisor.launcher.group_alive(record.process):
        raise TimeoutError('owned restart target group did not terminate before active deadline')
    return {'pid':record.pid, 'exit_status':record.process.returncode,
        'group_absent':True, 'identity':identity}


def technical_outcome(case, success):
    """Keep each case assessment label bound to its actual packet case."""
    if case not in CASE_PHASES:
        raise ValueError('unsupported B2.3 campaign case: ' + str(case))
    return case + '_COMPLETED' if success else 'INCOMPLETE'


def verify_r06_reset_fault(io, *, case, error, anchor_sequence=None):
    """Chấm fault reset qua lỗi của adapter thật, giữ B1/POLICY đóng."""
    from mecanum_nav_rl_interfaces.msg import LocalTrainingSafetyInput
    expected = {
        'R06a': (ValueError, 'measured XY reset error exceeds 0.01 m'),
        'R06b': (ValueError, 'standstill measurement has a missing physics iteration'),
    }
    if case not in {'R06a','R06b','R06c'}:
        raise ValueError('unsupported R06 case')
    if case == 'R06c':
        valid_timeout = (isinstance(error, TimeoutError)
            and 'observation0 did not confirm within reset deadline' in str(error))
        valid_native_expiry = (isinstance(error, RuntimeError)
            and str(error).startswith('native fault flags='))
        if not (valid_timeout or valid_native_expiry):
            raise RuntimeError('R06c did not fail at reset cutoff/receipt expiry: ' + repr(error)) from error
    else:
        error_type, message = expected[case]
        if not isinstance(error, error_type) or message not in str(error):
            raise RuntimeError(case + ' did not fail at its pinned reset acceptance condition: ' + repr(error)) from error
    names = [name for name, _ in io.events]
    forbidden = {'B1_RESET_COMMITTED','RESET_COMPLETE'}
    if case != 'R06c':
        forbidden.add('B1_RESET_STARTED')
    if any(name in forbidden for name in names):
        raise RuntimeError(case + ' advanced observation0/B1 reset despite the expected reset fault')
    issued = _ledger_rows(io.descriptor['run_root'], 'policy_adapter_issued.jsonl') \
        if Path(io.descriptor['run_root'], 'policy_adapter_issued.jsonl').exists() else []
    if issued:
        raise RuntimeError(case + ' issued POLICY before the reset failure')
    if (io.ingress.admission_state != LocalTrainingSafetyInput.ADMISSION_INHIBITED
            or io.ingress.last_published_admission_state != LocalTrainingSafetyInput.ADMISSION_INHIBITED
            or not io.safety.local_training.policy_hold):
        raise RuntimeError(case + ' did not leave POLICY inhibited after reset failure')
    detail = {'case':case, 'expected_rejection':True, 'error_type':type(error).__name__,
        'error':str(error), 'no_observation0_commit':True, 'no_policy_issuance':True,
        'policy_inhibited':True, 'completed_ns':time.monotonic_ns()}
    if case == 'R06a':
        mutations = [facts for name, facts in io.events if name == 'B23_R06A_SET_POSE_TARGET_MUTATED']
        if len(mutations) != 1:
            raise RuntimeError('R06a missing exact SetEntityPose target mutation evidence')
        detail['set_pose_mutation'] = mutations[0]
    elif case == 'R06b':
        omitted = [facts for name, facts in io.events if name == 'B23_R06B_PHYSICS_ITERATION_OMITTED']
        if len(omitted) != 1:
            raise RuntimeError('R06b missing one omitted production measurement record')
        detail['omitted_iteration'] = omitted[0]
    else:
        held = list(io._r06c_held_receipts)
        if (anchor_sequence is None or not held
                or any(row['final_publish_sequence'] <= anchor_sequence for row in held)):
            raise RuntimeError('R06c did not hold a post-anchor SAFE_STOP receipt')
        if valid_native_expiry and not (io.ingress.backend_state is not None
                and bool(io.ingress.backend_state.local_zero_override)):
            raise RuntimeError('R06c native expiry did not retain a verified zero override')
        detail.update({'zero_anchor_sequence':anchor_sequence,
            'held_receipt_count':len(held), 'held_receipts':held,
            'reset_deadline_ns':io._r06c_reset_deadline_ns})
    return detail


def verify_r01b_external_pause_rejection(io, error):
    """Validate the expected production rejection and fail-closed reset stop."""
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendControlError
    if not isinstance(error, BackendControlError):
        raise RuntimeError('R01b did not fail through the backend control response')
    ack = error.ack
    state = io.ingress.backend_state
    if (ack is None or ack.response.result != ack.response.RESULT_REJECTED
            or ack.response.reason_code != Control.Response.REASON_BARRIER_INVALID):
        raise RuntimeError('R01b rejection response does not match unexpected-pause contract')
    if not any(name == 'FAULT_HOOK_EXTERNAL_PAUSE_AFTER_W1' for name, _ in io.events):
        raise RuntimeError('R01b external pause hook was not observed')
    if state is None or state.fault_flags == 0 or not state.local_zero_override:
        raise RuntimeError('R01b did not observe native fault with zero override')
    if any(name in {'RESET_POSE_MUTATION_ARMED','B1_RESET_STARTED','B1_RESET_COMMITTED',
                    'RESET_COMPLETE'} for name, _ in io.events):
        raise RuntimeError('R01b continued reset after unexpected pause')
    return {'reason_code':ack.response.reason_code,
        'request_sequence':ack.request.request_sequence,
        'native_fault_flags':state.fault_flags, 'local_zero_override':True,
        'no_pose_mutation':True, 'no_observation0_commit':True}


def verify_r02_policy_order(root, *, case, step_started_ns):
    """Prove order at the native gate from backend receipt/admission records."""
    rows = [json.loads(line) for line in (Path(root)/'native-events.jsonl').read_text().splitlines() if line.strip()]
    receipts = [row for row in rows if row.get('kind') == 'B23_POLICY_RECEIPT_INGRESS'
        and int(row.get('fields',{}).get('step','0')) == 1
        and int(row.get('fields',{}).get('receive_ns','0')) >= step_started_ns]
    admissions = [row for row in rows if row.get('kind') == 'B23_ADMISSION_ACCEPTED'
        and int(row.get('fields',{}).get('processed_ns','0')) >= step_started_ns]
    if not receipts or not admissions:
        raise RuntimeError('R02 native receipt/admission order evidence is incomplete')
    receipt_ns = int(receipts[0]['fields']['receive_ns'])
    admission_ns = int(admissions[0]['fields']['processed_ns'])
    admission_receive_ns = int(admissions[0]['fields']['receive_ns'])
    expected = admission_ns < receipt_ns if case == 'R02a' else receipt_ns < admission_ns
    if case not in ('R02a','R02b') or not expected:
        raise RuntimeError(f'{case} native gate order mismatch: receipt={receipt_ns} admission={admission_ns}')
    admission_to_receipt_ns = receipt_ns - admission_receive_ns
    receipt_to_admission_ns = admission_ns - receipt_ns
    result = {'case':case,'receipt_ingress_ns':receipt_ns,'admission_received_ns':admission_receive_ns,
        'admission_gate_ns':admission_ns,'admission_minus_receipt_ns':admission_ns-receipt_ns,
        'admission_to_receipt_ns':admission_to_receipt_ns,
        'receipt_to_admission_ns':receipt_to_admission_ns,
        'order':'admission_before_receipt' if admission_ns < receipt_ns else 'receipt_before_admission'}
    if case == 'R02b':
        # R02b covers receipt-before-admission: the native receipt gate must
        # accept this exact POLICY publication after the matching admission is
        # processed, within the contract's 40 ms receipt residence bound.
        receipt_sequence = int(receipts[0]['fields']['sequence'])
        gate_acceptances = [row for row in rows
            if row.get('kind') == 'B23_RECEIPT_GATE_RESULT'
            and row.get('fields', {}).get('source') == '1'
            and row.get('fields', {}).get('key') == str(receipt_sequence)
            and row.get('fields', {}).get('reason') == 'accepted_once']
        if not gate_acceptances:
            raise RuntimeError('R02b lacks accepted native gate result for the observed POLICY receipt')
        gate_accepted_ns = int(gate_acceptances[0]['fields']['steady_ns'])
        gate_disposition = int(gate_acceptances[0]['fields']['disposition'])
        receipt_residence_ns = gate_accepted_ns - receipt_ns
        if gate_disposition != 3 or not (receipt_ns <= admission_ns <= gate_accepted_ns):
            raise RuntimeError(
                'R02b POLICY receipt was not accepted after the matching admission: '
                f'receipt={receipt_ns} admission={admission_ns} gate={gate_accepted_ns} '
                f'disposition={gate_disposition}')
        if not 0 <= receipt_residence_ns <= 40_000_000:
            raise RuntimeError('R02b native receipt exceeded the 40 ms bounded gate hold')
        result.update({'receipt_gate_accepted_ns':gate_accepted_ns,
            'receipt_gate_disposition':gate_disposition,
            'receipt_residence_ns':receipt_residence_ns})
    return result


def r02a_native_admission_row(rows, *, sample_sequence, session_id,
                              backend_instance_id, ingress_instance_id,
                              step_started_ns):
    """Select current-step admission accepted by the pinned native session."""
    for row in rows:
        if row.get('kind') != 'B23_ADMISSION_ACCEPTED':
            continue
        fields = row.get('fields', {})
        try:
            receive_ns = int(fields['receive_ns'])
            processed_ns = int(fields['processed_ns'])
            sample = int(fields['sample'])
            backend = int(fields['backend'])
            ingress = int(fields['ingress'])
        except (KeyError, TypeError, ValueError):
            continue
        if (sample == sample_sequence and fields.get('session') == session_id
                and backend == backend_instance_id and ingress == ingress_instance_id
                and receive_ns >= step_started_ns and processed_ns >= receive_ns):
            return row
    return None


def verify_r02f_safety_hold(io, *, step_index, receipt, backend_state):
    """Verify a real Safety rejection and matching native SAFE_STOP application."""
    from mecanum_nav_rl_interfaces.msg import CommandEnvelope, FinalIssuedCommandReceipt
    from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
    rejected = next((facts for name, facts in io.events
        if name == 'SAFETY_REJECTED' and facts.get('candidate_sequence') == step_index
        and facts.get('candidate_source') == CommandEnvelope.SOURCE_POLICY
        and facts.get('candidate_source_instance_id') == io.policy_source_id
        and 'POLICY_HELD' in facts.get('reasons', ())), None)
    if rejected is None:
        raise RuntimeError('R02f missing production Safety rejection for issued POLICY')
    if not isinstance(receipt, FinalIssuedCommandReceipt):
        raise RuntimeError('R02f final publisher receipt has the wrong generated message type')
    final_command = (receipt.final_command.linear.x, receipt.final_command.linear.y,
        receipt.final_command.angular.z)
    if (receipt.source != FinalIssuedCommandReceipt.SOURCE_SAFE_STOP
            or any(final_command)):
        raise RuntimeError('R02f final publisher did not publish the held POLICY as zero SAFE_STOP')
    if (backend_state is None or backend_state.fault_flags != 0
            or backend_state.local_zero_override
            or not backend_state.applied_receipt_valid
            or backend_state.applied_final_publisher_instance_id != receipt.final_publisher_instance_id
            or backend_state.applied_final_publish_sequence != receipt.final_publish_sequence):
        raise RuntimeError('R02f native backend did not apply the exact SAFE_STOP receipt')
    if any(item.source is ReceiptSource.POLICY and item.sequence == step_index
            for item in io.ingress.receipts):
        raise RuntimeError('R02f issued POLICY reached the final receipt/backend path')
    return {'safety_rejected':True,'reasons':list(rejected.get('reasons', ())),
        'safe_stop_applied':True,'final_publish_sequence':receipt.final_publish_sequence,
        'backend_iteration':backend_state.applied_physics_iteration,
        'policy_receipt_absent':True}


def verify_r04_stale_delivery(io, *, case, policy_step_index=None):
    """Bind delayed source input to real Safety stale rejection and recovery."""
    expected_reason = {'R04a':'NOISY_STALE_OR_FUTURE',
        'R04c':'SCAN_STALE_OR_FUTURE'}.get(case)
    if expected_reason is None:
        raise ValueError('R04 stale-delivery verifier supports R04a/R04c only')
    scheduled = next((facts for name, facts in io.events
        if name == 'B23_R04_DELIVERY_DELAY_SCHEDULED' and facts.get('case') == case), None)
    delayed = next((facts for name, facts in io.events
        if name == 'B23_R04_DELIVERY_DELAYED_CALLBACK' and facts.get('case') == case), None)
    if scheduled is None or delayed is None:
        raise RuntimeError(case + ' lacks delayed callback evidence')
    if delayed['delivery_ns'] - scheduled['callback_received_ns'] < int(scheduled['delay_s'] * 1e9):
        raise RuntimeError(case + ' callback delay was shorter than the pinned injection')
    if scheduled.get('source_stamp_ns') is None:
        raise RuntimeError(case + ' delayed message has no original source timestamp')
    if delayed.get('sample_sequence') != scheduled.get('sample_sequence'):
        raise RuntimeError(case + ' delayed callback identity does not match scheduled input')
    if case == 'R04a':
        rejected = next((facts for name, facts in io.events
            if name == 'SAFETY_REJECTED'
            and 'NOISY_STALE_OR_FUTURE' in facts.get('reasons', ())
            and facts.get('steady_ns', 0) >= delayed['delivery_ns']), None)
        if rejected is None:
            raise RuntimeError('R04a lacks production Safety rejection of the delayed stale noisy sample')
        if (type(rejected.get('ros_ns')) is not int
                or rejected['ros_ns'] - scheduled['source_stamp_ns'] <= 250_000_000):
            raise RuntimeError('R04a Safety rejection is not bound to the stale source timestamp')
        if any(name == 'SAFETY_ACCEPTED'
                and facts.get('candidate_source') == 1
                and facts.get('steady_ns', 0) > rejected['steady_ns']
                for name, facts in io.events):
            raise RuntimeError('R04a Safety accepted POLICY after delayed-input invalidation')
        if any(name == 'b1_transition_committed'
                and facts.get('steady_ns', 0) > rejected['steady_ns']
                for name, facts in io.events):
            raise RuntimeError('R04a B1 committed after delayed-input invalidation')
        if rejected['steady_ns'] < delayed['delivery_ns']:
            raise RuntimeError('R04a Safety block preceded delayed-input rejection')
        return {'case':case, 'delay_s':scheduled['delay_s'],
            'delayed_input_rejected':True, 'safety_blocked':True,
            'safety_rejection_reasons':list(rejected.get('reasons', ())),
            'rejected_steady_ns':rejected['steady_ns'],
            'rejected_ros_ns':rejected['ros_ns'],
            'source_ros_age_ns':rejected['ros_ns'] - scheduled['source_stamp_ns'],
            'source_stamp_ns':scheduled['source_stamp_ns'],
            'fresh_policy_recovery':False}
    rejected = next((facts for name, facts in io.events
        if name == 'SAFETY_REJECTED' and expected_reason in facts.get('reasons', ())), None)
    if rejected is None:
        raise RuntimeError(case + ' lacks actual Safety stale rejection')
    max_age_ns = 250_000_000 if case == 'R04a' else 500_000_000
    if (rejected['steady_ns'] < delayed['delivery_ns']
            or type(rejected.get('ros_ns')) is not int
            or rejected['ros_ns'] - scheduled['source_stamp_ns'] <= max_age_ns):
        raise RuntimeError(case + ' Safety rejection is not bound to the delayed stale source sample')
    accepted = None
    if policy_step_index is not None:
        from mecanum_nav_rl_interfaces.msg import CommandEnvelope
        accepted = next((facts for name, facts in io.events
            if name == 'SAFETY_ACCEPTED'
            and facts.get('candidate_sequence') == policy_step_index
            and facts.get('candidate_source') == CommandEnvelope.SOURCE_POLICY
            and facts.get('candidate_source_instance_id') == io.policy_source_id), None)
        if accepted is None:
            raise RuntimeError(case + ' did not recover using a fresh Safety input for the POLICY slot')
        if accepted['steady_ns'] <= rejected['steady_ns']:
            raise RuntimeError(case + ' POLICY acceptance preceded stale-input rejection')
    return {'case':case, 'delay_s':scheduled['delay_s'],
        'stale_rejection_reason':expected_reason, 'rejected_steady_ns':rejected['steady_ns'],
        'source_stamp_ns':scheduled['source_stamp_ns'],
        'fresh_policy_recovery':accepted is not None}


async def await_r04a_production_rejection(io, *, deadline_ns):
    """Wait boundedly for Safety's tick after the delayed callback is delivered."""
    # A failed POLICY step may exit before policy_step() restores its periodic
    # Safety output stream. Keep motion held, but resume the real Safety tick
    # so it can evaluate the delayed source sample and publish its fail-closed
    # SAFE_STOP. Without this, the worker waits for a rejection from a timer
    # that the same failed transaction left disabled.
    adapter = io.safety.local_training
    adapter.set_policy_hold(True)
    adapter.set_stream_enabled(True)
    def observed():
        delayed = next((facts for name, facts in reversed(io.events)
            if name == 'B23_R04_DELIVERY_DELAYED_CALLBACK' and facts.get('case') == 'R04a'), None)
        if delayed is None:
            return None
        return next((facts for name, facts in reversed(io.events)
            if name == 'SAFETY_REJECTED'
            and 'NOISY_STALE_OR_FUTURE' in facts.get('reasons', ())
            and facts.get('steady_ns', 0) >= delayed.get('delivery_ns', 0)), None)
    return await io.until(observed, deadline_ns=deadline_ns,
        phase='R04a bounded production Safety rejection after delayed stale input',
        expected_native_fault_flags=(4, 6))


async def await_r04a_post_rejection_zero(io, rejection, *, deadline_ns):
    """Require a native zero/inhibit status sampled after the Safety rejection."""
    from mecanum_nav_rl_interfaces.msg import SimulationContactState
    rejected_ns = rejection.get('steady_ns') if isinstance(rejection, dict) else None
    if type(rejected_ns) is not int or rejected_ns <= 0:
        raise ValueError('R04a Safety rejection has no steady timestamp')
    expected_flags = (SimulationContactState.FAULT_COMMAND_STALE,
        SimulationContactState.FAULT_COMMAND_SEQUENCE | SimulationContactState.FAULT_COMMAND_STALE)
    def observed():
        state = io.ingress.backend_state
        received_ns = io.ingress.backend_received_ns
        if (state is None or type(received_ns) is not int or received_ns <= rejected_ns
                or state.fault_flags not in expected_flags
                or not state.local_zero_override or not state.actuator_inhibited):
            return None
        return {'status_sequence':state.status_sequence, 'status_received_ns':received_ns,
            'fault_flags':int(state.fault_flags), 'local_zero_override':True,
            'actuator_inhibited':True, 'after_safety_rejection':True}
    result = await io.until(observed, deadline_ns=deadline_ns,
        phase='R04a backend zero status sampled after stale Safety rejection',
        expected_native_fault_flags=expected_flags)
    io.emit('R04A_POST_REJECTION_ZERO_OBSERVED', result)
    return result


def verify_r04b_missing_noisy_admission(*, issued_rows, transition_identity,
        run_id, invocation_id, policy_receipts, final_rows, applied_rows,
        committed_rows, worker_events):
    """Verify R04b rejected the bound candidate before final publication.

    Adapter issuance records a POLICY candidate delivered to Safety; it is not
    evidence that the candidate passed Safety or reached the actuator path.
    This check binds the one expected candidate to the active B1 slot and then
    requires every downstream ledger to contain no record for that slot.
    """
    if transition_identity is None:
        raise RuntimeError('R04b lost the active B1 transition identity')
    transition_id = getattr(transition_identity, 'transition_id', None)
    step_index = getattr(transition_identity, 'step_index', None)
    lifecycle_identity = getattr(transition_identity, 'identity', None)
    identity = [getattr(lifecycle_identity, name, None) for name in (
        'episode_generation', 'reset_epoch', 'runtime_generation')]
    if (not transition_id or type(step_index) is not int
            or any(type(value) is not int for value in identity)):
        raise RuntimeError('R04b active B1 transition identity is incomplete')

    candidates = [row for row in issued_rows
        if row.get('event') == 'policy_adapter_issued'
        and row.get('run_id') == run_id
        and row.get('invocation_id') == invocation_id]
    if len(candidates) != 1:
        raise RuntimeError('R04b requires exactly one run-bound adapter candidate')
    row = candidates[0]
    facts = row.get('facts', {})
    if (facts.get('transition_id') != transition_id
            or facts.get('step_index') != step_index
            or facts.get('sequence') != step_index
            or facts.get('identity') != identity
            or type(facts.get('source_instance_id')) is not int
            or type(facts.get('steady_ns')) is not int):
        raise RuntimeError('R04b adapter candidate does not match active B1 slot')

    if any(getattr(receipt, 'source', None) == 1 for receipt in policy_receipts):
        raise RuntimeError('R04b POLICY receipt reached native ingress')
    downstream = (final_rows, applied_rows, committed_rows)
    if any(any(item.get('facts', {}).get('transition_id') == transition_id
            for item in ledger) for ledger in downstream):
        raise RuntimeError('R04b rejected POLICY slot reached a downstream ledger')
    dropped = [(name, event_facts) for name, event_facts in worker_events
        if name == 'B23_R04_NOISY_ODOMETRY_DROPPED'
        and event_facts.get('case') == 'R04b'
        and type(event_facts.get('sample_sequence')) is int
        and type(event_facts.get('steady_ns')) is int]
    if len(dropped) != 1 or dropped[0][1]['steady_ns'] < facts['steady_ns']:
        raise RuntimeError('R04b missing-noisy hook is not bound after the active candidate')
    return {'step_index':step_index, 'transition_id':transition_id,
        'source_instance_id':facts['source_instance_id'],
        'identity':identity, 'adapter_candidates':1,
        'native_policy_receipts':0, 'final_publications':0,
        'backend_applications':0, 'b1_policy_commits':0,
        'dropped_sample_sequence':dropped[0][1]['sample_sequence'],
        'missing_admission_after_drop':True}


async def await_r04a_delayed_callback(io, state, *, timeout_ns=1_000_000_000):
    """Wait boundedly for the injected callback after the POLICY attempt stops."""
    deadline_ns = min(io.deadline_ns, io.now() + timeout_ns)
    while state['delivered'] < 1 and io.now() < deadline_ns:
        before = io.now()
        await io.pause(min(0.002, max(0., (deadline_ns - before) / 1e9)))
        if io.now() <= before:
            raise RuntimeError('R04a delayed callback wait did not advance monotonic time')
    if state['triggered'] != 1 or state['scheduled'] != 1 or state['delivered'] != 1:
        raise TimeoutError('R04a delayed callback did not complete exactly once before evidence deadline')
    return next((facts for name, facts in reversed(io.events)
        if name == 'B23_R04_DELIVERY_DELAYED_CALLBACK' and facts.get('case') == 'R04a'), None)


def verify_r04a_next_step_blocked(io, *, step_index):
    """Prove delayed out-of-order Safety input cannot authorize the next slot."""
    rejected = next((facts for name, facts in io.events
        if name == 'SAFETY_REJECTED'
        and 'NOISY_STALE_OR_FUTURE' in facts.get('reasons', ())), None)
    if rejected is None:
        raise RuntimeError('R04a lacks production Safety rejection after delayed-input invalidation')
    if any(name == 'SAFETY_ACCEPTED'
            and facts.get('candidate_source') == 1
            and facts.get('candidate_sequence') == step_index
            for name, facts in io.events):
        raise RuntimeError('R04a Safety accepted the POLICY slot after delayed-input invalidation')
    if any(name == 'b1_transition_committed'
            and facts.get('step_index') == step_index
            for name, facts in io.events):
        raise RuntimeError('R04a B1 committed the POLICY slot after delayed-input invalidation')
    if any(getattr(receipt, 'source_sequence', None) == step_index
            and getattr(receipt, 'source', None) == 1 for receipt in io.ingress.receipts):
        raise RuntimeError('R04a POLICY receipt for the blocked slot reached native ingress')
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
    rejection_ns = rejected.get('steady_ns')
    applied_zero = None
    for name, facts in io.events:
        if (name != 'NATIVE_APPLICATION_JOINED'
                or type(facts.get('steady_ns')) is not int
                or facts['steady_ns'] <= rejection_ns
                or facts.get('source_instance_id') != io.ingress.safe_stop_source_id
                or facts.get('step_index') != 0
                or facts.get('transition_id') != ''):
            continue
        receipt = io.final.publication_for_source_sequence(
            source=FinalIssuedCommandReceipt.SOURCE_SAFE_STOP,
            sequence=facts.get('source_sequence'))
        if (receipt is None
                or receipt.source != FinalIssuedCommandReceipt.SOURCE_SAFE_STOP
                or receipt.source_instance_id != io.ingress.safe_stop_source_id
                or receipt.final_publisher_instance_id != io.final.publisher_instance_id
                or receipt.final_publish_sequence != facts.get('publish_sequence')
                or receipt.sequence != facts.get('source_sequence')
                or any((receipt.final_command.linear.x, receipt.final_command.linear.y,
                        receipt.final_command.angular.z))):
            continue
        applied_zero = {'source_sequence': receipt.sequence,
            'final_publish_sequence': receipt.final_publish_sequence,
            'publisher_instance_id': receipt.final_publisher_instance_id,
            'native_iteration': facts.get('iteration'), 'native_stamp_ns': facts.get('stamp_ns'),
            'native_application_steady_ns': facts['steady_ns']}
        break
    if applied_zero is None:
        from mecanum_nav_rl_interfaces.msg import SimulationContactState
        state = getattr(io.ingress, 'backend_state', None)
        status_received_ns = getattr(io.ingress, 'backend_received_ns', None)
        expected_faults = (SimulationContactState.FAULT_COMMAND_STALE,
            SimulationContactState.FAULT_COMMAND_SEQUENCE | SimulationContactState.FAULT_COMMAND_STALE)
        if (state is None or state.fault_flags not in expected_faults
                or not state.local_zero_override or not state.actuator_inhibited
                or type(status_received_ns) is not int
                or status_received_ns < rejected['steady_ns']):
            raise RuntimeError('R04a lacks post-rejection exact SAFE_STOP application or watchdog zero')
        applied_zero = {'mode':'watchdog_emergency_zero',
            'fault_flags':int(state.fault_flags), 'local_zero_override':True,
            'actuator_inhibited':True, 'status_received_ns':status_received_ns}
    return {'blocked_step_index':step_index,
        'input_rejection_steady_ns':rejected['steady_ns'],
        'safety_rejection_reasons':list(rejected.get('reasons', ())),
        'rejected_steady_ns':rejected['steady_ns'],
        'policy_not_accepted':True,'native_policy_receipt_absent':True,
        'b1_transition_absent':True,'native_zero_application':applied_zero}


def verify_r04c_next_step_blocked(io, *, step_index, delayed_delivery_ns):
    """Bind the next POLICY denial to a scan delivered stale at Safety."""
    rejected = next((facts for name, facts in io.events
        if name == 'SAFETY_REJECTED'
        and 'SCAN_STALE_OR_FUTURE' in facts.get('reasons', ())
        and facts.get('steady_ns', 0) >= delayed_delivery_ns), None)
    if rejected is None:
        raise RuntimeError('R04c lacks Safety rejection after delayed stale scan delivery')
    if any(name == 'SAFETY_ACCEPTED'
            and facts.get('candidate_source') == 1
            and facts.get('candidate_sequence') == step_index
            and facts.get('steady_ns', 0) >= delayed_delivery_ns
            for name, facts in io.events):
        raise RuntimeError('R04c accepted the blocked POLICY slot after stale scan delivery')
    if any(name == 'b1_transition_committed'
            and facts.get('step_index') == step_index for name, facts in io.events):
        raise RuntimeError('R04c committed the blocked POLICY slot')
    if any(getattr(receipt, 'source_sequence', None) == step_index
            and getattr(receipt, 'source', None) == 1 for receipt in io.ingress.receipts):
        raise RuntimeError('R04c POLICY receipt for the stale-scan slot reached native ingress')
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
    applied_zero = None
    for name, facts in io.events:
        if (name != 'NATIVE_APPLICATION_JOINED'
                or type(facts.get('steady_ns')) is not int
                or facts['steady_ns'] <= rejected['steady_ns']
                or facts.get('source_instance_id') != io.ingress.safe_stop_source_id
                or facts.get('step_index') != 0
                or facts.get('transition_id') != ''):
            continue
        receipt = io.final.publication_for_source_sequence(
            source=FinalIssuedCommandReceipt.SOURCE_SAFE_STOP,
            sequence=facts.get('source_sequence'))
        if (receipt is None or receipt.source != FinalIssuedCommandReceipt.SOURCE_SAFE_STOP
                or receipt.source_instance_id != io.ingress.safe_stop_source_id
                or receipt.final_publisher_instance_id != io.final.publisher_instance_id
                or receipt.final_publish_sequence != facts.get('publish_sequence')
                or receipt.sequence != facts.get('source_sequence')
                or any((receipt.final_command.linear.x, receipt.final_command.linear.y,
                        receipt.final_command.angular.z))):
            continue
        applied_zero = {'source_sequence':receipt.sequence,
            'final_publish_sequence':receipt.final_publish_sequence,
            'publisher_instance_id':receipt.final_publisher_instance_id,
            'native_iteration':facts.get('iteration'),
            'native_stamp_ns':facts.get('stamp_ns'),
            'native_application_steady_ns':facts['steady_ns']}
        break
    if applied_zero is None:
        raise RuntimeError('R04c lacks exact native SAFE_STOP application after stale rejection')
    return {'blocked_step_index':step_index,'rejected_steady_ns':rejected['steady_ns'],
        'safety_rejection_reasons':list(rejected.get('reasons', ())),
        'policy_not_accepted':True,'native_policy_receipt_absent':True,
        'b1_transition_absent':True,'native_zero_application':applied_zero}


def verify_r04c_stale_rejection_and_zero(io, *, delayed_delivery_ns,
                                         step_index=None):
    """Prove a late scan was rejected and Safety's resulting zero was applied."""
    rejected = next((facts for name, facts in io.events
        if name == 'SAFETY_REJECTED'
        and 'SCAN_STALE_OR_FUTURE' in facts.get('reasons', ())
        and facts.get('steady_ns', 0) >= delayed_delivery_ns), None)
    if rejected is None:
        return None
    if step_index is not None:
        from mecanum_nav_rl_interfaces.msg import CommandEnvelope
        if any(name == 'SAFETY_ACCEPTED'
                and facts.get('candidate_source') == CommandEnvelope.SOURCE_POLICY
                and facts.get('candidate_sequence') == step_index
                and facts.get('steady_ns', 0) >= delayed_delivery_ns
                for name, facts in io.events):
            raise RuntimeError('R04c accepted the stale-scan POLICY step after callback delivery')
        if any(name == 'NATIVE_APPLICATION_JOINED'
                and facts.get('step_index') == step_index
                and facts.get('source_sequence') == step_index
                and facts.get('steady_ns', 0) >= delayed_delivery_ns
                for name, facts in io.events):
            raise RuntimeError('R04c applied POLICY after stale-scan callback delivery')
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
    for name, facts in io.events:
        if (name != 'NATIVE_APPLICATION_JOINED'
                or type(facts.get('steady_ns')) is not int
                or facts['steady_ns'] <= rejected['steady_ns']
                or facts.get('source_instance_id') != io.ingress.safe_stop_source_id
                or facts.get('step_index') != 0
                or facts.get('transition_id') != ''):
            continue
        receipt = io.final.publication_for_source_sequence(
            source=FinalIssuedCommandReceipt.SOURCE_SAFE_STOP,
            sequence=facts.get('source_sequence'))
        if (receipt is None or receipt.source != FinalIssuedCommandReceipt.SOURCE_SAFE_STOP
                or receipt.source_instance_id != io.ingress.safe_stop_source_id
                or receipt.final_publisher_instance_id != io.final.publisher_instance_id
                or receipt.final_publish_sequence != facts.get('publish_sequence')
                or receipt.sequence != facts.get('source_sequence')
                or any((receipt.final_command.linear.x, receipt.final_command.linear.y,
                        receipt.final_command.angular.z))):
            continue
        applied_zero = {'source_sequence':receipt.sequence,
            'final_publish_sequence':receipt.final_publish_sequence,
            'publisher_instance_id':receipt.final_publisher_instance_id,
            'native_iteration':facts.get('iteration'),
            'native_stamp_ns':facts.get('stamp_ns'),
            'native_application_steady_ns':facts['steady_ns']}
        return {'case':'R04c','delayed_delivery_ns':delayed_delivery_ns,
            'stale_rejection_reasons':list(rejected.get('reasons', ())),
            'rejected_steady_ns':rejected['steady_ns'],
            'native_zero_application':applied_zero}
    return None


def verify_r04c_stale_issuance_commit_rejected(io, *, step_index, error,
                                               error_steady_ns, delayed_delivery):
    """Bind R04c's stale B1 refusal to the exact applied step and late scan.

    A delayed scan can arrive after a valid POLICY application. B1 must still
    refuse to commit when the original POLICY issuance receipt has aged past
    its existing 500 ms limit. This is distinct from a slot rejected before
    publication; callers must separately prove Safety's later stale-scan
    rejection and native zero application.
    """
    expected = 'B1 transition commit rejected: POLICY issuance receipt is stale or invalid'
    if not isinstance(error, ValueError) or str(error) != expected:
        raise RuntimeError('R04c B1 failure is not the exact stale-issuance rejection')
    facts = delayed_delivery
    if (not isinstance(facts, dict) or facts.get('case') != 'R04c'
            or type(facts.get('delivery_ns')) is not int
            or type(facts.get('source_stamp_ns')) is not int):
        raise RuntimeError('R04c delayed scan evidence is incomplete')
    issued = [row for name, row in io.events
        if name == 'policy_adapter_issued' and row.get('step_index') == step_index]
    if len(issued) != 1:
        raise RuntimeError('R04c stale commit rejection lacks one exact POLICY issuance')
    issuance = issued[0]
    issued_ns = issuance.get('steady_ns')
    transition_id = issuance.get('transition_id')
    source_id = issuance.get('source_instance_id')
    sequence = issuance.get('sequence')
    if (type(issued_ns) is not int or not transition_id
            or type(source_id) is not int or sequence != step_index):
        raise RuntimeError('R04c POLICY issuance identity/timestamp is incomplete')
    publications = [row for name, row in io.events
        if name == 'policy_final_published'
        and row.get('step_index') == step_index
        and row.get('source_sequence') == sequence
        and row.get('transition_id') == transition_id
        and row.get('source_instance_id') == source_id]
    if not publications:
        raise RuntimeError('R04c stale commit rejection lacks the exact final receipt')
    publication = min(publications, key=lambda row: row.get('steady_ns', 0))
    published_ns = publication.get('steady_ns')
    if type(published_ns) is not int or published_ns < issued_ns:
        raise RuntimeError('R04c final receipt timestamp does not follow its issuance')
    from rclpy.serialization import deserialize_message
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
    raw_hex = publication.get('receipt_cdr_hex')
    try:
        receipt = deserialize_message(bytes.fromhex(raw_hex), FinalIssuedCommandReceipt)
    except (TypeError, ValueError) as decode_error:
        raise RuntimeError('R04c final receipt bytes are missing or invalid') from decode_error
    if (receipt.source != FinalIssuedCommandReceipt.SOURCE_POLICY
            or receipt.sequence != sequence
            or receipt.source_instance_id != source_id
            or receipt.transition_id != transition_id
            or receipt.step_index != step_index):
        raise RuntimeError('R04c final receipt bytes differ from the pinned POLICY issuance')
    applications = [row for name, row in io.events
        if name == 'B1_POLICY_APPLICATION_BOUND'
        and row.get('step_index') == step_index
        and row.get('transition_id') == transition_id]
    if len(applications) != 1:
        raise RuntimeError('R04c stale commit rejection lacks one bound B1 application')
    applied_ns = applications[0].get('steady_ns')
    if (type(applied_ns) is not int or applied_ns < published_ns
            or applied_ns >= facts['delivery_ns']):
        raise RuntimeError('R04c POLICY application is not ordered before the delayed scan')
    if type(error_steady_ns) is not int or error_steady_ns <= 0:
        raise RuntimeError('R04c stale B1 rejection has no monotonic observation time')
    receipt_age_ns = error_steady_ns - published_ns
    if receipt_age_ns <= 500_000_000:
        raise RuntimeError('R04c B1 receipt rejection is not proven beyond 500 ms')
    if any(name == 'b1_transition_committed' and row.get('step_index') == step_index
            for name, row in io.events):
        raise RuntimeError('R04c B1 committed the stale-issuance step')
    return {'blocked_step_index':step_index, 'transition_id':transition_id,
        'policy_issued_ns':issued_ns, 'policy_receipt_ns':published_ns,
        'policy_receipt_age_at_rejection_ns':receipt_age_ns,
        'b1_rejection_observed_ns':error_steady_ns,
        'policy_application_ns':applied_ns, 'scan_delivery_ns':facts['delivery_ns'],
        'scan_source_stamp_ns':facts['source_stamp_ns'],
        'b1_commit_rejected':True, 'b1_transition_absent':True,
        'policy_application_preceded_delayed_scan':True}


async def await_r04c_stale_scan_zero(io, *, delayed_delivery_ns, step_index):
    """Resume the real Safety timer and require stale-scan rejection plus applied zero."""
    adapter = io.safety.local_training
    adapter.set_policy_hold(True)
    adapter.set_stream_enabled(True)
    return await io.until(lambda: verify_r04c_stale_rejection_and_zero(io,
            delayed_delivery_ns=delayed_delivery_ns, step_index=step_index),
        deadline_ns=min(io.deadline_ns, io.now() + 1_000_000_000),
        phase='R04c production stale-scan rejection and applied SAFE_STOP zero')


def require_r04c_fault_state(io, error):
    """Preserve the first failure when POLICY setup failed before hook arming."""
    state = getattr(io, '_r04_fault_state', None)
    if isinstance(state, dict) and state.get('case') == 'R04c':
        return state
    facts = {'error_type':type(error).__name__, 'error':str(error),
        'steady_ns':io.now()}
    io.emit('R04C_STEP_FAILED_BEFORE_FAULT_ARM', facts)
    raise RuntimeError('R04c POLICY step failed before its scan-delay hook was armed: '
        + type(error).__name__ + ': ' + str(error)) from error


def abort_r04a_pending_step_if_active(lifecycle, *, expected_step_index,
                                      reason='R04a_delayed_input_blocked_next_slot'):
    """Abort only an active B1 step; a pre-bind timeout has no step to abort."""
    snapshot = lifecycle.snapshot
    active = snapshot.active_transition_identity
    if active is None:
        if snapshot.step_index != expected_step_index - 1:
            raise RuntimeError('R04a no-active-step state does not follow the last committed step')
        return {'disposition':'NOT_STARTED','step_index':expected_step_index,
            'last_committed_step_index':snapshot.step_index}
    if active.step_index != expected_step_index:
        raise RuntimeError('R04a pending B1 identity differs from blocked slot')
    result = lifecycle.abort_step(reason)
    return {'disposition':'ABORTED','step_index':active.step_index,
        'abort_status':str(result.status)}


def verify_r04a_zero_baseline(io, *, checked):
    """Accept a proven applied zero even when Safety has emitted its next tick.

    SAFE_STOP publication and native status callbacks are asynchronous. The
    latest Safety output can therefore be one sequence ahead of the latest
    native status without invalidating an earlier, exactly joined zero after
    the delayed-input rejection.
    """
    from mecanum_nav_rl_interfaces.msg import CommandEnvelope
    state = io.ingress.backend_state
    stop = io.safety.local_training.last_output
    if (stop is None or stop.source != CommandEnvelope.SOURCE_SAFE_STOP
            or any((stop.twist.linear.x, stop.twist.linear.y, stop.twist.angular.z))):
        raise RuntimeError('R04a current Safety output is not zero SAFE_STOP')
    proof = checked.get('native_zero_application') if isinstance(checked, dict) else None
    if isinstance(proof, dict) and proof.get('mode') == 'watchdog_emergency_zero':
        from mecanum_nav_rl_interfaces.msg import SimulationContactState
        expected_faults = (SimulationContactState.FAULT_COMMAND_STALE,
            SimulationContactState.FAULT_COMMAND_SEQUENCE | SimulationContactState.FAULT_COMMAND_STALE)
        if (state is None or state.fault_flags not in expected_faults
                or state.fault_flags != proof.get('fault_flags')
                or not state.local_zero_override or not state.actuator_inhibited
                or io.ingress.backend_received_ns != proof.get('status_received_ns')):
            raise RuntimeError('R04a watchdog emergency-zero evidence changed after capture')
        return {'native_fault_flags':int(state.fault_flags),
            'local_zero_override':True, 'actuator_inhibited':True,
            'backend_status_received_ns':io.ingress.backend_received_ns,
            'current_safety_source':stop.source, 'current_safety_sequence':stop.sequence,
            'current_safety_zero':True, 'native_zero_mode':'watchdog_emergency_zero'}
    if (not isinstance(proof, dict) or type(proof.get('publisher_instance_id')) is not int
            or type(proof.get('final_publish_sequence')) is not int
            or proof['publisher_instance_id'] != io.final.publisher_instance_id):
        raise RuntimeError('R04a native zero proof is not bound to the FinalTwistPublisher')
    from mecanum_nav_rl_interfaces.msg import SimulationContactState
    expected_faults = (SimulationContactState.FAULT_COMMAND_STALE,
        SimulationContactState.FAULT_COMMAND_SEQUENCE | SimulationContactState.FAULT_COMMAND_STALE)
    received_ns = getattr(io.ingress, 'backend_received_ns', None)
    if (state is not None and state.fault_flags in expected_faults
            and state.local_zero_override and state.actuator_inhibited
            and type(received_ns) is int
            and type(proof.get('native_application_steady_ns')) is int
            and received_ns >= proof['native_application_steady_ns']):
        return {'current_native_publish_sequence':None,
            'current_backend_status_received_ns':received_ns,
            'native_fault_flags':int(state.fault_flags),
            'local_zero_override':True, 'actuator_inhibited':True,
            'proven_post_rejection_zero':proof,
            'current_safety_source':stop.source,
            'current_safety_sequence':stop.sequence, 'current_safety_zero':True,
            'native_zero_mode':'watchdog_emergency_zero_after_applied_receipt'}
    if (state is None or not state.applied_receipt_valid or state.local_zero_override
            or state.fault_flags != 0
            or state.applied_final_publisher_instance_id != io.final.publisher_instance_id
            or state.applied_final_publish_sequence < proof['final_publish_sequence']):
        raise RuntimeError('R04a native backend lost its healthy applied-zero baseline')
    return {'current_native_publisher_instance_id':state.applied_final_publisher_instance_id,
        'current_native_publish_sequence':state.applied_final_publish_sequence,
        'proven_post_rejection_zero':proof,
        'current_safety_source':stop.source, 'current_safety_sequence':stop.sequence,
        'current_safety_zero':True}


def verify_r02g_close(io, *, route, policy_receipt_count, zero_receipt=None,
                      backend_state=None, control_ack=None):
    """Verify a real LOCAL_TRAINING closing path after nonzero POLICY.

    SAFE_STOP and Safety admission closures require the exact native-applied
    zero receipt. OP_INHIBIT uses its applied service ACK and native zero
    override. Token-state coverage at the native gate is tested separately by
    NativeClosingAuthority's twelve production-tick regressions.
    """
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
    if route not in ('safe_stop', 'admission_inhibited', 'zero_only', 'op_inhibit'):
        raise ValueError('R02g closing route is unsupported')
    if type(policy_receipt_count) is not int or policy_receipt_count < 0:
        raise ValueError('R02g requires the pre-close POLICY receipt count')
    if route == 'op_inhibit':
        if (control_ack is None or control_ack.request.operation != Control.Request.OP_INHIBIT
                or control_ack.response.result != Control.Response.RESULT_APPLIED
                or control_ack.response.reason_code != Control.Response.REASON_NONE
                or backend_state is None or not backend_state.local_zero_override):
            raise RuntimeError('R02g OP_INHIBIT lacks APPLIED ACK/native zero override')
    else:
        if not isinstance(zero_receipt, FinalIssuedCommandReceipt):
            raise RuntimeError('R02g closing route lacks generated SAFE_STOP receipt')
        command = (zero_receipt.final_command.linear.x, zero_receipt.final_command.linear.y,
            zero_receipt.final_command.angular.z)
        if (zero_receipt.source != FinalIssuedCommandReceipt.SOURCE_SAFE_STOP or any(command)
                or backend_state is None or backend_state.fault_flags != 0
                or backend_state.local_zero_override or not backend_state.applied_receipt_valid
                or backend_state.applied_final_publisher_instance_id != zero_receipt.final_publisher_instance_id
                or backend_state.applied_final_publish_sequence != zero_receipt.final_publish_sequence):
            raise RuntimeError('R02g closing route lacks exact native-applied zero receipt')
    # The production ingress keeps receipts in a bounded deque, which does
    # not support slicing. Snapshot it under the callback lock before checking
    # the post-close suffix so the runtime path and offline fixtures agree.
    with io.ingress.lock:
        receipts_after_close = tuple(io.ingress.receipts)[policy_receipt_count:]
    if any(item.source is ReceiptSource.POLICY for item in receipts_after_close):
        raise RuntimeError('R02g observed POLICY receipt after the close trigger')
    return {'route':route, 'closing_ack_applied':route == 'op_inhibit',
        'safe_stop_receipt_applied':route != 'op_inhibit',
        'native_local_zero_override':bool(backend_state.local_zero_override)}


def r02g_inhibit_operation():
    """Resolve the production service operation used by the R02g OP_INHIBIT route."""
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    return Control.Request.OP_INHIBIT


def r02g_close_admission(io, adapter, *, zero_only):
    """Close Safety issuance before revoking native admission, then publish zero."""
    adapter.set_policy_hold(True)
    io.ingress.inhibit(zero_only=zero_only)
    adapter.set_stream_enabled(True)


def verify_r02_late_receipt_rejected(io, *, case, step_index, receipt):
    """Bind a delayed real POLICY receipt to close-before-release and native rejection."""
    from mecanum_nav_rl_interfaces.msg import SimulationContactState
    if case not in ('R02c', 'R02d'):
        raise ValueError('unsupported delayed receipt case')
    rows = [json.loads(line) for line in Path(io.descriptor['native_events_path'])
        .read_text().splitlines() if line.strip()]
    held = [row for row in rows if row.get('kind') == 'B23_POLICY_RECEIPT_HELD'
        and row.get('fields', {}).get('sequence') == str(receipt.final_publish_sequence)
        and row.get('fields', {}).get('source_sequence') == str(step_index)]
    reason = 'safe_stop' if case == 'R02c' else 'admission_inhibited'
    released = [row for row in rows if row.get('kind') == 'B23_POLICY_RECEIPT_RELEASED_AFTER_CLOSE'
        and row.get('fields', {}).get('sequence') == str(receipt.final_publish_sequence)
        and row.get('fields', {}).get('reason') == reason]
    if len(held) != 1 or len(released) != 1:
        raise RuntimeError(f'{case} lacks exact native hold/release evidence')
    held_ns = int(held[0]['fields']['receive_ns'])
    release_ns = int(released[0]['fields']['receive_ns'])
    if release_ns < held_ns:
        raise RuntimeError(f'{case} release predates native receipt hold')
    state = io.ingress.backend_state
    expected_fault_flags = (SimulationContactState.FAULT_COMMAND_SEQUENCE
        | SimulationContactState.FAULT_COMMAND_STALE)
    if (state is None or state.fault_flags != expected_fault_flags
            or not state.local_zero_override):
        raise RuntimeError(f'{case} late POLICY receipt did not produce native fault and zero')
    if (state.applied_receipt_valid and
            state.applied_final_publisher_instance_id == receipt.final_publisher_instance_id and
            state.applied_final_publish_sequence == receipt.final_publish_sequence):
        raise RuntimeError(f'{case} late POLICY receipt was applied after close')
    if any(name == 'POLICY_STEP_COMPLETE' and facts.get('step_index') == step_index
           for name, facts in io.events):
        raise RuntimeError(f'{case} created a B1 commit for the canceled POLICY step')
    return {'case':case, 'held_final_publish_sequence':receipt.final_publish_sequence,
        'held_receive_ns':held_ns, 'release_receive_ns':release_ns, 'release_reason':reason,
        'native_fault_flags':state.fault_flags, 'local_zero_override':True,
        'policy_backend_applied':False, 'b1_transition_committed':False}


async def await_r02_late_receipt_close(io, *, release_predicate, deadline_ns):
    """Wait through the observed stale-only state, then require sequence+stale zero."""
    from mecanum_nav_rl_interfaces.msg import SimulationContactState
    stale = SimulationContactState.FAULT_COMMAND_STALE
    terminal_flags = (SimulationContactState.FAULT_COMMAND_SEQUENCE | stale)
    allowed_transition = (stale, terminal_flags)
    await io.until(release_predicate, deadline_ns=deadline_ns,
        phase='held POLICY receipt released only after closing condition',
        expected_native_fault_flags=allowed_transition)
    return await io.until(lambda: io.ingress.backend_state
        if io.ingress.backend_state is not None
        and io.ingress.backend_state.fault_flags == terminal_flags
        and io.ingress.backend_state.local_zero_override else None,
        deadline_ns=deadline_ns,
        phase='native rejection and local zero after late POLICY receipt',
        expected_native_fault_flags=allowed_transition)


def verify_guard_authority(packet, authority, packet_sha256):
    """Bind a capacity-one guard to the packet's case, phase, and run."""
    expected_phase = campaign_phase(packet['case'])
    if (authority.get('packet_sha256') != packet_sha256
            or authority.get('run_id') != packet.get('run_id')
            or authority.get('capacity') != 1
            or authority.get('phase') != expected_phase
            or authority.get('consumed') is not False):
        raise RuntimeError('capacity-one authority does not match packet case/phase')
    return expected_phase


class FinalPublicationView:
    """Đọc receipt của FinalTwistPublisher process riêng; không publish actuator."""
    def __init__(self, publisher_instance_id):
        if type(publisher_instance_id) is not int or publisher_instance_id <= 0:
            raise ValueError('actual final publisher boot identity required')
        self.publisher_instance_id = publisher_instance_id
        self.ingress = None

    @property
    def last_publication(self):
        from rclpy.serialization import deserialize_message
        from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
        if self.ingress is None or not self.ingress.receipts:
            return None
        sequence = self.ingress.receipts[-1].final_publish_sequence
        return deserialize_message(self.ingress._receipt_bytes[sequence], FinalIssuedCommandReceipt)

    def publication_for_source_sequence(self, *, source, sequence):
        """Select the retained receipt for one exact Safety output identity."""
        from rclpy.serialization import deserialize_message
        from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
        from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
        if self.ingress is None or type(sequence) is not int or sequence <= 0:
            return None
        expected = {FinalIssuedCommandReceipt.SOURCE_POLICY: ReceiptSource.POLICY,
            FinalIssuedCommandReceipt.SOURCE_SAFE_STOP: ReceiptSource.SAFE_STOP}.get(source)
        if expected is None:
            return None
        for view in reversed(self.ingress.receipts):
            if (view.source is expected and view.source_sequence == sequence
                    and view.final_publisher_instance_id == self.publisher_instance_id):
                raw = self.ingress._receipt_bytes.get(view.final_publish_sequence)
                if raw is None:
                    return None
                receipt = deserialize_message(raw, FinalIssuedCommandReceipt)
                if (receipt.final_publisher_instance_id != self.publisher_instance_id
                        or receipt.source != source or receipt.sequence != sequence
                        or receipt.final_publish_sequence != view.final_publish_sequence):
                    raise RuntimeError('retained receipt bytes do not match the pinned view')
                return receipt
        return None


class TrainingWorkerIO:
    """ROS I/O của một worker sở hữu riêng context, nodes, executor và RPC."""

    def __init__(self, descriptor, document, asset_manifest, emit):
        import rclpy
        from rclpy.context import Context
        from rclpy.node import Node
        from rclpy.parameter import Parameter
        from rclpy.executors import SingleThreadedExecutor
        from rclpy.clock import JumpThreshold
        from rclpy.clock_type import ClockType
        from rclpy.duration import Duration
        from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
        from nav_msgs.msg import Odometry
        from sensor_msgs.msg import LaserScan
        from mecanum_nav_rl_interfaces.msg import (
            SafetyLifecycleState, SimulationContactState, FinalIssuedCommandReceipt, SafetyState,
            LocalTrainingSafetyInput, CommandEnvelope,
        )
        from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
        from ros_gz_interfaces.srv import ControlWorld, SetEntityPose
        from std_srvs.srv import Trigger
        from mecanum_nav_rl.runtime_safety.safety_lifecycle_node import SafetyLifecycleNode
        from mecanum_nav_rl.runtime_safety.safety_supervisor_node import (
            SafetySupervisorNode, LocalTrainingSafetyAdapter)
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import LocalTrainingIngress
        from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendSessionIdentity, BackendControlSession
        from mecanum_nav_rl.runtime_simulation.local_training_ports import LocalTrainingBackendControlPort
        import secrets
        self.descriptor, self.document, self.asset = copy.deepcopy(descriptor), document, asset_manifest
        self.events = []
        self._accepted_policy_event_keys = set()
        self._event_sink = emit
        self.emit = self._emit
        self.fault_hooks = set()
        self.now, self.pause = time.monotonic_ns, asyncio.sleep
        self.deadline_ns = descriptor['active_deadline_ns']
        self.context = Context()
        self.nodes, self.calls = [], []
        self.executor = None
        self.safety_executor = None
        self.safety_thread = None
        self.safety_executor_error = None
        self._emit_lock = threading.RLock()
        self.pump_task = None
        self.pump_error = None
        self.stop_requested = False
        self.abort_requested = None
        self.subscriptions = []
        self._hold_next_safety_input = False
        self._held_safety_input = None
        self._r04d_fault_state = None
        self._r04d_pending_ingress_lifecycle = None
        self._r06b_measurement_fault = {'active':False, 'yielded':False, 'dropped':False}
        self._r06c_hold_after_sequence = None
        self._r06c_held_receipts = []
        self._pending_future_receipts = deque()
        self._receipt_max_age_ns = int(
            document['training']['local_training']['b1_receipt_max_age_ms']) * 1_000_000
        self.expected_paused = True
        self.last_clock_ns, self.last_clock_advance_ns = 0, self.now()
        self._native_offset, self._native_partial = 0, b''
        self._native_input_watermark = 0
        self._native_safe_stop_ingress = {}
        self.contact_ack = None
        self.contact_start_request_sequence = None
        self._r07b_rollback_pending_before_ns = None
        self._r07b_rollback_observed = None
        self._r07b_request_started_ns = None
        self._r07b_replacement_backend_statuses = []
        self._r07b_cleanup_control = None
        self._r07c_restart_started_ns = None
        self._r07c_restart_clock_phase = 'idle'
        self._r07c_restart_clock_grace_deadline_ns = None
        self._r07c_clock_rollback_observed = False
        self._r07c_replacement_backend_statuses = []
        try:
            rclpy.init(context=self.context)
            self.executor = SingleThreadedExecutor(context=self.context)
            self.safety_executor = SingleThreadedExecutor(context=self.context)
            base_params = [Parameter('use_sim_time', value=True)]
            mode_params = base_params + [Parameter('navigation_mode', value='LOCAL_TRAINING')]
            self.node = Node('b23_coordinator_ingress', context=self.context, parameter_overrides=base_params)
            self.nodes.append(self.node)
            ros_clock = self.node.get_clock()
            if ros_clock.clock_type != ClockType.ROS_TIME:
                raise RuntimeError('R07b requires the worker node ROS clock')
            self._r07b_jump_handle = ros_clock.create_jump_callback(
                JumpThreshold(min_forward=None, min_backward=Duration(nanoseconds=-1),
                    on_clock_change=False), post_callback=self._on_r07b_clock_jump)
            self.policy_source_id, self.safe_stop_source_id = secrets.randbelow(2**63 - 1) + 1, secrets.randbelow(2**63 - 1) + 1
            if self.policy_source_id == self.safe_stop_source_id:
                raise RuntimeError('source nonce collision')
            self.final = FinalPublicationView(descriptor['final_publisher_instance_id'])
            self.life = SafetyLifecycleNode(context=self.context, parameter_overrides=mode_params)
            self.nodes.append(self.life)
            identity = BackendSessionIdentity(descriptor['session_id'], descriptor['config_hash'],
                descriptor['asset_manifest_sha256'], descriptor['coordinator_ingress_instance_id'], descriptor['backend_instance_id'])
            safety_context = dict(session_id=identity.session_id, config_hash=identity.config_hash,
                ingress_instance_id=identity.coordinator_ingress_instance_id, backend_instance_id=identity.backend_instance_id,
                policy_source_instance_id=self.policy_source_id, safe_stop_source_instance_id=self.safe_stop_source_id,
                profile=document['training']['local_training'], sensor=asset_manifest['sensor'],
                sim_estop_release_authorized=True)
            enable_r04_adapter_fault_dispatch(LocalTrainingSafetyAdapter)
            self.safety = SafetySupervisorNode(context=self.context, parameter_overrides=mode_params,
                local_training_context=safety_context, evidence_sink=self._emit)
            self.nodes.append(self.safety)
            self.safety_executor.add_node(self.safety)
            self.safety.local_training.set_stream_enabled(False)
            reliable = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=10,
                reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE)
            backend_qos = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=50,
                reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE)
            receipt_qos = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=1,
                reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL)
            sensor_qos = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=5,
                reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.VOLATILE)
            self.safety_publisher = self.node.create_publisher(LocalTrainingSafetyInput,
                '/mecanum/local_training/safety_input', reliable)
            self.policy_publisher = self.node.create_publisher(CommandEnvelope, '/mecanum/cmd_policy', reliable)
            self.ingress = LocalTrainingIngress(identity, document['training']['local_training'],
                final_publisher_id=self.final.publisher_instance_id, policy_source_id=self.policy_source_id,
                safe_stop_source_id=self.safe_stop_source_id, safety_publish=self._publish_safety_input,
                emit=self.emit, now_ros_ns=self.ros_now)
            self.final.ingress = self.ingress
            for message, topic, callback, qos in (
                (Odometry, '/mecanum/internal/ground_truth/odom', self.ingress.on_ground_truth, backend_qos),
                (LaserScan, '/scan', self.ingress.on_scan, sensor_qos),
                (SafetyLifecycleState, '/mecanum/safety_lifecycle_state', self.ingress.bind_lifecycle, reliable),
                (SimulationContactState, '/mecanum/local_training/backend_state', self.ingress.on_backend, backend_qos),
                (FinalIssuedCommandReceipt, '/mecanum/final_issued_command', self.ingress.on_receipt, receipt_qos),
                (SafetyState, '/mecanum/safety_state', self.ingress.on_safety_state, reliable),
            ):
                self.subscriptions.append(self.node.create_subscription(message, topic,
                    self.observed_callback(message, topic, callback), qos, raw=True))
            self.safety.local_training.state_observer = lambda state: self.ingress.register_safety_publication(
                state, source_instance_id=self.safe_stop_source_id)
            self.control = BackendControlSession(LocalTrainingBackendControlPort.from_node(self.node), identity, emit=emit)
            self.control_world_type, self.pose_type, self.trigger_type = ControlWorld, SetEntityPose, Trigger
            self.world_client = self.node.create_client(ControlWorld, '/world/b2_training_arena/control')
            self.pose_client = self.node.create_client(SetEntityPose, '/world/b2_training_arena/set_pose')
            self.reset_client = self.node.create_client(Trigger, '/mecanum/safety/request_reset')
            self.rearm_client = self.node.create_client(Trigger, '/mecanum/safety/rearm')
            for node in self.nodes:
                if node is not self.safety:
                    self.executor.add_node(node)
            self.emit('WORKER_SOURCES', {'policy_source_instance_id': self.policy_source_id,
                'safe_stop_source_instance_id': self.safe_stop_source_id,
                'final_publisher_instance_id': self.final.publisher_instance_id,
                'coordinator_ingress_instance_id': identity.coordinator_ingress_instance_id,
                'backend_instance_id': identity.backend_instance_id})
        except BaseException:
            self.close_context()
            raise

    def _emit(self, name, facts):
        lock = getattr(self, '_emit_lock', None)
        if lock is None:
            lock = self._emit_lock = threading.RLock()
        with lock:
            if name in {'FAULT_HOOK_EXTERNAL_PAUSE_AFTER_W1','RESET_POSE_MUTATION_ARMED',
                        'B1_RESET_STARTED','B1_RESET_COMMITTED','RESET_COMPLETE',
                        'SAFETY_REJECTED','SAFETY_INPUT_REJECTED','b1_transition_committed',
                        'NATIVE_APPLICATION_JOINED',
                        'B23_R04_NOISY_ODOMETRY_DROPPED',
                        'B23_R04_DELIVERY_DELAY_SCHEDULED','B23_R04_DELIVERY_DELAYED_CALLBACK',
                        'B23_R04_INGRESS_DELIVERY_SCHEDULED','B23_R04_INGRESS_DELIVERY_COMPLETED',
                        'B23_R04_FAULT_ARMED','B23_R06A_SET_POSE_TARGET_MUTATED',
                        'B23_R06B_PHYSICS_ITERATION_OMITTED','B23_R06B_FAULT_ARMED',
                        'B23_R06C_FAULT_ARMED','B23_R06C_OBSERVATION0_RECEIPT_HELD'}:
                self.events.append((name, copy.deepcopy(facts)))
            elif (name == 'SAFETY_ACCEPTED' and facts.get('candidate_source') == 1
                    and type(facts.get('candidate_sequence')) is int):
                key = (facts['candidate_source_instance_id'], facts['candidate_sequence'])
                if key not in self._accepted_policy_event_keys:
                    self._accepted_policy_event_keys.add(key)
                    self.events.append((name, copy.deepcopy(facts)))
            self._event_sink(name, facts)

    def _publish_safety_input(self, message):
        """Packet-scoped R02e transport hold for one real pre-bind producer sample."""
        if self._hold_next_safety_input:
            if self._held_safety_input is not None:
                raise RuntimeError('R02e captured more than one pre-bind Safety input')
            self._held_safety_input = copy.deepcopy(message)
            self._hold_next_safety_input = False
            self.emit('R02E_PREBIND_SAFETY_INPUT_HELD', {
                'sample_sequence': message.sample_sequence,
                'admission_token_hex': bytes(message.admission_token).hex(),
                'episode_generation': message.episode_generation,
                'reset_epoch': message.reset_epoch,
                'runtime_generation': message.runtime_generation,
                'stamp_ns': (message.header.stamp.sec * 1_000_000_000
                    + message.header.stamp.nanosec),
                'message_cdr_hex': __import__('rclpy.serialization', fromlist=['serialize_message'])
                    .serialize_message(message).hex(),
                'steady_ns': self.now()})
            return
        self.safety_publisher.publish(message)

    def observed_callback(self, message_type, topic, callback):
        """Giữ CDR do DDS trả trước decode/validator; không sửa payload nguồn."""
        from rclpy.serialization import deserialize_message
        def quarantine_r07c_restart_epoch(message, wire, received_ns):
            if getattr(self, '_r07c_restart_started_ns', None) is None:
                return False
            old_backend = (topic == '/mecanum/local_training/backend_state'
                and int(message.backend_instance_id)
                    == self.descriptor['backend_instance_id'])
            if topic not in ('/mecanum/final_issued_command', '/scan',
                    '/mecanum/internal/ground_truth/odom') and not old_backend:
                return False
            header = getattr(message, 'header', None)
            source_stamp_ns = None if header is None else (
                int(header.stamp.sec)*1_000_000_000 + int(header.stamp.nanosec))
            self.emit('B23_R07C_RESTART_EPOCH_SAMPLE_QUARANTINED', {
                'topic':topic,'reason':('old_backend_instance_after_restart_request'
                    if old_backend else 'restart_scoped_sim_epoch_unbound'),
                'source_stamp_ns':source_stamp_ns,'received_ns':received_ns,
                'restart_started_ns':self._r07c_restart_started_ns,
                'detected_ns':self.now(),'wire_sha256':hashlib.sha256(wire).hexdigest(),
                'quarantined_before_ingress_validation':True})
            return True

        def process(message, wire, received_ns):
            try:
                if quarantine_r07c_restart_epoch(message, wire, received_ns):
                    return None
                rollback_active = (
                    'time_only_rollback_after_contact_proof' in getattr(self, 'fault_hooks', ())
                    and (getattr(self, '_r07b_rollback_pending_before_ns', None) is not None
                         or getattr(self, '_r07b_rollback_observed', None) is not None))
                if rollback_active and getattr(self, 'ingress', None) is not None:
                    stale = r07b_stale_rollback_input_reason(topic, message, wire, self.ingress)
                    if stale is not None:
                        reason, source_stamp_ns, watermark_ns = stale
                        event = {
                            '/mecanum/final_issued_command':'B23_R07B_POST_ROLLBACK_RECEIPT_REJECTED',
                            '/mecanum/internal/ground_truth/odom':'B23_R07B_POST_ROLLBACK_ORACLE_REJECTED',
                            '/scan':'B23_R07B_POST_ROLLBACK_SCAN_REJECTED',
                        }[topic]
                        self.emit(event, {
                            'reason':reason,'source_stamp_ns':source_stamp_ns,
                            'pinned_high_watermark_ns':watermark_ns,
                            'wire_sha256':hashlib.sha256(wire).hexdigest(),
                            'quarantined_before_ingress_validation':True,
                            'detected_ns':self.now()})
                        return None
                if (topic == '/mecanum/local_training/backend_state'
                        and 'time_only_rollback_after_contact_proof' in getattr(self, 'fault_hooks', ())
                        and self._r07b_rollback_observed is not None
                        and int(message.backend_instance_id) != self.descriptor['backend_instance_id']):
                    status = {
                        'backend_instance_id':int(message.backend_instance_id),
                        'session_id':str(message.session_id),
                        'config_hash':str(message.config_hash),
                        'status_sequence':int(message.status_sequence),
                        'physics_iteration':int(message.physics_iteration),
                        'stamp_ns':(int(message.header.stamp.sec)*1_000_000_000
                            + int(message.header.stamp.nanosec)),
                        'fault_flags':int(message.fault_flags),
                        'local_zero_override':bool(message.local_zero_override),
                        'actuator_inhibited':bool(message.actuator_inhibited),
                        'received_ns':self.now(),
                        'wire_sha256':hashlib.sha256(wire).hexdigest(),
                    }
                    self._r07b_replacement_backend_statuses.append(status)
                    self.emit('B23_R07B_REPLACEMENT_BACKEND_STATUS', status)
                    # Giữ consumer cũ pin đúng identity. Status instance mới
                    # được lưu raw/typed để nhánh restart kiểm tra riêng; không
                    # đưa nó vào session/ingress đã bị invalidation.
                    return message
                if (topic == '/mecanum/local_training/backend_state'
                        and self._r07c_restart_started_ns is not None
                        and int(message.backend_instance_id) != self.descriptor['backend_instance_id']):
                    status = {'backend_instance_id':int(message.backend_instance_id),
                        'session_id':str(message.session_id), 'config_hash':str(message.config_hash),
                        'status_sequence':int(message.status_sequence),
                        'physics_iteration':int(message.physics_iteration),
                        'stamp_ns':int(message.header.stamp.sec)*1_000_000_000
                            +int(message.header.stamp.nanosec),
                        'fault_flags':int(message.fault_flags),
                        'local_zero_override':bool(message.local_zero_override),
                        'actuator_inhibited':bool(message.actuator_inhibited),
                        'received_ns':self.now(), 'wire_sha256':hashlib.sha256(wire).hexdigest(),
                        'wire_cdr_hex':wire.hex()}
                    self._r07c_replacement_backend_statuses.append(status)
                    self.emit('B23_R07C_REPLACEMENT_BACKEND_STATUS', status)
                    return message
                if (topic == '/mecanum/final_issued_command'
                        and 'hold_observation0_adjacent_receipt_until_reset_deadline' in getattr(self, 'fault_hooks', ())
                        and self._r06c_hold_after_sequence is not None
                        and int(message.source) == message.SOURCE_SAFE_STOP
                        and int(message.final_publish_sequence) > self._r06c_hold_after_sequence):
                    # Keep the actual ingress/application join alive, but hide
                    # post-anchor receipts from B1's reset-cutoff selector.
                    # Returning before ingress.on_receipt() also withholds the
                    # join key from native application observations and fills
                    # its bounded unresolved-application queue long before the
                    # reset deadline; that tests observer overflow, not the
                    # missing B1 cutoff receipt.
                    receipt_view = callback(message, received_ns=received_ns)
                    sequence = int(message.final_publish_sequence)
                    with self.ingress.lock:
                        if (not self.ingress.receipts
                                or self.ingress.receipts[-1] is not receipt_view
                                or receipt_view.final_publish_sequence != sequence):
                            raise RuntimeError('R06c could not isolate the actual receipt from B1 cutoff selection')
                        self.ingress.receipts.pop()
                    record = {'case':'R06c',
                        'final_publish_sequence':int(message.final_publish_sequence),
                        'header_stamp_ns':int(message.header.stamp.sec)*1_000_000_000 + int(message.header.stamp.nanosec),
                        'wire_cdr_hex':wire.hex(), 'wire_sha256':hashlib.sha256(wire).hexdigest(),
                        'withheld_from_b1_ns':self.now(), 'hold_after_sequence':self._r06c_hold_after_sequence,
                        'reset_deadline_ns':self._r06c_reset_deadline_ns}
                    self._r06c_held_receipts.append(record)
                    self.emit('B23_R06C_OBSERVATION0_RECEIPT_WITHHELD_FROM_B1', record)
                    return receipt_view
                # R04d delays lifecycle delivery to both consumers. Delaying
                # Safety alone lets ingress advance first and rejects the old
                # SAFE_STOP identity before the stale lifecycle is measured.
                pending_ingress = getattr(self, '_r04d_pending_ingress_lifecycle', None)
                if (topic == '/mecanum/safety_lifecycle_state'
                        and self._r04d_fault_state is not None
                        and pending_ingress is not None
                        and int(message.sequence) >= int(pending_ingress[2].sequence)):
                    state = self._r04d_fault_state
                    state['ingress_repeats_held'] = state.get('ingress_repeats_held', 0) + 1
                    self.emit('B23_R04_INGRESS_LIFECYCLE_REPEAT_HELD', {
                        'case':'R04d','sequence':int(message.sequence),
                        'target_sequence':int(pending_ingress[2].sequence),
                        'received_ns':self.now(),
                        'held_count':state['ingress_repeats_held']})
                    return None
                if (topic == '/mecanum/safety_lifecycle_state'
                        and self._r04d_fault_state is not None
                        and self._r04d_pending_ingress_lifecycle is None
                        and not self._r04d_fault_state.get('ingress_scheduled')):
                    state = self._r04d_fault_state
                    state['ingress_scheduled'] = True
                    delay_s = r04d_ingress_lifecycle_delay_s(state['delay_s'])
                    due_ns = self.now() + int(delay_s * 1_000_000_000)
                    source_stamp_ns = (message.header.stamp.sec * 1_000_000_000
                        + message.header.stamp.nanosec)
                    self._r04d_pending_ingress_lifecycle = (
                        due_ns, callback, copy.deepcopy(message), source_stamp_ns)
                    self.emit('B23_R04_INGRESS_DELIVERY_SCHEDULED', {
                        'case':'R04d','delay_s':delay_s,
                        'source_stamp_ns':source_stamp_ns,
                        'received_ns':self.now(),'due_ns':due_ns})
                    return None
                if topic == '/mecanum/final_issued_command':
                    return callback(message, received_ns=received_ns)
                return callback(message)
            except BaseException as error:
                self.emit('INGRESS_CALLBACK_ERROR', {'topic':topic,'error':repr(error),
                    'wire_sha256':hashlib.sha256(wire).hexdigest(),'detected_ns':self.now()})
                raise

        def receive(raw, info):
            if not isinstance(raw,(bytes,bytearray,memoryview)):
                raise TypeError('raw subscription did not return serialized bytes')
            wire=bytes(raw)
            received_ns = self.now()
            self.emit('INGRESS_WIRE_RECEIVED', {'topic':topic,
                'received_ns':received_ns, 'wire_cdr_hex':wire.hex(),
                'message_info':{key:value for key,value in info.items() if type(value) is int}})
            try:
                message = deserialize_message(wire,message_type)
                if quarantine_r07c_restart_epoch(message, wire, received_ns):
                    return None
                rollback_active = (
                    'time_only_rollback_after_contact_proof' in getattr(self, 'fault_hooks', ())
                    and (getattr(self, '_r07b_rollback_pending_before_ns', None) is not None
                         or getattr(self, '_r07b_rollback_observed', None) is not None))
                if rollback_active and getattr(self, 'ingress', None) is not None:
                    stale = r07b_stale_rollback_input_reason(topic, message, wire, self.ingress)
                    if stale is not None:
                        reason, source_stamp_ns, watermark_ns = stale
                        event = {
                            '/mecanum/final_issued_command':'B23_R07B_POST_ROLLBACK_RECEIPT_REJECTED',
                            '/mecanum/internal/ground_truth/odom':'B23_R07B_POST_ROLLBACK_ORACLE_REJECTED',
                            '/scan':'B23_R07B_POST_ROLLBACK_SCAN_REJECTED',
                        }[topic]
                        self.emit(event, {
                            'reason':reason,'source_stamp_ns':source_stamp_ns,
                            'pinned_high_watermark_ns':watermark_ns,
                            'wire_sha256':hashlib.sha256(wire).hexdigest(),
                            'quarantined_before_ingress_validation':True,
                            'detected_ns':self.now()})
                        return None
                if topic == '/mecanum/final_issued_command':
                    source_stamp_ns = (int(message.header.stamp.sec) * 1_000_000_000
                        + int(message.header.stamp.nanosec))
                    ros_now_ns = self.ros_now()
                    # Once a receipt is waiting for its source ROS timestamp,
                    # keep every later receipt behind it even if the ROS clock
                    # has caught up by the time that callback is dispatched.
                    # Otherwise a newer zero receipt can advance ingress state
                    # before the older deferred receipt, turning a normal
                    # clock-catch-up race into a false sequence regression.
                    pending_receipts = getattr(self, '_pending_future_receipts', None)
                    queue_behind_pending = bool(pending_receipts)
                    if source_stamp_ns > ros_now_ns or queue_behind_pending:
                        if received_ns > self.now():
                            raise ValueError('receipt receive timestamp moved backward')
                        if pending_receipts is None:
                            raise RuntimeError('receipt deferral queue is unavailable')
                        if len(pending_receipts) >= 128:
                            raise ValueError('future receipt deferral queue capacity exceeded')
                        pending_receipts.append(
                            (source_stamp_ns, received_ns, process, message, wire))
                        self.emit('RECEIPT_CLOCK_CATCHUP_DEFERRED', {
                            'source_stamp_ns':source_stamp_ns, 'observed_ros_now_ns':ros_now_ns,
                            'received_steady_ns':received_ns, 'deferred_steady_ns':self.now(),
                            'wire_sha256':hashlib.sha256(wire).hexdigest(),
                            'reason':('behind_prior_future_receipt' if queue_behind_pending
                                and source_stamp_ns <= ros_now_ns else 'source_stamp_in_future'),
                            'queue_size':len(pending_receipts),
                            'max_original_receive_age_ns':self._receipt_max_age_ns})
                        return None
            except BaseException as error:
                self.emit('INGRESS_CALLBACK_ERROR', {'topic':topic,'error':repr(error),
                    'wire_sha256':hashlib.sha256(wire).hexdigest(),'detected_ns':self.now()})
                raise
            return process(message, wire, received_ns)
        return receive

    def _deliver_future_receipts_after_clock(self):
        """Process only after the owned ROS clock catches up, retaining DDS receive age."""
        while self._pending_future_receipts:
            source_stamp_ns, received_ns, process, message, wire = self._pending_future_receipts[0]
            now_ns = self.now()
            ros_now_ns = self.ros_now()
            if type(now_ns) is not int or now_ns < received_ns:
                raise RuntimeError('steady clock invalid while receipt waits for ROS clock')
            age_ns = now_ns - received_ns
            if age_ns > self._receipt_max_age_ns:
                self.emit('RECEIPT_CLOCK_CATCHUP_EXPIRED', {
                    'source_stamp_ns':source_stamp_ns, 'ros_now_ns':ros_now_ns,
                    'received_steady_ns':received_ns, 'checked_steady_ns':now_ns,
                    'original_receive_age_ns':age_ns,
                    'max_original_receive_age_ns':self._receipt_max_age_ns,
                    'wire_sha256':hashlib.sha256(wire).hexdigest()})
                raise TimeoutError('receipt clock catch-up exceeded original B1 receipt freshness age')
            if source_stamp_ns > ros_now_ns:
                return
            self._pending_future_receipts.popleft()
            process(message, wire, received_ns)

    def ros_now(self):
        return self.node.get_clock().now().nanoseconds

    def _on_r07b_clock_jump(self, jump):
        """Capture the actual ROS clock jump even if time advances past its baseline."""
        delta_ns = int(jump.delta.nanoseconds)
        if (delta_ns >= 0 or self._r07b_rollback_pending_before_ns is None
                or self._r07b_rollback_observed is not None):
            return
        self._r07b_rollback_observed = {
            'request_baseline_ns': self._r07b_rollback_pending_before_ns,
            'request_started_ns': self._r07b_request_started_ns,
            'delta_ns': delta_ns,
            'observed_steady_ns': self.now(),
        }

    def start_pump(self):
        if self.pump_task is not None:
            raise RuntimeError('executor pump already started')
        if self.safety_executor is None:
            raise RuntimeError('LOCAL_TRAINING Safety executor is unavailable')
        if self.safety_thread is not None:
            raise RuntimeError('LOCAL_TRAINING Safety executor thread already started')
        self.safety_thread = threading.Thread(
            target=self._spin_safety_executor,
            name='b23-safety-steady-executor',
            daemon=False,
        )
        self.safety_thread.start()
        self.pump_task = asyncio.create_task(self._pump(), name='b23-owned-ros-pump')

    def _spin_safety_executor(self):
        try:
            self.safety_executor.spin()
            if not self.stop_requested:
                raise RuntimeError('LOCAL_TRAINING Safety executor stopped unexpectedly')
        except BaseException as error:
            self.safety_executor_error = error
            self.abort_requested = 'SAFETY_EXECUTOR_FAILED'
            try:
                self.emit('SAFETY_EXECUTOR_FAILED', {'error': repr(error), 'steady_ns': self.now()})
            except BaseException:
                pass

    async def _pump(self):
        try:
            while not self.stop_requested:
                if self.safety_executor_error is not None:
                    raise RuntimeError('LOCAL_TRAINING Safety executor failed') from self.safety_executor_error
                for _ in range(16):
                    self.executor.spin_once(timeout_sec=0.)
                self._deliver_future_receipts_after_clock()
                self._deliver_r04d_ingress_lifecycle_if_due()
                await self.pause(0.001)
        except asyncio.CancelledError:
            raise
        except BaseException as error:
            self.pump_error = error
            raise

    def _deliver_r04d_ingress_lifecycle_if_due(self):
        pending = self._r04d_pending_ingress_lifecycle
        if pending is None or self.now() < pending[0]:
            return
        self._r04d_pending_ingress_lifecycle = None
        due_ns, callback, message, source_stamp_ns = pending
        delivered_ns = self.now()
        callback(message)
        self.emit('B23_R04_INGRESS_DELIVERY_COMPLETED', {
            'case':'R04d','source_stamp_ns':source_stamp_ns,
            'due_ns':due_ns,'delivery_ns':delivered_ns})

    def check(self, *, expected_native_fault_flags=None):
        if self.stop_requested or self.abort_requested is not None:
            raise RuntimeError('worker stop requested: ' + str(self.abort_requested))
        if self.pump_error is not None:
            raise RuntimeError('executor callback failed') from self.pump_error
        now, ros = self.now(), self.ros_now()
        restart_clock_phase = getattr(self, '_r07c_restart_clock_phase', 'idle')
        if now >= self.deadline_ns:
            raise TimeoutError('B23 active deadline reached')
        if ros < self.last_clock_ns:
            if (restart_clock_phase in ('restart_in_progress','awaiting_clock')
                    and getattr(self, '_r07c_restart_started_ns', None) is not None):
                if getattr(self, '_r07c_clock_rollback_observed', False):
                    raise RuntimeError('R07c observed more than one simulation clock rollback')
                self._r07c_clock_rollback_observed = True
                self.emit('B23_R07C_AUTHORIZED_CLOCK_EPOCH_RESET', {
                    'previous_ros_ns':self.last_clock_ns,'current_ros_ns':ros,
                    'restart_started_ns':self._r07c_restart_started_ns,
                    'observed_steady_ns':now})
            else:
                rollback = self._r07b_rollback_observed
                if (self._r07b_rollback_pending_before_ns is None or rollback is None
                        or rollback.get('delta_ns', 0) >= 0
                        or rollback.get('request_started_ns') is None
                        or rollback.get('observed_steady_ns', 0) < rollback['request_started_ns']):
                    raise RuntimeError('ROS clock rolled backward')
                self.emit('B23_R07B_AUTHORIZED_CLOCK_ROLLBACK_SAMPLE', {
                    'previous_ros_ns':self.last_clock_ns, 'current_ros_ns':ros,
                    'request_baseline_ns':self._r07b_rollback_pending_before_ns,
                    'request_started_ns':rollback['request_started_ns'],
                    'observed_steady_ns':now,
                })
            self.last_clock_ns, self.last_clock_advance_ns = ros, now
        if ros > self.last_clock_ns:
            self.last_clock_ns, self.last_clock_advance_ns = ros, now
            if restart_clock_phase == 'awaiting_clock':
                self._r07c_restart_clock_phase = 'idle'
                self._r07c_restart_clock_grace_deadline_ns = None
                self.emit('B23_R07C_SIM_CLOCK_RESUMED_AFTER_BACKEND_RESTART', {
                    'restart_started_ns':self._r07c_restart_started_ns,
                    'clock_resumed_ns':now,'ros_time_ns':ros})
        restart_clock_expected = (
            restart_clock_phase == 'restart_in_progress'
            or (restart_clock_phase == 'awaiting_clock'
                and getattr(self, '_r07c_restart_clock_grace_deadline_ns', None) is not None
                and now < self._r07c_restart_clock_grace_deadline_ns)
        )
        if (not self.expected_paused and not restart_clock_expected
                and now - self.last_clock_advance_ns > 1_000_000_000):
            raise RuntimeError('unexpected clock stall exceeded 1 s')
        if self.ingress.fault:
            raise RuntimeError('ingress fault: ' + self.ingress.fault)
        if self.ingress.backend_state is not None and self.ingress.backend_state.fault_flags:
            state = self.ingress.backend_state
            # The expected native fault and its zero override may arrive in
            # adjacent status publications. While polling for the closed
            # state, tolerate only the exact packet-pinned fault code; the
            # caller's terminal predicate still requires local_zero_override.
            expected_flags = (expected_native_fault_flags
                if isinstance(expected_native_fault_flags, (tuple, list, set, frozenset))
                else (expected_native_fault_flags,))
            if state.fault_flags not in expected_flags:
                raise RuntimeError('native fault flags=' + str(state.fault_flags))

    async def until(self, predicate, *, deadline_ns, phase, expected_native_fault_flags=None):
        deadline_ns = min(deadline_ns, self.deadline_ns)
        while self.now() < deadline_ns:
            self.check(expected_native_fault_flags=expected_native_fault_flags)
            value = predicate()
            if value:
                if self.now() >= deadline_ns:
                    raise TimeoutError(phase + ': observation completed late')
                return value
            before = self.now()
            duration = min(0.002, max(0., (deadline_ns - before) / 1e9))
            if duration > 0:
                await self.pause(duration)
                if self.now() <= before:
                    raise RuntimeError('worker pause did not advance monotonic clock')
        raise TimeoutError(phase + ': deadline expired')

    async def wait_backend_control_ready(self, control, *, timeout_ns, phase):
        """Wait for the backend service endpoint before sending a bounded RPC."""
        port = getattr(control, '_port', None)
        client = getattr(port, '_client', None)
        ready = getattr(client, 'service_is_ready', None)
        if not callable(ready):
            raise RuntimeError('backend control client readiness API unavailable')
        if type(timeout_ns) is not int or timeout_ns <= 0:
            raise ValueError('backend control readiness budget must be positive')
        deadline = min(self.deadline_ns, self.now() + timeout_ns)
        await self.until(ready, deadline_ns=deadline, phase=phase)
        self.emit('BACKEND_CONTROL_SERVICE_READY', {'phase':phase,'steady_ns':self.now()})
        return self.now()

    async def wait_r02e_native_admission(self, *, held_sample_sequence,
            fresh_sample_sequence, pending_token, deadline_ns):
        """Wait within the active step budget for the native event-pipe record."""
        path = self.descriptor['native_events_path']
        return await self.until(lambda: verify_r02e_prebind_admission_rejected(
                complete_jsonl_rows(path), held_sample_sequence=held_sample_sequence,
                fresh_sample_sequence=fresh_sample_sequence, pending_token=pending_token,
                session_id=self.descriptor['session_id'],
                backend_instance_id=self.descriptor['backend_instance_id'],
                ingress_instance_id=self.descriptor['coordinator_ingress_instance_id'],
                allow_pending=True),
            deadline_ns=deadline_ns, phase='R02e native pre-bind rejection and fresh acceptance')

    async def release_r02e_prebind_input_before_admission(self, *, held_sample,
            ack, deadline_ns):
        """Enqueue the old-token sample at native before allowing fresh samples."""
        held_sequence = held_sample.sample_sequence
        self.safety_publisher.publish(held_sample)
        self.emit('R02E_PREBIND_SAFETY_INPUT_RELEASED_AFTER_BIND', {
            'sample_sequence': held_sequence,
            'prior_token_hex': bytes(held_sample.admission_token).hex(),
            'new_token_hex': bytes(ack.response.pending_admission_token).hex(),
            'request_sequence': ack.request.request_sequence,
            'binding_revision': ack.response.applied_binding_revision,
            'steady_ns': self.now()})
        if bytes(held_sample.admission_token) == bytes(ack.response.pending_admission_token):
            raise RuntimeError('R02e test sample unexpectedly has the current slot token')
        native_row = await self.wait_r02e_native_input_enqueued(
            sample_sequence=held_sequence, deadline_ns=deadline_ns)
        self.ingress.resume_admission_publication()
        self.emit('R02E_PREBIND_ENQUEUED_BEFORE_FRESH_PUBLICATION', {
            'sample_sequence': held_sequence,
            'native_receive_ns': int(native_row['fields']['receive_ns']),
            'steady_ns': self.now()})
        return native_row

    async def wait_r02e_native_input_enqueued(self, *, sample_sequence, deadline_ns):
        path = self.descriptor['native_events_path']
        return await self.until(lambda: verify_r02e_safety_input_enqueued(
                complete_jsonl_rows(path), sample_sequence=sample_sequence,
                session_id=self.descriptor['session_id'],
                backend_instance_id=self.descriptor['backend_instance_id'],
                ingress_instance_id=self.descriptor['coordinator_ingress_instance_id'],
                allow_pending=True),
            deadline_ns=deadline_ns,
            phase='R02e exact pre-bind SafetyInput reaches native callback queue')

    async def wait_r02a_native_admission(self, *, sample_sequence, step_started_ns,
                                         deadline_ns):
        """Keep final output closed until this step's native admission is accepted."""
        path = self.descriptor['native_events_path']
        return await self.until(lambda: r02a_native_admission_row(
                complete_jsonl_rows(path), sample_sequence=sample_sequence,
                session_id=self.descriptor['session_id'],
                backend_instance_id=self.descriptor['backend_instance_id'],
                ingress_instance_id=self.descriptor['coordinator_ingress_instance_id'],
                step_started_ns=step_started_ns),
            deadline_ns=deadline_ns,
            phase='R02a native admission accepted before POLICY receipt')

    async def call(self, client, request, *, timeout_s, phase,
            expected_native_fault_flags=None, before_submit=None):
        from rclpy.serialization import serialize_message
        started = self.now()
        deadline = min(self.deadline_ns, started + int(timeout_s * 1e9))
        await self.until(client.service_is_ready, deadline_ns=deadline,
            phase=phase + ' service ready',
            expected_native_fault_flags=expected_native_fault_flags)
        if self.now() >= deadline:
            raise TimeoutError(phase + ': no remaining submit budget')
        self.emit('RPC_REQUEST', {'phase': phase, 'request_cdr_hex': serialize_message(request).hex(),
            'started_ns': started, 'deadline_ns': deadline})
        if before_submit is not None:
            before_submit(self.now())
        future = client.call_async(request)
        self.calls.append(future)
        try:
            await self.until(future.done, deadline_ns=deadline, phase=phase + ' ACK',
                expected_native_fault_flags=expected_native_fault_flags)
            response = future.result()
            self.emit('RPC_RESPONSE', {'phase': phase, 'response_cdr_hex': serialize_message(response).hex(),
                'received_ns': self.now(), 'deadline_ns': deadline})
            if self.now() >= deadline or type(response.success) is not bool or not response.success:
                raise RuntimeError(phase + ': late/negative actual ACK')
            return response
        finally:
            if not future.done():
                future.cancel()
            if future.done():
                self.calls.remove(future)

    async def control_world(self, *, world_name, pause, timeout_s,
            expected_native_fault_flags=None):
        from rclpy.serialization import serialize_message
        if world_name != 'b2_training_arena' or type(pause) is not bool:
            raise ValueError('world control target invalid')
        request = self.control_world_type.Request()
        request.world_control.pause = pause
        call_args = {'timeout_s':timeout_s,
            'phase':'world_pause' if pause else 'world_resume'}
        if expected_native_fault_flags is not None:
            call_args['expected_native_fault_flags'] = expected_native_fault_flags
        response = await self.call(self.world_client, request, **call_args)
        self.emit('WORLD_PAUSE_CONTROL', {'world':world_name,'requested_pause':pause,
            'request_cdr_hex':serialize_message(request).hex(),
            'response_success':response.success,
            'steady_ns':self.now()})
        # ResetAdapter's GazeboResetServices contract is bool. The generated
        # Jazzy ControlWorld response itself is only an ACK with `success`;
        # observed pause state is checked separately from native status.
        return response.success

    async def request_owned_restart(self, *, case, target_role):
        """Ask the parent to restart one process already owned by this run."""
        if case == 'R07c' and target_role == 'server':
            identity = dict(self.descriptor['server_identity'])
            if identity.get('pid') != self.descriptor.get('server_leader_pid'):
                raise RuntimeError('R07c server identity is not the descriptor-pinned process')
        elif case == 'R07d' and target_role == 'final':
            identity = process_identity(int(self.descriptor['final_publisher_pid']))
            if identity.get('pid') != self.descriptor['final_publisher_pid']:
                raise RuntimeError('R07d final identity is not the descriptor-pinned process')
        else:
            raise ValueError('owned restart operation does not match R07 case')
        request = {'schema':'b23_owned_restart_request/v1',
            'run_id':self.descriptor['run_id'],
            'invocation_id':self.descriptor['invocation_id'],
            'case':case,'operation':'restart_owned_process','target_role':target_role,
            'identity':identity,
            'old_backend_instance_id':int(self.descriptor['backend_instance_id'])
                if case == 'R07c' else None,
            'old_publisher_instance_id':int(self.descriptor['final_publisher_instance_id'])
                if case == 'R07d' else None,
            'requested_ns':self.now()}
        request_path = Path(self.descriptor['owned_restart_request_path'])
        response_path = Path(self.descriptor['owned_restart_response_path'])
        if case == 'R07c':
            self._r07c_restart_started_ns = self.now()
            self._r07c_restart_clock_phase = 'restart_in_progress'
            self._r07c_clock_rollback_observed = False
        write_record_once(request_path, request)
        request_hash = hashlib.sha256(request_path.read_bytes()).hexdigest()
        self.emit('B23_OWNED_PROCESS_RESTART_REQUESTED', {
            'case':case,'target_role':target_role,'identity':identity,
            'request_sha256':request_hash,'steady_ns':self.now()})
        def response_ready():
            if not response_path.exists():
                return None
            response = json.loads(response_path.read_bytes())
            old_process = response.get('old_process')
            old_identity = (old_process.get('identity')
                if isinstance(old_process, dict) else None)
            identity_fields = ('pid', 'uid', 'start_ticks', 'argv', 'pgid', 'sid')
            old_process_matches = (
                isinstance(old_process, dict)
                and isinstance(old_identity, dict)
                and old_process.get('pid') == identity.get('pid')
                and type(old_process.get('exit_status')) is int
                and old_process.get('group_absent') is True
                and all(old_identity.get(field) == identity.get(field)
                        for field in identity_fields)
            )
            if (response.get('schema') != 'b23_owned_restart_response/v1'
                    or response.get('run_id') != self.descriptor['run_id']
                    or response.get('invocation_id') != self.descriptor['invocation_id']
                    or response.get('case') != case
                    or response.get('target_role') != target_role
                    or response.get('request_sha256') != request_hash
                    or not old_process_matches):
                raise RuntimeError('owned restart response binding mismatch')
            return response
        expected_native_fault_flags = None
        if case == 'R07d':
            # Stopping the final publisher intentionally removes receipts; the
            # unchanged native watchdog latches stale. Receipt-gate invalidation
            # can additionally latch sequence fault; accept only these two
            # exact fail-closed states while collecting the owned restart ACK.
            expected_native_fault_flags = r07d_restart_fault_flags()
        until_args = {'deadline_ns':self.deadline_ns,
            'phase':case + ' owned process restart ACK'}
        if expected_native_fault_flags is not None:
            until_args['expected_native_fault_flags'] = expected_native_fault_flags
        response = await self.until(response_ready, **until_args)
        if case == 'R07c':
            self._r07c_restart_clock_phase = 'awaiting_clock'
            self._r07c_restart_clock_grace_deadline_ns = min(
                self.deadline_ns, self.now() + 1_000_000_000)
            self.emit('B23_R07C_REPLACEMENT_READY_WAITING_FOR_CLOCK', {
                'restart_started_ns':self._r07c_restart_started_ns,
                'replacement_ready_ns':self.now(),
                'clock_resume_deadline_ns':self._r07c_restart_clock_grace_deadline_ns})
        self.emit('B23_OWNED_PROCESS_RESTART_ACKNOWLEDGED', response)
        return response

    async def reset_world_time_only(self, *, timeout_s):
        """Apply the packet-pinned Gazebo time_only rollback through ControlWorld."""
        from rclpy.serialization import serialize_message
        before = self.ros_now()
        if before <= 0:
            raise RuntimeError('R07b requires positive simulation time before rollback')
        request = self.control_world_type.Request()
        request.world_control.reset.time_only = True
        request.world_control.reset.all = False
        request.world_control.reset.model_only = False
        request.world_control.pause = False
        if 'time_only_rollback_after_contact_proof' not in self.fault_hooks:
            raise RuntimeError('R07b time_only reset is not authorized by this packet hook')
        def arm_rollback_observer(request_started_ns):
            self._r07b_request_started_ns = request_started_ns
            self._r07b_rollback_pending_before_ns = before
        self._r07b_rollback_observed = None
        response = await self.call(self.world_client, request, timeout_s=timeout_s,
            phase='R07b_world_time_only_rollback', before_submit=arm_rollback_observer)
        after = self.ros_now()
        rollback = await self.until(lambda: self._r07b_rollback_observed,
            deadline_ns=min(self.deadline_ns, self.now() + 1_000_000_000),
            phase='R07b ROS clock rollback event')
        self.emit('B23_R07B_CLOCK_ROLLBACK_OBSERVED', rollback)
        self.emit('B23_R07B_TIME_ONLY_RESET', {
            'world':'b2_training_arena','pause':False,'reset_all':False,
            'reset_time_only':True,'reset_model_only':False,
            'request_cdr_hex':serialize_message(request).hex(),
            'response_success':response.success,
            'sim_before_ns':before,'sim_after_ack_ns':after,
            'clock_jump':rollback,'steady_ns':self.now()})
        if not response.success:
            raise RuntimeError('R07b world time_only API returned unsuccessful ACK')
        if (type(rollback.get('request_started_ns')) is not int
                or rollback['observed_steady_ns'] < rollback['request_started_ns']
                or rollback['delta_ns'] >= 0):
            raise RuntimeError('R07b clock rollback was not observed during the requested reset')
        self.last_clock_ns, self.last_clock_advance_ns = after, self.now()
        return before, after, rollback

    async def set_entity_pose(self, *, world_name, entity_name, target, timeout_s):
        from ros_gz_interfaces.msg import Entity
        if world_name != 'b2_training_arena' or entity_name != 'mecanum_b2':
            raise ValueError('only bound robot reset pose is allowed')
        request = self.pose_type.Request()
        request.entity.name, request.entity.type = entity_name, Entity.MODEL
        request.pose.position.x, request.pose.position.y, request.pose.position.z = target.x_m, target.y_m, target.z_m
        request.pose.orientation.w, request.pose.orientation.z = math.cos(target.yaw_rad / 2), math.sin(target.yaw_rad / 2)
        if not hasattr(self, 'pause_ack'):
            raise RuntimeError('robot pose request has no actual native pause ACK')
        self.ingress.begin_pose_mutation(self.pause_ack)
        await self.call(self.pose_client, request, timeout_s=timeout_s, phase='robot_set_pose')
        return True

    async def set_r09b_task_fixture_pose(self, *, pose_name, deadline_ns, zero_receipt=None):
        """Move only the pinned R09b world obstacle while actual robot zero is bound."""
        from rclpy.serialization import serialize_message
        from ros_gz_interfaces.msg import Entity
        from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
        fixture = validate_r09b_task_fixture(self.descriptor.get('task_fixture'))
        if pose_name not in ('contact_pose', 'initial_pose'):
            raise ValueError('R09b fixture pose must be the packet contact or restore pose')
        pose = fixture[pose_name]
        if zero_receipt is None:
            def current_applied_zero():
                from mecanum_nav_rl.runtime_simulation.local_training_ingress import lifecycle_identity
                receipt = self.final.last_publication
                latest = self.ingress.backend_state
                if (receipt is None or latest is None
                        or receipt.source != FinalIssuedCommandReceipt.SOURCE_SAFE_STOP
                        or receipt.final_publisher_instance_id != self.final.publisher_instance_id
                        or any((receipt.final_command.linear.x, receipt.final_command.linear.y,
                            receipt.final_command.angular.z))
                        or latest.backend_instance_id != self.descriptor['backend_instance_id']
                        or latest.session_id != self.descriptor['session_id']
                        or latest.config_hash != self.descriptor['config_hash']
                        or latest.fault_flags or latest.paused or latest.local_zero_override
                        or not latest.applied_receipt_valid
                        or latest.applied_final_publisher_instance_id != receipt.final_publisher_instance_id
                        or latest.applied_final_publish_sequence != receipt.final_publish_sequence
                        or not latest.coverage_complete or not latest.contact_source_healthy
                        or latest.required_collision_mask == 0
                        or latest.required_collision_mask != latest.observed_collision_mask):
                    return None
                application = self.ingress.application_for_receipt(receipt)
                if application is None:
                    return None
                applied = application.get('state')
                received_ns = application.get('received_ns')
                age_ns = self.now() - received_ns if type(received_ns) is int else None
                if (applied is None or type(age_ns) is not int or not 0 <= age_ns <= 500_000_000
                        or applied.fault_flags or applied.paused or applied.local_zero_override
                        or not applied.applied_receipt_valid
                        or applied.backend_instance_id != self.descriptor['backend_instance_id']
                        or applied.session_id != self.descriptor['session_id']
                        or applied.config_hash != self.descriptor['config_hash']
                        or lifecycle_identity(applied) != lifecycle_identity(latest)
                        or applied.applied_final_publisher_instance_id != receipt.final_publisher_instance_id
                        or applied.applied_final_publish_sequence != receipt.final_publish_sequence
                        or not applied.coverage_complete or not applied.contact_source_healthy
                        or applied.required_collision_mask == 0
                        or applied.required_collision_mask != applied.observed_collision_mask):
                    return None
                return receipt, applied, received_ns
            zero_receipt, state, _received_ns = await self.until(
                current_applied_zero, deadline_ns=deadline_ns,
                phase='R09b current applied SAFE_STOP before fixture pose')
        else:
            state = self.ingress.backend_state
        receipt = zero_receipt
        if receipt is None or state is None:
            raise RuntimeError('R09b fixture mutation lacks final receipt/backend state')
        if (receipt.final_publisher_instance_id != self.final.publisher_instance_id
                or (pose_name == 'contact_pose'
                    and receipt.source not in (FinalIssuedCommandReceipt.SOURCE_POLICY,
                        FinalIssuedCommandReceipt.SOURCE_SAFE_STOP))
                or any((receipt.final_command.linear.x, receipt.final_command.linear.y,
                        receipt.final_command.angular.z))):
            raise RuntimeError('R09b fixture mutation requires the bound zero final command')
        applied_zero = (state.applied_receipt_valid
            and state.applied_final_publisher_instance_id == receipt.final_publisher_instance_id
            and state.applied_final_publish_sequence == receipt.final_publish_sequence)
        emergency_zero = bool(state.local_zero_override and state.actuator_inhibited)
        if (not (applied_zero or emergency_zero) or state.fault_flags or state.paused):
            raise RuntimeError('R09b fixture mutation requires observed applied/emergency zero while unpaused')
        if (state.backend_instance_id != self.descriptor['backend_instance_id']
                or state.session_id != self.descriptor['session_id']
                or state.config_hash != self.descriptor['config_hash']):
            raise RuntimeError('R09b fixture mutation backend/session/config identity mismatch')
        request = self.pose_type.Request()
        request.entity.name, request.entity.type = fixture['entity_name'], Entity.MODEL
        request.pose.position.x, request.pose.position.y, request.pose.position.z = (
            pose['x_m'], pose['y_m'], pose['z_m'])
        request.pose.orientation.w = math.cos(pose['yaw_rad'] / 2)
        request.pose.orientation.z = math.sin(pose['yaw_rad'] / 2)
        started = self.now()
        remaining = min(1.0, (deadline_ns - started) / 1e9)
        if remaining <= 0:
            raise TimeoutError('R09b fixture SetEntityPose has no remaining step budget')
        self.emit('R09B_FIXTURE_POSE_REQUESTED', {
            'entity_name':fixture['entity_name'], 'entity_type':'MODEL', 'frame':'world',
            'pose_name':pose_name, 'target_pose':dict(pose),
            'zero_receipt_sequence':receipt.final_publish_sequence,
            'zero_receipt_source':receipt.source,
            'zero_applied':applied_zero, 'emergency_zero':emergency_zero,
            'actuator_inhibited':bool(state.actuator_inhibited),
            'recent_zero_witness_used':False,
            'zero_witness_age_ns':None,
            'backend_instance_id':state.backend_instance_id,
            'session_id':state.session_id, 'config_hash':state.config_hash,
            'request_cdr_hex':serialize_message(request).hex(), 'started_ns':started})
        response = await self.call(self.pose_client, request, timeout_s=remaining,
            phase='R09b_task_fixture_' + pose_name)
        if not response.success:
            raise RuntimeError('R09b SetEntityPose returned success=false for pinned fixture')
        self.emit('R09B_FIXTURE_POSE_APPLIED', {
            'entity_name':fixture['entity_name'], 'pose_name':pose_name,
            'target_pose':dict(pose), 'response_success':bool(response.success),
            'response_cdr_hex':serialize_message(response).hex(),
            'completed_ns':self.now()})
        return response

    async def run_r09b_contact_task_pulse(self, *, zero_receipt,
                                         zero_applied_state, deadline_ns,
                                         applied_received_ns):
        """Measure and clear the pinned fixture pulse under an applied zero.

        The caller may provide the bound SAFE_STOP zero while a B1 step is
        pending but before its POLICY issuance. The contact facts then remain
        in the real physics history for that step, while fixture RPC time
        cannot age the POLICY issuance past B1's unchanged freshness bound.
        """
        await self.set_r09b_task_fixture_pose(pose_name='contact_pose',
            deadline_ns=deadline_ns, zero_receipt=None)
        self.safety.local_training.set_policy_hold(True)
        self.emit('R09B_ZERO_STREAM_HELD_DURING_CONTACT_FIXTURE_TASK', {
            'zero_source':int(zero_receipt.source),
            'zero_publish_sequence':int(zero_receipt.final_publish_sequence),
            'applied_publish_sequence':int(zero_applied_state.applied_final_publish_sequence),
            'steady_ns':self.now()})
        return await restore_r09b_fixture_after_contact_pulse(self,
            deadline_ns=deadline_ns,
            after_status_sequence=zero_applied_state.status_sequence,
            after_physics_iteration=zero_applied_state.physics_iteration,
            zero_receipt=zero_receipt, zero_applied_state=zero_applied_state,
            zero_applied_received_ns=applied_received_ns)

    async def wait_r09b_pending_step_zero_witness(self, token, *, deadline_ns):
        """Join the pinned SAFE_STOP application, not a latest-value iteration.

        Physics status keeps advancing after a receipt is applied, so the
        latest status's physics iteration is normally newer than the retained
        application iteration. The receipt-keyed immutable application is the
        proof; the latest status only confirms the same zero remains active.
        """
        from mecanum_nav_rl_interfaces.msg import (
            FinalIssuedCommandReceipt, LocalTrainingSafetyInput,
        )
        from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
        ack = self.ingress.pending_ack
        if (ack is None or ack.request.operation != Control.Request.OP_BIND_PENDING_STEP
                or ack.request.pending_step_index != token.step_index
                or ack.request.pending_transition_id != token.transition_id
                or ack.response.result != Control.Response.RESULT_APPLIED
                or self.ingress.admission_state != LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN
                or not any(ack.response.pending_admission_token)):
            raise RuntimeError('R09b fixture task lacks the exact bound pending B1 slot')

        def exact_zero_witness():
            receipt = self.final.last_publication
            latest = self.ingress.backend_state
            if (receipt is None or latest is None
                    or receipt.source != FinalIssuedCommandReceipt.SOURCE_SAFE_STOP
                    or receipt.final_publisher_instance_id != self.final.publisher_instance_id
                    or any((receipt.final_command.linear.x, receipt.final_command.linear.y,
                        receipt.final_command.angular.z))
                    or latest.fault_flags or latest.paused or latest.actuator_inhibited
                    or latest.local_zero_override or not latest.applied_receipt_valid
                    or latest.applied_final_publisher_instance_id != receipt.final_publisher_instance_id
                    or latest.applied_final_publish_sequence != receipt.final_publish_sequence
                    or latest.backend_instance_id != self.descriptor['backend_instance_id']
                    or latest.session_id != self.descriptor['session_id']
                    or latest.config_hash != self.descriptor['config_hash']
                    or not latest.coverage_complete or not latest.contact_source_healthy
                    or latest.required_collision_mask == 0
                    or latest.required_collision_mask != latest.observed_collision_mask
                    or latest.contact_active):
                return None
            application = self.ingress.application_for_receipt(receipt)
            if application is None:
                return None
            state = application.get('state')
            received_ns = application.get('received_ns')
            now = self.now()
            if (state is None or type(received_ns) is not int
                    or not 0 <= now - received_ns <= 500_000_000
                    or state.applied_final_publisher_instance_id != receipt.final_publisher_instance_id
                    or state.applied_final_publish_sequence != receipt.final_publish_sequence
                    or state.backend_instance_id != self.descriptor['backend_instance_id']
                    or state.session_id != self.descriptor['session_id']
                    or state.config_hash != self.descriptor['config_hash']
                    or state.fault_flags or state.paused or state.actuator_inhibited
                    or state.local_zero_override or not state.coverage_complete
                    or not state.contact_source_healthy or state.contact_active):
                return None
            return receipt, state, received_ns

        return await self.until(exact_zero_witness, deadline_ns=deadline_ns,
            phase='R09b exact applied SAFE_STOP zero before fixture task')

    async def align_r09b_application_cutoff(self, b1, *, policy_receipt,
                                            minimum_cutoff_ns, deadline_ns):
        """Pin an applied zero and its following receipt around a B1 cutoff.

        During the R09b contact pulse Safety emits SAFE_STOP continuously. Keep
        that zero stream active while selecting the already retained exact
        application record and its adjacent receipt across a paired B1 cutoff.
        Freezing publication here can expire the native actuator watchdog
        before the asynchronous cutoff join completes.
        """
        from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import (
            lifecycle_identity, stamp_ns,
        )
        from mecanum_nav_rl.runtime_simulation.local_training_coordinator import B1SnapshotPending

        with self.ingress.lock:
            policy_view = self.ingress._receipt_views.get(
                policy_receipt.final_publish_sequence)
        if (policy_view is None or policy_view.source is not ReceiptSource.POLICY
                or policy_view.final_publisher_instance_id
                    != policy_receipt.final_publisher_instance_id
                or policy_view.source_instance_id != policy_receipt.source_instance_id
                or policy_view.source_sequence != policy_receipt.sequence
                or policy_view.step_index != policy_receipt.step_index
                or policy_view.transition_id != policy_receipt.transition_id
                or policy_view.publish_stamp_ns
                    != stamp_ns(policy_receipt.header.stamp)):
            raise RuntimeError('R09b cutoff alignment lacks the exact accepted POLICY receipt view')
        while self.now() < deadline_ns:
            self.check()
            def paired_cutoff():
                with self.ingress.lock:
                    receipts_by_sequence = dict(self.ingress._receipt_views)
                    cutoff_stamps = tuple(sorted(self.ingress.scans))
                receipt_views = tuple(receipts_by_sequence[key]
                    for key in sorted(receipts_by_sequence))
                for cutoff_ns in cutoff_stamps:
                    if cutoff_ns < minimum_cutoff_ns:
                        continue
                    matching_pairs = []
                    for selected in receipt_views:
                        boundary = receipts_by_sequence.get(
                            selected.final_publish_sequence + 1)
                        if (selected.source is not ReceiptSource.SAFE_STOP
                                or selected.lifecycle != policy_view.lifecycle
                                or selected.session_id != policy_view.session_id
                                or selected.publish_stamp_ns < policy_view.publish_stamp_ns
                                or any(selected.final_command)
                                or boundary is None
                                or boundary.source is not ReceiptSource.SAFE_STOP
                                or boundary.lifecycle != selected.lifecycle
                                or boundary.session_id != selected.session_id
                                or any(boundary.final_command)
                                or selected.publish_stamp_ns > cutoff_ns
                                or boundary.publish_stamp_ns <= cutoff_ns):
                            continue
                        application = self.ingress.application_for_receipt(selected)
                        if application is None:
                            continue
                        status = application['state']
                        applied_ns = stamp_ns(status.applied_sim_stamp)
                        if applied_ns >= cutoff_ns:
                            continue
                        matching_pairs.append((selected, boundary, application,
                            applied_ns, cutoff_ns))
                    if len(matching_pairs) != 1:
                        continue
                    selected, boundary, application, applied_ns, _ = matching_pairs[0]
                    try:
                        b1._joined(cutoff_ns)
                    except B1SnapshotPending:
                        continue
                    if self.now() >= deadline_ns:
                        raise TimeoutError('R09b paired cutoff completed after step deadline')
                    self.emit('R09B_APPLICATION_CUTOFF_BOUNDARY_PINNED', {
                        'selected_publish_sequence':selected.final_publish_sequence,
                        'selected_application_stamp_ns':applied_ns,
                        'cutoff_ns':cutoff_ns,
                        'adjacent_publish_sequence':boundary.final_publish_sequence,
                        'adjacent_publish_stamp_ns':boundary.publish_stamp_ns,
                        'status_sequence':application['state'].status_sequence,
                        'steady_ns':self.now()})
                    return cutoff_ns
                return None

            cutoff_ns = await self.until(paired_cutoff, deadline_ns=deadline_ns,
                phase='R09b applied zero and adjacent SAFE_STOP around paired cutoff')
            return cutoff_ns
        raise TimeoutError('R09b could not align an applied receipt around a B1 cutoff')

    async def lifecycle_event(self, *, rearm, deadline_ns):
        old = self.ingress.lifecycle
        previous = old.sequence if old is not None else 0
        client = self.rearm_client if rearm else self.reset_client
        budget = min(1., (deadline_ns - self.now()) / 1e9)
        if budget <= 0:
            raise TimeoutError('lifecycle event has no remaining budget')
        await self.call(client, self.trigger_type.Request(), timeout_s=budget,
                        phase='lifecycle_rearm' if rearm else 'lifecycle_reset')
        state = await self.until(lambda: self.ingress.lifecycle if self.ingress.lifecycle is not None
            and self.ingress.lifecycle.sequence > previous else None, deadline_ns=deadline_ns, phase='lifecycle source event')
        if state.barrier_state != (state.BARRIER_READY if rearm else state.BARRIER_NON_READY):
            raise RuntimeError('actual lifecycle event did not reach requested barrier')
        return copy.deepcopy(state)

    async def pin_graph(self, *, deadline_ns):
        def endpoints():
            cmd = self.node.get_publishers_info_by_topic('/cmd_vel')
            safety = self.node.get_publishers_info_by_topic('/mecanum/safety_state')
            ingress = self.node.get_publishers_info_by_topic('/mecanum/local_training/safety_input')
            world_ready = getattr(self.world_client, 'service_is_ready', None)
            if not callable(world_ready):
                raise RuntimeError('world control service readiness API unavailable')
            world_control_ready = bool(world_ready())
            self.emit('GRAPH_OBSERVATION', {name: [{'node': item.node_name,
                'namespace': item.node_namespace, 'type': item.topic_type,
                'gid_hex': bytes(item.endpoint_gid).hex()} for item in values]
                for name, values in [('cmd_vel',cmd),('safety',safety),('ingress',ingress)]} |
                {'world_control_service_ready':world_control_ready})
            if not (len(cmd) == len(safety) == len(ingress) == 1):
                return None
            # RMW DDS 3.1.1 trả sentinel khi endpoint đã thấy nhưng node chưa discovery.
            # Chưa đủ ownership: đợi trong cùng deadline, không bind hoặc đổi ngưỡng.
            if any(item.node_name == '_NODE_NAME_UNKNOWN_' or
                    item.node_namespace == '_NODE_NAMESPACE_UNKNOWN_'
                    for item in (cmd[0],safety[0],ingress[0])):
                return None
            if (cmd[0].node_name != 'final_twist_publisher' or safety[0].node_name != 'safety_supervisor'
                    or ingress[0].node_name != 'b23_coordinator_ingress'):
                raise RuntimeError('unexpected graph publisher ownership')
            if not world_control_ready:
                return None
            return cmd, safety, ingress
        cmd, safety, ingress = await self.until(endpoints, deadline_ns=deadline_ns, phase='source graph binding')
        self.ingress.bind_safety_publisher_gid(safety[0].endpoint_gid)
        self.emit('GRAPH_BOUND', {name: [{'node': item.node_name, 'namespace': item.node_namespace,
                'type': item.topic_type, 'gid_hex': bytes(item.endpoint_gid).hex()} for item in values]
            for name, values in [('cmd_vel', cmd), ('safety', safety), ('ingress', ingress)]})

    async def paused_state(self, paused, timeout, *, expected_native_fault_flags=None):
        status = await self.until(lambda: self.ingress.backend_state if self.ingress.backend_state is not None
            and self.ingress.backend_state.paused is paused else None,
            deadline_ns=self.now() + int(timeout * 1e9), phase='paused' if paused else 'resumed',
            expected_native_fault_flags=expected_native_fault_flags)
        self.expected_paused = paused
        if not paused:
            self.last_clock_advance_ns = self.now()
        self.emit('PAUSE_STATE_OBSERVED', {'paused': paused, 'status_sequence': status.status_sequence,
            'iteration': status.physics_iteration, 'steady_ns': self.now()})
        return True

    def read_native_input_watermark(self):
        path = Path(self.descriptor['native_events_path'])
        if not path.exists():
            return self._native_input_watermark
        safe_stop_ingress = getattr(self, '_native_safe_stop_ingress', None)
        if safe_stop_ingress is None:
            safe_stop_ingress = self._native_safe_stop_ingress = {}
        with path.open('rb') as stream:
            stream.seek(self._native_offset)
            raw = self._native_partial + stream.read(1_048_576)
            self._native_offset = stream.tell()
        lines = raw.split(b'\n'); self._native_partial = lines.pop()
        for line in lines:
            record = json.loads(line)
            kind = record['kind']
            if kind == 'B23_SAFE_STOP_RECEIPT_INGRESS':
                fields = record.get('fields')
                names = ('publisher', 'key', 'source_sequence', 'stamp_ns', 'receive_ns')
                valid_owner = (isinstance(fields, dict)
                    and record.get('server_leader_pid') == self.descriptor['server_leader_pid']
                    and record.get('invocation_id') == self.descriptor['invocation_id'])
                valid_fields = (valid_owner and all(
                    isinstance(fields.get(name), str) and fields[name].isdigit()
                    and int(fields[name]) > 0 for name in names))
                if not valid_fields:
                    self.emit('NATIVE_SAFE_STOP_RECEIPT_RECORD_REJECTED', {
                        'reason':('ownership_mismatch' if not valid_owner else 'incomplete_or_invalid_fields'),
                        'record_sha256':hashlib.sha256(line).hexdigest()})
                    continue
                key = tuple(fields[name] for name in names[:4])
                prior = safe_stop_ingress.get(key)
                if prior is not None and prior != record:
                    raise RuntimeError('native SAFE_STOP receipt evidence conflicts for exact key')
                safe_stop_ingress[key] = record
                continue
            if kind not in ('B23_SAFETY_INPUT_OBSERVED', 'B23_ADMISSION_ACCEPTED'):
                continue
            fields = record['fields']
            try:
                backend = int(fields['backend'])
                ingress = int(fields['ingress'])
                sample = int(fields['sample'])
            except (KeyError, TypeError, ValueError):
                self.emit('NATIVE_INPUT_WATERMARK_RECORD_REJECTED', {
                    'kind':record.get('kind'),
                    'reason':'incomplete_native_input_identity',
                    'record_sha256':hashlib.sha256(line).hexdigest(),
                    'fields':fields})
                continue
            if (fields['session'] != self.descriptor['session_id']
                    or backend != self.descriptor['backend_instance_id']
                    or ingress != self.descriptor['coordinator_ingress_instance_id']
                    or record['server_leader_pid'] != self.descriptor['server_leader_pid']
                    or record['invocation_id'] != self.descriptor['invocation_id']):
                raise RuntimeError('native input evidence ownership mismatch')
            self._native_input_watermark = max(self._native_input_watermark, sample)
        return self._native_input_watermark

    async def freeze_admission(self, *, deadline_ns):
        self.ingress.pause_admission_publication()
        target = self.ingress.last_published_sample_sequence
        if target:
            await self.until(lambda: self.read_native_input_watermark() >= target,
                             deadline_ns=deadline_ns, phase='native safety-input drain')
        self.emit('ADMISSION_STREAM_FROZEN', {'last_sample_sequence': target, 'steady_ns': self.now()})

    async def inhibit_and_drain(self, *, deadline_ns, zero_only=False):
        """Publish one fresh closing admission sample and observe it natively."""
        from mecanum_nav_rl_interfaces.msg import LocalTrainingSafetyInput
        previous = self.ingress.last_published_sample_sequence
        self.ingress.inhibit(zero_only=zero_only)
        self.safety.local_training.set_stream_enabled(True)
        expected = (LocalTrainingSafetyInput.ADMISSION_ZERO_ONLY if zero_only
                    else LocalTrainingSafetyInput.ADMISSION_INHIBITED)

        def drained():
            target = self.ingress.last_published_sample_sequence
            if (target <= previous or self.ingress.last_published_admission_state != expected
                    or self.read_native_input_watermark() < target):
                return None
            return target

        target = await self.until(drained, deadline_ns=deadline_ns,
            phase='fresh inhibited safety-input native drain')
        self.emit('INHIBITED_SAFETY_INPUT_DRAINED', {
            'previous_sample_sequence': previous, 'sample_sequence': target,
            'admission_state': expected, 'native_input_watermark': self._native_input_watermark,
            'steady_ns': self.now()})
        return target

    async def freeze_zero(self, *, deadline_ns):
        from mecanum_nav_rl.simulation.local_training_reset import AppliedZeroReceiptFact
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import stamp_ns
        adapter = self.safety.local_training
        adapter.set_policy_hold(True)
        initial_unarmed = (self.ingress.lifecycle is not None
            and self.ingress.lifecycle.episode_generation == 0 and not self.ingress._noise_ready
            and self.ingress.observation0_ack is None and self.ingress.last_published_sample_sequence == 0)
        sample_before = self.ingress.last_published_sample_sequence
        if not initial_unarmed:
            self.ingress.inhibit()
            await self.until(lambda: self.ingress.last_published_sample_sequence > sample_before
                and self.ingress.last_published_admission_state == 0,
                deadline_ns=deadline_ns, phase='closing admission publication')
        # Đợi ít nhất một tick SAFE_STOP trước khi khóa stream.
        previous = adapter.safe_stop_sequence
        await self.until(lambda: adapter.safe_stop_sequence > previous, deadline_ns=deadline_ns, phase='SAFE_STOP tick')
        await self.freeze_admission(deadline_ns=deadline_ns)
        adapter.set_stream_enabled(False)
        target = adapter.safe_stop_sequence
        receipt = await self.until(lambda: self.final.last_publication if self.final.last_publication is not None
            and self.final.last_publication.source == self.final.last_publication.SOURCE_SAFE_STOP
            and self.final.last_publication.sequence == target else None,
            deadline_ns=deadline_ns, phase='final SAFE_STOP drain')
        def applied():
            for pair in reversed(self.ingress.physics_pairs):
                from rclpy.serialization import deserialize_message
                from mecanum_nav_rl_interfaces.msg import SimulationContactState
                state = deserialize_message(pair.backend_bytes, SimulationContactState)
                if (state.applied_receipt_valid and not state.local_zero_override
                        and state.applied_final_publisher_instance_id == receipt.final_publisher_instance_id
                        and state.applied_final_publish_sequence == receipt.final_publish_sequence):
                    return pair, state
            return None
        pair, state = await self.until(applied, deadline_ns=deadline_ns, phase='native applied SAFE_STOP')
        identity = self.ingress.lifecycle
        fact = AppliedZeroReceiptFact(self.descriptor['session_id'], self.descriptor['config_hash'],
            self.descriptor['backend_instance_id'], receipt.episode_generation, receipt.reset_epoch,
            receipt.runtime_generation, receipt.final_publisher_instance_id, receipt.final_publish_sequence,
            receipt.source, receipt.source_instance_id, receipt.sequence, receipt.step_index, receipt.transition_id,
            (receipt.final_command.linear.x, receipt.final_command.linear.y, receipt.final_command.linear.z,
             receipt.final_command.angular.x, receipt.final_command.angular.y, receipt.final_command.angular.z),
            stamp_ns(identity.barrier_stamp), stamp_ns(receipt.header.stamp), state.applied_receipt_valid,
            state.applied_final_publisher_instance_id, state.applied_final_publish_sequence,
            state.applied_physics_iteration, stamp_ns(state.applied_sim_stamp), state.local_zero_override,
            pair.backend_received_steady_ns)
        self.emit('ZERO_STREAM_FROZEN', {'publish_sequence': fact.final_publish_sequence,
            'safe_stop_sequence': fact.source_sequence, 'application_iteration': fact.applied_physics_iteration,
            'application_stamp_ns': fact.applied_sim_stamp_ns, 'application_received_ns': fact.receive_steady_ns,
            'steady_ns': self.now()})
        return fact

    async def stop(self, *, deadline_ns):
        """Đóng ingress trước khi hủy RPC/pump; không nhận cancel là ACK native."""
        errors = []
        self.safety.local_training.set_policy_hold(True)
        self.ingress.inhibit()
        self.ingress.pause_admission_publication()
        self.safety.local_training.set_stream_enabled(False)
        for subscription in self.subscriptions:
            self.node.destroy_subscription(subscription)
        self.subscriptions.clear()
        if self.pump_task is not None and self.pump_task.done():
            try:
                self.pump_task.result()
            except BaseException as error:
                errors.append('original_pump_error:' + repr(error))
            # Chỉ còn RPC callbacks; thu ACK thực trước khi đóng executor.
            self.pump_task = asyncio.create_task(self._pump(), name='b23-owned-cleanup-rpc-pump')
        cleanup_control = self._r07b_cleanup_control or self.control
        try:
            await cleanup_control.inhibit(deadline_ns=min(deadline_ns, self.now() + 1_000_000_000))
        except BaseException as error:
            errors.append('inhibit:' + repr(error))
        self.safety.local_training.set_stream_enabled(False)
        self.ingress.pause_admission_publication()
        cleanup_control.cancel_pending_calls()
        if cleanup_control is not self.control:
            self.control.cancel_pending_calls()
        for future in self.calls:
            if not future.done(): future.cancel()
        self.stop_requested = True
        if self.pump_task is not None:
            self.pump_task.cancel()
            try:
                await asyncio.wait_for(self.pump_task, timeout=max(0., (deadline_ns - self.now()) / 1e9))
            except asyncio.CancelledError:
                pass
            except BaseException as error:
                errors.append('pump_join:' + repr(error))
        errors.extend(self.close_context())
        if self.now() > deadline_ns:
            errors.append('worker_cleanup_deadline_exceeded')
        self.emit('WORKER_CLEANUP', {'errors': errors, 'owned_calls_pending': len(self.control.owned_calls),
            'rpc_pending': sum(not call.done() for call in self.calls),
            'pump_joined': self.pump_task is None or self.pump_task.done(), 'steady_ns': self.now()})
        self.cleanup_errors = tuple(errors)
        return not errors

    def pin_replacement_backend_for_cleanup(self, control, expected_backend_instance_id):
        """Use cleanup control only when it is bound to the verified replacement."""
        identity = getattr(control, 'identity', None)
        backend_instance_id = getattr(identity, 'backend_instance_id', None)
        if (type(expected_backend_instance_id) is not int or expected_backend_instance_id <= 0
                or type(backend_instance_id) is not int
                or backend_instance_id != expected_backend_instance_id):
            raise RuntimeError('replacement cleanup control identity mismatch')
        self._r07b_cleanup_control = control

    def close_context(self):
        errors = []
        self.stop_requested = True
        if self.safety_executor is not None:
            try:
                if not self.safety_executor.shutdown(timeout_sec=1.0):
                    errors.append('safety_executor_shutdown_not_joined')
            except BaseException as error:
                errors.append('safety_executor_shutdown:' + repr(error))
        if self.safety_thread is not None:
            self.safety_thread.join(timeout=1.0)
            if self.safety_thread.is_alive():
                errors.append('safety_executor_thread_not_joined')
        if self.executor is not None:
            try:
                if not self.executor.shutdown(timeout_sec=0.):
                    errors.append('executor_shutdown_not_joined')
            except BaseException as error: errors.append(repr(error))
        try:
            if self.context.ok(): self.context.shutdown()
        except BaseException as error:
            errors.append(repr(error))
        thread_joined = self.safety_thread is None or not self.safety_thread.is_alive()
        if thread_joined:
            for node in reversed(self.nodes):
                try:
                    owner = self.safety_executor if node is self.safety else self.executor
                    if owner is not None: owner.remove_node(node)
                    node.destroy_node()
                except BaseException as error:
                    errors.append(repr(error))
            self.nodes.clear()
        else:
            errors.append('nodes_retained_until_owned_process_reap')
        if errors:
            self.emit('ROS_CONTEXT_CLEANUP_ERRORS', {'errors': errors})
        return errors

    async def startup(self):
        from rclpy.lifecycle import TransitionCallbackReturn
        from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
        from mecanum_nav_rl.runtime_simulation.local_training_coordinator import lifecycle_request_fields
        if (self.life.trigger_configure() != TransitionCallbackReturn.SUCCESS
                or self.life.trigger_activate() != TransitionCallbackReturn.SUCCESS):
            raise RuntimeError('actual lifecycle configure/activate failed')
        await self.pin_graph(deadline_ns=min(self.deadline_ns, self.now() + 5_000_000_000))
        await self.control_world(world_name='b2_training_arena', pause=False, timeout_s=1.)
        await self.paused_state(False, 2.)
        await self.until(lambda: self.ros_now() > 0, deadline_ns=self.now() + 2_000_000_000, phase='advancing startup clock')
        life = await self.lifecycle_event(rearm=True, deadline_ns=self.now() + 1_000_000_000)
        ack = await self.control.transact(Control.Request.OP_BIND_SESSION,
            deadline_ns=self.now() + 1_000_000_000, **lifecycle_request_fields(life),
            final_publisher_instance_id=self.final.publisher_instance_id,
            policy_source_instance_id=self.policy_source_id, safe_stop_source_instance_id=self.safe_stop_source_id,
            next_safe_stop_sequence=1)
        await self.bind_final_process(ack)
        self.emit('SESSION_BOUND', {'request_sequence': ack.request.request_sequence,
            'revision': ack.response.applied_binding_revision, 'steady_ns': self.now()})
        self.safety.local_training.set_stream_enabled(True)
        await self.contact_capability()

    async def contact_capability(self):
        from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
        from mecanum_nav_rl.runtime_simulation.local_training_coordinator import lifecycle_request_fields
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import stamp_ns
        started, last = self.now(), None
        deadline = min(self.deadline_ns, started + 5_000_000_000)
        work_deadline = deadline - 1_000_000_000
        start_ack = await self.control.transact(Control.Request.OP_VERIFY_CONTACT_CAPABILITY,
            deadline_ns=min(work_deadline, self.now() + 1_000_000_000),
            probe_action=Control.Request.PROBE_ACTION_START,
            **lifecycle_request_fields(self.ingress.lifecycle))
        reference = start_ack.request.request_sequence
        self.contact_start_request_sequence = reference
        try:
            while self.now() < work_deadline:
                last = await self.control.transact(Control.Request.OP_VERIFY_CONTACT_CAPABILITY,
                    deadline_ns=min(work_deadline, self.now() + 1_000_000_000),
                    probe_action=Control.Request.PROBE_ACTION_QUERY, probe_start_request_sequence=reference)
                proof = last.response
                if proof.contact_capability_state == proof.CAPABILITY_VERIFIED:
                    registry = ''.join(row['collision'] + ('|wheel\n' if row['wheel_floor_ignore'] else '|solid\n')
                        for row in sorted(self.asset['collision_registry']['tracked_collisions'], key=lambda row: row['collision']))
                    expected = dict(proof_session_id=self.descriptor['session_id'],
                        proof_backend_instance_id=self.descriptor['backend_instance_id'],
                        proof_config_hash=self.descriptor['config_hash'],
                        proof_asset_manifest_sha256=self.descriptor['asset_manifest_sha256'],
                        proof_world_name='b2_training_arena',
                        proof_collision_registry_sha256=hashlib.sha256(registry.encode()).hexdigest(),
                        proof_physics_engine_fingerprint_sha256=self.descriptor['physics_engine_sha256'])
                    for name, value in expected.items():
                        if getattr(proof, name) != value:
                            raise RuntimeError('actual contact proof mismatch: ' + name)
                    if not proof.proof_gz_sim_version.startswith('8.') or not proof.proof_physics_engine_plugin:
                        raise RuntimeError('contact proof has no pinned engine provenance')
                    for name, value in dict(probe_model_scoped_name='b2_training_arena::b2_capability_probe',
                        probe_collision_scoped_name='b2_training_arena::b2_capability_probe::link::collision',
                        floor_collision_scoped_name='b2_training_arena::ground_plane::link::collision').items():
                        if getattr(proof, name) != value:
                            raise RuntimeError('contact proof exact entity name mismatch')
                    ids = (proof.probe_model_entity_id, proof.probe_collision_entity_id, proof.floor_collision_entity_id)
                    if any(value == 0 for value in ids) or len(set(ids)) != 3:
                        raise RuntimeError('contact proof entity IDs missing/aliased')
                    for prefix, count in [('contact', proof.contact_sample_count), ('empty', proof.covered_empty_sample_count)]:
                        first, final = getattr(proof, prefix + '_first_iteration'), getattr(proof, prefix + '_last_iteration')
                        if (count < 3 or first == 0 or final - first + 1 != count
                                or stamp_ns(getattr(proof, prefix + '_last_stamp')) - stamp_ns(getattr(proof, prefix + '_first_stamp')) < 20_000_000):
                            raise RuntimeError('contact proof sample coverage invalid')
                    if proof.empty_first_iteration <= proof.contact_last_iteration:
                        raise RuntimeError('contact separation ordering invalid')
                    self.emit('CONTACT_CAPABILITY_VERIFIED', {'request_cdr_hex': last.request_bytes.hex(),
                        'response_cdr_hex': last.response_bytes.hex(), 'started_ns': started,
                        'completed_ns': self.now(), 'deadline_ns': deadline})
                    self.contact_ack = last
                    return last
                if proof.contact_capability_state in (proof.CAPABILITY_FAILED, proof.CAPABILITY_INVALIDATED):
                    raise RuntimeError('native contact capability failed/invalidated')
                await self.pause(min(0.01, max(0., (work_deadline - self.now()) / 1e9)))
            raise TimeoutError('normal contact proof not verified before cleanup reserve')
        finally:
            if (last is None or last.response.contact_capability_state != Control.Response.CAPABILITY_VERIFIED):
                try:
                    await self.control.transact(Control.Request.OP_VERIFY_CONTACT_CAPABILITY,
                        deadline_ns=min(deadline, self.now() + 1_000_000_000),
                        probe_action=Control.Request.PROBE_ACTION_ABORT, probe_start_request_sequence=reference)
                except BaseException as error:
                    self.emit('CONTACT_ABORT_ERROR', {'error': repr(error), 'steady_ns': self.now()})

    def fresh_reset_scan(self, *, now_ros_ns, now_steady_ns, at_or_before_ns=None,
                         at_or_after_ns=None):
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import stamp_ns
        from mecanum_nav_rl.simulation.local_training_io import validate_dual_clock_freshness
        if self.ingress.lifecycle is None:
            return None
        barrier = max(stamp_ns(self.ingress.lifecycle.barrier_stamp), self.ingress.scan_reset_stamp_ns)
        for stamp, sample in reversed(list(self.ingress.scans.items())):
            if at_or_before_ns is not None and stamp > at_or_before_ns:
                continue
            if at_or_after_ns is not None and stamp < at_or_after_ns:
                continue
            if stamp <= barrier:
                continue
            try:
                validate_dual_clock_freshness(source_ros_ns=stamp, now_ros_ns=now_ros_ns,
                    receive_steady_ns=sample.received_steady_ns, now_steady_ns=now_steady_ns,
                    max_age_ns=self.ingress.profile['scan_max_age_ms'] * 1_000_000)
            except ValueError:
                continue
            return sample
        return None

    def scan_clearance(self, *, now_ros_ns, now_steady_ns):
        from sensor_msgs.msg import LaserScan
        from rclpy.serialization import deserialize_message
        from rclpy.time import Time
        from mecanum_nav_rl.simulation.local_training_io import validate_dual_clock_freshness
        saved = self.fresh_reset_scan(now_ros_ns=now_ros_ns, now_steady_ns=now_steady_ns)
        if saved is None:
            raise RuntimeError('reset has no fresh post-barrier scan for clearance')
        validate_dual_clock_freshness(source_ros_ns=saved.stamp_ns, now_ros_ns=now_ros_ns,
            receive_steady_ns=saved.received_steady_ns, now_steady_ns=now_steady_ns,
            max_age_ns=self.ingress.profile['scan_max_age_ms'] * 1_000_000)
        scan = deserialize_message(saved.message_bytes, LaserScan)
        transform = self.safety._tf_buffer.lookup_transform('base_link', 'lidar_frame', Time())
        t, q = transform.transform.translation, transform.transform.rotation
        expected = self.asset['sensor']['extrinsic_xyz_m']
        if (any(abs(a - b) > 1e-9 for a, b in zip((t.x, t.y, t.z), expected))
                or any(abs(value) > 1e-9 for value in (q.x, q.y, q.z)) or abs(abs(q.w) - 1.) > 1e-9):
            raise RuntimeError('reset scan transform differs from asset')
        points = ((t.x + (scan.range_max if value == math.inf else value) * math.cos(scan.angle_min + i * scan.angle_increment),
                   t.y + (scan.range_max if value == math.inf else value) * math.sin(scan.angle_min + i * scan.angle_increment))
                  for i, value in enumerate(scan.ranges))
        return min(math.hypot(x, y) for x, y in points) - self.ingress.profile['robot_bounding_radius_m']

    async def measurements(self, *, deadline_ns, after_iteration):
        from nav_msgs.msg import Odometry
        from rclpy.serialization import deserialize_message
        from mecanum_nav_rl_interfaces.msg import SimulationContactState
        from mecanum_nav_rl.simulation.local_training_reset import ResetMeasurement
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import quaternion_rpy
        last = after_iteration
        # Sau reset_noise, buffer scan rỗng; đợi mẫu thật trong deadline gốc.
        await self.until(lambda: self.fresh_reset_scan(now_ros_ns=self.ros_now(), now_steady_ns=self.now()),
            deadline_ns=deadline_ns, phase='fresh reset scan')
        while self.now() < deadline_ns:
            pair = await self.until(lambda: next((value for value in self.ingress.physics_pairs
                if value.iteration > last), None), deadline_ns=deadline_ns, phase='fresh reset physics pair')
            oracle = deserialize_message(pair.oracle_bytes, Odometry)
            status = deserialize_message(pair.backend_bytes, SimulationContactState)
            pose, twist = oracle.pose.pose, oracle.twist.twist
            roll, pitch, yaw = quaternion_rpy(pose.orientation)
            clearance = self.scan_clearance(now_ros_ns=self.ros_now(), now_steady_ns=self.now())
            sample = ResetMeasurement(pair.iteration, pair.stamp_ns, pose.position.x, pose.position.y,
                pose.position.z, roll, pitch, yaw, (twist.linear.x, twist.linear.y, twist.linear.z),
                (twist.angular.x, twist.angular.y, twist.angular.z),
                status.contact_source_healthy and status.coverage_complete
                    and status.required_collision_mask != 0 and status.required_collision_mask == status.observed_collision_mask,
                status.contact_active, clearance >= self.ingress.profile['reset_footprint_clearance_expansion_m'],
                status.session_id, status.config_hash, status.backend_instance_id, status.reset_epoch,
                pair.backend_received_steady_ns, status.episode_generation, status.runtime_generation,
                pair.oracle_received_steady_ns, pair.stamp_ns)
            last = pair.iteration
            fault = self._r06b_measurement_fault
            if ('omit_one_settle_physics_iteration' in getattr(self, 'fault_hooks', ())
                    and fault['active'] and fault['yielded'] and not fault['dropped']):
                fault['dropped'] = True
                self.emit('B23_R06B_PHYSICS_ITERATION_OMITTED', {
                    'iteration':int(pair.iteration), 'stamp_ns':int(pair.stamp_ns),
                    'after_iteration':int(after_iteration), 'steady_ns':self.now(),
                    'reason':'packet-pinned fault omits one exact post-reset measurement'})
                continue
            self.emit('RESET_MEASUREMENT', {'iteration': sample.iteration, 'stamp_ns': sample.stamp_ns,
                'position_xyz': [sample.x_m, sample.y_m, sample.z_m], 'rpy': [roll, pitch, yaw],
                'linear_xyz': list(sample.linear_xyz_mps), 'angular_xyz': list(sample.angular_xyz_radps),
                'clearance_m': clearance, 'contact_healthy': sample.contact_healthy,
                'contact_active': sample.contact_active, 'backend_received_ns': sample.receive_steady_ns,
                'oracle_received_ns': sample.oracle_receive_steady_ns, 'steady_ns': self.now()})
            if 'omit_one_settle_physics_iteration' in getattr(self, 'fault_hooks', ()) and fault['active']:
                fault['yielded'] = True
            yield sample
        raise TimeoutError('reset measurement stream deadline expired')

    async def reset_episode(self, b1, *, seed, target, paused_hold_s=0.):
        from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
        from mecanum_nav_rl.runtime_simulation.local_training_coordinator import lifecycle_request_fields
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import stamp_ns
        from mecanum_nav_rl.simulation.local_training_reset import LocalTrainingResetAdapter
        started = self.now()
        deadline = min(self.deadline_ns, started + 15_000_000_000)
        w0 = await self.freeze_zero(deadline_ns=min(deadline, started + 5_000_000_000))
        self.emit('RESET_W0', {'publish_sequence': w0.final_publish_sequence,
            'safe_stop_sequence': w0.source_sequence, 'steady_ns': self.now(), 'reset_deadline_ns': deadline})
        l1 = await self.lifecycle_event(rearm=False, deadline_ns=min(deadline, self.now() + 1_000_000_000))
        await self.control.transact(Control.Request.OP_BIND_RESET_CONTEXT,
            deadline_ns=min(deadline, self.now() + 1_000_000_000), **lifecycle_request_fields(l1),
            final_publisher_instance_id=self.final.publisher_instance_id, policy_source_instance_id=self.policy_source_id,
            safe_stop_source_instance_id=self.safe_stop_source_id,
            next_safe_stop_sequence=self.safety.local_training.safe_stop_sequence + 1)
        if not self.ingress._noise_ready:
            self.ingress.reset_noise(seed)
        self.ingress.inhibit()
        self.safety.local_training.set_stream_enabled(True)
        await self.until(lambda: self.ingress.physics_pairs and self.ingress.physics_pairs[-1],
                         deadline_ns=deadline, phase='L1 actual physics context')
        before = self.ingress.physics_pairs[-1].iteration
        async def native_pause(fact, timeout):
            budget_ms = min(100, max(0, (deadline - self.now()) // 1_000_000))
            if budget_ms == 0:
                raise TimeoutError('native pause enter has no remaining budget')
            pause_deadline = min(deadline, self.now() + int(timeout * 1e9))
            self.ingress.begin_pause_transition(final_sequence=fact.final_publish_sequence, deadline_ns=pause_deadline)
            if 'external_pause_after_w1_before_native_dispatch' in self.fault_hooks:
                await self.control_world(world_name='b2_training_arena', pause=True,
                    timeout_s=min(1., max(0., (pause_deadline-self.now())/1e9)))
                self.emit('FAULT_HOOK_EXTERNAL_PAUSE_AFTER_W1', {
                    'w1_final_publish_sequence': fact.final_publish_sequence,
                    'steady_ns': self.now(), 'native_intent_dispatched': False})
            self.expected_paused = True  # Chỉ sau khi bắt đầu giao dịch pause native.
            ack = await self.control.transact(Control.Request.OP_PREPARE_RESET_PAUSE,
                deadline_ns=pause_deadline,
                **lifecycle_request_fields(self.ingress.lifecycle),
                final_publisher_instance_id=self.final.publisher_instance_id,
                pause_fence_final_publish_sequence=fact.final_publish_sequence,
                pause_enter_budget_ms=int(budget_ms))
            self.ingress.confirm_pause_transition(ack)
            self.pause_ack = ack
            self.emit('NATIVE_PAUSE_CONFIRMED', {'request_cdr_hex': ack.request_bytes.hex(),
                'response_cdr_hex': ack.response_bytes.hex(), 'steady_ns': self.now()})
            return True
        async def w1():
            result = await self.freeze_zero(deadline_ns=min(deadline, self.now() + 1_000_000_000))
            self.emit('RESET_W1', {'publish_sequence': result.final_publish_sequence,
                'safe_stop_sequence': result.source_sequence, 'steady_ns': self.now()})
            return result
        adapter = LocalTrainingResetAdapter(self, self.paused_state,
            lambda: self.measurements(deadline_ns=deadline, after_iteration=(
                self.ingress.physics_pairs[-1].iteration if self.ingress.physics_pairs else 0)),
            expected_session_id=self.descriptor['session_id'], expected_config_hash=self.descriptor['config_hash'],
            expected_backend_instance_id=self.descriptor['backend_instance_id'],
            expected_reset_epoch=l1.reset_epoch, expected_episode_generation=l1.episode_generation,
            expected_runtime_generation=l1.runtime_generation, expected_final_publisher_instance_id=self.final.publisher_instance_id,
            expected_safe_stop_source_instance_id=self.safe_stop_source_id,
            expected_barrier_stamp_ns=stamp_ns(l1.barrier_stamp),
            monotonic=lambda: self.now() / 1e9, sleep=self.pause,
            oracle_max_age_ns=self.ingress.profile['oracle_max_age_ms'] * 1_000_000,
            now_ros_ns=self.ros_now, native_pause=native_pause)
        original_set_entity_pose = self.set_entity_pose
        if 'set_pose_ack_with_wrong_target' in getattr(self, 'fault_hooks', ()):
            async def wrong_target_pose(**kwargs):
                actual = copy.copy(kwargs['target'])
                actual = type(actual)(x_m=actual.x_m + 0.25, y_m=actual.y_m,
                    z_m=actual.z_m, yaw_rad=actual.yaw_rad)
                self.emit('B23_R06A_SET_POSE_TARGET_MUTATED', {
                    'requested_target':{'x_m':kwargs['target'].x_m,'y_m':kwargs['target'].y_m,
                        'z_m':kwargs['target'].z_m,'yaw_rad':kwargs['target'].yaw_rad},
                    'actual_target':{'x_m':actual.x_m,'y_m':actual.y_m,
                        'z_m':actual.z_m,'yaw_rad':actual.yaw_rad}, 'steady_ns':self.now()})
                return await original_set_entity_pose(**{**kwargs, 'target':actual})
            self.set_entity_pose = wrong_target_pose
        async def reset_buffers():
            self.ingress.reset_noise(seed)
            if 'omit_one_settle_physics_iteration' in getattr(self, 'fault_hooks', ()):
                self._r06b_measurement_fault['active'] = True
                self.emit('B23_R06B_FAULT_ARMED', {'after_reset_buffer_clear':True,
                    'reset_scan_stamp_ns':self.ingress.scan_reset_stamp_ns,'steady_ns':self.now()})
        try:
            facts = await adapter.execute_async(target=target,
            measured_standstill=self.measurements(deadline_ns=deadline, after_iteration=before),
            applied_zero_receipt=w1, reset_emulator_and_buffers=reset_buffers,
            reset_deadline=deadline / 1e9, paused_hold_s=paused_hold_s,
            stop_deadline=min(deadline, started+5_000_000_000)/1e9,
            braking_start_stamp_ns=w0.applied_sim_stamp_ns)
        finally:
            if 'set_pose_ack_with_wrong_target' in getattr(self, 'fault_hooks', ()):
                self.__dict__.pop('set_entity_pose', None)
        l2 = await self.lifecycle_event(rearm=True, deadline_ns=min(deadline, self.now() + 1_000_000_000))
        await self.control.transact(Control.Request.OP_BIND_RESET_CONTEXT,
            deadline_ns=min(deadline, self.now() + 1_000_000_000), **lifecycle_request_fields(l2),
            final_publisher_instance_id=self.final.publisher_instance_id, policy_source_instance_id=self.policy_source_id,
            safe_stop_source_instance_id=self.safe_stop_source_id,
            next_safe_stop_sequence=self.safety.local_training.safe_stop_sequence + 1)
        return await self.confirm_observation0_after_resume(b1, deadline_ns=deadline,
            seed=seed, w0=w0, w1=facts.applied_zero_receipt, l1=l1, l2=l2,
            started_ns=started)

    async def confirm_observation0_after_resume(self, b1, *, deadline_ns,
            seed, w0, w1, l1, l2, started_ns):
        """Re-anchor reset confirmation with a fresh applied zero after L2.

        W1 proves the zero used to enter pause. The paused hold and resume may
        consume its 500 ms receipt freshness budget, so observation0 must use a
        newly published and natively applied SAFE_STOP receipt in the rebound
        L2 context.
        """
        # Sau L2, phát và xác minh một zero SAFE_STOP mới để B1 dùng
        # receipt còn mới tại cutoff, thay vì W1 đã cũ qua pause/resume.
        b1.begin_reset()
        self.ingress.inhibit()
        self.safety.local_training.set_stream_enabled(True)
        observation0_zero = await self.freeze_zero(deadline_ns=deadline_ns)
        if 'hold_observation0_adjacent_receipt_until_reset_deadline' in getattr(self, 'fault_hooks', ()):
            self._r06c_hold_after_sequence = int(observation0_zero.final_publish_sequence)
            self._r06c_reset_deadline_ns = int(deadline_ns)
            self.emit('B23_R06C_FAULT_ARMED', {
                'zero_anchor_sequence':self._r06c_hold_after_sequence,
                'zero_anchor_stamp_ns':int(observation0_zero.applied_sim_stamp_ns),
                'reset_deadline_ns':int(deadline_ns), 'steady_ns':self.now(),
                'reason':'withhold subsequent SAFE_STOP receipt callbacks through the original reset deadline'})
        self.emit('OBSERVATION0_ZERO_ANCHOR', {'publish_sequence': observation0_zero.final_publish_sequence,
            'application_stamp_ns': observation0_zero.applied_sim_stamp_ns,
            'application_iteration': observation0_zero.applied_physics_iteration, 'steady_ns': self.now()})
        # Giữ Safety stream chạy ở inhibit để refresh receipt SAFE_STOP trong
        # lúc chờ exact sensor join và CONFIRM; POLICY vẫn chưa được bind.
        self.safety.local_training.set_stream_enabled(True)
        observation, cutoff = await self.commit_and_confirm_observation0(
            b1, deadline_ns=deadline_ns, zero_receipt=observation0_zero)
        self.emit('RESET_COMPLETE', {'seed': seed, 'observation0_cutoff_ns': cutoff,
            'W0': w0.final_publish_sequence, 'W1': w1.final_publish_sequence,
            'zero_anchor_sequence': observation0_zero.final_publish_sequence,
            'l1_sequence': l1.sequence, 'l2_sequence': l2.sequence,
            'started_ns': started_ns, 'completed_ns': self.now(), 'deadline_ns': deadline_ns})
        return observation

    async def commit_and_confirm_observation0(self, b1, *, deadline_ns, zero_receipt=None):
        """Commit B1, xác nhận backend và chỉ giao observation khi ACK hợp lệ."""
        from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
        from mecanum_nav_rl.runtime_simulation.local_training_coordinator import lifecycle_request_fields, B1SnapshotPending
        last_pending = None
        while self.now() < deadline_ns:
            self.check()
            scan = self.fresh_reset_scan(now_ros_ns=self.ros_now(), now_steady_ns=self.now(),
                at_or_after_ns=None if zero_receipt is None else zero_receipt.applied_sim_stamp_ns)
            for cutoff in ([scan.stamp_ns] if scan is not None else []):
                try:
                    selection = b1.preview_observation0_selection(cutoff)
                    # B1's cutoff may contain a fresh SAFE_STOP receipt that
                    # has not yet been applied by native at or before this
                    # scan. Check that condition before waiting for the
                    # adjacent receipt; otherwise a scan/SAFE_STOP timer phase
                    # lock can make every new cutoff select the same invalid
                    # boundary until its 500 ms freshness budget expires.
                    b1._prove_application(selection.receipt, cutoff)
                except B1SnapshotPending as error:
                    last_pending = str(error)
                    if 'selected SAFE_STOP receipt exceeds the unchanged 500 ms freshness limit' in last_pending:
                        self.emit('RESET_ZERO_RECEIPT_FRESHNESS_DEFERRED', {
                            'cutoff_ns': cutoff,
                            'reason': last_pending,
                            'steady_ns': self.now()})
                    if last_pending == 'selected receipt lacks native application at/before cutoff':
                        reset_scans = sorted(stamp for stamp in self.ingress.scans
                            if self.ingress.scan_reset_stamp_ns < stamp <= cutoff)
                        if len(reset_scans) >= 2 and reset_scans[-1] == cutoff:
                            await self.align_reset_zero_receipt_boundary(
                                failed_cutoff_ns=cutoff, deadline_ns=deadline_ns)
                        else:
                            self.emit('RESET_RECEIPT_ALIGNMENT_DEFERRED', {
                                'failed_cutoff_ns': cutoff, 'post_reset_scans': reset_scans,
                                'steady_ns': self.now()})
                    continue
                native_boundary = self.native_adjacent_boundary_application(selection, cutoff)
                if native_boundary is None:
                    last_pending = 'native has not applied the adjacent post-cutoff SAFE_STOP receipt'
                    self.emit('RESET_ADJACENT_BOUNDARY_DEFERRED', {
                        'cutoff_ns': cutoff,
                        'adjacent_publisher_instance_id': selection.adjacent_receipt.final_publisher_instance_id,
                        'adjacent_publish_sequence': selection.adjacent_receipt.final_publish_sequence,
                        'steady_ns': self.now()})
                    continue
                expected_selection_keys = (selection.receipt.receipt_key,
                    selection.adjacent_receipt.receipt_key)
                try:
                    observation, selection = b1.commit_observation0(
                        cutoff, expected_selection_keys=expected_selection_keys)
                except B1SnapshotPending as error:
                    last_pending = str(error)
                    continue
                self.emit('RESET_ADJACENT_BOUNDARY_NATIVE_APPLIED', {
                    'cutoff_ns': cutoff,
                    'adjacent_publisher_instance_id': selection.adjacent_receipt.final_publisher_instance_id,
                    'adjacent_publish_sequence': selection.adjacent_receipt.final_publish_sequence,
                    'application_iteration': native_boundary['iteration'],
                    'application_stamp_ns': native_boundary['stamp_ns'],
                    'steady_ns': self.now()})
                ack = await self.control.transact(Control.Request.OP_CONFIRM_OBSERVATION0,
                    deadline_ns=min(deadline_ns, self.now() + 1_000_000_000),
                    **lifecycle_request_fields(self.ingress.lifecycle),
                    observation0_cutoff=self._time_msg(cutoff),
                    selected_zero_final_publisher_instance_id=self.final.publisher_instance_id,
                    selected_zero_final_publish_sequence=selection.receipt.final_publish_sequence,
                    adjacent_boundary_final_publisher_instance_id=self.final.publisher_instance_id,
                    adjacent_boundary_final_publish_sequence=selection.adjacent_receipt.final_publish_sequence)
                self.ingress.confirm_observation0(ack)
                return observation, cutoff
            await self.pause(min(0.002, max(0., (deadline_ns - self.now()) / 1e9)))
        raise TimeoutError('observation0 did not confirm within reset deadline: ' + str(last_pending))

    def native_adjacent_boundary_application(self, selection, cutoff_ns):
        """Return the exact native application of the adjacent receipt after cutoff."""
        from rclpy.serialization import deserialize_message
        from mecanum_nav_rl_interfaces.msg import SimulationContactState
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import stamp_ns
        receipt = selection.adjacent_receipt
        with self.ingress.lock:
            raw = self.ingress._application_bytes.get(receipt.final_publish_sequence)
        if raw is None:
            return None
        status = deserialize_message(raw, SimulationContactState)
        applied_stamp_ns = stamp_ns(status.applied_sim_stamp)
        if (not status.applied_receipt_valid or status.local_zero_override
                or status.applied_final_publisher_instance_id != receipt.final_publisher_instance_id
                or status.applied_final_publish_sequence != receipt.final_publish_sequence
                or status.applied_physics_iteration == 0
                or status.applied_physics_iteration != status.physics_iteration
                or applied_stamp_ns != stamp_ns(status.header.stamp)
                or applied_stamp_ns <= cutoff_ns):
            return None
        return {'iteration': status.applied_physics_iteration, 'stamp_ns': applied_stamp_ns}

    async def align_reset_zero_receipt_boundary(self, *, failed_cutoff_ns, deadline_ns):
        """Skip one colliding reset SAFE_STOP using observed receipt evidence.

        The timer's observed ROS stamps need not equal target minus its nominal
        period. Pin the latest actually published/applied zero before the next
        scan, suppress only the repeated zero at that exact scan stamp, then
        wait for an observed SAFE_STOP receipt after the cutoff. This is only a
        resynchronization hint: B1 independently selects and proves its exact
        adjacent receipt pair before committing observation0. Receipt
        callbacks may coalesce earlier publications, so this wait must not
        require the first post-cutoff sequence to be visible here.
        """
        from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import lifecycle_identity, stamp_ns
        from mecanum_nav_rl_interfaces.msg import SimulationContactState
        from rclpy.serialization import deserialize_message

        scans = sorted(stamp for stamp in self.ingress.scans
            if stamp > self.ingress.scan_reset_stamp_ns)
        if len(scans) < 2 or scans[-1] != failed_cutoff_ns:
            raise RuntimeError('cannot align reset receipt without two ordered post-reset scans')
        scan_period_ns = scans[-1] - scans[-2]
        if scan_period_ns <= 0 or scan_period_ns > self.ingress.profile['scan_max_age_ms'] * 1_000_000:
            raise RuntimeError('observed scan cadence cannot safely align SAFE_STOP publication')
        target_ns = failed_cutoff_ns + scan_period_ns
        life = self.ingress.lifecycle
        from mecanum_nav_rl_interfaces.msg import CommandEnvelope, LocalTrainingSafetyInput
        adapter = self.safety.local_training
        last_output = adapter.last_output
        if (life is None
                or self.ingress.admission_state != LocalTrainingSafetyInput.ADMISSION_INHIBITED
                or self.ingress.last_published_admission_state != LocalTrainingSafetyInput.ADMISSION_INHIBITED
                or not adapter.policy_hold
                or last_output is None or last_output.source != CommandEnvelope.SOURCE_SAFE_STOP):
            raise RuntimeError('reset receipt alignment requires admission to remain inhibited')
        identity = lifecycle_identity(life)
        if self.ros_now() >= target_ns:
            self.emit('RESET_RECEIPT_ALIGNMENT_MISSED', {'target_scan_ns': target_ns,
                'reason': 'scan boundary already passed before suppression was armed',
                'steady_ns': self.now()})
            return False
        # Boundary alignment is governed by B1's receipt-age contract, not
        # the shorter Safety command watchdog. Zero remains the selected
        # output while this bounded sensor/receipt join is pending.
        max_gap_ns = self.ingress.profile['b1_receipt_max_age_ms'] * 1_000_000
        armed_ns = self.now()
        adapter.arm_reset_scan_boundary(target_ns)
        self.emit('RESET_RECEIPT_ALIGNMENT_ARMED', {'target_scan_ns': target_ns,
            'failed_cutoff_ns': failed_cutoff_ns, 'armed_steady_ns': armed_ns,
            'freshness_limit_ns': max_gap_ns})
        try:
            scan_pending_logged = False
            def boundary_observed():
                nonlocal scan_pending_logged
                observed_ros = self.ros_now()
                suppressed = adapter._reset_boundary_suppressed_stamp_ns == target_ns
                with self.ingress.lock:
                    scan_seen = target_ns in self.ingress.scans
                if observed_ros > target_ns and suppressed and not scan_seen and not scan_pending_logged:
                    scan_pending_logged = True
                    self.emit('RESET_RECEIPT_ALIGNMENT_BOUNDARY_PENDING', {
                        'target_scan_ns': target_ns, 'suppressed': True,
                        'observed_ros_ns': observed_ros, 'steady_ns': self.now()})
                if observed_ros > target_ns and suppressed and scan_seen:
                    return {'observed_ros_ns': observed_ros, 'scan_seen': True,
                        'suppressed': True, 'steady_ns': self.now()}
                return None

            observed = await self.until(boundary_observed,
                deadline_ns=min(deadline_ns, armed_ns + max_gap_ns),
                phase='reset scan boundary and suppression within final-command timeout')
            suppressed = observed['suppressed']
            with self.ingress.lock:
                scan_seen = target_ns in self.ingress.scans
                receipts = tuple(self.ingress.receipts)
            if not suppressed or not scan_seen:
                self.emit('RESET_RECEIPT_ALIGNMENT_MISSED', {'target_scan_ns': target_ns,
                    'scan_seen': scan_seen, 'suppressed': suppressed,
                    'observed_ros_ns': observed['observed_ros_ns'], 'steady_ns': self.now()})
                return False

            before = [item for item in receipts if item.lifecycle == identity
                and item.source is ReceiptSource.SAFE_STOP and item.publish_stamp_ns < target_ns]
            if not before:
                raise RuntimeError('reset cutoff has no pre-boundary SAFE_STOP receipt')
            receipt = max(before, key=lambda item: item.final_publish_sequence)
            if any(receipt.final_command):
                raise RuntimeError('pre-cutoff reset receipt is not zero')
            def pre_boundary_application():
                # The scan callback can cross the boundary before the paired
                # native status/oracle callbacks have joined in ingress. Keep
                # observing the same pinned receipt within its original
                # freshness budget; never treat a missing or post-cutoff
                # application as proof.
                with self.ingress.lock:
                    current_pairs = tuple(self.ingress.physics_pairs)
                for pair in reversed(current_pairs):
                    if pair.stamp_ns > target_ns:
                        continue
                    candidate = deserialize_message(pair.backend_bytes, SimulationContactState)
                    if (candidate.applied_receipt_valid and not candidate.local_zero_override
                            and candidate.applied_final_publisher_instance_id == receipt.final_publisher_instance_id
                            and candidate.applied_final_publish_sequence == receipt.final_publish_sequence
                            and candidate.applied_physics_iteration == pair.iteration
                            and receipt.publish_stamp_ns <= stamp_ns(candidate.applied_sim_stamp) <= target_ns):
                        return candidate
                return None

            state = await self.until(pre_boundary_application,
                deadline_ns=min(deadline_ns, armed_ns + max_gap_ns,
                    receipt.received_steady_ns + max_gap_ns),
                phase='exact native SAFE_STOP application before reset scan boundary')
            if (self.now() < receipt.received_steady_ns
                    or self.now() - receipt.received_steady_ns > max_gap_ns
                    or target_ns - receipt.publish_stamp_ns > max_gap_ns):
                raise RuntimeError('pre-cutoff reset receipt exceeds 500 ms freshness at scan boundary')

            def post_boundary_receipt_candidate():
                with self.ingress.lock:
                    matches = [item for item in self.ingress.receipts
                        if item.final_publisher_instance_id == receipt.final_publisher_instance_id
                        and item.final_publish_sequence > receipt.final_publish_sequence
                        and item.publish_stamp_ns > target_ns]
                if not matches:
                    return None
                matches.sort(key=lambda item: item.final_publish_sequence)
                candidate = matches[0]
                if (sum(item.final_publish_sequence == candidate.final_publish_sequence
                        for item in matches) != 1
                        or candidate.lifecycle != identity
                        or candidate.source is not ReceiptSource.SAFE_STOP
                        or any(candidate.final_command)):
                    raise RuntimeError('post-cutoff receipt candidate is not the bound zero SAFE_STOP')
                return candidate

            adjacent_deadline = min(deadline_ns, receipt.received_steady_ns + max_gap_ns)
            candidate = await self.until(post_boundary_receipt_candidate, deadline_ns=adjacent_deadline,
                phase='post-cutoff reset SAFE_STOP receipt candidate')
            receive_gap_ns = candidate.received_steady_ns - receipt.received_steady_ns
            if (not 0 <= receive_gap_ns <= max_gap_ns
                    or self.now() < candidate.received_steady_ns
                    or self.now() - candidate.received_steady_ns > max_gap_ns
                    or candidate.publish_stamp_ns - target_ns > max_gap_ns):
                raise RuntimeError('reset SAFE_STOP publication gap exceeded 500 ms freshness')
            self.emit('RESET_RECEIPT_ALIGNMENT_BOUNDARY_CANDIDATE', {'target_scan_ns': target_ns,
                'selected_receipt_sequence': receipt.final_publish_sequence,
                'selected_receipt_stamp_ns': receipt.publish_stamp_ns,
                'selected_application_iteration': state.applied_physics_iteration,
                'selected_application_stamp_ns': stamp_ns(state.applied_sim_stamp),
                'post_boundary_receipt_sequence': candidate.final_publish_sequence,
                'post_boundary_receipt_stamp_ns': candidate.publish_stamp_ns,
                'receipt_receive_gap_ns': receive_gap_ns, 'steady_ns': self.now()})
            return True
        finally:
            if adapter._reset_scan_boundary_stamp_ns == target_ns:
                adapter.cancel_reset_scan_boundary(target_ns)

    @staticmethod
    def _time_msg(ns):
        from builtin_interfaces.msg import Time
        return Time(sec=ns // 10**9, nanosec=ns % 10**9)

    async def bind_final_process(self, ack):
        """Chuyển ACK gốc sang child đã pin boot nonce; chờ xác nhận của child."""
        import os
        record = {'schema': 'b23_final_source_binding/v1', 'run_id': self.descriptor['run_id'],
            'invocation_id': self.descriptor['invocation_id'],
            'final_publisher_instance_id': self.final.publisher_instance_id,
            'request_cdr_hex': ack.request_bytes.hex(), 'response_cdr_hex': ack.response_bytes.hex(),
            'ack_observed_ns': ack.observed_steady_ns}
        raw = json.dumps(record, sort_keys=True, separators=(',', ':')).encode() + b'\n'
        path = Path(self.descriptor['final_binding_path'])
        write_record_once(path, record)
        digest = hashlib.sha256(raw).hexdigest()
        result_path = Path(self.descriptor['final_binding_ack_path'])
        def observed():
            if not result_path.exists():
                return None
            result = json.loads(result_path.read_bytes())
            if (result.get('binding_file_sha256') != digest
                    or result.get('invocation_id') != self.descriptor['invocation_id']
                    or result.get('publisher_instance_id') != self.final.publisher_instance_id
                    or result.get('pid') != self.descriptor['final_publisher_pid']
                    or result.get('source_binding_applied') is not True):
                raise RuntimeError('final publisher binding ACK ownership mismatch')
            return result
        await self.until(observed, deadline_ns=min(self.deadline_ns, self.now() + 1_000_000_000),
                         phase='final source binding ACK')
        self.emit('FINAL_BINDING_CONFIRMED', {'binding_file_sha256': digest, 'steady_ns': self.now()})


    async def freeze_step_streams(self, *, deadline_ns):
        """Giữ native watchdog sống bằng zero SAFE_STOP trước pending step.

        Đóng POLICY trước, nhưng giữ timer/receipt SAFE_STOP chạy khi đang chờ
        bind slot mới. Tắt stream ở đây làm receipt gần nhất quá hạn watchdog.
        """
        from mecanum_nav_rl_interfaces.msg import CommandEnvelope
        adapter = self.safety.local_training
        previous_safe_stop = adapter.safe_stop_sequence
        adapter.set_policy_hold(True)
        adapter.set_stream_enabled(True)
        # Revoke the consumed slot token and let native observe a fresh
        # closing sample before freezing the stream.  Merely pausing here can
        # leave POLICY_OPEN carrying an already-consumed token; native then
        # rejects every later sample and the watermark drain cannot complete.
        await self.inhibit_and_drain(deadline_ns=deadline_ns)
        await self.until(lambda: adapter.last_output
            if adapter.safe_stop_sequence > previous_safe_stop
            and adapter.last_output is not None
            and adapter.last_output.source == CommandEnvelope.SOURCE_SAFE_STOP
            and adapter.last_output.sequence == adapter.safe_stop_sequence else None,
            deadline_ns=deadline_ns, phase='fresh SAFE_STOP before pending policy step')
        last = copy.deepcopy(adapter.last_output)
        await self.freeze_admission(deadline_ns=deadline_ns)
        if last is None:
            raise RuntimeError('step has no actual Safety publication anchor')
        def drained():
            exact = self.final.publication_for_source_sequence(
                source=last.source, sequence=last.sequence)
            if exact is not None:
                return exact
            # The receipt callback can coalesce the exact publication selected
            # above while later SAFE_STOP receipts continue to arrive. Rebind
            # only to an actually retained zero SAFE_STOP receipt from this
            # publisher and lifecycle, issued after the closing SAFE_STOP
            # watermark. The exact native application and current closed state
            # are still required below; this does not infer a receipt from a
            # sequence gap or from the latest backend watermark.
            from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
            from mecanum_nav_rl.runtime_simulation.local_training_ingress import lifecycle_identity
            life = self.ingress.lifecycle
            if life is None:
                return None
            identity = lifecycle_identity(life)
            with self.ingress.lock:
                views = tuple(self.ingress.receipts)
            for view in reversed(views):
                if (view.source is not ReceiptSource.SAFE_STOP
                        or view.final_publisher_instance_id != self.final.publisher_instance_id
                        or view.source_sequence <= previous_safe_stop
                        or view.lifecycle != identity
                        or any(view.final_command)):
                    continue
                candidate = self.final.publication_for_source_sequence(
                    source=CommandEnvelope.SOURCE_SAFE_STOP, sequence=view.source_sequence)
                if candidate is not None:
                    return candidate
            return None
        receipt = await self.until(drained, deadline_ns=deadline_ns, phase='Final SAFE_STOP publication drain')
        def applied_and_closed():
            application = self.ingress.application_for_receipt(receipt)
            state = self.ingress.backend_state
            if (application is None or state is None or state.fault_flags != 0 or state.paused):
                return None
            # The selected exact receipt may be followed by other zero samples
            # before this coroutine wakes. Accept retained application for the
            # selected key only while the current backend status still proves
            # motion is closed: emergency zero, or a later SAFE_STOP zero.
            if state.local_zero_override:
                return application
            if (not state.applied_receipt_valid
                    or state.applied_final_publisher_instance_id != self.final.publisher_instance_id
                    or state.applied_final_publish_sequence < receipt.final_publish_sequence):
                return None
            current_receipt = self.ingress.receipt_for_publication_sequence(
                state.applied_final_publish_sequence)
            from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
            if (current_receipt is None or current_receipt.source is not ReceiptSource.SAFE_STOP
                    or current_receipt.final_publisher_instance_id != self.final.publisher_instance_id
                    or any(current_receipt.final_command)):
                return None
            return application

        application = await self.until(applied_and_closed,
            deadline_ns=deadline_ns, phase='SAFE_STOP application before pending step')
        applied_state = application['state']
        self.emit('STEP_STREAMS_FROZEN', {'source': receipt.source, 'source_sequence': receipt.sequence,
            'publish_sequence': receipt.final_publish_sequence, 'watchdog_zero_stream_active': True,
            'application_iteration': applied_state.applied_physics_iteration,
            'application_stamp_ns': (applied_state.applied_sim_stamp.sec * 1_000_000_000
                + applied_state.applied_sim_stamp.nanosec),
            'application_received_ns': application['received_ns'],
            'steady_ns': self.now()})
        return {'receipt': receipt, 'state': applied_state,
            'received_ns': application['received_ns']}

    async def wait_r09b_restored_scan_zero_before_bind(self, *, deadline_ns):
        """Wait for a post-restore clear scan and drain its applied SAFE_STOP.

        Moving the task fixture can leave a real obstacle return in one or more
        lidar samples after the covered-empty contact status arrives. Binding a
        POLICY slot during that interval lets Safety correctly publish zero;
        that zero revokes the pending admission. Wait for Safety's own tick to
        evaluate a newer clear scan, then join its exact zero receipt before
        freezing the output stream and binding the slot.
        """
        from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import stamp_ns

        adapter = self.safety.local_training
        restored = self.ingress.backend_state
        if (restored is None or restored.fault_flags != 0 or restored.paused
                or restored.contact_active or not restored.coverage_complete
                or not restored.contact_source_healthy
                or restored.backend_instance_id != self.descriptor['backend_instance_id']
                or restored.session_id != self.descriptor['session_id']
                or restored.config_hash != self.descriptor['config_hash']):
            raise RuntimeError('R09b restored fixture status is not a healthy bound observation')
        restored_sequence = int(restored.status_sequence)
        restored_stamp_ns = stamp_ns(restored.header.stamp)
        event_floor = len(self.events)
        allowed_wait_reasons = {
            'COMMAND_MISSING', 'POLICY_HELD', 'NOISY_OR_ADMISSION_NOT_VALID',
            'LIMITER_PRIMED',
        }

        def clear_safety_tick():
            status = self.ingress.backend_state
            scan = adapter.scan
            life = adapter.life
            if (status is None or status.status_sequence <= restored_sequence
                    or status.fault_flags != 0 or status.paused or status.contact_active
                    or not status.coverage_complete or not status.contact_source_healthy
                    or status.backend_instance_id != self.descriptor['backend_instance_id']
                    or status.session_id != self.descriptor['session_id']
                    or status.config_hash != self.descriptor['config_hash']
                    or scan is None or adapter.stamp(scan.header.stamp) <= restored_stamp_ns
                    or life is None or adapter.identity(status) != adapter.identity(life)):
                return None
            event = next((facts for name, facts in reversed(self.events[event_floor:])
                if name == 'SAFETY_REJECTED'
                and facts.get('source') == 4
                and facts.get('ros_ns', 0) >= adapter.stamp(scan.header.stamp)
                and not (set(facts.get('reasons', ())) - allowed_wait_reasons)), None)
            if event is None:
                return None
            return event, scan, status

        event, scan, status = await self.until(clear_safety_tick,
            deadline_ns=deadline_ns,
            phase='R09b post-restore scan clear and Safety zero tick')
        receipt = await self.until(lambda: self.final.publication_for_source_sequence(
            source=FinalIssuedCommandReceipt.SOURCE_SAFE_STOP,
            sequence=event['sequence']), deadline_ns=deadline_ns,
            phase='R09b exact post-clear SAFE_STOP receipt')
        if (receipt is None or receipt.final_publisher_instance_id != self.final.publisher_instance_id
                or any((receipt.final_command.linear.x, receipt.final_command.linear.y,
                    receipt.final_command.angular.z))):
            raise RuntimeError('R09b post-clear Safety tick lacks its exact zero receipt')

        def exact_application():
            application = self.ingress.application_for_receipt(receipt)
            if application is None:
                return None
            applied = application.get('state')
            if (applied is None or applied.fault_flags != 0 or applied.paused
                    or applied.local_zero_override or not applied.applied_receipt_valid
                    or applied.applied_final_publisher_instance_id != receipt.final_publisher_instance_id
                    or applied.applied_final_publish_sequence != receipt.final_publish_sequence
                    or applied.backend_instance_id != self.descriptor['backend_instance_id']
                    or applied.session_id != self.descriptor['session_id']
                    or applied.config_hash != self.descriptor['config_hash']):
                return None
            return application

        application = await self.until(exact_application, deadline_ns=deadline_ns,
            phase='R09b exact post-clear zero application')
        self.emit('R09B_STOPPING_ENVELOPE_CLEAR_ZERO_APPLIED', {
            'restored_status_sequence': restored_sequence,
            'restored_stamp_ns': restored_stamp_ns,
            'clear_scan_stamp_ns': adapter.stamp(scan.header.stamp),
            'clear_scan_received_ns': int(adapter.scan_received),
            'safe_stop_sequence': int(event['sequence']),
            'publish_sequence': int(receipt.final_publish_sequence),
            'application_iteration': int(application['state'].applied_physics_iteration),
            'application_stamp_ns': stamp_ns(application['state'].applied_sim_stamp),
            'application_received_ns': int(application['received_ns']),
            'steady_ns': self.now()})
        return receipt, application['state'], application['received_ns']

    async def align_policy_step_launch_window(self, *, deadline_ns, zero_witness):
        """Giữ SAFE_STOP sống nếu bind muộn trong scan period.

        Sau khi bind slot, SAFE_STOP mới sẽ thu hồi admission. Vì vậy chỉ
        chuyển sang BIND_PENDING_STEP ở một cửa sổ còn đủ thời gian cho ACK,
        mẫu admission và receipt POLICY trước scan cutoff kế tiếp. Nếu đang
        sát cutoff, chờ SAFE_STOP post-cutoff có đủ cửa sổ và xác nhận receipt
        đã vào native trước khi bind. `zero_witness` tiếp tục là bằng chứng
        riêng về SAFE_STOP đã được apply; receipt mới được xếp trước bind để
        native drain nó mà không thu hồi slot mới.
        """
        from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
        from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import lifecycle_identity
        adapter = self.safety.local_training
        period_ns = adapter.scan_period_ns
        now_ros_ns = self.ros_now()
        # Safety defers a normal tick stamped exactly on a cutoff. Treat that
        # instant as the closed edge of the current window, not as a fresh
        # full period; only a strictly post-cutoff tick opens the next window.
        remaining_ns = policy_bind_launch_window_remaining_ns(now_ros_ns, period_ns)
        # Keep bind/sample processing away from the 100 ms edge: the 40-60 ms
        # band was selected from the observed bind, post-ACK sample, and
        # deferred-tick timings. It changes scheduling only, not any contract
        # freshness, scan-gap, cutoff, or native watchdog limit.
        if policy_bind_launch_window_ready(remaining_ns):
            return zero_witness

        target_cutoff_ns = now_ros_ns + remaining_ns
        baseline = max((receipt.final_publish_sequence for receipt in self.ingress.receipts
            if receipt.final_publisher_instance_id == self.final.publisher_instance_id
            and receipt.source is ReceiptSource.SAFE_STOP), default=0)

        life = self.ingress.lifecycle
        if life is None:
            raise RuntimeError('cannot align POLICY bind without a current lifecycle identity')
        expected_lifecycle = lifecycle_identity(life)

        def fresh_received_zero_after_cutoff_with_window():
            state = self.ingress.backend_state
            if state is None or state.fault_flags != 0 or state.paused:
                return None
            for receipt in reversed(tuple(self.ingress.receipts)):
                if (receipt.final_publish_sequence <= baseline
                        or receipt.source is not ReceiptSource.SAFE_STOP
                        or receipt.final_publisher_instance_id != self.final.publisher_instance_id
                        or receipt.lifecycle != expected_lifecycle
                        or receipt.session_id != self.descriptor['session_id']
                        or receipt.ingress_config_hash != self.descriptor['config_hash']
                        or receipt.frame_id != 'base_link'
                        or not receipt.admission_valid
                        or receipt.publish_stamp_ns <= target_cutoff_ns
                        or any(receipt.final_command)):
                    continue
                phase = receipt.publish_stamp_ns % period_ns
                remaining_to_cutoff = period_ns - phase if phase else 0
                if not policy_bind_launch_window_ready(remaining_to_cutoff):
                    continue
                current_ros_ns = self.ros_now()
                current_remaining_ns = policy_bind_launch_window_remaining_ns(
                    current_ros_ns, period_ns)
                if not policy_bind_launch_window_ready(current_remaining_ns):
                    continue
                publication = self.final.publication_for_source_sequence(
                    source=FinalIssuedCommandReceipt.SOURCE_SAFE_STOP,
                    sequence=receipt.source_sequence)
                if (publication is None
                        or publication.final_publisher_instance_id != receipt.final_publisher_instance_id
                        or publication.final_publish_sequence != receipt.final_publish_sequence
                        or publication.source != FinalIssuedCommandReceipt.SOURCE_SAFE_STOP
                        or any((publication.final_command.linear.x,
                            publication.final_command.linear.y, publication.final_command.angular.z))):
                    continue

                # Python receipt subscription proves the publication bytes;
                # only the backend's flushed event proves that the native
                # receipt callback queued this exact key before the bind RPC.
                self.read_native_input_watermark()
                native_key = (str(receipt.final_publisher_instance_id),
                    str(receipt.final_publish_sequence), str(receipt.source_sequence),
                    str(receipt.publish_stamp_ns))
                native_ingress = getattr(self, '_native_safe_stop_ingress', {}).get(native_key)
                if native_ingress is None:
                    continue
                try:
                    native_receive_ns = int(native_ingress['fields']['receive_ns'])
                except (KeyError, TypeError, ValueError):
                    continue
                if native_receive_ns <= 0:
                    continue
                return {'receipt':receipt, 'publication':publication,
                    'native_ingress':native_ingress, 'native_receive_ns':native_receive_ns,
                    'remaining_to_cutoff_ns':current_remaining_ns}
            return None

        aligned = await self.until(fresh_received_zero_after_cutoff_with_window,
            deadline_ns=deadline_ns,
            phase='post-cutoff native SAFE_STOP ingress with POLICY bind window')
        self.emit('POLICY_STEP_BIND_WINDOW_ALIGNED_AFTER_SCAN_CUTOFF', {
            'target_cutoff_ns':target_cutoff_ns,
            'zero_publish_sequence':aligned['receipt'].final_publish_sequence,
            'zero_publish_stamp_ns':aligned['receipt'].publish_stamp_ns,
            'zero_received_steady_ns':aligned['receipt'].received_steady_ns,
            'native_receive_ns':aligned['native_receive_ns'],
            'native_ingress_event':aligned['native_ingress'],
            'prior_applied_zero_sequence':zero_witness['receipt'].final_publish_sequence,
            'prior_applied_zero_received_ns':zero_witness['received_ns'],
            'remaining_to_cutoff_ns':aligned['remaining_to_cutoff_ns'],
            'remaining_to_next_cutoff_ns':period_ns - (self.ros_now() % period_ns),
            'steady_ns':self.now()})
        # Keep the earlier exact application witness. The staged post-cutoff
        # zero is proven received by native, but has not been claimed applied.
        return zero_witness

    async def refresh_zero_before_pending_bind(self, *, deadline_ns):
        """Require a newly applied SAFE_STOP immediately before binding POLICY.

        The native actuator watchdog is steady-clock based. Scan-window
        alignment can otherwise leave the last applied zero several timer
        ticks behind the pending-step ACK and its first eligible post-ACK
        odometry sample. Keep POLICY held, wait for the real Safety timer to
        publish another zero, and bind only after that exact receipt has an
        exact native application in the same session/lifecycle.
        """
        from mecanum_nav_rl_interfaces.msg import CommandEnvelope
        from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import lifecycle_identity

        adapter = self.safety.local_training
        baseline_sequence = adapter.safe_stop_sequence
        life = self.ingress.lifecycle
        if life is None:
            raise RuntimeError('cannot refresh pre-bind zero without lifecycle identity')
        expected_lifecycle = lifecycle_identity(life)

        def newly_applied_zero():
            state = self.ingress.backend_state
            if (state is None or state.fault_flags != 0 or state.paused
                    or state.local_zero_override
                    or state.session_id != self.descriptor['session_id']
                    or state.config_hash != self.descriptor['config_hash']
                    or state.backend_instance_id != self.descriptor['backend_instance_id']
                    or lifecycle_identity(state) != expected_lifecycle):
                return None
            for receipt in reversed(tuple(self.ingress.receipts)):
                if (receipt.source is not ReceiptSource.SAFE_STOP
                        or receipt.source_instance_id != self.ingress.safe_stop_source_id
                        or receipt.source_sequence <= baseline_sequence
                        or receipt.step_index != 0 or receipt.transition_id
                        or receipt.final_publisher_instance_id != self.final.publisher_instance_id
                        or receipt.lifecycle != expected_lifecycle
                        or receipt.session_id != self.descriptor['session_id']
                        or receipt.ingress_config_hash != self.descriptor['config_hash']
                        or receipt.frame_id != 'base_link'
                        or not receipt.admission_valid
                        or any(receipt.final_command)):
                    continue
                publication = self.final.publication_for_source_sequence(
                    source=CommandEnvelope.SOURCE_SAFE_STOP,
                    sequence=receipt.source_sequence)
                if (publication is None
                        or publication.final_publisher_instance_id != receipt.final_publisher_instance_id
                        or publication.final_publish_sequence != receipt.final_publish_sequence
                        or publication.source != CommandEnvelope.SOURCE_SAFE_STOP
                        or publication.sequence != receipt.source_sequence
                        or any((publication.final_command.linear.x,
                            publication.final_command.linear.y, publication.final_command.angular.z))):
                    continue
                application = self.ingress.application_for_receipt(receipt)
                if application is None:
                    continue
                applied_state = application['state']
                if (state.applied_final_publisher_instance_id != self.final.publisher_instance_id
                        or state.applied_final_publish_sequence < receipt.final_publish_sequence
                        or not state.applied_receipt_valid):
                    continue
                current_receipt = self.ingress.receipt_for_publication_sequence(
                    state.applied_final_publish_sequence)
                if (current_receipt is None
                        or current_receipt.source is not ReceiptSource.SAFE_STOP
                        or current_receipt.final_publisher_instance_id != self.final.publisher_instance_id
                        or any(current_receipt.final_command)
                        or applied_state.fault_flags != 0
                        or applied_state.paused
                        or applied_state.local_zero_override
                        or applied_state.session_id != self.descriptor['session_id']
                        or applied_state.config_hash != self.descriptor['config_hash']
                        or applied_state.backend_instance_id != self.descriptor['backend_instance_id']
                        or lifecycle_identity(applied_state) != expected_lifecycle
                        or applied_state.applied_final_publish_sequence != receipt.final_publish_sequence
                        or applied_state.applied_final_publisher_instance_id != self.final.publisher_instance_id):
                    continue
                age_ns = self.now() - receipt.received_steady_ns
                if age_ns < 0 or age_ns > 100_000_000:
                    continue
                return {'receipt': receipt, 'publication': publication,
                    'application': application, 'age_ns': age_ns}
            return None

        refreshed = await self.until(newly_applied_zero, deadline_ns=deadline_ns,
            phase='new exact SAFE_STOP application before pending POLICY bind')
        self.emit('POLICY_STEP_BIND_ZERO_REFRESH_APPLIED', {
            'baseline_safe_stop_sequence': baseline_sequence,
            'source_sequence': refreshed['receipt'].source_sequence,
            'final_publish_sequence': refreshed['receipt'].final_publish_sequence,
            'native_iteration': refreshed['application']['state'].applied_physics_iteration,
            'native_stamp_ns': (refreshed['application']['state'].applied_sim_stamp.sec
                * 1_000_000_000 + refreshed['application']['state'].applied_sim_stamp.nanosec),
            'receipt_received_steady_ns': refreshed['receipt'].received_steady_ns,
            'receipt_age_ns': refreshed['age_ns'],
            'deadline_ns': deadline_ns,
            'steady_ns': self.now(),
        })
        return refreshed

    async def tick_policy_after_deferred_scan_cutoff(self, *, deadline_ns,
            step_index, sample_sequence):
        """Retry the same Safety tick at the first post-cutoff physics time.

        A pending POLICY slot cannot be refreshed with SAFE_STOP without
        revoking its admission. If the immediate, fully validated Safety tick
        lands on a scan cutoff, do not wait for the next 50 ms executor timer:
        wait for ROS time to cross that exact boundary, then invoke the same
        production tick under its lock. The tick still owns all freshness,
        limiter, identity, and fail-safe decisions.
        """
        adapter = self.safety.local_training
        previous_tick_ros_ns = adapter.last_tick_ros_ns
        ready_ros_ns = self.ros_now()
        self.emit('POLICY_READY_IMMEDIATE_SAFETY_TICK', {
            'step_index': step_index,
            'sample_sequence': sample_sequence,
            'steady_ns': self.now(),
            'ros_ns': ready_ros_ns,
        })
        adapter.tick()
        boundary_ns = getattr(adapter, '_last_deferred_scan_cutoff_ns', None)
        if (adapter.last_tick_ros_ns != previous_tick_ros_ns
                or type(boundary_ns) is not int):
            return

        def crossed_boundary():
            current_ros_ns = self.ros_now()
            return current_ros_ns if current_ros_ns > boundary_ns else None

        if ready_ros_ns > boundary_ns:
            crossed_ros_ns = ready_ros_ns
        else:
            crossed_ros_ns = await self.until(
                crossed_boundary,
                deadline_ns=deadline_ns,
                phase='post-cutoff physics time for immediate POLICY Safety tick')
        with adapter.lock:
            tick_before_retry_ros_ns = adapter.last_tick_ros_ns
            if (tick_before_retry_ros_ns is None
                    or tick_before_retry_ros_ns <= boundary_ns):
                adapter.tick()
            tick_after_retry_ros_ns = adapter.last_tick_ros_ns
        self.emit('POLICY_SAFETY_TICK_RETRIED_AFTER_SCAN_CUTOFF', {
            'step_index': step_index,
            'boundary_ns': boundary_ns,
            'crossed_ros_ns': crossed_ros_ns,
            'tick_before_retry_ros_ns': tick_before_retry_ros_ns,
            'tick_after_retry_ros_ns': tick_after_retry_ros_ns,
            'retry_performed': (tick_before_retry_ros_ns is None
                or tick_before_retry_ros_ns <= boundary_ns),
            'steady_ns': self.now(),
        })

    async def replay_pause_intent_after_terminal(self):
        """Gửi lại đúng bytes pause đã APPLIED sau reset terminal; không tạo request mới."""
        if self.pause_ack is None:
            raise RuntimeError('pause replay requires the exact retained APPLIED request')
        original = self.pause_ack
        replayed = await self.control.replay(original, deadline_ns=min(
            self.deadline_ns, self.now() + 1_000_000_000))
        from rosidl_runtime_py.convert import message_to_ordereddict
        original_response, replayed_response = original.response, replayed.response
        semantic_response_match = (
            message_to_ordereddict(original_response) == message_to_ordereddict(replayed_response))
        if replayed.request_bytes != original.request_bytes or not semantic_response_match:
            raise RuntimeError('terminal pause replay request or semantic response differs from retained transaction')
        self.emit('PAUSE_INTENT_EXACT_REPLAY_AFTER_TERMINAL', {
            'request_sequence': original.request.request_sequence,
            'request_cdr_hex': original.request_bytes.hex(),
            'original_response_cdr_hex': original.response_bytes.hex(),
            'response_cdr_hex': replayed.response_bytes.hex(),
            'original_response_semantic': message_to_ordereddict(original_response),
            'replay_response_semantic': message_to_ordereddict(replayed_response),
            'original_applied_ns': original.observed_steady_ns,
            'replay_observed_ns': replayed.observed_steady_ns,
            'exact_request_bytes': True,
            'semantic_response_match': True,
        })
        return replayed

    async def policy_step(self, b1, action, *, hold_after_adapter_issuance=False,
                          close_after_held_receipt=None, prebind_admission=False,
                          measurement_fault_case=None,
                          align_admission_after_scan_boundary=False,
                          require_admission_before_receipt=False,
                          after_policy_applied=None,
                          before_pending_bind=None):
        """Một issuance thật qua Safety, application thật rồi transaction B1."""
        from mecanum_nav_rl_interfaces.msg import CommandEnvelope, LocalTrainingSafetyInput
        from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
        from mecanum_nav_rl.runtime_simulation.local_training_coordinator import B1SnapshotPending
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import stamp_ns
        if (not isinstance(action, (tuple, list)) or len(action) != 3
                or any(type(v) not in (float, int) or not math.isfinite(v) or not -1 <= v <= 1 for v in action)):
            raise ValueError('action requires three finite normalized values in [-1, 1]')
        started = self.now()
        deadline = min(self.deadline_ns, started + 2_000_000_000)
        held_prebind = None
        previous_pending_ack = None
        if prebind_admission:
            if self.ingress.pending_ack is None or self.ingress.admission_state != LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN:
                raise RuntimeError('R02e needs a live previous pending token before rebinding')
            previous_pending_ack = self.ingress.pending_ack
        zero_witness = await self.freeze_step_streams(deadline_ns=deadline)
        r02b_cutoff_evidence = None
        if align_admission_after_scan_boundary:
            adapter = self.safety.local_training
            cutoff_ns = r02b_admission_release_target_ns(
                self.ros_now(), adapter.scan_period_ns)

            def observed_post_cutoff_tick():
                ros_ns = self.ros_now()
                tick_ros_ns = adapter.last_tick_ros_ns
                if (ros_ns > cutoff_ns and tick_ros_ns is not None
                        and tick_ros_ns > cutoff_ns):
                    return {'cutoff_ns': cutoff_ns, 'ros_ns': ros_ns,
                        'safety_tick_ros_ns': tick_ros_ns,
                        'steady_ns': self.now()}
                return None

            r02b_cutoff_evidence = await self.until(observed_post_cutoff_tick,
                deadline_ns=deadline,
                phase='R02b Safety tick after scan cutoff before pending bind')
        if measurement_fault_case is not None:
            self._r04_fault_state = install_r04_delivery_fault(
                self.safety.local_training, measurement_fault_case, self.emit)
            self.emit('B23_R04_FAULT_ARMED', {'case':measurement_fault_case,
                'step_deadline_ns':deadline, 'steady_ns':self.now()})
        # Begin the pending transaction immediately after the exact SAFE_STOP
        # application above. Waiting for another scan boundary can place the
        # first eligible Safety tick on that cutoff: it is correctly deferred,
        # while the pending slot forbids a closing SAFE_STOP and the native
        # 100 ms command watchdog continues to run. The publisher and Safety
        # keep their existing scan-cutoff and freshness checks.
        if before_pending_bind is None:
            # R02c/R02d deliberately hold the first POLICY receipt until a
            # closing input reaches native. Their bounded fault window must
            # start from the fresh zero already proven above; an additional
            # scan-boundary alignment here can consume the remaining 100 ms
            # native watchdog budget before the held receipt can be released.
            # Normal POLICY transactions retain the launch-window alignment.
            if not prebind_admission and close_after_held_receipt is None:
                zero_witness = await self.align_policy_step_launch_window(
                    deadline_ns=deadline, zero_witness=zero_witness)
                zero_witness = await self.refresh_zero_before_pending_bind(
                    deadline_ns=deadline)
            self.safety.local_training.set_stream_enabled(False)
        if prebind_admission:
            # Build the held input after native has observed the closing
            # inhibited sample, but before binding the new slot. This keeps
            # its real producer sequence monotonic at the consumer while its
            # token and measurement still belong to the previous slot.
            with self.ingress.lock:
                if (self.ingress.pending_ack is not None
                        or self.ingress.admission_state != LocalTrainingSafetyInput.ADMISSION_INHIBITED):
                    raise RuntimeError('R02e old slot was not closed before constructing the held sample')
                candidates = tuple(self.ingress.noisy_samples.values())
                if not candidates:
                    raise RuntimeError('R02e has no actual noisy sample to carry across the bind')
                sample = candidates[-1]
                closed_sample_sequence = self.ingress.last_published_sample_sequence
                old_state = self.ingress.admission_state
                old_ack = self.ingress.pending_ack
                old_enabled = self.ingress.admission_publication_enabled
                self.ingress.pending_ack = previous_pending_ack
                self.ingress.admission_state = LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN
                self.ingress.admission_publication_enabled = True
                self._hold_next_safety_input = True
                try:
                    self.ingress._publish_safety(sample)
                finally:
                    self.ingress.pending_ack = old_ack
                    self.ingress.admission_state = old_state
                    self.ingress.admission_publication_enabled = old_enabled
                    if self._held_safety_input is None:
                        self._hold_next_safety_input = False
            held_prebind = self._held_safety_input
            if (held_prebind is None
                    or held_prebind.admission_state != LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN
                    or not any(held_prebind.admission_token)
                    or held_prebind.sample_sequence <= closed_sample_sequence):
                raise RuntimeError('R02e held sample is not a fresh monotonic prior-token POLICY admission')
            self.emit('R02E_PREBIND_SAMPLE_HELD_AFTER_CLOSE', {
                'closed_sample_sequence': closed_sample_sequence,
                'held_sample_sequence': held_prebind.sample_sequence,
                'previous_request_sequence': previous_pending_ack.request.request_sequence,
                'steady_ns': self.now()})
        # A SAFE_STOP arriving after OP_BIND_PENDING_STEP revokes the pending
        # admission by contract. The last zero receipt above is already native
        # applied, so stop emitting zero while this single slot is bound; native
        # zero remains in force until Safety publishes the admitted POLICY.
        token = b1.begin_step()
        barrier = self.ros_now()
        if barrier <= stamp_ns(self.ingress.lifecycle.barrier_stamp):
            raise RuntimeError('action barrier is not after authoritative lifecycle barrier')
        if before_pending_bind is not None:
            if not callable(before_pending_bind):
                raise TypeError('before_pending_bind must be callable')
            # Perform R09b fixture contact while SAFE_STOP receipts can still
            # refresh the native watchdog. The B1 step and barrier already
            # exist; contact remains in this transition's exact physics history.
            await before_pending_bind(deadline, token, barrier, zero_witness)
        if before_pending_bind is not None:
            await self.wait_r09b_restored_scan_zero_before_bind(deadline_ns=deadline)
            self.safety.local_training.set_stream_enabled(False)
        ack = await self.control.transact(Control.Request.OP_BIND_PENDING_STEP,
            deadline_ns=deadline, pending_step_index=token.step_index,
            pending_source_sequence=token.step_index, pending_transition_id=token.transition_id,
            action_barrier_stamp=self._time_msg(barrier))
        # Pin the producer watermark at the ACK boundary. The first valid
        # admission can arrive while the POLICY candidate is being delivered
        # to Safety; taking this watermark after that delivery would discard
        # that already post-ACK sample and wait for another sensor period.
        post_ack_floor = self.ingress.last_published_sample_sequence
        self.ingress.arm_pending(ack, publish_admission=held_prebind is None)
        # Stage the bound POLICY candidate while the stream remains closed.
        # Waiting for the first post-ACK admission sample before publishing
        # the candidate can consume the native 100 ms receipt watchdog window:
        # the sample is valid only after ACK, but the command itself is already
        # authorized by the applied pending-step binding. Safety still cannot
        # publish it until the matching fresh admission arrives and the stream
        # is enabled below.
        life = self.ingress.lifecycle
        envelope = CommandEnvelope()
        envelope.header.frame_id, envelope.header.stamp = 'base_link', self._time_msg(self.ros_now())
        envelope.source, envelope.source_instance_id, envelope.sequence = (
            envelope.SOURCE_POLICY, self.policy_source_id, token.step_index)
        envelope.episode_generation, envelope.reset_epoch, envelope.runtime_generation = (
            life.episode_generation, life.reset_epoch, life.runtime_generation)
        scales = self.document['training']['local_training']
        envelope.twist.linear.x = float(action[0]) * scales['max_vx_mps']
        envelope.twist.linear.y = float(action[1]) * scales['max_vy_mps']
        envelope.twist.angular.z = float(action[2]) * scales['max_wz_radps']
        self.policy_publisher.publish(envelope)
        b1.record_issuance(envelope, action_barrier_ns=barrier)
        await self.until(lambda: self.safety.local_training.command if self.safety.local_training.command is not None
            and self.safety.local_training.command.sequence == token.step_index
            and self.safety.local_training.command.source_instance_id == self.policy_source_id else None,
            deadline_ns=deadline, phase='actual adapter issuance delivered to Safety')
        if align_admission_after_scan_boundary:
            # Safety already consumed the upcoming scan cutoff while no new
            # slot was bound. Now hold only the native admission delivery
            # until the actual post-ACK sample reaches Safety.
            self.ingress.pause_admission_publication()
            adapter = self.safety.local_training
            prior_sample_sequence = self.ingress.last_published_sample_sequence
            self.ingress.admission_publication_enabled = True
            aligned_sample = await self.until(lambda: adapter.noisy
                if adapter.noisy is not None
                and adapter.noisy.sample_sequence > prior_sample_sequence
                and adapter.noisy.admission_state == LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN
                and bytes(adapter.noisy.admission_token) == bytes(ack.response.pending_admission_token)
                and self.ingress.last_published_sample_sequence == adapter.noisy.sample_sequence
                else None,
                deadline_ns=deadline,
                phase='R02b aligned post-cutoff admission reaches Safety')
            self.emit('R02B_ADMISSION_RELEASE_ALIGNED', {
                **r02b_cutoff_evidence,
                'sample_sequence': aligned_sample.sample_sequence,
                'sample_stamp_ns': self.safety.local_training.stamp(aligned_sample.header.stamp),
                'admission_ready_steady_ns': self.now()})
            self.ingress.pause_admission_publication()
            target_sample_sequence = aligned_sample.sample_sequence
        held_sample_sequence = None
        if held_prebind is not None:
            held_sample_sequence = held_prebind.sample_sequence
            await self.release_r02e_prebind_input_before_admission(
                held_sample=held_prebind, ack=ack, deadline_ns=deadline)
        if not align_admission_after_scan_boundary:
            await self.until(lambda: self.ingress.last_published_sample_sequence
                if (self.ingress.last_published_sample_sequence > post_ack_floor
                    and self.ingress.last_published_admission_state
                        == LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN) else None,
                deadline_ns=deadline, phase='first post-ACK admission publication')
            # Freeze on one exact producer sequence; otherwise faster sensor
            # callbacks can keep advancing the ingress target while the Safety
            # callback is receiving the previous valid message.
            self.ingress.pause_admission_publication()
            target_sample_sequence = self.ingress.last_published_sample_sequence
            self.emit('POST_ACK_ADMISSION_FROZEN', {
                'sample_sequence': target_sample_sequence,
                'steady_ns': self.now()})
        await self.until(lambda: self.safety.local_training.noisy if self.safety.local_training.noisy is not None
            and self.safety.local_training.noisy.sample_sequence == target_sample_sequence
            and self.safety.local_training.noisy.admission_state == LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN
            and bytes(self.safety.local_training.noisy.admission_token) == bytes(ack.response.pending_admission_token)
            and self.ingress.last_published_sample_sequence == target_sample_sequence
            else None, deadline_ns=deadline, phase='post-ACK admission delivered to Safety')
        if require_admission_before_receipt:
            admission_row = await self.wait_r02a_native_admission(
                sample_sequence=target_sample_sequence,
                step_started_ns=started, deadline_ns=deadline)
            native_rows = complete_jsonl_rows(self.descriptor['native_events_path'])
            receipt_before_release = next((row for row in native_rows
                if row.get('kind') == 'B23_POLICY_RECEIPT_INGRESS'
                and row.get('fields', {}).get('step') == str(token.step_index)
                and int(row.get('fields', {}).get('receive_ns', '0')) >= started), None)
            if receipt_before_release is not None:
                raise RuntimeError('R02a POLICY receipt reached native before admission was accepted')
            self.emit('R02A_ADMISSION_ACCEPTED_BEFORE_POLICY_STREAM', {
                'sample_sequence':target_sample_sequence,
                'admission_receive_ns':int(admission_row['fields']['receive_ns']),
                'admission_processed_ns':int(admission_row['fields']['processed_ns']),
                'step_started_ns':started, 'steady_ns':self.now()})
        prebind_check = None
        if held_sample_sequence is not None:
            fresh_sample_sequence = self.ingress.last_published_sample_sequence
            current_input = self.safety.local_training.noisy
            if current_input is None or current_input.sample_sequence != fresh_sample_sequence:
                raise RuntimeError('R02e fresh Safety input changed before native evidence wait')
            # Stop advancing the sample target while the asynchronous native
            # stdout collector records the acceptance event for this exact input.
            self.ingress.pause_admission_publication()
            prebind_check = await self.wait_r02e_native_admission(
                held_sample_sequence=held_sample_sequence,
                fresh_sample_sequence=fresh_sample_sequence,
                pending_token=ack.response.pending_admission_token,
                deadline_ns=deadline)
            self.emit('R02E_PREBIND_ADMISSION_REJECTED_AND_FRESH_ACCEPTED', {
                **prebind_check,
                'prior_token_sha256': hashlib.sha256(bytes(held_prebind.admission_token)).hexdigest(),
                'pending_token_sha256': hashlib.sha256(bytes(ack.response.pending_admission_token)).hexdigest(),
                'steady_ns': self.now()})
            self._last_prebind_check = prebind_check
        if close_after_held_receipt is not None:
            if close_after_held_receipt not in ('safe_stop', 'admission_inhibited'):
                raise ValueError('unsupported R02 close trigger')
            # The pending slot is admitted, but Safety's timer was held off
            # during bind/sample delivery so no SAFE_STOP can revoke it. Now
            # allow the real timer to publish POLICY; native captures that
            # receipt before the case-specific close condition is injected.
            self.safety.local_training.set_policy_hold(False)
            self.safety.local_training.set_stream_enabled(True)
            policy_receipt = await self.until(lambda: self.final.publication_for_source_sequence(
                source=CommandEnvelope.SOURCE_POLICY, sequence=token.step_index),
                deadline_ns=deadline, phase='actual held POLICY publication receipt')
            expected_mode = ('hold_policy_until_safe_stop' if close_after_held_receipt == 'safe_stop'
                else 'hold_policy_until_inhibit')
            def held_row():
                rows = complete_jsonl_rows(self.descriptor['native_events_path'])
                return next((row for row in rows if row.get('kind') == 'B23_POLICY_RECEIPT_HELD'
                    and row.get('fields', {}).get('mode') == expected_mode
                    and row.get('fields', {}).get('sequence') == str(policy_receipt.final_publish_sequence)
                    and row.get('fields', {}).get('source_sequence') == str(token.step_index)), None)
            await self.until(held_row, deadline_ns=deadline,
                phase='native held exact final POLICY receipt')
            self.safety.local_training.set_policy_hold(True)
            self.safety.local_training.set_stream_enabled(True)
            self.ingress.inhibit()
            expected_reason = close_after_held_receipt
            def released_row():
                rows = complete_jsonl_rows(self.descriptor['native_events_path'])
                return next((row for row in rows
                    if row.get('kind') == 'B23_POLICY_RECEIPT_RELEASED_AFTER_CLOSE'
                    and row.get('fields', {}).get('reason') == expected_reason
                    and row.get('fields', {}).get('sequence') == str(policy_receipt.final_publish_sequence)), None)
            native_fault = await await_r02_late_receipt_close(
                self, release_predicate=released_row, deadline_ns=deadline)
            checked = verify_r02_late_receipt_rejected(self, case=(
                'R02c' if close_after_held_receipt == 'safe_stop' else 'R02d'),
                step_index=token.step_index, receipt=policy_receipt)
            aborted = b1.lifecycle.abort_step('R02_late_policy_receipt_after_close')
            self.emit('R02_LATE_POLICY_RECEIPT_REJECTED', {
                **checked, 'native_fault_flags':native_fault.fault_flags,
                'b1_abort_status':str(aborted.status), 'steady_ns':self.now()})
            return {'expected_rejection':True, 'policy_issued':True, **checked,
                'b1_step_aborted':True, 'transition_id':token.transition_id}
        if hold_after_adapter_issuance:
            # The packet hook is armed only after the production adapter has
            # issued POLICY and Safety has received that exact candidate. Keep
            # POLICY held while the real timer evaluates it; do not publish a
            # fabricated rejection or count a backend/B1 step.
            safe_stop_sequence_before = self.safety.local_training.safe_stop_sequence
            self.safety.local_training.set_policy_hold(True)
            self.safety.local_training.set_stream_enabled(True)
            self.emit('FAULT_HOOK_SAFETY_HOLD_AFTER_ADAPTER_ISSUED', {
                'step_index': token.step_index, 'transition_id': token.transition_id,
                'steady_ns': self.now()})
            await self.until(lambda: next((facts for name, facts in self.events
                if name == 'SAFETY_REJECTED'
                and facts.get('candidate_sequence') == token.step_index
                and facts.get('candidate_source') == CommandEnvelope.SOURCE_POLICY
                and facts.get('candidate_source_instance_id') == self.policy_source_id
                and 'POLICY_HELD' in facts.get('reasons', ())), None),
                deadline_ns=deadline, phase='Safety hold rejection after adapter issuance')
            stop = await self.until(lambda: self.safety.local_training.last_output
                if self.safety.local_training.last_output is not None
                and self.safety.local_training.last_output.source == CommandEnvelope.SOURCE_SAFE_STOP
                and self.safety.local_training.last_output.sequence > safe_stop_sequence_before else None,
                deadline_ns=deadline, phase='Safety SAFE_STOP after held POLICY')
            def matching_zero_receipt():
                candidate = self.final.publication_for_source_sequence(
                    source=CommandEnvelope.SOURCE_SAFE_STOP, sequence=stop.sequence)
                if candidate is None or any((candidate.final_command.linear.x,
                        candidate.final_command.linear.y, candidate.final_command.angular.z)):
                    return None
                return candidate
            receipt = await self.until(matching_zero_receipt,
                deadline_ns=deadline, phase='SAFE_STOP receipt after held POLICY')
            applied = await self.until(lambda: self.ingress.backend_state
                if self.ingress.backend_state is not None
                and self.ingress.backend_state.fault_flags == 0
                and not self.ingress.backend_state.local_zero_override
                and self.ingress.backend_state.applied_final_publisher_instance_id == self.final.publisher_instance_id
                and self.ingress.backend_state.applied_final_publish_sequence == receipt.final_publish_sequence
                and self.ingress.backend_state.applied_receipt_valid else None,
                deadline_ns=deadline, phase='native zero application after held POLICY')
            checked = verify_r02f_safety_hold(self, step_index=token.step_index,
                receipt=receipt, backend_state=applied)
            aborted = b1.lifecycle.abort_step('R02f_safety_hold_before_policy_tick')
            self.emit('R02F_POLICY_REJECTED_ZERO_APPLIED', {
                'step_index': token.step_index, 'transition_id': token.transition_id,
                **checked, 'safe_stop_sequence': stop.sequence,
                'b1_abort_status': str(aborted.status), 'steady_ns': self.now()})
            return {'expected_rejection': True, 'policy_issued': True, **checked,
                'b1_step_aborted': True, 'transition_id': token.transition_id}
        self.safety.local_training.set_policy_hold(False)
        self.safety.local_training.set_stream_enabled(True)
        # The pending-step bind suppresses SAFE_STOP output so it cannot
        # revoke the admitted token. Once the exact post-ACK sample and
        # POLICY candidate have both reached Safety, evaluate that same
        # production selector immediately instead of waiting for its next
        # steady timer phase. The normal tick still enforces freshness,
        # scan-cutoff, limiter and fail-safe checks; a rejected candidate
        # therefore remains a SAFE_STOP and cannot open motion.
        await self.tick_policy_after_deferred_scan_cutoff(
            deadline_ns=deadline, step_index=token.step_index,
            sample_sequence=target_sample_sequence)
        if after_policy_applied is not None:
            from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
            if not callable(after_policy_applied):
                raise TypeError('after_policy_applied must be callable')
            receipt = await self.until(lambda: self.final.publication_for_source_sequence(
                source=FinalIssuedCommandReceipt.SOURCE_POLICY, sequence=token.step_index),
                deadline_ns=deadline, phase='R09b exact zero POLICY receipt before fixture pose')
            if any((receipt.final_command.linear.x, receipt.final_command.linear.y,
                    receipt.final_command.angular.z)):
                raise RuntimeError('R09b fixture callback requires an exact zero POLICY receipt')
            applied = await self.until(lambda: self.ingress.backend_state
                if self.ingress.backend_state is not None
                and self.ingress.backend_state.fault_flags == 0
                and not self.ingress.backend_state.paused
                and self.ingress.backend_state.applied_receipt_valid
                and self.ingress.backend_state.applied_final_publisher_instance_id
                    == receipt.final_publisher_instance_id
                and self.ingress.backend_state.applied_final_publish_sequence
                    == receipt.final_publish_sequence else None,
                deadline_ns=deadline, phase='R09b exact zero POLICY native application before fixture pose')
            applied_received_ns = self.ingress.backend_received_ns
            await after_policy_applied(receipt, applied, deadline, applied_received_ns)
        # The approved 0.10 s cadence is nominal; B1 computes reward from the
        # actual sim-time interval. Do not impose a second 100 ms minimum after
        # issuance: with a 10 Hz scan this can skip the first valid cutoff and
        # land on a receipt stamped at the cutoff but applied on the next tick.
        minimum_cutoff = stamp_ns(envelope.header.stamp) + 1
        if after_policy_applied is not None or before_pending_bind is not None:
            # R09b aligns its isolated fixture operation to a full nominal
            # interval after its exact zero POLICY application.
            minimum_cutoff = stamp_ns(envelope.header.stamp) + 100_000_000
        if after_policy_applied is not None:
            await self.align_r09b_application_cutoff(b1, policy_receipt=receipt,
                minimum_cutoff_ns=minimum_cutoff, deadline_ns=deadline)
        last_pending = None
        emitted_pending_cutoff_reasons = set()
        while self.now() < deadline:
            self.check()
            # Try the newest retained cutoff first. Older cutoffs remain
            # available as fallback, but evaluating them first can consume
            # the step budget and let their exact scan/noisy/backend facts
            # expire before a fresh cutoff with its adjacent receipt is
            # considered.
            for cutoff in sorted(
                    (stamp for stamp in self.ingress.scans if stamp >= minimum_cutoff),
                    reverse=True):
                try:
                    transition = b1.commit_step(cutoff)
                except B1SnapshotPending as error:
                    last_pending = str(error)
                    if should_emit_policy_cutoff_pending(
                            emitted_pending_cutoff_reasons, cutoff, last_pending):
                        self.emit('POLICY_CUTOFF_PENDING', {'step_index': token.step_index,
                            'transition_id': token.transition_id, 'cutoff_ns': cutoff,
                            'reason': last_pending, 'steady_ns': self.now()})
                    continue
                if self.now() >= deadline:
                    self.emit('B1_STEP_COMMITTED_LATE', {'step_index':token.step_index,
                        'transition_id':token.transition_id,'observed_ns':self.now(),'deadline_ns':deadline})
                    raise TimeoutError('B1 commit completed after step deadline')
                self.emit('POLICY_STEP_COMPLETE', {'step_index': token.step_index,
                    'transition_id': token.transition_id, 'started_ns': started,
                    'completed_ns': self.now(), 'deadline_ns': deadline, 'cutoff_ns': cutoff})
                if self.now() >= deadline:
                    raise TimeoutError('completion evidence published after step deadline')
                return transition
            await self.pause(min(0.002, max(0., (deadline - self.now()) / 1e9)))
        raise TimeoutError('POLICY step missing facts before deadline: ' + str(last_pending))



def evidence_json_value(value):
    """Giữ fields của DTO cleanup; không thay object thiếu bằng trạng thái sạch."""
    from dataclasses import is_dataclass, fields
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name:getattr(value, item.name) for item in fields(value)}
    if isinstance(value, Path):
        return str(value)
    raise TypeError('unsupported evidence value: ' + type(value).__name__)


def write_record_once(path, record):
    """Evidence bất biến: không ghi đè kể cả khi lần trước chưa hoàn tất."""
    import os
    raw = json.dumps(record, sort_keys=True, separators=(',', ':'), allow_nan=False, default=evidence_json_value).encode() + b'\n'
    import tempfile
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix='.b23-publish-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.link(temporary, path, follow_symlinks=False)  # Atomic, EEXIST không ghi đè.
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        os.unlink(temporary)  # Chỉ file tạm có nonce vừa được chính hàm tạo.
    return hashlib.sha256(raw).hexdigest()


async def write_record_once_async(path, record):
    """Ghi durable evidence mà không chặn event loop đang bơm ROS callbacks."""
    return await asyncio.to_thread(write_record_once, path, record)


def process_identity(pid):
    """Đọc bytes gốc cùng identity; lỗi đọc không được coi là PID vắng."""
    root = Path('/proc') / str(pid)
    raw = {name: (root/name).read_bytes() for name in ('stat', 'status', 'cmdline', 'cgroup')}
    fields = raw['stat'].rsplit(b')', 1)[1].split()
    uid = next(line.split()[1:] for line in raw['status'].splitlines() if line.startswith(b'Uid:'))
    return {'pid': pid, 'uid': int(uid[0]), 'state': fields[0].decode(),
        'ppid': int(fields[1]), 'pgid': int(fields[2]), 'sid': int(fields[3]),
        'start_ticks': int(fields[19]), 'argv': [v.decode() for v in raw['cmdline'].split(b'\0') if v],
        'raw_hex': {name: data.hex() for name, data in raw.items()}}


def same_process_identity(expected, observed):
    """Compare process identity fields, excluding volatile /proc counters/state."""
    fields = ('pid', 'uid', 'ppid', 'pgid', 'sid', 'start_ticks', 'argv')
    if not isinstance(expected, dict) or not isinstance(observed, dict):
        return False
    if any(field not in expected or field not in observed
           or expected[field] != observed[field] for field in fields):
        return False
    expected_raw = expected.get('raw_hex')
    observed_raw = observed.get('raw_hex')
    if not isinstance(expected_raw, dict) or not isinstance(observed_raw, dict):
        return False
    # cmdline/cgroup bind the executable arguments and service ownership; the
    # remaining stat/status bytes contain changing state and CPU counters.
    return all(isinstance(expected_raw.get(name), str)
               and expected_raw.get(name) == observed_raw.get(name)
               for name in ('cmdline', 'cgroup'))


class RunEvidence:
    """Sổ riêng từng process, raw stdout native và bốn book không gộp số đếm."""
    BOOKS = frozenset(('policy_adapter_issued', 'policy_final_published',
                      'policy_backend_applied', 'b1_transition_committed'))

    def __init__(self, root, role, *, run_id, invocation_id):
        self.root, self.role, self.run_id, self.invocation_id = Path(root), role, run_id, invocation_id
        self.streams = {}
        self._lock = threading.RLock()
        self.errors = []
        self.closed = False

    def append(self, filename, record):
        with self._lock:
            if self.closed:
                raise RuntimeError('evidence sink already closed')
            if filename not in self.streams:
                self.streams[filename] = (self.root/filename).open('x', encoding='utf-8')
            raw = json.dumps(record, sort_keys=True, separators=(',', ':'), allow_nan=False, default=evidence_json_value)
            self.streams[filename].write(raw + '\n')
            # These ledgers are read live by another owned process: the worker
            # polls native-events.jsonl while the parent decodes Gazebo stdout,
            # and the worker verifies a dropped POLICY receipt while the final
            # publisher is still alive. The worker also reads adapter issuance
            # from its own separate ledger handle before the evidence sink closes.
            # Flush these indexed streams without fsync; complete raw evidence
            # is synchronized at teardown.
            if filename in {'native-events.jsonl', 'policy_final_published.jsonl',
                            'policy_adapter_issued.jsonl', 'final-events.jsonl'}:
                self.streams[filename].flush()

    def record(self, event, facts):
        with self._lock:
            record = {'event': event, 'facts': facts, 'run_id': self.run_id,
                'invocation_id': self.invocation_id, 'role': self.role,
                'collected_ns': time.monotonic_ns()}
            self.append(self.role + '-events.jsonl', record)
            if event in self.BOOKS:
                self.append(event + '.jsonl', record)
            if event == 'owned_process_output' and facts.get('process') == 'server':
                import re
                text = re.sub(r'\x1b\[[0-9;]*m', '', facts['text'])
                messages = re.split(r'\[Msg\]\s*', text) if '[Msg]' in text else [text]
                parsed = []
                embedded_markers = []
                for index, message in enumerate(messages):
                    match = re.match(r'\s*(B23_[A-Z_]+)\s+(.*)', message)
                    if match:
                        parsed.append((index, match[1], match[2]))
                    else:
                        embedded_markers.extend((index, found[1]) for found in
                            re.finditer(r'\b(B23_[A-Z_]+)\b', message))
                common = {'raw_record': record, 'server_leader_pid': facts['pid'],
                    'invocation_id': self.invocation_id, 'collected_ns': time.monotonic_ns()}
                for index, kind, payload in parsed:
                    pairs = re.findall(r'(\w+)=([^\s]+)', payload)
                    fields = dict(pairs)
                    reason = None
                    if len(fields) != len(pairs):
                        reason = 'duplicate_native_event_field'
                    elif kind in ('B23_SAFETY_INPUT_OBSERVED', 'B23_ADMISSION_ACCEPTED'):
                        required = ('session', 'backend', 'ingress', 'sample')
                        if (any(not fields.get(key) for key in required)
                                or any(re.fullmatch(r'[0-9]+', fields[key]) is None
                                       for key in ('backend', 'ingress', 'sample'))):
                            reason = 'incomplete_native_input_identity'
                    event_record = dict(common, message_index=index,
                        message_text_sha256=hashlib.sha256(payload.encode()).hexdigest())
                    if reason is not None:
                        self.append('native-events.jsonl', dict(kind='B23_NATIVE_OUTPUT_REJECTED',
                            fields={'reason':reason, 'event_kind':kind,
                                'raw_text_sha256':hashlib.sha256(facts['text'].encode()).hexdigest()},
                            **event_record))
                    else:
                        self.append('native-events.jsonl', dict(kind=kind,
                            fields=fields, **event_record))
                for index, marker in embedded_markers:
                    self.append('native-events.jsonl', dict(kind='B23_NATIVE_OUTPUT_REJECTED',
                        fields={'reason':'event_marker_not_at_message_boundary', 'marker':marker,
                            'raw_text_sha256':hashlib.sha256(facts['text'].encode()).hexdigest()},
                        message_index=index, raw_record=record, server_leader_pid=facts['pid'],
                        invocation_id=self.invocation_id, collected_ns=time.monotonic_ns()))

    async def cleanup_publisher(self, batch, deadline):
        """ACK chỉ sau batch đúng ID đã được ghi và các sổ đã flush/fsync."""
        from mecanum_nav_bringup.local_training_process_supervisor import CleanupEvidenceAck
        if time.monotonic() >= deadline:
            raise TimeoutError('cleanup publication budget expired before write')
        write_record_once(self.root/'cleanup-batch.json', {'batch_id': batch.batch_id, 'events': batch.events})
        self.sync()
        if time.monotonic() >= deadline:
            raise TimeoutError('cleanup publication completed after deadline')
        write_record_once(self.root/'cleanup-ack.json', {'batch_id': batch.batch_id,
            'acknowledged': True, 'run_id': self.run_id, 'invocation_id': self.invocation_id,
            'acknowledged_ns': time.monotonic_ns()})
        if time.monotonic() >= deadline:
            raise TimeoutError('cleanup ACK completed after deadline')
        return CleanupEvidenceAck(batch.batch_id, True)

    def sync(self):
        import os
        with self._lock:
            for stream in self.streams.values():
                stream.flush(); os.fsync(stream.fileno())

    def close(self):
        with self._lock:
            try:
                self.sync()
            finally:
                self.closed = True
                for stream in self.streams.values():
                    stream.close()


def load_child_descriptor(path, role):
    """Child chỉ thuộc unit/parent/packet đã consume; không là CLI bypass guard."""
    import os
    raw = Path(path).resolve(strict=True).read_bytes()
    document = json.loads(raw)
    if (document.get('schema') != 'b23_owned_child/v1' or document.get('role') != role
            or document.get('invocation_id') != os.environ.get('INVOCATION_ID')
            or not document.get('invocation_id') or os.getuid() != 1000
            or document['parent_identity']['pid'] != os.getppid()):
        raise RuntimeError('child authority/profile/parent mismatch')
    current = process_identity(os.getppid())
    for key in ('pid', 'uid', 'start_ticks', 'argv'):
        if current[key] != document['parent_identity'][key]:
            raise RuntimeError('child parent identity changed: ' + key)
    packet_raw = Path(document['packet_path']).read_bytes()
    if hashlib.sha256(packet_raw).hexdigest() != document['packet_sha256']:
        raise RuntimeError('child packet bytes changed')
    packet = json.loads(packet_raw)
    if document.get('session_id') != packet.get('session_id'):
        raise RuntimeError('child session UUID does not match packet')
    consumed = json.loads(Path(packet['guard_path']).joinpath('consumed.json').read_bytes())
    if (consumed['run_id'] != document['run_id'] or consumed['packet_sha256'] != document['packet_sha256']
            or document['active_deadline_ns'] != consumed['active_deadline_ns']
            or document['total_deadline_ns'] != consumed['total_deadline_ns']
            or time.monotonic_ns() >= document['active_deadline_ns']
            or packet['unit'] not in Path('/proc/self/cgroup').read_text()):
        raise RuntimeError('child consumed guard/deadline/cgroup mismatch')
    return document, packet


def final_child(path):
    """Process Final riêng; boot không phát gì trước source binding APPLIED."""
    import os
    import signal
    import rclpy
    from rclpy.context import Context
    from rclpy.parameter import Parameter
    from rclpy.executors import SingleThreadedExecutor
    from mecanum_nav_rl_interfaces.msg import CommandEnvelope
    from mecanum_nav_rl.runtime_safety.final_twist_publisher_node import FinalTwistPublisherNode
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendControlAck, BackendSessionIdentity
    descriptor, packet = load_child_descriptor(path, 'final')
    sink = RunEvidence(descriptor['run_root'], descriptor['evidence_role'],
        run_id=descriptor['run_id'], invocation_id=descriptor['invocation_id'])
    context = Context(); node = executor = None
    stop = False
    def stopping(_sig, _frame):
        nonlocal stop
        stop = True
    signal.signal(signal.SIGTERM, stopping); signal.signal(signal.SIGINT, stopping)
    error = None
    r04d_original_lifecycle = None
    r04d_original_accepted = None
    try:
        rclpy.init(context=context)
        if packet['case'] == 'R04d':
            from rclpy.clock import Clock, ClockType
            r04d_original_lifecycle = FinalTwistPublisherNode._on_lifecycle
            r04d_original_accepted = FinalTwistPublisherNode._on_accepted
            marker_path = Path(descriptor['run_root'])/'r04d-final-lifecycle-delay.json'
            def schedule_steady(node, release_after_ns, callback):
                steady = Clock(clock_type=ClockType.STEADY_TIME)
                timer_holder = {}
                def poll_release():
                    if time.monotonic_ns() < release_after_ns:
                        return
                    timer = timer_holder['timer']
                    timer.cancel()
                    node.destroy_timer(timer)
                    callback()
                timer_holder['timer'] = node.create_timer(.005, poll_release, clock=steady)
            FinalTwistPublisherNode._on_lifecycle = r04d_final_lifecycle_dispatch(
                r04d_original_lifecycle, marker_path, sink.record, schedule_steady)
            FinalTwistPublisherNode._on_accepted = r04d_final_safe_stop_dispatch(
                r04d_original_accepted, marker_path, sink.record, schedule_steady,
                safe_stop_source=CommandEnvelope.SOURCE_SAFE_STOP)
        node = FinalTwistPublisherNode(context=context, parameter_overrides=[
            Parameter('use_sim_time', value=True), Parameter('navigation_mode', value='LOCAL_TRAINING'),
            Parameter('session_id', value=descriptor['session_id']),
            Parameter('scan_period_ns', value=descriptor['scan_period_ns'])], evidence_sink=sink.record)
        if packet['case'] == 'R04d':
            node._b23_r04d_run_id = descriptor['run_id']
            node._b23_r04d_invocation_id = descriptor['invocation_id']
        executor = SingleThreadedExecutor(context=context); executor.add_node(node)
        write_record_once(descriptor['final_boot_path'], {'schema': 'b23_final_boot/v1',
            'run_id': descriptor['run_id'], 'invocation_id': descriptor['invocation_id'],
            'identity': process_identity(os.getpid()), 'publisher_instance_id': node.publisher_instance_id})
        applied = False
        active_cutoff = False
        while not stop and time.monotonic_ns() < descriptor['total_deadline_ns']:
            if not active_cutoff and time.monotonic_ns() >= descriptor['active_deadline_ns']:
                node._local_admitted = False
                active_cutoff = True
                sink.record('FINAL_ACTIVE_CUTOFF', {'steady_ns':time.monotonic_ns()})
            executor.spin_once(timeout_sec=0.002)
            binding_path = Path(descriptor['final_binding_path'])
            if not active_cutoff and not applied and binding_path.exists():
                raw = binding_path.read_bytes(); binding = json.loads(raw)
                if (binding['schema'] != 'b23_final_source_binding/v1'
                        or binding['run_id'] != descriptor['run_id']
                        or binding['invocation_id'] != descriptor['invocation_id']
                        or binding['final_publisher_instance_id'] != node.publisher_instance_id):
                    raise RuntimeError('final source binding file ownership mismatch')
                ack = BackendControlAck(bytes.fromhex(binding['request_cdr_hex']),
                    bytes.fromhex(binding['response_cdr_hex']), binding['ack_observed_ns'])
                req = ack.request
                identity = BackendSessionIdentity(descriptor['session_id'], packet['config_hash'],
                    packet['asset_manifest_sha256'], packet['coordinator_ingress_instance_id'], descriptor['backend_instance_id'])
                # Chờ DDS lifecycle/clock đến đúng context; không sửa ACK hoặc deadline.
                life = node._identity
                if life is None or node.get_clock().now().nanoseconds < ack.response.applied_sim_stamp.sec*10**9+ack.response.applied_sim_stamp.nanosec:
                    continue
                if (life.sequence, life.episode_generation, life.reset_epoch, life.runtime_generation) != (
                        req.lifecycle_sequence, req.episode_generation, req.reset_epoch, req.runtime_generation):
                    if life.sequence < req.lifecycle_sequence:
                        continue
                    raise RuntimeError('final source binding lifecycle changed')
                node.bind_backend_session(ack, identity)
                write_record_once(descriptor['final_binding_ack_path'], {'source_binding_applied': True,
                    'binding_file_sha256': hashlib.sha256(raw).hexdigest(),
                    'publisher_instance_id': node.publisher_instance_id, 'pid': os.getpid(),
                    'invocation_id': descriptor['invocation_id']})
                applied = True
        if not stop:
            raise TimeoutError('final publisher cleanup deadline expired')
    except BaseException as exc:
        error = repr(exc)
        sink.record('FINAL_CHILD_ERROR', {'error': error})
    finally:
        if executor is not None:
            executor.shutdown(timeout_sec=0.)
        if node is not None:
            node.destroy_node()
        if context.ok(): context.shutdown()
        if r04d_original_lifecycle is not None:
            FinalTwistPublisherNode._on_lifecycle = r04d_original_lifecycle
        if r04d_original_accepted is not None:
            FinalTwistPublisherNode._on_accepted = r04d_original_accepted
        sink.close()
    return 0 if error is None else 1


def _ledger_rows(root, filename):
    rows = []
    for line in (Path(root)/filename).read_text().splitlines():
        if line.strip(): rows.append(json.loads(line))
    return rows


def _soak_ledger_counts(root):
    names = ('policy_adapter_issued.jsonl','policy_final_published.jsonl',
        'policy_backend_applied.jsonl','b1_transition_committed.jsonl')
    rows = [_ledger_rows(root, name) for name in names]
    ids = [{entry.get('facts',{}).get('transition_id') for entry in book
        if entry.get('facts',{}).get('transition_id')} for book in rows]
    return {'policy_adapter_issued':len(rows[0]), 'policy_final_published':len(rows[1]),
        'policy_backend_applied':len(ids[2]), 'policy_backend_applied_records':len(rows[2]),
        'b1_transition_committed':len(rows[3]), 'unique_transition_ids':[len(items) for items in ids]}


async def _run_b2_soak(io, b1, packet, sink):
    """Run the immutable 30-episode D04 schedule through the production path."""
    from mecanum_nav_rl.simulation.local_training_reset import ResetTarget
    target = ResetTarget(**packet['reset_target'])
    episode_steps = [34]*10 + [33]*20
    resets = committed_steps = 0
    terminal_records = []
    cutoff_records = []
    for episode_index, (seed, expected_steps) in enumerate(zip(packet['episode_seeds'], episode_steps)):
        if time.monotonic_ns() >= io.deadline_ns:
            raise TimeoutError('B2_SOAK_V1 active deadline reached before reset')
        await io.reset_episode(b1, seed=seed, target=target, paused_hold_s=.250)
        resets += 1
        terminal_seen = False
        for step_index in range(1, expected_steps + 1):
            transition = await io.policy_step(b1, soak_action(episode_index, step_index))
            committed_steps += 1
            terminal = bool(transition.termination.terminated or transition.termination.truncated)
            if terminal:
                terminal_records.append({'episode_index':episode_index,'step_index':step_index,
                    'terminated':transition.termination.terminated,'truncated':transition.termination.truncated,
                    'seed':seed})
                if step_index != expected_steps:
                    raise RuntimeError('B2_SOAK_V1 terminal occurred before scheduled episode slot end')
                if episode_index != 29:
                    raise RuntimeError('B2_SOAK_V1 terminal before final episode invalidates fixed schedule')
                terminal_seen = True
                break
        if not terminal_seen:
            cutoff = {'episode_index':episode_index,'step_count':expected_steps,
                'seed':seed,'episode_complete':False,
                'reason':'final_slot_unfinished' if episode_index == 29 else 'scheduled_slot_unfinished'}
            sink.record('COLLECTION_CUTOFF', cutoff)
            cutoff_records.append(cutoff)
    counts = _soak_ledger_counts(packet['run_root'])
    expected = 1000
    if resets != 30 or committed_steps != expected:
        raise RuntimeError('B2_SOAK_V1 reset/step schedule count mismatch')
    if (counts['policy_adapter_issued'] != expected or counts['policy_backend_applied'] != expected
            or counts['b1_transition_committed'] != expected
            or counts['unique_transition_ids'] != [expected, expected, expected, expected]):
        raise RuntimeError('B2_SOAK_V1 four-ledger counts do not reconcile: '+repr(counts))
    return {'case':'R08','resets_confirmed':resets,'policy_steps_committed':committed_steps,
        'ledger_counts':counts,'terminal_records':terminal_records,
        'collection_cutoff':bool(cutoff_records),'collection_cutoff_records':cutoff_records,
        'completed_ns':time.monotonic_ns()}


async def training_child(path):
    """Worker cases use only the bound LOCAL_TRAINING production path."""
    from rclpy.time import Time
    from mecanum_nav_rl.tasks.scenario_artifact import ScenarioArtifactLoader
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import LocalTrainingB1Adapter
    from mecanum_nav_rl.simulation.local_training_reset import ResetTarget
    descriptor, packet = load_child_descriptor(path, 'worker')
    sink = RunEvidence(descriptor['run_root'], 'worker', run_id=descriptor['run_id'],
        invocation_id=descriptor['invocation_id'])
    io = None
    primary, cleanup_errors, outcome = None, [], None
    try:
        document = json.loads(Path(packet['resolved_config']).read_bytes())
        asset = json.loads(Path(packet['asset_manifest']).read_bytes())
        io = TrainingWorkerIO(descriptor, document, asset, sink.record)
        io.fault_hooks = set(packet['fault_hooks'])
        loop = asyncio.get_running_loop()
        import signal
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, setattr, io, 'abort_requested', sig.name)
        io.start_pump()
        await io.startup()
        artifact = ScenarioArtifactLoader(expected_gazebo_world_name=asset['world_id'],
            expected_world_file_sha256=asset['world_file_sha256']).load(Path(packet['scenario']).read_text())
        b1 = LocalTrainingB1Adapter(io.ingress, artifact, asset,
            scan_transform=lambda: io.safety._tf_buffer.lookup_transform('base_link', 'lidar_frame', Time()), emit=io.emit)
        if packet['case'] == 'R08':
            if len(packet['episode_seeds']) != 30:
                raise RuntimeError('R08 requires the exact 30 B2_SOAK_V1 seeds')
            outcome = await _run_b2_soak(io, b1, packet, sink)
        elif packet['case'] == 'R09a':
            if packet['fault_hooks'] or len(packet['episode_seeds']) != 1:
                raise RuntimeError('R09a packet must pin the clean goal-settle scenario')
            require_r09_scenario(artifact, 'B2_GOAL_SETTLE_V1')
            target = ResetTarget(**packet['reset_target'])
            await io.reset_episode(b1, seed=packet['episode_seeds'][0], target=target,
                paused_hold_s=.250)
            committed = []
            for _ in range(30):
                transition = await io.policy_step(b1, (0., 0., 0.))
                committed.append(transition.transition_identity.transition_id)
                if transition.termination.terminated:
                    checked = verify_r09a_goal_settle(transition)
                    outcome = {'case':'R09a', 'resets_confirmed':1,
                        'policy_steps_committed':len(committed), 'transition_ids':committed,
                        **checked,
                        'completed_ns':time.monotonic_ns()}
                    break
                if transition.termination.truncated:
                    raise RuntimeError('R09a zero-command goal settle truncated before success')
            if outcome is None:
                raise TimeoutError('R09a did not settle at the bound goal within 30 committed steps')
        elif packet['case'] == 'R09b':
            from rclpy.serialization import deserialize_message
            from nav_msgs.msg import Odometry
            from mecanum_nav_rl_interfaces.msg import SimulationContactState
            if packet['fault_hooks'] or len(packet['episode_seeds']) != 1:
                raise RuntimeError('R09b packet must pin the clean contact-task scenario')
            require_r09_scenario(artifact, 'B2_CONTACT_V1')
            fixture = validate_r09b_task_fixture(packet.get('task_fixture'))
            target = ResetTarget(**packet['reset_target'])
            await io.reset_episode(b1, seed=packet['episode_seeds'][0], target=target,
                paused_hold_s=.250)
            fixture_moved = False
            primary = None
            try:
                async def move_fixture_before_pending_bind(deadline_ns, token, barrier_ns, zero_witness):
                    nonlocal fixture_moved
                    receipt = zero_witness['receipt']
                    applied_state = zero_witness['state']
                    applied_received_ns = zero_witness['received_ns']
                    # Once the RPC is submitted, its result can be uncertain on
                    # timeout. Always attempt the exact restore in finalization.
                    fixture_moved = True
                    io.emit('R09B_B1_STEP_STARTED_BEFORE_FIXTURE_CONTACT', {
                        'step_index':token.step_index, 'transition_id':token.transition_id,
                        'action_barrier_ns':int(barrier_ns),
                        'zero_publish_sequence':int(receipt.final_publish_sequence),
                        'zero_source':int(receipt.source), 'steady_ns':io.now()})
                    await io.run_r09b_contact_task_pulse(zero_receipt=receipt,
                        zero_applied_state=applied_state, deadline_ns=deadline_ns,
                        applied_received_ns=applied_received_ns)
                    fixture_moved = False
                transition = await io.policy_step(b1, (0., 0., 0.),
                    before_pending_bind=move_fixture_before_pending_bind)
                committed_steps = 1
                pair = io.ingress.physics_pairs[-1] if io.ingress.physics_pairs else None
                progress = []
                if pair is not None:
                    oracle = deserialize_message(pair.oracle_bytes, Odometry)
                    status = deserialize_message(pair.backend_bytes, SimulationContactState)
                    sample = {'transition_id':transition.transition_identity.transition_id,
                        'physics_iteration':pair.iteration, 'sim_stamp_ns':pair.stamp_ns,
                        'pose_xy_m':[oracle.pose.pose.position.x,oracle.pose.pose.position.y],
                        'twist_xyz':[oracle.twist.twist.linear.x, oracle.twist.twist.linear.y,
                            oracle.twist.twist.angular.z],
                        'contact_active':bool(status.contact_active),
                        'coverage_complete':bool(status.coverage_complete),
                        'fault_flags':int(status.fault_flags), 'steady_ns':io.now()}
                    progress.append(sample)
                    sink.record('R09B_CONTACT_TASK_PROGRESS', sample)
                contact = b1.contact.state
                if transition.termination.truncated:
                    raise RuntimeError('R09b task ended by truncation before contact')
                checked = verify_r09b_task_contact(transition, contact)
                if (pair is None or not sample['coverage_complete']
                        or sample['fault_flags'] != 0
                        or not (sample['contact_active'] or checked['contact_pulse_consumed_by_b1'])):
                    raise RuntimeError('R09b terminal lacks matching covered contact evidence at B1 cutoff')
                outcome = {'case':'R09b','resets_confirmed':1,
                    'policy_steps_committed':committed_steps, 'progress_samples':progress,
                    'task_fixture':fixture, **checked, 'completed_ns':time.monotonic_ns()}
            except BaseException as error:
                primary = error
                raise
            finally:
                if fixture_moved:
                    try:
                        await io.set_r09b_task_fixture_pose(pose_name='initial_pose',
                            deadline_ns=min(io.deadline_ns, io.now()+1_000_000_000))
                        empty = await io.until(lambda: io.ingress.backend_state
                            if io.ingress.backend_state is not None
                            and io.ingress.backend_state.coverage_complete
                            and not io.ingress.backend_state.contact_active
                            and io.ingress.backend_state.fault_flags == 0
                            and not io.ingress.backend_state.paused else None,
                            deadline_ns=min(io.deadline_ns, io.now()+1_000_000_000),
                            phase='R09b restored fixture covered-empty confirmation')
                        sink.record('R09B_FIXTURE_RESTORED_COVERED_EMPTY', {
                            'entity_name':fixture['entity_name'], 'pose':fixture['initial_pose'],
                            'coverage_complete':bool(empty.coverage_complete),
                            'contact_active':bool(empty.contact_active),
                            'physics_iteration':int(empty.physics_iteration),
                            'sim_stamp_ns':int(empty.header.stamp.sec)*1_000_000_000
                                +int(empty.header.stamp.nanosec),
                            'steady_ns':io.now()})
                    except BaseException as restore_error:
                        sink.record('R09B_FIXTURE_RESTORE_ERROR', {
                            'error':repr(restore_error), 'steady_ns':io.now()})
                        if primary is None:
                            raise
        elif packet['case'] == 'R05':
            expected_env = case_environment(packet['case'], packet['fault_hooks'])
            if (packet['fault_hooks'] != ['mask_contact_coverage_after_verified']
                    or any(packet['environment'].get(key) != value
                        for key, value in expected_env.items())
                    or io.contact_ack is None or io.contact_start_request_sequence is None):
                raise RuntimeError('R05 packet/hook/original QUERY binding is incomplete')
            def coverage_masked():
                return r05_contact_coverage_mask_event(
                    descriptor['native_events_path'])
            masked = await io.until(coverage_masked,
                deadline_ns=min(io.deadline_ns, time.monotonic_ns()+5_000_000_000),
                phase='R05 pinned contact coverage mask',
                expected_native_fault_flags=16)
            state = await io.until(lambda: io.ingress.backend_state
                    if (io.ingress.backend_state is not None
                        and int(io.ingress.backend_state.fault_flags) == 16
                        and io.ingress.backend_state.local_zero_override) else None,
                deadline_ns=min(io.deadline_ns, time.monotonic_ns()+2_000_000_000),
                phase='R05 contact loss closes POLICY with native zero',
                expected_native_fault_flags=16)
            replay_ack = await io.control.replay(io.contact_ack,
                deadline_ns=min(io.deadline_ns, time.monotonic_ns()+1_000_000_000))
            from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
            from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendControlError
            try:
                fresh_ack = await io.control.transact(
                    Control.Request.OP_VERIFY_CONTACT_CAPABILITY,
                    deadline_ns=min(io.deadline_ns, time.monotonic_ns()+1_000_000_000),
                    probe_action=Control.Request.PROBE_ACTION_QUERY,
                    probe_start_request_sequence=io.contact_start_request_sequence)
            except BackendControlError as error:
                fresh_ack = expected_r05_revoked_query_ack(
                    error, start_request_sequence=io.contact_start_request_sequence)
                sink.record('R05_FRESH_QUERY_REJECTED_AFTER_REVOCATION', {
                    'request_cdr_hex':fresh_ack.request_bytes.hex(),
                    'response_cdr_hex':fresh_ack.response_bytes.hex(),
                    'reason_code':fresh_ack.response.reason_code,
                    'observed_ns':fresh_ack.observed_steady_ns})
            checked = verify_r05_contact_query_revocation(descriptor['run_root'],
                original_ack=io.contact_ack, replay_ack=replay_ack,
                fresh_ack=fresh_ack, backend_state=state)
            sink.record('R05_CONTACT_QUERY_REVOCATION', {
                'original_request_cdr_hex':io.contact_ack.request_bytes.hex(),
                'original_response_cdr_hex':io.contact_ack.response_bytes.hex(),
                'replay_request_cdr_hex':replay_ack.request_bytes.hex(),
                'replay_response_cdr_hex':replay_ack.response_bytes.hex(),
                'fresh_request_cdr_hex':fresh_ack.request_bytes.hex(),
                'fresh_response_cdr_hex':fresh_ack.response_bytes.hex(),
                'coverage_mask_event':masked, 'native_zero_state_sequence':state.status_sequence,
                'checked':checked, 'completed_ns':time.monotonic_ns()})
            outcome = {'case':'R05','resets_confirmed':0,
                'policy_steps_committed':0, **checked,
                'completed_ns':time.monotonic_ns()}
        elif packet['case'] in ('R06a','R06b','R06c'):
            if packet['fault_hooks'] != case_fault_hooks(packet['case']):
                raise RuntimeError(packet['case'] + ' reset fault hook does not match the case contract')
            target = ResetTarget(**packet['reset_target'])
            try:
                await io.reset_episode(b1, seed=packet['episode_seeds'][0], target=target,
                    paused_hold_s=.250)
            except (ValueError, TimeoutError, RuntimeError) as error:
                anchor = next((facts for name, facts in io.events
                    if name == 'B23_R06C_FAULT_ARMED'), None)
                checked = verify_r06_reset_fault(io, case=packet['case'], error=error,
                    anchor_sequence=None if anchor is None else anchor['zero_anchor_sequence'])
                outcome = {'case':packet['case'], 'resets_confirmed':0,
                    'policy_steps_committed':0, **checked}
            if outcome is None:
                raise RuntimeError(packet['case'] + ' expected reset acceptance rejection was not observed')
        elif packet['case'] == 'R07a':
            if packet['fault_hooks'] != case_fault_hooks('R07a'):
                raise RuntimeError('R07a packet does not pin the unexpected-pause hook')
            target = ResetTarget(**packet['reset_target'])
            await io.reset_episode(b1, seed=packet['episode_seeds'][0], target=target,
                paused_hold_s=.250)
            transition = await io.policy_step(b1, (0.20, 0.0, 0.0))
            if transition.termination.terminated or transition.termination.truncated:
                raise RuntimeError('R07a POLICY step terminated before external pause')
            before_policy = policy_receipt_count(io.ingress.receipts)
            before_policy_identities = policy_step_identities(io.ingress.receipts)
            reset_fact_before = b1.lifecycle.snapshot.reset_commit_facts
            previous_ros = io.ros_now()
            io.expected_paused = True
            world_ack = await io.control_world(world_name='b2_training_arena', pause=True,
                timeout_s=min(1.0, max(0.0, (io.deadline_ns-io.now())/1e9)),
                expected_native_fault_flags=1)
            pause_state = await io.paused_state(True, min(1.0,
                max(0.0, (io.deadline_ns-io.now())/1e9)), expected_native_fault_flags=1)
            io.emit('B23_R07A_UNEXPECTED_PAUSE_ARMED', {
                'after_policy_step':transition.transition_identity.step_index,
                'pre_pause_policy_receipt_count':before_policy,
                'pre_pause_policy_step_identities':sorted(before_policy_identities, key=repr),
                'pre_pause_reset_fact':repr(reset_fact_before),
                'sim_ns_before_pause':previous_ros,'steady_ns':io.now()})
            state = await io.until(lambda: io.ingress.backend_state
                if (io.ingress.backend_state is not None
                    and io.ingress.backend_state.fault_flags == 1
                    and io.ingress.backend_state.local_zero_override
                    and io.ingress.backend_state.actuator_inhibited) else None,
                deadline_ns=min(io.deadline_ns, io.now()+1_000_000_000),
                phase='R07a native unexpected-pause zero/fault',
                expected_native_fault_flags=1)
            policy_after = policy_receipt_count(io.ingress.receipts)
            policy_after_identities = policy_step_identities(io.ingress.receipts)
            io.emit('B23_R07A_POLICY_OBSERVATION', {
                'post_pause_policy_receipt_count':policy_after,
                'post_pause_policy_step_identities':sorted(policy_after_identities, key=repr),
                'steady_ns':io.now()})
            reset_fact_after = b1.lifecycle.snapshot.reset_commit_facts
            checked = verify_r07a_unexpected_pause(world_ack=world_ack,
                world_pause_state=pause_state,
                backend_state=state,
                pre_pause_policy_step_identities=before_policy_identities,
                post_pause_policy_step_identities=policy_after_identities,
                reset_count_before=reset_fact_before, reset_count_after=reset_fact_after)
            await asyncio.sleep(min(.250, max(0.0, (io.deadline_ns-io.now())/1e9)))
            if io.now() >= io.deadline_ns:
                raise TimeoutError('R07a pause hold reached active deadline')
            from mecanum_nav_rl_interfaces.msg import SimulationContactState
            resumed_fault_flags = (SimulationContactState.FAULT_CONTEXT |
                SimulationContactState.FAULT_COMMAND_SEQUENCE |
                SimulationContactState.FAULT_COMMAND_STALE)
            resume_ack = await io.control_world(world_name='b2_training_arena', pause=False,
                timeout_s=min(1.0, max(0.0, (io.deadline_ns-io.now())/1e9)),
                expected_native_fault_flags=1)
            resume_state = await io.paused_state(False, min(1.0,
                max(0.0, (io.deadline_ns-io.now())/1e9)),
                expected_native_fault_flags=(1, resumed_fault_flags))
            io.expected_paused = False
            io.last_clock_advance_ns = io.now()
            resumed_gate_state = await io.until(lambda: io.ingress.backend_state
                if (io.ingress.backend_state is not None
                    and not io.ingress.backend_state.paused
                    and io.ingress.backend_state.fault_flags == resumed_fault_flags
                    and io.ingress.backend_state.local_zero_override
                    and io.ingress.backend_state.actuator_inhibited) else None,
                deadline_ns=min(io.deadline_ns, io.now()+1_000_000_000),
                phase='R07a resumed gate invalidation remains zero/inhibited',
                expected_native_fault_flags=(1, resumed_fault_flags))
            post_resume_policy_identities = policy_step_identities(io.ingress.receipts)
            resumed_checked = verify_r07a_resumed_inhibition(
                backend_state=resumed_gate_state,
                pre_pause_policy_step_identities=before_policy_identities,
                post_resume_policy_step_identities=post_resume_policy_identities,
                reset_count_before=reset_fact_before,
                reset_count_after=b1.lifecycle.snapshot.reset_commit_facts)
            io.emit('B23_R07A_RESUMED_INHIBITION_VERIFIED', {
                **resumed_checked, 'steady_ns':io.now()})
            await io.until(lambda: io.ros_now() if io.ros_now() > previous_ros else None,
                deadline_ns=min(io.deadline_ns, io.now()+1_000_000_000),
                phase='R07a simulation clock resumes after external pause',
                expected_native_fault_flags=resumed_fault_flags)
            inhibit_ack = await io.control.inhibit(
                deadline_ns=min(io.deadline_ns, io.now()+1_000_000_000))
            if resume_ack is not True or resume_state is not True:
                raise RuntimeError('R07a world resume was not acknowledged')
            io.emit('B23_R07A_VERIFIED', {'checked':checked,
                'world_pause_success':world_ack,'world_pause_state':pause_state,
                'world_resume_success':resume_ack,'world_resume_state':not resume_state,
                **resumed_checked,
                'native_status_sequence':state.status_sequence,
                'native_inhibit_request_cdr_hex':inhibit_ack.request_bytes.hex(),
                'native_inhibit_response_cdr_hex':inhibit_ack.response_bytes.hex(),
                'steady_ns':io.now()})
            outcome = {'case':'R07a','expected_unexpected_pause_fault':True,
                **checked,'inhibit_applied':True,'completed_ns':time.monotonic_ns()}
        elif packet['case'] == 'R07b':
            from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
            from mecanum_nav_rl.runtime_simulation.local_training_coordinator import (
                BackendControlError, BackendSessionIdentity, BackendControlSession)
            from mecanum_nav_rl.runtime_simulation.local_training_ports import LocalTrainingBackendControlPort
            if (packet['fault_hooks'] != case_fault_hooks('R07b')
                    or io.contact_ack is None or io.contact_start_request_sequence is None):
                raise RuntimeError('R07b packet/contact proof binding is incomplete')
            original = io.contact_ack
            original_backend_id = io.descriptor['backend_instance_id']
            before, after, rollback = await io.reset_world_time_only(timeout_s=
                min(1.0, max(0.0, (io.deadline_ns-io.now())/1e9)))
            rollback_disposition = await io.until(
                lambda: r07b_post_rollback_backend_disposition(
                    io, old_backend_instance_id=original_backend_id,
                    rollback_observed_ns=rollback['observed_steady_ns']),
                deadline_ns=min(io.deadline_ns, io.now()+1_000_000_000),
                phase='R07b native post-rollback disposition')
            io.emit('B23_R07B_NATIVE_ROLLBACK_DISPOSITION', rollback_disposition)
            # Keep the clock rollback exception scoped to this reset until
            # native proof invalidation/backend replacement is observable.
            # Subsequent time_only samples may still move backward while the
            # reset settles; no other phase gets this exception.
            io._r07b_rollback_pending_before_ns = None
            io._r07b_request_started_ns = None
            replay_ack, replay_error, replay_identity_ack = None, None, None
            try:
                replay_ack = await io.control.replay(original,
                    deadline_ns=min(io.deadline_ns, io.now()+1_000_000_000))
            except TimeoutError as error:
                replay_error = error
                io.emit('B23_R07B_OLD_QUERY_REPLAY_UNAVAILABLE', {
                    'request_sequence':original.request.request_sequence,
                    'error':repr(error),'reason':'replay window expired after time_only reset'})
            except BackendControlError as error:
                if error.ack is None:
                    raise
                replay_error, replay_identity_ack = error, error.ack
                io.emit('B23_R07B_OLD_QUERY_REPLAY_REJECTED', {
                    'request_sequence':original.request.request_sequence,
                    'request_cdr_hex':error.ack.request_bytes.hex(),
                    'response_cdr_hex':error.ack.response_bytes.hex(),
                    'reason':'replacement backend identity mismatch'})
            if replay_error is None:
                try:
                    fresh_ack = await io.control.transact(Control.Request.OP_VERIFY_CONTACT_CAPABILITY,
                        deadline_ns=min(io.deadline_ns, io.now()+1_000_000_000),
                        probe_action=Control.Request.PROBE_ACTION_QUERY,
                        probe_start_request_sequence=io.contact_start_request_sequence)
                except BackendControlError as error:
                    if error.ack is None:
                        raise
                    fresh_ack = error.ack
                state = await io.until(lambda: io.ingress.backend_state
                    if (io.ingress.backend_state is not None
                        and io.ingress.backend_state.fault_flags & 64
                        and io.ingress.backend_state.local_zero_override) else None,
                    deadline_ns=min(io.deadline_ns, io.now()+1_000_000_000),
                    phase='R07b native clock rollback inhibit', expected_native_fault_flags=64)
                inhibit_ack = await io.control.inhibit(
                    deadline_ns=min(io.deadline_ns, io.now()+1_000_000_000))
                checked = verify_r07b_revocation(response=fresh_ack.response,
                    original_proof=original, sim_before_ns=before, sim_after_ns=after,
                    sim_time_jump_delta_ns=rollback['delta_ns'],
                    replay_ack=replay_ack, fresh_ack=fresh_ack, inhibit_ack=inhibit_ack)
                io.emit('B23_R07B_VERIFIED', {'checked':checked,
                    'original_query_request_cdr_hex':original.request_bytes.hex(),
                    'original_query_response_cdr_hex':original.response_bytes.hex(),
                    'replay_query_request_cdr_hex':replay_ack.request_bytes.hex(),
                    'replay_query_response_cdr_hex':replay_ack.response_bytes.hex(),
                    'fresh_query_request_cdr_hex':fresh_ack.request_bytes.hex(),
                    'fresh_query_response_cdr_hex':fresh_ack.response_bytes.hex(),
                    'clock_fault_status_sequence':state.status_sequence,
                    'inhibit_request_cdr_hex':inhibit_ack.request_bytes.hex(),
                    'inhibit_response_cdr_hex':inhibit_ack.response_bytes.hex(),
                    'steady_ns':io.now()})
                outcome = {'case':'R07b', **checked,'completed_ns':time.monotonic_ns()}
            else:
                # Một số Gazebo time_only reset thay instance plugin/backend.
                # Không dùng status hoặc proof của instance cũ trong trường hợp
                # đó: xác minh identity mismatch bằng INHIBIT cũ rồi mở một
                # control client chỉ cho instance mới để chứng minh zero.
                try:
                    await io.control.inhibit(deadline_ns=min(io.deadline_ns, io.now()+1_000_000_000))
                    raise RuntimeError('R07b old backend identity unexpectedly remained accepted')
                except BackendControlError as error:
                    replacement_ack = error.ack
                    if replacement_ack is None:
                        raise
                new_backend_id = replacement_ack.response.backend_instance_id
                if (replacement_ack.request.operation != Control.Request.OP_INHIBIT
                        or replacement_ack.response.reason_code != Control.Response.REASON_IDENTITY_MISMATCH
                        or new_backend_id == original_backend_id):
                    raise RuntimeError('R07b replay timeout was not bound to backend replacement')
                identity = BackendSessionIdentity(io.descriptor['session_id'],
                    io.descriptor['config_hash'], io.descriptor['asset_manifest_sha256'],
                    io.descriptor['coordinator_ingress_instance_id'], new_backend_id)
                replacement_control = BackendControlSession(
                    LocalTrainingBackendControlPort.from_node(io.node), identity,
                    emit=io.emit, now_ns=io.now, pause=io.pause)
                io.pin_replacement_backend_for_cleanup(replacement_control, new_backend_id)
                fresh_ack, inhibit_ack = await query_replacement_backend_then_inhibit(
                    replacement_control,
                    query_deadline_ns=min(io.deadline_ns, io.now()+1_000_000_000),
                    inhibit_deadline_ns=min(io.deadline_ns, io.now()+1_000_000_000),
                    probe_start_request_sequence=io.contact_start_request_sequence)
                status_deadline = min(io.deadline_ns, io.now()+1_000_000_000)
                replacement_status = None
                while io.now() < status_deadline:
                    candidates = [status for status in io._r07b_replacement_backend_statuses
                        if status['backend_instance_id'] == new_backend_id
                        and status['received_ns'] > inhibit_ack.observed_steady_ns]
                    if candidates:
                        replacement_status = candidates[-1]
                        break
                    await io.pause(min(.005, max(0., (status_deadline-io.now())/1e9)))
                if replacement_status is None:
                    raise TimeoutError('R07b replacement backend zero status not observed after INHIBIT ACK')
                checked = verify_r07b_backend_restart(original_proof=original,
                    sim_time_jump_delta_ns=rollback['delta_ns'], replay_error=replay_error,
                    replay_identity_ack=replay_identity_ack,
                    replacement_ack=replacement_ack, inhibit_ack=inhibit_ack,
                    fresh_ack=fresh_ack, replacement_status=replacement_status,
                    old_backend_instance_id=original_backend_id)
                io.emit('B23_R07B_BACKEND_REPLACEMENT_VERIFIED', {'checked':checked,
                    'clock_jump':rollback,'old_query_request_cdr_hex':original.request_bytes.hex(),
                    'old_query_response_cdr_hex':original.response_bytes.hex(),
                    'old_query_replay_identity_response_cdr_hex':(
                        replay_identity_ack.response_bytes.hex() if replay_identity_ack else None),
                    'old_session_rejection_request_cdr_hex':replacement_ack.request_bytes.hex(),
                    'old_session_rejection_response_cdr_hex':replacement_ack.response_bytes.hex(),
                    'replacement_inhibit_request_cdr_hex':inhibit_ack.request_bytes.hex(),
                    'replacement_inhibit_response_cdr_hex':inhibit_ack.response_bytes.hex(),
                    'replacement_query_request_cdr_hex':fresh_ack.request_bytes.hex(),
                    'replacement_query_response_cdr_hex':fresh_ack.response_bytes.hex(),
                    'replacement_status':replacement_status,'steady_ns':io.now()})
                outcome = {'case':'R07b','clock_rollback_observed':True,
                    'backend_restarted':True,**checked,'completed_ns':time.monotonic_ns()}
        elif packet['case'] == 'R07c':
            from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
            from mecanum_nav_rl.runtime_simulation.local_training_coordinator import (
                BackendControlError, BackendSessionIdentity, BackendControlSession)
            from mecanum_nav_rl.runtime_simulation.local_training_ports import LocalTrainingBackendControlPort
            if packet['fault_hooks'] or io.contact_ack is None:
                raise RuntimeError('R07c requires a clean packet and verified original contact proof')
            old_backend = int(io.descriptor['backend_instance_id'])
            restart = await io.request_owned_restart(case='R07c', target_role='server')
            await io.wait_backend_control_ready(io.control, timeout_ns=10_000_000_000,
                phase='R07c replacement backend control service readiness')
            old_rejection = None
            try:
                await io.control.inhibit(deadline_ns=min(io.deadline_ns, io.now()+1_000_000_000))
                raise RuntimeError('R07c old backend control unexpectedly accepted after restart')
            except BackendControlError as error:
                old_rejection = error.ack
                if old_rejection is None:
                    raise
            new_backend = int(old_rejection.response.backend_instance_id)
            if new_backend == old_backend:
                raise RuntimeError('R07c old control rejection did not identify replacement backend')
            identity = BackendSessionIdentity(io.descriptor['session_id'],
                io.descriptor['config_hash'], io.descriptor['asset_manifest_sha256'],
                io.descriptor['coordinator_ingress_instance_id'], new_backend)
            replacement_control = BackendControlSession(
                LocalTrainingBackendControlPort.from_node(io.node), identity,
                emit=io.emit, now_ns=io.now, pause=io.pause)
            io.pin_replacement_backend_for_cleanup(replacement_control, new_backend)
            query_ack, inhibit_ack = await query_replacement_backend_then_inhibit(
                replacement_control, query_deadline_ns=min(io.deadline_ns, io.now()+1_000_000_000),
                inhibit_deadline_ns=min(io.deadline_ns, io.now()+1_000_000_000),
                probe_start_request_sequence=io.contact_start_request_sequence)
            status_deadline = min(io.deadline_ns, io.now()+1_000_000_000)
            replacement_status = None
            while io.now() < status_deadline:
                candidates = [status for status in io._r07c_replacement_backend_statuses
                    if status['backend_instance_id'] == new_backend
                    and status['received_ns'] > inhibit_ack.observed_steady_ns]
                if candidates:
                    replacement_status = candidates[-1]
                    break
                await io.pause(min(.005, max(0., (status_deadline-io.now())/1e9)))
            if replacement_status is None:
                raise TimeoutError('R07c replacement backend zero status not observed after INHIBIT')
            checked = verify_r07c_backend_restart(original_proof=io.contact_ack,
                old_backend_instance_id=old_backend, old_process=restart['old_process'],
                replacement=restart['replacement'], old_identity_rejection=old_rejection,
                query_ack=query_ack, inhibit_ack=inhibit_ack,
                replacement_status=replacement_status)
            io.emit('B23_R07C_BACKEND_RESTART_VERIFIED', {
                'checked':checked,'restart':restart,
                'old_control_request_cdr_hex':old_rejection.request_bytes.hex(),
                'old_control_response_cdr_hex':old_rejection.response_bytes.hex(),
                'query_request_cdr_hex':query_ack.request_bytes.hex(),
                'query_response_cdr_hex':query_ack.response_bytes.hex(),
                'inhibit_request_cdr_hex':inhibit_ack.request_bytes.hex(),
                'inhibit_response_cdr_hex':inhibit_ack.response_bytes.hex(),
                'replacement_status':replacement_status,'steady_ns':io.now()})
            outcome = {'case':'R07c', **checked,'completed_ns':time.monotonic_ns()}
        elif packet['case'] == 'R07d':
            if packet['fault_hooks'] or io.contact_ack is None:
                raise RuntimeError('R07d requires a clean packet and verified contact proof')
            from mecanum_nav_rl_interfaces.msg import SimulationContactState
            old_publisher = int(io.descriptor['final_publisher_instance_id'])
            await prepare_r07d_final_publisher_restart(io, b1, packet)
            restart = await io.request_owned_restart(case='R07d', target_role='final')
            replacement = dict(restart['replacement'])
            if Path(replacement['binding_ack_path']).exists():
                replacement['binding_ack_exists'] = True
            else:
                replacement['binding_ack_exists'] = False
            inhibit_ack = await io.control.inhibit(
                deadline_ns=min(io.deadline_ns, io.now()+1_000_000_000))
            expected_fault_flags = r07d_restart_fault_flags()
            state = await io.until(lambda: r07d_post_restart_zero_status(io.ingress, inhibit_ack),
                deadline_ns=min(io.deadline_ns, io.now()+1_000_000_000),
                phase='R07d post-restart native zero/inhibit status',
                expected_native_fault_flags=expected_fault_flags)
            status = r07d_backend_status_record(state, io.ingress.backend_received_ns)
            new_receipts = [receipt.final_publish_sequence for receipt in io.ingress.receipts
                if receipt.final_publisher_instance_id == replacement['publisher_instance_id']]
            checked = verify_r07d_final_publisher_restart(
                old_publisher_instance_id=old_publisher,
                old_process=restart['old_process'], replacement=replacement,
                backend_status=status, inhibit_ack=inhibit_ack, new_receipts=new_receipts)
            io.emit('B23_R07D_FINAL_PUBLISHER_RESTART_VERIFIED', {
                'checked':checked,'restart':restart,'inhibit_request_cdr_hex':inhibit_ack.request_bytes.hex(),
                'inhibit_response_cdr_hex':inhibit_ack.response_bytes.hex(),
                'backend_status':status,'steady_ns':io.now()})
            outcome = {'case':'R07d', **checked,'completed_ns':time.monotonic_ns()}
        elif packet['case'] in ('R02a','R02b'):
            if packet['case'] == 'R02b':
                expected_env = case_environment(packet['case'], packet['fault_hooks'])
                if any(packet['environment'].get(key) != value for key, value in expected_env.items()):
                    raise RuntimeError('R02b admission order hook environment does not match packet')
            target = ResetTarget(**packet['reset_target'])
            await io.reset_episode(b1, seed=packet['episode_seeds'][0], target=target, paused_hold_s=.250)
            step_started_ns = time.monotonic_ns()
            transition = await io.policy_step(b1, (0.4, 0., 0.),
                align_admission_after_scan_boundary=packet['case'] == 'R02b',
                require_admission_before_receipt=packet['case'] == 'R02a')
            if transition.termination.terminated or transition.termination.truncated:
                raise RuntimeError('R02 target POLICY step terminated before order proof')
            evidence_end = min(io.deadline_ns, time.monotonic_ns()+500_000_000)
            while time.monotonic_ns() < evidence_end:
                io.read_native_input_watermark()
                path = Path(descriptor['native_events_path'])
                records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []
                if (any(row.get('kind') == 'B23_POLICY_RECEIPT_INGRESS' for row in records)
                        and any(row.get('kind') == 'B23_ADMISSION_ACCEPTED' for row in records)):
                    break
                await io.pause(min(.005, max(0., (evidence_end-time.monotonic_ns())/1e9)))
            order = verify_r02_policy_order(descriptor['run_root'], case=packet['case'],
                step_started_ns=step_started_ns)
            outcome = {'case':packet['case'],'resets_confirmed':1,'policy_steps_committed':1,
                'native_order':order,'completed_ns':time.monotonic_ns()}
        elif packet['case'] in ('R02c', 'R02d'):
            expected_env = case_environment(packet['case'], packet['fault_hooks'])
            if any(packet['environment'].get(key) != value for key, value in expected_env.items()):
                raise RuntimeError(packet['case'] + ' delayed receipt hook environment does not match packet')
            target = ResetTarget(**packet['reset_target'])
            await io.reset_episode(b1, seed=packet['episode_seeds'][0], target=target,
                paused_hold_s=.250)
            close = 'safe_stop' if packet['case'] == 'R02c' else 'admission_inhibited'
            checked = await io.policy_step(b1, (0.4, 0., 0.), close_after_held_receipt=close)
            if checked.get('expected_rejection') is not True:
                raise RuntimeError(packet['case'] + ' did not reject the late POLICY receipt')
            outcome = {'case':packet['case'], 'resets_confirmed':1,
                'policy_steps_committed':0, **checked, 'completed_ns':time.monotonic_ns()}
        elif packet['case'] == 'R02e':
            if packet['fault_hooks'] != ['pre_bind_admission_sample']:
                raise RuntimeError('R02e packet hook does not match the fixed pre-bind admission case')
            target = ResetTarget(**packet['reset_target'])
            await io.reset_episode(b1, seed=packet['episode_seeds'][0], target=target,
                paused_hold_s=.250)
            first = await io.policy_step(b1, (0.2, 0., 0.))
            if first.termination.terminated or first.termination.truncated:
                raise RuntimeError('R02e first POLICY slot terminated before pre-bind test')
            second = await io.policy_step(b1, (0.2, 0., 0.), prebind_admission=True)
            if second.termination.terminated or second.termination.truncated:
                raise RuntimeError('R02e second POLICY slot terminated before fresh token check')
            outcome = {'case':'R02e','resets_confirmed':1,'policy_steps_committed':2,
                'prebind_admission':io._last_prebind_check,'completed_ns':time.monotonic_ns()}
        elif packet['case'] == 'R02f':
            if packet['fault_hooks'] != ['safety_hold_after_adapter_issuance']:
                raise RuntimeError('R02f packet hook does not match the fixed Safety hold case')
            target = ResetTarget(**packet['reset_target'])
            await io.reset_episode(b1, seed=packet['episode_seeds'][0], target=target,
                paused_hold_s=.250)
            checked = await io.policy_step(b1, (0.4, 0., 0.), hold_after_adapter_issuance=True)
            if checked.get('expected_rejection') is not True:
                raise RuntimeError('R02f Safety hold did not produce the expected fail-closed path')
            outcome = {'case':'R02f','resets_confirmed':1,'policy_steps_committed':0,
                **checked,'completed_ns':time.monotonic_ns()}
        elif packet['case'] == 'R02g':
            if packet['fault_hooks'] != ['closing_paths_after_policy_nonzero']:
                raise RuntimeError('R02g packet hook does not match the fixed closing-path case')
            target = ResetTarget(**packet['reset_target'])
            await io.reset_episode(b1, seed=packet['episode_seeds'][0], target=target,
                paused_hold_s=.250)
            checked_routes = []
            for route in ('safe_stop', 'admission_inhibited', 'zero_only', 'op_inhibit'):
                transition = await io.policy_step(b1, (0.25, 0., 0.))
                if transition.termination.terminated or transition.termination.truncated:
                    raise RuntimeError('R02g POLICY step terminated before closing-path check: ' + route)
                adapter = io.safety.local_training
                safe_stop_before = adapter.safe_stop_sequence
                if route == 'safe_stop':
                    adapter.set_policy_hold(True)
                    adapter.set_stream_enabled(True)
                elif route in ('admission_inhibited', 'zero_only'):
                    r02g_close_admission(io, adapter, zero_only=(route == 'zero_only'))
                else:
                    from mecanum_nav_rl_interfaces.msg import SimulationContactState
                    # OP_INHIBIT is the final route in this matrix. Stop the
                    # Safety timer before dispatch so a concurrent SAFE_STOP
                    # cannot arrive at the gate after the native operation
                    # invalidates it.
                    adapter.set_stream_enabled(False)
                    adapter.set_policy_hold(True)
                    io.ingress.inhibit()
                    control_ack = await io.control.transact(r02g_inhibit_operation(),
                        deadline_ns=min(io.deadline_ns, io.now() + 1_000_000_000))
                    # Native gate invalidation reports the now-closed active
                    # POLICY slot as sequence+stale while retaining zero.
                    state = await io.until(lambda: io.ingress.backend_state
                        if io.ingress.backend_state is not None
                        and io.ingress.backend_state.local_zero_override
                        and io.ingress.backend_state.status_sequence > 0 else None,
                        deadline_ns=min(io.deadline_ns, io.now() + 1_000_000_000),
                        phase='R02g native OP_INHIBIT zero state',
                        expected_native_fault_flags=(SimulationContactState.FAULT_COMMAND_SEQUENCE
                            | SimulationContactState.FAULT_COMMAND_STALE))
                    result = verify_r02g_close(io, route=route,
                        policy_receipt_count=len(io.ingress.receipts), backend_state=state,
                        control_ack=control_ack)
                    io.emit('R02G_CLOSING_PATH_VERIFIED', {**result,
                        'policy_transition_id':b1.lifecycle.snapshot.committed_transition_ids[-1],
                        'control_request_cdr_hex':control_ack.request_bytes.hex(),
                        'control_response_cdr_hex':control_ack.response_bytes.hex(),
                        'steady_ns':io.now()})
                    checked_routes.append(result)
                    continue
                stop = await io.until(lambda: adapter.last_output
                    if adapter.last_output is not None
                    and adapter.last_output.source == adapter.last_output.SOURCE_SAFE_STOP
                    and adapter.last_output.sequence > safe_stop_before else None,
                    deadline_ns=min(io.deadline_ns, io.now() + 1_000_000_000),
                    phase='R02g closing SAFE_STOP output: ' + route)
                receipt = await io.until(lambda: io.final.publication_for_source_sequence(
                    source=stop.SOURCE_SAFE_STOP, sequence=stop.sequence),
                    deadline_ns=min(io.deadline_ns, io.now() + 1_000_000_000),
                    phase='R02g closing SAFE_STOP receipt: ' + route)
                state = await io.until(lambda: io.ingress.backend_state
                    if io.ingress.backend_state is not None
                    and io.ingress.backend_state.applied_receipt_valid
                    and not io.ingress.backend_state.local_zero_override
                    and io.ingress.backend_state.applied_final_publisher_instance_id == receipt.final_publisher_instance_id
                    and io.ingress.backend_state.applied_final_publish_sequence == receipt.final_publish_sequence else None,
                    deadline_ns=min(io.deadline_ns, io.now() + 1_000_000_000),
                    phase='R02g native SAFE_STOP application: ' + route)
                result = verify_r02g_close(io, route=route,
                    policy_receipt_count=len(io.ingress.receipts), zero_receipt=receipt,
                    backend_state=state)
                io.emit('R02G_CLOSING_PATH_VERIFIED', {**result,
                    'safe_stop_sequence':stop.sequence,
                    'policy_transition_id':b1.lifecycle.snapshot.committed_transition_ids[-1],
                    'steady_ns':io.now()})
                checked_routes.append(result)
                await io.inhibit_and_drain(deadline_ns=min(io.deadline_ns,
                    io.now() + 1_000_000_000), zero_only=(route == 'zero_only'))
            expected_routes = {'safe_stop','admission_inhibited','zero_only','op_inhibit'}
            if {item['route'] for item in checked_routes} != expected_routes:
                raise RuntimeError('R02g did not verify every production closing route')
            outcome = {'case':'R02g','resets_confirmed':1,'policy_steps_committed':4,
                'closing_paths':checked_routes,'completed_ns':time.monotonic_ns()}
        elif packet['case'] in ('R03a', 'R03b'):
            expected_env = case_environment(packet['case'], packet['fault_hooks'])
            if any(packet['environment'].get(key) != value for key, value in expected_env.items()):
                raise RuntimeError(packet['case'] + ' native receipt fault environment does not match packet')
            target = ResetTarget(**packet['reset_target'])
            await io.reset_episode(b1, seed=packet['episode_seeds'][0], target=target,
                paused_hold_s=.250)
            try:
                await io.policy_step(b1, (0.4, 0., 0.))
            except Exception as exc:
                active_identity = b1.lifecycle.snapshot.active_transition_identity
                if active_identity is None:
                    raise RuntimeError('R03 failure lost the owned B1 pending-step identity') from exc
                checked = await verify_r03_receipt_fault(io, case=packet['case'],
                    step_index=active_identity.step_index, error=exc)
                aborted = b1.lifecycle.abort_step(packet['case'] + '_native_receipt_fault')
                outcome = {'case':packet['case'], 'resets_confirmed':1,
                    'policy_steps_committed':0, 'b1_abort_status':str(aborted.status),
                    **checked, 'completed_ns':time.monotonic_ns()}
            if outcome is None:
                raise RuntimeError(packet['case'] + ' expected native receipt fault was not observed')
        elif packet['case'] in ('R04a', 'R04b', 'R04c', 'R04d'):
            target = ResetTarget(**packet['reset_target'])
            await io.reset_episode(b1, seed=packet['episode_seeds'][0], target=target,
                paused_hold_s=.250)
            if packet['case'] == 'R04d':
                prior_commits = len([row for row in Path(packet['run_root'],
                    'b1_transition_committed.jsonl').read_text().splitlines() if row.strip()]) \
                    if Path(packet['run_root'], 'b1_transition_committed.jsonl').exists() else 0
                state = install_r04_delivery_fault(io.safety.local_training,
                    packet['case'], io.emit)
                io._r04d_fault_state = state
                marker_armed_ns = io.now()
                baseline_lifecycle = io.ingress.lifecycle
                if baseline_lifecycle is None:
                    raise RuntimeError('R04d requires a bound lifecycle before fault arming')
                marker_path = Path(packet['run_root'])/'r04d-final-lifecycle-delay.json'
                marker_write_started_ns = io.now()
                io.emit('R04D_MARKER_WRITE_STARTED', {
                    'steady_ns': marker_write_started_ns,
                    'path': str(marker_path)})
                marker_sha256 = await write_record_once_async(marker_path, {
                    'schema':'b23_r04d_delay_marker/v1', 'run_id':packet['run_id'],
                    'invocation_id':io.descriptor['invocation_id'],
                    'baseline_sequence':int(baseline_lifecycle.sequence),
                    'baseline_identity':[int(baseline_lifecycle.episode_generation),
                        int(baseline_lifecycle.reset_epoch), int(baseline_lifecycle.runtime_generation)],
                    'armed_ns':marker_armed_ns,
                    'delay_ns':700_000_000,
                    'safe_stop_source_instance_id':int(io.safe_stop_source_id),
                    'reason':'hold final lifecycle delivery and a mismatched new-context SAFE_STOP receipt until the R04d stale-Safety observation window closes'})
                marker_write_completed_ns = io.now()
                io.emit('R04D_MARKER_WRITE_COMPLETED', {
                    'steady_ns': marker_write_completed_ns,
                    'started_ns': marker_write_started_ns,
                    'duration_ns': marker_write_completed_ns - marker_write_started_ns,
                    'sha256': marker_sha256})
                io.emit('B23_R04_FAULT_ARMED', {'case':'R04d',
                    'next_operation':'lifecycle reset event', 'steady_ns':io.now(),
                    'final_lifecycle_delay_ns':700_000_000,
                    'marker_sha256':marker_sha256,
                    'marker_write_duration_ns':marker_write_completed_ns-marker_write_started_ns,
                    'final_lifecycle_baseline_sequence':int(baseline_lifecycle.sequence)})
                fault_lifecycle = await io.lifecycle_event(rearm=False,
                    deadline_ns=min(io.deadline_ns, io.now() + 2_000_000_000))
                await io.until(lambda: state if state['scheduled'] >= 1 and state['delivered'] >= 1 else None,
                    deadline_ns=min(io.deadline_ns, io.now() + 2_000_000_000),
                    phase='R04d delayed lifecycle callback completion')
                if state['scheduled'] != 1 or state['delivered'] != 1:
                    raise RuntimeError('R04d delayed lifecycle callback did not complete exactly once')
                scheduled = next((facts for name, facts in io.events
                    if name == 'B23_R04_DELIVERY_DELAY_SCHEDULED' and facts.get('case') == 'R04d'), None)
                delayed = next((facts for name, facts in io.events
                    if name == 'B23_R04_DELIVERY_DELAYED_CALLBACK' and facts.get('case') == 'R04d'), None)
                if (scheduled is None or delayed is None or scheduled.get('source_stamp_ns') is None
                        or type(delayed.get('delivery_ns')) is not int):
                    raise RuntimeError('R04d delayed lifecycle callback evidence is incomplete')
                verification_deadline_ns = min(io.deadline_ns, io.now() + 2_000_000_000)
                expected_lifecycle_identity = [int(fault_lifecycle.episode_generation),
                    int(fault_lifecycle.reset_epoch), int(fault_lifecycle.runtime_generation)]
                final_path = Path(packet['run_root'])/'final-events.jsonl'
                final_lifecycle_delivery = await io.until(lambda:
                    r04d_final_lifecycle_delivery(
                        _ledger_rows(packet['run_root'], 'final-events.jsonl') if final_path.exists() else [],
                        sequence=fault_lifecycle.sequence, identity=expected_lifecycle_identity),
                    deadline_ns=verification_deadline_ns,
                    phase='R04d exact final-publisher lifecycle delivery')
                ingress_scheduled = next((facts for name, facts in io.events
                    if name == 'B23_R04_INGRESS_DELIVERY_SCHEDULED' and facts.get('case') == 'R04d'), None)
                ingress_delivered = await io.until(lambda: next((facts for name, facts in io.events
                    if name == 'B23_R04_INGRESS_DELIVERY_COMPLETED' and facts.get('case') == 'R04d'), None),
                    deadline_ns=verification_deadline_ns,
                    phase='R04d exact ingress lifecycle delivery')
                rejected = await io.until(lambda: r04d_stale_safety_rejection_after_delivery(
                    io.events, delivery_ns=final_lifecycle_delivery['delivery_ns'],
                    source_stamp_ns=scheduled['source_stamp_ns']),
                    deadline_ns=verification_deadline_ns,
                    phase='R04d delivered stale lifecycle rejected by actual Safety')
                final_rows = _ledger_rows(packet['run_root'], 'final-events.jsonl') if final_path.exists() else []
                held_zero = [row['facts'] for row in final_rows
                    if row.get('event') == 'R04D_FINAL_NEW_CONTEXT_SAFE_STOP_HELD'
                    and row.get('facts', {}).get('identity') == expected_lifecycle_identity]
                published_new_context = [row['facts'] for row in final_rows
                    if row.get('event') == 'FINAL_PUBLISHED'
                    and int(row.get('facts', {}).get('steady_ns', 0)) >= marker_armed_ns
                    and row.get('facts', {}).get('identity') != [int(baseline_lifecycle.episode_generation),
                        int(baseline_lifecycle.reset_epoch), int(baseline_lifecycle.runtime_generation)]]
                if (scheduled is None or delayed is None or scheduled.get('source_stamp_ns') is None
                        or delayed['delivery_ns'] - scheduled['callback_received_ns'] < 650_000_000
                        or rejected['steady_ns'] < final_lifecycle_delivery['delivery_ns']
                        or rejected.get('ros_ns', 0) - scheduled['source_stamp_ns'] <= 500_000_000
                        or ingress_scheduled is None or ingress_delivered is None
                        or ingress_scheduled.get('source_stamp_ns') != scheduled.get('source_stamp_ns')
                        or ingress_delivered.get('source_stamp_ns') != scheduled.get('source_stamp_ns')
                        or final_lifecycle_delivery is None
                        or not r04d_final_publisher_precedes_ingress(
                            final_lifecycle_delivery.get('delivery_ns'), ingress_delivered.get('delivery_ns'))
                        or ingress_delivered['delivery_ns'] - ingress_scheduled['received_ns'] <= 500_000_000
                        or state.get('repeat_held', 0) < 1
                        or state.get('ingress_repeats_held', 0) < 1
                        or not held_zero or published_new_context):
                    raise RuntimeError('R04d Safety rejection is not bound to delayed stale lifecycle source')
                issued_path = Path(packet['run_root'])/'policy_adapter_issued.jsonl'
                commit_path = Path(packet['run_root'])/'b1_transition_committed.jsonl'
                issued_count = len([row for row in issued_path.read_text().splitlines() if row.strip()]) \
                    if issued_path.exists() else 0
                commit_count = len([row for row in commit_path.read_text().splitlines() if row.strip()]) \
                    if commit_path.exists() else 0
                if issued_count != 0 or commit_count != prior_commits:
                    raise RuntimeError('R04d stale lifecycle fault advanced POLICY/B1')
                outcome = {'case':'R04d','resets_confirmed':1,'policy_steps_committed':0,
                    'stale_rejection_reason':'LIFECYCLE_STALE_OR_FUTURE',
                    'rejected_steady_ns':rejected['steady_ns'], 'delayed_callbacks':state['scheduled'],
                    'safety_repeat_callbacks_held':state['repeat_held'],
                    'ingress_repeat_callbacks_held':state['ingress_repeats_held'],
                    'final_new_context_safe_stop_held':len(held_zero),
                    'final_new_context_receipts_published':len(published_new_context),
                    'source_stamp_ns':scheduled['source_stamp_ns'],
                    'source_ros_age_ns':rejected['ros_ns']-scheduled['source_stamp_ns'],
                    'no_policy_issued':True,'b1_commits_before_fault':prior_commits,
                    'completed_ns':time.monotonic_ns()}
            else:
                initial_fault_case, followup_fault_case = r04_policy_step_fault_plan(packet['case'])
                try:
                    transition = await io.policy_step(b1, (0.25, 0., 0.),
                        measurement_fault_case=initial_fault_case)
                except (TimeoutError, RuntimeError) as error:
                    if packet['case'] not in ('R04a', 'R04b'):
                        raise
                    if packet['case'] == 'R04a':
                        state = io._r04_fault_state
                        if state['triggered'] != 1 or state['scheduled'] != 1:
                            raise RuntimeError('R04a fault did not schedule exactly one delayed callback') from error
                        from mecanum_nav_rl_interfaces.msg import SimulationContactState
                        expected_error = (isinstance(error, TimeoutError)
                            or (isinstance(error, RuntimeError)
                                and str(error) in (
                                    'native fault flags=' + str(
                                        SimulationContactState.FAULT_COMMAND_STALE),
                                    'native fault flags=' + str(
                                        SimulationContactState.FAULT_COMMAND_SEQUENCE
                                        | SimulationContactState.FAULT_COMMAND_STALE))))
                        if not expected_error:
                            raise RuntimeError('R04a step ended outside its timeout/watchdog fail-closed path') from error
                        await await_r04a_delayed_callback(io, state)
                        rejected = await await_r04a_production_rejection(io,
                            deadline_ns=min(io.deadline_ns, io.now() + 1_000_000_000))
                        await await_r04a_post_rejection_zero(io, rejected,
                            deadline_ns=min(io.deadline_ns, io.now() + 1_000_000_000))
                        checked = verify_r04_stale_delivery(io, case='R04a')
                        active = b1.lifecycle.snapshot.active_transition_identity
                        blocked_step = (active.step_index if active is not None
                            else b1.lifecycle.snapshot.step_index + 1)
                        blocked = verify_r04a_next_step_blocked(io, step_index=blocked_step)
                        zero_baseline = verify_r04a_zero_baseline(io, checked=blocked)
                        if any(getattr(item, 'source', None) == 1 for item in io.ingress.receipts):
                            raise RuntimeError('R04a POLICY receipt reached native ingress after delay fault')
                        aborted = b1.lifecycle.abort_step('R04a_delayed_noisy_input_rejected')
                        outcome = {'case':'R04a','resets_confirmed':1,'policy_steps_committed':0,
                            'expected_rejection':True, **checked, **blocked,
                            'safe_stop_applied':True, 'safe_stop_baseline':zero_baseline,
                            'b1_abort_status':str(aborted.status),
                            'exception':repr(error),'completed_ns':time.monotonic_ns()}
                    else:
                        if isinstance(error, RuntimeError) and not str(error).startswith('native fault flags='):
                            raise
                        state = io._r04_fault_state
                        if state['triggered'] == 0:
                            raise RuntimeError('R04b timeout lacked dropped noisy input evidence') from error
                        run_root = Path(packet['run_root'])
                        issued_rows = (_ledger_rows(run_root, 'policy_adapter_issued.jsonl')
                            if (run_root/'policy_adapter_issued.jsonl').exists() else [])
                        verify_r04b_missing_noisy_admission(
                            issued_rows=issued_rows,
                            transition_identity=b1.lifecycle.snapshot.active_transition_identity,
                            run_id=packet['run_id'],
                            invocation_id=io.descriptor['invocation_id'],
                            policy_receipts=io.ingress.receipts,
                            final_rows=(_ledger_rows(run_root, 'policy_final_published.jsonl')
                                if (run_root/'policy_final_published.jsonl').exists() else []),
                            applied_rows=(_ledger_rows(run_root, 'policy_backend_applied.jsonl')
                                if (run_root/'policy_backend_applied.jsonl').exists() else []),
                            committed_rows=(_ledger_rows(run_root, 'b1_transition_committed.jsonl')
                                if (run_root/'b1_transition_committed.jsonl').exists() else []),
                            worker_events=io.events)
                        aborted = b1.lifecycle.abort_step('R04b_noisy_odometry_dropped')
                        native_state = io.ingress.backend_state
                        if isinstance(error, RuntimeError) and (native_state is None
                                or not native_state.local_zero_override or native_state.fault_flags == 0):
                            raise RuntimeError('R04b native fault did not prove local zero override') from error
                        if isinstance(error, TimeoutError):
                            stop = io.safety.local_training.last_output
                            if (native_state is None or native_state.local_zero_override
                                    or native_state.fault_flags != 0 or stop is None
                                    or stop.source != stop.SOURCE_SAFE_STOP
                                    or any((stop.twist.linear.x, stop.twist.linear.y, stop.twist.angular.z))):
                                raise RuntimeError('R04b timeout lacks a healthy applied-zero baseline') from error
                            receipt = io.final.publication_for_source_sequence(
                                source=stop.SOURCE_SAFE_STOP, sequence=stop.sequence)
                            if (receipt is None or native_state.applied_final_publisher_instance_id != receipt.final_publisher_instance_id
                                    or native_state.applied_final_publish_sequence != receipt.final_publish_sequence
                                    or not native_state.applied_receipt_valid):
                                raise RuntimeError('R04b timeout lacks exact native SAFE_STOP application') from error
                        if any(getattr(item, 'source', None) == 1 for item in io.ingress.receipts):
                            raise RuntimeError('R04b POLICY receipt reached the native ingress')
                        outcome = {'case':'R04b','resets_confirmed':1,'policy_steps_committed':0,
                            'expected_rejection':True,'failure_mode':'post-ACK noisy admission was dropped before Safety received it',
                            'dropped_policy_inputs':state['triggered'],
                            'pre_safety_candidate_verified':True,
                            'native_fault_flags':0 if native_state is None else native_state.fault_flags,
                            'local_zero_override':False if native_state is None else native_state.local_zero_override,
                            'baseline_zero_application_sequence':(native_state.applied_final_publish_sequence
                                if isinstance(error, TimeoutError) else None),
                            'exception':repr(error),
                            'b1_abort_status':str(aborted.status),'completed_ns':time.monotonic_ns()}
                else:
                    if packet['case'] == 'R04a':
                        state = io._r04_fault_state
                        await io.until(lambda: state if state['delivered'] == 1 else None,
                            deadline_ns=min(io.deadline_ns, io.now() + 1_000_000_000),
                            phase='R04a bounded delayed callback completion')
                        await await_r04a_production_rejection(io,
                            deadline_ns=min(io.deadline_ns, io.now() + 1_000_000_000))
                        checked = verify_r04_stale_delivery(io, case='R04a')
                        blocked_step = transition.transition_identity.step_index + 1
                        blocked_step_timeout = None
                        try:
                            await io.policy_step(b1, (0.25, 0., 0.))
                        except TimeoutError as error:
                            blocked_step_timeout = repr(error)
                            blocked = verify_r04a_next_step_blocked(io, step_index=blocked_step)
                            disposition = abort_r04a_pending_step_if_active(
                                b1.lifecycle, expected_step_index=blocked_step)
                        else:
                            raise RuntimeError('R04a next POLICY slot completed after delayed-input invalidation')
                        outcome = {'case':'R04a','resets_confirmed':1,
                            'policy_steps_committed':1, **checked, **blocked,
                            'safe_stop_applied':True,
                            'b1_step_disposition':disposition,
                            'blocked_step_timeout':blocked_step_timeout,
                            'completed_ns':time.monotonic_ns()}
                    elif packet['case'] == 'R04c':
                        blocked_step = transition.transition_identity.step_index + 1
                        blocked_step_timeout = None
                        stale_commit_rejection = None
                        try:
                            await io.policy_step(b1, (0.25, 0., 0.),
                                measurement_fault_case=followup_fault_case)
                        except (TimeoutError, RuntimeError) as error:
                            blocked_step_timeout = repr(error)
                            state = require_r04c_fault_state(io, error)
                            await io.until(lambda: state if state['triggered'] == 1
                                and state['delivered'] == 1 else None,
                                deadline_ns=min(io.deadline_ns, io.now() + 1_000_000_000),
                                phase='R04c bounded delayed scan delivery')
                            delayed = next((facts for name, facts in reversed(io.events)
                                if name == 'B23_R04_DELIVERY_DELAYED_CALLBACK'
                                and facts.get('case') == 'R04c'), None)
                            if (state['triggered'] != 1 or state['delivered'] != 1
                                    or delayed is None):
                                raise RuntimeError('R04c delayed scan callback did not complete exactly once') from error
                            checked = verify_r04_stale_delivery(io, case='R04c')
                            blocked = verify_r04c_next_step_blocked(io,
                                step_index=blocked_step,
                                delayed_delivery_ns=delayed['delivery_ns'])
                            disposition = abort_r04a_pending_step_if_active(
                                b1.lifecycle, expected_step_index=blocked_step,
                                reason='R04c_stale_scan_blocked_next_slot')
                        except ValueError as error:
                            # The command can be applied before the injected
                            # scan arrives. B1 must nevertheless reject the
                            # step if waiting for its exact cutoff lets the
                            # issuance receipt exceed the fixed 500 ms age.
                            if str(error) != (
                                    'B1 transition commit rejected: POLICY issuance receipt is stale or invalid'):
                                raise
                            error_steady_ns = io.now()
                            state = require_r04c_fault_state(io, error)
                            await io.until(lambda: state if state['triggered'] == 1
                                and state['delivered'] == 1 else None,
                                deadline_ns=min(io.deadline_ns, io.now() + 1_000_000_000),
                                phase='R04c bounded delayed scan delivery after stale B1 rejection')
                            delayed = next((facts for name, facts in reversed(io.events)
                                if name == 'B23_R04_DELIVERY_DELAYED_CALLBACK'
                                and facts.get('case') == 'R04c'), None)
                            if (state['triggered'] != 1 or state['delivered'] != 1
                                    or delayed is None):
                                raise RuntimeError('R04c delayed scan callback did not complete exactly once') from error
                            stale_commit_rejection = verify_r04c_stale_issuance_commit_rejected(
                                io, step_index=blocked_step, error=error,
                                error_steady_ns=error_steady_ns,
                                delayed_delivery=delayed)
                            io.emit('R04C_B1_STALE_ISSUANCE_COMMIT_REJECTED', {
                                **stale_commit_rejection,
                                'error':str(error),
                                'steady_ns':error_steady_ns})
                            stale_zero = await await_r04c_stale_scan_zero(
                                io, delayed_delivery_ns=delayed['delivery_ns'],
                                step_index=blocked_step)
                            disposition = abort_r04a_pending_step_if_active(
                                b1.lifecycle, expected_step_index=blocked_step,
                                reason='R04c_stale_POLICY_issuance_rejected_at_B1')
                        else:
                            # One delayed scan is an out-of-order sample, not a
                            # 650 ms sensor outage: fresh scans may legitimately
                            # complete this step before the delayed callback.
                            # Wait for the injected sample, prove Safety rejects
                            # it and applies zero, then prove recovery on a later
                            # POLICY slot using fresh scan data.
                            state = io._r04_fault_state
                            await io.until(lambda: state if state['triggered'] == 1
                                and state['delivered'] == 1 else None,
                                deadline_ns=min(io.deadline_ns, io.now() + 1_000_000_000),
                                phase='R04c bounded delayed scan delivery after in-flight step')
                            delayed = next((facts for name, facts in reversed(io.events)
                                if name == 'B23_R04_DELIVERY_DELAYED_CALLBACK'
                                and facts.get('case') == 'R04c'), None)
                            if delayed is None:
                                raise RuntimeError('R04c delayed scan callback has no evidence')
                            stale_zero = await io.until(
                                lambda: verify_r04c_stale_rejection_and_zero(io,
                                    delayed_delivery_ns=delayed['delivery_ns'],
                                    step_index=blocked_step),
                                deadline_ns=min(io.deadline_ns, io.now() + 1_000_000_000),
                                phase='R04c stale scan Safety rejection and applied zero')
                            recovery_step = blocked_step + 1
                            recovered = await io.policy_step(b1, (0.25, 0., 0.))
                            if recovered.transition_identity.step_index != recovery_step:
                                raise RuntimeError('R04c fresh recovery used an unexpected POLICY slot')
                            checked = verify_r04_stale_delivery(io, case='R04c',
                                policy_step_index=recovery_step)
                            if not checked['fresh_policy_recovery']:
                                raise RuntimeError('R04c did not recover from stale scan on fresh input')
                            committed_steps = sum(1 for name, facts in io.events
                                if name == 'b1_transition_committed'
                                and facts.get('step_index') in (transition.transition_identity.step_index,
                                    blocked_step, recovery_step))
                            if committed_steps != 3:
                                raise RuntimeError('R04c control, in-flight, and recovery commits are incomplete')
                            outcome = {'case':'R04c','resets_confirmed':1,
                                'policy_steps_committed':committed_steps,
                                'delayed_step_committed_before_delivery':True,
                                'stale_scan_safety_disposition':stale_zero,
                                'fresh_recovery_step_index':recovery_step,
                                **checked,'completed_ns':time.monotonic_ns()}
                        if blocked_step_timeout is not None:
                            outcome = {'case':'R04c','resets_confirmed':1,
                                'policy_steps_committed':1, **checked, **blocked,
                                'safe_stop_applied':True,
                                'b1_step_disposition':disposition,
                                'blocked_step_timeout':blocked_step_timeout,
                                'completed_ns':time.monotonic_ns()}
                        elif stale_commit_rejection is not None:
                            checked = verify_r04_stale_delivery(io, case='R04c')
                            outcome = {'case':'R04c','resets_confirmed':1,
                                'policy_steps_committed':1, **checked,
                                **stale_commit_rejection,
                                'stale_scan_safety_disposition':stale_zero,
                                'safe_stop_applied':True,
                                'b1_step_disposition':disposition,
                                'completed_ns':time.monotonic_ns()}
                    else:
                        checked = verify_r04_stale_delivery(io, case=packet['case'],
                            policy_step_index=transition.transition_identity.step_index)
                        outcome = {'case':packet['case'],'resets_confirmed':1,
                            'policy_steps_committed':1, **checked, 'completed_ns':time.monotonic_ns()}
        elif packet['case'] == 'R01a':
            target = ResetTarget(**packet['reset_target'])
            await io.reset_episode(b1, seed=packet['episode_seeds'][0], target=target, paused_hold_s=.250)
            transition = await io.policy_step(b1, (0.4, 0., 0.))
            if transition.termination.terminated or transition.termination.truncated:
                raise RuntimeError('R01a first POLICY terminated before active reset')
            await io.reset_episode(b1, seed=packet['episode_seeds'][1], target=target, paused_hold_s=.250)
            outcome = {'case': 'R01a', 'resets_confirmed': 2, 'policy_steps_committed': 1,
                'completed_ns': time.monotonic_ns()}
        elif packet['case'] == 'R01e':
            target = ResetTarget(**packet['reset_target'])
            await io.reset_episode(b1, seed=packet['episode_seeds'][0], target=target, paused_hold_s=.250)
            replay = await io.replay_pause_intent_after_terminal()
            outcome = {'case': 'R01e', 'resets_confirmed': 1,
                'pause_request_sequence': replay.request.request_sequence,
                'exact_terminal_replay': True, 'completed_ns': time.monotonic_ns()}
        elif packet['case'] == 'R01b':
            target = ResetTarget(**packet['reset_target'])
            try:
                await io.reset_episode(b1, seed=packet['episode_seeds'][0], target=target,
                    paused_hold_s=.250)
            except Exception as exc:
                checked = verify_r01b_external_pause_rejection(io, exc)
                outcome = {'case':'R01b', 'expected_rejection':True, **checked,
                    'completed_ns':time.monotonic_ns()}
            if outcome is None:
                raise RuntimeError('R01b expected unexpected-pause rejection was not observed')
        elif packet['case'] in ('R01c', 'R01d'):
            expected_env = case_environment(packet['case'], packet['fault_hooks'])
            if any(packet['environment'].get(key) != value for key, value in expected_env.items()):
                raise RuntimeError('native pause ACK fault environment does not match packet case')
            target = ResetTarget(**packet['reset_target'])
            try:
                await io.reset_episode(b1, seed=packet['episode_seeds'][0], target=target,
                    paused_hold_s=.250)
            except Exception as exc:
                checked = await verify_r01_pause_ack_failure(io, exc)
                outcome = {'case':packet['case'], 'expected_pause_ack_failure':True, **checked,
                    'completed_ns':time.monotonic_ns()}
            if outcome is None:
                raise RuntimeError(packet['case'] + ' expected pause ACK failure was not observed')
        else:
            raise RuntimeError('case not implemented by this worker; cannot launch other hooks')
        if outcome['completed_ns'] >= descriptor['active_deadline_ns']:
            raise TimeoutError('smoke completed after active deadline')
    except BaseException as exc:
        primary = repr(exc)
        sink.record('WORKER_PRIMARY_ERROR', {'error': primary})
    finally:
        cleanup_started = time.monotonic_ns()
        cleanup_deadline = min(descriptor['total_deadline_ns'], cleanup_started + 60_000_000_000)
        write_record_once(Path(descriptor['run_root'])/'worker-cleanup-start.json', {
            'run_id':descriptor['run_id'], 'invocation_id':descriptor['invocation_id'],
            'started_ns':cleanup_started, 'deadline_ns':cleanup_deadline})
        if io is not None:
            fault_state = getattr(io, '_r04_fault_state', None)
            if fault_state is not None:
                for timer in fault_state.get('timers', ()):
                    timer.join(timeout=1.0)
                    if timer.is_alive():
                        cleanup_errors.append('r04_fault_callback_thread_not_joined')
            try:
                clean = await io.stop(deadline_ns=cleanup_deadline)
                cleanup_errors.extend(io.cleanup_errors)
                if not clean and not cleanup_errors:
                    cleanup_errors.append('worker_cleanup_not_clean')
            except BaseException as exc:
                cleanup_errors.append(repr(exc))
                cleanup_errors.extend(io.close_context())
        result = {'primary_error': primary, 'cleanup_errors': cleanup_errors, 'outcome': outcome,
            'cleanup_started_ns': cleanup_started, 'cleanup_deadline_ns': cleanup_deadline,
            'completed_ns': time.monotonic_ns(), 'run_id': descriptor['run_id'],
            'invocation_id': descriptor['invocation_id']}
        write_record_once(Path(descriptor['run_root'])/'worker-result.json', result)
        sink.close()
    return 0 if primary is None and not cleanup_errors and outcome is not None else 1


def verify_packet(path, expected_sha256):
    """Pin mọi input trước spawn; packet không tự cấp thêm phase/hook."""
    import os
    import sys
    import re
    import pwd
    from mecanum_nav_bringup.local_training_launch_contract import load_bound_config
    raw = Path(path).resolve(strict=True).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('packet digest mismatch')
    packet = json.loads(raw)
    import uuid
    try:
        if str(uuid.UUID(packet['session_id'])) != packet['session_id'] or packet['launch_plan']['session_id'] != packet['session_id']:
            raise ValueError('session mismatch')
    except (KeyError,ValueError,TypeError,AttributeError) as error:
        raise ValueError('packet requires matching canonical session UUID') from error
    prefix = Path(packet['install_prefix']).resolve(strict=True)
    expected_hooks = {case: list(hooks) for case, hooks in CASE_HOOKS.items()}
    expected_phase = campaign_phase(packet.get('case'))
    expected_active_s = 900 if packet.get('case') == 'R08' else 120
    expected_seeds = (list(range(2026102900, 2026102930)) if packet.get('case') == 'R08' else
        [2026103028 if packet.get('case') == 'R09a' else 2026103029]
        if packet.get('case') in ('R09a','R09b') else [2026102900,2026102901])
    expected_scenario = {'R09a':'B2_GOAL_SETTLE_V1', 'R09b':'B2_CONTACT_V1'}.get(
        packet.get('case'), 'B2_SOAK_V1')
    if packet.get('case') == 'R09b':
        validate_r09b_task_fixture(packet.get('task_fixture'))
    elif 'task_fixture' in packet:
        raise ValueError('task fixture mutation is only valid for R09b')
    if (packet['schema'] != 'b23_packet/v1' or packet['case'] not in expected_hooks
            or packet['fault_hooks'] != expected_hooks[packet['case']] or packet['gui'] is not False
            or packet.get('world_seed') != 20261029 or packet.get('episode_seeds') != expected_seeds
            or packet['authority'] != 'OWNER_B23_CAMPAIGN_APPROVED'
            or packet.get('owner_decisions', {}).get('phase') != expected_phase
            or (packet['active_s'], packet['cleanup_s']) != (expected_active_s, 60)
            or not re.fullmatch(r'B23_[A-Z0-9_]+', packet['run_id'])
            or len(packet['run_id']) > 64
            or not re.fullmatch(r'b23-[a-z0-9-]+\.service', packet['unit'])
            or os.getuid() != 1000 or pwd.getpwuid(os.getuid()).pw_name != 'hazan'
            or sys.version_info[:3] != (3,12,3) or str(Path(sys.executable).absolute()) != packet['python']):
        raise ValueError('packet authority/profile/phase mismatch')
    ament_prefixes = packet.get('environment', {}).get('AMENT_PREFIX_PATH', '').split(os.pathsep)
    if str(prefix) not in ament_prefixes:
        raise ValueError('runtime AMENT_PREFIX_PATH omits the exact pinned install prefix')
    import importlib
    for name in ('mecanum_nav_rl.runtime_simulation.b23_runner',
                 'mecanum_nav_rl.runtime_simulation.local_training_coordinator',
                 'mecanum_nav_rl.runtime_simulation.local_training_ingress',
                 'mecanum_nav_rl.runtime_safety.final_twist_publisher_node',
                 'mecanum_nav_bringup.local_training_process_supervisor',
                 'mecanum_nav_rl_interfaces.srv'):
        origin = Path(importlib.import_module(name).__file__).resolve(strict=True)
        if not origin.is_relative_to(prefix) or str(origin) not in packet['input_sha256']:
            raise ValueError('runtime import is outside pinned install: ' + str(origin))
    for filename, digest in packet['input_sha256'].items():
        if hashlib.sha256(Path(filename).read_bytes()).hexdigest() != digest:
            raise ValueError('runtime input bytes changed: ' + filename)
    document, config_hash, asset_hash, scenario_id = load_bound_config(Path(packet['resolved_config']))
    if (config_hash != packet['config_hash'] or asset_hash != packet['asset_manifest_sha256']
            or scenario_id != expected_scenario
            or document['map_identity']['training_binding']['binding_status'] != 'BOUND'):
        raise ValueError('packet config/asset/scenario binding mismatch')
    root = Path(packet['run_root']).resolve(strict=True)
    canonical = Path('/home/hazan/mecanum_runtime_evidence').resolve(strict=True)
    if not root.is_relative_to(canonical) or root == canonical:
        raise ValueError('runtime evidence root outside canonical root')
    if Path(packet['guard_path']).parent != Path('/home/hazan/.local/state/ros2_nav2_drl/b23'):
        raise ValueError('guard outside campaign state root')
    if packet['launch_plan']['commands'] != [list(b23_server_argv(packet['launch_plan']['world_file']))]:
        raise ValueError('Gazebo server argv/seed do not match pinned R01a profile')
    if (packet.get('service_properties') != list(service_properties_for(packet.get('active_s')))
            or packet.get('launch_argv_template') != service_launch_command(packet, str(root/'packet.json'), '{PACKET_SHA256}')):
        raise ValueError('packet launch argv/properties do not match source-reviewed template')
    return packet


def _proc_start_ticks(proc_root, pid):
    """Return the start-time identity from a supplied /proc-compatible tree."""
    raw = (Path(proc_root) / str(pid) / 'stat').read_text()
    fields = raw[raw.rfind(')') + 2:].split()
    if len(fields) < 20:
        raise ValueError('proc stat identity is truncated')
    return int(fields[19])


def packet_scan_period_ns(packet):
    """Resolve scan cadence from the packet-pinned and hash-verified config."""
    import math
    from mecanum_nav_bringup.local_training_launch_contract import load_bound_config

    document, config_hash, asset_hash, _scenario_id = load_bound_config(
        Path(packet['resolved_config']))
    if (config_hash != packet['config_hash']
            or asset_hash != packet['asset_manifest_sha256']):
        raise ValueError('scan cadence config/asset binding mismatch')
    rate_hz = document['training']['local_training']['lidar_rate_hz']
    if (isinstance(rate_hz, bool) or not isinstance(rate_hz, (int, float))
            or not math.isfinite(rate_hz) or rate_hz <= 0):
        raise ValueError('packet-pinned LiDAR rate is invalid')
    return round(1_000_000_000 / rate_hz)


def verify_postmortem_residue_attestation(attestation_path, *, run_id, packet_sha256,
        evidence_root='/home/hazan/mecanum_runtime_evidence',
        cgroup_root='/sys/fs/cgroup', proc_root='/proc'):
    """Đọc bằng chứng thu hồi sau lượt controller mất khả năng ghi terminal record.

    Chỉ thay thế phần xác nhận residue khi guard cũ thiếu terminal-verified.json;
    không sửa guard, verdict hoặc history của lượt cũ.
    """
    import os
    root = Path(evidence_root).resolve(strict=True)
    path = Path(attestation_path).resolve(strict=True)
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError('postmortem attestation is outside canonical evidence root') from error
    record = json.loads(path.read_bytes())
    expected_unit = run_id.lower().replace('_', '-') + '.service'
    if (record.get('schema') != 'b23_postmortem_residue/v1'
            or record.get('run_id') != run_id
            or record.get('packet_sha256') != packet_sha256
            or record.get('unit') != expected_unit):
        raise ValueError('postmortem residue binding does not match consumed packet')
    source_packet = root / run_id / 'packet.json'
    packet_raw = source_packet.read_bytes()
    if hashlib.sha256(packet_raw).hexdigest() != packet_sha256:
        raise ValueError('postmortem packet bytes do not match consumed packet hash')
    original_packet = json.loads(packet_raw)
    if (original_packet.get('run_id') != run_id or original_packet.get('unit') != expected_unit
            or original_packet.get('source_commit') != record.get('source_commit')):
        raise ValueError('postmortem source packet identity mismatch')
    evidence_files = record.get('evidence_files')
    if not isinstance(evidence_files, dict) or not evidence_files:
        raise ValueError('postmortem raw evidence hash inventory missing')
    for filename, digest in evidence_files.items():
        evidence_path = Path(filename).resolve(strict=True)
        try:
            evidence_path.relative_to(root)
        except ValueError as error:
            raise ValueError('postmortem raw evidence is outside canonical evidence root') from error
        raw = evidence_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('postmortem raw evidence changed: ' + filename)
    roles = record.get('evidence_roles')
    required_roles = {'unit_properties', 'postmortem_summary', 'controller_events',
        'parent_identity', 'parent_events'}
    if not isinstance(roles, dict) or not required_roles.issubset(roles):
        raise ValueError('postmortem semantic evidence roles are incomplete')
    if any(roles[name] not in evidence_files for name in required_roles):
        raise ValueError('postmortem semantic evidence is not hash-bound')
    cgroup = record.get('pinned_cgroup')
    expected_cgroup = ('/user.slice/user-1000.slice/user@1000.service/app.slice/' + expected_unit)
    if cgroup != expected_cgroup:
        raise ValueError('postmortem cgroup path is not the exact owned unit path')
    unit_evidence = json.loads(Path(roles['unit_properties']).read_bytes())
    raw_properties = {}
    for line in unit_evidence.get('stdout', '').splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            if key in raw_properties:
                raise ValueError('duplicate unit property in postmortem evidence: ' + key)
            raw_properties[key] = value
    if (unit_evidence.get('returncode') != 0
            or raw_properties.get('Id') != expected_unit
            or raw_properties.get('InvocationID') != record.get('invocation_id')
            or raw_properties.get('ActiveState') not in ('inactive', 'failed')
            or raw_properties.get('MainPID') != '0'
            or raw_properties.get('ControlGroup') != ''):
        raise ValueError('raw postmortem unit properties do not prove the pinned terminal unit')
    summary = json.loads(Path(roles['postmortem_summary']).read_bytes())
    scan = summary.get('pinned_cgroup_scan', {})
    if (summary.get('run_id') != run_id or summary.get('unit') != expected_unit
            or summary.get('expected_invocation_id') != record.get('invocation_id')
            or scan.get('path') != str(Path(cgroup_root) / cgroup.lstrip('/'))
            or scan.get('status') != 'path_removed_confirmed'
            or scan.get('path_exists') is not False or scan.get('errors') != []
            or scan.get('members') != []):
        raise ValueError('raw postmortem summary does not prove the pinned cgroup absent')
    declared_tails = record.get('unparsed_jsonl_tails', [])
    if not isinstance(declared_tails, list):
        raise ValueError('postmortem JSONL tail disposition is invalid')
    tail_by_path = {}
    for tail in declared_tails:
        if not isinstance(tail, dict) or tail.get('path') in tail_by_path:
            raise ValueError('postmortem JSONL tail disposition is malformed')
        tail_by_path[tail['path']] = tail
    event_identities = set()
    cgroup_member_snapshots = []
    seen_tail_paths = set()
    jsonl_paths = {str(Path(roles[name])) for name in ('controller_events', 'parent_events')}
    if not set(tail_by_path).issubset(jsonl_paths):
        raise ValueError('declared JSONL tail is not a bound controller or parent log')
    for role in ('controller_events', 'parent_events'):
        event_path = Path(roles[role])
        event_lines = event_path.read_bytes().splitlines()
        for line_number, line in enumerate(event_lines, start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as error:
                declared = tail_by_path.get(str(event_path))
                if (line_number != len(event_lines) or declared is None
                        or declared.get('line_number') != line_number
                        or declared.get('line_sha256') != hashlib.sha256(line).hexdigest()):
                    raise ValueError('JSONL corruption is not a declared final partial record: ' + role) from error
                seen_tail_paths.add(str(event_path))
                continue
            if role != 'controller_events':
                continue
            if event.get('event') == 'PID_OBSERVATION':
                facts = event.get('facts', {})
                if type(facts.get('pid')) is int and type(facts.get('start_ticks')) is int:
                    event_identities.add((facts['pid'], facts['start_ticks']))
            elif event.get('event') == 'CGROUP_OBSERVATION':
                facts = event.get('facts', {})
                if facts.get('status') == 'complete_members' and isinstance(facts.get('members'), list):
                    cgroup_member_snapshots.append(set(facts['members']))
    if seen_tail_paths != set(tail_by_path):
        raise ValueError('declared JSONL tail was not present')
    if not event_identities or not cgroup_member_snapshots:
        raise ValueError('raw controller observations do not bind process identities to cgroup membership')
    parent_record = json.loads(Path(roles['parent_identity']).read_bytes())
    parent_identity = parent_record.get('identity', {})
    if parent_record.get('run_id') != run_id or parent_record.get('packet_sha256') != packet_sha256:
        raise ValueError('raw parent identity does not bind to the consumed packet')
    if (parent_identity.get('pid'), parent_identity.get('start_ticks')) not in event_identities:
        raise ValueError('raw parent identity is not present in controller PID observations')
    saved_identities = record.get('process_identities')
    if {(item.get('pid'), item.get('start_ticks')) for item in saved_identities
            if isinstance(item, dict)} != event_identities:
        raise ValueError('postmortem PID identities differ from raw controller observations')
    if not any(members == {pid for pid, _ticks in event_identities}
            for members in cgroup_member_snapshots):
        raise ValueError('raw cgroup observations do not contain the pinned process identities')
    absent_pids = summary.get('recorded_pid_checks')
    if (not isinstance(absent_pids, list)
            or {(item.get('pid'), item.get('present')) for item in absent_pids
                if isinstance(item, dict)} != {(pid, False) for pid, _ticks in event_identities}):
        raise ValueError('raw postmortem PID checks do not cover the pinned identities')
    terminal = record.get('terminal_unit')
    if (not isinstance(terminal, dict) or terminal.get('invocation_id') != record.get('invocation_id')
            or terminal.get('active_state') not in ('inactive', 'failed')
            or terminal.get('main_pid') != 0 or terminal.get('control_group') != ''):
        raise ValueError('postmortem unit terminal identity/residue fields incomplete')
    cgroup_path = Path(cgroup_root) / cgroup.lstrip('/')
    try:
        os.stat(cgroup_path)
        cgroup_exists = True
    except FileNotFoundError:
        cgroup_exists = False
    except OSError as error:
        raise ValueError(f'postmortem pinned cgroup path cannot be inspected: {error!r}') from error
    if cgroup_exists:
        errors = []
        members = []
        for base, _dirs, _files in os.walk(cgroup_path,
                onerror=lambda error: errors.append(repr(error))):
            procs = Path(base) / 'cgroup.procs'
            try:
                members.extend(int(value) for value in procs.read_text().split())
            except OSError as error:
                errors.append(f'{procs}: {error!r}')
            except ValueError as error:
                errors.append(f'{procs}: {error!r}')
        if errors or members:
            raise ValueError('postmortem cgroup is present, unreadable, or populated')
        cgroup_status = 'complete_empty'
    else:
        cgroup_status = 'path_removed_confirmed'
    identities = record.get('process_identities')
    if not isinstance(identities, list) or not identities:
        raise ValueError('postmortem process identity inventory missing')
    observed = []
    seen = set()
    for saved in identities:
        pid, start_ticks = saved.get('pid'), saved.get('start_ticks')
        if type(pid) is not int or pid <= 0 or type(start_ticks) is not int or start_ticks <= 0 or pid in seen:
            raise ValueError('postmortem process identity tuple invalid')
        seen.add(pid)
        try:
            current_start_ticks = _proc_start_ticks(proc_root, pid)
        except FileNotFoundError:
            observed.append({'pid': pid, 'state': 'absent'})
            continue
        except OSError as error:
            raise ValueError(f'postmortem PID identity unreadable: {pid}: {error!r}') from error
        except ValueError as error:
            raise ValueError(f'postmortem PID identity invalid: {pid}: {error!r}') from error
        if current_start_ticks == start_ticks:
            raise ValueError('postmortem process identity still exists: ' + str(pid))
        observed.append({'pid': pid, 'state': 'pid_reused',
            'saved_start_ticks': start_ticks, 'current_start_ticks': current_start_ticks})
    return {'run_id': run_id, 'packet_sha256': packet_sha256,
        'invocation_id': record['invocation_id'], 'unit': expected_unit,
        'pinned_cgroup': cgroup, 'cgroup_status': cgroup_status,
        'process_observations': observed, 'source_attestation': str(path),
        'source_attestation_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'residue_absent': True, 'cleanup_ack_present': bool(record.get('cleanup_ack_present'))}


def verify_residue_revalidation_attestation(attestation_path, *, run_id, packet_sha256,
        evidence_root='/home/hazan/mecanum_runtime_evidence',
        cgroup_root='/sys/fs/cgroup', proc_root='/proc'):
    """Xác minh lại residue hiện tại khi raw postmortem lịch sử đã mất.

    Đây chỉ là bằng chứng vắng residue hiện tại. Không phục dựng InvocationID,
    cleanup ACK hoặc verdict của lượt cũ.
    """
    import ast
    import os
    root = Path(evidence_root).resolve(strict=True)
    path = Path(attestation_path).resolve(strict=True)
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError('residue revalidation is outside canonical evidence root') from error
    record = json.loads(path.read_bytes())
    unit = run_id.lower().replace('_', '-') + '.service'
    pinned_cgroup = '/user.slice/user-1000.slice/user@1000.service/app.slice/' + unit
    recovery_run = 'B23_R02B_20261115_001'
    recovery_packet = '39aea4d9253f5f93daac5541e1c82df2a712a508e87432a2701f6e04b9ac1bce'
    recovery_history = '64cb78edb4e73cbc14a11d900ec193df98335fea0c37ef7f58989e04e795da4e'
    if (record.get('schema') != 'b23_residue_revalidation/v1'
            or record.get('run_id') != run_id
            or record.get('packet_sha256') != packet_sha256
            or run_id != recovery_run or packet_sha256 != recovery_packet
            or record.get('unit') != unit
            or record.get('pinned_cgroup') != pinned_cgroup
            or record.get('cleanup_ack_present') is not False
            or record.get('historical_verdict') != 'UNRECOVERABLE'
            or record.get('historical_attestation_sha256') != recovery_history):
        raise ValueError('residue revalidation identity or history disposition mismatch')
    evidence = record.get('evidence_files')
    roles = record.get('evidence_roles')
    required = {'unit_properties', 'pinned_cgroup', 'process_identities',
        'legacy_identity_source', 'legacy_source_record'}
    if not isinstance(evidence, dict) or not evidence or not isinstance(roles, dict) or not required.issubset(roles):
        raise ValueError('residue revalidation evidence inventory incomplete')
    for name, digest in evidence.items():
        item = Path(name).resolve(strict=True)
        try:
            item.relative_to(root)
        except ValueError as error:
            raise ValueError('residue revalidation evidence is outside canonical root') from error
        if hashlib.sha256(item.read_bytes()).hexdigest() != digest:
            raise ValueError('residue revalidation evidence hash mismatch: ' + name)
    if any(roles[name] not in evidence for name in required):
        raise ValueError('residue revalidation role is not hash-bound')

    unit_record = json.loads(Path(roles['unit_properties']).read_bytes())
    expected_property_list = ('Id,LoadState,ActiveState,SubState,Result,InvocationID,ControlGroup,'
        'MainPID,ExecMainPID,ExecMainCode,ExecMainStatus,ExecStart,Type,KillMode,RuntimeMaxUSec,'
        'RuntimeRandomizedExtraUSec,TimeoutStartUSec,TimeoutStopUSec,SendSIGKILL,KillSignal,'
        'FinalKillSignal,Restart,RemainAfterExit,ExecMainExitTimestampMonotonic,MemoryMax,'
        'MemoryCurrent,MemoryPeak,OOMPolicy')
    expected_unit_argv = ['systemctl', '--user', 'show', unit, '--no-pager',
        '--property=' + expected_property_list]
    stdout = unit_record.get('stdout', '')
    props = {}
    for line in stdout.splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            if key in props:
                raise ValueError('duplicate unit property in residue revalidation: ' + key)
            props[key] = value
    if (unit_record.get('argv') != expected_unit_argv or unit_record.get('returncode') != 0
            or unit_record.get('error') is not None
            or unit_record.get('stdout_hex') != stdout.encode().hex()
            or unit_record.get('stderr_hex') != unit_record.get('stderr', '').encode().hex()
            or type(unit_record.get('started_ns')) is not int
            or type(unit_record.get('completed_ns')) is not int
            or unit_record['completed_ns'] < unit_record['started_ns']
            or props.get('Id') != unit or props.get('LoadState') != 'not-found'
            or props.get('ActiveState') != 'inactive' or props.get('SubState') != 'dead'
            or props.get('MainPID') != '0' or props.get('ControlGroup') != ''
            or props.get('InvocationID') != ''):
        raise ValueError('current unit query does not prove the exact unit absent')

    cgroup_record = json.loads(Path(roles['pinned_cgroup']).read_bytes())
    expected_cgroup_path = str(Path(cgroup_root) / pinned_cgroup.lstrip('/'))
    if (cgroup_record.get('path') != expected_cgroup_path
            or cgroup_record.get('status') != 'path_removed_confirmed'
            or cgroup_record.get('errno') != 2 or cgroup_record.get('members') != []
            or cgroup_record.get('errors') != []
            or type(cgroup_record.get('started_monotonic_ns')) is not int
            or type(cgroup_record.get('completed_monotonic_ns')) is not int
            or cgroup_record['completed_monotonic_ns'] < cgroup_record['started_monotonic_ns']):
        raise ValueError('pinned cgroup revalidation is incomplete or not absent')
    cgroup_path = Path(cgroup_root) / pinned_cgroup.lstrip('/')
    try:
        os.stat(cgroup_path.parent)
    except OSError as error:
        raise ValueError(f'pinned cgroup parent cannot be inspected: {error!r}') from error
    try:
        os.stat(cgroup_path)
    except FileNotFoundError:
        pass
    except OSError as error:
        raise ValueError(f'pinned cgroup cannot be revalidated: {error!r}') from error
    else:
        raise ValueError('pinned cgroup reappeared after residue capture')

    source = Path(roles['legacy_identity_source']).read_text()
    if recovery_history not in source:
        raise ValueError('historical identity inventory is not tied to prior attestation digest')
    source_record_path = Path(roles['legacy_source_record'])
    source_record_raw = source_record_path.read_bytes()
    source_record = json.loads(source_record_raw)
    source_output = '\n'.join(item.get('text', '') for item in
        source_record.get('payload', {}).get('output', []) if item.get('type') == 'input_text')
    if (source_record.get('type') != 'response_item'
            or source_record.get('payload', {}).get('type') != 'custom_tool_call_output'
            or source not in source_output
            or record.get('legacy_record_source', {}).get('sha256')
                != hashlib.sha256(source_record_raw).hexdigest()):
        raise ValueError('historical identity inventory source record is not hash-bound')
    source_meta = record.get('legacy_record_source', {})
    try:
        source_path = Path(source_meta.get('path', '')).resolve(strict=True)
        source_lines = source_path.read_bytes().splitlines(keepends=True)
        line_number = source_meta.get('line_number')
        if (type(line_number) is not int or line_number <= 0
                or source_lines[line_number - 1] != source_record_raw):
            raise ValueError('historical identity source does not match its recorded session line')
    except (OSError, IndexError) as error:
        raise ValueError(f'historical identity source line cannot be verified: {error!r}') from error
    marker = 'identities '
    if marker not in source:
        raise ValueError('historical process identity inventory missing')
    try:
        parsed = ast.literal_eval(source.split(marker, 1)[1].splitlines()[0])
    except (SyntaxError, ValueError) as error:
        raise ValueError('historical process identity inventory cannot be parsed') from error
    if not isinstance(parsed, list) or not parsed:
        raise ValueError('historical process identity inventory is empty')
    saved = record.get('process_identities')
    expected = [{'pid': row.get('pid'), 'start_ticks': row.get('start_ticks')} for row in parsed]
    if saved != expected:
        raise ValueError('revalidated process identities differ from historical inventory')
    proc_record = json.loads(Path(roles['process_identities']).read_bytes())
    proc_observations = proc_record.get('observations')
    if (proc_record.get('identities') != saved or not isinstance(proc_observations, list)
            or len(proc_observations) != len(saved)
            or {item.get('pid') for item in proc_observations if isinstance(item, dict)}
                != {item['pid'] for item in saved}):
        raise ValueError('process identity observation does not match pinned inventory')
    if (type(proc_record.get('started_monotonic_ns')) is not int
            or type(proc_record.get('completed_monotonic_ns')) is not int
            or proc_record['completed_monotonic_ns'] < proc_record['started_monotonic_ns']):
        raise ValueError('process identity revalidation timestamps are invalid')
    recorded_states = {item['pid']: item.get('state') for item in proc_observations}
    observations = []
    seen = set()
    for identity in saved:
        pid, ticks = identity.get('pid'), identity.get('start_ticks')
        if type(pid) is not int or pid <= 0 or type(ticks) is not int or ticks <= 0 or pid in seen:
            raise ValueError('revalidated PID identity tuple invalid')
        seen.add(pid)
        try:
            current = _proc_start_ticks(proc_root, pid)
        except FileNotFoundError:
            if recorded_states.get(pid) != 'absent':
                raise ValueError('live PID absence differs from recorded observation: ' + str(pid))
            observations.append({'pid': pid, 'state': 'absent'})
            continue
        except OSError as error:
            raise ValueError(f'PID identity unreadable during revalidation: {pid}: {error!r}') from error
        except ValueError as error:
            raise ValueError(f'PID identity invalid during revalidation: {pid}: {error!r}') from error
        if current == ticks:
            raise ValueError('historical process identity remains live: ' + str(pid))
        if recorded_states.get(pid) != 'pid_reused':
            raise ValueError('live PID reuse differs from recorded observation: ' + str(pid))
        observations.append({'pid': pid, 'state': 'pid_reused', 'current_start_ticks': current})
    return {'run_id': run_id, 'packet_sha256': packet_sha256, 'unit': unit,
        'pinned_cgroup': pinned_cgroup, 'cgroup_status': 'path_removed_confirmed',
        'process_observations': observations, 'source_attestation': str(path),
        'source_attestation_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'residue_absent': True, 'cleanup_ack_present': False,
        'historical_verdict': 'UNRECOVERABLE'}


def verify_previous_run_residue(state_dir, previous, *, evidence_root,
        cgroup_root='/sys/fs/cgroup', proc_root='/proc'):
    """Require a packet-bound residue proof for every previously consumed run."""
    authority_path = previous / 'authority.json'
    consumed_path = previous / 'consumed.json'
    authority = json.loads(authority_path.read_bytes())
    consumed = json.loads(consumed_path.read_bytes())
    run_id = previous.name
    if (authority.get('run_id') != run_id or consumed.get('run_id') != run_id
            or authority.get('packet_sha256') != consumed.get('packet_sha256')):
        raise RuntimeError('previous consumed run guard identity mismatch: ' + str(previous))
    terminal_path = previous / 'terminal-verified.json'
    if terminal_path.exists():
        terminal = json.loads(terminal_path.read_bytes())
        if (terminal.get('run_id') != run_id
                or terminal.get('packet_sha256') != consumed.get('packet_sha256')
                or terminal.get('residue_absent') is not True):
            raise RuntimeError('previous consumed run has unverified residue: ' + str(previous))
        return {'run_id': run_id, 'source': str(terminal_path),
            'packet_sha256': consumed['packet_sha256'], 'residue_absent': True}
    attestation_path = (Path(evidence_root) / 'B23_POSTMORTEM' / run_id / 'terminal-residue.json')
    if attestation_path.exists():
        try:
            result = verify_postmortem_residue_attestation(attestation_path,
                run_id=run_id, packet_sha256=consumed['packet_sha256'],
                evidence_root=evidence_root, cgroup_root=cgroup_root, proc_root=proc_root)
        except (OSError, KeyError, TypeError, ValueError, AttributeError) as error:
            raise RuntimeError('previous consumed run has unverified residue: ' + str(previous)) from error
        return {'run_id': run_id, 'source': str(attestation_path),
            'packet_sha256': consumed['packet_sha256'], 'residue_absent': True,
            'postmortem': result}
    revalidation_path = (Path(evidence_root) / 'B23_RESIDUE_REVALIDATION' / run_id / 'residue-revalidation.json')
    try:
        result = verify_residue_revalidation_attestation(revalidation_path,
            run_id=run_id, packet_sha256=consumed['packet_sha256'],
            evidence_root=evidence_root, cgroup_root=cgroup_root, proc_root=proc_root)
    except (OSError, KeyError, TypeError, ValueError, AttributeError) as error:
        raise RuntimeError('previous consumed run has unverified residue: ' + str(previous)) from error
    return {'run_id': run_id, 'source': str(revalidation_path),
        'packet_sha256': consumed['packet_sha256'], 'residue_absent': True,
        'residue_revalidation': result}


async def run_parent(packet_path, packet_sha256):
    """Sở hữu tất cả launch qua supervisor đã audit; không override start()."""
    import os
    import sys
    import signal
    from mecanum_nav_bringup import local_training_process_supervisor as sp
    from mecanum_nav_bringup.local_training_launch_contract import LaunchPlan
    packet = verify_packet(packet_path, packet_sha256)
    invocation = os.environ.get('INVOCATION_ID', '')
    if (not invocation or packet['unit'] not in Path('/proc/self/cgroup').read_text()
            or len(invocation) != 32):
        raise RuntimeError('parent is not inside exact transient invocation')
    consumed = json.loads((Path(packet['guard_path'])/'consumed.json').read_bytes())
    if consumed['packet_sha256'] != packet_sha256 or consumed['run_id'] != packet['run_id']:
        raise RuntimeError('parent consumed guard mismatch')
    active_end, total_end = consumed['active_deadline_ns'], consumed['total_deadline_ns']
    root = Path(packet['run_root'])
    sink = RunEvidence(root, 'parent', run_id=packet['run_id'], invocation_id=invocation)
    identity = process_identity(os.getpid())
    write_record_once(root/'parent-identity.json', {'identity': identity,
        'packet_sha256': packet_sha256, 'invocation_id': invocation, 'run_id': packet['run_id'],
        'active_deadline_ns': active_end, 'total_deadline_ns': total_end})
    values = dict(packet['launch_plan'])
    for name in ('world_file', 'gui_config', 'resolved_config'):
        values[name] = Path(values[name])
    values['commands'] = tuple(tuple(command) for command in values['commands'])
    values['bridge_command'] = tuple(values['bridge_command'])
    plan = LaunchPlan(**values)
    supervisor = sp.LocalTrainingProcessSupervisor(plan=plan, launcher=sp.SubprocessProcessLauncher(),
        readiness=sp.RclpyReadiness(), evidence_sink=sink, heartbeat_diagnostics_enabled=True,
        heartbeat_trace_directory=root/'trace', cleanup_evidence_publisher=sink.cleanup_publisher)
    abort = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, abort.set)
    primary, clean, worker_exit = None, False, None
    startup_task = abort_task = None
    shared_cleanup_end = total_end
    cleanup_seen = False
    owned_identities = []
    expected_restart_pids = set()
    restart_request_processed = False
    async def handle_owned_restart_request():
        nonlocal restart_request_processed
        request_path = root/'owned-restart-request.json'
        response_path = root/'owned-restart-response.json'
        if restart_request_processed or not request_path.exists():
            return
        request = json.loads(request_path.read_bytes())
        case = packet['case']
        role = 'server' if case == 'R07c' else 'final' if case == 'R07d' else None
        if role is None:
            raise RuntimeError('owned restart request is outside R07c/R07d')
        expected_old_identity = (descriptor_base['backend_instance_id'] if case == 'R07c'
            else descriptor_base['final_publisher_instance_id'])
        identity_field = ('old_backend_instance_id' if case == 'R07c'
            else 'old_publisher_instance_id')
        if request.get(identity_field) != expected_old_identity:
            raise RuntimeError('owned restart request prior instance binding mismatch')
        candidates = [record for record in supervisor.owned if record.name == role]
        if not candidates:
            raise RuntimeError('owned restart target has no registered process')
        old = candidates[-1]
        identity = process_identity(old.pid)
        verify_owned_restart_request(request, run_id=packet['run_id'],
            invocation_id=invocation, case=case, role=role,
            process_identity_record=identity)
        if old.process.returncode is not None:
            raise RuntimeError('owned restart target already exited before request')
        expected_restart_pids.add(old.pid)
        stopped = await stop_exact_owned_process(supervisor, old,
            identity=identity, deadline_ns=active_end)
        if role == 'server':
            await supervisor.prepare_heartbeat_backend_restart_segment()
            server_command = tuple(plan.commands[0])
            server_environment = dict(plan.environment)
            for name in tuple(server_environment):
                if name.startswith('MECANUM_B2_HEARTBEAT_'):
                    server_environment.pop(name)
            server_environment['MECANUM_B2_HEARTBEAT_DIAGNOSTICS'] = '0'
            server_environment.update(supervisor._heartbeat_trace_environment)
            replacement = await supervisor._launch_owned_process(
                'server', server_command, server_environment)
            remaining = max(0., (active_end-time.monotonic_ns())/1e9)
            if remaining <= 0:
                raise TimeoutError('R07c active deadline expired before replacement readiness')
            from mecanum_nav_rl_interfaces.msg import SimulationContactState
            supervisor.readiness = supervisor.readiness.fresh_attempt(
                expected_fault_flags=int(SimulationContactState.FAULT_QUEUE))
            await supervisor.readiness.server_scene(plan, replacement.process,
                min(supervisor.SERVER_READY_TIMEOUT_S, remaining))
            await supervisor.bind_restarted_heartbeat_backend()
            replacement_facts = {'pid':replacement.pid,
                'identity':process_identity(replacement.pid),
                'backend_instance_id':supervisor.readiness.accepted_backend_status.get('backend_instance_id')
                    if isinstance(supervisor.readiness.accepted_backend_status, dict) else None}
            if replacement.pid == old.pid:
                raise RuntimeError('R07c replacement reused old server PID')
        else:
            final_descriptor = dict(descriptor_base, role='final',
                evidence_role='final_restart_1',
                final_boot_path=str(root/'final-restart-1-boot.json'),
                final_binding_path=str(root/'final-restart-1-binding.json'),
                final_binding_ack_path=str(root/'final-restart-1-binding-ack.json'))
            descriptor_path = root/'final-restart-1-descriptor.json'
            write_record_once(descriptor_path, final_descriptor)
            replacement = await launch('final', [sys.executable, '-B', '-m', MODULE,
                'final', '--descriptor', str(descriptor_path)])
            boot_path = Path(final_descriptor['final_boot_path'])
            while time.monotonic_ns() < active_end and not boot_path.exists():
                await asyncio.sleep(min(.01, max(0., (active_end-time.monotonic_ns())/1e9)))
            if not boot_path.exists():
                raise TimeoutError('R07d replacement final publisher did not boot')
            boot = json.loads(boot_path.read_bytes())
            if (boot.get('run_id') != packet['run_id']
                    or boot.get('invocation_id') != invocation
                    or not same_process_identity(boot.get('identity'),
                                                 process_identity(replacement.pid))
                    or boot.get('publisher_instance_id') == request.get('old_publisher_instance_id')):
                raise RuntimeError('R07d replacement publisher identity did not change')
            replacement_facts = {'pid':replacement.pid,
                'identity':boot['identity'],
                'publisher_instance_id':boot['publisher_instance_id'],
                'boot_path':str(boot_path),
                'binding_ack_path':final_descriptor['final_binding_ack_path']}
        result = {'schema':'b23_owned_restart_response/v1',
            'run_id':packet['run_id'],'invocation_id':invocation,'case':case,
            'target_role':role,'request_sha256':hashlib.sha256(request_path.read_bytes()).hexdigest(),
            'old_process':stopped,'replacement':replacement_facts,
            'completed_ns':time.monotonic_ns()}
        write_record_once(response_path, result)
        restart_request_processed = True
    async def wait_for(predicate, label):
        nonlocal shared_cleanup_end, cleanup_seen
        while time.monotonic_ns() < (shared_cleanup_end if cleanup_seen else active_end):
            marker = root/'worker-cleanup-start.json'
            if marker.exists():
                record = json.loads(marker.read_bytes())
                shared_cleanup_end = min(shared_cleanup_end, cleanup_window_deadline(record,
                    run_id=packet['run_id'], invocation=invocation, total_end=total_end, now_ns=time.monotonic_ns()))
                cleanup_seen = True
            if abort.is_set(): raise RuntimeError('parent cancellation requested')
            await handle_owned_restart_request()
            for process in supervisor.owned:
                if (process.process.returncode is not None and process.name not in ('worker',)
                        and process.pid not in expected_restart_pids):
                    raise RuntimeError('owned process exited: ' + process.name + '=' + str(process.process.returncode))
            observer = supervisor._heartbeat_observer_process
            if observer is not None and observer.returncode is not None:
                raise RuntimeError('owned heartbeat observer exited: ' + str(observer.returncode))
            if supervisor._heartbeat_trace_error is not None:
                raise RuntimeError('heartbeat trace error: ' + str(supervisor._heartbeat_trace_error))
            value = predicate()
            if value:
                if time.monotonic_ns() >= (shared_cleanup_end if cleanup_seen else active_end):
                    raise TimeoutError(label + ' observed late')
                return value
            await asyncio.sleep(min(.01, max(0., ((shared_cleanup_end if cleanup_seen else active_end)-time.monotonic_ns())/1e9)))
        raise TimeoutError(label + ' exceeded active deadline')
    async def launch(role, command):
        record = await supervisor._launch_owned_process(role, tuple(command), dict(plan.environment))
        observed = process_identity(record.pid)
        owned_identities.append(observed)
        sink.record('OWNED_IDENTITY', {'role': role, 'identity': observed, 'command': list(command)})
        return record
    descriptor_base = dict(schema='b23_owned_child/v1', run_id=packet['run_id'], session_id=packet['session_id'],
        packet_path=str(Path(packet_path).resolve()), packet_sha256=packet_sha256,
        invocation_id=invocation, run_root=str(root), parent_identity=identity,
        active_deadline_ns=active_end, total_deadline_ns=total_end,
        coordinator_ingress_instance_id=packet['coordinator_ingress_instance_id'],
        config_hash=packet['config_hash'], asset_manifest_sha256=packet['asset_manifest_sha256'],
        task_fixture=packet.get('task_fixture'),
        owned_restart_request_path=str(root/'owned-restart-request.json'),
        owned_restart_response_path=str(root/'owned-restart-response.json'),
        scan_period_ns=packet_scan_period_ns(packet),
        native_events_path=str(root/'native-events.jsonl'))
    try:
        if time.monotonic_ns() >= active_end:
            raise TimeoutError('active deadline expired before supervisor start')
        startup_task = asyncio.create_task(supervisor.start(), name='b23-owned-supervisor-start')
        abort_task = asyncio.create_task(abort.wait(), name='b23-owned-start-abort')
        done, _ = await asyncio.wait((startup_task, abort_task),
            timeout=max(0., (active_end-time.monotonic_ns())/1e9), return_when=asyncio.FIRST_COMPLETED)
        if abort_task in done:
            raise RuntimeError('parent cancellation requested during startup')
        if startup_task not in done:
            raise TimeoutError('supervisor startup exceeded active deadline')
        await startup_task
        abort_task.cancel()
        try: await abort_task
        except asyncio.CancelledError: pass
        status = supervisor.readiness.accepted_backend_status
        backend_id = status['backend_instance_id']
        server = next(row for row in supervisor.owned if row.name == 'server')
        descriptor_base.update(backend_instance_id=backend_id, server_leader_pid=server.pid,
            server_identity=process_identity(server.pid),
            physics_engine_sha256=packet['physics_engine_sha256'])
        await launch('robot_state_publisher', packet['robot_state_publisher_argv'])
        final_descriptor = dict(descriptor_base, role='final', evidence_role='final',
            final_boot_path=str(root/'final-boot.json'), final_binding_path=str(root/'final-binding.json'),
            final_binding_ack_path=str(root/'final-binding-ack.json'))
        write_record_once(root/'final-descriptor.json', final_descriptor)
        final = await launch('final', [sys.executable, '-B', '-m', MODULE, 'final',
            '--descriptor', str(root/'final-descriptor.json')])
        def booted():
            path = root/'final-boot.json'
            if not path.exists(): return None
            record = json.loads(path.read_bytes())
            if (record['run_id'] != packet['run_id'] or record['invocation_id'] != invocation
                    or record['identity'] != process_identity(final.pid) or record['publisher_instance_id'] <= 0):
                # /proc state có thể thay đổi; đối chiếu identity bất biến bên dưới.
                current = process_identity(final.pid)
                if (record['run_id'] != packet['run_id'] or record['invocation_id'] != invocation
                        or any(record['identity'][key] != current[key] for key in ('pid','uid','start_ticks','argv','pgid','sid'))
                        or record['publisher_instance_id'] <= 0):
                    raise RuntimeError('final boot record ownership mismatch')
            return record
        boot = await wait_for(booted, 'final actual boot')
        pin_initial_final_publisher_identity(descriptor_base, boot, final.pid)
        worker_descriptor = dict(descriptor_base, role='worker',
            final_publisher_instance_id=boot['publisher_instance_id'], final_publisher_pid=final.pid,
            final_binding_path=str(root/'final-binding.json'), final_binding_ack_path=str(root/'final-binding-ack.json'))
        write_record_once(root/'worker-descriptor.json', worker_descriptor)
        worker = await launch('worker', [sys.executable, '-B', '-m', MODULE, 'worker',
            '--descriptor', str(root/'worker-descriptor.json')])
        await wait_for(lambda: worker.process.returncode is not None, 'worker terminal')
        worker_exit = await worker.process.wait()
        outcome = json.loads((root/'worker-result.json').read_bytes())
        if (worker_exit != 0 or outcome['primary_error'] is not None or outcome['cleanup_errors']
                or outcome['outcome'] is None or outcome['run_id'] != packet['run_id']
                or outcome['invocation_id'] != invocation or outcome['outcome']['completed_ns'] >= active_end):
            raise RuntimeError('worker did not complete cleanly: ' + repr(outcome))
    except BaseException as error:
        primary = repr(error)
        sink.record('PARENT_PRIMARY_ERROR', {'error': primary})
    finally:
        started = time.monotonic_ns()
        marker = root/'worker-cleanup-start.json'
        if marker.exists():
            try:
                shared_cleanup_end = min(shared_cleanup_end, cleanup_window_deadline(
                    json.loads(marker.read_bytes()), run_id=packet['run_id'], invocation=invocation,
                    total_end=total_end, now_ns=started))
            except BaseException as error:
                sink.record('CLEANUP_WINDOW_BINDING_ERROR', {'error':repr(error)})
                shared_cleanup_end = min(shared_cleanup_end, started)
        deadline = min(total_end, shared_cleanup_end, started + 60_000_000_000)
        try:
            clean = await supervisor.cleanup(deadline=deadline/1e9)
        except BaseException as error:
            sink.record('PARENT_CLEANUP_ERROR', {'error': repr(error)})
        for task in (startup_task, abort_task):
            if task is not None:
                pending = not task.done()
                if pending: task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=max(0., (deadline-time.monotonic_ns())/1e9))
                except asyncio.CancelledError:
                    pass
                except BaseException as error:
                    sink.record('PARENT_TASK_FINALIZATION', {'task':task.get_name(), 'error':repr(error)})
                    if pending: clean = False
        cleanup = supervisor.cleanup_snapshot()
        result = {'run_id': packet['run_id'], 'invocation_id': invocation,
            'packet_sha256': packet_sha256, 'primary_error': primary, 'worker_exit': worker_exit,
            'cleanup_clean': clean, 'cleanup': cleanup, 'cleanup_started_ns': started,
            'cleanup_deadline_ns': deadline, 'completed_ns': time.monotonic_ns(),
            'owned_identities': owned_identities, 'containment_terminal_requires_external_readback': True}
        write_record_once(root/'parent-result.json', result)
        sink.close()
    return 0 if primary is None and clean and result['completed_ns'] <= total_end else 1




def cleanup_window_deadline(record, *, run_id, invocation, total_end, now_ns):
    """Một ngân sách 60 s cho worker và parent, không làm mới qua biên IPC."""
    if (record.get('run_id') != run_id or record.get('invocation_id') != invocation
            or type(record.get('started_ns')) is not int or type(record.get('deadline_ns')) is not int
            or not 0 <= record['started_ns'] <= now_ns
            or record['deadline_ns'] != min(total_end, record['started_ns'] + 60_000_000_000)):
        raise ValueError('worker cleanup deadline identity/budget invalid')
    return record['deadline_ns']


def launch_plan_record(plan):
    """Serialize plan bất biến mà không deepcopy MappingProxyType của env."""
    from dataclasses import fields
    return {item.name: (str(value) if isinstance(value, Path)
        else dict(value) if item.name == 'environment' else value)
        for item in fields(plan) for value in (getattr(plan, item.name),)}


def command_record(argv, *, timeout_s):
    """Lệnh quản trị có timeout và raw outcome; không sửa cấu hình khi lỗi."""
    import subprocess
    started = time.monotonic_ns()
    record = {'argv': list(argv), 'started_ns': started, 'timeout_s': timeout_s}
    if timeout_s <= 0:
        return dict(record, error='no_remaining_budget', returncode=None, stdout='', stderr='', completed_ns=time.monotonic_ns())
    try:
        result = subprocess.run(argv, capture_output=True, timeout=timeout_s, check=False)
        record.update(returncode=result.returncode, stdout_hex=result.stdout.hex(), stderr_hex=result.stderr.hex(),
            stdout=result.stdout.decode(errors='replace'), stderr=result.stderr.decode(errors='replace'), error=None)
    except subprocess.TimeoutExpired as error:
        record.update(returncode=None, stdout_hex=(error.stdout or b'').hex(), stderr_hex=(error.stderr or b'').hex(),
            stdout=(error.stdout or b'').decode(errors='replace'), stderr=(error.stderr or b'').decode(errors='replace'), error='timeout')
    record['completed_ns'] = time.monotonic_ns()
    return record


def prepare_packet(args):
    """Chuẩn bị R01a offline từ commit/install đã build và JUnit không lỗi."""
    import os
    import sys
    import secrets
    import uuid
    import xml.etree.ElementTree as ET
    from dataclasses import replace
    from mecanum_nav_bringup.local_training_launch_contract import build_launch_plan, write_bound_world, load_bound_config
    from mecanum_nav_bringup.local_training_process_supervisor import _physics_engine_plugin_path
    prefix, repo = Path(args.install).resolve(strict=True), Path(args.repo).resolve(strict=True)
    commit_record = command_record(['git', '-C', str(repo), 'rev-parse', 'HEAD'], timeout_s=5.)
    if commit_record['returncode'] != 0 or commit_record['stdout'].strip() != args.commit:
        raise ValueError('prepare source commit mismatch')
    branch = command_record(['git', '-C', str(repo), 'branch', '--show-current'], timeout_s=5.)
    dirty = command_record(['git', '-C', str(repo), 'status', '--porcelain'], timeout_s=5.)
    if (branch['returncode'] != 0 or branch['stdout'].strip() != 'roadmap-b-b23-local-training-integration'
            or dirty['returncode'] != 0 or dirty['stdout']):
        raise ValueError('runtime source worktree must be exact clean B23 candidate')
    build_binding_raw = Path(args.build_binding).resolve(strict=True).read_bytes()
    build_binding = json.loads(build_binding_raw)
    if (build_binding['source_commit'] != args.commit or build_binding['build_exit'] != 0
            or Path(build_binding['install_prefix']).resolve(strict=True) != prefix):
        raise ValueError('build/install provenance incomplete')
    for filename, digest in build_binding['input_sha256'].items():
        if hashlib.sha256(Path(filename).read_bytes()).hexdigest() != digest:
            raise ValueError('build input/output bytes changed: ' + filename)
    evidence = {}
    for filename in args.junit:
        path = Path(filename).resolve(strict=True)
        raw = path.read_bytes(); tree = ET.fromstring(raw)
        cases = tree.findall('.//testcase')
        if not cases or tree.findall('.//failure') or tree.findall('.//error') or tree.findall('.//skipped'):
            raise ValueError('offline JUnit incomplete/not green: ' + filename)
        evidence[str(path)] = hashlib.sha256(raw).hexdigest()
    if not evidence:
        raise ValueError('offline evidence required before packet preparation')
    rl, desc, bringup = (prefix/'share'/name for name in ('mecanum_nav_rl','ROBOT_URDF_final_description','mecanum_nav_bringup'))
    config_name, scenario_name = CASE_SCENARIOS.get(args.case,
        ('sim_train_local_training_soak.resolved.json', 'B2_SOAK_V1.json'))
    resolved_config = rl/'config/v3/resolved'/config_name
    scenario_path = rl/'scenarios/local_training'/scenario_name
    document, config_hash, asset_hash, _ = load_bound_config(resolved_config)
    import re
    if not re.fullmatch(r'B23_[A-Z0-9_]{1,60}', args.run_id):
        raise ValueError('run ID invalid')
    root = Path('/home/hazan/mecanum_runtime_evidence')/args.run_id
    root.mkdir(mode=0o700)  # EEXIST giữ toàn bộ lượt cũ, không retry.
    (root/'trace').mkdir(mode=0o700)
    guard = Path('/home/hazan/.local/state/ros2_nav2_drl/b23')/args.run_id
    guard.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    guard.mkdir(mode=0o700)
    session_id = str(uuid.uuid4())
    ingress = secrets.randbelow(2**63-1)+1
    engine_dir = _physics_engine_plugin_path()
    engine_files = sorted({path.resolve(strict=True) for path in engine_dir.glob('*dartsim-plugin.so*') if path.is_file()})
    if len(engine_files) != 1:
        raise ValueError('DART binary missing or ambiguous')
    engine_file = engine_files[0]
    plan = build_launch_plan(gui='false', resolved_config=resolved_config,
        world_file=desc/'worlds/b2_training_arena.sdf', gui_config=bringup/'config/gui/local_training.config',
        session_id=session_id, partition='mecanum_' + args.run_id.lower(),
        bridge_config=bringup/'config/bridge/local_training.runtime.yaml',
        resource_paths=(desc.parent, desc/'models'), plugin_path=prefix/'lib', physics_engine_plugin_path=engine_dir,
        asset_manifest_file=desc/'manifests/b2/asset_manifest.json', scenario_directory=rl/'scenarios/local_training',
        runtime_world_directory=root, coordinator_ingress_instance_id=ingress)
    plan = replace(plan, environment={**plan.environment, 'ROS_DOMAIN_ID': '84'},
        commands=(b23_server_argv(plan.world_file),))
    write_bound_world(plan, desc/'worlds/b2_training_arena.sdf', desc/'models/mecanum_b2/model.sdf')
    # Điểm tựa hình học từ bốn wheel cylinder hiện hành; measurement reset vẫn
    # phải kiểm z/roll/pitch/twist thật theo tolerance đã khóa.
    model = ET.parse(desc/'models/mecanum_b2/model.sdf')
    supports = []
    for name in ('Wheel_LF_1','Wheel_RF_1','Wheel_RB_1','Wheel_LB_1'):
        link = model.find(f".//link[@name='{name}']")
        pose = [float(v) for v in link.findtext('pose').split()]
        radius = float(link.findtext('collision/geometry/cylinder/radius'))
        supports.append(radius-pose[2])
    if max(supports)-min(supports) > 1e-9:
        raise ValueError('reset support geometry not uniform')
    inputs = {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in prefix.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    import importlib
    from rclpy.impl.implementation_singleton import rclpy_implementation
    dependency_origins = {name: str(Path(importlib.import_module(name).__file__).resolve(strict=True))
        for name in ('rclpy','pydantic','numpy','yaml','ros_gz_interfaces.srv._control_world',
                     'ros_gz_interfaces.srv._set_entity_pose','std_srvs.srv._trigger')}
    dependency_origins['rclpy_native'] = str(Path(rclpy_implementation.__file__).resolve(strict=True))
    dependency_origins['python_binary'] = str(Path(sys.executable).resolve(strict=True))
    inputs.update({path:hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in dependency_origins.values()})
    inputs.update({str(Path(args.build_binding).resolve()): hashlib.sha256(build_binding_raw).hexdigest(), **evidence,
        str(plan.world_file): hashlib.sha256(plan.world_file.read_bytes()).hexdigest(),
        str(engine_file): hashlib.sha256(engine_file.read_bytes()).hexdigest()})
    environment_keys = ('HOME','USER','LOGNAME','PATH','LANG','LC_ALL','LD_LIBRARY_PATH','PYTHONPATH',
        'AMENT_PREFIX_PATH','CMAKE_PREFIX_PATH','COLCON_PREFIX_PATH','ROS_DISTRO','ROS_VERSION','ROS_PYTHON_VERSION',
        'RMW_IMPLEMENTATION','XDG_RUNTIME_DIR','DBUS_SESSION_BUS_ADDRESS','LIBGL_ALWAYS_SOFTWARE','GZ_CONFIG_PATH')
    environment = bind_install_ament_prefix(
        {k: os.environ[k] for k in environment_keys if k in os.environ}, prefix,
    )
    environment.update(ROS_DOMAIN_ID='84', ROS_HOME=str(root/'ros-home'), ROS_LOG_DIR=str(root/'ros-log'),
        PYTHONPYCACHEPREFIX=str(root/'pycache'))
    values = launch_plan_record(plan)
    fault_hooks = case_fault_hooks(args.case, args.fault_hook)
    environment.update(case_environment(args.case, fault_hooks))
    active_s = 900 if args.case == 'R08' else 120
    cleanup_s = 60
    episode_seeds = (list(range(2026102900, 2026102930)) if args.case == 'R08' else
        [2026103028 if args.case == 'R09a' else 2026103029] if args.case in ('R09a','R09b') else
        [2026102900,2026102901])
    packet = {'schema': 'b23_packet/v1', 'run_id': args.run_id, 'session_id':session_id, 'unit': args.run_id.lower().replace('_','-')+'.service',
        'case': args.case, 'gui': False,
        'fault_hooks': fault_hooks,
        'world_seed':20261029,
        'episode_seeds':episode_seeds, 'authority': 'OWNER_B23_CAMPAIGN_APPROVED',
        'authority_reference': 'Owner approval B23_CAMPAIGN and standing authorization in task conversation',
        'source_commit': args.commit, 'source_repo': str(repo), 'install_prefix': str(prefix),
        'build_binding_sha256': hashlib.sha256(build_binding_raw).hexdigest(), 'python': str(Path(sys.executable).absolute()),
        'run_root': str(root), 'guard_path': str(guard), 'active_s':active_s, 'cleanup_s':cleanup_s,
        'resolved_config': str(plan.resolved_config), 'config_hash':config_hash, 'asset_manifest_sha256':asset_hash,
        'asset_manifest':str(desc/'manifests/b2/asset_manifest.json'), 'scenario':str(scenario_path),
        'coordinator_ingress_instance_id':ingress, 'physics_engine_sha256':inputs[str(engine_file)],
        'launch_plan':values, 'environment':environment, 'input_sha256':inputs,
        'reset_target':{'x_m':0.,'y_m':0.,'z_m':supports[0],'yaw_rad':0.},
        'robot_state_publisher_argv':['/opt/ros/jazzy/lib/robot_state_publisher/robot_state_publisher',
            '--ros-args','-p','use_sim_time:=true','-p','robot_description:='+(desc/'urdf/mecanum_b2_static.urdf').read_text()],
        'offline_evidence':evidence, 'dependency_origins':dependency_origins,
        'owner_decisions':{'L2-PAUSE':'APPROVED','L2-ADMISSION':'APPROVED','D03':'APPROVED','D04':'APPROVED',
            'D05':'APPROVED','offline_and_git':'APPROVED','runtime':'B23_CAMPAIGN_APPROVED',
            'phase':campaign_phase(args.case),
            'excluded_actions':['B22 contact-only runtime','hardware/HIL','PPO training'],
            'quoted_approval':'B23_CAMPAIGN_APPROVED; case-scoped campaign hook.'},
        'source_preflight':[commit_record,branch,dirty]}
    if args.case == 'R09b':
        packet['task_fixture'] = dict(R09B_TASK_FIXTURE)
    packet['service_properties'] = list(service_properties_for(active_s))
    packet['launch_argv_template'] = service_launch_command(packet, str(root/'packet.json'), '{PACKET_SHA256}')
    digest = write_record_once(root/'packet.json', packet)
    write_record_once(guard/'authority.json', {'run_id':args.run_id, 'capacity':1, 'packet_sha256':digest,
        'authority':packet['authority'], 'phase':campaign_phase(args.case), 'consumed':False})
    print(json.dumps({'packet':str(root/'packet.json'), 'packet_sha256':digest, 'guard':str(guard)}))
    return 0


def unit_properties(unit, *, timeout_s):
    names = ('Id','LoadState','ActiveState','SubState','Result','InvocationID','ControlGroup',
        'MainPID','ExecMainPID','ExecMainCode','ExecMainStatus','ExecStart','Type','KillMode',
        'RuntimeMaxUSec','RuntimeRandomizedExtraUSec','TimeoutStartUSec','TimeoutStopUSec',
        'SendSIGKILL','KillSignal','FinalKillSignal','Restart','RemainAfterExit','ExecMainExitTimestampMonotonic',
        'MemoryMax','MemoryCurrent','MemoryPeak','OOMPolicy')
    record = command_record(['systemctl','--user','show',unit,'--no-pager',
        '--property='+','.join(names)], timeout_s=timeout_s)
    properties = {}
    if record['returncode'] == 0 and record['error'] is None:
        for line in record['stdout'].splitlines():
            key, separator, value = line.partition('=')
            if not separator or key in properties:
                raise ValueError('ambiguous systemd property output')
            properties[key] = value
    return properties, record



def verify_unit_configuration(properties, *, active_s=120, cleanup_s=60):
    """Đối chiếu giá trị thực; định dạng ngoài tập chính xác phải dừng."""
    runtime_s = active_s + cleanup_s
    runtime_values = {f'{runtime_s}s', f'{runtime_s * 1_000_000}us'}
    if runtime_s % 60 == 0: runtime_values.add(f'{runtime_s // 60}min')
    expected = {'Type':{'exec'}, 'Restart':{'no'}, 'KillMode':{'control-group'},
        'RemainAfterExit':{'yes'}, 'MemoryMax':{'5368709120'}, 'OOMPolicy':{'stop'}, 'RuntimeMaxUSec':runtime_values,
        'RuntimeRandomizedExtraUSec':{'0','0us','0s'}, 'TimeoutStartUSec':{'5s','5000000us'},
        'TimeoutStopUSec':{'2s','2000000us'}, 'SendSIGKILL':{'yes'},
        'KillSignal':{'15','SIGTERM','TERM'}, 'FinalKillSignal':{'9','SIGKILL','KILL'}}
    for key, values in expected.items():
        if properties.get(key) not in values:
            raise ValueError('unit property missing/unrecognized/mismatched: ' + key + '=' + repr(properties.get(key)))


def scan_pinned_cgroup(cgroup):
    """Không dùng path cuối rỗng hoặc lỗi đọc thay cho scan hoàn tất."""
    import os
    if not isinstance(cgroup, str) or not cgroup.startswith('/user.slice/') or '..' in Path(cgroup).parts:
        raise ValueError('unverified cgroup path')
    path = Path('/sys/fs/cgroup')/cgroup.lstrip('/')
    result = {'path':str(path), 'started_ns':time.monotonic_ns(), 'files':{}, 'errors':[], 'members':[]}
    try:
        path.stat()
    except FileNotFoundError:
        # ENOENT của chính path đã pin là fact; không suy từ lỗi walk.
        result.update(status='path_removed_confirmed', completed_ns=time.monotonic_ns())
        return result
    except OSError as error:
        result['errors'].append(repr(error))
    def onerror(error): result['errors'].append(repr(error))
    if not result['errors']:
        for directory, directories, filenames in os.walk(path, onerror=onerror, followlinks=False):
            try:
                for name in directories:
                    if Path(directory, name).is_symlink():
                        raise ValueError('unexpected symlink under pinned cgroup')
                raw = Path(directory, 'cgroup.procs').read_bytes()
                result['files'][str(Path(directory,'cgroup.procs'))] = raw.hex()
                result['members'].extend(int(value) for value in raw.split())
            except (OSError, ValueError) as error:
                result['errors'].append(repr(error))
    result['members'] = sorted(set(result['members']))
    result['status'] = 'incomplete' if result['errors'] or not result['files'] else 'complete_members' if result['members'] else 'complete_empty'
    result['completed_ns'] = time.monotonic_ns()
    return result




def b23_server_argv(world_file):
    """CLI Harmonic cài thật truyền --seed xuống runServer; không chỉ ghi nhãn."""
    return ('gz','sim','-v','3','--seed','20261029','--force-version','8','-s',
            '--headless-rendering',str(world_file))


def unit_parent_command(packet, packet_path, packet_sha256):
    """Giữ InvocationID thật từ systemd trong env sạch, không expand argv packet."""
    wrapper = 'exec /usr/bin/env -i "INVOCATION_ID=${INVOCATION_ID:?}" "$@"'
    return ['/bin/bash','-c',wrapper,'b23-owned-env',
        *[key+'='+value for key,value in sorted(packet['environment'].items())],
        packet['python'],'-B','-m',MODULE,'parent','--packet',packet_path,
        '--packet-sha256',packet_sha256]



def service_launch_command(packet, packet_path, packet_sha256):
    """Mẫu đã pin trong packet; chỉ thay self-hash sau khi xuất packet bất biến."""
    properties = packet.get('service_properties', service_properties_for(packet.get('active_s', 120)))
    return ['systemd-run','--user','--unit='+packet['unit'],'--expand-environment=no',
        *['--property='+value for value in properties],
        *unit_parent_command(packet, packet_path, packet_sha256)]


def launch_packet(args):
    """Đúng một unit/consume; terminal và residue do controller ngoài unit đo."""
    import os
    import sys
    import fcntl
    packet = verify_packet(args.packet, args.packet_sha256)
    root, guard = Path(packet['run_root']), Path(packet['guard_path'])
    log = RunEvidence(root, 'controller', run_id=packet['run_id'], invocation_id='OUTER_CONTROLLER')
    state = guard.parent
    lock = Path('/home/hazan/.local/state/ros2_nav2_drl/b22-simulation-runtime.lock').open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    primary, cleanup_error, unit, invocation, pinned_cgroup = None, None, packet['unit'], None, None
    metadata_cleanup_error = None
    identities, terminal, consumed, launch = {}, None, None, None
    try:
        for previous in sorted(state.iterdir()):
            if previous.is_dir() and (previous/'consumed.json').exists():
                predecessor = verify_previous_run_residue(state, previous,
                    evidence_root='/home/hazan/mecanum_runtime_evidence')
                log.record('PREVIOUS_RUN_RESIDUE_VERIFIED', predecessor)
        preflight = command_record(['systemctl','--user','show','--property=SystemState','--value'], timeout_s=5.)
        log.record('USER_MANAGER', preflight)
        if preflight['returncode'] != 0 or preflight['stdout'].strip() != 'running':
            raise RuntimeError('user manager unavailable; no permission/environment changes attempted')
        properties, record = unit_properties(unit, timeout_s=5.)
        log.record('UNIT_COLLISION_CHECK', record)
        if properties.get('LoadState') != 'not-found':
            raise RuntimeError('unit name already exists or collision query incomplete')
        authority = json.loads((guard/'authority.json').read_bytes())
        verify_guard_authority(packet, authority, args.packet_sha256)
        started = time.monotonic_ns()
        consumed = {'run_id':packet['run_id'], 'packet_sha256':args.packet_sha256, 'consumed_ns':started,
            'active_deadline_ns':started+packet['active_s']*10**9,
            'total_deadline_ns':started+(packet['active_s']+packet['cleanup_s'])*10**9}
        write_record_once(guard/'consumed.json', consumed)
        command = service_launch_command(packet, str(Path(args.packet).resolve()), args.packet_sha256)
        write_record_once(root/'launch-argv.json', {'argv':command, 'packet_sha256':args.packet_sha256})
        launch = command_record(command, timeout_s=min(5., (consumed['active_deadline_ns']-time.monotonic_ns())/1e9))
        log.record('SERVICE_LAUNCH', launch)
        # timeout/nonzero không chứng minh unit chưa được tạo; vẫn đối chiếu.
        end = consumed['total_deadline_ns']
        while time.monotonic_ns() < end:
            props, record = unit_properties(unit, timeout_s=min(2., max(0.,(end-time.monotonic_ns())/1e9)))
            log.record('UNIT_OBSERVATION', record)
            if props.get('InvocationID'):
                if invocation is None:
                    if (props.get('Id') != unit or args.packet_sha256 not in props.get('ExecStart','')
                            or str(Path(args.packet).resolve()) not in props.get('ExecStart','')):
                        raise RuntimeError('launched unit ownership cannot be verified')
                    invocation = props['InvocationID']
                elif invocation != props['InvocationID']:
                    raise RuntimeError('unit invocation changed')
            if props.get('ControlGroup'):
                if pinned_cgroup is None and invocation is not None:
                    candidate = props['ControlGroup']
                    if Path(candidate).name != unit:
                        raise RuntimeError('unit cgroup ownership mismatch')
                    pinned_cgroup = candidate
                elif props['ControlGroup'] != pinned_cgroup:
                    raise RuntimeError('unit cgroup changed')
            try:
                log.record('HOST_MEMORY', {'meminfo_hex':Path('/proc/meminfo').read_bytes().hex(),
                    'collected_ns':time.monotonic_ns()})
            except OSError as error:
                log.record('HOST_MEMORY_ERROR', {'error':repr(error)})
            if invocation is not None and props:
                verify_unit_configuration(props, active_s=packet['active_s'], cleanup_s=packet['cleanup_s'])
            if pinned_cgroup:
                scan = scan_pinned_cgroup(pinned_cgroup)
                log.record('CGROUP_OBSERVATION', scan)
                for pid in scan['members']:
                    try:
                        identity = process_identity(pid)
                        key = (pid,identity['start_ticks'])
                        if identity['argv'] or key not in identities:
                            identities[key] = identity
                        log.record('PID_OBSERVATION', identity)
                    except OSError as error:
                        log.record('PID_READ_ERROR', {'pid':pid,'error':repr(error)})
            if invocation is not None and (props.get('ActiveState') in ('inactive','failed')
                    or (props.get('ActiveState') == 'active' and props.get('SubState') == 'exited'
                        and props.get('MainPID') == '0' and int(props.get('ExecMainExitTimestampMonotonic','0')) > 0)):
                terminal = props
                break
            remaining = end-time.monotonic_ns()
            if remaining > 0: time.sleep(min(.2, remaining/1e9))
        if launch['returncode'] != 0:
            raise RuntimeError('service launch did not return success: ' + str(launch['returncode']))
        if terminal is None:
            raise RuntimeError('unit terminal not observed inside total deadline')
    except BaseException as error:
        primary = repr(error)
        log.record('CONTROLLER_PRIMARY_ERROR', {'error':primary})
    finally:
        # Chỉ invocation đã pin, sau khi đọc lại command+identity; không dò tên
        # process để kill. Ngân sách này không gia hạn total deadline.
        if consumed is not None:
            end = consumed['total_deadline_ns']
            try:
                if invocation is not None and (terminal is None or terminal.get('ActiveState') in ('active','failed')) and time.monotonic_ns() < end:
                    props, record = unit_properties(unit, timeout_s=min(1., (end-time.monotonic_ns())/1e9))
                    log.record('PRE_STOP_BINDING', record)
                    if (props.get('InvocationID') != invocation or props.get('Id') != unit
                            or (props.get('ControlGroup') != pinned_cgroup
                                and not (terminal is not None and props.get('ControlGroup') == ''
                                    and props.get('ActiveState') in ('active','inactive','failed') and props.get('MainPID') == '0'))
                            or args.packet_sha256 not in props.get('ExecStart','')):
                        raise RuntimeError('ownership changed/unverified: no stop dispatched')
                    record = command_record(['systemctl','--user','stop',unit],
                        timeout_s=min(2., max(0.,(end-time.monotonic_ns())/1e9)))
                    log.record('GUARDED_STOP', record)
                    if record['returncode'] != 0: raise RuntimeError('guarded stop incomplete')
                if invocation is None or pinned_cgroup is None:
                    raise RuntimeError('missing invocation/cgroup binding; residue UNKNOWN')
                scan = scan_pinned_cgroup(pinned_cgroup)
                log.record('FINAL_CGROUP', scan)
                absent = scan['status'] in ('complete_empty','path_removed_confirmed') and not scan['errors'] and not scan['members']
                pid_states = []
                for (pid, ticks), saved in identities.items():
                    try:
                        current = process_identity(pid)
                        same = current['start_ticks'] == ticks
                        pid_states.append({'saved':saved,'current':current,'same_identity':same})
                        if same: absent = False  # live hoặc zombie đều chưa sạch.
                    except FileNotFoundError:
                        pid_states.append({'saved':saved,'absent':True})
                    except OSError as error:
                        absent = False; pid_states.append({'saved':saved,'error':repr(error)})
                verified = {'run_id':packet['run_id'], 'packet_sha256':args.packet_sha256,
                    'invocation_id':invocation,'pinned_cgroup':pinned_cgroup,'terminal':terminal,
                    'residue_absent':absent,'scan':scan,'pid_states':pid_states,'completed_ns':time.monotonic_ns()}
                write_record_once(guard/'terminal-verified.json', verified)
                write_record_once(root/'terminal-evidence.json', verified)
                if not absent: raise RuntimeError('residue not verified absent; next run blocked')
            except BaseException as error:
                cleanup_error = repr(error)
                log.record('CONTROLLER_CLEANUP_ERROR', {'error':cleanup_error})
            journal = command_record(['journalctl','--user','-u',unit,'--no-pager','-o','json',
                *(['_SYSTEMD_INVOCATION_ID='+invocation] if invocation else [])], timeout_s=3.)
            log.record('JOURNAL_SUPPORT', journal)
            if terminal is not None and terminal.get('ActiveState') == 'failed' and cleanup_error is None:
                try:
                    clear_owned_failed_state(unit, invocation, terminal['ExecMainPID'], args.packet_sha256,
                        deadline_ns=end, emit=log.record)
                except BaseException as error:
                    metadata_cleanup_error = repr(error)
                    log.record('OWNED_FAILED_STATE_CLEAR_ERROR', {'error':metadata_cleanup_error})
        result = {'run_id':packet['run_id'], 'packet_sha256':args.packet_sha256,
            'primary_error':primary,'cleanup_error':cleanup_error, 'metadata_cleanup_error':metadata_cleanup_error, 'launch_record':launch,
            'terminal':terminal, 'completed_ns':time.monotonic_ns()}
        write_record_once(root/'controller-result.json', result)
        log.close(); fcntl.flock(lock, fcntl.LOCK_UN); lock.close()
    parent = json.loads((root/'parent-result.json').read_bytes()) if (root/'parent-result.json').exists() else None
    success = (primary is None and cleanup_error is None and metadata_cleanup_error is None and terminal is not None
        and terminal.get('Result') == 'success' and terminal.get('ExecMainCode') == str(os.CLD_EXITED)
        and terminal.get('ExecMainStatus') == '0' and parent is not None
        and parent['primary_error'] is None and parent['cleanup_clean']
        and parent['run_id'] == packet['run_id'] and parent['invocation_id'] == invocation
        and consumed is not None and parent['completed_ns'] <= consumed['total_deadline_ns']
        and json.loads((guard/'terminal-verified.json').read_bytes())['completed_ns'] <= consumed['total_deadline_ns'])
    parent_identity = json.loads((root/'parent-identity.json').read_bytes()) if (root/'parent-identity.json').exists() else None
    binding_errors = terminal_binding_errors(packet, terminal, parent_identity, identities, invocation, args.packet_sha256)
    success = success and not binding_errors
    assessment = {'run_id':packet['run_id'],
        'technical_outcome':technical_outcome(packet['case'], success),
        'evidence':str(root),'primary_error':primary,'cleanup_error':cleanup_error,
        'terminal_binding_errors':binding_errors, 'metadata_cleanup_error':metadata_cleanup_error,
        'parent_primary_error':None if parent is None else parent.get('primary_error'), 'assessed_ns':time.monotonic_ns()}
    write_record_once(root/'r01a-assessment.json', assessment)
    hashes = {str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob('*') if path.is_file()}
    guard_hashes = {str(path):hashlib.sha256(path.read_bytes()).hexdigest()
        for path in guard.iterdir() if path.is_file()}
    write_record_once(root/'evidence-manifest.json', {'schema':'b23_evidence_manifest/v1',
        'run_id':packet['run_id'],'source_commit':packet['source_commit'],
        'packet_sha256':args.packet_sha256,'files':hashes,'guard_files':guard_hashes})
    print(json.dumps(assessment))
    return 0 if success else 1




def clear_owned_failed_state(unit, invocation, terminal_pid, packet_sha256, *, deadline_ns, emit,
                             now_ns=time.monotonic_ns):
    """Chỉ metadata unit đã thất bại, sau raw journal và proof không còn process.

    Không reset guard, không đổi verdict và không chạm failed unit khác.
    """
    remaining = (deadline_ns-now_ns())/1e9
    if remaining <= 0: raise TimeoutError('owned failed-state cleanup budget expired')
    properties, record = unit_properties(unit, timeout_s=min(1., remaining))
    emit('PRE_FAILED_STATE_CLEAR_BINDING', record)
    if (properties.get('Id') != unit or properties.get('InvocationID') != invocation
            or properties.get('ExecMainPID') != str(terminal_pid) or properties.get('MainPID') != '0'
            or properties.get('ActiveState') not in ('failed','inactive')
            or properties.get('ControlGroup') != '' or packet_sha256 not in properties.get('ExecStart','')):
        raise RuntimeError('failed-state ownership changed/unverified; no reset dispatched')
    remaining = (deadline_ns-now_ns())/1e9
    if remaining <= 0: raise TimeoutError('owned failed-state cleanup budget expired before reset')
    record = command_record(['systemctl','--user','reset-failed',unit], timeout_s=min(1.,remaining))
    emit('OWNED_FAILED_STATE_CLEAR_RESULT', record)
    if record['returncode'] != 0 or record['error'] is not None:
        raise RuntimeError('own failed-state clear failed')


def terminal_binding_errors(packet, terminal, parent_record, observed, invocation, packet_sha256):
    """Nối terminal unit tới PID/start ticks/argv đã đo, không dùng tên chung."""
    errors = []
    if terminal is None or parent_record is None:
        return ['missing unit terminal or actual parent identity record']
    identity = parent_record.get('identity', {})
    pid, ticks = identity.get('pid'), identity.get('start_ticks')
    saved = observed.get((pid,ticks))
    if (parent_record.get('invocation_id') != invocation or parent_record.get('run_id') != packet['run_id']
            or parent_record.get('packet_sha256') != packet_sha256
            or terminal.get('InvocationID') != invocation or terminal.get('Id') != packet['unit']
            or terminal.get('ExecMainPID') != str(pid)):
        errors.append('unit/InvocationID/ExecMainPID/packet binding mismatch')
    expected = [packet['python'],'-B','-m',MODULE,'parent','--packet',str(Path(packet['run_root'])/'packet.json'),
                '--packet-sha256',packet_sha256]
    if (saved is None or identity.get('uid') != 1000 or identity.get('argv') != expected
            or saved.get('argv') != expected or saved.get('uid') != 1000):
        errors.append('parent identity/argv not independently observed or changed')
    return errors


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='B2.3 campaign runner với packet/guard capacity-one')
    commands = parser.add_subparsers(dest='role', required=True)
    prepare = commands.add_parser('prepare')
    for key in ('repo','commit','install','build-binding','run-id'):
        prepare.add_argument('--'+key, required=True)
    prepare.add_argument('--case', choices=tuple(CASE_HOOKS), default='R01a')
    prepare.add_argument('--fault-hook', choices=tuple(sorted({hook for hooks in CASE_HOOKS.values() for hook in hooks})))
    prepare.add_argument('--junit', action='append', required=True)
    for role in ('launch','parent'):
        command = commands.add_parser(role)
        command.add_argument('--packet', required=True); command.add_argument('--packet-sha256', required=True)
    for role in ('worker','final'):
        commands.add_parser(role).add_argument('--descriptor', required=True)
    args = parser.parse_args(argv)
    if args.role == 'prepare': return prepare_packet(args)
    if args.role == 'launch': return launch_packet(args)
    if args.role == 'parent': return asyncio.run(run_parent(args.packet, args.packet_sha256))
    if args.role == 'worker': return asyncio.run(training_child(args.descriptor))
    return final_child(args.descriptor)


if __name__ == '__main__':
    raise SystemExit(main())
