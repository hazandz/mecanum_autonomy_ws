"""Owned Gazebo process groups and explicit GUI readiness/Owner handshake.

Runtime entry point only. Tests inject process, scene, acknowledgment and
evidence adapters; this module is not invoked by offline collection.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib
import os
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


class Readiness(Protocol):
    """Define server, GUI and human-owner readiness checks."""

    async def server_scene(
        self, plan: LaunchPlan, process: OwnedProcess, timeout_s: float,
    ) -> None:
        """Wait for the expected server scene identity."""
        ...

    async def gui_rendered(
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
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

    async def stop_group(self, process: OwnedProcess, sig: int) -> None:
        """Send a signal to an owned process group if it still exists."""
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass


class RclpyReadiness:
    """Check backend identity and require explicit GUI owner confirmation."""

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
        import rclpy
        from rclpy.node import Node
        from mecanum_nav_rl_interfaces.msg import SimulationContactState

        rclpy.init(args=None)
        node = Node('b2_server_scene_readiness')
        result: asyncio.Future[None] = (
            asyncio.get_running_loop().create_future()
        )
        _, config_hash, _, _ = load_bound_config(plan.resolved_config)

        def callback(msg: SimulationContactState) -> None:
            if (
                msg.header.frame_id == 'b2_training_arena'
                and msg.session_id == plan.session_id
                and msg.config_hash == config_hash
                and msg.backend_instance_id != 0
                and msg.status_sequence > 0
            ):
                if not result.done():
                    result.set_result(None)

        subscription = node.create_subscription(
            SimulationContactState,
            '/mecanum/local_training/backend_state', callback, 50,
        )
        try:
            while not result.done():
                if process.returncode is not None:
                    raise RuntimeError(
                        'Gazebo server exited before scene identity readiness'
                    )
                rclpy.spin_once(node, timeout_sec=0.1)
                await asyncio.sleep(0)
            await result
        finally:
            node.destroy_subscription(subscription)
            node.destroy_node()
            rclpy.shutdown()

    async def gui_rendered(
        self, plan: LaunchPlan, process: OwnedProcess, timeout_s: float,
    ) -> None:
        """Wait for GUI startup and owner confirmation."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if process.returncode is not None:
                raise RuntimeError('GUI exited before render readiness')
            await asyncio.sleep(0.1)

    async def owner_ack(self, timeout_s: float) -> tuple[bool, str]:
        """Collect the owner's explicit scene acknowledgment."""
        print(
            'Xác nhận trực tiếp world b2_training_arena và robot '
            'mecanum_b2 đã hiển thị; nhập screenshot reference rồi gõ '
            'OWNER_ACK_SCENE.',
            flush=True,
        )
        deadline = asyncio.get_running_loop().time() + timeout_s
        try:
            screenshot = await asyncio.wait_for(
                asyncio.to_thread(input, 'screenshot reference: '),
                timeout_s,
            )
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                return False, 'owner_ack_timeout'
            acknowledgement = await asyncio.wait_for(
                asyncio.to_thread(input, 'ack: '), remaining,
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
        self.owned.append(
            ProcessRecord('server', server_command, server.pid, server),
        )
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
            self.owned.append(
                ProcessRecord('gui', gui_command, gui.pid, gui),
            )
            self.evidence_sink.record(
                'gui_requested', self._facts(self.owned[-1]),
            )
            await self.readiness.gui_rendered(
                self.plan, gui, self.GUI_READY_TIMEOUT_S,
            )
            accepted, screenshot_ref = await self.readiness.owner_ack(
                self.OWNER_ACK_TIMEOUT_S,
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

    @staticmethod
    def _facts(record: ProcessRecord) -> dict[str, object]:
        return {
            'process': record.name,
            'command': list(record.command),
            'pid': record.pid,
            'owned_process_group': record.pid,
        }

    async def cleanup(self) -> None:
        """Stop owned processes with bounded signal escalation."""
        # Only these exact process groups were created by this supervisor.
        for record in reversed(self.owned):
            process = record.process
            if process.returncode is not None:
                continue
            await self.launcher.stop_group(process, signal.SIGINT)
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
                escalation = 'SIGINT'
            except asyncio.TimeoutError:
                await self.launcher.stop_group(process, signal.SIGTERM)
                try:
                    await asyncio.wait_for(process.wait(), timeout=3.0)
                    escalation = 'SIGINT_THEN_SIGTERM'
                except asyncio.TimeoutError:
                    await self.launcher.stop_group(process, signal.SIGKILL)
                    await process.wait()
                    escalation = 'SIGINT_THEN_SIGTERM_THEN_SIGKILL'
            self.evidence_sink.record('owned_process_cleanup', {
                **self._facts(record), 'escalation': escalation,
            })
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
        )
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
