"""Facts lifecycle thật của LOCAL_TRAINING và hành vi mode cũ."""
from mecanum_nav_rl.runtime_safety.safety_contract import (
    SafetyLifecycleCore, BarrierState,
)


def test_local_training_heartbeat_does_not_rebind_event_barrier():
    core = SafetyLifecycleCore(fixed_barrier=True)
    core.configure(100); core.activate(200)
    ready = core.rearm(300)
    for now in (400, 500, 1_000):
        heartbeat = core.refresh(now)
        assert heartbeat.barrier_ros_time_ns == ready.barrier_ros_time_ns == 300
        assert heartbeat.sequence == ready.sequence
        assert heartbeat.motion_permitted
    reset = core.begin_reset(1_100)
    assert reset.barrier_state is BarrierState.NON_READY and not reset.motion_permitted
    assert core.refresh(1_200).barrier_ros_time_ns == 1_100
    l2 = core.rearm(1_300)
    assert l2.runtime_generation == ready.runtime_generation + 1
    assert l2.episode_generation == ready.episode_generation + 1
    assert core.refresh(1_400).barrier_ros_time_ns == 1_300


def test_legacy_heartbeat_and_clock_regression_stay_fail_closed():
    legacy = SafetyLifecycleCore()
    legacy.configure(100); legacy.activate(200); legacy.rearm(300)
    assert legacy.refresh(400).barrier_ros_time_ns == 400
    assert legacy.refresh(399).barrier_state is BarrierState.FAULT
    fixed = SafetyLifecycleCore(fixed_barrier=True)
    fixed.configure(100); fixed.activate(200); fixed.rearm(300)
    fixed.refresh(400)
    assert fixed.refresh(399).barrier_state is BarrierState.FAULT

import copy
import json
from pathlib import Path
from types import SimpleNamespace as NS
import pytest


@pytest.fixture
def local_adapter():
    """Message ROS generated qua biên I/O giả, không tạo ROS context."""
    from builtin_interfaces.msg import Time
    from sensor_msgs.msg import LaserScan
    from mecanum_nav_rl_interfaces.msg import (
        SafetyLifecycleState, LocalTrainingSafetyInput, SimulationContactState, CommandEnvelope,
    )
    from mecanum_nav_rl.runtime_safety.safety_supervisor_node import LocalTrainingSafetyAdapter
    root = Path(__file__).resolve().parents[4]
    resolved = json.loads((root / 'ros2_ws/src/mecanum_nav_rl/config/v3/resolved/sim_train_local_training_soak.resolved.json').read_text())
    asset = json.loads((root / 'artifacts/simulation/roadmap_b_b2/asset_manifest.json').read_text())
    context = dict(session_id='b23-test', config_hash='a' * 64, ingress_instance_id=11,
                   backend_instance_id=22, policy_source_instance_id=33,
                   safe_stop_source_instance_id=44, profile=resolved['training']['local_training'],
                   sensor=asset['sensor'], sim_estop_release_authorized=True)
    clock = NS(ros=1_000_000_000, steady=2_000_000_000)
    def stamp(ns): return Time(sec=ns // 10**9, nanosec=ns % 10**9)
    published, state, evidence = [], [], []
    translation = NS(x=-0.031765, y=0., z=0.14)
    transform = NS(transform=NS(translation=translation, rotation=NS(x=0., y=0., z=0., w=1.)))
    node = NS(get_clock=lambda: NS(now=lambda: NS(nanoseconds=clock.ros, to_msg=lambda: stamp(clock.ros))),
              _tf_buffer=NS(lookup_transform=lambda *args: transform),
              _accepted_pub=NS(publish=lambda m: published.append(copy.deepcopy(m))),
              _state_pub=NS(publish=lambda m: state.append(copy.deepcopy(m))))
    adapter = LocalTrainingSafetyAdapter(node, context, now_steady_ns=lambda: clock.steady,
                                        emit=lambda event, data: evidence.append((event, data)))
    life = SafetyLifecycleState()
    life.header.frame_id, life.header.stamp = 'b2_training_arena', stamp(clock.ros)
    life.barrier_stamp = stamp(900_000_000)
    life.episode_generation, life.reset_epoch, life.runtime_generation = 1, 2, 3
    life.sequence, life.primary_state, life.barrier_state, life.motion_permitted = 3, life.PRIMARY_ACTIVE, life.BARRIER_READY, True
    scan = LaserScan()
    scan.header.frame_id, scan.header.stamp = 'lidar_frame', stamp(clock.ros)
    scan.range_min, scan.range_max = 0.1, 8.
    scan.angle_min, scan.angle_max = -3.141592653589793, 3.141592653589793
    scan.angle_increment = (scan.angle_max - scan.angle_min) / 499
    scan.ranges = [float('inf')] * 500
    noisy = LocalTrainingSafetyInput()
    noisy.schema_version, noisy.session_id, noisy.config_hash = noisy.SCHEMA_VERSION, 'b23-test', 'a' * 64
    noisy.header.frame_id, noisy.header.stamp = 'base_link', stamp(clock.ros)
    noisy.ingress_instance_id, noisy.sample_sequence = 11, 1
    noisy.episode_generation, noisy.reset_epoch, noisy.runtime_generation = 1, 2, 3
    noisy.measured_twist = [0., 0., 0.]
    noisy.admission_state, noisy.admission_token = noisy.ADMISSION_POLICY_OPEN, [1] * 16
    noisy.observation0_cutoff, noisy.observation0_final_publisher_instance_id, noisy.observation0_final_publish_sequence = stamp(950_000_000), 55, 1
    backend = SimulationContactState()
    backend.schema_version, backend.session_id, backend.config_hash = backend.SCHEMA_VERSION, 'b23-test', 'a' * 64
    backend.header.frame_id, backend.header.stamp = 'b2_training_arena', stamp(clock.ros)
    backend.backend_instance_id, backend.status_sequence = 22, 1
    backend.episode_generation, backend.reset_epoch, backend.runtime_generation = 1, 2, 3
    backend.coverage_complete, backend.contact_source_healthy = True, True
    backend.required_collision_mask = backend.observed_collision_mask = 3
    candidate = CommandEnvelope()
    candidate.header.frame_id, candidate.header.stamp = 'base_link', stamp(clock.ros)
    candidate.source, candidate.source_instance_id, candidate.sequence = candidate.SOURCE_POLICY, 33, 1
    candidate.episode_generation, candidate.reset_epoch, candidate.runtime_generation = 1, 2, 3
    candidate.twist.linear.x, candidate.twist.linear.y, candidate.twist.angular.z = 0.1, -0.1, 0.2
    adapter.on_lifecycle(life); adapter.on_scan(scan); adapter.on_safety_input(noisy)
    adapter.on_backend(backend); adapter.on_command(candidate)
    adapter.set_policy_hold(False)
    def advance(ns=20_000_000): clock.ros += ns; clock.steady += ns
    return NS(adapter=adapter, clock=clock, life=life, scan=scan, noisy=noisy, backend=backend,
              candidate=candidate, published=published, state=state, evidence=evidence,
              advance=advance, translation=translation, node=node, stamp=stamp)


def test_local_safety_preserves_issuance_and_both_ttl_clocks(local_adapter):
    f = local_adapter; a = f.adapter
    assert a.tick().source == f.candidate.SOURCE_SAFE_STOP
    for _ in range(4):
        f.advance(); command = a.tick()
        assert command.source == command.SOURCE_POLICY, f.state[-1].intervention_reasons
        assert command.sequence == 1 and command.source_instance_id == 33
        assert command.header.stamp == f.candidate.header.stamp
        assert command.twist.linear.y < 0 and command.twist.angular.z > 0
    received = a.command_received
    a.on_command(f.candidate)
    assert a.command_received == received
    f.advance(130_000_000)
    assert a.tick().source == f.candidate.SOURCE_SAFE_STOP
    assert 'COMMAND_STALE_OR_FUTURE' in f.state[-1].intervention_reasons


@pytest.mark.parametrize('clock_name', ['ros', 'steady'])
def test_local_safety_single_clock_age_is_enforced(local_adapter, clock_name):
    f = local_adapter; f.adapter.tick(); f.advance()
    assert f.adapter.tick().source == f.candidate.SOURCE_POLICY
    setattr(f.clock, clock_name, getattr(f.clock, clock_name) + 210_000_000)
    assert f.adapter.tick().source == f.candidate.SOURCE_SAFE_STOP
    assert 'COMMAND_STALE_OR_FUTURE' in f.state[-1].intervention_reasons


@pytest.mark.parametrize('field,value,reason', [
    ('admission_token', [0] * 16, 'NOISY_OR_ADMISSION_NOT_VALID'),
    ('admission_state', 0, 'NOISY_OR_ADMISSION_NOT_VALID'),
    ('measured_twist', [float('nan'), 0., 0.], 'NOISY_OR_ADMISSION_NOT_VALID'),
    ('odometry_status', 2, 'NOISY_OR_ADMISSION_NOT_VALID'),
])
def test_local_safety_invalid_noisy_or_admission_selects_real_safe_stop(local_adapter, field, value, reason):
    f = local_adapter; f.adapter.tick(); f.advance()
    f.noisy.sample_sequence += 1
    setattr(f.noisy, field, value)
    f.adapter.on_safety_input(f.noisy)
    msg = f.adapter.tick()
    assert msg.source == msg.SOURCE_SAFE_STOP
    assert not any((msg.twist.linear.x, msg.twist.linear.y, msg.twist.angular.z))
    assert reason in f.state[-1].intervention_reasons


@pytest.mark.parametrize('field,value', [('contact_active', True), ('fault_flags', 1),
    ('coverage_complete', False), ('contact_source_healthy', False),
    ('observed_collision_mask', 1), ('paused', True), ('backend_instance_id', 99)])
def test_local_safety_backend_contact_and_identity_fail_closed(local_adapter, field, value):
    f = local_adapter; f.adapter.tick(); f.advance()
    setattr(f.backend, field, value); f.backend.status_sequence += 1
    f.adapter.on_backend(f.backend)
    assert f.adapter.tick().source == f.candidate.SOURCE_SAFE_STOP
    assert f.state[-1].intervention_reasons


def test_local_safety_uses_verified_base_link_scan_transform(local_adapter):
    f = local_adapter; f.adapter.tick(); f.advance()
    assert f.adapter.tick().source == f.candidate.SOURCE_POLICY
    # Điểm gần: khoảng cách phải được tính sau extrinsic x=-0.031765.
    f.scan.ranges[249] = 0.94
    f.adapter.on_scan(f.scan); f.advance()
    assert f.adapter.tick().source == f.candidate.SOURCE_SAFE_STOP
    assert 'STOPPING_ENVELOPE_OCCUPIED' in f.state[-1].intervention_reasons
    f.scan.ranges[249] = float('inf'); f.adapter.on_scan(f.scan)
    f.translation.x = 0.5; f.advance()
    assert f.adapter.tick().source == f.candidate.SOURCE_SAFE_STOP
    assert 'SCAN_EXTRINSIC_UNVERIFIED' in f.state[-1].intervention_reasons


def test_local_safety_same_key_conflict_and_barrier_invalidate_candidate(local_adapter):
    f = local_adapter; f.adapter.tick(); f.advance()
    f.candidate.twist.linear.x = 0.2
    f.adapter.on_command(f.candidate)
    assert f.adapter.tick().source == f.candidate.SOURCE_SAFE_STOP
    assert 'POLICY_SAME_KEY_CONFLICT' in f.state[-1].intervention_reasons
    f.life.sequence += 1; f.life.runtime_generation += 1
    f.life.barrier_stamp = f.stamp(f.clock.ros)
    f.adapter.on_lifecycle(f.life)
    assert f.adapter.command is None and f.adapter.noisy is None
    assert f.adapter.tick().source == f.candidate.SOURCE_SAFE_STOP


def test_local_safety_stream_fence_does_not_emit_or_increment(local_adapter):
    f = local_adapter; a = f.adapter
    a.tick(); before = a.safe_stop_sequence
    a.set_stream_enabled(False)
    for _ in range(10):
        f.advance(); assert a.tick() is None
    assert len(f.published) == 1 and a.safe_stop_sequence == before
    a.set_stream_enabled(True)
    assert a.tick().source == f.candidate.SOURCE_SAFE_STOP
    assert a.safe_stop_sequence == before + 1


def test_local_safety_node_wires_only_real_local_sources_without_nav2_flags(tmp_path):
    """Constructor production dùng Node/TF giả; không khởi tạo graph ROS."""
    import os
    import subprocess
    import sys
    script = r'''
import json
from pathlib import Path
from types import SimpleNamespace as NS
import rclpy.node
class Node:
    def __init__(self, name, **kwargs):
        self.params = {'use_sim_time': True, 'navigation_mode': 'LOCAL_TRAINING'}
        self.subscriptions, self.timers = [], []
    def get_parameter(self, name): return NS(value=self.params[name])
    def declare_parameter(self, name, value=None): self.params.setdefault(name, value)
    def create_publisher(self, *args): return NS(publish=lambda msg: None)
    def create_subscription(self, message_type, topic, callback, qos):
        self.subscriptions.append((topic, callback, qos))
    def create_timer(self, period, callback): self.timers.append((period, callback))
rclpy.node.Node = Node
from mecanum_nav_rl.runtime_safety import safety_supervisor_node as module
module.Buffer = lambda: NS()
module.TransformListener = lambda *args: None
root = Path.cwd()
p = json.loads((root/'ros2_ws/src/mecanum_nav_rl/config/v3/resolved/sim_train_local_training_soak.resolved.json').read_text())['training']['local_training']
sensor = json.loads((root/'artifacts/simulation/roadmap_b_b2/asset_manifest.json').read_text())['sensor']
ctx = dict(session_id='b23-test', config_hash='a'*64, ingress_instance_id=11,
           backend_instance_id=22, policy_source_instance_id=33, safe_stop_source_instance_id=44,
           profile=p, sensor=sensor, sim_estop_release_authorized=True)
node = module.SafetySupervisorNode(local_training_context=ctx, evidence_sink=lambda *args: None)
assert {s[0] for s in node.subscriptions} == {'/scan', '/mecanum/policy_candidate_cmd',
 '/mecanum/safety_lifecycle_state', '/mecanum/local_training/safety_input', '/mecanum/local_training/backend_state'}
assert node.timers == [(0.02, node.local_training.tick)]
assert node.local_training.policy_hold is True
assert not hasattr(node, '_core')
'''
    result = subprocess.run([sys.executable, '-c', script], cwd=Path(__file__).resolve().parents[4],
                            env=dict(os.environ), capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
