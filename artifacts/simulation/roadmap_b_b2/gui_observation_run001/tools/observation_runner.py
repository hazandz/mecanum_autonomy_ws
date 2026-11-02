"""Single-run, paused GUI observation orchestration for B2.2."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
from collections import deque
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from observation_guard import (
    CONFIG_HASH, EVIDENCE_ROOT, GUARD_PATH, GuardError, MANIFEST_SHA256,
    RESOLVED_SHA256, RUN_ID, SCENARIO_SHA256,
    acquire_once, packet_bindings, sha256_file, validate_approval,
)

from observation_sink import ObservationEvidenceSink


PACKET_PATH = Path(__file__).resolve().parents[1] / 'packet.json'
TOOL_PATHS = {
    'observation_guard.py': Path(__file__).with_name('observation_guard.py'),
    'observation_sink.py': Path(__file__).with_name('observation_sink.py'),
    'observation_runner.py': Path(__file__).resolve(),
    'test_observation_packet.py': Path(__file__).with_name(
        'test_observation_packet.py',
    ),
}
SERVER_READY_S = 30.0
GUI_START_S = 30.0
OWNER_ACK_S = 60.0
OBSERVATION_S = 60.0
RUNTIME_CAP_S = 240.0
CLEANUP_CAP_S = 60.0
TOTAL_CAP_S = 300.0
HEARTBEAT_GAP_S = 1.0
CLOCK_READY_TIMEOUT_S = SERVER_READY_S
CLOCK_SAMPLE_GAP_S = 1.0
POLL_SLICE_S = 0.05
EXPECTED_ROS_NODES = {
    ('b22_gui_observation_observer', '/'),
    ('mecanum_sim_backend', '/'),
    ('robot_state_publisher', '/'), ('ros_gz_bridge', '/'),
}
STARTUP_TEMPORARY_ROS_NODES = {('b2_server_scene_readiness', '/')}


class ObservationFailure(RuntimeError):
    """A fail-closed runtime observation result."""


class OwnerAbort(ObservationFailure):
    """An Owner-closed GUI ended observation early."""


def enforce_runtime_cap(consumed_at: float, now: float) -> None:
    """Reject activity that exceeds the 240-second post-consume budget."""
    if now - consumed_at > RUNTIME_CAP_S:
        raise ObservationFailure('240 s runtime cap exceeded')


def classify_final_status(observation_passed, owner_aborted, cleanup_errors):
    """Classify a completed observation after accounting for cleanup errors."""
    if cleanup_errors:
        return 'FAIL'
    if owner_aborted:
        return 'ABORTED_BY_OWNER'
    return 'PASS' if observation_passed else 'FAIL'


def strict_gui_value(value: str) -> bool:
    """Parse only the exact lowercase ``true`` and ``false`` values."""
    if value not in ('true', 'false'):
        raise argparse.ArgumentTypeError(
            "gui must be exactly 'true' or 'false'",
        )
    return value == 'true'


def require_run_gui(gui: bool) -> None:
    """Require GUI mode for RUN001 before consuming its capacity-one guard."""
    if gui is not True:
        raise ObservationFailure('RUN001 requires --gui true before consume')


def preflight_desktop(
    stdin_isatty: bool, environ: dict[str, str], exists,
) -> None:
    """Require a real Owner TTY and an already available desktop socket."""
    if not stdin_isatty:
        raise ObservationFailure('Owner stdin is not an interactive TTY')
    display = environ.get('DISPLAY', '')
    wayland_display = environ.get('WAYLAND_DISPLAY', '')
    runtime_dir = environ.get('XDG_RUNTIME_DIR', '')
    x11_socket = None
    if display:
        match = re.fullmatch(
            r'(?:(?:unix|localhost)?):([0-9]+)(?:\.[0-9]+)?', display,
        )
        if match:
            x11_socket = Path('/tmp/.X11-unix') / f'X{match.group(1)}'
    wayland_socket = Path(runtime_dir) / wayland_display if (
        runtime_dir and wayland_display
    ) else None
    if not (
        (x11_socket is not None and exists(x11_socket))
        or (wayland_socket is not None and exists(wayland_socket))
    ):
        raise ObservationFailure('no usable existing desktop socket found')


def validate_run_roots(
    guard_path: Path, evidence_root: Path, *, expected_guard=GUARD_PATH,
    expected_evidence=EVIDENCE_ROOT,
) -> tuple[Path, Path]:
    """Reject redirected paths and evidence collisions before acquisition."""
    guard_path = Path(guard_path)
    evidence_root = Path(evidence_root)
    if guard_path != expected_guard or evidence_root != expected_evidence:
        raise GuardError('RUN001 acquisition/evidence paths are fixed')
    for path in (guard_path, evidence_root):
        if not path.is_absolute() or path.resolve(strict=False) != path:
            raise GuardError(f'RUN001 path is not canonical: {path}')
        for component in reversed((path, *path.parents)):
            try:
                if component.is_symlink():
                    raise GuardError(
                        f'RUN001 path contains a symlink: {component}'
                    )
            except OSError as error:
                raise GuardError(
                    f'RUN001 path cannot be inspected: {component}'
                ) from error
    if guard_path.exists() or guard_path.is_symlink():
        raise GuardError('RUN001 acquisition already exists; no retry')
    if evidence_root.exists():
        if not evidence_root.is_dir():
            raise GuardError('RUN001 evidence root is not a directory')
        if any(evidence_root.iterdir()):
            raise GuardError('RUN001 evidence root already contains data')
    return guard_path, evidence_root


def process_start_identity(pid: int, proc_root: Path = Path('/proc')) -> dict:
    """Read Linux PID, process-group, session and start-tick identity."""
    raw = (proc_root / str(pid) / 'stat').read_text(encoding='ascii')
    closing = raw.rfind(')')
    if closing < 0:
        raise ObservationFailure('malformed proc stat for owned process')
    fields = raw[closing + 2:].split()
    return {
        'pid': pid,
        'process_group_id': int(fields[2]),
        'session_id': int(fields[3]),
        'start_ticks': int(fields[19]),
    }


def assert_packet_inputs(packet: dict, file_hashes: dict[str, str]) -> None:
    """Call the one canonical packet validator used by guard and runner."""
    return packet_bindings(packet, file_hashes)


def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def _host_identity() -> dict[str, str]:
    return {
        'hostname': socket.gethostname(),
        'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text(
            encoding='ascii',
        ).strip(),
    }


class ScreenshotReadiness:
    """Delegate readiness to audited code and hash Owner's real screenshot."""

    def __init__(self, readiness, owner_ack_event=None,
                 readiness_complete_event=None):
        """Wrap audited readiness and retain the verified Owner screenshot."""
        self._readiness = readiness
        self.owner_ack_event = owner_ack_event
        self.readiness_complete_event = readiness_complete_event
        self.screenshot_path = None
        self.screenshot_sha256 = None
        self.owner_ack_cancelled = False

    def bind_environment(self, environment):
        """Bind the plan's partition and plugin/resource paths."""
        self._readiness.bind_environment(environment)

    async def server_scene(self, plan, process, timeout_s):
        """Delegate passive server and scene readiness checks."""
        await self._readiness.server_scene(plan, process, timeout_s)
        if self.readiness_complete_event is not None:
            self.readiness_complete_event.set()

    async def gui_process_started(self, plan, process, timeout_s):
        """Delegate the audited GUI process liveness check."""
        await self._readiness.gui_process_started(plan, process, timeout_s)

    async def owner_ack(self, timeout_s):
        """Collect Owner acknowledgment and hash the supplied screenshot."""
        try:
            accepted, reference = await self._readiness.owner_ack(timeout_s)
        except asyncio.CancelledError:
            self.owner_ack_cancelled = True
            raise
        if not accepted:
            return False, reference
        path = Path(reference).expanduser()
        if not path.is_absolute():
            raise ObservationFailure('screenshot reference must be absolute')
        path = path.resolve(strict=True)
        if not path.is_file() or path.stat().st_size <= 0:
            raise ObservationFailure(
                'Owner screenshot is not a non-empty file',
            )
        self.screenshot_path = path
        self.screenshot_sha256 = sha256_file(path)
        if self.owner_ack_event is not None:
            self.owner_ack_event.set()
        return True, str(path)

    async def wait_owner_abort(self):
        """Require direct TTY input to classify GUI close as Owner abort."""
        reader = getattr(self._readiness, '_read_stdin_line', None)
        if reader is None:
            await asyncio.Future()
        while True:
            value = await reader(
                'type OWNER_ABORT_GUI before closing to record Owner abort: '
            )
            if value is None:
                return False
            if value == 'OWNER_ABORT_GUI':
                return True


class TrackedProcessLauncher:
    """Use the audited launcher while checking its owned session identity."""

    def __init__(self, delegate, on_start=None, identity_reader=None):
        """Wrap the audited launcher with process-start identity tracking."""
        self.delegate = delegate
        self.on_start = on_start
        self.identity_reader = identity_reader or process_start_identity
        self.identities = {}
        self.records = []
        self.waiters = {}

    async def start(self, command, environment):
        """Start a process and record its PID/session identity immediately."""
        process = await self.delegate.start(command, environment)
        record = SimpleNamespace(
            name=_process_label(command), command=tuple(command),
            pid=process.pid, process=process, identity=None,
            identity_error=None,
        )
        self.records.append(record)
        self.waiters[id(process)] = asyncio.create_task(process.wait())
        try:
            identity = self.identity_reader(process.pid)
            if (
                identity.get('pid') != process.pid
                or identity.get('process_group_id') != process.pid
                or identity.get('session_id') != process.pid
            ):
                raise ObservationFailure(
                    'new launcher process is not its owned session leader'
                )
            record.identity = identity
            self.identities[id(process)] = identity
        except BaseException as error:
            record.identity_error = f'{type(error).__name__}:{error}'
            raise
        if self.on_start is not None:
            self.on_start(record, record.identity)
        return process

    def _members(self, process):
        identity = self.identities.get(id(process))
        if identity is None:
            raise ObservationFailure(
                'owned process group identity is unknown; '
                'residue is unverified'
            )
        members = []
        for entry in Path('/proc').iterdir():
            if not entry.name.isdigit():
                continue
            try:
                current = process_start_identity(int(entry.name))
            except (
                FileNotFoundError, ProcessLookupError,
                PermissionError, ValueError,
            ):
                continue
            if (
                current['process_group_id'] == identity['process_group_id']
                and current['session_id'] == identity['session_id']
                and current['start_ticks'] >= identity['start_ticks']
            ):
                members.append(current)
        return identity, members

    def group_alive(self, process):
        """Check members against the process group and session identity."""
        if id(process) not in self.identities:
            if process.returncode is not None:
                raise ObservationFailure(
                    'leader exited before its process-group identity was read'
                )
            return self.delegate.group_alive(process)
        _identity, members = self._members(process)
        return bool(members)

    async def stop_group(self, process, sig):
        """Signal only members whose current proc identity remains owned."""
        if id(process) not in self.identities:
            if process.returncode is not None:
                raise ObservationFailure(
                    'cannot signal an unverified group after leader exit'
                )
            await self.delegate.stop_group(process, sig)
            return
        identity, members = self._members(process)
        if not members:
            return
        leader = next(
            (item for item in members if item['pid'] == process.pid), None,
        )
        if (
            leader is not None
            and leader['start_ticks'] == identity['start_ticks']
        ):
            await self.delegate.stop_group(process, sig)
            return
        # The leader exited; signal only members whose live proc identity was
        # captured in the currently verified owned session.
        import signal
        for member in members:
            current = process_start_identity(member['pid'])
            if current != member:
                continue
            try:
                os.kill(
                    member['pid'],
                    sig if isinstance(sig, int) else signal.SIGINT,
                )
            except ProcessLookupError:
                pass


class ResilientSupervisor:
    """Instantiate the canonical supervisor with failure-resilient cleanup."""

    def __new__(cls, base_type, **kwargs):
        """Create the audited supervisor with best-effort owned cleanup."""
        cleanup_window = kwargs.pop('cleanup_window')
        cleanup_errors = kwargs.pop('cleanup_errors')
        cleanup_options = kwargs.pop('cleanup_options', {})

        class BoundSupervisor(base_type):
            async def cleanup(self):
                captured = list(self.owned)
                base_task = None
                cancelled = False
                try:
                    deadline = cleanup_window.begin()
                    base_task = asyncio.create_task(super().cleanup())
                    done, _ = await asyncio.wait(
                        {base_task}, timeout=max(
                            0.0, deadline - cleanup_window.steady(),
                        ),
                    )
                    if base_task not in done:
                        base_task.cancel()
                        cleanup_errors.append('base_cleanup_timeout')
                        joined, _ = await asyncio.wait(
                            {base_task}, timeout=max(
                                0.0, deadline - cleanup_window.steady(),
                            ),
                        )
                        if not joined:
                            cleanup_errors.append(
                                'base_cleanup_task_residue_unknown'
                            )
                        else:
                            await asyncio.gather(
                                base_task, return_exceptions=True,
                            )
                    else:
                        error = base_task.exception()
                        if error is not None:
                            raise error
                except asyncio.CancelledError:
                    cancelled = True
                    if base_task is not None and not base_task.done():
                        base_task.cancel()
                        joined, _ = await asyncio.wait(
                            {base_task}, timeout=max(
                                0.0, cleanup_window.begin()
                                - cleanup_window.steady(),
                            ),
                        )
                        if joined:
                            await asyncio.gather(
                                base_task, return_exceptions=True,
                            )
                        else:
                            cleanup_errors.append(
                                'base_cleanup_task_residue_unknown'
                            )
                except BaseException as error:
                    cleanup_errors.append(
                        f'base_cleanup:{type(error).__name__}:{error}'
                    )
                finally:
                    await _fallback_cleanup(
                        self.launcher, captured, self.evidence_sink,
                        cleanup_errors, deadline=cleanup_window.begin(),
                        steady=cleanup_window.steady,
                        **cleanup_options,
                    )
                if cleanup_window.steady() >= cleanup_window.begin():
                    if any('residue' in item or 'timeout' in item
                           for item in cleanup_errors):
                        raise ObservationFailure(
                            'cleanup deadline/residue was not cleared'
                        )
                if cancelled:
                    raise asyncio.CancelledError
        return BoundSupervisor(**kwargs)


class CleanupWindow:
    """One immutable cleanup deadline shared by every cleanup path."""

    def __init__(self, consumed_at, total_deadline, steady=time.monotonic):
        """Bind one cleanup window to the run's absolute total deadline."""
        self.consumed_at = consumed_at
        self.total_deadline = total_deadline
        self.steady = steady
        self.started_at = None
        self.deadline = None

    def begin(self):
        """Return the same absolute deadline on every cleanup invocation."""
        if self.started_at is None:
            self.started_at = self.steady()
            self.deadline = min(
                self.started_at + CLEANUP_CAP_S, self.total_deadline,
            )
        return self.deadline


def _process_label(command):
    values = tuple(str(value) for value in command)
    if (
        len(values) > 2 and values[0].endswith('/ros2')
        and 'parameter_bridge' in values
    ):
        return 'parameter_bridge'
    if len(values) > 1 and values[1:3] == ('run', 'robot_state_publisher'):
        return 'robot_state_publisher'
    if '-g' in values:
        return 'gui'
    if '-s' in values:
        return 'server'
    return 'owned_process'


class PassiveBackendObserver:
    """Owned ROS context with backend-state and clock subscribers only."""

    def __init__(self, ros_api_factory=None, *, steady_ns=time.monotonic_ns):
        """Prepare an independent observer context without initializing ROS."""
        self.context = None
        self.executor = None
        self.node = None
        self.subscriptions = []
        self._node_add_attempted = False
        self.events = deque()
        self._rclpy = None
        self._ros_api_factory = ros_api_factory
        self._steady_ns = steady_ns
        self._closed = False

    @staticmethod
    def _production_ros_api():
        import rclpy
        from rclpy.context import Context
        from rclpy.executors import SingleThreadedExecutor
        from rclpy.node import Node
        from rclpy.qos import (
            DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy,
        )
        from mecanum_nav_rl_interfaces.msg import SimulationContactState
        from rosgraph_msgs.msg import Clock
        return SimpleNamespace(
            rclpy=rclpy, Context=Context, Node=Node,
            SingleThreadedExecutor=SingleThreadedExecutor,
            SimulationContactState=SimulationContactState, Clock=Clock,
            QoSProfile=QoSProfile, HistoryPolicy=HistoryPolicy,
            ReliabilityPolicy=ReliabilityPolicy,
            DurabilityPolicy=DurabilityPolicy,
        )

    @staticmethod
    def clock_qos_profile(api):
        """Match the pinned ros_gz_bridge CLOCK profile's delivery policy."""
        return api.QoSProfile(
            history=api.HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=api.ReliabilityPolicy.BEST_EFFORT,
            durability=api.DurabilityPolicy.VOLATILE,
        )

    def start(self):
        """Initialize a private context with status and clock subscribers."""
        self._closed = False
        api = (
            self._ros_api_factory()
            if self._ros_api_factory is not None
            else self._production_ros_api()
        )
        self._rclpy = api.rclpy
        self.context = api.Context()
        self._rclpy.init(context=self.context, domain_id=83)
        self.executor = api.SingleThreadedExecutor(context=self.context)
        self.node = api.Node(
            'b22_gui_observation_observer', context=self.context,
        )
        self._node_add_attempted = True
        if self.executor.add_node(self.node) is False:
            raise ObservationFailure('observer executor rejected its node')
        self.subscriptions.append(self.node.create_subscription(
            api.SimulationContactState,
            '/mecanum/local_training/backend_state',
            lambda message: self._record_event('backend', message), 50,
        ))
        self.subscriptions.append(self.node.create_subscription(
            api.Clock, '/clock',
            lambda message: self._record_event('clock', message.clock),
            self.clock_qos_profile(api),
        ))

    def _record_event(self, kind, message):
        self.events.append((
            kind, message, time.monotonic(), self._steady_ns(),
        ))

    def spin_once(self, timeout_s: float = 0.1):
        """Process passive observer callbacks for one bounded interval."""
        if self.executor is None or self.node is None:
            raise ObservationFailure('observer executor is not active')
        self.executor.spin_once(timeout_sec=timeout_s)

    def close(self, *, deadline=None, steady=time.monotonic):
        """Release each owned ROS resource once, continuing after errors."""
        if self._closed:
            return
        self._closed = True
        errors = []
        executor, self.executor = self.executor, None
        node, self.node = self.node, None
        context, self.context = self.context, None
        if (
            executor is not None and node is not None
            and self._node_add_attempted
        ):
            try:
                executor.remove_node(node)
            except BaseException as error:
                errors.append(error)
        if executor is not None:
            try:
                timeout = (
                    max(0.0, deadline - steady())
                    if deadline is not None else CLEANUP_CAP_S
                )
                if executor.shutdown(timeout_sec=timeout) is False:
                    raise TimeoutError('observer executor shutdown timed out')
            except BaseException as error:
                errors.append(error)
        try:
            if node is not None:
                node.destroy_node()
        except BaseException as error:
            errors.append(error)
        self.subscriptions.clear()
        try:
            if (
                context is not None and self._rclpy is not None
                and self._rclpy.ok(context=context)
            ):
                self._rclpy.shutdown(context=context)
        except BaseException as error:
            errors.append(error)
        if errors:
            raise ObservationFailure(
                f'observer context cleanup failed: {type(errors[0]).__name__}'
            ) from errors[0]

    def node_inventory(self):
        """Read the post-consume graph from this owned observer node."""
        if self.node is None:
            raise ObservationFailure('observer node is not active')
        return self.node.get_node_names_and_namespaces()


async def evaluate_observation(
    *, plan, observer, duration_s: float = OBSERVATION_S,
    steady=time.monotonic, ack_event=None, owner_abort_event=None,
    deadline=None, sink=None, expected_nodes=EXPECTED_ROS_NODES,
    temporary_nodes=STARTUP_TEMPORARY_ROS_NODES,
    readiness_complete_event=None, graph_convergence_s=30.0,
    temporary_stale_s=30.0,
    clock_ready_timeout_s=CLOCK_READY_TIMEOUT_S,
):
    """Monitor status and clock through acknowledgment and observation."""
    monitor_started = steady()
    acknowledgement_time = None
    observation_start = None
    last_heartbeat = None
    last_status_sequence = None
    status_count = 0
    clock_value = None
    clock_stable_since = None
    last_clock_received = None
    clock_count = 0
    backend_identity = None
    seen_nodes = None
    readiness_completed_at = None
    while True:
        now = steady()
        if owner_abort_event is not None and owner_abort_event.is_set():
            raise OwnerAbort(
                'Owner explicitly requested GUI observation abort'
            )
        if deadline is not None and now >= deadline:
            raise ObservationFailure('240 s consume-to-end deadline expired')
        if now - monitor_started > clock_ready_timeout_s and clock_count == 0:
            raise ObservationFailure('clock readiness timed out')
        observer.spin_once(min(POLL_SLICE_S, max(0.001, duration_s)))
        while observer.events:
            event = observer.events.popleft()
            kind, message, received = event[:3]
            received_ns = event[3] if len(event) > 3 else int(received * 1e9)
            if kind == 'clock':
                stamp = (message.sec, message.nanosec)
                if clock_value is None:
                    clock_value = stamp
                elif stamp != clock_value:
                    raise ObservationFailure('simulation clock advanced')
                elif clock_stable_since is None:
                    clock_stable_since = received
                if (
                    last_clock_received is not None
                    and received - last_clock_received > CLOCK_SAMPLE_GAP_S
                ):
                    raise ObservationFailure('clock sample gap exceeded 1 s')
                last_clock_received = received
                clock_count += 1
                if sink is not None:
                    sink.record('clock_sample', {
                        'clock_sec': stamp[0], 'clock_nanosec': stamp[1],
                        'receive_steady_s': received,
                        'receive_steady_ns': received_ns,
                        'sample_index': clock_count,
                    })
                continue
            identity = (
                message.session_id, message.config_hash,
                message.backend_instance_id, message.header.frame_id,
            )
            if identity != (
                plan.session_id, plan.config_hash,
                identity[2], 'b2_training_arena',
            ) or not identity[2]:
                raise ObservationFailure('backend identity mismatch')
            if backend_identity is None:
                backend_identity = identity
            elif identity != backend_identity:
                raise ObservationFailure('backend identity changed')
            if not message.paused or not message.actuator_inhibited:
                raise ObservationFailure('backend is not paused and inhibited')
            if message.fault_flags != 0:
                raise ObservationFailure('backend reports fault flags')
            if message.applied_receipt_valid:
                raise ObservationFailure('applied receipt observed')
            if message.status_sequence <= 0:
                raise ObservationFailure('invalid backend heartbeat sequence')
            if (
                last_status_sequence is not None
                and message.status_sequence <= last_status_sequence
            ):
                raise ObservationFailure(
                    'backend heartbeat sequence did not increase'
                )
            if (
                last_heartbeat is not None
                and received - last_heartbeat > HEARTBEAT_GAP_S
            ):
                raise ObservationFailure('backend heartbeat gap exceeded 1 s')
            last_heartbeat = received
            last_status_sequence = message.status_sequence
            status_count += 1
            if sink is not None:
                sink.record('backend_status_sample', {
                    'session_id': message.session_id,
                    'config_hash': message.config_hash,
                    'backend_instance_id': message.backend_instance_id,
                    'world': message.header.frame_id,
                    'status_sequence': message.status_sequence,
                    'paused': message.paused,
                    'actuator_inhibited': message.actuator_inhibited,
                    'fault_flags': message.fault_flags,
                    'applied_receipt_valid': message.applied_receipt_valid,
                    'receive_steady_s': received,
                    'receive_steady_ns': received_ns,
                    'sample_index': status_count,
                })
        if hasattr(observer, 'node_inventory'):
            inventory = observer.node_inventory()
            participants = list(inventory)
            unique_participants = set(participants)
            names = {name for name, _namespace in participants}
            if len(participants) != len(unique_participants):
                raise ObservationFailure(
                    'duplicate ROS graph participant names were observed'
                )
            unexpected = unique_participants - (
                set(expected_nodes) | set(temporary_nodes)
            )
            if unexpected:
                raise ObservationFailure(
                    f'unexpected ROS graph participants: {sorted(unexpected)}'
                )
            if readiness_complete_event is None:
                readiness_completed_at = monitor_started
            elif readiness_complete_event.is_set() and (
                readiness_completed_at is None
            ):
                readiness_completed_at = now
            permanent_missing = set(expected_nodes) - unique_participants
            if readiness_completed_at is not None:
                if (permanent_missing and now - readiness_completed_at
                        >= graph_convergence_s):
                    raise ObservationFailure(
                        'ROS graph did not converge after scene readiness: '
                        f'{sorted(permanent_missing)}'
                    )
                stale_temporary = unique_participants & set(temporary_nodes)
                if (stale_temporary and now - readiness_completed_at
                        >= temporary_stale_s):
                    raise ObservationFailure(
                        'temporary readiness ROS node remained in graph'
                    )
            if unique_participants != seen_nodes:
                seen_nodes = unique_participants
                if sink is not None:
                    sink.record('ros_graph_inventory', {
                        'nodes': sorted(names),
                        'participants': [
                            list(item) for item in sorted(unique_participants)
                        ],
                        'unexpected_nodes': sorted(unexpected),
                    })
        now = steady()
        if (
            last_heartbeat is not None
            and now - last_heartbeat > HEARTBEAT_GAP_S
        ):
            raise ObservationFailure('backend heartbeat lost for over 1 s')
        if last_clock_received is not None and (
            now - last_clock_received > CLOCK_SAMPLE_GAP_S
        ):
            raise ObservationFailure(
                'clock samples stopped during observation'
            )
        if (last_heartbeat is None
                and now - monitor_started > clock_ready_timeout_s):
            raise ObservationFailure('backend status readiness timed out')
        if (
            ack_event is not None and ack_event.is_set()
            and acknowledgement_time is None
        ):
            acknowledgement_time = now
        clock_stable = (
            clock_stable_since is not None
            and now - clock_stable_since >= 1.0
        )
        if (
            acknowledgement_time is not None and clock_stable
            and observation_start is None
        ):
            observation_start = now
        if (
            observation_start is not None
            and now - observation_start >= duration_s
        ):
            return {
                'backend_identity': list(backend_identity),
                'last_status_sequence': last_status_sequence,
                'backend_status_samples': status_count,
                'heartbeat_last_steady': last_heartbeat,
                'clock_samples': clock_count,
                'clock_stamp': list(clock_value),
                'observed_seconds': now - observation_start,
            }
        await asyncio.sleep(0)


def _installed_paths():
    from ament_index_python.packages import (
        get_package_prefix, get_package_share_directory,
    )
    from mecanum_nav_bringup.local_training_process_supervisor import (
        _physics_engine_plugin_path,
    )

    description = Path(get_package_share_directory(
        'ROBOT_URDF_final_description',
    )).resolve(strict=True)
    rl_share = Path(get_package_share_directory('mecanum_nav_rl')).resolve(
        strict=True,
    )
    bringup = Path(get_package_share_directory('mecanum_nav_bringup')).resolve(
        strict=True,
    )
    backend_prefix = Path(get_package_prefix('mecanum_sim_backend')).resolve(
        strict=True,
    )
    interfaces_prefix = Path(get_package_prefix(
        'mecanum_nav_rl_interfaces',
    )).resolve(strict=True)
    return {
        'description_share': description,
        'rl_share': rl_share,
        'bringup_share': bringup,
        'backend_prefix': backend_prefix,
        'interfaces_prefix': interfaces_prefix,
        'physics_engine_path': _physics_engine_plugin_path(),
    }


def _fingerprint_install(paths: dict[str, Path]) -> dict[str, str]:
    candidates = {
        'world': paths['description_share'] / 'worlds/b2_training_arena.sdf',
        'model': paths['description_share'] / 'models/mecanum_b2/model.sdf',
        'robot_urdf': paths['description_share'] / (
            'urdf/mecanum_b2_static.urdf'
        ),
        'gui_config': paths['bringup_share'] / (
            'config/gui/local_training.config'
        ),
        'bridge_config': paths['bringup_share'] / (
            'config/bridge/local_training.runtime.yaml'
        ),
        'local_training_launch': paths['bringup_share'] / (
            'launch/sim_train_local_training.launch.py'
        ),
        'asset_manifest': paths['description_share'] / (
            'manifests/b2/asset_manifest.json'
        ),
        'resolved_config': paths['rl_share'] / (
            'config/v3/resolved/sim_train_local_training_soak.resolved.json'
        ),
        'scenario': paths['rl_share'] / (
            'scenarios/local_training/B2_SOAK_V1.json'
        ),
        'backend_system': paths['backend_prefix'] / (
            'lib/libmecanum_sim_backend_system.so'
        ),
        'backend_core': paths['backend_prefix'] / (
            'lib/libmecanum_sim_backend_core.so'
        ),
        'launch_contract': (
            paths['bringup_share'].parent.parent
            / 'lib/python3.12/site-packages/'
            / 'mecanum_nav_bringup/local_training_launch_contract.py'
        ),
        'process_supervisor': (
            paths['bringup_share'].parent.parent
            / 'lib/python3.12/site-packages/'
            / 'mecanum_nav_bringup/local_training_process_supervisor.py'
        ),
    }
    result = {}
    for name, path in candidates.items():
        resolved = path.resolve(strict=True)
        if not resolved.is_file():
            raise ObservationFailure(f'installed {name} is not a file')
        result[str(resolved)] = sha256_file(resolved)
    description_share = paths['description_share']
    manifest_path = description_share / 'manifests/b2/asset_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    for relative in sorted(manifest['resource_closure']):
        path = description_share.parent / relative
        resolved = path.resolve(strict=True)
        result[str(resolved)] = sha256_file(resolved)
    install_root = paths['backend_prefix']
    interface_lib = install_root / 'lib'
    for path in sorted(interface_lib.glob('libmecanum_nav_rl_interfaces*.so')):
        result[str(path.resolve(strict=True))] = sha256_file(path)
    for path in (
        Path(
            '/opt/ros/jazzy/opt/gz_sim_vendor/lib/'
            'libgz-sim8-scene-broadcaster-system.so.8.11.0'
        ),
        Path(
            '/opt/ros/jazzy/opt/gz_sim_vendor/lib/'
            'libgz-sim8-sensors-system.so.8.11.0'
        ),
        Path(
            '/opt/ros/jazzy/opt/gz_rendering_vendor/lib/'
            'libgz-rendering8-ogre2.so.8.2.3'
        ),
        Path(
            '/opt/ros/jazzy/opt/gz_rendering_vendor/lib/'
            'gz-rendering-8/engine-plugins/'
            'libgz-rendering8-ogre2.so.8.2.3'
        ),
        Path(shutil.which('gz') or ''), Path(shutil.which('ros2') or ''),
        Path('/opt/ros/jazzy/lib/ros_gz_bridge/parameter_bridge'),
        Path('/opt/ros/jazzy/lib/robot_state_publisher/robot_state_publisher'),
        Path('/opt/ros/jazzy/lib/libros_gz_bridge.so'),
        Path('/opt/ros/jazzy/lib/librobot_state_publisher_node.so'),
    ):
        resolved = path.resolve(strict=True)
        result[str(resolved)] = sha256_file(resolved)
    for interface_asset in (
        'msg/SimulationContactState.msg',
        'msg/FinalIssuedCommandReceipt.msg',
        'srv/LocalTrainingBackendControl.srv',
    ):
        path = (
            install_root / 'share/mecanum_nav_rl_interfaces' / interface_asset
        )
        resolved = path.resolve(strict=True)
        result[str(resolved)] = sha256_file(resolved)
    for path in sorted(paths['physics_engine_path'].glob('*')):
        if path.is_file():
            resolved = path.resolve(strict=True)
            result[str(resolved)] = sha256_file(resolved)
    return result


def _exclusive_copy(source: Path, destination: Path) -> None:
    """Copy bytes into a new evidence path without replacing prior evidence."""
    data = source.read_bytes()
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(destination, flags, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def build_runtime_plan(gui: bool, temp_dir: Path):
    """Resolve installed B2 assets and call the audited pure launch API."""
    require_run_gui(gui)
    from mecanum_nav_bringup.local_training_launch_contract import (
        build_launch_plan, load_bound_config, write_bound_world,
    )
    from mecanum_nav_bringup.local_training_process_supervisor import (
        _physics_engine_plugin_path,
    )

    paths = _installed_paths()
    config = paths['rl_share'] / (
        'config/v3/resolved/sim_train_local_training_soak.resolved.json'
    )
    world = paths['description_share'] / 'worlds/b2_training_arena.sdf'
    model = paths['description_share'] / 'models/mecanum_b2/model.sdf'
    gui_config = paths['bringup_share'] / 'config/gui/local_training.config'
    bridge = paths['bringup_share'] / (
        'config/bridge/local_training.runtime.yaml'
    )
    document, config_hash, manifest_hash, scenario_id = (
        load_bound_config(config)
    )
    if (
        sha256_file(config) != RESOLVED_SHA256
        or config_hash != CONFIG_HASH
        or manifest_hash != MANIFEST_SHA256
        or scenario_id != 'B2_SOAK_V1'
        or sha256_file(
            paths['rl_share'] / 'scenarios/local_training/B2_SOAK_V1.json'
        )
        != SCENARIO_SHA256
    ):
        raise ObservationFailure('installed B2 input pins do not match packet')
    session_id = str(uuid.uuid4())
    ingress_id = secrets.randbits(64) or 1
    partition = f"mecanum_b2_{session_id.replace('-', '')}"
    plan = build_launch_plan(
        gui='true', resolved_config=config, world_file=world,
        gui_config=gui_config, session_id=session_id, partition=partition,
        bridge_config=bridge,
        resource_paths=(paths['description_share'].parent,
                        paths['description_share'] / 'models'),
        plugin_path=paths['backend_prefix'] / 'lib',
        physics_engine_plugin_path=_physics_engine_plugin_path(),
        asset_manifest_file=(
            paths['description_share'] / 'manifests/b2/asset_manifest.json'
        ),
        scenario_directory=paths['rl_share'] / 'scenarios/local_training',
        runtime_world_directory=temp_dir,
        coordinator_ingress_instance_id=ingress_id,
    )
    descriptor = {
        'schema_id': 'mecanum_b2_run_descriptor/v1',
        'run_id': RUN_ID,
        'session_id': plan.session_id,
        'config_hash': plan.config_hash,
        'asset_manifest_sha256': plan.asset_manifest_sha256,
        'coordinator_ingress_instance_id': (
            plan.coordinator_ingress_instance_id
        ),
        'ros_domain_id': 83,
        'world_source_sha256': sha256_file(world),
        'runtime_bound_world_sha256': None,
        'robot_state_publisher_params_sha256': None,
    }
    bound_path = write_bound_world(plan, world, model)
    descriptor['runtime_bound_world_sha256'] = sha256_file(bound_path)
    urdf_path = paths['description_share'] / 'urdf/mecanum_b2_static.urdf'
    params_path = temp_dir / 'robot_state_publisher.params.yaml'
    params = (
        '/**:\n  ros__parameters:\n    robot_description: '
        + json.dumps(urdf_path.read_text(encoding='utf-8'))
        + '\n    use_sim_time: true\n'
    )
    with params_path.open('x', encoding='utf-8') as stream:
        stream.write(params)
        stream.flush()
        os.fsync(stream.fileno())
    descriptor['robot_state_publisher_params_sha256'] = sha256_file(
        params_path
    )
    descriptor_path = temp_dir / 'run_descriptor.json'
    with descriptor_path.open('x', encoding='utf-8') as stream:
        json.dump(descriptor, stream, sort_keys=True, separators=(',', ':'))
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    return plan, paths, descriptor, descriptor_path


def _validate_plan_commands(plan, packet):
    """Match audited launch composition to the packet command contract."""
    templates = packet['commands_argv']['exact_templates']
    if not plan.gui_requested or len(plan.commands) != 2:
        raise ObservationFailure('launch plan is not the one-GUI RUN001 plan')
    server, gui = (tuple(command) for command in plan.commands)
    expected_server = tuple(templates['server'][:-1]) + (str(plan.world_file),)
    if server != expected_server:
        raise ObservationFailure('server argv differs from approved packet')
    if gui != tuple(templates['gui']):
        raise ObservationFailure('GUI argv differs from approved packet')
    bridge = tuple(getattr(plan, 'bridge_command', ()) or ())
    if bridge != tuple(templates['parameter_bridge']):
        raise ObservationFailure('bridge argv differs from approved packet')


def _check_output_tasks(supervisor, sink):
    """Raise on background stdout/stderr task failure without swallowing it."""
    for record in tuple(getattr(supervisor, 'owned', ())):
        for task in getattr(record, 'output_tasks', ()):
            if not task.done():
                continue
            if task.cancelled():
                raise ObservationFailure(
                    f'background output task was cancelled: {record.name}'
                )
            error = task.exception()
            if error is not None:
                sink.record('background_output_failure', {
                    'process': record.name,
                    'error_type': type(error).__name__,
                    'error': str(error)[:1000],
                })
                raise ObservationFailure(
                    f'background output evidence failed: {record.name}'
                ) from error


async def _monitor_owned_processes(
    *, launcher, supervisor, readiness, sink, ack_event,
    owner_abort_event, stop_event, deadline, steady,
):
    """Monitor role exits and output evidence from the first owned spawn."""
    owner_abort_task = None
    try:
        while not stop_event.is_set():
            if ack_event.is_set() and owner_abort_task is None:
                owner_abort_task = asyncio.create_task(
                    readiness.wait_owner_abort(),
                )
            if owner_abort_task is not None and owner_abort_task.done():
                if owner_abort_task.cancelled():
                    raise ObservationFailure(
                        'Owner abort watcher was cancelled'
                    )
                if owner_abort_task.exception() is not None:
                    raise ObservationFailure(
                        'Owner abort watcher failed'
                    ) from owner_abort_task.exception()
                if owner_abort_task.result():
                    owner_abort_event.set()
                    sink.record('owner_abort_requested', {
                        'token': 'OWNER_ABORT_GUI',
                        'source': 'direct_owner_tty',
                    })
                    owner_abort_task = None
            for record in tuple(launcher.records):
                waiter = launcher.waiters.get(id(record.process))
                if waiter is None or not waiter.done():
                    continue
                if waiter.cancelled():
                    raise ObservationFailure(
                        f'owned process waiter cancelled: {record.name}'
                    )
                status = waiter.result()
                sink.record('owned_process_exit', {
                    'process': record.name, 'pid': record.pid,
                    'exit_status': status,
                })
                if (
                    record.name == 'gui' and status == 0
                    and owner_abort_event.is_set()
                ):
                    raise OwnerAbort(
                        'Owner requested abort and GUI exited normally'
                    )
                raise ObservationFailure(
                    'owned process exited unexpectedly: '
                    f'{record.name} ({status})'
                )
            _check_output_tasks(supervisor, sink)
            await asyncio.sleep(0)
    finally:
        if owner_abort_task is not None and not owner_abort_task.done():
            owner_abort_task.cancel()
        if owner_abort_task is not None:
            remaining = max(0.0, deadline - steady())
            done, _ = await asyncio.wait(
                {owner_abort_task}, timeout=remaining,
            )
            if done:
                await asyncio.gather(
                    owner_abort_task, return_exceptions=True,
                )
            else:
                raise ObservationFailure(
                    'Owner abort watcher residue after cancellation'
                )


async def _wait_competing(
    awaitable, monitor_task, deadline, steady, observer_task=None,
):
    """Wait for one operation while process monitoring remains active."""
    operation = asyncio.ensure_future(awaitable)
    remaining = deadline - steady()
    try:
        if remaining <= 0:
            raise ObservationFailure('240 s consume-to-end deadline expired')
        competing = {operation, monitor_task}
        if observer_task is not None:
            competing.add(observer_task)
        done, _pending = await asyncio.wait(
            competing, timeout=remaining,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if monitor_task in done:
            if monitor_task.cancelled():
                raise ObservationFailure('owned-process monitor was cancelled')
            error = monitor_task.exception()
            if error is not None:
                raise error
            raise ObservationFailure(
                'owned-process monitor stopped unexpectedly'
            )
        if observer_task is not None and observer_task in done:
            if observer_task.cancelled():
                raise ObservationFailure('observation monitor was cancelled')
            error = observer_task.exception()
            if error is not None:
                raise error
            raise ObservationFailure(
                'observation completed before startup/Owner acknowledgment'
            )
        if operation in done:
            return operation.result()
        raise ObservationFailure('240 s consume-to-end deadline expired')
    finally:
        if not operation.done():
            operation.cancel()
            remaining = min(1.0, max(0.0, deadline - steady()))
            done, _pending = await asyncio.wait(
                {operation}, timeout=remaining,
            )
            if done:
                await asyncio.gather(operation, return_exceptions=True)
            else:
                raise ObservationFailure(
                    'cancelled operation did not join before runtime deadline'
                )


async def _join_task(task, *, timeout_s):
    """Cancel and join one owned asyncio task within a bounded interval."""
    if task is None:
        return True
    if not task.done():
        task.cancel()
    done, _pending = await asyncio.wait({task}, timeout=max(0.0, timeout_s))
    if not done:
        return False
    await asyncio.gather(task, return_exceptions=True)
    return True


async def _run(args, *, dependencies=None):
    """Run one approved observation with injectable test boundaries."""
    deps = dependencies or {}
    mono = deps.get('monotonic', time.monotonic)
    wall_utc = deps.get('utc_now', _utc_now)
    require_run_gui(args.gui)
    preflight = deps.get('preflight', preflight_desktop)
    preflight(
        deps.get('stdin_isatty', sys.stdin.isatty()),
        deps.get('environ', os.environ),
        deps.get('exists', lambda path: Path(path).exists()),
    )
    packet_path = Path(args.packet).resolve(strict=True)
    approval_path = Path(args.approval_file).resolve(strict=True)
    packet, packet_hash, hashes = validate_approval(
        packet_path=packet_path, approval_path=approval_path,
        expected_commit=args.approved_commit, tool_paths=TOOL_PATHS,
    )
    bindings = assert_packet_inputs(packet, hashes)
    verify_commit = deps.get('verify_commit', verify_packet_commit)
    verify_commit(args.approved_commit, packet_path)
    injected_paths = dependencies is not None
    guard_path = Path(deps.get('guard_path', GUARD_PATH))
    evidence_root = Path(deps.get('evidence_root', EVIDENCE_ROOT))
    guard_path, evidence_root = validate_run_roots(
        guard_path, evidence_root,
        expected_guard=guard_path if injected_paths else GUARD_PATH,
        expected_evidence=evidence_root if injected_paths else EVIDENCE_ROOT,
    )
    if not guard_path.parent.is_dir():
        raise GuardError('canonical acquisition directory must be provisioned')

    install_preflight = deps.get('install_preflight')
    install_fingerprints = install_preflight() if install_preflight else None
    temp_parent = Path(args.temp_root)
    temp_parent.mkdir(parents=True, exist_ok=True)
    runtime_dir_context = deps.get(
        'temporary_directory_factory', tempfile.TemporaryDirectory,
    )(
        prefix='b22_gui_observation_run001_', dir=temp_parent,
    )
    runtime_dir = Path(runtime_dir_context.name)
    try:
        plan, paths, descriptor, descriptor_path = deps.get(
            'build_plan', build_runtime_plan,
        )(args.gui, runtime_dir)
        _validate_plan_commands(plan, packet)
    except BaseException:
        runtime_dir_context.cleanup()
        raise
    fingerprints = install_fingerprints or _fingerprint_install(paths)
    if fingerprints != bindings['file_sha256']:
        runtime_dir_context.cleanup()
        raise ObservationFailure(
            'installed file fingerprints differ from packet'
        )
    ros2_template = tuple(
        packet['commands_argv']['exact_templates'][
            'robot_state_publisher'
        ]
    )
    if injected_paths:
        ros2_template = tuple(
            value.replace(str(EVIDENCE_ROOT), str(evidence_root))
            for value in ros2_template
        )
    ros2_executable = deps.get('ros2_executable') or shutil.which('ros2')
    params_path = evidence_root / 'runtime_assets'
    params_path /= 'robot_state_publisher.params.yaml'
    planned_rsp_command = (
        ros2_executable, 'run', 'robot_state_publisher',
        'robot_state_publisher', '--ros-args', '--params-file',
        str(params_path),
    )
    if (not ros2_executable or ros2_executable != ros2_template[0]
            or planned_rsp_command != ros2_template):
        runtime_dir_context.cleanup()
        raise ObservationFailure(
            'robot_state_publisher argv differs from approved packet'
        )
    if not Path(ros2_executable).is_file():
        runtime_dir_context.cleanup()
        raise ObservationFailure('installed ros2 executable is missing')

    run_id = deps.get('run_id', RUN_ID)
    process_identity = deps.get(
        'runner_process_identity', process_start_identity,
    )(os.getpid())
    acquisition = {
        'schema_id': 'b22_gui_observation_acquisition/v1',
        'run_id': run_id,
        'capacity': 1,
        'packet_sha256': packet_hash,
        'packet_commit': args.approved_commit,
        'production_source_pin': bindings['production_source_pin'],
        'tool_sha256': hashes,
        'input_sha256': bindings['input_sha256'],
        'installed_sha256': fingerprints,
        'dependency_fingerprints': bindings['dependency_fingerprints'],
        'resolved_install_paths': {
            key: str(value) for key, value in paths.items()
        },
        'session_id': plan.session_id,
        'coordinator_ingress_instance_id': (
            plan.coordinator_ingress_instance_id
        ),
        'gz_partition': plan.environment['GZ_PARTITION'],
        'ros_domain_id': 83,
        'runtime_bound_world_sha256': descriptor['runtime_bound_world_sha256'],
        'robot_state_publisher_params_sha256': descriptor[
            'robot_state_publisher_params_sha256'
        ],
        'run_descriptor_sha256': sha256_file(descriptor_path),
        'host': deps.get('host_identity', _host_identity)(),
        'runner_process': process_identity,
        'steady_ns': deps.get('monotonic_ns', time.monotonic_ns)(),
        'utc_time': wall_utc(),
    }
    try:
        deps.get('acquire', acquire_once)(guard_path, acquisition)
    except BaseException:
        runtime_dir_context.cleanup()
        raise

    consumed_at = mono()
    runtime_deadline = consumed_at + RUNTIME_CAP_S
    total_deadline = consumed_at + TOTAL_CAP_S
    cleanup_window = CleanupWindow(consumed_at, total_deadline, mono)
    sink = None
    supervisor = None
    launcher = None
    observer = None
    observer_task = None
    process_monitor_task = None
    stop_monitor = asyncio.Event()
    owner_ack_event = asyncio.Event()
    owner_abort_event = asyncio.Event()
    final_status = 'FAIL'
    observation_verdict = 'FAIL'
    failure = None
    cleanup_errors = []
    original_environment = {}
    readiness_complete_event = asyncio.Event()
    bound_environment = {'ROS_DOMAIN_ID': '83', **dict(plan.environment)}
    try:
        if not evidence_root.exists():
            evidence_root.mkdir(mode=0o700, parents=False, exist_ok=False)
        sink = deps.get('sink_factory', ObservationEvidenceSink)(
            evidence_root, run_id, plan.session_id,
        )
        sink.record('guard_consumed', {
            'packet_sha256': packet_hash,
            'packet_commit': args.approved_commit,
            'production_source_pin': bindings['production_source_pin'],
            'tool_sha256': hashes,
            'descriptor_path': str(descriptor_path),
            'descriptor_sha256': sha256_file(descriptor_path),
            'source_world_sha256': descriptor['world_source_sha256'],
            'runtime_bound_world_sha256': descriptor[
                'runtime_bound_world_sha256'
            ],
            'install_fingerprints': fingerprints,
            'dependency_fingerprints': bindings['dependency_fingerprints'],
        })
        evidence_assets = evidence_root / 'runtime_assets'
        evidence_assets.mkdir(mode=0o700, exist_ok=False)
        persisted_world = evidence_assets / Path(plan.world_file).name
        persisted_params = evidence_assets / (
            'robot_state_publisher.params.yaml'
        )
        persisted_descriptor = evidence_assets / 'run_descriptor.json'
        _exclusive_copy(Path(plan.world_file), persisted_world)
        _exclusive_copy(runtime_dir / persisted_params.name, persisted_params)
        _exclusive_copy(descriptor_path, persisted_descriptor)
        commands = list(plan.commands)
        commands[0] = tuple(commands[0][:-1]) + (str(persisted_world),)
        plan = replace(
            plan, world_file=persisted_world, commands=tuple(commands),
        )
        sink.record('runtime_assets_persisted', {
            'runtime_bound_world_path': str(persisted_world),
            'runtime_bound_world_sha256': sha256_file(persisted_world),
            'run_descriptor_path': str(persisted_descriptor),
            'run_descriptor_sha256': sha256_file(persisted_descriptor),
            'robot_state_publisher_params_path': str(persisted_params),
            'robot_state_publisher_params_sha256': sha256_file(
                persisted_params
            ),
        })
        original_environment = {
            key: os.environ.get(key) for key in bound_environment
        }
        os.environ.update(bound_environment)

        from mecanum_nav_bringup.local_training_process_supervisor import (
            LocalTrainingProcessSupervisor, ProcessRecord,
            RclpyReadiness, SubprocessProcessLauncher,
        )

        def sink_factory(record, identity):
            return sink.record('owned_process_identity', {
                'process': record.name, 'command': list(record.command),
                'pid': record.pid, 'process_identity': identity,
            })
        launcher = TrackedProcessLauncher(
            deps.get('launcher', SubprocessProcessLauncher()),
            on_start=sink_factory,
            identity_reader=deps.get('process_identity_reader'),
        )
        readiness = ScreenshotReadiness(
            deps.get('readiness', RclpyReadiness()), owner_ack_event,
            readiness_complete_event,
        )
        if deps.get('supervisor_factory'):
            supervisor = deps['supervisor_factory'](
                plan=plan, launcher=launcher, readiness=readiness,
                evidence_sink=sink,
            )
        else:
            supervisor = ResilientSupervisor(
                LocalTrainingProcessSupervisor, plan=plan, launcher=launcher,
                readiness=readiness, evidence_sink=sink,
                cleanup_window=cleanup_window,
                cleanup_errors=cleanup_errors,
                cleanup_options={
                    'sleep': deps.get('cleanup_sleep', asyncio.sleep),
                    'escalation_grace': deps.get(
                        'cleanup_escalation_grace', (5.0, 3.0, 3.0),
                    ),
                },
            )
        observer = deps.get('observer_factory', PassiveBackendObserver)()
        observer.start()
        sink.record('passive_observer_started', {
            'node': 'b22_gui_observation_observer',
            'ros_domain_id': 83,
            'subscriptions': [
                '/mecanum/local_training/backend_state', '/clock',
            ],
            'control_publishers': 0,
            'control_service_clients': 0,
        })
        process_monitor_task = asyncio.create_task(_monitor_owned_processes(
            launcher=launcher, supervisor=supervisor, readiness=readiness,
            sink=sink, ack_event=owner_ack_event,
            owner_abort_event=owner_abort_event, stop_event=stop_monitor,
            deadline=runtime_deadline, steady=mono,
        ))
        observer_task = asyncio.create_task(evaluate_observation(
            plan=plan, observer=observer, duration_s=OBSERVATION_S,
            steady=mono, ack_event=owner_ack_event,
            owner_abort_event=owner_abort_event,
            deadline=runtime_deadline, sink=sink,
            expected_nodes={
                (name, packet['identity_binding'][
                    'expected_ros_node_namespace'
                ]) for name in packet['identity_binding'][
                    'expected_ros_node_names'
                ]
            },
            temporary_nodes={
                (name, packet['identity_binding'][
                    'expected_ros_node_namespace'
                ]) for name in packet['identity_binding'][
                    'startup_temporary_ros_node_names'
                ]
            },
            readiness_complete_event=readiness_complete_event,
            graph_convergence_s=packet['identity_binding'][
                'node_graph_convergence_after_readiness_s'
            ],
            temporary_stale_s=packet['identity_binding'][
                'temporary_node_stale_after_readiness_s'
            ],
        ))
        rsp_command = planned_rsp_command
        rsp = await _wait_competing(
            launcher.start(rsp_command, dict(plan.environment)),
            process_monitor_task, runtime_deadline, mono, observer_task,
        )
        rsp_record = ProcessRecord(
            'robot_state_publisher', rsp_command, rsp.pid, rsp,
        )
        supervisor.owned.append(rsp_record)
        capture_output = getattr(supervisor, '_capture_output', None)
        if capture_output is not None:
            capture_output(rsp_record)
        sink.record('owned_process_started', {
            'process': rsp_record.name, 'command': list(rsp_command),
            'pid': rsp.pid,
            'process_identity': launcher.identities.get(id(rsp)),
        })
        await _wait_competing(
            supervisor.start(), process_monitor_task, runtime_deadline, mono,
            observer_task,
        )
        screenshot = readiness.screenshot_path
        if screenshot is None or readiness.screenshot_sha256 is None:
            raise ObservationFailure('Owner screenshot was not verified')
        sink.record('owner_scene_acknowledged', {
            'screenshot_path': str(screenshot),
            'screenshot_sha256': readiness.screenshot_sha256,
            'confirmation_source': 'direct_owner_tty',
        })
        verdict = await _wait_competing(
            observer_task, process_monitor_task, runtime_deadline, mono,
        )
        if mono() > runtime_deadline:
            raise ObservationFailure('240 s runtime cap exceeded')
        sink.record('observation_result', verdict)
        final_status = 'PASS'
        observation_verdict = 'PASS'
    except OwnerAbort as error:
        failure = error
        final_status = 'ABORTED_BY_OWNER'
        observation_verdict = 'ABORTED_BY_OWNER'
        if sink is not None:
            try:
                sink.record('owner_abort', {
                    'error': str(error), 'source': 'direct_owner_tty',
                })
            except BaseException as sink_error:
                cleanup_errors.append(
                    f'evidence_failure:{type(sink_error).__name__}'
                )
    except BaseException as error:
        failure = error
        final_status = 'FAIL'
        observation_verdict = 'FAIL'
        if sink is not None:
            try:
                sink.record('observation_failure', {
                    'error_type': type(error).__name__,
                    'error': str(error)[:1000],
                    'traceback': ''.join(traceback.format_exception(
                        type(error), error, error.__traceback__,
                    ))[-12000:],
                })
            except BaseException as sink_error:
                cleanup_errors.append(
                    f'evidence_failure:{type(sink_error).__name__}'
                )
    finally:
        cleanup_deadline = cleanup_window.begin()
        cleanup_start = cleanup_window.started_at
        stop_monitor.set()
        observer_task_joined = observer_task is None
        for task in (observer_task, process_monitor_task):
            try:
                joined = await _join_task(
                    task, timeout_s=max(0.0, cleanup_deadline - mono()),
                )
                if task is observer_task:
                    observer_task_joined = joined
                if not joined:
                    cleanup_errors.append('async_task_residue_unknown')
            except BaseException as error:
                if task is observer_task:
                    observer_task_joined = False
                cleanup_errors.append(
                    f'task_cleanup:{type(error).__name__}:{error}'
                )
        if observer is not None:
            if observer_task_joined:
                try:
                    observer.close(
                        deadline=cleanup_deadline, steady=mono,
                    )
                except BaseException as error:
                    cleanup_errors.append(
                        f'observer_close:{type(error).__name__}:{error}'
                    )
            else:
                cleanup_errors.append('observer_context_residue_unknown')
        all_records = (
            list(getattr(launcher, 'records', ())) if launcher else []
        )
        supervisor_records = (
            list(getattr(supervisor, 'owned', ()))
            if supervisor is not None else []
        )
        if supervisor is not None:
            try:
                remaining = max(0.0, cleanup_deadline - mono())
                cleanup_task = asyncio.create_task(supervisor.cleanup())
                done, _pending = await asyncio.wait(
                    {cleanup_task}, timeout=remaining,
                )
                if cleanup_task in done:
                    error = cleanup_task.exception()
                    if error is not None:
                        cleanup_errors.append(
                            'supervisor_cleanup:'
                            f'{type(error).__name__}:{error}'
                        )
                else:
                    cleanup_task.cancel()
                    cleanup_errors.append('supervisor_cleanup_timeout')
                    joined, _pending = await asyncio.wait(
                        {cleanup_task},
                        timeout=max(0.0, cleanup_deadline - mono()),
                    )
                    if joined:
                        await asyncio.gather(
                            cleanup_task, return_exceptions=True,
                        )
                    else:
                        cleanup_errors.append(
                            'supervisor_cleanup_task_residue_unknown'
                        )
            except BaseException as error:
                cleanup_errors.append(
                    f'supervisor_cleanup:{type(error).__name__}:{error}'
                )
        for record in supervisor_records:
            for task in getattr(record, 'output_tasks', ()):
                if task.cancelled():
                    continue
                if task.done() and task.exception() is not None:
                    cleanup_errors.append(
                        f'background_output_failure:{record.name}:'
                        f'{type(task.exception()).__name__}'
                    )
        if launcher is not None and all_records:
            try:
                await _fallback_cleanup(
                    launcher, all_records, sink, cleanup_errors,
                    deadline=cleanup_deadline, steady=mono,
                    sleep=deps.get('cleanup_sleep', asyncio.sleep),
                    escalation_grace=deps.get(
                        'cleanup_escalation_grace', (5.0, 3.0, 3.0),
                    ),
                )
            except BaseException as error:
                cleanup_errors.append(
                    f'fallback_cleanup:{type(error).__name__}:{error}'
                )
        if launcher is not None:
            for record in all_records:
                if record.identity_error:
                    cleanup_errors.append(
                        'identity_unknown:'
                        f'{record.name}:{record.identity_error}'
                    )
            for task in launcher.waiters.values():
                try:
                    if not await _join_task(
                        task, timeout_s=max(0.0, cleanup_deadline - mono()),
                    ):
                        cleanup_errors.append('process_waiter_residue_unknown')
                except BaseException as error:
                    cleanup_errors.append(
                        'process_waiter_cleanup:'
                        f'{type(error).__name__}:{error}'
                    )
        for key, previous in original_environment.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous
        try:
            runtime_dir_context.cleanup()
        except BaseException as error:
            cleanup_errors.append(
                f'runtime_dir_cleanup:{type(error).__name__}:{error}'
            )
        if mono() - cleanup_start > CLEANUP_CAP_S:
            cleanup_errors.append('cleanup_deadline_exceeded')
        if mono() > total_deadline:
            cleanup_errors.append('consume_to_end_deadline_exceeded')
        if mono() > cleanup_deadline:
            cleanup_errors.append('cleanup_deadline_exceeded')
        if cleanup_errors:
            final_status = 'FAIL'
        if sink is not None:
            try:
                sink.record('observation_verdict', {
                    'status': observation_verdict,
                    'failure_type': (
                        type(failure).__name__ if failure else None
                    ),
                })
                sink.record('final_status', {
                    'status': final_status,
                    'observation_status': observation_verdict,
                    'evidence_close_required_for_validity': True,
                    'failure_type': (
                        type(failure).__name__ if failure else None
                    ),
                    'cleanup_elapsed_s': mono() - cleanup_start,
                    'cleanup_errors': cleanup_errors,
                })
            except BaseException as error:
                final_status = 'FAIL'
                cleanup_errors.append(
                    f'final_evidence_write:{type(error).__name__}:{error}'
                )
                try:
                    sink.record('evidence_incomplete', {
                        'reason': cleanup_errors[-1],
                    })
                except BaseException:
                    pass
            try:
                sink.close()
            except BaseException as error:
                final_status = 'FAIL'
                cleanup_errors.append(
                    f'evidence_close:{type(error).__name__}:{error}'
                )
                try:
                    sink.record('evidence_incomplete', {
                        'reason': cleanup_errors[-1],
                    })
                except BaseException:
                    pass
    return final_status


async def _fallback_cleanup(
    launcher, records, sink, errors, *, deadline=None,
    steady=time.monotonic, sleep=asyncio.sleep,
    escalation_grace=(5.0, 3.0, 3.0),
):
    """Escalate captured process groups and retain ownership records."""
    unique = {id(record.process): record for record in records}
    owned = list(reversed(list(unique.values())))
    signals = (signal.SIGINT, signal.SIGTERM, signal.SIGKILL)
    if len(escalation_grace) != len(signals):
        raise ValueError('cleanup escalation grace must have three stages')
    if deadline is None:
        raise ValueError('cleanup requires the runner shared deadline')
    cleanup_deadline = deadline
    for sig, grace in zip(signals, escalation_grace):
        if steady() >= cleanup_deadline:
            break
        for record in owned:
            if steady() >= cleanup_deadline:
                break
            try:
                if launcher.group_alive(record.process):
                    await launcher.stop_group(record.process, sig)
            except BaseException as error:
                errors.append(
                    f'cleanup:{record.name}:{type(error).__name__}:{error}'
                )
        stage_deadline = min(cleanup_deadline, steady() + grace)
        while steady() < stage_deadline:
            live = []
            for record in owned:
                try:
                    if launcher.group_alive(record.process):
                        live.append(record)
                except BaseException as error:
                    errors.append(
                        'identity:'
                        f'{record.name}:{type(error).__name__}:{error}'
                    )
            if not live:
                break
            await sleep(min(0.05, max(0.0, stage_deadline - steady())))
        if not any(
            _safe_group_alive(launcher, record, errors) for record in owned
        ):
            break
        if steady() >= cleanup_deadline:
            break
    for record in owned:
        try:
            if launcher.group_alive(record.process):
                errors.append(f'residue:process_group:{record.pid}')
        except BaseException as error:
            errors.append(
                f'residue_unknown:{record.name}:{type(error).__name__}:{error}'
            )
        try:
            if sink is not None:
                sink.record('fallback_cleanup_attempt', {
                    'process': record.name, 'pid': record.pid,
                    'ownership_record_retained': True,
                })
        except BaseException as error:
            errors.append(f'cleanup_evidence:{type(error).__name__}')


def _safe_group_alive(launcher, record, errors):
    """Check ownership without skipping remaining groups on failure."""
    try:
        return launcher.group_alive(record.process)
    except BaseException as error:
        errors.append(
            f'residue_unknown:{record.name}:{type(error).__name__}:{error}'
        )
        return True


def verify_packet_commit(commit: str, packet_path: Path) -> None:
    """Require current HEAD and committed packet bytes to match approval."""
    root = Path(__file__).resolve().parents[5]
    head = subprocess.run(
        ['git', '-C', str(root), 'rev-parse', 'HEAD'],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if head != commit:
        raise GuardError('current HEAD differs from Owner-approved commit')
    relative = packet_path.resolve().relative_to(root.resolve())
    committed = subprocess.run(
        ['git', '-C', str(root), 'show', f'{commit}:{relative.as_posix()}'],
        check=True, capture_output=True,
    ).stdout
    if committed != packet_path.read_bytes():
        raise GuardError('working packet bytes differ from approved commit')


def parse_args(argv=None):
    """Parse command-line arguments with a strict GUI value parser."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--gui', type=strict_gui_value, required=True)
    parser.add_argument('--packet', default=str(PACKET_PATH))
    parser.add_argument('--approval-file', required=True)
    parser.add_argument('--approved-commit', required=True)
    parser.add_argument('--temp-root', default='/tmp')
    return parser.parse_args(argv)


def main(argv=None):
    """Execute the approved observation and return via process status."""
    args = parse_args(argv)
    try:
        status = asyncio.run(_run(args))
    except BaseException as error:
        raise SystemExit(f'B22_GUI_OBSERVATION_RUN001: {error}') from error
    if status != 'PASS':
        raise SystemExit(f'B22_GUI_OBSERVATION_RUN001: {status}')
    print(f'{RUN_ID}: PASS')


if __name__ == '__main__':
    main()
