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
