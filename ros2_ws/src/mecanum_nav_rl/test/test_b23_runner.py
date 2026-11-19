"""Biên deadline/ownership worker bằng I/O fakes, không tạo ROS context."""
import ast
import asyncio
import json
import threading
import textwrap
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
import mecanum_nav_rl.runtime_simulation.b23_runner as runner_module
from mecanum_nav_rl.runtime_simulation.b23_runner import (
    TrainingWorkerIO, case_environment, case_fault_hooks, technical_outcome,
    QueuedRunEvidence, RunEvidence,
    policy_bind_launch_window_remaining_ns, policy_bind_launch_window_ready,
    verify_r01b_external_pause_rejection, verify_r01_pause_ack_failure,
    verify_r02_policy_order, r02a_native_admission_row,
    verify_r02f_safety_hold, verify_r02_late_receipt_rejected,
    verify_r02e_prebind_admission_rejected, verify_r02e_safety_input_enqueued,
    verify_r02g_close, r02g_inhibit_operation,
    await_r02g_exact_safe_stop_application,
    r02g_close_admission, verify_r03_receipt_fault, install_r04_delivery_fault,
    enable_r04_adapter_fault_dispatch, verify_r04_stale_delivery,
    r04_policy_step_fault_plan,
    await_r04a_production_rejection, await_r04a_post_rejection_zero,
    await_r04a_delayed_callback,
    verify_r04a_next_step_blocked,
    verify_r04a_zero_baseline, abort_r04a_pending_step_if_active,
    verify_r04c_next_step_blocked, verify_r04c_stale_rejection_and_zero,
    verify_r04c_stale_issuance_commit_rejected, require_r04c_fault_state,
    verify_r05_contact_query_revocation,
    expected_r05_revoked_query_ack, verify_r07a_unexpected_pause, policy_receipt_count,
    verify_r07a_resumed_inhibition, policy_step_identities,
    verify_r07b_revocation, verify_r07b_backend_restart,
    verify_owned_restart_request, verify_r07c_backend_restart,
    verify_r07d_final_publisher_restart, prepare_r07d_final_publisher_restart,
    pin_initial_final_publisher_identity, same_process_identity,
    query_replacement_backend_then_inhibit, verify_r09a_goal_settle,
    verify_r09b_task_contact, require_r09_scenario,
    should_emit_policy_cutoff_pending, worker_latency_diagnostic,
)


def test_worker_latency_diagnostic_separates_wall_gap_from_thread_cpu():
    assert worker_latency_diagnostic(started_ns=100, completed_ns=20_000_101,
        thread_cpu_started_ns=40, thread_cpu_completed_ns=60) == {
            'wall_ns':20_000_001, 'thread_cpu_ns':20,
            'non_cpu_wait_lower_bound_ns':19_999_981,
            'threshold_ns':20_000_000}
    assert worker_latency_diagnostic(started_ns=100, completed_ns=20_000_101,
        thread_cpu_started_ns=40, thread_cpu_completed_ns=20_000_040) == {
            'wall_ns':20_000_001, 'thread_cpu_ns':20_000_000,
            'non_cpu_wait_lower_bound_ns':1,
            'threshold_ns':20_000_000}
    assert worker_latency_diagnostic(started_ns=1, completed_ns=2,
        thread_cpu_started_ns=1, thread_cpu_completed_ns=2) is None
    assert worker_latency_diagnostic(started_ns=100, completed_ns=20_000_101,
        thread_cpu_started_ns=40, thread_cpu_completed_ns=60,
        process_cpu_started_ns=50, process_cpu_completed_ns=10_000_050) == {
            'wall_ns':20_000_001, 'thread_cpu_ns':20,
            'non_cpu_wait_lower_bound_ns':19_999_981,
            'threshold_ns':20_000_000, 'process_cpu_ns':10_000_000,
            'process_non_cpu_wait_lower_bound_ns':10_000_001}
    with pytest.raises(ValueError, match='moved backward'):
        worker_latency_diagnostic(started_ns=2, completed_ns=1,
            thread_cpu_started_ns=1, thread_cpu_completed_ns=2)
    with pytest.raises(ValueError, match='process CPU timestamps'):
        worker_latency_diagnostic(started_ns=1, completed_ns=30_000_001,
            thread_cpu_started_ns=1, thread_cpu_completed_ns=2,
            process_cpu_started_ns=1)


def test_worker_emit_reports_lock_wait_and_sink_delay_without_changing_event():
    class SlowLock:
        def __enter__(self):
            threading.Event().wait(.03)
        def __exit__(self, *args):
            return False

    for lock, delay_sink in ((SlowLock(), False), (threading.RLock(), True)):
        calls = []
        def sink(name, facts):
            calls.append((name, facts))
            if name == 'SLOW_EVENT' and delay_sink:
                threading.Event().wait(.03)
        worker = object.__new__(TrainingWorkerIO)
        worker._emit_lock = lock
        worker.events = []
        worker._accepted_policy_event_keys = set()
        worker._event_sink = sink
        worker._emit('SLOW_EVENT', {'source':'fake'})
        assert calls[0] == ('SLOW_EVENT', {'source':'fake'})
        assert calls[1][0] == 'B23_WORKER_EVENT_BLOCK'
        assert calls[1][1]['event_name'] == 'SLOW_EVENT'
        assert calls[1][1]['threshold_ns'] == 20_000_000
        if delay_sink:
            assert calls[1][1]['sink_wall_ns'] > 20_000_000
        else:
            assert calls[1][1]['lock_wait_ns'] > 20_000_000


def test_queued_run_evidence_preserves_order_and_does_not_wait_for_blocked_sink():
    entered, release, producer_done = threading.Event(), threading.Event(), threading.Event()
    rows = []
    class Sink:
        def record(self, event, facts, *, collected_ns=None):
            if event == 'first':
                entered.set()
                assert release.wait(2.)
            rows.append((event, facts, collected_ns))
        def sync(self):
            return None
        def close(self):
            return None
    sink = QueuedRunEvidence(Sink(), capacity=4)
    sink.record('first', {'value':1})
    assert entered.wait(1.)
    producer = threading.Thread(target=lambda: (sink.record('second', {'value':2}), producer_done.set()))
    producer.start()
    try:
        assert producer_done.wait(.1), 'callback-side record blocked behind the evidence sink'
    finally:
        release.set()
        producer.join(1.)
    sink.close(deadline_ns=runner_module.time.monotonic_ns()+2_000_000_000)
    assert [row[0] for row in rows] == ['first','second']
    assert all(type(row[2]) is int and row[2] > 0 for row in rows)


def test_queued_run_evidence_records_original_monotonic_collection_time(tmp_path):
    underlying = RunEvidence(tmp_path, 'worker', run_id='B23_TEST', invocation_id='test-invocation')
    sink = QueuedRunEvidence(underlying)
    before = runner_module.time.monotonic_ns()
    sink.record('QUEUED_SAMPLE', {'identity':'pinned'})
    after = runner_module.time.monotonic_ns()
    sink.close(deadline_ns=runner_module.time.monotonic_ns()+2_000_000_000)
    import json
    record = json.loads((tmp_path/'worker-events.jsonl').read_text().strip())
    assert record['event'] == 'QUEUED_SAMPLE'
    assert record['facts'] == {'identity':'pinned'}
    assert before <= record['collected_ns'] <= after


def test_queued_run_evidence_sink_failure_is_retained_and_fails_close():
    class BrokenSink:
        def record(self, event, facts, *, collected_ns=None):
            raise OSError('injected evidence write failure')
        def sync(self):
            return None
        def close(self):
            return None
    sink = QueuedRunEvidence(BrokenSink())
    sink.record('SAMPLE', {})
    with pytest.raises(RuntimeError, match='queued worker evidence writer failed'):
        sink.close(deadline_ns=runner_module.time.monotonic_ns()+2_000_000_000)


def test_case_phase_is_bound_in_packet_and_capacity_one_guard():
    from mecanum_nav_rl.runtime_simulation.b23_runner import campaign_phase, verify_guard_authority
    assert campaign_phase('R01a') == 'smoke'
    assert campaign_phase('R01e') == 'fault_task'
    assert campaign_phase('R02a') == 'fault_task'
    assert campaign_phase('R02b') == 'fault_task'
    assert campaign_phase('R02e') == 'fault_task'
    assert campaign_phase('R02f') == 'fault_task'
    assert campaign_phase('R02g') == 'fault_task'
    assert campaign_phase('R04a') == 'fault_task'
    assert campaign_phase('R05') == 'fault_task'
    assert campaign_phase('R06a') == 'fault_task'
    assert campaign_phase('R06b') == 'fault_task'
    assert campaign_phase('R06c') == 'fault_task'
    assert campaign_phase('R07a') == 'fault_task'
    assert campaign_phase('R07b') == 'fault_task'
    assert campaign_phase('R07c') == 'fault_task'
    assert campaign_phase('R07d') == 'fault_task'
    assert campaign_phase('R09a') == 'fault_task'
    assert campaign_phase('R09b') == 'fault_task'
    assert campaign_phase('R08') == 'soak'
    packet = {'case': 'R01e', 'run_id': 'B23_R01E_TEST'}
    authority = {'run_id': packet['run_id'], 'capacity': 1, 'packet_sha256': 'a'*64,
        'phase': 'fault_task', 'consumed': False}
    assert verify_guard_authority(packet, authority, 'a'*64) == 'fault_task'
    for key, bad in [('phase', 'smoke'), ('run_id', 'B23_R01A_TEST'),
                     ('capacity', 2), ('packet_sha256', 'b'*64), ('consumed', True)]:
        original = authority[key]
        authority[key] = bad
        with pytest.raises(RuntimeError, match='authority does not match packet case/phase'):
            verify_guard_authority(packet, authority, 'a'*64)
        authority[key] = original
    with pytest.raises(ValueError, match='unsupported B2.3 campaign case'):
        campaign_phase('R10')


def test_worker_safety_timer_executor_runs_independently_and_joins():
    """Production worker keeps Safety callbacks off the ingress executor pump."""
    import threading

    safety_started = threading.Event()
    safety_release = threading.Event()
    observed = {}

    class SafetyExecutor:
        def spin(self):
            observed['safety_thread'] = threading.current_thread().name
            safety_started.set()
            assert safety_release.wait(1.0)

        def shutdown(self, timeout_sec):
            observed['safety_shutdown_timeout'] = timeout_sec
            safety_release.set()
            return True

        def remove_node(self, _node):
            pass

    class MainExecutor:
        def spin_once(self, timeout_sec):
            observed['main_thread'] = threading.current_thread().name
            observed['main_timeout'] = timeout_sec
            assert safety_started.wait(0.5), 'Safety executor did not start independently'
            worker.stop_requested = True

        def shutdown(self, timeout_sec):
            observed['main_shutdown_timeout'] = timeout_sec
            return True

        def remove_node(self, _node):
            pass

    class Context:
        def ok(self):
            return True

        def shutdown(self):
            observed['context_shutdown'] = True

    worker = TrainingWorkerIO.__new__(TrainingWorkerIO)
    worker.safety_executor = SafetyExecutor()
    worker.executor = MainExecutor()
    worker.safety_thread = None
    worker.pump_task = None
    worker.pump_error = None
    worker.safety_executor_error = None
    worker.stop_requested = False
    worker.abort_requested = None
    worker.pause = asyncio.sleep
    worker.context = Context()
    worker.nodes = []
    worker.emit = lambda *_args, **_kwargs: None
    worker._deliver_future_receipts_after_clock = lambda: None
    worker._deliver_r04d_ingress_lifecycle_if_due = lambda: None

    async def exercise():
        worker.start_pump()
        await asyncio.wait_for(worker.pump_task, timeout=1.0)

    asyncio.run(exercise())
    errors = worker.close_context()
    assert errors == [], errors
    assert observed['safety_thread'] == 'b23-safety-steady-executor'
    assert observed['main_thread'] != observed['safety_thread']
    assert observed['main_timeout'] == 0.0
    assert observed['safety_shutdown_timeout'] == 1.0
    assert observed['context_shutdown'] is True
    assert worker.safety_thread is not None and not worker.safety_thread.is_alive()


def test_local_training_safety_executor_uses_two_workers_for_isolated_timer_group(monkeypatch):
    import sys
    calls = []
    context = object()

    class MultiThreadedExecutorFake:
        def __init__(self, *, num_threads, context):
            calls.append((num_threads, context))

    monkeypatch.setitem(sys.modules, 'rclpy.executors',
        NS(MultiThreadedExecutor=MultiThreadedExecutorFake))
    result = runner_module._new_local_training_safety_executor(context)

    assert isinstance(result, MultiThreadedExecutorFake)
    assert calls == [(2, context)]


def test_run_evidence_serializes_concurrent_safety_and_worker_records(tmp_path):
    from mecanum_nav_rl.runtime_simulation.b23_runner import RunEvidence

    evidence = RunEvidence(tmp_path, 'worker', run_id='B23-THREAD-TEST',
        invocation_id='inv-thread-test')
    failures = []

    def write_events(prefix):
        try:
            for index in range(40):
                evidence.record(prefix, {'index': index})
        except BaseException as error:
            failures.append(error)

    threads = [threading.Thread(target=write_events, args=(f'event-{index}',))
        for index in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2.0)
    assert not failures, failures
    assert all(not thread.is_alive() for thread in threads)
    evidence.close()
    records = [json.loads(line) for line in (tmp_path / 'worker-events.jsonl').read_text().splitlines()]
    assert len(records) == 120
    assert all(record['invocation_id'] == 'inv-thread-test' for record in records)


def test_run_evidence_buffers_hot_path_until_explicit_sync(tmp_path):
    from mecanum_nav_rl.runtime_simulation.b23_runner import RunEvidence

    evidence = RunEvidence(tmp_path, 'worker', run_id='B23-BUFFER-TEST',
        invocation_id='inv-buffer-test')
    evidence.record('PHYSICS_PAIR', {'iteration': 1, 'stamp_ns': 10})
    events_path = tmp_path/'worker-events.jsonl'
    assert events_path.read_bytes() == b'', 'hot-path append must not flush synchronously'

    evidence.sync()
    rows = [json.loads(line) for line in events_path.read_text().splitlines()]
    assert len(rows) == 1 and rows[0]['facts'] == {'iteration': 1, 'stamp_ns': 10}
    evidence.close()


def test_native_control_event_is_visible_to_cross_process_reader_before_sync(tmp_path):
    """The worker polls this index before native watchdog expiry; expose full rows promptly."""
    from mecanum_nav_rl.runtime_simulation.b23_runner import RunEvidence

    evidence = RunEvidence(tmp_path, 'parent', run_id='B23-NATIVE-FLUSH',
        invocation_id='inv-native-flush')
    evidence.record('owned_process_output', {
        'process':'server', 'pid':123, 'command':['gz', 'sim'], 'stream':'stdout',
        'text':('[Msg] B23_ADMISSION_ACCEPTED session=session-a backend=11 ingress=22 '
            'sample=33 source_ns=44000000 receive_ns=55 processed_ns=66 iteration=7')})
    path = tmp_path/'native-events.jsonl'
    raw = path.read_bytes()
    rows = [json.loads(line) for line in raw.splitlines()]
    assert len(rows) == 1, raw
    assert rows[0]['kind'] == 'B23_ADMISSION_ACCEPTED'
    assert rows[0]['fields']['sample'] == '33'
    assert rows[0]['invocation_id'] == 'inv-native-flush'
    evidence.close()


def test_published_policy_receipt_is_visible_to_cross_process_reader_before_close(tmp_path):
    """R03 verifies a dropped receipt before the separate publisher exits."""
    from mecanum_nav_rl.runtime_simulation.b23_runner import RunEvidence

    evidence = RunEvidence(tmp_path, 'final', run_id='B23-POLICY-RECEIPT-FLUSH',
        invocation_id='inv-policy-receipt-flush')
    evidence.record('policy_final_published', {
        'source_sequence':1, 'step_index':1, 'publisher_instance_id':42,
        'publish_sequence':77, 'receipt_cdr_hex':'0102'})
    path = tmp_path/'policy_final_published.jsonl'
    rows = [json.loads(line) for line in path.read_bytes().splitlines()]
    assert len(rows) == 1
    assert rows[0]['event'] == 'policy_final_published'
    assert rows[0]['facts']['publish_sequence'] == 77
    assert rows[0]['invocation_id'] == 'inv-policy-receipt-flush'
    evidence.close()


def test_policy_adapter_issuance_is_visible_to_live_verifier_before_sync(tmp_path):
    """R04b checks the issued candidate before the worker evidence sink closes."""
    from mecanum_nav_rl.runtime_simulation.b23_runner import RunEvidence

    evidence = RunEvidence(tmp_path, 'worker', run_id='B23-ADAPTER-ISSUANCE-FLUSH',
        invocation_id='inv-adapter-issuance-flush')
    evidence.record('policy_adapter_issued', {
        'step_index':1, 'sequence':1, 'source_instance_id':42,
        'transition_id':'policy-1', 'steady_ns':90})
    path = tmp_path/'policy_adapter_issued.jsonl'
    rows = [json.loads(line) for line in path.read_bytes().splitlines()]
    assert len(rows) == 1
    assert rows[0]['event'] == 'policy_adapter_issued'
    assert rows[0]['facts']['transition_id'] == 'policy-1'
    assert rows[0]['invocation_id'] == 'inv-adapter-issuance-flush'
    evidence.close()


def test_final_lifecycle_delivery_is_visible_to_live_r04d_verifier_before_sync(tmp_path):
    from mecanum_nav_rl.runtime_simulation.b23_runner import RunEvidence

    evidence = RunEvidence(tmp_path, 'final', run_id='B23-R04D-FINAL-FLUSH',
        invocation_id='inv-r04d-final-flush')
    evidence.record('R04D_FINAL_LIFECYCLE_DELIVERY_COMPLETED', {
        'sequence':6, 'identity':[2,2,2], 'delivery_ns':700,
        'source_stamp_ns':1_190_000_000})
    path = tmp_path/'final-events.jsonl'
    rows = [json.loads(line) for line in path.read_bytes().splitlines()]
    assert len(rows) == 1
    assert rows[0]['event'] == 'R04D_FINAL_LIFECYCLE_DELIVERY_COMPLETED'
    assert rows[0]['facts']['delivery_ns'] == 700
    assert rows[0]['invocation_id'] == 'inv-r04d-final-flush'
    evidence.close()


def test_parent_scan_period_comes_from_verified_packet_config(monkeypatch):
    from mecanum_nav_bringup import local_training_launch_contract as contract
    from mecanum_nav_rl.runtime_simulation.b23_runner import packet_scan_period_ns

    seen = []
    document = {'training': {'local_training': {'lidar_rate_hz': 20}}}
    monkeypatch.setattr(contract, 'load_bound_config', lambda path: (
        seen.append(path) or document, 'config-pin', 'asset-pin', 'B2_SOAK_V1'))
    packet = {'resolved_config': '/pin/resolved.json', 'config_hash': 'config-pin',
        'asset_manifest_sha256': 'asset-pin'}
    assert packet_scan_period_ns(packet) == 50_000_000
    assert seen == [Path('/pin/resolved.json')]

    monkeypatch.setattr(contract, 'load_bound_config', lambda path: (
        document, 'wrong-config', 'asset-pin', 'B2_SOAK_V1'))
    with pytest.raises(ValueError, match='config/asset binding mismatch'):
        packet_scan_period_ns(packet)

    monkeypatch.setattr(contract, 'load_bound_config', lambda path: (
        {'training': {'local_training': {'lidar_rate_hz': 0}}},
        'config-pin', 'asset-pin', 'B2_SOAK_V1'))
    with pytest.raises(ValueError, match='LiDAR rate is invalid'):
        packet_scan_period_ns(packet)


def test_final_publisher_physics_lead_comes_from_verified_packet_config(monkeypatch):
    from mecanum_nav_bringup import local_training_launch_contract as contract
    from mecanum_nav_rl.runtime_simulation.b23_runner import packet_physics_step_ns

    seen = []
    document = {'training': {'local_training': {'physics_step_s': 0.01}}}
    monkeypatch.setattr(contract, 'load_bound_config', lambda path: (
        seen.append(path) or document, 'config-pin', 'asset-pin', 'B2_SOAK_V1'))
    packet = {'resolved_config': '/pin/resolved.json', 'config_hash': 'config-pin',
        'asset_manifest_sha256': 'asset-pin'}
    assert packet_physics_step_ns(packet) == 10_000_000
    assert seen == [Path('/pin/resolved.json')]

    monkeypatch.setattr(contract, 'load_bound_config', lambda path: (
        document, 'wrong-config', 'asset-pin', 'B2_SOAK_V1'))
    with pytest.raises(ValueError, match='config/asset binding mismatch'):
        packet_physics_step_ns(packet)

    monkeypatch.setattr(contract, 'load_bound_config', lambda path: (
        {'training': {'local_training': {'physics_step_s': 0.0100000001}}},
        'config-pin', 'asset-pin', 'B2_SOAK_V1'))
    with pytest.raises(ValueError, match='integral nanoseconds'):
        packet_physics_step_ns(packet)


def test_d04_soak_schedule_and_unit_budget_are_exact():
    from mecanum_nav_rl.runtime_simulation.b23_runner import soak_action, service_properties_for
    assert soak_action(0, 1) == (0., 0., 0.)
    assert soak_action(0, 5) == (0., 0., 0.)
    assert soak_action(0, 6) == (0.40, 0., 0.)
    assert soak_action(1, 25) == (-0.40, 0., 0.)
    assert soak_action(5, 6) == (0.30, -0.25, 0.30)
    assert soak_action(29, 26) == (0., 0., 0.)
    assert len([soak_action(i, step) for i in range(30)
        for step in range(1, (34 if i < 10 else 33)+1)]) == 1000
    assert 'RuntimeMaxSec=180s' in service_properties_for(120)
    assert 'RuntimeMaxSec=960s' in service_properties_for(900)
    with pytest.raises(ValueError, match='active runtime budget'):
        service_properties_for(180)


def _write_complete_soak_ledgers(root):
    for name in ('policy_adapter_issued.jsonl','policy_final_published.jsonl',
                 'policy_backend_applied.jsonl','b1_transition_committed.jsonl'):
        (root / name).write_text(''.join(json.dumps({'facts': {
            'transition_id': f'transition-{index}'}}) + '\n' for index in range(1000)))


def test_r08_unfinished_scheduled_slots_are_collection_cutoffs_and_continue(tmp_path, monkeypatch):
    import asyncio
    from mecanum_nav_rl.runtime_simulation.b23_runner import _run_b2_soak

    run_root = tmp_path / 'run'
    run_root.mkdir()
    _write_complete_soak_ledgers(run_root)
    events = []
    sink_state = {'synced':False}
    original_read_counts = runner_module._soak_ledger_counts

    def read_counts_after_sync(root):
        assert sink_state['synced'], 'soak ledgers read before evidence sink sync'
        return original_read_counts(root)

    monkeypatch.setattr(runner_module, '_soak_ledger_counts', read_counts_after_sync)

    class FakeIO:
        deadline_ns = 10**30
        descriptor = {'run_root':str(run_root)}

        def __init__(self):
            self.episode_index = -1
            self.step_index = 0
            self.resets = []
            self.actions = []

        async def reset_episode(self, _b1, *, seed, target, paused_hold_s):
            self.episode_index += 1
            self.step_index = 0
            self.resets.append((seed, target, paused_hold_s))

        async def policy_step(self, _b1, action):
            self.step_index += 1
            self.actions.append((self.episode_index, self.step_index, action))
            return NS(termination=NS(terminated=False, truncated=False))

    io = FakeIO()
    monkeypatch.setattr(runner_module.time, 'monotonic_ns', lambda: 0)
    class FakeSink:
        def record(self, name, facts):
            events.append((name, facts))

        def sync(self):
            sink_state['synced'] = True

    result = asyncio.run(_run_b2_soak(io, object(), {
        'reset_target':{'x_m':0.,'y_m':0.,'z_m':0.,'yaw_rad':0.},
        'episode_seeds':[2026102900 + index for index in range(30)],
        'run_root':str(run_root)}, FakeSink()))

    cutoffs = [facts for name, facts in events if name == 'COLLECTION_CUTOFF']
    assert len(io.resets) == 30
    assert len(io.actions) == 1000
    assert result['resets_confirmed'] == 30
    assert result['policy_steps_committed'] == 1000
    assert result['collection_cutoff'] is True
    assert result['collection_cutoff_records'] == cutoffs
    assert [item['episode_index'] for item in cutoffs] == list(range(30))
    assert all(item['episode_complete'] is False for item in cutoffs)
    assert cutoffs[0]['reason'] == 'scheduled_slot_unfinished'
    assert cutoffs[-1]['reason'] == 'final_slot_unfinished'


def test_r08_task_terminal_before_final_slot_still_fails_schedule(tmp_path, monkeypatch):
    import asyncio
    from mecanum_nav_rl.runtime_simulation.b23_runner import _run_b2_soak

    class FakeIO:
        deadline_ns = 10**30
        descriptor = {'run_root':str(tmp_path)}

        def __init__(self):
            self.episode_index = -1
            self.step_index = 0

        async def reset_episode(self, _b1, *, seed, target, paused_hold_s):
            self.episode_index += 1
            self.step_index = 0

        async def policy_step(self, _b1, _action):
            self.step_index += 1
            terminal = self.episode_index == 0 and self.step_index == 34
            return NS(termination=NS(terminated=terminal, truncated=False))

    monkeypatch.setattr(runner_module.time, 'monotonic_ns', lambda: 0)
    with pytest.raises(RuntimeError, match='terminal before final episode invalidates fixed schedule'):
        asyncio.run(_run_b2_soak(FakeIO(), object(), {
            'reset_target':{'x_m':0.,'y_m':0.,'z_m':0.,'yaw_rad':0.},
            'episode_seeds':[2026102900 + index for index in range(30)],
            'run_root':str(tmp_path)}, NS(record=lambda *_args: None)))


def test_r05_native_mask_poll_waits_for_event_file_and_complete_record(tmp_path):
    from mecanum_nav_rl.runtime_simulation.b23_runner import r05_contact_coverage_mask_event

    path = tmp_path / 'native-events.jsonl'
    assert r05_contact_coverage_mask_event(path) is None
    path.write_bytes(b'{"kind":"B23_CONTACT_COVERAGE_MASKED","fields":')
    assert r05_contact_coverage_mask_event(path) is None
    path.write_bytes(path.read_bytes() + b'{"masked":"1"}}\n')
    assert r05_contact_coverage_mask_event(path) == {
        'kind': 'B23_CONTACT_COVERAGE_MASKED', 'fields': {'masked': '1'}}
    path.write_bytes(b'{broken}\n')
    with pytest.raises(json.JSONDecodeError):
        r05_contact_coverage_mask_event(path)


def test_r05_wait_tolerates_exact_fault_status_until_zero_override_is_published():
    worker = object.__new__(TrainingWorkerIO)
    worker.stop_requested = False
    worker.abort_requested = None
    worker.pump_error = None
    worker.now = lambda: 100
    worker.ros_now = lambda: 50
    worker.deadline_ns = 200
    worker.last_clock_ns = 50
    worker.last_clock_advance_ns = 99
    worker.expected_paused = False
    worker.ingress = NS(fault=None,
        backend_state=NS(fault_flags=16, local_zero_override=False))

    worker.check(expected_native_fault_flags=16)
    worker.ingress.backend_state.local_zero_override = True
    worker.check(expected_native_fault_flags=16)
    with pytest.raises(RuntimeError, match='native fault flags=16'):
        worker.check(expected_native_fault_flags=None)
    worker.ingress.backend_state.fault_flags = 8
    with pytest.raises(RuntimeError, match='native fault flags=8'):
        worker.check(expected_native_fault_flags=16)


def test_worker_check_accepts_only_packet_pinned_fault_transition_set():
    worker = object.__new__(TrainingWorkerIO)
    worker.stop_requested = False
    worker.abort_requested = None
    worker.pump_error = None
    worker.now = lambda: 100
    worker.ros_now = lambda: 50
    worker.deadline_ns = 200
    worker.last_clock_ns = 50
    worker.last_clock_advance_ns = 99
    worker.expected_paused = False
    worker.ingress = NS(fault=None, backend_state=NS(fault_flags=1))

    worker.check(expected_native_fault_flags=(1, 7))
    worker.ingress.backend_state.fault_flags = 7
    worker.check(expected_native_fault_flags=(1, 7))
    worker.ingress.backend_state.fault_flags = 3
    with pytest.raises(RuntimeError, match='native fault flags=3'):
        worker.check(expected_native_fault_flags=(1, 7))


@pytest.mark.parametrize('case,terminal_extra', [
    ('R02c', 0), ('R02d', 0), ('R02d', 256)])
def test_r02_late_receipt_wait_tolerates_stale_intermediate_but_requires_exact_closed_zero(
        case, terminal_extra):
    from mecanum_nav_rl_interfaces.msg import SimulationContactState
    from mecanum_nav_rl.runtime_simulation.b23_runner import await_r02_late_receipt_close

    clock = {'steady_ns':100, 'pauses':0}
    state = NS(fault_flags=SimulationContactState.FAULT_COMMAND_STALE,
        local_zero_override=False)
    worker = object.__new__(TrainingWorkerIO)
    worker.stop_requested = False
    worker.abort_requested = None
    worker.pump_error = None
    worker.now = lambda: clock['steady_ns']
    worker.ros_now = lambda: 50
    worker.deadline_ns = 1_000
    worker.last_clock_ns = 50
    worker.last_clock_advance_ns = clock['steady_ns']
    worker.expected_paused = False
    worker.ingress = NS(fault=None, backend_state=state)
    release = {'observed':False}

    async def pause(_duration_s):
        clock['pauses'] += 1
        clock['steady_ns'] += 10
        if clock['pauses'] == 1:
            release['observed'] = True
        elif clock['pauses'] == 2 and terminal_extra:
            state.fault_flags = (SimulationContactState.FAULT_COMMAND_SEQUENCE
                | SimulationContactState.FAULT_COMMAND_STALE)
        elif clock['pauses'] == (3 if terminal_extra else 2):
            state.fault_flags = (SimulationContactState.FAULT_COMMAND_SEQUENCE
                | SimulationContactState.FAULT_COMMAND_STALE | terminal_extra)
            state.local_zero_override = True

    worker.pause = pause
    terminal_flags = (SimulationContactState.FAULT_COMMAND_SEQUENCE
        | SimulationContactState.FAULT_COMMAND_STALE)
    expected_terminal_flags = ((terminal_flags, terminal_flags | SimulationContactState.FAULT_QUEUE)
        if case == 'R02d' else (terminal_flags,))
    result = asyncio.run(await_r02_late_receipt_close(
        worker, release_predicate=lambda: release['observed'], deadline_ns=900,
        expected_terminal_fault_flags=expected_terminal_flags))

    assert result is state
    assert state.fault_flags == (SimulationContactState.FAULT_COMMAND_SEQUENCE
        | SimulationContactState.FAULT_COMMAND_STALE | terminal_extra)
    assert state.local_zero_override is True
    assert clock['pauses'] == (3 if terminal_extra else 2)


def test_r07c_owned_server_restart_scopes_expected_clock_stall():
    worker = object.__new__(TrainingWorkerIO)
    worker.stop_requested = False
    worker.abort_requested = None
    worker.pump_error = None
    worker.now = lambda: 1_500_000_001
    worker.ros_now = lambda: 10
    worker.deadline_ns = 10_000_000_000
    worker.last_clock_ns = 10
    worker.last_clock_advance_ns = 0
    worker.expected_paused = False
    worker._r07c_restart_clock_phase = 'restart_in_progress'
    worker._r07c_restart_clock_grace_deadline_ns = None
    worker._r07b_rollback_observed = None
    worker._r07b_rollback_pending_before_ns = None
    worker.ingress = NS(fault=None, backend_state=None)
    worker.emit = lambda *_: None

    worker.check()

    worker._r07c_restart_clock_phase = 'awaiting_clock'
    worker._r07c_restart_clock_grace_deadline_ns = 2_000_000_000
    worker.check()
    worker.now = lambda: 2_000_000_000
    with pytest.raises(RuntimeError, match='unexpected clock stall exceeded 1 s'):
        worker.check()


def test_r07c_clock_resume_restores_normal_one_second_stall_guard():
    worker = object.__new__(TrainingWorkerIO)
    worker.stop_requested = False
    worker.abort_requested = None
    worker.pump_error = None
    worker.now = lambda: 1_500_000_001
    worker.ros_now = lambda: 11
    worker.deadline_ns = 10_000_000_000
    worker.last_clock_ns = 10
    worker.last_clock_advance_ns = 0
    worker.expected_paused = False
    worker._r07c_restart_clock_phase = 'awaiting_clock'
    worker._r07c_restart_clock_grace_deadline_ns = 2_000_000_000
    worker._r07c_restart_started_ns = 1
    worker._r07b_rollback_observed = None
    worker._r07b_rollback_pending_before_ns = None
    worker.ingress = NS(fault=None, backend_state=None)
    events = []
    worker.emit = lambda name, facts: events.append((name, facts))

    worker.check()

    assert worker._r07c_restart_clock_phase == 'idle'
    assert worker._r07c_restart_clock_grace_deadline_ns is None
    assert events == [('B23_R07C_SIM_CLOCK_RESUMED_AFTER_BACKEND_RESTART', {
        'restart_started_ns':1,'clock_resumed_ns':1_500_000_001,'ros_time_ns':11})]
    worker.now = lambda: 2_500_000_002
    with pytest.raises(RuntimeError, match='unexpected clock stall exceeded 1 s'):
        worker.check()


def test_r07c_owned_server_restart_allows_one_clock_epoch_reset_only():
    worker = object.__new__(TrainingWorkerIO)
    worker.stop_requested = False
    worker.abort_requested = None
    worker.pump_error = None
    worker.now = lambda: 1_500_000_001
    worker.ros_now = lambda: 10
    worker.deadline_ns = 10_000_000_000
    worker.last_clock_ns = 20
    worker.last_clock_advance_ns = 0
    worker.expected_paused = False
    worker._r07c_restart_clock_phase = 'restart_in_progress'
    worker._r07c_restart_clock_grace_deadline_ns = None
    worker._r07c_restart_started_ns = 5
    worker._r07c_clock_rollback_observed = False
    worker._r07b_rollback_observed = None
    worker._r07b_rollback_pending_before_ns = None
    worker.ingress = NS(fault=None, backend_state=None)
    events = []
    worker.emit = lambda name, facts: events.append((name, facts))

    worker.check()

    assert worker.last_clock_ns == 10
    assert worker._r07c_clock_rollback_observed is True
    assert events[0] == ('B23_R07C_AUTHORIZED_CLOCK_EPOCH_RESET', {
        'previous_ros_ns':20,'current_ros_ns':10,'restart_started_ns':5,
        'observed_steady_ns':1_500_000_001})
    worker.ros_now = lambda: 9
    with pytest.raises(RuntimeError, match='more than one simulation clock rollback'):
        worker.check()


def test_r07c_restart_epoch_oracle_is_quarantined_before_ingress():
    from nav_msgs.msg import Odometry
    from rclpy.serialization import serialize_message
    worker = object.__new__(TrainingWorkerIO)
    worker.now = lambda: 100
    worker.emit = lambda name, facts: events.append((name, facts))
    worker._r07c_restart_started_ns = 50
    worker.descriptor = {'backend_instance_id':123}
    events = []
    delivered = []
    msg = Odometry()
    msg.header.stamp.sec = 0
    msg.header.stamp.nanosec = 7
    wire = serialize_message(msg)
    receive = worker.observed_callback(Odometry,
        '/mecanum/internal/ground_truth/odom', delivered.append)

    assert receive(wire, {}) is None
    assert delivered == []
    assert events[-1][0] == 'B23_R07C_RESTART_EPOCH_SAMPLE_QUARANTINED'
    assert events[-1][1]['topic'] == '/mecanum/internal/ground_truth/odom'
    assert events[-1][1]['source_stamp_ns'] == 7
    assert events[-1][1]['quarantined_before_ingress_validation'] is True


@pytest.mark.parametrize(('now_ns', 'period_ns', 'expected_ns'), [
    (891_000_000, 100_000_000, 900_000_000),
    (905_000_000, 100_000_000, 1_000_000_000),
    (1_099_000_000, 100_000_000, 1_100_000_000),
    (10, 16_000_000, 16_000_000),
])
def test_r02b_waits_for_next_scan_cutoff_before_binding(now_ns, period_ns, expected_ns):
    from mecanum_nav_rl.runtime_simulation.b23_runner import r02b_admission_release_target_ns

    assert r02b_admission_release_target_ns(now_ns, period_ns) == expected_ns
    with pytest.raises(ValueError, match='scan release phase'):
        r02b_admission_release_target_ns(now_ns, 0)


@pytest.mark.parametrize(('initial_ros_ns', 'target_cutoff_ns'), [
    (3_420_000_000, 3_500_000_000),
    # The exact boundary is closed: Safety defers a tick stamped at cutoff.
    (3_500_000_000, 3_500_000_000),
])
def test_policy_step_waits_for_applied_zero_after_cutoff_when_bind_window_is_too_short(
        initial_ros_ns, target_cutoff_ns, tmp_path, monkeypatch):
    from mecanum_nav_rl.core.issued_command_cutoff import (
        IssuedCommandReceiptView, ReceiptSource,
    )
    from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt

    worker = object.__new__(TrainingWorkerIO)
    clock = {'ros_ns':initial_ros_ns, 'steady_ns':50}
    status = NS(fault_flags=0, paused=False, local_zero_override=False,
        applied_receipt_valid=True, applied_final_publisher_instance_id=77,
        applied_final_publish_sequence=3, backend_instance_id=99,
        session_id='session', config_hash='a'*64,
        episode_generation=1, reset_epoch=2, runtime_generation=3)
    life = EpisodeLifecycleIdentity(1, 2, 3)
    def receipt(sequence, stamp):
        return IssuedCommandReceiptView(stamp,77,sequence,ReceiptSource.SAFE_STOP,
            88,sequence,0,'',life,'session','a'*64,(0.,0.,0.),sequence,'base_link',True)
    old = receipt(1,3_420_000_000)
    prior_window_same_phase = receipt(2,3_550_000_000)
    aligned = receipt(3,3_640_000_000)
    publications = {
        sequence:NS(final_publisher_instance_id=77,final_publish_sequence=sequence,
            source=FinalIssuedCommandReceipt.SOURCE_SAFE_STOP,
            final_command=NS(linear=NS(x=0.,y=0.),angular=NS(z=0.)))
    for sequence in (2,3)
    }
    native_path=tmp_path/'native-events.jsonl'
    applied_state = NS(fault_flags=0, paused=False, local_zero_override=False,
        applied_receipt_valid=True, applied_final_publisher_instance_id=77,
        applied_final_publish_sequence=3, backend_instance_id=99,
        session_id='session', config_hash='a'*64,
        episode_generation=1, reset_epoch=2, runtime_generation=3,
        applied_physics_iteration=365, applied_sim_stamp=NS(sec=3,nanosec=650_000_000))
    ingress = NS(receipts=[old], backend_state=status, lifecycle=life,
        application_for_receipt=lambda receipt: ({'state':applied_state,'received_ns':195}
            if receipt.final_publish_sequence == 3 else None),
        receipt_for_publication_sequence=lambda sequence: aligned if sequence == 3 else None)
    worker.ingress, worker.final = ingress, NS(publisher_instance_id=77,
        publication_for_source_sequence=lambda *,source,sequence: publications.get(sequence)
            if source == FinalIssuedCommandReceipt.SOURCE_SAFE_STOP else None)
    worker.descriptor={'session_id':'session','config_hash':'a'*64,'backend_instance_id':99,
        'native_events_path':str(native_path),'server_leader_pid':777,
        'invocation_id':'inv-1'}
    worker._native_offset, worker._native_partial = 0, b''
    worker._native_input_watermark = 0
    worker._native_safe_stop_ingress = {}
    worker.safety = NS(local_training=NS(scan_period_ns=100_000_000))
    worker.ros_now = lambda:clock['ros_ns']
    worker.now = lambda:clock['steady_ns']
    events=[]
    worker.emit=lambda name,facts:events.append((name,facts))
    waits=[]
    samples=[
        # Same modulo phase as the current clock, but one scan interval old.
        (3_650_000_000,100,prior_window_same_phase),
        (3_650_000_000,200,aligned),
    ]

    async def until(predicate, *, deadline_ns, phase):
        waits.append((deadline_ns,phase))
        if phase == 'post-cutoff native SAFE_STOP ingress with POLICY bind window':
            for stamp,steady,view in samples:
                clock.update(ros_ns=stamp,steady_ns=steady)
                ingress.receipts.append(view)
                fields={'publisher':'77','key':str(view.final_publish_sequence),
                    'source_sequence':str(view.source_sequence),'stamp_ns':str(view.publish_stamp_ns),
                    'receive_ns':str(steady+1)}
                with native_path.open('a') as stream:
                    stream.write(json.dumps({'kind':'B23_SAFE_STOP_RECEIPT_INGRESS',
                        'server_leader_pid':777,'invocation_id':'inv-1',
                        'fields':fields})+'\n')
                value=predicate()
                if value is not None:
                    return value
            raise AssertionError('eligible native-ingress receipt was not selected')
        assert phase == 'exact post-cutoff SAFE_STOP application in POLICY bind window'
        clock['steady_ns']=200
        return predicate()

    worker.until=until
    monkeypatch.setattr(runner_module, 'complete_jsonl_rows',
        lambda _path: pytest.fail('POLICY bind polling must not reparse the full native log'))
    witness={'receipt':old,'state':status,'received_ns':90}
    result=asyncio.run(worker.align_policy_step_launch_window(
        deadline_ns=2_000_000_000,zero_witness=witness))
    assert [phase for _,phase in waits] == [
        'post-cutoff native SAFE_STOP ingress with POLICY bind window',
        'exact post-cutoff SAFE_STOP application in POLICY bind window']
    assert result['receipt'] is aligned
    assert result['state'] is applied_state
    assert result['received_ns'] == 195
    assert [view.final_publish_sequence for view in ingress.receipts[-2:]] == [2,3]
    assert events[-2][0]=='POLICY_STEP_BIND_WINDOW_ALIGNED_AFTER_SCAN_CUTOFF'
    facts=events[-2][1]
    assert facts['target_cutoff_ns']==target_cutoff_ns
    assert facts['zero_publish_sequence']==3
    assert facts['zero_publish_stamp_ns']==3_640_000_000
    assert facts['native_receive_ns']==201
    assert facts['remaining_to_cutoff_ns']==50_000_000
    assert facts['prior_applied_zero_sequence']==1
    assert facts['remaining_to_next_cutoff_ns']==50_000_000
    assert facts['receipt_scan_window']==36
    assert facts['current_scan_window']==36
    assert facts['steady_ns']==200
    assert events[-1][0]=='POLICY_STEP_BIND_WINDOW_ZERO_APPLIED'
    assert worker._native_offset == native_path.stat().st_size
    assert worker._native_safe_stop_ingress[
        ('77','3','3','3640000000')]['fields']['receive_ns'] == '201'


def test_policy_step_keeps_current_zero_witness_when_measured_launch_window_is_open():
    worker=object.__new__(TrainingWorkerIO)
    worker.ros_now=lambda:3_340_000_000
    worker.safety=NS(local_training=NS(scan_period_ns=100_000_000))
    worker.ingress=NS(receipts=[])
    witness={'bound':'actual zero witness'}
    async def unexpected_wait(*args,**kwargs):
        raise AssertionError('a full scan period remains; no alignment wait is needed')
    worker.until=unexpected_wait
    assert asyncio.run(worker.align_policy_step_launch_window(
        deadline_ns=2_000_000_000,zero_witness=witness)) is witness


def test_policy_bind_realigns_after_exact_zero_application_is_observed_late(
        tmp_path):
    from mecanum_nav_rl.core.issued_command_cutoff import (
        IssuedCommandReceiptView, ReceiptSource,
    )
    from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt

    worker=object.__new__(TrainingWorkerIO)
    clock={'ros_ns':3_420_000_000,'steady_ns':100}
    life=EpisodeLifecycleIdentity(1,2,3)
    def receipt(sequence,stamp):
        return IssuedCommandReceiptView(stamp,77,sequence,ReceiptSource.SAFE_STOP,
            88,sequence,0,'',life,'session','a'*64,(0.,0.,0.),sequence,'base_link',True)
    old,first,second=receipt(1,3_420_000_000),receipt(2,3_540_000_000),receipt(3,3_640_000_000)
    def state(sequence,stamp,iteration):
        return NS(fault_flags=0,paused=False,local_zero_override=False,
            applied_receipt_valid=True,applied_final_publisher_instance_id=77,
            applied_final_publish_sequence=sequence,backend_instance_id=99,
            session_id='session',config_hash='a'*64,episode_generation=1,
            reset_epoch=2,runtime_generation=3,applied_physics_iteration=iteration,
            applied_sim_stamp=NS(sec=stamp//1_000_000_000,
                nanosec=stamp%1_000_000_000),physics_iteration=iteration)
    first_state=state(2,3_550_000_000,355)
    second_state=state(3,3_650_000_000,365)
    applications={
        2:{'state':first_state,'received_ns':250},
        3:{'state':second_state,'received_ns':550},
    }
    publications={sequence:NS(final_publisher_instance_id=77,
        final_publish_sequence=sequence,source=FinalIssuedCommandReceipt.SOURCE_SAFE_STOP,
        final_command=NS(linear=NS(x=0.,y=0.),angular=NS(z=0.))) for sequence in (2,3)}
    ingress=NS(receipts=[old],backend_state=first_state,lifecycle=life,
        application_for_receipt=lambda view:applications.get(view.final_publish_sequence),
        receipt_for_publication_sequence=lambda sequence:{2:first,3:second}.get(sequence))
    worker.ingress=ingress
    worker.final=NS(publisher_instance_id=77,
        publication_for_source_sequence=lambda *,source,sequence:publications.get(sequence)
            if source==FinalIssuedCommandReceipt.SOURCE_SAFE_STOP else None)
    native_path=tmp_path/'native-events.jsonl'
    worker.descriptor={'session_id':'session','config_hash':'a'*64,
        'backend_instance_id':99,'native_events_path':str(native_path),
        'server_leader_pid':777,'invocation_id':'inv-1'}
    worker._native_offset=0; worker._native_partial=b''
    worker._native_input_watermark=0; worker._native_safe_stop_ingress={}
    worker.safety=NS(local_training=NS(scan_period_ns=100_000_000))
    worker.ros_now=lambda:clock['ros_ns']; worker.now=lambda:clock['steady_ns']
    events=[]; worker.emit=lambda name,facts:events.append((name,facts))
    waits=[]; deadline=2_000_000_000

    def write_native(view,receive_ns):
        row={'kind':'B23_SAFE_STOP_RECEIPT_INGRESS','server_leader_pid':777,
            'invocation_id':'inv-1','fields':{'publisher':'77',
                'key':str(view.final_publish_sequence),
                'source_sequence':str(view.source_sequence),
                'stamp_ns':str(view.publish_stamp_ns),'receive_ns':str(receive_ns)}}
        with native_path.open('ab') as stream:
            stream.write((json.dumps(row)+'\n').encode())

    async def until(predicate,*,deadline_ns,phase):
        waits.append((deadline_ns,phase))
        assert deadline_ns==deadline
        if phase=='post-cutoff native SAFE_STOP ingress with POLICY bind window':
            if len(waits)==1:
                clock.update(ros_ns=3_540_000_000,steady_ns=200)
                ingress.receipts.append(first); ingress.backend_state=first_state
                write_native(first,201)
            else:
                assert len(waits)==3
                clock.update(ros_ns=3_640_000_000,steady_ns=500)
                ingress.receipts.append(second); ingress.backend_state=second_state
                write_native(second,501)
            value=predicate()
            assert value is not None
            return value
        assert phase=='exact post-cutoff SAFE_STOP application in POLICY bind window'
        if len(waits)==2:
            # Exact receipt 2 was applied at 3.55 s, but the worker observes
            # the application at 3.57 s, outside the unchanged 40-60 ms band.
            clock.update(ros_ns=3_570_000_000,steady_ns=300)
            return predicate()
        assert len(waits)==4
        clock.update(ros_ns=3_650_000_000,steady_ns=600)
        return predicate()

    worker.until=until
    witness={'receipt':old,'state':state(1,3_420_000_000,342),'received_ns':90}
    result=asyncio.run(worker.align_policy_step_launch_window(
        deadline_ns=deadline,zero_witness=witness))
    assert result['receipt'] is second
    assert result['state'] is second_state
    assert result['received_ns']==550
    assert [phase for _,phase in waits]==[
        'post-cutoff native SAFE_STOP ingress with POLICY bind window',
        'exact post-cutoff SAFE_STOP application in POLICY bind window',
        'post-cutoff native SAFE_STOP ingress with POLICY bind window',
        'exact post-cutoff SAFE_STOP application in POLICY bind window']
    assert all(bound==deadline for bound,_ in waits)
    assert [name for name,_ in events]==[
        'POLICY_STEP_BIND_WINDOW_ALIGNED_AFTER_SCAN_CUTOFF',
        'POLICY_STEP_BIND_WINDOW_APPLICATION_OBSERVED_LATE',
        'POLICY_STEP_BIND_WINDOW_ALIGNED_AFTER_SCAN_CUTOFF',
        'POLICY_STEP_BIND_WINDOW_ZERO_APPLIED']
    assert events[1][1]['remaining_to_cutoff_ns']==30_000_000
    assert events[1][1]['final_publish_sequence']==2
    assert events[3][1]['remaining_to_cutoff_ns']==50_000_000
    assert events[3][1]['final_publish_sequence']==3
    assert worker._native_safe_stop_ingress[('77','2','2','3540000000')]['fields']['receive_ns']=='201'
    assert worker._native_safe_stop_ingress[('77','3','3','3640000000')]['fields']['receive_ns']=='501'


def test_prebind_zero_refresh_requires_new_identity_bound_native_application():
    from mecanum_nav_rl.core.issued_command_cutoff import IssuedCommandReceiptView, ReceiptSource
    from mecanum_nav_rl_interfaces.msg import CommandEnvelope
    value=object.__new__(TrainingWorkerIO)
    value.now=lambda:1_000_000_000
    life=NS(episode_generation=2, reset_epoch=3, runtime_generation=4)
    from mecanum_nav_rl.runtime_simulation.local_training_ingress import lifecycle_identity
    identity=lifecycle_identity(life)
    receipt=IssuedCommandReceiptView(publish_stamp_ns=900,
        final_publisher_instance_id=77, final_publish_sequence=101,
        source=ReceiptSource.SAFE_STOP, source_instance_id=88,
        source_sequence=12, step_index=0, transition_id='', lifecycle=identity,
        session_id='session-a', ingress_config_hash='a'*64,
        final_command=(0.0,0.0,0.0), received_steady_ns=990_000_000,
        frame_id='base_link', admission_valid=True)
    state=NS(session_id='session-a', config_hash='a'*64, backend_instance_id=99,
        episode_generation=2, reset_epoch=3, runtime_generation=4,
        fault_flags=0, paused=False, local_zero_override=False,
        applied_receipt_valid=True, applied_final_publisher_instance_id=77,
        applied_final_publish_sequence=101, applied_physics_iteration=12,
        applied_sim_stamp=NS(sec=0,nanosec=900), physics_iteration=12)
    publication=NS(final_publisher_instance_id=77, final_publish_sequence=101,
        source=CommandEnvelope.SOURCE_SAFE_STOP, sequence=12,
        final_command=NS(linear=NS(x=0.0,y=0.0,z=0.0),
            angular=NS(x=0.0,y=0.0,z=0.0)))
    value.safety=NS(local_training=NS(safe_stop_sequence=11))
    value.ingress=NS(lifecycle=life, safe_stop_source_id=88, receipts=[receipt],
        backend_state=state, application_for_receipt=lambda _receipt:{'state':state,'received_ns':990_000_000},
        receipt_for_publication_sequence=lambda seq:receipt if seq==101 else None)
    value.final=NS(publisher_instance_id=77,
        publication_for_source_sequence=lambda *,source,sequence:
            publication if source==CommandEnvelope.SOURCE_SAFE_STOP and sequence==12 else None)
    value.descriptor={'session_id':'session-a','config_hash':'a'*64,'backend_instance_id':99}
    events=[]
    value.emit=lambda name,facts:events.append((name,facts))
    async def until(predicate, *, deadline_ns, phase):
        assert phase=='new exact SAFE_STOP application before pending POLICY bind'
        result=predicate()
        assert result is not None
        return result
    value.until=until

    result=asyncio.run(value.refresh_zero_before_pending_bind(deadline_ns=2_000_000_000))
    assert result['receipt'] is receipt
    assert result['application']['state'] is state
    assert result['age_ns']==10_000_000
    assert events[-1][0]=='POLICY_STEP_BIND_ZERO_REFRESH_APPLIED'
    assert events[-1][1]['source_sequence']==12
    assert events[-1][1]['final_publish_sequence']==101
    reused=asyncio.run(value.refresh_zero_before_pending_bind(
        deadline_ns=2_000_000_000,zero_witness=result))
    assert reused['receipt'] is receipt
    assert reused['age_ns']==10_000_000
    assert events[-1][1]['reused_exact_scan_window_application'] is True


def test_prebind_zero_refresh_normalizes_exact_generated_receipt_to_ingress_view():
    from mecanum_nav_rl.core.issued_command_cutoff import IssuedCommandReceiptView, ReceiptSource
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
    from mecanum_nav_rl.runtime_simulation.local_training_ingress import lifecycle_identity

    value=object.__new__(TrainingWorkerIO)
    value.now=lambda:1_000_000_000
    life=NS(episode_generation=2, reset_epoch=3, runtime_generation=4)
    identity=lifecycle_identity(life)
    retained=IssuedCommandReceiptView(publish_stamp_ns=900,
        final_publisher_instance_id=77, final_publish_sequence=101,
        source=ReceiptSource.SAFE_STOP, source_instance_id=88,
        source_sequence=12, step_index=0, transition_id='', lifecycle=identity,
        session_id='session-a', ingress_config_hash='a'*64,
        final_command=(0.0,0.0,0.0), received_steady_ns=990_000_000,
        frame_id='base_link', admission_valid=True)
    generated=FinalIssuedCommandReceipt()
    generated.header.frame_id='base_link'
    generated.header.stamp.sec=0
    generated.header.stamp.nanosec=900
    generated.episode_generation=2
    generated.reset_epoch=3
    generated.runtime_generation=4
    generated.step_index=0
    generated.transition_id=''
    generated.source=FinalIssuedCommandReceipt.SOURCE_SAFE_STOP
    generated.sequence=12
    generated.source_instance_id=88
    generated.final_publisher_instance_id=77
    generated.final_publish_sequence=101
    state=NS(session_id='session-a', config_hash='a'*64, backend_instance_id=99,
        episode_generation=2, reset_epoch=3, runtime_generation=4,
        fault_flags=0, paused=False, local_zero_override=False,
        applied_receipt_valid=True, applied_final_publisher_instance_id=77,
        applied_final_publish_sequence=101, applied_physics_iteration=12,
        applied_sim_stamp=NS(sec=0,nanosec=900))
    latest=NS(session_id='session-a', config_hash='a'*64, backend_instance_id=99,
        episode_generation=2, reset_epoch=3, runtime_generation=4,
        fault_flags=0, paused=False, local_zero_override=False,
        applied_receipt_valid=False, applied_final_publisher_instance_id=0,
        applied_final_publish_sequence=0, applied_physics_iteration=0,
        applied_sim_stamp=NS(sec=0,nanosec=0), physics_iteration=13)
    value.safety=NS(local_training=NS(safe_stop_sequence=11))
    value.ingress=NS(lifecycle=life, safe_stop_source_id=88,
        backend_state=latest,
        receipt_for_publication_sequence=lambda seq:retained if seq==101 else None)
    value.final=NS(publisher_instance_id=77)
    value.descriptor={'session_id':'session-a','config_hash':'a'*64,
        'backend_instance_id':99}
    events=[]
    value.emit=lambda name,facts:events.append((name,facts))
    async def until(predicate, *, deadline_ns, phase):
        assert phase=='new exact SAFE_STOP application before pending POLICY bind'
        result=predicate()
        assert result is not None
        return result
    value.until=until

    result=asyncio.run(value.refresh_zero_before_pending_bind(deadline_ns=2_000_000_000,
        zero_witness={'receipt':generated,'state':state,'received_ns':990_000_000,
            'application':{'state':state,'received_ns':990_000_000}}))
    assert result['receipt'] is retained
    assert result['application']['state'] is state
    assert result['age_ns']==10_000_000
    assert events[-1][0]=='POLICY_STEP_BIND_ZERO_REFRESH_APPLIED'
    assert events[-1][1]['source_sequence']==12
    assert events[-1][1]['final_publish_sequence']==101
    assert events[-1][1]['reused_exact_scan_window_application'] is True

    newer_policy=IssuedCommandReceiptView(publish_stamp_ns=1_000,
        final_publisher_instance_id=77, final_publish_sequence=102,
        source=ReceiptSource.POLICY, source_instance_id=90,
        source_sequence=1, step_index=1, transition_id='step-1', lifecycle=identity,
        session_id='session-a', ingress_config_hash='a'*64,
        final_command=(0.1,0.0,0.0), received_steady_ns=995_000_000,
        frame_id='base_link', admission_valid=True)
    latest.applied_receipt_valid=True
    latest.applied_final_publisher_instance_id=77
    latest.applied_final_publish_sequence=102
    latest.applied_physics_iteration=14
    latest.applied_sim_stamp=NS(sec=0,nanosec=1_000)
    value.ingress.receipt_for_publication_sequence=lambda seq: {
        101:retained,102:newer_policy}.get(seq)
    with pytest.raises(RuntimeError,match='not a SAFE_STOP zero'):
        asyncio.run(value.refresh_zero_before_pending_bind(deadline_ns=2_000_000_000,
            zero_witness={'receipt':generated,'state':state,'received_ns':990_000_000,
                'application':{'state':state,'received_ns':990_000_000}}))


def test_prebind_zero_override_waits_for_new_exact_safe_stop_application():
    import asyncio
    from mecanum_nav_rl.core.issued_command_cutoff import IssuedCommandReceiptView, ReceiptSource
    from mecanum_nav_rl_interfaces.msg import CommandEnvelope
    from mecanum_nav_rl.runtime_simulation.b23_runner import TrainingWorkerIO
    from mecanum_nav_rl.runtime_simulation.local_training_ingress import lifecycle_identity

    value=object.__new__(TrainingWorkerIO)
    value.now=lambda:1_010_000_000
    life=NS(episode_generation=2, reset_epoch=3, runtime_generation=4)
    identity=lifecycle_identity(life)
    def receipt(pub, source_seq):
        return IssuedCommandReceiptView(publish_stamp_ns=1_000+pub,
            final_publisher_instance_id=77, final_publish_sequence=pub,
            source=ReceiptSource.SAFE_STOP, source_instance_id=88,
            source_sequence=source_seq, step_index=0, transition_id='', lifecycle=identity,
            session_id='session-a', ingress_config_hash='a'*64,
            final_command=(0.0,0.0,0.0), received_steady_ns=1_000_000_000+pub,
            frame_id='base_link', admission_valid=True)
    old=receipt(101,12)
    fresh=receipt(102,13)
    old_state=NS(session_id='session-a',config_hash='a'*64,backend_instance_id=99,
        episode_generation=2,reset_epoch=3,runtime_generation=4,fault_flags=0,
        paused=False,local_zero_override=False,applied_final_publisher_instance_id=77,
        applied_final_publish_sequence=101,applied_physics_iteration=12,
        applied_sim_stamp=NS(sec=1,nanosec=101))
    invalidated=NS(session_id='session-a',config_hash='a'*64,backend_instance_id=99,
        episode_generation=2,reset_epoch=3,runtime_generation=4,fault_flags=0,
        paused=False,local_zero_override=True,applied_receipt_valid=False,
        applied_final_publisher_instance_id=0,applied_final_publish_sequence=0,
        applied_physics_iteration=0,applied_sim_stamp=NS(sec=0,nanosec=0),
        physics_iteration=13)
    fresh_state=NS(session_id='session-a',config_hash='a'*64,backend_instance_id=99,
        episode_generation=2,reset_epoch=3,runtime_generation=4,fault_flags=0,
        paused=False,local_zero_override=False,applied_receipt_valid=True,
        applied_final_publisher_instance_id=77,applied_final_publish_sequence=102,
        applied_physics_iteration=14,applied_sim_stamp=NS(sec=1,nanosec=102),
        physics_iteration=14)
    publication=NS(final_publisher_instance_id=77,final_publish_sequence=102,
        source=CommandEnvelope.SOURCE_SAFE_STOP,sequence=13,
        final_command=NS(linear=NS(x=0.0,y=0.0,z=0.0),
            angular=NS(x=0.0,y=0.0,z=0.0)))
    values={101:old,102:fresh}
    value.safety=NS(local_training=NS(safe_stop_sequence=12))
    value.ingress=NS(lifecycle=life,safe_stop_source_id=88,backend_state=invalidated,
        receipts=[old,fresh],
        receipt_for_publication_sequence=lambda seq:values.get(seq),
        application_for_receipt=lambda current:{'state':fresh_state,'received_ns':1_005_000_000}
            if current is fresh else None)
    value.final=NS(publisher_instance_id=77,
        publication_for_source_sequence=lambda *,source,sequence:publication
            if source==CommandEnvelope.SOURCE_SAFE_STOP and sequence==13 else None)
    value.descriptor={'session_id':'session-a','config_hash':'a'*64,'backend_instance_id':99}
    events=[]; waits=[]
    value.emit=lambda name,facts:events.append((name,facts))
    async def until(predicate, *, deadline_ns, phase):
        waits.append((deadline_ns,phase))
        assert phase=='new exact SAFE_STOP application before pending POLICY bind'
        value.ingress.backend_state=fresh_state
        result=predicate()
        assert result is not None
        return result
    value.until=until

    result=asyncio.run(value.refresh_zero_before_pending_bind(deadline_ns=2_000_000_000,
        zero_witness={'receipt':old,'state':old_state,'received_ns':1_000_000_000,
            'application':{'state':old_state,'received_ns':1_000_000_000}}))

    assert len(waits)==1 and waits[0][1]=='new exact SAFE_STOP application before pending POLICY bind'
    assert result['receipt'] is fresh
    assert result['state'] is fresh_state
    assert result['received_ns']==fresh.received_steady_ns
    assert result['age_ns']==value.now()-fresh.received_steady_ns
    assert events[0][0]=='POLICY_STEP_BIND_ZERO_WITNESS_INVALIDATED'
    assert events[0][1]['reason']=='latest_native_local_zero_override'
    assert events[-1][0]=='POLICY_STEP_BIND_ZERO_REFRESH_APPLIED'
    assert events[-1][1]['source_sequence']==13
    assert events[-1][1]['final_publish_sequence']==102
    assert 'reused_exact_scan_window_application' not in events[-1][1]


def test_prebind_zero_refresh_rejects_stale_or_mismatched_evidence():
    from mecanum_nav_rl.core.issued_command_cutoff import IssuedCommandReceiptView, ReceiptSource
    from mecanum_nav_rl_interfaces.msg import CommandEnvelope
    value=object.__new__(TrainingWorkerIO)
    value.now=lambda:1_000_000_000
    life=NS(episode_generation=2, reset_epoch=3, runtime_generation=4)
    from mecanum_nav_rl.runtime_simulation.local_training_ingress import lifecycle_identity
    identity=lifecycle_identity(life)
    receipt=IssuedCommandReceiptView(publish_stamp_ns=900,
        final_publisher_instance_id=77, final_publish_sequence=101,
        source=ReceiptSource.SAFE_STOP, source_instance_id=88,
        source_sequence=12, step_index=0, transition_id='', lifecycle=identity,
        session_id='wrong-session', ingress_config_hash='a'*64,
        final_command=(0.0,0.0,0.0), received_steady_ns=880_000_000,
        frame_id='base_link', admission_valid=True)
    state=NS(session_id='session-a', config_hash='a'*64, backend_instance_id=99,
        episode_generation=2, reset_epoch=3, runtime_generation=4,
        fault_flags=0, paused=False, local_zero_override=False,
        applied_receipt_valid=True, applied_final_publisher_instance_id=77,
        applied_final_publish_sequence=101, applied_physics_iteration=12,
        applied_sim_stamp=NS(sec=0,nanosec=900))
    publication=NS(final_publisher_instance_id=77, final_publish_sequence=101,
        source=CommandEnvelope.SOURCE_SAFE_STOP, sequence=12,
        final_command=NS(linear=NS(x=0.0,y=0.0,z=0.0),
            angular=NS(x=0.0,y=0.0,z=0.0)))
    value.safety=NS(local_training=NS(safe_stop_sequence=11))
    value.ingress=NS(lifecycle=life, safe_stop_source_id=88, receipts=[receipt],
        backend_state=state, application_for_receipt=lambda _receipt:{'state':state,'received_ns':880_000_000},
        receipt_for_publication_sequence=lambda seq:receipt if seq==101 else None)
    value.final=NS(publisher_instance_id=77,
        publication_for_source_sequence=lambda *,source,sequence:
            publication if source==CommandEnvelope.SOURCE_SAFE_STOP and sequence==12 else None)
    value.descriptor={'session_id':'session-a','config_hash':'a'*64,'backend_instance_id':99}
    value.emit=lambda *_args:None
    async def until(predicate, *, deadline_ns, phase):
        assert predicate() is None
        raise TimeoutError('expected stale or mismatched pre-bind zero to remain ineligible')
    value.until=until

    with pytest.raises(TimeoutError,match='remain ineligible'):
        asyncio.run(value.refresh_zero_before_pending_bind(deadline_ns=2_000_000_000))


def test_case_hook_and_assessment_are_bound_to_packet_case():
    assert case_fault_hooks('R01a') == []
    assert case_fault_hooks('R01b') == ['external_pause_after_w1_before_native_dispatch']
    assert case_fault_hooks('R01c') == ['delay_native_pause_ack_1500ms_once']
    assert case_fault_hooks('R01d') == ['drop_native_pause_ack_once']
    assert case_fault_hooks('R01e') == ['pause_request_replay_after_terminal']
    assert case_fault_hooks('R02a') == []
    assert case_fault_hooks('R02b') == ['native_hold_admission_until_receipt']
    assert case_fault_hooks('R02c') == ['hold_policy_receipt_until_safe_stop']
    assert case_fault_hooks('R02d') == ['hold_policy_receipt_until_admission_inhibited']
    assert case_fault_hooks('R02e') == ['pre_bind_admission_sample']
    assert case_fault_hooks('R02f') == ['safety_hold_after_adapter_issuance']
    assert case_fault_hooks('R02g') == ['closing_paths_after_policy_nonzero']
    assert case_fault_hooks('R03a') == ['drop_native_policy_receipt_once']
    assert case_fault_hooks('R03b') == ['mutate_native_policy_transition_id_once']
    assert case_fault_hooks('R04a') == ['delay_noisy_odometry_delivery_300ms_once']
    assert case_fault_hooks('R04b') == ['drop_policy_noisy_odometry_delivery']
    assert case_fault_hooks('R04c') == ['delay_scan_delivery_650ms_once']
    assert case_fault_hooks('R04d') == ['delay_lifecycle_delivery_650ms_once']
    assert case_fault_hooks('R05') == ['mask_contact_coverage_after_verified']
    assert case_fault_hooks('R06a') == ['set_pose_ack_with_wrong_target']
    assert case_fault_hooks('R06b') == ['omit_one_settle_physics_iteration']
    assert case_fault_hooks('R06c') == ['hold_observation0_adjacent_receipt_until_reset_deadline']
    assert case_fault_hooks('R07a') == ['unexpected_pause_during_active_session']
    assert case_fault_hooks('R07b') == ['time_only_rollback_after_contact_proof']
    assert case_fault_hooks('R09a') == []
    assert case_fault_hooks('R09b') == []
    from mecanum_nav_rl.runtime_simulation.b23_runner import CASE_SCENARIOS
    assert CASE_SCENARIOS['R09a'] == ('sim_train_local_training_goal_settle.resolved.json', 'B2_GOAL_SETTLE_V1.json')
    assert CASE_SCENARIOS['R09b'] == ('sim_train_local_training_contact.resolved.json', 'B2_CONTACT_V1.json')
    assert case_environment('R02b',case_fault_hooks('R02b')) == {
        'B23_ADMISSION_ORDER_FAULT':'receipt_before_admission'}
    assert case_environment('R02c', case_fault_hooks('R02c')) == {
        'B23_RECEIPT_FAULT':'hold_policy_until_safe_stop'}
    assert case_environment('R02d', case_fault_hooks('R02d')) == {
        'B23_RECEIPT_FAULT':'hold_policy_until_inhibit'}
    assert case_environment('R01c', case_fault_hooks('R01c')) == {
        'B23_PAUSE_ACK_FAULT':'delay_1500ms_once'}
    assert case_environment('R01d', case_fault_hooks('R01d')) == {
        'B23_PAUSE_ACK_FAULT':'drop_once'}
    assert case_environment('R03a', case_fault_hooks('R03a')) == {
        'B23_RECEIPT_FAULT':'drop_policy_once'}
    assert case_environment('R03b', case_fault_hooks('R03b')) == {
        'B23_RECEIPT_FAULT':'mutate_policy_transition_id_once'}
    assert case_environment('R05', case_fault_hooks('R05')) == {
        'B23_CONTACT_COVERAGE_FAULT':'mask_coverage_after_verified'}
    assert case_environment('R01a', []) == {}
    with pytest.raises(ValueError, match='not approved for campaign case'):
        case_fault_hooks('R01a', 'pause_request_replay_after_terminal')
    assert technical_outcome('R01a', True) == 'R01a_COMPLETED'
    assert technical_outcome('R09a', True) == 'R09a_COMPLETED'
    assert technical_outcome('R01e', True) == 'R01e_COMPLETED'
    assert technical_outcome('R01e', False) == 'INCOMPLETE'


def test_r09_task_verifiers_require_b1_goal_and_contact_facts():
    from mecanum_nav_rl.termination.manager import TerminationReason
    transition_id = NS(transition_id='transition-1')
    goal = NS(termination=NS(terminated=True, reason=TerminationReason.GOAL),
        goal_settle_result=NS(healthy=True, success=True, distance_m=0.0),
        command_history=(0.,0.,0.), transition_identity=transition_id)
    assert verify_r09a_goal_settle(goal) == {'goal_settled':True,
        'goal_distance_m':0.0,'zero_command':True,'transition_id':'transition-1'}
    with pytest.raises(RuntimeError, match='healthy zero-command B1 goal settle'):
        verify_r09a_goal_settle(NS(**{**vars(goal), 'command_history':(0.1,0.,0.)}))
    contact = NS(termination=NS(terminated=True, reason=TerminationReason.COLLISION),
        transition_identity=transition_id)
    state = NS(source_healthy=True, contact_active=True, collision_pulse_pending=False,
        consumed_transition_ids=('transition-1',))
    assert verify_r09b_task_contact(contact, state) == {
        'task_contact_committed':True,'contact_active_at_commit':True,
        'contact_pulse_consumed_by_b1':True,'transition_id':'transition-1'}
    with pytest.raises(RuntimeError, match='B1-committed task contact terminal'):
        verify_r09b_task_contact(contact, NS(source_healthy=True,
            contact_active=False,collision_pulse_pending=False,consumed_transition_ids=()))


def test_r09b_task_fixture_is_exact_and_pinned_to_existing_world_model():
    from mecanum_nav_rl.runtime_simulation.b23_runner import (
        R09B_TASK_FIXTURE, validate_r09b_task_fixture,
    )
    assert validate_r09b_task_fixture(dict(R09B_TASK_FIXTURE)) == R09B_TASK_FIXTURE
    changed = dict(R09B_TASK_FIXTURE)
    changed['contact_pose'] = {**changed['contact_pose'], 'x_m': 0.4}
    with pytest.raises(ValueError, match='approved packet'):
        validate_r09b_task_fixture(changed)


def test_runtime_packet_ament_prefix_places_exact_install_before_underlays(tmp_path):
    import os
    from mecanum_nav_rl.runtime_simulation.b23_runner import bind_install_ament_prefix
    install = tmp_path/'install'; install.mkdir()
    other = tmp_path/'other'; other.mkdir()
    bound = bind_install_ament_prefix(
        {'AMENT_PREFIX_PATH':os.pathsep.join((str(other), str(install), '/opt/ros/jazzy')),
         'PYTHONPATH':'kept'}, install)
    assert bound['AMENT_PREFIX_PATH'].split(os.pathsep) == [
        str(install.resolve()), str(other), '/opt/ros/jazzy']
    assert bound['PYTHONPATH'] == 'kept'


@pytest.mark.parametrize('source_name', ['policy', 'safe_stop'])
def test_r09b_fixture_set_pose_uses_zero_bound_robot_and_exact_entity(source_name):
    import asyncio
    from mecanum_nav_rl.runtime_simulation.b23_runner import (
        R09B_TASK_FIXTURE, TrainingWorkerIO,
    )
    from mecanum_nav_rl_interfaces.msg import (
        FinalIssuedCommandReceipt, SimulationContactState,
    )
    from ros_gz_interfaces.msg import Entity
    from ros_gz_interfaces.srv import SetEntityPose

    io = object.__new__(TrainingWorkerIO)
    io.descriptor = {'task_fixture':dict(R09B_TASK_FIXTURE),
        'backend_instance_id':12,'session_id':'session-1','config_hash':'c'*64}
    io.final = NS(publisher_instance_id=34)
    io.ingress = NS(backend_state=SimulationContactState())
    state = io.ingress.backend_state
    state.backend_instance_id=12; state.session_id='session-1'; state.config_hash='c'*64
    state.applied_receipt_valid=True; state.applied_final_publisher_instance_id=34
    state.applied_final_publish_sequence=88; state.fault_flags=0; state.paused=False
    state.actuator_inhibited=False; state.local_zero_override=False
    receipt = FinalIssuedCommandReceipt()
    receipt.final_publisher_instance_id=34; receipt.final_publish_sequence=88
    receipt.source=(FinalIssuedCommandReceipt.SOURCE_POLICY if source_name == 'policy'
        else FinalIssuedCommandReceipt.SOURCE_SAFE_STOP)
    receipt.final_command.linear.x=receipt.final_command.linear.y=0.0
    receipt.final_command.angular.z=0.0
    io.pose_type=SetEntityPose; io.pose_client=object(); io.now=lambda:100
    emitted=[]; calls=[]
    io.emit=lambda event,facts: emitted.append((event,facts))
    async def call(client,request,**kwargs):
        calls.append((client,request,kwargs))
        response=SetEntityPose.Response(); response.success=True
        return response
    io.call=call
    asyncio.run(io.set_r09b_task_fixture_pose(
        pose_name='contact_pose',deadline_ns=1_000_000_000,zero_receipt=receipt))
    assert len(calls)==1
    req=calls[0][1]
    assert req.entity.name=='obstacle_0'
    assert req.entity.type==Entity.MODEL
    assert (req.pose.position.x,req.pose.position.y,req.pose.position.z)==(.27,0.,.5)
    assert req.pose.position.x-.1 < .2  # fixture overlaps the base front edge
    assert req.pose.position.x-.1-(-.031765) > .1  # lidar return is outside range_min
    assert any(name=='R09B_FIXTURE_POSE_APPLIED' for name,_ in emitted)
    receipt.final_command.linear.x=.01
    with pytest.raises(RuntimeError,match='bound zero final command'):
        asyncio.run(io.set_r09b_task_fixture_pose(
            pose_name='initial_pose',deadline_ns=1_000_000_000,zero_receipt=receipt))
    assert len(calls)==1


def test_r09b_contact_pulse_is_captured_and_fixture_cleared_before_cutoff():
    import asyncio
    from mecanum_nav_rl.runtime_simulation.b23_runner import (
        R09B_TASK_FIXTURE, restore_r09b_fixture_after_contact_pulse,
    )
    def status(sequence, iteration, active, *, backend=12):
        return NS(backend_instance_id=backend, session_id='session-1', config_hash='c'*64,
            coverage_complete=True, contact_source_healthy=True, required_collision_mask=3,
            observed_collision_mask=3, fault_flags=0, paused=False,
            status_sequence=sequence, physics_iteration=iteration, contact_active=active,
            header=NS(stamp=NS(sec=1, nanosec=iteration*10_000_000)))
    wrong = status(9, 90, True, backend=99)
    contact = status(10, 100, True)
    stale_empty = status(10, 100, False)
    empty = status(13, 103, False)
    batches = [[wrong, contact], [stale_empty, empty]]
    timeline = []
    io = NS(descriptor={'backend_instance_id':12, 'session_id':'session-1',
            'config_hash':'c'*64, 'task_fixture':dict(R09B_TASK_FIXTURE)},
        ingress=NS(backend_state=None), now=lambda: 500)
    async def until(predicate, *, deadline_ns, phase):
        assert deadline_ns == 1000
        timeline.append(('wait', phase))
        for candidate in batches.pop(0):
            io.ingress.backend_state = candidate
            value = predicate()
            if value is not None:
                return value
        raise AssertionError('finite fake observations exhausted: '+phase)
    zero_receipt = NS(final_publish_sequence=88)
    zero_applied_state = status(8, 80, False)
    async def set_pose(*, pose_name, deadline_ns, zero_receipt=None,
            applied_zero_witness=None):
        timeline.append(('set_pose', pose_name, deadline_ns, zero_receipt,
            applied_zero_witness))
    def emit(event, facts):
        timeline.append((event, facts))
    io.until, io.set_r09b_task_fixture_pose, io.emit = until, set_pose, emit
    result = asyncio.run(restore_r09b_fixture_after_contact_pulse(io, deadline_ns=1000,
        after_status_sequence=8, after_physics_iteration=80,
        zero_receipt=zero_receipt, zero_applied_state=zero_applied_state,
        zero_applied_received_ns=400))
    assert result['contact']['status_sequence'] == 10
    assert result['restored_empty']['status_sequence'] == 13
    tags = [row[0] for row in timeline]
    assert tags.index('R09B_FIXTURE_CONTACT_PULSE_OBSERVED') < tags.index('set_pose')
    assert timeline[tags.index('set_pose')][1] == 'initial_pose'
    assert timeline[tags.index('set_pose')][3:] == (None, None)
    assert tags.index('set_pose') < tags.index('R09B_FIXTURE_RESTORED_COVERED_EMPTY')
    assert len(batches) == 0


def test_r09b_pending_step_uses_exact_zero_application_not_latest_physics_iteration():
    import asyncio
    from mecanum_nav_rl.runtime_simulation.b23_runner import TrainingWorkerIO
    from mecanum_nav_rl_interfaces.msg import (
        FinalIssuedCommandReceipt, LocalTrainingSafetyInput, SimulationContactState,
    )
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control

    def state(iteration):
        value=SimulationContactState()
        value.backend_instance_id=12; value.session_id='session-1'; value.config_hash='c'*64
        value.applied_receipt_valid=True; value.local_zero_override=False
        value.applied_final_publisher_instance_id=34; value.applied_final_publish_sequence=88
        value.applied_physics_iteration=100; value.physics_iteration=iteration
        value.applied_sim_stamp.sec=1; value.applied_sim_stamp.nanosec=0
        value.header.stamp.sec=1; value.header.stamp.nanosec=(iteration-100)*10_000_000
        value.coverage_complete=True; value.contact_source_healthy=True
        value.required_collision_mask=3; value.observed_collision_mask=3
        value.fault_flags=0; value.paused=False; value.actuator_inhibited=False
        value.contact_active=False
        return value

    receipt=FinalIssuedCommandReceipt()
    receipt.final_publisher_instance_id=34; receipt.final_publish_sequence=88
    receipt.source=receipt.SOURCE_SAFE_STOP
    latest=state(104)
    applied=state(100)
    request=Control.Request(); request.operation=request.OP_BIND_PENDING_STEP
    request.pending_step_index=1; request.pending_transition_id='transition-1'
    response=Control.Response(); response.result=response.RESULT_APPLIED
    response.pending_admission_token=[7]*16
    io=object.__new__(TrainingWorkerIO)
    io.descriptor={'backend_instance_id':12,'session_id':'session-1','config_hash':'c'*64}
    io.final=NS(publisher_instance_id=34,last_publication=receipt)
    io.ingress=NS(pending_ack=NS(request=request,response=response),
        admission_state=LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN,
        backend_state=latest,application_for_receipt=lambda found: (
            {'state':applied,'received_ns':950_000_000} if found is receipt else None))
    io.now=lambda:1_000_000_000
    async def until(predicate,*,deadline_ns,phase):
        assert deadline_ns==2_000_000_000
        assert phase=='R09b exact applied SAFE_STOP zero before fixture task'
        return predicate()
    io.until=until
    token=NS(step_index=1,transition_id='transition-1')
    result=asyncio.run(io.wait_r09b_pending_step_zero_witness(token,deadline_ns=2_000_000_000))
    assert result==(receipt,applied,950_000_000)


def test_r09b_waits_for_post_restore_clear_scan_and_applied_zero_before_pending_bind():
    import asyncio
    from mecanum_nav_rl.runtime_simulation.b23_runner import TrainingWorkerIO

    def stamp(value):
        return value.sec * 1_000_000_000 + value.nanosec
    def state(sequence, sim_ns):
        return NS(status_sequence=sequence, fault_flags=0, paused=False,
            contact_active=False, coverage_complete=True, contact_source_healthy=True,
            episode_generation=1, reset_epoch=2, runtime_generation=3,
            backend_instance_id=12, session_id='session-r09b', config_hash='c'*64,
            applied_receipt_valid=True, local_zero_override=False,
            applied_final_publisher_instance_id=34, applied_final_publish_sequence=99,
            applied_physics_iteration=123,
            applied_sim_stamp=NS(sec=sim_ns//1_000_000_000,
                nanosec=sim_ns%1_000_000_000),
            header=NS(stamp=NS(sec=sim_ns//1_000_000_000,
                nanosec=sim_ns%1_000_000_000)))

    restored=state(10,1_000_000_000)
    applied=state(13,1_130_000_000)
    scan=NS(header=NS(stamp=NS(sec=1,nanosec=120_000_000)))
    life=NS(episode_generation=1,reset_epoch=2,runtime_generation=3)
    events=[]
    adapter=NS(scan=None,scan_received=0,life=life,
        stamp=lambda value: stamp(value), identity=lambda value: (
            value.episode_generation,value.reset_epoch,value.runtime_generation))
    receipt=NS(final_publisher_instance_id=34,final_publish_sequence=99,
        final_command=NS(linear=NS(x=0.,y=0.),angular=NS(z=0.)))
    application={'state':applied,'received_ns':900}
    io=object.__new__(TrainingWorkerIO)
    io.descriptor={'backend_instance_id':12,'session_id':'session-r09b','config_hash':'c'*64}
    io.safety=NS(local_training=adapter)
    io.ingress=NS(backend_state=restored,application_for_receipt=lambda found:
        application if found is receipt else None)
    io.final=NS(publisher_instance_id=34,publication_for_source_sequence=lambda **kwargs:
        receipt if kwargs=={'source':4,'sequence':7} else None)
    io.events=events
    io.now=lambda:1_500
    emitted=[]
    io.emit=lambda name,facts:emitted.append((name,facts))
    waits=[]

    async def until(predicate,*,deadline_ns,phase):
        assert deadline_ns==2_000
        waits.append(phase)
        if phase=='R09b post-restore scan clear and Safety zero tick':
            io.ingress.backend_state=state(11,1_110_000_000)
            adapter.scan=NS(header=NS(stamp=NS(sec=1,nanosec=100_000_000)))
            assert predicate() is None, 'pre-restore scan must not qualify'
            adapter.scan=scan; adapter.scan_received=1_400
            events.append(('SAFETY_REJECTED', {'source':4,'sequence':7,
                'ros_ns':1_120_000_000,'reasons':['POLICY_HELD','STOPPING_ENVELOPE_OCCUPIED']}))
            assert predicate() is None, 'occupied stopping envelope must keep waiting'
            events.append(('SAFETY_REJECTED', {'source':4,'sequence':7,
                'ros_ns':1_120_000_000,'reasons':['POLICY_HELD']}))
            return predicate()
        value=predicate()
        assert value is not None, f'expected evidence missing at {phase}'
        return value
    io.until=until

    result=asyncio.run(io.wait_r09b_restored_scan_zero_before_bind(deadline_ns=2_000))
    assert result==(receipt,applied,900)
    assert waits==[
        'R09b post-restore scan clear and Safety zero tick',
        'R09b exact post-clear SAFE_STOP receipt',
        'R09b exact post-clear zero application']
    assert emitted[0][0]=='R09B_STOPPING_ENVELOPE_CLEAR_ZERO_APPLIED'
    assert emitted[0][1]['restored_status_sequence']==10
    assert emitted[0][1]['clear_scan_stamp_ns']==1_120_000_000


def test_r09b_fixture_pose_waits_for_current_receipt_keyed_zero_application():
    import asyncio
    from mecanum_nav_rl.runtime_simulation.b23_runner import R09B_TASK_FIXTURE, TrainingWorkerIO
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt, SimulationContactState
    from ros_gz_interfaces.srv import SetEntityPose

    receipt=FinalIssuedCommandReceipt()
    receipt.final_publisher_instance_id=34; receipt.final_publish_sequence=88
    receipt.source=receipt.SOURCE_SAFE_STOP
    state=SimulationContactState()
    state.backend_instance_id=12; state.session_id='session-1'; state.config_hash='c'*64
    state.episode_generation=1; state.reset_epoch=2; state.runtime_generation=3
    state.applied_receipt_valid=True; state.applied_final_publisher_instance_id=34
    state.applied_final_publish_sequence=88; state.fault_flags=0; state.paused=False
    # Native may hold actuator_inhibited while applying the exact SAFE_STOP
    # receipt. That is a valid zero proof for this fixture-only operation.
    state.local_zero_override=False; state.actuator_inhibited=True
    state.coverage_complete=True; state.contact_source_healthy=True
    state.required_collision_mask=3; state.observed_collision_mask=3
    io=object.__new__(TrainingWorkerIO)
    io.descriptor={'task_fixture':dict(R09B_TASK_FIXTURE),'backend_instance_id':12,
        'session_id':'session-1','config_hash':'c'*64}
    io.final=NS(publisher_instance_id=34,last_publication=receipt)
    io.ingress=NS(backend_state=state,
        application_for_receipt=lambda candidate: {'state':state,'received_ns':90}
            if candidate is receipt else None)
    io.pose_type=SetEntityPose; io.pose_client=object(); io.now=lambda:100
    waits=[]; calls=[]; emitted=[]
    async def until(predicate, *, deadline_ns, phase):
        waits.append((deadline_ns,phase))
        return predicate()
    async def call(_client,request,**kwargs):
        calls.append((request,kwargs)); response=SetEntityPose.Response()
        response.success=True; return response
    io.until=until; io.call=call
    io.emit=lambda event,facts:emitted.append((event,facts))
    asyncio.run(io.set_r09b_task_fixture_pose(pose_name='contact_pose',
        deadline_ns=1_000_000_000,zero_receipt=None))
    assert waits==[(1_000_000_000,'R09b current applied SAFE_STOP before fixture pose')]
    assert len(calls)==1
    facts=next(facts for event,facts in emitted if event=='R09B_FIXTURE_POSE_REQUESTED')
    assert facts['zero_receipt_sequence']==88
    assert facts['zero_receipt_source']==receipt.SOURCE_SAFE_STOP
    assert facts['zero_applied'] is True
    assert facts['actuator_inhibited'] is True
    assert facts['recent_zero_witness_used'] is False


@pytest.mark.parametrize('mutation', ['receipt_sequence','application_age','contact_coverage'])
def test_r09b_fixture_pose_rejects_unverified_current_zero(mutation):
    import asyncio
    from mecanum_nav_rl.runtime_simulation.b23_runner import R09B_TASK_FIXTURE, TrainingWorkerIO
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt, SimulationContactState
    from ros_gz_interfaces.srv import SetEntityPose

    receipt=FinalIssuedCommandReceipt()
    receipt.final_publisher_instance_id=34; receipt.final_publish_sequence=88
    receipt.source=receipt.SOURCE_SAFE_STOP
    state=SimulationContactState()
    state.backend_instance_id=12; state.session_id='session-1'; state.config_hash='c'*64
    state.episode_generation=1; state.reset_epoch=2; state.runtime_generation=3
    state.applied_receipt_valid=True; state.applied_final_publisher_instance_id=34
    state.applied_final_publish_sequence=88; state.fault_flags=0; state.paused=False
    state.local_zero_override=False; state.actuator_inhibited=False
    state.coverage_complete=True; state.contact_source_healthy=True
    state.required_collision_mask=3; state.observed_collision_mask=3
    if mutation=='receipt_sequence':
        state.applied_final_publish_sequence=87
    elif mutation=='contact_coverage':
        state.observed_collision_mask=1
    io=object.__new__(TrainingWorkerIO)
    io.descriptor={'task_fixture':dict(R09B_TASK_FIXTURE),'backend_instance_id':12,
        'session_id':'session-1','config_hash':'c'*64}
    io.final=NS(publisher_instance_id=34,last_publication=receipt)
    received_ns=90 if mutation!='application_age' else -600_000_000
    io.ingress=NS(backend_state=state,
        application_for_receipt=lambda candidate: {'state':state,'received_ns':received_ns}
            if candidate is receipt else None)
    io.pose_type=SetEntityPose; io.pose_client=object(); io.now=lambda:100
    calls=[]
    async def until(predicate, *, deadline_ns, phase):
        assert phase=='R09b current applied SAFE_STOP before fixture pose'
        if predicate() is None:
            raise TimeoutError('current applied zero was not observed')
        raise AssertionError('invalid current-zero fixture unexpectedly passed')
    async def call(_client,request,**kwargs):
        calls.append(request); response=SetEntityPose.Response()
        response.success=True; return response
    io.until=until; io.call=call; io.emit=lambda *_args:None
    with pytest.raises(TimeoutError,match='current applied zero'):
        asyncio.run(io.set_r09b_task_fixture_pose(pose_name='contact_pose',
            deadline_ns=1_000_000_000,zero_receipt=None))
    assert calls==[]


def test_r09_scenario_identity_reads_ready_loader_artifact():
    import json
    from mecanum_nav_rl.tasks.scenario_artifact import (
        ScenarioArtifactLoader, ScenarioArtifactLoadStatus,
    )
    root = Path(__file__).parents[1] / 'scenarios' / 'local_training'
    for filename, expected in (
        ('B2_GOAL_SETTLE_V1.json', 'B2_GOAL_SETTLE_V1'),
        ('B2_CONTACT_V1.json', 'B2_CONTACT_V1'),
    ):
        raw = json.loads((root / filename).read_text())
        source_identity = raw['identity']
        result = ScenarioArtifactLoader(
            expected_gazebo_world_name=source_identity['gazebo_world_name'],
            expected_world_file_sha256=source_identity['world_file_sha256'],
        ).load(json.dumps(raw))
        assert result.status is ScenarioArtifactLoadStatus.READY
        assert require_r09_scenario(result, expected).scenario_id == expected
        with pytest.raises(RuntimeError, match='scenario identity mismatch'):
            require_r09_scenario(result, 'wrong-scenario')


def test_r07a_allows_timer_republication_but_rejects_new_policy_step_identity():
    from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
    from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity

    world = True
    state = NS(fault_flags=1, local_zero_override=True, actuator_inhibited=True)
    lifecycle = EpisodeLifecycleIdentity(1, 2, 3)
    def receipt(sequence, step, transition):
        return NS(source=ReceiptSource.POLICY, session_id='session-1',
            ingress_config_hash='a'*64, lifecycle=lifecycle,
            source_instance_id=91, source_sequence=sequence, step_index=step,
            transition_id=transition, final_publish_sequence=sequence+100)
    issued = receipt(1, 1, 'transition-1')
    repeated = receipt(1, 1, 'transition-1')
    pre_keys = policy_step_identities([issued])
    post_keys = policy_step_identities([issued, repeated])
    result = verify_r07a_unexpected_pause(world_ack=world, world_pause_state=True, backend_state=state,
        pre_pause_policy_step_identities=pre_keys, post_pause_policy_step_identities=post_keys,
        reset_count_before='reset-0', reset_count_after='reset-0')
    assert result['world_pause_state'] is True
    assert result['native_zero_override']
    with pytest.raises(RuntimeError, match='new POLICY step identity'):
        verify_r07a_unexpected_pause(world_ack=world, world_pause_state=True, backend_state=state,
            pre_pause_policy_step_identities=pre_keys,
            post_pause_policy_step_identities=policy_step_identities(
                [issued, repeated, receipt(2, 2, 'transition-2')]),
            reset_count_before='reset-0', reset_count_after='reset-0')
    with pytest.raises(RuntimeError, match='did not observe its committed POLICY step'):
        verify_r07a_unexpected_pause(world_ack=world, world_pause_state=True, backend_state=state,
            pre_pause_policy_step_identities=frozenset(), post_pause_policy_step_identities=frozenset(),
            reset_count_before='reset-0', reset_count_after='reset-0')
    with pytest.raises(RuntimeError, match='native unexpected-pause'):
        verify_r07a_unexpected_pause(world_ack=world, world_pause_state=True,
            backend_state=NS(fault_flags=0, local_zero_override=False, actuator_inhibited=False),
            pre_pause_policy_step_identities=pre_keys, post_pause_policy_step_identities=post_keys,
            reset_count_before='reset-0', reset_count_after='reset-0')
    with pytest.raises(RuntimeError, match='pause ACK/state'):
        verify_r07a_unexpected_pause(world_ack=world, world_pause_state=False,
            backend_state=state, pre_pause_policy_step_identities=pre_keys,
            post_pause_policy_step_identities=post_keys, reset_count_before='reset-0',
            reset_count_after='reset-0')


def test_r07a_resume_requires_exact_invalidated_gate_fault_and_zero_inhibit():
    from mecanum_nav_rl_interfaces.msg import SimulationContactState
    expected_faults = (SimulationContactState.FAULT_CONTEXT |
        SimulationContactState.FAULT_COMMAND_SEQUENCE |
        SimulationContactState.FAULT_COMMAND_STALE)
    identity = frozenset({('session-1', 'step-1')})
    state = NS(paused=False, fault_flags=expected_faults,
        local_zero_override=True, actuator_inhibited=True,
        status_sequence=81, physics_iteration=126)
    result = verify_r07a_resumed_inhibition(backend_state=state,
        pre_pause_policy_step_identities=identity,
        post_resume_policy_step_identities=identity,
        reset_count_before='reset-1', reset_count_after='reset-1')
    assert result['resumed_fault_flags'] == expected_faults
    assert result['gate_invalidation_and_zero_inhibit_verified']

    for bad_state in (
        NS(paused=False, fault_flags=SimulationContactState.FAULT_CONTEXT,
            local_zero_override=True, actuator_inhibited=True,
            status_sequence=81, physics_iteration=126),
        NS(paused=False, fault_flags=expected_faults | SimulationContactState.FAULT_CLOCK,
            local_zero_override=True, actuator_inhibited=True,
            status_sequence=81, physics_iteration=126),
        NS(paused=False, fault_flags=expected_faults,
            local_zero_override=False, actuator_inhibited=True,
            status_sequence=81, physics_iteration=126),
    ):
        with pytest.raises(RuntimeError, match='resumed backend'):
            verify_r07a_resumed_inhibition(backend_state=bad_state,
                pre_pause_policy_step_identities=identity,
                post_resume_policy_step_identities=identity,
                reset_count_before='reset-1', reset_count_after='reset-1')
    with pytest.raises(RuntimeError, match='new POLICY step identity'):
        verify_r07a_resumed_inhibition(backend_state=state,
            pre_pause_policy_step_identities=identity,
            post_resume_policy_step_identities=identity | {('session-1','step-2')},
            reset_count_before='reset-1', reset_count_after='reset-1')
    with pytest.raises(RuntimeError, match='reset/observation0 advanced'):
        verify_r07a_resumed_inhibition(backend_state=state,
            pre_pause_policy_step_identities=identity,
            post_resume_policy_step_identities=identity,
            reset_count_before='reset-1', reset_count_after='reset-2')


def test_policy_receipt_counter_uses_copied_receipt_source_enum():
    from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
    # The production IssuedCommandReceiptView has a source enum field but no
    # generated ROS constant such as SOURCE_POLICY on each instance.
    receipts = [NS(source=ReceiptSource.POLICY), NS(source=ReceiptSource.SAFE_STOP),
        NS(source=ReceiptSource.POLICY)]
    assert policy_receipt_count(receipts) == 2


def test_paused_state_poll_accepts_only_packet_expected_native_fault_code():
    worker = object.__new__(TrainingWorkerIO)
    worker.now = lambda: 100
    worker.last_clock_advance_ns = 0
    worker.expected_paused = False
    status = NS(paused=True, status_sequence=9, physics_iteration=44,
        fault_flags=1, local_zero_override=True)
    worker.ingress = NS(backend_state=status)
    events = []
    worker.emit = lambda name, facts: events.append((name, facts))
    observed = {}
    async def fake_until(predicate, *, deadline_ns, phase, expected_native_fault_flags=None):
        observed.update(deadline_ns=deadline_ns, phase=phase,
            expected_native_fault_flags=expected_native_fault_flags)
        return predicate()
    worker.until = fake_until
    assert asyncio.run(worker.paused_state(True, 1.0,
        expected_native_fault_flags=1)) is True
    assert observed == {'deadline_ns':1_000_000_100,'phase':'paused',
        'expected_native_fault_flags':1}
    assert events[-1][1]['paused'] is True


def test_r07a_resumed_state_poll_accepts_only_exact_gate_invalidation_transition():
    worker = object.__new__(TrainingWorkerIO)
    worker.now = lambda: 100
    worker.last_clock_advance_ns = 0
    worker.expected_paused = True
    status = NS(paused=False, status_sequence=10, physics_iteration=45,
        fault_flags=7, local_zero_override=True)
    worker.ingress = NS(backend_state=status)
    events = []
    worker.emit = lambda name, facts: events.append((name, facts))
    observed = {}
    async def fake_until(predicate, *, deadline_ns, phase, expected_native_fault_flags=None):
        observed.update(deadline_ns=deadline_ns, phase=phase,
            expected_native_fault_flags=expected_native_fault_flags)
        return predicate()
    worker.until = fake_until
    assert asyncio.run(worker.paused_state(False, 1.0,
        expected_native_fault_flags=(1, 7))) is True
    assert observed == {'deadline_ns':1_000_000_100,'phase':'resumed',
        'expected_native_fault_flags':(1, 7)}
    assert worker.last_clock_advance_ns == 100
    assert events[-1][1]['paused'] is False


def test_control_world_records_success_without_nonexistent_response_pause_field():
    from ros_gz_interfaces.srv import ControlWorld
    worker = object.__new__(TrainingWorkerIO)
    worker.control_world_type = ControlWorld
    worker.world_client = object()
    worker.now = lambda: 123
    events = []
    worker.emit = lambda name, facts: events.append((name, facts))
    response = ControlWorld.Response(success=True)
    async def fake_call(client, request, *, timeout_s, phase):
        assert client is worker.world_client
        assert timeout_s == 1.0 and phase == 'world_pause'
        assert request.world_control.pause is True
        return response
    worker.call = fake_call
    result = asyncio.run(worker.control_world(world_name='b2_training_arena', pause=True,
        timeout_s=1.0))
    assert result is True
    assert events[0][0] == 'WORLD_PAUSE_CONTROL'
    assert events[0][1]['requested_pause'] is True
    assert events[0][1]['response_success'] is True
    assert 'response_pause' not in events[0][1]


def test_r07a_pause_and_resume_control_rpc_tolerate_only_the_pinned_native_fault():
    from ros_gz_interfaces.srv import ControlWorld

    class Future:
        def __init__(self, response):
            self.response = response
        def done(self):
            return True
        def result(self):
            return self.response
        def cancel(self):
            raise AssertionError('completed service future must not be cancelled')

    class Client:
        def __init__(self):
            self.requests = []
        def service_is_ready(self):
            return True
        def call_async(self, request):
            self.requests.append(request)
            return Future(ControlWorld.Response(success=True))

    def worker_with_expected_fault():
        worker = object.__new__(TrainingWorkerIO)
        worker.control_world_type = ControlWorld
        worker.world_client = Client()
        worker.deadline_ns = 500
        worker.now = lambda: 100
        worker.ros_now = lambda: 50
        worker.last_clock_ns = 50
        worker.last_clock_advance_ns = 99
        worker.expected_paused = False
        worker.stop_requested = False
        worker.abort_requested = None
        worker.pump_error = None
        worker.calls = []
        worker.ingress = NS(fault=None,
            backend_state=NS(fault_flags=1, local_zero_override=True))
        worker.emit = lambda *_: None
        return worker

    # Các RPC thông thường vẫn fail-closed khi native đã báo fault.
    ordinary = worker_with_expected_fault()
    with pytest.raises(RuntimeError, match='native fault flags=1'):
        asyncio.run(ordinary.control_world(world_name='b2_training_arena',
            pause=False, timeout_s=0.25))
    assert ordinary.world_client.requests == []

    # The R07a external pause can produce FAULT_CONTEXT before ControlWorld's
    # success ACK arrives. Only this packet-pinned pause RPC accepts that bit.
    r07a_pause = worker_with_expected_fault()
    assert asyncio.run(r07a_pause.control_world(world_name='b2_training_arena',
        pause=True, timeout_s=0.25,
        expected_native_fault_flags=1)) is True
    assert len(r07a_pause.world_client.requests) == 1
    assert r07a_pause.world_client.requests[0].world_control.pause is True

    # R07a đã xác minh đúng FAULT_CONTEXT=1; đường resume chịu được cờ đó
    # trong cả service-ready và ACK polling của chính RPC này.
    r07a = worker_with_expected_fault()
    assert asyncio.run(r07a.control_world(world_name='b2_training_arena',
        pause=False, timeout_s=0.25,
        expected_native_fault_flags=1)) is True
    assert len(r07a.world_client.requests) == 1
    assert r07a.world_client.requests[0].world_control.pause is False

    # Không mở rộng sự khoan dung sang cờ khác.
    r07a.ingress.backend_state.fault_flags = 65
    r07a.world_client.requests.clear()
    with pytest.raises(RuntimeError, match='native fault flags=65'):
        asyncio.run(r07a.control_world(world_name='b2_training_arena',
            pause=False, timeout_s=0.25,
            expected_native_fault_flags=1))
    assert r07a.world_client.requests == []


def test_r07b_time_only_reset_accepts_real_controlworld_response_shape():
    from ros_gz_interfaces.srv import ControlWorld
    worker = object.__new__(TrainingWorkerIO)
    worker.control_world_type = ControlWorld
    worker.world_client = object()
    worker.fault_hooks = {'time_only_rollback_after_contact_proof'}
    worker._r07b_rollback_pending_before_ns = None
    worker._r07b_rollback_observed = None
    worker._r07b_request_started_ns = None
    worker.ros_now = iter((200, 330)).__next__
    worker.now = lambda: 321
    worker.deadline_ns = 2_000_000_000
    events = []
    worker.emit = lambda name, facts: events.append((name, facts))
    response = ControlWorld.Response(success=True)
    async def fake_call(client, request, *, timeout_s, phase, before_submit=None):
        assert client is worker.world_client
        assert phase == 'R07b_world_time_only_rollback'
        assert request.world_control.pause is False
        assert request.world_control.reset.time_only is True
        assert request.world_control.reset.all is False
        assert request.world_control.reset.model_only is False
        assert before_submit is not None
        before_submit(321)
        worker._r07b_rollback_observed = {
            'request_baseline_ns':200,'request_started_ns':321,
            'delta_ns':-200,'observed_steady_ns':322}
        return response
    worker.call = fake_call
    async def fake_until(predicate, **kwargs):
        assert kwargs['phase'] == 'R07b ROS clock rollback event'
        return predicate()
    worker.until = fake_until
    before, after, jump = asyncio.run(worker.reset_world_time_only(timeout_s=1.0))
    assert (before, after) == (200, 330)
    assert jump['delta_ns'] == -200
    assert [event[0] for event in events] == [
        'B23_R07B_CLOCK_ROLLBACK_OBSERVED','B23_R07B_TIME_ONLY_RESET']
    assert events[1][1]['response_success'] is True
    assert 'response_pause' not in events[1][1]


def test_r07b_rollback_disposition_requires_post_rollback_native_clock_fault():
    from mecanum_nav_rl.runtime_simulation.b23_runner import r07b_post_rollback_backend_disposition
    old_id = 101
    state = NS(backend_instance_id=old_id, session_id='r07b-session',
        config_hash='a'*64, status_sequence=8, physics_iteration=50,
        fault_flags=64, local_zero_override=True, actuator_inhibited=True)
    io = NS(descriptor={'backend_instance_id':old_id,'session_id':'r07b-session',
        'config_hash':'a'*64}, ingress=NS(backend_state=state,
        backend_received_ns=1_999), _r07b_replacement_backend_statuses=[])
    # A CLOCK fault status that predates the observed rollback cannot authorize QUERY.
    assert r07b_post_rollback_backend_disposition(io,
        old_backend_instance_id=old_id, rollback_observed_ns=2_000) is None
    io.ingress.backend_received_ns = 2_001
    disposition = r07b_post_rollback_backend_disposition(io,
        old_backend_instance_id=old_id, rollback_observed_ns=2_000)
    assert disposition == {
        'kind':'pinned_backend_clock_fault','backend_instance_id':old_id,
        'status_sequence':8,'physics_iteration':50,'fault_flags':64,
        'local_zero_override':True,'actuator_inhibited':True,'received_ns':2_001}
    io.ingress.backend_received_ns = 2_002
    io.ingress.backend_state.fault_flags = 0
    assert r07b_post_rollback_backend_disposition(io,
        old_backend_instance_id=old_id, rollback_observed_ns=2_000) is None


def test_r07b_rollback_disposition_accepts_only_bound_replacement_zero_status():
    from mecanum_nav_rl.runtime_simulation.b23_runner import r07b_post_rollback_backend_disposition
    io = NS(descriptor={'backend_instance_id':101,'session_id':'r07b-session',
        'config_hash':'a'*64}, ingress=NS(backend_state=None,
        backend_received_ns=-1), _r07b_replacement_backend_statuses=[{
            'backend_instance_id':202,'session_id':'r07b-session','config_hash':'a'*64,
            'status_sequence':4,'physics_iteration':9,'fault_flags':272,
            'local_zero_override':True,'actuator_inhibited':True,'received_ns':3_001}])
    got = r07b_post_rollback_backend_disposition(io,
        old_backend_instance_id=101, rollback_observed_ns=3_000)
    assert got['kind'] == 'replacement_backend'
    assert got['backend_instance_id'] == 202
    assert got['fault_flags'] == 272
    io._r07b_replacement_backend_statuses[0]['session_id'] = 'other-session'
    assert r07b_post_rollback_backend_disposition(io,
        old_backend_instance_id=101, rollback_observed_ns=3_000) is None


def test_r07b_verifier_requires_exact_rollback_and_both_queries_revoked():
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    original = NS(request_bytes=b'original-query',
        response_bytes=b'verified-query',
        request=NS(operation=Control.Request.OP_VERIFY_CONTACT_CAPABILITY),
        response=NS(contact_capability_state=Control.Response.CAPABILITY_VERIFIED))
    def revoked(request_bytes=b'original-query'):
        return NS(request_bytes=request_bytes, response_bytes=b'revoked-query',
            request=NS(operation=Control.Request.OP_VERIFY_CONTACT_CAPABILITY),
            response=NS(result=Control.Response.RESULT_REJECTED,
                reason_code=Control.Response.REASON_CONTACT_PROBE_FAILED,
                contact_capability_state=Control.Response.CAPABILITY_FAILED,
                proof_backend_instance_id=0, proof_session_id='', proof_config_hash='',
                proof_asset_manifest_sha256=''))
    inhibit = NS(request=NS(operation=Control.Request.OP_INHIBIT, request_sequence=7),
        response=NS(result=Control.Response.RESULT_APPLIED,
            reason_code=Control.Response.REASON_NONE, applied_binding_revision=3))
    result = verify_r07b_revocation(response=revoked().response,
        original_proof=original, sim_before_ns=900, sim_after_ns=930,
        sim_time_jump_delta_ns=-900,
        replay_ack=revoked(), fresh_ack=revoked(b'new-query'), inhibit_ack=inhibit)
    assert result['query_replay_revoked'] and result['fresh_query_revoked']
    assert result['simulation_time_jump_delta_ns'] == -900
    with pytest.raises(RuntimeError, match='replayed QUERY exposed proof'):
        stale_response = NS(result=Control.Response.RESULT_APPLIED,
            reason_code=Control.Response.REASON_NONE,
            contact_capability_state=Control.Response.CAPABILITY_VERIFIED,
            proof_backend_instance_id=8, proof_session_id='session',
            proof_config_hash='a'*64, proof_asset_manifest_sha256='b'*64)
        verify_r07b_revocation(response=original.response, original_proof=original,
            sim_before_ns=900, sim_after_ns=930, sim_time_jump_delta_ns=-900,
            replay_ack=NS(**{**revoked().__dict__, 'response_bytes':b'verified-query',
                'response':stale_response}), fresh_ack=revoked(), inhibit_ack=inhibit)


def test_r07b_worker_clock_monitor_keeps_packet_armed_window_until_native_disposition():
    worker = object.__new__(TrainingWorkerIO)
    worker.stop_requested = False
    worker.abort_requested = None
    worker.pump_error = None
    worker.deadline_ns = 1000
    worker.now = lambda: 20
    worker.ros_now = lambda: 5
    worker.last_clock_ns = 10
    worker.last_clock_advance_ns = 10
    worker.expected_paused = False
    worker._r07b_rollback_pending_before_ns = 15
    worker._r07b_request_started_ns = 15
    worker._r07b_rollback_observed = None
    events = []
    worker.emit = lambda kind, facts: events.append((kind, facts))
    worker.ingress = NS(fault=None, backend_state=None)
    worker._on_r07b_clock_jump(NS(delta=NS(nanoseconds=-5)))
    worker.check()
    assert worker._r07b_rollback_observed == {
        'request_baseline_ns':15,'request_started_ns':15,
        'delta_ns':-5,'observed_steady_ns':20}
    assert worker._r07b_rollback_pending_before_ns == 15
    worker.ros_now = lambda: 4
    worker.check()
    assert worker.last_clock_ns == 4
    assert worker._r07b_rollback_pending_before_ns == 15
    assert events[-1][0] == 'B23_R07B_AUTHORIZED_CLOCK_ROLLBACK_SAMPLE'
    worker._r07b_rollback_pending_before_ns = None
    worker.ros_now = lambda: 4
    with pytest.raises(RuntimeError, match='ROS clock rolled backward'):
        worker.last_clock_ns = 5
        worker.check()


def test_r07b_clock_jump_threshold_matches_jazzy_backward_duration_contract():
    from rclpy.clock import JumpThreshold
    from rclpy.duration import Duration

    threshold = JumpThreshold(min_forward=None,
        min_backward=Duration(nanoseconds=-1), on_clock_change=False)
    assert threshold.min_backward.nanoseconds == -1


def test_owned_restart_request_is_pinned_to_run_case_role_and_exact_identity():
    identity = {'pid':101,'uid':1000,'start_ticks':77,'argv':['gz','sim'],
        'pgid':101,'sid':101}
    request = {'schema':'b23_owned_restart_request/v1','run_id':'B23_R07C_TEST',
        'invocation_id':'a'*32,'case':'R07c','operation':'restart_owned_process',
        'target_role':'server','identity':identity}
    assert verify_owned_restart_request(request, run_id='B23_R07C_TEST',
        invocation_id='a'*32, case='R07c', role='server',
        process_identity_record=identity)
    for changes in ({'invocation_id':'b'*32}, {'target_role':'final'},
                    {'identity':dict(identity, start_ticks=78)},
                    {'case':'R07d'}):
        with pytest.raises(ValueError, match='identity mismatch|not authorized'):
            verify_owned_restart_request({**request, **changes}, run_id='B23_R07C_TEST',
                invocation_id='a'*32, case='R07c', role='server',
                process_identity_record=identity)


def test_owned_restart_request_ignores_mutable_proc_snapshot_but_pins_identity_tuple():
    identity = {'pid':101,'uid':1000,'start_ticks':77,
        'argv':['/usr/bin/gz','sim','--headless-rendering'],
        'pgid':101,'sid':101,'state':'R','ppid':90,
        'raw_hex':{'stat':'aa','status':'bb','cmdline':'cc','cgroup':'dd'}}
    request = {'schema':'b23_owned_restart_request/v1','run_id':'B23_R07C_TEST',
        'invocation_id':'a'*32,'case':'R07c','operation':'restart_owned_process',
        'target_role':'server','identity':identity}
    current = {**identity,'state':'S','ppid':99,
        'raw_hex':{'stat':'11','status':'22','cmdline':'cc','cgroup':'ee'}}
    assert verify_owned_restart_request(request, run_id='B23_R07C_TEST',
        invocation_id='a'*32, case='R07c', role='server',
        process_identity_record=current)
    for field, value in (('pid',102),('uid',1001),('start_ticks',78),
                         ('argv',['/usr/bin/gz','sim','different']),
                         ('pgid',102),('sid',102)):
        changed = {**current,field:value}
        with pytest.raises(ValueError, match='identity mismatch'):
            verify_owned_restart_request(request, run_id='B23_R07C_TEST',
                invocation_id='a'*32, case='R07c', role='server',
                process_identity_record=changed)


def _owned_restart_ack_test_io(tmp_path, identity, response_identity,
        *, group_absent=True, exit_status=0):
    import asyncio
    import hashlib
    import json
    from mecanum_nav_rl.runtime_simulation.b23_runner import TrainingWorkerIO

    tmp_path.mkdir(parents=True, exist_ok=True)
    request_path = tmp_path/'restart-request.json'
    response_path = tmp_path/'restart-response.json'
    io = object.__new__(TrainingWorkerIO)
    io.descriptor = {
        'run_id':'B23_R07C_RESPONSE_BINDING', 'invocation_id':'a'*32,
        'server_identity':identity, 'server_leader_pid':101,
        'backend_instance_id':11,
        'owned_restart_request_path':str(request_path),
        'owned_restart_response_path':str(response_path),
    }
    io.now = lambda:100
    io.emit = lambda *_args, **_kwargs: None
    io.deadline_ns = 1000
    io._r07c_restart_started_ns = None
    io._r07c_restart_clock_phase = 'idle'
    io._r07c_clock_rollback_observed = False

    async def until(predicate, *, deadline_ns, phase):
        assert deadline_ns == 1000
        assert phase == 'R07c owned process restart ACK'
        request = json.loads(request_path.read_bytes())
        response_path.write_text(json.dumps({
            'schema':'b23_owned_restart_response/v1',
            'run_id':request['run_id'],
            'invocation_id':request['invocation_id'],
            'case':'R07c', 'target_role':'server',
            'request_sha256':hashlib.sha256(request_path.read_bytes()).hexdigest(),
            'old_process':{'identity':response_identity,'pid':101,
                           'exit_status':exit_status,'group_absent':group_absent},
            'replacement':{'pid':202,'backend_instance_id':22},
            'completed_ns':200,
        }))
        return predicate()

    io.until = until
    return io


def test_owned_restart_ack_accepts_changed_mutable_proc_snapshot(tmp_path):
    """A process may change state/proc metadata while retaining its identity."""
    import asyncio
    from mecanum_nav_rl.runtime_simulation.b23_runner import TrainingWorkerIO

    identity = {
        'pid':101, 'uid':1000, 'start_ticks':77, 'pgid':101, 'sid':101,
        'argv':['gz', 'sim', '--headless-rendering'], 'state':'S',
        'ppid':90, 'raw_hex':{'stat':'aa','status':'bb','cmdline':'cc','cgroup':'dd'},
    }
    response_identity = {
        **identity, 'state':'Z', 'ppid':1,
        'raw_hex':{'stat':'11','status':'22','cmdline':'cc','cgroup':'ee'},
    }
    io = _owned_restart_ack_test_io(tmp_path, identity, response_identity)
    response = asyncio.run(io.request_owned_restart(case='R07c', target_role='server'))
    assert response['old_process']['identity']['pid'] == 101
    assert response['old_process']['identity']['start_ticks'] == 77
    assert response['old_process']['identity']['state'] == 'Z'


def test_owned_restart_ack_rejects_changed_identity_or_live_group(tmp_path):
    """A replacement ACK must retain identity and prove the old group absent."""
    import asyncio
    import pytest

    identity = {
        'pid':101, 'uid':1000, 'start_ticks':77, 'pgid':101, 'sid':101,
        'argv':['gz', 'sim', '--headless-rendering'], 'state':'S',
        'ppid':90, 'raw_hex':{'stat':'aa','status':'bb','cmdline':'cc','cgroup':'dd'},
    }
    bad_cases = (
        ({**identity, 'start_ticks':78}, True),
        (identity, False),
    )
    for index, (response_identity, group_absent) in enumerate(bad_cases):
        io = _owned_restart_ack_test_io(
            tmp_path/str(index), identity, response_identity,
            group_absent=group_absent,
        )
        with pytest.raises(RuntimeError, match='owned restart response binding mismatch'):
            asyncio.run(io.request_owned_restart(case='R07c', target_role='server'))


def test_r07c_owned_backend_restart_requires_new_identity_old_rejection_and_inhibit():
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    old_id, new_id = 11, 22
    original = NS(response=NS(contact_capability_state=Control.Response.CAPABILITY_VERIFIED))
    old_rejection = NS(request=NS(operation=Control.Request.OP_INHIBIT), response=NS(
        result=Control.Response.RESULT_REJECTED,
        reason_code=Control.Response.REASON_IDENTITY_MISMATCH,
        backend_instance_id=new_id))
    query = NS(request=NS(operation=Control.Request.OP_VERIFY_CONTACT_CAPABILITY), response=NS(
        result=Control.Response.RESULT_REJECTED,
        reason_code=Control.Response.REASON_CONTACT_PROBE_NOT_READY,
        contact_capability_state=Control.Response.CAPABILITY_FAILED,
        proof_backend_instance_id=0,proof_session_id='',proof_config_hash='',
        proof_asset_manifest_sha256=''))
    inhibit = NS(request=NS(operation=Control.Request.OP_INHIBIT), response=NS(
        result=Control.Response.RESULT_APPLIED,reason_code=Control.Response.REASON_NONE))
    status = {'backend_instance_id':new_id,'local_zero_override':True,
        'actuator_inhibited':True,'fault_flags':0}
    result = verify_r07c_backend_restart(original_proof=original,
        old_backend_instance_id=old_id, old_process={'pid':101,'group_absent':True},
        replacement={'pid':202,'backend_instance_id':new_id},
        old_identity_rejection=old_rejection, query_ack=query,
        inhibit_ack=inhibit, replacement_status=status)
    assert result['backend_restarted'] is True
    assert result['contact_proof_not_inherited'] is True
    assert result['replacement_inhibit_applied'] is True
    with pytest.raises(RuntimeError, match='did not remain natively inhibited'):
        verify_r07c_backend_restart(original_proof=original,
            old_backend_instance_id=old_id, old_process={'pid':101,'group_absent':True},
            replacement={'pid':202,'backend_instance_id':new_id},
            old_identity_rejection=old_rejection, query_ack=query,
            inhibit_ack=inhibit, replacement_status={**status,'local_zero_override':False})
    with pytest.raises(RuntimeError, match='old backend control'):
        verify_r07c_backend_restart(original_proof=original,
            old_backend_instance_id=old_id, old_process={'pid':101,'group_absent':True},
            replacement={'pid':202,'backend_instance_id':new_id},
            old_identity_rejection=NS(**{**old_rejection.__dict__,'response':NS(
                result=Control.Response.RESULT_APPLIED,
                reason_code=Control.Response.REASON_NONE,backend_instance_id=old_id)}),
            query_ack=query,inhibit_ack=inhibit,replacement_status=status)


def test_r07c_worker_finalization_uses_verified_replacement_backend():
    """R07c's final cleanup must inhibit the replacement, not stale control."""
    import asyncio
    from mecanum_nav_rl.runtime_simulation.b23_runner import TrainingWorkerIO

    calls = []
    class Control:
        def __init__(self, name, backend_instance_id):
            self.name = name
            self.identity = NS(backend_instance_id=backend_instance_id)
            self.owned_calls = []
        async def inhibit(self, *, deadline_ns): calls.append((self.name, deadline_ns))
        def cancel_pending_calls(self): pass
    class Gate:
        def set_policy_hold(self, value): pass
        def set_stream_enabled(self, value): pass
    class Ingress:
        def inhibit(self): pass
        def pause_admission_publication(self): pass
    io = TrainingWorkerIO.__new__(TrainingWorkerIO)
    io.safety = NS(local_training=Gate())
    io.ingress = Ingress()
    io.subscriptions = []
    io.pump_task = None
    io.calls = []
    io.control = Control('stale', 11)
    io._r07b_cleanup_control = None
    replacement = Control('replacement', 22)
    io.pin_replacement_backend_for_cleanup(replacement, 22)
    with pytest.raises(RuntimeError, match='identity mismatch'):
        io.pin_replacement_backend_for_cleanup(Control('wrong', 33), 22)
    io.now = lambda: 100
    io.close_context = lambda: []
    io.emit = lambda *args: None
    io.cleanup_errors = ()
    io.deadline_ns = 1_000
    assert asyncio.run(io.stop(deadline_ns=1_000)) is True
    assert [name for name, _ in calls] == ['replacement']


def test_r07d_establishes_real_episode_before_native_inhibited_drain():
    """Production helper resets noisy lifecycle before waiting for native input."""
    calls = []

    class IO:
        def __init__(self):
            self.deadline_ns = 9_000_000_000
            self.ingress = NS(_noise_ready=False, lifecycle=None)
        async def reset_episode(self, b1, *, seed, target, paused_hold_s):
            calls.append(('reset', b1, seed, target, paused_hold_s))
            self.ingress._noise_ready = True
            self.ingress.lifecycle = NS(episode_generation=1, reset_epoch=1,
                runtime_generation=1)
        async def inhibit_and_drain(self, *, deadline_ns):
            calls.append(('drain', deadline_ns))
            assert self.ingress._noise_ready is True
            assert self.ingress.lifecycle.episode_generation == 1
            self.ingress.last_published_sample_sequence = 7
            return 7
        async def freeze_admission(self, *, deadline_ns):
            calls.append(('freeze_admission', deadline_ns,
                self.ingress.last_published_sample_sequence))
        def emit(self, event, facts):
            calls.append((event, facts))
        def now(self):
            return 123

    packet = {'episode_seeds':[2026102900],
        'reset_target':{'x_m':0.0,'y_m':0.0,'z_m':0.1,'yaw_rad':0.0}}
    io = IO()
    result = asyncio.run(prepare_r07d_final_publisher_restart(io, object(), packet))
    assert result == 7
    assert calls[0][0] == 'reset'
    assert calls[0][2] == 2026102900
    assert calls[0][3].x_m == 0.0
    assert calls[0][4] == .250
    assert calls[1] == ('B23_R07D_ACTIVE_CONTEXT_READY', {
        'episode_generation':1,'reset_epoch':1,'runtime_generation':1,'steady_ns':123})
    assert calls[2] == ('drain', io.deadline_ns)
    assert calls[3] == ('freeze_admission', io.deadline_ns, 7)


def test_r07d_parent_pins_initial_final_instance_for_owned_restart():
    descriptor = {'run_id':'B23_R07D_TEST','invocation_id':'a'*32}
    boot = {'run_id':'B23_R07D_TEST','invocation_id':'a'*32,
        'publisher_instance_id':77,'identity':{'pid':101}}
    assert pin_initial_final_publisher_identity(descriptor, boot, 101) == 77
    assert descriptor['final_publisher_instance_id'] == 77
    assert descriptor['final_publisher_pid'] == 101
    with pytest.raises(RuntimeError, match='cannot be pinned'):
        pin_initial_final_publisher_identity(descriptor, {**boot,
            'publisher_instance_id':78}, 102)


def test_worker_waits_for_backend_service_before_control_rpc():
    import asyncio
    from mecanum_nav_rl.runtime_simulation.b23_runner import TrainingWorkerIO

    clock = {'ns':100}
    events = []
    class Client:
        def __init__(self, ready_after): self.calls, self.ready_after = 0, ready_after
        def service_is_ready(self):
            self.calls += 1
            return self.ready_after is not None and self.calls >= self.ready_after
    class PauseControl:
        async def __call__(self, seconds): clock['ns'] += int(seconds * 1e9)
    def io_for(client):
        io = TrainingWorkerIO.__new__(TrainingWorkerIO)
        io.deadline_ns = 100_000_000
        io.now = lambda: clock['ns']
        io.pause = PauseControl()
        io.check = lambda **_kwargs: None
        io.emit = lambda name, facts: events.append((name, facts))
        return io

    ready_client = Client(3)
    control = NS(_port=NS(_client=ready_client))
    reached = asyncio.run(io_for(ready_client).wait_backend_control_ready(
        control, timeout_ns=20_000_000, phase='fake replacement service'))
    assert ready_client.calls == 3
    assert reached == clock['ns']
    assert events[-1][0] == 'BACKEND_CONTROL_SERVICE_READY'
    assert events[-1][1]['phase'] == 'fake replacement service'

    clock['ns'] = 100
    unavailable = Client(None)
    with pytest.raises(TimeoutError, match='fake unavailable service: deadline expired'):
        asyncio.run(io_for(unavailable).wait_backend_control_ready(
            NS(_port=NS(_client=unavailable)), timeout_ns=5_000_000,
            phase='fake unavailable service'))
    with pytest.raises(RuntimeError, match='readiness API unavailable'):
        asyncio.run(io_for(object()).wait_backend_control_ready(
            NS(_port=object()), timeout_ns=5_000_000, phase='missing API'))


def test_contact_start_waits_for_all_native_probe_services_within_contact_budget():
    import asyncio
    import inspect
    from mecanum_nav_rl.runtime_simulation.b23_runner import TrainingWorkerIO

    clock = {'ns':100}
    events = []
    class Client:
        def __init__(self, ready_after): self.calls, self.ready_after = 0, ready_after
        def service_is_ready(self):
            self.calls += 1
            return self.ready_after is not None and self.calls >= self.ready_after
    class PauseControl:
        async def __call__(self, seconds): clock['ns'] += int(seconds * 1e9)

    io = TrainingWorkerIO.__new__(TrainingWorkerIO)
    io.deadline_ns = 100_000_000
    io.now = lambda: clock['ns']
    io.pause = PauseControl()
    io.check = lambda **_kwargs: None
    io.emit = lambda name, facts: events.append((name, facts))
    io.probe_spawn_client = Client(1)
    io.pose_client = Client(2)
    io.probe_remove_client = Client(3)

    reached = asyncio.run(io.wait_contact_probe_services_ready(deadline_ns=20_000_000))
    assert reached == clock['ns']
    assert [io.probe_spawn_client.calls, io.pose_client.calls,
        io.probe_remove_client.calls] == [4, 4, 3]
    assert events[0][0] == 'CONTACT_PROBE_SERVICE_READINESS_WAIT'
    assert events[-1] == ('CONTACT_PROBE_SERVICES_READY', {'services':[
        'create','remove','set_pose'], 'steady_ns':clock['ns']})

    clock['ns'] = 100
    io.probe_remove_client = Client(None)
    with pytest.raises(TimeoutError, match='contact probe Gazebo services readiness: deadline expired'):
        asyncio.run(io.wait_contact_probe_services_ready(deadline_ns=5_000_000))

    method = ast.parse(textwrap.dedent(inspect.getsource(TrainingWorkerIO.contact_capability)))
    calls = sorted((node for node in ast.walk(method) if isinstance(node, ast.Await)
        and isinstance(node.value, ast.Call)), key=lambda node: node.lineno)
    wait_index = next(i for i, node in enumerate(calls)
        if isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == 'wait_contact_probe_services_ready')
    start_index = next(i for i, node in enumerate(calls)
        if isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == 'transact'
        and any(isinstance(arg, ast.Attribute) and arg.attr == 'OP_VERIFY_CONTACT_CAPABILITY'
            for arg in node.value.args))
    assert wait_index < start_index


def test_r07d_final_restart_requires_reaped_old_and_unbound_zero_replacement():
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    from mecanum_nav_rl_interfaces.msg import SimulationContactState
    inhibit = NS(request=NS(operation=Control.Request.OP_INHIBIT), response=NS(
        result=Control.Response.RESULT_APPLIED))
    old = {'pid':303,'group_absent':True}
    replacement = {'pid':404,'publisher_instance_id':55,'binding_ack_exists':False}
    backend = {'local_zero_override':True,'actuator_inhibited':True,'fault_flags':0}
    result = verify_r07d_final_publisher_restart(old_publisher_instance_id=44,
        old_process=old,replacement=replacement,backend_status=backend,
        inhibit_ack=inhibit,new_receipts=[])
    assert result['replacement_unbound'] is True
    assert result['native_zero_inhibited'] is True
    assert result['native_fault_flags'] == 0
    expected_watchdog = verify_r07d_final_publisher_restart(
        old_publisher_instance_id=44,old_process=old,replacement=replacement,
        backend_status={**backend,'fault_flags':SimulationContactState.FAULT_COMMAND_STALE},
        inhibit_ack=inhibit,new_receipts=[])
    assert expected_watchdog['native_fault_flags'] == SimulationContactState.FAULT_COMMAND_STALE
    expected_gate_invalidation = verify_r07d_final_publisher_restart(
        old_publisher_instance_id=44,old_process=old,replacement=replacement,
        backend_status={**backend,'fault_flags':(
            SimulationContactState.FAULT_COMMAND_SEQUENCE
            | SimulationContactState.FAULT_COMMAND_STALE)},
        inhibit_ack=inhibit,new_receipts=[])
    assert expected_gate_invalidation['native_fault_flags'] == 6
    with pytest.raises(RuntimeError, match='replacement/binding boundary'):
        verify_r07d_final_publisher_restart(old_publisher_instance_id=44,
            old_process=old,replacement={**replacement,'publisher_instance_id':44},
            backend_status=backend,inhibit_ack=inhibit,new_receipts=[])
    with pytest.raises(RuntimeError, match='zero/inhibit'):
        verify_r07d_final_publisher_restart(old_publisher_instance_id=44,
            old_process=old,replacement=replacement,
            backend_status={**backend,'actuator_inhibited':False},
            inhibit_ack=inhibit,new_receipts=[])
    with pytest.raises(RuntimeError, match='zero/inhibit'):
        verify_r07d_final_publisher_restart(old_publisher_instance_id=44,
            old_process=old,replacement=replacement,
            backend_status={**backend,'fault_flags':SimulationContactState.FAULT_COMMAND_SEQUENCE},
            inhibit_ack=inhibit,new_receipts=[])
    with pytest.raises(RuntimeError, match='zero/inhibit'):
        verify_r07d_final_publisher_restart(old_publisher_instance_id=44,
            old_process=old,replacement=replacement,
            backend_status={**backend,'fault_flags':(
                SimulationContactState.FAULT_CONTEXT
                | SimulationContactState.FAULT_COMMAND_STALE)},
            inhibit_ack=inhibit,new_receipts=[])


def test_r07d_restart_poll_accepts_only_stale_and_exact_gate_invalidation(tmp_path, monkeypatch):
    import asyncio
    import hashlib
    import json
    import mecanum_nav_rl.runtime_simulation.b23_runner as runner
    from mecanum_nav_rl_interfaces.msg import SimulationContactState

    identity = {'pid':101,'uid':1000,'start_ticks':77,'pgid':101,'sid':101,
        'argv':['python','final','--descriptor','/run/final.json']}
    monkeypatch.setattr(runner,'process_identity',lambda _pid: identity)
    request_path=tmp_path/'restart-request.json'; response_path=tmp_path/'restart-response.json'
    io=object.__new__(runner.TrainingWorkerIO)
    io.descriptor={'run_id':'B23_R07D_FLAGS','invocation_id':'a'*32,
        'final_publisher_pid':101,'final_publisher_instance_id':44,
        'owned_restart_request_path':str(request_path),
        'owned_restart_response_path':str(response_path)}
    io.now=lambda:100; io.emit=lambda *_args,**_kwargs:None; io.deadline_ns=1000
    async def fake_until(predicate,*,deadline_ns,phase,expected_native_fault_flags=None):
        assert deadline_ns==1000 and phase=='R07d owned process restart ACK'
        assert expected_native_fault_flags==(SimulationContactState.FAULT_COMMAND_STALE,
            SimulationContactState.FAULT_COMMAND_SEQUENCE|SimulationContactState.FAULT_COMMAND_STALE)
        request=json.loads(request_path.read_bytes())
        response_path.write_text(json.dumps({'schema':'b23_owned_restart_response/v1',
            'run_id':request['run_id'],'invocation_id':request['invocation_id'],
            'case':'R07d','target_role':'final',
            'request_sha256':hashlib.sha256(request_path.read_bytes()).hexdigest(),
            'old_process':{'identity':identity,'pid':101,'exit_status':0,'group_absent':True},
            'replacement':{'pid':202,'publisher_instance_id':55},'completed_ns':200}))
        return predicate()
    io.until=fake_until
    response=asyncio.run(io.request_owned_restart(case='R07d',target_role='final'))
    assert response['old_process']['group_absent'] is True
    assert runner.r07d_restart_fault_flags()==(SimulationContactState.FAULT_COMMAND_STALE,
        SimulationContactState.FAULT_COMMAND_SEQUENCE|SimulationContactState.FAULT_COMMAND_STALE)


def test_r07d_post_restart_zero_uses_ingress_receive_timestamp_after_inhibit_ack():
    from mecanum_nav_rl.runtime_simulation.b23_runner import r07d_post_restart_zero_status
    ack=NS(observed_steady_ns=100)
    state=NS(local_zero_override=True,actuator_inhibited=True)
    ingress=NS(backend_state=state,backend_received_ns=99)
    assert r07d_post_restart_zero_status(ingress,ack) is None
    ingress.backend_received_ns=101
    assert r07d_post_restart_zero_status(ingress,ack) is state
    ingress.backend_received_ns=None
    assert r07d_post_restart_zero_status(ingress,ack) is None
    ingress.backend_received_ns=102; state.actuator_inhibited=False
    assert r07d_post_restart_zero_status(ingress,ack) is None


def test_r07d_backend_status_record_uses_ingress_timestamp_not_ros_message_field():
    from mecanum_nav_rl.runtime_simulation.b23_runner import r07d_backend_status_record
    from mecanum_nav_rl_interfaces.msg import SimulationContactState

    state = SimulationContactState()
    assert not hasattr(state, 'received_steady_ns')
    state.backend_instance_id = 19
    state.local_zero_override = True
    state.actuator_inhibited = True
    state.fault_flags = 6
    state.status_sequence = 42
    record = r07d_backend_status_record(state, 123456789)
    assert record == {'backend_instance_id':19,'local_zero_override':True,
        'actuator_inhibited':True,'fault_flags':6,'status_sequence':42,
        'received_ns':123456789}
    with pytest.raises(ValueError, match='ingress receive timestamp'):
        r07d_backend_status_record(state, None)


def test_r07d_process_identity_ignores_volatile_proc_state_but_pins_stable_fields():
    expected = {'pid':41,'uid':1000,'ppid':8,'pgid':41,'sid':41,'start_ticks':900,
        'argv':['python','final','--descriptor','/run/final.json'],'state':'S',
        'raw_hex':{'cmdline':'6172677600','cgroup':'2f736572766963650a',
            'stat':'old-stat-snapshot','status':'old-status-snapshot'}}
    observed = {**expected,'state':'R','raw_hex':{
        **expected['raw_hex'],'stat':'new-stat-snapshot','status':'new-status-snapshot'}}
    assert same_process_identity(expected, observed)
    for changes in (
        {'start_ticks':901}, {'uid':1001}, {'pgid':99}, {'sid':99},
        {'argv':['python','other']},
    ):
        assert not same_process_identity(expected, {**observed, **changes})
    changed_cgroup = {**observed,'raw_hex':{**observed['raw_hex'],'cgroup':'2f6f746865720a'}}
    assert not same_process_identity(expected, changed_cgroup)


def test_r07b_backend_restart_requires_old_identity_rejection_new_inhibit_and_proof_free_query():
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    old_id, new_id = 101, 202
    session, config, assets = 'session-r07b', 'a'*64, 'b'*64
    original = NS(request=NS(session_id=session), response=NS(
        contact_capability_state=Control.Response.CAPABILITY_VERIFIED), request_bytes=b'original-query')
    old_rejection = NS(
        request=NS(operation=Control.Request.OP_INHIBIT,
            expected_backend_instance_id=old_id, session_id=session,
            request_sequence=10, config_hash=config),
        response=NS(result=Control.Response.RESULT_REJECTED,
            reason_code=Control.Response.REASON_IDENTITY_MISMATCH,
            backend_instance_id=new_id, request_sequence=10))
    inhibit = NS(observed_steady_ns=400, request=NS(
        operation=Control.Request.OP_INHIBIT, expected_backend_instance_id=new_id,
        session_id=session, request_sequence=1), response=NS(
            result=Control.Response.RESULT_APPLIED, reason_code=Control.Response.REASON_NONE,
            backend_instance_id=new_id, request_sequence=1,
            applied_binding_revision=1,
            contact_capability_state=Control.Response.CAPABILITY_FAILED,
            proof_backend_instance_id=0, proof_session_id=''))
    fresh_query = NS(request=NS(operation=Control.Request.OP_VERIFY_CONTACT_CAPABILITY,
            probe_action=Control.Request.PROBE_ACTION_QUERY,
            expected_backend_instance_id=new_id, session_id=session, request_sequence=2),
        response=NS(result=Control.Response.RESULT_REJECTED,
            reason_code=Control.Response.REASON_CONTACT_PROBE_NOT_READY,
            backend_instance_id=new_id, request_sequence=2,
            contact_capability_state=Control.Response.CAPABILITY_FAILED,
            proof_backend_instance_id=0, proof_session_id='',
            proof_config_hash='', proof_asset_manifest_sha256=''))
    status = {'backend_instance_id':new_id,'session_id':session,'config_hash':config,
        'status_sequence':12,'physics_iteration':34,'stamp_ns':340_000_000,
        'fault_flags':272,'local_zero_override':True,'actuator_inhibited':True,
        'received_ns':401,'wire_sha256':'c'*64}
    result = verify_r07b_backend_restart(original_proof=original,
        sim_time_jump_delta_ns=-350_000_000, replay_error=TimeoutError('service vanished'),
        replay_identity_ack=None,
        replacement_ack=old_rejection, inhibit_ack=inhibit, fresh_ack=fresh_query,
        replacement_status=status, old_backend_instance_id=old_id)
    assert result['backend_restarted'] is True
    assert result['old_query_replay_unavailable_due_backend_replacement'] is True
    assert result['replacement_backend_zero_status_confirmed'] is True
    assert result['new_backend_instance_id'] == new_id
    assert result['replacement_backend_fault_flags'] == 272
    assert result['replacement_backend_fault_flags_expected'] == 272

    stale_query = NS(**{**fresh_query.__dict__, 'response':NS(
        **{**fresh_query.response.__dict__,
           'result':Control.Response.RESULT_APPLIED,
           'reason_code':Control.Response.REASON_NONE,
           'contact_capability_state':Control.Response.CAPABILITY_VERIFIED,
           'proof_backend_instance_id':new_id,'proof_session_id':session,
           'proof_config_hash':config,'proof_asset_manifest_sha256':assets})})
    with pytest.raises(RuntimeError, match='replacement QUERY returned stale'):
        verify_r07b_backend_restart(original_proof=original,
            sim_time_jump_delta_ns=-350_000_000,
            replay_error=TimeoutError('service vanished'), replay_identity_ack=None,
            replacement_ack=old_rejection,
            inhibit_ack=inhibit, fresh_ack=stale_query, replacement_status=status,
            old_backend_instance_id=old_id)

    unconfirmed_zero = dict(status, local_zero_override=False)
    with pytest.raises(RuntimeError, match='expected fail-closed zero'):
        verify_r07b_backend_restart(original_proof=original,
            sim_time_jump_delta_ns=-350_000_000,
            replay_error=TimeoutError('service vanished'), replay_identity_ack=None,
            replacement_ack=old_rejection,
            inhibit_ack=inhibit, fresh_ack=fresh_query, replacement_status=unconfirmed_zero,
            old_backend_instance_id=old_id)

    unexpected_fault = dict(status, fault_flags=272 | 64)
    with pytest.raises(RuntimeError, match='expected fail-closed zero'):
        verify_r07b_backend_restart(original_proof=original,
            sim_time_jump_delta_ns=-350_000_000, replay_error=TimeoutError('service vanished'),
            replay_identity_ack=None, replacement_ack=old_rejection, inhibit_ack=inhibit,
            fresh_ack=fresh_query, replacement_status=unexpected_fault,
            old_backend_instance_id=old_id)


def test_r07b_backend_restart_accepts_only_exact_replay_identity_mismatch_ack():
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendControlError
    old_id, new_id, session = 101, 202, 'session-r07b'
    original = NS(request_bytes=b'exact-cdr', request=NS(
        operation=Control.Request.OP_VERIFY_CONTACT_CAPABILITY,
        probe_action=Control.Request.PROBE_ACTION_QUERY, request_sequence=8,
        session_id=session), response=NS(
            contact_capability_state=Control.Response.CAPABILITY_VERIFIED))
    rejected_replay = NS(request_bytes=b'exact-cdr', request=original.request,
        response=NS(backend_instance_id=new_id, request_sequence=8,
            result=Control.Response.RESULT_REJECTED,
            reason_code=Control.Response.REASON_IDENTITY_MISMATCH,
            contact_capability_state=Control.Response.CAPABILITY_INVALIDATED,
            proof_backend_instance_id=0, proof_session_id='', proof_config_hash='',
            proof_asset_manifest_sha256=''))
    error = BackendControlError('replay ACK identity/schema mismatch', rejected_replay)
    invalid_old_rejection = NS(request=NS(operation=Control.Request.OP_INHIBIT,
        expected_backend_instance_id=old_id, session_id=session, request_sequence=9),
        response=NS(backend_instance_id=old_id, result=Control.Response.RESULT_APPLIED,
            reason_code=Control.Response.REASON_NONE, request_sequence=9))
    # Any later replacement evidence is intentionally minimal here; the replay
    # mismatch must be validated before downstream replacement fields.
    with pytest.raises(RuntimeError, match='replacement backend identity'):
        verify_r07b_backend_restart(original_proof=original,
            sim_time_jump_delta_ns=-1, replay_error=error,
            replay_identity_ack=rejected_replay, replacement_ack=invalid_old_rejection, inhibit_ack=NS(),
            fresh_ack=NS(), replacement_status={}, old_backend_instance_id=old_id)
    altered = NS(**{**rejected_replay.__dict__, 'request_bytes':b'other-cdr'})
    with pytest.raises(RuntimeError, match='exact QUERY replay'):
        verify_r07b_backend_restart(original_proof=original,
            sim_time_jump_delta_ns=-1, replay_error=error,
            replay_identity_ack=altered, replacement_ack=NS(), inhibit_ack=NS(),
            fresh_ack=NS(), replacement_status={}, old_backend_instance_id=old_id)


def test_r07b_replacement_query_uses_real_control_session_before_terminal_inhibit():
    from rclpy.serialization import serialize_message
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import (
        BackendSessionIdentity, BackendControlSession, BackendControlError,
    )
    from mecanum_nav_rl.runtime_simulation.local_training_ports import LocalTrainingBackendControlPort

    class PortClient:
        def __init__(self):
            self.requests = []

        def call_async(self, request):
            self.requests.append(serialize_message(request))
            response = Control.Response()
            response.schema_version = response.RESPONSE_SCHEMA_VERSION
            response.backend_instance_id = 202
            response.request_sequence = request.request_sequence
            response.binding_revision = request.expected_binding_revision
            if request.operation == Control.Request.OP_VERIFY_CONTACT_CAPABILITY:
                response.result = response.RESULT_REJECTED
                response.reason_code = response.REASON_CONTACT_PROBE_NOT_READY
            else:
                assert request.operation == Control.Request.OP_INHIBIT
                response.result = response.RESULT_APPLIED
                response.reason_code = response.REASON_NONE
                response.binding_revision += 1
                response.applied_binding_revision = response.binding_revision
                response.applied_physics_iteration = 9
                response.applied_sim_stamp.sec = 1
            return NS(done=lambda: True, result=lambda: response)

    client = PortClient()
    session = BackendControlSession(LocalTrainingBackendControlPort(client),
        BackendSessionIdentity('r07b-session', 'a'*64, 'b'*64, 17, 202),
        emit=lambda _name, _facts: None, now_ns=lambda: 1_000_000_000,
        pause=lambda _seconds: None)
    fresh, inhibit = asyncio.run(query_replacement_backend_then_inhibit(
        session, query_deadline_ns=2_000_000_000, inhibit_deadline_ns=3_000_000_000,
        probe_start_request_sequence=4))

    from rclpy.serialization import deserialize_message
    query = deserialize_message(client.requests[0], Control.Request)
    stop = deserialize_message(client.requests[1], Control.Request)
    assert [query.operation, stop.operation] == [
        Control.Request.OP_VERIFY_CONTACT_CAPABILITY, Control.Request.OP_INHIBIT]
    assert fresh.response.reason_code == Control.Response.REASON_CONTACT_PROBE_NOT_READY
    assert inhibit.response.result == Control.Response.RESULT_APPLIED
    assert len(client.requests) == 2
    with pytest.raises(BackendControlError, match='already uncertain/faulted'):
        asyncio.run(session.transact(Control.Request.OP_VERIFY_CONTACT_CAPABILITY,
            deadline_ns=4_000_000_000,
            probe_action=Control.Request.PROBE_ACTION_QUERY,
            probe_start_request_sequence=4))
    assert len(client.requests) == 2


def test_r07b_callback_records_replacement_status_and_expected_future_receipt_without_killing_pump():
    from mecanum_nav_rl_interfaces.msg import SimulationContactState, FinalIssuedCommandReceipt
    from rclpy.serialization import serialize_message
    worker = object.__new__(TrainingWorkerIO)
    worker.descriptor = {'backend_instance_id':101}
    worker.fault_hooks = {'time_only_rollback_after_contact_proof'}
    worker._r07b_rollback_observed = {'delta_ns':-1}
    worker._r07b_replacement_backend_statuses = []
    worker.ros_now = lambda: 50
    worker.ingress = NS(lock=threading.RLock(), _last_receipt_stamp_ns=100,
        _last_gt_stamp=100, _last_gt_bytes=b'old-oracle', scans={}, fault=None)
    worker.now = lambda: 777
    events = []
    worker.emit = lambda name, facts: events.append((name, facts))
    status = SimulationContactState()
    status.backend_instance_id = 202
    status.session_id = 'session-r07b'
    status.config_hash = 'a'*64
    status.status_sequence = 12
    status.physics_iteration = 34
    status.local_zero_override = True
    status.actuator_inhibited = True
    result = worker.observed_callback(SimulationContactState,
        '/mecanum/local_training/backend_state', lambda _: pytest.fail('old ingress must remain pinned'))(
            serialize_message(status), {})
    assert result.backend_instance_id == 202
    assert worker._r07b_replacement_backend_statuses[0]['backend_instance_id'] == 202
    assert events[-1][0] == 'B23_R07B_REPLACEMENT_BACKEND_STATUS'

    receipt = FinalIssuedCommandReceipt()
    receipt.header.stamp.nanosec = 90
    returned = worker.observed_callback(FinalIssuedCommandReceipt,
        '/mecanum/final_issued_command',
        lambda _: pytest.fail('stale receipt must be quarantined before ingress validation'))(
            serialize_message(receipt), {})
    assert returned is None
    assert events[-1][0] == 'B23_R07B_POST_ROLLBACK_RECEIPT_REJECTED'
    assert events[-1][1]['quarantined_before_ingress_validation'] is True
    assert worker.ingress.fault is None

    receipt.header.stamp.nanosec = 200
    worker.ros_now = lambda: 200

    with pytest.raises(ValueError, match='unrelated receipt failure'):
        worker.observed_callback(FinalIssuedCommandReceipt,
            '/mecanum/final_issued_command',
            lambda _, **_kwargs: (_ for _ in ()).throw(ValueError('unrelated receipt failure')))(
                serialize_message(receipt), {})


def test_r07c_callback_records_replacement_backend_without_fault_hook():
    from mecanum_nav_rl_interfaces.msg import SimulationContactState
    from rclpy.serialization import serialize_message

    worker = object.__new__(TrainingWorkerIO)
    worker.descriptor = {'backend_instance_id':101}
    worker.fault_hooks = ()
    worker._r07c_restart_started_ns = 50
    worker._r07c_replacement_backend_statuses = []
    worker.now = lambda: 777
    events = []
    worker.emit = lambda name, facts: events.append((name, facts))
    status = SimulationContactState()
    status.backend_instance_id = 202
    status.session_id = 'session-r07c'
    status.config_hash = 'a'*64
    status.status_sequence = 12
    status.physics_iteration = 34
    status.local_zero_override = True
    status.actuator_inhibited = True
    callback_calls = []

    result = worker.observed_callback(SimulationContactState,
        '/mecanum/local_training/backend_state',
        lambda message: (callback_calls.append(message), message)[1])(
            serialize_message(status), {})

    assert callback_calls == []
    assert result.backend_instance_id == 202
    assert worker._r07c_replacement_backend_statuses[0]['backend_instance_id'] == 202
    assert worker._r07c_replacement_backend_statuses[0]['received_ns'] == 777
    assert events[-1][0] == 'B23_R07C_REPLACEMENT_BACKEND_STATUS'


def test_r07b_callback_records_and_drops_only_the_rollback_oracle_sample():
    from nav_msgs.msg import Odometry
    from rclpy.serialization import serialize_message
    worker = object.__new__(TrainingWorkerIO)
    worker.fault_hooks = {'time_only_rollback_after_contact_proof'}
    worker._r07b_rollback_observed = {'delta_ns':-360_000_000}
    worker.ingress = NS(lock=threading.RLock(), _last_receipt_stamp_ns=-1,
        _last_gt_stamp=100, _last_gt_bytes=b'old-oracle', scans={}, fault=None)
    worker.now = lambda: 888
    events = []
    worker.emit = lambda name, facts: events.append((name, facts))
    oracle = Odometry()
    oracle.header.stamp.nanosec = 90
    result = worker.observed_callback(Odometry,
        '/mecanum/internal/ground_truth/odom',
        lambda _: pytest.fail('stale oracle must be quarantined before ingress validation'))(
            serialize_message(oracle), {})
    assert result is None
    assert events[-1][0] == 'B23_R07B_POST_ROLLBACK_ORACLE_REJECTED'
    assert events[-1][1]['reason'] == 'oracle_source_stamp_below_pinned_high_watermark'
    assert events[-1][1]['quarantined_before_ingress_validation'] is True
    assert worker.ingress.fault is None

    oracle.header.stamp.nanosec = 100
    result = worker.observed_callback(Odometry,
        '/mecanum/internal/ground_truth/odom',
        lambda _: pytest.fail('same-stamp conflict must be quarantined before ingress validation'))(
            serialize_message(oracle), {})
    assert result is None
    assert events[-1][0] == 'B23_R07B_POST_ROLLBACK_ORACLE_REJECTED'
    assert events[-1][1]['reason'] == 'oracle_same_stamp_bytes_conflict_with_pinned_sample'
    assert worker.ingress.fault is None

    oracle.header.stamp.nanosec = 101
    with pytest.raises(ValueError, match='unrelated oracle failure'):
        worker.observed_callback(Odometry,
            '/mecanum/internal/ground_truth/odom',
            lambda _: (_ for _ in ()).throw(ValueError('unrelated oracle failure')))(
                serialize_message(oracle), {})


def test_r07b_same_stamp_conflicting_scan_is_quarantined_before_ingress_fault():
    from sensor_msgs.msg import LaserScan
    from rclpy.serialization import serialize_message
    worker = object.__new__(TrainingWorkerIO)
    worker.fault_hooks = {'time_only_rollback_after_contact_proof'}
    worker._r07b_rollback_pending_before_ns = 1_000_000_000
    worker._r07b_rollback_observed = None
    worker.ingress = NS(lock=threading.RLock(), _last_receipt_stamp_ns=-1,
        _last_gt_stamp=-1, _last_gt_bytes=None,
        scans={250_000_000:NS(message_bytes=b'previous-scan')}, fault=None)
    worker.now = lambda: 999
    events = []
    worker.emit = lambda name, facts: events.append((name, facts))
    scan = LaserScan()
    scan.header.stamp.nanosec = 250_000_000
    result = worker.observed_callback(LaserScan, '/scan',
        lambda _: pytest.fail('conflicting scan must be quarantined before ingress validation'))(
            serialize_message(scan), {})
    assert result is None
    assert events[-1][0] == 'B23_R07B_POST_ROLLBACK_SCAN_REJECTED'
    assert events[-1][1]['reason'] == 'scan_same_stamp_bytes_conflict_with_pinned_sample'
    assert events[-1][1]['quarantined_before_ingress_validation'] is True
    assert worker.ingress.fault is None
    scan.header.stamp.nanosec = 250_000_001
    with pytest.raises(ValueError, match='unrelated scan failure'):
        worker.observed_callback(LaserScan, '/scan',
            lambda _: (_ for _ in ()).throw(ValueError('unrelated scan failure')))(
                serialize_message(scan), {})


def test_r05_contact_query_revocation_requires_coverage_mask_and_zero_closed_state(tmp_path):
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control

    original = NS(response=NS(
        contact_capability_state=Control.Response.CAPABILITY_VERIFIED))
    def query(state, *, backend_id=0):
        return NS(response=NS(contact_capability_state=state,
            proof_backend_instance_id=backend_id, proof_session_id='',
            proof_config_hash='', proof_asset_manifest_sha256='', proof_world_name='',
            proof_collision_registry_sha256='', proof_physics_engine_fingerprint_sha256='',
            probe_model_entity_id=0, probe_collision_entity_id=0,
            floor_collision_entity_id=0, contact_sample_count=0,
            covered_empty_sample_count=0))
    (tmp_path/'native-events.jsonl').write_text(json.dumps({
        'kind':'B23_CONTACT_COVERAGE_MASKED','fields':{'masked':'1',
        'entity':'b2_training_arena::mecanum_b2::base_link::collision',
        'iteration':'123'}})+'\n')
    state=NS(local_zero_override=True, fault_flags=16)
    result=verify_r05_contact_query_revocation(tmp_path, original_ack=original,
        replay_ack=query(Control.Response.CAPABILITY_FAILED),
        fresh_ack=query(Control.Response.CAPABILITY_FAILED), backend_state=state)
    assert result['masked_iteration'] == 123
    assert result['replay_query_revoked'] and result['fresh_query_revoked']
    with pytest.raises(RuntimeError, match='replay QUERY returned a stale verified proof'):
        verify_r05_contact_query_revocation(tmp_path, original_ack=original,
            replay_ack=query(Control.Response.CAPABILITY_VERIFIED, backend_id=9),
            fresh_ack=query(Control.Response.CAPABILITY_FAILED), backend_state=state)


def test_r05_accepts_only_exact_native_rejection_for_fresh_revoked_query():
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendControlError
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    request=NS(operation=Control.Request.OP_VERIFY_CONTACT_CAPABILITY,
        probe_action=Control.Request.PROBE_ACTION_QUERY,
        probe_start_request_sequence=7)
    response=NS(result=Control.Response.RESULT_REJECTED,
        reason_code=Control.Response.REASON_CONTACT_PROBE_FAILED,
        contact_capability_state=Control.Response.CAPABILITY_FAILED)
    ack=NS(request=request,response=response)
    assert expected_r05_revoked_query_ack(BackendControlError('backend control rejected: 16',ack),
        start_request_sequence=7) is ack
    with pytest.raises(RuntimeError,match='does not match revoked probe identity/state'):
        wrong_request=NS(operation=request.operation,probe_action=request.probe_action,
            probe_start_request_sequence=8)
        expected_r05_revoked_query_ack(BackendControlError('wrong request',
            NS(request=wrong_request,response=response)),start_request_sequence=7)
    with pytest.raises(RuntimeError,match='lacks its native ACK'):
        expected_r05_revoked_query_ack(BackendControlError('no ACK'),start_request_sequence=7)


@pytest.mark.parametrize('case,mode,ingress_count', [
    ('R03a','drop_policy_once',0),
    ('R03b','mutate_policy_transition_id_once',1),
])
def test_r03_verifier_binds_native_receipt_fault_to_real_policy_publication(
        tmp_path, case, mode, ingress_count):
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
    from rclpy.serialization import serialize_message

    native = tmp_path/'native-events.jsonl'
    receipt = FinalIssuedCommandReceipt()
    receipt.source = FinalIssuedCommandReceipt.SOURCE_POLICY
    receipt.sequence = 1
    receipt.source_instance_id = 9
    receipt.step_index = 1
    receipt.transition_id = 'policy-1'
    receipt.final_publisher_instance_id = 42
    receipt.final_publish_sequence = 77
    receipt_bytes = serialize_message(receipt)
    publication = {'event':'policy_final_published','facts':{
        'source':'POLICY','source_sequence':1,'source_instance_id':9,
        'step_index':1,'transition_id':'policy-1','steady_ns':90,
        'publisher_instance_id':42,'publish_sequence':77,
        'receipt_cdr_hex':receipt_bytes.hex()}}
    (tmp_path/'policy_final_published.jsonl').write_text(
        json.dumps(publication,separators=(',',':'))+'\n')
    native.write_text(json.dumps({'kind':'B23_RECEIPT_FAULT','fields':{
        'mode':mode,'publisher':'42','sequence':'77','source_sequence':'1',
        'original_transition_id':'policy-1',
        'mutated_transition_id':'policy-1.b23-injected-mismatch'}})+'\n')
    if ingress_count:
        with native.open('a') as stream:
            stream.write(json.dumps({'kind':'B23_POLICY_RECEIPT_INGRESS',
                'fields':{'sequence':'77'}})+'\n')
    io=NS(descriptor={'run_root':str(tmp_path)},
        events=[], final=NS(publisher_instance_id=42),
        ingress=NS(receipts=[],
            backend_state=NS(fault_flags=7,local_zero_override=True)),
        now=lambda:100, deadline_ns=200, pause=None)
    error=RuntimeError('native fault flags=7')

    result=asyncio.run(verify_r03_receipt_fault(io,case=case,step_index=1,error=error))

    assert result['expected_fault'] is True
    assert result['stop_reason']=='native_fault_flags=7'
    assert result['published_policy_sequence']==77
    assert result['policy_step_committed'] is False
    assert result['local_zero_override'] is True
    if case == 'R03a':
        assert io.ingress.receipts == []  # the faulted publication was not received
    with pytest.raises(RuntimeError,match='expected cutoff/receipt path'):
        asyncio.run(verify_r03_receipt_fault(io,case=case,step_index=1,error=RuntimeError('unexpected')))


def test_r02f_requires_policy_hold_rejection_and_exact_zero_native_receipt():
    from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
    from mecanum_nav_rl_interfaces.msg import CommandEnvelope, FinalIssuedCommandReceipt
    receipt=FinalIssuedCommandReceipt()
    receipt.source=FinalIssuedCommandReceipt.SOURCE_SAFE_STOP
    receipt.final_command.linear.x=receipt.final_command.linear.y=receipt.final_command.angular.z=0.
    receipt.final_publisher_instance_id=17
    receipt.final_publish_sequence=42
    state=NS(fault_flags=0, local_zero_override=False, applied_receipt_valid=True,
        applied_final_publisher_instance_id=17, applied_final_publish_sequence=42,
        applied_physics_iteration=101)
    io=NS(events=[('SAFETY_REJECTED', {'sequence':7,
        'source':CommandEnvelope.SOURCE_SAFE_STOP,
        'candidate_sequence':1,'candidate_source':CommandEnvelope.SOURCE_POLICY,
        'candidate_source_instance_id':33,'reasons':['POLICY_HELD']})],
        ingress=NS(receipts=[]), policy_source_id=33)
    result=verify_r02f_safety_hold(io,step_index=1,receipt=receipt,backend_state=state)
    assert result == {'safety_rejected':True,'reasons':['POLICY_HELD'],
        'safe_stop_applied':True,'final_publish_sequence':42,'backend_iteration':101,
        'policy_receipt_absent':True}
    io.events=[]
    with pytest.raises(RuntimeError,match='Safety rejection'):
        verify_r02f_safety_hold(io,step_index=1,receipt=receipt,backend_state=state)
    io.events=[('SAFETY_REJECTED', {'sequence':7,
        'source':CommandEnvelope.SOURCE_SAFE_STOP,
        'candidate_sequence':1,'candidate_source':CommandEnvelope.SOURCE_POLICY,
        'candidate_source_instance_id':33,'reasons':['POLICY_HELD']})]
    io.ingress.receipts=[NS(source=ReceiptSource.POLICY,sequence=1)]
    with pytest.raises(RuntimeError,match='reached the final receipt'):
        verify_r02f_safety_hold(io,step_index=1,receipt=receipt,backend_state=state)
    io.ingress.receipts=[]
    receipt.source=FinalIssuedCommandReceipt.SOURCE_POLICY
    with pytest.raises(RuntimeError,match='held POLICY as zero SAFE_STOP'):
        verify_r02f_safety_hold(io,step_index=1,receipt=receipt,backend_state=state)
    receipt.source=FinalIssuedCommandReceipt.SOURCE_SAFE_STOP
    receipt.final_command.linear.x=0.01
    with pytest.raises(RuntimeError,match='held POLICY as zero SAFE_STOP'):
        verify_r02f_safety_hold(io,step_index=1,receipt=receipt,backend_state=state)


def test_r02g_close_routes_require_exact_native_evidence():
    from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    receipt=FinalIssuedCommandReceipt()
    receipt.source=receipt.SOURCE_SAFE_STOP
    receipt.final_publisher_instance_id=17
    receipt.final_publish_sequence=42
    state=NS(fault_flags=0,local_zero_override=False,applied_receipt_valid=True,
        applied_final_publisher_instance_id=17,applied_final_publish_sequence=42)
    io=NS(ingress=NS(receipts=[NS(source=ReceiptSource.POLICY)],lock=threading.RLock()))
    result=verify_r02g_close(io,route='safe_stop',policy_receipt_count=1,
        zero_receipt=receipt,backend_state=state)
    assert result['safe_stop_receipt_applied'] is True
    for route in ('admission_inhibited','zero_only'):
        assert verify_r02g_close(io,route=route,policy_receipt_count=1,
            zero_receipt=receipt,backend_state=state)['route']==route
    ack=NS(request=NS(operation=Control.Request.OP_INHIBIT),response=NS(
        result=Control.Response.RESULT_APPLIED,reason_code=Control.Response.REASON_NONE))
    inhibited=NS(fault_flags=0,local_zero_override=True)
    assert verify_r02g_close(io,route='op_inhibit',policy_receipt_count=1,
        backend_state=inhibited,control_ack=ack)['closing_ack_applied'] is True
    io.ingress.receipts.append(NS(source=ReceiptSource.POLICY))
    with pytest.raises(RuntimeError,match='POLICY receipt after the close trigger'):
        verify_r02g_close(io,route='safe_stop',policy_receipt_count=1,
            zero_receipt=receipt,backend_state=state)
    with pytest.raises(RuntimeError,match='OP_INHIBIT lacks APPLIED'):
        verify_r02g_close(io,route='op_inhibit',policy_receipt_count=1,
            backend_state=inhibited,control_ack=NS(request=NS(operation=0),response=NS(result=0,reason_code=0)))
    with pytest.raises(RuntimeError,match='exact native-applied zero receipt'):
        verify_r02g_close(io,route='zero_only',policy_receipt_count=1,
            zero_receipt=receipt,backend_state=NS(**{**vars(state),'applied_final_publish_sequence':41}))
def test_r02g_close_accepts_production_deque_and_rejects_late_policy_receipt():
    from collections import deque
    from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
    receipt=FinalIssuedCommandReceipt()
    receipt.source=receipt.SOURCE_SAFE_STOP
    receipt.final_publisher_instance_id=17
    receipt.final_publish_sequence=42
    state=NS(fault_flags=0,local_zero_override=False,applied_receipt_valid=True,
        applied_final_publisher_instance_id=17,applied_final_publish_sequence=42)
    io=NS(ingress=NS(receipts=deque([NS(source=ReceiptSource.POLICY)]),lock=threading.RLock()))
    assert verify_r02g_close(io,route='safe_stop',policy_receipt_count=1,
        zero_receipt=receipt,backend_state=state)['route']=='safe_stop'
    io.ingress.receipts.append(NS(source=ReceiptSource.POLICY))
    with pytest.raises(RuntimeError,match='POLICY receipt after the close trigger'):
        verify_r02g_close(io,route='safe_stop',policy_receipt_count=1,
            zero_receipt=receipt,backend_state=state)


def test_r02g_op_inhibit_resolves_installed_control_operation():
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    assert r02g_inhibit_operation() == Control.Request.OP_INHIBIT


def test_r02g_waits_for_exact_receipt_application_not_latest_status():
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
    receipt=FinalIssuedCommandReceipt()
    receipt.source=receipt.SOURCE_SAFE_STOP
    receipt.final_publisher_instance_id=17
    receipt.final_publish_sequence=42
    latest=NS(applied_final_publish_sequence=44,local_zero_override=False)
    exact_state=NS(applied_final_publisher_instance_id=17,
        applied_final_publish_sequence=42,applied_receipt_valid=True,
        local_zero_override=False,fault_flags=0)
    application={'state':exact_state,'received_ns':1234}
    lookups=[]; waits=[]
    io=NS(ingress=NS(backend_state=latest,
        application_for_receipt=lambda selected:(lookups.append(selected),application)[1]))
    async def until(predicate,*,deadline_ns,phase):
        waits.append((deadline_ns,phase))
        return predicate()
    io.until=until
    result=asyncio.run(await_r02g_exact_safe_stop_application(
        io,receipt=receipt,deadline_ns=5678,route='admission_inhibited'))
    assert result is application
    assert lookups == [receipt]
    assert waits == [(5678,'R02g exact native SAFE_STOP application: admission_inhibited')]
    assert result['state'].applied_final_publish_sequence == receipt.final_publish_sequence


@pytest.mark.parametrize('zero_only', [False, True])
def test_r02g_admission_close_holds_policy_before_revoking_gate(zero_only):
    calls = []
    io = NS(ingress=NS(inhibit=lambda *, zero_only: calls.append(('admission', zero_only))))
    adapter = NS(set_policy_hold=lambda enabled: calls.append(('hold', enabled)),
        set_stream_enabled=lambda enabled: calls.append(('stream', enabled)))

    r02g_close_admission(io, adapter, zero_only=zero_only)

    assert calls == [('hold', True), ('admission', zero_only), ('stream', True)]


@pytest.mark.parametrize('case,method_name,message', [
    ('R04a','on_safety_input',NS(admission_state=1,ADMISSION_POLICY_OPEN=1,
        sample_sequence=7,header=NS(stamp=NS(sec=3,nanosec=4)))),
    ('R04b','on_safety_input',NS(admission_state=1,ADMISSION_POLICY_OPEN=1,
        sample_sequence=8,header=NS(stamp=NS(sec=3,nanosec=5)))),
    ('R04c','on_scan',NS(header=NS(stamp=NS(sec=4,nanosec=5)))),
    ('R04d','on_lifecycle',NS(sequence=6,episode_generation=2,reset_epoch=3,
        runtime_generation=4,header=NS(stamp=NS(sec=5,nanosec=6)))),
])
def test_r04_fault_dispatch_uses_bound_safety_callbacks(case, method_name, message):
    class FakeAdapter:
        def __init__(self): self.calls = []
        def on_safety_input(self, value): self.calls.append(('on_safety_input', value))
        def on_scan(self, value): self.calls.append(('on_scan', value))
        def on_lifecycle(self, value): self.calls.append(('on_lifecycle', value))

    enable_r04_adapter_fault_dispatch(FakeAdapter)
    adapter, events = FakeAdapter(), []
    state = install_r04_delivery_fault(adapter, case,
        lambda name, facts: events.append((name, facts)), delay_s=0.01)

    async def exercise():
        getattr(adapter, method_name)(message)
        await asyncio.sleep(0.03)
    asyncio.run(exercise())

    if case == 'R04b':
        assert state['triggered'] == 1
        assert adapter.calls == []
        closed = NS(admission_state=0, ADMISSION_POLICY_OPEN=1,
            sample_sequence=9, header=message.header)
        adapter.on_safety_input(closed)
        assert adapter.calls == [('on_safety_input', closed)]
        assert [name for name, _ in events] == ['B23_R04_NOISY_ODOMETRY_DROPPED']
    else:
        assert state['triggered'] == 1 and state['scheduled'] == 1
        for timer in state['timers']:
            timer.join(timeout=0.2)
        assert state['delivered'] == 1
        assert len(adapter.calls) == 1 and adapter.calls[0][0] == method_name
        assert [name for name, _ in events] == [
            'B23_R04_DELIVERY_DELAY_SCHEDULED','B23_R04_DELIVERY_DELAYED_CALLBACK']
        assert events[0][1]['source_stamp_ns'] == (
            message.header.stamp.sec*1_000_000_000+message.header.stamp.nanosec)


def test_r04b_accepts_only_bound_pre_safety_candidate_and_no_downstream_effect():
    from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity, TransitionIdentity
    from mecanum_nav_rl.runtime_simulation.b23_runner import verify_r04b_missing_noisy_admission

    transition = TransitionIdentity(EpisodeLifecycleIdentity(1, 1, 2), 1,
        '31005bb2-c071-59b9-b01b-bd9b246f2d9c')
    issued = [{'event':'policy_adapter_issued','run_id':'RUN-TEST',
        'invocation_id':'INV-TEST','facts':{'identity':[1,1,2], 'sequence':1,
            'step_index':1,'source_instance_id':77,'steady_ns':100,
            'transition_id':transition.transition_id}}]
    events = [('policy_adapter_issued', issued[0]['facts']),
        ('B23_R04_NOISY_ODOMETRY_DROPPED', {'case':'R04b','sample_sequence':9,'steady_ns':110}),
        ('B23_R04_NOISY_ODOMETRY_DROPPED', {'case':'R04b','sample_sequence':10,'steady_ns':120})]
    result = verify_r04b_missing_noisy_admission(issued_rows=issued,
        transition_identity=transition, run_id='RUN-TEST', invocation_id='INV-TEST',
        policy_receipts=[], final_rows=[], applied_rows=[], committed_rows=[],
        worker_events=events)
    assert result['adapter_candidates'] == 1
    assert result['native_policy_receipts'] == result['final_publications'] == 0
    assert result['backend_applications'] == result['b1_policy_commits'] == 0
    assert result['dropped_sample_sequence'] == 9
    assert result['dropped_sample_sequences'] == [9, 10]
    assert result['missing_admission_after_drop'] is True

    with pytest.raises(RuntimeError, match='active B1 slot'):
        verify_r04b_missing_noisy_admission(issued_rows=[{
            **issued[0], 'facts':{**issued[0]['facts'], 'identity':[1, 9, 2]}}],
            transition_identity=transition, run_id='RUN-TEST', invocation_id='INV-TEST',
            policy_receipts=[], final_rows=[], applied_rows=[], committed_rows=[],
            worker_events=events)
    with pytest.raises(RuntimeError, match='downstream ledger'):
        verify_r04b_missing_noisy_admission(issued_rows=issued,
            transition_identity=transition, run_id='RUN-TEST', invocation_id='INV-TEST',
            policy_receipts=[], final_rows=[{'facts':{'transition_id':transition.transition_id}}],
            applied_rows=[], committed_rows=[], worker_events=events)
    with pytest.raises(RuntimeError, match='not bound after the active candidate'):
        verify_r04b_missing_noisy_admission(issued_rows=issued,
            transition_identity=transition, run_id='RUN-TEST', invocation_id='INV-TEST',
            policy_receipts=[], final_rows=[], applied_rows=[], committed_rows=[],
            worker_events=[('B23_R04_NOISY_ODOMETRY_DROPPED',
                {'case':'R04b','sample_sequence':9,'steady_ns':99})])


def test_r04c_delays_scan_only_after_control_policy_commit_path():
    assert r04_policy_step_fault_plan('R04a') == ('R04a', None)
    assert r04_policy_step_fault_plan('R04b') == ('R04b', None)
    assert r04_policy_step_fault_plan('R04c') == (None, 'R04c')
    with pytest.raises(ValueError, match='unsupported R04 POLICY-step fault plan'):
        r04_policy_step_fault_plan('R04d')

    source = textwrap.dedent(__import__('inspect').getsource(runner_module.training_child))
    tree = ast.parse(source)
    fault_calls = [node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name) and node.func.value.id == 'io'
        and node.func.attr == 'policy_step'
        and any(keyword.arg == 'measurement_fault_case' for keyword in node.keywords)]
    fault_arguments = [next(keyword.value for keyword in node.keywords
        if keyword.arg == 'measurement_fault_case') for node in fault_calls]
    assert any(isinstance(value, ast.Name) and value.id == 'initial_fault_case'
        for value in fault_arguments)
    assert any(isinstance(value, ast.Name) and value.id == 'followup_fault_case'
        for value in fault_arguments)
    source = textwrap.dedent(__import__('inspect').getsource(runner_module.training_child))
    assert "R04c stale scan allowed the next POLICY slot" not in source
    assert 'R04c stale scan Safety rejection and applied zero' in source
    assert 'verify_r04c_stale_issuance_commit_rejected' in source
    assert 'require_r04c_fault_state' in source
    assert 'R04C_B1_STALE_ISSUANCE_COMMIT_REJECTED' in source
    assert 'fresh_recovery_step_index' in source
    assert 'policy_step_index=recovery_step' in source


def test_r04d_ingress_lifecycle_delivery_is_delayed_on_owned_pump():
    from mecanum_nav_rl.runtime_simulation.b23_runner import TrainingWorkerIO

    now = [1_000_000_000]
    delivered, events = [], []
    io = object.__new__(TrainingWorkerIO)
    io._r04d_fault_state = {'case':'R04d','delay_s':.650,'ingress_scheduled':False}
    io._r04d_pending_ingress_lifecycle = (1_625_000_000,
        lambda message: delivered.append(message), object(), 900_000_000)
    io.now = lambda: now[0]
    io.emit = lambda name, facts: events.append((name, facts))

    io._deliver_r04d_ingress_lifecycle_if_due()
    assert delivered == []
    now[0] = 1_624_999_999
    io._deliver_r04d_ingress_lifecycle_if_due()
    assert delivered == []
    now[0] = 1_625_000_001
    io._deliver_r04d_ingress_lifecycle_if_due()

    assert len(delivered) == 1
    assert events == [('B23_R04_INGRESS_DELIVERY_COMPLETED', {
        'case':'R04d','source_stamp_ns':900_000_000,
        'due_ns':1_625_000_000,'delivery_ns':1_625_000_001})]
    assert io._r04d_pending_ingress_lifecycle is None


def test_r04d_ingress_binding_switch_follows_final_publisher_switch():
    from mecanum_nav_rl.runtime_simulation.b23_runner import (
        r04d_final_publisher_precedes_ingress, r04d_ingress_lifecycle_delay_s)

    safety_lifecycle_delay_s = 0.650
    final_lifecycle_delay_s = 0.700
    ingress_delay_s = r04d_ingress_lifecycle_delay_s(safety_lifecycle_delay_s)
    # Safety delivery remains at 650 ms; final publisher switches at 700 ms;
    # ingress switches after it, so a receipt cannot cross an identity gap.
    safety_delivery_delay_s = 0.650
    assert safety_delivery_delay_s < final_lifecycle_delay_s < ingress_delay_s
    assert ingress_delay_s == 0.725
    assert r04d_final_publisher_precedes_ingress(700_000_000, 725_000_000)
    assert r04d_final_publisher_precedes_ingress(725_000_000, 725_000_000)
    assert not r04d_final_publisher_precedes_ingress(730_000_000, 725_000_000)
    assert not r04d_final_publisher_precedes_ingress(None, 725_000_000)


def test_r04d_ingress_binding_delay_rejects_invalid_final_delay():
    import pytest
    from mecanum_nav_rl.runtime_simulation.b23_runner import r04d_ingress_lifecycle_delay_s

    for value in (0, -0.1, None, '0.7', True):
        with pytest.raises(ValueError, match='Safety lifecycle delay must be positive'):
            r04d_ingress_lifecycle_delay_s(value)


def test_r04d_ingress_holds_repeated_new_identity_until_first_delivery():
    from mecanum_nav_rl_interfaces.msg import SafetyLifecycleState
    from rclpy.serialization import serialize_message
    from mecanum_nav_rl.runtime_simulation.b23_runner import TrainingWorkerIO

    target=SafetyLifecycleState(); target.sequence=5
    repeated=SafetyLifecycleState(); repeated.sequence=6
    delivered,events=[],[]
    io=object.__new__(TrainingWorkerIO)
    io._r04d_fault_state={'case':'R04d','delay_s':.650,'ingress_scheduled':True,
        'ingress_repeats_held':0}
    io._r04d_pending_ingress_lifecycle=(10_000,(lambda value:delivered.append(value)),
        target,900)
    io.now=lambda:20_000
    io.emit=lambda name,facts:events.append((name,facts))
    receive=io.observed_callback(SafetyLifecycleState,'/mecanum/safety_lifecycle_state',
        lambda value:delivered.append(value))
    assert receive(serialize_message(repeated),{}) is None
    assert delivered==[] and io._r04d_fault_state['ingress_repeats_held']==1
    assert events[-1][0]=='B23_R04_INGRESS_LIFECYCLE_REPEAT_HELD'

    io._deliver_r04d_ingress_lifecycle_if_due()
    assert delivered==[target]
    assert io._r04d_pending_ingress_lifecycle is None


def test_r04d_safety_lifecycle_repeats_stay_held_until_original_delivers():
    from mecanum_nav_rl.runtime_simulation.b23_runner import install_r04_delivery_fault

    class Adapter:
        def __init__(self): self.calls = []
        def on_lifecycle(self, message): self.calls.append(message.sequence)
        def on_scan(self, message): pass
        def on_safety_input(self, message): pass

    from mecanum_nav_rl.runtime_simulation.b23_runner import enable_r04_adapter_fault_dispatch
    enable_r04_adapter_fault_dispatch(Adapter)
    adapter, events = Adapter(), []
    state = install_r04_delivery_fault(adapter, 'R04d',
        lambda name, facts: events.append((name, facts)), delay_s=.04)
    first = NS(sequence=6, episode_generation=2, reset_epoch=3, runtime_generation=4,
        header=NS(stamp=NS(sec=5, nanosec=6)))
    repeated = NS(sequence=6, episode_generation=2, reset_epoch=3, runtime_generation=4,
        header=NS(stamp=NS(sec=5, nanosec=7)))
    adapter.on_lifecycle(first)
    adapter.on_lifecycle(repeated)
    assert adapter.calls == []
    assert state['repeat_held'] == 1
    assert [name for name, _ in events] == [
        'B23_R04_DELIVERY_DELAY_SCHEDULED','B23_R04_LIFECYCLE_REPEAT_HELD']

    async def wait_delivery():
        await asyncio.sleep(.06)
    asyncio.run(wait_delivery())
    for timer in state['timers']:
        timer.join(timeout=.2)
    assert adapter.calls == [6]
    assert state['delivered'] == 1
    adapter.on_lifecycle(repeated)
    assert adapter.calls == [6,6]


def test_r04d_stale_safety_observation_must_follow_delayed_lifecycle_delivery():
    from mecanum_nav_rl.runtime_simulation.b23_runner import r04d_stale_safety_rejection_after_delivery

    before_final_delivery = ('SAFETY_REJECTED', {'reasons':['LIFECYCLE_STALE_OR_FUTURE'],
        'steady_ns':660, 'ros_ns':1_850_000_001})
    final_delivery_ns = 700
    after_final_delivery = ('SAFETY_REJECTED', {'reasons':['LIFECYCLE_STALE_OR_FUTURE'],
        'steady_ns':720, 'ros_ns':1_850_000_001})
    assert r04d_stale_safety_rejection_after_delivery(
        [before_final_delivery, after_final_delivery], delivery_ns=final_delivery_ns,
        source_stamp_ns=1_050_000_000) is after_final_delivery[1]
    assert r04d_stale_safety_rejection_after_delivery(
        [before_final_delivery], delivery_ns=final_delivery_ns,
        source_stamp_ns=1_050_000_000) is None
    not_stale_enough = ('SAFETY_REJECTED', {'reasons':['LIFECYCLE_STALE_OR_FUTURE'],
        'steady_ns':700, 'ros_ns':1_550_000_000})
    assert r04d_stale_safety_rejection_after_delivery(
        [not_stale_enough], delivery_ns=final_delivery_ns,
        source_stamp_ns=1_050_000_000) is None


def test_r04d_final_lifecycle_delivery_is_pinned_to_sequence_and_identity():
    from mecanum_nav_rl.runtime_simulation.b23_runner import r04d_final_lifecycle_delivery

    expected = {'event':'R04D_FINAL_LIFECYCLE_DELIVERY_COMPLETED','facts':{
        'sequence':6, 'identity':[2,2,2], 'delivery_ns':700}}
    wrong_sequence = {'event':'R04D_FINAL_LIFECYCLE_DELIVERY_COMPLETED','facts':{
        'sequence':5, 'identity':[2,2,2], 'delivery_ns':690}}
    wrong_identity = {'event':'R04D_FINAL_LIFECYCLE_DELIVERY_COMPLETED','facts':{
        'sequence':6, 'identity':[2,2,1], 'delivery_ns':695}}
    assert r04d_final_lifecycle_delivery(
        [wrong_sequence, wrong_identity, expected], sequence=6, identity=[2,2,2]) == expected['facts']
    assert r04d_final_lifecycle_delivery(
        [wrong_sequence, wrong_identity], sequence=6, identity=[2,2,2]) is None


def test_r04d_final_new_context_safe_stop_is_held_for_identity_isolation():
    import json
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from types import SimpleNamespace as NS
    from mecanum_nav_rl.runtime_simulation.b23_runner import r04d_final_safe_stop_dispatch

    with TemporaryDirectory() as directory:
        marker = Path(directory)/'marker.json'
        marker.write_text(json.dumps({'schema':'b23_r04d_delay_marker/v1',
            'run_id':'RUN-1','invocation_id':'INV-1','baseline_identity':[1,2,3],
            'safe_stop_source_instance_id':77,'delay_ns':700_000_000}))
        node=NS(_b23_r04d_run_id='RUN-1',_b23_r04d_invocation_id='INV-1')
        envelope=NS(source=1,source_instance_id=77,sequence=8,episode_generation=2,
            reset_epoch=2,runtime_generation=3)
        calls,events,scheduled=[],[],[]
        dispatch=r04d_final_safe_stop_dispatch(lambda owner,msg:calls.append(msg.sequence),
            marker,lambda name,facts:events.append((name,facts)),
            lambda owner,due,callback:scheduled.append((due,callback)),safe_stop_source=1)
        assert dispatch(node,envelope) is None
        assert calls == [] and len(scheduled)==1
        assert events[0][0]=='R04D_FINAL_NEW_CONTEXT_SAFE_STOP_HELD'
        assert scheduled[0][0] >= events[0][1]['received_ns'] + 700_000_000
        scheduled[0][1]()
        assert calls == [8]
        assert events[1][0]=='R04D_FINAL_NEW_CONTEXT_SAFE_STOP_RELEASED'


def test_r04d_final_publisher_keeps_bound_identity_until_stale_safety_window():
    import json
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from types import SimpleNamespace as NS
    from mecanum_nav_rl.runtime_simulation.b23_runner import r04d_final_lifecycle_dispatch

    with TemporaryDirectory() as directory:
        marker_path = Path(directory) / 'r04d-final-lifecycle-delay.json'
        node = NS(_b23_r04d_run_id='RUN-1', _b23_r04d_invocation_id='INV-1')
        delivered, events, scheduled = [], [], []
        original = lambda owner, message: delivered.append((owner, message.sequence))
        dispatch = r04d_final_lifecycle_dispatch(original, marker_path,
            lambda name, facts: events.append((name, facts)),
            lambda owner, due_ns, callback: scheduled.append((owner, due_ns, callback)))
        before = NS(sequence=4, episode_generation=1, reset_epoch=2,
            runtime_generation=3, header=NS(stamp=NS(sec=1, nanosec=2)))
        dispatch(node, before)
        assert delivered == [(node, 4)]
        marker_path.write_text(json.dumps({'schema':'b23_r04d_delay_marker/v1',
            'run_id':'RUN-1','invocation_id':'INV-1','baseline_sequence':4,
            'baseline_identity':[1,2,3],'armed_ns':100,'delay_ns':700_000_000}))
        changed = NS(sequence=5, episode_generation=2, reset_epoch=2,
            runtime_generation=3, header=NS(stamp=NS(sec=2, nanosec=3)))
        dispatch(node, changed)
        dispatch(node, changed)
        assert delivered == [(node, 4)]
        assert len(scheduled) == 1
        assert scheduled[0][1] >= events[0][1]['received_ns'] + 700_000_000
        assert events[0][0] == 'R04D_FINAL_LIFECYCLE_DELIVERY_SCHEDULED'
        assert events[0][1]['identity'] == [2,2,3]
        scheduled[0][2]()
        assert delivered == [(node, 4), (node, 5)]
        assert events[1][0] == 'R04D_FINAL_LIFECYCLE_DELIVERY_COMPLETED'


def test_r04d_final_lifecycle_delay_rejects_foreign_marker():
    import json
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from types import SimpleNamespace as NS
    import pytest
    from mecanum_nav_rl.runtime_simulation.b23_runner import r04d_final_lifecycle_dispatch

    with TemporaryDirectory() as directory:
        marker_path = Path(directory) / 'r04d-final-lifecycle-delay.json'
        marker_path.write_text(json.dumps({'schema':'b23_r04d_delay_marker/v1',
            'run_id':'OTHER','invocation_id':'INV-1','baseline_sequence':4,
            'baseline_identity':[1,2,3],'armed_ns':100,'delay_ns':700_000_000}))
        node = NS(_b23_r04d_run_id='RUN-1', _b23_r04d_invocation_id='INV-1')
        message = NS(sequence=5, episode_generation=2, reset_epoch=2,
            runtime_generation=3, header=NS(stamp=NS(sec=2, nanosec=3)))
        dispatch = r04d_final_lifecycle_dispatch(lambda *_: None, marker_path,
            lambda *_: None, lambda *_: None)
        with pytest.raises(RuntimeError, match='ownership/schema mismatch'):
            dispatch(node, message)


def test_r04d_durable_marker_write_does_not_block_ros_pump(monkeypatch):
    import inspect
    from mecanum_nav_rl.runtime_simulation.b23_runner import write_record_once_async

    entered = threading.Event()
    release = threading.Event()
    writer_thread = []

    def slow_durable_write(path, record):
        writer_thread.append(threading.get_ident())
        entered.set()
        if not release.wait(1.0):
            raise TimeoutError('fake durable write was not released')
        return 'a' * 64

    monkeypatch.setattr(runner_module, 'write_record_once', slow_durable_write)

    async def exercise():
        pulses = 0
        finished = False

        async def pump_pulses():
            nonlocal pulses
            while not finished:
                pulses += 1
                await asyncio.sleep(.005)

        pump = asyncio.create_task(pump_pulses())
        write = asyncio.create_task(write_record_once_async('marker', {}))
        assert await asyncio.to_thread(entered.wait, .5)
        await asyncio.sleep(.04)
        progressed_while_writer_blocked = pulses >= 4 and not write.done()
        release.set()
        digest = await asyncio.wait_for(write, .5)
        finished = True
        await pump
        return progressed_while_writer_blocked, digest

    progressed, digest = asyncio.run(asyncio.wait_for(exercise(), 1.5))
    assert progressed is True
    assert digest == 'a' * 64
    assert writer_thread and writer_thread[0] != threading.get_ident()

    training_source = inspect.getsource(runner_module.training_child)
    ast.parse(training_source)
    assert "await write_record_once_async(marker_path" in training_source


def test_r04a_requires_the_delayed_stale_input_rejection_and_safety_block():
    # Use the exact event names and ordering emitted by the production worker.
    io = NS(policy_source_id=9, events=[
        ('B23_R04_DELIVERY_DELAY_SCHEDULED', {'case':'R04a','delay_s':.3,
            'callback_received_ns':100,'source_stamp_ns':77,'sample_sequence':22}),
        ('B23_R04_DELIVERY_DELAYED_CALLBACK', {'case':'R04a','delay_s':.3,
            'delivery_ns':300_000_101,'source_stamp_ns':77,'sample_sequence':22}),
        ('SAFETY_REJECTED', {'reasons':['NOISY_STALE_OR_FUTURE'],
            'steady_ns':300_000_103,'ros_ns':1_000_000_000}),
    ])
    result = verify_r04_stale_delivery(io, case='R04a')
    assert result['delayed_input_rejected'] is True
    assert result['safety_blocked'] is True
    assert result['fresh_policy_recovery'] is False
    io.events.append(('SAFETY_ACCEPTED', {'candidate_source':1,'steady_ns':300_000_104}))
    with pytest.raises(RuntimeError, match='accepted POLICY after delayed-input invalidation'):
        verify_r04_stale_delivery(io, case='R04a')
    io.events.pop()
    io.events[1][1]['sample_sequence'] = 23
    with pytest.raises(RuntimeError, match='identity does not match'):
        verify_r04_stale_delivery(io, case='R04a')


def test_r04a_waits_boundedly_for_production_safety_tick_after_callback():
    events = [
        ('B23_R04_DELIVERY_DELAYED_CALLBACK', {'case':'R04a','delivery_ns':300}),
    ]
    calls = []
    safety_calls = []
    class SafetyAdapter:
        def set_policy_hold(self, value):
            safety_calls.append(('policy_hold', value))
        def set_stream_enabled(self, value):
            safety_calls.append(('stream_enabled', value))
            if value:
                events.append(('SAFETY_REJECTED', {'reasons':['NOISY_STALE_OR_FUTURE'],
                    'steady_ns':302}))
    async def until(predicate, *, deadline_ns, phase, expected_native_fault_flags=None):
        calls.append((deadline_ns, phase, expected_native_fault_flags))
        return predicate()
    io = NS(events=events, until=until, safety=NS(local_training=SafetyAdapter()))
    result = __import__('asyncio').run(await_r04a_production_rejection(io, deadline_ns=1_000))
    assert result['steady_ns'] == 302
    assert safety_calls == [('policy_hold', True), ('stream_enabled', True)]
    assert calls == [(1_000,'R04a bounded production Safety rejection after delayed stale input', (4, 6))]


def test_r04a_waits_for_backend_zero_status_after_safety_rejection():
    from mecanum_nav_rl_interfaces.msg import SimulationContactState
    state = NS(fault_flags=SimulationContactState.FAULT_COMMAND_SEQUENCE
        | SimulationContactState.FAULT_COMMAND_STALE,
        local_zero_override=True, actuator_inhibited=True, status_sequence=8)
    ingress = NS(backend_state=state, backend_received_ns=99)
    calls = []
    events = []
    clock = {'advance':True}
    async def until(predicate, *, deadline_ns, phase, expected_native_fault_flags=None):
        calls.append((deadline_ns, phase, expected_native_fault_flags))
        assert predicate() is None
        if clock['advance']:
            ingress.backend_received_ns = 101
            return predicate()
        raise TimeoutError(phase)
    io = NS(ingress=ingress, until=until,
        emit=lambda name, facts: events.append((name, facts)))
    result = asyncio.run(await_r04a_post_rejection_zero(io,
        {'steady_ns':100}, deadline_ns=200))
    assert result == {'status_sequence':8,'status_received_ns':101,
        'fault_flags':6,'local_zero_override':True,'actuator_inhibited':True,
        'after_safety_rejection':True}
    assert calls == [(200,'R04a backend zero status sampled after stale Safety rejection', (4, 6))]
    assert events == [('R04A_POST_REJECTION_ZERO_OBSERVED', result)]
    clock['advance'] = False
    ingress.backend_received_ns = 99
    with pytest.raises(TimeoutError):
        asyncio.run(await_r04a_post_rejection_zero(io, {'steady_ns':100}, deadline_ns=200))


def test_r04a_waits_for_scheduled_callback_after_step_fault_without_resetting_deadline():
    clock = {'ns':0}
    state = {'triggered':1,'scheduled':1,'delivered':0}
    events = []
    async def pause(duration_s):
        clock['ns'] += int(duration_s * 1_000_000_000)
        if clock['ns'] >= 300_000_000 and state['delivered'] == 0:
            state['delivered'] = 1
            events.append(('B23_R04_DELIVERY_DELAYED_CALLBACK',
                {'case':'R04a','delivery_ns':clock['ns']}))
    io = NS(deadline_ns=2_000_000_000, now=lambda:clock['ns'], pause=pause, events=events)
    delayed = asyncio.run(await_r04a_delayed_callback(io, state, timeout_ns=500_000_000))
    assert delayed['delivery_ns'] >= 300_000_000
    assert clock['ns'] < io.deadline_ns
    assert state == {'triggered':1,'scheduled':1,'delivered':1}


def test_r04_delivery_state_counts_scheduled_before_delayed_callback_runs(monkeypatch):
    import threading
    from mecanum_nav_rl.runtime_simulation.b23_runner import install_r04_delivery_fault

    timers = []
    class FakeTimer:
        def __init__(self, delay, callback):
            self.delay = delay
            self.callback = callback
            self.daemon = False
            timers.append(self)
        def start(self):
            pass

    monkeypatch.setattr(threading, 'Timer', FakeTimer)
    adapter = NS()
    events = []
    state = install_r04_delivery_fault(adapter, 'R04a',
        lambda name, facts: events.append((name, facts)))
    message = NS(admission_state=1, ADMISSION_POLICY_OPEN=1,
        sample_sequence=7, header=NS(stamp=NS(sec=2, nanosec=3)))
    delivered = []
    assert adapter._b23_r04_injector(
        'on_safety_input', message, lambda _adapter, item: delivered.append(item)) is None
    assert state['triggered'] == 1
    assert state['scheduled'] == 1
    assert state['delivered'] == 0
    assert len(timers) == 1 and timers[0].delay == .3
    assert events[0][0] == 'B23_R04_DELIVERY_DELAY_SCHEDULED'

    timers[0].callback()
    assert state['scheduled'] == 1
    assert state['delivered'] == 1
    assert delivered == [message]
    assert events[-1][0] == 'B23_R04_DELIVERY_DELAYED_CALLBACK'


def test_r04a_blocked_slot_accepts_only_exact_watchdog_emergency_zero():
    from mecanum_nav_rl_interfaces.msg import SimulationContactState
    io = NS(events=[
        ('SAFETY_REJECTED', {'reasons':['NOISY_STALE_OR_FUTURE'],'steady_ns':902}),
    ], ingress=NS(safe_stop_source_id=70, receipts=[],
        backend_state=NS(fault_flags=(SimulationContactState.FAULT_COMMAND_SEQUENCE
            | SimulationContactState.FAULT_COMMAND_STALE),
            local_zero_override=True, actuator_inhibited=True), backend_received_ns=903),
        final=NS(publisher_instance_id=80))
    result = verify_r04a_next_step_blocked(io, step_index=2)
    assert result['native_zero_application'] == {
        'mode':'watchdog_emergency_zero','fault_flags':(
            SimulationContactState.FAULT_COMMAND_SEQUENCE | SimulationContactState.FAULT_COMMAND_STALE),
        'local_zero_override':True,'actuator_inhibited':True,'status_received_ns':903}


def test_r04a_next_policy_slot_requires_safety_rejection_and_no_commit_or_receipt():
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
    from geometry_msgs.msg import Twist
    from mecanum_nav_rl.runtime_simulation.b23_runner import TrainingWorkerIO
    import ast
    import inspect
    constructor = ast.parse(textwrap.dedent(inspect.getsource(TrainingWorkerIO.__init__)))
    ingress_call = next(node for node in ast.walk(constructor)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == 'LocalTrainingIngress')
    emitter_arg = next(item.value for item in ingress_call.keywords if item.arg == 'emit')
    assert (isinstance(emitter_arg, ast.Attribute) and emitter_arg.attr == 'emit'
        and isinstance(emitter_arg.value, ast.Name) and emitter_arg.value.id == 'self')
    receipt = FinalIssuedCommandReceipt()
    receipt.source = FinalIssuedCommandReceipt.SOURCE_SAFE_STOP
    receipt.source_instance_id = 70
    receipt.sequence = 9
    receipt.final_publisher_instance_id = 80
    receipt.final_publish_sequence = 99
    receipt.final_command = Twist()
    events = [
        ('SAFETY_REJECTED', {'reasons':['NOISY_STALE_OR_FUTURE'], 'steady_ns':902}),
    ]
    joined = {'source_instance_id':70,'source_sequence':9,
        'step_index':0,'transition_id':'','steady_ns':950,'publish_sequence':99,
        'iteration':12,'stamp_ns':120_000_000}
    emitter = TrainingWorkerIO.__new__(TrainingWorkerIO)
    emitter.events = []
    emitter._accepted_policy_event_keys = set()
    emitter._event_sink = lambda _name, _facts: None
    emitter._emit('NATIVE_APPLICATION_JOINED', joined)
    events.extend(emitter.events)
    final = NS(publisher_instance_id=80)
    final.publication_for_source_sequence = lambda **kwargs: receipt if (
        kwargs == {'source':FinalIssuedCommandReceipt.SOURCE_SAFE_STOP,'sequence':9}) else None
    io = NS(events=events, ingress=NS(safe_stop_source_id=70,
        receipts=[NS(source=1,source_sequence=1)]), final=final)
    result = verify_r04a_next_step_blocked(io, step_index=2)
    assert result['blocked_step_index'] == 2
    assert result['policy_not_accepted'] is True
    assert result['native_policy_receipt_absent'] is True
    assert result['b1_transition_absent'] is True
    assert result['input_rejection_steady_ns'] == 902
    assert result['rejected_steady_ns'] == 902
    assert result['native_zero_application'] == {
        'source_sequence':9,'final_publish_sequence':99,'publisher_instance_id':80,
        'native_iteration':12,'native_stamp_ns':120_000_000,
        'native_application_steady_ns':950}
    events.remove(('NATIVE_APPLICATION_JOINED', joined))
    with pytest.raises(RuntimeError, match='lacks post-rejection exact SAFE_STOP'):
        verify_r04a_next_step_blocked(io, step_index=2)
    events.append(('NATIVE_APPLICATION_JOINED', joined))
    io.events.append(('SAFETY_ACCEPTED', {'candidate_source':1,'candidate_sequence':2}))
    with pytest.raises(RuntimeError, match='accepted the POLICY slot'):
        verify_r04a_next_step_blocked(io, step_index=2)


def test_r04c_next_policy_slot_requires_stale_scan_rejection_and_applied_zero():
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
    from geometry_msgs.msg import Twist
    receipt = FinalIssuedCommandReceipt()
    receipt.source = FinalIssuedCommandReceipt.SOURCE_SAFE_STOP
    receipt.source_instance_id = 70
    receipt.sequence = 9
    receipt.final_publisher_instance_id = 80
    receipt.final_publish_sequence = 99
    receipt.final_command = Twist()
    joined = {'source_instance_id':70,'source_sequence':9,'step_index':0,
        'transition_id':'','steady_ns':950,'publish_sequence':99,
        'iteration':12,'stamp_ns':120_000_000}
    final = NS(publisher_instance_id=80,
        publication_for_source_sequence=lambda **kwargs: receipt if kwargs == {
            'source':FinalIssuedCommandReceipt.SOURCE_SAFE_STOP,'sequence':9} else None)
    io = NS(events=[
        ('B23_R04_DELIVERY_DELAYED_CALLBACK', {'case':'R04c','delivery_ns':800}),
        ('SAFETY_REJECTED', {'reasons':['SCAN_STALE_OR_FUTURE'],
            'steady_ns':900,'ros_ns':1_700_000_000}),
        ('NATIVE_APPLICATION_JOINED', joined),
        ('b1_transition_committed', {'step_index':1}),
    ], ingress=NS(safe_stop_source_id=70,receipts=[]), final=final)
    result = verify_r04c_next_step_blocked(io, step_index=2, delayed_delivery_ns=800)
    assert result['blocked_step_index'] == 2
    assert result['policy_not_accepted'] is True
    assert result['native_policy_receipt_absent'] is True
    assert result['b1_transition_absent'] is True
    assert result['native_zero_application']['native_application_steady_ns'] == 950
    io.events.append(('SAFETY_ACCEPTED', {'candidate_source':1,
        'candidate_sequence':2,'steady_ns':901}))
    with pytest.raises(RuntimeError, match='accepted the blocked POLICY slot'):
        verify_r04c_next_step_blocked(io, step_index=2, delayed_delivery_ns=800)
    io.events.pop()
    io.events[1][1]['steady_ns'] = 799
    with pytest.raises(RuntimeError, match='lacks Safety rejection'):
        verify_r04c_next_step_blocked(io, step_index=2, delayed_delivery_ns=800)


def test_r04c_stale_callback_requires_production_rejection_and_exact_zero_join():
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
    from geometry_msgs.msg import Twist
    receipt = FinalIssuedCommandReceipt()
    receipt.source = FinalIssuedCommandReceipt.SOURCE_SAFE_STOP
    receipt.source_instance_id = 70
    receipt.sequence = 9
    receipt.final_publisher_instance_id = 80
    receipt.final_publish_sequence = 99
    receipt.final_command = Twist()
    joined = {'source_instance_id':70,'source_sequence':9,'step_index':0,
        'transition_id':'','steady_ns':950,'publish_sequence':99,
        'iteration':12,'stamp_ns':120_000_000}
    io = NS(events=[
        ('B23_R04_DELIVERY_DELAYED_CALLBACK', {'case':'R04c','delivery_ns':800,
            'source_stamp_ns':1_000_000_000}),
        ('SAFETY_REJECTED', {'reasons':['SCAN_STALE_OR_FUTURE'],
            'steady_ns':900,'ros_ns':1_700_000_000}),
        ('NATIVE_APPLICATION_JOINED', joined),
    ], ingress=NS(safe_stop_source_id=70),
       final=NS(publisher_instance_id=80,
           publication_for_source_sequence=lambda **kwargs: receipt if kwargs == {
               'source':FinalIssuedCommandReceipt.SOURCE_SAFE_STOP,'sequence':9} else None))
    result = verify_r04c_stale_rejection_and_zero(io, delayed_delivery_ns=800)
    assert result['stale_rejection_reasons'] == ['SCAN_STALE_OR_FUTURE']
    assert result['native_zero_application']['source_sequence'] == 9
    assert result['native_zero_application']['native_application_steady_ns'] == 950
    io.events.pop()
    assert verify_r04c_stale_rejection_and_zero(io, delayed_delivery_ns=800) is None

    from mecanum_nav_rl_interfaces.msg import CommandEnvelope
    io.events.insert(2, ('SAFETY_ACCEPTED', {'candidate_source':CommandEnvelope.SOURCE_POLICY,
        'candidate_sequence':2,'steady_ns':901}))
    with pytest.raises(RuntimeError, match='accepted the stale-scan POLICY step'):
        verify_r04c_stale_rejection_and_zero(io, delayed_delivery_ns=800, step_index=2)
    io.events.pop(2)
    io.events.insert(2, ('NATIVE_APPLICATION_JOINED', {'step_index':2,
        'source_sequence':2,'steady_ns':902}))
    with pytest.raises(RuntimeError, match='applied POLICY after stale-scan callback'):
        verify_r04c_stale_rejection_and_zero(io, delayed_delivery_ns=800, step_index=2)


def test_r04c_exact_stale_b1_receipt_rejection_is_bound_to_applied_step_and_late_scan():
    from rclpy.serialization import serialize_message
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt

    receipt = FinalIssuedCommandReceipt()
    receipt.step_index = 2
    receipt.transition_id = 'transition-r04c-2'
    receipt.source = FinalIssuedCommandReceipt.SOURCE_POLICY
    receipt.sequence = 2
    receipt.source_instance_id = 77
    receipt.final_publisher_instance_id = 88
    receipt.final_publish_sequence = 65
    error = ValueError('B1 transition commit rejected: POLICY issuance receipt is stale or invalid')
    events = [
        ('policy_adapter_issued', {'step_index':2,'sequence':2,'source_instance_id':77,
            'transition_id':'transition-r04c-2','steady_ns':100_000_000}),
        ('policy_final_published', {'step_index':2,'source_sequence':2,
            'source_instance_id':77,'transition_id':'transition-r04c-2',
            'steady_ns':150_000_000,'receipt_cdr_hex':serialize_message(receipt).hex()}),
        ('B1_POLICY_APPLICATION_BOUND', {'step_index':2,
            'transition_id':'transition-r04c-2','steady_ns':200_000_000}),
        ('B23_R04_DELIVERY_DELAYED_CALLBACK', {'case':'R04c',
            'delivery_ns':800_000_000,'source_stamp_ns':1_000_000_000}),
        ('b1_transition_committed', {'step_index':1}),
    ]
    result = verify_r04c_stale_issuance_commit_rejected(NS(events=events),
        step_index=2, error=error, error_steady_ns=700_000_000,
        delayed_delivery=events[3][1])
    assert result == {
        'blocked_step_index':2,'transition_id':'transition-r04c-2',
        'policy_issued_ns':100_000_000,'policy_receipt_ns':150_000_000,
        'policy_receipt_age_at_rejection_ns':550_000_000,
        'b1_rejection_observed_ns':700_000_000,
        'policy_application_ns':200_000_000,'scan_delivery_ns':800_000_000,
        'scan_source_stamp_ns':1_000_000_000,
        'b1_commit_rejected':True,'b1_transition_absent':True,
        'policy_application_preceded_delayed_scan':True}

    with pytest.raises(RuntimeError, match='not proven beyond 500 ms'):
        verify_r04c_stale_issuance_commit_rejected(NS(events=events),
            step_index=2, error=error, error_steady_ns=650_000_000,
            delayed_delivery=events[3][1])
    wrong_error = ValueError('some other B1 failure')
    with pytest.raises(RuntimeError, match='not the exact stale-issuance rejection'):
        verify_r04c_stale_issuance_commit_rejected(NS(events=events),
            step_index=2, error=wrong_error, error_steady_ns=700_000_000,
            delayed_delivery=events[3][1])
    events.append(('b1_transition_committed', {'step_index':2}))
    with pytest.raises(RuntimeError, match='committed the stale-issuance step'):
        verify_r04c_stale_issuance_commit_rejected(NS(events=events),
            step_index=2, error=error, error_steady_ns=700_000_000,
            delayed_delivery=events[3][1])


def test_r04c_failure_before_hook_arm_preserves_primary_error_and_event():
    events = []
    io = NS(now=lambda:1234,
        emit=lambda name, facts:events.append((name, facts)))
    original = TimeoutError('SAFE_STOP application timed out before hook arm')
    with pytest.raises(RuntimeError, match='TimeoutError: SAFE_STOP application timed out') as caught:
        require_r04c_fault_state(io, original)
    assert caught.value.__cause__ is original
    assert events == [('R04C_STEP_FAILED_BEFORE_FAULT_ARM', {
        'error_type':'TimeoutError',
        'error':'SAFE_STOP application timed out before hook arm',
        'steady_ns':1234})]
    io._r04_fault_state = {'case':'R04c','triggered':0,'scheduled':0,'delivered':0}
    assert require_r04c_fault_state(io, original) is io._r04_fault_state


def test_training_worker_routes_b1_events_through_worker_event_recorder():
    import ast
    import inspect
    from pathlib import Path
    from mecanum_nav_rl.runtime_simulation import b23_runner

    source = Path(inspect.getsourcefile(b23_runner)).read_bytes()
    tree = ast.parse(source)
    worker = next(node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == 'training_child')
    adapter = next(node for node in ast.walk(worker)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == 'LocalTrainingB1Adapter')
    emitter = next(item.value for item in adapter.keywords if item.arg == 'emit')
    assert (isinstance(emitter, ast.Attribute) and emitter.attr == 'emit'
        and isinstance(emitter.value, ast.Name) and emitter.value.id == 'io'), ast.dump(emitter)
    from mecanum_nav_rl.runtime_simulation.b23_runner import TrainingWorkerIO
    seen = []
    recorder = TrainingWorkerIO.__new__(TrainingWorkerIO)
    recorder.events = []
    recorder._accepted_policy_event_keys = set()
    recorder._event_sink = lambda name, facts: seen.append((name, facts))
    facts = {'step_index':1,'transition_id':'transition-1'}
    recorder._emit('b1_transition_committed', facts)
    assert recorder.events == [('b1_transition_committed', facts)]
    assert seen == [('b1_transition_committed', facts)]


def test_r04a_accepts_exact_applied_zero_when_latest_safety_tick_is_ahead():
    from mecanum_nav_rl_interfaces.msg import CommandEnvelope
    proof = {'publisher_instance_id':80, 'final_publish_sequence':99,
        'source_sequence':42, 'native_iteration':151, 'native_stamp_ns':1_510_000_000,
        'native_application_steady_ns':500}
    io = NS(final=NS(publisher_instance_id=80),
        ingress=NS(backend_state=NS(applied_receipt_valid=True,
            local_zero_override=False, fault_flags=0,
            applied_final_publisher_instance_id=80, applied_final_publish_sequence=99)),
        safety=NS(local_training=NS(last_output=NS(
            source=CommandEnvelope.SOURCE_SAFE_STOP, sequence=43,
            twist=NS(linear=NS(x=0., y=0., z=0.),
                angular=NS(x=0., y=0., z=0.))))))

    result = verify_r04a_zero_baseline(io, checked={'native_zero_application':proof})

    assert result['current_native_publish_sequence'] == 99
    assert result['current_safety_sequence'] == 43
    assert result['proven_post_rejection_zero'] == proof
    io.ingress.backend_state.applied_final_publish_sequence = 98
    with pytest.raises(RuntimeError, match='lost its healthy applied-zero baseline'):
        verify_r04a_zero_baseline(io, checked={'native_zero_application':proof})


def test_r04a_accepts_watchdog_zero_after_exact_applied_zero_proof():
    from mecanum_nav_rl_interfaces.msg import CommandEnvelope, SimulationContactState
    proof = {'publisher_instance_id':80, 'final_publish_sequence':99,
        'source_sequence':42, 'native_iteration':151, 'native_stamp_ns':1_510_000_000,
        'native_application_steady_ns':500}
    io = NS(final=NS(publisher_instance_id=80),
        ingress=NS(backend_state=NS(applied_receipt_valid=False,
            local_zero_override=True, actuator_inhibited=True,
            fault_flags=(SimulationContactState.FAULT_COMMAND_SEQUENCE
                | SimulationContactState.FAULT_COMMAND_STALE)),
            backend_received_ns=600),
        safety=NS(local_training=NS(last_output=NS(
            source=CommandEnvelope.SOURCE_SAFE_STOP, sequence=43,
            twist=NS(linear=NS(x=0., y=0., z=0.),
                angular=NS(x=0., y=0., z=0.))))))

    result = verify_r04a_zero_baseline(io, checked={'native_zero_application':proof})

    assert result['native_zero_mode'] == 'watchdog_emergency_zero_after_applied_receipt'
    assert result['proven_post_rejection_zero'] == proof
    assert result['actuator_inhibited'] is True
    assert result['current_backend_status_received_ns'] == 600
    io.ingress.backend_state.actuator_inhibited = False
    with pytest.raises(RuntimeError, match='lost its healthy applied-zero baseline'):
        verify_r04a_zero_baseline(io, checked={'native_zero_application':proof})


def test_r04a_blocked_slot_distinguishes_prebegin_timeout_from_pending_abort():
    lifecycle = NS(snapshot=NS(active_transition_identity=None, step_index=1))
    result = abort_r04a_pending_step_if_active(lifecycle, expected_step_index=2)
    assert result == {'disposition':'NOT_STARTED','step_index':2,
        'last_committed_step_index':1}
    lifecycle.abort_step = lambda _reason: pytest.fail('must not abort a nonexistent B1 step')

    active = NS(step_index=2)
    lifecycle.snapshot = NS(active_transition_identity=active, step_index=1)
    lifecycle.abort_step = lambda reason: (setattr(lifecycle, 'abort_reason', reason)
        or NS(status='aborted'))
    result = abort_r04a_pending_step_if_active(lifecycle, expected_step_index=2)
    assert result == {'disposition':'ABORTED','step_index':2,'abort_status':'aborted'}
    assert lifecycle.abort_reason == 'R04a_delayed_input_blocked_next_slot'

    lifecycle.snapshot = NS(active_transition_identity=NS(step_index=3), step_index=1)
    with pytest.raises(RuntimeError, match='pending B1 identity differs'):
        abort_r04a_pending_step_if_active(lifecycle, expected_step_index=2)


def test_r04a_timeout_detail_is_saved_inside_exception_handler():
    tree = ast.parse(Path(runner_module.__file__).read_bytes())
    handler = next(node for node in ast.walk(tree)
        if isinstance(node, ast.ExceptHandler) and node.name == 'error'
        and any(isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
            and child.func.id == 'abort_r04a_pending_step_if_active'
            for statement in node.body for child in ast.walk(statement)))
    saved = next(node for node in ast.walk(handler)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'blocked_step_timeout'
            for target in node.targets))
    assert isinstance(saved.value, ast.Call)
    assert isinstance(saved.value.func, ast.Name) and saved.value.func.id == 'repr'
    assert isinstance(saved.value.args[0], ast.Name) and saved.value.args[0].id == 'error'
    outcome = next(node for node in ast.walk(tree)
        if isinstance(node, ast.Dict) and any(isinstance(key, ast.Constant)
            and key.value == 'blocked_step_timeout' for key in node.keys))
    value = outcome.values[outcome.keys.index(next(key for key in outcome.keys
        if isinstance(key, ast.Constant) and key.value == 'blocked_step_timeout'))]
    assert isinstance(value, ast.Name) and value.id == 'blocked_step_timeout'


@pytest.mark.parametrize('case,reason', [('R04c','SCAN_STALE_OR_FUTURE')])
def test_r04_assessment_requires_delayed_source_and_real_safety_rejection(case, reason):
    from mecanum_nav_rl_interfaces.msg import CommandEnvelope
    delayed = 1_000_000_000
    io = NS(policy_source_id=9, events=[
        ('B23_R04_DELIVERY_DELAY_SCHEDULED', {'case':case,'delay_s':.3,
            'callback_received_ns':0,'source_stamp_ns':77}),
        ('B23_R04_DELIVERY_DELAYED_CALLBACK', {'case':case,'delay_s':.3,
            'delivery_ns':delayed,'source_stamp_ns':77}),
        ('SAFETY_REJECTED', {'reasons':[reason],'steady_ns':delayed+1,
            'ros_ns':1_000_000_000}),
        ('SAFETY_ACCEPTED', {'candidate_sequence':1,
            'candidate_source':CommandEnvelope.SOURCE_POLICY,
            'candidate_source_instance_id':9,'steady_ns':delayed+2}),
    ])
    assert verify_r04_stale_delivery(io, case=case, policy_step_index=1)['fresh_policy_recovery'] is True
    io.events = [row for row in io.events if row[0] != 'SAFETY_REJECTED']
    with pytest.raises(RuntimeError, match='actual Safety stale rejection'):
        verify_r04_stale_delivery(io, case=case, policy_step_index=1)


def test_final_publication_view_selects_retained_receipt_for_exact_safety_sequence():
    from rclpy.serialization import serialize_message
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
    from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
    from mecanum_nav_rl.runtime_simulation.b23_runner import FinalPublicationView
    expected = FinalIssuedCommandReceipt()
    expected.source = expected.SOURCE_SAFE_STOP
    expected.sequence = 31
    expected.source_instance_id = 44
    expected.final_publisher_instance_id = 55
    expected.final_publish_sequence = 20
    expected.final_command.linear.x = expected.final_command.linear.y = 0.
    expected.final_command.angular.z = 0.
    view = FinalPublicationView(55)
    view.ingress = NS(
        receipts=[
            NS(source=ReceiptSource.SAFE_STOP, source_sequence=31,
                final_publisher_instance_id=55, final_publish_sequence=20),
            NS(source=ReceiptSource.SAFE_STOP, source_sequence=32,
                final_publisher_instance_id=55, final_publish_sequence=21),
        ],
        _receipt_bytes={20:serialize_message(expected)},
    )
    selected = view.publication_for_source_sequence(
        source=FinalIssuedCommandReceipt.SOURCE_SAFE_STOP, sequence=31)
    assert selected is not None
    assert selected.sequence == 31 and selected.final_publish_sequence == 20
    assert view.publication_for_source_sequence(
        source=FinalIssuedCommandReceipt.SOURCE_SAFE_STOP, sequence=30) is None


def test_r02_order_assessment_requires_actual_native_gate_timestamps(tmp_path):
    import json
    path=tmp_path/'native-events.jsonl'
    rows=[
        {'kind':'B23_POLICY_RECEIPT_INGRESS','fields':{'step':'1','receive_ns':'300'}},
        {'kind':'B23_ADMISSION_ACCEPTED','fields':{'receive_ns':'100','processed_ns':'200'}},
    ]
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    assert verify_r02_policy_order(tmp_path,case='R02a',step_started_ns=50)['order']=='admission_before_receipt'
    rows[0]['fields']['receive_ns']='150'
    rows[1]['fields']['receive_ns']='100'; rows[1]['fields']['processed_ns']='200'
    rows[0]['fields']['sequence']='53'
    rows.append({'kind':'B23_RECEIPT_GATE_RESULT','fields':{
        'source':'1','key':'53','disposition':'3','reason':'accepted_once','steady_ns':'208'}})
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    result=verify_r02_policy_order(tmp_path,case='R02b',step_started_ns=50)
    assert result['order']=='receipt_before_admission', result
    assert result['receipt_residence_ns']==58, result
    rows[0]['fields']['receive_ns']='300'
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    with pytest.raises(RuntimeError,match='order mismatch'):
        verify_r02_policy_order(tmp_path,case='R02b',step_started_ns=50)


def test_r02a_wait_target_binds_native_admission_to_current_sample_and_session():
    rows=[
        {'kind':'B23_ADMISSION_ACCEPTED','fields':{
            'receive_ns':'101','processed_ns':'110','sample':'37',
            'session':'session-a','backend':'8','ingress':'9'}},
        {'kind':'B23_ADMISSION_ACCEPTED','fields':{
            'receive_ns':'102','processed_ns':'111','sample':'38',
            'session':'wrong-session','backend':'8','ingress':'9'}},
        {'kind':'B23_ADMISSION_ACCEPTED','fields':{
            'receive_ns':'103','processed_ns':'112','sample':'38',
            'session':'session-a','backend':'7','ingress':'9'}},
        {'kind':'B23_ADMISSION_ACCEPTED','fields':{
            'receive_ns':'104','processed_ns':'113','sample':'38',
            'session':'session-a','backend':'8','ingress':'9'}},
    ]
    selected=r02a_native_admission_row(rows,sample_sequence=38,
        session_id='session-a',backend_instance_id=8,ingress_instance_id=9,
        step_started_ns=100)
    assert selected==rows[3]
    assert r02a_native_admission_row(rows,sample_sequence=39,
        session_id='session-a',backend_instance_id=8,ingress_instance_id=9,
        step_started_ns=100) is None


def test_r02b_measures_receipt_residence_until_matching_native_gate_acceptance(tmp_path):
    import json
    path=tmp_path/'native-events.jsonl'
    admission_receive_ns=1_000_000_000
    receipt_ns=admission_receive_ns+2_600_000
    admission_processed_ns=receipt_ns+5_600_000
    gate_accepted_ns=admission_processed_ns+175_000
    # The receipt ingress is earlier than native admission processing; the
    # matching gate result proves the same publication was applied after that
    # admission, and its measured residence remains within 40 ms.
    rows=[
        {'kind':'B23_POLICY_RECEIPT_INGRESS','fields':{
            'step':'1','sequence':'53','receive_ns':str(receipt_ns)}},
        {'kind':'B23_ADMISSION_ACCEPTED','fields':{
            'receive_ns':str(admission_receive_ns),'processed_ns':str(admission_processed_ns)}},
        {'kind':'B23_RECEIPT_GATE_RESULT','fields':{
            'source':'1','key':'53','disposition':'3','reason':'accepted_once',
            'steady_ns':str(gate_accepted_ns)}},
    ]
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    result=verify_r02_policy_order(tmp_path,case='R02b',step_started_ns=admission_receive_ns-1)
    assert result['order']=='receipt_before_admission', result
    assert result['receipt_residence_ns']==5_775_000, result
    assert result['receipt_to_admission_ns']==5_600_000, result

    rows[2]['fields']['steady_ns']=str(receipt_ns+40_000_001)
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    with pytest.raises(RuntimeError,match='40 ms bounded gate hold'):
        verify_r02_policy_order(tmp_path,case='R02b',step_started_ns=admission_receive_ns-1)

    rows[2]['fields']['steady_ns']=str(gate_accepted_ns)
    rows[2]['fields']['key']='54'
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    with pytest.raises(RuntimeError,match='lacks accepted native gate result'):
        verify_r02_policy_order(tmp_path,case='R02b',step_started_ns=admission_receive_ns-1)


def test_r01b_requires_native_unexpected_pause_and_zero_without_reset_commit():
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendControlError
    response = Control.Response()
    response.result = response.RESULT_REJECTED
    response.reason_code = response.REASON_BARRIER_INVALID
    ack = NS(response=response, request=NS(request_sequence=24))
    error = BackendControlError('backend rejected pause', ack)
    io = NS(events=[('FAULT_HOOK_EXTERNAL_PAUSE_AFTER_W1', {'sequence': 11})],
        ingress=NS(backend_state=NS(fault_flags=1, local_zero_override=True)))
    result = verify_r01b_external_pause_rejection(io, error)
    assert result == {'reason_code': response.REASON_BARRIER_INVALID,
        'request_sequence': 24, 'native_fault_flags': 1, 'local_zero_override': True,
        'no_pose_mutation': True, 'no_observation0_commit': True}
    io.events.append(('B1_RESET_COMMITTED', {}))
    with pytest.raises(RuntimeError, match='continued reset'):
        verify_r01b_external_pause_rejection(io, error)
    io.events = [('FAULT_HOOK_EXTERNAL_PAUSE_AFTER_W1', {})]
    io.ingress.backend_state.local_zero_override = False
    with pytest.raises(RuntimeError, match='zero override'):
        verify_r01b_external_pause_rejection(io, error)


def test_r01c_d_wait_bounded_for_native_fault_status_after_expired_ack():
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendControlError
    response = Control.Response()
    response.result = response.RESULT_REJECTED
    response.reason_code = response.REASON_CONTROL_EXPIRED
    error = BackendControlError('native pause ACK expired', NS(response=response))
    clock = NS(ns=10_000_000_000)
    state = NS(fault_flags=0, local_zero_override=False)
    async def pause(duration):
        clock.ns += int(duration * 1e9)
        if clock.ns >= 10_050_000_000:
            state.fault_flags, state.local_zero_override = 1, True
    io = NS(events=[], now=lambda:clock.ns, pause=pause, deadline_ns=11_000_000_000,
        ingress=NS(backend_state=state))
    result = asyncio.run(verify_r01_pause_ack_failure(io, error))
    assert result['reason_code'] == response.REASON_CONTROL_EXPIRED
    assert result['native_fault_flags'] == 1 and result['local_zero_override'] is True
    assert result['no_pose_mutation'] and result['no_observation0_commit']
    io.events.append(('B1_RESET_COMMITTED', {}))
    with pytest.raises(RuntimeError, match='continued reset'):
        asyncio.run(verify_r01_pause_ack_failure(io, TimeoutError('late ACK')))


def test_r01c_d_fail_when_native_fault_status_never_arrives():
    clock = NS(ns=20_000_000_000)
    async def pause(duration): clock.ns += int(duration * 1e9)
    io = NS(events=[], now=lambda:clock.ns, pause=pause, deadline_ns=21_000_000_000,
        ingress=NS(backend_state=NS(fault_flags=0, local_zero_override=False)))
    with pytest.raises(RuntimeError, match='did not retain native fault and zero override'):
        asyncio.run(verify_r01_pause_ack_failure(io, TimeoutError('bounded fault timeout')))


def test_r01c_d_preserves_unrelated_reset_error_before_pause_ack_hook():
    io = NS(events=[], now=lambda: 20_000_000_000, pause=lambda _duration: None,
        deadline_ns=21_000_000_000,
        ingress=NS(backend_state=NS(fault_flags=0, local_zero_override=False)))
    original = ValueError('stationary scan window missed reset deadline')
    with pytest.raises(RuntimeError, match='pause ACK fault was not reached') as caught:
        asyncio.run(verify_r01_pause_ack_failure(io, original))
    assert 'stationary scan window missed reset deadline' in str(caught.value)
    assert caught.value.__cause__ is original


class Clock:
    def __init__(self): self.ns = 1_000_000_000
    def now(self): return self.ns
    async def pause(self, seconds):
        self.ns += round(seconds * 10**9)
        await asyncio.sleep(0)


def worker():
    value = TrainingWorkerIO.__new__(TrainingWorkerIO)
    clock = Clock()
    value.now, value.pause = clock.now, clock.pause
    value.deadline_ns = clock.ns + 100_000_000
    value.stop_requested, value.abort_requested = False, None
    value.pump_error, value.expected_paused = None, True
    value.last_clock_ns, value.last_clock_advance_ns = 0, clock.ns
    value.node = NS(get_clock=lambda: NS(now=lambda: NS(nanoseconds=0)))
    value.world_client = NS(service_is_ready=lambda: True)
    value.emit = lambda _name, _facts: None
    value.ingress = NS(fault=None, backend_state=None, backend_received_ns=clock.ns)
    async def refresh_zero_before_pending_bind(*, deadline_ns):
        return {'test_witness': True, 'deadline_ns': deadline_ns}
    value.refresh_zero_before_pending_bind = refresh_zero_before_pending_bind
    return value, clock


def test_freeze_zero_closes_safe_stop_stream_before_waiting_for_pinned_receipt(monkeypatch):
    """No later SAFE_STOP may move native application beyond the reset fence."""
    from mecanum_nav_rl_interfaces.msg import CommandEnvelope

    value, clock = worker()
    stream = {'enabled': True}
    stream_states = []
    adapter = NS(safe_stop_sequence=0)
    adapter.set_policy_hold = lambda _held: None
    def set_stream_enabled(enabled):
        stream['enabled'] = enabled
        stream_states.append(bool(enabled))
    adapter.set_stream_enabled = set_stream_enabled
    value.safety = NS(local_training=adapter)
    lifecycle = NS(episode_generation=0, barrier_stamp=NS(sec=0, nanosec=0))
    value.ingress = NS(lifecycle=lifecycle, _noise_ready=False,
        observation0_ack=None, last_published_sample_sequence=0,
        pause_admission_publication=lambda: None, physics_pairs=[])
    receipt = NS(
        source=CommandEnvelope.SOURCE_SAFE_STOP, sequence=1,
        final_publisher_instance_id=77, final_publish_sequence=9,
        source_instance_id=88, episode_generation=0, reset_epoch=0,
        runtime_generation=0, step_index=0, transition_id='',
        final_command=NS(linear=NS(x=0., y=0., z=0.),
            angular=NS(x=0., y=0., z=0.)),
        header=NS(stamp=NS(sec=0, nanosec=10_000_000)))
    value.final = NS(publication_for_source_sequence=lambda *, source, sequence:
        receipt if (source == CommandEnvelope.SOURCE_SAFE_STOP and sequence == 1) else None)
    value.descriptor = {'session_id':'session-1', 'config_hash':'a'*64,
        'backend_instance_id':99}
    state = NS(applied_receipt_valid=True, local_zero_override=False,
        applied_final_publisher_instance_id=77, applied_final_publish_sequence=9,
        applied_physics_iteration=1, applied_sim_stamp=NS(sec=0, nanosec=10_000_000))
    monkeypatch.setattr('rclpy.serialization.deserialize_message', lambda _raw, _type: state)
    phases = []
    async def until(predicate, *, deadline_ns, phase):
        phases.append(phase)
        if phase == 'SAFE_STOP tick':
            adapter.safe_stop_sequence = 1
        elif phase == 'final SAFE_STOP drain':
            assert stream['enabled'] is False, 'Safety stream remained open after pinning W1'
            # A delayed timer callback must not mint another sequence after W1.
            assert adapter.safe_stop_sequence == 1
        elif phase == 'native applied SAFE_STOP':
            assert stream['enabled'] is False, 'Safety stream reopened before native zero application'
            value.ingress.physics_pairs[:] = [NS(backend_bytes=b'fake-status',
                backend_received_steady_ns=clock.ns)]
        result = predicate()
        assert result is not None, phase
        return result
    value.until = until
    value.now = clock.now
    value.emit = lambda _name, _facts: None

    result = asyncio.run(value.freeze_zero(deadline_ns=clock.ns + 5_000_000_000))

    assert result.final_publish_sequence == 9
    assert phases == ['SAFE_STOP tick', 'final SAFE_STOP drain', 'native applied SAFE_STOP']
    assert stream_states == [False]
    assert stream['enabled'] is False


def test_policy_pending_event_dedupe_is_scoped_per_cutoff_and_reason():
    seen = set()
    observed = []
    for cutoff, reason in ((10, 'waiting'), (20, 'waiting'), (10, 'waiting'),
            (20, 'waiting'), (10, 'freshness changed'), (10, 'freshness changed')):
        observed.append(should_emit_policy_cutoff_pending(seen, cutoff, reason))
    assert observed == [True, True, False, False, True, False]
    assert seen == {(10, 'waiting'), (20, 'waiting'), (10, 'freshness changed')}


def test_until_waits_in_common_budget_and_does_not_accept_late_data():
    value, clock = worker()
    deadline = clock.ns + 5_000_000
    seen = []
    def observation():
        seen.append(clock.ns)
        return 'ready' if clock.ns >= 1_004_000_000 else None
    assert asyncio.run(value.until(observation, deadline_ns=deadline, phase='test')) == 'ready'
    assert seen == [1_000_000_000, 1_002_000_000, 1_004_000_000]
    value, clock = worker()
    def late():
        clock.ns += 6_000_000
        return 'ready'
    with pytest.raises(TimeoutError, match='completed late'):
        asyncio.run(value.until(late, deadline_ns=1_005_000_000, phase='test'))


def test_until_none_and_frozen_pause_fail_bounded():
    value, clock = worker()
    with pytest.raises(TimeoutError, match='deadline expired'):
        asyncio.run(value.until(lambda: None, deadline_ns=clock.ns + 5_000_000, phase='none'))
    assert clock.ns == 1_005_000_000
    value, clock = worker()
    async def frozen(seconds): await asyncio.sleep(0)
    value.pause = frozen
    with pytest.raises(RuntimeError, match='did not advance'):
        asyncio.run(value.until(lambda: None, deadline_ns=clock.ns + 5_000_000, phase='frozen'))


def test_r02g_inhibit_drain_requires_a_new_native_observed_sample():
    from mecanum_nav_rl_interfaces.msg import LocalTrainingSafetyInput
    value, clock = worker()
    class Ingress:
        fault = None
        backend_state = None
        last_published_sample_sequence = 8
        last_published_admission_state = LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN
        def inhibit(self, *, zero_only=False):
            self.last_published_admission_state = (LocalTrainingSafetyInput.ADMISSION_ZERO_ONLY
                if zero_only else LocalTrainingSafetyInput.ADMISSION_INHIBITED)
        def publish_fresh_on_next_pause(self, zero_only=False):
            self.last_published_sample_sequence = 9
            self.last_published_admission_state = (LocalTrainingSafetyInput.ADMISSION_ZERO_ONLY
                if zero_only else LocalTrainingSafetyInput.ADMISSION_INHIBITED)
    ingress = Ingress()
    value.ingress = ingress
    watermark = [8]
    async def pause(seconds):
        clock.ns += round(seconds * 1e9)
        ingress.publish_fresh_on_next_pause()
        watermark[0] = 9
        await asyncio.sleep(0)
    value.pause = pause
    value.read_native_input_watermark = lambda: watermark[0]
    value._native_input_watermark = 9
    value.safety = NS(local_training=NS(set_stream_enabled=lambda enabled: None))
    drained = asyncio.run(value.inhibit_and_drain(deadline_ns=clock.ns+20_000_000))
    assert drained == 9
    assert ingress.last_published_sample_sequence > 8
    assert ingress.last_published_admission_state == LocalTrainingSafetyInput.ADMISSION_INHIBITED


def test_until_can_observe_only_the_case_expected_native_zero_fault():
    from mecanum_nav_rl_interfaces.msg import SimulationContactState
    expected = (SimulationContactState.FAULT_COMMAND_SEQUENCE
        | SimulationContactState.FAULT_COMMAND_STALE)
    value, clock = worker()
    value.ingress.backend_state = NS(fault_flags=expected, local_zero_override=True)
    assert asyncio.run(value.until(lambda: value.ingress.backend_state,
        deadline_ns=clock.ns + 5_000_000, phase='expected close fault',
        expected_native_fault_flags=expected)) is value.ingress.backend_state

    value, clock = worker()
    value.ingress.backend_state = NS(fault_flags=expected | SimulationContactState.FAULT_CLOCK,
        local_zero_override=True)
    with pytest.raises(RuntimeError, match='native fault flags=70'):
        asyncio.run(value.until(lambda: value.ingress.backend_state,
            deadline_ns=clock.ns + 5_000_000, phase='unexpected fault',
            expected_native_fault_flags=expected))

    value, clock = worker()
    value.ingress.backend_state = NS(fault_flags=expected, local_zero_override=False)
    with pytest.raises(TimeoutError, match='deadline expired'):
        asyncio.run(value.until(lambda: value.ingress.backend_state
            if value.ingress.backend_state.local_zero_override else None,
            deadline_ns=clock.ns + 5_000_000, phase='fault without zero',
            expected_native_fault_flags=expected))


def test_r02_close_marker_remains_observable_when_expected_fault_arrives_first():
    """R02d must observe release marker despite the fail-closed fault racing it."""
    from mecanum_nav_rl_interfaces.msg import SimulationContactState
    expected = (SimulationContactState.FAULT_COMMAND_SEQUENCE
        | SimulationContactState.FAULT_COMMAND_STALE)
    value, clock = worker()
    value.ingress.backend_state = NS(fault_flags=expected, local_zero_override=True)
    release_marker = {'kind': 'B23_POLICY_RECEIPT_RELEASED_AFTER_CLOSE',
        'reason': 'admission_inhibited', 'sequence': 35}

    observed = asyncio.run(value.until(lambda: release_marker,
        deadline_ns=clock.ns + 5_000_000,
        phase='held POLICY receipt released only after closing condition',
        expected_native_fault_flags=expected))

    assert observed == release_marker
    assert value.ingress.backend_state.fault_flags == expected
    assert value.ingress.backend_state.local_zero_override is True

    value, clock = worker()
    value.ingress.backend_state = NS(fault_flags=expected | SimulationContactState.FAULT_CLOCK,
        local_zero_override=True)
    with pytest.raises(RuntimeError, match='native fault flags=70'):
        asyncio.run(value.until(lambda: release_marker,
            deadline_ns=clock.ns + 5_000_000,
            phase='held POLICY receipt released only after closing condition',
            expected_native_fault_flags=expected))


def test_r02e_requires_prebind_sample_rejected_and_fresh_pending_token_accepted():
    from mecanum_nav_rl.runtime_simulation.b23_runner import verify_r02e_prebind_admission_rejected
    identity = {'session':'session-1','backend':'22','ingress':'11'}
    rows = [
        {'kind':'B23_SAFETY_INPUT_ENQUEUED','fields':{**identity,'sample':'10','receive_ns':'100'}},
        {'kind':'B23_ADMISSION_ACCEPTED','fields':{**identity,'sample':'9'}},
        {'kind':'B23_SAFETY_INPUT_ENQUEUED','fields':{**identity,'sample':'11','receive_ns':'200'}},
        {'kind':'B23_ADMISSION_ACCEPTED','fields':{**identity,'sample':'11'}},
    ]
    result = verify_r02e_prebind_admission_rejected(rows, held_sample_sequence=10,
        fresh_sample_sequence=11, pending_token=bytes([1])*16,
        session_id='session-1', backend_instance_id=22, ingress_instance_id=11)
    assert result == {'prebind_sample_sequence':10,'prebind_native_accept_count':0,
        'postbind_sample_sequence':11,'postbind_native_accept_count':1,
        'prebind_enqueued_before_fresh':True,
        'pending_token_nonzero':True}
    rows.append({'kind':'B23_ADMISSION_ACCEPTED','fields':{**identity,'sample':'10'}})
    with pytest.raises(RuntimeError, match='pre-bind sample was accepted'):
        verify_r02e_prebind_admission_rejected(rows, held_sample_sequence=10,
            fresh_sample_sequence=11, pending_token=bytes([1])*16,
            session_id='session-1', backend_instance_id=22, ingress_instance_id=11)
    with pytest.raises(RuntimeError, match='fresh post-bind admission'):
        verify_r02e_prebind_admission_rejected(rows[:3], held_sample_sequence=10,
            fresh_sample_sequence=11, pending_token=bytes([1])*16,
            session_id='session-1', backend_instance_id=22, ingress_instance_id=11)


def test_r02e_waits_for_delayed_native_acceptance_record(tmp_path):
    value, clock = worker()
    native = tmp_path/'native-events.jsonl'
    identity = {'session':'session-1','backend':'22','ingress':'11'}
    records = [
        {'kind':'B23_SAFETY_INPUT_ENQUEUED','fields':{**identity,'sample':'10','receive_ns':'100'}},
        {'kind':'B23_SAFETY_INPUT_ENQUEUED','fields':{**identity,'sample':'11','receive_ns':'200'}},
        {'kind':'B23_ADMISSION_ACCEPTED','fields':{**identity,'sample':'11'}},
    ]
    content = b''.join((json.dumps(row).encode()+b'\n') for row in records)
    partial = content[:9]
    native.write_bytes(partial)
    value.descriptor = {'native_events_path':str(native), 'session_id':'session-1',
        'backend_instance_id':22,'coordinator_ingress_instance_id':11}
    value.ros_now = lambda: 0
    pauses = []
    async def pause(seconds):
        await clock.pause(seconds)
        pauses.append(seconds)
        if len(pauses) == 1:
            with native.open('ab') as stream:
                stream.write(content[len(partial):])
    value.pause = pause

    result = asyncio.run(value.wait_r02e_native_admission(
        held_sample_sequence=10, fresh_sample_sequence=11,
        pending_token=bytes([1])*16, deadline_ns=clock.ns+10_000_000))

    assert result == {'prebind_sample_sequence':10,'prebind_native_accept_count':0,
        'postbind_sample_sequence':11,'postbind_native_accept_count':1,
        'prebind_enqueued_before_fresh':True,
        'pending_token_nonzero':True}
    assert len(pauses) == 1


def test_r02e_wait_rejects_prebind_acceptance_while_native_log_is_pending(tmp_path):
    value, clock = worker()
    native = tmp_path/'native-events.jsonl'
    native.write_text(json.dumps({'kind':'B23_ADMISSION_ACCEPTED',
        'fields':{'sample':'10'}})+'\n')
    value.descriptor = {'native_events_path':str(native), 'session_id':'session-1',
        'backend_instance_id':22,'coordinator_ingress_instance_id':11}
    value.ros_now = lambda: 0
    with pytest.raises(RuntimeError, match='pre-bind sample was accepted'):
        asyncio.run(value.wait_r02e_native_admission(
            held_sample_sequence=10, fresh_sample_sequence=11,
            pending_token=bytes([1])*16, deadline_ns=clock.ns+10_000_000))


def test_r02e_rejects_native_enqueue_reordering_or_identity_change():
    identity = {'session':'session-1','backend':'22','ingress':'11'}
    rows = [
        {'kind':'B23_SAFETY_INPUT_ENQUEUED','fields':{**identity,'sample':'11','receive_ns':'100'}},
        {'kind':'B23_SAFETY_INPUT_ENQUEUED','fields':{**identity,'sample':'10','receive_ns':'200'}},
        {'kind':'B23_ADMISSION_ACCEPTED','fields':{**identity,'sample':'11'}},
    ]
    with pytest.raises(RuntimeError, match='enqueued after the fresh input'):
        verify_r02e_prebind_admission_rejected(rows, held_sample_sequence=10,
            fresh_sample_sequence=11, pending_token=bytes([1])*16,
            session_id='session-1', backend_instance_id=22, ingress_instance_id=11)
    rows[0]['fields']['session'] = 'other-session'
    with pytest.raises(RuntimeError, match='identity mismatch'):
        verify_r02e_safety_input_enqueued(rows, sample_sequence=11,
            session_id='session-1', backend_instance_id=22,
            ingress_instance_id=11)


def test_r02e_publishes_held_input_then_waits_for_bound_enqueue_before_resume(tmp_path):
    value, clock = worker()
    native = tmp_path/'native-events.jsonl'
    native.write_text('')
    value.descriptor = {'native_events_path':str(native), 'session_id':'session-1',
        'backend_instance_id':22,'coordinator_ingress_instance_id':11}
    value.ros_now = lambda: 0
    history = []
    value.emit = lambda name, fields: history.append((name, fields))
    value.safety_publisher = NS(publish=lambda message: history.append(('publish', message.sample_sequence)))
    value.ingress = NS(fault=None, backend_state=None,
        backend_received_ns=clock.ns,
        resume_admission_publication=lambda: history.append(('resume', clock.ns)))
    identity = {'session':'session-1','backend':'22','ingress':'11'}
    row = {'kind':'B23_SAFETY_INPUT_ENQUEUED','fields':{**identity,
        'sample':'10','receive_ns':'123456'}}
    async def pause(seconds):
        await clock.pause(seconds)
        native.write_text(json.dumps(row)+'\n')
    value.pause = pause
    held = NS(sample_sequence=10, admission_token=[1]*16)
    ack = NS(response=NS(pending_admission_token=[2]*16, applied_binding_revision=7),
        request=NS(request_sequence=9))

    result = asyncio.run(value.release_r02e_prebind_input_before_admission(
        held_sample=held, ack=ack, deadline_ns=clock.ns+10_000_000))

    assert result == row
    assert [entry[0] for entry in history] == [
        'publish', 'R02E_PREBIND_SAFETY_INPUT_RELEASED_AFTER_BIND',
        'resume', 'R02E_PREBIND_ENQUEUED_BEFORE_FRESH_PUBLICATION']


def test_r02e_runner_keeps_new_admission_closed_until_held_input_is_enqueued():
    import inspect
    import mecanum_nav_rl.runtime_simulation.b23_runner as module
    source = textwrap.dedent(inspect.getsource(module.TrainingWorkerIO.policy_step))
    tree = ast.parse(source)
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute) and node.func.attr == 'arm_pending']
    assert len(calls) == 1
    keyword = next(item.value for item in calls[0].keywords
        if item.arg == 'publish_admission')
    assert ast.dump(keyword, include_attributes=False) == ast.dump(
        ast.parse('held_prebind is None', mode='eval').body, include_attributes=False)
    release = source.index('release_r02e_prebind_input_before_admission')
    first_fresh = source.index('first post-ACK admission publication')
    assert release < first_fresh


def test_active_deadline_is_never_extended_by_predicate_budget():
    value, clock = worker()
    value.deadline_ns = clock.ns + 3_000_000
    with pytest.raises(TimeoutError):
        asyncio.run(value.until(lambda: None, deadline_ns=clock.ns + 10_000_000, phase='test'))
    assert clock.ns == value.deadline_ns == 1_003_000_000


def test_terminal_pause_replay_resubmits_exact_owned_bytes_and_records_evidence():
    value, clock = worker()
    from rclpy.serialization import serialize_message
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendControlAck
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    request = Control.Request(); request.request_sequence = 17
    response = Control.Response(); response.schema_version = response.RESPONSE_SCHEMA_VERSION
    response.result = response.RESULT_APPLIED; response.reason_code = response.REASON_NONE
    response.request_sequence = 17; response.backend_instance_id = 22
    response.binding_revision = response.applied_binding_revision = 4
    response.applied_physics_iteration = 90
    original = BackendControlAck(serialize_message(request), serialize_message(response), clock.ns)
    # Response CDR bytes can differ in padding after ROSIDL serialization;
    # the replay contract is exact request plus the same decoded response fields.
    replayed = NS(request_bytes=original.request_bytes, response_bytes=b'raw-replay-cdr-differs',
                  response=response, observed_steady_ns=clock.ns + 1)
    calls, events = [], []
    async def replay(ack, *, deadline_ns):
        calls.append((ack, deadline_ns))
        return replayed
    value.pause_ack = original
    value.control = NS(replay=replay)
    value.emit = lambda name, fields: events.append((name, fields))
    assert asyncio.run(value.replay_pause_intent_after_terminal()) is replayed
    assert calls == [(original, value.deadline_ns)]
    assert events[0][0] == 'PAUSE_INTENT_EXACT_REPLAY_AFTER_TERMINAL'
    assert events[0][1]['request_sequence'] == 17
    assert events[0][1]['exact_request_bytes'] is True
    assert events[0][1]['semantic_response_match'] is True
    assert events[0][1]['original_response_cdr_hex'] != events[0][1]['response_cdr_hex']


def test_terminal_pause_replay_rejects_different_response_bytes():
    value, clock = worker()
    from rclpy.serialization import serialize_message
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendControlAck
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    request = Control.Request(); request.request_sequence = 4
    response = Control.Response(); response.schema_version = response.RESPONSE_SCHEMA_VERSION
    response.result = response.RESULT_APPLIED; response.request_sequence = 4
    original = BackendControlAck(serialize_message(request), serialize_message(response), clock.ns)
    rejected = Control.Response(); rejected.schema_version = rejected.RESPONSE_SCHEMA_VERSION
    rejected.result = rejected.RESULT_REJECTED; rejected.request_sequence = 4
    value.pause_ack = original
    async def replay(ack, *, deadline_ns):
        return NS(request_bytes=ack.request_bytes, response_bytes=b'different',
                  response=rejected, observed_steady_ns=clock.ns)
    value.control = NS(replay=replay)
    value.emit = lambda *_: None
    with pytest.raises(RuntimeError, match='semantic response differs'):
        asyncio.run(value.replay_pause_intent_after_terminal())


def test_abort_native_fault_and_callback_error_remain_visible():
    value, clock = worker()
    value.abort_requested = 'SIGTERM'
    with pytest.raises(RuntimeError, match='SIGTERM'):
        asyncio.run(value.until(lambda: True, deadline_ns=clock.ns + 1_000_000, phase='test'))
    value.abort_requested = None
    value.pump_error = ValueError('callback invalid')
    with pytest.raises(RuntimeError, match='callback failed') as error:
        value.check()
    assert str(error.value.__cause__) == 'callback invalid'
    value.pump_error = None; value.ingress.backend_state = NS(fault_flags=64)
    with pytest.raises(RuntimeError, match='fault flags=64'):
        value.check()


@pytest.fixture
def native_reader(tmp_path):
    value, clock = worker()
    path = tmp_path/'native-events.jsonl'
    value.descriptor = dict(native_events_path=str(path), run_id='B23_TEST', session_id='own-session',
        backend_instance_id=22, coordinator_ingress_instance_id=11,
        server_leader_pid=777, invocation_id='inv-1')
    value._native_offset, value._native_partial, value._native_input_watermark = 0, b'', 0
    record = dict(kind='B23_SAFETY_INPUT_OBSERVED',
        fields=dict(session='own-session', backend='22', ingress='11', sample='9'),
        server_leader_pid=777, invocation_id='inv-1')
    return value, path, record


def test_native_ack_reader_retains_partial_and_raw_ownership(native_reader):
    value, path, record = native_reader
    assert value.read_native_input_watermark() == 0
    raw = json.dumps(record).encode() + b'\n'
    path.write_bytes(raw[:20])
    assert value.read_native_input_watermark() == 0
    with path.open('ab') as stream: stream.write(raw[20:])
    assert value.read_native_input_watermark() == 9
    assert value.read_native_input_watermark() == 9


@pytest.mark.parametrize('key,bad', [('invocation_id', 'inv-2'), ('server_leader_pid', 888)])
def test_native_ack_other_invocation_cannot_supply_drain_proof(native_reader, key, bad):
    value, path, record = native_reader
    record[key] = bad
    path.write_text(json.dumps(record) + '\n')
    with pytest.raises(RuntimeError, match='ownership mismatch'):
        value.read_native_input_watermark()
    assert value._native_input_watermark == 0


@pytest.mark.parametrize('key,bad', [('session', 'other'), ('backend', '23'), ('ingress', '12')])
def test_native_ack_other_source_cannot_supply_drain_proof(native_reader, key, bad):
    value, path, record = native_reader
    record['fields'][key] = bad
    path.write_text(json.dumps(record) + '\n')
    with pytest.raises(RuntimeError, match='ownership mismatch'):
        value.read_native_input_watermark()


def test_native_ack_corrupt_complete_record_is_not_an_empty_scan(native_reader):
    value, path, record = native_reader
    path.write_bytes(b'{invalid json}\n')
    with pytest.raises(json.JSONDecodeError):
        value.read_native_input_watermark()
    assert value._native_input_watermark == 0


def test_interleaved_gazebo_stdout_is_preserved_but_cannot_poison_native_watermark(native_reader, tmp_path):
    from mecanum_nav_rl.runtime_simulation.b23_runner import RunEvidence
    value, path, record = native_reader
    sink = RunEvidence(tmp_path, 'parent', run_id='B23_TEST', invocation_id='inv-1')
    events = []
    value.emit = lambda name, facts: events.append((name, facts))
    try:
        sink.record('owned_process_output', {
            'process':'server', 'pid':777,
            'text':('[Msg] B23_SAFETY_INPUT_OBSERVED session=own-session backend=22 '
                'ingress=11 sample=28[Msg] admission=0 episode='
                'B23_SAFE_STOP_RECEIPT_INGRESS publisher=B23_SAFE_STOP_RECEIPT_INGRESS '
                'publisher=1')})
        sink.sync()
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        safety = [row for row in rows if row['kind'] == 'B23_SAFETY_INPUT_OBSERVED']
        assert len(safety) == 1
        assert safety[0]['fields'] == {
            'session':'own-session', 'backend':'22', 'ingress':'11', 'sample':'28'}
        assert safety[0]['raw_record']['facts']['text'].startswith('[Msg] B23_SAFETY_INPUT_OBSERVED')
        assert any(row['kind'] == 'B23_NATIVE_OUTPUT_REJECTED'
            and row['fields']['reason'] == 'event_marker_not_at_message_boundary' for row in rows)
        assert value.read_native_input_watermark() == 28

        sink.record('owned_process_output', {
            'process':'server', 'pid':777,
            'text':('[Msg] B23_SAFETY_INPUT_OBSERVED session=own-session backend='
                '[Msg] B23_SAFE_STOP_RECEIPT_INGRESS publisher=33 admission=0 '
                'backend=22 ingress=11 sample=28')})
        sink.sync()
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        assert [row for row in rows if row['kind'] == 'B23_SAFETY_INPUT_OBSERVED'] == safety
        assert any(row['kind'] == 'B23_NATIVE_OUTPUT_REJECTED'
            and row['fields']['reason'] == 'incomplete_native_input_identity' for row in rows)
        assert value.read_native_input_watermark() == 28
    finally:
        sink.close()

    corrupt = {'kind':'B23_SAFETY_INPUT_OBSERVED',
        'fields':{'session':'own-session','backend':'[Msg]','ingress':'11','sample':'28[Msg]'},
        'server_leader_pid':777,'invocation_id':'inv-1'}
    with path.open('a') as stream:
        stream.write(json.dumps(corrupt) + '\n')
    assert value.read_native_input_watermark() == 28
    assert events[-1][0] == 'NATIVE_INPUT_WATERMARK_RECORD_REJECTED'

    valid = dict(kind='B23_SAFETY_INPUT_OBSERVED',
        fields=dict(session='own-session', backend='22', ingress='11', sample='29'),
        server_leader_pid=777, invocation_id='inv-1')
    with path.open('a') as stream:
        stream.write(json.dumps(valid) + '\n')
    assert value.read_native_input_watermark() == 29


def test_native_policy_admission_ack_is_bound_before_stream_freeze(native_reader):
    value, path, record = native_reader
    record['kind'] = 'B23_ADMISSION_ACCEPTED'
    path.write_text(json.dumps(record) + '\n')
    assert value.read_native_input_watermark() == 9


@pytest.mark.parametrize('last_source', ['safe_stop', 'policy'])
def test_freeze_step_streams_keeps_zero_receipts_alive_under_native_watchdog(last_source):
    from mecanum_nav_rl_interfaces.msg import CommandEnvelope, LocalTrainingSafetyInput
    value, clock = worker()
    calls, events = [], []
    source = CommandEnvelope.SOURCE_SAFE_STOP if last_source == 'safe_stop' else CommandEnvelope.SOURCE_POLICY
    adapter = NS(safe_stop_sequence=7, last_output=NS(source=source, source_instance_id=44, sequence=7),
        set_policy_hold=lambda hold: calls.append(('hold', hold)),
        set_stream_enabled=lambda enabled: calls.append(('stream', enabled)))
    value.safety = NS(local_training=adapter)
    value.ingress.last_published_sample_sequence = 9
    value.ingress.last_published_admission_state = LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN
    def inhibit(*, zero_only=False):
        calls.append(('inhibit', zero_only))
        value.ingress.last_published_admission_state = (LocalTrainingSafetyInput.ADMISSION_ZERO_ONLY
            if zero_only else LocalTrainingSafetyInput.ADMISSION_INHIBITED)
    value.ingress.inhibit = inhibit
    value.ingress.pause_admission_publication = lambda: calls.append(('pause_admission',))
    watermark = [9]
    value._native_input_watermark = 9
    def read_watermark():
        value._native_input_watermark = watermark[0]
        return watermark[0]
    value.read_native_input_watermark = read_watermark
    stop = NS(SOURCE_SAFE_STOP=CommandEnvelope.SOURCE_SAFE_STOP)
    value.final = NS(publisher_instance_id=55, last_publication=NS(source=source,
        source_instance_id=44, sequence=7, final_publish_sequence=20),
        publication_for_source_sequence=lambda *, source, sequence: NS(
            source=CommandEnvelope.SOURCE_SAFE_STOP, source_instance_id=44,
            sequence=8, final_publish_sequence=21)
            if source == CommandEnvelope.SOURCE_SAFE_STOP and sequence == 8 else None)
    value.ingress.backend_state = NS(fault_flags=0, applied_final_publish_sequence=20,
        applied_final_publisher_instance_id=55, local_zero_override=False,
        applied_receipt_valid=True, paused=False)
    value.ingress.application_for_receipt = lambda receipt: (
        {'state':value.ingress.backend_state, 'received_ns':clock.ns}
        if receipt.final_publish_sequence == 21 else None)
    value.ingress.receipt_for_publication_sequence = lambda sequence: NS(
        source=__import__('mecanum_nav_rl.core.issued_command_cutoff',
            fromlist=['ReceiptSource']).ReceiptSource.SAFE_STOP,
        final_publisher_instance_id=55, final_command=(0.0, 0.0, 0.0))
    value.last_safe_stop_publish_sequence = 20
    async def pause(seconds):
        await clock.pause(seconds)
        if value.ingress.last_published_sample_sequence == 9:
            value.ingress.last_published_sample_sequence = 10
            watermark[0] = 10
        adapter.safe_stop_sequence = 8
        adapter.last_output = NS(source=stop.SOURCE_SAFE_STOP, source_instance_id=44, sequence=8)
        value.final.last_publication = NS(source=stop.SOURCE_SAFE_STOP,
            source_instance_id=44, sequence=8, final_publish_sequence=21)
        value.ingress.backend_state.applied_final_publish_sequence = 21
        value.ingress.backend_state.applied_physics_iteration = 305
        value.ingress.backend_state.physics_iteration = 305
        value.ingress.backend_state.applied_sim_stamp = NS(sec=3, nanosec=50_000_000)
        value.ingress.backend_state.header = NS(stamp=NS(sec=3, nanosec=50_000_000))
        value.ingress.backend_state.applied_receipt_valid = True
        value.ingress.backend_state.paused = False
    value.pause = pause
    value.emit = lambda name, record: (calls.append((name, record)), events.append((name, record)))
    asyncio.run(value.freeze_step_streams(deadline_ns=clock.ns+20_000_000))
    assert ('hold', True) in calls
    assert ('stream', True) in calls
    assert ('stream', False) not in calls
    assert ('inhibit', False) in calls
    assert events[0][0] == 'INHIBITED_SAFETY_INPUT_DRAINED'
    assert events[0][1]['sample_sequence'] == 10
    assert events[0][1]['native_input_watermark'] == 10
    names = [name for name, _ in events]
    assert names.index('INHIBITED_SAFETY_INPUT_DRAINED') < names.index('ADMISSION_STREAM_FROZEN')
    assert names.index('ADMISSION_STREAM_FROZEN') < names.index('STEP_STREAMS_FROZEN')
    assert calls.index(('inhibit', False)) < calls.index(('pause_admission',))
    assert adapter.last_output.source == CommandEnvelope.SOURCE_SAFE_STOP
    assert calls.index(('hold', True)) < calls.index(('stream', True))
    assert events[-1][0] == 'STEP_STREAMS_FROZEN'
    assert events[-1][1]['source'] == CommandEnvelope.SOURCE_SAFE_STOP
    assert events[-1][1]['publish_sequence'] == 21


def test_freeze_step_streams_recovers_from_coalesced_exact_safe_stop_receipt():
    import threading
    from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
    from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity
    from mecanum_nav_rl_interfaces.msg import CommandEnvelope, LocalTrainingSafetyInput

    value, clock = worker()
    life = EpisodeLifecycleIdentity(1, 1, 1)
    candidate_view = NS(source=ReceiptSource.SAFE_STOP, lifecycle=life,
        final_publisher_instance_id=55, final_publish_sequence=22,
        source_sequence=10, final_command=(0.0, 0.0, 0.0))
    candidate = NS(source=CommandEnvelope.SOURCE_SAFE_STOP, sequence=10,
        final_publish_sequence=22, final_publisher_instance_id=55)
    state = NS(fault_flags=0, paused=False, local_zero_override=False,
        applied_receipt_valid=True, applied_final_publisher_instance_id=55,
        applied_final_publish_sequence=22, applied_physics_iteration=305,
        physics_iteration=305, applied_sim_stamp=NS(sec=3, nanosec=50_000_000),
        header=NS(stamp=NS(sec=3, nanosec=50_000_000)))
    calls, events, watermark = [], [], [9]
    adapter = NS(safe_stop_sequence=7,
        last_output=NS(source=CommandEnvelope.SOURCE_SAFE_STOP, source_instance_id=44, sequence=7),
        set_policy_hold=lambda hold: calls.append(('hold', hold)),
        set_stream_enabled=lambda enabled: calls.append(('stream', enabled)))
    value.safety = NS(local_training=adapter)
    value.ingress = NS(fault=None, backend_state=state, lifecycle=life,
        last_published_sample_sequence=9,
        last_published_admission_state=LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN,
        receipts=[candidate_view], lock=threading.RLock())
    def inhibit(*, zero_only=False):
        calls.append(('inhibit', zero_only))
        value.ingress.last_published_admission_state = (
            LocalTrainingSafetyInput.ADMISSION_ZERO_ONLY if zero_only
            else LocalTrainingSafetyInput.ADMISSION_INHIBITED)
    value.ingress.inhibit = inhibit
    value.ingress.pause_admission_publication = lambda: calls.append(('pause_admission',))
    value.ingress.application_for_receipt = lambda receipt: (
        {'state':state,'received_ns':clock.ns}
        if receipt.final_publish_sequence == candidate.final_publish_sequence else None)
    value.ingress.receipt_for_publication_sequence = lambda sequence: (
        candidate_view if sequence == candidate.final_publish_sequence else None)
    value.read_native_input_watermark = lambda: watermark[0]
    value._native_input_watermark = 9
    value.final = NS(publisher_instance_id=55, last_publication=None,
        publication_for_source_sequence=lambda *, source, sequence: (
            candidate if source == CommandEnvelope.SOURCE_SAFE_STOP and sequence == 10 else None))
    async def pause(seconds):
        await clock.pause(seconds)
        value.ingress.last_published_sample_sequence = 10
        watermark[0] = 10
        adapter.safe_stop_sequence = 8
        adapter.last_output = NS(source=CommandEnvelope.SOURCE_SAFE_STOP,
            source_instance_id=44, sequence=8)
    value.pause = pause
    value.emit = lambda name, fields: events.append((name, fields))

    asyncio.run(value.freeze_step_streams(deadline_ns=clock.ns + 20_000_000))

    frozen = next(fields for name, fields in events if name == 'STEP_STREAMS_FROZEN')
    assert frozen['source'] == CommandEnvelope.SOURCE_SAFE_STOP
    assert frozen['source_sequence'] == 10
    assert frozen['publish_sequence'] == 22
    assert frozen['application_iteration'] == 305


def test_ingress_retains_valid_application_by_exact_safe_stop_receipt_key():
    import threading
    from rclpy.serialization import serialize_message
    from mecanum_nav_rl.core.issued_command_cutoff import IssuedCommandReceiptView, ReceiptSource
    from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendSessionIdentity
    from mecanum_nav_rl.runtime_simulation.local_training_ingress import LocalTrainingIngress
    from mecanum_nav_rl_interfaces.msg import SafetyLifecycleState, SimulationContactState

    ingress = LocalTrainingIngress.__new__(LocalTrainingIngress)
    identity = EpisodeLifecycleIdentity(1, 2, 3)
    lifecycle = SafetyLifecycleState()
    lifecycle.episode_generation, lifecycle.reset_epoch, lifecycle.runtime_generation = 1, 2, 3
    ingress.lock = threading.RLock()
    ingress.identity = BackendSessionIdentity('session-1', 'a'*64, 'b'*64, 12, 13)
    ingress.final_publisher_id = 55
    ingress.safe_stop_source_id = 66
    ingress.lifecycle = lifecycle
    ingress._last_applied_sequence = 20
    ingress._application_bytes = __import__('collections').OrderedDict()
    ingress._application_received_ns = __import__('collections').OrderedDict()
    ingress._receipt_views = __import__('collections').OrderedDict()
    ingress._unresolved_applications = __import__('collections').OrderedDict()
    ingress.emit = lambda *_args: None
    ingress.now = lambda: 130

    receipt = IssuedCommandReceiptView(1_050_000_000, 55, 21, ReceiptSource.SAFE_STOP,
        66, 8, 0, '', identity, 'session-1', 'a'*64, (0.0, 0.0, 0.0),
        110, 'base_link', True)
    ingress._receipt_views[21] = receipt
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
    ros_receipt = FinalIssuedCommandReceipt()
    ros_receipt.header.frame_id = 'base_link'
    ros_receipt.header.stamp.sec, ros_receipt.header.stamp.nanosec = 1, 50_000_000
    ros_receipt.episode_generation, ros_receipt.reset_epoch, ros_receipt.runtime_generation = 1, 2, 3
    ros_receipt.source = FinalIssuedCommandReceipt.SOURCE_SAFE_STOP
    ros_receipt.sequence = 8
    ros_receipt.source_instance_id = 66
    ros_receipt.step_index = 0
    ros_receipt.transition_id = ''
    ros_receipt.final_publisher_instance_id = 55
    ros_receipt.final_publish_sequence = 21
    ingress._receipt_bytes = __import__('collections').OrderedDict(
        [(21, serialize_message(ros_receipt))])
    status = SimulationContactState()
    status.session_id, status.config_hash, status.backend_instance_id = 'session-1', 'a'*64, 13
    status.episode_generation, status.reset_epoch, status.runtime_generation = 1, 2, 3
    status.header.frame_id = 'b2_training_arena'
    status.header.stamp.sec, status.header.stamp.nanosec = 1, 60_000_000
    status.status_sequence = 44
    status.physics_iteration = 305
    status.paused = False
    status.fault_flags = 0
    status.local_zero_override = False
    status.applied_receipt_valid = True
    status.applied_final_publisher_instance_id = 55
    status.applied_final_publish_sequence = 21
    status.applied_physics_iteration = 305
    status.applied_sim_stamp.sec, status.applied_sim_stamp.nanosec = 1, 60_000_000

    raw = serialize_message(status)
    ingress._record_application(status, raw, 120)
    proof = ingress.application_for_receipt(receipt)

    assert proof is not None
    assert proof['state'].applied_final_publish_sequence == 21
    assert proof['state'].applied_physics_iteration == 305
    assert proof['received_ns'] == 120
    # Production FinalPublicationView returns a generated ROS message deserialized
    # from retained raw CDR; join its semantic fields to the immutable receipt
    # view without reserializing and comparing potentially variable padding.
    assert ingress.application_for_receipt(ros_receipt) == proof
    ros_receipt.final_publish_sequence = 22
    assert ingress.application_for_receipt(ros_receipt) is None
    ros_receipt.final_publish_sequence = 21
    ros_receipt.final_command.linear.x = 0.1
    assert ingress.application_for_receipt(ros_receipt) is None
    ros_receipt.sequence += 1
    assert ingress.application_for_receipt(ros_receipt) is None
    wrong = IssuedCommandReceiptView(1_050_000_000, 55, 22, ReceiptSource.SAFE_STOP,
        66, 9, 0, '', identity, 'session-1', 'a'*64, (0.0, 0.0, 0.0),
        110, 'base_link', True)
    assert ingress.application_for_receipt(wrong) is None


def test_final_publication_view_selects_retained_receipt_when_latest_advances():
    from collections import OrderedDict
    from rclpy.serialization import serialize_message
    from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
    from mecanum_nav_rl.runtime_simulation.b23_runner import FinalPublicationView
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt

    def receipt(*, sequence, publish_sequence):
        value = FinalIssuedCommandReceipt()
        value.final_publisher_instance_id = 55
        value.final_publish_sequence = publish_sequence
        value.source = FinalIssuedCommandReceipt.SOURCE_SAFE_STOP
        value.sequence = sequence
        value.source_instance_id = 44
        return value

    target, latest = receipt(sequence=8, publish_sequence=21), receipt(sequence=9, publish_sequence=22)
    view = FinalPublicationView(55)
    view.ingress = NS(
        receipts=[
            NS(source=ReceiptSource.SAFE_STOP, source_sequence=8,
                final_publisher_instance_id=55, final_publish_sequence=21),
            NS(source=ReceiptSource.SAFE_STOP, source_sequence=9,
                final_publisher_instance_id=55, final_publish_sequence=22),
        ],
        _receipt_bytes=OrderedDict([
            (21, serialize_message(target)),
            (22, serialize_message(latest)),
        ]),
    )

    assert view.last_publication.sequence == 9
    selected = view.publication_for_source_sequence(
        source=FinalIssuedCommandReceipt.SOURCE_SAFE_STOP, sequence=8)
    assert selected.sequence == 8
    assert selected.final_publish_sequence == 21


def test_freeze_step_streams_uses_retained_exact_application_when_latest_status_advances():
    from mecanum_nav_rl_interfaces.msg import CommandEnvelope, LocalTrainingSafetyInput
    value, clock = worker()
    calls, events = [], []
    adapter = NS(safe_stop_sequence=7,
        last_output=NS(source=CommandEnvelope.SOURCE_SAFE_STOP, source_instance_id=44, sequence=7),
        set_policy_hold=lambda hold: calls.append(('hold', hold)),
        set_stream_enabled=lambda enabled: calls.append(('stream', enabled)))
    value.safety = NS(local_training=adapter)
    value.ingress.last_published_sample_sequence = 9
    value.ingress.last_published_admission_state = LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN
    def inhibit(*, zero_only=False):
        calls.append(('inhibit', zero_only))
        value.ingress.last_published_admission_state = (
            LocalTrainingSafetyInput.ADMISSION_ZERO_ONLY if zero_only
            else LocalTrainingSafetyInput.ADMISSION_INHIBITED)
    value.ingress.inhibit = inhibit
    value.ingress.pause_admission_publication = lambda: calls.append(('pause_admission',))
    watermark = [9]
    value._native_input_watermark = 9
    value.read_native_input_watermark = lambda: watermark[0]
    value.ingress.backend_state = NS(fault_flags=0, applied_final_publish_sequence=20,
        applied_final_publisher_instance_id=55, local_zero_override=False,
        applied_receipt_valid=True, paused=False)
    value.ingress.application_for_receipt = lambda receipt: (
        {'state':NS(applied_receipt_valid=True, local_zero_override=False, fault_flags=0,
            applied_final_publisher_instance_id=55,
            applied_final_publish_sequence=receipt.final_publish_sequence,
            applied_physics_iteration=305, physics_iteration=305,
            applied_sim_stamp=NS(sec=3, nanosec=50_000_000),
            header=NS(stamp=NS(sec=3, nanosec=50_000_000))),
         'received_ns':clock.ns}
        if receipt.final_publish_sequence == 21 else None)
    from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
    value.ingress.receipt_for_publication_sequence = lambda sequence: NS(
        source=ReceiptSource.SAFE_STOP, final_publisher_instance_id=55,
        final_command=(0.0, 0.0, 0.0)) if sequence == 22 else None
    value.ingress.lifecycle = object()
    stop = NS(SOURCE_SAFE_STOP=CommandEnvelope.SOURCE_SAFE_STOP)
    exact_receipt = NS(source=stop.SOURCE_SAFE_STOP, source_instance_id=44,
        sequence=8, final_publish_sequence=21)
    later_receipt = NS(source=stop.SOURCE_SAFE_STOP, source_instance_id=44,
        sequence=9, final_publish_sequence=22)
    selected = []
    value.final = NS(publisher_instance_id=55, last_publication=NS(
        source=stop.SOURCE_SAFE_STOP, source_instance_id=44, sequence=7,
        final_publish_sequence=20), publication_for_source_sequence=lambda *, source, sequence: (
            selected.append((source, sequence)) or (exact_receipt
                if (source, sequence) == (stop.SOURCE_SAFE_STOP, 8) else None)))
    value.last_safe_stop_publish_sequence = 20

    async def pause(seconds):
        await clock.pause(seconds)
        if value.ingress.last_published_sample_sequence == 9:
            value.ingress.last_published_sample_sequence = 10
            watermark[0] = 10
        adapter.safe_stop_sequence = 8
        adapter.last_output = NS(source=stop.SOURCE_SAFE_STOP, source_instance_id=44, sequence=8)
        # The exact target remains retained, while the latest receipt advances
        # before freeze_step_streams can inspect the view.
        value.final.last_publication = later_receipt
        # The exact target receipt was applied, then a later native status
        # replaced backend_state before the coroutine could inspect it.
        value.ingress.backend_state.applied_final_publish_sequence = 22
        value.ingress.backend_state.applied_receipt_valid = True
        value.ingress.backend_state.applied_physics_iteration = 306
        value.ingress.backend_state.physics_iteration = 306
        value.ingress.backend_state.applied_final_publisher_instance_id = 55
    value.pause = pause
    value.emit = lambda name, record: (calls.append((name, record)), events.append((name, record)))

    asyncio.run(value.freeze_step_streams(deadline_ns=clock.ns + 20_000_000))

    assert events[-1][0] == 'STEP_STREAMS_FROZEN'
    assert events[-1][1]['publish_sequence'] == 21
    assert events[-1][1]['application_iteration'] == 305
    assert (stop.SOURCE_SAFE_STOP, 8) in selected


def test_r02_held_receipt_path_enables_real_safety_timer_before_waiting_for_receipt():
    import ast
    import inspect
    import textwrap
    from mecanum_nav_rl.runtime_simulation.b23_runner import TrainingWorkerIO

    tree = ast.parse(textwrap.dedent(inspect.getsource(TrainingWorkerIO.policy_step)))
    hook = next(node for node in ast.walk(tree) if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == 'close_after_held_receipt'
        and any(isinstance(op, ast.IsNot) for op in node.test.ops))
    body = hook.body
    def call_index(method, value):
        for index, statement in enumerate(body):
            calls = [node for node in ast.walk(statement) if isinstance(node, ast.Call)]
            if any(isinstance(call.func, ast.Attribute) and call.func.attr == method
                    and call.args and isinstance(call.args[0], ast.Constant)
                    and call.args[0].value is value for call in calls):
                return index
        raise AssertionError(f'{method}({value}) is missing in held-receipt path')
    release_hold = call_index('set_policy_hold', False)
    stream_on = call_index('set_stream_enabled', True)
    wait_receipt = next(index for index, statement in enumerate(body)
        if any(isinstance(node, ast.Constant) and node.value == 'actual held POLICY publication receipt'
            for node in ast.walk(statement)))
    assert release_hold < wait_receipt
    assert release_hold < stream_on < wait_receipt


@pytest.mark.parametrize('close_after', ['safe_stop', 'admission_inhibited'])
def test_r02_close_fault_paths_align_receipt_window_before_pending_bind(close_after):
    from builtin_interfaces.msg import Time

    value, clock = worker()
    events = []
    async def freeze_step_streams(*, deadline_ns):
        events.append('fresh_applied_zero')
        return {'zero_receipt_age_ns': 0}
    async def align_policy_window(*, deadline_ns, zero_witness):
        events.append('scan_alignment')
        assert zero_witness == {'zero_receipt_age_ns': 0}
        return zero_witness
    async def refresh_zero(*, deadline_ns, zero_witness=None):
        events.append('refresh_zero')
        assert zero_witness is not None
        return {'zero_receipt_age_ns': 0, 'refreshed': True}
    value.freeze_step_streams = freeze_step_streams
    value.align_policy_step_launch_window = align_policy_window
    value.refresh_zero_before_pending_bind = refresh_zero
    value.safety = NS(local_training=NS(set_stream_enabled=lambda enabled:
        events.append(('stream_enabled', enabled))))
    value.ingress.lifecycle = NS(barrier_stamp=Time())
    value.ros_now = lambda: 1_000_000_000

    class BindReached(Exception):
        pass
    class B1:
        def begin_step(self):
            events.append('begin_pending_step')
            raise BindReached

    with pytest.raises(BindReached):
        asyncio.run(value.policy_step(B1(), (0.4, 0.0, 0.0),
            close_after_held_receipt=close_after))
    assert events == ['fresh_applied_zero', 'scan_alignment', 'refresh_zero',
        ('stream_enabled', False), 'begin_pending_step']

    # Ordinary POLICY and both held-receipt fault cases share the production
    # scan-boundary alignment; the fault begins only after an actual receipt.
    events.clear()
    class AlignmentReached(Exception):
        pass
    async def observe_alignment(*, deadline_ns, zero_witness):
        events.append('scan_alignment')
        raise AlignmentReached
    value.align_policy_step_launch_window = observe_alignment
    with pytest.raises(AlignmentReached):
        asyncio.run(value.policy_step(B1(), (0.4, 0.0, 0.0)))
    assert events == ['fresh_applied_zero', 'scan_alignment']


@pytest.mark.parametrize('timing', ['ready','late_commit','late_publish','r09b_callback',
    'r09b_before_bind','first_sample_races_candidate_delivery','pending_cutoff_dedup',
    'nominal_issued_cutoff','prebind_elapsed_deadline'])
def test_policy_step_orders_ack_sample_issue_safety_application_and_commit(timing):
    from builtin_interfaces.msg import Time
    from mecanum_nav_rl_interfaces.msg import CommandEnvelope, LocalTrainingSafetyInput, SafetyLifecycleState
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendControlAck, B1SnapshotPending
    from rclpy.serialization import serialize_message
    value, clock = worker()
    value.deadline_ns = clock.ns + 3_000_000_000
    ros = lambda: clock.ns
    value.ros_now = ros
    value.document = {'training': {'local_training': {'max_vx_mps': .25, 'max_vy_mps': .2, 'max_wz_radps': .8}}}
    value.policy_source_id = 33
    history = []
    prebind_refresh_times = []
    async def aligned_window(*, deadline_ns, zero_witness):
        history.append(('scan_alignment', deadline_ns))
        if timing == 'prebind_elapsed_deadline':
            await clock.pause(.150)
        return zero_witness
    # This test isolates transaction ordering; launch-window cadence is
    # covered by test_policy_step_waits_for_applied_zero_after_cutoff... .
    value.align_policy_step_launch_window = aligned_window
    async def refreshed_zero(*, deadline_ns, zero_witness=None):
        history.append(('prebind_zero_refresh', deadline_ns))
        assert zero_witness is not None
        if timing == 'prebind_elapsed_deadline':
            await clock.pause(.150)
        prebind_refresh_times.append(clock.ns)
        return {'receipt':'newly applied zero'}
    value.refresh_zero_before_pending_bind = refreshed_zero
    life = SafetyLifecycleState(); life.barrier_stamp = Time(nanosec=900_000_000)
    life.episode_generation, life.reset_epoch, life.runtime_generation = 1, 2, 3
    value.ingress.backend_state = NS(fault_flags=0, applied_final_publish_sequence=2,
        applied_final_publisher_instance_id=55, applied_receipt_valid=False,
        local_zero_override=False, paused=False,
        applied_physics_iteration=0, physics_iteration=0,
        applied_sim_stamp=NS(sec=0, nanosec=0), header=NS(stamp=NS(sec=0, nanosec=0)))
    def set_stream_enabled(enabled):
        history.append(('stream', enabled))
        if enabled and bind_times and adapter.policy_hold:
            # Model the real Safety timer running between stream enable and
            # hold release: it emits a SAFE_STOP after OP_BIND_PENDING_STEP,
            # which revokes the pending native admission token.
            history.append(('safe_stop_race_after_pending_bind', clock.ns))
        if enabled and timing == 'r09b_callback' and adapter.command is not None:
            value.ingress.backend_state.applied_final_publish_sequence = 4
            value.ingress.backend_state.applied_receipt_valid = True
            value.ingress.backend_received_ns = clock.ns
    def safety_tick():
        history.append(('safety_tick', clock.ns))
    adapter = NS(safe_stop_sequence=1, policy_hold=True,
        last_output=NS(source=CommandEnvelope.SOURCE_SAFE_STOP, source_instance_id=44, sequence=1),
        command=None, noisy=None, set_stream_enabled=set_stream_enabled,
        tick=safety_tick,
        set_policy_hold=lambda state: (setattr(adapter, 'policy_hold', state), history.append(('hold', state))),
        scan_period_ns=(1_000_000_000 if timing == 'prebind_elapsed_deadline'
            else 100_000_000), last_tick_ros_ns=1_000_000_000)
    value.safety = NS(local_training=adapter)
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
    zero_policy_receipt = FinalIssuedCommandReceipt()
    zero_policy_receipt.final_publisher_instance_id=55
    zero_policy_receipt.final_publish_sequence=4
    zero_policy_receipt.source=FinalIssuedCommandReceipt.SOURCE_POLICY
    zero_policy_receipt.sequence=1
    safe_stop_receipt = FinalIssuedCommandReceipt()
    safe_stop_receipt.final_publisher_instance_id=55
    safe_stop_receipt.final_publish_sequence=3
    safe_stop_receipt.source=FinalIssuedCommandReceipt.SOURCE_SAFE_STOP
    safe_stop_receipt.sequence=2
    value.final = NS(publisher_instance_id=55, last_publication=NS(source=CommandEnvelope.SOURCE_SAFE_STOP,
        source_instance_id=44, sequence=1, final_publish_sequence=2),
        publication_for_source_sequence=lambda *, source, sequence: (
            safe_stop_receipt if (source, sequence) ==
                (FinalIssuedCommandReceipt.SOURCE_SAFE_STOP, 2) else
            zero_policy_receipt if (source, sequence) ==
                (FinalIssuedCommandReceipt.SOURCE_POLICY, 1) else None))
    value.ingress.lifecycle = life
    value.ingress.last_published_sample_sequence = 1
    value.ingress.last_published_admission_state = LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN
    def inhibit(*, zero_only=False):
        value.ingress.last_published_admission_state = (LocalTrainingSafetyInput.ADMISSION_ZERO_ONLY
            if zero_only else LocalTrainingSafetyInput.ADMISSION_INHIBITED)
        history.append(('admission_inhibit', zero_only))
    value.ingress.inhibit = inhibit
    value.ingress.pause_admission_publication = lambda: history.append(('freeze_admission',))
    value.ingress.scans = {}
    value.ingress.profile = {'safety_period_ms':20, 'final_command_timeout_ms':100,
        'scan_max_age_ms':500}
    native_watermark = [1]
    value._native_input_watermark = 1
    def read_watermark():
        value._native_input_watermark = native_watermark[0]
        return native_watermark[0]
    value.read_native_input_watermark = read_watermark
    def emit(event, facts):
        history.append((event, facts))
        if event == 'POLICY_STEP_COMPLETE' and timing == 'late_publish':
            clock.ns = b1_begin_times[0] + 2_000_000_001
    value.emit = emit
    bind_times = []
    bind_deadlines = []
    async def transact(operation, **fields):
        bind_times.append(clock.ns)
        bind_deadlines.append(fields.get('deadline_ns'))
        history.append(('bind', operation))
        req, res = Control.Request(), Control.Response()
        req.operation = operation; req.pending_step_index = fields['pending_step_index']
        req.action_barrier_stamp = fields['action_barrier_stamp']
        res.pending_admission_token = [7]*16
        return BackendControlAck(serialize_message(req), serialize_message(res), clock.ns)
    value.control = NS(transact=transact)
    armed = []
    def arm(ack, *, publish_admission=True):
        history.append(('arm', ack.observed_steady_ns, publish_admission)); armed.append(ack)
    value.ingress.arm_pending = arm
    def publish(envelope):
        history.append(('publish', envelope)); adapter.command = envelope
        if timing == 'first_sample_races_candidate_delivery':
            # This callback is after the real ACK/arm point but races with
            # delivery of the staged POLICY candidate to Safety.
            value.ingress.last_published_sample_sequence = 3
            value.ingress.last_published_admission_state = LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN
            adapter.noisy = NS(admission_state=LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN,
                admission_token=[7]*16, sample_sequence=3)
            history.append(('post_ack_admission_sample_ready', clock.ns))
    value.policy_publisher = NS(publish=publish)
    async def pause(seconds):
        await clock.pause(seconds)
        adapter.last_tick_ros_ns = clock.ns
        if armed and timing != 'first_sample_races_candidate_delivery':
            value.ingress.last_published_sample_sequence = 3
            value.ingress.last_published_admission_state = LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN
            native_watermark[0] = 3
            adapter.noisy = NS(admission_state=LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN,
                admission_token=[7]*16, sample_sequence=3)
            history.append(('post_ack_admission_sample_ready', clock.ns))
        else:
            value.ingress.last_published_sample_sequence = 2
            value.ingress.last_published_admission_state = LocalTrainingSafetyInput.ADMISSION_INHIBITED
            native_watermark[0] = 2
            adapter.safe_stop_sequence = 2
            adapter.last_output = NS(source=CommandEnvelope.SOURCE_SAFE_STOP,
                source_instance_id=44, sequence=2)
            value.final.last_publication = NS(source=CommandEnvelope.SOURCE_SAFE_STOP,
                source_instance_id=44, sequence=2, final_publish_sequence=3)
            value.ingress.backend_state.applied_final_publish_sequence = 3
            value.ingress.backend_state.applied_receipt_valid = True
            value.ingress.backend_state.applied_physics_iteration = 12
            value.ingress.backend_state.physics_iteration = 12
            value.ingress.backend_state.applied_sim_stamp = NS(sec=1, nanosec=200_000_000)
            value.ingress.backend_state.header.stamp = NS(sec=1, nanosec=200_000_000)
        if adapter.command and timing != 'pending_cutoff_dedup':
            value.ingress.scans[clock.ns] = True
    value.pause = pause
    value.ingress.application_for_receipt = lambda receipt: (
        {'state':value.ingress.backend_state, 'received_ns':clock.ns}
        if (receipt.final_publish_sequence == 3
            and value.ingress.backend_state.applied_final_publish_sequence == 3
            and value.ingress.backend_state.applied_receipt_valid) else None)
    from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
    value.ingress.receipt_for_publication_sequence = lambda sequence: NS(
        source=ReceiptSource.SAFE_STOP, final_publish_sequence=sequence,
        final_publisher_instance_id=55, final_command=(0.,0.,0.)) if sequence == 3 else None
    pending = NS(step_index=1, transition_id='actual-b1-token')
    b1_begin_times = []
    commit_calls = []
    issue_times = []
    nominal_cutoff = None
    def record(envelope, *, action_barrier_ns):
        nonlocal minimum_cutoff, nominal_cutoff
        issue_times.append(clock.ns)
        history.append(('issued', envelope.sequence))
        assert any(row[0] == 'publish' and row[1] is envelope for row in history)
        assert action_barrier_ns <= envelope.header.stamp.sec*10**9+envelope.header.stamp.nanosec
        issued_stamp = envelope.header.stamp.sec*10**9+envelope.header.stamp.nanosec
        minimum_cutoff = issued_stamp + (1 if timing == 'nominal_issued_cutoff' else 100_000_000)
        if timing == 'nominal_issued_cutoff':
            nominal_cutoff = issued_stamp + 90_000_000
            value.ingress.scans[nominal_cutoff] = True
        if timing == 'pending_cutoff_dedup':
            value.ingress.scans[minimum_cutoff] = True
            value.ingress.scans[minimum_cutoff + 2_000_000] = True
            value.ingress.scans[minimum_cutoff + 4_000_000] = True
            clock.ns = minimum_cutoff + 4_000_000
    transition = object()
    minimum_cutoff = None
    commit_attempts = {}
    def commit(cutoff):
        commit_calls.append(cutoff)
        if timing == 'nominal_issued_cutoff':
            if cutoff == nominal_cutoff:
                return transition
            raise B1SnapshotPending('waiting for the exact nominal-period sample cutoff')
        if timing == 'pending_cutoff_dedup':
            commit_attempts[cutoff] = commit_attempts.get(cutoff, 0) + 1
            if cutoff == max(value.ingress.scans):
                raise B1SnapshotPending('newest cutoff awaits its adjacent receipt')
            if cutoff == min(value.ingress.scans):
                raise B1SnapshotPending('old cutoff is retained only as stale fallback')
            if commit_attempts[cutoff] < 3:
                raise B1SnapshotPending('application facts pending for this cutoff')
            return transition
        if minimum_cutoff is None:
            raise B1SnapshotPending('application not received yet')
        if cutoff == minimum_cutoff:
            raise B1SnapshotPending('receipt boundary at cutoff is not applied')
        if timing == 'late_commit': clock.ns = b1_begin_times[0] + 2_000_000_001
        return transition
    def begin_step():
        history.append(('b1_begin_step',))
        b1_begin_times.append(clock.ns)
        return pending
    b1 = NS(begin_step=begin_step, record_issuance=record, commit_step=commit)
    callback_calls=[]
    async def after_policy_applied(receipt, state, deadline_ns, applied_received_ns):
        history.append(('r09b_fixture_after_exact_zero_application',
            receipt.final_publish_sequence, state.applied_final_publish_sequence,
            applied_received_ns))
        callback_calls.append((receipt,state,deadline_ns,applied_received_ns))
    before_issue_calls=[]
    async def before_pending_bind(deadline_ns, token, barrier_ns, zero_witness):
        callback_started_ns = clock.ns
        assert ('stream', True) in history
        await value.pause(.120)
        assert clock.ns - callback_started_ns >= 120_000_000
        assert adapter.last_output.source == CommandEnvelope.SOURCE_SAFE_STOP
        assert value.final.last_publication.source == CommandEnvelope.SOURCE_SAFE_STOP
        history.append(('r09b_fixture_before_pending_bind', token.step_index,
            token.transition_id, barrier_ns, deadline_ns,
            zero_witness['receipt'].final_publish_sequence,
            zero_witness['state'].applied_final_publish_sequence, clock.ns))
        before_issue_calls.append((deadline_ns, token, barrier_ns, zero_witness,
            callback_started_ns, clock.ns))
    async def wait_r09b_clear_zero(*, deadline_ns):
        history.append(('r09b_clear_scan_zero_applied', deadline_ns))
    if timing == 'r09b_before_bind':
        value.wait_r09b_restored_scan_zero_before_bind = wait_r09b_clear_zero
    async def align_r09b_application_cutoff(b1_adapter, *, policy_receipt,
            minimum_cutoff_ns, deadline_ns):
        history.append(('r09b_application_cutoff_aligned',
            policy_receipt.final_publish_sequence, minimum_cutoff_ns, deadline_ns))
    value.align_r09b_application_cutoff = align_r09b_application_cutoff
    if timing in ('ready','r09b_callback','r09b_before_bind',
            'first_sample_races_candidate_delivery','nominal_issued_cutoff',
            'prebind_elapsed_deadline'):
        kwargs = ({'after_policy_applied':after_policy_applied}
            if timing=='r09b_callback' else
            {'before_pending_bind':before_pending_bind}
            if timing=='r09b_before_bind' else {})
        action = (0.,0.,0.) if timing in ('r09b_callback','r09b_before_bind') else (0.,.4,0.)
        assert asyncio.run(value.policy_step(b1, action, **kwargs)) is transition
    else:
        if timing == 'pending_cutoff_dedup':
            assert asyncio.run(value.policy_step(b1, (0., .4, 0.))) is transition
        else:
            with pytest.raises(TimeoutError, match='step deadline'):
                asyncio.run(value.policy_step(b1, (0., .4, 0.)))
    if timing == 'pending_cutoff_dedup':
        pending_events = [facts for row in history
            if isinstance(row, tuple) and len(row) == 2
            for name, facts in (row,) if name == 'POLICY_CUTOFF_PENDING']
        emitted = [(facts['cutoff_ns'], facts['reason']) for facts in pending_events]
        assert len(emitted) >= 2, f'expected multiple pending cutoffs: {history!r}'
        assert len(emitted) == len(set(emitted)), f'pending cutoff evidence was duplicated: {history!r}'
        assert commit_calls[:3] == sorted(value.ingress.scans, reverse=True), (
            f'policy step must try freshest cutoff first: {commit_calls!r}')
        repeated_cutoffs = {cutoff for cutoff in commit_calls
            if commit_calls.count(cutoff) > 1}
        assert len(repeated_cutoffs) >= 2, (
            f'fixture must retry multiple distinct cutoffs: {commit_calls!r}')
    if timing == 'nominal_issued_cutoff':
        assert commit_calls == [nominal_cutoff], (
            f'production runner skipped the actual post-issuance cutoff within the nominal 100 ms period: {commit_calls!r}')
    if timing == 'prebind_elapsed_deadline':
        assert bind_deadlines == [b1_begin_times[0] + 2_000_000_000], (
            f'B1 step deadline must start at the actual B1 slot, after pre-bind safety preparation; '
            f'begin={b1_begin_times!r}, bind_deadline={bind_deadlines!r}')
    tags = [row[0] for row in history]
    assert tags.index('hold') < tags.index('bind') < tags.index('arm') < tags.index('publish') < tags.index('issued')
    assert ('hold', True) in history
    assert ('stream', True) in history
    stream_off = history.index(('stream', False))
    bind = next(i for i, row in enumerate(history) if row[0] == 'bind')
    issued = next(i for i, row in enumerate(history) if row[0] == 'issued')
    stream_on_after_issue = next(i for i, row in enumerate(history)
        if i > issued and row == ('stream', True))
    immediate_policy_tick = next(i for i, row in enumerate(history)
        if i > issued and row[0] == 'safety_tick')
    hold_off_after_issue = next(i for i, row in enumerate(history)
        if i > issued and row == ('hold', False))
    refresh = next((i for i,row in enumerate(history) if row[0]=='prebind_zero_refresh'),None)
    if timing == 'r09b_before_bind':
        assert refresh is None
        assert stream_off < bind < issued < hold_off_after_issue < stream_on_after_issue
    else:
        assert refresh is not None
        assert refresh < stream_off < bind < issued < hold_off_after_issue < stream_on_after_issue
    sample_ready = next(i for i, row in enumerate(history)
        if row[0] == 'post_ack_admission_sample_ready')
    if timing == 'first_sample_races_candidate_delivery':
        assert sample_ready < issued < hold_off_after_issue < stream_on_after_issue, (
            f'earliest post-ACK sample racing candidate delivery was discarded: {history!r}')
        assert ('freeze_admission',) in history
        assert value.safety.local_training.noisy.sample_sequence == 3
    else:
        assert issued < sample_ready < hold_off_after_issue < stream_on_after_issue, (
        f'POLICY candidate must be staged after ACK while the stream is closed, then await '
        f'the fresh admission before Safety can emit it: {history!r}')
    assert stream_on_after_issue < immediate_policy_tick, (
        f'production POLICY path did not evaluate Safety immediately after enabling the admitted candidate: {history!r}')
    assert not any(row[0] == 'safe_stop_race_after_pending_bind' for row in history)
    envelope = next(row[1] for row in history if row[0] == 'publish')
    frozen = next(row[1] for row in history
        if isinstance(row, tuple) and len(row) == 2 and row[0] == 'STEP_STREAMS_FROZEN')
    scan_period_ns = value.safety.local_training.scan_period_ns
    next_scan_boundary = ((frozen['application_stamp_ns'] // scan_period_ns) + 1) * scan_period_ns
    watchdog_reference_ns = (before_issue_calls[0][5] if timing == 'r09b_before_bind'
        else prebind_refresh_times[0] if timing == 'prebind_elapsed_deadline'
        else frozen['steady_ns'])
    assert bind_times and bind_times[0] - watchdog_reference_ns < 100_000_000, (
        f'pending bind waited through an unnecessary scan phase and consumed the native zero watchdog budget: {history!r}')
    assert issue_times and issue_times[0] - watchdog_reference_ns < 100_000_000, (
        f'POLICY issuance exceeded the unchanged native zero watchdog budget: {history!r}')
    issued_ros_ns = envelope.header.stamp.sec * 10**9 + envelope.header.stamp.nanosec
    assert issued_ros_ns < next_scan_boundary, (
        f'POLICY was not staged before the next scan cutoff: {history!r}')
    assert envelope.twist.linear.y == pytest.approx(
        0. if timing in ('r09b_callback','r09b_before_bind') else .08)
    assert len([row for row in history if row[0] == 'publish']) == 1
    assert len(commit_calls) >= 1
    issued_stamp = envelope.header.stamp.sec*10**9 + envelope.header.stamp.nanosec
    expected_delay = (100_000_000 if timing in (
        'r09b_callback','r09b_before_bind','pending_cutoff_dedup') else 1)
    expected_minimum = issued_stamp + expected_delay
    assert min(commit_calls) >= expected_minimum
    if timing == 'r09b_callback':
        assert len(callback_calls)==1
        callback_index=tags.index('r09b_fixture_after_exact_zero_application')
        assert callback_index > tags.index('issued')
        assert callback_index < tags.index('POLICY_STEP_COMPLETE')
        alignment_index=tags.index('r09b_application_cutoff_aligned')
        assert callback_index < alignment_index < tags.index('POLICY_STEP_COMPLETE')
    if timing == 'r09b_before_bind':
        assert len(before_issue_calls) == 1
        callback_index=tags.index('r09b_fixture_before_pending_bind')
        clear_zero_index=tags.index('r09b_clear_scan_zero_applied')
        assert tags.index('b1_begin_step') < callback_index < clear_zero_index < stream_off < bind
        assert ('stream', True) in history[:callback_index]
        witness = before_issue_calls[0][3]
        assert witness['receipt'].source == CommandEnvelope.SOURCE_SAFE_STOP
        assert witness['receipt'].final_publish_sequence == witness['state'].applied_final_publish_sequence
        assert bind < tags.index('arm') < tags.index('publish') < tags.index('issued')
        assert before_issue_calls[0][5] - before_issue_calls[0][4] >= 120_000_000
        assert callback_calls == []
    assert commit_calls[-1] >= expected_minimum
    if timing in ('late_commit', 'late_publish'):
        assert clock.ns >= bind_deadlines[0], (
            f'late completion must be rejected at the B1 transaction deadline: {history!r}')
    else:
        assert clock.ns < value.deadline_ns, (
            f'normal completion unexpectedly reached the campaign deadline: {history!r}')
    assert all(row[0] != 'align_policy_boundary' for row in history)
    assert ('stream', False) in history  # only pending-step freeze before bind
    assert not any(i > issued and row == ('stream', False) for i, row in enumerate(history))


def test_r02e_old_token_sample_is_built_after_close_before_new_bind():
    import asyncio
    import threading
    from builtin_interfaces.msg import Time
    from mecanum_nav_rl.runtime_simulation.b23_runner import TrainingWorkerIO
    from mecanum_nav_rl.runtime_simulation.local_training_ingress import LocalTrainingIngress
    from mecanum_nav_rl.simulation.simulated_odometry import SimulatedOdometryStatus
    from mecanum_nav_rl_interfaces.msg import LocalTrainingSafetyInput

    class BindReached(Exception):
        pass

    io, clock = worker()
    held_events = []
    previous_token = [0x31] * 16
    old_ack = NS(observed_steady_ns=clock.ns,
        request=NS(request_sequence=7),
        response=NS(pending_admission_token=previous_token,
            applied_sim_stamp=Time(sec=1)))
    sample = NS(
        output=NS(snapshot=NS(timestamp_ns=1_010_000_000,
            status=SimulatedOdometryStatus.VALID,
            measurement=NS(vx_mps=.01, vy_mps=0., wz_radps=0.))),
        received_steady_ns=1_010_000_000,
        lifecycle=NS(episode_generation=1, reset_epoch=2, runtime_generation=3))
    io.ros_now = clock.now
    io._hold_next_safety_input = False
    io._held_safety_input = None
    io._publish_safety_input = TrainingWorkerIO._publish_safety_input.__get__(io)
    io.emit = lambda name, facts: held_events.append((name, facts))
    io.ingress.lock = threading.RLock()
    io.ingress.noisy_samples = {1: sample}
    io.ingress.pending_ack = old_ack
    io.ingress.admission_state = LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN
    io.ingress.admission_publication_enabled = True
    io.ingress.lifecycle = NS(episode_generation=1, reset_epoch=2, runtime_generation=3)
    io.ingress.identity = NS(session_id='session-1', config_hash='a'*64,
        coordinator_ingress_instance_id=9)
    io.ingress.profile = {'odometry_max_age_ms':500}
    io.ingress.now = clock.now
    io.ingress.ros_now = clock.now
    io.ingress._sample_sequence = 30
    io.ingress.last_published_sample_sequence = 29
    io.ingress.last_published_admission_state = LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN
    io.ingress.observation0_ack = NS(request=NS(observation0_cutoff=Time(sec=1),
        selected_zero_final_publisher_instance_id=55,
        selected_zero_final_publish_sequence=11))
    io.ingress.publish = io._publish_safety_input
    io.ingress.emit = io.emit
    io.ingress._publish_safety = LocalTrainingIngress._publish_safety.__get__(io.ingress)

    async def freeze_closing_old_slot(*, deadline_ns):
        assert deadline_ns > io.now()
        held_events.append(('freeze_step_streams', {}))
        clock.ns = 1_020_000_000
        io.ingress.pending_ack = None
        io.ingress.admission_state = LocalTrainingSafetyInput.ADMISSION_INHIBITED
        io.ingress.admission_publication_enabled = False
        io.ingress.last_published_sample_sequence = 30
        io.ingress.last_published_admission_state = LocalTrainingSafetyInput.ADMISSION_INHIBITED

    io.freeze_step_streams = freeze_closing_old_slot
    io.safety = NS(local_training=NS(set_stream_enabled=lambda enabled:
        held_events.append(('stream',enabled))))

    class B1:
        def begin_step(self):
            held_events.append(('bind_step_begin',{}))
            raise BindReached

    with pytest.raises(BindReached):
        asyncio.run(io.policy_step(B1(), (0.2, 0.0, 0.0), prebind_admission=True))

    held = io._held_safety_input
    assert held is not None, f'production ingress did not build and hold a pre-bind input: {held_events!r}'
    tags = [name for name, _ in held_events]
    freeze_index = tags.index('freeze_step_streams')
    held_index = tags.index('R02E_PREBIND_SAFETY_INPUT_HELD')
    bind_index = tags.index('bind_step_begin')
    assert freeze_index < held_index < bind_index, f'held input must be built after close and before new bind: {held_events!r}'
    held_record = held_events[held_index][1]
    assert held_record['admission_token_hex'] == bytes(previous_token).hex()
    assert held.sample_sequence == 31 and held.sample_sequence > 30
    assert io.ingress.pending_ack is None
    assert io.ingress.admission_state == LocalTrainingSafetyInput.ADMISSION_INHIBITED
    assert ('stream',False) in held_events


def test_r09b_holds_policy_before_waiting_for_contact_and_restoring_fixture():
    from builtin_interfaces.msg import Time
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt

    order = []
    class FakeIO:
        descriptor = {'task_fixture': {'entity_name':'obstacle_0'},
            'backend_instance_id':22, 'session_id':'session-a', 'config_hash':'c'*64}
        def __init__(self):
            self.safety = NS(local_training=NS(set_policy_hold=lambda value:
                order.append(('policy_hold', value))))
            self.ingress = NS(backend_state=None)
        def now(self): return 1000
        def emit(self, event, facts): order.append((event, facts))
        async def set_r09b_task_fixture_pose(self, *, pose_name, **kwargs):
            order.append(('fixture_pose', pose_name))
        async def until(self, predicate, *, deadline_ns, phase):
            active = phase == 'R09b healthy fixture contact pulse'
            status = NS(backend_instance_id=22, session_id='session-a', config_hash='c'*64,
                coverage_complete=True, contact_source_healthy=True,
                required_collision_mask=3, observed_collision_mask=3, fault_flags=0,
                paused=False, status_sequence=11 if active else 12,
                physics_iteration=101 if active else 102, contact_active=active,
                header=NS(stamp=Time(sec=1, nanosec=101 if active else 102)))
            self.ingress.backend_state = status
            assert predicate() is not None
            order.append(('observation', phase))
            return status

    io = FakeIO()
    receipt = NS(final_publish_sequence=40,
        source=FinalIssuedCommandReceipt.SOURCE_SAFE_STOP)
    applied = NS(applied_final_publish_sequence=40, status_sequence=10,
        physics_iteration=100)
    result = asyncio.run(TrainingWorkerIO.run_r09b_contact_task_pulse(io,
        zero_receipt=receipt, zero_applied_state=applied,
        deadline_ns=5000, applied_received_ns=900))
    tags = [row[0] for row in order]
    pose_contact = order.index(('fixture_pose', 'contact_pose'))
    held = order.index(('policy_hold', True))
    contact_wait = order.index(('observation', 'R09b healthy fixture contact pulse'))
    pose_restore = order.index(('fixture_pose', 'initial_pose'))
    empty_wait = order.index(('observation', 'R09b fixture restored covered-empty before B1 cutoff'))
    assert pose_contact < held < contact_wait < pose_restore < empty_wait
    assert tags.count('policy_hold') == 1
    assert any(row[0] == 'R09B_ZERO_STREAM_HELD_DURING_CONTACT_FIXTURE_TASK' for row in order)
    assert result['contact']['physics_iteration'] == 101
    assert result['restored_empty']['physics_iteration'] == 102


def test_r09b_application_cutoff_keeps_zero_stream_active_and_uses_retained_pair():
    from builtin_interfaces.msg import Time
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
    from mecanum_nav_rl.core.issued_command_cutoff import (
        CutoffStatus, IssuedCommandReceiptView, PolicyActionIssuance,
        ReceiptSource, ReceiptStreamBinding, select_final_issued_at_cutoff,
    )
    from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity

    identity = EpisodeLifecycleIdentity(1, 1, 2)
    policy = IssuedCommandReceiptView(1_250_000_000, 90, 39,
        ReceiptSource.POLICY, 7, 1, 1, 'transition-1', identity,
        'session-a', 'c'*64, (0., 0., 0.), 100, 'base_link', True)
    applied_stop = IssuedCommandReceiptView(1_370_000_000, 90, 40,
        ReceiptSource.SAFE_STOP, 8, 1, 0, '', identity,
        'session-a', 'c'*64, (0., 0., 0.), 101, 'base_link', True)
    boundary = IssuedCommandReceiptView(1_400_000_000, 90, 41,
        ReceiptSource.SAFE_STOP, 8, 2, 0, '', identity,
        'session-a', 'c'*64, (0., 0., 0.), 103, 'base_link', True)
    policy_raw = FinalIssuedCommandReceipt()
    policy_raw.header.stamp = Time(sec=1, nanosec=250_000_000)
    policy_raw.final_publisher_instance_id = 90
    policy_raw.final_publish_sequence = 39
    policy_raw.source = FinalIssuedCommandReceipt.SOURCE_POLICY
    policy_raw.source_instance_id = 7
    policy_raw.sequence = 1
    policy_raw.step_index = 1
    policy_raw.transition_id = 'transition-1'
    status = NS(applied_receipt_valid=True, local_zero_override=False,
        fault_flags=0, episode_generation=1, reset_epoch=1, runtime_generation=2,
        applied_final_publisher_instance_id=90, applied_final_publish_sequence=40,
        applied_physics_iteration=128, physics_iteration=128,
        applied_sim_stamp=Time(sec=1, nanosec=380_000_000),
        header=NS(stamp=Time(sec=1, nanosec=380_000_000)), status_sequence=55)

    class FakeIO:
        def __init__(self):
            self.stream = []
            self.stream_enabled = True
            def set_stream_enabled(value):
                self.stream.append(value)
                self.stream_enabled = value
            self.safety = NS(local_training=NS(set_stream_enabled=set_stream_enabled))
            def application_for_receipt(receipt):
                self.application_requests.append(receipt.final_publish_sequence)
                if receipt.final_publish_sequence != applied_stop.final_publish_sequence:
                    return None
                return {'state':status, 'received_ns':190}
            self.ingress = NS(lock=threading.RLock(), receipts=[policy, applied_stop, boundary],
                _receipt_views={39:policy, 40:applied_stop, 41:boundary}, backend_state=status,
                scans={1_390_000_000:object()}, application_for_receipt=application_for_receipt)
            self.calls = []
            self.application_requests = []

        def now(self):
            return 200

        def check(self):
            return None

        def emit(self, event, facts):
            self.calls.append((event, facts))

        async def until(self, predicate, *, deadline_ns, phase):
            self.calls.append(('wait', phase))
            assert phase == 'R09b applied zero and adjacent SAFE_STOP around paired cutoff'
            value = predicate()
            assert value is not None, 'fake must provide exact application, adjacent receipt, and joined cutoff'
            return value

    class FakeB1:
        def __init__(self):
            self.joined = []

        def _joined(self, cutoff):
            self.joined.append(cutoff)
            return {'cutoff':cutoff}

    io, b1 = FakeIO(), FakeB1()
    cutoff = asyncio.run(TrainingWorkerIO.align_r09b_application_cutoff(io, b1,
        policy_receipt=policy_raw, minimum_cutoff_ns=1_350_000_000,
        deadline_ns=1_000))

    assert cutoff == 1_390_000_000
    assert b1.joined == [1_390_000_000]
    assert io.stream == [], 'alignment must not pause the watchdog-fed SAFE_STOP stream'
    assert io.stream_enabled is True
    assert io.application_requests == [40]
    assert io.calls[-1][0] == 'R09B_APPLICATION_CUTOFF_BOUNDARY_PINNED'
    pinned = io.calls[-1][1]
    assert pinned['selected_publish_sequence'] == 40
    assert pinned['selected_application_stamp_ns'] == 1_380_000_000
    assert pinned['cutoff_ns'] == cutoff
    assert pinned['adjacent_publish_sequence'] == 41
    selected = select_final_issued_at_cutoff(
        (policy, applied_stop, boundary),
        binding=ReceiptStreamBinding(90, 'session-a', 'c'*64, identity, 'base_link'),
        issuance=PolicyActionIssuance(7, 1, identity, 1, 'transition-1'),
        cutoff_ros_ns=cutoff, evaluation_ros_now_ns=boundary.publish_stamp_ns,
        evaluation_steady_now_ns=105, reset_barrier_ros_ns=0,
        action_barrier_ros_ns=1_200_000_000, physical_scales=(1., 1., 1.))
    assert selected.status is CutoffStatus.READY, selected
    assert selected.receipt == applied_stop
    assert selected.adjacent_receipt == boundary
    assert applied_stop.publish_stamp_ns < cutoff < boundary.publish_stamp_ns


def test_evidence_sink_routes_actual_server_output_and_keeps_books_distinct(tmp_path):
    from mecanum_nav_rl.runtime_simulation.b23_runner import RunEvidence
    sink = RunEvidence(tmp_path, 'parent', run_id='run', invocation_id='inv-1')
    facts = dict(process='server', pid=777, command=['gz', 'sim'], stream='stdout',
        text='[Msg] B23_ADMISSION_ACCEPTED session=run backend=22 ingress=11 sample=9')
    sink.record('owned_process_output', facts)
    sink.record('policy_backend_applied', {'step_index': 1})
    sink.close()
    raw = (tmp_path/'native-events.jsonl').read_bytes().splitlines()
    assert len(raw) == 1
    record = json.loads(raw[0])
    assert record['server_leader_pid'] == 777 and record['invocation_id'] == 'inv-1'
    assert record['fields']['sample'] == '9' and record['raw_record']['facts'] == facts
    assert len((tmp_path/'policy_backend_applied.jsonl').read_bytes().splitlines()) == 1
    assert not (tmp_path/'policy_adapter_issued.jsonl').exists()
    with pytest.raises(RuntimeError, match='already closed'):
        sink.record('late', {})


def test_cleanup_ack_is_bound_to_exact_batch_after_flush(tmp_path, monkeypatch):
    from mecanum_nav_rl.runtime_simulation import b23_runner as module
    from mecanum_nav_bringup.local_training_process_supervisor import CleanupEvidenceBatch
    clock = NS(ns=1_000_000_000)
    monkeypatch.setattr(module.time, 'monotonic', lambda: clock.ns/1e9)
    monkeypatch.setattr(module.time, 'monotonic_ns', lambda: clock.ns)
    sink = module.RunEvidence(tmp_path, 'parent', run_id='run', invocation_id='inv-1')
    sink.record('application', {'key': [55, 2]})
    batch = CleanupEvidenceBatch('batch-1', ())
    ack = asyncio.run(sink.cleanup_publisher(batch, 2.))
    assert ack.batch_id == 'batch-1' and ack.acknowledged
    assert json.loads((tmp_path/'cleanup-ack.json').read_bytes())['batch_id'] == 'batch-1'
    sink.close()
    second = tmp_path/'late'; second.mkdir()
    sink = module.RunEvidence(second, 'parent', run_id='run', invocation_id='inv-1')
    def late_sync(): clock.ns = 3_000_000_000
    monkeypatch.setattr(sink, 'sync', late_sync)
    with pytest.raises(TimeoutError, match='after deadline'):
        asyncio.run(sink.cleanup_publisher(batch, 2.))
    assert (second/'cleanup-batch.json').exists() and not (second/'cleanup-ack.json').exists()


def test_immutable_record_refuses_to_overwrite_consumed_evidence(tmp_path):
    from mecanum_nav_rl.runtime_simulation.b23_runner import write_record_once
    import hashlib
    path = tmp_path/'record.json'
    expected = write_record_once(path, {'run_id': 'run'})
    raw = path.read_bytes()
    assert raw.endswith(b'\n') and expected == hashlib.sha256(raw).hexdigest()
    with pytest.raises(FileExistsError): write_record_once(path, {'run_id': 'other'})
    assert path.read_bytes() == raw


def test_proc_identity_argv_and_start_ticks_are_derived_from_saved_bytes(monkeypatch):
    from mecanum_nav_rl.runtime_simulation import b23_runner as module
    from pathlib import Path
    fields = {3:'S', 4:'55', 5:'77', 6:'77', 22:'12345'}
    stat = b'77 (worker (owned)) ' + ' '.join(fields.get(i, '0') for i in range(3, 24)).encode()
    raw = {'stat': stat,
        'status': b'Name:\tworker\nUid:\t1000\t1000\t1000\t1000\n',
        'cmdline': b'/pinned/python\0-B\0-m\0b23_runner\0',
        'cgroup': b'0::/user.slice/user-1000.slice/user@1000.service/app.slice/b23-test.service\n'}
    monkeypatch.setattr(Path, 'read_bytes', lambda path: raw[path.name])
    result = module.process_identity(77)
    assert result['argv'] == ['/pinned/python','-B','-m','b23_runner']
    assert result['start_ticks'] == 12345 and result['uid'] == 1000
    assert result['raw_hex'] == {name:value.hex() for name,value in raw.items()}
    assert (result['ppid'], result['pgid'], result['sid']) == (55,77,77)


def test_cgroup_scan_read_error_and_incomplete_walk_are_never_empty(monkeypatch):
    from mecanum_nav_rl.runtime_simulation import b23_runner as module
    from pathlib import Path
    import os
    path = '/user.slice/user-1000.slice/user@1000.service/app.slice/b23-test.service'
    monkeypatch.setattr(Path, 'stat', lambda p, *a, **k: object())
    monkeypatch.setattr(os, 'walk', lambda p, **kwargs: iter([(str(p), [], ['cgroup.procs'])]))
    def denied(path): raise PermissionError('test denied cgroup.procs')
    monkeypatch.setattr(Path, 'read_bytes', denied)
    result = module.scan_pinned_cgroup(path)
    assert result['status'] == 'incomplete' and result['errors'] and not result['files']
    monkeypatch.setattr(os, 'walk', lambda p, **kwargs: iter([]))
    result = module.scan_pinned_cgroup(path)
    assert result['status'] == 'incomplete'
    def missing(path, *a, **k): raise FileNotFoundError('exact pinned path removed')
    monkeypatch.setattr(Path, 'stat', missing)
    result = module.scan_pinned_cgroup(path)
    assert result['status'] == 'path_removed_confirmed' and not result['errors']
    with pytest.raises(ValueError, match='unverified'):
        module.scan_pinned_cgroup('/')


def test_cgroup_walk_error_is_preserved_even_if_one_procs_file_is_empty(monkeypatch):
    from mecanum_nav_rl.runtime_simulation import b23_runner as module
    from pathlib import Path
    import os
    monkeypatch.setattr(Path, 'stat', lambda *a, **k: object())
    monkeypatch.setattr(Path, 'read_bytes', lambda p: b'')
    def walk(path, **kwargs):
        kwargs['onerror'](OSError('child cgroup unreadable'))
        yield str(path), [], ['cgroup.procs']
    monkeypatch.setattr(os, 'walk', walk)
    result = module.scan_pinned_cgroup('/user.slice/user-1000.slice/user@1000.service/b23-test.service')
    assert result['status'] == 'incomplete' and result['files'] and result['errors']


def test_command_adapter_preserves_timeout_bytes_and_exit(monkeypatch):
    from mecanum_nav_rl.runtime_simulation import b23_runner as module
    import subprocess
    calls = []
    def execute(argv, **kwargs):
        calls.append((argv,kwargs)); raise subprocess.TimeoutExpired(argv, kwargs['timeout'], b'raw output', b'bus denied')
    monkeypatch.setattr(subprocess, 'run', execute)
    result = module.command_record(['systemctl','--user','show'], timeout_s=.5)
    assert result['error'] == 'timeout' and result['returncode'] is None
    assert bytes.fromhex(result['stderr_hex']) == b'bus denied' and result['stdout'] == 'raw output'
    assert calls[0][1]['timeout'] == .5
    assert module.command_record(['systemctl'], timeout_s=0)['error'] == 'no_remaining_budget'
    assert len(calls) == 1


def test_main_invalid_case_and_child_without_guard_never_start_ros(tmp_path, monkeypatch):
    from mecanum_nav_rl.runtime_simulation import b23_runner as module
    with pytest.raises(SystemExit) as error:
        module.main(['invalid-case'])
    assert error.value.code == 2
    path = tmp_path/'descriptor.json'
    path.write_text(json.dumps({'schema':'b23_owned_child/v1','role':'worker','invocation_id':'inv-1'}))
    monkeypatch.delenv('INVOCATION_ID', raising=False)
    with pytest.raises(RuntimeError, match='authority/profile/parent'):
        module.load_child_descriptor(path, 'worker')


def test_launch_plan_serialization_preserves_frozen_environment_and_exact_argv(tmp_path):
    from mecanum_nav_rl.runtime_simulation.b23_runner import launch_plan_record
    from mecanum_nav_bringup.local_training_launch_contract import LaunchPlan
    plan = LaunchPlan(False,tmp_path/'world',tmp_path/'gui',tmp_path/'config', 'run', 'a'*64,'b'*64,11,
        (('gz','sim','--headless-rendering',str(tmp_path/'world')),), {'GZ_PARTITION':'private'},
        ('ros2','run','ros_gz_bridge','parameter_bridge'))
    raw = json.dumps(launch_plan_record(plan)).encode()
    saved = json.loads(raw)
    assert saved['commands'] == [list(plan.commands[0])]
    assert saved['environment'] == {'GZ_PARTITION':'private'}
    saved['environment']['GZ_PARTITION'] = 'changed'
    assert plan.environment['GZ_PARTITION'] == 'private'


def test_pending_cleanup_batch_is_preserved_in_failure_summary(tmp_path):
    from mecanum_nav_rl.runtime_simulation.b23_runner import write_record_once
    from mecanum_nav_bringup.local_training_process_supervisor import CleanupEvidenceBatch
    pending = CleanupEvidenceBatch('batch-not-acked', (('group_residue', (('pid',77),)),))
    path = tmp_path/'failed-summary.json'
    write_record_once(path, {'primary_error':'worker failed', 'pending_batch':pending})
    result = json.loads(path.read_bytes())
    assert result['primary_error'] == 'worker failed'
    assert result['pending_batch']['batch_id'] == 'batch-not-acked'
    assert result['pending_batch']['events'][0][0] == 'group_residue'


def test_actual_unit_properties_are_checked_exactly_without_duration_rounding():
    from mecanum_nav_rl.runtime_simulation.b23_runner import verify_unit_configuration
    properties = dict(Type='exec',Restart='no',KillMode='control-group',RemainAfterExit='yes',
        RuntimeMaxUSec='3min',RuntimeRandomizedExtraUSec='0',TimeoutStartUSec='5s',TimeoutStopUSec='2s',
        MemoryMax='5368709120',OOMPolicy='stop',
        SendSIGKILL='yes',KillSignal='15',FinalKillSignal='9')
    verify_unit_configuration(properties)
    for key,bad in [('RuntimeMaxUSec','3min 500ms'),('RuntimeRandomizedExtraUSec','500ms'),
            ('KillSignal','9'),('KillMode','process'),('TimeoutStopUSec','2.5s')]:
        with pytest.raises(ValueError, match=key): verify_unit_configuration(dict(properties, **{key:bad}))
    properties.pop('RemainAfterExit')
    with pytest.raises(ValueError, match='RemainAfterExit'): verify_unit_configuration(properties)
    soak=dict(Type='exec',Restart='no',KillMode='control-group',RemainAfterExit='yes',
        RuntimeMaxUSec='16min',RuntimeRandomizedExtraUSec='0',TimeoutStartUSec='5s',TimeoutStopUSec='2s',
        MemoryMax='5368709120',OOMPolicy='stop',SendSIGKILL='yes',KillSignal='15',FinalKillSignal='9')
    verify_unit_configuration(soak,active_s=900,cleanup_s=60)
    with pytest.raises(ValueError,match='RuntimeMaxUSec'):
        verify_unit_configuration(dict(soak,RuntimeMaxUSec='16min 1ms'),active_s=900,cleanup_s=60)


def test_terminal_evidence_is_joined_to_actual_main_pid_invocation_and_argv(tmp_path):
    from mecanum_nav_rl.runtime_simulation.b23_runner import terminal_binding_errors, MODULE
    packet = dict(run_id='B23_R01A_TEST',unit='b23-r01a-test.service',python='/pinned/python',run_root=str(tmp_path))
    sha = 'a'*64
    identity = dict(pid=77,start_ticks=12345,uid=1000,argv=[packet['python'],'-B','-m',MODULE,
        'parent','--packet',str(tmp_path/'packet.json'),'--packet-sha256',sha])
    parent = dict(identity=identity,run_id=packet['run_id'],invocation_id='inv-1',packet_sha256=sha)
    terminal = dict(InvocationID='inv-1',Id=packet['unit'],ExecMainPID='77')
    observed = {(77,12345):dict(identity)}
    assert terminal_binding_errors(packet,terminal,parent,observed,'inv-1',sha) == []
    assert terminal_binding_errors(packet,dict(terminal,ExecMainPID='78'),parent,observed,'inv-1',sha)
    assert terminal_binding_errors(packet,terminal,parent,observed,'inv-2',sha)
    assert terminal_binding_errors(packet,terminal,parent,{},'inv-1',sha)
    observed[(77,12345)]['argv'] = ['bash','unrelated']
    assert terminal_binding_errors(packet,terminal,parent,observed,'inv-1',sha)


def test_cleanup_budget_is_not_renewed_when_parent_follows_worker():
    from mecanum_nav_rl.runtime_simulation.b23_runner import cleanup_window_deadline
    marker = dict(run_id='run',invocation_id='inv-1',started_ns=2_000_000_000,deadline_ns=62_000_000_000)
    assert cleanup_window_deadline(marker,run_id='run',invocation='inv-1',total_end=180_000_000_000,
        now_ns=61_000_000_000) == 62_000_000_000
    for invalid in (dict(marker,deadline_ns=122_000_000_000),dict(marker,invocation_id='inv-2')):
        with pytest.raises(ValueError, match='identity/budget'):
            cleanup_window_deadline(invalid,run_id='run',invocation='inv-1',total_end=180_000_000_000,now_ns=61_000_000_000)


def test_unit_wrapper_preserves_real_invocation_and_literal_environment_without_leak():
    from mecanum_nav_rl.runtime_simulation.b23_runner import unit_parent_command
    import subprocess
    command = unit_parent_command({'environment':{'B23_LITERAL':'literal $HOME; $(echo not-executed)\nnext'},
        'python':'/pinned/python'}, '/packet.json', 'a'*64)
    # Thay argv program sau biên env bằng shell in hai biến; không systemd,
    # ROS hoặc helper probe. Cùng wrapper/argv literal production.
    index = command.index('/pinned/python')
    actual = command[:index]+['/bin/bash','-c','printf "%s\\n" "$INVOCATION_ID" "$B23_LITERAL" "${UNRELATED_SECRET-unset}"']
    result = subprocess.run(actual, env={'INVOCATION_ID':'inv-from-systemd','UNRELATED_SECRET':'must-not-leak'},
        capture_output=True,text=True,timeout=2)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'inv-from-systemd\nliteral $HOME; $(echo not-executed)\nnext\nunset\n'
    missing = subprocess.run(actual,env={},capture_output=True,text=True,timeout=2)
    assert missing.returncode != 0 and 'INVOCATION_ID' in missing.stderr
    assert command[index:] == ['/pinned/python','-B','-m',
        'mecanum_nav_rl.runtime_simulation.b23_runner','parent','--packet','/packet.json','--packet-sha256','a'*64]


def test_launch_template_pins_properties_env_and_only_substitutes_self_hash():
    from mecanum_nav_rl.runtime_simulation.b23_runner import service_launch_command, service_properties_for
    packet = dict(unit='b23-test.service',environment={'ROS_DOMAIN_ID':'84'},python='/pinned/python')
    template = service_launch_command(packet,'/packet.json','{PACKET_SHA256}')
    actual = service_launch_command(packet,'/packet.json','a'*64)
    assert actual == [value.replace('{PACKET_SHA256}','a'*64) for value in template]
    assert actual[:3] == ['systemd-run','--user','--unit=b23-test.service']
    assert '--scope' not in actual and '--collect' not in actual
    assert '--expand-environment=no' in actual
    assert set(value for value in actual if value.startswith('--property=')) == {'--property='+v for v in service_properties_for(120)}
    assert '--property=KillMode=control-group' in actual and '--property=RuntimeMaxSec=180s' in actual


def test_headless_smoke_seed_is_in_real_gazebo_server_argv(tmp_path):
    from mecanum_nav_rl.runtime_simulation.b23_runner import b23_server_argv
    command = b23_server_argv(tmp_path/'bound-world.sdf')
    assert command[:2] == ('gz','sim') and command[-1] == str(tmp_path/'bound-world.sdf')
    assert command[command.index('--seed')+1] == '20261029' and command.count('--seed') == 1
    assert command[command.index('--force-version')+1] == '8'
    assert '-s' in command and '--headless-rendering' in command and '-r' not in command


def test_worker_publishes_envelope_on_architecture_canonical_policy_topic():
    import ast
    from pathlib import Path
    from mecanum_nav_rl.runtime_simulation import b23_runner as module
    from mecanum_nav_rl_interfaces.msg import CommandEnvelope
    tree = ast.parse(Path(module.__file__).read_bytes())
    worker = next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name == 'TrainingWorkerIO')
    constructor = next(node for node in worker.body if isinstance(node,ast.FunctionDef) and node.name == '__init__')
    assignment = next(node for node in ast.walk(constructor) if isinstance(node,ast.Assign)
        and any(isinstance(target,ast.Attribute) and target.attr == 'policy_publisher' for target in node.targets))
    calls = []
    node = NS(node=NS(create_publisher=lambda *args:calls.append(args)))
    qos = object()
    statement = ast.fix_missing_locations(ast.Module(body=[assignment],type_ignores=[]))
    exec(compile(statement,module.__file__,'exec'), {'self':node,'CommandEnvelope':CommandEnvelope,'reliable':qos})
    assert calls == [(CommandEnvelope,'/mecanum/cmd_policy',qos)]


def test_packet_argv_is_stable_across_canonical_json_roundtrip():
    from mecanum_nav_rl.runtime_simulation.b23_runner import service_launch_command
    packet = dict(unit='b23-test.service',python='/pinned/python',
        environment={'Z_LAST':'literal value','A_FIRST':'other'})
    before = service_launch_command(packet,'/packet.json','{PACKET_SHA256}')
    restored = json.loads(json.dumps(packet,sort_keys=True,separators=(',',':')))
    after = service_launch_command(restored,'/packet.json','{PACKET_SHA256}')
    assert before == after


def test_prepared_session_identity_satisfies_real_readiness_contract():
    import ast,uuid
    from pathlib import Path
    from mecanum_nav_rl.runtime_simulation import b23_runner as module
    from mecanum_nav_bringup.local_training_process_supervisor import RclpyReadiness
    tree=ast.parse(Path(module.__file__).read_bytes())
    producer=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='prepare_packet')
    call=next(node for node in ast.walk(producer) if isinstance(node,ast.Call)
        and isinstance(node.func,ast.Name) and node.func.id=='build_launch_plan')
    namespace={'args':NS(run_id='B23_R01A_TEST'),'uuid':uuid,'str':str}
    for node in producer.body:
        if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='session_id' for target in node.targets):
            exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),module.__file__,'exec'),namespace)
    expression=next(keyword.value for keyword in call.keywords if keyword.arg=='session_id')
    session=eval(compile(ast.fix_missing_locations(ast.Expression(expression)),module.__file__,'eval'),namespace)
    plan=NS(session_id=session,coordinator_ingress_instance_id=11,config_hash='a'*64,
        asset_manifest_sha256='b'*64,environment={'ROS_DOMAIN_ID':'84','GZ_PARTITION':'private'})
    request=RclpyReadiness()._make_request(plan,'a'*64,1_000_000_000)
    assert request['session_id']==session and session != namespace['args'].run_id
    assert str(uuid.UUID(session))==session


def test_failed_state_clear_only_targets_the_bound_completed_invocation(monkeypatch):
    from mecanum_nav_rl.runtime_simulation import b23_runner as module
    import subprocess
    calls,events=[],[]
    props=dict(Id='b23-test.service',InvocationID='inv-1',ExecMainPID='77',MainPID='0',
        ActiveState='failed',ControlGroup='',ExecStart='pinned argv --packet-sha256 '+'a'*64)
    def execute(argv,**kwargs):
        calls.append(argv)
        return NS(returncode=0,stdout=('\n'.join(k+'='+v for k,v in props.items())+'\n').encode()
            if 'show' in argv else b'',stderr=b'')
    monkeypatch.setattr(subprocess,'run',execute)
    module.clear_owned_failed_state('b23-test.service','inv-1','77','a'*64,deadline_ns=2_000_000_000,
        now_ns=lambda:1_000_000_000,emit=lambda n,r:events.append((n,r)))
    assert calls[-1]==['systemctl','--user','reset-failed','b23-test.service']
    for key,bad in [('InvocationID','inv-2'),('ExecMainPID','88'),('MainPID','88'),('ControlGroup','/foreign')]:
        original=props[key];props[key]=bad;calls.clear()
        with pytest.raises(RuntimeError,match='ownership changed'):
            module.clear_owned_failed_state('b23-test.service','inv-1','77','a'*64,deadline_ns=2_000_000_000,
                now_ns=lambda:1_000_000_000,emit=lambda n,r:events.append((n,r)))
        assert not any('reset-failed' in a for a in calls)
        props[key]=original
    calls.clear()
    with pytest.raises(TimeoutError):
        module.clear_owned_failed_state('b23-test.service','inv-1','77','a'*64,deadline_ns=1_000_000_000,
            now_ns=lambda:1_000_000_000,emit=lambda n,r:None)
    assert not calls


def test_packet_environment_keeps_gazebo_vendor_discovery_and_install_ament_prefix(tmp_path):
    import ast
    import os
    from pathlib import Path
    from mecanum_nav_rl.runtime_simulation import b23_runner as module
    tree=ast.parse(Path(module.__file__).read_bytes())
    producer=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='prepare_packet')
    statements=[node for node in producer.body if isinstance(node,ast.Assign) and
        any(isinstance(target,ast.Name) and target.id in ('environment_keys','environment') for target in node.targets)]
    install=tmp_path/'install'; install.mkdir()
    namespace={'os':NS(environ={'GZ_CONFIG_PATH':'/vendor/sim/share/gz:/vendor/transport/share/gz',
        'PATH':'/vendor/bin','AMENT_PREFIX_PATH':'/opt/ros/jazzy','UNLISTED_SECRET':'must-not-leak'}),
        'Path':Path, 'prefix':install, 'bind_install_ament_prefix':module.bind_install_ament_prefix}
    exec(compile(ast.fix_missing_locations(ast.Module(body=statements,type_ignores=[])),module.__file__,'exec'),namespace)
    environment=namespace['environment']
    assert environment.get('GZ_CONFIG_PATH')==namespace['os'].environ['GZ_CONFIG_PATH'], environment
    assert environment['PATH']=='/vendor/bin' and 'UNLISTED_SECRET' not in environment
    assert environment['AMENT_PREFIX_PATH'].split(os.pathsep)==[str(install.resolve()),'/opt/ros/jazzy']


def test_graph_failure_preserves_observed_endpoint_identity_without_binding():
    value,clock=worker();events=[];bound=[]
    def endpoint(name):return NS(node_name=name,node_namespace='/',topic_type='actual/type',endpoint_gid=bytes(range(16)))
    groups={'/cmd_vel':[endpoint('unexpected')],'/mecanum/safety_state':[endpoint('safety_supervisor')],
        '/mecanum/local_training/safety_input':[endpoint('b23_coordinator_ingress')],
        '/mecanum/local_training/backend_state':[]}
    value.node.get_publishers_info_by_topic=lambda topic:groups[topic]
    value.emit=lambda event,facts:events.append((event,facts))
    value.ingress.bind_safety_publisher_gid=lambda gid:bound.append(gid)
    with pytest.raises(RuntimeError,match='unexpected graph publisher ownership'):
        asyncio.run(value.pin_graph(deadline_ns=clock.ns+10_000_000))
    assert not bound and [event for event,_ in events]==['GRAPH_OBSERVATION']
    assert events[0][1]['cmd_vel'][0]==dict(node='unexpected',namespace='/',type='actual/type',
        gid_hex=bytes(range(16)).hex(),qos={'qos_available':False})


def test_ros_endpoint_qos_evidence_keeps_observed_profile_values():
    endpoint = NS(qos_profile=NS(history=1, depth=50, reliability=2, durability=2,
        liveliness=1, deadline=NS(nanoseconds=0), lifespan=NS(nanoseconds=0),
        liveliness_lease_duration=NS(nanoseconds=0)))
    assert runner_module.ros_endpoint_qos_evidence(endpoint) == {
        'qos_available':True, 'history':1, 'depth':50, 'reliability':2,
        'durability':2, 'liveliness':1, 'deadline_ns':0, 'lifespan_ns':0,
        'liveliness_lease_duration_ns':0}
    assert runner_module.ros_endpoint_qos_evidence(NS()) == {'qos_available':False}
    assert runner_module.ros_message_lost_evidence('/backend',
        NS(total_count=5, total_count_change=3), 123456) == {
            'topic':'/backend','total_count':5,'total_count_change':3,
            'received_steady_ns':123456}
    service_event = NS(info=NS(event_type=3, sequence_number=42,
        client_gid=bytes(range(16)), stamp=NS(sec=17, nanosec=29)))
    assert runner_module.ros_service_event_evidence(service_event, 987654) == {
        'service_event_type':3, 'service_event_name':'RESPONSE_RECEIVED',
        'sequence_number':42, 'client_gid_hex':bytes(range(16)).hex(),
        'stamp_sec':17, 'stamp_nanosec':29, 'received_steady_ns':987654}


def test_graph_undiscovered_ros_node_waits_without_binding_or_extending_deadline():
    value,clock=worker();events=[];bound=[]
    def endpoint(name):return NS(node_name=name,node_namespace='/',topic_type='actual/type',endpoint_gid=bytes(range(16)))
    cmd=endpoint('_NODE_NAME_UNKNOWN_');cmd.node_namespace='_NODE_NAMESPACE_UNKNOWN_'
    groups={'/cmd_vel':[cmd],'/mecanum/safety_state':[endpoint('safety_supervisor')],
        '/mecanum/local_training/safety_input':[endpoint('b23_coordinator_ingress')],
        '/mecanum/local_training/backend_state':[]}
    value.node.get_publishers_info_by_topic=lambda topic:groups[topic]
    value.emit=lambda event,facts:events.append((event,facts))
    value.ingress.bind_safety_publisher_gid=lambda gid:bound.append(gid)
    async def pause(seconds):
        assert not bound
        await clock.pause(seconds)
        cmd.node_name='final_twist_publisher';cmd.node_namespace='/'
    value.pause=pause
    asyncio.run(value.pin_graph(deadline_ns=clock.ns+5_000_000))
    assert bound==[bytes(range(16))] and clock.ns==1_002_000_000
    assert [name for name,_ in events]==['GRAPH_OBSERVATION','GRAPH_OBSERVATION','GRAPH_BOUND']
    cmd.node_name='_NODE_NAME_UNKNOWN_';cmd.node_namespace='_NODE_NAMESPACE_UNKNOWN_'
    bound.clear();value.pause=clock.pause
    deadline=clock.ns+5_000_000
    with pytest.raises(TimeoutError,match='source graph binding'):
        asyncio.run(value.pin_graph(deadline_ns=deadline))
    assert not bound and clock.ns==deadline


def test_graph_binding_waits_for_world_control_service_within_same_startup_deadline():
    value, clock = worker()
    events, bound, polls = [], [], []
    def endpoint(name):
        return NS(node_name=name, node_namespace='/', topic_type='actual/type',
            endpoint_gid=bytes(range(16)))
    groups = {
        '/cmd_vel':[endpoint('final_twist_publisher')],
        '/mecanum/safety_state':[endpoint('safety_supervisor')],
        '/mecanum/local_training/safety_input':[endpoint('b23_coordinator_ingress')],
        '/mecanum/local_training/backend_state':[],
    }
    value.node.get_publishers_info_by_topic = lambda topic: groups[topic]
    value.emit = lambda event, facts: events.append((event, facts))
    value.ingress.bind_safety_publisher_gid = lambda gid: bound.append(gid)
    ready = {'value':False}
    value.world_client.service_is_ready = lambda: polls.append(clock.ns) or ready['value']
    async def pause(seconds):
        await clock.pause(seconds)
        if len(polls) == 2:
            ready['value'] = True
    value.pause = pause

    asyncio.run(value.pin_graph(deadline_ns=clock.ns + 5_000_000))

    assert len(polls) == 3, polls
    assert bound == [bytes(range(16))]
    observations = [facts for event, facts in events if event == 'GRAPH_OBSERVATION']
    assert [row['world_control_service_ready'] for row in observations] == [False, False, True]
    assert events[-1][0] == 'GRAPH_BOUND'


def test_graph_service_not_ready_at_deadline_does_not_bind_publishers():
    value, clock = worker()
    bound = []
    def endpoint(name):
        return NS(node_name=name, node_namespace='/', topic_type='actual/type',
            endpoint_gid=bytes(range(16)))
    groups = {
        '/cmd_vel':[endpoint('final_twist_publisher')],
        '/mecanum/safety_state':[endpoint('safety_supervisor')],
        '/mecanum/local_training/safety_input':[endpoint('b23_coordinator_ingress')],
        '/mecanum/local_training/backend_state':[],
    }
    value.node.get_publishers_info_by_topic = lambda topic: groups[topic]
    value.ingress.bind_safety_publisher_gid = lambda gid: bound.append(gid)
    value.world_client.service_is_ready = lambda: False
    deadline = clock.ns + 5_000_000
    with pytest.raises(TimeoutError, match='source graph binding'):
        asyncio.run(value.pin_graph(deadline_ns=deadline))
    assert not bound
    assert clock.ns == deadline


def test_subscription_keeps_actual_wire_before_decode_and_callback_failure():
    from nav_msgs.msg import Odometry
    from rclpy.serialization import serialize_message
    import hashlib
    value,clock=worker();events=[];seen=[]
    value.emit=lambda event,facts:events.append((event,facts))
    original=Odometry();original.header.frame_id='world';original.pose.pose.orientation.w=1.
    wire=serialize_message(original);info={'source_timestamp':123,'received_timestamp':456}
    def consumer(msg):
        seen.append(msg)
        assert events[-1][0]=='INGRESS_WIRE_RECEIVED'
        assert events[-1][1]['wire_cdr_hex']==wire.hex()
        return 'actual-result'
    receive=value.observed_callback(Odometry,'/actual/oracle',consumer)
    assert receive(wire,info)=='actual-result' and seen==[original]
    assert events[0][1]['message_info']==info
    def reject(msg):raise ValueError('actual rejected sample')
    receive=value.observed_callback(Odometry,'/actual/oracle',reject)
    with pytest.raises(ValueError,match='actual rejected sample'):receive(wire,info)
    assert [x[0] for x in events][-2:]==['INGRESS_WIRE_RECEIVED','INGRESS_CALLBACK_ERROR']
    assert events[-1][1]['wire_sha256']==hashlib.sha256(wire).hexdigest()


def test_future_receipt_waits_for_owned_ros_clock_and_keeps_original_receive_age():
    from collections import deque
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
    from rclpy.serialization import serialize_message

    value, clock = worker()
    value._pending_future_receipts = deque()
    value._receipt_max_age_ns = 500_000_000
    ros_now = [1_000_000_000]
    value.ros_now = lambda: ros_now[0]
    events, delivered = [], []
    value.emit = lambda name, facts: events.append((name, facts))

    message = FinalIssuedCommandReceipt()
    message.header.frame_id = 'base_link'
    message.header.stamp.sec, message.header.stamp.nanosec = 1, 10_000_000
    message.final_publish_sequence = 7
    wire = serialize_message(message)
    received_ns = clock.ns
    def consume(receipt, *, received_ns):
        delivered.append((receipt.final_publish_sequence, received_ns))
        return 'accepted'

    receive = value.observed_callback(FinalIssuedCommandReceipt,
        '/mecanum/final_issued_command', consume)
    assert receive(wire, {}) is None
    assert delivered == [] and len(value._pending_future_receipts) == 1
    assert events[-1][0] == 'RECEIPT_CLOCK_CATCHUP_DEFERRED'
    assert events[-1][1]['received_steady_ns'] == received_ns

    ros_now[0] = 1_010_000_000
    value._deliver_future_receipts_after_clock()
    assert delivered == [(7, received_ns)]
    assert not value._pending_future_receipts


def test_receipt_after_future_receipt_stays_behind_it_until_fifo_drain():
    """A caught-up newer receipt cannot overtake an older clock-deferred one."""
    from collections import deque
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
    from rclpy.serialization import serialize_message

    value, clock = worker()
    value._pending_future_receipts = deque()
    value._receipt_max_age_ns = 500_000_000
    value.fault_hooks = ()
    ros_now = [1_000_000_000]
    value.ros_now = lambda: ros_now[0]
    events, delivered = [], []
    value.emit = lambda name, facts: events.append((name, facts))

    def receipt(sequence, stamp_ns):
        message = FinalIssuedCommandReceipt()
        message.header.frame_id = 'base_link'
        message.header.stamp.sec, message.header.stamp.nanosec = divmod(stamp_ns, 1_000_000_000)
        message.final_publish_sequence = sequence
        return message

    def consume(message, *, received_ns):
        delivered.append((message.final_publish_sequence, received_ns))
        return message.final_publish_sequence

    receive = value.observed_callback(FinalIssuedCommandReceipt,
        '/mecanum/final_issued_command', consume)
    first = receipt(29, 1_010_000_000)
    first_received_ns = clock.ns
    assert receive(serialize_message(first), {}) is None
    assert delivered == [] and len(value._pending_future_receipts) == 1

    # The source clock catches up past receipt 30 before the pump drains 29.
    ros_now[0] = 1_020_000_000
    second = receipt(30, 1_020_000_000)
    second_received_ns = clock.ns
    assert receive(serialize_message(second), {}) is None
    assert delivered == [] and len(value._pending_future_receipts) == 2
    assert events[-1][0] == 'RECEIPT_CLOCK_CATCHUP_DEFERRED'
    assert events[-1][1]['reason'] == 'behind_prior_future_receipt'

    value._deliver_future_receipts_after_clock()
    assert delivered == [(29, first_received_ns), (30, second_received_ns)]
    assert not value._pending_future_receipts


def test_future_receipt_deferral_expires_at_original_freshness_budget():
    from collections import deque
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
    from rclpy.serialization import serialize_message

    value, clock = worker()
    value._pending_future_receipts = deque()
    value._receipt_max_age_ns = 500_000_000
    value.ros_now = lambda: 1_000_000_000
    events = []
    value.emit = lambda name, facts: events.append((name, facts))
    message = FinalIssuedCommandReceipt()
    message.header.frame_id = 'base_link'
    message.header.stamp.sec, message.header.stamp.nanosec = 1, 10_000_000
    message.final_publish_sequence = 7
    receive = value.observed_callback(FinalIssuedCommandReceipt,
        '/mecanum/final_issued_command', lambda _msg, **_kwargs: pytest.fail('future receipt dispatched'))
    assert receive(serialize_message(message), {}) is None
    clock.ns += 500_000_001
    with pytest.raises(TimeoutError, match='original B1 receipt freshness age'):
        value._deliver_future_receipts_after_clock()
    assert events[-1][0] == 'RECEIPT_CLOCK_CATCHUP_EXPIRED'


def test_r06c_withholds_receipt_only_from_b1_after_real_ingress_callback():
    from collections import deque
    from threading import Lock
    from rclpy.serialization import serialize_message
    from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt

    value, _clock = worker()
    events=[]
    value.emit=lambda event,facts:events.append((event,facts))
    value.fault_hooks={'hold_observation0_adjacent_receipt_until_reset_deadline'}
    value._r06c_hold_after_sequence=25
    value._r06c_reset_deadline_ns=15_000_000_000
    value._r06c_held_receipts=[]
    value.ros_now=lambda:1_000_000_000
    receipts=deque()
    receipt_views={}
    value.ingress=NS(lock=Lock(),receipts=receipts,_receipt_views=receipt_views)
    delivered=[]
    def production_receipt_consumer(message, *, received_ns):
        view=NS(final_publish_sequence=message.final_publish_sequence)
        with value.ingress.lock:
            receipts.append(view)
            receipt_views[view.final_publish_sequence]=view
        delivered.append(message.final_publish_sequence)
        return view

    message=FinalIssuedCommandReceipt()
    message.header.frame_id='base_link'
    message.header.stamp.sec=1
    message.source=message.SOURCE_SAFE_STOP
    message.final_publisher_instance_id=9
    message.final_publish_sequence=26
    wire=serialize_message(message)
    receive=value.observed_callback(FinalIssuedCommandReceipt,
        '/mecanum/final_issued_command',production_receipt_consumer)
    returned=receive(wire,{})

    assert delivered==[26]
    assert returned is receipt_views[26]
    assert not receipts  # B1 selection cannot consume the withheld receipt.
    assert receipt_views[26] is returned  # Native application join remains live.
    assert events[-1][0]=='B23_R06C_OBSERVATION0_RECEIPT_WITHHELD_FROM_B1'
    assert events[-1][1]['wire_cdr_hex']==wire.hex()
    assert value._r06c_held_receipts[0]['final_publish_sequence']==26


def test_reset_measurements_wait_for_scan_with_original_deadline():
    value, clock=worker()
    value.ingress.scans={}
    value.ingress.lifecycle=NS(barrier_stamp=NS(sec=0,nanosec=90))
    value.ingress.profile={"scan_max_age_ms":500}
    value.ingress.scan_reset_stamp_ns=90
    value.ingress.physics_pairs=[]
    value.ros_now=lambda:100
    async def consume():
        async for _ in value.measurements(deadline_ns=clock.ns+5_000_000,after_iteration=0):
            pytest.fail('measurement requires actual physics pair')
    with pytest.raises(TimeoutError,match='fresh reset scan'):
        asyncio.run(consume())
    assert clock.ns==1_005_000_000


def test_reset_scan_rejects_old_delayed_and_stale_samples():
    value,clock=worker()
    value.ingress.lifecycle=NS(barrier_stamp=NS(sec=1,nanosec=0))
    value.ingress.profile={'scan_max_age_ms':100}
    value.ingress.scan_reset_stamp_ns=1_001_000_000
    value.ingress.scans={999_999_999:NS(received_steady_ns=clock.ns)}
    assert value.fresh_reset_scan(now_ros_ns=1_010_000_000,now_steady_ns=clock.ns) is None
    value.ingress.scans[1_001_000_000]=NS(received_steady_ns=clock.ns)
    assert value.fresh_reset_scan(now_ros_ns=1_010_000_000,now_steady_ns=clock.ns) is None
    value.ingress.scans[1_001_000_001]=NS(received_steady_ns=clock.ns-200_000_000)
    assert value.fresh_reset_scan(now_ros_ns=1_010_000_000,now_steady_ns=clock.ns) is None
    fresh=NS(received_steady_ns=clock.ns)
    value.ingress.scans[1_002_000_000]=fresh
    assert value.fresh_reset_scan(now_ros_ns=1_010_000_000,now_steady_ns=clock.ns) is fresh
    later=NS(received_steady_ns=clock.ns)
    value.ingress.scans[1_009_000_000]=later
    assert value.fresh_reset_scan(now_ros_ns=1_010_000_000,now_steady_ns=clock.ns,
        at_or_before_ns=1_005_000_000) is fresh


def test_observation0_handoff_rejects_pre_reset_scan_until_deadline():
    from mecanum_nav_rl_interfaces.msg import LocalTrainingSafetyInput
    value,clock=worker();calls=[]
    value.ros_now=lambda:100
    value.ingress.lifecycle=NS(barrier_stamp=NS(sec=0,nanosec=90))
    value.ingress.scan_reset_stamp_ns=95
    value.ingress.profile={'scan_max_age_ms':500}
    value.ingress.scans={95:NS(stamp_ns=95,received_steady_ns=clock.ns)}
    value.ingress.admission_state=LocalTrainingSafetyInput.ADMISSION_INHIBITED
    value.ingress.confirm_observation0=lambda ack:calls.append('confirmed')
    b1=NS(commit_observation0=lambda cutoff:calls.append('committed'))
    with pytest.raises(TimeoutError,match='observation0 did not confirm'):
        asyncio.run(value.commit_and_confirm_observation0(b1,deadline_ns=clock.ns+5_000_000))
    assert calls==[] and value.ingress.admission_state==LocalTrainingSafetyInput.ADMISSION_INHIBITED


def test_observation0_handoff_uses_fresh_scan_after_zero_anchor():
    from mecanum_nav_rl_interfaces.msg import LocalTrainingSafetyInput
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    from mecanum_nav_rl.runtime_simulation import local_training_coordinator

    value,clock=worker(); calls=[]; ack=NS(request_bytes=b'confirm-request',response_bytes=b'confirm-response')
    value.ros_now=lambda:1_010_000_000
    value.ingress.lifecycle=NS(barrier_stamp=NS(sec=0,nanosec=90))
    value.ingress.scan_reset_stamp_ns=95
    value.ingress.profile={'scan_max_age_ms':500}
    fresh=NS(stamp_ns=1_000_000_000,received_steady_ns=clock.ns)
    value.ingress.scans={fresh.stamp_ns:fresh}
    value.ingress.admission_state=LocalTrainingSafetyInput.ADMISSION_INHIBITED
    value.final=NS(publisher_instance_id=33)
    value.ingress.confirm_observation0=lambda result:calls.append(('confirmed',result))
    receipt=NS(final_publish_sequence=27,final_publisher_instance_id=33,receipt_key=('p',27))
    adjacent=NS(final_publish_sequence=28,final_publisher_instance_id=33,receipt_key=('p',28))
    selection=NS(receipt=receipt,adjacent_receipt=adjacent)
    b1=NS(preview_observation0_selection=lambda cutoff:selection,
        _prove_application=lambda _receipt, _cutoff:{'iteration':9,'stamp_ns':1_090_000_000},
        commit_observation0=lambda cutoff, **kwargs:(calls.append(('committed',cutoff,kwargs)) or ('observation0',selection)))
    value.native_adjacent_boundary_application=lambda _selection, _cutoff:{'iteration':10,'stamp_ns':1_120_000_000}
    async def transact(operation,**kwargs):
        calls.append(('control',operation,kwargs['observation0_cutoff']))
        return ack
    value.control=NS(transact=transact)
    original=local_training_coordinator.lifecycle_request_fields
    local_training_coordinator.lifecycle_request_fields=lambda _snapshot:{}
    try:
        result,cutoff=asyncio.run(value.commit_and_confirm_observation0(
            b1,deadline_ns=clock.ns+5_000_000,
            zero_receipt=NS(applied_sim_stamp_ns=990_000_000)))
    finally:
        local_training_coordinator.lifecycle_request_fields=original

    assert result=='observation0' and cutoff==fresh.stamp_ns, calls
    assert calls[0][0:2]==('committed',fresh.stamp_ns), calls
    assert calls[0][2]['expected_selection_keys']==(receipt.receipt_key,adjacent.receipt_key)
    assert calls[1][0]=='control' and calls[1][1]==Control.Request.OP_CONFIRM_OBSERVATION0, calls
    assert calls[2]==('confirmed',ack), calls
    assert value.ingress.admission_state==LocalTrainingSafetyInput.ADMISSION_INHIBITED


def test_observation0_waits_for_native_adjacent_receipt_application_before_b1_commit():
    import threading
    from builtin_interfaces.msg import Time
    from mecanum_nav_rl_interfaces.msg import LocalTrainingSafetyInput, SimulationContactState
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    from mecanum_nav_rl.runtime_simulation import local_training_coordinator
    from rclpy.serialization import serialize_message

    value, clock = worker()
    cutoff = 1_100_000_000
    adjacent_stamp = 1_120_000_000
    value.ros_now = lambda: 1_200_000_000
    value.ingress.lifecycle = NS(barrier_stamp=Time(sec=0, nanosec=900_000_000))
    value.ingress.scan_reset_stamp_ns = 900_000_000
    value.ingress.profile = {'scan_max_age_ms': 500}
    scan = NS(stamp_ns=cutoff, received_steady_ns=clock.ns)
    value.ingress.scans = {cutoff: scan}
    value.ingress.admission_state = LocalTrainingSafetyInput.ADMISSION_INHIBITED
    value.ingress.lock = threading.Lock()
    value.ingress._application_bytes = {}
    value.final = NS(publisher_instance_id=55)
    receipt = NS(receipt_key=('session', 8), final_publish_sequence=8,
        final_publisher_instance_id=55)
    adjacent = NS(receipt_key=('session', 9), final_publish_sequence=9,
        final_publisher_instance_id=55)
    selection = NS(receipt=receipt, adjacent_receipt=adjacent)
    commit_calls, control_calls, confirmations, events = [], [], [], []

    def commit(selected_cutoff, *, expected_selection_keys=None):
        assert 9 in value.ingress._application_bytes, 'B1 commit preceded native application'
        commit_calls.append((selected_cutoff, expected_selection_keys))
        return 'observation0', selection

    b1 = NS(preview_observation0_selection=lambda selected_cutoff:selection,
        _prove_application=lambda _receipt, _cutoff:{'iteration':11,'stamp_ns':1_090_000_000},
        commit_observation0=commit)
    value.ingress.confirm_observation0 = lambda ack: confirmations.append(ack)
    value.emit = lambda name, fields: events.append((name, fields))
    async def transact(operation, **fields):
        control_calls.append((operation, fields['selected_zero_final_publish_sequence'],
            fields['adjacent_boundary_final_publish_sequence']))
        return 'confirm-ack'
    value.control = NS(transact=transact)

    status = SimulationContactState()
    status.applied_receipt_valid = True
    status.local_zero_override = False
    status.applied_final_publisher_instance_id = 55
    status.applied_final_publish_sequence = 9
    status.applied_physics_iteration = 12
    status.physics_iteration = 12
    status.applied_sim_stamp = Time(sec=1, nanosec=120_000_000)
    status.header.stamp = Time(sec=1, nanosec=120_000_000)
    raw_application = serialize_message(status)
    pause_calls = []
    async def pause(seconds):
        pause_calls.append(seconds)
        await clock.pause(seconds)
        value.ingress._application_bytes[9] = raw_application
    value.pause = pause
    original = local_training_coordinator.lifecycle_request_fields
    local_training_coordinator.lifecycle_request_fields = lambda _snapshot:{}
    try:
        result, selected_cutoff = asyncio.run(value.commit_and_confirm_observation0(
            b1, deadline_ns=clock.ns + 20_000_000,
            zero_receipt=NS(applied_sim_stamp_ns=1_000_000_000)))
    finally:
        local_training_coordinator.lifecycle_request_fields = original

    assert result == 'observation0' and selected_cutoff == cutoff
    assert len(pause_calls) == 1, 'caller must wait after receipt publication until native application'
    assert commit_calls == [(cutoff, (receipt.receipt_key, adjacent.receipt_key))]
    assert control_calls == [(Control.Request.OP_CONFIRM_OBSERVATION0, 8, 9)]
    assert confirmations == ['confirm-ack']
    deferred = [fields for name, fields in events if name == 'RESET_ADJACENT_BOUNDARY_DEFERRED']
    applied = [fields for name, fields in events if name == 'RESET_ADJACENT_BOUNDARY_NATIVE_APPLIED']
    assert len(deferred) == len(applied) == 1
    assert deferred[0]['adjacent_publish_sequence'] == applied[0]['adjacent_publish_sequence'] == 9
    assert applied[0]['application_iteration'] == 12
    assert applied[0]['application_stamp_ns'] == adjacent_stamp


def test_observation0_handoff_rejects_scan_before_zero_anchor():
    from mecanum_nav_rl_interfaces.msg import LocalTrainingSafetyInput
    value,clock=worker()
    value.ros_now=lambda:1_010_000_000
    value.ingress.lifecycle=NS(barrier_stamp=NS(sec=0,nanosec=90))
    value.ingress.scan_reset_stamp_ns=95
    value.ingress.profile={'scan_max_age_ms':500}
    value.ingress.scans={980_000_000:NS(stamp_ns=980_000_000,received_steady_ns=clock.ns)}
    value.ingress.admission_state=LocalTrainingSafetyInput.ADMISSION_INHIBITED
    value.ingress.confirm_observation0=lambda _ack:pytest.fail('pre-anchor scan cannot confirm')
    b1=NS(preview_observation0_selection=lambda _cutoff:pytest.fail('pre-anchor scan cannot preview'),
        commit_observation0=lambda _cutoff, **_kwargs:pytest.fail('pre-anchor scan cannot commit'))
    with pytest.raises(TimeoutError,match='observation0 did not confirm'):
        asyncio.run(value.commit_and_confirm_observation0(
            b1,deadline_ns=clock.ns+5_000_000,
            zero_receipt=NS(applied_sim_stamp_ns=990_000_000)))
    assert value.ingress.admission_state==LocalTrainingSafetyInput.ADMISSION_INHIBITED


def test_observation0_aligns_safe_stop_receipt_away_from_scan_cutoff():
    from collections import deque
    from builtin_interfaces.msg import Time
    from mecanum_nav_rl.core.issued_command_cutoff import (
        IssuedCommandReceiptView, ReceiptSource, ReceiptStreamBinding,
        CutoffStatus, select_reset_zero_at_cutoff,
    )
    from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity
    from mecanum_nav_rl_interfaces.msg import (
        CommandEnvelope, LocalTrainingSafetyInput, SimulationContactState,
    )
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    from mecanum_nav_rl.runtime_simulation import local_training_coordinator
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import B1SnapshotPending
    from rclpy.serialization import serialize_message

    value, clock = worker()
    value.deadline_ns = clock.ns + 1_000_000_000
    ros_ns = [1_090_000_000]
    value.ros_now = lambda: ros_ns[0]
    lifecycle = NS(episode_generation=1, reset_epoch=2, runtime_generation=3,
        barrier_stamp=Time(sec=0, nanosec=800_000_000))
    value.ingress.lifecycle = lifecycle
    value.ingress.scan_reset_stamp_ns = 800_000_000
    value.ingress.profile = {'scan_max_age_ms': 500, 'safety_period_ms': 20,
        'final_command_timeout_ms': 100}
    value.ingress.scans = {
        900_000_000: NS(stamp_ns=900_000_000, received_steady_ns=clock.ns),
        1_000_000_000: NS(stamp_ns=1_000_000_000, received_steady_ns=clock.ns),
    }
    value.ingress.admission_state = LocalTrainingSafetyInput.ADMISSION_INHIBITED
    value.ingress.last_published_admission_state = LocalTrainingSafetyInput.ADMISSION_INHIBITED
    value.ingress.fault = None
    value.ingress.backend_state = NS(fault_flags=0)
    value.ingress.receipts = deque()
    identity = EpisodeLifecycleIdentity(1, 2, 3)
    receipt = NS(source=ReceiptSource.SAFE_STOP, lifecycle=identity,
        publish_stamp_ns=1_080_000_000, final_publisher_instance_id=55,
        final_publish_sequence=8, final_command=(0.0, 0.0, 0.0),
        received_steady_ns=clock.ns)
    value.ingress.receipts.append(receipt)
    status = SimulationContactState()
    status.applied_receipt_valid = True
    status.local_zero_override = False
    status.applied_final_publisher_instance_id = 55
    status.applied_final_publish_sequence = 8
    status.applied_physics_iteration = 9
    status.applied_sim_stamp = Time(sec=1, nanosec=90_000_000)
    value.ingress.physics_pairs = [NS(stamp_ns=1_090_000_000, iteration=9,
        backend_bytes=serialize_message(status))]

    stream_history, events = [], []
    alignment_calls = []
    adapter = NS(policy_hold=True,
        last_output=NS(source=CommandEnvelope.SOURCE_SAFE_STOP),
        set_stream_enabled=lambda enabled: stream_history.append((enabled, clock.ns)))
    value.safety = NS(local_training=adapter)
    async def align(*, failed_cutoff_ns, deadline_ns):
        alignment_calls.append((failed_cutoff_ns, deadline_ns))
        return True
    value.align_reset_zero_receipt_boundary = align
    value.final = NS(publisher_instance_id=55)
    value.emit = lambda name, fields: events.append((name, fields))
    async def pause(seconds):
        await clock.pause(seconds)
        ros_ns[0] += 10_000_000
        if ros_ns[0] == 1_100_000_000:
            value.ingress.scans[ros_ns[0]] = NS(stamp_ns=ros_ns[0], received_steady_ns=clock.ns)
        if ros_ns[0] == 1_120_000_000:
            value.ingress.receipts.append(NS(source=ReceiptSource.SAFE_STOP, lifecycle=identity,
                publish_stamp_ns=ros_ns[0], final_publisher_instance_id=55,
                final_publish_sequence=9, final_command=(0.0, 0.0, 0.0),
                received_steady_ns=clock.ns))
    value.pause = pause

    cutoffs = []
    binding = ReceiptStreamBinding(55, 'session', 'a' * 64, identity, 'base_link')
    def receipt_view(sequence, stamp, received):
        return IssuedCommandReceiptView(stamp, 55, sequence, ReceiptSource.SAFE_STOP,
            66, sequence, 0, '', identity, 'session', 'a' * 64, (0.0, 0.0, 0.0),
            received, 'base_link', True)
    selected_view = receipt_view(8, 1_080_000_000, clock.ns)
    adjacent_view = receipt_view(9, 1_120_000_000, clock.ns + 40_000_000)
    selection = select_reset_zero_at_cutoff((selected_view, adjacent_view), binding=binding,
        cutoff_ros_ns=1_100_000_000, evaluation_ros_now_ns=1_120_000_000,
        evaluation_steady_now_ns=clock.ns + 50_000_000, reset_barrier_ros_ns=800_000_000,
        physical_scales=(0.25, 0.2, 0.8))
    assert selection.status is CutoffStatus.READY, selection.reason
    assert selection.receipt.final_publish_sequence == 8
    assert selection.adjacent_receipt.final_publish_sequence == 9
    def preview(cutoff):
        previewed.append(cutoff)
        return selection
    previewed=[]
    def commit(cutoff, *, expected_selection_keys=None):
        cutoffs.append(cutoff)
        assert expected_selection_keys == (selection.receipt.receipt_key,
            selection.adjacent_receipt.receipt_key)
        return 'observation0', selection

    application_checks = []
    def prove_selected_application(_receipt, cutoff):
        application_checks.append(cutoff)
        if len(application_checks) == 1:
            raise B1SnapshotPending('selected receipt lacks native application at/before cutoff')
        return {'iteration':11,'stamp_ns':cutoff}
    confirmations, control_calls = [], []
    value.ingress.confirm_observation0 = lambda ack: confirmations.append(ack)
    value.native_adjacent_boundary_application=lambda _selection, cutoff:{
        'iteration':10,'stamp_ns':cutoff+20_000_000}
    async def transact(operation, **fields):
        control_calls.append((operation, fields['observation0_cutoff'].nanosec))
        return 'actual-ack'
    value.control = NS(transact=transact)
    original = local_training_coordinator.lifecycle_request_fields
    local_training_coordinator.lifecycle_request_fields = lambda _snapshot: {}
    try:
        result, cutoff = asyncio.run(value.commit_and_confirm_observation0(
            NS(preview_observation0_selection=preview,
                _prove_application=prove_selected_application, commit_observation0=commit),
            deadline_ns=clock.ns + 500_000_000))
    finally:
        local_training_coordinator.lifecycle_request_fields = original

    assert result == 'observation0' and cutoff == 1_100_000_000
    assert previewed == [1_000_000_000, 1_100_000_000]
    assert application_checks == [1_000_000_000, 1_100_000_000]
    assert cutoffs == [1_100_000_000]
    assert alignment_calls and alignment_calls[0][0] == 1_000_000_000
    assert not stream_history
    assert not [name for name, _ in events if name == 'RESET_RECEIPT_ALIGNMENT_DEFERRED']
    assert 'RESET_ADJACENT_BOUNDARY_NATIVE_APPLIED' in [name for name, _ in events]
    assert control_calls == [(Control.Request.OP_CONFIRM_OBSERVATION0, 100_000_000)]
    assert confirmations == ['actual-ack']


def test_observation0_waits_for_fresh_zero_when_b1_cutoff_receipt_is_stale():
    from collections import OrderedDict
    from builtin_interfaces.msg import Time
    from mecanum_nav_rl.core.issued_command_cutoff import (
        IssuedCommandReceiptView, ReceiptSource,
    )
    from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import (
        LocalTrainingB1Adapter,
    )
    from mecanum_nav_rl.runtime_simulation import local_training_coordinator

    value, clock = worker()
    identity = EpisodeLifecycleIdentity(1, 2, 3)
    ros_ns = [1_100_000_000]
    lifecycle = NS(barrier_stamp=Time(sec=0, nanosec=200_000_000))
    source = NS(
        final_publisher_id=55,
        identity=NS(session_id='session', config_hash='a' * 64),
        lifecycle=lifecycle,
        receipts=[],
    )
    selector = NS(ingress=source, scales=(0.25, 0.2, 0.8))

    def receipt(sequence, stamp, received):
        return IssuedCommandReceiptView(
            stamp, 55, sequence, ReceiptSource.SAFE_STOP, 66, sequence, 0, '',
            identity, 'session', 'a' * 64, (0.0, 0.0, 0.0), received,
            'base_link', True)

    # Lượt đầu: B1 chọn zero mới nhất trước cutoff, nhưng dữ liệu đó đã quá
    # tuổi 500 ms. Receipt kế tiếp nằm sau cutoff và chỉ làm bằng chứng biên.
    source.receipts.extend((
        receipt(7, 300_000_000, 800_000_000),
        receipt(8, 1_020_000_000, 950_000_000),
    ))
    value.ingress = NS(
        fault=None,
        backend_state=None,
        lifecycle=lifecycle,
        scan_reset_stamp_ns=200_000_000,
        profile={'scan_max_age_ms': 500},
        scans=OrderedDict(((1_000_000_000,
            NS(stamp_ns=1_000_000_000, received_steady_ns=clock.ns)),)),
        confirm_observation0=lambda _ack: confirmations.append('ack'),
    )
    value.ros_now = lambda: ros_ns[0]
    events, previews, commits, confirmations, control_calls = [], [], [], [], []
    value.final = NS(publisher_instance_id=55)
    value.emit = lambda name, facts: events.append((name, facts))
    value.native_adjacent_boundary_application = lambda _selection, cutoff: {
        'iteration': 10, 'stamp_ns': cutoff + 20_000_000}
    async def pause(seconds):
        await clock.pause(seconds)
        ros_ns[0] = 1_120_000_000
        value.ingress.scans[1_100_000_000] = NS(
            stamp_ns=1_100_000_000, received_steady_ns=clock.ns)
        source.receipts.extend((
            receipt(9, 1_050_000_000, clock.ns),
            receipt(10, 1_120_000_000, clock.ns),
        ))
    value.pause = pause
    def preview(cutoff):
        previews.append(cutoff)
        facts = {'identity': identity, 'cutoff': cutoff,
            'ros_now': ros_ns[0], 'steady_now': clock.ns}
        return LocalTrainingB1Adapter._selection(selector, facts, reset=True)
    def prove(_receipt, cutoff):
        return NS(stamp_ns=cutoff)
    preview_selection = []
    def commit(cutoff, *, expected_selection_keys):
        commits.append((cutoff, expected_selection_keys))
        selected = preview_selection[0]
        assert expected_selection_keys == (
            selected.receipt.receipt_key,
            selected.adjacent_receipt.receipt_key)
        return 'observation0', selected
    b1 = NS(preview_observation0_selection=preview,
        _prove_application=prove,
        commit_observation0=commit)
    # Capture the ready selection only after the production selector returns it.
    def capture_preview(cutoff):
        selected = preview(cutoff)
        preview_selection[:] = [selected]
        return selected
    b1.preview_observation0_selection = capture_preview
    async def transact(operation, **fields):
        control_calls.append((operation, fields['observation0_cutoff']))
        return 'actual-confirm-ack'
    value.control = NS(transact=transact)
    original = local_training_coordinator.lifecycle_request_fields
    local_training_coordinator.lifecycle_request_fields = lambda _snapshot: {}
    try:
        result, cutoff = asyncio.run(value.commit_and_confirm_observation0(
            b1, deadline_ns=clock.ns + 300_000_000))
    finally:
        local_training_coordinator.lifecycle_request_fields = original

    assert result == 'observation0' and cutoff == 1_100_000_000, (result, cutoff, events)
    assert previews == [1_000_000_000, 1_100_000_000], (previews, events)
    assert len(commits) == 1 and commits[0][0] == 1_100_000_000, (commits, events)
    deferred = [facts for name, facts in events
        if name == 'RESET_ZERO_RECEIPT_FRESHNESS_DEFERRED']
    assert len(deferred) == 1 and '500 ms' in deferred[0]['reason'], events
    assert confirmations == ['ack'] and control_calls


def test_reset_cutoff_future_receipt_remains_rejected_not_pending():
    from mecanum_nav_rl.core.issued_command_cutoff import (
        IssuedCommandReceiptView, ReceiptSource, ReceiptStreamBinding,
        select_reset_zero_at_cutoff,
    )
    from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity

    identity = EpisodeLifecycleIdentity(1, 2, 3)
    binding = ReceiptStreamBinding(55, 'session', 'a' * 64, identity, 'base_link')
    def receipt(sequence, stamp, received):
        return IssuedCommandReceiptView(stamp, 55, sequence, ReceiptSource.SAFE_STOP,
            66, sequence, 0, '', identity, 'session', 'a' * 64,
            (0.0, 0.0, 0.0), received, 'base_link', True)
    selection = select_reset_zero_at_cutoff(
        (receipt(1, 900_000_000, 1_000_000_001),
         receipt(2, 1_010_000_000, 1_000_000_001)),
        binding=binding, cutoff_ros_ns=1_000_000_000,
        evaluation_ros_now_ns=1_010_000_000,
        evaluation_steady_now_ns=1_000_000_000,
        reset_barrier_ros_ns=800_000_000,
        physical_scales=(0.25, 0.2, 0.8))
    assert selection.status.value == 'rejected'
    assert selection.reason == 'ready selection receipt has a future timestamp'


def test_observation0_defers_scan_alignment_until_two_post_reset_scans():
    from builtin_interfaces.msg import Time
    from mecanum_nav_rl.runtime_simulation import local_training_coordinator
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import B1SnapshotPending

    value, clock = worker()
    value.deadline_ns = clock.ns + 200_000_000
    ros_ns = [1_020_000_000]
    value.ros_now = lambda: ros_ns[0]
    value.node = NS(get_clock=lambda: NS(now=lambda: NS(nanoseconds=ros_ns[0])))
    life = NS(barrier_stamp=Time(sec=0, nanosec=900_000_000))
    first = NS(stamp_ns=1_000_000_000, received_steady_ns=clock.ns)
    second = NS(stamp_ns=1_100_000_000, received_steady_ns=clock.ns)
    value.ingress = NS(lifecycle=life, scan_reset_stamp_ns=900_000_000,
        scans={first.stamp_ns:first}, profile={'scan_max_age_ms':500}, fault=None,
        backend_state=NS(fault_flags=0), admission_state=0,
        confirm_observation0=lambda ack: confirmations.append(ack))
    value.final = NS(publisher_instance_id=55)
    value.control = NS(transact=lambda *args, **kwargs: asyncio.sleep(0, result='ack'))
    confirmations, cutoffs, align_calls, events = [], [], [], []
    receipt = NS(receipt_key=('session', 8), final_publish_sequence=8,
        final_publisher_instance_id=55)
    adjacent = NS(receipt_key=('session', 9), final_publish_sequence=9,
        final_publisher_instance_id=55)
    selection = NS(receipt=receipt, adjacent_receipt=adjacent)
    previewed = []

    def preview(cutoff):
        previewed.append(cutoff)
        if len(previewed) < 3:
            raise B1SnapshotPending('selected receipt lacks native application at/before cutoff')
        return selection

    def commit(cutoff, *, expected_selection_keys=None):
        cutoffs.append(cutoff)
        assert expected_selection_keys == (receipt.receipt_key, adjacent.receipt_key)
        return 'observation0', selection

    b1 = NS(preview_observation0_selection=preview,
        _prove_application=lambda _receipt, _cutoff:{'iteration':12,'stamp_ns':1_120_000_000},
        commit_observation0=commit)
    value.native_adjacent_boundary_application = lambda _selection, cutoff:{
        'iteration':12, 'stamp_ns':cutoff + 20_000_000}

    async def pause(duration):
        await clock.pause(duration)
        ros_ns[0] = 1_120_000_000
        value.ingress.scans[second.stamp_ns] = second

    async def align(*, failed_cutoff_ns, deadline_ns):
        stamps = sorted(stamp for stamp in value.ingress.scans
            if value.ingress.scan_reset_stamp_ns < stamp <= failed_cutoff_ns)
        align_calls.append((failed_cutoff_ns, stamps))
        return True

    value.pause = pause
    value.align_reset_zero_receipt_boundary = align
    value.emit = lambda name, fields: events.append((name, fields))
    original = local_training_coordinator.lifecycle_request_fields
    local_training_coordinator.lifecycle_request_fields = lambda _snapshot: {}
    try:
        result, cutoff = asyncio.run(value.commit_and_confirm_observation0(
            b1, deadline_ns=clock.ns + 100_000_000,
            zero_receipt=NS(applied_sim_stamp_ns=950_000_000)))
    finally:
        local_training_coordinator.lifecycle_request_fields = original

    assert result == 'observation0' and cutoff == second.stamp_ns
    assert previewed == [first.stamp_ns, second.stamp_ns, second.stamp_ns]
    assert cutoffs == [second.stamp_ns]
    assert align_calls == [(second.stamp_ns, [first.stamp_ns, second.stamp_ns])]
    assert [name for name, _ in events] == [
        'RESET_RECEIPT_ALIGNMENT_DEFERRED', 'RESET_ADJACENT_BOUNDARY_NATIVE_APPLIED']
    assert confirmations == ['ack']


@pytest.mark.parametrize('application_delta_ns, accepted', [(0, True), (1, False)])
def test_reset_zero_alignment_uses_observed_applied_receipt_not_predicted_stamp(
        application_delta_ns, accepted):
    """Timer phase may skip target-safety_period; pin the real applied zero."""
    from builtin_interfaces.msg import Time
    from mecanum_nav_rl_interfaces.msg import SimulationContactState
    from rclpy.serialization import serialize_message
    from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
    from mecanum_nav_rl.runtime_simulation.local_training_ingress import lifecycle_identity

    value, clock = worker()
    value.deadline_ns = clock.ns + 300_000_000
    ros_ns = [1_000_000_000]
    target = 1_100_000_000
    life = NS(episode_generation=1, reset_epoch=2, runtime_generation=3,
        barrier_stamp=Time(sec=0, nanosec=800_000_000))
    identity = lifecycle_identity(life)
    applied = SimulationContactState()
    applied.applied_receipt_valid = True
    applied.local_zero_override = False
    applied.applied_final_publisher_instance_id = 55
    applied.applied_final_publish_sequence = 11
    applied.applied_physics_iteration = 110
    # The reset contract accepts native application exactly at the scan cutoff.
    applied.applied_sim_stamp = Time(sec=1, nanosec=100_000_000 + application_delta_ns)
    receipt = NS(source=ReceiptSource.SAFE_STOP, lifecycle=identity,
        publish_stamp_ns=1_060_000_000, received_steady_ns=clock.ns,
        final_publisher_instance_id=55, final_publish_sequence=11,
        final_command=(0., 0., 0.))
    # Receipt callbacks may coalesce sequences 12 and 13. This candidate only
    # unblocks resynchronization; B1 must still prove its own exact adjacent
    # pair before observation0 can be committed.
    adjacent = NS(source=ReceiptSource.SAFE_STOP, lifecycle=identity,
        publish_stamp_ns=1_120_000_000, received_steady_ns=0,
        final_publisher_instance_id=55, final_publish_sequence=14,
        final_command=(0., 0., 0.))
    suppressed = NS(_reset_boundary_suppressed_stamp_ns=None,
        _reset_scan_boundary_stamp_ns=None, policy_hold=True,
        last_output=NS(source=1))
    armed = []
    def arm(stamp):
        armed.append(stamp)
        suppressed._reset_scan_boundary_stamp_ns = stamp
    suppressed.arm_reset_scan_boundary = arm
    suppressed.cancel_reset_scan_boundary = lambda stamp: setattr(
        suppressed, '_reset_scan_boundary_stamp_ns', None)
    value.node = NS(get_clock=lambda: NS(now=lambda: NS(nanoseconds=ros_ns[0])))
    value.ros_now = lambda: ros_ns[0]
    value.ingress = NS(lifecycle=life, scan_reset_stamp_ns=800_000_000,
        scans={900_000_000: NS(stamp_ns=900_000_000), 1_000_000_000: NS(stamp_ns=1_000_000_000)},
        profile={'safety_period_ms': 20, 'scan_max_age_ms': 500,
            'final_command_timeout_ms': 100, 'b1_receipt_max_age_ms': 500}, receipts=[receipt],
        # The native status/oracle join is delayed past the scan callback.
        # Production must retain the same pinned receipt and wait inside its
        # existing freshness window rather than fail on callback ordering.
        physics_pairs=[], admission_state=0,
        last_published_admission_state=0, fault=None, backend_state=NS(fault_flags=0),
        lock=threading.RLock())
    from mecanum_nav_rl_interfaces.msg import CommandEnvelope
    suppressed.last_output.source = CommandEnvelope.SOURCE_SAFE_STOP
    value.safety = NS(local_training=suppressed)
    value.final = NS(publisher_instance_id=55)
    value.pause = None
    events = []
    value.emit = lambda name, fields: events.append((name, fields))

    boundary_overrun_polls = [0]
    scan_delivered_ns = [None]
    application_delivered_ns = [None]
    async def advance(seconds):
        before = ros_ns[0]
        await clock.pause(seconds)
        ros_ns[0] = min(target + 10_000_000, before + 10_000_000)
        if ros_ns[0] == target:
            suppressed._reset_boundary_suppressed_stamp_ns = target
        elif ros_ns[0] > target:
            boundary_overrun_polls[0] += 1
        if ros_ns[0] > target and boundary_overrun_polls[0] >= 60 and len(value.ingress.receipts) == 1:
            # Clock/suppression may advance before the scan callback is
            # delivered. The production wait must keep polling in the same
            # 500 ms receipt-age budget, independent of the 100 ms command
            # watchdog, until that exact post-barrier sample is visible.
            value.ingress.scans[target] = NS(stamp_ns=target)
            adjacent.received_steady_ns = clock.ns
            value.ingress.receipts.append(adjacent)
            scan_delivered_ns[0] = clock.ns
        elif scan_delivered_ns[0] is not None and not value.ingress.physics_pairs:
            value.ingress.physics_pairs.append(NS(stamp_ns=target + application_delta_ns, iteration=110,
                backend_bytes=serialize_message(applied)))
            application_delivered_ns[0] = clock.ns

    value.pause = advance
    if not accepted:
        with pytest.raises(TimeoutError, match='exact native SAFE_STOP application before reset scan boundary'):
            asyncio.run(value.align_reset_zero_receipt_boundary(
                failed_cutoff_ns=1_000_000_000, deadline_ns=clock.ns + 300_000_000))
        assert not any(name == 'RESET_RECEIPT_ALIGNMENT_BOUNDARY_CANDIDATE' for name, _ in events)
        return
    result = asyncio.run(value.align_reset_zero_receipt_boundary(
        failed_cutoff_ns=1_000_000_000, deadline_ns=clock.ns + 300_000_000))
    assert result is True
    assert armed == [target]
    boundary = next(fields for name, fields in events
        if name == 'RESET_RECEIPT_ALIGNMENT_BOUNDARY_CANDIDATE')
    assert boundary['target_scan_ns'] == target
    assert boundary['selected_receipt_sequence'] == 11
    assert boundary['post_boundary_receipt_sequence'] == 14
    assert boundary['post_boundary_receipt_stamp_ns'] > target
    assert boundary['receipt_receive_gap_ns'] <= 500_000_000
    assert scan_delivered_ns[0] < application_delivered_ns[0]
    assert application_delivered_ns[0] <= boundary['steady_ns']
    pending = next(fields for name, fields in events
        if name == 'RESET_RECEIPT_ALIGNMENT_BOUNDARY_PENDING')
    assert pending['suppressed'] is True
    assert pending['target_scan_ns'] == target
    assert events.index(('RESET_RECEIPT_ALIGNMENT_BOUNDARY_PENDING', pending)) < events.index(
        ('RESET_RECEIPT_ALIGNMENT_BOUNDARY_CANDIDATE', boundary))


def test_observation0_reanchors_zero_after_pause_before_b1_cutoff():
    """A >500 ms W1 is retained for pause, while B1 receives fresh L2 zero."""
    value, clock = worker()
    clock.ns = 2_000_000_000
    w1 = NS(final_publish_sequence=24, received_steady_ns=1_400_000_000,
        applied_sim_stamp_ns=630_000_000)
    fresh = NS(final_publish_sequence=25, received_steady_ns=clock.ns,
        applied_sim_stamp_ns=900_000_000, applied_physics_iteration=90)
    order, events = [], []
    b1 = NS(begin_reset=lambda: order.append(('begin_reset', clock.ns)))
    value.ingress = NS(inhibit=lambda: order.append(('inhibit', clock.ns)))
    value.safety = NS(local_training=NS(set_stream_enabled=lambda enabled:
        order.append(('stream', enabled, clock.ns))))
    async def freeze_zero(*, deadline_ns):
        order.append(('fresh_zero_applied', clock.ns, deadline_ns))
        return fresh
    async def confirm(b1_arg, *, deadline_ns, zero_receipt):
        order.append(('b1_cutoff', clock.ns, deadline_ns, zero_receipt))
        assert b1_arg is b1
        assert zero_receipt is fresh
        assert clock.ns - zero_receipt.received_steady_ns <= 500_000_000
        assert clock.ns - w1.received_steady_ns > 500_000_000
        return 'confirmed-observation0', 910_000_000
    value.freeze_zero = freeze_zero
    value.commit_and_confirm_observation0 = confirm
    value.now = clock.now
    value.emit = lambda name, fields: events.append((name, fields))

    result = asyncio.run(value.confirm_observation0_after_resume(
        b1, deadline_ns=clock.ns + 15_000_000_000,
        seed=2026102900, w0=NS(final_publish_sequence=11), w1=w1,
        l1=NS(sequence=3), l2=NS(sequence=4), started_ns=1_000_000_000))

    assert result == 'confirmed-observation0'
    assert [item[0] for item in order] == [
        'begin_reset', 'inhibit', 'stream', 'fresh_zero_applied', 'stream', 'b1_cutoff']
    assert order[-1][3] is fresh
    assert events[0][0] == 'OBSERVATION0_ZERO_ANCHOR'
    assert events[0][1]['publish_sequence'] == 25
    assert events[-1][0] == 'RESET_COMPLETE'
    assert events[-1][1]['W1'] == 24
    assert events[-1][1]['zero_anchor_sequence'] == 25


def test_observation0_reanchor_keeps_real_b1_receipt_selection_within_500ms():
    """Old W1 fails the real cutoff selector; the post-resume anchor is selected."""
    from mecanum_nav_rl.core.issued_command_cutoff import (
        CutoffStatus, IssuedCommandReceiptView, ReceiptSource, ReceiptStreamBinding,
        select_reset_zero_at_cutoff,
    )
    from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity

    value, clock = worker()
    clock.ns = 2_000_000_000
    lifecycle = EpisodeLifecycleIdentity(1, 2, 3)
    binding = ReceiptStreamBinding(90, 'session-1', 'a' * 64, lifecycle, 'base_link')
    scales = (0.25, 0.2, 0.8)

    def receipt(sequence, stamp_ns, received_ns):
        return IssuedCommandReceiptView(
            stamp_ns, 90, sequence, ReceiptSource.SAFE_STOP, 7, sequence,
            0, '', lifecycle, 'session-1', 'a' * 64, (0.0, 0.0, 0.0),
            received_ns, 'base_link', True)

    # Reproduce _005: W1 #24 is the last zero at/before 890 ms. The next
    # receipt is after the scan cutoff, while B1 evaluates #24 at +547.8 ms.
    old_w1 = receipt(24, 630_000_000, 1_400_000_000)
    after_old_cutoff = receipt(25, 900_000_000, 1_900_000_000)
    stale = select_reset_zero_at_cutoff(
        (old_w1, after_old_cutoff), binding=binding,
        cutoff_ros_ns=890_000_000, evaluation_ros_now_ns=900_000_000,
        evaluation_steady_now_ns=1_947_800_000,
        reset_barrier_ros_ns=600_000_000, physical_scales=scales)
    assert stale.status is CutoffStatus.REJECTED
    assert 'stale or future' in stale.reason

    refreshed = receipt(26, 910_000_000, 2_000_000_000)
    adjacent = receipt(27, 920_000_000, 2_020_000_000)
    calls, events = [], []
    b1 = NS(begin_reset=lambda: calls.append(('begin_reset', clock.ns)))
    value.ingress = NS(inhibit=lambda: calls.append(('inhibit', clock.ns)))
    value.safety = NS(local_training=NS(set_stream_enabled=lambda enabled:
        calls.append(('stream', enabled, clock.ns))))

    async def freeze_zero(*, deadline_ns):
        calls.append(('fresh_zero_applied', clock.ns, deadline_ns))
        return NS(final_publish_sequence=26, received_steady_ns=2_000_000_000,
            applied_sim_stamp_ns=910_000_000, applied_physics_iteration=91)

    async def commit_with_real_selector(b1_arg, *, deadline_ns, zero_receipt):
        assert b1_arg is b1
        assert zero_receipt.final_publish_sequence == 26
        selection = select_reset_zero_at_cutoff(
            (refreshed, adjacent), binding=binding,
            cutoff_ros_ns=910_000_000, evaluation_ros_now_ns=930_000_000,
            evaluation_steady_now_ns=2_030_000_000,
            reset_barrier_ros_ns=600_000_000, physical_scales=scales)
        assert selection.status is CutoffStatus.READY, selection.reason
        assert selection.receipt.final_publish_sequence == 26
        calls.append(('b1_selected', selection.receipt.final_publish_sequence,
            selection.evaluation_steady_now_ns - selection.receipt.received_steady_ns))
        return 'confirmed-observation0', 910_000_000

    value.freeze_zero = freeze_zero
    value.commit_and_confirm_observation0 = commit_with_real_selector
    value.now = clock.now
    value.emit = lambda name, fields: events.append((name, fields))
    result = asyncio.run(value.confirm_observation0_after_resume(
        b1, deadline_ns=clock.ns + 15_000_000_000, seed=2026102900,
        w0=NS(final_publish_sequence=11), w1=NS(final_publish_sequence=24),
        l1=NS(sequence=3), l2=NS(sequence=4), started_ns=1_000_000_000))

    assert result == 'confirmed-observation0'
    assert ('b1_selected', 26, 30_000_000) in calls
    assert events[0][0] == 'OBSERVATION0_ZERO_ANCHOR'
    assert events[0][1]['publish_sequence'] == 26
    assert events[-1][0] == 'RESET_COMPLETE'


@pytest.mark.parametrize('case,reason,mode,fault_flags,queue_diag', [
    ('R02c','safe_stop','hold_policy_until_safe_stop',6,False),
    ('R02d','admission_inhibited','hold_policy_until_inhibit',6,False),
    ('R02d','admission_inhibited','hold_policy_until_inhibit',262,True)])
def test_r02_late_policy_receipt_requires_native_close_and_fail_closed_evidence(
        tmp_path, case, reason, mode, fault_flags, queue_diag):
    native=tmp_path/'native-events.jsonl'
    rows = [
        ('B23_POLICY_RECEIPT_HELD',{'mode':mode,'sequence':'52','source_sequence':'1','receive_ns':'100'}),
        ('B23_POLICY_RECEIPT_RELEASED_AFTER_CLOSE',{'reason':reason,'sequence':'52',
            'source_sequence':'1','receive_ns':'200'})]
    if queue_diag:
        rows.append(('B23_NATIVE_OUTPUT_REJECTED', {'marker':'B23_QUEUE_FAULT',
            'raw_text_sha256':'diagnostic-hash', 'reason':'event_marker_not_at_message_boundary',
            'raw_record':{'event':'owned_process_output','facts':{'text':
                '[Err] B23_QUEUE_FAULT cause=receipt_gate_release_after_inhibit receipt=held_policy'}}}))
    native.write_text('\n'.join(json.dumps({'kind':kind,'fields':fields} if kind !=
        'B23_NATIVE_OUTPUT_REJECTED' else {'kind':kind,'fields':{k:v for k,v in fields.items()
            if k != 'raw_record'},'raw_record':fields['raw_record']}) for kind,fields in rows)+'\n')
    receipt=NS(final_publish_sequence=52,final_publisher_instance_id=81)
    state=NS(fault_flags=fault_flags,
        local_zero_override=True,applied_receipt_valid=False,
        applied_final_publisher_instance_id=0,applied_final_publish_sequence=0)
    io=NS(descriptor={'native_events_path':str(native)},ingress=NS(backend_state=state),events=[])
    checked=verify_r02_late_receipt_rejected(io,case=case,step_index=1,receipt=receipt)
    assert checked['release_reason'] == reason
    assert checked['policy_backend_applied'] is False
    assert checked['b1_transition_committed'] is False
    state.local_zero_override=False
    with pytest.raises(RuntimeError,match='native fault and zero'):
        verify_r02_late_receipt_rejected(io,case=case,step_index=1,receipt=receipt)
    state.local_zero_override=True
    state.fault_flags=4
    with pytest.raises(RuntimeError,match='native fault and zero'):
        verify_r02_late_receipt_rejected(io,case=case,step_index=1,receipt=receipt)
    if queue_diag:
        state.fault_flags=262
        rows[-1][1]['raw_record']['facts']['text'] = (
            '[Err] B23_QUEUE_FAULT cause=unrelated_queue_fault receipt=held_policy')
        native.write_text('\n'.join(json.dumps({'kind':kind,'fields':fields} if kind !=
            'B23_NATIVE_OUTPUT_REJECTED' else {'kind':kind,'fields':{k:v for k,v in fields.items()
                if k != 'raw_record'},'raw_record':fields['raw_record']}) for kind,fields in rows)+'\n')
        with pytest.raises(RuntimeError,match='exact native held-receipt queue-fault evidence'):
            verify_r02_late_receipt_rejected(io,case=case,step_index=1,receipt=receipt)


def _postmortem_residue_fixture(tmp_path):
    import hashlib
    from mecanum_nav_rl.runtime_simulation.b23_runner import verify_postmortem_residue_attestation

    evidence_root = tmp_path / 'evidence'
    run_id = 'B23_R02B_TEST_001'
    unit = 'b23-r02b-test-001.service'
    run_root = evidence_root / run_id
    run_root.mkdir(parents=True)
    source_commit = 'a' * 40
    packet_raw = json.dumps({'run_id': run_id, 'unit': unit,
        'source_commit': source_commit}, sort_keys=True).encode()
    packet_hash = hashlib.sha256(packet_raw).hexdigest()
    (run_root / 'packet.json').write_bytes(packet_raw)
    raw_paths = {
        'unit_properties': run_root / 'unit_properties.json',
        'postmortem_summary': run_root / 'summary.json',
        'controller_events': run_root / 'controller-events.jsonl',
        'parent_identity': run_root / 'parent-identity.json',
        'parent_events': run_root / 'parent-events.jsonl',
    }
    cgroup_root = tmp_path / 'cgroup'
    cgroup_path = str(cgroup_root / 'user.slice/user-1000.slice/user@1000.service/app.slice' / unit)
    raw_values = {
        'unit_properties': json.dumps({'returncode': 0, 'stdout':
            'Id=' + unit + '\nInvocationID=' + '1' * 32 + '\nActiveState=failed\n'
            'MainPID=0\nControlGroup=\n'}).encode(),
        'postmortem_summary': json.dumps({'run_id': run_id, 'unit': unit,
            'expected_invocation_id': '1' * 32, 'pinned_cgroup_scan': {
                'path': cgroup_path, 'path_exists': False,
                'status': 'path_removed_confirmed', 'errors': [], 'members': []},
            'recorded_pid_checks': [{'pid': 989897, 'present': False}]}).encode(),
        'controller_events': (json.dumps({'event': 'PID_OBSERVATION', 'facts': {
            'pid': 989897, 'start_ticks': 123456}}) + '\n'
            + json.dumps({'event': 'CGROUP_OBSERVATION', 'facts': {
                'status': 'complete_members', 'members': [989897]}}) + '\n').encode(),
        'parent_identity': json.dumps({'run_id': run_id, 'packet_sha256': packet_hash,
            'identity': {'pid': 989897, 'start_ticks': 123456}}).encode(),
        'parent_events': (json.dumps({'event': 'owned_process_output',
            'facts': {'output': 'captured'}}) + '\n').encode(),
    }
    for key, path in raw_paths.items():
        path.write_bytes(raw_values[key])
    evidence_files = {str(raw_paths[key]): hashlib.sha256(raw_values[key]).hexdigest()
        for key in raw_paths}
    attestation_dir = evidence_root / 'B23_POSTMORTEM' / run_id
    attestation_dir.mkdir(parents=True)
    attestation_path = attestation_dir / 'terminal-residue.json'
    record = {
        'schema': 'b23_postmortem_residue/v1', 'run_id': run_id,
        'packet_sha256': packet_hash, 'source_commit': source_commit,
        'unit': unit, 'invocation_id': '1' * 32,
        'terminal_unit': {'invocation_id': '1' * 32, 'active_state': 'failed',
            'main_pid': 0, 'control_group': '', 'result': 'exit-code'},
        'pinned_cgroup': '/user.slice/user-1000.slice/user@1000.service/app.slice/' + unit,
        'process_identities': [{'pid': 989897, 'start_ticks': 123456}],
        'cleanup_ack_present': False,
        'evidence_files': evidence_files,
        'evidence_roles': {key: str(path) for key, path in raw_paths.items()},
        'unparsed_jsonl_tails': [],
    }
    attestation_path.write_text(json.dumps(record, sort_keys=True))
    return (evidence_root, run_id, unit, packet_hash, attestation_path,
        raw_paths['unit_properties'], cgroup_root)


def test_postmortem_residue_requires_packet_bound_raw_evidence_and_absent_cgroup(tmp_path):
    from mecanum_nav_rl.runtime_simulation.b23_runner import (
        verify_postmortem_residue_attestation, verify_previous_run_residue)

    evidence_root, run_id, unit, packet_hash, attestation_path, _raw, cgroup_root = \
        _postmortem_residue_fixture(tmp_path)
    proc_root = tmp_path / 'proc'
    proc_root.mkdir()
    result = verify_postmortem_residue_attestation(attestation_path,
        run_id=run_id, packet_sha256=packet_hash, evidence_root=evidence_root,
        cgroup_root=cgroup_root, proc_root=proc_root)
    assert result['residue_absent'] is True, result
    assert result['cleanup_ack_present'] is False, result
    assert result['cgroup_status'] == 'path_removed_confirmed', result

    guard = tmp_path / 'guards' / run_id
    guard.mkdir(parents=True)
    authority = {'run_id': run_id, 'packet_sha256': packet_hash}
    consumed = {'run_id': run_id, 'packet_sha256': packet_hash}
    (guard / 'authority.json').write_text(json.dumps(authority))
    (guard / 'consumed.json').write_text(json.dumps(consumed))
    verified = verify_previous_run_residue(guard.parent, guard,
        evidence_root=evidence_root, cgroup_root=cgroup_root, proc_root=proc_root)
    assert verified['residue_absent'] is True, verified
    assert verified['postmortem']['cleanup_ack_present'] is False, verified


def test_postmortem_residue_rejects_tampered_or_outside_evidence_and_live_identity(tmp_path):
    from mecanum_nav_rl.runtime_simulation.b23_runner import verify_postmortem_residue_attestation

    evidence_root, run_id, _unit, packet_hash, attestation_path, raw_evidence, cgroup_root = \
        _postmortem_residue_fixture(tmp_path)
    proc_root = tmp_path / 'proc'
    proc_root.mkdir()
    raw_evidence.write_bytes(b'changed')
    with pytest.raises(ValueError, match='raw evidence changed'):
        verify_postmortem_residue_attestation(attestation_path,
            run_id=run_id, packet_sha256=packet_hash, evidence_root=evidence_root,
            cgroup_root=cgroup_root, proc_root=proc_root)

    evidence_root, run_id, _unit, packet_hash, attestation_path, _raw, cgroup_root = \
        _postmortem_residue_fixture(tmp_path / 'second')
    external = tmp_path / 'outside.json'
    external.write_text(attestation_path.read_text())
    with pytest.raises(ValueError, match='outside canonical evidence root'):
        verify_postmortem_residue_attestation(external,
            run_id=run_id, packet_sha256=packet_hash, evidence_root=evidence_root,
            cgroup_root=cgroup_root, proc_root=proc_root)

    evidence_root, run_id, _unit, packet_hash, attestation_path, _raw, cgroup_root = \
        _postmortem_residue_fixture(tmp_path / 'third')
    live_proc = tmp_path / 'live-proc'
    pid_dir = live_proc / '989897'
    pid_dir.mkdir(parents=True)
    fields = ['S'] + ['1'] * 18 + ['123456']
    (pid_dir / 'stat').write_text('989897 (helper) ' + ' '.join(fields))
    with pytest.raises(ValueError, match='process identity still exists'):
        verify_postmortem_residue_attestation(attestation_path,
            run_id=run_id, packet_sha256=packet_hash, evidence_root=evidence_root,
            cgroup_root=cgroup_root, proc_root=live_proc)


def _residue_revalidation_fixture(tmp_path):
    import hashlib
    from mecanum_nav_rl.runtime_simulation.b23_runner import verify_residue_revalidation_attestation

    evidence_root = tmp_path / 'evidence'
    run_id = 'B23_R02B_20261115_001'
    unit = 'b23-r02b-20261115-001.service'
    packet_hash = '39aea4d9253f5f93daac5541e1c82df2a712a508e87432a2701f6e04b9ac1bce'
    cgroup_root = tmp_path / 'cgroup'
    cgroup_path = str(cgroup_root / 'user.slice/user-1000.slice/user@1000.service/app.slice' / unit)
    run_root = evidence_root / 'B23_RESIDUE_REVALIDATION' / run_id
    run_root.mkdir(parents=True)
    identities = [{'pid': 989897, 'start_ticks': 123456}]
    legacy_text = ("sha256 64cb78edb4e73cbc14a11d900ec193df98335fea0c37ef7f58989e04e795da4e\n"
        "identities [{'pid': 989897, 'start_ticks': 123456}]\ncleanup_ack_present False\n")
    source_record_raw = json.dumps({'type': 'response_item', 'payload': {
        'type': 'custom_tool_call_output', 'output': [{'type': 'input_text', 'text': legacy_text}]}}).encode()+b'\n'
    source_session = tmp_path / 'legacy-session.jsonl'
    source_session.write_bytes(source_record_raw)
    property_list = ('Id,LoadState,ActiveState,SubState,Result,InvocationID,ControlGroup,'
        'MainPID,ExecMainPID,ExecMainCode,ExecMainStatus,ExecStart,Type,KillMode,RuntimeMaxUSec,'
        'RuntimeRandomizedExtraUSec,TimeoutStartUSec,TimeoutStopUSec,SendSIGKILL,KillSignal,'
        'FinalKillSignal,Restart,RemainAfterExit,ExecMainExitTimestampMonotonic,MemoryMax,'
        'MemoryCurrent,MemoryPeak,OOMPolicy')
    unit_argv = ['systemctl', '--user', 'show', unit, '--no-pager', '--property=' + property_list]
    unit_stdout = ('Id=' + unit + '\nLoadState=not-found\nActiveState=inactive\nSubState=dead\n'
        'MainPID=0\nControlGroup=\nInvocationID=\n')
    raw = {
        'unit_properties': json.dumps({'argv': unit_argv, 'returncode': 0, 'error': None,
            'stdout': unit_stdout, 'stderr': '', 'stdout_hex': unit_stdout.encode().hex(),
            'stderr_hex': '', 'started_ns': 100, 'completed_ns': 200}).encode(),
        'pinned_cgroup': json.dumps({'path': cgroup_path, 'status': 'path_removed_confirmed',
            'errno': 2, 'errors': [], 'members': [],
            'started_monotonic_ns': 100, 'completed_monotonic_ns': 200}).encode(),
        'process_identities': json.dumps({'identities': identities,
            'observations': [{'pid': 989897, 'state': 'absent'}],
            'started_monotonic_ns': 100, 'completed_monotonic_ns': 200}).encode(),
        'legacy_identity_source': legacy_text.encode(),
        'legacy_source_record': source_record_raw,
    }
    roles = {}
    evidence_files = {}
    for name, value in raw.items():
        path = run_root / (name + '.json' if name != 'legacy_identity_source' else 'legacy-identity-source.txt')
        if name == 'legacy_source_record': path = run_root / 'legacy-source-record.json'
        path.write_bytes(value)
        roles[name] = str(path)
        evidence_files[str(path)] = hashlib.sha256(value).hexdigest()
    record = {'schema': 'b23_residue_revalidation/v1', 'run_id': run_id,
        'packet_sha256': packet_hash, 'unit': unit,
        'pinned_cgroup': '/user.slice/user-1000.slice/user@1000.service/app.slice/' + unit,
        'process_identities': identities, 'historical_verdict': 'UNRECOVERABLE',
        'historical_attestation_sha256': '64cb78edb4e73cbc14a11d900ec193df98335fea0c37ef7f58989e04e795da4e',
        'cleanup_ack_present': False, 'evidence_files': evidence_files, 'evidence_roles': roles,
        'legacy_record_source': {'sha256': hashlib.sha256(source_record_raw).hexdigest(),
            'path': str(source_session), 'line_number': 1}}
    attestation = run_root / 'residue-revalidation.json'
    attestation.write_text(json.dumps(record, sort_keys=True))
    guard = tmp_path / 'guards' / run_id
    guard.mkdir(parents=True)
    (guard / 'authority.json').write_text(json.dumps({'run_id': run_id, 'packet_sha256': packet_hash}))
    (guard / 'consumed.json').write_text(json.dumps({'run_id': run_id, 'packet_sha256': packet_hash}))
    proc_root = tmp_path / 'proc'
    proc_root.mkdir()
    (cgroup_root / 'user.slice/user-1000.slice/user@1000.service/app.slice').mkdir(parents=True)
    return evidence_root, run_id, packet_hash, attestation, cgroup_root, proc_root, guard, roles


def test_residue_revalidation_requires_live_unit_cgroup_and_process_absence(tmp_path):
    import hashlib
    from pathlib import Path
    from mecanum_nav_rl.runtime_simulation.b23_runner import (
        verify_previous_run_residue, verify_residue_revalidation_attestation)

    evidence_root, run_id, packet_hash, attestation, cgroup_root, proc_root, guard, roles = \
        _residue_revalidation_fixture(tmp_path)
    result = verify_residue_revalidation_attestation(attestation, run_id=run_id,
        packet_sha256=packet_hash, evidence_root=evidence_root,
        cgroup_root=cgroup_root, proc_root=proc_root)
    assert result['residue_absent'] is True, result
    assert result['cleanup_ack_present'] is False, result
    assert result['historical_verdict'] == 'UNRECOVERABLE', result
    verified = verify_previous_run_residue(guard.parent, guard,
        evidence_root=evidence_root, cgroup_root=cgroup_root, proc_root=proc_root)
    assert verified['residue_revalidation']['residue_absent'] is True, verified

    unit_path = Path(roles['unit_properties'])
    unit = json.loads(unit_path.read_bytes())
    unit['stdout'] = unit['stdout'].replace('LoadState=not-found', 'LoadState=loaded')
    unit_path.write_text(json.dumps(unit))
    record = json.loads(attestation.read_text())
    record['evidence_files'][str(unit_path)] = hashlib.sha256(unit_path.read_bytes()).hexdigest()
    attestation.write_text(json.dumps(record))
    with pytest.raises(ValueError, match='exact unit absent'):
        verify_residue_revalidation_attestation(attestation, run_id=run_id,
            packet_sha256=packet_hash, evidence_root=evidence_root,
            cgroup_root=cgroup_root, proc_root=proc_root)


def test_residue_revalidation_rejects_present_pinned_process_identity(tmp_path):
    from mecanum_nav_rl.runtime_simulation.b23_runner import verify_residue_revalidation_attestation

    evidence_root, run_id, packet_hash, attestation, cgroup_root, proc_root, _guard, _roles = \
        _residue_revalidation_fixture(tmp_path)
    pid_path = proc_root / '989897'
    pid_path.mkdir()
    fields = ['S'] + ['1'] * 18 + ['123456']
    (pid_path / 'stat').write_text('989897 (helper) ' + ' '.join(fields))
    with pytest.raises(ValueError, match='remains live'):
        verify_residue_revalidation_attestation(attestation, run_id=run_id,
            packet_sha256=packet_hash, evidence_root=evidence_root,
            cgroup_root=cgroup_root, proc_root=proc_root)


def test_policy_safety_tick_retries_immediately_after_deferred_scan_cutoff():
    io = object.__new__(TrainingWorkerIO)
    io.safety = NS(local_training=None)
    io.events = []
    io.deadline_ns = 1_000
    io.now = lambda: 100
    io.ros_now = lambda: 90
    io.emit = lambda name, facts: io.events.append((name, facts))

    class Adapter:
        def __init__(self):
            self.last_tick_ros_ns = 80
            self._last_deferred_scan_cutoff_ns = None
            self.lock = threading.RLock()
            self.calls = 0

        def tick(self):
            self.calls += 1
            if self.calls == 1:
                self._last_deferred_scan_cutoff_ns = 100
                return
            self.last_tick_ros_ns = 101

    adapter = Adapter()
    io.safety.local_training = adapter
    current_ros = {'ns':100}
    io.ros_now = lambda: current_ros['ns']

    async def until(predicate, *, deadline_ns, phase, **_kwargs):
        assert deadline_ns == 900
        assert phase == 'post-cutoff physics time for immediate POLICY Safety tick'
        current_ros['ns'] = 101
        value = predicate()
        assert value == 101
        return value

    io.until = until
    asyncio.run(io.tick_policy_after_deferred_scan_cutoff(
        deadline_ns=900, step_index=7, sample_sequence=42))

    assert adapter.calls == 2
    assert adapter.last_tick_ros_ns == 101
    retry = [facts for name, facts in io.events
        if name == 'POLICY_SAFETY_TICK_RETRIED_AFTER_SCAN_CUTOFF']
    assert retry == [{
        'step_index':7, 'boundary_ns':100, 'crossed_ros_ns':101,
        'tick_before_retry_ros_ns':80, 'tick_after_retry_ros_ns':101,
        'retry_performed':True, 'steady_ns':100,
    }], retry


def test_policy_safety_tick_retries_when_first_defer_is_already_past_boundary():
    io = object.__new__(TrainingWorkerIO)
    io.safety = NS(local_training=None)
    io.events = []
    io.deadline_ns = 1_000
    io.now = lambda: 100
    io.ros_now = lambda: 101
    io.emit = lambda name, facts: io.events.append((name, facts))

    class Adapter:
        def __init__(self):
            self.last_tick_ros_ns = 80
            self._last_deferred_scan_cutoff_ns = None
            self.lock = threading.RLock()
            self.calls = 0

        def tick(self):
            self.calls += 1
            if self.calls == 1:
                # The first steady tick crosses the cutoff and defers, even
                # though the runner's pre-tick ROS sample is already later.
                self._last_deferred_scan_cutoff_ns = 100
                return
            self.last_tick_ros_ns = 101

    adapter = Adapter()
    io.safety.local_training = adapter

    async def until(*_args, **_kwargs):
        raise AssertionError('an already crossed cutoff must retry immediately')

    io.until = until
    asyncio.run(io.tick_policy_after_deferred_scan_cutoff(
        deadline_ns=900, step_index=8, sample_sequence=43))

    assert adapter.calls == 2
    assert adapter.last_tick_ros_ns == 101
    retry = [facts for name, facts in io.events
        if name == 'POLICY_SAFETY_TICK_RETRIED_AFTER_SCAN_CUTOFF']
    assert retry == [{
        'step_index':8, 'boundary_ns':100, 'crossed_ros_ns':101,
        'tick_before_retry_ros_ns':80, 'tick_after_retry_ros_ns':101,
        'retry_performed':True, 'steady_ns':100,
    }], retry


@pytest.mark.parametrize(('phase_ns','expected_remaining_ns','ready'), [
    (10_000_000, 90_000_000, False),
    (40_000_000, 60_000_000, True),
    (60_000_000, 40_000_000, True),
    (80_000_000, 20_000_000, False),
    (0, 0, False),
])
def test_policy_bind_uses_later_measured_scan_window(phase_ns, expected_remaining_ns, ready):
    remaining = policy_bind_launch_window_remaining_ns(2_400_000_000 + phase_ns, 100_000_000)
    assert remaining == expected_remaining_ns
    assert policy_bind_launch_window_ready(remaining) is ready


@pytest.mark.parametrize(('ros_ns','period_ns'), [(-1, 100), (0, 0), (True, 100)])
def test_policy_bind_scan_window_rejects_invalid_clock_inputs(ros_ns, period_ns):
    with pytest.raises(ValueError):
        policy_bind_launch_window_remaining_ns(ros_ns, period_ns)


@pytest.mark.parametrize('trigger_success', [True, False])
def test_reset_l1_bind_dispatches_on_actual_event_before_trigger_ack(trigger_success):
    """Reset binding starts on the observed L1 event, while Trigger ACK stays mandatory."""
    from std_srvs.srv import Trigger
    from mecanum_nav_rl_interfaces.msg import SafetyLifecycleState

    io, clock = worker()
    io.deadline_ns = clock.ns + 1_000_000_000
    io.calls = []
    old = SafetyLifecycleState()
    old.sequence = 4
    io.ingress.lifecycle = old
    next_state = SafetyLifecycleState()
    next_state.sequence = 5
    next_state.episode_generation = 2
    next_state.reset_epoch = 3
    next_state.runtime_generation = 4
    next_state.primary_state = next_state.PRIMARY_ACTIVE
    next_state.barrier_state = next_state.BARRIER_NON_READY
    next_state.motion_permitted = False
    next_state.header.frame_id = 'map'
    next_state.barrier_stamp.sec = 1
    next_state.barrier_stamp.nanosec = 100

    events = []
    io.events = events
    io.trigger_type = Trigger
    trigger_future = None
    pause_count = 0

    class TriggerClient:
        def service_is_ready(self):
            return True

        def call_async(self, _request):
            nonlocal trigger_future
            trigger_future = asyncio.get_running_loop().create_future()
            events.append(('trigger_submitted', clock.now()))
            return trigger_future

    io.reset_client = TriggerClient()
    io.final = NS(publisher_instance_id=61)
    io.policy_source_id = 62
    io.safe_stop_source_id = 63
    io.safety = NS(local_training=NS(safe_stop_sequence=17))

    class Control:
        async def transact(self, operation, *, deadline_ns, **fields):
            assert operation == 6  # OP_BIND_RESET_CONTEXT in the pinned interface.
            assert fields['lifecycle_sequence'] == 5
            assert fields['episode_generation'] == 2
            assert fields['reset_epoch'] == 3
            assert fields['runtime_generation'] == 4
            assert deadline_ns > clock.now()
            events.append(('bind_started', clock.now()))
            await asyncio.sleep(0)
            events.append(('bind_ack', clock.now()))
            return NS(request=NS(request_sequence=18), response_bytes=b'bind-ack')

    io.control = Control()

    async def pause(seconds):
        nonlocal pause_count
        await clock.pause(seconds)
        pause_count += 1
        if pause_count == 2:
            io.ingress.lifecycle = next_state
            events.append(('lifecycle_event', clock.now()))
        if pause_count == 7:
            events.append(('trigger_response', clock.now()))
            trigger_future.set_result(Trigger.Response(success=trigger_success, message='recorded'))

    io.pause = pause
    original_emit = io.emit
    io.emit = lambda name, fields: events.append((name, dict(fields)))

    async def exercise():
        if trigger_success:
            state, ack = await io.reset_lifecycle_and_bind(deadline_ns=io.deadline_ns)
            assert state.sequence == 5
            assert ack.request.request_sequence == 18
        else:
            with pytest.raises(RuntimeError, match='late/negative actual ACK'):
                await io.reset_lifecycle_and_bind(deadline_ns=io.deadline_ns)

    try:
        asyncio.run(asyncio.wait_for(exercise(), timeout=1.0))
    finally:
        io.emit = original_emit

    names = [item[0] for item in events]
    assert names.index('trigger_submitted') < names.index('lifecycle_event')
    assert names.index('lifecycle_event') < names.index('bind_started')
    assert names.index('bind_started') < names.index('trigger_response')
    if trigger_success:
        assert names.index('trigger_response') < names.index('bind_ack') or names.index('bind_ack') < names.index('trigger_response')
        assert 'RESET_L1_EVENT_BIND_CONCURRENT_ACKS' in names
    else:
        assert 'RESET_L1_EVENT_BIND_CONCURRENT_ACKS' not in names


@pytest.mark.parametrize(('case','error','extra'), [
    ('R06a', ValueError('measured XY reset error exceeds 0.01 m'),
        [('B23_R06A_SET_POSE_TARGET_MUTATED', {'actual_target':{'x_m':.25}})]),
    ('R06b', ValueError('standstill measurement has a missing physics iteration'),
        [('B23_R06B_PHYSICS_ITERATION_OMITTED', {'iteration':103,'stamp_ns':1_030_000_000})]),
    ('R06c', TimeoutError('observation0 did not confirm within reset deadline'),
        [('B23_R06C_FAULT_ARMED', {'zero_anchor_sequence':25})]),
])
def test_r06_fault_verifier_requires_real_reason_and_preserves_inhibit(tmp_path, case, error, extra):
    from mecanum_nav_rl_interfaces.msg import LocalTrainingSafetyInput
    from mecanum_nav_rl.runtime_simulation.b23_runner import verify_r06_reset_fault

    root = tmp_path / case
    root.mkdir()
    events = list(extra)
    if case == 'R06c':
        events.append(('B1_RESET_STARTED', {'cutoff_pending':True}))
    io = NS(events=events, descriptor={'run_root':str(root)},
        ingress=NS(admission_state=LocalTrainingSafetyInput.ADMISSION_INHIBITED,
            last_published_admission_state=LocalTrainingSafetyInput.ADMISSION_INHIBITED,
            backend_state=NS(local_zero_override=True)),
        safety=NS(local_training=NS(policy_hold=True)),
        _r06c_held_receipts=[{'final_publish_sequence':26,'wire_sha256':'a'*64}],
        _r06c_reset_deadline_ns=15_000_000_000)
    outcome = verify_r06_reset_fault(io, case=case, error=error,
        anchor_sequence=25 if case == 'R06c' else None)
    assert outcome['expected_rejection'] is True, outcome
    assert outcome['no_observation0_commit'] is True, outcome
    assert outcome['no_policy_issuance'] is True, outcome
    assert outcome['policy_inhibited'] is True, outcome
