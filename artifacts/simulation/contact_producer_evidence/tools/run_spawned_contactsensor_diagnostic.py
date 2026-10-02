#!/usr/bin/env python3
"""One-shot, read-only spawned ContactSensor diagnostic supervisor.

No bridge, collector, analyzer, publisher, service client, action client, or
simulator-control request is created. Every live command is an approved
information query or the existing Gazebo launch; shutdown is SIGINT-only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from approval_bound_guard import acquire_guard, consume_guard, initialize_guard

ROOT = Path("/home/hazan/mecanum_autonomy_ws")
WS = ROOT / "ros2_ws"
ART = ROOT / "artifacts/simulation/contact_producer_evidence"
PACKET = ROOT / "docs/S3_D3_Spawned_ContactSensor_Diagnostic_Run_Approval_Packet_DRAFT.md"
GUARD = ART / "approval_guards/S3.3.20_SPAWNED_CONTACTSENSOR_DIAGNOSTIC_RUN.json"
APPROVAL_ID = "S3.3.20_SPAWNED_CONTACTSENSOR_DIAGNOSTIC_RUN"
WORLD = "world_demo"
WORLD_SHA256 = "1c50f90d151a12559d426796c5d153c829b8777a5b4e8ef94c007a2023f6e271"
MODEL = "ROBOT_URDF_final"
LINK = "base_link"
COLLISION = "s3_d3_base_contact_collision"
SENSOR = "s3_d3_base_contact_sensor"
TOPIC_HYPOTHESIS = "/s3_d3/contact/raw"
GZ_CONTACTS_TYPE = "gz.msgs.Contacts"
QUERY_TIMEOUT_SECONDS = 20.0
SHUTDOWN_WAIT_SECONDS = 20.0


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def context() -> dict[str, Any]:
    if not PACKET.is_file():
        raise RuntimeError("approval packet unavailable")
    return {
        "approval_id": APPROVAL_ID,
        "authority_packet": "docs/S3_D3_Spawned_ContactSensor_Diagnostic_Run_Approval_Packet_DRAFT.md",
        "authority_packet_sha256": sha256(PACKET),
        "world": WORLD,
        "world_sha256": WORLD_SHA256,
        "literals": {
            "model": MODEL,
            "link": LINK,
            "collision": COLLISION,
            "sensor": SENSOR,
            "configured_topic_hypothesis": TOPIC_HYPOTHESIS,
            "bridge": "none",
            "ros_collector": "none",
            "raw_contact_analyzer": "none",
        },
    }


def ros_shell(command: str) -> list[str]:
    return ["/bin/bash", "-lc", f"source /opt/ros/jazzy/setup.bash && source {WS}/install/setup.bash && {command}"]


def command_record(command: list[str], *, model: str | None = None, link: str | None = None) -> dict[str, Any]:
    """Run a created process once. Timeout path sends only SIGINT to its group."""
    record: dict[str, Any] = {
        "command": command,
        "command_literal": " ".join(command),
        "timestamp_utc": now(),
        "model_identity": model,
        "link_identity": link,
        "timeout": False,
        "parse_status": "NOT_PARSED",
        "stdout": "",
        "stderr": "",
        "exit_code": None,
    }
    process = subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=QUERY_TIMEOUT_SECONDS)
        record.update({"stdout": stdout, "stderr": stderr, "exit_code": process.returncode})
    except subprocess.TimeoutExpired:
        record["timeout"] = True
        os.killpg(process.pid, signal.SIGINT)
        try:
            stdout, stderr = process.communicate(timeout=SHUTDOWN_WAIT_SECONDS)
            record.update({"stdout": stdout or "", "stderr": stderr or "", "exit_code": process.returncode})
        except subprocess.TimeoutExpired:
            record["stderr"] = "SIGINT-only shutdown incomplete for query process"
            record["shutdown_incomplete"] = True
    return record


def parse_models(record: dict[str, Any]) -> tuple[bool, str]:
    """Parse only the observed local ``gz model --list`` grammar fail-closed.

    Accepted grammar is one exact ``Available models:`` header, followed by zero
    or more non-empty entries of the exact form ``<space>*-<space>+NAME``.
    ``MODEL_IDENTITY_CONFIRMED`` requires exactly one entry whose NAME equals
    ``ROBOT_URDF_final``. Substrings, prefixes, suffixes, and scoped names do
    not match.
    """
    record["accepted_grammar"] = "one 'Available models:' header; entries: ^[ \t]*-[ \t]+([^ \t\r\n]+)[ \t]*$"
    if record.get("timeout") or record.get("exit_code") != 0 or record.get("shutdown_incomplete"):
        record.update({"parse_status": "NOT_PARSED", "model_identity_status": "DIAGNOSTIC_INCOMPLETE_ROBOT_ENTITY"})
        return False, "query failed, timed out, or shutdown incomplete"
    stdout, stderr = record.get("stdout"), record.get("stderr")
    if not isinstance(stdout, str) or not isinstance(stderr, str):
        record.update({"parse_status": "NOT_PARSED", "model_identity_status": "DIAGNOSTIC_INCOMPLETE_ROBOT_ENTITY"})
        return False, "stdout/stderr has invalid encoding or type"
    lines = stdout.splitlines()
    header_indices = [index for index, line in enumerate(lines) if line.strip() == "Available models:"]
    if len(header_indices) != 1:
        record.update({"parse_status": "NOT_PARSED", "model_identity_status": "DIAGNOSTIC_INCOMPLETE_ROBOT_ENTITY"})
        return False, "expected exactly one Available models header"
    entry_lines = [line for line in lines[header_indices[0] + 1:] if line.strip()]
    import re
    entry_pattern = re.compile(r"^[ \t]*-[ \t]+([^ \t\r\n]+)[ \t]*$")
    names: list[str] = []
    for line in entry_lines:
        match = entry_pattern.fullmatch(line)
        if match is None:
            record.update({"parse_status": "NOT_PARSED", "model_identity_status": "DIAGNOSTIC_INCOMPLETE_ROBOT_ENTITY"})
            return False, "model entry does not match accepted local grammar"
        names.append(match.group(1))
    count = sum(name == MODEL for name in names)
    record["parsed_model_entries"] = names
    record["parsed_model_count"] = count
    if count == 1:
        record.update({"parse_status": "PARSED", "model_identity_status": "MODEL_IDENTITY_CONFIRMED"})
        return True, "MODEL_IDENTITY_CONFIRMED"
    record.update({"parse_status": "PARSED", "model_identity_status": "DIAGNOSTIC_INCOMPLETE_ROBOT_ENTITY"})
    if count == 0:
        return False, "exact model identity absent from valid parsed entries"
    return False, "exact model identity is ambiguous"


NO_LOCAL_LINK_SENSOR_OUTPUT_GRAMMAR = "NO_LOCAL_LINK_SENSOR_OUTPUT_GRAMMAR_CONFIRMED"


def _named_query_preconditions(record: dict[str, Any], *, expected: str, kind: str) -> tuple[bool, str]:
    """Validate a named-query record without interpreting arbitrary CLI text.

    The installed local ``gz model`` wrapper documents selectors but provides no
    output grammar for either ``-l`` or ``-s``. Until a local, version-matched
    grammar is evidenced, this helper may only reject malformed query records;
    it cannot establish either identity presence or identity absence.
    """
    record.update({
        "expected_exact_identity": expected,
        "named_query_kind": kind,
        "local_grammar_status": NO_LOCAL_LINK_SENSOR_OUTPUT_GRAMMAR,
    })
    if record.get("timeout") or record.get("exit_code") != 0 or record.get("shutdown_incomplete"):
        record.update({"parse_status": "NOT_PARSED", "named_identity_status": "DIAGNOSTIC_INCOMPLETE_SENSOR_QUERY"})
        return False, "query failed, timed out, or shutdown incomplete"
    stdout, stderr = record.get("stdout"), record.get("stderr")
    if not isinstance(stdout, str) or not isinstance(stderr, str):
        record.update({"parse_status": "NOT_PARSED", "named_identity_status": "DIAGNOSTIC_INCOMPLETE_SENSOR_QUERY"})
        return False, "stdout/stderr has invalid encoding or type"
    if not stdout.strip():
        record.update({"parse_status": "NOT_PARSED", "named_identity_status": "DIAGNOSTIC_INCOMPLETE_SENSOR_QUERY"})
        return False, "empty named-query stdout"
    return True, NO_LOCAL_LINK_SENSOR_OUTPUT_GRAMMAR


def parse_link_output(record: dict[str, Any]) -> tuple[bool, bool, str]:
    """Fail closed for ``base_link`` until a local link-output grammar exists."""
    valid, reason = _named_query_preconditions(record, expected=LINK, kind="link")
    if not valid:
        record["link_identity_status"] = "DIAGNOSTIC_INCOMPLETE_SENSOR_QUERY"
        return False, False, reason
    record.update({"parse_status": "NOT_PARSED", "link_identity_status": "DIAGNOSTIC_INCOMPLETE_SENSOR_QUERY"})
    return False, False, NO_LOCAL_LINK_SENSOR_OUTPUT_GRAMMAR


def parse_sensor_output(record: dict[str, Any]) -> tuple[bool, bool, str]:
    """Fail closed for the exact sensor until a local sensor-output grammar exists.

    In particular, free text containing the literal, ``No``, or ``not`` is not
    evidence of presence or absence. Therefore this parser cannot produce
    ``SENSOR_ABSENT_AFTER_SPAWN`` under the currently verified local evidence.
    """
    valid, reason = _named_query_preconditions(record, expected=SENSOR, kind="sensor")
    if not valid:
        record["sensor_identity_status"] = "DIAGNOSTIC_INCOMPLETE_SENSOR_QUERY"
        return False, False, reason
    record.update({"parse_status": "NOT_PARSED", "sensor_identity_status": "DIAGNOSTIC_INCOMPLETE_SENSOR_QUERY"})
    return False, False, NO_LOCAL_LINK_SENSOR_OUTPUT_GRAMMAR


def parse_topics(record: dict[str, Any]) -> tuple[bool, list[str]]:
    if record["timeout"] or record["exit_code"] != 0 or record.get("shutdown_incomplete"):
        return False, []
    topics = [line.strip() for line in str(record["stdout"]).splitlines() if line.strip()]
    # A successful topic list may be empty; it is still a parseable enumeration.
    record["parse_status"] = "PARSED"
    record["parsed_topics"] = topics
    return True, topics


def static_gate(run: Path) -> tuple[bool, str, str]:
    world = WS / "src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf"
    xacro = WS / "src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro"
    gazebo = WS / "src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo"
    result: dict[str, Any] = {"stage": "static_gate", "timestamp_utc": now()}
    if sha256(world) != WORLD_SHA256:
        result.update({"stage": "world_sha256", "reason": "source world SHA-256 mismatch"})
        dump(run / "static_gate.json", result)
        return False, "world_sha256", result["reason"]
    try:
        root = ET.fromstring(world.read_text(encoding="utf-8"))
        worlds = [item for item in root.iter() if item.tag.rsplit("}", 1)[-1] == "world"]
    except ET.ParseError as exc:
        result.update({"stage": "world_name", "reason": f"malformed source SDF: {exc}"})
        dump(run / "static_gate.json", result)
        return False, "world_name", result["reason"]
    if len(worlds) != 1 or worlds[0].get("name") != WORLD:
        result.update({"stage": "world_name", "reason": "world identity mismatch"})
        dump(run / "static_gate.json", result)
        return False, "world_name", result["reason"]
    xacro_text, gazebo_text, world_text = xacro.read_text(encoding="utf-8"), gazebo.read_text(encoding="utf-8"), world.read_text(encoding="utf-8")
    literals = {
        "contact_system": world_text.count('filename="gz-sim-contact-system" name="gz::sim::systems::Contact"'),
        "collision": xacro_text.count(f'name="{COLLISION}"'),
        "sensor": gazebo_text.count(f'name="{SENSOR}"'),
        "sensor_target": gazebo_text.count(f"<collision>{COLLISION}</collision>"),
        "sensor_topic": gazebo_text.count(f"<topic>{TOPIC_HYPOTHESIS}</topic>"),
    }
    prefix = command_record(ros_shell("ros2 pkg prefix ROBOT_URDF_final_description"))
    if prefix["exit_code"] != 0 or prefix["timeout"] or not str(prefix["stdout"]).strip():
        result.update({"stage": "package_prefix", "reason": "package prefix query failed", "package_prefix": prefix, "literals": literals})
        dump(run / "static_gate.json", result)
        return False, "package_prefix", result["reason"]
    installed = Path(str(prefix["stdout"]).strip().splitlines()[-1]) / "share/ROBOT_URDF_final_description/launch/tugbot_depot.sdf"
    if not installed.is_file() or sha256(installed) != WORLD_SHA256:
        result.update({"stage": "world_sha256", "reason": "installed world SHA-256 mismatch", "installed_world": str(installed), "literals": literals})
        dump(run / "static_gate.json", result)
        return False, "world_sha256", result["reason"]
    render = command_record(ros_shell("ros2 run xacro xacro $(ros2 pkg prefix ROBOT_URDF_final_description)/share/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro"))
    rendered = str(render["stdout"])
    valid = render["exit_code"] == 0 and not render["timeout"] and all(value == 1 for value in literals.values()) and rendered.count(COLLISION) == 2 and rendered.count(SENSOR) == 1 and rendered.count(TOPIC_HYPOTHESIS) == 1
    result.update({"stage": "ready" if valid else "xacro_validation", "reason": "ready" if valid else "source/Xacro literal validation failed", "source_world_sha256": sha256(world), "installed_world_sha256": sha256(installed), "literals": literals, "xacro_render": render, "rendered_counts": {"collision": rendered.count(COLLISION), "sensor": rendered.count(SENSOR), "topic": rendered.count(TOPIC_HYPOTHESIS)}})
    dump(run / "static_gate.json", result)
    return valid, str(result["stage"]), str(result["reason"])


def launch(command: list[str], path: Path) -> tuple[subprocess.Popen[str], Any]:
    handle = path.open("w", encoding="utf-8")
    return subprocess.Popen(command, stdout=handle, stderr=subprocess.STDOUT, text=True, start_new_session=True), handle


def stop_sigint(process: subprocess.Popen[str], label: str) -> dict[str, Any]:
    record: dict[str, Any] = {"process": label, "pid": process.pid, "signal": "SIGINT"}
    if process.poll() is not None:
        record.update({"already_exited": True, "exit_code": process.returncode, "complete": True})
        return record
    os.killpg(process.pid, signal.SIGINT)
    deadline = time.monotonic() + SHUTDOWN_WAIT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            record.update({"exit_code": process.returncode, "complete": True})
            return record
        time.sleep(0.2)
    record.update({"complete": False, "status": "SHUTDOWN_INCOMPLETE"})
    return record


def query(command_text: str, *, model: str | None = None, link: str | None = None) -> dict[str, Any]:
    return command_record(ros_shell(command_text), model=model, link=link)


def offline_model_list_parser_self_test() -> tuple[bool, dict[str, Any]]:
    """Validate parser fixtures only; no subprocess, ROS, Gazebo, or guard access."""
    raw_path = ART / "run-spawned-contactsensor-diagnostic-20260926T161318Z-01/queries/01_models.json"
    raw_record = json.loads(raw_path.read_text(encoding="utf-8"))
    raw_stdout, raw_stderr = raw_record["stdout"], raw_record["stderr"]
    fixtures: dict[str, tuple[dict[str, Any], bool, str]] = {
        "s3_3_20_raw_exact_once": ({"stdout": raw_stdout, "stderr": raw_stderr, "exit_code": 0, "timeout": False}, True, "MODEL_IDENTITY_CONFIRMED"),
        "duplicate_exact": ({"stdout": "Available models:\n  - ROBOT_URDF_final\n  - ROBOT_URDF_final\n", "stderr": "", "exit_code": 0, "timeout": False}, False, "DIAGNOSTIC_INCOMPLETE_ROBOT_ENTITY"),
        "no_exact": ({"stdout": "Available models:\n  - tugbot\n", "stderr": "", "exit_code": 0, "timeout": False}, False, "DIAGNOSTIC_INCOMPLETE_ROBOT_ENTITY"),
        "near_match_names": ({"stdout": "Available models:\n  - ROBOT_URDF_final_backup\n  - prefix_ROBOT_URDF_final\n", "stderr": "", "exit_code": 0, "timeout": False}, False, "DIAGNOSTIC_INCOMPLETE_ROBOT_ENTITY"),
        "empty_output": ({"stdout": "", "stderr": "", "exit_code": 0, "timeout": False}, False, "DIAGNOSTIC_INCOMPLETE_ROBOT_ENTITY"),
        "malformed_entry": ({"stdout": "Available models:\nROBOT_URDF_final\n", "stderr": "", "exit_code": 0, "timeout": False}, False, "DIAGNOSTIC_INCOMPLETE_ROBOT_ENTITY"),
        "nonzero_exit": ({"stdout": "Available models:\n  - ROBOT_URDF_final\n", "stderr": "failure", "exit_code": 1, "timeout": False}, False, "DIAGNOSTIC_INCOMPLETE_ROBOT_ENTITY"),
        "timeout": ({"stdout": "Available models:\n  - ROBOT_URDF_final\n", "stderr": "", "exit_code": None, "timeout": True}, False, "DIAGNOSTIC_INCOMPLETE_ROBOT_ENTITY"),
        "invalid_encoding_or_type": ({"stdout": b"\xff", "stderr": "", "exit_code": 0, "timeout": False}, False, "DIAGNOSTIC_INCOMPLETE_ROBOT_ENTITY"),
    }
    results: dict[str, Any] = {}
    for name, (fixture, expected_ok, expected_status) in fixtures.items():
        case = dict(fixture)
        ok, reason = parse_models(case)
        passed = ok == expected_ok and case.get("model_identity_status") == expected_status
        results[name] = {"passed": passed, "expected_confirmed": expected_ok, "actual_confirmed": ok, "status": case.get("model_identity_status"), "reason": reason, "parsed_model_count": case.get("parsed_model_count")}
    passed = all(result["passed"] for result in results.values())
    return passed, {"offline_model_list_parser_self_test": "PASS" if passed else "FAIL", "accepted_grammar": "one Available models header; entries ^[ \t]*-[ \t]+([^ \t\r\n]+)[ \t]*$", "raw_fixture": str(raw_path), "results": results}


def offline_link_sensor_parser_self_test() -> tuple[bool, dict[str, Any]]:
    """Exercise named-output hardening in memory only; never starts a process.

    No local link/sensor output grammar is proven. Consequently, fixtures that
    contain even the exact literal must remain incomplete rather than becoming
    synthetic evidence of presence or absence.
    """
    fixtures: dict[str, dict[str, Any]] = {
        "link_exact_literal_without_verified_grammar": {"stdout": "Link: base_link\n", "stderr": "", "exit_code": 0, "timeout": False},
        "sensor_exact_literal_without_verified_grammar": {"stdout": "Sensor: s3_d3_base_contact_sensor\n", "stderr": "", "exit_code": 0, "timeout": False},
        "link_near_match": {"stdout": "Link: base_link_extra\n", "stderr": "", "exit_code": 0, "timeout": False},
        "sensor_near_match": {"stdout": "Sensor: s3_d3_base_contact_sensor_backup\n", "stderr": "", "exit_code": 0, "timeout": False},
        "link_warning_with_literal": {"stdout": "warning: base_link was requested\n", "stderr": "", "exit_code": 0, "timeout": False},
        "sensor_warning_with_literal": {"stdout": "warning: s3_d3_base_contact_sensor was requested\n", "stderr": "", "exit_code": 0, "timeout": False},
        "empty_output": {"stdout": "", "stderr": "", "exit_code": 0, "timeout": False},
        "malformed_output": {"stdout": "???\x00unstructured\n", "stderr": "", "exit_code": 0, "timeout": False},
        "nonzero_exit": {"stdout": "Link: base_link\n", "stderr": "query failure", "exit_code": 1, "timeout": False},
        "timeout": {"stdout": "Sensor: s3_d3_base_contact_sensor\n", "stderr": "", "exit_code": None, "timeout": True},
        "bytes_stdout": {"stdout": b"base_link", "stderr": "", "exit_code": 0, "timeout": False},
        "bytes_stderr": {"stdout": "Sensor: s3_d3_base_contact_sensor\n", "stderr": b"bad", "exit_code": 0, "timeout": False},
    }
    parser_cases = {
        "link": (parse_link_output, "link_identity_status"),
        "sensor": (parse_sensor_output, "sensor_identity_status"),
    }
    results: dict[str, Any] = {}
    for parser_name, (parser_function, status_key) in parser_cases.items():
        for fixture_name, fixture in fixtures.items():
            case = dict(fixture)
            parse_valid, present, reason = parser_function(case)
            passed = (
                not parse_valid
                and not present
                and case.get("parse_status") == "NOT_PARSED"
                and case.get(status_key) == "DIAGNOSTIC_INCOMPLETE_SENSOR_QUERY"
                and case.get("local_grammar_status") == NO_LOCAL_LINK_SENSOR_OUTPUT_GRAMMAR
            )
            results[f"{parser_name}:{fixture_name}"] = {
                "passed": passed,
                "parse_valid": parse_valid,
                "present": present,
                "reason": reason,
                "status": case.get(status_key),
            }
    parser_source = Path(__file__).read_text(encoding="utf-8")
    named_section = parser_source[parser_source.index("NO_LOCAL_LINK_SENSOR_OUTPUT_GRAMMAR"):parser_source.index("def parse_topics")]
    results["no_substring_or_coercion_parser"] = {
        "passed": (
            "def parse_named_output" not in named_section
            and "expected in output" not in named_section
            and 'str(record["stdout"])' not in named_section
            and '"No" in output' not in named_section
            and '"not" in output.lower()' not in named_section
        ),
        "reason": "named parsers reject arbitrary text and do not coerce bytes",
    }
    passed = all(result["passed"] for result in results.values())
    return passed, {
        "offline_link_sensor_parser_self_test": "PASS" if passed else "FAIL",
        "local_link_sensor_output_grammar": NO_LOCAL_LINK_SENSOR_OUTPUT_GRAMMAR,
        "positive_or_absence_fixture_omitted": "no local grammar proves either result",
        "results": results,
    }


def offline_self_test() -> tuple[bool, dict[str, Any]]:
    """Test a distinct context in a temporary directory only; never launches anything."""
    from approval_bound_guard import atomic_write_json
    import approval_bound_guard as guard_module
    result: dict[str, Any] = {}
    test_context = {
        "approval_id": APPROVAL_ID,
        "authority_packet": "docs/test.md",
        "authority_packet_sha256": "a" * 64,
        "world": WORLD,
        "world_sha256": WORLD_SHA256,
        "literals": {"model": MODEL, "link": LINK, "collision": COLLISION, "sensor": SENSOR, "configured_topic_hypothesis": TOPIC_HYPOTHESIS, "bridge": "none", "ros_collector": "none", "raw_contact_analyzer": "none"},
    }
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        guard = base / "guard.json"
        ok, reason = initialize_guard(guard, test_context, "2026-09-26T00:00:00Z")
        result["initialize"] = {"passed": ok, "reason": reason}
        ok, reason, lock = acquire_guard(guard, test_context)
        result["first_acquire"] = {"passed": ok and lock is not None, "reason": reason}
        consumed = False
        if ok and lock is not None:
            consumed, reason = consume_guard(guard, lock, test_context, "test-run", "INVALID", "2026-09-26T00:00:01Z")
        result["consume"] = {"passed": consumed, "reason": reason}
        ok, reason, _ = acquire_guard(guard, test_context)
        result["second_acquire_rejected"] = {"passed": not ok and reason == "approval already consumed", "reason": reason}
        mismatch = dict(test_context); mismatch["authority_packet_sha256"] = "b" * 64
        ok, reason, _ = acquire_guard(guard, mismatch)
        result["packet_hash_mismatch_rejected"] = {"passed": not ok and "authority_packet_sha256" in reason, "reason": reason}
        mismatch = dict(test_context); mismatch["world_sha256"] = "c" * 64
        ok, reason, _ = acquire_guard(guard, mismatch)
        result["world_hash_mismatch_rejected"] = {"passed": not ok and "world_sha256" in reason, "reason": reason}
        mismatch = dict(test_context); mismatch["literals"] = dict(test_context["literals"]); mismatch["literals"]["sensor"] = "wrong"
        second = base / "second.json"; initialize_guard(second, test_context, "2026-09-26T00:00:00Z")
        ok, reason, _ = acquire_guard(second, mismatch)
        result["literal_mismatch_rejected"] = {"passed": not ok and "literals" in reason, "reason": reason}
        malformed = base / "malformed.json"; malformed.write_text("not-json", encoding="utf-8")
        ok, reason, _ = acquire_guard(malformed, test_context)
        result["malformed_rejected"] = {"passed": not ok and "malformed" in reason, "reason": reason}
        locked = base / "locked.json"; initialize_guard(locked, test_context, "2026-09-26T00:00:00Z"); locked.with_name(locked.name + ".lock").mkdir()
        ok, reason, _ = acquire_guard(locked, test_context)
        result["lock_rejected"] = {"passed": not ok and "lock unavailable" in reason, "reason": reason}
        parent_file = base / "not_directory"; parent_file.write_text("x", encoding="utf-8")
        ok, reason = atomic_write_json(parent_file / "record.json", {"x": 1})
        result["atomic_write_failure_rejected"] = {"passed": not ok and "atomic-write failure" in reason, "reason": reason}
        # Confirm that this test did not mutate an unrelated historical guard.
        result["temporary_directory_only"] = {"passed": not (ART / "approval_guards" / "S3.3.15_POST_REPAIR_PASSIVE_CONTACT_RUN.json").samefile(guard) if guard.exists() else True}
    passed = all(item["passed"] for item in result.values())
    return passed, {"offline_spawned_contactsensor_guard_self_test": "PASS" if passed else "FAIL", "results": result}


def write_report(run: Path, result: dict[str, Any]) -> None:
    query_dir = run / "queries"
    query_files = sorted(item.name for item in query_dir.glob("*.json")) if query_dir.exists() else []
    report = f"""# S3 D3 Spawned ContactSensor Diagnostic Evidence Report

Run: `{run.name}`

Final classification: **{result['status']}**

## Scope evidence

- Approval ID: `{APPROVAL_ID}`.
- No measurement-created ROS bridge, ROS collector, raw-contact collector, or analyzer was started.
- No `/cmd_vel` publication, teleop, Nav2, PPO, Gymnasium, SB3, pose/reset/pause/step/spawn/delete/world-control, service/action, or hardware operation was performed.
- Every query record is retained under `queries/`: {', '.join(query_files) if query_files else 'none'}.

## Result

```json
{json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True)}
```

## Retained non-claims

This diagnostic does not establish a collision event, ContactLatch, collision policy/filter, raw contact payload delivery, reward, termination, Gym/training, or hardware readiness. Endpoint discovery is not a collision fact.
"""
    (run / "Spawned_ContactSensor_Diagnostic_Evidence_Report.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--initialize-guard", action="store_true")
    parser.add_argument("--offline-guard-self-test", action="store_true")
    parser.add_argument("--offline-model-list-parser-self-test", action="store_true")
    parser.add_argument("--offline-link-sensor-parser-self-test", action="store_true")
    args = parser.parse_args()
    if args.offline_link_sensor_parser_self_test:
        ok, result = offline_link_sensor_parser_self_test()
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 0 if ok else 1
    if args.offline_model_list_parser_self_test:
        ok, result = offline_model_list_parser_self_test()
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 0 if ok else 1
    if args.offline_guard_self_test:
        ok, result = offline_self_test()
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 0 if ok else 1
    ctx = context()
    if args.initialize_guard:
        ok, reason = initialize_guard(GUARD, ctx, now())
        print(json.dumps({"approval_id": APPROVAL_ID, "state": "authorized_not_consumed" if ok else "INVALID", "reason": reason}, ensure_ascii=True, sort_keys=True))
        return 0 if ok else 1
    acquired, reason, lock = acquire_guard(GUARD, ctx)
    if not acquired or lock is None:
        print(json.dumps({"status": "INVALID", "stage": "approval_guard_acquire", "reason": reason}, ensure_ascii=True, sort_keys=True))
        return 2
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run = ART / f"run-spawned-contactsensor-diagnostic-{stamp}-01"
    run.mkdir(parents=True, exist_ok=False)
    (run / "queries").mkdir()
    processes: list[tuple[subprocess.Popen[str], str, Any]] = []
    status, stage, reason = "INVALID", "not_started", "not started"
    query_sequence = 0
    try:
        dump(run / "manifest.json", {"approval_id": APPROVAL_ID, "authority_packet": ctx["authority_packet"], "authority_packet_sha256": ctx["authority_packet_sha256"], "world": WORLD, "world_sha256": WORLD_SHA256, "literals": ctx["literals"], "capacity": 1, "scope": "one read-only spawned ContactSensor diagnostic; no bridge/collector/analyzer"})
        static_ok, stage, reason = static_gate(run)
        if not static_ok:
            return 2
        gazebo, handle = launch(ros_shell("exec ros2 launch ROBOT_URDF_final_description gazebo.launch.py"), run / "gazebo_launch.log")
        processes.append((gazebo, "gazebo_launch", handle))
        time.sleep(8.0)
        if gazebo.poll() is not None:
            stage, reason = "gazebo_launch", "Gazebo exited before diagnostic queries"
            return 2
        # Read-only ROS graph snapshot only when the existing launch exposes it.
        graph = command_record(ros_shell("ros2 topic info /cmd_vel -v"))
        dump(run / "cmd_vel_graph_snapshot.json", graph)
        query_sequence += 1
        models = query("gz model --list")
        models["sequence"] = query_sequence; dump(run / "queries/01_models.json", models)
        model_ok, _ = parse_models(models)
        if not model_ok:
            status, stage, reason = "DIAGNOSTIC_INCOMPLETE_ROBOT_ENTITY", "model_query", "model identity query failed, was unparseable, or did not confirm exactly one model"
            return 2
        query_sequence += 1
        link = query(f"gz model -m {MODEL} -l {LINK}", model=MODEL, link=LINK)
        link["sequence"] = query_sequence; dump(run / "queries/02_link.json", link)
        link_parse, link_present, link_reason = parse_link_output(link)
        if not link_parse or not link_present:
            status, stage, reason = "DIAGNOSTIC_INCOMPLETE_SENSOR_QUERY", "link_query", link_reason
            return 2
        dump(run / "collision_identity.json", {"status": "DIAGNOSTIC_INCOMPLETE_COLLISION_IDENTITY", "reason": "no locally verified read-only collision/ECS component inspection API"})
        query_sequence += 1
        sensor = query(f"gz model -m {MODEL} -l {LINK} -s {SENSOR}", model=MODEL, link=LINK)
        sensor["sequence"] = query_sequence; dump(run / "queries/03_sensor.json", sensor)
        sensor_parse, sensor_present, sensor_reason = parse_sensor_output(sensor)
        if not sensor_parse:
            status, stage, reason = "DIAGNOSTIC_INCOMPLETE_SENSOR_QUERY", "sensor_query", sensor_reason
            return 2
        if not sensor_present:
            status, stage, reason = "SENSOR_ABSENT_AFTER_SPAWN", "sensor_query", "successful parsed sensor query omitted exact sensor literal"
            return 0
        query_sequence += 1
        topics = query("gz topic -l")
        topics["sequence"] = query_sequence; dump(run / "queries/04_topics.json", topics)
        topics_parse, topic_names = parse_topics(topics)
        if not topics_parse:
            status, stage, reason = "DIAGNOSTIC_INCOMPLETE_ENDPOINT_QUERY", "topic_enumeration", "topic enumeration failed, timed out, or was unparseable"
            return 2
        candidates: list[dict[str, Any]] = []
        contacts: list[str] = []
        for topic_name in topic_names:
            query_sequence += 1
            info = query(f"gz topic -i -t {topic_name}")
            info["sequence"] = query_sequence; info["candidate_topic"] = topic_name
            dump(run / f"queries/topic_{query_sequence:03d}.json", info)
            if info["timeout"] or info["exit_code"] != 0 or info.get("shutdown_incomplete") or not str(info["stdout"]).strip():
                status, stage, reason = "DIAGNOSTIC_INCOMPLETE_ENDPOINT_QUERY", "topic_type_query", f"type query did not complete for {topic_name}"
                return 2
            info["parse_status"] = "PARSED"
            is_contacts = GZ_CONTACTS_TYPE in str(info["stdout"])
            candidates.append({"topic": topic_name, "type_query": "PARSED", "is_contacts": is_contacts})
            if is_contacts:
                contacts.append(topic_name)
        dump(run / "topic_candidate_summary.json", {"all_listed_topics": topic_names, "type_queries": candidates, "contacts_candidates": contacts})
        if not contacts:
            status, stage, reason = "SENSOR_PRESENT_ENDPOINT_ABSENT", "topic_enumeration", "sensor confirmed; no gz.msgs.Contacts endpoint discovered"
            return 0
        status, stage, reason = "SENSOR_PRESENT_ENDPOINT_DISCOVERED", "topic_type_query", "gz.msgs.Contacts endpoint discovered"
        return 0
    except Exception as exc:
        status, stage, reason = "INVALID", "supervisor_exception", f"{type(exc).__name__}: {exc}"
        return 5
    finally:
        shutdown_records = []
        complete = True
        for process, label, handle in reversed(processes):
            record = stop_sigint(process, label)
            shutdown_records.append(record)
            complete = complete and bool(record["complete"])
            handle.close()
        if not complete:
            status, stage, reason = "SHUTDOWN_INCOMPLETE", "shutdown", "SIGINT-only shutdown incomplete"
        dump(run / "shutdown_record.json", {"complete": complete, "records": shutdown_records})
        final = {"status": status, "stage": stage, "reason": reason, "run_id": run.name, "commands_published": 0, "control_services_called": 0, "bridge_processes_started": 0, "collectors_started": 0, "hardware_operations": 0, "collision_identity_status": "DIAGNOSTIC_INCOMPLETE_COLLISION_IDENTITY"}
        consumed, consume_reason = consume_guard(GUARD, lock, ctx, run.name, status, now())
        final["approval_guard_consumed"] = consumed
        final["approval_guard_consume_reason"] = consume_reason
        if not consumed:
            final.update({"status": "INVALID", "stage": "approval_guard_consume", "reason": consume_reason})
        dump(run / "run_result.json", final)
        write_report(run, final)
        (run / "manifest.json").chmod(0o444)


if __name__ == "__main__":
    sys.exit(main())
