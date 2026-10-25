from __future__ import annotations

import json
import io
from pathlib import Path
import signal
import sys
import time
from types import ModuleType
from types import SimpleNamespace

import pytest

from run_step07_research_acceptance import (
    AcceptanceFailure, CampaignState, OwnedProcess, ProcessOwner, ResearchAcceptanceRunner,
    atomic_json, load_json, validate_resolved_config, verify_runtime_authorization,
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
    assert "/navigate_to_pose/_action/status" in recorder


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


def test_tf_owner_admission_uses_observed_edges_and_rejects_duplicate_or_wrong_publishers():
    runner = object.__new__(ResearchAcceptanceRunner)
    runner.observer = SimpleNamespace(tf_edge_owners={
        ("map", "odom"): {"amcl"}, ("odom", "base_link"): {"ekf_filter_node"},
        ("base_link", "lidar_frame"): {"robot_state_publisher"}})
    owners = runner._observed_tf_owners()
    assert owners == {"map->odom": "amcl", "odom->base_link": "ekf_filter_node",
                      "base_link->lidar_frame": "robot_state_publisher"}
    runner.observer.tf_edge_owners[("map", "odom")].add("other_localizer")
    with pytest.raises(AcceptanceFailure, match="TF_EDGE_OWNER_MISMATCH"):
        runner._observed_tf_owners()


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
