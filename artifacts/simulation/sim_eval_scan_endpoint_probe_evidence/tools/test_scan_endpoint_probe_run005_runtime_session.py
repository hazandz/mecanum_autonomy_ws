"""Offline fake-only tests for Run 005 persistent discovery/session boundaries."""

import ast
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[4]
RUNNER_PATH = ROOT / "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/run_scan_endpoint_probe_run005_session.py"
GUARD_PATH = ROOT / "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/tools/scan_endpoint_probe_run005_runtime_guard.py"
sys.path.insert(0, str(RUNNER_PATH.parent))
spec = importlib.util.spec_from_file_location("run005_session_tested", RUNNER_PATH)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

def test_binding_import_is_delayed_and_before_guard_consumption():
    assert "from gz.transport import Node, NodeOptions" in RUNNER_PATH.read_text(encoding="utf-8")
    events = []
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp); run = root / runner.RUN_DIRECTORY
        checked = {"run_dir": run, "guard_path": root / "guard", "guard_context": {},
            "guard_state_before": runner.guard.PENDING, "manifest": {"authority_packet": {}, "source_pins": {}},
            "integration_commit": "a" * 40}
        runner.preflight = lambda *args, **kwargs: checked
        def unavailable():
            events.append("import")
            raise ImportError("binding unavailable")
        runner.guard.consume_guard = lambda *args: events.append("consume")
        try:
            runner.run_session(root, root / "guard", run, runner.RUN_ID, runner.PARTITION, "a" * 40,
                import_binding=unavailable)
        except runner.TransportBindingUnavailable as exc:
            assert str(exc) == "GZ_TRANSPORT_PYTHON_BINDING_UNAVAILABLE"
        else:
            raise AssertionError("missing binding must fail")
        assert events == ["import"]
        assert not run.exists()

def test_single_persistent_node_delayed_service_and_exact_create_probe_order():
    events = []
    class Options:
        partition = None
    class Node:
        def __init__(self, options):
            events.append(("node", options.partition)); self.calls = 0
        def service_list(self):
            self.calls += 1
            return [] if self.calls == 1 else [runner.CREATE_SERVICE]
    class Proc:
        next_pid = 40000
        def __init__(self, argv, **kwargs):
            self.argv = argv; self.pid = Proc.next_pid; Proc.next_pid += 1; self.rc = None
            events.append(("popen", argv[0:4]))
            if "create" in argv:
                kwargs["stdout"].write(runner.CREATE_SUCCESS)
                self.rc = 0
        def poll(self): return self.rc
        def wait(self, timeout=None): self.rc = 0; return self.rc
    def fake_popen(argv, **kwargs): return Proc(argv, **kwargs)
    def fake_command(argv, **kwargs):
        events.append(("probe", argv))
        return SimpleNamespace(returncode=0, stdout=b'{"outcome":"EXACTLY_ONE_MATCH"}', stderr=b"")
    def fake_pgid(pid): return pid
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp); run = root / runner.RUN_DIRECTORY; guard_file = root / "guard"
        checked = {"root": root, "run_dir": run, "guard_path": guard_file, "guard_context": {},
            "guard_state_before": runner.guard.PENDING, "manifest": {"authority_packet": {}, "source_pins": {}},
            "integration_commit": "b" * 40}
        runner.preflight = lambda *args, **kwargs: checked
        consumed = []
        runner.guard.consume_guard = lambda *args: consumed.append(True)
        class FakeClock:
            now = 0.0
            def __call__(self): return self.now
        clk = FakeClock()
        def sleep(seconds): clk.now += seconds
        record = runner.run_session(root, guard_file, run, runner.RUN_ID, runner.PARTITION, "b" * 40,
            import_binding=lambda: (Node, Options), popen=fake_popen, command_runner=fake_command,
            pgid_getter=fake_pgid, signal_group=lambda *args: None, proc_root=root / "proc",
            clock=clk, sleeper=sleep)
        assert consumed == [True]
        assert events.count(("node", runner.PARTITION)) == 1
        assert record["service_readiness"]["ready"] is True
        assert len(record["service_readiness"]["attempts"]) == 2
        assert record["create"]["readiness"] is True
        assert record["terminal_outcome"] == "GZ_LASERSCAN_ENDPOINT_OBSERVED_NOT_PINNED"
        assert sum(event[0] == "probe" for event in events) == 1

def test_missing_exact_service_prevents_create_and_probe_but_tears_server_down():
    calls = []
    class Options: partition = None
    class FakeNode:
        def __init__(self, options): calls.append("node")
        def service_list(self): return ["/world/wp06_scan_probe_world/create_extra"]
    class Proc:
        pid = 50000
        def __init__(self, argv, **kwargs): self.rc = None; calls.append("server")
        def poll(self): return self.rc
        def wait(self, timeout=None): self.rc = 0; return 0
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp); run = root / runner.RUN_DIRECTORY
        checked = {"root": root, "run_dir": run, "guard_path": root / "guard", "guard_context": {},
            "guard_state_before": runner.guard.PENDING, "manifest": {"authority_packet": {}, "source_pins": {}},
            "integration_commit": "c" * 40}
        runner.preflight = lambda *args, **kwargs: checked
        runner.guard.consume_guard = lambda *args: None
        clk = [0.0]
        def clock(): return clk[0]
        def sleep(seconds): clk[0] += seconds
        rec = runner.run_session(root, root / "guard", run, runner.RUN_ID, runner.PARTITION, "c" * 40,
            import_binding=lambda: (FakeNode, Options), popen=lambda argv, **kw: Proc(argv, **kw),
            pgid_getter=lambda pid: pid, signal_group=lambda *a: None, proc_root=root / "proc",
            clock=clock, sleeper=sleep)
        assert calls == ["node", "server"]
        assert rec["service_readiness"]["ready"] is False
        assert rec["create"] is None and rec["probe"] is None

def test_no_short_lived_service_cli_or_node_creation_inside_polling_loop():
    source = RUNNER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert "gz service --list" not in source
    assert "subprocess" not in source[source.index("def _wait_for_create_service"):source.index("def parse_proc_stat")]
    fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_wait_for_create_service")
    names = [node.id for node in ast.walk(fn) if isinstance(node, ast.Name)]
    assert "Node" not in names and "NodeOptions" not in names
    assert "_service_snapshot" in names
    snapshot = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_service_snapshot")
    assert "service_list" in [node.attr for node in ast.walk(snapshot) if isinstance(node, ast.Attribute)]

def test_create_success_requires_zero_exit_and_exact_bytes():
    source = RUNNER_PATH.read_text(encoding="utf-8")
    assert "rc == 0 and CREATE_SUCCESS in raw" in source
    assert "CREATE_SUCCESS = b\"Entity creation successful.\"" in source
    assert "finally:" in source[source.index("create_log ="):source.index("sleeper(STABILIZATION_S)")]
    assert "create_torn_down = True" in source

def test_teardown_process_accounting_distinguishes_zombie_live_and_group_mismatch():
    assert runner.parse_proc_stat(b"10 (name with ) paren) S 1 77 77 0") == ("S", 77)
    assert runner.parse_proc_stat(b"10 (z) Z 1 77 77 0")[0] == "Z"
    class Process:
        pid = 700
        def poll(self): return 0
        def wait(self, timeout=None): return 0
    signals = []
    result = runner.teardown(Process(), 701, owned_pgid=700, signal_group=lambda *args: signals.append(args))
    assert result["outcome"] == "UNEXPECTED_PGID_NO_SIGNAL"
    assert signals == []

def test_proc_snapshot_records_zombies_separately_from_live_members():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "11").mkdir(); (root / "12").mkdir()
        (root / "11/stat").write_bytes(b"11 (worker with ) char) Z 1 88 88 0")
        (root / "12/stat").write_bytes(b"12 (worker) S 1 88 88 0")
        snapshot = runner.snapshot_group(88, root)
        assert snapshot == {"live_member_pids": [12], "zombie_member_pids": [11]}

def test_zombie_only_group_is_not_reported_live_during_teardown():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp); (root / "21").mkdir()
        (root / "21/stat").write_bytes(b"21 (zombie) Z 1 21 21 0")
        class Process:
            pid = 21
            def poll(self): return 0
            def wait(self, timeout=None): return 0
        now = [0.0]
        result = runner.teardown(Process(), 21, owned_pgid=21, proc_root=root,
            signal_group=lambda *args: None, clock=lambda: now[0], sleeper=lambda s: now.__setitem__(0, now[0] + s))
        assert result["outcome"] == "STOPPED"
        assert result["final_snapshot"]["live_member_pids"] == []
        assert result["final_snapshot"]["zombie_member_pids"] == [21]

def test_live_member_after_sigkill_is_reported_with_evidence():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp); (root / "31").mkdir()
        (root / "31/stat").write_bytes(b"31 (worker) S 1 31 31 0")
        class Process:
            pid = 31
            def poll(self): return None
            def wait(self, timeout=None): raise subprocess.TimeoutExpired("fake", timeout)
        now = [0.0]
        result = runner.teardown(Process(), 31, owned_pgid=31, proc_root=root,
            signal_group=lambda *args: None, clock=lambda: now[0], sleeper=lambda s: now.__setitem__(0, now[0] + s))
        assert result["outcome"] == "LIVE_PROCESS_GROUP_AFTER_SIGKILL"
        assert result["final_snapshot"]["live_member_pids"] == [31]

def test_guard_is_pending_capacity_one_and_rejects_second_acquire():
    guard_spec = importlib.util.spec_from_file_location("run005_guard_tested", GUARD_PATH)
    guard_module = importlib.util.module_from_spec(guard_spec)
    guard_spec.loader.exec_module(guard_module)
    context = {"run_id": runner.RUN_ID, "gz_partition": runner.PARTITION}
    seed = {"schema": guard_module.SCHEMA, "capacity": 1, "state": guard_module.PENDING, "context": context}
    assert guard_module.validate_guard(seed, context)["state"] == guard_module.PENDING
    consumed = dict(seed, state=guard_module.CONSUMED)
    try:
        guard_module.validate_guard(consumed, context)
    except guard_module.GuardError:
        pass
    else:
        raise AssertionError("second acquire must be rejected")

def test_guard_atomic_transition_consumes_once_in_temporary_directory():
    guard_spec = importlib.util.spec_from_file_location("run005_guard_atomic_tested", GUARD_PATH)
    guard_module = importlib.util.module_from_spec(guard_spec)
    guard_spec.loader.exec_module(guard_module)
    context = {"run_id": runner.RUN_ID, "gz_partition": runner.PARTITION}
    seed = {"schema": guard_module.SCHEMA, "capacity": 1, "state": guard_module.PENDING, "context": context}
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "guard.json"
        path.write_bytes(guard_module.canonical_json_bytes(seed))
        digest = guard_module.consume_guard(path, context)
        updated = guard_module.load_guard_bytes(path.read_bytes())
        assert updated["state"] == guard_module.CONSUMED
        assert digest == hashlib.sha256(path.read_bytes()).hexdigest()
        try:
            guard_module.consume_guard(path, context)
        except guard_module.GuardError:
            pass
        else:
            raise AssertionError("capacity-one guard must reject second consumption")

def test_candidate_manifest_source_pins_are_exact_and_historical_files_not_changed():
    manifest_path = ROOT / "docs/governance/evidence/WP-06_SCAN_PROBE_RUN_005_RUNTIME_GUARD_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["run_id"] == runner.RUN_ID
    for relative, expected in manifest["source_pins"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
    assert (ROOT / "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/approval_guards/WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_005.json").exists()
    guard = json.loads((ROOT / runner.GUARD_PATH).read_text(encoding="utf-8"))
    assert guard["state"] == "PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION"
    assert guard["context"]["source_pins"] == manifest["source_pins"]
    assert runner._sha(manifest_path.read_bytes()) == guard["context"]["manifest_sha256"]

def test_create_failure_is_accounted_in_finally_and_never_probes():
    calls = []
    class Options: partition = None
    class FakeNode:
        def __init__(self, options): pass
        def service_list(self): return [runner.CREATE_SERVICE]
    class Proc:
        next_pid = 81000
        def __init__(self, argv, **kwargs):
            self.argv = argv; self.pid = Proc.next_pid; Proc.next_pid += 1
            self.rc = 7 if "create" in argv else None
            if "create" in argv:
                calls.append("create")
                kwargs["stdout"].write(b"creation rejected")
        def poll(self): return self.rc
        def wait(self, timeout=None): return self.rc
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp); run = root / runner.RUN_DIRECTORY; guard_file = root / "guard"
        empty_proc = root / "empty_proc"; empty_proc.mkdir()
        checked = {"root": root, "run_dir": run, "guard_path": guard_file, "guard_context": {},
            "guard_state_before": runner.guard.PENDING, "manifest": {"authority_packet": {}, "source_pins": {}},
            "integration_commit": "d" * 40}
        runner.preflight = lambda *args, **kwargs: checked
        runner.guard.consume_guard = lambda *args: None
        now = [0.0]
        def sleep(seconds): now[0] += seconds
        record = runner.run_session(root, guard_file, run, runner.RUN_ID, runner.PARTITION, "d" * 40,
            import_binding=lambda: (FakeNode, Options),
            popen=lambda argv, **kw: Proc(argv, **kw), command_runner=lambda *a, **kw: calls.append("probe"),
            pgid_getter=lambda pid: pid, signal_group=lambda *a: None, proc_root=empty_proc,
            clock=lambda: now[0], sleeper=sleep)
        assert calls == ["create"]
        assert record["create"]["readiness"] is False
        assert record["teardown"]["create"]["outcome"] == "STOPPED"
        assert record["terminal_outcome"] == "CREATE_NOT_READY"

def test_existing_run002_003_004_paths_are_not_in_candidate_diff_allowlist():
    # Direct structural boundary: Run005 tests/source never point at prior run artifacts.
    for text in (RUNNER_PATH.read_text(encoding="utf-8"), GUARD_PATH.read_text(encoding="utf-8")):
        assert "RUN_002" not in text and "RUN_003" not in text and "RUN_004" not in text
