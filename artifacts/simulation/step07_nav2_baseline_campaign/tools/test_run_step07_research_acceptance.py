from __future__ import annotations

import json
import io
import math
from pathlib import Path
import signal
import sys
import threading
import time
from types import ModuleType
from types import SimpleNamespace

import pytest
import run_step07_research_acceptance as runner_module  # noqa: I201
from run_step07_research_acceptance import (
    AcceptanceFailure, atomic_json, CampaignState, CAPTURE_TOPICS, load_json,
    OwnedProcess, ProcessOwner, REQUIRED_NAV2_LIFECYCLE_NODES,
    REQUIRED_RECORDER_TOPICS, ResearchAcceptanceRunner,
    validate_resolved_config, verify_runtime_authorization,
)


def test_production_qos_graph_admission_rejects_known_mismatch_and_ignores_unknown():
    graph = {"topics": {"/scan": {
        "publishers": (("bridge", "/", "sensor_msgs/msg/LaserScan", 2, 2, 5),),
        "subscriptions": (("observer", "/", "sensor_msgs/msg/LaserScan", 1, 2, 5),),
    }}}
    assert ResearchAcceptanceRunner._known_qos_mismatches(graph) == ("/scan",)
    graph["topics"]["/scan"]["publishers"] = (
        ("bridge", "/", "sensor_msgs/msg/LaserScan", 3, 3, 0),)
    assert ResearchAcceptanceRunner._known_qos_mismatches(graph) == ()


def test_duplicate_json_keys_and_nonfinite_constants_reject(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"a":1,"a":2}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_json(path)
    path.write_text('{"x":NaN}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_json(path)


def test_atomic_report_write_requires_finite_json_and_replaces_complete_file(tmp_path):
    path = tmp_path / "report.json"
    atomic_json(path, {"a": [1, 2]})
    assert json.loads(path.read_text()) == {"a": [1, 2]}
    with pytest.raises(ValueError):
        atomic_json(path, {"bad": float("nan")})
    assert json.loads(path.read_text()) == {"a": [1, 2]}


def test_authorization_must_match_exact_commit_hash_run_and_output(tmp_path):
    output = tmp_path / "run-1"
    auth = tmp_path / "auth.json"
    auth.write_text(json.dumps({"owner_authorized": True, "sim_estop_release_authorized": True, "exact_git_commit": "c"*40,
        "config_hash": "f"*64, "run_id": "run-1", "output_target": str(output)}))
    assert verify_runtime_authorization(auth, commit="c"*40, config_hash="f"*64,
                                        run_id="run-1", output_target=output)["owner_authorized"]
    with pytest.raises(AcceptanceFailure, match="BINDING_MISMATCH"):
        verify_runtime_authorization(auth, commit="d"*40, config_hash="f"*64,
                                    run_id="run-1", output_target=output)
    auth.write_text(json.dumps({"owner_authorized": True, "sim_estop_release_authorized": False,
        "exact_git_commit": "c"*40, "config_hash": "f"*64,
        "run_id": "run-1", "output_target": str(output)}))
    with pytest.raises(AcceptanceFailure, match="SIM_ESTOP_RELEASE_AUTHORIZATION_REQUIRED"):
        verify_runtime_authorization(auth, commit="c"*40, config_hash="f"*64,
                                    run_id="run-1", output_target=output)


def test_runner_rejects_declared_config_hash_mismatch():
    repository = Path(__file__).parents[4]
    config_path = repository / "ros2_ws/src/mecanum_nav_rl/config/v3/resolved/sim_eval_nav2_baseline.resolved.json"
    document = json.loads(config_path.read_text(encoding="utf-8"))
    document["provenance"]["config_hash"] = "0" * 64
    with pytest.raises(ValueError, match="declared config_hash"):
        validate_resolved_config(document)


def test_failed_acceptance_sets_primary_failure_and_unmeasured_metric_is_null():
    runner = object.__new__(ResearchAcceptanceRunner)
    runner.state = CampaignState(stage="A9_NAVIGATION_OUTCOME",
        facts={"A9": {"pass": False, "reason": "NAVIGATION_DEADLINE_OR_NO_RESULT"}})
    runner.output = None
    report = runner.evaluate_and_write()
    assert report["overall"] == "FAIL"
    assert runner.state.primary_failure["primary_failure"] == "NAVIGATION_DEADLINE_OR_NO_RESULT"
    assert runner.state.metrics.get("safety_interventions") is None


def test_cleanup_is_separate_from_functional_verdict_and_only_signals_owned_groups(monkeypatch):
    class FakeProcess:
        pid = 987654
        returncode = None
        def wait(self, timeout=None): self.returncode = 0; return 0
        def poll(self): return self.returncode

    sent = []
    members = [(987654, "S")]
    monkeypatch.setattr("run_step07_research_acceptance.subprocess.Popen",
                        lambda *a, **k: FakeProcess())
    monkeypatch.setattr("run_step07_research_acceptance.os.killpg",
                        lambda pid, sig: sent.append((pid, sig)))
    monkeypatch.setattr("run_step07_research_acceptance.os.getpgid", lambda pid: pid)
    monkeypatch.setattr(ProcessOwner, "_group_members", staticmethod(lambda pgid: tuple(members)))
    def send(pid, sig):
        sent.append((pid, sig))
        members.clear()
    owner = ProcessOwner()
    import io, time
    owned = owner.start("composite", ["fake-runtime"], env={}, runtime_log=io.BytesIO(), cwd=Path.cwd())
    members[:] = [(owned.pgid, "S")]
    monkeypatch.setattr("run_step07_research_acceptance.os.killpg", send)
    cleanup = owner.stop_all(("composite",))
    state = CampaignState(facts={"A9": {"pass": False}})
    assert cleanup[0]["stopped"] is True
    assert sent == [(987654, signal.SIGINT)]
    assert state.facts["A9"]["pass"] is False


def test_process_group_cleanup_detects_child_after_leader_exit_and_zombie(monkeypatch):
    class FakeProcess:
        pid = 12345
        def poll(self): return 0
        def wait(self, timeout=None): return 0
    members = [(23456, "S")]
    clear_on_signal = True
    monkeypatch.setattr(ProcessOwner, "_group_members", staticmethod(lambda pgid: tuple(members)))
    sent = []
    def send(pid, sig):
        sent.append((pid, sig))
        if sig == signal.SIGINT and clear_on_signal:
            members.clear()
    monkeypatch.setattr("run_step07_research_acceptance.os.killpg", send)
    import io
    owned = __import__("run_step07_research_acceptance").OwnedProcess(
        "composite", FakeProcess(), time.monotonic(), io.BytesIO(), 12345)
    result = ProcessOwner().stop_one(owned, grace_s=0.1)
    assert result["stopped"] and sent == [(12345, signal.SIGINT)]
    members[:] = [(23456, "Z")]
    clear_on_signal = False
    owned = __import__("run_step07_research_acceptance").OwnedProcess(
        "composite", FakeProcess(), time.monotonic(), io.BytesIO(), 12345)
    zombie = ProcessOwner().stop_one(owned, grace_s=0.01)
    assert zombie["sigint_timeout"] and zombie["group_members"] == [(23456, "Z")]


def test_cleanup_reaps_exited_launcher_before_deciding_group_is_empty(
    monkeypatch,
):
    """Reap a direct child before treating its process group as empty."""
    members = [(12345, 'Z')]

    class FakeProcess:
        pid = 12345

        def poll(self):
            members.clear()
            return 0

        def wait(self, timeout=None):
            self.waited = True
            return 0

    import io
    process = FakeProcess()
    process.waited = False

    def group_members(pgid):
        return tuple(members)

    monkeypatch.setattr(
        ProcessOwner, '_group_members', staticmethod(group_members)
    )
    owned = OwnedProcess(
        'composite', process, time.monotonic(), io.BytesIO(), 12345
    )
    result = ProcessOwner().stop_one(owned)
    assert result['stopped'] is True and result['returncode'] == 0
    assert process.waited is True


def test_procfs_race_is_ignored_but_permission_error_is_unknown(monkeypatch):
    """Ignore an exited PID while preserving real procfs inspection errors."""
    import run_step07_research_acceptance as runner_module

    class Entry:
        def __init__(self, name, raw=None, error=None):
            self.name, self.raw, self.error = name, raw, error

        def __truediv__(self, value):
            return self

        def read_text(self, encoding):
            if self.error:
                raise self.error
            return self.raw

    class Proc:
        def is_dir(self): return True

        def iterdir(self):
            return iter((
                Entry('110', error=FileNotFoundError()),
                Entry('111', '111 (owned child) S 1 77 0'),
            ))

    monkeypatch.setattr(runner_module, 'Path', lambda _: Proc())
    assert ProcessOwner._group_members(77) == ((111, 'S'),)

    class DeniedProc(Proc):
        def iterdir(self):
            return iter((Entry('112', error=PermissionError()),))

    monkeypatch.setattr(runner_module, 'Path', lambda _: DeniedProc())
    assert ProcessOwner._group_members(77) is None


def test_group_inspection_failure_does_not_block_next_cleanup(monkeypatch):
    """Continue cleanup of the second owned group after the first fails."""
    class FakeProcess:
        def __init__(self, pid):
            self.pid, self.returncode = pid, None

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            self.returncode = 0
            return 0

    groups = {101: None, 202: ((202, 'S'),)}
    sent = []

    def members(pgid): return groups[pgid]

    def send(pgid, sig):
        sent.append((pgid, sig))
        groups[pgid] = ()

    monkeypatch.setattr(ProcessOwner, '_group_members', staticmethod(members))
    monkeypatch.setattr('run_step07_research_acceptance.os.killpg', send)
    import io
    owner = ProcessOwner()
    owner.processes.extend((
        OwnedProcess(
            'bad', FakeProcess(101), time.monotonic(), io.BytesIO(), 101
        ),
        OwnedProcess(
            'good', FakeProcess(202), time.monotonic(), io.BytesIO(), 202
        ),
    ))
    results = owner.stop_all(('bad', 'good'), grace_s=0.02)
    assert (
        results[0]['group_inspection_error']
        == 'OWNED_PROCESS_GROUP_STATUS_UNKNOWN'
    )
    assert results[1]['stopped'] is True
    assert sent == [(202, signal.SIGINT)]


def test_sigkill_containment_fails_a10_without_finalized_capture(monkeypatch):
    """Mark containment as cleanup failure if capture was not finalized."""
    class FakeProcess:
        pid = 303
        returncode = None

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            self.returncode = 0
            return 0

    process = FakeProcess()
    members = [(303, 'S')]
    sent = []

    def send(pgid, sig):
        sent.append((pgid, sig))
        if sig == signal.SIGKILL:
            members.clear()
            process.returncode = 0

    def group_members(pgid):
        return tuple(members)

    monkeypatch.setattr(
        ProcessOwner, '_group_members', staticmethod(group_members)
    )
    monkeypatch.setattr('run_step07_research_acceptance.os.killpg', send)
    import io
    owner = ProcessOwner()
    owned = OwnedProcess(
        'recorder', process, time.monotonic(), io.BytesIO(), 303
    )
    owner.processes.append(owned)
    result = owner.stop_all(
        ('recorder',), grace_s=0.01, capture_finalized=lambda: False
    )
    assert sent == [(303, signal.SIGINT), (303, signal.SIGKILL)]
    assert (
        result[0]['sigkill_required'] is True
        and result[0]['stopped'] is True
    )


def test_sigterm_fallback_waits_for_capture_finalize_and_records_escalation(monkeypatch):
    class FakeProcess:
        pid = 56789
        returncode = None
        def poll(self): return self.returncode
        def wait(self, timeout=None): self.returncode = 0; return 0
    members = [(56789, "S")]
    monkeypatch.setattr(ProcessOwner, "_group_members", staticmethod(lambda pgid: tuple(members)))
    sent = []
    def send(pid, sig):
        sent.append((pid, sig))
        if sig == signal.SIGTERM:
            members.clear()
    monkeypatch.setattr("run_step07_research_acceptance.os.killpg", send)
    import io
    owner = ProcessOwner()
    owned = OwnedProcess("recorder", FakeProcess(), time.monotonic(), io.BytesIO(), 56789)
    owner.processes.append(owned)
    result = owner.stop_all(("recorder",), grace_s=0.01, capture_finalized=lambda: True)
    assert sent == [(56789, signal.SIGINT), (56789, signal.SIGTERM)]
    assert result[0]["sigterm_escalated_after_finalize"] is True
    assert result[0]["stopped"] is True


def test_runner_requires_preflight_before_process_start_and_capacity_one_output(tmp_path):
    # Production preflight uses repository identity/config; this unit check
    # exercises the actual guard at the production child-start method.
    runner = object.__new__(ResearchAcceptanceRunner)
    runner.output = None
    with pytest.raises(RuntimeError, match="preflight"):
        runner.start_runtime_children()


def test_no_estop_release_grant_rejects_before_starting_any_runtime_child(tmp_path):
    class Owner:
        def __init__(self): self.started = []
        def start(self, *args, **kwargs): self.started.append(args[0])
    runner = object.__new__(ResearchAcceptanceRunner)
    runner.output = tmp_path / "output"
    runner.authorization = {"owner_authorized": True, "sim_estop_release_authorized": False}
    runner.process_owner = Owner()
    with pytest.raises(AcceptanceFailure, match="SIM_ESTOP_RELEASE_AUTHORIZATION_REQUIRED"):
        runner.start_runtime_children()
    assert runner.process_owner.started == []


def test_authorized_estop_release_is_forwarded_to_composite_launch(tmp_path, monkeypatch):
    import io
    class Owner:
        def __init__(self): self.started = []
        def start(self, name, command, **kwargs): self.started.append((name, command))
    runner = object.__new__(ResearchAcceptanceRunner)
    runner.output = tmp_path
    runner.authorization = {"sim_estop_release_authorized": True}
    runner.process_owner = Owner()
    runner.partition = "offline-test"
    runner.fuel_cache_root = tmp_path
    runner.repository = tmp_path
    runner.map_root = tmp_path
    runner.log_stream = io.BytesIO()
    runner._launch = ResearchAcceptanceRunner._launch.__get__(runner)
    monkeypatch.setenv("ROS_DOMAIN_ID", "17")
    runner.start_runtime_children()
    composite = next(command for name, command in runner.process_owner.started if name == "composite")
    assert "sim_estop_release_authorized:=true" in composite
    recorder = next(command for name, command in runner.process_owner.started if name == "recorder")
    assert "--include-hidden-topics" in recorder
    assert '--include-unpublished-topics' in recorder
    assert '/navigate_to_pose/_action/status' in recorder
    assert '/navigate_to_pose/_action/feedback' in recorder
    for topic in REQUIRED_RECORDER_TOPICS:
        assert topic in recorder
    assert '/initialpose' in CAPTURE_TOPICS
    assert '/initialpose' not in REQUIRED_RECORDER_TOPICS
    assert '/navigate_to_pose/_action/status' not in REQUIRED_RECORDER_TOPICS
    assert '/mecanum/nav2_candidate_cmd' in REQUIRED_RECORDER_TOPICS
    assert '/cmd_vel' in REQUIRED_RECORDER_TOPICS
    assert '/mecanum/final_issued_command' in REQUIRED_RECORDER_TOPICS


def test_recorder_readiness_uses_only_explicit_pre_goal_topics_and_checks_processes():
    calls = []

    class Observer:
        def recording_ready(self, topics):
            calls.append(tuple(topics))
            return False, ('/map',)

    runner = object.__new__(ResearchAcceptanceRunner)
    runner.observer = Observer()
    runner.state = CampaignState(stage='RECORDER')
    runner.process_owner = SimpleNamespace(processes=[])
    runner.log_stream = None
    assert runner._graph_ready_for_recording() is False
    assert calls == [REQUIRED_RECORDER_TOPICS]
    assert '/initialpose' not in calls[0]
    assert '/navigate_to_pose/_action/status' not in calls[0]

    class Exited:
        name = 'recorder'
        process = SimpleNamespace(poll=lambda: 0)

    runner.process_owner.processes = [Exited()]
    with pytest.raises(AcceptanceFailure) as error:
        runner._graph_ready_for_recording()
    assert error.value.stage == 'RECORDER'
    assert error.value.component == 'recorder'
    assert 'OWNED_LAUNCH_EXITED' in error.value.reason
    assert len(calls) == 1


def test_execute_checks_upstream_before_recorder_and_never_missions_after_failure():
    runner = object.__new__(ResearchAcceptanceRunner)
    runner.state = CampaignState()
    runner.started_steady = time.monotonic()
    runner.now_steady = time.monotonic
    now_ns = time.monotonic_ns()
    odom_value = SimpleNamespace(
        header=SimpleNamespace(frame_id='odom'), child_frame_id='base_link',
        pose=SimpleNamespace(pose=SimpleNamespace(position=SimpleNamespace(x=0.0, y=0.0)),
                             covariance=[0.0] * 36),
        twist=SimpleNamespace(twist=SimpleNamespace(
            linear=SimpleNamespace(x=0.0, y=0.0), angular=SimpleNamespace(z=0.0)),
            covariance=[0.0] * 36),
    )
    runner.observer = SimpleNamespace(
        executor_error=None, clock_ns=100, clock_advance_count=2,
        scans=[SimpleNamespace(received_steady_ns=now_ns, frame_id='lidar_frame')],
        wheel=[SimpleNamespace(received_steady_ns=now_ns, value=SimpleNamespace(
            header=SimpleNamespace(frame_id='odom'), child_frame_id='base_link'))],
        imu=[SimpleNamespace(received_steady_ns=now_ns)],
        odometry=[SimpleNamespace(stamp_ns=1, value=odom_value),
                  SimpleNamespace(stamp_ns=2, value=odom_value)],
        graph_snapshot=lambda: {
            'topics': {'/odometry/filtered': {'publishers': (('ekf_filter_node',),)}},
            'nodes': {'map_server', 'planner_server', 'controller_server',
                      'behavior_server', 'bt_navigator'},
        },
    )
    runner.output = None
    runner.log_stream = None
    runner.process_owner = SimpleNamespace(processes=[])
    calls = []

    runner.start_observer = lambda: calls.append('observer')
    runner.start_runtime_children = lambda: calls.append('children')
    runner._a1_asset_check = lambda: {'pass': True, 'measured': {}}
    runner._topic_samples_ready = lambda: calls.append('upstream') or True
    runner._last_sensor_health_success = {
        'snapshot': {'clock_advance_count': 2,
                     'odometry': tuple(runner.observer.odometry)},
        'ros_now_ns': 100, 'steady_now_ns': now_ns,
        'facts': {'scan': runner.observer.scans[0],
                  'wheel_odometry': runner.observer.wheel[0],
                  'imu': runner.observer.imu[0],
                  'filtered_odometry': runner.observer.odometry[-1]},
    }
    runner._localization_ok = lambda: (True, None)
    runner._graph_ready_for_recording = lambda: calls.append('recorder') or True
    runner._mission = lambda: calls.append('mission')
    runner.shutdown = lambda: calls.append('shutdown')

    report = runner.execute()
    assert calls == ['observer', 'children', 'upstream', 'shutdown']
    assert report['overall'] == 'FAIL'
    assert runner.state.primary_failure['stage'] == 'A6_NAV2'
    assert runner.state.primary_failure['component'] == 'amcl'
    assert runner.state.primary_failure['primary_failure'].startswith(
        'NAV2_LIFECYCLE_CLIENT_SET_INVALID:'
    )


def test_execute_runs_mission_only_after_upstream_and_required_recorder_ready():
    runner = object.__new__(ResearchAcceptanceRunner)
    runner.state = CampaignState()
    runner.started_steady = time.monotonic()
    runner.now_steady = time.monotonic
    runner.observer = None
    runner.output = None
    runner.log_stream = None
    calls = []

    def append_call(name):
        def callback():
            calls.append(name)
        return callback

    runner.start_observer = append_call('observer')
    runner.start_runtime_children = append_call('children')
    runner._wait_ready = append_call('upstream')

    def recorder_ready():
        calls.append('recorder')
        return True

    runner._graph_ready_for_recording = recorder_ready
    runner._mission = append_call('mission')
    runner.shutdown = append_call('shutdown')

    runner.execute()
    assert calls == ['observer', 'children', 'upstream', 'recorder', 'mission', 'shutdown']


def _fake_clock_execute_runner(monkeypatch, upstream_time, recorder_ready):
    import run_step07_research_acceptance as runner_module

    class FakeClock:
        def __init__(self):
            self.value = 0.0

        def __call__(self):
            return self.value

    clock = FakeClock()
    calls = []
    monkeypatch.setattr(runner_module.time, 'sleep', lambda _seconds: None)
    runner = object.__new__(ResearchAcceptanceRunner)
    runner.state = CampaignState()
    runner.started_steady = 0.0
    runner.now_steady = clock
    runner.observer = None
    runner.output = None
    runner.log_stream = None

    def start_observer():
        calls.append('observer')

    def start_children():
        calls.append('children')

    def wait_upstream():
        calls.append('upstream')
        clock.value = upstream_time

    def mission():
        calls.append('mission')

    def shutdown():
        calls.append('shutdown')

    def report():
        return {'overall': 'FAKE_OFFLINE_EXECUTE'}

    runner.start_observer = start_observer
    runner.start_runtime_children = start_children
    runner._wait_ready = wait_upstream
    runner._graph_ready_for_recording = recorder_ready(clock, calls)
    runner._mission = mission
    runner.shutdown = shutdown
    runner.evaluate_and_write = report
    return runner, clock, calls


def test_recorder_stage_gets_sixty_seconds_after_late_startup(monkeypatch):
    checks = []

    def recorder_ready(clock, calls):
        def check():
            checks.append(clock.value)
            if len(checks) == 1:
                clock.value = 91.0
                return False
            clock.value = 92.0
            return True
        return check

    runner, clock, calls = _fake_clock_execute_runner(
        monkeypatch, upstream_time=90.0, recorder_ready=recorder_ready)
    runner.execute()
    assert checks == [90.0, 91.0]
    assert clock.value == 92.0
    assert 'mission' in calls
    assert runner.state.primary_failure is None


def test_recorder_stage_times_out_after_its_full_sixty_second_budget(monkeypatch):
    checks = []

    def recorder_ready(clock, _calls):
        def check():
            checks.append(clock.value)
            clock.value += 1.0
            return False
        return check

    runner, clock, calls = _fake_clock_execute_runner(
        monkeypatch, upstream_time=90.0, recorder_ready=recorder_ready)
    report = runner.execute()
    assert len(checks) == 60
    assert clock.value == 150.0
    assert 'mission' not in calls
    assert report['overall'] == 'FAKE_OFFLINE_EXECUTE'
    assert runner.state.primary_failure['stage'] == 'RECORDER'
    assert runner.state.primary_failure['component'] == 'recorder'
    assert runner.state.primary_failure['primary_failure'] == 'RECORDER_SUBSCRIPTIONS_NOT_READY'


def test_recorder_deadline_is_capped_at_campaign_shutdown_reserve(monkeypatch):
    checks = []

    def recorder_ready(clock, _calls):
        def check():
            checks.append(clock.value)
            clock.value += 1.0
            return False
        return check

    runner, clock, calls = _fake_clock_execute_runner(
        monkeypatch, upstream_time=455.0, recorder_ready=recorder_ready)
    runner.execute()
    assert checks == [455.0, 456.0, 457.0, 458.0, 459.0]
    assert clock.value == 460.0
    assert 'mission' not in calls
    assert runner.state.primary_failure['stage'] == 'RECORDER'


def test_expired_recorder_work_deadline_rejects_even_if_ready(monkeypatch):
    checks = []

    def recorder_ready(_clock, _calls):
        def check():
            checks.append(True)
            return True
        return check

    runner, clock, calls = _fake_clock_execute_runner(
        monkeypatch, upstream_time=460.0, recorder_ready=recorder_ready)
    runner.execute()
    assert clock.value == 460.0
    assert checks == []
    assert 'mission' not in calls
    assert runner.state.primary_failure['stage'] == 'RECORDER'
    assert runner.state.primary_failure['component'] == 'recorder'
    assert runner.state.primary_failure['primary_failure'] == 'RECORDER_STAGE_DEADLINE_EXPIRED'


def test_recorder_exit_or_missing_required_subscription_fails_before_mission(monkeypatch):
    class Process:
        def __init__(self, returncode):
            self.returncode = returncode

        def poll(self):
            return self.returncode

    class Clock:
        value = 60.0

        def __call__(self):
            return self.value

    clock = Clock()

    def advance_to_deadline(_seconds):
        clock.value += 60.0

    monkeypatch.setattr('run_step07_research_acceptance.time.sleep', advance_to_deadline)

    for failure in ('exited', 'missing_subscription'):
        runner = object.__new__(ResearchAcceptanceRunner)
        runner.state = CampaignState()
        runner.started_steady = 0.0
        runner.now_steady = clock
        runner.observer = SimpleNamespace(recording_ready=lambda _topics: (False, ('/map',)))
        runner.process_owner = SimpleNamespace(processes=[])
        runner.output = None
        runner.log_stream = None
        calls = []

        def append_call(name):
            def callback():
                calls.append(name)
            return callback

        runner.start_observer = append_call('observer')
        runner.start_runtime_children = append_call('children')
        runner._wait_ready = append_call('upstream')
        runner._mission = append_call('mission')
        runner.shutdown = append_call('shutdown')
        if failure == 'exited':
            runner.process_owner.processes = [
                SimpleNamespace(name='recorder', process=Process(1))]

        report = runner.execute()
        assert 'mission' not in calls
        assert report['overall'] == 'FAIL'
        assert runner.state.primary_failure['stage'] == 'RECORDER'
        if failure == 'exited':
            assert runner.state.primary_failure['component'] == 'recorder'
            assert 'OWNED_LAUNCH_EXITED' in runner.state.primary_failure['primary_failure']
        else:
            assert runner.state.primary_failure['component'] == 'recorder'
            assert (
                runner.state.primary_failure['primary_failure']
                == 'RECORDER_SUBSCRIPTIONS_NOT_READY'
            )


def test_owned_startup_process_exit_is_reported_before_recorder_gate():
    runner = object.__new__(ResearchAcceptanceRunner)
    runner.state = CampaignState(stage='STARTUP')
    runner.process_owner = SimpleNamespace(processes=[SimpleNamespace(
        name='composite', process=SimpleNamespace(poll=lambda: 23))])
    runner.observer = SimpleNamespace()

    with pytest.raises(AcceptanceFailure) as error:
        runner._topic_samples_ready()
    assert error.value.stage == 'STARTUP'
    assert error.value.component == 'composite'
    assert 'OWNED_LAUNCH_EXITED:23' == error.value.reason


def test_startup_rearm_requests_once_and_waits_for_fresh_ready_lifecycle():
    from mecanum_nav_rl.observations.step07_research_acceptance import Context, StampedFact
    context = Context(1, 2, 3, "a" * 64)
    now = time.monotonic_ns()
    life = StampedFact(100, now, "base_link", {"primary_state": 2,
        "barrier_state": 1, "motion_permitted": True}, context)
    class Future:
        def done(self): return True
        def exception(self): return None
        def result(self): return SimpleNamespace(success=True)
    class Observer:
        def __init__(self): self.calls = 0
        def request_rearm(self): self.calls += 1; return Future()
    observer = Observer()
    runner = object.__new__(ResearchAcceptanceRunner)
    runner.authorization = {"sim_estop_release_authorized": True}
    runner.rearm_requested = False
    runner.observer = SimpleNamespace(request_rearm=observer.request_rearm,
        lifecycle=life, context=context, clock_ns=100)
    _bind_health_snapshot(
        runner.observer, context=context, ros_now_ns=100,
        lifecycle=life, odometry=(),
    )
    runner.now_steady = time.monotonic
    runner.state = CampaignState()
    runner._startup_rearm(time.monotonic() + 1.0)
    assert observer.calls == 1 and runner._lifecycle_ready()
    with pytest.raises(AcceptanceFailure, match="STARTUP_REARM_ALREADY_REQUESTED"):
        runner._startup_rearm(time.monotonic() + 1.0)


def test_startup_rearm_refusal_and_missing_authorization_fail_closed():
    class Future:
        def done(self): return True
        def exception(self): return None
        def result(self): return SimpleNamespace(success=False)
    calls = []
    runner = object.__new__(ResearchAcceptanceRunner)
    runner.authorization = {"sim_estop_release_authorized": True}
    runner.rearm_requested = False
    runner.observer = SimpleNamespace(request_rearm=lambda: calls.append("rearm") or Future())
    runner.now_steady = time.monotonic
    with pytest.raises(AcceptanceFailure, match="SAFETY_REARM_REFUSED"):
        runner._startup_rearm(time.monotonic() + 1.0)
    assert calls == ["rearm"]
    runner.authorization = {"sim_estop_release_authorized": False}
    runner.rearm_requested = False
    with pytest.raises(AcceptanceFailure, match="SIM_ESTOP_RELEASE_AUTHORIZATION_REQUIRED"):
        runner._startup_rearm(time.monotonic() + 1.0)
    assert calls == ["rearm"]


def _tf_graph_fixture(graph=None, *, observed_edges=None):
    runner = object.__new__(ResearchAcceptanceRunner)
    runner.tf_configured_ownership = {
        'configured_owners': {
            'map->odom': {'node_name': 'amcl', 'node_namespace': '/'},
            'odom->base_link': {
                'node_name': 'ekf_filter_node', 'node_namespace': '/'},
            'base_link->lidar_frame': {
                'node_name': 'robot_state_publisher', 'node_namespace': '/'},
        },
        'dynamic_joint_names': ['Wheel_LF_Joint'],
    }
    runner._last_tf_a4_evidence = {}
    runner.observer = SimpleNamespace(
        tf_observed_edges=set(
            observed_edges if observed_edges is not None else {
                ('map', 'odom'), ('odom', 'base_link'),
                ('base_link', 'lidar_frame'),
            }),
        tf_publisher_graph=lambda: (
            graph if graph is not None else _complete_tf_graph()),
        lookup_transform=lambda target, source, stamp: (target, source, stamp),
        executor_error=None,
    )
    return runner


def _endpoint(name, namespace='/', topic_type='tf2_msgs/msg/TFMessage'):
    return {
        'node_name': name,
        'node_namespace': namespace,
        'topic_type': topic_type,
    }


def _complete_tf_graph():
    return {
        '/tf': [_endpoint('amcl'), _endpoint('ekf_filter_node')],
        '/tf_static': [_endpoint('robot_state_publisher')],
    }


def _undiscovered_endpoint():
    return {
        'node_name': '_NODE_NAME_UNKNOWN_',
        'node_namespace': '_NODE_NAMESPACE_UNKNOWN_',
        'topic_type': 'tf2_msgs/msg/TFMessage',
    }


def test_tf_graph_edges_and_exact_time_lookup_form_a4_evidence():
    """Verify tf graph edges and exact time lookup form a4 evidence."""
    runner = _tf_graph_fixture()
    assert runner._tf_a4_ready(123456)
    measured = runner._last_tf_a4_evidence
    assert measured['configured_ownership']['map->odom']['node_name'] == 'amcl'
    assert (measured['observed_publisher_graph']['/tf']
            == _complete_tf_graph()['/tf'])
    assert set(measured['observed_edges']) == {
        'map->odom', 'odom->base_link', 'base_link->lidar_frame'}
    assert measured['exact_time_lookup']['stamp_ns'] == 123456
    assert (measured['per_message_publisher_attribution']
            == 'NOT_PROVIDED_BY_RCLPY_CALLBACK_API')


def test_tf_static_edge_before_graph_discovery_can_resolve_without_new_message(
        monkeypatch):
    """Verify late graph discovery resolves an earlier static edge."""
    clock = [0.0]
    monkeypatch.setattr(
        runner_module.time, 'sleep',
        lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    graph = {'/tf': [], '/tf_static': []}
    runner = _tf_graph_fixture(graph=graph)
    runner.observer.tf_observed_edges = {('base_link', 'lidar_frame')}

    def discover():
        if clock[0] >= 0.2:
            graph.update(_complete_tf_graph())
        return graph
    runner.observer.tf_publisher_graph = discover
    edge_messages = [1]
    assert runner.observer.tf_observed_edges == {('base_link', 'lidar_frame')}
    runner.observer.tf_observed_edges.update(
        {('map', 'odom'), ('odom', 'base_link')})
    runner.started_steady = 0.0
    runner.now_steady = lambda: clock[0]
    runner._wait_for(
        runner._tf_ownership_ready, 1.0, stage='A4_TF',
        component='tf_publishers', reason='TF_GRAPH_UNRESOLVED')
    assert clock[0] >= 0.2
    assert edge_messages == [1]
    assert runner._tf_ownership_ready()


@pytest.mark.parametrize('mutation,reason', [
    ('foreign', 'TF_PUBLISHER_TOPOLOGY_MISMATCH'),
    ('duplicate', 'TF_PUBLISHER_DUPLICATE_ENDPOINT'),
    ('wrong_namespace', 'TF_PUBLISHER_TOPOLOGY_MISMATCH'),
    ('wrong_type', 'TF_PUBLISHER_TYPE_MISMATCH'),
])
def test_tf_graph_rejects_foreign_duplicate_namespace_and_type(
        mutation, reason):
    """Verify tf graph rejects foreign duplicate namespace and type."""
    graph = _complete_tf_graph()
    if mutation == 'foreign':
        graph['/tf'].append(_endpoint('other_localizer'))
    elif mutation == 'duplicate':
        graph['/tf'].append(_endpoint('amcl'))
    elif mutation == 'wrong_namespace':
        graph['/tf'][0] = _endpoint('amcl', '/robot')
    else:
        graph['/tf'][0] = _endpoint(
            'amcl', topic_type='geometry_msgs/msg/TransformStamped')
    runner = _tf_graph_fixture(graph=graph)
    with pytest.raises(AcceptanceFailure, match=reason):
        runner._tf_ownership_ready()


def test_jazzy_discovery_sentinel_waits_then_resolves_to_expected_endpoint(
        monkeypatch):
    """Wait for an undiscovered Jazzy endpoint to resolve."""
    clock = [0.0]
    monkeypatch.setattr(
        runner_module.time, 'sleep',
        lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    graph = _complete_tf_graph()
    graph['/tf'].append(_undiscovered_endpoint())
    runner = _tf_graph_fixture(graph=graph)
    runner.started_steady = 0.0
    runner.now_steady = lambda: clock[0]
    assert runner._tf_graph_evidence()[0] is False

    def current_graph():
        if clock[0] >= 0.2:
            graph['/tf'][-1] = _endpoint('robot_state_publisher')
        return graph

    runner.observer.tf_publisher_graph = current_graph
    runner._wait_for(
        lambda: runner._tf_a4_ready(123456), 1.0,
        stage='A4_TF', component='tf_publishers',
        reason='TF_GRAPH_UNRESOLVED')
    assert clock[0] >= 0.2
    assert (runner._last_tf_a4_evidence['observed_publisher_graph']['/tf'][-1]
            ['node_name'] == 'robot_state_publisher')


def test_jazzy_sentinel_remaining_to_deadline_fails_readiness(monkeypatch):
    """Fail readiness when the graph sentinel never resolves."""
    clock = [0.0]
    monkeypatch.setattr(
        runner_module.time, 'sleep',
        lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    graph = _complete_tf_graph()
    graph['/tf'].append(_undiscovered_endpoint())
    runner = _tf_graph_fixture(graph=graph)
    runner.started_steady = 0.0
    runner.now_steady = lambda: clock[0]
    with pytest.raises(AcceptanceFailure, match='TF_GRAPH_UNRESOLVED'):
        runner._wait_for(
            lambda: runner._tf_a4_ready(123456), 0.25, stage='A4_TF',
            component='tf_publishers', reason='TF_GRAPH_UNRESOLVED')
    assert clock[0] >= 0.25


def test_expected_publishers_plus_unresolved_endpoint_remain_pending():
    """Keep expected publishers pending while any endpoint is unresolved."""
    graph = _complete_tf_graph()
    graph['/tf_static'].append(_undiscovered_endpoint())
    runner = _tf_graph_fixture(graph=graph)
    ready, measured = runner._tf_graph_evidence()
    assert ready is False
    assert len(measured['/tf_static']) == 1


def test_unresolved_endpoint_resolving_as_foreign_fails_immediately(
        monkeypatch):
    """Reject an endpoint when discovery resolves to a foreign node."""
    clock = [0.0]
    monkeypatch.setattr(
        runner_module.time, 'sleep',
        lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    graph = _complete_tf_graph()
    graph['/tf'].append(_undiscovered_endpoint())
    runner = _tf_graph_fixture(graph=graph)
    runner.started_steady = 0.0
    runner.now_steady = lambda: clock[0]

    def current_graph():
        if clock[0] >= 0.2:
            graph['/tf'][-1] = _endpoint('foreign_localizer')
        return graph

    runner.observer.tf_publisher_graph = current_graph
    with pytest.raises(
            AcceptanceFailure, match='TF_PUBLISHER_TOPOLOGY_MISMATCH'):
        runner._wait_for(
            lambda: runner._tf_a4_ready(123456), 1.0, stage='A4_TF',
            component='tf_publishers', reason='TF_GRAPH_UNRESOLVED')
    assert clock[0] >= 0.2


def test_multiple_undiscovered_endpoints_wait_without_false_duplicate():
    """Keep discovery sentinels pending without false duplicate failure."""
    graph = _complete_tf_graph()
    graph['/tf'].extend([_undiscovered_endpoint(), _undiscovered_endpoint()])
    runner = _tf_graph_fixture(graph=graph)
    ready, _ = runner._tf_graph_evidence()
    assert ready is False


def test_unresolved_endpoint_does_not_hide_known_foreign_endpoint():
    """Still reject known foreign endpoints beside a discovery sentinel."""
    graph = _complete_tf_graph()
    graph['/tf'].extend([
        _undiscovered_endpoint(), _endpoint('foreign_localizer')])
    runner = _tf_graph_fixture(graph=graph)
    with pytest.raises(
            AcceptanceFailure, match='TF_PUBLISHER_TOPOLOGY_MISMATCH'):
        runner._tf_graph_evidence()


def test_only_exact_jazzy_sentinel_pair_is_treated_as_undiscovered():
    """Do not treat partial or substring sentinel names as discovery state."""
    graph = _complete_tf_graph()
    graph['/tf'].append(_endpoint('_NODE_NAME_UNKNOWN_'))
    runner = _tf_graph_fixture(graph=graph)
    with pytest.raises(
            AcceptanceFailure, match='TF_PUBLISHER_TOPOLOGY_MISMATCH'):
        runner._tf_graph_evidence()


def test_bare_dds_endpoint_is_not_treated_as_ros_discovery_pending():
    """Reject the distinct bare DDS graph-cache sentinel as foreign."""
    graph = _complete_tf_graph()
    graph['/tf'].append(_endpoint('_CREATED_BY_BARE_DDS_APP_'))
    runner = _tf_graph_fixture(graph=graph)
    with pytest.raises(
            AcceptanceFailure, match='TF_PUBLISHER_TOPOLOGY_MISMATCH'):
        runner._tf_graph_evidence()


def test_tf_graph_required_and_optional_endpoint_topology():
    """Allow dynamic RSP optionally while requiring its static endpoint."""
    runner = _tf_graph_fixture(graph=_complete_tf_graph())
    assert runner._tf_a4_ready(123456)

    graph = _complete_tf_graph()
    graph['/tf'].append(_endpoint('robot_state_publisher'))
    runner = _tf_graph_fixture(graph=graph)
    assert runner._tf_a4_ready(123456)

    graph = _complete_tf_graph()
    graph['/tf_static'] = []
    runner = _tf_graph_fixture(graph=graph)
    assert runner._tf_graph_evidence()[0] is False


def test_empty_graph_and_edges_are_not_replaced_by_fixture_defaults():
    """Preserve explicitly empty graph and edge observations in fixtures."""
    runner = _tf_graph_fixture(graph={}, observed_edges=set())
    assert runner.observer.tf_publisher_graph() == {}
    assert runner.observer.tf_observed_edges == set()
    assert runner._tf_ownership_ready() is False


def test_robot_state_publisher_tf_endpoint_requires_dynamic_robot_joints(
):
    """Verify RSP TF endpoint requires movable robot joints."""
    graph = _complete_tf_graph()
    graph['/tf'].append(_endpoint('robot_state_publisher'))
    runner = _tf_graph_fixture(graph=graph)
    runner.tf_configured_ownership['dynamic_joint_names'] = []
    with pytest.raises(
            AcceptanceFailure, match='TF_PUBLISHER_TOPOLOGY_MISMATCH:/tf'):
        runner._tf_ownership_ready()


def test_tf_graph_missing_publishers_wait_and_unresolved_graph_times_out(
        monkeypatch):
    """Verify missing publishers wait until graph discovery expires."""
    clock = [0.0]
    monkeypatch.setattr(
        runner_module.time, 'sleep',
        lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    runner = _tf_graph_fixture(graph={'/tf': [], '/tf_static': []})
    runner.started_steady = 0.0
    runner.now_steady = lambda: clock[0]
    with pytest.raises(AcceptanceFailure, match='TF_GRAPH_UNRESOLVED'):
        runner._wait_for(
            runner._tf_ownership_ready, 0.25, stage='A4_TF',
            component='tf_publishers', reason='TF_GRAPH_UNRESOLVED')
    assert clock[0] >= 0.25
    assert not runner._tf_ownership_ready()


def test_tf_graph_delayed_resolution_before_deadline_is_requeried(monkeypatch):
    """Verify tf graph delayed resolution before deadline is requeried."""
    clock = [0.0]
    monkeypatch.setattr(
        runner_module.time, 'sleep',
        lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    graph = {'/tf': [], '/tf_static': []}
    runner = _tf_graph_fixture(graph=graph)
    runner.observer.tf_publisher_graph = lambda: (
        _complete_tf_graph() if clock[0] >= 0.15 else graph)
    runner.started_steady = 0.0
    runner.now_steady = lambda: clock[0]
    runner._wait_for(
        runner._tf_ownership_ready, 1.0, stage='A4_TF',
        component='tf_publishers', reason='TF_GRAPH_UNRESOLVED')
    assert clock[0] >= 0.15


@pytest.mark.parametrize(
    'mutation', ['missing_edge', 'wrong_frame', 'lookup_failure'])
def test_tf_a4_still_fails_for_missing_edge_or_exact_time_lookup(
        monkeypatch, mutation):
    """Verify tf a4 still fails for missing edge or exact time lookup."""
    clock = [0.0]
    monkeypatch.setattr(
        runner_module.time, 'sleep',
        lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    runner = _tf_graph_fixture()
    runner.started_steady = 0.0
    runner.now_steady = lambda: clock[0]
    if mutation in ('missing_edge', 'wrong_frame'):
        runner.observer.tf_observed_edges.remove(('base_link', 'lidar_frame'))
        if mutation == 'wrong_frame':
            runner.observer.tf_observed_edges.add(('base_link', 'lidar'))
    else:
        runner.observer.lookup_transform = lambda *_: (
            (_ for _ in ()).throw(LookupError('no exact transform')))
    with pytest.raises(AcceptanceFailure, match='TF_A4_NOT_READY'):
        runner._wait_for(
            lambda: runner._tf_a4_ready(123456), 0.2,
            stage='A4_TF', component='tf2', reason='TF_A4_NOT_READY')
    assert clock[0] >= 0.2


def test_tf_resource_validation_rejects_wrong_configured_owner(
        monkeypatch, tmp_path):
    """Verify tf resource validation rejects wrong configured owner."""
    import shutil
    verify_tf_ownership_resources = runner_module.verify_tf_ownership_resources
    source_repo = Path(__file__).resolve().parents[4]
    repo = tmp_path / 'repo'
    shares = {}
    for package in ('mecanum_nav_bringup', 'ROBOT_URDF_final_description'):
        shares[package] = tmp_path / package / 'share' / package
        shares[package].mkdir(parents=True)
    relative = (
        ('mecanum_nav_bringup',
         'launch/sim_eval_nav2_baseline_system.launch.py'),
        ('mecanum_nav_bringup',
         'launch/sim_eval_tf_ekf_state_estimation.launch.py'),
        ('mecanum_nav_bringup', 'config/localization/amcl_omni.yaml'),
        ('mecanum_nav_bringup', 'config/state_estimation/ekf_sim.yaml'),
        ('ROBOT_URDF_final_description',
         'launch/sim_eval_nav2_baseline_bootstrap.launch.py'),
        ('ROBOT_URDF_final_description', 'urdf/ROBOT_URDF_final.xacro'),
    )
    for package, rel in relative:
        source = source_repo / 'ros2_ws/src' / package / rel
        source_copy = repo / 'ros2_ws/src' / package / rel
        target = shares[package] / rel
        source_copy.parent.mkdir(parents=True, exist_ok=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, source_copy)
        shutil.copyfile(source, target)
    verified = verify_tf_ownership_resources(
        repo, share_resolver=lambda package: str(shares[package]))
    assert verified['source_installed_resources_byte_equal'] is True
    assert 'Wheel_LF_Joint' in verified['dynamic_joint_names']
    amcl = shares['mecanum_nav_bringup'] / 'config/localization/amcl_omni.yaml'
    invalid_amcl = amcl.read_text().replace(
        'tf_broadcast: true', 'tf_broadcast: false')
    amcl.write_text(invalid_amcl)
    source_amcl = (
        repo / 'ros2_ws/src/mecanum_nav_bringup/config/localization/'
        'amcl_omni.yaml')
    source_amcl.write_text(invalid_amcl)
    with pytest.raises(ValueError, match='TF_OWNERSHIP_AMCL_CONFIG_MISMATCH'):
        verify_tf_ownership_resources(
            repo, share_resolver=lambda package: str(shares[package]))


def test_shutdown_a10_requires_safe_stop_capture_finalization_and_owned_cleanup():
    from mecanum_nav_rl.observations.step07_research_acceptance import Context, StampedFact
    context = Context(1, 2, 3, "a" * 64)
    class Future:
        def done(self): return True
        def exception(self): return None
        def result(self): return SimpleNamespace(success=True)
    class Observer:
        def __init__(self):
            self.context = context
            self.receipts = [StampedFact(101, time.monotonic_ns(), "base_link",
                {"command": (0.0, 0.0, 0.0)}, context)]
            self.node = SimpleNamespace(get_clock=lambda: SimpleNamespace(
                now=lambda: SimpleNamespace(nanoseconds=100)))
        def request_safe_stop(self): return Future()
        def destroy(self): pass
    runner = object.__new__(ResearchAcceptanceRunner)
    runner.state = CampaignState(facts={"A9": {"pass": False, "reason": "NO_RESULT"}})
    runner.observer = Observer()
    runner.navigation_goal_handle = None
    runner.now_steady = time.monotonic
    runner.process_owner = ProcessOwner()
    runner.process_owner.stop_all = lambda *args, **kwargs: []
    runner.process_owner.warnings = []
    runner._capture_finalized = lambda: True
    runner.executor = None
    runner.executor_thread = None
    runner.rclpy = None
    runner.shutdown_completed = False
    runner.shutdown()
    assert runner.state.facts["A10"]["pass"] is True
    assert runner.state.facts["A9"]["pass"] is False


def test_shutdown_fails_a10_when_capture_is_not_finalized_or_no_runtime_child_started():
    runner = object.__new__(ResearchAcceptanceRunner)
    runner.state = CampaignState()
    runner.observer = None
    runner.navigation_goal_handle = None
    runner.now_steady = time.monotonic
    runner.process_owner = ProcessOwner()
    runner.process_owner.warnings = []
    runner._capture_finalized = lambda: False
    runner.executor = None
    runner.executor_thread = None
    runner.rclpy = None
    runner.shutdown_completed = False
    runner.shutdown()
    assert runner.state.facts["A10"]["pass"] is False
    assert runner.state.cleanup["safe_stop_verified"] is False


def test_executor_exception_is_captured_and_raised_into_runner_failure():
    class BrokenExecutor:
        def spin(self):
            raise RuntimeError("executor broke")
    runner = object.__new__(ResearchAcceptanceRunner)
    runner.executor = BrokenExecutor()
    runner.observer = SimpleNamespace(executor_error=None)
    runner.state = CampaignState(stage="A7_OBSERVATION")
    runner._spin_executor()
    with pytest.raises(AcceptanceFailure, match="EXECUTOR_EXCEPTION:RuntimeError:executor broke"):
        runner._raise_executor_error()


def _install_fake_ros_time(monkeypatch):
    module = ModuleType("rclpy.time")
    class FakeTime:
        def __init__(self, *, nanoseconds, clock_type):
            self.nanoseconds = nanoseconds
            self.clock_type = clock_type
    module.Time = FakeTime
    monkeypatch.setitem(sys.modules, "rclpy.time", module)
    return SimpleNamespace(ROS_TIME="ROS_TIME")


def _bind_health_snapshot(
        observer, *, context, ros_now_ns, lifecycle, odometry):
    from collections import deque
    from types import MethodType
    from mecanum_nav_rl.observations.step07_research_observer import (
        Step07ResearchObserver,
    )

    observer._lock = threading.RLock()
    observer.context = context
    observer.lifecycle = lifecycle
    observer.barrier_sequence = 5
    observer.barrier_stamp_ns = 0
    observer.clock_rollback = False
    observer.clock_ns = ros_now_ns
    observer.clock_advance_count = 2
    observer.scans = deque()
    observer.wheel = deque()
    observer.imu = deque()
    observer.odometry = deque(odometry)
    observer.receipts = deque()
    observer.localization = deque()
    observer.node = SimpleNamespace(get_clock=lambda: SimpleNamespace(
        now=lambda: SimpleNamespace(nanoseconds=ros_now_ns)))
    observer.sensor_health_snapshot = MethodType(
        Step07ResearchObserver.sensor_health_snapshot, observer
    )


@pytest.mark.parametrize(("poses", "translation", "rotation"), [
    (((0.2, 0.0), (1.2, 0.0)), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
    (((1.2, 0.0), (2.2, 0.0)), (-1.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
    (((0.0, -0.2), (0.0, -1.2)), (0.0, 0.0, 0.0),
     (0.0, 0.0, 0.7071067811865476, 0.7071067811865476)),
    (((-1.0, -1.2), (-1.0, -2.2)), (-1.0, 1.0, 0.0),
     (0.0, 0.0, 0.7071067811865476, 0.7071067811865476)),
])
def test_production_tf_lookup_applies_base_from_map_transform_without_mutating_path(monkeypatch,
        poses, translation, rotation):
    from mecanum_nav_rl.observations.step07_research_acceptance import Context, PathSnapshot, StampedFact
    clock_type = _install_fake_ros_time(monkeypatch)

    now = time.monotonic_ns()
    context = Context(1, 2, 3, "a" * 64)
    path = PathSnapshot(poses, "request", (-4.0, 0.0),
        "map", "b" * 64, context, now, now + 5_000_000_000)
    transform = SimpleNamespace(transform=SimpleNamespace(
        translation=SimpleNamespace(x=translation[0], y=translation[1], z=translation[2]),
        rotation=SimpleNamespace(x=rotation[0], y=rotation[1], z=rotation[2], w=rotation[3])))
    lookups = []
    def lookup(*args, **kwargs):
        lookups.append(args)
        return transform
    observer = SimpleNamespace(
        tf_buffer=SimpleNamespace(lookup_transform=lookup),
        _Duration=lambda **kwargs: None,
        clock_ns=100, clock_rollback=False, context=context, barrier_sequence=5,
        lifecycle=StampedFact(100, now, "base_link", {"primary_state": 2,
            "barrier_state": 1, "motion_permitted": True}, context))
    _bind_health_snapshot(
        observer, context=context, ros_now_ns=100,
        lifecycle=observer.lifecycle,
        odometry=(StampedFact(100, now, 'base_link', SimpleNamespace(), context),),
    )
    runner = object.__new__(ResearchAcceptanceRunner)
    runner.path_snapshot = path
    runner.observer = observer
    runner.rclpy = SimpleNamespace(clock=SimpleNamespace(ClockType=clock_type))
    runner.now_steady = time.monotonic
    runner.last_progress_arc = None
    runner.goal_barrier_sequence = 5
    runner.log_stream = io.StringIO()
    result = runner._lookup_local_reference(100, now, 100, time.monotonic() + 1.0)
    assert result is not None, runner.log_stream.getvalue()
    assert result[0] == pytest.approx((0.14, 0.0, 1.0))
    assert path.poses_xy == poses
    assert lookups[0][0:2] == ("base_link", "map")
    assert lookups[0][2].nanoseconds == 100


def test_production_tf_lookup_returns_no_vector_for_unavailable_or_expired_path(monkeypatch):
    from mecanum_nav_rl.observations.step07_research_acceptance import Context, PathSnapshot, StampedFact
    clock_type = _install_fake_ros_time(monkeypatch)

    now = time.monotonic_ns()
    context = Context(1, 2, 3, "a" * 64)
    expired = PathSnapshot(((2.0, 0.0), (3.0, 0.0)), "request", (-4.0, 0.0),
        "map", "b" * 64, context, now, now - 1)
    calls = 0
    def unavailable(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise LookupError("no transform at exact stamp")
    observer = SimpleNamespace(tf_buffer=SimpleNamespace(lookup_transform=unavailable),
        _Duration=lambda **kwargs: None, clock_ns=100, clock_rollback=False,
        context=context, barrier_sequence=5, lifecycle=StampedFact(100, now, "base_link",
        {"primary_state": 2, "barrier_state": 1, "motion_permitted": True}, context))
    _bind_health_snapshot(
        observer, context=context, ros_now_ns=100,
        lifecycle=observer.lifecycle,
        odometry=(StampedFact(100, now, 'base_link', SimpleNamespace(), context),),
    )
    runner = object.__new__(ResearchAcceptanceRunner)
    runner.path_snapshot = expired
    runner.observer = observer
    runner.rclpy = SimpleNamespace(clock=SimpleNamespace(ClockType=clock_type))
    runner.now_steady = time.monotonic
    runner.last_progress_arc = None
    runner.goal_barrier_sequence = 5
    runner.log_stream = None
    assert runner._lookup_local_reference(100, now, 100, time.monotonic() + 0.02) is None
    assert calls > 0
    transform = SimpleNamespace(transform=SimpleNamespace(
        translation=SimpleNamespace(x=-1.0, y=0.0, z=0.0),
        rotation=SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0)))
    runner.observer.tf_buffer.lookup_transform = lambda *args, **kwargs: transform
    assert runner._lookup_local_reference(100, now, 100, time.monotonic() + 1.0) is None


def _production_observation_runner(monkeypatch, *, tf_available=True):
    from collections import deque
    from mecanum_nav_rl.observations.step07_research_acceptance import (
        Context, PathSnapshot, StampedFact,
    )

    clock_type = _install_fake_ros_time(monkeypatch)
    now_ros = 20_000_000_000
    now_steady = time.monotonic_ns()
    context = Context(4, 2, 3, 'a' * 64)
    lifecycle = StampedFact(
        now_ros, now_steady, 'base_link',
        {'primary_state': 2, 'barrier_state': 1, 'motion_permitted': True},
        context,
    )
    scan_value = SimpleNamespace(
        header=SimpleNamespace(frame_id='lidar_frame'),
        ranges=[2.0] * 360,
        angle_min=-math.pi,
        angle_increment=2*math.pi/360,
        range_min=0.1,
        range_max=10.0,
    )

    def odom_message(stamp_ns):
        def vector3():
            return SimpleNamespace(x=0.0, y=0.0, z=0.0)

        return SimpleNamespace(
            header=SimpleNamespace(frame_id='odom', stamp_ns=stamp_ns),
            child_frame_id='base_link',
            pose=SimpleNamespace(
                pose=SimpleNamespace(
                    position=vector3(),
                    orientation=SimpleNamespace(
                        x=0.0, y=0.0, z=0.0, w=1.0
                    ),
                ),
                covariance=[0.0]*36,
            ),
            twist=SimpleNamespace(
                twist=SimpleNamespace(
                    linear=SimpleNamespace(x=0.1, y=-0.05, z=0.0),
                    angular=SimpleNamespace(x=0.0, y=0.0, z=0.2),
                ),
                covariance=[0.0]*36,
            ),
        )

    odom_value = odom_message(now_ros-1_000_000)

    def lookup(target, source, stamp, *, timeout):
        assert (target, source) == ('base_link', 'map')
        assert stamp.nanoseconds == odom_value.header.stamp_ns
        if not tf_available:
            raise LookupError('exact-time TF unavailable')
        return SimpleNamespace(
            transform=SimpleNamespace(
                translation=SimpleNamespace(x=0.0, y=0.0, z=0.0),
                rotation=SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0),
            )
        )

    observer = SimpleNamespace(
        context=context, clock_ns=now_ros, clock_rollback=False,
        barrier_sequence=7, barrier_stamp_ns=1, lifecycle=lifecycle,
        scans=deque(maxlen=64), odometry=deque(maxlen=64),
        wheel=deque(maxlen=64), imu=deque(maxlen=64),
        receipts=deque(maxlen=64),
        localization=deque(maxlen=64),
        node_ros_clock_ns=now_ros,
        node=SimpleNamespace(
            get_clock=lambda: SimpleNamespace(
                now=lambda: SimpleNamespace(nanoseconds=observer.node_ros_clock_ns)
            )
        ),
        tf_buffer=SimpleNamespace(lookup_transform=lookup),
        lookup_transform=lambda *args: None,
        tf_observed_edges={('map', 'odom'), ('odom', 'base_link'),
                           ('base_link', 'lidar_frame')},
        _Duration=lambda **kwargs: SimpleNamespace(**kwargs),
    )
    from types import MethodType
    from mecanum_nav_rl.observations.step07_research_observer import (
        Step07ResearchObserver,
    )
    observer._lock = threading.RLock()
    observer.clock_advance_count = 2
    observer.sensor_health_snapshot = MethodType(
        Step07ResearchObserver.sensor_health_snapshot, observer
    )
    # Clock callback in the fake node reads this assigned observer dynamically.
    observer.clock_ns = now_ros
    runner = object.__new__(ResearchAcceptanceRunner)
    runner.observer = observer
    runner._tf_ownership_ready = lambda: True
    runner.rclpy = SimpleNamespace(clock=SimpleNamespace(ClockType=clock_type))
    runner.path_snapshot = PathSnapshot(
        ((0.0, 0.0), (1.0, 0.0), (2.0, 0.0)),
        'path-request', (-4.0, 0.0), 'warehouse_map2', 'b' * 64, context,
        now_steady-10_000_000, now_steady+10_000_000_000,
    )
    runner.goal_barrier_sequence = 7
    runner.goal_barrier_stamp_ns = 1
    runner.action_accept_ns = 1
    runner.used_pairs = set()
    runner.last_progress_arc = None
    runner.now_steady = time.monotonic
    runner.config_hash = context.config_hash
    runner.state = CampaignState()
    runner.log_stream = io.StringIO()
    runner._test_scan_value = scan_value
    runner._test_odom_value = odom_value
    runner._test_context = context
    runner._test_receipt = StampedFact(
        now_ros-1_000_000, now_steady, 'base_link', {
            'command': (0.1, -0.05, 0.2), 'source': 2, 'sequence': 3,
            'final_publish_sequence': 8,
        }, context,
    )

    def update(index, *, scan_stamp=None, odom_stamp=None):
        cutoff = now_ros + (index+1)*10_000_000
        steady = time.monotonic_ns()
        observer.clock_ns = cutoff
        observer.node_ros_clock_ns = cutoff
        observer.lifecycle = StampedFact(
            cutoff, steady, 'base_link', {
                'primary_state': 2, 'barrier_state': 1,
                'motion_permitted': True,
            }, context,
        )
        scan_value.header.stamp_ns = (
            scan_stamp if scan_stamp is not None else cutoff-1_000_000
        )
        odom_value.header.stamp_ns = (
            odom_stamp if odom_stamp is not None else cutoff-1_000_000
        )
        observer.scans.clear()
        observer.scans.append(StampedFact(
            scan_value.header.stamp_ns, steady, 'lidar_frame', scan_value,
            context,
        ))
        observer.odometry.clear()
        observer.odometry.append(StampedFact(
            odom_value.header.stamp_ns, steady, 'base_link', odom_value,
            context,
        ))
        observer.wheel.clear()
        observer.wheel.append(StampedFact(
            cutoff-1_000_000, steady, 'odom',
            odom_message(cutoff-1_000_000), context,
        ))
        observer.imu.clear()
        zeros = SimpleNamespace(x=0.0, y=0.0, z=0.0)
        imu_message = SimpleNamespace(
            header=SimpleNamespace(frame_id='base_link'),
            angular_velocity=zeros,
            linear_acceleration=zeros,
            angular_velocity_covariance=[0.0]*9,
            linear_acceleration_covariance=[0.0]*9,
            orientation_covariance=[0.0]*9,
        )
        observer.imu.append(StampedFact(
            cutoff-1_000_000, steady, 'base_link', imu_message, context,
        ))
        observer.localization.clear()
        observer.localization.append({
            'stamp_ns': cutoff-1_000_000,
            'received_steady_ns': steady,
            'frame_id': 'map',
            'pose': (0.0, 0.0, 0.0),
            'covariance': (0.01, 0.01, 0.01),
            'context': context,
        })
        observer.receipts.clear()
        receipt = runner._test_receipt
        observer.receipts.append(StampedFact(
            receipt.stamp_ns, steady, receipt.frame_id, receipt.value, context,
        ))
    runner._update_test_observation = update
    return runner


def test_production_health_snapshot_precedes_interleaved_scan_callback(monkeypatch):
    """Keep the evaluation on the scan facts captured before callback entry."""
    """A callback after the local snapshot cannot make receive age negative."""
    from types import MethodType
    from mecanum_nav_rl.observations.step07_research_observer import (
        Step07ResearchObserver,
    )

    runner = _production_observation_runner(monkeypatch)
    runner._update_test_observation(0)
    observer = runner.observer
    observer._lock = threading.RLock()
    observer._steady_ns = lambda: 1_000_000_001
    observer._stamp = Step07ResearchObserver._stamp
    observer._insert_ordered = Step07ResearchObserver._insert_ordered
    observer._fact = MethodType(Step07ResearchObserver._fact, observer)
    observer._scan = MethodType(Step07ResearchObserver._scan, observer)
    observer.sensor_health_snapshot = MethodType(
        Step07ResearchObserver.sensor_health_snapshot, observer
    )
    for stream_name in ('scans', 'wheel', 'imu', 'odometry'):
        stream = getattr(observer, stream_name)
        fact = stream[-1]
        stream[-1] = type(fact)(
            fact.stamp_ns, 999_000_000, fact.frame_id, fact.value,
            fact.context, fact.identity,
        )
    observer.lifecycle = type(observer.lifecycle)(
        observer.lifecycle.stamp_ns, 999_000_000, observer.lifecycle.frame_id,
        observer.lifecycle.value, observer.lifecycle.context,
        observer.lifecycle.identity,
    )
    observer.localization[-1]['received_steady_ns'] = 999_000_000
    original_scan_stamp = observer.scans[-1].stamp_ns+1_000_000
    scan_message = SimpleNamespace(
        header=SimpleNamespace(
            stamp=SimpleNamespace(
                sec=original_scan_stamp // 1_000_000_000,
                nanosec=original_scan_stamp % 1_000_000_000,
            ),
            frame_id='lidar_frame',
        ),
        ranges=[2.0]*360, angle_min=-math.pi,
        angle_increment=2*math.pi/360, range_min=0.1, range_max=10.0,
    )
    injected = False

    evaluation_now = []

    def evaluation_steady_ns():
        nonlocal injected
        if not injected:
            injected = True
            observer._scan(scan_message)
            evaluation_now.append(1_000_000_000)
            return evaluation_now[-1]
        return evaluation_now[-1]+2

    monkeypatch.setattr(runner_module.time, 'monotonic_ns', evaluation_steady_ns)
    runner._assert_live_mission_health(
        runner.path_snapshot.context, 'A7_OBSERVATION'
    )
    assert injected is True
    assert observer.scans[-1].received_steady_ns > 1_000_000_000
    assert 1_000_000_000-observer.scans[-1].received_steady_ns < 0
    assert runner.state.valid_observations == []


def test_production_health_uses_node_ros_clock_not_cached_clock(monkeypatch):
    """A stale cache cannot make stale sensor facts appear fresh."""
    runner = _production_observation_runner(monkeypatch)
    runner._update_test_observation(0)
    observer = runner.observer
    node_now = observer.node_ros_clock_ns
    observer.node_ros_clock_ns = node_now + 200_000_000
    observer.clock_ns = node_now - 200_000_000
    scan = observer.scans[-1]
    observer.scans[-1] = type(scan)(
        node_now-400_000_000, scan.received_steady_ns, scan.frame_id,
        scan.value, scan.context, scan.identity,
    )
    lifecycle = observer.lifecycle
    observer.lifecycle = type(lifecycle)(
        observer.clock_ns-100_000_000, lifecycle.received_steady_ns,
        lifecycle.frame_id,
        lifecycle.value, lifecycle.context, lifecycle.identity,
    )
    observer.localization[-1]['stamp_ns'] = observer.clock_ns-50_000_000
    for stream_name in ('wheel', 'imu', 'odometry'):
        stream = getattr(observer, stream_name)
        fact = stream[-1]
        stream[-1] = type(fact)(
            observer.clock_ns-10_000_000, fact.received_steady_ns,
            fact.frame_id, fact.value, fact.context, fact.identity,
        )

    with pytest.raises(AcceptanceFailure, match='ROS_AGE_EXCEEDED'):
        runner._assert_live_mission_health(
            runner.path_snapshot.context, 'A7_OBSERVATION'
        )


def test_production_health_reports_receive_age_when_ros_clock_is_paused(monkeypatch):
    """Keep steady receive-age enforcement active with paused ROS time."""
    runner = _production_observation_runner(monkeypatch)
    runner._update_test_observation(0)
    fact = runner.observer.scans[-1]
    runner.observer.scans[-1] = type(fact)(
        fact.stamp_ns, fact.received_steady_ns-600_000_000,
        fact.frame_id, fact.value, fact.context, fact.identity,
    )

    with pytest.raises(AcceptanceFailure, match='RECEIVE_AGE_EXCEEDED') as error:
        runner._assert_live_mission_health(
            runner.path_snapshot.context, 'A7_OBSERVATION'
        )

    measured = error.value.measured
    assert measured['stream'] == 'scan'
    assert (
        measured['evaluation_ros_time_ns']
        == runner.observer.node_ros_clock_ns
    )
    assert measured['ros_age_ns'] >= 0
    assert measured['receive_age_ns'] > measured['steady_receive_limit_ns']


def test_production_health_rejects_context_mismatch_with_measurement(monkeypatch):
    """Reject facts outside the pinned context with measured evidence."""
    from mecanum_nav_rl.observations.step07_research_acceptance import Context

    runner = _production_observation_runner(monkeypatch)
    runner._update_test_observation(0)
    fact = runner.observer.scans[-1]
    runner.observer.scans[-1] = type(fact)(
        fact.stamp_ns, fact.received_steady_ns, fact.frame_id, fact.value,
        Context(99, 2, 3, fact.context.config_hash), fact.identity,
    )

    with pytest.raises(AcceptanceFailure, match='CONTEXT_MISMATCH') as error:
        runner._assert_live_mission_health(
            runner.path_snapshot.context, 'A7_OBSERVATION'
        )

    assert error.value.measured['expected_context']['episode_generation'] == 4
    assert error.value.measured['observed_context']['episode_generation'] == 99


def test_production_health_treats_node_ros_clock_rollback_as_terminal(monkeypatch):
    """Fail closed when the attached ROS clock moves backward."""
    runner = _production_observation_runner(monkeypatch)
    runner._update_test_observation(0)
    runner._last_node_ros_now_ns = runner.observer.node_ros_clock_ns+1
    runner._node_ros_rollback = False

    with pytest.raises(
            AcceptanceFailure, match='SIM_CLOCK_INVALID_OR_ROLLED_BACK'):
        runner._assert_live_mission_health(
            runner.path_snapshot.context, 'A7_OBSERVATION'
        )

    assert runner._node_ros_rollback is True


def test_production_health_future_only_buffer_does_not_create_observation(monkeypatch):
    """A future-only buffer cannot produce an observation or report PASS."""
    runner = _production_observation_runner(monkeypatch)
    runner._update_test_observation(0)
    future = runner.observer.node_ros_clock_ns+1
    fact = runner.observer.odometry[-1]
    runner.observer.odometry[-1] = type(fact)(
        future, fact.received_steady_ns, fact.frame_id, fact.value,
        fact.context, fact.identity,
    )

    with pytest.raises(AcceptanceFailure, match='ROS_TIMESTAMP_FUTURE') as error:
        runner._collect_one_observation(time.monotonic()+1.0)

    assert error.value.measured['stream'] == 'filtered_odometry'
    assert runner.state.valid_observations == []
    assert (runner.state.primary_failure['measured']['reason']
            == 'ROS_TIMESTAMP_FUTURE')


def test_production_observation_skips_future_newest_for_earlier_fresh_pair(monkeypatch):
    """A post-cutoff newest scan does not hide an eligible earlier pair."""
    from mecanum_nav_rl.observations.step07_research_acceptance import (
        StampedFact,
    )

    runner = _production_observation_runner(monkeypatch)
    runner._update_test_observation(0)
    observer = runner.observer
    cutoff = observer.node_ros_clock_ns
    context = runner.path_snapshot.context
    steady = time.monotonic_ns()
    fresh_stamp = cutoff-20_000_000
    fresh_scan = SimpleNamespace(
        header=SimpleNamespace(frame_id='lidar_frame', stamp_ns=fresh_stamp),
        ranges=[2.0]*360, angle_min=-math.pi,
        angle_increment=2*math.pi/360, range_min=0.1, range_max=10.0,
    )
    future_scan = SimpleNamespace(
        header=SimpleNamespace(frame_id='lidar_frame', stamp_ns=cutoff+1),
        ranges=[2.0]*360, angle_min=-math.pi,
        angle_increment=2*math.pi/360, range_min=0.1, range_max=10.0,
    )
    fresh_odom_value = observer.odometry[-1].value
    fresh_odom_value.header.stamp_ns = fresh_stamp+1_000_000
    fresh_odom = StampedFact(
        fresh_stamp+1_000_000, steady, 'base_link', fresh_odom_value, context,
    )
    observer.scans.clear()
    observer.scans.extend((
        StampedFact(fresh_stamp, steady, 'lidar_frame', fresh_scan, context),
        StampedFact(cutoff+1, steady, 'lidar_frame', future_scan, context),
    ))
    observer.odometry.clear()
    observer.odometry.append(fresh_odom)

    assert runner._collect_one_observation(time.monotonic()+1.0) is True
    sample = runner.state.valid_observations[-1]
    assert sample['scan_stamp_ns'] == fresh_stamp
    assert sample['scan_stamp_ns'] <= sample['snapshot_cutoff_ros_ns']
    assert len(runner.state.valid_observations) == 1


def test_production_collect_one_observation_builds_five_distinct_81d_pairs(
    monkeypatch,
):
    """Collect five production-path vectors from five distinct input pairs."""
    runner = _production_observation_runner(monkeypatch)
    deadline = time.monotonic()+3.0
    for i in range(5):
        runner._update_test_observation(i)
        assert runner._collect_one_observation(deadline) is True
    assert len(runner.state.valid_observations) == 5
    assert all(
        item['dtype'] == 'float32'
        and item['shape'] == [81]
        and len(item['vector']) == 81
        for item in runner.state.valid_observations
    )
    pairs = {(item['scan_stamp_ns'], item['odom_stamp_ns'])
             for item in runner.state.valid_observations}
    assert len(pairs) == 5
    assert runner._collect_one_observation(deadline) is False
    assert len(runner.state.valid_observations) == 5


@pytest.mark.parametrize('mutation', [
    'stale', 'future', 'lifecycle', 'clock_rollback', 'tf_unavailable'
])
def test_production_collect_one_observation_rejects_invalid_live_facts(
    monkeypatch, mutation,
):
    """Reject invalid live facts on the direct observation collection path."""
    runner = _production_observation_runner(
        monkeypatch, tf_available=mutation != 'tf_unavailable'
    )
    runner._update_test_observation(0)
    if mutation == 'stale':
        runner._update_test_observation(
            0, scan_stamp=runner.observer.clock_ns-600_000_000
        )
    elif mutation == 'future':
        runner._update_test_observation(
            0, odom_stamp=runner.observer.clock_ns+1
        )
    elif mutation == 'lifecycle':
        runner.observer.lifecycle.value['barrier_state'] = 2
        runner.observer.lifecycle.value['motion_permitted'] = False
    elif mutation == 'clock_rollback':
        runner.observer.clock_rollback = True
    deadline = time.monotonic()+(0.03 if mutation == 'tf_unavailable' else 1.0)
    if mutation in ('lifecycle', 'clock_rollback', 'stale', 'future'):
        with pytest.raises(AcceptanceFailure):
            runner._collect_one_observation(deadline)
    else:
        assert runner._collect_one_observation(deadline) is False
    assert runner.state.valid_observations == []


def _prepare_mission_health_check(runner):
    runner.started_steady = time.monotonic()-459.95
    runner.now_steady = time.monotonic
    runner._send_one_plan = lambda: None
    runner._goal_pose = lambda: SimpleNamespace(
        header=SimpleNamespace(stamp=SimpleNamespace())
    )

    class ResultFuture:
        def done(self): return False

    class GoalHandle:
        accepted = True
        goal_id = SimpleNamespace(uuid=b'goal')
        def get_result_async(self): return ResultFuture()

    class ReadyFuture:
        def __init__(self, value): self.value = value
        def done(self): return True
        def exception(self): return None
        def result(self): return self.value
    runner.observer.send_navigation = lambda goal: ReadyFuture(GoalHandle())
    runner._check_launch_processes = lambda: None
    runner.state.valid_observations = [{'shape': [81]} for _ in range(5)]
    runner.mission_deadline_steady = time.monotonic()+1.0


@pytest.mark.parametrize(
    'mutation', ['nonready', 'stale_input', 'stale_ros_odom', 'clock_rollback']
)
def test_production_mission_rechecks_health_after_fifth_observation(
    monkeypatch, mutation,
):
    """Keep production mission health admission active after sample five."""
    runner = _production_observation_runner(monkeypatch)
    runner._update_test_observation(0)
    _prepare_mission_health_check(runner)
    if mutation == 'nonready':
        runner.observer.lifecycle.value['barrier_state'] = 2
        runner.observer.lifecycle.value['motion_permitted'] = False
    elif mutation == 'stale_input':
        fact = runner.observer.scans[-1]
        runner.observer.scans[-1] = type(fact)(
            fact.stamp_ns, fact.received_steady_ns-600_000_000,
            fact.frame_id, fact.value, fact.context, fact.identity,
        )
    elif mutation == 'stale_ros_odom':
        fact = runner.observer.odometry[-1]
        runner.observer.odometry[-1] = type(fact)(
            runner.observer.clock_ns-300_000_000,
            time.monotonic_ns(), fact.frame_id, fact.value, fact.context,
            fact.identity,
        )
    else:
        runner.observer.clock_rollback = True
    with pytest.raises(AcceptanceFailure):
        runner._mission()
    assert runner.state.facts['A7']['pass'] is False
    assert runner.state.facts['A9']['pass'] is False
    assert runner.state.primary_failure is not None
    if mutation in ('stale_input', 'nonready', 'clock_rollback'):
        assert runner.state.facts['A2']['pass'] is False
    if mutation == 'stale_ros_odom':
        assert runner.state.facts['A3']['pass'] is False


def test_settle_rejects_ros_stale_odometry(monkeypatch):
    """Reject old ROS-stamped odometry during production settle checks."""
    runner = _production_observation_runner(monkeypatch)
    runner._update_test_observation(0)
    fact = runner.observer.odometry[-1]
    runner.observer.odometry[-1] = type(fact)(
        runner.observer.clock_ns-300_000_000,
        time.monotonic_ns(), fact.frame_id, fact.value, fact.context,
        fact.identity,
    )
    runner.mission_deadline_steady = time.monotonic()+0.05
    assert runner._wait_for_settle(time.monotonic()+0.05) is False
    assert runner.state.facts['A3']['pass'] is False
    assert runner.state.facts['A9']['pass'] is False


def test_navigation_success_requires_fresh_settle(monkeypatch):
    """Require the real navigation success path to observe a fresh settle."""
    runner = _production_observation_runner(monkeypatch)
    runner._update_test_observation(0)
    runner.started_steady = time.monotonic()-10.0
    runner.mission_deadline_steady = time.monotonic()+3.0
    runner.observer.odometry[-1].value.twist.twist.linear.x = 0.0
    runner.observer.odometry[-1].value.twist.twist.linear.y = 0.0
    runner.observer.odometry[-1].value.twist.twist.angular.z = 0.0
    runner.observer.localization[-1]['pose'] = (-4.0, 0.0, 0.0)
    stop = threading.Event()

    def refresh():
        index = 1
        while not stop.is_set():
            runner._update_test_observation(index)
            runner.observer.odometry[-1].value.twist.twist.linear.x = 0.0
            runner.observer.odometry[-1].value.twist.twist.linear.y = 0.0
            runner.observer.odometry[-1].value.twist.twist.angular.z = 0.0
            runner.observer.localization[-1]['pose'] = (-4.0, 0.0, 0.0)
            index += 1
            time.sleep(0.02)
    thread = threading.Thread(target=refresh)
    thread.start()
    try:
        outcome = runner._navigation_outcome(
            SimpleNamespace(status=4, result=SimpleNamespace())
        )
    finally:
        stop.set()
        thread.join(timeout=1.0)
    assert not thread.is_alive()
    assert outcome['pass'] is True
    assert outcome['measured']['settled'] is True


def test_a4_failure_before_mission_keeps_full_a6_unevaluated():
    """Verify a4 failure before mission keeps full a6 unevaluated."""
    from mecanum_nav_rl.observations.step07_research_acceptance import (
        evaluate_a1_a10,
    )
    runner = object.__new__(ResearchAcceptanceRunner)
    runner.state = CampaignState(stage='STARTUP')
    runner.started_steady = 0.0
    runner.output = None
    runner.start_observer = lambda: None
    runner.start_runtime_children = lambda: None
    runner._wait_ready = lambda: (_ for _ in ()).throw(
        AcceptanceFailure('A4_TF', 'tf_publishers', 'TF_GRAPH_UNRESOLVED'))
    runner.log = lambda *_args: None
    runner.shutdown = lambda: {}
    runner.evaluate_and_write = lambda: evaluate_a1_a10({
        **runner.state.facts, 'primary_failure': runner.state.primary_failure})
    runner.close = lambda: None

    report = runner.execute()

    assert report['acceptance']['A6']['status'] == 'FAIL'
    assert report['acceptance']['A6']['reason'] == 'NOT_EVALUATED_DUE_TO_A4_TF'


def test_full_a6_is_recorded_only_after_path_success_and_navigate_acceptance():
    """Verify A6 follows successful planning and accepted navigation."""
    from mecanum_nav_rl.observations.step07_research_acceptance import (
        PathSnapshot,
    )
    runner = object.__new__(ResearchAcceptanceRunner)
    runner.started_steady = time.monotonic()-459.0
    runner.now_steady = time.monotonic
    runner.state = CampaignState()
    runner.log_stream = io.StringIO()
    runner.navigation_goal_handle = None
    context = SimpleNamespace()
    runner._send_one_plan = lambda: setattr(
        runner, 'path_snapshot', PathSnapshot(
            ((0.0, 0.0), (1.0, 0.0)), 'request', (-4.0, 0.0),
            'warehouse_map2', 'b'*64, context, 1, 2))
    runner._goal_pose = lambda: SimpleNamespace(
        header=SimpleNamespace(stamp=SimpleNamespace()))

    class ResultFuture:
        def done(self): return False

    class CompletedFuture:
        def done(self): return True
        def exception(self): return None
        def result(self): return goal_handle

    goal_handle = SimpleNamespace(
        accepted=True, goal_id=SimpleNamespace(uuid=b'accepted-goal'),
        get_result_async=lambda: ResultFuture())
    runner.observer = SimpleNamespace(
        node=SimpleNamespace(get_clock=lambda: SimpleNamespace(
            now=lambda: SimpleNamespace(nanoseconds=10))),
        barrier_sequence=4, barrier_stamp_ns=9,
        send_navigation=lambda _goal: CompletedFuture(),
        executor_error=None,
    )
    _bind_health_snapshot(
        runner.observer, context=context, ros_now_ns=10,
        lifecycle=SimpleNamespace(context=context), odometry=(),
    )
    runner._check_live_mission_health = lambda *_args: (_ for _ in ()).throw(
        AcceptanceFailure(
            'A7_OBSERVATION', 'mission', 'STOP_AFTER_ACCEPTANCE_ASSERTION'))

    with pytest.raises(
            AcceptanceFailure, match='STOP_AFTER_ACCEPTANCE_ASSERTION'):
        runner._mission()

    assert runner.state.facts['A6']['pass'] is True
    assert (runner.state.facts['A6']['reason']
            == 'PATH_SUCCEEDED_AND_NAVIGATE_GOAL_ACCEPTED')


def test_command_episode_rechecks_current_publisher():
    """Recheck the actual sole publisher when accepting a retained episode."""
    runner = object.__new__(ResearchAcceptanceRunner)
    episode = {
        'pass': True, 'reason': 'earlier causal episode', 'measured': {},
    }
    runner.state = CampaignState(facts={'command_chain_episode': episode})
    runner.observer = SimpleNamespace(
        graph_snapshot=lambda: {
            'topics': {
                '/cmd_vel': {
                    'publishers': (
                        ('other_publisher', '/', 'geometry_msgs/msg/Twist'),
                    ),
                },
            },
        }
    )
    result = runner._command_chain_fact()
    assert result['pass'] is False
    assert result['reason'] == 'FINAL_CMD_VEL_OWNER_NOT_SOLE_AT_CONCLUSION'


def test_command_chain_correlates_actual_episode_and_retains_success_after_zero_command():
    from mecanum_nav_rl.observations.step07_research_acceptance import Context, StampedFact
    context = Context(1, 2, 3, "a" * 64)
    command = (0.1, -0.02, 0.03)
    candidate = StampedFact(900, 900, "base_link", (0.2, 0.0, 0.0), context)
    envelope = StampedFact(1000, 1100, "base_link", {"source": 2, "sequence": 9,
        "source_instance_id": 11, "command": command}, context)
    unrelated_latest = StampedFact(1200, 1200, "base_link", {"source": 3, "sequence": 10,
        "source_instance_id": 99, "command": (0.3, 0.0, 0.0)}, context)
    safety = StampedFact(1100, 1150, "base_link", {"active_command_source": 2,
        "command_valid": True, "motion_permitted": True, "final_command": command}, context)
    receipt = StampedFact(1300, 1300, "base_link", {"source": 2, "sequence": 9,
        "source_instance_id": 11, "command": command, "final_publish_sequence": 44,
        "publisher_instance": 55}, context)
    zero_receipt = StampedFact(1400, 1400, "base_link", {"source": 2, "sequence": 10,
        "source_instance_id": 11, "command": (0.0, 0.0, 0.0), "final_publish_sequence": 45,
        "publisher_instance": 55}, context)
    actual = StampedFact(1250, 1260, "base_link", command, context)
    observer = SimpleNamespace(graph_snapshot=lambda: {"topics": {"/cmd_vel": {
        "publishers": (("final_twist_publisher", "/", "geometry_msgs/msg/Twist"),)}}},
        nav2_candidates=[candidate], accepted_envelopes=[envelope, unrelated_latest],
        safety_states=[safety], receipts=[receipt, zero_receipt], cmd_vel_commands=[actual])
    runner = object.__new__(ResearchAcceptanceRunner)
    runner.observer = observer
    runner.path_snapshot = SimpleNamespace(context=context)
    runner.state = CampaignState()
    episode = runner._command_chain_fact()
    assert episode["pass"] is True
    assert episode["measured"]["sequence"] == 9
    assert runner._command_chain_fact() == episode


@pytest.mark.parametrize("mutation", ["sequence", "source_instance", "payload", "context"])
def test_command_chain_rejects_mismatched_identity_payload_or_context(mutation):
    from mecanum_nav_rl.observations.step07_research_acceptance import Context, StampedFact
    context = Context(1, 2, 3, "a" * 64)
    other = Context(1, 2, 4, "a" * 64)
    command = (0.1, 0.0, 0.0)
    envelope_context = other if mutation == "context" else context
    sequence = 8 if mutation == "sequence" else 9
    instance = 12 if mutation == "source_instance" else 11
    envelope_command = (0.2, 0.0, 0.0) if mutation == "payload" else command
    observer = SimpleNamespace(graph_snapshot=lambda: {"topics": {"/cmd_vel": {
        "publishers": (("final_twist_publisher", "/", "geometry_msgs/msg/Twist"),)}}},
        nav2_candidates=[StampedFact(900, 900, "base_link", (0.2, 0.0, 0.0), context)],
        accepted_envelopes=[StampedFact(1000, 1100, "base_link", {"source": 2,
            "sequence": sequence, "source_instance_id": instance,
            "command": envelope_command}, envelope_context)],
        safety_states=[StampedFact(1100, 1150, "base_link", {"active_command_source": 2,
            "command_valid": True, "motion_permitted": True, "final_command": envelope_command}, envelope_context)],
        receipts=[StampedFact(1300, 1300, "base_link", {"source": 2, "sequence": 9,
            "source_instance_id": 11, "command": command, "final_publish_sequence": 44,
            "publisher_instance": 55}, context)],
        cmd_vel_commands=[StampedFact(1250, 1260, "base_link", command, context)])
    runner = object.__new__(ResearchAcceptanceRunner)
    runner.observer = observer
    runner.path_snapshot = SimpleNamespace(context=context)
    runner.state = CampaignState()
    assert runner._command_chain_fact()["pass"] is False


def test_command_chain_requires_actual_cmd_vel_and_sole_final_publisher():
    from mecanum_nav_rl.observations.step07_research_acceptance import Context, StampedFact
    context = Context(1, 2, 3, "a" * 64)
    command = (0.1, 0.0, 0.0)
    candidate = StampedFact(900, 900, "base_link", command, context)
    envelope = StampedFact(1000, 1100, "base_link", {"source": 2, "sequence": 9,
        "source_instance_id": 11, "command": command}, context)
    safety = StampedFact(1100, 1150, "base_link", {"active_command_source": 2,
        "command_valid": True, "motion_permitted": True, "final_command": command}, context)
    receipt = StampedFact(1300, 1300, "base_link", {"source": 2, "sequence": 9,
        "source_instance_id": 11, "command": command, "final_publish_sequence": 44,
        "publisher_instance": 55}, context)
    for publishers, commands in [((("final_twist_publisher", "/", "Twist"),), []),
                                 ((("other_node", "/", "Twist"),),
                                  [StampedFact(1250, 1260, "base_link", command, context)])]:
        observer = SimpleNamespace(graph_snapshot=lambda p=publishers: {"topics": {"/cmd_vel": {"publishers": p}}},
            nav2_candidates=[candidate], accepted_envelopes=[envelope], safety_states=[safety],
            receipts=[receipt], cmd_vel_commands=commands)
        runner = object.__new__(ResearchAcceptanceRunner)
        runner.observer = observer
        runner.path_snapshot = SimpleNamespace(context=context)
        runner.state = CampaignState()
        assert runner._command_chain_fact()["pass"] is False


class _Nav2FakeClock:
    def __init__(self):
        self.value = 0.0
        self.callbacks = []

    def __call__(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds
        for callback in tuple(self.callbacks):
            callback(self.value)


class _Nav2FakeFuture:
    def __init__(self, clock, client, response, ready_at, error=None):
        self.clock = clock
        self.client = client
        self.response = response
        self.ready_at = ready_at
        self.error = error
        self.released = False

    def _release(self):
        if not self.released:
            self.released = True
            self.client.outstanding -= 1

    def done(self):
        ready = self.clock() >= self.ready_at
        if ready:
            self._release()
        return ready

    def exception(self):
        return self.error

    def result(self):
        if self.error is not None:
            raise self.error
        return self.response


class _Nav2FakeClient:
    def __init__(self, clock, *, service_ready_at=0.0, node_ready_at=0.0,
                 responses=None):
        self.clock = clock
        self.service_ready_at = service_ready_at
        self.node_ready_at = node_ready_at
        self.responses = list(responses or [(3, 'active', 0.0)])
        self.calls = 0
        self.outstanding = 0
        self.max_outstanding = 0
        self.removed = []
        self.futures = []

    def service_is_ready(self):
        if callable(self.service_ready_at):
            return bool(self.service_ready_at(self.clock()))
        return self.clock() >= self.service_ready_at

    def call_async(self, _request):
        index = min(self.calls, len(self.responses) - 1)
        state_id, label, latency = self.responses[index]
        self.calls += 1
        if state_id is None or isinstance(state_id, SimpleNamespace):
            response = state_id
        else:
            response = SimpleNamespace(
                current_state=SimpleNamespace(id=state_id, label=label)
            )
        self.outstanding += 1
        self.max_outstanding = max(self.max_outstanding, self.outstanding)
        future = _Nav2FakeFuture(
            self.clock, self, response, self.clock() + latency
        )
        self.futures.append(future)
        return future

    def remove_pending_request(self, future):
        self.removed.append(future)
        future._release()


def _nav2_lifecycle_fixture(monkeypatch, *, service_ready_at=None,
                            node_ready_at=None, responses=None):
    service_ready_at = service_ready_at or {}
    node_ready_at = node_ready_at or {}
    responses = responses or {}
    clock = _Nav2FakeClock()
    clients = {
        name: _Nav2FakeClient(
            clock,
            service_ready_at=service_ready_at.get(name, 0.0),
            node_ready_at=node_ready_at.get(name, 0.0),
            responses=responses.get(name),
        )
        for name in REQUIRED_NAV2_LIFECYCLE_NODES
    }
    observer = SimpleNamespace(
        lifecycle_clients=clients,
        _GetState=SimpleNamespace(Request=lambda: object()),
        executor_error=None,
        wait_for_actions=lambda timeout_sec: True,
        graph_snapshot=lambda: {
            'nodes': {name for name, client in clients.items()
                      if clock() >= client.node_ready_at},
            'topics': {},
        },
    )
    runner = object.__new__(ResearchAcceptanceRunner)
    runner.observer = observer
    runner.process_owner = SimpleNamespace(processes=[])
    runner.now_steady = clock
    runner.started_steady = 0.0
    runner.state = CampaignState()
    runner.log_stream = None
    monkeypatch.setattr(runner_module.time, 'sleep', clock.sleep)
    return runner, observer, clients, clock


def _prepare_production_startup(runner, observer, clock, *, rearm_calls):
    now_ns = time.monotonic_ns()
    odom_value = SimpleNamespace(
        header=SimpleNamespace(frame_id='odom'), child_frame_id='base_link',
        pose=SimpleNamespace(
            pose=SimpleNamespace(position=SimpleNamespace(x=0.0, y=0.0)),
            covariance=[0.0] * 36,
        ),
        twist=SimpleNamespace(
            twist=SimpleNamespace(
                linear=SimpleNamespace(x=0.0, y=0.0),
                angular=SimpleNamespace(z=0.0),
            ),
            covariance=[0.0] * 36,
        ),
    )
    observer.clock_ns = 10
    observer.clock_advance_count = 2
    observer.localization = []
    observer.scans = [SimpleNamespace(received_steady_ns=now_ns)]
    observer.wheel = [SimpleNamespace(received_steady_ns=now_ns)]
    observer.imu = [SimpleNamespace(received_steady_ns=now_ns)]
    observer.odometry = [
        SimpleNamespace(stamp_ns=1, value=odom_value),
        SimpleNamespace(stamp_ns=2, value=odom_value),
    ]
    observer.sensor_health_snapshot = lambda: {
        'context': None, 'barrier_sequence': 0, 'barrier_stamp_ns': 0,
        'clock_rollback': False, 'clock_ns': 10, 'clock_advance_count': 2,
        'lifecycle': None, 'scans': tuple(observer.scans),
        'wheel': tuple(observer.wheel), 'imu': tuple(observer.imu),
        'odometry': tuple(observer.odometry), 'receipts': (),
        'localization': tuple(observer.localization),
    }
    topics = {'/odometry/filtered': {'publishers': (('ekf_filter_node',),)}}
    observer.graph_snapshot = lambda: {
        'nodes': {name for name, client in observer.lifecycle_clients.items()
                  if clock() >= client.node_ready_at},
        'topics': topics,
    }
    runner._a1_asset_check = lambda: {'pass': True, 'measured': {}}
    runner.config = {'map_identity': {'map_id': 'test_map'}}
    runner._topic_samples_ready = lambda: True
    runner._last_sensor_health_success = {
        'snapshot': {'clock_advance_count': 2,
                     'odometry': tuple(observer.odometry)},
        'ros_now_ns': 10, 'steady_now_ns': now_ns,
        'facts': {
            'scan': observer.scans[0], 'wheel_odometry': observer.wheel[0],
            'imu': observer.imu[0], 'filtered_odometry': observer.odometry[-1],
        },
    }
    runner._localization_ok = lambda: (True, None)
    runner._tf_chain_usable = lambda _stamp: True
    runner._tf_ownership_ready = lambda: True
    runner._tf_a4_ready = lambda stamp: (
        setattr(
            runner, '_last_tf_a4_evidence',
            {'ownership_basis': 'fake canonical graph', 'stamp_ns': stamp})
        or True)
    runner._a4_current_ready = lambda: True
    runner._last_tf_a4_evidence = {'test': 'canonical fake graph'}
    runner._startup_rearm = lambda _deadline: rearm_calls.append(clock())


def _safety_core_startup_runner(monkeypatch, *, authorized=True,
                                rearm_behavior='apply'):
    """Build a real production startup path around the pure Safety core."""
    from collections import deque
    from mecanum_nav_rl.observations.step07_research_acceptance import StampedFact
    from mecanum_nav_rl.observations.step07_research_observer import (
        Step07ResearchObserver,
    )
    from mecanum_nav_rl.runtime_safety.safety_contract import (
        SafetyLifecycleCore,
    )

    class Clock:
        seconds = 10.0
        ros_ns = 1_200_000_000

        def steady_ns(self):
            return int(self.seconds * 1_000_000_000)

        def sleep(self, seconds):
            if rearm_behavior == 'stay_nonready':
                self.seconds += 1_000.0
            else:
                self.seconds += seconds

    clock = Clock()
    monkeypatch.setattr(runner_module.time, 'monotonic_ns', clock.steady_ns)
    monkeypatch.setattr(runner_module.time, 'sleep', clock.sleep)
    core = SafetyLifecycleCore()
    core.configure(1_000_000_000)
    core.activate(1_100_000_000)
    assert core.snapshot().reason == 'ACTIVE_REARM_REQUIRED'
    assert core.snapshot().motion_permitted is False

    observer = object.__new__(Step07ResearchObserver)
    observer._lock = threading.RLock()
    observer._config_hash = 'a' * 64
    observer._steady_ns = clock.steady_ns
    observer.lifecycle = None
    observer.context = None
    observer.barrier_sequence = 0
    observer.barrier_stamp_ns = 0
    observer.barrier_event_stamp_ns = 0
    observer.action_events = []
    observer.clock_rollback = False
    observer.clock_ns = clock.ros_ns
    observer.clock_advance_count = 2
    observer.scans = deque()
    observer.wheel = deque()
    observer.imu = deque()
    observer.odometry = deque()
    observer.receipts = deque()
    observer.localization = deque()
    observer.node = SimpleNamespace(get_clock=lambda: SimpleNamespace(
        now=lambda: SimpleNamespace(nanoseconds=clock.ros_ns)))

    primary = {'Unconfigured': 0, 'Inactive': 1, 'Active': 2}
    barrier = {'INIT': 0, 'READY': 1, 'NON_READY': 2, 'FAULT': 3}

    def publish_identity(identity):
        stamp = SimpleNamespace(sec=clock.ros_ns // 1_000_000_000,
                                nanosec=clock.ros_ns % 1_000_000_000)
        message = SimpleNamespace(
            header=SimpleNamespace(stamp=stamp, frame_id='base_link'),
            barrier_stamp=SimpleNamespace(
                sec=identity.barrier_ros_time_ns // 1_000_000_000,
                nanosec=identity.barrier_ros_time_ns % 1_000_000_000),
            episode_generation=identity.episode_generation,
            reset_epoch=identity.reset_epoch,
            runtime_generation=identity.runtime_generation,
            sequence=identity.sequence,
            primary_state=primary[identity.primary_state.value],
            barrier_state=barrier[identity.barrier_state.value],
            motion_permitted=identity.motion_permitted,
            reason=identity.reason,
        )
        Step07ResearchObserver._lifecycle_cb(observer, message)

    publish_identity(core.snapshot())
    context = observer.context
    from mecanum_nav_rl.observations.step07_research_observer import (
        Step07ResearchObserver as Observer,
    )
    observer.sensor_health_snapshot = lambda: Observer.sensor_health_snapshot(
        observer)
    observer.graph_snapshot = lambda: {
        'nodes': set(), 'topics': {
            '/mecanum/safety_lifecycle_state': {
                'publishers': (('safety_lifecycle',),)},
            '/odometry/filtered': {
                'publishers': (('ekf_filter_node',),)},
        },
    }
    observer.wait_for_actions = lambda timeout_sec: True
    observer.recording_ready = lambda _topics: (True, ())
    observer.executor_error = None
    observer.lifecycle_clients = {}
    observer._GetState = SimpleNamespace(Request=lambda: object())

    def add_fact(stream, stamp_ns, frame_id, value):
        stream.append(StampedFact(
            stamp_ns, clock.steady_ns(), frame_id, value, context))

    sample_stamp = clock.ros_ns - 10_000_000
    scan = SimpleNamespace(
        header=SimpleNamespace(frame_id='lidar_frame'),
        ranges=[1.0] * 720, angle_min=-math.pi,
        angle_increment=(2 * math.pi / 720), range_min=0.1,
        range_max=10.0,
    )
    add_fact(observer.scans, sample_stamp, 'lidar_frame', scan)
    wheel = SimpleNamespace(
        header=SimpleNamespace(frame_id='odom'), child_frame_id='base_link')
    add_fact(observer.wheel, sample_stamp, 'odom', wheel)
    imu = SimpleNamespace(header=SimpleNamespace(frame_id='base_link'))
    add_fact(observer.imu, sample_stamp, 'base_link', imu)

    def odom(stamp_ns):
        return SimpleNamespace(
            header=SimpleNamespace(frame_id='odom'),
            child_frame_id='base_link',
            pose=SimpleNamespace(
                pose=SimpleNamespace(position=SimpleNamespace(x=0.0, y=0.0)),
                covariance=[0.0] * 36),
            twist=SimpleNamespace(
                twist=SimpleNamespace(
                    linear=SimpleNamespace(x=0.0, y=0.0),
                    angular=SimpleNamespace(z=0.0)),
                covariance=[0.0] * 36),
        )

    add_fact(
        observer.odometry, sample_stamp - 1, 'base_link',
        odom(sample_stamp - 1),
    )
    add_fact(
        observer.odometry, sample_stamp, 'base_link', odom(sample_stamp),
    )
    runner = object.__new__(ResearchAcceptanceRunner)
    runner.observer = observer
    runner.process_owner = SimpleNamespace(processes=[])
    runner.now_steady = lambda: clock.seconds
    runner.started_steady = 0.0
    runner.state = CampaignState()
    runner.log_stream = None
    runner.output = None
    runner.config = {'map_identity': {'map_id': 'test_map'}}
    runner.authorization = {'sim_estop_release_authorized': authorized}
    runner.rearm_requested = False
    runner._last_node_ros_now_ns = clock.ros_ns - 1
    runner._node_ros_advance_count = 2
    runner._a1_asset_check = lambda: {'pass': True, 'measured': {}}
    runner._wait_nav2_ready = lambda _deadline: {}
    runner._localization_ok = lambda *args, **kwargs: (True, None)
    runner._a4_current_ready = lambda: True
    runner._last_tf_a4_evidence = {'fixture': 'offline'}
    calls = {'rearm': 0, 'recorder': 0, 'mission': 0}

    class Future:
        def __init__(self, success=True):
            self.success = success

        def done(self):
            return True

        def exception(self):
            return None

        def result(self):
            return SimpleNamespace(success=self.success)

    def request_rearm():
        calls['rearm'] += 1
        if rearm_behavior == 'apply':
            publish_identity(core.rearm(clock.ros_ns))
        return Future(success=rearm_behavior != 'refuse')

    observer.request_rearm = request_rearm
    original_recording_ready = runner._graph_ready_for_recording

    def recording_gate():
        calls['recorder'] += 1
        assert core.snapshot().barrier_state.value == 'READY'
        assert core.snapshot().motion_permitted is True
        return original_recording_ready()

    runner._graph_ready_for_recording = recording_gate
    runner._mission = lambda: calls.update(mission=calls['mission'] + 1)
    runner.start_observer = lambda: None
    runner.start_runtime_children = lambda: None
    runner.shutdown = lambda: None
    runner.close = lambda: None
    runner.evaluate_and_write = lambda: {'overall': 'OFFLINE_TEST_ONLY'}
    return runner, observer, core, clock, calls, publish_identity


def test_production_wait_ready_rearms_real_nonready_core_before_mission(
        monkeypatch):
    """Use real configure/activate/rearm before recorder and mission gates."""
    runner, observer, core, _clock, calls, _publish = (
        _safety_core_startup_runner(monkeypatch))
    assert observer.lifecycle.value['barrier_state'] == 2
    assert observer.lifecycle.value['motion_permitted'] is False

    report = runner.execute()

    assert report['overall'] == 'OFFLINE_TEST_ONLY'
    assert core.snapshot().barrier_state.value == 'READY'
    assert observer.lifecycle.value['motion_permitted'] is True
    assert calls == {'rearm': 1, 'recorder': 1, 'mission': 1}


@pytest.mark.parametrize(('authorized', 'behavior', 'failure'), [
    (False, 'apply', 'SIM_ESTOP_RELEASE_AUTHORIZATION_REQUIRED'),
    (True, 'refuse', 'SAFETY_REARM_REFUSED'),
    (True, 'stay_nonready', 'SAFETY_READY_AFTER_REARM_TIMEOUT'),
])
def test_production_startup_rearm_failures_never_admit_recorder_or_mission(
        monkeypatch, authorized, behavior, failure):
    """Keep mission admission closed when authorization or rearm fails."""
    runner, _observer, core, _clock, calls, _publish = (
        _safety_core_startup_runner(
            monkeypatch, authorized=authorized, rearm_behavior=behavior))

    report = runner.execute()

    assert report['overall'] == 'OFFLINE_TEST_ONLY'
    assert runner.state.primary_failure['primary_failure'] == failure
    assert calls['rearm'] == (0 if not authorized else 1)
    assert calls['recorder'] == 0
    assert calls['mission'] == 0
    assert core.snapshot().barrier_state.value == 'NON_READY'


@pytest.mark.parametrize('mutation', [
    'fault', 'stale_lifecycle', 'stale_sensor', 'clock_rollback',
])
def test_pre_rearm_startup_still_rejects_fault_stale_inputs_and_rollback(
        monkeypatch, mutation):
    """Keep fault, freshness and rollback checks active before rearm."""
    from mecanum_nav_rl.observations.step07_research_acceptance import (
        StampedFact,
    )

    runner, observer, core, clock, _calls, publish_identity = (
        _safety_core_startup_runner(monkeypatch))
    if mutation == 'fault':
        publish_identity(core.fault('TEST_FAULT', clock.ros_ns))
        with pytest.raises(AcceptanceFailure, match='SAFETY_LIFECYCLE_FAULT'):
            runner._topic_samples_ready()
        return
    if mutation == 'clock_rollback':
        observer.clock_rollback = True
        with pytest.raises(AcceptanceFailure, match='SIM_CLOCK_ROLLBACK'):
            runner._topic_samples_ready()
        return

    fact = (observer.lifecycle if mutation == 'stale_lifecycle'
            else observer.scans[0])
    stale = StampedFact(
        fact.stamp_ns, fact.received_steady_ns - 600_000_000,
        fact.frame_id, fact.value, fact.context, fact.identity,
    )
    if mutation == 'stale_lifecycle':
        observer.lifecycle = stale
    else:
        observer.scans[0] = stale
    assert runner._topic_samples_ready() is False


def test_post_rearm_ready_without_motion_permission_is_not_lifecycle_ready():
    """Require motion permission even when the barrier reports READY."""
    from mecanum_nav_rl.observations.step07_research_acceptance import (
        Context, StampedFact,
    )
    context = Context(0, 0, 1, 'a' * 64)
    life = StampedFact(100, time.monotonic_ns(), 'base_link', {
        'primary_state': 2, 'barrier_state': 1, 'motion_permitted': False,
        'reason': 'EXPLICIT_REARM',
    }, context)
    observer = SimpleNamespace(
        node=SimpleNamespace(get_clock=lambda: SimpleNamespace(
            now=lambda: SimpleNamespace(nanoseconds=100))),
        sensor_health_snapshot=lambda: {
            'context': context, 'clock_rollback': False, 'lifecycle': life,
        },
        lifecycle=life, context=context,
    )
    _bind_health_snapshot(observer, context=context, ros_now_ns=100,
                          lifecycle=life, odometry=())
    runner = object.__new__(ResearchAcceptanceRunner)
    runner.observer = observer
    runner._last_node_ros_now_ns = 100
    runner._node_ros_advance_count = 2

    assert runner._lifecycle_ready() is False


def test_production_wait_ready_requeries_until_all_six_are_active(
    monkeypatch,
):
    """Startup re-queries non-active states until every Nav2 node is Active."""
    runner, observer, clients, clock = _nav2_lifecycle_fixture(
        monkeypatch,
        responses={'map_server': [(1, 'unconfigured', 0.0),
                                  (2, 'inactive', 0.0),
                                  (3, 'active', 0.0)]},
    )
    rearm_calls = []
    _prepare_production_startup(
        runner, observer, clock, rearm_calls=rearm_calls)

    runner._wait_ready()

    assert clients['map_server'].calls == 3
    assert 'A6' not in runner.state.facts
    assert runner.state.facts['A4']['pass'] is True
    assert rearm_calls and rearm_calls[0] >= clock()


def test_production_wait_ready_waits_for_delayed_services_and_nodes(
    monkeypatch,
):
    """Action discovery alone does not satisfy lifecycle readiness."""
    delays = {name: index * 0.1 for index, name in
              enumerate(REQUIRED_NAV2_LIFECYCLE_NODES)}
    runner, observer, clients, clock = _nav2_lifecycle_fixture(
        monkeypatch, service_ready_at=delays, node_ready_at=delays,
    )
    rearm_calls = []
    _prepare_production_startup(
        runner, observer, clock, rearm_calls=rearm_calls)
    actions = []
    observer.wait_for_actions = (
        lambda timeout_sec: actions.append(timeout_sec) or True)

    runner._wait_ready()

    assert actions
    assert clock() >= max(delays.values())
    assert all(client.calls == 1 for client in clients.values())
    assert rearm_calls and rearm_calls[0] >= max(delays.values())


def test_nav2_round_requeries_active_nodes_and_requires_full_active_round(
    monkeypatch,
):
    """An Active result from a failed round cannot satisfy the next round."""
    runner, _observer, clients, clock = _nav2_lifecycle_fixture(
        monkeypatch,
        responses={
            'map_server': [(3, 'active', 0.0), (2, 'inactive', 0.0),
                           (3, 'active', 0.0)],
            'planner_server': [(2, 'inactive', 0.0), (3, 'active', 0.0),
                               (3, 'active', 0.0)],
        },
    )

    result = runner._wait_nav2_ready(1.0)

    assert clients['map_server'].calls == 3
    assert clients['planner_server'].calls == 3
    assert all(result[name]['id'] == 3
               for name in REQUIRED_NAV2_LIFECYCLE_NODES)
    assert clock() < 1.0


def test_nav2_alternating_rounds_timeout_without_mission(monkeypatch):
    """Alternating states time out before recorder or mission gates."""
    runner, observer, clients, clock = _nav2_lifecycle_fixture(
        monkeypatch,
        responses={
            'map_server': [(3, 'active', 0.0), (2, 'inactive', 0.0),
                           (3, 'active', 0.0), (2, 'inactive', 0.0)],
            'amcl': [(2, 'inactive', 0.0), (3, 'active', 0.0),
                     (2, 'inactive', 0.0), (3, 'active', 0.0)],
        },
    )
    rearm_calls = []
    _prepare_production_startup(
        runner, observer, clock, rearm_calls=rearm_calls)
    runner.started_steady = -459.55
    calls = []
    runner.start_observer = lambda: calls.append('observer')
    runner.start_runtime_children = lambda: calls.append('children')
    runner._graph_ready_for_recording = (
        lambda: calls.append('recorder') or True)
    runner._mission = lambda: calls.append('mission')
    runner.shutdown = lambda: calls.append('cleanup')
    runner.output = None
    runner.evaluate_and_write = lambda: {'overall': 'FAIL'}
    runner.close = lambda: None

    report = runner.execute()

    assert report['overall'] == 'FAIL'
    assert runner.state.primary_failure['stage'] == 'A6_NAV2'
    assert 'recorder' not in calls and 'mission' not in calls
    assert not rearm_calls
    assert clients['map_server'].calls >= 3
    assert clients['amcl'].calls >= 3
    assert max(client.max_outstanding for client in clients.values()) == 1


def test_nav2_node_requeried_after_disappear_and_reappear(monkeypatch):
    """A returning node must answer again after disappearing mid-round."""
    runner, observer, clients, clock = _nav2_lifecycle_fixture(
        monkeypatch,
        responses={
            'map_server': [(3, 'active', 0.0), (2, 'inactive', 0.0),
                           (3, 'active', 0.0)],
            'controller_server': [(3, 'active', 0.4), (3, 'active', 0.0)],
        },
    )

    def graph_snapshot():
        nodes = {name for name, client in clients.items()
                 if clock() >= client.node_ready_at}
        if 0.15 <= clock() < 0.3:
            nodes.discard('map_server')
        return {'nodes': nodes, 'topics': {}}

    observer.graph_snapshot = graph_snapshot

    result = runner._wait_nav2_ready(1.5)

    assert clients['map_server'].calls == 3
    assert result['map_server'] == {'id': 3, 'label': 'active'}
    assert clock() >= 0.5


def test_nav2_all_active_after_failed_round_continues_startup(monkeypatch):
    """A later complete Active round allows startup to continue."""
    runner, observer, clients, clock = _nav2_lifecycle_fixture(
        monkeypatch,
        responses={
            'amcl': [(2, 'inactive', 0.0), (3, 'active', 0.0)],
        },
    )
    rearm_calls = []
    _prepare_production_startup(
        runner, observer, clock, rearm_calls=rearm_calls)

    runner._wait_ready()

    assert 'A6' not in runner.state.facts
    assert clients['amcl'].calls == 2
    assert rearm_calls and rearm_calls[0] >= clock()


def test_nav2_action_server_must_remain_ready_at_conclusion(monkeypatch):
    """Readiness requires action discovery at the final conclusion check."""
    runner, observer, _clients, _clock = _nav2_lifecycle_fixture(monkeypatch)
    action_results = iter((True, True, False, False))
    action_timeouts = []

    def wait_for_actions(timeout_sec):
        action_timeouts.append(timeout_sec)
        return next(action_results, False)

    observer.wait_for_actions = wait_for_actions

    with pytest.raises(
            AcceptanceFailure, match='NAV2_ACTION_SERVER_UNAVAILABLE'):
        runner._wait_nav2_ready(0.15)

    assert runner.state.facts['A6']['pass'] is False
    assert action_timeouts and all(
        timeout == 0.0 for timeout in action_timeouts)


def test_nav2_missing_graph_node_times_out_with_node_state_and_cleans_pending(
    monkeypatch,
):
    """Missing node times out and cleans pending work."""
    runner, _observer, clients, _clock = _nav2_lifecycle_fixture(
        monkeypatch,
        node_ready_at={'amcl': 10.0},
        responses={'controller_server': [(3, 'active', 1.0)]},
    )

    with pytest.raises(
            AcceptanceFailure,
            match=('NAV2_LIFECYCLE_STARTUP_DEADLINE_EXPIRED:'
                   'amcl:NODE_NOT_DISCOVERED')):
        runner._wait_nav2_ready(0.25)

    failure = runner.state.facts['A6']
    assert failure['pass'] is False
    assert failure['measured']['node'] == 'amcl'
    assert failure['measured']['state']['label'] == 'NODE_NOT_DISCOVERED'
    assert clients['controller_server'].removed
    assert all(client.outstanding == 0 for client in clients.values())


def test_nav2_inactive_node_times_out_with_last_state_and_no_request_storm(
    monkeypatch,
):
    """An inactive node is re-queried at a bounded cadence until timeout."""
    runner, _observer, clients, clock = _nav2_lifecycle_fixture(
        monkeypatch,
        responses={'planner_server': [(2, 'inactive', 0.0)]},
    )

    with pytest.raises(
            AcceptanceFailure,
            match=(r'NAV2_LIFECYCLE_STARTUP_DEADLINE_EXPIRED:'
                   r'planner_server:inactive\(2\)')):
        runner._wait_nav2_ready(0.31)

    measured = runner.state.facts['A6']['measured']
    assert measured['node'] == 'planner_server'
    assert measured['state'] == {'id': 2, 'label': 'inactive'}
    assert clients['planner_server'].calls <= 4
    assert max(client.max_outstanding for client in clients.values()) == 1


@pytest.mark.parametrize(
    'client_map',
    [
        {},
        {name: _Nav2FakeClient(_Nav2FakeClock())
         for name in REQUIRED_NAV2_LIFECYCLE_NODES[:-1]},
    ],
    ids=['empty', 'missing-node'],
)
def test_nav2_empty_or_missing_lifecycle_client_set_cannot_pass(
    monkeypatch, client_map,
):
    """A missing or empty lifecycle client set cannot satisfy A6."""
    runner, observer, _clients, _clock = _nav2_lifecycle_fixture(monkeypatch)
    observer.lifecycle_clients = client_map

    with pytest.raises(
            AcceptanceFailure, match='NAV2_LIFECYCLE_CLIENT_SET_INVALID'):
        runner._wait_nav2_ready(1.0)

    assert runner.state.facts['A6']['pass'] is False


@pytest.mark.parametrize(
    'response',
    [None,
     SimpleNamespace(current_state=SimpleNamespace(id=255, label='bogus')),
     SimpleNamespace(current_state=SimpleNamespace(id=3, label='inactive'))],
    ids=['missing-current-state', 'unknown-state', 'id-label-mismatch'],
)
def test_nav2_invalid_get_state_response_fails_closed(monkeypatch, response):
    """Malformed state responses fail closed and leave no pending request."""
    runner, observer, clients, _clock = _nav2_lifecycle_fixture(monkeypatch)
    clients['amcl'].responses = [(response, 'ignored', 0.0)]

    with pytest.raises(
            AcceptanceFailure, match='NAV2_GET_STATE_RESPONSE_INVALID:amcl'):
        runner._wait_nav2_ready(1.0)

    assert runner.state.facts['A6']['pass'] is False
    assert runner.state.facts['A6']['measured']['node'] == 'amcl'
    assert (runner.state.facts['A6']['measured']['state']['label']
            == 'INVALID_RESPONSE')
    assert all(client.outstanding == 0 for client in clients.values())


def test_nav2_deadline_expired_with_active_responses_still_fails(monkeypatch):
    """An Active response observed after the deadline does not pass A6."""
    runner, _observer, _clients, _clock = _nav2_lifecycle_fixture(
        monkeypatch,
        responses={name: [(3, 'active', 0.1)]
                   for name in REQUIRED_NAV2_LIFECYCLE_NODES},
    )

    with pytest.raises(
            AcceptanceFailure,
            match=(r'NAV2_LIFECYCLE_STARTUP_DEADLINE_EXPIRED:'
                   r'bt_navigator:active\(3\)')):
        runner._wait_nav2_ready(0.1)

    assert runner.state.facts['A6']['pass'] is False
    assert runner.state.facts['A6']['measured']['state'] == {
        'id': 3, 'label': 'active',
    }


@pytest.mark.parametrize(
    'failure_kind', ['process_exit', 'executor_exception'])
def test_nav2_wait_failure_cleans_pending_and_blocks_later_gates(
    monkeypatch, failure_kind,
):
    """Startup exceptions clean up and block all later gates."""
    runner, observer, clients, clock = _nav2_lifecycle_fixture(
        monkeypatch,
        responses={'controller_server': [(3, 'active', 1.0)]},
    )
    rearm_calls = []
    _prepare_production_startup(
        runner, observer, clock, rearm_calls=rearm_calls)
    calls = []
    runner.start_observer = lambda: calls.append('observer')
    runner.start_runtime_children = lambda: calls.append('children')
    runner._graph_ready_for_recording = (
        lambda: calls.append('recorder') or True)
    runner._mission = lambda: calls.append('mission')
    runner.output = None
    runner.shutdown = lambda: calls.append('cleanup')
    runner.evaluate_and_write = lambda: {'overall': 'FAIL'}
    runner.close = lambda: None

    if failure_kind == 'process_exit':
        runner.process_owner.processes = [SimpleNamespace(
            name='composite',
            process=SimpleNamespace(
                poll=lambda: 23 if clock() >= 0.15 else None),
        )]
    else:
        clock.callbacks.append(
            lambda now: setattr(
                observer, 'executor_error', RuntimeError('executor stopped'))
            if now >= 0.15 else None
        )

    report = runner.execute()

    assert report['overall'] == 'FAIL'
    assert runner.state.primary_failure['stage'] == 'A6_NAV2'
    assert 'recorder' not in calls and 'mission' not in calls
    assert 'cleanup' in calls
    assert not rearm_calls
    assert clients['controller_server'].removed
    assert all(client.outstanding == 0 for client in clients.values())
