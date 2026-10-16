import hashlib
import ast
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from scan_endpoint_probe_runtime_guard import (  # noqa: E402
    CapacityOneGuard,
    EXPECTED_AUTHORIZATION,
    EXPECTED_PACKET_SHA256,
    GuardRejected,
    SCHEMA,
    canonical_json_bytes,
)


ROOT = TOOLS.parents[3]
GUARD_TEMPLATE = (
    ROOT
    / "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/approval_guards/"
    / "WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_001.json"
)


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result


def _fresh_guard(tmp_path):
    path = tmp_path / "guard.json"
    shutil.copyfile(GUARD_TEMPLATE, path)
    return path


def _acquire(guard, **overrides):
    args = {
        "packet_sha256": EXPECTED_PACKET_SHA256,
        "run_id": EXPECTED_AUTHORIZATION["run_id"],
        "guard_context": EXPECTED_AUTHORIZATION,
        "source_pins": EXPECTED_AUTHORIZATION["source_pins"],
        "command_literal": EXPECTED_AUTHORIZATION["command_template"],
        "partition": EXPECTED_AUTHORIZATION["gz_partition"],
    }
    args.update(overrides)
    return guard.acquire(**args)


def _read_json(path):
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert not raw.endswith(b"\n")
    parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    assert canonical_json_bytes(parsed) == raw
    return parsed


def test_guard_packet_is_canonical_and_has_capacity_one_state():
    packet = _read_json(GUARD_TEMPLATE)
    assert set(packet) == {"authorization", "packet_sha256", "schema", "state"}
    assert packet["schema"] == SCHEMA
    assert packet["state"] == "AUTHORIZED_NOT_CONSUMED"
    assert packet["authorization"] == EXPECTED_AUTHORIZATION
    assert packet["authorization"]["capacity"] == 1
    assert hashlib.sha256(canonical_json_bytes(packet["authorization"])).hexdigest() == EXPECTED_PACKET_SHA256
    assert packet["packet_sha256"] == EXPECTED_PACKET_SHA256


def test_guard_acquires_once_consumes_atomically_and_rejects_second_acquire(tmp_path):
    path = _fresh_guard(tmp_path)
    guard = CapacityOneGuard(path)
    assert _acquire(guard) == EXPECTED_AUTHORIZATION["run_id"]
    record = _read_json(path)
    assert record["state"] == "CONSUMED"
    assert record["consumption"] == {
        "outcome": "IN_PROGRESS",
        "run_id": EXPECTED_AUTHORIZATION["run_id"],
    }
    with pytest.raises(GuardRejected):
        _acquire(guard)


@pytest.mark.parametrize(
    "field,value",
    [
        ("packet_sha256", "0" * 64),
        ("source_pins", {"probe_module": {"sha256": "0" * 64}}),
        ("command_literal", ["gz", "topic", "-l"]),
        ("partition", "another_partition"),
        ("run_id", "RUN_002"),
        ("guard_context", {"profile": "other_profile"}),
    ],
)
def test_guard_rejects_packet_pin_command_partition_run_or_context_mismatch(
    tmp_path, field, value
):
    guard = CapacityOneGuard(_fresh_guard(tmp_path))
    with pytest.raises(GuardRejected):
        _acquire(guard, **{field: value})


def test_guard_rejects_packet_payload_tampering(tmp_path):
    path = _fresh_guard(tmp_path)
    packet = _read_json(path)
    packet["authorization"]["capacity"] = 2
    path.write_bytes(canonical_json_bytes(packet))
    with pytest.raises(GuardRejected):
        _acquire(CapacityOneGuard(path))


@pytest.mark.parametrize("outcome", ["PASS", "FAIL", "WRAPPER_TIMEOUT", "INTERRUPTED"])
def test_every_runtime_outcome_is_durably_consumed(tmp_path, outcome):
    guard = CapacityOneGuard(_fresh_guard(tmp_path))
    run_id = _acquire(guard)
    guard.finalize(run_id=run_id, outcome=outcome)
    record = _read_json(guard.guard_path)
    assert record["state"] == "CONSUMED"
    assert record["consumption"]["outcome"] == outcome
    with pytest.raises(GuardRejected):
        _acquire(guard)


def test_guard_source_is_pure_and_does_not_reuse_contact_producer_guard():
    source = (TOOLS / "scan_endpoint_probe_runtime_guard.py").read_text(encoding="utf-8")
    lowered = source.lower()
    for forbidden in (
        "import subprocess",
        "import rclpy",
        "import gazebo",
        "import ros_gz_bridge",
        "contact_producer_evidence",
        "typed_scene_approval_guard",
    ):
        assert forbidden not in lowered
    assert "scan_endpoint_probe_runtime_guard" in sys.modules
    assert not any("contact_producer_evidence" in name for name in sys.modules)


def _copy_future_run_sources(tmp_path):
    repository = tmp_path / "repository"
    for relative in (
        EXPECTED_AUTHORIZATION["source_pins"]["gazebo_source"]["path"],
        EXPECTED_AUTHORIZATION["source_pins"]["probe_module"]["path"],
        EXPECTED_AUTHORIZATION["source_pins"]["probe_descriptor"]["path"],
    ):
        destination = repository / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    guard_path = repository / (
        "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/approval_guards/"
        "WP06_6D_SIM_EVAL_SCAN_ENDPOINT_PROBE_RUN_001.json"
    )
    guard_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(GUARD_TEMPLATE, guard_path)
    return repository, guard_path


def test_supervisor_pass_is_shell_free_single_call_and_records_observation(tmp_path):
    from run_scan_endpoint_probe_once import run_scan_endpoint_probe_once

    repository, guard_path = _copy_future_run_sources(tmp_path)
    calls = []
    probe_json = json.dumps(
        {
            "outcome": "EXACTLY_ONE_MATCH",
            "observed_endpoints": [
                {
                    "message_type": "gz.msgs.LaserScan",
                    "status": "OBSERVED_NOT_PINNED",
                    "topic": "/world/example/model/robot/link/lidar/sensor/lidar/scan",
                }
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    def fake_runner(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, probe_json, "")

    result = run_scan_endpoint_probe_once(
        repository,
        guard_path,
        EXPECTED_AUTHORIZATION["run_id"],
        command_runner=fake_runner,
        utc_clock=lambda: "2026-10-16T00:00:00.000000Z",
    )
    assert len(calls) == 1
    command, kwargs = calls[0]
    assert command[0] == "env"
    assert command[1] == "GZ_PARTITION=wp06_scan_probe_run_001"
    assert command[2] == f"PYTHONPATH={repository}/ros2_ws/src/mecanum_nav_bringup"
    assert command[3:] == [
        "python3",
        "-m",
        "mecanum_nav_bringup.sim_eval_scan_endpoint_probe",
    ]
    assert kwargs["shell"] is False
    assert kwargs["timeout"] == 75
    assert result["outcome"] == "EXACTLY_ONE_MATCH"
    assert result["probe_result"]["observed_endpoints"][0]["status"] == "OBSERVED_NOT_PINNED"
    assert "launcher-managed escalation" in result["timeout_cleanup"]
    run_directory = (
        repository
        / "artifacts/simulation/sim_eval_scan_endpoint_probe_evidence/runs"
        / EXPECTED_AUTHORIZATION["run_id"]
    )
    assert {"result.json", "stdout.txt", "stderr.txt"} == {
        path.name for path in run_directory.iterdir()
    }
    assert _read_json(guard_path)["state"] == "CONSUMED"


@pytest.mark.parametrize(
    "runner_kind,expected_outcome",
    [
        ("failure", "PROBE_COMMAND_FAILED"),
        ("timeout", "WRAPPER_TIMEOUT"),
        ("interrupt", "INTERRUPTED"),
    ],
)
def test_supervisor_failure_timeout_and_interruption_consume_without_retry(
    tmp_path, runner_kind, expected_outcome
):
    from run_scan_endpoint_probe_once import run_scan_endpoint_probe_once

    repository, guard_path = _copy_future_run_sources(tmp_path)
    calls = []

    def fake_runner(command, **kwargs):
        calls.append((command, kwargs))
        if runner_kind == "failure":
            return subprocess.CompletedProcess(command, 7, "", "fixture failure")
        if runner_kind == "timeout":
            raise subprocess.TimeoutExpired(command, 75, output="partial", stderr="timeout")
        raise KeyboardInterrupt

    result = run_scan_endpoint_probe_once(
        repository,
        guard_path,
        EXPECTED_AUTHORIZATION["run_id"],
        command_runner=fake_runner,
        utc_clock=lambda: "2026-10-16T00:00:00.000000Z",
    )
    assert len(calls) == 1
    assert result["outcome"] == expected_outcome
    assert _read_json(guard_path)["state"] == "CONSUMED"
    with pytest.raises(GuardRejected):
        CapacityOneGuard(guard_path).acquire(
            packet_sha256=EXPECTED_PACKET_SHA256,
            run_id=EXPECTED_AUTHORIZATION["run_id"],
            guard_context=EXPECTED_AUTHORIZATION,
            source_pins=EXPECTED_AUTHORIZATION["source_pins"],
            command_literal=EXPECTED_AUTHORIZATION["command_template"],
            partition=EXPECTED_AUTHORIZATION["gz_partition"],
        )


def test_supervisor_checks_source_pins_before_acquire(tmp_path):
    from run_scan_endpoint_probe_once import (
        GUARD_RELATIVE_PATH,
        RUNS_RELATIVE_PATH,
        SupervisorPreflightError,
        run_scan_endpoint_probe_once,
    )

    repository, guard_path = _copy_future_run_sources(tmp_path)
    source = repository / EXPECTED_AUTHORIZATION["source_pins"]["probe_module"]["path"]
    source.write_bytes(source.read_bytes() + b"# drift\n")
    called = []
    with pytest.raises(SupervisorPreflightError):
        run_scan_endpoint_probe_once(
            repository,
            GUARD_RELATIVE_PATH,
            EXPECTED_AUTHORIZATION["run_id"],
            command_runner=lambda *args, **kwargs: called.append((args, kwargs)),
        )
    assert not called
    assert _read_json(guard_path)["state"] == "AUTHORIZED_NOT_CONSUMED"
    assert not (repository / RUNS_RELATIVE_PATH).exists()


def test_supervisor_rejects_existing_run_directory_without_consuming_guard(tmp_path):
    from run_scan_endpoint_probe_once import (
        RUNS_RELATIVE_PATH,
        SupervisorPreflightError,
        run_scan_endpoint_probe_once,
    )

    repository, guard_path = _copy_future_run_sources(tmp_path)
    run_directory = repository / RUNS_RELATIVE_PATH / EXPECTED_AUTHORIZATION["run_id"]
    run_directory.mkdir(parents=True)
    called = []
    with pytest.raises(SupervisorPreflightError):
        run_scan_endpoint_probe_once(
            repository,
            guard_path,
            EXPECTED_AUTHORIZATION["run_id"],
            command_runner=lambda *args, **kwargs: called.append((args, kwargs)),
        )
    assert not called
    assert _read_json(guard_path)["state"] == "AUTHORIZED_NOT_CONSUMED"


def test_supervisor_source_is_single_shot_shell_free_and_has_no_forbidden_runtime_apis():
    source = (TOOLS / "run_scan_endpoint_probe_once.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    for forbidden in (
        "rclpy",
        "launch",
        "launch_ros",
        "tf2_ros",
        "ros_gz_bridge",
        "ros_gz_sim",
        "gz",
        "gazebo",
        "socket",
    ):
        assert not any(name == forbidden or name.startswith(forbidden + ".") for name in imported)
    assert "subprocess" in imported
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "Popen"
        for node in ast.walk(tree)
    )
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "command_runner"
    ]
    assert len(calls) == 1
    assert '"ros2 topic"' not in source
    assert '"ros2 node"' not in source
    assert '"ros2 launch"' not in source
    assert '"gz topic -e"' not in source
    assert "shell=True" not in source
