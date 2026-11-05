"""Owned Gazebo process groups and explicit GUI readiness/Owner handshake.

Runtime entry point only. Tests inject process, scene, acknowledgment and
evidence adapters; this module is not invoked by offline collection.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import json
import os
import re
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
from mecanum_nav_bringup.local_training_readiness_worker import (
    EVENT_SCHEMA as READINESS_EVENT_SCHEMA,
    WORLD_IDENTITY_SOURCE,
    scene_readiness_matches,
    status_readiness_matches,
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

    async def start_controlled(
        self, command: tuple[str, ...], environment: dict[str, str],
    ) -> OwnedProcess:
        """Start one private framed-control child in its own session."""
        env = os.environ.copy()
        env.update(environment)
        return await asyncio.create_subprocess_exec(
            *command, env=env, start_new_session=True,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=4096 + len(b'HBTRACE_CONTROL ') + 1,
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


class RclpyReadiness:
    """Own an isolated worker for ROS/Gazebo server-scene readiness."""

    SERVER_READY_TIMEOUT_S = 30.0
    WORKER_MODULE = 'mecanum_nav_bringup.local_training_readiness_worker'
    REQUEST_SCHEMA = 'mecanum_b2_scene_readiness_request/v1'
    EVENT_SCHEMA = READINESS_EVENT_SCHEMA
    MAX_REQUEST_BYTES = 16 * 1024
    MAX_RECORD_BYTES = 4 * 1024
    MAX_STREAM_BYTES = 64 * 1024
    CLEANUP_CAP_S = 3.0

    def __init__(
        self, *, worker_factory=None, identity_reader=None, signal_group=None,
        monotonic=time.monotonic, monotonic_ns=time.monotonic_ns,
        sleep=asyncio.sleep,
    ) -> None:
        """Prepare process seams without creating middleware or a worker."""
        self._stdin_buffers: dict[int, bytearray] = {}
        self._worker_factory = worker_factory or self._spawn_worker
        self._identity_reader = identity_reader or self._read_process_identity
        self._signal_group = signal_group or self._signal_verified_group
        self._monotonic = monotonic
        self._monotonic_ns = monotonic_ns
        self._sleep = sleep
        self._evidence_sink = None
        self._worker = None
        self._worker_identity = None
        self._worker_cleanup_deadline = None
        self._stdout_task = None
        self._stderr_task = None
        self._worker_wait_task = None
        self._stdin_close_task = None
        self._stdin_closed_recorded = False
        self._cleanup_phase = 0
        self._cleanup_record_error = False
        self._cleanup_deadline_violation = False
        self._readiness_deadline_violation = False
        self._protocol_records = []
        self._protocol_error = None
        self._protocol_state = 'EXPECT_WORKER_STARTED'
        self._protocol_last_status = None
        self._accepted_backend_status = None
        self._protocol_last_scene = None
        self._protocol_last_scene_outcome = None
        self._protocol_last_query_service = None
        self._spawn_task = None
        self._phase_tasks = set()
        self._evidence_errors = []
        self._process_residue = 'NONE'
        self._task_residue = 'NONE'
        self._task_cleanup_unknown = False
        self._stdout_total = 0
        self._stderr_total = 0
        self._stderr_hash = hashlib.sha256()
        self._ready_attempted = False
        self._residue = 'NONE'
        self._active_request = None
        self._active_request_sha256 = None

    def bind_evidence_sink(self, evidence_sink):
        """Bind the one owner responsible for readiness evidence."""
        if (self._evidence_sink is not None
                and self._evidence_sink is not evidence_sink):
            raise RuntimeError('readiness evidence sink already bound')
        self._evidence_sink = evidence_sink

    @property
    def accepted_backend_status(self):
        """Status independently accepted by the production readiness path."""
        return dict(self._accepted_backend_status or {})

    @staticmethod
    def _read_process_identity(pid):
        raw = Path(f'/proc/{pid}/stat').read_text(encoding='ascii')
        closing = raw.rfind(')')
        if closing < 0:
            raise RuntimeError('malformed worker proc stat')
        fields = raw[closing + 2:].split()
        return {
            'pid': pid,
            'process_group_id': int(fields[2]),
            'session_id': int(fields[3]),
            'start_ticks': int(fields[19]),
        }

    @staticmethod
    def _valid_process_identity(identity, pid):
        if not isinstance(identity, dict):
            return False
        keys = ('pid', 'process_group_id', 'session_id', 'start_ticks')
        if set(identity) != set(keys):
            return False
        if any(type(identity[key]) is not int or identity[key] <= 0
               for key in keys):
            return False
        return (identity['pid'] == pid
                and identity['process_group_id'] == pid
                and identity['session_id'] == pid)

    async def _spawn_worker(self, environment):
        env = os.environ.copy()
        env.update(environment)
        return await asyncio.create_subprocess_exec(
            sys.executable, '-m', self.WORKER_MODULE,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env, start_new_session=True, limit=self.MAX_RECORD_BYTES,
        )

    def _capture_spawn_result(self, task):
        """Retain a late spawn handle after timeout or cancellation."""
        if task.cancelled():
            self._process_residue = 'UNKNOWN'
            return
        try:
            process = task.result()
        except BaseException:
            return
        if self._worker is None:
            self._worker = process

    async def _await_operation(self, operation, deadline, server, label):
        """Await one phase while polling the parent server and deadline."""
        if isinstance(operation, asyncio.Future):
            task = operation
        else:
            task = asyncio.create_task(operation)
            self._phase_tasks.add(task)
            if label == 'stdin close':
                self._stdin_close_task = task
        while True:
            if server.returncode is not None:
                self._record('readiness_server_exit_detected', {
                    'detection_monotonic_ns': self._monotonic_ns(),
                    'server_pid': server.pid,
                    'exit_status': server.returncode,
                    'readiness_phase': label,
                })
                raise RuntimeError('Gazebo server exited during readiness')
            if self._protocol_error:
                raise RuntimeError(self._protocol_error)
            for drain_task in (self._stdout_task, self._stderr_task):
                if (drain_task is not None and drain_task.done()
                        and not drain_task.cancelled()):
                    drain_error = drain_task.exception()
                    if drain_error is not None:
                        raise RuntimeError(
                            f'readiness worker drain failed during {label}'
                        ) from drain_error
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f'readiness deadline expired during {label}'
                )
            if task.done():
                result = task.result()
                if self._monotonic() >= deadline:
                    raise TimeoutError(
                        f'{label} completed after readiness deadline'
                    )
                return result
            await asyncio.wait(
                {task}, timeout=min(0.025, remaining),
                return_when=asyncio.FIRST_COMPLETED,
            )
        return task.result()

    def _record(self, event, facts):
        if self._evidence_sink is None:
            raise RuntimeError('readiness evidence sink is not bound')
        try:
            self._evidence_sink.record(event, facts)
        except BaseException as error:
            self._evidence_errors.append(
                f'{event}:{type(error).__name__}:{error}'[:512]
            )
            raise

    @staticmethod
    def _canonical_request(request):
        return json.dumps(
            request, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
            allow_nan=False,
        ).encode('utf-8')

    def _make_request(self, plan, config_hash, deadline_ns):
        coordinator = plan.coordinator_ingress_instance_id
        if type(coordinator) is not int or not 0 < coordinator < 2**64:
            raise RuntimeError('coordinator identity is not nonzero uint64')
        domain = plan.environment.get('ROS_DOMAIN_ID')
        partition = plan.environment.get('GZ_PARTITION')
        if (not isinstance(domain, str) or not re.fullmatch(r'[0-9]+', domain)
                or not isinstance(partition, str) or not partition):
            raise RuntimeError('readiness domain/partition binding is invalid')
        if config_hash != plan.config_hash:
            raise RuntimeError('resolved config hash differs from launch plan')
        try:
            if str(uuid.UUID(plan.session_id)) != plan.session_id:
                raise ValueError
        except (ValueError, TypeError, AttributeError) as error:
            raise RuntimeError('session ID must be canonical UUID') from error
        return {
            'schema_id': self.REQUEST_SCHEMA,
            'request_id': str(uuid.uuid4()),
            'session_id': plan.session_id,
            'config_hash': config_hash,
            'asset_manifest_sha256': plan.asset_manifest_sha256,
            'coordinator_ingress_instance_id': coordinator,
            'world_id': 'b2_training_arena',
            'model_id': 'mecanum_b2',
            'gz_partition': partition,
            'ros_domain_id': domain,
            'deadline_monotonic_ns': deadline_ns,
        }

    @staticmethod
    def _strict_worker_json(line):
        def pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('duplicate JSON key')
                result[key] = value
            return result

        def constant(value):
            raise ValueError(f'invalid JSON constant: {value}')

        return json.loads(
            line.decode('utf-8', errors='strict'),
            object_pairs_hook=pairs, parse_constant=constant,
        )

    async def _drain_stdout(self, request_id, request_sha256):
        stream = self._worker.stdout
        buffered = bytearray()
        seen_result = False
        sequence = 0
        allowed = {
            'worker_started', 'status_wait_started', 'status_matched',
            'scene_query_started', 'scene_query_finished', 'worker_result',
        }
        while True:
            chunk = await stream.read(2048)
            if not chunk:
                break
            self._stdout_total += len(chunk)
            if self._stdout_total > self.MAX_STREAM_BYTES:
                self._protocol_error = 'worker stdout exceeded 64 KiB'
                continue
            if seen_result:
                self._protocol_error = 'protocol output followed worker_result'
                continue
            buffered.extend(chunk)
            while b'\n' in buffered:
                line, _, tail = buffered.partition(b'\n')
                buffered = bytearray(tail)
                if len(line) + 1 > self.MAX_RECORD_BYTES:
                    self._protocol_error = 'worker record exceeded 4 KiB'
                    continue
                try:
                    record = self._strict_worker_json(line)
                    if not isinstance(record, dict) or set(record) != {
                        'schema_id', 'request_id', 'request_sha256',
                        'sequence', 'event', 'monotonic_ns', 'facts',
                    }:
                        raise ValueError('worker event fields mismatch')
                    if record['schema_id'] != self.EVENT_SCHEMA:
                        raise ValueError('worker event schema mismatch')
                    if record['request_id'] != request_id:
                        raise ValueError('worker request ID mismatch')
                    if record['request_sha256'] != request_sha256:
                        raise ValueError('worker request hash mismatch')
                    if type(record['sequence']) is not int or record[
                        'sequence'
                    ] != sequence + 1:
                        raise ValueError('worker event sequence mismatch')
                    if type(record['monotonic_ns']) is not int or record[
                        'monotonic_ns'
                    ] <= 0:
                        raise ValueError('worker monotonic timestamp invalid')
                    if record['event'] not in allowed or not isinstance(
                        record['facts'], dict,
                    ):
                        raise ValueError('worker event type/facts invalid')
                    self._validate_event_facts(record, self._active_request)
                    if seen_result:
                        raise ValueError('duplicate worker_result')
                    self._advance_protocol_state(record)
                    sequence += 1
                    if record['event'] == 'worker_result':
                        seen_result = True
                    self._protocol_records.append(record)
                    self._record('readiness_worker_event', {
                        'worker_monotonic_ns': record['monotonic_ns'],
                        'parent_received_monotonic_ns': self._monotonic_ns(),
                        'record': record,
                    })
                    if self._active_request is not None and (
                        self._monotonic_ns() >= self._active_request[
                            'deadline_monotonic_ns'
                        ]
                    ):
                        self._protocol_error = (
                            'worker evidence processing crossed '
                            'readiness deadline'
                        )
                except BaseException as exc:
                    self._protocol_error = f'worker protocol invalid: {exc}'
        if buffered:
            self._protocol_error = self._protocol_error or (
                'worker stdout ended with partial JSON record'
            )
        results = [r for r in self._protocol_records
                   if r['event'] == 'worker_result']
        if len(results) != 1:
            self._protocol_error = self._protocol_error or (
                'worker result missing or duplicated'
            )

    def _advance_protocol_state(self, record):
        """Validate protocol history, including repeated query cycles."""
        event = record['event']
        facts = record['facts']
        state = self._protocol_state
        if event == 'worker_started':
            if state != 'EXPECT_WORKER_STARTED':
                raise ValueError('worker_started is not the first event')
            self._protocol_state = 'EXPECT_STATUS_WAIT'
        elif event == 'status_wait_started':
            if state != 'EXPECT_STATUS_WAIT':
                raise ValueError('status_wait_started transition mismatch')
            self._protocol_state = 'EXPECT_STATUS_MATCHED'
        elif event == 'status_matched':
            if state != 'EXPECT_STATUS_MATCHED':
                raise ValueError('status_matched transition mismatch')
            self._protocol_last_status = facts['status']
            self._protocol_state = 'EXPECT_QUERY_STARTED'
        elif event == 'scene_query_started':
            if state != 'EXPECT_QUERY_STARTED':
                raise ValueError('scene_query_started transition mismatch')
            self._protocol_last_query_service = facts['service']
            self._protocol_state = 'EXPECT_QUERY_FINISHED'
        elif event == 'scene_query_finished':
            if state != 'EXPECT_QUERY_FINISHED':
                raise ValueError('scene_query_finished without query start')
            self._protocol_last_scene = {
                key: facts[key] for key in (
                    'scene_name', 'matching_model_count', 'query_service',
                    'query_partition', 'world_identity_source',
                )
            }
            if facts['query_service'] != self._protocol_last_query_service:
                raise ValueError('scene query service history mismatch')
            self._protocol_last_scene_outcome = facts['outcome']
            self._protocol_state = (
                'MATCHED_SCENE' if facts['outcome'] == 'MATCH'
                else 'EXPECT_STATUS_WAIT'
            )
        elif event == 'worker_result':
            if state == 'EXPECT_WORKER_STARTED':
                raise ValueError('worker_result before worker_started')
            if facts['verdict'] == 'FAIL':
                self._protocol_state = 'TERMINAL'
                return
            if state != 'MATCHED_SCENE':
                raise ValueError('READY lacks a matched query history')
            ready = facts['facts']
            if (ready.get('status') != self._protocol_last_status
                    or ready.get('scene') != self._protocol_last_scene
                    or self._protocol_last_scene_outcome != 'MATCH'):
                raise ValueError('READY facts disagree with protocol history')
            if not scene_readiness_matches(
                    self._protocol_last_status,
                    self._protocol_last_scene, self._active_request):
                raise ValueError('READY terminal binding is not matched')
            self._protocol_state = 'TERMINAL'
        else:
            raise ValueError('unknown readiness protocol event')

    async def _drain_stderr(self):
        while True:
            chunk = await self._worker.stderr.read(4096)
            if not chunk:
                return
            self._stderr_total += len(chunk)
            self._stderr_hash.update(chunk)
            if self._stderr_total > self.MAX_STREAM_BYTES:
                self._protocol_error = 'worker stderr exceeded 64 KiB'

    def _request_binding_facts(self, request, digest):
        return {
            'request_id': request['request_id'],
            'request_sha256': digest,
            'session_id': request['session_id'],
            'config_hash': request['config_hash'],
            'asset_manifest_sha256': request['asset_manifest_sha256'],
            'coordinator_ingress_instance_id': request[
                'coordinator_ingress_instance_id'
            ],
            'world_id': request['world_id'],
            'model_id': request['model_id'],
            'gz_partition': request['gz_partition'],
            'ros_domain_id': request['ros_domain_id'],
            'deadline_monotonic_ns': request['deadline_monotonic_ns'],
        }

    def _validate_event_facts(self, record, request):
        """Reject event payloads that do not match the worker protocol."""
        if not isinstance(request, dict):
            raise ValueError('readiness request is unavailable')
        event = record['event']
        facts = record['facts']
        binding = {
            key: request[key] for key in (
                'session_id', 'config_hash', 'asset_manifest_sha256',
                'coordinator_ingress_instance_id',
            )
        }
        if event == 'worker_started':
            if (set(facts) != {'request_binding'}
                    or facts['request_binding'] != binding):
                raise ValueError('worker_started binding mismatch')
        elif event == 'status_wait_started':
            if facts != {
                'topic': '/mecanum/local_training/backend_state',
                'qos_depth': 50,
            }:
                raise ValueError('status wait contract mismatch')
        elif event == 'status_matched':
            if set(facts) != {'status', 'request_binding'}:
                raise ValueError('matched status fields mismatch')
            if facts['request_binding'] != binding:
                raise ValueError('matched status binding mismatch')
            status = facts['status']
            if not isinstance(status, dict) or set(status) != {
                'world_id', 'session_id', 'config_hash',
                'backend_instance_id', 'status_sequence', 'fault_flags',
                'actuator_inhibited',
            }:
                raise ValueError('matched status fields invalid')
            if not status_readiness_matches(status, request):
                raise ValueError('matched status predicate failed')
        elif event == 'scene_query_started':
            expected_service = f"/world/{request['world_id']}/scene/info"
            if (set(facts) != {'service', 'timeout_ms'}
                    or facts['service'] != expected_service):
                raise ValueError('scene query start binding mismatch')
            timeout_ms = facts['timeout_ms']
            if type(timeout_ms) is not int or not 1 <= timeout_ms <= 500:
                raise ValueError('scene query timeout is invalid')
        elif event == 'scene_query_finished':
            if set(facts) != {
                'scene_name', 'matching_model_count', 'query_service',
                'query_partition', 'world_identity_source', 'duration_ns',
                'outcome', 'error',
            }:
                raise ValueError('scene query result fields mismatch')
            if (facts['scene_name'] is not None
                    and not isinstance(facts['scene_name'], str)):
                raise ValueError('scene label must be raw string or None')
            if (type(facts['matching_model_count']) is not int
                    or facts['matching_model_count'] < 0
                    or facts['query_service'] != (
                        f"/world/{request['world_id']}/scene/info"
                    )
                    or facts['query_partition'] != request['gz_partition']
                    or facts['world_identity_source'] != WORLD_IDENTITY_SOURCE
                    or type(facts['duration_ns']) is not int
                    or facts['duration_ns'] < 0
                    or facts['outcome'] not in {'MATCH', 'MISMATCH', 'ERROR'}
                    or (facts['error'] is not None
                        and not isinstance(facts['error'], str))):
                raise ValueError('scene query result is invalid')
            matches = scene_readiness_matches(
                self._protocol_last_status, {
                    key: facts[key] for key in (
                        'scene_name', 'matching_model_count', 'query_service',
                        'query_partition', 'world_identity_source',
                    )
                }, request,
            )
            if (facts['outcome'] == 'MATCH'
                    and (not matches or facts['error'] is not None)):
                raise ValueError('MATCH scene result facts are inconsistent')
            if (facts['outcome'] == 'MISMATCH'
                    and (matches or facts['error'] is not None)):
                raise ValueError(
                    'MISMATCH scene result facts are inconsistent'
                )
            if (facts['outcome'] == 'ERROR'
                    and (not facts['error'] or not isinstance(
                        facts['error'], str,
                    ))):
                raise ValueError('ERROR scene result lacks an error fact')
        elif event == 'worker_result':
            if set(facts) != {
                'verdict', 'reason', 'facts', 'cleanup_errors',
                'cleanup_elapsed_ns',
            }:
                raise ValueError('worker result fields mismatch')
            if (facts['verdict'] not in {'READY', 'FAIL'}
                    or not isinstance(facts['reason'], str)
                    or not isinstance(facts['facts'], dict)
                    or not isinstance(facts['cleanup_errors'], list)
                    or any(not isinstance(item, str)
                           for item in facts['cleanup_errors'])
                    or type(facts['cleanup_elapsed_ns']) is not int
                    or facts['cleanup_elapsed_ns'] < 0
                    or facts['cleanup_elapsed_ns'] > 3_000_000_000):
                raise ValueError('worker result values invalid')
            if facts['verdict'] == 'READY' and facts['reason']:
                raise ValueError('READY result contains a failure reason')
            if facts['verdict'] == 'FAIL' and not facts['reason']:
                raise ValueError('FAIL result has no reason')

    def _validate_ready_result(self, record, request, digest):
        facts = record['facts']
        if facts.get('verdict') != 'READY':
            raise RuntimeError(
                str(facts.get('reason') or 'worker readiness failed')
            )
        if facts.get('cleanup_errors') != []:
            raise RuntimeError('worker cleanup was not clean')
        ready = facts.get('facts')
        if not isinstance(ready, dict) or set(ready) != {
            'status', 'scene', 'request_binding',
        }:
            raise RuntimeError('worker READY facts are incomplete')
        status = ready['status']
        binding = ready['request_binding']
        expected_binding = {
            key: request[key] for key in (
                'session_id', 'config_hash', 'asset_manifest_sha256',
                'coordinator_ingress_instance_id',
            )
        }
        if binding != expected_binding:
            raise RuntimeError('worker READY request binding mismatch')
        if not status_readiness_matches(status, request):
            raise RuntimeError('worker status measurement is invalid')
        if not scene_readiness_matches(status, ready['scene'], request):
            raise RuntimeError('worker scene facts do not match binding')
        return {
            **self._request_binding_facts(request, digest),
            'status': status, 'scene': ready['scene'],
        }

    async def server_scene(
        self, plan: LaunchPlan, process: OwnedProcess, timeout_s: float,
    ) -> None:
        """Wait for server readiness in one owned middleware worker process."""
        if self._ready_attempted:
            raise RuntimeError('readiness worker attempt already consumed')
        if self._evidence_sink is None:
            raise RuntimeError(
                'readiness evidence sink must be bound before spawn'
            )
        self._ready_attempted = True
        started = self._monotonic()
        deadline = started + min(timeout_s, self.SERVER_READY_TIMEOUT_S)
        if deadline <= started:
            raise TimeoutError('readiness budget expired before worker spawn')
        self._readiness_deadline = deadline
        deadline_ns = self._monotonic_ns() + int(
            max(0.0, deadline - started) * 1e9
        )
        request = None
        digest = None
        try:
            _, config_hash, manifest_hash, _ = load_bound_config(
                plan.resolved_config,
            )
            if manifest_hash != plan.asset_manifest_sha256:
                raise RuntimeError(
                    'resolved manifest differs from launch plan'
                )
            request = self._make_request(plan, config_hash, deadline_ns)
            self._active_request = request
            request_bytes = self._canonical_request(request)
            if len(request_bytes) > self.MAX_REQUEST_BYTES:
                raise RuntimeError('readiness request exceeds 16 KiB')
            digest = hashlib.sha256(request_bytes).hexdigest()
            self._active_request_sha256 = digest
            self._record('readiness_worker_spawn_requested', {
                **self._request_binding_facts(request, digest),
                'module': self.WORKER_MODULE,
                'interpreter': sys.executable,
            })
            if self._monotonic() >= deadline:
                raise TimeoutError(
                    'readiness budget expired before worker spawn'
                )
            self._spawn_task = asyncio.create_task(
                self._worker_factory(dict(plan.environment)),
            )
            self._spawn_task.add_done_callback(self._capture_spawn_result)
            # Shield the owned task from caller cancellation. If the bounded
            # wait ends first, finalization still owns and accounts for it.
            self._worker = await self._await_operation(
                self._spawn_task, deadline, process, 'worker spawn',
            )
            self._stdout_task = asyncio.create_task(
                self._drain_stdout(request['request_id'], digest),
            )
            self._stderr_task = asyncio.create_task(self._drain_stderr())
            self._worker_wait_task = asyncio.create_task(self._worker.wait())
            try:
                identity = self._identity_reader(self._worker.pid)
                if not self._valid_process_identity(
                    identity, self._worker.pid,
                ):
                    raise RuntimeError('readiness worker identity invalid')
                self._worker_identity = identity
                self._process_residue = 'OWNED'
                self._residue = 'OWNED'
                self._record('readiness_worker_spawned', {
                    **self._request_binding_facts(request, digest),
                    'worker_identity': identity,
                })
                if self._monotonic() >= deadline:
                    raise TimeoutError(
                        'readiness deadline expired after spawn evidence'
                    )
            except BaseException:
                self._process_residue = 'UNKNOWN'
                self._residue = 'UNKNOWN'
                raise
            self._worker.stdin.write(request_bytes + b'\n')
            await self._await_operation(
                self._worker.stdin.drain(), deadline, process,
                'request drain',
            )
            self._worker.stdin.close()
            await self._await_operation(
                self._worker.stdin.wait_closed(), deadline, process,
                'stdin close',
            )
            self._record('readiness_request_sent', {
                **self._request_binding_facts(request, digest),
            })
            if self._monotonic() >= deadline:
                raise TimeoutError(
                    'readiness deadline expired after request evidence'
                )
            while True:
                if self._monotonic() >= deadline:
                    raise TimeoutError('readiness parent deadline expired')
                if process.returncode is not None:
                    self._record('readiness_server_exit_detected', {
                        'detection_monotonic_ns': self._monotonic_ns(),
                        'server_pid': process.pid,
                        'exit_status': process.returncode,
                    })
                    raise RuntimeError('Gazebo server exited during readiness')
                if self._protocol_error:
                    raise RuntimeError(self._protocol_error)
                tasks = {self._worker_wait_task, self._stdout_task,
                         self._stderr_task}
                pending_tasks = {task for task in tasks if not task.done()}
                if not pending_tasks:
                    break
                remaining = deadline - self._monotonic()
                await asyncio.wait(
                    pending_tasks, timeout=min(0.05, max(0.0, remaining)),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in tasks:
                    if task.done() and not task.cancelled():
                        error = task.exception()
                        if error is not None:
                            raise RuntimeError(
                                f'readiness worker pipe/task failed: {error}'
                            ) from error
            if self._monotonic() >= deadline:
                raise TimeoutError('readiness worker completed after deadline')
            if self._protocol_error:
                raise RuntimeError(self._protocol_error)
            if self._worker.returncode != 0:
                raise RuntimeError(
                    f'readiness worker exited {self._worker.returncode}'
                )
            records = self._protocol_records
            result = records[-1] if records else None
            if result is None or result['event'] != 'worker_result':
                raise RuntimeError('readiness worker result missing')
            ready_facts = self._validate_ready_result(result, request, digest)
            if self._monotonic() >= deadline:
                raise TimeoutError(
                    'readiness validation completed after deadline'
                )
            self._record('readiness_worker_parent_validated', {
                'parent_received_monotonic_ns': self._monotonic_ns(),
                'worker_exit_status': self._worker.returncode,
                'readiness': ready_facts,
                'stderr_bytes': self._stderr_total,
                'stderr_sha256': self._stderr_hash.hexdigest(),
            })
            if self._monotonic() >= deadline:
                raise TimeoutError(
                    'readiness validation evidence completed after deadline'
                )
            self._accepted_backend_status = dict(ready_facts['status'])
            self._residue = 'NONE'
        except BaseException as error:
            detection = self._monotonic_ns()
            try:
                self._record('readiness_failure_detected', {
                    'detection_monotonic_ns': detection,
                    'error_type': type(error).__name__,
                    'error': str(error)[:512],
                    'request_id': request['request_id'] if request else None,
                    'worker_identity': self._worker_identity,
                    'residue': self._residue,
                })
            except BaseException:
                pass
            raise
        finally:
            active_exception = sys.exc_info()[0] is not None
            await self._finalize_worker()
            deadline = self._readiness_deadline
            if deadline is not None and self._monotonic() >= deadline:
                self._readiness_deadline_violation = True
                try:
                    self._record(
                        'readiness_deadline_violation_after_finalization', {
                            'detection_monotonic_ns': self._monotonic_ns(),
                            'readiness_deadline_s': deadline,
                            'cleanup_deadline_s': (
                                self._worker_cleanup_deadline
                            ),
                            'worker_identity': self._worker_identity,
                            'process_residue': self._process_residue,
                            'task_residue': self._task_residue,
                        },
                    )
                except BaseException:
                    pass
            if self._cleanup_deadline_violation and not active_exception:
                raise TimeoutError(
                    'readiness worker cleanup deadline exceeded'
                )
            if self._readiness_deadline_violation and not active_exception:
                raise TimeoutError(
                    'readiness deadline expired during finalization'
                )
            if (self._residue != 'NONE' or self._cleanup_record_error
                    or self._evidence_errors) and not active_exception:
                raise RuntimeError(
                    'readiness worker incomplete: '
                    f'residue={self._residue}, '
                    f'evidence_errors={self._evidence_errors!r}'
                )

    async def _wait_worker(self, timeout):
        if self._worker_wait_task is None:
            return self._worker is None or self._worker.returncode is not None
        if self._worker_wait_task.done():
            return True
        done, _ = await asyncio.wait(
            {self._worker_wait_task}, timeout=max(0.0, timeout),
        )
        return bool(done)

    def _verified_signal(self, sig):
        if self._worker is None or self._worker_identity is None:
            return False, 'identity_unavailable'
        try:
            current = self._identity_reader(self._worker.pid)
        except BaseException as error:
            return False, f'identity_read_failed:{type(error).__name__}'
        if current != self._worker_identity:
            return False, 'identity_mismatch_or_pid_reuse'
        if not self._valid_process_identity(current, self._worker.pid):
            return False, 'identity_invalid'
        try:
            self._signal_group(self._worker, current, sig)
        except ProcessLookupError:
            return False, 'process_group_missing'
        except OSError as error:
            return False, f'signal_failed:{error.errno}'
        return True, 'signal_sent'

    @staticmethod
    def _signal_verified_group(process, identity, sig):
        del process
        os.killpg(identity['process_group_id'], sig)

    async def _finalize_worker(self):
        if self._worker_cleanup_deadline is None:
            self._worker_cleanup_deadline = (
                self._monotonic() + self.CLEANUP_CAP_S
            )
            try:
                self._record('readiness_worker_cleanup_started', {
                    'detection_monotonic_ns': self._monotonic_ns(),
                    'worker_identity': self._worker_identity,
                    'residue': self._residue,
                })
            except BaseException:
                pass
        deadline = self._worker_cleanup_deadline
        if self._monotonic() >= deadline:
            self._cleanup_deadline_violation = True
        if self._spawn_task is not None and self._worker is None:
            if not self._spawn_task.done():
                remaining = max(0.0, deadline - self._monotonic())
                if remaining > 0:
                    await asyncio.wait({self._spawn_task}, timeout=remaining)
            if self._spawn_task.done() and not self._spawn_task.cancelled():
                try:
                    self._worker = self._spawn_task.result()
                except BaseException:
                    self._process_residue = 'NONE'
            else:
                self._process_residue = 'UNKNOWN'
                self._spawn_task.cancel()

        stdin = getattr(self._worker, 'stdin', None)
        if self._worker is not None:
            if self._worker_wait_task is None:
                self._worker_wait_task = asyncio.create_task(
                    self._worker.wait(),
                )
            if self._active_request is not None:
                if self._stdout_task is None:
                    self._stdout_task = asyncio.create_task(
                        self._drain_stdout(
                            self._active_request['request_id'],
                            self._active_request_sha256,
                        ),
                    )
                if self._stderr_task is None:
                    self._stderr_task = asyncio.create_task(
                        self._drain_stderr(),
                    )
            if self._worker_identity is None:
                try:
                    identity = self._identity_reader(self._worker.pid)
                    if not self._valid_process_identity(
                        identity, self._worker.pid,
                    ):
                        raise RuntimeError('late worker identity invalid')
                    self._worker_identity = identity
                    self._process_residue = 'OWNED'
                    self._record('readiness_worker_spawned', {
                        'worker_identity': identity,
                        'late_handle_received_during_cleanup': True,
                    })
                except BaseException:
                    self._process_residue = 'UNKNOWN'
        if stdin is not None:
            try:
                if not stdin.is_closing():
                    stdin.close()
                close_task = self._stdin_close_task
                if close_task is None:
                    close_task = asyncio.create_task(stdin.wait_closed())
                    self._stdin_close_task = close_task
                    self._phase_tasks.add(close_task)
                remaining = max(0.0, deadline - self._monotonic())
                close_budget = min(0.1, remaining)
                if close_budget > 0 and not close_task.done():
                    await asyncio.wait({close_task}, timeout=close_budget)
                if close_task.done() and not close_task.cancelled():
                    close_task.result()
                    self._record('readiness_worker_stdin_closed', {
                        'worker_identity': self._worker_identity,
                        'remaining_budget_s': max(
                            0.0, deadline - self._monotonic(),
                        ),
                    })
                    self._stdin_closed_recorded = True
            except BaseException:
                self._task_residue = 'FAILED'
                self._cleanup_record_error = True
        phases = ((signal.SIGINT, 0.5), (signal.SIGTERM, 0.5),
                  (signal.SIGKILL, float('inf')))
        if self._worker is not None and self._worker.returncode is None:
            while self._cleanup_phase < len(phases):
                sig, phase_s = phases[self._cleanup_phase]
                self._cleanup_phase += 1
                remaining = max(0.0, deadline - self._monotonic())
                if remaining <= 0:
                    break
                budget = min(phase_s, remaining)
                sent, reason = self._verified_signal(sig)
                try:
                    self._record('readiness_worker_cleanup_signal', {
                        'signal': sig, 'sent': sent, 'reason': reason,
                        'worker_identity': self._worker_identity,
                        'remaining_budget_s': remaining,
                    })
                except BaseException:
                    self._cleanup_record_error = True
                if await self._wait_worker(
                    min(budget, deadline - self._monotonic()),
                ):
                    break
                if not sent:
                    self._process_residue = 'UNKNOWN'
                    break
        close_task = self._stdin_close_task
        if (close_task is not None and close_task.done()
                and not close_task.cancelled()):
            try:
                close_task.result()
                if not self._stdin_closed_recorded:
                    self._record('readiness_worker_stdin_closed', {
                        'worker_identity': self._worker_identity,
                        'after_worker_stop': True,
                        'remaining_budget_s': max(
                            0.0, deadline - self._monotonic(),
                        ),
                    })
                    self._stdin_closed_recorded = True
            except BaseException:
                self._task_residue = 'FAILED'
                self._cleanup_record_error = True
        task_map = {
            'stdout_drain': self._stdout_task,
            'stderr_drain': self._stderr_task,
            'worker_wait': self._worker_wait_task,
            'spawn': self._spawn_task,
            'stdin_close': self._stdin_close_task,
        }
        task_map.update({f'io_{i}': task
                         for i, task in enumerate(self._phase_tasks)
                         if task is not self._stdin_close_task})
        live_tasks = {task for task in task_map.values()
                      if task is not None and not task.done()}
        remaining = max(0.0, deadline - self._monotonic())
        if live_tasks and remaining > 0:
            await asyncio.wait(live_tasks, timeout=remaining)
        for task in live_tasks:
            if not task.done():
                task.cancel()
        remaining = max(0.0, deadline - self._monotonic())
        if live_tasks and remaining > 0:
            await asyncio.wait(live_tasks, timeout=remaining)
        task_states = {}
        task_pending = False
        task_failed = False
        task_unknown = False
        for label, task in task_map.items():
            if task is None:
                task_states[label] = 'not_started'
            elif not task.done():
                task_states[label] = 'pending'
                task_pending = True
            elif task.cancelled():
                task_states[label] = 'cancelled'
                if label == 'stdin_close':
                    task_unknown = True
            else:
                try:
                    error = task.exception()
                except BaseException as exc:
                    error = exc
                if error is None:
                    task_states[label] = 'done'
                else:
                    task_states[label] = f'failed:{type(error).__name__}'
                    task_failed = True
        self._task_residue = (
            'UNKNOWN' if task_pending or task_unknown
            or self._task_cleanup_unknown
            else 'FAILED' if task_failed else 'NONE'
        )
        joined = (
            self._worker is not None and self._worker.returncode is not None
        )
        if self._worker is None:
            if self._spawn_task is None or (
                self._spawn_task.done() and not self._spawn_task.cancelled()
            ):
                self._process_residue = 'NONE'
            else:
                self._process_residue = 'UNKNOWN'
        elif joined and self._worker_identity is not None:
            try:
                os.killpg(self._worker_identity['process_group_id'], 0)
            except ProcessLookupError:
                self._process_residue = 'NONE'
            except PermissionError:
                self._process_residue = 'UNKNOWN'
            else:
                self._process_residue = 'UNKNOWN'
        elif self._worker_identity is None:
            self._process_residue = 'UNKNOWN'
        else:
            self._process_residue = 'UNKNOWN'
        self._residue = (
            'NONE' if self._process_residue == 'NONE'
            and self._task_residue == 'NONE' else 'UNKNOWN'
        )
        try:
            self._record('readiness_worker_cleanup_finished', {
                'worker_identity': self._worker_identity,
                'exit_status': (
                    self._worker.returncode if self._worker is not None
                    else None
                ),
                'joined': joined,
                'residue': self._residue,
                'process_residue': self._process_residue,
                'task_residue': self._task_residue,
                'task_states': task_states,
                'cleanup_elapsed_s': self.CLEANUP_CAP_S - max(
                    0.0, deadline - self._monotonic(),
                ),
            })
        except BaseException:
            self._cleanup_record_error = True
        if self._monotonic() >= deadline:
            self._cleanup_deadline_violation = True
            try:
                self._record('readiness_worker_cleanup_deadline_violation', {
                    'detection_monotonic_ns': self._monotonic_ns(),
                    'cleanup_deadline_s': deadline,
                    'worker_identity': self._worker_identity,
                    'process_residue': self._process_residue,
                    'task_residue': self._task_residue,
                })
            except BaseException:
                self._cleanup_record_error = True

    @staticmethod
    def _matches_bound_scene_status(msg, plan, config_hash: str) -> bool:
        """Pure predicate for the existing fault-free inhibited status."""
        return (
            msg.header.frame_id == 'b2_training_arena'
            and msg.session_id == plan.session_id
            and msg.config_hash == config_hash
            and msg.backend_instance_id != 0
            and msg.status_sequence > 0
            and msg.fault_flags == 0
            and msg.actuator_inhibited
        )

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
    HEARTBEAT_OBSERVER_MODULE = (
        'mecanum_nav_bringup.local_training_heartbeat_trace_observer'
    )
    HEARTBEAT_OBSERVER_FRAME = b'HBTRACE_CONTROL '
    HEARTBEAT_OBSERVER_MAX_FRAME = 4096
    HEARTBEAT_OBSERVER_START_CAP_S = 3.0
    HEARTBEAT_OBSERVER_CLEANUP_CAP_S = 3.0

    def __init__(
        self, *, plan: LaunchPlan, launcher: ProcessLauncher,
        readiness: Readiness, evidence_sink: EvidenceSink,
        heartbeat_diagnostics_enabled: bool = False,
        heartbeat_trace_directory: Path | None = None,
        heartbeat_observer_factory=None,
        heartbeat_library_path: Path | None = None,
        heartbeat_identity_reader=None,
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
        self.heartbeat_diagnostics_enabled = (
            heartbeat_diagnostics_enabled is True
        )
        self.heartbeat_trace_directory = heartbeat_trace_directory
        self.heartbeat_observer_factory = heartbeat_observer_factory
        self.heartbeat_library_path = heartbeat_library_path
        self._heartbeat_identity_reader = (
            heartbeat_identity_reader or RclpyReadiness._read_process_identity
        )
        self._heartbeat_observer = None
        self._heartbeat_observer_process = None
        self._heartbeat_observer_identity = None
        self._heartbeat_observer_nonce = None
        self._heartbeat_observer_spawn_task = None
        self._heartbeat_observer_wait_task = None
        self._heartbeat_observer_exit_status = None
        self._heartbeat_observer_state = None
        self._heartbeat_observer_stderr_task = None
        self._heartbeat_observer_stderr = bytearray()
        self._heartbeat_observer_stderr_total = 0
        self._heartbeat_observer_protocol_lock = asyncio.Lock()
        self._heartbeat_observer_cleanup_deadline = None
        self._heartbeat_observer_stop_acknowledged = False
        self._heartbeat_observer_end_written = False
        self._heartbeat_observer_handle_closed = False
        self._heartbeat_observer_writer_closed = False
        self._heartbeat_observer_termination = 'NOT_STARTED'
        self._heartbeat_observer_protocol_started = False
        self._task_residue = 'NONE'
        self._process_residue = 'NONE'
        self._heartbeat_files = ()
        self._heartbeat_clock = None
        self._heartbeat_clock_domain_certificate = None
        self._heartbeat_library_sha256 = None
        self._heartbeat_trace_environment = {}
        self._heartbeat_trace_error = None
        self._heartbeat_trace_reported = False
        self._server_process_record = None
        self.owned: list[ProcessRecord] = []
        self._observer_tasks: set[asyncio.Task] = set()
        self._cleanup_lock = asyncio.Lock()
        self.gui_opened = False
        bind_evidence_sink = getattr(readiness, 'bind_evidence_sink', None)
        if bind_evidence_sink is not None:
            bind_evidence_sink(evidence_sink)

    async def start(self) -> None:
        """Start the server and requested GUI, failing closed on readiness."""
        try:
            await self._prepare_heartbeat_diagnostics()
            bind_environment = getattr(
                self.readiness, 'bind_environment', None,
            )
            if bind_environment is not None:
                bind_environment(self.plan.environment)
            bridge_command = getattr(self.plan, 'bridge_command', None)
            if bridge_command:
                bridge = await self.launcher.start(
                    bridge_command, self.plan.environment,
                )
                bridge_record = ProcessRecord(
                    'parameter_bridge', bridge_command, bridge.pid, bridge,
                )
                self.owned.append(bridge_record)
                self._capture_output(bridge_record)
                self.evidence_sink.record(
                    'parameter_bridge_requested', self._facts(bridge_record),
                )
            server_command = self.plan.commands[0]
            server_environment = dict(self.plan.environment)
            for name in tuple(server_environment):
                if name.startswith('MECANUM_B2_HEARTBEAT_'):
                    server_environment.pop(name)
            server_environment['MECANUM_B2_HEARTBEAT_DIAGNOSTICS'] = '0'
            server_environment.update(self._heartbeat_trace_environment)
            server = await self.launcher.start(
                server_command, server_environment,
            )
            server_record = ProcessRecord(
                'server', server_command, server.pid, server,
            )
            self._server_process_record = server_record
            self.owned.append(server_record)
            self._capture_output(server_record)
            self.evidence_sink.record(
                'server_requested', self._facts(server_record),
            )
            await self.readiness.server_scene(
                self.plan, server, self.SERVER_READY_TIMEOUT_S,
            )
            await self._bind_heartbeat_readiness()
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

    async def _prepare_heartbeat_diagnostics(self) -> None:
        """Create optional trace resources only after an explicit opt-in."""
        if not self.heartbeat_diagnostics_enabled:
            return
        try:
            from importlib import import_module

            trace_observer = import_module(
                'mecanum_nav_bringup.local_training_heartbeat_trace_observer'
            )

            directory = self.heartbeat_trace_directory
            if directory is None:
                raise ValueError(
                    'heartbeat trace directory was not configured'
                )
            self._heartbeat_clock = trace_observer.clock_context()
            self._heartbeat_files = trace_observer.prepare_trace_pair(
                directory, collection_id=self.plan.session_id,
            )
            backend_file = next(
                entry for entry in self._heartbeat_files
                if entry['role'] == 'backend'
            )
            observer_file = next(
                entry for entry in self._heartbeat_files
                if entry['role'] == 'observer'
            )
            library = self.heartbeat_library_path
            if library is None:
                prefix = Path(
                    get_package_prefix('mecanum_sim_backend')
                ).resolve(strict=True)
                library = prefix / 'lib/libmecanum_heartbeat_trace_writer.so'
            library = Path(library).resolve(strict=True)
            self._heartbeat_library_sha256 = hashlib.sha256(
                library.read_bytes(),
            ).hexdigest()
            if self.heartbeat_observer_factory is not None:
                # Explicit test adapter only. Production always uses the child.
                self._heartbeat_observer = self.heartbeat_observer_factory(
                    plan=self.plan, trace_file=observer_file,
                    collection_id=self.plan.session_id,
                    clock_provenance=self._heartbeat_clock['provenance'],
                    library_path=library,
                )
                started = self._heartbeat_observer.start()
                snapshot = self._heartbeat_observer.snapshot()
                if started is not True or snapshot.get('ready') is not True:
                    self._heartbeat_trace_error = (
                        'observer_initialization_failed:'
                        + ','.join(snapshot.get('errors', ()))[:320]
                    )
                    return
                self._heartbeat_observer_termination = 'TEST_ADAPTER'
            else:
                await self._start_heartbeat_observer_process(
                    trace_observer, observer_file, library,
                )
            if self._heartbeat_trace_error is not None:
                return
            self._heartbeat_trace_environment = {
                'MECANUM_B2_HEARTBEAT_DIAGNOSTICS': '1',
                'MECANUM_B2_HEARTBEAT_BACKEND_FILE': backend_file['path'],
                'MECANUM_B2_HEARTBEAT_BACKEND_DEVICE': str(
                    backend_file['device']
                ),
                'MECANUM_B2_HEARTBEAT_BACKEND_INODE': str(
                    backend_file['inode']
                ),
                'MECANUM_B2_HEARTBEAT_COLLECTION_ID': self.plan.session_id,
                'MECANUM_B2_HEARTBEAT_SESSION_ID': self.plan.session_id,
                'MECANUM_B2_HEARTBEAT_CONFIG_HASH': self.plan.config_hash,
                'MECANUM_B2_HEARTBEAT_WORLD': 'b2_training_arena',
                'MECANUM_B2_HEARTBEAT_CLOCK': self._heartbeat_clock['clock'],
                'MECANUM_B2_HEARTBEAT_CLOCK_PROVENANCE': (
                    self._heartbeat_clock['provenance']
                ),
            }
        except asyncio.CancelledError:
            self._heartbeat_trace_error = (
                self._heartbeat_trace_error or 'observer_prepare_cancelled'
            )
            raise
        except BaseException as error:
            self._heartbeat_trace_error = (
                f'{type(error).__name__}:{str(error)[:160]}'
            )

    async def _start_heartbeat_observer_process(
        self, trace_observer, observer_file, library,
    ):
        """Start, identify and initialize the isolated observer child."""
        starter = getattr(self.launcher, 'start_controlled', None)
        if starter is None:
            raise RuntimeError('launcher lacks controlled child support')
        domain = self.plan.environment.get('ROS_DOMAIN_ID')
        if (not isinstance(domain, str) or not domain.isascii()
                or not domain.isdecimal() or not 0 <= int(domain) <= 232):
            raise ValueError('observer ROS_DOMAIN_ID binding invalid')
        self._heartbeat_observer_nonce = secrets.token_hex(16)
        environment = dict(self.plan.environment)
        environment['MECANUM_B2_HEARTBEAT_WORKER_NONCE'] = (
            self._heartbeat_observer_nonce
        )
        command = (
            sys.executable, '-m', self.HEARTBEAT_OBSERVER_MODULE, '--worker',
        )
        spawn_deadline = (
            self.monotonic() + self.HEARTBEAT_OBSERVER_START_CAP_S
        )
        self._heartbeat_observer_spawn_task = asyncio.create_task(
            starter(command, environment),
        )
        # Keep spawn owned by this operation.  On the pinned Linux/Python
        # subprocess path, cancellation closes the transport, kills its exact
        # Popen child, and awaits its reap before propagating.  Shielding would
        # let a process handle materialize after supervisor cleanup returned.
        self._heartbeat_observer_process = await asyncio.wait_for(
            self._heartbeat_observer_spawn_task,
            timeout=self.HEARTBEAT_OBSERVER_START_CAP_S,
        )
        process = self._heartbeat_observer_process
        identity = self._heartbeat_identity_reader(process.pid)
        if not RclpyReadiness._valid_process_identity(identity, process.pid):
            raise RuntimeError('observer_process_identity_unverified')
        self._heartbeat_observer_identity = dict(identity)
        self._heartbeat_observer_stderr_task = asyncio.create_task(
            self._drain_observer_stderr(process.stderr),
        )
        if self.monotonic() >= spawn_deadline:
            raise TimeoutError('observer_spawn_completed_after_start_deadline')
        deadline = self.monotonic() + self.HEARTBEAT_OBSERVER_START_CAP_S
        hello = await self._observer_read_frame(deadline)
        module_path = Path(trace_observer.__file__).resolve(strict=True)
        if (
            hello.get('kind') != 'hello'
            or set(hello) != {
                'kind', 'nonce', 'module_path', 'executable', 'prefix',
            }
            or hello.get('nonce') != self._heartbeat_observer_nonce
            or hello.get('module_path') != str(module_path)
            or hello.get('executable') != str(Path(sys.executable).resolve())
            or hello.get('prefix') != str(Path(sys.prefix).resolve())
        ):
            raise RuntimeError('observer_child_binding_unverified')
        fields = {
            'session_id': self.plan.session_id,
            'config_hash': self.plan.config_hash,
            'domain_id': int(domain),
            'collection_id': self.plan.session_id,
            'clock_provenance': self._heartbeat_clock['provenance'],
            'trace_file': observer_file,
            'library_path': str(library),
        }
        await self._observer_send_frame(
            {'kind': 'start', 'nonce': self._heartbeat_observer_nonce,
             'fields': fields}, deadline,
        )
        started = await self._observer_read_frame(deadline)
        if (started.get('kind') != 'started'
                or set(started) != {
                    'kind', 'nonce', 'started', 'snapshot',
                    'clock_domain_certificate',
                }
                or started.get('nonce') != self._heartbeat_observer_nonce
                or started.get('started') is not True
                or not isinstance(started.get('snapshot'), dict)
                or started['snapshot'].get('ready') is not True):
            self._heartbeat_trace_error = 'observer_initialization_failed'
            return
        self._heartbeat_clock_domain_certificate = started.get(
            'clock_domain_certificate',
        )
        self._heartbeat_observer_protocol_started = True
        self._heartbeat_observer_termination = 'RUNNING'

    async def _observer_send_frame(self, message, deadline):
        process = self._heartbeat_observer_process
        if process is None or process.stdin is None:
            raise RuntimeError('observer_control_stdin_unavailable')
        if not self._observer_identity_matches_live_process():
            raise RuntimeError('observer_process_identity_unknown')
        raw = self.HEARTBEAT_OBSERVER_FRAME + json.dumps(
            message, sort_keys=True, separators=(',', ':'),
        ).encode('utf-8') + b'\n'
        if len(raw) > self.HEARTBEAT_OBSERVER_MAX_FRAME + len(
                self.HEARTBEAT_OBSERVER_FRAME) + 1:
            raise ValueError('observer_control_frame_oversized')
        remaining = deadline - self.monotonic()
        if remaining <= 0:
            raise TimeoutError('observer_control_deadline_expired')
        process.stdin.write(raw[len(self.HEARTBEAT_OBSERVER_FRAME):])
        await asyncio.wait_for(process.stdin.drain(), timeout=remaining)

    async def _observer_read_frame(self, deadline):
        process = self._heartbeat_observer_process
        if process is None or process.stdout is None:
            raise RuntimeError('observer_control_stdout_unavailable')
        remaining = deadline - self.monotonic()
        if remaining <= 0:
            raise TimeoutError('observer_control_deadline_expired')
        raw = await asyncio.wait_for(
            process.stdout.readline(), timeout=remaining,
        )
        if (not raw or not raw.endswith(b'\n')
                or len(raw) > self.HEARTBEAT_OBSERVER_MAX_FRAME + len(
                    self.HEARTBEAT_OBSERVER_FRAME) + 1):
            raise ValueError('observer_control_frame_missing_or_oversized')
        if not raw.startswith(self.HEARTBEAT_OBSERVER_FRAME):
            raise ValueError('observer_control_frame_prefix_invalid')
        result = json.loads(raw[len(self.HEARTBEAT_OBSERVER_FRAME):])
        if (not isinstance(result, dict)
                or result.get('nonce') not in (
                    None, self._heartbeat_observer_nonce,
                )):
            raise ValueError('observer_control_frame_binding_invalid')
        return result

    def _observer_identity_matches_live_process(self):
        process = self._heartbeat_observer_process
        expected = self._heartbeat_observer_identity
        if (process is None or expected is None
                or process.returncode is not None):
            return False
        try:
            current = self._heartbeat_identity_reader(process.pid)
        except BaseException:
            return False
        return (
            RclpyReadiness._valid_process_identity(current, process.pid)
            and current == expected
        )

    async def _signal_observer_process(self, sig):
        """Signal only a group with the captured live leader identity."""
        process = self._heartbeat_observer_process
        if (process is None
                or not self._observer_identity_matches_live_process()):
            return False
        try:
            await self.launcher.stop_group(process, sig)
        except BaseException:
            return False
        return True

    async def _wait_observer_reaped(self, deadline):
        process = self._heartbeat_observer_process
        if process is None:
            return False
        if self._heartbeat_observer_wait_task is None:
            self._heartbeat_observer_wait_task = asyncio.create_task(
                process.wait(),
            )
        waiter = self._heartbeat_observer_wait_task
        while True:
            if not waiter.done():
                remaining = deadline - self.monotonic()
                if remaining <= 0:
                    return False
                done, _ = await asyncio.wait(
                    (waiter,), timeout=min(0.05, remaining),
                )
                if not done:
                    continue
            try:
                self._heartbeat_observer_exit_status = waiter.result()
            except BaseException:
                return False
            try:
                group_alive = self.launcher.group_alive(process)
            except BaseException:
                return False
            if not group_alive:
                return True
            remaining = deadline - self.monotonic()
            if remaining <= 0:
                return False
            await self.sleep(min(0.02, remaining))

    async def _stop_observer_process(self):
        """Stop the isolated child within one fixed cleanup deadline."""
        if self._heartbeat_observer_cleanup_deadline is None:
            self._heartbeat_observer_cleanup_deadline = (
                self.monotonic() + self.HEARTBEAT_OBSERVER_CLEANUP_CAP_S
            )
        deadline = self._heartbeat_observer_cleanup_deadline
        spawn_task = self._heartbeat_observer_spawn_task
        if self._heartbeat_observer_process is None and spawn_task is not None:
            remaining = deadline - self.monotonic()
            if remaining > 0:
                done, _ = await asyncio.wait((spawn_task,), timeout=remaining)
                if done:
                    try:
                        self._heartbeat_observer_process = spawn_task.result()
                        identity = self._heartbeat_identity_reader(
                            self._heartbeat_observer_process.pid,
                        )
                        pid = self._heartbeat_observer_process.pid
                        if RclpyReadiness._valid_process_identity(
                                identity, pid):
                            self._heartbeat_observer_identity = dict(identity)
                        else:
                            self._process_residue = 'UNKNOWN'
                    except BaseException:
                        pass
            if self._heartbeat_observer_process is None:
                self._process_residue = 'UNKNOWN'
                self._heartbeat_observer_termination = 'UNKNOWN'
                return {
                    'joined': False, 'group_absent': False,
                    'identity_verified': False, 'exit_status': None,
                    'stop_acknowledged': False, 'writer_closed': False,
                    'termination': 'UNKNOWN',
                    'errors': ('observer_spawn_handle_unresolved',),
                }
        process = self._heartbeat_observer_process
        if process is None:
            return None
        errors = []
        clean_ack = False
        if (
            self._heartbeat_observer_protocol_started
            and process.returncode is None
            and self._observer_identity_matches_live_process()
            and self.monotonic() < deadline
        ):
            phase_deadline = min(deadline, self.monotonic() + 0.35)
            try:
                async with self._heartbeat_observer_protocol_lock:
                    await self._observer_send_frame({
                        'kind': 'stop',
                        'nonce': self._heartbeat_observer_nonce,
                        'timeout_s': max(
                            0.0, min(0.25, phase_deadline - self.monotonic()),
                        ),
                    }, phase_deadline)
                    response = await self._observer_read_frame(phase_deadline)
                clean_ack = (
                    response.get('kind') == 'stopped'
                    and response.get('nonce') == self._heartbeat_observer_nonce
                    and response.get('joined') is True
                    and response.get('end_written') is True
                    and response.get('handle_closed') is True
                    and response.get('writer_closed') is True
                    and isinstance(response.get('snapshot'), dict)
                    and response['snapshot'].get('end_written') is True
                    and response['snapshot'].get('handle_closed') is True
                    and response['snapshot'].get('writer_closed') is True
                )
                self._heartbeat_observer_stop_acknowledged = clean_ack
                snapshot = response.get('snapshot')
                self._heartbeat_observer_end_written = bool(
                    snapshot and snapshot.get('end_written') is True
                )
                self._heartbeat_observer_handle_closed = bool(
                    snapshot and snapshot.get('handle_closed') is True
                )
                self._heartbeat_observer_writer_closed = (
                    self._heartbeat_observer_end_written
                    and self._heartbeat_observer_handle_closed
                )
                self._heartbeat_observer_state = snapshot
            except BaseException as error:
                errors.append(f'observer_stop_ack:{type(error).__name__}')
        cooperative_deadline = min(
            deadline, max(self.monotonic(), deadline - 0.75),
        )
        if clean_ack and await self._wait_observer_reaped(
                cooperative_deadline):
            self._heartbeat_observer_termination = 'CLEAN_COOPERATIVE'
        else:
            if process.returncode is None:
                remaining = deadline - self.monotonic()
                term_wait = max(0.0, min(0.65, remaining - 0.75))
                if term_wait > 0:
                    if await self._signal_observer_process(
                            signal.SIGTERM):
                        self._heartbeat_observer_termination = 'SIGTERM'
                        await self._wait_observer_reaped(
                            min(deadline, self.monotonic() + term_wait),
                        )
                    else:
                        errors.append(
                            'observer_sigterm_identity_or_dispatch_unknown'
                        )
            try:
                leader_live_or_group_live = (
                    process.returncode is None
                    or self.launcher.group_alive(process)
                )
            except BaseException:
                leader_live_or_group_live = True
                errors.append('observer_group_state_unknown')
            if leader_live_or_group_live:
                if self.monotonic() < deadline:
                    if await self._signal_observer_process(
                            signal.SIGKILL):
                        self._heartbeat_observer_termination = 'SIGKILL'
                    else:
                        errors.append(
                            'observer_sigkill_identity_or_dispatch_unknown'
                        )
            if not await self._wait_observer_reaped(deadline):
                errors.append('observer_process_reap_or_group_join_unknown')
                self._process_residue = 'UNKNOWN'
                self._heartbeat_observer_termination = 'UNKNOWN'
        joined = self._heartbeat_observer_wait_task is not None and (
            self._heartbeat_observer_wait_task.done()
            and self._heartbeat_observer_exit_status is not None
        )
        group_absent = False
        try:
            group_absent = not self.launcher.group_alive(process)
        except BaseException:
            pass
        if self._heartbeat_observer_stderr_task is not None:
            remaining = max(0.0, deadline - self.monotonic())
            if remaining > 0:
                done, _ = await asyncio.wait(
                    (self._heartbeat_observer_stderr_task,), timeout=remaining,
                )
                if not done:
                    self._heartbeat_observer_stderr_task.cancel()
                    errors.append('observer_stderr_drain_unknown')
                    self._task_residue = 'UNKNOWN'
            elif not self._heartbeat_observer_stderr_task.done():
                self._heartbeat_observer_stderr_task.cancel()
                errors.append('observer_stderr_drain_deadline')
                self._task_residue = 'UNKNOWN'
        if process.stdin is not None:
            try:
                process.stdin.close()
                remaining = max(0.0, deadline - self.monotonic())
                if remaining > 0:
                    await asyncio.wait_for(
                        process.stdin.wait_closed(), timeout=remaining,
                    )
            except BaseException:
                errors.append('observer_control_stdin_close_unknown')
        if not joined or not group_absent:
            self._process_residue = 'UNKNOWN'
        if (joined and not self._heartbeat_observer_stop_acknowledged
                and self._heartbeat_observer_termination in {
                    'NOT_STARTED', 'RUNNING',
                }):
            self._heartbeat_observer_termination = 'UNCONFIRMED_EXIT'
        self._heartbeat_observer_state = self._heartbeat_observer_state or {
            'ready': False, 'errors': tuple(errors),
        }
        self._heartbeat_observer_state.update({
            'process_identity': self._heartbeat_observer_identity,
            'process_joined': joined, 'group_absent': group_absent,
            'exit_status': self._heartbeat_observer_exit_status,
            'stop_acknowledged': self._heartbeat_observer_stop_acknowledged,
            'end_written': self._heartbeat_observer_end_written,
            'handle_closed': self._heartbeat_observer_handle_closed,
            'writer_closed': self._heartbeat_observer_writer_closed,
            'termination': self._heartbeat_observer_termination,
            'stderr_bytes': self._heartbeat_observer_stderr_total,
            'stderr_excerpt': self._heartbeat_observer_stderr.decode(
                'utf-8', errors='replace',
            )[:1024],
            'stderr_truncated': self._heartbeat_observer_stderr_total > len(
                self._heartbeat_observer_stderr,
            ),
            'errors': tuple(self._heartbeat_observer_state.get('errors', ()))
            + tuple(errors),
        })
        return {
            'joined': joined, 'group_absent': group_absent,
            'identity_verified': self._heartbeat_observer_identity is not None,
            'exit_status': self._heartbeat_observer_exit_status,
            'stop_acknowledged': self._heartbeat_observer_stop_acknowledged,
            'end_written': self._heartbeat_observer_end_written,
            'handle_closed': self._heartbeat_observer_handle_closed,
            'writer_closed': self._heartbeat_observer_writer_closed,
            'termination': self._heartbeat_observer_termination,
            'errors': tuple(errors),
        }

    async def _drain_observer_stderr(self, stream):
        """Drain stderr to avoid blocking, retaining only a bounded excerpt."""
        if stream is None:
            return
        cap = 8192
        while True:
            chunk = await stream.read(1024)
            if not chunk:
                return
            self._heartbeat_observer_stderr_total += len(chunk)
            remaining = cap - len(self._heartbeat_observer_stderr)
            if remaining > 0:
                self._heartbeat_observer_stderr.extend(chunk[:remaining])

    async def _bind_observer_child(self, status):
        deadline = self.monotonic() + self.HEARTBEAT_OBSERVER_START_CAP_S
        async with self._heartbeat_observer_protocol_lock:
            await self._observer_send_frame({
                'kind': 'bind', 'nonce': self._heartbeat_observer_nonce,
                'status': status,
            }, deadline)
            result = await self._observer_read_frame(deadline)
        return (result.get('kind') == 'bound'
                and result.get('accepted') is True)

    async def _bind_heartbeat_readiness(self) -> None:
        """Bind trace identity to status accepted by the readiness parent."""
        if not self.heartbeat_diagnostics_enabled:
            return
        status = getattr(self.readiness, 'accepted_backend_status', None)
        if not isinstance(status, dict) or not status:
            self._heartbeat_trace_error = (
                self._heartbeat_trace_error
                or 'independent_readiness_backend_binding_unavailable'
            )
            return
        observer = self._heartbeat_observer
        binder = getattr(observer, 'bind_readiness_backend', None)
        if observer is not None:
            accepted = binder is not None and binder(status) is True
        elif self._heartbeat_observer_process is not None:
            try:
                accepted = await self._bind_observer_child(status)
            except asyncio.CancelledError:
                self._heartbeat_trace_error = (
                    self._heartbeat_trace_error or 'observer_bind_cancelled'
                )
                raise
            except BaseException as error:
                self._heartbeat_trace_error = (
                    self._heartbeat_trace_error
                    or f'observer_readiness_bind:{type(error).__name__}'
                )
                accepted = False
        else:
            accepted = False
        if not accepted:
            self._heartbeat_trace_error = (
                self._heartbeat_trace_error
                or 'observer_readiness_backend_binding_failed'
            )
            return
        self._heartbeat_readiness_status = dict(status)

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
        records = {record.name: record for record in self.owned}
        server_record = records.get('server')
        if server_record is None:
            raise RuntimeError('no owned server process')
        bridge_record = records.get('parameter_bridge')
        gui_record = records.get('gui')
        waiters: dict[asyncio.Task, ProcessRecord] = {
            asyncio.create_task(record.process.wait()): record
            for record in (server_record, bridge_record)
            if record is not None
        }
        for task in waiters:
            self._track_observer(task)
        if gui_record is not None and gui_record.process.returncode is None:
            self._track_observer(asyncio.create_task(
                self._record_gui_exit(gui_record),
            ))
        try:
            done, _ = await asyncio.wait(
                waiters, return_when=asyncio.FIRST_COMPLETED,
            )
            completed = [(waiters[task], task.result()) for task in done]
            bridge_exit = next(
                ((record, status) for record, status in completed
                 if record.name == 'parameter_bridge'), None,
            )
            if bridge_exit is not None:
                record, status = bridge_exit
                raise RuntimeError(
                    f'owned infrastructure {record.name} exited: {status}'
                )
            return next(status for record, status in completed
                        if record.name == 'server')
        finally:
            for task in waiters:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*waiters, return_exceptions=True)
            await self.cleanup()

    def _track_observer(self, task: asyncio.Task) -> None:
        self._observer_tasks.add(task)
        task.add_done_callback(self._observer_tasks.discard)

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
        async with self._cleanup_lock:
            try:
                await self._cleanup_owned()
            finally:
                await self._stop_heartbeat_diagnostics()

    async def _cleanup_owned(self) -> None:
        current = asyncio.current_task()
        observers = [
            task for task in self._observer_tasks if task is not current
        ]
        for task in observers:
            task.cancel()
        if observers:
            await asyncio.gather(*observers, return_exceptions=True)
        self._observer_tasks.difference_update(observers)
        records, self.owned = list(reversed(self.owned)), []
        for record in records:
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

    async def _stop_heartbeat_diagnostics(self) -> None:
        if (not self.heartbeat_diagnostics_enabled
                or self._heartbeat_trace_reported):
            return
        observer_state = None
        server_record = self._server_process_record
        server_exit_status = (
            server_record.process.returncode
            if server_record is not None else None
        )
        server_group_absent = False
        if server_record is not None:
            try:
                server_group_absent = not self.launcher.group_alive(
                    server_record.process,
                )
            except BaseException as error:
                self._heartbeat_trace_error = (
                    self._heartbeat_trace_error
                    or f'server_group_identity_unknown:{type(error).__name__}'
                )
        observer_join = None
        if self._heartbeat_observer_process is not None or (
                self._heartbeat_observer_spawn_task is not None):
            observer_join = await self._stop_observer_process()
            observer_state = self._heartbeat_observer_state
            if (observer_join is None
                    or observer_join.get('joined') is not True):
                self._heartbeat_trace_error = (
                    self._heartbeat_trace_error
                    or 'observer_process_reap_or_group_join_unknown'
                )
            if (observer_join
                    and observer_join.get('writer_closed') is not True):
                self._heartbeat_trace_error = (
                    self._heartbeat_trace_error
                    or 'observer_writer_close_unconfirmed'
                )
        elif self._heartbeat_observer is not None:
            try:
                stop_async = getattr(
                    self._heartbeat_observer, 'stop_async', None,
                )
                stopped = (
                    await stop_async(2.0) if stop_async is not None
                    else self._heartbeat_observer.stop(2.0)
                )
                observer_state = self._heartbeat_observer.snapshot()
                if not stopped:
                    self._heartbeat_trace_error = (
                        self._heartbeat_trace_error
                        or 'observer_join_residue_unknown'
                    )
            except BaseException as error:
                self._heartbeat_trace_error = (
                    self._heartbeat_trace_error or
                    f'observer_cleanup:{type(error).__name__}'
                )
        facts = {
            'session_id': self.plan.session_id,
            'config_hash': self.plan.config_hash,
            'world': 'b2_training_arena',
            'clock_context': self._heartbeat_clock,
            'clock_library_sha256': self._heartbeat_library_sha256,
            'clock_domain_certificate': (
                self._heartbeat_clock_domain_certificate
            ),
            'files': list(self._heartbeat_files),
            'observer': observer_state,
            'readiness_backend_status': getattr(
                self, '_heartbeat_readiness_status', None,
            ),
            'readiness_binding_verified': bool(
                getattr(self, '_heartbeat_readiness_status', None)
                and observer_state
                and observer_state.get('readiness_backend_instance_id')
                == self._heartbeat_readiness_status.get(
                    'backend_instance_id',
                )
            ),
            'join_evidence': {
                'server_exit_status': server_exit_status,
                'server_process_joined': bool(
                    server_record is not None
                    and server_exit_status is not None
                ),
                'server_group_absent': server_group_absent,
                'observer_process_identity': (
                    dict(self._heartbeat_observer_identity)
                    if self._heartbeat_observer_identity else None
                ),
                'observer_process_identity_verified': bool(
                    self._heartbeat_observer_identity
                    and self._heartbeat_observer_process is not None
                ),
                'observer_process_joined': bool(
                    observer_join and observer_join.get('joined') is True
                ),
                'observer_process_group_absent': bool(
                    observer_join and observer_join.get('group_absent') is True
                ),
                'observer_exit_status': (
                    observer_join.get('exit_status') if observer_join else None
                ),
                'observer_stop_acknowledged': bool(
                    observer_join
                    and observer_join.get('stop_acknowledged') is True
                ),
                'observer_end_written': bool(
                    observer_join
                    and observer_join.get('end_written') is True
                ),
                'observer_handle_closed': bool(
                    observer_join
                    and observer_join.get('handle_closed') is True
                ),
                'observer_writer_closed': bool(
                    observer_join
                    and observer_join.get('writer_closed') is True
                ),
                'observer_termination': (
                    observer_join.get('termination') if observer_join
                    else self._heartbeat_observer_termination
                ),
                'task_residue': (
                    'NONE' if not self._observer_tasks
                    and self._task_residue == 'NONE'
                    and self._process_residue == 'NONE' else 'UNKNOWN'
                ),
            },
            'trace_error': self._heartbeat_trace_error,
            'coverage_note': (
                'diagnostic records require process reap and group absence'
            ),
            'sink_record_measurement': (
                'NOT_INSTRUMENTED_NO_EXISTING_CALLBACK_CALL'
            ),
        }
        self._heartbeat_trace_reported = True
        try:
            self.evidence_sink.record('heartbeat_trace_collection', facts)
        except BaseException as error:
            self._heartbeat_trace_error = (
                self._heartbeat_trace_error or
                f'trace_summary_sink_failed:{type(error).__name__}'
            )


def _load_sink(specification: str) -> EvidenceSink:
    if ':' not in specification:
        raise RuntimeError(
            'B2.3 evidence sink must be injected as module:factory'
        )
    module_name, factory_name = specification.split(':', 1)
    factory = getattr(importlib.import_module(module_name), factory_name)
    return factory()


def _physics_engine_plugin_path() -> Path:
    """Resolve the pinned DART engine directory from its installed package."""
    prefix = Path(get_package_prefix('gz_physics_vendor')).resolve(strict=True)
    library_root = prefix / 'opt/gz_physics_vendor/lib'
    matches = sorted({
        entry.parent.resolve(strict=True)
        for entry in library_root.rglob('*dartsim-plugin.so*')
        if entry.is_file() and entry.parent.name == 'engine-plugins'
    }) if library_root.is_dir() else []
    if len(matches) != 1:
        raise RuntimeError(
            'pinned Gazebo DART engine plugin path is missing or ambiguous'
        )
    return matches[0]


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
            bridge_config=(
                bringup_share / 'config/bridge/local_training.runtime.yaml'
            ),
            resource_paths=(
                description_share.parent, description_share / 'models',
            ),
            plugin_path=backend_prefix / 'lib',
            physics_engine_plugin_path=_physics_engine_plugin_path(),
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
            heartbeat_diagnostics_enabled=(
                os.environ.get('MECANUM_B2_HEARTBEAT_DIAGNOSTICS') == '1'
            ),
            heartbeat_trace_directory=(
                Path(os.environ['MECANUM_B2_HEARTBEAT_TRACE_DIR'])
                if os.environ.get('MECANUM_B2_HEARTBEAT_TRACE_DIR') else None
            ),
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
