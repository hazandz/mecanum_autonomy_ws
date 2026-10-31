"""Owned Gazebo process groups and explicit GUI readiness/Owner handshake.

Runtime entry point only. Tests inject process, scene, acknowledgment and
evidence adapters; this module is not invoked by offline collection.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib
import inspect
import json
import os
import secrets
import signal
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Protocol

from ament_index_python.packages import (
    get_package_prefix,
    get_package_share_directory,
)

from mecanum_nav_bringup.local_training_launch_contract import (
    LaunchPlan,
    build_launch_plan,
    load_bound_config,
    write_bound_world,
)


class OwnedProcess(Protocol):
    """Expose identity, status and wait behavior for an owned process."""

    pid: int
    returncode: int | None

    async def wait(self) -> int:
        """Wait for process completion and return its exit status."""
        ...


class ProcessLauncher(Protocol):
    """Define process launch and owned process-group shutdown operations."""

    async def start(
        self, command: tuple[str, ...], environment: dict[str, str],
    ) -> OwnedProcess:
        """Start one process group and return its owned process handle."""
        ...

    async def stop_group(self, process: OwnedProcess, sig: int) -> None:
        """Send a signal to the process group owned by this launcher."""
        ...

    def group_alive(self, process: OwnedProcess) -> bool:
        """Check whether the launcher-owned process group still exists."""
        ...


class Readiness(Protocol):
    """Define server, GUI and human-owner readiness checks."""

    async def server_scene(
        self, plan: LaunchPlan, process: OwnedProcess, timeout_s: float,
    ) -> None:
        """Wait for the expected server scene identity."""
        ...

    async def gui_process_started(
        self, plan: LaunchPlan, process: OwnedProcess, timeout_s: float,
    ) -> None:
        """Wait for the GUI rendering readiness condition."""
        ...

    async def owner_ack(self, timeout_s: float) -> tuple[bool, str]:
        """Collect explicit human confirmation and screenshot reference."""
        ...


class EvidenceSink(Protocol):
    """Define the evidence event sink used by the supervisor."""

    def record(self, event: str, facts: dict[str, object]) -> None:
        """Record one event with its associated facts."""
        ...


@dataclass
class ProcessRecord:
    """Bind an owned process handle to its name and launch command."""

    name: str
    command: tuple[str, ...]
    pid: int
    process: OwnedProcess
    output_tasks: tuple[asyncio.Task[None], ...] = ()


class SubprocessProcessLauncher:
    """Launch and stop OS process groups for this supervisor."""

    async def start(
        self, command: tuple[str, ...], environment: dict[str, str],
    ) -> OwnedProcess:
        """Start the requested command in a new process group."""
        env = os.environ.copy()
        env.update(environment)
        return await asyncio.create_subprocess_exec(
            *command, env=env, start_new_session=True,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    async def stop_group(self, process: OwnedProcess, sig: int) -> None:
        """Signal only the process group created by this launcher."""
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass

    def group_alive(self, process: OwnedProcess) -> bool:
        """Return whether the owned process group has any remaining member."""
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True


class _RclpyBackendStatusSource:
    """Own the production ROS subscription used by scene readiness."""

    def __init__(self) -> None:
        self._rclpy = None
        self._node = None
        self._subscription = None
        self._messages = []

    async def start(self) -> None:
        import rclpy
        from rclpy.node import Node
        from mecanum_nav_rl_interfaces.msg import SimulationContactState

        self._rclpy = rclpy
        rclpy.init(args=None)
        self._node = Node('b2_server_scene_readiness')
        self._subscription = self._node.create_subscription(
            SimulationContactState,
            '/mecanum/local_training/backend_state',
            self._messages.append,
            50,
        )

    async def next_status(self, timeout_s: float):
        if self._rclpy is None or self._node is None:
            raise RuntimeError('backend status source is not started')
        self._rclpy.spin_once(self._node, timeout_sec=timeout_s)
        return self._messages.pop(0) if self._messages else None

    async def close(self) -> None:
        if self._node is not None and self._subscription is not None:
            self._node.destroy_subscription(self._subscription)
            self._subscription = None
        if self._node is not None:
            self._node.destroy_node()
            self._node = None
        if self._rclpy is not None and self._rclpy.ok():
            self._rclpy.shutdown()
        self._rclpy = None


class RclpyReadiness:
    """Check backend identity and require explicit GUI owner confirmation."""

    SERVER_READY_TIMEOUT_S = 30.0

    def __init__(
        self, scene_query=None, *, backend_status_source_factory=None,
        steady_clock=None,
    ) -> None:
        """Keep partial stdin lines across bounded, cancellable reads."""
        self._stdin_buffers: dict[int, bytearray] = {}
        self._scene_query = scene_query or self._query_gazebo_scene
        self._backend_status_source_factory = (
            backend_status_source_factory or _RclpyBackendStatusSource
        )
        self._steady_clock = steady_clock or time.monotonic

    @staticmethod
    def _query_gazebo_scene(service: str, timeout_ms: int):
        """Read the current Gazebo Sim scene through its documented service."""
        from gz.msgs10.empty_pb2 import Empty
        from gz.msgs10.scene_pb2 import Scene
        from gz.transport13 import Node

        node = Node()
        success, scene = node.request(
            service, Empty(), Empty, Scene, timeout_ms,
        )
        return scene if success else None

    @staticmethod
    def _matches_expected_scene(scene, plan) -> bool:
        """Require the exact world and one mecanum model in the scene data."""
        if scene is None or scene.name != 'b2_training_arena':
            return False
        models = list(scene.model)
        matches = []
        while models:
            model = models.pop()
            if model.name == 'mecanum_b2':
                matches.append(model)
            models.extend(model.model)
        return len(matches) == 1 and bool(plan.session_id)

    async def _query_scene_matches(self, plan) -> bool:
        """Query the installed Gazebo scene service and validate its reply."""
        service = '/world/b2_training_arena/scene/info'
        try:
            scene = self._scene_query(service, 500)
            if inspect.isawaitable(scene):
                scene = await scene
        except (TimeoutError, OSError):
            return False
        return self._matches_expected_scene(scene, plan)

    @staticmethod
    def _matches_bound_scene_status(msg, plan, config_hash: str) -> bool:
        """Accept only healthy inhibited status from the bound world/run.

        Backend Configure validates exact world/model/link identity and model
        cardinality before it can publish a fault-free status. Requiring the
        fault-free state keeps a matching heartbeat from masking that failure.
        """
        return (
            msg.header.frame_id == 'b2_training_arena'
            and msg.session_id == plan.session_id
            and msg.config_hash == config_hash
            and msg.backend_instance_id != 0
            and msg.status_sequence > 0
            and msg.fault_flags == 0
            and not msg.paused
            and msg.actuator_inhibited
        )

    async def server_scene(
        self, plan: LaunchPlan, process: OwnedProcess, timeout_s: float,
    ) -> None:
        """Wait for backend status matching the bound scene identity."""
        await asyncio.wait_for(
            self._backend_status(plan, process), timeout=timeout_s,
        )

    async def _backend_status(
        self, plan: LaunchPlan, process: OwnedProcess,
    ) -> None:
        _, config_hash, _, _ = load_bound_config(plan.resolved_config)
        source = self._backend_status_source_factory()
        deadline = self._steady_clock() + self.SERVER_READY_TIMEOUT_S
        try:
            await asyncio.wait_for(
                source.start(), timeout=self.SERVER_READY_TIMEOUT_S,
            )
            while True:
                if process.returncode is not None:
                    raise RuntimeError(
                        'Gazebo server exited before scene identity readiness'
                    )
                remaining = deadline - self._steady_clock()
                if remaining <= 0:
                    raise TimeoutError(
                        'server scene readiness deadline expired'
                    )
                message = await asyncio.wait_for(
                    source.next_status(min(remaining, 0.1)), timeout=remaining,
                )
                if message is None:
                    await asyncio.sleep(0)
                    continue
                if not self._matches_bound_scene_status(
                    message, plan, config_hash,
                ):
                    continue
                scene_ready = await asyncio.wait_for(
                    self._query_scene_matches(plan),
                    timeout=max(0.001, deadline - self._steady_clock()),
                )
                if scene_ready:
                    return
        finally:
            await asyncio.wait_for(source.close(), timeout=3.0)

    async def gui_process_started(
        self, plan: LaunchPlan, process: OwnedProcess, timeout_s: float,
    ) -> None:
        """Check process startup; Owner confirms rendered scene separately."""
        del plan
        if timeout_s <= 0 or process.returncode is not None:
            raise RuntimeError('GUI process failed before startup readiness')

    async def _read_stdin_line(self, prompt: str) -> str | None:
        """Read one line using a removable event-loop reader."""
        loop = asyncio.get_running_loop()
        descriptor = sys.stdin.fileno()
        buffer = self._stdin_buffers.setdefault(descriptor, bytearray())
        future: asyncio.Future[str | None] = loop.create_future()
        print(prompt, end='', flush=True)

        def read_line() -> None:
            if future.done():
                return
            newline = buffer.find(b'\n')
            if newline >= 0:
                value = bytes(buffer[:newline]).rstrip(b'\r')
                del buffer[:newline + 1]
                future.set_result(value.decode('utf-8', errors='replace'))
                return
            try:
                chunk = os.read(descriptor, 4096)
            except BlockingIOError:
                return
            except OSError:
                future.set_result(None)
                return
            if not chunk:
                future.set_result(None)
                return
            buffer.extend(chunk)
            newline = buffer.find(b'\n')
            if newline >= 0:
                value = bytes(buffer[:newline]).rstrip(b'\r')
                del buffer[:newline + 1]
                future.set_result(value.decode('utf-8', errors='replace'))

        loop.add_reader(descriptor, read_line)
        try:
            return await future
        finally:
            loop.remove_reader(descriptor)

    async def owner_ack(self, timeout_s: float) -> tuple[bool, str]:
        """Require screenshot reference and an explicit Owner confirmation."""
        print(
            'Xác nhận trực tiếp world b2_training_arena và robot '
            'mecanum_b2 đang hiển thị; không tự động chấp nhận.', flush=True,
        )
        deadline = asyncio.get_running_loop().time() + timeout_s
        try:
            screenshot = await asyncio.wait_for(
                self._read_stdin_line('screenshot reference: '), timeout_s,
            )
            remaining = deadline - asyncio.get_running_loop().time()
            if screenshot is None or remaining <= 0:
                return False, 'owner_ack_eof_or_timeout'
            acknowledgement = await asyncio.wait_for(
                self._read_stdin_line('type OWNER_ACK_SCENE: '), remaining,
            )
        except asyncio.TimeoutError:
            return False, 'owner_ack_timeout'
        if not screenshot.strip() or acknowledgement != 'OWNER_ACK_SCENE':
            return False, 'owner_ack_missing_or_invalid'
        return True, screenshot.strip()


class LocalTrainingProcessSupervisor:
    """Own the B2.2 server and optional GUI process lifecycle."""

    SERVER_READY_TIMEOUT_S = 30.0
    GUI_READY_TIMEOUT_S = 30.0
    OWNER_ACK_TIMEOUT_S = 60.0

    def __init__(
        self, *, plan: LaunchPlan, launcher: ProcessLauncher,
        readiness: Readiness, evidence_sink: EvidenceSink,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """Bind launch, readiness, evidence and timing dependencies."""
        self.plan = plan
        self.launcher = launcher
        self.readiness = readiness
        self.evidence_sink = evidence_sink
        self.monotonic = monotonic
        self.sleep = sleep
        self.owned: list[ProcessRecord] = []
        self.gui_opened = False

    async def start(self) -> None:
        """Start the server and requested GUI, failing closed on readiness."""
        server_command = self.plan.commands[0]
        server = await self.launcher.start(
            server_command, self.plan.environment,
        )
        server_record = ProcessRecord(
            'server', server_command, server.pid, server,
        )
        self.owned.append(server_record)
        self._capture_output(server_record)
        self.evidence_sink.record(
            'server_requested', self._facts(self.owned[-1]),
        )
        try:
            await self.readiness.server_scene(
                self.plan, server, self.SERVER_READY_TIMEOUT_S,
            )
            self.evidence_sink.record(
                'server_scene_ready',
                {
                    **self._facts(self.owned[-1]),
                    'session_id': self.plan.session_id,
                },
            )
            if not self.plan.gui_requested:
                return
            gui_command = self.plan.commands[1]
            gui = await self.launcher.start(
                gui_command, self.plan.environment,
            )
            gui_record = ProcessRecord('gui', gui_command, gui.pid, gui)
            self.owned.append(gui_record)
            self._capture_output(gui_record)
            self.evidence_sink.record(
                'gui_requested', self._facts(self.owned[-1]),
            )
            await self.readiness.gui_process_started(
                self.plan, gui, self.GUI_READY_TIMEOUT_S,
            )
            self.evidence_sink.record(
                'gui_process_started', self._facts(gui_record),
            )
            accepted, screenshot_ref = await self._owner_ack_with_liveness(
                gui_record,
            )
            if not accepted:
                self.evidence_sink.record(
                    'gui_owner_ack_failed', {'reason': screenshot_ref},
                )
                raise RuntimeError(
                    'GUI scene confirmation is required before collection'
                )
            self.gui_opened = True
            self.evidence_sink.record(
                'gui_scene_owner_confirmed',
                {
                    **self._facts(self.owned[-1]),
                    'screenshot_ref': screenshot_ref,
                    'confirmation_source': 'human_owner',
                },
            )
        except BaseException:
            await self.cleanup()
            raise

    def _capture_output(self, record: ProcessRecord) -> None:
        """Drain child output into the injected evidence sink."""
        tasks = []
        for stream_name in ('stdout', 'stderr'):
            stream = getattr(record.process, stream_name, None)
            if stream is not None:
                tasks.append(asyncio.create_task(
                    self._drain_output(record, stream_name, stream),
                ))
        record.output_tasks = tuple(tasks)

    async def _drain_output(self, record, stream_name, stream) -> None:
        """Preserve each child output line without blocking the child pipe."""
        while True:
            chunk = await stream.readline()
            if not chunk:
                return
            self.evidence_sink.record('owned_process_output', {
                **self._facts(record), 'stream': stream_name,
                'text': chunk.decode('utf-8', errors='replace').rstrip('\r\n'),
            })

    async def _owner_ack_with_liveness(self, gui_record):
        """Cancel bounded Owner input immediately if the GUI exits."""
        acknowledgement = asyncio.create_task(
            self.readiness.owner_ack(self.OWNER_ACK_TIMEOUT_S),
        )
        gui_exit = asyncio.create_task(gui_record.process.wait())
        done, pending = await asyncio.wait(
            (acknowledgement, gui_exit), timeout=self.OWNER_ACK_TIMEOUT_S,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        if gui_exit in done:
            acknowledgement.cancel()
            self.evidence_sink.record('gui_closed_or_crashed', {
                **self._facts(gui_record), 'exit_status': gui_exit.result(),
                'during_owner_confirmation': True,
            })
            return False, 'gui_exited_during_owner_confirmation'
        if acknowledgement not in done:
            return False, 'owner_ack_timeout'
        return acknowledgement.result()

    async def monitor(self) -> int:
        """Wait for server exit and clean up only owned process groups."""
        if not self.owned:
            raise RuntimeError('no owned server process')
        server = self.owned[0].process
        if self.plan.gui_requested and len(self.owned) > 1:
            gui_record = self.owned[1]
            if gui_record.process.returncode is None:
                asyncio.create_task(self._record_gui_exit(gui_record))
        try:
            return await server.wait()
        finally:
            await self.cleanup()

    async def _record_gui_exit(self, gui: ProcessRecord) -> None:
        status = await gui.process.wait()
        self.evidence_sink.record('gui_closed_or_crashed', {
            **self._facts(gui), 'exit_status': status,
            'server_restart': False, 'gui_restart': False,
            'motion_permission_changed_by_gui_exit': False,
        })

    def _facts(self, record: ProcessRecord) -> dict[str, object]:
        return {
            'process': record.name,
            'command': list(record.command),
            'pid': record.pid,
            'owned_process_group': record.pid,
            'environment': dict(self.plan.environment),
        }

    async def _wait_group_exit(
        self, process: OwnedProcess, timeout_s: float,
    ) -> bool:
        """Poll one owned process group until empty or a steady deadline."""
        deadline = self.monotonic() + timeout_s
        while self.launcher.group_alive(process):
            remaining = deadline - self.monotonic()
            if remaining <= 0:
                return False
            await self.sleep(min(0.05, remaining))
        return True

    async def cleanup(self) -> None:
        """Stop all owned groups, including children whose leader exited."""
        for record in reversed(self.owned):
            process = record.process
            if self.launcher.group_alive(process):
                await self.launcher.stop_group(process, signal.SIGINT)
                if await self._wait_group_exit(process, 5.0):
                    escalation = 'SIGINT'
                else:
                    await self.launcher.stop_group(process, signal.SIGTERM)
                    if await self._wait_group_exit(process, 3.0):
                        escalation = 'SIGINT_THEN_SIGTERM'
                    else:
                        await self.launcher.stop_group(process, signal.SIGKILL)
                        stopped = await self._wait_group_exit(process, 3.0)
                        escalation = 'SIGINT_THEN_SIGTERM_THEN_SIGKILL'
                        if not stopped:
                            escalation += '_GROUP_STILL_PRESENT'
            else:
                escalation = 'GROUP_ALREADY_EXITED'
            self.evidence_sink.record(
                'owned_process_cleanup', {
                    **self._facts(record), 'escalation': escalation,
                },
            )
            if record.output_tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(
                            *record.output_tasks, return_exceptions=True,
                        ),
                        timeout=1.0,
                    )
                except asyncio.TimeoutError:
                    for task in record.output_tasks:
                        task.cancel()
                    await asyncio.gather(
                        *record.output_tasks, return_exceptions=True,
                    )
                    self.evidence_sink.record(
                        'owned_process_output_drain_timeout',
                        self._facts(record),
                    )
        self.owned.clear()


def _load_sink(specification: str) -> EvidenceSink:
    if ':' not in specification:
        raise RuntimeError(
            'B2.3 evidence sink must be injected as module:factory'
        )
    module_name, factory_name = specification.split(':', 1)
    factory = getattr(importlib.import_module(module_name), factory_name)
    return factory()


async def _run_from_cli(args: argparse.Namespace) -> int:
    gui = 'true' if args.gui == 'true' else 'false'
    config_path = Path(args.resolved_config).resolve(strict=True)
    document, _, _, _ = load_bound_config(config_path)
    session_id = str(uuid.uuid4())
    coordinator_ingress_instance_id = secrets.randbits(64) or 1
    partition = f"mecanum_b2_{session_id.replace('-', '')}"
    description_share = Path(
        get_package_share_directory('ROBOT_URDF_final_description'),
    ).resolve()
    rl_share = Path(get_package_share_directory('mecanum_nav_rl')).resolve()
    backend_prefix = Path(get_package_prefix('mecanum_sim_backend')).resolve()
    bringup_share = Path(
        get_package_share_directory('mecanum_nav_bringup'),
    ).resolve()
    with tempfile.TemporaryDirectory(
        prefix='mecanum_b2_session_',
    ) as runtime_dir:
        installed_world = description_share / 'worlds/b2_training_arena.sdf'
        installed_model = description_share / 'models/mecanum_b2/model.sdf'
        plan = build_launch_plan(
            gui=gui, resolved_config=config_path, world_file=installed_world,
            gui_config=bringup_share / 'config/gui/local_training.config',
            session_id=session_id, partition=partition,
            resource_paths=(
                description_share.parent, description_share / 'models',
            ),
            plugin_path=backend_prefix / 'lib',
            asset_manifest_file=(
                description_share / 'manifests/b2/asset_manifest.json'
            ),
            scenario_directory=rl_share / 'scenarios/local_training',
            runtime_world_directory=Path(runtime_dir),
            coordinator_ingress_instance_id=(
                coordinator_ingress_instance_id
            ),
        )
        descriptor = {
            'schema_id': 'mecanum_b2_run_descriptor/v1',
            'session_id': plan.session_id,
            'config_hash': plan.config_hash,
            'asset_manifest_sha256': plan.asset_manifest_sha256,
            'coordinator_ingress_instance_id': (
                plan.coordinator_ingress_instance_id
            ),
        }
        descriptor_path = Path(runtime_dir) / 'run_descriptor.json'
        with descriptor_path.open('x', encoding='utf-8') as stream:
            json.dump(
                descriptor, stream, sort_keys=True, separators=(',', ':'),
            )
            stream.write('\n')
        write_bound_world(plan, installed_world, installed_model)
        sink = _load_sink(os.environ.get('MECANUM_B2_EVIDENCE_SINK', ''))
        supervisor = LocalTrainingProcessSupervisor(
            plan=plan, launcher=SubprocessProcessLauncher(),
            readiness=RclpyReadiness(), evidence_sink=sink,
        )
        await supervisor.start()
        return await supervisor.monitor()


def main() -> None:
    """Parse the launcher arguments and run the owned process supervisor."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--gui', required=True, choices=('true', 'false'))
    parser.add_argument('--resolved-config', required=True)
    args = parser.parse_args()
    try:
        sys.exit(asyncio.run(_run_from_cli(args)))
    except Exception as error:
        raise SystemExit(f'LOCAL_TRAINING_START_FAILED: {error}') from error
