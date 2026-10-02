#!/usr/bin/env python3
"""Typed-Scene supervisor primitives; runtime execution remains unavailable.

The supervisor-owned create phase is injection-only for offline tests. It has no
subprocess implementation and cannot launch Gazebo, ROS, create, or the helper.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import shlex
import signal
import stat
import subprocess
import tempfile
import time
import uuid
from datetime import UTC, datetime
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Protocol

import typed_scene_final_run_guard as approval_guard

CREATE_EXECUTABLE = Path('/opt/ros/jazzy/lib/ros_gz_sim/create')
ROS2_EXECUTABLE = Path('/opt/ros/jazzy/bin/ros2')
CXX_EXECUTABLE = Path('/usr/bin/g++')
PKG_CONFIG_EXECUTABLE = Path('/usr/bin/pkg-config')
DEDICATED_LAUNCH_ARGUMENTS = ('launch', 'ROBOT_URDF_final_description', 'native_sdf_contact_diagnostic.launch.py')
HELPER_SOURCE_RELATIVE = Path('artifacts/simulation/contact_producer_evidence/tools/typed_scene_observer.cpp')
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
MEASUREMENT_SHUTDOWN_GRACE_MS = 5000
CREATE_TIMEOUT_MS = 90000
POST_CREATE_DELAY_MS = 2000
CREATE_SHUTDOWN_GRACE_MS = 5000
OWNERSHIP_MODE = 'SUPERVISOR_OWNED_CREATE_V1'


class PrepareFailure(RuntimeError):
    """Typed, fail-closed failure before trusted-context acquisition."""

    def __init__(self, status: str):
        super().__init__(status)
        self.status = status
def native_create_arguments(workspace_root: Path) -> tuple[str, ...]:
    """Derive the allowlisted native-SDF create argv from trusted route data."""
    return tuple(approval_guard.native_create_argv(workspace_root))


CREATE_ARGUMENTS = native_create_arguments(WORKSPACE_ROOT)


@dataclass(frozen=True)
class RunIdentity:
    """One immutable future-run identity shared by every durable receipt."""

    run_id: str


@dataclass(frozen=True)
class PreparedHelper:
    """Immutable compile receipt retained only in a temporary directory."""

    temporary_directory: object
    binary_path: Path
    binary_sha256: str
    source_sha256: str
    compiler_path: str
    pkg_config_path: str
    compiler_argv: tuple[str, ...]


def new_run_identity() -> RunIdentity:
    """Create the opaque ID before any future runtime callback or subprocess."""
    return RunIdentity(f'run-typed-scene-{uuid.uuid4().hex}')


def atomic_write_json_new(path: Path, value: dict) -> None:
    """Write one evidence JSON file without replacing committed evidence."""
    if path.exists() or path.is_symlink() or path.parent.is_symlink():
        raise RuntimeError('evidence target already exists or is a symlink')
    temporary = path.with_name(f'.{path.name}.{uuid.uuid4().hex}.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        # link(2) is an atomic no-overwrite commit on this same filesystem.
        os.link(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        temporary.unlink()
    except BaseException:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


class CreateProcess(Protocol):
    pid: int

    def wait(self, timeout_ms: int) -> int | None: ...

    def send_sigint_group(self) -> None: ...


class RuntimeCreateProcess:
    """Adapter around one supervisor-owned create child process group."""

    def __init__(self, process, process_group_id: int, kill_process_group):
        self._process = process
        self._process_group_id = process_group_id
        self._kill_process_group = kill_process_group
        self.pid = process.pid

    def wait(self, timeout_ms: int) -> int | None:
        try:
            return self._process.wait(timeout=timeout_ms / 1000.0)
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError('create child wait timeout') from exc

    def send_sigint_group(self) -> None:
        self._kill_process_group(self._process_group_id, signal.SIGINT)


class RuntimeCreateAdapter:
    """Future-only Popen adapter; no CLI path invokes this class today."""

    def __init__(
        self,
        expected_argv: tuple[str, ...] = CREATE_ARGUMENTS,
        popen_factory=subprocess.Popen,
        get_process_group=os.getpgid,
        kill_process_group=os.killpg,
    ):
        self._expected_argv = expected_argv
        self._popen_factory = popen_factory
        self._get_process_group = get_process_group
        self._kill_process_group = kill_process_group

    def spawn(self, executable: str, argv: tuple[str, ...]) -> CreateProcess:
        if executable != str(CREATE_EXECUTABLE) or argv != self._expected_argv:
            raise ValueError('runtime create adapter received non-allowlisted command')
        process = self._popen_factory(
            [executable, *argv],
            shell=False,
            start_new_session=True,
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if not isinstance(process.pid, int) or isinstance(process.pid, bool) or process.pid <= 0:
            raise RuntimeError('create child PID unavailable')
        process_group_id = self._get_process_group(process.pid)
        if process_group_id != process.pid:
            raise RuntimeError('create child session/process group ownership unconfirmed')
        return RuntimeCreateProcess(process, process_group_id, self._kill_process_group)


@dataclass(frozen=True)
class CreatePlan:
    executable_path: str
    executable_sha256: str
    argv: tuple[str, ...]
    timeout_ms: int
    post_create_delay_ms: int
    shutdown_grace_ms: int
    ownership_mode: str


@dataclass(frozen=True)
class CreatePhaseResult:
    status: str
    bootstrap_status: str
    helper_permitted: bool
    create_invocations: int
    executable_path: str | None
    executable_sha256: str | None
    argv: tuple[str, ...]
    pid: int | None
    start_steady_ns: int | None
    end_steady_ns: int | None
    exit_code: int | None
    reason: str
    shutdown_signal_sent: bool = False
    shutdown_grace_ms: int | None = None
    shutdown_complete: bool | None = None


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def regular_file(path: Path) -> bool:
    """True only for a non-symlink regular file at the exact path."""
    try:
        return stat.S_ISREG(path.stat(follow_symlinks=False).st_mode)
    except OSError:
        return False


def valid_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        char in '0123456789abcdef' for char in value
    )


def unconfirmed(reason: str) -> CreatePhaseResult:
    return CreatePhaseResult(
        'SCENE_CREATE_OUTCOME_UNCONFIRMED',
        'SCENE_BOOTSTRAP_UNCONFIRMED',
        False,
        0,
        None,
        None,
        (),
        None,
        None,
        None,
        None,
        reason,
    )


def resolve_create_plan(
    workspace_root: Path = WORKSPACE_ROOT,
    executable: Path = CREATE_EXECUTABLE,
    digest_path: Callable[[Path], str] = digest,
    is_regular_file: Callable[[Path], bool] = regular_file,
) -> CreatePlan:
    """Create an immutable plan after resolving the exact allowlisted binary."""
    if executable != CREATE_EXECUTABLE or not is_regular_file(executable):
        raise ValueError('create executable is not allowlisted regular file')
    executable_sha256 = digest_path(executable)
    if not valid_sha256(executable_sha256):
        raise ValueError('create executable SHA-256 is invalid')
    return CreatePlan(
        executable_path=str(executable),
        executable_sha256=executable_sha256,
        argv=native_create_arguments(workspace_root),
        timeout_ms=CREATE_TIMEOUT_MS,
        post_create_delay_ms=POST_CREATE_DELAY_MS,
        shutdown_grace_ms=CREATE_SHUTDOWN_GRACE_MS,
        ownership_mode=OWNERSHIP_MODE,
    )


def create_phase(
    plan: CreatePlan,
    spawn: Callable[[str, tuple[str, ...]], CreateProcess],
    steady_ns: Callable[[], int] = time.monotonic_ns,
    delay_ms: Callable[[int], None] = lambda milliseconds: None,
    digest_path: Callable[[Path], str] = digest,
    is_regular_file: Callable[[Path], bool] = regular_file,
    workspace_root: Path = WORKSPACE_ROOT,
) -> CreatePhaseResult:
    """Run one injected create phase; caller must already own a future guard.

    Integrity is checked immediately before injected spawn. This function makes
    no helper or RequestRaw call; the only future runtime adapter is separately
    injectable and unreachable from the fail-closed CLI.
    """
    if (
        plan.ownership_mode != OWNERSHIP_MODE
        or plan.timeout_ms != CREATE_TIMEOUT_MS
        or plan.post_create_delay_ms != POST_CREATE_DELAY_MS
        or plan.shutdown_grace_ms != CREATE_SHUTDOWN_GRACE_MS
    ):
        return unconfirmed('create plan literals mismatch')
    if plan.executable_path != str(CREATE_EXECUTABLE) or plan.argv != native_create_arguments(workspace_root):
        return unconfirmed('create executable or argv not allowlisted')
    if not valid_sha256(plan.executable_sha256):
        return unconfirmed('create plan SHA-256 format invalid')
    if not is_regular_file(CREATE_EXECUTABLE):
        return unconfirmed('create executable missing or not a regular file')
    try:
        observed_sha256 = digest_path(CREATE_EXECUTABLE)
    except (OSError, RuntimeError, ValueError) as exc:
        return unconfirmed(f'create executable integrity read failed: {type(exc).__name__}')
    if not valid_sha256(observed_sha256):
        return unconfirmed('create executable SHA-256 format invalid at spawn')
    if observed_sha256 != plan.executable_sha256:
        return unconfirmed('create executable SHA-256 mismatch at spawn')

    start = steady_ns()
    try:
        process = spawn(plan.executable_path, plan.argv)
    except (OSError, RuntimeError) as exc:
        return CreatePhaseResult(
            'SCENE_CREATE_OUTCOME_UNCONFIRMED', 'SCENE_BOOTSTRAP_UNCONFIRMED',
            False, 1, plan.executable_path, plan.executable_sha256, plan.argv,
            None, start, steady_ns(), None, f'create start failed: {type(exc).__name__}',
        )
    try:
        exit_code = process.wait(plan.timeout_ms)
    except TimeoutError:
        return timeout_shutdown_phase(process, plan, start, steady_ns)
    except InterruptedError:
        return CreatePhaseResult(
            'SCENE_CREATE_OUTCOME_UNCONFIRMED', 'SCENE_BOOTSTRAP_UNCONFIRMED',
            False, 1, plan.executable_path, plan.executable_sha256, plan.argv,
            process.pid, start, steady_ns(), None, 'create interrupted',
        )
    end = steady_ns()
    if not isinstance(exit_code, int) or isinstance(exit_code, bool):
        return CreatePhaseResult(
            'SCENE_CREATE_OUTCOME_UNCONFIRMED', 'SCENE_BOOTSTRAP_UNCONFIRMED',
            False, 1, plan.executable_path, plan.executable_sha256, plan.argv,
            process.pid, start, end, None, 'create exit code missing',
        )
    if exit_code != 0:
        return CreatePhaseResult(
            'SCENE_CREATE_OUTCOME_UNCONFIRMED', 'SCENE_BOOTSTRAP_UNCONFIRMED',
            False, 1, plan.executable_path, plan.executable_sha256, plan.argv,
            process.pid, start, end, exit_code, 'create exit convention nonzero',
        )
    try:
        delay_ms(plan.post_create_delay_ms)
    except (OSError, RuntimeError, InterruptedError) as exc:
        return CreatePhaseResult(
            'SCENE_BOOTSTRAP_UNCONFIRMED', 'SCENE_BOOTSTRAP_UNCONFIRMED', False,
            1, plan.executable_path, plan.executable_sha256, plan.argv,
            process.pid, start, end, exit_code,
            f'post-create delay failed: {type(exc).__name__}',
        )
    return CreatePhaseResult(
        'SCENE_BOOTSTRAP_READY_FOR_ONE_REQUEST',
        'SCENE_BOOTSTRAP_READY_FOR_ONE_REQUEST',
        True,
        1,
        plan.executable_path,
        plan.executable_sha256,
        plan.argv,
        process.pid,
        start,
        end,
        exit_code,
        'exit 0 operational convention plus fixed delay',
    )



def timeout_shutdown_phase(
    process: CreateProcess,
    plan: CreatePlan,
    start_steady_ns: int,
    steady_ns: Callable[[], int],
) -> CreatePhaseResult:
    """Offline-testable future timeout cleanup contract; sends SIGINT only."""
    try:
        process.send_sigint_group()
    except (OSError, RuntimeError, InterruptedError) as exc:
        return CreatePhaseResult(
            'SHUTDOWN_INCOMPLETE', 'SCENE_BOOTSTRAP_UNCONFIRMED', False, 1,
            plan.executable_path, plan.executable_sha256, plan.argv, process.pid,
            start_steady_ns, steady_ns(), None,
            f'create timeout; SIGINT group delivery failed: {type(exc).__name__}',
            shutdown_signal_sent=False,
            shutdown_grace_ms=plan.shutdown_grace_ms,
            shutdown_complete=False,
        )
    try:
        exit_code = process.wait(plan.shutdown_grace_ms)
    except (TimeoutError, InterruptedError) as exc:
        return CreatePhaseResult(
            'SHUTDOWN_INCOMPLETE', 'SCENE_BOOTSTRAP_UNCONFIRMED', False, 1,
            plan.executable_path, plan.executable_sha256, plan.argv, process.pid,
            start_steady_ns, steady_ns(), None,
            f'create timeout; child did not exit during SIGINT grace: {type(exc).__name__}',
            shutdown_signal_sent=True,
            shutdown_grace_ms=plan.shutdown_grace_ms,
            shutdown_complete=False,
        )
    end_steady_ns = steady_ns()
    if not isinstance(exit_code, int) or isinstance(exit_code, bool):
        return CreatePhaseResult(
            'SHUTDOWN_INCOMPLETE', 'SCENE_BOOTSTRAP_UNCONFIRMED', False, 1,
            plan.executable_path, plan.executable_sha256, plan.argv, process.pid,
            start_steady_ns, end_steady_ns, None,
            'create timeout; child exit code unavailable after SIGINT grace',
            shutdown_signal_sent=True,
            shutdown_grace_ms=plan.shutdown_grace_ms,
            shutdown_complete=False,
        )
    return CreatePhaseResult(
        'SCENE_CREATE_OUTCOME_UNCONFIRMED', 'SCENE_BOOTSTRAP_UNCONFIRMED',
        False, 1, plan.executable_path, plan.executable_sha256, plan.argv,
        process.pid, start_steady_ns, end_steady_ns, exit_code,
        'create timeout; child exited during SIGINT grace',
        shutdown_signal_sent=True,
        shutdown_grace_ms=plan.shutdown_grace_ms,
        shutdown_complete=True,
    )


@dataclass(frozen=True)
class GuardedExecutionDependencies:
    """Injected operations only; tests supply fakes and the CLI supplies none."""
    launch_bootstrap: Callable[[], None]
    spawn_create: Callable[[str, tuple[str, ...]], CreateProcess]
    compile_helper: Callable[[Path], None]
    helper_once: Callable[[Path], str]
    persist_artifact: Callable[[Path, str], None]
    shutdown_sigint_only: Callable[[], bool]
    temporary_directory: Callable[[], object]
    now_utc: Callable[[], str]
    run_id: Callable[[], str]
    prepare: Callable[[], PreparedHelper | None] | None = None
    begin_run: Callable[[str], None] | None = None
    finalize_evidence: Callable[[str, CreatePhaseResult | None, bool, bool], None] | None = None
    cleanup_prepared: Callable[[], None] | None = None


def helper_runtime_argv(binary: Path, run_id: str, output_dir: Path) -> list[str]:
    """Build the sole future helper invocation without accepting caller literals."""
    if (not isinstance(run_id, str) or not run_id.startswith('run-typed-scene-')
            or any(character not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for character in run_id)):
        raise RuntimeError('invalid shared run identity')
    if not output_dir.is_absolute() or output_dir.is_symlink():
        raise RuntimeError('durable helper output directory invalid')
    return [str(binary), '--runtime-once', '--run-id', run_id,
            '--preflight-wait-ms', '90000', '--request-timeout-ms', '5000',
            '--polling-ms', '10', '--output-dir', str(output_dir)]


class RuntimeDependencyFactory:
    """Deferred real-runtime callback factory; construction performs no I/O.

    It is intentionally not called by the current S3.3.47 CLI gate. Every
    callback is suitable only after a future approval binds a new packet/guard.
    """

    def __init__(self, workspace_root: Path, popen_factory=subprocess.Popen,
                 clock=time.monotonic, process_group=os.killpg,
                 run_factory=subprocess.run, environ=None,
                 create_arguments: tuple[str, ...] | None = None):
        self._root = workspace_root
        self._popen_factory = popen_factory
        self._clock = clock
        self._process_group = process_group
        self._run_factory = run_factory
        self._base_environ = dict(os.environ if environ is None else environ)
        self._launch_process = None
        self._helper_process = None
        self._run_directory: Path | None = None
        self._active_run_id: str | None = None
        self._prepared_helper: PreparedHelper | None = None
        self._prepared_context = None
        self._helper_sha256: str | None = None
        # The optional injection exists only for offline tests with a synthetic
        # workspace. Production construction derives the native argv from the
        # supplied workspace and never accepts it from a CLI caller.
        if create_arguments is not None and create_arguments != CREATE_ARGUMENTS:
            raise ValueError('test create argv injection is not the locked native contract')
        self._create_arguments = (
            native_create_arguments(workspace_root)
            if create_arguments is None else create_arguments
        )

    def begin_run(self, run_id: str) -> None:
        if not isinstance(run_id, str) or not run_id.startswith('run-typed-scene-') or '/' in run_id:
            raise RuntimeError('invalid shared run identity')
        if self._run_directory is not None or self._active_run_id is not None:
            raise RuntimeError('second run identity prohibited')
        directory = self._root / 'artifacts/simulation/contact_producer_evidence' / run_id
        if directory.exists() or directory.is_symlink() or directory.parent.is_symlink():
            raise RuntimeError('durable run directory collision or symlink')
        directory.mkdir(mode=0o700, parents=True)
        self._active_run_id = run_id
        self._run_directory = directory
        atomic_write_json_new(directory / 'run_manifest.json', {
            'run_id': run_id,
            'schema_version': 's3_d3_typed_scene_durable_evidence/v1',
            'create_argv': list(self._create_arguments),
            'launch_argv': [str(ROS2_EXECUTABLE), *DEDICATED_LAUNCH_ARGUMENTS],
            'shutdown_policy': 'SUPERVISOR_SIGINT_ONLY_LAUNCHER_ESCALATION_POSSIBLE',
        })

    def _ensure_artifact_directory(self) -> Path:
        if self._run_directory is None or self._active_run_id is None:
            raise RuntimeError('durable run identity required before callback')
        if self._run_directory.is_symlink() or not self._run_directory.is_dir():
            raise RuntimeError('durable run directory invalid')
        return self._run_directory

    @staticmethod
    def _require_allowlisted_regular(path: Path, expected: Path) -> None:
        if path != expected:
            raise RuntimeError('allowlisted executable/source unavailable')
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise RuntimeError('allowlisted executable/source unavailable') from exc
        if not resolved.is_file():
            raise RuntimeError('allowlisted executable/source unavailable')

    def launch_bootstrap(self) -> None:
        self._require_allowlisted_regular(ROS2_EXECUTABLE, ROS2_EXECUTABLE)
        if self._launch_process is not None:
            raise RuntimeError('second bootstrap launch prohibited')
        directory = self._ensure_artifact_directory()
        with (directory / 'bootstrap_launch_stdout.log').open('xb') as stdout, \
             (directory / 'bootstrap_launch_stderr.log').open('xb') as stderr:
            self._launch_process = self._popen_factory(
                [str(ROS2_EXECUTABLE), *DEDICATED_LAUNCH_ARGUMENTS],
                shell=False, start_new_session=True, close_fds=True,
                stdout=stdout, stderr=stderr,
            )
        if self._launch_process.pid <= 0:
            raise RuntimeError('bootstrap launch process identity unavailable')

    def _wait_or_sigint(self, process, timeout_ms: int) -> int:
        try:
            return process.wait(timeout=timeout_ms / 1000.0)
        except subprocess.TimeoutExpired:
            self._process_group(process.pid, signal.SIGINT)
            try:
                process.wait(timeout=MEASUREMENT_SHUTDOWN_GRACE_MS / 1000.0)
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError('SHUTDOWN_INCOMPLETE') from exc
            raise RuntimeError('runtime callback timeout')

    def _pkg_config_environment(self) -> dict[str, str]:
        try:
            directories, versions = approval_guard.pkg_config_identity()
        except approval_guard.TrustedContextError as exc:
            raise PrepareFailure('INVALID_PREPARE_PKG_CONFIG_ENV') from exc
        if tuple(directories) != approval_guard.PKG_CONFIG_DIRECTORIES:
            raise PrepareFailure('INVALID_PREPARE_PKG_CONFIG_ENV')
        if any(versions.get(name) != expected for name, expected in approval_guard.PKG_CONFIG_RUNTIME_VERSIONS.items()):
            raise PrepareFailure('INVALID_PREPARE_PKG_CONFIG_ENV')
        environment = dict(self._base_environ)
        environment['PKG_CONFIG_PATH'] = os.pathsep.join(directories)
        completed = self._run_factory(
            [str(PKG_CONFIG_EXECUTABLE), '--modversion', 'gz-transport13', 'gz-msgs10'],
            shell=False, check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            start_new_session=True, close_fds=True, env=environment,
        )
        try:
            values = completed.stdout.decode('utf-8', 'strict').splitlines()
        except (AttributeError, UnicodeDecodeError) as exc:
            raise PrepareFailure('INVALID_PREPARE_PKG_CONFIG_ENV') from exc
        if completed.returncode != 0 or values != ['13.5.0', '10.3.2']:
            raise PrepareFailure('INVALID_PREPARE_PKG_CONFIG_ENV')
        return environment

    def _pkg_config_flags(self, packages: tuple[str, ...], environment: dict[str, str]) -> bytes:
        completed = self._run_factory(
            [str(PKG_CONFIG_EXECUTABLE), '--cflags', '--libs', *packages],
            shell=False, check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            start_new_session=True, close_fds=True, env=environment,
        )
        if completed.returncode != 0 or not isinstance(completed.stdout, bytes):
            raise PrepareFailure('INVALID_PREPARE_PKG_CONFIG_ENV')
        try:
            completed.stdout.decode('utf-8', 'strict')
        except UnicodeDecodeError as exc:
            raise PrepareFailure('INVALID_PREPARE_PKG_CONFIG_ENV') from exc
        return completed.stdout

    def compile_helper(self, directory: Path) -> PreparedHelper:
        self._require_allowlisted_regular(CXX_EXECUTABLE, CXX_EXECUTABLE)
        self._require_allowlisted_regular(PKG_CONFIG_EXECUTABLE, PKG_CONFIG_EXECUTABLE)
        source = self._root / HELPER_SOURCE_RELATIVE
        binary = directory / 'typed_scene_observer'
        if not regular_file(source) or directory.is_symlink() or not directory.is_dir():
            raise PrepareFailure('INVALID_PREPARE')
        environment = self._pkg_config_environment()
        flags = self._pkg_config_flags(('gz-transport13', 'gz-msgs10'), environment)
        openssl = self._pkg_config_flags(('openssl',), environment)
        try:
            argv = [str(CXX_EXECUTABLE), '-std=c++17', '-Wall', '-Wextra', '-Werror', str(source), '-o', str(binary), *shlex.split(flags.decode('utf-8', 'strict')), *shlex.split(openssl.decode('utf-8', 'strict'))]
            completed = self._run_factory(argv, shell=False, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True, env=environment)
        except (OSError, ValueError) as exc:
            raise PrepareFailure('INVALID_PREPARE_COMPILE') from exc
        if completed.returncode != 0 or not regular_file(binary) or not valid_sha256(digest(binary)):
            raise PrepareFailure('INVALID_PREPARE_COMPILE')
        return PreparedHelper(
            self._prepared_context, binary, digest(binary), digest(source), str(CXX_EXECUTABLE),
            environment['PKG_CONFIG_PATH'], tuple(argv),
        )

    def helper_once(self, directory: Path) -> str:
        binary = directory / 'typed_scene_observer'
        artifact = self._ensure_artifact_directory()
        prepared = self._prepared_helper
        if (prepared is None or self._helper_sha256 is None
                or prepared.binary_path != binary
                or prepared.binary_sha256 != self._helper_sha256
                or not regular_file(binary) or digest(binary) != self._helper_sha256):
            raise RuntimeError('typed Scene helper binary invalid')
        argv = helper_runtime_argv(binary, self._active_run_id, artifact)
        started = time.monotonic_ns()
        completed = subprocess.run(argv, shell=False, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True)
        ended = time.monotonic_ns()
        summary = artifact / 'scene_summary.json'; metadata = artifact / 'request_metadata.json'
        if completed.returncode != 0 or not regular_file(summary) or not regular_file(metadata):
            raise RuntimeError('INVALID_EVIDENCE_PERSISTENCE_FAILURE')
        try:
            value = json.loads(summary.read_text(encoding='utf-8'))
            meta = json.loads(metadata.read_text(encoding='utf-8'))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError('INVALID_EVIDENCE_PERSISTENCE_FAILURE') from exc
        allowed = {'SCENE_SERVICE_UNAVAILABLE','SCENE_REQUEST_INCOMPLETE','SCENE_RESPONSE_UNDECODABLE','SCENE_MODEL_NOT_OBSERVED_AFTER_DELAY','SCENE_LINK_NOT_OBSERVED_AFTER_DELAY','SCENE_SENSOR_NOT_OBSERVED_AFTER_DELAY','SCENE_SENSOR_PRESENT_IDENTITY_ONLY'}
        status = value.get('status'); called = value.get('request_raw_called'); sha = value.get('raw_response_sha256')
        required_summary = {'status', 'reason', 'request_raw_called', 'raw_response_sha256', 'run_id', 'preflight_start_steady_ns', 'preflight_end_steady_ns', 'request_start_steady_ns', 'request_end_steady_ns', 'schema_version'}
        required_metadata = {'scene_status', 'detail', 'request_raw_called', 'run_id', 'preflight_start_steady_ns', 'preflight_end_steady_ns', 'request_start_steady_ns', 'request_end_steady_ns', 'outer_status', 'service', 'schema_version'}
        def valid_timestamp(candidate):
            return candidate is None or (isinstance(candidate, int) and not isinstance(candidate, bool) and candidate >= 0)
        timestamps = ('preflight_start_steady_ns', 'preflight_end_steady_ns', 'request_start_steady_ns', 'request_end_steady_ns')
        if (not required_summary.issubset(value) or not required_metadata.issubset(meta)
                or not isinstance(value.get('reason'), str) or not isinstance(meta.get('detail'), str)
                or not isinstance(called, bool) or meta.get('request_raw_called') is not called
                or any(not valid_timestamp(value[key]) or not valid_timestamp(meta[key]) for key in timestamps)
                or any(value[key] != meta[key] for key in timestamps)
                or value.get('run_id') != self._active_run_id or meta.get('run_id') != self._active_run_id
                or status not in allowed or meta.get('scene_status') not in (None, status)
                or value.get('schema_version') != 's3_d3_typed_scene_summary/v4'
                or meta.get('schema_version') != 's3_d3_typed_scene_metadata/v3'):
            raise RuntimeError('INVALID_EVIDENCE_PERSISTENCE_FAILURE')
        raw = artifact / 'scene_response.pb'; raw_sha = artifact / 'scene_response.sha256'
        if sha is None:
            if raw.exists() or raw_sha.exists() or status not in {'SCENE_SERVICE_UNAVAILABLE', 'SCENE_REQUEST_INCOMPLETE'}:
                raise RuntimeError('INVALID_EVIDENCE_PERSISTENCE_FAILURE')
        elif (not called or not regular_file(raw) or not regular_file(raw_sha) or not valid_sha256(sha)
              or digest(raw) != sha or raw_sha.read_text(encoding='ascii').strip() != sha):
            raise RuntimeError('INVALID_EVIDENCE_PERSISTENCE_FAILURE')
        atomic_write_json_new(artifact / 'helper_process.json', {
            'run_id': self._active_run_id, 'argv': argv, 'binary_sha256': self._helper_sha256,
            'pid': None, 'pid_reason': 'unavailable_subprocess_run', 'start_steady_ns': started,
            'end_steady_ns': ended, 'exit_code': completed.returncode, 'outcome': status,
        })
        return status

    def prepare(self) -> PreparedHelper:
        if self._prepared_context is not None or self._prepared_helper is not None:
            raise PrepareFailure('INVALID_PREPARE')
        self._prepared_context = tempfile.TemporaryDirectory()
        try:
            prepared = self.compile_helper(Path(self._prepared_context.name))
            if not isinstance(prepared, PreparedHelper):
                raise PrepareFailure('INVALID_PREPARE_COMPILE')
            if (not valid_sha256(prepared.binary_sha256)
                    or prepared.binary_path != Path(self._prepared_context.name) / 'typed_scene_observer'
                    or digest(prepared.binary_path) != prepared.binary_sha256):
                raise PrepareFailure('INVALID_PREPARE_COMPILE')
            self._prepared_helper = prepared
            self._helper_sha256 = prepared.binary_sha256
            return prepared
        except BaseException:
            self.discard_prepared()
            raise

    def discard_prepared(self) -> None:
        context, self._prepared_context = self._prepared_context, None
        self._prepared_helper = None
        self._helper_sha256 = None
        if context is not None:
            context.cleanup()

    def persist_artifact(self, directory: Path, status: str) -> None:
        artifact = self._ensure_artifact_directory()
        if directory == artifact or not regular_file(artifact / 'scene_summary.json') or not regular_file(artifact / 'request_metadata.json'):
            raise RuntimeError('INVALID_EVIDENCE_PERSISTENCE_FAILURE')
        atomic_write_json_new(artifact / 'supervisor_metadata.json', {
            'run_id': self._active_run_id,
            'create_argv': list(self._create_arguments),
            'helper_status': status,
            'launch_argv': [str(ROS2_EXECUTABLE), *DEDICATED_LAUNCH_ARGUMENTS],
            'shutdown_policy': 'SUPERVISOR_SIGINT_ONLY_LAUNCHER_ESCALATION_POSSIBLE',
            'shutdown_grace_ms': MEASUREMENT_SHUTDOWN_GRACE_MS,
        })

    def finalize_evidence(self, status: str, phase: CreatePhaseResult | None,
                          helper_started: bool, shutdown_complete: bool) -> None:
        artifact = self._ensure_artifact_directory()
        if not (artifact / 'scene_summary.json').exists():
            atomic_write_json_new(artifact / 'scene_summary.json', {
                'status': 'INVALID_EVIDENCE_PERSISTENCE_FAILURE', 'reason': 'HELPER_NOT_COMPLETED',
                'run_id': self._active_run_id, 'request_raw_called': False, 'raw_response_sha256': None,
                'preflight_start_steady_ns': None, 'preflight_end_steady_ns': None,
                'request_start_steady_ns': None, 'request_end_steady_ns': None,
                'schema_version': 's3_d3_typed_scene_summary/v4',
            })
            atomic_write_json_new(artifact / 'request_metadata.json', {
                'scene_status': None, 'detail': 'HELPER_NOT_COMPLETED', 'run_id': self._active_run_id, 'request_raw_called': False,
                'preflight_start_steady_ns': None, 'preflight_end_steady_ns': None,
                'request_start_steady_ns': None, 'request_end_steady_ns': None,
                'outer_status': 'INVALID_EVIDENCE_PERSISTENCE_FAILURE',
                'service': '/world/world_demo/scene/info',
                'schema_version': 's3_d3_typed_scene_metadata/v3',
            })
        if not (artifact / 'create_process.json').exists():
            record = {'run_id': self._active_run_id, 'invocation_count': 0, 'outcome': 'NOT_STARTED'}
            if phase is not None:
                record = {'run_id': self._active_run_id, 'invocation_count': phase.create_invocations,
                          'executable_path': phase.executable_path, 'executable_sha256': phase.executable_sha256,
                          'argv': list(phase.argv), 'pid': phase.pid, 'start_steady_ns': phase.start_steady_ns,
                          'end_steady_ns': phase.end_steady_ns, 'exit_code': phase.exit_code,
                          'outcome': phase.status, 'reason': phase.reason}
            atomic_write_json_new(artifact / 'create_process.json', record)
        if not (artifact / 'helper_process.json').exists():
            atomic_write_json_new(artifact / 'helper_process.json', {
                'run_id': self._active_run_id, 'started': helper_started, 'outcome': 'NOT_STARTED' if not helper_started else status,
            })
        atomic_write_json_new(artifact / 'shutdown_outcome.json', {
            'run_id': self._active_run_id, 'process_group_owner': 'supervisor',
            'supervisor_sigint_attempted': True, 'grace_ms': MEASUREMENT_SHUTDOWN_GRACE_MS,
            'deadline_result': 'COMPLETE' if shutdown_complete else 'INCOMPLETE',
            'launcher_managed_escalation_observed': None,
            'final_classification': status,
        })

    def shutdown_sigint_only(self) -> bool:
        complete = True
        for process in (self._helper_process, self._launch_process):
            if process is None:
                continue
            try:
                self._process_group(process.pid, signal.SIGINT)
                process.wait(timeout=MEASUREMENT_SHUTDOWN_GRACE_MS / 1000.0)
            except (OSError, subprocess.TimeoutExpired):
                complete = False
        return complete

    def build(self) -> GuardedExecutionDependencies:
        adapter = RuntimeCreateAdapter(self._create_arguments)
        return GuardedExecutionDependencies(
            self.launch_bootstrap, adapter.spawn, self.compile_helper, self.helper_once,
            self.persist_artifact, self.shutdown_sigint_only, lambda: self._prepared_context,
            lambda: datetime.now(UTC).isoformat(), lambda: new_run_identity().run_id,
            self.prepare, self.begin_run, self.finalize_evidence, self.discard_prepared,
        )


def build_runtime_dependencies(
    workspace_root: Path,
    *,
    create_arguments: tuple[str, ...] | None = None,
) -> GuardedExecutionDependencies:
    """Construct deferred real-runtime dependencies without launching anything."""
    return RuntimeDependencyFactory(
        workspace_root, create_arguments=create_arguments,
    ).build()


def execute_guarded(
    workspace_root: Path,
    approval_spec: approval_guard.TypedSceneApprovalSpec,
    dependencies: GuardedExecutionDependencies,
) -> str:
    """One-shot orchestration. Approval identity is explicit and data-driven."""
    try:
        approval_guard.validate_spec(approval_spec, workspace_root, True, True)
    except approval_guard.TrustedContextError:
        return "INVALID_GATE_APPROVAL_SPEC"
    try:
        run_id = dependencies.run_id()
        if not isinstance(run_id, str) or not run_id:
            return "INVALID_PREPARE"
        if dependencies.prepare is not None:
            dependencies.prepare()
    except PrepareFailure as exc:
        return exc.status
    except (OSError, RuntimeError, ValueError, TimeoutError, InterruptedError):
        return "INVALID_PREPARE"
    begun = False
    try:
        if dependencies.begin_run is not None:
            dependencies.begin_run(run_id)
        begun = True
        approval_guard.build_trusted_context(workspace_root, approval_spec)
    except approval_guard.TrustedContextError:
        if begun and dependencies.finalize_evidence is not None:
            dependencies.finalize_evidence("INVALID_GATE_TRUSTED_CONTEXT", None, False, False)
        if dependencies.cleanup_prepared is not None:
            dependencies.cleanup_prepared()
        return "INVALID_GATE_TRUSTED_CONTEXT"
    except (OSError, RuntimeError, ValueError):
        if begun and dependencies.finalize_evidence is not None:
            dependencies.finalize_evidence("INVALID_PREPARE", None, False, False)
        if dependencies.cleanup_prepared is not None:
            dependencies.cleanup_prepared()
        return "INVALID_PREPARE"
    ok, _, lease = approval_guard.acquire_trusted(approval_spec, workspace_root)
    if not ok or lease is None:
        if begun and dependencies.finalize_evidence is not None:
            dependencies.finalize_evidence("INVALID_GATE_GUARD", None, False, False)
        if dependencies.cleanup_prepared is not None:
            dependencies.cleanup_prepared()
        return "INVALID_GATE_GUARD"
    status = "INVALID"
    phase: CreatePhaseResult | None = None
    helper_started = False
    shutdown_complete = False
    try:
        dependencies.launch_bootstrap()
        plan = resolve_create_plan(workspace_root)
        phase = create_phase(plan, dependencies.spawn_create, workspace_root=workspace_root)
        if not phase.helper_permitted:
            status = phase.status
        else:
            with dependencies.temporary_directory() as raw:
                temporary = Path(raw)
                helper_started = True
                status = dependencies.helper_once(temporary)
                dependencies.persist_artifact(temporary, status)
    except (OSError, RuntimeError, ValueError, TimeoutError, InterruptedError):
        status = "INVALID"
    finally:
        try:
            shutdown_complete = dependencies.shutdown_sigint_only()
            if not shutdown_complete:
                status = "SHUTDOWN_INCOMPLETE"
        except (OSError, RuntimeError, InterruptedError):
            shutdown_complete = False
            status = "SHUTDOWN_INCOMPLETE"
        try:
            if dependencies.finalize_evidence is not None:
                dependencies.finalize_evidence(status, phase, helper_started, shutdown_complete)
        except (OSError, RuntimeError, ValueError):
            status = "INVALID_EVIDENCE_PERSISTENCE_FAILURE"
        consumed, _ = approval_guard.consume_trusted(
            approval_spec, lease, workspace_root, run_id, status,
            dependencies.now_utc(),
        )
        if not consumed:
            status = "GUARD_CONSUMPTION_INCOMPLETE"
    return status

def result_json(result: CreatePhaseResult) -> str:
    return json.dumps(asdict(result), sort_keys=True, separators=(',', ':'))


def main(argv=None, dependencies: GuardedExecutionDependencies | None = None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--offline-self-test', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--workspace-root')
    parser.add_argument('--approval-id')
    parser.add_argument('--packet-path')
    parser.add_argument('--guard-path')
    args = parser.parse_args(argv)
    if args.execute:
        if not args.workspace_root or not args.approval_id or not args.packet_path or not args.guard_path:
            raise SystemExit('EXECUTION_GATE_ARGUMENTS_REQUIRED')
        root = Path(args.workspace_root)
        try:
            spec = approval_guard.spec_from_cli(args.approval_id, args.packet_path, args.guard_path)
            context = approval_guard.build_trusted_context(root, spec)
            _, guard_path = approval_guard.validate_spec(spec, root, True, True)
        except approval_guard.TrustedContextError as exc:
            raise SystemExit(f'EXECUTION_GATE_APPROVAL_SPEC_REJECTED:{exc}') from exc
        ok, record, _ = approval_guard.load(guard_path)
        if not ok or record is None or approval_guard.validate(record, context, spec, False)[0] is False:
            raise SystemExit('EXECUTION_GATE_GUARD_CONTEXT_REJECTED')
        if record.get('state') != approval_guard.AUTHORIZED:
            raise SystemExit('EXECUTION_GATE_PENDING_USER_APPROVAL')
        if dependencies is None:
            dependencies = build_runtime_dependencies(root)
        status = execute_guarded(root, spec, dependencies)
        if status.startswith('INVALID_PREPARE'):
            raise SystemExit(status)
        return 0 if status not in {'GUARD_CONSUMPTION_INCOMPLETE', 'SHUTDOWN_INCOMPLETE'} else 1
    if not args.offline_self_test:
        raise SystemExit('choose --offline-self-test; runtime execution is unavailable')
    print(json.dumps({
        'runtime_execution_available': False,
        'supervisor_mode': OWNERSHIP_MODE,
        'approval_binding': 'explicit-data-driven-spec',
    }, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
