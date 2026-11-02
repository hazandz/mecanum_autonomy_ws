"""Single-run, paused GUI observation orchestration for B2.2."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from collections import deque
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from observation_guard import (
    CONFIG_HASH, GUARD_PATH, GuardError, MANIFEST_SHA256,
    PRODUCTION_SOURCE_PIN, RESOLVED_SHA256, RUN_ID, SCENARIO_SHA256,
    acquire_once, sha256_file, validate_approval,
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
    """Validate fixed RUN001 identities and exact current tool hashes."""
    expected = {
        'run_id': RUN_ID,
        'capacity': 1,
        'gui': True,
        'scenario_id': 'B2_SOAK_V1',
        'world': 'b2_training_arena',
        'robot': 'mecanum_b2',
        'backend': 'NATIVE_B2_BACKEND_V1',
        'production_source_pin': PRODUCTION_SOURCE_PIN,
        'input_sha256': {
            'asset_manifest': MANIFEST_SHA256,
            'resolved_soak': RESOLVED_SHA256,
            'config_hash': CONFIG_HASH,
            'scenario': SCENARIO_SHA256,
        },
    }
    for key, value in expected.items():
        if packet.get(key) != value:
            raise GuardError(f'packet pin mismatch: {key}')
    if packet.get('tool_sha256') != file_hashes:
        raise GuardError('packet tool hashes are not final/current')


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

    def __init__(self, readiness):
        """Wrap audited readiness and retain the verified Owner screenshot."""
        self._readiness = readiness
        self.screenshot_path = None
        self.screenshot_sha256 = None
        self.owner_ack_cancelled = False

    def bind_environment(self, environment):
        """Bind the plan's partition and plugin/resource paths."""
        self._readiness.bind_environment(environment)

    async def server_scene(self, plan, process, timeout_s):
        """Delegate passive server and scene readiness checks."""
        await self._readiness.server_scene(plan, process, timeout_s)

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
        return True, str(path)


class TrackedProcessLauncher:
    """Use the audited launcher while checking its owned session identity."""

    def __init__(self, delegate, on_start=None):
        """Wrap the audited launcher with process-start identity tracking."""
        self.delegate = delegate
        self.on_start = on_start
        self.identities = {}
        self.records = []

    async def start(self, command, environment):
        """Start a process and record its PID/session identity immediately."""
        process = await self.delegate.start(command, environment)
        try:
            self.identities[id(process)] = process_start_identity(process.pid)
        except BaseException:
            import signal
            try:
                await self.delegate.stop_group(process, signal.SIGINT)
            finally:
                raise
        record = SimpleNamespace(
            name=_process_label(command), command=command,
            pid=process.pid, process=process,
        )
        self.records.append(record)
        if self.on_start is not None:
            try:
                self.on_start(record, self.identities[id(process)])
            except BaseException:
                import signal
                await self.stop_group(process, signal.SIGINT)
                raise
        return process

    def _members(self, process):
        identity = self.identities.get(id(process))
        if identity is None:
            raise ObservationFailure('owned process identity was not recorded')
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
        _identity, members = self._members(process)
        return bool(members)

    async def stop_group(self, process, sig):
        """Signal only members whose current proc identity remains owned."""
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
        class BoundSupervisor(base_type):
            async def cleanup(self):
                captured = list(self.owned)
                try:
                    await super().cleanup()
                except BaseException:
                    await _fallback_cleanup(
                        self.launcher, captured, self.evidence_sink, [],
                    )
                    raise
        return BoundSupervisor(**kwargs)


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

    def __init__(self):
        """Prepare an independent observer context without initializing ROS."""
        self.context = None
        self.node = None
        self.events = deque()
        self._rclpy = None

    def start(self):
        """Initialize a private context with status and clock subscribers."""
        import rclpy
        from rclpy.context import Context
        from rclpy.node import Node
        from mecanum_nav_rl_interfaces.msg import SimulationContactState
        from rosgraph_msgs.msg import Clock

        self._rclpy = rclpy
        self.context = Context()
        rclpy.init(context=self.context, domain_id=83)
        self.node = Node(
            'b22_gui_observation_observer', context=self.context,
        )
        self.node.create_subscription(
            SimulationContactState,
            '/mecanum/local_training/backend_state',
            lambda message: self.events.append(
                ('backend', message, time.monotonic()),
            ), 50,
        )
        self.node.create_subscription(
            Clock, '/clock',
            lambda message: self.events.append(
                ('clock', message.clock, time.monotonic()),
            ), 10,
        )

    def spin_once(self, timeout_s: float = 0.1):
        """Process passive observer callbacks for one bounded interval."""
        self._rclpy.spin_once(self.node, timeout_sec=timeout_s)

    def close(self):
        """Destroy the owned node and shut down only its ROS context."""
        if self.node is not None:
            self.node.destroy_node()
            self.node = None
        if self.context is not None and self._rclpy.ok(context=self.context):
            self._rclpy.shutdown(context=self.context)
        self.context = None


def evaluate_observation(
    *, plan, observer, duration_s: float = OBSERVATION_S,
    steady=time.monotonic, sleep=time.sleep, gui_exit=None,
):
    """Require an uninterrupted stable paused/inhibited 60-second window."""
    stable_start = None
    observation_start = None
    last_heartbeat = None
    clock_value = None
    clock_stable_since = None
    backend_identity = None
    seen_backend = False
    while True:
        now = steady()
        if gui_exit is not None and gui_exit.done():
            raise OwnerAbort('Owner closed GUI during observation')
        observer.spin_once(min(0.1, max(0.001, duration_s)))
        while observer.events:
            kind, message, received = observer.events.popleft()
            if kind == 'clock':
                stamp = (message.sec, message.nanosec)
                if clock_value is None:
                    clock_value = stamp
                    clock_stable_since = received
                elif stamp != clock_value:
                    raise ObservationFailure('simulation clock advanced')
                continue
            seen_backend = True
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
                last_heartbeat is not None
                and received - last_heartbeat > HEARTBEAT_GAP_S
            ):
                raise ObservationFailure('backend heartbeat gap exceeded 1 s')
            last_heartbeat = received
            if stable_start is None:
                stable_start = received
        now = steady()
        if (
            last_heartbeat is not None
            and now - last_heartbeat > HEARTBEAT_GAP_S
        ):
            raise ObservationFailure('backend heartbeat lost for over 1 s')
        if clock_stable_since is not None and now - clock_stable_since >= 1.0:
            if not seen_backend:
                raise ObservationFailure('no backend status received')
            if observation_start is None:
                observation_start = now
        if (
            observation_start is not None
            and now - observation_start >= duration_s
        ):
            return {
                'backend_identity': list(backend_identity),
                'heartbeat_last_steady': last_heartbeat,
                'clock_stamp': list(clock_value),
                'observed_seconds': now - observation_start,
            }
        sleep(0.01)


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
    assert_packet_inputs(packet, hashes)
    verify_commit = deps.get('verify_commit', verify_packet_commit)
    verify_commit(args.approved_commit, packet_path)
    install_preflight = deps.get('install_preflight')
    install_fingerprints = install_preflight() if install_preflight else None

    temp_parent = Path(args.temp_root)
    temp_parent.mkdir(parents=True, exist_ok=True)
    runtime_dir_context = tempfile.TemporaryDirectory(
        prefix='b22_gui_observation_run001_', dir=temp_parent,
    )
    runtime_dir = Path(runtime_dir_context.name)
    try:
        plan, paths, descriptor, descriptor_path = deps.get(
            'build_plan', build_runtime_plan,
        )(args.gui, runtime_dir)
    except BaseException:
        runtime_dir_context.cleanup()
        raise
    fingerprints = install_fingerprints or _fingerprint_install(paths)
    if fingerprints != packet.get('installed_sha256'):
        runtime_dir_context.cleanup()
        raise ObservationFailure(
            'installed file fingerprints differ from packet'
        )
    approved_packet_commit = args.approved_commit
    process_identity = process_start_identity(os.getpid())
    acquisition = {
        'schema_id': 'b22_gui_observation_acquisition/v1',
        'run_id': RUN_ID,
        'capacity': 1,
        'packet_sha256': packet_hash,
        'packet_commit': approved_packet_commit,
        'production_source_pin': PRODUCTION_SOURCE_PIN,
        'tool_sha256': hashes,
        'input_sha256': packet['input_sha256'],
        'installed_sha256': fingerprints,
        'dependency_fingerprints': packet['dependency_fingerprints'],
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
        'host': _host_identity(),
        'runner_process': process_identity,
        'steady_ns': time.monotonic_ns(),
        'utc_time': wall_utc(),
    }
    acquire = deps.get('acquire', acquire_once)
    guard_path = Path(args.guard_path)
    try:
        acquire(guard_path, acquisition)
    except BaseException:
        runtime_dir_context.cleanup()
        raise
    consumed_at = mono()
    sink = None
    supervisor = None
    launcher = None
    observer = None
    final_status = 'FAIL'
    cleanup_errors = []
    records_before_cleanup = []
    bound_environment = {'ROS_DOMAIN_ID': '83', **dict(plan.environment)}
    original_environment = {
        key: os.environ.get(key) for key in bound_environment
    }
    try:
        sink_factory = deps.get('sink_factory', ObservationEvidenceSink)
        sink = sink_factory(
            Path(args.evidence_root), RUN_ID, plan.session_id,
        )
        sink.record('guard_consumed', {
            'packet_sha256': packet_hash,
            'packet_commit': approved_packet_commit,
            'production_source_pin': PRODUCTION_SOURCE_PIN,
            'tool_sha256': hashes,
            'descriptor_path': str(descriptor_path),
            'descriptor_sha256': sha256_file(descriptor_path),
            'source_world_sha256': descriptor['world_source_sha256'],
            'runtime_bound_world_sha256': (
                descriptor['runtime_bound_world_sha256']
            ),
            'install_fingerprints': fingerprints,
            'dependency_fingerprints': packet['dependency_fingerprints'],
        })
        evidence_assets = Path(args.evidence_root) / 'runtime_assets'
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
        os.environ.update(bound_environment)
        from mecanum_nav_bringup.local_training_process_supervisor import (
            LocalTrainingProcessSupervisor, ProcessRecord,
            RclpyReadiness, SubprocessProcessLauncher,
        )
        launcher = deps.get('launcher')
        if launcher is None:
            launcher = TrackedProcessLauncher(
                SubprocessProcessLauncher(),
                on_start=lambda record, identity: sink.record(
                    'owned_process_identity', {
                        'process': record.name,
                        'command': list(record.command),
                        'pid': record.pid, 'process_identity': identity,
                    },
                ),
            )
        readiness = ScreenshotReadiness(
            deps.get('readiness', RclpyReadiness())
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
            )
        # The installed robot_state_publisher shares this lifecycle.
        ros2 = shutil.which('ros2')
        if not ros2:
            raise ObservationFailure('installed ros2 executable is missing')
        rsp_command = (
            ros2, 'run', 'robot_state_publisher', 'robot_state_publisher',
            '--ros-args', '--params-file', str(persisted_params),
        )
        rsp = await launcher.start(rsp_command, dict(plan.environment))
        rsp_record = ProcessRecord(
            'robot_state_publisher', rsp_command, rsp.pid, rsp,
        )
        supervisor.owned.append(rsp_record)
        start_identity = getattr(launcher, 'identities', {}).get(
            id(rsp), process_start_identity(rsp.pid),
        )
        sink.record('owned_process_started', {
            'process': rsp_record.name, 'command': list(rsp_command),
            'pid': rsp.pid, 'process_identity': start_identity,
        })
        await asyncio.wait_for(
            supervisor.start(),
            timeout=SERVER_READY_S + GUI_START_S + OWNER_ACK_S,
        )
        for record in supervisor.owned:
            identity = getattr(
                launcher, 'identities', {},
            ).get(id(record.process))
            sink.record('owned_process_identity', {
                'process': record.name, 'pid': record.pid,
                'process_identity': identity,
            })
        if mono() - consumed_at > RUNTIME_CAP_S:
            raise ObservationFailure(
                '240 s runtime cap exceeded before observation'
            )
        screenshot = readiness.screenshot_path
        if screenshot is None or readiness.screenshot_sha256 is None:
            raise ObservationFailure('Owner screenshot was not verified')
        sink.record('owner_scene_acknowledged', {
            'screenshot_path': str(screenshot),
            'screenshot_sha256': readiness.screenshot_sha256,
            'confirmation_source': 'direct_owner_tty',
        })
        observer_factory = deps.get('observer_factory', PassiveBackendObserver)
        observer = observer_factory()
        observer.start()
        gui_record = next(
            record for record in supervisor.owned if record.name == 'gui'
        )
        gui_exit = asyncio.create_task(gui_record.process.wait())
        sink.record('observation_started', {'duration_s': OBSERVATION_S})
        observe = deps.get('evaluate_observation', evaluate_observation)
        verdict = await asyncio.wait_for(asyncio.to_thread(
            observe, plan=plan, observer=observer,
            duration_s=deps.get('observation_duration', OBSERVATION_S),
            steady=mono, gui_exit=gui_exit,
        ), timeout=deps.get('observation_duration', OBSERVATION_S) + 15.0)
        if mono() - consumed_at > RUNTIME_CAP_S:
            raise ObservationFailure('240 s runtime cap exceeded')
        final_status = 'PASS'
        sink.record('observation_result', verdict)
    except asyncio.CancelledError:
        final_status = 'ABORTED_BY_OWNER'
        raise
    except BaseException as error:
        if isinstance(error, OwnerAbort):
            final_status = 'ABORTED_BY_OWNER'
        elif (
            'readiness' in locals()
            and readiness.owner_ack_cancelled
            and sink is not None
            and 'gui_closed_or_crashed' in getattr(sink, 'events', [])
        ):
            final_status = 'ABORTED_BY_OWNER'
        try:
            if sink is not None:
                sink.record('observation_failure', {
                    'error_type': type(error).__name__,
                    'error': str(error)[:1000],
                })
        except BaseException as sink_error:
            cleanup_errors.append(
                f'evidence_failure:{type(sink_error).__name__}'
            )
        if isinstance(error, ObservationFailure):
            final_status = 'FAIL'
        if final_status != 'ABORTED_BY_OWNER':
            raise
    finally:
        cleanup_start = mono()
        cleanup_deadline = time.monotonic() + CLEANUP_CAP_S
        if observer is not None:
            try:
                observer.close()
            except BaseException as error:
                cleanup_errors.append(
                    f'observer_close:{type(error).__name__}:{error}'
                )
        if supervisor is not None:
            records_before_cleanup = list(supervisor.owned)
            try:
                await asyncio.wait_for(
                    supervisor.cleanup(),
                    timeout=max(0.001, cleanup_deadline - time.monotonic()),
                )
            except BaseException as error:
                cleanup_errors.append(
                    f'supervisor_cleanup:{type(error).__name__}:{error}'
                )
                await _fallback_cleanup(
                    launcher, records_before_cleanup, sink, cleanup_errors,
                    deadline=cleanup_deadline,
                )
        tracked_records = getattr(launcher, 'records', []) if launcher else []
        if tracked_records:
            await _fallback_cleanup(
                launcher, tracked_records, sink, cleanup_errors,
                deadline=cleanup_deadline,
            )
        for key, previous in original_environment.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous
        cleanup_elapsed = mono() - cleanup_start
        if cleanup_elapsed > CLEANUP_CAP_S:
            cleanup_errors.append('cleanup_deadline_exceeded')
        if mono() - consumed_at > TOTAL_CAP_S:
            cleanup_errors.append('consume_to_end_deadline_exceeded')
        if sink is not None:
            try:
                final_status = classify_final_status(
                    final_status == 'PASS',
                    final_status == 'ABORTED_BY_OWNER', cleanup_errors,
                )
                sink.record('final_status', {
                    'status': final_status,
                    'cleanup_elapsed_s': cleanup_elapsed,
                    'cleanup_errors': cleanup_errors,
                })
            except BaseException:
                final_status = 'FAIL'
            try:
                sink.close()
            except BaseException:
                final_status = 'FAIL'
        runtime_dir_context.cleanup()
    return final_status


async def _fallback_cleanup(launcher, records, sink, errors, *, deadline=None):
    """Try captured groups despite supervisor cleanup or logging failures."""
    import signal
    deadline = (
        deadline
        if deadline is not None
        else time.monotonic() + CLEANUP_CAP_S
    )
    unique = {id(record.process): record for record in records}
    owned = list(reversed(list(unique.values())))
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
        for record in owned:
            try:
                if launcher.group_alive(record.process):
                    await launcher.stop_group(record.process, sig)
            except BaseException as error:
                errors.append(
                    f'cleanup:{record.name}:{type(error).__name__}:{error}'
                )
        stage_deadline = min(deadline, time.monotonic() + 0.75)
        while time.monotonic() < stage_deadline:
            live = []
            for record in owned:
                try:
                    if launcher.group_alive(record.process):
                        live.append(record)
                except BaseException as error:
                    errors.append(
                        f'identity:{record.name}:'
                        f'{type(error).__name__}:{error}'
                    )
            if not live:
                break
            await asyncio.sleep(min(0.05, stage_deadline - time.monotonic()))
        if time.monotonic() >= deadline:
            break
    for record in owned:
        try:
            if launcher.group_alive(record.process):
                errors.append(f'residue:process_group:{record.pid}')
        except BaseException as error:
            errors.append(
                f'residue_unknown:{record.name}:{type(error).__name__}'
            )
        try:
            if sink is not None:
                sink.record('fallback_cleanup_attempt', {
                    'process': record.name, 'pid': record.pid,
                })
        except BaseException as error:
            errors.append(f'cleanup_evidence:{type(error).__name__}')


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
    parser.add_argument('--guard-path', default=str(GUARD_PATH))
    parser.add_argument(
        '--evidence-root',
        default=(
            '/home/hazan/mecanum_runtime_evidence/'
            'B22_GUI_OBSERVATION_RUN001'
        ),
    )
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
