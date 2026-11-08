"""Regression ingress/producer thật với generated interfaces và I/O fakes."""
from dataclasses import fields
import copy
import json
import math
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from builtin_interfaces.msg import Time
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from rclpy.serialization import serialize_message
from mecanum_nav_rl_interfaces.msg import SafetyLifecycleState, SimulationContactState, FinalIssuedCommandReceipt
from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
from mecanum_nav_rl.core.lifecycle_types import policy_transition_identity, EpisodeLifecycleIdentity
from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendControlAck, BackendSessionIdentity, lifecycle_request_fields
from mecanum_nav_rl.runtime_simulation.local_training_ingress import LocalTrainingIngress, ReceivedNoisySample


def stamp(ns):
    return Time(sec=ns // 10**9, nanosec=ns % 10**9)


@pytest.fixture
def source():
    root = Path(__file__).resolve().parents[4]
    profile = json.loads((root / 'ros2_ws/src/mecanum_nav_rl/config/v3/resolved/sim_train_local_training_soak.resolved.json').read_text())['training']['local_training']
    clock = NS(ros=1_000_000_000, steady=2_000_000_000)
    sent, events = [], []
    identity = BackendSessionIdentity('b23-test', 'a' * 64, 'b' * 64, 11, 22)
    ingress = LocalTrainingIngress(identity, profile, final_publisher_id=55, policy_source_id=33,
        safe_stop_source_id=44, safety_publish=sent.append, emit=lambda event, data: events.append((event, data)),
        now_ns=lambda: clock.steady, now_ros_ns=lambda: clock.ros)
    life = SafetyLifecycleState()
    life.header.frame_id, life.header.stamp = 'b2_training_arena', stamp(900_000_000)
    life.barrier_stamp = stamp(900_000_000)
    life.sequence, life.episode_generation, life.reset_epoch, life.runtime_generation = 3, 1, 2, 3
    life.primary_state, life.barrier_state, life.motion_permitted = life.PRIMARY_ACTIVE, life.BARRIER_READY, True
    ingress.bind_lifecycle(life); ingress.reset_noise(2026102900)

    def gt(ns=None):
        value = Odometry()
        value.header.frame_id, value.child_frame_id = 'world', 'base_link'
        value.header.stamp = stamp(clock.ros if ns is None else ns)
        value.pose.pose.orientation.w = 1.
        value.pose.pose.position.x, value.pose.pose.position.z = 0.2, 0.1
        value.twist.twist.linear.x, value.twist.twist.linear.y = 0.02, -0.03
        return value

    def backend(ns=None, iteration=1, sequence=1):
        value = SimulationContactState()
        value.header.frame_id, value.header.stamp = 'b2_training_arena', stamp(clock.ros if ns is None else ns)
        value.schema_version = value.SCHEMA_VERSION
        value.session_id, value.config_hash, value.backend_instance_id = 'b23-test', 'a' * 64, 22
        value.episode_generation, value.reset_epoch, value.runtime_generation = 1, 2, 3
        value.status_sequence, value.physics_iteration = sequence, iteration
        value.coverage_complete, value.contact_source_healthy = True, True
        value.required_collision_mask = value.observed_collision_mask = 3
        return value

    def ack(operation, request_sequence=1):
        req, res = Control.Request(), Control.Response()
        req.schema_version, res.schema_version = req.SCHEMA_VERSION, res.RESPONSE_SCHEMA_VERSION
        req.operation, req.request_sequence = operation, request_sequence
        req.session_id, req.config_hash, req.asset_manifest_sha256 = 'b23-test', 'a' * 64, 'b' * 64
        req.coordinator_ingress_instance_id, req.expected_backend_instance_id = 11, 22
        res.request_sequence, res.backend_instance_id = request_sequence, 22
        res.result, res.reason_code = res.RESULT_APPLIED, res.REASON_NONE
        req.expected_binding_revision, res.binding_revision, res.applied_binding_revision = 4, 5, 5
        res.applied_physics_iteration, res.applied_sim_stamp = 1, stamp(clock.ros - 10_000_000)
        if operation == req.OP_CONFIRM_OBSERVATION0:
            for key, value in lifecycle_request_fields(life).items(): setattr(req, key, value)
            req.selected_zero_final_publisher_instance_id = req.adjacent_boundary_final_publisher_instance_id = 55
            req.selected_zero_final_publish_sequence, req.adjacent_boundary_final_publish_sequence = 1, 2
            req.observation0_cutoff = stamp(950_000_000)
        else:
            req.pending_step_index = req.pending_source_sequence = 1
            req.pending_transition_id = policy_transition_identity(identity=EpisodeLifecycleIdentity(1, 2, 3),
                session_id='b23-test', source_instance_id=33, source_sequence=1, step_index=1).transition_id
            req.action_barrier_stamp = stamp(990_000_000)
            res.pending_admission_token = [7] * 16
        return BackendControlAck(serialize_message(req), serialize_message(res), clock.steady)

    def receipt(sequence=1):
        value = FinalIssuedCommandReceipt()
        value.header.frame_id, value.header.stamp = 'base_link', stamp(clock.ros)
        value.source, value.source_instance_id, value.sequence = value.SOURCE_SAFE_STOP, 44, sequence
        value.final_publisher_instance_id, value.final_publish_sequence = 55, sequence
        value.episode_generation, value.reset_epoch, value.runtime_generation = 1, 2, 3
        return value

    def advance(ns=10_000_000): clock.ros += ns; clock.steady += ns
    return NS(ingress=ingress, clock=clock, sent=sent, events=events, life=life,
              gt=gt, backend=backend, ack=ack, receipt=receipt, advance=advance)


def test_noisy_output_has_no_ground_truth_reference_and_keeps_source_stamp(source):
    f = source; result = f.ingress.on_ground_truth(f.gt())
    assert isinstance(result, ReceivedNoisySample)
    assert set(field.name for field in fields(result)) == {'output', 'received_steady_ns', 'lifecycle'}
    assert result.output.snapshot.timestamp_ns == f.clock.ros
    noisy = result.output.snapshot.measurement
    assert noisy is not None and noisy.vy_mps != -0.03  # Profile N0 thật có noise.
    assert not hasattr(noisy, 'ground_truth') and not f.sent
    assert f.ingress.on_ground_truth(f.gt()) is None
    assert len(f.ingress.noisy_samples) == 1
    modified = f.gt(); modified.pose.pose.position.x = 4.
    with pytest.raises(ValueError, match='same stamp changed bytes'):
        f.ingress.on_ground_truth(modified)


def test_pending_ack_requires_new_sample_before_build_and_publish(source):
    f = source; ingress = f.ingress
    ingress.on_ground_truth(f.gt())
    ingress.confirm_observation0(f.ack(Control.Request.OP_CONFIRM_OBSERVATION0))
    pending = f.ack(Control.Request.OP_BIND_PENDING_STEP, 2)
    ingress.arm_pending(pending)
    old = next(iter(ingress.noisy_samples.values()))
    ingress._publish_safety(old)
    assert not f.sent
    f.advance(); sample = ingress.on_ground_truth(f.gt())
    assert len(f.sent) == 1
    value = f.sent[0]
    assert value.schema_version == 2 and bytes(value.admission_token) == bytes([7] * 16)
    assert value.header.stamp == stamp(sample.output.snapshot.timestamp_ns)
    assert list(value.measured_twist) == [sample.output.snapshot.measurement.vx_mps,
        sample.output.snapshot.measurement.vy_mps, sample.output.snapshot.measurement.wz_radps]
    events = [event for event, _ in f.events]
    assert events.index('SAMPLE_RECEIVED', events.index('ADMISSION_SAMPLE_REJECTED')) < events.index('ADMISSION_BUILT') < events.index('ADMISSION_PUBLISHED')
    built = next(data for event, data in f.events if event == 'ADMISSION_BUILT')
    assert built['sample_received_ns'] > built['ack_observed_ns']
    assert value.observation0_final_publish_sequence == 1
    assert not hasattr(value, 'pose')


def test_pending_requires_observation0_and_real_b1_uuid(source):
    f = source
    with pytest.raises(ValueError, match='observation0/token'):
        f.ingress.arm_pending(f.ack(Control.Request.OP_BIND_PENDING_STEP))


@pytest.mark.parametrize('zero_only', [False, True])
def test_closing_input_needs_no_admission_token_or_observation0(source, zero_only):
    f = source; f.ingress.inhibit(zero_only=zero_only)
    f.ingress.on_ground_truth(f.gt())
    assert len(f.sent) == 1
    value = f.sent[0]
    assert not any(value.admission_token)
    assert value.observation0_final_publish_sequence == 0
    assert value.admission_state == (value.ADMISSION_ZERO_ONLY if zero_only else value.ADMISSION_INHIBITED)
    assert value.header.stamp == stamp(f.clock.ros)


@pytest.mark.parametrize('order', ['oracle_first', 'status_first'])
def test_physics_pair_uses_exact_source_stamp_and_real_status_iteration(source, order):
    f = source
    methods = ((f.ingress.on_ground_truth, f.gt()), (f.ingress.on_backend, f.backend()))
    for method, value in methods if order == 'oracle_first' else reversed(methods): method(value)
    pair = f.ingress.physics_pairs[-1]
    assert pair.iteration == 1 and pair.stamp_ns == f.clock.ros
    assert pair.oracle_bytes == serialize_message(f.gt())
    assert pair.backend_bytes == serialize_message(f.backend())
    assert pair.oracle_received_steady_ns == f.clock.steady
    f.advance(); f.ingress.on_backend(f.backend(iteration=3, sequence=2))
    with pytest.raises(ValueError, match='iteration missing or gap'):
        f.ingress.on_ground_truth(f.gt())


def test_status_cannot_supply_or_invent_oracle_iteration(source):
    f = source
    f.ingress.on_ground_truth(f.gt())
    f.ingress.on_backend(f.backend(f.clock.ros + 1))
    assert not f.ingress.physics_pairs


def test_receipt_replay_keeps_original_bytes_receive_time_and_sequence(source):
    f = source; one = f.ingress.on_receipt(f.receipt())
    f.advance()
    # Phát lại chính bytes cũ, không tạo receipt mới bằng thời gian hiện tại.
    original = f.receipt(); original.header.stamp = stamp(one.publish_stamp_ns)
    assert f.ingress.on_receipt(original) is None
    assert len(f.ingress.receipts) == 1 and f.ingress.receipts[0] is one
    changed = copy.deepcopy(original); changed.final_command.linear.x = 0.1
    with pytest.raises(ValueError, match='same publication key changed bytes'):
        f.ingress.on_receipt(changed)


def test_receipt_gap_never_creates_b1_view(source):
    f = source
    with pytest.raises(ValueError, match='gap/context'):
        f.ingress.on_receipt(f.receipt(2))
    assert not f.ingress.receipts


def test_scan_replay_does_not_refresh_receive_age(source):
    f = source; scan = LaserScan()
    scan.header.frame_id, scan.header.stamp = 'lidar_frame', stamp(f.clock.ros)
    scan.range_min, scan.range_max = 0.1, 8.
    scan.angle_min, scan.angle_max = -math.pi, math.pi
    scan.angle_increment = 2 * math.pi / 499
    scan.ranges = [float('inf')] * 500
    f.ingress.on_scan(scan); first = f.ingress.scans[f.clock.ros]
    f.advance(); f.ingress.on_scan(scan)
    assert f.ingress.scans[first.stamp_ns] is first


def test_context_change_revokes_pending_and_flushes_sensor_pair_buffers(source):
    f = source
    f.ingress.on_ground_truth(f.gt())
    f.ingress.confirm_observation0(f.ack(Control.Request.OP_CONFIRM_OBSERVATION0))
    f.ingress.arm_pending(f.ack(Control.Request.OP_BIND_PENDING_STEP, 2))
    f.life.sequence += 1; f.life.runtime_generation += 1
    f.life.barrier_stamp = stamp(f.clock.ros)
    f.ingress.bind_lifecycle(f.life)
    assert f.ingress.pending_ack is f.ingress.observation0_ack is None
    assert not f.ingress.noisy_samples and not f.ingress.scans and not f.ingress.physics_pairs
    assert not f.ingress.admission_publication_enabled


def b1_runtime_chain(f):
    """Dữ liệu biên I/O xác định; gọi ingress, assembler và transaction B1 thật."""
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import LocalTrainingB1Adapter
    from mecanum_nav_rl.tasks.scenario_artifact import ScenarioArtifactLoader
    from mecanum_nav_rl_interfaces.msg import CommandEnvelope, SafetyState
    root = Path(__file__).resolve().parents[4]
    asset = json.loads((root/'artifacts/simulation/roadmap_b_b2/asset_manifest.json').read_text())
    artifact = ScenarioArtifactLoader(expected_gazebo_world_name=asset['world_id'],
        expected_world_file_sha256=asset['world_file_sha256']).load(
            (root/'ros2_ws/src/mecanum_nav_rl/scenarios/local_training/B2_SOAK_V1.json').read_text())
    transform = NS(transform=NS(translation=NS(x=-0.031765, y=0., z=0.14),
                                    rotation=NS(x=0., y=0., z=0., w=1.)))
    b1 = LocalTrainingB1Adapter(f.ingress, artifact, asset, scan_transform=lambda: transform,
                               emit=lambda name, data: f.events.append((name, data)))
    b1.begin_reset()

    def scan():
        msg = LaserScan()
        msg.header.frame_id, msg.header.stamp = 'lidar_frame', stamp(f.clock.ros)
        msg.range_min, msg.range_max = 0.1, 8.
        msg.angle_min, msg.angle_max = -math.pi, math.pi
        msg.angle_increment = (msg.angle_max - msg.angle_min) / 499
        msg.ranges = [float('inf')] * 500
        return msg

    def physics(iteration, applied=0):
        f.ingress.on_ground_truth(f.gt())
        msg = f.backend(iteration=iteration, sequence=iteration)
        if applied:
            msg.applied_receipt_valid = True
            msg.applied_final_publisher_instance_id, msg.applied_final_publish_sequence = 55, applied
            msg.applied_physics_iteration, msg.applied_sim_stamp = iteration, stamp(f.clock.ros)
        f.ingress.on_backend(msg)
        return msg

    f.ingress.on_receipt(f.receipt(1))
    f.advance(); physics(1, 1); f.ingress.on_scan(scan())
    reset_cutoff = f.clock.ros
    f.advance(); physics(2)
    f.ingress.on_receipt(f.receipt(2))
    observation0, selected_zero = b1.commit_observation0(reset_cutoff)
    raw = f.ack(Control.Request.OP_CONFIRM_OBSERVATION0)
    req = raw.request; req.observation0_cutoff = stamp(reset_cutoff)
    req.selected_zero_final_publish_sequence = selected_zero.receipt.final_publish_sequence
    req.adjacent_boundary_final_publish_sequence = selected_zero.adjacent_receipt.final_publish_sequence
    confirmed = BackendControlAck(serialize_message(req), raw.response_bytes, raw.observed_steady_ns)
    f.ingress.confirm_observation0(confirmed)
    token = b1.begin_step()
    f.advance(); physics(3)
    pending = f.ack(Control.Request.OP_BIND_PENDING_STEP, 2)
    req = pending.request; req.action_barrier_stamp = stamp(f.clock.ros)
    pending = BackendControlAck(serialize_message(req), pending.response_bytes, pending.observed_steady_ns)
    f.ingress.arm_pending(pending)
    envelope = CommandEnvelope()
    envelope.header.frame_id, envelope.header.stamp = 'base_link', stamp(f.clock.ros)
    envelope.source, envelope.source_instance_id, envelope.sequence = envelope.SOURCE_POLICY, 33, 1
    envelope.episode_generation, envelope.reset_epoch, envelope.runtime_generation = 1, 2, 3
    envelope.twist.linear.x, envelope.twist.linear.y, envelope.twist.angular.z = 0.1, -0.1, 0.2
    issued = []
    issued.append(copy.deepcopy(envelope))  # Biên publisher giả trả về thành công.
    b1.record_issuance(issued[-1], action_barrier_ns=f.clock.ros)
    f.advance(); physics(4, 3)
    receipt = f.receipt(3)
    receipt.source, receipt.source_instance_id, receipt.sequence, receipt.step_index = receipt.SOURCE_POLICY, 33, 1, 1
    receipt.transition_id = token.transition_id
    receipt.final_command.linear.x, receipt.final_command.linear.y, receipt.final_command.angular.z = 0.05, -0.04, 0.08
    f.ingress.on_receipt(receipt)
    for iteration in range(5, 14):
        f.advance(); physics(iteration)
    cutoff = f.clock.ros
    f.ingress.on_scan(scan())
    f.advance()
    adjacent = copy.deepcopy(receipt)
    adjacent.header.stamp, adjacent.final_publish_sequence = stamp(f.clock.ros), 4
    f.ingress.on_receipt(adjacent)
    state = SafetyState()
    state.header.frame_id, state.header.stamp = 'base_link', stamp(f.clock.ros)
    state.state, state.reset_epoch, state.runtime_generation = state.STATE_NORMAL, 2, 3
    state.command_valid = state.motion_permitted = True
    state.active_command_source = state.COMMAND_SOURCE_POLICY
    f.ingress.bind_safety_publisher_gid(bytes(range(24)))
    f.ingress.register_safety_publication(state, source_instance_id=44)
    f.ingress.on_safety_state(state)
    return NS(b1=b1, cutoff=cutoff, observation0=observation0, zero_selection=selected_zero,
              token=token, envelope=envelope, transform=transform, state=state)


def test_real_ingress_b1_reset_then_policy_commit_retains_81d_and_true_dt(source):
    import numpy as np
    f = source; chain = b1_runtime_chain(f)
    result = chain.b1.commit_step(chain.cutoff)
    assert chain.observation0.shape == result.observation.shape == (81,)
    assert chain.observation0.dtype == result.observation.dtype == np.float32
    assert not result.observation.flags.writeable
    assert result.transition_identity == chain.token
    assert result.lifecycle_result.snapshot.step_index == 1
    assert not result.termination.terminated and not result.termination.truncated
    assert list(result.observation[-3:]) == list(np.asarray([0.2, -0.2, 0.1], dtype=np.float32))
    assert result.command_history == tuple(float(v) for v in result.observation[-3:])
    assert result.reward.terms.time == pytest.approx(-0.1 * 0.12)
    names = [name for name, _ in f.events]
    assert names.count('policy_adapter_issued') == names.count('policy_backend_applied') == names.count('b1_transition_committed') == 1
    with pytest.raises(ValueError, match='no actual issuance'):
        chain.b1.commit_step(chain.cutoff)
    assert [name for name, _ in f.events].count('b1_transition_committed') == 1


@pytest.mark.parametrize('missing', ['scan', 'noisy', 'physics', 'safety'])
def test_b1_missing_real_input_never_creates_transition_or_reward(source, missing):
    f = source; chain = b1_runtime_chain(f)
    if missing == 'scan': f.ingress.scans.clear()
    if missing == 'noisy': f.ingress.noisy_samples.clear()
    if missing == 'physics': f.ingress.physics_pairs.clear()
    if missing == 'safety': f.ingress.safety_state = None
    with pytest.raises(ValueError): chain.b1.commit_step(chain.cutoff)
    assert not chain.b1.committer.committed
    assert 'b1_transition_committed' not in [name for name, _ in f.events]


def test_b1_native_application_is_required_separately_from_publication(source):
    from dataclasses import replace
    from rclpy.serialization import deserialize_message
    from collections import deque
    f = source; chain = b1_runtime_chain(f)
    changed = []
    for pair in f.ingress.physics_pairs:
        status = deserialize_message(pair.backend_bytes, SimulationContactState)
        if status.applied_final_publish_sequence == 3:
            status.applied_receipt_valid = False
            status.applied_final_publisher_instance_id = status.applied_final_publish_sequence = 0
            status.applied_physics_iteration = 0; status.applied_sim_stamp = Time()
        changed.append(replace(pair, backend_bytes=serialize_message(status)))
    f.ingress.physics_pairs = deque(changed, maxlen=64)
    with pytest.raises(ValueError, match='native application'):
        chain.b1.commit_step(chain.cutoff)
    assert not chain.b1.committer.committed


def test_b1_changed_transform_or_backend_fault_never_uses_fallback(source):
    f = source; chain = b1_runtime_chain(f)
    chain.transform.transform.translation.x = 0.5
    with pytest.raises(ValueError, match='transform differs'):
        chain.b1.commit_step(chain.cutoff)
    assert not chain.b1.committer.committed


def test_safety_endpoint_change_cannot_supply_health_for_b1(source):
    from mecanum_nav_rl_interfaces.msg import SafetyState
    f = source
    f.ingress.bind_safety_publisher_gid(bytes(range(24)))
    with pytest.raises(ValueError, match='matching actual producer'):
        f.ingress.on_safety_state(SafetyState())
    assert f.ingress.safety_state is None


def test_application_ledger_joins_delayed_receipt_once_with_original_receive_time(source):
    f = source; chain = b1_runtime_chain(f)
    records = [data for name, data in f.events if name == 'policy_backend_applied']
    assert len(records) == 1
    assert records[0]['publish_sequence'] == 3
    assert records[0]['transition_id'] == chain.token.transition_id
    assert records[0]['iteration'] == 4
    assert records[0]['status_received_ns'] < f.clock.steady
    assert not f.ingress._unresolved_applications
    chain.b1.commit_step(chain.cutoff)
    assert len([name for name, _ in f.events if name == 'policy_backend_applied']) == 1


def test_reapplication_of_same_final_key_is_not_a_second_application_fact(source):
    f = source; b1_runtime_chain(f)
    state = f.backend(iteration=14, sequence=14)
    state.applied_receipt_valid = True
    state.applied_final_publisher_instance_id, state.applied_final_publish_sequence = 55, 3
    state.applied_physics_iteration, state.applied_sim_stamp = 14, stamp(f.clock.ros)
    with pytest.raises(ValueError, match='applied more than once'):
        f.ingress.on_backend(state)
    assert len([name for name, _ in f.events if name == 'policy_backend_applied']) == 1


def test_receipt_clock_rollback_cannot_be_hidden_by_phase_window(source):
    f = source
    f.ingress.on_receipt(f.receipt(1))
    old = f.receipt(2); old.header.stamp = stamp(f.clock.ros - 1)
    with pytest.raises(ValueError, match='timestamp rollback'):
        f.ingress.on_receipt(old)
    assert len(f.ingress.receipts) == 1


def test_safety_receiver_uses_jazzy_message_only_and_keeps_replay_receive_age(source):
    from mecanum_nav_rl_interfaces.msg import SafetyState
    f = source
    f.ingress.bind_safety_publisher_gid(bytes(range(24)))
    state = SafetyState(); state.header.frame_id = 'base_link'; state.header.stamp = stamp(f.clock.ros)
    f.ingress.register_safety_publication(state, source_instance_id=44)
    f.ingress.on_safety_state(state)
    received = f.ingress.safety_received_ns
    f.advance(); f.ingress.on_safety_state(state)
    assert f.ingress.safety_received_ns == received
    changed = copy.deepcopy(state); changed.motion_permitted = True
    with pytest.raises(ValueError, match='matching actual producer'):
        f.ingress.on_safety_state(changed)


def test_paused_pose_bytes_require_native_reset_ack_and_never_create_noisy_tick(source):
    f = source
    f.life.sequence += 1
    f.life.barrier_state, f.life.motion_permitted = f.life.BARRIER_NON_READY, False
    f.ingress.bind_lifecycle(f.life)
    f.ingress.on_ground_truth(f.gt())
    state = f.backend(); state.paused, state.actuator_inhibited = True, True
    f.ingress.on_backend(state)
    req, res = Control.Request(), Control.Response()
    req.schema_version = res.schema_version = 2
    req.operation, req.request_sequence, res.request_sequence = req.OP_PREPARE_RESET_PAUSE, 9, 9
    req.session_id, req.config_hash, req.asset_manifest_sha256 = 'b23-test', 'a'*64, 'b'*64
    req.coordinator_ingress_instance_id, req.expected_backend_instance_id = 11, 22
    req.final_publisher_instance_id, req.pause_fence_final_publish_sequence = 55, 20
    req.pause_enter_budget_ms = 100
    for key, value in lifecycle_request_fields(f.life).items(): setattr(req,key,value)
    req.expected_binding_revision = 4
    res.backend_instance_id, res.binding_revision, res.applied_binding_revision = 22, 5, 5
    res.result, res.applied_physics_iteration = res.RESULT_APPLIED, 10
    res.applied_sim_stamp = stamp(f.clock.ros)
    ack = BackendControlAck(serialize_message(req), serialize_message(res), f.clock.steady)
    f.ingress.begin_pose_mutation(ack)
    before = len(f.ingress.noisy_samples)
    moved = f.gt(); moved.pose.pose.position.x = 0.
    assert f.ingress.on_ground_truth(moved) is None
    assert len(f.ingress.noisy_samples) == before
    assert next(data for name,data in f.events if name == 'RESET_PAUSED_ORACLE')['message_cdr_hex'] == serialize_message(moved).hex()
    f.advance(); f.ingress.on_ground_truth(f.gt())
    assert f.ingress._pose_mutation is None
    changed = f.gt(); changed.pose.pose.position.x = 5.
    with pytest.raises(ValueError, match='same stamp changed bytes'):
        f.ingress.on_ground_truth(changed)
