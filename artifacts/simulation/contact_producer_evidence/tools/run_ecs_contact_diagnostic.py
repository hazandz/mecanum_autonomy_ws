#!/usr/bin/env python3
"""Offline-testable future orchestration for the native ECS diagnostic route.

This module deliberately has no runtime entrypoint.  Its orchestration is driven
only by injected collaborators; ``--execute`` fails before preflight or process
construction until a separately approved execution authority exists.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol, Sequence

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{7,127}$")
_CREATE_PATH = Path("/opt/ros/jazzy/lib/ros_gz_sim/create")


@dataclass(frozen=True)
class EcsDiagnosticRunPlan:
    """All future runtime inputs, supplied explicitly and never defaulted."""
    workspace_root: Path
    run_id: str
    template_source: Path
    template_installed: Path
    template_sha256: str
    model_source: Path
    model_installed: Path
    model_sha256: str
    plugin_source: Path
    plugin_source_sha256: str
    plugin_binary: Path
    plugin_binary_sha256: str
    collector_source: Path
    collector_source_sha256: str
    collector_binary: Path
    collector_binary_sha256: str
    renderer_executable: Path
    renderer_sha256: str
    collector_executable: Path
    collector_executable_sha256: str
    launch_executable: Path
    launch_executable_sha256: str
    launch_file: Path
    launch_sha256: str
    create_executable: Path
    create_sha256: str
    create_argv: tuple[str, ...]
    run_directory: Path
    rendered_world: Path
    renderer_result_receipt: Path
    world_name: str
    model_name: str
    link_name: str
    sensor_name: str
    receipt_topic: str
    system_wait_timeout_sim_time_ns: int
    system_delivery_wait_timeout_steady_ns: int
    collector_receipt_wait_timeout_steady_ns: int
    collector_persist_timeout_steady_ns: int


@dataclass(frozen=True)
class RendererResultReceipt:
    schema_version: str
    run_id: str
    template_path: Path
    rendered_world_path: Path
    base_world_template_sha256: str
    rendered_world_sha256: str


def parse_renderer_result_receipt(path: Path) -> RendererResultReceipt | None:
    """Strictly parse the renderer's machine-readable receipt; no log parsing."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    expected = {"schema_version", "run_id", "template_path", "rendered_world_path", "base_world_template_sha256", "rendered_world_sha256"}
    if not isinstance(value, dict) or set(value) != expected or any(not isinstance(value[key], str) for key in expected):
        return None
    receipt = RendererResultReceipt(value["schema_version"], value["run_id"], Path(value["template_path"]),
                                    Path(value["rendered_world_path"]), value["base_world_template_sha256"],
                                    value["rendered_world_sha256"])
    if receipt.schema_version != "s3_d3_renderer_result/v1" or not receipt.template_path.is_absolute() or not receipt.rendered_world_path.is_absolute():
        return None
    if not _valid_hash(receipt.base_world_template_sha256) or not _valid_hash(receipt.rendered_world_sha256):
        return None
    return receipt


@dataclass(frozen=True)
class Command:
    argv: tuple[str, ...]
    shell: bool = False
    new_session: bool = True


@dataclass(frozen=True)
class CleanupRecord:
    process_role: str
    supervisor_initiated_sigint_only: bool
    grace_completed: bool
    launcher_managed_escalation_observed: bool | None


@dataclass(frozen=True)
class OrchestrationResult:
    status: str
    events: tuple[str, ...]
    cleanup: tuple[CleanupRecord, ...]


class FutureProcess(Protocol):
    def ready(self) -> bool: ...
    def terminal(self) -> str: ...
    def send_sigint_group(self) -> None: ...
    def wait_grace(self, timeout_ns: int) -> bool: ...


class FutureRunner(Protocol):
    def render(self, command: Command, plan: EcsDiagnosticRunPlan) -> bool: ...
    def read_renderer_result(self, plan: EcsDiagnosticRunPlan) -> RendererResultReceipt | None: ...
    def write_manifest(self, plan: EcsDiagnosticRunPlan, receipt: RendererResultReceipt) -> bool: ...
    def start(self, role: str, command: Command) -> FutureProcess: ...


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _regular_non_symlink(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _valid_hash(value: str) -> bool:
    return bool(_SHA256.fullmatch(value))


def _expected_create_argv(plan: EcsDiagnosticRunPlan) -> tuple[str, ...]:
    return (
        "-world", plan.world_name, "-file", str(plan.model_installed.resolve()),
        "-name", plan.model_name, "-allow_renaming", "false",
        "-x", "0", "-y", "0", "-z", "0.1", "-Y", "0",
    )


def validate_plan(
    plan: EcsDiagnosticRunPlan,
    *,
    file_hash: Callable[[Path], str] = _sha256,
    is_regular: Callable[[Path], bool] = _regular_non_symlink,
) -> str | None:
    """Return a typed failure, or ``None`` without running any child."""
    if not _RUN_ID.fullmatch(plan.run_id):
        return "INVALID_RUN_ID"
    if plan.create_executable != _CREATE_PATH or plan.create_argv != _expected_create_argv(plan):
        return "INVALID_NATIVE_CREATE_CONTRACT"
    if not all((plan.world_name == "world_demo", plan.model_name == "ROBOT_URDF_final",
                plan.link_name == "base_link", plan.sensor_name == "s3_d3_base_contact_sensor",
                plan.receipt_topic.startswith("/") and "//" not in plan.receipt_topic)):
        return "INVALID_IDENTITY_CONTRACT"
    if any(value <= 0 for value in (
        plan.system_wait_timeout_sim_time_ns, plan.system_delivery_wait_timeout_steady_ns,
        plan.collector_receipt_wait_timeout_steady_ns, plan.collector_persist_timeout_steady_ns)):
        return "INVALID_TIMEOUT_CONTRACT"
    checked = (
        (plan.template_source, plan.template_sha256), (plan.template_installed, plan.template_sha256),
        (plan.model_source, plan.model_sha256), (plan.model_installed, plan.model_sha256),
        (plan.plugin_source, plan.plugin_source_sha256), (plan.plugin_binary, plan.plugin_binary_sha256),
        (plan.collector_source, plan.collector_source_sha256), (plan.collector_binary, plan.collector_binary_sha256),
        (plan.renderer_executable, plan.renderer_sha256), (plan.collector_executable, plan.collector_executable_sha256),
        (plan.launch_executable, plan.launch_executable_sha256), (plan.launch_file, plan.launch_sha256),
        (plan.create_executable, plan.create_sha256),
    )
    for path, expected in checked:
        if not _valid_hash(expected) or not is_regular(path) or file_hash(path) != expected:
            return "INVALID_PREFLIGHT_BINDING"
    for path in (plan.template_source, plan.template_installed, plan.model_source, plan.model_installed,
                 plan.plugin_source, plan.plugin_binary, plan.collector_source, plan.collector_binary,
                 plan.renderer_executable, plan.collector_executable, plan.launch_file,
                 plan.run_directory, plan.rendered_world, plan.renderer_result_receipt):
        if path != _CREATE_PATH and not _inside(plan.workspace_root, path):
            return "INVALID_WORKSPACE_PATH"
    if (plan.rendered_world.parent != plan.run_directory or
            plan.renderer_result_receipt.parent != plan.run_directory or
            plan.renderer_result_receipt.name != "renderer_result.json" or plan.run_directory.is_symlink()):
        return "INVALID_RENDER_DESTINATION"
    return None


def renderer_command(plan: EcsDiagnosticRunPlan) -> Command:
    c = plan
    return Command((str(c.renderer_executable), "--render-diagnostic-world", "--template", str(c.template_installed), "--output", str(c.rendered_world), "--result", str(c.renderer_result_receipt),
                    "--receipt-topic", c.receipt_topic, "--run-id", c.run_id, "--world-name", c.world_name,
                    "--model-name", c.model_name, "--link-name", c.link_name, "--sensor-name", c.sensor_name,
                    "--plugin-source-sha256", c.plugin_source_sha256, "--plugin-binary-sha256", c.plugin_binary_sha256,
                    "--collector-source-sha256", c.collector_source_sha256, "--collector-binary-sha256", c.collector_binary_sha256,
                    "--base-world-template-sha256", c.template_sha256, "--native-model-sha256", c.model_sha256,
                    "--system-wait-timeout-sim-time-ns", str(c.system_wait_timeout_sim_time_ns),
                    "--system-delivery-wait-timeout-steady-ns", str(c.system_delivery_wait_timeout_steady_ns),
                    "--collector-receipt-wait-timeout-steady-ns", str(c.collector_receipt_wait_timeout_steady_ns),
                    "--collector-persist-timeout-steady-ns", str(c.collector_persist_timeout_steady_ns)))


def collector_command(plan: EcsDiagnosticRunPlan) -> Command:
    c = plan
    return Command((str(c.collector_executable), "--runtime-collector", "--receipt-topic", c.receipt_topic,
                    "--run-id", c.run_id, "--world-name", c.world_name, "--model-name", c.model_name,
                    "--link-name", c.link_name, "--sensor-name", c.sensor_name,
                    "--plugin-source-sha256", c.plugin_source_sha256, "--plugin-binary-sha256", c.plugin_binary_sha256,
                    "--collector-source-sha256", c.collector_source_sha256, "--collector-binary-sha256", c.collector_binary_sha256,
                    "--base-world-template-sha256", c.template_sha256, "--native-model-sha256", c.model_sha256,
                    "--output-dir", str(c.run_directory),
                    "--system-wait-timeout-sim-time-ns", str(c.system_wait_timeout_sim_time_ns),
                    "--system-delivery-wait-timeout-steady-ns", str(c.system_delivery_wait_timeout_steady_ns),
                    "--collector-receipt-wait-timeout-steady-ns", str(c.collector_receipt_wait_timeout_steady_ns),
                    "--collector-persist-timeout-steady-ns", str(c.collector_persist_timeout_steady_ns)))


def launch_command(plan: EcsDiagnosticRunPlan) -> Command:
    return Command((str(plan.launch_executable), "launch", "ROBOT_URDF_final_description",
                    plan.launch_file.name, f"rendered_world:={plan.rendered_world}"))


def create_command(plan: EcsDiagnosticRunPlan) -> Command:
    return Command((str(plan.create_executable), *plan.create_argv))


def _cleanup(processes: Sequence[tuple[str, FutureProcess]], grace_ns: int) -> tuple[CleanupRecord, ...]:
    records: list[CleanupRecord] = []
    for role, process in reversed(processes):
        process.send_sigint_group()
        records.append(CleanupRecord(role, True, process.wait_grace(grace_ns), None))
    return tuple(records)


def orchestrate_future(plan: EcsDiagnosticRunPlan, runner: FutureRunner, *,
                       file_hash: Callable[[Path], str] = _sha256,
                       is_regular: Callable[[Path], bool] = _regular_non_symlink) -> OrchestrationResult:
    """Run only injected actions; production execution remains deliberately blocked."""
    events: list[str] = []
    failure = validate_plan(plan, file_hash=file_hash, is_regular=is_regular)
    if failure:
        return OrchestrationResult(failure, tuple(events), ())
    events.append("preflight")
    if not runner.render(renderer_command(plan), plan):
        return OrchestrationResult("INVALID_RENDER", tuple(events), ())
    events.append("render")
    receipt = runner.read_renderer_result(plan)
    expected_template = plan.template_installed.resolve()
    expected_rendered = plan.rendered_world.resolve()
    if (receipt is None or receipt.schema_version != "s3_d3_renderer_result/v1" or
            receipt.run_id != plan.run_id or receipt.template_path != expected_template or
            receipt.rendered_world_path != expected_rendered or
            receipt.base_world_template_sha256 != plan.template_sha256 or
            not _valid_hash(receipt.rendered_world_sha256) or
            not is_regular(plan.rendered_world) or file_hash(plan.rendered_world) != receipt.rendered_world_sha256):
        return OrchestrationResult("INVALID_RENDER_RESULT_PROVENANCE", tuple(events), ())
    events.append("render_result")
    if not runner.write_manifest(plan, receipt):
        return OrchestrationResult("INVALID_MANIFEST", tuple(events), ())
    events.append("manifest")
    active: list[tuple[str, FutureProcess]] = []
    collector = runner.start("collector", collector_command(plan)); active.append(("collector", collector)); events.append("collector")
    if not collector.ready():
        return OrchestrationResult("COLLECTOR_UNREADY", tuple(events), _cleanup(active, plan.collector_persist_timeout_steady_ns))
    launch = runner.start("launch", launch_command(plan)); active.append(("launch", launch)); events.append("launch")
    create = runner.start("create", create_command(plan)); active.append(("create", create)); events.append("create")
    result = collector.terminal(); events.append("collector_terminal")
    return OrchestrationResult(result, tuple(events), _cleanup(active, plan.collector_persist_timeout_steady_ns))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if args.execute:
        print("NO_EXECUTION_AUTHORITY")
        return 2
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
