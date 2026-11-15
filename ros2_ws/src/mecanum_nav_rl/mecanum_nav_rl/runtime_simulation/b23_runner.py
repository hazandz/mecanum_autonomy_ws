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
from pathlib import Path
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
    'R07a':'fault_task', 'R07b':'fault_task', 'R08': 'soak'}
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
    'R08': (),
}


def service_properties_for(active_s):
    """Unit cap exactly covers active and cleanup budgets for the packet."""
    if type(active_s) is not int or active_s not in (120, 900):
        raise ValueError('unsupported B2.3 active runtime budget')
    return (*SERVICE_PROPERTIES, f'RuntimeMaxSec={active_s + 60}s')


def verify_r07b_revocation(*, response, original_proof, sim_before_ns,
                           sim_after_ns, replay_ack, fresh_ack, inhibit_ack):
    """Require rollback, revoked QUERY replay/fresh response, and INHIBIT ACK."""
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    if sim_after_ns >= sim_before_ns:
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
        'contact_state':response.contact_capability_state,
        'query_replay_revoked':True,'fresh_query_revoked':True,
        'inhibit_request_sequence':inhibit_ack.request.request_sequence,
        'inhibit_revision':inhibit_ack.response.applied_binding_revision}


def verify_r07a_unexpected_pause(*, world_ack, world_pause_state, backend_state, pre_pause_policy_receipts,
                                 post_pause_policy_receipts, reset_count_before,
                                 reset_count_after):
    """Require external pause to produce native fault/zero without later POLICY."""
    if not world_ack.success or world_pause_state is not True:
        raise RuntimeError('R07a world pause ACK/state was not confirmed')
    if (backend_state is None or backend_state.fault_flags != 1
            or not backend_state.local_zero_override or backend_state.actuator_inhibited is False):
        raise RuntimeError('R07a lacks native unexpected-pause fault and zero override')
    if post_pause_policy_receipts != pre_pause_policy_receipts:
        raise RuntimeError('R07a observed a POLICY receipt after unexpected pause')
    if reset_count_after != reset_count_before:
        raise RuntimeError('R07a reset/observation0 advanced after unexpected pause')
    return {'world_pause_acknowledged':True,'world_pause_state':world_pause_state,
        'native_fault_flags':backend_state.fault_flags,
        'native_zero_override':True,'policy_receipt_count_unchanged':True,
        'reset_count_unchanged':True}


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
            state['scheduled'] += 1
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
        timer.start()
        return None
    adapter._b23_r04_injector = callback
    return state


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
                                           allow_pending=False):
    """Require the pre-bind sample to stay out of the new native admission slot."""
    accepted = [row for row in rows if row.get('kind') == 'B23_ADMISSION_ACCEPTED']
    if any(int(row.get('fields', {}).get('sample', '0')) == held_sample_sequence for row in accepted):
        raise RuntimeError('R02e pre-bind sample was accepted by the new native slot')
    fresh = [row for row in accepted
        if int(row.get('fields', {}).get('sample', '0')) == fresh_sample_sequence]
    if not fresh and allow_pending:
        return None
    if len(fresh) != 1 or not any(pending_token):
        raise RuntimeError('R02e fresh post-bind admission was not accepted exactly once')
    return {'prebind_sample_sequence': held_sample_sequence,
        'prebind_native_accept_count': 0,
        'postbind_sample_sequence': fresh_sample_sequence,
        'postbind_native_accept_count': 1,
        'pending_token_nonzero': True}


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
    from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
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
    publications = [receipt for receipt in io.ingress.receipts
        if receipt.source is ReceiptSource.POLICY
        and receipt.source_sequence == step_index
        and receipt.final_publisher_instance_id == io.final.publisher_instance_id]
    if (fault_publisher != io.final.publisher_instance_id or fault_source_sequence != step_index
            or fault_sequence not in {receipt.final_publish_sequence for receipt in publications}):
        raise RuntimeError('R03 native hook does not bind to a retained final POLICY receipt')
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
    if case == 'R02b':
        if not 0 <= admission_to_receipt_ns <= 40_000_000:
            raise RuntimeError('R02b receipt did not arrive within the 40 ms bounded admission hold')
        held = [row for row in rows if row.get('kind') == 'B23_POLICY_ADMISSION_HELD'
            and int(row.get('fields',{}).get('receive_ns','0')) == admission_receive_ns]
        if not held or int(held[0].get('fields',{}).get('limit_ns','0')) != 40_000_000:
            raise RuntimeError('R02b does not prove the packet-scoped 40 ms admission hold')
    return {'case':case,'receipt_ingress_ns':receipt_ns,'admission_received_ns':admission_receive_ns,
        'admission_gate_ns':admission_ns,'admission_minus_receipt_ns':admission_ns-receipt_ns,
        'admission_to_receipt_ns':admission_to_receipt_ns,
        'order':'admission_before_receipt' if admission_ns < receipt_ns else 'receipt_before_admission'}


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
        input_rejected = next((facts for name, facts in io.events
            if name == 'SAFETY_INPUT_REJECTED'
            and facts.get('reason') == 'SAFETY_INPUT_REPLAY_OR_CONFLICT'
            and facts.get('steady_ns', 0) >= delayed['delivery_ns']), None)
        rejected = next((facts for name, facts in io.events
            if name == 'SAFETY_REJECTED'
            and 'SAFETY_INPUT_REPLAY_OR_CONFLICT' in facts.get('reasons', ())
            and facts.get('steady_ns', 0) >= (input_rejected or {}).get('steady_ns', 0)), None)
        if input_rejected is None or rejected is None:
            raise RuntimeError('R04a lacks a delayed-input replay rejection and production Safety block')
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
            'input_rejection_reason':input_rejected['reason'],
            'safety_rejection_reasons':list(rejected.get('reasons', ())),
            'rejected_steady_ns':rejected['steady_ns'],
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
    def observed():
        delayed = next((facts for name, facts in reversed(io.events)
            if name == 'B23_R04_DELIVERY_DELAYED_CALLBACK' and facts.get('case') == 'R04a'), None)
        input_rejected = next((facts for name, facts in reversed(io.events)
            if name == 'SAFETY_INPUT_REJECTED'
            and facts.get('reason') == 'SAFETY_INPUT_REPLAY_OR_CONFLICT'), None)
        if delayed is None or input_rejected is None or input_rejected.get('steady_ns', 0) < delayed.get('delivery_ns', 0):
            return None
        return next((facts for name, facts in reversed(io.events)
            if name == 'SAFETY_REJECTED'
            and 'SAFETY_INPUT_REPLAY_OR_CONFLICT' in facts.get('reasons', ())
            and facts.get('steady_ns', 0) >= input_rejected['steady_ns']), None)
    return await io.until(observed, deadline_ns=deadline_ns,
        phase='R04a bounded production Safety rejection after delayed replay')


def verify_r04a_next_step_blocked(io, *, step_index):
    """Prove delayed out-of-order Safety input cannot authorize the next slot."""
    input_rejected = next((facts for name, facts in io.events
        if name == 'SAFETY_INPUT_REJECTED'
        and facts.get('reason') == 'SAFETY_INPUT_REPLAY_OR_CONFLICT'), None)
    rejected = next((facts for name, facts in io.events
        if name == 'SAFETY_REJECTED'
        and 'SAFETY_INPUT_REPLAY_OR_CONFLICT' in facts.get('reasons', ())
        and input_rejected is not None
        and facts.get('steady_ns', 0) >= input_rejected.get('steady_ns', 0)), None)
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
        raise RuntimeError('R04a lacks a post-rejection exact native SAFE_STOP receipt application')
    return {'blocked_step_index':step_index,
        'input_rejection_steady_ns':input_rejected['steady_ns'],
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
    proof = checked.get('native_zero_application') if isinstance(checked, dict) else None
    if (not isinstance(proof, dict) or type(proof.get('publisher_instance_id')) is not int
            or type(proof.get('final_publish_sequence')) is not int
            or proof['publisher_instance_id'] != io.final.publisher_instance_id):
        raise RuntimeError('R04a native zero proof is not bound to the FinalTwistPublisher')
    if (state is None or not state.applied_receipt_valid or state.local_zero_override
            or state.fault_flags != 0
            or state.applied_final_publisher_instance_id != io.final.publisher_instance_id
            or state.applied_final_publish_sequence < proof['final_publish_sequence']):
        raise RuntimeError('R04a native backend lost its healthy applied-zero baseline')
    if (stop is None or stop.source != CommandEnvelope.SOURCE_SAFE_STOP
            or any((stop.twist.linear.x, stop.twist.linear.y, stop.twist.angular.z))):
        raise RuntimeError('R04a current Safety output is not zero SAFE_STOP')
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
        self.expected_paused = True
        self.last_clock_ns, self.last_clock_advance_ns = 0, self.now()
        self._native_offset, self._native_partial = 0, b''
        self._native_input_watermark = 0
        self.contact_ack = None
        self.contact_start_request_sequence = None
        self._r07b_rollback_pending_before_ns = None
        self._r07b_rollback_observed = None
        try:
            rclpy.init(context=self.context)
            self.executor = SingleThreadedExecutor(context=self.context)
            base_params = [Parameter('use_sim_time', value=True)]
            mode_params = base_params + [Parameter('navigation_mode', value='LOCAL_TRAINING')]
            self.node = Node('b23_coordinator_ingress', context=self.context, parameter_overrides=base_params)
            self.nodes.append(self.node)
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
        def receive(raw, info):
            if not isinstance(raw,(bytes,bytearray,memoryview)):
                raise TypeError('raw subscription did not return serialized bytes')
            wire=bytes(raw)
            self.emit('INGRESS_WIRE_RECEIVED', {'topic':topic,
                'received_ns':self.now(), 'wire_cdr_hex':wire.hex(),
                'message_info':{key:value for key,value in info.items() if type(value) is int}})
            try:
                message = deserialize_message(wire,message_type)
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
                    receipt_view = callback(message)
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
                return callback(message)
            except BaseException as error:
                self.emit('INGRESS_CALLBACK_ERROR', {'topic':topic,'error':repr(error),
                    'wire_sha256':hashlib.sha256(wire).hexdigest(),'detected_ns':self.now()})
                raise
        return receive

    def ros_now(self):
        return self.node.get_clock().now().nanoseconds

    def start_pump(self):
        if self.pump_task is not None:
            raise RuntimeError('executor pump already started')
        self.pump_task = asyncio.create_task(self._pump(), name='b23-owned-ros-pump')

    async def _pump(self):
        try:
            while not self.stop_requested:
                for _ in range(16):
                    self.executor.spin_once(timeout_sec=0.)
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
        if now >= self.deadline_ns:
            raise TimeoutError('B23 active deadline reached')
        if ros < self.last_clock_ns:
            rollback_before = self._r07b_rollback_pending_before_ns
            if (rollback_before is None or ros >= rollback_before
                    or self._r07b_rollback_observed is not None):
                raise RuntimeError('ROS clock rolled backward')
            self._r07b_rollback_observed = {
                'before_ns': rollback_before, 'after_ns': ros, 'observed_steady_ns': now}
            self._r07b_rollback_pending_before_ns = None
            self.last_clock_ns, self.last_clock_advance_ns = ros, now
            self.emit('B23_R07B_CLOCK_ROLLBACK_OBSERVED', self._r07b_rollback_observed)
        if ros > self.last_clock_ns:
            self.last_clock_ns, self.last_clock_advance_ns = ros, now
        if not self.expected_paused and now - self.last_clock_advance_ns > 1_000_000_000:
            raise RuntimeError('unexpected clock stall exceeded 1 s')
        if self.ingress.fault:
            raise RuntimeError('ingress fault: ' + self.ingress.fault)
        if self.ingress.backend_state is not None and self.ingress.backend_state.fault_flags:
            state = self.ingress.backend_state
            # The expected native fault and its zero override may arrive in
            # adjacent status publications. While polling for the closed
            # state, tolerate only the exact packet-pinned fault code; the
            # caller's terminal predicate still requires local_zero_override.
            if state.fault_flags != expected_native_fault_flags:
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

    async def wait_r02e_native_admission(self, *, held_sample_sequence,
            fresh_sample_sequence, pending_token, deadline_ns):
        """Wait within the active step budget for the native event-pipe record."""
        path = self.descriptor['native_events_path']
        return await self.until(lambda: verify_r02e_prebind_admission_rejected(
                complete_jsonl_rows(path), held_sample_sequence=held_sample_sequence,
                fresh_sample_sequence=fresh_sample_sequence, pending_token=pending_token,
                allow_pending=True),
            deadline_ns=deadline_ns, phase='R02e native pre-bind rejection and fresh acceptance')

    async def call(self, client, request, *, timeout_s, phase):
        from rclpy.serialization import serialize_message
        started = self.now()
        deadline = min(self.deadline_ns, started + int(timeout_s * 1e9))
        await self.until(client.service_is_ready, deadline_ns=deadline, phase=phase + ' service ready')
        if self.now() >= deadline:
            raise TimeoutError(phase + ': no remaining submit budget')
        self.emit('RPC_REQUEST', {'phase': phase, 'request_cdr_hex': serialize_message(request).hex(),
            'started_ns': started, 'deadline_ns': deadline})
        future = client.call_async(request)
        self.calls.append(future)
        try:
            await self.until(future.done, deadline_ns=deadline, phase=phase + ' ACK')
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

    async def control_world(self, *, world_name, pause, timeout_s):
        from rclpy.serialization import serialize_message
        if world_name != 'b2_training_arena' or type(pause) is not bool:
            raise ValueError('world control target invalid')
        request = self.control_world_type.Request()
        request.world_control.pause = pause
        response = await self.call(self.world_client, request, timeout_s=timeout_s,
            phase='world_pause' if pause else 'world_resume')
        self.emit('WORLD_PAUSE_CONTROL', {'world':world_name,'requested_pause':pause,
            'request_cdr_hex':serialize_message(request).hex(),
            'response_success':response.success,
            'steady_ns':self.now()})
        return response

    async def reset_world_time_only(self, *, timeout_s):
        """Apply the packet-pinned Gazebo time_only rollback through ControlWorld."""
        from rclpy.serialization import serialize_message
        before = self.ros_now()
        request = self.control_world_type.Request()
        request.world_control.reset.time_only = True
        request.world_control.reset.all = False
        request.world_control.reset.model_only = False
        request.world_control.pause = False
        if 'time_only_rollback_after_contact_proof' not in self.fault_hooks:
            raise RuntimeError('R07b time_only reset is not authorized by this packet hook')
        self._r07b_rollback_pending_before_ns = before
        self._r07b_rollback_observed = None
        response = await self.call(self.world_client, request, timeout_s=timeout_s,
            phase='R07b_world_time_only_rollback')
        after = self.ros_now()
        self.emit('B23_R07B_TIME_ONLY_RESET', {
            'world':'b2_training_arena','pause':False,'reset_all':False,
            'reset_time_only':True,'reset_model_only':False,
            'request_cdr_hex':serialize_message(request).hex(),
            'response_success':response.success,
            'sim_before_ns':before,'sim_after_ns':after,'steady_ns':self.now()})
        if not response.success:
            raise RuntimeError('R07b world time_only API returned unsuccessful ACK')
        if after >= before or self._r07b_rollback_observed is None:
            raise RuntimeError('R07b clock rollback was not observed through the worker clock monitor')
        self.last_clock_ns, self.last_clock_advance_ns = after, self.now()
        return before, after

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
            self.emit('GRAPH_OBSERVATION', {name: [{'node': item.node_name,
                'namespace': item.node_namespace, 'type': item.topic_type,
                'gid_hex': bytes(item.endpoint_gid).hex()} for item in values]
                for name, values in [('cmd_vel',cmd),('safety',safety),('ingress',ingress)]})
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
            return cmd, safety, ingress
        cmd, safety, ingress = await self.until(endpoints, deadline_ns=deadline_ns, phase='source graph binding')
        self.ingress.bind_safety_publisher_gid(safety[0].endpoint_gid)
        self.emit('GRAPH_BOUND', {name: [{'node': item.node_name, 'namespace': item.node_namespace,
                'type': item.topic_type, 'gid_hex': bytes(item.endpoint_gid).hex()} for item in values]
            for name, values in [('cmd_vel', cmd), ('safety', safety), ('ingress', ingress)]})

    async def paused_state(self, paused, timeout):
        status = await self.until(lambda: self.ingress.backend_state if self.ingress.backend_state is not None
            and self.ingress.backend_state.paused is paused else None,
            deadline_ns=self.now() + int(timeout * 1e9), phase='paused' if paused else 'resumed')
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
        with path.open('rb') as stream:
            stream.seek(self._native_offset)
            raw = self._native_partial + stream.read(1_048_576)
            self._native_offset = stream.tell()
        lines = raw.split(b'\n'); self._native_partial = lines.pop()
        for line in lines:
            record = json.loads(line)
            if record['kind'] not in ('B23_SAFETY_INPUT_OBSERVED', 'B23_ADMISSION_ACCEPTED'):
                continue
            fields = record['fields']
            if (fields['session'] != self.descriptor['session_id']
                    or int(fields['backend']) != self.descriptor['backend_instance_id']
                    or int(fields['ingress']) != self.descriptor['coordinator_ingress_instance_id']
                    or record['server_leader_pid'] != self.descriptor['server_leader_pid']
                    or record['invocation_id'] != self.descriptor['invocation_id']):
                raise RuntimeError('native input evidence ownership mismatch')
            self._native_input_watermark = max(self._native_input_watermark, int(fields['sample']))
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
        try:
            await self.control.inhibit(deadline_ns=min(deadline_ns, self.now() + 1_000_000_000))
        except BaseException as error:
            errors.append('inhibit:' + repr(error))
        self.safety.local_training.set_stream_enabled(False)
        self.ingress.pause_admission_publication()
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

    def close_context(self):
        errors = []
        for node in reversed(self.nodes):
            try:
                if self.executor is not None: self.executor.remove_node(node)
                node.destroy_node()
            except BaseException as error:
                errors.append(repr(error))
        self.nodes.clear()
        if self.executor is not None:
            try:
                if not self.executor.shutdown(timeout_sec=0.):
                    errors.append('executor_shutdown_not_joined')
            except BaseException as error: errors.append(repr(error))
        try:
            if self.context.ok(): self.context.shutdown()
        except BaseException as error:
            errors.append(repr(error))
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
        require its adjacent receipt after the cutoff. B1 still enforces the
        unchanged 500 ms freshness rule for both receipts.
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

            def next_boundary_receipt():
                matches = [item for item in self.ingress.receipts
                    if item.final_publisher_instance_id == receipt.final_publisher_instance_id
                    and item.final_publish_sequence == receipt.final_publish_sequence + 1]
                if not matches:
                    return None
                if (len(matches) != 1 or matches[0].lifecycle != identity
                        or matches[0].source is not ReceiptSource.SAFE_STOP
                        or matches[0].publish_stamp_ns <= target_ns
                        or any(matches[0].final_command)):
                    raise RuntimeError('post-cutoff SAFE_STOP receipt does not prove the adjacent boundary')
                return matches[0]

            adjacent_deadline = min(deadline_ns, receipt.received_steady_ns + max_gap_ns)
            adjacent = await self.until(next_boundary_receipt, deadline_ns=adjacent_deadline,
                phase='post-cutoff reset SAFE_STOP boundary receipt')
            receive_gap_ns = adjacent.received_steady_ns - receipt.received_steady_ns
            if (not 0 <= receive_gap_ns <= max_gap_ns
                    or self.now() - adjacent.received_steady_ns > max_gap_ns):
                raise RuntimeError('reset SAFE_STOP publication gap exceeded 500 ms freshness')
            self.emit('RESET_RECEIPT_ALIGNMENT_BOUNDARY', {'target_scan_ns': target_ns,
                'selected_receipt_sequence': receipt.final_publish_sequence,
                'selected_receipt_stamp_ns': receipt.publish_stamp_ns,
                'selected_application_iteration': state.applied_physics_iteration,
                'selected_application_stamp_ns': stamp_ns(state.applied_sim_stamp),
                'adjacent_receipt_sequence': adjacent.final_publish_sequence,
                'adjacent_receipt_stamp_ns': adjacent.publish_stamp_ns,
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
        self.ingress.pause_admission_publication()
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
            receipt = self.final.last_publication
            if (receipt is None or receipt.source != CommandEnvelope.SOURCE_SAFE_STOP
                    or receipt.source_instance_id != last.source_instance_id
                    or receipt.sequence != last.sequence):
                return None
            return receipt
        receipt = await self.until(drained, deadline_ns=deadline_ns, phase='Final SAFE_STOP publication drain')
        await self.until(lambda: self.ingress.backend_state if self.ingress.backend_state is not None
            and self.ingress.backend_state.fault_flags == 0
            and self.ingress.backend_state.applied_final_publish_sequence == receipt.final_publish_sequence
            and self.ingress.backend_state.applied_final_publisher_instance_id == self.final.publisher_instance_id
            and not self.ingress.backend_state.local_zero_override else None,
            deadline_ns=deadline_ns, phase='SAFE_STOP application before pending step')
        self.emit('STEP_STREAMS_FROZEN', {'source': last.source, 'source_sequence': last.sequence,
            'publish_sequence': receipt.final_publish_sequence, 'watchdog_zero_stream_active': True,
            'steady_ns': self.now()})

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
                          align_admission_after_scan_boundary=False):
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
        await self.freeze_step_streams(deadline_ns=deadline)
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
        held_prebind = None
        if prebind_admission:
            if self.ingress.pending_ack is None or self.ingress.admission_state != LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN:
                raise RuntimeError('R02e needs a live previous pending token before rebinding')
            with self.ingress.lock:
                candidates = tuple(self.ingress.noisy_samples.values())
            if not candidates:
                raise RuntimeError('R02e has no actual noisy sample to carry across the bind')
            sample = candidates[-1]
            self.ingress.admission_publication_enabled = True
            self._hold_next_safety_input = True
            self.ingress._publish_safety(sample)
            held_prebind = self._held_safety_input
            if held_prebind is None:
                raise RuntimeError('R02e producer did not create a held pre-bind input')
            if (held_prebind.admission_state != LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN
                    or not any(held_prebind.admission_token)
                    or held_prebind.sample_sequence == 0):
                raise RuntimeError('R02e held sample is not a valid prior-token POLICY admission')
            self.ingress.pause_admission_publication()
        # A SAFE_STOP arriving after OP_BIND_PENDING_STEP revokes the pending
        # admission by contract. The last zero receipt above is already native
        # applied, so stop emitting zero while this single slot is bound; native
        # zero remains in force until Safety publishes the admitted POLICY.
        self.safety.local_training.set_stream_enabled(False)
        token = b1.begin_step()
        barrier = self.ros_now()
        if barrier <= stamp_ns(self.ingress.lifecycle.barrier_stamp):
            raise RuntimeError('action barrier is not after authoritative lifecycle barrier')
        ack = await self.control.transact(Control.Request.OP_BIND_PENDING_STEP,
            deadline_ns=deadline, pending_step_index=token.step_index,
            pending_source_sequence=token.step_index, pending_transition_id=token.transition_id,
            action_barrier_stamp=self._time_msg(barrier))
        self.ingress.arm_pending(ack)
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
        held_sample_sequence = None
        if held_prebind is not None:
            held_sample_sequence = held_prebind.sample_sequence
            self.safety_publisher.publish(held_prebind)
            self.emit('R02E_PREBIND_SAFETY_INPUT_RELEASED_AFTER_BIND', {
                'sample_sequence': held_sample_sequence,
                'prior_token_hex': bytes(held_prebind.admission_token).hex(),
                'new_token_hex': bytes(ack.response.pending_admission_token).hex(),
                'request_sequence': ack.request.request_sequence,
                'binding_revision': ack.response.applied_binding_revision,
                'steady_ns': self.now()})
            if bytes(held_prebind.admission_token) == bytes(ack.response.pending_admission_token):
                raise RuntimeError('R02e test sample unexpectedly has the current slot token')
        await self.until(lambda: self.safety.local_training.noisy if self.safety.local_training.noisy is not None
            and self.safety.local_training.noisy.admission_state == LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN
            and bytes(self.safety.local_training.noisy.admission_token) == bytes(ack.response.pending_admission_token)
            and self.ingress.last_published_sample_sequence == self.safety.local_training.noisy.sample_sequence
            else None, deadline_ns=deadline, phase='post-ACK admission delivered to Safety')
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
        if close_after_held_receipt is not None:
            if close_after_held_receipt not in ('safe_stop', 'admission_inhibited'):
                raise ValueError('unsupported R02 close trigger')
            # The pending slot is admitted, but Safety's timer was held off
            # during bind/sample delivery so no SAFE_STOP can revoke it. Now
            # allow the real timer to publish POLICY; native captures that
            # receipt before the case-specific close condition is injected.
            self.safety.local_training.set_stream_enabled(True)
            self.safety.local_training.set_policy_hold(False)
            policy_receipt = await self.until(lambda: self.final.publication_for_source_sequence(
                source=CommandEnvelope.SOURCE_POLICY, sequence=token.step_index),
                deadline_ns=deadline, phase='actual held POLICY publication receipt')
            expected_mode = ('hold_policy_until_safe_stop' if close_after_held_receipt == 'safe_stop'
                else 'hold_policy_until_inhibit')
            def held_row():
                rows = [json.loads(line) for line in Path(self.descriptor['native_events_path'])
                    .read_text().splitlines() if line.strip()]
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
            from mecanum_nav_rl_interfaces.msg import SimulationContactState
            expected_native_fault_flags = (SimulationContactState.FAULT_COMMAND_SEQUENCE
                | SimulationContactState.FAULT_COMMAND_STALE)
            def released_row():
                rows = [json.loads(line) for line in Path(self.descriptor['native_events_path'])
                    .read_text().splitlines() if line.strip()]
                return next((row for row in rows
                    if row.get('kind') == 'B23_POLICY_RECEIPT_RELEASED_AFTER_CLOSE'
                    and row.get('fields', {}).get('reason') == expected_reason
                    and row.get('fields', {}).get('sequence') == str(policy_receipt.final_publish_sequence)), None)
            await self.until(released_row, deadline_ns=deadline,
                phase='held POLICY receipt released only after closing condition',
                expected_native_fault_flags=expected_native_fault_flags)
            native_fault = await self.until(lambda: self.ingress.backend_state
                if self.ingress.backend_state is not None
                and self.ingress.backend_state.fault_flags == expected_native_fault_flags
                and self.ingress.backend_state.local_zero_override else None,
                deadline_ns=deadline, phase='native rejection and local zero after late POLICY receipt',
                expected_native_fault_flags=expected_native_fault_flags)
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
        self.safety.local_training.set_stream_enabled(True)
        self.safety.local_training.set_policy_hold(False)
        minimum_cutoff = stamp_ns(envelope.header.stamp) + 100_000_000
        last_pending = None
        last_pending_key = None
        while self.now() < deadline:
            self.check()
            for cutoff in sorted(stamp for stamp in self.ingress.scans if stamp >= minimum_cutoff):
                try:
                    transition = b1.commit_step(cutoff)
                except B1SnapshotPending as error:
                    last_pending = str(error)
                    pending_key = (cutoff, last_pending)
                    if pending_key != last_pending_key:
                        self.emit('POLICY_CUTOFF_PENDING', {'step_index': token.step_index,
                            'transition_id': token.transition_id, 'cutoff_ns': cutoff,
                            'reason': last_pending, 'steady_ns': self.now()})
                        last_pending_key = pending_key
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


class RunEvidence:
    """Sổ riêng từng process, raw stdout native và bốn book không gộp số đếm."""
    BOOKS = frozenset(('policy_adapter_issued', 'policy_final_published',
                      'policy_backend_applied', 'b1_transition_committed'))

    def __init__(self, root, role, *, run_id, invocation_id):
        self.root, self.role, self.run_id, self.invocation_id = Path(root), role, run_id, invocation_id
        self.streams = {}
        self.errors = []
        self.closed = False

    def append(self, filename, record):
        if self.closed:
            raise RuntimeError('evidence sink already closed')
        if filename not in self.streams:
            self.streams[filename] = (self.root/filename).open('x', encoding='utf-8')
        raw = json.dumps(record, sort_keys=True, separators=(',', ':'), allow_nan=False, default=evidence_json_value)
        self.streams[filename].write(raw + '\n')
        self.streams[filename].flush()

    def record(self, event, facts):
        record = {'event': event, 'facts': facts, 'run_id': self.run_id,
            'invocation_id': self.invocation_id, 'role': self.role,
            'collected_ns': time.monotonic_ns()}
        self.append(self.role + '-events.jsonl', record)
        if event in self.BOOKS:
            self.append(event + '.jsonl', record)
        if event == 'owned_process_output' and facts.get('process') == 'server':
            import re
            text = re.sub(r'\x1b\[[0-9;]*m', '', facts['text'])
            match = re.search(r'\b(B23_[A-Z_]+)\s+(.*)', text)
            if match:
                fields = dict(re.findall(r'(\w+)=([^\s]+)', match[2]))
                self.append('native-events.jsonl', {'kind': match[1], 'fields': fields,
                    'raw_record': record, 'server_leader_pid': facts['pid'],
                    'invocation_id': self.invocation_id, 'collected_ns': time.monotonic_ns()})

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
        for stream in self.streams.values():
            stream.flush(); os.fsync(stream.fileno())

    def close(self):
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
            Parameter('session_id', value=descriptor['session_id'])], evidence_sink=sink.record)
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
    terminal_seen = False
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
        if episode_index < 29 and not terminal_seen:
            raise RuntimeError('B2_SOAK_V1 scheduled episode ended without terminal')
        if episode_index == 29 and not terminal_seen:
            sink.record('COLLECTION_CUTOFF', {'episode_index':episode_index,
                'step_count':expected_steps,'seed':seed,'reason':'final_slot_unfinished'})
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
        'collection_cutoff':not terminal_seen,'completed_ns':time.monotonic_ns()}


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
            scan_transform=lambda: io.safety._tf_buffer.lookup_transform('base_link', 'lidar_frame', Time()), emit=sink.record)
        if packet['case'] == 'R08':
            if len(packet['episode_seeds']) != 30:
                raise RuntimeError('R08 requires the exact 30 B2_SOAK_V1 seeds')
            outcome = await _run_b2_soak(io, b1, packet, sink)
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
            before_policy = sum(1 for receipt in io.ingress.receipts
                if receipt.source == receipt.SOURCE_POLICY)
            reset_fact_before = b1.lifecycle.snapshot.reset_commit_facts
            previous_ros = io.ros_now()
            io.expected_paused = True
            world_ack = await io.control_world(world_name='b2_training_arena', pause=True,
                timeout_s=min(1.0, max(0.0, (io.deadline_ns-io.now())/1e9)))
            pause_state = await io.paused_state(True, min(1.0,
                max(0.0, (io.deadline_ns-io.now())/1e9)))
            io.emit('B23_R07A_UNEXPECTED_PAUSE_ARMED', {
                'after_policy_step':transition.transition_identity.step_index,
                'pre_pause_policy_receipt_count':before_policy,
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
            policy_after = sum(1 for receipt in io.ingress.receipts
                if receipt.source == receipt.SOURCE_POLICY)
            reset_fact_after = b1.lifecycle.snapshot.reset_commit_facts
            checked = verify_r07a_unexpected_pause(world_ack=world_ack,
                world_pause_state=pause_state,
                backend_state=state, pre_pause_policy_receipts=before_policy,
                post_pause_policy_receipts=policy_after,
                reset_count_before=reset_fact_before, reset_count_after=reset_fact_after)
            await asyncio.sleep(min(.250, max(0.0, (io.deadline_ns-io.now())/1e9)))
            if io.now() >= io.deadline_ns:
                raise TimeoutError('R07a pause hold reached active deadline')
            resume_ack = await io.control_world(world_name='b2_training_arena', pause=False,
                timeout_s=min(1.0, max(0.0, (io.deadline_ns-io.now())/1e9)))
            resume_state = await io.paused_state(False, min(1.0,
                max(0.0, (io.deadline_ns-io.now())/1e9)))
            io.expected_paused = False
            io.last_clock_advance_ns = io.now()
            await io.until(lambda: io.ros_now() if io.ros_now() > previous_ros else None,
                deadline_ns=min(io.deadline_ns, io.now()+1_000_000_000),
                phase='R07a simulation clock resumes after external pause',
                expected_native_fault_flags=1)
            inhibit_ack = await io.control.inhibit(
                deadline_ns=min(io.deadline_ns, io.now()+1_000_000_000))
            if not resume_ack.success or resume_state is not True:
                raise RuntimeError('R07a world resume was not acknowledged')
            io.emit('B23_R07A_VERIFIED', {'checked':checked,
                'world_pause_success':world_ack.success,'world_pause_state':pause_state,
                'world_resume_success':resume_ack.success,'world_resume_state':not resume_state,
                'native_status_sequence':state.status_sequence,
                'native_inhibit_request_cdr_hex':inhibit_ack.request_bytes.hex(),
                'native_inhibit_response_cdr_hex':inhibit_ack.response_bytes.hex(),
                'steady_ns':io.now()})
            outcome = {'case':'R07a','expected_unexpected_pause_fault':True,
                **checked,'inhibit_applied':True,'completed_ns':time.monotonic_ns()}
        elif packet['case'] == 'R07b':
            from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
            from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendControlError
            if (packet['fault_hooks'] != case_fault_hooks('R07b')
                    or io.contact_ack is None or io.contact_start_request_sequence is None):
                raise RuntimeError('R07b packet/contact proof binding is incomplete')
            original = io.contact_ack
            before, after = await io.reset_world_time_only(timeout_s=
                min(1.0, max(0.0, (io.deadline_ns-io.now())/1e9)))
            replay_ack = await io.control.replay(original,
                deadline_ns=min(io.deadline_ns, io.now()+1_000_000_000))
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
        elif packet['case'] in ('R02a','R02b'):
            if packet['case'] == 'R02b':
                expected_env = case_environment(packet['case'], packet['fault_hooks'])
                if any(packet['environment'].get(key) != value for key, value in expected_env.items()):
                    raise RuntimeError('R02b admission order hook environment does not match packet')
            target = ResetTarget(**packet['reset_target'])
            await io.reset_episode(b1, seed=packet['episode_seeds'][0], target=target, paused_hold_s=.250)
            step_started_ns = time.monotonic_ns()
            transition = await io.policy_step(b1, (0.4, 0., 0.),
                align_admission_after_scan_boundary=packet['case'] == 'R02b')
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
                rejected = await io.until(lambda: r04d_stale_safety_rejection_after_delivery(
                    io.events, delivery_ns=delayed['delivery_ns'],
                    source_stamp_ns=scheduled['source_stamp_ns']),
                    deadline_ns=min(io.deadline_ns, io.now() + 2_000_000_000),
                    phase='R04d delivered stale lifecycle rejected by actual Safety')
                ingress_scheduled = next((facts for name, facts in io.events
                    if name == 'B23_R04_INGRESS_DELIVERY_SCHEDULED' and facts.get('case') == 'R04d'), None)
                ingress_delivered = next((facts for name, facts in io.events
                    if name == 'B23_R04_INGRESS_DELIVERY_COMPLETED' and facts.get('case') == 'R04d'), None)
                final_path = Path(packet['run_root'])/'final-events.jsonl'
                final_rows = _ledger_rows(packet['run_root'], 'final-events.jsonl') if final_path.exists() else []
                expected_lifecycle_identity = [int(fault_lifecycle.episode_generation),
                    int(fault_lifecycle.reset_epoch), int(fault_lifecycle.runtime_generation)]
                final_lifecycle_delivery = next((row.get('facts', {}) for row in final_rows
                    if row.get('event') == 'R04D_FINAL_LIFECYCLE_DELIVERY_COMPLETED'
                    and row.get('facts', {}).get('sequence') == fault_lifecycle.sequence
                    and row.get('facts', {}).get('identity') == expected_lifecycle_identity), None)
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
                        or rejected['steady_ns'] < delayed['delivery_ns']
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
                try:
                    transition = await io.policy_step(b1, (0.25, 0., 0.),
                        measurement_fault_case=packet['case'])
                except (TimeoutError, RuntimeError) as error:
                    if packet['case'] not in ('R04a', 'R04b'):
                        raise
                    if packet['case'] == 'R04a':
                        state = io._r04_fault_state
                        if state['triggered'] != 1 or state['delivered'] != 1:
                            raise RuntimeError('R04a delayed callback did not finish exactly once') from error
                        await await_r04a_production_rejection(io,
                            deadline_ns=min(io.deadline_ns, io.now() + 1_000_000_000))
                        checked = verify_r04_stale_delivery(io, case='R04a')
                        if not isinstance(error, TimeoutError):
                            raise RuntimeError('R04a expected the blocked POLICY step to reach its deadline') from error
                        zero_baseline = verify_r04a_zero_baseline(io, checked=checked)
                        if any(getattr(item, 'source', None) == 1 for item in io.ingress.receipts):
                            raise RuntimeError('R04a POLICY receipt reached native ingress after delay fault')
                        aborted = b1.lifecycle.abort_step('R04a_delayed_noisy_input_rejected')
                        outcome = {'case':'R04a','resets_confirmed':1,'policy_steps_committed':0,
                            'expected_rejection':True, **checked,
                            'safe_stop_applied':True, 'safe_stop_baseline':zero_baseline,
                            'b1_abort_status':str(aborted.status),
                            'exception':repr(error),'completed_ns':time.monotonic_ns()}
                    else:
                        if isinstance(error, RuntimeError) and not str(error).startswith('native fault flags='):
                            raise
                        state = io._r04_fault_state
                        rejection = next((facts for name, facts in io.events
                            if name == 'SAFETY_REJECTED'
                            and 'NOISY_OR_ADMISSION_NOT_VALID' in facts.get('reasons', ())), None)
                        if state['triggered'] == 0 or rejection is None:
                            raise RuntimeError('R04b timeout lacked dropped noisy inputs and Safety rejection') from error
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
                        issued_path = Path(packet['run_root'])/'policy_adapter_issued.jsonl'
                        if issued_path.exists() and any(row.strip() for row in issued_path.read_text().splitlines()):
                            raise RuntimeError('R04b issued POLICY despite missing noisy admission')
                        outcome = {'case':'R04b','resets_confirmed':1,'policy_steps_committed':0,
                            'expected_rejection':True,'safety_reason':'NOISY_OR_ADMISSION_NOT_VALID',
                            'dropped_policy_inputs':state['triggered'],
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
                        state = io._r04_fault_state
                        await io.until(lambda: state if state['delivered'] == 1 else None,
                            deadline_ns=min(io.deadline_ns, io.now() + 1_000_000_000),
                            phase='R04c bounded delayed scan delivery')
                        delayed = next((facts for name, facts in reversed(io.events)
                            if name == 'B23_R04_DELIVERY_DELAYED_CALLBACK'
                            and facts.get('case') == 'R04c'), None)
                        if state['triggered'] != 1 or state['delivered'] != 1 or delayed is None:
                            raise RuntimeError('R04c delayed scan callback did not complete exactly once')
                        blocked_step = transition.transition_identity.step_index + 1
                        blocked_step_timeout = None
                        try:
                            await io.policy_step(b1, (0.25, 0., 0.))
                        except (TimeoutError, RuntimeError) as error:
                            blocked_step_timeout = repr(error)
                            checked = verify_r04_stale_delivery(io, case='R04c')
                            blocked = verify_r04c_next_step_blocked(io,
                                step_index=blocked_step,
                                delayed_delivery_ns=delayed['delivery_ns'])
                            disposition = abort_r04a_pending_step_if_active(
                                b1.lifecycle, expected_step_index=blocked_step,
                                reason='R04c_stale_scan_blocked_next_slot')
                        else:
                            raise RuntimeError('R04c stale scan allowed the next POLICY slot')
                        outcome = {'case':'R04c','resets_confirmed':1,
                            'policy_steps_committed':1, **checked, **blocked,
                            'safe_stop_applied':True,
                            'b1_step_disposition':disposition,
                            'blocked_step_timeout':blocked_step_timeout,
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
    expected_seeds = list(range(2026102900, 2026102930)) if packet.get('case') == 'R08' else [2026102900,2026102901]
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
            or scenario_id != 'B2_SOAK_V1' or document['map_identity']['training_binding']['binding_status'] != 'BOUND'):
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
            for process in supervisor.owned:
                if process.process.returncode is not None and process.name not in ('worker',):
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
    document, config_hash, asset_hash, _ = load_bound_config(rl/'config/v3/resolved/sim_train_local_training_soak.resolved.json')
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
    plan = build_launch_plan(gui='false', resolved_config=rl/'config/v3/resolved/sim_train_local_training_soak.resolved.json',
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
    environment = {k: os.environ[k] for k in environment_keys if k in os.environ}
    environment.update(ROS_DOMAIN_ID='84', ROS_HOME=str(root/'ros-home'), ROS_LOG_DIR=str(root/'ros-log'),
        PYTHONPYCACHEPREFIX=str(root/'pycache'))
    values = launch_plan_record(plan)
    fault_hooks = case_fault_hooks(args.case, args.fault_hook)
    environment.update(case_environment(args.case, fault_hooks))
    active_s = 900 if args.case == 'R08' else 120
    cleanup_s = 60
    episode_seeds = list(range(2026102900, 2026102930)) if args.case == 'R08' else [2026102900,2026102901]
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
        'asset_manifest':str(desc/'manifests/b2/asset_manifest.json'), 'scenario':str(rl/'scenarios/local_training/B2_SOAK_V1.json'),
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
