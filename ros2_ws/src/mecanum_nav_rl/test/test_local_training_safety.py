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


def test_safety_subscription_profiler_records_slow_input_without_changing_result(monkeypatch):
    import mecanum_nav_rl.runtime_safety.safety_supervisor_node as module
    from mecanum_nav_rl.runtime_safety.safety_supervisor_node import SafetySupervisorNode

    events = []
    node = object.__new__(SafetySupervisorNode)
    node.local_training = NS(emit=lambda event, facts: events.append((event, facts)))
    wall = iter((100, 10_000_101))
    cpu = iter((200, 6_000_201))
    monkeypatch.setattr(module.time, 'monotonic_ns', lambda: next(wall))
    monkeypatch.setattr(module.time, 'thread_time_ns', lambda: next(cpu))
    scan = NS(ranges=[1.0] * 500)
    callback = node._profile_local_training_callback('/scan', lambda msg: msg)
    assert callback(scan) is scan
    assert len(events) == 1
    event, facts = events[0]
    assert event == 'SAFETY_INPUT_CALLBACK_SLOW'
    assert facts['topic'] == '/scan'
    assert facts['wall_ns'] == 10_000_001
    assert facts['thread_cpu_ns'] == 6_000_001
    assert facts['range_count'] == 500
    assert facts['thread_native_id'] > 0

    wall = iter((20, 10_000_030))
    cpu = iter((40, 6_000_050))
    failed = node._profile_local_training_callback(
        '/mecanum/local_training/backend_state',
        lambda _msg: (_ for _ in ()).throw(ValueError('callback error')))
    with pytest.raises(ValueError, match='callback error'):
        failed(NS())
    assert len(events) == 2


def test_safety_subscription_profiler_aggregates_bounded_callback_work(monkeypatch):
    import threading
    import mecanum_nav_rl.runtime_safety.safety_supervisor_node as module
    from mecanum_nav_rl.runtime_safety.safety_supervisor_node import SafetySupervisorNode

    node = object.__new__(SafetySupervisorNode)
    node.local_training = NS(emit=lambda *_args: None)
    node._local_training_callback_stats_lock = threading.Lock()
    node._local_training_callback_stats = {}
    wall = iter((100, 1100, 2000, 5000))
    cpu = iter((200, 700, 900, 1400))
    monkeypatch.setattr(module.time, 'monotonic_ns', lambda: next(wall))
    monkeypatch.setattr(module.time, 'thread_time_ns', lambda: next(cpu))

    callback = node._profile_local_training_callback('/scan', lambda msg: msg)
    assert callback('one') == 'one'
    assert callback('two') == 'two'
    assert node._take_local_training_callback_stats() == {
        '/scan': {'count': 2, 'wall_ns': 4000, 'thread_cpu_ns': 1000,
                  'max_wall_ns': 3000, 'max_thread_cpu_ns': 500}}
    assert node._take_local_training_callback_stats() == {}


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
        assert command.header.stamp == f.stamp(f.clock.ros)
        assert command.twist.linear.y < 0 and command.twist.angular.z > 0
    received = a.command_received
    a.on_command(f.candidate)
    assert a.command_received == received
    f.advance(130_000_000)
    assert a.tick().source == f.candidate.SOURCE_SAFE_STOP
    assert 'COMMAND_STALE_OR_FUTURE' in f.state[-1].intervention_reasons


def test_local_safety_defers_only_normal_output_at_exact_scan_cutoff(local_adapter):
    f = local_adapter; adapter = f.adapter
    assert adapter.tick().source == f.candidate.SOURCE_SAFE_STOP
    for _ in range(4):
        f.advance()
        assert adapter.tick().source == f.candidate.SOURCE_POLICY
    assert f.clock.ros == 1_080_000_000
    previous_tick = adapter.last_tick_ns
    published_count, state_count = len(f.published), len(f.state)
    f.advance()
    assert f.clock.ros == 1_100_000_000
    assert adapter.tick() is None
    assert adapter.last_tick_ns == previous_tick
    assert len(f.published) == published_count and len(f.state) == state_count
    deferred = [data for name, data in f.evidence
        if name == 'SAFETY_OUTPUT_DEFERRED_AT_SCAN_CUTOFF']
    assert deferred[-1] == {'ros_ns':1_100_000_000,'steady_ns':2_100_000_000,
        'scan_period_ns':100_000_000,'prior_tick_ns':2_080_000_000}
    f.advance()
    assert adapter.tick().source == f.candidate.SOURCE_POLICY
    assert adapter.last_tick_ns == f.clock.steady
    assert len(f.published) == published_count + 1


def test_local_safety_defers_when_only_one_physics_step_remains(local_adapter):
    f = local_adapter; adapter = f.adapter
    assert adapter.tick().source == f.candidate.SOURCE_SAFE_STOP
    for _ in range(4):
        f.advance()
        assert adapter.tick().source == f.candidate.SOURCE_POLICY
    assert f.clock.ros == 1_080_000_000
    previous_tick = adapter.last_tick_ns
    published_count = len(f.published)

    # At 1:1 cadence, a tick at exactly one 10 ms physics step from the
    # cutoff is not enough to prove native application by that cutoff. Retain
    # the preceding receipt and defer this normal output.
    f.advance(10_000_000)
    assert f.clock.ros == 1_090_000_000
    before_defer_tick = adapter.last_tick_ns
    assert adapter.tick() is None
    assert adapter.last_tick_ns == before_defer_tick
    assert len(f.published) == published_count
    before = [data for name, data in f.evidence
        if name == 'SAFETY_OUTPUT_DEFERRED_BEFORE_SCAN_CUTOFF']
    assert before == [{'boundary_ns':1_100_000_000,
        'ros_ns':1_090_000_000,'steady_ns':2_090_000_000,
        'remaining_ros_ns':10_000_000,'projected_remaining_steady_ns':10_000_000,
        'physics_step_ns':10_000_000,'observed_ros_delta_ns':10_000_000,
        'observed_steady_delta_ns':10_000_000}]

    # Exact-cutoff suppression and recovery after the boundary remain in force.
    f.advance(10_000_000)
    assert adapter.tick() is None
    f.advance(20_000_000)
    assert adapter.tick().source == f.candidate.SOURCE_POLICY
    assert f.clock.ros == 1_120_000_000
    assert len(f.published) == published_count + 1
    assert f.clock.steady - previous_tick == 40_000_000


def test_local_safety_fault_stop_is_not_deferred_before_scan_cutoff(local_adapter):
    f = local_adapter; adapter = f.adapter
    assert adapter.tick().source == f.candidate.SOURCE_SAFE_STOP
    for _ in range(4):
        f.advance()
        adapter.tick()
    f.advance(10_000_000)
    adapter.command_received = f.clock.steady - 250_000_000
    output = adapter.tick()
    assert output.source == output.SOURCE_SAFE_STOP
    assert 'COMMAND_STALE_OR_FUTURE' in f.state[-1].intervention_reasons
    assert not any(name == 'SAFETY_OUTPUT_DEFERRED_BEFORE_SCAN_CUTOFF'
        for name, _ in f.evidence)


def test_local_safety_uses_observed_ros_steady_rate_for_cutoff_margin(local_adapter):
    f = local_adapter; adapter = f.adapter
    assert adapter.tick().source == f.candidate.SOURCE_SAFE_STOP
    for _ in range(4):
        f.clock.ros += 10_000_000
        f.clock.steady += 20_000_000
        output = adapter.tick()
        assert output is not None and output.source == output.SOURCE_POLICY
    assert f.clock.ros == 1_040_000_000

    # At RTF 0.5, 20 ms of ROS time to the cutoff is 40 ms steady time,
    # leaving more than one 20 ms Safety period for application.
    f.clock.ros = 1_080_000_000
    f.clock.steady += 80_000_000
    output = adapter.tick()
    assert output is not None and output.source == output.SOURCE_POLICY
    f.clock.ros = 1_090_000_000
    f.clock.steady += 20_000_000
    output = adapter.tick()
    assert output is not None and output.source == output.SOURCE_POLICY
    assert not any(name == 'SAFETY_OUTPUT_DEFERRED_BEFORE_SCAN_CUTOFF'
        for name, _ in f.evidence)


def test_local_safety_keeps_deferring_repeated_steady_ticks_at_exact_ros_cutoff(local_adapter):
    f = local_adapter; adapter = f.adapter
    assert adapter.tick().source == f.candidate.SOURCE_SAFE_STOP
    for _ in range(4):
        f.advance()
        assert adapter.tick().source == f.candidate.SOURCE_POLICY
    f.advance()
    assert f.clock.ros == 1_100_000_000
    published_count, state_count = len(f.published), len(f.state)
    assert adapter.tick() is None

    # A steady timer can fire again before the simulation clock advances.
    # It must not publish another receipt stamped at the same scan cutoff.
    f.advance(ns=0)
    assert adapter.tick() is None
    assert len(f.published) == published_count and len(f.state) == state_count
    deferred = [data for name, data in f.evidence
        if name == 'SAFETY_OUTPUT_DEFERRED_AT_SCAN_CUTOFF']
    assert len(deferred) == 1

    f.advance()
    output = adapter.tick()
    assert output is not None and output.source == output.SOURCE_POLICY
    assert f.clock.ros == 1_120_000_000
    assert len(f.published) == published_count + 1
    assert len([data for name, data in f.evidence
        if name == 'SAFETY_OUTPUT_DEFERRED_AT_SCAN_CUTOFF']) == 1


def test_local_safety_defers_normal_output_when_steady_tick_crosses_scan_cutoff(local_adapter):
    f = local_adapter; adapter = f.adapter
    assert adapter.tick().source == f.candidate.SOURCE_SAFE_STOP
    for _ in range(4):
        f.advance()
        assert adapter.tick().source == f.candidate.SOURCE_POLICY
    assert f.clock.ros == 1_080_000_000
    previous_tick = adapter.last_tick_ns
    published_count, state_count = len(f.published), len(f.state)

    # The steady timer skips ROS 1.100 s and wakes at 1.110 s.
    f.advance(30_000_000)
    assert f.clock.ros == 1_110_000_000
    assert adapter.tick() is None
    assert adapter.last_tick_ns == previous_tick
    assert len(f.published) == published_count and len(f.state) == state_count
    deferred = [data for name, data in f.evidence
        if name == 'SAFETY_OUTPUT_DEFERRED_AT_SCAN_CUTOFF']
    assert deferred[-1] == {'ros_ns':1_110_000_000,'steady_ns':2_110_000_000,
        'scan_period_ns':100_000_000,'prior_tick_ns':2_080_000_000,
        'crossed_boundary_ns':1_100_000_000,
        'reason':'steady_tick_crossed_scan_cutoff'}

    f.advance()
    assert adapter.tick().source == f.candidate.SOURCE_POLICY
    assert adapter.last_tick_ns == f.clock.steady
    assert len(f.published) == published_count + 1


def test_local_safety_still_publishes_fault_zero_at_scan_cutoff(local_adapter):
    f = local_adapter; adapter = f.adapter
    assert adapter.tick().source == f.candidate.SOURCE_SAFE_STOP
    f.advance()
    assert adapter.tick().source == f.candidate.SOURCE_POLICY
    f.advance()
    f.backend.fault_flags = 1
    f.backend.status_sequence += 1
    adapter.on_backend(f.backend)
    f.advance(60_000_000)
    assert f.clock.ros == 1_100_000_000
    message = adapter.tick()
    assert message.source == message.SOURCE_SAFE_STOP
    assert not any((message.twist.linear.x, message.twist.linear.y, message.twist.angular.z))
    assert 'BACKEND_CONTACT_UNHEALTHY' in f.state[-1].intervention_reasons
    assert not any(name == 'SAFETY_OUTPUT_DEFERRED_AT_SCAN_CUTOFF' for name, _ in f.evidence)


def test_local_safety_suppresses_only_armed_reset_zero_at_exact_scan_boundary(local_adapter):
    f = local_adapter; adapter = f.adapter
    adapter.set_policy_hold(True)
    first = adapter.tick()
    assert first.source == first.SOURCE_SAFE_STOP
    target = 1_100_000_000
    adapter.arm_reset_scan_boundary(target)
    published, states = len(f.published), len(f.state)
    f.clock.ros = target
    f.clock.steady += 20_000_000
    assert adapter.tick() is None
    assert len(f.published) == published and len(f.state) == states
    assert adapter._reset_boundary_suppressed_stamp_ns == target
    assert any(name == 'RESET_SAFE_STOP_BOUNDARY_SUPPRESSED' and
        data['target_scan_ns'] == target for name, data in f.evidence)
    f.clock.ros += 20_000_000; f.clock.steady += 20_000_000
    resumed = adapter.tick()
    assert resumed.source == resumed.SOURCE_SAFE_STOP
    assert len(f.published) == published + 1


def test_local_safety_suppresses_one_zero_when_timer_tick_lands_within_scan_period(local_adapter):
    f = local_adapter; adapter = f.adapter
    adapter.set_policy_hold(True)
    first = adapter.tick()
    assert first.source == first.SOURCE_SAFE_STOP
    target = 1_100_000_000
    adapter.arm_reset_scan_boundary(target)
    f.clock.ros = target - 10_000_000
    f.clock.steady += 20_000_000
    published, states, sequence = len(f.published), len(f.state), adapter.safe_stop_sequence
    assert adapter.tick() is None
    assert len(f.published) == published and len(f.state) == states
    assert adapter._reset_scan_boundary_stamp_ns == target
    assert adapter._reset_boundary_suppressed_stamp_ns == target
    f.clock.ros = target + 10_000_000
    f.clock.steady += 20_000_000
    assert adapter.tick() is None
    assert len(f.published) == published and len(f.state) == states
    assert adapter._reset_boundary_suppressed_stamp_ns == target
    assert adapter.safe_stop_sequence == sequence
    suppressed = next(data for name, data in f.evidence
        if name == 'RESET_SAFE_STOP_BOUNDARY_SUPPRESSED')
    assert suppressed == {'target_scan_ns': target, 'observed_ros_ns': target - 10_000_000,
        'suppression_window_start_ns': target - adapter.safety_period_ns,
        'steady_ns': f.clock.steady - 20_000_000}
    f.clock.ros += 20_000_000; f.clock.steady += 20_000_000
    resumed = adapter.tick()
    assert resumed.source == resumed.SOURCE_SAFE_STOP
    assert len(f.published) == published + 1


def test_local_safety_does_not_suppress_boundary_without_prior_zero_stop(local_adapter):
    f = local_adapter; adapter = f.adapter
    adapter.set_policy_hold(True)
    assert adapter.tick().source == f.candidate.SOURCE_SAFE_STOP
    adapter.set_policy_hold(False)
    f.advance()
    assert adapter.tick().source == f.candidate.SOURCE_POLICY
    adapter.set_policy_hold(True)
    adapter.arm_reset_scan_boundary(1_100_000_000)
    f.clock.ros = 1_100_000_000; f.clock.steady += 20_000_000
    output = adapter.tick()
    assert output is not None and output.source == output.SOURCE_SAFE_STOP
    assert adapter._reset_boundary_suppressed_stamp_ns is None
    assert any(name == 'RESET_SAFE_STOP_BOUNDARY_NOT_SUPPRESSED' for name, _ in f.evidence)


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


def test_local_safety_rejection_records_candidate_and_selected_zero_identity(local_adapter):
    f = local_adapter; adapter = f.adapter
    adapter.set_policy_hold(True)
    output = adapter.tick()
    assert output.source == output.SOURCE_SAFE_STOP
    event = next(data for name, data in reversed(f.evidence) if name == 'SAFETY_REJECTED')
    assert event['source'] == output.SOURCE_SAFE_STOP
    assert event['sequence'] == output.sequence
    assert event['candidate_source'] == f.candidate.SOURCE_POLICY
    assert event['candidate_sequence'] == f.candidate.sequence
    assert event['candidate_source_instance_id'] == f.candidate.source_instance_id
    assert 'POLICY_HELD' in event['reasons']


@pytest.mark.parametrize('field,value', [('contact_active', True), ('fault_flags', 1),
    ('coverage_complete', False), ('contact_source_healthy', False),
    ('observed_collision_mask', 1), ('paused', True), ('backend_instance_id', 99)])
def test_local_safety_backend_contact_and_identity_fail_closed(local_adapter, field, value):
    f = local_adapter; f.adapter.tick(); f.advance()
    setattr(f.backend, field, value); f.backend.status_sequence += 1
    f.adapter.on_backend(f.backend)
    message = f.adapter.tick()
    assert message.source == f.candidate.SOURCE_SAFE_STOP
    if field == 'backend_instance_id':
        assert 'BACKEND_IDENTITY' in f.state[-1].intervention_reasons
        return
    assert 'BACKEND_CONTACT_UNHEALTHY' in f.state[-1].intervention_reasons
    evidence = [data for name, data in f.evidence if name == 'BACKEND_CONTACT_GATE_REJECTED']
    assert evidence, f.evidence
    gate = evidence[-1]
    assert gate['status_present'] is True, gate
    assert gate['status_age_valid'] is True, gate
    assert gate['identity_matches'] is True, gate
    assert gate[field] == value, gate


def test_local_safety_backend_contact_gate_records_stale_receive_status(local_adapter):
    """Expose the exact receive-age fact that made the backend gate fail."""
    f = local_adapter; f.adapter.tick(); f.advance()
    f.clock.steady += 200_000_001
    message = f.adapter.tick()
    assert message.source == message.SOURCE_SAFE_STOP
    assert 'BACKEND_CONTACT_UNHEALTHY' in f.state[-1].intervention_reasons
    gate = next(data for name, data in reversed(f.evidence)
        if name == 'BACKEND_CONTACT_GATE_REJECTED')
    assert gate['status_age_ns'] == 220_000_001, gate
    assert gate['status_age_valid'] is False, gate


def test_backend_state_serialization_does_not_hold_safety_tick_lock(local_adapter, monkeypatch):
    """A slow backend snapshot must not block the watchdog-fed Safety tick."""
    import threading
    import rclpy.serialization

    f = local_adapter
    backend = copy.deepcopy(f.backend)
    backend.status_sequence += 1
    original_serialize = rclpy.serialization.serialize_message
    serializing = threading.Event()
    release_serializer = threading.Event()
    tick_completed = threading.Event()

    def blocked_serialize(message):
        serializing.set()
        if not release_serializer.wait(timeout=2.0):
            raise TimeoutError('test serializer release timed out')
        return original_serialize(message)

    monkeypatch.setattr(rclpy.serialization, 'serialize_message', blocked_serialize)
    backend_thread = threading.Thread(target=f.adapter.on_backend, args=(backend,), daemon=True)
    tick_thread = threading.Thread(
        target=lambda: (f.adapter.tick(), tick_completed.set()), daemon=True)
    backend_thread.start()
    try:
        assert serializing.wait(timeout=1.0), 'backend callback did not reach serialization seam'
        tick_thread.start()
        assert tick_completed.wait(timeout=0.05), (
            'Safety tick waited behind backend serialization/copy work')
    finally:
        release_serializer.set()
        backend_thread.join(timeout=1.0)
        if tick_thread.ident is not None:
            tick_thread.join(timeout=1.0)
    assert not backend_thread.is_alive()
    assert tick_thread.ident is not None and not tick_thread.is_alive()
    assert f.adapter.status.status_sequence == backend.status_sequence


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
import sys
from pathlib import Path
from types import SimpleNamespace as NS
import rclpy.node
class CallbackGroup: pass
sys.modules['rclpy.callback_groups'] = NS(
    MutuallyExclusiveCallbackGroup=CallbackGroup,
    ReentrantCallbackGroup=CallbackGroup)
class Node:
    def __init__(self, name, **kwargs):
        self.params = {'use_sim_time': True, 'navigation_mode': 'LOCAL_TRAINING'}
        self.subscriptions, self.timers = [], []
        self.ros_now_ns = 0
    def get_parameter(self, name): return NS(value=self.params[name])
    def get_clock(self): return NS(now=lambda: NS(nanoseconds=self.ros_now_ns))
    def declare_parameter(self, name, value=None): self.params.setdefault(name, value)
    def create_publisher(self, *args): return NS(publish=lambda msg: None)
    def create_subscription(self, message_type, topic, callback, qos):
        self.subscriptions.append((topic, callback, qos))
    def create_timer(self, period, callback, callback_group=None, clock=None, autostart=True):
        timer = NS(clock=clock, period=period, callback=callback, callback_group=callback_group)
        self.timers.append(timer)
        return timer
    def destroy_timer(self, timer): self.timers.remove(timer)
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
events = []
tick_now = [0]
node = module.SafetySupervisorNode(local_training_context=ctx,
    evidence_sink=lambda *args: events.append(args), _steady_now_ns=lambda: tick_now[0])
assert {s[0] for s in node.subscriptions} == {'/scan', '/mecanum/cmd_policy',
 '/mecanum/safety_lifecycle_state', '/mecanum/local_training/safety_input', '/mecanum/local_training/backend_state'}
assert len(node.timers) == 1 and node.timers[0].period == 0.02
assert node.timers[0].clock.clock_type == rclpy.clock.ClockType.STEADY_TIME
assert isinstance(node._local_training_timer_group, CallbackGroup)
assert node.timers[0].callback_group is node._local_training_timer_group
assert node.timers[0].callback == node._start_local_training_periodic_timer
assert node._local_training_phase_timer is node.timers[0] and node._local_training_timer is None
tick_now[0] = 20_000_000
node.timers[0].callback()
assert len(node.timers) == 1 and node.timers[0].period == 0.02
assert node.timers[0].clock.clock_type == rclpy.clock.ClockType.STEADY_TIME
assert node.timers[0].callback_group is node._local_training_timer_group
assert node.timers[0].callback == node._tick_local_training_steady
assert node._local_training_phase_timer is None and node._local_training_timer is node.timers[0]
phase = next(fields for event, fields in events if event == 'SAFETY_TIMER_PHASE_STARTED')
assert phase['initial_offset_ns'] == 20_000_000
assert phase['actual_initial_delay_ns'] == 20_000_000
assert phase['period_ns'] == 20_000_000
assert phase['clock'] == 'steady'
assert node.local_training.policy_hold is True
assert not hasattr(node, '_core')
ticks = []
node.local_training.tick = lambda: ticks.append(tick_now[0])
import time
thread_cpu = [0]
def fake_thread_time_ns():
    thread_cpu[0] += 1000
    return thread_cpu[0]
time.thread_time_ns = fake_thread_time_ns
for tick_now[0] in (0, 20_000_000, 100_000_000):
    node._tick_local_training_steady()
overruns = [(event, fields) for event, fields in events if event == 'SAFETY_TIMER_OVERRUN']
assert ticks == [0, 20_000_000, 100_000_000]
assert len(overruns) == 1 and overruns[0][1] == {
    'clock':'steady', 'previous_tick_ns':20_000_000, 'current_tick_ns':100_000_000,
    'gap_ns':80_000_000, 'period_ns':20_000_000,
    'previous_callback_wall_ns':0, 'previous_callback_cpu_ns':1000,
    'missed_periods_lower_bound':3,
    'subscription_callback_work_since_previous_tick':{}}
node._local_training_last_timer_ns = None
tick_now[0] = 200_000_000
node.local_training.tick = lambda: tick_now.__setitem__(0, tick_now[0] + 25_000_000)
node._tick_local_training_steady()
slow = [(event, fields) for event, fields in events if event == 'SAFETY_TIMER_CALLBACK_SLOW']
assert len(slow) == 1 and slow[0][1] == {
    'clock':'steady', 'started_ns':200_000_000, 'completed_ns':225_000_000,
    'callback_wall_ns':25_000_000, 'callback_thread_cpu_ns':1000,
    'period_ns':20_000_000}

# Exercise the real main() branch with fake ROS/executor boundaries. LOCAL_TRAINING
# gets a dedicated worker for its mutually-exclusive steady timer group; NAV2 keeps
# the existing rclpy.spin path.
executor_calls = []
class FakeExecutor:
    def __init__(self, *, num_threads): executor_calls.append(('init', num_threads))
    def add_node(self, value): executor_calls.append(('add', value.mode))
    def spin(self): executor_calls.append(('spin',))
    def shutdown(self): executor_calls.append(('shutdown',))
sys.modules['rclpy.executors'] = NS(MultiThreadedExecutor=FakeExecutor)
module.rclpy.init = lambda args=None: executor_calls.append(('ros_init',))
module.rclpy.shutdown = lambda: executor_calls.append(('ros_shutdown',))
module.rclpy.spin = lambda value: executor_calls.append(('single_spin', value.mode))
class MainNode:
    def __init__(self, mode): self.mode = mode
    def get_parameter(self, name): return NS(value=self.mode)
    def destroy_node(self): executor_calls.append(('destroy', self.mode))
for mode in ('LOCAL_TRAINING', 'NAV2_BASELINE'):
    module.SafetySupervisorNode = lambda mode=mode: MainNode(mode)
    module.main([])
assert ('init', 4) in executor_calls and ('add', 'LOCAL_TRAINING') in executor_calls
assert ('single_spin', 'NAV2_BASELINE') in executor_calls
assert executor_calls.count(('shutdown',)) == 1
'''
    result = subprocess.run([sys.executable, '-c', script], cwd=Path(__file__).resolve().parents[4],
                            env=dict(os.environ), capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
