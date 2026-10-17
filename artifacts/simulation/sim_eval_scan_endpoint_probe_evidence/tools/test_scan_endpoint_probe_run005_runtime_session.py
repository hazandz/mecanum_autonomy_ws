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
INTEGRATION_BASE = "83f13d67ab212fec03b18cd2ed830349b7013ab3"
sys.path.insert(0, str(RUNNER_PATH.parent))
spec = importlib.util.spec_from_file_location("run005_session_tested", RUNNER_PATH)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

def test_transport13_import_and_node_capability_are_preacquire_only():
    source = RUNNER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = [(node.module, tuple(alias.name for alias in node.names))
                for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert ("gz.transport13", ("Node", "NodeOptions")) in imports
    assert not any(module == "gz.transport" or (module or "").startswith("gz.transport.")
                   for module, _ in imports)
    helper = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                  and node.name == "_create_preacquire_transport_node")
    session = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                   and node.name == "run_session")
    helper_text = ast.get_source_segment(source, helper)
    assert helper_text.index("NodeOptions()") < helper_text.index("options.partition = PARTITION")
    assert helper_text.index("options.partition = PARTITION") < helper_text.index("Node(options)")
    assert helper_text.index("Node(options)") < helper_text.index('getattr(node, "service_list", None)')
    session_text = ast.get_source_segment(source, session)
    assert session_text.index("transport_node_factory()") < session_text.index('checked["run_dir"].mkdir')
    assert session_text.index('checked["run_dir"].mkdir') < session_text.index("guard.consume_guard")
    assert session_text.index("guard.consume_guard") < session_text.index('server_log =')
    assert session_text.count("transport_node_factory()") == 1
    assert "GZ_TRANSPORT13_BINDING_OR_NODE_PREACQUIRE_UNAVAILABLE" in source


def test_every_preacquire_failure_keeps_guard_pending_and_starts_nothing(monkeypatch):
    class Options:
        def __init__(self): self._partition = None
        @property
        def partition(self): return self._partition
        @partition.setter
        def partition(self, value): self._partition = value
    class BadPartitionOptions:
        @property
        def partition(self): return None
        @partition.setter
        def partition(self, value): raise RuntimeError("partition rejected")
    class WrongPartitionOptions:
        def __init__(self): self.partition = None
        def __setattr__(self, name, value):
            object.__setattr__(self, name, "wrong-partition" if name == "partition" else value)
    class GoodNode:
        def __init__(self, options): self.options = options
        def service_list(self): return []
    class NoServiceListNode:
        def __init__(self, options): pass
    class FailingNode:
        def __init__(self, options): raise RuntimeError("node construction failed")
    class FailingOptions:
        def __init__(self): raise RuntimeError("options construction failed")

    cases = [
        ("import", lambda: (_ for _ in ()).throw(ImportError("binding unavailable"))),
        ("options", lambda: (FailingNode, FailingOptions)),
        ("partition", lambda: (GoodNode, BadPartitionOptions)),
        ("partition_value", lambda: (GoodNode, WrongPartitionOptions)),
        ("node", lambda: (FailingNode, Options)),
        ("service_list", lambda: (NoServiceListNode, Options)),
    ]
    for name, binding_loader in cases:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); run = root / runner.RUN_DIRECTORY; guard_file = root / "guard.json"
            guard_before = runner.guard.canonical_json_bytes({
                "schema": runner.guard.SCHEMA, "capacity": 1,
                "state": runner.guard.PENDING, "context": {"run_id": runner.RUN_ID}})
            guard_file.write_bytes(guard_before)
            checked = {"root": root, "run_dir": run, "guard_path": guard_file, "guard_context": {},
                "guard_state_before": runner.guard.PENDING, "manifest": {"authority_packet": {}, "source_pins": {}},
                "review_commit": "a" * 40, "integration_base": INTEGRATION_BASE}
            monkeypatch.setattr(runner, "preflight", lambda *args, **kwargs: checked)
            consumed = []; started = []
            monkeypatch.setattr(runner.guard, "consume_guard", lambda *args: consumed.append(True))
            def no_process(*args, **kwargs):
                started.append(args[0] if args else None)
                raise AssertionError("process must not start before guard acquisition")
            try:
                runner.run_session(root, guard_file, run, runner.RUN_ID, runner.PARTITION,
                    "a" * 40, INTEGRATION_BASE,
                    transport_node_factory=lambda: runner._create_preacquire_transport_node(binding_loader),
                    popen=no_process, command_runner=no_process)
            except runner.TransportBindingUnavailable as exc:
                assert str(exc) == runner.PREACQUIRE_UNAVAILABLE
            else:
                raise AssertionError(f"preacquire {name} failure must stop")
            assert not consumed
            assert not started
            assert guard_file.read_bytes() == guard_before
            assert runner.guard.load_guard_bytes(guard_before)["state"] == runner.guard.PENDING
            assert not run.exists()

def test_single_persistent_node_delayed_service_and_exact_create_probe_order(monkeypatch):
    events = []
    nodes = []
    class Options:
        partition = None
    class Node:
        def __init__(self, options):
            events.append(("node", options.partition)); self.options = options
            self.calls = 0; nodes.append(self)
        def service_list(self):
            events.append(("service_list", self))
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
            "review_commit": "b" * 40, "integration_base": INTEGRATION_BASE}
        monkeypatch.setattr(runner, "preflight", lambda *args, **kwargs: checked)
        consumed = []
        def consume(*args):
            assert len(nodes) == 1
            assert nodes[0].options.partition == runner.PARTITION
            assert run.exists()
            events.append("consume")
            consumed.append(True)
        monkeypatch.setattr(runner.guard, "consume_guard", consume)
        class FakeClock:
            now = 0.0
            def __call__(self): return self.now
        clk = FakeClock()
        def sleep(seconds): clk.now += seconds
        def make_node():
            assert not run.exists()
            return runner._create_preacquire_transport_node(lambda: (Node, Options))
        record = runner.run_session(root, guard_file, run, runner.RUN_ID, runner.PARTITION, "b" * 40, INTEGRATION_BASE,
            transport_node_factory=make_node,
            popen=fake_popen, command_runner=fake_command,
            pgid_getter=fake_pgid, signal_group=lambda *args: None, proc_root=root / "proc",
            clock=clk, sleeper=sleep)
        assert consumed == [True]
        assert record["review_commit"] == "b" * 40
        assert record["integration_base"] == INTEGRATION_BASE
        assert "integration_commit" not in record
        assert events.count(("node", runner.PARTITION)) == 1
        assert len(nodes) == 1
        assert all(event[1] is nodes[0] for event in events
                   if isinstance(event, tuple) and event[0] == "service_list")
        assert events.index(("node", runner.PARTITION)) < events.index("consume")
        assert events.index("consume") < next(i for i, event in enumerate(events)
                                                if isinstance(event, tuple) and event[0] == "popen")
        assert record["service_readiness"]["ready"] is True
        assert len(record["service_readiness"]["attempts"]) == 2
        assert record["create"]["readiness"] is True
        assert record["terminal_outcome"] == "GZ_LASERSCAN_ENDPOINT_OBSERVED_NOT_PINNED"
        assert sum(event[0] == "probe" for event in events) == 1

def test_missing_exact_service_prevents_create_and_probe_but_tears_server_down(monkeypatch):
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
            "review_commit": "c" * 40, "integration_base": INTEGRATION_BASE}
        monkeypatch.setattr(runner, "preflight", lambda *args, **kwargs: checked)
        monkeypatch.setattr(runner.guard, "consume_guard", lambda *args: None)
        clk = [0.0]
        def clock(): return clk[0]
        def sleep(seconds): clk[0] += seconds
        rec = runner.run_session(root, root / "guard", run, runner.RUN_ID, runner.PARTITION, "c" * 40, INTEGRATION_BASE,
            transport_node_factory=lambda: runner._create_preacquire_transport_node(lambda: (FakeNode, Options)),
            popen=lambda argv, **kw: Proc(argv, **kw),
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
    assert guard["capacity"] == 1
    assert guard["context"]["source_pins"] == manifest["source_pins"]
    assert runner._sha(manifest_path.read_bytes()) == guard["context"]["manifest_sha256"]
    transport = manifest["transport_discovery"]
    assert transport["import"] == "from gz.transport13 import Node, NodeOptions"
    assert transport["host_prerequisite_package"] == "python3-gz-transport13"
    assert transport["binding_and_node_capability_before_guard_acquire"] is True
    assert manifest["authority_packet"]["sha256"] == manifest["source_pins"][runner.DECISION_PATH]

def test_create_failure_is_accounted_in_finally_and_never_probes(monkeypatch):
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
            "review_commit": "d" * 40, "integration_base": INTEGRATION_BASE}
        monkeypatch.setattr(runner, "preflight", lambda *args, **kwargs: checked)
        monkeypatch.setattr(runner.guard, "consume_guard", lambda *args: None)
        now = [0.0]
        def sleep(seconds): now[0] += seconds
        record = runner.run_session(root, guard_file, run, runner.RUN_ID, runner.PARTITION, "d" * 40, INTEGRATION_BASE,
            transport_node_factory=lambda: runner._create_preacquire_transport_node(lambda: (FakeNode, Options)),
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

REVIEW_COMMIT = "a" * 40

def _fake_git_runner(root, *, head=REVIEW_COMMIT, integration=INTEGRATION_BASE,
                     ancestor=True, blob_overrides=None):
    blob_overrides = blob_overrides or {}
    calls = []
    def run(argv, **kwargs):
        args = argv[3:]
        calls.append(args)
        if args == ["remote", "get-url", "origin"]:
            return SimpleNamespace(returncode=0, stdout=b"https://github.com/hazandz/mecanum_autonomy_ws.git\n", stderr=b"")
        if args == ["rev-parse", "HEAD"]:
            return SimpleNamespace(returncode=0, stdout=(head + "\n").encode(), stderr=b"")
        if args == ["rev-parse", "origin/integration/implementation"]:
            return SimpleNamespace(returncode=0, stdout=(integration + "\n").encode(), stderr=b"")
        if args[:2] == ["merge-base", "--is-ancestor"]:
            code = 0 if ancestor and args[2:] == [INTEGRATION_BASE, REVIEW_COMMIT] else 1
            return SimpleNamespace(returncode=code, stdout=b"", stderr=b"")
        if args == ["status", "--porcelain"]:
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        if len(args) == 2 and args[0] == "show":
            revision, path = args[1].split(":", 1)
            if revision != REVIEW_COMMIT:
                return SimpleNamespace(returncode=1, stdout=b"", stderr=b"wrong revision")
            raw = blob_overrides.get(path, (Path(root) / path).read_bytes())
            return SimpleNamespace(returncode=0, stdout=raw, stderr=b"")
        raise AssertionError(f"unexpected fake git argv: {args}")
    return run, calls

def test_review_commit_runtime_topology_uses_candidate_blobs_and_leaves_guard_pending():
    original_guard = (ROOT / runner.GUARD_PATH).read_bytes()
    git_runner, calls = _fake_git_runner(ROOT)
    checked = runner.preflight(ROOT, ROOT / runner.GUARD_PATH, ROOT / runner.RUN_DIRECTORY,
        runner.RUN_ID, runner.PARTITION, REVIEW_COMMIT, INTEGRATION_BASE, git_runner=git_runner)
    assert checked["review_commit"] == REVIEW_COMMIT
    assert checked["integration_base"] == INTEGRATION_BASE
    assert checked["guard_state_before"] == runner.guard.PENDING
    assert (ROOT / runner.GUARD_PATH).read_bytes() == original_guard
    blob_revisions = [args[1].split(":", 1)[0] for args in calls if args and args[0] == "show"]
    assert blob_revisions and set(blob_revisions) == {REVIEW_COMMIT}
    # The integration SHA is only the ancestry/ref baseline, never a source-blob selector.
    assert ["merge-base", "--is-ancestor", INTEGRATION_BASE, REVIEW_COMMIT] in calls

def test_review_preflight_rejects_topology_and_candidate_blob_mismatches_before_acquire():
    guard_file = ROOT / runner.GUARD_PATH
    guard_before = guard_file.read_bytes()
    run_dir = ROOT / runner.RUN_DIRECTORY
    variants = [
        {"name": "integration-equals-review", "integration": REVIEW_COMMIT},
        {"name": "integration-ref-mismatch", "integration": "b" * 40},
        {"name": "unexpected-expected-base", "expected_base": "b" * 40},
        {"name": "head-mismatch", "head": "c" * 40},
        {"name": "review-not-descended-from-base", "ancestor": False},
        {"name": "source-blob-mismatch", "blob_overrides": {runner.WORLD_PATH: b"different world bytes"}},
        {"name": "manifest-blob-mismatch", "blob_overrides": {runner.MANIFEST_PATH: b"different manifest bytes"}},
    ]
    for variant in variants:
        kwargs = {k: v for k, v in variant.items() if k not in {"name", "expected_base"}}
        git_runner, _ = _fake_git_runner(ROOT, **kwargs)
        try:
            runner.preflight(ROOT, guard_file, run_dir, runner.RUN_ID, runner.PARTITION,
                REVIEW_COMMIT, variant.get("expected_base", INTEGRATION_BASE), git_runner=git_runner)
        except runner.SessionError:
            pass
        else:
            raise AssertionError(f"preflight accepted {variant['name']}")
        assert guard_file.read_bytes() == guard_before
        assert json.loads(guard_before.decode("utf-8"))["state"] == runner.guard.PENDING

def test_binding_failure_after_valid_review_preflight_keeps_guard_pending_and_creates_no_run_dir():
    guard_file = ROOT / runner.GUARD_PATH
    guard_before = guard_file.read_bytes()
    events = []
    git_runner, _ = _fake_git_runner(ROOT)
    try:
        runner.run_session(ROOT, guard_file, ROOT / runner.RUN_DIRECTORY, runner.RUN_ID,
            runner.PARTITION, REVIEW_COMMIT, INTEGRATION_BASE, git_runner=git_runner,
            transport_node_factory=lambda: runner._create_preacquire_transport_node(
                lambda: (events.append("import"), (_ for _ in ()).throw(ImportError("missing binding")))[1]),
            popen=lambda *a, **kw: (_ for _ in ()).throw(AssertionError("process must not start")))
    except runner.TransportBindingUnavailable:
        pass
    else:
        raise AssertionError("binding failure must fail before acquisition")
    assert events == ["import"]
    assert guard_file.read_bytes() == guard_before
    assert json.loads(guard_before.decode("utf-8"))["state"] == runner.guard.PENDING
    assert not (ROOT / runner.RUN_DIRECTORY).exists()

def test_cli_and_run_record_distinguish_review_commit_from_integration_base():
    tree = ast.parse(RUNNER_PATH.read_text(encoding="utf-8"))
    source = RUNNER_PATH.read_text(encoding="utf-8")
    assert '"expected-review-commit"' in source
    assert '"expected-integration-base"' in source
    assert "expected-integration-commit" not in source
    assert '"review_commit": expected_review_commit' in source
    assert '"integration_base": expected_integration_base' in source
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"Popen", "run"}
                   and any(isinstance(arg, ast.Constant) and arg.value == "gz service --list" for arg in node.args)
                   for node in ast.walk(tree))
